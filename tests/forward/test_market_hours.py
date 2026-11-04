"""장중 수집 차단.

2026-09-29 22:36 에 수동 실행한 배치가 미국 개장 6분 뒤 가격을 그날 종가로
저장했다. 증분 수집 규칙상 같은 날짜를 다시 받아오지 않아 스스로 고쳐지지
않는다. 가격을 받은 뒤 거르는 대신 실행 자체를 막는다.
"""
from datetime import datetime, timedelta

import pytest

from src.forward.market_hours import (KST, guard_message, next_safe, now_kst,
                                      open_markets)


def at(text: str) -> datetime:
    """'2026-09-29 22:36' -> KST datetime."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


# --------------------------------------------------------------------------
# 한국 (09:00~15:30, 평일)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("when, expected", [
    ("2026-09-30 08:59", False),   # 개장 직전
    ("2026-09-30 09:00", True),    # 개장
    ("2026-09-30 12:00", True),
    ("2026-09-30 15:29", True),
    ("2026-09-30 15:30", False),   # 마감
    ("2026-09-30 16:00", False),
])
def test_한국_장중_판정(when, expected):
    assert ("KR" in open_markets(at(when))) is expected


def test_주말에는_한국_장이_없다():
    for when in ("2026-10-03 12:00", "2026-10-04 12:00"):   # 토, 일
        assert "KR" not in open_markets(at(when))


# --------------------------------------------------------------------------
# 미국 (22:30~06:00 KST, 서머타임 양쪽을 덮는다)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("when, expected", [
    ("2026-09-29 22:29", False),   # 개장 직전
    ("2026-09-29 22:30", True),    # 개장
    ("2026-09-29 22:36", True),    # ** 실제 사고 시각 **
    ("2026-09-30 02:00", True),    # 자정을 넘어 계속
    ("2026-09-30 05:59", True),
    ("2026-09-30 06:00", False),   # 마감(EST 기준까지 덮음)
    ("2026-09-30 07:10", False),   # 자동 실행 시각
    ("2026-09-30 17:10", False),   # 자동 실행 시각
])
def test_미국_장중_판정(when, expected):
    assert ("US" in open_markets(at(when))) is expected


def test_금요일_밤_세션은_토요일_새벽까지다():
    assert "US" in open_markets(at("2026-10-02 23:00"))   # 금 밤
    assert "US" in open_markets(at("2026-10-03 03:00"))   # 토 새벽
    assert "US" not in open_markets(at("2026-10-03 23:00"))  # 토 밤은 세션 없음


def test_일요일_밤은_세션이_아니다():
    assert "US" not in open_markets(at("2026-10-04 23:00"))
    assert "US" not in open_markets(at("2026-10-05 03:00"))   # 월 새벽


# --------------------------------------------------------------------------
# 자동 실행 시각은 항상 안전해야 한다
# --------------------------------------------------------------------------

@pytest.mark.parametrize("day", ["2026-09-28", "2026-09-29", "2026-09-30",
                                 "2026-10-01", "2026-10-02"])
@pytest.mark.parametrize("hhmm", ["07:10", "17:10"])
def test_스케줄러_시각은_평일_내내_안전하다(day, hhmm):
    assert open_markets(at(f"{day} {hhmm}")) == []


def test_안전_구간_두_개():
    """06:00~09:00 과 15:30~22:30 이 비어 있어야 한다."""
    for when in ("2026-09-30 06:00", "2026-09-30 08:30",
                 "2026-09-30 15:30", "2026-09-30 20:00", "2026-09-30 22:29"):
        assert open_markets(at(when)) == [], when


def test_두_시장이_겹치는_시간은_없다():
    """한국 09:00~15:30 과 미국 22:30~06:00 은 만나지 않는다."""
    t = at("2026-09-30 00:00")
    for _ in range(24 * 60):
        assert len(open_markets(t)) <= 1, t
        t += timedelta(minutes=1)


# --------------------------------------------------------------------------
# 안내 문구
# --------------------------------------------------------------------------

def test_안전하면_문구가_없다():
    assert guard_message(at("2026-09-30 07:10")) is None


def test_장중이면_다음_안전_시각을_알려준다():
    msg = guard_message(at("2026-09-29 22:36"))
    assert msg is not None
    assert "--force" in msg
    assert "06:00" in msg


def test_next_safe_는_항상_안전한_시각이다():
    for when in ("2026-09-29 22:36", "2026-09-30 10:00", "2026-09-30 07:10"):
        assert open_markets(next_safe(at(when))) == []


def test_now_kst_는_시간대를_붙인다():
    assert now_kst().tzinfo is not None


def test_tzdata_없이_동작한다():
    """Windows 파이썬은 tzdata 없이 ZoneInfo('Asia/Seoul') 가 실패한다.

    고정 오프셋을 쓰므로 이 테스트는 어느 환경에서나 통과해야 한다.
    """
    assert KST.utcoffset(None) == timedelta(hours=9)


# --------------------------------------------------------------------------
# run_daily 연결
# --------------------------------------------------------------------------

def test_run_daily에_force_옵션이_있다():
    """가드를 넘길 수단이 없으면 휴장일에 손발이 묶인다."""
    import re
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "src" / "forward"
            / "run_daily.py").read_text(encoding="utf-8")
    assert '"--force"' in text
    assert re.search(r"guard_message", text), "run_daily 가 가드를 부르지 않는다"


def test_dry_run은_가드를_통과한다():
    """dry-run 은 가격을 받지 않으므로 언제든 허용해야 한다."""
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "src" / "forward"
            / "run_daily.py").read_text(encoding="utf-8")
    assert "not args.dry_run" in text, "dry-run 까지 막으면 미리보기를 못 한다"
