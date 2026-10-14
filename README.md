# adGuard

점검할 웹사이트 URL 1개를 넣으면 하위 페이지·게시글·댓글·iframe에 숨겨진 불법광고(도박·성인물 등)를 찾아 유형과 위치를 알려주는 Windows 도구.
「공공 웹사이트 불법광고 탐지 도구 개발 공모전」 출품작이며, 목표와 평가 기준은 [docs/GOAL.md](docs/GOAL.md)에 있다.

## 사용 (Windows)

설치는 필요 없다. 압축을 풀고 `adguard.exe`를 실행한다.

| 실행 | 동작 |
|---|---|
| `adguard.exe` (더블클릭) | 창에서 URL 입력 → "탐지 시작" |
| `adguard.exe <URL>` | 창 없이 탐지하고 파일만 쓴다 (채점용) |

결과는 exe와 같은 폴더에 생긴다.

- `result.json`: 채점용 결과
- `report.html`: 단일 파일 보고서 (브라우저로 연다)
- `result.csv`: Excel용 (UTF-8 BOM)
- `history.json`: 지문별 최초 발견일

## 개발 실행 (macOS·Windows 공용)

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium

python app/main.py                 # 화면 모드
python app/main.py <URL>           # 명령줄 모드
```

- 맥에서는 pywebview가 macOS 기본 WebKit 창을 띄운다. 창이 뜨지 않으면 기본 브라우저(`127.0.0.1` 주소)로 연다. 화면과 흐름은 Windows와 같다
- 결과 파일은 `app/` 폴더에 생긴다

## 자체 평가 (eval)

```bash
python eval/scenarios/S1-baseline/serve.py                  # 테스트 사이트 (http://127.0.0.1:8110)
python app/main.py http://127.0.0.1:8110/                   # 다른 터미널에서 탐지
python eval/scorer/score.py S1-baseline app/result.json     # 채점
python eval/validate.py app/result.json                     # 스키마 검사
```

시나리오 목록, 포트, 정답표 형식은 [eval/README.md](eval/README.md)를 본다. `eval/blind/`는 개발 중에 열어 보지 않는다.

## Windows 빌드

push할 때마다 GitHub Actions(`.github/workflows/windows-build.yml`)가 PyInstaller onedir로 빌드한다. Chromium은 exe 옆 `browsers/` 폴더에 함께 넣는다. 빌드한 exe를 한글·공백이 든 경로로 옮겨 명령줄 모드와 창 모드를 모두 실행해 본다.
결과물은 Actions 실행 페이지의 artifact `adguard-windows`에서 받는다.

## 구조

```
app/      main.py(진입점·화면) crawler.py(탐색) detect.py(탐지 4종) report.py(보고서) data/ui.html
eval/     테스트 사이트·정답표·채점기
docs/     GOAL.md, research/(조사), todo/(남은 일), done/(완료 기록)
```
