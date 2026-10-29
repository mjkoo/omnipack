"""Choose the release Obtainium would show for a GitHub or GitLab entry.

This is the shared core of the forge resolvers and of the update-health
lookup: it orders a project's releases, applies an entry's filters and
yields the first release that qualifies, then computes the version string
Obtainium displays. See the package docstring for the upstream commit.

Not ported: the minimum update age (a global app setting the packs do not
carry), tarball assets, draft releases and the device-specific architecture
filter.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import cache, cmp_to_key
from typing import Any

APK_SUFFIXES = (".apk", ".xapk", ".apkm", ".apks")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)


class SettingsError(ValueError):
    """An entry's `additionalSettings` cannot be used."""


class VersionError(ValueError):
    """A release has no version, or the entry's extraction matches nothing."""


class SortMethod(StrEnum):
    """How Obtainium orders a project's releases (`sortMethodChoice`)."""

    DATE = "date"
    NAME = "name"
    SMARTNAME = "smartname"
    SMARTNAME_DATE = "smartname-datefallback"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ReleaseSettings:
    """The `additionalSettings` that decide which release is selected and
    what its version reads, as Obtainium reads them. Defaults are
    Obtainium's, so a caller that needs fewer settings sets only those."""

    include_prereleases: bool = False
    include_zips: bool = False
    fallback_to_older: bool = False
    track_only: bool = False
    title_filter: re.Pattern[str] | None = None
    invert_title_filter: bool = False
    notes_filter: re.Pattern[str] | None = None
    invert_notes_filter: bool = False
    apk_filter: re.Pattern[str] | None = None
    invert_apk_filter: bool = False
    sort_method: SortMethod = SortMethod.SMARTNAME_DATE
    use_latest_asset_date: bool = False
    verify_latest_tag: bool = False
    release_title_as_version: bool = False
    version_regex: re.Pattern[str] | None = None
    match_group: str = ""
    release_date_as_version: bool = False

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> ReleaseSettings:
        """Read a decoded `additionalSettings` object, raising `SettingsError`
        for a pattern that does not compile or an unknown sort method."""
        sort = options.get("sortMethodChoice", SortMethod.SMARTNAME_DATE)
        try:
            sort_method = SortMethod(sort)
        except ValueError as error:
            raise SettingsError(f"unknown sortMethodChoice: {sort!r}") from error
        match_group = options.get("matchGroupToUse")
        return cls(
            include_prereleases=options.get("includePrereleases") is True,
            include_zips=options.get("includeZips") is True,
            fallback_to_older=options.get("fallbackToOlderReleases") is True,
            track_only=options.get("trackOnly") is True,
            title_filter=pattern(options, "filterReleaseTitlesByRegEx"),
            invert_title_filter=options.get("invertReleaseTitlesFilter") is True,
            notes_filter=pattern(options, "filterReleaseNotesByRegEx"),
            invert_notes_filter=options.get("invertReleaseNotesFilter") is True,
            apk_filter=pattern(options, "apkFilterRegEx"),
            invert_apk_filter=options.get("invertAPKFilter") is True,
            sort_method=sort_method,
            use_latest_asset_date=options.get("useLatestAssetDateAsReleaseDate")
            is True,
            verify_latest_tag=options.get("verifyLatestTag") is True,
            release_title_as_version=options.get("releaseTitleAsVersion") is True,
            version_regex=pattern(options, "versionExtractionRegEx"),
            match_group=match_group if isinstance(match_group, str) else "",
            release_date_as_version=options.get("releaseDateAsVersion") is True,
        )


def pattern(options: Mapping[str, Any], key: str) -> re.Pattern[str] | None:
    """The compiled pattern an option holds, None when it is unset or empty."""
    value = options.get(key)
    if not isinstance(value, str) or not value:
        return None
    try:
        return re.compile(value)
    except re.error as error:
        raise SettingsError(f"{key} is not a valid pattern: {error}") from error


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """A file attached to a release. `installable` marks an APK or container
    the source would offer; `updated` is read only when the entry dates a
    release by its assets."""

    name: str
    installable: bool
    updated: datetime | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    """One release as a source reports it, normalized for selection.

    `published` is None for a release that cannot be selected anyway, such as
    a draft. `record` is the source's own JSON for the release.
    """

    tag: str | None
    title: str | None
    notes: str
    published: datetime | None
    prerelease: bool
    draft: bool
    assets: tuple[ReleaseAsset, ...]
    record: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Selected:
    """The chosen release: its title (or tag, when untitled), the installable
    assets that passed the APK filter and the date Obtainium shows for it."""

    candidate: Candidate
    name: str
    installable: tuple[ReleaseAsset, ...]
    date: datetime | None


def is_installable(name: str, *, include_zips: bool = False) -> bool:
    """Whether a file name is an APK, an APK container or, when the entry
    includes zips, a zip archive."""
    suffixes = APK_SUFFIXES + ((".zip",) if include_zips else ())
    return name.lower().endswith(suffixes)


def select_release(
    candidates: Sequence[Candidate],
    settings: ReleaseSettings,
    *,
    latest: Candidate | None = None,
    date_by_all_assets: bool = False,
) -> Selected | None:
    """The release Obtainium selects, or None when none qualifies.

    `candidates` are in the order the source lists them, newest first.
    `latest` is the source's own latest release, given when the entry
    verifies it: it joins the list if absent and then ranks newest. A release
    dated by its assets takes Obtainium's date, the newest installable asset
    that passed the filter, unless `date_by_all_assets` asks for the newest of
    all its assets.
    """
    releases = list(candidates)
    if latest is not None and not any(_key(r) == _key(latest) for r in releases):
        releases.insert(0, latest)
    # Obtainium sorts oldest first and walks the list from the end.
    if settings.sort_method is SortMethod.NONE:
        releases.reverse()
    else:
        releases.sort(key=cmp_to_key(_comparator(settings)))
    _rank_latest(releases, latest)
    releases.reverse()

    skipped = 0
    for index, release in enumerate(releases):
        if not settings.fallback_to_older and index > skipped:
            break
        if release.draft or (release.prerelease and not settings.include_prereleases):
            skipped += 1
            continue
        name = (
            release.title if release.title and release.title.strip() else release.tag
        ) or ""
        if settings.title_filter and not passes(
            settings.title_filter, name.strip(), settings.invert_title_filter
        ):
            continue
        if settings.notes_filter and not passes(
            settings.notes_filter, release.notes.strip(), settings.invert_notes_filter
        ):
            continue
        installable = tuple(a for a in release.assets if a.installable)
        passing = tuple(
            a
            for a in installable
            if settings.apk_filter is None
            or passes(settings.apk_filter, a.name, settings.invert_apk_filter)
        )
        if not passing and not settings.track_only:
            continue
        return Selected(
            release,
            name,
            passing,
            release_date(release, settings, () if date_by_all_assets else passing),
        )
    return None


def release_date(
    release: Candidate,
    settings: ReleaseSettings,
    assets: Sequence[ReleaseAsset] = (),
) -> datetime | None:
    """The date Obtainium shows for a release: its publication, or with
    `useLatestAssetDateAsReleaseDate` the newest date among `assets` (all the
    release's when none are given). A release without asset dates is dated by
    its publication."""
    if settings.use_latest_asset_date:
        dates = [a.updated for a in assets or release.assets if a.updated]
        if dates:
            return max(dates)
    return release.published


def release_version(selected: Selected, settings: ReleaseSettings) -> str:
    """The version string Obtainium displays for the selected release.

    Raises `VersionError` when the release has no version or the entry's
    extraction pattern matches nothing.
    """
    release = selected.candidate
    if settings.release_title_as_version:
        version = selected.name
    else:
        version = release.tag if release.tag is not None else release.title
    if not version:
        raise VersionError("release has neither a tag nor a title")
    if settings.version_regex is not None:
        version = extract_version(settings.version_regex, settings.match_group, version)
    if settings.release_date_as_version and selected.date is not None:
        version = str((selected.date.astimezone(UTC) - _EPOCH) // _MICROSECOND)
    return version


def extract_version(regex: re.Pattern[str], match_group: str, text: str) -> str:
    """Apply an entry's extraction pattern as Obtainium does: the last match
    of `regex` in `text`, rendered through `match_group`, a template whose
    `$N` references are replaced by the match's groups (a bare number `N`
    means `$N`, an empty template means `$0`)."""
    matches = list(regex.finditer(text))
    if not matches:
        raise VersionError(f"version pattern {regex.pattern!r} matches nothing")
    template = match_group.strip() or "0"
    if re.fullmatch(r"[0-9]+", template):
        template = f"${template}"
    references = re.findall(r"\$[0-9]+", template)
    if not references:
        raise VersionError("version template has no group reference")
    result = template
    for reference in references:
        try:
            group = matches[-1].group(int(reference[1:])) or ""
        except IndexError as error:
            raise VersionError(f"version pattern has no group {reference}") from error
        # A backslash before a reference keeps it literal.
        if f"\\{reference}" in result:
            result = result.replace(f"\\{reference}", reference)
        else:
            result = result.replace(reference, group)
    if not result:
        raise VersionError("version template yields nothing")
    return result


def compare_alphanumeric(a: str, b: str) -> int:
    """Order two strings with digit runs compared as numbers, as Obtainium
    does; a digit run sorts after text."""
    parts_a = re.findall(r"[0-9]+|[^0-9]+", a)
    parts_b = re.findall(r"[0-9]+|[^0-9]+", b)
    for part_a, part_b in zip(parts_a, parts_b, strict=False):
        number_a, number_b = part_a[0] in "0123456789", part_b[0] in "0123456789"
        if number_a and number_b:
            result = _cmp(int(part_a), int(part_b))
        elif not number_a and not number_b:
            result = _cmp(part_a, part_b)
        else:
            return 1 if number_a else -1
        if result:
            return result
    return _cmp(len(parts_a), len(parts_b))


def _cmp(a: Any, b: Any) -> int:
    return (a > b) - (a < b)


def _key(release: Candidate) -> str | None:
    return release.tag if release.tag is not None else release.title


def passes(regex: re.Pattern[str], value: str, invert: bool) -> bool:
    """Whether `value` passes a filter: it matches `regex`, or with `invert`
    it does not."""
    return (regex.search(value) is not None) != invert


def _rank_latest(releases: list[Candidate], latest: Candidate | None) -> None:
    """Move the verified latest release to the end, where the newest sits."""
    if latest is None or _key(latest) is None or not releases:
        return
    if _key(latest) == _key(releases[-1]):
        return
    for index, release in enumerate(releases):
        if _key(release) == _key(latest):
            releases.append(releases.pop(index))
            return


def _comparator(settings: ReleaseSettings) -> Callable[[Candidate, Candidate], int]:
    method = settings.sort_method

    def by_date(a: Candidate, b: Candidate) -> int:
        date_a = release_date(a, settings) or _EPOCH
        date_b = release_date(b, settings) or _EPOCH
        return _cmp(date_a, date_b)

    def compare(a: Candidate, b: Candidate) -> int:
        if method is SortMethod.DATE:
            return by_date(a, b)
        name_a, name_b = _key(a) or a.title or "", _key(b) or b.title or ""
        shared = _standard_formats(name_a) & _standard_formats(name_b)
        if method is SortMethod.SMARTNAME_DATE and not shared:
            return by_date(a, b)
        if method is not SortMethod.NAME and shared:
            # The longest shared shape is the most specific one.
            shape = re.compile(max(sorted(shared), key=len))
            match_a, match_b = shape.search(name_a), shape.search(name_b)
            if match_a and match_b:
                return compare_alphanumeric(match_a.group(), match_b.group())
        return compare_alphanumeric(name_a, name_b)

    return compare


@cache
def _standard_patterns() -> tuple[re.Pattern[str], ...]:
    """The version shapes Obtainium can order: a numeric core, optionally
    with a pre-release qualifier and a trailing build number."""
    basics = [
        "[0-9]+",
        "[0-9]+\\.[0-9]+",
        "[0-9]+\\.[0-9]+\\.[0-9]+",
        "[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+",
    ]
    separators = ["-", "\\+"]
    suffixes = ["alpha", "beta", "rc", "pre", "dev", "snapshot", "nightly", "ose"]
    suffixes.append("[0-9]+")
    builds = ["\\+[0-9]+", "[0-9]+"]
    shapes: set[str] = set()
    for basic in basics:
        shapes.add(basic)
        for separator in separators:
            for suffix in suffixes:
                shapes.add(f"{basic}{suffix}")
                shapes.add(f"{basic}{separator}{suffix}")
                for build in builds:
                    shapes.add(f"{basic}{suffix}{build}")
                    shapes.add(f"{basic}{separator}{suffix}{build}")
    return tuple(re.compile(shape) for shape in sorted(shapes))


@cache
def _standard_formats(version: str) -> frozenset[str]:
    return frozenset(p.pattern for p in _standard_patterns() if p.search(version))
