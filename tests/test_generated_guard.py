"""Tests for the pull request check that keeps generated output out of PRs.

Each test commits a change on top of a base commit in a temporary repository
and judges the pair the way CI judges a pull request's merge commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generated_guard import REMEDY, generated_changes, main
from tests.publication_support import (
    README_BYTES,
    git,
    isolated_git_identity,
    repository,
)

pytestmark = pytest.mark.usefixtures(isolated_git_identity.__name__)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return repository(
        tmp_path,
        {
            "dist/single-screen.json": '{"apps": []}\n',
            "dist/dual-screen.json": '{"apps": []}\n',
            "README.md": README_BYTES,
            "config/extras.json": "[]\n",
        },
    )


def commit(root: Path, files: dict[str, str | bytes]) -> None:
    for relative, content in files.items():
        path = root / relative
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
    git(root, "add", *files)
    git(root, "commit", "-qm", "change")


def test_source_and_readme_prose_changes_pass(repo: Path) -> None:
    commit(
        repo,
        {
            "config/extras.json": '[{"id": "a"}]\n',
            "README.md": README_BYTES.replace(b"guide", b"new guide"),
        },
    )

    assert generated_changes(repo, "HEAD^1", "HEAD") == []


def test_pack_change_fails(repo: Path) -> None:
    commit(repo, {"dist/dual-screen.json": '{"apps": [1]}\n'})

    assert generated_changes(repo, "HEAD^1", "HEAD") == [
        f"dist/dual-screen.json changed: {REMEDY}"
    ]


def test_pack_deletion_fails(repo: Path) -> None:
    git(repo, "rm", "-q", "dist/single-screen.json")
    git(repo, "commit", "-qm", "delete")

    assert generated_changes(repo, "HEAD^1", "HEAD") == [
        f"dist/single-screen.json changed: {REMEDY}"
    ]


def test_readme_catalog_change_fails(repo: Path) -> None:
    commit(repo, {"README.md": README_BYTES.replace(b"base catalog", b"rebuilt")})

    assert generated_changes(repo, "HEAD^1", "HEAD") == [
        f"README.md catalog section changed: {REMEDY}"
    ]


def test_broken_readme_markers_fail(repo: Path) -> None:
    commit(repo, {"README.md": b"guide only\n"})

    [problem] = generated_changes(repo, "HEAD^1", "HEAD")
    assert problem.startswith("README.md: README must contain exactly one")


def test_main_reports_annotations_and_exit_status(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    commit(repo, {"config/extras.json": '[{"id": "a"}]\n'})

    assert main([]) == 0

    commit(repo, {"dist/single-screen.json": '{"apps": [1]}\n'})

    assert main([]) == 1
    assert capsys.readouterr().out.startswith(
        "::error::dist/single-screen.json changed"
    )
