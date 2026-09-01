"""Path helpers for asset browser files and generated backups."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .constants import PROMPT_TEMPLATE_FILE

def project_root_from_script() -> Path:
    return Path.cwd().resolve()

def bundled_template_path() -> Path:
    return Path(__file__).resolve().with_name(PROMPT_TEMPLATE_FILE)

def template_path(project_root: Path | None = None) -> Path:
    if project_root is None:
        return bundled_template_path()
    return project_root / "tools" / "asset_browser" / PROMPT_TEMPLATE_FILE

def palette_backup_root(project_root: Path | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if project_root is None:
        return Path.cwd().resolve() / "tools" / "asset_browser" / "palette_backups" / stamp
    return project_root / "tools" / "asset_browser" / "palette_backups" / stamp

def relative_or_name(path: Path, project_root: Path) -> Path:
    try:
        return path.relative_to(project_root)
    except ValueError:
        return Path(path.name)
