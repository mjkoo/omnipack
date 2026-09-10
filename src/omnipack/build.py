"""Render and publish import files and their README catalog as a recoverable unit."""

from __future__ import annotations

import json
import tempfile
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
    """Render both variants and their catalog, gate them, and publish together."""
    readme_path = root / "README.md"
    try:
        readme_before = readme_path.read_bytes()
    except OSError:
        readme_before = None
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
    consumed_policy = (
        composition_bytes if composition_bytes is not None else snapshots[3]
    )
    result = validate_offline(
        OfflineInputs(
            rendered[Variant.SINGLE],
            rendered[Variant.DUAL],
            snapshots[0],
            snapshots[1],
            snapshots[2],
            (root / "config/settings.json").read_bytes(),
            consumed_policy,
        )
    )
    findings = [
        {key: value for key, value in asdict(item).items() if value is not None}
        for item in result.findings
    ]
    from omnipack.catalog import generate_catalog, replace_catalog
    from omnipack.composition_policy import load_composition_policy

    readme_rendered = None
    if not findings:
        try:
            if readme_before is None:
                raise ValueError("README input is missing or unreadable")
            catalog = generate_catalog(
                rendered[Variant.SINGLE],
                rendered[Variant.DUAL],
                load_composition_policy(consumed_policy),
            )
            readme_rendered = replace_catalog(readme_before, catalog)
        except ValueError as error:
            findings.append(
                {"stage": "catalog", "code": "catalog_invalid", "message": str(error)}
            )
    verdict = {"status": "failed" if findings else "success", "findings": findings}
    if on_verification is not None:
        on_verification(verdict)
    if findings:
        raise OfflineVerificationError(findings)

    def require_current_inputs() -> None:
        changed = []
        for path, snapshot, label in (
            (root / "config/composition.json", consumed_policy, "composition policy"),
            (readme_path, readme_before, "README"),
        ):
            try:
                current = path.read_bytes()
            except OSError:
                current = None
            if current != snapshot:
                changed.append(
                    {
                        "stage": "input",
                        "code": "input_changed",
                        "message": f"{label} changed during the build",
                    }
                )
        if changed:
            if on_verification is not None:
                on_verification({"status": "failed", "findings": changed})
            raise OfflineVerificationError(changed)

    require_current_inputs()

    if on_stage is not None:
        on_stage("report writing")
    write_report(
        root,
        before,
        composition,
        ingestion,
        offline_verification=verdict,
        policy=load_composition_policy(consumed_policy),
    )
    if on_stage is not None:
        on_stage("publication")
    require_current_inputs()
    assert readme_rendered is not None
    _replace_outputs(
        {
            **{
                root / "dist" / OUTPUTS[variant]: value
                for variant, value in rendered.items()
            },
            readme_path: readme_rendered,
        },
        before_replace=require_current_inputs,
    )


def _replace_outputs(
    rendered: dict[Path, bytes], *, before_replace: Callable[[], None] | None = None
) -> None:
    """Recover prior bytes or absence on handled staging/replacement failures."""
    snapshots = {
        path: path.read_bytes() if path.exists() else None for path in rendered
    }
    temporary: list[Path] = []
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []

    def stage(path: Path, content: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as handle:
            temp = Path(handle.name)
        temporary.append(temp)
        temp.write_bytes(content)
        return temp

    try:
        for path, content in rendered.items():
            staged[path] = stage(path, content)
        if before_replace is not None:
            before_replace()
        for path, temp in staged.items():
            temp.replace(path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            snapshot = snapshots[path]
            if snapshot is None:
                path.unlink(missing_ok=True)
            else:
                stage(path, snapshot).replace(path)
        raise
    finally:
        for temp in temporary:
            temp.unlink(missing_ok=True)
