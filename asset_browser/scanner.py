"""Image discovery for the asset browser."""

from __future__ import annotations

from pathlib import Path

from .constants import IMAGE_EXTENSIONS
from .models import AssetImage


def find_images(root: Path, project_root: Path) -> list[AssetImage]:
    if not root.exists():
        return []

    images: list[AssetImage] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            relative_path = path.relative_to(project_root)
        except ValueError:
            relative_path = path
        images.append(AssetImage(path=path, relative_path=relative_path))

    return sorted(images, key=lambda item: item.relative_path.as_posix().lower())


def folder_group_label(asset: AssetImage, asset_root: Path, project_root: Path) -> str:
    try:
        folder = asset.path.parent.relative_to(asset_root)
    except ValueError:
        try:
            folder = asset.path.parent.relative_to(project_root)
        except ValueError:
            folder = asset.relative_path.parent

    label = folder.as_posix()
    return label if label and label != "." else "(현재 폴더)"


def group_images_by_folder(
    images: list[AssetImage],
    asset_root: Path,
    project_root: Path,
) -> list[tuple[str, list[AssetImage]]]:
    groups: dict[str, list[AssetImage]] = {}
    for image in images:
        label = folder_group_label(image, asset_root, project_root)
        groups.setdefault(label, []).append(image)
    return list(groups.items())
