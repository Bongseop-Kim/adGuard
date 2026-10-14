# -*- coding: utf-8 -*-
"""폐기된 옛 게시판 (2019년판). 메뉴에 없고 sitemap.xml·robots.txt로만 닿는다.
응답은 EUC-KR(CP949)로 인코딩된다 — serve.py가 ENCODING 값을 보고 인코딩한다.
"""
from .ads import AD
from .layout import E, q1

ENCODING = "euc-kr"
POSTS = {n: "2019년 시설 이용 안내 %d" % n for n in range(1, 13)}
POSTS[8] = "무료 이벤트 안내"
POSTS[12] = "주차장 이용 안내"
BODY = {
    12: '<p>주차장 이용 시간은 09시부터 22시까지입니다.</p>\n<p class="old-note"><font color="#ffffff">%s</font></p>' % AD["old12"],
    8: '<p class="old-txt">%s</p>' % AD["old8_extra"],
}


def _page(title, body):
    return """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=euc-kr">
<title>%s - 가온시설관리공단 (구)</title>
</head>
<body bgcolor="#ffffff">
<div class="old-wrap">
<h1 class="old-logo">가온시설관리공단</h1>
%s
</div>
</body>
</html>""" % (E(title), body)


def page_list(qs):
    rows = "\n".join('<tr><td>%d</td><td class="old-subj"><a href="view.asp?idx=%d">%s</a></td></tr>' % (n, n, E(t))
                     for n, t in sorted(POSTS.items(), reverse=True))
    return _page("자유게시판", '<table class="old-list" border="1">\n%s\n</table>' % rows)


def page_view(qs):
    try:
        n = int(q1(qs, "idx", "0"))
    except ValueError:
        return None
    if n not in POSTS:
        return None
    return _page(POSTS[n], '<h2 class="old-title">%s</h2>\n<div class="old-body">\n%s\n</div>\n<p><a href="list.asp">목록</a></p>'
                 % (E(POSTS[n]), BODY.get(n, "<p>내용이 없습니다.</p>")))
