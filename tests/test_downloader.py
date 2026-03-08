from pathlib import Path

import httpx

from dataset_collection.downloader import collect_sources
from dataset_collection.models import SourceDefinition


def test_downloader_writes_file_and_metadata(tmp_path: Path) -> None:
    source = SourceDefinition(
        id="historic_england",
        name="Historic England",
        type="download",
        format="zip",
        url="https://example.com/data.zip",
        enabled=True,
        filename="scheduled-monuments.zip",
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code=200,
            headers={"content-type": "application/zip"},
            content=b"zip-bytes",
            request=request,
        )
    )

    results = collect_sources(
        sources=[source],
        output_root=tmp_path / "raw",
        force=False,
        today="2026-03-08",
        client=httpx.Client(transport=transport),
    )

    assert len(results) == 1
    result = results[0]
    assert result.success is True
    assert result.http_status == 200
    assert Path(result.output_file).read_bytes() == b"zip-bytes"
    metadata_path = Path(result.output_file).with_suffix(".metadata.json")
    assert metadata_path.exists()


def test_downloader_handles_failed_request_without_crashing_whole_run(tmp_path: Path) -> None:
    sources = [
        SourceDefinition(
            id="historic_england",
            name="Historic England",
            type="download",
            format="zip",
            url="https://example.com/data.zip",
            enabled=True,
            filename="scheduled-monuments.zip",
        ),
        SourceDefinition(
            id="cadw",
            name="Cadw",
            type="download",
            format="geojson",
            url="https://example.com/cadw.geojson",
            enabled=True,
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if "cadw" in str(request.url):
            raise httpx.ConnectError("network down", request=request)
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/zip"},
            content=b"zip-bytes",
            request=request,
        )

    results = collect_sources(
        sources=sources,
        output_root=tmp_path / "raw",
        force=False,
        today="2026-03-08",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert "network down" in (results[1].error_message or "")
