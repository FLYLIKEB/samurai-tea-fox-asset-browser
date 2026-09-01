"""Shared constants for the local asset browser."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = {
    ".png",
    ".gif",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".tga",
    ".tif",
    ".tiff",
    ".ppm",
    ".pgm",
}

SCALE_CHOICES = (2, 3, 4, 5, 6, 8)
GRID_CELL_PITCH = 140
GRID_CELL_WIDTH = 132
GRID_CELL_HEIGHT = 162
THUMBNAIL_BOX_SIZE = 128

BG = "#f5f5f7"
PANEL = "#ffffff"
TEXT = "#1d1d1f"
MUTED = "#86868b"
SELECTED = "#2f6f73"
SELECTED_TEXT = "#ffffff"
BORDER = "#d2d2d7"
ERROR = "#8c3f38"

PROMPT_TEMPLATE_FILE = "default_prompt_template.txt"
ART_STYLE_TOKENS_PATH = Path("assets/style/art-style-tokens.json")
BUILTIN_PROMPT_TEMPLATE = """아래 로컬 게임 에셋 이미지들을 한 번에 확인하고 수정해줘.

먼저 assets/style/art-style-tokens.json을 읽고, 그 파일의 팔레트/공통 시각 컨셉/ImageGen positive·negative 토큰을 기준으로 작업해.
색상 팔레트와 시각 제약은 다른 곳에 새로 복제하지 말고 해당 JSON을 단일 정본으로 유지해.
이 게임은 정사각형 타일 기반 탑뷰 로그라이크이므로 모든 캐릭터, 맵, 맵 내 사물은 정면을 보게 만들고 측면·후면·3/4·아이소메트릭 시점은 피해야 해.

이미지:
{asset_list}
"""
