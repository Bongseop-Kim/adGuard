#!/usr/bin/env python3
"""S2-realistic 테스트 사이트 서버 (Python 3.10+ 표준 라이브러리만, Windows·macOS 공용).

    python serve.py

- 본 도메인:   http://127.0.0.1:8120/   (site/ 폴더)
- 다른 도메인: http://localhost:8121/   (site_ext/ 폴더)

정적 파일로 안 되는 동작만 코드로 처리한다:
- 전자정부형 공지: GET/POST /cop/bbs/selectArticleList.do, selectArticleDetail.do (onclick POST = 같은 파라미터 GET)
- 그누보드형: /bbs/board.php?bo_table=free&wr_id=N[&cpage=N], &page=N
- 경로 파라미터 ;jsessionid= 제거, JSESSIONID 쿠키 설정
- /minwon/apply → 302 리다이렉트
"""
import re, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

BASE = Path(__file__).resolve().parent
PORT = 8120
TYPES = {".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8",
         ".txt":"text/plain; charset=utf-8",".xml":"application/xml; charset=utf-8",".svg":"image/svg+xml",
         ".png":"image/png",".gif":"image/gif",".ico":"image/x-icon"}
SAFE = re.compile(r"^[A-Za-z0-9_.:/-]+$")
NOT_FOUND = ("<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>404</title></head>"
             "<body><h1>요청하신 페이지를 찾을 수 없습니다.</h1><p><a href=\"/\">홈으로</a></p></body></html>").encode("utf-8")
REDIRECTS = {"/minwon/apply": "/minwon/apply-notice.html"}


def logical(root, raw_path, params):
    """요청 경로+파라미터 → site/ 안의 실제 파일 경로(없으면 None). 특수 라우팅 우선."""
    path = raw_path
    path = re.sub(r";jsessionid=[^?/]*", "", path)   # 경로 파라미터 제거
    if path in ("", "/"):
        return root / "index.html"
    if path == "/cop/bbs/selectArticleList.do":
        p = params.get("pageIndex", "1")
        return _f(root / "_gen" / f"notice-list-{p}.html")
    if path == "/cop/bbs/selectArticleDetail.do":
        n = params.get("nttId", "")
        return _f(root / "_gen" / f"notice-view-{n}.html")
    if path == "/bbs/board.php":
        if params.get("bo_table") == "free":
            if "wr_id" in params:
                wr = params["wr_id"]; c = params.get("cpage")
                if c:
                    cand = root / "_gen" / f"free-view-{wr}-cpage-{c}.html"
                    if cand.is_file():
                        return cand
                return _f(root / "_gen" / f"free-view-{wr}.html")
            return _f(root / "_gen" / f"free-list-{params.get('page','1')}.html")
    if path == "/search.do":
        return _f(root / "_gen" / "search.html")
    # 일반 정적 파일
    rel = unquote(path).lstrip("/")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        return None
    if target.is_dir():
        return _f(target / "index.html")
    if target.is_file():
        return target
    return _f(target.with_name(target.name + ".html"))


def _f(p):
    return p if p.is_file() else None


def make_handler(root, is_main):
    class H(BaseHTTPRequestHandler):
        server_version = "EvalSite/2.0"
        def _params(self):
            parts = urlsplit(self.path)
            q = dict(parse_qsl(parts.query, keep_blank_values=True))
            if self.command == "POST":
                try:
                    ln = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    ln = 0
                if ln:
                    body = self.rfile.read(ln).decode("utf-8", "replace")
                    q.update(dict(parse_qsl(body, keep_blank_values=True)))
            return parts.path, q
        def _handle(self, head_only=False):
            raw, params = self._params()
            raw = unquote(raw) if "%" in raw else raw
            if is_main and raw in REDIRECTS:
                self.send_response(302)
                self.send_header("Location", REDIRECTS[raw])
                self.send_header("Set-Cookie", "JSESSIONID=A1B2C3D4E5F60718293A4B5C6D7E8F90; Path=/")
                self.send_header("Content-Length", "0")
                self.end_headers(); return
            path = logical(root, raw, params)
            if path is None:
                body, ctype, code = NOT_FOUND, TYPES[".html"], 404
            else:
                body = path.read_bytes(); ctype = TYPES.get(path.suffix.lower(), "application/octet-stream"); code = 200
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Set-Cookie", "JSESSIONID=A1B2C3D4E5F60718293A4B5C6D7E8F90; Path=/")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
        def do_GET(self): self._handle()
        def do_HEAD(self): self._handle(head_only=True)
        def do_POST(self): self._handle()
        def log_message(self, *a): pass
    return H


class Server6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def start(cls, host, port, root, is_main):
    srv = cls((host, port), make_handler(root, is_main))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    servers = [start(ThreadingHTTPServer, "127.0.0.1", PORT, (BASE / "site").resolve(), True)]
    print(f"본 도메인:   http://127.0.0.1:{PORT}/")
    ext = BASE / "site_ext"
    if ext.is_dir():
        servers.append(start(ThreadingHTTPServer, "127.0.0.1", PORT + 1, ext.resolve(), False))
        try:
            servers.append(start(Server6, "::1", PORT + 1, ext.resolve(), False))
        except OSError:
            pass
        print(f"다른 도메인: http://localhost:{PORT + 1}/")
    print("종료: Ctrl+C")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.shutdown()


