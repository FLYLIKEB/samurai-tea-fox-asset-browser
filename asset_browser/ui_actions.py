"""User actions for selection, prompt editing, files, and palette conversion."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

from .constants import ART_STYLE_TOKENS_PATH, BUILTIN_PROMPT_TEMPLATE
from .crop_window import ImageCropWindow
from .image_ops import Image, apply_palette_to_images, is_larger_than_tile
from .paths import palette_backup_root, template_path
from .prompting import load_prompt_template, render_prompt_template, save_prompt_template
from .scanner import find_images
from .style_tokens import extract_palette_colors

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
        self.selected = {path for path in self.selected if path in {item.path for item in self.images}}
        self.apply_filter()
        self.update_prompt_preview(force=True)

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
        self.render_grid()
        self.update_prompt_preview()

    def select_all(self) -> None:
        self.selected.update(item.path for item in self.filtered_images)
        self.render_grid()
        self.update_prompt_preview()

    def clear_selection(self) -> None:
        self.selected.clear()
        self.render_grid()
        self.update_prompt_preview()

    def selected_assets(self) -> list[AssetImage]:
        selected = set(self.selected)
        return [item for item in self.images if item.path in selected]

    def selected_relative_paths(self) -> list[str]:
        return [item.relative_path.as_posix() for item in self.selected_assets()]

    def selected_absolute_paths(self) -> list[str]:
        return [str(item.path) for item in self.selected_assets()]

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

    def open_crop_or_copy_prompt(self, asset: AssetImage) -> None:
        try:
            should_crop = is_larger_than_tile(asset.path)
        except Exception as exc:
            messagebox.showerror("이미지 확인 실패", f"{asset.path}\n\n{exc}")
            return

        if not should_crop:
            self.copy_single_prompt(asset)
            return

        ImageCropWindow(self, asset, self._crop_saved)

    def _crop_saved(self, path: Path) -> None:
        self.rescan()
        self.status_var.set(f"크롭 저장 완료: {path}")

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
        self.status_var.set(
            f"전체 {len(self.images)}개 | 표시 {len(self.filtered_images)}개 | 선택 {len(self.selected)}개{suffix}"
        )

    def _scale_changed(self, _value: str) -> None:
        self.render_grid()

    def toggle_palette_preview(self) -> None:
        self.render_grid()
        if self.palette_preview_var.get():
            self.status_var.set("팔레트 테스트 보기: 원본 파일은 변경하지 않습니다.")
        else:
            self._set_status()

    def apply_palette_to_shown_images(self) -> None:
        if Image is None:
            messagebox.showerror("Pillow 필요", "실제 이미지 변환에는 Pillow가 필요합니다.")
            return

        if not self.filtered_images:
            messagebox.showinfo("이미지 없음", "변환할 표시 이미지가 없습니다.")
            return

        palette = extract_palette_colors(self.art_style_data)
        if not palette:
            messagebox.showinfo("팔레트 없음", "적용할 팔레트 색상을 찾지 못했습니다.")
            return

        backup_root = palette_backup_root(self.project_root)
        count = len(self.filtered_images)
        ok = messagebox.askokcancel(
            "실제 이미지 변환 확인",
            "현재 화면에 표시된 이미지 전체를 팔레트 색으로 실제 변환합니다.\n\n"
            f"대상: {count}개\n"
            f"백업 위치: {backup_root}\n\n"
            "원본 파일이 덮어써집니다. 계속할까요?",
        )
        if not ok:
            return

        paths = [item.path for item in self.filtered_images]
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
