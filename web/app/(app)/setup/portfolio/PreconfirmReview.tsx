"use client";
import {useState,type ReactNode} from "react";
import {useQuery} from "@tanstack/react-query";
import {ArrowLeft,ArrowRight} from "lucide-react";
import {post} from "@/lib/api/client";
import {fmtDate,fmtPct,fmtReturn} from "@/lib/format";
import {PerformanceChart,CORE_LINE,MY_LINE} from "@/components/dashboard/PerformanceChart";
import type {Rehearsal} from "@/components/portfolio/InvestmentRehearsal";
import type {ReviewData} from "./review-data";
import {THEME_INFO} from "./theme-content";
import {useSetupStyles} from "../style-context";
import {REBALANCE_LABELS,type RebalanceFrequency} from "@/lib/rebalance";

export type DraftRehearsal=Omit<Rehearsal,"decision_id"|"confirmed_at">&{decision_id:null;confirmed_at:null;proposal:ReviewData};
const won=(v:number)=>`${Math.round(v).toLocaleString("ko-KR")}원`;
export function PreconfirmReview({basePoint,themeIds,onBack,onComplete,onCompleteBase,pending,error,rebalanceFrequency,selectionReason,renderDetails}:{
  basePoint:{frontier_id:string};themeIds:string[];onBack:()=>void;onComplete:()=>void;onCompleteBase:()=>void;pending:boolean;error:boolean;
  rebalanceFrequency?:RebalanceFrequency;selectionReason?:{value:string;onChange:(value:string)=>void};renderDetails:(proposal:ReviewData)=>ReactNode;
}) {
  const {review:s}=useSetupStyles();
  const [period,setPeriod]=useState("all"),[amount,setAmount]=useState(10_000_000),[view,setView]=useState<"drawdown"|"value">("drawdown");
  const [periods,setPeriods]=useState<{id:string;label:string}[]>([{id:"all",label:"전체 자료 기간"}]);
  const q=useQuery({queryKey:["onboarding-rehearsal",basePoint.frontier_id,themeIds,period,amount],
    queryFn:async()=>{const result=await post<DraftRehearsal>("/api/v1/me/onboarding/rehearsal",{frontier_id:basePoint.frontier_id,theme_ids:themeIds,period,initial_amount:amount});return result;},retry:1});
  // Keep the period menu available while another period loads or fails.
  const options=q.data?.periods.length?q.data.periods:periods;
  const changePeriod=(next:string)=>{setPeriods(options);setPeriod(next);};
  const d=q.isError?undefined:q.data;
  const available=d?.status==="AVAILABLE"&&d.base&&d.personalized&&d.period;
  const waiting=q.isFetching||pending;
  const canConfirm=!!d&&!waiting;
  return <div className={s.page}>
    <header className={s.header}><div className={s.eyebrow}>BEFORE & AFTER</div><h1>확정하기 전에, 두 구성을 비교해 보세요</h1>
      <p>{themeIds.length?<><strong>{themeIds.map(id=>THEME_INFO[id]?.name??id).join(" · ")}</strong>를 반영한 구성과 기본 구성을 같은 조건에서 살펴봅니다.</>:"선택한 위험 수준의 기본 구성입니다. 과거 움직임을 확인하고 시작하세요."}</p></header>
    <section className={`${s.changes} ${s.rehearsal}`} aria-label="확정 전 과거 비교">
      <div className={s.sectionHeading}><div><h2>과거에 어떻게 달랐을까요?</h2><p>현재 선택한 비중을 과거 가격에 적용한 가정 계산입니다. 실제 운용 성과나 미래 예측이 아닙니다.</p></div></div>
      <div className={s.rehearsalControls}>
        <label>비교 기간<select aria-label="비교 기간" value={period} disabled={pending} onChange={e=>changePeriod(e.target.value)}>{options.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
        <label>가정 투자금<select aria-label="가정 투자금" value={amount} disabled={pending} onChange={e=>{setPeriods(options);setAmount(Number(e.target.value));}}>{[1_000_000,10_000_000,100_000_000].map(v=><option key={v} value={v}>{won(v)}</option>)}</select></label>
        <span>같은 기간 · 같은 금액 · 매수 후 보유</span>
      </div>
      {q.isError?<div className={s.rehearsalEmpty} role="alert"><p>과거 비교를 불러오지 못했습니다. 선택한 조건을 다시 조회해 주세요.</p><button className={s.back} onClick={()=>q.refetch()}>다시 조회</button></div>
        :!d?<div className={s.rehearsalEmpty} role="status">선택한 두 구성을 비교하고 있습니다.</div>
        :!available?<div className={s.rehearsalEmpty} role="status"><h3>과거 비교 자료 미확보</h3><p>{d.reason}</p><p>아래 비중과 예상 위험은 확인할 수 있지만, 과거 성과 비교 없이 확정하게 됩니다.</p></div>
        :<><p className={s.rehearsalDates}>{fmtDate(d.period!.start)} ~ {fmtDate(d.period!.end)} · {d.period!.observations.toLocaleString()}개 관측</p>
          <div className={s.rehearsalMetrics} aria-label="과거 비교 결과">{([
            ["기간 내 최대 낙폭",fmtPct(d.base!.max_drawdown),fmtPct(d.personalized!.max_drawdown)],
            ["기간 수익률",fmtReturn(d.base!.cumulative_return),fmtReturn(d.personalized!.cumulative_return)],
            ["마지막 평가액",won(d.base!.end_value),won(d.personalized!.end_value)],
          ] as const).map(([title,base,personal])=><div key={title}><h3>{title}</h3><dl><div><dt>기본 구성</dt><dd>{base}</dd></div><div><dt>선택한 구성</dt><dd>{personal}</dd></div></dl></div>)}</div>
          <div className={s.rehearsalChartBar}><div role="group" aria-label="과거 비교 그래프"><button aria-pressed={view==="drawdown"} onClick={()=>setView("drawdown")}>낙폭</button><button aria-pressed={view==="value"} onClick={()=>setView("value")}>평가액</button></div><span><i/> 기본 구성 <b/> 선택한 구성</span></div>
          <p className={s.explanation}>{view==="drawdown"?"선택 기간의 직전 고점 대비 하락률입니다. 과거 최대 낙폭은 미래 손실 한도가 아닙니다.":"두 구성에 같은 투자금을 적용한 평가액입니다. 비용·세금과 정기 리밸런싱은 반영하지 않았습니다."}</p>
          <div className={s.rehearsalChart}><PerformanceChart data={d.series} series={[{key:"base",label:"기본 구성",dataKey:view==="drawdown"?"base_drawdown":"base_value",...CORE_LINE,dash:"4 3"},{key:"personalized",label:"선택한 구성",dataKey:view==="drawdown"?"personalized_drawdown":"personalized_value",...MY_LINE}]}
            yFormat={view==="drawdown"?v=>fmtPct(v,1):v=>`${(v/10000).toLocaleString("ko-KR",{maximumFractionDigits:1})}만원`} yAxisWidth={view==="drawdown"?55:88} height={250} curve="linear" animate={false} connectNulls={false} showLegend={false} framed={false}/></div>
          <details className={s.rehearsalMethod}><summary>계산 기준과 자료 출처</summary><p>시작일에 소수 수량으로 매수해 보유하는 가정입니다. 수수료·세금·현금 이자와 정기 리밸런싱을 반영하지 않습니다. 연도별 비교는 매년 첫 관측일부터 새로 시작합니다. 현재 선택을 과거에 적용한 결과이므로 당시 실행 가능한 전략의 실적이 아닙니다.</p><p>기존 원화 환산·조정 가격을 사용합니다. 미국국채·TIPS는 환헤지 대용가격으로 실제 환헤지 비용을 재현하지 않습니다. 자료 전처리를 포함하므로 모든 관측이 해당 자산의 새 거래 가격은 아닙니다.</p><p>{d.source?.version} · {d.source?.source}</p></details>
        </>}
    </section>
    <footer className={`${s.footer} ${s.preconfirmFooter}`} aria-label="비교 후 구성 선택">
      <div><strong>어떤 구성으로 시작할까요?</strong><p>확정하면 선택한 비중으로 저장됩니다.{rebalanceFrequency&&<span aria-label="확정 전 리밸런싱 주기"> 정기 리밸런싱: {REBALANCE_LABELS[rebalanceFrequency]}.</span>}</p>
        {selectionReason&&<label className={s.selectionReason}>선택 이유 <span>선택 사항 · 나중에 검토할 때 함께 표시됩니다</span><textarea aria-label="확정 전 선택 이유" value={selectionReason.value} maxLength={1024} disabled={pending} onChange={e=>selectionReason.onChange(e.target.value)} placeholder="이 구성을 선택한 이유와 더 확인하고 싶은 점"/></label>}
      </div>
      <div className={s.preconfirmActions}>{themeIds.length>0&&<button className={s.back} onClick={onCompleteBase} disabled={!canConfirm}>기본 구성으로 확정</button>}<button className={s.confirm} onClick={onComplete} disabled={!canConfirm}>{pending?"설정 중…":themeIds.length?"선택한 테마 반영해 확정":"기본 구성으로 확정"}<ArrowRight size={17}/></button><button className={s.back} onClick={onBack} disabled={pending}><ArrowLeft size={16}/>테마 다시 고르기</button></div>
    </footer>
    {error&&<p className={s.error} role="alert">구성을 저장하지 못했습니다. 대기 주문 등 확정 조건을 확인하고 다시 시도해 주세요.</p>}
    {d&&<details className={s.details}><summary>비중과 예상 위험 자세히 보기<span>자산배분 · 예상 변동성 · 프런티어</span></summary>{renderDetails(d.proposal)}</details>}
  </div>;
}
