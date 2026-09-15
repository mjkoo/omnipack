"""Check the publication scripts' standard-library-only import boundary."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


def test_write_side_modules_import_only_stdlib_and_scripts() -> None:
    root = Path(__file__).resolve().parents[1]
    pending = [
        "scripts.nightly_write",
        "scripts.source_proposal",
        "scripts.workflow_support",
    ]
    seen = set()
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        path = root / (module.replace(".", "/") + ".py")
        package = module.rpartition(".")[0]
        if not path.is_file():
            path = root / module.replace(".", "/") / "__init__.py"
            package = module
        tree = ast.parse(path.read_text(), filename=str(path))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ""
                if node.level:
                    name = importlib.util.resolve_name("." * node.level + name, package)
                names.add(name)
                if name == "scripts":
                    names.update("scripts." + alias.name for alias in node.names)
        for name in names:
            top = name.split(".")[0]
            assert top == "scripts" or top in sys.stdlib_module_names, (
                f"{module} imports {name}"
            )
            if top == "scripts":
                pending.extend(["scripts", name])
