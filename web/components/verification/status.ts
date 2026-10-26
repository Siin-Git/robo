import type {DecisionVerification} from '@/components/portfolio/DecisionVerificationPanel';
import {valuationLabel} from '@/components/portfolio/ValuationStatus';
export type Tone = 'confirmed'|'pending'|'missing'|'attention';
export const finite = (value:unknown):value is number => typeof value==='number' && Number.isFinite(value);
const isoDate = (value:string|null|undefined) => !!value && /^\d{4}-\d{2}-\d{2}$/.test(value);
export function canCompare(actual:DecisionVerification['actual']) {
  return actual.status==='AVAILABLE' && actual.observations>=2 &&
    isoDate(actual.start) && isoDate(actual.end) && actual.start!<actual.end! &&
    [actual.personalized_return,actual.core_return,actual.difference_pp].every(finite) &&
    [actual.personalized_nav?.start,actual.personalized_nav?.end,actual.core_nav?.start,actual.core_nav?.end].every(v=>finite(v)&&v>0);
}
export function originalComplete(data:DecisionVerification) {
  return [data.original.base,data.original.personalized].every(record=>
    finite(record.expected_return) && finite(record.volatility) &&
    Object.values(record.weights).some(v=>finite(v)&&v>0));
}
export function jobStatus(job:DecisionVerification['valuation_job']):{label:string;tone:Tone} {
  if(!job)return {label:'작업 기록 미확보',tone:'missing'};
  if(job.state==='NAV_COMPLETE'&&job.valuation_completed===true)return {label:'최근 평가 완료',tone:'confirmed'};
  if(job.state==='EVALUATION_FAILED'||job.status==='failed')return {label:'평가 실패',tone:'attention'};
  if(job.state==='START_WAIT'&&job.reason_code==='AWAITING_T0')return {label:'당시 시작일 도달 전',tone:'pending'};
  if(job.state==='PARTIAL'||job.state==='NAV_COMPLETE')return {label:'평가 완료 확인 필요',tone:'attention'};
  return {label:valuationLabel(job)||'평가 상태 미확보',tone:job.state==='UNKNOWN'?'missing':'pending'};
}
export const checkpointLabels: Record<string,string> = {
  UPCOMING:'관측 중',DATA_PENDING:'관측 자료 대기',DUE:'재검토 시점',RECORDED:'검토 기록 있음',ENDED:'후속 판단 적용',
};
export const koreaTime=(value:string|number|null|undefined)=> {
  if(value==null||value==='')return '미확보';
  const date=new Date(value);
  return Number.isNaN(date.getTime())?'미확보':new Intl.DateTimeFormat('ko-KR',{
    timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,
  }).format(date);
};

// Use the successful response time, not a moving client clock, to date the evidence.
export function hasTodayJob(job:DecisionVerification['valuation_job'],queriedAt:number) {
  if(!job || !queriedAt || !isoDate(job.scheduled_for)) return false;
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(queriedAt));
  const value=(type:string)=>parts.find(part=>part.type===type)?.value;
  return job.scheduled_for===`${value('year')}-${value('month')}-${value('day')}`;
}
