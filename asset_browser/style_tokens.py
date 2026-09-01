"""Art style token JSON loading, formatting, and palette extraction."""

from __future__ import annotations

import json
from pathlib import Path

from .constants import ART_STYLE_TOKENS_PATH

CANONICAL_PALETTE_LABEL = "정본"

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

def palette_candidates(data: dict | None) -> list[dict]:
    if data is None:
        return []
    candidates = data.get("palette", {}).get("candidates", [])
    return candidates if isinstance(candidates, list) else []

def palette_candidate_label(candidate: dict) -> str:
    name = candidate.get("name", candidate.get("id", "후보"))
    candidate_id = candidate.get("id", "")
    return f"{name} ({candidate_id})" if candidate_id else name

def palette_candidate_options(data: dict | None) -> list[tuple[str, str]]:
    options = [(CANONICAL_PALETTE_LABEL, "")]
    for candidate in palette_candidates(data):
        candidate_id = candidate.get("id", "")
        if candidate_id:
            options.append((palette_candidate_label(candidate), candidate_id))
    return options

def palette_block(data: dict | None, candidate_id: str = "") -> dict:
    if data is None:
        return {}

    palette = data.get("palette", {})
    if not candidate_id:
        return palette

    candidate = next(
        (item for item in palette_candidates(data) if item.get("id") == candidate_id),
        None,
    )
    if candidate is None:
        return palette

    merged = dict(palette)
    merged["global"] = merge_global_palette(palette.get("global", []), candidate.get("global", []))
    merged["biome_accents"] = merge_biome_accents(
        palette.get("biome_accents", []),
        candidate.get("biome_accents", []),
    )
    return merged

def merge_global_palette(base: list[dict], candidate: list[dict]) -> list[dict]:
    candidate_by_id = {entry.get("id"): entry for entry in candidate}
    merged: list[dict] = []
    for base_entry in base:
        entry = dict(base_entry)
        override = candidate_by_id.get(base_entry.get("id"))
        if override:
            entry.update(override)
        merged.append(entry)
    base_ids = {entry.get("id") for entry in base}
    merged.extend(dict(entry) for entry in candidate if entry.get("id") not in base_ids)
    return merged

def merge_biome_accents(base: list[dict], candidate: list[dict]) -> list[dict]:
    candidate_by_id = {entry.get("id"): entry for entry in candidate}
    merged: list[dict] = []
    for base_entry in base:
        entry = dict(base_entry)
        override = candidate_by_id.get(base_entry.get("id"))
        if override:
            entry.update(override)
        merged.append(entry)
    base_ids = {entry.get("id") for entry in base}
    merged.extend(dict(entry) for entry in candidate if entry.get("id") not in base_ids)
    return merged

def apply_palette_candidate(data: dict, candidate_id: str) -> bool:
    palette = data.get("palette", {})
    candidate = next(
        (item for item in palette_candidates(data) if item.get("id") == candidate_id),
        None,
    )
    if candidate is None:
        return False

    block = palette_block(data, candidate_id)
    palette["global"] = block.get("global", [])
    palette["biome_accents"] = block.get("biome_accents", [])
    return True

def upsert_candidate_global_color(
    data: dict,
    candidate_id: str,
    color_id: str,
    hex_color: str,
) -> bool:
    candidate = next(
        (item for item in palette_candidates(data) if item.get("id") == candidate_id),
        None,
    )
    if candidate is None:
        return False
    global_palette = candidate.setdefault("global", [])
    entry = next((item for item in global_palette if item.get("id") == color_id), None)
    if entry is None:
        global_palette.append({"id": color_id, "hex": hex_color})
    else:
        entry["hex"] = hex_color
    return True

def upsert_candidate_biome_color(
    data: dict,
    candidate_id: str,
    biome_id: str,
    color_index: int,
    hex_color: str,
) -> bool:
    candidate = next(
        (item for item in palette_candidates(data) if item.get("id") == candidate_id),
        None,
    )
    if candidate is None:
        return False
    biome_accents = candidate.setdefault("biome_accents", [])
    entry = next((item for item in biome_accents if item.get("id") == biome_id), None)
    if entry is None:
        entry = {"id": biome_id, "colors": []}
        biome_accents.append(entry)
    colors = entry.setdefault("colors", [])
    while len(colors) <= color_index:
        colors.append("#000000")
    colors[color_index] = hex_color
    return True

def extract_palette_colors(data: dict | None, candidate_id: str = "") -> list[tuple[int, int, int]]:
    if data is None:
        return []

    colors: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    palette = palette_block(data, candidate_id)

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

    candidates = palette_candidates(data)
    if candidates:
        lines.append("[팔레트 후보]")
        for candidate in candidates:
            lines.append(
                f"- {candidate.get('name', candidate.get('id', '(후보)'))}: "
                f"{candidate.get('description', '')}"
            )
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
