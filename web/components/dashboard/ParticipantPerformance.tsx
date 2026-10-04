"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, SlidersHorizontal } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorState, LoadingSkeleton, MetricCard } from "@/components/shared/ui";
import { PortfolioComparisonTable } from "@/components/portfolio/PortfolioTables";
import { PerformanceChart, MY_LINE, CORE_LINE } from "./PerformanceChart";
import { get, ApiError } from "@/lib/api/client";
import type { Comparison } from "@/lib/api/comparison";
import { themeLabel } from "@/lib/constants";
import { fmtActivePp, fmtDate, fmtNav, fmtPct, fmtReturn } from "@/lib/format";
import { RiskReturnMap, useComparisonAnalytics } from "@/components/performance/ComparisonAnalytics";
import type { ExperimentStatus } from "@/lib/api/experiment";
import { AllocationDonut } from "@/components/portfolio/AllocationDonut";
import { ResetPortfolioButton } from "@/components/portfolio/ResetPortfolioButton";
import s from "./demo.module.css";

export function DemoNote({market = false}: {market?: boolean}) {
  if (market) return <p className={s.note}><span className="ui-badge">과거 가격 비교</span> 현재 비중을 같은 시작일에 투자해 보유했을 때의 비교 결과입니다. 실제 계좌 수익률이나 미래 성과가 아니며, 거래비용·세금은 제외합니다.</p>;
  return <p className={s.note}><span className="ui-badge">DEMO</span> 가상 NAV 기반 시연 데이터 · 실제 운용 실적 아님. Theme 조합에 배정된 시나리오이며 실제 금융 엔진 산출 결과가 아닙니다.</p>;
}

export function ThemeChips({ themes }: { themes: string[] }) {
  return <div className={s.chips}><span className={s.coreChip}>CORE V0.3</span>{themes.map(t => <span key={t} className={s.themeChip}>+ {themeLabel(t)}</span>)}</div>;
}

export function ParticipantPerformance({ participantId, portfolioOnly = false }: { participantId?: string; portfolioOnly?: boolean }) {
  const detail = !!participantId;
  const analytics=useComparisonAnalytics();
  const experiment=useQuery({queryKey:["own-experiment"],queryFn:()=>get<ExperimentStatus>("/api/v1/me/experiment"),enabled:!detail});
  const query = useQuery({
    queryKey: ["comparison", participantId ?? "me"],
    queryFn: () => get<Comparison>(participantId
      ? `/api/v1/participants/${encodeURIComponent(participantId)}/comparison` : "/api/v1/me/comparison"),
  });
  const title = portfolioOnly ? "내 포트폴리오 구성" : detail ? "참여자 상세" : "성과 대시보드";
  const r = query.data;
  const market = r?.data_source === "MARKET_PRICE_REPLAY";
  const compactPortfolio = portfolioOnly && market;
  const compactPerformance = !portfolioOnly && market;
  const myRank = analytics.data?.rankings.return.find(row => row.participant_id === r?.participant_id)?.rank;
  return <AppShell headerTitle={title} softBackground hideDesignNotice={compactPortfolio || compactPerformance}><div className={s.page}>
    {!detail && <p className="ui-note"><strong>시연 비교 데이터</strong> · 실제 forward 운용 기록과 별도입니다. <Link href={portfolioOnly ? "/portfolio" : "/dashboard"}>실제 운용 {portfolioOnly ? "포트폴리오" : "성과"} 보기 →</Link></p>}
    {detail && <Link className={s.back} href="/ranking?source=demo"><ArrowLeft size={15}/>참여자 비교로 돌아가기</Link>}
    {query.isLoading ? <LoadingSkeleton rows={8}/> : query.isError ? <ErrorState
      message={query.error instanceof ApiError && query.error.status === 404 ? "비교할 참여자를 찾을 수 없습니다." : "성과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."}
      onRetry={() => query.refetch()}/> : r && <>
      {compactPortfolio ? <header className={s.portfolioHeader}>
        <div><h1 className="page-title">내 포트폴리오</h1><p className={s.portfolioSubtitle}>선택한 위험 수준과 테마를 반영한 투자 구성이에요.</p>
          <div className={s.portfolioThemes}>{r.themes.length ? r.themes.map(t => <span key={t}>{themeLabel(t)}</span>) : <span>기본 자산배분</span>}</div>
        </div>
        <div className={s.portfolioActions}><Link className="btn-primary" href="/setup/portfolio?step=risk"><SlidersHorizontal size={16}/>구성 변경</Link><Link className="btn-secondary" href="/ranking?source=demo">성과 비교<ArrowRight size={16}/></Link></div>
      </header> : compactPerformance ? <header className={s.portfolioHeader}>
        <div><h1 className="page-title">{detail ? `${r.display_name}의 투자 성과` : "내 투자 성과"}</h1><p className={s.portfolioSubtitle}>{detail ? `${r.themes.map(themeLabel).join(" · ") || "기본 자산배분"} · 기준 포트폴리오와 성과 비교` : "내 포트폴리오와 기준 포트폴리오의 성과를 비교해보세요."}</p></div>
        <div className={s.portfolioActions}>{!detail && <Link className="btn-secondary" href="/portfolio?source=demo">투자 구성 보기</Link>}<Link className="btn-primary" href="/ranking?source=demo">참여자와 비교<ArrowRight size={16}/></Link></div>
      </header> : <header className={s.header}><div><p className="ui-eyebrow">{detail ? "PARTICIPANT DETAIL" : "PERSONAL DASHBOARD"}</p>
        <h1 className="page-title">{r.display_name}<span className={s.titleSuffix}>{portfolioOnly ? "의 투자 구성" : "의 포트폴리오"}</span></h1>
        <p className="page-desc">{market ? "저장한 포트폴리오를 같은 기간의 시장 가격으로 공통 CORE와 비교합니다." : detail ? "선택 View와 해당 가상 시나리오의 성과를 함께 확인합니다." : "같은 CORE, 나만의 View. 내 성과를 기준 포트폴리오와 비교합니다."}</p>
        <ThemeChips themes={r.themes}/></div>
        {!detail && <Link className="btn-primary" href="/ranking?source=demo">참여자 성과 비교<ArrowRight size={16}/></Link>}
      </header>}
      {!compactPortfolio && !compactPerformance && <>
      {r.status!=="awaiting_performance"&&<DemoNote market={market}/>}
      {r.confirmed_at&&<p className="ui-note">구성 저장: {fmtDate(r.confirmed_at.slice(0,10))}{!market&&<> · 실제 Forward Test 시작: 성과 집계 대기{r.scenario_id&&<> · 시연 시나리오 {r.scenario_id}</>}<br/>가입 이전의 NAV는 신규 사용자의 운용 이력이 아닙니다.</>}</p>}
      {market&&<section className="ui-note"><strong>현재 비교에 반영된 구성</strong>{!detail&&<><Link className="btn-secondary" href="/setup/portfolio?step=risk">포트폴리오 재구성</Link>{experiment.data?.can_reset && <ResetPortfolioButton/>}<p>위험 수준과 Theme를 변경하고 저장하면 내 성과와 순위가 함께 갱신됩니다.</p></>}</section>}
      {!detail&&!market&&<p><Link className="btn-secondary" href="/portfolio">저장한 자유 설계 보기</Link></p>}
      {!detail&&!market&&experiment.data?.configuration&&<section className="ui-note"><strong>확정된 실험 구성</strong><p>선택 이유: {experiment.data.configuration.reason}</p><Link className="btn-secondary" href="/setup/portfolio?step=risk">자유 포트폴리오 설계</Link></section>}
      {r.status!=="awaiting_performance"&&<div className={s.period}><span>공통 비교 기간</span><strong>{fmtDate(r.start)} — {fmtDate(r.end)}</strong><span>{r.observations}개 평가일 · NAV 시작값 100</span></div>}
      </>}
      {r.status==="awaiting_performance"&&<section className="ui-panel"><h2>성과 집계 대기</h2><p>선택 조합에 맞는 시연 시나리오가 없습니다. 실제 시작일과 평가 기록이 준비되면 같은 기간끼리 비교합니다. 과거 실적은 소급 생성하지 않습니다.</p></section>}
      {compactPerformance && r.status === "ready" && <>
        <div className={s.performanceMeta}><span>{fmtDate(r.start)} — {fmtDate(r.end)}</span><span>과거 가격 기준 · 실제 운용 성과 아님</span></div>
        <section className={s.performancePanel} aria-label="내 투자 성과 요약">
          <div className="analytics-kpis race-kpis race-summary">
            <div><span>{detail ? "참여자 수익률" : "내 수익률"}</span><strong>{fmtReturn(r.metrics.cumulative_return)}</strong><small>선택한 기간의 누적 성과</small></div>
            <div><span>기준 대비 차이</span><strong>{fmtActivePp(r.metrics.excess_return)}</strong><small>기준 포트폴리오 {fmtReturn(r.metrics.core_return)}</small></div>
            <div><span>{detail ? "참여자 순위" : "내 순위"}</span><strong>{myRank ? `${myRank}위` : "—"}<small> / {analytics.data?.comparable ?? "—"}명</small></strong><small>수익률 높은 순</small></div>
          </div>
          <div className={s.sectionTitle}><div><h2>투자금의 변화</h2><p className="caption">같은 날 100으로 시작했을 때의 평가액</p></div></div>
          <PerformanceChart data={r.series} series={[
            {key:"personal",label:detail ? r.display_name : "내 포트폴리오",...MY_LINE,dataKey:"personalized_nav"},
            {key:"core",label:"기준 포트폴리오 (CORE)",...CORE_LINE,dataKey:"core_nav"},
          ]} height={310} animate={false} curve="linear"/>
        </section>
        <section aria-label="위험 지표"><div className={s.sectionTitle}><h2>투자 기간의 위험</h2></div><div className={s.performanceRisk}>
          <MetricCard label="최대 낙폭" value={fmtPct(r.metrics.mdd)} sub="고점에서 가장 크게 하락한 폭"/>
          <MetricCard label="변동성" value={fmtPct(r.metrics.volatility)} sub="가격이 흔들린 정도 · 연율"/>
          <MetricCard label="위험 대비 수익" value={r.metrics.sharpe?.toFixed(2) ?? "—"} sub="샤프 지수 · 높을수록 효율적"/>
        </div></section>
      </>}
      {!compactPerformance && !portfolioOnly && r.status!=="awaiting_performance" && <>
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
            <div data-metric="sharpe"><MetricCard label="Sharpe" value={r.metrics.sharpe?.toFixed(2) ?? "—"} sub="비교 NAV 기준 · 무위험수익률 0"/></div>
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
      {!portfolioOnly&&r.status!=="awaiting_performance"&&<details className={s.details}><summary>세부 지표와 주간 성과 보기</summary>
        <div className="analytics-kpis">{(["return","mdd","sharpe","excess"] as const).map(b=><div key={b}><span>{({return:"수익률",mdd:"최대 낙폭",sharpe:"위험 대비 수익",excess:"기준 대비"})[b]} 순위</span><strong>{analytics.data?.rankings[b].find(row=>row.participant_id===r.participant_id)?.rank??"—"} / {analytics.data?.comparable??"—"}</strong></div>)}</div>
        <div className="analytics-kpis"><div>추적오차<strong>{fmtPct(r.metrics.tracking_error)}</strong></div><div>정보비율<strong>{r.metrics.information_ratio?.toFixed(2)??"—"}</strong></div></div>
        <h2>최근 데이터 기준 주간</h2>{r.weekly?<><p>기준 주간 {r.weekly.week_start} — {r.weekly.end} · 수익률 출발 평가일 {r.weekly.start} · 현재 달력상의 이번 주가 아닙니다.</p><div className="analytics-kpis"><div>포트폴리오<strong>{fmtReturn(r.weekly.portfolio_return)}</strong></div><div>기준 포트폴리오<strong>{fmtReturn(r.weekly.core_return)}</strong></div><div>기준 대비<strong>{fmtActivePp(r.weekly.excess_return)}</strong></div></div></>:<p>주간 데이터 없음</p>}
        <p className="ui-note">자산·테마별 성과 기여도는 제공하지 않습니다. 테마 선택자들의 평균 성과는 해당 테마의 기여도를 뜻하지 않습니다.</p>
      </details>}
      {detail&&analytics.data&&<RiskReturnMap reports={analytics.data.reports} highlight={r.participant_id} highlightLabel={`선택 참가자 · ${r.display_name}`}/>}
      {(detail || portfolioOnly) ? <section className={s.allocation} aria-label="확정 Personalized Portfolio 구성">
        <div className={s.sectionTitle}><div><h2>{market ? "자산 구성" : "확정 포트폴리오 구성"}</h2><p className="caption">{compactPortfolio ? "자산을 선택하면 투자 비중을 확인할 수 있어요." : market ? "가장 최근에 저장한 목표 비중입니다. 이 비중으로 공통 기간의 가격 비교를 계산합니다." : "공통 CORE의 주식 비중에서 Theme 비중을 조달한 고정 목표 구성입니다. 실제 운용 보유 비중 데이터는 없습니다."}</p></div>{compactPortfolio && r.confirmed_at && <span className={s.savedAt}>{fmtDate(r.confirmed_at.slice(0,10))} 저장</span>}</div>
        <AllocationDonut weights={r.allocation}/>
        <details className={s.details}><summary>공통 CORE와 자산 비중 비교</summary><PortfolioComparisonTable rows={Array.from(new Set([...r.core_allocation, ...r.allocation].map(w => w.asset_id))).map(id => {
          const core = r.core_allocation.find(w => w.asset_id === id)?.weight ?? 0;
          const mine = r.allocation.find(w => w.asset_id === id)?.weight ?? 0;
          return {asset_id:id,core,mine,active:mine-core};
        })}/></details>
      </section> : <Link className={s.detailLink} href={compactPerformance ? "/portfolio?source=demo" : `/participants/${r.participant_id}?source=demo`}>내 투자 구성 자세히 보기<ArrowRight size={16}/></Link>}
      {(compactPortfolio || compactPerformance) && <footer className={s.portfolioFooter}>
        <details className={s.calculationDetails}><summary>계산 기준</summary><div>
          <p>현재 목표 비중을 {fmtDate(r.start)}부터 {fmtDate(r.end)}까지 같은 시장 가격으로 비교합니다. {r.observations}개 평가일 · NAV 시작값 100 · 공통 기준 CORE V0.3.</p>
          <DemoNote market/>
          {compactPerformance && <p>변동성과 샤프 지수는 일별 평가액을 바탕으로 계산합니다. 연율화 252일, 무위험수익률 0을 적용하며, 기준 대비 차이는 반올림 전 수익률로 계산합니다.</p>}
          <p>구성을 변경하고 저장하면 성과와 순위도 갱신됩니다. 주간 투자 의견은 별도로 기록됩니다.</p>
        </div></details>
        {compactPortfolio && experiment.data?.can_reset && <div className={s.resetAction}><ResetPortfolioButton className={s.resetLink}/></div>}
      </footer>}
      {!compactPerformance && !portfolioOnly && r.status!=="awaiting_performance"&&<p className={s.assumption}>Excess는 반올림 전 수익률의 %p 차이입니다. 표시값을 직접 빼면 반올림으로 0.01%p 차이가 날 수 있습니다. Volatility와 Sharpe는 같은 기간의 일별 비교 NAV로 계산하며 연율화 기준은 252일, 무위험수익률은 0입니다. 예상 Sharpe가 아닙니다.</p>}
    </>}
  </div></AppShell>;
}
