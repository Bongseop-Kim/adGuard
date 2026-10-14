# -*- coding: utf-8 -*-
"""블라인드 평가 사이트 서버 (표준 라이브러리만). Windows/macOS 공용.
  python serve.py
  본 도메인:   http://127.0.0.1:8190/   (진입 URL)
  다른 도메인: http://localhost:8191/
"""
import gzip, io, os, re, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
EXT = os.path.join(HERE, "site_ext")
MAIN_PORT, EXT_PORT = 8190, 8191

TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".xml": "application/xml; charset=utf-8",
         ".txt": "text/plain; charset=utf-8", ".json": "application/json; charset=utf-8"}

def ctype(path):
    return TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")

def read(path):
    with open(path, "rb") as f:
        return f.read()

def resolve(path):
    """URL 경로 -> site/ 하위 파일 경로. 매칭 안 되면 None."""
    path = path.split(";", 1)[0]  # ;jsessionid 제거
    if path == "/" or path == "":
        return os.path.join(SITE, "index.html")
    # 게시글 상세 /board/<b>/view
    m = re.match(r"^/board/([a-z]+)/view$", path)
    if m:
        return ("VIEW", m.group(1))
    p = path.lstrip("/")
    full = os.path.normpath(os.path.join(SITE, p))
    if not full.startswith(SITE):
        return None
    if os.path.isfile(full):
        return full
    if os.path.isfile(full + ".html"):
        return full + ".html"
    return None

class Handler(BaseHTTPRequestHandler):
    server_version = "BlindEval/1.0"
    def log_message(self, *a):
        pass

    def _send(self, body, code=200, ctype_="text/html; charset=utf-8", gz=False, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = {"Content-Type": ctype_}
        if gz:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as g:
                g.write(body)
            body = buf.getvalue()
            headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(body))
        if extra:
            headers.update(extra)
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _query(self, qs):
        return urllib.parse.parse_qs(qs)

    def do_GET(self):
        self.route(method="GET")

    def do_HEAD(self):
        self.route(method="GET")

    def do_POST(self):
        self.route(method="POST")

    def route(self, method):
        parsed = urllib.parse.urlsplit(self.path)
        path, qs = parsed.path, parsed.query
        q = self._query(qs)
        site_root = SITE if self.server.server_port == MAIN_PORT else EXT

        # ---- 다른 도메인(8191): 정적만 ----
        if site_root == EXT:
            p = path.lstrip("/") or "promo.html"
            full = os.path.normpath(os.path.join(EXT, p))
            if full.startswith(EXT) and os.path.isfile(full):
                return self._send(read(full), ctype_=ctype(full))
            return self._send("not found", 404, "text/plain; charset=utf-8")

        # ---- 본 도메인(8190) ----
        path = path.split(";", 1)[0]

        # 리다이렉트
        if path == "/event":
            self.send_response(302)
            self.send_header("Location", "/board/notice/view?id=1210")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # 느린 응답
        if path == "/slow":
            time.sleep(2.0)
            return self._send(read(os.path.join(SITE, "slow.html")))

        # gzip 인코딩
        if path == "/gz":
            return self._send(read(os.path.join(SITE, "gz.html")), gz=True)

        # 내부 검색 반사
        if path == "/search":
            term = (q.get("q", [""])[0])
            tmpl = read(os.path.join(SITE, "search.html")).decode("utf-8")
            return self._send(tmpl.replace("{Q}", escape(term)))

        # 게시판 목록 페이지네이션
        m = re.match(r"^/board/(notice|free)$", path)
        if m:
            b = m.group(1)
            page = q.get("page", ["1"])[0]
            fn = f"{b}_p2.html" if page == "2" else f"{b}.html"
            fp = os.path.join(SITE, "board", fn)
            if os.path.isfile(fp):
                return self._send(read(fp))

        # 게시글 상세 (GET ?id / POST id)
        m = re.match(r"^/board/([a-z]+)/view$", path)
        if m:
            b = m.group(1)
            vid = q.get("id", [None])[0]
            if method == "POST":
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                vid = self._query(raw).get("id", [vid])[0]
            if vid:
                fp = os.path.join(SITE, "board", b, f"v{vid}.html")
                if os.path.isfile(fp):
                    return self._send(read(fp))
            return self._send("not found", 404, "text/plain; charset=utf-8")

        # 일반 정적
        r = resolve(path)
        if isinstance(r, str) and os.path.isfile(r):
            return self._send(read(r), ctype_=ctype(r))
        return self._send("not found", 404, "text/plain; charset=utf-8")


def escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def run():
    main = ThreadingHTTPServer(("127.0.0.1", MAIN_PORT), Handler)
    ext = ThreadingHTTPServer(("127.0.0.1", EXT_PORT), Handler)
    t = threading.Thread(target=ext.serve_forever, daemon=True)
    t.start()
    print(f"[blind] 본 도메인   http://127.0.0.1:{MAIN_PORT}/  (진입 URL)")
    print(f"[blind] 다른 도메인 http://localhost:{EXT_PORT}/")
    print("Ctrl+C 로 종료")
    try:
        main.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        main.shutdown()
        ext.shutdown()


if __name__ == "__main__":
    run()
