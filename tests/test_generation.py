from __future__ import annotations

import hashlib
import json
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from omnipack import cli
from omnipack.discovery import GeneratedSource, Listing
from omnipack.generation import (
    generate,
    load_committed,
    placeholder_id,
    render_entries,
    trim_name,
)
from omnipack.http import HttpClient, HttpError, HttpResponse
from omnipack.report_model import Status
from omnipack.settings_defaults import SETTINGS_DEFAULTS
from omnipack.source_catalog import render_catalog
from tests.test_discovery import (
    ASSETS_URL,
    INDEX_URL,
    LIST_URL,
    README_URL,
    FakeHttp,
    asset,
    quiver_http,
    row,
)

TABLE = "| Project | Game |\n|---|---|\n"


def entry_for(listings: list[Listing], committed: dict[str, Any] | None = None):
    [entry] = render_entries(listings, committed or {})
    return entry


def candidate(listings: list[Listing], committed: dict[str, Any] | None = None):
    return render_catalog(render_entries(listings, committed or {}))


def test_github_listing_becomes_a_minimal_entry_with_a_placeholder_id() -> None:
    entry = entry_for([Listing("https://github.com/owner/repo", "Repo App")])
    assert entry == {
        "id": hashlib.sha256(b"github.com/owner/repo").hexdigest()[:12],
        "url": "https://github.com/owner/repo",
        "author": "owner",
        "name": "Repo App",
        "additionalSettings": {},
        "categories": [],
        "overrideSource": "GitHub",
    }
    [rendered] = json.loads(candidate([Listing(entry["url"], "Repo App")]))["apps"]
    assert json.loads(rendered["additionalSettings"]) == SETTINGS_DEFAULTS["GitHub"]


def test_gitlab_listing_declares_gitlab_and_its_top_level_group() -> None:
    entry = entry_for([Listing("https://gitlab.com/group/sub/app", "App")])
    assert (entry["overrideSource"], entry["author"]) == ("GitLab", "group")


def test_link_on_another_host_has_no_source_type_and_no_author() -> None:
    entry = entry_for([Listing("https://christt105.itch.io/poketch", "Pokétch")])
    assert "overrideSource" not in entry
    assert (entry["url"], entry["author"], entry["name"]) == (
        "https://christt105.itch.io/poketch",
        "",
        "Pokétch",
    )
    [rendered] = json.loads(candidate([Listing(entry["url"], "Pokétch")]))["apps"]
    assert "overrideSource" not in rendered
    assert rendered["additionalSettings"] == "{}"


def test_release_asset_deep_link_becomes_the_repository_root() -> None:
    entry = entry_for(
        [Listing("https://github.com/Owner/Repo/releases/download/v1.0/app.apk", "A")]
    )
    assert (entry["url"], entry["author"]) == ("https://github.com/Owner/Repo", "Owner")


def test_other_host_keeps_query_and_reduces_host() -> None:
    entry = entry_for([Listing("https://www.Example.test/store/app/?id=a#top", None)])
    assert entry["url"] == "https://example.test/store/app?id=a#top"
    assert entry["name"] == "app"


@pytest.mark.parametrize(
    "order",
    [
        ["https://github.com/Owner/Repo", "https://github.com/owner/repo"],
        ["https://github.com/owner/repo", "https://github.com/Owner/Repo"],
    ],
)
def test_two_spellings_collapse_to_the_smallest_url_whatever_the_order(
    order: list[str],
) -> None:
    listings = [Listing(url, "Repo") for url in order]
    [entry] = json.loads(candidate(listings))["apps"]
    assert (entry["url"], entry["author"]) == ("https://github.com/Owner/Repo", "Owner")
    assert candidate(listings) == candidate(list(reversed(listings)))


@pytest.mark.parametrize("names", [["App", "app"], ["app", "App"]])
def test_listing_order_does_not_choose_the_name(names: list[str]) -> None:
    listings = [Listing("https://github.com/o/r", name) for name in names]
    assert entry_for(listings)["name"] == "App"
    assert candidate(listings) == candidate(list(reversed(listings)))


def test_names_take_the_first_in_case_insensitive_order() -> None:
    listings = [
        Listing("https://github.com/o/r", "links Awakening"),
        Listing("https://github.com/o/r", "BOI-DS 🤖"),
        Listing("https://github.com/o/r", " "),
    ]
    assert entry_for(listings)["name"] == "BOI-DS"


def test_name_falls_back_to_the_last_path_segment() -> None:
    assert entry_for([Listing("https://github.com/o/my-port", "🤖")])["name"] == (
        "my-port"
    )


@pytest.mark.parametrize(
    ("raw", "trimmed"),
    [
        ("Kanto Gear 🤖", "Kanto Gear"),
        ("Port ★", "Port"),
        ("Thumbs 👍🏽", "Thumbs"),
        ("Keycap 9️⃣", "Keycap 9"),
        ("Family 👨‍👩‍👧", "Family"),
        ("  Sonic 3 A.I.R.  ", "Sonic 3 A.I.R."),
        ("Notepad++", "Notepad++"),
        ("Price $", "Price $"),
        ("🤖 Leading", "🤖 Leading"),
        (None, ""),
    ],
)
def test_trailing_emoji_and_symbols_are_trimmed(raw: str | None, trimmed: str) -> None:
    assert trim_name(raw) == trimmed


def test_quiver_name_with_a_trailing_symbol_is_trimmed(tmp_path: Path) -> None:
    write_config(tmp_path)
    http = quiver_http(
        [row("owner/repo", project="Melee PC ™")], [asset("owner/repo", "m.apk")]
    )
    generate(tmp_path, GeneratedSource.QUIVER, http=http)
    [entry] = catalog_apps(tmp_path, GeneratedSource.QUIVER)
    assert entry["name"] == "Melee PC"


COMMITTED = {
    "id": "com.example.app",
    "url": "https://github.com/owner/repo",
    "author": "owner",
    "name": "Repo",
    "additionalSettings": "{}",
    "categories": [],
    "overrideSource": "GitHub",
}


def test_committed_entry_keeps_its_id_url_and_author_when_upstream_recases() -> None:
    committed = {"github.com/owner/repo": COMMITTED}
    entry = entry_for([Listing("https://github.com/Owner/Repo", "Repo")], committed)
    assert (entry["id"], entry["url"], entry["author"]) == (
        "com.example.app",
        "https://github.com/owner/repo",
        "owner",
    )
    assert candidate(
        [Listing("https://github.com/Owner/Repo", "Repo")], committed
    ) == render_catalog([COMMITTED])


def test_placeholder_id_hashes_the_normalized_url() -> None:
    assert (
        placeholder_id("github.com/owner/repo")
        == (hashlib.sha256(b"github.com/owner/repo").hexdigest()[:12])
    )
    assert len(placeholder_id("x")) == 12


def test_missing_committed_catalog_holds_nothing(tmp_path: Path) -> None:
    assert load_committed(tmp_path / "missing.json") == {}


@pytest.mark.parametrize(
    "body",
    ["not json", "[]", '{"apps": {}}', '{"apps": [{"id": "a"}]}', '{"apps": [7]}'],
)
def test_malformed_committed_catalog_fails(tmp_path: Path, body: str) -> None:
    (tmp_path / "catalog.json").write_text(body)
    with pytest.raises(ValueError, match="committed catalog"):
        load_committed(tmp_path / "catalog.json")


def test_two_committed_entries_at_one_project_fail_naming_both_ids(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    committed = [
        {**COMMITTED, "url": "https://github.com/Owner/Repo"},
        {
            **COMMITTED,
            "id": "a1b2c3d4e5f6",
            "url": "https://www.github.com/owner/repo/",
        },
    ]
    write_catalog(tmp_path, "codm", committed)
    http = FakeHttp(
        {README_URL: TABLE + "| [A](https://github.com/owner/repo) | x |\n"}
    )
    report = generate(tmp_path, GeneratedSource.CODM, http=http)
    assert report["status"] == Status.FAILED
    assert "github.com/owner/repo" in report["error"]
    assert "a1b2c3d4e5f6" in report["error"]
    assert "com.example.app" in report["error"]
    assert not candidate_path(tmp_path, "codm").exists()


# --- the generate-source command -----------------------------------------


def write_config(root: Path) -> None:
    (root / "config").mkdir(exist_ok=True)
    (root / "config/sources.json").write_text(
        json.dumps(
            {
                "codm": {"readme_url": README_URL, "catalog": "config/codm.json"},
                "quiver": {"index_url": INDEX_URL, "catalog": "config/quiver.json"},
            }
        )
    )


def write_catalog(root: Path, source: str, apps: list[dict[str, Any]]) -> None:
    (root / f"config/{source}.json").write_bytes(render_catalog(apps))


def candidate_path(root: Path, source: str) -> Path:
    return root / f".build/source-generation/{source}/catalog.json"


def catalog_apps(root: Path, source: str) -> list[dict[str, Any]]:
    return json.loads(candidate_path(root, source).read_bytes())["apps"]


def stored_report(root: Path, source: str) -> dict[str, Any]:
    return json.loads(
        (root / f".build/source-generation/{source}/report.json").read_bytes()
    )


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_cli(monkeypatch: pytest.MonkeyPatch, source: str, http: FakeHttp) -> int:
    monkeypatch.setattr("omnipack.generation.HttpClient", lambda: http)
    return cli.main(["generate-source", source])


def test_codm_command_writes_candidate_and_report_requesting_only_the_readme(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme = TABLE + (
        "| [Kanto Gear 🤖](https://github.com/AverageConsumer/kanto-gear) | x |\n"
        "| [Pokétch](https://christt105.itch.io/poketch) | y |\n"
    )
    http = FakeHttp({README_URL: readme})
    assert run_cli(monkeypatch, "codm", http) == 0
    assert http.urls == [README_URL]
    apps = catalog_apps(workdir, "codm")
    assert {(app["name"], app.get("overrideSource")) for app in apps} == {
        ("Kanto Gear", "GitHub"),
        ("Pokétch", None),
    }
    report = stored_report(workdir, "codm")
    assert report["status"] == "success"
    assert report["source"] == "codm"
    assert report["inputs"] == [
        {"url": README_URL, "sha256": hashlib.sha256(readme.encode()).hexdigest()}
    ]
    assert report["skipped"] == []
    assert report["changes"] == {
        "added": [
            "https://christt105.itch.io/poketch",
            "https://github.com/AverageConsumer/kanto-gear",
        ],
        "removed": [],
        "changed": [],
    }


def test_unchanged_inputs_reproduce_the_committed_catalog_byte_for_byte(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    http = FakeHttp({README_URL: TABLE + "| [A 🤖](https://github.com/o/a) | x |\n"})
    assert run_cli(monkeypatch, "codm", http) == 0
    (workdir / "config/codm.json").write_bytes(
        candidate_path(workdir, "codm").read_bytes()
    )
    assert run_cli(monkeypatch, "codm", http) == 0
    assert (
        candidate_path(workdir, "codm").read_bytes()
        == (workdir / "config/codm.json").read_bytes()
    )
    assert stored_report(workdir, "codm")["changes"] == {
        "added": [],
        "removed": [],
        "changed": [],
    }


def test_a_renamed_committed_entry_is_changed_not_removed_and_added(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gone = {**COMMITTED, "id": "com.example.gone", "url": "https://github.com/o/gone"}
    write_catalog(workdir, "codm", [COMMITTED, gone])
    http = FakeHttp(
        {README_URL: TABLE + "| [New Name](https://github.com/Owner/Repo) | x |\n"}
    )
    assert run_cli(monkeypatch, "codm", http) == 0
    [entry] = catalog_apps(workdir, "codm")
    assert (entry["id"], entry["url"], entry["name"]) == (
        "com.example.app",
        "https://github.com/owner/repo",
        "New Name",
    )
    assert stored_report(workdir, "codm")["changes"] == {
        "added": [],
        "removed": ["https://github.com/o/gone"],
        "changed": ["https://github.com/owner/repo"],
    }


def test_a_failed_rerun_leaves_no_candidate_and_records_the_error(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    good = FakeHttp({README_URL: TABLE + "| [A](https://github.com/o/a) | x |\n"})
    assert run_cli(monkeypatch, "codm", good) == 0
    assert candidate_path(workdir, "codm").exists()
    bad = FakeHttp({README_URL: HttpError("README unavailable")})
    assert run_cli(monkeypatch, "codm", bad) == 1
    assert not candidate_path(workdir, "codm").exists()
    report = stored_report(workdir, "codm")
    assert (report["status"], report["error"]) == ("failed", "README unavailable")
    assert "README unavailable" in capsys.readouterr().err


def test_quiver_command_reports_skipped_rows_and_screened_out_projects(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_catalog(
        workdir, "quiver", [{**COMMITTED, "url": "https://github.com/kept/old"}]
    )
    http = quiver_http(
        [
            row("kept/old", project="Committed"),
            row("new/port", project="New"),
            row("new/zip", project="Zip only"),
            row("a/b", project="Elsewhere", repositorySource="codeberg"),
        ],
        [
            asset("kept/old", "old.zip"),
            asset("new/port", "port.apk"),
            asset("new/zip", "port.zip"),
        ],
    )
    assert run_cli(monkeypatch, "quiver", http) == 0
    assert http.urls == [INDEX_URL, ASSETS_URL, LIST_URL]
    kept, new = catalog_apps(workdir, "quiver")
    assert (kept["id"], kept["url"]) == (
        "com.example.app",
        "https://github.com/kept/old",
    )
    assert (new["id"], new["url"]) == (
        placeholder_id("github.com/new/port"),
        "https://github.com/new/port",
    )
    report = stored_report(workdir, "quiver")
    assert [(item["project"], item["reason"]) for item in report["skipped"]] == [
        ("Zip only", "latest release lists no APK asset"),
        ("Elsewhere", "names a forge no project URL can be formed for"),
    ]
    assert [item["url"] for item in report["inputs"]] == [
        INDEX_URL,
        ASSETS_URL,
        LIST_URL,
    ]


def test_a_run_whose_candidate_keeps_nothing_fails_with_the_skipped_rows(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    http = quiver_http([row("a/b", project="Zip only")], [asset("a/b", "a.zip")])
    assert run_cli(monkeypatch, "quiver", http) == 1
    report = stored_report(workdir, "quiver")
    assert report["status"] == "failed"
    assert [item["reason"] for item in report["skipped"]] == [
        "latest release lists no APK asset"
    ]
    assert not candidate_path(workdir, "quiver").exists()


def test_the_command_rejects_an_unknown_source() -> None:
    with pytest.raises(SystemExit):
        cli.main(["generate-source", "rjny"])


def test_generation_sends_no_credentials_when_a_token_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    requests: list[Any] = []

    def transport(_client: HttpClient, request: Any, _timeout: float) -> HttpResponse:
        requests.append(request)
        body = (TABLE + "| [A](https://github.com/o/a) | x |\n").encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    report = generate(tmp_path, GeneratedSource.CODM)
    assert report["status"] == Status.SUCCESS
    assert [request.full_url for request in requests] == [README_URL]
    assert all(request.get_header("Authorization") is None for request in requests)
