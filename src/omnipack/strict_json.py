"""JSON decoding that refuses to let a repeated object key silently win."""

from __future__ import annotations

from typing import Any


class DuplicateKeyError(ValueError):
    """A JSON object repeats a key, so no single occurrence can be trusted."""

    def __init__(self, key: str) -> None:
        super().__init__(f"duplicate JSON key {key!r}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """An `object_pairs_hook` raising `DuplicateKeyError` on a repeated key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result
