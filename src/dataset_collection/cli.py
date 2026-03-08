from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dataset_collection.downloader import collect_sources
from dataset_collection.logging_config import configure_logging
from dataset_collection.manifest import load_sources

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dataset-collection")
    parser.add_argument("--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-manifest")
    validate_parser.add_argument("--sources", type=Path, required=True)
    validate_parser.set_defaults(handler=handle_validate_manifest)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--sources", type=Path, required=True)
    collect_parser.add_argument("--output-root", type=Path, default=Path("data/raw"))
    collect_parser.add_argument("--force", action="store_true")
    collect_parser.set_defaults(handler=handle_collect)

    return parser


def handle_validate_manifest(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources)
    logger.info("Validated %s sources from %s", len(sources), args.sources)
    return 0


def handle_collect(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources)
    results = collect_sources(sources=sources, output_root=args.output_root, force=args.force)
    failures = sum(1 for result in results if not result.success)
    successes = len(results) - failures
    logger.info("Collection complete: %s succeeded, %s failed", successes, failures)
    return 1 if failures else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
