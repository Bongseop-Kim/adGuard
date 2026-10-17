"""crawlprobe: 도달 경로 테스트 사이트. python serve.py [--big]
본 도메인 127.0.0.1:8180, 다른 도메인 localhost:8181.
각 경로 끝 페이지에 `<div class="adx-RXX" style="display:none">... @test_rXX</div>` 숨김 광고.
"""
import json
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

H, X = "http://127.0.0.1:8180", "http://localhost:8181"
BIG = "--big" in sys.argv
TICK = "<script>(function t(){document.getElementById('clk').textContent=new Date().toLocaleTimeString();setTimeout(t,1000);})();</script>" if "--tick" in sys.argv else ""
NPOST, PER = 3000, 10


def ad(rid):
    return '<div class="adx-%s" style="display:none">먹튀검증 카지노 첫충 20%% 텔레그램 @test_%s</div>' % (rid, rid.lower())


def page(title, body, head=""):
    return ("<!doctype html><html lang=ko><head><meta charset=utf-8><title>%s</title>%s</head>"
            "<body><header><a href='/'>홈</a></header><main><h1>%s</h1>%s"
            "<p>이 페이지는 크롤러 도달 경로 시험용 페이지입니다. 공공기관 누리집 게시판 본문 예시 문장을 충분히 넣어 본문 해시가 서로 다르게 만듭니다.</p>"
            "</main><footer>Duegosystem 시험 사이트<span id=clk></span></footer>%s</body></html>") % (title, head, title, body, TICK)


def target(rid, extra=""):
    return page("도착 %s" % rid, "<p>%s 경로의 끝 페이지입니다. 고유 본문 %s.</p>%s%s" % (rid, rid * 20, extra, ad(rid)))


INDEX = page("시험 누리집", """
<ul>
<li><a href="/f1/list">R01 form GET select 쪽 이동</a></li>
<li><a href="/f2/list">R02 fn_egov_link_page POST</a></li>
<li><a href="/f3/list">R03 goPage AJAX 쪽 교체</a></li>
<li><a href="/f4/list">R04 무한 스크롤</a></li>
<li><a href="/spa/">R05 해시 라우트 SPA</a></li>
<li><a href="/app/">R06 pushState SPA</a></li>
<li><a href="/c7/view?id=1">R07 댓글 JSON API</a></li>
<li><a href="/c8/view?id=1">R08 댓글 더보기 6번</a></li>
<li><a href="/t9/">R09 탭 AJAX</a></li>
<li><a href="/m10/list">R10 모달 상세</a></li>
<li><a href="/v11/view?id=1">R11 첨부 미리보기</a></li>
<li><a href="/d13/list">R13 중복 폭발</a></li>
<li><a href="/cal?ym=202610">R14 달력</a></li>
<li><a href="/slow/list">R15 느린 응답</a></li>
<li><a href="/map/">R17 area</a></li>
<li><a href="/btn/">R18 button location.href</a></li>
<li><a href="/dh/">R19 data-href</a></li>
<li><a href="/sel/">R20 select onchange</a></li>
<li><a href="/ext/">R21 외부 도메인</a></li>
<li><a href="/공지/목록">R23 한글 경로</a></li>
<li><a href="/bh/">R24 base href</a></li>
<li><a href="/mr/">R25 meta refresh</a></li>
<li><a href="/jsr/">R26 JS redirect(조립 주소)</a></li>
<li><a href="/nest/">R27 iframe 3중+srcdoc</a></li>
<li><a href="/sess/">R28 세션 필요</a></li>
<li><a href="/ln/1">R31 link rel=next</a></li>
<li><a href="/pop/">R33 window.open 조립</a></li>
<li><a href="/hov/">R39 hover AJAX 메뉴</a></li>
<li><a href="/ev/list">R40 addEventListener 행 클릭</a></li>
<li><a href="/fp/list">R41 POST form submit 버튼</a></li>
<li><a href="/ib/list?id=free">R42 게시판 ID가 id인 목록 2쪽</a></li>
<li><a href="/aeb/">R44·R45 리스너 button·void 링크</a></li>
<li><a href="/lx/list">R46 리스너 클릭 뒤 화면만 바뀜</a></li>
<li><a href="/cn/list">R47 모든 글 canonical이 목록</a></li>
<li><a href="/late/">R48 4초 뒤 iframe</a></li>
<li><a href="/enc/">R49 원래 표기 그대로</a></li>
<li><a href="/err/">R16 404/500 섞임</a></li>
%s
</ul>""" % ('<li><a href="/big/list?page=1">R12 대형 게시판</a></li>' if BIG else ""))


def list_html(rows):
    return "<table class=tbl><tr><th>제목</th></tr>%s</table>" % "".join("<tr><td>%s</td></tr>" % r for r in rows)


class Hd(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def send(self, body, status=200, ctype="text/html; charset=utf-8", headers=()):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def redirect(self, loc, headers=()):
        self.send("", 302, headers=[("Location", loc)] + list(headers))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.form = dict(urllib.parse.parse_qsl(self.rfile.read(n).decode()))
        self.route()

    def do_GET(self):
        self.form = {}
        self.route()

    def route(self):
        hostport = self.server.server_address[1]
        u = urllib.parse.urlsplit(self.path)
        p = urllib.parse.unquote(u.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        q.update(self.form)
        if hostport == 8181:
            return self.ext(p, q)
        log.append((time.time(), self.command, self.path))
        f = ROUTES.get(p)
        if f:
            return f(self, q)
        for pre, fn in PREFIX:
            if p.startswith(pre):
                return fn(self, p, q)
        self.send(page("없음", "404"), 404)

    def ext(self, p, q):
        if p == "/ad":
            return self.send(target("R21X"))
        if p == "/inner":  # R27 3중 iframe의 가장 안쪽 (다른 도메인)
            return self.send("<html><body><p>안쪽</p>%s</body></html>" % ad("R27"))
        self.send("404", 404)


log = []
ROUTES, PREFIX = {}, []


def r(path):
    def d(fn):
        ROUTES[path] = fn
        return fn
    return d


@r("/")
def _i(h, q):
    h.send(INDEX)


@r("/robots.txt")
def _rb(h, q):
    h.send("User-agent: *\nDisallow: /secret/\nSitemap: %s/sitemap.xml\n" % H, ctype="text/plain")


@r("/sitemap.xml")
def _sm(h, q):
    h.send('<?xml version="1.0"?><urlset><url><loc>%s/only/sitemap-page.html</loc></url></urlset>' % H, ctype="application/xml")


@r("/secret/")
def _sec(h, q):
    h.send(target("R29"))


@r("/only/sitemap-page.html")
def _osp(h, q):
    h.send(target("R30"))


# R01: 쪽 이동이 select + submit(GET)뿐
@r("/f1/list")
def _f1(h, q):
    pg = int(q.get("page", "1"))
    rows = ['<a href="/f1/view?id=%d%02d">글 %d-%d</a>' % (pg, i, pg, i) for i in range(1, 4)]
    form = ('<form action="/f1/list" method="get"><select name="page">%s</select><button type="submit">이동</button></form>'
            % "".join("<option value=%d>%d쪽</option>" % (i, i) for i in range(1, 4)))
    h.send(page("R01 목록 %d쪽" % pg, list_html(rows) + form))


@r("/f1/view")
def _f1v(h, q):
    h.send(target("R01") if q.get("id") == "301" else page("R01 글 " + q.get("id", ""), "<p>보통 글 %s</p>" % q.get("id")))


# R02: 전자정부 fn_egov_link_page → POST, 상세도 POST
@r("/f2/list")
def _f2(h, q):
    if h.command != "POST" and "pageIndex" not in q:
        pg = 1
    else:
        pg = int(q.get("pageIndex", "1"))
    rows = ['<a href="javascript:fn_egov_inqire_notice(\'%d%02d\')">글 %d-%d</a>' % (pg, i, pg, i) for i in range(1, 4)]
    js = """<script>
function fn_egov_link_page(n){document.listForm.pageIndex.value=n;document.listForm.action='/f2/list';document.listForm.submit();}
function fn_egov_inqire_notice(id){document.listForm.nttId.value=id;document.listForm.action='/f2/view';document.listForm.submit();}
</script>"""
    pager = " ".join('<a href="#" onclick="fn_egov_link_page(%d);return false;">%d</a>' % (i, i) for i in range(1, 4))
    form = '<form name="listForm" method="post"><input type=hidden name=pageIndex value=%d><input type=hidden name=nttId></form>' % pg
    h.send(page("R02 목록 %d쪽" % pg, list_html(rows) + "<div class=paging>%s</div>%s%s" % (pager, form, js)))


@r("/f2/view")
def _f2v(h, q):
    if h.command != "POST":
        return h.send(page("잘못된 접근", "<p>잘못된 접근입니다</p>"), 400)
    h.send(target("R02") if q.get("nttId") == "303" else page("R02 글 " + q.get("nttId", ""), "<p>글 %s</p>" % q.get("nttId")))


# R03: goPage(n) → fetch POST JSON, 목록을 그 자리에서 바꿔 끼움
@r("/f3/list")
def _f3(h, q):
    js = """<script>
function goPage(n){fetch('/f3/api',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'page='+n})
.then(r=>r.json()).then(d=>{document.getElementById('rows').innerHTML=d.rows.map(x=>'<li><a href="'+x.u+'">'+x.t+'</a></li>').join('')});}
goPage(1);</script>"""
    pager = " ".join('<a href="javascript:void(0)" onclick="goPage(%d)">%d</a>' % (i, i) for i in range(1, 4))
    h.send(page("R03 목록", "<ul id=rows></ul><div class=paging>%s</div>%s" % (pager, js)))


@r("/f3/api")
def _f3a(h, q):
    pg = int(q.get("page", "1"))
    h.send(json.dumps({"rows": [{"u": "/f3/view?no=%d%02d" % (pg, i), "t": "글 %d-%d" % (pg, i)} for i in range(1, 4)]}),
           ctype="application/json")


@r("/f3/view")
def _f3v(h, q):
    h.send(target("R03") if q.get("no") == "302" else page("R03 글 " + q.get("no", ""), "<p>글 %s</p>" % q.get("no")))


# R04: 무한 스크롤 (스크롤해야 다음 묶음 fetch)
@r("/f4/list")
def _f4(h, q):
    js = """<script>
let pg=1, busy=false;
function more(){ if(busy||pg>3) return; busy=true; fetch('/f4/api?page='+pg).then(r=>r.json()).then(d=>{
 document.getElementById('rows').insertAdjacentHTML('beforeend', d.map(x=>'<li style="height:400px"><a href="'+x.u+'">'+x.t+'</a></li>').join(''));
 pg++; busy=false; });}
window.addEventListener('scroll',()=>{ if(window.innerHeight+window.scrollY>=document.body.scrollHeight-50) more(); });
more();</script>"""
    h.send(page("R04 무한 스크롤", "<ul id=rows></ul>" + js))


@r("/f4/api")
def _f4a(h, q):
    pg = int(q.get("page", "1"))
    h.send(json.dumps([{"u": "/f4/view?no=%d%02d" % (pg, i), "t": "글 %d-%d" % (pg, i)} for i in range(1, 4)]), ctype="application/json")


@r("/f4/view")
def _f4v(h, q):
    h.send(target("R04") if q.get("no") == "201" else page("R04 글 " + q.get("no", ""), "<p>글 %s</p>" % q.get("no")))


# R05: 해시 라우트 SPA. #/board/3 에만 광고 (채점 URL은 /spa/)
@r("/spa/")
def _spa(h, q):
    js = """<script>
function render(){ const r=location.hash.slice(1)||'/';
 fetch('/spa/api?r='+encodeURIComponent(r)).then(x=>x.text()).then(t=>{document.getElementById('view').innerHTML=t;}); }
window.addEventListener('hashchange',render); render();</script>"""
    h.send(page("R05 SPA", '<nav><a href="#/">홈</a> <a href="#/board/1">게시판1</a> <a href="#/board/3">게시판3</a></nav><div id=view></div>' + js))


@r("/spa/api")
def _spaa(h, q):
    h.send(("<p>게시판 3 화면</p>" + ad("R05")) if q.get("r") == "/board/3" else "<p>화면 %s</p>" % q.get("r"), ctype="text/html; charset=utf-8")


# R06: pushState SPA. 링크는 button onclick nav('/app/post/7') 형태, 서버는 직접 접근도 지원
APP_JS = """<script>
function nav(p){ history.pushState({},'',p); render(); }
function render(){ const m=location.pathname.match(/^\\/app\\/post\\/(\\d+)/);
 if(!m){ document.getElementById('view').innerHTML='<p>앱 홈</p>'; return; }
 fetch('/app-api/post?id='+m[1]).then(x=>x.text()).then(t=>{document.getElementById('view').innerHTML=t;}); }
window.addEventListener('popstate',render); render();</script>"""


def _app(h, p, q):
    h.send(page("R06 앱", '<nav><button onclick="nav(\'/app/post/\'+5)">글5</button> <button onclick="nav(\'/app/post/\'+7)">글7</button></nav><div id=view></div>' + APP_JS))


PREFIX.append(("/app/", _app))


@r("/app-api/post")
def _appa(h, q):
    i = q.get("id")
    h.send(("<p>글 7 본문 R06R06R06R06R06</p>" + ad("R06")) if i == "7" else "<p>글 %s 본문</p>" % i)


# R07: 댓글이 별도 JSON API
@r("/c7/view")
def _c7(h, q):
    js = """<script>fetch('/c7/comments?id=1').then(r=>r.json()).then(d=>{document.getElementById('cmt').innerHTML=d.map(c=>'<li class="c">'+c+'</li>').join('');});</script>"""
    h.send(page("R07 글", '<p>본문 R07 글 R07R07R07R07R07R07</p><ul id=cmt></ul>' + js))


@r("/c7/comments")
def _c7c(h, q):
    h.send(json.dumps(["좋은 글입니다", ad("R07")]), ctype="application/json")


# R08: 댓글 더보기 6번 (7번째 묶음에 광고)
@r("/c8/view")
def _c8(h, q):
    js = """<script>let cp=1; function moreCmt(){ fetch('/c8/cmt?cp='+(++cp)).then(r=>r.text()).then(t=>{
 document.getElementById('cmt').insertAdjacentHTML('beforeend',t); if(cp>=7) document.getElementById('mb').remove(); }); }</script>"""
    h.send(page("R08 글", '<p>본문 R08 R08R08R08R08R08R08</p><ul id=cmt><li>댓글 묶음 1</li></ul><button id=mb type=button onclick="moreCmt()">댓글 더보기</button>' + js))


@r("/c8/cmt")
def _c8c(h, q):
    cp = int(q.get("cp", "2"))
    h.send("<li>댓글 묶음 %d %s</li>" % (cp, "가나다라" * 10) + (ad("R08") if cp == 7 else ""))


# R09: 탭 전환 AJAX (내용을 바꿔 끼움)
@r("/t9/")
def _t9(h, q):
    js = """<script>function loadTab(t){ fetch('/t9/tab?t='+t).then(r=>r.text()).then(x=>{document.getElementById('tabc').innerHTML=x;}); } loadTab('notice');</script>"""
    h.send(page("R09 탭", '<div class=tabs><button type=button onclick="loadTab(\'notice\')">공지</button><button type=button onclick="loadTab(\'data\')">자료실</button></div><div id=tabc></div>' + js))


@r("/t9/tab")
def _t9t(h, q):
    h.send(("<p>자료실 탭</p>" + ad("R09")) if q.get("t") == "data" else "<p>공지 탭 내용</p>")


# R10: 상세가 모달 (fetch 조각을 모달에 넣음)
@r("/m10/list")
def _m10(h, q):
    js = """<script>function openModal(id){ fetch('/m10/frag?id='+id).then(r=>r.text()).then(t=>{const m=document.getElementById('modal'); m.innerHTML=t; m.style.display='block';}); }</script>"""
    rows = ['<a href="#" onclick="openModal(%d);return false;">글 %d</a>' % (i, i) for i in range(1, 4)]
    h.send(page("R10 목록", list_html(rows) + '<div id=modal style="display:none;position:fixed;top:10px;left:10px;background:#fff"></div>' + js))


@r("/m10/frag")
def _m10f(h, q):
    h.send(("<p>글 2 상세</p>" + ad("R10")) if q.get("id") == "2" else "<p>글 %s 상세</p>" % q.get("id"))


# R11: 첨부 미리보기 (쿼리 값이 .hwp)
@r("/v11/view")
def _v11(h, q):
    h.send(page("R11 글", '<p>첨부: 공고문.hwp <a href="/v11/download?file=notice.hwp">내려받기</a> <a href="/v11/preview?file=notice.hwp" target="_blank">미리보기</a></p>'))


@r("/v11/preview")
def _v11p(h, q):
    h.send(target("R11"))


# R13: 같은 글이 ref 꼬리표만 다른 URL 수백 개
@r("/d13/list")
def _d13(h, q):
    links = " ".join('<a href="/d13/view?id=1&ref=r%d">글1 경로%d</a>' % (i, i) for i in range(300))
    links += ' <a href="/d13/view?id=2">글2</a>'
    h.send(page("R13 목록", links))


@r("/d13/view")
def _d13v(h, q):
    h.send(target("R13") if q.get("id") == "2" else page("R13 글1", "<p>글1 본문 같은 내용 반복</p>" + "가" * 200))


# R14: 무한 달력
@r("/cal")
def _cal(h, q):
    ym = int(q.get("ym", "202610"))
    y, m = divmod(ym, 100)
    nx = y * 100 + m + 1 if m < 12 else (y + 1) * 100 + 1
    pv = y * 100 + m - 1 if m > 1 else (y - 1) * 100 + 12
    ev = '<a href="/cal/event?id=9">행사</a>' if ym == 202610 else ""
    h.send(page("R14 달력 %d" % ym, '<a href="/cal?ym=%d">이전</a> <a href="/cal?ym=%d">다음</a> %s' % (pv, nx, ev)))


@r("/cal/event")
def _cale(h, q):
    h.send(target("R14"))


# R15: 느린 응답 4초
@r("/slow/list")
def _slow(h, q):
    h.send(page("R15 목록", '<a href="/slow/view?id=1">느린 글</a>'))


@r("/slow/view")
def _slowv(h, q):
    time.sleep(4)
    h.send(target("R15"))


# R16: 404/500 섞임 + 500 응답 본문에 광고(채점 대상 여부는 출제 해석)
@r("/err/")
def _err(h, q):
    h.send(page("R16", '<a href="/err/missing">깨진 링크</a> <a href="/err/500">서버 오류</a> <a href="/err/ok">정상</a>'))


@r("/err/500")
def _e500(h, q):
    h.send(target("R16X"), 500)


@r("/err/ok")
def _eok(h, q):
    h.send(target("R16"))


# R17~R20
@r("/map/")
def _map(h, q):
    h.send(page("R17", '<img src="/x.gif" usemap="#m" width=10 height=10 alt=""><map name=m><area shape=rect coords="0,0,10,10" href="/map/target" alt="이동"></map>'))


@r("/map/target")
def _mapt(h, q):
    h.send(target("R17"))


@r("/btn/")
def _btn(h, q):
    h.send(page("R18", '<button type=button onclick="location.href=\'/btn/target\'">바로가기</button>'))


@r("/btn/target")
def _btnt(h, q):
    h.send(target("R18"))


@r("/dh/")
def _dh(h, q):
    h.send(page("R19", '<div class=card data-href="/dh/target">카드</div>'))


@r("/dh/target")
def _dht(h, q):
    h.send(target("R19"))


@r("/sel/")
def _sel(h, q):
    h.send(page("R20", '<select onchange="if(this.value) location.href=this.value"><option value="">관련 사이트</option><option value="/sel/target">산하기관</option></select>'))


@r("/sel/target")
def _selt(h, q):
    h.send(target("R20"))


@r("/ext/")
def _ext(h, q):
    h.send(page("R21", '<a href="%s/ad">협력 기관</a> <a href="/ext/ok">정상</a>' % X))


@r("/ext/ok")
def _exto(h, q):
    h.send(target("R21"))


def _kor(h, p, q):
    if p == "/공지/목록":
        return h.send(page("R23", '<a href="/공지/글%20보기?번호=5">글</a>'))
    if p == "/공지/글 보기" and q.get("번호") == "5":
        return h.send(target("R23"))
    h.send("404", 404)


PREFIX.append(("/공지/", _kor))


@r("/bh/")
def _bh(h, q):
    h.send(page("R24", '<a href="target.html">상대 링크</a>', head='<base href="/bh/sub/">'))


@r("/bh/sub/target.html")
def _bht(h, q):
    h.send(target("R24"))


@r("/mr/")
def _mr(h, q):
    h.send(page("R25", "<p>이동 중</p>", head='<meta http-equiv="refresh" content="0; url=/mr/target">'))


@r("/mr/target")
def _mrt(h, q):
    h.send(target("R25"))


@r("/jsr/")
def _jsr(h, q):
    h.send(page("R26", "<p>이동 중</p><script>var d='tar'+'get'; setTimeout(function(){location.replace('/jsr/'+d+'_page');},300);</script>"))


@r("/jsr/target_page")
def _jsrt(h, q):
    h.send(target("R26"))


@r("/nest/")
def _nest(h, q):
    h.send(page("R27", '<iframe src="/nest/l1" width=400 height=300></iframe>'))


@r("/nest/l1")
def _n1(h, q):
    h.send('<html><body><p>1단</p><iframe srcdoc="&lt;p&gt;2단 srcdoc&lt;/p&gt;&lt;iframe src=&quot;%s/inner&quot;&gt;&lt;/iframe&gt;"></iframe></body></html>' % X)


# R28: 세션 쿠키가 있어야 게시판이 열림 (없으면 /sess/로 돌려보냄)
@r("/sess/")
def _sess(h, q):
    h.send(page("R28 입구", '<a href="/sess/board">게시판</a>'), headers=[("Set-Cookie", "SID=ok; Path=/")])


def has_cookie(h):
    return "SID=ok" in (h.headers.get("Cookie") or "")


@r("/sess/board")
def _sessb(h, q):
    if not has_cookie(h):
        return h.redirect("/sess/")
    h.send(page("R28 게시판", '<a href="/sess/view?id=1">글1</a>'))


@r("/sess/view")
def _sessv(h, q):
    if not has_cookie(h):
        return h.redirect("/sess/")
    h.send(target("R28"))


@r("/ln/1")
def _ln1(h, q):
    h.send(page("R31 1쪽", "<p>첫 쪽</p>", head='<link rel="next" href="/ln/2">'))


@r("/ln/2")
def _ln2(h, q):
    h.send(target("R31"))


@r("/pop/")
def _pop(h, q):
    h.send(page("R33", "<a href=\"javascript:openPop('n7')\">팝업 공지</a><script>function openPop(k){window.open('/pop/'+'view_'+k,'pop','width=400,height=300');}</script>"))


@r("/pop/view_n7")
def _popv(h, q):
    h.send(target("R33"))


@r("/hov/")
def _hov(h, q):
    js = """<script>document.getElementById('m').addEventListener('mouseenter',()=>{fetch('/hov/menu').then(r=>r.text()).then(t=>{document.getElementById('sub').innerHTML=t;});});</script>"""
    h.send(page("R39", '<div id=m>기관소개 메뉴<div id=sub></div></div>' + js))


@r("/hov/menu")
def _hovm(h, q):
    h.send('<a href="/hov/target">조직도</a>')


@r("/hov/target")
def _hovt(h, q):
    h.send(target("R39"))


@r("/ev/list")
def _ev(h, q):
    rows = ['<span data-no="%d" class=row>글 %d</span>' % (i, i) for i in (11, 12, 13)]
    js = """<script>document.querySelectorAll('.row').forEach(e=>e.addEventListener('click',()=>{location.href='/ev/view?no='+e.dataset.no;}));</script>"""
    h.send(page("R40 목록", list_html(rows) + js))


@r("/ev/view")
def _evv(h, q):
    h.send(target("R40") if q.get("no") == "12" else page("R40 글 " + q.get("no", ""), "<p>글 %s</p>" % q.get("no")))


@r("/fp/list")
def _fp(h, q):
    pg = int(q.get("page", "1"))
    rows = ['<a href="/fp/view?id=%d">글 %d</a>' % (pg * 10 + i, pg * 10 + i) for i in range(1, 3)]
    nxt = '<form method="post" action="/fp/list"><input type=hidden name=page value="%d"><button type=submit>다음 쪽</button></form>' % (pg + 1) if pg < 2 else ""
    h.send(page("R41 목록 %d" % pg, list_html(rows) + nxt))


@r("/fp/view")
def _fpv(h, q):
    h.send(target("R41") if q.get("id") == "22" else page("R41 글 " + q.get("id", ""), "<p>글 %s</p>" % q.get("id")))


# R12: 대형 게시판 (--big): 300쪽 x 10글
@r("/big/list")
def _big(h, q):
    pg = int(q.get("page", "1"))
    rows = ['<a href="/big/view?id=%d">글 %d</a>' % (i, i) for i in range((pg - 1) * PER + 1, pg * PER + 1)]
    pager = " ".join('<a href="/big/list?page=%d">%d</a>' % (i, i) for i in range(max(1, pg - 5), min(NPOST // PER, pg + 5) + 1))
    h.send(page("R12 목록 %d쪽" % pg, list_html(rows) + "<div class=paging>%s</div>" % pager))


@r("/big/view")
def _bigv(h, q):
    i = int(q.get("id", "0"))
    if i in (5, 1500, 2995):
        return h.send(target("R12_%d" % i))
    h.send(page("R12 글 %d" % i, "<p>대형 게시판 글 %d 본문 %s</p>" % (i, str(i) * 30)))


@r("/x.gif")
def _gif(h, q):
    h.send(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", ctype="image/gif")


# ---------- todo/12 재현 (10/17) ----------
@r("/ib/list")
def _ib(h, q):  # R42 게시판 ID가 id인 목록의 2쪽: ?id=free&page=2는 ?id=free와 다른 페이지
    pg = q.get("page", "1")
    nxt = '<a href="/ib/list?id=free&amp;page=2">2</a>' if pg == "1" else ""
    h.send(page("R42 목록 %s쪽" % pg, list_html(["글 %s-%d" % (pg, i) for i in (1, 2)]) + nxt + (ad("R42") if pg == "2" else "")))


@r("/aeb/")
def _aeb(h, q):  # R44 addEventListener로 건 button, R45 javascript:void(0) 링크 + 리스너
    js = """<script>document.querySelector('.go44').addEventListener('click',()=>{location.href='/aeb/t44';});
document.querySelector('.go45').addEventListener('click',e=>{e.preventDefault();location.href='/aeb/t45';});</script>"""
    h.send(page("R44 버튼", '<button type=button class=go44>상세 보기</button> <a href="javascript:void(0)" class=go45>자세히</a>' + js))


@r("/aeb/t44")
def _aeb44(h, q):
    h.send(target("R44"))


@r("/aeb/t45")
def _aeb45(h, q):
    h.send(target("R45"))


@r("/lx/list")
def _lx(h, q):  # R46 리스너 클릭이 이동 없이 화면만 바꿈 (상세를 같은 페이지에 그림)
    rows = ['<div class=card data-no="%d">글 %d</div>' % (i, i) for i in (1, 2)]
    js = """<script>document.querySelectorAll('.card').forEach(e=>e.addEventListener('click',()=>{
document.getElementById('detail').innerHTML = e.dataset.no === '2' ? '<p>글 2 본문</p>' + %s : '<p>글 1 본문</p>';}));</script>""" % json.dumps(ad("R46"))
    h.send(page("R46 목록", "".join(rows) + '<div id=detail></div>' + js))


@r("/cn/list")
def _cn(h, q):  # R47 모든 글의 canonical이 목록을 가리킴: 글마다 따로 기록해야 함
    h.send(page("R47 목록", list_html(['<a href="/cn/view?id=%d">글 %d</a>' % (i, i) for i in (1, 2, 3)])))


@r("/cn/view")
def _cnv(h, q):
    i = q.get("id", "")
    body = "<p>R47 글 %s 본문 %s</p>" % (i, i * 30) + (ad("R47") if i == "3" else "")
    h.send(page("R47 글 " + i, body, head='<link rel="canonical" href="/cn/list?bid=notice">'))


@r("/late/")
def _late(h, q):  # R48 4초 뒤에 넣는 iframe (확인만)
    js = """<script>setTimeout(()=>{const f=document.createElement('iframe');f.src='/late/frame';document.body.appendChild(f);},4000);</script>"""
    h.send(page("R48 늦은 iframe", "<p>늦게 붙는 배너</p>" + js))


@r("/late/frame")
def _latef(h, q):
    h.send("<html><body><p>배너</p>%s</body></html>" % ad("R48"))



@r("/enc/")
def _enc(h, q):  # R49 결과 url이 링크 원래 표기 그대로인지: %20, %2F, 값 없는 ?flag (todo/12 결정 6)
    h.send(page("R49 인코딩", '<a href="/enc/view?q=a%20b&amp;path=x%2Fy&amp;flag">글</a>'))


@r("/enc/view")
def _encv(h, q):
    h.send(target("R49") if q.get("path") == "x/y" else page("R49 없음", "<p>없음</p>"))

def dump_log():
    with open(sys.argv[sys.argv.index("--log") + 1] if "--log" in sys.argv else "/dev/null", "w") as f:
        for t, m, p in log:
            f.write("%.2f %s %s\n" % (t, m, p))


if __name__ == "__main__":
    ext = ThreadingHTTPServer(("127.0.0.1", 8181), Hd)
    threading.Thread(target=ext.serve_forever, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", 8180), Hd)
    srv.daemon_threads = True
    import signal
    signal.signal(signal.SIGTERM, lambda *a: (dump_log(), sys.exit(0)))
    try:
        srv.serve_forever()
    finally:
        dump_log()
