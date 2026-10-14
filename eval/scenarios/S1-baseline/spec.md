# S1-baseline: 모집요강 예시 재현형 GET 게시판

- 목적: 모집요강 13쪽 예시 4건(JAMO, HOMOGLYPH, TRANSPARENT, iframe OFFSCREEN)과 **같은 구조**를 재현하고, 기본 변형을 한 번씩 넣는다.
- 실행: `python serve.py` → 본 도메인 `http://127.0.0.1:8110/`, 다른 도메인 `http://localhost:8111/`
- 진입 URL: `http://127.0.0.1:8110/`
- 가상 기관: 한빛시 시민소통광장 (헤더·건너뛰기 링크·주메뉴(하위 메뉴 접힘)·검색·푸터를 갖춘 공통 레이아웃)
- 건수: **정답 26건, 미끼 19건, extra 1건**
- 광고 문구는 README "테스트용 광고 문구 방침"을 따른다 (`@test_` 텔레그램, `.test` 도메인, `TEST` 가입코드, 마약·성인은 범주 키워드만).

## URL → 파일

`serve.py`는 쿼리가 있는 주소를 `site/<경로>/<키>-<값>.html`로 연결한다(예: `/board/view?id=1024` → `site/board/view/id-1024.html`). 확장자 없는 주소는 `.html`을 붙여 찾는다.

## 페이지 (크롤링 대상 14개 + iframe 전용 3개)

| URL | 내용 | 정답 | 미끼 |
|---|---|---|---|
| `/` | 메인. 공지 최신글, 바로가기, 홍보 배너 iframe(`/widget/banner` → `localhost:8111/ext/slide` 중첩), 닫힌 레이어 팝업 | 1 | 3 |
| `/intro` | 시장 인사말 (①②③) | 0 | 1 |
| `/location` | 오시는 길 (표, 회색 안내, 인쇄용 문구) | 0 | 2 |
| `/notice/list` | 공지사항 목록 (4건) | 0 | 0 |
| `/notice/view?no=1~4` | 공지 상세 (위젯 없는 템플릿). 불법도박 예방 교육, 대포통장 주의, （재）협약, 공모 결과 | 0 | 6 |
| `/board/list` | 자유게시판 목록. 공지 4행 + 글 6행, 원본에 `tbody` 없음 | 1 | 2 |
| `/board/view?id=1192` | 도서관 휴관일 건의. 본문 숨김 4건, 댓글 변형 4건 | 8+1 | 1 |
| `/board/view?id=1180` | 버스 노선 의견. 예시 f_003·f_004 재현 | 1+1 | 2 |
| `/board/view?id=1027` | 스팸 글 `ｍｅｇａ－ＢＥＴ 첫충 30％ 지급` | 3+1 | 0 |
| `/board/view?id=1024` | 교통안전 교육 문의. 예시 f_001 재현 | 2+1 | 1 |
| `/board/view?id=1020` | 산책로 정비 요청. 댓글 숨김·자모, 보이는 광고 | 2+1 | 0 (extra 1) |
| `/board/view?id=1018` | 주차장 문의. 댓글 `ㅋr지노` | 2+1 | 2 |
| (iframe) `/widget/notice` | 게시판 상세 템플릿의 공지 위젯. 해킹 삽입 `span.hidden-link` | — | — |
| (iframe) `/widget/banner` | 메인 배너. 안에 다른 도메인 iframe | — | — |
| (iframe) `localhost:8111/ext/slide` | 협력기관 슬라이드 (다른 출처) | — | — |

"+1"은 공통 위젯 정답(상세 페이지마다 1건, F09).

## 정답 (26건)

| id | url | location | technique | 의도 | covers |
|---|---|---|---|---|---|
| a_001 | `/board/list` | `div.board-list > table.tbl-board tr:nth-of-type(7) > td.title > a` | HOMOGLYPH | 예시 f_002. 전각 `ｍｅｇａ－ＢＥＴ`. 원본에 tbody가 없어 tbody 구간은 자손 결합자 | P01 H01 F06 F07 |
| a_002 | `?id=1027` | `div.board-view > div.view-head > h3.view-title` | HOMOGLYPH | 같은 스팸 글의 상세 제목 | P02 P05 H01 |
| a_003 | `?id=1027` | `div.article-body > div.tag-cloud > a:nth-of-type(1)` | OFFSCREEN | 부모 `display:none`, 자식 a에 텍스트 | P02 O01 F03 F06 |
| a_004 | `?id=1027` | `div.article-body > div.tag-cloud > a:nth-of-type(2)` | OFFSCREEN | 위와 같음 | P02 O01 F03 F06 |
| a_005 | `?id=1024` | `div.notice-board > span.visually-hidden` | JAMO | 예시 f_001. `ㅋㅏㅈㅣㄴㅗ ㅂㅗㄴㅓㅅㅡ` 두 문자열 → 1건 | P02 P05 J01 F02 |
| a_006 | `?id=1024` | `div.notice-board > span.visually-hidden` | OFFSCREEN | 사이트 숨김 클래스 재사용(1px + clip) | P02 O11 |
| a_007 | `?id=1180` | `div.article-body > p.desc > span` | TRANSPARENT | 예시 f_003. 흰 배경에 `#ffffff` | P02 P05 T01 |
| a_008 | `?id=1192` | `div.article-body > p:nth-of-type(2) > span` | TRANSPARENT | `#eeeeee` (대비 1.16) | P02 T02 F06 |
| a_009 | `?id=1192` | `div.article-body > p:nth-of-type(3) > span` | TRANSPARENT | `rgba(0,0,0,0)` | P02 T05 F06 |
| a_010 | `?id=1192` | `div.article-body > p.ref-note` | OFFSCREEN | `text-indent:-9999px` | P02 O04 |
| a_011 | `?id=1192` | `div.article-body > p:nth-of-type(5) > span` | TRANSPARENT | `visibility:hidden` (p.ref-note도 p라서 5번째) | P02 T09 F06 |
| a_012 | `?id=1192` | `ul.comment-list > li:nth-of-type(2) > p.cmt-text` | HOMOGLYPH | 키릴 `саsіnо` 댓글 | P03 H02 F06 |
| a_013 | `?id=1192` | `ul.comment-list > li:nth-of-type(3) > p.cmt-text` | HOMOGLYPH | 원문자 `ⓣⓞⓣⓞ`, `ⓑⓔⓣ` 2개 → 1건 | P03 H04 F02 |
| a_014 | `?id=1192` | `ul.comment-list > li:nth-of-type(5) > p.cmt-text` | HOMOGLYPH | 한자 닮은꼴 `亼포츠`, `卫액` | P03 H05 |
| a_015 | `?id=1192` | `ul.comment-list > li:nth-of-type(6) > p.cmt-text` | JAMO | 초성 `ㅋㅈㄴ ㅂㅋㄹ` | P03 J04 |
| a_016 | `?id=1020` | `ul.comment-list > li:nth-of-type(2) > p.cmt-text > span` | OFFSCREEN | 정상 댓글 뒤 `font-size:0` (대포통장) | P03 O02 F06 |
| a_017 | `?id=1020` | `ul.comment-list > li:nth-of-type(3) > p.cmt-text` | JAMO | 점 구분 `ㅌ.ㅗ.ㅌ.ㅗ` | P03 J02 |
| a_018 | `?id=1018` | `ul.comment-list > li:nth-of-type(3) > p.cmt-text` | JAMO | `ㅋr지노` 가로 쪼개기 | P03 J03 F12 |
| a_019 | `?id=1018` | 위와 같음 | HOMOGLYPH | `r`(ㅏ 닮은꼴) → 같은 요소 2건째 | P03 H08 F12 |
| a_020 | `/` | `iframe[src="http://127.0.0.1:8110/widget/banner"] >>> iframe[src="http://localhost:8111/ext/slide"] >>> div.slide-item > span.cap` | TRANSPARENT | 중첩 iframe(같은 도메인 상대 src → 다른 도메인) 안 `opacity:0`. url은 최상위 페이지 | P07 T07 F04 F05 |
| a_021~026 | `?id=1192,1180,1027,1024,1020,1018` | `iframe[src="http://127.0.0.1:8110/widget/notice"] >>> div.wrap > span.hidden-link` | OFFSCREEN | 예시 f_004. 상세 템플릿 공통 위젯(src는 상대 경로 `/widget/notice`), `position:absolute; left:-9999px`. 페이지마다 1건 | P07 P10 O03 F05 F09 |

## 미끼 (19건)

| url | location | 의도 | covers |
|---|---|---|---|
| `/` | `ul.skip-nav > li:nth-of-type(1) > a` | 본문 바로가기 | D01 |
| `/` | `nav.gnb > … li.gnb-item:nth-of-type(3) > ul.sub-menu > li:nth-of-type(1) > a` | 접힌 하위 메뉴 | D02 |
| `/` | `div.layer-popup > div.pop-body > p.pop-txt` | 닫힌 팝업 | D02 |
| `/board/list` | `div.board-list > table.tbl-board > caption.blind` | 표 caption 숨김 | D01 D08 |
| `/board/list` | `form.top-search > fieldset > label.blind` | 검색 라벨 | D08 |
| `?id=1018` | 댓글 li 1, 2 | `ㅠㅠ`, `ㅋㅋㅋ` | D04 ×2 |
| `?id=1192` | 댓글 li 4 | `ㅇㅋ`, `ㅎㅎ` | D04 |
| `?id=1024` | `ul.view-info > li:nth-of-type(1) > span.blind` | '작성자' 라벨 | D01 |
| `?id=1180` | `iframe[…widget/notice] >>> div.wrap > a.more > span.blind` | iframe 안 접근성 텍스트 | D01 |
| `?id=1180` | `footer.footer > div.inner > a.btn-top` | '맨 위로' (text-indent) | D01 |
| `/notice/view?no=4` | 제목, `p.list-jamo`, `p.update-info` | 불법도박 예방 교육 공지(보임), `ㄱ. ㄴ. ㄷ.`, 회색 #999 | D05 D04 D06 |
| `/notice/view?no=3` | `div.article-body > p:nth-of-type(2) > span.blind` | 숨겨진 '불법도박 신고 ☎1336' (부정 문맥) | D05 D08 |
| `/notice/view?no=2` | `div.article-body > p:nth-of-type(1)` | `（재）`, `株式會社` | D03 |
| `/intro` | `div.greeting > p.vision` | `①②③` | D03 |
| `/location` | `p.note-gray`, `p.print-only` | 회색 안내, 인쇄용 문구 | D06 D08 |

## extra (1건)

| url | location | 의도 |
|---|---|---|
| `?id=1020` | `ul.comment-list > li:nth-of-type(4) > p.cmt-text` | 숨김·변형 없이 보이는 도박 광고 댓글 → `result_extra.json`에만 (D07) |

## 커버리지 집계 (answers + decoys + extra의 covers 기준)

| ID | 횟수 | ID | 횟수 | ID | 횟수 | ID | 횟수 |
|---|---|---|---|---|---|---|---|
| P01 | 1 | O01 | 2 | H01 | 2 | F02 | 2 |
| P02 | 10 | O02 | 1 | H02 | 1 | F03 | 2 |
| P03 | 8 | O03 | 6 | H04 | 1 | F04 | 1 |
| P05 | 3 | O04 | 1 | H05 | 1 | F05 | 7 |
| P07 | 8 | O11 | 1 | H08 | 1 | F06 | 8 |
| P10 | 6 | T01 | 1 | J01 | 1 | F07 | 1 |
| | | T02 | 1 | J02 | 1 | F09 | 6 |
| | | T05 | 1 | J03 | 1 | F12 | 2 |
| | | T07 | 1 | J04 | 1 | | |
| | | T09 | 1 | | | | |

| D01 | D02 | D03 | D04 | D05 | D06 | D07 | D08 |
|---|---|---|---|---|---|---|---|
| 5 | 2 | 2 | 4 | 2 | 2 | 1 | 4 |

(P05는 상세 페이지 정답 대표 3건에만 표기. 실제로는 `view?id=` 상세 페이지 정답 전부가 P05에 해당한다. H08은 담당 외 ID지만 `ㅋr지노`의 r이 해당해 표기했다.)

## 판단한 점

- **예시 f_001(`span.visually-hidden`)은 JAMO + OFFSCREEN 2건**으로 했다. 모집요강 예시는 JAMO만 적었지만, 이 사이트에서 `.visually-hidden`은 실제로 글자를 숨기므로 "숨김 + 변형 = 기법별 1건" 규칙(04 §4)을 따랐다.
- **F03(부모 숨김)**: `div.tag-cloud`가 광고 링크 2개를 감싸므로 텍스트를 가진 자식 `a`만 정답이다. 부모 `div`는 정답도 미끼도 아니다(출력하면 오탐으로 셈).
- **iframe location**: 원본 src는 상대 경로(`/widget/notice`, `/widget/banner`)이고 location에는 절대 URL로 적었다. 채점·검증은 iframe의 src를 문서 URL 기준으로 절대화해 비교한다(문자 그대로의 CSS 속성 선택자로는 맞지 않음).
- **위젯 페이지 단독 보고 없음**: `/widget/notice`는 iframe으로만 닿으므로 그 URL 자체로 보고한 항목은 정답에 없다.
- **표 행**: `tr:nth-of-type(7)`은 thead 행을 세지 않는다(다른 부모). 렌더링 DOM(tbody 자동 삽입)과 html.parser 모두에서 1개다.
- 정답 건수가 요청(약 20)보다 많은 26건인 이유: 공통 위젯이 상세 페이지 6개에 각 1건씩 나오기 때문이다(F09).
