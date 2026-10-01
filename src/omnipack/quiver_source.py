"""Quiver catalog discovery.

Discovery keeps list provenance and resolves GitHub renames, while candidate
rendering and accepted-entry retention belong to the generation command.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from omnipack.http import HttpError, HttpStatusError
from omnipack.package_id import resolve_release_assets
from omnipack.project_policy import (
    PolicyError,
    ProjectRule,
    default_apk_rule,
    parse_project_policy,
    repository_url,
)
from omnipack.source_http import GenerationHttp

MAX_CATALOG_BYTES = 2_000_000
_PAIR = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


@dataclass(frozen=True, slots=True)
class QuiverConfig:
    index_url: str
    catalog: str
    project_policy: str


def load_quiver_config(value: object) -> QuiverConfig:
    if not isinstance(value, dict):
        raise TypeError("quiver source configuration must be an object")
    index = value.get("index_url")
    catalog = value.get("catalog")
    policy = value.get("project_policy")
    if not isinstance(index, str) or not _catalog_root(index):
        raise ValueError("quiver index_url must be an HTTPS catalog JSON URL")
    if not isinstance(catalog, str) or not catalog.strip():
        raise ValueError("quiver catalog path must be a nonempty string")
    if not isinstance(policy, str) or not policy.strip():
        raise ValueError("quiver project_policy path must be a nonempty string")
    return QuiverConfig(index, catalog, policy)


class Category(StrEnum):
    """Pack categories a Quiver entry may be filed under."""

    DECOMPS = "Decomps/Recomps"
    PC_PORTS = "PC Ports"


@dataclass(frozen=True, slots=True)
class QuiverRule:
    project: ProjectRule
    category: Category = Category.DECOMPS

    def canonical(self) -> dict[str, Any]:
        return {**self.project.canonical(), "category": self.category}


@dataclass(frozen=True, slots=True)
class UrlSkip:
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class RepositorySkip:
    repository: str
    repository_source: str | None
    reason: str


type QuiverSkip = UrlSkip | RepositorySkip


@dataclass(frozen=True, slots=True)
class QuiverPolicy:
    projects: dict[str, QuiverRule]
    skips: tuple[QuiverSkip, ...]

    def rule_for(self, project: str) -> QuiverRule:
        return self.projects.get(project, QuiverRule(default_apk_rule()))

    def skip_for(self, row: QuiverRow) -> QuiverSkip | None:
        for skip in self.skips:
            match skip:
                case UrlSkip(url=url) if row.listed == url:
                    return skip
                case RepositorySkip(
                    repository=repository, repository_source=source
                ) if row.repository == repository and row.repository_source == source:
                    return skip
        return None


def parse_quiver_policy(data: bytes | object) -> QuiverPolicy:
    if isinstance(data, bytes):
        try:
            data = json.loads(data, object_pairs_hook=_unique_policy_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PolicyError(f"quiver policy is not valid JSON: {error}") from error
    if not isinstance(data, dict) or set(data) - {"schemaVersion", "projects", "skips"}:
        raise PolicyError("quiver policy has invalid fields")
    if data.get("schemaVersion") != 1 or isinstance(data.get("schemaVersion"), bool):
        raise PolicyError("quiver policy schemaVersion must be 1")
    raw_projects = data.get("projects")
    if not isinstance(raw_projects, dict):
        raise PolicyError("quiver policy projects must be an object")
    project_rules: dict[str, dict[str, Any]] = {}
    categories: dict[str, Category] = {}
    for raw_url, raw_rule in raw_projects.items():
        if not isinstance(raw_url, str) or not isinstance(raw_rule, dict):
            raise PolicyError("quiver project rules must map URLs to objects")
        try:
            url = repository_url(raw_url)
        except ValueError as error:
            raise PolicyError(f"invalid quiver project URL {raw_url!r}") from error
        if url in project_rules:
            raise PolicyError(f"duplicate normalized quiver project URL {url}")
        if set(raw_rule) - {"name", "category", "additionalSettings"}:
            raise PolicyError(f"{url}: unsupported quiver project rule field")
        try:
            categories[url] = Category(raw_rule.get("category", Category.DECOMPS))
        except ValueError as error:
            raise PolicyError(
                f"{url}: category must be one of {[str(c) for c in Category]}"
            ) from error
        project_rules[url] = {
            "kind": "apk",
            **{k: v for k, v in raw_rule.items() if k != "category"},
        }
    parsed = parse_project_policy({"schemaVersion": 1, "projects": project_rules})
    projects = {
        url: QuiverRule(rule, categories[url]) for url, rule in parsed.projects.items()
    }
    raw_skips = data.get("skips", [])
    if not isinstance(raw_skips, list):
        raise PolicyError("quiver skips must be a list")
    skips: list[QuiverSkip] = []
    seen: set[tuple[str, ...]] = set()
    for item in raw_skips:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("reason"), str)
            or not item["reason"].strip()
        ):
            raise PolicyError("quiver skip requires a nonempty reason")
        skip: QuiverSkip
        if set(item) == {"url", "reason"} and isinstance(item["url"], str):
            try:
                url = repository_url(item["url"])
            except ValueError as error:
                raise PolicyError("quiver skip has invalid listed URL") from error
            skip = UrlSkip(url, item["reason"])
        elif set(item) in (
            {"repository", "reason"},
            {"repository", "repositorySource", "reason"},
        ):
            repository = item["repository"]
            source = item.get("repositorySource")
            if (
                not isinstance(repository, str)
                or not repository
                or (source is not None and not isinstance(source, str))
            ):
                raise PolicyError("quiver literal skip has invalid repository values")
            if _listed_repository(repository, source) is not None:
                raise PolicyError("supported GitHub rows must be skipped by listed URL")
            skip = RepositorySkip(repository, source, item["reason"])
        else:
            raise PolicyError(
                "quiver skip must name a listed URL or literal repository values"
            )
        key = _skip_key(skip)
        if key in seen:
            raise PolicyError("duplicate quiver skip")
        seen.add(key)
        skips.append(skip)
    return QuiverPolicy(projects, tuple(skips))


def _skip_key(skip: QuiverSkip) -> tuple[str, ...]:
    match skip:
        case UrlSkip(url=url):
            return (url,)
        case RepositorySkip(repository=repository, repository_source=source):
            return (repository, source or "")


def _unique_policy_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"duplicate quiver policy JSON key {key!r}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class QuiverRow:
    list_id: str
    list_url: str
    repository: object
    repository_source: object
    listed: str | None
    project_name: str | None
    release_asset_filter: object


@dataclass(frozen=True, slots=True)
class QuiverProject:
    key: str
    url: str
    name: str
    rows: tuple[QuiverRow, ...]
    rule: QuiverRule


@dataclass(frozen=True, slots=True)
class QuiverLookupFailure:
    row: QuiverRow
    rule: QuiverRule
    error: HttpError | ValueError | TypeError


@dataclass(frozen=True, slots=True)
class QuiverUnavailable:
    """A listed repository whose lookup conclusively returned HTTP 404 or 451."""

    url: str
    rows: tuple[QuiverRow, ...]
    error: HttpStatusError


@dataclass(frozen=True, slots=True)
class QuiverDiscovery:
    projects: tuple[QuiverProject, ...]
    skipped: tuple[tuple[QuiverRow, str], ...]
    unsupported: tuple[QuiverRow, ...]
    lookup_failures: tuple[QuiverLookupFailure, ...]
    unavailable: tuple[QuiverUnavailable, ...]
    filter_disagreements: tuple[str, ...]
    list_ids: tuple[str, ...]


def _catalog_root(index_url: str) -> tuple[str, str] | None:
    parsed = urlsplit(index_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(".json")
        or "%" in parsed.path
        or any(part in {".", ".."} for part in parsed.path.split("/"))
    ):
        return None
    return parsed.hostname.lower(), parsed.path.rpartition("/")[0] + "/"


def _within_catalog(url: str, root: tuple[str, str]) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == root[0]
            and parsed.username is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and "%" not in parsed.path
            and all(part not in {".", ".."} for part in parsed.path.split("/"))
            and parsed.path.startswith(root[1])
        )
    except ValueError:
        return False


def _read_catalog_json(http: GenerationHttp, url: str, root: tuple[str, str]) -> object:
    if not _within_catalog(url, root):
        raise ValueError("location is outside the configured catalog")
    response = http.get(
        url,
        max_bytes=MAX_CATALOG_BYTES,
        allowed_url=lambda target: _within_catalog(target, root),
    )
    if not _within_catalog(response.url, root):
        raise ValueError("redirect left the configured catalog")
    return response.json()


def _listed_repository(repository: object, source: object) -> str | None:
    if not isinstance(repository, str) or _PAIR.fullmatch(repository) is None:
        return None
    if source is not None and (
        not isinstance(source, str) or source.lower() != "github"
    ):
        return None
    try:
        return repository_url(f"https://github.com/{repository}")
    except ValueError:
        return None


def _repository_api(project: str) -> str:
    _, owner, repository = project.split("/")
    return f"https://api.github.com/repos/{owner}/{repository}"


def _canonical_repository(http: GenerationHttp, listed: str) -> tuple[str, str]:
    """Return the normalized key used for matching and GitHub's display URL."""
    response = http.get(
        _repository_api(listed), headers={"Accept": "application/vnd.github+json"}
    )
    value = response.json()
    if not isinstance(value, dict) or not isinstance(value.get("full_name"), str):
        raise TypeError(f"repository metadata is malformed for {listed}")
    full_name = value["full_name"]
    if _PAIR.fullmatch(full_name) is None:
        raise ValueError(f"repository metadata has invalid full_name for {listed}")
    url = f"https://github.com/{full_name}"
    return repository_url(url), url


def discovery_name(rows: Iterable[QuiverRow], fallback: str) -> str:
    """Pick the port name for rows of one project independently of row order."""
    names = sorted(
        {row.project_name for row in rows if row.project_name},
        key=lambda value: (value.casefold(), value),
    )
    return names[0] if names else fallback


def discover_quiver(
    index_url: str, policy: QuiverPolicy, http: GenerationHttp
) -> QuiverDiscovery:
    root = _catalog_root(index_url)
    if root is None:
        raise ValueError("quiver index URL is malformed")
    index = _read_catalog_json(http, index_url, root)
    if (
        not isinstance(index, dict)
        or index.get("version") != 2
        or not isinstance(index.get("lists"), list)
        or not index["lists"]
    ):
        raise ValueError("quiver index has no lists")
    locations: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for item in index["lists"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"]
            or not isinstance(item.get("remoteLocation"), str)
        ):
            raise ValueError("quiver index has a malformed list reference")
        if item["id"] in seen_ids or not _within_catalog(item["remoteLocation"], root):
            raise ValueError("quiver index has duplicate IDs or an out-of-catalog list")
        seen_ids.add(item["id"])
        locations.append((item["id"], item["remoteLocation"]))
    rows: list[QuiverRow] = []
    for list_id, list_url in locations:
        document = _read_catalog_json(http, list_url, root)
        if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
            raise TypeError(f"quiver list {list_id} is malformed")
        for raw in document["apps"]:
            if not isinstance(raw, dict):
                raise TypeError(f"quiver list {list_id} has a malformed row")
            repository = raw.get("repository")
            source = raw.get("repositorySource")
            listed = _listed_repository(repository, source)
            name = raw.get("project")
            rows.append(
                QuiverRow(
                    list_id,
                    list_url,
                    repository,
                    source,
                    listed,
                    name.strip() if isinstance(name, str) and name.strip() else None,
                    raw.get("releaseAssetFilter"),
                )
            )
    if not rows:
        raise ValueError("quiver discovery is empty")
    skipped: list[tuple[QuiverRow, str]] = []
    unsupported: list[QuiverRow] = []
    lookup_failures: list[QuiverLookupFailure] = []
    grouped: dict[str, list[QuiverRow]] = {}
    display: dict[str, str] = {}
    aliases: dict[str, str] = {}
    unavailable: dict[str, tuple[HttpStatusError, list[QuiverRow]]] = {}
    lookups: dict[str, tuple[str, str] | HttpError | ValueError | TypeError] = {}
    for row in rows:
        skip = policy.skip_for(row)
        if skip is not None:
            skipped.append((row, skip.reason))
            continue
        if row.listed is None:
            unsupported.append(row)
            continue
        if row.listed not in lookups:
            try:
                lookups[row.listed] = _canonical_repository(http, row.listed)
            except (HttpError, ValueError, TypeError) as error:
                lookups[row.listed] = error
        lookup = lookups[row.listed]
        if isinstance(lookup, HttpStatusError) and lookup.status in {404, 451}:
            unavailable.setdefault(row.listed, (lookup, []))[1].append(row)
            continue
        if not isinstance(lookup, tuple):
            lookup_failures.append(
                QuiverLookupFailure(row, policy.rule_for(row.listed), lookup)
            )
            continue
        canonical, display[canonical] = lookup
        grouped.setdefault(canonical, []).append(row)
        aliases[row.listed] = canonical
    projects: list[QuiverProject] = []
    disagreements: list[str] = []
    for canonical, members in sorted(grouped.items()):
        matching_rules = {
            key
            for key in policy.projects
            if key == canonical or aliases.get(key) == canonical
        }
        if len(matching_rules) > 1:
            raise PolicyError(
                f"ambiguous Quiver policy after repository rename: {sorted(matching_rules)}"
            )
        rule = policy.rule_for(next(iter(matching_rules), canonical))
        url = display[canonical]
        name = discovery_name(members, url.rsplit("/", 1)[-1])
        filters = {
            json.dumps(row.release_asset_filter, sort_keys=True, default=str)
            for row in members
        }
        if len(filters) > 1:
            disagreements.append(canonical)
        projects.append(QuiverProject(canonical, url, name, tuple(members), rule))
    return QuiverDiscovery(
        tuple(projects),
        tuple(skipped),
        tuple(unsupported),
        tuple(lookup_failures),
        tuple(
            QuiverUnavailable(listed, tuple(members), error)
            for listed, (error, members) in sorted(unavailable.items())
        ),
        tuple(disagreements),
        tuple(list_id for list_id, _ in locations),
    )


def resolve_quiver_apk(
    http: GenerationHttp,
    release: dict[str, Any],
    rule: QuiverRule,
    filtered_assets: list[dict[str, Any]],
    project: str,
) -> str:
    """Resolve APK identity, recording filtered asset names whatever the outcome.

    APK names excluded by the reviewed filename filter are appended to
    `filtered_assets`.
    """
    diagnostics: dict[str, Any] = {}
    try:
        return resolve_release_assets(
            http,
            release,
            rule.project.additional_settings.get("apkFilterRegEx", ""),
            diagnostics,
            project,
        )
    finally:
        filtered_assets.extend(diagnostics.get("filteredAssets", ()))
