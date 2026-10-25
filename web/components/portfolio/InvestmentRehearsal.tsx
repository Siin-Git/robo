"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api/client";
import { fmtDate, fmtPct, fmtReturn } from "@/lib/format";
import { PerformanceChart, CORE_LINE, MY_LINE } from "@/components/dashboard/PerformanceChart";
import { LoadingSkeleton } from "@/components/shared/ui";
import { ASSET_META } from "@/app/(app)/setup/portfolio/asset-meta";
import { THEME_INFO } from "@/app/(app)/setup/portfolio/theme-content";
import s from "./InvestmentRehearsal.module.css";

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

export function InvestmentRehearsal({ decisionId }: { decisionId: string }) {
  const [period, setPeriod] = useState("all");
  const [amount, setAmount] = useState(10_000_000);
  const [periodOptions, setPeriodOptions] = useState<{id: string; label: string}[]>([{id: "all", label: "전체 자료 기간"}]);
  const query = useQuery({ queryKey: ["investment-rehearsal", decisionId, period, amount],
    queryFn: () => get<Rehearsal>(`/api/v1/me/decisions/${encodeURIComponent(decisionId)}/rehearsal?period=${period}&initial_amount=${amount}`),
    staleTime: 60_000, retry: 1 });
  const data = query.data;
  useEffect(() => { if (data?.periods.length) setPeriodOptions(data.periods); }, [data?.periods]);
  return <div className={s.page}>
    <header><span className={s.eyebrow}>과거 가격으로 비교하는 선택의 차이</span><h1>내 투자 리허설</h1>
      <p>내가 고른 구성이 기본 구성과 얼마나 다르게 움직였을지 살펴보세요.</p></header>
    <div className={s.notice}><strong>확정 비중을 과거에 적용한 가정 계산</strong>
      <p>실제 계좌 성과가 아닙니다. 과거의 최대 낙폭은 앞으로 발생할 최대 손실을 뜻하지 않습니다.</p></div>
    <div className={s.controls}>
      <label>비교 기간<select value={period} onChange={e => setPeriod(e.target.value)}>
        {periodOptions.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select></label>
      <label>가정 투자금<select value={amount} onChange={e => setAmount(Number(e.target.value))}>
        {[1_000_000, 10_000_000, 100_000_000].map(v => <option key={v} value={v}>{won(v)}</option>)}
      </select></label>
      <span>두 구성에 같은 기간과 금액을 적용합니다.</span>
    </div>
    {query.isError ? <div role="alert" className={s.notice}><p>리허설을 불러오지 못했습니다. 선택한 조건의 결과를 다시 조회해 주세요.</p><button className="btn-secondary" onClick={() => query.refetch()}>다시 조회</button></div>
      : query.isLoading || !data ? <LoadingSkeleton rows={5}/> : data.status !== "AVAILABLE" || !data.base || !data.personalized || !data.period ?
        <div role="status" className={s.notice}><strong>비교 자료 미확보</strong><p>{data.reason}</p><button className="btn-secondary" onClick={() => query.refetch()}>다시 조회</button></div> : <>
      <p className={s.context}>저장 판단 · {new Date(data.confirmed_at).toLocaleDateString("ko-KR", {timeZone: "Asia/Seoul"})} (한국시간)<br/>
        비교 기간 · {fmtDate(data.period.start)} ~ {fmtDate(data.period.end)} · {data.period.observations.toLocaleString()}개 관측 · 각 {won(data.initial_amount)}</p>
      <div className={s.metrics} aria-label="두 구성의 과거 가정 계산 결과">
        {([["기본 구성", data.base], ["내 구성", data.personalized]] as const).map(([label, result]) => <section key={label} className={s.card}>
          <h2>{label}</h2><dl><div><dt>마지막 평가액</dt><dd>{won(result.end_value)}</dd></div>
            <div><dt>기간 수익률</dt><dd>{fmtReturn(result.cumulative_return)}</dd></div>
            <div><dt>기간 내 최대 낙폭</dt><dd>{fmtPct(result.max_drawdown)}</dd></div></dl></section>)}
      </div>
      <section className={s.card} aria-labelledby="rehearsal-value"><h2 id="rehearsal-value">같은 투자금의 평가액 흐름</h2>
        <PerformanceChart data={data.series} series={[
          {key: "base", label: "기본 구성", dataKey: "base_value", ...CORE_LINE},
          {key: "personalized", label: "내 구성", dataKey: "personalized_value", ...MY_LINE},
        ]} yFormat={v => `${(v / 10_000).toLocaleString("ko-KR", {maximumFractionDigits: 1})}만원`} yAxisWidth={88} height={300} animate={false} curve="linear" connectNulls={false} framed={false}/>
      </section>
      <section className={s.card} aria-labelledby="rehearsal-drawdown"><h2 id="rehearsal-drawdown">직전 고점에서 얼마나 하락했을까</h2>
        <p>선택한 기간 안에서 앞서 기록한 최고 평가액 대비 하락률입니다. 투자금 대비 손익과는 다릅니다.</p>
        <PerformanceChart data={data.series} series={[
          {key: "base", label: "기본 구성", dataKey: "base_drawdown", ...CORE_LINE},
          {key: "personalized", label: "내 구성", dataKey: "personalized_drawdown", ...MY_LINE},
        ]} yFormat={v => fmtPct(v, 1)} height={260} animate={false} curve="linear" connectNulls={false} framed={false}/>
      </section>
      <details className={s.card}><summary>비교한 비중과 계산 기준</summary>
        <div className={s.table}><table><caption>같은 판단에 저장된 두 구성 · 기본 구성은 CORE 계좌와 다를 수 있습니다.</caption><thead><tr><th scope="col">자산</th><th scope="col">기본 구성</th><th scope="col">내 구성</th></tr></thead>
          <tbody>{Array.from(new Set([...Object.keys(data.base.weights), ...Object.keys(data.personalized.weights)])).sort().map(id => <tr key={id}><th scope="row">{name(id)}</th><td>{fmtPct(data.base!.weights[id] ?? 0)}</td><td>{fmtPct(data.personalized!.weights[id] ?? 0)}</td></tr>)}</tbody></table></div>
        <p>시작일에 소수 수량으로 매수해 보유한 계산입니다. 정기 리밸런싱·추가 입출금은 없으며 수수료·세금은 제외하고 현금 이자는 0으로 가정합니다. 실제 자동 운용의 월별 리밸런싱과 다릅니다.</p>
        <p>확정 이후의 선택을 과거에 적용하므로 당시 실행 가능한 전략이었다는 증거가 아닙니다. 연도별 비교는 각 연도 첫 관측일부터 새로 시작합니다.</p>
        <p>기존 원화 환산·조정 가격 묶음을 사용합니다. 미국 국채·TIPS는 기존 환헤지 대용가격 관례를 따르며 실제 환헤지 비용을 재현하지 않습니다. 휴장일 등 기존 자료의 전처리를 포함하므로 모든 관측이 해당 자산의 새 거래 가격을 뜻하지는 않습니다.</p>
        {data.source && <p>가격 자료: {data.source.version} · {fmtDate(data.source.start)} ~ {fmtDate(data.source.end)}<br/>출처: {data.source.source}</p>}
      </details>
      <section className={s.card}><h2>이 차이가 내 선택 이유와 맞나요?</h2>
        <p>확정 당시 이유: {data.selection_reason || "저장된 이유 없음"}</p>
        <p>이 기간의 수익과 낙폭만으로 유지·변경을 결정하지 말고, 당시 선택 근거와 함께 검토하세요.</p>
        <Link className="btn-secondary" href={`/review?decision_id=${encodeURIComponent(data.decision_id)}`}>기존 판단 검토하기</Link>
      </section>
    </>}
    <Link className="btn-secondary" href="/portfolio">내 포트폴리오로 돌아가기</Link>
  </div>;
}
