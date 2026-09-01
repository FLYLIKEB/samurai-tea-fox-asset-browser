"""Art style token JSON loading, formatting, and palette extraction."""

from __future__ import annotations

import json
from pathlib import Path

from .constants import ART_STYLE_TOKENS_PATH

def load_art_style_tokens(project_root: Path) -> tuple[dict | None, str]:
    path = project_root / ART_STYLE_TOKENS_PATH
    if not path.exists():
        return None, f"스타일 토큰 파일이 없습니다: {ART_STYLE_TOKENS_PATH.as_posix()}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError as exc:
        return None, f"JSON 읽기 오류: {exc}"

def save_art_style_tokens(project_root: Path, data: dict) -> None:
    path = project_root / ART_STYLE_TOKENS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def normalize_hex_color(color: str) -> str:
    color = color.strip()
    if not color:
        return color
    if not color.startswith("#"):
        color = f"#{color}"
    if len(color) != 7:
        return color.upper()
    return color.upper()

def hex_to_rgb(color: str) -> tuple[int, int, int] | None:
    color = normalize_hex_color(color)
    if len(color) != 7 or not color.startswith("#"):
        return None
    try:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError:
        return None

def extract_palette_colors(data: dict | None) -> list[tuple[int, int, int]]:
    if data is None:
        return []

    colors: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    palette = data.get("palette", {})

    for entry in palette.get("global", []):
        rgb = hex_to_rgb(entry.get("hex", ""))
        if rgb is not None and rgb not in seen:
            colors.append(rgb)
            seen.add(rgb)

    for accent in palette.get("biome_accents", []):
        for hex_color in accent.get("colors", []):
            rgb = hex_to_rgb(hex_color)
            if rgb is not None and rgb not in seen:
                colors.append(rgb)
                seen.add(rgb)

    return colors

def format_art_style_tokens(data: dict | None, error: str) -> str:
    if data is None:
        return error

    lines: list[str] = []
    lines.append(f"제목: {data.get('title', '(제목 없음)')}")
    lines.append(f"ID: {data.get('id', '(id 없음)')}")
    lines.append("")

    management_rule = data.get("management_rule", {})
    if management_rule:
        lines.append("[관리 규칙]")
        for value in management_rule.values():
            lines.append(f"- {value}")
        lines.append("")

    project_concept = data.get("project_concept", {})
    if project_concept:
        lines.append("[공통 컨셉]")
        if project_concept.get("short"):
            lines.append(f"- {project_concept['short']}")
        if project_concept.get("mood"):
            lines.append(f"- 분위기: {', '.join(project_concept['mood'])}")
        if project_concept.get("motifs"):
            lines.append(f"- 모티브: {', '.join(project_concept['motifs'])}")
        if project_concept.get("avoid_mood"):
            lines.append(f"- 피할 분위기: {', '.join(project_concept['avoid_mood'])}")
        lines.append("")

    pixel_rules = data.get("pixel_rules", {})
    if pixel_rules:
        lines.append("[픽셀 규칙]")
        for key, value in pixel_rules.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    style_pillars = data.get("style_pillars", [])
    if style_pillars:
        lines.append("[스타일 축]")
        for pillar in style_pillars:
            lines.append(f"- {pillar.get('name', pillar.get('id', '(이름 없음)'))}: {pillar.get('rule', '')}")
        lines.append("")

    palette = data.get("palette", {})
    global_palette = palette.get("global", [])
    if global_palette:
        lines.append("[전역 팔레트]")
        for color in global_palette:
            lines.append(
                f"- {color.get('name', color.get('id', '(색상)'))} "
                f"{color.get('hex', '')}: {color.get('usage', '')}"
            )
        lines.append("")

    biome_accents = palette.get("biome_accents", [])
    if biome_accents:
        lines.append("[바이옴 포인트 색]")
        for accent in biome_accents:
            colors = ", ".join(accent.get("colors", []))
            lines.append(f"- {accent.get('name', accent.get('id', '(바이옴)'))}: {colors} / {accent.get('usage', '')}")
        lines.append("")

    palette_rules = palette.get("rules", {})
    if palette_rules:
        lines.append("[팔레트 금지/규칙]")
        for key, value in palette_rules.items():
            if isinstance(value, list):
                lines.append(f"- {key}: {', '.join(value)}")
            else:
                lines.append(f"- {key}: {value}")
        lines.append("")

    asset_profiles = data.get("asset_profiles", {})
    if asset_profiles:
        lines.append("[에셋 프로필 토큰]")
        for profile_id, profile in asset_profiles.items():
            lines.append(f"- {profile_id}")
            positive = profile.get("positive_tokens", [])
            negative = profile.get("negative_tokens", [])
            if positive:
                lines.append(f"  positive: {', '.join(positive)}")
            if negative:
                lines.append(f"  negative: {', '.join(negative)}")
        lines.append("")

    prompt_assembly = data.get("prompt_assembly", {})
    if prompt_assembly:
        lines.append("[프롬프트 조립]")
        for key, value in prompt_assembly.items():
            if isinstance(value, list):
                lines.append(f"- {key}: {', '.join(value)}")
            else:
                lines.append(f"- {key}: {value}")

    return "\n".join(lines).rstrip() + "\n"
