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
  // 타이머 안에서 다시 거는 200ms 이상 타이머(시계·롤링 배너의 반복)는 세지 않는다: 기다리면 끝없이 3초를 채운다 (research/14 §4)
  // 반복으로 확인된 타이머의 코드 지문은 sessionStorage에 남겨 같은 사이트 다음 페이지에서는 처음부터 안 센다
  const st = window.setTimeout, ct = window.clearTimeout, ids = new Set();
  let inCb = 0, rep = new Set();
  try { rep = new Set(JSON.parse(sessionStorage.getItem('__adgRep') || '[]')); } catch (e) {}
  const sig = f => typeof f === 'function' ? String(f).slice(0, 120) : String(f).slice(0, 120);
  window.__adgST = st; window.__adgT = ids;
  window.setTimeout = function (f, d, ...a) {
    const id = st.call(window, function (...x) {
      ids.delete(id); inCb++;
      try { return typeof f === 'function' ? f.apply(this, x) : (0, eval)(f); } finally { inCb--; }
    }, d, ...a);
    if (inCb && d >= 200 && !rep.has(sig(f))) {
      rep.add(sig(f)); try { sessionStorage.setItem('__adgRep', JSON.stringify([...rep].slice(-50))); } catch (e) {}
    }
    if (!(d > 3000) && !(d >= 200 && (inCb || rep.has(sig(f))))) ids.add(id);
    return id;
  };
  window.clearTimeout = function (id) { ids.delete(id); return ct.call(window, id); };
  // 무한 스크롤 단서: scroll 리스너나 IntersectionObserver를 쓰는 페이지만 바닥까지 스크롤해 본다
  const ael = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (t, ...a) {
    if (t === 'scroll' || t === 'wheel') window.__adgScroll = true;
    // 클릭 리스너가 걸린 목록 행·버튼(addEventListener로 연결한 글 이동): 클릭 후보로 표시
    // 링크는 다른 주소로 가는 href가 없을 때만 (#, javascript:void(0), 없음). href 있는 링크는 링크로 모은다
    if (t === 'click' && this instanceof Element && (/^(TR|LI|TD|DIV|SPAN|DT|DD|ARTICLE|BUTTON)$/.test(this.tagName) ||
        this.tagName === 'A' && /^\s*(#|javascript:|$)/i.test(this.getAttribute('href') || ''))) this.setAttribute('data-adg-click', '');
    return ael.call(this, t, ...a);
  };
  if (window.IntersectionObserver) { const IO = window.IntersectionObserver;
    window.IntersectionObserver = function (...a) { window.__adgScroll = true; return new IO(...a); };
    window.IntersectionObserver.prototype = IO.prototype; }
  // loading="lazy" iframe·img를 바로 불러온다 (안 그러면 프레임 evaluate가 무한 대기)
  const eager = n => { if (n.nodeType === 1) for (const e of [n, ...n.querySelectorAll('[loading]')]) if (e.loading === 'lazy') e.loading = 'eager'; };
  new MutationObserver(ms => { for (const m of ms) m.addedNodes.forEach(eager); }).observe(document, { childList: true, subtree: true });
})();
"""

# 요소가 새로 붙는 변화가 300ms 없고 대기 중인 짧은 타이머가 없을 때까지 (최대 3초)
# 글자·속성만 바뀌는 변화(시계 숫자, 롤링 배너의 위치)는 안 센다: 끝나지 않는다 (research/14 §4)
SETTLE_JS = r"""() => new Promise(res => {
  let last = Date.now(); const t0 = last, st = window.__adgST || setTimeout;
  const mo = new MutationObserver(ms => { if (ms.some(m => [...m.addedNodes].some(n => n.nodeType === 1))) last = Date.now(); });
  mo.observe(document, { subtree: true, childList: true });
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
  // 쪽 이동 폼: 글을 쓰는 칸 없이 숨은 값·select·버튼만 있는 폼. GET은 select 값마다 주소로, POST는 본문과 함께 (research/14 §3-5)
  const posts = [];
  const form = f => {
    const method = (f.getAttribute('method') || 'get').toLowerCase(), action = f.getAttribute('action') || location.href;
    if (method === 'get') add(action);
    const els = [...f.elements].filter(x => x.name && !x.disabled);
    if (!els.length || els.some(x => x.tagName === 'TEXTAREA' || (x.tagName === 'INPUT' && !/^(hidden|submit|button|image|radio|checkbox)$/.test(x.type)))) return;
    const base = els.filter(x => x.tagName !== 'SELECT' && !/^(submit|button|image)$/.test(x.type) && (!/^(radio|checkbox)$/.test(x.type) || x.checked)).map(x => [x.name, x.value]);
    const sel = els.find(x => x.tagName === 'SELECT');
    const combos = sel ? [...sel.options].slice(0, 50).map(o => base.concat([[sel.name, o.value]])) : [base];
    for (const c of combos) {
      const q = new URLSearchParams(c).toString();
      if (method === 'get') { const u = abs(action); if (u) { const x = new URL(u); x.search = q; out.add(x.href); } }
      else if (method === 'post') { const u = abs(action); if (u) posts.push([u, q]); }
    }
  };
  const walk = root => {
    for (const e of root.querySelectorAll('a[href],area[href],link[rel~=next][href],link[rel~=prev][href],[data-href],[data-url],form,meta[http-equiv],[onclick],select[onchange]')) {
      const t = e.tagName;
      if (t === 'A' || t === 'AREA') { if (!/^(ko|$)/i.test(e.getAttribute('hreflang') || '')) continue; add(e.getAttribute('href')); }
      else if (t === 'LINK') add(e.getAttribute('href'));
      else if (t === 'FORM') form(e);
      else if (t === 'SELECT') { if (/location|href|open\(/.test(e.getAttribute('onchange'))) for (const o of e.options) if (o.value) add(o.value); }
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
  return { links: [...out], posts, scripts: [...document.querySelectorAll('script[src]')].map(s => s.src) };
}"""

SIZE_JS = "() => document.documentElement.textContent.length"
# 화면 내용 지문: 글자 수가 같은 쪽 교체(글 1-1 → 글 2-1)도 잡는다
SIG_JS = """() => { const t = document.documentElement.textContent; let h = 0;
  for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0; return t.length + ':' + h; }"""

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

CAND = '[onclick],a[href^="javascript:" i],[data-adg-click]'
CANDS_JS = r"""(sel) => [...document.querySelectorAll(sel)].map(e => {
  const h = e.getAttribute('href') || '';
  let js = ''; try { js = /^javascript:/i.test(h) ? decodeURIComponent(h.slice(11)) : ''; } catch (x) {}
  js = js.replace(/^\s*(void\s*\(?\s*0\s*\)?|return\s+false)?\s*;?\s*$/i, '');  // javascript:void(0)은 코드 없음: 리스너만 있는 링크
  const code = (e.getAttribute('onclick') || '') + ';' + js;
  // 코드 없이 리스너만 있으면 태그·클래스로 묶는다
  return [code === ';' && e.hasAttribute('data-adg-click') ? '@ev:' + e.tagName + '.' + (e.classList[0] || '') : code,
          (e.textContent || '').trim().slice(0, 40)];
})"""
CLICK_JS = "([sel, i]) => { const e = document.querySelectorAll(sel)[i]; if (e) e.click(); }"

# 누르거나 방문하면 안 되는 것 (research/03 §1)
# URL·onclick 코드는 영어 토큰으로, 버튼 글자는 이름 전체가 위험 단어일 때만 ("전입신고 안내"·"추천 도서"는 통과)
# 지우기·로그아웃은 부분 일치로, 쓰기·인쇄 등은 낱말일 때만 (/updates/, /blueprint/, /writer/는 통과. research/14 §3-5)
# ctx.route에도 쓰므로 JS 정규식으로도 옮겨지는 문법만 쓴다
DANGER = re.compile(r"delete|remove|logout|logoff|signout|withdraw|"
                    r"(?<![a-z])(?:update|write|insert|vote|print|modify)(?:form|proc|ok|act|action|article|post|comment|confirm|exec|submit)?(?![a-z])|"
                    r"act=disp\w*(?:delete|modify|write|reply)|act=dispmember|sns_send|sharer?\.php|"
                    # 쿼리 값이 동작 줄임말: ?mode=del&idx=3, ?act=edit (research/17 문제 3, 비밀번호 없는 게시판이면 GET으로 지워진다)
                    r"[?&](?:mode|act|cmd|action|proc|job|type)=(?:del|delete|edit|modify|update|write|reply|reg|regist)(?=&|$)", re.I)
# 함수명의 동작 줄임말: fnDel(3)·goEdit()·doReg3()·fn_del(). 대소문자로 낱말을 가른다 (model·Delivery·showEditor는 통과)
DANGER_FN = re.compile(r"(?:^|_)(?:del|edit|reg)(?![a-z])|(?:Del|Edit|Reg)(?![a-z])")
DANGER_LABEL = re.compile(r"^\s*(?:삭제|수정|등록|글쓰기|쓰기|답변|답글|로그아웃|탈퇴|추천|신고|스크랩|인쇄|검색|delete|edit|write|"
                          r"logout|print)(?:하기)?\s*$", re.I)
INERT_FN = {"void", "blur", "focus", "print", "close", "alert", "confirm", "back", "forward", "go", "reload",
            "preventDefault", "stopPropagation", "return", "toggle", "toggleClass", "addClass", "removeClass", "scrollTo",
            "if", "for", "while", "switch", "function"}  # if(this.checked) 같은 문법을 함수로 읽지 않게
# 첨부파일 내려받기 주소 (그누보드 download.php, 전자정부 FileDown.do 등)와 외부 링크 중계(그누보드 bbs/link.php): 페이지가 아니다
DOWNLOAD = re.compile(r"download\.(?:php|do|jsp|aspx?)|file_?down|bbs/link\.php", re.I)
SKIP_EXT = re.compile(r"\.(pdf|hwp|hwpx|docx?|xlsx?|pptx?|zip|rar|7z|gz|tar|jpe?g|png|gif|bmp|svg|webp|ico|mp[34]|avi|mov|"
                      r"wmv|wav|css|js|json|xml|txt|exe|msi|apk|woff2?|ttf)$", re.I)
# 쿼리 값의 확장자: 이미지·영상은 늘 건너뛰고(view_image.php?fn=a.jpg), 문서는 내려받기 경로일 때만 (preview?file=a.hwp는 HTML 미리보기)
MEDIA_EXT = re.compile(r"\.(jpe?g|png|gif|bmp|svg|webp|ico|mp[34]|avi|mov|wmv|wav)$", re.I)
DOWNLOAD_PATH = re.compile(r"down|file|attach|get_?file", re.I)
# 글 내용을 바꾸지 않는 정렬·검색·분류 꼬리표 (그누보드 $qstr·device, 전자정부 search*, XE·라이믹스)
NOISE = {"device", "sca", "sfl", "stx", "sst", "sod", "sop", "spt", "searchcnd", "searchwrd", "searchkeyword", "searchcondition",
         "searchtype", "searchword", "sort", "order", "orderby", "sortorder", "sortfield",
         "sort_index", "order_type", "liststyle", "search_target", "search_keyword"}
# 세션 언어를 바꾸는 주소·버튼: 누르면 이후 페이지가 다른 언어로 나온다 (research/13 §5, 사이트 E doChangeLangType)
LANG_URL = re.compile(r"[?&](?:lang|lang_type|locale|language)=(?!ko)", re.I)
LANG_CODE = re.compile(r"lang|locale", re.I)
PAGE_KEYS = {"page", "pageindex", "pageno", "pagenum", "currentpage", "curpage"}
SEARCH_KEYS = {"q", "query", "keyword", "kwd", "searchwrd", "searchkeyword", "search", "sw", "stx", "word", "skeyword", "searchword"}
ID_KEYS = {"id", "wr_id", "nttid", "no", "idx", "seq", "document_srl", "articleno", "bno", "num", "p", "nttsn", "postid"}
DATE_KEYS = {"ym", "yyyymm", "year", "month", "day", "date", "yy", "mm", "dd", "caldate", "sdate", "edate", "week"}
DATE_VAL = re.compile(r"^\d{4}[-./]?\d{2}(?:[-./]?\d{2})?$")
MOBILE_ONLY = re.compile(r"모바일|mobile|스마트폰", re.I)
# 본문 해시용 글자: 머리·메뉴·꼬리·옆 영역과 스크립트를 뺀다 (Bar-Yossef 2002 템플릿 제외의 간이판, research/13 §4-2)
BODY_JS = r"""() => {
  const skip = 'script,style,noscript,template,header,nav,footer,aside,[role=navigation],[role=banner],[role=contentinfo]';
  const w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
    n => n.nodeType === 1 && n.matches(skip) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT);  // 제외 영역은 하위째 건너뜀
  let t = '';
  while (w.nextNode()) if (w.currentNode.nodeType === 3) t += w.currentNode.nodeValue;
  return [t.replace(/\s+/g, ' ').trim(), document.documentElement.textContent];
}"""
# 원본 HTML의 meta refresh: 0초 이동은 분석 도중 페이지를 바꿔 DOM에서 못 읽을 수 있다
META_REFRESH = re.compile(r"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[^>]*content\s*=\s*[\"']?\s*\d*\s*;?\s*url\s*=\s*([^\"'>]+)", re.I)
NET_ERR = re.compile(r"Timeout|net::ERR_")
# 서버가 버거워서 생긴 실패가 아닌 것: 다른 호스트로 보내진 뒤 DNS·인증서 실패, 리다이렉트 반복(사이트 설정 오류), 차단한 요청 (P11)
NOT_SERVER = re.compile(r"ERR_NAME_NOT_RESOLVED|ERR_TOO_MANY_REDIRECTS|ERR_CERT|ERR_ABORTED|ERR_BLOCKED|ERR_UNKNOWN_URL_SCHEME|ERR_INVALID")
# 패턴당 상한. 날짜형(무한 달력)은 넘으면 버리고, 그 밖은 CAP_PATTERN을 넘으면 맨 뒤로 미뤘다가 CAP_HARD에서 버린다 (research/03 결론 5)
CAP_DATE, CAP_PATTERN, CAP_HARD = 24, 500, 3000


def norm(u):
    """중복 판정 키 (모집요강 12쪽 + ;jsessionid 제거 + 쿼리가 있는 /index.php는 디렉터리와 같음)."""
    s = urllib.parse.urlsplit(u)
    path = re.sub(r";jsessionid=[^/?#]*", "", s.path, flags=re.I).rstrip("/") or "/"
    if s.query and path.endswith("/index.php"):  # XE·라이믹스 /?mid=…와 /index.php?mid=…는 같은 페이지 (P7)
        path = path[:-10] or "/"
    qs = urllib.parse.parse_qsl(s.query, keep_blank_values=True)
    d = dict(qs)
    if "mid" in d and set(d) <= {"mid", "document_srl"} and len(qs) == len(d):
        # XE·라이믹스 고유 주소: ?mid=board&document_srl=123 ≡ /board/123 (canonical로 합치기 전에 같은 키로)
        path, qs = path.rstrip("/") + "/" + "/".join(v for v in (d["mid"], d.get("document_srl")) if v), []
    q = urllib.parse.urlencode(sorted(qs))
    return "%s%s%s" % (s.netloc.lower(), path, "?" + q if q else "")


def qkey(x):
    """쿼리 조각 'k=v'의 키"""
    return urllib.parse.unquote_plus(x.partition("=")[0])


def minimize(u, extra=None):
    """방문·출력용 URL: # 제거, ;jsessionid 제거, 꼬리표 제거, 글 ID가 있으면 쪽번호 제거.
    extra(POST 본문)는 쿼리에 합치고 빈 값은 버린다. 남는 조각은 원래 표기 그대로 (%20→+, ?flag→?flag= 같은 재인코딩 없음, todo/12)"""
    s = urllib.parse.urlsplit(u)
    path = re.sub(r";jsessionid=[^/?#]*", "", s.path, flags=re.I)
    q = [x for x in s.query.split("&") if x]
    if extra is not None:
        body = [x for x in extra.split("&") if x]
        keys = {qkey(x) for x in body}
        q = [x for x in q if qkey(x) not in keys] + body
        q = [x for x in q if x.partition("=")[2] != ""]
    keys = {qkey(x).lower() for x in q}
    # 쪽번호는 글 ID가 있을 때만 뺀다. 게시판 ID로도 쓰는 id는 상세 경로(view·read·detail)일 때만 (?id=free&page=2는 목록 2쪽)
    post = keys & (ID_KEYS - {"id"}) or "id" in keys and re.search(r"view|read|detail", path, re.I)
    drop = NOISE | (PAGE_KEYS if post else set())
    q = [x for x in q if qkey(x).lower() not in drop]
    return urllib.parse.urlunsplit((s.scheme, s.netloc, path, "&".join(q), ""))


def section(u):
    """게시판 단위 키: 글 ID·쪽번호를 뺀 norm (같은 게시판 글은 같은 키)"""
    s = urllib.parse.urlsplit(minimize(u))
    q = [(k, v) for k, v in urllib.parse.parse_qsl(s.query, keep_blank_values=True) if k.lower() not in ID_KEYS | PAGE_KEYS]
    return norm(urllib.parse.urlunsplit((s.scheme, s.netloc, s.path, urllib.parse.urlencode(q), "")))


def signature(u):
    s = urllib.parse.urlsplit(u)
    q = urllib.parse.parse_qsl(s.query, keep_blank_values=True)
    is_date = any(k.lower() in DATE_KEYS or DATE_VAL.match(v) for k, v in q)
    # 경로 속 글 번호(/review/41428, XE /jayoo/400570)는 쿼리의 id처럼 같은 패턴으로 묶는다: 글마다 버튼을 다시 누르지 않게 (research/17 문제 2)
    return (s.netloc.lower(), re.sub(r"/\d+(?=/|$)", "/N", s.path), tuple(sorted({k for k, _ in q}))), is_date


def priority(u):
    s = urllib.parse.urlsplit(u.lower())
    keys = {k for k, _ in urllib.parse.parse_qsl(s.query)}
    # 검색어 붙은 주소: 인기 검색어 위젯 등으로 사이트 안에 퍼진 검색 반사 광고(ISAP)를 먼저 본다 (research/11 S-1)
    # 경로 끝 숫자(/help/129462, XE /jayoo/400570)도 글. review·preview의 view는 글 표시가 아니다 (research/17 문제 2)
    if keys & ID_KEYS or keys & SEARCH_KEYS or re.search(r"(?<!re)view|read|detail|article|/\d+/?$", s.path):
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


class Throttled(Exception):
    """서버가 429·503으로 요청을 줄여 달라고 했다. 인자: 기다릴 초"""


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
        self.canon_of = {}  # canonical(norm) → 처음 그것을 가리킨 주소
        # 무관한 파라미터 학습 (research/13 §4-4): 같은 페이지 키(본문 해시·canonical) → 방문 주소들, 근거, 배운 것
        self.groups, self.evidence, self.learned = {}, {}, set()  # learned: (호스트, 경로, 파라미터)
        self.templates = {}  # (페이지 패턴, 함수명) → (요청, 인자) 또는 None(이동 없음)
        self.ev_miss = {}  # 리스너 묶음(@ev:태그.클래스) → 눌러도 얻은 게 없던 페이지 수
        # 인자 없는 함수: 처음 눌러 본 (페이지 패턴, 결과). 다른 패턴에서도 결과가 같으면 사이트 공통 버튼(머리말·꼬리말)으로 보고 더 안 누른다
        # 결과로 비교한다: moveList()처럼 인자가 없어도 페이지 안 폼 값을 읽어 게시판마다 다른 곳으로 가는 함수가 있다 (research/17 문제 2)
        self.fn_first, self.fn_common = {}, set()
        self.visited = 0
        self.errors = []
        self.own = set()
        self.js_seen = set()
        self.dropped = 0
        self.mobile = set()  # 모바일 화면으로만 열리는 주소·게시판 (norm, section)
        self.retried = set()
        self.limit, self.fails, self.oks = self.workers, 0, 0  # 지금 쓰는 병렬 수, 연속 실패·성공 수
        self.shared = None  # 처음에 모든 워커가 같이 쓰는 컨텍스트
        self.pause_until = 0  # 429·503을 받으면 모든 워커가 이 시각까지 새 페이지를 꺼내지 않는다
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
        # www.x.kr로 넣었는데 x.kr로 보내는 사이트: 맨도메인도 범위 안
        return s.scheme in ("http", "https") and (s.netloc.lower() == self.netloc or host == self.base or host.endswith("." + self.base))

    def requeue(self, url, post, depth, prio):
        self.seq += 1
        heapq.heappush(self.heap, (prio, depth, self.seq, url, post))

    def push(self, url, depth, body=None, via=(None, "링크")):
        post = (url, body) if body is not None else None  # POST로만 열리면 원래 action과 본문을 남겨 둔다
        url = minimize(url, body)
        if self.learned and body is None:  # 내용을 안 바꾼다고 배운 파라미터는 뺀다
            s = urllib.parse.urlsplit(url)
            q = [x for x in s.query.split("&") if x]
            q2 = [x for x in q if (s.netloc.lower(), s.path, qkey(x)) not in self.learned]
            if len(q2) != len(q):
                url = urllib.parse.urlunsplit((s.scheme, s.netloc, s.path, "&".join(q2), ""))
        key = norm(url)
        if key != self.start:
            s = urllib.parse.urlsplit(url)
            # 쿼리 값의 확장자도 본다: view_image.php?fn=a.jpg (P12)
            if not self.in_scope(url) or SKIP_EXT.search(s.path) or LANG_URL.search(url) or \
                    any(MEDIA_EXT.search(v) or SKIP_EXT.search(v) and DOWNLOAD_PATH.search(s.path)
                        for _, v in urllib.parse.parse_qsl(s.query)):
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
        if n > (CAP_DATE if is_date else CAP_HARD):
            self.dropped += 1
            return
        self.seq += 1
        # 같은 패턴 주소가 쌓일수록 30개마다 한 단계 뒤로: 글 많은 게시판 하나가 시간을 다 쓰고 다른 게시판을 못 보는 것을 막는다 (research/17 문제 2)
        # 첫 화면에서 바로 이어진 주소(깊이 1)는 사이트 메뉴: 이름에 list·board가 없는 게시판(/help)도 목록과 같은 순서로 본다
        prio = min(priority(url), 2) if depth <= 1 else priority(url)
        heapq.heappush(self.heap, (prio + min(n // 30, 5) + (10 if n > CAP_PATTERN else 0), depth, self.seq, url, post))

    def same(self, url, key):
        """url이 key(본문 해시·canonical)로 본 페이지와 같다. 같은 페이지의 주소들이 파라미터 하나만 다르면 그 파라미터를 근거로 모으고,
        서로 다른 페이지 2곳에서 근거가 나오면 그 경로에서는 무관한 파라미터로 배운다 (Koppula 외 WSDM 2010의 온라인 축소판).
        숫자 값·ID·쪽·날짜 키는 배우지 않는다. 같은 안내 화면(삭제·권한)을 여러 주소가 보여도 근거는 1곳으로만 센다"""
        g = self.groups.setdefault(key, [])
        if url in g:
            return
        g.append(url)
        if len(g) < 2:
            return
        parts = [(s.netloc.lower(), s.path, dict(urllib.parse.parse_qsl(s.query, keep_blank_values=True)))
                 for s in map(urllib.parse.urlsplit, g)]
        base, diff = parts[0], set()
        for x in parts[1:]:
            diff |= {k for k in set(x[2]) | set(base[2]) if x[2].get(k) != base[2].get(k)} if x[:2] == base[:2] else {None, ""}
        if len(diff) != 1:
            for ev in self.evidence.values():
                ev.discard(key)  # 여러 파라미터가 다른데도 같은 화면: 안내 화면일 수 있어 근거에서 뺀다
            return
        p = diff.pop()
        if p.lower() in ID_KEYS | PAGE_KEYS | DATE_KEYS or any(x[2].get(p, "").isdigit() for x in parts):
            return
        k = base[:2] + (p,)
        ev = self.evidence.setdefault(k, set())
        ev.add(key)
        if len(ev) >= 2 and k not in self.learned:
            self.learned.add(k)
            self.log("꼬리표 '%s'는 내용을 바꾸지 않아 이후 주소에서 뺍니다 (%s)" % (p, base[1]))

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
            # 처음엔 컨텍스트 하나를 같이 쓴다: 새 컨텍스트 여럿이 동시에 붙으면 페이지를 안 주는 서버가 있다 (bd.kma.go.kr: 6개면 4개 시간 초과)
            self.shared = await self.new_ctx()
            ctxs = [self.shared] * self.workers
            self.push(self.entry, 0, via=(None, "시작 주소"))
            await self.seed(ctxs[0])
            tasks = [asyncio.create_task(self.worker(c, i)) for i, c in enumerate(ctxs)]
            # 하드 데드라인: 시간이 다 되면 진행 중인 페이지도 끊고 모은 결과만 돌려준다
            _, pending = await asyncio.wait(tasks, timeout=max(1, self.deadline - time.monotonic()) + 30)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await with_timeout(browser.close(), 10)
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
            if n >= self.limit or time.monotonic() < self.pause_until:  # 서버가 버거워해서 쉬는 워커
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
            except Throttled as e:
                # 요청 과다(429)·일시 중단(503): 다 같이 쉬고, 병렬을 반으로, 이 주소는 1번 더 (research/17 문제 5)
                self.pause_until = max(self.pause_until, time.monotonic() + e.args[0])
                self.limit = max(1, self.limit // 2)
                self.log("서버가 요청을 줄여 달라고 해서 %d초 쉬고 동시 접속을 %d개로 줄입니다 (%s)" % (e.args[0], self.limit, url))
                if norm(url) not in self.retried:
                    self.retried.add(norm(url))
                    self.requeue(url, post, depth, prio)
                else:
                    self.errors.append((url, "HTTP 429/503 (서버가 요청을 줄여 달라고 함)"))
            except Exception as e:
                r = repr(e)
                self.errors.append((url, r[:200]))
                m = re.search(r"net::\w+|Timeout", r)
                self.log("열지 못함(%s): %s" % (m.group(0) if m else type(e).__name__, url))
                await with_timeout(page.close(), 3)
                if "ERR_TOO_MANY_REDIRECTS" in r and norm(url) == self.start:
                    # 서버 한 대가 자기 자신으로 301을 보내는 사이트: 새 연결(새 컨텍스트)로 다른 서버에 붙어 2번 더 (research/17 문제 4)
                    # 큐에 다시 넣지 않고 이 워커가 바로 연다: 다른 워커는 같은 연결을 쓰고, 큐가 비면 먼저 끝나 버린다
                    for _ in range(2):
                        if ctx is not self.shared:
                            await with_timeout(ctx.close(), 5)
                        ctx = await self.new_ctx(mobile)
                        page = await self.new_page(ctx)
                        self.log("시작 주소를 새 연결로 다시 엽니다: %s" % url)
                        try:
                            await asyncio.wait_for(self.visit(page, url, post, depth, mobile), 60)
                            self.ok()
                            break
                        except Exception as e2:
                            if "ERR_TOO_MANY_REDIRECTS" not in repr(e2):
                                break
                    tabs[mobile] = (ctx, page)
                    continue
                if NET_ERR.search(r) and not NOT_SERVER.search(r):
                    # 끝나지 않는 요청이 서버 세션을 잠갔을 수 있다: 이 워커만 쿠키가 새로운 자기 컨텍스트로 옮긴다
                    if ctx is not self.shared:  # 같이 쓰는 컨텍스트는 다른 워커가 쓰고 있어 닫지 않는다
                        await with_timeout(ctx.close(), 5)
                    ctx = await self.new_ctx(mobile)
                    self.fail()
                    # 서버 전체가 힘든 때(연결 실패, 연속 실패)만 나중에 1번 더. 혼자 멈추는 함정 페이지는 다시 기다리지 않는다
                    if ("net::ERR_" in r or self.fails >= 2) and norm(url) not in self.retried:
                        self.retried.add(norm(url))
                        self.requeue(url, post, depth, prio + 10)
                tabs[mobile] = (ctx, await self.new_page(ctx))  # 멈춘 탭은 버리고 새로 연다
            finally:
                self.active -= 1
        for c, _ in tabs.values():
            if c is not self.shared:
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
        t0 = time.monotonic()
        page.adg_dialogs.clear()
        resp = await self.open(page, url, post)
        self.visited += 1
        ctype = resp.headers.get("content-type") or "html" if resp else ""
        if resp is not None and resp.status in (429, 503):
            ra = (resp.headers.get("retry-after") or "").strip()
            raise Throttled(min(60, int(ra)) if ra.isdigit() else 30)
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
        final = minimize(page.url) if page.url.startswith("http") else url  # 중복 판정 키용
        shown = page.url.split("#")[0] if page.url.startswith("http") else url  # 출력 주소: 실제로 연 주소에서 #만 뺀다 (todo/12 결정)
        if not mobile and norm(final) != norm(url) and any(MOBILE_ONLY.search(m) for m in page.adg_dialogs):
            # "모바일 전용입니다" 경고 뒤 다른 곳으로 보냄: 모바일 화면으로 다시 열고, 같은 게시판 글도 처음부터 모바일로
            self.mobile |= {norm(url), section(url)}
            self.requeue(url, post, depth, 0)
            return
        if not self.in_scope(final):
            return  # 리다이렉트로 범위 밖으로 나감
        if post is None and norm(final) in self.canons:
            return  # 이미 기록한 페이지로 보내짐 ("잘못된 접근" 뒤 첫 화면 등)
        landed = final
        self.seen.add(norm(final))
        self.via.setdefault(norm(final), self.via.get(norm(url)))
        canon = await with_timeout(page.evaluate(
            "() => { const l = document.querySelector('link[rel=canonical]'); return l ? l.href : null }"), 3)
        cs = urllib.parse.urlsplit(minimize(canon)) if canon and self.in_scope(canon) else None
        # 모든 쪽이 첫 화면을 가리키는 잘못된 canonical은 중복 판정에도, 결과 주소에도 쓰지 않는다
        # 글 ID가 다른 여러 주소가 같은 canonical(목록 등)을 가리키면 잘못 쓴 canonical: 글마다 따로 기록한다
        ids = lambda u: sorted((k.lower(), v) for k, v in urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query) if k.lower() in ID_KEYS)  # noqa: E731
        if cs and (cs.query or not re.fullmatch(r"/*(?:index\.\w+)?/*", cs.path)) and \
                not (ids(url) and ids(self.canon_of.setdefault(norm(minimize(canon)), url)) not in ([], ids(url))):
            final = minimize(canon)
            ckey = ("c", norm(final))
            if post is None:
                self.same(url, ckey)
            if norm(final) in self.canons:
                return  # canonical이 같으면 같은 페이지 (P7)
            self.canons.add(norm(final))
            self.seen.add(norm(final))
            self.via.setdefault(norm(final), self.via.get(norm(url)))

        if post is None:  # 기록하기 전(분석·클릭에 몇 초)에 먼저 차지한다: 동시에 같은 곳으로 보내진 워커가 겹치지 않게
            self.canons.add(norm(landed))
        body, full = await with_timeout(page.evaluate(BODY_JS), 5) or ("", "")
        # 본문이 거의 없으면(머리·꼬리만 있는 화면) 전체 글자로: 서로 다른 짧은 화면을 하나로 합치지 않게
        h = hashlib.sha1((body if len(body) >= 100 else "\0" + full).encode("utf-8", "replace")).hexdigest()
        if post is None:
            self.same(url, ("h", h))
        if h in self.hashes:  # 같은 글이 다른 URL로 (꼬리표·세션 등): 대표 URL만 짧은 것으로 바꾼다
            r = self.results[self.hashes[h]]
            # POST로 연 주소(action, 쿼리 없음)는 대표로 안 쓴다: 같은 목록의 GET 주소에서 쿼리가 빠진다
            # POST로 먼저 기록된 글은 GET 주소로. 쿼리를 통째로 잃는 짧은 주소(…List.do?bbsId=X → …List.do)는 대표로 안 쓴다
            shorter = len(final) < len(r["key"]) and (urllib.parse.urlsplit(final).query or not urllib.parse.urlsplit(r["key"]).query)
            better = post is None and (r.get("post") or shorter)
            if better and not any(norm(x["key"]) == norm(final) for x in self.results):
                r["url"], r["key"], r["post"] = shown, final, False  # 다른 결과가 이미 쓰는 주소로는 바꾸지 않는다 (결과 주소가 겹치면 한 쪽이 덮인다)
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

        async def reopen():
            try:  # abort하면 오류 페이지가 되므로 다시 연다
                await self.open(page, url, post)
            except Exception:  # 오류 페이지로 가는 이동과 겹치면 끊긴다 ("interrupted by another navigation")
                await asyncio.sleep(0.3)
                await self.open(page, url, post)
            await with_timeout(page.wait_for_load_state("load"), 5)
            await with_timeout(page.evaluate(SETTLE_JS), 4)

        async def act(frame_url, js, arg, watch=None):
            """프레임에서 js(클릭)를 실행하고 상위 페이지 이동 요청을 가로챈다. 이동했으면 페이지를 다시 연다.
            watch(결과 항목)를 주면 이동 없이 화면만 바뀐 클릭(AJAX 쪽 교체·탭·모달)에서 링크를 모으고 다시 분석해 합친 뒤 다시 연다.
            반환: (가로챈 요청 또는 None, 페이지를 다시 열었는지)"""
            f = next((f for f in page.frames if f.url == frame_url), None)
            if f is None:
                return None, False
            caught.clear()
            size0 = watch is not None and await with_timeout(page.evaluate(SIG_JS), 3)
            before, state["aborted"], state["armed"] = page.url, False, True
            await with_timeout(f.evaluate(js, arg), 3)
            for _ in range(20):  # setTimeout 뒤 이동까지 1초 기다림
                if caught:
                    break
                await asyncio.sleep(0.05)
            state["armed"] = False
            got = caught[0] if caught else (("GET", page.url, None) if page.url != before else None)
            if state["aborted"] or page.url != before:
                await reopen()
                return got, True
            if watch is not None:
                await with_timeout(page.evaluate(SETTLE_JS), 4)
                if size0 and await with_timeout(page.evaluate(SIG_JS), 3) != size0:
                    await self.harvest(page, depth, final, watch, "클릭 뒤 바뀐 화면")
                    await reopen()
                    return "changed", True
            return got, False

        await page.route("**/*", intercept)
        try:
            await self.expand(page, act, depth, final)
            for f in page.frames:
                got = await with_timeout(f.evaluate(LINKS_JS), 5) or {}
                self.take(got, depth, final, "링크")
                for js in got.get("scripts", []):
                    await self.js_links(page, js, depth, final)

            if page.url.startswith("http") and norm(minimize(page.url)) not in (norm(landed), norm(url)):
                # 분석 전에 JS가 다른 곳으로 보냈다 (지연 리다이렉트): 원래 주소로 기록하지 않고 새 주소를 연다
                self.push(page.url, depth + 1, via=(url, "자동 이동(스크립트)"))
                return
            result = None
            if self.analyze:
                result = await self.analyze(page, final)
            self.hashes[h] = len(self.results)
            self.canons.add(norm(final))
            self.results.append({"url": shown, "key": final, "result": result, "path": self.path(url), "mobile": mobile, "post": post is not None})
            self.log("[%d] %s" % (len(self.results), shown))

            # 클릭마다 다시 여는 느린 사이트는 30번이면 60초를 넘는다: 남은 시간만 누르고, 분석한 페이지를 실패로 세지 않는다
            await with_timeout(self.clicks(page, url, act, depth, final, self.results[-1] if self.results[-1]["key"] == final else None),
                               max(5, t0 + 50 - time.monotonic()))
        finally:
            await with_timeout(page.unroute("**/*", intercept), 3)

    async def expand(self, page, act, depth, parent):
        """'더보기'·'댓글 더보기'처럼 같은 페이지에 내용을 덧붙이는 버튼을 내용이 안 늘 때까지 누른다 (research/03 §2).
        ponytail: 덧붙이는 방식만. 탭·댓글 쪽번호처럼 내용을 바꿔 끼우는 AJAX는 상태별 분석이 필요해서 안 함"""
        size = SIZE_JS
        t_end = time.monotonic() + 8  # 회수 대신 시간으로 (댓글 더보기 6번 이상, research/14 §3-5)
        for _ in range(30):
            if time.monotonic() > t_end:
                break
            before = await with_timeout(page.evaluate(size), 3)
            # 바닥까지 스크롤: 무한 스크롤이 다음 묶음을 붙인다 (스크롤을 듣는 페이지만)
            scroll = await with_timeout(page.evaluate(
                "() => !!window.__adgScroll && (window.scrollTo(0, document.documentElement.scrollHeight), true)"), 2)
            n = await with_timeout(page.evaluate(EXPAND_JS), 5) or []
            n = [k for k, text in n if not DANGER_LABEL.match(text)][:10]
            if not n:
                if scroll:
                    await with_timeout(page.evaluate(SETTLE_JS), 4)
                    if await with_timeout(page.evaluate(size), 3) != before:
                        continue
                break
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

    def take(self, got, depth, parent, how):
        for u in got.get("links", []):
            self.push(u, depth + 1, via=(parent, how))
        for u, body in got.get("posts", []):
            self.push(u, depth + 1, body, via=(parent, "쪽 이동 폼(POST)"))

    async def harvest(self, page, depth, parent, entry, how):
        """지금 화면의 링크를 모으고 다시 분석해 entry 결과에 합친다 (location·technique이 같으면 1건)"""
        for f in page.frames:
            self.take(await with_timeout(f.evaluate(LINKS_JS), 5) or {}, depth, parent, how)
        if self.analyze and entry is not None:
            have = {(x["location"], x["technique"]) for x in entry["result"] or []}
            for x in await self.analyze(page, parent) or []:
                if (x["location"], x["technique"]) not in have:
                    entry["result"] = (entry["result"] or []) + [dict(x, reason=x.get("reason", "") + " (%s)" % how)]

    async def clicks(self, page, url, act, depth, parent, entry=None):
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
                if code.startswith("@ev:"):  # 리스너만 있는 요소: 묶음별로 하나씩 눌러 본다 (인자 치환 불가)
                    groups.setdefault(code, []).append((i, None))
                    continue
                name, args = call_of(code)
                if name and DANGER_FN.search(name.split(".")[-1]):
                    continue
                if name and not args and "search" in name.lower():
                    continue  # 빈 검색 버튼: "검색어를 입력하세요" 경고만 뜬다. 인자가 있으면 쪽 이동일 수 있어 누른다
                if name:
                    groups.setdefault(name, []).append((i, args))
            for name, members in groups.items():
                key = (sig, signature(furl)[0], name)
                if name.startswith("@ev:"):
                    if self.templates.get(key, 1) is None or self.ev_miss.get(name, 0) >= 2:
                        continue  # 이 패턴 페이지에서, 또는 다른 페이지 2곳에서 눌러 봐도 얻은 게 없던 묶음 (공통 영역의 펼침 버튼 등)
                    moved, miss = False, 0
                    for i, _ in members[:10]:  # ponytail: 묶음당 10개, 쪽마다 전체 클릭 예산 안에서
                        if budget <= 0:
                            return
                        budget -= 1
                        got = (len(self.seen), len((entry or {}).get("result") or []))
                        r, _ = await act(furl, CLICK_JS, [CAND, i], entry)  # 이동 없이 화면만 바뀌면(상세를 같은 화면에) 다시 분석해 합친다
                        if r == "changed" and got == (len(self.seen), len((entry or {}).get("result") or [])):
                            r = None  # 화면만 바뀌고 새 주소·검출 없음 (메뉴 펼침·탭 등)
                        if r:
                            moved = True
                            if r != "changed":
                                self.add_request(r, depth + 1, (parent, "클릭(목록 행)"))
                        elif not moved:
                            miss += 1
                            if miss >= 2:  # 처음 2개가 헛클릭이면 그만 (첫 행만 빈 상세일 수 있어 하나 더 본다)
                                break
                    self.templates[key] = 1 if moved else None
                    if not moved:
                        self.ev_miss[name] = self.ev_miss.get(name, 0) + 1
                    continue
                if key not in self.templates:  # 처음 2개까지 눌러 보고, 이동이 잡힌 것만 템플릿으로 쓴다
                    plain = not any(args for _, args in members)
                    if plain and name in self.fn_common:
                        continue
                    for i, args in members[:2]:
                        if budget <= 0:
                            return
                        budget -= 1
                        got, _ = await act(furl, CLICK_JS, [CAND, i], entry)
                        if got == "changed":  # AJAX로 화면만 바꾸는 함수(goPage 등): 나머지도 하나씩 누른다
                            self.templates[key] = "ajax"
                            break
                        if got:
                            self.templates[key] = (got, args)
                            break
                    tpl = self.templates.setdefault(key, None)  # 얻은 게 없으면 같은 패턴 페이지에서 다시 누르지 않는다
                    if plain and tpl != "ajax":  # 화면만 바꾸는 함수는 게시판마다 내용이 달라 공통으로 보지 않는다
                        first = self.fn_first.setdefault(name, (key, tpl))
                        if first[0] != key and first[1] == tpl:
                            self.fn_common.add(name)
                tpl = self.templates.get(key)
                if tpl == "ajax":
                    for i, _ in members[1:]:
                        if budget <= 0:
                            return
                        budget -= 1
                        await act(furl, CLICK_JS, [CAND, i], entry)
                    continue
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


if __name__ == "__main__" and sys.argv[1:] == ["--self-test"]:  # 무관한 파라미터 학습 확인
    c = Crawler("http://s.kr/", None, 1, 10, lambda m: None)
    c.same("http://s.kr/v?id=1&view=a", "K1"), c.same("http://s.kr/v?id=1&view=b", "K1")
    assert not c.learned  # 근거 1곳
    c.same("http://s.kr/v?id=2&view=a", "K2"), c.same("http://s.kr/v?id=2", "K2")
    assert c.learned == {("s.kr", "/v", "view")}
    c.push("http://s.kr/v?id=3&view=c", 1)
    assert c.heap[-1][3] == "http://s.kr/v?id=3"
    for u in ("http://s.kr/v?id=5", "http://s.kr/v?id=6"):  # 삭제 글 안내처럼 ID만 다른데 같은 화면
        c.same(u, "K3")
    for k, u in (("K4", "http://s.kr/b?cfile=a"), ("K4", "http://s.kr/b?cfile=b"), ("K4", "http://s.kr/b?cfile=c&idx=1"),
                 ("K5", "http://s.kr/b?cfile=d"), ("K5", "http://s.kr/b?cfile=e")):
        c.same(u, k)  # K4는 여러 파라미터가 다른 안내 화면이라 근거에서 빠짐 → cfile은 근거 1곳
    assert c.learned == {("s.kr", "/v", "view")}, c.learned
    w = Crawler("http://www.x.kr/", None, 1, 10, lambda m: None)  # www로 넣었는데 맨도메인으로 보내는 사이트
    assert w.in_scope("http://x.kr/a") and w.in_scope("http://m.x.kr/") and not w.in_scope("http://evilx.kr/")
    assert minimize("http://a/list?id=free&page=2") == "http://a/list?id=free&page=2"  # id가 게시판 ID인 목록 2쪽
    assert minimize("http://a/view?id=3&page=2") == minimize("http://a/b.php?wr_id=3&page=2").replace("b.php?wr_", "view?") == "http://a/view?id=3"
    assert minimize("http://a/s?q=a%20b&flag&x=%2F#f") == "http://a/s?q=a%20b&flag&x=%2F"  # 원래 표기 그대로
    for u in ("http://a/?pCode=request&mode=del&idx=436", "http://a/b.php?act=edit", "http://a/b?cmd=delete&no=1", "http://a/b?mode=reg"):
        assert DANGER.search(u), u
    for u in ("http://a/?mode=view&idx=1", "http://a/b?type=model", "http://a/b?mode=editorial", "http://a/delivery/1"):
        assert not DANGER.search(u), u
    assert signature("http://a/review/41428")[0] == signature("http://a/review/7600")[0] != signature("http://a/review")[0]
    assert call_of("if(this.checked) return confirm('x')") == (None, None)
    assert priority("http://a/help/129462") == priority("http://a/bbs/boardView.do") == 1 and priority("http://a/review") == 3
    for n in ("fnDel", "goEdit", "doReg3", "fn_del", "del", "fileDel", "board.fnDel"):
        assert DANGER_FN.search(n.split(".")[-1]), n
    for n in ("model", "goDelivery", "showEditor", "fn_region", "goRegular", "fn_view", "moveList"):
        assert not DANGER_FN.search(n), n
    print("통과")
elif __name__ == "__main__":  # python app/crawler.py <URL>
    sys.stdout.reconfigure(encoding="utf-8")
    for r in asyncio.run(crawl(sys.argv[1], log=lambda m: None)):
        print(r["url"])
