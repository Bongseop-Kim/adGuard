# -*- coding: utf-8 -*-
"""대형 공지사항 게시판 (그누보드식 GET 게시판, 260건 26쪽).

- 목록: /board/notice/list?page=&sca=&sfl=&stx=&sst=&sod=  (조합이 폭증하는 함정)
- 상세: /board/notice/view?id=N  (목록 링크에는 &page= 등 꼬리표가 붙는다)
"""
import random
from urllib.parse import urlencode

from .ads import AD
from .layout import BASE, BOARD_CSS, E, crumb, layout, q1

N_FIRST, N_LAST, PER_PAGE = 1001, 1260, 10
CATES = ["공지", "안내", "채용", "입찰", "행사"]
SUBJ = ["가온체육센터 수영장 정기 휴관", "공영주차장 요금 체계 개편", "시설물 안전점검 실시", "청년 인턴 채용",
        "무인민원발급기 설치", "하반기 생활체육 강좌 수강생 모집", "공원 녹지 정비 공사", "장애인 편의시설 개선",
        "주민 공청회 개최", "직원 정기 인사", "청사 전기설비 교체", "문화센터 대관 신청", "고객만족도 조사 결과",
        "개인정보 처리방침 개정", "에너지 절약 캠페인", "기간제 근로자 채용", "물품 구매 입찰", "용역 입찰 재공고",
        "시민 사진 공모전", "가온 한마당 축제 운영"]

_rng = random.Random(20261014)
NOTICES = {}
for _i, _nid in enumerate(range(N_LAST, N_FIRST - 1, -1)):
    _cate = CATES[_rng.randrange(len(CATES))]
    _subj = SUBJ[_rng.randrange(len(SUBJ))]
    _m, _d = 10, 13 - (_i // 3)
    while _d < 1:
        _m, _d = _m - 1, _d + 30
    NOTICES[_nid] = {"id": _nid, "cate": _cate, "subj": _subj,
                     "title": "[%s] 2026년 %s 안내 (제%d호)" % (_cate, _subj, _nid - 1000),
                     "date": "2026-%02d-%02d" % (_m, _d), "hit": _rng.randrange(30, 2400),
                     "dept": _rng.choice(["경영지원팀", "시설운영팀", "체육사업팀", "주차사업팀", "안전관리팀"])}
NOTICES[1255]["title"] = "[안내] 청소년 불법도박 예방 교육 운영 안내"
NOTICES[1220]["title"] = "[공지] 위탁 운영사 계약 체결 결과 공개"
NOTICES[1190]["title"] = "[안내] 2026년 시민 의견 수렴 게시판 운영"

# 본문 끝에 덧붙는 숨김 요소 (정답)
EXTRA = {
    1002: '<div class="ref-box" style="transform:translateX(-9999px)">%s</div>' % AD["n1002"],
    1009: '<p class="addr-note" style="margin-left:-9999px">%s</p>' % AD["n1009"],
    1137: ('<div class="info-box"><p class="info-txt">※ 담당부서: 시설운영팀 (031-000-0137)</p>'
           '<span class="tail-txt" style="color:#eef3f8">%s</span></div>') % AD["n1137"],
    1088: '<div class="sr-box" style="width:1px;height:1px;overflow:hidden">%s</div>' % AD["n1088"],
    1045: '<div class="fold-txt" style="max-height:0;overflow:hidden">%s</div>' % AD["n1045"],
    1201: '<span class="clip-txt" style="position:absolute;clip:rect(0 0 0 0)">%s</span>' % AD["n1201"],
    1176: '<p class="ls-txt" style="letter-spacing:-30px;font-size:12px;white-space:nowrap">%s</p>' % AD["n1176"],
    1150: ('<div class="clip-wrap" style="position:relative;height:26px;overflow:hidden">'
           '<p>※ 문의: 시설운영팀 (031-000-0150)</p>'
           '<span class="out-txt" style="position:absolute;left:0;top:300px">%s</span></div>') % AD["n1150"],
    1033: '<p class="ntc-meta">%s</p>' % AD["n1033"],
    1240: ('<p class="js-tail">%s</p><script>(function(){var t=document.querySelector(".view-content .js-tail");'
           't.setAttribute("style",atob("cG9zaXRpb246YWJzb2x1dGU7bGVmdDotOTk5OXB4"));})();</script>') % AD["n1240"],
    1111: '<p class="fill-txt" style="-webkit-text-fill-color:transparent">%s</p>' % AD["n1111"],
    1260: ('<p class="late-msg"></p><script>setTimeout(function(){'
           'document.querySelector(".view-content .late-msg").textContent="%s";},1500);</script>') % AD["n1260"],
}

COMMENTS = {
    1190: [("김시민", "ㅋㅋ 좋은 정보 감사합니다 ㅠㅠ"), ("방문자", AD["n1190_extra"]),
           ("이가온", "주차장 운영 시간도 안내 부탁드립니다.")],
    1137: [("박주민", "안내 감사합니다.")],
    1200: [("최민원", "수영장 재개장 일정이 궁금합니다."), ("담당자", "11월 3일 재개장 예정입니다.")],
}


def _body(nid):
    n = NOTICES[nid]
    paras = ["<p>%s 관련하여 다음과 같이 안내드립니다.</p>" % E(n["subj"]),
             "<p>자세한 사항은 첨부파일을 확인하시거나 %s(031-000-%04d)로 문의하여 주시기 바랍니다.</p>" % (n["dept"], nid)]
    if nid == 1255:
        paras = ["<p>청소년을 대상으로 불법도박 예방 교육을 운영합니다. 불법 사설토토·온라인 카지노 광고 신고 방법도 함께 안내합니다.</p>",
                 "<p>신고: 사이버범죄 신고시스템, 한국도박문제예방치유원 1336</p>"]
    elif nid == 1220:
        paras = ["<p>위탁 운영사 계약 체결 결과를 다음과 같이 공개합니다.</p>",
                 "<p>① 계약 상대자: 가온레저株式會社 ② 계약 기간: 2026. 11. 1. ~ 2028. 10. 31. ③ 계약 금액: ₩120,000,000（부가세 포함）</p>",
                 "<p>ㄱ. 운영 범위 ㄴ. 성과 평가 ㄷ. 위반 시 제재 사항은 붙임 문서를 참고하시기 바랍니다.</p>"]
    if nid == 1066:
        # 요청마다 바뀌는 해시 클래스 (F14)
        h = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
        paras.append('<div class="css-%s e1%s" style="color:transparent">%s</div>' % (h, h[:3], AD["n1066"]))
    elif nid in EXTRA:
        paras.append(EXTRA[nid])
    return "\n".join(paras)


def _filtered(sca, stx, sfl, sst, sod):
    items = list(NOTICES.values())
    if sca in CATES:
        items = [x for x in items if x["cate"] == sca]
    if stx:
        key = "subj" if sfl == "wr_content" else "title"
        items = [x for x in items if stx in x[key]]
    if sst == "wr_hit":
        items.sort(key=lambda x: (x["hit"], x["id"]))
    elif sst == "wr_subject":
        items.sort(key=lambda x: (x["title"], x["id"]))
    else:
        items.sort(key=lambda x: x["id"])
    if sod != "asc":
        items.reverse()
    return items


def page_list(qs):
    try:
        page = max(1, int(q1(qs, "page", "1")))
    except ValueError:
        page = 1
    sca, stx = q1(qs, "sca"), q1(qs, "stx")
    sfl, sst, sod = q1(qs, "sfl", "wr_subject"), q1(qs, "sst", "wr_datetime"), q1(qs, "sod", "desc")
    items = _filtered(sca, stx, sfl, sst, sod)
    total = len(items)
    last = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    rows = items[(page - 1) * PER_PAGE: page * PER_PAGE]
    state = [("sca", sca), ("sfl", sfl if stx else ""), ("stx", stx),
             ("sst", sst if sst != "wr_datetime" else ""), ("sod", sod if sod != "desc" else "")]

    def link(**over):
        p = dict(state)
        p["page"] = str(page)
        p.update(over)
        p = {k: v for k, v in p.items() if v}
        return E("/board/notice/list" + ("?" + urlencode(p) if p else ""))

    def view_link(nid):
        p = [("id", nid)] + [(k, v) for k, v in state if v] + [("page", page)]
        return E("/board/notice/view?" + urlencode(p))

    cate = '<div class="board-cate"><a href="%s"%s>전체</a>%s</div>' % (
        link(sca="", page="1"), ' class="on"' if not sca else "",
        "".join('<a href="%s"%s>%s</a>' % (link(sca=c, page="1"), ' class="on"' if c == sca else "", c) for c in CATES))
    hot = '<div class="hot-keyword">인기검색어: %s</div>' % " ".join(
        '<a href="%s">%s</a>' % (link(stx=k, sfl="wr_subject", page="1"), k) for k in ["채용", "입찰", "휴관", "모집", "주차장"])
    search = ('<form class="board-search" method="get" action="/board/notice/list">'
              '<label class="blind" for="sfl">검색 조건</label><select id="sfl" name="sfl"><option value="wr_subject">제목</option>'
              '<option value="wr_content">내용</option></select><label class="blind" for="stx">검색어</label>'
              '<input id="stx" name="stx" value="%s"><button type="submit">검색</button></form>') % E(stx)

    def th(label, key):
        nsod = "asc" if (sst == key and sod == "desc") else "desc"
        return '<th scope="col"><a href="%s">%s</a></th>' % (link(sst=key, sod=nsod, page="1"), label)

    trs = ['<tr><td class="num">%d</td><td class="cate">%s</td><td class="title"><a href="%s">%s</a></td>'
           '<td class="writer">%s</td><td class="date">%s</td><td class="hit">%d</td></tr>'
           % (total - ((page - 1) * PER_PAGE + i), it["cate"], view_link(it["id"]), E(it["title"]), it["dept"], it["date"], it["hit"])
           for i, it in enumerate(rows)] or ['<tr><td colspan="6" class="empty">게시물이 없습니다.</td></tr>']
    pg = []
    if page > 1:
        pg.append('<a href="%s" class="first">처음</a><a href="%s" class="prev">이전</a>' % (link(page="1"), link(page=str(page - 1))))
    for p in range(1, last + 1):
        pg.append("<strong>%d</strong>" % p if p == page else '<a href="%s">%d</a>' % (link(page=str(p)), p))
    if page < last:
        pg.append('<a href="%s" class="next">다음</a><a href="%s" class="last">맨끝</a>' % (link(page=str(page + 1)), link(page=str(last))))
    body = """<h2 class="sub-title">공지사항</h2>
%s%s%s
<p class="total">전체 <strong>%d</strong>건, 현재 %d / %d 쪽</p>
<table class="board-list">
<caption class="blind">공지사항 목록</caption>
<thead><tr><th scope="col">번호</th><th scope="col">분류</th>%s<th scope="col">담당부서</th>%s%s</tr></thead>
<tbody>
%s
</tbody>
</table>
<div class="paging">%s</div>""" % (cate, hot, search, total, page, last, th("제목", "wr_subject"), th("등록일", "wr_datetime"),
                                    th("조회", "wr_hit"), "\n".join(trs), "".join(pg))
    return layout("공지사항", body, crumb("알림마당", "공지사항"), BOARD_CSS)


def page_view(qs):
    try:
        nid = int(q1(qs, "id", "0"))
    except ValueError:
        return None
    if nid not in NOTICES:
        return None
    n = NOTICES[nid]
    page = (N_LAST - nid) // PER_PAGE + 1
    files = ('<div class="view-file">첨부파일: <a href="/files/notice_%d.hwp">%s.hwp</a> '
             '<a href="/files/notice_%d.pdf">%s.pdf</a></div>') % (nid, E(n["subj"]), nid, E(n["subj"]))
    cmts = COMMENTS.get(nid, [])
    cmt_html = ""
    if cmts:
        cmt_html = '<div class="cmt-area"><h4>댓글 %d</h4><div class="cmt-list">%s</div></div>' % (
            len(cmts), "".join('<div class="cmt-item"><p class="cmt-name">%s</p><p class="cmt-txt">%s</p></div>'
                               % (E(a), E(b)) for a, b in cmts))
    pn = []
    if nid + 1 in NOTICES:
        pn.append('<li class="prev">이전글 <a href="/board/notice/view?id=%d">%s</a></li>' % (nid + 1, E(NOTICES[nid + 1]["title"])))
    if nid - 1 in NOTICES:
        pn.append('<li class="next">다음글 <a href="/board/notice/view?id=%d">%s</a></li>' % (nid - 1, E(NOTICES[nid - 1]["title"])))
    body = """<h2 class="sub-title">공지사항</h2>
<div class="view-wrap">
  <h3 class="view-title">%s</h3>
  <div class="view-info">담당부서 %s | 등록일 %s | 조회 %d</div>
  <div class="view-content">
%s
  </div>
  %s
  <p class="print-only">본 문서는 가온시설관리공단 누리집에서 출력한 문서입니다.</p>
  %s
  <ul class="prev-next">%s</ul>
  <div class="btn-area"><a class="btn" href="/board/notice/list?page=%d">목록</a></div>
</div>""" % (E(n["title"]), n["dept"], n["date"], n["hit"], _body(nid), files, cmt_html, "".join(pn), page)
    head = BOARD_CSS + '<link rel="canonical" href="%s/board/notice/view?id=%d">' % (BASE, nid)
    return layout(n["title"], body, crumb("알림마당", "공지사항"), head)


def recent(k=5):
    return [NOTICES[i] for i in range(N_LAST, N_LAST - k, -1)]
