# S5-detect: 탐지 규칙 보완 회귀 세트 (research/09)

- 사이트: 가람구 보건소 (가상), `python serve.py` → `http://127.0.0.1:8150/`
- 목적: research/09에서 실험으로 확인한 판정 버그 7가지를 정답·미끼로 고정한다 (todo/04)
- 정답 17, 미끼 2, extra(보이는 광고) 8. 페이지마다 한 주제

| 페이지 | 주제 | 정답 | 미끼·extra |
|---|---|---|---|
| `/c/zero-auto.html` | R1 크기 0 + `overflow:auto` | `div.seo-box > a.seo-lnk` | 스크롤하면 보이는 상자 아래쪽 |
| `/c/clamp.html` | R2 한 줄이라도 보이면 보임 | — | line-clamp 미리보기, 말줄임 제목 |
| `/c/diff.html` | R3 스크린샷 차분 | 흰/#eee 그라데이션 위 같은 색 글자 | background-clip:text 글자, 그라데이션 위 #333 |
| `/c/marquee.html` | R4 marquee | scrollamount 99999, scrolldelay 9999999 | 보통 속도 marquee |
| `/c/vtext.html` | R5 보이는 글자열 | salting·bidi·U+202E·::before·flex order (모두 숨김) | 보이는 문장의 salting, 그 font-size:0 조각 |
| `/c/norm.html` | R6 정규화 | `카ㆍ지ㆍ노`, `77ㅗㅇ머니`(JAMO+HOMOGLYPH), 결합 부호 | 공문서 `시ㆍ도` |
| `/c/svg.html` | R7 SVG·input | fill #fff, fill-opacity 0, input value 흰 글자 | SVG fill #333 |

- 숨김·변형 없이 보이는 광고는 `extra`(VISIBLE_AD)다. result.json에 나오면 오탐
