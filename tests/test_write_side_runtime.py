"""Guard the write job's standard-library-only, `python3`-3.12-safe runtime."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

WRITE_SIDE_MODULES = (
    "scripts/nightly_write.py",
    "scripts/source_proposal.py",
    "scripts/workflow_support.py",
)


def _imported_names(tree: ast.Module, relative: str) -> set[str]:
    """Every dotted module name this file imports, at any depth.

    A relative import fails the check outright: the write job runs these
    modules as `python3 -m scripts.<name>`, and every import must name its
    module so the check below can follow it.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module, (
                f"{relative} uses a relative import; import scripts modules by name"
            )
            names.add(node.module)
            if node.module == "scripts":
                names.update(f"scripts.{alias.name}" for alias in node.names)
    return names


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
        ):
            return True
    return False


def test_write_side_modules_import_only_stdlib_and_scripts() -> None:
    seen: set[str] = set()
    pending = list(WRITE_SIDE_MODULES)
    root = Path(__file__).parent.parent
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        source = (root / relative).read_text()
        tree = ast.parse(source, filename=relative)
        assert _has_future_annotations(tree), (
            f"{relative} must start with `from __future__ import annotations`"
        )
        for name in _imported_names(tree, relative):
            top = name.split(".")[0]
            if top != "scripts":
                assert top in sys.stdlib_module_names, (
                    f"{relative} imports {name!r}, which is not the standard "
                    "library or the scripts package"
                )
                continue
            if name == "scripts":
                continue
            submodule = root / (name.replace(".", "/") + ".py")
            pending.append(str(submodule.relative_to(root)))
