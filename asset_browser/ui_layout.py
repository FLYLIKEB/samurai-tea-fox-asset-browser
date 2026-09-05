"""Layout construction and scroll behavior for the asset browser UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .constants import (
    ADJUSTMENT_CHOICES,
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

def wheel_scroll_units(delta: int, remainder: float) -> tuple[int, float]:
    if delta == 0:
        return 0, remainder

    if abs(delta) < 120:
        return (-1 if delta > 0 else 1), 0.0

    amount = remainder + (-delta / 120)
    units = int(amount)
    return units, amount - units

class LayoutMixin:
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 5))

        toolbar = tk.Frame(self, bg=PANEL, padx=8, pady=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        path_entry = tk.Entry(toolbar, textvariable=self.path_var, bg=BG, fg=TEXT, relief=tk.FLAT)
        path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._button(toolbar, "⌕ 찾기 (⌘O)", self.choose_root).grid(row=0, column=1, padx=1)
        self._button(toolbar, "↻ 새로고침 (⌘R)", self.rescan).grid(row=0, column=2, padx=1)
        self._button(toolbar, "⌂ Finder (⌘F)", self.reveal_asset_root).grid(
            row=0, column=3, padx=1
        )
        self._button(toolbar, "▾ 펼침 (⌘U)", self.expand_all_groups).grid(
            row=0, column=4, padx=1
        )
        self._button(toolbar, "▸ 접기 (⌘J)", self.collapse_all_groups).grid(
            row=0, column=5, padx=(1, 8)
        )
        filter_entry = tk.Entry(
            toolbar,
            textvariable=self.filter_var,
            bg=BG,
            fg=TEXT,
            relief=tk.FLAT,
            insertbackground=TEXT,
        )
        filter_entry.grid(row=0, column=6, sticky="ew", padx=(0, 6))
        filter_entry.bind("<KeyRelease>", lambda _event: self.apply_filter())

        scale_box = tk.OptionMenu(toolbar, self.scale_var, *SCALE_CHOICES, command=self._scale_changed)
        scale_box.configure(bg=BG, fg=TEXT, activebackground=PANEL, relief=tk.FLAT, width=6)
        scale_box["menu"].configure(bg=BG, fg=TEXT)
        scale_box.grid(row=0, column=7, padx=(0, 2))

        toolbar.columnconfigure(0, weight=3)
        toolbar.columnconfigure(6, weight=2)

        self.bottom_panel = tk.Frame(self, bg=PANEL, padx=8, pady=3)
        self.bottom_panel.pack(side=tk.BOTTOM, fill=tk.X)

        self.bottom_bar = tk.Frame(self.bottom_panel, bg=PANEL)
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_toggle_button = self._button(
            self.bottom_bar,
            "▴ 작업 패널 (⌘W)",
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
        self._build_bottom_panel()
        self._set_bottom_panel_visible(False)

        main_area = tk.Frame(self, bg=BG)
        main_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left_sidebar = tk.Frame(main_area, bg=BG, padx=8, pady=8, width=220)
        left_sidebar.pack(side=tk.LEFT, fill=tk.Y)
        left_sidebar.pack_propagate(False)

        select_group = self._side_group(left_sidebar, "선택")
        file_group = self._side_group(left_sidebar, "파일")
        copy_group = self._side_group(left_sidebar, "복사")

        self._button(select_group, "✓ 전체 (⌘A)", self.select_all, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(select_group, "× 해제 (Esc)", self.clear_selection, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        scroll_select_toggle = tk.Checkbutton(
            select_group,
            text="↕ 스크롤선택 (⌘E)",
            variable=self.scroll_select_var,
            command=self.scroll_select_changed,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=PANEL,
            relief=tk.FLAT,
            padx=6,
            width=15,
            anchor="w",
        )
        scroll_select_toggle.pack(side=tk.TOP, fill=tk.X)

        self._button(file_group, "⌫ 삭제 (Del)", self.delete_selected_images, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(file_group, "⇢ 이동 (⌘M)", self.move_selected_images, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(file_group, "⇄ 파일 교체", self.replace_selected_image_with_file, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(file_group, "⟳ Godot 전체 반영", self.sync_all_images_to_godot, width=16).pack(
            side=tk.TOP,
            fill=tk.X,
        )

        self._button(copy_group, "⇄ 상대 (⌘1)", self.copy_relative_paths, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(copy_group, "⛓ 절대 (⌘2)", self.copy_absolute_paths, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(copy_group, "⌘ 프롬프트 (⌘C)", self.copy_codex_prompt, width=15).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(copy_group, "▤ TXT (⌘T)", self.save_txt, width=10).pack(side=tk.TOP, fill=tk.X)

        image_area = tk.Frame(main_area, bg=BG)
        image_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(image_area, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(image_area, orient=tk.VERTICAL, command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas, bg=BG, padx=10, pady=10)

        self.grid_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        right_sidebar = tk.Frame(main_area, bg=BG, padx=8, pady=8, width=270)
        right_sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        right_sidebar.pack_propagate(False)

        resize_group = self._side_group(right_sidebar, "크기")
        transparent_group = self._side_group(right_sidebar, "투명화")
        palette_group = self._side_group(right_sidebar, "팔레트")
        adjust_group = self._side_group(right_sidebar, "보정")

        resize_box = tk.OptionMenu(resize_group, self.resize_size_var, *RESIZE_CHOICES)
        resize_box.configure(bg=BG, fg=TEXT, activebackground=PANEL, relief=tk.FLAT, width=18)
        resize_box["menu"].configure(bg=BG, fg=TEXT)
        resize_box.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self._button(resize_group, "↔ 적용 (⌘Z)", self.resize_selected_images, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
        )

        transparent_color_row = tk.Frame(transparent_group, bg=PANEL)
        transparent_color_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.transparent_color_swatch = tk.Button(
            transparent_color_row,
            text="색 (⌘K)",
            command=self.choose_transparent_color,
            bg=self.transparent_color_var.get(),
            activebackground=self.transparent_color_var.get(),
            fg=TEXT,
            relief=tk.FLAT,
            width=7,
            padx=2,
            pady=3,
            highlightthickness=0,
        )
        self.transparent_color_swatch.pack(side=tk.LEFT, padx=(0, 3))
        transparent_entry = tk.Entry(
            transparent_color_row,
            textvariable=self.transparent_color_var,
            bg=PANEL,
            fg=TEXT,
            relief=tk.FLAT,
            width=8,
            insertbackground=TEXT,
        )
        transparent_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        transparent_entry.bind("<KeyRelease>", lambda _event: self.refresh_transparent_color_swatch())
        tk.Label(transparent_group, text="범위", bg=PANEL, fg=MUTED, anchor="w").pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(2, 2),
        )
        tolerance_box = tk.Spinbox(
            transparent_group,
            from_=0,
            to=255,
            textvariable=self.transparent_tolerance_var,
            width=4,
            bg=PANEL,
            fg=TEXT,
            relief=tk.FLAT,
            increment=4,
        )
        tolerance_box.pack(side=tk.TOP, anchor="w", pady=(0, 4))
        edge_only_toggle = tk.Checkbutton(
            transparent_group,
            text="외곽만",
            variable=self.transparent_edge_only_var,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=PANEL,
            relief=tk.FLAT,
            padx=4,
        )
        edge_only_toggle.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self._button(
            transparent_group,
            "◫ 적용 (⌘G)",
            self.apply_transparency_to_selected_images,
            width=11,
        ).pack(side=tk.TOP, fill=tk.X)

        self._button(palette_group, "◩ 선택 변환 (⌘P)", self.apply_palette_to_selected_images, width=16).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        preview_toggle = tk.Checkbutton(
            palette_group,
            text="미리보기 (⌘V)",
            variable=self.palette_preview_var,
            command=self.toggle_palette_preview,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=PANEL,
            relief=tk.FLAT,
            padx=6,
            width=13,
            anchor="w",
        )
        preview_toggle.pack(side=tk.TOP, fill=tk.X)

        adjustment_box = tk.OptionMenu(adjust_group, self.adjustment_kind_var, *ADJUSTMENT_CHOICES)
        adjustment_box.configure(bg=BG, fg=TEXT, activebackground=PANEL, relief=tk.FLAT, width=18)
        adjustment_box["menu"].configure(bg=BG, fg=TEXT)
        adjustment_box.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        adjustment_row = tk.Frame(adjust_group, bg=PANEL)
        adjustment_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        adjustment_percent = tk.Spinbox(
            adjustment_row,
            from_=-100,
            to=300,
            textvariable=self.adjustment_percent_var,
            width=5,
            bg=PANEL,
            fg=TEXT,
            relief=tk.FLAT,
            increment=5,
        )
        adjustment_percent.pack(side=tk.LEFT, padx=(0, 3))
        tk.Label(adjustment_row, text="%", bg=PANEL, fg=MUTED).pack(side=tk.LEFT)
        self._button(adjust_group, "◐ 적용 (⌘Y)", self.adjust_selected_images, width=11).pack(
            side=tk.TOP,
            fill=tk.X,
        )

        self.grid_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_grid_window)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        self.bind_all("<ButtonRelease-1>", self.end_drag_selection, add="+")
        self._bind_shortcuts()

    def _build_bottom_panel(self) -> None:
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
        self._button(prompt_header, "↺ 초기화 (⌘I)", self.reset_prompt).pack(side=tk.RIGHT)

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
        self._button(template_header, "↺ 기본값 (⌘B)", self.restore_builtin_template).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_header, "↻ 다시 읽기 (⌘L)", self.reload_template).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_header, "◆ 저장 (⌘S)", self.save_template).pack(side=tk.RIGHT)

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
        self._button(template_path_row, "⇄ 경로 (⌘3)", self.copy_template_path).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(template_path_row, "⌂ Finder", self.reveal_template_file).pack(
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
        self._button(style_header, "⇄ 원본 (⌘4)", self.copy_art_style_tokens).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(style_header, "↻ 다시 읽기", self.reload_art_style_tokens).pack(side=tk.RIGHT)

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
        self._button(style_path_row, "⇄ 경로 (⌘5)", self.copy_art_style_path).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        self._button(style_path_row, "⌂ Finder", self.reveal_art_style_file).pack(
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

    def _button(self, parent: tk.Widget, text: str, command, width: int | None = None) -> tk.Button:
        options = {"width": width} if width is not None else {}
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
            **options,
        )

    def _side_group(self, parent: tk.Widget, label: str) -> tk.Frame:
        group = tk.Frame(
            parent,
            bg=PANEL,
            padx=7,
            pady=7,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        group.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        tk.Label(
            group,
            text=label,
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        return group

    def toggle_bottom_panel(self) -> None:
        self._set_bottom_panel_visible(not self.bottom_panel_visible.get())

    def _set_bottom_panel_visible(self, visible: bool) -> None:
        self.bottom_panel_visible.set(visible)
        if visible:
            self.bottom_content.pack(side=tk.TOP, fill=tk.X, before=self.bottom_bar)
            self.bottom_toggle_button.configure(text="▾ 작업 패널 (⌘W)")
        else:
            self.bottom_content.pack_forget()
            self.bottom_toggle_button.configure(text="▴ 작업 패널 (⌘W)")

    def _bind_shortcuts(self) -> None:
        self._shortcut("<Command-o>", self.choose_root)
        self._shortcut("<Command-r>", self.rescan)
        self._shortcut("<Command-f>", self.reveal_asset_root)
        self._shortcut("<Command-u>", self.expand_all_groups)
        self._shortcut("<Command-j>", self.collapse_all_groups)
        self._shortcut("<Command-a>", self.select_all)
        self._shortcut("<Escape>", self.clear_selection)
        self._shortcut("<Delete>", self.delete_selected_images)
        self._shortcut("<BackSpace>", self.delete_selected_images)
        self._shortcut("<Command-m>", self.move_selected_images)
        self._shortcut("<Command-Key-1>", self.copy_relative_paths)
        self._shortcut("<Command-Key-2>", self.copy_absolute_paths)
        self._shortcut("<Command-c>", self.copy_codex_prompt)
        self._shortcut("<Command-t>", self.save_txt)
        self._shortcut("<Command-z>", self.resize_selected_images)
        self._shortcut("<Command-y>", self.adjust_selected_images)
        self._shortcut("<Command-g>", self.apply_transparency_to_selected_images)
        self._shortcut("<Command-k>", self.choose_transparent_color)
        self._shortcut("<Command-p>", self.apply_palette_to_selected_images)
        self._shortcut("<Command-v>", self.toggle_palette_preview)
        self._shortcut("<Command-e>", self.toggle_scroll_select)
        self._shortcut("<Command-w>", self.toggle_bottom_panel)
        self._shortcut("<Command-i>", self.reset_prompt)
        self._shortcut("<Command-b>", self.restore_builtin_template)
        self._shortcut("<Command-l>", self.reload_template)
        self._shortcut("<Command-s>", self.save_template)
        self._shortcut("<Command-Key-3>", self.copy_template_path)
        self._shortcut("<Command-Key-4>", self.copy_art_style_tokens)
        self._shortcut("<Command-Key-5>", self.copy_art_style_path)

    def _shortcut(self, sequence: str, command) -> None:
        self.bind_all(sequence, lambda event, action=command: self._run_shortcut(event, action))

    def _run_shortcut(self, event: tk.Event, command) -> str:
        if self._shortcut_should_use_text_default(event):
            return ""
        command()
        return "break"

    def _shortcut_should_use_text_default(self, event: tk.Event) -> bool:
        widget = event.widget
        if isinstance(widget, tk.Text):
            return True
        if isinstance(widget, tk.Entry) and event.keysym not in {"Escape"}:
            return True
        return False

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_grid_window(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.grid_window, width=event.width)
        self.render_grid()

    def _on_mousewheel(self, event: tk.Event) -> str:
        if not self._event_targets_asset_grid(event):
            return ""

        event_num = getattr(event, "num", None)
        if event_num == 4:
            units = -1
        elif event_num == 5:
            units = 1
        else:
            units, self.scroll_remainder = wheel_scroll_units(int(event.delta), self.scroll_remainder)

        if units:
            self.canvas.yview_scroll(units * 3, "units")
            if self.drag_selecting or self.scroll_select_var.get() or getattr(event, "state", 0) & 0x0001:
                self.after_idle(self.select_visible_images)
        return "break"

    def _event_targets_asset_grid(self, event: tk.Event) -> bool:
        widget = event.widget
        while widget is not None:
            if widget is self.canvas:
                return True
            widget = getattr(widget, "master", None)
        return self._pointer_is_over_asset_grid()

    def _pointer_is_over_asset_grid(self) -> bool:
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        while widget is not None:
            if widget is self.canvas:
                return True
            widget = getattr(widget, "master", None)
        return False

    def autoscroll_during_drag(self, event: tk.Event) -> None:
        canvas_top = self.canvas.winfo_rooty()
        canvas_bottom = canvas_top + self.canvas.winfo_height()
        if event.y_root < canvas_top + 28:
            self.canvas.yview_scroll(-2, "units")
        elif event.y_root > canvas_bottom - 28:
            self.canvas.yview_scroll(2, "units")
