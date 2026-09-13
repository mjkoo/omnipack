"""Hand-written entries from `config/extras.json`."""

from __future__ import annotations

from collections.abc import Sequence

from omnipack.model import App, Variant
from omnipack.sources.common import SourceError, normalize_record

_RETIRED_FIELDS = frozenset({"variants", "dualPreferred"})


def fetch(entries: Sequence[object]) -> list[App]:
    """Return the hand-added entries, normalized.

    An entry is a baseline build, a candidate for both packs, unless it sets
    `dualScreen` to true. That makes it a dual-screen build: a candidate for
    the dual-screen pack only, and preferred there, as every other source marks
    its dual-only builds.
    """
    result: list[App] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise SourceError("extras", f"entry {index} must be an object")
        label = entry.get("name") or entry.get("id") or f"entry {index}"
        retired = _RETIRED_FIELDS & entry.keys()
        if retired:
            raise SourceError(
                "extras", f"entry {label!r} has unknown field {min(retired)!r}"
            )
        dual_screen = entry.get("dualScreen", False)
        if type(dual_screen) is not bool:
            raise SourceError("extras", f"entry {label!r} dualScreen must be boolean")
        result.append(
            normalize_record(
                entry,
                source="extras",
                variant=Variant.DUAL if dual_screen else Variant.SINGLE,
                derive_type=True,
                eligibility=(
                    frozenset({Variant.DUAL}) if dual_screen else frozenset(Variant)
                ),
                dual_preferred=dual_screen,
                origin="extras",
            )
        )
    return result
