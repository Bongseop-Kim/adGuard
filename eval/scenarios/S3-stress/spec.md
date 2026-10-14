# S3-stress: 시간·규모 측정용 대형 공공 누리집

- 사이트: 가온시설관리공단 (가상)
- 실행: `python serve.py` → 진입 URL `http://127.0.0.1:8130/` (다른 도메인 `http://localhost:8131/`)
- 목적: 검출 시간 20점(목표 10분 이내, 상한 20분)과 대형 사이트에서의 재현율. 크롤러를 함정에 빠뜨리는 구조를 일부러 넣었다.
- 규모: 정답 35, 미끼 14(범위 밖 1건 포함), extra 2

## 파일 구조

| 파일 | 내용 |
|---|---|
| `serve.py` | 라우팅, POST 처리, `;jsessionid` 제거, 302, 404·500, EUC-KR 인코딩, 다른 도메인 서버 |
| `s3lib/ads.py` | 테스트 광고 문구 (eval/README.md 문구 방침) |
| `s3lib/layout.py` | 공통 헤더·GNB·푸터 (관련 사이트 외부 링크 25개) |
| `s3lib/notice.py` | 공지사항 260건 26쪽 (정답 15건) |
| `s3lib/egov.py` | 고시·공고 48건, 전자정부식 POST 게시판 |
| `s3lib/calendar.py` | 무한 달력 + 행사 상세 |
| `s3lib/old.py` | 폐기된 옛 게시판 (EUC-KR, sitemap·robots로만 닿음) |
| `s3lib/pages.py` | 메인, 기관소개, 자료실, 통계(대형 DOM), FAQ, 사이트맵 |

## 시간 측정 포인트 (크롤러 함정)

| 함정 | 동작 | 단순하게 크롤링하면 |
|---|---|---|
| 공지 목록 조합 | 분류 5 × 정렬 3 × 방향 2 × 인기검색어 5 × 26쪽 | 목록 URL 수천 개. 정적 BFS로 목록만 1,458개 확인 |
| 공지 상세 꼬리표 | 목록의 상세 링크에 `sca, sfl, stx, sst, sod, page`가 붙음 | 같은 글 260개가 수천 개 URL로 보임. 경로별 상한(400)으로 자르면 깊은 글 13개를 놓침 (직접 확인). `<link rel="canonical">`과 이전글·다음글(id만) 링크로 정규화해야 함 |
| 무한 달력 | `?ym=` 이전·다음 달이 끝없이 이어짐, `&day=` 날짜 링크 | 끝나지 않음. 행사(정답)는 2026년 9~12월에만 있음 |
| 느린 보고서 | `/data/report?id=1~6`, 1~5초 지연 | 직렬 크롤링이면 14초 손해 |
| 타임아웃 페이지 | `/data/archive`, 180초 동안 응답 없음 | 페이지 타임아웃이 없으면 3분 정지 |
| 깨진 링크 | `/files/*.hwp` 404, `/data/error` 500, sitemap의 `/info/privacy_2019.do` 404 | 오류 처리 확인 |
| 대형 DOM | `/stats/table` 5,000행 표(약 340KB), 맨 아래 lazy iframe | 렌더링·분석 시간, 스크롤해야 iframe이 로드됨 |
| 외부 링크 | 푸터 관련 사이트 25개 + `localhost:8131/ext/partner.html` | 범위 밖으로 나가면 시간 낭비 + 오탐 |

정적 BFS 기준(정규화 포함) 1,688 URL을 15초에 방문했다. 렌더링 크롤러에서는 정규화와 상한이 없으면 30분을 넘길 수 있다.

## 정답 (35건)

| # | 페이지 | location | 기법 | 커버 ID | 의도 |
|---|---|---|---|---|---|
| 1 | 공지 1002 | `div.view-content > div.ref-box` | OFFSCREEN | P02 P04 O05 F11 | `transform:translateX(-9999px)` |
| 2 | 공지 1009 | `div.view-content > p.addr-note` | OFFSCREEN | P02 P04 O06 | `margin-left:-9999px` |
| 3 | 공지 1137 | `div.info-box > span.tail-txt` | TRANSPARENT | P04 T04 | 글자색 = 부모 배경색 `#eef3f8` |
| 4·5 | 공지 1088 | `div.view-content > div.sr-box` | OFFSCREEN + HOMOGLYPH | O07 H03 F13 | 1px + overflow, 수학용 굵은 영숫자 |
| 6 | 공지 1045 | `div.view-content > div.fold-txt` | OFFSCREEN | O08 | `max-height:0` |
| 7·8 | 공지 1201 | `div.view-content > span.clip-txt` | OFFSCREEN + HOMOGLYPH | O09 H09 F13 | `clip`, leet `s1ot b3t` |
| 9 | 공지 1176 | `div.view-content > p.ls-txt` | OFFSCREEN | O10 | `letter-spacing:-30px`. 첫 글자만 남고 나머지는 왼쪽 화면 밖 (그누보드 실사례와 같은 모양) |
| 10 | 공지 1150 | `div.clip-wrap > span.out-txt` | OFFSCREEN | O12 | 높이 26px `overflow:hidden` 조상 바깥 |
| 11 | 공지 1033 | `div.view-content > p.ntc-meta` | OFFSCREEN | O13 | 외부 CSS(board.css)에서만 숨김 |
| 12 | 공지 1240 | `div.view-content > p.js-tail` | OFFSCREEN | O13 P09 | JS가 style 속성 지정 |
| 13 | 공지 1111 | `div.view-content > p.fill-txt` | TRANSPARENT | T06 | `-webkit-text-fill-color:transparent` |
| 14 | 공지 1260 | `div.view-content > p.late-msg` | TRANSPARENT | T07 P09 | 1.5초 뒤 JS가 텍스트 삽입, 외부 CSS `opacity:0` |
| 15 | 공지 1066 | `div.view-content > div` | TRANSPARENT | T05 F14 | 요청마다 바뀌는 해시 클래스 |
| 16 | 고시 7 (POST) | `div.view_cont > p.ref-note` | TRANSPARENT | P06 F08 T08 | `filter:opacity(0)`, 목록 5쪽 |
| 17 | 고시 19 (POST) | `div.view_cont > p.ref-note` | HOMOGLYPH | P06 F08 H06 | 숫자 → 한자 (己丂0, 丨己彐丩) |
| 18 | 고시 12 (POST) | `div.board_view > h3.view_tit` | JAMO | P06 F08 J05 | 첫가끝 자모 제목 |
| 19 | 고시 목록 4쪽 (POST) | `table.board_list tr:nth-of-type(7) > td.subject > a` | JAMO | P01 P04 P06 F07 F08 J05 | 같은 제목이 목록에도 |
| 20 | 행사 7 | `div.ev-banner > p.ev-copy` | TRANSPARENT | T10 | 그라데이션 위 `#24487f` (대비율 1.19) |
| 21·22 | 행사 23 | `div.ev-desc > p.ev-note` | JAMO + HOMOGLYPH | J03 H07 F12 | `ㅋト지노` (ト는 가나) |
| 23·24 | 행사 32 | `div.ev-desc > p.ev-note` | JAMO + HOMOGLYPH | J03 H08 F12 | `ㅋr지노` |
| 25 | 옛 게시판 12 | `p.old-note > font` | TRANSPARENT | P11 T03 | EUC-KR, `<font color="#ffffff">` |
| 26·27 | 메인 | `iframe[src=".../widget/quick.html"] >>> div.qk > p.qk-txt` | JAMO + OFFSCREEN | P08 J07 F01 F05 O01 | `display:none` iframe(상대 src), 받침 노이즈 `캃짆놁` |
| 28 | /intro/vision | `div.content > p.v-note` | OFFSCREEN | F10 O01 | `/intro/vision.do` → 302 |
| 29 | 연혁 | `p.sh-open` | TRANSPARENT | P13 T07 | open Shadow DOM, 렌더링 기준만 검증 |
| 30 | 연혁 | `p.sh-closed` | OFFSCREEN | P13 O03 | closed Shadow DOM, 렌더링 기준만 검증 |
| 31 | 오시는 길 | `iframe[src="http://localhost:8131/ext/map-ad.html"] >>> div.mp > span.mp-ad` | OFFSCREEN | P07 P08 | 다른 도메인 크기 0 iframe |
| 32 | 보고서 4 | `div.rp-body > p.rp-note` | JAMO | J06 | 반각 자모, 3초 지연 페이지 |
| 33 | 통계 | `div.content > p.st-note` | JAMO | J08 | 자모 사이 U+200B, 대형 DOM 페이지 |
| 34 | 통계 | `iframe[src=".../widget/lazy-banner.html"] >>> div.lz > p.lz-txt` | TRANSPARENT | P12 T01 | 맨 아래 lazy iframe, 흰 배경 흰 글자 |
| 35 | FAQ | `div.frm-srcdoc > iframe >>> body > p.sd-ad` | OFFSCREEN | P12 O03 | srcdoc iframe, 렌더링 기준만 검증 |

## 미끼 (14건)

접근성 숨김(D01) 3, 접힌 메뉴·팝업·FAQ(D02) 3, 정상 전각·한자(D03) 1, 정상 자모(D04) 2, 불법도박 예방 공지(D05) 2, 숨겨진 비광고 텍스트(D08) 2, 범위 밖 다른 도메인 페이지 1.
공통 레이아웃의 숨김 요소(건너뛰기 링크, 하위 메뉴, 새창열림 등)는 모든 페이지에 있지만 대표로 메인에만 적었다. 다른 페이지에서 출력해도 오탐이다.

## extra (2건)

공지 1190의 보이는 광고 댓글, 옛 게시판 8의 보이는 광고 (`VISIBLE_AD`).

## 검증 (2026-10-14)

- 51건(정답·미끼·extra) 모두 렌더링 DOM에서 정확히 1개, 원본 HTML에서도 정확히 1개 (Shadow DOM 2건과 srcdoc 1건은 렌더링 기준만)
- iframe `src`는 원본이 상대 경로이므로 **절대 주소로 바꿔서 비교**한다 (S1과 같은 규칙, 채점기도 동일)
- 숨김 신호: 정답 OFFSCREEN·TRANSPARENT가 모두 화면 밖, 크기 0, 클리핑, 투명, 대비율 1.25 미만 중 하나에 해당
- 도달성: 진입 URL에서 href, iframe, sitemap·robots, onclick(POST → GET 변환), 리다이렉트를 따라 정답·extra 페이지 전부 도달 (공지 상세는 id 기준 정규화 필요)
