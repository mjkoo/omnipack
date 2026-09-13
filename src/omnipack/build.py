"""Render and publish import files and their README catalog as a recoverable unit."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from stat import S_IMODE
from typing import Any
from uuid import uuid4

from omnipack.composition_policy import CompositionPolicy, load_composition_policy
from omnipack.merge import CompositionResult
from omnipack.model import Variant
from omnipack.render import render
from omnipack.sources import IngestionReport, SourceError

OUTPUTS = {
    Variant.SINGLE: "single-screen.json",
    Variant.DUAL: "dual-screen.json",
}


class OfflineVerificationError(ValueError):
    """Newly rendered output failed the pure publication gate."""

    def __init__(self, findings: list[dict[str, Any]]) -> None:
        super().__init__(f"offline verification failed with {len(findings)} finding(s)")
        self.findings = findings


@dataclass(frozen=True, slots=True)
class BuildInputs:
    """The five configuration files and the optional README, captured once
    when a build starts, with the composition policy parsed from its bytes.

    Composition, the offline gate and catalog generation all use these bytes,
    so a file edited while the build runs is overwritten by, or missing from,
    that build's outputs instead of being read part way through. Other
    on-disk inputs, such as the committed codm catalog, are read separately
    during ingestion.
    """

    sources: bytes
    extras: bytes
    deny: bytes
    overlay: bytes
    composition: bytes
    policy: CompositionPolicy
    readme: bytes | None

    @classmethod
    def read(cls, root: Path) -> BuildInputs:
        def required(relative: str, source: str) -> bytes:
            try:
                return (root / relative).read_bytes()
            except OSError as error:
                raise SourceError(source, str(error)) from error

        try:
            readme = (root / "README.md").read_bytes()
        except OSError:
            readme = None
        sources = required("config/sources.json", "sources")
        extras = required("config/extras.json", "extras")
        deny = required("config/deny.json", "denylist")
        overlay = required("config/overlay.json", "overlay")
        composition = required("config/composition.json", "composition policy")
        return cls(
            sources=sources,
            extras=extras,
            deny=deny,
            overlay=overlay,
            composition=composition,
            policy=load_composition_policy(composition),
            readme=readme,
        )


def previous_ids(root: Path) -> dict[Variant, set[str]]:
    """Read rendered package ids from the output pair before publication begins."""
    result: dict[Variant, set[str]] = {}
    for variant, name in OUTPUTS.items():
        path = root / "dist" / name
        if not path.exists():
            result[variant] = set()
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            result[variant] = set()
            continue
        apps = document.get("apps", []) if isinstance(document, dict) else []
        result[variant] = {
            item["id"]
            for item in apps
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
    return result


def publish_build(
    root: Path,
    composition: CompositionResult,
    ingestion: IngestionReport,
    inputs: BuildInputs,
    *,
    on_stage: Callable[[str], None] | None = None,
    on_verification: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Render both variants and their catalog, gate them, and publish together."""
    if on_stage is not None:
        on_stage("rendering")
    before = previous_ids(root)
    rendered = {
        variant: render(composition.apps[variant]).encode() for variant in Variant
    }
    from omnipack.offline import OfflineInputs, validate_offline
    from omnipack.report import write_report

    if on_stage is not None:
        on_stage("offline verification")
    offline_findings = validate_offline(
        OfflineInputs(
            rendered[Variant.SINGLE],
            rendered[Variant.DUAL],
            inputs.deny,
            inputs.overlay,
            inputs.composition,
        )
    )
    findings = [
        {key: value for key, value in asdict(item).items() if value is not None}
        for item in offline_findings
    ]
    from omnipack.catalog import generate_catalog, replace_catalog

    readme_rendered = None
    if not findings:
        try:
            if inputs.readme is None:
                raise ValueError("README input is missing or unreadable")
            catalog = generate_catalog(
                rendered[Variant.SINGLE], rendered[Variant.DUAL], inputs.policy
            )
            readme_rendered = replace_catalog(inputs.readme, catalog)
        except ValueError as error:
            findings.append(
                {"stage": "catalog", "code": "catalog_invalid", "message": str(error)}
            )
    verdict = {"status": "failed" if findings else "success", "findings": findings}
    if on_verification is not None:
        on_verification(verdict)
    if findings:
        raise OfflineVerificationError(findings)

    if on_stage is not None:
        on_stage("report writing")
    write_report(
        root,
        before,
        composition,
        ingestion,
        offline_verification=verdict,
    )
    if on_stage is not None:
        on_stage("publication")
    assert readme_rendered is not None
    _replace_outputs(
        {
            **{
                root / "dist" / OUTPUTS[variant]: value
                for variant, value in rendered.items()
            },
            root / "README.md": readme_rendered,
        }
    )


def _replace_outputs(rendered: dict[Path, bytes]) -> None:
    """Preserve modes and recover prior bytes or absence on handled failures."""
    snapshots = {
        path: path.read_bytes() if path.exists() else None for path in rendered
    }
    modes = {
        path: S_IMODE(path.stat().st_mode)
        for path, snapshot in snapshots.items()
        if snapshot is not None
    }
    temporary: list[Path] = []
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []

    def stage(path: Path, content: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        # Exclusive creation respects the umask for outputs that do not yet exist.
        with temp.open("xb"):
            pass
        temporary.append(temp)
        temp.write_bytes(content)
        if path in modes:
            temp.chmod(modes[path])
        return temp

    try:
        for path, content in rendered.items():
            staged[path] = stage(path, content)
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
