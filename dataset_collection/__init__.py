from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE_PATH = Path(__file__).resolve().parent.parent / "src" / "dataset_collection"
if str(_SRC_PACKAGE_PATH) not in __path__:
    __path__.append(str(_SRC_PACKAGE_PATH))
