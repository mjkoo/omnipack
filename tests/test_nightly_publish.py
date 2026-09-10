from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.nightly_publish import (
    ALLOWED_PATHS,
    CandidateError,
    CommandResult,
    LocalAttemptFactory,
    PublicationCandidate,
    RefreshOrchestrator,
    validate_candidate,
)


class ControlledProcess:
    def __init__(self, root: Path, *, fail_at: int | None = None) -> None:
        self.root = root
        self.fail_at = fail_at
        self.commands: list[tuple[str, ...]] = []
        self.on_command: dict[int, Callable[[], None]] = {}

    def run(self, command: Sequence[str], cwd: Path) -> CommandResult:
        assert cwd == self.root
        self.commands.append(tuple(command))
        index = len(self.commands)
        callback = self.on_command.get(index)
        if callback is not None:
            callback()
        if "--validate-evidence" in command:
            from scripts.nightly_publish import _validate_live_evidence

            try:
                _validate_live_evidence(cwd, datetime.fromisoformat(command[-1]))
            except CandidateError as error:
                return CommandResult(1, "", str(error))
        return CommandResult(1 if index == self.fail_at else 0, "", "failed")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    for relative in ALLOWED_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "README.md":
            path.write_bytes(
                b"guide\r\n<!-- omnipack:catalog:start -->\r\n"
                b"base catalog\n<!-- omnipack:catalog:end -->\r\ncredits\r\n"
            )
        else:
            path.write_text(f"base:{relative}\n")
    (root / "tracked.txt").write_text("base\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _evidence(
    root: Path, *, warnings: bool = False, observed: str | None = None
) -> None:
    from omnipack.verify import SCHEMA_VERSION, capture_inputs, verifier_identity

    _, inputs = capture_inputs(root)
    observed = observed or datetime.now(UTC).isoformat()
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "verifier": verifier_identity(),
        "mode": "live",
        "startedAt": observed,
        "completedAt": observed,
        "complete": True,
        "status": "success",
        "inputs": inputs,
        "errors": [],
        "warnings": (
            [{"stage": "live", "code": "warning", "message": "temporary"}]
            if warnings
            else []
        ),
        "entries": [],
    }
    path = root / ".build/verify.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report))


def test_refresh_orders_checks_build_and_metadata_only_verification(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    process = ControlledProcess(root)
    old_evidence = root / ".build/verify.json"
    old_evidence.parent.mkdir(parents=True)
    old_evidence.write_text("stale")

    def replace_evidence() -> None:
        assert not old_evidence.exists()
        _evidence(root, warnings=True)

    process.on_command[9] = replace_evidence

    result = RefreshOrchestrator(process).run(root, "abc123")

    assert result.status == "no-op"
    assert [outcome.stage for outcome in result.stages] == [
        "sync",
        "format-check",
        "lint-check",
        "typecheck",
        "python-build",
        "tests",
        "offline-verify",
        "build",
        "live-verify",
        "candidate",
    ]
    assert process.commands[-3:-1] == [
        ("uv", "run", "--no-sync", "pack", "build"),
        ("uv", "run", "--no-sync", "pack", "verify", "--live"),
    ]
    assert all("--probe-assets" not in command for command in process.commands)
    assert "config/composition.json" not in ALLOWED_PATHS


def test_every_attempt_reruns_every_refresh_command(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    process = ControlledProcess(root)
    process.on_command[9] = lambda: _evidence(root)
    process.on_command[19] = lambda: _evidence(root)

    assert RefreshOrchestrator(process).run(root, "first").status == "no-op"
    assert RefreshOrchestrator(process).run(root, "second").status == "no-op"

    assert [
        (command[:-1] if "--validate-evidence" in command else command)
        for command in process.commands[:10]
    ] == [
        (command[:-1] if "--validate-evidence" in command else command)
        for command in process.commands[10:]
    ]


@pytest.mark.parametrize("fail_at", range(1, 10))
def test_failed_gate_stops_without_candidate(tmp_path: Path, fail_at: int) -> None:
    root = _repo(tmp_path)
    process = ControlledProcess(root, fail_at=fail_at)

    result = RefreshOrchestrator(process).run(root, "abc123")

    assert result.status == "failed"
    assert len(process.commands) == fail_at
    assert result.candidate is None


def test_command_launch_error_is_an_explicit_stage_failure(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    class BrokenProcess:
        def run(self, command: Sequence[str], cwd: Path) -> CommandResult:
            raise OSError("cannot launch")

    result = RefreshOrchestrator(BrokenProcess()).run(root, "abc123")

    assert result.status == "failed"
    assert result.stages[0].stage == "sync"
    assert result.stages[0].status == "failed"


def test_missing_file_before_live_verification_is_an_explicit_failure(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ALLOWED_PATHS[0]).unlink()
    process = ControlledProcess(root)

    result = RefreshOrchestrator(process).run(root, "abc123")

    assert result.status == "failed"
    assert result.stages[-1].stage == "candidate"
    assert len(process.commands) == 8


@pytest.mark.parametrize(
    "defect",
    ["absent", "stale", "incomplete", "verifier", "mode", "schema", "old"],
)
def test_bad_live_evidence_rejects_candidate(tmp_path: Path, defect: str) -> None:
    root = _repo(tmp_path)
    process = ControlledProcess(root)

    def write_defective() -> None:
        if defect == "absent":
            return
        _evidence(
            root,
            observed="2020-01-01T00:00:00+00:00" if defect == "old" else None,
        )
        report_path = root / ".build/verify.json"
        report = json.loads(report_path.read_text())
        if defect == "stale":
            report["inputs"]["single"]["sha256"] = "0" * 64
        else:
            if defect == "incomplete":
                report["complete"] = False
                report["status"] = "running"
                report["completedAt"] = None
            elif defect == "verifier":
                report["verifier"]["version"] = "other"
            elif defect == "mode":
                report["mode"] = "offline"
            elif defect == "schema":
                report["schemaVersion"] = 999
        report_path.write_text(json.dumps(report))

    process.on_command[9] = write_defective
    result = RefreshOrchestrator(process).run(root, "abc123")

    assert result.status == "failed"
    assert result.stages[-1].stage == "candidate"
    assert result.candidate is None


def test_disposable_attempt_is_a_clean_checkout_at_requested_sha(
    tmp_path: Path,
) -> None:
    source = _repo(tmp_path)
    base = _git(source, "rev-parse", "HEAD")
    (source / "tracked.txt").write_text("dirty\n")

    with LocalAttemptFactory(source).checkout(base) as checkout:
        assert checkout != source
        assert _git(checkout, "rev-parse", "HEAD") == base
        assert (checkout / "tracked.txt").read_text() == "base\n"

    assert not checkout.exists()


@pytest.mark.parametrize("relative", ALLOWED_PATHS)
def test_candidate_rejects_missing_publishable_file(
    tmp_path: Path, relative: str
) -> None:
    root = _repo(tmp_path)
    (root / relative).unlink()
    _evidence(root)

    with pytest.raises(CandidateError, match="missing"):
        validate_candidate(root)


def test_candidate_rejects_symlink(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    path = root / ALLOWED_PATHS[0]
    path.unlink()
    path.symlink_to(root / ALLOWED_PATHS[1])
    _evidence(root)

    with pytest.raises(CandidateError, match="regular file"):
        validate_candidate(root)


def test_candidate_rejects_symlink_parent(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    dist = root / "dist"
    real_dist = root / "real-dist"
    dist.rename(real_dist)
    dist.symlink_to(real_dist, target_is_directory=True)
    _evidence(root)

    with pytest.raises(CandidateError, match="symlink directory"):
        validate_candidate(root)


def test_candidate_rejects_unexpected_tracked_change(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "tracked.txt").write_text("changed\n")
    _evidence(root)

    with pytest.raises(CandidateError, match="unexpected tracked"):
        validate_candidate(root)


def test_candidate_rejects_post_verification_mutation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _evidence(root)
    candidate = PublicationCandidate.capture(root)
    (root / ALLOWED_PATHS[2]).write_text("mutated\n")

    with pytest.raises(CandidateError, match="changed after verification"):
        candidate.stage_and_validate()


def test_candidate_rejects_staged_content_mismatch(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ALLOWED_PATHS[0]).write_text("candidate\n")
    _evidence(root)
    candidate = PublicationCandidate.capture(root)
    _git(root, "add", ALLOWED_PATHS[0])
    # Replace the index entry while leaving the verified working-tree bytes intact.
    blob = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=root,
            input=b"wrong\n",
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )
    _git(root, "update-index", "--cacheinfo", "100644", blob, ALLOWED_PATHS[0])

    with pytest.raises(CandidateError, match="staged content"):
        candidate.validate_staged()


def test_cache_only_change_is_publishable(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    cache = root / "config/package-ids.json"
    cache.write_text("new cache\n")
    _evidence(root)

    candidate = validate_candidate(root)

    assert candidate.changed_paths == ("config/package-ids.json",)
    assert candidate.snapshots["config/package-ids.json"] == b"new cache\n"


def test_catalog_interior_change_is_publishable_with_exact_snapshot(
    tmp_path: Path,
) -> None:
    from omnipack.catalog import replace_catalog

    root = _repo(tmp_path)
    readme = root / "README.md"
    expected = replace_catalog(readme.read_bytes(), b"new catalog\n")
    readme.write_bytes(expected)
    _evidence(root)

    candidate = validate_candidate(root)

    assert candidate.changed_paths == ("README.md",)
    assert candidate.snapshots["README.md"] == expected
    assert (
        subprocess.run(
            ["git", "show", ":README.md"], cwd=root, check=True, capture_output=True
        ).stdout
        == expected
    )


@pytest.mark.parametrize("phase", ["capture", "staged"])
def test_candidate_rejects_handwritten_readme_change(
    tmp_path: Path, phase: str
) -> None:
    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_bytes(readme.read_bytes().replace(b"guide", b"edited guide"))
    _evidence(root)

    if phase == "capture":
        with pytest.raises(CandidateError, match="outside catalog"):
            PublicationCandidate.capture(root)
        return

    readme.write_bytes(
        readme.read_bytes()
        .replace(b"edited guide", b"guide")
        .replace(b"base catalog", b"new catalog")
    )
    _evidence(root)
    candidate = PublicationCandidate.capture(root)
    _git(root, "add", "README.md")
    staged = subprocess.run(
        ["git", "show", ":README.md"], cwd=root, check=True, capture_output=True
    ).stdout.replace(b"guide", b"edited guide")
    blob = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=root,
            input=staged,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )
    _git(root, "update-index", "--cacheinfo", "100644", blob, "README.md")

    with pytest.raises(CandidateError, match="outside catalog"):
        candidate.validate_staged()


def test_malformed_readme_is_rejected_during_candidate_capture(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "README.md").write_text("no catalog markers\n")
    _evidence(root)

    with pytest.raises(CandidateError, match="catalog marker"):
        PublicationCandidate.capture(root)


def test_candidate_rejects_staged_readme_catalog_mismatch(tmp_path: Path) -> None:
    from omnipack.catalog import replace_catalog

    root = _repo(tmp_path)
    readme = root / "README.md"
    readme.write_bytes(replace_catalog(readme.read_bytes(), b"verified catalog\n"))
    _evidence(root)
    candidate = PublicationCandidate.capture(root)
    staged = replace_catalog(readme.read_bytes(), b"different staged catalog\n")
    blob = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=root,
            input=staged,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )
    _git(root, "update-index", "--cacheinfo", "100644", blob, "README.md")

    with pytest.raises(CandidateError, match="staged content"):
        candidate.validate_staged()


def test_successful_build_command_preserves_soft_failure_policy(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    process = ControlledProcess(root)

    def record_soft_failure_and_evidence() -> None:
        report = root / ".build/report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"status": "success", "retainedFailures": ["x"]}))
        _evidence(root)

    process.on_command[9] = record_soft_failure_and_evidence

    assert RefreshOrchestrator(process).run(root, "abc123").status == "no-op"


def test_byte_identical_candidate_is_noop(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _evidence(root)

    candidate = validate_candidate(root)

    assert candidate.changed_paths == ()
    assert set(candidate.snapshots) == set(ALLOWED_PATHS)


@pytest.mark.parametrize("byte_change", [False, True])
def test_candidate_ignores_mode_changes_and_preserves_base_mode(
    tmp_path: Path, byte_change: bool
) -> None:
    root = _repo(tmp_path)
    _git(root, "config", "core.fileMode", "true")
    path = root / ALLOWED_PATHS[0]
    if byte_change:
        path.write_text("changed bytes\n")
    path.chmod(0o755)
    _evidence(root)

    candidate = validate_candidate(root)

    assert candidate.changed_paths == ((ALLOWED_PATHS[0],) if byte_change else ())
    assert _git(root, "ls-files", "--stage", ALLOWED_PATHS[0]).startswith("100644 ")
    assert bool(_git(root, "diff", "--cached", "--name-only")) == byte_change


def test_readme_mode_change_is_noop_and_restores_base_mode(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "config", "core.fileMode", "true")
    (root / "README.md").chmod(0o755)
    _evidence(root)

    candidate = validate_candidate(root)

    assert candidate.changed_paths == ()
    assert _git(root, "ls-files", "--stage", "README.md").startswith("100644 ")
    assert not _git(root, "diff", "--cached", "--name-only")


@pytest.mark.parametrize("during_staging", [False, True])
def test_candidate_rejects_unrelated_mutation_after_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, during_staging: bool
) -> None:
    import scripts.nightly_publish as publishing

    root = _repo(tmp_path)
    _evidence(root)
    candidate = PublicationCandidate.capture(root)
    original = publishing._git

    def mutate(root: Path, *args: str) -> None:
        original(root, *args)
        (root / "tracked.txt").write_text("unexpected\n")

    if during_staging:
        monkeypatch.setattr(publishing, "_git", mutate)
    else:
        (root / "tracked.txt").write_text("unexpected\n")

    with pytest.raises(CandidateError, match="unexpected tracked"):
        candidate.stage_and_validate()
