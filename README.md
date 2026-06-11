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
