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
from omnipack.project_policy import default_apk_rule
from omnipack.source_generation import _canonical_json, _entry, _render_catalog, _sha
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
    (root / "config/codm-projects.json").write_text(
        '{"schemaVersion":1,"projects":{}}\n'
    )
    (root / "config/sources.json").write_text(
        json.dumps(
            {
                "codm": {
                    "catalog": SOURCE_PATHS[0],
                    "readme_url": "https://example.invalid/README.md",
                }
            }
        )
    )
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
    apps = [
        _entry(
            "https://github.com/example/one",
            default_apk_rule(),
            "app." + suffix.replace("-", "_"),
        )
    ]
    return _catalog_outputs(root, apps)


def _catalog_outputs(root: Path, apps: list[dict[str, object]]) -> Path:
    output = root / ".build/source-generation/codm"
    output.mkdir(parents=True, exist_ok=True)
    readme = (
        "| Project | Notes |\n| --- | --- |\n"
        + "".join(f"| [App]({app['url']}) | yes |\n" for app in apps)
    ).encode()
    rule = default_apk_rule()
    try:
        catalog = _render_catalog(apps)
    except ValueError:
        catalog = _canonical_json({"apps": apps})
    inputs = {
        "sourceUrl": "https://example.invalid/README.md",
        "readmeSha256": _sha(readme),
        "projectPolicySha256": _sha((root / "config/codm-projects.json").read_bytes()),
    }
    (output / "catalog.json").write_bytes(catalog)
    (output / "readme-input.bin").write_bytes(readme)
    (output / "source.json").write_bytes(
        _canonical_json({"schemaVersion": 1, **inputs, "catalogSha256": _sha(catalog)})
    )
    (output / "resolution-state.json").write_bytes(
        _canonical_json(
            {
                str(app["url"]).removeprefix("https://"): {
                    "packageId": app["id"],
                    "releaseId": 1,
                    "policyFingerprint": rule.fingerprint,
                }
                for app in apps
            }
        )
    )
    (output / "report.json").write_bytes(
        _canonical_json(
            {
                "status": "success",
                "inputs": inputs,
                "effectivePolicy": {
                    str(app["url"]).removeprefix("https://"): {
                        **rule.canonical(),
                        "fingerprint": rule.fingerprint,
                    }
                    for app in apps
                },
            }
        )
    )
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
    app = _entry("https://github.com/example/one", default_apk_rule(), "same.id")
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

    with pytest.raises(PublicationError, match="collision|duplicate id|missing.id"):
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
    assert result.base_sha == main
    assert candidate.pack_diagnostics["baseSha"] == main
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
    candidate = _checked(root)
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
    (root / SOURCE_PATHS[0]).write_bytes(
        _render_catalog(
            [_entry("https://github.com/example/one", default_apk_rule(), "main.value")]
        )
    )
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
            "repo": {"owner": {"login": "mjkoo"}, "full_name": "mjkoo/omnipack"},
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


@pytest.mark.parametrize("stage", ["build", "verify"])
@pytest.mark.parametrize("mutation", ["source", "mode", "policy-mode"])
def test_checks_reject_mutation_during_each_command(
    tmp_path: Path, stage: str, mutation: str
) -> None:
    root = _repo(tmp_path)

    class MutatingChecks(Checks):
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            result = super().run(command, cwd)
            if command[-1] == stage:
                path = cwd / (
                    "config/codm-projects.json"
                    if mutation == "policy-mode"
                    else SOURCE_PATHS[0]
                )
                if mutation == "source":
                    path.write_text("mutated\n")
                else:
                    path.chmod(0o755)
            return result

    with pytest.raises(PublicationError, match="changed"):
        CheckedSourceCandidate.check(
            root, _git(root, "rev-parse", "HEAD"), _outputs(root), MutatingChecks()
        )
    assert (root / "README.md").read_text() == "readme\n"


@pytest.mark.parametrize(
    "corruption",
    [
        "metadata-schema",
        "readme-hash",
        "source-url",
        "policy-hash",
        "state-id",
        "state-membership",
        "fingerprint",
        "catalog-format",
        "policy",
    ],
)
def test_production_source_validation_rejects_corrupt_generation(
    tmp_path: Path, corruption: str
) -> None:
    root = _repo(tmp_path)
    output = _outputs(root)
    target = output / "source.json"
    if corruption.startswith("state") or corruption == "fingerprint":
        target = output / "resolution-state.json"
    doc = json.loads(target.read_bytes())
    if corruption == "metadata-schema":
        doc["schemaVersion"] = 2
    elif corruption == "readme-hash":
        doc["readmeSha256"] = "a" * 64
    elif corruption == "source-url":
        doc["sourceUrl"] = "https://foreign.invalid/README.md"
    elif corruption == "policy-hash":
        doc["projectPolicySha256"] = "a" * 64
    elif corruption == "state-id":
        doc["github.com/example/one"]["packageId"] = "forged.id"
    elif corruption == "state-membership":
        doc["github.com/foreign/project"] = dict(doc["github.com/example/one"])
    elif corruption == "fingerprint":
        doc["github.com/example/one"]["policyFingerprint"] = "a" * 64
    elif corruption == "catalog-format":
        catalog = output / "catalog.json"
        catalog.write_bytes(catalog.read_bytes() + b"\n")
        doc["catalogSha256"] = _sha(catalog.read_bytes())
    elif corruption == "policy":
        (root / "config/codm-projects.json").write_text(
            '{"schemaVersion":2,"projects":{}}'
        )
        _git(root, "add", "config/codm-projects.json")
        _git(root, "commit", "-m", "invalid selected policy")
    target.write_bytes(_canonical_json(doc))

    class NeverChecks:
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            raise AssertionError("invalid generation reached build")

    with pytest.raises(PublicationError, match="source validation"):
        CheckedSourceCandidate.check(
            root, _git(root, "rev-parse", "HEAD"), output, NeverChecks()
        )
    assert not _git(root, "diff", "--cached", "--name-only")


def _owned(
    number: int = 7, state: str = "open", merged: str | None = None, head: str = ""
) -> PullRequest:
    return PullRequest(
        number,
        state,
        merged,
        "mjkoo/omnipack",
        "mjkoo",
        "automation/codm-catalog",
        "main",
        MARKER,
        "mjkoo/omnipack",
        head,
    )


@pytest.mark.parametrize("ack_stage", ["push", "pr-failed", "pr-applied"])
def test_initial_partial_write_is_recovered_by_later_invocation(
    tmp_path: Path, ack_stage: str
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)

    class PartialRemote(FakeRemote):
        def push(self, root: Path, expected: str | None, token: str) -> None:
            super().push(root, expected, token)
            if ack_stage == "push":
                raise OSError("push applied but ack lost")

        def create_pull_request(self, token: str) -> None:
            if ack_stage == "pr-applied":
                self.prs = (_owned(head=self.branch or ""),)
                self.created += 1
            raise OSError("PR acknowledgement unavailable")

    remote = PartialRemote(candidate.base_sha)
    first = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert first.status == "uncertain"
    assert len(remote.pushes or []) == 1
    _git(root, "checkout", "--detach", candidate.base_sha)
    candidate = _checked(root)
    next_run = FakeRemote(candidate.base_sha, remote.branch, remote.prs)
    result = SourcePublicationCoordinator(root, next_run).publish(candidate, "secret")
    assert result.status == ("no-op" if ack_stage == "pr-applied" else "published")
    assert next_run.created == (0 if ack_stage == "pr-applied" else 1)
    assert not next_run.pushes


def test_source_only_foreign_initial_commit_is_never_adopted(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    _git(root, "add", *SOURCE_PATHS)
    _git(root, "commit", "-m", "foreign source-only commit")
    branch = _git(root, "rev-parse", "HEAD")
    remote = FakeRemote(candidate.base_sha, branch)
    with pytest.raises(PublicationError, match="provenance"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes and remote.created == 0


@pytest.mark.parametrize("same", [False, True])
def test_same_owner_fork_pr_is_rejected(tmp_path: Path, same: bool) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    branch = candidate.create_commit() if same else candidate.base_sha
    remote = FakeRemote(
        candidate.base_sha,
        branch,
        (replace(_owned(), head_repository="mjkoo/foreign"),),
    )
    with pytest.raises(PublicationError, match="ownership"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes and remote.created == 0


def test_latest_merged_lifecycle_is_checked_in_mixed_history(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    branch = candidate.create_commit()
    remote = FakeRemote(
        candidate.base_sha,
        branch,
        (_owned(3, "closed"), _owned(4, "closed", "merged", branch)),
    )
    with pytest.raises(PublicationError, match="not integrated"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes and remote.created == 0


@pytest.mark.parametrize("open_pr", [False, True])
@pytest.mark.parametrize("mutate", ["policy", "source", "mode"])
def test_same_content_paths_recheck_candidate_guards(
    tmp_path: Path, open_pr: bool, mutate: str
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    branch = candidate.create_commit()
    remote = FakeRemote(
        candidate.base_sha, branch, (_owned(state="open" if open_pr else "closed"),)
    )
    path = root / (
        "config/codm-projects.json" if mutate == "policy" else SOURCE_PATHS[0]
    )
    if mutate == "mode":
        path.chmod(0o755)
    else:
        path.write_text("changed\n")
    with pytest.raises(PublicationError, match="changed"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes and remote.created == 0


def test_main_advance_after_local_commit_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    remote = FakeRemote(candidate.base_sha)
    create = CheckedSourceCandidate.create_commit

    def racing(self: CheckedSourceCandidate) -> str:
        sha = create(self)
        remote.main = "advanced"
        return sha

    monkeypatch.setattr(CheckedSourceCandidate, "create_commit", racing)
    with pytest.raises(PublicationError, match="immediately before push"):
        SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert not remote.pushes and remote.created == 0


@pytest.mark.parametrize("race", ["creation", "rewind", "advance", "none", "non-ff"])
def test_real_transport_fences_expected_ref_without_history_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str
) -> None:
    from typing import cast

    from scripts.nightly_release import GitHubApi
    from scripts.source_publication import SOURCE_BRANCH

    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(bare))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "origin", "main")
    first = _checked(root, "first").create_commit()
    _git(root, "push", "origin", f"{first}:refs/heads/{SOURCE_BRANCH}")
    second = _checked(root, "second").create_commit()
    _git(root, "push", "origin", f"{second}:refs/heads/staged-test-object")
    if race == "creation":
        _git(bare, "update-ref", "-d", f"refs/heads/{SOURCE_BRANCH}")
    if race == "non-ff":
        _git(root, "checkout", "--detach", base)
    transport = GitHubSourceRemote(root, cast(GitHubApi, object()))
    original = subprocess.run
    seen = []

    def raced_run(command, *args, **kwargs):
        if command[:2] == ["git", "push"]:
            seen.append(command)
            if race in {"creation", "rewind", "advance"}:
                target = {"creation": base, "rewind": base, "advance": second}[race]
                _git(bare, "update-ref", f"refs/heads/{SOURCE_BRANCH}", target)
        return original(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", raced_run)
    if race == "none":
        transport.push(root, first, "secret")
        assert _git(bare, "rev-parse", f"refs/heads/{SOURCE_BRANCH}") == second
    else:
        with pytest.raises(PublicationError, match="rejected|rewrite"):
            transport.push(root, None if race == "creation" else first, "secret")
        expected = {
            "creation": base,
            "rewind": base,
            "advance": second,
            "non-ff": first,
        }[race]
        assert _git(bare, "rev-parse", f"refs/heads/{SOURCE_BRANCH}") == expected
    if race == "non-ff":
        assert not seen


def _cli_environment(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ID", "current-run")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


def _observe_cli(root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from scripts import source_publication as publication

    base = _git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(
        publication.GitHubSourceRemote, "snapshot", lambda self: (base, None)
    )
    assert publication.main(["observe", "--base", base]) == 0
    return base


@pytest.mark.parametrize(
    "failure", ["generation", "source-check", "build", "verify", "stale-observation"]
)
def test_cli_check_failures_remove_stale_evidence_and_report_actual_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from omnipack import cli
    from scripts import source_publication as publication

    root = _repo(tmp_path)
    _cli_environment(root, tmp_path, monkeypatch)
    base = _observe_cli(root, monkeypatch)
    output = _outputs(root)
    evidence = output / "checked.json"
    evidence.write_text('{"status":"no-op","baseSha":"stale"}')

    class FailureChecks(Checks):
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            result = super().run(command, cwd)
            return (
                CommandResult(1, "", "failed validation")
                if command[-1] == failure
                else result
            )

    monkeypatch.setattr(publication, "SubprocessBoundary", FailureChecks)
    if failure == "generation":
        (root / "config/codm-projects.json").write_text("invalid policy")
        assert cli.main(["generate-source", "codm"]) == 1
    elif failure == "source-check":
        (output / "source.json").write_text("{}")
    elif failure == "stale-observation":
        monkeypatch.setenv("GITHUB_RUN_ID", "later-run")
    assert publication.main(["check", "--base", base]) == 1
    assert not evidence.exists()
    result = json.loads(
        (tmp_path / "runner/source-catalog-diagnostics/run-result.json").read_bytes()
    )
    assert result["status"] == "failed" and result["stage"] == "check"
    assert result["baseSha"] == base
    assert publication.main(["publish"]) == 1


def test_cli_checked_diagnostics_show_pack_effects_and_guard_stale_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import source_publication as publication

    root = _repo(tmp_path)
    _cli_environment(root, tmp_path, monkeypatch)
    base = _observe_cli(root, monkeypatch)
    _outputs(root)

    class PackChecks(Checks):
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            result = super().run(command, cwd)
            if command[-1] == "build":
                (cwd / "dist/dual-screen.json").write_text(
                    '{"apps":[{"id":"app.new"}]}'
                )
            return result

    monkeypatch.setattr(publication, "SubprocessBoundary", PackChecks)
    assert publication.main(["check", "--base", base]) == 0
    directory = tmp_path / "runner/source-catalog-diagnostics"
    result = json.loads((directory / "run-result.json").read_bytes())
    assert result["status"] == "checked"
    assert result["baseSha"] == base
    assert result["build"] == result["structuralVerify"] == "success"
    assert result["packEffects"]["dist/dual-screen.json"]["addedIds"] == ["app.new"]
    for key in (
        "sourceUrl",
        "readmeSha256",
        "projectPolicySha256",
        "catalogSha256",
        "effectivePolicy",
        "sourceChanges",
    ):
        assert key in result
    assert {path.name for path in directory.iterdir()} == {
        "run-result.json",
        "report.json",
        "pack-diff.json",
    }
    assert "readme-input" not in (directory / "report.json").read_text()
    monkeypatch.setenv("GITHUB_RUN_ID", "later-run")
    assert publication.main(["publish"]) == 1
    assert (
        json.loads((directory / "run-result.json").read_bytes())["status"] == "failed"
    )


def test_cli_publication_failure_redacts_raw_and_basic_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import base64

    from scripts import source_publication as publication

    root = _repo(tmp_path)
    _cli_environment(root, tmp_path, monkeypatch)
    base = _observe_cli(root, monkeypatch)
    _outputs(root)
    monkeypatch.setattr(publication, "SubprocessBoundary", Checks)
    assert publication.main(["check", "--base", base]) == 0
    token = "private-token-value"
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    monkeypatch.setenv("GITHUB_TOKEN", token)

    def fail(self):
        raise PublicationError(f"credential transport failed: {token} {encoded}")

    monkeypatch.setattr(publication.GitHubSourceRemote, "snapshot", fail)
    assert publication.main(["publish"]) == 1
    content = capsys.readouterr().err + (tmp_path / "summary.md").read_text()
    for path in (tmp_path / "runner/source-catalog-diagnostics").iterdir():
        content += path.read_text()
    assert token not in content and encoded not in content
    assert "REDACTED" in content


@pytest.mark.parametrize("command", ["observe", "publish"])
def test_cli_early_failures_replace_previous_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from scripts import source_publication as publication

    root = _repo(tmp_path)
    _cli_environment(root, tmp_path, monkeypatch)
    directory = tmp_path / "runner/source-catalog-diagnostics"
    directory.mkdir(parents=True)
    (directory / "run-result.json").write_text('{"status":"published"}')

    def failed(self):
        raise OSError("read-only remote unavailable")

    monkeypatch.setattr(publication.GitHubSourceRemote, "snapshot", failed)
    args = [command] + (
        ["--base", _git(root, "rev-parse", "HEAD")] if command == "observe" else []
    )
    assert publication.main(args) == 1
    result = json.loads((directory / "run-result.json").read_bytes())
    assert result["status"] == "failed" and result["stage"] == command


@pytest.mark.parametrize(
    "failure", [None, "stale-selector", "tracker-collision", "verify"]
)
def test_candidate_executes_real_pack_build_and_structural_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    from email.message import Message
    from urllib.request import Request

    from omnipack import cli
    from omnipack.http import HttpClient, HttpResponse

    root = _repo(tmp_path)
    sources = json.loads((root / "config/sources.json").read_bytes())
    sources.update(
        {
            "rjny": {"repo": "fixture/rjny", "branch": "main", "path": "apps.json"},
            "bboi": {
                "codeberg_repo": "fixture/bboi",
                "single_asset_pattern": "single.json",
                "dual_asset_pattern": "dual.json",
            },
        }
    )
    policy = {"schemaVersion": 1, "candidates": [], "pins": []}
    if failure == "stale-selector":
        policy["candidates"] = [
            {
                "match": {
                    "source": "codm2000",
                    "origin": "codm-generated",
                    "id": "missing.id",
                    "url": "https://github.com/example/missing",
                },
                "rationale": "pinned identity must exist",
            }
        ]
    extras = []
    if failure == "tracker-collision":
        extras = [
            {
                "id": "app.candidate",
                "url": "https://example.invalid/tracker",
                "name": "Colliding tracker",
                "overrideSource": "HTML",
                "additionalSettings": {"trackOnly": True},
            }
        ]
        policy["candidates"] = [
            {
                "match": {
                    "source": "codm2000",
                    "origin": "codm-generated",
                    "id": "app.candidate",
                    "url": "https://github.com/example/one",
                },
                "family": "app:installable",
                "rationale": "distinct installable",
            },
            {
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": "app.candidate",
                    "url": "https://example.invalid/tracker",
                },
                "family": "app:tracking",
                "rationale": "distinct tracker",
            },
        ]
    for name, value in {
        "sources.json": sources,
        "http.json": {"credentials": {}},
        "extras.json": extras,
        "composition.json": policy,
        "deny.json": [],
        "overlay.json": [],
        "overlay.dual.json": [],
        "settings.json": {},
    }.items():
        (root / "config" / name).write_text(json.dumps(value))
    (root / "README.md").write_text(
        "<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "configure real composition")
    response_docs = {
        "https://raw.githubusercontent.com/fixture/rjny/main/apps.json": {
            "apps": [
                {
                    "id": "app.other",
                    "url": "https://example.invalid/other",
                    "name": "Other",
                    "overrideSource": "HTML",
                }
            ]
        },
        "https://codeberg.org/api/v1/repos/fixture/bboi/releases/latest": {
            "assets": [
                {
                    "name": "single.json",
                    "browser_download_url": "https://fixture.invalid/single",
                },
                {
                    "name": "dual.json",
                    "browser_download_url": "https://fixture.invalid/dual",
                },
            ]
        },
        "https://fixture.invalid/single": {"apps": []},
        "https://fixture.invalid/dual": {"apps": []},
    }
    requested = []

    def transport(
        self: HttpClient, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        requested.append(request.full_url)
        return HttpResponse(
            request.full_url,
            200,
            Message(),
            json.dumps(response_docs[request.full_url]).encode(),
        )

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(root)
    commands = []

    class RealCommands:
        def run(self, command: tuple[str, ...], cwd: Path) -> CommandResult:
            commands.append(command[-1])
            if failure == "verify" and command[-1] == "verify":
                (cwd / "dist/dual-screen.json").write_text('{"apps":[]}')
            return CommandResult(
                cli.main([command[-1]]), "", "pack command rejected candidate"
            )

    before = {
        name: ((root / name).read_bytes(), (root / name).stat().st_mode)
        for name in ("README.md", "dist/single-screen.json", "dist/dual-screen.json")
    }
    if failure:
        with pytest.raises(PublicationError, match="failed"):
            CheckedSourceCandidate.check(
                root, _git(root, "rev-parse", "HEAD"), _outputs(root), RealCommands()
            )
    else:
        candidate = CheckedSourceCandidate.check(
            root, _git(root, "rev-parse", "HEAD"), _outputs(root), RealCommands()
        )
        assert candidate.pack_diagnostics["build"] == "success"
        assert candidate.pack_diagnostics["structuralVerify"] == "success"
        assert commands == ["build", "verify"]
        candidate.create_commit()
        assert set(
            _git(root, "show", "--format=", "--name-only", "HEAD").splitlines()
        ) == set(SOURCE_PATHS)
    assert requested == list(response_docs)
    assert {
        name: ((root / name).read_bytes(), (root / name).stat().st_mode)
        for name in before
    } == before


def test_initial_partial_write_recovery_after_benign_main_advance(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    candidate = _checked(root)
    branch = candidate.create_commit()
    _git(root, "checkout", "--detach", candidate.base_sha)
    (root / "other.txt").write_text("benign main advancement")
    _git(root, "add", "other.txt")
    _git(root, "commit", "-m", "advance main")
    candidate = _checked(root)
    remote = FakeRemote(candidate.base_sha, branch)
    result = SourcePublicationCoordinator(root, remote).publish(candidate, "secret")
    assert result.status == "published"
    assert result.base_sha == candidate.base_sha
    assert remote.created == 1 and not remote.pushes


@pytest.mark.parametrize("mutation", ["source", "policy"])
def test_source_validation_cannot_replace_initial_input_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from scripts import source_publication as publication

    root = _repo(tmp_path)
    output = _outputs(root)
    validate = publication.validate_generation_output

    def racing(root: Path, output: Path):
        result = validate(root, output)
        target = (
            output / "catalog.json"
            if mutation == "source"
            else root / "config/codm-projects.json"
        )
        target.write_bytes(target.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(publication, "validate_generation_output", racing)
    with pytest.raises(PublicationError, match="changed during source validation"):
        CheckedSourceCandidate.check(
            root, _git(root, "rev-parse", "HEAD"), output, Checks()
        )


@pytest.mark.parametrize("mutation", [None, "policy", "source"])
def test_cli_unchanged_generation_is_validated_and_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str | None
) -> None:
    from scripts import source_publication as publication

    root = _repo(tmp_path)
    _cli_environment(root, tmp_path, monkeypatch)
    _checked(root).create_commit()
    base = _observe_cli(root, monkeypatch)
    output = _outputs(root)
    report = json.loads((output / "report.json").read_bytes())
    report["status"] = "unchanged"
    (output / "report.json").write_text(json.dumps(report))
    assert publication.main(["check", "--base", base]) == 0
    if mutation:
        path = root / (
            "config/codm-projects.json" if mutation == "policy" else SOURCE_PATHS[0]
        )
        path.write_bytes(path.read_bytes() + b"\n")
    assert publication.main(["publish"]) == (1 if mutation else 0)
    result = json.loads(
        (tmp_path / "runner/source-catalog-diagnostics/run-result.json").read_text()
    )
    assert result["status"] == ("failed" if mutation else "no-op")
    if mutation is None:
        assert result["packValidation"] == "not-run-unchanged"
