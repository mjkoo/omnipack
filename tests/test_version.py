from __future__ import annotations

import pytest

from obtainium_pack.resolution.types import ResolutionError
from obtainium_pack.resolution.version import extract_version


def test_extracts_last_match_and_defaults_to_group_zero() -> None:
    assert extract_version("old-v1.2 new-v2.3", r"v\d+\.\d+", "") == "v2.3"


@pytest.mark.parametrize("template", ["2", "$2"])
def test_numeric_and_dollar_group_templates_are_equivalent(template: str) -> None:
    assert extract_version("release-12.34", r"(release)-(\d+\.\d+)", template) == (
        "12.34"
    )


def test_concatenates_groups_and_substitutes_unmatched_optional_as_empty() -> None:
    assert extract_version("v1.2", r"v(\d+)\.(\d+)(?:\.(\d+))?", "$1.$2$3") == ("1.2")


def test_escaped_group_reference_remains_literal() -> None:
    assert extract_version("v12", r"v(\d+)", r"\$1") == "$1"


def test_actual_ppsspp_template_selects_groups_from_three_part_path() -> None:
    pattern = (
        r"\/(?:(?:([0-9]+)_([0-9]+)\/ppsspp\.)|"
        r"(?:([0-9]+)_([0-9]+)_([0-9]+)\/ppsspp(\.)))apk$"
    )
    assert (
        extract_version(
            "https://www.ppsspp.org/files/1_18_1/ppsspp.apk",
            pattern,
            "$1$3.$2$4$6$5",
        )
        == "1.18.1"
    )


def test_actual_cocoon_template_concatenates_beta_version() -> None:
    assert extract_version("beta-0.9.2", r"(b)eta-(.*)", "$1$2") == "b0.9.2"


@pytest.mark.parametrize(
    ("pattern", "template", "code"),
    [
        ("(", "0", "regex-invalid"),
        (r"(?P<version>\d+)", "0", "regex-unsupported"),
        (r"(?<version>\d+)", "0", "regex-unsupported"),
        (r"(?i)v(\d+)", "1", "regex-unsupported"),
        (r"v(\d+)", "$2", "regex-group-invalid"),
        (r"v(\d+)", "literal", "regex-group-invalid"),
        (r"v(\d+)", "$1", "regex-no-match"),
        (r"v(\d*)", "$1", "version-empty"),
    ],
)
def test_extraction_failures_have_stable_codes(
    pattern: str, template: str, code: str
) -> None:
    raw = "v" if code in {"regex-no-match", "version-empty"} else "v1"
    if code == "regex-no-match":
        raw = "continuous"
    with pytest.raises(ResolutionError) as raised:
        extract_version(raw, pattern, template)
    assert raised.value.code == code


@pytest.mark.parametrize("template", [r"\$1-$1", r"$1-\$1"])
def test_repeated_reference_globally_expands_after_unescaping(template: str) -> None:
    assert extract_version("v12", r"v(\d+)", template) == "12-12"


@pytest.mark.parametrize(
    ("template", "expected"), [("$1-$10", "a-a0"), ("$10-$1", "j-a")]
)
def test_overlapping_group_references_expand_in_template_order(
    template: str, expected: str
) -> None:
    assert (
        extract_version("abcdefghij", "(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)", template)
        == expected
    )


def test_later_group_reference_expands_text_inserted_by_earlier_group() -> None:
    assert extract_version("$2-b", r"(\$2)-(b)", "$1-$2") == "b-b"


@pytest.mark.parametrize(
    ("raw", "pattern", "expected"),
    [
        ("Version:\u00a01.2", r"Version:\s+(\d+\.\d+)", "1.2"),
        ("Version:\ufeff1.2", r"Version:[\s]+(\d+\.\d+)", "1.2"),
        ("v1.2\rv9.9", r"v(.*)", "9.9"),
        ("v1.2\u2028v9.9", r"v(.*)", "9.9"),
        ("v1.2\u2029v9.9", r"v(.*)", "9.9"),
        ("v1.2", r"v([^\s]+)$", "1.2"),
        ("v.", r"v([.])", "."),
        ("v$", r"v([\$])", "$"),
    ],
)
def test_ecmascript_character_and_line_semantics(raw, pattern, expected) -> None:
    assert extract_version(raw, pattern, "1") == expected


@pytest.mark.parametrize(
    ("raw", "pattern"),
    [("v1.2\n", r"v(\d+\.\d+)$"), ("Version:\x851.2", r"Version:\s+(.*)")],
)
def test_ecmascript_end_anchor_and_whitespace_exclusions(raw, pattern) -> None:
    with pytest.raises(ResolutionError, match="did not match"):
        extract_version(raw, pattern, "1")


@pytest.mark.parametrize("pattern", [r"(x)?v(\d+\.\d+)\1", r"[\1]", r"[\S]", r"\a"])
def test_unsupported_pattern_escapes_are_explicit(pattern) -> None:
    with pytest.raises(ResolutionError) as raised:
        extract_version("v1.2", pattern, "0")
    assert raised.value.code == "regex-unsupported"


@pytest.mark.parametrize(
    ("raw", "pattern", "group"),
    [
        ("v\uff10", r"v([\s-\uffff]+)", "1"),
        ("v\x01", r"v([\x00-\s]+)", "1"),
        ("ba", r"(a|(b))+", "2"),
        ("ba", r"(?:a|(b)){2}", "1"),
        ("a", r"(a|)+", "1"),
    ],
)
def test_incompatible_class_ranges_and_repeated_captures_are_rejected(
    raw: str, pattern: str, group: str
) -> None:
    with pytest.raises(ResolutionError) as raised:
        extract_version(raw, pattern, group)
    assert raised.value.code == "regex-unsupported"


def test_repeated_noncapturing_groups_preserve_supported_version_capture() -> None:
    assert extract_version("foobar12", r"(?:foo|bar)+(\d+)", "1") == "12"


@pytest.mark.parametrize("pattern", [r"([]1])", r"([^]2])"])
def test_leading_unescaped_closing_bracket_is_explicitly_unsupported(
    pattern: str,
) -> None:
    with pytest.raises(ResolutionError) as raised:
        extract_version("1", pattern, "1")
    assert raised.value.code == "regex-unsupported"


def test_escaped_closing_bracket_remains_supported_in_character_class() -> None:
    assert extract_version("]1", r"([\]1]+)", "1") == "]1"
