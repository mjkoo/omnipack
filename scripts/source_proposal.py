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
from dataclasses import dataclass
from pathlib import Path

from scripts.workflow_support import (
    FULL_SHA,
    DiffEntry,
    GhRunner,
    HandoffRejected,
    SubprocessGhRunner,
    append_summary,
    bot_commit,
    expect,
    git,
    git_output,
    git_text,
    ls_remote_sha,
    regular_file_problem,
    require_env,
    run_url,
    verify_handoff,
    write_github_output,
)

CANONICAL_REPOSITORY = "mjkoo/omnipack"
CANONICAL_OWNER = "mjkoo"
BRANCH_NAME = "automation/codm-catalog"
CATALOG_PATH = "config/catalogs/codm.json"
CANDIDATE_PATH = ".build/source-generation/codm/catalog.json"
REPORT_PATH = ".build/source-generation/codm/report.json"
HANDOFF_DIRECTORY = "source-handoff"
BUNDLE_NAME = "candidate.bundle"
BODY_NAME = "pr-body.md"
COMMIT_SUBJECT = "chore(catalog): update reviewed codm source"
PR_TITLE = COMMIT_SUBJECT


# --- stage (read-only check job) -----------------------------------------


@dataclass(frozen=True)
class StageOutcome:
    """The outcome of one guarded `stage` run.

    `stage` names the failing stage on failure, or `"complete"` otherwise.
    """

    status: str  # "unchanged", "changed" or "failed"
    stage: str
    base_sha: str | None
    sha: str | None
    changed: bool
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed_urls: tuple[str, ...] = ()
    retained_failures: tuple[tuple[str, str], ...] = ()

    @property
    def summary(self) -> str:
        if self.status == "failed":
            return self.stage
        return _render_report(
            base_sha=self.base_sha or "",
            run_url=None,
            added=self.added,
            removed=self.removed,
            changed=self.changed_urls,
            retained_failures=self.retained_failures,
        )


def run_stage(
    root: Path,
    github_sha: str,
    run_url: str,
    bundle_path: Path,
    body_path: Path,
) -> StageOutcome:
    """Copy the generated candidate over the reviewed catalog and commit it.

    Runs in the read-only job. When the catalog changes, it commits only that
    file on a fresh local branch and hands the commit to the write job as a
    bundle, alongside a PR body file, so the write job can push only bytes
    this run actually rendered.
    """
    try:
        head = git_text(root, "rev-parse", "HEAD")
    except OSError:
        return StageOutcome("failed", "checkout", None, None, False)
    if head != github_sha:
        return StageOutcome("failed", "checkout", head, None, False)
    base_sha = head

    candidate_path = root / CANDIDATE_PATH
    catalog_path = root / CATALOG_PATH
    report_path = root / REPORT_PATH

    if (
        regular_file_problem(candidate_path) is not None
        or regular_file_problem(catalog_path) is not None
    ):
        return StageOutcome("failed", "symlink", base_sha, None, False)

    try:
        report = json.loads(report_path.read_bytes())
        candidate_bytes = candidate_path.read_bytes()
    except (OSError, ValueError):
        return StageOutcome("failed", "report", base_sha, None, False)
    if not isinstance(report, dict):
        return StageOutcome("failed", "report", base_sha, None, False)

    added, removed, changed_urls = _report_changes(report)
    retained_failures = _report_retained_failures(report)

    try:
        base_bytes = git_output(root, "show", f"{base_sha}:{CATALOG_PATH}")
    except OSError:
        return StageOutcome("failed", "report", base_sha, None, False)

    try:
        catalog_path.write_bytes(candidate_bytes)
        catalog_path.chmod(0o644)
    except OSError:
        return StageOutcome("failed", "write", base_sha, None, False)

    changed = candidate_bytes != base_bytes
    sha = base_sha
    if changed:
        try:
            sha = _commit_candidate(root, base_sha, run_url)
            if git_text(root, "rev-parse", "HEAD") != sha:
                return StageOutcome("failed", "bundle", base_sha, None, False)
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            git_output(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
            body_text = _render_report(
                base_sha=base_sha,
                run_url=run_url,
                added=added,
                removed=removed,
                changed=changed_urls,
                retained_failures=retained_failures,
            )
            body_path.parent.mkdir(parents=True, exist_ok=True)
            body_path.write_text(body_text, encoding="utf-8")
        except OSError:
            return StageOutcome("failed", "bundle", base_sha, None, False)

    status = "changed" if changed else "unchanged"
    return StageOutcome(
        status,
        "complete",
        base_sha,
        sha,
        changed,
        added,
        removed,
        changed_urls,
        retained_failures,
    )


def _report_changes(
    report: Mapping[str, object],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    changes = report.get("changes")
    if not isinstance(changes, dict):
        return (), (), ()
    return (
        tuple(url for url in changes.get("added", ()) or () if isinstance(url, str)),
        tuple(url for url in changes.get("removed", ()) or () if isinstance(url, str)),
        tuple(url for url in changes.get("changed", ()) or () if isinstance(url, str)),
    )


def _report_retained_failures(
    report: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    raw = report.get("retainedFailures")
    if not isinstance(raw, list):
        return ()
    failures: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            url = item.get("url")
            message = item.get("message")
            if isinstance(url, str) and isinstance(message, str):
                failures.append((url, message))
    return tuple(failures)


def _render_report(
    *,
    base_sha: str,
    run_url: str | None,
    added: Sequence[str],
    removed: Sequence[str],
    changed: Sequence[str],
    retained_failures: Sequence[tuple[str, str]],
) -> str:
    lines: list[str] = []
    if run_url is not None:
        lines.append(f"Workflow run: {run_url}")
        lines.append("")
    lines.append(f"Base SHA: {base_sha}")
    lines.append("")
    lines.append("<pre>")
    lines.append("Added:")
    lines.extend(html.escape(url) for url in added)
    lines.append("")
    lines.append("Removed:")
    lines.extend(html.escape(url) for url in removed)
    lines.append("")
    lines.append("Changed:")
    lines.extend(html.escape(url) for url in changed)
    lines.append("")
    lines.append("Retained failures:")
    lines.extend(
        f"{html.escape(url)}: {html.escape(message)}"
        for url, message in retained_failures
    )
    lines.append("</pre>")
    return "\n".join(lines) + "\n"


def _commit_candidate(root: Path, base_sha: str, run_url: str) -> str:
    git_output(root, "checkout", "-q", "-B", BRANCH_NAME)
    git_output(root, "add", "--", CATALOG_PATH)
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    return bot_commit(root, COMMIT_SUBJECT, body)


# --- publish (write job) --------------------------------------------------


class PublishFailure(RuntimeError):
    def __init__(self, summary: str) -> None:
        super().__init__(summary)
        self.summary = summary


@dataclass(frozen=True)
class PublishOutcome:
    status: str  # "closed", "unchanged", "published" or "failed"
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
) -> PublishOutcome:
    """Close a stale proposal, or push and open or refresh the source-update PR.

    Every check below runs before any remote write, so a rejected hand-off or
    an advanced main changes neither the bot branch nor any PR.
    """
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

        selected_number = _selected_pr_number(selected_gh, generic)

        if not is_changed:
            if selected_number is None:
                return PublishOutcome("unchanged", "publish made no change")
            close_result = selected_gh.run(
                ["pr", "close", str(selected_number), "--repo", CANONICAL_REPOSITORY]
            )
            if close_result.returncode != 0:
                raise PublishFailure(generic)
            return PublishOutcome("closed", f"publish closed PR #{selected_number}")

        if bundle_path is None or body_path is None:
            raise PublishFailure(generic)

        try:
            entries = verify_handoff(root, bundle_path, candidate_sha, base_sha)
        except HandoffRejected:
            raise PublishFailure(generic) from None
        if not _catalog_only_diff(entries):
            raise PublishFailure(generic)

        remote_branch_sha = ls_remote_sha(root, f"refs/heads/{BRANCH_NAME}")
        if remote_branch_sha is None:
            raise PublishFailure(generic)
        needs_push = True
        if remote_branch_sha:
            expect(
                git(root, "fetch", "--quiet", "origin", f"refs/heads/{BRANCH_NAME}"),
                PublishFailure,
                generic,
            )
            remote_tree = expect(
                git(root, "rev-parse", "FETCH_HEAD^{tree}"), PublishFailure, generic
            ).strip()
            candidate_tree = expect(
                git(root, "rev-parse", f"{candidate_sha}^{{tree}}"),
                PublishFailure,
                generic,
            ).strip()
            needs_push = remote_tree != candidate_tree

        if needs_push:
            push_result = git(
                root,
                "push",
                "--force",
                "origin",
                f"{candidate_sha}:refs/heads/{BRANCH_NAME}",
            )
            if push_result.returncode != 0:
                raise PublishFailure(generic)

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
                raise PublishFailure(generic)
            return PublishOutcome("published", f"publish updated PR #{selected_number}")

        create_result = selected_gh.run(
            [
                "pr",
                "create",
                "--repo",
                CANONICAL_REPOSITORY,
                "--title",
                PR_TITLE,
                "--body-file",
                str(body_path),
                "--base",
                "main",
                "--head",
                BRANCH_NAME,
            ]
        )
        if create_result.returncode != 0:
            raise PublishFailure(generic)
        return PublishOutcome("published", "publish created PR")
    except PublishFailure as failure:
        return PublishOutcome("failed", failure.summary)


def _selected_pr_number(gh: GhRunner, failure_message: str) -> int | None:
    result = gh.run(
        [
            "pr",
            "list",
            "--repo",
            CANONICAL_REPOSITORY,
            "--head",
            BRANCH_NAME,
            "--base",
            "main",
            "--state",
            "open",
            "--json",
            "number,isCrossRepository,headRepositoryOwner",
        ]
    )
    if result.returncode != 0:
        raise PublishFailure(failure_message)
    try:
        candidates = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise PublishFailure(failure_message) from None
    if not isinstance(candidates, list):
        raise PublishFailure(failure_message)
    selected = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("isCrossRepository") is False
        and isinstance(item.get("headRepositoryOwner"), dict)
        and item["headRepositoryOwner"].get("login") == CANONICAL_OWNER
    ]
    if len(selected) > 1:
        raise PublishFailure(failure_message)
    if not selected:
        return None
    number = selected[0].get("number")
    if not isinstance(number, int):
        raise PublishFailure(failure_message)
    return number


def _catalog_only_diff(entries: Sequence[DiffEntry]) -> bool:
    """Exactly one entry: the catalog, at mode 100644 on both sides."""
    return len(entries) == 1 and entries[0] == (CATALOG_PATH, "100644", "100644")


# --- shared CLI plumbing ---------------------------------------------------


def _handoff_paths(environ: Mapping[str, str]) -> tuple[Path, Path]:
    directory = Path(require_env(environ, "RUNNER_TEMP")) / HANDOFF_DIRECTORY
    return directory / BUNDLE_NAME, directory / BODY_NAME


def _run_stage_command(environ: Mapping[str, str], *, root: Path | None = None) -> int:
    selected_root = root or Path.cwd()
    bundle_path, body_path = _handoff_paths(environ)
    outcome = run_stage(
        selected_root,
        environ.get("GITHUB_SHA", ""),
        run_url(environ),
        bundle_path,
        body_path,
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
    append_summary(environ, outcome.summary + "\n")
    return 0 if outcome.status != "failed" else 1


def _run_publish_command(
    environ: Mapping[str, str],
    bundle_path: Path | None,
    body_path: Path | None,
    *,
    root: Path | None = None,
) -> int:
    selected_root = root or Path.cwd()
    outcome = run_publish(
        selected_root,
        environ.get("CHANGED", ""),
        environ.get("CANDIDATE_SHA", ""),
        environ.get("BASE_SHA", ""),
        bundle_path,
        body_path,
    )
    append_summary(environ, outcome.summary + "\n")
    return 0 if outcome.status != "failed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.source_proposal")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("stage")
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--bundle", type=Path, default=None)
    publish_parser.add_argument("--body-file", type=Path, default=None)
    arguments = parser.parse_args(argv)
    environ = os.environ

    if arguments.command == "stage":
        return _run_stage_command(environ)
    return _run_publish_command(environ, arguments.bundle, arguments.body_file)


if __name__ == "__main__":
    sys.exit(main())
