"""Build verification: offline checks always, live resolution on nightly runs.

Offline: schema, unique ids, `additionalSettings` round-trips, every overlay
target exists. Live: every app resolves to at least one APK URL and a
version string, using the vendored RJNY resolver. Lint: flag GitHub apps
whose latest version does not match a standard numeric format unless the
entry opts out via `versionDetection`, `releaseDateAsVersion`,
`releaseTitleAsVersion`, or a `versionExtractionRegEx`.
"""

from __future__ import annotations

from dataclasses import dataclass

from obtainium_pack.model import App


@dataclass(frozen=True, slots=True)
class VerifyReport:
    """Findings from a verify pass, surfaced in the build report."""

    errors: list[str]
    lint_findings: list[str]


def verify_offline(apps: list[App]) -> VerifyReport:
    """Run the offline checks that gate every build."""
    raise NotImplementedError


def verify_live(apps: list[App]) -> VerifyReport:
    """Run the live checks that gate nightly builds."""
    raise NotImplementedError
