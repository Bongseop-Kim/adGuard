# Jev(TypeSafe) 도입 조사: 근거·장단점·사용 설계

- 작성: 2026-10-14
- 결정: **AI 판정 모델로 TypeSafe Jev를 쓴다.** 주최 측 키 발급 가능 여부는 확인됨(사용자 확인). 기법 4종 판정은 규칙이 하고, Jev는 "광고인가" 판정만 맡는다.
- 담당 평가 항목: 적격평가 **정답 추출 정확도 35점**(오탐 제거), 본심사 **창의성·독창성 20점**, **도입 가능성 10점**(AI 비용·호출 방식), **실무 활용성 20점**(판정 근거 제공)
- 방법: docs.typesafe.ai 문서를 브라우저와 `llms.txt`의 `.md` 원문으로 읽음(2026-10-14). PyPI·GitHub 메타데이터 확인. 성능 수치는 아직 **직접 측정 전**이며 §7 실험으로 확인한다.

## 핵심 결론

1. **Jev는 글을 생성하지 않는 판단 전용 모델이다.** 텍스트(`state`)와 타입이 정해진 질문을 보내면 확률이 붙은 답을 돌려준다. 우리가 AI에게 맡길 일이 "이 숨김 텍스트가 광고인가"라는 짧은 판단 하나라서, 생성형 LLM보다 형태가 잘 맞는다.
2. **가장 큰 도입 근거는 "보정된 확률(calibrated probability)"이다.** 04 문서 §0은 "정탐 확률 q가 약 0.4를 넘는 후보만 낸다"는 출력 규칙을 이미 계산해 두었다. Jev의 Noul 답은 바로 그 q 자리에 들어가는 0~1 확률이다. LLM에게 "확률을 말해 달라"고 글로 받는 것과 달리, 학습 단계에서 확률이 맞도록 보정된 값이다(TypeSafe 주장, §7에서 검증).
3. **가장 큰 위험은 한국어 정확도다.** 공식 문서에 "주 학습 언어는 영어이고, 한중일 문자는 정확도가 낮다. 비영어 작업은 자기 데이터로 시험하라"고 적혀 있다. 그래서 **정규화된 텍스트를 함께 보내고, 질문은 영어로 쓰고, 규칙 판정을 폴백이자 안전장치로 남긴다.**
4. **Jev가 틀리거나 장애가 나도 `result.json` 점수는 지킨다.** Jev는 규칙 점수가 애매한 구간에서만 결정권을 갖고, 타임아웃·429·키 없음이면 규칙 판정으로 확정한다(05 문서 §6.1 원칙 그대로).
5. **비용은 사실상 0에 가깝다.** 입력 100만 토큰당 $0.042, 출력 무료. 후보 1,000건을 전부 보내도 약 2센트로 추정된다(§5.6). 본심사 "토큰 사용량·호출 방식" 설명에 유리하다.

---

## 1. Jev 개요 (공식 문서 기준)

| 항목 | 내용 | 출처 |
|---|---|---|
| 정체 | TypeSafe의 "System One" 모델. 빠르고 구조화된 판단을 내림. 답장·코드·추론 설명을 생성하지 않음 | System One, Introduction |
| 호출 | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <KEY>` | API reference |
| 입력 | `state`(문자열·JSON 객체·배열, 텍스트만) + `questions`(내가 정한 id → 질문) + `model` | API reference, State |
| 질문 3종 | **Noul**: 예/아니오 확률(0~1). **Choice**: 선택지 중 하나 + 선택지별 확률 + confidence(최대 255개). **Score**: 순서 있는 등급(2~10개) + 확률 + confidence | API reference |
| 병렬 평가 | 한 요청 안의 질문들은 같은 state를 보고 **서로 독립적으로** 평가됨. 질문을 늘려도 응답 시간이 거의 안 늘어남 | Introduction, Primitives |
| 응답 | `answers`(질문 id별 답), `usage.input_tokens/output_tokens`, `model`(실제 응답한 버전) | API reference |
| 현재 모델 | `jev-1.13.0` (`jev-latest`, `jev-preview` 모두 이것을 가리킴) | Models |
| 가격 | 입력 100만 토큰당 **$0.042**, 출력 토큰 무료 | Models |
| 한도 | 초당 10만 토큰 / 초당 80요청. "수요가 많아 **예고 없이 바뀔 수 있음**" 경고 | Models |
| 컨텍스트 | 요청당 64k 토큰. state + 가장 긴 질문은 32k | Models |
| 속도 | "150ms 수준의 실시간 속도" (회사 주장, 미측정) | Example use cases |
| 오류 | 401(키), 422(요청 형식), 429(한도), 529(과부하). 429·529는 지수 백오프로 재시도. SDK는 자동 재시도 | API reference |
| 언어 | 영어가 주 학습 언어. 한중일은 "처리하지만 같은 수준은 아님" | Models §Language support, State |
| 데이터 | 고객 요청·응답으로 학습하지 않음. 계정별 파인튜닝 없음(모두 같은 가중치) | Models §Data handling, §Customizing |
| Python SDK | `typesafe-sdk` 0.7.4, Python ≥3.10, **MIT**. 의존성: httpx2, pydantic 2, tenacity, truststore | PyPI, GitHub |

### 1.1 알려진 약점 (Jev 1.13 jaggedness, 2026-10-02 검토판)

| # | 약점 | 우리 설계에서의 대응 |
|---|---|---|
| 1 | 글자 그대로 읽음 (의도를 추론하지 않음) | 판정 조건과 경계 사례를 `criteria`에 명시 (§5.3) |
| 2 | 계산·숫자에 약함. 색상 hex값·RGB 비교를 못 함 | 대비율·좌표는 코드가 계산하고, Jev에는 "사실상 안 보임" 같은 말로 바꿔 넣음. 애초에 숨김 판정은 Jev에 묻지 않음 |
| 4 | 여러 단계를 거치는 간접 질문에 약함 | 질문 하나에 판단 하나 |
| 5 | state에 관계없는 내용이 많으면 정확도 하락(context rot) | 페이지 전체가 아니라 후보 요소 텍스트 + 주변 제목만 보냄 |
| 6 | 적대적 내용에 흔들림 (state 안의 지시문, 자기 분류를 주장하는 글) | 광고 문구가 "이건 광고 아님" 같은 문장을 넣을 수 있음 → 규칙 확실 양성은 Jev가 뒤집지 못하게 함 (§5.4) |
| 8 | Choice는 앞쪽 선택지로 쏠리는 경향 | 분류 Choice는 선택지 순서를 바꿔 일관성 확인 (§7) |
| 9 | 텍스트 생성 불가 | 근거 위치·키워드 추출은 코드가 하고, Jev는 판단만 |

---

## 2. 도입 근거

### 2.1 규칙만으로는 풀기 어려운 부분이 정확히 "광고인가" 판정이다

04 문서 §7.3의 광고성 점수는 키워드·패턴 가산과 부정 문맥 감산으로 되어 있다. 다음 경우가 규칙으로는 경계에 걸린다.

| 사례 | 규칙의 어려움 | 출처 |
|---|---|---|
| `ｍｅｇａ－ＢＥＴ 첫충 30% 지급` | 브랜드명이 사전에 없음 | 모집요강 예시 2, 04 §핵심결론 4 |
| `무료 슬롯 체험 바로가기` | 연락 수단 패턴이 없음. 키워드+행동 유도어 조합 규칙을 따로 만들어야 했음 | 모집요강 예시 4, 04 §7.3 |
| 숨겨진 "불법도박 예방 교육 안내" | 도박 키워드가 많지만 공지. 부정 문맥 단어 목록에 의존 | eval D05, 04 §7.3 |
| 2군 키워드(토토, 놀이터, 픽, 오피 등) | 일상어와 겹쳐서 단독으로 쓸 수 없음 | 04 §7.1 |
| 전각 회사명(`ＬＧ전자`), `10μg` | HOMOGLYPH 신호는 있으나 광고 아님 | 04 §5.5 |
| 출제자가 만든 처음 보는 표현 | 사전·패턴을 미리 다 만들 수 없음 | 02 출제 시나리오 |

이 판단은 "알 만한 사람이 문장을 보고 1초 안에 내리는 판단"이고, Jev 문서가 권하는 질문 형태와 같다.

### 2.2 확률이 04 문서의 출력 규칙에 바로 들어간다

04 문서 §0: 정밀도 P≈0.9일 때 **정탐 확률 q > 약 0.4인 후보만 내는 것이 점수상 이득**이다. 규칙 점수(정수)를 q로 바꾸려면 따로 보정 데이터가 필요하지만, Noul의 답은 처음부터 확률이다. 테스트 세트로 보정 상태만 확인하면(§7) 임계값을 계산값 그대로 쓸 수 있다.

### 2.3 심사 항목별 기여

| 항목 | 기여 |
|---|---|
| 정확도 35점 | 규칙의 경계 구간 오탐·미탐을 줄임. 확률 기반으로 출력 기준을 정할 수 있음 |
| 창의성 20점 | 공공 웹 점검 도구에 "판단 전용 모델 + 신뢰도 기반 라우팅"을 적용. 생성형 LLM에 JSON을 요구하는 흔한 방식과 다름 |
| 도입 가능성 10점 | 출력 토큰 무료, 입력 단가가 매우 낮음. 호출 방식(후보만, 묶음, 캐시)과 토큰 사용량을 화면에 그대로 보여줄 수 있음 |
| 실무 활용성 20점 | "광고일 확률 92%", "분류: 도박(88%)" 같은 근거를 결과 화면에 표시. 애매한 건 "검토 필요"로 분리해 담당자 확인 업무로 연결 |

---

## 3. 장점

| 장점 | 설명 |
|---|---|
| 파싱 실패가 없음 | 답이 타입이 정해진 JSON(`noul`, `choice`, `probabilities`, `confidence`). 생성형 LLM의 "JSON으로 답해" 프롬프트가 깨지는 문제가 없음 |
| 보정된 확률 | Noul은 0~1 확률, Choice·Score는 분포와 confidence를 줌. 임계값으로 바로 분기 가능 |
| 한 번에 여러 질문 | 광고 여부, 분류, 공지 여부를 한 요청에 묻고 응답 시간은 거의 그대로 |
| 비용 | 입력 $0.042/100만 토큰, 출력 무료 |
| 속도 | 회사 주장 150ms 수준. 크롤링과 병행해도 검출 시간 20점에 부담이 적음 |
| 결정적인 사용 방식 | 프롬프트가 아니라 코드가 흐름을 쥠. 임계값·가중치를 코드 상수로 관리 |
| 라이선스 | Python SDK가 MIT라 오픈소스 고지만 하면 됨 |

## 4. 단점·위험과 대응

| 단점·위험 | 영향 | 대응 |
|---|---|---|
| 한국어 정확도가 영어보다 낮음 (공식 명시) | 은어·변형 한국어 광고를 놓치거나 공지를 광고로 볼 수 있음 | ① 원문과 함께 **정규화 결과**(자모 결합, 닮은꼴 치환)를 보냄 ② 질문·기준은 영어로 쓰고 광고 유형 예시를 한국어로 넣음 ③ §7 실험에서 규칙보다 나을 때만 결정권을 줌 |
| 신생 서비스, 한도가 예고 없이 바뀜 | 심사 당일 429·529 가능 | 동시 요청 제한, SDK 자동 재시도 + 전체 AI 예산(60초) 초과 시 규칙으로 확정 |
| 모델 별칭이 새 버전으로 바뀌면 답이 달라짐 | 맞춰 둔 임계값이 어긋남 | `jev-1.13.0`으로 버전 고정. 응답의 `model` 값을 로그에 남김 |
| 적대적 문구에 흔들림 | 광고 문구가 스스로 "공지"라고 주장할 수 있음 | 규칙 확실 양성(연락 수단 패턴 + 1군 키워드)은 Jev가 뒤집지 못함 |
| Choice 앞쪽 쏠림 | 분류 결과 편향 | 실험에서 선택지 순서 바꿔 확인. 분류는 화면 표시용이라 점수에 영향 없음 |
| 텍스트만 입력 | 이미지 광고는 못 봄 | 이미지 OCR은 이미 C등급(06 문서). OCR을 하더라도 결과 텍스트를 Jev에 넣으면 됨 |
| 외부 네트워크 의존 | 차단 환경이면 호출 불가 | 키 없음·연결 실패 시 규칙만으로 결과 완성(기본 동작) |
| SDK 의존성 추가 (httpx2, pydantic 등) | exe 용량 증가, PyInstaller 수집 누락 가능 | 표준 라이브러리 `urllib`로 HTTP 직접 호출(요청 1종, 재시도만 직접 구현). SDK는 실험 단계에서만 사용 |

---

## 5. 사용 설계

### 5.1 파이프라인에서의 위치

```
크롤링 → 후보 요소 추출 → [규칙] 기법 판정(4종) → [규칙] 광고성 점수(04 §7)
                                                         │
                       확실 양성 ─────────────────────────┼──→ 출력 (Jev 결과는 화면 근거로만)
                       확실 음성 ─────────────────────────┼──→ 버림
                       경계 구간 ──→ [Jev] 광고 확률 q ───┴──→ q ≥ 임계값이면 출력
                                         │ 실패·시간 초과
                                         └──→ 규칙 판정으로 확정
```

- Jev는 **기법 코드(technique)와 location을 정하지 않는다.** 이건 계산으로 정확히 정해지는 값이다.
- `is_violation`은 항상 `true`다(04 §11). Jev의 역할은 **"이 후보를 result.json에 넣을지"**를 정하는 것이다.
- 경계 구간 정의(초안): 04 §7.3의 `ad_score` 1~4점, 또는 3점 이상이지만 연락·코드·퍼센트·도메인 패턴이 없는 경우. §7 실험 뒤 조정.
- 화면 근거용으로 확실 양성도 Jev에 보낼지는 비용이 아니라 시간으로 정한다. 크롤링과 병행해 끝나면 보내고, 아니면 생략.

### 5.2 state 구성

후보 1건 = 요청 1건. 관계없는 내용을 빼고 판단에 필요한 것만 넣는다(약점 #5).

```json
{
  "hidden_text_original": "ｍｅｇａ－ＢＥＴ 첫충 30% 지급",
  "hidden_text_normalized": "mega-BET 첫충 30% 지급",
  "how_it_is_hidden": "Text is positioned far off-screen (left:-9999px), so visitors cannot see it.",
  "page_title": "공지사항 | ○○시청",
  "nearby_heading": "2026년 하반기 행사 안내",
  "site_type": "Korean public institution website"
}
```

- 숨김 방식은 숫자 대신 말로 쓴다(약점 #2). 예: 대비율 1.02:1 → "Text color is almost identical to the background."
- `hidden_text_*`는 500자 정도로 자른다. 요소 하나에 긴 본문이 있으면 키워드 주변 구간만 보낸다.

### 5.3 질문 (한 요청에 함께)

```json
{
  "is_illegal_ad": {
    "type": "noul",
    "instructions": "Is `hidden_text_normalized` an advertisement promoting illegal gambling, adult content, drugs, or illegal finance?",
    "criteria": {
      "true": "Promotes a service and invites action: signup codes, bonus percentages (첫충, 매충), Telegram/KakaoTalk IDs, site links, slot/casino/toto promotions, 출장안마, 대포통장, 작업대출.",
      "false": "Normal site text: navigation or accessibility text (본문 바로가기, 새창 열림), public notices or campaigns warning against gambling or drugs (예방, 근절, 신고), company names, product units."
    }
  },
  "is_public_warning": {
    "type": "noul",
    "instructions": "Does `hidden_text_normalized` warn citizens against illegal gambling, drugs, or fraud, rather than promote them?"
  },
  "ad_category": {
    "type": "choice",
    "instructions": "Which kind of content is `hidden_text_normalized`?",
    "criteria": {
      "gambling": "Online casino, slots, sports betting (토토), 꽁머니, 먹튀",
      "adult": "Sexual services or adult content",
      "drugs": "Illegal drugs or unlicensed medicine",
      "illegal_finance": "Bank account trading, illegal loans, card cashing",
      "not_an_ad": "Not an advertisement"
    }
  }
}
```

- 질문은 영어로 쓴다(주 학습 언어). 한국어 은어는 criteria 안에 예시로 넣는다. 한국어 질문과 비교는 §7에서 한다.
- `is_public_warning`은 결정에 직접 쓰지 않고 화면 근거와 실험 분석용이다. 질문 1개 추가는 응답 시간에 거의 영향이 없다(문서 주장).
- `ad_category`는 화면 분류 표시와 `result_extra.json`의 유형 보조에 쓴다.

### 5.4 판정 규칙

| 구간 | 결정 |
|---|---|
| 규칙 확실 양성 (`ad_score ≥ 5` + 연락 수단 패턴) | 출력. Jev가 낮게 봐도 뒤집지 않음(적대적 문구 대비). 화면에 "AI 의견 불일치" 표시 |
| 경계 구간 | `q = is_illegal_ad.noul`. **q ≥ 0.4면 출력**(04 §0의 계산값, 실험 뒤 보정). 0.25 ≤ q < 0.4면 `result.json`에는 넣지 않고 화면에 "검토 필요"로 표시 |
| 규칙 확실 음성 | 버림. Jev에 보내지 않음 |
| Jev 실패 (키 없음, 429·529 재시도 소진, 타임아웃, 전체 예산 초과) | 04 §7.3 규칙 판정 그대로 |

### 5.5 호출 방식

| 항목 | 값 | 이유 |
|---|---|---|
| 모델 | `jev-1.13.0` 고정 (`.env`의 `TYPESAFE_MODEL`로 변경 가능) | 별칭이 바뀌면 임계값이 어긋남 |
| 키 | `.env`의 `TYPESAFE_API_KEY` (exe 옆 경로, 05 문서 규칙) | 모집요강 하드코딩 금지 |
| 캐시 | 정규화 텍스트 + 숨김 방식의 해시 → 답 | 푸터·배너처럼 페이지마다 반복되는 후보는 1회만 호출 |
| 동시성 | 크롤링과 병행하는 백그라운드 스레드, 동시 요청 4개 | 공식 한도(80rps)보다 훨씬 낮게 |
| 타임아웃·재시도 | 요청당 5초, 429·529만 백오프 재시도 2회, 전체 AI 예산 60초 | 검출 시간 20점 보호 |
| HTTP | 표준 라이브러리 `urllib.request` + `truststore`(사내 SSL 검사 프록시 대비, 05 문서) | 의존성 최소화 |
| 로그·화면 | 호출 수, `usage.input_tokens` 합계, 예상 비용, 응답 `model` 버전 | 본심사 비용·호출 방식 설명 근거 |

### 5.6 비용 추정 (가정)

- 요청 1건 ≈ state 150토큰 + 질문 3개 350토큰 = **약 500 입력 토큰** (가정, 실험에서 `usage`로 실측)
- 경계 후보 200건 → 10만 토큰 → **$0.0042**. 모든 후보 1,000건을 보내도 50만 토큰 → **$0.021**
- 출력 토큰은 과금되지 않는다.

### 5.7 추가 탐지(`result_extra.json`)에서의 활용

06 문서의 S등급 추가 탐지(내부 검색 반사형 광고, 만료 도메인, 클로킹, 보이지 않는 문자·주석 은닉)도 결국 "찾아낸 텍스트가 광고인가"를 판단해야 한다. 같은 질문 세트를 그대로 재사용한다. 예: HTML 주석 안의 텍스트, 클로킹으로 검색봇에게만 보이는 문단.

---

## 6. OpenAI 대비 비교

| 항목 | Jev | OpenAI (05 문서의 기존 안) |
|---|---|---|
| 답 형식 | 타입 고정, 확률 포함 | 생성 텍스트 → JSON 파싱 (structured output으로 완화 가능) |
| 확률 | 보정된 확률이 기본 | logprobs로 근사해야 함 |
| 한국어 | 공식적으로 약함 | 강함 |
| 비용 | 입력 $0.042/1M, 출력 무료 | gpt-5-nano 입력 $0.05/1M, 출력 $0.40/1M (05 문서 §6.2) |
| 모집요강 예시에 포함 | 아님 (주최 측 키 발급 가능 확인됨) | 예시로 명시 |
| 차별성 | 높음 | 낮음 (많은 팀이 선택할 가능성) |

→ 한국어 정확도만 실험으로 확인되면 나머지는 Jev가 유리하거나 같다.

---

## 7. 검증 실험 (도입 확정 전 필수)

- 데이터: `eval/`의 광고 후보(정답) + 미끼(`decoys`: D03 정상 전각, D04 정상 자모, D05 광고 키워드가 든 정상 공지, sr-only 접근성 텍스트) + 04 §7.1 2군 키워드 문장. **최소 60건(양성 30, 음성 30).**
- 비교 대상: ① 규칙 `ad_score`만 ② Jev만 ③ 규칙 + Jev(§5.4)
- 변형: 질문 영어 vs 한국어, state에 정규화 텍스트 있음 vs 없음, `ad_category` 선택지 순서 정방향 vs 역방향
- 측정: 정밀도·재현율, 경계 구간에서의 정답률, 보정 상태(q 구간 0.0~0.2 / 0.2~0.4 / … 별 실제 양성 비율), 지연시간(p50·p95), 요청당 입력 토큰
- **합격 기준:** ③이 ①보다 경계 구간 정답률이 높고, 전체 정밀도가 떨어지지 않음. 지연 p95 < 1초. 미달이면 Jev는 화면 근거 표시용으로만 쓰고 결정권을 주지 않는다.
- 결과는 이 문서 하단 또는 `todo/04-탐지-4종.md` 완료 기록에 남긴다.

---

## 8. 다른 문서에서 고칠 점

| 문서 | 현재 | 수정 |
|---|---|---|
| 05 §핵심결론 추천 스택 | "선택적 OpenAI 호출(.env)" | "선택적 TypeSafe Jev 호출(.env)" |
| 05 §6 AI API 비용 | OpenAI 기준 묶음 호출·프롬프트 캐시 | Jev는 후보 1건 = 요청 1건, 질문 병렬. 프롬프트 캐시 개념 없음(출력 무료라 불필요). §5.5·§5.6으로 대체 |
| 04 §7.3 마지막 줄 | "LLM 재판정(옵션): 2~3점 후보만" | "Jev 판정: 경계 구간 후보, q ≥ 0.4 출력(07 문서 §5.4)" |
| todo/01 기술스택 | AI 사용 범위 미정 | "TypeSafe Jev(`jev-1.13.0`), 광고성 판정 보조, 규칙 폴백" |
| 사용설명서(todo/09) | — | 서비스명 TypeSafe, 모델명 `jev-1.13.0`, 환경변수 `TYPESAFE_API_KEY`·`TYPESAFE_MODEL` 명시 (모집요강 필수) |

---

## 9. 출처 (2026-10-14 열람)

- Introduction — https://docs.typesafe.ai/introduction
- Quick start — https://docs.typesafe.ai/introduction/quickstart
- System One — https://docs.typesafe.ai/concepts/system-one
- State — https://docs.typesafe.ai/concepts/state
- Primitives / Choice / Noul / Score — https://docs.typesafe.ai/primitives , /primitives/choice , /primitives/noul , /primitives/score
- Confidence — https://docs.typesafe.ai/confidence
- Models (가격·한도·언어·데이터 처리) — https://docs.typesafe.ai/models
- Jev 1.13 jaggedness (2026-10-02 검토판) — https://docs.typesafe.ai/model-jaggedness/jev-1.13
- API reference — https://docs.typesafe.ai/api
- Example use cases (150ms 주장) — https://docs.typesafe.ai/concepts/use-case-map
- Patterns: Confidence-gated routing — https://docs.typesafe.ai/patterns/confidence-routing
- Cookbook: Guardrails for LLMs (review/action 이중 임계값) — https://docs.typesafe.ai/cookbooks/llm_guardrails
- Python SDK — https://github.com/typesafe-ai/typesafe-sdk-python (MIT), https://pypi.org/project/typesafe-sdk/ (0.7.4, Python ≥3.10)
- 문서 전체 목록 — https://docs.typesafe.ai/llms.txt
