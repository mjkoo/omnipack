"""`pack` command-line entry point: build, verify, report."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from obtainium_pack.http import HttpClient, HttpConfig
from obtainium_pack.package_id import PackageIdCache, PackageIdResolver
from obtainium_pack.sources import IngestionResult, ingest_all, load_json


def build(_args: argparse.Namespace) -> int:
    _ingest_for_build(Path.cwd())
    # Composition, rendering, and atomic publication are implemented by the
    # later pipeline groups. Reaching here proves all sources were ingested.
    raise NotImplementedError("build output pipeline is not implemented")


def _ingest_for_build(root: Path) -> IngestionResult:
    source_config = load_json(root / "config/sources.json", "sources")
    if not isinstance(source_config, dict):
        from obtainium_pack.sources import SourceError

        raise SourceError("sources", "configuration must be an object")
    extras_config = load_json(root / "config/extras.json", "extras")
    http = HttpClient(HttpConfig.from_path(root / "config/http.json"))
    resolver = PackageIdResolver(http, PackageIdCache(root / "config/package-ids.json"))
    return ingest_all(http, source_config, extras_config, resolver)


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
