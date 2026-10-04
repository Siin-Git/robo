import type {Report, Period} from "@/app/(app)/dashboard/performance-data";

export type LedgerBasis="return"|"excess"|"mdd"|"volatility";
export interface LedgerPeer {
  participant_id:string;display_name:string;rank:number|null;reason:string|null;
  metrics:Report["metrics"];observations:number;observed_start:string|null;observed_end:string|null;
  start:string|null;end:string|null;
  quality?:Report["quality"];
  series:{date:string;personal_index100:number;core_index100:number|null}[];
}
export interface LedgerComparison {
  data_source:"ACCOUNT_LEDGER";data_kind:string;period:Period;basis:LedgerBasis;
  status:string;reason:string|null;start:string|null;end:string|null;dates:string[];
  registered:number;ranked:number;items:LedgerPeer[];
}
export const ledgerReason=(reason:string|null)=>({
  NO_CONFIRMED_DECISION:"포트폴리오 확정 기록 없음",AWAITING_EFFECTIVE_DATE:"목표 효력일 대기",
  NO_VALUATIONS:"평가 기록 없음",ONE_VALUATION:"평가 기록 1건 · 두 번째 평가일 대기",
  INSUFFICIENT_PARTICIPANTS:"평가 기록이 두 날짜 이상인 참여자가 2명 미만입니다.",
  NO_COMMON_PERIOD:"공통 평가일이 두 날짜 미만입니다.",
  CORE_SAME_PERIOD_MISSING:"같은 기간의 CORE 기록 부족",RISK_HISTORY_INSUFFICIENT:"연율 위험 지표 산출 기록 부족",
  INSUFFICIENT_COMPARABLE_METRIC:"이 지표로 비교 가능한 참여자가 2명 미만입니다.",
  NOT_COMPARABLE_COHORT:"현재 참여자 비교 대상에 포함되지 않습니다."
}[reason??""]??reason??"");
