from __future__ import annotations

import json
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import Any
from urllib.request import Request
from urllib.response import addinfourl

import pytest

from omnipack.http import HttpError, HttpResponse, HttpStatusError
from omnipack.model import Category
from omnipack.package_id import NoEligibleApk
from omnipack.project_policy import default_apk_rule
from omnipack.quiver_source import (
    QuiverPolicy,
    QuiverRule,
    discover_quiver,
    load_quiver_config,
    parse_quiver_policy,
    resolve_quiver_apk,
)
from omnipack.source_http import HttpConfig, SourceHttpClient
from omnipack.source_release import NoRelease, lookup_release
from tests.test_package_id import AssetTransport, malformed_manifest, release

INDEX = "https://raw.githubusercontent.com/o/catalog/main/index.json"
LIST = "https://raw.githubusercontent.com/o/catalog/main/lists/one.json"
API = "https://api.github.com/repos/o/repo"


class FakeHttp:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: object) -> HttpResponse:
        self.urls.append(url)
        value = self.values[url]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, HttpResponse):
            return value
        return HttpResponse(url, 200, Message(), json.dumps(value).encode())


def documents(*rows: object, list_url: str = LIST) -> dict[str, Any]:
    return {
        INDEX: {"version": 2, "lists": [{"id": "one", "remoteLocation": list_url}]},
        LIST: {"name": "One", "version": "1", "apps": list(rows)},
    }


def policy(**kwargs: object) -> QuiverPolicy:
    return parse_quiver_policy({"schemaVersion": 1, "projects": {}, **kwargs})


def test_policy_defaults_and_rejects_invalid_rules_before_requests() -> None:
    parsed = policy()
    assert parsed.rule_for("github.com/o/repo") == QuiverRule(default_apk_rule())
    assert parsed.rule_for("github.com/o/repo").category is Category.DECOMPS
    for invalid in (
        {"projects": {"github.com/o/repo": {"kind": "apk"}}},
        {"projects": {"github.com/o/repo": {"category": "Emulators"}}},
        {"projects": {"github.com/o/repo": {"name": " "}}},
        {
            "projects": {
                "github.com/o/repo": {"additionalSettings": {"apkFilterRegEx": "["}}
            }
        },
        {"skips": [{"url": "github.com/o/repo", "reason": " "}]},
        {"skips": [{"repository": "a/b", "reason": "x"}]},
    ):
        with pytest.raises(ValueError):
            parse_quiver_policy({"schemaVersion": 1, "projects": {}, **invalid})
    for category in ("Emulator", "Track Only"):
        with pytest.raises(ValueError, match="category must be one of"):
            policy(projects={"github.com/o/repo": {"category": category}})


def test_discovery_collapses_renames_preserves_provenance_and_filter_diagnostic() -> (
    None
):
    values = documents(
        {"repository": "O/Old", "project": "Port B", "releaseAssetFilter": "a"},
        {"repository": "O/Repo", "project": "Port A", "releaseAssetFilter": "b"},
        {"repository": "O/Other", "repositorySource": "GitHub"},
        {"repository": "x/y", "repositorySource": "gitlab"},
        {"repository": "not-a-pair"},
    )
    values["https://api.github.com/repos/o/old"] = {"full_name": "O/Repo"}
    values[API] = {"full_name": "O/Repo"}
    values["https://api.github.com/repos/o/other"] = {"full_name": "O/Other"}
    http = FakeHttp(values)
    result = discover_quiver(INDEX, policy(), http)
    assert len(result.projects) == 2
    merged = next(p for p in result.projects if p.key == "github.com/o/repo")
    assert {r.listed for r in merged.rows} == {"github.com/o/old", "github.com/o/repo"}
    assert merged.name == "Port A"
    assert merged.url == "https://github.com/O/Repo"
    assert result.filter_disagreements
    assert len(result.unsupported) == 2
    assert "https://api.github.com/repos/x/y" not in http.urls


@pytest.mark.parametrize(
    "outside",
    [
        "https://raw.githubusercontent.com/o/other/main/list.json",
        "https://raw.githubusercontent.com:bad/o/catalog/main/platform.json",
        "https://[broken/platform.json",
    ],
    ids=["outside-root", "nonnumeric-port", "malformed-authority"],
)
def test_out_of_scope_list_fails_before_fetch(outside: str) -> None:
    http = FakeHttp(documents({"repository": "O/Repo"}, list_url=outside))
    with pytest.raises(ValueError):
        discover_quiver(INDEX, policy(), http)
    assert http.urls == [INDEX]


def test_platform_metadata_is_never_read() -> None:
    values = documents({"repository": "O/Repo"})
    values[INDEX]["platformMetadataUrl"] = LIST.replace("lists/one", "platform")
    values[API] = {"full_name": "O/Repo"}
    http = FakeHttp(values)
    result = discover_quiver(INDEX, policy(), http)
    assert len(result.projects) == 1
    assert http.urls == [INDEX, LIST, API]


def test_redirected_list_outside_catalog_is_rejected() -> None:
    values = documents({"repository": "O/Repo"})
    values[LIST] = HttpResponse(
        "https://elsewhere.test/list.json", 200, Message(), b"{}"
    )
    with pytest.raises(ValueError, match="catalog"):
        discover_quiver(INDEX, policy(), FakeHttp(values))


def test_catalog_redirect_is_stopped_before_destination_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        seen.append(request.full_url)
        headers = Message()
        headers["Location"] = "https://elsewhere.test/list.json"
        return FixtureResponse(BytesIO(b""), headers, request.full_url, 302)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    client = SourceHttpClient(HttpConfig({}), retries=0)
    with pytest.raises(ValueError, match="redirect"):
        client.get(
            LIST,
            allowed_url=lambda url: url.startswith(
                "https://raw.githubusercontent.com/o/catalog/main/"
            ),
        )
    assert seen == [LIST]


def test_literal_and_listed_skips_make_no_repository_request() -> None:
    values = documents(
        {"repository": "O/Repo"},
        {"repository": "x/y", "repositorySource": "gitlab"},
    )
    parsed = policy(
        skips=[
            {"url": "github.com/o/repo", "reason": "blocked upstream"},
            {
                "repository": "x/y",
                "repositorySource": "gitlab",
                "reason": "unsupported",
            },
        ]
    )
    http = FakeHttp(values)
    result = discover_quiver(INDEX, parsed, http)
    assert len(result.skipped) == 2
    assert http.urls == [INDEX, LIST]


def test_missing_and_empty_discovery_fail() -> None:
    for value in ({"version": 2, "lists": []}, {"version": 2, "lists": [{"id": "x"}]}):
        with pytest.raises(ValueError):
            discover_quiver(INDEX, policy(), FakeHttp({INDEX: value}))
    with pytest.raises(ValueError, match="empty"):
        discover_quiver(INDEX, policy(), FakeHttp(documents()))
    unsupported = discover_quiver(
        INDEX,
        policy(),
        FakeHttp(documents({"repository": "x/y", "repositorySource": "gitlab"})),
    )
    assert len(unsupported.unsupported) == 1
    assert not unsupported.projects


def test_required_list_404_fails_complete_discovery() -> None:
    missing = LIST.replace("one.json", "missing.json")
    values = documents({"repository": "O/Repo"})
    values[INDEX]["lists"].append({"id": "missing", "remoteLocation": missing})
    values[missing] = HttpStatusError(missing, 404)
    http = FakeHttp(values)

    with pytest.raises(HttpStatusError) as caught:
        discover_quiver(INDEX, policy(), http)

    assert caught.value.status == 404
    assert http.urls == [INDEX, LIST, missing]


def test_repository_lookup_failure_is_available_for_accepted_entry_retention() -> None:
    values = documents({"repository": "O/Repo", "project": "Port"})
    values[API] = HttpStatusError(API, 403)
    result = discover_quiver(INDEX, policy(), FakeHttp(values))
    assert not result.projects
    assert len(result.lookup_failures) == 1
    failure = result.lookup_failures[0]
    assert failure.row.listed == "github.com/o/repo"
    assert failure.row.project_name == "Port"
    assert failure.rule.project.additional_settings == {}
    assert isinstance(failure.error, HttpStatusError)


@pytest.mark.parametrize("status", [404, 451])
def test_conclusive_repository_absence_is_unavailable_not_a_project(
    status: int,
) -> None:
    values = documents(
        {"repository": "O/Repo", "project": "Port"}, {"repository": "o/repo"}
    )
    values[API] = HttpStatusError(API, status)
    http = FakeHttp(values)
    result = discover_quiver(INDEX, policy(), http)
    assert not result.projects and not result.lookup_failures
    assert len(result.unavailable) == 1
    unavailable = result.unavailable[0]
    assert (unavailable.url, unavailable.error.status) == ("github.com/o/repo", status)
    assert len(unavailable.rows) == 2
    assert http.urls == [INDEX, LIST, API]


def test_duplicate_policy_json_keys_fail() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_quiver_policy(b'{"schemaVersion":1,"projects":{},"projects":{}}')


def test_release_outcomes_distinguish_absence_from_failure() -> None:
    rule = policy().rule_for("github.com/o/repo")
    latest = API + "/releases/latest"
    http = FakeHttp({latest: HttpStatusError(latest, 404)})
    with pytest.raises(NoRelease):
        lookup_release(http, "github.com/o/repo", rule.project)
    assert http.urls == [latest]
    with pytest.raises(HttpError):
        lookup_release(
            FakeHttp({latest: HttpStatusError(latest, 403)}),
            "github.com/o/repo",
            rule.project,
        )


@pytest.mark.parametrize("status", [None, 401, 403, 429])
@pytest.mark.parametrize("include_prereleases", [False, True])
def test_release_request_failures_do_not_become_no_release(
    status: int | None, include_prereleases: bool
) -> None:
    endpoint = API + (
        "/releases?per_page=100&page=1" if include_prereleases else "/releases/latest"
    )
    requests: list[str] = []

    def transport(
        request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        requests.append(request.full_url)
        assert request.full_url == endpoint
        if status is None:
            raise OSError("connection interrupted")
        raise urllib.error.HTTPError(
            endpoint, status, "request failed", Message(), None
        )

    rule = policy(
        projects={
            "github.com/o/repo": {
                "additionalSettings": {"includePrereleases": include_prereleases}
            }
        }
    ).rule_for("github.com/o/repo")
    http = SourceHttpClient(HttpConfig({}), transport=transport, retries=0)
    with pytest.raises(HttpError):
        lookup_release(http, "github.com/o/repo", rule.project)
    assert requests == [endpoint]


def test_no_eligible_apk_is_typed() -> None:
    release = {"assets": [{"name": "desktop.zip"}]}
    with pytest.raises(NoEligibleApk):
        resolve_quiver_apk(
            FakeHttp({}),
            release,
            policy().rule_for("github.com/o/repo"),
            [],
            "github.com/o/repo",
        )


@pytest.mark.parametrize(
    "body",
    [b"PK\x05\x06", malformed_manifest("utf8")],
    ids=["truncated-zip", "malformed-manifest"],
)
def test_unreadable_selected_apk_is_an_error_not_no_eligible_apk(body: bytes) -> None:
    asset = "https://objects.example/app.apk"
    transport = AssetTransport({asset: body})
    http = SourceHttpClient(HttpConfig({}), transport=transport, retries=0)

    with pytest.raises(ValueError, match="cannot read eligible APK") as caught:
        resolve_quiver_apk(
            http,
            release([("app.apk", asset)]),
            policy().rule_for("github.com/o/repo"),
            [],
            "github.com/o/repo",
        )

    assert not isinstance(caught.value, NoEligibleApk)
    assert any(request.method == "GET" for request, _ in transport.requests)


def test_apk_transport_failure_is_an_error_not_no_eligible_apk() -> None:
    asset = "https://objects.example/app.apk"
    transport = AssetTransport({asset: OSError("connection interrupted")})
    http = SourceHttpClient(HttpConfig({}), transport=transport, retries=0)

    with pytest.raises(ValueError, match="cannot read eligible APK") as caught:
        resolve_quiver_apk(
            http,
            release([("app.apk", asset)]),
            policy().rule_for("github.com/o/repo"),
            [],
            "github.com/o/repo",
        )

    assert not isinstance(caught.value, NoEligibleApk)
    assert isinstance(caught.value.__cause__, HttpError)
    assert [request.method for request, _ in transport.requests] == ["HEAD", "GET"]


def test_catalog_scope_rejects_parent_path_and_encoded_traversal() -> None:
    for location in (
        "https://raw.githubusercontent.com/o/catalog/main/../elsewhere.json",
        "https://raw.githubusercontent.com/o/catalog/main/%2e%2e/elsewhere.json",
    ):
        values = documents({"repository": "O/Repo"}, list_url=location)
        with pytest.raises(ValueError, match="index"):
            discover_quiver(INDEX, policy(), FakeHttp(values))


def test_source_config_validates_before_requests() -> None:
    config = load_quiver_config(
        {
            "index_url": INDEX,
            "catalog": "config/catalogs/quiver.json",
            "project_policy": "config/quiver-projects.json",
        }
    )
    assert config.index_url == INDEX
    with pytest.raises(ValueError):
        load_quiver_config(
            {
                "index_url": "http://example.test/index.json",
                "catalog": "x",
                "project_policy": "y",
            }
        )
