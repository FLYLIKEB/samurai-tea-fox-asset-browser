"""Layout construction and scroll behavior for the asset browser UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .constants import (
    ART_STYLE_TOKENS_PATH,
    BG,
    BORDER,
    MUTED,
    PANEL,
    RESIZE_CHOICES,
    SCALE_CHOICES,
    TEXT,
)
from .paths import template_path

class LayoutMixin:
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 5))

        toolbar = tk.Frame(self, bg=PANEL, padx=8, pady=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        path_entry = tk.Entry(toolbar, textvariable=self.path_var, bg=BG, fg=TEXT, relief=tk.FLAT)
        path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._button(toolbar, "찾기", self.choose_root).grid(row=0, column=1, padx=1)
        self._button(toolbar, "새로고침", self.rescan).grid(row=0, column=2, padx=1)
        self._button(toolbar, "Finder에서 폴더 보기", self.reveal_asset_root).grid(
            row=0, column=3, padx=(1, 8)
        )
        filter_entry = tk.Entry(
            toolbar,
            textvariable=self.filter_var,
            bg=BG,
            fg=TEXT,
            relief=tk.FLAT,
            insertbackground=TEXT,
        )
        filter_entry.grid(row=0, column=4, sticky="ew", padx=(0, 6))
        filter_entry.bind("<KeyRelease>", lambda _event: self.apply_filter())

        scale_box = tk.OptionMenu(toolbar, self.scale_var, *SCALE_CHOICES, command=self._scale_changed)
        scale_box.configure(bg=BG, fg=TEXT, activebackground=PANEL, relief=tk.FLAT, width=6)
        scale_box["menu"].configure(bg=BG, fg=TEXT)
        scale_box.grid(row=0, column=5, padx=(0, 2))

        toolbar.columnconfigure(0, weight=3)
        toolbar.columnconfigure(4, weight=2)

        actions = tk.Frame(self, bg=BG, padx=8, pady=5)
        actions.pack(side=tk.TOP, fill=tk.X)

        self._button(actions, "전체", self.select_all).pack(side=tk.LEFT, padx=(0, 4))
        self._button(actions, "해제", self.clear_selection).pack(side=tk.LEFT, padx=(0, 4))
        self._button(actions, "삭제", self.delete_selected_images).pack(side=tk.LEFT, padx=(0, 8))
        self._button(actions, "상대경로", self.copy_relative_paths).pack(side=tk.LEFT, padx=(0, 4))
        self._button(actions, "절대경로", self.copy_absolute_paths).pack(side=tk.LEFT, padx=(0, 4))
        self._button(actions, "프롬프트", self.copy_codex_prompt).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        self._button(actions, "TXT 저장", self.save_txt).pack(side=tk.LEFT)
        resize_box = tk.OptionMenu(actions, self.resize_size_var, *RESIZE_CHOICES)
        resize_box.configure(bg=BG, fg=TEXT, activebackground=PANEL, relief=tk.FLAT, width=7)
        resize_box["menu"].configure(bg=BG, fg=TEXT)
        resize_box.pack(side=tk.LEFT, padx=(8, 3))
        self._button(actions, "리사이즈", self.resize_selected_images).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.transparent_color_swatch = tk.Button(
            actions,
            text="",
            command=self.choose_transparent_color,
            bg=self.transparent_color_var.get(),
            activebackground=self.transparent_color_var.get(),
            relief=tk.FLAT,
            width=2,
            padx=0,
            pady=3,
            highlightthickness=0,
        )
        self.transparent_color_swatch.pack(side=tk.LEFT, padx=(0, 3))
        transparent_entry = tk.Entry(
            actions,
            textvariable=self.transparent_color_var,
            bg=PANEL,
            fg=TEXT,
            relief=tk.FLAT,
            width=8,
            insertbackground=TEXT,
        )
        transparent_entry.pack(side=tk.LEFT, padx=(0, 3))
        transparent_entry.bind("<KeyRelease>", lambda _event: self.refresh_transparent_color_swatch())
        self._button(actions, "투명화", self.apply_transparency_to_selected_images).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self._button(actions, "팔레트 변환", self.apply_palette_to_shown_images).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        preview_toggle = tk.Checkbutton(
            actions,
            text="팔레트 테스트 보기",
            variable=self.palette_preview_var,
            command=self.toggle_palette_preview,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=PANEL,
            relief=tk.FLAT,
            padx=6,
        )
        preview_toggle.pack(side=tk.RIGHT)

        self.bottom_panel = tk.Frame(self, bg=PANEL, padx=8, pady=3)
        self.bottom_panel.pack(side=tk.BOTTOM, fill=tk.X)

        self.bottom_bar = tk.Frame(self.bottom_panel, bg=PANEL)
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_toggle_button = self._button(
            self.bottom_bar,
            "작업 패널 열기",
            self.toggle_bottom_panel,
        )
        self.bottom_toggle_button.pack(side=tk.LEFT, padx=(0, 8))

        status = tk.Label(
            self.bottom_bar,
            textvariable=self.status_var,
            anchor="w",
            bg=PANEL,
            fg=MUTED,
            padx=0,
            pady=3,
        )
        status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.bottom_content = tk.Frame(self.bottom_panel, bg=PANEL)

        notebook = ttk.Notebook(self.bottom_content)
        notebook.pack(side=tk.TOP, fill=tk.X)

        prompt_panel = tk.Frame(notebook, bg=PANEL, padx=5, pady=5)
        template_panel = tk.Frame(notebook, bg=PANEL, padx=5, pady=5)
        style_panel = tk.Frame(notebook, bg=PANEL, padx=5, pady=5)
        notebook.add(prompt_panel, text="복사 프롬프트")
        notebook.add(template_panel, text="기본 템플릿")
        notebook.add(style_panel, text="스타일 토큰")

        prompt_header = tk.Frame(prompt_panel, bg=PANEL)
        prompt_header.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(
            prompt_header,
            text="복사될 Codex 프롬프트",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT)
        self._button(prompt_header, "프롬프트 초기화", self.reset_prompt).pack(side=tk.RIGHT)

        self.prompt_text = tk.Text(
            prompt_panel,
            height=3,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=6,
            pady=6,
            undo=True,
        )
        self.prompt_text.pack(side=tk.TOP, fill=tk.X)
        self.prompt_text.bind("<<Modified>>", self._prompt_modified)

        template_header = tk.Frame(template_panel, bg=PANEL)
        template_header.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(
            template_header,
            text="기본 프롬프트 템플릿",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT)
        self._button(template_header, "기본값 복원", self.restore_builtin_template).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_header, "다시 읽기", self.reload_template).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_header, "템플릿 저장", self.save_template).pack(side=tk.RIGHT)

        template_path_row = tk.Frame(template_panel, bg=PANEL)
        template_path_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        tk.Label(
            template_path_row,
            text=f"파일: {template_path(self.project_root)}",
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            justify=tk.LEFT,
            wraplength=310,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._button(template_path_row, "경로 복사", self.copy_template_path).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_path_row, "Finder에서 보기", self.reveal_template_file).pack(
            side=tk.RIGHT
        )

        self.template_text = tk.Text(
            template_panel,
            height=3,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=6,
            pady=6,
            undo=True,
        )
        self.template_text.pack(side=tk.TOP, fill=tk.X)
        self.template_text.bind("<<Modified>>", self._template_modified)
        self.set_template_text(self.prompt_template, dirty=False)

        style_header = tk.Frame(style_panel, bg=PANEL)
        style_header.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(
            style_header,
            text="아트 스타일 토큰",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT)
        self._button(style_header, "원본 복사", self.copy_art_style_tokens).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(style_header, "다시 읽기", self.reload_art_style_tokens).pack(side=tk.RIGHT)

        style_path_row = tk.Frame(style_panel, bg=PANEL)
        style_path_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.style_file_path = self.project_root / ART_STYLE_TOKENS_PATH
        tk.Label(
            style_path_row,
            text=f"파일: {self.style_file_path}",
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            justify=tk.LEFT,
            wraplength=310,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._button(style_path_row, "경로 복사", self.copy_art_style_path).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(style_path_row, "Finder에서 보기", self.reveal_art_style_file).pack(
            side=tk.RIGHT
        )

        self.palette_frame = tk.Frame(style_panel, bg=BG, padx=6, pady=4)
        self.palette_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        style_text_frame = tk.Frame(style_panel, bg=PANEL)
        style_text_frame.pack(side=tk.TOP, fill=tk.X)
        self.style_text = tk.Text(
            style_text_frame,
            height=3,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=6,
            pady=6,
        )
        style_scrollbar = tk.Scrollbar(style_text_frame, orient=tk.VERTICAL, command=self.style_text.yview)
        self.style_text.configure(yscrollcommand=style_scrollbar.set)
        self.style_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.reload_art_style_tokens()

        self._set_bottom_panel_visible(False)

        image_area = tk.Frame(self, bg=BG)
        image_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(image_area, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(image_area, orient=tk.VERTICAL, command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas, bg=BG, padx=10, pady=10)

        self.grid_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.grid_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_grid_window)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BG,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            highlightthickness=0,
            highlightbackground=BORDER,
        )

    def toggle_bottom_panel(self) -> None:
        self._set_bottom_panel_visible(not self.bottom_panel_visible.get())

    def _set_bottom_panel_visible(self, visible: bool) -> None:
        self.bottom_panel_visible.set(visible)
        if visible:
            self.bottom_content.pack(side=tk.TOP, fill=tk.X, before=self.bottom_bar)
            self.bottom_toggle_button.configure(text="작업 패널 닫기")
        else:
            self.bottom_content.pack_forget()
            self.bottom_toggle_button.configure(text="작업 패널 열기")

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_grid_window(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.grid_window, width=event.width)
        self.render_grid()

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
