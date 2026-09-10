from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

import pytest

import scripts.nightly
from scripts.nightly import ApiResponse
from scripts.nightly_release import (
    RELEASE_PATH,
    TAG_REF_PATH,
    BootstrapConflict,
    ReleaseError,
    bootstrap_release,
    parse_state,
    seed_body,
)
from scripts.nightly_release_sync import (
    ReleaseAsset,
    SyncFailure,
    SyncResult,
    synchronize_release,
)
from scripts.nightly_release_transport import MAX_ASSET_BYTES, GitHubReleaseRemote


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


class ControlledReleaseRemote:
    def __init__(
        self, document: dict[str, object], blobs: dict[str, bytes] | None = None
    ) -> None:
        self.document: dict[str, Any] = document
        self.blobs = dict(blobs or {})
        self.calls: list[tuple[str, object]] = []
        self.ambiguous: set[str] = set()
        self.fail: dict[str, ReleaseError] = {}
        self.next_id = 10
        self.ambiguous_update_number: int | None = None
        self.update_count = 0

    def discover(self) -> dict[str, object]:
        self.calls.append(("discover", None))
        return self.document

    def update(self, release_id: int, *, title: str, body: str) -> None:
        self.calls.append(("update", (release_id, title, body)))
        self.update_count += 1
        if self.update_count == self.ambiguous_update_number:
            self.ambiguous.add("update")
        self._fail_or_apply(
            "update", lambda: self.document.update(name=title, body=body)
        )

    def delete_asset(self, asset: ReleaseAsset) -> None:
        self.calls.append(("delete", asset.name))

        def apply() -> None:
            self.document["assets"] = [
                a for a in self.document["assets"] if a["id"] != asset.asset_id
            ]  # type: ignore[index]
            self.blobs.pop(asset.name, None)

        self._fail_or_apply("delete", apply)

    def upload_asset(self, release_id: int, name: str, content: bytes) -> None:
        self.calls.append(("upload", name))

        def apply() -> None:
            self.document["assets"].append(
                {
                    "id": self.next_id,
                    "name": name,
                    "url": f"https://api.github.com/assets/{self.next_id}",
                }
            )  # type: ignore[union-attr]
            self.next_id += 1
            self.blobs[name] = content

        self._fail_or_apply("upload", apply)

    def download_asset(self, asset: ReleaseAsset) -> bytes:
        self.calls.append(("download", asset.name))
        return self.blobs[asset.name]

    def _fail_or_apply(self, operation: str, apply) -> None:
        if operation in self.fail:
            raise self.fail[operation]
        apply()
        if operation in self.ambiguous:
            self.ambiguous.remove(operation)
            raise OSError("response lost")


def completed_release(
    single: bytes, dual: bytes, revision: int = 3
) -> dict[str, object]:
    from scripts.nightly_release import (
        DigestPair,
        PublishedTarget,
        RollingState,
        state_body,
    )

    target = PublishedTarget(
        revision,
        "a" * 40,
        DigestPair(sha256(single).hexdigest(), sha256(dual).hexdigest()),
    )
    return release(
        name=f"omnipack revision {revision}",
        body=state_body(RollingState(target, None)),
        assets=[
            {
                "id": 1,
                "name": "single-screen.json",
                "url": "https://api.github.com/assets/1",
            },
            {
                "id": 2,
                "name": "dual-screen.json",
                "url": "https://api.github.com/assets/2",
            },
        ],
    )


def test_first_pair_promotes_seed_to_one_and_one_change_advances_pair_once() -> None:
    remote = ControlledReleaseRemote(release())
    result = synchronize_release(remote, b"single", b"dual", "b" * 40)
    assert result == SyncResult(1, True, False)
    assert remote.document["name"] == "omnipack revision 1"
    assert [call[0] for call in remote.calls].count("update") == 2

    result = synchronize_release(remote, b"single changed", b"dual", "c" * 40)
    assert result.revision == 2
    assert result.changed is True


def test_unchanged_pair_repairs_corruption_without_increment() -> None:
    document = completed_release(b"single", b"dual")
    remote = ControlledReleaseRemote(
        document, {"single-screen.json": b"corrupt", "dual-screen.json": b"dual"}
    )
    result = synchronize_release(remote, b"single", b"dual", "d" * 40)
    assert result == SyncResult(3, False, True)
    assert remote.document["name"] == "omnipack revision 3"
    assert [call for call in remote.calls if call[0] == "upload"] == [
        ("upload", "single-screen.json")
    ]


def test_interrupted_upload_recovers_without_duplicate_increment() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    remote.ambiguous.add("upload")
    result = synchronize_release(remote, b"new-s", b"new-d", "e" * 40)
    assert result.revision == 4
    assert [
        call for call in remote.calls if call == ("upload", "single-screen.json")
    ] == [("upload", "single-screen.json")]


def test_ambiguous_promotion_uses_readback_without_repeat() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    # First update writes pending; the second promotes and loses its response.
    remote.ambiguous_update_number = 2
    assert synchronize_release(remote, b"new-s", b"new-d", "f" * 40).revision == 4
    assert remote.update_count == 2


def test_ambiguous_pending_write_uses_readback_before_asset_mutation() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    remote.ambiguous_update_number = 1
    assert synchronize_release(remote, b"new-s", b"new-d", "f" * 40).revision == 4
    assert remote.update_count == 2


def test_ambiguous_delete_rediscovers_absence_before_one_upload() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    remote.ambiguous.add("delete")
    assert synchronize_release(remote, b"new-s", b"new-d", "f" * 40).revision == 4
    assert [
        call for call in remote.calls if call == ("delete", "single-screen.json")
    ] == [("delete", "single-screen.json")]


@pytest.mark.parametrize("operation", ["pending", "delete", "upload", "promotion"])
@pytest.mark.parametrize("ambiguous", [False, True])
def test_replacement_release_stops_reconciliation(
    operation: str, ambiguous: bool
) -> None:
    class ReplacingRemote(ControlledReleaseRemote):
        replacement_seen_at: int | None = None

        def discover(self) -> dict[str, object]:
            last = self.calls[-1][0] if self.calls else None
            trigger = (
                last == "update"
                and self.update_count == (1 if operation == "pending" else 2)
                if operation in {"pending", "promotion"}
                else last == operation
            )
            if trigger and self.replacement_seen_at is None:
                self.document["id"] = 456
                self.replacement_seen_at = len(self.calls)
            return super().discover()

    remote = ReplacingRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    if ambiguous:
        if operation in {"pending", "promotion"}:
            remote.ambiguous_update_number = 1 if operation == "pending" else 2
        else:
            remote.ambiguous.add(operation)
    with pytest.raises(SyncFailure, match="release identity changed") as failure:
        synchronize_release(remote, b"new-s", b"new-d", "f" * 40)
    assert failure.value.pending_revision is None
    assert remote.replacement_seen_at is not None
    assert all(
        call[0] == "discover" for call in remote.calls[remote.replacement_seen_at :]
    )


def test_failure_diagnostics_do_not_use_replacement_pending_state() -> None:
    class ReplacingRemote(ControlledReleaseRemote):
        def discover(self) -> dict[str, object]:
            if self.calls and self.calls[-1][0] == "upload":
                self.document["id"] = 456
            return super().discover()

    remote = ReplacingRemote(release())
    remote.fail["upload"] = ReleaseError("upload denied")
    with pytest.raises(SyncFailure, match="upload denied") as failure:
        synchronize_release(remote, b"single", b"dual", "f" * 40)
    assert failure.value.pending_revision is None
    assert remote.calls[-1] == ("discover", None)


def test_invalid_source_commit_fails_before_remote_access() -> None:
    remote = ControlledReleaseRemote(release())
    with pytest.raises(ReleaseError, match="source commit"):
        synchronize_release(remote, b"single", b"dual", "main")
    assert remote.calls == []


def test_superseded_pending_uses_completed_plus_one() -> None:
    from scripts.nightly_release import (
        DigestPair,
        PublishedTarget,
        RollingState,
        state_body,
    )

    doc = completed_release(b"old-s", b"old-d")
    completed = PublishedTarget(
        3,
        "a" * 40,
        DigestPair(sha256(b"old-s").hexdigest(), sha256(b"old-d").hexdigest()),
    )
    stale = PublishedTarget(4, "b" * 40, DigestPair("1" * 64, "2" * 64))
    doc["body"] = state_body(RollingState(completed, stale))
    remote = ControlledReleaseRemote(
        doc, {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"}
    )
    assert synchronize_release(remote, b"new-s", b"new-d", "f" * 40).revision == 4


def test_desired_completed_restores_assets_and_clears_pending() -> None:
    from scripts.nightly_release import (
        DigestPair,
        PublishedTarget,
        RollingState,
        parse_state,
        state_body,
    )

    doc = completed_release(b"old-s", b"old-d")
    completed = PublishedTarget(
        3,
        "a" * 40,
        DigestPair(sha256(b"old-s").hexdigest(), sha256(b"old-d").hexdigest()),
    )
    stale = PublishedTarget(4, "b" * 40, DigestPair("1" * 64, "2" * 64))
    doc["body"] = state_body(RollingState(completed, stale))
    remote = ControlledReleaseRemote(
        doc, {"single-screen.json": b"wrong", "dual-screen.json": b"wrong"}
    )
    result = synchronize_release(remote, b"old-s", b"old-d", "a" * 40)
    assert result.revision == 3
    assert parse_state(remote.document["body"]).pending is None


def test_permission_failure_is_not_retried_or_converted_to_ambiguity() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"old-s", b"old-d"),
        {"single-screen.json": b"old-s", "dual-screen.json": b"old-d"},
    )
    remote.fail["update"] = ReleaseError("release update failed with status 403")
    with pytest.raises(ReleaseError, match="403"):
        synchronize_release(remote, b"new-s", b"new-d", "f" * 40)
    assert [call[0] for call in remote.calls].count("update") == 1


def test_failed_second_asset_does_not_advertise_pending_revision() -> None:
    remote = ControlledReleaseRemote(
        completed_release(b"single", b"old-dual"),
        {"single-screen.json": b"single", "dual-screen.json": b"old-dual"},
    )
    remote.fail["upload"] = ReleaseError("asset upload failed with status 403")
    with pytest.raises(SyncFailure) as caught:
        synchronize_release(remote, b"single", b"new-dual", "f" * 40)
    assert remote.document["name"] == "omnipack revision 3"
    assert caught.value.outcome == "failure"
    assert caught.value.pending_revision == 4


class Opened:
    def __init__(
        self, status: int, body: bytes, headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


def test_release_transport_scopes_auth_and_removes_it_from_signed_redirect() -> None:
    trusted_requests = []
    unsigned_requests = []

    def trusted(request, *, timeout):
        trusted_requests.append(request)
        return Opened(
            302, b"", {"Location": "https://objects.example.net/signed?key=value"}
        )

    def unsigned(request, *, timeout):
        unsigned_requests.append(request)
        return Opened(200, b"asset bytes")

    remote = GitHubReleaseRemote(
        "secret", trusted_opener=trusted, unsigned_opener=unsigned
    )
    asset = ReleaseAsset(7, "single-screen.json", "https://api.github.com/assets/7")
    assert remote.download_asset(asset) == b"asset bytes"
    assert trusted_requests[0].get_header("Authorization") == "Bearer secret"
    assert unsigned_requests[0].get_header("Authorization") is None
    assert unsigned_requests[0].full_url.startswith("https://objects.example.net/")


def test_release_transport_accepts_direct_200_and_bounds_download_bytes() -> None:
    remote = GitHubReleaseRemote(
        "secret", trusted_opener=lambda request, **kwargs: Opened(200, b"direct")
    )
    asset = ReleaseAsset(7, "dual-screen.json", "https://api.github.com/assets/7")
    assert remote.download_asset(asset) == b"direct"

    oversized = GitHubReleaseRemote(
        "secret",
        trusted_opener=lambda request, **kwargs: Opened(
            200, b"x" * (MAX_ASSET_BYTES + 1)
        ),
    )
    with pytest.raises(ReleaseError, match="byte limit"):
        oversized.download_asset(asset)


def test_release_transport_uses_upload_origin_and_raw_content_once() -> None:
    requests = []

    def opener(request, *, timeout):
        requests.append(request)
        return Opened(201, b"{}")

    remote = GitHubReleaseRemote("secret", trusted_opener=opener)
    remote.upload_asset(123, "single-screen.json", b"exact bytes")
    request = requests[0]
    assert (
        request.full_url
        == "https://uploads.github.com/repos/mjkoo/omnipack/releases/123/assets?name=single-screen.json"
    )
    assert request.data == b"exact bytes"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Content-type") == "application/octet-stream"


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
