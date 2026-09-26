"""Transactional fresh Quiver generation with conservative accepted-entry retention."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from omnipack.http import HttpError
from omnipack.quiver_catalog import load_quiver_catalog, render_quiver_entry
from omnipack.quiver_source import (
    NoApk,
    NoRelease,
    QuiverRule,
    RepositoryUnavailable,
    discover_quiver,
    load_quiver_config,
    lookup_quiver_release,
    parse_quiver_policy,
    resolve_quiver_apk,
)
from omnipack.report_model import Status
from omnipack.source_catalog import _render_catalog, _validate_ids
from omnipack.source_http import GenerationHttp, HttpConfig, SourceHttpClient
from omnipack.urls import normalize_project_url


def _accepted_match(
    accepted: dict[str, dict[str, Any]], urls: set[str]
) -> dict[str, Any] | None:
    matches = [entry for url, entry in accepted.items() if url in urls]
    if len(matches) > 1:
        raise ValueError(
            f"multiple accepted entries match canonical project: {sorted(urls)}"
        )
    return matches[0] if matches else None


def _retain(accepted: dict[str, Any] | None, name: str, rule: QuiverRule) -> bool:
    return (
        accepted is not None
        and render_quiver_entry(accepted["url"], name, rule, accepted["id"]) == accepted
    )


def generate_quiver(
    root: Path, *, http: GenerationHttp | None = None
) -> dict[str, Any]:
    """Emit a complete candidate and report, never modifying accepted inputs."""
    output = root / ".build/source-generation/quiver"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    report: dict[str, Any] = {
        "status": Status.FAILED,
        "source": "quiver",
        "apk": [],
        "tracking": [],
        "skipped": [],
        "unsupportedRows": [],
        "noAndroid": [],
        "unavailableRepositories": [],
        "retainedFailures": [],
        "unresolved": [],
        "effectivePolicy": {},
    }
    try:
        sources = json.loads((root / "config/sources.json").read_bytes())
        config = load_quiver_config(
            sources.get("quiver") if isinstance(sources, dict) else None
        )
        policy = parse_quiver_policy((root / config.project_policy).read_bytes())
        accepted = {
            normalize_project_url(e["url"]): e
            for e in load_quiver_catalog(root / config.catalog)
        }
        client = http or SourceHttpClient(
            HttpConfig.from_path(root / "config/http.json")
        )
        discovery = discover_quiver(config.index_url, policy, client)
        report["inputs"] = {
            "indexUrl": config.index_url,
            "listIds": list(discovery.list_ids),
        }
        report["coverage"] = [
            {"url": p.canonical, "rows": [asdict(r) for r in p.rows]}
            for p in discovery.projects
        ]
        report["unsupportedRows"] = [asdict(r) for r in discovery.unsupported]
        report["filterDisagreements"] = list(discovery.filter_disagreements)
        report["platformMetadata"] = discovery.metadata_diagnostic
        entries: list[dict[str, Any]] = []
        retained_urls: set[str] = set()
        for row, reason in discovery.skipped:
            existing = accepted.get(row.listed or "")
            report["skipped"].append(
                {"row": asdict(row), "reason": reason, "retained": existing is not None}
            )
            if existing is not None and row.listed not in retained_urls:
                entries.append(existing)
                retained_urls.add(row.listed or "")
        # Duplicate failed rows still describe one listed project. Pick the same
        # deterministic discovery name that successful canonical grouping uses.
        failures: dict[str, list[Any]] = {}
        for failure in discovery.lookup_failures:
            failures.setdefault(failure.row.listed or "", []).append(failure)
        for listed, items in sorted(failures.items()):
            failure = items[0]
            names = sorted(
                {x.row.project_name for x in items if x.row.project_name},
                key=lambda s: (s.casefold(), s),
            )
            name = names[0] if names else listed.rsplit("/", 1)[-1]
            existing = accepted.get(listed)
            report["effectivePolicy"][listed] = asdict(failure.rule)
            detail = {
                "url": listed,
                "message": str(failure.error),
                "rows": [asdict(x.row) for x in items],
            }
            if _retain(existing, name, failure.rule):
                assert existing is not None
                entries.append(existing)
                report["retainedFailures"].append(detail)
            else:
                report["unresolved"].append(detail)
        for project in discovery.projects:
            urls = {project.canonical, *(r.listed for r in project.rows if r.listed)}
            existing = _accepted_match(accepted, urls)
            report["effectivePolicy"][project.canonical] = asdict(project.rule)
            try:
                canonical, release = lookup_quiver_release(
                    client, project.canonical, project.rule
                )
                identifier = resolve_quiver_apk(
                    client, release, project.rule, report, canonical
                )
                entry = render_quiver_entry(
                    "https://" + canonical, project.name, project.rule, identifier
                )
                entries.append(entry)
                report["apk"].append(
                    {
                        "url": canonical,
                        "packageId": identifier,
                        "releaseId": release["id"],
                        "status": "resolved",
                    }
                )
            except RepositoryUnavailable as error:
                report["unavailableRepositories"].append(
                    {
                        "url": project.canonical,
                        "message": str(error),
                        "status": error.status,
                    }
                )
            except (HttpError, ValueError, TypeError, KeyError) as error:
                detail = {"url": project.canonical, "message": str(error)}
                if _retain(existing, project.name, project.rule):
                    assert existing is not None
                    entries.append(existing)
                    report["retainedFailures"].append(detail)
                elif existing is None and isinstance(error, (NoApk, NoRelease)):
                    report["noAndroid"].append(detail)
                else:
                    report["unresolved"].append(detail)
        _validate_ids(entries)
        by_url = {normalize_project_url(e["url"]): e for e in entries}
        if len(by_url) != len(entries):
            raise ValueError("duplicate normalized project URLs in candidate")
        if not report["unresolved"]:
            report["changes"] = {
                "added": sorted(by_url.keys() - accepted.keys()),
                "removed": sorted(accepted.keys() - by_url.keys()),
                "changed": sorted(
                    url
                    for url in by_url.keys() & accepted.keys()
                    if by_url[url] != accepted[url]
                ),
            }
            data = _render_catalog(entries)
            (output / "catalog.json").write_bytes(data)
            report["status"] = Status.SUCCESS
    except Exception as error:  # noqa: BLE001 - persist actionable command failure
        report["error"] = str(error)
    if report["status"] != Status.SUCCESS:
        (output / "catalog.json").unlink(missing_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    return report
