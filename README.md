# Samurai Tea Fox Asset Browser

`assets/` 아래 이미지를 로컬 Tkinter 앱에서 확인하고, 선택한 경로나
Codex에 바로 붙여넣을 프롬프트를 복사하는 독립 도구입니다.

대상 게임 프로젝트 루트에서 실행합니다:

```sh
python3 /Users/jwp/Developer/samurai-tea-fox-asset-browser/asset_browser/asset_browser.py
```

옵션:

```sh
python3 /Users/jwp/Developer/samurai-tea-fox-asset-browser/asset_browser/asset_browser.py --project-root /path/to/game --root assets/sprites
python3 /Users/jwp/Developer/samurai-tea-fox-asset-browser/asset_browser/asset_browser.py --scale 6
python3 /Users/jwp/Developer/samurai-tea-fox-asset-browser/asset_browser/asset_browser.py --list-images
```

설치해서 쓰는 경우:

```sh
python3 -m pip install -e /Users/jwp/Developer/samurai-tea-fox-asset-browser
asset-browser --project-root /path/to/game
```

기능:

- 선택한 폴더 아래의 일반 이미지 포맷을 재귀적으로 스캔합니다.
- 32×32 픽셀아트 이미지는 기본 2배율인 64×64 크기로 보여줍니다.
- 32×64처럼 긴 타일은 같은 배율로 64×128 크기로 보여주고, 64×64 이상 또는 긴 시트는 요약 카드로 보여줍니다.
- 단색 중심의 미니멀 격자 UI에서 여러 이미지를 선택할 수 있습니다.
- 상단 버튼은 선택, 파일, 복사, 크기, 투명화, 팔레트, 보정 작업 단위로 나뉘어 배치됩니다.
- 스캔 루트 안의 내부 폴더별로 이미지를 묶어 보여줍니다.
- 이미지 셀과 128px 썸네일 박스 크기를 고정해 파일별 영역이 흔들리지 않습니다.
- 선택한 이미지의 상대경로, 절대경로, Codex용 배치 프롬프트를 복사합니다.
- 하단 작업 패널은 접었다 펼 수 있으며, 접힌 상태에서는 이미지 그리드가 화면을 최대한 차지합니다.
- 펼친 하단 편집창에서 복사될 Codex 프롬프트를 확인하고 직접 수정할 수 있습니다.
- 기본 프롬프트는 대상 프로젝트의 `tools/asset_browser/default_prompt_template.txt`에서 관리하며 앱 안에서 수정/저장할 수 있습니다.
- `assets/style/art-style-tokens.json`의 팔레트, 컨셉, 이미지 생성 토큰을 앱 안에서 요약 확인하고 원본 JSON을 복사할 수 있습니다.
- 기본 프롬프트와 스타일 토큰은 정사각형 타일 기반 탑뷰 로그라이크에 맞춰 캐릭터, 맵, 맵 내 사물을 모두 정면 시점으로 유지하도록 안내합니다.
- 전역 팔레트와 바이옴 포인트 색을 실제 색상 스와치로 볼 수 있습니다.
- 팔레트 색상칩을 클릭해 시스템 색상 선택기로 색을 수정하고 JSON에 바로 저장할 수 있습니다.
- `팔레트 테스트 보기`를 켜면 원본 파일을 수정하지 않고 현재 팔레트로 이미지가 어떻게 바뀌는지 썸네일에서 미리볼 수 있습니다.
- `표시 이미지 실제 변환`을 누르면 현재 화면에 표시된 이미지 전체를 팔레트 색으로 실제 변환합니다.
- 실제 변환 전 확인 팝업을 띄우고, 원본은 `tools/asset_browser/palette_backups/` 아래에 자동 백업합니다.
- 스캔 폴더, 기본 프롬프트 템플릿, 아트 스타일 토큰 파일을 Finder에서 바로 볼 수 있습니다.
- 선택한 상대경로 목록을 `.txt` 파일로 저장합니다.
- 선택한 이미지 파일을 확인 후 실제 삭제할 수 있습니다.
- 선택한 이미지를 `32x32`, `32x64`, `64x64` 같은 지정 크기의 새 PNG로 리사이즈 저장할 수 있습니다.
- 색상 선택기로 배경색을 고른 뒤 선택 이미지에서 해당 색상 주변 범위까지 투명으로 실제 변경할 수 있습니다. 기본은 외곽과 연결된 배경만 지우며, 체크를 끄면 같은 색 전체를 지웁니다. 변경 전 원본은 자동 백업합니다.
- 이미지 목록은 폴더/타일 크기별 구획으로 나뉘며, 각 이미지와 구획 헤더에 투명/불투명 여부가 표시됩니다. 투명 이미지는 체커 배경 위에 미리보기됩니다.
- 이미지 위를 누른 채 드래그하면 지나가는 이미지들이 빠르게 선택됩니다. 가장자리로 드래그하면 목록이 자동으로 조금씩 스크롤됩니다.
- 32x32보다 큰 이미지는 더블클릭해 원본 픽셀 좌표 기준으로 영역을 드래그하고 새 PNG로 자동 크롭 저장할 수 있습니다.
- 이미지 상세보기는 좌측 도구막대, 중앙 캔버스, 우측 색상/크롭/저장 패널 구조로 열립니다.
- 크롭 창에서 한 번 클릭하면 32x32 영역이 잡히고, `32x32 맞춤`으로 현재 선택 영역을 타일 크기에 맞출 수 있습니다.
- 크롭 저장은 파일 대화상자 없이 `원본명_crop_x_y_가로x세로.png` 형식으로 저장하며, 창을 닫지 않아 이어서 작업할 수 있습니다.
- 크롭 창에서 `영역 추가`로 여러 영역을 모은 뒤 `모두 저장`으로 한 번에 분리 저장할 수 있습니다.
- 크롭 창의 `Cmd+S` 또는 `Ctrl+S`는 현재 영역을 바로 저장하고, `Shift+Cmd+S` 또는 `Shift+Ctrl+S`는 대기 영역을 모두 저장합니다.

주요 단축키:

- `Cmd+A`: 전체 선택
- `Esc`: 선택 해제
- `Delete`: 선택 삭제
- `Cmd+C`: Codex 프롬프트 복사
- `Cmd+R`: 새로고침
- `Cmd+O`: 폴더 찾기
- `Cmd+Z`: 선택 리사이즈
- `Cmd+G`: 배경 투명화
- `Cmd+P`: 팔레트 변환

기본 프롬프트 템플릿에서 쓸 수 있는 치환값:

- `{asset_list}`: 선택한 이미지 상대경로 목록
- `{asset_count}`: 선택한 이미지 개수
- `{project_root}`: 프로젝트 루트 절대경로

Pillow는 선택 사항입니다. 설치되어 있으면 JPG, BMP, WEBP, TGA, TIFF 같은
포맷도 미리볼 수 있습니다. Pillow가 없어도 Tkinter 기본 지원 포맷인 PNG,
GIF 등은 미리볼 수 있습니다.

## 코드 구조

- `asset_browser.py`: 직접 실행용 호환 래퍼입니다.
- `cli.py`: 인자 파싱과 CLI 실행 흐름입니다.
- `crop_window.py`: 원본 픽셀 좌표 기준 크롭 창입니다.
- `ui_app.py`: `AssetBrowser` 상태와 이미지 그리드 렌더링입니다.
- `ui_layout.py`: Tkinter 레이아웃 구성입니다.
- `ui_actions.py`: 선택, 복사, 템플릿 저장, Finder 열기, 실제 팔레트 변환 액션입니다.
- `ui_palette.py`: 스타일 토큰 표시와 팔레트 색상 편집 패널입니다.
- `scanner.py`: `assets/` 이미지 검색과 폴더별 그룹 분류입니다.
- `prompting.py`: Codex 프롬프트 템플릿 로드와 렌더링입니다.
- `style_tokens.py`: `assets/style/art-style-tokens.json` 로드, 저장, 요약, 팔레트 추출입니다.
- `image_ops.py`: Pillow 기반 팔레트 미리보기와 실제 이미지 변환입니다.
