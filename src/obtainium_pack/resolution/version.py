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
_ECMASCRIPT_WHITESPACE = (
    r"\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
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
        return re.compile(_translate_pattern(pattern), re.ASCII)
    except re.error as error:
        raise ResolutionError("regex-invalid", f"invalid regex: {error.msg}") from error


def _translate_pattern(pattern: str) -> str:
    """Translate the supported default ECMAScript character and anchor rules."""
    result: list[str] = []
    in_class = False
    group_captures: list[int] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\" and index + 1 < len(pattern):
            index += 1
            escape = pattern[index]
            if (
                escape.isdigit()
                or escape not in r"dDwWsSbBfnrtvxu^$\.*+?()[]{}|/-"
                or (in_class and escape == "S")
            ):
                raise ResolutionError(
                    "regex-unsupported",
                    "regex uses unsupported escape or pattern backreference",
                )
            if (
                in_class
                and escape in "dDwWsS"
                and (
                    pattern[index - 2 : index - 1] == "-"
                    or pattern[index + 1 : index + 2] == "-"
                )
            ):
                raise ResolutionError(
                    "regex-unsupported",
                    "character-class escapes beside hyphens are unsupported",
                )
            if escape == "s":
                result.append(
                    _ECMASCRIPT_WHITESPACE
                    if in_class
                    else f"[{_ECMASCRIPT_WHITESPACE}]"
                )
            elif escape == "S":
                result.append(f"[^{_ECMASCRIPT_WHITESPACE}]")
            else:
                result.append("\\" + escape)
        elif char == "[" and not in_class:
            in_class = True
            result.append(char)
        elif char == "]" and in_class:
            in_class = False
            result.append(char)
        elif char == "(" and not in_class:
            capturing = pattern[index + 1 : index + 2] != "?"
            if capturing:
                group_captures = [count + 1 for count in group_captures]
            group_captures.append(int(capturing))
            result.append(char)
        elif char == ")" and not in_class:
            if (
                group_captures
                and group_captures.pop()
                and _repeated(pattern[index + 1 :])
            ):
                raise ResolutionError(
                    "regex-unsupported",
                    "repeated groups containing captures are unsupported",
                )
            result.append(char)
        elif char == "." and not in_class:
            result.append(r"[^\n\r\u2028\u2029]")
        elif char == "$" and not in_class:
            result.append(r"\Z")
        else:
            result.append(char)
        index += 1
    return "".join(result)


def _repeated(suffix: str) -> bool:
    if suffix.startswith(("*", "+")):
        return True
    repeat = re.match(r"\{(\d+)(?:,(\d*))?\}", suffix)
    if repeat is None:
        return False
    maximum = repeat[2] if repeat[2] is not None else repeat[1]
    return maximum == "" or int(maximum) > 1


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
