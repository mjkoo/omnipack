"""Check and publish reviewed codm source candidates through an owned PR."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from scripts.nightly import UrllibGitHubApi
from scripts.nightly_publish import CommandResult
from scripts.nightly_release import GitHubApi

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
        runner = process or SubprocessBoundary()
        try:
            for stage, command in (
                ("build", ("uv", "run", "--no-sync", "pack", "build")),
                ("structural-verify", ("uv", "run", "--no-sync", "pack", "verify")),
            ):
                result = runner.run(command, root)
                if result.returncode:
                    detail = result.stderr.strip() or result.stdout.strip()
                    raise PublicationError(f"{stage} failed: {detail}")
            diagnostics: dict[str, object] = {
                "baseSha": base_sha,
                "sourcePaths": list(SOURCE_PATHS),
                "packChanged": [
                    name
                    for name in outputs
                    if (root / name).read_bytes() != prior[name][0]
                ],
                "build": "success",
                "structuralVerify": "success",
            }
        finally:
            _restore(root, prior)
        if _regular_bytes(root / POLICY_PATH, "reviewed policy") != policy:
            raise PublicationError("policy bytes changed during checking")
        snapshots = {name: _regular_bytes(root / name, name) for name in SOURCE_PATHS}
        changed = tuple(
            name
            for name in SOURCE_PATHS
            if snapshots[name] != _git(root, "show", f"{base_sha}:{name}")
        )
        return cls(root, base_sha, policy, snapshots, modes, changed, diagnostics)

    def stage_and_validate(self) -> None:
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
            "chore(catalog): update reviewed codm source",
        )
        sha = _git(self.root, "rev-parse", "HEAD").decode().strip()
        committed = _paths(
            self.root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", sha
        )
        if committed != set(self.changed_paths):
            raise PublicationError("commit contains paths outside checked source")
        for relative in committed:
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
        main, branch = self.remote.snapshot()
        if candidate.refs_observed and (
            main != candidate.base_sha or branch != candidate.observed_branch_sha
        ):
            raise PublicationError(
                "remote main or source branch advanced during checking"
            )
        history = self.remote.pull_requests()
        self._validate_ownership(branch, main, history)
        same = branch is not None and all(
            _git(self.root, "show", f"{branch}:{path}") == content
            for path, content in candidate.snapshots.items()
        )
        open_prs = tuple(pr for pr in history if pr.state == "open")
        if same and open_prs:
            return SourcePublicationResult(
                "no-op", "complete", candidate.base_sha, branch
            )
        if main != candidate.base_sha:
            raise PublicationError("remote main advanced after checking")
        current_main, current_branch = self.remote.snapshot()
        if (current_main, current_branch) != (main, branch):
            raise PublicationError("remote main or source branch advanced")
        if same:
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
            )
        sha = candidate.create_commit()
        try:
            self.remote.push(self.root, branch, token)
        except OSError:
            return SourcePublicationResult(
                "uncertain",
                "push",
                candidate.base_sha,
                None,
                "branch write outcome is unknown; rediscover next run",
            )
        if not open_prs:
            try:
                self.remote.create_pull_request(token)
            except OSError:
                return SourcePublicationResult(
                    "uncertain",
                    "pull-request",
                    candidate.base_sha,
                    sha,
                    "pull-request creation outcome is unknown; rediscover next run",
                )
        return SourcePublicationResult("published", "complete", candidate.base_sha, sha)

    def _validate_ownership(
        self, branch: str | None, main: str, history: tuple[PullRequest, ...]
    ) -> None:
        for pr in history:
            if (
                pr.repository != CANONICAL_REPOSITORY
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
                raise PublicationError(
                    "source branch has no owned pull-request history"
                )
            changed = set(self.remote.changed_paths(main, branch))
            if changed - set(SOURCE_PATHS):
                raise PublicationError("source branch contains unrelated changes")
            if history and all(pr.merged_at is not None for pr in history):
                integrated = self.remote.is_ancestor(branch, main) or all(
                    content_at(self.root, branch, path)
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

    def push(self, root: Path, _expected: str | None, token: str) -> None:
        authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {authorization}",
        }
        result = subprocess.run(
            ["git", "push", "origin", f"HEAD:refs/heads/{SOURCE_BRANCH}"],
            cwd=root,
            env={**os.environ, **env},
            capture_output=True,
            check=False,
        )
        if result.returncode:
            stderr = result.stderr.decode(errors="replace")
            if "[rejected]" in stderr or "non-fast-forward" in stderr:
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


def _diagnostic_dir(environ: Mapping[str, str]) -> Path:
    value = environ.get("RUNNER_TEMP")
    if not value:
        raise PublicationError("RUNNER_TEMP is required")
    return Path(value) / "source-catalog-diagnostics"


def _write_result(environ: Mapping[str, str], result: Mapping[str, object]) -> None:
    directory = _diagnostic_dir(environ)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f"Source catalog stage: {result.get('stage', 'unknown')}\n")


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
    try:
        if arguments.command == "observe":
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
                    {"mainSha": main_sha, "branchSha": branch_sha}, sort_keys=True
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
            if observed["mainSha"] != arguments.base:
                raise PublicationError("checked base differs from observed main")
            report = json.loads((output / "report.json").read_bytes())
            if report.get("status") == "unchanged":
                (output / "checked.json").write_text(
                    json.dumps({"status": "no-op", "baseSha": arguments.base}) + "\n"
                )
                diagnostics = _diagnostic_dir(environ)
                diagnostics.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output / "report.json", diagnostics / "report.json")
                _write_result(
                    environ,
                    {
                        "status": "no-op",
                        "stage": "validation",
                        "baseSha": arguments.base,
                    },
                )
                return 0
            unchecked = CheckedSourceCandidate.check(root, arguments.base, output)
            candidate = CheckedSourceCandidate(
                unchecked.root,
                unchecked.base_sha,
                unchecked.policy,
                unchecked.snapshots,
                unchecked.modes,
                unchecked.changed_paths,
                unchecked.pack_diagnostics,
                observed["branchSha"],
                True,
            )
            evidence = output / "checked.json"
            evidence.write_text(
                json.dumps(
                    {
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
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            diagnostics = _diagnostic_dir(environ)
            diagnostics.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output / "report.json", diagnostics / "report.json")
            (diagnostics / "pack-diff.json").write_text(
                json.dumps(candidate.pack_diagnostics, indent=2, sort_keys=True) + "\n"
            )
            _write_result(
                environ,
                {
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
        if checked.get("status") == "no-op":
            _write_result(
                environ,
                {
                    "status": "no-op",
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
        )
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
        detail = str(error).replace(token, "REDACTED") if token else str(error)
        _write_result(
            environ, {"status": "failed", "stage": arguments.command, "detail": detail}
        )
        print(json.dumps({"source_publication_failure": detail}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
