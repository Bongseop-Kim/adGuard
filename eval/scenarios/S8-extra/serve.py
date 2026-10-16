#!/usr/bin/env python3
"""S8-extra 테스트 사이트 (추가 탐지 유형, todo/08): 127.0.0.1:8200 (site/)"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

BASE = Path(__file__).resolve().parent
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".txt": "text/plain; charset=utf-8", ".xml": "application/xml"}


def make(root):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urlsplit(self.path)
            p = u.path
            if p == "/board/view":
                p = "/board/view-%s.html" % parse_qs(u.query).get("id", ["0"])[0]
            elif p.endswith("/"):
                p += "index.html"
            elif "." not in p.rsplit("/", 1)[-1]:
                p += ".html"
            f = (root / p.lstrip("/")).resolve()
            if not str(f).startswith(str(root.resolve())) or not f.is_file():
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>404</h1>")
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(f.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return H


if __name__ == "__main__":
    a = ThreadingHTTPServer(("127.0.0.1", 8200), make(BASE / "site"))
    b = ThreadingHTTPServer(("localhost", 8201), make(BASE / "site_ext"))
    threading.Thread(target=b.serve_forever, daemon=True).start()
    a.serve_forever()
