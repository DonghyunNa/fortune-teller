from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

# 사주 모듈의 공통 enum / Pillar 재사용 — 새로 정의하지 않는다.
from app.saju.schemas import Calendar, Gender, Pillar


class DailyCalcRequest(BaseModel):
    """일일운세 계산 입력.

    target_date를 비우면 오늘(KST)을 사용한다.
    birth_date를 주면 개인화(일진↔일간 관계)되고, 없으면 일진 자체의 기운만 풀이한다.
    birth_hour/minute/calendar/is_leap_month는 사주와 동일 제약이며, 일간 계산용으로만 쓰인다.
    (일일운세는 일진=날짜 기준이라 birth_hour는 일간에 영향을 주지 않는다.)
    """

    target_date: Optional[date] = Field(
        None, description="운세를 볼 날짜(양력). 비우면 오늘(KST). 1900~2050 지원"
    )
    birth_date: Optional[date] = Field(
        None, description="생년월일(calendar 기준). 주면 개인화, 없으면 일진 전반 기운만"
    )
    birth_hour: Optional[int] = Field(
        None, ge=0, le=23, description="0~23시. 일간·십신에는 영향 없으나, 오행 분포 보강 풀이(element_focus.reinforced)에는 시주가 반영됨"
    )
    birth_minute: Optional[int] = Field(0, ge=0, le=59, description="분 (기본 0)")
    calendar: Calendar = Field(Calendar.SOLAR, description="birth_date 해석 기준. solar=양력, lunar=음력")
    is_leap_month: bool = Field(False, description="birth_date가 음력 윤달이면 true")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "target_date": "2026-06-12",
                    "birth_date": "1991-11-29",
                    "birth_hour": 14,
                    "birth_minute": 0,
                    "calendar": "solar",
                    "is_leap_month": False,
                }
            ]
        }
    }


class DailyCalcResponse(BaseModel):
    day_ganzhi: Pillar = Field(..., description="그날의 일진(日辰) = 그날의 60갑자 일주")
    target_date: date = Field(..., description="운세 대상 날짜(양력)")
    personalized: bool = Field(..., description="birth_date가 주어져 개인화되었는지")
    day_master: Optional[str] = Field(
        None, description="사용자 일간(日干). 개인화 시에만 채워짐"
    )
    relation_ten_god: Optional[str] = Field(
        None, description="사용자 일간 기준, 오늘 일진 천간의 십신. 개인화 시에만"
    )
    element_focus: Optional[dict] = Field(
        None,
        description="오늘 강조되는 오행 설명. {day_stem_element, day_branch_element, "
        "user_elements(개인화 시), reinforced(개인화 시 보강 여부)} 등",
    )
    normalized: dict = Field(
        ..., description="내부 계산 정보: today_used, calendar_input, ja_si_policy 등"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "day_ganzhi": {
                        "stem": "갑",
                        "branch": "자",
                        "sexagenary": "갑자",
                        "stem_element": "목",
                        "branch_element": "수",
                    },
                    "target_date": "2026-06-12",
                    "personalized": True,
                    "day_master": "신",
                    "relation_ten_god": "정재",
                    "element_focus": {
                        "day_stem_element": "목",
                        "day_branch_element": "수",
                        "user_elements": {"목": 1, "화": 2, "토": 1, "금": 3, "수": 1},
                        "reinforced": ["목", "수"],
                    },
                    "normalized": {
                        "today_used": False,
                        "calendar_input": "solar",
                        "ja_si_policy": "야자시",
                    },
                }
            ]
        }
    }


class DailyInterpretRequest(BaseModel):
    daily: DailyCalcResponse = Field(
        ...,
        description="**`POST /daily/calc` 응답 객체를 그대로 넣으세요.** 빈 객체로는 동작하지 않습니다.",
    )
    focus: Optional[str] = Field(
        None,
        max_length=100,
        description="오늘 풀이 초점, 자유 입력. 예: '일/업무', '관계', '재물', '건강'. 없으면 종합",
    )
    tone: Optional[str] = Field(
        "balanced",
        max_length=100,
        description="풀이 톤, 자유 입력. 프리셋: balanced / playful / scholarly. "
        "그 외 자유 표현(예: '20대 친구처럼')도 가능",
    )
    gender: Optional[Gender] = Field(None, description="male / female (풀이 컨텍스트)")
    context: Optional[str] = Field(
        None, max_length=500, description="추가 맥락 자유 입력. 예: '오늘 중요한 미팅이 있습니다'"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "daily": "(POST /daily/calc 응답 객체를 여기에 그대로 붙여넣으세요)",
                    "focus": "일/업무",
                    "tone": "balanced",
                    "gender": "male",
                    "context": "오늘 중요한 미팅이 있습니다",
                }
            ]
        }
    }


class DailyInterpretResponse(BaseModel):
    interpretation: Optional[str] = Field(
        None, description="LLM 풀이 본문. 호출 실패 시 null, error 필드 참조"
    )
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(None, description="LLM 호출 실패 시 에러 메시지")


class DailyReadingRequest(BaseModel):
    """`/daily/calc`와 `/daily/interpret`을 한 번에 호출하는 통합 엔드포인트 입력."""

    # --- 일진 + 일간 계산용 입력 ---
    target_date: Optional[date] = Field(None, description="운세 날짜(양력). 비우면 오늘(KST)")
    birth_date: Optional[date] = Field(None, description="생년월일(calendar 기준). 주면 개인화")
    birth_hour: Optional[int] = Field(None, ge=0, le=23)
    birth_minute: Optional[int] = Field(0, ge=0, le=59)
    calendar: Calendar = Field(Calendar.SOLAR)
    is_leap_month: bool = Field(False, description="birth_date 음력 윤달이면 true")

    # --- 풀이용 입력 ---
    focus: Optional[str] = Field(None, max_length=100, description="오늘 풀이 초점. 없으면 종합")
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
                    "target_date": "2026-06-12",
                    "birth_date": "1991-11-29",
                    "birth_hour": 14,
                    "birth_minute": 0,
                    "calendar": "solar",
                    "is_leap_month": False,
                    "focus": "일/업무",
                    "tone": "balanced",
                    "gender": "male",
                    "context": "오늘 중요한 미팅이 있습니다",
                }
            ]
        }
    }


class DailyReadingResponse(BaseModel):
    """통합 응답: 일진/관계 계산 결과 + LLM 풀이."""

    daily: DailyCalcResponse
    interpretation: Optional[str] = None
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(
        None, description="LLM 호출 실패 시 메시지. 계산 자체가 실패하면 422로 응답"
    )
