"""Tile-size grouping and preview sizing rules."""

from __future__ import annotations

BASE_TILE_SIZE = 32
PREVIEW_SCALE = 2
SUMMARY_THRESHOLD = 64
STRIP_SUMMARY_THRESHOLD = 128
SUMMARY_PREVIEW_SIZE = (104, 64)


def is_summary_size(width: int, height: int) -> bool:
    return is_large_sheet_size(width, height) or is_long_strip_size(width, height)


def is_large_sheet_size(width: int, height: int) -> bool:
    return width >= SUMMARY_THRESHOLD and height >= SUMMARY_THRESHOLD


def is_long_strip_size(width: int, height: int) -> bool:
    return max(width, height) >= STRIP_SUMMARY_THRESHOLD


def tile_size_group_label(size: tuple[int, int] | None) -> str:
    if size is None:
        return "크기 확인 불가"

    width, height = size
    if is_large_sheet_size(width, height):
        return "대형/시트 (64x64 이상)"
    if is_long_strip_size(width, height):
        return "긴 시트 (128px 이상)"
    if width % BASE_TILE_SIZE == 0 and height % BASE_TILE_SIZE == 0:
        return f"{width}x{height}"
    return f"기타 {width}x{height}"


def tile_size_sort_key(size: tuple[int, int] | None) -> tuple[int, int, int]:
    if size is None:
        return 99, 0, 0

    width, height = size
    if is_summary_size(width, height):
        return 50, width * height, max(width, height)
    if width % BASE_TILE_SIZE == 0 and height % BASE_TILE_SIZE == 0:
        return 0, height // BASE_TILE_SIZE, width // BASE_TILE_SIZE
    return 10, height, width


def preview_size_for_image(size: tuple[int, int] | None, scale: int) -> tuple[int, int]:
    if size is None:
        return SUMMARY_PREVIEW_SIZE

    width, height = size
    if is_summary_size(width, height):
        return SUMMARY_PREVIEW_SIZE

    scale = max(1, scale)
    return max(1, width * scale), max(1, height * scale)


def cell_size_for_preview(preview_size: tuple[int, int]) -> tuple[int, int]:
    width, height = preview_size
    return max(132, width + 4), max(98, height + 34)
