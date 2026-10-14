#!/usr/bin/env python3
"""S1-baseline 테스트 사이트 서버 (Python 3.10+ 표준 라이브러리만 사용, Windows·macOS 공용).

    python serve.py

- 본 도메인:   http://127.0.0.1:8110/      (site/ 폴더)
- 다른 도메인: http://localhost:8111/      (site_ext/ 폴더, 있을 때만)

URL → 파일 규칙 (정적 파일로 안 되는 '쿼리별 상세 페이지'만 코드로 처리):
- /a/b            → site/a/b.html (확장자 없는 주소)
- /a/             → site/a/index.html
- /a/b?id=1024    → site/a/b/id-1024.html (쿼리 키를 정렬해 '키-값'을 '_'로 연결)
- 확장자가 있는 파일(css, js 등)은 쿼리를 무시하고 그대로 제공
"""
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

BASE = Path(__file__).resolve().parent
PORT = 8110
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}
SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


def resolve(root: Path, raw: str):
    parts = urlsplit(raw)
    rel = unquote(parts.path).lstrip("/")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        return None
    query = parse_qsl(parts.query, keep_blank_values=True)
    if query and not Path(rel).suffix:
        if not all(SAFE.match(k) and SAFE.match(v) for k, v in query):
            return None
        cand = target / ("_".join(f"{k}-{v}" for k, v in sorted(query)) + ".html")
        return cand if cand.is_file() else None
    if target.is_dir():
        cand = target / "index.html"
        return cand if cand.is_file() else None
    if target.is_file():
        return target
    cand = target.with_name(target.name + ".html")
    return cand if cand.is_file() else None


NOT_FOUND = ("<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>404</title></head>"
             "<body><h1>요청하신 페이지를 찾을 수 없습니다.</h1><p><a href=\"/\">홈으로</a></p></body></html>").encode("utf-8")


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EvalSite/1.0"

        def _send(self, head_only=False):
            path = resolve(root, self.path)
            if path is None:
                body, ctype, code = NOT_FOUND, TYPES[".html"], 404
            else:
                body = path.read_bytes()
                ctype = TYPES.get(path.suffix.lower(), "application/octet-stream")
                code = 200
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

        def do_GET(self):
            self._send()

        def do_HEAD(self):
            self._send(head_only=True)

        def log_message(self, fmt, *args):
            sys.stderr.write("[%s] %s\n" % (self.server.server_address[1], fmt % args))

    return Handler


class Server6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def start(server_cls, host, port, root):
    srv = server_cls((host, port), make_handler(root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    servers = [start(ThreadingHTTPServer, "127.0.0.1", PORT, (BASE / "site").resolve())]
    print(f"본 도메인:   http://127.0.0.1:{PORT}/")
    ext = BASE / "site_ext"
    if ext.is_dir():
        servers.append(start(ThreadingHTTPServer, "127.0.0.1", PORT + 1, ext.resolve()))
        try:  # localhost가 ::1로 풀리는 환경 대비
            servers.append(start(Server6, "::1", PORT + 1, ext.resolve()))
        except OSError:
            pass
        print(f"다른 도메인: http://localhost:{PORT + 1}/")
    print("종료: Ctrl+C")
    try:
        while True:  # Windows에서도 Ctrl+C가 먹도록 짧게 깨어남
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.shutdown()


if __name__ == "__main__":
    main()
