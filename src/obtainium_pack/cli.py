"""`pack` command-line entry point: build, verify, report."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from obtainium_pack.build import previous_ids, publish_build
from obtainium_pack.http import HttpClient, HttpConfig
from obtainium_pack.merge import CompositionReport, CompositionResult, compose
from obtainium_pack.package_id import PackageIdCache, PackageIdResolver
from obtainium_pack.report import write_report
from obtainium_pack.sources import (
    IngestionReport,
    IngestionResult,
    SourceError,
    ingest_all,
    load_json,
)


def build(_args: argparse.Namespace) -> int:
    root = Path.cwd()
    ingestion_report = IngestionReport()
    composition_report = CompositionReport()
    composition: CompositionResult | None = None
    stage = "ingestion"

    def record_stage(value: str) -> None:
        nonlocal stage
        stage = value

    try:
        ingested = _ingest_for_build(root, ingestion_report)
        stage = "composition"
        composition = compose(
            ingested.apps,
            _object_list(root / "config/deny.json", "denylist"),
            _object(root / "config/overlay.json", "overlay"),
            _object(root / "config/overlay.dual.json", "dual overlay"),
            report=composition_report,
        )
        stage = "rendering"
        publish_build(
            root,
            composition,
            _object(root / "config/settings.json", "settings"),
            ingestion_report,
            on_stage=record_stage,
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
        from obtainium_pack.sources import SourceError

        raise SourceError("sources", "configuration must be an object")
    extras_config = load_json(root / "config/extras.json", "extras")
    http = HttpClient(HttpConfig.from_path(root / "config/http.json"))
    resolver = PackageIdResolver(http, PackageIdCache(root / "config/package-ids.json"))
    return ingest_all(http, source_config, extras_config, resolver, report)


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


def verify(args: argparse.Namespace) -> int:
    raise NotImplementedError


def report(args: argparse.Namespace) -> int:
    raise NotImplementedError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pack")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="fetch sources and render dist/")
    build_parser.set_defaults(func=build)

    verify_parser = subparsers.add_parser(
        "verify", help="run offline (and, with --live, live) checks"
    )
    verify_parser.add_argument(
        "--live", action="store_true", help="also run live APK resolution checks"
    )
    verify_parser.set_defaults(func=verify)

    report_parser = subparsers.add_parser("report", help="print the last build report")
    report_parser.set_defaults(func=report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
