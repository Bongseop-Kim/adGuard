"""탐지(result.json) 뒤에 도는 사이트 진단 (todo/08). 검출 시간 밖이다.

    diag = await run(entry, log)   # → [{"name", "level", "summary", "rows": [[항목, 값]], "advice": [...]}]

- S-1 검색 노출 위험(ISAP): 사이트 검색창에 무해한 시험 문자열을 넣어 URL·<title> 반사와 색인 차단을 본다.
  판정 기준은 USENIX Security 2024 (Zhang 외)와 같다: URL 반사 + title 반사 + 색인 허용이면 '위험' (research/11 S-1)
"""
import random
import urllib.parse

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


async def run(entry, log=print):
    from playwright.async_api import async_playwright
    from crawler import INIT, launch

    async with async_playwright() as p:
        browser, _ = await launch(p)
        ctx = await browser.new_context(ignore_https_errors=True, service_workers="block", locale="ko-KR")
        await ctx.add_init_script(INIT)
        out = [await isap(ctx, entry, log)]
        await browser.close()
    for d in out:
        log("진단: %s → %s" % (d["name"], d["level"]))
    return out


if __name__ == "__main__":  # robots_block 자체 시험
    t = "User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nDisallow: /search # 검색\nDisallow: /tmp*\n"
    assert robots_block(t, "/search/list.do") and robots_block(t, "/tmp/x") and not robots_block(t, "/board")
    assert not robots_block("User-agent: *\nDisallow:\n", "/search")
    print("ok")
