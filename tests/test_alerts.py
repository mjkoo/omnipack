"""Tests for the findings model, validation and issue reconciliation.

This file imports only the standard library, pytest and the modules under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter.
"""

from __future__ import annotations

import json
import re
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
    PREPARE_STAGE_SLUGS,
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
from tests.publication_support import OK, CommandResult, FakeGh, failure

REPOSITORY = "mjkoo/omnipack"
RUN_1 = "https://github.com/mjkoo/omnipack/actions/runs/1"
RUN_2 = "https://github.com/mjkoo/omnipack/actions/runs/2"
LIST = ("api", "--paginate")
CODM_CHECK = Owner("check", "codm")
CODM_PUBLISH = Owner("publish", "codm")
QUIVER_CHECK = Owner("check", "quiver")
QUIVER_PUBLISH = Owner("publish", "quiver")
CODM_STEP = "codm/check/verify"
NIGHTLY_STAGE = "nightly/prepare/build"


def _issue(
    number: int,
    key: str,
    *,
    details: tuple[str, ...] = ("boom",),
    title: str | None = None,
    state: str = "open",
    reason: str | None = None,
    run: str = RUN_1,
    body: str | None = None,
) -> dict:
    return {
        "number": number,
        "title": title or f"title of {key}",
        "body": body
        if body is not None
        else build_body(Finding(key, "t", details), run),
        "state": state,
        "state_reason": reason,
    }


def _gh(
    issues: list[dict] | list[list[dict]] | None = None,
    *,
    label: CommandResult = OK,
    listing: CommandResult | None = None,
    **operations: CommandResult,
) -> FakeGh:
    pages = issues or []
    if pages and isinstance(pages[0], dict):
        pages = [pages]
    text = "".join(json.dumps(page) for page in pages) or "[]"
    responses = {
        ("label", "create"): label,
        LIST: listing or CommandResult(0, text, ""),
        ("issue", "create"): OK,
        ("issue", "edit"): OK,
        ("issue", "reopen"): OK,
        ("issue", "close"): OK,
    }
    responses.update(
        {tuple(name.split("_")): value for name, value in operations.items()}
    )
    return FakeGh(responses)


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


def _verbs(gh: FakeGh) -> list[tuple[str, ...]]:
    """Each issue write as (verb, number-or-title)."""
    writes = []
    for call in gh.calls:
        if call[0] == "issue":
            writes.append(
                (
                    call[1],
                    call[2] if call[1] != "create" else call[call.index("--title") + 1],
                )
            )
    return writes


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


# --- lifecycle -------------------------------------------------------------


def test_new_finding_opens_an_issue_with_label_title_and_body(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "Build failed", ("error <1>",)),),
    )
    gh = _gh()

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
    gh = _gh([_issue(7, NIGHTLY_STAGE)])

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
    gh = _gh([_issue(7, NIGHTLY_STAGE, title="t", details=("old message",))])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("edit", "7")]
    (body,) = _bodies(gh, "edit")
    assert "new message" in body
    assert f"Run: {RUN_2}" in body


def test_persisting_finding_with_changed_title_edits_the_issue(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "new title", ("boom",)),),
    )
    gh = _gh([_issue(7, NIGHTLY_STAGE, title="old title")])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("edit", "7")]


def test_unchanged_finding_makes_no_edit_across_runs_with_different_urls(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    first = _gh()
    _run(first, _nightly(path), url=RUN_1)
    (opened_body,) = _bodies(first, "create")
    existing = _issue(7, NIGHTLY_STAGE, title="t", body=opened_body)

    second = _gh([existing])
    _run(second, _nightly(path), url=RUN_2)
    third = _gh([{**existing, "body": opened_body.replace("\n", "\r\n")}])
    _run(third, _nightly(path), url="https://example.invalid/runs/3")

    assert _verbs(second) == []
    assert _verbs(third) == []


def test_muted_issue_stays_closed_while_the_finding_persists(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")])

    _run(gh, _nightly(path))

    assert _verbs(gh) == []


def test_muted_issue_that_clears_is_marked_completed_and_then_recurs_reopened(
    tmp_path: Path,
) -> None:
    clear = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    muted = _issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")
    gh = _gh([muted])

    _run(gh, _nightly(clear))

    assert _verbs(gh) == [("reopen", "7"), ("close", "7")]
    close = next(call for call in gh.calls if call[:2] == ("issue", "close"))
    assert close[close.index("--reason") + 1] == "completed"
    assert close[close.index("--comment") + 1] == f"Cleared in run {RUN_2}"

    raise_again = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
        name="again.json",
    )
    cleared = _issue(7, NIGHTLY_STAGE, state="closed", reason="completed")
    gh = _gh([cleared])

    _run(gh, _nightly(raise_again))

    assert _verbs(gh) == [("reopen", "7"), ("edit", "7")]


def test_mute_survives_a_run_that_did_not_re_check_the_key(tmp_path: Path) -> None:
    key = "live-check/status/https://example.com/x"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/status/", "live-check/gone/"),
        unchecked=(key,),
    )
    other = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,), name="n.json")
    gh = _gh([_issue(7, key, state="closed", reason="not_planned")])

    _run(gh, Producer(LIVE_CHECK, path, "success"), _nightly(other))

    assert _verbs(gh) == []


@pytest.mark.parametrize("reason", ["not_planned", "duplicate"])
def test_not_planned_and_duplicate_closures_are_mutes(
    tmp_path: Path, reason: str
) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("reopen", "7"), ("close", "7")]


@pytest.mark.parametrize("reason", ["completed", None])
def test_completed_or_unreasoned_closures_reopen_when_raised(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("reopen", "7"), ("edit", "7")]


@pytest.mark.parametrize("reason", ["completed", None])
def test_completed_closure_is_left_alone_when_the_finding_clears(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == []


def test_muted_403_does_not_hide_a_later_404(tmp_path: Path) -> None:
    url = "https://example.com/x"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        findings=(Finding(f"live-check/gone/{url}", "gone", ("404",)),),
    )
    gh = _gh(
        [_issue(7, f"live-check/status/{url}", state="closed", reason="not_planned")]
    )

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert _verbs(gh)[0] == ("create", "gone")


def test_key_outside_scope_or_unchecked_is_left_unchanged(tmp_path: Path) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = _gh(
        [
            _issue(1, "nightly/prepare/commit"),
            _issue(2, "nightly/prepare/build-extra"),
            _issue(3, "nightly/publish/release"),
            _issue(4, "codm/check/verify"),
        ]
    )

    _run(gh, _nightly(path))

    assert _verbs(gh) == []


def test_unchecked_key_under_a_scope_prefix_is_not_closed(tmp_path: Path) -> None:
    kept = "live-check/gone/https://example.com/kept"
    gone = "live-check/gone/https://example.com/gone"
    path = _file(
        tmp_path,
        LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        unchecked=(kept,),
    )
    gh = _gh([_issue(1, kept), _issue(2, gone)])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert _verbs(gh) == [("close", "2")]


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
    gh = _gh(
        [
            _issue(1, "codm/check/generation"),
            _issue(2, "codm/check/build", state="closed", reason="completed"),
        ]
    )

    _run(gh, Producer(CODM_CHECK, path, "failure"))

    verbs = [verb for verb, _ in _verbs(gh)]
    assert verbs == ["create", "reopen", "edit", "close"]


# --- issue identification --------------------------------------------------


def test_duplicate_keys_use_the_lowest_number(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("new",)),),
    )
    gh = _gh([[_issue(9, NIGHTLY_STAGE)], [_issue(4, NIGHTLY_STAGE, title="t")]])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("edit", "4")]


def test_issues_without_a_valid_first_line_marker_are_ignored(tmp_path: Path) -> None:
    marker = marker_line(NIGHTLY_STAGE)
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh(
        [
            _issue(1, NIGHTLY_STAGE, body="no marker at all"),
            _issue(2, NIGHTLY_STAGE, body=f"intro\n{marker}\n"),
            _issue(3, NIGHTLY_STAGE, body=f"{marker}{marker}\nmore"),
            _issue(4, NIGHTLY_STAGE, body=f"{marker} trailing\nmore"),
            _issue(5, NIGHTLY_STAGE, body=None) | {"body": None},
        ]
    )

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("create", "t")]


def test_pull_requests_in_the_listing_are_ignored(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh([_issue(1, NIGHTLY_STAGE) | {"pull_request": {}}])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("create", "t")]


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
    gh = _gh([_issue(8, other)])

    _run(gh, _nightly(path))

    (body,) = _bodies(gh, "create")
    assert body.split("\n")[0] == marker_line(NIGHTLY_STAGE)
    assert "&lt;!-- omnipack-alert-key: codm/check/verify --&gt;" in body
    assert "<b>" not in body
    assert _verbs(gh) == [("create", "t")]


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
    gh = _gh(
        [[_issue(1, "nightly/prepare/commit")], [_issue(2, NIGHTLY_STAGE, title="t")]]
    )

    _run(gh, _nightly(path))

    assert _verbs(gh) == []
    listing = next(call for call in gh.calls if call[:2] == LIST)
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
    gh = _gh(
        label=failure('label with name "omnipack-alert" already exists; use --force')
    )

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("create", "t")]
    assert gh.calls[0][:3] == ("label", "create", "omnipack-alert")


# --- producers -------------------------------------------------------------


def test_producer_findings_files_do_not_cross_owners(tmp_path: Path) -> None:
    codm = _file(
        tmp_path,
        CODM_CHECK,
        scope=("codm/check/",),
        findings=(Finding("codm/check/verify", "verify", ("x",)),),
    )
    gh = _gh([_issue(1, "quiver/check/verify")])
    quiver = Producer(QUIVER_CHECK, tmp_path / "missing.json", "skipped")

    _run(gh, Producer(CODM_CHECK, codm, "failure"), quiver)

    assert _verbs(gh) == [("create", "verify")]


def test_codm_early_failure_leaves_quivers_issue_open(tmp_path: Path) -> None:
    gh_codm = _gh([_issue(1, early_failure_key(QUIVER_CHECK))])
    _run(gh_codm, Producer(CODM_CHECK, tmp_path / "none.json", "failure"))

    assert _verbs(gh_codm) == [("create", early_failure_finding(CODM_CHECK).title)]

    gh_quiver = _gh([_issue(1, early_failure_key(CODM_CHECK))])
    quiver = _file(tmp_path, QUIVER_CHECK, scope=("quiver/check/",))
    _run(gh_quiver, Producer(QUIVER_CHECK, quiver, "success"))
    assert _verbs(gh_quiver) == []


def test_codm_and_quiver_reconcile_in_one_run_independently(tmp_path: Path) -> None:
    quiver = _file(tmp_path, QUIVER_CHECK, scope=("quiver/check/",))
    gh = _gh(
        [
            _issue(1, early_failure_key(QUIVER_CHECK)),
            _issue(
                2,
                early_failure_key(CODM_CHECK),
                title=early_failure_finding(CODM_CHECK).title,
                details=early_failure_finding(CODM_CHECK).details,
            ),
        ]
    )

    _run(
        gh,
        Producer(CODM_CHECK, tmp_path / "none.json", "failure"),
        Producer(QUIVER_CHECK, quiver, "success"),
    )

    assert ("close", "1") in _verbs(gh)
    assert ("close", "2") not in _verbs(gh)
    assert [v for v in _verbs(gh) if v[0] == "edit"] == []


def test_early_failure_issue_closes_when_the_producer_succeeds(tmp_path: Path) -> None:
    path = _file(tmp_path, LIVE_CHECK)
    gh = _gh([_issue(1, early_failure_key(LIVE_CHECK))])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert _verbs(gh) == [("close", "1")]


@pytest.mark.parametrize("result", ["success", "failure"])
def test_missing_file_raises_the_early_failure_and_closes_nothing_else(
    tmp_path: Path, result: StepOutcome
) -> None:
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(tmp_path / "absent.json", result))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


def test_rejected_file_raises_the_early_failure_only(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


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
    gh = _gh([_issue(1, "live-check/gone/y")])

    _run(gh, Producer(LIVE_CHECK, path, "success"))

    assert _verbs(gh) == [("create", early_failure_finding(LIVE_CHECK).title)]


def test_pathologically_nested_file_is_rejected_with_the_early_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested.json"
    path.write_text("[" * 100_000 + "]" * 100_000)
    assert parse_findings(NIGHTLY_PREPARE, path.read_text()) is None
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


def test_symlinked_findings_file_is_rejected(tmp_path: Path) -> None:
    real = _file(tmp_path, NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(link))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


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
    gh = _gh([_issue(1, "nightly/prepare/commit"), _issue(2, "build/x")])

    _run(gh, _nightly(path, "cancelled"))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


def test_failed_producer_reporting_only_the_early_failure_closes_nothing(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(early_failure_finding(NIGHTLY_PREPARE),),
    )
    gh = _gh([_issue(1, NIGHTLY_STAGE), _issue(2, "build/uncategorized/x")])

    _run(gh, _nightly(path, "failure"))

    assert _verbs(gh) == [("create", early_failure_finding(NIGHTLY_PREPARE).title)]


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
    gh = _gh([_issue(1, "nightly/publish/release"), _issue(2, "nightly/publish/run")])

    _run(gh, Producer(NIGHTLY_PUBLISH, path, result))

    assert _verbs(gh) == []


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
    gh = _gh()

    _run(gh, Producer(CODM_CHECK, path, "failure"))

    assert _verbs(gh) == [("create", "verify")]
    (body,) = _bodies(gh, "create")
    assert len(body) <= BODY_LIMIT
    assert re.search(r"\nand \d+ more\n</pre>", body)


# --- failures --------------------------------------------------------------


@pytest.mark.parametrize(
    ("knob", "issues", "reason"),
    [
        ("label", None, "could not create the label"),
        ("listing", None, "could not list issues"),
        ("issue_create", None, "could not create an issue"),
        (
            "issue_edit",
            [_issue(1, NIGHTLY_STAGE, title="old")],
            "could not update an issue",
        ),
        (
            "issue_close",
            [_issue(1, "nightly/prepare/commit")],
            "could not close an issue",
        ),
        (
            "issue_reopen",
            [_issue(1, NIGHTLY_STAGE, state="closed", reason="completed")],
            "could not reopen an issue",
        ),
    ],
)
def test_failed_gh_operation_fails_with_a_fixed_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        gh = _gh(issues, label=failure("token leaked"))
    elif knob == "listing":
        gh = _gh(issues, listing=failure("token leaked"))
    else:
        gh = _gh(issues, **{knob: failure("token leaked")})
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(alerts_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "2")

    exit_code = alerts_module.main(
        ["reconcile", "--producer", f"nightly-prepare=success:{path}"]
    )

    assert exit_code == 1
    assert summary_path.read_text() == f"reconcile failed: {reason}\n"
    assert "token leaked" not in summary_path.read_text()
    assert f"reconcile failed: {reason}" in capsys.readouterr().err


def test_unreadable_listing_fails_without_gh_output(tmp_path: Path) -> None:
    path = _file(tmp_path, NIGHTLY_PREPARE)
    gh = _gh(listing=CommandResult(0, "{not json", ""))

    with pytest.raises(ReconcileFailure, match="could not read the issue listing"):
        _run(gh, _nightly(path))


def test_cli_reconciles_producers_with_results_from_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh()
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(alerts_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "2")

    exit_code = alerts_module.main(
        [
            "reconcile",
            "--producer", f"nightly-prepare=success:{path}",
            "--producer", f"nightly-publish=skipped:{tmp_path / 'absent.json'}",
        ]
    )  # fmt: skip

    assert exit_code == 0
    assert _verbs(gh) == [("create", "t")]
    assert f"Run: {RUN_2}" in _bodies(gh, "create")[0]
    assert (
        summary_path.read_text()
        == "alerts: 1 opened, 0 updated, 0 reopened, 0 closed, 0 mute cleared\n"
    )


@pytest.mark.parametrize("result", ["", "weird"])
def test_cli_producer_with_an_empty_or_unknown_result_contributes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: str
) -> None:
    path = _file(
        tmp_path,
        NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh()
    monkeypatch.setattr(alerts_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "2")
    monkeypatch.setenv("NIGHTLY_PREPARE_RESULT", "success")

    exit_code = alerts_module.main(
        ["reconcile", "--producer", f"nightly-prepare={result}:{path}"]
    )

    assert exit_code == 0
    assert _verbs(gh) == []


@pytest.mark.parametrize(
    "value",
    [
        "nightly-prepare",
        "nightly-prepare=success",
        "nightly-prepare=success:",
        "bogus=success:f.json",
    ],
)
def test_cli_rejects_a_malformed_producer(value: str) -> None:
    with pytest.raises(SystemExit):
        alerts_module.main(["reconcile", "--producer", value])


# --- emitters --------------------------------------------------------------

STAGES = "checkout,build,allowlist,README boundary,verify,drift after verify"
HARMLESS_RUN_CONTEXT = {"GITHUB_RUN_ID": "7", "GITHUB_SHA": "a" * 40}


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
        **lists,
    }


def test_emit_requires_the_job_status(tmp_path: Path) -> None:
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


def test_failure_removing_stale_reports_leaves_checkout_out_of_scope(
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
    assert _keys(file) == ["nightly/prepare/build"]


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


def test_a_failed_stage_accounts_for_the_failed_job(tmp_path: Path) -> None:
    file = _emit(
        NIGHTLY_PREPARE,
        "failure",
        tmp_path=tmp_path,
        PREPARE_STAGE="verify",
        PREPARE_STAGES="checkout,build,allowlist,README boundary,verify",
    )

    assert early_failure_key(NIGHTLY_PREPARE) not in _keys(file)


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


def test_release_main_advanced_after_an_ok_push_scopes_only_the_push() -> None:
    file = _emit(
        NIGHTLY_PUBLISH,
        "failure",
        PUSH_OUTCOME="ok",
        RELEASE_OUTCOME="main-advanced",
    )

    assert file.scope == ("nightly/publish/push",)
    assert file.findings == ()


def test_release_ok_from_a_new_revision_scopes_the_release_key() -> None:
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


def test_source_publication_refused_as_main_advanced_raises_nothing() -> None:
    file = _emit(CODM_PUBLISH, "failure", PUBLISH_OUTCOME="main-advanced")

    assert file.findings == ()
    assert file.scope == ()


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
    return {"status": "success", "unreachable": [], "inconclusive": [], **overrides}


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
    assert file.scope == ("live-check/read", "live-check/gone/", "live-check/status/")
    assert file.unchecked == (
        "live-check/gone/https://c.example/limited",
        "live-check/status/https://c.example/limited",
        "live-check/gone/https://d.example/slow",
        "live-check/status/https://d.example/slow",
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


def test_a_url_absent_from_the_report_falls_in_scope(tmp_path: Path) -> None:
    file = _emit(
        LIVE_CHECK,
        report=_live_report(),
        tmp_path=tmp_path,
        CHECK_RESULT="success",
    )

    assert alerts_module._in_scope(
        "live-check/gone/https://removed.example/x", file.scope
    )
    assert file.unchecked == ()


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


def test_a_successful_read_scopes_the_read_key_so_a_stale_issue_closes(
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
    first = _gh()
    _run(first, Producer(LIVE_CHECK, path, "success"), url=RUN_1)
    (body,) = _bodies(first, "create")
    second = _gh(
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
    assert _verbs(second) == []
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
            ]
        ),
        tmp_path=tmp_path,
        PREPARE_STAGE="complete",
        PREPARE_STAGES=STAGES,
    )

    assert file.findings[0].title == "Family has no category: two lines"
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

    first = both(**HARMLESS_RUN_CONTEXT)
    second = both(
        GITHUB_RUN_ID="8",
        GITHUB_SHA="b" * 40,
        BASE_SHA="c" * 40,
        CANDIDATE_SHA="d" * 40,
        GITHUB_RUN_ATTEMPT="3",
    )

    assert first == second
    for file in first:
        assert "a" * 40 not in file.to_json()


def test_cli_emit_writes_a_file_reconcile_accepts(
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


def test_prepare_stage_slugs_make_valid_keys() -> None:
    for slug in PREPARE_STAGE_SLUGS.values():
        key = "nightly/prepare/" + slug
        assert alerts_module.valid_key(NIGHTLY_PREPARE, key)
