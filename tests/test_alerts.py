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
    KEY_LIMIT,
    TITLE_LIMIT,
    Finding,
    FindingsFile,
    JobResult,
    Owner,
    Producer,
    ReconcileFailure,
    build_body,
    early_failure_finding,
    early_failure_key,
    encode_subject,
    marker_line,
    parse_findings,
    reconcile,
    subject_key,
    truncate_title,
)
from tests.publication_support import OK, CommandResult, FakeGh, failure

REPOSITORY = "mjkoo/omnipack"
RUN_1 = "https://github.com/mjkoo/omnipack/actions/runs/1"
RUN_2 = "https://github.com/mjkoo/omnipack/actions/runs/2"
LIST = ("api", "--paginate")
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


def _nightly(path: Path, result: JobResult | None = JobResult.SUCCESS) -> Producer:
    return Producer(Owner.NIGHTLY_PREPARE, path, result)


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
        Owner.LIVE_CHECK,
        FindingsFile(Owner.LIVE_CHECK, findings=(Finding(key, "t"),)).to_json(),
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


def test_early_failure_finding_is_fixed_per_owner() -> None:
    for owner in Owner:
        finding = early_failure_finding(owner)
        assert finding == early_failure_finding(owner)
        assert finding.key == early_failure_key(owner)
        assert finding.key.endswith("/run")
        assert owner.value in finding.title
        assert not any("http" in line for line in finding.details)
    assert early_failure_key(Owner.NIGHTLY_PREPARE) == "nightly/prepare/run"
    assert early_failure_key(Owner.LIVE_CHECK) == "live-check/run"
    assert early_failure_key(Owner.QUIVER_PUBLISH) == "quiver/publish/run"


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
    assert _parse(Owner.CODM_CHECK, **overrides) is None


def test_valid_findings_keep_raw_details_and_allow_long_ones() -> None:
    long_details = ["<b>" + "x" * 200_000]
    parsed = _parse(
        Owner.CODM_CHECK,
        findings=[_entry(CODM_STEP, title="x" * 255, details=long_details)],
        scope=["codm/check/"],
    )

    assert parsed is not None
    assert parsed.findings[0].details == tuple(long_details)
    assert parse_findings(Owner.CODM_CHECK, "{not json") is None
    assert parse_findings(Owner.CODM_CHECK, "[]") is None


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
        Owner.NIGHTLY_PREPARE,
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
    path = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
        scope=(NIGHTLY_STAGE,),
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")])

    _run(gh, _nightly(path))

    assert _verbs(gh) == []


def test_muted_issue_that_clears_is_marked_completed_and_then_recurs_reopened(
    tmp_path: Path,
) -> None:
    clear = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    muted = _issue(7, NIGHTLY_STAGE, state="closed", reason="not_planned")
    gh = _gh([muted])

    _run(gh, _nightly(clear))

    assert _verbs(gh) == [("reopen", "7"), ("close", "7")]
    close = next(call for call in gh.calls if call[:2] == ("issue", "close"))
    assert close[close.index("--reason") + 1] == "completed"
    assert close[close.index("--comment") + 1] == f"Cleared in run {RUN_2}"

    raise_again = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
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
        Owner.LIVE_CHECK,
        scope=("live-check/status/", "live-check/gone/"),
        unchecked=(key,),
    )
    other = _file(
        tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,), name="n.json"
    )
    gh = _gh([_issue(7, key, state="closed", reason="not_planned")])

    _run(gh, Producer(Owner.LIVE_CHECK, path, JobResult.SUCCESS), _nightly(other))

    assert _verbs(gh) == []


@pytest.mark.parametrize("reason", ["not_planned", "duplicate"])
def test_not_planned_and_duplicate_closures_are_mutes(
    tmp_path: Path, reason: str
) -> None:
    path = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("reopen", "7"), ("close", "7")]


@pytest.mark.parametrize("reason", ["completed", None])
def test_completed_or_unreasoned_closures_reopen_when_raised(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("reopen", "7"), ("edit", "7")]


@pytest.mark.parametrize("reason", ["completed", None])
def test_completed_closure_is_left_alone_when_the_finding_clears(
    tmp_path: Path, reason: str | None
) -> None:
    path = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    gh = _gh([_issue(7, NIGHTLY_STAGE, state="closed", reason=reason)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == []


def test_muted_403_does_not_hide_a_later_404(tmp_path: Path) -> None:
    url = "https://example.com/x"
    path = _file(
        tmp_path,
        Owner.LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        findings=(Finding(f"live-check/gone/{url}", "gone", ("404",)),),
    )
    gh = _gh(
        [_issue(7, f"live-check/status/{url}", state="closed", reason="not_planned")]
    )

    _run(gh, Producer(Owner.LIVE_CHECK, path, JobResult.SUCCESS))

    assert _verbs(gh)[0] == ("create", "gone")


def test_key_outside_scope_or_unchecked_is_left_unchanged(tmp_path: Path) -> None:
    path = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
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
        Owner.LIVE_CHECK,
        scope=("live-check/gone/", "live-check/status/"),
        unchecked=(kept,),
    )
    gh = _gh([_issue(1, kept), _issue(2, gone)])

    _run(gh, Producer(Owner.LIVE_CHECK, path, JobResult.SUCCESS))

    assert _verbs(gh) == [("close", "2")]


def test_creates_and_reopens_precede_closes(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        Owner.CODM_CHECK,
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

    _run(gh, Producer(Owner.CODM_CHECK, path, JobResult.FAILURE))

    verbs = [verb for verb, _ in _verbs(gh)]
    assert verbs == ["create", "reopen", "edit", "close"]


# --- issue identification --------------------------------------------------


def test_duplicate_keys_use_the_lowest_number(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("new",)),),
    )
    gh = _gh([[_issue(9, NIGHTLY_STAGE)], [_issue(4, NIGHTLY_STAGE, title="t")]])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [("edit", "4")]


def test_issues_without_a_valid_first_line_marker_are_ignored(tmp_path: Path) -> None:
    marker = marker_line(NIGHTLY_STAGE)
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.NIGHTLY_PREPARE,
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
        Owner.CODM_CHECK,
        scope=("codm/check/",),
        findings=(Finding("codm/check/verify", "verify", ("x",)),),
    )
    gh = _gh([_issue(1, "quiver/check/verify")])
    quiver = Producer(Owner.QUIVER_CHECK, tmp_path / "missing.json", JobResult.SKIPPED)

    _run(gh, Producer(Owner.CODM_CHECK, codm, JobResult.FAILURE), quiver)

    assert _verbs(gh) == [("create", "verify")]


def test_codm_early_failure_leaves_quivers_issue_open(tmp_path: Path) -> None:
    gh_codm = _gh([_issue(1, early_failure_key(Owner.QUIVER_CHECK))])
    _run(gh_codm, Producer(Owner.CODM_CHECK, tmp_path / "none.json", JobResult.FAILURE))

    assert _verbs(gh_codm) == [
        ("create", early_failure_finding(Owner.CODM_CHECK).title)
    ]

    gh_quiver = _gh([_issue(1, early_failure_key(Owner.CODM_CHECK))])
    quiver = _file(tmp_path, Owner.QUIVER_CHECK, scope=("quiver/check/",))
    _run(gh_quiver, Producer(Owner.QUIVER_CHECK, quiver, JobResult.SUCCESS))
    assert _verbs(gh_quiver) == []


def test_codm_and_quiver_reconcile_in_one_run_independently(tmp_path: Path) -> None:
    quiver = _file(tmp_path, Owner.QUIVER_CHECK, scope=("quiver/check/",))
    gh = _gh(
        [
            _issue(1, early_failure_key(Owner.QUIVER_CHECK)),
            _issue(
                2,
                early_failure_key(Owner.CODM_CHECK),
                title=early_failure_finding(Owner.CODM_CHECK).title,
                details=early_failure_finding(Owner.CODM_CHECK).details,
            ),
        ]
    )

    _run(
        gh,
        Producer(Owner.CODM_CHECK, tmp_path / "none.json", JobResult.FAILURE),
        Producer(Owner.QUIVER_CHECK, quiver, JobResult.SUCCESS),
    )

    assert ("close", "1") in _verbs(gh)
    assert ("close", "2") not in _verbs(gh)
    assert [v for v in _verbs(gh) if v[0] == "edit"] == []


def test_early_failure_issue_closes_when_the_producer_succeeds(tmp_path: Path) -> None:
    path = _file(tmp_path, Owner.LIVE_CHECK)
    gh = _gh([_issue(1, early_failure_key(Owner.LIVE_CHECK))])

    _run(gh, Producer(Owner.LIVE_CHECK, path, JobResult.SUCCESS))

    assert _verbs(gh) == [("close", "1")]


@pytest.mark.parametrize("result", [JobResult.SUCCESS, JobResult.FAILURE])
def test_missing_file_raises_the_early_failure_and_closes_nothing_else(
    tmp_path: Path, result: JobResult
) -> None:
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(tmp_path / "absent.json", result))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


def test_rejected_file_raises_the_early_failure_only(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


def test_foreign_key_is_rejected_with_the_early_failure_finding(tmp_path: Path) -> None:
    path = _file(
        tmp_path,
        Owner.LIVE_CHECK,
        scope=("live-check/",),
        findings=(Finding("live-check/gone/x", "gone", ()),),
    )
    data = json.loads(path.read_text())
    data["findings"].append(_entry("nightly/prepare/build"))
    path.write_text(json.dumps(data))
    gh = _gh([_issue(1, "live-check/gone/y")])

    _run(gh, Producer(Owner.LIVE_CHECK, path, JobResult.SUCCESS))

    assert _verbs(gh) == [("create", early_failure_finding(Owner.LIVE_CHECK).title)]


def test_pathologically_nested_file_is_rejected_with_the_early_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested.json"
    path.write_text("[" * 100_000 + "]" * 100_000)
    assert parse_findings(Owner.NIGHTLY_PREPARE, path.read_text()) is None
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(path))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


def test_job_result_parses_known_values_and_nothing_else() -> None:
    assert JobResult.parse("cancelled") is JobResult.CANCELLED
    assert JobResult.parse("success") is JobResult.SUCCESS
    assert JobResult.parse("") is None
    assert JobResult.parse("weird") is None
    assert JobResult.parse(None) is None


def test_symlinked_findings_file_is_rejected(tmp_path: Path) -> None:
    real = _file(tmp_path, Owner.NIGHTLY_PREPARE, scope=(NIGHTLY_STAGE,))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    gh = _gh([_issue(1, NIGHTLY_STAGE)])

    _run(gh, _nightly(link))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


def test_cancelled_producer_with_a_valid_file_raises_only_the_early_failure(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
        scope=("nightly/prepare/", NIGHTLY_STAGE),
        unchecked=(),
        findings=(Finding(NIGHTLY_STAGE, "build", ("boom",)),),
    )
    gh = _gh([_issue(1, "nightly/prepare/commit"), _issue(2, "build/x")])

    _run(gh, _nightly(path, JobResult.CANCELLED))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


def test_failed_producer_reporting_only_the_early_failure_closes_nothing(
    tmp_path: Path,
) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
        findings=(early_failure_finding(Owner.NIGHTLY_PREPARE),),
    )
    gh = _gh([_issue(1, NIGHTLY_STAGE), _issue(2, "build/uncategorized/x")])

    _run(gh, _nightly(path, JobResult.FAILURE))

    assert _verbs(gh) == [
        ("create", early_failure_finding(Owner.NIGHTLY_PREPARE).title)
    ]


@pytest.mark.parametrize("result", [JobResult.SKIPPED, None])
def test_producer_with_another_result_contributes_nothing(
    tmp_path: Path, result: JobResult | None
) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PUBLISH,
        scope=("nightly/publish/",),
        findings=(Finding("nightly/publish/push", "push", ()),),
    )
    gh = _gh([_issue(1, "nightly/publish/release"), _issue(2, "nightly/publish/run")])

    _run(gh, Producer(Owner.NIGHTLY_PUBLISH, path, result))

    assert _verbs(gh) == []


def test_oversized_details_keep_the_finding_with_an_overflow_count(
    tmp_path: Path,
) -> None:
    details = tuple("y" * 1000 for _ in range(200))
    path = _file(
        tmp_path,
        Owner.CODM_CHECK,
        scope=("codm/check/",),
        findings=(Finding(CODM_STEP, "verify", details),),
    )
    gh = _gh()

    _run(gh, Producer(Owner.CODM_CHECK, path, JobResult.FAILURE))

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
        Owner.NIGHTLY_PREPARE,
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
    monkeypatch.setenv("NIGHTLY_PREPARE_RESULT", "success")

    exit_code = alerts_module.main(
        ["reconcile", "--producer", f"nightly-prepare={path}"]
    )

    assert exit_code == 1
    assert summary_path.read_text() == f"reconcile failed: {reason}\n"
    assert "token leaked" not in summary_path.read_text()
    assert f"reconcile failed: {reason}" in capsys.readouterr().err


def test_unreadable_listing_fails_without_gh_output(tmp_path: Path) -> None:
    path = _file(tmp_path, Owner.NIGHTLY_PREPARE)
    gh = _gh(listing=CommandResult(0, "{not json", ""))

    with pytest.raises(ReconcileFailure, match="could not read the issue listing"):
        _run(gh, _nightly(path))


def test_cli_reconciles_producers_with_results_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(
        tmp_path,
        Owner.NIGHTLY_PREPARE,
        findings=(Finding(NIGHTLY_STAGE, "t", ("boom",)),),
    )
    gh = _gh()
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(alerts_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "2")
    monkeypatch.setenv("NIGHTLY_PREPARE_RESULT", "success")
    monkeypatch.setenv("NIGHTLY_PUBLISH_RESULT", "skipped")

    exit_code = alerts_module.main(
        [
            "reconcile",
            "--producer", f"nightly-prepare={path}",
            "--producer", f"nightly-publish={tmp_path / 'absent.json'}",
        ]
    )  # fmt: skip

    assert exit_code == 0
    assert _verbs(gh) == [("create", "t")]
    assert f"Run: {RUN_2}" in _bodies(gh, "create")[0]
    assert (
        summary_path.read_text()
        == "alerts: 1 opened, 0 updated, 0 reopened, 0 closed, 0 mute cleared\n"
    )
