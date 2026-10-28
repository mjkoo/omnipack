from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack.archive.targets import (
    ArchiveTarget,
    SkipReason,
    select_targets,
    source_key,
)
from omnipack.model import SourceType

TRACK_ONLY = json.dumps({"trackOnly": True})


def entry(
    url: str,
    *,
    source: str | None = "GitHub",
    settings: object = "{}",
    name: str = "Fixture",
) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "fixture",
        "name": name,
        "url": url,
        "additionalSettings": settings,
    }
    if source is not None:
        data["overrideSource"] = source
    return data


def write_packs(
    root: Path,
    single: list[dict[str, object]],
    dual: list[dict[str, object]] | None = None,
) -> None:
    (root / "dist").mkdir(exist_ok=True)
    for name, apps in (("single-screen.json", single), ("dual-screen.json", dual)):
        (root / "dist" / name).write_text(
            json.dumps({"settings": {}, "apps": apps or []})
        )


def by_key(targets: list[ArchiveTarget]) -> dict[str, ArchiveTarget]:
    return {target.key: target for target in targets}


def test_an_app_in_both_packs_is_one_target_with_its_single_screen_entry(
    tmp_path: Path,
) -> None:
    write_packs(
        tmp_path,
        [entry("https://github.com/Owner/Repo", name="single")],
        [entry("https://github.com/owner/repo/", name="dual")],
    )

    (target,) = select_targets(tmp_path)

    assert target.key == "github.com/owner/repo"
    assert target.entry["name"] == "single"
    assert target.source is SourceType.GITHUB
    assert target.skip is None


def test_a_track_only_entry_is_skipped(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://github.com/owner/repo", settings=TRACK_ONLY)])

    (target,) = select_targets(tmp_path)

    assert target.skip is SkipReason.TRACK_ONLY


def test_an_unsupported_source_is_skipped(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://codeberg.org/owner/repo", source="Codeberg")])

    (target,) = select_targets(tmp_path)

    assert target.skip is SkipReason.UNSUPPORTED_SOURCE
    assert target.source is None


def test_html_keys_are_prefixed(tmp_path: Path) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://www.ppsspp.org/download", source="HTML"),
            entry("https://gitlab.com/group/project", source="GitLab"),
        ],
    )

    keys = by_key(select_targets(tmp_path))

    assert keys["html/ppsspp.org/download"].source is SourceType.HTML
    assert keys["gitlab.com/group/project"].source is SourceType.GITLAB


@pytest.mark.parametrize(
    ("url", "source"),
    [
        ("https://github.com/owner/repo", SourceType.GITHUB),
        ("https://www.github.com/owner/repo", SourceType.GITHUB),
        ("https://gitlab.com/group/project", SourceType.GITLAB),
    ],
)
def test_an_entry_without_an_override_is_classified_by_its_host(
    tmp_path: Path, url: str, source: SourceType
) -> None:
    write_packs(tmp_path, [entry(url, source=None)])

    (target,) = select_targets(tmp_path)

    assert target.source is source
    assert target.skip is None


def test_an_entry_without_an_override_on_an_unrecognised_host_is_not_html(
    tmp_path: Path,
) -> None:
    write_packs(tmp_path, [entry("https://example.com/downloads", source=None)])

    (target,) = select_targets(tmp_path)

    assert target.source is None
    assert target.skip is SkipReason.UNSUPPORTED_SOURCE


def test_an_override_wins_over_the_host(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://github.com/owner/repo", source="HTML")])

    (target,) = select_targets(tmp_path)

    assert target.source is SourceType.HTML
    assert target.key == "html/github.com/owner/repo"


def test_malformed_settings_do_not_hide_a_target(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://github.com/owner/repo", settings="{")])

    (target,) = select_targets(tmp_path)

    assert target.skip is None


@pytest.mark.parametrize(
    ("url", "key"),
    [
        (
            "https://example.com/dl?file=a b&x=1#top",
            "html/example.com/dl%3Ffile%3Da%20b%26x%3D1%23top",
        ),
        ("https://example.com:8080/a", "html/example.com%3A8080/a"),
        ("https://example.com/../x", "html/example.com/%2E%2E/x"),
        ("https://example.com/a//b", "html/example.com/a/%2F/b"),
        ("https://example.com/100%25", "html/example.com/100%2525"),
    ],
)
def test_html_source_keys_are_safe_path_segments(url: str, key: str) -> None:
    assert source_key(url, SourceType.HTML) == key


def test_source_keys_are_deterministic_and_bounded() -> None:
    url = "https://example.com/" + "a" * 2000

    first = source_key(url, SourceType.HTML)

    assert first == source_key(url, SourceType.HTML)
    assert len(first) <= 600
    assert first != source_key(url + "b", SourceType.HTML)
    assert first.isascii()
