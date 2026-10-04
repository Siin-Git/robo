"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, ChartNoAxesCombined, Info } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { get } from "@/lib/api/client";
import { fmtActivePp, fmtDate, fmtPct, fmtReturn } from "@/lib/format";
import { PerformancePanels } from "./performance-panels";
import { Report, Period, PERIODS, exampleReport, assetName } from "./performance-data";
import s from "./dashboard.module.css";
import { DEMO_MODE } from "@/lib/api/comparison";
import { ParticipantPerformance } from "@/components/dashboard/ParticipantPerformance";
import { useComparisonMode } from "@/lib/api/use-comparison-mode";
import { LedgerHistory } from "@/components/dashboard/LedgerHistory";
import { DashboardDecisionContext } from "@/components/dashboard/DashboardDecisionContext";
import { ForwardOperations } from "@/components/dashboard/ForwardOperations";
import { ledgerReason } from "@/lib/api/ledger-comparison";
import { BenchmarkOptions } from '@/components/strategies/BenchmarkOptions';

export default function DashboardPage() {
  return <Suspense fallback={<LoadingSkeleton rows={6}/>}><DashboardRoute/></Suspense>;
}

function DashboardRoute() {
  const params = useSearchParams();
  return DEMO_MODE && params.get("source") === "demo" ? <DemoDashboardPage/> : <LegacyDashboardPage/>;
}

function DemoDashboardPage() {
  const mode = useComparisonMode();
  if(mode.isLoading)return <LoadingSkeleton rows={6}/>;
  if(mode.isError)return <ErrorState message="비교 설정을 불러오지 못했습니다." onRetry={()=>mode.refetch()}/>;
  return <ParticipantPerformance/>;
}

function LegacyDashboardPage() {
  const params=useSearchParams();
  const initialPeriod=params.get("period");
  const [period,setPeriod]=useState<Period>(PERIODS.some(p=>p.key===initialPeriod)?initialPeriod as Period:"ALL");
  const common=params.get("comparison")==="common";
  const [example,setExample]=useState(false);
  const [operationsOpen,setOperationsOpen]=useState(false);
  const [mode,setMode]=useState<"groups"|"assets">("groups");
  const [selected,setSelected]=useState<string|null>(null);
  const query=useQuery({queryKey:["dashboard-performance",period,common],queryFn:()=>get<Report>(`/api/v1/me/performance/dashboard?period=${period}&comparison=${common?"common":"individual"}`),enabled:!example,refetchInterval:15_000});
  const base = useQuery({queryKey:["base-portfolio"],queryFn:()=>get<{status:string}>("/api/v1/me/base-portfolio")});
  const needsSetup = base.data?.status === "not_selected";
  const hasPortfolio = base.data?.status === "selected";
  const report=example?exampleReport(period):query.data;
  const ready=!!report&&report.series.length>1;
  const m=report?.metrics;
  const portfolioHref = "/portfolio";
  return <AppShell headerTitle="포트폴리오 운용 성과" softBackground><div className={s.page}>
    <header className={s.header}><div><span className={s.eyebrow}>MY PORTFOLIO</span><h1>내 투자 성과</h1><p>{report?.replay_context?"선택한 투자 구성이 과거 시장에서 어떻게 움직였는지 살펴보세요.":"내 투자 구성의 변화와 수익에 기여한 자산을 살펴보세요."}</p></div><div className="ui-actions"><Link className={s.outlineLink} href={portfolioHref}>내 포트폴리오</Link><Link className="btn-primary" href="/setup/portfolio?step=risk">포트폴리오 설계<ArrowRight size={16}/></Link></div></header>
    <div className={s.toolbar}><div className={s.measurement}><span className={s.statusDot}/>{example?"화면 예시 · 가상 데이터":report?.replay_context?"과거 가격 모의실험":"모의운용 성과"}<span className={s.date}>{report?.end ? `데이터 기준 ${fmtDate(report.end)}` : "운용 데이터 대기 중"}</span></div><div className={s.periods} role="group" aria-label="성과 조회 기간">{PERIODS.map(p=><button key={p.key} aria-pressed={period===p.key} onClick={()=>{setPeriod(p.key);setSelected(null);}}>{p.label}</button>)}</div></div>
    {!example && report?.valuation && <div className={s.balanceSummary} aria-label="계좌 요약"><span>총 평가액 <strong>{report.valuation.nav_krw.toLocaleString("ko-KR",{maximumFractionDigits:0})}원</strong></span><span>현금 <strong>{report.valuation.cash_krw?.toLocaleString("ko-KR",{maximumFractionDigits:0})??"—"}원</strong></span><a href="#operation-details" onClick={()=>setOperationsOpen(true)}>보유·운용 내역 보기 <ArrowRight size={13}/></a></div>}
    {example&&<div className={s.exampleBanner} role="status"><Info size={19}/><div><strong>DEMO / EXAMPLE · 가상 데이터</strong><span>확정한 포트폴리오의 성과가 아닙니다. 시연용 가상 데이터이며 랭킹에 반영되지 않습니다.</span></div><button onClick={()=>{setExample(false);setSelected(null);}}>내 모의운용 기록으로 돌아가기</button></div>}
    {!example && report?.data_kind === "TEST_FIXTURE" && <p className={`${s.exampleBanner} ${s.fixtureBanner}`} role="status">검증용 합성 데이터 · 실제 운용 기록이 아닙니다. 장기 성과나 발표 실적의 근거로 사용하지 않습니다.</p>}
    {!example&&query.isLoading?<LoadingSkeleton rows={6}/>:!example&&query.isError?<ErrorState message="성과 데이터를 불러오지 못했습니다." onRetry={()=>query.refetch()}/>:<>
      {ready && <div className={s.kpis}>
        <Metric label="내 누적수익률" value={fmtReturn(m?.cumulative_return)} hint={ready?`${fmtDate(report?.start)} — ${fmtDate(report?.end)}`:"첫 평가액 이후의 변화"} primary/>
        <Metric label="비교 기준 수익률" value={fmtReturn(m?.benchmark_return)} hint="시스템 기준 CORE · 같은 기간"/>
        <Metric label="기준 대비 차이" value={fmtActivePp(m?.difference_pp)} hint="내 수익률 − CORE 수익률"/>
        <Metric label="최대 낙폭" value={fmtPct(m?.mdd)} hint={report?.quality.missing_nav_dates ? "관측 기준 · 평가 공백 있음" : "기록된 고점 대비 최대 하락"}/>
      </div>}
      {!ready?<section className={s.empty} aria-label="운용 준비 상태"><div className={s.emptyIcon}><ChartNoAxesCombined size={32}/></div>
        <h2>{needsSetup ? "나의 기본 포트폴리오부터 설계해 보세요" : hasPortfolio ? "포트폴리오는 저장되어 있어요" : "포트폴리오 상태를 확인하고 있어요"}</h2>
        <p>{needsSetup ? "위험 수준 선택 → 투자 인사이트 반영 → 비교 및 확정 순서로 나의 투자 구성을 만듭니다." : hasPortfolio ? <>현재 조회 기간에는 수익률을 표시할 운용 기록이 부족합니다.<br/>다시 설계할 필요 없이 저장된 투자 구성을 먼저 확인할 수 있어요.<br/>모의운용 평가액이 두 날짜 이상 기록되면 성과가 표시됩니다.</> : base.isError ? "저장 상태를 불러오지 못했습니다. 다시 확인해 주세요." : "저장된 투자 구성을 확인한 뒤 다음 단계를 안내합니다."}</p>
        {needsSetup && <Link className="btn-primary" href="/setup/portfolio?step=risk">기본 포트폴리오 설계 시작<ArrowRight size={17}/></Link>}
        {hasPortfolio && <Link className="btn-primary" href={portfolioHref}>저장된 포트폴리오 확인<ArrowRight size={17}/></Link>}
        {base.isError && <button className="btn-secondary" onClick={()=>base.refetch()}>저장 상태 다시 확인</button>}
        <button className="btn-secondary" onClick={()=>setExample(true)}>예시 데이터로 화면 살펴보기<ArrowRight size={17}/></button>
      </section>:<>
        <PerformancePanels styles={s} report={report!} mode={mode} selected={selected} onSelect={setSelected} onMode={value=>{setMode(value);setSelected(null);}} riskPanel={<details className={s.riskDisclosure}><summary>위험 지표 자세히 보기<span>변동성 · 최대 낙폭 · 산출 조건</span></summary><section className={s.riskSection}><div className={s.sectionHeading}><div><span className={s.eyebrow}>RISK & RETURN</span><h2>수익과 위험 함께 보기</h2><p>{example ? "현재 지표는 시연용 가상 데이터로 계산한 예시입니다." : "선택한 기간의 모의운용 기록으로 계산한 위험 지표입니다."}</p></div></div>
          <div className={s.riskMetrics}><div><span>실현 변동성 · 연율</span><strong>{fmtPct(m?.volatility)}</strong><p>수익률이 얼마나 흔들렸는지</p></div><div><span>최대 낙폭</span><strong>{fmtPct(m?.mdd)}</strong><p>유효 평가 2건 이상에서 관측된 최대 하락</p></div><div><span>기록된 평가일</span><strong>{report!.observations}<small>일</small></strong><p>{fmtDate(report!.start)} — {fmtDate(report!.end)}</p></div></div>
          <p className={s.infoNote}>MDD는 관측 기록 기준입니다. 평가 공백에서 발생한 낙폭은 확인할 수 없으며, 연율 변동성과 산출 조건이 다릅니다.</p>{report?.metric_quality?.mdd.reason&&<p className={s.infoNote}>MDD 비교: {ledgerReason(report.metric_quality.mdd.reason)}</p>}
          {m?.volatility==null&&<p className={s.infoNote}>연율 위험 지표는 유효한 수익률 30개 이상이 필요합니다. 누락되거나 오래된 가격이 있는 기간에는 표시하지 않습니다.</p>}
          <details className={s.innerDetails}><summary>평가 지표 더 보기</summary><div className={s.riskMetrics}><div><span>추적오차 · 연율</span><strong>{fmtPct(m?.tracking_error)}</strong><p>CORE와 수익률 차이가 흔들리는 정도</p></div><div><span>정보비율</span><strong>{m?.information_ratio==null?"—":m.information_ratio.toFixed(2)}</strong><p>CORE 대비 초과 성과를 추적오차로 나눈 값</p></div></div><p className={s.infoNote}>샤프 비율은 무위험수익률의 기준을 연결한 뒤 제공합니다.</p></details>
        </section></details>}/>

        <details className={s.details}><summary>자산별 성과 자세히 보기<span>평균 비중 · 가격 수익률 · 기여도</span></summary><div className={s.tableWrap}><table><thead><tr><th>자산</th><th>평균 비중</th><th>기간 가격 수익률</th><th>수익 기여도</th></tr></thead><tbody>{report!.assets.map(a=><tr key={a.asset_id}><th>{assetName(a.asset_id)}</th><td>{fmtPct(a.average_weight)}</td><td>{fmtReturn(a.price_return)}</td><td>{fmtActivePp(a.contribution)}</td></tr>)}<tr className={s.totalRow}><th>전체 수익률</th><td>—</td><td>—</td><td>{fmtReturn(m?.cumulative_return)}</td></tr></tbody></table></div><p className={s.tableNote}>평균 비중은 기간 중 일수로 가중합니다. 가격 수익률은 시작·종료일의 보유 가격이 모두 있을 때만 표시합니다. 중도 편입·전량 매도 등으로 비교 가격이 없으면 ‘—’로 표시합니다.</p></details>
      </>}
      {!example && <details id="operation-details" className={s.details} open={!ready || operationsOpen} onToggle={event=>setOperationsOpen(event.currentTarget.open)}><summary>보유자산·운용 내역<span>현금 · 주문 · 체결 · 리밸런싱</span></summary><div className={s.detailContent}>
    {!example && <ForwardOperations latestValuationDate={query.data?.end ?? null} observations={query.data?.observations ?? null}/>}
    {!example && <LedgerHistory/>}
      </div></details>}
      <details className={s.details}><summary>계산·데이터 상세<span>평가 기준 · 관측 기록 · 비교 조건</span></summary><div className={s.detailContent}>
    {!example && report?.decision_context && !report.replay_context && <DashboardDecisionContext context={report.decision_context} observations={report.observations} start={report.start} end={report.end}/>}
    {!example&&common&&<p className="ui-note" role="status">참여자 비교와 같은 공통 관측 기간 · {report?.comparison_window?.start??"기록 부족"} — {report?.comparison_window?.end??"기록 부족"} · {report?.comparison_window?.status==="UNAVAILABLE"?ledgerReason(report.comparison_window.reason):"같은 시작·종료일과 계산 기준을 사용하며 내부 실제 평가를 보존합니다."} <Link href="/dashboard">내 전체 운용 기간 보기</Link></p>}
    {!example&&report?.valuation&&<section className={s.operations} aria-label="기록된 평가액"><h2>기록된 평가액 · 원화</h2><p>마지막 평가일 {fmtDate(report.valuation.date)} · 총 평가액 {report.valuation.nav_krw.toLocaleString("ko-KR",{maximumFractionDigits:0})}원 · 현금 {report.valuation.cash_krw?.toLocaleString("ko-KR",{maximumFractionDigits:0})??"—"}원</p><p>실제 관측 {fmtDate(report.start)} — {fmtDate(report.end)} · 평가일 {report.observations}개 · 기준 100 지수 {report.valuation.index100.toFixed(2)} (원화 금액과 별도)</p>{report.observations===1&&<p role="status">첫 평가 기록 1건 · 기준점 100만 확인됩니다. 두 번째 평가일 전에는 수익률·변동성·기여도를 계산하지 않습니다.</p>}</section>}
    {!example&&report?.latest_recorded_date&&report.latest_recorded_date!==report.end&&<p className="ui-note" role="status">마지막 원장 평가일 {fmtDate(report.latest_recorded_date)} · 상태 {report.latest_recorded_status}. 불완전한 평가액은 수익률 관측 구간에서 제외합니다.</p>}
    {!example && report?.comparators && <section className={s.operations} aria-label="같은 기간 비교"><h2>같은 관측 기간의 비교 기준</h2><p>{report.start ?? "기록 대기"} — {report.end ?? "기록 대기"}</p><ul>{report.comparators.map(c=><li key={c.key}>{c.label}: {c.status === "AVAILABLE" ? fmtReturn(c.return) : c.reason === "BENCHMARK_DEFINITION_NOT_CONFIGURED" ? "비교 불가 · 기준 포트폴리오 정의 미정" : `비교 불가 · ${c.reason??'같은 기간 데이터 부족'}`}{c.source === "REFERENCE_PRICE_REPLAY_GROSS" && " · 실제 계좌 운용 아님 / 거래비용 제외"}{c.source === 'REVIEWED_REFERENCE_LEVELS'&&<span> · {c.definition?.currency} · 배당 {c.definition?.dividends} · 비용 {c.definition?.costs} · {c.definition_version}</span>}{c.difference!=null&&<span> · 실제 − 기준 {fmtActivePp(c.difference)}</span>}{c.difference_reason&&<span> · 수치 차이 보류: 비용·배당 기준 불일치</span>}</li>)}</ul><BenchmarkOptions/></section>}
      </div><div className={s.method}><p><strong>추가 검토</strong><Link href="/review">최초 예상·실제 검토</Link>{DEMO_MODE && <> · <Link href="/dashboard?source=demo">시연 비교 데이터 보기</Link></>}</p>
        <p><strong>성과 기준</strong> 원화 기준 모의운용 평가액을 사용하며, 선택 기간 첫 평가액을 출발점으로 계산합니다. 첫 기록 이전의 손익·비용은 포함하지 않습니다. 입출금이 없는 현재 모의계좌를 기준으로 합니다.</p>
        <p><strong>비교 기준</strong> 시스템 기준 CORE입니다. 고객이 선택한 기본 구성과는 다를 수 있습니다. 같은 시작일과 종료일 기록이 없으면 비교 수익률을 표시하지 않습니다. 사용자 선택 기본 구성은 가격 자료가 있는 같은 기간에 매수 후 보유 기준으로 비교하며, 실제 계좌 운용이나 거래비용을 포함한 결과는 아닙니다.</p>
        <p><strong>기여도</strong> 자산 평가액 변화에서 순매수 금액을 제외해 손익을 계산한 뒤, 기간 시작 평가액으로 나눠 누적합니다. 거래비용은 별도 표시하며, 합계는 전체 누적수익률과 대조합니다.</p>
        <p><strong>미설명 차이</strong> 보유 내역 누락이나 장부 차이로 자산에 배분할 수 없는 손익입니다. 특정 자산의 수익으로 배분하지 않습니다. 현금은 현재 모의계좌에서 이자를 발생시키지 않습니다.</p>
        {report&&<p><strong>데이터 상태</strong> 미설명 구간 {report.quality.unresolved_intervals}개 · 오래된 가격 평가일 {report.quality.stale_observations}개 · 평일 평가 공백 {report.quality.missing_nav_dates}개</p>}
      </div></details>
      <footer className={s.footer}><div><strong>다른 참여자의 투자 관점과 성과를 비교해 보세요</strong><p>같은 비교 기준으로 참여자별 CORE 대비 성과와 위험을 확인합니다.</p></div><Link href="/ranking">다음: 참여자 성과 비교<ArrowRight size={17}/></Link></footer>
    </>}
  </div></AppShell>;
}
function Metric({label,value,hint,primary=false}:{label:string;value:string;hint:string;primary?:boolean}){
  return <div className={s.metric} data-primary={primary}><span>{label}</span><strong>{value}</strong><p>{hint}</p></div>;
}
