from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataset_collection.models import SourceDefinition
from dataset_collection.normalize import find_latest_raw_file, normalise_sources


def _write_metadata(raw_file: Path, *, source: SourceDefinition, success: bool = True) -> None:
    metadata_path = raw_file.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "source_id": source.id,
                "source_name": source.name,
                "url": source.url,
                "request_method": source.method,
                "fetched_at": "2026-03-08T12:00:00+00:00",
                "http_status": 200 if success else 500,
                "content_type": "application/geo+json",
                "output_file": str(raw_file),
                "file_size": raw_file.stat().st_size if raw_file.exists() else 0,
                "sha256": None,
                "success": success,
                "error_message": None if success else "failed",
            }
        ),
        encoding="utf-8",
    )


def _write_historic_england_geojson(path: Path, *, include_bad_record: bool = False) -> None:
    features: list[object] = [
        {
            "type": "Feature",
            "properties": {
                "Name": "Stone Circle A",
                "ListEntry": "1001234",
                "NGR": "SU123456",
                "SchedDate": "1970-01-01",
                "hyperlink": "https://example.com/1001234",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-1.0, 51.0],
                        [-1.0, 51.1],
                        [-0.9, 51.1],
                        [-0.9, 51.0],
                        [-1.0, 51.0],
                    ]
                ],
            },
        }
    ]
    if include_bad_record:
        features.append("not-a-feature")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def test_find_latest_raw_file_prefers_most_recent_successful_download(tmp_path: Path) -> None:
    source = SourceDefinition(
        id="historic_england",
        name="Historic England",
        type="download",
        format="geojson",
        url="https://example.com/he.geojson",
        enabled=True,
        filename="historic_england.geojson",
    )
    older = tmp_path / "raw" / source.id / "2026-03-06" / source.filename
    older.parent.mkdir(parents=True, exist_ok=True)
    older.write_text("{}", encoding="utf-8")
    _write_metadata(older, source=source, success=True)

    newer_failed = tmp_path / "raw" / source.id / "2026-03-07" / source.filename
    newer_failed.parent.mkdir(parents=True, exist_ok=True)
    newer_failed.write_text("{}", encoding="utf-8")
    _write_metadata(newer_failed, source=source, success=False)

    newest = tmp_path / "raw" / source.id / "2026-03-08" / source.filename
    newest.parent.mkdir(parents=True, exist_ok=True)
    newest.write_text("{}", encoding="utf-8")
    _write_metadata(newest, source=source, success=True)

    selected = find_latest_raw_file(source=source, raw_root=tmp_path / "raw")

    assert selected is not None
    assert selected.raw_file_path == newest
    assert selected.metadata_path == newest.with_suffix(".metadata.json")


def test_normalise_sources_writes_jsonl_and_preserves_provenance(tmp_path: Path) -> None:
    source = SourceDefinition(
        id="historic_england",
        name="Historic England",
        type="download",
        format="geojson",
        url="https://example.com/he.geojson",
        enabled=True,
        filename="historic_england.geojson",
    )
    raw_file = tmp_path / "raw" / source.id / "2026-03-08" / source.filename
    _write_historic_england_geojson(raw_file)
    _write_metadata(raw_file, source=source)

    summaries = normalise_sources(
        sources=[source],
        raw_root=tmp_path / "raw",
        output_root=tmp_path / "normalized",
    )

    assert summaries[0].records_read == 1
    assert summaries[0].records_written == 1
    output_file = tmp_path / "normalized" / "historic_england.jsonl"
    assert output_file.exists()

    payload = json.loads(output_file.read_text(encoding="utf-8").splitlines()[0])
    assert payload["source_id"] == "historic_england"
    assert payload["source_record_id"] == "1001234"
    assert payload["canonical_name"] == "Stone Circle A"
    assert payload["site_types"] == []
    assert payload["raw_name"] == "Stone Circle A"
    assert payload["raw_file_path"] == str(raw_file)
    assert payload["raw_record_index"] == 0
    assert payload["provenance"]["fetched_at"] == "2026-03-08T12:00:00+00:00"
    assert payload["provenance"]["source_metadata_file"] == str(raw_file.with_suffix(".metadata.json"))
    assert payload["provenance"]["parser_name"] == "historic_england"
    assert payload["provenance"]["raw_source_fields"]["ListEntry"] == "1001234"


def test_normalise_sources_skips_missing_raw_files_cleanly(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    source = SourceDefinition(
        id="cadw",
        name="Cadw",
        type="download",
        format="geojson",
        url="https://example.com/cadw.geojson",
        enabled=True,
    )

    summaries = normalise_sources(
        sources=[source],
        raw_root=tmp_path / "raw",
        output_root=tmp_path / "normalized",
    )

    assert summaries[0].skipped_reason == "missing_raw_file"
    assert not (tmp_path / "normalized" / "cadw.jsonl").exists()
    assert "No raw file found for 'cadw'" in caplog.text


def test_normalise_sources_skips_manual_sources_cleanly(tmp_path: Path) -> None:
    source = SourceDefinition(
        id="hes_scheduled",
        name="Historic Environment Scotland",
        type="manual",
        format="geojson",
        url="",
        enabled=True,
    )

    summaries = normalise_sources(
        sources=[source],
        raw_root=tmp_path / "raw",
        output_root=tmp_path / "normalized",
    )

    assert summaries[0].skipped_reason == "manual_source"
    assert not (tmp_path / "normalized" / "hes_scheduled.jsonl").exists()


def test_normalise_sources_continues_after_bad_record(tmp_path: Path) -> None:
    source = SourceDefinition(
        id="historic_england",
        name="Historic England",
        type="download",
        format="geojson",
        url="https://example.com/he.geojson",
        enabled=True,
        filename="historic_england.geojson",
    )
    raw_file = tmp_path / "raw" / source.id / "2026-03-08" / source.filename
    _write_historic_england_geojson(raw_file, include_bad_record=True)
    _write_metadata(raw_file, source=source)

    summaries = normalise_sources(
        sources=[source],
        raw_root=tmp_path / "raw",
        output_root=tmp_path / "normalized",
    )

    assert summaries[0].records_read == 2
    assert summaries[0].records_written == 1
    assert summaries[0].records_failed == 1
    assert len((tmp_path / "normalized" / "historic_england.jsonl").read_text(encoding="utf-8").splitlines()) == 1
