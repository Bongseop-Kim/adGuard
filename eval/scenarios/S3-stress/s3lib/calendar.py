# -*- coding: utf-8 -*-
"""행사일정: 무한 달력 함정 + 행사 상세.

- /calendar/month?ym=YYYYMM&day=D : 이전·다음 달 링크가 끝없이 이어진다 (날짜 범위 제한 없음)
- /calendar/event?id=N : 행사 상세 (2026년 안에만 존재)
"""
import calendar as _cal

from .ads import AD
from .layout import BOARD_CSS, E, crumb, layout, q1

# (월, 일) -> 행사 id
EVENTS = {(9, 5): 3, (9, 19): 7, (10, 3): 12, (10, 17): 23, (11, 7): 32, (12, 12): 40}
TITLES = {3: "가을 생활체육 대회", 7: "시민 걷기 행사", 12: "가온 한마당 축제", 23: "청소년 진로 박람회",
          32: "공영주차장 무료 개방의 날", 40: "송년 음악회"}
# 행사 상세에 덧붙는 요소 (정답)
EXTRA = {
    7: '<p class="ev-copy">%s</p>' % AD["ev7"],
    23: '<p class="ev-note">%s</p>' % AD["ev23"],
    32: '<p class="ev-note">%s</p>' % AD["ev32"],
}


def _ym(qs):
    raw = q1(qs, "ym", "202610")
    try:
        y, m = int(raw[:4]), int(raw[4:6])
        if not 1 <= m <= 12:
            raise ValueError
    except ValueError:
        y, m = 2026, 10
    return y, m


def page_month(qs):
    y, m = _ym(qs)
    sel = q1(qs, "day")
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    weeks = []
    for wk in _cal.Calendar(firstweekday=6).monthdayscalendar(y, m):
        tds = []
        for d in wk:
            if not d:
                tds.append("<td></td>")
                continue
            ev = EVENTS.get((m, d)) if y == 2026 else None
            evl = '<br><a href="/calendar/event?id=%d">%s</a>' % (ev, TITLES[ev]) if ev else ""
            cls = ' class="sel"' if sel == str(d) else ""
            tds.append('<td%s><a href="/calendar/month?ym=%04d%02d&amp;day=%d">%d</a>%s</td>' % (cls, y, m, d, d, evl))
        weeks.append("<tr>%s</tr>" % "".join(tds))
    body = """<h2 class="sub-title">행사일정</h2>
<div class="cal-nav"><a href="/calendar/month?ym=%04d%02d">이전 달</a> %d년 %d월 <a href="/calendar/month?ym=%04d%02d">다음 달</a></div>
<table class="cal-table">
<caption class="blind">%d년 %d월 행사 달력</caption>
<thead><tr><th scope="col">일</th><th scope="col">월</th><th scope="col">화</th><th scope="col">수</th><th scope="col">목</th><th scope="col">금</th><th scope="col">토</th></tr></thead>
<tbody>
%s
</tbody>
</table>""" % (py, pm, y, m, ny, nm, y, m, "\n".join(weeks))
    return layout("행사일정", body, crumb("알림마당", "행사일정"), BOARD_CSS)


def page_event(qs):
    try:
        ev = int(q1(qs, "id", "0"))
    except ValueError:
        return None
    if ev not in TITLES:
        return None
    body = """<h2 class="sub-title">행사일정</h2>
<div class="ev-banner">
  <p class="ev-title">%s</p>
  %s
</div>
<div class="ev-desc">
  <p>일시: 2026년 가온시 일원 / 문의: 체육사업팀 (031-000-0300)</p>
  %s
</div>""" % (E(TITLES[ev]), EXTRA[ev] if ev == 7 else "", EXTRA[ev] if ev in (23, 32) else "")
    return layout(TITLES[ev], body, crumb("알림마당", "행사일정"), BOARD_CSS)
