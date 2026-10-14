# S0-empty: 광고 없는 공공기관 누리집

- 목적: 숨김·변형 광고가 **0건**인 평범한 공공 누리집에서 오탐이 0건인지 본다. 정상 숨김 요소(접근성 숨김, 접힌 메뉴, 닫힌 탭·팝업·FAQ, 인쇄용 문구)와 정상 전각·한자·자모, 광고 키워드가 들어간 정상 공지를 일부러 많이 넣었다.
- 실행: `python serve.py` → `http://127.0.0.1:8100/` (다른 도메인 없음, `site_ext/` 없음)
- 진입 URL: `http://127.0.0.1:8100/`
- 가상 기관: 한국공공정보진흥원
- 건수: **정답 0건, 미끼 27건, extra 3건**
- 통과 조건: `result.json`의 `findings`가 `[]`. extra 3건은 `result_extra.json`에만 나와도 되고 안 나와도 감점 없음.

## URL → 파일

`serve.py`는 쿼리가 있는 주소를 `site/<경로>/<키>-<값>.html`로 연결한다(예: `/notice/view?no=101` → `site/notice/view/no-101.html`).

## 페이지 (13개)

| URL | 내용 | 미끼 |
|---|---|---|
| `/` | 메인. 탭(공지사항/보도자료, 보도자료 패널 `hidden`), 바로가기, 닫힌 레이어 팝업 | 6 |
| `/intro/greeting` | 인사말 (`（재）`, `국민(國民)`) | 2 |
| `/intro/history` | 연혁 (`①②`, `Ⅱ`, `Ⅰ`) | 1 |
| `/intro/org` | 조직 표(원본에 tbody 없음), 협력기관(`株式會社`, `ＬＧ전자`, `㈜`) | 2 |
| `/location` | 오시는 길 (회색 #999·#bbb 안내, 인쇄용 문구) | 3 |
| `/faq` | 자주 묻는 질문 (답변 `hidden`, 버튼으로 열림) | 2 |
| `/notice/list` | 공지 목록 3건 | 1 |
| `/notice/view?no=101` | 불법도박 예방 교육 안내 (`ㄱ. ㄴ. ㄷ.`, 카지노·토토·텔레그램 언급 경고문) | 3 |
| `/notice/view?no=102` | 개인정보 처리방침 개정 (첨부 '새창열림', 회색 수정일) | 2 |
| `/notice/view?no=103` | 대포통장 매매 처벌 안내 (광고 문구 인용 경고문, `.sound_only` 신고 번호) | 2 |
| `/qna/list` | 묻고 답하기 목록 (스팸 글 1건 보임, 비밀글 2건) | 1 (+extra 1) |
| `/qna/view?no=55` | 주차 문의 (`ㅠㅠ`, 댓글 `ㅋㅋ`) | 2 |
| `/qna/view?no=57` | 스팸 글 (숨김·변형 없이 보임) | 0 (+extra 2) |

## 미끼 (27건)

| url | location | 의도 | covers |
|---|---|---|---|
| `/` | `ul.skip-nav > li:nth-of-type(1) > a` | 본문 바로가기 | D01 |
| `/` | `footer.footer > div.inner > ul.f-menu > li:nth-of-type(2) > a > span.blind` | 새창열림 | D01 |
| `/` | `nav.gnb > ul.gnb-list > li.gnb-item:nth-of-type(1) > ul.sub-menu > li:nth-of-type(2) > a` | 접힌 하위 메뉴 | D02 |
| `/` | `section.main-tabs > div.panel-press > ul.latest-list > li:nth-of-type(1) > a` | 닫힌 탭의 '불법 게시물 집중 점검' 보도자료 | D02 D05 |
| `/` | `div.layer-popup > div.pop-body > p.pop-txt` | 닫힌 팝업 | D02 |
| `/` | `form.top-search > fieldset > label.blind` | 검색 라벨 | D08 |
| `/faq` | `div.faq-list > div.faq-item:nth-of-type(3) > div.faq-a > p` | 닫힌 FAQ 답변(불법도박 신고 안내) | D02 D05 |
| `/faq` | `form.top-search > fieldset > legend.blind` | 검색 legend | D08 |
| `/intro/greeting` | `div.greeting > p:nth-of-type(1)`, `p:nth-of-type(2)` | `（재）`, `국민(國民)` | D03 ×2 |
| `/intro/history` | `ol.history-list > li:nth-of-type(1)` | `①②` | D03 |
| `/intro/org` | `ul.partner-list > li:nth-of-type(1)`, `(2)` | `株式會社`, `ＬＧ전자` | D03 ×2 |
| `/notice/list` | `div.board-list > table.tbl-board tr:nth-of-type(3) > td.title > a` | '불법도박 예방 교육 안내' 제목 | D05 |
| `/notice/view?no=101` | `h3.view-title`, `p.list-jamo`, `p:nth-of-type(3)` | 정상 공지 제목, `ㄱ. ㄴ. ㄷ.`, 키워드 있는 경고문 | D05 D04 D05 |
| `/notice/view?no=103` | `div.article-body > p:nth-of-type(1)` | 대포통장 광고 문구를 인용한 경고문 | D05 |
| `/notice/view?no=103` | `div.article-body > p:nth-of-type(3) > span.sound_only` | 숨겨진 '불법도박 신고 ☎1336' | D05 D08 |
| `/notice/view?no=102` | `div.article-body > div.attach > a > span.blind`, `p.update-info` | 새창열림, 회색 #999 | D01 D06 |
| `/qna/list` | `div.board-list > table.tbl-board tr:nth-of-type(2) > td.title > span.blind` | '비밀글' 대체 텍스트 | D01 |
| `/qna/view?no=55` | `div.article-body > p`, 댓글 li 2 | `ㅠㅠ`, `ㅋㅋ` | D04 ×2 |
| `/location` | `p.note-gray`, `p.note-light`, `p.print-only` | 회색 #999(2.85), 연회색 #bbb(1.92), 인쇄용 | D06 D06 D08 |

## extra (3건, D07)

| url | location | 의도 |
|---|---|---|
| `/qna/list` | `div.board-list > table.tbl-board tr:nth-of-type(1) > td.title > a` | 그냥 보이는 스팸 글 제목 |
| `/qna/view?no=57` | `div.board-view > div.view-head > h3.view-title` | 같은 글 상세 제목 |
| `/qna/view?no=57` | `div.article-body > p` | 같은 글 본문 |

## 커버리지 집계

| D01 | D02 | D03 | D04 | D05 | D06 | D07 | D08 |
|---|---|---|---|---|---|---|---|
| 4 | 4 | 5 | 3 | 7 | 3 | 3 | 4 |

## 판단한 점

- "광고 없는 사이트"와 "D07(보이는 광고) 2번 이상"이 충돌한다. D07은 숨김·변형이 없어 `result.json` 대상이 아니므로 **정답 0건은 유지**하고, 보이는 스팸 글을 `extra`로만 넣었다.
- 모든 페이지에 공통으로 있는 숨김 요소(건너뛰기, 하위 메뉴, 검색 라벨, 새창열림, 맨 위로)는 페이지마다 미끼로 적지 않고 대표 페이지에서만 적었다. 다른 페이지의 같은 요소도 출력하면 오탐이다.
- 이메일 `help@kpia.example.go.kr`(푸터)은 텔레그램 ID 패턴 오탐을 보려고 넣은 정상 텍스트다(미끼 목록에는 없음, 보임).
