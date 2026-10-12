"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ScatterChart, Scatter, Cell } from "recharts";
import { get } from "@/lib/api/client";
import type { ComparisonAnalytics as Analytics, Comparison, ReadyComparison } from "@/lib/api/comparison";
import { COMPARISON_REFRESH_MS } from "@/lib/api/comparison";
import { ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { fmtActivePp, fmtPct, fmtReturn } from "@/lib/format";
import { themeLabel } from "@/lib/constants";

export function useComparisonAnalytics() {
  return useQuery({queryKey:["comparison-analytics"],queryFn:()=>get<Analytics>("/api/v1/comparison/analytics"),refetchInterval:COMPARISON_REFRESH_MS});
}
export function RiskReturnMap({reports,highlight,highlightLabel="내 포트폴리오"}:{reports:Comparison[];highlight?:string;highlightLabel?:string}) {
  const router=useRouter();
  const points=reports.filter((r):r is ReadyComparison=>r.status==="ready").filter(r=>r.metrics.volatility!=null).map(r=>({id:r.participant_id,name:r.display_name,themes:r.themes,x:r.metrics.volatility,y:r.metrics.cumulative_return,mdd:r.metrics.mdd,sharpe:r.metrics.sharpe}));
  const c=reports.find(r=>r.core_metrics)?.core_metrics;
  const core=c?.volatility!=null?[{id:"core",name:"기준 포트폴리오 (CORE)",themes:[],x:c.volatility,y:c.cumulative_return,mdd:c.mdd,sharpe:c.sharpe}]:[];
  const volatilities = [...points, ...core].map(p=>p.x).filter((v): v is number => v != null && Number.isFinite(v));
  const minVolatility = Math.min(.10, ...volatilities);
  const xStart = minVolatility < .09 ? Math.max(0, Math.floor((minVolatility - .01) * 100) / 100) : .09;
  const xStep = .03;
  const intervals = Math.max(1, Math.ceil((Math.max(xStart, ...volatilities) + .005 - xStart) / xStep));
  const xTicks = Array.from({length: intervals + 1}, (_, i) => Number((xStart + i * xStep).toFixed(6)));
  const xEnd = xTicks[xTicks.length - 1];
  return <section className="analytics-panel" aria-label="Risk–Return Map"><h2>위험과 수익 비교</h2><p className="caption">위로 갈수록 수익률이 높고, 오른쪽으로 갈수록 가격 변동이 큽니다.</p><div className="chart"><ResponsiveContainer><ScatterChart margin={{top:25,right:25,bottom:30,left:5}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="x" domain={[xStart, xEnd]} ticks={xTicks} allowDataOverflow tickFormatter={n=>fmtPct(n,1)} name="Volatility" label={{value:"변동성 · 연율",position:"bottom",offset:12}}/><YAxis type="number" dataKey="y" tickFormatter={n=>fmtPct(n,1)} name="Return"/><Tooltip cursor={{strokeDasharray:"3 3"}} content={({active,payload})=>{const p=payload?.[0]?.payload;return active&&p?<div className="analytics-tooltip"><strong>{p.name}</strong><p>{p.themes.map(themeLabel).join(" · ")}</p><p>수익률 {fmtReturn(p.y)} · 최대 낙폭 {fmtPct(p.mdd)}</p><p>변동성 {fmtPct(p.x)} · 샤프 지수 {p.sharpe?.toFixed(2)??"—"}</p></div>:null;}}/><Scatter name="참가자" data={points} onClick={p=>router.push(`/participants/${p.id}?source=demo`)}>{points.map(p=><Cell key={p.id} fill={p.id===highlight?"#74a8ff":"#94a3b8"} stroke={p.id===highlight?"#aed0ff":"#64748b"} strokeWidth={p.id===highlight?4:1}/>)}</Scatter><Scatter name="CORE" data={core} shape="diamond" fill="#c7d3e6"/></ScatterChart></ResponsiveContainer></div><ul className="race-legend point-legend" aria-label="차트 점 색상 안내">
      <li><i style={{background:"#74a8ff"}}/>{highlightLabel}</li>
      <li><i className="benchmark-dot" style={{background:"#c7d3e6"}}/>기준 포트폴리오 (CORE)</li>
      <li><i style={{background:"#94a3b8"}}/>다른 참가자</li>
    </ul><p className="caption">점을 선택하면 참가자 상세로 이동합니다.</p><div className="scenario-grid">{points.map(p=><Link className="btn-secondary" key={p.id} href={`/participants/${p.id}?source=demo`}>{p.name}{p.id===highlight?" · 선택":""}</Link>)}</div>{!c&&<p>CORE 위험지표 없음</p>}</section>;
}

export function PortfolioRace({data,participantId}:{data:Analytics;participantId?:string}) {
  const [filter,setFilter]=useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const focusedId = filter === "selected" ? selectedId : participantId;
  const isOwn = focusedId === participantId;
  function selectParticipant(id: string) { setSelectedId(id); setFilter("selected"); setHoverId(null); }
  const ready=data.reports.filter(r=>r.status==="ready");
  const mine=ready.find(r=>r.participant_id===focusedId);
  const top=new Set(data.rankings.return.slice(0,5).map(r=>r.participant_id));
  const visible=ready.filter(r=>(filter==="mine" || filter==="selected")?r.participant_id===focusedId:filter==="top"?top.has(r.participant_id):true);
  const base=ready[0];
  const rows=base?.series.map((p,i)=>({date:p.date,core:p.core_nav,...Object.fromEntries(visible.map(r=>[r.participant_id,r.series[i]?.date===p.date?r.series[i].personalized_nav:null]))}))??[];
  const rank=data.rankings.return.find(r=>r.participant_id===focusedId)?.rank;
  const [hoverId,setHoverId]=useState<string|null>(null);
  const excess = mine?.metrics.excess_return;
  return <section className="analytics-panel race-panel" aria-label="투자 성과 비교">
    <div className="analytics-kpis race-kpis race-summary" aria-live="polite">
      <div><span>{isOwn ? "내 수익률" : `${mine?.display_name ?? "선택 참여자"} 수익률`}</span><strong>{fmtReturn(mine?.metrics.cumulative_return)}</strong><small>선택한 기간의 누적 성과</small></div>
      <div><span>기준 대비 차이</span><strong>{fmtActivePp(excess)}</strong><small>기준 포트폴리오 {fmtReturn(base?.metrics.core_return)}</small></div>
      <div><span>{isOwn ? "내 순위" : "선택 참여자 순위"}</span><strong>{rank ? `${rank}위` : "—"}<small> / {ready.length}명</small></strong><small>{rank ? "수익률 높은 순" : "포트폴리오 확정 후 표시"}</small></div>
    </div>
    <div className="race-chart-heading"><div><h2>투자금의 변화</h2><p className="caption">같은 날 100으로 시작했을 때의 평가액</p></div><div className="race-filters" role="group" aria-label="차트 표시 필터">{[["all","전체"],["mine","나와 기준"],["top","상위 5명"]].map(([k,l])=><button key={k} onClick={()=>{setFilter(k);setSelectedId(null);setHoverId(null);}} aria-pressed={filter===k}>{l}</button>)}</div></div>
    <div className="race-participant-picker">
      <label>참여자와 기준 비교<select className="input" value={filter === "selected" ? selectedId ?? "" : ""} onChange={e=>{if(e.target.value)selectParticipant(e.target.value);}}>
        <option value="" disabled>참여자를 선택하세요</option>
        {data.reports.map(r=><option key={r.participant_id} value={r.participant_id} disabled={r.status !== "ready"}>{r.display_name}{r.participant_id === participantId ? " (나)" : ""} · {r.themes.map(themeLabel).join(" / ") || "기본 구성"}{r.status !== "ready" ? " · 집계 대기" : ""}</option>)}
      </select></label>
      {filter === "selected" && mine && <Link href={`/participants/${mine.participant_id}?source=demo`} className="race-participant-detail">상세 성과 보기 →</Link>}
    </div>
    <ul className="race-legend" aria-label="차트 선 색상 안내">
      {mine && visible.includes(mine) && <li><i style={{background:"#74a8ff"}}/>{isOwn ? "내 포트폴리오" : mine.display_name}</li>}
      <li><i style={{background:"#c7d3e6"}}/>기준 포트폴리오 (CORE)</li>
      {visible.some(r=>r.participant_id !== focusedId) && <li><i style={{background:"#647a98"}}/>다른 참가자</li>}
    </ul>
    <div className="chart"><ResponsiveContainer><LineChart data={rows} margin={{top:25,right:12,bottom:5,left:0}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" minTickGap={60} tickFormatter={d=>d.slice(5)}/><YAxis domain={["auto","auto"]} tickFormatter={n=>n.toFixed(0)}/><Tooltip content={({active,payload,label})=>{if(!active||!payload?.length)return null;const id=hoverId??focusedId;const focused=payload.find(p=>p.dataKey===id)??payload[0];const person=ready.find(r=>r.participant_id===focused?.dataKey);return <div className="analytics-tooltip"><strong>{person?.display_name??"CORE"}</strong><p>{person?.themes.map(themeLabel).join(" · ")}</p><p>{String(label)} · 평가액 {Number(focused?.value).toFixed(2)}</p><p>기준일 {person?.end??base?.end} 누적수익률 {fmtReturn(person?.metrics.cumulative_return??base?.metrics.core_return)}</p></div>;}}/>
    {visible.filter(r=>r.participant_id!==focusedId).map(r=><Line key={r.participant_id} dataKey={r.participant_id} name={r.display_name} type="linear" stroke="#647a98" strokeWidth={1} dot={false} activeDot={{r:5,onClick:()=>selectParticipant(r.participant_id)}} isAnimationActive={false} onMouseEnter={()=>setHoverId(r.participant_id)} onClick={()=>selectParticipant(r.participant_id)}/>)}
    <Line dataKey="core" name="CORE" type="linear" stroke="#c7d3e6" strokeWidth={2.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId("core")}/>
    {mine&&visible.includes(mine)&&<Line dataKey={mine.participant_id} name={mine.display_name} type="linear" stroke="#74a8ff" strokeWidth={3.5} dot={false} isAnimationActive={false} onMouseEnter={()=>setHoverId(mine.participant_id)} activeDot={{r:6,onClick:()=>selectParticipant(mine.participant_id)}}/>}
    </LineChart></ResponsiveContainer></div>
  </section>;
}

export function ThemeComparison({data,ledger=false}:{data:{comparable:number;theme_selectors:{theme_id:string;count:number;cumulative_return:number|null;excess_return:number|null;mdd:number|null;measured?:Record<string,number>}[]};ledger?:boolean}) {
  const [sort, setSort] = useState("count");
  const rows = [...data.theme_selectors].sort((a, b) => {
    const field = sort === "return" ? "cumulative_return" : sort === "excess" ? "excess_return" : sort === "mdd" ? "mdd" : "count";
    const av = a[field] ?? -Infinity, bv = b[field] ?? -Infinity;
    return (bv - av) || themeLabel(a.theme_id).localeCompare(themeLabel(b.theme_id), "ko");
  });
  const metrics = [
    { key: "cumulative_return", label: "평균 수익률", format: fmtReturn },
    { key: "excess_return", label: "평균 기준 대비", format: fmtActivePp },
    { key: "mdd", label: ledger ? "평균 관측 최대낙폭" : "평균 최대낙폭", format: fmtPct },
  ] as const;
  return <section className="analytics-panel" aria-label="Theme 선택자 비교">
    <div className="theme-count-header"><div><h2>{ledger ? "편입 테마별 성과" : "테마별 선택과 성과"}</h2><p className="caption">{ledger ? "같은 기간에 해당 테마를 보유한 참여자들의 포트폴리오 평균입니다." : "선택 인원과 테마별 참여자들의 평균 성과를 비교하세요."}</p></div>
      <label>정렬 기준<select className="input" value={sort} onChange={e => setSort(e.target.value)}>
        <option value="count">많이 선택한 순</option><option value="return">평균 수익률 높은 순</option><option value="excess">기준 대비 수익률 높은 순</option><option value="mdd">최대낙폭 작은 순</option>
      </select></label>
    </div>
    <div className="theme-count-scroll" tabIndex={0} aria-label="좌우로 이동 가능한 테마 성과 표">
      <table className="theme-count-table"><caption className="sr-only">테마별 선택 인원과 포트폴리오 평균 성과 막대그래프</caption>
        <thead><tr><th scope="col">테마</th>{rows.map(t=><th scope="col" key={t.theme_id}>{themeLabel(t.theme_id)}</th>)}</tr></thead>
        <tbody>
          <tr className="theme-selection-count"><th scope="row">{ledger ? "편입 인원" : "선택 인원"}</th>{rows.map(t=><td key={t.theme_id}><strong>{t.count}</strong><small>명</small></td>)}</tr>
          {metrics.map(metric => {
            const values = rows.map(t => t[metric.key]).filter((v): v is number => v != null && Number.isFinite(v));
            const low = Math.min(0, ...values), high = Math.max(0, ...values);
            const range = high - low || 1;
            const zero = high / range * 100;
            return <tr className="theme-metric-row" key={metric.key}>
              <th scope="row">{metric.label}<small>{metric.key === "mdd" ? "0에 가까울수록 안정적" : "높을수록 좋은 성과"}</small></th>
              {rows.map(t => {
                const value = t[metric.key];
                const valid = value != null && Number.isFinite(value);
                const height = valid ? Math.abs(value) / range * 100 : 0;
                const top = valid && value > 0 ? zero - height : zero;
                return <td key={t.theme_id}>
                  <div className="theme-metric-plot" role="img" aria-label={`${themeLabel(t.theme_id)} ${metric.label} ${metric.format(value)}`}>
                    <span className="theme-zero-line" style={{top:`${zero}%`}}/>
                    {valid && <span className="theme-metric-bar" data-negative={value < 0} data-risk={metric.key === "mdd"} style={{top:`${top}%`,height:`${height}%`}}/>}
                  </div>
                  <strong className="theme-metric-value">{metric.format(value)}</strong>
                  {ledger && <small className="caption" style={{display:"block"}}>관측 {t.measured?.[metric.key] ?? 0}명</small>}
                </td>;
              })}
            </tr>;
          })}
        </tbody>
      </table>
    </div>
    <p className="caption">같은 행의 막대끼리 비교하세요. 행마다 눈금이 다르며 가로선은 0입니다. 테마 자체 수익률이 아닌 {ledger ? "기간 내 편입자" : "선택자"}들의 포트폴리오 평균입니다. 두 테마 {ledger ? "편입자" : "선택자"}는 양쪽에 포함됩니다. · {data.comparable}명 기준{ledger && " · 최대낙폭은 관측값이며 위험 순위를 뜻하지 않습니다."}</p>
  </section>;
}

export function AnalyticsOverview({participantId}:{participantId?:string}) {
  const q=useComparisonAnalytics();
  if(q.isLoading)return <LoadingSkeleton rows={4}/>;
  if(q.isError)return <ErrorState message="전체 NAV와 위험지표를 불러오지 못했습니다." onRetry={()=>q.refetch()}/>;
  return q.data?<><PortfolioRace data={q.data} participantId={participantId}/><RiskReturnMap reports={q.data.reports} highlight={participantId}/></>:null;
}
