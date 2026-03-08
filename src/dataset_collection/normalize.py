from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from dataset_collection.canonical_models import RawFileSelection, SourceNormalizationSummary
from dataset_collection.models import DownloadMetadata, SourceDefinition
from dataset_collection.parsers import get_parser
from dataset_collection.storage import ensure_parent_directory, metadata_path_for

logger = logging.getLogger(__name__)


def normalise_sources(
    sources: list[SourceDefinition],
    raw_root: Path,
    output_root: Path,
) -> list[SourceNormalizationSummary]:
    output_root.mkdir(parents=True, exist_ok=True)
    summaries: list[SourceNormalizationSummary] = []

    for source in sources:
        if not source.enabled:
            logger.info("Skipping disabled source '%s'", source.id)
            summaries.append(
                SourceNormalizationSummary(source_id=source.id, skipped_reason="disabled_source")
            )
            continue

        if source.type == "manual":
            logger.info("Skipping manual source '%s'", source.id)
            summaries.append(
                SourceNormalizationSummary(source_id=source.id, skipped_reason="manual_source")
            )
            continue

        raw_selection = find_latest_raw_file(source=source, raw_root=raw_root)
        if raw_selection is None:
            logger.warning("No raw file found for '%s'", source.id)
            summaries.append(
                SourceNormalizationSummary(source_id=source.id, skipped_reason="missing_raw_file")
            )
            continue

        parser = get_parser(source.id)
        if parser is None:
            logger.info("Skipping unsupported source '%s'", source.id)
            summaries.append(
                SourceNormalizationSummary(source_id=source.id, skipped_reason="unsupported_source")
            )
            continue

        output_path = output_root / f"{source.id}.jsonl"
        try:
            parsed = parser(
                source=source,
                raw_file_path=raw_selection.raw_file_path,
                fetched_at=raw_selection.fetched_at,
                metadata_path=str(raw_selection.metadata_path) if raw_selection.metadata_path else None,
            )
            _write_jsonl(output_path, parsed.records)
            summary = SourceNormalizationSummary(
                source_id=source.id,
                records_read=parsed.records_read,
                records_written=len(parsed.records),
                records_failed=parsed.records_failed,
                output_file=str(output_path),
            )
            logger.info(
                "Normalised '%s': %s read, %s written, %s failed",
                source.id,
                summary.records_read,
                summary.records_written,
                summary.records_failed,
            )
        except Exception:
            logger.exception("Failed to normalise source '%s'", source.id)
            summary = SourceNormalizationSummary(
                source_id=source.id,
                skipped_reason="source_error",
            )
        summaries.append(summary)

    return summaries


def find_latest_raw_file(source: SourceDefinition, raw_root: Path) -> RawFileSelection | None:
    source_root = raw_root / source.id
    if not source_root.exists():
        return None

    for date_dir in _dated_directories(source_root):
        candidates = sorted(
            [
                path
                for path in date_dir.iterdir()
                if path.is_file() and not path.name.endswith(".metadata.json")
            ],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            metadata_path = metadata_path_for(candidate)
            metadata = _load_metadata(metadata_path)
            if metadata is not None and not metadata.success:
                continue

            return RawFileSelection(
                raw_file_path=candidate,
                metadata_path=metadata_path if metadata_path.exists() else None,
                fetched_at=metadata.fetched_at if metadata is not None else None,
            )

    return None


def _dated_directories(source_root: Path) -> list[Path]:
    dated_paths: list[tuple[date, Path]] = []
    for child in source_root.iterdir():
        if not child.is_dir():
            continue
        try:
            dated_paths.append((date.fromisoformat(child.name), child))
        except ValueError:
            logger.debug("Ignoring non-date raw directory: %s", child)

    return [path for _, path in sorted(dated_paths, key=lambda item: item[0], reverse=True)]


def _load_metadata(metadata_path: Path) -> DownloadMetadata | None:
    if not metadata_path.exists():
        return None

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return DownloadMetadata.model_validate(payload)


def _write_jsonl(output_path: Path, records: list[object]) -> None:
    ensure_parent_directory(output_path)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            payload = record.model_dump(mode="json")
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")
