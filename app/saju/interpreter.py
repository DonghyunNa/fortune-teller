from datetime import date
from typing import Optional

from anthropic import APIError

from app._shared.llm import MODEL, get_client

from .schemas import (
    Pillar,
    SajuCalcResponse,
    SajuInterpretRequest,
    SajuInterpretResponse,
)

_SYSTEM = """당신은 한국 명리학에 정통한 풀이가입니다. 사용자가 제공하는 사주팔자(천간·지지·오행·십신)를 바탕으로 한국어로 풀이합니다.

규칙:
- 사주팔자는 사실이고, 풀이는 해석입니다. 단정 대신 경향성 표현을 씁니다("~한 성향이 있다", "~기운이 강하다").
- 미신적·운명결정론적 표현은 피하고, 자기 이해의 도구로 제시합니다.
- 사용자가 나이·성별·추가 맥락을 제공하면, 풀이의 인생 단계와 관심사를 그에 맞게 조정합니다. 단 사주에 없는 사실을 추가로 단정하지는 않습니다.
- 일반인이 이해하지 못할 전문 용어는 사용하지 않습니다.(일간, 기토, 오행, 명리 등)
- 4~6단락으로 작성하고, 각 단락은 3~5문장 정도로 균형 있게 씁니다.
- 글머리 기호나 표는 사용하지 않고 문단으로만 씁니다."""


_TONE_PRESETS = {
    "balanced": "균형 잡힌 차분한 전문가 톤. 평이한 한국어로 명리 용어가 나오면 짧게 풀어 설명합니다.",
    "playful": "친근하고 가벼운 톤. 일상의 비유를 적절히 사용하고 너무 진지하지 않게 씁니다.",
    "scholarly": "고전 명리 용어를 적극 사용하되 풀이는 정확하게. 학자적이고 단정한 문체로 씁니다.",
}


def _tone_description(tone: Optional[str]) -> str:
    if not tone:
        return _TONE_PRESETS["balanced"]
    return _TONE_PRESETS.get(tone, tone)  # 프리셋 외에는 입력 자체를 톤 지시문으로


def _calc_age(solar_date_iso: Optional[str], today: Optional[date] = None) -> Optional[int]:
    if not solar_date_iso:
        return None
    today = today or date.today()
    try:
        birth = date.fromisoformat(solar_date_iso)
    except ValueError:
        return None
    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    return max(age, 0)


def _render_pillar(p: Optional[Pillar], label: str) -> str:
    if p is None:
        return f"| {label} | 미상 | 미상 | 미상 | 미상 | 미상 |"
    return (
        f"| {label} | {p.stem} | {p.branch} | {p.sexagenary} "
        f"| {p.stem_element} | {p.branch_element} |"
    )


def _render_pillars_table(resp: SajuCalcResponse) -> str:
    header = "| 기둥 | 천간 | 지지 | 60갑자 | 천간오행 | 지지오행 |\n|---|---|---|---|---|---|"
    rows = [
        _render_pillar(resp.pillars["year"], "연주"),
        _render_pillar(resp.pillars["month"], "월주"),
        _render_pillar(resp.pillars["day"], "일주"),
        _render_pillar(resp.pillars["hour"], "시주"),
    ]
    return header + "\n" + "\n".join(rows)


def _render_elements(elements: dict[str, int]) -> str:
    parts = [f"{k}={v}" for k, v in elements.items()]
    return ", ".join(parts)


def _render_ten_gods(ten_gods: dict[str, str], hour_unknown: bool) -> str:
    lines = [
        f"- 연간 십신: {ten_gods.get('year_stem', '?')}",
        f"- 월간 십신: {ten_gods.get('month_stem', '?')}",
    ]
    if hour_unknown:
        lines.append("- 시간 십신: 미상 (시주 미상)")
    else:
        lines.append(f"- 시간 십신: {ten_gods.get('hour_stem', '?')}")
    return "\n".join(lines)


def _render_user_context(req: SajuInterpretRequest) -> str:
    """gender/context + birth_date로부터 자동 계산한 나이를 모아 사용자 맥락 섹션 생성."""
    lines: list[str] = []
    age = _calc_age(req.pillars.normalized.get("solar_date"))
    if age is not None:
        lines.append(f"- 현재 나이: 만 {age}세 (생년월일에서 자동 계산)")
    if req.gender is not None:
        ko = {"male": "남", "female": "여"}.get(req.gender.value, req.gender.value)
        lines.append(f"- 성별: {ko}")
    if req.context:
        lines.append(f"- 추가 맥락: {req.context}")
    if not lines:
        return ""
    return "## 사용자 맥락\n" + "\n".join(lines) + "\n"


def _build_user_message(req: SajuInterpretRequest) -> str:
    pillars_md = _render_pillars_table(req.pillars)
    elements_summary = _render_elements(req.pillars.elements)
    ten_gods_md = _render_ten_gods(req.pillars.ten_gods, req.pillars.hour_unknown)
    hour_note = "시주: 미상 (시간과 관련된 풀이는 보수적으로)" if req.pillars.hour_unknown else "시주: 명시됨"
    focus = req.focus or "종합 풀이"
    tone_desc = _tone_description(req.tone)
    user_ctx = _render_user_context(req)

    return f"""다음은 한 분의 사주팔자입니다.

## 사주
{pillars_md}

## 일간(日干)
{req.pillars.day_master} ({req.pillars.day_master_element})

## 오행 분포
{elements_summary}

## 십신
{ten_gods_md}

## 메타
- {hour_note}
- 음양력 입력: {req.pillars.normalized.get("calendar_input")}
- 입춘 전 출생 여부: {req.pillars.normalized.get("pre_ipchun")}

{user_ctx}
## 풀이 요청
- 초점: {focus}
- 톤: {tone_desc}

위 정보를 바탕으로 4~6단락의 풀이를 작성해주세요."""


def interpret_pillars(req: SajuInterpretRequest) -> SajuInterpretResponse:
    user_msg = _build_user_message(req)

    last_error: Optional[str] = None
    for attempt in range(2):  # 1회 재시도
        try:
            client = get_client()
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            return SajuInterpretResponse(
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
            return SajuInterpretResponse(
                interpretation=None,
                model=None,
                tokens_in=None,
                tokens_out=None,
                error=str(e),
            )
        except Exception as e:  # noqa: BLE001
            last_error = f"Unexpected error (attempt {attempt + 1}): {type(e).__name__}: {e}"

    return SajuInterpretResponse(
        interpretation=None,
        model=None,
        tokens_in=None,
        tokens_out=None,
        error=last_error or "Unknown error",
    )
