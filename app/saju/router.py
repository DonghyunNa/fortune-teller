from fastapi import APIRouter, HTTPException

from .calculator import compute_pillars
from .interpreter import interpret_pillars
from .schemas import (
    SajuCalcRequest,
    SajuCalcResponse,
    SajuInterpretRequest,
    SajuInterpretResponse,
    SajuReadingRequest,
    SajuReadingResponse,
)

router = APIRouter()


@router.post("/calc", response_model=SajuCalcResponse, summary="사주팔자 계산")
def calc(req: SajuCalcRequest) -> SajuCalcResponse:
    try:
        return compute_pillars(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/interpret",
    response_model=SajuInterpretResponse,
    summary="사주팔자 LLM 풀이",
    description="`/saju/calc`의 응답을 그대로 `pillars` 필드에 넣어 호출합니다. "
    "ANTHROPIC_API_KEY 환경변수가 필요합니다.",
)
def interpret(req: SajuInterpretRequest) -> SajuInterpretResponse:
    return interpret_pillars(req)


@router.post(
    "/reading",
    response_model=SajuReadingResponse,
    summary="사주 통합 풀이 (계산 + LLM 해석 한 번에)",
    description="생년월일시와 focus/tone/age/gender/context를 한 번에 보내면 "
    "사주팔자 계산과 LLM 자연어 풀이를 묶어서 반환합니다. "
    "계산 단계 오류는 422, LLM 단계 오류는 응답 본문의 `error`로 전달됩니다.",
)
def reading(req: SajuReadingRequest) -> SajuReadingResponse:
    calc_req = SajuCalcRequest(
        birth_date=req.birth_date,
        birth_hour=req.birth_hour,
        birth_minute=req.birth_minute,
        calendar=req.calendar,
        is_leap_month=req.is_leap_month,
    )
    try:
        pillars = compute_pillars(calc_req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    interpret_req = SajuInterpretRequest(
        pillars=pillars,
        focus=req.focus,
        tone=req.tone,
        gender=req.gender,
        context=req.context,
    )
    interp = interpret_pillars(interpret_req)

    return SajuReadingResponse(
        pillars=pillars,
        interpretation=interp.interpretation,
        model=interp.model,
        tokens_in=interp.tokens_in,
        tokens_out=interp.tokens_out,
        error=interp.error,
    )
