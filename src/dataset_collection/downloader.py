from __future__ import annotations

import json
import logging
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from dataset_collection.models import DownloadMetadata, SourceDefinition
from dataset_collection.storage import build_output_path, metadata_path_for, write_bytes, write_metadata

logger = logging.getLogger(__name__)
_EXPORTING_STATUSES = {"exportingdata", "preparingdata", "creatingexport", "processing"}


def collect_sources(
    sources: list[SourceDefinition],
    output_root: Path,
    force: bool = False,
    today: date | str | None = None,
    client: httpx.Client | None = None,
) -> list[DownloadMetadata]:
    collection_date = _normalize_collection_date(today)
    own_client = client is None
    http_client = client or httpx.Client(follow_redirects=True)

    try:
        results: list[DownloadMetadata] = []
        for source in sources:
            if not source.enabled:
                logger.info("Skipping disabled source '%s'", source.id)
                continue

            if source.type == "manual":
                logger.info("Skipping manual source '%s'", source.id)
                continue

            results.append(
                _collect_single_source(
                    source=source,
                    output_root=output_root,
                    collection_date=collection_date,
                    force=force,
                    client=http_client,
                )
            )

        return results
    finally:
        if own_client:
            http_client.close()


def _collect_single_source(
    source: SourceDefinition,
    output_root: Path,
    collection_date: date,
    force: bool,
    client: httpx.Client,
) -> DownloadMetadata:
    output_path = build_output_path(output_root=output_root, source=source, collection_date=collection_date)
    metadata_path = metadata_path_for(output_path)

    if output_path.exists() and not force:
        logger.info("Skipping existing download for '%s': %s", source.id, output_path)
        result = DownloadMetadata(
            source_id=source.id,
            source_name=source.name,
            url=source.url,
            request_method=source.method,
            fetched_at=_timestamp(),
            http_status=None,
            content_type=None,
            output_file=str(output_path),
            file_size=output_path.stat().st_size,
            sha256=None,
            success=True,
            error_message="Skipped existing download for the current day",
        )
        if not metadata_path.exists():
            write_metadata(metadata_path, result.model_dump(mode="json"))
        return result

    try:
        response = _request_with_retries(client=client, source=source)
    except httpx.HTTPError as exc:
        logger.exception("Request failed for '%s'", source.id)
        result = DownloadMetadata(
            source_id=source.id,
            source_name=source.name,
            url=source.url,
            request_method=source.method,
            fetched_at=_timestamp(),
            http_status=None,
            content_type=None,
            output_file=str(output_path),
            file_size=0,
            sha256=None,
            success=False,
            error_message=str(exc),
        )
        write_metadata(metadata_path, result.model_dump(mode="json"))
        return result

    content_type = response.headers.get("content-type")
    if not response.is_success:
        logger.error("Download failed for '%s' with status %s", source.id, response.status_code)
        result = DownloadMetadata(
            source_id=source.id,
            source_name=source.name,
            url=source.url,
            request_method=source.method,
            fetched_at=_timestamp(),
            http_status=response.status_code,
            content_type=content_type,
            output_file=str(output_path),
            file_size=0,
            sha256=None,
            success=False,
            error_message=f"HTTP {response.status_code}",
        )
        write_metadata(metadata_path, result.model_dump(mode="json"))
        return result

    content_error = _detect_content_error(source=source, response=response)
    if content_error is not None:
        logger.error("Download failed validation for '%s': %s", source.id, content_error)
        result = DownloadMetadata(
            source_id=source.id,
            source_name=source.name,
            url=source.url,
            request_method=source.method,
            fetched_at=_timestamp(),
            http_status=response.status_code,
            content_type=content_type,
            output_file=str(output_path),
            file_size=0,
            sha256=None,
            success=False,
            error_message=content_error,
        )
        write_metadata(metadata_path, result.model_dump(mode="json"))
        return result

    file_size, sha256 = write_bytes(output_path, response.content)
    result = DownloadMetadata(
        source_id=source.id,
        source_name=source.name,
        url=source.url,
        request_method=source.method,
        fetched_at=_timestamp(),
        http_status=response.status_code,
        content_type=content_type,
        output_file=str(output_path),
        file_size=file_size,
        sha256=sha256,
        success=True,
        error_message=None,
    )
    write_metadata(metadata_path, result.model_dump(mode="json"))
    logger.info("Collected '%s' to %s", source.id, output_path)
    return result


def _normalize_collection_date(value: date | str | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _request_with_retries(client: httpx.Client, source: SourceDefinition) -> httpx.Response:
    deadline = time.monotonic() + max(source.timeout, 1)
    last_response: httpx.Response | None = None

    while True:
        response = client.request(
            method=source.method,
            url=source.url,
            headers=source.headers,
            params=source.params,
            timeout=source.timeout,
        )
        last_response = response

        if not _is_export_in_progress(response):
            return response

        if time.monotonic() + 1 > deadline:
            return response

        logger.info("Download still preparing for '%s'; retrying", source.id)
        time.sleep(1)

    return last_response  # pragma: no cover


def _is_export_in_progress(response: httpx.Response) -> bool:
    if response.status_code != 202:
        return False

    try:
        payload = response.json()
    except json.JSONDecodeError:
        return False

    status = str(payload.get("status", "")).strip().lower()
    return status in _EXPORTING_STATUSES


def _detect_content_error(source: SourceDefinition, response: httpx.Response) -> str | None:
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    content_prefix = response.content[:256].lstrip().lower()

    if source.format in {"geojson", "json"}:
        if b"<html" in content_prefix or b"<!doctype html" in content_prefix:
            return "Expected JSON content but received HTML"
    if source.format == "zip" and content_type == "text/html":
        return "Expected ZIP content but received HTML"

    return None
