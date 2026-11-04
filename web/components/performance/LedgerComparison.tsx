"use client";
import {useState,useRef,useEffect} from "react";
import Link from "next/link";
import {useQuery} from "@tanstack/react-query";
import {ArrowUpRight,ChevronDown,ChartNoAxesCombined} from "lucide-react";
import {ResponsiveContainer,ScatterChart,Scatter,Cell,XAxis,YAxis,CartesianGrid,Tooltip} from "recharts";
import {AppShell} from "@/components/layout/AppShell";
import {ErrorState,LoadingSkeleton} from "@/components/shared/ui";
import {DataTable,Column} from "@/components/tables/DataTable";
import {PerformanceChart,CORE_LINE,MY_LINE} from "@/components/dashboard/PerformanceChart";
import {ThemeComparison} from "./ComparisonAnalytics";
import {get} from "@/lib/api/client";
import {fmtDate,fmtReturn,fmtPct,fmtActivePp} from "@/lib/format";
import {themeLabel} from "@/lib/constants";
import {DEMO_MODE} from "@/lib/api/comparison";
import {LedgerComparison as Contract,LedgerBasis,LedgerPeer,ledgerReason} from "@/lib/api/ledger-comparison";
import {PERIODS,Period,observedChartDates} from "@/app/(app)/dashboard/performance-data";
import s from "./demo-ranking.module.css";
import ui from "./ledger-ranking.module.css";

const bases: {key:LedgerBasis;label:string}[] = [
  {key:"return",label:"수익률 높은 순"},{key:"excess",label:"CORE 대비 차이 큰 순"},
  {key:"mdd",label:"최대 낙폭 작은 순"},{key:"volatility",label:"연율 변동성 낮은 순"},
];
type Filter="all"|"mine"|"top"|"selected";

function RiskMap({items,focus,select}:{items:LedgerPeer[];focus?:string;select:(id:string)=>void}) {
  // A measured value alone is insufficient: honor the server's quality gate.
  const points=items.filter(p=>p.metric_quality?.volatility.rankable && p.metrics.volatility!=null && p.metrics.cumulative_return!=null)
    .map(p=>({id:p.participant_id,name:p.display_name,x:p.metrics.volatility!,y:p.metrics.cumulative_return!}));
  return <section className={`analytics-panel ${ui.riskPanel}`} aria-label="위험과 수익 비교">
    <h2>위험과 수익 비교</h2><p className="caption">위로 갈수록 수익률이 높고, 오른쪽으로 갈수록 가격 변동이 큽니다.</p>
    {points.length>=2 ? <><div className="chart"><ResponsiveContainer><ScatterChart margin={{top:24,right:24,bottom:12,left:8}}>
      <CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="x" name="연율 변동성" tickFormatter={v=>fmtPct(v,1)}/>
      <YAxis type="number" dataKey="y" name="누적수익률" tickFormatter={v=>fmtPct(v,1)}/>
      <Tooltip cursor={{strokeDasharray:"3 3"}} content={({active,payload})=>active&&payload?.[0] ? <div className="analytics-tooltip"><strong>{payload[0].payload.name}</strong><p>수익률 {fmtReturn(payload[0].payload.y)}</p><p>연율 변동성 {fmtPct(payload[0].payload.x)}</p></div> : null}/>
      <Scatter data={points} isAnimationActive={false} onClick={p=>select(p.id)}>{points.map(p=><Cell key={p.id} fill={p.id===focus?MY_LINE.color:"#9aaac0"}/>)}</Scatter>
    </ScatterChart></ResponsiveContainer></div><p className="caption">가로축 · 연율 변동성 / 세로축 · 누적수익률. CORE의 연율 위험 좌표는 이 API에서 제공하지 않습니다.</p>
    <div className={ui.peerButtons}>{points.map(p=><button key={p.id} className="btn-secondary" aria-pressed={focus===p.id} onClick={()=>select(p.id)}>{p.name} 비교</button>)}</div></> :
    <div className={ui.waiting} role="status"><ChartNoAxesCombined size={28} aria-hidden="true"/><strong>운용 기록이 쌓이면 위험 분포가 표시됩니다</strong><p>연율 변동성은 유효 수익률 30개 이상과 가격·평가 품질 조건이 필요합니다.</p><small>현재 산출 가능한 참여자 {points.length}명 · 비교 기준 보기에서 진행 상태 확인</small></div>}
  </section>;
}

export function LedgerComparison({participantId}:{participantId?:string}) {
  const [source,setSource]=useState<"auto"|"archive"|"forward">("auto");
  const [hasArchive,setHasArchive]=useState(false);
  const [period,setPeriod]=useState<Period>("ALL");
  const [basis,setBasis]=useState<LedgerBasis>("return");
  const [selected,setSelected]=useState<string|null>(participantId??null);
  const [filter,setFilter]=useState<Filter>("all");
  const summaryRef=useRef<HTMLElement>(null);
  const me=useQuery({queryKey:["comparison-identity"],queryFn:()=>get<{participant_id:string}>("/api/v1/me")});
  const q=useQuery({queryKey:["ledger-comparison",period,basis,source],queryFn:()=>get<Contract>(`/api/v1/me/performance/comparison?period=${period}&basis=${basis}&source=${source}`),refetchInterval:15_000});
  const data=q.data;
  useEffect(()=>{if(data?.archive_available)setHasArchive(true);},[data?.archive_available]);
  const archived=data?.selected_source==="archive";
  const focus=(filter==="mine" ? me.data?.participant_id : selected??me.data?.participant_id);
  const person=data?.items.find(p=>p.participant_id===focus);
  const own=focus===me.data?.participant_id;
  const peers=data?.items.filter(p=>p.series.length>1)??[];
  // Top-five and KPI ranks use server return_rank, independent of table sorting.
  const returnRank=(p:LedgerPeer)=>p.return_rank??(basis==="return"?p.rank:null);
  const visible=peers.filter(p=>filter==="mine"||filter==="selected" ? p.participant_id===focus : filter==="top" ? returnRank(p)!=null&&returnRank(p)!<=5 : true);
  const chartDates=observedChartDates(data?.dates??[],data?.replay_context?.excluded_dates,
    date=>data?.items.some(peer=>peer.series.some(p=>p.date===date&&(p.personal_index100!=null||p.core_index100!=null)))??false);
  const points=chartDates.map(date=>({date,core:person?.series.find(p=>p.date===date)?.core_index100??null,
    ...Object.fromEntries(visible.map(peer=>[peer.participant_id,peer.series.find(p=>p.date===date)?.personal_index100??null]))}));
  function select(id:string) {setSelected(id);setFilter("selected");summaryRef.current?.scrollIntoView?.({behavior:window.matchMedia?.("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});}
  function filterChart(next:Filter) {setFilter(next);if(next==="mine")setSelected(null);}
  const riskBasis=basis==="mdd"||basis==="volatility";
  const columns:Column<LedgerPeer>[]=[
    {key:"rank",header:"순위",render:r=><span className={r.rank!=null&&r.rank<=3?s.topRank:s.rank}>{r.rank==null?"대기":String(r.rank).padStart(2,"0")}</span>},
    {key:"participant",header:"참여자",render:r=><div><button className={`${s.person} ${ui.personButton}`} aria-label={r.display_name+(r.participant_id===me.data?.participant_id?" (나)":"")} aria-pressed={focus===r.participant_id} onClick={()=>select(r.participant_id)}>{r.display_name}{r.participant_id===me.data?.participant_id&&<small>나</small>}<ArrowUpRight size={13}/></button><span className={s.mobileMetric}>{riskBasis?fmtPct(r.metrics.mdd):fmtReturn(r.metrics.cumulative_return)}</span></div>},
    {key:"themes",header:"기간 내 편입 테마",render:r=><div className={s.themes}>{r.themes?.length?r.themes.map(t=><span className={s.themeChip} key={t}>{themeLabel(t)}</span>):<span className="caption">{r.observations<2?"집계 대기":"기본 구성"}</span>}</div>},
    {key:riskBasis?"mdd":"return",header:riskBasis?"관측 최대 낙폭":"수익률",numeric:true,render:r=><div><strong className={`${s.primaryMetric} ${basis==="return"||basis==="mdd"?s.selectedMetric:""}`}>{riskBasis?fmtPct(r.metrics.mdd):fmtReturn(r.metrics.cumulative_return)}</strong>{riskBasis&&r.metric_quality?.mdd.status==="OBSERVED_ONLY"&&<small className={ui.metricNote}>MDD 순위 보류</small>}</div>},
    {key:riskBasis?"volatility":"excess",header:riskBasis?"연율 변동성":"CORE 대비",numeric:true,render:r=><strong className={`${s.secondaryMetric} ${basis==="excess"||basis==="volatility"?s.selectedMetric:""}`}>{riskBasis?fmtPct(r.metrics.volatility):fmtActivePp(r.metrics.difference_pp)}</strong>},
  ];
  return <AppShell headerTitle="참여자 성과 비교" softBackground><div className={`${s.page} ${ui.page}`}>
    <header className={s.header}><div><h1>참여자 성과 비교</h1><p className="page-desc">같은 기간의 수익률과 위험을 비교합니다.</p></div><Link className="btn-secondary" href={archived?"/dashboard?view=details&source=archive":`/dashboard?comparison=common&period=${period}&source=forward`}>공통 기간의 내 성과·기여도</Link></header>
    {(hasArchive||data?.archive_available)&&<div className="race-filters" role="group" aria-label="비교 기록 선택"><button aria-pressed={archived} onClick={()=>setSource("archive")}>저장된 모의운용</button><button aria-pressed={!archived} onClick={()=>setSource("forward")}>자동운용</button></div>}
    <div className={ui.context}><div className={ui.contextText}><span className={ui.sourceBadge}>{!data?"기록 확인 중":archived?"모의운용 성과":data?.data_kind==="HISTORICAL_REPLAY"?"과거 가격 모의실험":data?.data_kind==="TEST_FIXTURE"?"검증용 합성 데이터":"실제 시장 가격 모의운용"}</span><span>{fmtDate(data?.start)} — {fmtDate(data?.end)}</span><span>{data?.registered??"—"}명 비교</span></div><label className={ui.period}>조회 기간<select aria-label="조회 기간" className="input" value={period} onChange={e=>setPeriod(e.target.value as Period)}>{PERIODS.map(p=><option key={p.key} value={p.key}>{p.label}</option>)}</select></label></div>
    {q.isLoading?<LoadingSkeleton rows={5}/>:q.isError?<ErrorState message="운용 원장 비교를 불러오지 못했습니다." onRetry={()=>q.refetch()}/>:data&&<>
      {data.reason&&<p className={ui.notice} role="status">순위 대기 · {ledgerReason(data.reason)}</p>}
      <section ref={summaryRef} className="analytics-panel race-panel" aria-label="투자 성과 비교">
        <div className="analytics-kpis race-kpis race-summary" aria-live="polite">
          <div><span>{own?"내 수익률":`${person?.display_name??"선택 참여자"} 수익률`}</span><strong>{fmtReturn(person?.metrics.cumulative_return)}</strong><small>공통 기간의 누적 성과</small></div>
          <div><span>기준 대비 차이</span><strong>{fmtActivePp(person?.metrics.difference_pp)}</strong><small>CORE 수익률 {fmtReturn(person?.metrics.benchmark_return)}</small></div>
          <div><span>{own?"내 순위":"선택 참여자 순위"}</span><strong>{person&&returnRank(person)!=null?`${returnRank(person)}위`:"—"}<small> / {data.return_ranked??data.ranked}명</small></strong><small>수익률 높은 순</small></div>
        </div>
        <div className="race-chart-heading"><div><h2>투자금의 변화</h2><p className="caption">같은 날 100으로 시작했을 때의 평가 지수</p></div><div className="race-filters" role="group" aria-label="차트 표시 필터">{([["all","전체"],["mine","나와 기준"],["top","상위 5명"]] as const).map(([k,l])=><button key={k} aria-pressed={filter===k} onClick={()=>filterChart(k)}>{l}</button>)}</div></div>
        <div className="race-participant-picker"><label>참여자와 기준 비교<select aria-label="참여자와 기준 비교" className="input" value={selected??""} onChange={e=>select(e.target.value)}><option value="" disabled>참여자를 선택하세요</option>{data.items.map(p=><option key={p.participant_id} value={p.participant_id}>{p.display_name}{p.participant_id===me.data?.participant_id?" (나)":""}{p.series.length<2?" · 집계 대기":""}</option>)}</select></label></div>
        <ul className="race-legend" aria-label="차트 선 색상 안내">{visible.some(p=>p.participant_id===focus)&&<li><i style={{background:MY_LINE.color}}/>{own?"내 포트폴리오":person?.display_name??"선택 참여자"}</li>}<li><i style={{background:CORE_LINE.color}}/>기준 포트폴리오 (CORE)</li>{visible.some(p=>p.participant_id!==focus)&&<li><i style={{background:"#647a98"}}/>다른 참가자</li>}</ul>
        {data.dates.length>1&&peers.length>1 ? <section className={ui.chart} aria-label="참여자와 CORE 지수 그래프"><PerformanceChart data={points} series={[...visible.map(p=>({key:p.participant_id,dataKey:p.participant_id,label:p.display_name,...(p.participant_id===focus?{color:MY_LINE.color,width:3}:{color:"#647a98",width:1})})),{key:"core",dataKey:"core",label:"선택 참여자의 CORE V0.3",...CORE_LINE,width:2.5}]} curve="linear" animate={false} connectNulls={false} showPoints framed={false} showLegend={false}/></section> : <div className={ui.waiting} role="status"><strong>첫 성과 기록을 기다리고 있습니다</strong><p>{ledgerReason(person?.reason??data.reason) || "같은 기간의 평가 기록이 두 건 이상 쌓이면 표시됩니다."}</p></div>}
        <p className={s.footnote}>확인된 휴장일은 표시축에서 제외해 앞뒤 관측을 연결합니다. 원인 불명의 평가 누락은 선을 끊어 표시합니다.</p>
      </section>
      <RiskMap items={data.items} focus={focus} select={select}/>
      <section className={s.panel} aria-label="운용 기록 참여자 순위"><div className={s.toolbar}><div><h2>참여자 순위 <span>{data.registered}명</span></h2><p>참여자를 선택하면 위에서 같은 기간의 성과를 비교할 수 있습니다.</p></div><label>정렬 기준<span className={s.selectWrap}><select aria-label="순위 기준" className="input" value={basis} onChange={e=>setBasis(e.target.value as LedgerBasis)}>{bases.map(b=><option key={b.key} value={b.key}>{b.label}</option>)}</select><ChevronDown size={14}/></span></label></div>
        <p className={s.sortHint}>{riskBasis?"기록·가격 품질 조건을 충족한 경우에만 위험 순위를 산출합니다.":basis==="return"?"누적수익률이 높은 순서입니다.":"CORE와 같은 기간의 차이가 큰 순서입니다."}</p>
        <p className={`${s.footnote} ${ui.scrollHint}`}>표를 좌우로 밀어 테마와 비교 지표를 확인하세요.</p>
        <DataTable rows={data.items} columns={columns} rowKey={r=>r.participant_id} rowClassName={r=>`${s.row} ${r.rank!=null&&r.rank<=3?s.topRow:""} ${r.participant_id===me.data?.participant_id?"analytics-my-row":""} ${r.participant_id===focus?ui.focusRow:""}`}/>
        <p className={s.footnote}>산출할 수 없는 지표는 ‘—’로 표시합니다.</p>
      </section>
      {data.theme_selectors?.length ? <ThemeComparison ledger data={{theme_selectors:data.theme_selectors,comparable:data.items.filter(p=>p.metrics.cumulative_return!=null).length}}/> : <section className="analytics-panel" aria-label="테마별 성과 대기"><h2>편입 테마별 성과</h2><p className="caption">같은 기간의 테마 보유·평가 기록이 쌓이면 참여자 평균을 보여드립니다.</p></section>}
      <details className={`${s.guide} ${ui.guide}`}><summary>비교 기준 보기</summary>
        <p>{data.data_kind==="HISTORICAL_REPLAY"?"현재 확정 구성의 과거 가격 모의실험 원장입니다. 확정 이후 실제 운용 실적이 아닙니다.":data.data_kind==="TEST_FIXTURE"?"검증용 합성 데이터 · 실제 운용 기록이 아닙니다.":"확정 이후의 실제 시장 가격 모의운용 원장입니다."} 입출금 없는 계좌의 기록된 NAV 변화로 계산합니다.</p>
        <dl><div><dt>공통 비교 기간</dt><dd>{fmtDate(data.start)} — {fmtDate(data.end)} · 그래프 표시 날짜 {chartDates.length}개 · 순위 산출 {data.ranked}명 / 등록 {data.registered}명. 시작·종료일을 맞추고 각 참여자의 구간 내부 실제 평가를 모두 사용합니다.</dd></div><div><dt>기준 100 지수</dt><dd>원화 평가금액이 아닙니다. 같은 시작 평가일 100에서 시작합니다. CORE는 선택 참여자의 같은 기간 시스템 기준 원장입니다. 확인된 휴장일만 표시축에서 제외하며, 실제 관측과 원인 불명의 누락은 유지합니다. 휴장일 가격·평가·수익률을 생성하지 않습니다.</dd></div><div><dt>편입 테마</dt><dd>기간 내 보유 기록으로 묶은 참여자들의 포트폴리오 평균입니다. 테마 자체의 수익률이 아니며 두 테마 편입자는 두 그룹에 모두 포함됩니다. 각 지표의 실제 관측 인원을 표시합니다.</dd></div></dl>
        {person&&<section aria-label="선택 참여자 성과" className={ui.detail}><h3>{person.display_name} · 공통 기간 성과</h3><p>수익률 {fmtReturn(person.metrics.cumulative_return)} · CORE 수익률 {fmtReturn(person.metrics.benchmark_return)} · 최대 낙폭 {fmtPct(person.metrics.mdd)} · 연율 변동성 {fmtPct(person.metrics.volatility)}</p><p>개인 관측 {fmtDate(person.observed_start)} — {fmtDate(person.observed_end)} · 평가 {person.observations}건</p>
          <p>MDD는 유효 평가 2건 이상에서 관측된 최대 낙폭입니다. 평가 공백·오래된 가격이 있으면 놓친 낙폭을 확인할 수 없어 위험 순위를 보류합니다. 연율 변동성은 별도로 유효 수익률 30개 이상과 기존 평일 공백·가격 품질 조건이 필요합니다.</p>{person.reason&&<p>{ledgerReason(person.reason)}</p>}{person.metric_quality?.mdd?.reason&&<p>MDD 비교: {ledgerReason(person.metric_quality.mdd.reason)}</p>}{person.metric_quality?.volatility?.reason&&<p>연율 변동성: {ledgerReason(person.metric_quality.volatility.reason)} · 유효 수익률 {person.metric_quality.volatility.return_observations}개 / 필요 {person.metric_quality.volatility.minimum_return_observations}개</p>}{person.quality&&<p>오래된 가격 평가일 {person.quality.stale_observations}개 · 평일 평가 공백 구간 {person.quality.missing_nav_dates}개 · 표시 구간 내 평가 누락 {person.quality.missing_comparison_dates?.length??0}개</p>}
        </section>}
        <p>기록 없음·한 건·공통 기간 없음은 순위를 산출하지 않습니다. 다른 참여자의 원화 잔액·보유 수량·주문·판단 기록은 공개하지 않습니다.</p>
        <div className="ui-actions"><Link href="/dashboard">내 운용 성과</Link>{DEMO_MODE&&<Link href="/ranking?source=demo">과거 가격 비교·시연 보기</Link>}</div>
      </details>
    </>}
  </div></AppShell>;
}
