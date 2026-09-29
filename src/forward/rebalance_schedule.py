"""리밸런싱 주기 규칙 (순수 날짜 계산, 의존성 없음).

여기에 모으는 이유:
  - 월간/분기 판정이 run_monthly 안에 묻혀 있으면 테스트할 수 없다.
  - API 의 next_rebalance_date 와 엔진의 실제 실행 시점이 어긋나면
    프론트가 잘못된 날짜를 보여준다. 같은 함수를 쓴다.

효력일 규칙: 결정에 쓴 마지막 날(asof)의 **다음 거래일**이다. 제출 시점보다
미래여야 한다(``execution`` 의 next-available-close 규칙). 과거로 잡으면 나중
데이터로 판단해놓고 이전 종가에 체결하게 된다.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

FREQUENCIES = ("monthly", "quarterly")
QUARTER_END_MONTHS = (3, 6, 9, 12)
_SEARCH_MONTHS = 15  # 분기라도 최대 3개월이면 찾는다. 넉넉히 둔다.


def normalize_frequency(value) -> str:
    freq = str(value or "monthly").strip().lower()
    if freq not in FREQUENCIES:
        raise ValueError(f"unknown rebalance frequency {value!r} "
                         f"(expected one of {FREQUENCIES})")
    return freq


def is_rebalance_period(year: int, month: int, frequency) -> bool:
    """그 달의 말일을 기준으로 리밸런싱을 실행하는 달인가."""
    freq = normalize_frequency(frequency)
    if freq == "monthly":
        return True
    return int(month) in QUARTER_END_MONTHS


def period_asof(year: int, month: int) -> str:
    """해당 월의 마지막 날(결정 기준일)."""
    year, month = int(year), int(month)
    return date(year, month, monthrange(year, month)[1]).isoformat()


def next_trading_weekday(d: date) -> date:
    """다음 평일. 공휴일은 보지 않는다(체결은 실제 종가가 있는 날로 다시 정렬된다)."""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def effective_date(asof: str) -> str:
    """주문 효력일. 결정 기준일의 다음 거래일이며 항상 미래다."""
    return next_trading_weekday(date.fromisoformat(str(asof)[:10])).isoformat()


def next_rebalance_effective(after: date, frequency) -> date | None:
    """``after`` 이후 처음 도래하는 리밸런싱의 효력일.

    API 의 next_rebalance_date 가 이것을 쓴다. 엔진이 실제로 주문을 만드는
    날짜와 같아야 프론트에 표시되는 값이 맞는다.
    """
    freq = normalize_frequency(frequency)
    year, month = after.year, after.month
    for _ in range(_SEARCH_MONTHS):
        end = date(year, month, monthrange(year, month)[1])
        if end >= after and is_rebalance_period(year, month, freq):
            return next_trading_weekday(end)
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return None


def skip_reason(year: int, month: int, frequency) -> str:
    """리밸런싱을 건너뛸 때 로그에 남길 설명."""
    freq = normalize_frequency(frequency)
    return (f"{int(year)}-{int(month):02d} is not a rebalance period "
            f"(frequency={freq}, quarter ends: "
            f"{', '.join(str(x) for x in QUARTER_END_MONTHS)})")
