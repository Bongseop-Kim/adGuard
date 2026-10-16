# S8-extra: 추가 탐지 유형 (todo/08)

- 2026-10-16. 4종 밖 추가 유형의 데모 + 미끼. `result.json`은 0건이어야 한다(추가 유형은 `result_extra.json`으로만)
- 진입: `http://127.0.0.1:8200/`
- 채점: `python eval/scorer/score.py S8-extra app/result.json --extra app/result_extra.json` → `extra.found == expected`, `unexpected == []`

| 페이지 | 유형 | 내용 |
|---|---|---|
| `/s4/comment` | HTML_COMMENT_AD | 본문 상자 안 HTML 주석에 광고 |
| `/s4/meta` | ATTR_META_AD ×2 | `<title>`·`<meta description>`에 광고, 본문에는 없음 |
| `/s4/attr` | ATTR_META_AD ×2 | `img alt`, `a title`에 광고 |
| `/s4/decoy` | (미끼) | 예방 교육 주석·제목·메타·alt, `aria-label="메뉴 열기"`, 본문과 같은 `title`. 추가 유형 0건 |
| `/s5/reorder` | VISUAL_REORDER ×5, VISIBLE_AD ×2 | 보이는 글의 bidi-override, U+202E, flex row-reverse, order, position:relative left. 대조군: 순서 그대로, direction:rtl만 (→ VISIBLE_AD) |
| `/search?q=카지노…` | ISAP_SEARCH_REFLECTION | 첫 페이지 '인기 검색어' 위젯 링크. 검색어가 `<title>`에 반사. 같은 글의 VISIBLE_AD·ATTR_META_AD는 이 유형으로 합침 |
| `/search?q=민원 서식…` | (미끼) | 정상 검색어 반사. 0건 |
| `/s5/decoy` | (미끼) | 히브리어·아랍어 rtl, 역순 메뉴, 정상 bidi-override, RLM 전화번호, order 카드. 추가 유형 0건 |

- 중복 제외: 같은 글이 화면에 보이면(제목 형식은 조각마다, NFKC 비교) 속성·제목 쪽은 내지 않는다 (S3 첫가끝 자모 제목 사례)

## 검색 노출 위험 진단 (보고서 '사이트 진단', 결과 파일에는 없음)

`app/extra.py`의 `run(시작 주소)`. 시작 페이지 검색창에 `adgisapNNNNN`을 넣어 본다. 기대값은 answer.json `diagnosis`

| 시작 주소 | 기대 |
|---|---|
| `/` (→ `/search`, 제목 반사·색인 허용) | 위험 |
| `/s1/safe` (→ `/search-safe`, noindex) | 안전 |
| `/s1/body` (→ `/search-body`, 본문만 반사) | 참고 |
| `/s1/post` (POST 검색) | 안전 |
| `/s1/external` (구글 검색으로 연결) | 안전 |
| `/s4/meta` (검색창 없음) | 판정 불가 |
