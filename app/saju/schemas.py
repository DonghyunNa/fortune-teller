from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Calendar(str, Enum):
    SOLAR = "solar"
    LUNAR = "lunar"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"


# 톤 프리셋 — 이 키워드로 들어오면 LLM에 풀어 설명. 그 외 자유 입력은 그대로 LLM에 전달
TONE_PRESETS = ("balanced", "playful", "scholarly")


class SajuCalcRequest(BaseModel):
    birth_date: date = Field(..., description="생년월일. calendar 필드 기준으로 양력/음력 해석")
    birth_hour: Optional[int] = Field(
        None, ge=0, le=23, description="0~23시. 모르면 null (시주를 계산하지 않음)"
    )
    birth_minute: Optional[int] = Field(0, ge=0, le=59, description="분 (기본 0)")
    calendar: Calendar = Field(Calendar.SOLAR, description="solar=양력, lunar=음력")
    is_leap_month: bool = Field(False, description="음력일 때만 유효. 윤달이면 true")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "birth_date": "1991-11-29",
                    "birth_hour": 14,
                    "birth_minute": 0,
                    "calendar": "solar",
                    "is_leap_month": False,
                }
            ]
        }
    }


class Pillar(BaseModel):
    stem: str           # 천간 (한글) — 예: "갑"
    branch: str         # 지지 (한글) — 예: "자"
    sexagenary: str     # 60갑자 (한글 2글자) — 예: "갑자"
    stem_element: str   # 천간 오행 — 목/화/토/금/수
    branch_element: str # 지지 오행


class SajuCalcResponse(BaseModel):
    pillars: dict[str, Optional[Pillar]] = Field(
        ..., description="year/month/day/hour 네 기둥. hour는 birth_hour=null이면 None"
    )
    day_master: str = Field(..., description="일간(日干) — 십신 계산 기준이 되는 천간")
    day_master_element: str
    elements: dict[str, int] = Field(
        ..., description="오행 분포: {목, 화, 토, 금, 수}. 시주 미상 시 6자 기준"
    )
    ten_gods: dict[str, str] = Field(
        ...,
        description="십신: {year_stem, month_stem, hour_stem}. 일간은 제외. hour_stem은 시주 미상 시 누락",
    )
    hour_unknown: bool = Field(..., description="birth_hour=null이었는지")
    normalized: dict = Field(
        ...,
        description="내부 계산 정보: solar_date(양력 변환된 일자), pre_ipchun(입춘 전 출생자 여부) 등",
    )


class SajuInterpretRequest(BaseModel):
    pillars: SajuCalcResponse = Field(
        ...,
        description="**`POST /saju/calc` 응답 객체를 그대로 복사해서 넣으세요.** 빈 객체로는 동작하지 않습니다.",
    )
    focus: Optional[str] = Field(
        None,
        max_length=100,
        description="해석 초점, 자유 입력. 예: '직업운', '연애운', '건강', '대인 관계'. 없으면 종합",
    )
    tone: Optional[str] = Field(
        "balanced",
        max_length=100,
        description="풀이 톤, 자유 입력. 프리셋: balanced / playful / scholarly. "
        "그 외 자유 표현(예: '20대 친구처럼', '도사풍')도 가능",
    )
    gender: Optional[Gender] = Field(
        None, description="male / female (LLM 풀이의 컨텍스트)"
    )
    context: Optional[str] = Field(
        None,
        max_length=500,
        description="추가 맥락 자유 입력. 예: '최근 새로운 인연이 생겼습니다'",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pillars": "(POST /saju/calc 응답 객체를 여기에 그대로 붙여넣으세요)",
                    "focus": "연애운",
                    "tone": "balanced",
                    "gender": "male",
                    "context": "최근 새로운 인연이 생겨 궁금합니다",
                }
            ]
        }
    }


class SajuReadingRequest(BaseModel):
    """`/saju/calc`와 `/saju/interpret`을 한 번에 호출하는 통합 엔드포인트 입력."""

    # --- 사주 계산용 입력 ---
    birth_date: date = Field(..., description="생년월일 (calendar 기준)")
    birth_hour: Optional[int] = Field(
        None, ge=0, le=23, description="0~23시. 모르면 null"
    )
    birth_minute: Optional[int] = Field(0, ge=0, le=59)
    calendar: Calendar = Field(Calendar.SOLAR)
    is_leap_month: bool = Field(False, description="음력 윤달이면 true")

    # --- 풀이용 입력 (나이는 birth_date에서 자동 계산) ---
    focus: Optional[str] = Field(
        None, max_length=100, description="해석 초점, 자유 입력. 없으면 종합"
    )
    tone: Optional[str] = Field(
        "balanced",
        max_length=100,
        description="풀이 톤, 자유 입력. 프리셋: balanced / playful / scholarly",
    )
    gender: Optional[Gender] = Field(None)
    context: Optional[str] = Field(None, max_length=500)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "birth_date": "1991-11-29",
                    "birth_hour": 14,
                    "birth_minute": 0,
                    "calendar": "solar",
                    "is_leap_month": False,
                    "focus": "연애운",
                    "tone": "balanced",
                    "gender": "male",
                    "context": "최근 새로운 인연이 생겨 궁금합니다",
                }
            ]
        }
    }


class SajuReadingResponse(BaseModel):
    """통합 응답: 사주팔자 계산 결과 + LLM 풀이."""

    pillars: SajuCalcResponse
    interpretation: Optional[str] = None
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(
        None, description="LLM 호출 실패 시 메시지. 계산 자체가 실패하면 422로 응답"
    )


class SajuInterpretResponse(BaseModel):
    interpretation: Optional[str] = Field(
        None, description="LLM 풀이 본문. 호출 실패 시 null, error 필드 참조"
    )
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(None, description="LLM 호출 실패 시 에러 메시지")
