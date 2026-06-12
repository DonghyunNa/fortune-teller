from datetime import date

# 만세력 로직은 사주 모듈에서 그대로 재사용한다. 재구현하지 않는다.
from app.saju.calculator import (
    BRANCH_ELEMENT,
    STEM_ELEMENT,
    _day_pillar_indices,
    _pillar_from_indices,
    _ten_god,
    compute_pillars,
)
from app.saju.schemas import SajuCalcRequest

from .schemas import DailyCalcRequest, DailyCalcResponse

# 사주 calculator의 지원 범위와 동일하게 묶는다 (일진도 korean-lunar-calendar epoch 기반).
_SUPPORTED_MIN_YEAR = 1900
_SUPPORTED_MAX_YEAR = 2050


def compute_daily(req: DailyCalcRequest) -> DailyCalcResponse:
    """그날의 일진(일주)과 (선택)사용자 일간의 명리적 관계를 계산한다."""

    # KST 가정: 서버 로컬 시각을 KST로 간주한다(별도 타임존 변환 없음).
    today_used = req.target_date is None
    target = req.target_date or date.today()

    if target.year < _SUPPORTED_MIN_YEAR or target.year > _SUPPORTED_MAX_YEAR:
        raise ValueError(
            f"지원 범위({_SUPPORTED_MIN_YEAR}~{_SUPPORTED_MAX_YEAR}) 밖의 날짜: {target}. "
            "사주 만세력과 동일한 범위만 지원합니다."
        )

    # 그날의 일진 = 그날의 60갑자 일주. 야자시 정책상 시각은 일주에 영향 없음.
    day_stem_idx, day_branch_idx = _day_pillar_indices(target)
    day_ganzhi = _pillar_from_indices(day_stem_idx, day_branch_idx)

    normalized: dict = {
        "today_used": today_used,
        "calendar_input": req.calendar.value,
        "is_leap_month_input": req.is_leap_month,
        "ja_si_policy": "야자시",
        "kst_assumption": "server_local_as_kst",
    }

    # --- 개인화 없음: 일진만 ---
    if req.birth_date is None:
        return DailyCalcResponse(
            day_ganzhi=day_ganzhi,
            target_date=target,
            personalized=False,
            day_master=None,
            relation_ten_god=None,
            element_focus={
                "day_stem_element": day_ganzhi.stem_element,
                "day_branch_element": day_ganzhi.branch_element,
            },
            normalized=normalized,
        )

    # --- 개인화: 사주 계산으로 사용자 일간 도출 (사주 calculator 재사용) ---
    saju_req = SajuCalcRequest(
        birth_date=req.birth_date,
        birth_hour=req.birth_hour,
        birth_minute=req.birth_minute,
        calendar=req.calendar,
        is_leap_month=req.is_leap_month,
    )
    saju = compute_pillars(saju_req)  # ValueError는 그대로 전파(라우터에서 422)
    day_master = saju.day_master

    # 일진 천간 ↔ 사용자 일간의 십신: 사용자 일간 기준으로 오늘 천간을 본다.
    relation_ten_god = _ten_god(day_master, day_ganzhi.stem)

    # 오늘 들어오는 오행(일진 천간/지지)을 사용자 오행 분포와 대비.
    user_elements = saju.elements
    day_elements = {day_ganzhi.stem_element, day_ganzhi.branch_element}

    # "보강": 사용자 사주에서 약한(분포가 적은) 오행을 오늘 일진이 채워주는지.
    if user_elements:
        min_count = min(user_elements.values())
    else:
        min_count = 0
    reinforced = sorted(
        e for e in day_elements if user_elements.get(e, 0) <= min_count
    )

    element_focus = {
        "day_stem_element": day_ganzhi.stem_element,
        "day_branch_element": day_ganzhi.branch_element,
        "user_elements": user_elements,
        # 오늘 일진이 사용자에게 상대적으로 부족한 기운을 채워주는 오행 목록
        "reinforced": reinforced,
    }

    return DailyCalcResponse(
        day_ganzhi=day_ganzhi,
        target_date=target,
        personalized=True,
        day_master=day_master,
        relation_ten_god=relation_ten_god,
        element_focus=element_focus,
        normalized=normalized,
    )


# STEM_ELEMENT / BRANCH_ELEMENT는 재사용 import를 노출만 해두어(향후 풀이 확장용)
# 사주 모듈의 단일 출처를 유지한다.
__all__ = ["compute_daily", "STEM_ELEMENT", "BRANCH_ELEMENT"]
