"use client";

import {useState} from "react";
import {useSearchParams} from "next/navigation";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {ArrowUpRight, ArrowRight, Wallet, Activity, Layers3, RefreshCw, UserRound, ChevronRight} from "lucide-react";
import {ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell, ReferenceLine} from "recharts";
import {AppShell} from "@/components/layout/AppShell";
import {useCurrentUser} from "@/components/layout/AppSidebar";
import {useHistoricalPreview} from "./HistoricalPreview";
import {ReturnContribution} from "./ReturnContribution";
import {HistoricalLedger} from "./HistoricalLedger";
import {LedgerHistory} from "./LedgerHistory";
import {ForwardOperations} from "./ForwardOperations";
import {Continuity} from "./Continuity";
import {OperationReadiness} from "./OperationReadiness";
import {get} from "@/lib/api/client";
import {getForwardLedger} from "@/lib/api/ledger";
import {fmtReturn, fmtActivePp, fmtPct, fmtDate} from "@/lib/format";
import {assetName, reportChartPoints, type Report} from "@/app/(app)/dashboard/performance-data";
import s from "./DarkDashboard.module.css";

const COLORS=["#659bff","#64d4bb","#a49bf4","#ddbf83","#64bbd9","#c791bb","#98afc6","#8ba2e8","#83bb97","#cfa58a","#8298a7","#b2bcc9"];
const money=(v:number|null|undefined)=>v==null?"—":`${Math.round(v).toLocaleString("ko-KR")}원`;
const tone=(v:number|null|undefined)=>v==null?s.neutral:v>0?s.positive:v<0?s.negative:s.neutral;

/** Dashboard overview. All amounts and financial metrics come from existing read APIs. */
export function DarkDashboard(){
 const params=useSearchParams();
 const user=useCurrentUser();
 const [view,setView]=useState<"auto"|"archive"|"forward">(params.get("source")==="forward"?"forward":params.get("source")==="archive"?"archive":"auto");
 const history=useHistoricalPreview();
 const forward=useQuery({queryKey:["dashboard-performance","ALL",false],queryFn:()=>get<Report>("/api/v1/me/performance/dashboard?period=ALL&comparison=individual"),refetchInterval:60_000,refetchIntervalInBackground:false});
 const saved=history.data?.available?history.data.report:undefined;
 const archive=!!saved?.ledger&&(view==="archive"||(view==="auto"&&!forward.isLoading&&!!forward.data&&(forward.data.series.length??0)<2));
 const source=archive?"archive":"forward";
 const ledgerQuery=useQuery({queryKey:["dark-preview-forward-ledger"],queryFn:getForwardLedger,enabled:!archive&&!forward.isLoading,refetchInterval:60_000,refetchIntervalInBackground:false});
 const ledger=archive?saved?.ledger:ledgerQuery.data;
 const latest=ledger?.snapshots.at(-1);
 const report=forward.data;
 const loading=view==="auto"?(history.isLoading||forward.isLoading):view==="archive"?history.isLoading:forward.isLoading;
 const error=archive||view==="archive"?history.isError:forward.isError||(view==="auto"&&!forward.isLoading&&(forward.data?.series.length??0)<2&&history.isError);
 const hasData=archive ? !!saved : !!report && !(view==="auto" && history.isError && !saved && report.series.length<2);
 const points=archive&&saved?saved.series.map(p=>({date:p.date,personal:p.personal_index-100,benchmark:p.core_index-100})):report?reportChartPoints(report):[];
 const ready=points.filter(p=>p.personal!=null).length>1;
 const personal=archive?saved?.summary.personal_return:report?.metrics.cumulative_return;
 const core=archive?saved?.summary.core_return:report?.metrics.benchmark_return;
 const difference=archive&&personal!=null&&core!=null?personal-core:report?.metrics.difference_pp;
 const start=archive?saved?.start:report?.start;
 const end=archive?saved?.end:report?.end;
 const observations=archive?saved?.summary.observations:report?.observations;
 const balance=archive?latest?.nav:report?.valuation?.nav_krw;
 const cash=archive?latest?.cash_balance:report?.valuation?.cash_krw;
 const holdings=[...(latest?.holdings??[])].filter(h=>h.market_value>0).sort((a,b)=>b.market_value-a.market_value);
 const mix=holdings.map(h=>({name:assetName(h.asset_id),value:h.market_value}));
 if((cash??0)>0)mix.push({name:"현금",value:cash!});
 const sourceLabel=archive?`${fmtDate(start)} 기준 모의운용`:report?.data_kind==="TEST_FIXTURE"?"검증용 합성 데이터":report?.data_kind==="HISTORICAL_REPLAY"?"과거 가격 모의실험":"자동운용";
 const originalHref=`/dashboard?view=details&source=${source}`;
 const retry=()=>{void history.refetch();void forward.refetch();void ledgerQuery.refetch();};
 return <div className={s.theme}><AppShell headerTitle="대시보드" headerRight={<div className={s.account}><UserRound size={15}/>{user?.display_name??user?.participant_id??"내 계정"}</div>}>
  <div className={s.page}>
   <div className={s.preview}><span>PORTFOLIO OVERVIEW <b>내 투자 현황 한눈에 보기</b></span><Link href={originalHref}>상세 분석 <ArrowUpRight size={14}/></Link></div>
   <header className={s.heading}><div><p className={s.eyebrow}>MY INVESTMENT</p><h1>내 투자의 흐름을 한눈에</h1><p>성과부터 보유자산까지, 기록된 숫자로 살펴보세요.</p></div><Link className={s.primary} href="/portfolio">내 포트폴리오 <ArrowUpRight size={17}/></Link></header>
   <Continuity/>
   <div className={s.toolbar}><div className={s.tabs} role="group" aria-label="운용 기록 선택">{saved?.ledger&&<button aria-pressed={archive} onClick={()=>setView("archive")}>기준일 모의운용</button>}<button aria-pressed={!archive} onClick={()=>setView("forward")}>자동운용</button></div><span className={s.asof}><span/>{end?`${fmtDate(end)} 평가 기준`:"평가일 미확보"}<button aria-label="기록 새로고침" onClick={retry}><RefreshCw size={14}/></button></span></div>
   {error&&hasData&&<p role="alert">기록 갱신에 실패했습니다. 이전 조회 결과를 표시합니다. <button className="btn-secondary" onClick={retry}>다시 조회</button></p>}
   {!archive && report?.data_kind === "TEST_FIXTURE" && <p role="status">검증용 합성 데이터 · 실제 운용 실적이 아닙니다.</p>}
   {loading?<section className={s.empty} role="status">운용 기록을 불러오고 있어요.</section>:error&&!hasData?<section className={s.empty} role="alert"><h2>성과 기록을 불러오지 못했어요</h2><button className={s.primary} onClick={retry}>다시 불러오기</button></section>:<>
    <section className={s.metrics} aria-label="성과 요약">
     <div className={s.balance}><span>총 평가자산 <Wallet size={15}/></span><strong>{money(balance)}</strong><small>{sourceLabel}</small></div>
     <div><span>누적 수익률</span><strong className={tone(ready?personal:null)}>{ready?fmtReturn(personal):"—"}</strong><small>{start&&end?`${fmtDate(start)} — ${fmtDate(end)}`:"평가 기록 2개부터 표시"}</small></div>
     <div><span>CORE 대비</span><strong className={tone(ready?difference:null)}>{ready?fmtActivePp(difference):"—"}</strong><small>기준 포트폴리오 {ready?fmtReturn(core):"—"}</small></div>
     <div><span>보유 현금</span><strong>{money(cash)}</strong><small>마지막 평가일의 현금 잔액</small></div>
    </section>
    <div className={s.mainGrid}>
     <section className={`${s.card} ${s.chartCard}`}><div className={s.cardHeading}><div><h2>수익률의 흐름</h2><p>내 포트폴리오와 CORE 비교</p></div><span className={s.pill}>전체 기간</span></div>
      <div className={s.legend}><span><i style={{background:COLORS[0]}}/>내 포트폴리오 <b>{ready?fmtReturn(personal):"—"}</b></span><span><i style={{background:"#8a99ad"}}/>CORE <b>{ready?fmtReturn(core):"—"}</b></span></div>
      {ready?<div className={s.chart} role="img" aria-label={`${start}부터 ${end}까지 누적 수익률. 내 포트폴리오 ${fmtReturn(personal)}, CORE ${fmtReturn(core)}`}><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{top:20,right:16,bottom:8,left:0}} accessibilityLayer><CartesianGrid vertical={false} stroke="#293548" strokeDasharray="3 5"/><XAxis dataKey="date" tickFormatter={v=>v.slice(5).replace("-",".")} tick={{fill:"#91a2b8",fontSize:11}} tickLine={false} axisLine={false} minTickGap={28} dy={12}/><YAxis tickFormatter={v=>`${v.toFixed(1)}%`} tick={{fill:"#91a2b8",fontSize:11}} tickLine={false} axisLine={false} width={52} domain={['auto','auto']}/><Tooltip contentStyle={{background:"#1b293b",border:"1px solid #42526b",borderRadius:12,color:"#edf3fb"}} labelFormatter={v=>fmtDate(String(v))} formatter={(v:number,name:string)=>[`${v>0?"+":""}${v.toFixed(2)}%`,name]} cursor={{stroke:"#58708d",strokeDasharray:"4 4"}}/><ReferenceLine y={0} stroke="#40516b"/><Line type="linear" dataKey="benchmark" name="CORE" stroke="#8a99ad" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false}/><Line type="linear" dataKey="personal" name="내 포트폴리오" stroke={COLORS[0]} strokeWidth={3} dot={{r:3,fill:COLORS[0],stroke:"#122139",strokeWidth:2}} activeDot={{r:5}} connectNulls={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>:<div className={s.chartEmpty}><Activity size={30}/>{archive ? <h3>저장된 모의운용 관측 부족</h3> : <OperationReadiness/>}<p>동일 기간의 정상 평가액이 두 날짜 이상 기록되어야 수익률을 표시합니다.</p><Link href="/portfolio">저장된 구성 확인 <ArrowRight size={14}/></Link></div>}
      <div className={s.chartFoot}><span>기록된 평가일 <b>{observations??0}일</b></span><Link href={originalHref}>성과 상세 <ChevronRight size={14}/></Link></div>
     </section>
     <section className={`${s.card} ${s.mixCard}`}><div className={s.cardHeading}><div><h2>지금의 자산 구성</h2><p>{latest?.date?`${fmtDate(latest.date)} · 보유 금액 기준`:"마지막 평가일의 보유 금액 기준"}</p></div><Layers3 size={19}/></div>
      {mix.length?<><div className={s.donut}><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={mix} dataKey="value" nameKey="name" innerRadius="70%" outerRadius="92%" stroke="#142033" strokeWidth={3} paddingAngle={1} isAnimationActive={false}>{mix.map((v,i)=><Cell key={v.name} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip contentStyle={{background:"#1b293b",border:"1px solid #42526b",borderRadius:12,color:"#edf3fb"}} itemStyle={{color:"#edf3fb"}} formatter={(v:number)=>money(v)}/></PieChart></ResponsiveContainer><div className={s.donutLabel}><span>보유자산</span><strong>{holdings.length}<small>개</small></strong></div></div>
       <ul className={s.holdings}>{mix.slice(0,5).map((item,i)=><li key={item.name}><span><i style={{background:COLORS[i]}}/>{item.name}</span><b>{money(item.value)}</b></li>)}</ul>{mix.length>5&&<small className={s.more}>외 {mix.length-5}개 항목 · 전체 구성은 상세에서 확인</small>}</>:<div className={s.chartEmpty}><Layers3 size={28}/><p>{ledgerQuery.isError?"보유 내역을 불러오지 못했어요.":"아직 기록된 보유자산이 없어요."}</p>{ledgerQuery.isError&&<button onClick={()=>ledgerQuery.refetch()}>다시 불러오기</button>}</div>}
      <a className={s.detailLink} href="#dark-records" onClick={()=>{const d=document.getElementById("dark-records");if(d instanceof HTMLDetailsElement)d.open=true;}}>보유·운용 내역 <ArrowRight size={15}/></a>
     </section>
    </div>
    <ReturnContribution report={archive?saved?.performance_report:report}/>
    <div className={s.actions}>
     <div className={s.action}><span className={s.icon}><Activity size={20}/></span><div><h3>{archive?"기록으로 확인하는 모의운용":"자동운용 기록"}</h3><p>{archive?`평가 ${observations??0}회 · 모의 체결 ${ledger?.trades.length??0}건`:`평가 ${observations??0}회 · ${end?`마지막 평가 ${fmtDate(end)}`:"정상 평가일 미확보"}`}</p></div></div>
     <Link className={s.action} href={`/ranking?source=${source}`}><span className={s.icon}><Layers3 size={20}/></span><div><h3>다른 참여자와 비교</h3><p>같은 기간의 성과와 순위를 확인하세요</p></div><ArrowUpRight size={18}/></Link>
     <Link className={s.action} href="/review"><span className={s.icon}><RefreshCw size={20}/></span><div><h3>처음의 판단 돌아보기</h3><p>저장한 예상과 이후의 기록을 함께</p></div><ArrowUpRight size={18}/></Link>
    </div>
    <details id="dark-records" className={s.disclosure}><summary>보유자산과 운용 기록 <span>현금 · 주문 · 체결 <ChevronRight size={16}/></span></summary><div className={s.records}>{archive&&saved?<HistoricalLedger report={saved}/>:<><ForwardOperations latestValuationDate={end??null} observations={observations??null}/><LedgerHistory/></>}</div></details>
    <details className={s.disclosure}><summary>계산 기준과 데이터 확인 <span>출처 · 평가일 · 일별 수치 <ChevronRight size={16}/></span></summary><div className={s.method}>
     {archive&&saved?<><p>저장된 구성을 해당 기간의 시장 가격으로 사후 계산한 모의운용입니다. 기준일부터 실제로 자동 수집·운용한 기록을 뜻하지 않으며, 자동운용 기록과 합산하지 않습니다. 최초 매수 후 보유하며 거래비용 {saved.cost_bps}bp를 적용했습니다. 최초 매수비용은 첫 평가액에 반영되어 있습니다.</p><p>구성 확정 {fmtDate(saved.decision_confirmed_at)} · {saved.is_current_configuration?"현재 구성과 일치":"구성 변경 전의 저장 결과"}. 시장별로 각 평가일에 이용 가능한 마지막 가격을 사용합니다.</p><details><summary>자산별 가격 기준일</summary><div className={s.tableWrap}><table><thead><tr><th>평가일</th><th>자산</th><th>가격 기준일</th></tr></thead><tbody>{Object.entries(saved.price_dates).flatMap(([day,assets])=>Object.entries(assets).map(([asset,date])=><tr key={`${day}-${asset}`}><td>{day}</td><td>{assetName(asset)}</td><td>{date}</td></tr>))}</tbody></table></div></details></>:<p>원화 모의운용 평가액의 첫 관측일을 기준으로 계산합니다. CORE와 같은 기간을 비교하며, 없는 평가 값은 만들지 않습니다. 미확인 공백은 선을 연결하지 않습니다. 상세 위험 지표와 기여도는 <Link href={originalHref}>성과 상세 화면</Link>에서 확인할 수 있습니다.</p>}
     <div className={s.tableWrap}><table><thead><tr><th>평가일</th><th>내 누적 수익률</th><th>CORE</th></tr></thead><tbody>{points.map(p=><tr key={p.date}><td>{p.date}</td><td>{fmtPct(p.personal==null?null:p.personal/100)}</td><td>{fmtPct(p.benchmark==null?null:p.benchmark/100)}</td></tr>)}</tbody></table></div>
    </div></details>
   </>}
   <footer className={s.footer}>Robo Advisor <span>시장 가격을 이용한 모의운용 · 실제 계좌 거래가 아닙니다</span></footer>
  </div>
 </AppShell></div>;
}
