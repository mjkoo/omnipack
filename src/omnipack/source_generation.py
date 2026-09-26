"""Transactional README source catalog generation."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from omnipack.http import HttpError
from omnipack.package_id import resolve_release_assets
from omnipack.project_policy import (
    ProjectRule,
    default_apk_rule,
    parse_project_policy,
    repository_url,
)
from omnipack.report_model import Status
from omnipack.source_catalog import _render_catalog, _rendered_entry, _validate_ids
from omnipack.source_http import GenerationHttp, HttpConfig, SourceHttpClient
from omnipack.source_release import _release_id, select_release
from omnipack.sources import load_json
from omnipack.urls import normalize_project_url

LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")


@dataclass(frozen=True, slots=True)
class ParsedProjects:
    projects: tuple[str, ...]
    source_urls: dict[str, str]
    unsupported: tuple[str, ...]


def _outside_code(lines: list[str]) -> list[str]:
    """Keep line boundaries while hiding fenced and indented code examples."""
    visible: list[str] = []
    fence = ""
    for line in lines:
        expanded = line.expandtabs(4)
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*",
                expanded,
            ):
                fence = ""
            visible.append("")
        elif expanded.startswith("    "):
            visible.append("")
        elif match := re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", expanded):
            delimiter, info = match.groups()
            if delimiter[0] == "~" or "`" not in info:
                fence = delimiter
            visible.append("")
        else:
            visible.append(line)
    return visible


def parse_project_table(readme: bytes) -> ParsedProjects:
    try:
        lines = _outside_code(readme.decode("utf-8").splitlines())
    except UnicodeDecodeError as error:
        raise ValueError("README is not UTF-8") from error
    projects: dict[str, str] = {}
    unsupported: set[str] = set()
    found = False
    index = 0
    while index < len(lines):
        header = lines[index]
        if re.match(r"^\s*\|\s*Project\s*\|", header, re.IGNORECASE):
            separator = lines[index + 1] if index + 1 < len(lines) else ""
            if SEPARATOR_RE.fullmatch(separator) is None:
                raise ValueError(
                    "Project catalog table has a missing or invalid delimiter"
                )
            # Escaped pipes are cell content, including pipes in inline code.
            pipes = list(re.finditer(r"(?<!\\)(?:\\\\)*\|", header.rstrip()))
            columns = len(pipes) - (pipes[-1].end() == len(header.rstrip()))
            if columns != separator.count("|") - 1:
                raise ValueError(
                    "Project catalog table header/delimiter column mismatch"
                )
            found = True
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                for raw_url in LINK_RE.findall(lines[index]):
                    try:
                        normalized = repository_url(raw_url)
                    except ValueError:
                        unsupported.add(raw_url)
                        continue
                    if (
                        normalized.startswith("github.com/")
                        and len(normalized.split("/")) == 3
                    ):
                        projects[normalized] = min(
                            projects.get(normalized, raw_url), raw_url
                        )
                    else:
                        unsupported.add(raw_url)
                index += 1
            continue
        index += 1
    if not found:
        raise ValueError("README lacks a recognizable Project catalog table")
    if not projects:
        raise ValueError(
            "Project catalog tables contain no eligible GitHub repositories"
        )
    return ParsedProjects(tuple(sorted(projects)), projects, tuple(sorted(unsupported)))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def effective_settings(rule: ProjectRule) -> dict[str, Any]:
    settings = dict(rule.additional_settings)
    settings.setdefault("verifyLatestTag", False)
    settings.setdefault("sortMethodChoice", "date")
    if rule.kind == "apk":
        settings.setdefault("trackOnly", False)
    else:
        settings.update(
            trackOnly=True,
            versionDetection=False,
            includeZips=False,
            autoApkFilterByArch=False,
        )
        settings["about"] = (
            f"{rule.rationale} {rule.installation} Obtainium only tracks release notifications; acknowledgement does not install the resource or detect its installed version."
        )
    return settings


def _entry(source_url: str, rule: ProjectRule, identifier: str) -> dict[str, Any]:
    parsed = urlsplit(source_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValueError(f"project URL lacks owner and repository: {source_url}")
    owner, repository = parts
    repository = repository.removesuffix(".git")
    return {
        "id": identifier,
        "url": source_url,
        "author": owner,
        "name": rule.name or repository,
        "additionalSettings": json.dumps(
            effective_settings(rule), sort_keys=True, separators=(",", ":")
        ),
        "categories": [],
        "overrideSource": "GitHub",
    }


def generate_codm(root: Path, *, http: GenerationHttp | None = None) -> dict[str, Any]:
    output = root / ".build/source-generation/codm"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    report: dict[str, Any] = {
        "status": Status.FAILED,
        "apk": [],
        "tracking": [],
        "retainedFailures": [],
    }
    try:
        sources = load_json(root / "config/sources.json", "sources")
        config = sources.get("codm") if isinstance(sources, dict) else None
        if not isinstance(config, dict):
            raise TypeError("codm source configuration must be an object")
        source_url = config.get("readme_url")
        policy_path = config.get("project_policy", "config/codm-projects.json")
        catalog_path = config.get("catalog", "config/catalogs/codm.json")
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("codm README URL is empty")
        if not all(isinstance(value, str) for value in (policy_path, catalog_path)):
            raise ValueError("codm source paths must be strings")
        policy_bytes = (root / policy_path).read_bytes()
        policy = parse_project_policy(policy_bytes)
        client = http or SourceHttpClient(
            HttpConfig.from_path(root / "config/http.json")
        )
        readme = client.get(source_url).body
        parsed = parse_project_table(readme)
        report["inputs"] = {"sourceUrl": source_url, "readmeSha256": _sha(readme)}
        report["unsupportedLinks"] = list(parsed.unsupported)
        report["inactiveRules"] = sorted(set(policy.projects) - set(parsed.projects))
        accepted_by_url = {
            normalize_project_url(item["url"]): item
            for item in _load_catalog(root / catalog_path)
        }
        entries: list[dict[str, Any]] = []
        rendered_by_project: dict[str, dict[str, Any]] = {}
        failed = False
        for project in parsed.projects:
            rule = policy.projects.get(project, default_apk_rule())
            report.setdefault("effectivePolicy", {})[project] = rule.canonical()
            try:
                release = select_release(client, project, rule)
                release_id = _release_id(release)
                if rule.kind == "track-only":
                    assert rule.tracker_id is not None
                    entry = _entry(parsed.source_urls[project], rule, rule.tracker_id)
                    entries.append(entry)
                    rendered_by_project[project] = _rendered_entry(entry)
                    report["tracking"].append(
                        {"url": project, "id": rule.tracker_id, "status": "verified"}
                    )
                    continue
                package_id = resolve_release_assets(
                    client,
                    release,
                    rule.additional_settings.get("apkFilterRegEx", ""),
                    report,
                    project,
                )
                entry = _entry(parsed.source_urls[project], rule, package_id)
                entries.append(entry)
                rendered_by_project[project] = _rendered_entry(entry)
                report["apk"].append(
                    {
                        "url": project,
                        "packageId": package_id,
                        "releaseId": release_id,
                        "status": "resolved",
                    }
                )
            except (HttpError, ValueError, TypeError, KeyError) as error:
                accepted = accepted_by_url.get(project)
                if accepted is not None and _retained(rule, accepted):
                    entries.append(accepted)
                    rendered_by_project[project] = _rendered_entry(accepted)
                    report["retainedFailures"].append(
                        {"url": project, "message": str(error)}
                    )
                else:
                    failed = True
                    report.setdefault("unresolved", []).append(
                        {"url": project, "error": str(error), "kind": rule.kind}
                    )
        _validate_ids(entries)
        if failed:
            report["status"] = Status.FAILED
            _write_report(output, report)
            return report
        catalog_bytes = _render_catalog(entries)
        common = set(parsed.projects) & set(accepted_by_url)
        changes = {
            "added": sorted(set(parsed.projects) - set(accepted_by_url)),
            "removed": sorted(set(accepted_by_url) - set(parsed.projects)),
            "changed": sorted(
                project
                for project in common
                if rendered_by_project[project]
                != _rendered_entry(accepted_by_url[project])
            ),
        }
        (output / "catalog.json").write_bytes(catalog_bytes)
        report["changes"] = changes
        # Success is recorded last, so any exception above fails generation.
        report["status"] = Status.SUCCESS
        _write_report(output, report)
        return report
    except Exception as error:  # noqa: BLE001 - command records all failures
        report["status"] = Status.FAILED
        report["error"] = str(error)
        _write_report(output, report)
        return report


def _retained(rule: ProjectRule, accepted: dict[str, Any]) -> bool:
    """A failed project keeps its committed entry only when the current rule,
    rendered with the identity it is authoritative for, reproduces that entry
    exactly: the committed package ID for an APK rule, or the rule's own
    tracker ID for a track-only rule, both against the committed URL.
    """
    identity = rule.tracker_id if rule.kind == "track-only" else accepted.get("id")
    if not isinstance(identity, str):
        return False
    try:
        candidate = _entry(accepted["url"], rule, identity)
        return _rendered_entry(candidate) == _rendered_entry(accepted)
    except TypeError, ValueError, KeyError:
        return False


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    doc = load_json(path, "accepted codm catalog")
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("apps"), list)
        or not all(
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("url"), str)
            for item in doc["apps"]
        )
    ):
        raise ValueError("accepted codm catalog is malformed")
    seen_urls: set[str] = set()
    seen_ids: dict[str, str] = {}
    for item in doc["apps"]:
        normalized = normalize_project_url(item["url"])
        if normalized in seen_urls:
            raise ValueError(
                f"accepted codm catalog has duplicate project {normalized}"
            )
        seen_urls.add(normalized)
        prior = seen_ids.get(item["id"])
        if prior is not None:
            raise ValueError(
                f"accepted codm catalog ID collision {item['id']!r} between {prior} and {item['url']}"
            )
        seen_ids[item["id"]] = item["url"]
    return doc["apps"]


def _write_report(output: Path, report: dict[str, Any]) -> None:
    (output / "report.json").write_bytes(_canonical_json(report))
