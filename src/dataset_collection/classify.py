from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from dataset_collection.classification_rules import classify_record
from dataset_collection.storage import ensure_parent_directory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationRunSummary:
    records_read: int = 0
    included_count: int = 0
    excluded_count: int = 0
    review_count: int = 0
    parse_failures: int = 0


def classify_normalized_records(
    normalized_root: Path,
    output_root: Path,
    source_id: str | None = None,
) -> ClassificationRunSummary:
    if not normalized_root.exists():
        logger.warning("Normalized input directory does not exist: %s", normalized_root)
        return ClassificationRunSummary()

    input_files = _input_files(normalized_root=normalized_root, source_id=source_id)
    output_root.mkdir(parents=True, exist_ok=True)

    included_path = output_root / "included.jsonl"
    excluded_path = output_root / "excluded.jsonl"
    review_path = output_root / "review.jsonl"
    for output_path in (included_path, excluded_path, review_path):
        ensure_parent_directory(output_path)

    records_read = 0
    included_count = 0
    excluded_count = 0
    review_count = 0
    parse_failures = 0

    with (
        included_path.open("w", encoding="utf-8") as included_handle,
        excluded_path.open("w", encoding="utf-8") as excluded_handle,
        review_path.open("w", encoding="utf-8") as review_handle,
    ):
        output_handles = {
            "included": included_handle,
            "excluded": excluded_handle,
            "review": review_handle,
        }

        for input_file in input_files:
            for line_number, line in enumerate(input_file.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("record is not an object")
                except (json.JSONDecodeError, ValueError):
                    parse_failures += 1
                    logger.warning("Skipping unreadable normalized record in %s line %s", input_file, line_number)
                    continue

                records_read += 1
                decision = classify_record(record)
                classified_record = {
                    **record,
                    "classification": decision.classification,
                    "classification_reason": decision.classification_reason,
                    "classification_rules_matched": decision.classification_rules_matched,
                    "classification_confidence": decision.classification_confidence,
                }
                _write_jsonl_line(output_handles[decision.classification], classified_record)

                if decision.classification == "included":
                    included_count += 1
                elif decision.classification == "excluded":
                    excluded_count += 1
                else:
                    review_count += 1

    return ClassificationRunSummary(
        records_read=records_read,
        included_count=included_count,
        excluded_count=excluded_count,
        review_count=review_count,
        parse_failures=parse_failures,
    )


def _input_files(normalized_root: Path, source_id: str | None) -> list[Path]:
    if source_id is not None:
        candidate = normalized_root / f"{source_id}.jsonl"
        return [candidate] if candidate.exists() else []
    return sorted(path for path in normalized_root.glob("*.jsonl") if path.is_file())


def _write_jsonl_line(handle: TextIO, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, ensure_ascii=True))
    handle.write("\n")
