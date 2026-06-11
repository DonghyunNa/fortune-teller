from datetime import date, datetime
from typing import Optional

from korean_lunar_calendar import KoreanLunarCalendar

from .schemas import (
    Calendar,
    Pillar,
    SajuCalcRequest,
    SajuCalcResponse,
)

HEAVENLY_STEMS = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
EARTHLY_BRANCHES = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

STEM_ELEMENT = {
    "갑": "목", "을": "목",
    "병": "화", "정": "화",
    "무": "토", "기": "토",
    "경": "금", "신": "금",
    "임": "수", "계": "수",
}
BRANCH_ELEMENT = {
    "인": "목", "묘": "목",
    "사": "화", "오": "화",
    "진": "토", "술": "토", "축": "토", "미": "토",
    "신": "금", "유": "금",
    "해": "수", "자": "수",
}
STEM_YIN_YANG = {
    "갑": "양", "병": "양", "무": "양", "경": "양", "임": "양",
    "을": "음", "정": "음", "기": "음", "신": "음", "계": "음",
}

ELEMENTS = ["목", "화", "토", "금", "수"]

# 60갑자 EPOCH: 1900-01-01 양력 = 경자(庚子) 일 → 인덱스 36
_EPOCH = date(1900, 1, 1)
_EPOCH_INDEX = 36

# korean-lunar-calendar 라이브러리 지원 범위
_SUPPORTED_MIN_YEAR = 1900
_SUPPORTED_MAX_YEAR = 2050


def _sexagenary(stem_idx: int, branch_idx: int) -> str:
    return HEAVENLY_STEMS[stem_idx % 10] + EARTHLY_BRANCHES[branch_idx % 12]


def _pillar_from_indices(stem_idx: int, branch_idx: int) -> Pillar:
    stem = HEAVENLY_STEMS[stem_idx % 10]
    branch = EARTHLY_BRANCHES[branch_idx % 12]
    return Pillar(
        stem=stem,
        branch=branch,
        sexagenary=stem + branch,
        stem_element=STEM_ELEMENT[stem],
        branch_element=BRANCH_ELEMENT[branch],
    )


def _to_solar(req: SajuCalcRequest) -> date:
    y = req.birth_date.year
    if y < _SUPPORTED_MIN_YEAR or y > _SUPPORTED_MAX_YEAR:
        raise ValueError(
            f"지원 범위({_SUPPORTED_MIN_YEAR}~{_SUPPORTED_MAX_YEAR}) 밖의 연도: {y}. "
            "v0.1은 korean-lunar-calendar 라이브러리 검증 범위만 지원합니다."
        )

    if req.calendar == Calendar.SOLAR:
        return req.birth_date

    cal = KoreanLunarCalendar()
    ok = cal.setLunarDate(
        req.birth_date.year,
        req.birth_date.month,
        req.birth_date.day,
        bool(req.is_leap_month),
    )
    if not ok:
        raise ValueError(
            f"음력 변환 실패: {req.birth_date} (leap={req.is_leap_month}). "
            "윤달 존재 여부를 확인하세요."
        )
    solar = date(cal.solarYear, cal.solarMonth, cal.solarDay)

    # 라운드트립 검증: 라이브러리가 setLunarDate를 통과시켰지만 윤달이 실제로 없어서
    # 잘못된 양력 날짜를 돌려주는 케이스를 방어한다 (예: 1995년 윤9월은 존재 X).
    try:
        verify = KoreanLunarCalendar()
        verify.setSolarDate(solar.year, solar.month, solar.day)
        if (verify.lunarYear, verify.lunarMonth, verify.lunarDay) != (
            req.birth_date.year,
            req.birth_date.month,
            req.birth_date.day,
        ):
            raise ValueError(
                f"음력 입력 검증 실패: 입력 {req.birth_date} "
                f"(leap={req.is_leap_month}) → 양력 {solar} → 음력 재변환 "
                f"{verify.lunarYear}-{verify.lunarMonth}-{verify.lunarDay}. "
                "해당 음력 날짜가 존재하지 않거나 윤달 정보가 부정확합니다."
            )
    except AttributeError:
        # 라이브러리에 setSolarDate / lunar* 속성이 없으면 라운드트립 검증 생략 (한계 명시)
        pass
    return solar


def _birth_datetime(solar: date, hour: Optional[int], minute: Optional[int]) -> datetime:
    """시간이 None이면 12:00 KST로 가정(연주·월주 분기용). 시주 자체는 hour 사용 여부로 따로 처리."""
    h = hour if hour is not None else 12
    m = minute if minute is not None else 0
    return datetime(solar.year, solar.month, solar.day, h, m)


def _ipchun(year: int) -> datetime:
    """y년의 입춘 평균 시각 (KST)."""
    return datetime(year, 2, 4, 12, 0)


def _year_pillar_indices(birth_dt: datetime) -> tuple[int, int, bool]:
    """연주의 (stem_idx, branch_idx, pre_ipchun) 반환. 입춘 전이면 전년도."""
    year = birth_dt.year
    pre_ipchun = birth_dt < _ipchun(year)
    effective_year = year - 1 if pre_ipchun else year
    # 1984년이 갑자년(60갑자 인덱스 0)
    idx = (effective_year - 1984) % 60
    return idx % 10, idx % 12, pre_ipchun


def _month_branch(birth_dt: datetime) -> str:
    """절기 구간으로 월지 결정."""
    y = birth_dt.year
    # 그 해의 12개 절기 시각을 구성. 단 "소한"은 1월에 있고 의미상 작년의 마지막 월(축)을 시작.
    # 알고리즘: birth_dt가 어느 절기 구간(절기 i ~ 절기 i+1)에 속하는지 찾는다.
    # 12개 절기를 연대순으로 나열 (소한 → 입춘 → 경칩 → ... → 대설), 그리고 다음 해 소한까지.
    nodes = []
    # 작년 소한
    nodes.append((datetime(y - 1, 1, 6, 12, 0), "축"))
    # 작년 입춘 ~ 대설
    nodes.append((datetime(y - 1, 2, 4, 12, 0), "인"))
    nodes.append((datetime(y - 1, 3, 6, 12, 0), "묘"))
    nodes.append((datetime(y - 1, 4, 5, 12, 0), "진"))
    nodes.append((datetime(y - 1, 5, 6, 12, 0), "사"))
    nodes.append((datetime(y - 1, 6, 6, 12, 0), "오"))
    nodes.append((datetime(y - 1, 7, 7, 12, 0), "미"))
    nodes.append((datetime(y - 1, 8, 8, 12, 0), "신"))
    nodes.append((datetime(y - 1, 9, 8, 12, 0), "유"))
    nodes.append((datetime(y - 1, 10, 8, 12, 0), "술"))
    nodes.append((datetime(y - 1, 11, 7, 12, 0), "해"))
    nodes.append((datetime(y - 1, 12, 7, 12, 0), "자"))
    # 올해 소한 ~ 대설
    nodes.append((datetime(y, 1, 6, 12, 0), "축"))
    nodes.append((datetime(y, 2, 4, 12, 0), "인"))
    nodes.append((datetime(y, 3, 6, 12, 0), "묘"))
    nodes.append((datetime(y, 4, 5, 12, 0), "진"))
    nodes.append((datetime(y, 5, 6, 12, 0), "사"))
    nodes.append((datetime(y, 6, 6, 12, 0), "오"))
    nodes.append((datetime(y, 7, 7, 12, 0), "미"))
    nodes.append((datetime(y, 8, 8, 12, 0), "신"))
    nodes.append((datetime(y, 9, 8, 12, 0), "유"))
    nodes.append((datetime(y, 10, 8, 12, 0), "술"))
    nodes.append((datetime(y, 11, 7, 12, 0), "해"))
    nodes.append((datetime(y, 12, 7, 12, 0), "자"))
    # 다음 해 소한 (월지 결정에는 불필요하지만 경계용)
    nodes.append((datetime(y + 1, 1, 6, 12, 0), "축"))

    # 가장 마지막으로 지나간 절기 노드의 월지가 현재 월지
    current_branch = nodes[0][1]
    for ts, branch in nodes:
        if birth_dt >= ts:
            current_branch = branch
        else:
            break
    return current_branch


def _month_pillar_indices(year_stem_idx: int, month_branch: str) -> tuple[int, int]:
    branch_idx = EARTHLY_BRANCHES.index(month_branch)
    # 인월(branch_idx=2)에서의 천간 = (year_stem % 5)*2 + 2
    # offset = (branch_idx - 2) % 12
    offset = (branch_idx - 2) % 12
    stem_idx = ((year_stem_idx % 5) * 2 + 2 + offset) % 10
    return stem_idx, branch_idx


def _day_pillar_indices(solar: date) -> tuple[int, int]:
    # 야자시 정책상 시간(hour)은 일주에 영향 없음 — 양력 날짜만으로 결정
    days_from_epoch = (solar - _EPOCH).days
    idx = (_EPOCH_INDEX + days_from_epoch) % 60
    return idx % 10, idx % 12


def _hour_pillar_indices(day_stem_idx: int, hour: int) -> tuple[int, int]:
    # 시지: ((hour + 1) // 2) % 12
    branch_idx = ((hour + 1) // 2) % 12
    # 시간(時干): (day_stem%5)*2 + branch_idx
    stem_idx = ((day_stem_idx % 5) * 2 + branch_idx) % 10
    return stem_idx, branch_idx


def _ten_god(day_stem: str, other_stem: str) -> str:
    """일간 기준 다른 천간의 십신."""
    day_elem = STEM_ELEMENT[day_stem]
    other_elem = STEM_ELEMENT[other_stem]
    same_yy = STEM_YIN_YANG[day_stem] == STEM_YIN_YANG[other_stem]

    # 오행 순환
    generates = {"목": "화", "화": "토", "토": "금", "금": "수", "수": "목"}
    overcomes = {"목": "토", "토": "수", "수": "화", "화": "금", "금": "목"}

    if day_elem == other_elem:
        return "비견" if same_yy else "겁재"
    if generates[day_elem] == other_elem:
        return "식신" if same_yy else "상관"
    if overcomes[day_elem] == other_elem:
        return "편재" if same_yy else "정재"
    if overcomes[other_elem] == day_elem:
        return "편관" if same_yy else "정관"
    if generates[other_elem] == day_elem:
        return "편인" if same_yy else "정인"
    return "?"  # 도달 불가


def _count_elements(pillars: dict[str, Optional[Pillar]]) -> dict[str, int]:
    counts = {e: 0 for e in ELEMENTS}
    for p in pillars.values():
        if p is None:
            continue
        counts[p.stem_element] += 1
        counts[p.branch_element] += 1
    return counts


def compute_pillars(req: SajuCalcRequest) -> SajuCalcResponse:
    solar = _to_solar(req)
    birth_dt = _birth_datetime(solar, req.birth_hour, req.birth_minute)

    # 연주
    year_stem_idx, year_branch_idx, pre_ipchun = _year_pillar_indices(birth_dt)
    year_pillar = _pillar_from_indices(year_stem_idx, year_branch_idx)

    # 월주
    month_branch = _month_branch(birth_dt)
    month_stem_idx, month_branch_idx = _month_pillar_indices(year_stem_idx, month_branch)
    month_pillar = _pillar_from_indices(month_stem_idx, month_branch_idx)

    # 일주
    day_stem_idx, day_branch_idx = _day_pillar_indices(solar)
    day_pillar = _pillar_from_indices(day_stem_idx, day_branch_idx)

    # 시주
    hour_unknown = req.birth_hour is None
    if hour_unknown:
        hour_pillar: Optional[Pillar] = None
    else:
        hour_stem_idx, hour_branch_idx = _hour_pillar_indices(day_stem_idx, req.birth_hour)
        hour_pillar = _pillar_from_indices(hour_stem_idx, hour_branch_idx)

    pillars = {
        "year": year_pillar,
        "month": month_pillar,
        "day": day_pillar,
        "hour": hour_pillar,
    }

    day_master = day_pillar.stem
    day_master_element = day_pillar.stem_element

    elements = _count_elements(pillars)

    ten_gods = {
        "year_stem": _ten_god(day_master, year_pillar.stem),
        "month_stem": _ten_god(day_master, month_pillar.stem),
    }
    if hour_pillar is not None:
        ten_gods["hour_stem"] = _ten_god(day_master, hour_pillar.stem)

    return SajuCalcResponse(
        pillars=pillars,
        day_master=day_master,
        day_master_element=day_master_element,
        elements=elements,
        ten_gods=ten_gods,
        hour_unknown=hour_unknown,
        normalized={
            "solar_date": solar.isoformat(),
            "pre_ipchun": pre_ipchun,
            "birth_datetime": birth_dt.isoformat(),
            "calendar_input": req.calendar.value,
            "is_leap_month_input": req.is_leap_month,
            "jieqi_method": "average_solar_date_approx",
            "ja_si_policy": "야자시",
        },
    )
