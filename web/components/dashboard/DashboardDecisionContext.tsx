import Link from 'next/link';
import type { DecisionContext } from '@/app/(app)/dashboard/performance-data';
import { fmtDate } from '@/lib/format';
import s from '@/app/(app)/dashboard/dashboard.module.css';

export function DashboardDecisionContext({context,observations,start,end}:{
  context:DecisionContext;observations:number;start:string|null;end:string|null;
}){
  const {active_decision:active,pending_decision:pending,previous_decision:previous}=context;
  if(context.status==='LEGACY_UNRECORDED')return null;
  return <section className={s.operations} aria-label="성과 적용 판단"><h2>현재 운용 판단과 적용 대기</h2>
    <p>효력일 판단 기준 {fmtDate(context.as_of)} KST · 실제 체결·평가 여부는 운용 기록에서 확인합니다.</p>
    <p>현재 운용 판단: {active?`v${active.version} · 효력일 ${fmtDate(active.target_effective_date)}`:'없음 · 첫 목표 효력일 대기'}</p>
    {pending&&<p>적용 대기 판단: v{pending.version} · 효력일 {fmtDate(pending.target_effective_date)}. {active?'대기 중에는 현재 판단의 성과·기여도·선택 기본 구성을 함께 조회합니다.':'효력일 이후 체결·평가 기록이 쌓이면 성과를 표시합니다.'} <Link href={`/review?decision_id=${encodeURIComponent(pending.decision_id)}`}>대기 판단 상세 보기</Link></p>}
    {active&&<p>성과·기여도·기본 구성 비교 기준: v{active.version} · 실제 관측 {start??'기록 대기'} — {end??'기록 대기'} · 평가일 {observations}개</p>}
    {active&&observations<2&&<p>현재 판단의 평가 기록이 부족합니다. 이전 판단의 수익률을 새 판단의 성과로 표시하지 않습니다.</p>}
    {previous&&<Link href={`/review?decision_id=${encodeURIComponent(previous.decision_id)}`}>이전 판단 v{previous.version} 성과 상세 보기</Link>}
  </section>;
}
