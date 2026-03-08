from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dataset_collection.downloader import collect_sources
from dataset_collection.normalize import normalise_sources
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

    normalise_parser = subparsers.add_parser("normalise")
    normalise_parser.add_argument("--sources", type=Path, required=True)
    normalise_parser.add_argument("--source", dest="source_id")
    normalise_parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    normalise_parser.add_argument("--output-root", type=Path, default=Path("data/normalized"))
    normalise_parser.set_defaults(handler=handle_normalise)

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


def handle_normalise(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources)
    selected_sources = [
        source
        for source in sources
        if args.source_id is None or source.id == args.source_id
    ]
    summaries = normalise_sources(
        sources=selected_sources,
        raw_root=args.raw_root,
        output_root=args.output_root,
    )
    failures = sum(summary.records_failed for summary in summaries)
    source_errors = sum(1 for summary in summaries if summary.skipped_reason == "source_error")
    logger.info(
        "Normalization complete: %s sources, %s record failures, %s source errors",
        len(summaries),
        failures,
        source_errors,
    )
    return 1 if source_errors else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
