"""크롤러: 진입 URL에서 같은 도메인 하위 페이지·게시글·댓글·iframe까지 렌더링하며 방문한다.

근거: docs/research/03-검출개수-탐색전략.md, 05-시간-실행환경.md

    results = asyncio.run(crawl(url, analyze))   # analyze(page, url) -> 페이지별 분석 결과

- 브라우저 1개 + 컨텍스트 N개(워커) + 우선순위 BFS(상세 > 목록 > 일반, 같은 순위는 깊이 순)
- 링크: DOM href/action/data-*/meta refresh(Shadow DOM 포함, 모든 프레임) + 주석·스크립트·onclick 문자열 속 URL
  + robots.txt(Sitemap·Disallow·Allow) + sitemap(index, .gz) + onclick/javascript: 클릭 → 이동 요청 가로채기(POST 포함)
- 정규화: 모집요강 12쪽(#·끝 / 무시, 쿼리 순서 무시) + `;jsessionid` 제거 + 정렬·검색 꼬리표 제거
  + 글 ID가 있으면 목록 쪽번호 제거 + 내용이 같은 페이지는 1번만(대표 URL은 짧은 것)
- 함정: 패턴별 상한(날짜형 24, 그 밖 500), 쓰기·삭제·로그아웃 링크 차단, 페이지·프레임 타임아웃, 전체 시간 제한
- 실제 사이트 대응: 경고창은 기록하고 닫음, "모바일 전용" 경고 뒤 다른 곳으로 보내면 모바일 화면으로 다시 엶,
  연결 실패·타임아웃은 쿠키가 새로운 컨텍스트로 1번 더 시도, 실패가 이어지면 병렬 수를 줄이고 회복되면 늘림
"""
import asyncio
import gzip
import hashlib
import heapq
import os
import re
import sys
import time
import urllib.parse

INIT = r"""
(() => {
  // closed Shadow DOM을 open으로 (research/03 §2)
  const as = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (i) { return as.call(this, Object.assign({}, i, { mode: 'open' })); };
  // 3초 이하 setTimeout을 세어 둔다: 로드 뒤 JS가 넣는 광고를 기다리기 위해
  const st = window.setTimeout, ct = window.clearTimeout, ids = new Set();
  window.__adgST = st; window.__adgT = ids;
  window.setTimeout = function (f, d, ...a) {
    const id = st.call(window, function (...x) { ids.delete(id); return typeof f === 'function' ? f.apply(this, x) : (0, eval)(f); }, d, ...a);
    if (!(d > 3000)) ids.add(id);
    return id;
  };
  window.clearTimeout = function (id) { ids.delete(id); return ct.call(window, id); };
  // loading="lazy" iframe·img를 바로 불러온다 (안 그러면 프레임 evaluate가 무한 대기)
  const eager = n => { if (n.nodeType === 1) for (const e of [n, ...n.querySelectorAll('[loading]')]) if (e.loading === 'lazy') e.loading = 'eager'; };
  new MutationObserver(ms => { for (const m of ms) m.addedNodes.forEach(eager); }).observe(document, { childList: true, subtree: true });
})();
"""

# DOM 변화가 300ms 없고 대기 중인 짧은 타이머가 없을 때까지 (최대 3초)
SETTLE_JS = r"""() => new Promise(res => {
  let last = Date.now(); const t0 = last, st = window.__adgST || setTimeout;
  const mo = new MutationObserver(() => last = Date.now());
  mo.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  (function tick() {
    const now = Date.now();
    if ((now - last >= 300 && !(window.__adgT && window.__adgT.size)) || now - t0 > 3000) { mo.disconnect(); res(); }
    else st(tick, 50);
  })();
})"""

LINKS_JS = r"""() => {
  const out = new Set(), texts = [];
  const abs = u => { try { return new URL(u.trim(), document.baseURI).href; } catch (e) { return null; } };
  const add = u => { const a = u && abs(u); if (a) out.add(a); };
  const walk = root => {
    for (const e of root.querySelectorAll('a[href],area[href],[data-href],[data-url],form[action],meta[http-equiv],[onclick]')) {
      const t = e.tagName;
      if (t === 'A' || t === 'AREA') { if (!/^(ko|$)/i.test(e.getAttribute('hreflang') || '')) continue; add(e.getAttribute('href')); }
      else if (t === 'FORM') { if ((e.getAttribute('method') || 'get').toLowerCase() === 'get') add(e.getAttribute('action')); }
      else if (t === 'META') { const m = /url\s*=\s*['"]?([^'"]+)/i.exec(e.getAttribute('content') || ''); if (m) add(m[1]); }
      add(e.getAttribute('data-href')); add(e.getAttribute('data-url'));
      if (e.hasAttribute('onclick')) texts.push(['q', e.getAttribute('onclick')]);
    }
    for (const s of root.querySelectorAll('script:not([src])')) texts.push(['q', s.textContent]);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT);
    while (w.nextNode()) texts.push(['c', w.currentNode.nodeValue]);
    for (const e of root.querySelectorAll('*')) if (e.shadowRoot) walk(e.shadowRoot);
  };
  walk(document);
  // 문자열 속 URL: 스크립트·onclick은 따옴표 안, 주석은 공백 뒤 경로
  const Q = /["'`]((?:https?:)?\/[^"'`\s<>]*)["'`]/g, C = /(?:^|[\s:("'=])((?:https?:\/\/|\/)[^\s"'<>()]+)/g;
  for (const [k, t] of texts) for (const m of (t || '').matchAll(k === 'q' ? Q : C)) add(m[1]);
  return { links: [...out], scripts: [...document.querySelectorAll('script[src]')].map(s => s.src) };
}"""

# 같은 페이지에 내용을 덧붙이는 버튼: 보이고, 다른 주소로 가는 href가 없는 것
EXPAND_JS = r"""() => {
  const R = /더\s*보기|more|펼치기|펼쳐\s*보기|전체\s*보기|댓글\s*보기|이전\s*댓글|다음\s*댓글/i;
  const out = [];
  document.querySelectorAll('button,a,[role=button],input[type=button]').forEach((e, i) => {
    const t = (e.textContent || e.value || e.getAttribute('aria-label') || '').trim();
    const h = e.tagName === 'A' ? (e.getAttribute('href') || '') : '';
    if (!R.test(t) || t.length > 30 || (h && !/^(#|javascript:)/i.test(h))) return;
    if (!e.getClientRects().length || getComputedStyle(e).visibility === 'hidden') return;
    e.setAttribute('data-adg-x', i); out.push([i, t]);
  });
  return out;
}"""

CAND = '[onclick],a[href^="javascript:" i]'
CANDS_JS = r"""(sel) => [...document.querySelectorAll(sel)].map(e => {
  const h = e.getAttribute('href') || '';
  let js = ''; try { js = /^javascript:/i.test(h) ? decodeURIComponent(h.slice(11)) : ''; } catch (x) {}
  return [(e.getAttribute('onclick') || '') + ';' + js, (e.textContent || '').trim().slice(0, 40)];
})"""
CLICK_JS = "([sel, i]) => { const e = document.querySelectorAll(sel)[i]; if (e) e.click(); }"

# 누르거나 방문하면 안 되는 것 (research/03 §1)
# URL·onclick 코드는 영어 토큰으로, 버튼 글자는 이름 전체가 위험 단어일 때만 ("전입신고 안내"·"추천 도서"는 통과)
DANGER = re.compile(r"delete|remove|update|write|insert|logout|logoff|signout|vote|print|modify|"
                    r"act=disp\w*(?:delete|modify|write|reply)|act=dispmember|sns_send|sharer?\.php", re.I)
DANGER_LABEL = re.compile(r"^\s*(?:삭제|수정|등록|글쓰기|쓰기|답변|답글|로그아웃|탈퇴|추천|신고|스크랩|인쇄|검색|delete|edit|write|"
                          r"logout|print)(?:하기)?\s*$", re.I)
INERT_FN = {"void", "blur", "focus", "print", "close", "alert", "confirm", "back", "forward", "go", "reload",
            "preventDefault", "stopPropagation", "return", "toggle", "toggleClass", "addClass", "removeClass", "scrollTo"}
# 첨부파일 내려받기 주소 (그누보드 download.php, 전자정부 FileDown.do 등): 페이지가 아니다
DOWNLOAD = re.compile(r"download\.(?:php|do|jsp|aspx?)|file_?down", re.I)
SKIP_EXT = re.compile(r"\.(pdf|hwp|hwpx|docx?|xlsx?|pptx?|zip|rar|7z|gz|tar|jpe?g|png|gif|bmp|svg|webp|ico|mp[34]|avi|mov|"
                      r"wmv|wav|css|js|json|xml|txt|exe|msi|apk|woff2?|ttf)$", re.I)
# 글 내용을 바꾸지 않는 정렬·검색·분류 꼬리표 (그누보드 $qstr·device, 전자정부 search*, XE·라이믹스)
NOISE = {"device", "sca", "sfl", "stx", "sst", "sod", "sop", "spt", "searchcnd", "searchwrd", "searchkeyword", "searchcondition",
         "searchtype", "searchword", "sort", "order", "orderby", "sortorder", "sortfield",
         "sort_index", "order_type", "liststyle", "search_target", "search_keyword"}
# 세션 언어를 바꾸는 주소·버튼: 누르면 이후 페이지가 다른 언어로 나온다 (research/13 §5, 사이트 E doChangeLangType)
LANG_URL = re.compile(r"[?&](?:lang|lang_type|locale|language)=(?!ko)", re.I)
LANG_CODE = re.compile(r"lang|locale", re.I)
PAGE_KEYS = {"page", "pageindex", "pageno", "pagenum", "currentpage", "curpage"}
ID_KEYS = {"id", "wr_id", "nttid", "no", "idx", "seq", "document_srl", "articleno", "bno", "num", "p", "nttsn", "postid"}
DATE_KEYS = {"ym", "yyyymm", "year", "month", "day", "date", "yy", "mm", "dd", "caldate", "sdate", "edate", "week"}
DATE_VAL = re.compile(r"^\d{4}[-./]?\d{2}(?:[-./]?\d{2})?$")
MOBILE_ONLY = re.compile(r"모바일|mobile|스마트폰", re.I)
# 원본 HTML의 meta refresh: 0초 이동은 분석 도중 페이지를 바꿔 DOM에서 못 읽을 수 있다
META_REFRESH = re.compile(r"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[^>]*content\s*=\s*[\"']?\s*\d*\s*;?\s*url\s*=\s*([^\"'>]+)", re.I)
NET_ERR = re.compile(r"Timeout|net::ERR_")
CAP_DATE, CAP_PATTERN = 24, 500  # ponytail: 패턴당 고정 상한, 실제 사이트에서 모자라면 조정


def norm(u):
    """중복 판정 키 (모집요강 12쪽 + ;jsessionid 제거 + 쿼리가 있는 /index.php는 디렉터리와 같음)."""
    s = urllib.parse.urlsplit(u)
    path = re.sub(r";jsessionid=[^/?#]*", "", s.path, flags=re.I).rstrip("/") or "/"
    if s.query and path.endswith("/index.php"):  # XE·라이믹스 /?mid=…와 /index.php?mid=…는 같은 페이지 (P7)
        path = path[:-10] or "/"
    q = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(s.query, keep_blank_values=True)))
    return "%s%s%s" % (s.netloc.lower(), path, "?" + q if q else "")


def minimize(u, extra=None):
    """방문·출력용 URL: # 제거, ;jsessionid 제거, 꼬리표 제거, 글 ID가 있으면 쪽번호 제거.
    extra(POST 본문)는 쿼리에 합치고 빈 값은 버린다."""
    s = urllib.parse.urlsplit(u)
    path = re.sub(r";jsessionid=[^/?#]*", "", s.path, flags=re.I)
    q = urllib.parse.parse_qsl(s.query, keep_blank_values=True)
    if extra is not None:
        body = urllib.parse.parse_qsl(extra, keep_blank_values=True)
        keys = {k for k, _ in body}
        q = [(k, v) for k, v in q if k not in keys] + body
        q = [(k, v) for k, v in q if v != ""]
    keys = {k.lower() for k, _ in q}
    drop = NOISE | (PAGE_KEYS if keys & ID_KEYS else set())
    q = [(k, v) for k, v in q if k.lower() not in drop]
    return urllib.parse.urlunsplit((s.scheme, s.netloc, path, urllib.parse.urlencode(q), ""))


def section(u):
    """게시판 단위 키: 글 ID·쪽번호를 뺀 norm (같은 게시판 글은 같은 키)"""
    s = urllib.parse.urlsplit(minimize(u))
    q = [(k, v) for k, v in urllib.parse.parse_qsl(s.query, keep_blank_values=True) if k.lower() not in ID_KEYS | PAGE_KEYS]
    return norm(urllib.parse.urlunsplit((s.scheme, s.netloc, s.path, urllib.parse.urlencode(q), "")))


def signature(u):
    s = urllib.parse.urlsplit(u)
    q = urllib.parse.parse_qsl(s.query, keep_blank_values=True)
    is_date = any(k.lower() in DATE_KEYS or DATE_VAL.match(v) for k, v in q)
    return (s.netloc.lower(), s.path, tuple(sorted({k for k, _ in q}))), is_date


def priority(u):
    s = urllib.parse.urlsplit(u.lower())
    keys = {k for k, _ in urllib.parse.parse_qsl(s.query)}
    if keys & ID_KEYS or re.search(r"view|read|detail|article", s.path):
        return 1
    if keys & PAGE_KEYS or re.search(r"list|board|bbs", s.path):
        return 2
    return 3


def call_of(code):
    """onclick 코드에서 첫 함수 호출 (이름, 인자들)."""
    for m in re.finditer(r"([A-Za-z_$][\w$.]*)\s*\(([^()]*)\)", code):
        name = m.group(1)
        if name.split(".")[-1] not in INERT_FN:
            args = [a or b or c for a, b, c in re.findall(r"'([^']*)'|\"([^\"]*)\"|([^,\s'\"]+)", m.group(2))]
            return name, args
    return None, None


def substitute(req, a, b):
    """템플릿 요청(method, url, body)에서 인자 a를 b로 바꾼다. 못 바꾸는 인자가 있으면 None."""
    method, url, body = req
    for x, y in zip(a, b):
        if x == y:
            continue
        pat = re.compile(r"(?<=[=/])%s(?=[&/;?]|$)" % re.escape(urllib.parse.quote_plus(x)))
        n1 = n2 = 0
        url, n1 = pat.subn(urllib.parse.quote_plus(y).replace("\\", "\\\\"), url)
        if body:
            body, n2 = pat.subn(urllib.parse.quote_plus(y).replace("\\", "\\\\"), body)
        if not n1 + n2:
            return None
    return method, url, body


async def launch(p):
    try:
        return await p.chromium.launch(), "동봉 Chromium"
    except Exception:
        return await p.chromium.launch(channel="msedge"), "Edge"  # 동봉 Chromium이 막히면 Edge로


async def with_timeout(coro, sec):
    try:
        return await asyncio.wait_for(coro, sec)
    except Exception:
        return None


class Crawler:
    def __init__(self, entry, analyze, workers, time_limit, log):
        self.entry, self.analyze, self.log = entry, analyze, log
        self.workers = workers or max(2, min(6, os.cpu_count() or 4))  # ponytail: RAM 기준 자동 조정은 실측 후
        self.deadline = time.monotonic() + time_limit
        e = urllib.parse.urlsplit(entry)
        self.netloc, self.base = e.netloc.lower(), (e.hostname or "").lower().removeprefix("www.")
        self.heap, self.seq, self.active = [], 0, 0
        self.seen, self.sig_count = set(), {}
        self.hashes, self.results = {}, []  # 내용 해시 → results 인덱스
        self.canons = set()  # 결과로 남긴 페이지의 대표 주소(norm)
        self.templates = {}  # (페이지 패턴, 함수명) → (요청, 인자) 또는 None(이동 없음)
        self.visited = 0
        self.errors = []
        self.own = set()
        self.js_seen = set()
        self.dropped = 0
        self.mobile = set()  # 모바일 화면으로만 열리는 주소·게시판 (norm, section)
        self.retried = set()
        self.limit, self.fails, self.oks = self.workers, 0, 0  # 지금 쓰는 병렬 수, 연속 실패·성공 수
        self.dialogs = []  # (URL, 경고창 문구)
        self.via = {}  # norm(URL) → (찾은 페이지 URL 또는 None, 찾은 방법). 보고서의 발견 경로
        # 사용자가 직접 넣은 시작 주소는 명시적 의도라 위험·내려받기 필터를 건너뛴다 (research/13 §5, RFC 9110 GET은 안전)
        self.start = norm(minimize(entry))
        self.blocked = 0  # 위험·내려받기 주소라 큐에 넣지 않은 수
        self.start_fail = None  # 시작 주소가 열렸지만 점검할 웹 페이지가 아닐 때 그 사유

    def stop(self):  # 화면의 "중단": 새 페이지를 꺼내지 않고, 진행 중인 페이지만 마친 뒤 모은 결과를 돌려준다
        self.deadline = 0

    def in_scope(self, u):
        s = urllib.parse.urlsplit(u)
        host = (s.hostname or "").lower()
        return s.scheme in ("http", "https") and (s.netloc.lower() == self.netloc or host.endswith("." + self.base))

    def requeue(self, url, post, depth, prio):
        self.seq += 1
        heapq.heappush(self.heap, (prio, depth, self.seq, url, post))

    def push(self, url, depth, body=None, via=(None, "링크")):
        post = (url, body) if body is not None else None  # POST로만 열리면 원래 action과 본문을 남겨 둔다
        url = minimize(url, body)
        key = norm(url)
        if key != self.start:
            s = urllib.parse.urlsplit(url)
            # 쿼리 값의 확장자도 본다: view_image.php?fn=a.jpg (P12)
            if not self.in_scope(url) or SKIP_EXT.search(s.path) or LANG_URL.search(url) or \
                    any(SKIP_EXT.search(v) for _, v in urllib.parse.parse_qsl(s.query)):
                return
            if DANGER.search(url) or DOWNLOAD.search(url):
                self.blocked += key not in self.seen
                self.seen.add(key)
                return
        if key in self.seen:
            return
        self.seen.add(key)
        self.via[key] = via
        sig, is_date = signature(url)
        self.sig_count[sig] = n = self.sig_count.get(sig, 0) + 1
        if n > (CAP_DATE if is_date else CAP_PATTERN):
            self.dropped += 1
            return
        self.seq += 1
        heapq.heappush(self.heap, (priority(url), depth, self.seq, url, post))

    async def seed(self, ctx):
        """robots.txt와 sitemap에서 시드를 얻는다. 메뉴에 없는 옛 게시판용 (research/03 §2)."""
        s = urllib.parse.urlsplit(self.entry)
        root = "%s://%s" % (s.scheme, s.netloc)
        sitemaps = [root + "/sitemap.xml"]
        self.via[norm(root + "/robots.txt")] = (self.entry, "robots.txt 확인")
        self.via[norm(sitemaps[0])] = (self.entry, "sitemap.xml 확인")
        txt = await self.fetch(ctx, root + "/robots.txt")
        for line in (txt or "").splitlines():
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.split("#")[0].strip()
            if k == "sitemap" and v:
                sitemaps.append(urllib.parse.urljoin(root, v))
                self.via.setdefault(norm(sitemaps[-1]), (root + "/robots.txt", "robots.txt의 Sitemap"))
            elif k in ("allow", "disallow") and v.startswith("/") and v != "/":
                self.push(root + re.split(r"[*$]", v)[0], 1, via=(root + "/robots.txt", "robots.txt"))
        done = set()
        while sitemaps and len(done) < 50:
            sm = sitemaps.pop(0)
            if sm in done:
                continue
            done.add(sm)
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", await self.fetch(ctx, sm) or ""):
                loc = loc.replace("&amp;", "&")
                if re.search(r"\.xml(\.gz)?$", urllib.parse.urlsplit(loc).path, re.I):
                    sitemaps.append(loc)
                    self.via.setdefault(norm(loc), (sm, "sitemap 색인"))
                else:
                    self.push(loc, 1, via=(sm, "sitemap"))

    async def fetch(self, ctx, url):
        try:
            r = await ctx.request.get(url, timeout=10000)
            if not r.ok:
                return None
            data = await r.body()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            return data.decode("utf-8", "replace")
        except Exception:
            return None

    async def run(self):
        from playwright.async_api import async_playwright

        t0 = time.monotonic()
        async with async_playwright() as p:
            browser, kind = await launch(p)
            self.phone = p.devices["iPhone 13"]
            self.log("브라우저: %s %s, 병렬 %d" % (kind, browser.version, self.workers))
            self.browser = browser
            ctxs = [await self.new_ctx() for _ in range(self.workers)]
            self.push(self.entry, 0, via=(None, "시작 주소"))
            await self.seed(ctxs[0])
            tasks = [asyncio.create_task(self.worker(c, i)) for i, c in enumerate(ctxs)]
            # 하드 데드라인: 시간이 다 되면 진행 중인 페이지도 끊고 모은 결과만 돌려준다
            _, pending = await asyncio.wait(tasks, timeout=max(1, self.deadline - time.monotonic()) + 30)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await browser.close()
        self.log("크롤 완료: 렌더링 %d쪽, 결과 페이지 %d개, 상한으로 제외 %d개, 위험·내려받기 주소라 제외 %d개, %.1f초"
                 % (self.visited, len(self.results), self.dropped, self.blocked, time.monotonic() - t0))
        return self.results

    def on_popup(self, page):
        async def grab():  # window.open·target=_blank 새 창은 URL만 큐에 넣고 닫는다
            await with_timeout(page.wait_for_load_state("domcontentloaded"), 3)
            if page.url.startswith("http"):
                self.push(page.url, 9, via=(None, "새 창(window.open)"))
            await with_timeout(page.close(), 2)
        async def later():
            await asyncio.sleep(0.2)
            if page not in self.own:  # 워커가 직접 만든 탭은 제외
                await grab()
        asyncio.ensure_future(later())

    async def new_ctx(self, mobile=False):
        view = self.phone if mobile else {"viewport": {"width": 1280, "height": 720}}
        ctx = await self.browser.new_context(ignore_https_errors=True, service_workers="block", locale="ko-KR", **view)
        await ctx.add_init_script(INIT)
        ctx.on("page", self.on_popup)
        # 공유·위험 주소는 클릭으로 나가는 요청(새 창 포함)도 막는다. 끝나지 않는 요청이 PHP 세션을 잠그면 같은 쿠키의 모든 요청이 멈춘다
        await ctx.route(DANGER, lambda route: route.continue_() if norm(minimize(route.request.url)) == self.start else route.abort())
        return ctx

    async def worker(self, ctx, n):
        tabs = {False: (ctx, await self.new_page(ctx))}  # 모바일 탭은 필요할 때 만든다
        while time.monotonic() < self.deadline:
            if not self.heap:
                if self.active == 0:
                    break
                await asyncio.sleep(0.05)
                continue
            if n >= self.limit:  # 서버가 버거워해서 쉬는 워커
                await asyncio.sleep(0.5)
                continue
            prio, depth, _, url, post = heapq.heappop(self.heap)
            mobile = norm(url) in self.mobile or section(url) in self.mobile
            if mobile not in tabs:
                c = await self.new_ctx(mobile)
                tabs[mobile] = (c, await self.new_page(c))
            ctx, page = tabs[mobile]
            self.active += 1
            try:
                await asyncio.wait_for(self.visit(page, url, post, depth, mobile), 60)
                self.ok()
            except Exception as e:
                self.errors.append((url, repr(e)[:200]))
                await with_timeout(page.close(), 3)
                if NET_ERR.search(repr(e)):
                    # 끝나지 않는 요청이 서버 세션을 잠갔을 수 있다: 쿠키가 새로운 컨텍스트로 바꾼다
                    await with_timeout(ctx.close(), 5)
                    ctx = await self.new_ctx(mobile)
                    self.fail()
                    # 서버 전체가 힘든 때(연결 실패, 연속 실패)만 나중에 1번 더. 혼자 멈추는 함정 페이지는 다시 기다리지 않는다
                    if ("net::ERR_" in repr(e) or self.fails >= 2) and norm(url) not in self.retried:
                        self.retried.add(norm(url))
                        self.requeue(url, post, depth, prio + 10)
                tabs[mobile] = (ctx, await self.new_page(ctx))  # 멈춘 탭은 버리고 새로 연다
            finally:
                self.active -= 1
        for c, _ in tabs.values():
            await with_timeout(c.close(), 5)

    def ok(self):
        self.fails, self.oks = 0, self.oks + 1
        if self.oks >= 10 and self.limit < self.workers:
            self.limit, self.oks = self.limit + 1, 0

    def fail(self):
        self.oks, self.fails = 0, self.fails + 1
        if self.fails >= 3 and self.limit > 1:  # ponytail: 연속 3번 실패면 절반으로. 서버별 학습은 하지 않는다
            self.limit, self.fails = max(1, self.limit // 2), 0
            self.log("서버 응답이 늦어 동시 접속을 %d개로 줄입니다" % self.limit)

    async def new_page(self, ctx):
        page = await ctx.new_page()
        self.own.add(page)
        page.adg_dialogs = []
        page.on("dialog", lambda d: self.on_dialog(page, d))
        return page

    def on_dialog(self, page, d):
        page.adg_dialogs.append(d.message)
        if (page.url, d.message) not in self.dialogs:
            self.dialogs.append((page.url, d.message))
            self.log("경고창: %s (%s)" % (d.message.strip()[:60], page.url))
        asyncio.ensure_future(with_timeout(d.dismiss(), 3))

    async def open(self, page, url, post):
        """GET으로 연다. POST로만 열리는 글은 같은 파라미터의 GET이 실패할 때만 POST로 연다 (research/03 §8)."""
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if post and (resp is None or resp.status >= 400):
            action, body = post
            async def as_post(route):
                await route.continue_(method="POST", post_data=body, headers={
                    **route.request.headers, "content-type": "application/x-www-form-urlencoded"})
            await page.route(action, as_post)
            try:
                resp = await page.goto(action, wait_until="domcontentloaded", timeout=15000)
            finally:
                await page.unroute(action, as_post)
        return resp

    async def visit(self, page, url, post, depth, mobile=False):
        page.adg_dialogs.clear()
        resp = await self.open(page, url, post)
        self.visited += 1
        ctype = resp.headers.get("content-type") or "html" if resp else ""
        if resp is None or resp.status >= 400 or "html" not in ctype:
            if norm(url) == self.start and resp is not None:
                self.start_fail = "HTTP %d" % resp.status if resp.status >= 400 else "웹 페이지가 아닌 파일(%s)" % ctype.split(";")[0]
            return
        m = META_REFRESH.search(await with_timeout(resp.text(), 5) or "")
        if m:
            self.push(urllib.parse.urljoin(resp.url, m.group(1).strip()), depth + 1, via=(url, "자동 이동(meta refresh)"))
        await with_timeout(page.wait_for_load_state("load"), 5)
        await with_timeout(page.evaluate(SETTLE_JS), 4)
        await with_timeout(asyncio.gather(*[f.wait_for_load_state("load") for f in page.frames]), 3)

        # 리다이렉트 뒤 최종 URL. POST로만 열리는 글은 GET이 되면 GET 표기, 안 되면 action URL (research/03 §8)
        final = minimize(page.url) if page.url.startswith("http") else url
        if not mobile and norm(final) != norm(url) and any(MOBILE_ONLY.search(m) for m in page.adg_dialogs):
            # "모바일 전용입니다" 경고 뒤 다른 곳으로 보냄: 모바일 화면으로 다시 열고, 같은 게시판 글도 처음부터 모바일로
            self.mobile |= {norm(url), section(url)}
            self.requeue(url, post, depth, 0)
            return
        if not self.in_scope(final):
            return  # 리다이렉트로 범위 밖으로 나감
        if post is None and norm(final) in self.canons:
            return  # 이미 기록한 페이지로 보내짐 ("잘못된 접근" 뒤 첫 화면 등)
        self.seen.add(norm(final))
        self.via.setdefault(norm(final), self.via.get(norm(url)))
        canon = await with_timeout(page.evaluate(
            "() => { const l = document.querySelector('link[rel=canonical]'); return l ? l.href : null }"), 3)
        if canon and self.in_scope(canon):
            final = minimize(canon)
            cs = urllib.parse.urlsplit(final)
            if norm(final) in self.canons and (cs.query or not re.fullmatch(r"/*(?:index\.\w+)?/*", cs.path)):
                return  # canonical이 같으면 같은 페이지 (P7). 모든 쪽이 첫 화면을 가리키는 잘못된 설정은 믿지 않는다
            self.seen.add(norm(final))
            self.via.setdefault(norm(final), self.via.get(norm(url)))

        text = await with_timeout(page.evaluate("() => document.documentElement.textContent"), 5) or ""
        h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
        if h in self.hashes:  # 같은 글이 다른 URL로 (꼬리표·세션 등): 대표 URL만 짧은 것으로 바꾼다
            r = self.results[self.hashes[h]]
            if len(final) < len(r["url"]):
                r["url"] = final
            return

        caught, state = [], {"armed": False, "aborted": False}

        async def intercept(route):
            r = route.request
            if state["armed"] and r.is_navigation_request():
                state["aborted"] = True  # iframe 자체 이동도 막는다 (iframe 전용 페이지는 따로 출력하지 않음)
                if r.frame == page.main_frame:
                    caught.append((r.method, r.url, r.post_data))
                await route.abort()
            else:
                await route.continue_()

        async def act(frame_url, js, arg):
            """프레임에서 js(클릭)를 실행하고 상위 페이지 이동 요청을 가로챈다. 이동했으면 페이지를 다시 연다.
            반환: (가로챈 요청 또는 None, 페이지를 다시 열었는지)"""
            f = next((f for f in page.frames if f.url == frame_url), None)
            if f is None:
                return None, False
            caught.clear()
            before, state["aborted"], state["armed"] = page.url, False, True
            await with_timeout(f.evaluate(js, arg), 3)
            for _ in range(20):  # setTimeout 뒤 이동까지 1초 기다림
                if caught:
                    break
                await asyncio.sleep(0.05)
            state["armed"] = False
            got = caught[0] if caught else (("GET", page.url, None) if page.url != before else None)
            if state["aborted"] or page.url != before:
                try:  # abort하면 오류 페이지가 되므로 다시 연다
                    await self.open(page, url, post)
                except Exception:  # 오류 페이지로 가는 이동과 겹치면 끊긴다 ("interrupted by another navigation")
                    await asyncio.sleep(0.3)
                    await self.open(page, url, post)
                await with_timeout(page.wait_for_load_state("load"), 5)
                await with_timeout(page.evaluate(SETTLE_JS), 4)
                return got, True
            return got, False

        await page.route("**/*", intercept)
        try:
            await self.expand(page, act, depth, final)
            for f in page.frames:
                got = await with_timeout(f.evaluate(LINKS_JS), 5) or {}
                for u in got.get("links", []):
                    self.push(u, depth + 1, via=(final, "링크"))
                for js in got.get("scripts", []):
                    await self.js_links(page, js, depth, final)

            result = None
            if self.analyze:
                result = await self.analyze(page, final)
            self.hashes[h] = len(self.results)
            self.canons.add(norm(final))
            self.results.append({"url": final, "result": result, "path": self.path(url), "mobile": mobile})
            self.log("[%d] %s" % (len(self.results), final))

            await self.clicks(page, url, act, depth, final)
        finally:
            await with_timeout(page.unroute("**/*", intercept), 3)

    async def expand(self, page, act, depth, parent):
        """'더보기'·'댓글 더보기'처럼 같은 페이지에 내용을 덧붙이는 버튼을 내용이 안 늘 때까지 누른다 (research/03 §2).
        ponytail: 덧붙이는 방식만. 탭·댓글 쪽번호처럼 내용을 바꿔 끼우는 AJAX는 상태별 분석이 필요해서 안 함"""
        size = "() => document.documentElement.textContent.length"
        for _ in range(5):
            n = await with_timeout(page.evaluate(EXPAND_JS), 5) or []
            n = [k for k, text in n if not DANGER_LABEL.match(text)][:10]
            if not n:
                break
            before = await with_timeout(page.evaluate(size), 3)
            for k in n:
                got, reloaded = await act(page.main_frame.url, "(k) => { const e = document.querySelector('[data-adg-x=\"' + k + '\"]'); if (e) e.click(); }", k)
                if got:
                    self.add_request(got, depth + 1, (parent, "더보기 클릭"))
                if reloaded:
                    return  # 더보기가 실제로는 이동이었다: 링크로만 쓴다
            await with_timeout(page.evaluate(SETTLE_JS), 4)
            if await with_timeout(page.evaluate(size), 3) == before:
                break
        await with_timeout(page.evaluate("() => document.querySelectorAll('[data-adg-x]').forEach(e => e.removeAttribute('data-adg-x'))"), 3)

    async def js_links(self, page, js, depth, parent):
        """같은 도메인 외부 .js 파일 속 따옴표 문자열 경로 (파일마다 1번)"""
        if js in self.js_seen or not self.in_scope(js):
            return
        self.js_seen.add(js)
        text = await self.fetch(page.context, js) or ""
        for m in re.finditer(r"[\"'`]((?:https?:)?/[^\"'`\s<>]*)[\"'`]", text):
            self.push(urllib.parse.urljoin(page.url, m.group(1)), depth + 1, via=(parent, "스크립트 속 주소"))

    async def clicks(self, page, url, act, depth, parent):
        """모든 프레임의 onclick·javascript: 링크를 눌러 상위 페이지 이동 요청을 가로챈다.
        함수마다 1번만 누르고 나머지는 인자 치환 (research/03 §3-4). 배운 템플릿은 같은 패턴 페이지에서 재사용"""
        sig = signature(url)[0]
        budget = 30
        for furl in [f.url for f in page.frames]:
            f = next((f for f in page.frames if f.url == furl), None)
            cands = f and await with_timeout(f.evaluate(CANDS_JS, CAND), 5) or []
            groups = {}
            for i, (code, text) in enumerate(cands):
                if DANGER.search(code) or DANGER_LABEL.match(text) or LANG_CODE.search(code):
                    continue
                name, args = call_of(code)
                if name and not args and "search" in name.lower():
                    continue  # 빈 검색 버튼: "검색어를 입력하세요" 경고만 뜬다. 인자가 있으면 쪽 이동일 수 있어 누른다
                if name:
                    groups.setdefault(name, []).append((i, args))
            for name, members in groups.items():
                key = (sig, signature(furl)[0], name)
                if key not in self.templates:  # 처음 2개까지 눌러 보고, 이동이 잡힌 것만 템플릿으로 쓴다
                    for i, args in members[:2]:
                        if budget <= 0:
                            return
                        budget -= 1
                        got, _ = await act(furl, CLICK_JS, [CAND, i])
                        if got:
                            self.templates[key] = (got, args)
                            break
                tpl = self.templates.get(key)
                if not tpl:
                    continue
                req, args0 = tpl
                for i, args in members:
                    r = substitute(req, args0, args) if len(args) == len(args0) else None
                    if r is None and budget > 0:
                        budget -= 1
                        r, _ = await act(furl, CLICK_JS, [CAND, i])
                    if r:
                        self.add_request(r, depth + 1, (parent, "클릭(%s)" % name))

    def add_request(self, req, depth, via):
        method, u, body = req
        if not u.startswith("http"):
            return
        self.push(u, depth, body if method == "POST" and body else None, via)

    def path(self, url):
        """시작 주소부터 이 페이지까지 [[URL, 찾은 방법], ...]. 각 단계의 방법은 그 URL을 찾은 방법"""
        out, key = [], norm(url)
        for _ in range(15):  # ponytail: 깊이 15에서 자른다
            parent, how = self.via.get(key) or (None, "")
            out.append([url, how])
            if not parent or norm(parent) in {norm(u) for u, _ in out}:
                break
            url, key = parent, norm(parent)
        return out[::-1]


async def crawl(entry, analyze=None, workers=None, time_limit=20 * 60, log=print, ctl=None):
    """analyze(page, url)는 페이지가 다 그려진 뒤 탭을 넘겨받아 분석 결과를 돌려준다.
    반환: [{"url": 출력용 URL, "result": analyze 결과}] (같은 내용 페이지는 1개)
    ctl(dict)을 넘기면 ctl["crawler"]로 진행 상황(visited, heap, results)을 읽고 stop()으로 중단할 수 있다"""
    c = Crawler(entry, analyze, workers, time_limit, log)
    if ctl is not None:
        ctl["crawler"] = c
    return await c.run()


if __name__ == "__main__":  # python app/crawler.py <URL>
    sys.stdout.reconfigure(encoding="utf-8")
    for r in asyncio.run(crawl(sys.argv[1], log=lambda m: None)):
        print(r["url"])
