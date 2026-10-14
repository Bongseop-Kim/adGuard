# -*- coding: utf-8 -*-
"""고시·공고 게시판 (전자정부 표준프레임워크식).

- 목록 1쪽: GET /egov/cop/bbs/selectArticleList.do?bbsId=…
- 목록 2쪽 이후·상세: onclick → form POST 로만 열림 (같은 파라미터의 GET도 같은 글을 돌려줌)
- 링크에 ;jsessionid= 가 붙는다
"""
from .ads import AD
from .layout import BOARD_CSS, E, crumb, layout, q1

BBS = "BBSMSTR_000000000021"
LIST = "/egov/cop/bbs/selectArticleList.do"
DETAIL = "/egov/cop/bbs/selectArticleDetail.do"
PER_PAGE = 10
TOPICS = ["도시계획시설 결정 고시", "공유재산 대부 공고", "체육시설 사용료 변경 고시", "건축물 철거 공고",
          "주차장 관리 위탁 공고", "개인정보파일 보유 현황 공고", "물품 매각 공고", "시설물 사용 허가 공고"]
ARTICLES = {n: {"id": n, "title": "제2026-%03d호 %s" % (n, TOPICS[n % len(TOPICS)]),
                "date": "2026-%02d-%02d" % (10 - n // 20, 28 - n % 20)} for n in range(1, 49)}
ARTICLES[12]["title"] = AD["e12_title"]

# 본문에 덧붙는 요소 (정답)
EXTRA = {
    7: '<p class="ref-note" style="filter:opacity(0)">%s</p>' % AD["e7"],
    19: '<p class="ref-note">%s</p>' % AD["e19"],
}


SID = ";jsessionid=S3A9F0C1D2E3"  # 서버가 경로에서 떼어 낸다


def page_list(qs):
    try:
        page = max(1, int(q1(qs, "pageIndex", "1")))
    except ValueError:
        page = 1
    ids = sorted(ARTICLES, reverse=True)
    last = (len(ids) + PER_PAGE - 1) // PER_PAGE
    rows = ids[(page - 1) * PER_PAGE: page * PER_PAGE]
    trs = "\n".join(
        '<tr><td>%d</td><td class="subject"><a href="#none" onclick="fn_egov_inqire_notice(\'%d\'); return false;">%s</a></td>'
        '<td>%s</td></tr>' % (n, n, E(ARTICLES[n]["title"]), ARTICLES[n]["date"]) for n in rows)
    pg = "".join("<strong>%d</strong>" % p if p == page else
                 '<a href="#none" onclick="fn_egov_select_noticeList(\'%d\'); return false;">%d</a>' % (p, p)
                 for p in range(1, last + 1))
    body = """<h2 class="sub-title">고시·공고</h2>
<form name="frm" method="post" action="%(list)s%(sid)s">
<input type="hidden" name="bbsId" value="%(bbs)s">
<input type="hidden" name="pageIndex" value="%(page)d">
<input type="hidden" name="nttId" value="">
</form>
<table class="board_list">
<caption class="blind">고시·공고 목록</caption>
<thead><tr><th scope="col">번호</th><th scope="col">제목</th><th scope="col">게시일</th></tr></thead>
<tbody>
%(trs)s
</tbody>
</table>
<div class="paging">%(pg)s</div>
<script>
function fn_egov_select_noticeList(p){var f=document.frm;f.pageIndex.value=p;f.action="%(list)s%(sid)s";f.submit();}
function fn_egov_inqire_notice(id){var f=document.frm;f.nttId.value=id;f.action="%(detail)s%(sid)s";f.submit();}
</script>""" % {"list": LIST, "detail": DETAIL, "sid": SID, "bbs": BBS, "page": page, "trs": trs, "pg": pg}
    return layout("고시·공고", body, crumb("알림마당", "고시·공고"), BOARD_CSS)


def page_detail(qs):
    try:
        n = int(q1(qs, "nttId", "0"))
    except ValueError:
        return None
    if n not in ARTICLES:
        return None
    a = ARTICLES[n]
    body = """<h2 class="sub-title">고시·공고</h2>
<div class="board_view">
  <h3 class="view_tit">%s</h3>
  <div class="view_cont">
    <p>%s에 관한 사항을 다음과 같이 고시합니다.</p>
    <p>열람 장소: 가온시설관리공단 경영지원팀 (031-000-0021)</p>
    %s
  </div>
</div>
<p><a class="btn" href="%s?bbsId=%s">목록</a></p>""" % (E(a["title"]), E(TOPICS[n % len(TOPICS)]), EXTRA.get(n, ""), LIST, BBS)
    return layout(a["title"], body, crumb("알림마당", "고시·공고"), BOARD_CSS)
