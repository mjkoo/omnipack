"""Tests for the findings model, validation and issue reconciliation.

This file imports only the standard library, pytest and the modules under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import alerts as alerts_module
from scripts.alerts import (
    BODY_LIMIT,
    CHECK_STEPS,
    KEY_LIMIT,
    LIVE_CHECK,
    NIGHTLY_PREPARE,
    NIGHTLY_PUBLISH,
    OWNERS,
    RELEASE_ARCHIVE,
    TITLE_LIMIT,
    Finding,
    FindingsFile,
    Owner,
    Producer,
    ReconcileFailure,
    build_body,
    early_failure_finding,
    early_failure_key,
    emit,
    encode_subject,
    marker_line,
    parse_findings,
    parse_owner,
    reconcile,
    subject_key,
    truncate_title,
)
from scripts.workflow_support import SOURCE_NAMES, VALIDATION_STEPS, StepOutcome
from tests.publication_support import (
    ISSUE_LISTING,
    REPOSITORY,
    RUN_1,
    RUN_2,
    CommandResult,
    FakeGh,
    alert_gh,
    alert_issue,
    failure,
    issue_writes,
)

CODM_CHECK = Owner("check", "codm")
CODM_PUBLISH = Owner("publish", "codm")
QUIVER_CHECK = Owner("check", "quiver")
QUIVER_PUBLISH = Owner("publish", "quiver")
CODM_STEP = "codm/check/verify"
NIGHTLY_STAGE = "nightly/prepare/build"


def _file(
    tmp_path: Path,
    owner: Owner,
    *,
    scope: tuple[str, ...] = (),
    unchecked: tuple[str, ...] = (),
    findings: tuple[Finding, ...] = (),
    name: str | None = None,
) -> Path:
    path = tmp_path / (name or f"{owner.value}.json")
    path.write_text(FindingsFile(owner, scope, unchecked, findings).to_json())
    return path


def _run(
    gh: FakeGh,
    *producers: Producer,
    url: str = RUN_2,
) -> alerts_module.ReconcileSummary:
    return reconcile(gh, producers, repository=REPOSITORY, url=url)


def _nightly(path: Path, result: StepOutcome | None = "success") -> Producer:
    return Producer(NIGHTLY_PREPARE, path, result)


def _bodies(gh: FakeGh, verb: str) -> list[str]:
    return gh.texts_for(("issue", verb), "--body-file")


# --- keys, titles and the model -------------------------------------------


def test_subject_encoding_percent_encodes_every_unsafe_byte() -> None:
    assert (
        subject_key("live-check/gone/", "https://dolphin-emu.org/download/?ref=btn")
        == "live-check/gone/https://dolphin-emu.org/download/%3Fref%3Dbtn"
    )
    assert encode_subject("100% a b") == "100%25%20a%20b"
    assert encode_subject("café") == "caf%C3%A9"
    assert encode_subject("a-b_c.d~e+f/g:h") == "a-b_c.d~e+f/g:h"


def test_overlong_subject_keys_fit_the_cap_and_stay_distinct_and_stable() -> None:
    first = "https://example.com/" + "a" * 3000 + "?x=1"
    second = "https://example.com/" + "a" * 3000 + "?x=2"

    key = subject_key("live-check/gone/", first)

    assert len(key) <= KEY_LIMIT
    assert key == subject_key("live-check/gone/", first)
    assert key != subject_key("live-check/gone/", second)
    assert parse_findings(
        LIVE_CHECK,
        FindingsFile(LIVE_CHECK, findings=(Finding(key, "t"),)).to_json(),
    )


def test_overlong_key_is_not_cut_inside_an_escape() -> None:
    key = subject_key("live-check/", "é" * 2000)

    assert len(key) <= KEY_LIMIT
    assert not re.search(r"%[0-9A-F]?~", key)


def test_titles_past_the_limit_end_in_an_ellipsis() -> None:
    assert truncate_title("short") == "short"
    cut = truncate_title("x" * 1000)
    assert len(cut) == TITLE_LIMIT
    assert cut.endswith("…")


def test_each_source_has_its_own_check_and_publish_owners() -> None:
    sourced = [owner for owner in OWNERS if owner.source is not None]

    assert sorted((o.source, o.job) for o in sourced) == sorted(
        (source, job) for source in SOURCE_NAMES for job in ("check", "publish")
    )
    assert len({owner.value for owner in OWNERS}) == len(OWNERS)
    prefixes = [prefix for owner in OWNERS for prefix in owner.prefixes]
    assert not any(a != b and b.startswith(a) for a in prefixes for b in prefixes)
    assert parse_owner("quiver-publish").prefixes == ("quiver/publish/",)
    with pytest.raises(ValueError, match="unknown producer owner"):
        parse_owner("quiver")


@pytest.mark.parametrize(
    ("job", "source"), [("check", None), ("publish", None), ("live-check", "codm")]
)
def test_an_owner_has_a_source_exactly_when_its_job_belongs_to_one(
    job: str, source: str | None
) -> None:
    with pytest.raises(ValueError, match="job with source"):
        Owner(job, source)  # ty: ignore[invalid-argument-type]


def test_check_step_table_covers_exactly_the_validation_steps_in_order() -> None:
    assert tuple(CHECK_STEPS) == VALIDATION_STEPS
    slugs = [slug for slug, _ in CHECK_STEPS.values()]
    assert len(set(slugs)) == len(slugs)


def test_early_failure_finding_is_fixed_per_owner() -> None:
    for owner in OWNERS:
        finding = early_failure_finding(owner)
        assert finding == early_failure_finding(owner)
        assert finding.key == early_failure_key(owner)
        assert finding.key.endswith("/run")
        assert owner.value in finding.title
        assert not any("http" in line for line in finding.details)
    assert early_failure_key(NIGHTLY_PREPARE) == "nightly/prepare/run"
    assert early_failure_key(LIVE_CHECK) == "live-check/run"
    assert early_failure_key(QUIVER_PUBLISH) == "quiver/publish/run"


def _parse(expected: Owner, **overrides: object) -> FindingsFile | None:
    data: dict[str, object] = {
        "owner": expected.value,
        "scope": [],
        "unchecked": [],
        "findings": [],
    }
    data.update(overrides)
    return parse_findings(expected, json.dumps(data))


def _entry(key: str, **overrides: object) -> dict[str, object]:
    return {"key": key, "title": "t", "details": ["d"], **overrides}


@pytest.mark.parametrize(
    "overrides",
    [
        {"findings": [_entry("codm/check/a-->b")]},
        {"findings": [_entry("codm/check/<b>")]},
        {"findings": [_entry("codm/check/a b")]},
        {"findings": [_entry("codm/check/" + "a" * KEY_LIMIT)]},
        {"findings": [_entry("nightly/prepare/build")]},
        {"findings": [_entry("codm/check/a", title="two\nlines")]},
        {"findings": [_entry("codm/check/a", title="")]},
        {"findings": [_entry("codm/check/a", title=" padded")]},
        {"findings": [_entry("codm/check/a", title="padded\t")]},
        {"findings": [_entry("codm/check/a", title="x" * 256)]},
        {"findings": [_entry("codm/check/a", details="not a list")]},
        {"findings": [_entry("codm/check/a", details=["ok", 3])]},
        {"findings": ["not an object"]},
        {"scope": ["quiver/check/"]},
        {"scope": "codm/check/"},
        {"unchecked": ["nightly/prepare/build"]},
        {"owner": "quiver-check"},
    ],
)
def test_invalid_findings_files_are_rejected(overrides: dict[str, object]) -> None:
    assert _parse(CODM_CHECK, **overrides) is None


def test_valid_findings_keep_raw_details_and_allow_long_ones() -> None:
    long_details = ["<b>" + "x" * 200_000]
    parsed = _parse(
        CODM_CHECK,
        findings=[_entry(CODM_STEP, title="x" * 255, details=long_details)],
        scope=["codm/check/"],
    )

    assert parsed is not None
    assert parsed.findings[0].details == tuple(long_details)
    assert parse_findings(CODM_CHECK, "{not json") is None
    assert parse_findings(CODM_CHECK, "[]") is None


# --- bodies ----------------------------------------------------------------


def test_body_starts_with_the_marker_escapes_details_and_ends_with_the_run() -> None:
    body = build_body(Finding(CODM_STEP, "t", ("<script>x</script>", "a & b")), RUN_1)

    lines = body.split("\n")
    assert lines[0] == f"<!-- omnipack-alert-key: {CODM_STEP} -->"
    assert "<script>" not in body
    assert "&lt;script&gt;x&lt;/script&gt;" in body
    assert "a &amp; b" in body
    assert lines[-1] == f"Run: {RUN_1}"
    assert marker_line(CODM_STEP) == lines[0]


def test_body_truncates_to_the_limit_counting_the_rest() -> None:
    details = tuple(f"line {index} " + "x" * 90 for index in range(2000))

    body = build_body(Finding(CODM_STEP, "t", details), RUN_1)

    assert len(body) <= BODY_LIMIT
    assert re.search(r"\nand \d+ more\n</pre>\n\nRun: ", body)
    assert body.endswith(f"Run: {RUN_1}")


def test_overflowing_body_keeps_the_same_details_whatever_the_run_url() -> None:
    details = tuple("x" * 9 for _ in range(10_000))
    finding = Finding(CODM_STEP, "t", details)

    short = build_body(finding, RUN_1)
    long = build_body(finding, RUN_1.replace("/1", "/" + "9" * 20))

    assert len(long) <= BODY_LIMIT
    assert short.rsplit("Run: ", 1)[0] == long.rsplit("Run: ", 1)[0]


# --- lifecycle -------------------------------------------------------------


def test_new_finding_opens_an_issue_with_label_title_and_body(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "Build failed", ("error <1>",)),),
    )
    gh = alert_gh()

    summary = _run(gh, _nightly(path))

    create = next(call for call in gh.calls if call[:2] == ("issue", "create"))
    assert create[create.index("--title") + 1] == "Build failed"
    assert create[create.index("--label") + 1] == "omnipack-alert"
    assert create[create.index("--repo") + 1] == REPOSITORY
    (body,) = _bodies(gh, "create")
    assert body.startswith(marker_line(NIGHTLY_STAGE) + "\n<pre>\nerror &lt;1&gt;\n")
    assert body.endswith(f"Run: {RUN_2}")
    assert summary.opened == 1


def test_finding_clears_closing_its_issue_as_completed(tmp_path: Path) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    close = next(call for call in gh.calls if call[:2] == ("issue", "close"))
    assert close[2] == "7"
    assert close[close.index("--reason") + 1] == "completed"
    assert close[close.index("--comment") + 1] == f"Not seen in run {RUN_2}"


def test_persisting_finding_with_new_details_edits_the_same_issue(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("new message",)),),
    )
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE, title="t", details=("old message",))])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("edit", "7")]
    (body,) = _bodies(gh, "edit")
    assert "new message" in body
    assert f"Run: {RUN_2}" in body


def test_persisting_finding_with_changed_title_edits_the_issue(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "new title", ("boom",)),),
    )
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE, title="old title")])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("edit", "7")]


def test_unchanged_finding_makes_no_edit_across_runs_with_different_urls(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    first = alert_gh()
    _run(first, _nightly(path), url=RUN_1)
    (opened_body,) = _bodies(first, "create")
    existing = alert_issue(7, NIGHTLY_STAGE, title="t", body=opened_body)

    second = alert_gh([existing])
    _run(second, _nightly(path), url=RUN_2)
    third = alert_gh([{**existing, "body": opened_body.replace("\n", "\r\n")}])
    _run(third, _nightly(path), url="https://example.invalid/runs/3")

    assert issue_writes(second) == []
    assert issue_writes(third) == []


def test_muted_issue_stays_closed_while_the_finding_persists(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == []


def test_muted_issue_that_clears_is_marked_completed_and_then_recurs_reopened(
    tmp_path: Path,
) -> None:
    clear = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    muted = alert_issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")
    gh = alert_gh([muted])

    _run(gh, _nightly(clear))

    assert issue_writes(gh) == [("reopen", "7"), ("close", "7")]
    close = next(call for call in gh.calls if call[:2] == ("issue", "close"))
    assert close[close.index("--reason") + 1] == "completed"
    assert close[close.index("--comment") + 1] == f"Cleared in run {RUN_2}"

    raise_again = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
        name="again.json",
    )
    cleared = alert_issue(7, NIGHTLY_STAGE, state="closed", reason="completed")
    gh = alert_gh([cleared])

    _run(gh, _nightly(raise_again))

    assert issue_writes(gh) == [("reopen", "7"), ("edit", "7")]


def test_mute_survives_a_run_that_did_not_re_check_the_key(tmp_path: Path) -> None:
    key = "live-check/status/https://example.com/x"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/status/", "live-check/gone/"),
        unchecked=(key,),
    )
    other = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,), name="n.json")
    gh = alert_gh([alert_issue(7, key, state="closed", reason="not_planned")])

    _run(gh, Producer(LIVE_CHECK, path, "success"), _nightly(other))

    assert issue_writes(gh) == []


@pytest.mark.parametrize("reason", ["completed", "duplicate", None])
def test_completed_duplicate_or_unreasoned_closures_reopen_when_raised(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("reopen", "7"), ("edit", "7")]


@pytest.mark.parametrize("reason", ["completed", None])
def test_completed_closure_is_left_alone_when_the_finding_clears(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = alert_gh([alert_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == []


def test_muted_403_does_not_hide_a_later_404(tmp_path: Path) -> None:
    url = "https://example.com/x"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        findings=(Finding(f"live-check/gone/{url}", "gone", ("404",)),),
    )
    gh = alert_gh(
        [
            alert_issue(
                7, f"live-check/status/{url}", state="closed", reason="not_planned"
            )
        ]
    )

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert issue_writes(gh) == [("create", "gone"), ("reopen", "7"), ("close", "7")]


def test_key_outside_scope_or_unchecked_is_left_unchanged(tmp_path: Path) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = alert_gh(
        [
            alert_issue(1, "nightly/prepare/commit"),
            alert_issue(2, "nightly/prepare/build-extra"),
            alert_issue(3, "nightly/publish/release"),
            alert_issue(4, "codm/check/verify"),
        ]
    )

    _run(gh, _nightly(path))

    assert issue_writes(gh) == []


def test_unchecked_key_under_a_scope_prefix_is_not_closed(tmp_path: Path) -> None:
    kept = "live-check/gone/https://example.com/kept"
    gone = "live-check/gone/https://example.com/gone"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        unchecked=(kept,),
    )
    gh = alert_gh([alert_issue(1, kept), alert_issue(2, gone)])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert issue_writes(gh) == [("close", "2")]


def test_creates_and_reopens_precede_closes(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        CODM_CHECK,
        scope=("codm/check/",),
        findings=(
            Finding("codm/check/tests", "tests", ("x",)),
            Finding("codm/check/build", "build", ("x",)),
        ),
    )
    gh = alert_gh(
        [
            alert_issue(1, "codm/check/generation"),
            alert_issue(2, "codm/check/build", state="closed", reason="completed"),
        ]
    )

    _run(gh, Producer(CODM_CHECK, path, "failure"))

    verbs = [verb for verb, _ in issue_writes(gh)]
    assert verbs == ["create", "reopen", "edit", "close"]


# --- issue identification --------------------------------------------------


def test_duplicate_keys_use_the_lowest_number(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("new",)),),
    )
    gh = alert_gh(
        [[alert_issue(9, NIGHTLY_STAGE)], [alert_issue(4, NIGHTLY_STAGE, title="t")]]
    )

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("edit", "4")]


def test_issues_without_a_valid_first_line_marker_are_ignored(tmp_path: Path) -> None:
    marker = marker_line(NIGHTLY_STAGE)
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh(
        [
            alert_issue(1, NIGHTLY_STAGE, body="no marker at all"),
            alert_issue(2, NIGHTLY_STAGE, body=f"intro\n{marker}\n"),
            alert_issue(3, NIGHTLY_STAGE, body=f"{marker}{marker}\nmore"),
            alert_issue(4, NIGHTLY_STAGE, body=f"{marker} trailing\nmore"),
            alert_issue(5, NIGHTLY_STAGE, body=None) | {"body": None},
        ]
    )

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("create", "t")]


def test_pull_requests_in_the_listing_are_ignored(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh([alert_issue(1, NIGHTLY_STAGE) | {"pull_request": {}}])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("create", "t")]


def test_details_carrying_another_keys_marker_leave_that_issue_alone(
    tmp_path: Path,
) -> None:
    other = "codm/check/verify"
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", (marker_line(other), "<b>x</b>")),),
    )
    gh = alert_gh([alert_issue(8, other)])

    _run(gh, _nightly(path))

    (body,) = _bodies(gh, "create")
    assert body.split("\n")[0] == marker_line(NIGHTLY_STAGE)
    assert "&lt;!-- omnipack-alert-key: codm/check/verify --&gt;" in body
    assert "<b>" not in body
    assert issue_writes(gh) == [("create", "t")]


def test_marker_inside_an_existing_issues_details_is_not_its_key() -> None:
    body = build_body(
        Finding(CODM_STEP, "t", (marker_line("codm/check/other"),)), RUN_1
    )

    assert alerts_module.body_key(body) == CODM_STEP


def test_listing_reads_every_page(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh(
        [
            [alert_issue(1, "nightly/prepare/commit")],
            [alert_issue(2, NIGHTLY_STAGE, title="t")],
        ]
    )

    _run(gh, _nightly(path))

    assert issue_writes(gh) == []
    listing = next(call for call in gh.calls if call[:2] == ISSUE_LISTING)
    assert f"repos/{REPOSITORY}/issues" in listing
    assert f"labels={alerts_module.LABEL}" in listing
    assert "state=all" in listing


# --- label -----------------------------------------------------------------


def test_existing_label_is_success_and_reconcile_proceeds(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh(
        label=failure('label with name "omnipack-alert" already exists; use --force')
    )

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("create", "t")]
    assert gh.calls[0][:3] == ("label", "create", "omnipack-alert")


# --- producers -------------------------------------------------------------


def test_codm_early_failure_leaves_quivers_issue_open(tmp_path: Path) -> None:
    gh_codm = alert_gh([alert_issue(1, early_failure_key(QUIVER_CHECK))])
    _run(gh_codm, Producer(CODM_CHECK, tmp_path / "none.json", "failure"))

    assert issue_writes(gh_codm) == [
        ("create", early_failure_finding(CODM_CHECK).title)
    ]

    gh_quiver = alert_gh([alert_issue(1, early_failure_key(CODM_CHECK))])
    quiver = _file(tmp_path, QUIVER_CHECK, scope=("quiver/check/",))
    _run(gh_quiver, Producer(QUIVER_CHECK, quiver, "success"))
    assert issue_writes(gh_quiver) == []


def test_early_failure_issue_closes_when_the_producer_succeeds(tmp_path: Path) -> None:
    path = _file(tmp_path, LIVE_CHECK)
    gh = alert_gh([alert_issue(1, early_failure_key(LIVE_CHECK))])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert issue_writes(gh) == [("close", "1")]


@pytest.mark.parametrize("result", ["success", "failure"])
def test_missing_file_raises_the_early_failure_and_closes_nothing_else(
    tmp_path: Path, result: StepOutcome
) -> None:
    gh = alert_gh([alert_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(tmp_path / "absent.json", result))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


def test_foreign_key_is_rejected_with_the_early_failure_finding(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/",),
        findings=(Finding("live-check/gone/x", "gone", ()),),
    )
    data = json.loads(path.read_text())
    data["findings"].append(_entry("nightly/prepare/build"))
    path.write_text(json.dumps(data))
    gh = alert_gh([alert_issue(1, "live-check/gone/y")])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert issue_writes(gh) == [("create", early_failure_finding(LIVE_CHECK).title)]


def test_pathologically_nested_file_is_rejected_with_the_early_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested.json"
    path.write_text("[" * 100_000 + "]" * 100_000)
    assert parse_findings(NIGHTLY_PREPARE, path.read_text()) is None
    gh = alert_gh([alert_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


@pytest.mark.parametrize(
    "entry",
    [
        _entry(NIGHTLY_STAGE, title="a\x00b"),
        _entry(NIGHTLY_STAGE, title="bell\x07"),
        _entry(NIGHTLY_STAGE, title="half \ud800 pair"),
        _entry(NIGHTLY_STAGE, details=["half \udfff pair"]),
    ],
    ids=["nul-title", "control-title", "surrogate-title", "surrogate-detail"],
)
def test_text_gh_cannot_carry_rejects_the_file_with_the_early_failure(
    tmp_path: Path, entry: dict[str, object]
) -> None:
    path = tmp_path / "findings.json"
    path.write_text(
        json.dumps(
            {
                "owner": NIGHTLY_PREPARE.value,
                "scope": [NIGHTLY_STAGE],
                "unchecked": [],
                "findings": [entry],
            }
        )
    )
    gh = alert_gh([alert_issue(1, NIGHTLY_STAGE), alert_issue(2, "codm/check/verify")])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


def test_symlinked_findings_file_is_rejected(tmp_path: Path) -> None:
    real = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    gh = alert_gh([alert_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(link))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


def test_cancelled_producer_with_a_valid_file_raises_only_the_early_failure(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=("nightly/prepare/", NIGHTLY_STAGE),
        unchecked=(),
        findings=(Finding(NIGHTLY_STAGE, "build", ("boom",)),),
    )
    gh = alert_gh([alert_issue(1, "nightly/prepare/commit"), alert_issue(2, "build/x")])

    _run(gh, _nightly(path, "cancelled"))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


def test_failed_producer_reporting_only_the_early_failure_closes_nothing(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(early_failure_finding(NIGHTLY_PREPARE),),
    )
    gh = alert_gh(
        [alert_issue(1, NIGHTLY_STAGE), alert_issue(2, "build/uncategorized/x")]
    )

    _run(gh, _nightly(path, "failure"))

    assert issue_writes(gh) == [
        ("create", early_failure_finding(NIGHTLY_PREPARE).title)
    ]


@pytest.mark.parametrize("result", ["skipped", None])
def test_producer_with_another_result_contributes_nothing(
    tmp_path: Path, result: StepOutcome | None
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PUBLISH,
        scope=("nightly/publish/",),
        findings=(Finding("nightly/publish/push", "push", ()),),
    )
    gh = alert_gh(
        [
            alert_issue(1, "nightly/publish/release"),
            alert_issue(2, "nightly/publish/run"),
        ]
    )

    _run(gh, Producer(NIGHTLY_PUBLISH, path, result))

    assert issue_writes(gh) == []


def test_oversized_details_keep_the_finding_with_an_overflow_count(
    tmp_path: Path,
) -> None:
    details = tuple("y" * 1000 for _ in range(200))
    path = _file(
        tmp_path,
        CODM_CHECK,
        scope=("codm/check/",),
        findings=(Finding(CODM_STEP, "verify", details),),
    )
    gh = alert_gh()

    _run(gh, Producer(CODM_CHECK, path, "failure"))

    assert issue_writes(gh) == [("create", "verify")]
    (body,) = _bodies(gh, "create")
    assert len(body) <= BODY_LIMIT
    assert re.search(r"\nand \d+ more\n</pre>", body)


# --- failures --------------------------------------------------------------


@pytest.fixture
def reconcile_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[FakeGh], Path]:
    """Install a fake `gh` and the run variables `reconcile` reads; the
    returned function gives the step summary path."""

    def install(gh: FakeGh) -> Path:
        summary = tmp_path / "summary.md"
        monkeypatch.setattr(alerts_module, "SubprocessGhRunner", lambda: gh)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
        monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
        monkeypatch.setenv("GITHUB_RUN_ID", "2")
        return summary

    return install


@pytest.mark.parametrize(
    ("knob", "issues", "reason"),
    [
        ("label", None, "could not create the label"),
        ("listing", None, "could not list issues"),
        ("issue_create", None, "could not create an issue"),
        (
            "issue_edit",
            [alert_issue(1, NIGHTLY_STAGE, title="old")],
            "could not update an issue",
        ),
        (
            "issue_close",
            [alert_issue(1, "nightly/prepare/commit")],
            "could not close an issue",
        ),
        (
            "issue_reopen",
            [alert_issue(1, NIGHTLY_STAGE, state="closed", reason="completed")],
            "could not reopen an issue",
        ),
    ],
)
def test_failed_gh_operation_fails_with_a_fixed_reason(
    tmp_path: Path,
    reconcile_cli: Callable[[FakeGh], Path],
    capsys: pytest.CaptureFixture[str],
    knob: str,
    issues: list[dict] | None,
    reason: str,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=("nightly/prepare/commit",),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    if knob == "label":
        gh = alert_gh(issues, label=failure("token leaked"))
    elif knob == "listing":
        gh = alert_gh(issues, listing=failure("token leaked"))
    else:
        gh = alert_gh(issues, **{knob: failure("token leaked")})
    summary_path = reconcile_cli(gh)

    exit_code = alerts_module.main(
        ["reconcile", "--producer", f"nightly-prepare=success:{path}"]
    )

    assert exit_code == 1
    assert summary_path.read_text() == f"reconcile failed: {reason}\n"
    assert "token leaked" not in summary_path.read_text()
    assert f"reconcile failed: {reason}" in capsys.readouterr().err


def test_unreadable_listing_fails_without_gh_output(tmp_path: Path) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE)
    gh = alert_gh(listing=CommandResult(0, "{not json", ""))

    with pytest.raises(ReconcileFailure, match="could not read the issue listing"):
        _run(gh, _nightly(path))


def test_cli_reconciles_producers_with_results_from_the_command_line(
    tmp_path: Path, reconcile_cli: Callable[[FakeGh], Path]
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh()
    summary_path = reconcile_cli(gh)

    exit_code = alerts_module.main(
        [
            "reconcile",
            "--producer", f"nightly-prepare=success:{path}",
            "--producer", f"nightly-publish=skipped:{tmp_path / 'absent.json'}",
        ]
    )  # fmt: skip

    assert exit_code == 0
    assert issue_writes(gh) == [("create", "t")]
    assert f"Run: {RUN_2}" in _bodies(gh, "create")[0]
    assert (
        summary_path.read_text()
        == "alerts: 1 opened, 0 updated, 0 reopened, 0 closed, 0 mute cleared\n"
    )


def test_cli_producer_with_an_empty_result_contributes_nothing(
    tmp_path: Path, reconcile_cli: Callable[[FakeGh], Path]
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = alert_gh()
    reconcile_cli(gh)

    exit_code = alerts_module.main(
        ["reconcile", "--producer", f"nightly-prepare=:{path}"]
    )

    assert exit_code == 0
    assert issue_writes(gh) == []


@pytest.mark.parametrize(
    "value",
    [
        "nightly-prepare",
        "nightly-prepare=success",
        "nightly-prepare=success:",
        "bogus=success:f.json",
    ],
)
def test_cli_rejects_a_malformed_producer_with_a_usage_error(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        alerts_module.main(["reconcile", "--producer", value])

    assert raised.value.code == 2
    assert "usage:" in capsys.readouterr().err


# --- emitters --------------------------------------------------------------

STAGES = "checkout,build,allowlist,README boundary,verify,drift after verify"


def _emit(
    owner: Owner,
    status: str = "success",
    *,
    report: object | None = None,
    tmp_path: Path | None = None,
    **env: str,
) -> FindingsFile:
    """The emitted file, checked to survive validation unchanged."""
    report_path = None
    if report is not None:
        assert tmp_path is not None
        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(report))
    elif tmp_path is not None:
        report_path = tmp_path / "absent-report.json"
    file = emit(owner, {"JOB_STATUS": status, **env}, report_path)
    assert parse_findings(owner, file.to_json()) == file
    return file


def _keys(file: FindingsFile) -> list[str]:
    return [finding.key for finding in file.findings]


def _early(owner: Owner) -> list[str]:
    return [early_failure_key(owner)]


def _build_report(status: str = "success", **lists: list) -> dict:
    return {
        "status": status,
        "uncategorizedFamilies": [],
        "staleExclusions": [],
        "staleCategoryAssignments": [],
        "redundantOverlayKeys": [],
        "extrasListedByCatalog": [],
        "repeatedIds": [],
        **lists,
    }


def _prepare_file(tmp_path: Path, report: dict, name: str = "prepare.json") -> Path:
    """The nightly prepare findings file for `report`, written for reconciling."""
    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )
    path = tmp_path / name
    path.write_text(file.to_json())
    return path


REDUNDANT = "build/redundant-patch/"
LISTED = "build/listed-extra/"


def _dead_keys(url: str, *keys: str) -> dict:
    return {"url": url, "keys": list(keys)}


def _listed_extra(url: str, package_id: str, **sources: list[str]) -> dict:
    return {
        "url": url,
        "id": package_id,
        "sources": [
            {"source": source, "fields": fields} for source, fields in sources.items()
        ],
    }


def test_dead_keys_and_listed_extras_are_one_finding_per_key_and_per_url(
    tmp_path: Path,
) -> None:
    report = _build_report(
        redundantOverlayKeys=[
            _dead_keys("example.org/a", "additionalSettings.includeZips", "name")
        ],
        extrasListedByCatalog=[
            _listed_extra("example.org/b", "org.b", quiver=["name", "variants"])
        ],
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [
        REDUNDANT + "example.org/a/additionalSettings.includeZips",
        REDUNDANT + "example.org/a/name",
        LISTED + "example.org/b",
    ]
    assert early_failure_key(NIGHTLY_PREPARE) not in _keys(file)
    assert "build/" in file.scope
    assert file.findings[0].title == (
        "Overlay patch key changes nothing: example.org/a additionalSettings.includeZips"
    )
    assert file.findings[0].details == (
        "URL: example.org/a",
        "Key: additionalSettings.includeZips",
    )
    assert file.findings[2].title == "A catalog lists an extra at: example.org/b"
    assert file.findings[2].details == ("Package: org.b", "quiver: name, variants")


def test_a_muted_dead_key_stays_closed_while_a_later_one_raises_its_own(
    tmp_path: Path,
) -> None:
    report = _build_report(
        redundantOverlayKeys=[_dead_keys("example.org/a", "name", "pinned")]
    )
    path = _prepare_file(tmp_path, report)
    muted = alert_issue(
        7, REDUNDANT + "example.org/a/name", state="closed", reason="not_planned"
    )
    gh = alert_gh([muted])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [
        ("create", "Overlay patch key changes nothing: example.org/a pinned")
    ]


def test_two_listed_extras_at_one_url_are_one_finding_naming_both(
    tmp_path: Path,
) -> None:
    report = _build_report(
        extrasListedByCatalog=[
            _listed_extra("example.org/x", "org.a", quiver=["name"], rjny=[]),
            _listed_extra("example.org/x", "org.b", codm=["additionalSettings.about"]),
        ]
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [LISTED + "example.org/x"]
    assert file.findings[0].details == (
        "Package: org.a",
        "quiver: name",
        "rjny: no differences",
        "Package: org.b",
        "codm: additionalSettings.about",
    )


REPEATED = "build/repeated-id/"


def _repeated(variant: str, package_id: str, *entries: tuple[str, str]) -> dict:
    return {
        "variant": variant,
        "id": package_id,
        "entries": [{"family": family, "url": url} for family, url in entries],
    }


def test_a_repeated_package_id_raises_one_finding_per_pack(tmp_path: Path) -> None:
    entries = (("example.org/a", "example.org/a"), ("app:b", "example.org/b"))
    report = _build_report(
        repeatedIds=[
            _repeated("single", "p", *entries),
            _repeated("dual", "p", *entries),
        ]
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [REPEATED + "single/p", REPEATED + "dual/p"]
    assert file.findings[0].title == "Package id repeated in the single pack: p"
    assert file.findings[0].details == (
        "Variant: single",
        "Package id: p",
        "Entry: example.org/a at example.org/a",
        "Entry: app:b at example.org/b",
    )
    assert file.findings[1].title == "Package id repeated in the dual pack: p"
    assert file.findings[1].details == (
        "Variant: dual",
        "Package id: p",
        "Entry: example.org/a at example.org/a",
        "Entry: app:b at example.org/b",
    )


@pytest.mark.parametrize(
    "malformed",
    [{"family": 1, "url": "example.org/c"}, {"family": "app:c", "url": None}],
    ids=["family", "url"],
)
def test_a_repeated_id_entry_without_a_string_family_and_url_is_left_out(
    tmp_path: Path, malformed: dict[str, object]
) -> None:
    item = _repeated("single", "p", ("app:b", "example.org/b"))
    item["entries"].append(malformed)
    report = _build_report(repeatedIds=[item])

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [REPEATED + "single/p"]
    assert file.findings[0].details == (
        "Variant: single",
        "Package id: p",
        "Entry: app:b at example.org/b",
    )


def test_a_repeated_package_id_with_an_unknown_pack_raises_nothing(
    tmp_path: Path,
) -> None:
    report = _build_report(repeatedIds=[_repeated("both", "p")])

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert not any(key.startswith(REPEATED) for key in _keys(file))


def test_dead_key_subjects_are_percent_encoded(tmp_path: Path) -> None:
    report = _build_report(
        redundantOverlayKeys=[_dead_keys("example.org/x?v=1", "na\u00efve")],
        extrasListedByCatalog=[_listed_extra("example.org/x?v=1", "org.x")],
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [
        REDUNDANT + "example.org/x%3Fv%3D1/na%C3%AFve",
        LISTED + "example.org/x%3Fv%3D1",
    ]
    assert file.findings[0].details == ("URL: example.org/x?v=1", "Key: na\u00efve")


def test_dead_key_subjects_are_distinct_across_nested_urls(tmp_path: Path) -> None:
    # The URL and key join with `/`, so `example.org/a` with key `b` yields the
    # subject `example.org/a/b`. Overlay parsing rejects any patch key holding
    # a `/`, so URL `example.org` with key `a/b` never reaches a report and the
    # subject names one pair. Nested URLs with their own keys stay distinct.
    report = _build_report(
        redundantOverlayKeys=[
            _dead_keys("example.org/a", "b"),
            _dead_keys("example.org/a/b", "c"),
            _dead_keys("example.org/a", "b.c"),
        ]
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [
        REDUNDANT + "example.org/a/b",
        REDUNDANT + "example.org/a/b/c",
        REDUNDANT + "example.org/a/b.c",
    ]


def test_an_overlong_dead_key_subject_is_accepted_and_distinct(
    tmp_path: Path,
) -> None:
    url = "example.org/" + "a" * (KEY_LIMIT + 10)
    report = _build_report(redundantOverlayKeys=[_dead_keys(url, "name")])
    neighbour = _build_report(redundantOverlayKeys=[_dead_keys(url, "nam2")])

    first = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )
    other = _emit(
        NIGHTLY_PREPARE,
        report=neighbour,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    (finding,) = first.findings
    assert len(finding.key) <= KEY_LIMIT
    assert finding.key.startswith(REDUNDANT)
    assert _keys(first) != _keys(other)
    assert finding.details == (f"URL: {url}", "Key: name")


def test_a_muted_dead_key_clears_when_a_successful_build_drops_it(
    tmp_path: Path,
) -> None:
    path = _prepare_file(tmp_path, _build_report())
    muted = alert_issue(
        7, REDUNDANT + "example.org/a/name", state="closed", reason="not_planned"
    )
    gh = alert_gh([muted])

    _run(gh, _nightly(path))

    assert issue_writes(gh) == [("reopen", "7"), ("close", "7")]


@pytest.mark.parametrize("owner", [NIGHTLY_PUBLISH, CODM_CHECK], ids=str)
def test_an_unrecognized_job_status_counts_as_failure(owner: Owner) -> None:
    file = _emit(owner, "bogus")

    assert _keys(file) == _early(owner)


def test_emit_requires_the_job_status() -> None:
    with pytest.raises(SystemExit, match="JOB_STATUS is required"):
        emit(NIGHTLY_PUBLISH, {})


def test_successful_prepare_with_an_empty_report_raises_nothing(
    tmp_path: Path,
) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        report=_build_report(),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert file.findings == ()
    assert file.scope == (
        "nightly/prepare/checkout",
        "nightly/prepare/build",
        "nightly/prepare/allowlist",
        "nightly/prepare/readme-boundary",
        "nightly/prepare/verify",
        "nightly/prepare/drift-after-verify",
        "build/",
    )
    assert "nightly/prepare/commit" not in file.scope
    assert "nightly/prepare/bundle" not in file.scope


def test_prepare_failing_at_build_leaves_later_stages_out_of_scope(
    tmp_path: Path,
) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        tmp_path=tmp_path,
        PREPARE_STAGE="build",
        PREPARE_STAGES="checkout,build",
    )

    assert _keys(file) == ["nightly/prepare/build"]
    assert file.scope == ("nightly/prepare/checkout", "nightly/prepare/build")
    assert file.findings[0].title == "Nightly preparation failed at the build stage"


def test_prepare_reporting_only_a_later_stage_leaves_checkout_out_of_scope(
    tmp_path: Path,
) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        tmp_path=tmp_path,
        PREPARE_STAGE="build",
        PREPARE_STAGES="build",
    )

    assert file.scope == ("nightly/prepare/build",)


def test_stage_with_spaces_maps_through_its_slug(tmp_path: Path) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        tmp_path=tmp_path,
        PREPARE_STAGE="README boundary",
        PREPARE_STAGES="checkout,build,allowlist,README boundary",
    )

    assert _keys(file) == ["nightly/prepare/readme-boundary"]
    assert "nightly/prepare/readme-boundary" in file.scope


def test_build_warnings_are_one_finding_per_item_and_scope_the_build_keys(
    tmp_path: Path,
) -> None:
    report = _build_report(
        uncategorizedFamilies=[
            {"family": "Alpha", "variants": ["single-screen"]},
            {"family": "Beta", "variants": ["single-screen", "dual-screen"]},
        ],
        staleExclusions=[{"url": "https://example.com/old", "reason": "gone"}],
        staleCategoryAssignments=["Some Key"],
    )

    file = _emit(
        NIGHTLY_PREPARE,
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == [
        "build/uncategorized/Alpha",
        "build/uncategorized/Beta",
        "build/stale-denial/https://example.com/old",
        "build/stale-category/Some%20Key",
    ]
    assert "build/" in file.scope
    assert file.findings[1].details == (
        "Family: Beta",
        "Variants: single-screen, dual-screen",
    )


def test_failed_build_report_raises_its_items_but_scopes_no_build_key(
    tmp_path: Path,
) -> None:
    failed = _build_report(
        "failed", uncategorizedFamilies=[{"family": "Alpha", "variants": []}]
    )
    empty = _build_report("failed")

    raising = _emit(
        NIGHTLY_PREPARE,
        "failure",
        report=failed,
        tmp_path=tmp_path,
        PREPARE_STAGE="build",
        PREPARE_STAGES="checkout,build",
    )
    quiet = _emit(
        NIGHTLY_PREPARE,
        "failure",
        report=empty,
        tmp_path=tmp_path,
        PREPARE_STAGE="build",
        PREPARE_STAGES="checkout,build",
    )

    assert "build/uncategorized/Alpha" in _keys(raising)
    assert not any(entry.startswith("build/") for entry in raising.scope)
    assert not any(entry.startswith("build/") for entry in quiet.scope)


def test_missing_or_malformed_build_report_contributes_nothing(
    tmp_path: Path,
) -> None:
    env = {"PREPARE_STAGE": "complete", "PREPARE_STAGES": STAGES}
    missing = _emit(NIGHTLY_PREPARE, tmp_path=tmp_path, **env)
    (tmp_path / "report.json").write_text("[not an object")
    malformed = emit(
        NIGHTLY_PREPARE,
        {"JOB_STATUS": "success", **env},
        tmp_path / "report.json",
    )

    assert "build/" not in missing.scope
    assert "build/" not in malformed.scope
    assert missing.findings == malformed.findings == ()


def test_setup_failure_before_prepare_raises_the_early_failure_only(
    tmp_path: Path,
) -> None:
    file = _emit(NIGHTLY_PREPARE, "failure", tmp_path=tmp_path)

    assert _keys(file) == _early(NIGHTLY_PREPARE)
    assert file.scope == ()


def test_upload_failure_after_a_successful_prepare_raises_the_early_failure(
    tmp_path: Path,
) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        report=_build_report(),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert _keys(file) == _early(NIGHTLY_PREPARE)
    assert "nightly/prepare/verify" in file.scope


def test_unrecognized_stage_names_contribute_nothing(tmp_path: Path) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        tmp_path=tmp_path,
        PREPARE_STAGE="reticulate splines",
        PREPARE_STAGES="checkout,../escape,reticulate splines",
    )

    assert file.scope == ("nightly/prepare/checkout",)
    assert _keys(file) == _early(NIGHTLY_PREPARE)


@pytest.mark.parametrize("owner", OWNERS, ids=str)
def test_cancelled_job_yields_exactly_the_early_failure(
    owner: Owner, tmp_path: Path
) -> None:
    report = {
        "status": "success",
        "unreachable": [{"url": "https://x/y", "status": 404}],
    }
    file = _emit(
        owner,
        "cancelled",
        report=report,
        tmp_path=tmp_path,
        PREPARE_STAGE="build",
        PREPARE_STAGES="checkout,build",
        PUSH_OUTCOME="failed",
        RELEASE_OUTCOME="ok",
        PUBLISH_OUTCOME="failed",
        GENERATION_RESULT="success",
        STAGING_RESULT="failure",
        TESTS_RESULT="failure",
        CHECK_RESULT="failure",
        CHANGED="false",
    )

    assert file == FindingsFile(owner, (), (), (early_failure_finding(owner),))


def test_nightly_push_and_release_are_scoped_when_ok_or_failed() -> None:
    file = _emit(
        NIGHTLY_PUBLISH, "failure", PUSH_OUTCOME="ok", RELEASE_OUTCOME="failed"
    )

    assert file.scope == ("nightly/publish/push", "nightly/publish/release")
    assert _keys(file) == ["nightly/publish/release"]


def test_main_advanced_raises_nothing_and_leaves_its_key_out_of_scope() -> None:
    file = _emit(NIGHTLY_PUBLISH, "failure", PUSH_OUTCOME="main-advanced")

    assert file.findings == ()
    assert file.scope == ()


@pytest.mark.parametrize("owner", [CODM_PUBLISH, QUIVER_PUBLISH], ids=str)
def test_source_publish_refused_as_main_advanced_raises_nothing(owner: Owner) -> None:
    file = _emit(owner, "failure", PUBLISH_OUTCOME="main-advanced")

    assert file == FindingsFile(owner)


def test_release_main_advanced_after_an_ok_push_scopes_only_the_push() -> None:
    file = _emit(
        NIGHTLY_PUBLISH,
        "failure",
        PUSH_OUTCOME="ok",
        RELEASE_OUTCOME="main-advanced",
    )

    assert file.scope == ("nightly/publish/push",)
    assert file.findings == ()


def test_ok_push_and_release_scope_the_release_key_and_raise_nothing() -> None:
    file = _emit(NIGHTLY_PUBLISH, PUSH_OUTCOME="ok", RELEASE_OUTCOME="ok")

    assert "nightly/publish/release" in file.scope
    assert file.findings == ()


@pytest.mark.parametrize("owner", [NIGHTLY_PUBLISH, CODM_PUBLISH, QUIVER_PUBLISH])
def test_failed_base_guard_in_a_write_job_raises_the_early_failure(
    owner: Owner,
) -> None:
    file = _emit(owner, "failure")

    assert _keys(file) == _early(owner)
    assert file.scope == ()


def test_skipped_publish_steps_after_a_successful_job_raise_nothing() -> None:
    file = _emit(CODM_PUBLISH)

    assert file == FindingsFile(CODM_PUBLISH)


@pytest.mark.parametrize(
    ("owner", "source"),
    [(CODM_PUBLISH, "codm"), (QUIVER_PUBLISH, "quiver")],
)
def test_failed_source_publication_raises_the_proposal_finding(
    owner: Owner, source: str
) -> None:
    file = _emit(owner, "failure", PUBLISH_OUTCOME="failed")

    assert _keys(file) == [f"{source}/publish/proposal"]
    assert file.scope == (f"{source}/publish/proposal",)
    assert source in file.findings[0].title


def test_candidate_failing_verification_raises_the_verify_finding() -> None:
    file = _emit(
        CODM_CHECK,
        "failure",
        GENERATION_RESULT="success",
        STAGING_RESULT="success",
        TESTS_RESULT="success",
        BUILD_RESULT="success",
        VERIFY_RESULT="failure",
        GUARD_RESULT="skipped",
        CHANGED="true",
    )

    assert _keys(file) == ["codm/check/verify"]
    assert file.scope == (
        "codm/check/generation",
        "codm/check/stage",
        "codm/check/tests",
        "codm/check/build",
        "codm/check/verify",
    )
    assert "codm/check/guard" not in file.scope


def test_generation_failing_leaves_later_steps_out_of_scope() -> None:
    file = _emit(
        QUIVER_CHECK,
        "failure",
        GENERATION_RESULT="failure",
        STAGING_RESULT="skipped",
        TESTS_RESULT="skipped",
        BUILD_RESULT="skipped",
        VERIFY_RESULT="skipped",
        GUARD_RESULT="skipped",
    )

    assert _keys(file) == ["quiver/check/generation"]
    assert file.scope == ("quiver/check/generation",)


def test_unchanged_candidate_after_successful_staging_re_checks_the_skipped_steps() -> (
    None
):
    file = _emit(
        CODM_CHECK,
        GENERATION_RESULT="success",
        STAGING_RESULT="success",
        TESTS_RESULT="skipped",
        BUILD_RESULT="skipped",
        VERIFY_RESULT="skipped",
        GUARD_RESULT="skipped",
        CHANGED="false",
    )

    assert file.findings == ()
    assert file.scope == tuple(
        f"codm/check/{slug}"
        for slug in ("generation", "stage", "tests", "build", "verify", "guard")
    )


def test_steps_skipped_after_a_failed_staging_are_not_re_checked() -> None:
    file = _emit(
        CODM_CHECK,
        "failure",
        GENERATION_RESULT="success",
        STAGING_RESULT="failure",
        TESTS_RESULT="skipped",
        BUILD_RESULT="skipped",
        VERIFY_RESULT="skipped",
        GUARD_RESULT="skipped",
        CHANGED="",
    )

    assert file.scope == ("codm/check/generation", "codm/check/stage")


def test_check_setup_failure_and_upload_failure_raise_the_early_failure() -> None:
    setup = _emit(CODM_CHECK, "failure")
    upload = _emit(
        CODM_CHECK,
        "failure",
        GENERATION_RESULT="success",
        STAGING_RESULT="success",
        CHANGED="false",
        TESTS_RESULT="skipped",
        BUILD_RESULT="skipped",
        VERIFY_RESULT="skipped",
        GUARD_RESULT="skipped",
    )

    assert _keys(setup) == _early(CODM_CHECK)
    assert setup.scope == ()
    assert _keys(upload) == _early(CODM_CHECK)
    assert "codm/check/guard" in upload.scope


def test_unrecognized_step_results_count_for_nothing() -> None:
    file = _emit(CODM_CHECK, GENERATION_RESULT="weird", TESTS_RESULT="")

    assert file == FindingsFile(CODM_CHECK)


LIVE_ENV = {"CHECK_RESULT": "failure"}


def _live_report(**overrides: object) -> dict:
    return {
        "status": "success",
        "unreachable": [],
        "inconclusive": [],
        "stale": [],
        "archived": [],
        "healthInconclusive": [],
        **overrides,
    }


def _reconcile_live(tmp_path: Path, report: dict, issues: list[dict]) -> FakeGh:
    """Emit the live-check findings for `report` and reconcile them."""
    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")
    path = tmp_path / "live.json"
    path.write_text(file.to_json())
    gh = alert_gh(issues)
    _run(gh, Producer(LIVE_CHECK, path, "success"))
    return gh


def test_stale_and_archived_urls_raise_health_findings(tmp_path: Path) -> None:
    report = _live_report(
        stale=[
            {
                "url": "https://github.com/a/old",
                "name": "Old App",
                "tag": "v1.0",
                "date": "2026-01-02",
            },
            {"url": "https://github.com/a/none", "name": "No APK"},
        ],
        archived=[{"url": "https://github.com/a/shut", "name": "Shut"}],
        healthInconclusive=[
            {"url": "https://github.com/a/limited", "name": "Q", "reason": "HTTP 403"}
        ],
    )

    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")

    assert [(f.key, f.title, f.details) for f in file.findings] == [
        (
            "live-check/stale/https://github.com/a/old",
            (
                "Project has had no qualifying release in 180 days: "
                "https://github.com/a/old"
            ),
            (
                "URL: https://github.com/a/old",
                "Entry: Old App",
                "Newest qualifying release: v1.0 (2026-01-02)",
            ),
        ),
        (
            "live-check/stale/https://github.com/a/none",
            "Project has no qualifying release: https://github.com/a/none",
            (
                "URL: https://github.com/a/none",
                "Entry: No APK",
                "No release qualified.",
            ),
        ),
        (
            "live-check/archived/https://github.com/a/shut",
            "Project repository is archived: https://github.com/a/shut",
            ("URL: https://github.com/a/shut", "Entry: Shut"),
        ),
    ]
    assert file.scope == (
        "live-check/read",
        "live-check/gone/",
        "live-check/status/",
        "live-check/stale/",
        "live-check/archived/",
    )
    assert file.unchecked == (
        "live-check/stale/https://github.com/a/limited",
        "live-check/archived/https://github.com/a/limited",
    )


def test_a_stale_release_without_a_date_or_entry_name_is_still_described(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/old"
    report = _live_report(
        stale=[{"url": url, "name": "", "tag": "v1.0"}],
        archived=[{"url": url}],
    )

    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")

    assert [(f.title, f.details) for f in file.findings] == [
        (
            f"Project has had no qualifying release in 180 days: {url}",
            (f"URL: {url}", "Newest qualifying release: v1.0"),
        ),
        (f"Project repository is archived: {url}", (f"URL: {url}",)),
    ]


def test_health_findings_do_not_account_for_a_failed_live_check_job(
    tmp_path: Path,
) -> None:
    report = _live_report(
        stale=[{"url": "https://github.com/a/old", "name": "Old"}],
        archived=[{"url": "https://github.com/a/old", "name": "Old"}],
    )

    file = _emit(LIVE_CHECK, "failure", report=report, tmp_path=tmp_path, **LIVE_ENV)

    assert _keys(file) == [
        "live-check/stale/https://github.com/a/old",
        "live-check/archived/https://github.com/a/old",
        *_early(LIVE_CHECK),
    ]


def test_health_findings_follow_health_alone(tmp_path: Path) -> None:
    url = "https://github.com/a/slow"
    report = _live_report(
        inconclusive=[{"url": url, "reason": "timed out"}],
        stale=[{"url": url, "name": "Slow"}],
    )

    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")

    assert _keys(file) == [f"live-check/stale/{url}"]
    assert file.unchecked == (f"live-check/gone/{url}", f"live-check/status/{url}")


def test_a_blocked_page_with_a_rate_limited_lookup_keeps_its_health_issues(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/blocked"
    report = _live_report(
        inconclusive=[{"url": url, "reason": "HTTP 403", "status": 403}],
        healthInconclusive=[{"url": url, "name": "B", "reason": "HTTP 403"}],
    )

    gh = _reconcile_live(
        tmp_path,
        report,
        [
            alert_issue(1, f"live-check/stale/{url}"),
            alert_issue(2, f"live-check/archived/{url}"),
        ],
    )

    assert issue_writes(gh) == [("create", f"Project URL answers HTTP 403: {url}")]


def test_a_rate_limited_lookup_leaves_an_open_stale_issue_unchanged(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/app"
    report = _live_report(
        healthInconclusive=[{"url": url, "name": "App", "reason": "HTTP 429"}]
    )

    gh = _reconcile_live(tmp_path, report, [alert_issue(1, f"live-check/stale/{url}")])

    assert issue_writes(gh) == []


def test_unreachable_urls_leave_their_health_issues_unchanged(tmp_path: Path) -> None:
    url = "https://github.com/a/gone"
    report = _live_report(unreachable=[{"url": url, "status": 404}])

    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")

    assert file.unchecked == (
        f"live-check/stale/{url}",
        f"live-check/archived/{url}",
    )


def test_a_muted_stale_issue_stays_closed_and_clears_on_a_fresh_release(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/app"
    muted = alert_issue(
        1, f"live-check/stale/{url}", state="closed", reason="not_planned"
    )
    dormant = _live_report(stale=[{"url": url, "name": "App"}])

    accepted = _reconcile_live(tmp_path, dormant, [muted])

    assert issue_writes(accepted) == []

    # The first run wrote nothing, so the issue is still muted.
    released = _reconcile_live(tmp_path, _live_report(), [muted])

    assert issue_writes(released) == [("reopen", "1"), ("close", "1")]
    close = next(call for call in released.calls if call[:2] == ("issue", "close"))
    assert close[close.index("--reason") + 1] == "completed"
    assert close[close.index("--comment") + 1] == f"Cleared in run {RUN_2}"


def test_a_lookup_cut_by_the_time_budget_leaves_a_muted_stale_issue_unchanged(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/app"
    not_checked = "not checked: time budget spent"
    report = _live_report(
        inconclusive=[{"url": url, "reason": not_checked}],
        healthInconclusive=[{"url": url, "name": "App", "reason": not_checked}],
    )
    muted = alert_issue(
        1, f"live-check/stale/{url}", state="closed", reason="not_planned"
    )

    gh = _reconcile_live(tmp_path, report, [muted])

    assert issue_writes(gh) == []


def test_health_issues_of_a_url_that_left_the_packs_are_closed(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/denied"
    issues = [
        alert_issue(1, f"live-check/stale/{url}"),
        alert_issue(2, f"live-check/archived/{url}"),
        alert_issue(
            3, f"live-check/stale/{url}x", state="closed", reason="not_planned"
        ),
        alert_issue(
            4, f"live-check/archived/{url}x", state="closed", reason="not_planned"
        ),
    ]

    gh = _reconcile_live(tmp_path, _live_report(), issues)

    assert issue_writes(gh) == [
        ("close", "1"),
        ("close", "2"),
        ("reopen", "3"),
        ("close", "3"),
        ("reopen", "4"),
        ("close", "4"),
    ]
    closes = [call for call in gh.calls if call[:2] == ("issue", "close")]
    assert all(call[call.index("--reason") + 1] == "completed" for call in closes)
    assert [
        call[call.index("--comment") + 1] for call in closes if call[2] in ("3", "4")
    ] == [f"Cleared in run {RUN_2}"] * 2


def test_live_check_outcomes_raise_findings_for_404_and_403_only(
    tmp_path: Path,
) -> None:
    report = _live_report(
        unreachable=[{"url": "https://a.example/gone", "status": 404}],
        inconclusive=[
            {"url": "https://b.example/blocked", "reason": "HTTP 403", "status": 403},
            {"url": "https://c.example/limited", "reason": "HTTP 429"},
            {"url": "https://d.example/slow", "reason": "timed out"},
        ],
    )

    file = _emit(LIVE_CHECK, "failure", report=report, tmp_path=tmp_path, **LIVE_ENV)

    assert _keys(file) == [
        "live-check/gone/https://a.example/gone",
        "live-check/status/https://b.example/blocked",
    ]
    assert file.scope == (
        "live-check/read",
        "live-check/gone/",
        "live-check/status/",
        "live-check/stale/",
        "live-check/archived/",
    )
    assert file.unchecked == (
        "live-check/gone/https://c.example/limited",
        "live-check/status/https://c.example/limited",
        "live-check/gone/https://d.example/slow",
        "live-check/status/https://d.example/slow",
        "live-check/stale/https://a.example/gone",
        "live-check/archived/https://a.example/gone",
    )


def test_budget_spent_urls_are_unchecked(tmp_path: Path) -> None:
    report = _live_report(
        inconclusive=[
            {"url": "https://a.example/x", "reason": "not checked: time budget spent"}
        ]
    )

    file = _emit(LIVE_CHECK, report=report, tmp_path=tmp_path, CHECK_RESULT="success")

    assert file.findings == ()
    assert "live-check/gone/https://a.example/x" in file.unchecked
    assert "live-check/status/https://a.example/x" in file.unchecked


def test_a_url_absent_from_the_report_closes_its_issue(tmp_path: Path) -> None:
    file = _emit(
        LIVE_CHECK,
        report=_live_report(),
        tmp_path=tmp_path,
        CHECK_RESULT="success",
    )
    path = tmp_path / "live.json"
    path.write_text(file.to_json())
    gh = alert_gh([alert_issue(3, "live-check/gone/https://removed.example/x")])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert issue_writes(gh) == [("close", "3")]


def test_unreadable_packs_raise_the_read_finding_and_scope_only_it(
    tmp_path: Path,
) -> None:
    file = _emit(
        LIVE_CHECK,
        "failure",
        report={"status": "failed", "error": "pack single-screen.json is unreadable"},
        tmp_path=tmp_path,
        **LIVE_ENV,
    )

    assert _keys(file) == ["live-check/read"]
    assert file.scope == ("live-check/read",)


def test_a_successful_read_scopes_the_read_key(
    tmp_path: Path,
) -> None:
    file = _emit(
        LIVE_CHECK,
        report=_live_report(),
        tmp_path=tmp_path,
        CHECK_RESULT="success",
    )

    assert "live-check/read" in file.scope


def test_live_check_report_is_ignored_when_the_check_step_did_not_run(
    tmp_path: Path,
) -> None:
    file = _emit(
        LIVE_CHECK,
        "failure",
        report=_live_report(unreachable=[{"url": "https://stale/x", "status": 404}]),
        tmp_path=tmp_path,
        CHECK_RESULT="skipped",
    )

    assert _keys(file) == _early(LIVE_CHECK)
    assert file.scope == ()


def test_live_check_without_a_report_after_a_failed_step_raises_the_early_failure(
    tmp_path: Path,
) -> None:
    file = _emit(LIVE_CHECK, "failure", tmp_path=tmp_path, **LIVE_ENV)

    assert _keys(file) == _early(LIVE_CHECK)
    assert "live-check/read" not in file.scope


def test_a_status_finding_does_not_account_for_an_unrelated_job_failure(
    tmp_path: Path,
) -> None:
    report = _live_report(
        inconclusive=[
            {"url": "https://b.example/blocked", "reason": "HTTP 403", "status": 403}
        ]
    )

    file = _emit(
        LIVE_CHECK,
        "failure",
        report=report,
        tmp_path=tmp_path,
        CHECK_RESULT="success",
    )

    assert _keys(file) == [
        "live-check/status/https://b.example/blocked",
        *_early(LIVE_CHECK),
    ]


@pytest.mark.parametrize("status", [True, None, "404"], ids=["bool", "absent", "text"])
def test_an_unreachable_status_that_is_not_an_int_is_left_out_of_the_text(
    tmp_path: Path, status: object
) -> None:
    item: dict[str, object] = {"url": "https://a.example/gone"}
    if status is not None:
        item["status"] = status

    file = _emit(
        LIVE_CHECK,
        "failure",
        report=_live_report(unreachable=[item]),
        tmp_path=tmp_path,
        **LIVE_ENV,
    )

    (finding,) = file.findings
    assert finding.title == "Project URL is gone: https://a.example/gone"
    assert finding.details == ("URL: https://a.example/gone",)


# --- emitter keys, titles and determinism ----------------------------------


def test_query_bearing_url_and_family_key_validly_and_round_trip_to_one_issue(
    tmp_path: Path,
) -> None:
    url = "https://dolphin-emu.org/download/?ref=btn&x=%20"
    live = _emit(
        LIVE_CHECK,
        report=_live_report(unreachable=[{"url": url, "status": 404}]),
        tmp_path=tmp_path,
        CHECK_RESULT="failure",
    )
    prepare = _emit(
        NIGHTLY_PREPARE,
        report=_build_report(
            uncategorizedFamilies=[{"family": "Ünï / Cödé?", "variants": []}]
        ),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert live.findings[0].key == (
        "live-check/gone/https://dolphin-emu.org/download/%3Fref%3Dbtn%26x%3D%2520"
    )
    path = tmp_path / "live.json"
    path.write_text(live.to_json())
    first = alert_gh()
    _run(first, Producer(LIVE_CHECK, path, "success"), url=RUN_1)
    (body,) = _bodies(first, "create")
    second = alert_gh(
        [
            {
                "number": 4,
                "title": live.findings[0].title,
                "body": body,
                "state": "open",
                "state_reason": None,
            }
        ]
    )
    _run(second, Producer(LIVE_CHECK, path, "success"), url=RUN_2)
    assert issue_writes(second) == []
    assert prepare.findings[0].key.startswith("build/uncategorized/")


def test_overlong_url_and_family_still_yield_a_valid_file_keeping_other_findings(
    tmp_path: Path,
) -> None:
    long_url = "https://example.com/" + "a/b?" * 2000
    long_family = "F" * 5000
    live = _emit(
        LIVE_CHECK,
        report=_live_report(
            unreachable=[
                {"url": long_url, "status": 404},
                {"url": "https://ok.example/gone", "status": 410},
            ]
        ),
        tmp_path=tmp_path,
        CHECK_RESULT="failure",
    )
    prepare = _emit(
        NIGHTLY_PREPARE,
        report=_build_report(
            uncategorizedFamilies=[
                {"family": long_family, "variants": []},
                {"family": "Short", "variants": []},
            ]
        ),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert len(live.findings) == 2
    assert "live-check/gone/https://ok.example/gone" in _keys(live)
    assert all(len(f.key) <= KEY_LIMIT for f in live.findings + prepare.findings)
    assert all(len(f.title) <= TITLE_LIMIT for f in live.findings + prepare.findings)
    assert "build/uncategorized/Short" in _keys(prepare)
    assert len(prepare.findings) == 2


def test_report_rows_with_lone_surrogates_still_yield_a_valid_file(
    tmp_path: Path,
) -> None:
    live = _emit(
        LIVE_CHECK,
        "failure",
        report=_live_report(
            unreachable=[
                {"url": "https://bad.example/\ud800", "status": 404},
                {"url": "https://ok.example/gone", "status": 404},
            ]
        ),
        tmp_path=tmp_path,
        CHECK_RESULT="failure",
    )
    prepare = _emit(
        NIGHTLY_PREPARE,
        report=_build_report(
            uncategorizedFamilies=[
                {"family": "Bad \udfff", "variants": ["\ud800"]},
                {"family": "Good", "variants": []},
            ]
        ),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert "live-check/gone/https://ok.example/gone" in _keys(live)
    assert len(live.findings) == 2
    assert "build/uncategorized/Good" in _keys(prepare)
    assert len(prepare.findings) == 2


def test_multiline_and_padded_subjects_give_one_line_trimmed_titles(
    tmp_path: Path,
) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        report=_build_report(
            uncategorizedFamilies=[
                {"family": "  two\nlines\r\n ", "variants": []},
                {"family": "", "variants": []},
                {"family": "x" * 400, "variants": []},
                {"family": "nul\x00bell\x07", "variants": []},
            ]
        ),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert file.findings[0].title == "Family has no category: two lines"
    assert file.findings[3].title == "Family has no category: nul bell"
    assert file.findings[1].title == "Family has no category:"
    assert file.findings[2].title.endswith("…")
    assert all(f.title == f.title.strip() for f in file.findings)


def test_findings_carry_no_per_run_values(tmp_path: Path) -> None:
    def both(**context: str) -> list[FindingsFile]:
        live = _live_report(
            unreachable=[{"url": "https://a.example/gone", "status": 404}]
        )
        build = _build_report(
            uncategorizedFamilies=[{"family": "Alpha", "variants": ["single-screen"]}]
        )
        return [
            _emit(
                LIVE_CHECK,
                "failure",
                report=live,
                tmp_path=tmp_path,
                CHECK_RESULT="failure",
                **context,
            ),
            _emit(
                NIGHTLY_PREPARE,
                "failure",
                report=build,
                tmp_path=tmp_path,
                PREPARE_STAGE="verify",
                PREPARE_STAGES="checkout,build,allowlist,README boundary,verify",
                **context,
            ),
            emit(
                CODM_CHECK,
                {"JOB_STATUS": "failure", "GENERATION_RESULT": "failure", **context},
            ),
            emit(
                NIGHTLY_PUBLISH,
                {"JOB_STATUS": "failure", "PUSH_OUTCOME": "failed", **context},
            ),
            emit(QUIVER_PUBLISH, {"JOB_STATUS": "failure", **context}),
        ]

    first = both(GITHUB_RUN_ID="7", GITHUB_SHA="a" * 40)
    second = both(
        GITHUB_RUN_ID="8",
        GITHUB_SHA="b" * 40,
        BASE_SHA="c" * 40,
        CANDIDATE_SHA="d" * 40,
        GITHUB_RUN_ATTEMPT="3",
    )

    assert first == second


def test_cli_emit_writes_a_whole_file_that_validates_as_its_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "nested" / "findings.json"
    monkeypatch.setenv("JOB_STATUS", "failure")
    monkeypatch.setenv("PUSH_OUTCOME", "failed")

    exit_code = alerts_module.main(["emit", "nightly-publish", "--output", str(output)])

    assert exit_code == 0
    parsed = parse_findings(NIGHTLY_PUBLISH, output.read_text())
    assert parsed is not None
    assert [f.key for f in parsed.findings] == ["nightly/publish/push"]
    assert not output.with_name("findings.json.partial").exists()


def test_cli_emit_reports_a_file_it_cannot_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file")
    monkeypatch.setenv("JOB_STATUS", "success")

    exit_code = alerts_module.main(
        ["emit", "nightly-publish", "--output", str(blocker / "findings.json")]
    )

    assert exit_code == 1
    assert capsys.readouterr().err == "emit failed: could not write the findings file\n"


def test_cli_emit_reads_a_report_from_the_given_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "live.json"
    report.write_text(
        json.dumps(_live_report(unreachable=[{"url": "https://a/b", "status": 404}]))
    )
    output = tmp_path / "findings.json"
    monkeypatch.setenv("JOB_STATUS", "failure")
    monkeypatch.setenv("CHECK_RESULT", "failure")

    alerts_module.main(
        ["emit", "live-check", "--report", str(report), "--output", str(output)]
    )

    parsed = parse_findings(LIVE_CHECK, output.read_text())
    assert parsed is not None
    assert [f.key for f in parsed.findings] == ["live-check/gone/https://a/b"]


ARCHIVE_ENV = {"ARCHIVE_RESULT": "success"}


def _archive_report(status: str = "success", **overrides: object) -> dict:
    report: dict = {"status": status, "dryRun": False, "targets": []}
    if status == "failed":
        report["error"] = "the bucket cannot be reached"
    return {**report, **overrides}


def test_archive_target_outcomes_raise_no_finding(tmp_path: Path) -> None:
    targets = [
        {
            "name": "A",
            "url": "https://github.com/a/a",
            "outcome": "failed",
            "error": "x",
        },
        {"name": "B", "url": "https://github.com/b/b", "outcome": "unreachable"},
        {"name": "C", "url": "https://github.com/c/c", "outcome": "not checked"},
        {"name": "D", "url": "https://github.com/d/d", "outcome": "archived"},
    ]

    file = _emit(
        RELEASE_ARCHIVE,
        report=_archive_report(targets=targets),
        tmp_path=tmp_path,
        **ARCHIVE_ENV,
    )

    assert file == FindingsFile(RELEASE_ARCHIVE, scope=("release-archive/read",))


def test_archive_run_that_cannot_read_packs_or_reach_bucket_raises_one_finding(
    tmp_path: Path,
) -> None:
    file = _emit(
        RELEASE_ARCHIVE,
        "failure",
        report=_archive_report("failed"),
        tmp_path=tmp_path,
        ARCHIVE_RESULT="failure",
    )

    assert _keys(file) == ["release-archive/read"]
    assert file.scope == ("release-archive/read",)


def test_archive_missing_report_raises_the_early_failure_finding(
    tmp_path: Path,
) -> None:
    file = _emit(
        RELEASE_ARCHIVE,
        "failure",
        tmp_path=tmp_path,
        ARCHIVE_RESULT="failure",
    )

    assert _keys(file) == _early(RELEASE_ARCHIVE)
    assert file.scope == ()


def test_archive_report_is_not_read_when_the_step_did_not_run(tmp_path: Path) -> None:
    file = _emit(
        RELEASE_ARCHIVE,
        "failure",
        report=_archive_report("failed"),
        tmp_path=tmp_path,
        ARCHIVE_RESULT="skipped",
    )

    assert _keys(file) == _early(RELEASE_ARCHIVE)


def test_archive_cancelled_job_keeps_only_the_early_failure_finding(
    tmp_path: Path,
) -> None:
    file = _emit(
        RELEASE_ARCHIVE,
        "cancelled",
        report=_archive_report("failed"),
        tmp_path=tmp_path,
        ARCHIVE_RESULT="cancelled",
    )

    assert _keys(file) == _early(RELEASE_ARCHIVE)
    assert file.scope == ()


def _reconcile_archive(
    tmp_path: Path, report: dict, issues: list[dict], status: str = "success"
) -> FakeGh:
    file = _emit(
        RELEASE_ARCHIVE,
        status,
        report=report,
        tmp_path=tmp_path,
        ARCHIVE_RESULT="failure" if status == "failure" else "success",
    )
    path = tmp_path / "archive.json"
    path.write_text(file.to_json())
    gh = alert_gh(issues)
    _run(gh, Producer(RELEASE_ARCHIVE, path, "success"))
    return gh


def test_healthy_archive_run_closes_an_open_run_level_issue(tmp_path: Path) -> None:
    gh = _reconcile_archive(
        tmp_path,
        _archive_report(),
        [alert_issue(1, "release-archive/read")],
    )

    assert issue_writes(gh) == [("close", "1")]


def test_failed_archive_run_opens_the_run_level_issue(tmp_path: Path) -> None:
    gh = _reconcile_archive(tmp_path, _archive_report("failed"), [], status="failure")

    assert issue_writes(gh) == [
        ("create", "Release archive could not read the packs or reach its bucket")
    ]
