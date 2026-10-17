"""디자인 미리보기: 마지막 점검 데이터(report.html)를 ui.html에 끼워 띄우고, ui.html을 저장하면 브라우저가 새로고침된다.

    python app/preview.py [report.html 경로]   → http://127.0.0.1:8765

다시 점검하지 않아도 된다. 펼쳐 둔 검출 줄과 스크롤 위치는 새로고침 뒤에도 유지된다. 개발용이라 exe에는 들어가지 않는다.
"""
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import main

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "data", "ui.html")
SLOT = '<script type="application/json" id="data">null</script>'

with open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "report.html"), encoding="utf-8") as f:
    BLOB = re.search(r'<script type="application/json" id="data">(.*?)</script>', f.read(), re.S).group(1)

# 저장 감지 → 새로고침. 펼친 줄 번호와 스크롤을 sessionStorage에 넣었다가 되살린다
RELOAD = """<script>
(() => {
  const ver = () => fetch('/v').then(r => r.text());
  const rows = () => [...document.querySelectorAll('button.gh')];
  try {
    const s = JSON.parse(sessionStorage.pv || 'null');
    if (s) { s.open.forEach(i => rows()[i] && rows()[i].click()); setTimeout(() => scrollTo(0, s.y), 50); }
  } catch (e) {}
  ver().then(v0 => setInterval(() => ver().then(v => {
    if (v === v0) return;
    sessionStorage.pv = JSON.stringify({ y: scrollY, open: rows().flatMap((r, i) => r.getAttribute('aria-expanded') === 'true' ? [i] : []) });
    location.reload();
  }), 500));
})();
</script></body>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/v":
            body = str(os.stat(UI).st_mtime_ns).encode()
        else:
            body = main.ui_html().replace(SLOT, SLOT.replace("null", BLOB), 1).replace("</body>", RELOAD, 1).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("미리보기: http://127.0.0.1:8765  (Ctrl+C로 종료)")
    webbrowser.open("http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
