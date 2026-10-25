"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, ChevronDown, Info, SlidersHorizontal } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api/client";
import { fmtDate, fmtPct, fmtReturn } from "@/lib/format";
import { PerformanceChart, CORE_LINE, MY_LINE } from "@/components/dashboard/PerformanceChart";
import { ASSET_META } from "@/app/(app)/setup/portfolio/asset-meta";
import { THEME_INFO } from "@/app/(app)/setup/portfolio/theme-content";
import s from "./InvestmentRehearsal.module.css";
import {rehearsalHref,type RehearsalContext} from "@/lib/rehearsal-context";

type Period = { id: string; label: string; start: string; end: string; observations: number };
type Result = { weights: Record<string, number>; end_value: number; cumulative_return: number; max_drawdown: number };
export interface Rehearsal {
  status: "AVAILABLE" | "UNAVAILABLE"; reason: string | null;
  kind: "HISTORICAL_REHEARSAL"; actual_account_history: false;
  decision_id: string; confirmed_at: string; selection_reason: string;
  initial_amount: number; currency: "KRW"; periods: Period[]; period: Period | null;
  base: Result | null; personalized: Result | null;
  series: { date: string; base_value: number; personalized_value: number; base_drawdown: number; personalized_drawdown: number }[];
  source: { version: string; source: string; currency: string; start: string; end: string; sha256: string } | null;
}
const won = (v: number) => `${Math.round(v).toLocaleString("ko-KR")}원`;
const name = (id: string) => ASSET_META[id]?.name ?? THEME_INFO[id.replace(/^theme:/, "")]?.name ?? id;
type View = "drawdown" | "value";

export function InvestmentRehearsal({ decisionId, initialContext = {period: "all", amount: 10_000_000} }: { decisionId: string; initialContext?: RehearsalContext }) {
  const [period, setPeriod] = useState(initialContext.period);
  const [amount, setAmount] = useState(initialContext.amount);
  const [view, setView] = useState<View>("drawdown");
  const [periodOptions, setPeriodOptions] = useState<{id: string; label: string}[]>([{id: "all", label: "전체 자료 기간"}, ...(initialContext.period === "all" ? [] : [{id: initialContext.period, label: `${initialContext.period}년` }])]);
  const query = useQuery({ queryKey: ["investment-rehearsal", decisionId, period, amount],
    queryFn: () => get<Rehearsal>(`/api/v1/me/decisions/${encodeURIComponent(decisionId)}/rehearsal?period=${period}&initial_amount=${amount}`),
    staleTime: 60_000, retry: 1 });
  const data = query.data;
  const chartId = useId();
  useEffect(() => { if (data?.periods.length) setPeriodOptions(data.periods); }, [data?.periods]);
  const available = !query.isError && data?.status === "AVAILABLE" && data.base && data.personalized && data.period;
  const metric = (title: string, key: keyof Omit<Result, "weights">, format: (v: number) => string, primary = false) => <section className={s.metric} data-primary={primary} aria-label={title}>
    <h3>{title}</h3><dl>{([["기본 구성", data!.base!, false], ["내 구성", data!.personalized!, true]] as const).map(([label, result, personal]) =>
      <div key={label} data-personal={personal}><dt><i aria-hidden/>{label}</dt><dd>{format(result[key])}</dd></div>)}</dl>
  </section>;
  return <div className={s.page}>
    <Link className={s.back} href="/portfolio"><ArrowLeft size={14} aria-hidden/>내 포트폴리오</Link>
    <header className={s.header}>
      <div><h1>내 투자 리허설</h1><p>내 선택이 바꾼 하락의 크기, 기본 구성과 비교해 보세요.</p></div>
      <span className={s.badge}><span aria-hidden/>과거 가정 계산</span>
    </header>
    <p className={s.notice}><Info size={15} aria-hidden/><span>확정 비중을 과거 가격에 적용합니다. 실제 계좌 성과가 아닙니다. 과거 낙폭은 미래 손실 한도가 아닙니다.</span></p>
    <section className={s.workspace} aria-label="투자 리허설 비교">
      <div className={s.controls}>
        <span className={s.controlCaption}><SlidersHorizontal size={15} aria-hidden/>비교 조건</span>
        <label>비교 기간<span className={s.selectWrap}><select value={period} onChange={e => setPeriod(e.target.value)}>
          {periodOptions.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select><ChevronDown size={13} aria-hidden/></span></label>
        <label>가정 투자금<span className={s.selectWrap}><select value={amount} onChange={e => setAmount(Number(e.target.value))}>
          {[1_000_000, 10_000_000, 100_000_000].map(v => <option key={v} value={v}>{won(v)}</option>)}
        </select><ChevronDown size={13} aria-hidden/></span></label>
        <span className={s.conditionNote}>같은 기간 · 같은 금액</span>
      </div>
      {query.isError ? <div role="alert" className={s.empty}><Info size={24} aria-hidden/><h2>리허설을 불러오지 못했습니다</h2><p>선택한 조건의 결과를 다시 조회해 주세요.</p><button className="btn-secondary" onClick={() => query.refetch()}>다시 조회</button></div>
        : query.isLoading || !data ? <div className={s.loading} role="status" aria-label="Loading"><span className={s.loadingBar}/><span className={s.loadingBar}/><p>두 구성을 같은 조건으로 비교하고 있습니다.</p><div className={s.loadingChart}/></div>
        : !available ? <div role="status" className={s.empty}><Info size={24} aria-hidden/><h2>비교 자료 미확보</h2><p>{data.reason}</p><button className="btn-secondary" onClick={() => query.refetch()}>다시 조회</button></div> : <>
          <div className={s.resultMeta}><span>{fmtDate(data.period!.start)} ~ {fmtDate(data.period!.end)}</span><span>{data.period!.observations.toLocaleString()}개 관측 · 각 {won(data.initial_amount)}</span></div>
          <div className={s.metrics} aria-label="두 구성의 과거 가정 계산 결과">
            {metric("기간 내 최대 낙폭", "max_drawdown", fmtPct, true)}
            {metric("기간 수익률", "cumulative_return", fmtReturn)}
            {metric("마지막 평가액", "end_value", won)}
          </div>
          <div className={s.chartToolbar}>
            <div className={s.switch} role="group" aria-label="그래프 보기">
              <button type="button" aria-pressed={view === "drawdown"} aria-controls={chartId} onClick={() => setView("drawdown")}>낙폭</button>
              <button type="button" aria-pressed={view === "value"} aria-controls={chartId} onClick={() => setView("value")}>평가액</button>
            </div>
            <div className={s.legend} aria-label="그래프 범례"><span><i aria-hidden/>기본 구성</span><span><i aria-hidden/>내 구성</span></div>
          </div>
          <section id={chartId} className={s.chart} aria-label={view === "drawdown" ? "고점 대비 하락률 그래프" : "평가액 흐름 그래프"}>
            <p className={s.chartHelp}>{view === "drawdown" ? "선택한 기간의 직전 고점 대비 하락률입니다. 0%에서 멀어질수록 더 크게 하락한 것입니다." : "같은 투자금으로 시작해 매수 후 보유했을 때의 평가액입니다."}</p>
            <PerformanceChart data={data.series} series={[
              {key: "base", label: "기본 구성", dataKey: view === "drawdown" ? "base_drawdown" : "base_value", ...CORE_LINE, dash: "4 3"},
              {key: "personalized", label: "내 구성", dataKey: view === "drawdown" ? "personalized_drawdown" : "personalized_value", ...MY_LINE},
            ]} yFormat={view === "drawdown" ? v => fmtPct(v, 1) : v => `${(v / 10_000).toLocaleString("ko-KR", {maximumFractionDigits: 1})}만원`}
              yAxisWidth={view === "drawdown" ? 56 : 88} height={280} animate={false} curve="linear" connectNulls={false} framed={false} showLegend={false}/>
          </section>
          <p className={s.calculationNote}>매수 후 보유 가정 · 비용·세금 제외 · 정기 리밸런싱 미적용</p>
        </>}
    </section>
    {available && <>
      <section className={s.review} aria-labelledby="rehearsal-review">
        <div><span className={s.reviewEyebrow}>다음으로 살펴볼 것</span><h2 id="rehearsal-review">이 차이가 내 선택 이유와 맞나요?</h2>
          <p>확정 당시 이유: {data.selection_reason || "저장된 이유 없음"}</p>
          <span className={s.reviewHint}>이 기간의 결과와 당시 선택 근거를 함께 검토하세요.</span></div>
        <Link className={s.reviewLink} href={rehearsalHref(data.decision_id, {period, amount}, true)}>기존 판단 검토하기<ArrowUpRight size={16} aria-hidden/></Link>
      </section>
      <div className={s.detailHeading}><span>저장 판단 · {new Date(data.confirmed_at).toLocaleDateString("ko-KR", {timeZone: "Asia/Seoul"})} (한국시간)</span><span>확정 당시 비중으로 비교</span></div>
      <div className={s.details}>
        <details><summary>비교한 자산 비중<ChevronDown size={16} aria-hidden/></summary>
          <div className={s.table}><table><caption>같은 판단에 저장된 두 구성 · 기본 구성은 CORE 계좌와 다를 수 있습니다.</caption><thead><tr><th scope="col">자산</th><th scope="col">기본 구성</th><th scope="col">내 구성</th></tr></thead>
            <tbody>{Array.from(new Set([...Object.keys(data.base!.weights), ...Object.keys(data.personalized!.weights)])).sort().map(id => <tr key={id}><th scope="row">{name(id)}</th><td>{fmtPct(data.base!.weights[id] ?? 0)}</td><td>{fmtPct(data.personalized!.weights[id] ?? 0)}</td></tr>)}</tbody></table></div>
        </details>
        <details><summary>계산 기준과 자료 출처<ChevronDown size={16} aria-hidden/></summary>
          <div className={s.method}>
            <div><h3>계산 방식</h3><p>시작일에 소수 수량으로 매수해 보유한 계산입니다. 정기 리밸런싱·추가 입출금은 없으며 수수료·세금은 제외하고 현금 이자는 0으로 가정합니다. 실제 자동 운용의 월별 리밸런싱과 다릅니다.</p></div>
            <div><h3>해석할 때 유의할 점</h3><p>확정 이후의 선택을 과거에 적용하므로 당시 실행 가능한 전략이었다는 증거가 아닙니다. 연도별 비교는 각 연도 첫 관측일부터 새로 시작합니다. 최대 낙폭은 직전 고점 대비 하락률로, 투자금 대비 최종 손익과 다릅니다.</p></div>
            <div><h3>가격 자료의 한계</h3><p>기존 원화 환산·조정 가격 묶음을 사용합니다. 미국 국채·TIPS는 기존 환헤지 대용가격 관례를 따르며 실제 환헤지 비용을 재현하지 않습니다. 휴장일 등 기존 자료의 전처리를 포함하므로 모든 관측이 해당 자산의 새 거래 가격을 뜻하지는 않습니다.</p></div>
            {data.source && <div><h3>자료 출처</h3><p>{data.source.version}<br/>{fmtDate(data.source.start)} ~ {fmtDate(data.source.end)}<br/>{data.source.source}</p></div>}
          </div>
        </details>
      </div>
    </>}
  </div>;
}
