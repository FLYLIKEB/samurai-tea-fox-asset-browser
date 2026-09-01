from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from asset_browser import asset_browser as core

class AssetBrowserCoreTest(unittest.TestCase):
    def test_find_images_returns_sorted_project_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            root = project_root / "assets"
            (root / "sprites").mkdir(parents=True)
            (root / "tiles").mkdir(parents=True)
            (root / "tiles" / "b.txt").write_text("not an image", encoding="utf-8")
            (root / "tiles" / "b.PNG").write_bytes(b"")
            (root / "sprites" / "a.png").write_bytes(b"")

            images = core.find_images(root, project_root)

        self.assertEqual(
            [item.relative_path.as_posix() for item in images],
            ["assets/sprites/a.png", "assets/tiles/b.PNG"],
        )

    def test_group_images_by_folder_uses_current_scan_root(self) -> None:
        project_root = Path("/project")
        asset_root = project_root / "assets"
        images = [
            core.AssetImage(project_root / "assets" / "sprites" / "fox.png", Path("assets/sprites/fox.png")),
            core.AssetImage(project_root / "assets" / "tiles" / "grass.png", Path("assets/tiles/grass.png")),
            core.AssetImage(project_root / "assets" / "tiles" / "water.png", Path("assets/tiles/water.png")),
        ]

        groups = core.group_images_by_folder(images, asset_root, project_root)

        self.assertEqual(
            [(label, [item.relative_path.name for item in items]) for label, items in groups],
            [("sprites", ["fox.png"]), ("tiles", ["grass.png", "water.png"])],
        )

    def test_thumbnail_scale_keeps_32px_assets_at_4x_inside_128px_box(self) -> None:
        scaled_size = core.AssetBrowser._scaled_size

        self.assertEqual(scaled_size(None, 32, 32, 4), (128, 128))
        self.assertEqual(scaled_size(None, 64, 64, 4), (128, 128))
        self.assertEqual(scaled_size(None, 128, 64, 4), (128, 64))

    def test_render_prompt_template_replaces_known_placeholders(self) -> None:
        prompt = core.render_prompt_template(
            "개수: {asset_count}\n루트: {project_root}\n이미지:\n{asset_list}",
            ["assets/a.png", "assets/b.png"],
            Path("/tmp/project"),
        )

        self.assertIn("개수: 2", prompt)
        self.assertIn("루트: /tmp/project", prompt)
        self.assertIn("- assets/a.png\n- assets/b.png", prompt)
        self.assertTrue(prompt.endswith("\n"))

    def test_render_prompt_template_appends_asset_list_when_placeholder_missing(self) -> None:
        prompt = core.render_prompt_template("수정해줘", ["assets/a.png"])

        self.assertEqual(prompt, "수정해줘\n\n이미지:\n- assets/a.png\n")

    def test_extract_palette_colors_deduplicates_global_and_biome_colors(self) -> None:
        data = {
            "palette": {
                "global": [{"hex": "#000000"}, {"hex": "ffffff"}, {"hex": "bad"}],
                "biome_accents": [{"colors": ["#000000", "#112233"]}],
            }
        }

        self.assertEqual(
            core.extract_palette_colors(data),
            [(0, 0, 0), (255, 255, 255), (17, 34, 51)],
        )

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_recolor_image_to_palette_preserves_transparent_pixels(self) -> None:
        image = core.Image.new("RGBA", (2, 1))
        image.putdata([(250, 250, 250, 255), (10, 20, 30, 0)])

        recolored = core.recolor_image_to_palette(image, [(0, 0, 0), (255, 255, 255)])

        self.assertEqual(list(recolored.getdata()), [(255, 255, 255, 255), (10, 20, 30, 0)])

    def test_normalize_crop_box_sorts_and_clamps_coordinates(self) -> None:
        box = core.normalize_crop_box((90, 50), (-10, 20), (64, 64))

        self.assertEqual(box, (0, 20, 64, 50))

    def test_normalize_crop_box_rejects_empty_selection(self) -> None:
        box = core.normalize_crop_box((10, 10), (10, 30), (64, 64))

        self.assertIsNone(box)

    def test_default_crop_output_path_uses_source_folder_and_original_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sheet.png"

            target = core.default_crop_output_path(source, (32, 64, 64, 96))

        self.assertEqual(target.name, "sheet_crop_32_64_32x32.png")

    def test_default_crop_output_path_always_uses_png_and_avoids_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sheet.jpg"
            existing = Path(tmp) / "sheet_crop_0_0_32x32.png"
            existing.write_bytes(b"already here")

            target = core.default_crop_output_path(source, (0, 0, 32, 32))

        self.assertEqual(target.name, "sheet_crop_0_0_32x32_2.png")

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_crop_image_to_file_saves_original_pixel_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            target = Path(tmp) / "crop.png"
            image = core.Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            image.putpixel((2, 1), (255, 0, 0, 255))
            image.save(source)

            core.crop_image_to_file(source, target, (2, 1, 3, 2))

            with core.Image.open(target) as cropped:
                self.assertEqual(cropped.size, (1, 1))
                self.assertEqual(cropped.convert("RGBA").getpixel((0, 0)), (255, 0, 0, 255))

if __name__ == "__main__":
    unittest.main()
