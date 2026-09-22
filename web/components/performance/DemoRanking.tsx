"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { useCurrentUser } from "@/components/layout/AppSidebar";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { DemoNote } from "@/components/dashboard/ParticipantPerformance";
import { get } from "@/lib/api/client";
import type { ComparisonRanking, ComparisonRow, RankingBasis } from "@/lib/api/comparison";
import { LAB_MEETING_MODE, COMPARISON_REFRESH_MS } from "@/lib/api/comparison";
import { fmtActivePp, fmtDate, fmtPct, fmtReturn } from "@/lib/format";
import { themeLabel } from "@/lib/constants";
import { AnalyticsOverview, ThemeComparison, useComparisonAnalytics } from "./ComparisonAnalytics";
import s from "./demo-ranking.module.css";

const OPTIONS: {value:RankingBasis;label:string;hint:string}[] = [
  {value:"return",label:"수익률 높은 순",hint:"누적수익률이 높은 순서입니다."},
  {value:"excess",label:"기준 대비 수익률 높은 순",hint:"개인 수익률에서 기준 수익률을 뺀 차이입니다(%p). 공통 기준을 사용하므로 수익률 순위와 같습니다."},
  {value:"mdd",label:"최대 낙폭 작은 순",hint:"MDD는 음수로 표시합니다. 0에 가까울수록 낙폭이 작습니다."},
  {value:"volatility",label:"변동성 낮은 순",hint:"같은 기간의 실현 변동성이 낮은 순서입니다."},
  {value:"sharpe",label:"위험 대비 수익 높은 순",hint:"비교 NAV 기준 Sharpe입니다. 무위험수익률 0, 연율화 252일을 적용합니다."},
  {value:"te",label:"추적오차 낮은 순",hint:"같은 기간의 일별 초과수익률 변동성 · 연율"},
  {value:"ir",label:"정보비율 높은 순",hint:"기준 포트폴리오 대비 상대 수익의 일관성을 비교합니다."},
];

export function DemoRanking() {
  const [basis,setBasis] = useState<RankingBasis>("return");
  const user = useCurrentUser();
  const analytics = useComparisonAnalytics();
  const router = useRouter();
  const query = useQuery({queryKey:["comparison-ranking",basis],queryFn:()=>get<ComparisonRanking>(`/api/v1/comparison/rankings?basis=${basis}`),refetchInterval:COMPARISON_REFRESH_MS});
  const rows = query.data?.items ?? [];
  const selectedValue=(r:ComparisonRow)=>({return:fmtReturn(r.metrics.cumulative_return),excess:fmtActivePp(r.metrics.excess_return),mdd:fmtPct(r.metrics.mdd),volatility:fmtPct(r.metrics.volatility),sharpe:r.metrics.sharpe?.toFixed(2)??"—",te:fmtPct(r.metrics.tracking_error),ir:r.metrics.information_ratio?.toFixed(2)??"—"})[basis];
  const metricColumn = (key: RankingBasis, label: string, format: (row:ComparisonRow)=>string): Column<ComparisonRow> => ({
    key, header:label,numeric:true,ariaSort:basis === key ? (key === "volatility" || key === "te") ? "ascending" : "descending" : undefined,
    render:r=><span className={`${key === "return" || key === "excess" ? s.primaryMetric : s.secondaryMetric} ${basis === key ? s.selectedMetric : ""}`}>{format(r)}</span>,
  });
  const columns:Column<ComparisonRow>[] = [
    {key:"rank",header:"순위",numeric:true,render:r=><span className={r.rank <= 3 ? s.topRank : s.rank}>{String(r.rank).padStart(2,"0")}</span>},
    {key:"participant",header:"참여자",render:r=><div><Link href={`/participants/${r.participant_id}`} className={s.person} onClick={e=>e.stopPropagation()}>{r.display_name}{user?.participant_id === r.participant_id && <small>나</small>}<ArrowUpRight size={14}/></Link><span className={s.mobileMetric}>{basis.toUpperCase()} {selectedValue(r)}</span></div>},
    {key:"themes",header:"선택 테마",render:r=><span className={s.themes}>{r.themes.map(theme=><span className={s.themeChip} key={theme}>{themeLabel(theme)}</span>)}</span>},
    ...(["return", "excess"].includes(basis) ? [
      metricColumn("return","수익률",r=>fmtReturn(r.metrics.cumulative_return)),
      metricColumn("excess","기준 대비",r=>fmtActivePp(r.metrics.excess_return)),
    ] : ["mdd", "volatility"].includes(basis) ? [
      metricColumn("mdd","최대 낙폭",r=>fmtPct(r.metrics.mdd)),
      metricColumn("volatility","변동성",r=>fmtPct(r.metrics.volatility)),
    ] : [
      metricColumn("sharpe","Sharpe",r=>r.metrics.sharpe?.toFixed(2) ?? "—"),
      metricColumn("te","TE",r=>fmtPct(r.metrics.tracking_error)),
      metricColumn("ir","IR",r=>r.metrics.information_ratio?.toFixed(2) ?? "—"),
    ]),
  ];
  return <AppShell headerTitle="참여자 성과 비교" softBackground><div className={s.page}>
    <header className={s.header}><div><h1 className="page-title">참여자 성과 비교</h1><p className="page-desc">내 투자 구성이 다른 참여자, 기준 포트폴리오와 얼마나 달랐는지 확인하세요.</p></div><Link href="/dashboard" className="btn-secondary">내 성과 자세히</Link></header>
    <div className={s.comparisonMeta}><span>{fmtDate(query.data?.start)} — {fmtDate(query.data?.end)}</span><span>{query.data?.total ?? "—"}명 비교</span><span>{query.data?.data_source === "MARKET_PRICE_REPLAY" ? "과거 가격 기준 · 실제 운용 성과 아님" : "가상 시연 데이터 · 실제 운용 성과 아님"}</span></div>
    {LAB_MEETING_MODE && <div className="ui-note" role="status"><strong>구성 완료 {query.data?.registered ?? "—"} / {query.data?.capacity ?? 13}명</strong><span> · 선택 중 {query.data?.reserved ?? "—"}명 · 10초마다 자동 갱신</span><p>저장한 포트폴리오만 순위에 반영됩니다. <Link href="/setup/portfolio">내 섹터·테마 선택하기 →</Link></p></div>}
    <AnalyticsOverview participantId={user?.participant_id??undefined}/>
    <section className={s.panel} aria-label="순위표">
      <div className={s.toolbar}><div><h2>참여자 순위 <span>{query.data?.total ?? "—"}명</span></h2><p>참여자를 선택하면 상세 성과와 투자 구성을 볼 수 있습니다.</p></div><label>정렬 기준<span className={s.selectWrap}><select className="input" value={basis} onChange={e=>setBasis(e.target.value as RankingBasis)}>
        <optgroup label="수익">{OPTIONS.slice(0,2).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>
        <optgroup label="위험">{OPTIONS.slice(2,4).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>
        <optgroup label="위험 대비 수익">{OPTIONS.slice(4).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>
      </select><ChevronDown size={16} aria-hidden="true"/></span></label></div>
      <p className={s.sortHint} aria-live="polite">{OPTIONS.find(o=>o.value===basis)?.hint}</p>
      {query.isLoading ? <LoadingSkeleton rows={13}/> : query.isError ? <ErrorState message="참여자 비교 데이터를 불러오지 못했습니다." onRetry={()=>query.refetch()}/> : !rows.length ? <EmptyState title="아직 비교할 참여자가 없습니다."/> :
        <DataTable columns={columns} rows={rows} rowKey={r=>r.participant_id} onRowClick={r=>router.push(`/participants/${r.participant_id}`)} rowClassName={r=>`${s.row} ${r.rank<=3?s.topRow:""} ${r.participant_id===user?.participant_id?"analytics-my-row":""}`}/>}
      <p className={s.footnote}>현재 정렬 기준의 Top 3를 강조합니다. 전체 지표와 구성은 참여자 상세에서 확인하세요.</p>
    </section>
    {query.data?.pending?.length ? <section className="ui-note"><h2>성과 집계 대기 · 전체 기간 순위 제외</h2>{query.data.pending.map(p=><p key={p.participant_id}><Link href={`/participants/${p.participant_id}`}>{p.display_name} · {p.themes.map(themeLabel).join(" / ")}</Link></p>)}</section>:null}
    {analytics.data&&<ThemeComparison data={analytics.data}/>}
    <details className={s.guide}><summary>비교 기준과 지표 설명</summary>
      <DemoNote market={query.data?.data_source === "MARKET_PRICE_REPLAY"}/>
      <dl><div><dt>수익</dt><dd>누적수익률 · Excess는 CORE 대비 %p 차이</dd></div><div><dt>위험</dt><dd>MDD는 최대 낙폭 · Volatility는 연율 변동성</dd></div><div><dt>위험 대비 수익</dt><dd>Sharpe는 NAV 기준 실현 위험 대비 수익</dd></div></dl>
      <p>보기는 정렬 지표에 따라 수익 / 위험 / 위험조정·상대성과로 전환됩니다. 동률은 같은 순위 · 반올림 전 값 기준</p>
    </details>
  </div></AppShell>;
}
