# S7-reach: 처음 보는 도달 경로 (research/14)

- 2026-10-16, 탐색 경로 33가지. 경로마다 끝 페이지에 `div.adx-RXX`(display:none) 광고 1건
- 진입: `http://127.0.0.1:8180/` (다른 도메인 localhost:8181). `python serve.py --big`: 목록 300쪽·글 3000개, `--tick`: 모든 쪽에 1초 반복 타이머
- 채점: `python check.py result.json` (광고의 `@test_rXX`로 경로를 찾아 URL만 본다. `--big`이면 R12만)
- 정답 URL 표는 check.py의 EXP. R05(해시 라우트)·R26(지연 JS 리다이렉트)은 해석이 갈릴 수 있다
- 2026-10-17 todo/12 재현 7가지 추가: R49 결과 url 원래 표기(`%20`·`%2F`·`?flag`, 문자열 그대로 비교), R42 게시판 ID가 `id`인 목록 2쪽(`?id=free&page=2`), R44 addEventListener로 건 `button`, R45 `javascript:void(0)` 링크 + 리스너, R46 리스너 클릭 뒤 이동 없이 화면만 바뀜(정답 URL은 목록), R47 모든 글의 canonical이 목록, R48 4초 뒤에 넣는 iframe(확인만)
