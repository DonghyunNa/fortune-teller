from typing import Optional

from anthropic import APIError

from app._shared.llm import MODEL, get_client

from .schemas import (
    DrawnCard,
    Spread,
    TarotInterpretRequest,
    TarotInterpretResponse,
)

_SYSTEM = """당신은 타로 카드를 읽어주는 따뜻한 풀이가입니다. 사용자가 뽑은 카드(이름·정/역방향·위치·키워드)를 근거로 한국어로 풀이합니다.

규칙:
- 카드 키워드는 풀이의 "참고"일 뿐입니다. 키워드에 갇히지 말고, 카드들의 조합과 사용자의 질문/맥락을 함께 엮어 자연스럽게 해석합니다.
- 단정 대신 경향성으로 말합니다("~한 흐름이 보인다", "~에 마음을 두면 좋겠다"). 카드가 미래를 결정한다는 식의 운명결정론·미신적 표현은 피합니다.
- 타로는 점이 아니라 자기 성찰과 마음을 들여다보는 도구로 제시합니다.
- 역방향 카드는 무조건 나쁜 의미가 아니라, 그 기운이 안으로 향하거나 막혀 있거나 과한 상태일 수 있다는 관점으로 풀이합니다.
- 3~5단락으로 작성하고, 각 단락은 3~4문장 정도로 균형 있게 씁니다.
- 글머리 기호나 표는 쓰지 않고 문단으로만 씁니다.
- 카드 이름은 자연스럽게 언급하되 전문 용어 나열은 피합니다.
- 의료·법률·재정에 대한 단정적 조언은 하지 않습니다."""


_TONE_PRESETS = {
    "balanced": "균형 잡힌 차분한 톤. 평이한 한국어로 따뜻하게 쓰고 어려운 표현은 짧게 풀어 설명합니다.",
    "playful": "친근하고 가벼운 톤. 일상의 비유를 적절히 사용하고 너무 진지하지 않게 씁니다.",
    "scholarly": "타로의 상징과 전통적 의미를 살리되 풀이는 정확하게. 차분하고 단정한 문체로 씁니다.",
}


def _tone_description(tone: Optional[str]) -> str:
    if not tone:
        return _TONE_PRESETS["balanced"]
    return _TONE_PRESETS.get(tone, tone)  # 프리셋 외에는 입력 자체를 톤 지시문으로


def _render_card(card: DrawnCard, index: int) -> str:
    direction = "역방향" if card.reversed else "정방향"
    pos = f"[{card.position}] " if card.position else ""
    keywords = ", ".join(card.keywords)
    return (
        f"{index}. {pos}{card.name_ko}({card.name_en}) — {direction}\n"
        f"   참고 키워드: {keywords}"
    )


def _render_cards(req: TarotInterpretRequest) -> str:
    lines = [_render_card(c, i + 1) for i, c in enumerate(req.draw.cards)]
    return "\n".join(lines)


def _render_user_context(req: TarotInterpretRequest) -> str:
    lines: list[str] = []
    if req.gender is not None:
        ko = {"male": "남", "female": "여"}.get(req.gender.value, req.gender.value)
        lines.append(f"- 성별: {ko}")
    if req.context:
        lines.append(f"- 추가 맥락: {req.context}")
    if not lines:
        return ""
    return "## 사용자 맥락\n" + "\n".join(lines) + "\n\n"


def _spread_guidance(req: TarotInterpretRequest) -> str:
    if req.draw.spread == Spread.THREE:
        return (
            "이 스프레드는 과거-현재-미래 3장입니다. 세 카드를 따로 보지 말고 "
            "과거에서 현재로, 현재에서 앞으로 이어지는 하나의 흐름으로 엮어 풀이해주세요."
        )
    return "오늘 뽑은 한 장의 카드에 집중해 그 기운과 메시지를 풀이해주세요."


def _build_user_message(req: TarotInterpretRequest) -> str:
    cards_md = _render_cards(req)
    user_ctx = _render_user_context(req)
    tone_desc = _tone_description(req.tone)
    spread_note = _spread_guidance(req)

    question = req.question or "특정 질문 없음(전반적인 흐름을 봐주세요)"
    focus = req.focus or "종합"

    return f"""다음은 한 분이 뽑은 타로 카드입니다.

## 뽑힌 카드
{cards_md}

## 스프레드 안내
{spread_note}

## 질문/고민
{question}

{user_ctx}## 풀이 요청
- 초점: {focus}
- 톤: {tone_desc}

위 카드들을 근거로(키워드는 참고만) 3~5단락의 타로 풀이를 작성해주세요."""


def interpret_tarot(req: TarotInterpretRequest) -> TarotInterpretResponse:
    user_msg = _build_user_message(req)

    last_error: Optional[str] = None
    for attempt in range(2):  # 1회 재시도
        try:
            client = get_client()
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1800,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            )
            return TarotInterpretResponse(
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
            return TarotInterpretResponse(
                interpretation=None,
                model=None,
                tokens_in=None,
                tokens_out=None,
                error=str(e),
            )
        except Exception as e:  # noqa: BLE001
            last_error = f"Unexpected error (attempt {attempt + 1}): {type(e).__name__}: {e}"

    return TarotInterpretResponse(
        interpretation=None,
        model=None,
        tokens_in=None,
        tokens_out=None,
        error=last_error or "Unknown error",
    )
