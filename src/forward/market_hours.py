"""장이 열려 있는지 판정한다 (순수 시간 계산, 의존성 없음).

왜 필요한가
-----------
야후는 장이 열려 있는 동안에도 그날 바를 돌려준다. 그 값이 저장되면
``refresh_live`` 의 증분 규칙(시작점 = 마지막 보유일 + 1일) 때문에 같은 날짜를
다시 받아오지 않는다. **잠정가가 종가로 굳고 스스로 고쳐지지 않는다.**

2026-09-29 에 실제로 발생했다. 22:36 에 배치를 수동 실행했고 미국 장이 22:30 에
열린 뒤라 미국 자산 16개의 그날 "종가"가 장 시작 6분 뒤 가격으로 기록됐다.

여기서는 가격을 걸러내지 않고 **실행 자체를 막는다.** 수집 로직을 건드리지
않으므로 실패해도 최악이 "돌아야 할 때 안 도는 것"이고, 그건 바로 눈에 띈다.

시간대
------
KST 고정 오프셋(UTC+9)을 쓴다. 한국은 서머타임이 없고, Windows 파이썬은
tzdata 패키지 없이는 ZoneInfo("Asia/Seoul") 가 실패한다.

미국 구간은 서머타임 양쪽을 덮도록 넓게 잡았다(EDT 22:30~05:00,
EST 23:30~06:00 → 22:30~06:00). 조금 넓게 막는 쪽이 안전하다.

공휴일은 보지 않는다. 휴장일에도 막히지만 그 경우 --force 로 넘길 수 있고,
잘못 저장하는 것보다 낫다.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")

KR_OPEN, KR_CLOSE = time(9, 0), time(15, 30)
US_OPEN, US_CLOSE = time(22, 30), time(6, 0)   # KST 기준, 자정을 넘는다


def now_kst() -> datetime:
    return datetime.now(KST)


def _kr_open(ts: datetime) -> bool:
    if ts.weekday() >= 5:                      # 토·일
        return False
    return KR_OPEN <= ts.time() < KR_CLOSE


def _us_open(ts: datetime) -> bool:
    t, wd = ts.time(), ts.weekday()
    if t >= US_OPEN:                           # 당일 밤에 시작한 세션
        return wd <= 4                         # 월~금 밤
    if t < US_CLOSE:                           # 전날 밤에 시작해 새벽까지
        return 1 <= wd <= 5                    # 화~토 새벽
    return False


def open_markets(ts: datetime | None = None) -> list[str]:
    """지금 열려 있는 시장. 비어 있으면 수집해도 안전하다."""
    ts = ts or now_kst()
    if ts.tzinfo is not None:
        ts = ts.astimezone(KST)
    out = []
    if _kr_open(ts):
        out.append("KR")
    if _us_open(ts):
        out.append("US")
    return out


def next_safe(ts: datetime | None = None) -> datetime:
    """다음으로 수집이 안전해지는 시각(분 단위 탐색)."""
    ts = (ts or now_kst())
    if ts.tzinfo is not None:
        ts = ts.astimezone(KST)
    probe = ts.replace(second=0, microsecond=0)
    for _ in range(24 * 60 + 1):
        if not open_markets(probe):
            return probe
        probe += timedelta(minutes=1)
    return probe


def guard_message(ts: datetime | None = None) -> str | None:
    """열린 시장이 있으면 설명 문구, 없으면 None."""
    ts = ts or now_kst()
    markets = open_markets(ts)
    if not markets:
        return None
    names = {"KR": "한국(09:00~15:30)", "US": "미국(22:30~06:00)"}
    which = ", ".join(names[m] for m in markets)
    safe = next_safe(ts)
    return (f"지금은 장중이다: {which} KST.\n"
            f"장중 가격이 종가로 저장되면 증분 수집 규칙상 다시 받아오지 않는다"
            f"(2026-09-29 에 실제로 발생).\n"
            f"{safe.strftime('%H:%M')} KST 이후에 실행하거나, 그래도 진행하려면 "
            f"--force 를 붙일 것.")
