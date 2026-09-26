from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.http import HttpError, HttpResponse, HttpStatusError
from omnipack.quiver_generation import generate_quiver
from omnipack.source_catalog import _render_catalog
from tests.test_package_id import AssetTransport, apk
from tests.test_quiver_discovery import API, INDEX, LIST, FakeHttp, documents

ASSET = "https://objects.example/game.apk"
OUTPUT = ".build/source-generation/quiver"


class ScenarioHttp:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.json_http = FakeHttp(values)
        self.urls = self.json_http.urls

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse:
        value = self.values[url]
        if isinstance(value, bytes):
            self.urls.append(url)
            return AssetTransport({url: value})(
                Request(url, headers=headers or {}, method=method), 10, max_bytes
            )
        return self.json_http.get(url)


def setup(root: Path, *, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    (root / "config/catalogs").mkdir(parents=True)
    (root / "config/sources.json").write_text(
        json.dumps(
            {
                "quiver": {
                    "index_url": INDEX,
                    "catalog": "config/catalogs/quiver.json",
                    "project_policy": "config/quiver-projects.json",
                }
            }
        )
    )
    (root / "config/quiver-projects.json").write_text(
        json.dumps({"schemaVersion": 1, "projects": {}, "skips": []})
    )
    (root / "config/catalogs/quiver.json").write_bytes(_render_catalog([]))
    (root / "README.md").write_text("unchanged README")
    (root / "dist").mkdir()
    (root / "dist/single-screen.json").write_text("unchanged single")
    (root / "dist/dual-screen.json").write_text("unchanged dual")
    values = documents(
        *(
            rows
            if rows is not None
            else [{"repository": "o/repo", "project": "Port", "name": "Game"}]
        )
    )
    values[API] = {"full_name": "o/repo"}
    values[API + "/releases/latest"] = {
        "id": 1,
        "tag_name": "v1",
        "published_at": "2026-09-01T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "assets": [{"name": "game.apk", "browser_download_url": ASSET}],
    }
    values[ASSET] = apk("org.example.game")
    return values


def candidate(root: Path) -> list[dict[str, Any]]:
    return json.loads((root / OUTPUT / "catalog.json").read_bytes())["apps"]


def accept(root: Path) -> bytes:
    data = (root / OUTPUT / "catalog.json").read_bytes()
    (root / "config/catalogs/quiver.json").write_bytes(data)
    return data


def set_policy(root: Path, **kwargs: Any) -> None:
    (root / "config/quiver-projects.json").write_text(
        json.dumps({"schemaVersion": 1, "projects": {}, "skips": [], **kwargs})
    )


def test_fresh_candidate_uses_port_name_manifest_and_fresh_release_without_pins(
    tmp_path: Path,
) -> None:
    values = setup(tmp_path)
    second = ASSET + "2"
    values[second] = apk("org.example.game")
    values[API + "/releases/latest"]["assets"].append(
        {"name": "other.apk", "browser_download_url": second}
    )
    first = generate_quiver(tmp_path, http=ScenarioHttp(values))
    entry = candidate(tmp_path)[0]
    assert first["status"] == "success"
    assert (entry["id"], entry["name"], entry["url"]) == (
        "org.example.game",
        "Port",
        "https://github.com/o/repo",
    )
    assert entry["categories"] == ["Decomps/Recomps"]
    assert "objects.example" not in json.dumps(entry)
    values[ASSET] = values[second] = apk("org.example.changed")
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    assert candidate(tmp_path)[0]["id"] == "org.example.changed"


@pytest.mark.parametrize("defect", ["mixed", "unreadable"])
def test_all_selected_apks_must_agree_and_be_readable(
    tmp_path: Path, defect: str
) -> None:
    values = setup(tmp_path)
    second = ASSET + "2"
    values[second] = apk("org.other.game") if defect == "mixed" else b"broken"
    values[API + "/releases/latest"]["assets"].append(
        {"name": "other.apk", "browser_download_url": second}
    )
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert report["status"] == "failed" and report["unresolved"]
    assert not (tmp_path / OUTPUT / "catalog.json").exists()


def test_prerelease_filename_and_category_policy(tmp_path: Path) -> None:
    values = setup(tmp_path)
    release = values.pop(API + "/releases/latest")
    release["prerelease"] = True
    release["assets"].append(
        {"name": "debug.apk", "browser_download_url": "never-requested"}
    )
    values[API + "/releases?per_page=100&page=1"] = [release]
    set_policy(
        tmp_path,
        projects={
            "github.com/o/repo": {
                "name": "Reviewed",
                "category": "PC Ports",
                "additionalSettings": {
                    "includePrereleases": True,
                    "apkFilterRegEx": "^game[.]apk$",
                },
            }
        },
    )
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert report["status"] == "success"
    entry = candidate(tmp_path)[0]
    assert (entry["name"], entry["categories"]) == ("Reviewed", ["PC Ports"])
    assert json.loads(entry["additionalSettings"])["includePrereleases"] is True
    assert report["filteredAssets"][0]["names"] == ["debug.apk"]


@pytest.mark.parametrize(
    "failure", ["no-apk", "no-release", "repository-error", "release-error"]
)
def test_accepted_entry_is_retained_only_with_current_name_and_policy(
    tmp_path: Path, failure: str
) -> None:
    values = setup(tmp_path)
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    accepted = accept(tmp_path)
    if failure == "no-apk":
        values[API + "/releases/latest"]["assets"] = []
    elif failure == "no-release":
        values[API + "/releases/latest"] = HttpStatusError(
            API + "/releases/latest", 404
        )
    elif failure == "repository-error":
        values[API] = HttpError("temporary")
    else:
        values[API + "/releases/latest"] = HttpError("temporary")
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert report["status"] == "success" and report["retainedFailures"]
    assert (tmp_path / OUTPUT / "catalog.json").read_bytes() == accepted
    values[LIST]["apps"][0]["project"] = "Renamed Port"
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "failed"
    assert not (tmp_path / OUTPUT / "catalog.json").exists()
    values[LIST]["apps"][0]["project"] = "Port"
    set_policy(
        tmp_path,
        projects={
            "github.com/o/repo": {"additionalSettings": {"includePrereleases": True}}
        },
    )
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "failed"


def test_discovery_skip_retains_accepted_bytes_without_requests(tmp_path: Path) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    accepted = accept(tmp_path)
    set_policy(
        tmp_path,
        skips=[
            {"url": "github.com/o/repo", "reason": "Quiver row cannot be inspected"}
        ],
    )
    values[API] = HttpStatusError(API, 403)
    http = ScenarioHttp(values)
    report = generate_quiver(tmp_path, http=http)
    assert report["status"] == "success"
    assert report["skipped"][0]["reason"] == "Quiver row cannot be inspected"
    assert report["skipped"][0]["retained"] is True
    assert not report["apk"] and not report["retainedFailures"]
    assert http.urls == [INDEX, LIST]
    assert (tmp_path / OUTPUT / "catalog.json").read_bytes() == accepted


@pytest.mark.parametrize("status", [404, 451])
def test_unavailable_repository_skips_new_and_removes_accepted(
    tmp_path: Path, status: int
) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    accepted = accept(tmp_path)
    values[API] = HttpStatusError(API, status)
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert report["status"] == "success" and candidate(tmp_path) == []
    assert report["changes"]["removed"] == ["github.com/o/repo"]
    assert report["unavailableRepositories"]
    (tmp_path / "config/catalogs/quiver.json").write_bytes(_render_catalog([]))
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    assert accepted


def test_old_listed_url_matches_accepted_entry_after_rename(tmp_path: Path) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    accepted = accept(tmp_path)
    values[API] = {"full_name": "o/renamed"}
    newapi = "https://api.github.com/repos/o/renamed"
    values[newapi] = {"full_name": "o/renamed"}
    values[newapi + "/releases/latest"] = {
        **values[API + "/releases/latest"],
        "assets": [],
    }
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    assert (tmp_path / OUTPUT / "catalog.json").read_bytes() == accepted
    values[newapi + "/releases/latest"] = values[API + "/releases/latest"]
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    assert candidate(tmp_path)[0]["url"] == "https://github.com/o/renamed"


def test_unmatched_alias_lookup_failure_blocks_without_guessing_accepted_identity(
    tmp_path: Path,
) -> None:
    values = setup(tmp_path)
    values[API] = {"full_name": "o/renamed"}
    newapi = "https://api.github.com/repos/o/renamed"
    values[newapi] = {"full_name": "o/renamed"}
    values[newapi + "/releases/latest"] = values[API + "/releases/latest"]
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    accept(tmp_path)
    values[API] = HttpError("offline")
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert (
        report["status"] == "failed"
        and not (tmp_path / OUTPUT / "catalog.json").exists()
    )


def test_removed_row_is_removed_but_required_list_failure_never_emits_candidate(
    tmp_path: Path,
) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    accept(tmp_path)
    values[LIST]["apps"] = [{"repository": "git/lab", "repositorySource": "gitlab"}]
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["changes"][
        "removed"
    ] == ["github.com/o/repo"]
    assert candidate(tmp_path) == []
    values[LIST] = HttpError("offline")
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "failed"
    assert not (tmp_path / OUTPUT / "catalog.json").exists()


def test_new_fork_reusing_package_fails_naming_both_projects(tmp_path: Path) -> None:
    values = setup(tmp_path, rows=[{"repository": "o/repo"}, {"repository": "o/fork"}])
    fork = "https://api.github.com/repos/o/fork"
    values[fork] = {"full_name": "o/fork"}
    values[fork + "/releases/latest"] = values[API + "/releases/latest"]
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert report["status"] == "failed"
    assert (
        "github.com/o/repo" in report["error"]
        and "github.com/o/fork" in report["error"]
    )


def test_names_and_catalog_are_independent_of_row_order(tmp_path: Path) -> None:
    rows = [
        {"repository": "o/repo", "project": "port", "name": "Shared Game"},
        {"repository": "o/repo", "project": "Port"},
        {"repository": "o/other", "project": "Other Port", "name": "Shared Game"},
    ]
    values = setup(tmp_path, rows=rows)
    other = "https://api.github.com/repos/o/other"
    values[other] = {"full_name": "o/other"}
    values[other + "/releases/latest"] = {
        **values[API + "/releases/latest"],
        "assets": [{"name": "other.apk", "browser_download_url": ASSET + "2"}],
    }
    values[ASSET + "2"] = apk("org.other.game")
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    first = (tmp_path / OUTPUT / "catalog.json").read_bytes()
    assert {e["name"] for e in candidate(tmp_path)} == {"Port", "Other Port"}
    values[LIST]["apps"].reverse()
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    assert (tmp_path / OUTPUT / "catalog.json").read_bytes() == first


@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("first_fails", [False, True])
def test_duplicate_listed_rows_share_one_discovery_lookup(
    tmp_path: Path, accepted: bool, first_fails: bool
) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    if accepted:
        entries = candidate(tmp_path)
        entries[0]["url"] = "https://github.com/o/old"
        (tmp_path / "config/catalogs/quiver.json").write_bytes(_render_catalog(entries))
    values[LIST]["apps"] = [
        {"repository": "o/old", "project": "Port", "releaseAssetFilter": "one"},
        {"repository": "O/Old", "project": "Z Port", "releaseAssetFilter": "two"},
    ]
    old_api = "https://api.github.com/repos/o/old"
    calls: list[str] = []

    class FluctuatingHttp(ScenarioHttp):
        def get(self, url: str, **kwargs: Any) -> HttpResponse:
            if url == old_api:
                calls.append(url)
                fails = (len(calls) == 1) == first_fails
                self.values[url] = (
                    HttpError("temporary metadata outage")
                    if fails
                    else {"full_name": "o/repo"}
                )
            return super().get(url, **kwargs)

    report = generate_quiver(tmp_path, http=FluctuatingHttp(values))
    assert calls == [old_api]
    if first_fails and not accepted:
        assert report["status"] == "failed"
        assert len(report["unresolved"]) == 1
        assert len(report["unresolved"][0]["rows"]) == 2
    else:
        assert report["status"] == "success"
        assert len(candidate(tmp_path)) == 1
        assert candidate(tmp_path)[0]["name"] == "Port"
        if first_fails:
            assert len(report["retainedFailures"]) == 1
            assert len(report["retainedFailures"][0]["rows"]) == 2
        else:
            assert not report["retainedFailures"]
            assert report["filterDisagreements"] == ["github.com/o/repo"]
            assert len(report["coverage"][0]["rows"]) == 2


def test_invalid_github_owner_is_an_unsupported_row(tmp_path: Path) -> None:
    values = setup(tmp_path, rows=[{"repository": "bad_owner/repo"}])
    http = ScenarioHttp(values)
    report = generate_quiver(tmp_path, http=http)
    assert report["status"] == "success"
    assert len(report["unsupportedRows"]) == 1
    assert candidate(tmp_path) == []
    assert http.urls == [INDEX, LIST]


@pytest.mark.parametrize(
    "defect",
    ["duplicate-id", "duplicate-project", "bad-id", "track-only", "policy-field"],
)
def test_invalid_accepted_catalog_fails_before_requests(
    tmp_path: Path, defect: str
) -> None:
    values = setup(tmp_path)
    generate_quiver(tmp_path, http=ScenarioHttp(values))
    entries = candidate(tmp_path)
    if defect == "duplicate-id":
        entries.append({**entries[0], "url": "https://github.com/o/other"})
    elif defect == "duplicate-project":
        entries.append({**entries[0], "id": "org.other.game"})
    elif defect == "bad-id":
        entries[0]["id"] = "123"
    elif defect == "track-only":
        entries[0]["additionalSettings"] = '{"trackOnly":true}'
    else:
        entries[0]["family"] = "app:forbidden"
    (tmp_path / "config/catalogs/quiver.json").write_text(json.dumps({"apps": entries}))
    http = ScenarioHttp(values)
    assert generate_quiver(tmp_path, http=http)["status"] == "failed"
    assert not http.urls


def test_cli_success_and_failed_rerun_preserve_committed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    values = setup(tmp_path)
    http = ScenarioHttp(values)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "omnipack.quiver_generation.SourceHttpClient", lambda config: http
    )
    (tmp_path / "config/http.json").write_text('{"credentials":{}}')
    tracked = [p for p in tmp_path.rglob("*") if p.is_file()]
    before = {p: p.read_bytes() for p in tracked}
    assert cli.main(["generate-source", "quiver"]) == 0
    values[LIST] = HttpError("required list unavailable")
    assert cli.main(["generate-source", "quiver"]) == 1
    assert "required list unavailable" in capsys.readouterr().err
    assert not (tmp_path / OUTPUT / "catalog.json").exists()
    assert before == {p: p.read_bytes() for p in tracked}


@pytest.mark.parametrize("outcome", ["no-apk", "no-release", "rate-limit"])
def test_new_project_absence_is_a_skip_but_failed_lookup_blocks(
    tmp_path: Path, outcome: str
) -> None:
    values = setup(tmp_path)
    if outcome == "no-apk":
        values[API + "/releases/latest"]["assets"] = []
    else:
        values[API + "/releases/latest"] = HttpStatusError(
            API + "/releases/latest", 404 if outcome == "no-release" else 429
        )
    report = generate_quiver(tmp_path, http=ScenarioHttp(values))
    if outcome == "rate-limit":
        assert report["status"] == "failed" and report["unresolved"]
        assert not (tmp_path / OUTPUT / "catalog.json").exists()
    else:
        assert report["status"] == "success" and report["noAndroid"]
        assert candidate(tmp_path) == []


def test_invalid_policy_makes_no_requests_and_fallback_name_is_repository(
    tmp_path: Path,
) -> None:
    values = setup(
        tmp_path, rows=[{"repository": "o/repo", "name": "Not the port name"}]
    )
    assert generate_quiver(tmp_path, http=ScenarioHttp(values))["status"] == "success"
    assert candidate(tmp_path)[0]["name"] == "repo"
    set_policy(
        tmp_path,
        projects={"github.com/o/repo": {"additionalSettings": {"apkFilterRegEx": "["}}},
    )
    http = ScenarioHttp(values)
    assert generate_quiver(tmp_path, http=http)["status"] == "failed"
    assert not http.urls
