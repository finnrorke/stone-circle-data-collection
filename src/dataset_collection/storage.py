from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx

from dataset_collection.models import SourceDefinition


_GENERIC_URL_NAMES = {"", "download", "query", "wfs", "api"}
_FORMAT_SUFFIXES = {
    "zip": ".zip",
    "geojson": ".geojson",
    "json": ".json",
    "csv": ".csv",
    "xml": ".xml",
    "gml": ".gml",
    "html": ".html",
}
_CONTENT_TYPE_SUFFIXES = {
    "application/geo+json": ".geojson",
    "application/json": ".json",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "application/gml+xml": ".gml",
}


def build_output_path(output_root: Path, source: SourceDefinition, collection_date: date) -> Path:
    return output_root / source.id / collection_date.isoformat() / infer_filename(source)


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def infer_filename(source: SourceDefinition, response: httpx.Response | None = None) -> str:
    if source.filename:
        return sanitize_filename(source.filename)

    url_name = sanitize_filename(Path(urlparse(source.url).path).name)
    if url_name and url_name.lower() not in _GENERIC_URL_NAMES:
        return url_name

    suffix = ""
    if response is not None:
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        suffix = _CONTENT_TYPE_SUFFIXES.get(content_type, "")
        if not suffix:
            guessed = mimetypes.guess_extension(content_type)
            suffix = guessed or ""

    if not suffix:
        suffix = _FORMAT_SUFFIXES.get(source.format, "")

    return f"raw_download{suffix}"


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned or "raw_download"


def metadata_path_for(output_path: Path) -> Path:
    return output_path.with_suffix(".metadata.json")


def write_bytes(path: Path, content: bytes) -> tuple[int, str]:
    ensure_parent_directory(path)
    path.write_bytes(content)
    return len(content), hashlib.sha256(content).hexdigest()


def write_metadata(path: Path, payload: dict[str, object]) -> None:
    ensure_parent_directory(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
