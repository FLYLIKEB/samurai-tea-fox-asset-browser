"""Pillow-backed palette preview and destructive image conversion."""

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
