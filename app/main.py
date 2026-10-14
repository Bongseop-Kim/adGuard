"""adGuard 진입점 (골격).

- 명령줄 모드: adguard.exe <URL>  → 창 없이 탐지하고 result.json을 쓴다
- 창 모드:     adguard.exe        → WebView2 창(pywebview)에서 URL 입력·탐지 시작
- 검증 모드:   adguard.exe --smoke-gui <URL> → 창을 띄워 자동으로 탐지하고 닫는다 (CI용)
"""
import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

VERSION = "0.1.0"
KST = timezone(timedelta(hours=9))


def base_dir():
    # PyInstaller로 묶이면 exe가 있는 폴더, 아니면 이 파일의 폴더
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def write_json(path, data):
    # UTF-8(BOM 없음), 임시 파일에 쓴 뒤 교체해서 반쯤 쓰인 파일이 남지 않게 한다
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def scan(url, log=print):
    browsers = os.path.join(base_dir(), "browsers")
    if os.path.isdir(browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers  # PC에 같은 환경변수가 있어도 동봉본을 쓴다
    from crawler import crawl
    from detect import analyze

    started, t0 = datetime.now(KST), time.monotonic()
    pages = []
    try:
        pages = asyncio.run(crawl(url, analyze, log=log))
    finally:  # 크롤이 죽어도 파싱 가능한 result.json은 남긴다 (파일이 없거나 깨지면 0점)
        findings, seen = [], set()
        for pg in pages:
            for f in pg["result"] or []:
                key = (pg["url"], f["location"], f["technique"])  # 채점 단위. 같은 조합은 1건
                if key in seen:
                    continue
                seen.add(key)
                findings.append({"id": "f_%03d" % (len(findings) + 1), "url": pg["url"], "is_violation": True,
                                 "location": f["location"], "evidence_text": f["evidence_text"] or f["location"],
                                 "technique": f["technique"]})
        meta = {
            "topic": "TOPIC",
            "entry_url": url,
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
            "elapsed_sec": round(time.monotonic() - t0, 2),
            "tool_version": VERSION,
        }
        out = os.path.join(base_dir(), "result.json")
        write_json(out, {"meta": meta, "findings": findings})
    log("탐지 완료: %d쪽, %d건 -> %s" % (len(pages), len(findings), out))


PAGE = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>adGuard</title>
<body style="font-family:sans-serif;margin:24px">
<h1>adGuard</h1>
<input id="url" style="width:420px" placeholder="점검할 URL"> <button id="go" onclick="start()">탐지 시작</button>
<pre id="log"></pre>
<script>
function log(s){ document.getElementById('log').textContent += s + '\\n'; }
function start(){ document.getElementById('go').disabled = true; pywebview.api.start(document.getElementById('url').value); }
</script></body></html>"""


class Api:
    def __init__(self, smoke=False):
        self._window = None  # 밑줄: JS에 노출하지 않음
        self._smoke = smoke

    def start(self, url):
        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _run(self, url):
        def log(msg):
            print(msg, flush=True)
            self._window.evaluate_js("log(%s)" % json.dumps(msg))
        try:
            scan(url, log)
        except Exception as e:
            log("오류: %r" % e)
        if self._smoke:
            self._window.destroy()


def gui(smoke_url=None):
    import webview

    api = Api(smoke=bool(smoke_url))
    api._window = webview.create_window("adGuard", html=PAGE, js_api=api, width=760, height=520)
    if smoke_url:  # 창이 뜨면 URL을 넣고 "탐지 시작"을 누른 것과 같게 한다
        api._window.events.loaded += lambda: api._window.evaluate_js(
            "function go(){document.getElementById('url').value=%s; start();}"
            "if (window.pywebview && pywebview.api && pywebview.api.start) go(); else window.addEventListener('pywebviewready', go);"
            % json.dumps(smoke_url))
    webview.start(gui="edgechromium")  # IE 엔진으로 넘어가지 않게 WebView2만 허용
    print("UI: WebView2 창 종료", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows에서 출력을 파일로 돌려도 한글이 깨지지 않게
    args = sys.argv[1:]
    if args[:1] == ["--smoke-gui"]:
        gui(args[1])
    elif args:
        scan(args[0])
    else:
        gui()  # ponytail: WebView2 실패 시 로컬 서버+기본 브라우저 예비 경로는 todo/06에서 추가


if __name__ == "__main__":
    main()
