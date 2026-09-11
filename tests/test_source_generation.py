from __future__ import annotations

import json
from email.message import Message
from pathlib import Path

import pytest

from omnipack.http import HttpResponse
from omnipack.project_policy import PolicyError, parse_project_policy
from omnipack.source_generation import (
    generate_codm,
    parse_project_table,
    select_release,
)


def test_project_parser_ignores_links_outside_project_tables() -> None:
    readme = b"""# links\nhttps://github.com/outside/repo\n\n| Project | Notes |\n| --- | --- |\n| [One](https://github.com/Owner/Repo.git/) | yes |\n| [same](http://www.github.com/owner/repo) | duplicate |\n| [unsupported](https://example.test/tool) | skipped |\n"""
    parsed = parse_project_table(readme)
    assert parsed.projects == ("github.com/owner/repo",)
    assert parsed.unsupported == ("https://example.test/tool",)


@pytest.mark.parametrize(
    "document",
    [
        {"schemaVersion": 2, "projects": {}},
        {"schemaVersion": 1, "projects": []},
        {"schemaVersion": 1, "projects": {"github.com/a/b": {"kind": "other"}}},
        {
            "schemaVersion": 1,
            "projects": {"github.com/a/b": {"kind": "apk", "trackerId": "123"}},
        },
        {
            "schemaVersion": 1,
            "projects": {
                "github.com/a/b": {
                    "kind": "track-only",
                    "trackerId": "abc",
                    "rationale": "r",
                    "installation": "i",
                }
            },
        },
        {
            "schemaVersion": 1,
            "projects": {
                "github.com/a/b": {
                    "kind": "apk",
                    "additionalSettings": {"apkFilterRegEx": "(?<=app)\\.apk$"},
                }
            },
        },
        {
            "schemaVersion": 1,
            "projects": {
                "github.com/a/b": {
                    "kind": "apk",
                    "additionalSettings": {"apkFilterRegEx": "["},
                }
            },
        },
    ],
)
def test_policy_rejects_invalid_documents(document: object) -> None:
    with pytest.raises(PolicyError):
        parse_project_policy(json.dumps(document).encode())


def test_policy_normalizes_keys_and_has_format_independent_fingerprint() -> None:
    first = parse_project_policy(
        b'{"schemaVersion":1,"projects":{"https://www.github.com/A/B.git/":{"kind":"apk","name":"B","additionalSettings":{"includePrereleases":true}}}}'
    )
    second = parse_project_policy(
        b'{ "projects": { "github.com/a/b": { "additionalSettings": { "includePrereleases": true }, "name": "B", "kind": "apk" } }, "schemaVersion": 1 }'
    )
    assert (
        first.projects["github.com/a/b"].fingerprint
        == second.projects["github.com/a/b"].fingerprint
    )


def test_empty_or_malformed_project_table_fails() -> None:
    with pytest.raises(ValueError, match="Project catalog table"):
        parse_project_table(b"[outside](https://github.com/a/b)")
    with pytest.raises(ValueError, match="no eligible"):
        parse_project_table(b"| Project | Note |\n| --- | --- |\n| text | none |\n")


class JsonHttp:
    def __init__(self, value: object) -> None:
        self.value = value
        self.urls: list[str] = []

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse:
        self.urls.append(url)
        return HttpResponse(url, 200, Message(), json.dumps(self.value).encode())


def test_release_list_excludes_drafts_and_selects_newest_matching_title() -> None:
    rule = parse_project_policy(
        b'{"schemaVersion":1,"projects":{"github.com/a/b":{"kind":"apk","additionalSettings":{"includePrereleases":true,"filterReleaseTitlesByRegEx":"^v[0-9]+$"}}}}'
    ).projects["github.com/a/b"]
    http = JsonHttp(
        [
            {
                "id": 9,
                "name": "debug-latest",
                "published_at": "2026-09-11T00:00:00Z",
                "prerelease": True,
                "draft": False,
            },
            {
                "id": 3,
                "name": "v3",
                "published_at": "2026-09-10T00:00:00Z",
                "prerelease": True,
                "draft": False,
            },
            {
                "id": 4,
                "name": "v4",
                "published_at": "2026-09-12T00:00:00Z",
                "prerelease": True,
                "draft": True,
            },
            {
                "id": 2,
                "name": "v2",
                "published_at": "2026-09-09T00:00:00Z",
                "prerelease": True,
                "draft": False,
            },
        ]
    )
    assert select_release(http, "github.com/a/b", rule)["id"] == 3
    assert http.urls == [
        "https://api.github.com/repos/a/b/releases?per_page=100&page=1"
    ]


def test_release_scan_bound_is_visible() -> None:
    rule = parse_project_policy(
        b'{"schemaVersion":1,"projects":{"github.com/a/b":{"kind":"apk","additionalSettings":{"includePrereleases":true}}}}'
    ).projects["github.com/a/b"]
    with pytest.raises(ValueError, match="100-release bound"):
        select_release(JsonHttp([{}] * 101), "github.com/a/b", rule)


class MappingHttp:
    def __init__(self, values: dict[str, bytes | object]) -> None:
        self.values = values
        self.urls: list[str] = []

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse:
        self.urls.append(url)
        value = self.values[url]
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        return HttpResponse(url, 200, Message(), body)


def tracking_root(tmp_path: Path) -> tuple[str, str]:
    source_url = "https://fixture.test/README.md"
    project = "github.com/example/tracker"
    config = tmp_path / "config"
    config.mkdir()
    (config / "catalogs").mkdir()
    (config / "sources.json").write_text(
        json.dumps(
            {
                "codm": {
                    "readme_url": source_url,
                    "project_policy": "config/codm-projects.json",
                    "catalog": "config/catalogs/codm.json",
                    "source_metadata": "config/catalogs/codm.source.json",
                }
            }
        )
    )
    (config / "package-ids.json").write_text("{}")
    (config / "codm-projects.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "projects": {
                    project: {
                        "kind": "track-only",
                        "trackerId": "12345",
                        "name": "Tracker",
                        "rationale": "A non-APK resource.",
                        "installation": "Install with https://github.com/example/host.",
                    }
                },
            }
        )
    )
    return source_url, project


def test_track_only_generation_writes_current_candidate_without_apk_state(
    tmp_path: Path,
) -> None:
    source_url, project = tracking_root(tmp_path)
    release_url = "https://api.github.com/repos/example/tracker/releases/latest"
    http = MappingHttp(
        {
            source_url: b"| Project | Note |\n| --- | --- |\n| [Tracker](https://github.com/example/tracker) | mod |\n",
            release_url: {
                "id": 7,
                "assets": [
                    {
                        "name": "mod.zip",
                        "browser_download_url": "https://fixture.test/mod.zip",
                    }
                ],
            },
        }
    )
    report = generate_codm(tmp_path, http=http)
    output = tmp_path / ".build/source-generation/codm"
    assert report["status"] == "success"
    app = json.loads((output / "catalog.json").read_text())["apps"][0]
    settings = json.loads(app["additionalSettings"])
    assert app["id"] == "12345" and settings["trackOnly"] is True
    assert json.loads((output / "resolution-state.json").read_text()) == {}
    assert "https://fixture.test/mod.zip" not in http.urls
    assert report["tracking"] == [{"url": project, "id": "12345", "status": "verified"}]


def test_unchanged_gate_validates_policy_then_makes_zero_release_requests(
    tmp_path: Path,
) -> None:
    source_url, _ = tracking_root(tmp_path)
    readme = b"| Project | Note |\n| --- | --- |\n| [Tracker](https://github.com/example/tracker) | mod |\n"
    release_url = "https://api.github.com/repos/example/tracker/releases/latest"
    first = generate_codm(
        tmp_path,
        http=MappingHttp({source_url: readme, release_url: {"id": 7, "assets": []}}),
    )
    assert first["status"] == "success"
    output = tmp_path / ".build/source-generation/codm"
    (tmp_path / "config/catalogs/codm.json").write_bytes(
        (output / "catalog.json").read_bytes()
    )
    (tmp_path / "config/catalogs/codm.source.json").write_bytes(
        (output / "source.json").read_bytes()
    )
    second_http = MappingHttp({source_url: readme})
    second = generate_codm(tmp_path, http=second_http)
    assert second["status"] == "unchanged"
    assert second_http.urls == [source_url]
    assert not (output / "catalog.json").exists()
    assert {path.name for path in output.iterdir()} == {"report.json"}


def test_failed_invocation_rejects_stale_candidates_and_preserves_tracked_inputs(
    tmp_path: Path,
) -> None:
    source_url, _ = tracking_root(tmp_path)
    output = tmp_path / ".build/source-generation/codm"
    output.mkdir(parents=True)
    for name in ("catalog.json", "source.json", "resolution-state.json", "report.json"):
        (output / name).write_text("stale")
    tracked = {
        path: path.read_bytes()
        for path in (
            tmp_path / "config/sources.json",
            tmp_path / "config/codm-projects.json",
            tmp_path / "config/package-ids.json",
        )
    }
    (tmp_path / "config/codm-projects.json").write_text("not json")
    tracked[tmp_path / "config/codm-projects.json"] = b"not json"

    result = generate_codm(tmp_path, http=MappingHttp({source_url: b"unused"}))

    assert result["status"] == "failed"
    assert {path.name for path in output.iterdir()} == {"report.json"}
    assert all(path.read_bytes() == contents for path, contents in tracked.items())


def test_tracker_id_collision_fails_with_both_projects(tmp_path: Path) -> None:
    source_url, _ = tracking_root(tmp_path)
    policy_path = tmp_path / "config/codm-projects.json"
    policy = json.loads(policy_path.read_text())
    first_rule = policy["projects"]["github.com/example/tracker"]
    policy["projects"]["github.com/other/tracker"] = {
        **first_rule,
        "name": "Other tracker",
    }
    policy_path.write_text(json.dumps(policy))
    readme = b"| Project | Note |\n| --- | --- |\n| [One](https://github.com/example/tracker) | mod |\n| [Two](https://github.com/other/tracker) | mod |\n"
    http = MappingHttp(
        {
            source_url: readme,
            "https://api.github.com/repos/example/tracker/releases/latest": {
                "id": 1,
                "assets": [],
            },
            "https://api.github.com/repos/other/tracker/releases/latest": {
                "id": 2,
                "assets": [],
            },
        }
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert "example/tracker" in result["error"]
    assert "other/tracker" in result["error"]
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()
