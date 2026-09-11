from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from omnipack.composition_policy import (
    apply_composition_policy,
    parse_composition_policy,
)
from omnipack.sources import IngestionReport, SourceError
from omnipack.sources.codm import fetch as fetch_codm
from scripts.nightly import ApiResponse
from scripts.nightly_publish import CommandResult
from scripts.source_publication import (
    MARKER,
    SOURCE_PATHS,
    CheckedSourceCandidate,
    GitHubSourceRemote,
    PublicationError,
    PullRequest,
    SourcePublicationCoordinator,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Tests")
    _git(root, "config", "user.email", "tests@example.invalid")
    for relative in (*SOURCE_PATHS, "config/codm-projects.json", "README.md"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if relative != "README.md" else "readme\n")
    (root / "dist").mkdir()
    for name in ("single-screen.json", "dual-screen.json"):
        (root / "dist" / name).write_text("{}\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return root


class Checks:
    def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
        if command[-2:] == ("pack", "build"):
            (cwd / "dist/single-screen.json").write_text('{"built":1}\n')
            (cwd / "dist/dual-screen.json").write_text('{"built":2}\n')
            (cwd / "README.md").write_text("generated readme\n")
        return CommandResult(0, "", "")


def _outputs(root: Path, suffix: str = "candidate") -> Path:
    output = root / ".build/source-generation/codm"
    output.mkdir(parents=True, exist_ok=True)
    for name in ("catalog.json", "source.json", "resolution-state.json"):
        (output / name).write_text(json.dumps({"name": name, "value": suffix}) + "\n")
    (output / "report.json").write_text('{"status":"generated"}\n')
    return output


def _catalog_outputs(root: Path, apps: list[dict[str, object]]) -> Path:
    output = _outputs(root)
    (output / "catalog.json").write_text(json.dumps({"apps": apps}) + "\n")
    return output


def test_checked_candidate_restores_pack_outputs_and_binds_source_policy(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    old_readme = (root / "README.md").read_bytes()
    old_dist = (root / "dist/single-screen.json").read_bytes()

    candidate = CheckedSourceCandidate.check(root, base, _outputs(root), Checks())

    assert set(candidate.changed_paths) == set(SOURCE_PATHS)
    assert (root / "README.md").read_bytes() == old_readme
    assert (root / "dist/single-screen.json").read_bytes() == old_dist
    assert set(_git(root, "diff", "--name-only").splitlines()) == set(SOURCE_PATHS)
    (root / "config/codm-projects.json").write_text('{"changed":true}\n')
    with pytest.raises(PublicationError, match="policy bytes changed"):
        candidate.stage_and_validate()


def test_checked_candidate_rejects_changed_candidate_and_unexpected_paths(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    candidate = CheckedSourceCandidate.check(
        root, _git(root, "rev-parse", "HEAD"), _outputs(root), Checks()
    )
    (root / SOURCE_PATHS[0]).write_text("changed after checks\n")
    with pytest.raises(PublicationError, match="source bytes changed"):
        candidate.stage_and_validate()


def test_failed_build_restores_pack_outputs_and_never_stages_source(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)

    class FailedBuild(Checks):
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            super().run(command, cwd)
            return CommandResult(1, "", "stale selector or package collision")

    with pytest.raises(PublicationError, match="stale selector or package collision"):
        CheckedSourceCandidate.check(
            root, _git(root, "rev-parse", "HEAD"), _outputs(root), FailedBuild()
        )

    assert (root / "README.md").read_text() == "readme\n"
    assert not _git(root, "diff", "--cached", "--name-only")


@pytest.mark.parametrize("failure", ["collision", "stale-selector"])
def test_checked_candidate_runs_real_catalog_and_policy_validation(
    tmp_path: Path, failure: str
) -> None:
    root = _repo(tmp_path)
    app: dict[str, object] = {
        "id": "same.id",
        "url": "https://github.com/example/one",
        "name": "One",
        "author": "example",
        "categories": [],
        "additionalSettings": "{}",
        "overrideSource": "GitHub",
    }
    apps: list[dict[str, object]] = [
        app,
        {**app, "url": "https://github.com/example/two"},
    ]
    policy: dict[str, object] = {
        "schemaVersion": 1,
        "candidates": [],
        "pins": [],
    }
    if failure == "stale-selector":
        apps = [app]
        policy["candidates"] = [
            {
                "match": {
                    "source": "codm2000",
                    "origin": "codm-generated",
                    "id": "missing.id",
                    "url": "https://github.com/example/missing",
                },
                "rationale": "must remain",
            }
        ]

    class RealCompositionChecks(Checks):
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            if command[-2:] != ("pack", "build"):
                return CommandResult(0, "", "")
            try:
                admitted = fetch_codm(
                    cwd,
                    {"catalog": "config/catalogs/codm.json"},
                    [],
                    IngestionReport(),
                )
                apply_composition_policy(
                    parse_composition_policy(policy), admitted, require_all=True
                )
            except (SourceError, ValueError) as error:
                return CommandResult(1, "", str(error))
            raise AssertionError("invalid candidate passed real composition validation")

    with pytest.raises(PublicationError, match="duplicate id|missing.id"):
        CheckedSourceCandidate.check(
            root,
            _git(root, "rev-parse", "HEAD"),
            _catalog_outputs(root, apps),
            RealCompositionChecks(),
        )


@dataclass
class FakeRemote:
    main: str
    branch: str | None = None
    prs: tuple[PullRequest, ...] = ()
    diff: tuple[str, ...] = SOURCE_PATHS
    pushes: list[tuple[str, str | None]] | None = None
    created: int = 0
    uncertain: bool = False

    def snapshot(self) -> tuple[str, str | None]:
        return self.main, self.branch

    def pull_requests(self) -> tuple[PullRequest, ...]:
        return self.prs

    def changed_paths(self, _main: str, _branch: str) -> tuple[str, ...]:
        return self.diff

    def is_ancestor(self, older: str, newer: str) -> bool:
        return older == newer

    def push(self, root: Path, expected: str | None, token: str) -> None:
        assert token == "secret"
        assert "policy" not in " ".join(
            _git(root, "show", "--format=", "--name-only", "HEAD").splitlines()
        )
        if self.uncertain:
            raise OSError("acknowledgement lost")
        if self.pushes is None:
            self.pushes = []
        self.pushes.append((_git(root, "rev-parse", "HEAD"), expected))
        self.branch = self.pushes[-1][0]

    def create_pull_request(self, token: str) -> None:
        assert token == "secret"
        if self.uncertain:
            raise OSError("acknowledgement lost")
        self.created += 1


def _checked(root: Path, suffix: str = "candidate") -> CheckedSourceCandidate:
    return CheckedSourceCandidate.check(
        root, _git(root, "rev-parse", "HEAD"), _outputs(root, suffix), Checks()
    )


def test_first_proposal_pushes_once_and_creates_owned_pr(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    remote = FakeRemote(_git(root, "rev-parse", "HEAD"))

    result = SourcePublicationCoordinator(root, remote).publish(
        _checked(root), "secret"
    )

    assert result.status == "published"
    assert len(remote.pushes or []) == 1
    assert remote.created == 1


def test_open_same_content_is_noop_even_if_main_advanced(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    proposed = candidate.create_commit()
    pr = PullRequest(
        7,
        "open",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote("advanced-main", proposed, (pr,))

    result = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    assert result.status == "no-op"
    assert not remote.pushes
    assert remote.created == 0


def test_foreign_branch_diff_and_ambiguous_write_are_not_retried(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    pr = PullRequest(
        7,
        "open",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote(candidate.base_sha, candidate.base_sha, (pr,), ("README.md",))
    with pytest.raises(PublicationError, match="unrelated changes"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    remote = FakeRemote(candidate.base_sha, uncertain=True)
    result = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert result.status == "uncertain"
    assert remote.created == 0

    discovered = _git(root, "rev-parse", "HEAD")
    owned = PullRequest(
        8,
        "open",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    next_run = FakeRemote(candidate.base_sha, discovered, (owned,))
    assert (
        SourcePublicationCoordinator(root, next_run).publish(candidate, "secret").status
        == "no-op"
    )
    assert not next_run.pushes and next_run.created == 0


def test_closed_unmerged_history_creates_later_pr_without_reopening(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    proposed = candidate.create_commit()
    closed = PullRequest(
        3,
        "closed",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote(candidate.base_sha, proposed, (closed,))

    result = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    assert result.status == "published"
    assert not remote.pushes
    assert remote.created == 1


def test_changed_proposal_incorporates_unrelated_main_advancement(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    old_candidate = _checked(root, "old")
    branch = old_candidate.create_commit()
    _git(root, "checkout", "--detach", old_candidate.base_sha)
    _git(root, "branch", "-f", "main", old_candidate.base_sha)
    _git(root, "checkout", "main")
    (root / "unrelated.txt").write_text("new on main\n")
    _git(root, "add", "unrelated.txt")
    _git(root, "commit", "-m", "advance main")
    main = _git(root, "rev-parse", "HEAD")
    candidate = _checked(root, "new")
    pr = PullRequest(
        7,
        "open",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote(main, branch, (pr,))

    result = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    assert result.status == "published"
    assert len(remote.pushes or []) == 1
    updated = (remote.pushes or [])[0][0]
    assert _git(root, "merge-base", "--is-ancestor", main, updated) == ""
    assert _git(root, "merge-base", "--is-ancestor", branch, updated) == ""
    assert remote.created == 0


def test_merged_branch_must_be_integrated_before_reuse(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    branch = candidate.create_commit()
    _git(root, "checkout", "--detach", candidate.base_sha)
    _git(root, "branch", "-f", "main", candidate.base_sha)
    _git(root, "checkout", "main")
    merged = PullRequest(
        4,
        "closed",
        "2026-09-10T00:00:00Z",
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote(candidate.base_sha, branch, (merged,))

    with pytest.raises(PublicationError, match="not integrated"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")


def test_changed_proposal_rejects_real_source_merge_conflict(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    old_candidate = _checked(root, "branch-value")
    branch = old_candidate.create_commit()
    _git(root, "checkout", "--detach", old_candidate.base_sha)
    _git(root, "branch", "-f", "main", old_candidate.base_sha)
    _git(root, "checkout", "main")
    (root / SOURCE_PATHS[0]).write_text("main value\n")
    _git(root, "add", SOURCE_PATHS[0])
    _git(root, "commit", "-m", "change source on main")
    main = _git(root, "rev-parse", "HEAD")
    candidate = _checked(root, "next-value")
    pr = PullRequest(
        7,
        "open",
        None,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
    )
    remote = FakeRemote(main, branch, (pr,))

    with pytest.raises(PublicationError, match="conflicts"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    assert not remote.pushes


def test_main_or_branch_race_blocks_all_writes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    remote = FakeRemote(candidate.base_sha)
    calls = 0
    original = remote.snapshot

    def racing() -> tuple[str, str | None]:
        nonlocal calls
        calls += 1
        return original() if calls == 1 else ("new-main", None)

    remote.snapshot = racing  # ty: ignore[invalid-assignment]
    with pytest.raises(PublicationError, match="advanced"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes
    assert remote.created == 0


def test_branch_advance_during_generation_is_rejected_before_pr_discovery(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    candidate = replace(
        _checked(root), observed_branch_sha="old-branch", refs_observed=True
    )
    remote = FakeRemote(candidate.base_sha, "new-branch")

    with pytest.raises(PublicationError, match="during checking"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")

    assert not remote.pushes
    assert remote.created == 0


def test_pull_request_ownership_discovery_reads_every_page(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    item = {
        "number": 1,
        "state": "closed",
        "merged_at": None,
        "body": MARKER,
        "head": {
            "ref": "automation/codm-catalog",
            "repo": {"owner": {"login": "mjkoo"}},
        },
        "base": {"ref": "main", "repo": {"full_name": "mjkoo/omnipack"}},
    }

    class Pages:
        token = ""

        def __init__(self) -> None:
            self.paths: list[str] = []

        def request(
            self,
            method: str,
            path: str,
            body: Mapping[str, object] | None = None,
        ) -> ApiResponse:
            assert method == "GET" and body is None
            self.paths.append(path)
            page = 2 if "page=2" in path else 1
            values = [item] * (100 if page == 1 else 1)
            return ApiResponse(200, {}, json.dumps(values).encode())

    api = Pages()
    history = GitHubSourceRemote(root, api).pull_requests()

    assert len(history) == 101
    assert len(api.paths) == 2
    assert all("state=all" in path and "per_page=100" in path for path in api.paths)
