"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ScatterChart, Scatter, Cell } from "recharts";
import { get } from "@/lib/api/client";
import type { ComparisonAnalytics as Analytics, Comparison, ReadyComparison } from "@/lib/api/comparison";
import { ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { fmtActivePp, fmtPct, fmtReturn } from "@/lib/format";
import { themeLabel } from "@/lib/constants";

export function useComparisonAnalytics() {
  return useQuery({queryKey:["comparison-analytics"],queryFn:()=>get<Analytics>("/api/v1/comparison/analytics")});
}
export function RiskReturnMap({reports,highlight}:{reports:Comparison[];highlight?:string}) {
  const router=useRouter();
  const points=reports.filter((r):r is ReadyComparison=>r.status==="ready").filter(r=>r.metrics.volatility!=null).map(r=>({id:r.participant_id,name:r.display_name,themes:r.themes,x:r.metrics.volatility,y:r.metrics.cumulative_return,mdd:r.metrics.mdd,sharpe:r.metrics.sharpe}));
  const c=reports.find(r=>r.core_metrics)?.core_metrics;
  const core=c?.volatility!=null?[{id:"core",name:"CORE V0.3",themes:[],x:c.volatility,y:c.cumulative_return,mdd:c.mdd,sharpe:c.sharpe}]:[];
  return <section className="analytics-panel" aria-label="Risk–Return Map"><h2>Risk–Return Map</h2><p className="caption">X: 실현 변동성 · 연율 (오른쪽일수록 큼) / Y: 누적수익률 · 동일 비교 기간</p><div className="chart"><ResponsiveContainer><ScatterChart margin={{top:25,right:25,bottom:30,left:5}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="x" tickFormatter={n=>fmtPct(n,1)} name="Volatility" label={{value:"Volatility · 연율",position:"bottom",offset:12}}/><YAxis type="number" dataKey="y" tickFormatter={n=>fmtPct(n,1)} name="Return"/><Tooltip cursor={{strokeDasharray:"3 3"}} content={({active,payload})=>{const p=payload?.[0]?.payload;return active&&p?<div className="analytics-tooltip"><strong>{p.name}</strong><p>{p.themes.map(themeLabel).join(" · ")}</p><p>Return {fmtReturn(p.y)} · MDD {fmtPct(p.mdd)}</p><p>Volatility {fmtPct(p.x)} · Sharpe {p.sharpe?.toFixed(2)??"—"}</p></div>:null;}}/><Scatter name="참가자" data={points} onClick={p=>router.push(`/participants/${p.id}`)}>{points.map(p=><Cell key={p.id} fill={p.id===highlight?"#2563eb":"#94a3b8"} stroke={p.id===highlight?"#1745a8":"#64748b"} strokeWidth={p.id===highlight?4:1}/>)}</Scatter><Scatter name="CORE" data={core} shape="diamond" fill="#111827"/></ScatterChart></ResponsiveContainer></div><p className="caption">파란 점: 선택 참가자 · ◆ CORE · 점을 선택하면 상세로 이동합니다. 아래 참가자 목록으로도 이동할 수 있습니다.</p><div className="scenario-grid">{points.map(p=><Link className="btn-secondary" key={p.id} href={`/participants/${p.id}`}>{p.name}{p.id===highlight?" · 선택":""}</Link>)}</div>{!c&&<p>CORE 위험지표 없음</p>}</section>;
}

export function PortfolioRace({data,participantId}:{data:Analytics;participantId?:string}) {
  const [filter,setFilter]=useState("all");
  const router=useRouter();
  const ready=data.reports.filter(r=>r.status==="ready");
  const mine=ready.find(r=>r.participant_id===participantId);
  const top=new Set(data.rankings.return.slice(0,5).map(r=>r.participant_id));
  const visible=ready.filter(r=>filter==="mine"?r.participant_id===participantId:filter==="top"?top.has(r.participant_id):true);
  const base=ready[0];
  const rows=base?.series.map((p,i)=>({date:p.date,core:p.core_nav,...Object.fromEntries(visible.map(r=>[r.participant_id,r.series[i]?.date===p.date?r.series[i].personalized_nav:null]))}))??[];
  const rank=data.rankings.return.find(r=>r.participant_id===participantId)?.rank;
  const [hoverId,setHoverId]=useState<string|null>(null);
  return <section className="analytics-panel" aria-label="Portfolio Race"><h2>Portfolio Race</h2><p className="caption">{base?.data_source === "MARKET_PRICE_REPLAY" ? "가격 기반 비교 NAV 시작값 100" : "가상 NAV 시작값 100"} · {base?.start} — {base?.end} · 비교 가능 {ready.length}명 + CORE</p><div className="analytics-kpis"><div><span>내 누적수익률</span><strong>{fmtReturn(mine?.metrics.cumulative_return)}</strong></div><div><span>CORE 누적수익률</span><strong>{fmtReturn(base?.metrics.core_return)}</strong></div><div><span>내 누적수익률 순위</span><strong>{rank?`${rank}위` : "—"}</strong></div><div><span>CORE 초과 / 비교 대상</span><strong>{data.outperformers} / {data.comparable}</strong></div></div><div className="ui-actions" role="group" aria-label="차트 표시 필터">{[["all","전체"],["mine","나 + CORE"],["top","상위 5명 · 누적수익률"]].map(([k,l])=><button className={filter===k?"btn-primary":"btn-secondary"} key={k} onClick={()=>setFilter(k)} aria-pressed={filter===k}>{l}</button>)}</div>
    <div className="chart"><ResponsiveContainer><LineChart data={rows} margin={{top:25,right:12,bottom:5,left:0}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" minTickGap={60} tickFormatter={d=>d.slice(5)}/><YAxis domain={["auto","auto"]} tickFormatter={n=>n.toFixed(0)}/><Tooltip content={({active,payload,label})=>{if(!active||!payload?.length)return null;const id=hoverId??participantId;const focused=payload.find(p=>p.dataKey===id)??payload[0];const person=ready.find(r=>r.participant_id===focused?.dataKey);return <div className="analytics-tooltip"><strong>{person?.display_name??"CORE"}</strong><p>{person?.themes.map(themeLabel).join(" · ")}</p><p>{String(label)} · NAV {Number(focused?.value).toFixed(2)}</p><p>기준일 {person?.end??base?.end} 누적수익률 {fmtReturn(person?.metrics.cumulative_return??base?.metrics.core_return)}</p></div>;}}/>
    {visible.filter(r=>r.participant_id!==participantId).map(r=><Line key={r.participant_id} dataKey={r.participant_id} name={r.display_name} type="linear" stroke="#c6cdd8" strokeWidth={1} dot={false} activeDot={{r:5,onClick:()=>router.push(`/participants/${r.participant_id}`)}} isAnimationActive={false} onMouseEnter={()=>setHoverId(r.participant_id)} onClick={()=>router.push(`/participants/${r.participant_id}`)}/>)}
    <Line dataKey="core" name="CORE" type="linear" stroke="#101d38" strokeWidth={2.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId("core")}/>
    {mine&&visible.includes(mine)&&<Line dataKey={mine.participant_id} name={mine.display_name} type="linear" stroke="#2563eb" strokeWidth={3.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId(mine.participant_id)} activeDot={{r:6,onClick:()=>router.push(`/participants/${mine.participant_id}`)}}/>}
    </LineChart></ResponsiveContainer></div><label>참가자 상세 선택<select className="input mt-[8px]" defaultValue="" onChange={e=>{if(e.target.value)router.push(`/participants/${e.target.value}`);}}><option value="" disabled>이름으로 선택 · 모바일에서도 이용 가능</option>{data.reports.map(r=><option key={r.participant_id} value={r.participant_id}>{r.display_name} · {r.themes.map(themeLabel).join(" / ")}</option>)}</select></label>
  </section>;
}

export function ThemeComparison({data}:{data:Analytics}) {
  return <details className="analytics-panel"><summary>Theme 선택자 비교</summary><p className="page-desc">Theme 자체 수익률이 아닌 해당 Theme 선택자들의 포트폴리오 현황입니다. 두 Theme를 선택한 참가자는 두 집계에 모두 포함됩니다. 소규모 시연이며 통계적 우열을 뜻하지 않습니다.</p><div className="overflow-x-auto"><table className="fin-table"><thead><tr><th>Theme</th><th>선택자 수</th><th>평균 Portfolio Return</th><th>평균 Excess</th><th>평균 MDD</th></tr></thead><tbody>{data.theme_selectors.map(t=><tr key={t.theme_id}><th>{themeLabel(t.theme_id)}</th><td>{t.count}</td><td>{fmtReturn(t.cumulative_return)}</td><td>{fmtActivePp(t.excess_return)}</td><td>{fmtPct(t.mdd)}</td></tr>)}</tbody></table></div><p className="caption">같은 기간의 성과가 있는 {data.comparable}명 기준 · 집계 대기 참가자 제외 · 참여자별 동일 가중 산술평균</p></details>;
}

export function AnalyticsOverview({participantId}:{participantId?:string}) {
  const q=useComparisonAnalytics();
  if(q.isLoading)return <LoadingSkeleton rows={4}/>;
  if(q.isError)return <ErrorState message="전체 NAV와 위험지표를 불러오지 못했습니다." onRetry={()=>q.refetch()}/>;
  return q.data?<><PortfolioRace data={q.data} participantId={participantId}/><RiskReturnMap reports={q.data.reports} highlight={participantId}/></>:null;
}
