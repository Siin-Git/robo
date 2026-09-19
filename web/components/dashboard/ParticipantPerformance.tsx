"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorState, LoadingSkeleton, MetricCard } from "@/components/shared/ui";
import { AllocationBars, PortfolioComparisonTable } from "@/components/portfolio/PortfolioTables";
import { PerformanceChart, MY_LINE, CORE_LINE } from "./PerformanceChart";
import { get, ApiError } from "@/lib/api/client";
import type { Comparison } from "@/lib/api/comparison";
import { themeLabel } from "@/lib/constants";
import { fmtActivePp, fmtDate, fmtNav, fmtPct, fmtReturn } from "@/lib/format";
import s from "./demo.module.css";

export function DemoNote() {
  return <p className={s.note}><span className="ui-badge">DEMO</span> 시연용 가상 NAV · 실제 Forward Test 실적이 아닙니다. 동일 CORE에서 View별 성과를 비교하는 실험 구조를 보여줍니다.</p>;
}

export function ThemeChips({ themes }: { themes: string[] }) {
  return <div className={s.chips}><span className={s.coreChip}>CORE V0.3</span>{themes.map(t => <span key={t} className={s.themeChip}>+ {themeLabel(t)}</span>)}</div>;
}

export function ParticipantPerformance({ participantId, portfolioOnly = false }: { participantId?: string; portfolioOnly?: boolean }) {
  const detail = !!participantId;
  const query = useQuery({
    queryKey: ["comparison", participantId ?? "me"],
    queryFn: () => get<Comparison>(participantId
      ? `/api/v1/participants/${encodeURIComponent(participantId)}/comparison` : "/api/v1/me/comparison"),
  });
  const title = portfolioOnly ? "내 포트폴리오 구성" : detail ? "참여자 상세" : "내 포트폴리오 성과";
  const r = query.data;
  return <AppShell headerTitle={title} softBackground><div className={s.page}>
    {detail && <Link className={s.back} href="/ranking"><ArrowLeft size={15}/>참여자 비교로 돌아가기</Link>}
    {query.isLoading ? <LoadingSkeleton rows={8}/> : query.isError ? <ErrorState
      message={query.error instanceof ApiError && query.error.status === 404 ? "비교할 참여자를 찾을 수 없습니다." : "시연 데이터를 불러오지 못했습니다. 데모 서버와 seed 실행을 확인해 주세요."}
      onRetry={() => query.refetch()}/> : r && <>
      <header className={s.header}><div><p className="ui-eyebrow">{detail ? "PARTICIPANT DETAIL" : "PERSONAL DASHBOARD"}</p>
        <h1 className="page-title">{r.display_name}<span className={s.titleSuffix}>{portfolioOnly ? "의 투자 구성" : "의 포트폴리오"}</span></h1>
        <p className="page-desc">{detail ? "어떤 View가 어떤 성과로 이어졌는지 살펴봅니다." : "같은 CORE, 나만의 View. 내 성과를 기준 포트폴리오와 비교합니다."}</p>
        <ThemeChips themes={r.themes}/></div>
        {!detail && <Link className="btn-primary" href="/ranking">13명 성과 비교<ArrowRight size={16}/></Link>}
      </header>
      <DemoNote/>
      <div className={s.period}><span>공통 비교 기간</span><strong>{fmtDate(r.start)} — {fmtDate(r.end)}</strong><span>{r.observations}개 평가일 · NAV 시작값 100</span></div>
      {!portfolioOnly && <>
        <section aria-label="Return" className={s.section}>
          <div className={s.sectionTitle}><h2>Return <span>수익 성과</span></h2></div>
          <div className={s.returnGrid}>
            <div data-metric="nav"><MetricCard label="Portfolio NAV" value={fmtNav(r.metrics.nav)} sub="시작값 100 기준"/></div>
            <div data-metric="cumulative_return"><MetricCard label="Cumulative Return" value={fmtReturn(r.metrics.cumulative_return)} sub="내 포트폴리오 누적수익률"/></div>
            <div data-metric="core_return"><MetricCard label="CORE Return" value={fmtReturn(r.metrics.core_return)} sub="13명 모두 동일한 비교 기준"/></div>
            <div data-metric="excess_return" className={s.excess}><MetricCard label="Excess Return" value={fmtActivePp(r.metrics.excess_return)} sub="내 수익률 − CORE 수익률" tone={r.metrics.excess_return >= 0 ? "positive" : "negative"}/></div>
          </div>
        </section>
        <div className={s.riskGroups}>
          <section aria-label="Risk"><div className={s.sectionTitle}><h2>Risk <span>위험</span></h2></div><div className={s.riskGrid}>
            <div data-metric="mdd"><MetricCard label="MDD" value={fmtPct(r.metrics.mdd)} sub="최대 낙폭 · 0에 가까울수록 작음"/></div>
            <div data-metric="volatility"><MetricCard label="Volatility" value={fmtPct(r.metrics.volatility)} sub="실현 변동성 · 연율"/></div>
          </div></section>
          <section aria-label="Risk-adjusted"><div className={s.sectionTitle}><h2>Risk-adjusted <span>위험 대비 수익</span></h2></div>
            <div data-metric="sharpe"><MetricCard label="Sharpe" value={r.metrics.sharpe?.toFixed(2) ?? "—"} sub="가상 NAV 기준 실현값 · 무위험수익률 0"/></div>
          </section>
        </div>
        <section className={s.section} aria-label="Personalized Portfolio vs CORE NAV">
          <div className={s.sectionTitle}><div><h2>Personalized Portfolio vs CORE</h2><p className="caption">동일한 100에서 시작한 평가액의 변화</p></div><span className="ui-badge">NAV</span></div>
          <PerformanceChart data={r.series} series={[
            {key:"personal",label:r.display_name,...MY_LINE,dataKey:"personalized_nav"},
            {key:"core",label:"CORE V0.3",...CORE_LINE,dataKey:"core_nav"},
          ]} height={310} animate={false} curve="linear"/>
        </section>
      </>}
      {(detail || portfolioOnly) ? <section className={s.allocation} aria-label="현재 Personalized Portfolio 구성">
        <div className={s.sectionTitle}><div><h2>현재 Personalized Portfolio 구성</h2><p className="caption">공통 CORE의 주식 비중에서 테마 비중을 조달한 시연용 고정 구성입니다.</p></div></div>
        <AllocationBars weights={r.allocation.filter(w => w.weight > 0)}/>
        <details className={s.details}><summary>공통 CORE와 자산 비중 비교</summary><PortfolioComparisonTable rows={Array.from(new Set([...r.core_allocation, ...r.allocation].map(w => w.asset_id))).map(id => {
          const core = r.core_allocation.find(w => w.asset_id === id)?.weight ?? 0;
          const mine = r.allocation.find(w => w.asset_id === id)?.weight ?? 0;
          return {asset_id:id,core,mine,active:mine-core};
        })}/></details>
      </section> : <Link className={s.detailLink} href={`/participants/${r.participant_id}`}>내 Theme와 포트폴리오 구성 자세히 보기<ArrowRight size={16}/></Link>}
      <p className={s.assumption}>Excess는 반올림 전 수익률의 %p 차이입니다. 표시값을 직접 빼면 반올림으로 0.01%p 차이가 날 수 있습니다. Volatility와 Sharpe는 같은 기간의 일별 가상 NAV로 계산하며 연율화 기준은 252일, 무위험수익률은 0입니다. 예상 Sharpe가 아닙니다.</p>
    </>}
  </div></AppShell>;
}
