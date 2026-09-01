"""Style token and palette editing panel for the asset browser UI."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import colorchooser, messagebox

from .constants import ART_STYLE_TOKENS_PATH, BG, BORDER, ERROR, MUTED, PANEL, TEXT
from .style_tokens import (
    CANONICAL_PALETTE_LABEL,
    apply_palette_candidate,
    format_art_style_tokens,
    load_art_style_tokens,
    normalize_hex_color,
    palette_block,
    palette_candidate_options,
    palette_candidates,
    save_art_style_tokens,
    upsert_candidate_biome_color,
    upsert_candidate_global_color,
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

    def selected_palette_candidate_id(self) -> str:
        return self.palette_candidate_ids.get(self.palette_candidate_var.get(), "")

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

        self._render_palette_candidate_controls(data)
        selected_block = palette_block(data, self.selected_palette_candidate_id())
        global_palette = selected_block.get("global", [])
        biome_accents = selected_block.get("biome_accents", [])

        tk.Label(self.palette_frame, text="전역 팔레트", bg=BG, fg=TEXT, anchor="w").grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 4),
        )
        tk.Label(
            self.palette_frame,
            text="선택 후보 기준 표시",
            bg=BG,
            fg=MUTED,
            anchor="e",
        ).grid(row=3, column=1, sticky="e", pady=(8, 4))
        for index, color in enumerate(global_palette[:14]):
            row = 4 + index // 2
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

        accent_start_row = 4 + math.ceil(min(len(global_palette), 14) / 2)
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

    def _render_palette_candidate_controls(self, data: dict) -> None:
        options = palette_candidate_options(data)
        self.palette_candidate_ids = {label: candidate_id for label, candidate_id in options}
        labels = [label for label, _candidate_id in options]
        if self.palette_candidate_var.get() not in self.palette_candidate_ids:
            self.palette_candidate_var.set(CANONICAL_PALETTE_LABEL)

        tk.Label(self.palette_frame, text="팔레트 후보", bg=BG, fg=TEXT, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )

        controls = tk.Frame(self.palette_frame, bg=BG)
        controls.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        menu = tk.OptionMenu(
            controls,
            self.palette_candidate_var,
            *labels,
            command=lambda _value: self.palette_candidate_changed(),
        )
        menu.configure(bg=PANEL, fg=TEXT, activebackground=BG, relief=tk.FLAT, width=24)
        menu["menu"].configure(bg=PANEL, fg=TEXT)
        menu.pack(side=tk.LEFT, padx=(0, 6))
        self._button(controls, "✓ 선택 후보 적용", self.apply_selected_palette_candidate).pack(
            side=tk.LEFT
        )

        compare = tk.Frame(self.palette_frame, bg=BG)
        compare.grid(row=2, column=0, columnspan=2, sticky="w")
        self._add_candidate_preview(compare, CANONICAL_PALETTE_LABEL, "", palette_block(data))
        for candidate in palette_candidates(data):
            self._add_candidate_preview(
                compare,
                candidate.get("name", candidate.get("id", "후보")),
                candidate.get("id", ""),
                palette_block(data, candidate.get("id", "")),
            )

    def _add_candidate_preview(
        self,
        parent: tk.Widget,
        name: str,
        candidate_id: str,
        selected_palette: dict,
    ) -> None:
        item = tk.Frame(parent, bg=BG)
        item.pack(side=tk.TOP, fill=tk.X, pady=1)
        label = tk.Label(item, text=name, bg=BG, fg=TEXT, anchor="w", width=12, cursor="hand2")
        label.pack(side=tk.LEFT)
        option_label = self._candidate_label_for_id(candidate_id)
        label.bind("<Button-1>", lambda _event, value=option_label: self.select_palette_candidate(value))
        colors = [entry.get("hex", "") for entry in selected_palette.get("global", [])[:8]]
        for accent in selected_palette.get("biome_accents", [])[:3]:
            colors.extend(accent.get("colors", [])[:1])
        for hex_color in colors[:11]:
            canvas = tk.Canvas(
                item,
                width=16,
                height=14,
                bg=BG,
                highlightthickness=1,
                highlightbackground=BORDER,
                cursor="hand2",
            )
            canvas.pack(side=tk.LEFT, padx=(0, 2))
            self._safe_rectangle(canvas, 2, 2, 14, 12, hex_color)
            canvas.bind("<Button-1>", lambda _event, value=option_label: self.select_palette_candidate(value))

    def _candidate_label_for_id(self, candidate_id: str) -> str:
        for label, stored_id in self.palette_candidate_ids.items():
            if stored_id == candidate_id:
                return label
        return CANONICAL_PALETTE_LABEL

    def select_palette_candidate(self, option_label: str) -> None:
        self.palette_candidate_var.set(option_label)
        self.palette_candidate_changed()

    def palette_candidate_changed(self) -> None:
        self.render_palette_swatches(self.art_style_data)
        if self.palette_preview_var.get():
            self.render_grid()
        candidate = self.palette_candidate_var.get()
        self.status_var.set(f"팔레트 후보 선택: {candidate}")

    def apply_selected_palette_candidate(self) -> None:
        if self.art_style_data is None:
            self._warn_no_art_style_tokens()
            return
        candidate_id = self.selected_palette_candidate_id()
        if not candidate_id:
            self.status_var.set("정본 팔레트가 이미 선택되어 있습니다.")
            return
        ok = messagebox.askokcancel(
            "팔레트 후보 적용",
            f"{self.palette_candidate_var.get()} 후보를 전역/바이옴 팔레트 정본으로 적용합니다.\n\n계속할까요?",
        )
        if not ok:
            return
        if apply_palette_candidate(self.art_style_data, candidate_id):
            self.palette_candidate_var.set(CANONICAL_PALETTE_LABEL)
            self.persist_art_style_tokens("선택 후보를 정본 팔레트로 적용했습니다.")

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
        selected_block = palette_block(self.art_style_data, self.selected_palette_candidate_id())
        global_palette = selected_block.get("global", [])
        if color_index >= len(global_palette):
            return
        candidate_id = self.selected_palette_candidate_id()
        if candidate_id:
            color_id = global_palette[color_index].get("id", "")
            if not color_id:
                return
            upsert_candidate_global_color(self.art_style_data, candidate_id, color_id, hex_color)
        else:
            palette.get("global", [])[color_index]["hex"] = hex_color
        self.persist_art_style_tokens(f"전역 팔레트 색상 저장: {hex_color}")

    def update_biome_accent_color(self, accent_index: int, color_index: int, hex_color: str) -> None:
        if self.art_style_data is None:
            self._warn_no_art_style_tokens()
            return
        palette = self.art_style_data.get("palette", {})
        selected_block = palette_block(self.art_style_data, self.selected_palette_candidate_id())
        biome_accents = selected_block.get("biome_accents", [])
        if accent_index >= len(biome_accents):
            return
        colors = biome_accents[accent_index].get("colors", [])
        if color_index >= len(colors):
            return
        candidate_id = self.selected_palette_candidate_id()
        if candidate_id:
            biome_id = biome_accents[accent_index].get("id", "")
            if not biome_id:
                return
            upsert_candidate_biome_color(
                self.art_style_data,
                candidate_id,
                biome_id,
                color_index,
                hex_color,
            )
        else:
            palette.get("biome_accents", [])[accent_index].get("colors", [])[color_index] = hex_color
        self.persist_art_style_tokens(f"바이옴 포인트 색상 저장: {hex_color}")

    def persist_art_style_tokens(self, status: str) -> None:
        if self.art_style_data is None:
            return
        save_art_style_tokens(self.project_root, self.art_style_data)
        self.reload_art_style_tokens()
        if self.palette_preview_var.get():
            self.render_grid()
        self.status_var.set(status)
