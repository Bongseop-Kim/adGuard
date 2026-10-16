# S7-reach: 처음 보는 도달 경로 (research/14)

- 2026-10-16, 탐색 경로 33가지. 경로마다 끝 페이지에 `div.adx-RXX`(display:none) 광고 1건
- 진입: `http://127.0.0.1:8180/` (다른 도메인 localhost:8181). `python serve.py --big`: 목록 300쪽·글 3000개, `--tick`: 모든 쪽에 1초 반복 타이머
- 채점: `python check.py result.json` (광고의 `@test_rXX`로 경로를 찾아 URL만 본다. `--big`이면 R12만)
- 정답 URL 표는 check.py의 EXP. R05(해시 라우트)·R26(지연 JS 리다이렉트)은 해석이 갈릴 수 있다
