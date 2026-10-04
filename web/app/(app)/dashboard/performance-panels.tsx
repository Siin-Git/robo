"use client";
import type { ReactNode } from "react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Report, contributionView, reportChartPoints } from "./performance-data";
import { fmtActivePp, fmtDate, fmtReturn } from "@/lib/format";


function ChartTooltip({active,payload,label,unit="%",names,styles:s}:{styles:Record<string,string>;active?:boolean;payload?:readonly {dataKey?:string|number;value?:unknown;color?:string;name?:string|number}[];label?:unknown;unit?:string;names?:Record<string,string>}){
  if(!active||!payload?.length)return null;
  return <div className={s.tooltip}><strong>{fmtDate(String(label))}</strong>{payload.map((item,i)=><div key={String(item.dataKey??i)}><i style={{background:item.color}}/><span>{names?.[String(item.dataKey)]??item.name}</span><b>{Number(item.value)>0?"+":""}{Number(item.value).toFixed(2)}{unit}</b></div>)}</div>;
}
export function PerformancePanels({report,mode,selected,onSelect,onMode,styles:s,riskPanel}:{styles:Record<string,string>;riskPanel?:ReactNode;report:Report;mode:"groups"|"assets";selected:string|null;onSelect:(id:string|null)=>void;onMode:(mode:"groups"|"assets")=>void}){
  const data=reportChartPoints(report);
  const view=contributionView(report,mode);
  const observedContributions=new Map(view.points.map(p=>[p.date,p]));
  const contributionPoints=(report.comparison_window?.dates??view.points.map(p=>String(p.date))).map(date=>
    observedContributions.get(date)??{date,total:null,...Object.fromEntries(view.series.map(s=>[s.id,null]))});
  const max=Math.max(...view.ranking.map(r=>Math.abs(r.value)),.0001);
  const labels=Object.fromEntries(view.series.map(item=>[item.id,item.name]));
  const switchSelected=(id:string)=>onSelect(selected===id?null:id);
  return <>
    <section className={s.panel} aria-labelledby="performance-chart-heading"><div className={s.sectionHeading}><div><span className={s.eyebrow}>GROWTH OVER TIME</span><h2 id="performance-chart-heading">내 포트폴리오는 어떻게 움직였을까요?</h2></div><span className={s.unit}>누적수익률 %</span></div>
      <div className={s.lineLegend}><span><i style={{background:"#3268df"}}/>내 포트폴리오<strong>{fmtReturn(report.metrics.cumulative_return)}</strong></span><span><i style={{background:"#8896ab"}}/>시스템 기준 CORE<strong>{fmtReturn(report.metrics.benchmark_return)}</strong></span></div>
      <div className={s.mainChart} role="img" aria-label={`누적수익률: 내 포트폴리오 ${fmtReturn(report.metrics.cumulative_return)}, 시스템 기준 CORE ${fmtReturn(report.metrics.benchmark_return)}`}>
        <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:18,right:16,left:0,bottom:5}}>
          <CartesianGrid vertical={false} stroke="#e0e7f0" strokeDasharray="3 5"/><XAxis dataKey="date" tickFormatter={d=>String(d).slice(5).replace("-",".")} minTickGap={55} tickLine={false} axisLine={false} tick={{fill:"#718299",fontSize:11}} dy={10}/><YAxis tickFormatter={n=>`${n.toFixed(1)}%`} width={57} axisLine={false} tickLine={false} tick={{fill:"#718299",fontSize:11}}/>
          <ReferenceLine y={0} stroke="#adbcd0"/><Tooltip content={<ChartTooltip styles={s}/>}/><Line name="내 포트폴리오" dataKey="personal" stroke="#3268df" strokeWidth={3} dot={false} activeDot={{r:5}} connectNulls={false} isAnimationActive={false}/><Line name="시스템 기준 CORE" dataKey="benchmark" stroke="#8896ab" strokeWidth={2} strokeDasharray="6 5" dot={false} connectNulls={false} isAnimationActive={false}/>
        </LineChart></ResponsiveContainer>
      </div>
      {!report.quality.benchmark_complete&&<p className={s.infoNote}>CORE 기록이 없는 날짜는 선을 연결하지 않습니다. 비교 수익률은 동일한 시작·종료일이 있을 때만 계산합니다.</p>}
    </section>
    {riskPanel}
    <section className={s.panel} aria-labelledby="contribution-heading"><div className={s.sectionHeading}><div><span className={s.eyebrow}>RETURN CONTRIBUTION</span><h2 id="contribution-heading">내 수익은 어디에서 나왔을까요?</h2><p>위쪽은 수익에 더한 부분, 아래쪽은 수익에서 뺀 부분입니다.</p></div><div className={s.segmented} role="group" aria-label="기여도 표시 단위"><button aria-pressed={mode==="groups"} onClick={()=>onMode("groups")}>자산군</button><button aria-pressed={mode==="assets"} onClick={()=>onMode("assets")}>개별 자산</button></div></div>
      {report.quality.unresolved_intervals>0&&<p className={s.warning}>보유 내역이 부족한 {report.quality.unresolved_intervals}개 구간의 손익은 ‘미설명 차이’로 표시합니다.</p>}
      <div className={s.contributionGrid}><div className={s.contributionPlot}><div className={s.plotTitle}><span>누적 수익 기여도 · %p</span>{selected&&<button onClick={()=>onSelect(null)}>전체 강조로 돌아가기</button>}</div>
        <div className={s.areaChart} role="img" aria-label={`누적 기여도: ${view.series.map(r=>r.name+" "+fmtActivePp(r.value)).join(", ")}`}>
          <ResponsiveContainer width="100%" height="100%"><AreaChart data={contributionPoints} stackOffset="sign" margin={{top:12,right:14,left:0,bottom:5}}>
            <CartesianGrid vertical={false} stroke="#e0e7f0" strokeDasharray="3 5"/><XAxis dataKey="date" tickFormatter={d=>String(d).slice(5).replace("-",".")} minTickGap={50} tickLine={false} axisLine={false} tick={{fill:"#718299",fontSize:11}} dy={10}/><YAxis tickFormatter={n=>`${n.toFixed(1)}`} width={45} axisLine={false} tickLine={false} tick={{fill:"#718299",fontSize:11}}/><ReferenceLine y={0} stroke="#a7b5c8" strokeWidth={1.5}/><Tooltip content={<ChartTooltip styles={s} unit="%p" names={labels}/>}/>
            {view.series.map(item=><Area key={item.id} name={item.name} dataKey={item.id} type="linear" stackId="contribution" stroke={item.color} strokeWidth={selected===item.id?2.5:1} fill={item.color} fillOpacity={!selected||selected===item.id? .8 : .16} connectNulls={false} isAnimationActive={false} dot={false}/>)}
          </AreaChart></ResponsiveContainer>
        </div><div className={s.legend}>{view.series.map(item=><button key={item.id} aria-pressed={selected===item.id} onClick={()=>switchSelected(item.id)}><i style={{background:item.color}}/>{item.name}</button>)}</div>
      </div>
      <div className={s.ranking}><div className={s.rankingTitle}><h3>{mode==="groups"?"자산군별":"자산별"} 기여도</h3><span>선택 기간 합계</span></div>
        {view.ranking.length?view.ranking.map(item=><button key={item.id} className={s.rankRow} aria-pressed={selected===item.id} onClick={()=>switchSelected(item.id)}><div><span><i style={{background:item.color}}/>{item.name}</span><strong>{fmtActivePp(item.value)}</strong></div><div className={s.rankTrack}><span style={{left:item.value>=0?"50%":`${50-Math.abs(item.value)/max*50}%`,width:`${Math.abs(item.value)/max*50}%`,background:item.color}}/></div></button>):<p className={s.infoNote}>현재 기록에는 자산별 수익 기여가 없습니다.</p>}
        <div className={s.rankTotal}><span>합계 · 전체 수익률</span><strong>{fmtReturn(report.metrics.cumulative_return)}</strong></div><p className={s.rankHint}>항목을 누르면 차트에서 강조됩니다.<br/>양수와 음수를 합한 값이 전체 수익률입니다.</p>
      </div></div>
    </section>
    <section className={s.drawdownPanel}><div className={s.sectionHeading}><div><h2>고점에서 얼마나 내려왔을까요?</h2><p>선택 기간 안에서의 낙폭을 확인합니다.</p></div><strong>{fmtReturn(report.metrics.mdd)}</strong></div><div className={s.drawdownChart}>
      <ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{top:10,right:16,left:0,bottom:5}}><CartesianGrid vertical={false} stroke="#e4eaf2"/><XAxis dataKey="date" tickFormatter={d=>String(d).slice(5).replace("-",".")} minTickGap={65} axisLine={false} tickLine={false} tick={{fontSize:11,fill:"#718299"}}/><YAxis width={57} tickFormatter={n=>`${n.toFixed(1)}%`} axisLine={false} tickLine={false} tick={{fontSize:11,fill:"#718299"}}/><Tooltip content={<ChartTooltip styles={s}/>}/><Area name="고점 대비 낙폭" dataKey="drawdown" stroke="#7890b1" fill="#dce5f1" type="linear" connectNulls={false} isAnimationActive={false}/></AreaChart></ResponsiveContainer>
    </div></section>
  </>;
}
