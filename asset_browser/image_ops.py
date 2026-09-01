"""Pillow-backed palette preview, conversion, and crop helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from .paths import relative_or_name

try:
    from PIL import Image, ImageTk
except ImportError:  # Pillow is optional; Tk can still load PNG/GIF/PPM/PGM.
    Image = None
    ImageTk = None

def nearest_palette_color(
    rgb: tuple[int, int, int],
    palette: list[tuple[int, int, int]],
) -> tuple[int, int, int]:
    red, green, blue = rgb
    return min(
        palette,
        key=lambda color: (
            (red - color[0]) * (red - color[0])
            + (green - color[1]) * (green - color[1])
            + (blue - color[2]) * (blue - color[2])
        ),
    )

def recolor_image_to_palette(image, palette: list[tuple[int, int, int]]):
    if not palette:
        return image

    image = image.convert("RGBA")
    remapped = []
    for red, green, blue, alpha in image.getdata():
        if alpha == 0:
            remapped.append((red, green, blue, alpha))
            continue
        mapped = nearest_palette_color((red, green, blue), palette)
        remapped.append((mapped[0], mapped[1], mapped[2], alpha))

    recolored = Image.new("RGBA", image.size)
    recolored.putdata(remapped)
    return recolored

def save_recolored_image(path: Path, palette: list[tuple[int, int, int]]) -> None:
    if Image is None:
        raise RuntimeError("Pillow가 설치되어 있지 않습니다.")

    with Image.open(path) as opened:
        recolored = recolor_image_to_palette(opened, palette)
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            recolored = recolored.convert("RGB")
        recolored.save(path)

def image_size(path: Path) -> tuple[int, int]:
    if Image is not None:
        with Image.open(path) as opened:
            return opened.size

    raise RuntimeError("이미지 크기를 읽으려면 Pillow가 필요합니다.")

def is_larger_than_tile(path: Path, tile_size: int = 32) -> bool:
    width, height = image_size(path)
    return width > tile_size or height > tile_size

def normalize_crop_box(
    start: tuple[int, int],
    end: tuple[int, int],
    image_size_value: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    width, height = image_size_value
    x1 = max(0, min(start[0], end[0], width))
    y1 = max(0, min(start[1], end[1], height))
    x2 = max(0, min(max(start[0], end[0]), width))
    y2 = max(0, min(max(start[1], end[1]), height))

    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2

def default_crop_output_path(source: Path, box: tuple[int, int, int, int]) -> Path:
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    candidate = source.with_name(f"{source.stem}_crop_{x1}_{y1}_{width}x{height}.png")
    index = 2
    while candidate.exists():
        candidate = source.with_name(
            f"{source.stem}_crop_{x1}_{y1}_{width}x{height}_{index}.png"
        )
        index += 1
    return candidate

def crop_image_to_file(source: Path, target: Path, box: tuple[int, int, int, int]) -> None:
    if Image is None:
        raise RuntimeError("이미지 크롭에는 Pillow가 필요합니다.")

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        cropped = opened.convert("RGBA").crop(box)
        if target.suffix.lower() in {".jpg", ".jpeg"}:
            cropped = cropped.convert("RGB")
        cropped.save(target)

def apply_palette_to_images(
    image_paths: list[Path],
    palette: list[tuple[int, int, int]],
    project_root: Path,
    backup_root: Path,
) -> tuple[int, list[str]]:
    converted = 0
    failures: list[str] = []

    for path in image_paths:
        try:
            backup_path = backup_root / relative_or_name(path, project_root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            save_recolored_image(path, palette)
            converted += 1
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    return converted, failures
