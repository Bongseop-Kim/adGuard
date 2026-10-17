"""탐지(result.json) 뒤에 도는 사이트 진단 (todo/08). 검출 시간 밖이다.

    diag, found = await run(entry, log, pages)   # diag → [{"name", "level", "summary", "rows": [[항목, 값]], "advice": [...]}]
                                                 # found → result_extra.json에 덧붙일 CLOAKING 검출

- S-1 검색 노출 위험(ISAP): 사이트 검색창에 무해한 시험 문자열을 넣어 URL·<title> 반사와 색인 차단을 본다.
  판정 기준은 USENIX Security 2024 (Zhang 외)와 같다: URL 반사 + title 반사 + 색인 허용이면 '위험' (research/11 S-1)
- S-3 검색봇 클로킹: 같은 페이지를 일반 브라우저 2회(자연 변동 제거)와 검색봇·검색 유입 모바일로 받아 비교한다.
  봇에게만 생긴 글이 광고이거나, 검색 유입 모바일만 다른 도메인 광고로 넘어가면 CLOAKING (research/11 S-3)
"""
import asyncio
import random
import re
import time
import urllib.parse
from html.parser import HTMLParser

import textcheck

# 검색창으로 볼 입력칸: 논문 Table 2처럼 글을 넣을 수 없는 유형은 뺀다
FIND_JS = r"""
() => {
  const BAD = /^(hidden|submit|button|checkbox|radio|email|password|image|tel|reset|file|color|range|date|datetime-local|month|week|time|number)$/;
  const KEY = /search|srch|query|keyword|kwd|word|^q$|^sw$|^stx$/i;
  const out = [];
  for (const i of document.querySelectorAll('input, textarea')) {
    if (BAD.test(i.type) || !i.form) continue;
    const hint = [i.type, i.name, i.id, i.className, i.placeholder, i.getAttribute('title'), i.getAttribute('aria-label'), i.form.action, i.form.className, i.form.id].join(' ');
    if (i.type !== 'search' && !KEY.test(hint) && !/검색/.test(hint)) continue;
    if (!i.name) continue;
    const f = i.form, rest = [];
    for (const e of f.elements) if (e !== i && e.name && !/^(submit|button|image|reset|file)$/.test(e.type) && (!/checkbox|radio/.test(e.type) || e.checked)) rest.push([e.name, e.value]);
    out.push({ action: f.action || location.href, method: (f.getAttribute('method') || 'get').toLowerCase(), name: i.name, rest });
  }
  return out;
}
"""

ADVICE_ISAP = [
    "검색은 POST로 보내거나, 결과 페이지의 <title>·URL에 검색어를 넣지 않습니다 (USENIX Security 2024 권고).",
    "검색 결과 페이지(특히 결과 0건)에 <meta name=\"robots\" content=\"noindex\">를 넣어 검색엔진 색인을 막습니다.",
    "robots.txt에 검색 결과 경로를 Disallow로 추가합니다 (2025 행정·공공기관 웹사이트 품질관리 지침의 크롤링 일부 차단).",
]


def robots_block(text, path):
    """robots.txt의 User-agent: * 묶음에서 path를 막는 Disallow가 있는가 (가장 단순한 접두어 비교)"""
    on, block = False, False
    for line in (text or "").splitlines():
        k, _, v = line.split("#")[0].partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            on = v == "*"
        elif on and k == "disallow" and v and path.startswith(v.rstrip("*")):
            block = True
    return block


async def isap(ctx, entry, log):
    page = await ctx.new_page()
    name = "검색 노출 위험 (ISAP)"
    try:
        await page.goto(entry, wait_until="domcontentloaded", timeout=15000)
        forms = await page.evaluate(FIND_JS)
        host = urllib.parse.urlsplit(page.url).hostname
        own = [f for f in forms if urllib.parse.urlsplit(f["action"]).hostname == host]
        if not forms:
            return {"name": name, "level": "판정 불가", "summary": "시작 페이지에서 검색창을 찾지 못했습니다.", "rows": [], "advice": []}
        if not own:  # 논문의 오탐 주원인: 외부 검색엔진(site: 검색)을 부르는 사이트
            return {"name": name, "level": "안전", "summary": "검색창이 외부 검색엔진으로 연결되어 이 사이트의 검색 결과 페이지가 없습니다.",
                    "rows": [["검색창 연결", forms[0]["action"]]], "advice": []}
        f = own[0]
        if f["method"] == "post":
            return {"name": name, "level": "안전", "summary": "검색이 POST로 전송되어 검색어가 URL에 남지 않습니다.",
                    "rows": [["검색 주소", f["action"]], ["전송 방식", "POST"]], "advice": []}
        canary = "adgisap%05d" % random.randrange(100000)  # 무해한 시험 문자열
        q = [(f["name"], canary)] + [tuple(x) for x in f["rest"]]
        s = urllib.parse.urlsplit(f["action"])
        url = urllib.parse.urlunsplit(s._replace(query=urllib.parse.urlencode(q), fragment=""))
        log("진단: 검색 노출 위험 시험 %s" % url)
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        got = await page.evaluate("""c => ({ title: document.title, body: (document.body && document.body.innerText || '').includes(c),
            robots: [...document.querySelectorAll('meta[name="robots" i], meta[name="googlebot" i], meta[name="yeti" i]')].map(m => m.content).join(' ') })""", canary)
        header = (resp and resp.headers.get("x-robots-tag")) or ""
        noindex = "noindex" in (got["robots"] + " " + header).lower()
        robots = ""
        try:
            r = await ctx.request.get(urllib.parse.urlunsplit((s.scheme, s.netloc, "/robots.txt", "", "")), timeout=5000)
            robots = await r.text() if r.ok else ""
        except Exception:
            pass
        blocked = robots_block(robots, urllib.parse.urlsplit(page.url).path or "/")
        in_url, in_title = canary in urllib.parse.unquote(page.url), canary in got["title"]
        rows = [["시험 주소", page.url], ["URL에 반사", "예" if in_url else "아니요"], ["<title>에 반사", "예" if in_title else "아니요"],
                ["본문에 반사", "예" if got["body"] else "아니요"], ["noindex", "있음" if noindex else "없음"],
                ["robots.txt 차단", "있음" if blocked else "없음"], ["결과 페이지 제목", got["title"][:120]]]
        if in_url and in_title and not noindex and not blocked:
            return {"name": name, "level": "위험", "rows": rows, "advice": ADVICE_ISAP,
                    "summary": "검색어가 URL과 페이지 제목에 그대로 들어가고 색인도 막혀 있지 않습니다. 누구나 광고 문구로 검색한 주소를 퍼뜨려 "
                               "검색엔진에 이 사이트 이름으로 광고를 올릴 수 있습니다."}
        if (in_url and got["body"]) and not noindex and not blocked:
            return {"name": name, "level": "참고", "rows": rows, "advice": ADVICE_ISAP,
                    "summary": "검색어가 본문에 반사되지만 페이지 제목에는 들어가지 않아 검색 결과 노출 위험은 낮습니다."}
        return {"name": name, "level": "안전", "rows": rows, "advice": [],
                "summary": "검색어가 제목에 반사되지 않거나 색인이 막혀 있어 검색 결과 노출 위험이 낮습니다."}
    except Exception as e:
        return {"name": name, "level": "판정 불가", "summary": "진단 중 오류: %s" % type(e).__name__, "rows": [], "advice": []}
    finally:
        await page.close()


DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
MOBILE = "Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"
BOTS = {"Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Yeti(네이버)": "Mozilla/5.0 (compatible; Yeti/1.1; +https://naver.me/spd)",
        "Daum": "Mozilla/5.0 (compatible; Daum/4.1; +http://cs.daum.net/faq/15/4118.html?faqId=28966)"}
REFERERS = {"구글 검색 유입 모바일": "https://www.google.com/", "네이버 검색 유입 모바일": "https://m.search.naver.com/search.naver?query=%EA%B3%B5%EC%A7%80"}
CHALLENGE = re.compile(r"checking your browser|cf-chl|just a moment|captcha|보안 확인|자동입력 방지", re.I)
CLOAK_PAGES, CLOAK_SEC = 20, 60


class Text(HTMLParser):
    """HTML → 글 조각 목록 (script·style 제외). 봇 응답은 렌더링하지 않고 원문으로 비교한다"""

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, a):
        self.skip += tag in ("script", "style", "noscript", "template")

    def handle_endtag(self, tag):
        self.skip -= tag in ("script", "style", "noscript", "template") and self.skip > 0

    def handle_data(self, d):
        d = " ".join(d.split())
        if d and not self.skip:
            self.out.append(d)


def chunks(html):
    t = Text()
    try:
        t.feed(html)
    except Exception:
        pass
    return t.out


def added_ad(base, other):
    """other에만 있는 글 조각(순서대로 이어 붙임)이 광고면 그 글. base = 일반 브라우저 응답들의 조각 집합"""
    extra = " ".join(c for c in other if c not in base)
    return extra[:300] if extra and textcheck.check(extra)["ad"] else None


def pick(pages, entry, n):
    """시작 페이지 먼저, 나머지는 구역(경로 첫 단계)마다 돌아가며 고른다"""
    by = {}
    for p in [entry] + [x["url"] for x in pages]:
        k = urllib.parse.urlsplit(p).path.strip("/").split("/")[0]
        if p not in by.setdefault(k, []):
            by[k].append(p)
    out, lists = [], list(by.values())
    while len(out) < n and any(lists):
        for lst in lists:
            if lst and len(out) < n:
                out.append(lst.pop(0))
    return out


async def cloaking(p, browser, entry, pages, log, end=None):
    name = "검색봇 클로킹"
    t0, found, rows, blocked, compared = time.monotonic(), [], [], {}, 0
    req = await p.request.new_context(ignore_https_errors=True)
    mob = await browser.new_context(ignore_https_errors=True, service_workers="block", user_agent=MOBILE, is_mobile=True,
                                    viewport={"width": 390, "height": 844}, locale="ko-KR")
    host = urllib.parse.urlsplit(entry).hostname

    async def get(url, ua, ref=None):
        h = {"User-Agent": ua}
        if ref:
            h["Referer"] = ref
        r = await req.get(url, headers=h, timeout=10000, max_redirects=5)
        return r.status, await r.text(), r.url

    async def render(ctx, url, ref=None):
        pg = await ctx.new_page()
        try:
            await pg.goto(url, referer=ref, wait_until="load", timeout=10000)
            await pg.wait_for_timeout(1000)  # 로드 뒤 JS 이동을 기다린다
            return pg.url, await pg.evaluate("() => [document.title, document.body ? document.body.innerText : '']")
        finally:
            await pg.close()

    async def one(url):
        nonlocal compared
        if time.monotonic() - t0 > CLOAK_SEC or end and time.monotonic() > end - 45:  # end: 보고서까지 끝낼 시각 (4쪽 1묶음 최대 약 30초)
            return
        try:
            (s1, h1, _), (s2, h2, _) = await asyncio.gather(get(url, DESKTOP), get(url, DESKTOP))
        except Exception:
            return
        compared += 1
        base = set(chunks(h1)) | set(chunks(h2))  # 두 번 받아 합치면 매번 바뀌는 조각(시각·토큰)은 비교에서 빠진다
        bots = await asyncio.gather(*(get(url, ua) for ua in BOTS.values()), return_exceptions=True)
        for bot, r in zip(BOTS, bots):
            if isinstance(r, Exception):
                continue
            st, html, _ = r
            if st in (403, 429, 503) or CHALLENGE.search(html[:5000]):
                blocked.setdefault(url, set()).add(bot)  # 가짜 봇 차단(WAF)·보안 확인: 클로킹으로 보지 않는다
                continue
            ad = added_ad(base, chunks(html))
            if ad:
                found.append({"url": url, "location": "body", "technique": "ETC", "extra_finding": "CLOAKING", "evidence_text": ad,
                              "reason": "%s에게만 보이는 광고 (일반 브라우저 상태 %d, %s 상태 %d)" % (bot, s1, bot, st)})
                break
        # 검색 유입 모바일: 렌더링해서 JS 이동까지 본다. 크롤러가 데스크톱으로 연 이 주소는 같은 사이트에 머물렀다
        mobs = await asyncio.gather(*(render(mob, url, ref) for ref in REFERERS.values()), return_exceptions=True)
        for prof, r in zip(REFERERS, mobs):
            if isinstance(r, Exception):
                continue
            murl, (title, text) = r
            if urllib.parse.urlsplit(murl).hostname != host and textcheck.check(title + " " + text[:2000])["ad"]:
                found.append({"url": url, "location": "body", "technique": "ETC", "extra_finding": "CLOAKING",
                              "evidence_text": " ".join((title + " " + text).split())[:300],
                              "reason": "%s만 다른 도메인 광고로 이동 (%s)" % (prof, murl)})
                break

    try:
        todo = pick(pages, entry, CLOAK_PAGES)
        for i in range(0, len(todo), 4):  # 4쪽씩 동시에
            await asyncio.gather(*(one(u) for u in todo[i:i + 4]))
        if compared < len(todo):
            rows.append(["시간 상한", "%d초에 닿아 %d쪽까지만 비교" % (CLOAK_SEC, compared)])
    finally:
        await req.dispose()
        await mob.close()
    rows = [["비교한 페이지", "%d쪽" % compared], ["비교 방식", "일반 브라우저 2회 / " + " · ".join(BOTS) + " / " + " · ".join(REFERERS)]] + rows
    if blocked:  # 봇 이름 요청을 막은 쪽: 그 쪽의 봇 비교는 판정 불가
        rows.append(["봇 요청 차단", "%d쪽 (%s). 그 쪽의 봇 비교는 판정 불가" % (len(blocked), ", ".join(sorted(set().union(*blocked.values()))))])
    rows.append(["한계", "접속 IP·국가로 바꾸는 클로킹은 이 PC에서 확인할 수 없습니다"])
    advice = ["서버의 웹 설정(.htaccess·web.config·IIS 모듈)과 공통 템플릿에서 User-Agent·Referer로 분기하는 코드를 찾아 지웁니다 (BadIIS·PHP 백도어 사례).",
              "검색엔진의 '실제 크롤러가 본 페이지'(Google Search Console URL 검사, 네이버 서치어드바이저 웹페이지 수집)로 봇이 본 내용을 확인합니다.",
              "KISA 인터넷침해대응센터(118)에 신고하고, 웹셸 점검 뒤 관리자 비밀번호를 바꿉니다."]
    if found:
        return found, {"name": name, "level": "위험", "rows": rows, "advice": advice,
                       "summary": "검색봇이나 검색으로 들어온 모바일 사용자에게만 다른 내용(광고)을 보여 주는 페이지가 %d쪽 있습니다. 관리자 브라우저로는 보이지 않습니다." % len({f["url"] for f in found})}
    if compared and sum(len(b) == len(BOTS) for b in blocked.values()) == compared:
        return [], {"name": name, "level": "판정 불가", "rows": rows, "advice": [],
                    "summary": "사이트가 검색봇 이름의 요청을 막아 비교하지 못했습니다. 검색 유입 모바일 비교에서는 차이가 없었습니다."}
    return [], {"name": name, "level": "안전" if compared else "판정 불가", "rows": rows, "advice": [],
                "summary": "검색봇·검색 유입 모바일에게만 보이는 광고는 없었습니다." if compared else "비교할 페이지를 받지 못했습니다."}


async def run(entry, log=print, pages=(), end=None):
    from playwright.async_api import async_playwright
    from crawler import INIT, launch

    async with async_playwright() as p:
        browser, _ = await launch(p)
        ctx = await browser.new_context(ignore_https_errors=True, service_workers="block", locale="ko-KR")
        await ctx.add_init_script(INIT)
        out = [await isap(ctx, entry, log)]
        found, d = await cloaking(p, browser, entry, list(pages), log, end)
        out.append(d)
        await browser.close()
    for d in out:
        log("진단: %s → %s" % (d["name"], d["level"]))
    return out, found


if __name__ == "__main__":  # robots_block 자체 시험
    t = "User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nDisallow: /search # 검색\nDisallow: /tmp*\n"
    assert robots_block(t, "/search/list.do") and robots_block(t, "/tmp/x") and not robots_block(t, "/board")
    assert not robots_block("User-agent: *\nDisallow:\n", "/search")
    base = set(chunks("<p>공지</p><script>var t='카지노'</script><span>12:00</span>")) | set(chunks("<p>공지</p><span>12:01</span>"))
    assert added_ad(base, chunks("<p>공지</p><span>12:02</span>")) is None  # 시각 변동은 광고 아님
    assert added_ad(base, chunks("<p>공지</p><div>카지노 가입코드 TEST1 @test_x</div>"))
    assert pick([{"url": "http://a/b/1"}, {"url": "http://a/b/2"}, {"url": "http://a/c/1"}], "http://a/", 3) == ["http://a/", "http://a/b/1", "http://a/c/1"]
    print("ok")
