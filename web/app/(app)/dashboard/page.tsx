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

export default function DashboardPage() {
  return DEMO_MODE ? <Suspense fallback={<LoadingSkeleton rows={6}/>}><DashboardRoute/></Suspense> : <LegacyDashboardPage/>;
}

function DashboardRoute() {
  const params = useSearchParams();
  const mode = useComparisonMode();
  if(mode.isLoading)return <LoadingSkeleton rows={6}/>;
  if(mode.isError)return <ErrorState message="비교 설정을 불러오지 못했습니다." onRetry={()=>mode.refetch()}/>;
  return params.get("workspace") === "design" && !mode.data?.market_comparison ? <LegacyDashboardPage/> : <ParticipantPerformance/>;
}

function LegacyDashboardPage() {
  const [period,setPeriod]=useState<Period>("ALL");
  const [example,setExample]=useState(false);
  const [mode,setMode]=useState<"groups"|"assets">("groups");
  const [selected,setSelected]=useState<string|null>(null);
  const query=useQuery({queryKey:["dashboard-performance",period],queryFn:()=>get<Report>(`/api/v1/me/performance/dashboard?period=${period}`),enabled:!example});
  const base = useQuery({queryKey:["base-portfolio"],queryFn:()=>get<{status:string}>("/api/v1/me/base-portfolio")});
  const needsSetup = base.data?.status === "not_selected";
  const hasPortfolio = base.data?.status === "active";
  const report=example?exampleReport(period):query.data;
  const ready=!!report&&report.series.length>1;
  const m=report?.metrics;
  const portfolioHref = DEMO_MODE ? "/portfolio?workspace=design" : "/portfolio";
  return <AppShell headerTitle="포트폴리오 운용 성과" softBackground><div className={s.page}>
    <header className={s.header}><div><span className={s.eyebrow}>PERFORMANCE OVERVIEW</span><h1>포트폴리오 운용 성과</h1><p>확정한 포트폴리오의 모의운용 성과를 CORE와 비교하고, 위험과 수익 기여도를 확인합니다.</p></div><div className="ui-actions"><Link className={s.outlineLink} href={portfolioHref}>내 포트폴리오</Link><Link className="btn-primary" href="/setup/portfolio?step=risk">포트폴리오 설계<ArrowRight size={16}/></Link></div></header>
    <div className={s.toolbar}><div className={s.measurement}><span className={s.statusDot}/>{example?"화면 예시":"설정 이후 모의운용"}<span className={s.date}>{report?.end ? `데이터 기준 ${fmtDate(report.end)}` : "운용 데이터 대기 중"}</span></div><div className={s.periods} role="group" aria-label="성과 조회 기간">{PERIODS.map(p=><button key={p.key} aria-pressed={period===p.key} onClick={()=>{setPeriod(p.key);setSelected(null);}}>{p.label}</button>)}</div></div>
    {example&&<div className={s.exampleBanner} role="status"><Info size={19}/><div><strong>DEMO / EXAMPLE · 가상 데이터</strong><span>확정한 포트폴리오의 성과가 아닙니다. 시연용 가상 데이터이며 랭킹에 반영되지 않습니다.</span></div><button onClick={()=>{setExample(false);setSelected(null);}}>내 모의운용 기록으로 돌아가기</button></div>}
    {!example&&query.isLoading?<LoadingSkeleton rows={6}/>:!example&&query.isError?<ErrorState message="성과 데이터를 불러오지 못했습니다." onRetry={()=>query.refetch()}/>:<>
      {ready && <div className={s.kpis}>
        <Metric label="내 누적수익률" value={fmtReturn(m?.cumulative_return)} hint={ready?`${fmtDate(report?.start)} — ${fmtDate(report?.end)}`:"첫 평가액 이후의 변화"} primary/>
        <Metric label="비교 기준 수익률" value={fmtReturn(m?.benchmark_return)} hint="시스템 기준 CORE · 같은 기간"/>
        <Metric label="기준 대비 차이" value={fmtActivePp(m?.difference_pp)} hint="내 수익률 − CORE 수익률"/>
        <Metric label="최대 낙폭" value={fmtPct(m?.mdd)} hint="선택 기간 고점 대비 최대 하락"/>
      </div>}
      {!ready?<section className={s.empty} aria-label="운용 준비 상태"><div className={s.emptyIcon}><ChartNoAxesCombined size={32}/></div>
        <h2>{needsSetup ? "나의 기본 포트폴리오부터 설계해 보세요" : hasPortfolio ? "포트폴리오는 저장되어 있어요" : "포트폴리오 상태를 확인하고 있어요"}</h2>
        <p>{needsSetup ? "위험 수준 선택 → 투자 인사이트 반영 → 비교 및 확정 순서로 나의 투자 구성을 만듭니다." : hasPortfolio ? <>현재 조회 기간에는 수익률을 표시할 운용 기록이 부족합니다.<br/>다시 설계할 필요 없이 저장된 투자 구성을 먼저 확인할 수 있어요.<br/>모의운용 평가액이 두 날짜 이상 기록되면 성과가 표시됩니다.</> : base.isError ? "저장 상태를 불러오지 못했습니다. 다시 확인해 주세요." : "저장된 투자 구성을 확인한 뒤 다음 단계를 안내합니다."}</p>
        {needsSetup && <Link className="btn-primary" href="/setup/portfolio?step=risk">기본 포트폴리오 설계 시작<ArrowRight size={17}/></Link>}
        {hasPortfolio && <Link className="btn-primary" href={portfolioHref}>저장된 포트폴리오 확인<ArrowRight size={17}/></Link>}
        {base.isError && <button className="btn-secondary" onClick={()=>base.refetch()}>저장 상태 다시 확인</button>}
        <button className="btn-secondary" onClick={()=>setExample(true)}>예시 데이터로 화면 살펴보기<ArrowRight size={17}/></button>
      </section>:<>
        <PerformancePanels styles={s} report={report!} mode={mode} selected={selected} onSelect={setSelected} onMode={value=>{setMode(value);setSelected(null);}} riskPanel={<section className={s.riskSection}><div className={s.sectionHeading}><div><span className={s.eyebrow}>RISK & RETURN</span><h2>수익과 위험 함께 보기</h2><p>{example ? "현재 지표는 시연용 가상 데이터로 계산한 예시입니다." : "선택한 기간의 모의운용 기록으로 계산한 위험 지표입니다."}</p></div></div>
          <div className={s.riskMetrics}><div><span>실현 변동성 · 연율</span><strong>{fmtPct(m?.volatility)}</strong><p>수익률이 얼마나 흔들렸는지</p></div><div><span>최대 낙폭</span><strong>{fmtPct(m?.mdd)}</strong><p>기간 중 가장 크게 하락한 폭</p></div><div><span>기록된 평가일</span><strong>{report!.observations}<small>일</small></strong><p>{fmtDate(report!.start)} — {fmtDate(report!.end)}</p></div></div>
          {m?.volatility==null&&<p className={s.infoNote}>연율 위험 지표는 유효한 수익률 30개 이상이 필요합니다. 누락되거나 오래된 가격이 있는 기간에는 표시하지 않습니다.</p>}
          <details className={s.innerDetails}><summary>평가 지표 더 보기</summary><div className={s.riskMetrics}><div><span>추적오차 · 연율</span><strong>{fmtPct(m?.tracking_error)}</strong><p>CORE와 수익률 차이가 흔들리는 정도</p></div><div><span>정보비율</span><strong>{m?.information_ratio==null?"—":m.information_ratio.toFixed(2)}</strong><p>CORE 대비 초과 성과를 추적오차로 나눈 값</p></div></div><p className={s.infoNote}>샤프 비율은 무위험수익률의 기준을 연결한 뒤 제공합니다.</p></details>
        </section>}/>

        <details className={s.details}><summary>자산별 성과 자세히 보기<span>평균 비중 · 가격 수익률 · 기여도</span></summary><div className={s.tableWrap}><table><thead><tr><th>자산</th><th>평균 비중</th><th>기간 가격 수익률</th><th>수익 기여도</th></tr></thead><tbody>{report!.assets.map(a=><tr key={a.asset_id}><th>{assetName(a.asset_id)}</th><td>{fmtPct(a.average_weight)}</td><td>{fmtReturn(a.price_return)}</td><td>{fmtActivePp(a.contribution)}</td></tr>)}<tr className={s.totalRow}><th>전체 수익률</th><td>—</td><td>—</td><td>{fmtReturn(m?.cumulative_return)}</td></tr></tbody></table></div><p className={s.tableNote}>평균 비중은 기간 중 일수로 가중합니다. 가격 수익률은 시작·종료일의 보유 가격이 모두 있을 때만 표시합니다. 중도 편입·전량 매도 등으로 비교 가격이 없으면 ‘—’로 표시합니다.</p></details>
      </>}
      <details className={s.details}><summary>성과와 기여도는 어떻게 계산하나요?</summary><div className={s.method}>
        <p><strong>성과 기준</strong> 원화 기준 모의운용 평가액을 사용하며, 선택 기간 첫 평가액을 출발점으로 계산합니다. 첫 기록 이전의 손익·비용은 포함하지 않습니다. 입출금이 없는 현재 모의계좌를 기준으로 합니다.</p>
        <p><strong>비교 기준</strong> 시스템 기준 CORE입니다. 고객이 선택한 기본 구성과는 다를 수 있습니다. 같은 시작일과 종료일 기록이 없으면 비교 수익률을 표시하지 않습니다. 내 기본 구성의 별도 운용 이력은 아직 연결되지 않았습니다.</p>
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
