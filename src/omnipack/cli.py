"""`pack` command-line entry point: build, verify, report."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from omnipack.build import previous_ids, publish_build
from omnipack.composition_policy import load_composition_policy
from omnipack.http import HttpClient, HttpConfig
from omnipack.merge import CompositionReport, CompositionResult, compose
from omnipack.report import format_reports, write_report
from omnipack.source_generation import generate_codm
from omnipack.sources import (
    IngestionReport,
    IngestionResult,
    SourceError,
    ingest_all,
    load_json,
)
from omnipack.verify import VerificationReportError, run_verification


def build(_args: argparse.Namespace) -> int:
    root = Path.cwd()
    ingestion_report = IngestionReport()
    composition_report = CompositionReport()
    composition: CompositionResult | None = None
    stage = "ingestion"
    offline_verification: dict[str, Any] = {"status": "not-run", "findings": []}

    def record_stage(value: str) -> None:
        nonlocal stage
        stage = value

    def record_verification(value: dict[str, Any]) -> None:
        nonlocal offline_verification
        offline_verification = value

    try:
        ingested = _ingest_for_build(root, ingestion_report)
        stage = "composition"
        if ingested.policy is None:
            raise ValueError("ingestion result is missing composition policy")
        composition_bytes = ingested.policy_bytes
        if composition_bytes is None:
            raise ValueError("ingestion result is missing composition policy snapshot")
        composition = compose(
            ingested.apps,
            _object_list(root / "config/deny.json", "denylist"),
            load_json(root / "config/overlay.json", "overlay"),
            policy=ingested.policy,
            report=composition_report,
        )
        stage = "rendering"
        publish_build(
            root,
            composition,
            _object(root / "config/settings.json", "settings"),
            ingestion_report,
            composition_bytes,
            on_stage=record_stage,
            on_verification=record_verification,
        )
    except Exception as error:  # noqa: BLE001 - CLI converts build failures to status
        try:
            write_report(
                root,
                previous_ids(root),
                composition,
                ingestion_report,
                composition_report=composition_report,
                stage=stage,
                error=error,
                offline_verification=offline_verification,
            )
        except Exception as report_error:  # noqa: BLE001 - preserve original diagnostic
            print(
                f"build failed during {stage}: {error}; report failed: {report_error}",
                file=sys.stderr,
            )
            return 1
        print(f"build failed during {stage}: {error}", file=sys.stderr)
        return 1
    return 0


def _ingest_for_build(
    root: Path, report: IngestionReport | None = None
) -> IngestionResult:
    source_config = load_json(root / "config/sources.json", "sources")
    if not isinstance(source_config, dict):
        from omnipack.sources import SourceError

        raise SourceError("sources", "configuration must be an object")
    extras_config = load_json(root / "config/extras.json", "extras")
    http = HttpClient(HttpConfig.from_path(root / "config/http.json"))
    policy_bytes = (root / "config/composition.json").read_bytes()
    policy = load_composition_policy(policy_bytes)
    result = ingest_all(root, http, source_config, extras_config, policy, report)
    return IngestionResult(result.apps, result.report, result.policy, policy_bytes)


def _object(path: Path, source: str) -> dict[str, Any]:
    value = load_json(path, source)
    if not isinstance(value, dict):
        raise SourceError(source, "configuration must be an object")
    return value


def _object_list(path: Path, source: str) -> list[dict[str, str]]:
    value = load_json(path, source)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SourceError(source, "configuration must be a list of objects")
    return value


def verify(_args: argparse.Namespace) -> int:
    try:
        result = run_verification(Path.cwd())
    except VerificationReportError as error:
        print(f"verify failed: {error}", file=sys.stderr)
        return 1
    if result["status"] != "success":
        print(f"verify failed with {len(result['errors'])} error(s)", file=sys.stderr)
        return 1
    return 0


def report(_args: argparse.Namespace) -> int:
    try:
        print(format_reports(Path.cwd()), end="")
    except ValueError as error:
        print(f"report failed: {error}", file=sys.stderr)
        return 1
    return 0


def generate_source(_args: argparse.Namespace) -> int:
    result = generate_codm(Path.cwd())
    if result["status"] == "failed":
        detail = result.get("error") or result.get("unresolved") or "generation failed"
        print(f"source generation failed: {detail}", file=sys.stderr)
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pack")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="fetch sources and render dist/")
    build_parser.set_defaults(func=build)

    verify_parser = subparsers.add_parser(
        "verify", help="run structural checks offline"
    )
    verify_parser.set_defaults(func=verify)

    report_parser = subparsers.add_parser("report", help="print the last build report")
    report_parser.set_defaults(func=report)

    generate_parser = subparsers.add_parser(
        "generate-source", help="generate a reviewed source catalog candidate"
    )
    source_parsers = generate_parser.add_subparsers(dest="source", required=True)
    codm_parser = source_parsers.add_parser("codm", help="generate codm source")
    codm_parser.set_defaults(func=generate_source)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
