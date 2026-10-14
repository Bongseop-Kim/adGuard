# -*- coding: utf-8 -*-
"""일반 페이지: 메인, 기관소개, 자료실(지연·타임아웃·깨진 링크), 통계(대형 DOM), FAQ, 사이트맵."""
import html
import time

from . import notice
from .ads import AD
from .layout import BOARD_CSS, E, EXT, crumb, layout, q1

DELAY = {1: 1, 2: 2, 3: 1, 4: 3, 5: 5, 6: 2}  # 보고서 id -> 응답 지연(초)


def page_index(qs):
    latest = "".join('<li><a href="/board/notice/view?id=%d">%s</a><span>%s</span></li>' % (n["id"], E(n["title"]), n["date"])
                     for n in notice.recent())
    body = """<div class="main-visual"><p class="mv-txt">시민과 함께하는 가온시설관리공단</p></div>
<div class="main-box">
  <div class="latest"><h2>공지사항</h2><ul>%s</ul><a class="more" href="/board/notice/list">더보기<span class="blind">공지사항</span></a></div>
  <div class="quick"><h2>바로가기</h2>
    <ul><li><a href="/calendar/month">행사일정</a></li><li><a href="/data/list">자료실</a></li><li><a href="/civil/faq">자주 묻는 질문</a></li></ul>
    <iframe class="quick-frame" src="/widget/quick.html" title="퀵메뉴" style="display:none"></iframe>
  </div>
</div>
<div class="layer-popup"><p class="lp-txt">추석 연휴 시설 운영 안내</p><button type="button" class="btn-close">닫기</button></div>""" % latest
    return layout("메인", body)


INTRO = {
    "greeting": ("인사말", "<p>시민 여러분, 반갑습니다. 가온시설관리공단 이사장입니다.</p>"),
    "org": ("조직도", '<ul class="org"><li>이사장</li><li>경영지원팀</li><li>시설운영팀</li><li>체육사업팀</li><li>주차사업팀</li><li>안전관리팀</li></ul>'),
    "vision": ("비전·목표", '<p>안전하고 쾌적한 공공시설, 시민이 만족하는 서비스</p>\n<p class="v-note" style="display:none">%s</p>' % AD["vision"]),
    "history": ("연혁", """<ul class="history"><li>2001. 공단 설립</li><li>2015. 가온체육센터 개관</li><li>2024. 공영주차장 통합 운영</li></ul>
<div class="sh-host-open"></div><div class="sh-host-closed"></div>
<script>
(function(){
  var o=document.querySelector('.sh-host-open').attachShadow({mode:'open'});
  o.innerHTML='<p class="sh-open" style="opacity:0">%s</p>';
  var c=document.querySelector('.sh-host-closed').attachShadow({mode:'closed'});
  c.innerHTML='<p class="sh-closed" style="position:absolute;left:-9999px">%s</p>';
})();
</script>""" % (AD["shadow_open"], AD["shadow_closed"])),
    "location": ("오시는 길", """<p>가온시 중앙로 100 (가온역 2번 출구 도보 5분)</p>
<iframe class="map-frame" src="%(ext)s/ext/map.html" title="약도" width="600" height="300"></iframe>
<iframe class="stat-frame" src="%(ext)s/ext/map-ad.html" title="통계" width="0" height="0" frameborder="0"></iframe>""" % {"ext": EXT}),
}


def page_intro(name):
    if name not in INTRO:
        return None
    title, body = INTRO[name]
    return layout(title, '<h2 class="sub-title">%s</h2>\n%s' % (title, body), crumb("공단소개", title))


def page_data_list(qs):
    rows = "".join('<tr><td>%d</td><td class="title"><a href="/data/report?id=%d">2026년 %d분기 시설 운영 보고서</a></td></tr>'
                   % (i, i, (i - 1) % 4 + 1) for i in DELAY)
    rows += ('<tr><td>7</td><td class="title"><a href="/data/archive">과거 자료 전체 보기</a></td></tr>'
             '<tr><td>8</td><td class="title"><a href="/files/plan_2025.hwp">2025 사업계획서.hwp</a></td></tr>'
             '<tr><td>9</td><td class="title"><a href="/data/error">통계 연보</a></td></tr>')
    body = '<h2 class="sub-title">자료실</h2>\n<table class="board-list"><caption class="blind">자료실 목록</caption>\n<tbody>%s</tbody></table>' % rows
    return layout("자료실", body, crumb("정보공개", "자료실"), BOARD_CSS)


def page_report(qs):
    try:
        rid = int(q1(qs, "id", "0"))
    except ValueError:
        return None
    if rid not in DELAY:
        return None
    time.sleep(DELAY[rid])  # 느린 응답
    extra = '<p class="rp-note">%s</p>' % AD["report4"] if rid == 4 else ""
    body = '<h2 class="sub-title">시설 운영 보고서 %d</h2>\n<div class="rp-body"><p>분기별 시설 운영 실적을 공개합니다.</p>%s</div>' % (rid, extra)
    return layout("시설 운영 보고서", body, crumb("정보공개", "자료실"), BOARD_CSS)


def page_archive(qs):
    time.sleep(180)  # 크롤러가 끝까지 기다리면 안 되는 페이지
    return layout("과거 자료", "<p>과거 자료</p>")


def page_stats(qs):
    rows = "\n".join("<tr><td>%d</td><td>%s시설</td><td>%d</td><td>%d</td></tr>" % (i, ["체육", "주차", "문화", "공원"][i % 4], i * 7 % 997, i * 13 % 1009)
                     for i in range(1, 5001))
    body = """<h2 class="sub-title">시설 이용 통계</h2>
<p class="st-note">%s</p>
<table class="board-list stats"><caption class="blind">시설별 이용 통계</caption>
<thead><tr><th scope="col">번호</th><th scope="col">시설</th><th scope="col">이용자</th><th scope="col">예약</th></tr></thead>
<tbody>
%s
</tbody></table>
<iframe class="promo-frame" src="/widget/lazy-banner.html" loading="lazy" title="홍보 배너" width="600" height="130"></iframe>""" % (AD["stats"], rows)
    return layout("시설 이용 통계", body, crumb("정보공개", "시설 이용 통계"), BOARD_CSS)


def page_faq(qs):
    qa = [("수영장 자유수영 시간은 언제인가요?", "평일 06시~21시입니다."),
          ("주차 요금 감면 대상은 누구인가요?", "장애인, 국가유공자 등입니다."),
          ("체육관 대관은 어떻게 신청하나요?", "누리집 예약 메뉴에서 신청합니다.")]
    dl = "".join('<dt><a href="#none">%s</a></dt><dd>%s</dd>' % (E(q), E(a)) for q, a in qa)
    sd = html.escape('<p class="sd-ad" style="position:absolute;left:-9999px">%s</p><p>민원 안내 위젯</p>' % AD["srcdoc"], quote=True)
    body = """<h2 class="sub-title">자주 묻는 질문</h2>
<dl class="faq-list">%s</dl>
<div class="frm-srcdoc"><iframe srcdoc="%s" title="민원 안내" width="600" height="60"></iframe></div>""" % (dl, sd)
    return layout("자주 묻는 질문", body, crumb("참여마당", "자주 묻는 질문"))


def page_sitemap(qs):
    links = [("/intro/greeting", "인사말"), ("/intro/vision.do", "비전·목표"), ("/intro/history", "연혁"),
             ("/intro/org", "조직도"), ("/intro/location", "오시는 길"), ("/board/notice/list", "공지사항"),
             ("/egov/cop/bbs/selectArticleList.do?bbsId=BBSMSTR_000000000021", "고시·공고"),
             ("/calendar/month", "행사일정"), ("/data/list", "자료실"), ("/stats/table", "시설 이용 통계"), ("/civil/faq", "자주 묻는 질문")]
    body = '<h2 class="sub-title">사이트맵</h2>\n<ul class="sitemap">%s</ul>' % "".join('<li><a href="%s">%s</a></li>' % (E(u), n) for u, n in links)
    return layout("사이트맵", body, crumb("사이트맵"))


def page_info(name):
    title = {"privacy": "개인정보처리방침", "copyright": "저작권정책"}.get(name)
    if not title:
        return None
    return layout(title, '<h2 class="sub-title">%s</h2><p>가온시설관리공단 %s입니다.</p>' % (title, title), crumb(title))
