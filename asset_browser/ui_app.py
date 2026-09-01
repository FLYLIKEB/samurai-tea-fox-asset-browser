"""Tkinter UI for the local asset browser."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tkinter as tk

from .constants import BG, BORDER, ERROR, MUTED, SELECTED, SELECTED_TEXT, TEXT
from .constants import GRID_CELL_HEIGHT, GRID_CELL_PITCH, GRID_CELL_WIDTH, THUMBNAIL_BOX_SIZE
from .image_ops import Image, ImageTk, recolor_image_to_palette
from .models import AssetImage
from .prompting import load_prompt_template
from .scanner import group_images_by_folder
from .style_tokens import extract_palette_colors
from .ui_actions import ActionsMixin
from .ui_layout import LayoutMixin
from .ui_palette import PalettePanelMixin

@dataclass
class AssetCellWidgets:
    cell: tk.Frame
    image_box: tk.Frame
    image_label: tk.Label
    name_label: tk.Label
    detail_label: tk.Label

class AssetBrowser(LayoutMixin, PalettePanelMixin, ActionsMixin, tk.Tk):
    def __init__(self, project_root: Path, asset_root: Path, scale: int) -> None:
        super().__init__()
        self.project_root = project_root
        self.asset_root = asset_root
        self.scale_var = tk.IntVar(value=scale)
        self.resize_size_var = tk.StringVar(value="32x32")
        self.transparent_color_var = tk.StringVar(value="#ffffff")
        self.transparent_tolerance_var = tk.IntVar(value=32)
        self.palette_preview_var = tk.BooleanVar(value=False)
        self.scroll_select_var = tk.BooleanVar(value=False)
        self.bottom_panel_visible = tk.BooleanVar(value=False)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.path_var = tk.StringVar(value=str(asset_root))
        self.images: list[AssetImage] = []
        self.filtered_images: list[AssetImage] = []
        self.image_by_path: dict[Path, AssetImage] = {}
        self.image_order_by_path: dict[Path, int] = {}
        self.selected: set[Path] = set()
        self.cell_widgets: dict[Path, AssetCellWidgets] = {}
        self.path_by_widget_id: dict[int, Path] = {}
        self.thumbnail_refs: list[tk.PhotoImage] = []
        self.prompt_template = load_prompt_template(project_root)
        self.art_style_data: dict | None = None
        self.art_style_raw = ""
        self.prompt_dirty = False
        self.template_dirty = False
        self.updating_prompt = False
        self.updating_template = False
        self.pending_click_after_id: str | None = None
        self.pending_prompt_after_id: str | None = None
        self.suppress_single_click_until = 0.0
        self.scroll_remainder = 0.0
        self.drag_selecting = False
        self.drag_seen_paths: set[Path] = set()
        self.expanded_group_labels: set[str] = set()

        self.title("무사여우 에셋 브라우저")
        self.geometry("1360x940")
        self.minsize(1040, 720)
        self.configure(bg=BG)

        self._build_ui()
        self.rescan()

    def render_grid(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.thumbnail_refs.clear()
        self.cell_widgets.clear()
        self.path_by_widget_id.clear()

        if not self.filtered_images:
            tk.Label(
                self.grid_frame,
                text="이미지가 없습니다",
                bg=BG,
                fg=MUTED,
                font=("TkDefaultFont", 15),
                pady=40,
            ).grid(row=0, column=0, sticky="n")
            self._set_status()
            return

        width = max(self.canvas.winfo_width(), 720)
        columns = max(1, width // GRID_CELL_PITCH)

        for column in range(columns):
            self.grid_frame.columnconfigure(column, minsize=GRID_CELL_PITCH, uniform="asset_cells")

        row = 0
        for label, images in group_images_by_folder(
            self.filtered_images,
            self.asset_root,
            self.project_root,
        ):
            expanded = label in self.expanded_group_labels
            self._add_group_header(label, len(images), row, columns, expanded)
            row += 1
            if not expanded:
                continue
            for index, item in enumerate(images):
                cell_row = row + index // columns
                column = index % columns
                self._add_cell(item, cell_row, column)
            row += math.ceil(len(images) / columns)

        self._set_status()

    def _add_group_header(
        self,
        label: str,
        count: int,
        row: int,
        columns: int,
        expanded: bool,
    ) -> None:
        header = tk.Frame(self.grid_frame, bg=BG, pady=2)
        header.grid(row=row, column=0, columnspan=columns, sticky="w", padx=3, pady=(8, 1))

        icon = "▾" if expanded else "▸"
        title = tk.Label(
            header,
            text=f"{icon} {label}  {count}개",
            bg=BG,
            fg=MUTED,
            anchor="w",
            font=("TkDefaultFont", 10, "bold"),
            cursor="pointinghand",
        )
        title.pack(side=tk.LEFT)
        for widget in (header, title):
            widget.bind("<Button-1>", lambda _event, group_label=label: self.toggle_group(group_label))

    def current_group_labels(self) -> list[str]:
        return [
            label
            for label, _images in group_images_by_folder(
                self.filtered_images,
                self.asset_root,
                self.project_root,
            )
        ]

    def toggle_group(self, label: str) -> str:
        if label in self.expanded_group_labels:
            self.expanded_group_labels.remove(label)
        else:
            self.expanded_group_labels.add(label)
        self.render_grid()
        return "break"

    def _add_cell(self, item: AssetImage, row: int, column: int) -> None:
        is_selected = item.path in self.selected
        bg, fg, meta_fg = self._cell_colors(is_selected)

        cell = tk.Frame(
            self.grid_frame,
            bg=bg,
            padx=2,
            pady=2,
            highlightthickness=0,
            highlightbackground=SELECTED if is_selected else BORDER,
            width=GRID_CELL_WIDTH,
            height=GRID_CELL_HEIGHT,
        )
        cell.grid(row=row, column=column, padx=3, pady=3, sticky="n")
        cell.grid_propagate(False)

        image_box = tk.Frame(
            cell,
            bg=bg,
            width=THUMBNAIL_BOX_SIZE,
            height=THUMBNAIL_BOX_SIZE,
        )
        image_box.pack(side=tk.TOP)
        image_box.pack_propagate(False)

        thumb, meta = self._load_thumbnail(item.path)
        if thumb is not None:
            self.thumbnail_refs.append(thumb)
            image_label = tk.Label(image_box, image=thumb, bg=bg)
        else:
            image_label = tk.Label(
                image_box,
                text="미리보기\n불가",
                bg=bg,
                fg=ERROR if not is_selected else SELECTED_TEXT,
                width=15,
                height=6,
                justify=tk.CENTER,
            )
        image_label.pack(expand=True)

        name_label = tk.Label(
            cell,
            text=self._short_name(item.relative_path.name),
            bg=bg,
            fg=fg,
            wraplength=124,
            justify=tk.CENTER,
            height=1,
            font=("TkDefaultFont", 10),
        )
        name_label.pack(side=tk.TOP)

        detail_label = tk.Label(
            cell,
            text=meta,
            bg=bg,
            fg=meta_fg,
            wraplength=124,
            justify=tk.CENTER,
            font=("TkDefaultFont", 9),
            height=1,
        )
        detail_label.pack(side=tk.BOTTOM)

        for widget in (cell, image_box, image_label, name_label, detail_label):
            widget.bind("<Button-1>", lambda _event, asset=item: self.schedule_toggle_selection(asset))
            widget.bind("<B1-Motion>", lambda _event, asset=item: self.begin_drag_selection(asset))
            widget.bind("<Enter>", lambda event, asset=item: self.extend_drag_selection(event, asset))
            widget.bind("<Double-Button-1>", lambda _event, asset=item: self.open_crop_or_copy_prompt(asset))
            self.path_by_widget_id[id(widget)] = item.path

        self.cell_widgets[item.path] = AssetCellWidgets(
            cell=cell,
            image_box=image_box,
            image_label=image_label,
            name_label=name_label,
            detail_label=detail_label,
        )

    def update_cell_selection(self, path: Path) -> None:
        widgets = self.cell_widgets.get(path)
        if widgets is None:
            return

        is_selected = path in self.selected
        bg, fg, meta_fg = self._cell_colors(is_selected)
        widgets.cell.configure(bg=bg, highlightbackground=SELECTED if is_selected else BORDER)
        widgets.image_box.configure(bg=bg)
        widgets.image_label.configure(bg=bg)
        widgets.name_label.configure(bg=bg, fg=fg)
        widgets.detail_label.configure(bg=bg, fg=meta_fg)

        if not widgets.image_label.cget("image"):
            widgets.image_label.configure(fg=ERROR if not is_selected else SELECTED_TEXT)

    def update_visible_selection_styles(self) -> None:
        for path in self.cell_widgets:
            self.update_cell_selection(path)

    def asset_under_pointer(self) -> AssetImage | None:
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        while widget is not None:
            path = self.path_by_widget_id.get(id(widget))
            if path is not None:
                return self.image_by_path.get(path)
            widget = widget.master
        return None

    def visible_assets(self) -> list[AssetImage]:
        top = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        assets: list[AssetImage] = []
        for path, widgets in self.cell_widgets.items():
            cell_top = widgets.cell.winfo_y()
            cell_bottom = cell_top + widgets.cell.winfo_height()
            if cell_bottom >= top and cell_top <= bottom:
                asset = self.image_by_path.get(path)
                if asset is not None:
                    assets.append(asset)
        return sorted(
            assets,
            key=lambda asset: self.image_order_by_path.get(asset.path, 0),
        )

    def _cell_colors(self, is_selected: bool) -> tuple[str, str, str]:
        bg = SELECTED if is_selected else BG
        fg = SELECTED_TEXT if is_selected else TEXT
        meta_fg = SELECTED_TEXT if is_selected else MUTED
        return bg, fg, meta_fg

    def _load_thumbnail(self, path: Path) -> tuple[tk.PhotoImage | None, str]:
        scale = max(1, self.scale_var.get())

        if Image is not None and ImageTk is not None:
            try:
                with Image.open(path) as opened:
                    image = opened.convert("RGBA")
                    width, height = image.size
                    meta_suffix = ""
                    if self.palette_preview_var.get():
                        palette = extract_palette_colors(self.art_style_data)
                        if palette:
                            image = recolor_image_to_palette(image, palette)
                            meta_suffix = " | 팔레트 테스트"
                        else:
                            meta_suffix = " | 팔레트 없음"
                    target_width, target_height = self._scaled_size(width, height, scale)
                    resampling = getattr(Image, "Resampling", Image)
                    image = image.resize((target_width, target_height), resampling.NEAREST)
                    return ImageTk.PhotoImage(image), f"{width}x{height}{meta_suffix}"
            except Exception as exc:  # Tk fallback may still work for PNG/GIF.
                pil_error = exc
        else:
            pil_error = None

        if self.palette_preview_var.get():
            return None, "팔레트 테스트는 Pillow 필요"

        try:
            image = tk.PhotoImage(file=str(path))
            width, height = image.width(), image.height()
            target_width, target_height = self._scaled_size(width, height, scale)
            zoom = max(1, min(target_width // max(width, 1), target_height // max(height, 1)))
            if zoom > 1:
                image = image.zoom(zoom, zoom)
            elif max(width, height) > 192:
                subsample = math.ceil(max(width, height) / 192)
                image = image.subsample(subsample, subsample)
            return image, f"{width}x{height}"
        except Exception as exc:
            if pil_error is not None:
                return None, f"{path.suffix.lower()} 지원 안 됨"
            return None, f"읽기 오류: {exc.__class__.__name__}"

    def _scaled_size(self, width: int, height: int, scale: int) -> tuple[int, int]:
        max_dimension = max(width, height)
        if max_dimension <= 0:
            return 1, 1

        fit_scale = min(float(scale), THUMBNAIL_BOX_SIZE / max_dimension)
        return max(1, int(width * fit_scale)), max(1, int(height * fit_scale))

    def _short_name(self, name: str) -> str:
        if len(name) <= 20:
            return name
        stem, dot, suffix = name.rpartition(".")
        if dot and len(suffix) <= 5:
            return f"{stem[:13]}...{suffix}"
        return f"{name[:17]}..."
