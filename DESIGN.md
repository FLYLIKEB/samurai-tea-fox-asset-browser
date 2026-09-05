# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-09-05
- Primary product surfaces: Tkinter asset grid, image detail/crop editor, prompt/style bottom panel.
- Evidence reviewed: `README.md`, `asset_browser/constants.py`, `asset_browser/ui_layout.py`, `asset_browser/ui_app.py`, `asset_browser/ui_widgets.py`, `asset_browser/crop_window.py`, Aseprite 공식 Workspace·Tool Bar·Keyboard Shortcuts·Sprite Editor 문서.

## Brand
- Personality: Quiet local production tool for pixel-art asset maintenance.
- Trust signals: Predictable file operations, visible backup behavior, clear shortcut labels.
- Avoid: Decorative gradients, dense unlabeled button clusters, marketing-like surfaces.

## Product goals
- Goals: Show many assets at once, batch-select quickly, edit/crop sprites without leaving the app.
- Non-goals: Full replacement for Aseprite or a general image editor.
- Success signals: Users can distinguish folder/size/transparent state at a glance, including 64x64+ thumbnails, and 상세 편집에서 현재 도구·줌·미저장 상태와 다음 작업을 즉시 파악한다.

## Personas and jobs
- Primary personas: Solo developer/artist using Codex-assisted asset iteration.
- User jobs: Select asset lists, inspect sprite sheets, crop variants, draw/erase/fill small edits, apply palette/transparency changes.
- Key contexts of use: Local macOS development, many 32x32 sprites, frequent keyboard shortcuts.

## Information architecture
- Primary navigation: Scan path and filter at the top, selection/copy/file actions on the left, 폴더와 하위 폴더를 단계별로 여닫는 이미지 트리를 중앙에 두고, image operations on the right, collapsible prompt/style panel at the bottom.
- Core routes/screens: Main browser, image detail editor.
- Content hierarchy: Assets first, file actions second, prompt/style metadata last.

## Design principles
- Principle 1: Group buttons by task sequence, not by implementation module.
- Principle 2: Keep canvas and thumbnails dominant; move secondary operations to side panels or tabs instead of stacking them above the grid. 메인 브라우저와 상세 편집창은 같은 평면형 버튼, hover 툴팁, teal 선택 상태를 공유한다.
- Principle 3: Aseprite의 익숙한 `B/E/I/H`, `Space` 임시 이동, 단계별 줌 흐름을 재사용하되 현재 도구에 없는 복잡도는 추가하지 않는다.
- Tradeoffs: Slightly more visible grouping is acceptable when it reduces accidental destructive edits.

## Visual language
- Color: Mostly neutral app chrome with existing teal selection color. 메인 브라우저는 흰 패널과 옅은 청회색 작업 배경을 사용하고, 주요 실행 한 곳에만 teal 강조색을 쓴다. 상세 편집 캔버스는 어두운 작업 배경과 원본 픽셀보다 큰 중간 회색 투명 체커를 사용한다. 밝거나 어두운 스프라이트는 `체커`·`밝게`·`어둡게` 배경을 전환해 실재 픽셀 경계를 확인한다.
- Typography: Tk default fonts, compact labels, Korean UI text.
- Spacing/layout rhythm: Small fixed groups, stable cell sizes, no layout shift on selection. 32x32 에셋은 한 화면에 더 많이 보이도록 셀과 사이드바 여백을 최소화한다.
- Shape/radius/elevation: macOS에서도 일관되게 보이는 평면형 기능 버튼을 사용한다. 패널 외곽과 입력 필드에만 얇은 경계를 두고 기능 그룹마다 중첩된 박스를 만들지 않는다.
- Motion: None.
- Imagery/iconography: Text plus simple symbols for commands; pixel previews use nearest scaling and large assets keep aspect ratio in thumbnail bounds.

## Components
- Existing components to reuse: `_button`, fixed grid cells, grouped headers, bottom panel tabs.
- New/changed components: Main side action panels, 메인·상세 편집 공용 macOS 일관형 `ModernButton`, 모든 기능 버튼의 지연형 설명 툴팁, 선택 상태를 공유하는 image editor tool rail, 상단 문서·실행 취소·줌·투명 보기 바, `색상`/`선택·저장` 탭 인스펙터, 현재 스캔 경로의 상위 폴더 이동 버튼, `-100%`에서 `100%`까지 조정하는 보정 강도 슬라이더, 폴더·하위 폴더·이미지 크기 그룹을 별도로 여닫는 계층형 이미지 목록.
- Variants and states: Selected tool, dirty edit status, undo/redo availability, zoom and painted-pixel-only grid state, `체커`·`밝게`·`어둡게` 투명 배경 보기, line preview, transparent/opaque asset badge. 완전히 투명한 픽셀에는 격자선을 표시하지 않는다.
- Token/component ownership: `asset_browser/constants.py` owns colors; layout modules own placement.

## Accessibility
- Target standard: Keyboard-accessible local desktop utility.
- Keyboard/focus behavior: 공통 기능 버튼은 키보드 포커스와 Enter·Space 실행을 지원한다. 단축키는 화면 혼잡을 줄이기 위해 툴팁에서 확인할 수 있다. 텍스트 입력에 포커스가 있을 때는 캔버스 도구 단축키를 적용하지 않는다.
- Contrast/readability: Neutral backgrounds with dark text and visible selected states.
- Screen-reader semantics: 입력 필드와 선택 컨트롤은 Tk native widget을 유지한다. 평면형 기능 버튼은 텍스트, 키보드 포커스, Enter·Space 실행을 제공하며 native button role 보강은 후속 검토 대상으로 둔다.
- Reduced motion and sensory considerations: No animation.

## Responsive behavior
- Supported breakpoints/devices: macOS desktop windows down to the app min sizes.
- Layout adaptations: Main browser uses narrower left/right side panels so the asset canvas retains priority; image detail keeps tool rail and inspector fixed.
- Touch/hover differences: Optimized for mouse/trackpad and keyboard.

## Interaction states
- Loading: Status bar and empty grid message.
- Empty: Grid shows Korean empty-state text.
- Error: Dialogs for destructive or failed file actions; 미저장 편집창을 닫을 때 저장·폐기·취소를 선택한다.
- Success: Status bar reports saved/copied/converted result. 기능 버튼에 포인터를 약 0.45초 올리면 화면 안쪽에 동작 설명과 단축키를 표시한다.
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
- [ ] Whether the editor should support multi-pixel brush sizes beyond 1px.
