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

    def test_toggle_selection_updates_only_one_cell_without_grid_render(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        asset = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        calls: list[str] = []
        browser.selected = set()
        browser.update_cell_selection = lambda path: calls.append(f"cell:{path.name}")
        browser._set_status = lambda: calls.append("status")
        browser.update_prompt_preview = lambda: calls.append("prompt")
        browser.render_grid = lambda: self.fail("selection should not rebuild the full grid")

        browser.toggle_selection(asset)

        self.assertEqual(browser.selected, {asset.path})
        self.assertEqual(calls, ["cell:a.png", "status", "prompt"])

    def test_selected_assets_preserves_scan_order_from_cache(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        first = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        second = core.AssetImage(Path("/project/assets/b.png"), Path("assets/b.png"))
        browser.selected = {second.path, first.path}
        browser.image_by_path = {first.path: first, second.path: second}
        browser.image_order_by_path = {first.path: 0, second.path: 1}

        self.assertEqual(browser.selected_assets(), [first, second])

    def test_wheel_scroll_units_supports_mac_trackpad_small_delta(self) -> None:
        self.assertEqual(core.wheel_scroll_units(-1, 0.0), (1, 0.0))
        self.assertEqual(core.wheel_scroll_units(1, 0.0), (-1, 0.0))

    def test_wheel_scroll_units_supports_classic_mousewheel_delta(self) -> None:
        self.assertEqual(core.wheel_scroll_units(-120, 0.0), (1, 0.0))
        self.assertEqual(core.wheel_scroll_units(120, 0.0), (-1, 0.0))

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

    def test_parse_image_size_accepts_width_height_text(self) -> None:
        self.assertEqual(core.parse_image_size("32x64"), (32, 64))
        self.assertEqual(core.parse_image_size(" 64 X 32 "), (64, 32))

    def test_default_resize_output_path_uses_png_and_avoids_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tile.jpg"
            existing = Path(tmp) / "tile_resize_32x32.png"
            existing.write_bytes(b"already here")

            target = core.default_resize_output_path(source, (32, 32))

        self.assertEqual(target.name, "tile_resize_32x32_2.png")

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

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_crop_boxes_to_files_saves_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            image = core.Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            image.putpixel((0, 0), (255, 0, 0, 255))
            image.putpixel((1, 0), (0, 255, 0, 255))
            image.save(source)

            saved = core.crop_boxes_to_files(source, [(0, 0, 1, 1), (1, 0, 2, 1)])

            self.assertEqual([path.name for path in saved], [
                "source_crop_0_0_1x1.png",
                "source_crop_1_0_1x1.png",
            ])
            self.assertTrue(all(path.exists() for path in saved))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_resize_image_to_file_uses_nearest_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            target = Path(tmp) / "resize.png"
            core.Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(source)

            core.resize_image_to_file(source, target, (4, 8))

            with core.Image.open(target) as resized:
                self.assertEqual(resized.size, (4, 8))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_make_color_transparent_only_changes_matching_opaque_pixels(self) -> None:
        image = core.Image.new("RGBA", (3, 1))
        image.putdata([(255, 255, 255, 255), (255, 255, 255, 0), (1, 2, 3, 255)])

        converted = core.make_color_transparent(image, (255, 255, 255))

        self.assertEqual(
            list(converted.getdata()),
            [(255, 255, 255, 0), (255, 255, 255, 0), (1, 2, 3, 255)],
        )

if __name__ == "__main__":
    unittest.main()
