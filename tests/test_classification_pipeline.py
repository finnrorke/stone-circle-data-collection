from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dataset_collection.classify import classify_normalized_records
from dataset_collection.cli import main


def _write_jsonl(path: Path, records: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record))
            handle.write("\n")


def _normalized_record(
    *,
    source_id: str,
    canonical_name: str,
    source_record_id: str,
    description: str | None = None,
    raw_type: str | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_name": source_id.replace("_", " ").title(),
        "source_record_id": source_record_id,
        "source_dataset": source_id,
        "source_url": f"https://example.com/{source_record_id}",
        "raw_file_path": f"data/raw/{source_id}/2026-03-08/{source_id}.geojson",
        "raw_record_index": 0,
        "canonical_name": canonical_name,
        "alternate_names": [],
        "nation": "England",
        "county_or_region": "Cornwall",
        "latitude": 50.0,
        "longitude": -5.0,
        "geometry_type": "Point",
        "geometry_wkt": "POINT (-5 50)",
        "site_types": [],
        "primary_type": None,
        "period": "Prehistoric",
        "designation_status": "scheduled",
        "grid_reference": "SW123456",
        "description": description,
        "tags": [],
        "raw_name": canonical_name,
        "raw_type": raw_type,
        "raw_subtype": None,
        "raw_description": description,
        "provenance": {
            "fetched_at": "2026-03-08T12:00:00+00:00",
            "source_metadata_file": f"data/raw/{source_id}/2026-03-08/{source_id}.metadata.json",
            "parser_name": source_id,
            "parser_version": "1.0",
            "normalization_timestamp": "2026-03-08T12:30:00+00:00",
            "raw_source_fields": {"Name": canonical_name},
        },
    }


def test_reads_one_normalized_source_file_and_writes_classified_outputs(tmp_path: Path) -> None:
    normalized_root = tmp_path / "data" / "normalized"
    output_root = tmp_path / "data" / "classified"
    _write_jsonl(
        normalized_root / "historic_england.jsonl",
        [
            _normalized_record(
                source_id="historic_england",
                source_record_id="he-1",
                canonical_name="Merry Maidens Stone Circle",
            ),
            _normalized_record(
                source_id="historic_england",
                source_record_id="he-2",
                canonical_name="St Mary's Church",
                raw_type="church",
            ),
            _normalized_record(
                source_id="historic_england",
                source_record_id="he-3",
                canonical_name="Carn View",
                description="Possible ring cairn noted by survey.",
            ),
        ],
    )

    summary = classify_normalized_records(
        normalized_root=normalized_root,
        output_root=output_root,
    )

    assert summary.records_read == 3
    assert summary.included_count == 1
    assert summary.excluded_count == 1
    assert summary.review_count == 1
    assert summary.parse_failures == 0

    included_lines = (output_root / "included.jsonl").read_text(encoding="utf-8").splitlines()
    excluded_lines = (output_root / "excluded.jsonl").read_text(encoding="utf-8").splitlines()
    review_lines = (output_root / "review.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(included_lines) == 1
    assert len(excluded_lines) == 1
    assert len(review_lines) == 1

    included_record = json.loads(included_lines[0])
    assert included_record["canonical_name"] == "Merry Maidens Stone Circle"
    assert included_record["provenance"]["parser_name"] == "historic_england"
    assert included_record["classification"] == "included"
    assert included_record["classification_reason"] == "Matched megalith-specific include term"
    assert included_record["classification_rules_matched"] == ["include:stone circle"]
    assert included_record["classification_confidence"] == "high"


def test_missing_normalized_directory_is_handled_cleanly(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    summary = classify_normalized_records(
        normalized_root=tmp_path / "data" / "normalized",
        output_root=tmp_path / "data" / "classified",
    )

    assert summary.records_read == 0
    assert summary.parse_failures == 0
    assert "Normalized input directory does not exist" in caplog.text
    assert not (tmp_path / "data" / "classified").exists()


def test_empty_normalized_file_is_handled_cleanly(tmp_path: Path) -> None:
    normalized_root = tmp_path / "data" / "normalized"
    (normalized_root / "cadw.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (normalized_root / "cadw.jsonl").write_text("", encoding="utf-8")

    summary = classify_normalized_records(
        normalized_root=normalized_root,
        output_root=tmp_path / "data" / "classified",
    )

    assert summary.records_read == 0
    assert summary.included_count == 0
    assert summary.excluded_count == 0
    assert summary.review_count == 0
    assert summary.parse_failures == 0

    assert (tmp_path / "data" / "classified" / "included.jsonl").read_text(encoding="utf-8") == ""
    assert (tmp_path / "data" / "classified" / "excluded.jsonl").read_text(encoding="utf-8") == ""
    assert (tmp_path / "data" / "classified" / "review.jsonl").read_text(encoding="utf-8") == ""


def test_one_bad_line_does_not_crash_the_whole_classification_run(tmp_path: Path) -> None:
    normalized_root = tmp_path / "data" / "normalized"
    file_path = normalized_root / "nismr.jsonl"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "\n".join(
            [
                json.dumps(
                    _normalized_record(
                        source_id="nismr",
                        source_record_id="ni-1",
                        canonical_name="Bally Stone Circle",
                    )
                ),
                "{not-json}",
                json.dumps(
                    _normalized_record(
                        source_id="nismr",
                        source_record_id="ni-2",
                        canonical_name="North Fort",
                        description="standing stones beside the fort",
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = classify_normalized_records(
        normalized_root=normalized_root,
        output_root=tmp_path / "data" / "classified",
    )

    assert summary.records_read == 2
    assert summary.parse_failures == 1
    assert summary.included_count == 2
    assert len((tmp_path / "data" / "classified" / "included.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_cli_classify_supports_source_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized_root = tmp_path / "data" / "normalized"
    _write_jsonl(
        normalized_root / "historic_england.jsonl",
        [
            _normalized_record(
                source_id="historic_england",
                source_record_id="he-1",
                canonical_name="Stone Circle One",
            )
        ],
    )
    _write_jsonl(
        normalized_root / "cadw.jsonl",
        [
            _normalized_record(
                source_id="cadw",
                source_record_id="ca-1",
                canonical_name="Village Church",
                raw_type="church",
            )
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dataset-collection",
            "classify",
            "--source",
            "historic_england",
            "--normalized-root",
            str(normalized_root),
            "--output-root",
            str(tmp_path / "data" / "classified"),
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert len((tmp_path / "data" / "classified" / "included.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert (tmp_path / "data" / "classified" / "excluded.jsonl").read_text(encoding="utf-8") == ""
