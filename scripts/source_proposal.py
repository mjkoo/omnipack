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
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.nightly_write import (
    CommandResult,
    DiffParseError,
    GhRunner,
    SubprocessGhRunner,
    _append_summary,
    _diff_raw_entries,
    _remote_sha,
)
from scripts.nightly_write import _git as _hooked_git

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
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
_FULL_SHA = re.compile(r"[0-9a-f]{40}")


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
        head = _git_text(root, "rev-parse", "HEAD")
    except OSError:
        return StageOutcome("failed", "checkout", None, None, False)
    if head != github_sha:
        return StageOutcome("failed", "checkout", head, None, False)
    base_sha = head

    candidate_path = root / CANDIDATE_PATH
    catalog_path = root / CATALOG_PATH
    report_path = root / REPORT_PATH

    if (
        _file_problem(candidate_path) is not None
        or _file_problem(catalog_path) is not None
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
        base_bytes = _git_bytes(root, "show", f"{base_sha}:{CATALOG_PATH}")
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
            if _git_text(root, "rev-parse", "HEAD") != sha:
                return StageOutcome("failed", "bundle", base_sha, None, False)
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            _git(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
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
    _git(root, "checkout", "-q", "-B", BRANCH_NAME)
    _git(root, "add", "--", CATALOG_PATH)
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    _git(
        root,
        "-c",
        f"user.name={BOT_NAME}",
        "-c",
        f"user.email={BOT_EMAIL}",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "-m",
        COMMIT_SUBJECT,
        "-m",
        body,
    )
    return _git_text(root, "rev-parse", "HEAD")


def _file_problem(path: Path) -> str | None:
    try:
        info = path.lstat()
    except OSError:
        return "missing"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if not stat.S_ISREG(info.st_mode):
        return "irregular"
    return None


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise OSError(
            completed.stderr.decode(errors="replace").strip()
            or f"git {' '.join(args)} failed"
        )
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode().strip()


def _git(root: Path, *args: str) -> None:
    _git_bytes(root, *args)


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
            _FULL_SHA.fullmatch(base_sha) is None
            or _FULL_SHA.fullmatch(candidate_sha) is None
        ):
            raise PublishFailure(generic)
        is_changed = changed == "true"

        auth_result = selected_gh.run(["auth", "setup-git"])
        if auth_result.returncode != 0:
            raise PublishFailure(f"{generic}: gh auth setup-git failed")

        ls_remote_result = _hooked_git(root, "ls-remote", "origin", "refs/heads/main")
        if ls_remote_result.returncode != 0:
            raise PublishFailure(f"{generic}: could not read remote main")
        if _remote_sha(ls_remote_result.stdout) != base_sha:
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

        head = _expect(_hooked_git(root, "rev-parse", "HEAD"), generic).strip()
        if head != base_sha:
            raise PublishFailure(generic)
        if _expect(_hooked_git(root, "status", "--porcelain"), generic).strip():
            raise PublishFailure(generic)

        _expect(_hooked_git(root, "bundle", "verify", str(bundle_path)), generic)
        _expect(
            _hooked_git(root, "fetch", "--quiet", str(bundle_path), "HEAD"), generic
        )
        fetched_sha = _expect(
            _hooked_git(root, "rev-parse", "FETCH_HEAD"), generic
        ).strip()
        if fetched_sha != candidate_sha:
            raise PublishFailure(generic)

        parents = _expect(
            _hooked_git(root, "rev-list", "--parents", "-n", "1", fetched_sha), generic
        ).split()
        if len(parents) != 2 or parents[1] != base_sha:
            raise PublishFailure(generic)

        try:
            entries = _diff_raw_entries(root, base_sha, fetched_sha)
        except DiffParseError:
            raise PublishFailure(generic) from None
        _require_catalog_only_diff(entries, generic)

        remote_branch_output = _expect(
            _hooked_git(
                root, "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH_NAME}"
            ),
            generic,
        )
        remote_branch_sha = _remote_sha(remote_branch_output)
        needs_push = True
        if remote_branch_sha:
            _expect(
                _hooked_git(
                    root, "fetch", "--quiet", "origin", f"refs/heads/{BRANCH_NAME}"
                ),
                generic,
            )
            remote_tree = _expect(
                _hooked_git(root, "rev-parse", "FETCH_HEAD^{tree}"), generic
            ).strip()
            candidate_tree = _expect(
                _hooked_git(root, "rev-parse", f"{candidate_sha}^{{tree}}"), generic
            ).strip()
            needs_push = remote_tree != candidate_tree

        if needs_push:
            push_result = _hooked_git(
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


def _require_catalog_only_diff(
    entries: Sequence[tuple[str, str, str]], failure_message: str
) -> None:
    if len(entries) != 1:
        raise PublishFailure(failure_message)
    path, old_mode, new_mode = entries[0]
    if path != CATALOG_PATH or old_mode != "100644" or new_mode != "100644":
        raise PublishFailure(failure_message)


def _expect(result: CommandResult, failure_message: str) -> str:
    if result.returncode != 0:
        raise PublishFailure(failure_message)
    return result.stdout


# --- shared CLI plumbing ---------------------------------------------------


def _run_url(environ: Mapping[str, str]) -> str:
    server = environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = environ.get("GITHUB_REPOSITORY", CANONICAL_REPOSITORY)
    run_id = environ.get("GITHUB_RUN_ID", "unknown")
    return f"{server}/{repository}/actions/runs/{run_id}"


def _write_github_output(environ: Mapping[str, str], values: Mapping[str, str]) -> None:
    output = environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def _handoff_paths(environ: Mapping[str, str]) -> tuple[Path, Path]:
    runner_temp = environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise OSError("RUNNER_TEMP is required")
    directory = Path(runner_temp) / HANDOFF_DIRECTORY
    return directory / BUNDLE_NAME, directory / BODY_NAME


def _run_stage_command(environ: Mapping[str, str], *, root: Path | None = None) -> int:
    selected_root = root or Path.cwd()
    bundle_path, body_path = _handoff_paths(environ)
    outcome = run_stage(
        selected_root,
        environ.get("GITHUB_SHA", ""),
        _run_url(environ),
        bundle_path,
        body_path,
    )
    if outcome.status != "failed":
        _write_github_output(
            environ,
            {
                "changed": "true" if outcome.changed else "false",
                "sha": outcome.sha or "",
                "base": outcome.base_sha or "",
            },
        )
    _append_summary(environ, outcome.summary + "\n")
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
    _append_summary(environ, outcome.summary + "\n")
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
