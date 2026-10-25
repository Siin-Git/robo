"use client";
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import {useQuery} from '@tanstack/react-query';
import {AppShell} from '@/components/layout/AppShell';
import {getDecisions,getReview,getChoices} from '@/lib/api/decisions';
import {fmtPct,fmtDate} from '@/lib/format';
import {assetName} from '@/app/(app)/dashboard/performance-data';
import {ExpectationComparison} from '@/components/performance/ExpectationComparison';
import s from '@/app/(app)/dashboard/dashboard.module.css';
import {DecisionReviewAction} from '@/components/portfolio/DecisionReviewAction';
import {RehearsalReviewContext} from '@/components/portfolio/RehearsalReviewContext';
import {readRehearsalContext,rehearsalHref} from '@/lib/rehearsal-context';
import flow from '@/components/portfolio/review-flow.module.css';
const labels:Record<string,string>={expected_return:'예상 수익률',volatility:'예상 변동성',tracking_error:'예상 추적오차'};
export default function ReviewPage(){
  return <Suspense fallback={<p>판단 기록 조회 중</p>}><ReviewContent/></Suspense>;
}
function ReviewContent(){
  const ds=useQuery({queryKey:['decisions'],queryFn:getDecisions});
  const cs=useQuery({queryKey:['portfolio-choices'],queryFn:getChoices});
  const [selected,setSelected]=useState<string|null>(null);
  const params=useSearchParams();
  const id=selected??params.get('decision_id')??ds.data?.items[0]?.decision_id;
  const q=useQuery({queryKey:['decision-review',id],queryFn:()=>getReview(id!),enabled:!!id});
  const d=q.data?.decision,actual=q.data?.actual;
  const isLatest=d?.decision_id===ds.data?.items[0]?.decision_id;
  const fromRehearsal=params.get('source')==='rehearsal'&&id===params.get('decision_id');
  const context=readRehearsalContext(params);
  const returnHref=fromRehearsal&&id?rehearsalHref(id,context):undefined;
  return <AppShell headerTitle={fromRehearsal?"내 선택 다시 살펴보기":"최초 예상·실제 검토"} softBackground><div className={`${s.page} review-workspace`}><header className={s.header}><div><h1>{fromRehearsal?"내 선택 다시 살펴보기":"최초 예상·실제 검토"}</h1><p>확정 당시 판단을 보존하고 관측 결과를 검토합니다. 조회만으로 구성이나 주문이 변경되지 않습니다.</p></div><div className="ui-actions">{returnHref?<Link href={returnHref}>← 같은 조건의 리허설로 돌아가기</Link>:<>{id&&<Link href={`/portfolio?decision_id=${encodeURIComponent(id)}&inspect=personalized`}>이 판단의 검증으로 돌아가기</Link>}<Link href="/dashboard">운용 성과로 돌아가기</Link></>}</div></header>
    {ds.isError&&<p role="alert">판단 기록 조회 실패 <button onClick={()=>ds.refetch()}>다시 조회</button></p>}
    {ds.isLoading?<p>판단 기록 조회 중</p>:!ds.data?.items.length?<section className={s.empty}><h2>최초 예상 기록이 없습니다</h2><p>과거에 저장하지 않은 예상값을 현재 모형으로 채우지 않습니다. 이후 새 확정부터 판단 버전이 저장됩니다.</p><Link href="/setup/portfolio">새 판단 설계</Link></section>:<>
    <label>판단 버전 <select className="input" style={{maxWidth:"100%"}} aria-label="판단 버전" value={id} onChange={e=>setSelected(e.target.value)}>{ds.data.items.map(x=><option key={x.decision_id} value={x.decision_id}>v{x.version} · {new Date(x.confirmed_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} KST</option>)}</select></label>
    {q.isError?<p role="alert">검토 결과 조회 실패 <button onClick={()=>q.refetch()}>다시 조회</button></p>:!d?<p>검토 결과 조회 중</p>:<>
    {actual?.data_kind === "TEST_FIXTURE" && <p className={`${s.exampleBanner} ${s.fixtureBanner}`} role="status">검증용 합성 데이터 · 실제 운용 기록이 아닙니다. 아래 관측 값은 기능 검증용입니다.</p>}
    {fromRehearsal&&<p className={flow.status}>{actual?.data_kind==="TEST_FIXTURE"?"검증용 관측 자료 · 실제 운용 성과가 아닙니다.":(actual?.observations??0)<2?`실제 운용 관측 ${actual?.observations??0}개 · 성과 검증 진행 중. 아래 리허설은 실제 운용 성과와 구분됩니다.`:'실제 운용 관측과 과거 가정 계산은 별도 자료입니다. 상세 관측과 비교 조건은 아래에서 확인할 수 있습니다.'}</p>}
    <div className={fromRehearsal?flow.flow:undefined}>
      {fromRehearsal&&<RehearsalReviewContext decisionId={d.decision_id} context={context}/>}
      {isLatest?<DecisionReviewAction key={d.decision_id} decision={d} returnHref={returnHref}/>:<p className={flow.status}>이전 판단은 조회만 가능합니다. 검토 이유를 저장하려면 최신 판단을 선택해 주세요.</p>}
    </div>
    <details className={flow.evidence} open={!fromRehearsal} key={`${id}:${fromRehearsal}`}><summary>확정 당시 예상과 실제 관측 근거 확인</summary>
    <section className={s.operations}><h2>확정 당시 판단 · v{d.version}</h2>
      <dl className={s.operationGrid}><div><dt>최초 확정 시각</dt><dd>{new Date(d.confirmed_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} KST</dd></div><div><dt>목표 효력일</dt><dd>{fmtDate(d.target_effective_date)}</dd></div><div><dt>효력 이후 첫 체결일</dt><dd>{q.data?.first_execution_date??'체결 대기 / 후속 체결 없음'}</dd></div><div><dt>마지막 평가일</dt><dd>{q.data?.valuation_date??'평가 대기'}</dd></div></dl>
      <p>관측 구간 {q.data?.observation_start??'없음'} — {q.data?.observation_end??'없음'} · 평가일 {actual?.observations??0}개</p><p>확정 이유: {d.reason||'미입력'}</p>
      <div className="review-estimates">{Object.entries(d.expectations).map(([key,m])=><div key={key}><span>{labels[key]??key} · 연율</span><strong>{m.value==null?'자료 부족':fmtPct(m.value)}</strong></div>)}</div>
      <details><summary>최초 예상 지표의 산출 기준</summary>      <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>최초 예상</th><th>값 · 연율</th><th>기간·단위</th><th>산출 기준</th></tr></thead><tbody>{Object.entries(d.expectations).map(([key,m])=><tr key={key}><th>{labels[key]??key}</th><td>{m.value==null?'자료 부족':fmtPct(m.value)}</td><td>{m.horizon === "1Y" ? "1년" : m.horizon} · {m.unit === "fraction_per_year" ? "비율 · 연율" : m.unit}</td><td>{m.basis} · {m.sampling}</td></tr>)}</tbody></table></div></details>
      <details><summary>모형·데이터 버전</summary><p>판단 ID {d.decision_id} · 이전 판단 {d.previous_decision_id??'없음'}</p><p>{d.provenance.risk_model_version} · 위험 데이터 기준일 {d.provenance.price_data_as_of??'미기록'}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(d.provenance.artifact_sha256,null,2)}</pre></details>
    </section>
    <section className={s.operations}><h2>관측 결과와 검토 근거</h2><p>확정 당시 저장된 기준과 실제 관측의 기간·단위·통화·비용·배당·산출 주기·기준 포트폴리오가 일치할 때만 실제 − 예상 차이를 계산합니다. 연간 예상과 단기 누적수익률을 빼거나 미기록 예상값을 복원하지 않습니다.</p><p>관측 누적수익률 {fmtPct(actual?.metrics.cumulative_return)} · 실현 변동성 · 연율 {fmtPct(actual?.metrics.volatility)}</p>
      {actual?.status==='INSUFFICIENT_HISTORY'&&<p>기록 부족: 두 평가일 이상 기록되어야 누적 성과를 표시합니다. 연율 통계는 별도의 충분한 관측과 품질 조건이 필요합니다.</p>}
      <ExpectationComparison items={q.data?.comparisons??[]}/>
      <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>자산</th><th>확정 비중</th><th>최신 평가 비중</th><th>차이 · %p</th></tr></thead><tbody>{q.data?.weight_changes.map(delta=><tr key={delta.asset_id}><th>{assetName(delta.asset_id)}</th><td>{fmtPct(delta.confirmed_weight)}</td><td>{fmtPct(delta.current_weight)}</td><td>{delta.difference==null?'평가 부족':`${(delta.difference*100).toFixed(2)}%p`}</td></tr>)}</tbody></table></div>
      <p>비중 차이는 최신 보유 평가와 선택한 판단을 비교합니다. 수익 기여도와 누적 수익률의 차이가 아닙니다.</p>
      {q.data?.horizons.map(h=><p key={h.months}>{h.months}개월 추적 · 관측 시작 기준 도달 예정일 {h.due_date} · {h.status==='NOT_REACHED'?'기간 미도달':`관측 결과 ${fmtPct(h.cumulative_return)}`}</p>)}
    </section>
    </details>
    </>}
    <section className={s.operations}><h2>이 판단의 검토 기록</h2>{cs.isError?<p role="alert">선택 기록 조회 실패 <button onClick={()=>cs.refetch()}>다시 조회</button></p>:cs.data?.items.some(c=>c.decision_id===id)?<ul>{cs.data.items.filter(c=>c.decision_id===id).map(c=><li key={c.choice_id}>{c.action==='KEEP'?'유지':'조정 검토'} · {c.selected_at} · {c.reason} · 판단 {c.decision_id}</li>)}</ul>:<p>저장된 선택이 없습니다.</p>}</section>
    </>}
  </div></AppShell>;
}
