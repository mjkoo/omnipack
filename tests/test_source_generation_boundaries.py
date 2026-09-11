from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack.project_policy import PolicyError, default_apk_rule, parse_project_policy
from omnipack.source_generation import (
    generate_codm,
    parse_project_table,
    select_release,
)
from tests.test_package_id import apk
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


def accept(root, metadata=True):
    output = root / ".build/source-generation/codm"
    for src, dst in [
        ("catalog.json", "catalogs/codm.json"),
        ("resolution-state.json", "package-ids.json"),
    ] + ([("source.json", "catalogs/codm.source.json")] if metadata else []):
        (root / "config" / dst).write_bytes((output / src).read_bytes())


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


@pytest.mark.parametrize("failure", [False, True])
def test_bootstrap_derives_default_fingerprint_for_admitted_member(tmp_path, failure):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path, metadata=False)
    state_path = tmp_path / "config/package-ids.json"
    state = json.loads(state_path.read_text())
    state[PROJECT].pop("policyFingerprint")
    state_path.write_text(json.dumps(state))
    config_path = tmp_path / "config/sources.json"
    config = json.loads(config_path.read_text())
    config["codm"]["legacy_default_projects"] = [PROJECT]
    config_path.write_text(json.dumps(config))
    result, http = run(tmp_path, source, {"id": 8} if failure else release())
    assert result["status"] == "success"
    assert ASSET not in http.urls
    assert result["warnings"] if failure else result["apk"][0]["status"] == "reused"
    candidate = json.loads(
        (tmp_path / ".build/source-generation/codm/resolution-state.json").read_text()
    )
    assert candidate[PROJECT]["policyFingerprint"] == default_apk_rule().fingerprint
    assert "policyFingerprint" not in json.loads(state_path.read_text())[PROJECT]


def test_explicit_repository_name_is_valid_after_acceptance(tmp_path):
    source = setup(tmp_path, {"kind": "apk", "name": "tracker"})
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "unchanged"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schemaVersion", True),
        ("readmeSha256", "bad"),
        ("projectPolicySha256", "g" * 64),
    ],
)
def test_malformed_accepted_metadata_fails(tmp_path, field, value):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    path = tmp_path / "config/catalogs/codm.source.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    result, http = run(tmp_path, source)
    assert result["status"] == "failed"
    assert http.urls == [source]


@pytest.mark.parametrize(
    "change", ["force", "release", "policy", "format", "readme", "url"]
)
def test_accepted_gate_and_fresh_inspection(tmp_path, change):
    source = setup(tmp_path)
    first, _ = run(tmp_path, source)
    assert first["apk"][0]["status"] == "resolved"
    output = tmp_path / ".build/source-generation/codm"
    original = (output / "catalog.json").read_bytes()
    accept(tmp_path)
    policy = tmp_path / "config/codm-projects.json"
    rel = release()
    readme = README
    if change == "policy":
        policy.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "projects": {
                        PROJECT: {
                            "kind": "apk",
                            "additionalSettings": {"fallbackToOlderReleases": False},
                        }
                    },
                }
            )
        )
    elif change == "format":
        policy.write_text(json.dumps(json.loads(policy.read_text()), indent=4))
    elif change == "readme":
        readme += b"\nprose\n"
    elif change == "release":
        rel = release(8)
    elif change == "url":
        config = tmp_path / "config/sources.json"
        data = json.loads(config.read_text())
        source += "?new=1"
        data["codm"]["readme_url"] = source
        config.write_text(json.dumps(data))
    http = MappingHttp({source: readme, API: rel, ASSET: apk("org.example.app")})
    result = generate_codm(tmp_path, force=change in {"force", "release"}, http=http)
    assert result["status"] == "success"
    assert (ASSET in http.urls) == (change in {"release", "policy"})
    assert result["apk"][0]["status"] == (
        "resolved" if change in {"release", "policy"} else "reused"
    )
    assert ((output / "catalog.json").read_bytes() == original) == (change != "policy")


@pytest.mark.parametrize(
    "mode", ["new", "cache-only", "policy-change", "accepted", "kind-change"]
)
def test_failed_apk_resolution_membership_and_fallback(tmp_path, mode):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    if mode != "new":
        accept(tmp_path)
    if mode == "cache-only":
        (tmp_path / "config/catalogs/codm.json").unlink()
        (tmp_path / "config/catalogs/codm.source.json").unlink()
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
        force=True,
    )
    assert result["status"] == ("success" if mode == "accepted" else "failed")
    if mode == "accepted":
        assert result["warnings"][0]["status"] == "retained"
        assert (
            json.loads(
                (
                    tmp_path / ".build/source-generation/codm/resolution-state.json"
                ).read_text()
            )[PROJECT]["releaseId"]
            == 7
        )
    else:
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
        assert (tmp_path / "config/package-ids.json").read_text() == "{}"
        assert not (tmp_path / "config/catalogs/codm.source.json").exists()


@pytest.mark.parametrize("other_kind", ["apk", "track-only"])
def test_cross_project_collisions(tmp_path, other_kind, monkeypatch):
    source = setup(tmp_path)
    other = "github.com/other/app"
    if other_kind == "track-only":
        identifier = "123"
        monkeypatch.setattr(
            "omnipack.source_generation.PackageIdResolver.resolve_release_assets",
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


def test_apk_filter_and_all_eligible_agreement(tmp_path):
    source = setup(
        tmp_path, {"kind": "apk", "additionalSettings": {"apkFilterRegEx": "^app.*"}}
    )
    assets = [
        {"name": name, "browser_download_url": "https://fixture.test/" + name}
        for name in ["app.apk", "app-arm.APK", "debug.apk"]
    ]
    for second in [apk("org.example.app"), apk("org.example.different"), b"unreadable"]:
        http = MappingHttp(
            {
                source: README,
                API: release(assets=assets),
                ASSET: apk("org.example.app"),
                "https://fixture.test/app-arm.APK": second,
            }
        )
        result = generate_codm(tmp_path, http=http)
        assert result["status"] == (
            "success" if second == apk("org.example.app") else "failed"
        )
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
    result, http = run(tmp_path, source, release(8, assets=[]), force=True)
    assert result["status"] == ("failed" if transition else "success")
    assert ASSET not in http.urls
    if not transition:
        result, _ = run(tmp_path, source, {"id": 8}, force=True)
        assert result["warnings"][0]["status"] == "retained"


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


@pytest.mark.parametrize("variant", ["not-admitted", "nondefault", "after-acceptance"])
def test_bootstrap_rejects_unproven_legacy_entries(tmp_path, variant):
    source = setup(
        tmp_path, {"kind": "apk", "name": "Custom"} if variant == "nondefault" else None
    )
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path, metadata=variant == "after-acceptance")
    path = tmp_path / "config/package-ids.json"
    state = json.loads(path.read_text())
    state[PROJECT].pop("policyFingerprint")
    path.write_text(json.dumps(state))
    config = tmp_path / "config/sources.json"
    data = json.loads(config.read_text())
    data["codm"]["legacy_default_projects"] = (
        [] if variant == "not-admitted" else [PROJECT]
    )
    config.write_text(json.dumps(data))
    assert run(tmp_path, source)[0]["status"] == "failed"


def test_cli_real_generation_preserves_inputs_and_history(tmp_path, monkeypatch):
    import subprocess

    from omnipack.cli import main

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
    repository = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "omnipack.source_generation.HttpConfig.from_path", lambda path: None
    )
    for late_failure in [False, True]:
        readme = README + (
            b"| [New](https://github.com/new/app) | missing |\n"
            if late_failure
            else b""
        )
        http = MappingHttp(
            {
                source: readme,
                API: release(),
                ASSET: apk("org.example.app"),
                "https://api.github.com/repos/new/app/releases/latest": release(
                    8, assets=[]
                ),
            }
        )
        monkeypatch.setattr(
            "omnipack.source_generation.HttpClient", lambda config, client=http: client
        )
        assert main(["generate-source", "codm", "--force"]) == int(late_failure)
        output = tmp_path / ".build/source-generation/codm"
        report = json.loads((output / "report.json").read_text())
        assert report["apk"][0]["status"] == "reused"
        assert report["status"] == ("failed" if late_failure else "success")
        assert all(p.read_bytes() == content for p, content in tracked.items())
        assert (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository)
            == head
        )
        if late_failure:
            assert {p.name for p in output.iterdir()} == {"report.json"}


def test_kanto_settings_manual_guidance_and_cli_tracker(tmp_path, monkeypatch):
    from omnipack.cli import main

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
    monkeypatch.setattr("omnipack.source_generation.HttpClient", lambda config: http)
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
    assert json.loads((output / "resolution-state.json").read_text()) == {}
    assert "mod.zip" not in (output / "catalog.json").read_text()
    assert app.get("installedVersion") in (None, "")
    assert app.get("latestVersion") in (None, "")


@pytest.mark.parametrize("identifier", ["", -1, 0, True, None])
def test_invalid_host_release_identifier(identifier):
    with pytest.raises((TypeError, ValueError)):
        select_release(JsonHttp(release(identifier)), PROJECT, default_apk_rule())


def test_catalog_digest_failure_precedes_resolution(tmp_path):
    source = setup(tmp_path)
    assert run(tmp_path, source)[0]["status"] == "success"
    accept(tmp_path)
    path = tmp_path / "config/catalogs/codm.json"
    path.write_bytes(path.read_bytes() + b" ")
    result, http = run(tmp_path, source)
    assert result["status"] == "failed"
    assert "digest" in result["error"]
    assert http.urls == [source]


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
    assert json.loads((tmp_path / "config/package-ids.json").read_text()) == {}
    path.write_text(json.dumps({"schemaVersion": 1, "projects": {}}))
    result, http = run(tmp_path, source)
    assert result["status"] == "success"
    assert ASSET in http.urls
    assert result["apk"][0]["status"] == "resolved"
