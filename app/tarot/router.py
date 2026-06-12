from fastapi import APIRouter, HTTPException

from .calculator import draw_cards
from .interpreter import interpret_tarot
from .schemas import (
    TarotDrawRequest,
    TarotDrawResponse,
    TarotInterpretRequest,
    TarotInterpretResponse,
    TarotReadingRequest,
    TarotReadingResponse,
)

router = APIRouter()


@router.post("/draw", response_model=TarotDrawResponse, summary="타로 카드 추출 (LLM 없음)")
def draw(req: TarotDrawRequest) -> TarotDrawResponse:
    try:
        return draw_cards(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/interpret",
    response_model=TarotInterpretResponse,
    summary="타로 LLM 풀이",
    description="`/tarot/draw`의 응답을 그대로 `draw` 필드에 넣어 호출합니다. "
    "ANTHROPIC_API_KEY 환경변수가 필요합니다.",
)
def interpret(req: TarotInterpretRequest) -> TarotInterpretResponse:
    return interpret_tarot(req)


@router.post(
    "/reading",
    response_model=TarotReadingResponse,
    summary="타로 통합 (추출 + LLM 풀이 한 번에)",
    description="스프레드/방향/seed와 question/focus/tone/gender/context를 한 번에 보내면 "
    "카드 추출과 LLM 자연어 풀이를 묶어서 반환합니다. "
    "추출 단계 오류(미구현 스프레드 등)는 422, LLM 단계 오류는 응답 본문의 `error`로 전달됩니다.",
)
def reading(req: TarotReadingRequest) -> TarotReadingResponse:
    draw_req = TarotDrawRequest(
        spread=req.spread,
        allow_reversed=req.allow_reversed,
        seed=req.seed,
    )
    try:
        drawn = draw_cards(draw_req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    interpret_req = TarotInterpretRequest(
        draw=drawn,
        question=req.question,
        focus=req.focus,
        tone=req.tone,
        gender=req.gender,
        context=req.context,
    )
    interp = interpret_tarot(interpret_req)

    return TarotReadingResponse(
        draw=drawn,
        interpretation=interp.interpretation,
        model=interp.model,
        tokens_in=interp.tokens_in,
        tokens_out=interp.tokens_out,
        error=interp.error,
    )
