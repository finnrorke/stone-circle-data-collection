from pathlib import Path

import pytest

from dataset_collection.manifest import load_sources


def write_sources(tmp_path: Path, payload: str) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(payload, encoding="utf-8")
    return path


def test_valid_manifest_loads_successfully(tmp_path: Path) -> None:
    path = write_sources(
        tmp_path,
        """
        [
          {
            "id": "historic_england",
            "name": "Historic England",
            "type": "download",
            "format": "zip",
            "url": "https://example.com/data.zip",
            "enabled": true
          },
          {
            "id": "archwilio",
            "name": "Archwilio",
            "type": "manual",
            "format": "html",
            "url": "",
            "enabled": false
          }
        ]
        """.strip(),
    )

    sources = load_sources(path)

    assert [source.id for source in sources] == ["historic_england", "archwilio"]


def test_duplicate_source_ids_fail_validation(tmp_path: Path) -> None:
    path = write_sources(
        tmp_path,
        """
        [
          {
            "id": "duplicate",
            "name": "First",
            "type": "download",
            "format": "zip",
            "url": "https://example.com/first.zip",
            "enabled": true
          },
          {
            "id": "duplicate",
            "name": "Second",
            "type": "manual",
            "format": "html",
            "url": "",
            "enabled": false
          }
        ]
        """.strip(),
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_sources(path)


def test_enabled_non_manual_source_with_empty_url_fails_validation(tmp_path: Path) -> None:
    path = write_sources(
        tmp_path,
        """
        [
          {
            "id": "historic_england",
            "name": "Historic England",
            "type": "download",
            "format": "zip",
            "url": "",
            "enabled": true
          }
        ]
        """.strip(),
    )

    with pytest.raises(ValueError, match="url"):
        load_sources(path)


def test_manual_source_with_empty_url_is_allowed(tmp_path: Path) -> None:
    path = write_sources(
        tmp_path,
        """
        [
          {
            "id": "heritage_gateway",
            "name": "Heritage Gateway",
            "type": "manual",
            "format": "html",
            "url": "",
            "enabled": false
          }
        ]
        """.strip(),
    )

    sources = load_sources(path)

    assert sources[0].url == ""
