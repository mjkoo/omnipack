"""Live source resolution, bounded probing, and version classification."""

from __future__ import annotations

import json
import re
import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from omnipack.http import HttpClient, HttpError, HttpResponse, redact_url
from omnipack.offline import Finding, ValidatedEntry
from omnipack.resolution.github import resolve_github
from omnipack.resolution.html import resolve_html
from omnipack.resolution.types import ResolutionError, ResolutionResult


class VersionClass(str, Enum):
    """How an effective version participates in GitHub numeric linting."""

    NUMERIC = "numeric"
    NONNUMERIC = "nonnumeric"
    TRACK_ONLY = "track-only"
    DETECTION_DISABLED = "version-detection-disabled"
    DATE = "date-version"
    NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """A selected download candidate safe to include in evidence."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class ResolutionEvidence:
    """Sanitized source-selection evidence."""

    raw_version: str
    effective_version: str
    version_origin: str
    candidates: tuple[CandidateEvidence, ...]
    selected: dict[str, Any] | None
    inspected_count: int | None
    window_limit: int | None


@dataclass(frozen=True, slots=True)
class ProbeEvidence:
    """The outcome of one bounded candidate request."""

    name: str
    url: str
    success: bool
    response_url: str | None = None
    status: int | None = None
    bytes_read: int = 0
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class LiveEntryResult:
    """Resolution and probe outcome for one variant entry."""

    variant: str
    entry_id: str
    index: int
    source: str
    resolution: ResolutionEvidence | None
    probes: tuple[ProbeEvidence, ...]
    version_class: VersionClass | None
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class LiveResult:
    """All live outcomes, including aggregate findings."""

    entries: tuple[LiveEntryResult, ...]
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


_NUMERIC_VERSION = re.compile(
    r"[vV]?(?:\d+|\d+(?:\.\d+)+(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?)\Z"
)
_URL_IN_MESSAGE = re.compile(r"https?://[^\s\"'<>]+")


def verify_live(
    entries: Mapping[str, tuple[ValidatedEntry, ...]],
    http: HttpClient,
    *,
    probe_assets: bool = False,
) -> LiveResult:
    """Resolve every entry and optionally probe its selected asset candidates."""
    cached_http = _CachingHttpClient(http)
    resolutions: dict[
        tuple[str, str, str], tuple[ResolutionResult | None, Exception | None]
    ] = {}
    results: list[LiveEntryResult] = []
    errors: list[Finding] = []
    warnings: list[Finding] = []

    for variant_entries in entries.values():
        for entry in variant_entries:
            result = _verify_entry(
                entry, cached_http, resolutions, probe_assets=probe_assets
            )
            results.append(result)
            errors.extend(result.errors)
            warnings.extend(result.warnings)
    return LiveResult(tuple(results), tuple(errors), tuple(warnings))


def classify_version(
    source: str,
    settings: Mapping[str, object],
    resolution: ResolutionResult,
) -> tuple[VersionClass, Finding | None]:
    """Classify a resolved version and return its optional lint finding."""
    if source != "GitHub":
        return VersionClass.NOT_APPLICABLE, None
    if settings.get("trackOnly") is True:
        return VersionClass.TRACK_ONLY, None
    if settings.get("versionDetection") is False:
        return VersionClass.DETECTION_DISABLED, None
    if settings.get("releaseDateAsVersion") is True:
        return VersionClass.DATE, None
    if _NUMERIC_VERSION.fullmatch(resolution.effective_version) is not None:
        return VersionClass.NUMERIC, None
    return (
        VersionClass.NONNUMERIC,
        Finding(
            "version-lint",
            "github-version-format",
            f"effective GitHub version {resolution.effective_version!r} "
            "does not match the numeric version shape",
        ),
    )


def _verify_entry(
    entry: ValidatedEntry,
    http: _CachingHttpClient,
    resolutions: dict[
        tuple[str, str, str], tuple[ResolutionResult | None, Exception | None]
    ],
    *,
    probe_assets: bool,
) -> LiveEntryResult:
    key = (
        entry.source,
        str(entry.raw.get("url", "")),
        json.dumps(entry.settings, sort_keys=True, separators=(",", ":")),
    )
    try:
        outcome = resolutions.get(key)
        if outcome is None:
            try:
                resolver = resolve_github if entry.source == "GitHub" else resolve_html
                outcome = (resolver(entry.raw, http), None)
            except (ResolutionError, HttpError, OSError, ValueError) as error:
                outcome = (None, error)
            resolutions[key] = outcome
        resolution, resolution_error = outcome
        if resolution_error is not None:
            raise resolution_error
        assert resolution is not None
    except ResolutionError as error:
        finding = _finding(
            entry, "resolution", error.code, _resolution_failure_message(error)
        )
        return LiveEntryResult(
            entry.variant,
            entry.entry_id,
            entry.index,
            entry.source,
            None,
            (),
            None,
            (finding,),
            (),
        )
    except (HttpError, OSError, ValueError) as error:
        finding = _finding(
            entry,
            "resolution",
            "source-resolution-failed",
            _sanitize_message(str(error)) or "source resolution failed",
        )
        return LiveEntryResult(
            entry.variant,
            entry.entry_id,
            entry.index,
            entry.source,
            None,
            (),
            None,
            (finding,),
            (),
        )

    version_class, lint = classify_version(entry.source, entry.settings, resolution)
    entry_warnings: list[Finding] = []
    if lint is not None:
        entry_warnings.append(_finding(entry, lint.stage, lint.code, lint.message))

    probes: list[ProbeEvidence] = []
    entry_errors: list[Finding] = []
    if probe_assets and entry.settings.get("trackOnly") is not True:
        succeeded = False
        for candidate in resolution.candidates:
            try:
                response = http.probe(
                    candidate.url, headers=dict(resolution.request_headers)
                )
            except (HttpError, OSError, ValueError) as error:
                probes.append(
                    ProbeEvidence(
                        candidate.name,
                        _safe_redact_url(candidate.url),
                        False,
                        failure_reason=_probe_failure_reason(error),
                    )
                )
                continue
            probes.append(
                ProbeEvidence(
                    candidate.name,
                    _safe_redact_url(candidate.url),
                    True,
                    _safe_redact_url(response.url),
                    response.status,
                    len(response.body),
                )
            )
            succeeded = True
            break
        if succeeded:
            entry_warnings.extend(
                _finding(
                    entry,
                    "probe",
                    "candidate-probe-failed",
                    f"selected candidate {probe.url} failed: {probe.failure_reason}",
                )
                for probe in probes
                if not probe.success
            )
        else:
            entry_errors.append(
                _finding(
                    entry,
                    "probe",
                    "candidate-probes-failed",
                    "no selected download candidate was reachable"
                    + "".join(
                        f"; {probe.url}: {probe.failure_reason}" for probe in probes
                    ),
                )
            )

    return LiveEntryResult(
        entry.variant,
        entry.entry_id,
        entry.index,
        entry.source,
        _resolution_evidence(resolution),
        tuple(probes),
        version_class,
        tuple(entry_errors),
        tuple(entry_warnings),
    )


def _finding(entry: ValidatedEntry, stage: str, code: str, message: str) -> Finding:
    return Finding(
        stage,
        code,
        message,
        entry.variant,
        entry.entry_id,
        entry.index,
    )


def _resolution_evidence(result: ResolutionResult) -> ResolutionEvidence:
    return ResolutionEvidence(
        result.raw_version,
        result.effective_version,
        result.version_origin,
        tuple(
            CandidateEvidence(candidate.name, _safe_redact_url(candidate.url))
            for candidate in result.candidates
        ),
        _sanitize_selected(result.selected),
        result.inspected_count,
        result.window_limit,
    )


def _sanitize_selected(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        key: _safe_redact_url(item)
        if isinstance(item, str) and "url" in key.casefold()
        else item
        for key, item in value.items()
    }


def _sanitize_message(message: str) -> str:
    return _URL_IN_MESSAGE.sub(lambda match: _safe_redact_url(match.group(0)), message)


def _safe_redact_url(url: str) -> str:
    try:
        return redact_url(url)
    except ValueError:
        return "<invalid-url>"


class _CachingHttpClient(HttpClient):
    """Invocation-local exact cache for metadata and optional asset probes."""

    def __init__(self, delegate: HttpClient) -> None:
        self._delegate = delegate
        self._metadata: dict[
            tuple[str, tuple[tuple[str, str], ...]],
            tuple[HttpResponse | None, Exception | None],
        ] = {}
        self._probes: dict[
            tuple[str, tuple[tuple[str, str], ...]],
            tuple[HttpResponse | None, Exception | None],
        ] = {}

    def get_metadata(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        key = (url, tuple(sorted((headers or {}).items())))
        if key not in self._metadata:
            self._metadata[key] = self._call(
                self._delegate.get_metadata, url, headers=headers
            )
        return self._unwrap(self._metadata[key])

    def probe(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        key = (url, tuple(sorted((headers or {}).items())))
        if key not in self._probes:
            self._probes[key] = self._call(self._delegate.probe, url, headers=headers)
        return self._unwrap(self._probes[key])

    @staticmethod
    def _call(
        method: Any, url: str, *, headers: Mapping[str, str] | None
    ) -> tuple[HttpResponse | None, Exception | None]:
        try:
            return method(url, headers=headers), None
        except (HttpError, OSError, ValueError) as error:
            return None, error

    @staticmethod
    def _unwrap(outcome: tuple[HttpResponse | None, Exception | None]) -> HttpResponse:
        response, error = outcome
        if error is not None:
            raise error
        assert response is not None
        return response


def _probe_failure_reason(error: Exception) -> str:
    cause = error.__cause__
    if isinstance(cause, urllib.error.HTTPError):
        detail = f"HTTP {cause.code}"
    elif isinstance(cause, TimeoutError):
        detail = "request timed out"
    elif isinstance(cause, urllib.error.URLError):
        detail = str(cause.reason)
    elif cause is not None:
        detail = str(cause) or type(cause).__name__
    else:
        detail = ""
    message = str(error) or type(error).__name__
    return _sanitize_message(f"{message}: {detail}" if detail else message)


def _resolution_failure_message(error: ResolutionError) -> str:
    message = str(error)
    cause = error.__cause__
    if cause is not None:
        detail = str(cause)
        if detail and detail not in message:
            message = f"{message}: {detail}"
    return _sanitize_message(message)
