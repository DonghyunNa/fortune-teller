"""타로 카드 추출기.

만세력·생년월일 없음. 78장 덱에서 seed 재현성 있게 카드를 뽑는다.
seed가 없어도 사용된 seed를 normalized에 기록해 재현 가능하게 한다.
"""

import random

from .deck import FULL_DECK
from .schemas import (
    Arcana,
    DrawnCard,
    Spread,
    TarotDrawRequest,
    TarotDrawResponse,
)

# 스프레드별 뽑는 장수
_SPREAD_COUNT: dict[Spread, int] = {
    Spread.ONE: 1,
    Spread.THREE: 3,
}

# three 스프레드의 position 라벨(순서 고정)
_THREE_POSITIONS = ["과거", "현재", "미래"]

# seed가 없을 때 재현용으로 생성하는 정수 seed의 범위
_SEED_BOUND = 2**63 - 1


def draw_cards(req: TarotDrawRequest) -> TarotDrawResponse:
    """덱에서 카드를 뽑아 TarotDrawResponse를 반환한다.

    - seed 있으면 random.Random(seed)로 결정론적 추출.
    - seed 없으면 정수 seed를 먼저 생성·기록한 뒤 그 seed로 추출 → 응답만으로 재현 가능.
    - 카드는 중복 없이 sample, 방향도 같은 Random 인스턴스로 결정(재현성 유지).
    - 미구현 스프레드(celtic 등)는 ValueError → 라우터에서 422.
    """
    if req.spread not in _SPREAD_COUNT:
        supported = ", ".join(s.value for s in _SPREAD_COUNT)
        raise ValueError(
            f"미구현 스프레드입니다: '{req.spread.value}'. 현재 지원: {supported}."
        )

    seed_provided = req.seed is not None
    if seed_provided:
        seed_used = req.seed
    else:
        # seed 없을 때도 재현 가능하도록: 무작위로 정수 seed를 만들어 기록한 뒤 사용.
        seed_used = random.Random().randint(0, _SEED_BOUND)

    rng = random.Random(seed_used)

    count = _SPREAD_COUNT[req.spread]

    # 중복 없이 카드 추출 (인덱스로 sample → 덱 순서 안정)
    indices = rng.sample(range(len(FULL_DECK)), count)

    # 방향 결정: allow_reversed=True면 카드마다 50% 역방향.
    # 카드 추출 직후 같은 rng로 방향을 정해야 같은 seed에서 동일 결과가 나온다.
    cards: list[DrawnCard] = []
    for slot, deck_idx in enumerate(indices):
        card_def = FULL_DECK[deck_idx]
        if req.allow_reversed:
            is_reversed = rng.random() < 0.5
        else:
            is_reversed = False

        position = _THREE_POSITIONS[slot] if req.spread == Spread.THREE else None

        cards.append(
            DrawnCard(
                name_en=card_def.name_en,
                name_ko=card_def.name_ko,
                arcana=Arcana(card_def.arcana),
                suit=card_def.suit,
                reversed=is_reversed,
                position=position,
                keywords=card_def.keywords_for(is_reversed),
            )
        )

    normalized = {
        "seed_used": seed_used,
        "seed_provided": seed_provided,
        "allow_reversed": req.allow_reversed,
        "spread": req.spread.value,
        "card_count": count,
        "deck_size": len(FULL_DECK),
    }

    return TarotDrawResponse(
        spread=req.spread,
        cards=cards,
        normalized=normalized,
    )
