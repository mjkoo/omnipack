"""Minimal serialized inputs and reports for verification tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SERIALIZED_INPUTS = {
    Path("dist/single-screen.json"): b'{"settings":{},"apps":[]}\n',
    Path("dist/dual-screen.json"): b'{"settings":{},"apps":[]}\n',
    Path("config/deny.json"): b"[]\n",
    Path("config/overlay.json"): b"[]\n",
    Path("config/composition.json"): (
        b'{"schemaVersion":1,"candidates":[],"pins":[]}\n'
    ),
    Path("README.md"): (
        b"Fixture guide\n"
        b"<!-- omnipack:catalog:start -->\n"
        b"<!-- omnipack:catalog:end -->\n"
    ),
}


def write_verification_inputs(root: Path) -> None:
    """Write one valid verifier input set without composing or rendering it."""
    for relative, value in _SERIALIZED_INPUTS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)


def verification_report(**fields: object) -> dict[str, Any]:
    """Return one valid serialized verification report with explicit defaults."""
    document: dict[str, Any] = {
        "schemaVersion": 4,
        "verifier": {"version": "fixture", "scope": "structural"},
        "mode": "offline",
        "startedAt": "2026-09-01T00:00:00+00:00",
        "completedAt": "2026-09-01T00:00:01+00:00",
        "status": "success",
        "inputs": {
            name: {"state": "missing"}
            for name in ("single", "dual", "deny", "overlay", "composition", "readme")
        },
        "errors": [],
    }
    document.update(fields)
    return document


def write_verification_report(root: Path, **fields: object) -> dict[str, Any]:
    """Write a valid serialized verification report with selected replacements."""
    document = verification_report(**fields)
    path = root / ".build/verify.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document))
    return document
