"""adGuard 진입점 (골격): URL을 받아 동봉 Chromium으로 열고 result.json을 쓴다."""
import json
import os
import sys
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


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(channel="msedge")  # 동봉 Chromium이 막히면 Edge로


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows에서 출력을 파일로 돌려도 한글이 깨지지 않게
    url = sys.argv[1] if len(sys.argv) > 1 else input("점검할 URL: ").strip()
    browsers = os.path.join(base_dir(), "browsers")
    if os.path.isdir(browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers  # PC에 같은 환경변수가 있어도 동봉본을 쓴다
    from playwright.sync_api import sync_playwright

    started, t0 = datetime.now(KST), time.monotonic()
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = page.title()
        browser.close()
    meta = {
        "topic": "TOPIC",
        "entry_url": url,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
        "elapsed_sec": round(time.monotonic() - t0, 2),
        "tool_version": VERSION,
    }
    out = os.path.join(base_dir(), "result.json")
    write_json(out, {"meta": meta, "findings": []})
    print("탐지 완료: %s -> %s" % (title, out))


if __name__ == "__main__":
    main()
