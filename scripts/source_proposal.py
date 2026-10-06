"""GitHub Actions entrypoints for the guarded source-update proposal jobs.

This module runs in both the read-only check job (`stage`, under the synced
project environment) and the write job (`publish`, on the runner's
preinstalled `python3`, with no project environment installed). It therefore
imports only the standard library and the `scripts` package, so it must not
import anything from `omnipack` or from a module that does.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

from scripts.workflow_support import (
    FULL_SHA,
    DiffEntry,
    FileProblem,
    GhRunner,
    HandoffRejected,
    SubprocessGhRunner,
    append_summary,
    bot_commit,
    diff_raw_entries,
    expect,
    git,
    git_output,
    git_text,
    log,
    ls_remote_sha,
    regular_file_problem,
    require_env,
    run_url,
    verify_handoff,
    write_github_output,
)

CANONICAL_REPOSITORY = "mjkoo/omnipack"
CANONICAL_OWNER = "mjkoo"


SourceName = Literal["codm", "quiver"]


@dataclass(frozen=True)
class SourceDescriptor:
    name: SourceName
    branch: str
    catalog: str
    candidate: str
    report: str
    subject: str


SOURCES: Mapping[SourceName, SourceDescriptor] = {
    name: SourceDescriptor(
        name,
        f"automation/{name}-catalog",
        f"config/catalogs/{name}.json",
        f".build/source-generation/{name}/catalog.json",
        f".build/source-generation/{name}/report.json",
        f"chore(catalog): update reviewed {name} source",
    )
    for name in get_args(SourceName)
}
GENERATION_SUCCESS_STATUS = "success"
HANDOFF_DIRECTORY = "source-handoff"
BUNDLE_NAME = "candidate.bundle"
BODY_NAME = "pr-body.md"
# GitHub rejects a pull request body longer than this many characters.
PR_BODY_LIMIT = 65536
# GitHub rejects a step summary over 1 MiB. The bound counts characters, and
# a character takes at most four bytes in UTF-8, so this stays under it.
SUMMARY_LIMIT = 250_000
# Shown when the candidate's bytes differ from the catalog's but no entry was
# added, removed or changed, so a reviewer is not left with three empty lists.
BYTES_ONLY_CHANGE = "Catalog bytes changed without entry changes"

# The values GitHub reports for a step's `outcome`.
StepOutcome = Literal["success", "failure", "skipped", "cancelled"]
STEP_OUTCOMES: frozenset[StepOutcome] = frozenset(get_args(StepOutcome))
# The summary reports this for a step whose outcome is absent or unrecognized.
StepResult = StepOutcome | Literal["unavailable"]
VALIDATION_STEPS = ("generation", "staging", "tests", "build", "verify", "guard")


# --- stage (read-only check job) -----------------------------------------


StageStatus = Literal["unchanged", "changed", "failed"]
StageName = Literal[
    "checkout", "base", "files", "report", "write", "commit", "bundle", "complete"
]


@dataclass(frozen=True)
class StageOutcome:
    """The outcome of one guarded `stage` run.

    `stage` names the failing stage on failure, or `"complete"` otherwise, and
    `reason` says what failed in fixed text that holds no upstream data.
    """

    status: StageStatus
    stage: StageName
    base_sha: str | None
    sha: str | None
    report: Mapping[str, object] = field(default_factory=dict)
    reason: str = ""

    @property
    def changed(self) -> bool:
        return self.status == "changed"

    @property
    def summary(self) -> str:
        if self.status == "failed":
            return f"stage failed: {self.reason or self.stage}"
        return _render_report(
            self.report,
            base_sha=self.base_sha or "",
            run_url=None,
            catalog_changed=self.changed,
            limit=SUMMARY_LIMIT,
        )


def run_stage(
    root: Path,
    github_sha: str,
    run_url: str,
    bundle_path: Path,
    *,
    source: SourceName = "codm",
) -> StageOutcome:
    """Copy the generated candidate over the reviewed catalog and commit it.

    Runs in the read-only job. When the catalog changes, it commits only that
    file on a fresh local branch and hands the commit to the write job as a
    bundle. The PR body is written later by `summarize`, and only once every
    check has succeeded.
    """
    descriptor = SOURCES[source]
    try:
        head = git_text(root, "rev-parse", "HEAD")
    except OSError:
        return _stage_failure("checkout", "could not read HEAD", None)
    if head != github_sha:
        return _stage_failure("checkout", "HEAD is not GITHUB_SHA", head)
    base_sha = head

    candidate_path = root / descriptor.candidate
    catalog_path = root / descriptor.catalog
    report_path = root / descriptor.report

    for relative in (descriptor.candidate, descriptor.catalog):
        problem = regular_file_problem(root / relative)
        if problem is not None:
            return _stage_failure(
                "files", f"{relative} is {_FILE_PROBLEMS[problem]}", base_sha
            )

    try:
        report = json.loads(report_path.read_bytes())
        candidate_bytes = candidate_path.read_bytes()
    except (OSError, ValueError):
        return _stage_failure(
            "report", "could not read the generation report or candidate", base_sha
        )
    if (
        not isinstance(report, dict)
        or report.get("status") != GENERATION_SUCCESS_STATUS
    ):
        return _stage_failure("report", "generation did not succeed", base_sha)

    try:
        base_entry = git_text(root, "ls-tree", base_sha, "--", descriptor.catalog)
        if not base_entry.startswith("100644 blob "):
            return _stage_failure(
                "base", "base catalog is not a regular mode 100644 file", base_sha
            )
        if git_text(root, "diff", "--cached", "--name-only"):
            return _stage_failure("base", "index contains staged changes", base_sha)
        base_bytes = git_output(root, "show", f"{base_sha}:{descriptor.catalog}")
    except OSError:
        return _stage_failure("base", "could not read the base catalog", base_sha)

    try:
        catalog_path.write_bytes(candidate_bytes)
        catalog_path.chmod(0o644)
    except OSError:
        return _stage_failure("write", "could not write the catalog", base_sha)

    changed = candidate_bytes != base_bytes
    sha = base_sha
    if changed:
        try:
            sha = _commit_candidate(root, base_sha, run_url, descriptor)
        except OSError:
            return _stage_failure("commit", "could not commit the candidate", base_sha)
        try:
            if git_text(root, "rev-parse", "HEAD") != sha:
                return _stage_failure(
                    "bundle", "HEAD is not the candidate commit", base_sha
                )
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            git_output(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
        except OSError:
            return _stage_failure("bundle", "could not write the bundle", base_sha)

    status: StageStatus = "changed" if changed else "unchanged"
    return StageOutcome(status, "complete", base_sha, sha, report)


_FILE_PROBLEMS: Mapping[FileProblem, str] = {
    "missing": "missing",
    "symlink": "a symlink",
    "irregular": "not a regular file",
}


def _stage_failure(stage: StageName, reason: str, base_sha: str | None) -> StageOutcome:
    return StageOutcome("failed", stage, base_sha, None, reason=reason)


def _report_changes(
    report: Mapping[str, object],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None:
    """The added, removed and changed URLs, or None when the report has no
    changes because generation failed before writing a candidate."""
    changes = report.get("changes")
    if not isinstance(changes, dict):
        return None
    return (
        tuple(url for url in changes.get("added", ()) or () if isinstance(url, str)),
        tuple(url for url in changes.get("removed", ()) or () if isinstance(url, str)),
        tuple(url for url in changes.get("changed", ()) or () if isinstance(url, str)),
    )


def _report_skipped(report: Mapping[str, object]) -> tuple[str, ...]:
    """One line per skipped listing: what it was, then why it was skipped."""
    raw = report.get("skipped")
    if not isinstance(raw, list):
        return ()
    lines: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            listing = {key: value for key, value in item.items() if key != "reason"}
            text = json.dumps(listing, ensure_ascii=False, sort_keys=True)
            lines.append(f"{text}: {item.get('reason')}")
    return tuple(lines)


def _render_report(
    report: Mapping[str, object],
    *,
    base_sha: str,
    run_url: str | None,
    catalog_changed: bool,
    limit: int,
) -> str:
    """Render a generation report inside an escaped `<pre>` block.

    A failed report has no changes, so it shows no change sections rather
    than empty ones. When the text would exceed `limit`, entries that do not
    fit are left out and counted, while every section header stays.
    """
    head: list[str] = []
    if run_url is not None:
        head += [f"Workflow run: {run_url}", ""]
    head += [f"Base SHA: {base_sha}", "", "<pre>"]
    notes: list[str] = []
    error = report.get("error")
    if isinstance(error, str):
        notes.append(f"Error: {error}")
    sections: list[tuple[str, Sequence[str]]] = []
    changes = _report_changes(report)
    if changes is not None:
        added, removed, changed = changes
        if catalog_changed and not (added or removed or changed):
            notes.append(BYTES_ONLY_CHANGE)
        sections += [("Added:", added), ("Removed:", removed), ("Changed:", changed)]
    sections.append(("Skipped:", _report_skipped(report)))
    escaped_notes = [html.escape(note) for note in notes]
    escaped_sections = [
        (header, [html.escape(line) for line in lines]) for header, lines in sections
    ]

    def render(kept_notes: list[str], kept: list[list[str]], omitted: int) -> str:
        lines = list(head)
        for note in kept_notes:
            lines += [note, ""]
        for index, (header, _) in enumerate(escaped_sections):
            if index:
                lines.append("")
            lines += [header, *kept[index]]
        if omitted:
            lines.append(f"and {omitted} more")
        return "\n".join([*lines, "</pre>"]) + "\n"

    full = render(escaped_notes, [lines for _, lines in escaped_sections], 0)
    if len(full) <= limit:
        return full
    # Keep what fits, in order, leaving room for the longest omission line.
    # The full diagnostics remain in the generation report.
    total = len(escaped_notes) + sum(len(lines) for _, lines in escaped_sections)
    budget = limit - len(render([], [[] for _ in escaped_sections], total))
    kept_notes: list[str] = []
    for note in escaped_notes:
        if len(note) + 2 <= budget:
            kept_notes.append(note)
            budget -= len(note) + 2
    kept: list[list[str]] = []
    for _, lines in escaped_sections:
        kept.append([])
        for line in lines:
            if len(line) + 1 <= budget:
                kept[-1].append(line)
                budget -= len(line) + 1
    omitted = total - len(kept_notes) - sum(len(lines) for lines in kept)
    return render(kept_notes, kept, omitted)


def _commit_candidate(
    root: Path, base_sha: str, run_url: str, descriptor: SourceDescriptor
) -> str:
    git_output(root, "checkout", "-q", "-B", descriptor.branch)
    git_output(root, "add", "--", descriptor.catalog)
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    return bot_commit(root, descriptor.subject, body)


# --- publish (write job) --------------------------------------------------


class PublishFailure(RuntimeError):
    def __init__(self, summary: str) -> None:
        super().__init__(summary)
        self.summary = summary


PublishStatus = Literal["closed", "unchanged", "published", "failed"]


@dataclass(frozen=True)
class PublishOutcome:
    status: PublishStatus
    summary: str


def run_publish(
    root: Path,
    changed: str,
    candidate_sha: str,
    base_sha: str,
    bundle_path: Path | None,
    body_path: Path | None,
    *,
    gh: GhRunner | None = None,
    source: SourceName = "codm",
) -> PublishOutcome:
    """Close a stale proposal, or push and open or refresh the source-update PR.

    Every check below runs before any remote write, so a rejected hand-off or
    an advanced main changes neither the bot branch nor any PR.
    """
    descriptor = SOURCES[source]
    selected_gh = gh or SubprocessGhRunner()
    generic = "publish failed"
    try:
        if changed not in ("true", "false"):
            raise PublishFailure(generic)
        if (
            FULL_SHA.fullmatch(base_sha) is None
            or FULL_SHA.fullmatch(candidate_sha) is None
        ):
            raise PublishFailure(generic)
        is_changed = changed == "true"

        auth_result = selected_gh.run(["auth", "setup-git"])
        if auth_result.returncode != 0:
            raise PublishFailure(f"{generic}: gh auth setup-git failed")

        remote_main = ls_remote_sha(root, "refs/heads/main")
        if remote_main is None:
            raise PublishFailure(f"{generic}: could not read remote main")
        if remote_main != base_sha:
            raise PublishFailure(f"{generic}: main advanced")

        selected_number = _selected_pr_number(selected_gh, descriptor)

        if not is_changed:
            if selected_number is None:
                return PublishOutcome("unchanged", "publish made no change")
            close_result = selected_gh.run(
                ["pr", "close", str(selected_number), "--repo", CANONICAL_REPOSITORY]
            )
            if close_result.returncode != 0:
                raise PublishFailure(f"{generic}: PR close failed")
            return PublishOutcome("closed", f"publish closed PR #{selected_number}")

        rejected = f"{generic}: hand-off rejected"
        if bundle_path is None:
            raise PublishFailure(rejected)
        try:
            entries = verify_handoff(root, bundle_path, candidate_sha, base_sha)
        except HandoffRejected as rejection:
            log(f"hand-off rejected: {rejection}")
            raise PublishFailure(rejected) from None
        if not _catalog_only_diff(entries, descriptor):
            log(
                "hand-off rejected: the candidate changes a file other than the "
                "catalog, or the catalog's mode"
            )
            raise PublishFailure(rejected)

        body_problem = "missing" if body_path is None else _body_problem(body_path)
        if body_problem is not None:
            log(f"PR body rejected: {body_problem}")
            raise PublishFailure(f"{generic}: PR body rejected")

        unreadable = f"{generic}: could not read remote branch"
        remote_branch_sha = ls_remote_sha(root, f"refs/heads/{descriptor.branch}")
        if remote_branch_sha is None:
            raise PublishFailure(unreadable)
        needs_push = True
        if remote_branch_sha:
            expect(
                git(
                    root,
                    "fetch",
                    "--quiet",
                    "origin",
                    f"refs/heads/{descriptor.branch}",
                ),
                PublishFailure,
                unreadable,
            )
            remote_tree = expect(
                git(root, "rev-parse", "FETCH_HEAD^{tree}"), PublishFailure, unreadable
            ).strip()
            candidate_tree = expect(
                git(root, "rev-parse", f"{candidate_sha}^{{tree}}"),
                PublishFailure,
                unreadable,
            ).strip()
            needs_push = remote_tree != candidate_tree

        if needs_push:
            push_result = git(
                root,
                "push",
                "--force",
                "origin",
                f"{candidate_sha}:refs/heads/{descriptor.branch}",
            )
            if push_result.returncode != 0:
                raise PublishFailure(f"{generic}: branch push failed")

        if selected_number is not None:
            edit_result = selected_gh.run(
                [
                    "pr",
                    "edit",
                    str(selected_number),
                    "--repo",
                    CANONICAL_REPOSITORY,
                    "--body-file",
                    str(body_path),
                ]
            )
            if edit_result.returncode != 0:
                raise PublishFailure(f"{generic}: PR edit failed")
            return PublishOutcome("published", f"publish updated PR #{selected_number}")

        create_result = selected_gh.run(
            [
                "pr",
                "create",
                "--repo",
                CANONICAL_REPOSITORY,
                "--title",
                descriptor.subject,
                "--body-file",
                str(body_path),
                "--base",
                "main",
                "--head",
                descriptor.branch,
            ]
        )
        if create_result.returncode != 0:
            raise PublishFailure(f"{generic}: PR create failed")
        return PublishOutcome("published", "publish created PR")
    except PublishFailure as failure:
        return PublishOutcome("failed", failure.summary)


def _selected_pr_number(gh: GhRunner, descriptor: SourceDescriptor) -> int | None:
    result = gh.run(
        [
            "pr",
            "list",
            "--repo",
            CANONICAL_REPOSITORY,
            "--head",
            descriptor.branch,
            "--base",
            "main",
            "--state",
            "open",
            "--json",
            "number,isCrossRepository,headRepositoryOwner,headRefName,baseRefName",
        ]
    )
    unreadable = "publish failed: PR list failed"
    if result.returncode != 0:
        raise PublishFailure(unreadable)
    try:
        candidates = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise PublishFailure(unreadable) from None
    if not isinstance(candidates, list):
        raise PublishFailure(unreadable)
    selected = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("headRefName") == descriptor.branch
        and item.get("baseRefName") == "main"
        and item.get("isCrossRepository") is False
        and isinstance(item.get("headRepositoryOwner"), dict)
        and item["headRepositoryOwner"].get("login") == CANONICAL_OWNER
    ]
    if len(selected) > 1:
        raise PublishFailure("publish failed: more than one source-update PR")
    if not selected:
        return None
    number = selected[0].get("number")
    if not isinstance(number, int):
        raise PublishFailure(unreadable)
    return number


def _body_problem(body_path: Path) -> str | None:
    """Why the PR body file cannot be sent to `gh`, or None.

    The file must be a regular file (checked with `lstat`, so a symlink to a
    runner file is refused), valid UTF-8, and within GitHub's length limit.
    """
    problem = regular_file_problem(body_path)
    if problem is not None:
        return problem
    try:
        text = body_path.read_bytes().decode("utf-8")
    except OSError:
        return "unreadable"
    except UnicodeDecodeError:
        return "not UTF-8"
    if len(text) > PR_BODY_LIMIT:
        return "too long"
    return None


def _catalog_only_diff(
    entries: Sequence[DiffEntry], descriptor: SourceDescriptor
) -> bool:
    """Exactly one entry: the catalog, at mode 100644 on both sides."""
    return len(entries) == 1 and entries[0] == (descriptor.catalog, "100644", "100644")


# --- shared CLI plumbing ---------------------------------------------------


def _handoff_directory(environ: Mapping[str, str]) -> Path:
    return Path(require_env(environ, "RUNNER_TEMP")) / HANDOFF_DIRECTORY


def _report_outcome(environ: Mapping[str, str], summary: str, *, failed: bool) -> int:
    """Record one command's outcome and return its exit code.

    The step summary always carries it. A failure also goes to the job log, so
    `gh run view --log-failed` names the cause. Only failure summaries are
    logged, and those hold fixed text rather than upstream data.
    """
    append_summary(environ, summary + "\n")
    if failed:
        log(summary)
    return 1 if failed else 0


def _run_stage_command(
    environ: Mapping[str, str],
    *,
    root: Path | None = None,
    source: SourceName = "codm",
) -> int:
    selected_root = root or Path.cwd()
    outcome = run_stage(
        selected_root,
        environ.get("GITHUB_SHA", ""),
        run_url(environ),
        _handoff_directory(environ) / BUNDLE_NAME,
        source=source,
    )
    if outcome.status != "failed":
        write_github_output(
            environ,
            {
                "changed": "true" if outcome.changed else "false",
                "sha": outcome.sha or "",
                "base": outcome.base_sha or "",
            },
        )
    return _report_outcome(environ, outcome.summary, failed=outcome.status == "failed")


def _run_publish_command(
    environ: Mapping[str, str],
    bundle_path: Path | None,
    body_path: Path | None,
    *,
    root: Path | None = None,
    source: SourceName = "codm",
) -> int:
    selected_root = root or Path.cwd()
    outcome = run_publish(
        selected_root,
        environ.get("CHANGED", ""),
        environ.get("CANDIDATE_SHA", ""),
        environ.get("BASE_SHA", ""),
        bundle_path,
        body_path,
        source=source,
    )
    return _report_outcome(environ, outcome.summary, failed=outcome.status == "failed")


def _run_guard_command(environ: Mapping[str, str], source: SourceName) -> int:
    descriptor = SOURCES[source]
    root = Path.cwd()
    sha = environ.get("CANDIDATE_SHA", "")
    base = environ.get("BASE_SHA", "")
    try:
        if FULL_SHA.fullmatch(sha) is None or FULL_SHA.fullmatch(base) is None:
            raise ValueError("invalid checked revision")
        if git_text(root, "rev-parse", f"{sha}^@") != base:
            raise ValueError("checked commit does not have the expected single parent")
        if not _catalog_only_diff(diff_raw_entries(root, base, sha), descriptor):
            raise ValueError("checked commit is not scoped to the selected source")
        path = root / descriptor.catalog
        if regular_file_problem(path) is not None:
            raise ValueError("workspace catalog is not a regular file")
        if path.read_bytes() != git_output(root, "show", f"{sha}:{descriptor.catalog}"):
            raise ValueError("workspace catalog differs from the checked commit")
        if path.stat().st_mode & 0o111:
            raise ValueError("workspace catalog is executable")
    except (OSError, ValueError, HandoffRejected) as error:
        return _report_outcome(environ, f"guard failed: {error}", failed=True)
    return 0


def _step_result(value: str) -> StepResult:
    return value if value in STEP_OUTCOMES else "unavailable"


def _render_validation(results: Mapping[str, StepResult]) -> str:
    lines = [f"{step}: {result}" for step, result in results.items()]
    return "Validation outcomes:\n" + "\n".join(lines) + "\n"


def render_pr_body(
    report: Mapping[str, object],
    *,
    base_sha: str,
    run_url: str,
    results: Mapping[str, StepResult],
) -> str:
    """The escaped PR body: the run, base, changes, skipped listings and results.

    The report section is bounded so the whole body, including the validation
    results, stays within GitHub's length limit. A body is written only for a
    candidate that changed the catalog.
    """
    validation = _render_validation(results)
    report_text = _render_report(
        report,
        base_sha=base_sha,
        run_url=run_url,
        catalog_changed=True,
        limit=PR_BODY_LIMIT - len(validation) - 1,
    )
    return report_text + "\n" + validation


def _run_summary_command(environ: Mapping[str, str], source: SourceName) -> int:
    """Summarize the run, and write the PR body only when every step succeeded.

    Writing the body here, after the checks, means the write job can only ever
    receive a body for a candidate that passed them.
    """
    descriptor = SOURCES[source]
    results = {
        step: _step_result(environ.get(step.upper() + "_RESULT", ""))
        for step in VALIDATION_STEPS
    }
    validation = _render_validation(results)
    base = environ.get("BASE_SHA", "")
    if FULL_SHA.fullmatch(base) is None:
        base = "unavailable (no staged base revision)"
    try:
        report = json.loads(Path(descriptor.report).read_bytes())
        if not isinstance(report, dict):
            raise TypeError("malformed report")
    except (OSError, ValueError, TypeError):
        summary = f"Source: {source}\nBase SHA: {base}\ngeneration report unavailable\n"
    else:
        summary = _render_report(
            report,
            base_sha=base,
            run_url=run_url(environ),
            catalog_changed=environ.get("CHANGED") == "true",
            limit=SUMMARY_LIMIT - len(validation) - 1,
        )
        if all(result == "success" for result in results.values()):
            body_path = _handoff_directory(environ) / BODY_NAME
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_text(
                render_pr_body(
                    report, base_sha=base, run_url=run_url(environ), results=results
                ),
                encoding="utf-8",
            )
    append_summary(environ, summary + "\n" + validation)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.source_proposal")
    subparsers = parser.add_subparsers(dest="command", required=True)
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--source", choices=SOURCES, default="codm")
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--source", choices=SOURCES, default="codm")
    publish_parser.add_argument("--bundle", type=Path, default=None)
    publish_parser.add_argument("--body-file", type=Path, default=None)
    for name in ("guard", "summarize"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("--source", choices=SOURCES, default="codm")
    arguments = parser.parse_args(argv)
    environ = os.environ

    if arguments.command == "stage":
        return _run_stage_command(environ, source=arguments.source)
    if arguments.command == "guard":
        return _run_guard_command(environ, arguments.source)
    if arguments.command == "summarize":
        return _run_summary_command(environ, arguments.source)
    return _run_publish_command(
        environ, arguments.bundle, arguments.body_file, source=arguments.source
    )


if __name__ == "__main__":
    sys.exit(main())
