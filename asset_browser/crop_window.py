"""Original-coordinate crop window for large source images."""

from __future__ import annotations

from pathlib import Path
import shutil
import tkinter as tk
from tkinter import colorchooser, messagebox

from .constants import BG, BORDER, MUTED, PANEL, SELECTED, TEXT
from .image_ops import (
    Image,
    ImageTk,
    crop_boxes_to_files,
    default_crop_output_path,
    draw_pixel_line,
    erase_pixel_line,
    flood_fill_image,
    make_edge_connected_color_transparent,
    normalize_crop_box,
    save_cropped_image_to_file,
    save_rgba_image_to_file,
)
from .models import AssetImage
from .paths import paint_backup_root, relative_or_name
from .style_tokens import extract_palette_colors, hex_to_rgb, normalize_hex_color

MAX_INITIAL_WIDTH = 980
MAX_INITIAL_HEIGHT = 620

class ImageCropWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, asset: AssetImage, on_saved) -> None:
        super().__init__(parent)
        if Image is None or ImageTk is None:
            messagebox.showerror("Pillow 필요", "원본 기준 이미지 크롭에는 Pillow가 필요합니다.")
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
        self.tool_mode = tk.StringVar(value="crop")
        self.paint_color_var = tk.StringVar(value="#2F6F73")
        self.paint_tolerance_var = tk.IntVar(value=0)
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
        self._build_ui()
        self._render_image()
        self._set_box((0, 0, min(32, self.image_width), min(32, self.image_height)))
        self.grab_set()
        self.focus_set()

    def _build_ui(self) -> None:
        top_bar = tk.Frame(self, bg=PANEL, padx=10, pady=6)
        top_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(
            top_bar,
            text=f"{self.asset.relative_path.as_posix()}  {self.image_width}x{self.image_height}",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        info = tk.Label(self, textvariable=self.info_var, bg=PANEL, fg=MUTED, anchor="w", padx=10, pady=4)
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
        tool_rail.grid(row=0, column=0, sticky="ns", padx=(8, 4), pady=8)
        self.tool_buttons["crop"] = self._tool_button(tool_rail, "✂\n크롭\nV", self.use_crop_tool)
        self.tool_buttons["pencil"] = self._tool_button(tool_rail, "✎\n펜\nB", self.use_pencil_tool)
        self.tool_buttons["eraser"] = self._tool_button(tool_rail, "⌫\n지우개\nE", self.use_eraser_tool)
        self.tool_buttons["line"] = self._tool_button(tool_rail, "╱\n직선\nL", self.use_line_tool)
        self.tool_buttons["paint"] = self._tool_button(tool_rail, "▣\n채우기\nP", self.use_paint_tool)
        self.tool_buttons["eyedropper"] = self._tool_button(
            tool_rail,
            "⌖\n스포이드\nI",
            self.use_eyedropper_tool,
        )
        self._tool_button(tool_rail, "◫\n외곽\nT", self.apply_transparency)
        self._tool_spacer(tool_rail)
        self._tool_button(tool_rail, "×\n초기화\nC", self.clear_queued_boxes)

        canvas_shell = tk.Frame(editor, bg=BG)
        canvas_shell.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)

        self.canvas = tk.Canvas(canvas_shell, bg=BG, highlightthickness=1, highlightbackground=BORDER)
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
            padx=8,
            pady=8,
            highlightthickness=1,
            highlightbackground=BORDER,
            width=230,
        )
        inspector.grid(row=0, column=2, sticky="ns", padx=(4, 8), pady=8)
        inspector.grid_propagate(False)

        self._section_label(inspector, "색상")
        color_row = tk.Frame(inspector, bg=PANEL)
        color_row.pack(side=tk.TOP, fill=tk.X)
        self.paint_color_swatch = tk.Button(
            color_row,
            text="현재 색",
            command=self.choose_paint_color,
            bg=self.paint_color_var.get(),
            activebackground=self.paint_color_var.get(),
            fg=TEXT,
            relief=tk.FLAT,
            width=9,
            padx=2,
            pady=4,
            highlightthickness=0,
        )
        self.paint_color_swatch.pack(side=tk.LEFT, padx=(0, 5))
        self._add_palette_chips(color_row)
        tk.Label(inspector, text="허용 범위", bg=PANEL, fg=MUTED, anchor="w").pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(10, 2),
        )
        tk.Spinbox(
            inspector,
            from_=0,
            to=255,
            textvariable=self.paint_tolerance_var,
            width=8,
            bg=BG,
            fg=TEXT,
            relief=tk.FLAT,
            increment=4,
        ).pack(side=tk.TOP, anchor="w")

        self._section_label(inspector, "크롭", pady=(16, 4))
        self._button(inspector, "□ 32x32 맞춤 (X)", self.fit_32, width=21).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(inspector, "+ 영역 추가 (Space)", self.queue_current_box, width=21).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )

        self._section_label(inspector, "저장", pady=(16, 4))
        self._button(inspector, "◆ 크롭 저장 (⌘S)", self.save_crop, width=21).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(inspector, "◆ 대기 모두 저장 (⇧⌘S)", self.save_all_crops, width=21).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )
        self._button(inspector, "⬇ 원본 덮어쓰기 (⌘P)", self.save_edited_image, width=21).pack(
            side=tk.TOP,
            fill=tk.X,
            pady=(0, 4),
        )

        tk.Frame(inspector, bg=PANEL).pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._button(inspector, "닫기 (Esc)", self.destroy, width=21).pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.bind("<ButtonPress-1>", self._start_crop)
        self.canvas.bind("<B1-Motion>", self._drag_crop)
        self.canvas.bind("<ButtonRelease-1>", self._finish_crop)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self.queue_current_box())
        self.bind("<space>", lambda _event: self.queue_current_box())
        self.bind("v", lambda _event: self.use_crop_tool())
        self.bind("b", lambda _event: self.use_pencil_tool())
        self.bind("e", lambda _event: self.use_eraser_tool())
        self.bind("l", lambda _event: self.use_line_tool())
        self.bind("p", lambda _event: self.use_paint_tool())
        self.bind("i", lambda _event: self.use_eyedropper_tool())
        self.bind("t", lambda _event: self.apply_transparency())
        self.bind("x", lambda _event: self.fit_32())
        self.bind("c", lambda _event: self.clear_queued_boxes())
        self.bind("<Command-s>", lambda _event: self.save_shortcut())
        self.bind("<Command-Shift-s>", lambda _event: self.save_all_crops())
        self.bind("<Command-p>", lambda _event: self.save_edited_image())
        self.bind("<Control-s>", lambda _event: self.save_shortcut())
        self.bind("<Control-Shift-s>", lambda _event: self.save_all_crops())
        self.bind("<Control-p>", lambda _event: self.save_edited_image())
        self._refresh_tool_buttons()

    def _add_palette_chips(self, parent: tk.Widget) -> None:
        for rgb in self.palette_colors[:8]:
            color = self._rgb_to_hex(rgb)
            chip = tk.Button(
                parent,
                text="",
                command=lambda value=color: self.set_paint_color(value),
                bg=color,
                activebackground=color,
                relief=tk.FLAT,
                width=2,
                padx=0,
                pady=3,
                highlightthickness=0,
            )
            chip.pack(side=tk.LEFT, padx=(0, 2))

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
            height=3,
            padx=2,
            pady=3,
            highlightthickness=0,
            justify=tk.CENTER,
        )
        button.pack(side=tk.TOP, pady=(0, 5))
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
                button.configure(bg=SELECTED, fg="#ffffff", activebackground=SELECTED)
            else:
                button.configure(bg=BG, fg=TEXT, activebackground=PANEL)

    def _initial_scale(self) -> float:
        scale = min(MAX_INITIAL_WIDTH / self.image_width, MAX_INITIAL_HEIGHT / self.image_height)
        return max(1.0, min(8.0, scale))

    def _render_image(self) -> None:
        display_size = (
            max(1, int(self.image_width * self.scale)),
            max(1, int(self.image_height * self.scale)),
        )
        resampling = getattr(Image, "Resampling", Image)
        displayed = self.original.resize(display_size, resampling.NEAREST)
        self.preview_ref = ImageTk.PhotoImage(displayed)
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, image=self.preview_ref, anchor="nw")
        else:
            self.canvas.itemconfigure(self.image_id, image=self.preview_ref)
        self.canvas.configure(scrollregion=(0, 0, display_size[0], display_size[1]))

    def _to_original_point(self, event: tk.Event) -> tuple[int, int]:
        x = int(self.canvas.canvasx(event.x) / self.scale)
        y = int(self.canvas.canvasy(event.y) / self.scale)
        return (
            max(0, min(x, self.image_width)),
            max(0, min(y, self.image_height)),
        )

    def _to_pixel_point(self, event: tk.Event) -> tuple[int, int]:
        x, y = self._to_original_point(event)
        return (
            min(x, self.image_width - 1),
            min(y, self.image_height - 1),
        )

    def _start_crop(self, event: tk.Event) -> None:
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
        if self.tool_mode.get() in {"pencil", "eraser"}:
            self.continue_pixel_stroke(event)
            return
        if self.tool_mode.get() == "line":
            self.preview_line(event)
            return
        if self.tool_mode.get() == "paint":
            self.paint_at_event(event)
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
        x1, y1, x2, y2 = box
        display_box = (x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale)
        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(*display_box, outline=SELECTED, width=2)
        else:
            self.canvas.coords(self.rect_id, *display_box)
        self._show_box_status()

    def _show_box_status(self) -> None:
        if self.box is None:
            return
        x1, y1, x2, y2 = self.box
        status = f"선택 영역: x={x1}, y={y1}, w={x2 - x1}, h={y2 - y1}"
        if self.queued_boxes:
            status = f"{status} | 대기 {len(self.queued_boxes)}개"
        if self.last_saved_path is not None:
            status = f"{status} | 마지막 저장: {self.last_saved_path.name}"
        if self.edit_dirty:
            status = f"{status} | 편집 미저장"
        if self.last_changed_pixels:
            status = f"{status} | 변경 {self.last_changed_pixels}픽셀"
        status = f"{status} | 도구: {self._tool_mode_label()} | 색: {self.paint_color_var.get()}"
        self.info_var.set(status)

    def _tool_mode_label(self) -> str:
        return {
            "crop": "크롭",
            "pencil": "펜",
            "eraser": "지우개",
            "line": "직선",
            "paint": "채우기",
            "eyedropper": "스포이드",
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
        self.paint_color_swatch.configure(bg=normalized, activebackground=normalized)
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
        return (
            (start[0] + 0.5) * self.scale,
            (start[1] + 0.5) * self.scale,
            (end[0] + 0.5) * self.scale,
            (end[1] + 0.5) * self.scale,
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

        point = self._to_original_point(event)
        self.original, changed = flood_fill_image(
            self.original,
            point,
            rgb,
            self.paint_tolerance_var.get(),
        )
        self.last_changed_pixels = changed
        if changed:
            self.edit_dirty = True
            self._render_image()
        self._show_box_status()
        return "break"

    def apply_transparency(self) -> str:
        rgb = hex_to_rgb(self.paint_color_var.get())
        if rgb is None:
            messagebox.showerror("색상 오류", f"잘못된 색상입니다: {self.paint_color_var.get()}")
            return "break"

        before = list(self.original.getdata())
        self.original = make_edge_connected_color_transparent(
            self.original,
            rgb,
            self.paint_tolerance_var.get(),
        )
        changed = sum(
            1 for old, new in zip(before, self.original.getdata(), strict=True) if old != new
        )
        self.last_changed_pixels = changed
        if changed:
            self.edit_dirty = True
            self._render_image()
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

    def fit_32(self) -> None:
        if self.box is None:
            return
        x1, y1, _, _ = self.box
        box = normalize_crop_box((x1, y1), (x1 + 32, y1 + 32), (self.image_width, self.image_height))
        if box is not None:
            self._set_box(box)

    def queue_current_box(self) -> str:
        if self.box is None:
            messagebox.showinfo("선택 없음", "추가할 크롭 영역을 먼저 선택하세요.")
            return "break"

        self.queued_boxes.append(self.box)
        x1, y1, x2, y2 = self.box
        rect_id = self.canvas.create_rectangle(
            x1 * self.scale,
            y1 * self.scale,
            x2 * self.scale,
            y2 * self.scale,
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
        return self.save_crop()

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
