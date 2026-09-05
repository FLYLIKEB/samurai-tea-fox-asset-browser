from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from asset_browser import asset_browser as core
from asset_browser import ui_actions

class FakeVar:
    def __init__(self, value=None) -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value

class AssetBrowserCoreTest(unittest.TestCase):
    def test_parse_args_defaults_to_2x_scale(self) -> None:
        args = core.parse_args([])

        self.assertEqual(args.scale, 2)

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

    def test_current_group_labels_groups_by_folder_then_tile_size(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        browser.project_root = Path("/project")
        browser.asset_root = browser.project_root / "assets"
        fox = core.AssetImage(
            browser.project_root / "assets" / "sprites" / "fox.png",
            Path("assets/sprites/fox.png"),
        )
        grass = core.AssetImage(
            browser.project_root / "assets" / "tiles" / "grass.png",
            Path("assets/tiles/grass.png"),
        )
        browser.filtered_images = [fox, grass]
        browser.image_size_by_path = {fox.path: (32, 64), grass.path: (32, 32)}
        browser.expanded_group_labels = set()
        browser.default_expanded_group_labels = set()

        self.assertEqual(browser.current_group_labels(), ["sprites / 32x64", "tiles / 32x32"])

    def test_current_group_labels_starts_groups_collapsed_for_fast_initial_load(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        browser.project_root = Path("/project")
        browser.asset_root = browser.project_root / "assets"
        fox = core.AssetImage(
            browser.project_root / "assets" / "sprites" / "fox.png",
            Path("assets/sprites/fox.png"),
        )
        sheet = core.AssetImage(
            browser.project_root / "assets" / "sprites" / "sheet.png",
            Path("assets/sprites/sheet.png"),
        )
        browser.filtered_images = [fox, sheet]
        browser.image_size_by_path = {fox.path: (32, 32), sheet.path: (64, 64)}
        browser.expanded_group_labels = set()
        browser.default_expanded_group_labels = set()

        browser.current_group_labels()

        self.assertNotIn("sprites / 32x32", browser.expanded_group_labels)
        self.assertNotIn("sprites / 대형/시트 (64x64 이상)", browser.expanded_group_labels)

    def test_group_can_be_expanded_after_fast_initial_load(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        browser.project_root = Path("/project")
        browser.asset_root = browser.project_root / "assets"
        fox = core.AssetImage(
            browser.project_root / "assets" / "sprites" / "fox.png",
            Path("assets/sprites/fox.png"),
        )
        browser.filtered_images = [fox]
        browser.image_size_by_path = {fox.path: (32, 32)}
        browser.expanded_group_labels = set()
        browser.default_expanded_group_labels = set()

        label = browser.current_group_labels()[0]
        browser.expanded_group_labels.add(label)

        self.assertIn("sprites / 32x32", browser.expanded_group_labels)

    def test_rescan_reads_size_without_eager_transparency_decoding(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        asset = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        browser.project_root = Path("/project")
        browser.path_var = FakeVar("/project/assets")
        browser.selected = set()
        browser.apply_filter = lambda: None
        browser.update_prompt_preview = lambda **_kwargs: None
        browser._read_image_size = lambda _path: (32, 32)
        browser._read_image_info = lambda _path: self.fail("rescan must not decode transparency")
        original_find_images = ui_actions.find_images
        try:
            ui_actions.find_images = lambda *_args: [asset]
            browser.rescan()
        finally:
            ui_actions.find_images = original_find_images

        self.assertEqual(browser.image_size_by_path, {asset.path: (32, 32)})
        self.assertEqual(browser.image_has_transparency_by_path, {asset.path: None})

    def test_thumbnail_scale_keeps_32px_assets_at_default_2x(self) -> None:
        scaled_size = core.AssetBrowser._scaled_size

        self.assertEqual(scaled_size(None, 32, 32, core.PREVIEW_SCALE), (64, 64))
        self.assertEqual(scaled_size(None, 32, 64, core.PREVIEW_SCALE), (64, 128))
        self.assertEqual(scaled_size(None, 64, 64, core.PREVIEW_SCALE), (104, 104))
        self.assertEqual(scaled_size(None, 32, 128, core.PREVIEW_SCALE), (26, 104))

    def test_fit_size_within_preserves_aspect_ratio(self) -> None:
        self.assertEqual(core.fit_size_within((64, 64), (104, 104)), (104, 104))
        self.assertEqual(core.fit_size_within((256, 128), (104, 104)), (104, 52))
        self.assertEqual(core.fit_size_within((32, 128), (104, 104)), (26, 104))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_image_info_reports_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transparent = Path(tmp) / "transparent.png"
            opaque = Path(tmp) / "opaque.png"
            core.Image.new("RGBA", (2, 1), (0, 0, 0, 0)).save(transparent)
            core.Image.new("RGBA", (2, 1), (0, 0, 0, 255)).save(opaque)

            self.assertEqual(core.image_info(transparent), ((2, 1), True))
            self.assertEqual(core.image_info(opaque), ((2, 1), False))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_composite_on_black_background_reveals_transparent_pixels(self) -> None:
        image = core.Image.new("RGBA", (2, 1), (10, 20, 30, 255))
        image.putpixel((1, 0), (10, 20, 30, 0))

        composited = core.composite_on_black_background(image)

        self.assertEqual(composited.getpixel((0, 0)), (10, 20, 30, 255))
        self.assertEqual(composited.getpixel((1, 0)), (0, 0, 0, 255))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_replace_color_replaces_all_matching_pixels_and_preserves_alpha(self) -> None:
        image = core.Image.new("RGBA", (3, 1), (10, 20, 30, 255))
        image.putpixel((1, 0), (10, 20, 30, 80))
        image.putpixel((2, 0), (1, 2, 3, 255))
        replaced, changed = core.replace_color(image, (10, 20, 30), (200, 0, 0))
        self.assertEqual(changed, 2)
        self.assertEqual(replaced.getpixel((0, 0)), (200, 0, 0, 255))
        self.assertEqual(replaced.getpixel((1, 0)), (200, 0, 0, 80))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_expand_canvas_to_selection_pads_and_offsets_source(self) -> None:
        image = core.Image.new("RGBA", (2, 2), (1, 2, 3, 255))
        expanded = core.expand_canvas_to_selection(image, (-1, -1, 3, 3))
        self.assertEqual(expanded.size, (4, 4))
        self.assertEqual(expanded.getpixel((1, 1)), (1, 2, 3, 255))
        self.assertEqual(expanded.getpixel((0, 0)), (0, 0, 0, 0))

    def test_tile_size_group_labels_large_images_as_summary(self) -> None:
        self.assertEqual(core.tile_size_group_label((32, 32)), "32x32")
        self.assertEqual(core.tile_size_group_label((32, 64)), "32x64")
        self.assertEqual(core.tile_size_group_label((64, 64)), "대형/시트 (64x64 이상)")
        self.assertEqual(core.tile_size_group_label((32, 128)), "긴 시트 (128px 이상)")
        self.assertEqual(core.tile_size_group_label((48, 32)), "기타 48x32")

    def test_toggle_selection_updates_only_one_cell_without_grid_render(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        asset = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        calls: list[str] = []
        browser.selected = set()
        browser.update_cell_selection = lambda path: calls.append(f"cell:{path.name}")
        browser._set_status = lambda: calls.append("status")
        browser.schedule_prompt_preview_update = lambda: calls.append("prompt")
        browser.render_grid = lambda: self.fail("selection should not rebuild the full grid")

        browser.toggle_selection(asset)

        self.assertEqual(browser.selected, {asset.path})
        self.assertEqual(calls, ["cell:a.png", "status", "prompt"])

    def test_status_includes_visible_transparent_count(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        transparent = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        opaque = core.AssetImage(Path("/project/assets/b.png"), Path("assets/b.png"))
        messages: list[str] = []
        browser.images = [transparent, opaque]
        browser.filtered_images = [transparent, opaque]
        browser.selected = set()
        browser.prompt_dirty = False
        browser.template_dirty = False
        browser.image_has_transparency_by_path = {transparent.path: True, opaque.path: False}
        browser.status_var = type("StatusVar", (), {"set": lambda _self, value: messages.append(value)})()

        browser._set_status()

        self.assertEqual(messages[-1], "전체 2개 | 표시 2개 | 투명 1개 | 선택 0개")

    def test_selected_assets_preserves_scan_order_from_cache(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        first = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        second = core.AssetImage(Path("/project/assets/b.png"), Path("assets/b.png"))
        browser.selected = {second.path, first.path}
        browser.image_by_path = {first.path: first, second.path: second}
        browser.image_order_by_path = {first.path: 0, second.path: 1}

        self.assertEqual(browser.selected_assets(), [first, second])

    def test_visible_assets_preserves_scan_order(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        first = core.AssetImage(Path("/project/assets/a.png"), Path("assets/a.png"))
        second = core.AssetImage(Path("/project/assets/b.png"), Path("assets/b.png"))
        browser.image_by_path = {first.path: first, second.path: second}
        browser.image_order_by_path = {first.path: 0, second.path: 1}
        browser.cell_widgets = {
            second.path: type(
                "Widgets",
                (),
                {"cell": type("Cell", (), {"winfo_y": lambda _self: 10, "winfo_height": lambda _self: 128})()},
            )(),
            first.path: type(
                "Widgets",
                (),
                {"cell": type("Cell", (), {"winfo_y": lambda _self: 20, "winfo_height": lambda _self: 128})()},
            )(),
        }
        browser.canvas = type(
            "Canvas",
            (),
            {
                "canvasy": lambda _self, value: value,
                "winfo_height": lambda _self: 200,
            },
        )()

        self.assertEqual(browser.visible_assets(), [first, second])

    def test_folder_path_for_group_uses_group_image_parent(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        asset = core.AssetImage(
            Path("/project/assets/sprites/enemies/oni.png"),
            Path("assets/sprites/enemies/oni.png"),
        )

        self.assertEqual(browser.folder_path_for_group([asset]), Path("/project/assets/sprites/enemies"))

    def test_navigate_to_asset_folder_changes_scan_root_and_clears_filter_groups(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        browser.project_root = Path("/project")
        browser.path_var = FakeVar("/project/assets/sprites")
        browser.filter_var = FakeVar("fox")
        browser.expanded_group_labels = {"sprites / 32x32"}
        browser.default_expanded_group_labels = {"sprites / 32x32"}
        browser.status_var = FakeVar("")
        rescans: list[Path] = []
        browser.rescan = lambda: rescans.append(Path(browser.path_var.get()))

        result = browser.navigate_to_asset_folder(Path("/project/assets/sprites/enemies"))

        self.assertEqual(result, "break")
        self.assertEqual(rescans, [Path("/project/assets/sprites/enemies")])
        self.assertEqual(browser.filter_var.get(), "")
        self.assertEqual(browser.expanded_group_labels, set())
        self.assertEqual(browser.default_expanded_group_labels, set())
        self.assertIn("/project/assets/sprites/enemies", browser.status_var.get())

    def test_palette_conversion_targets_selected_assets_only(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        selected = core.AssetImage(Path("/project/assets/selected.png"), Path("assets/selected.png"))
        visible = core.AssetImage(Path("/project/assets/visible.png"), Path("assets/visible.png"))
        browser.project_root = Path("/project")
        browser.filtered_images = [selected, visible]
        browser.art_style_data = {"palette": {"global": [{"hex": "#000000"}]}}
        browser.selected_palette_candidate_id = lambda: ""
        browser.selected_assets = lambda: [selected]
        browser.rescan = lambda: None
        browser.status_var = FakeVar("")

        calls: list[list[Path]] = []
        original_apply = ui_actions.apply_palette_to_images
        original_ask = ui_actions.messagebox.askokcancel
        original_info = ui_actions.messagebox.showinfo
        try:
            ui_actions.apply_palette_to_images = (
                lambda paths, _palette, _project_root, _backup_root: (calls.append(paths) or (len(paths), []))
            )
            ui_actions.messagebox.askokcancel = lambda *_args, **_kwargs: True
            ui_actions.messagebox.showinfo = lambda *_args, **_kwargs: None

            browser.apply_palette_to_selected_images()
        finally:
            ui_actions.apply_palette_to_images = original_apply
            ui_actions.messagebox.askokcancel = original_ask
            ui_actions.messagebox.showinfo = original_info

        self.assertEqual(calls, [[selected.path]])
        self.assertIn("팔레트 실제 변환 완료: 1개", browser.status_var.get())

    def test_move_files_to_directory_avoids_name_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "fox.png").write_text("new", encoding="utf-8")
            (target / "fox.png").write_text("old", encoding="utf-8")

            moved, failures = core.move_files_to_directory([source / "fox.png"], target)

        self.assertEqual(failures, [])
        self.assertEqual([path.name for path in moved], ["fox_2.png"])

    def test_replace_file_keeps_target_name_and_deletes_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "kept_name.png"
            source = root / "replacement.png"
            target.write_bytes(b"old")
            source.write_bytes(b"new")

            core.replace_file_with_and_delete_source(target, source)

            self.assertEqual(target.read_bytes(), b"new")
            self.assertFalse(source.exists())

    def test_replace_file_rejects_different_extensions_without_modifying_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "kept_name.png"
            source = root / "replacement.jpg"
            target.write_bytes(b"old")
            source.write_bytes(b"new")

            with self.assertRaises(ValueError):
                core.replace_file_with_and_delete_source(target, source)

            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(source.read_bytes(), b"new")

    def test_godot_sync_runs_project_wide_headless_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "project.godot").write_text("[application]\nconfig/name=\"test\"\n", encoding="utf-8")
            browser = core.AssetBrowser.__new__(core.AssetBrowser)
            browser.project_root = project_root
            browser.status_var = FakeVar("")
            commands: list[list[str]] = []
            original_run = ui_actions.subprocess.run
            original_ask = ui_actions.messagebox.askokcancel
            original_info = ui_actions.messagebox.showinfo
            try:
                ui_actions.subprocess.run = lambda command, **_kwargs: (
                    commands.append(command) or type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                )
                ui_actions.messagebox.askokcancel = lambda *_args, **_kwargs: True
                ui_actions.messagebox.showinfo = lambda *_args, **_kwargs: None

                browser.sync_all_images_to_godot()
            finally:
                ui_actions.subprocess.run = original_run
                ui_actions.messagebox.askokcancel = original_ask
                ui_actions.messagebox.showinfo = original_info

            self.assertEqual(
                commands,
                [["godot", "--headless", "--path", str(project_root), "--editor", "--quit"]],
            )
            self.assertEqual(browser.status_var.get(), "Godot 이미지 메타데이터 전체 반영 완료")

    def test_wheel_scroll_units_supports_mac_trackpad_small_delta(self) -> None:
        self.assertEqual(core.wheel_scroll_units(-1, 0.0), (1, 0.0))
        self.assertEqual(core.wheel_scroll_units(1, 0.0), (-1, 0.0))

    def test_wheel_scroll_units_supports_classic_mousewheel_delta(self) -> None:
        self.assertEqual(core.wheel_scroll_units(-120, 0.0), (1, 0.0))
        self.assertEqual(core.wheel_scroll_units(120, 0.0), (-1, 0.0))

    def test_mousewheel_ignores_widgets_outside_the_asset_grid(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        calls: list[tuple[int, str]] = []
        browser.canvas = object()
        browser.winfo_pointerx = lambda: 0
        browser.winfo_pointery = lambda: 0
        browser.winfo_containing = lambda *_args: None
        browser.scroll_remainder = 0.0
        browser.drag_selecting = False
        browser.scroll_select_var = FakeVar(False)
        browser.after_idle = lambda *_args: self.fail("outside wheel must not schedule grid selection")
        event = type("Event", (), {"widget": object(), "num": None, "delta": -1, "state": 0})()

        self.assertEqual(browser._on_mousewheel(event), "")
        self.assertEqual(calls, [])

    def test_mousewheel_accepts_trackpad_event_when_pointer_is_over_the_grid(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        calls: list[tuple[int, str]] = []
        canvas = type("Canvas", (), {"yview_scroll": lambda _self, units, kind: calls.append((units, kind))})()
        browser.canvas = canvas
        browser.winfo_pointerx = lambda: 100
        browser.winfo_pointery = lambda: 200
        browser.winfo_containing = lambda *_args: canvas
        browser.scroll_remainder = 0.0
        browser.drag_selecting = False
        browser.scroll_select_var = FakeVar(False)
        browser.after_idle = lambda *_args: self.fail("ordinary scrolling must not select assets")
        event = type("Event", (), {"widget": object(), "num": None, "delta": -1, "state": 0})()

        self.assertEqual(browser._on_mousewheel(event), "break")
        self.assertEqual(calls, [(3, "units")])

    def test_mousewheel_scrolls_asset_grid_children_by_three_units(self) -> None:
        browser = core.AssetBrowser.__new__(core.AssetBrowser)
        calls: list[tuple[int, str]] = []
        canvas = type("Canvas", (), {"yview_scroll": lambda _self, units, kind: calls.append((units, kind))})()
        child = type("Child", (), {"master": canvas})()
        browser.canvas = canvas
        browser.scroll_remainder = 0.0
        browser.drag_selecting = False
        browser.scroll_select_var = FakeVar(False)
        browser.after_idle = lambda *_args: self.fail("ordinary scrolling must not select assets")
        event = type("Event", (), {"widget": child, "num": None, "delta": -1, "state": 0})()

        self.assertEqual(browser._on_mousewheel(event), "break")
        self.assertEqual(calls, [(3, "units")])

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

    def test_palette_candidate_colors_overlay_canonical_palette(self) -> None:
        data = {
            "palette": {
                "global": [
                    {"id": "ink", "name": "먹선", "hex": "#111111"},
                    {"id": "paper", "name": "한지", "hex": "#EEEEEE"},
                ],
                "biome_accents": [{"id": "white", "name": "백국", "colors": ["#AAAAAA"]}],
                "candidates": [
                    {
                        "id": "brighter",
                        "name": "밝음",
                        "global": [{"id": "paper", "hex": "#FFFFFF"}],
                        "biome_accents": [{"id": "white", "colors": ["#CCCCCC"]}],
                    }
                ],
            }
        }

        block = core.palette_block(data, "brighter")

        self.assertEqual(block["global"][0]["hex"], "#111111")
        self.assertEqual(block["global"][1]["name"], "한지")
        self.assertEqual(block["global"][1]["hex"], "#FFFFFF")
        self.assertEqual(block["biome_accents"][0]["colors"], ["#CCCCCC"])
        self.assertEqual(
            core.extract_palette_colors(data, "brighter"),
            [(17, 17, 17), (255, 255, 255), (204, 204, 204)],
        )

    def test_apply_palette_candidate_promotes_candidate_to_canonical_palette(self) -> None:
        data = {
            "palette": {
                "global": [{"id": "ink", "hex": "#111111"}],
                "biome_accents": [{"id": "white", "colors": ["#AAAAAA"]}],
                "candidates": [
                    {
                        "id": "brighter",
                        "global": [{"id": "ink", "hex": "#222222"}],
                        "biome_accents": [{"id": "white", "colors": ["#BBBBBB"]}],
                    }
                ],
            }
        }

        self.assertTrue(core.apply_palette_candidate(data, "brighter"))
        self.assertEqual(data["palette"]["global"][0]["hex"], "#222222")
        self.assertEqual(data["palette"]["biome_accents"][0]["colors"], ["#BBBBBB"])

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

    def test_resize_choices_include_tall_character_sizes(self) -> None:
        self.assertIn("64x96", core.RESIZE_CHOICES)
        self.assertIn("96x128", core.RESIZE_CHOICES)

    def test_adjustment_factor_clamps_percent_range(self) -> None:
        self.assertEqual(core.adjustment_factor(-150), 0.0)
        self.assertEqual(core.adjustment_factor(20), 1.2)
        self.assertEqual(core.adjustment_factor(400), 4.0)

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_adjust_image_brightness_preserves_alpha(self) -> None:
        image = core.Image.new("RGBA", (1, 1), (10, 20, 30, 77))

        adjusted = core.adjust_image(image, "밝기", 100)

        self.assertEqual(adjusted.getpixel((0, 0)), (20, 40, 60, 77))

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
    def test_save_cropped_image_to_file_uses_edited_image_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "crop.png"
            image = core.Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            image.putpixel((1, 1), (12, 34, 56, 255))

            core.save_cropped_image_to_file(image, target, (1, 1, 2, 2))

            with core.Image.open(target) as cropped:
                self.assertEqual(cropped.convert("RGBA").getpixel((0, 0)), (12, 34, 56, 255))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_save_rgba_image_to_file_overwrites_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            core.Image.new("RGBA", (1, 1), (0, 0, 0, 255)).save(source)
            edited = core.Image.new("RGBA", (1, 1), (10, 20, 30, 255))

            core.save_rgba_image_to_file(edited, source)

            with core.Image.open(source) as saved:
                self.assertEqual(saved.convert("RGBA").getpixel((0, 0)), (10, 20, 30, 255))

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
    def test_crop_boxes_to_files_can_use_edited_image_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            core.Image.new("RGBA", (2, 1), (0, 0, 0, 255)).save(source)
            edited = core.Image.new("RGBA", (2, 1), (0, 0, 0, 255))
            edited.putpixel((1, 0), (200, 100, 50, 255))

            saved = core.crop_boxes_to_files(source, [(1, 0, 2, 1)], edited)

            with core.Image.open(saved[0]) as cropped:
                self.assertEqual(cropped.convert("RGBA").getpixel((0, 0)), (200, 100, 50, 255))

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
    def test_apply_resize_overwrites_source_and_keeps_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            source = project_root / "assets" / "tile.png"
            backup_root = project_root / "tools" / "asset_browser" / "resize_backups" / "test"
            source.parent.mkdir(parents=True)
            core.Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(source)
            original = source.read_bytes()

            converted, failures = core.apply_resize_to_images(
                [source], (4, 8), project_root, backup_root
            )

            self.assertEqual((converted, failures), (1, []))
            with core.Image.open(source) as resized:
                self.assertEqual(resized.size, (4, 8))
            self.assertEqual((backup_root / "assets" / "tile.png").read_bytes(), original)

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_make_color_transparent_only_changes_matching_opaque_pixels(self) -> None:
        image = core.Image.new("RGBA", (3, 1))
        image.putdata([(255, 255, 255, 255), (255, 255, 255, 0), (1, 2, 3, 255)])

        converted = core.make_color_transparent(image, (255, 255, 255))

        self.assertEqual(
            list(converted.getdata()),
            [(255, 255, 255, 0), (255, 255, 255, 0), (1, 2, 3, 255)],
        )

    def test_color_within_tolerance_checks_each_rgb_channel(self) -> None:
        self.assertTrue(core.color_within_tolerance((250, 248, 245), (255, 255, 255), 10))
        self.assertFalse(core.color_within_tolerance((244, 248, 245), (255, 255, 255), 10))

    def test_line_points_supports_diagonal_pixel_lines(self) -> None:
        self.assertEqual(core.line_points((0, 0), (3, 2)), [(0, 0), (1, 1), (2, 1), (3, 2)])

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_draw_pixel_line_colors_pixels(self) -> None:
        image = core.Image.new("RGBA", (4, 1), (0, 0, 0, 0))

        drawn, changed = core.draw_pixel_line(image, (0, 0), (2, 0), (1, 2, 3, 255))

        self.assertEqual(changed, 3)
        self.assertEqual(
            [drawn.getpixel((x, 0)) for x in range(4)],
            [(1, 2, 3, 255), (1, 2, 3, 255), (1, 2, 3, 255), (0, 0, 0, 0)],
        )

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_erase_pixel_line_clears_alpha(self) -> None:
        image = core.Image.new("RGBA", (3, 1), (10, 20, 30, 255))

        erased, changed = core.erase_pixel_line(image, (0, 0), (1, 0))

        self.assertEqual(changed, 2)
        self.assertEqual(erased.getpixel((0, 0)), (10, 20, 30, 0))
        self.assertEqual(erased.getpixel((2, 0)), (10, 20, 30, 255))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_flood_fill_image_recolors_connected_region_only(self) -> None:
        image = core.Image.new("RGBA", (3, 2))
        image.putdata(
            [
                (1, 1, 1, 255),
                (1, 1, 1, 255),
                (9, 9, 9, 255),
                (1, 1, 1, 255),
                (9, 9, 9, 255),
                (9, 9, 9, 255),
            ]
        )

        painted, changed = core.flood_fill_image(image, (0, 0), (255, 0, 0))

        self.assertEqual(changed, 3)
        self.assertEqual(painted.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(painted.getpixel((1, 1)), (9, 9, 9, 255))

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_make_color_transparent_supports_tolerance(self) -> None:
        image = core.Image.new("RGBA", (2, 1))
        image.putdata([(250, 248, 245, 255), (230, 248, 245, 255)])

        converted = core.make_color_transparent(image, (255, 255, 255), tolerance=10)

        self.assertEqual(
            list(converted.getdata()),
            [(250, 248, 245, 0), (230, 248, 245, 255)],
        )

    @unittest.skipIf(core.Image is None, "Pillow is not installed")
    def test_edge_connected_transparency_preserves_enclosed_matching_color(self) -> None:
        image = core.Image.new("RGBA", (5, 5), (255, 255, 255, 255))
        for x in range(1, 4):
            for y in range(1, 4):
                image.putpixel((x, y), (1, 1, 1, 255))
        image.putpixel((2, 2), (255, 255, 255, 255))

        converted = core.make_edge_connected_color_transparent(image, (255, 255, 255))

        self.assertEqual(converted.getpixel((0, 0)), (255, 255, 255, 0))
        self.assertEqual(converted.getpixel((2, 2)), (255, 255, 255, 255))

if __name__ == "__main__":
    unittest.main()
