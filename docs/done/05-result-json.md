# result.json 출력

- 마감: 10/19
- 할 일: 모집요강 붙임4 스키마대로 출력, 스키마 검증 스크립트
- 완료 조건: 검출 0건/다건 모두 검증 통과, UTF-8(BOM 없음), 실행 파일 폴더에 생성

## 결과 (2026-10-14)

- `app/main.py`: (url, location, technique) 중복 제거, 크롤이 예외로 끝나도 `finally`에서 result.json을 쓴다. UTF-8(BOM 없음)·원자적 저장·exe 폴더(`base_dir()`)는 기존 그대로
- `eval/validate.py <파일…>`: 붙임4 기준 엄격 검증(BOM, NaN, 최상위 키, meta 형식·시간대 있는 ISO 8601, 필드 누락·빈 evidence_text, technique 4종, id·채점 단위 중복). 파일 이름이 `result_extra.json`이면 ETC + extra_finding 요구. CI(windows-build)도 이 스크립트로 검증
- 확인: S0(0건)·S1(26건) 실제 출력 통과, 접속 불가 URL도 빈 findings로 통과. 깨뜨린 파일 6종(BOM·NaN·중복·필드·최상위 키·시각) 모두 FAIL
