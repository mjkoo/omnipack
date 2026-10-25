"""CI check that a pull request leaves the nightly's generated output alone.

The nightly publisher is the only writer of the packs and of the README
catalog section. A pull request carries sources only, so two open pull
requests never conflict over a rebuilt pack.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from omnipack.catalog import CatalogError, split_catalog
from scripts.nightly_write import PACK_PATHS
from scripts.workflow_support import git_output

README = "README.md"
REMEDY = "drop it from the pull request; the nightly rebuild publishes it"


def generated_changes(root: Path, base: str, head: str) -> list[str]:
    """Describe each generated file that differs between `base` and `head`."""
    problems = [
        f"{relative} changed: {REMEDY}"
        for relative in PACK_PATHS
        if _tree_entry(root, base, relative) != _tree_entry(root, head, relative)
    ]
    try:
        _, base_catalog, _ = split_catalog(git_output(root, "show", f"{base}:{README}"))
        _, head_catalog, _ = split_catalog(git_output(root, "show", f"{head}:{README}"))
    except CatalogError as error:
        problems.append(f"{README}: {error}")
    else:
        if base_catalog != head_catalog:
            problems.append(f"{README} catalog section changed: {REMEDY}")
    return problems


def _tree_entry(root: Path, revision: str, relative: str) -> bytes:
    # The tree entry carries the blob id, so equal entries mean equal bytes,
    # and a deleted file yields an empty entry.
    return git_output(root, "ls-tree", "-z", revision, "--", relative)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    # A pull_request checkout is the merge commit, whose first parent is the
    # base branch tip, so the defaults judge the pull request's net change.
    parser.add_argument("--base", default="HEAD^1")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)
    problems = generated_changes(Path.cwd(), args.base, args.head)
    for problem in problems:
        print(f"::error::{problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
