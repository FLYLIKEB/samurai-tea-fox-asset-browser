"""Regression benchmark for large-folder initial asset discovery."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from asset_browser.image_ops import Image, image_size
from asset_browser.scanner import find_images


def main() -> int:
    if Image is None:
        print("SKIP: Pillow is not installed")
        return 0

    with tempfile.TemporaryDirectory() as temporary_directory:
        project_root = Path(temporary_directory)
        assets_root = project_root / "assets"
        assets_root.mkdir()
        image = Image.new("RGBA", (128, 128), (20, 40, 60, 128))
        for index in range(500):
            image.save(assets_root / f"asset_{index:03}.png")

        started_at = time.perf_counter()
        images = find_images(assets_root, project_root)
        sizes = {asset.path: image_size(asset.path) for asset in images}
        elapsed = time.perf_counter() - started_at

    if len(images) != 500 or len(sizes) != 500:
        raise AssertionError("500-image fixture scan was incomplete")
    print(f"initial loading benchmark: {elapsed:.3f}s for 500 images")
    if elapsed >= 1.0:
        raise AssertionError("initial loading exceeded 1.0 seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
