"""Command-line entry point for the asset browser."""

from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Sequence

from .constants import SCALE_CHOICES
from .paths import project_root_from_script
from .scanner import find_images

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="프로젝트 에셋 이미지를 확인하고 선택합니다.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="대상 게임 프로젝트 루트입니다. 기본값은 현재 작업 디렉터리입니다.",
    )
    parser.add_argument(
        "--root",
        default="assets",
        help="스캔할 이미지 폴더입니다. 기본값은 프로젝트 assets 폴더입니다.",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=4,
        choices=SCALE_CHOICES,
        help="작은 픽셀아트 이미지를 보여줄 정수 미리보기 배율입니다.",
    )
    parser.add_argument(
        "--list-images",
        action="store_true",
        help="UI를 열지 않고 발견한 이미지 경로만 출력합니다.",
    )
    return parser.parse_args(argv)

def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    asset_root = Path(args.root).expanduser()
    if not asset_root.is_absolute():
        asset_root = (project_root / asset_root).resolve()

    if args.list_images:
        for image in find_images(asset_root, project_root):
            print(image.relative_path.as_posix())
        return 0

    from .ui_app import AssetBrowser

    app = AssetBrowser(project_root=project_root, asset_root=asset_root, scale=args.scale)
    app.mainloop()
    return 0
