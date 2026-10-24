"""Apply build-bound JSON Merge Patch overlays to composed imports."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from omnipack.urls import normalize_project_url, parse_project_url


class OverlayError(ValueError):
    """An overlay cannot be applied to the composed pack."""


@dataclass(frozen=True, slots=True)
class ComposedApp:
    """A selected entry: its app family and the import data rendered for it."""

    family: str
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def url(self) -> str:
        return self.data["url"]


@dataclass(frozen=True, slots=True)
class OverlayPatch:
    """A patch for every selected entry at one normalized project URL."""

    url: str
    patch: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RedundantOverlayKeys:
    """An overlay record's patch keys that change no published entry.

    Each key is the dotted path to a leaf of the patch, the keys along it
    joined with `.`.
    """

    url: str
    keys: tuple[str, ...]


# Fields only the source, composition and the category map decide.
PROTECTED_FIELDS = frozenset(
    {"url", "overrideSource", "family", "variant", "categories"}
)


def _record_context(record: dict[str, Any]) -> str:
    """Name the record's URL when it normalizes, so an error names what to look for.

    The index alone sends a maintainer counting records. A URL that does not
    normalize is left out and reported by the validation that follows.
    """
    url = record.get("url")
    if isinstance(url, str) and url.strip():
        try:
            return f" (url {normalize_project_url(url)!r})"
        except ValueError:
            pass
    return ""


def parse_overlay(document: object, label: str) -> tuple[OverlayPatch, ...]:
    if not isinstance(document, list):
        raise OverlayError(f"{label} must be an array of URL patch records")
    result: list[OverlayPatch] = []
    indexes: dict[str, int] = {}
    for index, value in enumerate(document):
        item_label = f"{label}[{index}]"
        if not isinstance(value, dict):
            raise OverlayError(f"{item_label} must be an object")
        context = _record_context(value)
        unknown = set(value) - {"url", "patch"}
        if unknown:
            raise OverlayError(
                f"{item_label} has unknown field {min(unknown)!r}{context}"
            )
        url, patch = value.get("url"), value.get("patch")
        if not isinstance(url, str) or not url.strip():
            raise OverlayError(f"{item_label}.url must be a nonempty project URL")
        try:
            url = parse_project_url(url)
        except ValueError as error:
            raise OverlayError(
                f"{item_label}.url is not a project URL: {url!r}"
            ) from error
        if not isinstance(patch, dict):
            raise OverlayError(f"{item_label}.patch must be an object{context}")
        protected = PROTECTED_FIELDS.intersection(patch)
        if protected:
            raise OverlayError(
                f"{item_label}.patch for {url!r} contains protected field "
                f"{min(protected)}"
            )
        if "id" in patch and (
            not isinstance(patch["id"], str) or not patch["id"].strip()
        ):
            raise OverlayError(
                f"{item_label}.patch for {url!r} must set id to a nonempty string"
            )
        _check_patch_keys(patch, f"{item_label}.patch for {url!r}")
        if url in indexes:
            raise OverlayError(
                f"{item_label} names the same project URL {url!r} as "
                f"{label}[{indexes[url]}]"
            )
        indexes[url] = index
        result.append(OverlayPatch(url, deepcopy(patch)))
    return tuple(result)


def _check_patch_keys(
    patch: dict[str, Any], label: str, path: tuple[str, ...] = ()
) -> None:
    """Refuse keys a dotted path cannot name, and objects that patch nothing.

    A patch key is reported by its dotted path, and that path is joined to a
    project URL with `/` in an alert key, so a key holding either character
    would let two locations share one name. An empty object has no key to
    judge: a record whose last live key was deleted is removed, not left in
    place. Arrays are values, so keys inside them are not checked.
    """
    if not patch:
        where = f" under {'.'.join(path)!r}" if path else ""
        raise OverlayError(f"{label} patches nothing{where}")
    for key, value in patch.items():
        if "." in key or "/" in key:
            raise OverlayError(f"{label} has key {key!r} containing '.' or '/'")
        if isinstance(value, dict):
            _check_patch_keys(value, label, (*path, key))


def merge_patch(target: object, patch: object) -> object:
    if not isinstance(patch, dict):
        return deepcopy(patch)
    result: dict[str, Any] = deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def apply_overlay(
    apps: list[ComposedApp], overlay: tuple[OverlayPatch, ...]
) -> list[ComposedApp]:
    patches = {item.url: item.patch for item in overlay}
    result: list[ComposedApp] = []
    for app in apps:
        data = deepcopy(app.data)
        patch = patches.get(normalize_project_url(app.url))
        if patch is not None:
            patched = merge_patch(data, patch)
            assert isinstance(patched, dict)
            data = patched
        result.append(ComposedApp(app.family, data))
    return result


def redundant_overlay_keys(
    apps: Iterable[ComposedApp],
    overlay: tuple[OverlayPatch, ...],
    published_form: Callable[[ComposedApp], object],
) -> list[RedundantOverlayKeys]:
    """Each record's keys that leave every targeted entry's published form as is.

    `apps` are the selected entries of every variant before overlays apply,
    and `published_form` renders one entry as a pack publishes it, raising
    ValueError when it cannot. Each leaf of a record's patch (any value that
    is not an object; an array counts whole) is merged alone into each entry
    the record targets, and it changes nothing when the published forms with
    and without it are equal for every target. A null is judged the same way,
    so deleting an absent key or a defaulted setting changes nothing. A leaf
    whose patched entry cannot be published counts as changing it, so this
    never raises; the build's own rendering reports that error.
    """
    targets: dict[str, list[ComposedApp]] = {}
    for app in apps:
        targets.setdefault(normalize_project_url(app.url), []).append(app)
    result: list[RedundantOverlayKeys] = []
    for record in overlay:
        entries = targets.get(record.url)
        if not entries:
            continue
        try:
            baselines = [published_form(app) for app in entries]
        except ValueError:
            continue
        keys = tuple(
            sorted(
                ".".join(path)
                for path, value in _leaves(record.patch)
                if all(
                    _unchanged(app, baseline, _leaf_patch(path, value), published_form)
                    for app, baseline in zip(entries, baselines, strict=True)
                )
            )
        )
        if keys:
            result.append(RedundantOverlayKeys(record.url, keys))
    result.sort(key=lambda item: item.url)
    return result


def _leaves(
    patch: dict[str, Any], path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    for key, value in patch.items():
        if isinstance(value, dict):
            yield from _leaves(value, (*path, key))
        else:
            yield (*path, key), value


def _leaf_patch(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    """A patch holding `value` alone at `path`."""
    patch: Any = value
    for key in reversed(path):
        patch = {key: patch}
    return patch


def _unchanged(
    app: ComposedApp,
    baseline: object,
    patch: dict[str, Any],
    published_form: Callable[[ComposedApp], object],
) -> bool:
    patched = merge_patch(app.data, patch)
    assert isinstance(patched, dict)
    try:
        return published_form(ComposedApp(app.family, patched)) == baseline
    except ValueError:
        return False
