"""Render and publish the two import files as one recoverable pair."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from omnipack.merge import CompositionResult
from omnipack.model import Variant
from omnipack.render import render
from omnipack.sources import IngestionReport

OUTPUTS = {
    Variant.SINGLE: "single-screen.json",
    Variant.DUAL: "dual-screen.json",
}


class OfflineVerificationError(ValueError):
    """Newly rendered output failed the pure publication gate."""

    def __init__(self, findings: list[dict[str, Any]]) -> None:
        super().__init__(f"offline verification failed with {len(findings)} finding(s)")
        self.findings = findings


def previous_ids(root: Path) -> dict[Variant, list[dict[str, str]]]:
    """Read rendered identities from the output pair before publication begins."""
    result: dict[Variant, list[dict[str, str]]] = {}
    for variant, name in OUTPUTS.items():
        path = root / "dist" / name
        if not path.exists():
            result[variant] = []
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            result[variant] = []
            continue
        apps = document.get("apps", []) if isinstance(document, dict) else []
        result[variant] = [
            {"id": item["id"], "url": item.get("url", "")}
            for item in apps
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
    return result


def publish_build(
    root: Path,
    composition: CompositionResult,
    settings: dict[str, Any],
    ingestion: IngestionReport,
    composition_bytes: bytes | None = None,
    *,
    on_stage: Callable[[str], None] | None = None,
    on_verification: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Render both variants, write their report, and publish them together."""
    if on_stage is not None:
        on_stage("rendering")
    before = previous_ids(root)
    rendered = {
        variant: render(composition.apps[variant], settings).encode()
        for variant in Variant
    }
    from omnipack.offline import OfflineInputs, validate_offline
    from omnipack.report import write_report

    if on_stage is not None:
        on_stage("offline verification")
    config_paths = (
        "config/deny.json",
        "config/overlay.json",
        "config/overlay.dual.json",
        "config/composition.json",
    )
    snapshots = [(root / path).read_bytes() for path in config_paths]
    result = validate_offline(
        OfflineInputs(
            rendered[Variant.SINGLE],
            rendered[Variant.DUAL],
            snapshots[0],
            snapshots[1],
            snapshots[2],
            (root / "config/settings.json").read_bytes(),
            composition_bytes if composition_bytes is not None else snapshots[3],
        )
    )
    findings = [
        {key: value for key, value in asdict(item).items() if value is not None}
        for item in result.findings
    ]
    verdict = {"status": "failed" if findings else "success", "findings": findings}
    if on_verification is not None:
        on_verification(verdict)
    if findings:
        raise OfflineVerificationError(findings)

    def require_current_policy() -> None:
        if (
            composition_bytes is None
            or (root / "config/composition.json").read_bytes() == composition_bytes
        ):
            return
        changed = [
            {
                "stage": "input",
                "code": "input_changed",
                "message": "composition policy changed during the build",
            }
        ]
        if on_verification is not None:
            on_verification({"status": "failed", "findings": changed})
        raise OfflineVerificationError(changed)

    require_current_policy()

    if on_stage is not None:
        on_stage("report writing")
    from omnipack.composition_policy import load_composition_policy

    write_report(
        root,
        before,
        composition,
        ingestion,
        offline_verification=verdict,
        policy=load_composition_policy(
            composition_bytes if composition_bytes is not None else snapshots[3]
        ),
    )
    if on_stage is not None:
        on_stage("publication")
    require_current_policy()
    _replace_pair(root / "dist", rendered)


def _replace_pair(dist: Path, rendered: dict[Variant, bytes]) -> None:
    paths = {variant: dist / name for variant, name in OUTPUTS.items()}
    snapshots = {
        variant: path.read_bytes() if path.exists() else None
        for variant, path in paths.items()
    }
    dist.mkdir(parents=True, exist_ok=True)
    temporary: dict[Variant, Path] = {}
    for variant, path in paths.items():
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(rendered[variant])
        temporary[variant] = temp
    replaced: list[Variant] = []
    try:
        for variant in Variant:
            temporary[variant].replace(paths[variant])
            replaced.append(variant)
    except Exception:
        for variant in replaced:
            snapshot = snapshots[variant]
            if snapshot is None:
                paths[variant].unlink(missing_ok=True)
            else:
                backup = paths[variant].with_suffix(paths[variant].suffix + ".rollback")
                backup.write_bytes(snapshot)
                backup.replace(paths[variant])
        raise
    finally:
        for path in temporary.values():
            path.unlink(missing_ok=True)
