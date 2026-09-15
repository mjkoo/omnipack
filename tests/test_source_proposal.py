"""Tests for the guarded source-update `stage` and `publish` commands.

This file imports only the standard library, pytest and the module under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter. Git runs in an isolated environment (no global
identity), so these tests exercise the actual commit, hand-off and PR
selection behavior against temporary repositories and a bare remote.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import source_proposal as proposal_module
from scripts.source_proposal import (
    BRANCH_NAME,
    CATALOG_PATH,
    run_publish,
    run_stage,
)
from scripts.workflow_support import BOT_EMAIL, BOT_NAME, CommandResult

CANDIDATE_DIR = ".build/source-generation/codm"


@pytest.fixture(autouse=True)
def _isolated_git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in list(os.environ):
        if name.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_")):
            monkeypatch.delenv(name)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _install_failing_hooks(root: Path, *names: str) -> None:
    """Hooks that would fail any git command that ran them."""
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    for name in names:
        hook = hooks / name
        hook.write_text("#!/bin/sh\necho 'a repository hook ran' >&2\nexit 1\n")
        hook.chmod(0o755)


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
    assert outcome.summary == "stage failed: HEAD is not GITHUB_SHA"
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
    assert f"Base SHA: {base}" in outcome.summary


def _pre_block(text: str) -> str:
    return text[text.index("<pre>") : text.index("</pre>")]


def test_catalog_changes_appear_escaped_in_the_summary_and_body(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root,
        '{"apps": [{"id": "a"}]}\n',
        _report(
            added=("https://example.test/a?x=1&y=2",),
            removed=("https://example.test/<removed>",),
            changed=("https://example.test/c&d",),
        ),
    )
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(
        root, base, "https://github.example/runs/9", tmp_path / "b.bundle", body_path
    )

    expected = (
        "Added:\nhttps://example.test/a?x=1&amp;y=2\n\n"
        "Removed:\nhttps://example.test/&lt;removed&gt;\n\n"
        "Changed:\nhttps://example.test/c&amp;d\n\n"
        "Retained failures:\n"
    )
    assert expected in _pre_block(outcome.summary)
    assert expected in _pre_block(body_path.read_text())


def test_repository_hooks_never_run_when_staging(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _install_failing_hooks(
        root, "pre-commit", "commit-msg", "post-commit", "post-checkout"
    )
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )

    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert outcome.status == "changed"
    assert _git(root, "rev-parse", "--abbrev-ref", "HEAD") == BRANCH_NAME


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


def test_workspace_edits_outside_the_catalog_are_never_staged(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    policy_path = root / "config/codm-projects.json"
    policy_path.write_text('{"schemaVersion": 1, "projects": {}}\n')
    _git(root, "add", "--", "config/codm-projects.json")
    _git(root, "commit", "-qm", "policy")
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    # The reviewed policy, a pack and the README differ from HEAD in the
    # working tree when `stage` runs.
    policy_path.write_text('{"schemaVersion": 1, "projects": {"x": {}}}\n')
    (root / "dist/single-screen.json").write_text('{"apps": [1]}\n')
    (root / "README.md").write_text("changed guide\n")

    outcome = run_stage(
        root, base, "run", tmp_path / "candidate.bundle", tmp_path / "pr-body.md"
    )

    assert outcome.status == "changed"
    assert outcome.sha is not None
    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", outcome.sha)
        == CATALOG_PATH
    )
    assert _git(root, "diff", "--cached", "--name-only") == ""
    assert _git(root, "diff", "--name-only").splitlines() == [
        "README.md",
        "config/codm-projects.json",
        "dist/single-screen.json",
    ]


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
    assert outcome.stage == "files"
    assert outcome.summary == (
        f"stage failed: {CANDIDATE_DIR}/catalog.json is a symlink"
    )
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
    assert outcome.stage == "files"
    assert outcome.summary == f"stage failed: {CATALOG_PATH} is a symlink"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()
    assert not body_path.exists()


def test_missing_generated_candidate_fails_naming_it(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": [1]}\n', _report())
    (root / CANDIDATE_DIR / "catalog.json").unlink()
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_stage(root, base, "run", bundle_path, tmp_path / "pr-body.md")

    assert outcome.status == "failed"
    assert outcome.summary == f"stage failed: {CANDIDATE_DIR}/catalog.json is missing"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


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
    sha = _git(root, "rev-parse", "HEAD")
    assert sha != base
    assert output_path.read_text() == f"changed=true\nsha={sha}\nbase={base}\n"
    assert (runner_temp / "source-handoff" / "candidate.bundle").exists()
    assert (runner_temp / "source-handoff" / "pr-body.md").exists()
    assert (
        "https://github.example/mjkoo/omnipack/actions/runs/42"
        in (runner_temp / "source-handoff" / "pr-body.md").read_text()
    )


def test_report_whose_status_is_not_success_fails_with_no_commit(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    report = _report(added=("https://example.test/a",))
    report["status"] = "failed"
    _write_candidate(root, '{"apps": [{"id": "a"}]}\n', report)
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(root, base, "run", bundle_path, body_path)

    assert outcome.status == "failed"
    assert outcome.stage == "report"
    assert outcome.summary == "stage failed: generation did not succeed"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()
    assert not body_path.exists()


def test_stage_caps_a_huge_retained_failure_list_inside_the_pre_block(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    failures = tuple(
        (f"https://example.test/project-{index}", "x" * 200) for index in range(1000)
    )
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(retained_failures=failures)
    )
    body_path = tmp_path / "pr-body.md"

    outcome = run_stage(
        root, base, "https://github.example/runs/1", tmp_path / "b.bundle", body_path
    )

    assert outcome.status == "changed"
    body_text = body_path.read_text()
    assert len(body_text) <= 65536
    pre_block = body_text[body_text.index("<pre>") : body_text.index("</pre>")]
    assert "https://example.test/project-0: " in pre_block
    kept = pre_block.count("https://example.test/project-")
    assert 0 < kept < 1000
    assert f"and {1000 - kept} more" in pre_block
    assert body_text.endswith("</pre>\n")


def _stage_environment(
    monkeypatch: pytest.MonkeyPatch, root: Path, tmp_path: Path, base: str
) -> Path:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_SHA", base)
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    return runner_temp


def test_stage_cli_writes_changed_false_for_an_unchanged_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(root, '{"apps": []}\n', _report())
    runner_temp = _stage_environment(monkeypatch, root, tmp_path, base)

    exit_code = proposal_module.main(["stage"])

    assert exit_code == 0
    assert (tmp_path / "output.txt").read_text() == (
        f"changed=false\nsha={base}\nbase={base}\n"
    )
    assert not (runner_temp / "source-handoff").exists()


@pytest.mark.parametrize("missing", ["RUNNER_TEMP", "GITHUB_RUN_ID"])
def test_stage_cli_without_a_required_variable_exits_before_any_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _write_candidate(
        root, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    runner_temp = _stage_environment(monkeypatch, root, tmp_path, base)
    monkeypatch.delenv(missing)

    with pytest.raises(SystemExit, match=f"^{missing} is required$"):
        proposal_module.main(["stage"])

    assert _git(root, "rev-parse", "HEAD") == base
    assert not (runner_temp / "source-handoff").exists()
    assert not (tmp_path / "output.txt").exists()


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
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(7)])

    result = run_publish(write_side, "false", base, base, None, None, gh=gh)

    assert result.status == "closed"
    assert result.summary == "publish closed PR #7"
    close_calls = [call for call in gh.calls if call[:2] == ("pr", "close")]
    assert close_calls == [("pr", "close", "7", "--repo", "mjkoo/omnipack")]
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
    assert result.summary == "publish updated PR #3"
    edit_calls = [call for call in gh.calls if call[:2] == ("pr", "edit")]
    assert len(edit_calls) == 1
    assert edit_calls[0][:3] == ("pr", "edit", "3")
    assert gh.edited_bodies == [body_path.read_text()]
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


def test_hand_pushed_commit_with_a_different_tree_is_overwritten(
    tmp_path: Path,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)

    # Someone pushes a commit to the bot branch whose tree differs from the
    # rebuild; the next changed run replaces it.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.name", "Someone")
    _git(other, "config", "user.email", "someone@example.invalid")
    _git(other, "checkout", "-q", "-b", BRANCH_NAME, base)
    (other / CATALOG_PATH).write_text('{"apps": [{"id": "hand"}]}\n')
    _git(other, "commit", "-qam", "hand-made")
    hand_made_sha = _git(other, "rev-parse", "HEAD")
    _git(other, "push", "-q", "origin", f"HEAD:refs/heads/{BRANCH_NAME}")
    assert _bare_branch_sha(bare) == hand_made_sha

    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(4)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert _bare_branch_sha(bare) == sha


@pytest.mark.parametrize(
    ("cross_repo", "owner"),
    [(True, "someoneelse"), (True, "mjkoo"), (False, "someoneelse")],
)
def test_fork_pr_sharing_the_branch_name_is_untouched_and_own_pr_is_created(
    tmp_path: Path, cross_repo: bool, owner: str
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(11, cross_repo=cross_repo, owner=owner)])

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
    assert result.summary == "publish failed: more than one source-update PR"
    assert not any(
        call[:2] in (("pr", "close"), ("pr", "edit"), ("pr", "create"))
        for call in gh.calls
    )
    assert _bare_branch_sha(bare) == ""


@pytest.mark.parametrize(
    ("cross_repo", "owner"),
    [(True, "someoneelse"), (True, "mjkoo"), (False, "someoneelse")],
)
def test_fork_pr_sharing_the_branch_name_is_not_closed_when_unchanged(
    tmp_path: Path, cross_repo: bool, owner: str
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(11, cross_repo=cross_repo, owner=owner)])

    result = run_publish(write_side, "false", base, base, None, None, gh=gh)

    assert result.status == "unchanged"
    assert result.summary == "publish made no change"
    assert not any(
        call[:2] in (("pr", "close"), ("pr", "edit"), ("pr", "create"))
        for call in gh.calls
    )


def test_two_selected_same_repository_prs_fail_before_closing_either(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(1), _pr(2)])

    result = run_publish(write_side, "false", base, base, None, None, gh=gh)

    assert result.status == "failed"
    assert result.summary == "publish failed: more than one source-update PR"
    assert not any(call[:2] == ("pr", "close") for call in gh.calls)


def test_repository_hooks_never_run_when_publishing(tmp_path: Path) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    _install_failing_hooks(write_side, "pre-push", "reference-transaction")
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert _bare_branch_sha(bare) == sha


def _bot_catalog_commit(root: Path, catalog_text: str) -> str:
    (root / CATALOG_PATH).write_text(catalog_text)
    _git(root, "add", "--", CATALOG_PATH)
    _git(
        root,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(catalog): update reviewed codm source",
    )
    return _git(root, "rev-parse", "HEAD")


def test_bundle_with_wrong_parent_fails_before_any_push_or_pr_write(
    tmp_path: Path,
) -> None:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    # Two catalog commits on base, bundled from base: the bundle verifies
    # against the write side's base checkout and the diff names only the
    # catalog, so only the parent check can reject it.
    _git(seed, "checkout", "-q", "-b", BRANCH_NAME)
    _bot_catalog_commit(seed, '{"apps": [{"id": "intermediate"}]}\n')
    sha = _bot_catalog_commit(seed, '{"apps": [{"id": "a"}]}\n')
    bundle_path = tmp_path / "candidate.bundle"
    _git(seed, "bundle", "create", str(bundle_path), f"{base}..HEAD")
    body_path = tmp_path / "pr-body.md"
    body_path.write_text("body\n")
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert result.summary == "publish failed: hand-off rejected"
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
    assert result.summary == "publish failed: hand-off rejected"
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
    assert _bare_branch_sha(bare) == ""


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
    message = "[x](https://example.test) <b>app.apk</b> & ![i](https://e.test/i.png)"
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
    escaped = (
        "[x](https://example.test) &lt;b&gt;app.apk&lt;/b&gt; &amp; "
        "![i](https://e.test/i.png)"
    )
    assert f"https://example.test/proj: {escaped}" in _pre_block(body_text)
    assert message not in body_text


def test_rejected_branch_push_fails_with_its_reason_and_no_pr_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    pre_receive = bare / "hooks" / "pre-receive"
    pre_receive.write_text("#!/bin/sh\necho 'fixture rejects the branch' >&2\nexit 1\n")
    pre_receive.chmod(0o755)
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert result.summary == "publish failed: branch push failed"
    assert "fixture rejects the branch" in capsys.readouterr().err
    assert not any(call[:2] == ("pr", "create") for call in gh.calls)
    assert _bare_branch_sha(bare) == ""


def _replace_body(body_path: Path, kind: str) -> None:
    if kind == "missing":
        body_path.unlink()
    elif kind == "symlink":
        target = body_path.parent / "runner-file.txt"
        target.write_text("runner secrets\n")
        body_path.unlink()
        body_path.symlink_to(target)
    elif kind == "oversized":
        body_path.write_text("x" * 65537)
    elif kind == "not-utf-8":
        body_path.write_bytes(b"\xff\xfe body\n")
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["missing", "symlink", "oversized", "not-utf-8"])
def test_unusable_pr_body_fails_before_any_push_or_pr_write(
    tmp_path: Path, kind: str
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    _replace_body(body_path, kind)
    gh = ScriptedGh(pr_list=[_pr(5)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "failed"
    assert result.summary == "publish failed: PR body rejected"
    assert not any(call[:2] in (("pr", "edit"), ("pr", "create")) for call in gh.calls)
    assert _bare_branch_sha(bare) == ""


def test_pr_body_at_the_length_limit_is_accepted(tmp_path: Path) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    body_path.write_text("\u00e9" * 65536, encoding="utf-8")
    gh = ScriptedGh(pr_list=[])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"


@pytest.mark.parametrize(
    ("knob", "changed", "open_prs", "reason"),
    [
        ("auth_ok", "true", [], "publish failed: gh auth setup-git failed"),
        ("pr_list_ok", "true", [], "publish failed: PR list failed"),
        ("close_ok", "false", [6], "publish failed: PR close failed"),
        ("edit_ok", "true", [6], "publish failed: PR edit failed"),
        ("create_ok", "true", [], "publish failed: PR create failed"),
    ],
)
def test_failed_gh_operation_exits_nonzero_with_its_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    knob: str,
    changed: str,
    open_prs: list[int],
    reason: str,
) -> None:
    seed, base, sha, bundle_path, body_path = _staged_candidate(tmp_path)
    bare = _bare_from(seed, tmp_path)
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(number) for number in open_prs], **{knob: False})
    summary_path = tmp_path / "summary.md"
    monkeypatch.setattr(proposal_module, "SubprocessGhRunner", lambda: gh)
    monkeypatch.chdir(write_side)
    monkeypatch.setenv("CHANGED", changed)
    monkeypatch.setenv("CANDIDATE_SHA", sha if changed == "true" else base)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    exit_code = proposal_module.main(
        ["publish", "--bundle", str(bundle_path), "--body-file", str(body_path)]
    )

    assert exit_code == 1
    assert summary_path.read_text() == f"{reason}\n"


def _commit_with_tree(root: Path, tree: str, parent: str) -> str:
    return subprocess.run(
        ["git", "commit-tree", tree, "-p", parent, "-m", "hand-made"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Someone",
            "GIT_AUTHOR_EMAIL": "someone@example.invalid",
            "GIT_COMMITTER_NAME": "Someone",
            "GIT_COMMITTER_EMAIL": "someone@example.invalid",
        },
    ).stdout.strip()


def _tree_with_catalog_of(root: Path, tree_of: str, catalog_of: str) -> str:
    """`tree_of`'s tree with the catalog blob from `catalog_of`."""
    index = root.parent / f"{root.name}-scratch-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    blob = _git(root, "rev-parse", f"{catalog_of}:{CATALOG_PATH}")
    for args in (
        ["read-tree", tree_of],
        ["update-index", "--cacheinfo", f"100644,{blob},{CATALOG_PATH}"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, env=env)
    return subprocess.run(
        ["git", "write-tree"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


@pytest.mark.parametrize("same_tree", [True, False])
def test_bot_branch_built_on_an_older_main_is_compared_from_a_shallow_checkout(
    tmp_path: Path, same_tree: bool
) -> None:
    seed = _repo(tmp_path)
    older_main = _git(seed, "rev-parse", "HEAD")
    (seed / "README.md").write_text("newer guide\n")
    _git(seed, "commit", "-qam", "advance main")
    base = _git(seed, "rev-parse", "HEAD")
    _write_candidate(
        seed, '{"apps": [{"id": "a"}]}\n', _report(added=("https://example.test/a",))
    )
    bundle_path = tmp_path / "candidate.bundle"
    body_path = tmp_path / "pr-body.md"
    outcome = run_stage(
        seed, base, "https://github.example/runs/1", bundle_path, body_path
    )
    sha = outcome.sha
    assert sha is not None
    # The existing bot branch was built on the older main, outside the write
    # side's depth-1 history of the newer one.
    tree = (
        _git(seed, "rev-parse", f"{sha}^{{tree}}")
        if same_tree
        else _tree_with_catalog_of(seed, older_main, sha)
    )
    existing = _commit_with_tree(seed, tree, older_main)
    bare = _bare_from(seed, tmp_path)
    _git(seed, "push", "-q", str(bare), f"{existing}:refs/heads/{BRANCH_NAME}")
    write_side = _write_side(tmp_path, bare, base)
    gh = ScriptedGh(pr_list=[_pr(8)])

    result = run_publish(write_side, "true", sha, base, bundle_path, body_path, gh=gh)

    assert result.status == "published"
    assert _bare_branch_sha(bare) == (existing if same_tree else sha)
    assert _git(write_side, "rev-parse", "--is-shallow-repository") == "true"
