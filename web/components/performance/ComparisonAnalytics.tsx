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
export function RiskReturnMap({reports,highlight,highlightLabel="내 포트폴리오"}:{reports:Comparison[];highlight?:string;highlightLabel?:string}) {
  const router=useRouter();
  const points=reports.filter((r):r is ReadyComparison=>r.status==="ready").filter(r=>r.metrics.volatility!=null).map(r=>({id:r.participant_id,name:r.display_name,themes:r.themes,x:r.metrics.volatility,y:r.metrics.cumulative_return,mdd:r.metrics.mdd,sharpe:r.metrics.sharpe}));
  const c=reports.find(r=>r.core_metrics)?.core_metrics;
  const core=c?.volatility!=null?[{id:"core",name:"CORE V0.3",themes:[],x:c.volatility,y:c.cumulative_return,mdd:c.mdd,sharpe:c.sharpe}]:[];
  const volatilities = [...points, ...core].map(p=>p.x).filter((v): v is number => v != null && Number.isFinite(v));
  const minVolatility = Math.min(.10, ...volatilities);
  const xStart = minVolatility < .09 ? Math.max(0, Math.floor((minVolatility - .01) * 100) / 100) : .09;
  const xStep = .03;
  const intervals = Math.max(1, Math.ceil((Math.max(xStart, ...volatilities) + .005 - xStart) / xStep));
  const xTicks = Array.from({length: intervals + 1}, (_, i) => Number((xStart + i * xStep).toFixed(6)));
  const xEnd = xTicks[xTicks.length - 1];
  return <section className="analytics-panel" aria-label="Risk–Return Map"><h2>Risk–Return Map</h2><p className="caption">X: 실현 변동성 · 연율 (오른쪽일수록 큼) / Y: 누적수익률 · 동일 비교 기간</p><div className="chart"><ResponsiveContainer><ScatterChart margin={{top:25,right:25,bottom:30,left:5}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="x" domain={[xStart, xEnd]} ticks={xTicks} allowDataOverflow tickFormatter={n=>fmtPct(n,1)} name="Volatility" label={{value:"Volatility · 연율",position:"bottom",offset:12}}/><YAxis type="number" dataKey="y" tickFormatter={n=>fmtPct(n,1)} name="Return"/><Tooltip cursor={{strokeDasharray:"3 3"}} content={({active,payload})=>{const p=payload?.[0]?.payload;return active&&p?<div className="analytics-tooltip"><strong>{p.name}</strong><p>{p.themes.map(themeLabel).join(" · ")}</p><p>Return {fmtReturn(p.y)} · MDD {fmtPct(p.mdd)}</p><p>Volatility {fmtPct(p.x)} · Sharpe {p.sharpe?.toFixed(2)??"—"}</p></div>:null;}}/><Scatter name="참가자" data={points} onClick={p=>router.push(`/participants/${p.id}`)}>{points.map(p=><Cell key={p.id} fill={p.id===highlight?"#2563eb":"#94a3b8"} stroke={p.id===highlight?"#1745a8":"#64748b"} strokeWidth={p.id===highlight?4:1}/>)}</Scatter><Scatter name="CORE" data={core} shape="diamond" fill="#111827"/></ScatterChart></ResponsiveContainer></div><ul className="race-legend point-legend" aria-label="차트 점 색상 안내">
      <li><i style={{background:"#2563eb"}}/>{highlightLabel}</li>
      <li><i className="benchmark-dot" style={{background:"#111827"}}/>벤치마크 · 공통 CORE</li>
      <li><i style={{background:"#94a3b8"}}/>다른 참가자</li>
    </ul><p className="caption">점을 선택하면 참가자 상세로 이동합니다.</p><div className="scenario-grid">{points.map(p=><Link className="btn-secondary" key={p.id} href={`/participants/${p.id}`}>{p.name}{p.id===highlight?" · 선택":""}</Link>)}</div>{!c&&<p>CORE 위험지표 없음</p>}</section>;
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
  return <section className="analytics-panel" aria-label="Portfolio Race"><h2>Portfolio Race</h2><p className="caption">{base?.data_source === "MARKET_PRICE_REPLAY" ? "가격 기반 비교 NAV 시작값 100" : "가상 NAV 시작값 100"} · {base?.start} — {base?.end} · 비교 가능 {ready.length}명 + CORE</p><div className="analytics-kpis race-kpis"><div><span>내 누적수익률</span><strong>{fmtReturn(mine?.metrics.cumulative_return)}</strong></div><div><span>CORE 누적수익률</span><strong>{fmtReturn(base?.metrics.core_return)}</strong></div><div><span>내 누적수익률 순위</span><strong>{rank?`${rank}위` : "—"}</strong></div></div><div className="ui-actions" role="group" aria-label="차트 표시 필터">{[["all","전체"],["mine","나 + CORE"],["top","상위 5명 · 누적수익률"]].map(([k,l])=><button className={filter===k?"btn-primary":"btn-secondary"} key={k} onClick={()=>setFilter(k)} aria-pressed={filter===k}>{l}</button>)}</div>
    <ul className="race-legend" aria-label="차트 선 색상 안내">
      <li><i style={{background:"#2563eb"}}/>내 포트폴리오{filter === "top" && mine && !visible.includes(mine) ? " (상위 5명에 미포함)" : ""}</li>
      <li><i style={{background:"#101d38"}}/>공통 CORE · 벤치마크</li>
      {filter !== "mine" && <li><i style={{background:"#c6cdd8"}}/>다른 참가자</li>}
    </ul>
    <div className="chart"><ResponsiveContainer><LineChart data={rows} margin={{top:25,right:12,bottom:5,left:0}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" minTickGap={60} tickFormatter={d=>d.slice(5)}/><YAxis domain={["auto","auto"]} tickFormatter={n=>n.toFixed(0)}/><Tooltip content={({active,payload,label})=>{if(!active||!payload?.length)return null;const id=hoverId??participantId;const focused=payload.find(p=>p.dataKey===id)??payload[0];const person=ready.find(r=>r.participant_id===focused?.dataKey);return <div className="analytics-tooltip"><strong>{person?.display_name??"CORE"}</strong><p>{person?.themes.map(themeLabel).join(" · ")}</p><p>{String(label)} · NAV {Number(focused?.value).toFixed(2)}</p><p>기준일 {person?.end??base?.end} 누적수익률 {fmtReturn(person?.metrics.cumulative_return??base?.metrics.core_return)}</p></div>;}}/>
    {visible.filter(r=>r.participant_id!==participantId).map(r=><Line key={r.participant_id} dataKey={r.participant_id} name={r.display_name} type="linear" stroke="#c6cdd8" strokeWidth={1} dot={false} activeDot={{r:5,onClick:()=>router.push(`/participants/${r.participant_id}`)}} isAnimationActive={false} onMouseEnter={()=>setHoverId(r.participant_id)} onClick={()=>router.push(`/participants/${r.participant_id}`)}/>)}
    <Line dataKey="core" name="CORE" type="linear" stroke="#101d38" strokeWidth={2.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId("core")}/>
    {mine&&visible.includes(mine)&&<Line dataKey={mine.participant_id} name={mine.display_name} type="linear" stroke="#2563eb" strokeWidth={3.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId(mine.participant_id)} activeDot={{r:6,onClick:()=>router.push(`/participants/${mine.participant_id}`)}}/>}
    </LineChart></ResponsiveContainer></div><label>참가자 상세 선택<select className="input mt-[8px]" defaultValue="" onChange={e=>{if(e.target.value)router.push(`/participants/${e.target.value}`);}}><option value="" disabled>이름으로 선택 · 모바일에서도 이용 가능</option>{data.reports.map(r=><option key={r.participant_id} value={r.participant_id}>{r.display_name} · {r.themes.map(themeLabel).join(" / ")}</option>)}</select></label>
  </section>;
}

export function ThemeComparison({data}:{data:Analytics}) {
  const [sort, setSort] = useState("count");
  const rows = [...data.theme_selectors].sort((a, b) => {
    const field = sort === "return" ? "cumulative_return" : sort === "excess" ? "excess_return" : sort === "mdd" ? "mdd" : "count";
    const av = a[field] ?? -Infinity, bv = b[field] ?? -Infinity;
    return (bv - av) || themeLabel(a.theme_id).localeCompare(themeLabel(b.theme_id), "ko");
  });
  const maxCount = Math.max(1, ...rows.map(t => t.count));
  return <section className="analytics-panel" aria-label="Theme 선택자 비교">
    <div className="theme-count-header"><div><h2>Theme 선택자 비교</h2><p className="caption">막대 높이는 테마를 선택한 참가자 수입니다.</p></div>
      <label>정렬 기준<select className="input" value={sort} onChange={e => setSort(e.target.value)}>
        <option value="count">많이 선택한 순</option><option value="return">평균 수익률 높은 순</option><option value="excess">CORE 초과수익률 높은 순</option><option value="mdd">최대낙폭 작은 순</option>
      </select></label>
    </div>
    <div className="theme-count-scroll">
      <table className="theme-count-table"><caption className="sr-only">테마별 선택자 수 막대그래프와 선택자 포트폴리오 평균 지표</caption>
        <thead><tr><th scope="col">테마</th>{rows.map(t=><th scope="col" key={t.theme_id}>{themeLabel(t.theme_id)}</th>)}</tr></thead>
        <tbody>
          <tr className="theme-count-chart"><th scope="row">선택자 수</th>{rows.map(t=><td key={t.theme_id}>
            <div className="theme-count-column" role="img" aria-label={`${themeLabel(t.theme_id)} ${t.count}명 선택`}>
              <strong>{t.count}<small>명</small></strong><div className="theme-count-bar" style={{height:`${t.count / maxCount * 145}px`}}/>
            </div>
          </td>)}</tr>
          <tr><th scope="row">평균 수익률</th>{rows.map(t=><td key={t.theme_id}>{fmtReturn(t.cumulative_return)}</td>)}</tr>
          <tr><th scope="row">평균 CORE 초과</th>{rows.map(t=><td key={t.theme_id}>{fmtActivePp(t.excess_return)}</td>)}</tr>
          <tr><th scope="row">평균 최대낙폭</th>{rows.map(t=><td key={t.theme_id}>{fmtPct(t.mdd)}</td>)}</tr>
        </tbody>
      </table>
    </div>
    <p className="caption">수익률·초과수익률·최대낙폭은 해당 테마 선택자들의 포트폴리오 평균이며 테마 자체 성과가 아닙니다. 두 테마를 선택한 참가자는 양쪽에 포함됩니다. · 비교 가능 {data.comparable}명 기준</p>
  </section>;
}

export function AnalyticsOverview({participantId}:{participantId?:string}) {
  const q=useComparisonAnalytics();
  if(q.isLoading)return <LoadingSkeleton rows={4}/>;
  if(q.isError)return <ErrorState message="전체 NAV와 위험지표를 불러오지 못했습니다." onRetry={()=>q.refetch()}/>;
  return q.data?<><PortfolioRace data={q.data} participantId={participantId}/><RiskReturnMap reports={q.data.reports} highlight={participantId}/></>:null;
}
