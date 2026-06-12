from fastapi import APIRouter, HTTPException

from .calculator import compute_daily
from .interpreter import interpret_daily
from .schemas import (
    DailyCalcRequest,
    DailyCalcResponse,
    DailyInterpretRequest,
    DailyInterpretResponse,
    DailyReadingRequest,
    DailyReadingResponse,
)

router = APIRouter()


@router.post("/calc", response_model=DailyCalcResponse, summary="일일운세 계산 (일진 + 일간 관계)")
def calc(req: DailyCalcRequest) -> DailyCalcResponse:
    try:
        return compute_daily(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/interpret",
    response_model=DailyInterpretResponse,
    summary="일일운세 LLM 풀이",
    description="`/daily/calc`의 응답을 그대로 `daily` 필드에 넣어 호출합니다. "
    "ANTHROPIC_API_KEY 환경변수가 필요합니다.",
)
def interpret(req: DailyInterpretRequest) -> DailyInterpretResponse:
    return interpret_daily(req)


@router.post(
    "/reading",
    response_model=DailyReadingResponse,
    summary="일일운세 통합 (계산 + LLM 풀이 한 번에)",
    description="날짜와 (선택)생년월일, focus/tone/gender/context를 한 번에 보내면 "
    "일진 계산과 LLM 자연어 풀이를 묶어서 반환합니다. "
    "계산 단계 오류는 422, LLM 단계 오류는 응답 본문의 `error`로 전달됩니다.",
)
def reading(req: DailyReadingRequest) -> DailyReadingResponse:
    calc_req = DailyCalcRequest(
        target_date=req.target_date,
        birth_date=req.birth_date,
        birth_hour=req.birth_hour,
        birth_minute=req.birth_minute,
        calendar=req.calendar,
        is_leap_month=req.is_leap_month,
    )
    try:
        daily = compute_daily(calc_req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    interpret_req = DailyInterpretRequest(
        daily=daily,
        focus=req.focus,
        tone=req.tone,
        gender=req.gender,
        context=req.context,
    )
    interp = interpret_daily(interpret_req)

    return DailyReadingResponse(
        daily=daily,
        interpretation=interp.interpretation,
        model=interp.model,
        tokens_in=interp.tokens_in,
        tokens_out=interp.tokens_out,
        error=interp.error,
    )
