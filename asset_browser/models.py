"""Small data models used by the asset browser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class AssetImage:
    path: Path
    relative_path: Path
