"""adGuard 진입점 (골격).

- 명령줄 모드: adguard.exe <URL>  → 창 없이 탐지하고 result.json을 쓴다
- 창 모드:     adguard.exe        → WebView2 창(pywebview)에서 URL 입력·탐지 시작
- 검증 모드:   adguard.exe --smoke-gui <URL> → 창을 띄워 자동으로 탐지하고 닫는다 (CI용)
- 결과: exe 폴더에 result.json(채점용), report.html(단일 파일 보고서), result.csv(Excel용), history.json(최초 발견일)
"""
import asyncio
import json
import os
import pathlib
import re
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


def scan(url, log=print, ctl=None, minutes=20):
    """탐지하고 result.json을 쓴다. 반환: (meta, 검출 목록(보고서용 근거 포함))"""
    browsers = os.path.join(base_dir(), "browsers")
    if os.path.isdir(browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers  # PC에 같은 환경변수가 있어도 동봉본을 쓴다
    from crawler import crawl
    from detect import analyze

    ctl = {} if ctl is None else ctl
    started, t0 = datetime.now(KST), time.monotonic()
    try:
        asyncio.run(crawl(url, analyze, log=log, ctl=ctl, time_limit=minutes * 60))
    except Exception as e:
        log("오류로 탐색 중단, 그때까지의 결과를 저장합니다: %r" % e)
    finally:  # 크롤이 죽어도 파싱 가능한 result.json은 남긴다 (파일이 없거나 깨지면 0점)
        pages = ctl["crawler"].results if "crawler" in ctl else []
        findings, items, seen = [], [], set()
        for pg in pages:
            for f in pg["result"] or []:
                key = (pg["url"], f["location"], f["technique"])  # 채점 단위. 같은 조합은 1건
                if key in seen:
                    continue
                seen.add(key)
                findings.append({"id": "f_%03d" % (len(findings) + 1), "url": pg["url"], "is_violation": True,
                                 "location": f["location"], "evidence_text": f["evidence_text"] or f["location"],
                                 "technique": f["technique"]})
                items.append(dict(f, **findings[-1], path=pg.get("path") or []))
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
    return meta, items


def run_all(url, log=print, ctl=None, minutes=20, on_done=None):
    """탐지(result.json) → on_done(meta, items) → 보고서(report.html, result.csv). 보고서 단계는 검출 시간 밖이다"""
    import report

    ctl = {} if ctl is None else ctl
    meta, items = scan(url, log, ctl, minutes)
    if on_done:
        on_done(meta, items)
    c = ctl.get("crawler")
    pages = [{"url": r["url"], "path": r.get("path") or []} for r in (c.results if c else [])]
    error = None
    if not pages:  # 한 쪽도 못 열었으면 "광고 없음"이 아니라 점검 실패
        error = "시작 주소를 열지 못했습니다. 주소가 맞는지, 사이트가 켜져 있는지, 이 PC에서 접속되는지 확인하세요."
        if c and c.errors:
            m = re.search(r"net::\w+|Timeout[^\\]*", c.errors[0][1])
            error += " (오류: %s)" % (m.group(0) if m else c.errors[0][1][:120])
        log("점검 실패: " + error)
    return report.make(meta, items, c.visited if c else 0, bool(c and c.deadline == 0), minutes, log, pages, error)


def ui_html():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ui.html"), encoding="utf-8") as f:
        return f.read()


class Api:
    """화면(JS)이 부르는 함수. JS는 state()를 0.5초마다 읽는다 (WebView2·예비 서버 공통)"""

    def __init__(self, smoke=False):
        self._window = None  # 밑줄: JS에 노출하지 않음
        self._smoke = smoke
        self._s, self._ctl, self._t0 = {"phase": "idle", "log": []}, {}, 0

    def start(self, url, minutes=20):
        if self._s["phase"] in ("running", "report"):
            return
        url = (url or "").strip()
        if "://" not in url:
            url = "http://" + url
        self._s, self._ctl, self._t0 = {"phase": "running", "log": [], "url": url}, {}, time.monotonic()
        threading.Thread(target=self._run, args=(url, max(1, min(30, int(minutes or 20)))), daemon=True).start()

    def stop(self):
        c = self._ctl.get("crawler")
        if c and self._s["phase"] == "running":
            c.stop()
            self._s["stopping"] = True

    def state(self):
        s, c = self._s, self._ctl.get("crawler")
        out = {k: v for k, v in s.items() if k != "log"}
        out["log"] = s["log"][-200:]
        if c:
            out.update(visited=c.visited, queue=len(c.heap), found=sum(len(r["result"] or []) for r in c.results))
        if s["phase"] == "running":
            out["elapsed"] = round(time.monotonic() - self._t0, 1)
        return out

    def open(self, what):
        import webbrowser
        name = {"report": "report.html", "csv": "result.csv", "json": "result.json", "folder": ""}[what]
        webbrowser.open(pathlib.Path(base_dir(), name).as_uri())

    def _run(self, url, minutes):
        def log(msg):
            print(msg, flush=True)
            self._s["log"].append(msg)

        try:
            # on_done이 "탐지 완료" 시점: 화면은 바로 완료를 표시하고 보고서는 뒤에서 만든다
            self._s["data"] = run_all(url, log, self._ctl, minutes, lambda meta, items: self._s.update(
                phase="report", elapsed=meta["elapsed_sec"], found=len(items)))
            self._s["phase"] = "ready"
        except Exception as e:
            log("오류: %r" % e)
            self._s["phase"] = "error"
        if self._smoke:
            self._window.destroy()


def serve(api):
    """WebView2 창을 못 띄울 때 예비 경로: 127.0.0.1 임의 포트 + 기본 브라우저. 같은 ui.html, API는 POST로"""
    import secrets
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    token = secrets.token_urlsafe(16)  # 다른 웹페이지가 로컬 API를 부르지 못하게 주소에 토큰

    class H(BaseHTTPRequestHandler):
        def reply(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/%s/" % token:
                return self.send_error(404)
            self.reply(ui_html().encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            name = self.path.rsplit("/", 1)[-1]
            if not self.path.startswith("/%s/api/" % token) or name not in ("start", "stop", "state", "open"):
                return self.send_error(404)
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"[]")
            self.reply(json.dumps(getattr(api, name)(*args), ensure_ascii=False).encode("utf-8"), "application/json")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    url = "http://127.0.0.1:%d/%s/" % (srv.server_port, token)
    print("UI: 예비 경로(기본 브라우저) %s" % url, flush=True)
    webbrowser.open(url)
    srv.serve_forever()


def hide_own_console():
    # exe를 더블클릭해서 콘솔이 이 프로세스 혼자 것이면 숨긴다 (cmd에서 실행했으면 그대로 둔다)
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        if k.GetConsoleProcessList((ctypes.c_uint * 2)(), 2) == 1:
            ctypes.windll.user32.ShowWindow(k.GetConsoleWindow(), 0)


def gui(smoke_url=None):
    api = Api(smoke=bool(smoke_url))
    try:
        import webview

        api._window = webview.create_window("adGuard 불법광고 탐지", html=ui_html(), js_api=api, width=1200, height=860,
                                            min_size=(720, 560))
        if smoke_url:  # 창이 뜨면 URL을 넣고 "탐지 시작"을 누른 것과 같게 한다
            api._window.events.loaded += lambda: api._window.evaluate_js(
                "function go(){document.getElementById('url').value=%s; start();}"
                "if (window.pywebview && pywebview.api && pywebview.api.start) go(); else window.addEventListener('pywebviewready', go);"
                % json.dumps(smoke_url))
        else:
            hide_own_console()
        webview.start(gui="edgechromium")  # IE 엔진으로 넘어가지 않게 WebView2만 허용
        print("UI: WebView2 창 종료", flush=True)
    except Exception as e:
        if smoke_url:
            raise
        print("UI: WebView2 실패(%r), 기본 브라우저로 엽니다" % e, flush=True)
        serve(api)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows에서 출력을 파일로 돌려도 한글이 깨지지 않게
    args = sys.argv[1:]
    if args[:1] == ["--smoke-gui"]:
        gui(args[1])
    elif args:
        run_all(args[0])
    else:
        gui()


if __name__ == "__main__":
    main()
