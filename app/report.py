"""결과 화면·보고서 데이터 (todo/06). result.json을 쓴 뒤에 돌아서 검출 시간에 들어가지 않는다.

    data = make(meta, items, visited, stopped, minutes, log)   # report.html·result.csv도 쓴다

- 묶음: 지문 = 기법 + 원문(공백 정리). 같은 지문의 위치별 검출이 한 행 (research/10 §1-2)
- 원인 유형(R14): 같은 지문이 2개 이상 페이지의 같은 위치에 있으면 해킹 삽입 의심, 아니면 게시물형
- 위험도(R3): 심각 = 해킹 삽입 의심, 위험 = 숨김(OFFSCREEN·TRANSPARENT), 참고 = 보이는 변형 광고(HOMOGLYPH·JAMO)
- 최초 발견일: exe 폴더 history.json (지문 → 처음 본 시각). R11 이력 비교·R18 예외 목록도 이 지문으로 확장한다
- 숨김 드러내기(R6): 페이지를 다시 열어 부모 영역을 찍고, 숨김을 푼 CSS를 넣어 한 번 더 찍는다
"""
import asyncio
import base64
import csv
import hashlib
import json
import os
import re
import time
import unicodedata
from datetime import datetime

import main

TECH = {
    "HOMOGLYPH": "유사 문자 치환",
    "JAMO": "자모 분리",
    "TRANSPARENT": "투명·배경색 숨김",
    "OFFSCREEN": "화면 밖·크기 0 숨김",
}
HIDDEN = {"OFFSCREEN", "TRANSPARENT"}
RISK = ["심각", "위험", "참고"]
HACK, POST = "해킹 삽입 의심", "게시물형"
SHOT_MAX, SHOT_SEC = 100, 240  # ponytail: 캡처 상한. 넘는 묶음은 "캡처 생략"으로 표시

REVEAL_JS = r"""
(e, [step, hidden]) => {
  const up = n => n.parentElement || (n.parentNode && n.parentNode.host) || null;
  if (step === 'mark') {
    // 숨김 요소에서 위로 올라가며 사람이 보는 크기의 부모 영역을 찾는다. 그 사이 요소는 드러낼 대상
    const mark = n => { n.setAttribute('data-adg-up', ''); if (getComputedStyle(n).display === 'none') n.setAttribute('data-adg-show', ''); };
    // 보이는 변형 광고(HOMOGLYPH·JAMO)는 테두리만 두르고 부모는 건드리지 않는다
    if (hidden) mark(e); e.setAttribute('data-adg', '');
    let n = up(e);
    for (; n && n !== document.body && n !== document.documentElement; n = up(n)) {
      const r = n.getBoundingClientRect(), s = getComputedStyle(n);
      if (r.width >= 240 && r.height >= 80 && r.right > 0 && r.bottom + scrollY > 0 && s.display !== 'none' &&
          s.visibility === 'visible' && parseFloat(s.opacity) > 0.5) break;
      if (hidden) mark(n);
    }
    n = n || document.body;
    n.setAttribute('data-adg-box', '');
    n.scrollIntoView({ block: 'start' });
    return;
  }
  const css = `
[data-adg-show]{display:block!important}
[data-adg-up]{visibility:visible!important;opacity:1!important;position:static!important;transform:none!important;
  clip:auto!important;clip-path:none!important;filter:none!important;overflow:visible!important;text-indent:0!important;
  width:auto!important;height:auto!important;max-width:none!important;max-height:none!important;margin:0!important}
[data-adg],[data-adg] *{color:#c00!important;-webkit-text-fill-color:#c00!important;font-size:15px!important;
  line-height:1.5!important;opacity:1!important;visibility:visible!important}
[data-adg]{background:#fff6bf!important;outline:3px solid #e00!important;outline-offset:2px!important}`;
  const roots = new Set();
  for (let n = e; n; n = up(n)) roots.add(n.getRootNode());
  for (const r of roots) { const s = document.createElement('style'); s.textContent = css; (r.head || r).append(s); }
}
"""

# R7 조치 안내: 유형별 고정 문구
GUIDE = {
    POST: ["게시물·댓글을 삭제하거나 블라인드 처리하고 삭제게시물 기록대장에 남깁니다 (게시일, 게시자, 제목, 내용, 삭제 사유, 담당자, 확인자).",
           "같은 작성자·연락처의 다른 글이 있는지 게시판 관리자 화면에서 함께 확인합니다.",
           "자동 등록 방지(CAPTCHA), 금칙어에 변형 표기(자모 분리·유사 문자)를 추가합니다."],
    HACK: ["여러 페이지 같은 위치에 같은 문구가 있으면 게시물이 아니라 공통 템플릿·소스가 변조됐을 가능성이 큽니다. 게시물 삭제만으로는 다시 나타납니다.",
           "KISA 인터넷침해대응센터(국번 없이 118, boho.or.kr)에 침해사고를 신고합니다.",
           "웹셸 탐지 도구(KISA 휘슬 등)로 서버를 점검하고, 변조된 템플릿·공통 파일을 백업본으로 복구한 뒤 관리자 계정 비밀번호를 바꿉니다."],
    "검색엔진 흔적": ["삭제한 뒤에도 검색 결과에 광고 문구가 남을 수 있습니다.",
                 "Google Search Console '삭제' 도구, 네이버 서치어드바이저 '웹페이지 수집 요청/검색 제외'로 흔적을 지웁니다."],
    "ISAP": ["사이트 내부 검색 결과 페이지가 검색엔진에 수집되지 않게 검색 결과 페이지에 noindex를 넣고 robots.txt로 차단합니다.",
             "검색어를 GET 주소와 페이지 제목에 그대로 반사하지 않게 합니다 (결과 0건 페이지는 noindex)."],
}


def fingerprint(technique, text):
    return hashlib.sha1((technique + "\n" + " ".join(text.split())).encode()).hexdigest()[:10]


def odd_chars(raw):
    """원문에서 설명이 필요한 글자: 완성형 한글·ASCII가 아닌 것 (키릴 а, 전각 Ｃ, 자모 ㅋ, 보이지 않는 글자 등)"""
    out = {}
    for c in raw:
        if not ("가" <= c <= "힣" or " " <= c <= "~" or c in "\n\t") and c not in out:
            out[c] = ["U+%04X" % ord(c), unicodedata.name(c, "이름 없는 글자")]
        if len(out) >= 40:
            break
    return [[c] + v for c, v in out.items()]


def group(items, history, now):
    by = {}
    for it in items:
        by.setdefault(fingerprint(it["technique"], it["evidence_text"]), []).append(it)
    groups = []
    for fp, its in by.items():
        f = next((x for x in its if "norm" in x), its[0])  # 근거가 있는 것(숨김 상위 요소보다 실제 글자 요소)
        urls = {x["url"] for x in its}
        locs = {}
        for x in its:
            locs.setdefault(x["location"], set()).add(x["url"])
        hack = len(urls) >= 2 and max(len(u) for u in locs.values()) >= 2
        tech = f["technique"]
        risk = "심각" if hack else "위험" if tech in HIDDEN else "참고"
        kw = f.get("kw") or []
        summary = "[%s] %s · [광고 신호] %s · [영향] 페이지 %d개" % (
            TECH[tech], f.get("reason") or "-", ", ".join(kw[:6]) or "-", len(urls))
        if hack:
            summary += " · 여러 페이지 같은 위치 → 해킹 삽입 의심"
        groups.append({
            "fp": fp, "technique": tech, "tech_label": TECH[tech], "risk": risk, "cause": HACK if hack else POST,
            "first_seen": history.setdefault(fp, now), "summary": summary, "evidence_text": f["evidence_text"],
            "norm": f.get("norm", ""), "kw": kw, "reason": f.get("reason", ""), "chars": odd_chars(f["evidence_text"]),
            "html": f.get("html", ""), "style": f.get("style", {}),
            "items": [{"id": x["id"], "url": x["url"], "location": x["location"]} for x in its],
        })
    # 정렬: 위험도 → 영향 페이지 수 → 최초 발견일(신규 먼저) (research/10 §1-6)
    groups.sort(key=lambda g: g["first_seen"], reverse=True)
    groups.sort(key=lambda g: (RISK.index(g["risk"]), -len({i["url"] for i in g["items"]})))
    return groups


async def frame_scope(page, location):
    """location(`a > b >>> c`) → (프레임, 선택자). iframe 구간은 src 속성이 상대 주소일 수 있어 프레임 URL로 먼저 찾고
    (srcdoc·src 없는 iframe은 요소의 content_frame으로), 그 밖의 >>>는 Shadow 호스트라 CSS로 그대로 뚫는다"""
    *outer, last = location.split(" >>> ")
    frame, css = page.main_frame, ""
    for seg in outer:
        css = (css + " " + seg).strip()
        if not seg.rsplit(" > ", 1)[-1].startswith("iframe"):
            continue
        m = re.search(r'iframe\[src="((?:[^"\\]|\\.)*)"\]$', seg)
        src = re.sub(r"\\(.)", r"\1", m.group(1)) if m else None  # detect.js q()의 역슬래시 이스케이프를 푼다
        hit = [f for f in frame.child_frames if src and f.url == src]
        frame = hit[0] if hit else await (await frame.locator(css).first.element_handle(timeout=3000)).content_frame()
        css = ""
    return frame, (css + " " + last).strip()


async def shoot(page, url, location, hidden):
    await page.goto(url, wait_until="load", timeout=15000)
    await asyncio.sleep(0.8)  # 로드 뒤 JS가 넣는 광고
    scope, css = await frame_scope(page, location)
    loc, box = scope.locator(css).first, scope.locator("[data-adg-box]").first
    await loc.evaluate(REVEAL_JS, ["mark", hidden], timeout=4000)
    mask = [page.locator('[class*="writer"], [class*="author"], [class*="nick"]')]  # 작성자 칸은 가린다 (보고서가 외부로 나가므로)

    async def snap():
        b = await box.bounding_box(timeout=3000)
        if not b or b["width"] < 1 or b["height"] < 1:
            raise RuntimeError("부모 영역 크기 0")
        y, e = b["y"], await loc.bounding_box(timeout=1000)
        if b["height"] > 420 and e and b["y"] <= e["y"] <= b["y"] + b["height"]:  # 긴 표·본문: 광고 줄이 가운데 오게
            y = min(max(b["y"], e["y"] + e["height"] / 2 - 210), b["y"] + b["height"] - 420)
        clip = {"x": max(0, b["x"]), "y": max(0, y), "width": min(b["width"], 1000), "height": min(b["height"], 420)}
        img = await page.screenshot(clip=clip, type="jpeg", quality=60, animations="disabled", caret="hide",
                                    mask=mask, timeout=5000)
        return "data:image/jpeg;base64," + base64.b64encode(img).decode()

    before = await snap()
    await loc.evaluate(REVEAL_JS, ["reveal", hidden], timeout=3000)
    await page.wait_for_timeout(100)
    return {"before": before, "after": await snap()}


async def capture(groups, log):
    from playwright.async_api import async_playwright
    from crawler import INIT, launch

    t0 = time.monotonic()
    async with async_playwright() as p:
        browser, _ = await launch(p)
        ctx = await browser.new_context(ignore_https_errors=True, service_workers="block",
                                        viewport={"width": 1280, "height": 720}, locale="ko-KR")
        await ctx.add_init_script(INIT)
        page = await ctx.new_page()
        for n, g in enumerate(groups):
            if n >= SHOT_MAX or time.monotonic() - t0 > SHOT_SEC:
                g["shot"] = {"error": "캡처 생략(보고서 크기·시간 상한)"}
                continue
            it = g["items"][0]
            for _ in (0, 1):  # 실패하면 새 탭으로 한 번 더 (프레임 분리 등 일시적인 실패)
                try:
                    g["shot"] = await asyncio.wait_for(shoot(page, it["url"], it["location"], g["technique"] in HIDDEN), 25)
                    break
                except Exception as e:
                    g["shot"] = {"error": "캡처 실패: 페이지를 다시 열었을 때 요소를 찾지 못함 (%s)" % type(e).__name__}
                    await page.close()
                    page = await ctx.new_page()
            log("숨김 드러내기 캡처 %d/%d" % (n + 1, len(groups)))
        await browser.close()


def html_report(data):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ui.html"), encoding="utf-8") as f:
        page = f.read()
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")  # 원문 속 </script>가 태그를 닫지 못하게
    return page.replace('<script type="application/json" id="data">null</script>',
                        '<script type="application/json" id="data">%s</script>' % blob, 1)


def write_csv(path, groups):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel에서 더블클릭으로 한글이 열린다
        w = csv.writer(f)
        w.writerow(["id", "위험도", "원인 유형", "기법", "기법 코드", "URL", "위치(CSS 선택자)", "원문", "근거", "지문", "최초 발견"])
        for g in groups:
            for it in g["items"]:
                w.writerow([it["id"], g["risk"], g["cause"], g["tech_label"], g["technique"], it["url"], it["location"],
                            g["evidence_text"], g["reason"], g["fp"], g["first_seen"]])


def make(meta, items, visited, stopped, minutes, log=print):
    base = main.base_dir()
    hist_path = os.path.join(base, "history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, ValueError):
        history = {}
    groups = group(items, history, meta["started_at"])
    main.write_json(hist_path, history)
    if groups:
        try:
            asyncio.run(capture(groups, log))
        except Exception as e:
            log("캡처 단계 오류(보고서는 캡처 없이 만듦): %r" % e)
    data = {
        "meta": dict(meta, visited=visited, stopped=stopped, minutes=minutes, findings=len(items),
                     report_at=datetime.now(main.KST).isoformat(timespec="seconds")),
        "groups": groups,
        "guide": GUIDE,
        # R20: AI 판정은 todo/08에서 연결. 켜지면 rows에 [항목, 값] (후보·규칙 확정·전송·캐시·호출·거부·토큰·비용·바뀐 판정)
        "ai": {"enabled": False, "reason": "이 버전은 규칙만으로 판정합니다. 외부로 보낸 데이터 0건, 사용 토큰 0, 비용 0원."},
    }
    with open(os.path.join(base, "report.html"), "w", encoding="utf-8") as f:
        f.write(html_report(data))
    write_csv(os.path.join(base, "result.csv"), groups)
    log("보고서 저장: report.html, result.csv")
    return data


if __name__ == "__main__":  # 자체 확인: python app/report.py
    it = lambda i, u, loc, t, ev: {"id": i, "url": u, "location": loc, "technique": t, "evidence_text": ev}
    gs = group([it("f_1", "a", "div > span", "OFFSCREEN", "카지노 @x"), it("f_2", "b", "div > span", "OFFSCREEN", "카지노  @x"),
                it("f_3", "a", "td", "JAMO", "ㅋㅏㅈㅣㄴㅗ"), it("f_4", "a", "p", "TRANSPARENT", "토토"),
                it("f_5", "b", "li", "TRANSPARENT", "토토")], {}, "t")
    assert [(g["risk"], g["cause"], len(g["items"])) for g in gs] == [("심각", HACK, 2), ("위험", POST, 2), ("참고", POST, 1)], gs
    assert odd_chars("саsino ㅋ가") == [["с", "U+0441", "CYRILLIC SMALL LETTER ES"], ["а", "U+0430", "CYRILLIC SMALL LETTER A"],
                                       ["ㅋ", "U+314B", "HANGUL LETTER KHIEUKH"]]
    page = html_report({"x": "</script><script>alert(1)</script>"})
    assert "</script><script>alert" not in page and json.loads(page.split('id="data">')[1].split("</script>")[0])["x"].startswith("</")
    print("통과")
