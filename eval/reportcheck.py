"""report.html을 브라우저로 열어 스크립트 오류가 없고 결과 화면이 그려졌는지 본다. 사용: python eval/reportcheck.py app/report.html"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = b.new_page(), []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(pathlib.Path(sys.argv[1]).resolve().as_uri())
    pg.wait_for_timeout(500)
    drawn = pg.evaluate("!document.getElementById('result').hidden && document.getElementById('result').children.length > 0")
    b.close()
if errs or not drawn:
    sys.exit("report.html 오류: %s" % (errs or "결과 화면이 비어 있음"))
print("report.html OK")
