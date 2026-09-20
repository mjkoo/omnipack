"""Tests for the standard-library write-side push and release commands.

This file imports only the standard library, pytest and the module under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import nightly_write as write_module
from scripts.nightly_write import (
    MARKER,
    run_push,
    run_release,
)
from scripts.workflow_support import HandoffRejected
from tests.publication_support import (
    OK,
    CommandResult,
    FakeGh,
    bare_remote,
    bundle,
    failure,
    install_failing_hooks,
    isolated_git_identity,
    repository,
    shallow_checkout,
)
from tests.publication_support import (
    git as _git,
)

pytestmark = pytest.mark.usefixtures(isolated_git_identity.__name__)

ALLOWED_PATHS = (
    "dist/single-screen.json",
    "dist/dual-screen.json",
    "README.md",
)


def _push_gh(*, auth_ok: bool = True) -> FakeGh:
    return FakeGh({("auth", "setup-git"): OK if auth_ok else failure()})


def _seed(tmp_path: Path, name: str = "seed") -> Path:
    return repository(
        tmp_path,
        {relative: f"base:{relative}\n" for relative in ALLOWED_PATHS},
        name=name,
    )


def _bot_commit(root: Path, changes: dict[str, str]) -> str:
    for relative, content in changes.items():
        path = root / relative
        path.write_text(content)
        _git(root, "add", "--", relative)
    _git(
        root,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(dist): nightly rebuild 2026-09-12",
    )
    return _git(root, "rev-parse", "HEAD")


def test_advanced_main_fails_before_push_and_reports_main_advanced(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)

    # Another run's push lands on main first.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.name", "Test")
    _git(other, "config", "user.email", "test@example.invalid")
    (other / "tracked.txt").write_text("advance\n")
    _git(other, "add", "tracked.txt")
    _git(other, "commit", "-qm", "advance")
    _git(other, "push", "-q", "origin", "HEAD:main")
    advanced = _git(other, "rev-parse", "HEAD")

    result = run_push(write_side, bundle_path, sha, base, gh=_push_gh())

    assert result.status == "failed"
    assert result.summary == f"push failed for {sha}: main advanced"
    assert _git(bare, "rev-parse", "main") == advanced


def test_rerun_after_own_push_fails_as_main_advanced_through_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    _git(seed, "push", "-q", str(bare), "HEAD:main")
    assert _git(bare, "rev-parse", "main") == sha
    write_side = shallow_checkout(tmp_path, bare, base)

    result = run_push(write_side, bundle_path, sha, base, gh=_push_gh())

    assert result.status == "failed"
    assert result.summary == f"push failed for {sha}: main advanced"
    assert _git(bare, "rev-parse", "main") == sha

    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(write_module, "SubprocessGhRunner", _push_gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    assert write_module.main(["push", "--bundle", str(bundle_path)]) == 1
    assert summary_path.read_text() == f"push failed for {sha}: main advanced\n"
    assert _git(bare, "rev-parse", "main") == sha


def test_push_propagates_handoff_rejection_before_remote_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    candidate = "a" * 40
    gh = _push_gh()

    def reject(*_args: object) -> None:
        raise HandoffRejected("fixture rejection")

    monkeypatch.setattr(write_module, "verify_handoff", reject)
    result = run_push(
        tmp_path, tmp_path / "candidate.bundle", candidate, "b" * 40, gh=gh
    )

    assert result.status == "failed"
    assert result.summary == f"push failed for {candidate}"
    assert "hand-off rejected: fixture rejection" in capsys.readouterr().err
    assert gh.calls == []


@pytest.mark.parametrize("case", ["disallowed", "empty", "symlink", "executable"])
def test_unsafe_candidate_commit_is_rejected(tmp_path: Path, case: str) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    if case == "disallowed":
        sha = _bot_commit(seed, {"tracked.txt": "sneaky\n"})
    elif case == "empty":
        _git(seed, "commit", "--allow-empty", "-qm", "empty")
        sha = _git(seed, "rev-parse", "HEAD")
    elif case == "symlink":
        target = seed / ALLOWED_PATHS[0]
        target.unlink()
        target.symlink_to(seed / "README.md")
        _git(seed, "add", "--", ALLOWED_PATHS[0])
        sha = _bot_commit(seed, {})
    else:
        _git(seed, "config", "core.fileMode", "true")
        (seed / "README.md").chmod(0o755)
        _git(seed, "add", "--", "README.md")
        sha = _bot_commit(seed, {})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)

    result = run_push(write_side, bundle_path, sha, base, gh=_push_gh())

    assert result.status == "failed"
    assert result.summary == f"push failed for {sha}"
    assert _git(bare, "rev-parse", "main") == base


@pytest.mark.parametrize(
    ("candidate_sha", "base_sha"),
    [
        ("main", "a" * 40),
        ("a" * 40, "main"),
        ("a" * 39, "b" * 40),
        ("A" * 40, "b" * 40),
    ],
)
def test_malformed_shas_are_rejected_before_any_fetch_or_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, candidate_sha: str, base_sha: str
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("unexpected subprocess"),
    )
    gh = _push_gh()

    result = run_push(
        tmp_path, tmp_path / "absent.bundle", candidate_sha, base_sha, gh=gh
    )

    assert result.status == "failed"
    assert result.summary == "push failed"
    assert gh.calls == []


def test_push_cli_fails_when_gh_cannot_hand_git_the_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)
    summary_path = tmp_path / "summary.md"
    gh = _push_gh(auth_ok=False)
    monkeypatch.setattr(write_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["push", "--bundle", str(bundle_path)])

    assert exit_code == 1
    assert summary_path.read_text() == f"push failed for {sha}\n"
    assert _git(bare, "rev-parse", "main") == base


def test_push_cli_reads_env_and_exit_code_and_writes_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)
    install_failing_hooks(
        write_side, "pre-push", "post-checkout", "reference-transaction"
    )
    summary_path = tmp_path / "summary.md"

    monkeypatch.setattr(write_module, "SubprocessGhRunner", _push_gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["push", "--bundle", str(bundle_path)])

    assert exit_code == 0
    assert summary_path.read_text() == f"published {sha}\n"
    assert _git(bare, "rev-parse", "main") == sha
    assert _git(write_side, "rev-parse", "HEAD") == sha


def test_rejected_push_logs_the_remote_error_and_keeps_it_out_of_the_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)
    pre_receive = bare / "hooks" / "pre-receive"
    pre_receive.write_text(
        "#!/bin/sh\necho 'protected branch: fixture says no' >&2\nexit 1\n"
    )
    pre_receive.chmod(0o755)
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(write_module, "SubprocessGhRunner", _push_gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["push", "--bundle", str(bundle_path)])

    assert exit_code == 1
    assert summary_path.read_text() == f"push failed for {sha}\n"
    assert "protected branch: fixture says no" in capsys.readouterr().err
    assert _git(bare, "rev-parse", "main") == base


def test_detach_failure_after_a_landed_push_reports_published_and_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _seed(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = _bot_commit(seed, {ALLOWED_PATHS[0]: "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    write_side = shallow_checkout(tmp_path, bare, base)
    # The remote accepts the push, then leaves the write side's index locked,
    # so the detach that follows the push fails.
    post_receive = bare / "hooks" / "post-receive"
    post_receive.write_text(f"#!/bin/sh\ntouch '{write_side}/.git/index.lock'\n")
    post_receive.chmod(0o755)
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(write_module, "SubprocessGhRunner", _push_gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["push", "--bundle", str(bundle_path)])

    assert exit_code == 1
    assert summary_path.read_text() == f"published {sha}\n"
    assert _git(bare, "rev-parse", "main") == sha
    assert "index.lock" in capsys.readouterr().err


# --- release -----------------------------------------------------------


def _release_repo(tmp_path: Path) -> tuple[Path, str]:
    root = repository(
        tmp_path,
        {
            "dist/single-screen.json": '{"apps": []}',
            "dist/dual-screen.json": '{"apps": [1]}',
        },
        name="release-repo",
    )
    sha = _git(root, "rev-parse", "HEAD")
    bare = bare_remote(root, tmp_path, name="release-remote.git")
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "main")
    return root, sha


def _digest(text: str) -> str:
    from hashlib import sha256

    return sha256(text.encode()).hexdigest()


SINGLE_DIGEST = _digest('{"apps": []}')
DUAL_DIGEST = _digest('{"apps": [1]}')


def _record_line(single: str, dual: str, commit: str) -> str:
    return (
        f"<!-- omnipack:digests single-screen.json={single} "
        f"dual-screen.json={dual} commit={commit} -->"
    )


BOOTSTRAP_BODY = (
    "<!-- omnipack:rolling-pack -->\n"
    "\n"
    "Initial pack publication is pending; JSON assets are not yet published.\n"
)


def _canonical_body(commit: str) -> str:
    return (
        "<!-- omnipack:rolling-pack -->\n"
        "\n"
        "Download the current pack pair directly from the stable URLs:\n"
        "- https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json\n"
        "- https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json\n"
        "\n"
        f"{_record_line(SINGLE_DIGEST, DUAL_DIGEST, commit)}\n"
    )


def _body(*, marker: bool = True, record: str | None = None) -> str:
    lines = []
    if marker:
        lines.append(MARKER)
    lines.append("")
    lines.append("Download the pack from the stable URLs.")
    if record is not None:
        lines.append(record)
    return "\n".join(lines)


def _valid_release(commit: str, **overrides: object) -> dict[str, object]:
    view: dict[str, object] = {
        "name": "omnipack revision 3",
        "body": _body(record=_record_line(SINGLE_DIGEST, DUAL_DIGEST, commit)),
        "assets": [
            {"name": "single-screen.json", "digest": f"sha256:{SINGLE_DIGEST}"},
            {"name": "dual-screen.json", "digest": f"sha256:{DUAL_DIGEST}"},
        ],
        "isDraft": False,
        "isPrerelease": True,
        "isImmutable": False,
    }
    view.update(overrides)
    return view


def _release_gh(
    *,
    view: dict | None,
    view_ok: bool = True,
    view_stderr: str = "release not found",
    upload_ok: bool = True,
    edit_ok: bool = True,
    auth_ok: bool = True,
) -> FakeGh:
    return FakeGh(
        {
            ("auth", "setup-git"): OK if auth_ok else failure(),
            ("release", "view"): (
                CommandResult(0, json.dumps(view), "")
                if view_ok
                else failure(view_stderr)
            ),
            ("release", "upload"): OK if upload_ok else failure(),
            ("release", "edit"): OK if edit_ok else failure(),
        }
    )


def test_comparison_ignores_the_recorded_commit_and_uses_digests_only(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    # The recorded commit is stale and unrelated; only the digests decide
    # "unchanged", never this field.
    view = _valid_release("9" * 40)
    assets = view["assets"]
    assert isinstance(assets, list)
    assets.append({"name": "extra-file.txt", "digest": "sha256:" + "7" * 64})
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "unchanged"
    assert result.summary == "unchanged at revision 3"
    assert not any(call[:2] == ("release", "upload") for call in gh.calls)
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


def test_duplicate_record_lines_count_as_no_valid_record(tmp_path: Path) -> None:
    root, sha = _release_repo(tmp_path)
    record = _record_line(SINGLE_DIGEST, DUAL_DIGEST, sha)
    view = _valid_release(sha, body=_body(record=record) + f"\n{record}\n")
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "advanced"
    assert result.summary == "revision 4"
    assert any(call[:2] == ("release", "upload") for call in gh.calls)


def test_malformed_record_line_counts_as_no_valid_record(tmp_path: Path) -> None:
    root, sha = _release_repo(tmp_path)
    malformed = (
        f"<!-- omnipack:digests single-screen.json={SINGLE_DIGEST[:-1]} "
        f"dual-screen.json={DUAL_DIGEST} commit={sha} -->"
    )
    view = _valid_release(sha, body=_body(record=malformed))
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "advanced"
    assert result.summary == "revision 4"


def test_differing_record_uploads_and_edits_with_canonical_body(
    tmp_path: Path,
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(
        sha,
        body=_body(record=_record_line("0" * 64, "1" * 64, "a" * 40)),
        assets=[],
    )
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "advanced"
    assert result.summary == "revision 4"
    upload_calls = [call for call in gh.calls if call[:2] == ("release", "upload")]
    edit_calls = [call for call in gh.calls if call[:2] == ("release", "edit")]
    assert len(upload_calls) == 1
    assert len(edit_calls) == 1
    assert gh.calls.index(upload_calls[0]) < gh.calls.index(edit_calls[0])
    assert upload_calls[0] == (
        "release",
        "upload",
        "continuous",
        str(root / "dist/single-screen.json"),
        str(root / "dist/dual-screen.json"),
        "--clobber",
    )
    assert gh.texts_for(("release", "edit"), "--notes-file") == [_canonical_body(sha)]
    assert "omnipack revision 4" in edit_calls[0]


def test_bootstrap_seed_is_replaced_by_the_canonical_body_at_revision_1(
    tmp_path: Path,
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(
        sha, name="omnipack revision 0", body=BOOTSTRAP_BODY, assets=[]
    )
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "advanced"
    assert result.summary == "revision 1"
    upload_calls = [call for call in gh.calls if call[:2] == ("release", "upload")]
    assert upload_calls == [
        (
            "release",
            "upload",
            "continuous",
            str(root / "dist/single-screen.json"),
            str(root / "dist/dual-screen.json"),
            "--clobber",
        )
    ]
    assert gh.texts_for(("release", "edit"), "--notes-file") == [_canonical_body(sha)]


@pytest.mark.parametrize(
    "assets",
    [
        [{"name": "dual-screen.json", "digest": f"sha256:{DUAL_DIGEST}"}],
        [
            {"name": "single-screen.json", "digest": None},
            {"name": "dual-screen.json", "digest": f"sha256:{DUAL_DIGEST}"},
        ],
        [
            {"name": "single-screen.json"},
            {"name": "dual-screen.json", "digest": f"sha256:{DUAL_DIGEST}"},
        ],
    ],
)
def test_missing_or_absent_served_digest_repairs_without_edit(
    tmp_path: Path, assets: list[dict]
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(sha, assets=assets)
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "repaired"
    assert result.summary == "repaired at revision 3"
    assert [call for call in gh.calls if call[:2] == ("release", "upload")] == [
        (
            "release",
            "upload",
            "continuous",
            str(root / "dist/single-screen.json"),
            str(root / "dist/dual-screen.json"),
            "--clobber",
        )
    ]
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


@pytest.mark.parametrize("different_asset", ["single-screen.json", "dual-screen.json"])
def test_interrupted_upload_then_run_returning_to_recorded_pair_repairs(
    tmp_path: Path,
    different_asset: str,
) -> None:
    root, sha = _release_repo(tmp_path)
    # Pair B's edit never completed: record and title still describe pair A,
    # but only one asset was actually replaced with B's bytes.
    assets = [
        {"name": "single-screen.json", "digest": f"sha256:{SINGLE_DIGEST}"},
        {"name": "dual-screen.json", "digest": f"sha256:{DUAL_DIGEST}"},
    ]
    for asset in assets:
        if asset["name"] == different_asset:
            asset["digest"] = "sha256:" + "9" * 64
    view = _valid_release(
        sha,
        name="omnipack revision 5",
        assets=assets,
    )
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "repaired"
    assert result.summary == "repaired at revision 5"
    assert [call for call in gh.calls if call[:2] == ("release", "upload")] == [
        (
            "release",
            "upload",
            "continuous",
            str(root / "dist/single-screen.json"),
            str(root / "dist/dual-screen.json"),
            "--clobber",
        )
    ]
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


@pytest.mark.parametrize(
    ("overrides", "reason_substring"),
    [
        ({"name": "omnipack revision 1", "body": "no marker here"}, "marker"),
        ({"name": "not a revision"}, "title"),
    ],
)
def test_invalid_release_marker_or_title_fails_with_bootstrap_guidance(
    tmp_path: Path,
    overrides: dict[str, object],
    reason_substring: str,
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(sha, **overrides)
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary.startswith("release failed:")
    assert reason_substring in result.summary
    assert "gh release create" in result.summary
    assert not any(call[:2] == ("release", "upload") for call in gh.calls)
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


@pytest.mark.parametrize(
    ("is_draft", "is_prerelease", "is_immutable", "reason"),
    [
        (True, True, False, "release is a draft"),
        (False, False, False, "release is not a prerelease"),
        (False, True, True, "release is immutable"),
    ],
)
def test_draft_non_prerelease_or_immutable_fails_with_bootstrap_guidance(
    tmp_path: Path, is_draft: bool, is_prerelease: bool, is_immutable: bool, reason: str
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(
        sha,
        assets=[],
        isDraft=is_draft,
        isPrerelease=is_prerelease,
        isImmutable=is_immutable,
    )
    gh = _release_gh(view=view)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == (
        f"release failed: {reason}; {write_module.BOOTSTRAP_GUIDANCE}"
    )
    assert not any(call[:2] == ("release", "upload") for call in gh.calls)
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


def test_symlinked_pack_file_fails_before_any_release_call(tmp_path: Path) -> None:
    root, _sha = _release_repo(tmp_path)
    runner_file = tmp_path / "runner-file"
    runner_file.write_text("not a pack\n")
    pack = root / "dist/single-screen.json"
    pack.unlink()
    pack.symlink_to(runner_file)
    gh = _release_gh(view=None)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == (
        "release failed: dist/single-screen.json is not a regular file"
    )
    assert gh.calls == []


def test_bootstrap_guidance_command_matches_the_publishing_guide() -> None:
    command = write_module.BOOTSTRAP_GUIDANCE.split("`")[1]
    guide = (Path(__file__).parents[1] / "docs/publishing.md").read_text()
    flattened = " ".join(guide.replace("\\\n", " ").split())

    assert "docs/publishing.md" in write_module.BOOTSTRAP_GUIDANCE
    assert command.startswith("gh release create continuous --prerelease")
    assert command in flattened


def test_upload_failure_prevents_edit_without_bootstrap_guidance(
    tmp_path: Path,
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(
        sha,
        body=_body(record=_record_line("0" * 64, "1" * 64, "a" * 40)),
        assets=[],
    )
    gh = _release_gh(view=view, upload_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary.startswith("release failed:")
    assert "gh release create" not in result.summary
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


def test_remote_main_other_than_head_fails_without_bootstrap_guidance(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    # A later run pushed past this run's HEAD.
    other = root.parent / "other"
    subprocess.run(
        ["git", "clone", "-q", str(root.parent / "release-remote.git"), str(other)],
        check=True,
    )
    _git(other, "config", "user.name", "Test")
    _git(other, "config", "user.email", "test@example.invalid")
    (other / "tracked.txt").write_text("advance\n")
    _git(other, "add", "tracked.txt")
    _git(other, "commit", "-qm", "advance")
    _git(other, "push", "-q", "origin", "HEAD:main")

    gh = _release_gh(view=None, view_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: main advanced"
    assert "gh release create" not in result.summary
    assert gh.calls == [("auth", "setup-git")]


def test_head_read_failure_fails_with_release_failed_reason(
    tmp_path: Path,
) -> None:
    root = tmp_path / "empty-repo"
    root.mkdir()
    _git(root, "init", "-q", "--initial-branch=main")
    (root / "dist").mkdir()
    (root / "dist/single-screen.json").write_text('{"apps": []}')
    (root / "dist/dual-screen.json").write_text('{"apps": [1]}')
    gh = _release_gh(view=None, view_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: could not read HEAD"
    assert "gh release create" not in result.summary
    assert gh.calls == []


def test_missing_pack_file_fails_with_release_failed_reason_and_no_writes(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    (root / "dist/single-screen.json").unlink()
    gh = _release_gh(view=None, view_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: could not read release assets"
    assert gh.calls == []


def test_gh_auth_failure_fails_with_specific_reason_and_no_writes(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    gh = _release_gh(view=None, view_ok=False, auth_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: gh auth setup-git failed"
    assert "gh release create" not in result.summary
    assert gh.calls == [("auth", "setup-git")]


def test_ls_remote_command_failure_fails_with_specific_reason_and_no_writes(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    _git(root, "remote", "remove", "origin")
    gh = _release_gh(view=None, view_ok=False)

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: could not read remote main"
    assert "gh release create" not in result.summary
    assert gh.calls == [("auth", "setup-git")]


def test_release_cli_exit_code_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(sha)
    summary_path = tmp_path / "summary.md"

    monkeypatch.setattr(
        write_module, "SubprocessGhRunner", lambda: _release_gh(view=view)
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["release"])

    assert exit_code == 0
    assert summary_path.read_text() == "unchanged at revision 3\n"


def test_release_view_failure_other_than_not_found_has_no_bootstrap_guidance(
    tmp_path: Path,
) -> None:
    root, _sha = _release_repo(tmp_path)
    gh = _release_gh(view=None, view_ok=False, view_stderr="HTTP 502: Bad Gateway")

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == "release failed: could not read release"
    assert not any(call[:2] == ("release", "upload") for call in gh.calls)


def test_release_not_found_is_missing_with_bootstrap_guidance(tmp_path: Path) -> None:
    root, _sha = _release_repo(tmp_path)
    gh = _release_gh(view=None, view_ok=False, view_stderr="release not found\n")

    result = run_release(root, gh=gh)

    assert result.status == "failed"
    assert result.summary == (
        f"release failed: release is missing; {write_module.BOOTSTRAP_GUIDANCE}"
    )
    assert not any(call[:2] == ("release", "upload") for call in gh.calls)
    assert not any(call[:2] == ("release", "edit") for call in gh.calls)


def test_release_cli_fails_when_the_release_edit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, sha = _release_repo(tmp_path)
    view = _valid_release(
        sha,
        body=_body(record=_record_line("0" * 64, "1" * 64, "a" * 40)),
        assets=[],
    )
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(
        write_module,
        "SubprocessGhRunner",
        lambda: _release_gh(view=view, edit_ok=False),
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = write_module.main(["release"])

    assert exit_code == 1
    assert summary_path.read_text() == "release failed: release edit failed\n"
