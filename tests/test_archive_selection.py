from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from omnipack.archive.selection import (
    Candidate,
    ReleaseAsset,
    ReleaseSettings,
    SettingsError,
    SortMethod,
    VersionError,
    compare_alphanumeric,
    extract_version,
    is_installable,
    release_version,
    select_release,
)

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def asset(name: str, days: float = 0) -> ReleaseAsset:
    return ReleaseAsset(name, is_installable(name), BASE + timedelta(days=days))


def release(
    tag: str,
    days: float,
    *assets: ReleaseAsset,
    title: str | None = None,
    notes: str = "",
    prerelease: bool = False,
    draft: bool = False,
) -> Candidate:
    return Candidate(
        tag=tag,
        title=title,
        notes=notes,
        published=BASE + timedelta(days=days),
        prerelease=prerelease,
        draft=draft,
        assets=assets or (asset("app.apk", days),),
        record={"tag_name": tag},
    )


def settings(**values: Any) -> ReleaseSettings:
    return ReleaseSettings(sort_method=SortMethod.DATE, **values)


def chosen(candidates: list[Candidate], configured: ReleaseSettings, **kw: Any) -> Any:
    selected = select_release(candidates, configured, **kw)
    return None if selected is None else selected.candidate.tag


def test_drafts_and_excluded_prereleases_are_passed_over_even_without_fallback() -> (
    None
):
    releases = [
        release("v3", 3, draft=True),
        release("v2", 2, prerelease=True),
        release("v1", 1),
    ]

    assert chosen(releases, settings()) == "v1"
    assert chosen(releases, settings(include_prereleases=True)) == "v2"


def test_without_fallback_only_the_first_unexcluded_release_is_tried() -> None:
    releases = [release("v2", 2, asset("notes.txt")), release("v1", 1)]

    assert chosen(releases, settings()) is None
    assert chosen(releases, settings(fallback_to_older=True)) == "v1"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (settings(title_filter=re.compile("^Stable")), "v1"),
        (settings(title_filter=re.compile("^Stable"), invert_title_filter=True), "v2"),
        (settings(notes_filter=re.compile("keep")), "v2"),
        (settings(notes_filter=re.compile("keep"), invert_notes_filter=True), "v1"),
        (settings(apk_filter=re.compile("arm64")), "v1"),
        (settings(apk_filter=re.compile("arm64"), invert_apk_filter=True), "v2"),
    ],
)
def test_title_notes_and_apk_filters_decide_which_release_qualifies(
    configured: ReleaseSettings, expected: str
) -> None:
    releases = [
        release("v2", 2, asset("app-x86.apk"), title="Nightly 2", notes="keep"),
        release("v1", 1, asset("app-arm64.apk"), title="Stable 1", notes="drop"),
    ]

    assert chosen(releases, replace(configured, fallback_to_older=True)) == expected


def test_an_untitled_release_is_filtered_by_its_tag() -> None:
    releases = [release("nightly", 2, title="  "), release("v1", 1)]
    configured = settings(title_filter=re.compile("^v"), fallback_to_older=True)

    assert chosen(releases, configured) == "v1"


def test_a_track_only_entry_needs_no_apk() -> None:
    assert (
        chosen([release("v1", 1, asset("app.exe"))], settings(track_only=True)) == "v1"
    )


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (SortMethod.DATE, "v9"),
        (SortMethod.NONE, "v10"),
        (SortMethod.NAME, "v10"),
        (SortMethod.SMARTNAME, "v10"),
        (SortMethod.SMARTNAME_DATE, "v10"),
    ],
)
def test_sort_method_orders_the_releases(method: SortMethod, expected: str) -> None:
    # Listed newest first, but v9 was published after v10.
    releases = [release("v10", 1), release("v9", 2)]

    assert chosen(releases, ReleaseSettings(sort_method=method)) == expected


def test_smartname_falls_back_to_dates_when_tags_share_no_shape() -> None:
    releases = [release("alpha-build", 1), release("zulu-build", 2)]
    by_date = ReleaseSettings(sort_method=SortMethod.SMARTNAME_DATE)
    by_name = ReleaseSettings(sort_method=SortMethod.NAME)

    assert chosen(releases, by_date) == "zulu-build"
    assert chosen(list(reversed(releases)), by_name) == "zulu-build"


def test_dating_by_assets_reorders_a_rolling_release() -> None:
    rolling = release("latest", 1, asset("app.apk", 30))
    plain = release("v2", 10)

    assert chosen([rolling, plain], settings()) == "v2"
    assert chosen([rolling, plain], settings(use_latest_asset_date=True)) == "latest"


def test_the_date_shown_follows_the_filtered_assets() -> None:
    rolling = release("latest", 1, asset("app.apk", 5), asset("sums.txt", 30))
    configured = settings(use_latest_asset_date=True)

    selected = select_release([rolling], configured)

    assert selected is not None
    assert selected.date == BASE + timedelta(days=5)


def test_a_verified_latest_release_ranks_newest_and_joins_the_list() -> None:
    releases = [release("v2", 2), release("v1", 1)]
    latest = release("v1", 1)
    outside = release("v0", 0)

    assert chosen(releases, settings(), latest=latest) == "v1"
    assert chosen(releases, settings(), latest=outside) == "v0"


@pytest.mark.parametrize(
    ("configured", "version"),
    [
        (ReleaseSettings(), "v1.2"),
        (ReleaseSettings(release_title_as_version=True), "Title 1.2"),
        (ReleaseSettings(version_regex=re.compile(r"v?(.+)"), match_group="$1"), "1.2"),
        (ReleaseSettings(version_regex=re.compile(r"[0-9]+$")), "2"),
        (
            ReleaseSettings(
                release_title_as_version=True,
                version_regex=re.compile(r"(\w+) ([0-9.]+)"),
                match_group="$2-$1",
            ),
            "1.2-Title",
        ),
        (ReleaseSettings(release_date_as_version=True), "1767312000000000"),
    ],
)
def test_the_version_follows_title_extraction_and_date_settings(
    configured: ReleaseSettings, version: str
) -> None:
    candidate = release("v1.2", 1, title="Title 1.2")
    selected = select_release(
        [candidate], replace(configured, sort_method=SortMethod.NONE)
    )
    assert selected is not None

    assert release_version(selected, configured) == version


@pytest.mark.parametrize(
    ("pattern", "group", "text", "expected"),
    [
        (r"(\d+)\.(\d+)", "$1.$2", "x 1.2 and 3.4", "3.4"),
        (r"(\d+)", "", "a1b22", "22"),
        (r"(\d+)", "1", "a1b22", "22"),
        (r"(b)eta-(.*)", "$1-vanilla", "beta-9", "b-vanilla"),
        (r"(\d+)", r"\$1", "7", "$1"),
        (r"(a)|(b)", "$2$1", "a", "a"),
    ],
)
def test_extraction_renders_the_last_match_through_the_group_template(
    pattern: str, group: str, text: str, expected: str
) -> None:
    assert extract_version(re.compile(pattern), group, text) == expected


@pytest.mark.parametrize(
    ("pattern", "group", "text"),
    [
        (r"\d+", "", "none"),
        (r"\d+", "text", "1"),
        (r"(\d+)", "$3", "1"),
        (r"()", "$1", "x"),
    ],
)
def test_extraction_that_yields_nothing_is_an_error(
    pattern: str, group: str, text: str
) -> None:
    with pytest.raises(VersionError):
        extract_version(re.compile(pattern), group, text)


def test_a_release_with_no_tag_or_title_has_no_version() -> None:
    candidate = replace(release("x", 1), tag=None, title=None)
    selected = select_release([candidate], settings())
    assert selected is not None

    with pytest.raises(VersionError):
        release_version(selected, settings())


@pytest.mark.parametrize(
    ("a", "b", "sign"),
    [("v2", "v10", -1), ("v10", "v10", 0), ("1.2.3", "1.2", 1), ("a", "1", -1)],
)
def test_alphanumeric_comparison_reads_digit_runs_as_numbers(
    a: str, b: str, sign: int
) -> None:
    assert compare_alphanumeric(a, b) == sign


def test_options_are_read_as_obtainium_reads_them() -> None:
    parsed = ReleaseSettings.from_options(
        {
            "includePrereleases": True,
            "fallbackToOlderReleases": "yes",
            "filterReleaseTitlesByRegEx": "^v",
            "apkFilterRegEx": "",
            "sortMethodChoice": "none",
            "matchGroupToUse": "$1",
        }
    )

    assert parsed.include_prereleases is True
    assert parsed.fallback_to_older is False
    assert parsed.title_filter is not None and parsed.apk_filter is None
    assert parsed.sort_method is SortMethod.NONE
    assert ReleaseSettings.from_options({}).sort_method is SortMethod.SMARTNAME_DATE


@pytest.mark.parametrize(
    "options", [{"apkFilterRegEx": "("}, {"sortMethodChoice": "newest"}]
)
def test_unusable_options_are_a_settings_error(options: dict[str, Any]) -> None:
    with pytest.raises(SettingsError):
        ReleaseSettings.from_options(options)
