"""Check and publish reviewed codm source candidates through an owned PR."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from omnipack.source_generation import validate_generation_output
from scripts.nightly import UrllibGitHubApi
from scripts.nightly_publish import CommandResult
from scripts.nightly_release import GitHubApi
from scripts.nightly_reporting import redact

CANONICAL_REPOSITORY = "mjkoo/omnipack"
CANONICAL_OWNER = "mjkoo"
SOURCE_BRANCH = "automation/codm-catalog"
MARKER = "<!-- omnipack:codm-catalog -->"
POLICY_PATH = "config/codm-projects.json"
SOURCE_PATHS = (
    "config/catalogs/codm.json",
    "config/catalogs/codm.source.json",
    "config/package-ids.json",
)
OUTPUT_NAMES = ("catalog.json", "source.json", "resolution-state.json")
DIAGNOSTIC_NAMES = ("run-result.json", "report.json", "pack-diff.json")
OBSERVED_REFS_PATH = ".build/source-publication/observed-refs.json"


class PublicationError(RuntimeError):
    """The checked source is unsafe to publish."""


class ProcessBoundary(Protocol):
    def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult: ...


class SubprocessBoundary:
    def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _git(root: Path, *args: str, env: Mapping[str, str] | None = None) -> bytes:
    process_env = os.environ.copy()
    process_env.update(env or {})
    completed = subprocess.run(
        ["git", *args], cwd=root, env=process_env, capture_output=True, check=False
    )
    if completed.returncode:
        detail = completed.stderr.decode(errors="replace").strip()
        raise PublicationError(detail or "git operation failed")
    return completed.stdout


def _paths(root: Path, *args: str) -> set[str]:
    return {value.decode() for value in _git(root, *args).split(b"\0") if value}


def _regular_bytes(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise PublicationError(f"missing {label}") from error
    if not stat.S_ISREG(mode) or path.is_symlink():
        raise PublicationError(f"{label} is not a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise PublicationError(f"cannot read {label}") from error


def _restore(root: Path, snapshots: Mapping[str, tuple[bytes, int]]) -> None:
    for relative, (content, mode) in snapshots.items():
        path = root / relative
        path.write_bytes(content)
        path.chmod(stat.S_IMODE(mode))


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise PublicationError("unable to prove fast-forward ancestry")
    return result.returncode == 0


def _pack_effect(before: bytes, after: bytes) -> dict[str, object]:
    def entries(raw: bytes) -> dict[str, object]:
        value = json.loads(raw)
        return {app["id"]: app for app in value.get("apps", [])}

    old, new = entries(before), entries(after)
    return {
        "addedIds": sorted(new.keys() - old.keys()),
        "removedIds": sorted(old.keys() - new.keys()),
        "changedIds": sorted(
            key for key in old.keys() & new.keys() if old[key] != new[key]
        ),
    }


@dataclass(frozen=True)
class CheckedSourceCandidate:
    root: Path
    base_sha: str
    policy: bytes
    snapshots: Mapping[str, bytes]
    modes: Mapping[str, bytes]
    changed_paths: tuple[str, ...]
    pack_diagnostics: Mapping[str, object]
    observed_branch_sha: str | None = None
    refs_observed: bool = False
    permissions: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def check(
        cls,
        root: Path,
        base_sha: str,
        output: Path,
        process: ProcessBoundary | None = None,
    ) -> CheckedSourceCandidate:
        if _git(root, "rev-parse", "HEAD").decode().strip() != base_sha:
            raise PublicationError("selected base does not match HEAD")
        if _paths(root, "diff", "--name-only", "-z", "HEAD", "--") or _paths(
            root, "diff", "--cached", "--name-only", "-z", "HEAD", "--"
        ):
            raise PublicationError("source checking requires a clean tracked workspace")
        policy = _regular_bytes(root / POLICY_PATH, "reviewed policy")
        candidate_bytes = {
            relative: _regular_bytes(output / name, f"candidate {name}")
            for relative, name in zip(SOURCE_PATHS, OUTPUT_NAMES, strict=True)
        }
        permissions = {
            name: stat.S_IMODE((root / name).stat().st_mode)
            for name in (*SOURCE_PATHS, POLICY_PATH)
        }
        try:
            generation = validate_generation_output(root, output)
        except (ValueError, TypeError, KeyError, OSError) as error:
            raise PublicationError(f"source validation failed: {error}") from error
        if (
            any(
                _regular_bytes(output / name, name) != candidate_bytes[relative]
                for relative, name in zip(SOURCE_PATHS, OUTPUT_NAMES, strict=True)
            )
            or _regular_bytes(root / POLICY_PATH, POLICY_PATH) != policy
        ):
            raise PublicationError(
                "source or policy bytes changed during source validation"
            )
        modes: dict[str, bytes] = {}
        for relative in SOURCE_PATHS:
            entry = _git(root, "ls-tree", base_sha, "--", relative).split()
            if not entry or entry[0] not in (b"100644", b"100755"):
                raise PublicationError(f"base source path is not regular: {relative}")
            modes[relative] = entry[0]
            (root / relative).write_bytes(candidate_bytes[relative])

        publishable = set(SOURCE_PATHS)
        if _paths(root, "diff", "--name-only", "-z", "HEAD", "--") - publishable:
            raise PublicationError("candidate introduced an unexpected tracked change")
        outputs = ("README.md", "dist/single-screen.json", "dist/dual-screen.json")
        prior = {
            name: ((root / name).read_bytes(), (root / name).stat().st_mode)
            for name in outputs
        }

        def guard() -> None:
            for name, expected in {**candidate_bytes, POLICY_PATH: policy}.items():
                if (
                    _regular_bytes(root / name, name) != expected
                    or stat.S_IMODE((root / name).stat().st_mode) != permissions[name]
                ):
                    raise PublicationError(
                        "source or policy bytes/modes changed during checking"
                    )
            unexpected = (
                _paths(root, "diff", "--name-only", "-z", "HEAD", "--")
                - set(SOURCE_PATHS)
                - set(outputs)
            )
            if unexpected:
                raise PublicationError("unexpected tracked changes during checking")

        runner = process or SubprocessBoundary()
        try:
            for stage, command in (
                ("build", ("uv", "run", "--no-sync", "pack", "build")),
                ("structural-verify", ("uv", "run", "--no-sync", "pack", "verify")),
            ):
                guard()
                result = runner.run(command, root)
                guard()
                if result.returncode:
                    detail = result.stderr.strip() or result.stdout.strip()
                    raise PublicationError(f"{stage} failed: {detail}")
            diagnostics: dict[str, object] = {
                **generation,
                "baseSha": base_sha,
                "sourcePaths": list(SOURCE_PATHS),
                "sourceChanges": _pack_effect(
                    _git(root, "show", f"{base_sha}:{SOURCE_PATHS[0]}"),
                    candidate_bytes[SOURCE_PATHS[0]],
                ),
                "packChanged": [
                    name
                    for name in outputs
                    if (root / name).read_bytes() != prior[name][0]
                ],
                "packEffects": {
                    name: _pack_effect(prior[name][0], (root / name).read_bytes())
                    for name in outputs
                    if name.endswith(".json")
                },
                "build": "success",
                "structuralVerify": "success",
            }
        finally:
            _restore(root, prior)
        if _regular_bytes(root / POLICY_PATH, "reviewed policy") != policy:
            raise PublicationError("policy bytes changed during checking")
        guard()
        snapshots = candidate_bytes
        changed = tuple(
            name
            for name in SOURCE_PATHS
            if snapshots[name] != _git(root, "show", f"{base_sha}:{name}")
        )
        return cls(
            root,
            base_sha,
            policy,
            snapshots,
            modes,
            changed,
            diagnostics,
            permissions=permissions,
        )

    def validate_bytes(self) -> None:
        for name, mode in self.permissions.items():
            _regular_bytes(self.root / name, name)
            if stat.S_IMODE((self.root / name).stat().st_mode) != mode:
                raise PublicationError("source or policy mode changed after checking")
        if _regular_bytes(self.root / POLICY_PATH, "reviewed policy") != self.policy:
            raise PublicationError("policy bytes changed after checking")
        for relative, expected in self.snapshots.items():
            if _regular_bytes(self.root / relative, relative) != expected:
                raise PublicationError("source bytes changed after checking")

        if _paths(self.root, "diff", "--name-only", "-z", "HEAD", "--") - set(
            SOURCE_PATHS
        ):
            raise PublicationError("unexpected tracked changes after checking")

    def stage_and_validate(self) -> None:
        self.validate_bytes()
        if _git(self.root, "rev-parse", "HEAD").decode().strip() != self.base_sha:
            raise PublicationError("selected base changed before publication")
        if _regular_bytes(self.root / POLICY_PATH, "reviewed policy") != self.policy:
            raise PublicationError("policy bytes changed after checking")
        for relative, expected in self.snapshots.items():
            if _regular_bytes(self.root / relative, relative) != expected:
                raise PublicationError("source bytes changed after checking")
        changed = _paths(self.root, "diff", "--name-only", "-z", "HEAD", "--")
        if changed - set(SOURCE_PATHS):
            raise PublicationError("unexpected tracked changes before publication")
        _git(self.root, "reset", "--quiet")
        _git(self.root, "add", "--", *SOURCE_PATHS)
        for relative in SOURCE_PATHS:
            _git(
                self.root,
                "update-index",
                f"--chmod={'+x' if self.modes[relative] == b'100755' else '-x'}",
                "--",
                relative,
            )
        staged = _paths(
            self.root, "diff", "--cached", "--name-only", "-z", self.base_sha, "--"
        )
        if staged != set(self.changed_paths):
            raise PublicationError(
                "staged source path set differs from checked candidate"
            )
        for relative in staged:
            if _git(self.root, "show", f":{relative}") != self.snapshots[relative]:
                raise PublicationError(
                    "staged source bytes differ from checked candidate"
                )
            mode = _git(self.root, "ls-files", "--stage", "--", relative).split()[0]
            if mode != self.modes[relative]:
                raise PublicationError("staged source mode differs from selected base")

    def provenance(self) -> str:
        return f"{MARKER}\nSource-Repository: {CANONICAL_REPOSITORY}\nSource-Base: {self.pack_diagnostics['baseSha']}"

    def create_commit(self) -> str:
        self.stage_and_validate()
        if not self.changed_paths:
            return self.base_sha
        _git(
            self.root,
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--quiet",
            "-m",
            "chore(catalog): update reviewed codm source\n\n" + self.provenance(),
        )
        sha = _git(self.root, "rev-parse", "HEAD").decode().strip()
        committed = _paths(
            self.root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", sha
        )
        if committed != set(self.changed_paths):
            raise PublicationError("commit contains paths outside checked source")
        for relative in committed:
            if (
                _git(self.root, "ls-tree", sha, "--", relative).split()[0]
                != self.modes[relative]
            ):
                raise PublicationError("commit mode differs from checked source")
            if _git(self.root, "show", f"{sha}:{relative}") != self.snapshots[relative]:
                raise PublicationError("commit tree differs from checked source")
        return sha


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    merged_at: str | None
    repository: str
    owner: str
    head: str
    base: str
    body: str
    head_repository: str = CANONICAL_REPOSITORY
    head_sha: str = ""


class SourceRemoteBoundary(Protocol):
    def snapshot(self) -> tuple[str, str | None]: ...
    def pull_requests(self) -> tuple[PullRequest, ...]: ...
    def changed_paths(self, main: str, branch: str, /) -> tuple[str, ...]: ...
    def is_ancestor(self, older: str, newer: str, /) -> bool: ...
    def push(self, root: Path, expected: str | None, token: str, /) -> None: ...
    def create_pull_request(self, token: str) -> None: ...


@dataclass(frozen=True)
class SourcePublicationResult:
    status: str
    stage: str
    base_sha: str
    branch_sha: str | None = None
    detail: str = ""


class SourcePublicationCoordinator:
    def __init__(self, root: Path, remote: SourceRemoteBoundary) -> None:
        self.root = root
        self.remote = remote

    def publish(
        self, candidate: CheckedSourceCandidate, token: str
    ) -> SourcePublicationResult:
        if not token:
            raise PublicationError("publication token is absent")
        candidate.validate_bytes()
        selected_base = candidate.base_sha
        main, branch = self.remote.snapshot()
        if candidate.refs_observed and (
            main != candidate.base_sha or branch != candidate.observed_branch_sha
        ):
            raise PublicationError(
                "remote main or source branch advanced during checking"
            )
        history = self.remote.pull_requests()
        self._validate_ownership(branch, main, history, candidate)
        same = branch is not None and all(
            _git(self.root, "show", f"{branch}:{path}") == content
            for path, content in candidate.snapshots.items()
        )
        open_prs = tuple(pr for pr in history if pr.state == "open")
        if same and open_prs:
            candidate.validate_bytes()
            return SourcePublicationResult(
                "no-op", "complete", candidate.base_sha, branch
            )
        if main != candidate.base_sha:
            raise PublicationError("remote main advanced after checking")
        current_main, current_branch = self.remote.snapshot()
        if (current_main, current_branch) != (main, branch):
            raise PublicationError("remote main or source branch advanced")
        if same:
            candidate.validate_bytes()
            try:
                self.remote.create_pull_request(token)
            except OSError:
                return SourcePublicationResult(
                    "uncertain",
                    "pull-request",
                    candidate.base_sha,
                    branch,
                    "pull-request creation outcome is unknown; rediscover next run",
                )
            return SourcePublicationResult(
                "published", "complete", candidate.base_sha, branch
            )

        if branch is not None:
            for relative in SOURCE_PATHS:
                (self.root / relative).write_bytes(
                    content_at(self.root, candidate.base_sha, relative)
                )
            if self.remote.is_ancestor(branch, main):
                _git(self.root, "checkout", "--detach", main)
            elif self.remote.is_ancestor(main, branch):
                _git(self.root, "checkout", "--detach", branch)
            else:
                merge = subprocess.run(
                    ["git", "merge-tree", "--write-tree", branch, main],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if merge.returncode:
                    raise PublicationError(
                        "owned source branch conflicts with current main"
                    )
                tree = merge.stdout.splitlines()[0]
                merged = (
                    _git(
                        self.root,
                        "-c",
                        "user.name=github-actions[bot]",
                        "-c",
                        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                        "commit-tree",
                        tree,
                        "-p",
                        branch,
                        "-p",
                        main,
                        "-m",
                        "chore(catalog): incorporate current main",
                    )
                    .decode()
                    .strip()
                )
                _git(self.root, "checkout", "--detach", merged)
            for relative, content in candidate.snapshots.items():
                (self.root / relative).write_bytes(content)
            candidate = CheckedSourceCandidate(
                self.root,
                _git(self.root, "rev-parse", "HEAD").decode().strip(),
                candidate.policy,
                candidate.snapshots,
                candidate.modes,
                tuple(
                    path
                    for path in SOURCE_PATHS
                    if content_at(self.root, "HEAD", path) != candidate.snapshots[path]
                ),
                candidate.pack_diagnostics,
                candidate.observed_branch_sha,
                candidate.refs_observed,
                candidate.permissions,
            )
        sha = candidate.create_commit()
        candidate.validate_bytes()
        if self.remote.snapshot() != (main, branch):
            raise PublicationError(
                "remote main or source branch advanced immediately before push"
            )
        if branch is not None and not _is_ancestor(self.root, branch, sha):
            raise PublicationError("source update would rewrite branch history")
        try:
            self.remote.push(self.root, branch, token)
        except OSError:
            return SourcePublicationResult(
                "uncertain",
                "push",
                selected_base,
                None,
                "branch write outcome is unknown; rediscover next run",
            )
        if not open_prs:
            candidate.validate_bytes()
            if self.remote.snapshot() != (main, sha):
                raise PublicationError(
                    "remote main or source branch advanced before pull-request creation"
                )
            try:
                self.remote.create_pull_request(token)
            except OSError:
                return SourcePublicationResult(
                    "uncertain",
                    "pull-request",
                    selected_base,
                    sha,
                    "pull-request creation outcome is unknown; rediscover next run",
                )
        return SourcePublicationResult("published", "complete", selected_base, sha)

    def _validate_ownership(
        self,
        branch: str | None,
        main: str,
        history: tuple[PullRequest, ...],
        candidate: CheckedSourceCandidate,
    ) -> None:
        for pr in history:
            if (
                pr.repository != CANONICAL_REPOSITORY
                or pr.head_repository != CANONICAL_REPOSITORY
                or pr.owner != CANONICAL_OWNER
                or pr.head != SOURCE_BRANCH
                or pr.base != "main"
                or MARKER not in pr.body
            ):
                raise PublicationError("source pull-request ownership is invalid")
        if len(tuple(pr for pr in history if pr.state == "open")) > 1:
            raise PublicationError("multiple open owned source pull requests")
        if branch is not None:
            if not history:
                parents = (
                    _git(self.root, "show", "-s", "--format=%P", branch)
                    .decode()
                    .split()
                )
                message = (
                    _git(self.root, "show", "-s", "--format=%B", branch)
                    .decode()
                    .strip()
                )
                author = (
                    _git(
                        self.root, "show", "-s", "--format=%an <%ae>|%cn <%ce>", branch
                    )
                    .decode()
                    .strip()
                )
                bot = "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
                exact = all(
                    content_at(self.root, branch, path) == value
                    and _git(self.root, "ls-tree", branch, "--", path).split()[0]
                    == candidate.modes[path]
                    for path, value in candidate.snapshots.items()
                )
                if (
                    len(parents) != 1
                    or not _is_ancestor(self.root, parents[0], main)
                    or message
                    != "chore(catalog): update reviewed codm source\n\n"
                    + f"{MARKER}\nSource-Repository: {CANONICAL_REPOSITORY}\nSource-Base: {parents[0]}"
                    or author != f"{bot}|{bot}"
                    or not exact
                ):
                    raise PublicationError(
                        "source branch has no owned pull-request history or exact initial-write provenance"
                    )
            changed = set(self.remote.changed_paths(main, branch))
            if changed - set(SOURCE_PATHS):
                raise PublicationError("source branch contains unrelated changes")
            latest = max(history, key=lambda pr: pr.number) if history else None
            if latest and latest.merged_at is not None:
                merged_head = latest.head_sha or branch
                integrated = self.remote.is_ancestor(merged_head, main) or all(
                    content_at(self.root, merged_head, path)
                    == content_at(self.root, main, path)
                    for path in SOURCE_PATHS
                )
                if not integrated:
                    raise PublicationError(
                        "merged source branch content is not integrated into main"
                    )


def content_at(root: Path, revision: str, path: str) -> bytes:
    return _git(root, "show", f"{revision}:{path}")


class GitHubSourceRemote:
    def __init__(self, root: Path, api: GitHubApi) -> None:
        self.root = root
        self.api = api

    def snapshot(self) -> tuple[str, str | None]:
        result = subprocess.run(
            [
                "git",
                "fetch",
                "--quiet",
                "--prune",
                "origin",
                "+refs/heads/main:refs/remotes/origin/main",
                f"+refs/heads/{SOURCE_BRANCH}:refs/remotes/origin/{SOURCE_BRANCH}",
            ],
            cwd=self.root,
            capture_output=True,
            check=False,
        )
        # A missing optional source ref can make the two-ref fetch fail. Fetch main
        # independently, then query the source ref without creating a local branch.
        if result.returncode:
            _git(
                self.root,
                "fetch",
                "--quiet",
                "origin",
                "+refs/heads/main:refs/remotes/origin/main",
            )
        main = _git(self.root, "rev-parse", "refs/remotes/origin/main").decode().strip()
        branch_result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", f"refs/heads/{SOURCE_BRANCH}"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if branch_result.returncode:
            raise OSError("unable to inspect source branch")
        branch = (
            branch_result.stdout.split()[0] if branch_result.stdout.strip() else None
        )
        if branch:
            _git(
                self.root,
                "fetch",
                "--quiet",
                "origin",
                f"+refs/heads/{SOURCE_BRANCH}:refs/remotes/origin/{SOURCE_BRANCH}",
            )
        return main, branch

    def pull_requests(self) -> tuple[PullRequest, ...]:
        found: list[PullRequest] = []
        page = 1
        while True:
            query = urlencode(
                {
                    "state": "all",
                    "head": f"{CANONICAL_OWNER}:{SOURCE_BRANCH}",
                    "base": "main",
                    "per_page": 100,
                    "page": page,
                }
            )
            response = self.api.request(
                "GET", f"/repos/{CANONICAL_REPOSITORY}/pulls?{query}"
            )
            if response.status != 200:
                raise PublicationError("unable to discover source pull-request history")
            document = json.loads(response.body)
            if not isinstance(document, list):
                raise PublicationError("source pull-request history is malformed")
            for item in document:
                found.append(
                    PullRequest(
                        int(item["number"]),
                        str(item["state"]),
                        item.get("merged_at"),
                        str(item["base"]["repo"]["full_name"]),
                        str(item["head"]["repo"]["owner"]["login"]),
                        str(item["head"]["ref"]),
                        str(item["base"]["ref"]),
                        str(item.get("body") or ""),
                        str((item["head"].get("repo") or {}).get("full_name", "")),
                        str(item["head"].get("sha", "")),
                    )
                )
            if len(document) < 100:
                return tuple(found)
            page += 1

    def changed_paths(self, main: str, branch: str) -> tuple[str, ...]:
        paths = _paths(
            self.root, "diff", "--name-only", "-z", f"{main}...{branch}", "--"
        )
        return tuple(sorted(paths))

    def is_ancestor(self, older: str, newer: str) -> bool:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", older, newer],
            cwd=self.root,
            check=False,
        )
        if completed.returncode not in (0, 1):
            raise PublicationError("unable to inspect source branch ancestry")
        return completed.returncode == 0

    def push(self, root: Path, expected: str | None, token: str) -> None:
        head = _git(root, "rev-parse", "HEAD").decode().strip()
        if expected is not None and not _is_ancestor(root, expected, head):
            raise PublicationError("source update would rewrite branch history")
        authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {authorization}",
        }
        result = subprocess.run(
            [
                "git",
                "push",
                "--porcelain",
                f"--force-with-lease=refs/heads/{SOURCE_BRANCH}:{expected or ''}",
                "origin",
                f"{head}:refs/heads/{SOURCE_BRANCH}",
            ],
            cwd=root,
            env={**os.environ, **env},
            capture_output=True,
            check=False,
        )
        if any(line.startswith(b"=\t") for line in result.stdout.splitlines()):
            raise PublicationError(
                "source branch expected-ref write was rejected after concurrent advance"
            )
        if result.returncode:
            diagnostic = (result.stderr + result.stdout).decode(errors="replace")
            if "[rejected]" in diagnostic or "non-fast-forward" in diagnostic:
                raise PublicationError("source branch fast-forward write was rejected")
            raise OSError("source branch write acknowledgement unavailable")

    def create_pull_request(self, token: str) -> None:
        if not token:
            raise PublicationError("publication token is absent")
        response = self.api.request(
            "POST",
            f"/repos/{CANONICAL_REPOSITORY}/pulls",
            {
                "title": "chore(catalog): update reviewed codm source",
                "head": SOURCE_BRANCH,
                "base": "main",
                "body": f"{MARKER}\n\nUpdates the checked codm source catalog and bound resolution state.",
            },
        )
        if response.status != 201:
            if response.status in (409, 422) or response.status >= 500:
                raise OSError("pull-request creation acknowledgement unavailable")
            raise PublicationError(
                f"pull-request creation failed with status {response.status}"
            )


def _copy_report(output: Path, directory: Path) -> None:
    report = json.loads((output / "report.json").read_bytes())

    def safe(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: safe(item)
                for key, item in value.items()
                if key not in {"error", "detail"}
            }
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value

    (directory / "report.json").write_text(
        json.dumps(redact(safe(report)), indent=2, sort_keys=True) + "\n"
    )


def _diagnostic_dir(environ: Mapping[str, str]) -> Path:
    value = environ.get("RUNNER_TEMP")
    if not value:
        raise PublicationError("RUNNER_TEMP is required")
    return Path(value) / "source-catalog-diagnostics"


def _write_result(environ: Mapping[str, str], result: Mapping[str, object]) -> None:
    token = environ.get("GITHUB_TOKEN", "")
    secrets = (
        (token, base64.b64encode(f"x-access-token:{token}".encode()).decode())
        if token
        else ()
    )
    result = {
        "baseSha": environ.get("GITHUB_SHA"),
        "sourceUrl": None,
        "readmeSha256": None,
        "projectPolicySha256": None,
        "catalogSha256": None,
        "effectivePolicy": {},
        "sourceChanges": {},
        "packValidation": "not-run",
        **result,
    }
    rendered = json.dumps(redact(result, secrets), indent=2, sort_keys=True)
    directory = _diagnostic_dir(environ)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run-result.json").write_text(rendered + "\n")
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write("<pre>" + html.escape(rendered) + "</pre>\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    observe = commands.add_parser("observe")
    observe.add_argument("--base", required=True)
    check = commands.add_parser("check")
    check.add_argument("--base", required=True)
    commands.add_parser("publish")
    arguments = parser.parse_args(argv)
    root = Path.cwd()
    environ = os.environ
    output = root / ".build/source-generation/codm"
    run_identity = [
        environ.get("GITHUB_RUN_ID", "local"),
        environ.get("GITHUB_RUN_ATTEMPT", "1"),
    ]
    failure_diagnostics: dict[str, object] = {
        "baseSha": getattr(arguments, "base", None),
        "packValidation": "not-run",
    }
    try:
        if arguments.command == "observe":
            directory = _diagnostic_dir(environ)
            directory.mkdir(parents=True, exist_ok=True)
            for name in DIAGNOSTIC_NAMES:
                (directory / name).unlink(missing_ok=True)
        if arguments.command == "check":
            (_diagnostic_dir(environ) / "pack-diff.json").unlink(missing_ok=True)
        if arguments.command in {"observe", "check"}:
            (output / "checked.json").unlink(missing_ok=True)
        if arguments.command == "observe":
            (root / OBSERVED_REFS_PATH).unlink(missing_ok=True)
            api = UrllibGitHubApi(
                "", environ.get("GITHUB_API_URL", "https://api.github.com")
            )
            main_sha, branch_sha = GitHubSourceRemote(root, api).snapshot()
            if main_sha != arguments.base:
                raise PublicationError(
                    "remote main differs from selected workflow base"
                )
            observed_path = root / OBSERVED_REFS_PATH
            observed_path.parent.mkdir(parents=True, exist_ok=True)
            observed_path.write_text(
                json.dumps(
                    {
                        "mainSha": main_sha,
                        "branchSha": branch_sha,
                        "runIdentity": run_identity,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            _write_result(
                environ,
                {"status": "observed", "stage": "generation", "baseSha": main_sha},
            )
            return 0
        if arguments.command == "check":
            output = root / ".build/source-generation/codm"
            observed = json.loads((root / OBSERVED_REFS_PATH).read_bytes())
            if observed.get("runIdentity") != run_identity:
                raise PublicationError("observed refs belong to a previous run")
            if observed["mainSha"] != arguments.base:
                raise PublicationError("checked base differs from observed main")
            report = json.loads((output / "report.json").read_bytes())
            failure_diagnostics.update(
                {
                    **report.get("inputs", {}),
                    "effectivePolicy": report.get("effectivePolicy", {}),
                    "sourceChanges": report.get("changes", {}),
                    "packValidation": "failed",
                }
            )
            if (output / "source.json").is_file():
                metadata = json.loads((output / "source.json").read_bytes())
                if isinstance(metadata, dict):
                    failure_diagnostics["catalogSha256"] = metadata.get("catalogSha256")
            if report.get("status") == "unchanged":
                generation = validate_generation_output(root, output)
                if _git(
                    root, "rev-parse", "HEAD"
                ).decode().strip() != arguments.base or _paths(
                    root, "diff", "--name-only", "-z", "HEAD", "--"
                ):
                    raise PublicationError(
                        "unchanged source requires clean selected main"
                    )
                (output / "checked.json").write_text(
                    json.dumps(
                        {
                            "runIdentity": run_identity,
                            "status": "no-op",
                            "baseSha": arguments.base,
                            "diagnostics": generation,
                            "policy": base64.b64encode(
                                (root / POLICY_PATH).read_bytes()
                            ).decode(),
                            "observedBranchSha": observed["branchSha"],
                        }
                    )
                    + "\n"
                )
                diagnostics = _diagnostic_dir(environ)
                diagnostics.mkdir(parents=True, exist_ok=True)
                _copy_report(output, diagnostics)
                _write_result(
                    environ,
                    {
                        **generation,
                        "status": "no-op",
                        "packValidation": "not-run-unchanged",
                        "stage": "validation",
                        "baseSha": arguments.base,
                    },
                )
                return 0
            unchecked = CheckedSourceCandidate.check(root, arguments.base, output)
            candidate = replace(
                unchecked, observed_branch_sha=observed["branchSha"], refs_observed=True
            )
            evidence = output / "checked.json"
            evidence.write_text(
                json.dumps(
                    {
                        "runIdentity": run_identity,
                        "baseSha": candidate.base_sha,
                        "policy": base64.b64encode(candidate.policy).decode(),
                        "sources": {
                            path: base64.b64encode(value).decode()
                            for path, value in candidate.snapshots.items()
                        },
                        "modes": {
                            path: value.decode()
                            for path, value in candidate.modes.items()
                        },
                        "changedPaths": list(candidate.changed_paths),
                        "packDiagnostics": candidate.pack_diagnostics,
                        "observedBranchSha": candidate.observed_branch_sha,
                        "refsObserved": candidate.refs_observed,
                        "permissions": dict(candidate.permissions),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            diagnostics = _diagnostic_dir(environ)
            diagnostics.mkdir(parents=True, exist_ok=True)
            _copy_report(output, diagnostics)
            (diagnostics / "pack-diff.json").write_text(
                json.dumps(candidate.pack_diagnostics, indent=2, sort_keys=True) + "\n"
            )
            _write_result(
                environ,
                {
                    **candidate.pack_diagnostics,
                    "packValidation": "success",
                    "status": "checked",
                    "stage": "validation",
                    "baseSha": candidate.base_sha,
                },
            )
            return 0
        if (
            environ.get("GITHUB_REPOSITORY") != CANONICAL_REPOSITORY
            or environ.get("GITHUB_REF") != "refs/heads/main"
        ):
            _write_result(environ, {"status": "ineligible", "stage": "publication"})
            return 0
        checked = json.loads(
            (root / ".build/source-generation/codm/checked.json").read_text()
        )
        failure_diagnostics["baseSha"] = checked.get("baseSha")
        if checked.get("runIdentity") != run_identity:
            raise PublicationError("checked evidence belongs to a previous run")
        if checked.get("status") == "no-op":
            generation = validate_generation_output(root, output)
            if (
                generation != checked["diagnostics"]
                or (root / POLICY_PATH).read_bytes()
                != base64.b64decode(checked["policy"])
                or _git(root, "rev-parse", "HEAD").decode().strip()
                != checked["baseSha"]
                or _paths(root, "diff", "--name-only", "-z", "HEAD", "--")
            ):
                raise PublicationError(
                    "unchanged source or policy changed after checking"
                )
            _write_result(
                environ,
                {
                    **generation,
                    "status": "no-op",
                    "packValidation": "not-run-unchanged",
                    "stage": "publication",
                    "baseSha": checked["baseSha"],
                },
            )
            return 0
        candidate = CheckedSourceCandidate(
            root,
            checked["baseSha"],
            base64.b64decode(checked["policy"]),
            {
                path: base64.b64decode(value)
                for path, value in checked["sources"].items()
            },
            {path: value.encode() for path, value in checked["modes"].items()},
            tuple(checked["changedPaths"]),
            checked["packDiagnostics"],
            checked["observedBranchSha"],
            checked["refsObserved"],
            checked["permissions"],
        )
        failure_diagnostics = {
            **candidate.pack_diagnostics,
            "packValidation": "success",
        }
        token = environ.get("GITHUB_TOKEN", "")
        api = UrllibGitHubApi(
            token, environ.get("GITHUB_API_URL", "https://api.github.com")
        )
        result = SourcePublicationCoordinator(
            root, GitHubSourceRemote(root, api)
        ).publish(candidate, token)
        _write_result(
            environ,
            {
                **candidate.pack_diagnostics,
                "packValidation": "success",
                "status": result.status,
                "stage": result.stage,
                "baseSha": result.base_sha,
                "branchSha": result.branch_sha,
                "detail": result.detail,
            },
        )
        return 0 if result.status in ("published", "no-op") else 1
    except Exception as error:  # noqa: BLE001 - final workflow boundary
        token = environ.get("GITHUB_TOKEN", "")
        secrets = (
            (token, base64.b64encode(f"x-access-token:{token}".encode()).decode())
            if token
            else ()
        )
        detail = redact(str(error), secrets)
        _write_result(
            environ,
            {
                **failure_diagnostics,
                "status": "failed",
                "stage": arguments.command,
                "detail": f"{arguments.command} failed ({type(error).__name__}); inspect the step log",
            },
        )
        print(json.dumps({"source_publication_failure": detail}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
