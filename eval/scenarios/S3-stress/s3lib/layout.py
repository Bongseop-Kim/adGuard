# -*- coding: utf-8 -*-
"""공통 레이아웃 (헤더·GNB·푸터). 모든 UTF-8 페이지가 이 틀을 쓴다."""
import html

HOST, PORT, EXT_PORT = "127.0.0.1", 8130, 8131
BASE = "http://%s:%d" % (HOST, PORT)
EXT = "http://localhost:%d" % EXT_PORT
E = html.escape

# 크롤 범위 밖 외부 링크 (관련 사이트)
FAMILY = [
    ("https://www.gov.kr/", "정부24"), ("https://www.mois.go.kr/", "행정안전부"),
    ("https://www.korea.kr/", "정책브리핑"), ("https://www.epeople.go.kr/", "국민신문고"),
    ("https://www.data.go.kr/", "공공데이터포털"), ("https://www.open.go.kr/", "정보공개포털"),
    ("https://www.alio.go.kr/", "공공기관 경영정보"), ("https://www.cleaneye.go.kr/", "클린아이"),
    ("https://www.acrc.go.kr/", "국민권익위원회"), ("https://www.pipc.go.kr/", "개인정보보호위원회"),
    ("https://www.law.go.kr/", "국가법령정보센터"), ("https://www.elis.go.kr/", "자치법규정보시스템"),
    ("https://www.kogl.or.kr/", "공공누리"), ("https://www.safekorea.go.kr/", "국민재난안전포털"),
    ("https://www.nts.go.kr/", "국세청"), ("https://www.wetax.go.kr/", "위택스"),
    ("https://www.g2b.go.kr/", "나라장터"), ("https://www.work24.go.kr/", "고용24"),
    ("https://www.bokjiro.go.kr/", "복지로"), ("https://www.police.go.kr/", "경찰청"),
    ("https://ecrm.police.go.kr/", "사이버범죄 신고"), ("https://www.ggc.go.kr/", "사행산업통합감독위원회"),
    ("https://gaon-city.example/", "가온시청"), ("https://library.gaon-city.example/", "가온시립도서관"),
    ("https://tour.gaon-city.example/", "가온 관광"),
]

GNB = """<nav class="gnb">
    <ul>
      <li class="m1"><a href="/intro/greeting">공단소개</a>
        <ul class="depth2">
          <li><a href="/intro/greeting">인사말</a></li>
          <li><a href="/intro/vision.do">비전·목표</a></li>
          <li><a href="/intro/history">연혁</a></li>
          <li><a href="/intro/org">조직도</a></li>
          <li><a href="/intro/location">오시는 길</a></li>
        </ul>
      </li>
      <li class="m2"><a href="/board/notice/list">알림마당</a>
        <ul class="depth2">
          <li><a href="/board/notice/list">공지사항</a></li>
          <li><a href="/egov/cop/bbs/selectArticleList.do?bbsId=BBSMSTR_000000000021">고시·공고</a></li>
          <li><a href="/calendar/month">행사일정</a></li>
        </ul>
      </li>
      <li class="m3"><a href="/data/list">정보공개</a>
        <ul class="depth2">
          <li><a href="/data/list">자료실</a></li>
          <li><a href="/stats/table">시설 이용 통계</a></li>
        </ul>
      </li>
      <li class="m4"><a href="/civil/faq">참여마당</a>
        <ul class="depth2">
          <li><a href="/civil/faq">자주 묻는 질문</a></li>
          <li><a href="https://www.epeople.go.kr/" target="_blank">국민신문고</a></li>
        </ul>
      </li>
    </ul>
  </nav>"""


def layout(title, body, crumb="", head=""):
    fam = "".join('<li><a href="%s" target="_blank">%s<span class="blind">새창열림</span></a></li>' % (u, n)
                  for u, n in FAMILY)
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s | 가온시설관리공단</title>
<link rel="stylesheet" href="/css/common.css">
%(head)s
</head>
<body>
<div id="skip"><a class="skip-nav" href="#container">본문 바로가기</a></div>
<header class="header">
  <div class="util"><a href="/">HOME</a><a href="/sitemap.html">사이트맵</a><a href="https://en.gaon-city.example/" target="_blank">ENGLISH</a><a href="%(ext)s/ext/index.html" target="_blank">가온지도</a></div>
  <div class="top">
    <h1 class="logo"><a href="/">가온시설관리공단</a></h1>
    <form class="top-search" action="/board/notice/list" method="get">
      <label class="blind" for="topKeyword">통합검색어 입력</label>
      <input type="hidden" name="sfl" value="wr_subject">
      <input type="text" id="topKeyword" name="stx" placeholder="검색어를 입력하세요">
      <button type="submit">검색</button>
    </form>
  </div>
  %(gnb)s
</header>
<div id="container">
  <div class="content">
    %(crumb)s
    %(body)s
  </div>
</div>
<footer class="footer">
  <div class="inner">
    <div class="family"><strong>관련 사이트</strong><ul class="family-list">%(fam)s</ul></div>
    <p class="foot-link"><a href="/info/privacy.do">개인정보처리방침</a> · <a href="/info/copyright.do">저작권정책</a> · <a href="%(ext)s/ext/partner.html" target="_blank">협력기관</a></p>
    <address>（재）가온시설관리공단 | (12345) 가온시 중앙로 100 | 대표전화 031-000-0000</address>
    <p class="copy">COPYRIGHT (C) GAON FACILITIES MANAGEMENT CORPORATION. ALL RIGHTS RESERVED.</p>
  </div>
</footer>
<script src="/js/common.js"></script>
</body>
</html>""" % {"title": E(title), "head": head, "crumb": crumb, "body": body, "fam": fam, "ext": EXT, "gnb": GNB}


def crumb(*parts):
    return '<div class="location-bar">HOME &gt; %s</div>' % " &gt; ".join(parts)


BOARD_CSS = '<link rel="stylesheet" href="/css/board.css">'


def q1(qs, k, d=""):
    v = qs.get(k)
    return v[0] if v else d
