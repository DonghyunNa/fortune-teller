from typing import Optional

from anthropic import APIError

from app._shared.llm import MODEL, get_client

from .schemas import DailyCalcResponse, DailyInterpretRequest, DailyInterpretResponse

_SYSTEM = """당신은 한국 명리학에 정통한 풀이가입니다. 그날의 기운(일진)과, 주어지면 그 사람의 타고난 기질(일간)의 관계를 바탕으로 "오늘 하루의 마음가짐"을 한국어로 풀이합니다.

규칙:
- 오늘의 기운은 경향성일 뿐 단정이 아닙니다. "~한 흐름이 있다", "~에 마음을 두면 좋다"처럼 부드럽게 씁니다.
- 운명결정론·미신적 표현(반드시 ~된다, ~하면 큰일난다 등)은 피하고, 하루를 더 잘 보내기 위한 참고로 제시합니다.
- 일진, 십신, 오행 같은 전문 용어는 그대로 쓰지 말고 일상 언어로 풀어서 설명합니다.
- 3~5단락으로 작성하고, 각 단락은 3~4문장 정도로 균형 있게 씁니다.
- 글머리 기호나 표는 쓰지 않고 문단으로만 씁니다.
- 의료·법률·재정에 대한 단정적 조언은 하지 않습니다."""


_TONE_PRESETS = {
    "balanced": "균형 잡힌 차분한 톤. 평이한 한국어로 쓰고 어려운 용어는 짧게 풀어 설명합니다.",
    "playful": "친근하고 가벼운 톤. 일상의 비유를 적절히 사용하고 너무 진지하지 않게 씁니다.",
    "scholarly": "고전 명리의 관점을 살리되 풀이는 정확하게. 차분하고 단정한 문체로 씁니다.",
}


def _tone_description(tone: Optional[str]) -> str:
    if not tone:
        return _TONE_PRESETS["balanced"]
    return _TONE_PRESETS.get(tone, tone)  # 프리셋 외에는 입력 자체를 톤 지시문으로


def _render_user_context(req: DailyInterpretRequest) -> str:
    lines: list[str] = []
    if req.gender is not None:
        ko = {"male": "남", "female": "여"}.get(req.gender.value, req.gender.value)
        lines.append(f"- 성별: {ko}")
    if req.context:
        lines.append(f"- 추가 맥락: {req.context}")
    if not lines:
        return ""
    return "## 사용자 맥락\n" + "\n".join(lines) + "\n\n"


def _render_personalized(daily: DailyCalcResponse) -> str:
    ef = daily.element_focus or {}
    reinforced = ef.get("reinforced") or []
    reinforced_text = ", ".join(reinforced) if reinforced else "특별히 두드러지는 보강 없음"
    user_elements = ef.get("user_elements") or {}
    elements_summary = ", ".join(f"{k}={v}" for k, v in user_elements.items())
    return f"""이 분의 타고난 기운과 오늘의 기운을 견주어 풀이합니다.

## 오늘의 기운(일진)
- 60갑자: {daily.day_ganzhi.sexagenary}
- 오늘 천간 오행: {daily.day_ganzhi.stem_element}
- 오늘 지지 오행: {daily.day_ganzhi.branch_element}

## 이 분의 타고난 중심 기운(일간)
- 일간: {daily.day_master}

## 오늘과 이 분의 관계
- 오늘 기운이 이 분에게 갖는 의미(십신): {daily.relation_ten_god}
- 이 분의 평소 오행 분포: {elements_summary}
- 오늘 채워지는(보강되는) 기운: {reinforced_text}
"""


def _render_general(daily: DailyCalcResponse) -> str:
    return f"""오늘 하루 전반의 기운을 풀이합니다(개인 사주 없이 일진만 기준).

## 오늘의 기운(일진)
- 60갑자: {daily.day_ganzhi.sexagenary}
- 오늘 천간 오행: {daily.day_ganzhi.stem_element}
- 오늘 지지 오행: {daily.day_ganzhi.branch_element}
"""


def _build_user_message(req: DailyInterpretRequest) -> str:
    daily = req.daily
    if daily.personalized:
        core = _render_personalized(daily)
    else:
        core = _render_general(daily)

    focus = req.focus or "종합(하루 전반)"
    tone_desc = _tone_description(req.tone)
    user_ctx = _render_user_context(req)

    return f"""다음은 {daily.target_date.isoformat()}의 운세 정보입니다.

{core}
{user_ctx}## 풀이 요청
- 초점: {focus}
- 톤: {tone_desc}

위 정보를 바탕으로 오늘 하루의 기운과 마음가짐에 대한 3~5단락 풀이를 작성해주세요."""


def interpret_daily(req: DailyInterpretRequest) -> DailyInterpretResponse:
    user_msg = _build_user_message(req)

    last_error: Optional[str] = None
    for attempt in range(2):  # 1회 재시도
        try:
            client = get_client()
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            )
            return DailyInterpretResponse(
                interpretation=text,
                model=resp.model,
                tokens_in=resp.usage.input_tokens,
                tokens_out=resp.usage.output_tokens,
                error=None,
            )
        except APIError as e:
            last_error = f"Anthropic APIError (attempt {attempt + 1}): {e}"
        except RuntimeError as e:
            # API 키 누락 등 (재시도 무의미)
            return DailyInterpretResponse(
                interpretation=None,
                model=None,
                tokens_in=None,
                tokens_out=None,
                error=str(e),
            )
        except Exception as e:  # noqa: BLE001
            last_error = f"Unexpected error (attempt {attempt + 1}): {type(e).__name__}: {e}"

    return DailyInterpretResponse(
        interpretation=None,
        model=None,
        tokens_in=None,
        tokens_out=None,
        error=last_error or "Unknown error",
    )
