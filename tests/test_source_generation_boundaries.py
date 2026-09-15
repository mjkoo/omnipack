from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack.cli import main
from omnipack.project_policy import PolicyError, default_apk_rule, parse_project_policy
from omnipack.source_generation import (
    generate_codm,
    parse_project_table,
    select_release,
)
from omnipack.source_http import HttpConfig, SourceHttpClient
from tests.test_package_id import AssetTransport, apk
from tests.test_source_generation import JsonHttp, MappingHttp, tracking_root

PROJECT = "github.com/example/tracker"
API = "https://api.github.com/repos/example/tracker/releases/latest"
README = b"| Project | Note |\n| --- | --- |\n| [Tracker](https://github.com/example/tracker) | app |\n"
ASSET = "https://fixture.test/app.apk"


def release(identifier=7, **fields):
    return {
        "id": identifier,
        "published_at": "2026-09-10T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "assets": [{"name": "app.apk", "browser_download_url": ASSET}],
        **fields,
    }


def setup(root: Path, rule=None):
    source, _ = tracking_root(root)
    (root / "config/codm-projects.json").write_text(
        json.dumps(
            {"schemaVersion": 1, "projects": {} if rule is None else {PROJECT: rule}}
        )
    )
    return source


def run(root, source, rel=None, **kwargs):
    http = MappingHttp(
        {
            source: README,
            API: release() if rel is None else rel,
            ASSET: apk("org.example.app"),
        }
    )
    result = generate_codm(root, http=http, **kwargs)
    return result, http


def accept(root):
    output = root / ".build/source-generation/codm"
    (root / "config/catalogs/codm.json").write_bytes(
        (output / "catalog.json").read_bytes()
    )


@pytest.mark.parametrize("separator", ["| -- |", ""])
def test_malformed_second_table_cannot_propose_removal(tmp_path, separator):
    source, _ = tracking_root(tmp_path)
    second = "\n\n| Project |\n| --- |\n| [Other](https://github.com/example/other) |\n"
    readme = README + second.encode()
    policy_path = tmp_path / "config/codm-projects.json"
    policy = json.loads(policy_path.read_bytes())
    policy["projects"]["github.com/example/other"] = {
        **policy["projects"][PROJECT],
        "trackerId": "67890",
    }
    policy_path.write_text(json.dumps(policy))
    http = MappingHttp(
        {
            source: readme,
            API: release(),
            "https://api.github.com/repos/example/other/releases/latest": release(8),
        }
    )
    assert generate_codm(tmp_path, http=http)["status"] == "success"
    accept(tmp_path)
    accepted = (tmp_path / "config/catalogs/codm.json").read_bytes()
    broken = README + second.replace("| --- |", separator).encode()
    http = MappingHttp({source: broken})
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert "Project catalog table" in result["error"]
    assert http.urls == [source]
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()
    assert (tmp_path / "config/catalogs/codm.json").read_bytes() == accepted


@pytest.mark.parametrize("selector", ["2", "$2", "v$1.$2", " 2 "])
def test_version_capture_references_fail_before_discovery(tmp_path, selector):
    source = setup(
        tmp_path,
        {
            "kind": "apk",
            "additionalSettings": {
                "versionExtractionRegEx": "^v?(.+)$",
                "matchGroupToUse": selector,
            },
        },
    )
    result, http = run(tmp_path, source)
    assert result["status"] == "failed"
    assert "capture group" in result["error"]
    assert http.urls == []
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()


@pytest.mark.parametrize("token", ["fixture-token", "", None])
def test_fresh_resolution_sends_the_api_credential_only_to_the_api_host(
    tmp_path, monkeypatch, token
):
    if token is None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    source = setup(tmp_path)
    transport = AssetTransport(
        {
            source: README,
            API: json.dumps(release()).encode(),
            ASSET: apk("org.example.app"),
        }
    )
    http = SourceHttpClient(
        HttpConfig.from_path("config/http.json"), retries=0, transport=transport
    )
    assert generate_codm(tmp_path, http=http)["status"] == "success"
    sent = [
        (request.full_url, request.get_header("Authorization"))
        for request, _ in transport.requests
    ]
    assert {url for url, _ in sent} == {source, API, ASSET}
    expected = f"Bearer {token}" if token else None
    assert all(value == (expected if url == API else None) for url, value in sent)


@pytest.mark.parametrize("selector", ["", "0", "1", "$1", "v$1.$0", " 1 "])
def test_version_capture_references_preserve_supported_selectors(selector):
    settings = {
        "versionExtractionRegEx": "^v?(.+)$",
        "matchGroupToUse": selector,
    }
    policy = parse_project_policy(
        {
            "schemaVersion": 1,
            "projects": {PROJECT: {"kind": "apk", "additionalSettings": settings}},
        }
    )
    assert policy.projects[PROJECT].additional_settings == settings


def test_duplicate_order_and_nested_paths():
    links = ["https://github.com/Owner/Repo.git/?a=1", "https://github.com/owner/repo"]

    def parse(urls):
        return parse_project_table(
            (
                "| Project |\n| --- |\n" + "".join(f"| [x]({url}) |\n" for url in urls)
            ).encode()
        )

    assert parse(links).source_urls == parse(links[::-1]).source_urls
    assert parse([links[0]]).source_urls["github.com/owner/repo"] == links[0]
    nested = "https://github.com/owner/repo/tree/main"
    assert parse([nested, links[0]]).unsupported == (nested,)
    with pytest.raises(PolicyError):
        parse_project_policy(
            {"schemaVersion": 1, "projects": {nested: {"kind": "apk"}}}
        )


@pytest.mark.parametrize(
    "pattern",
    [
        r"\Aapp",
        r"app\Z",
        "(?i)app",
        "(?s:app)",
        "(?P<x>app)",
        "a++",
        r"\123",
        "(?#comment)app",
    ],
)
def test_reject_nonportable_regex(pattern):
    with pytest.raises(PolicyError):
        parse_project_policy(
            {
                "schemaVersion": 1,
                "projects": {
                    PROJECT: {
                        "kind": "apk",
                        "additionalSettings": {"apkFilterRegEx": pattern},
                    }
                },
            }
        )


@pytest.mark.parametrize("escape", list("dDsSwWbB"))
def test_unicode_sensitive_regex_escapes_fail_before_discovery(tmp_path, escape):
    source = setup(
        tmp_path,
        {
            "kind": "apk",
            "additionalSettings": {"apkFilterRegEx": rf"^\{escape}.*\.apk$"},
        },
    )
    result, http = run(tmp_path, source)
    assert result["status"] == "failed"
    assert "explicit character classes" in result["error"]
    assert http.urls == []


def test_explicit_regex_classes_and_literal_backslashes_remain_supported():
    settings = {
        "apkFilterRegEx": r"^[A-Za-z0-9_]+\.apk$",
        "filterReleaseTitlesByRegEx": r"^Release [0-9]+$",
        "versionExtractionRegEx": r"^(\\w+)$",
    }
    policy = parse_project_policy(
        {
            "schemaVersion": 1,
            "projects": {PROJECT: {"kind": "apk", "additionalSettings": settings}},
        }
    )
    assert policy.projects[PROJECT].additional_settings == settings


@pytest.mark.parametrize(
    "instruction",
    [
        "Install it manually.",
        "https://github.com/example/host",
        "Install Host at http://github.com/example/host",
        "Install Host at https://user:pass@github.com/example/host",
        "Install Host at https://github.com/example/host/tree/main",
        1,
    ],
)
def test_tracker_instruction_requires_named_canonical_host(instruction):
    with pytest.raises(PolicyError):
        parse_project_policy(
            {
                "schemaVersion": 1,
                "projects": {
                    PROJECT: {
                        "kind": "track-only",
                        "trackerId": "123",
                        "rationale": "Mod",
                        "installation": instruction,
                    }
                },
            }
        )


@pytest.mark.parametrize(
    "fields",
    [
        {"draft": True},
        {"prerelease": True},
        {"published_at": None},
        {"published_at": "bad"},
        {"published_at": "2026-09-10"},
        {"published_at": "2026-09-10T00:00:00"},
        {"draft": "false"},
    ],
)
def test_latest_requires_published_stable_release(fields):
    with pytest.raises((ValueError, TypeError)):
        select_release(JsonHttp(release(**fields)), PROJECT, default_apk_rule())


def test_unchanged_inputs_reproduce_the_committed_catalog_byte_for_byte(tmp_path):
    source = setup(tmp_path, {"kind": "apk", "name": "tracker"})
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    committed = (tmp_path / "config/catalogs/codm.json").read_bytes()
    result, http = run(tmp_path, source)
    assert result["status"] == "success"
    assert http.urls[:2] == [source, API]
    assert all(url == ASSET for url in http.urls[2:])
    assert result["apk"][0]["status"] == "resolved"
    assert (
        tmp_path / ".build/source-generation/codm/catalog.json"
    ).read_bytes() == committed
    assert result["changes"] == {"added": [], "removed": [], "changed": []}


def test_project_resolving_to_a_different_entry_is_reported_as_changed(tmp_path):
    source = setup(tmp_path, {"kind": "apk", "name": "tracker"})
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    (tmp_path / "config/codm-projects.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "projects": {
                    PROJECT: {
                        "kind": "apk",
                        "name": "tracker",
                        "additionalSettings": {"fallbackToOlderReleases": False},
                    }
                },
            }
        )
    )
    result = run(tmp_path, source)[0]
    assert result["status"] == "success"
    assert result["changes"] == {"added": [], "removed": [], "changed": [PROJECT]}
    assert result["retainedFailures"] == []


def test_readme_additions_and_removals_are_reported(tmp_path):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    other_api = "https://api.github.com/repos/other/app/releases/latest"
    other_asset = ASSET + "?other"
    http = MappingHttp(
        {
            source: b"| Project | Note |\n| --- | --- |\n"
            b"| [Other](https://github.com/other/app) | app |\n",
            other_api: release(
                8, assets=[{"name": "other.apk", "browser_download_url": other_asset}]
            ),
            other_asset: apk("org.example.other"),
        }
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "success"
    assert result["changes"] == {
        "added": ["github.com/other/app"],
        "removed": [PROJECT],
        "changed": [],
    }


def test_retained_entry_survives_an_unchanged_or_reformatted_policy(tmp_path):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    policy_path = tmp_path / "config/codm-projects.json"
    policy_path.write_text(json.dumps(json.loads(policy_path.read_text()), indent=4))
    committed = (tmp_path / "config/catalogs/codm.json").read_bytes()
    result, http = run(tmp_path, source, release(8, assets=[]))
    assert result["status"] == "success"
    assert ASSET not in http.urls
    assert result["retainedFailures"] == [
        {"url": PROJECT, "message": "latest release has no eligible APK assets"}
    ]
    assert (
        tmp_path / ".build/source-generation/codm/catalog.json"
    ).read_bytes() == committed
    assert result["changes"] == {"added": [], "removed": [], "changed": []}


@pytest.mark.parametrize("mode", ["new", "policy-change", "kind-change"])
def test_failed_apk_resolution_membership_and_fallback(tmp_path, mode):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    if mode != "new":
        accept(tmp_path)
    if mode == "policy-change":
        (tmp_path / "config/codm-projects.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "projects": {PROJECT: {"kind": "apk", "name": "Changed"}},
                }
            )
        )
    if mode == "kind-change":
        (tmp_path / "config/codm-projects.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "projects": {
                        PROJECT: {
                            "kind": "track-only",
                            "trackerId": "123",
                            "rationale": "mod",
                            "installation": "Install Host from https://github.com/example/host",
                        }
                    },
                }
            )
        )
    result, _ = run(
        tmp_path,
        source,
        {"id": 8} if mode == "kind-change" else release(8, assets=[]),
    )
    assert result["status"] == "failed"
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()


def test_retries_never_accept_partial_resolutions(tmp_path):
    source = setup(tmp_path)
    readme = README + b"| [Other](https://github.com/other/app) | app |\n"
    other = "https://api.github.com/repos/other/app/releases/latest"
    for attempt in range(3):
        values = {
            source: readme,
            API: release(),
            ASSET: apk("org.example.app"),
            other: release(
                8,
                assets=[]
                if attempt < 2
                else [{"name": "other.apk", "browser_download_url": ASSET + "?other"}],
            ),
            ASSET + "?other": apk("org.example.other"),
        }
        http = MappingHttp(values)
        result = generate_codm(tmp_path, http=http)
        assert ASSET in http.urls
        assert result["status"] == ("failed" if attempt < 2 else "success")
        candidate_exists = (
            tmp_path / ".build/source-generation/codm/catalog.json"
        ).exists()
        assert candidate_exists == (attempt == 2)


@pytest.mark.parametrize("other_kind", ["apk", "track-only"])
def test_cross_project_collisions(tmp_path, other_kind, monkeypatch):
    source = setup(tmp_path)
    other = "github.com/other/app"
    if other_kind == "track-only":
        identifier = "123"
        monkeypatch.setattr(
            "omnipack.source_generation.resolve_release_assets",
            lambda *args, **kwargs: identifier,
        )
        (tmp_path / "config/codm-projects.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "projects": {
                        other: {
                            "kind": "track-only",
                            "trackerId": identifier,
                            "rationale": "mod",
                            "installation": "Install Host from https://github.com/example/host",
                        }
                    },
                }
            )
        )
    else:
        identifier = "org.example.app"
    http = MappingHttp(
        {
            source: README + b"| [Other](https://github.com/other/app) | app |\n",
            API: release(),
            "https://api.github.com/repos/other/app/releases/latest": release(),
            ASSET: apk(identifier),
        }
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert PROJECT in result["error"] and other in result["error"]


def test_heimdall_newest_matching_release_never_searches_older_apk(tmp_path):
    rule = {
        "kind": "apk",
        "additionalSettings": {
            "includePrereleases": True,
            "filterReleaseTitlesByRegEx": r"^Heimdall v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta)\.[0-9]+)?$",
            "apkFilterRegEx": r"^heimdall-v[0-9].*\.apk$",
            "fallbackToOlderReleases": True,
        },
    }
    source = setup(tmp_path, rule)
    listed = API.replace("/latest", "?per_page=100&page=1")
    releases = [
        release(9, name="debug-latest", published_at="2026-09-11T00:00:00Z"),
        release(8, name="Heimdall v1.0.0-alpha.1", assets=[]),
        release(
            7,
            name="Heimdall v0.9.0",
            published_at="2026-09-09T00:00:00Z",
            assets=[{"name": "heimdall-v0.9.apk", "browser_download_url": ASSET}],
        ),
    ]
    http = MappingHttp(
        {source: README, listed: releases, ASSET: apk("org.example.app")}
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert ASSET not in http.urls
    assert (
        result["effectivePolicy"][PROJECT]["additionalSettings"][
            "fallbackToOlderReleases"
        ]
        is True
    )


@pytest.mark.parametrize(
    ("second", "expected_status"),
    [
        (apk("org.example.app"), "success"),
        (apk("org.example.different"), "failed"),
        (b"unreadable", "failed"),
    ],
    ids=["matching-id", "mixed-ids", "unreadable"],
)
def test_apk_filter_and_all_eligible_agreement(tmp_path, second, expected_status):
    source = setup(
        tmp_path, {"kind": "apk", "additionalSettings": {"apkFilterRegEx": "^app.*"}}
    )
    assets = [
        {"name": name, "browser_download_url": "https://fixture.test/" + name}
        for name in ["app.apk", "app-arm.APK", "debug.apk"]
    ]
    http = MappingHttp(
        {
            source: README,
            API: release(assets=assets),
            ASSET: apk("org.example.app"),
            "https://fixture.test/app-arm.APK": second,
        }
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == expected_status
    assert result["filteredAssets"] == [{"url": PROJECT, "names": ["debug.apk"]}]
    assert "https://fixture.test/debug.apk" not in http.urls


def test_equal_publication_time_uses_numeric_id():
    rule = parse_project_policy(
        {
            "schemaVersion": 1,
            "projects": {
                PROJECT: {
                    "kind": "apk",
                    "additionalSettings": {"includePrereleases": True},
                }
            },
        }
    ).projects[PROJECT]
    for releases in [
        [release(9, name="a"), release(10, name="b")],
        [release(10, name="b"), release(9, name="a")],
    ]:
        assert select_release(JsonHttp(releases), PROJECT, rule)["id"] == 10


@pytest.mark.parametrize("transition", [False, True])
def test_tracker_fallback_and_transition(tmp_path, transition):
    source, _ = tracking_root(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    if transition:
        (tmp_path / "config/codm-projects.json").write_text(
            json.dumps({"schemaVersion": 1, "projects": {}})
        )
    result, http = run(tmp_path, source, release(8, assets=[]))
    assert result["status"] == ("failed" if transition else "success")
    assert ASSET not in http.urls
    if not transition:
        result, _ = run(tmp_path, source, {"id": 8})
        assert result["retainedFailures"][0]["url"] == PROJECT


def test_tracker_id_change_with_failed_lookup_blocks_generation(tmp_path):
    source_url, project = tracking_root(tmp_path)
    readme = b"| Project | Note |\n| --- | --- |\n| [Tracker](https://github.com/example/tracker) | mod |\n"
    release_url = "https://api.github.com/repos/example/tracker/releases/latest"
    good_release = {"id": 7, "published_at": "2026-09-10T00:00:00Z", "assets": []}
    first = generate_codm(
        tmp_path, http=MappingHttp({source_url: readme, release_url: good_release})
    )
    assert first["status"] == "success"
    (tmp_path / "config/catalogs/codm.json").write_bytes(
        (tmp_path / ".build/source-generation/codm/catalog.json").read_bytes()
    )
    policy_path = tmp_path / "config/codm-projects.json"
    policy = json.loads(policy_path.read_text())
    policy["projects"][project]["trackerId"] = "67890"
    policy_path.write_text(json.dumps(policy))
    result = generate_codm(tmp_path, http=MappingHttp({source_url: readme}))
    assert result["status"] == "failed"
    assert result["retainedFailures"] == []
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()


@pytest.mark.parametrize(
    "rule",
    [
        {"kind": "apk", "name": 1},
        {"kind": "apk", "additionalSettings": {"includePrereleases": 1}},
        {"kind": "apk", "additionalSettings": {"matchGroupToUse": "1"}},
        {
            "kind": "track-only",
            "trackerId": "1",
            "rationale": "mod",
            "installation": "Install Host from https://github.com/example/host",
            "additionalSettings": {"apkFilterRegEx": "x"},
        },
        {"kind": "apk", "unknown": True},
    ],
)
def test_invalid_rule_fields_and_combinations(rule):
    with pytest.raises(PolicyError):
        parse_project_policy({"schemaVersion": 1, "projects": {PROJECT: rule}})


@pytest.mark.parametrize(
    "policy",
    [
        b'{"schemaVersion":1,"schemaVersion":1,"projects":{}}',
        (
            b'{"schemaVersion":1,"projects":{'
            b'"github.com/example/tracker":{"kind":"apk","additionalSettings":{"includePrereleases":false}},'
            b'"github.com/example/tracker":{"kind":"apk","additionalSettings":{"includePrereleases":true}}}}'
        ),
        (
            b'{"schemaVersion":1,"projects":{"github.com/example/tracker":'
            b'{"kind":"apk","additionalSettings":{"includePrereleases":false,"includePrereleases":true}}}}'
        ),
    ],
    ids=["root", "project", "setting"],
)
def test_duplicate_json_policy_keys_fail_before_discovery(tmp_path, policy):
    source = setup(tmp_path)
    policy_path = tmp_path / "config/codm-projects.json"
    policy_path.write_bytes(policy)
    with pytest.raises(PolicyError, match="duplicate"):
        parse_project_policy(policy)
    result, http = run(tmp_path, source)
    assert result["status"] == "failed"
    assert "duplicate" in result["error"]
    assert http.urls == []
    assert policy_path.read_bytes() == policy
    output = tmp_path / ".build/source-generation/codm"
    assert not (output / "catalog.json").exists()


def test_duplicate_policy_keys_and_inactive_rules(tmp_path):
    with pytest.raises(PolicyError, match="duplicate"):
        parse_project_policy(
            {
                "schemaVersion": 1,
                "projects": {
                    PROJECT: {"kind": "apk"},
                    "https://github.com/Example/Tracker.git": {"kind": "apk"},
                },
            }
        )
    source = setup(tmp_path)
    (tmp_path / "config/codm-projects.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "projects": {"github.com/inactive/app": {"kind": "apk"}},
            }
        )
    )
    result, _ = run(tmp_path, source)
    assert result["inactiveRules"] == ["github.com/inactive/app"]


def test_cli_real_generation_preserves_inputs_and_cleans_failed_candidates(
    tmp_path, monkeypatch
):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    (tmp_path / "README.md").write_text("handwritten")
    (tmp_path / "dist").mkdir()
    for name in ["single-screen.json", "dual-screen.json"]:
        (tmp_path / "dist" / name).write_text("published")
    tracked = {
        p: p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and ".build" not in p.parts
    }
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "omnipack.source_generation.HttpConfig.from_path", lambda path: None
    )
    for late_failure in [False, True]:
        readme = README + (
            b"| [New](https://github.com/new-project/app) | missing |\n"
            if late_failure
            else b""
        )
        http = MappingHttp(
            {
                source: readme,
                API: release(),
                ASSET: apk("org.example.app"),
                "https://api.github.com/repos/new-project/app/releases/latest": release(
                    8, assets=[]
                ),
            }
        )
        monkeypatch.setattr(
            "omnipack.source_generation.SourceHttpClient",
            lambda config, client=http: client,
        )
        assert main(["generate-source", "codm"]) == int(late_failure)
        output = tmp_path / ".build/source-generation/codm"
        report = json.loads((output / "report.json").read_text())
        assert report["apk"][0]["status"] == "resolved"
        assert report["status"] == ("failed" if late_failure else "success")
        assert all(p.read_bytes() == content for p, content in tracked.items())
        if late_failure:
            assert {p.name for p in output.iterdir()} == {"report.json"}


def test_kanto_settings_manual_guidance_and_cli_tracker(tmp_path, monkeypatch):
    source = setup(
        tmp_path,
        {
            "kind": "track-only",
            "trackerId": "1845280017",
            "name": "Kanto Gear (mod updates)",
            "rationale": "A Lua mod for Gen1Recomp.",
            "installation": "Install/update through official Gen1Recomp at https://github.com/bryanthaboi/gen1recomp using its Mod Index or ZIP import.",
        },
    )
    monkeypatch.chdir(tmp_path)
    http = MappingHttp(
        {
            source: README,
            API: release(
                assets=[
                    {
                        "name": "mod.zip",
                        "browser_download_url": "https://fixture.test/mod.zip",
                    }
                ]
            ),
        }
    )
    monkeypatch.setattr(
        "omnipack.source_generation.HttpConfig.from_path", lambda path: None
    )
    monkeypatch.setattr(
        "omnipack.source_generation.SourceHttpClient", lambda config: http
    )
    assert main(["generate-source", "codm"]) == 0
    output = tmp_path / ".build/source-generation/codm"
    app = json.loads((output / "catalog.json").read_text())["apps"][0]
    settings = json.loads(app["additionalSettings"])
    assert app["id"] == "1845280017"
    assert settings["trackOnly"] is True
    for key in ["versionDetection", "includeZips", "autoApkFilterByArch"]:
        assert settings[key] is False
    assert (
        "https://github.com/bryanthaboi/gen1recomp using its Mod Index or ZIP import."
        in settings["about"]
    )
    assert "acknowledgement does not install" in settings["about"]
    assert http.urls == [source, API]
    assert "mod.zip" not in (output / "catalog.json").read_text()
    assert app.get("installedVersion") in (None, "")
    assert app.get("latestVersion") in (None, "")


@pytest.mark.parametrize(
    "identifier",
    ["", "9", "10", "0", "-1", "invalid", -1, 0, True, None],
    ids=lambda value: f"{type(value).__name__}-{value}",
)
def test_invalid_host_release_identifier(identifier):
    with pytest.raises((TypeError, ValueError)):
        select_release(JsonHttp(release(identifier)), PROJECT, default_apk_rule())


def test_both_kind_transitions_require_fresh_destination_validation(tmp_path):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    path = tmp_path / "config/codm-projects.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "projects": {
                    PROJECT: {
                        "kind": "track-only",
                        "trackerId": "123",
                        "rationale": "mod",
                        "installation": "Install Host from https://github.com/example/host",
                    }
                },
            }
        )
    )
    result, http = run(tmp_path, source)
    assert result["status"] == "success"
    assert ASSET not in http.urls
    assert result["tracking"][0]["id"] == "123"
    accept(tmp_path)
    path.write_text(json.dumps({"schemaVersion": 1, "projects": {}}))
    result, http = run(tmp_path, source)
    assert result["status"] == "success"
    assert ASSET in http.urls
    assert result["apk"][0]["status"] == "resolved"


@pytest.mark.parametrize(
    "instruction",
    [
        "Install Host from https://example.org/host",
        "Install Host from https://github.com/Example/Host",
    ],
)
def test_tracker_instruction_supports_canonical_host_urls(instruction):
    policy = parse_project_policy(
        {
            "schemaVersion": 1,
            "projects": {
                PROJECT: {
                    "kind": "track-only",
                    "trackerId": "123",
                    "rationale": "mod",
                    "installation": instruction,
                }
            },
        }
    )
    assert policy.projects[PROJECT].installation == instruction


@pytest.mark.parametrize(
    "name,tag", [("  Release stable  ", "v1"), ("   ", "stable-v1")]
)
def test_title_filter_uses_search_and_trimmed_tag_fallback(name, tag):
    rule = parse_project_policy(
        {
            "schemaVersion": 1,
            "projects": {
                PROJECT: {
                    "kind": "apk",
                    "additionalSettings": {"filterReleaseTitlesByRegEx": "stable"},
                }
            },
        }
    ).projects[PROJECT]
    chosen = release(name=name, tag_name=tag)
    assert select_release(JsonHttp([chosen]), PROJECT, rule) == chosen


def test_change_summary_failure_fails_generation_without_a_catalog(tmp_path):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    catalog_path = tmp_path / "config/catalogs/codm.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["apps"][0]["additionalSettings"] = "{not json"
    catalog_path.write_text(json.dumps(catalog))

    result = run(tmp_path, source)[0]

    assert result["status"] == "failed"
    assert "error" in result
    assert "changes" not in result
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()
