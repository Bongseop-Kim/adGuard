# 광고성 판정 AI 도입 조사: OpenAI Decisions API (비교 대상 TypeSafe Jev)

- 작성: 2026-10-14 (같은 날 개정: Jev 단독안 → Decisions API 1순위, Jev는 비교 대상)
- 결정: **광고성 판정 AI로 OpenAI Decisions API(`gpt-6-luna`)를 쓴다.** 기법 4종 판정은 규칙이 하고, AI는 "광고인가" 판정만 맡는다. Jev는 같은 실험(§8)에 비교 대상으로 넣고, 확실히 나을 때만 교체한다.
- 담당 평가 항목: 적격평가 **정답 추출 정확도 35점**(오탐 제거), 본심사 **창의성·독창성 20점**, **도입 가능성 10점**(AI 비용·호출 방식), **실무 활용성 20점**(판정 근거 제공)
- 방법: developers.openai.com의 Decisions 가이드, API 레퍼런스, `gpt-6-luna` 모델 페이지, 변경 이력을 브라우저로 읽음. docs.typesafe.ai 문서를 브라우저와 `.md` 원문으로 읽음. PyPI·GitHub 메타데이터 확인(모두 2026-10-14). 성능 수치는 아직 **직접 측정 전**이며 §8 실험으로 확인한다.

## 핵심 결론

1. **Decisions API는 글을 생성하지 않는 판단 전용 API다.** 입력과 타입이 정해진 질문을 보내면 확률이 붙은 답을 돌려준다. 우리가 AI에게 맡길 일이 "이 숨김 텍스트가 광고인가"라는 짧은 판단 하나라서, 생성형 호출보다 형태가 잘 맞는다. 2026-10-06 베타 출시.
2. **가장 큰 도입 근거는 확률을 그대로 쓸 수 있다는 점이다.** 04 문서 §0은 "정탐 확률 q가 약 0.4를 넘는 후보만 낸다"는 출력 규칙을 이미 계산해 두었다. predicate 질문의 `probability`가 바로 그 q 자리에 들어간다. 보정 상태는 §8에서 확인한다.
3. **Jev 대신 Decisions API를 고른 이유는 위험이 더 작기 때문이다.** 개념과 질문 구조는 같지만, Jev는 공식 문서에 "한중일 문자는 정확도가 낮다"고 명시돼 있고, 요청 한도가 예고 없이 바뀌며, 주최 측 키 발급이 별도 확인 사항이었다. Decisions API는 OpenAI 키(모집요강 예시에 명시)로 쓰고, 한도가 훨씬 크고, **이미지도 받는다.**
4. **새로 생긴 위험은 두 가지다.** ① 도박·성인 문구라서 질문이 `refusal`로 돌아올 수 있다. ② 베타라서 정식 출시(GA) 때 형식이 바뀔 수 있고, 시점이 심사 기간과 겹칠 수 있다. 둘 다 **규칙 판정 폴백**으로 막는다.
5. **AI가 틀리거나 장애가 나도 `result.json` 점수는 지킨다.** AI는 규칙 점수가 애매한 구간에서만 결정권을 갖고, 키 없음·타임아웃·429·거부면 규칙 판정으로 확정한다(05 문서 §6.1 원칙 그대로).
6. **비용은 사실상 0에 가깝다.** 입력 100만 토큰당 $0.10, 출력·캐시 비용 없음. 후보 1,000건을 전부 보내도 약 5센트로 추정된다(§6.6).

---

## 1. OpenAI Decisions API 개요

| 항목 | 내용 | 출처 |
|---|---|---|
| 정체 | 텍스트·이미지를 평가해 타입이 정해진 답을 돌려주는 API. "Responses API보다 약 10배 빠르다" | Decisions 가이드 |
| 상태 | **공개 베타.** "몇 주 안에 GA 예정". 2026-10-06 출시 | Decisions 가이드, 변경 이력 |
| 호출 | `POST https://api.openai.com/v1/decisions`, `Authorization: Bearer $OPENAI_API_KEY` | API 레퍼런스 |
| 요청 | `model`, `input`(문자열, 또는 `input_text`·`input_image` 파트를 담은 user 메시지 배열), `questions`(배열), `safety_identifier`(선택, 128자 이하) | API 레퍼런스 |
| 모델 | `gpt-6-luna`만 지원 | Decisions 가이드 |
| 질문 3종 | **predicate** `{type, name, instructions}`: 조건이 참일 확률. **choice** `{type, name, instructions, choices:[{value, description}]}`: 선택지 하나 + 선택지별 확률 + confidence. **score** `{type, name, instructions, levels:[{label, description}]}`: 등급 확률의 가중 평균 점수 + confidence | Decisions 가이드, API 레퍼런스 |
| 응답 | `answers` 배열(질문 순서대로, `name`으로 식별), `model`, `usage`(`input_tokens`, `output_tokens`=0 등) | API 레퍼런스 |
| 거부 | 질문 하나가 답 대신 `type: "refusal"`로 올 수 있음(`name` 포함) | API 레퍼런스 |
| 여러 질문 | 서로 독립인 질문은 한 요청에 함께. 앞 답에 따라 달라지는 질문은 별도 요청 | Decisions 가이드 |
| 이미지 | 요청당 최대 128장. 가이드는 "base64 data URL만", 레퍼런스는 "공개 HTTP(S) URL도 가능"이라 **서로 다름** → base64로 보냄 | Decisions 가이드, API 레퍼런스 |
| 가격 | 입력 100만 토큰당 **$0.10**. 출력·캐시 읽기·캐시 쓰기 비용 없음. 지역 처리·긴 컨텍스트 할증은 적용 | Decisions 가이드 |
| 한도 | `gpt-6-luna` 기준 Build 등급 분당 5,000요청·200만 토큰, Launch 10,000·1,000만, Grow 30,000·1.8억. Free 등급은 지원 안 함 | gpt-6-luna 모델 페이지 |
| 모델 정보 | 컨텍스트 105만 토큰, 지식 기준일 2026-05-18, 입력 텍스트·이미지 | gpt-6-luna 모델 페이지 |
| SDK | OpenAI Python SDK 3.26.0 이상 필요 | Decisions 가이드 |
| 데이터 | ZDR·HIPAA(자격 고객), 미국·유럽 데이터 상주 | Decisions 가이드 |
| 임계값 권고 | "실제 레이블 데이터로 임계값을 정하고, 오탐·미탐 비용에 맞춰라" | Decisions 가이드 |

---

## 2. 비교 대상: TypeSafe Jev

| 항목 | 내용 | 출처 |
|---|---|---|
| 정체 | TypeSafe의 "System One" 판단 전용 모델. 질문 3종 Noul·Choice·Score (predicate·choice·score와 1:1 대응) | docs.typesafe.ai Introduction, API reference |
| 호출 | `POST https://api.typesafe.ai/v1/systemone`, 질문은 id → 질문 맵 | API reference |
| 모델 | `jev-1.13.0` (`jev-latest` 별칭) | Models |
| 가격 | 입력 100만 토큰당 $0.042, 출력 무료 | Models |
| 한도 | 초당 10만 토큰 / 초당 80요청. "**예고 없이 바뀔 수 있음**" | Models |
| 입력 | 텍스트만 | State |
| 언어 | "주 학습 언어는 영어. 한중일은 처리하지만 같은 수준은 아님. 비영어는 자기 데이터로 시험하라" | Models §Language support |
| Python SDK | `typesafe-sdk` 0.7.4, Python ≥3.10, MIT | PyPI, GitHub |

### 2.1 Jev 문서의 알려진 약점 (Jev 1.13 jaggedness, 2026-10-02)

Decisions API에는 이런 문서가 없지만, 같은 계열 모델에 공통으로 적용될 만한 내용이라 설계 원칙으로 가져온다.

| 약점 | 설계 원칙 |
|---|---|
| 글자 그대로 읽음 | 판정 조건과 경계 사례를 질문 문장에 명시 (§6.3) |
| 계산·숫자에 약함(색상 hex값·RGB 비교 불가) | 대비율·좌표는 코드가 계산하고 "사실상 안 보임" 같은 말로 바꿔 넣음 |
| 여러 단계를 거치는 간접 질문에 약함 | 질문 하나에 판단 하나 |
| 관계없는 내용이 많으면 정확도 하락 | 페이지 전체가 아니라 후보 텍스트 + 주변 제목만 |
| 적대적 문구에 흔들림 | 규칙 확실 양성은 AI가 뒤집지 못하게 함 (§6.4) |
| choice는 앞쪽 선택지로 쏠림 | 실험에서 선택지 순서를 바꿔 확인 (§8) |

---

## 3. 비교와 선택

| 항목 | OpenAI Decisions | TypeSafe Jev |
|---|---|---|
| 개념·질문 구조 | 같음 | 같음 |
| 한국어 | 별도 언급 없음. 범용 GPT-6 계열이라 강할 가능성이 크나 **미확인** | **공식적으로 약함** |
| 이미지 | 가능 (요청당 128장) | 불가 |
| 키 발급 | 모집요강 예시(OpenAI)에 명시 | 주최 측 확인 필요 |
| 가격 (입력 1M) | $0.10 | $0.042 |
| 한도 | 분당 5,000요청 이상 | 초당 80요청, 변동 |
| 성숙도 | 베타(출시 8일), 운영사 OpenAI | 정식, 운영사 신생 스타트업 |
| 거부 | `refusal` 가능 | 문서상 거부 개념 없음 |
| 버전 고정 | `gpt-6-luna` 하나(스냅샷 고정 ID는 문서에 없음) | `jev-1.13.0`으로 고정 가능 |
| 창의성 소재 | 출시 2주 된 기능이라 아는 팀이 드묾 | 생소한 모델 |

→ 가격 차이는 후보 1,000건 기준 3센트 수준이라 의미가 없다. 한국어·키·한도·이미지에서 Decisions API가 유리하다. Jev가 앞서는 부분은 거부가 없다는 점과 버전 고정뿐이다. 그래서 **Decisions API를 1순위로 두고, §8 실험에서 Jev가 한국어 경계 사례를 확실히 더 잘 맞히거나 Decisions의 거부율이 높을 때만 교체**한다. 두 API는 질문 구조가 같아서 실험 스크립트 하나로 둘 다 돌릴 수 있다.

---

## 4. 도입 근거

### 4.1 규칙만으로는 풀기 어려운 부분이 정확히 "광고인가" 판정이다

04 문서 §7.3의 광고성 점수는 키워드·패턴 가산과 부정 문맥 감산이다. 다음 경우가 규칙으로는 경계에 걸린다.

| 사례 | 규칙의 어려움 | 출처 |
|---|---|---|
| `ｍｅｇａ－ＢＥＴ 첫충 30% 지급` | 브랜드명이 사전에 없음 | 모집요강 예시 2, 04 §핵심결론 4 |
| `무료 슬롯 체험 바로가기` | 연락 수단 패턴이 없음. 키워드+행동 유도어 조합 규칙을 따로 만들어야 했음 | 모집요강 예시 4, 04 §7.3 |
| 숨겨진 "불법도박 예방 교육 안내" | 도박 키워드가 많지만 공지. 부정 문맥 단어 목록에 의존 | eval D05, 04 §7.3 |
| 2군 키워드(토토, 놀이터, 픽, 오피 등) | 일상어와 겹쳐 단독으로 쓸 수 없음 | 04 §7.1 |
| 전각 회사명(`ＬＧ전자`), `10μg` | HOMOGLYPH 신호는 있으나 광고 아님 | 04 §5.5 |
| 출제자가 만든 처음 보는 표현 | 사전·패턴을 미리 다 만들 수 없음 | 02 출제 시나리오 |

### 4.2 확률이 04 문서의 출력 규칙에 바로 들어간다

04 문서 §0: 정밀도 P≈0.9일 때 **정탐 확률 q > 약 0.4인 후보만 내는 것이 점수상 이득**이다. 규칙 점수(정수)를 q로 바꾸려면 보정 데이터가 따로 필요하지만, predicate의 답은 처음부터 확률이다. 테스트 세트로 보정 상태만 확인하면(§8) 임계값을 계산값 그대로 쓸 수 있다.

### 4.3 심사 항목별 기여

| 항목 | 기여 |
|---|---|
| 정확도 35점 | 규칙의 경계 구간 오탐·미탐을 줄임. 확률 기반으로 출력 기준을 정함 |
| 창의성 20점 | 공공 웹 점검에 "판단 전용 API + 확률 기반 라우팅"을 적용. 생성형 LLM에 JSON을 요구하는 흔한 방식과 다름. 출시 직후 기능이라 다른 팀과 겹칠 가능성이 낮음 |
| 도입 가능성 10점 | 출력 비용 없음, 입력 단가가 낮음. 호출 방식(애매한 후보만, 캐시)과 토큰 사용량을 화면에 그대로 보여줌. 주최 측이 이미 쓰는 OpenAI 키로 동작 |
| 실무 활용성 20점 | "광고일 확률 92%", "분류: 도박(88%)" 같은 근거를 결과 화면에 표시. 애매한 건 "검토 필요"로 분리 |

---

## 5. 장점과 단점

### 5.1 장점

| 장점 | 설명 |
|---|---|
| 파싱 실패가 없음 | 답이 타입이 정해진 JSON(`probability`, `choice`, `probabilities`, `confidence`) |
| 확률 | predicate는 0~1 확률, choice·score는 분포와 confidence. 임계값으로 바로 분기 |
| 한 번에 여러 질문 | 광고 여부, 공지 여부, 분류를 한 요청에 |
| 이미지 | 숨김 판정이 불확실한 경우의 스크린샷, 이미지 속 광고 문구까지 같은 API로 판정 가능 (§6.7) |
| 비용 | 입력 $0.10/100만 토큰, 출력·캐시 비용 없음 |
| 한도 | 분당 5,000요청 이상이라 우리 규모(수백 건)에서 429 걱정이 거의 없음 |
| 키 | 모집요강 예시 서비스. 사용설명서에 서비스명·모델명·환경변수명만 적으면 됨 |

### 5.2 단점·위험과 대응

| 단점·위험 | 영향 | 대응 |
|---|---|---|
| `refusal` (불법 도박·성인 문구) | 해당 질문 답이 없음 | 거부는 실패와 같게 규칙 판정으로 확정. 질문을 "광고를 찾아내는 콘텐츠 검수" 맥락으로 씀. 거부율을 §8에서 측정 |
| 베타 → GA 때 형식 변경 가능 | 심사 기간에 요청이 422 등으로 실패할 수 있음 | 응답 파싱 실패도 규칙 폴백. GA 공지를 제출 직전까지 확인하고 요청 형식을 맞춤 |
| 모델 스냅샷 고정 ID가 없음 | 모델이 바뀌면 맞춰 둔 임계값이 어긋남 | 응답의 `model` 값을 로그에 남김. `.env`의 `OPENAI_DECISIONS_MODEL`로 바꿀 수 있게 함 |
| 한국어 정확도 미확인 | 은어·변형 한국어를 놓칠 수 있음 | 원문과 정규화 결과를 함께 보냄. §8에서 규칙보다 나을 때만 결정권을 줌 |
| 적대적 문구 | 광고가 스스로 "공지"라고 주장 | 규칙 확실 양성은 AI가 뒤집지 못함 |
| 문서끼리 이미지 URL 지원이 다름 | URL 이미지가 거부될 수 있음 | base64 data URL만 사용 |
| 외부 네트워크 의존 | 연결 실패 시 호출 불가 | 키 없음·연결 실패 시 규칙만으로 결과 완성(기본 동작) |
| Free 등급 미지원 | 결제 안 된 키로는 호출 불가 | 사용설명서에 "유료 등급(Build 이상) 키 필요" 명시. 키 확인 실패 시 화면에 "AI: 꺼짐" 표시 |

---

## 6. 사용 설계

### 6.1 파이프라인에서의 위치

```
크롤링 → 후보 요소 추출 → [규칙] 기법 판정(4종) → [규칙] 광고성 점수(04 §7)
                                                         │
                       확실 양성 ─────────────────────────┼──→ 출력 (AI 결과는 화면 근거로만)
                       확실 음성 ─────────────────────────┼──→ 버림
                       경계 구간 ──→ [AI] 광고 확률 q ────┴──→ q ≥ 임계값이면 출력
                                         │ 실패·거부·시간 초과
                                         └──→ 규칙 판정으로 확정
```

- AI는 **기법 코드(technique)와 location을 정하지 않는다.** 계산으로 정확히 정해지는 값이다.
- `is_violation`은 항상 `true`다(04 §11). AI의 역할은 **"이 후보를 result.json에 넣을지"**를 정하는 것이다.
- 경계 구간 정의(초안): 04 §7.3의 `ad_score` 1~4점, 또는 3점 이상이지만 연락·코드·퍼센트·도메인 패턴이 없는 경우. §8 실험 뒤 조정.
- 확실 양성도 화면 근거용으로 보낼지는 시간으로 정한다. 크롤링과 병행해 끝나면 보내고, 아니면 생략.

### 6.2 input 구성

후보 1건 = 요청 1건. 판단에 필요한 것만 넣는다. `input`은 문자열이므로 아래 JSON을 문자열로 직렬화해 보낸다.

```json
{
  "hidden_text_original": "ｍｅｇａ－ＢＥＴ 첫충 30% 지급",
  "hidden_text_normalized": "mega-BET 첫충 30% 지급",
  "how_it_is_hidden": "Text is positioned far off-screen (left:-9999px), so visitors cannot see it.",
  "page_title": "공지사항 | ○○시청",
  "nearby_heading": "2026년 하반기 행사 안내",
  "site_type": "Korean public institution website",
  "task": "Content audit: detecting illegal advertisements hidden on a public website"
}
```

- 숨김 방식은 숫자 대신 말로 쓴다. 예: 대비율 1.02:1 → "Text color is almost identical to the background."
- `task`는 검수 맥락을 밝혀 거부 가능성을 낮추기 위한 것이다(효과는 §8에서 확인).
- `hidden_text_*`는 500자 정도로 자른다. 긴 본문이면 키워드 주변 구간만 보낸다.

### 6.3 질문 (한 요청에 함께)

predicate에는 `criteria` 필드가 없으므로 판정 기준을 `instructions` 문장 안에 쓴다.

```json
[
  {
    "type": "predicate",
    "name": "is_illegal_ad",
    "instructions": "Is hidden_text_normalized an advertisement promoting illegal gambling, adult services, drugs, or illegal finance? Yes if it promotes a service and invites action, such as signup codes, bonus percentages (첫충, 매충), Telegram or KakaoTalk IDs, site links, slot/casino/toto promotions, 출장안마, 대포통장, 작업대출. No if it is normal site text: navigation or accessibility text (본문 바로가기, 새창 열림), a public notice or campaign warning against gambling or drugs (예방, 근절, 신고), a company name, or a product unit."
  },
  {
    "type": "predicate",
    "name": "is_public_warning",
    "instructions": "Does hidden_text_normalized warn citizens against illegal gambling, drugs, or fraud, rather than promote them?"
  },
  {
    "type": "choice",
    "name": "ad_category",
    "instructions": "Which kind of content is hidden_text_normalized?",
    "choices": [
      {"value": "gambling", "description": "Online casino, slots, sports betting (토토), 꽁머니, 먹튀"},
      {"value": "adult", "description": "Sexual services or adult content"},
      {"value": "drugs", "description": "Illegal drugs or unlicensed medicine"},
      {"value": "illegal_finance", "description": "Bank account trading, illegal loans, card cashing"},
      {"value": "not_an_ad", "description": "Not an advertisement"}
    ]
  }
]
```

- 질문은 영어로 쓰고 한국어 은어는 예시로 넣는다. 한국어 질문과의 비교는 §8에서 한다.
- `is_public_warning`은 결정에 직접 쓰지 않고 화면 근거와 실험 분석용이다.
- `ad_category`는 화면 분류 표시와 `result_extra.json`의 유형 보조에 쓴다. 가이드 권고대로 범주 밖 선택지(`not_an_ad`)를 둔다.

### 6.4 판정 규칙

| 구간 | 결정 |
|---|---|
| 규칙 확실 양성 (`ad_score ≥ 5` + 연락 수단 패턴) | 출력. AI가 낮게 봐도 뒤집지 않음(적대적 문구 대비). 화면에 "AI 의견 불일치" 표시 |
| 경계 구간 | `q = is_illegal_ad.probability`. **q ≥ 0.4면 출력**(04 §0의 계산값, 실험 뒤 보정). 0.25 ≤ q < 0.4면 `result.json`에는 넣지 않고 화면에 "검토 필요"로 표시 |
| 규칙 확실 음성 | 버림. AI에 보내지 않음 |
| AI 실패 (키 없음, 거부, 429 재시도 소진, 타임아웃, 응답 형식 오류, 전체 예산 초과) | 04 §7.3 규칙 판정 그대로 |

### 6.5 호출 방식

| 항목 | 값 | 이유 |
|---|---|---|
| 모델 | `gpt-6-luna` (`.env`의 `OPENAI_DECISIONS_MODEL`로 변경 가능) | 현재 유일한 지원 모델. GA 때 바뀌면 재빌드 없이 교체 |
| 키 | `.env`의 `OPENAI_API_KEY` (exe 옆 경로, 05 문서 규칙) | 모집요강 하드코딩 금지 |
| 캐시 | 정규화 텍스트 + 숨김 방식의 해시 → 답 | 푸터·배너처럼 페이지마다 반복되는 후보는 1회만 호출 |
| 동시성 | 크롤링과 병행하는 백그라운드 스레드, 동시 요청 4개 | 한도보다 훨씬 낮게 |
| 타임아웃·재시도 | 요청당 5초, 429·5xx만 백오프 재시도 2회, 전체 AI 예산 60초 | 검출 시간 20점 보호 |
| HTTP | 표준 라이브러리 `urllib.request` + `truststore`(사내 SSL 검사 프록시 대비, 05 문서) | 요청 1종뿐이라 SDK 불필요. exe 용량·PyInstaller 수집 문제 회피 |
| 로그·화면 | 호출 수, `usage.input_tokens` 합계, 예상 비용, 거부 수, 응답 `model` | 본심사 비용·호출 방식 설명 근거 |

### 6.6 비용 추정 (가정)

- 요청 1건 ≈ input 200토큰 + 질문 3개 350토큰 = **약 550 입력 토큰** (가정, 실험에서 `usage`로 실측)
- 경계 후보 200건 → 11만 토큰 → **약 $0.011**. 모든 후보 1,000건을 보내도 55만 토큰 → **약 $0.055**
- 출력·캐시 토큰은 과금되지 않는다.

### 6.7 이미지 활용 (선택, 실험 뒤 결정)

| 용도 | 방법 | 연결 문서 |
|---|---|---|
| TRANSPARENT 판정이 불확정일 때 | 요소 스크린샷 + 질문 "Is the text '…' readable in this image?" | 04 §3.3(지금은 글자를 투명하게 바꾼 스크린샷 비교). 규칙이 1차, AI는 보조 |
| 이미지 속 광고 문구 | 게시판 첨부·본문 이미지 + `is_illegal_ad` 같은 질문. OCR 없이 바로 판정 | 06 C-9(`IMAGE_TEXT_AD`). OCR 엔진을 번들하지 않아도 됨 → C등급 재검토 후보 |

- 이미지는 토큰이 많이 들고 시간이 걸리므로 개수 상한을 둔다(예: 사이트당 50장).

### 6.8 추가 탐지(`result_extra.json`)에서의 활용

06 문서의 S등급 추가 탐지(내부 검색 반사형 광고, 만료 도메인, 클로킹, 보이지 않는 문자·주석 은닉)도 결국 "찾아낸 텍스트가 광고인가"를 판단해야 한다. 같은 질문 세트를 그대로 재사용한다.

---

## 7. 대안 비교 요약

| 항목 | Decisions API (채택) | Jev (비교 대상) | Responses API + 구조화 출력 (05 기존안) |
|---|---|---|---|
| 답 형식 | 타입 고정, 확률 | 타입 고정, 확률 | 생성 JSON. 확률은 logprobs로 근사 |
| 한국어 | 미확인(강할 가능성) | 약함(공식) | 강함 |
| 이미지 | 가능 | 불가 | 가능 |
| 비용 (입력/출력, 1M) | $0.10 / 0 | $0.042 / 0 | gpt-6-luna $0.10 / $0.50 |
| 속도 | Responses 대비 약 10배(주장) | 150ms 수준(주장) | 기준 |
| 성숙도 | 베타 | 정식(신생 회사) | 정식 |

---

## 8. 검증 실험 (도입 확정 전 필수)

- 데이터: `eval/`의 광고 후보(정답) + 미끼(`decoys`: D03 정상 전각, D04 정상 자모, D05 광고 키워드가 든 정상 공지, sr-only 접근성 텍스트) + 04 §7.1 2군 키워드 문장. **최소 60건(양성 30, 음성 30).**
- 비교 대상: ① 규칙 `ad_score`만 ② Decisions만 ③ Jev만 ④ 규칙 + Decisions(§6.4) ⑤ 규칙 + Jev
- 변형: 질문 영어 vs 한국어, 정규화 텍스트 있음 vs 없음, `task` 맥락 있음 vs 없음(거부율), `ad_category` 선택지 순서 정방향 vs 역방향
- 측정: 정밀도·재현율, 경계 구간 정답률, 보정 상태(q 구간 0.0~0.2 / 0.2~0.4 / … 별 실제 양성 비율), **거부율**, 지연시간(p50·p95), 요청당 입력 토큰
- **합격 기준:** ④가 ①보다 경계 구간 정답률이 높고 전체 정밀도가 떨어지지 않음. 거부율 10% 미만. 지연 p95 < 1초. 미달이면 AI는 화면 근거 표시용으로만 쓰고 결정권을 주지 않는다.
- **교체 기준:** ⑤가 ④보다 경계 구간 정답률이 확실히 높거나(5%p 이상), Decisions 거부율이 10% 이상이면 Jev로 교체한다.
- 결과는 이 문서 하단 또는 `todo/04-탐지-4종.md` 완료 기록에 남긴다.

---

## 9. 다른 문서에서 고칠 점

| 문서 | 현재 | 수정 |
|---|---|---|
| 05 §핵심결론 추천 스택 | "선택적 OpenAI 호출(.env)" | "선택적 OpenAI Decisions API 호출(`gpt-6-luna`, .env)" |
| 05 §6 AI API 비용 | Responses API 기준 묶음 호출·프롬프트 캐시 | Decisions는 후보 1건 = 요청 1건, 질문 병렬, 캐시·출력 과금 없음. §6.5·§6.6으로 대체 |
| 04 §7.3 마지막 줄 | "LLM 재판정(옵션): 2~3점 후보만" | "Decisions API 판정: 경계 구간 후보, q ≥ 0.4 출력(07 문서 §6.4)" |
| 06 C-9 이미지 속 광고 | CPU OCR, C등급 | Decisions 이미지 입력으로 OCR 없이 판정 가능 → 등급 재검토 |
| todo/01 기술스택 | AI 사용 범위 미정 | "OpenAI Decisions API(`gpt-6-luna`), 광고성 판정 보조, 규칙 폴백" |
| 사용설명서(todo/09) | — | 서비스명 OpenAI Decisions API, 모델명 `gpt-6-luna`, 환경변수 `OPENAI_API_KEY`·`OPENAI_DECISIONS_MODEL`, 유료 등급 키 필요 명시 (모집요강 필수) |

---

## 10. 출처 (2026-10-14 열람)

OpenAI
- Decisions 가이드 — https://developers.openai.com/api/docs/guides/decisions
- Decisions API 레퍼런스 — https://developers.openai.com/api/reference/resources/decisions/methods/create
- gpt-6-luna 모델 페이지 (가격·한도·컨텍스트) — https://developers.openai.com/api/docs/models/gpt-6-luna
- 변경 이력 (2026-10-06 Decisions API 베타 출시, 2026-09-22 GPT-6 Luna 출시) — https://developers.openai.com/api/docs/changelog

TypeSafe
- Introduction — https://docs.typesafe.ai/introduction
- System One — https://docs.typesafe.ai/concepts/system-one
- State — https://docs.typesafe.ai/concepts/state
- Primitives / Choice / Noul / Score — https://docs.typesafe.ai/primitives
- Confidence — https://docs.typesafe.ai/confidence
- Models (가격·한도·언어·데이터 처리) — https://docs.typesafe.ai/models
- Jev 1.13 jaggedness (2026-10-02 검토판) — https://docs.typesafe.ai/model-jaggedness/jev-1.13
- API reference — https://docs.typesafe.ai/api
- Example use cases (150ms 주장) — https://docs.typesafe.ai/concepts/use-case-map
- Python SDK — https://github.com/typesafe-ai/typesafe-sdk-python (MIT), https://pypi.org/project/typesafe-sdk/ (0.7.4)
