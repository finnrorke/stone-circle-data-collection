from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NormalizationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetched_at: str | None = None
    source_metadata_file: str | None = None
    parser_name: str
    parser_version: str
    normalization_timestamp: str
    raw_source_fields: dict[str, Any] = Field(default_factory=dict)


class NormalizedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    source_record_id: str | None = None
    source_dataset: str | None = None
    source_url: str | None = None
    raw_file_path: str
    raw_record_index: int | None = None

    canonical_name: str | None = None
    alternate_names: list[str] = Field(default_factory=list)
    nation: str | None = None
    county_or_region: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    geometry_type: str | None = None
    geometry_wkt: str | None = None

    site_types: list[str] = Field(default_factory=list)
    primary_type: str | None = None
    period: str | None = None
    designation_status: str | None = None
    grid_reference: str | None = None

    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    raw_name: str | None = None
    raw_type: str | None = None
    raw_subtype: str | None = None
    raw_description: str | None = None

    provenance: NormalizationProvenance


class SourceNormalizationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    records_read: int = 0
    records_written: int = 0
    records_failed: int = 0
    output_file: str | None = None
    skipped_reason: str | None = None


class RawFileSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_file_path: Path
    metadata_path: Path | None = None
    fetched_at: str | None = None
