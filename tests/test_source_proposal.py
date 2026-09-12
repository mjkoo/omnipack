"""Tests for the guarded source-update `stage` and `publish` commands.

This file imports only the standard library, pytest and the module under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter. Git runs in an isolated environment (no global
identity), so these tests exercise the actual commit, hand-off and PR
selection behavior against temporary repositories and a bare remote.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import source_proposal as proposal_module
from scripts.nightly_write import CommandResult
from scripts.source_proposal import (
    BOT_EMAIL,
    BOT_NAME,
    BRANCH_NAME,
    CATALOG_PATH,
    run_publish,
    run_stage,
)

CANDIDATE_DIR = ".build/source-generation/codm"


@pytest.fixture(autouse=True)
def _isolated_git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    catalog_path = root / CATALOG_PATH
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text('{"apps": []}\n')
    (root / "dist").mkdir()
    (root / "dist/single-screen.json").write_text('{"apps": []}\n')
    (root / "README.md").write_text("guide\n")
    (root / ".gitignore").write_text(".build/\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _write_candidate(root: Path, catalog_text: str, report: dict) -> None:
    generation_dir = root / CANDIDATE_DIR
    generation_dir.mkdir(parents=True, exist_ok=True)
    (generation_dir / "catalog.json").write_text(catalog_text)
    (generation_dir / "report.json").write_text(json.dumps(report))


def _report(
    *,
    added: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
    changed: tuple[str, ...] = (),
    retained_failures: tuple[tuple[str, str], ...] = (),
) -> dict:
    return {
        "status": "success",
        "changes": {
            "added": list(added),
            "removed": list(removed),
            "changed": list(changed),
        },
        "retainedFailures": [
            {"url": url, "message": message} for url, message in retained_failures
        ],
    }


# --- stage ----------------------------------------------------------------


def test_head_other_than_github_sha_fails_with_no_commit_or_bundle(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _write_candidate(root, '{"apps": [1]}\n', _report())
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(
        root, "0" * 40, "https://github.example/runs/1", bundle_path, body_path
    )

    assert outcome.status == "failed"
    assert outcome.stage == "checkout"
    assert not bundle_path.exists()
    assert not body_path.exists()


def test_unchanged_candidate_writes_neither_bundle_nor_body(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": []}\n', _report())
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(
        root, base, "https://github.example/runs/1", bundle_path, body_path
    )

    assert outcome.status == "unchanged"
    assert not outcome.changed
    assert outcome.base_sha == base
    assert outcome.sha == base
    assert not bundle_path.exists()
    assert not body_path.exists()
    assert _git(root, "rev-parse", "HEAD") == base
    assert _git(root, "branch", "--list", BRANCH_NAME) == ""


def test_changed_candidate_writes_bundle_and_body_with_run_url_and_base_sha(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(
        root, base, "https://github.example/runs/9", bundle_path, body_path
    )

    assert outcome.status == "changed"
    assert outcome.changed
    assert outcome.base_sha == base
    sha = outcome.sha
    assert sha is not None
    assert sha != base

    heads = _git(root, "bundle", "list-heads", str(bundle_path))
    assert heads == f"{sha} HEAD"
    verification = _git(root, "bundle", "verify", str(bundle_path))
    assert base in verification

    body_text = body_path.read_text()
    assert "https://github.example/runs/9" in body_text
    assert base in body_text


def test_changed_candidate_commits_only_the_catalog_as_the_bot(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(root, base, "run", bundle_path, body_path)
    assert outcome.status == "changed"
    sha = outcome.sha
    assert sha is not None

    assert _git(root, "show", "-s", "--format=%an <%ae>%n%cn <%ce>", sha) == (
        f"{BOT_NAME} <{BOT_EMAIL}>\n{BOT_NAME} <{BOT_EMAIL}>"
    )
    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
        == CATALOG_PATH
    )

    # Later working-tree changes (as later steps in the check job would make)
    # do not affect the commit already made.
    (root / "dist/single-screen.json").write_text('{"apps": [1]}\n')
    (root / "README.md").write_text("changed guide\n")

    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
        == CATALOG_PATH
    )
    assert _git(root, "rev-parse", sha) == sha


def test_symlinked_generated_candidate_fails_with_no_commit_or_bundle(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": [1]}\n', _report())
    candidate_path = root / CANDIDATE_DIR / "catalog.json"
    candidate_path.unlink()
    candidate_path.symlink_to(root / CATALOG_PATH)
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(root, base, "run", bundle_path, body_path)

    assert outcome.status == "failed"
    assert outcome.stage == "symlink"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()
    assert not body_path.exists()


def test_symlinked_catalog_fails_with_no_commit_or_bundle(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": [1]}\n', _report())
    catalog_path = root / CATALOG_PATH
    catalog_path.unlink()
    catalog_path.symlink_to(root / "README.md")
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(root, base, "run", bundle_path, body_path)

    assert outcome.status == "failed"
    assert outcome.stage == "symlink"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()
    assert not body_path.exists()


def test_base_sha_line_in_summary_names_the_branch_creation_commit(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": [1]}\n', _report())
    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert f"Base SHA: {base}" in outcome.summary


def test_retained_failures_appear_in_the_summary(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root,
        '{"apps": []}\n',
        _report(retained_failures=(("https://example.test/proj", "network error"),)),
    )
    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert "https://example.test/proj" in outcome.summary
    assert "network error" in outcome.summary


def test_markdown_bearing_retained_failure_message_is_escaped_in_a_pre_block(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    # A backtick is HTML-safe as-is, so escaping is visible only through the
    # bracket and bang characters, which html.escape leaves untouched too;
    # the real assertion is structural: the text sits inside <pre>...</pre>
    # rather than being interpreted as Markdown by anything upstream of it.
    message = "[x](https://example.test) ![i](https://example.test/i.png) `y`"
    _write_candidate(
        root,
        '{"apps": []}\n',
        _report(retained_failures=(("https://example.test/proj", message),)),
    )
    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert "<pre>" in outcome.summary
    pre_start = outcome.summary.index("<pre>")
    pre_end = outcome.summary.index("</pre>")
    assert message in outcome.summary[pre_start:pre_end]
    assert message not in outcome.summary[:pre_start]


def test_html_bearing_retained_failure_message_is_html_escaped(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    message = '<script>alert(1)</script> & "quoted"'
    _write_candidate(
        root,
        '{"apps": []}\n',
        _report(retained_failures=(("https://example.test/proj", message),)),
    )
    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert message not in outcome.summary
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quoted&quot;" in (
        outcome.summary
    )


def test_stage_cli_reads_env_and_exit_code_and_writes_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    output_path = tmp_path / "output.txt"
    summary_path = tmp_path / "summary.md"

    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_SHA", base)
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")

    exit_code = proposal_module.main(["stage"])

    assert exit_code == 0
    output_text = output_path.read_text()
    assert "changed=true" in output_text
    assert (runner_temp / "source-handoff" / "candidate.bundle").exists()
    assert (runner_temp / "source-handoff" / "pr-body.md").exists()
    assert (
        "https://github.example/mjkoo/omnipack/actions/runs/42"
        in (runner_temp / "source-handoff" / "pr-body.md").read_text()
    )


# --- publish ----------------------------------------------------------------


class ScriptedGh:
    def __init__(
        self,
        *,
        pr_list: list[dict] | None = None,
        auth_ok: bool = True,
        pr_list_ok: bool = True,
        close_ok: bool = True,
        edit_ok: bool = True,
        create_ok: bool = True,
    ) -> None:
        self.pr_list = pr_list if pr_list is not None else []
        self.auth_ok = auth_ok
        self.pr_list_ok = pr_list_ok
        self.close_ok = close_ok
        self.edit_ok = edit_ok
        self.create_ok = create_ok
        self.calls: list[tuple[str, ...]] = []
        self.created_bodies: list[str] = []
        self.edited_bodies: list[str] = []

    def run(self, args):
        args = tuple(args)
        self.calls.append(args)
        if args[:2] == ("auth", "setup-git"):
            return CommandResult(0 if self.auth_ok else 1, "", "")
        if args[:2] == ("pr", "list"):
            if not self.pr_list_ok:
                return CommandResult(1, "", "")
            return CommandResult(0, json.dumps(self.pr_list), "")
        if args[:2] == ("pr", "close"):
            return CommandResult(0 if self.close_ok else 1, "", "")
        if args[:2] == ("pr", "edit"):
            body_path = Path(args[args.index("--body-file") + 1])
            self.edited_bodies.append(body_path.read_text())
            return CommandResult(0 if self.edit_ok else 1, "", "")
        if args[:2] == ("pr", "create"):
            body_path = Path(args[args.index("--body-file") + 1])
            self.created_bodies.append(body_path.read_text())
            return CommandResult(0 if self.create_ok else 1, "", "")
        raise AssertionError(f"unexpected gh command {args}")


def _bare_branch_sha(bare: Path) -> str:
    """The bot branch's tip on `bare` itself, read directly from its own refs
    rather than through a remote named "origin" (which, after `_bare_from`'s
    clone, points back at `seed` and would report `seed`'s own branch)."""
    return _git(
        bare, "for-each-ref", "--format=%(objectname)", f"refs/heads/{BRANCH_NAME}"
    )


def _pr(number: int, *, cross_repo: bool = False, owner: str = "mjkoo") -> dict:
    return {
        "number": number,
        "isCrossRepository": cross_repo,
        "headRepositoryOwner": {"login": owner},
    }


def _bare_from(seed: Path, tmp_path: Path, name: str = "remote.git") -> Path:
    """Clone only `main`, so a local branch `stage` left checked out in
    `seed` (or created by hand in a test) never leaks onto the remote."""
    bare = tmp_path / name
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--bare",
            "--single-branch",
            "--branch",
            "main",
            str(seed),
            str(bare),
        ],
        check=True,
    )
    return bare


def _write_side(
    tmp_path: Path, bare: Path, base: str, name: str = "write-side"
) -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "remote", "add", "origin", f"file://{bare}")
    _git(root, "fetch", "-q", "--depth", "1", "origin", base)
    _git(root, "checkout", "-q", "--detach", "FETCH_HEAD")
    assert _git(root, "rev-parse", "--is-shallow-repository") == "true"
    return root


def _staged_candidate(
    tmp_path: Path, *, seed_name: str = "seed"
) -> tuple[Path, str, str, Path, Path]:
    """Run a real `stage` to produce a commit, its bundle and body file."""
    seed = _repo(tmp_path, seed_name)
    base = _git(seed, "rev-parse", "HEAD")
    _write_candidate(
        seed, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    bundle_path = tmp_path / f"{seed_name}-candidate.bundle"
    body_path = tmp_path / f"{seed_name}-pr-body.md"
    outcome = run_stage(
        seed, base, "https://github.example/runs/1", bundle_path, body_path
    )
    assert outcome.status == "changed"
    sha = outcome.sha
    assert sha is not None
    return seed, base, sha, bundle_path, body_path


def test_unchanged_closes_an_open_pr_and_makes_no_push_or_pr_write(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = _bare_from(seed, tmp_path)
    _git(seed, "remote", "add", "origin", str(bare))
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(7)])

    result = run_publish(write_side, "false", base, base, None, None, gh=gh)

    assert result.status == "closed"
    assert any(call[:2] == ("pr", "close") for call in gh.calls)
    assert not any(call[:2] == ("pr", "create") for call in gh.calls)
    assert not any(call[:2] == ("pr", "edit") for call in gh.calls)
    assert _bare_branch_sha(bare) == ""


def test_unchanged_with_no_open_pr_makes_no_write(tmp_path: Path) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "false", base, base, None, None, gh=gh)

    assert result.status == "unchanged"
    assert not any(call[:2] == ("pr", "close") for call in gh.calls)


def test_changed_with_no_open_pr_creates_one_from_the_body_file(
    tmp_path: Path,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    create_calls = [call for call in gh.calls if call[:2] == ("pr", "create")]
    assert len(create_calls) == 1
    body_text = gh.created_bodies[0]
    assert "https://github.example/runs/1" in body_text
    assert base in body_text
    assert _git(bare, "rev-parse", f"refs/heads/{BRANCH_NAME}") == sha


def test_changed_with_an_open_pr_edits_its_body(tmp_path: Path) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(3)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    edit_calls = [call for call in gh.calls if call[:2] == ("pr", "edit")]
    assert len(edit_calls) == 1
    assert not any(call[:2] == ("pr", "create") for call in gh.calls)
    assert _git(bare, "rev-parse", f"refs/heads/{BRANCH_NAME}") == sha


def test_equal_trees_make_no_push_even_with_a_different_hand_made_commit(
    tmp_path: Path,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)

    # A hand-made commit on the bot branch whose tree matches the rebuild.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.name", "Someone")
    _git(other, "config", "user.email", "someone@example.invalid")
    _git(other, "checkout", "-q", "-b", BRANCH_NAME, base)
    _git(other, "checkout", sha, "--", CATALOG_PATH)
    _git(other, "commit", "-qm", "hand-made")
    hand_made_sha = _git(other, "rev-parse", "HEAD")
    _git(other, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH_NAME}")

    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(4)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert _git(bare, "rev-parse", f"refs/heads/{BRANCH_NAME}") == hand_made_sha
    edit_calls = [call for call in gh.calls if call[:2] == ("pr", "edit")]
    assert len(edit_calls) == 1


def test_bare_remote_without_the_branch_pushes_and_creates_pr(tmp_path: Path) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert _git(bare, "rev-parse", f"refs/heads/{BRANCH_NAME}") == sha
    assert any(call[:2] == ("pr", "create") for call in gh.calls)


def test_fork_pr_sharing_the_branch_name_is_untouched_and_own_pr_is_created(
    tmp_path: Path,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(11, cross_repo=True, owner="someoneelse")])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert not any(call[:2] == ("pr", "close") for call in gh.calls)
    assert not any(call[:2] == ("pr", "edit") for call in gh.calls)
    assert any(call[:2] == ("pr", "create") for call in gh.calls)


def test_two_selected_same_repository_prs_fail_before_any_write(
    tmp_path: Path,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(1), _pr(2)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert result.summary == "publish failed"
    assert not any(
        call[:2] in (("pr", "close"), ("pr", "edit"), ("pr", "create"))
        for call in gh.calls
    )
    assert _bare_branch_sha(bare) == ""


def test_bundle_with_wrong_parent_fails_before_any_push_or_pr_write(
    tmp_path: Path,
) -> None:
    seed, base, sha, _bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)

    # A commit with the same catalog content as the real candidate, but
    # built on an unrelated parent instead of `base`.
    _git(seed, "checkout", "-q", "main")
    (seed / "tracked.txt").write_text("unrelated\n")
    _git(seed, "add", "tracked.txt")
    _git(seed, "commit", "-qm", "unrelated")
    wrong_base = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "-B", BRANCH_NAME)
    _git(seed, "checkout", sha, "--", CATALOG_PATH)
    _git(seed, "add", "--", CATALOG_PATH)
    _git(
        seed,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(catalog): update reviewed codm source",
    )
    wrong_parent_sha = _git(seed, "rev-parse", "HEAD")
    wrong_bundle_path = tmp_path / "wrong-parent.bundle"
    _git(seed, "bundle", "create", str(wrong_bundle_path), f"{wrong_base}..HEAD")
    gh = ScriptedGh(pr_list=[])

    result = run_publish(
        write_side, "true", wrong_parent_sha, base, wrong_bundle_path, body_path, gh=gh
    )

    assert result.status == "failed"
    assert not any(call[:2] == ("pr", "create") for call in gh.calls)
    assert _bare_branch_sha(bare) == ""


def test_bundle_head_not_matching_candidate_is_rejected(tmp_path: Path) -> None:
    seed, base, _sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(
        write_side, "true", "a" * 40, base, bundle_path, body_path, gh=gh
    )

    assert result.status == "failed"
    assert _bare_branch_sha(bare) == ""


def test_commit_changing_a_file_other_than_the_catalog_is_rejected(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "-b", BRANCH_NAME)
    (seed / "tracked.txt").write_text("sneaky\n")
    _git(seed, "add", "tracked.txt")
    _git(
        seed,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(catalog): update reviewed codm source",
    )
    sha = _git(seed, "rev-parse", "HEAD")
    bundle_path = tmp_path / "candidate.bundle"
    _git(seed, "bundle", "create", str(bundle_path), f"{base}..HEAD")
    body_path = tmp_path / "pr-body.md"
    body_path.write_text("body\n")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert _bare_branch_sha(bare) == ""


def test_commit_replacing_the_catalog_with_a_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "-b", BRANCH_NAME)
    target = seed / CATALOG_PATH
    target.unlink()
    target.symlink_to(seed / "README.md")
    _git(seed, "add", "--", CATALOG_PATH)
    _git(
        seed,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(catalog): update reviewed codm source",
    )
    sha = _git(seed, "rev-parse", "HEAD")
    bundle_path = tmp_path / "candidate.bundle"
    _git(seed, "bundle", "create", str(bundle_path), f"{base}..HEAD")
    body_path = tmp_path / "pr-body.md"
    body_path.write_text("body\n")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert _bare_branch_sha(bare) == ""


def test_commit_setting_the_catalogs_executable_bit_is_rejected(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "-b", BRANCH_NAME)
    _git(seed, "config", "core.fileMode", "true")
    (seed / CATALOG_PATH).chmod(0o755)
    _git(seed, "add", "--", CATALOG_PATH)
    _git(
        seed,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(catalog): update reviewed codm source",
    )
    sha = _git(seed, "rev-parse", "HEAD")
    bundle_path = tmp_path / "candidate.bundle"
    _git(seed, "bundle", "create", str(bundle_path), f"{base}..HEAD")
    body_path = tmp_path / "pr-body.md"
    body_path.write_text("body\n")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert _bare_branch_sha(bare) == ""


def test_remote_main_other_than_base_fails_on_both_paths(tmp_path: Path) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)

    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.name", "Test")
    _git(other, "config", "user.email", "test@example.invalid")
    (other / "tracked.txt").write_text("advance\n")
    _git(other, "add", "tracked.txt")
    _git(other, "commit", "-qm", "advance")
    _git(other, "push", "-q", "origin", "HEAD:main")

    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(9)])

    unchanged_result = run_publish(write_side, "false", base, base, None, None, gh=gh)
    assert unchanged_result.status == "failed"
    assert unchanged_result.summary == "publish failed: main advanced"
    assert not any(call[:2] == ("pr", "close") for call in gh.calls)

    gh2 = ScriptedGh(pr_list=[_pr(9)])
    changed_result = run_publish(
        write_side, "true", sha, base, bundle_path, body_path, gh=gh2
    )
    assert changed_result.status == "failed"
    assert changed_result.summary == "publish failed: main advanced"
    assert not any(
        call[:2] in (("pr", "close"), ("pr", "edit"), ("pr", "create"))
        for call in gh2.calls
    )


@pytest.mark.parametrize(
    ("changed", "candidate_sha", "base_sha"),
    [
        ("true", "main", "a" * 40),
        ("true", "a" * 40, "main"),
        ("true", "a" * 39, "b" * 40),
        ("true", "A" * 40, "b" * 40),
        ("maybe", "a" * 40, "b" * 40),
    ],
)
def test_malformed_env_values_are_rejected_before_any_fetch_or_write(
    tmp_path: Path, changed: str, candidate_sha: str, base_sha: str
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(
        write_side, changed, candidate_sha, base_sha, None, None, gh=gh
    )

    assert result.status == "failed"
    assert result.summary == "publish failed"
    assert gh.calls == []


def test_markdown_bearing_asset_name_is_escaped_in_the_pr_body(
    tmp_path: Path,
) -> None:
    message = "[x](https://example.test) ![i](https://example.test/i.png) `y`"
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    _write_candidate(
        seed,
        '{"apps": [{"id": "a"}]}\n',
        _report(retained_failures=(("https://example.test/proj", message),)),
    )
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"
    outcome = run_stage(
        seed, base, "https://github.example/runs/1", bundle_path, body_path
    )
    assert outcome.status == "changed"
    sha = outcome.sha
    assert sha is not None

    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    body_text = gh.created_bodies[0]
    assert message in body_text
    assert "<pre>" in body_text
