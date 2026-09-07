"""Version extraction compatible with the supported Obtainium regex subset."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from .types import ResolutionError

_UNSUPPORTED_PATTERN_PARTS = (
    "(?P<",
    "(?P=",
    "(?#",
    "(?>",
    "(?(",
    "\\A",
    "\\Z",
    "\\z",
    "\\G",
    "\\p{",
    "\\P{",
)
_INLINE_FLAGS = re.compile(r"\(\?[aiLmsux-]+(?:\)|:)")
_DART_NAMED_GROUP = re.compile(r"\(\?<[^=!]")
_POSSESSIVE_QUANTIFIER = re.compile(r"(?:[*+?]|\{\d+(?:,\d*)?\})\+")
_GROUP_REFERENCE = re.compile(r"\$\d+")


def compile_compatible_regex(pattern: str) -> re.Pattern[str]:
    """Compile syntax whose behavior is shared by Dart and Python for this pack."""
    if any(part in pattern for part in _UNSUPPORTED_PATTERN_PARTS):
        raise ResolutionError("regex-unsupported", "regex uses unsupported syntax")
    if (
        _INLINE_FLAGS.search(pattern)
        or _DART_NAMED_GROUP.search(pattern)
        or _POSSESSIVE_QUANTIFIER.search(pattern)
    ):
        raise ResolutionError("regex-unsupported", "regex uses unsupported syntax")
    try:
        return re.compile(pattern, re.ASCII)
    except re.error as error:
        raise ResolutionError("regex-invalid", f"invalid regex: {error.msg}") from error


def extract_version(raw: str, pattern: str, group_template: str | None) -> str:
    """Extract the last match and expand Obtainium-style numeric group references."""
    regex = compile_compatible_regex(pattern)
    matches = list(regex.finditer(raw))
    if not matches:
        raise ResolutionError("regex-no-match", "version regex did not match")

    template = (group_template or "").strip() or "0"
    if template.isdigit():
        template = f"${template}"
    references = list(_GROUP_REFERENCE.finditer(template))
    if not references:
        raise ResolutionError(
            "regex-group-invalid", "version group template has no group reference"
        )

    match = matches[-1]
    output = template
    # Global replacement in template order also affects escaped and inserted text.
    for reference in references:
        token = reference.group(0)
        index = int(token[1:])
        try:
            value = match.group(index) or ""
        except IndexError as error:
            raise ResolutionError(
                "regex-group-invalid", f"version regex has no group {index}"
            ) from error
        escaped = f"\\{token}"
        if escaped in output:
            output = output.replace(escaped, token)
        else:
            output = output.replace(token, value)
    if not output:
        raise ResolutionError(
            "version-empty", "version extraction produced an empty value"
        )
    return output


def parse_timestamp(value: object) -> datetime | None:
    """Parse an ISO-8601 source timestamp, returning UTC when it has no zone."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def epoch_microseconds(value: datetime) -> str:
    """Return exact microseconds since the Unix epoch without float rounding."""
    delta = value - datetime(1970, 1, 1, tzinfo=UTC)
    return str((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds)
