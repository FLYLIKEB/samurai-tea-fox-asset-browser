"""User actions for selection, prompt editing, files, and palette conversion."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

from .constants import ART_STYLE_TOKENS_PATH, BUILTIN_PROMPT_TEMPLATE
from .crop_window import ImageCropWindow
from .file_ops import move_files_to_directory, replace_file_with_and_delete_source
from .image_ops import (
    Image,
    apply_adjustment_to_images,
    apply_palette_to_images,
    apply_resize_to_images,
    apply_transparency_to_images,
    image_info,
    image_size,
    parse_image_size,
)
from .paths import adjustment_backup_root, palette_backup_root, resize_backup_root, template_path
from .prompting import load_prompt_template, render_prompt_template, save_prompt_template
from .scanner import find_images
from .style_tokens import extract_palette_colors, hex_to_rgb, normalize_hex_color

class ActionsMixin:
    def choose_root(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.path_var.get() or str(self.project_root))
        if not chosen:
            return
        self.path_var.set(chosen)
        self.rescan()

    def rescan(self) -> None:
        root = Path(self.path_var.get()).expanduser()
        if not root.is_absolute():
            root = (self.project_root / root).resolve()
        self.asset_root = root
        self.path_var.set(str(root))
        self.images = find_images(root, self.project_root)
        self.image_by_path = {item.path: item for item in self.images}
        self.image_order_by_path = {item.path: index for index, item in enumerate(self.images)}
        # Decoding every alpha channel is expensive for large folders. Size is
        # available from the image header; transparency waits for thumbnail use.
        self.image_size_by_path = {
            item.path: self._read_image_size(item.path) for item in self.images
        }
        self.image_has_transparency_by_path = {item.path: None for item in self.images}
        self.selected = {path for path in self.selected if path in {item.path for item in self.images}}
        self.apply_filter()
        self.update_prompt_preview(force=True)

    def _read_image_info(self, path: Path) -> tuple[tuple[int, int] | None, bool | None]:
        try:
            return image_info(path)
        except Exception:
            return None, None

    def _read_image_size(self, path: Path) -> tuple[int, int] | None:
        try:
            return image_size(path)
        except Exception:
            return None

    def apply_filter(self) -> None:
        query = self.filter_var.get().strip().lower()
        if query:
            self.filtered_images = [
                item for item in self.images if query in item.relative_path.as_posix().lower()
            ]
        else:
            self.filtered_images = list(self.images)
        self.render_grid()

    def toggle_selection(self, asset: AssetImage) -> None:
        if asset.path in self.selected:
            self.selected.remove(asset.path)
        else:
            self.selected.add(asset.path)
        self.update_cell_selection(asset.path)
        self._set_status()
        self.schedule_prompt_preview_update()

    def select_asset_fast(self, asset: AssetImage) -> None:
        if asset.path in self.selected:
            return
        self.selected.add(asset.path)
        self.update_cell_selection(asset.path)
        self._set_status()
        self.schedule_prompt_preview_update()

    def begin_drag_selection(self, asset: AssetImage) -> str:
        pending_id = self.pending_click_after_id
        if pending_id is not None:
            self.after_cancel(pending_id)
            self.pending_click_after_id = None
        self.drag_selecting = True
        self.drag_seen_paths.clear()
        self.select_asset_fast(asset)
        self.drag_seen_paths.add(asset.path)
        return "break"

    def extend_drag_selection(self, event: tk.Event, asset: AssetImage) -> str:
        if not self.drag_selecting and not (event.state & 0x0100):
            return "break"
        self.drag_selecting = True
        if asset.path not in self.drag_seen_paths:
            self.select_asset_fast(asset)
            self.drag_seen_paths.add(asset.path)
        self.autoscroll_during_drag(event)
        return "break"

    def end_drag_selection(self, _event: tk.Event | None = None) -> str:
        self.drag_selecting = False
        self.drag_seen_paths.clear()
        return "break"

    def select_asset_under_pointer(self) -> None:
        asset = self.asset_under_pointer()
        if asset is not None:
            self.select_asset_fast(asset)

    def select_visible_images(self) -> None:
        changed: list[Path] = []
        for asset in self.visible_assets():
            if asset.path not in self.selected:
                self.selected.add(asset.path)
                changed.append(asset.path)
        if not changed:
            return
        for path in changed:
            self.update_cell_selection(path)
        self._set_status()
        self.schedule_prompt_preview_update()

    def toggle_scroll_select(self) -> None:
        self.scroll_select_var.set(not self.scroll_select_var.get())
        self.scroll_select_changed()

    def scroll_select_changed(self) -> None:
        if self.scroll_select_var.get():
            self.select_visible_images()
            self.status_var.set("스크롤 선택 켜짐: 스크롤하면 보이는 이미지가 선택됩니다.")
        else:
            self._set_status()

    def expand_all_groups(self) -> None:
        self.expanded_group_labels.update(self.current_group_labels())
        self.render_grid()
        self.status_var.set("모든 폴더를 펼쳤습니다.")

    def collapse_all_groups(self) -> None:
        self.expanded_group_labels.clear()
        self.render_grid()
        self.status_var.set("모든 폴더를 접었습니다.")

    def navigate_to_asset_folder(self, folder: Path) -> str:
        target = folder.expanduser()
        if not target.is_absolute():
            target = (self.project_root / target).resolve()
        self.path_var.set(str(target))
        self.filter_var.set("")
        self.expanded_group_labels.clear()
        self.default_expanded_group_labels.clear()
        self.rescan()
        self.status_var.set(f"폴더로 이동: {target}")
        return "break"

    def navigate_to_parent_folder(self) -> str:
        current = Path(self.path_var.get()).expanduser()
        if not current.is_absolute():
            current = (self.project_root / current).resolve()
        else:
            current = current.resolve()

        parent = current.parent
        if parent == current:
            self.status_var.set("이미 최상위 폴더입니다.")
            return "break"

        self.navigate_to_asset_folder(parent)
        self.status_var.set(f"상위 폴더로 이동: {parent}")
        return "break"

    def schedule_toggle_selection(self, asset: AssetImage) -> str:
        if time.monotonic() < self.suppress_single_click_until:
            return "break"

        pending_id = self.pending_click_after_id
        if pending_id is not None:
            self.after_cancel(pending_id)

        self.pending_click_after_id = self.after(220, lambda: self._run_scheduled_toggle(asset))
        return "break"

    def _run_scheduled_toggle(self, asset: AssetImage) -> None:
        self.pending_click_after_id = None
        if time.monotonic() < self.suppress_single_click_until:
            return
        self.toggle_selection(asset)

    def select_all(self) -> None:
        self.selected.update(item.path for item in self.filtered_images)
        self.update_visible_selection_styles()
        self._set_status()
        self.schedule_prompt_preview_update()

    def clear_selection(self) -> None:
        self.selected.clear()
        self.update_visible_selection_styles()
        self._set_status()
        self.schedule_prompt_preview_update()

    def selected_assets(self) -> list[AssetImage]:
        return [
            self.image_by_path[path]
            for path in sorted(
                self.selected,
                key=lambda selected_path: self.image_order_by_path.get(selected_path, 0),
            )
            if path in self.image_by_path
        ]

    def selected_relative_paths(self) -> list[str]:
        return [item.relative_path.as_posix() for item in self.selected_assets()]

    def selected_absolute_paths(self) -> list[str]:
        return [str(item.path) for item in self.selected_assets()]

    def delete_selected_images(self) -> None:
        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        preview = "\n".join(item.relative_path.as_posix() for item in assets[:8])
        if len(assets) > 8:
            preview = f"{preview}\n..."
        ok = messagebox.askokcancel(
            "선택 이미지 삭제",
            f"선택한 이미지 {len(assets)}개를 실제 삭제합니다.\n\n{preview}\n\n계속할까요?",
        )
        if not ok:
            return

        deleted = 0
        failures: list[str] = []
        for asset in assets:
            try:
                asset.path.unlink()
                deleted += 1
            except Exception as exc:
                failures.append(f"{asset.relative_path.as_posix()}: {exc}")

        self.selected.clear()
        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "삭제 실패 목록")
            messagebox.showwarning("일부 삭제 실패", f"{deleted}개 삭제, {len(failures)}개 실패")
        self.status_var.set(f"삭제 완료: {deleted}개")

    def replace_selected_image_with_file(self) -> None:
        assets = self.selected_assets()
        if len(assets) != 1:
            messagebox.showinfo("대상 하나 선택", "바꿀 대상 이미지를 정확히 하나 선택하세요.")
            return

        target = assets[0]
        source_name = filedialog.askopenfilename(
            title="대상 이미지로 교체할 원본 선택",
            initialdir=str(target.path.parent),
            filetypes=[("이미지 파일", "*.png *.gif *.jpg *.jpeg *.bmp *.webp *.tga *.tif *.tiff *.ppm *.pgm"), ("모든 파일", "*.*")],
        )
        if not source_name:
            return

        source = Path(source_name)
        try:
            if source.resolve() == target.path.resolve():
                raise ValueError("교체 대상과 원본 파일은 서로 달라야 합니다.")
            if source.suffix.lower() != target.path.suffix.lower():
                raise ValueError("교체 대상과 원본의 파일 확장자가 같아야 합니다.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("이미지 교체 불가", str(exc))
            return

        ok = messagebox.askokcancel(
            "이미지 교체 및 원본 삭제",
            f"대상 파일명은 유지한 채 이미지 내용을 교체합니다.\n\n"
            f"대상: {target.relative_path.as_posix()}\n"
            f"원본: {source}\n\n"
            "원본 파일은 교체 성공 후 실제 삭제됩니다. 계속할까요?",
        )
        if not ok:
            return

        try:
            replace_file_with_and_delete_source(target.path, source)
        except Exception as exc:
            messagebox.showerror("이미지 교체 실패", str(exc))
            return

        self.selected.clear()
        self.rescan()
        self.status_var.set(f"이미지 교체 완료: {target.relative_path.as_posix()} | 원본 삭제: {source.name}")

    def sync_all_images_to_godot(self) -> None:
        project_file = self.project_root / "project.godot"
        if not project_file.is_file():
            messagebox.showerror("Godot 프로젝트 없음", f"project.godot 파일을 찾을 수 없습니다.\n\n{project_file}")
            return

        ok = messagebox.askokcancel(
            "Godot 이미지 메타데이터 전체 반영",
            "Godot 에디터를 headless로 실행해 프로젝트 전체 에셋을 다시 가져옵니다.\n"
            "같은 파일명으로 덮어쓴 이미지도 Godot import 메타데이터에 반영됩니다.\n\n계속할까요?",
        )
        if not ok:
            return

        try:
            result = subprocess.run(
                ["godot", "--headless", "--path", str(self.project_root), "--editor", "--quit"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            messagebox.showerror("Godot 실행 실패", f"godot 명령을 실행할 수 없습니다.\n\n{exc}")
            return

        if result.returncode != 0:
            output = (result.stderr or result.stdout or "출력 없음").strip()
            messagebox.showerror("Godot 반영 실패", f"종료 코드: {result.returncode}\n\n{output}")
            return

        self.status_var.set("Godot 이미지 메타데이터 전체 반영 완료")
        messagebox.showinfo("Godot 반영 완료", "프로젝트 전체 이미지의 변경 메타데이터를 Godot에 반영했습니다.")

    def move_selected_images(self) -> None:
        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        destination = filedialog.askdirectory(
            title="선택 이미지를 이동할 폴더",
            initialdir=str(self.asset_root),
        )
        if not destination:
            return

        preview = "\n".join(item.relative_path.as_posix() for item in assets[:8])
        if len(assets) > 8:
            preview = f"{preview}\n..."
        ok = messagebox.askokcancel(
            "선택 이미지 이동",
            f"선택한 이미지 {len(assets)}개를 다음 폴더로 이동합니다.\n\n"
            f"{destination}\n\n{preview}\n\n계속할까요?",
        )
        if not ok:
            return

        moved, failures = move_files_to_directory(
            [asset.path for asset in assets],
            Path(destination),
        )
        self.selected.clear()
        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "이동 실패 목록")
            messagebox.showwarning("일부 이동 실패", f"{len(moved)}개 이동, {len(failures)}개 실패")
        self.status_var.set(f"이동 완료: {len(moved)}개 -> {destination}")

    def copy_relative_paths(self) -> None:
        self._copy_lines(self.selected_relative_paths(), "상대경로")

    def copy_absolute_paths(self) -> None:
        self._copy_lines(self.selected_absolute_paths(), "절대경로")

    def copy_codex_prompt(self) -> None:
        paths = self.selected_relative_paths()
        if not paths:
            self._warn_no_selection()
            return
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            self._warn_empty_prompt()
            return
        self._copy_text(prompt + "\n", "Codex 프롬프트")

    def copy_single_prompt(self, asset: AssetImage) -> None:
        prompt = render_prompt_template(
            self.prompt_template,
            [asset.relative_path.as_posix()],
            self.project_root,
        )
        self.set_prompt_text(prompt, dirty=False)
        self._copy_text(prompt, "단일 이미지 프롬프트")

    def open_crop_or_copy_prompt(self, asset: AssetImage) -> str:
        self.suppress_single_click_until = time.monotonic() + 0.35
        pending_id = self.pending_click_after_id
        if pending_id is not None:
            self.after_cancel(pending_id)
            self.pending_click_after_id = None

        ImageCropWindow(self, asset, self._crop_saved)
        return "break"

    def _crop_saved(self, path: Path) -> None:
        self.rescan()
        self.status_var.set(f"이미지 저장 완료: {path}")

    def reset_prompt(self) -> None:
        self.update_prompt_preview(force=True)

    def update_prompt_preview(self, force: bool = False) -> None:
        if self.prompt_dirty and not force:
            return
        paths = self.selected_relative_paths()
        if paths:
            prompt = render_prompt_template(self.prompt_template, paths, self.project_root)
        else:
            prompt = "이미지를 선택하면 여기에 복사될 Codex 프롬프트가 표시됩니다.\n"
        self.set_prompt_text(prompt, dirty=False)

    def schedule_prompt_preview_update(self) -> None:
        pending_id = self.pending_prompt_after_id
        if pending_id is not None:
            self.after_cancel(pending_id)
        self.pending_prompt_after_id = self.after(120, self._run_scheduled_prompt_update)

    def _run_scheduled_prompt_update(self) -> None:
        self.pending_prompt_after_id = None
        self.update_prompt_preview()

    def set_prompt_text(self, text: str, dirty: bool) -> None:
        self.updating_prompt = True
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)
        self.prompt_text.edit_modified(False)
        self.prompt_dirty = dirty
        self.updating_prompt = False

    def _prompt_modified(self, _event: tk.Event) -> None:
        if self.updating_prompt:
            self.prompt_text.edit_modified(False)
            return
        if self.prompt_text.edit_modified():
            self.prompt_dirty = True
            self.prompt_text.edit_modified(False)
            self._set_status()

    def save_template(self) -> None:
        content = self.template_text.get("1.0", "end-1c")
        if not content.strip():
            self._warn_empty_template()
            return
        if "{asset_list}" not in content:
            ok = messagebox.askokcancel(
                "이미지 목록 치환값 없음",
                "{asset_list}가 없으면 이미지 목록이 프롬프트 끝에 자동으로 붙습니다. 계속 저장할까요?",
            )
            if not ok:
                return
        save_prompt_template(
            content if content.endswith("\n") else f"{content}\n",
            self.project_root,
        )
        self.prompt_template = load_prompt_template(self.project_root)
        self.set_template_text(self.prompt_template, dirty=False)
        self.update_prompt_preview(force=True)
        self.status_var.set(f"템플릿 저장 완료: {template_path(self.project_root)}")

    def reload_template(self) -> None:
        self.prompt_template = load_prompt_template(self.project_root)
        self.set_template_text(self.prompt_template, dirty=False)
        self.update_prompt_preview(force=True)
        self.status_var.set(f"템플릿 다시 읽음: {template_path(self.project_root)}")

    def restore_builtin_template(self) -> None:
        self.prompt_template = BUILTIN_PROMPT_TEMPLATE
        self.set_template_text(self.prompt_template, dirty=True)
        self.update_prompt_preview(force=True)
        self.status_var.set("기본 템플릿을 편집창에 복원했습니다. 저장하면 파일에 반영됩니다.")

    def copy_template_path(self) -> None:
        self._copy_text(str(template_path(self.project_root)), "템플릿 파일 경로")
        self.status_var.set("템플릿 파일 경로 복사 완료")

    def copy_art_style_path(self) -> None:
        self._copy_text(str(self.project_root / ART_STYLE_TOKENS_PATH), "아트 스타일 토큰 파일 경로")
        self.status_var.set("아트 스타일 토큰 파일 경로 복사 완료")

    def reveal_template_file(self) -> None:
        self.reveal_in_finder(template_path(self.project_root))

    def reveal_art_style_file(self) -> None:
        self.reveal_in_finder(self.project_root / ART_STYLE_TOKENS_PATH)

    def reveal_asset_root(self) -> None:
        self.reveal_in_finder(self.asset_root)

    def reveal_in_finder(self, path: Path) -> None:
        target = path if path.exists() else path.parent
        try:
            subprocess.run(["open", "-R", str(target)], check=True)
            self.status_var.set(f"Finder에서 표시: {target}")
        except (OSError, subprocess.CalledProcessError) as exc:
            messagebox.showerror("Finder 열기 실패", f"{target}\n\n{exc}")

    def set_template_text(self, text: str, dirty: bool) -> None:
        self.updating_template = True
        self.template_text.delete("1.0", tk.END)
        self.template_text.insert("1.0", text)
        self.template_text.edit_modified(False)
        self.template_dirty = dirty
        self.updating_template = False

    def _template_modified(self, _event: tk.Event) -> None:
        if self.updating_template:
            self.template_text.edit_modified(False)
            return
        if self.template_text.edit_modified():
            self.template_dirty = True
            self.template_text.edit_modified(False)
            self._set_status()

    def save_txt(self) -> None:
        paths = self.selected_relative_paths()
        if not paths:
            self._warn_no_selection()
            return
        target = filedialog.asksaveasfilename(
            initialdir=str(self.project_root / "tools" / "asset_browser"),
            initialfile="selected_assets.txt",
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
        )
        if not target:
            return
        Path(target).write_text("\n".join(paths) + "\n", encoding="utf-8")
        self.status_var.set(f"{len(paths)}개 경로를 저장했습니다: {target}")

    def resize_selected_images(self) -> None:
        if Image is None:
            messagebox.showerror("Pillow 필요", "이미지 리사이즈에는 Pillow가 필요합니다.")
            return

        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        try:
            size = parse_image_size(self.resize_size_var.get())
        except Exception as exc:
            messagebox.showerror("크기 오류", str(exc))
            return

        backup_root = resize_backup_root(self.project_root)
        preview = "\n".join(item.relative_path.as_posix() for item in assets[:8])
        if len(assets) > 8:
            preview = f"{preview}\n..."
        ok = messagebox.askokcancel(
            "선택 이미지 크기 변경",
            f"선택한 이미지 {len(assets)}개를 {size[0]}x{size[1]}로 원본 파일에 적용합니다.\n\n"
            f"{preview}\n\n"
            f"백업 위치: {backup_root}\n\n"
            "새 이미지 파일은 만들지 않습니다. 계속할까요?",
        )
        if not ok:
            return

        converted, failures = apply_resize_to_images(
            [asset.path for asset in assets],
            size,
            self.project_root,
            backup_root,
        )

        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "리사이즈 실패 목록")
            messagebox.showwarning("일부 리사이즈 실패", f"{converted}개 변경, {len(failures)}개 실패")
        self.status_var.set(
            f"리사이즈 완료: {converted}개 | {size[0]}x{size[1]} | 백업: {backup_root}"
        )

    def adjust_selected_images(self) -> None:
        if Image is None:
            messagebox.showerror("Pillow 필요", "이미지 보정에는 Pillow가 필요합니다.")
            return

        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        kind = self.adjustment_kind_var.get()
        percent = self.adjustment_percent_var.get()
        backup_root = adjustment_backup_root(self.project_root)
        preview = "\n".join(item.relative_path.as_posix() for item in assets[:8])
        if len(assets) > 8:
            preview = f"{preview}\n..."
        ok = messagebox.askokcancel(
            "선택 이미지 보정",
            f"선택한 이미지 {len(assets)}개에 {kind} {percent:+d}% 보정을 실제 적용합니다.\n\n"
            f"{preview}\n\n"
            f"백업 위치: {backup_root}\n\n계속할까요?",
        )
        if not ok:
            return

        converted, failures = apply_adjustment_to_images(
            [asset.path for asset in assets],
            kind,
            percent,
            self.project_root,
            backup_root,
        )
        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "보정 실패 목록")
            messagebox.showwarning("일부 보정 실패", f"{converted}개 보정, {len(failures)}개 실패")
        self.status_var.set(f"보정 완료: {converted}개 | {kind} {percent:+d}% | 백업: {backup_root}")

    def choose_transparent_color(self) -> None:
        _rgb, hex_color = colorchooser.askcolor(
            color=self.transparent_color_var.get(),
            title="투명하게 바꿀 배경색 선택",
        )
        if not hex_color:
            return
        self.transparent_color_var.set(normalize_hex_color(hex_color))
        self.refresh_transparent_color_swatch()

    def refresh_transparent_color_swatch(self) -> None:
        color = normalize_hex_color(self.transparent_color_var.get())
        rgb = hex_to_rgb(color)
        if rgb is None:
            return
        self.transparent_color_var.set(color)
        self.transparent_color_swatch.configure(bg=color, activebackground=color)

    def apply_transparency_to_selected_images(self) -> None:
        if Image is None:
            messagebox.showerror("Pillow 필요", "배경 투명화에는 Pillow가 필요합니다.")
            return

        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        color = normalize_hex_color(self.transparent_color_var.get())
        rgb = hex_to_rgb(color)
        if rgb is None:
            messagebox.showerror("색상 오류", f"잘못된 색상입니다: {self.transparent_color_var.get()}")
            return

        tolerance = self.transparent_tolerance_var.get()
        edge_only = self.transparent_edge_only_var.get()
        backup_root = palette_backup_root(self.project_root)
        mode = "외곽 연결 영역만" if edge_only else "같은 색 전체"
        ok = messagebox.askokcancel(
            "배경 투명화 확인",
            f"선택한 이미지 {len(assets)}개에서 {color} 주변 색상을 투명으로 실제 변경합니다.\n"
            f"방식: {mode}\n"
            f"허용 범위: 채널별 ±{tolerance}\n\n"
            f"백업 위치: {backup_root}\n\n계속할까요?",
        )
        if not ok:
            return

        converted, failures = apply_transparency_to_images(
            [asset.path for asset in assets],
            rgb,
            self.project_root,
            backup_root,
            tolerance,
            edge_only,
        )
        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "투명화 실패 목록")
            messagebox.showwarning("일부 투명화 실패", f"{converted}개 변환, {len(failures)}개 실패")
        self.status_var.set(
            f"배경 투명화 완료: {converted}개 | {mode} | 색상 {color} | 범위 {tolerance} | 백업: {backup_root}"
        )

    def _copy_lines(self, lines: list[str], label: str) -> None:
        if not lines:
            self._warn_no_selection()
            return
        self._copy_text("\n".join(lines) + "\n", label)

    def _copy_text(self, text: str, label: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status_var.set(f"{label} 복사 완료: {len(self.selected)}개 선택됨")

    def _warn_no_selection(self) -> None:
        messagebox.showinfo("선택 없음", "먼저 이미지를 하나 이상 선택하세요.")

    def _warn_empty_prompt(self) -> None:
        messagebox.showinfo("프롬프트 없음", "복사할 프롬프트 내용을 입력하세요.")

    def _warn_empty_template(self) -> None:
        messagebox.showinfo("템플릿 없음", "저장할 기본 프롬프트 템플릿을 입력하세요.")

    def _warn_no_art_style_tokens(self) -> None:
        messagebox.showinfo("토큰 없음", "복사할 아트 스타일 토큰 파일을 찾지 못했습니다.")

    def _set_status(self) -> None:
        suffixes = []
        if self.prompt_dirty:
            suffixes.append("프롬프트 수정됨")
        if self.template_dirty:
            suffixes.append("템플릿 수정됨")
        suffix = f" | {' | '.join(suffixes)}" if suffixes else ""
        transparency_by_path = getattr(self, "image_has_transparency_by_path", {})
        transparent_count = sum(
            1
            for image in self.filtered_images
            if transparency_by_path.get(image.path) is True
        )
        self.status_var.set(
            f"전체 {len(self.images)}개 | 표시 {len(self.filtered_images)}개 | "
            f"투명 {transparent_count}개 | 선택 {len(self.selected)}개{suffix}"
        )

    def _scale_changed(self, _value: str) -> None:
        self.render_grid()

    def toggle_palette_preview(self) -> None:
        self.render_grid()
        if self.palette_preview_var.get():
            self.status_var.set("팔레트 테스트 보기: 원본 파일은 변경하지 않습니다.")
        else:
            self._set_status()

    def apply_palette_to_selected_images(self) -> None:
        if Image is None:
            messagebox.showerror("Pillow 필요", "실제 이미지 변환에는 Pillow가 필요합니다.")
            return

        assets = self.selected_assets()
        if not assets:
            self._warn_no_selection()
            return

        palette = extract_palette_colors(self.art_style_data, self.selected_palette_candidate_id())
        if not palette:
            messagebox.showinfo("팔레트 없음", "적용할 팔레트 색상을 찾지 못했습니다.")
            return

        backup_root = palette_backup_root(self.project_root)
        count = len(assets)
        preview = "\n".join(item.relative_path.as_posix() for item in assets[:8])
        if len(assets) > 8:
            preview = f"{preview}\n..."
        ok = messagebox.askokcancel(
            "실제 이미지 변환 확인",
            "선택한 이미지를 팔레트 색으로 실제 변환합니다.\n\n"
            f"대상: {count}개\n"
            f"{preview}\n\n"
            f"백업 위치: {backup_root}\n\n"
            "원본 파일이 덮어써집니다. 계속할까요?",
        )
        if not ok:
            return

        paths = [item.path for item in assets]
        converted, failures = apply_palette_to_images(paths, palette, self.project_root, backup_root)
        self.rescan()
        if failures:
            self._copy_text("\n".join(failures) + "\n", "변환 실패 목록")
            messagebox.showwarning(
                "일부 변환 실패",
                f"{converted}개 변환 완료, {len(failures)}개 실패.\n"
                "실패 목록은 클립보드에 복사했습니다.",
            )
        else:
            messagebox.showinfo(
                "변환 완료",
                f"{converted}개 이미지를 변환했습니다.\n백업 위치: {backup_root}",
            )
        self.status_var.set(f"팔레트 실제 변환 완료: {converted}개 | 백업: {backup_root}")

    def apply_palette_to_shown_images(self) -> None:
        self.apply_palette_to_selected_images()
