# S6-probe: 처음 보는 변형 (research/14)

- 2026-10-16, 코드를 읽고 약점을 노려 따로 만든 시험지. S0~S5 커버리지 ID 밖의 변형을 모았다
- 진입: `http://127.0.0.1:8170/`, 다른 도메인 `http://localhost:8171/`
- 정답 40건, 미끼 11건, extra 2건 (VISIBLE_AD)

| 묶음 | 내용 |
|---|---|
| 화면 밖 | top·right·bottom 밖, details 닫힘, content-visibility(조상·자신), hidden=until-found, 미디어쿼리, scale(0.01), SVG text |
| 투명 | 알파 0.04, opacity 0.01, 단색 그라데이션, animation opacity, td bgcolor + font color |
| 닮은꼴 | 그리스 대문자, 전각 숫자 전화번호, 위첨자, 작은 대문자 ʙᴇᴛ, 체로키, leet 대문자, 음각 원문자 🅑🅔🅣 |
| 자모 | span으로 쪼갠 자모, 쌍자음 풀어쓰기(ㄱㄱㅗㅇ), 두 글자 받침 노이즈(먺튅), 전각 공백 구분 |
| 블록 | display:none 상자 안 strong+a, 화면 밖 상자 안 문단 2개(상자와 광고 문단 둘 다 정답, S2 s-wrap1 규칙) |
| 어휘 | 릴게임, 오피·출장, 스포츠중계+bit.ly, 사설·롤링, 대출, 비아그라+카톡ID, 도박, 유흥, gambling, 조건 만남+오픈채팅, 카톡ID |
| 미끼 | 닫힌 메뉴 "성인반 수강 신청 문의", 닫힌 탭 "외화 환전 안내", FAQ 안내문, 인쇄용 문구, sr-only, 정상 전각·그리스 문자 |

- 뺀 것: 다른 요소에 가려진 글자(z-index, 형제 상자). 4종 중 어느 기법인지 모호하다
