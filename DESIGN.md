# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-09-01
- Primary product surfaces: Tkinter asset grid, image detail/crop editor, prompt/style bottom panel.
- Evidence reviewed: `README.md`, `asset_browser/constants.py`, `asset_browser/ui_layout.py`, `asset_browser/ui_app.py`, `asset_browser/crop_window.py`.

## Brand
- Personality: Quiet local production tool for pixel-art asset maintenance.
- Trust signals: Predictable file operations, visible backup behavior, clear shortcut labels.
- Avoid: Decorative gradients, dense unlabeled button clusters, marketing-like surfaces.

## Product goals
- Goals: Show many assets at once, batch-select quickly, edit/crop sprites without leaving the app.
- Non-goals: Full replacement for Aseprite or a general image editor.
- Success signals: Users can distinguish folder/size/transparent state at a glance and reach the next action without scanning every button.

## Personas and jobs
- Primary personas: Solo developer/artist using Codex-assisted asset iteration.
- User jobs: Select asset lists, inspect sprite sheets, crop variants, paint/fill small edits, apply palette/transparency changes.
- Key contexts of use: Local macOS development, many 32x32 sprites, frequent keyboard shortcuts.

## Information architecture
- Primary navigation: Scan path and filter at the top, selection/copy/file actions on the left, grouped asset grid in the center, image operations on the right, collapsible prompt/style panel at the bottom.
- Core routes/screens: Main browser, image detail editor.
- Content hierarchy: Assets first, file actions second, prompt/style metadata last.

## Design principles
- Principle 1: Group buttons by task sequence, not by implementation module.
- Principle 2: Keep canvas and thumbnails dominant; move secondary operations to side panels instead of stacking them above the grid.
- Tradeoffs: Slightly more visible grouping is acceptable when it reduces accidental destructive edits.

## Visual language
- Color: Mostly neutral app chrome with existing teal selection color.
- Typography: Tk default fonts, compact labels, Korean UI text.
- Spacing/layout rhythm: Small fixed groups, stable cell sizes, no layout shift on selection.
- Shape/radius/elevation: Flat Tk controls, thin borders only where they clarify sections.
- Motion: None.
- Imagery/iconography: Text plus simple symbols for commands; pixel previews use nearest scaling.

## Components
- Existing components to reuse: `_button`, fixed grid cells, grouped headers, bottom panel tabs.
- New/changed components: Main side action panels, image editor tool rail, image editor inspector panel.
- Variants and states: Selected tool, dirty edit status, transparent/opaque asset badge.
- Token/component ownership: `asset_browser/constants.py` owns colors; layout modules own placement.

## Accessibility
- Target standard: Keyboard-accessible local desktop utility.
- Keyboard/focus behavior: Every common button displays its shortcut in the label.
- Contrast/readability: Neutral backgrounds with dark text and visible selected states.
- Screen-reader semantics: Tk labels/buttons remain native widgets.
- Reduced motion and sensory considerations: No animation.

## Responsive behavior
- Supported breakpoints/devices: macOS desktop windows down to the app min sizes.
- Layout adaptations: Main browser uses left/right side panels; image detail keeps tool rail and inspector fixed.
- Touch/hover differences: Optimized for mouse/trackpad and keyboard.

## Interaction states
- Loading: Status bar and empty grid message.
- Empty: Grid shows Korean empty-state text.
- Error: Dialogs for destructive or failed file actions.
- Success: Status bar reports saved/copied/converted result.
- Disabled: Prefer no-op plus status/dialog over hidden actions.
- Offline/slow network, if applicable: Not applicable.

## Content voice
- Tone: Short, direct Korean production-tool labels.
- Terminology: Use `이미지`, `크롭`, `페인트`, `투명`, `팔레트`, `프롬프트`.
- Microcopy rules: Destructive commands name the affected target and keep shortcut labels visible.

## Implementation constraints
- Framework/styling system: Python Tkinter, Pillow optional but preferred.
- Design-token constraints: Reuse existing constants; no new dependency for UI styling.
- Performance constraints: Avoid per-render expensive image reads; cache scan metadata.
- Compatibility constraints: Keep direct script wrapper import/export compatibility.
- Test/screenshot expectations: Unit-test pure behavior; smoke-run Tk app after layout changes.

## Open questions
- [ ] Whether the editor should eventually support true per-pixel pencil drawing instead of flood fill.
