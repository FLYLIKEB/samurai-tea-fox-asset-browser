"""File operations used by the asset browser."""

from __future__ import annotations

from pathlib import Path
import shutil


def unique_destination_path(destination_dir: Path, filename: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    candidate = destination_dir / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = destination_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def move_files_to_directory(paths: list[Path], destination_dir: Path) -> tuple[list[Path], list[str]]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    failures: list[str] = []

    for source in paths:
        try:
            source = source.resolve()
            target_dir = destination_dir.resolve()
            if source.parent == target_dir:
                moved.append(source)
                continue
            target = unique_destination_path(target_dir, source.name)
            shutil.move(str(source), str(target))
            moved.append(target)
        except Exception as exc:
            failures.append(f"{source}: {exc}")

    return moved, failures
