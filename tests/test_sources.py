from __future__ import annotations

import json
import shutil
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request

import pytest

from obtainium_pack import cli
from obtainium_pack.http import HttpClient, HttpError, HttpResponse
from obtainium_pack.model import App, Provenance, SourceType, Variant
from obtainium_pack.package_id import ResolutionResult, ResolutionStatus
from obtainium_pack.sources import (
    IngestionReport,
    SourceError,
    bboi,
    codm,
    extras,
    rjny,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttp:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> HttpResponse:
        self.urls.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        body = value if isinstance(value, bytes) else value.encode()
        return HttpResponse(url, 200, Message(), body)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_rjny_applies_export_flags_and_ignores_presentation_overrides() -> None:
    url = "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    apps = rjny.fetch(
        FakeHttp({url: fixture("rjny-applications.json")}),
        {
            "repo": "RJNY/Obtainium-Emulation-Pack",
            "branch": "main",
            "path": "src/applications.json",
        },
    )
    cemu = [app for app in apps if app.id == "info.cemu.cemu"]
    assert {(app.variant, app.url) for app in cemu} == {
        (Variant.SINGLE, "https://github.com/SSimco/Cemu"),
        (Variant.DUAL, "https://github.com/sapphirerhodonite/cemu"),
    }
    assert all(app.name == "Citra" for app in apps if app.id == "org.citra.emu")
    assert not any("Dev build" in app.name for app in apps)
    assert all(isinstance(app.additional_settings, dict) for app in apps)


def test_rjny_matches_both_upstream_exports() -> None:
    catalog_url = "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    apps = rjny.fetch(
        FakeHttp({catalog_url: fixture("rjny-applications.json")}),
        {
            "repo": "RJNY/Obtainium-Emulation-Pack",
            "branch": "main",
            "path": "src/applications.json",
        },
    )
    for variant, export_name, count in (
        (Variant.SINGLE, "rjny-single.json", 62),
        (Variant.DUAL, "rjny-dual.json", 66),
    ):
        expected = json.loads(fixture(export_name))["apps"]
        assert len(expected) == count
        assert len([app for app in apps if app.variant is variant]) == count
        assert {(app.id, app.url) for app in apps if app.variant is variant} == {
            (entry["id"], entry["url"]) for entry in expected
        }


def test_rjny_rejects_empty_location_and_unsupported_source() -> None:
    with pytest.raises(SourceError, match="rjny"):
        rjny.fetch(FakeHttp({}), {"repo": "", "branch": "main", "path": "x"})
    record = json.loads(fixture("rjny-applications.json"))
    record["apps"][0]["overrideSource"] = "F-Droid Third Party Repo"
    url = "https://raw.githubusercontent.com/r/main/p"
    with pytest.raises(SourceError, match="rjny.*F-Droid Third Party Repo"):
        rjny.fetch(
            FakeHttp({url: json.dumps(record)}),
            {"repo": "r", "branch": "main", "path": "p"},
        )


@pytest.mark.parametrize("response", [HttpError("offline"), "not json"])
def test_rjny_fetch_and_parse_failures_name_source(response: object) -> None:
    url = "https://raw.githubusercontent.com/r/main/p"
    with pytest.raises(SourceError, match="rjny"):
        rjny.fetch(
            FakeHttp({url: response}), {"repo": "r", "branch": "main", "path": "p"}
        )


def test_bboi_latest_release_maps_assets_and_dual_overrides_same_id() -> None:
    api = "https://codeberg.org/api/v1/repos/BBoi34/Obtainium-Recomp-Decomp/releases/latest"
    single_url, dual_url = "https://assets/single.json", "https://assets/dual.json"
    release = {
        "assets": [
            {"name": "Decomp-Recomp.V9.json", "browser_download_url": single_url},
            {
                "name": "Dual-Screen-Decomp-Recomp.V9.json",
                "browser_download_url": dual_url,
            },
        ]
    }
    apps = bboi.fetch(
        FakeHttp(
            {
                api: json.dumps(release),
                single_url: fixture("bboi-single.json"),
                dual_url: fixture("bboi-dual.json"),
            }
        ),
        {
            "codeberg_repo": "BBoi34/Obtainium-Recomp-Decomp",
            "single_asset_pattern": "Decomp-Recomp.V*.json",
            "dual_asset_pattern": "Dual-Screen-Decomp-Recomp.V*.json",
        },
    )
    dual_ids = [app.id for app in apps if app.variant is Variant.DUAL]
    assert len(dual_ids) == len(set(dual_ids))
    overlapping_ids = {
        "com.aure.banjorecomp",
        "com.igawa6.harvestmoon64",
        "com.samyost1.zelda3android",
        "com.samyost1.tmcandroid",
    }
    for variant, asset in (
        (Variant.SINGLE, "bboi-single.json"),
        (Variant.DUAL, "bboi-dual.json"),
    ):
        expected = {entry["id"]: entry for entry in json.loads(fixture(asset))["apps"]}
        actual = {app.id: app for app in apps if app.variant is variant}
        assert set(actual) == set(expected) == overlapping_ids
        for app_id in overlapping_ids:
            entry, app = expected[app_id], actual[app_id]
            assert app.name == entry["name"]
            assert app.url == entry["url"]
            assert app.categories == tuple(entry["categories"])
            assert app.source_type is SourceType(entry["overrideSource"])
            assert app.additional_settings == json.loads(entry["additionalSettings"])


def test_bboi_rejects_malformed_settings() -> None:
    document = json.loads(fixture("bboi-single.json"))
    document["apps"][0]["additionalSettings"] = "not json"
    api, asset = (
        "https://codeberg.org/api/v1/repos/a/b/releases/latest",
        "https://asset/s.json",
    )
    release = {
        "assets": [
            {"name": "single.json", "browser_download_url": asset},
            {"name": "dual.json", "browser_download_url": asset},
        ]
    }
    with pytest.raises(SourceError, match="bboi"):
        bboi.fetch(
            FakeHttp({api: json.dumps(release), asset: json.dumps(document)}),
            {
                "codeberg_repo": "a/b",
                "single_asset_pattern": "single.json",
                "dual_asset_pattern": "dual.json",
            },
        )


class StubResolver:
    def resolve(self, url: str) -> ResolutionResult:
        repo = url.rstrip("/").split("/")[-1]
        return ResolutionResult(f"app.{repo.lower()}", ResolutionStatus.RESOLVED, 1)


class ResultResolver:
    def __init__(self, result: ResolutionResult) -> None:
        self.result = result

    def resolve(self, project_url: str) -> ResolutionResult:
        return self.result


def test_codm_extracts_all_github_links_skips_other_hosts_and_deduplicates_dual() -> (
    None
):
    readme_url = "https://example/readme"
    report = IngestionReport()
    higher = [
        App(
            "x",
            "https://www.github.com/SAMYOST1/ZELDA3-ANDROID.git/",
            "x",
            SourceType.GITHUB,
            (),
            Variant.DUAL,
            Provenance("x", "x"),
        ),
        App(
            "y",
            "http://github.com/igawa6/DUSKLIGHT",
            "y",
            SourceType.GITHUB,
            (),
            Variant.DUAL,
            Provenance("x", "x"),
        ),
        App(
            "z",
            "https://github.com/Josh-Daniels/OpenMW-DS",
            "z",
            SourceType.GITHUB,
            (),
            Variant.SINGLE,
            Provenance("x", "x"),
        ),
    ]
    apps = codm.fetch(
        FakeHttp({readme_url: fixture("codm-readme.md")}),
        {"readme_url": readme_url},
        StubResolver(),
        higher,
        report,
    )
    urls = {app.url for app in apps}
    assert "https://github.com/samyost1/zelda3-android" not in urls
    assert "https://github.com/igawa6/dusklight" not in urls
    assert "https://github.com/Josh-Daniels/OpenMW-DS" in urls
    assert "https://github.com/cylonid/NativeAlphaForAndroid" in urls
    assert all(app.variant is Variant.DUAL and not app.categories for app in apps)
    assert all(app.source_type is SourceType.GITHUB for app in apps)
    assert (
        next(app for app in apps if app.url.endswith("OpenMW-DS")).name == "OpenMW-DS"
    )
    assert any(
        item["url"].startswith("https://www.nexusmods.com") for item in report.skipped
    )
    assert len(urls) == 22  # 24 GitHub repositories minus two dual-covered links


def test_codm_reports_unresolved_and_cached_resolution_failures() -> None:
    readme_url = "https://example/readme"
    readme = "[Project](https://github.com/owner/repo)"
    unresolved_report = IngestionReport()
    apps = codm.fetch(
        FakeHttp({readme_url: readme}),
        {"readme_url": readme_url},
        ResultResolver(
            ResolutionResult(None, ResolutionStatus.UNRESOLVED, 2, "no APK")
        ),
        [],
        unresolved_report,
    )
    assert apps == []
    assert unresolved_report.unresolved == [
        {
            "source": "codm2000",
            "url": "https://github.com/owner/repo",
            "failure": "no APK",
        }
    ]

    retained_report = IngestionReport()
    apps = codm.fetch(
        FakeHttp({readme_url: readme}),
        {"readme_url": readme_url},
        ResultResolver(
            ResolutionResult(
                "app.cached", ResolutionStatus.REUSED, 1, "release unavailable"
            )
        ),
        [],
        retained_report,
    )
    assert [app.id for app in apps] == ["app.cached"]
    assert retained_report.generated[0]["status"] == "reused"
    assert retained_report.retained_failures[0]["failure"] == "release unavailable"


@pytest.mark.parametrize("missing", ["id", "url", "name"])
def test_extras_requires_named_fields(missing: str) -> None:
    entry = {"id": "app.id", "url": "https://example.test/app", "name": "Example"}
    del entry[missing]
    with pytest.raises(SourceError, match="extras.*(Example|app.id|entry 1)"):
        extras.fetch([entry])


def test_extras_defaults_variants_derives_source_and_validates_subset() -> None:
    apps = extras.fetch(
        [
            {"id": "a", "url": "https://github.com/o/r", "name": "GitHub"},
            {
                "id": "b",
                "url": "https://elsewhere/app",
                "name": "HTML",
                "variants": ["single"],
            },
        ]
    )
    assert {(app.id, app.variant, app.source_type) for app in apps} == {
        ("a", Variant.SINGLE, SourceType.GITHUB),
        ("a", Variant.DUAL, SourceType.GITHUB),
        ("b", Variant.SINGLE, SourceType.HTML),
    }
    with pytest.raises(SourceError, match="extras.*Bad.*wide"):
        extras.fetch(
            [{"id": "c", "url": "https://x", "name": "Bad", "variants": ["wide"]}]
        )


def test_settings_json_string_must_decode_to_object() -> None:
    with pytest.raises(SourceError, match="extras.*Settings"):
        extras.fetch(
            [
                {
                    "id": "x",
                    "url": "https://x",
                    "name": "Settings",
                    "additionalSettings": "[]",
                }
            ]
        )


@pytest.mark.parametrize("failure", ["unreachable", "malformed"])
def test_build_ingestion_failure_leaves_existing_outputs_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    single, dual = dist / "single-screen.json", dist / "dual-screen.json"
    single.write_text("old single", encoding="utf-8")
    dual.write_text("old dual", encoding="utf-8")
    shutil.copytree(Path(__file__).parents[1] / "config", tmp_path / "config")
    before = {path.name: path.read_bytes() for path in dist.iterdir()}
    monkeypatch.chdir(tmp_path)
    requests: list[str] = []

    def transport(
        _client: HttpClient, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        requests.append(request.full_url)
        if failure == "unreachable":
            raise URLError("source unreachable")
        return HttpResponse(request.full_url, 200, Message(), b"not json")

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    with pytest.raises(SourceError, match="rjny"):
        cli.main(["build"])
    assert requests and set(requests) == {
        "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    }
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before
    assert single.read_text(encoding="utf-8") == "old single"
    assert dual.read_text(encoding="utf-8") == "old dual"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com", SourceType.HTML),
        ("https://github.com/owner", SourceType.HTML),
        ("https://github.com/topics/android", SourceType.HTML),
        ("https://github.com/orgs/example/repositories", SourceType.HTML),
        ("https://github.com/settings/profile", SourceType.HTML),
        ("https://github.com/features/actions", SourceType.HTML),
        ("https://github.com/owner/repo", SourceType.GITHUB),
        ("https://www.github.com/owner/repo/releases/latest", SourceType.GITHUB),
        ("https://github.com/owner/repo/tree/main", SourceType.GITHUB),
    ],
)
def test_extras_derives_github_only_for_repository_urls(
    url: str, expected: SourceType
) -> None:
    apps = extras.fetch([{"id": "app.test", "url": url, "name": "Example"}])
    assert {app.source_type for app in apps} == {expected}


@pytest.mark.parametrize("declared", [SourceType.GITHUB, SourceType.HTML])
def test_upstream_declared_source_type_is_preserved(declared: SourceType) -> None:
    url = "https://raw.githubusercontent.com/r/main/p"
    record = {
        "id": "app.test",
        "name": "Example",
        "url": "https://github.com/owner/repo",
        "overrideSource": declared.value,
    }
    apps = rjny.fetch(
        FakeHttp({url: json.dumps({"apps": [record]})}),
        {"repo": "r", "branch": "main", "path": "p"},
    )
    assert len(apps) == 2
    assert all(app.source_type is declared for app in apps)
