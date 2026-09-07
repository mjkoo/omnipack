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
