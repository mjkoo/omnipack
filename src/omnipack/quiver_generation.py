"""Transactional fresh Quiver generation with conservative accepted-entry retention."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from omnipack.http import HttpError
from omnipack.package_id import NoEligibleApk
from omnipack.quiver_catalog import load_quiver_catalog, render_quiver_entry
from omnipack.quiver_source import (
    QuiverLookupFailure,
    QuiverRule,
    discover_quiver,
    discovery_name,
    load_quiver_config,
    parse_quiver_policy,
    resolve_quiver_apk,
)
from omnipack.report_model import Status
from omnipack.source_catalog import render_catalog, validate_ids
from omnipack.source_http import GenerationHttp, HttpConfig, SourceHttpClient
from omnipack.source_release import NoRelease, lookup_release
from omnipack.urls import normalize_project_url


class QuiverReport(TypedDict):
    """The generation report written beside every Quiver candidate."""

    status: Status
    source: Literal["quiver"]
    apk: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    unsupportedRows: list[dict[str, Any]]
    noAndroid: list[dict[str, Any]]
    unavailableRepositories: list[dict[str, Any]]
    retainedFailures: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    effectivePolicy: dict[str, dict[str, Any]]
    filteredAssets: list[dict[str, Any]]
    inputs: NotRequired[dict[str, Any]]
    coverage: NotRequired[list[dict[str, Any]]]
    filterDisagreements: NotRequired[list[str]]
    changes: NotRequired[dict[str, list[str]]]
    error: NotRequired[str]


def _accepted_match(accepted: dict[str, dict[str, Any]], urls: set[str]) -> str | None:
    """Return the normalized URL of the one accepted entry a project matches."""
    matches = [url for url in accepted if url in urls]
    if len(matches) > 1:
        raise ValueError(
            f"multiple accepted entries match canonical project: {sorted(urls)}"
        )
    return matches[0] if matches else None


def _retain(accepted: dict[str, Any], name: str, rule: QuiverRule) -> bool:
    return render_quiver_entry(accepted["url"], name, rule, accepted["id"]) == accepted


def generate_quiver(root: Path, *, http: GenerationHttp | None = None) -> QuiverReport:
    """Emit a complete candidate and report, never modifying accepted inputs."""
    output = root / ".build/source-generation/quiver"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    report: QuiverReport = {
        "status": Status.FAILED,
        "source": "quiver",
        "apk": [],
        "skipped": [],
        "unsupportedRows": [],
        "noAndroid": [],
        "unavailableRepositories": [],
        "retainedFailures": [],
        "unresolved": [],
        "effectivePolicy": {},
        "filteredAssets": [],
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
            {"url": p.key, "rows": [asdict(r) for r in p.rows]}
            for p in discovery.projects
        ]
        report["unsupportedRows"] = [asdict(r) for r in discovery.unsupported]
        report["filterDisagreements"] = list(discovery.filter_disagreements)
        entries: list[dict[str, Any]] = []
        # Accepted entries kept by a skip or a retained lookup failure, keyed by
        # normalized URL, with the report detail that explains the retention. A
        # project matching one of them was already decided and is not resolved.
        retained: dict[str, dict[str, Any]] = {}
        for row, reason in discovery.skipped:
            existing = accepted.get(row.listed or "")
            detail = {
                "row": asdict(row),
                "reason": reason,
                "retained": existing is not None,
            }
            report["skipped"].append(detail)
            if existing is not None and row.listed not in retained:
                entries.append(existing)
                retained[row.listed or ""] = detail
        for unavailable in discovery.unavailable:
            report["unavailableRepositories"].append(
                {
                    "url": unavailable.url,
                    "message": str(unavailable.error),
                    "status": unavailable.error.status,
                    "rows": [asdict(row) for row in unavailable.rows],
                }
            )
        # Duplicate failed rows still describe one listed project. Pick the same
        # deterministic discovery name that successful canonical grouping uses.
        failures: dict[str, list[QuiverLookupFailure]] = {}
        for failure in discovery.lookup_failures:
            failures.setdefault(failure.row.listed or "", []).append(failure)
        for listed, items in sorted(failures.items()):
            failure = items[0]
            name = discovery_name((x.row for x in items), listed.rsplit("/", 1)[-1])
            existing = accepted.get(listed)
            report["effectivePolicy"][listed] = failure.rule.canonical()
            detail = {
                "url": listed,
                "message": str(failure.error),
                "rows": [asdict(x.row) for x in items],
            }
            if existing is not None and _retain(existing, name, failure.rule):
                entries.append(existing)
                report["retainedFailures"].append(detail)
                retained[listed] = detail
            else:
                report["unresolved"].append(detail)
        for project in discovery.projects:
            urls = {project.key, *(r.listed for r in project.rows if r.listed)}
            matched = _accepted_match(accepted, urls)
            existing = accepted.get(matched or "")
            report["effectivePolicy"][project.key] = project.rule.canonical()
            if matched in retained:
                retained[matched].setdefault("matchedProjects", []).append(
                    {"url": project.key, "rows": [asdict(r) for r in project.rows]}
                )
                continue
            try:
                release = lookup_release(client, project.key, project.rule.project)
                identifier = resolve_quiver_apk(
                    client, release, project.rule, report["filteredAssets"], project.key
                )
                entry = render_quiver_entry(
                    project.url, project.name, project.rule, identifier
                )
                entries.append(entry)
                report["apk"].append(
                    {
                        "url": project.key,
                        "packageId": identifier,
                        "releaseId": release["id"],
                    }
                )
            except (HttpError, ValueError, TypeError, KeyError) as error:
                detail = {"url": project.key, "message": str(error)}
                if existing is not None and _retain(
                    existing, project.name, project.rule
                ):
                    entries.append(existing)
                    report["retainedFailures"].append(detail)
                elif existing is None and isinstance(error, (NoEligibleApk, NoRelease)):
                    report["noAndroid"].append(detail)
                else:
                    report["unresolved"].append(detail)
        validate_ids(entries)
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
            data = render_catalog(entries)
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
