from __future__ import annotations

import json
from email.message import Message
from typing import Any
from urllib.request import Request

import pytest

from omnipack.http import HttpError, HttpResponse
from omnipack.quiver_source import (
    NoApk,
    NoRelease,
    QuiverPolicy,
    RepositoryUnavailable,
    discover_quiver,
    load_quiver_config,
    lookup_quiver_release,
    parse_quiver_policy,
    resolve_quiver_apk,
)
from omnipack.source_http import HttpConfig, SourceHttpClient

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
    assert parsed.rule_for("github.com/o/repo").additional_settings == {}
    for invalid in (
        {"projects": {"github.com/o/repo": {"kind": "track-only"}}},
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
    merged = next(p for p in result.projects if p.canonical == "github.com/o/repo")
    assert {r.listed for r in merged.rows} == {"github.com/o/old", "github.com/o/repo"}
    assert merged.name == "Port A"
    assert result.filter_disagreements
    assert len(result.unsupported) == 2
    assert "https://api.github.com/repos/x/y" not in http.urls


def test_out_of_scope_list_fails_before_fetch_and_metadata_is_advisory() -> None:
    outside = "https://raw.githubusercontent.com/o/other/main/list.json"
    http = FakeHttp(documents({"repository": "O/Repo"}, list_url=outside))
    with pytest.raises(ValueError, match="index"):
        discover_quiver(INDEX, policy(), http)
    assert http.urls == [INDEX]
    values = documents({"repository": "O/Repo"})
    values[INDEX]["platformMetadataUrl"] = outside
    values[API] = {"full_name": "O/Repo"}
    result = discover_quiver(INDEX, policy(), FakeHttp(values))
    assert len(result.projects) == 1
    assert result.metadata_diagnostic


def test_redirected_list_outside_catalog_is_rejected() -> None:
    values = documents({"repository": "O/Repo"})
    values[LIST] = HttpResponse(
        "https://elsewhere.test/list.json", 200, Message(), b"{}"
    )
    with pytest.raises(ValueError, match="catalog"):
        discover_quiver(INDEX, policy(), FakeHttp(values))


def test_catalog_redirect_is_stopped_before_destination_request() -> None:
    seen: list[str] = []
    client: SourceHttpClient

    def transport(
        request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        seen.append(request.full_url)
        client.redirect_request(request, "https://elsewhere.test/list.json")
        raise AssertionError("redirect should have been refused")

    client = SourceHttpClient(HttpConfig({}), transport=transport, retries=0)
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


def test_repository_lookup_failure_is_available_for_accepted_entry_retention() -> None:
    from omnipack.http import HttpStatusError

    values = documents({"repository": "O/Repo", "project": "Port"})
    values[API] = HttpStatusError(API, 403)
    result = discover_quiver(INDEX, policy(), FakeHttp(values))
    assert not result.projects
    assert len(result.lookup_failures) == 1
    failure = result.lookup_failures[0]
    assert failure.row.listed == "github.com/o/repo"
    assert failure.row.project_name == "Port"
    assert failure.rule.additional_settings == {}
    assert isinstance(failure.error, HttpStatusError)


def test_duplicate_policy_json_keys_fail() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_quiver_policy(b'{"schemaVersion":1,"projects":{},"projects":{}}')


def test_release_outcomes_distinguish_absence_from_failure() -> None:
    from omnipack.http import HttpStatusError

    rule = policy().rule_for("github.com/o/repo")
    metadata = {API: {"full_name": "O/Repo"}}
    latest = API + "/releases/latest"
    with pytest.raises(RepositoryUnavailable):
        lookup_quiver_release(
            FakeHttp({API: HttpStatusError(API, 404)}), "github.com/o/repo", rule
        )
    with pytest.raises(NoRelease):
        lookup_quiver_release(
            FakeHttp({**metadata, latest: HttpStatusError(latest, 404)}),
            "github.com/o/repo",
            rule,
        )
    with pytest.raises(RepositoryUnavailable) as unavailable:
        lookup_quiver_release(
            FakeHttp({API: HttpStatusError(API, 451)}), "github.com/o/repo", rule
        )
    assert unavailable.value.status == 451
    with pytest.raises(HttpError):
        lookup_quiver_release(
            FakeHttp({API: HttpStatusError(API, 403)}), "github.com/o/repo", rule
        )


def test_no_apk_is_typed_but_unreadable_apk_remains_an_error() -> None:
    release = {"assets": [{"name": "desktop.zip"}]}
    with pytest.raises(NoApk):
        resolve_quiver_apk(
            FakeHttp({}),
            release,
            policy().rule_for("github.com/o/repo"),
            {},
            "github.com/o/repo",
        )


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
