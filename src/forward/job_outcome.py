"""Interpret recorded daily evidence; never equate process success with NAV."""


def incomplete_daily(stats):
    """Explicit incomplete legacy success may retry; unknown legacy stays locked."""
    return (stats.get("status") in {"COMPETITION_WAIT", "PARTIAL", "FAIL"}
            or stats.get("outcome") in {"PARTIAL", "FAILED"}
            or stats.get("retryable") is True
            or stats.get("valuated") == 0)


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def daily_outcome(status, stats):
    """Allowlisted public fields only: raw diagnostics/account IDs stay private."""
    reason = stats.get("reason")
    valuated = count(stats.get("valuated"))
    results = stats.get("account_results") or {}
    # Historical valuated counted attempted NAVs, including NAV_INCOMPLETE.
    if results:
        valuated = sum(r.get("status") in {"OK", "STALE_PRICE"} for r in results.values())
    if status == "running":
        state, message = "RUNNING", "평가 작업 진행 중"
    elif status == "failed" or stats.get("status") == "FAIL" or stats.get("outcome") == "FAILED":
        state, message = "EVALUATION_FAILED", "평가 작업 실패 · 재시도 필요"
    elif stats.get("status") == "COMPETITION_WAIT":
        if reason == "PARTICIPANTS_NOT_READY":
            state, message = "PARTICIPANTS_NOT_READY", "참가자 준비 부족"
        elif reason in {"START_NOT_SCHEDULED", "AWAITING_T0"}:
            state = "START_WAIT"
            message = "공동 운용 시작일 미지정" if reason == "START_NOT_SCHEDULED" else "지정된 공동 운용 시작일 도달 전"
        else:
            state, message = "OPERATION_WAIT", "운용 조건 확인 대기"
    elif stats.get("price_wait_accounts") or any(
            r.get("status") == "STALE_PRICE" or r.get("reason") in {
                "no executions yet", "competition not started for this valuation", "no stored investable prices"}
            for r in results.values()):
        state, message = "PRICE_WAIT", "가격 확보 대기 · 평가 미완료"
    elif incomplete_daily(stats):
        state, message = ("NO_NAV", "저장된 NAV 없음") if valuated == 0 else ("PARTIAL", "일부 평가 미완료")
    elif status == "success" and stats.get("status") == "PASS" and valuated and stats.get("outcome") in {None, "SUCCESS"}:
        state, message = "NAV_COMPLETE", "정상 NAV 저장 완료"
    else:
        state, message = "UNKNOWN", "작업 기록만으로 평가 완료를 확인할 수 없습니다."
    return {"state": state, "message": message,
            "reason_code": reason if reason in {"START_NOT_SCHEDULED", "AWAITING_T0", "PARTICIPANTS_NOT_READY"} else None,
            "execution_succeeded": status == "success",
            "valuation_completed": state == "NAV_COMPLETE",
            "valuated": valuated,
            "ready": count(stats.get("ready")), "required": count(stats.get("required")),
            "retryable": status == "failed" or incomplete_daily(stats)}
