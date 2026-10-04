"use client";
import {Suspense,useState} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import {useQuery} from '@tanstack/react-query';
import {Line,LineChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import {AppShell} from '@/components/layout/AppShell';
import {getStrategies,getStrategy} from '@/lib/api/strategies';
import {fmtPct} from '@/lib/format';
import s from '@/app/(app)/dashboard/dashboard.module.css';

export default function StrategyPage(){return <Suspense fallback={<p>전략 자료 조회 중</p>}><Content/></Suspense>;}
function Content(){
  const params=useSearchParams(),catalog=useQuery({queryKey:['strategy-research'],queryFn:getStrategies});
  const initial=params.get('strategy')??'';
  const [selection,setSelection]=useState({strategy:initial,variant:''});
  const q=useQuery({queryKey:['strategy-detail',selection.strategy,selection.variant],queryFn:()=>getStrategy(selection.strategy,selection.variant),enabled:!!selection.strategy});
  const d=q.data;
  const points=d?.report?.series.map(p=>({date:p.date,index100:(1+p.personal)*100}));
  return <AppShell headerTitle="전략 자료 검토" softBackground><main className={s.page}>
    <header className={s.header}><div><h1>주도주·수출 전략 자료 검토</h1><p>제공된 과거 모델 백테스트입니다. ETF 종가·사용자 확정 이후 실제 운용 실적으로 사용하지 않습니다.</p></div><Link href="/setup/portfolio?step=themes">투자 선택으로 돌아가기</Link></header>
    {catalog.isError&&<p role="alert">전략 목록 조회 실패 <button onClick={()=>catalog.refetch()}>다시 조회</button></p>}
    <label>전략 <select aria-label="전략 자료 선택" value={selection.strategy} onChange={e=>setSelection({strategy:e.target.value,variant:''})}><option value="">전략 선택</option>{catalog.data?.items.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
    {q.isError&&<p role="alert">전략 상세 조회 실패 <button onClick={()=>q.refetch()}>다시 조회</button></p>}
    {q.isLoading&&<p role="status">전략 상세 조회 중</p>}
    {d&&<>
      <section className={s.operations}><h2>{d.label} · 운용 준비 전</h2><p>{d.selection_rule}</p><p>{d.rebalance_rule}</p><p>통화 {d.currency} · {d.cost_basis}</p><p>{d.dividend_basis}</p>
        <label>전략 변형 <select style={{maxWidth:'100%'}} aria-label="전략 변형 선택" value={selection.variant} onChange={e=>setSelection({...selection,variant:e.target.value})}><option value="">변형을 직접 선택하세요</option>{d.variants.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select></label>
        <ul>{d.variants.map(v=><li key={v.id}>{v.label}: {v.signal_execution} · {v.frequency==='MONTHLY'?'월별 자료':'일별 모델 지수'}</li>)}</ul>
      </section>
      {d.report&&<section className={s.operations}><h2>선택한 과거 모델의 성과</h2><p>자료 표기 구간 {d.report.source_period?.start??d.report.start} — {d.report.source_period?.end??d.report.end} · 관측 {d.report.observations}개</p>
        <p>{d.report.warning}</p><p>첫 표시 지수=100 · 표시된 양 끝 값 기준 누적수익률 {fmtPct(d.report.metrics.cumulative_return)} · 관측 최대낙폭 {fmtPct(d.report.metrics.mdd)}</p>
        <div style={{height:280}} role="img" aria-label="과거 모델 지수, 실제 계좌 운용 아님"><ResponsiveContainer width="100%" height="100%"><LineChart data={points}><XAxis dataKey="date" minTickGap={80}/><YAxis width={65}/><Tooltip/><Line dataKey="index100" name="모델 지수" type="linear" stroke="#3268df" dot={false} connectNulls={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
        <p>자료 원문 전체 기간 CAGR {fmtPct(d.source_summary?.cagr)} · MDD {fmtPct(d.source_summary?.mdd)}. 과거 통계이며 기대수익률 전망이 아닙니다. 월별 관측 MDD는 자료의 일별 MDD와 다를 수 있습니다.</p>
      </section>}
      <section className={s.operations}><h2>제공 자료의 구성 종목</h2><p>{d.snapshot.as_of?`측정 기준일 ${d.snapshot.as_of} · 최신 목표안`: `과거 신호월 ${d.snapshot.signal_month} · 리밸런싱 ${d.snapshot.rebalance_date} · 체결창 종료 스냅샷 ${d.snapshot.snapshot_date}`}</p>
        <p>이 스냅샷은 선택한 모든 변형의 공통 편입안이 아닙니다. 사용자 계좌에 적용하지 않습니다.</p>
        <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>종목</th><th>코드</th><th>목표 비중</th><th>과거 체결창 종료 비중</th></tr></thead><tbody>{d.snapshot.members.map(m=><tr key={m.ticker}><th>{m.company}</th><td>{m.ticker}</td><td>{fmtPct(m.weight??m.target_weight)}</td><td>{fmtPct(m.actual_weight)}</td></tr>)}</tbody></table></div>
      </section>
      <section className={s.operations}><h2>운용 연결에 필요한 자료·결정</h2><ul>{d.blockers.map(x=><li key={x}>{x}</li>)}</ul><p>자료 버전 {d.version}. 월별 자료를 일별 가격으로 늘리지 않으며, 과거 모델 성과를 실제 원장에 쓰지 않습니다.</p></section>
    </>}
  </main></AppShell>;
}
