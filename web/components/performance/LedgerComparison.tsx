"use client";
import {useState} from "react";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {AppShell} from "@/components/layout/AppShell";
import {ErrorState,LoadingSkeleton} from "@/components/shared/ui";
import {PerformanceChart,CORE_LINE,MY_LINE} from "@/components/dashboard/PerformanceChart";
import {get} from "@/lib/api/client";
import {fmtDate,fmtReturn,fmtPct,fmtActivePp} from "@/lib/format";
import {DEMO_MODE} from "@/lib/api/comparison";
import {LedgerComparison as Contract,LedgerBasis,ledgerReason} from "@/lib/api/ledger-comparison";
import {PERIODS,Period} from "@/app/(app)/dashboard/performance-data";

export function LedgerComparison({participantId}:{participantId?:string}) {
  const [period,setPeriod]=useState<Period>("ALL");
  const [basis,setBasis]=useState<LedgerBasis>("return");
  const [selected,setSelected]=useState<string|null>(participantId??null);
  const me=useQuery({queryKey:["comparison-identity"],queryFn:()=>get<{participant_id:string}>("/api/v1/me")});
  const q=useQuery({queryKey:["ledger-comparison",period,basis],queryFn:()=>get<Contract>(`/api/v1/me/performance/comparison?period=${period}&basis=${basis}`),refetchInterval:15_000});
  const data=q.data;
  const focus=selected??me.data?.participant_id;
  const person=data?.items.find(p=>p.participant_id===focus);
  const peers=data?.items.filter(p=>p.series.length>1)??[];
  const points=(data?.dates??[]).map(date=>({date,core:person?.series.find(p=>p.date===date)?.core_index100??null,
    ...Object.fromEntries(peers.map(peer=>[peer.participant_id,peer.series.find(p=>p.date===date)?.personal_index100??null]))}));
  return <AppShell headerTitle="참여자 운용 성과 비교" softBackground><div className="ranking-page">
    <h1>참여자 운용 성과 비교</h1><p>{data?.data_kind==="HISTORICAL_REPLAY"?"현재 확정 구성의 과거 가격 모의실험 원장":"확정 이후의 실제 시장 가격 모의운용 원장"} · 입출금 없는 계좌의 기록된 NAV 변화</p>
    <div className="ui-actions"><Link className="btn-secondary" href="/dashboard">내 운용 성과</Link><Link className="btn-secondary" href={`/dashboard?comparison=common&period=${period}`}>공통 기간의 내 성과·기여도</Link>{DEMO_MODE&&<Link className="btn-secondary" href="/ranking?source=demo">과거 가격 비교·시연 보기</Link>}</div>
    <div className="ranking-toolbar"><label>조회 기간<select aria-label="조회 기간" className="input" value={period} onChange={e=>setPeriod(e.target.value as Period)}>{PERIODS.map(p=><option key={p.key} value={p.key}>{p.label}</option>)}</select></label><label>순위 기준<select aria-label="순위 기준" className="input" value={basis} onChange={e=>setBasis(e.target.value as LedgerBasis)}><option value="return">누적수익률</option><option value="excess">CORE 대비 차이</option><option value="mdd">최대 낙폭</option><option value="volatility">연율 변동성</option></select></label></div>
    {q.isLoading?<LoadingSkeleton rows={5}/>:q.isError?<ErrorState message="운용 원장 비교를 불러오지 못했습니다." onRetry={()=>q.refetch()}/>:data&&<>
      {data.data_kind==="TEST_FIXTURE"&&<p className="ui-note" role="status">검증용 합성 데이터 · 실제 운용 기록이 아닙니다.</p>}
      <p className="ui-note">공통 관측 {fmtDate(data.start)} — {fmtDate(data.end)} · 표시 날짜 {data.dates.length}개 · 순위 산출 {data.ranked}명 / 등록 {data.registered}명. 시작·종료일을 맞추고 각 참여자의 구간 내부 실제 평가를 모두 사용합니다. 누락 날짜는 연결하지 않습니다.</p>
      {data.reason&&<p role="status">순위 대기 · {ledgerReason(data.reason)}</p>}
      <section aria-label="운용 기록 참여자 순위" className="ui-panel"><p className="caption">좁은 화면에서는 표를 좌우로 이동해 지표와 기간을 확인하세요.</p><div style={{overflowX:"auto"}} tabIndex={0} aria-label="좌우로 이동 가능한 참여자 순위 표"><table className="table" style={{minWidth:960,whiteSpace:"nowrap"}}><thead><tr><th>순위</th><th>참여자</th><th>누적수익률</th><th>CORE 수익률</th><th>차이 · %p</th><th>최대 낙폭</th><th>연율 변동성</th><th>개인 관측 기간 / 상태</th></tr></thead><tbody>{data.items.map(row=><tr key={row.participant_id}><td>{row.rank??"대기"}</td><th><button className="btn-secondary" aria-pressed={focus===row.participant_id} onClick={()=>setSelected(row.participant_id)}>{row.display_name}{row.participant_id===me.data?.participant_id?" (나)":""}</button></th><td>{fmtReturn(row.metrics.cumulative_return)}</td><td>{fmtReturn(row.metrics.benchmark_return)}</td><td>{fmtActivePp(row.metrics.difference_pp)}</td><td>{fmtPct(row.metrics.mdd)}{row.metric_quality?.mdd.status==="OBSERVED_ONLY"&&<><br/><small>관측값 · MDD 순위 보류</small></>}</td><td>{fmtPct(row.metrics.volatility)}</td><td>{fmtDate(row.observed_start)} — {fmtDate(row.observed_end)}<br/>{ledgerReason(row.reason)||"공통 기간 비교 가능"}</td></tr>)}</tbody></table></div></section>
      {person&&<section aria-label="선택 참여자 성과"><h2>{person.display_name} · 공통 기간 성과</h2><p>수익률 {fmtReturn(person.metrics.cumulative_return)} · 최대 낙폭 {fmtPct(person.metrics.mdd)} · 연율 변동성 {fmtPct(person.metrics.volatility)}</p><p>개인 관측 종료·마지막 유효 평가일 {fmtDate(person.observed_end)}. MDD는 유효 평가 2건 이상에서 관측된 최대 낙폭입니다. 평가 공백·오래된 가격이 있으면 놓친 낙폭을 확인할 수 없어 위험 순위를 보류합니다. 연율 변동성은 별도로 유효 수익률 30개 이상과 기존 평일 공백·가격 품질 조건이 필요합니다.</p>{person.reason&&<p>{ledgerReason(person.reason)}</p>}{person.metric_quality?.mdd.reason&&<p>MDD 비교: {ledgerReason(person.metric_quality.mdd.reason)}</p>}{person.metric_quality?.volatility.reason&&<p>연율 변동성: {ledgerReason(person.metric_quality.volatility.reason)} · 유효 수익률 {person.metric_quality.volatility.return_observations}개 / 필요 {person.metric_quality.volatility.minimum_return_observations}개</p>}{person.quality&&<p>오래된 가격 평가일 {person.quality.stale_observations}개 · 평일 평가 공백 구간 {person.quality.missing_nav_dates}개 · 표시 구간 내 평가 누락 {person.quality.missing_comparison_dates?.length??0}개</p>}</section>}
      {data.dates.length>1&&peers.length>1&&<section aria-label="참여자와 CORE 지수 그래프"><h2>공통 기간의 기준 100 지수</h2><p>원화 평가금액이 아닙니다. 모두 같은 시작 평가일 100에서 시작합니다. 각 참여자의 실제 관측을 보존하며, 없는 날짜는 빈칸으로 두고 선을 연결하지 않습니다. CORE 선은 선택 참여자의 시스템 기준 CORE 원장입니다.</p><PerformanceChart data={points} series={[...peers.map(p=>({key:p.participant_id,dataKey:p.participant_id,label:p.display_name,...(p.participant_id===focus?MY_LINE:{color:"#b6c3d6",width:1})})),{key:"core",dataKey:"core",label:"선택 참여자의 CORE V0.3",...CORE_LINE}]} curve="linear" animate={false} connectNulls={false} showPoints/>{!person?.series.every(p=>p.core_index100!==null)&&<p>같은 날짜의 CORE 평가가 없으면 해당 지수와 비교 수익률을 표시하지 않습니다. 결측 구간을 연결하지 않습니다.</p>}</section>}
      <p className="page-desc">기록 없음·한 건·공통 기간 없음은 순위를 산출하지 않습니다. 다른 참여자의 원화 잔액·보유·주문·판단 기록은 공개하지 않습니다.</p>
    </>}
  </div></AppShell>;
}
