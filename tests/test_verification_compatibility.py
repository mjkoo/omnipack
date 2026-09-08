import json
from pathlib import Path

import pytest

from obtainium_pack.resolution.support import SupportClass, classify_settings
from obtainium_pack.settings_defaults import SETTINGS_DEFAULTS

FIXTURES = Path(__file__).parent / "fixtures" / "verification"


def test_every_default_setting_has_an_explicit_live_classification() -> None:
    for source, defaults in SETTINGS_DEFAULTS.items():
        classifications = classify_settings(source, defaults)
        assert classifications.keys() == defaults.keys()
        assert all(item.classification is not None for item in classifications.values())
        assert all("unknown" not in item.reason for item in classifications.values())


def test_unknown_setting_is_a_live_error_even_when_false() -> None:
    settings = {**SETTINGS_DEFAULTS["GitHub"], "futureSetting": False}
    result = classify_settings("GitHub", settings)

    assert result["futureSetting"].classification is SupportClass.LIVE_ERROR
    assert "unknown" in result["futureSetting"].reason


def test_every_setting_in_both_committed_packs_is_classified() -> None:
    repository = Path(__file__).parents[1]
    live_errors: set[str] = set()
    for name in ("single-screen.json", "dual-screen.json"):
        pack = json.loads((repository / "dist" / name).read_text())
        for app in pack["apps"]:
            settings = json.loads(app["additionalSettings"])
            result = classify_settings(app["overrideSource"], settings)
            assert result.keys() == settings.keys()
            assert all("unknown" not in item.reason for item in result.values())
            live_errors.update(
                key
                for key, item in result.items()
                if item.classification is SupportClass.LIVE_ERROR
            )

    assert live_errors == set()


@pytest.mark.parametrize(
    ("source", "updates", "key"),
    [
        ("GitHub", {"includeZips": True}, "includeZips"),
        ("GitHub", {"GHReqPrefix": "proxy.example"}, "GHReqPrefix"),
        ("HTML", {"allowInsecure": True}, "allowInsecure"),
        (
            "HTML",
            {
                "versionExtractionRegEx": "",
                "defaultPseudoVersioningMethod": "APKLinkHash",
            },
            "defaultPseudoVersioningMethod",
        ),
    ],
)
def test_active_unsupported_settings_are_live_errors(
    source: str, updates: dict[str, object], key: str
) -> None:
    settings = {**SETTINGS_DEFAULTS[source], **updates}
    assert (
        classify_settings(source, settings)[key].classification
        is SupportClass.LIVE_ERROR
    )


def test_inactive_unsupported_and_device_settings_are_distinguished() -> None:
    result = classify_settings(
        "HTML",
        {
            **SETTINGS_DEFAULTS["HTML"],
            "versionExtractionRegEx": r"v([0-9.]+)",
        },
    )

    assert result["includeZips"].classification is SupportClass.INACTIVE_UNSUPPORTED
    assert (
        result["defaultPseudoVersioningMethod"].classification
        is SupportClass.INACTIVE_UNSUPPORTED
    )
    assert (
        result["autoApkFilterByArch"].classification is SupportClass.DEVICE_OR_HARMLESS
    )


def test_fixture_manifest_covers_all_configured_resolution_patterns() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    cases = manifest["cases"]

    assert {case["id"] for case in cases if case["source"] == "HTML"} == {
        "org.dolphinemu.dolphinemu",
        "com.github.stenzek.duckstation",
        "dev.eden.eden_emulator",
        "org.ppsspp.ppsspp",
        "com.virtualapplications.play",
        "487343354",
        "org.scummvm.scummvm",
    }
    assert {case["pattern"] for case in cases if case["source"] == "GitHub"} == {
        "direct-apk",
        "asset-filter",
        "prerelease",
        "release-title-version",
        "release-date-asset-date",
        "regex-concatenation",
        "track-only-release",
        "track-only-tags-fallback",
    }
    for case in cases:
        fixture = json.loads((FIXTURES / case["fixture"]).read_text())
        provenance = fixture["provenance"]
        assert provenance["kind"] in {"live-capture", "synthetic-discriminator"}
        if provenance["kind"] == "live-capture":
            assert provenance["source_url"].startswith("https://")
            assert provenance["captured_at"]
        else:
            assert provenance["behavioral_source_url"].startswith("https://")
            assert "no live capture is claimed" in provenance["note"]

        evidence = fixture["cases"][case["case"]] if "case" in case else fixture
        assert evidence["expected"]["version"]
        assert "trackOnly" in evidence["settings"]
        if not evidence["settings"]["trackOnly"]:
            assert evidence["expected"]["selected_url"].startswith("https://")


def test_all_seven_html_fixtures_are_real_captures() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for case in manifest["cases"]:
        if case["source"] != "HTML":
            continue
        fixture = json.loads((FIXTURES / case["fixture"]).read_text())
        assert fixture["provenance"]["kind"] == "live-capture"
        assert fixture["responses"]
