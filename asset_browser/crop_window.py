"""Pixel-art image editor with original-coordinate crop tools."""

from __future__ import annotations

from pathlib import Path
import shutil
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

from .constants import BG, BORDER, MUTED, PANEL, SELECTED, TEXT
from .image_ops import (
    Image,
    ImageTk,
    crop_boxes_to_files,
    default_crop_output_path,
    draw_pixel_line,
    erase_pixel_line,
    flood_fill_image,
    expand_canvas_to_selection,
    replace_color,
    make_edge_connected_color_transparent,
    normalize_crop_box,
    save_cropped_image_to_file,
    save_rgba_image_to_file,
)
from .models import AssetImage
from .paths import paint_backup_root, relative_or_name
from .style_tokens import extract_palette_colors, hex_to_rgb, normalize_hex_color
from .ui_layout import touchpad_scroll_deltas

MAX_INITIAL_WIDTH = 980
MAX_INITIAL_HEIGHT = 620
MAX_UNDO_STEPS = 30
ZOOM_LEVELS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
KEY_ZOOM_LEVELS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
CANVAS_MARGIN = 48
EDITOR_BG = "#25262b"
CHECKER_LIGHT = "#90949d"
CHECKER_DARK = "#686c75"
TRANSPARENCY_BACKGROUNDS = ("체커", "밝게", "어둡게")
SOLID_TRANSPARENCY_BACKGROUNDS = {
    "밝게": "#f2f2f4",
    "어둡게": "#34363c",
}


def next_zoom_scale(current: float, direction: int) -> float:
    if direction > 0:
        return next((level for level in ZOOM_LEVELS if level > current + 0.01), ZOOM_LEVELS[-1])
    return next(
        (level for level in reversed(ZOOM_LEVELS) if level < current - 0.01),
        ZOOM_LEVELS[0],
    )


def checker_square_size(scale: float) -> int:
    """Keep transparency checks larger than the source-pixel grid."""
    return max(8, int(round(scale * 4)))


def next_transparency_background(current: str) -> str:
    try:
        index = TRANSPARENCY_BACKGROUNDS.index(current)
    except ValueError:
        return TRANSPARENCY_BACKGROUNDS[0]
    return TRANSPARENCY_BACKGROUNDS[(index + 1) % len(TRANSPARENCY_BACKGROUNDS)]


def composite_transparency_preview(
    image,
    display_size: tuple[int, int],
    scale: float,
    mode: str,
):
    """Render RGBA pixels over a clearly identifiable transparency background."""
    resampling = getattr(Image, "Resampling", Image)
    displayed = image.resize(display_size, resampling.NEAREST)
    solid_color = SOLID_TRANSPARENCY_BACKGROUNDS.get(mode)
    if solid_color is not None:
        background = Image.new("RGBA", display_size, solid_color)
    else:
        background = Image.new("RGBA", display_size, CHECKER_LIGHT)
        square_size = checker_square_size(scale)
        for y in range(0, display_size[1], square_size):
            for x in range(0, display_size[0], square_size):
                if (x // square_size + y // square_size) % 2:
                    background.paste(
                        CHECKER_DARK,
                        (
                            x,
                            y,
                            min(x + square_size, display_size[0]),
                            min(y + square_size, display_size[1]),
                        ),
                    )
    background.alpha_composite(displayed)
    return background


class ImageCropWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, asset: AssetImage, on_saved) -> None:
        super().__init__(parent)
        if Image is None or ImageTk is None:
            messagebox.showerror("Pillow 필요", "이미지 상세 편집에는 Pillow가 필요합니다.")
            self.destroy()
            return

        self.asset = asset
        self.on_saved = on_saved
        with Image.open(asset.path) as opened:
            self.original = opened.convert("RGBA")
        self.image_width, self.image_height = self.original.size
        self.scale = self._initial_scale()
        self.start: tuple[int, int] | None = None
        self.box: tuple[int, int, int, int] | None = None
        self.queued_boxes: list[tuple[int, int, int, int]] = []
        self.preview_ref: tk.PhotoImage | None = None
        self.rect_id: int | None = None
        self.queued_rect_ids: list[int] = []
        self.tool_buttons: dict[str, tk.Button] = {}
        self.last_draw_point: tuple[int, int] | None = None
        self.line_start: tuple[int, int] | None = None
        self.line_preview_id: int | None = None
        self.last_saved_path: Path | None = None
        self.image_id: int | None = None
        self.pixel_grid_ids: list[int] = []
        self.undo_stack: list = []
        self.redo_stack: list = []
        self.previous_tool_mode: str | None = None
        self.canvas_origin = (CANVAS_MARGIN, CANVAS_MARGIN)
        self.tool_mode = tk.StringVar(value="crop")
        self.paint_color_var = tk.StringVar(value="#2F6F73")
        self.replace_source_var = tk.StringVar(value="#FFFFFF")
        self.paint_tolerance_var = tk.IntVar(value=0)
        self.transparency_background_var = tk.StringVar(value=TRANSPARENCY_BACKGROUNDS[0])
        self.edit_dirty = False
        self.last_changed_pixels = 0
        self.project_root = getattr(parent, "project_root", asset.path.parent)
        selected_candidate = getattr(parent, "selected_palette_candidate_id", lambda: "")()
        self.palette_colors = extract_palette_colors(
            getattr(parent, "art_style_data", None),
            selected_candidate,
        )

        self.title(f"이미지 상세 - {asset.relative_path.name}")
        self.geometry("1080x760")
        self.minsize(720, 520)
        self.configure(bg=BG)

        self.info_var = tk.StringVar()
        self.document_var = tk.StringVar()
        self.tool_hint_var = tk.StringVar()
        self.zoom_var = tk.StringVar()
        self.selection_summary_var = tk.StringVar()
        self._build_ui()
        self._render_image()
        self._set_box((0, 0, min(32, self.image_width), min(32, self.image_height)))
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.grab_set()
        self.focus_set()

    def _build_ui(self) -> None:
        top_bar = tk.Frame(self, bg=PANEL, padx=8, pady=4)
        top_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(
            top_bar,
            textvariable=self.document_var,
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        context_bar = tk.Frame(self, bg=BG, padx=8, pady=4)
        context_bar.pack(side=tk.TOP, fill=tk.X)
        self.undo_button = self._button(context_bar, "↶ 되돌리기  ⌘Z", self.undo)
        self.undo_button.pack(side=tk.LEFT, padx=(0, 2))
        self.redo_button = self._button(context_bar, "↷ 다시 실행  ⇧⌘Z", self.redo)
        self.redo_button.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(
            context_bar,
            textvariable=self.tool_hint_var,
            bg=BG,
            fg=MUTED,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._button(context_bar, "−", self.zoom_out, width=3).pack(side=tk.LEFT, padx=(4, 1))
        tk.Label(
            context_bar,
            textvariable=self.zoom_var,
            bg=PANEL,
            fg=TEXT,
            width=7,
            padx=3,
            pady=3,
        ).pack(side=tk.LEFT)
        self._button(context_bar, "+", self.zoom_in, width=3).pack(side=tk.LEFT, padx=1)
        self._button(context_bar, "맞춤  F", self.fit_to_window).pack(side=tk.LEFT, padx=(1, 8))
        save_button = self._button(context_bar, "원본 저장  ⌘S", self.save_edited_image)
        save_button.configure(
            fg=SELECTED,
            highlightthickness=1,
            highlightbackground=SELECTED,
        )
        save_button.pack(side=tk.RIGHT)
        self.background_button = self._button(
            context_bar,
            "▧ 투명 보기: 체커  D",
            self.cycle_transparency_background,
        )
        self.background_button.pack(side=tk.RIGHT, padx=(4, 4))

        info = tk.Label(self, textvariable=self.info_var, bg=PANEL, fg=MUTED, anchor="w", padx=8, pady=4)
        info.pack(side=tk.BOTTOM, fill=tk.X)

        editor = tk.Frame(self, bg=BG)
        editor.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        editor.columnconfigure(1, weight=1)
        editor.rowconfigure(0, weight=1)

        tool_rail = tk.Frame(
            editor,
            bg=PANEL,
            padx=5,
            pady=6,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        tool_rail.grid(row=0, column=0, sticky="ns", padx=(6, 3), pady=6)
        self.tool_buttons["crop"] = self._tool_button(tool_rail, "✂\n선택 M", self.use_crop_tool)
        self.tool_buttons["pencil"] = self._tool_button(tool_rail, "✎\n펜 B", self.use_pencil_tool)
        self.tool_buttons["eraser"] = self._tool_button(tool_rail, "⌫\n지우개 E", self.use_eraser_tool)
        self.tool_buttons["line"] = self._tool_button(tool_rail, "╱\n직선 L", self.use_line_tool)
        self.tool_buttons["paint"] = self._tool_button(tool_rail, "▣\n채우기 G", self.use_paint_tool)
        self.tool_buttons["eyedropper"] = self._tool_button(
            tool_rail,
            "⌖\n스포이드 I",
            self.use_eyedropper_tool,
        )
        self.tool_buttons["hand"] = self._tool_button(tool_rail, "✋\n이동 H", self.use_hand_tool)
        self._tool_spacer(tool_rail)
        self._tool_button(tool_rail, "◫\n외곽 투명 T", self.apply_transparency)
        self._tool_button(tool_rail, "×\n영역 비우기 C", self.clear_queued_boxes)

        canvas_shell = tk.Frame(editor, bg=BG)
        canvas_shell.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)

        self.canvas = tk.Canvas(
            canvas_shell,
            bg=EDITOR_BG,
            cursor="crosshair",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        x_scroll = tk.Scrollbar(canvas_shell, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = tk.Scrollbar(canvas_shell, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas_shell.columnconfigure(0, weight=1)
        canvas_shell.rowconfigure(0, weight=1)

        inspector = tk.Frame(
            editor,
            bg=PANEL,
            padx=6,
            pady=6,
            highlightthickness=1,
            highlightbackground=BORDER,
            width=242,
        )
        inspector.grid(row=0, column=2, sticky="ns", padx=(3, 6), pady=6)
        inspector.grid_propagate(False)

        inspector_tabs = ttk.Notebook(inspector)
        inspector_tabs.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        color_panel = tk.Frame(inspector_tabs, bg=PANEL, padx=7, pady=7)
        selection_panel = tk.Frame(inspector_tabs, bg=PANEL, padx=7, pady=7)
        inspector_tabs.add(color_panel, text="색상")
        inspector_tabs.add(selection_panel, text="선택·저장")

        self._section_label(color_panel, "현재 색")
        color_row = tk.Frame(color_panel, bg=PANEL)
        color_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        self.paint_color_swatch = tk.Label(
            color_row,
            text="",
            bg=self.paint_color_var.get(),
            relief=tk.SOLID,
            borderwidth=1,
            width=5,
            padx=2,
            pady=8,
            cursor="pointinghand",
        )
        self.paint_color_swatch.pack(side=tk.LEFT, padx=(0, 5))
        self.paint_color_swatch.bind("<Button-1>", lambda _event: self.choose_paint_color())
        paint_color_entry = tk.Entry(
            color_row,
            textvariable=self.paint_color_var,
            bg=BG,
            fg=TEXT,
            relief=tk.FLAT,
            width=10,
        )
        paint_color_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        paint_color_entry.bind("<Return>", lambda _event: self.set_paint_color(self.paint_color_var.get()))
        paint_color_entry.bind("<FocusOut>", lambda _event: self.set_paint_color(self.paint_color_var.get()))
        self._section_label(color_panel, "팔레트", pady=(4, 4))
        palette_grid = tk.Frame(color_panel, bg=PANEL)
        palette_grid.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        self._add_palette_chips(palette_grid)
        tk.Label(color_panel, text="채우기 허용 범위", bg=PANEL, fg=MUTED, anchor="w").pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(6, 2),
        )
        tk.Scale(
            color_panel,
            from_=0,
            to=255,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.paint_tolerance_var,
            showvalue=True,
            bg=BG,
            fg=TEXT,
            troughcolor=PANEL,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            sliderlength=16,
        ).pack(side=tk.TOP, fill=tk.X)
        replace_row = tk.Frame(color_panel, bg=PANEL)
        replace_row.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))
        tk.Label(replace_row, text="치환할 색", bg=PANEL, fg=MUTED).pack(side=tk.LEFT)
        tk.Entry(
            replace_row,
            textvariable=self.replace_source_var,
            bg=BG,
            fg=TEXT,
            relief=tk.FLAT,
            width=9,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self._button(color_panel, "↔ 선택 색으로 전체 치환", self.replace_all_colors).pack(
            side=tk.TOP, fill=tk.X, pady=(4, 0)
        )

        self._section_label(selection_panel, "선택 영역")
        tk.Label(
            selection_panel,
            textvariable=self.selection_summary_var,
            bg=BG,
            fg=TEXT,
            anchor="w",
            justify=tk.LEFT,
            padx=6,
            pady=6,
        ).pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        self._button(selection_panel, "□ 32x32로 맞춤  X", self.fit_32).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(selection_panel, "+ 대기 영역에 추가  Q", self.queue_current_box).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(selection_panel, "× 대기 영역 비우기  C", self.clear_queued_boxes).pack(
            side=tk.TOP,
            fill=tk.X,
        )

        self._section_label(selection_panel, "내보내기", pady=(16, 4))
        self._button(selection_panel, "◆ 현재 영역 PNG 내보내기  ⌘E", self.save_crop).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(selection_panel, "◆ 대기 영역 모두 내보내기  ⇧⌘E", self.save_all_crops).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._section_label(selection_panel, "원본 이미지", pady=(16, 4))
        self._button(selection_panel, "▣ 선택 영역을 캔버스로 적용", self.save_canvas_to_selection).pack(
            side=tk.TOP, fill=tk.X, pady=(0, 4)
        )
        original_save = self._button(selection_panel, "⬇ 원본 저장  ⌘S", self.save_edited_image)
        original_save.configure(
            fg=SELECTED,
            highlightthickness=1,
            highlightbackground=SELECTED,
        )
        original_save.pack(side=tk.TOP, fill=tk.X)

        self._button(inspector, "닫기  Esc", self.request_close).pack(
            side=tk.BOTTOM,
            fill=tk.X,
            pady=(6, 0),
        )

        self.canvas.bind("<ButtonPress-1>", self._start_crop)
        self.canvas.bind("<B1-Motion>", self._drag_crop)
        self.canvas.bind("<ButtonRelease-1>", self._finish_crop)
        self.canvas.bind("<ButtonPress-2>", self.start_canvas_pan)
        self.canvas.bind("<B2-Motion>", self.continue_canvas_pan)
        self.canvas.bind("<MouseWheel>", self.on_canvas_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_canvas_shift_mousewheel)
        try:
            self.canvas.bind("<TouchpadScroll>", self.on_touchpad_scroll)
        except tk.TclError:
            pass
        self.bind("<Escape>", lambda _event: self.request_close())
        canvas_shortcuts = {
            "<Return>": self.queue_current_box,
            "q": self.queue_current_box,
            "m": self.use_crop_tool,
            "v": self.use_crop_tool,
            "b": self.use_pencil_tool,
            "e": self.use_eraser_tool,
            "l": self.use_line_tool,
            "g": self.use_paint_tool,
            "p": self.use_paint_tool,
            "i": self.use_eyedropper_tool,
            "h": self.use_hand_tool,
            "t": self.apply_transparency,
            "x": self.fit_32,
            "c": self.clear_queued_boxes,
            "f": self.fit_to_window,
            "d": self.cycle_transparency_background,
        }
        for sequence, command in canvas_shortcuts.items():
            self.bind(
                sequence,
                lambda event, action=command: self._run_canvas_shortcut(event, action),
            )
        self.bind(
            "<KeyPress-space>",
            lambda event: self._run_canvas_shortcut(
                event,
                lambda: self.start_quick_pan(event),
            ),
        )
        self.bind(
            "<KeyRelease-space>",
            lambda event: self._run_canvas_shortcut(
                event,
                lambda: self.finish_quick_pan(event),
            ),
        )
        self.bind("<Command-z>", lambda _event: self.undo())
        self.bind("<Command-Shift-z>", lambda _event: self.redo())
        self.bind("<Control-z>", lambda _event: self.undo())
        self.bind("<Control-Shift-z>", lambda _event: self.redo())
        self.bind("<Command-s>", lambda _event: self.save_edited_image())
        self.bind("<Command-e>", lambda _event: self.save_crop())
        self.bind("<Command-Shift-e>", lambda _event: self.save_all_crops())
        self.bind("<Control-s>", lambda _event: self.save_edited_image())
        self.bind("<Control-e>", lambda _event: self.save_crop())
        self.bind("<Control-Shift-e>", lambda _event: self.save_all_crops())
        for key, zoom in zip(("1", "2", "3", "4", "5", "6"), KEY_ZOOM_LEVELS, strict=True):
            self.bind(
                key,
                lambda event, value=zoom: self._run_canvas_shortcut(
                    event,
                    lambda: self.set_zoom(value),
                ),
            )
        self._refresh_tool_buttons()
        self._refresh_history_buttons()

    def _add_palette_chips(self, parent: tk.Widget) -> None:
        if not self.palette_colors:
            tk.Label(
                parent,
                text="스타일 팔레트 없음",
                bg=PANEL,
                fg=MUTED,
                anchor="w",
            ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=2, pady=4)
            return
        for index, rgb in enumerate(self.palette_colors[:12]):
            color = self._rgb_to_hex(rgb)
            chip = tk.Label(
                parent,
                text="",
                bg=color,
                relief=tk.SOLID,
                borderwidth=1,
                width=4,
                padx=0,
                pady=5,
                cursor="pointinghand",
            )
            chip.grid(row=index // 4, column=index % 4, sticky="ew", padx=2, pady=2)
            chip.bind("<Button-1>", lambda _event, value=color: self.set_paint_color(value))
        for column in range(4):
            parent.columnconfigure(column, weight=1)

    def _run_canvas_shortcut(self, event: tk.Event, command) -> str:
        if isinstance(event.widget, (tk.Entry, tk.Spinbox)):
            return ""
        return command()

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
            padx=9,
            pady=3,
            highlightthickness=0,
            **options,
        )

    def _tool_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=BG,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            relief=tk.FLAT,
            width=8,
            height=2,
            padx=2,
            pady=2,
            highlightthickness=0,
            justify=tk.CENTER,
        )
        button.pack(side=tk.TOP, pady=(0, 3))
        return button

    def _tool_spacer(self, parent: tk.Widget) -> None:
        tk.Frame(parent, bg=PANEL, height=8).pack(side=tk.TOP, fill=tk.X)

    def _section_label(self, parent: tk.Widget, text: str, pady: tuple[int, int] = (0, 4)) -> None:
        tk.Label(
            parent,
            text=text,
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(side=tk.TOP, fill=tk.X, pady=pady)

    def _refresh_tool_buttons(self) -> None:
        active_tool = self.tool_mode.get()
        for name, button in self.tool_buttons.items():
            if name == active_tool:
                button.configure(
                    bg=BG,
                    fg=SELECTED,
                    activebackground=PANEL,
                    relief=tk.SUNKEN,
                    highlightthickness=2,
                    highlightbackground=SELECTED,
                )
            else:
                button.configure(
                    bg=BG,
                    fg=TEXT,
                    activebackground=PANEL,
                    relief=tk.FLAT,
                    highlightthickness=0,
                )
        self.tool_hint_var.set(
            {
                "crop": "선택: 드래그로 크롭 영역 지정",
                "pencil": "펜: 1px 도트 그리기",
                "eraser": "지우개: 픽셀 투명화",
                "line": "직선: 시작점에서 끝점까지 드래그",
                "paint": "채우기: 연결된 영역 채우기",
                "eyedropper": "스포이드: 캔버스에서 색 추출",
                "hand": "이동: 드래그로 캔버스 이동  (Space 임시 전환)",
            }.get(active_tool, "")
        )
        self.canvas.configure(cursor="fleur" if active_tool == "hand" else "crosshair")

    def _refresh_history_buttons(self) -> None:
        self.undo_button.configure(state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        self.redo_button.configure(state=tk.NORMAL if self.redo_stack else tk.DISABLED)

    def _record_undo(self, snapshot) -> None:
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > MAX_UNDO_STEPS:
            del self.undo_stack[0]
        self.redo_stack.clear()
        self._refresh_history_buttons()

    def _restore_history_image(self, image) -> None:
        previous_size = (self.image_width, self.image_height)
        self.original = image.copy()
        self.image_width, self.image_height = self.original.size
        if self.original.size != previous_size:
            self.clear_queued_boxes()
            self.box = (0, 0, min(32, self.image_width), min(32, self.image_height))
        self.edit_dirty = True
        self.last_changed_pixels = 0
        self._render_image()
        if self.box is not None:
            self._set_box(self.box)
        self._refresh_history_buttons()
        self._show_box_status()

    def undo(self) -> str:
        if not self.undo_stack:
            return "break"
        self.redo_stack.append(self.original.copy())
        self._restore_history_image(self.undo_stack.pop())
        return "break"

    def redo(self) -> str:
        if not self.redo_stack:
            return "break"
        self.undo_stack.append(self.original.copy())
        self._restore_history_image(self.redo_stack.pop())
        return "break"

    def request_close(self) -> str:
        if self.edit_dirty:
            choice = messagebox.askyesnocancel(
                "편집 내용 저장",
                "저장되지 않은 편집 내용이 있습니다.\n원본 이미지에 저장하고 닫을까요?",
                parent=self,
            )
            if choice is None:
                return "break"
            if choice:
                self.save_edited_image()
                if self.edit_dirty:
                    return "break"
        self.destroy()
        return "break"

    def _initial_scale(self) -> float:
        scale = min(MAX_INITIAL_WIDTH / self.image_width, MAX_INITIAL_HEIGHT / self.image_height)
        return max(ZOOM_LEVELS[0], min(8.0, scale))

    def _render_image(self) -> None:
        display_size = (
            max(1, int(self.image_width * self.scale)),
            max(1, int(self.image_height * self.scale)),
        )
        preview = composite_transparency_preview(
            self.original,
            display_size,
            self.scale,
            self.transparency_background_var.get(),
        )
        self.preview_ref = ImageTk.PhotoImage(preview)

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        origin_x = max(CANVAS_MARGIN, (canvas_width - display_size[0]) // 2)
        origin_y = max(CANVAS_MARGIN, (canvas_height - display_size[1]) // 2)
        self.canvas_origin = (origin_x, origin_y)
        if self.image_id is None:
            self.image_id = self.canvas.create_image(
                origin_x,
                origin_y,
                image=self.preview_ref,
                anchor="nw",
            )
        else:
            self.canvas.itemconfigure(self.image_id, image=self.preview_ref)
            self.canvas.coords(self.image_id, origin_x, origin_y)
        scroll_width = max(canvas_width, origin_x + display_size[0] + CANVAS_MARGIN)
        scroll_height = max(canvas_height, origin_y + display_size[1] + CANVAS_MARGIN)
        self.canvas.configure(scrollregion=(0, 0, scroll_width, scroll_height))
        self._redraw_overlays()
        self._render_pixel_grid()
        self.zoom_var.set(f"{round(self.scale * 100)}%")

    def cycle_transparency_background(self) -> str:
        mode = next_transparency_background(self.transparency_background_var.get())
        self.transparency_background_var.set(mode)
        self.background_button.configure(text=f"▧ 투명 보기: {mode}  D")
        self._render_image()
        self._show_box_status()
        return "break"

    def _to_original_point(self, event: tk.Event) -> tuple[int, int]:
        origin_x, origin_y = self.canvas_origin
        x = int((self.canvas.canvasx(event.x) - origin_x) / self.scale)
        y = int((self.canvas.canvasy(event.y) - origin_y) / self.scale)
        return (
            max(0, min(x, self.image_width)),
            max(0, min(y, self.image_height)),
        )

    def _event_is_over_image(self, event: tk.Event) -> bool:
        origin_x, origin_y = self.canvas_origin
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        return (
            origin_x <= canvas_x < origin_x + self.image_width * self.scale
            and origin_y <= canvas_y < origin_y + self.image_height * self.scale
        )

    def _display_box(self, box: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
        origin_x, origin_y = self.canvas_origin
        x1, y1, x2, y2 = box
        return (
            origin_x + x1 * self.scale,
            origin_y + y1 * self.scale,
            origin_x + x2 * self.scale,
            origin_y + y2 * self.scale,
        )

    def _redraw_overlays(self) -> None:
        if self.rect_id is not None and self.box is not None:
            self.canvas.coords(self.rect_id, *self._display_box(self.box))
        for rect_id, box in zip(self.queued_rect_ids, self.queued_boxes, strict=False):
            self.canvas.coords(rect_id, *self._display_box(box))
        if self.line_preview_id is not None and self.line_start is not None:
            self.canvas.coords(
                self.line_preview_id,
                *self._display_line_coords(self.line_start, self.line_start),
            )

    def _render_pixel_grid(self) -> None:
        for line_id in self.pixel_grid_ids:
            self.canvas.delete(line_id)
        self.pixel_grid_ids.clear()
        if self.scale < 8 or self.image_width > 256 or self.image_height > 256:
            return

        origin_x, origin_y = self.canvas_origin
        width = self.image_width * self.scale
        height = self.image_height * self.scale
        for x in range(self.image_width + 1):
            screen_x = origin_x + x * self.scale
            self.pixel_grid_ids.append(
                self.canvas.create_line(
                    screen_x,
                    origin_y,
                    screen_x,
                    origin_y + height,
                    fill="#000000",
                    stipple="gray50",
                    tags=("pixel_grid",),
                )
            )
        for y in range(self.image_height + 1):
            screen_y = origin_y + y * self.scale
            self.pixel_grid_ids.append(
                self.canvas.create_line(
                    origin_x,
                    screen_y,
                    origin_x + width,
                    screen_y,
                    fill="#000000",
                    stipple="gray50",
                    tags=("pixel_grid",),
                )
            )
        if self.image_id is not None:
            self.canvas.tag_raise("pixel_grid", self.image_id)
        if self.rect_id is not None:
            self.canvas.tag_raise(self.rect_id)
        for rect_id in self.queued_rect_ids:
            self.canvas.tag_raise(rect_id)

    def set_zoom(self, scale: float) -> str:
        scale = max(ZOOM_LEVELS[0], min(ZOOM_LEVELS[-1], float(scale)))
        if abs(scale - self.scale) < 0.01:
            return "break"

        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        origin_x, origin_y = self.canvas_origin
        center_x = (self.canvas.canvasx(canvas_width / 2) - origin_x) / self.scale
        center_y = (self.canvas.canvasy(canvas_height / 2) - origin_y) / self.scale
        self.scale = scale
        self._render_image()
        self.update_idletasks()
        new_origin_x, new_origin_y = self.canvas_origin
        scroll_region = tuple(float(value) for value in self.canvas.cget("scrollregion").split())
        total_width = max(1.0, scroll_region[2] - scroll_region[0])
        total_height = max(1.0, scroll_region[3] - scroll_region[1])
        target_x = new_origin_x + center_x * self.scale - canvas_width / 2
        target_y = new_origin_y + center_y * self.scale - canvas_height / 2
        self.canvas.xview_moveto(max(0.0, min(1.0, target_x / total_width)))
        self.canvas.yview_moveto(max(0.0, min(1.0, target_y / total_height)))
        self._show_box_status()
        return "break"

    def zoom_in(self) -> str:
        return self.set_zoom(next_zoom_scale(self.scale, 1))

    def zoom_out(self) -> str:
        return self.set_zoom(next_zoom_scale(self.scale, -1))

    def fit_to_window(self) -> str:
        available_width = max(1, self.canvas.winfo_width() - CANVAS_MARGIN * 2)
        available_height = max(1, self.canvas.winfo_height() - CANVAS_MARGIN * 2)
        scale = min(available_width / self.image_width, available_height / self.image_height)
        self.scale = max(ZOOM_LEVELS[0], min(ZOOM_LEVELS[-1], scale))
        self._render_image()
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
        self._show_box_status()
        return "break"

    def _to_pixel_point(self, event: tk.Event) -> tuple[int, int]:
        x, y = self._to_original_point(event)
        return (
            min(x, self.image_width - 1),
            min(y, self.image_height - 1),
        )

    def _start_crop(self, event: tk.Event) -> None:
        if self.tool_mode.get() == "hand":
            self.start_canvas_pan(event)
            return
        if not self._event_is_over_image(event):
            return
        if self.tool_mode.get() == "eyedropper":
            self.pick_color_at_event(event)
            return
        if self.tool_mode.get() == "paint":
            self.paint_at_event(event)
            return
        if self.tool_mode.get() in {"pencil", "eraser"}:
            self.start_pixel_stroke(event)
            return
        if self.tool_mode.get() == "line":
            self.start_line(event)
            return
        self.start = self._to_original_point(event)
        self._set_box((*self.start, *self.start))

    def _drag_crop(self, event: tk.Event) -> None:
        if self.tool_mode.get() == "hand":
            self.continue_canvas_pan(event)
            return
        if self.tool_mode.get() in {"pencil", "eraser"}:
            self.continue_pixel_stroke(event)
            return
        if self.tool_mode.get() == "line":
            self.preview_line(event)
            return
        if self.tool_mode.get() == "paint":
            return
        if self.tool_mode.get() != "crop":
            return
        if self.start is None:
            return
        end = self._to_original_point(event)
        box = normalize_crop_box(self.start, end, (self.image_width, self.image_height))
        if box is not None:
            self._set_box(box)

    def _finish_crop(self, event: tk.Event) -> None:
        if self.tool_mode.get() in {"pencil", "eraser"}:
            self.finish_pixel_stroke()
            return
        if self.tool_mode.get() == "line":
            self.finish_line(event)
            return
        if self.tool_mode.get() != "crop":
            return
        if self.start is None:
            return
        end = self._to_original_point(event)
        box = normalize_crop_box(self.start, end, (self.image_width, self.image_height))
        if box is None:
            x, y = self.start
            box = normalize_crop_box((x, y), (x + 32, y + 32), (self.image_width, self.image_height))
        if box is not None:
            self._set_box(box)
        self.start = None

    def _set_box(self, box: tuple[int, int, int, int]) -> None:
        self.box = box
        display_box = self._display_box(box)
        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(*display_box, outline=SELECTED, width=2)
        else:
            self.canvas.coords(self.rect_id, *display_box)
        self._show_box_status()

    def _show_box_status(self) -> None:
        if self.box is None:
            return
        x1, y1, x2, y2 = self.box
        self.selection_summary_var.set(
            f"X {x1}   Y {y1}\nW {x2 - x1}   H {y2 - y1}\n대기 영역 {len(self.queued_boxes)}개"
        )
        status = f"선택 영역: x={x1}, y={y1}, w={x2 - x1}, h={y2 - y1}"
        if self.queued_boxes:
            status = f"{status} | 대기 {len(self.queued_boxes)}개"
        if self.last_saved_path is not None:
            status = f"{status} | 마지막 저장: {self.last_saved_path.name}"
        if self.edit_dirty:
            status = f"{status} | 편집 미저장"
        if self.last_changed_pixels:
            status = f"{status} | 변경 {self.last_changed_pixels}픽셀"
        transparency_mode = self.transparency_background_var.get()
        transparency_help = " (무늬 부분은 투명)" if transparency_mode == "체커" else ""
        status = (
            f"{status} | 도구: {self._tool_mode_label()} | 색: {self.paint_color_var.get()}"
            f" | 투명 보기: {transparency_mode}{transparency_help}"
        )
        self.info_var.set(status)
        dirty_mark = "● " if self.edit_dirty else ""
        self.document_var.set(
            f"{dirty_mark}{self.asset.relative_path.as_posix()}   {self.image_width}x{self.image_height}"
        )
        self.title(f"{'*' if self.edit_dirty else ''}이미지 편집 - {self.asset.relative_path.name}")

    def _tool_mode_label(self) -> str:
        return {
            "crop": "크롭",
            "pencil": "펜",
            "eraser": "지우개",
            "line": "직선",
            "paint": "채우기",
            "eyedropper": "스포이드",
            "hand": "이동",
        }.get(self.tool_mode.get(), self.tool_mode.get())

    def use_crop_tool(self) -> str:
        self.tool_mode.set("crop")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_pencil_tool(self) -> str:
        self.tool_mode.set("pencil")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_eraser_tool(self) -> str:
        self.tool_mode.set("eraser")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_line_tool(self) -> str:
        self.tool_mode.set("line")
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_paint_tool(self) -> str:
        self.tool_mode.set("paint")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_eyedropper_tool(self) -> str:
        self.tool_mode.set("eyedropper")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def use_hand_tool(self) -> str:
        self.tool_mode.set("hand")
        self.clear_line_preview()
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def start_quick_pan(self, _event: tk.Event) -> str:
        if self.previous_tool_mode is None:
            self.previous_tool_mode = self.tool_mode.get()
            self.tool_mode.set("hand")
            self._refresh_tool_buttons()
            self._show_box_status()
        return "break"

    def finish_quick_pan(self, _event: tk.Event) -> str:
        if self.previous_tool_mode is not None:
            self.tool_mode.set(self.previous_tool_mode)
            self.previous_tool_mode = None
            self._refresh_tool_buttons()
            self._show_box_status()
        return "break"

    def start_canvas_pan(self, event: tk.Event) -> str:
        self.canvas.scan_mark(event.x, event.y)
        return "break"

    def continue_canvas_pan(self, event: tk.Event) -> str:
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def on_canvas_mousewheel(self, event: tk.Event) -> str:
        if 0 < abs(event.delta) < 120:
            scroll_region = tuple(float(value) for value in self.canvas.cget("scrollregion").split())
            total_height = max(1.0, scroll_region[3] - scroll_region[1])
            self.canvas.yview_moveto(self.canvas.yview()[0] - event.delta / total_height)
            return "break"
        if event.delta > 0:
            return self.zoom_in()
        if event.delta < 0:
            return self.zoom_out()
        return "break"

    def on_canvas_shift_mousewheel(self, event: tk.Event) -> str:
        if event.delta:
            self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def on_touchpad_scroll(self, event: tk.Event) -> str:
        delta_x, delta_y = touchpad_scroll_deltas(int(event.delta))
        scroll_region = tuple(float(value) for value in self.canvas.cget("scrollregion").split())
        total_width = max(1.0, scroll_region[2] - scroll_region[0])
        total_height = max(1.0, scroll_region[3] - scroll_region[1])
        if delta_x:
            self.canvas.xview_moveto(self.canvas.xview()[0] - delta_x / total_width)
        if delta_y:
            self.canvas.yview_moveto(self.canvas.yview()[0] - delta_y / total_height)
        return "break"

    def choose_paint_color(self) -> str:
        _rgb, hex_color = colorchooser.askcolor(
            color=self.paint_color_var.get(),
            title="페인트 색상 선택",
        )
        if hex_color:
            self.set_paint_color(hex_color)
        return "break"

    def set_paint_color(self, color: str) -> None:
        normalized = normalize_hex_color(color)
        if hex_to_rgb(normalized) is None:
            return
        self.paint_color_var.set(normalized)
        self.paint_color_swatch.configure(bg=normalized)
        self._show_box_status()

    def pick_color_at_event(self, event: tk.Event) -> str:
        point = self._to_pixel_point(event)
        red, green, blue, _alpha = self.original.getpixel(point)
        self.set_paint_color(self._rgb_to_hex((red, green, blue)))
        self.tool_mode.set("paint")
        self._refresh_tool_buttons()
        self._show_box_status()
        return "break"

    def start_pixel_stroke(self, event: tk.Event) -> str:
        self._record_undo(self.original.copy())
        point = self._to_pixel_point(event)
        self.last_draw_point = point
        self.apply_pixel_line(point, point)
        return "break"

    def continue_pixel_stroke(self, event: tk.Event) -> str:
        point = self._to_pixel_point(event)
        start = self.last_draw_point or point
        self.apply_pixel_line(start, point)
        self.last_draw_point = point
        return "break"

    def finish_pixel_stroke(self) -> str:
        self.last_draw_point = None
        return "break"

    def start_line(self, event: tk.Event) -> str:
        point = self._to_pixel_point(event)
        self.line_start = point
        self.preview_line(event)
        return "break"

    def preview_line(self, event: tk.Event) -> str:
        if self.line_start is None:
            return "break"
        end = self._to_pixel_point(event)
        coords = self._display_line_coords(self.line_start, end)
        if self.line_preview_id is None:
            self.line_preview_id = self.canvas.create_line(
                *coords,
                fill=SELECTED,
                width=1,
                dash=(3, 2),
            )
        else:
            self.canvas.coords(self.line_preview_id, *coords)
        self._show_box_status()
        return "break"

    def finish_line(self, event: tk.Event) -> str:
        if self.line_start is None:
            return "break"
        start = self.line_start
        end = self._to_pixel_point(event)
        self.line_start = None
        self.clear_line_preview()
        self._record_undo(self.original.copy())
        self.apply_pixel_line(start, end)
        return "break"

    def clear_line_preview(self) -> None:
        if self.line_preview_id is not None:
            self.canvas.delete(self.line_preview_id)
            self.line_preview_id = None
        self.line_start = None

    def _display_line_coords(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> tuple[float, float, float, float]:
        origin_x, origin_y = self.canvas_origin
        return (
            origin_x + (start[0] + 0.5) * self.scale,
            origin_y + (start[1] + 0.5) * self.scale,
            origin_x + (end[0] + 0.5) * self.scale,
            origin_y + (end[1] + 0.5) * self.scale,
        )

    def apply_pixel_line(self, start: tuple[int, int], end: tuple[int, int]) -> str:
        if self.tool_mode.get() == "eraser":
            self.original, changed = erase_pixel_line(self.original, start, end)
        else:
            rgb = hex_to_rgb(self.paint_color_var.get())
            if rgb is None:
                messagebox.showerror("색상 오류", f"잘못된 색상입니다: {self.paint_color_var.get()}")
                return "break"
            self.original, changed = draw_pixel_line(self.original, start, end, (*rgb, 255))

        self.last_changed_pixels = changed
        if changed:
            self.edit_dirty = True
            self._render_image()
        self._show_box_status()
        return "break"

    def paint_at_event(self, event: tk.Event) -> str:
        rgb = hex_to_rgb(self.paint_color_var.get())
        if rgb is None:
            messagebox.showerror("색상 오류", f"잘못된 색상입니다: {self.paint_color_var.get()}")
            return "break"

        point = self._to_pixel_point(event)
        before = self.original.copy()
        painted, changed = flood_fill_image(
            self.original,
            point,
            rgb,
            self.paint_tolerance_var.get(),
        )
        self.last_changed_pixels = changed
        if changed:
            self._record_undo(before)
            self.original = painted
            self.edit_dirty = True
            self._render_image()
        self._show_box_status()
        return "break"

    def apply_transparency(self) -> str:
        rgb = hex_to_rgb(self.paint_color_var.get())
        if rgb is None:
            messagebox.showerror("색상 오류", f"잘못된 색상입니다: {self.paint_color_var.get()}")
            return "break"

        before = self.original.copy()
        changed_image = make_edge_connected_color_transparent(
            self.original,
            rgb,
            self.paint_tolerance_var.get(),
        )
        changed = sum(
            1 for old, new in zip(before.getdata(), changed_image.getdata(), strict=True) if old != new
        )
        self.last_changed_pixels = changed
        if changed:
            self._record_undo(before)
            self.original = changed_image
            self.edit_dirty = True
            self._render_image()
        self._show_box_status()
        return "break"

    def replace_all_colors(self) -> str:
        source = hex_to_rgb(self.replace_source_var.get())
        target = hex_to_rgb(self.paint_color_var.get())
        if source is None or target is None:
            messagebox.showerror("색상 오류", "치환할 색과 대상 색을 #RRGGBB 형식으로 입력하세요.")
            return "break"
        before = self.original.copy()
        replaced, changed = replace_color(
            self.original,
            source,
            target,
            self.paint_tolerance_var.get(),
        )
        self.last_changed_pixels = changed
        if changed:
            self._record_undo(before)
            self.original = replaced
            self.edit_dirty = True
            self._render_image()
        self._show_box_status()
        return "break"

    def save_canvas_to_selection(self) -> str:
        if self.box is None:
            messagebox.showinfo("선택 없음", "캔버스로 사용할 영역을 먼저 선택하세요.")
            return "break"
        try:
            before = self.original.copy()
            backup_root = paint_backup_root(self.project_root)
            backup_path = backup_root / relative_or_name(self.asset.path, self.project_root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.asset.path, backup_path)
            self.original = expand_canvas_to_selection(self.original, self.box)
            save_rgba_image_to_file(self.original, self.asset.path)
        except Exception as exc:
            messagebox.showerror("캔버스 저장 실패", str(exc))
            return "break"
        self.image_width, self.image_height = self.original.size
        self._record_undo(before)
        self.edit_dirty = False
        self.last_saved_path = self.asset.path
        self.on_saved(self.asset.path)
        self._render_image()
        self._set_box((0, 0, self.image_width, self.image_height))
        self._show_box_status()
        return "break"

    def save_edited_image(self) -> str:
        if not self.edit_dirty:
            self._show_box_status()
            return "break"

        try:
            backup_root = paint_backup_root(self.project_root)
            backup_path = backup_root / relative_or_name(self.asset.path, self.project_root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.asset.path, backup_path)
            save_rgba_image_to_file(self.original, self.asset.path)
        except Exception as exc:
            messagebox.showerror("편집 저장 실패", str(exc))
            return "break"

        self.edit_dirty = False
        self.last_saved_path = self.asset.path
        self.on_saved(self.asset.path)
        self._show_box_status()
        return "break"

    @staticmethod
    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    def fit_32(self) -> str:
        if self.box is None:
            return "break"
        x1, y1, _, _ = self.box
        box = normalize_crop_box((x1, y1), (x1 + 32, y1 + 32), (self.image_width, self.image_height))
        if box is not None:
            self._set_box(box)
        return "break"

    def queue_current_box(self) -> str:
        if self.box is None:
            messagebox.showinfo("선택 없음", "추가할 크롭 영역을 먼저 선택하세요.")
            return "break"

        self.queued_boxes.append(self.box)
        rect_id = self.canvas.create_rectangle(
            *self._display_box(self.box),
            outline=MUTED,
            width=1,
        )
        self.queued_rect_ids.append(rect_id)
        self._show_box_status()
        return "break"

    def clear_queued_boxes(self) -> str:
        for rect_id in self.queued_rect_ids:
            self.canvas.delete(rect_id)
        self.queued_boxes.clear()
        self.queued_rect_ids.clear()
        self._show_box_status()
        return "break"

    def save_shortcut(self) -> str:
        return self.save_edited_image()

    def save_crop(self) -> str:
        if self.box is None:
            messagebox.showinfo("선택 없음", "크롭할 영역을 먼저 선택하세요.")
            return "break"

        target = default_crop_output_path(self.asset.path, self.box)

        try:
            save_cropped_image_to_file(self.original, target, self.box)
        except Exception as exc:
            messagebox.showerror("크롭 저장 실패", str(exc))
            return "break"

        self.last_saved_path = target
        self.on_saved(target)
        self._show_box_status()
        return "break"

    def save_all_crops(self) -> str:
        boxes = list(self.queued_boxes)
        if not boxes and self.box is not None:
            boxes = [self.box]
        if not boxes:
            messagebox.showinfo("선택 없음", "저장할 크롭 영역을 먼저 선택하세요.")
            return "break"

        try:
            saved_paths = crop_boxes_to_files(self.asset.path, boxes, self.original)
        except Exception as exc:
            messagebox.showerror("크롭 저장 실패", str(exc))
            return "break"

        self.last_saved_path = saved_paths[-1]
        self.on_saved(saved_paths[-1])
        self.clear_queued_boxes()
        self._show_box_status()
        return "break"
