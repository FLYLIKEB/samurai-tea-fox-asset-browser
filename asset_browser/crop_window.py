"""Original-coordinate crop window for large source images."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .constants import BG, BORDER, MUTED, PANEL, SELECTED, TEXT
from .image_ops import (
    Image,
    ImageTk,
    crop_boxes_to_files,
    crop_image_to_file,
    default_crop_output_path,
    normalize_crop_box,
)
from .models import AssetImage

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
        self.last_saved_path: Path | None = None

        self.title(f"이미지 크롭 - {asset.relative_path.name}")
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
        header = tk.Frame(self, bg=PANEL, padx=10, pady=7)
        header.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            header,
            text=f"{self.asset.relative_path.as_posix()}  {self.image_width}x{self.image_height}",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._button(header, "× 초기화 (C)", self.clear_queued_boxes).pack(side=tk.RIGHT, padx=(6, 0))
        self._button(header, "◆ 모두 저장 (⇧⌘S)", self.save_all_crops).pack(side=tk.RIGHT, padx=(6, 0))
        self._button(header, "+ 영역 추가 (Space)", self.queue_current_box).pack(side=tk.RIGHT, padx=(6, 0))
        self._button(header, "◆ 저장 (⌘S)", self.save_crop).pack(side=tk.RIGHT, padx=(6, 0))
        self._button(header, "□ 32x32 (X)", self.fit_32).pack(side=tk.RIGHT, padx=(6, 0))

        info = tk.Label(self, textvariable=self.info_var, bg=BG, fg=MUTED, anchor="w", padx=10, pady=5)
        info.pack(side=tk.TOP, fill=tk.X)

        canvas_shell = tk.Frame(self, bg=BG)
        canvas_shell.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_shell, bg=BG, highlightthickness=1, highlightbackground=BORDER)
        x_scroll = tk.Scrollbar(canvas_shell, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = tk.Scrollbar(canvas_shell, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas_shell.columnconfigure(0, weight=1)
        canvas_shell.rowconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self._start_crop)
        self.canvas.bind("<B1-Motion>", self._drag_crop)
        self.canvas.bind("<ButtonRelease-1>", self._finish_crop)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self.queue_current_box())
        self.bind("<space>", lambda _event: self.queue_current_box())
        self.bind("x", lambda _event: self.fit_32())
        self.bind("c", lambda _event: self.clear_queued_boxes())
        self.bind("<Command-s>", lambda _event: self.save_shortcut())
        self.bind("<Command-Shift-s>", lambda _event: self.save_all_crops())
        self.bind("<Control-s>", lambda _event: self.save_shortcut())
        self.bind("<Control-Shift-s>", lambda _event: self.save_all_crops())

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
            padx=9,
            pady=3,
            highlightthickness=0,
        )

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
        self.canvas.create_image(0, 0, image=self.preview_ref, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, display_size[0], display_size[1]))

    def _to_original_point(self, event: tk.Event) -> tuple[int, int]:
        x = int(self.canvas.canvasx(event.x) / self.scale)
        y = int(self.canvas.canvasy(event.y) / self.scale)
        return (
            max(0, min(x, self.image_width)),
            max(0, min(y, self.image_height)),
        )

    def _start_crop(self, event: tk.Event) -> None:
        self.start = self._to_original_point(event)
        self._set_box((*self.start, *self.start))

    def _drag_crop(self, event: tk.Event) -> None:
        if self.start is None:
            return
        end = self._to_original_point(event)
        box = normalize_crop_box(self.start, end, (self.image_width, self.image_height))
        if box is not None:
            self._set_box(box)

    def _finish_crop(self, event: tk.Event) -> None:
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
        self.info_var.set(status)

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
            crop_image_to_file(self.asset.path, target, self.box)
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
            saved_paths = crop_boxes_to_files(self.asset.path, boxes)
        except Exception as exc:
            messagebox.showerror("크롭 저장 실패", str(exc))
            return "break"

        self.last_saved_path = saved_paths[-1]
        self.on_saved(saved_paths[-1])
        self.clear_queued_boxes()
        self._show_box_status()
        return "break"
