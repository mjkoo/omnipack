from __future__ import annotations

import json

import pytest

import scripts.nightly
from scripts.nightly import ApiResponse
from scripts.nightly_release import (
    RELEASE_PATH,
    TAG_REF_PATH,
    BootstrapConflict,
    bootstrap_release,
    parse_state,
    seed_body,
)


class ControlledApi:
    def __init__(self, responses: list[ApiResponse | BaseException]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, path: str, body=None) -> ApiResponse:
        self.calls.append((method, path, body))
        outcome = self.responses.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def response(status: int, body: object = None) -> ApiResponse:
    encoded = b"" if body is None else json.dumps(body).encode()
    return ApiResponse(status, {}, encoded)


def release(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": 123,
        "tag_name": "continuous",
        "name": "omnipack revision 0",
        "body": seed_body(),
        "draft": False,
        "prerelease": True,
        "immutable": False,
        "assets": [],
    }
    value.update(changes)
    return value


def test_absent_seed_creates_once_at_canonical_main_without_assets() -> None:
    api = ControlledApi([response(404), response(404), response(201, release())])
    result = bootstrap_release(api)
    assert result.created is True
    assert [call[:2] for call in api.calls] == [
        ("GET", RELEASE_PATH),
        ("GET", TAG_REF_PATH),
        ("POST", "/repos/mjkoo/omnipack/releases"),
    ]
    payload = api.calls[-1][2]
    assert isinstance(payload, dict)
    assert payload == {
        "tag_name": "continuous",
        "target_commitish": "main",
        "name": "omnipack revision 0",
        "body": seed_body(),
        "draft": False,
        "prerelease": True,
    }
    assert "assets" not in payload


def test_existing_owned_seed_is_idempotent() -> None:
    api = ControlledApi([response(200, release())])
    assert bootstrap_release(api).created is False
    assert len(api.calls) == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"body": "somebody else's release"},
        {"body": seed_body().replace('"schemaVersion":1', '"schemaVersion":2')},
        {"name": "omnipack revision 9"},
        {"immutable": True},
        {"assets": [{"name": "unexpected.zip"}]},
    ],
)
def test_conflicting_malformed_and_immutable_releases_fail_without_writes(
    changed: dict[str, object],
) -> None:
    api = ControlledApi([response(200, release(**changed))])
    with pytest.raises(BootstrapConflict):
        bootstrap_release(api)
    assert [call[0] for call in api.calls] == ["GET"]


def test_bare_tag_conflict_fails_without_creation() -> None:
    api = ControlledApi([response(404), response(200, {"ref": "refs/tags/continuous"})])
    with pytest.raises(BootstrapConflict, match="tag already exists"):
        bootstrap_release(api)
    assert [call[0] for call in api.calls] == ["GET", "GET"]


def test_ambiguous_creation_is_reconciled_before_any_repeat() -> None:
    api = ControlledApi(
        [
            response(404),
            response(404),
            OSError("response lost"),
            response(200, release()),
        ]
    )
    result = bootstrap_release(api)
    assert result.created is True
    assert [call[0] for call in api.calls].count("POST") == 1
    assert api.calls[-1][:2] == ("GET", RELEASE_PATH)


def test_ambiguous_creation_without_owned_readback_fails_without_retry() -> None:
    api = ControlledApi(
        [response(404), response(404), OSError("response lost"), response(404)]
    )
    with pytest.raises(BootstrapConflict, match="outcome is unknown"):
        bootstrap_release(api)
    assert [call[0] for call in api.calls].count("POST") == 1


@pytest.mark.parametrize(
    "corruption",
    [
        lambda body: body.replace('"pending":null', '"extra":null,"pending":null'),
        lambda body: body.replace('"revision":0', '"revision":false'),
        lambda body: body.replace('"schemaVersion":1', '"schemaVersion":NaN'),
        lambda body: body.replace('"pending":null', '"pending":null,"pending":null'),
        lambda body: body.replace(
            '"sourceCommit":null', '"sourceCommit":"not-a-commit"'
        ),
        lambda body: body.replace(
            '"single-screen.json":null', '"single-screen.json":"abc"'
        ),
        lambda body: body + "\n" + body[body.index("<!-- omnipack:rolling-state") :],
        lambda body: body + " trailing",
    ],
    ids=(
        "unknown-field",
        "boolean-revision",
        "non-finite-number",
        "duplicate-field",
        "invalid-source-commit",
        "invalid-digest",
        "duplicate-state-block",
        "trailing-content",
    ),
)
def test_state_parser_rejects_unknown_invalid_duplicate_and_trailing_state(
    corruption,
) -> None:
    with pytest.raises(BootstrapConflict):
        parse_state(corruption(seed_body()))


@pytest.mark.parametrize(
    "assets",
    [
        [None],
        [{}],
        [{"name": "single-screen.json"}, {"name": "single-screen.json"}],
    ],
)
def test_malformed_and_duplicate_asset_metadata_is_a_conflict(
    assets: list[object],
) -> None:
    with pytest.raises(BootstrapConflict):
        bootstrap_release(ControlledApi([response(200, release(assets=assets))]))


def test_explicit_cli_can_run_from_a_local_change_ref_but_targets_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = ControlledApi([response(404), response(404), response(201, release())])
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(scripts.nightly, "_api", lambda _environ: api)

    assert scripts.nightly.main(["bootstrap-release"]) == 0
    payload = api.calls[-1][2]
    assert isinstance(payload, dict)
    assert payload["target_commitish"] == "main"


def test_explicit_cli_rejects_noncanonical_repository_before_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "fork/omnipack")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(
        scripts.nightly,
        "_api",
        lambda _environ: pytest.fail("API must not be constructed"),
    )

    assert scripts.nightly.main(["bootstrap-release"]) == 1
