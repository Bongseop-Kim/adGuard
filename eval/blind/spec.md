# blind 세트 출제 의도 (내부 문서 — 채점기 개발자도 보지 않음)

주최 측(행안부·NIA) 시각으로 만든 비공개 평가 사이트. 가상의 공공기관 "한국공공생활안전진흥원"
누리집을 모사한다. 모든 광고 문구는 테스트용(범주 키워드 + 가짜 연락처: `@test_`, `.test`/`.example`,
`010-0000-`, `TEST`). 모집요강 붙임1(주요 탐지 유형 4종)·붙임4(result.json 스키마) 규칙만 구속력으로 삼았다.

## 규모
- 페이지 약 35개(본 도메인 8190 + 다른 도메인 8191), answer 참조 페이지 22개.
- 정답 39건 / 미끼 20건 / extra 2건.
- technique 분포: OFFSCREEN 12, HOMOGLYPH 10, JAMO 9, TRANSPARENT 8.
- 참가팀 연구문서(docs/research) 표에 없는 변형 12건(약 1/3)은 covers에 `NEW:...`로 표기.

## 숨긴 장소(크롤링 커버리지)
게시판 목록 제목/2쪽, 게시글 본문, 댓글, iframe(같은 도메인·다른 도메인·중첩·숨김·lazy·srcdoc),
Shadow DOM(open), 공통 푸터, onclick POST 전용 글, 리다이렉트 최종 페이지, 느린 응답, gzip 응답,
sitemap·robots·HTML 주석으로만 닿는 옛 게시판, 중복 URL(`&page=`, `;jsessionid`).

## 기법 중첩/경계
- 같은 요소 숨김+닮은꼴(F13), 같은 문자열 자모+닮은꼴(F12)은 기법별 2건으로 분리.
- 중첩 iframe은 `>>>` 반복(F04), Shadow DOM은 렌더링 기준(`host >>> inner`).

## NEW 변형(연구문서 표 밖, 붙임1 정의 내)
CSS translate 속성, `left:210vw`, `clip-path:circle(0)`, `content-visibility:hidden`,
`visibility:collapse`, 아르메니아 닮은꼴, 한글→한자(土/巴/上…) 다른 매핑, img alt 속성 위치,
가나/한자 혼용, 자모 사이 U+FEFF·U+2060·U+00AD(soft hyphen).

## 미끼(정확도 방어)
접근성 숨김 텍스트(.sound_only, skip-nav), 접힌 메뉴, 정상 전각/한자(（주）/株式會社/①②),
정상 자모(ㅋㅋ/ㅠㅠ/ㄱ.ㄴ.ㄷ.), 키워드 있으나 숨김·변형 없는 정상 공지, 저대비 회색 안내,
인쇄용 숨김(광고 아님), 정상 배너 alt, 정상 댓글.

## extra(result_extra.json)
숨김/변형 없이 그냥 보이는 광고 2건(배너 링크, 참여마당 노출문) → result.json에 넣으면 오탐.

## 검증
scratchpad의 verify.py로 모든 answer/decoy/extra가 렌더링 DOM과 원본 HTML(html.parser)에서
정확히 1개 요소인지(Shadow DOM은 렌더링 기준), 진입 URL에서 도달 가능한지, 숨김/변형이
의도대로인지 확인함(전부 통과).
