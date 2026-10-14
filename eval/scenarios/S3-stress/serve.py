# -*- coding: utf-8 -*-
"""S3-stress 테스트 사이트. `python serve.py`
본 도메인 http://127.0.0.1:8130/ , 다른 도메인 http://localhost:8131/ (표준 라이브러리만)
"""
import mimetypes
import os
import re
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from s3lib import calendar, egov, notice, old, pages  # noqa: E402
from s3lib.layout import EXT_PORT, HOST, PORT  # noqa: E402

ROUTES = {
    "/": pages.page_index,
    "/sitemap.html": pages.page_sitemap,
    "/board/notice/list": notice.page_list,
    "/board/notice/view": notice.page_view,
    egov.LIST: egov.page_list,
    egov.DETAIL: egov.page_detail,
    "/calendar/month": calendar.page_month,
    "/calendar/event": calendar.page_event,
    "/data/list": pages.page_data_list,
    "/data/report": pages.page_report,
    "/data/archive": pages.page_archive,
    "/stats/table": pages.page_stats,
    "/civil/faq": pages.page_faq,
    "/old/board/list.asp": old.page_list,
    "/old/board/view.asp": old.page_view,
}
REDIRECTS = {"/intro/vision.do": "/intro/vision"}
SESSION = re.compile(r";jsessionid=[^/?#]*", re.I)


class Handler(BaseHTTPRequestHandler):
    static_root = os.path.join(ROOT, "site")
    dynamic = True

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def route(self, qs):
        path = SESSION.sub("", urlsplit(self.path).path)
        if not self.dynamic:
            return self.static(path)
        if path in REDIRECTS:
            self.send_response(302)
            self.send_header("Location", REDIRECTS[path])
            self.end_headers()
            return
        if path == "/data/error":
            return self.send(500, "<h1>500 Internal Server Error</h1>".encode())
        m = re.fullmatch(r"/intro/(\w+)", path)
        m2 = re.fullmatch(r"/info/(\w+)\.do", path)
        if path in ROUTES:
            out = ROUTES[path](qs)
        elif m:
            out = pages.page_intro(m.group(1))
        elif m2:
            out = pages.page_info(m2.group(1))
        else:
            return self.static(path)
        if out is None:
            return self.send(404, "<h1>404 Not Found</h1>".encode())
        enc = old.ENCODING if path.startswith("/old/") else "utf-8"
        self.send(200, out.encode(enc), "text/html; charset=%s" % enc)

    def static(self, path):
        full = os.path.normpath(os.path.join(self.static_root, path.lstrip("/")))
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not full.startswith(self.static_root) or not os.path.isfile(full):
            return self.send(404, "<h1>404 Not Found</h1>".encode())
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_GET(self):
        self.route(parse_qs(urlsplit(self.path).query))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        qs = parse_qs(urlsplit(self.path).query)
        qs.update(parse_qs(self.rfile.read(n).decode("utf-8", "replace")))
        self.route(qs)


class ExtHandler(Handler):
    static_root = os.path.join(ROOT, "site_ext")
    dynamic = False


class V6Server(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def main():
    mimetypes.add_type("application/javascript", ".js")
    servers = [ThreadingHTTPServer((HOST, PORT), Handler), ThreadingHTTPServer(("127.0.0.1", EXT_PORT), ExtHandler)]
    try:  # localhost가 ::1로 풀리는 환경 대비
        servers.append(V6Server(("::1", EXT_PORT), ExtHandler))
    except OSError:
        pass
    for s in servers:
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print("S3-stress: http://%s:%d/  (ext http://localhost:%d/)  Ctrl+C로 종료" % (HOST, PORT, EXT_PORT))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
