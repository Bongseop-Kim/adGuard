# S4-dynamic: 클릭·스크립트로만 닿는 위치 회귀 세트

- 사이트: 누리동 행정복지센터 (가상), `python serve.py` → `http://127.0.0.1:8140/`
- 목적: 크롤러가 놓치기 쉬운 3가지를 각 2건씩 고정한다 (todo/03 후속, research/03 §2)
- 정답 6, 미끼 2, extra 0

| 장소 | 정답 | 크롤러가 해야 할 일 |
|---|---|---|
| P14 클릭해야 AJAX로 붙는 댓글 | a_001 버튼 1번, a_002 `href="#none"` 링크 2번 | "더보기" 류를 DOM이 안 바뀔 때까지 눌러서 펼친 뒤 분석 |
| P16 iframe 안 onclick → 상위 페이지 | a_003 `top.location` GET, a_004 `target=_top` 폼 POST | iframe 프레임에서도 onclick을 눌러 이동 요청을 가로챔 |
| P15 외부 JS 파일 속 URL | a_005 `/js/common.js`, a_006 `/js/sub/legacy.js`(소개 페이지만) | 같은 도메인 `script[src]`를 받아 문자열 속 경로를 수집 |

- 정답의 `click`: 채점기가 location을 찾기 전에 차례로 누를 선택자. 클릭해야 생기는 요소라서 원본 HTML 검증 대상이 아니다(`[render_only]`)
- `/api/comments?id=N&cpage=M`은 댓글 조각(HTML 일부)이다. 단독 페이지가 아니다
- `serve.py`는 S1과 같고, POST 본문을 쿼리에 합쳐 같은 파일을 주는 처리만 더했다
