from __future__ import annotations

import json
import logging
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dataset_collection.canonical_models import NormalizationProvenance, NormalizedRecord
from dataset_collection.models import SourceDefinition

logger = logging.getLogger(__name__)
PARSER_VERSION = "1.0.0"


@dataclass(slots=True)
class ParsedSourceResult:
    records: list[NormalizedRecord] = field(default_factory=list)
    records_read: int = 0
    records_failed: int = 0


ParserFunction = Callable[[SourceDefinition, Path, str | None, str | None], ParsedSourceResult]


def get_parser(source_id: str) -> ParserFunction | None:
    return _PARSERS.get(source_id)


def parse_historic_england(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
) -> ParsedSourceResult:
    payload = json.loads(raw_file_path.read_text(encoding="utf-8"))
    return _parse_geojson_features(
        source=source,
        payload=payload,
        raw_file_path=raw_file_path,
        fetched_at=fetched_at,
        metadata_path=metadata_path,
        nation="England",
        designation_status="Scheduled Monument",
        field_map={
            "record_id": ["ListEntry"],
            "name": ["Name"],
            "url": ["hyperlink"],
            "grid_reference": ["NGR"],
            "description": [],
            "raw_type": [],
            "raw_subtype": [],
            "period": [],
        },
        coordinate_field_map={"x": "Easting", "y": "Northing", "crs": "EPSG:27700"},
    )


def parse_cadw(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
) -> ParsedSourceResult:
    payload = json.loads(raw_file_path.read_text(encoding="utf-8"))
    return _parse_geojson_features(
        source=source,
        payload=payload,
        raw_file_path=raw_file_path,
        fetched_at=fetched_at,
        metadata_path=metadata_path,
        nation="Wales",
        designation_status="Scheduled Ancient Monument",
        field_map={
            "record_id": ["SAMNumber", "RecordNumber"],
            "name": ["Name"],
            "alternate_name": ["Name_cy"],
            "url": ["Report"],
            "county_or_region": ["UnitaryAuthority", "Community"],
            "grid_reference": [],
            "description": [],
            "raw_type": ["BroadClass"],
            "raw_subtype": ["SiteType"],
            "period": ["Period"],
        },
        coordinate_field_map={"x": "easting", "y": "northing", "crs": "EPSG:27700"},
    )


def parse_hes_scheduled(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
) -> ParsedSourceResult:
    payload = json.loads(raw_file_path.read_text(encoding="utf-8"))
    return _parse_geojson_features(
        source=source,
        payload=payload,
        raw_file_path=raw_file_path,
        fetched_at=fetched_at,
        metadata_path=metadata_path,
        nation="Scotland",
        designation_status="Scheduled Monument",
        field_map={
            "record_id": ["INDEX_NO", "HESPRINCNO", "OBJECTID"],
            "name": ["NAME", "Name", "SITE_NAME"],
            "alternate_name": ["GAELICNAME", "ALT_NAME"],
            "url": ["URL", "WEBSITE"],
            "county_or_region": ["COUNCIL", "ADMINAREA"],
            "grid_reference": ["NGR", "GRIDREF"],
            "description": ["DESCRIPTION", "DESCR"],
            "raw_type": ["TYPE_DESC", "TYPE", "CLASS"],
            "raw_subtype": ["SUBTYPE", "SUB_TYPE"],
            "period": ["PERIOD", "PERIOD_DESC"],
        },
        coordinate_field_map=None,
    )


def parse_nismr(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
) -> ParsedSourceResult:
    schema, geometry, columns = _read_zipped_shapefile(raw_file_path)
    result = ParsedSourceResult()

    for index, raw_record in _iter_shapefile_records(schema["fields"], columns):
        result.records_read += 1
        try:
            geom_wkt, geom_type, latitude, longitude = _geometry_from_wkb(
                geometry[index],
                source_crs=schema["crs"],
            )
            if latitude is None or longitude is None:
                latitude, longitude = _transform_xy(raw_record.get("X"), raw_record.get("Y"), schema["crs"])

            result.records.append(
                _build_record(
                    source=source,
                    raw_file_path=raw_file_path,
                    fetched_at=fetched_at,
                    metadata_path=metadata_path,
                    raw_record_index=index,
                    raw_source_fields=raw_record,
                    source_record_id=_string_or_none(raw_record.get("SMRNo")),
                    source_url=source.url or None,
                    canonical_name=_string_or_none(raw_record.get("Edited_Typ")),
                    nation="Northern Ireland",
                    county_or_region=_string_or_none(raw_record.get("Council")),
                    latitude=latitude,
                    longitude=longitude,
                    geometry_type=geom_type,
                    geometry_wkt=geom_wkt,
                    site_types=_list_without_empty(raw_record.get("General_Ty"), raw_record.get("Edited_Typ")),
                    primary_type=_string_or_none(raw_record.get("General_Ty")),
                    period=_string_or_none(raw_record.get("General_Pe")),
                    designation_status=_string_or_none(raw_record.get("Protection")),
                    grid_reference=_string_or_none(raw_record.get("Grid_Refer")),
                    description=None,
                    tags=_list_without_empty(raw_record.get("Located")),
                    raw_name=_string_or_none(raw_record.get("Edited_Typ")),
                    raw_type=_string_or_none(raw_record.get("General_Ty")),
                    raw_subtype=None,
                    raw_description=None,
                )
            )
        except Exception as exc:
            result.records_failed += 1
            logger.warning("Failed to normalise record %s from '%s': %s", index, source.id, exc)

    return result


def parse_ni_scheduled(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
) -> ParsedSourceResult:
    schema, geometry, columns = _read_zipped_shapefile(raw_file_path)
    result = ParsedSourceResult()

    for index, raw_record in _iter_shapefile_records(schema["fields"], columns):
        result.records_read += 1
        try:
            geom_wkt, geom_type, _, _ = _geometry_from_wkb(geometry[index], source_crs=schema["crs"])
            latitude, longitude = _transform_xy(
                raw_record.get("Centroid_X"),
                raw_record.get("Centroid_Y"),
                schema["crs"],
            )

            result.records.append(
                _build_record(
                    source=source,
                    raw_file_path=raw_file_path,
                    fetched_at=fetched_at,
                    metadata_path=metadata_path,
                    raw_record_index=index,
                    raw_source_fields=raw_record,
                    source_record_id=_string_or_none(raw_record.get("SMNO")),
                    source_url=source.url or None,
                    canonical_name=None,
                    nation="Northern Ireland",
                    county_or_region=_string_or_none(raw_record.get("COUNTY")),
                    latitude=latitude,
                    longitude=longitude,
                    geometry_type=geom_type,
                    geometry_wkt=geom_wkt,
                    site_types=_list_without_empty(raw_record.get("EDITED_TYP")),
                    primary_type=_string_or_none(raw_record.get("EDITED_TYP")),
                    period=None,
                    designation_status="Scheduled Historic Monument Area",
                    grid_reference=None,
                    description=None,
                    tags=[],
                    raw_name=None,
                    raw_type=_string_or_none(raw_record.get("EDITED_TYP")),
                    raw_subtype=None,
                    raw_description=None,
                )
            )
        except Exception as exc:
            result.records_failed += 1
            logger.warning("Failed to normalise record %s from '%s': %s", index, source.id, exc)

    return result


def _parse_geojson_features(
    source: SourceDefinition,
    payload: dict[str, Any],
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
    nation: str,
    designation_status: str | None,
    field_map: dict[str, list[str]],
    coordinate_field_map: dict[str, str] | None,
) -> ParsedSourceResult:
    result = ParsedSourceResult()
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise ValueError("Expected GeoJSON FeatureCollection with a features list")

    for index, feature in enumerate(features):
        result.records_read += 1
        try:
            if not isinstance(feature, dict):
                raise ValueError("Feature must be an object")

            properties = feature.get("properties")
            if not isinstance(properties, dict):
                raise ValueError("Feature properties must be an object")

            raw_source_fields = _json_ready_dict(properties)
            geometry = feature.get("geometry")
            geom_wkt, geom_type = _geometry_from_geojson(geometry)
            latitude, longitude = _point_from_geojson(geometry)
            if (latitude is None or longitude is None) and coordinate_field_map is not None:
                latitude, longitude = _transform_xy(
                    properties.get(coordinate_field_map["x"]),
                    properties.get(coordinate_field_map["y"]),
                    coordinate_field_map["crs"],
                )

            raw_type = _first_present(properties, field_map.get("raw_type", []))
            raw_subtype = _first_present(properties, field_map.get("raw_subtype", []))
            record_url = _first_present(properties, field_map.get("url", []))
            description = _first_present(properties, field_map.get("description", []))

            result.records.append(
                _build_record(
                    source=source,
                    raw_file_path=raw_file_path,
                    fetched_at=fetched_at,
                    metadata_path=metadata_path,
                    raw_record_index=index,
                    raw_source_fields=raw_source_fields,
                    source_record_id=_first_present(properties, field_map.get("record_id", [])),
                    source_url=record_url or source.url or None,
                    canonical_name=_first_present(properties, field_map.get("name", [])),
                    alternate_names=_list_without_empty(_first_present(properties, field_map.get("alternate_name", []))),
                    nation=nation,
                    county_or_region=_first_present(properties, field_map.get("county_or_region", [])),
                    latitude=latitude,
                    longitude=longitude,
                    geometry_type=geom_type,
                    geometry_wkt=geom_wkt,
                    site_types=_list_without_empty(raw_subtype, raw_type),
                    primary_type=raw_subtype or raw_type,
                    period=_first_present(properties, field_map.get("period", [])),
                    designation_status=designation_status,
                    grid_reference=_first_present(properties, field_map.get("grid_reference", [])),
                    description=description,
                    tags=[],
                    raw_name=_first_present(properties, field_map.get("name", [])),
                    raw_type=raw_type,
                    raw_subtype=raw_subtype,
                    raw_description=description,
                )
            )
        except Exception as exc:
            result.records_failed += 1
            logger.warning("Failed to normalise record %s from '%s': %s", index, source.id, exc)

    return result


def _build_record(
    source: SourceDefinition,
    raw_file_path: Path,
    fetched_at: str | None,
    metadata_path: str | None,
    raw_record_index: int | None,
    raw_source_fields: dict[str, Any],
    source_record_id: str | None,
    source_url: str | None,
    canonical_name: str | None,
    nation: str | None,
    county_or_region: str | None,
    latitude: float | None,
    longitude: float | None,
    geometry_type: str | None,
    geometry_wkt: str | None,
    site_types: list[str] | None = None,
    primary_type: str | None = None,
    period: str | None = None,
    designation_status: str | None = None,
    grid_reference: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    raw_name: str | None = None,
    raw_type: str | None = None,
    raw_subtype: str | None = None,
    raw_description: str | None = None,
    alternate_names: list[str] | None = None,
) -> NormalizedRecord:
    return NormalizedRecord(
        source_id=source.id,
        source_name=source.name,
        source_record_id=source_record_id,
        source_dataset=source.name,
        source_url=source_url,
        raw_file_path=str(raw_file_path),
        raw_record_index=raw_record_index,
        canonical_name=canonical_name,
        alternate_names=alternate_names or [],
        nation=nation,
        county_or_region=county_or_region,
        latitude=latitude,
        longitude=longitude,
        geometry_type=geometry_type,
        geometry_wkt=geometry_wkt,
        site_types=site_types or [],
        primary_type=primary_type,
        period=period,
        designation_status=designation_status,
        grid_reference=grid_reference,
        description=description,
        tags=tags or [],
        raw_name=raw_name,
        raw_type=raw_type,
        raw_subtype=raw_subtype,
        raw_description=raw_description,
        provenance=NormalizationProvenance(
            fetched_at=fetched_at,
            source_metadata_file=metadata_path,
            parser_name=source.id,
            parser_version=PARSER_VERSION,
            normalization_timestamp=datetime.now(UTC).isoformat(),
            raw_source_fields=raw_source_fields,
        ),
    )


def _read_zipped_shapefile(raw_file_path: Path) -> tuple[dict[str, Any], Any, list[Any]]:
    try:
        import pyogrio.raw
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyogrio is required to parse zipped shapefiles") from exc

    member = _find_zipped_member(raw_file_path, suffix=".shp")
    dataset_path = f"/vsizip/{raw_file_path.resolve()}/{member}"
    schema, _, geometry, columns = pyogrio.raw.read(dataset_path, read_geometry=True)
    return schema, geometry, columns


def _find_zipped_member(raw_file_path: Path, suffix: str) -> str:
    with zipfile.ZipFile(raw_file_path) as archive:
        for name in archive.namelist():
            if name.lower().endswith(suffix.lower()):
                return name
    raise ValueError(f"No {suffix} file found in {raw_file_path}")


def _iter_shapefile_records(fields: Any, columns: list[Any]) -> list[tuple[int, dict[str, Any]]]:
    field_names = [str(field) for field in fields]
    if not columns:
        return []
    row_count = len(columns[0])
    records: list[tuple[int, dict[str, Any]]] = []
    for index in range(row_count):
        record: dict[str, Any] = {}
        for column_index, field_name in enumerate(field_names):
            record[field_name] = _python_value(columns[column_index][index])
        records.append((index, record))
    return records


def _geometry_from_geojson(geometry: Any) -> tuple[str | None, str | None]:
    if geometry is None:
        return None, None

    try:
        from shapely.geometry import shape
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required to convert GeoJSON geometry to WKT") from exc

    shapely_geometry = shape(geometry)
    return shapely_geometry.wkt, shapely_geometry.geom_type


def _point_from_geojson(geometry: Any) -> tuple[float | None, float | None]:
    if not isinstance(geometry, dict):
        return None, None
    if geometry.get("type") != "Point":
        return None, None

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None

    longitude = _float_or_none(coordinates[0])
    latitude = _float_or_none(coordinates[1])
    return latitude, longitude


def _geometry_from_wkb(geometry_wkb: Any, source_crs: str | None) -> tuple[str | None, str | None, float | None, float | None]:
    if geometry_wkb is None:
        return None, None, None, None

    try:
        from shapely import from_wkb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required to convert WKB geometry to WKT") from exc

    geometry = from_wkb(geometry_wkb)
    latitude = None
    longitude = None
    if geometry.geom_type == "Point":
        latitude, longitude = _transform_xy(geometry.x, geometry.y, source_crs)

    return geometry.wkt, geometry.geom_type, latitude, longitude


def _transform_xy(x: Any, y: Any, source_crs: str | None) -> tuple[float | None, float | None]:
    x_value = _float_or_none(x)
    y_value = _float_or_none(y)
    if x_value is None or y_value is None:
        return None, None

    if source_crs in {None, "", "EPSG:4326"}:
        return y_value, x_value

    try:
        from pyproj import Transformer
    except ImportError:  # pragma: no cover
        return None, None

    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    longitude, latitude = transformer.transform(x_value, y_value)
    return latitude, longitude


def _first_present(properties: dict[str, Any], fields: list[str]) -> str | None:
    for field_name in fields:
        value = _string_or_none(properties.get(field_name))
        if value is not None:
            return value
    return None


def _list_without_empty(*values: Any) -> list[str]:
    items: list[str] = []
    for value in values:
        string_value = _string_or_none(value)
        if string_value is not None and string_value not in items:
            items.append(string_value)
    return items


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _python_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _json_ready_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _python_value(value) for key, value in payload.items()}


_PARSERS: dict[str, ParserFunction] = {
    "historic_england": parse_historic_england,
    "hes_scheduled": parse_hes_scheduled,
    "cadw": parse_cadw,
    "nismr": parse_nismr,
    "ni_scheduled": parse_ni_scheduled,
}
