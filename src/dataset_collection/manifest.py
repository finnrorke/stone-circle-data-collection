from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from dataset_collection.models import SourceDefinition


_SOURCES_ADAPTER = TypeAdapter(list[SourceDefinition])


def load_sources(path: Path) -> list[SourceDefinition]:
    try:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
        sources = _SOURCES_ADAPTER.validate_python(raw_payload)
    except FileNotFoundError as exc:
        raise ValueError(f"Manifest file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in manifest: {exc}") from exc
    except ValidationError as exc:
        raise ValueError(f"Invalid source manifest: {exc}") from exc

    seen_ids: set[str] = set()
    for source in sources:
        if source.id in seen_ids:
            raise ValueError(f"Duplicate source id found: {source.id}")
        seen_ids.add(source.id)

    return sources
