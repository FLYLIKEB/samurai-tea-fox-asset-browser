"""Tkinter UI for the local asset browser."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tkinter as tk

from .constants import BG, BORDER, ERROR, MUTED, PANEL, SELECTED, SELECTED_TEXT, TEXT
from .constants import GRID_CELL_PITCH
from .image_ops import Image, ImageTk, composite_on_checkerboard, recolor_image_to_palette
from .models import AssetImage
from .prompting import load_prompt_template
from .scanner import folder_group_label
from .sizing import (
    cell_size_for_preview,
    preview_size_for_image,
    tile_size_group_label,
    tile_size_sort_key,
)
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
    transparency_label: tk.Label
    preview_error: bool

class AssetBrowser(LayoutMixin, PalettePanelMixin, ActionsMixin, tk.Tk):
    def __init__(self, project_root: Path, asset_root: Path, scale: int) -> None:
        super().__init__()
        self.project_root = project_root
        self.asset_root = asset_root
        self.scale_var = tk.IntVar(value=scale)
        self.resize_size_var = tk.StringVar(value="32x32")
        self.adjustment_kind_var = tk.StringVar(value="대비")
        self.adjustment_percent_var = tk.IntVar(value=20)
        self.transparent_color_var = tk.StringVar(value="#ffffff")
        self.transparent_tolerance_var = tk.IntVar(value=32)
        self.transparent_edge_only_var = tk.BooleanVar(value=True)
        self.palette_preview_var = tk.BooleanVar(value=False)
        self.palette_candidate_var = tk.StringVar(value="정본")
        self.scroll_select_var = tk.BooleanVar(value=False)
        self.bottom_panel_visible = tk.BooleanVar(value=False)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.path_var = tk.StringVar(value=str(asset_root))
        self.images: list[AssetImage] = []
        self.filtered_images: list[AssetImage] = []
        self.image_by_path: dict[Path, AssetImage] = {}
        self.image_order_by_path: dict[Path, int] = {}
        self.image_size_by_path: dict[Path, tuple[int, int] | None] = {}
        self.image_has_transparency_by_path: dict[Path, bool | None] = {}
        self.selected: set[Path] = set()
        self.cell_widgets: dict[Path, AssetCellWidgets] = {}
        self.path_by_widget_id: dict[int, Path] = {}
        self.thumbnail_refs: list[tk.PhotoImage] = []
        self.prompt_template = load_prompt_template(project_root)
        self.art_style_data: dict | None = None
        self.art_style_raw = ""
        self.palette_candidate_ids: dict[str, str] = {"정본": ""}
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
        self.default_expanded_group_labels: set[str] = set()

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

        width = max(self.canvas.winfo_width(), 360)
        groups = self.grouped_images_for_render()

        max_columns = max(1, width // GRID_CELL_PITCH)
        for column in range(max_columns):
            self.grid_frame.columnconfigure(column, minsize=GRID_CELL_PITCH, uniform="asset_cells")

        row = 0
        for label, images in groups:
            expanded = label in self.expanded_group_labels
            group_preview_size = self.preview_size_for_group(images)
            group_cell_width, _group_cell_height = cell_size_for_preview(group_preview_size)
            group_pitch = group_cell_width + 8
            columns = max(1, width // group_pitch)
            self._add_group_header(label, images, row, columns, expanded)
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
        images: list[AssetImage],
        row: int,
        columns: int,
        expanded: bool,
    ) -> None:
        header = tk.Frame(
            self.grid_frame,
            bg=PANEL,
            padx=8,
            pady=5,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        header.grid(row=row, column=0, columnspan=columns, sticky="ew", padx=3, pady=(10, 2))

        icon = "▾" if expanded else "▸"
        transparent_count = self.transparent_image_count(images)
        title = tk.Label(
            header,
            text=f"{icon} {label}",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
            font=("TkDefaultFont", 10, "bold"),
            cursor="pointinghand",
        )
        title.pack(side=tk.LEFT)
        summary = tk.Label(
            header,
            text=f"{len(images)}개 | 투명 {transparent_count} | 불투명 {len(images) - transparent_count}",
            bg=PANEL,
            fg=MUTED,
            anchor="e",
            font=("TkDefaultFont", 9),
            cursor="pointinghand",
        )
        summary.pack(side=tk.RIGHT)
        for widget in (header, title, summary):
            widget.bind("<Button-1>", lambda _event, group_label=label: self.toggle_group(group_label))

    def current_group_labels(self) -> list[str]:
        return [label for label, _images in self.grouped_images_for_render()]

    def grouped_images_for_render(self) -> list[tuple[str, list[AssetImage]]]:
        groups: dict[str, list[AssetImage]] = {}
        sort_keys: dict[str, tuple[str, int, int, int]] = {}
        for image in self.filtered_images:
            size = self.image_size_by_path.get(image.path)
            folder_label, size_label = self.group_parts_for_asset(image)
            label = self.group_label_for_asset(image)
            groups.setdefault(label, []).append(image)
            sort_keys.setdefault(label, (folder_label.lower(), *tile_size_sort_key(size)))

        self.expand_default_groups(groups)
        return sorted(groups.items(), key=lambda item: sort_keys[item[0]])

    def group_parts_for_asset(self, image: AssetImage) -> tuple[str, str]:
        size = self.image_size_by_path.get(image.path)
        return (
            folder_group_label(image, self.asset_root, self.project_root),
            tile_size_group_label(size),
        )

    def group_label_for_asset(self, image: AssetImage) -> str:
        folder_label, size_label = self.group_parts_for_asset(image)
        return f"{folder_label} / {size_label}"

    def expand_default_groups(self, groups: dict[str, list[AssetImage]]) -> None:
        default_expanded = getattr(self, "default_expanded_group_labels", set())
        self.default_expanded_group_labels = default_expanded
        for label, images in groups.items():
            if label in default_expanded:
                continue
            if any(
                tile_size_group_label(self.image_size_by_path.get(image.path)) == "32x32"
                for image in images
            ):
                self.expanded_group_labels.add(label)
                default_expanded.add(label)

    def preview_size_for_group(self, images: list[AssetImage]) -> tuple[int, int]:
        if not images:
            return 1, 1
        return max(
            (preview_size_for_image(self.image_size_by_path.get(item.path), self.scale_var.get()) for item in images),
            key=lambda size: size[0] * size[1],
        )

    def transparent_image_count(self, images: list[AssetImage]) -> int:
        transparency_by_path = getattr(self, "image_has_transparency_by_path", {})
        return sum(1 for image in images if transparency_by_path.get(image.path) is True)

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

        source_size = self.image_size_by_path.get(item.path)
        preview_size = preview_size_for_image(source_size, self.scale_var.get())
        cell_width, cell_height = cell_size_for_preview(preview_size)
        image_box_width, image_box_height = preview_size

        cell = tk.Frame(
            self.grid_frame,
            bg=bg,
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground=SELECTED if is_selected else BORDER,
            width=cell_width,
            height=cell_height,
        )
        cell.grid(row=row, column=column, padx=3, pady=3, sticky="n")
        cell.grid_propagate(False)

        image_box = tk.Frame(
            cell,
            bg=bg,
            width=image_box_width,
            height=image_box_height,
        )
        image_box.pack(side=tk.TOP)
        image_box.pack_propagate(False)

        thumb, meta = self._load_thumbnail(item.path)
        preview_error = False
        if thumb is not None:
            self.thumbnail_refs.append(thumb)
            image_label = tk.Label(image_box, image=thumb, bg=bg)
        else:
            preview_error = True
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
            wraplength=max(124, cell_width - 8),
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
            wraplength=max(124, cell_width - 8),
            justify=tk.CENTER,
            font=("TkDefaultFont", 9),
            height=1,
        )
        detail_label.pack(side=tk.BOTTOM)

        badge_text, badge_bg, badge_fg = self._transparency_badge(item.path, is_selected)
        transparency_label = tk.Label(
            cell,
            text=badge_text,
            bg=badge_bg,
            fg=badge_fg,
            justify=tk.CENTER,
            font=("TkDefaultFont", 8),
            height=1,
            padx=4,
        )
        transparency_label.pack(side=tk.BOTTOM, pady=(1, 0))

        for widget in (cell, image_box, image_label, name_label, detail_label, transparency_label):
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
            transparency_label=transparency_label,
            preview_error=preview_error,
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
        badge_text, badge_bg, badge_fg = self._transparency_badge(path, is_selected)
        widgets.transparency_label.configure(text=badge_text, bg=badge_bg, fg=badge_fg)

        if widgets.preview_error:
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
        bg = SELECTED if is_selected else PANEL
        fg = SELECTED_TEXT if is_selected else TEXT
        meta_fg = SELECTED_TEXT if is_selected else MUTED
        return bg, fg, meta_fg

    def _transparency_badge(self, path: Path, is_selected: bool) -> tuple[str, str, str]:
        has_transparency = getattr(self, "image_has_transparency_by_path", {}).get(path)
        if is_selected:
            return self._transparency_label(has_transparency), SELECTED, SELECTED_TEXT
        if has_transparency is True:
            return "투명", "#e8f3f1", SELECTED
        if has_transparency is False:
            return "불투명", "#ececf0", MUTED
        return "확인불가", "#f1f1f3", ERROR

    def _transparency_label(self, has_transparency: bool | None) -> str:
        if has_transparency is True:
            return "투명"
        if has_transparency is False:
            return "불투명"
        return "확인불가"

    def _load_thumbnail(self, path: Path) -> tuple[tk.PhotoImage | None, str]:
        scale = max(1, self.scale_var.get())
        known_size = self.image_size_by_path.get(path)
        has_transparency = getattr(self, "image_has_transparency_by_path", {}).get(path)
        transparency_meta = self._transparency_label(has_transparency)

        if Image is not None and ImageTk is not None:
            try:
                with Image.open(path) as opened:
                    image = opened.convert("RGBA")
                    width, height = image.size
                    tiles_wide = max(1, math.ceil(width / 32))
                    tiles_high = max(1, math.ceil(height / 32))
                    meta_suffix = ""
                    if self.palette_preview_var.get():
                        palette = extract_palette_colors(
                            self.art_style_data,
                            self.selected_palette_candidate_id(),
                        )
                        if palette:
                            image = recolor_image_to_palette(image, palette)
                            meta_suffix = " | 팔레트 테스트"
                        else:
                            meta_suffix = " | 팔레트 없음"
                    target_width, target_height = self._scaled_size(width, height, scale)
                    resampling = getattr(Image, "Resampling", Image)
                    image = image.resize((target_width, target_height), resampling.NEAREST)
                    if has_transparency is True:
                        image = composite_on_checkerboard(image)
                    return (
                        ImageTk.PhotoImage(image),
                        f"{width}x{height} | {tiles_wide}x{tiles_high}타일 | {transparency_meta}{meta_suffix}",
                    )
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
            return image, f"{width}x{height} | {transparency_meta}"
        except Exception as exc:
            if pil_error is not None:
                return None, f"{path.suffix.lower()} 지원 안 됨"
            return None, f"읽기 오류: {exc.__class__.__name__}"

    def _scaled_size(self, width: int, height: int, scale: int) -> tuple[int, int]:
        return preview_size_for_image((width, height), scale)

    def _short_name(self, name: str) -> str:
        if len(name) <= 20:
            return name
        stem, dot, suffix = name.rpartition(".")
        if dot and len(suffix) <= 5:
            return f"{stem[:13]}...{suffix}"
        return f"{name[:17]}..."
