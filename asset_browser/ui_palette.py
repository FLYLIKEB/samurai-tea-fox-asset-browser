"""Style token and palette editing panel for the asset browser UI."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import colorchooser

from .constants import ART_STYLE_TOKENS_PATH, BG, BORDER, ERROR, MUTED, PANEL, TEXT
from .style_tokens import (
    format_art_style_tokens,
    load_art_style_tokens,
    normalize_hex_color,
    save_art_style_tokens,
)

class PalettePanelMixin:
    def reload_art_style_tokens(self) -> None:
        path = self.project_root / ART_STYLE_TOKENS_PATH
        data, error = load_art_style_tokens(self.project_root)
        self.art_style_data = data
        if path.exists():
            self.art_style_raw = path.read_text(encoding="utf-8")
        else:
            self.art_style_raw = ""
        self.render_palette_swatches(data)
        self.style_text.configure(state=tk.NORMAL)
        self.style_text.delete("1.0", tk.END)
        self.style_text.insert("1.0", format_art_style_tokens(data, error))
        self.style_text.configure(state=tk.DISABLED)
        if error:
            self.status_var.set(error)
        else:
            self.status_var.set(f"아트 스타일 토큰 다시 읽음: {ART_STYLE_TOKENS_PATH.as_posix()}")
        if self.palette_preview_var.get():
            self.render_grid()

    def copy_art_style_tokens(self) -> None:
        if not self.art_style_raw:
            self._warn_no_art_style_tokens()
            return
        self._copy_text(self.art_style_raw, "아트 스타일 토큰 원본")
        self.status_var.set("아트 스타일 토큰 원본 복사 완료")

    def render_palette_swatches(self, data: dict | None) -> None:
        for child in self.palette_frame.winfo_children():
            child.destroy()

        if data is None:
            tk.Label(
                self.palette_frame,
                text="팔레트 없음",
                bg=BG,
                fg=MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            return

        palette = data.get("palette", {})
        global_palette = palette.get("global", [])
        biome_accents = palette.get("biome_accents", [])

        tk.Label(self.palette_frame, text="전역 팔레트", bg=BG, fg=TEXT, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        tk.Label(
            self.palette_frame,
            text="색상칩 클릭으로 수정",
            bg=BG,
            fg=MUTED,
            anchor="e",
        ).grid(row=0, column=1, sticky="e", pady=(0, 4))
        for index, color in enumerate(global_palette[:14]):
            row = 1 + index // 2
            column = index % 2
            self._add_color_swatch(
                self.palette_frame,
                row,
                column,
                color.get("hex", ""),
                color.get("name", color.get("id", "색상")),
                lambda selected, color_index=index: self.update_global_palette_color(
                    color_index,
                    selected,
                ),
            )

        accent_start_row = 1 + math.ceil(min(len(global_palette), 14) / 2)
        if biome_accents:
            tk.Label(
                self.palette_frame,
                text="바이옴 포인트",
                bg=BG,
                fg=TEXT,
                anchor="w",
            ).grid(row=accent_start_row, column=0, columnspan=2, sticky="w", pady=(8, 4))
            for index, accent in enumerate(biome_accents[:4]):
                row = accent_start_row + 1 + index // 2
                column = index % 2
                self._add_accent_swatch(
                self.palette_frame,
                row,
                column,
                accent.get("colors", []),
                accent.get("name", accent.get("id", "바이옴")),
                index,
            )

    def _add_color_swatch(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        hex_color: str,
        name: str,
        on_pick,
    ) -> None:
        item = tk.Frame(parent, bg=BG)
        item.grid(row=row, column=column, sticky="w", padx=(0, 12), pady=2)
        canvas = tk.Canvas(item, width=22, height=18, bg=BG, highlightthickness=1, highlightbackground=BORDER)
        canvas.pack(side=tk.LEFT)
        self._safe_rectangle(canvas, 2, 2, 20, 16, hex_color)
        canvas.configure(cursor="hand2")
        tk.Label(
            item,
            text=f"{name} {hex_color}",
            bg=BG,
            fg=TEXT,
            anchor="w",
            font=("TkDefaultFont", 9),
        ).pack(side=tk.LEFT, padx=(5, 0))
        canvas.bind(
            "<Button-1>",
            lambda _event, current=hex_color, label=name, callback=on_pick: self.pick_palette_color(
                current,
                label,
                callback,
            ),
        )

    def _add_accent_swatch(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        colors: list[str],
        name: str,
        accent_index: int,
    ) -> None:
        item = tk.Frame(parent, bg=BG)
        item.grid(row=row, column=column, sticky="w", padx=(0, 12), pady=2)
        for index, hex_color in enumerate(colors[:3]):
            canvas = tk.Canvas(
                item,
                width=14,
                height=18,
                bg=BG,
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            canvas.pack(side=tk.LEFT)
            self._safe_rectangle(canvas, 2, 2, 12, 16, hex_color)
            canvas.configure(cursor="hand2")
            canvas.bind(
                "<Button-1>",
                lambda _event,
                current=hex_color,
                label=f"{name} {index + 1}",
                accent=accent_index,
                color_index=index: self.pick_palette_color(
                    current,
                    label,
                    lambda selected: self.update_biome_accent_color(accent, color_index, selected),
                ),
            )
        tk.Label(
            item,
            text=name,
            bg=BG,
            fg=TEXT,
            anchor="w",
            font=("TkDefaultFont", 9),
        ).pack(side=tk.LEFT, padx=(5, 0))

    def _safe_rectangle(
        self,
        canvas: tk.Canvas,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        hex_color: str,
    ) -> None:
        try:
            canvas.create_rectangle(x0, y0, x1, y1, fill=hex_color, outline="")
        except tk.TclError:
            canvas.create_rectangle(x0, y0, x1, y1, fill=ERROR, outline="")

    def pick_palette_color(self, current_hex: str, name: str, on_pick) -> None:
        selected = colorchooser.askcolor(
            color=normalize_hex_color(current_hex),
            title=f"{name} 색상 선택",
            parent=self,
        )
        if not selected or not selected[1]:
            return
        on_pick(normalize_hex_color(selected[1]))

    def update_global_palette_color(self, color_index: int, hex_color: str) -> None:
        if self.art_style_data is None:
            self._warn_no_art_style_tokens()
            return
        palette = self.art_style_data.get("palette", {})
        global_palette = palette.get("global", [])
        if color_index >= len(global_palette):
            return
        global_palette[color_index]["hex"] = hex_color
        self.persist_art_style_tokens(f"전역 팔레트 색상 저장: {hex_color}")

    def update_biome_accent_color(self, accent_index: int, color_index: int, hex_color: str) -> None:
        if self.art_style_data is None:
            self._warn_no_art_style_tokens()
            return
        palette = self.art_style_data.get("palette", {})
        biome_accents = palette.get("biome_accents", [])
        if accent_index >= len(biome_accents):
            return
        colors = biome_accents[accent_index].get("colors", [])
        if color_index >= len(colors):
            return
        colors[color_index] = hex_color
        self.persist_art_style_tokens(f"바이옴 포인트 색상 저장: {hex_color}")

    def persist_art_style_tokens(self, status: str) -> None:
        if self.art_style_data is None:
            return
        save_art_style_tokens(self.project_root, self.art_style_data)
        self.reload_art_style_tokens()
        if self.palette_preview_var.get():
            self.render_grid()
        self.status_var.set(status)
