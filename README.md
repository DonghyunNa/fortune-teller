# Fortune Telling API

한국식 사주명리부터 시작하는 멀티 운세 FastAPI 서비스. Anthropic Claude로 자연어 풀이를 생성합니다.

> 학습·재미용 MVP — 절기 시각은 평균값 근사를 사용하므로 정밀 사주 풀이에는 부적합합니다.

**스택**: Python 3.11+ · FastAPI · Anthropic SDK (`claude-sonnet-4-6`) · `korean-lunar-calendar`

## 빠른 시작

`Makefile`을 사용하면 npm scripts처럼 한 줄로 끝납니다.

```bash
# 1) 의존성 설치 (자동으로 .venv 생성)
make install

# 2) Anthropic API 키 설정 (/saju/interpret · /saju/reading 호출 시 필요. /saju/calc은 키 없이 사용 가능)
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY=sk-ant-... 채우기
# (선택) ANTHROPIC_MODEL 환경변수로 모델 ID override 가능

# 3) 개발 서버 (자동 reload)
make dev
# → http://127.0.0.1:8000/docs 에서 OpenAPI UI 사용
```

사용 가능한 명령어 (`make` 또는 `make help`):

| 명령 | 동작 |
|------|------|
| `make install` | `.venv` 생성(없으면) + 의존성 설치 |
| `make dev` | 개발 서버 (코드 변경 시 자동 reload) |
| `make run` | 운영 모드 (0.0.0.0:8000) |
| `make test` | 테스트 실행 (`pytest`) |
| `make clean` | `__pycache__`·빌드 산출물 제거 |

## 엔드포인트

### `POST /saju/calc` — 사주팔자 계산

요청:
```json
{
  "birth_date": "1990-06-15",
  "birth_hour": 14,
  "birth_minute": 30,
  "calendar": "solar",
  "is_leap_month": false
}
```

응답 (일부):
```json
{
  "pillars": {
    "year": {"stem": "경", "branch": "오", "sexagenary": "경오", "stem_element": "금", "branch_element": "화"},
    "month": {"stem": "임", "branch": "오", "sexagenary": "임오", "...": "..."},
    "day": {"...": "..."},
    "hour": {"...": "..."}
  },
  "day_master": "...",
  "elements": {"목": 1, "화": 3, "토": 1, "금": 2, "수": 1},
  "ten_gods": {"year_stem": "정관", "month_stem": "편인", "hour_stem": "비견"},
  "hour_unknown": false,
  "normalized": {"...": "..."}
}
```

- **시간 미정**: `birth_hour: null` 입력 시 `pillars.hour = null`, `hour_unknown = true`, 십신에서 `hour_stem` 키 누락.
- **음력**: `calendar: "lunar"` + 윤달이면 `is_leap_month: true`.

### `POST /saju/reading` — 통합 풀이 (계산 + LLM 한 번에)

`calc` + `interpret`을 한 번에 처리합니다. `focus`/`tone` 외에 `gender`/`context`로 LLM 컨텍스트를 보강할 수 있습니다. 만 나이는 `birth_date`에서 서버가 자동 계산합니다.

요청:
```json
{
  "birth_date": "1991-11-29",
  "birth_hour": 14,
  "birth_minute": 0,
  "calendar": "solar",
  "is_leap_month": false,
  "focus": "연애운",
  "tone": "balanced",
  "gender": "male",
  "context": "최근 새로운 인연이 생겨 궁금합니다"
}
```

- `focus`: 자유 입력. 예: `"연애운"`, `"직업운"`, `"건강"`, `"대인 관계"`. 생략하면 종합 풀이
- `tone`: 자유 입력. 프리셋 `balanced` / `playful` / `scholarly`는 풀어 설명되고, 그 외(예: `"20대 친구처럼"`, `"도사풍"`)는 입력 그대로 LLM 지시문이 됨
- `gender`: `male` / `female` (선택)
- `context`: 자유 메모 최대 500자 (선택)

응답: `pillars`(사주팔자 풀세트) + `interpretation`(LLM 풀이) + `model`/`tokens_*`/`error`.

- 계산 실패(범위 밖·윤달 오류) → 422
- LLM 실패 → 200 + `interpretation: null` + `error: "..."`

### `POST /saju/interpret` — LLM 자연어 풀이

`/saju/calc`의 응답 객체를 그대로 `pillars` 필드에 넣어 호출합니다.

요청:
```json
{
  "pillars": { "...": "/saju/calc 응답 그대로" },
  "focus": "직업운",
  "tone": "balanced"
}
```

- `focus`: 풀이 초점 자유 입력. 생략하면 종합 풀이
- `tone`: 자유 입력. 프리셋 `balanced`/`playful`/`scholarly` 또는 자유 표현
- `gender`: `male` / `female` (선택)
- `context`: 자유 메모 최대 500자 (선택)

만 나이는 `pillars.normalized.solar_date`에서 서버가 자동 계산해 LLM 컨텍스트로 전달됩니다.

응답:
```json
{
  "interpretation": "...자연어 풀이...",
  "model": "claude-sonnet-4-6",
  "tokens_in": 540,
  "tokens_out": 1280,
  "error": null
}
```

LLM 호출 실패 시 `interpretation: null`, `error: "..."`. 서버 500은 발생하지 않습니다.

### `POST /daily/calc` — 일일운세(일진) 계산

해당 날짜의 일진(日辰, 그날의 60갑자 일주)을 계산합니다. `birth_date`를 주면 사용자 일간과의 관계(십신)·오행 보강까지 개인화되고, 없으면 일진 자체의 기운만 풀이합니다.

요청 (개인화):
```json
{
  "target_date": "2026-06-12",
  "birth_date": "1991-11-29",
  "birth_hour": 14,
  "birth_minute": 0,
  "calendar": "solar",
  "is_leap_month": false
}
```

응답 (개인화):
```json
{
  "day_ganzhi": {"stem": "계", "branch": "미", "sexagenary": "계미", "stem_element": "수", "branch_element": "토"},
  "target_date": "2026-06-12",
  "personalized": true,
  "day_master": "기",
  "relation_ten_god": "편재",
  "element_focus": {
    "day_stem_element": "수",
    "day_branch_element": "토",
    "user_elements": {"목": 0, "화": 1, "토": 4, "금": 2, "수": 1},
    "reinforced": []
  },
  "normalized": {"today_used": false, "calendar_input": "solar", "ja_si_policy": "야자시"}
}
```

- **`target_date` 기본값**: 비우면 오늘(KST)을 사용하고 `normalized.today_used = true`로 신호합니다. 지원 범위는 1900~2050.
- **개인화 차이**:
  - `birth_date` 있음 → `personalized: true`, `day_master`(사용자 일간)·`relation_ten_god`(일간 기준 오늘 천간의 십신)·`element_focus.user_elements`/`reinforced`(오늘 보강되는 기운)까지 채워집니다.
  - `birth_date` 없음 → `personalized: false`, `day_master`/`relation_ten_god`는 `null`, `element_focus`는 `day_stem_element`/`day_branch_element` 2키만(그날 일진의 오행만).
- **`birth_hour`**: 일진과의 관계(일간·십신)는 날짜 기준이라 시주의 영향이 없습니다. 다만 `element_focus.user_elements`/`reinforced`(오행 분포 보강)에는 시주가 한 글자 더해지므로, `birth_hour` 값에 따라 보강 오행이 달라질 수 있습니다.

### `POST /daily/reading` — 일일운세 통합 풀이 (계산 + LLM 한 번에)

`/daily/calc` + `/daily/interpret`을 한 번에 처리합니다.

요청:
```json
{
  "target_date": "2026-06-12",
  "birth_date": "1991-11-29",
  "birth_hour": 14,
  "birth_minute": 0,
  "calendar": "solar",
  "is_leap_month": false,
  "focus": "일/업무",
  "tone": "balanced",
  "gender": "male",
  "context": "오늘 중요한 미팅이 있습니다"
}
```

- `target_date` 생략 시 오늘(KST)의 운세를 봅니다.
- `focus`: 오늘 풀이 초점 자유 입력. 예: `"일/업무"`, `"관계"`, `"재물"`, `"건강"`. 생략하면 종합
- `tone`: 자유 입력. 프리셋 `balanced`/`playful`/`scholarly` 또는 자유 표현
- `gender`: `male` / `female` (선택), `context`: 자유 메모 최대 500자 (선택)

응답: `daily`(일진 계산 결과) + `interpretation`(LLM 풀이) + `model`/`tokens_*`/`error`.

- 계산 실패(범위 밖·윤달 오류) → 422
- LLM 실패 → 200 + `interpretation: null` + `error: "..."`

### `POST /daily/interpret` — 일일운세 LLM 풀이

`/daily/calc`의 응답 객체를 그대로 `daily` 필드에 넣어 호출합니다.

요청:
```json
{
  "daily": { "...": "/daily/calc 응답 그대로" },
  "focus": "일/업무",
  "tone": "balanced",
  "gender": "male",
  "context": "오늘 중요한 미팅이 있습니다"
}
```

- 개인화 응답(`personalized: true`)을 넣으면 일간·십신·오행 보강을 반영한 풀이가, 비개인화 응답을 넣으면 일진 전반의 기운만 풀이됩니다.
- 응답 shape·에러 정책은 `/saju/interpret`과 동일(`interpretation`/`model`/`tokens_in`/`tokens_out`/`error`, LLM 실패 시 200 + `error`).

### `POST /tarot/draw` — 타로 카드 추출 (LLM 없음)

스프레드에 맞춰 카드를 뽑습니다. LLM을 호출하지 않으므로 API 키 없이 사용 가능합니다.

요청 (one 스프레드):
```json
{
  "spread": "one",
  "allow_reversed": true,
  "seed": 42
}
```

응답 (one):
```json
{
  "spread": "one",
  "cards": [
    {
      "name_en": "The Star",
      "name_ko": "별",
      "arcana": "major",
      "suit": null,
      "reversed": false,
      "position": null,
      "keywords": ["희망", "영감", "치유", "평온"]
    }
  ],
  "normalized": {"seed_used": 42, "seed_provided": true, "allow_reversed": true, "card_count": 1}
}
```

요청 (three 스프레드):
```json
{
  "spread": "three",
  "allow_reversed": true,
  "seed": 42
}
```

응답 (three): `cards`가 3장이며 각 카드에 `position`("과거"/"현재"/"미래")이 채워집니다.
```json
{
  "spread": "three",
  "cards": [
    {"name_en": "The Fool", "name_ko": "바보", "arcana": "major", "suit": null, "reversed": false, "position": "과거", "keywords": ["새로운 시작", "순수함", "모험", "자유"]},
    {"name_en": "Ace of Wands", "name_ko": "완드 에이스", "arcana": "minor", "suit": "완드", "reversed": true, "position": "현재", "keywords": ["...(역방향 키워드)..."]},
    {"name_en": "...", "name_ko": "...", "arcana": "...", "position": "미래", "keywords": ["..."]}
  ],
  "normalized": {"seed_used": 42, "seed_provided": true, "allow_reversed": true, "card_count": 3}
}
```

- **재현성(`seed`)**: 같은 `seed`는 항상 같은 카드·방향·순서를 보장합니다. `seed`를 비우면 무작위로 뽑되, 실제 사용한 seed를 `normalized.seed_used`에 기록하므로 그 값을 다시 넣으면 동일 결과를 재현할 수 있습니다(`seed_provided`로 사용자가 직접 준 seed인지 구분).
- **정/역방향(`allow_reversed`)**: `true`(기본)면 카드마다 50% 확률로 역방향(`reversed: true`)이 나오고, 카드의 `keywords`도 해당 방향 기준으로 채워집니다. `false`면 전부 정방향으로 고정됩니다(입문/간이 모드).
- **스프레드(`spread`)**: `one`(1장) / `three`(과거·현재·미래 3장)만 구현되어 있습니다. **`celtic`은 Swagger 스키마에 값이 노출되지만 v0.1 미구현이라 선택 시 항상 `422`를 반환합니다.**

### `POST /tarot/interpret` — 타로 LLM 풀이

`/tarot/draw`의 응답 객체를 **그대로** `draw` 필드에 넣어 호출합니다(라운드트립).

요청:
```json
{
  "draw": { "...": "POST /tarot/draw 응답 객체를 그대로 붙여넣기" },
  "question": "이직을 고민 중입니다",
  "focus": "진로",
  "tone": "balanced",
  "gender": "female",
  "context": "최근 일에 대한 회의감이 큽니다"
}
```

- `draw`: **`/tarot/draw` 응답을 통째로** 넣습니다. 빈 객체로는 동작하지 않습니다.
- `question`: 알고 싶은 질문/고민 자유 입력(최대 200자). 생략하면 일반 풀이
- `focus`: 풀이 초점 자유 입력(예: `"연애"`, `"진로"`, `"재물"`). 생략하면 종합
- `tone`: 자유 입력. 프리셋 `balanced`/`playful`/`scholarly` 또는 자유 표현(예: `"20대 친구처럼"`)
- `gender`: `male` / `female` (선택), `context`: 자유 메모 최대 500자 (선택)

응답:
```json
{
  "interpretation": "...뽑힌 카드와 방향을 근거로 한 자연어 풀이...",
  "model": "claude-sonnet-4-6",
  "tokens_in": 480,
  "tokens_out": 1100,
  "error": null
}
```

LLM 호출 실패 시 `interpretation: null`, `error: "..."`. 서버 500은 발생하지 않습니다.

### `POST /tarot/reading` — 타로 통합 풀이 (추출 + LLM 한 번에)

`/tarot/draw` + `/tarot/interpret`을 한 번에 처리합니다. 추출 입력(spread/allow_reversed/seed)과 풀이 입력(question/focus/tone/gender/context)을 함께 보냅니다.

요청:
```json
{
  "spread": "three",
  "allow_reversed": true,
  "seed": 42,
  "question": "이직을 고민 중입니다",
  "focus": "진로",
  "tone": "balanced",
  "gender": "female",
  "context": "최근 일에 대한 회의감이 큽니다"
}
```

응답: `draw`(카드 추출 결과 풀세트) + `interpretation`(LLM 풀이) + `model`/`tokens_*`/`error`.

- `seed`를 주면 추출이 재현 가능하므로 통합 풀이도 카드 구성이 동일해집니다.
- 추출 실패(미구현 스프레드 `celtic` 등) → 422
- LLM 실패 → 200 + `interpretation: null` + `error: "..."`

> **라운드트립 사용법**: `/tarot/draw`로 먼저 카드만 뽑아 사용자에게 보여준 뒤, 그 응답 객체를 그대로 `/tarot/interpret`의 `draw` 필드에 넣어 풀이를 받는 2단계 흐름을 쓸 수 있습니다. 추출과 풀이를 한 번에 끝내려면 `/tarot/reading`을 쓰세요.

## 도메인 룰 요약

| 항목 | 룰 |
|------|---|
| 연주 | 입춘 절기 시각 기준 (음력 1월 1일 X) |
| 월주 | 24절기 중 12개 절(節) 구간 기준 |
| 일주 | EPOCH 1900-01-01 = 경자(36) 기반 60갑자 |
| 시주 | 야자시(23시 출생도 일주는 당일) |
| 오행 | 8자(시주 미상 시 6자) 카운트 |
| 십신 | 일간 vs 다른 천간(연·월·시)의 오행+음양 관계 |

## 알려진 한계 (v0.1)

- **24절기 시각 정밀도**: 평균 시각 ±수 시간 오차. 절기 ±12시간 경계 입력은 결과가 달라질 수 있음
- **`korean-lunar-calendar` 지원 범위**: 1900~2050
- **진태양시 보정 미적용**: KST 그대로 사용
- **자시 정책 옵션 없음**: 야자시 고정

정밀 풀이가 필요하면 24절기 시각을 정확한 천문 계산 라이브러리(`sxtwl` 등)로 교체하세요.

## 확장: 새 운세 모듈 추가

타로·별자리·일일운세 등은 같은 구조로 추가합니다.

1. `app/{type}/` 디렉토리 생성 — `router.py`, `schemas.py`, `calculator.py` (또는 `picker.py`), `interpreter.py`
2. `app/main.py`에 한 줄 추가:
   ```python
   from app.tarot.router import router as tarot_router
   app.include_router(tarot_router, prefix="/tarot", tags=["tarot"])
   ```

## 면책

학습·재미용 토이 프로젝트입니다. 운세 풀이 결과는 자기 이해를 위한 도구이지 단정적 미래 예측이 아닙니다.
