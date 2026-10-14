# S2-realistic 명세서

실전 공공 누리집형 테스트 사이트 '새솔시 청소년수련관'. 전자정부 표준프레임워크형 게시판 + 그누보드형 게시판을 흉내 냈다.

- 본 도메인 `http://127.0.0.1:8120` (`site/`), 다른 도메인 `http://localhost:8121` (`site_ext/`)
- 진입 URL: `http://127.0.0.1:8120/`
- HTML 페이지 82개, 정답 61건, 미끼 42건, extra 2건
- 광고 문구는 README '테스트용 광고 문구 방침' 준수(범주 키워드 + `@test_`/`.example`/`010-0000-`/`TEST` 가짜 식별자, 마약·불법대출은 범주어만).

## 실행

```
python serve.py
```

`serve.py`가 정적 파일로 안 되는 동작을 처리한다: 전자정부형 공지의 onclick POST(`fn_egov_inqire_notice`, `fn_egov_select_linkPage`)와 같은 파라미터 GET, 그누보드형 `board.php?bo_table=free&wr_id=N[&cpage=N]`·`&page=N`, 경로의 `;jsessionid=` 제거, `JSESSIONID` 쿠키 설정, `/minwon/apply` 302 리다이렉트.

## 사이트 구조 / 주요 페이지

- 공통 레이아웃: 정부배너·건너뛰기 링크·헤더·GNB(접힌 하위메뉴)·LNB·만족도 위젯·푸터(관련 사이트 접힘). 접근성 숨김 텍스트(`.blind`/`.sound_only`)가 페이지마다 다수.
- 기관소개 5쪽(인사말/연혁/조직/비전/오시는 길): **공통 푸터 위젯에 숨긴 광고(F09·P10)** 가 이 섹션 5쪽에만 삽입 → 페이지마다 1건.
- 알림마당 > 공지사항: 전자정부형. 목록 3쪽, 상세는 onclick POST로 열림(같은 파라미터 GET도 동일 글 반환, 정답 url은 GET URL). 메뉴 링크에 `;jsessionid=`.
- 알림마당 > 자유게시판: 그누보드형(`board.php`). 목록 링크에 `&page=N` 꼬리표, 댓글 `&cpage=N`. 스팸글(145/143/141), Shadow DOM(140), iframe 트릭(135), 댓글 많은 글(130).
- 정보공개(예산/시설/FAQ), 열린민원(302 리다이렉트), 참여마당(상담/설문).
- iframe: 같은 도메인 위젯(공지/통계(display:none)/시설캠/lazyad), 다른 도메인(localhost:8121) 지도 + 중첩 iframe(poi), srcdoc iframe, lazy iframe.
- 메뉴에 없는 옛 게시판 `/archive/data_list.html` → `sitemap.xml`·`robots.txt` Disallow·메인 HTML 주석으로만 도달(P11).
- `robots.txt`, `sitemap.xml`, 사람용 `sitemap.html`, 검색결과(`/search.do`).

## Shadow DOM / 렌더링 전용 항목

다음 정답은 **원본 HTML(html.parser) 검증 대상이 아니며 렌더링 DOM 기준으로만** 유일성·은닉을 확인한다(note에 `[render_only]` 표기):
- `a_002` OFFSCREEN — div.quick-notice > span.live-msg (로드 0.9초 뒤 JS가 빈 span에 문구 삽입 + 외부 CSS 클래스(.js-hidden=display:none)로 숨김. render_only)
- `a_056` TRANSPARENT — p.sad-open (open Shadow DOM 안 p, opacity:0. 렌더링(Playwright 로케이터)만 검증)
- `a_057` OFFSCREEN — p.sad-closed (closed Shadow DOM 안 p, left:-9999px. attachShadow 강제 open 필요. 렌더링만 검증)
- `a_058` OFFSCREEN — div.frm-srcdoc > iframe >>> body > p.sd-ad (srcdoc iframe(가상, src 없음→nth/태그 경로). 안 p left:-9999px. 렌더링만)

## 정답 (61건)

| id | url | location | technique | covers | 의도 |
|---|---|---|---|---|---|
| a_001 | `/` | `iframe[src="http://127.0.0.1:8120/widget/notice.html"] >>> div.ntc-wrap > p.ntc-hidden` | OFFSCREEN | P07 F05 O03 | 같은 도메인 위젯 iframe(상대경로 src→절대). 위젯 안 p가 position:absolute;left:-9999px |
| a_002 | `/` | `div.quick-notice > span.live-msg` | OFFSCREEN | P09 O13 | 로드 0.9초 뒤 JS가 빈 span에 문구 삽입 + 외부 CSS 클래스(.js-hidden=display:none)로 숨김. render_only |
| a_003 | `/` | `iframe[src="http://127.0.0.1:8120/widget/stat.html"] >>> div.stat-box > a.stat-lnk` | OFFSCREEN | P08 O01 | display:none 숨긴 iframe(같은 도메인) 안의 링크. 조상 iframe이 렌더링 안 됨 |
| a_004 | `/intro/greeting.html` | `footer.footer > div.footer-widget > span.fw-txt` | OFFSCREEN | P10 F09 O02 | 기관소개 섹션 공통 푸터 위젯(템플릿 삽입) font-size:0. 이 5쪽에서 페이지마다 1건 |
| a_005 | `/intro/history.html` | `footer.footer > div.footer-widget > span.fw-txt` | OFFSCREEN | P10 F09 O02 | 기관소개 섹션 공통 푸터 위젯(템플릿 삽입) font-size:0. 이 5쪽에서 페이지마다 1건 |
| a_006 | `/intro/organization.html` | `footer.footer > div.footer-widget > span.fw-txt` | OFFSCREEN | P10 F09 O02 | 기관소개 섹션 공통 푸터 위젯(템플릿 삽입) font-size:0. 이 5쪽에서 페이지마다 1건 |
| a_007 | `/intro/vision.html` | `footer.footer > div.footer-widget > span.fw-txt` | OFFSCREEN | P10 F09 O02 | 기관소개 섹션 공통 푸터 위젯(템플릿 삽입) font-size:0. 이 5쪽에서 페이지마다 1건 |
| a_008 | `/intro/location.html` | `footer.footer > div.footer-widget > span.fw-txt` | OFFSCREEN | P10 F09 O02 | 기관소개 섹션 공통 푸터 위젯(템플릿 삽입) font-size:0. 이 5쪽에서 페이지마다 1건 |
| a_009 | `/intro/greeting.html` | `div.greeting-txt > p:nth-of-type(3) > span.blind` | OFFSCREEN | O11 F06 | 사이트 접근성 숨김 클래스 .blind 재사용. 부모 p는 nth-of-type |
| a_010 | `/intro/greeting.html` | `div.greeting-txt > p:nth-of-type(5)` | TRANSPARENT | T01 F06 | 클래스 없는 p, 흰 배경에 color:#ffffff |
| a_011 | `/intro/history.html` | `dl.tbl-hist > dd.hist-note` | OFFSCREEN | O04 | text-indent:-9999px |
| a_012 | `/intro/history.html` | `div.hist-wrap > p.hist-foot` | TRANSPARENT | T06 | -webkit-text-fill-color:transparent (color는 기본값) |
| a_013 | `/intro/organization.html` | `table.tbl-org tr:nth-of-type(4) > td.task > span:nth-of-type(2)` | TRANSPARENT | T04 F06 F07 | 원본에 tbody 없는 표. 짝수행 배경 #eef2f7(tr에서 옴)과 같은 글자색. 클래스 없는 두 번째 span |
| a_014 | `/intro/organization.html` | `p.org-note` | HOMOGLYPH | H05 | 한글음절→한자 亼(스). 숨김 없음, 닮은꼴만 |
| a_015 | `/intro/vision.html` | `div.vision-box > p.slogan-sub` | OFFSCREEN | O05 | transform:scale(0) |
| a_016 | `/intro/vision.html` | `div.vision-box > p.v-note` | OFFSCREEN | O09 | clip-path:inset(100%) |
| a_017 | `/intro/location.html` | `iframe[src="http://localhost:8121/map/embed.html"] >>> div.map-info > p.addr-ad` | TRANSPARENT | P07 T05 | 다른 도메인(localhost:8121) iframe, color:rgba(0,0,0,0) |
| a_018 | `/intro/location.html` | `iframe[src="http://localhost:8121/map/embed.html"] >>> iframe[src="http://localhost:8121/map/poi.html"] >>> ul.poi-list > li:nth-of-type(3)` | JAMO | P07 F04 F05 F06 J01 | 2단 중첩 iframe. 안쪽 src 상대경로(poi.html)→바깥 프레임 기준 절대. 호환자모 나열 |
| a_019 | `/info/facility.html` | `iframe[src="http://127.0.0.1:8120/widget/facility-cam.html"] >>> p.cam-ad` | TRANSPARENT | P07 T08 | 같은 도메인 iframe 안 p, filter:opacity(0) |
| a_020 | `/info/faq.html` | `div.faq-item:nth-of-type(2) > dd.faq-a > span.sound_only` | OFFSCREEN | O11 F06 | 접힌 FAQ(display:none) 안에 .sound_only 추가 은닉(조상 display:none + 자기 sound_only). 접근성 클래스 재사용 |
| a_021 | `/minwon/apply-notice.html` | `div.apply-notice > p.an-hidden` | OFFSCREEN | F10 O03 | GET /minwon/apply 가 302로 /minwon/apply-notice.html 로 이동. 최종 URL 기준. position:fixed;top:-9999px |
| a_022 | `/cop/bbs/selectArticleList.do?bbsId=BBSMSTR_11` | `div.bbs-list > table.tbl tr:nth-of-type(8) > td.subject > a` | HOMOGLYPH | P01 H01 F07 | 목록 제목(전각 영숫자). 원본에 tbody 없는 표, 헤더 tr 포함 8번째 행 |
| a_023 | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1064` | `div.bbs-view > h3.view-tit` | HOMOGLYPH | P02 P06 F08 | onclick POST(fn_egov_inqire_notice)로만 열리는 상세. GET 동일글 반환→url은 GET URL. 상세 제목 전각 |
| a_024 | `/cop/bbs/selectArticleList.do?bbsId=BBSMSTR_11&pageIndex=2` | `div.bbs-list > table.tbl tr:nth-of-type(6) > td.subject > a` | HOMOGLYPH | P04 H02 | 목록 2쪽(POST paging)에만 있는 글 제목. 키릴 문자 혼합 |
| a_025 | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1058` | `div.bbs-view > h3.view-tit` | HOMOGLYPH | P02 P06 | 상세 제목 키릴 혼합 |
| a_026 | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1070` | `div.view-cont > p.cont-extra` | TRANSPARENT | P02 T09 F08 | 본문 visibility:hidden. onclick POST로 열림 |
| a_027 | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1052` | `div.view-cont > p.cont-extra` | JAMO | P02 J05 P05 | 첫가끝(조합형) 자모 '카지노'(화면엔 정상 음절). 쿼리값만 다른 상세 |
| a_028 | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1050` | `div.view-cont > p.cont-extra` | TRANSPARENT | P02 T07 F08 | 본문 opacity:0. 목록 3쪽에서 도달 |
| a_029 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-o06` | OFFSCREEN | P02 O06 F11 | margin-left:-9999px. 목록 링크가 &page=1 꼬리표 → 같은 글 여러 URL(F11), 대표는 wr_id만 |
| a_030 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-o07` | OFFSCREEN | O07 | width/height 0 + overflow:hidden |
| a_031 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-o08` | OFFSCREEN | O08 | max-height:0 + overflow:hidden |
| a_032 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-o10` | OFFSCREEN | O10 | letter-spacing 큰 음수(-0.6em) |
| a_033 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.clipbox > p.s-o12` | OFFSCREEN | O12 | overflow:hidden height:0 조상 바깥(absolute top:60px) |
| a_034 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-t02` | TRANSPARENT | T02 | color:#eee (대비 1.16) |
| a_035 | `/bbs/board.php?bo_table=free&wr_id=145` | `p.s-t03row > font` | TRANSPARENT | T03 | 레거시 <font color=#ffffff> |
| a_036 | `/bbs/board.php?bo_table=free&wr_id=145` | `div.spam-body > p.s-t10` | TRANSPARENT | T10 | 흰→흰 그라데이션 배경 위 흰 글자 |
| a_037 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > p.s-f01` | TRANSPARENT | P02 F01 T07 | 한 요소에 opacity:0 + left:-9999px → 기법별 2건(TRANSPARENT) |
| a_038 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > p.s-f01` | OFFSCREEN | F01 O03 | 같은 요소 OFFSCREEN(left:-9999px) |
| a_039 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > div.s-wrap1` | OFFSCREEN | F03 | 부모 div display:none(광고만 감쌈) → 부모도 출력 |
| a_040 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.s-wrap1 > a` | OFFSCREEN | F03 | 부모 숨김, 자식 a 텍스트 → 자식도 출력 |
| a_041 | `/bbs/board.php?bo_table=free&wr_id=143` | `span.s-f13` | OFFSCREEN | F13 | display:none + 수학 영숫자 → OFFSCREEN 1건 |
| a_042 | `/bbs/board.php?bo_table=free&wr_id=143` | `span.s-f13` | HOMOGLYPH | F13 H03 | 같은 요소 HOMOGLYPH(수학용 영숫자 𝐂𝐀𝐒𝐈𝐍𝐎) |
| a_043 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > p.s-f02` | HOMOGLYPH | H04 F02 | 원문자 ⓣⓞⓣⓞ 같은 기법 문자열 2개 → 1건 |
| a_044 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > p.s-h06` | HOMOGLYPH | H06 | 숫자→한자 丨(1)己(2)彐(3) |
| a_045 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.spam-body > p.s-h09` | HOMOGLYPH | H09 | 라틴 leet cas1no b3t |
| a_046 | `/bbs/board.php?bo_table=free&wr_id=143` | `div.col-box > span` | OFFSCREEN | F14 | 해시 클래스 css-1x2y3z 는 불안정 → 상위 안정 경로+태그로 지정 |
| a_047 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-j02` | JAMO | P02 J02 | 호환 자모 + 점 구분자 |
| a_048 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-j04` | JAMO | J04 | 초성만(ㅋㅈㄴ=카지노, ㅌㅌ=토토) + 텔레그램 신호 |
| a_049 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-j06` | JAMO | J06 | 반각 자모(U+FFA0~)로 '토토' |
| a_050 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-j07` | JAMO | J07 | 받침 노이즈(ㅋㅏㄹㅈㅣㄴㅗ=칼지노) |
| a_051 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-j08` | JAMO | J08 | 자모 사이 보이지 않는 문자(U+200B) |
| a_052 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-f12a` | JAMO | J03 F12 | 가로 쪼개기(ㅋ+ㅏ) |
| a_053 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-f12a` | HOMOGLYPH | H08 F12 | 같은 요소에서 r→ㅏ 닮은꼴 |
| a_054 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-f12b` | JAMO | J04 F12 | 초성 ㅌ(토토) |
| a_055 | `/bbs/board.php?bo_table=free&wr_id=141` | `div.spam-body > p.s-f12b` | HOMOGLYPH | H07 F12 | 같은 요소에서 ロ(가나)→ㅁ 닮은꼴 |
| a_056 | `/bbs/board.php?bo_table=free&wr_id=140` | `p.sad-open` | TRANSPARENT | P13 T07 | open Shadow DOM 안 p, opacity:0. 렌더링(Playwright 로케이터)만 검증 |
| a_057 | `/bbs/board.php?bo_table=free&wr_id=140` | `p.sad-closed` | OFFSCREEN | P13 O03 | closed Shadow DOM 안 p, left:-9999px. attachShadow 강제 open 필요. 렌더링만 검증 |
| a_058 | `/bbs/board.php?bo_table=free&wr_id=135` | `div.frm-srcdoc > iframe >>> body > p.sd-ad` | OFFSCREEN | P12 F04 O03 | srcdoc iframe(가상, src 없음→nth/태그 경로). 안 p left:-9999px. 렌더링만 |
| a_059 | `/bbs/board.php?bo_table=free&wr_id=135` | `iframe[src="http://127.0.0.1:8120/widget/lazyad.html"] >>> p.lz-ad` | OFFSCREEN | P12 P07 O03 | lazy iframe(페이지 하단, 스크롤해야 로드). 안 p left:-9999px |
| a_060 | `/bbs/board.php?bo_table=free&wr_id=130&cpage=2` | `ul.cmt-list > li:nth-of-type(5) > p.cmt-txt` | OFFSCREEN | P03 O11 | 댓글 2쪽(cpage=2)에만 있는 숨김 댓글(.sound_only) |
| a_061 | `/archive/data_list.html` | `div.old-wrap > p.old-ad` | OFFSCREEN | P11 O03 | 메뉴에 없는 옛 게시판. sitemap.xml·robots Disallow·index 주석으로만 도달 |

## 미끼 (42건, result.json 에 나오면 오탐)

| id | url | location | technique | covers | 의도 |
|---|---|---|---|---|---|
| - | `/` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/` | `ul.util > li:nth-of-type(2) > a > span.blind` | - | D01 | '새창열림' 접근성 텍스트 |
| - | `/` | `form.top-search > fieldset > label.blind` | - | D08 | 검색어 입력 라벨(숨김이지만 광고 아님) |
| - | `/` | `nav.gnb > ul.gnb-list > li:nth-of-type(1) > div.gnb-sub > ul > li:nth-of-type(1) > a` | - | D02 | 접힌 GNB 하위메뉴 '인사말' |
| - | `/` | `div.main-popup > div.pop-cont > p.pop-txt` | - | D02 | 닫힌 팝업(display:none) 정상 공지 |
| - | `/` | `div.main-tab > div.tab-panel > ul.press-list > li:nth-of-type(1)` | - | D02 | 닫힌 탭 패널 보도자료 |
| - | `/` | `section.campaign > p.cp-txt` | - | D05 | '대포통장 매매·대여 처벌' 정상 캠페인(보임) |
| - | `/` | `section.campaign > p.cp-txt2` | - | D05 | '불법도박 예방 상담 1336' 정상 안내(보임) |
| - | `/intro/greeting.html` | `div.skip-nav > a:nth-of-type(2)` | - | D01 | 주메뉴 바로가기 |
| - | `/intro/greeting.html` | `aside.lnb > ul.lnb-list > li.on > a > span.blind` | - | D01 | '현재 메뉴' 접근성 텍스트 |
| - | `/intro/history.html` | `div.hist-wrap > p.txt-gray2` | - | D06 | #ddd 흐린 안내문(대비 1.36, 읽힘) |
| - | `/intro/organization.html` | `div.org-intro > p.hanja` | - | D03 | 정상 한자·전각괄호(（주）,株式會社,公團) |
| - | `/intro/organization.html` | `table.tbl-org > caption.blind` | - | D01 | 표 캡션 접근성 텍스트 |
| - | `/intro/vision.html` | `div.vision-box > ul.v-goal > li:nth-of-type(1)` | - | D03 | 원문자 ① 목록 번호 |
| - | `/info/budget.html` | `p.unit.txt-gray` | - | D06 | #999 회색 안내문(대비 2.85, 읽힘) |
| - | `/info/faq.html` | `div.faq-item:nth-of-type(1) > dd.faq-a` | - | D02 | 접힌 FAQ 답변(정상) |
| - | `/info/faq.html` | `div.faq-item:nth-of-type(3) > dd.faq-a` | - | D02 | 접힌 FAQ 답변(정상) |
| - | `/event/chat.html` | `div.chat-note > p:nth-of-type(1)` | - | D04 | 정상 자모 ㅠㅠ |
| - | `/event/chat.html` | `p.chat-help` | - | D04 | 정상 자모 목록기호 ㄱ. ㄴ. ㄷ. |
| - | `/event/survey.html` | `p.print-guide` | - | D08 | display:none 인쇄용 안내(숨김이지만 광고 아님) |
| - | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1068` | `div.view-cont > p.cont-txt:nth-of-type(3)` | - | D05 | '불법도박 예방 교육' 정상 공지(보임) |
| - | `/bbs/board.php?bo_table=free&wr_id=150` | `ul.cmt-list > li:nth-of-type(2) > p.cmt-txt` | - | D04 | 정상 자모 ㅋㅋㅋ ㅠㅠ 댓글 |
| - | `/bbs/board.php?bo_table=free` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=145` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=143` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=141` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=140` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=135` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=130` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/cop/bbs/selectArticleList.do?bbsId=BBSMSTR_11` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1064` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/intro/vision.html` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/info/budget.html` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/event/index.html` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/minwon/` | `div.skip-nav > a:nth-of-type(1)` | - | D01 | 본문 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=145` | `div.skip-nav > a:nth-of-type(2)` | - | D01 | 주메뉴 바로가기(건너뛰기 링크) |
| - | `/bbs/board.php?bo_table=free&wr_id=143` | `div.skip-nav > a:nth-of-type(2)` | - | D01 | 주메뉴 바로가기(건너뛰기 링크) |
| - | `/cop/bbs/selectArticleDetail.do?bbsId=BBSMSTR_11&nttId=1058` | `div.skip-nav > a:nth-of-type(2)` | - | D01 | 주메뉴 바로가기(건너뛰기 링크) |
| - | `/intro/vision.html` | `nav.gnb > ul.gnb-list > li:nth-of-type(2) > div.gnb-sub > ul > li:nth-of-type(1) > a` | - | D02 | 접힌 GNB 하위메뉴 |
| - | `/info/faq.html` | `nav.gnb > ul.gnb-list > li:nth-of-type(2) > div.gnb-sub > ul > li:nth-of-type(1) > a` | - | D02 | 접힌 GNB 하위메뉴 |
| - | `/bbs/board.php?bo_table=free&wr_id=140` | `nav.gnb > ul.gnb-list > li:nth-of-type(2) > div.gnb-sub > ul > li:nth-of-type(1) > a` | - | D02 | 접힌 GNB 하위메뉴 |
| - | `/intro/organization.html` | `p.hanja` | - | D03 | 정상 한자·전각괄호(2회째) |

## extra (2건, result_extra.json 에만)

| url | location | extra | covers | 의도 |
|---|---|---|---|---|
| `/bbs/board.php?bo_table=free&wr_id=150` | `ul.cmt-list > li:nth-of-type(3) > p.cmt-txt` | VISIBLE_AD | D07 | 숨김·변형 없이 그냥 보이는 도박 광고 댓글 → result_extra |
| `/bbs/board.php?bo_table=free&wr_id=147` | `div.bo_v_con > p.ad-plain` | VISIBLE_AD | D07 | 숨김·변형 없이 그냥 보이는 도박 광고 글 → result_extra |

## ID별 등장 횟수

| ID | 횟수 | ID | 횟수 | ID | 횟수 | ID | 횟수 |
|---|---|---|---|---|---|---|---|
| P01 | 1 | P02 | 8 | P03 | 1 | P04 | 1 |
| P05 | 1 | P06 | 2 | P07 | 5 | P08 | 1 |
| P09 | 1 | P10 | 5 | P11 | 1 | P12 | 2 |
| P13 | 2 | O01 | 1 | O02 | 5 | O03 | 7 |
| O04 | 1 | O05 | 1 | O06 | 1 | O07 | 1 |
| O08 | 1 | O09 | 1 | O10 | 1 | O11 | 3 |
| O12 | 1 | O13 | 1 | T01 | 1 | T02 | 1 |
| T03 | 1 | T04 | 1 | T05 | 1 | T06 | 1 |
| T07 | 3 | T08 | 1 | T09 | 1 | T10 | 1 |
| H01 | 1 | H02 | 1 | H03 | 1 | H04 | 1 |
| H05 | 1 | H06 | 1 | H07 | 1 | H08 | 1 |
| H09 | 1 | J01 | 1 | J02 | 1 | J03 | 1 |
| J04 | 2 | J05 | 1 | J06 | 1 | J07 | 1 |
| J08 | 1 | F01 | 2 | F02 | 1 | F03 | 2 |
| F04 | 2 | F05 | 2 | F06 | 5 | F07 | 2 |
| F08 | 3 | F09 | 5 | F10 | 1 | F11 | 1 |
| F12 | 4 | F13 | 2 | F14 | 1 | D01 | 21 |
| D02 | 8 | D03 | 3 | D04 | 3 | D05 | 3 |
| D06 | 2 | D07 | 2 | D08 | 2 |  |  |

모든 P·O·T·H·J·F·D ID가 1회 이상, D는 2회 이상 등장(누락 없음).

## 규칙상 애매해서 판단한 점

- **POST 전용 글의 url(F08)**: 전자정부형 상세는 onclick POST로 열지만, 같은 `bbsId`·`nttId` GET도 같은 글을 반환하도록 `serve.py`를 구현했다(03 §8). 정답 url은 GET URL(`selectArticleDetail.do?bbsId=..&nttId=..`).
- **같은 글 여러 URL(F11)**: 그누보드 목록 링크의 `&page=N` 꼬리표, 메뉴의 `;jsessionid=` 는 같은 글/페이지를 가리킨다. 정답 url은 대표(꼬리표 없는) URL로 적었다.
- **iframe 내부 항목의 url**: 상위 페이지 URL로 적고 location은 `iframe[src="절대URL"] >>> ...`. iframe src가 상대경로면 그 프레임 기준 절대 URL로 변환(F05). 중첩은 `>>>` 반복(F04).
- **공통 영역(F09/P10)**: 채점 단위가 url+location+technique이므로 페이지마다 1건으로 집계. 정답 폭증을 막으려고 기관소개 5쪽에만 공통 위젯 광고를 넣었다.
- **부모 숨김+자식 텍스트(F03)**: 광고만 감싼 `display:none` 부모(`div.s-wrap1`)와 자식 `a` 를 둘 다 정답으로 등록(04 §4.3 기대점수).
- **Shadow DOM / srcdoc / JS 삽입**: 원본 HTML에 요소가 없거나 src 속성이 없어 `iframe[src]` 규칙을 쓸 수 없으므로 렌더링 DOM 기준으로만 검증(위 render_only 목록). closed shadow 는 `attachShadow` 강제 open 후 확인.
- **srcdoc iframe location**: src가 없어 `div.frm-srcdoc > iframe >>> ...` 로 표기(nth/태그 경로). 실제 평가 정답과 표기가 다를 수 있어 render_only로 둔다.
- **접근성 숨김 텍스트는 미끼**: `.blind`/`.sound_only`/'본문 바로가기' 등은 숨김 신호가 있어도 광고성이 없으면 미끼(D01/D08). 같은 클래스를 광고 은닉에도 재사용(O11)해 광고성으로만 갈리게 했다.
- **extra(D07)**: 숨김·변형 없이 그냥 보이는 도박 광고(댓글/글)는 4종 기법이 아니므로 result_extra.json 대상.
