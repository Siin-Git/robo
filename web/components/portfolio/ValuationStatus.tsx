import {fmtDate} from "@/lib/format";
import type {DecisionVerification} from "./DecisionVerificationPanel";
export type ValuationJob = NonNullable<DecisionVerification["valuation_job"]>;

export function valuationLabel(job?: ValuationJob | null): string {
  if (!job) return "자동 평가 작업 기록 미확보";
  if (job.state === "START_WAIT") {
    if (job.reason_code === "START_NOT_SCHEDULED") return "공동 운용 시작일 미지정";
    if (job.reason_code === "AWAITING_T0") return "지정된 공동 운용 시작일 도달 전";
    return "공동 운용 시작 대기";
  }
  if (job.state === "NAV_COMPLETE") return job.valuation_completed === true ? "정상 NAV 저장 완료" : "정상 NAV 저장 확인 미완료";
  const labels:Record<string,string> = {RUNNING:"평가 작업 진행 중", PARTICIPANTS_NOT_READY:"참가자 준비 부족",
    OPERATION_WAIT:"운용 조건 확인 대기", PRICE_WAIT:"가격 확보 대기 · 평가 미완료",
    EVALUATION_FAILED:"평가 작업 실패", NO_NAV:"저장된 NAV 없음", PARTIAL:"일부 평가 미완료",
    UNKNOWN:"평가 완료 여부 미확인"};
  return labels[job.state ?? ""] ?? ({running:"평가 작업 진행 중", failed:"평가 작업 실패",
    success:"작업 성공 · 평가 완료 여부 미확인", skipped:"작업 건너뜀 · 평가 완료 여부 미확인"}[job.status]);
}

export function ValuationStatus({job}:{job?:ValuationJob|null}) {
  return <div aria-label="최근 자동 평가 결과">
    <p>전체 계좌 평가 작업 · {valuationLabel(job)}</p>
    {job && <p>최근 작업 기준일: {fmtDate(job.scheduled_for)}
      {job.ready != null && job.required != null && <> · 준비 인원: {job.ready}/{job.required}명</>}
      {job.valuated != null && <> · NAV 저장: {job.valuated}개 계좌</>}
    </p>}
    <p>화면은 저장된 결과를 조회합니다. 화면 갱신으로 운용 작업이 실행되지는 않습니다.</p>
  </div>;
}
