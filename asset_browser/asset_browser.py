#!/usr/bin/env python3
"""Compatibility wrapper for the modular asset browser package."""

from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    tool_root = Path(__file__).resolve().parents[1]
    if str(tool_root) not in sys.path:
        sys.path.insert(0, str(tool_root))

from asset_browser.cli import main, parse_args
from asset_browser.constants import (
    ART_STYLE_TOKENS_PATH,
    BG,
    BORDER,
    BUILTIN_PROMPT_TEMPLATE,
    ERROR,
    IMAGE_EXTENSIONS,
    MUTED,
    PANEL,
    PROMPT_TEMPLATE_FILE,
    RESIZE_CHOICES,
    SCALE_CHOICES,
    SELECTED,
    SELECTED_TEXT,
    TEXT,
)
from asset_browser.image_ops import (
    Image,
    ImageTk,
    apply_palette_to_images,
    apply_transparency_to_images,
    color_within_tolerance,
    crop_image_to_file,
    crop_boxes_to_files,
    default_crop_output_path,
    default_resize_output_path,
    image_size,
    is_larger_than_tile,
    nearest_palette_color,
    normalize_crop_box,
    parse_image_size,
    make_color_transparent,
    recolor_image_to_palette,
    resize_image_to_file,
    save_color_transparent_image,
    save_recolored_image,
)
from asset_browser.models import AssetImage
from asset_browser.paths import (
    palette_backup_root,
    project_root_from_script,
    relative_or_name,
    template_path,
)
from asset_browser.prompting import (
    codex_prompt_for,
    load_prompt_template,
    render_prompt_template,
    save_prompt_template,
)
from asset_browser.scanner import find_images, folder_group_label, group_images_by_folder
from asset_browser.style_tokens import (
    extract_palette_colors,
    format_art_style_tokens,
    hex_to_rgb,
    load_art_style_tokens,
    normalize_hex_color,
    save_art_style_tokens,
)
from asset_browser.ui_app import AssetBrowser
from asset_browser.ui_layout import wheel_scroll_units

__all__ = [
    "ART_STYLE_TOKENS_PATH",
    "AssetBrowser",
    "AssetImage",
    "BG",
    "BORDER",
    "BUILTIN_PROMPT_TEMPLATE",
    "ERROR",
    "IMAGE_EXTENSIONS",
    "Image",
    "ImageTk",
    "MUTED",
    "PANEL",
    "PROMPT_TEMPLATE_FILE",
    "RESIZE_CHOICES",
    "SCALE_CHOICES",
    "SELECTED",
    "SELECTED_TEXT",
    "TEXT",
    "apply_palette_to_images",
    "apply_transparency_to_images",
    "codex_prompt_for",
    "color_within_tolerance",
    "crop_boxes_to_files",
    "crop_image_to_file",
    "default_crop_output_path",
    "default_resize_output_path",
    "extract_palette_colors",
    "find_images",
    "folder_group_label",
    "format_art_style_tokens",
    "group_images_by_folder",
    "hex_to_rgb",
    "image_size",
    "is_larger_than_tile",
    "load_art_style_tokens",
    "load_prompt_template",
    "main",
    "make_color_transparent",
    "nearest_palette_color",
    "normalize_crop_box",
    "normalize_hex_color",
    "palette_backup_root",
    "parse_image_size",
    "parse_args",
    "project_root_from_script",
    "recolor_image_to_palette",
    "relative_or_name",
    "render_prompt_template",
    "resize_image_to_file",
    "save_color_transparent_image",
    "save_art_style_tokens",
    "save_prompt_template",
    "save_recolored_image",
    "template_path",
    "wheel_scroll_units",
]

if __name__ == "__main__":
    raise SystemExit(main())
