# S5-detect: 탐지 규칙 보완 회귀 세트 (research/09)

- 사이트: 가람구 보건소 (가상), `python serve.py` → `http://127.0.0.1:8150/`
- 목적: research/09에서 실험으로 확인한 판정 버그 7가지와 실제 사이트 오탐(research/13)을 정답·미끼로 고정한다 (todo/04)
- 정답 20, 미끼 4, extra(보이는 광고) 9. 페이지마다 한 주제

| 페이지 | 주제 | 정답 | 미끼·extra |
|---|---|---|---|
| `/c/zero-auto.html` | R1 크기 0 + `overflow:auto` | `div.seo-box > a.seo-lnk` | 스크롤하면 보이는 상자 아래쪽 |
| `/c/clamp.html` | R2 한 줄이라도 보이면 보임 | — | line-clamp 미리보기, 말줄임 제목 |
| `/c/diff.html` | R3 스크린샷 차분 | 흰/#eee 그라데이션 위 같은 색 글자 | background-clip:text 글자, 그라데이션 위 #333 |
| `/c/marquee.html` | R4 marquee | scrollamount 99999, scrolldelay 9999999 | 보통 속도 marquee |
| `/c/vtext.html` | R5 보이는 글자열 | salting·bidi·U+202E·::before·flex order (모두 숨김) | 보이는 문장의 salting, 그 font-size:0 조각 |
| `/c/norm.html` | R6 정규화 | `카ㆍ지ㆍ노`, `77ㅗㅇ머니`(JAMO+HOMOGLYPH), 결합 부호 | 공문서 `시ㆍ도` |
| `/c/svg.html` | R7 SVG·input | fill #fff, fill-opacity 0, input value 흰 글자 | SVG fill #333 |
| `/c/dup.html` | R8 보이는 곳에 같은 글이 있는 숨김 (research/13 §1) | 보이는 제목의 변형(JAMO+HOMOGLYPH), 화면에 없는 sr-only 광고 | 그누보드 `h1#hd_h1`, 댓글 수정 폼 textarea / extra: 보이는 댓글 |

- 숨김·변형 없이 보이는 광고는 `extra`(VISIBLE_AD)다. result.json에 나오면 오탐
