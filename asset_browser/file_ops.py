"""File operations used by the asset browser."""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import tempfile


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


def replace_file_with_and_delete_source(target: Path, source: Path) -> None:
    """Atomically replace ``target`` contents with ``source``, then delete ``source``.

    The target name (and therefore its Godot resource path) is deliberately kept.
    Requiring equal suffixes prevents copying, for example, JPEG bytes into a PNG path.
    """
    target = target.resolve()
    source = source.resolve()
    if target == source:
        raise ValueError("교체 대상과 원본 파일은 서로 달라야 합니다.")
    if not target.is_file():
        raise FileNotFoundError(f"교체 대상 파일을 찾을 수 없습니다: {target}")
    if not source.is_file():
        raise FileNotFoundError(f"교체 원본 파일을 찾을 수 없습니다: {source}")
    if target.suffix.lower() != source.suffix.lower():
        raise ValueError("교체 대상과 원본의 파일 확장자가 같아야 합니다.")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.replace-",
        suffix=target.suffix,
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file, source.open("rb") as source_file:
            shutil.copyfileobj(source_file, temporary_file)
        shutil.copystat(source, temporary_path)
        os.replace(temporary_path, target)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    source.unlink()
