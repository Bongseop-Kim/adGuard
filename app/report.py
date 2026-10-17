"""결과 화면·보고서 데이터 (todo/06). result.json을 쓴 뒤에 돌아서 검출 시간에 들어가지 않는다.

    data = make(meta, items, visited, stopped, minutes, log)   # report.html·result.csv도 쓴다

- 묶음: 지문 = 기법 + 원문(공백 정리). 같은 지문의 위치별 검출이 한 행 (research/10 §1-2)
- 원인 유형(R14): 게시판 영역 밖에서 같은 지문이 2개 이상 페이지의 같은 위치에 숨겨져 있으면 해킹 삽입 의심, 아니면 게시물형
- 위험도(R3): 심각 = 해킹 삽입 의심, 위험 = 숨김(OFFSCREEN·TRANSPARENT), 참고 = 보이는 변형 광고(HOMOGLYPH·JAMO)
- 최초 발견일: exe 폴더 history.json (지문 → 처음 본 시각). R11 이력 비교·R18 예외 목록도 이 지문으로 확장한다
- 숨김 드러내기(R6): 페이지를 다시 열어 광고 둘레 PAD_X·PAD_Y px을 원래 해상도로 찍고, 숨김을 푼 CSS를 넣어 한 번 더 찍는다
- 시각 자료: 위 전·후 캡처 + 광고 위치 좌표, 발견 경로, 사이트 지도
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
import urllib.parse
from datetime import datetime

import ai
import main

TECH = {
    "HOMOGLYPH": "유사 문자 치환",
    "JAMO": "자모 분리",
    "TRANSPARENT": "투명·배경색 숨김",
    "OFFSCREEN": "화면 밖·크기 0 숨김",
}
EXTRA = {"INVISIBLE_CHAR": "추가 유형: 보이지 않는 문자 삽입", "VISIBLE_AD": "추가 유형: 그대로 보이는 광고",
         "HTML_COMMENT_AD": "추가 유형: HTML 주석 속 광고", "ATTR_META_AD": "추가 유형: 제목·메타·속성 속 광고",
         "VISUAL_REORDER": "추가 유형: 화면 순서 뒤집기",
         "ISAP_SEARCH_REFLECTION": "추가 유형: 내부 검색 반사 광고",
         "CLOAKING": "추가 유형: 검색봇 클로킹"}  # result_extra.json의 extra_finding
HIDDEN = {"OFFSCREEN", "TRANSPARENT"}
RISK = ["심각", "위험", "참고"]
HACK, POST = "해킹 삽입 의심", "게시물형"
SHOT_MAX, SHOT_SEC = 100, 240  # ponytail: 캡처 상한. 넘는 묶음은 "캡처 생략"으로 표시
PAD_X, PAD_Y = 240, 160  # 광고 둘레로 찍는 범위(CSS px). 화면(ui.html shotFig)이 보여 주는 범위와 같다

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
    "내부 검색 결과 악용": ["사이트 내부 검색 결과 페이지가 검색엔진에 수집되지 않게 검색 결과 페이지에 noindex를 넣고 robots.txt로 차단합니다.",
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


# 게시판 글·댓글이 들어가는 영역 (그누보드·XE·라이믹스·전자정부 등): 여러 쪽에 반복돼도 게시물이다 (research/13 §2)
USER_AREA = re.compile(r"bo_v|cmt|comment|reply|xe_content|rd_body|view_?con|board_?view|bbs_?view|article|answer|"
                       r"btn_(?:prv|next)|prev|next|latest|lt_", re.I)
HREF = re.compile(r"""^<a\s[^>]*href\s*=\s*["']?([^"'\s>]+)""", re.I)


def user_area(location):
    return bool(USER_AREA.search(location))


def own_link(f):
    """같은 사이트 글로 가는 링크(이전·다음 글, 최근 글 위젯, 목록 제목)면 그 글의 제목이 반복된 것이다"""
    m = HREF.search(f.get("html") or "")
    if not m or m.group(1).lower().startswith(("javascript:", "#", "mailto:")):
        return False
    host = urllib.parse.urlsplit(urllib.parse.urljoin(f["url"], m.group(1))).hostname or ""
    return host.removeprefix("www.") == (urllib.parse.urlsplit(f["url"]).hostname or "").removeprefix("www.")


def group(items, history, now):
    """원인 유형(R14): 해킹 삽입 의심 = 게시판 영역 밖에서 같은 문구가 2개 이상 페이지의 같은 위치에 '숨겨져' 반복되고,
    같은 사이트 글로 가는 링크가 아닐 때. 보이는 변형·글 제목·이웃 글 링크는 템플릿 반복일 뿐이다 (research/13 §2)"""
    hidden = {(x["url"], x["location"]) for x in items if x["technique"] in HIDDEN}
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
        rep = [loc for loc, u in locs.items() if len(u) >= 2]  # 2개 이상 페이지에 같은 위치로 반복
        hack = any(not user_area(loc) and all((u, loc) in hidden for u in locs[loc]) for loc in rep) and not own_link(f)
        hack = hack or f.get("extra_finding") == "CLOAKING"  # UA·Referer 분기는 서버 설정·템플릿 변조라야 가능하다
        tech = f["technique"]
        # 그대로 보이는 광고는 시민이 바로 보는 게시물, 제목·메타 속 광고는 검색 결과에 뜨는 글이라 숨김과 같은 '위험'
        risk = "심각" if hack else "위험" if tech in HIDDEN or f.get("extra_finding") in ("VISIBLE_AD", "ATTR_META_AD", "VISUAL_REORDER", "ISAP_SEARCH_REFLECTION", "CLOAKING") else "참고"
        kw = f.get("kw") or []
        groups.append({
            "fp": fp, "technique": tech, "tech_label": TECH.get(tech) or EXTRA.get(f.get("extra_finding"), "추가 유형"), "risk": risk, "cause": HACK if hack else POST,
            "first_seen": history.setdefault(fp, now), "evidence_text": f["evidence_text"],
            "norm": f.get("norm", ""), "kw": kw, "reason": f.get("reason", ""), "chars": odd_chars(f["evidence_text"]),
            "html": f.get("html", ""), "style": f.get("style", {}),
            "items": [{"id": x["id"], "url": x["url"], "location": x["location"], "path": x.get("path") or [],
                       "mobile": x.get("mobile", False)}
                      for x in its],
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


MASK = '[class*="writer"], [class*="author"], [class*="nick"]'  # 작성자 칸은 가린다 (보고서가 외부로 나가므로)


async def open_marked(page, url, location, hidden):
    await page.goto(url, wait_until="load", timeout=15000)
    await asyncio.sleep(0.8)  # 로드 뒤 JS가 넣는 광고
    scope, css = await frame_scope(page, location)
    loc, box = scope.locator(css).first, scope.locator("[data-adg-box]").first
    await loc.evaluate(REVEAL_JS, ["mark", hidden], timeout=4000)
    return loc, box


async def shoot(page, url, location, hidden):
    """광고 둘레 PAD_X·PAD_Y px을 원래 해상도로 숨김 해제 전·후 두 장. pos는 캡처 안 좌표(CSS px)"""
    loc, box = await open_marked(page, url, location, hidden)
    # 숨김 광고는 크기가 없어 부모 영역, 보이는 광고는 요소 자체
    r = (not hidden and await loc.bounding_box(timeout=1000)) or await box.bounding_box(timeout=3000)
    if not r or r["width"] < 1 or r["height"] < 1:
        raise RuntimeError("부모 영역 크기 0")
    sx, sy, dw, dh = await page.evaluate(
        "() => [scrollX, scrollY, document.documentElement.scrollWidth, document.documentElement.scrollHeight]")
    ax, ay = r["x"] + sx, r["y"] + sy
    x0, y0 = max(0, ax - PAD_X), max(0, ay - PAD_Y)
    clip = {"x": x0, "y": y0, "width": max(1, min(dw, ax + r["width"] + PAD_X) - x0),
            "height": max(1, min(dh, ay + r["height"] + PAD_Y) - y0)}

    async def snap():
        img = await page.screenshot(full_page=True, clip=clip, type="jpeg", quality=80, animations="disabled",
                                    caret="hide", mask=[page.locator(MASK)], timeout=10000)
        return "data:image/jpeg;base64," + base64.b64encode(img).decode()

    before = await snap()
    await loc.evaluate(REVEAL_JS, ["reveal", hidden], timeout=3000)
    await page.wait_for_timeout(100)
    return {"before": before, "after": await snap(), "url": url, "w": clip["width"], "h": clip["height"],
            "pos": {"x": ax - x0, "y": ay - y0, "w": r["width"], "h": r["height"]}}


async def capture(groups, log, ctl=None):
    """묶음별 숨김 해제 전·후 캡처를 g["shot"]에 넣는다"""
    from playwright.async_api import async_playwright
    from crawler import INIT, launch

    t0 = time.monotonic()
    ctl = {} if ctl is None else ctl
    ctl["shot"] = [0, min(len(groups), SHOT_MAX)]  # 화면 진행 막대용 [끝난 수, 전체]
    async with async_playwright() as p:
        browser, _ = await launch(p)
        tabs = {}  # 모바일 전용 페이지는 크롤 때처럼 모바일 화면으로 연다

        async def tab(mobile):
            if mobile not in tabs:
                view = p.devices["iPhone 13"] if mobile else {"viewport": {"width": 1280, "height": 720}}
                c = await browser.new_context(ignore_https_errors=True, service_workers="block", locale="ko-KR", **view)
                await c.add_init_script(INIT)
                tabs[mobile] = (c, await c.new_page())
            return tabs[mobile]

        for n, g in enumerate(groups):
            # 시간 상한(ctl["end"]) 전에 끝나게: 캡처 1건은 재시도까지 최대 50초
            if n >= SHOT_MAX or time.monotonic() - t0 > SHOT_SEC or time.monotonic() > ctl.get("end", 1e18) - 55:
                g["shot"] = {"error": "캡처 생략(보고서 크기·시간 상한)"}
                continue
            it = g["items"][0]
            ctx, page = await tab(it.get("mobile", False))
            for _ in (0, 1):  # 실패하면 새 탭으로 한 번 더 (프레임 분리 등 일시적인 실패)
                try:
                    g["shot"] = await asyncio.wait_for(shoot(page, it["url"], it["location"], g["technique"] in HIDDEN), 25)
                    break
                except Exception as e:
                    g["shot"] = {"error": "캡처 실패: 페이지를 다시 열었을 때 요소를 찾지 못함 (%s)" % type(e).__name__}
                    await page.close()
                    page = await ctx.new_page()
                    tabs[it.get("mobile", False)] = (ctx, page)
            log("증거 캡처 %d/%d" % (n + 1, len(groups)))
            ctl["shot"][0] = min(n + 1, ctl["shot"][1])

        await browser.close()


def html_report(data):
    page = main.ui_html()
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")  # 원문 속 </script>가 태그를 닫지 못하게
    return page.replace('<script type="application/json" id="data">null</script>',
                        '<script type="application/json" id="data">%s</script>' % blob, 1)


def save_record(base, data):
    """점검 기록: records/<시작 시각>.html(그때 보고서 사본) + records/index.json(목록 요약, 최신이 앞)"""
    d = os.path.join(base, "records")
    os.makedirs(d, exist_ok=True)
    m = data["meta"]
    name = re.sub(r"\D", "", m["started_at"])[:14] + ".html"
    # 사본에는 캡처를 넣지 않는다: 기록이 쌓여도 디스크를 덜 쓴다 (P9). 캡처는 그때의 report.html에만
    lite = dict(data, groups=[dict(g, shot={"error": "점검 기록 사본에는 캡처를 넣지 않습니다"}) for g in data["groups"]])
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(html_report(lite))
    idx = [e for e in records(base) if e["file"] != name]
    idx.insert(0, {"file": name, "entry_url": m["entry_url"], "finished_at": m["finished_at"], "elapsed_sec": m["elapsed_sec"],
                   "visited": m["visited"], "findings": m["findings"], "kinds": len(data["groups"]),
                   "risk": {r: sum(g["risk"] == r for g in data["groups"]) for r in RISK},
                   "stopped": m["stopped"], "error": m["error"]})
    main.write_json(os.path.join(d, "index.json"), idx)


def records(base):
    try:
        with open(os.path.join(base, "records", "index.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def read_record(base, name):
    """기록 보고서에 내장된 결과 JSON. 목록에 있는 파일만 연다 (경로 조작 방지)"""
    if name not in {e["file"] for e in records(base)}:
        return None
    with open(os.path.join(base, "records", name), encoding="utf-8") as f:
        return json.loads(f.read().split('<script type="application/json" id="data">', 1)[1].split("</script>", 1)[0])


def write_csv(path, groups):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel에서 더블클릭으로 한글이 열린다
        w = csv.writer(f)
        w.writerow(["id", "위험도", "원인 유형", "기법", "기법 코드", "URL", "위치(CSS 선택자)", "원문", "근거", "지문", "최초 발견",
                    "지난 점검 대비", "조치 상태", "조치 메모"])
        for g in groups:
            st = g.get("status") or {}
            for it in g["items"]:
                w.writerow([it["id"], g["risk"], g["cause"], g["tech_label"], g["technique"], it["url"], it["location"],
                            g["evidence_text"], g["reason"], g["fp"], g["first_seen"], g.get("change", ""),
                            st.get("status", "미조치"), st.get("memo", "")])


# ---------- 조치 상태와 재점검 비교 (research/14 §6) ----------
STATUSES = ["미조치", "조치 요청", "조치 완료", "오탐(예외)"]


def load_status(base):
    """지문 → {"status", "memo", "at"}. 화면에서 바꾸면 status.json에 저장된다"""
    try:
        with open(os.path.join(base, "status.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def set_status(base, fp, status, memo=""):
    if status not in STATUSES or not re.fullmatch(r"[0-9a-f]{6,40}", fp or ""):
        return False
    st = load_status(base)
    st[fp] = {"status": status, "memo": (memo or "")[:500], "at": datetime.now(main.KST).isoformat(timespec="seconds")}
    main.write_json(os.path.join(base, "status.json"), st)
    return True


def compare(base, meta, groups, status):
    """같은 사이트(호스트)의 지난 점검과 비교: 항목마다 change(신규·지속·재발), 사라진 항목 목록. 지난 점검이 없으면 None"""
    host = urllib.parse.urlsplit(meta["entry_url"]).netloc.lower()
    prev = next((e for e in records(base) if urllib.parse.urlsplit(e["entry_url"]).netloc.lower() == host and not e.get("error")), None)
    old = prev and read_record(base, prev["file"])
    if not old:
        return None
    before = {g["fp"]: g for g in old.get("groups", [])}
    for g in groups:
        done = (status.get(g["fp"]) or {}).get("status") == "조치 완료"
        g["change"] = "재발" if done else "지속" if g["fp"] in before else "신규"
    now = {g["fp"] for g in groups}
    gone = [{"fp": fp, "evidence_text": g["evidence_text"], "tech_label": g["tech_label"],
             "pages": len({i["url"] for i in g["items"]}), "status": (status.get(fp) or {}).get("status", "미조치")}
            for fp, g in before.items() if fp not in now]
    count = lambda c: sum(g.get("change") == c for g in groups)  # noqa: E731
    return {"prev_at": prev["finished_at"], "new": count("신규"), "kept": count("지속"), "again": count("재발"), "resolved": gone}


def make(meta, items, visited, stopped, minutes, log=print, pages=None, error=None, ctl=None, diag=None, done=None):
    base = main.base_dir()
    hist_path = os.path.join(base, "history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, ValueError):
        history = {}
    groups = group(items, history, meta["started_at"])
    main.write_json(hist_path, history)
    status = load_status(base)
    for g in groups:
        g["status"] = status.get(g["fp"]) or {}
    diff = compare(base, meta, groups, status)
    if groups:
        try:
            asyncio.run(capture(groups, log, ctl))
        except Exception as e:
            log("캡처 단계 오류(보고서는 캡처 없이 만듦): %r" % e)
    if done:  # 탐지 완료 시각 확정 (보고서 파일 쓰기만 남음)
        done(meta)
    data = {
        "meta": dict(meta, visited=visited, stopped=stopped, minutes=minutes, findings=len(items), error=error,
                     report_at=datetime.now(main.KST).isoformat(timespec="seconds")),
        "groups": groups,
        "pages": pages or [],  # 방문한 전체 페이지와 발견 경로 (사이트 지도)
        "guide": GUIDE,
        "diff": diff,
        "diag": diag or [],  # 사이트 진단 (extra.py): 검색 노출 위험 등
        "statuses": STATUSES,
        "ai": ai.summary(),  # R20 AI 사용 명세: 켜지면 rows에 [항목, 값], changed에 AI가 바꾼 판정 (실제 보낸 글 포함)
    }
    page = html_report(data)
    with open(os.path.join(base, "report.html"), "w", encoding="utf-8") as f:
        f.write(page)
    save_record(base, data)
    write_csv(os.path.join(base, "result.csv"), groups)
    log("보고서 저장: report.html, result.csv")
    return data


if __name__ == "__main__":  # 자체 확인: python app/report.py
    it = lambda i, u, loc, t, ev: {"id": i, "url": u, "location": loc, "technique": t, "evidence_text": ev}
    gs = group([it("f_1", "a", "div > span", "OFFSCREEN", "카지노 @x"), it("f_2", "b", "div > span", "OFFSCREEN", "카지노  @x"),
                it("f_3", "a", "td", "JAMO", "ㅋㅏㅈㅣㄴㅗ"), it("f_4", "a", "p", "TRANSPARENT", "토토"),
                it("f_5", "b", "li", "TRANSPARENT", "토토")], {}, "t")
    assert [(g["risk"], g["cause"], len(g["items"])) for g in gs] == [("심각", HACK, 2), ("위험", POST, 2), ("참고", POST, 1)], gs
    # 보이는 변형, 게시판 영역, 같은 사이트 글 링크는 반복돼도 게시물형
    gs = group([it("f_1", "http://s/a", "p", "JAMO", "ㅋr지노"), it("f_2", "http://s/b", "p", "JAMO", "ㅋr지노"),
                it("f_3", "http://s/a", "div#bo_v_con > p", "OFFSCREEN", "토토"), it("f_4", "http://s/b", "div#bo_v_con > p", "OFFSCREEN", "토토"),
                dict(it("f_5", "http://s/a", "li > a", "OFFSCREEN", "바카라"), html='<a href="/bbs?id=3">'),
                dict(it("f_6", "http://s/b", "li > a", "OFFSCREEN", "바카라"), html='<a href="/bbs?id=3">'),
                dict(it("f_7", "http://s/a", "ul > a", "OFFSCREEN", "슬롯"), html='<a href="http://spam.test/">'),
                dict(it("f_8", "http://s/b", "ul > a", "OFFSCREEN", "슬롯"), html='<a href="http://spam.test/">')], {}, "t")
    assert [g["evidence_text"] for g in gs if g["cause"] == HACK] == ["슬롯"], gs
    assert odd_chars("саsino ㅋ가") == [["с", "U+0441", "CYRILLIC SMALL LETTER ES"], ["а", "U+0430", "CYRILLIC SMALL LETTER A"],
                                       ["ㅋ", "U+314B", "HANGUL LETTER KHIEUKH"]]
    page = html_report({"x": "</script><script>alert(1)</script>"})
    assert "</script><script>alert" not in page and json.loads(page.split('id="data">')[1].split("</script>")[0])["x"].startswith("</")
    print("통과")
