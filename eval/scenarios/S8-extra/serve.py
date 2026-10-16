#!/usr/bin/env python3
"""S8-extra 테스트 사이트 (추가 탐지 유형, todo/08): 127.0.0.1:8200 (site/)"""
import html
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

BASE = Path(__file__).resolve().parent
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".txt": "text/plain; charset=utf-8", ".xml": "application/xml"}


# 경로 → (제목 틀, robots 메타). /search: 제목 반사 + 색인 허용(위험), /search-safe: noindex(안전), /search-body: 본문만 반사(참고)
SEARCH = {"/search": ("'{q}' 검색 결과 | 테스트시", ""),
          "/search-safe": ("'{q}' 검색 결과 | 테스트시", '<meta name="robots" content="noindex">'),
          "/search-body": ("통합검색 | 테스트시", "")}


BOT = re.compile(r"googlebot|yeti|daum", re.I)


def cloak(p, ua, ref):
    """S-3 클로킹 재현: (상태, 위치 또는 None, 본문). 해당 없으면 None"""
    mobile, search = "Mobile" in ua, bool(re.search(r"google\.|naver\.", ref))
    page = lambda body, title="소식 | 테스트시": (200, None, '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>%s</title></head><body><main>%s</main></body></html>' % (title, body))
    if p == "/s3/news":  # 봇에게만 광고 문단 (Situs Toto·gov.br 사례)
        seo = '<div class="seo">카지노 사이트 추천 가입코드 TEST831 텔레그램 @test_promo_831</div>' if BOT.search(ua) else ""
        return page("<h1>구정 소식</h1><p>10월 구정 소식입니다.</p>" + seo)
    if p == "/s3/mobile":  # 검색 유입 모바일만 다른 도메인으로 (인도 2026·Sucuri 사례)
        if mobile and search:
            return 302, "http://localhost:8201/land.html", ""
        return page("<h1>행사 안내</h1><p>가을 행사 일정입니다.</p>")
    if p == "/s3/varies":  # 미끼: 매번 바뀌는 시각·토큰
        return page("<h1>오늘의 소식</h1><p>갱신 %s</p><input type=hidden name=csrf value=%s>" % (time.strftime("%H:%M:%S"), random.random()))
    if p == "/s3/waf":  # 미끼: 가짜 봇 차단(WAF)
        if BOT.search(ua):
            return 403, None, "<h1>Access denied</h1>"
        return page("<h1>민원 안내</h1><p>민원 접수 안내입니다.</p>")
    if p == "/s3/m-normal":  # 미끼: 모바일 전용 정상 화면, 검색 유입은 같은 사이트 모바일 주소로
        if mobile and search:
            return 302, "/s3/m-normal?m=1", ""
        return page("<h1>모바일 화면</h1><p>모바일 전용 안내입니다.</p>" if mobile else "<h1>안내</h1><p>데스크톱 안내입니다.</p>")
    if p == "/s3/bot-lite":  # 미끼: 봇에게는 배너를 뺀 가벼운 화면
        banner = "" if BOT.search(ua) else '<aside class="banner">구민 체육대회 참가 신청</aside>'
        return page("<h1>공지</h1><p>체육대회 안내입니다.</p>" + banner)
    return None


def make(root):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def search(self, p, q):
            title, robots = SEARCH[p]
            e = html.escape(q)
            body = ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><title>%s</title>%s</head><body><main>"
                    "<h1>통합검색</h1><p class=\"result\">'%s'에 대한 검색 결과가 없습니다.</p></main></body></html>"
                    % (title.replace("{q}", e), robots, e)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlsplit(self.path)
            p = u.path
            c = cloak(p, self.headers.get("User-Agent", ""), self.headers.get("Referer", ""))
            if c:
                st, loc, body = c
                body = body.encode("utf-8")
                self.send_response(st)
                if loc:
                    self.send_header("Location", loc)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if p in SEARCH:  # S-1 내부 검색: 검색어를 그대로 반사 (ISAP 재현)
                return self.search(p, parse_qs(u.query).get("q", [""])[0])
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
