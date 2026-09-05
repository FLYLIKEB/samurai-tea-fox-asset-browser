"""Small reusable widgets for a quiet, modern Tk interface."""

from __future__ import annotations

import tkinter as tk

from .constants import BORDER, MUTED, PANEL, SELECTED, SELECTED_TEXT, TEXT

BUTTON_BG = "#eef2f4"
BUTTON_HOVER = "#e2e9eb"
GHOST_HOVER = "#e9eff1"
ACCENT_HOVER = "#125b58"
DANGER_BG = "#f9eceb"
DANGER_HOVER = "#f3ddda"
DANGER_TEXT = "#93443d"
SELECTED_BG = "#dcebea"
SELECTED_HOVER = "#cfe2e0"
TOOLTIP_BG = "#20262d"
TOOLTIP_TEXT = "#ffffff"

BUTTON_HELP = {
    "navigate_to_parent_folder": "현재 이미지 폴더의 상위 폴더로 한 단계 이동합니다. 단축키: Cmd+↑",
    "choose_root": "이미지 목록에서 탐색할 폴더를 선택합니다. 단축키: Cmd+O",
    "rescan": "현재 폴더의 이미지와 메타데이터를 다시 읽습니다. 단축키: Cmd+R",
    "reveal_asset_root": "현재 이미지 폴더를 Finder에서 엽니다. 단축키: Cmd+F",
    "expand_all_groups": "모든 폴더와 크기 그룹을 펼칩니다. 단축키: Cmd+U",
    "collapse_all_groups": "모든 폴더와 크기 그룹을 접습니다. 단축키: Cmd+J",
    "toggle_bottom_panel": "프롬프트와 스타일 토큰 작업 패널을 열거나 닫습니다. 단축키: Cmd+W",
    "select_all": "현재 표시된 이미지를 모두 선택합니다. 단축키: Cmd+A",
    "clear_selection": "현재 이미지 선택을 모두 해제합니다. 단축키: Esc",
    "delete_selected_images": "선택한 이미지 파일을 확인 후 삭제합니다. 단축키: Delete",
    "move_selected_images": "선택한 이미지 파일을 지정한 폴더로 이동합니다. 단축키: Cmd+M",
    "replace_selected_image_with_file": "선택한 이미지의 내용은 다른 파일로 바꾸고, 가져온 파일은 삭제합니다.",
    "sync_all_images_to_godot": "Godot 전체 import를 실행해 변경된 이미지 메타데이터를 반영합니다.",
    "copy_relative_paths": "선택한 이미지의 프로젝트 상대경로를 복사합니다. 단축키: Cmd+1",
    "copy_absolute_paths": "선택한 이미지의 절대경로를 복사합니다. 단축키: Cmd+2",
    "copy_codex_prompt": "선택 이미지 목록이 포함된 Codex 프롬프트를 복사합니다. 단축키: Cmd+C",
    "save_txt": "선택한 이미지 경로 목록을 TXT 파일로 저장합니다. 단축키: Cmd+T",
    "resize_selected_images": "선택 이미지를 지정 크기로 바꾸고 원본 위치에 저장합니다. 변경 전 파일은 백업됩니다.",
    "choose_transparent_color": "투명하게 만들 배경색을 색상 선택기로 고릅니다. 단축키: Cmd+K",
    "apply_transparency_to_selected_images": "선택 이미지에서 지정 색을 투명하게 만들고 원본에 저장합니다. 단축키: Cmd+G",
    "apply_palette_to_selected_images": "선택 이미지를 현재 팔레트로 변환하고 원본에 저장합니다. 단축키: Cmd+P",
    "toggle_palette_preview": "원본을 바꾸지 않고 현재 팔레트 적용 결과를 미리 봅니다. 단축키: Cmd+V",
    "adjust_selected_images": "선택 이미지에 고른 보정과 강도를 적용하고 원본에 저장합니다. 단축키: Cmd+Y",
    "reset_prompt": "수정한 복사 프롬프트를 기본 생성 결과로 되돌립니다. 단축키: Cmd+I",
    "restore_builtin_template": "프롬프트 템플릿을 앱 기본값으로 되돌립니다. 단축키: Cmd+B",
    "reload_template": "저장된 프롬프트 템플릿 파일을 다시 읽습니다. 단축키: Cmd+L",
    "save_template": "현재 프롬프트 템플릿을 파일에 저장합니다. 단축키: Cmd+S",
    "copy_template_path": "프롬프트 템플릿 파일 경로를 복사합니다. 단축키: Cmd+3",
    "reveal_template_file": "프롬프트 템플릿 파일을 Finder에서 표시합니다.",
    "copy_art_style_tokens": "아트 스타일 토큰 원본을 복사합니다. 단축키: Cmd+4",
    "reload_art_style_tokens": "아트 스타일 토큰 파일을 다시 읽습니다.",
    "copy_art_style_path": "아트 스타일 토큰 파일 경로를 복사합니다. 단축키: Cmd+5",
    "reveal_art_style_file": "아트 스타일 토큰 파일을 Finder에서 표시합니다.",
    "apply_selected_palette_candidate": "선택한 팔레트 후보를 정본 팔레트로 적용합니다.",
    "undo": "마지막 이미지 편집을 되돌립니다. 단축키: Cmd+Z",
    "redo": "되돌린 이미지 편집을 다시 실행합니다. 단축키: Shift+Cmd+Z",
    "zoom_out": "캔버스 배율을 한 단계 줄입니다.",
    "zoom_in": "캔버스 배율을 한 단계 높입니다.",
    "fit_to_window": "이미지 전체가 캔버스 안에 보이도록 맞춥니다. 단축키: F",
    "save_edited_image": "편집 결과를 원본 파일에 저장하고 기존 파일을 백업합니다. 단축키: Cmd+S",
    "cycle_transparency_background": "투명 확인 배경을 체커, 밝게, 어둡게 순서로 전환합니다. 단축키: D",
    "replace_all_colors": "이미지의 지정 색을 현재 선택 색으로 한 번에 치환합니다.",
    "fit_32": "현재 선택 영역을 32x32 크기로 맞춥니다. 단축키: X",
    "queue_current_box": "현재 선택 영역을 일괄 내보내기 목록에 추가합니다. 단축키: Q",
    "clear_queued_boxes": "일괄 내보내기 대기 영역을 모두 비웁니다. 단축키: C",
    "save_crop": "현재 선택 영역을 별도 PNG로 내보냅니다. 단축키: Cmd+E",
    "save_all_crops": "대기 영역을 각각의 PNG 파일로 모두 내보냅니다. 단축키: Shift+Cmd+E",
    "save_canvas_to_selection": "선택 영역을 새 캔버스 범위로 적용하고 바깥을 투명하게 채웁니다.",
    "request_close": "이미지 상세 편집창을 닫습니다. 미저장 편집이 있으면 먼저 확인합니다.",
    "use_crop_tool": "드래그로 크롭하거나 내보낼 영역을 선택합니다. 단축키: M",
    "use_pencil_tool": "현재 색으로 1픽셀 도트를 그립니다. 단축키: B",
    "use_eraser_tool": "드래그한 픽셀을 완전히 투명하게 지웁니다. 단축키: E",
    "use_line_tool": "시작점부터 끝점까지 1픽셀 직선을 그립니다. 단축키: L",
    "use_paint_tool": "연결된 같은 색 영역을 현재 색으로 채웁니다. 단축키: G",
    "use_eyedropper_tool": "이미지에서 클릭한 픽셀을 페인트 및 치환 결과색으로 선택합니다. 단축키: I",
    "use_replace_source_eyedropper": "캔버스에서 치환할 원본색을 직접 찍습니다.",
    "choose_replace_source_color": "색상 선택기를 열어 치환할 원본색을 고릅니다.",
    "use_hand_tool": "드래그로 확대된 캔버스를 이동합니다. 단축키: H 또는 Space",
    "apply_transparency": "이미지 외곽과 연결된 배경색을 투명하게 만듭니다. 단축키: T",
}


def tooltip_for_command(command, fallback: str = "") -> str:
    name = getattr(command, "__name__", "")
    return BUTTON_HELP.get(name, fallback)


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        if self.window is not None or not self.widget.winfo_exists():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        try:
            self.window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        label = tk.Label(
            self.window,
            text=self.text,
            bg=TOOLTIP_BG,
            fg=TOOLTIP_TEXT,
            justify=tk.LEFT,
            wraplength=300,
            padx=10,
            pady=7,
            font=("TkDefaultFont", 10),
        )
        label.pack()
        self.window.update_idletasks()
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 7
        x = min(x, self.widget.winfo_screenwidth() - self.window.winfo_reqwidth() - 8)
        if y + self.window.winfo_reqheight() > self.widget.winfo_screenheight() - 8:
            y = self.widget.winfo_rooty() - self.window.winfo_reqheight() - 7
        self.window.wm_geometry(f"+{max(8, x)}+{max(8, y)}")

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


def attach_tooltip(widget: tk.Widget, text: str) -> tk.Widget:
    if text:
        widget._tooltip = Tooltip(widget, text)  # type: ignore[attr-defined]
    return widget


class ModernButton(tk.Label):
    """Flat label-backed button that renders consistently on macOS Tk."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command,
        *,
        width: int | None = None,
        height: int | None = None,
        variant: str = "secondary",
        anchor: str = "center",
    ) -> None:
        self.command = command
        self.variant = variant
        self._state = tk.NORMAL
        self._selected = False
        self.base_bg = self._variant_color("bg", parent.cget("bg"))
        options = {"width": width} if width is not None else {}
        if height is not None:
            options["height"] = height
        super().__init__(
            parent,
            text=text,
            bg=self.base_bg,
            fg=self._variant_color("fg", TEXT),
            padx=9,
            pady=5,
            anchor=anchor,
            cursor="pointinghand",
            takefocus=True,
            highlightthickness=1,
            highlightbackground=self.base_bg,
            highlightcolor=SELECTED,
            **options,
        )
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")
        self.bind("<ButtonRelease-1>", self._invoke, add="+")
        self.bind("<Return>", self._invoke, add="+")
        self.bind("<space>", self._invoke, add="+")

    def _variant_color(self, role: str, parent_bg: str) -> str:
        colors = {
            "accent": {"bg": SELECTED, "hover": ACCENT_HOVER, "fg": SELECTED_TEXT},
            "danger": {"bg": DANGER_BG, "hover": DANGER_HOVER, "fg": DANGER_TEXT},
            "ghost": {"bg": parent_bg, "hover": GHOST_HOVER, "fg": TEXT},
            "secondary": {"bg": BUTTON_BG, "hover": BUTTON_HOVER, "fg": TEXT},
        }
        return colors.get(self.variant, colors["secondary"])[role]

    def _enter(self, _event=None) -> None:
        if self._state != tk.DISABLED:
            hover_bg = (
                SELECTED_HOVER
                if self._selected
                else self._variant_color("hover", self.master.cget("bg"))
            )
            self.configure(bg=hover_bg)

    def _leave(self, _event=None) -> None:
        self.configure(bg=SELECTED_BG if self._selected else self.base_bg)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.configure(
            bg=SELECTED_BG if selected else self.base_bg,
            fg=SELECTED if selected else self._variant_color("fg", TEXT),
            highlightbackground=SELECTED if selected else self.base_bg,
        )

    def _invoke(self, _event=None):
        if self._state != tk.DISABLED:
            return self.command()
        return None

    def invoke(self):
        return self._invoke()

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, str):
            return super().configure(cnf)
        if cnf:
            kwargs.update(cnf)
        state = kwargs.pop("state", None)
        if state is not None:
            self._state = state
            normal_fg = SELECTED if self._selected else self._variant_color("fg", TEXT)
            kwargs.setdefault("fg", MUTED if state == tk.DISABLED else normal_fg)
            kwargs.setdefault("cursor", "arrow" if state == tk.DISABLED else "pointinghand")
        return super().configure(**kwargs)

    config = configure
