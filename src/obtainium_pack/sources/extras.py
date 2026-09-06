"""Hand-written entries from `config/extras.json`."""

from __future__ import annotations

from collections.abc import Sequence

from obtainium_pack.model import App, Variant
from obtainium_pack.sources.common import SourceError, normalize_record


def fetch(entries: Sequence[object]) -> list[App]:
    """Return the hand-added entries, normalized."""
    result: list[App] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise SourceError("extras", f"entry {index} must be an object")
        label = entry.get("name") or entry.get("id") or f"entry {index}"
        variants = entry.get("variants", [variant.value for variant in Variant])
        if not isinstance(variants, list):
            raise SourceError("extras", f"entry {label!r} variants must be a list")
        for value in variants:
            try:
                variant = Variant(value)
            except (TypeError, ValueError) as error:
                raise SourceError(
                    "extras", f"entry {label!r} has unknown variant {value!r}"
                ) from error
            result.append(
                normalize_record(
                    entry, source="extras", variant=variant, derive_type=True
                )
            )
    return result
