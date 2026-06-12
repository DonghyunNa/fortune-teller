from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# 성별 enum은 사주 모듈의 공통 정의를 재사용한다(풀이 컨텍스트용).
from app.saju.schemas import Gender


class Spread(str, Enum):
    """스프레드 종류. one/three만 구현. celtic은 스키마에만 존재(draw에서 422)."""

    ONE = "one"
    THREE = "three"
    CELTIC = "celtic"  # v0.1 미구현 — draw 시 422


class Arcana(str, Enum):
    MAJOR = "major"
    MINOR = "minor"


class DrawnCard(BaseModel):
    name_en: str = Field(..., description="카드 영문명. 예: 'The Fool', 'Ace of Wands'")
    name_ko: str = Field(..., description="카드 한글명. 예: '바보', '완드 에이스'")
    arcana: Arcana = Field(..., description="major(메이저 아르카나) / minor(마이너 아르카나)")
    suit: Optional[str] = Field(
        None, description="마이너 아르카나의 수트(완드/컵/소드/펜타클). 메이저면 null"
    )
    reversed: bool = Field(..., description="역방향이면 true, 정방향이면 false")
    position: Optional[str] = Field(
        None, description="스프레드 내 위치 라벨. three면 과거/현재/미래, one이면 null"
    )
    keywords: list[str] = Field(
        ..., description="현재 방향(정/역) 기준 키워드 리스트. LLM 풀이의 참고용 근거"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name_en": "The Star",
                    "name_ko": "별",
                    "arcana": "major",
                    "suit": None,
                    "reversed": False,
                    "position": "현재",
                    "keywords": ["희망", "영감", "치유", "평온"],
                }
            ]
        }
    }


class TarotDrawRequest(BaseModel):
    spread: Spread = Field(
        Spread.ONE,
        description="**one(1장) / three(과거·현재·미래 3장)만 구현됨.** "
        "celtic 값은 스키마에 노출되지만 v0.1 미구현이라 선택 시 항상 422를 반환합니다.",
    )
    allow_reversed: bool = Field(
        True, description="true면 카드마다 50% 역방향. false면 전부 정방향(입문/간이 모드)"
    )
    seed: Optional[int] = Field(
        None,
        description="재현성 seed. 같은 seed=같은 카드·방향·순서. 비우면 무작위로 뽑되 "
        "사용된 seed를 normalized.seed_used에 기록(재현 가능)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"spread": "three", "allow_reversed": True, "seed": 42}
            ]
        }
    }


class TarotDrawResponse(BaseModel):
    spread: Spread = Field(..., description="사용된 스프레드")
    cards: list[DrawnCard] = Field(..., description="뽑힌 카드 목록(순서 유의)")
    normalized: dict = Field(
        ...,
        description="내부 추출 정보: seed_used(실제 사용 seed), allow_reversed, "
        "card_count, seed_provided 등. seed_used로 동일 결과 재현 가능",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "spread": "three",
                    "cards": [
                        {
                            "name_en": "The Fool",
                            "name_ko": "바보",
                            "arcana": "major",
                            "suit": None,
                            "reversed": False,
                            "position": "과거",
                            "keywords": ["새로운 시작", "순수함", "모험", "자유"],
                        }
                    ],
                    "normalized": {
                        "seed_used": 42,
                        "seed_provided": True,
                        "allow_reversed": True,
                        "card_count": 3,
                    },
                }
            ]
        }
    }


class TarotInterpretRequest(BaseModel):
    draw: TarotDrawResponse = Field(
        ...,
        description="**`POST /tarot/draw` 응답 객체를 그대로 넣으세요.** 빈 객체로는 동작하지 않습니다.",
    )
    question: Optional[str] = Field(
        None,
        max_length=200,
        description="알고 싶은 질문/고민. 자유 입력. 예: '이직을 고민 중입니다'. 없으면 일반 풀이",
    )
    focus: Optional[str] = Field(
        None,
        max_length=100,
        description="풀이 초점, 자유 입력. 예: '연애', '진로', '재물'. 없으면 종합",
    )
    tone: Optional[str] = Field(
        "balanced",
        max_length=100,
        description="풀이 톤, 자유 입력. 프리셋: balanced / playful / scholarly. "
        "그 외 자유 표현(예: '20대 친구처럼')도 가능",
    )
    gender: Optional[Gender] = Field(None, description="male / female (풀이 컨텍스트)")
    context: Optional[str] = Field(
        None, max_length=500, description="추가 맥락 자유 입력. 예: '최근 큰 변화를 겪었습니다'"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "draw": "(POST /tarot/draw 응답 객체를 여기에 그대로 붙여넣으세요)",
                    "question": "이직을 고민 중입니다",
                    "focus": "진로",
                    "tone": "balanced",
                    "gender": "female",
                    "context": "최근 일에 대한 회의감이 큽니다",
                }
            ]
        }
    }


class TarotInterpretResponse(BaseModel):
    interpretation: Optional[str] = Field(
        None, description="LLM 풀이 본문. 호출 실패 시 null, error 필드 참조"
    )
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(None, description="LLM 호출 실패 시 에러 메시지")


class TarotReadingRequest(BaseModel):
    """`/tarot/draw`와 `/tarot/interpret`을 한 번에 호출하는 통합 엔드포인트 입력."""

    # --- 카드 추출용 입력 ---
    spread: Spread = Field(
        Spread.ONE,
        description="**one / three만 구현됨.** celtic은 스키마에만 노출될 뿐 "
        "v0.1 미구현이라 선택 시 항상 422를 반환합니다.",
    )
    allow_reversed: bool = Field(True, description="false면 전부 정방향")
    seed: Optional[int] = Field(None, description="재현성 seed. 비우면 무작위(seed_used에 기록)")

    # --- 풀이용 입력 ---
    question: Optional[str] = Field(None, max_length=200, description="알고 싶은 질문/고민")
    focus: Optional[str] = Field(None, max_length=100, description="풀이 초점. 없으면 종합")
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
                    "spread": "three",
                    "allow_reversed": True,
                    "seed": 42,
                    "question": "이직을 고민 중입니다",
                    "focus": "진로",
                    "tone": "balanced",
                    "gender": "female",
                    "context": "최근 일에 대한 회의감이 큽니다",
                }
            ]
        }
    }


class TarotReadingResponse(BaseModel):
    """통합 응답: 카드 추출 결과 + LLM 풀이."""

    draw: TarotDrawResponse
    interpretation: Optional[str] = None
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error: Optional[str] = Field(
        None, description="LLM 호출 실패 시 메시지. 추출 자체가 실패하면 422로 응답"
    )
