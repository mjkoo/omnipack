"""`pack` command-line entry point: build, verify, report."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build(args: argparse.Namespace) -> int:
    raise NotImplementedError


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
