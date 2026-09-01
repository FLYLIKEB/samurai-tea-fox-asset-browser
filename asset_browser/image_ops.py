"""Pillow-backed palette preview, conversion, and crop helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from .paths import relative_or_name

try:
    from PIL import Image, ImageEnhance, ImageTk
except ImportError:  # Pillow is optional; Tk can still load PNG/GIF/PPM/PGM.
    Image = None
    ImageEnhance = None
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

def crop_boxes_to_files(source: Path, boxes: list[tuple[int, int, int, int]]) -> list[Path]:
    saved_paths: list[Path] = []
    for box in boxes:
        target = default_crop_output_path(source, box)
        crop_image_to_file(source, target, box)
        saved_paths.append(target)
    return saved_paths

def parse_image_size(value: str) -> tuple[int, int]:
    normalized = value.lower().replace(" ", "")
    width_text, separator, height_text = normalized.partition("x")
    if separator != "x":
        raise ValueError(f"잘못된 크기 형식: {value}")

    width = int(width_text)
    height = int(height_text)
    if width <= 0 or height <= 0:
        raise ValueError(f"크기는 1 이상이어야 합니다: {value}")
    return width, height

def default_resize_output_path(source: Path, size: tuple[int, int]) -> Path:
    width, height = size
    candidate = source.with_name(f"{source.stem}_resize_{width}x{height}.png")
    index = 2
    while candidate.exists():
        candidate = source.with_name(f"{source.stem}_resize_{width}x{height}_{index}.png")
        index += 1
    return candidate

def resize_image_to_file(source: Path, target: Path, size: tuple[int, int]) -> None:
    if Image is None:
        raise RuntimeError("이미지 리사이즈에는 Pillow가 필요합니다.")

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        resampling = getattr(Image, "Resampling", Image)
        resized = opened.convert("RGBA").resize(size, resampling.NEAREST)
        resized.save(target)

def adjustment_factor(percent: int) -> float:
    return max(0.0, 1.0 + max(-100, min(300, percent)) / 100)

def adjust_image(image, kind: str, percent: int):
    if Image is None or ImageEnhance is None:
        raise RuntimeError("이미지 보정에는 Pillow가 필요합니다.")

    enhancer_by_kind = {
        "대비": ImageEnhance.Contrast,
        "contrast": ImageEnhance.Contrast,
        "밝기": ImageEnhance.Brightness,
        "brightness": ImageEnhance.Brightness,
        "채도": ImageEnhance.Color,
        "saturation": ImageEnhance.Color,
        "선명도": ImageEnhance.Sharpness,
        "sharpness": ImageEnhance.Sharpness,
    }
    enhancer_class = enhancer_by_kind.get(kind)
    if enhancer_class is None:
        raise ValueError(f"지원하지 않는 보정입니다: {kind}")

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    adjusted = enhancer_class(rgba.convert("RGB")).enhance(adjustment_factor(percent))
    adjusted = adjusted.convert("RGBA")
    adjusted.putalpha(alpha)
    return adjusted

def save_adjusted_image(path: Path, kind: str, percent: int) -> None:
    if Image is None:
        raise RuntimeError("이미지 보정에는 Pillow가 필요합니다.")

    with Image.open(path) as opened:
        adjusted = adjust_image(opened, kind, percent)
        save_rgba_image_to_file(adjusted, path)

def color_within_tolerance(
    pixel_rgb: tuple[int, int, int],
    target_rgb: tuple[int, int, int],
    tolerance: int,
) -> bool:
    return all(abs(pixel_rgb[index] - target_rgb[index]) <= tolerance for index in range(3))

def make_color_transparent(image, rgb: tuple[int, int, int], tolerance: int = 0):
    image = image.convert("RGBA")
    tolerance = max(0, min(255, tolerance))
    transparent = []
    for red, green, blue, alpha in image.getdata():
        if alpha > 0 and color_within_tolerance((red, green, blue), rgb, tolerance):
            transparent.append((red, green, blue, 0))
        else:
            transparent.append((red, green, blue, alpha))

    converted = Image.new("RGBA", image.size)
    converted.putdata(transparent)
    return converted


def make_edge_connected_color_transparent(
    image,
    rgb: tuple[int, int, int],
    tolerance: int = 0,
):
    image = image.convert("RGBA")
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    pixels = image.load()
    tolerance = max(0, min(255, tolerance))

    def matches(x: int, y: int) -> bool:
        red, green, blue, alpha = pixels[x, y]
        return alpha > 0 and color_within_tolerance((red, green, blue), rgb, tolerance)

    stack: list[tuple[int, int]] = []
    for x in range(width):
        if matches(x, 0):
            stack.append((x, 0))
        if height > 1 and matches(x, height - 1):
            stack.append((x, height - 1))
    for y in range(1, height - 1):
        if matches(0, y):
            stack.append((0, y))
        if width > 1 and matches(width - 1, y):
            stack.append((width - 1, y))

    visited: set[tuple[int, int]] = set()
    while stack:
        current_x, current_y = stack.pop()
        if (current_x, current_y) in visited:
            continue
        visited.add((current_x, current_y))
        if current_x < 0 or current_y < 0 or current_x >= width or current_y >= height:
            continue
        if not matches(current_x, current_y):
            continue
        red, green, blue, _alpha = pixels[current_x, current_y]
        pixels[current_x, current_y] = (red, green, blue, 0)
        stack.extend(
            (
                (current_x + 1, current_y),
                (current_x - 1, current_y),
                (current_x, current_y + 1),
                (current_x, current_y - 1),
            )
        )

    return image

def flood_fill_image(
    image,
    point: tuple[int, int],
    rgb: tuple[int, int, int],
    tolerance: int = 0,
):
    image = image.convert("RGBA")
    width, height = image.size
    x, y = point
    if x < 0 or y < 0 or x >= width or y >= height:
        return image, 0

    pixels = image.load()
    target = pixels[x, y]
    replacement = (rgb[0], rgb[1], rgb[2], 255)
    tolerance = max(0, min(255, tolerance))
    if target == replacement:
        return image, 0

    def matches(pixel) -> bool:
        if target[3] == 0:
            return pixel[3] == 0
        return pixel[3] > 0 and color_within_tolerance(pixel[:3], target[:3], tolerance)

    changed = 0
    stack = [(x, y)]
    visited: set[tuple[int, int]] = set()
    while stack:
        current_x, current_y = stack.pop()
        if (current_x, current_y) in visited:
            continue
        visited.add((current_x, current_y))
        if current_x < 0 or current_y < 0 or current_x >= width or current_y >= height:
            continue
        if not matches(pixels[current_x, current_y]):
            continue
        pixels[current_x, current_y] = replacement
        changed += 1
        stack.extend(
            (
                (current_x + 1, current_y),
                (current_x - 1, current_y),
                (current_x, current_y + 1),
                (current_x, current_y - 1),
            )
        )

    return image, changed

def save_rgba_image_to_file(image, path: Path) -> None:
    target = image.convert("RGBA")
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        target = target.convert("RGB")
    target.save(path)

def save_color_transparent_image(path: Path, rgb: tuple[int, int, int], tolerance: int = 0) -> None:
    if Image is None:
        raise RuntimeError("배경 투명화에는 Pillow가 필요합니다.")

    with Image.open(path) as opened:
        converted = make_color_transparent(opened, rgb, tolerance)
        converted.save(path)


def save_edge_connected_color_transparent_image(
    path: Path,
    rgb: tuple[int, int, int],
    tolerance: int = 0,
) -> None:
    if Image is None:
        raise RuntimeError("배경 투명화에는 Pillow가 필요합니다.")

    with Image.open(path) as opened:
        converted = make_edge_connected_color_transparent(opened, rgb, tolerance)
        converted.save(path)

def apply_transparency_to_images(
    image_paths: list[Path],
    rgb: tuple[int, int, int],
    project_root: Path,
    backup_root: Path,
    tolerance: int = 0,
    edge_only: bool = False,
) -> tuple[int, list[str]]:
    converted = 0
    failures: list[str] = []

    for path in image_paths:
        try:
            backup_path = backup_root / relative_or_name(path, project_root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            if edge_only:
                save_edge_connected_color_transparent_image(path, rgb, tolerance)
            else:
                save_color_transparent_image(path, rgb, tolerance)
            converted += 1
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    return converted, failures

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

def apply_adjustment_to_images(
    image_paths: list[Path],
    kind: str,
    percent: int,
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
            save_adjusted_image(path, kind, percent)
            converted += 1
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    return converted, failures
