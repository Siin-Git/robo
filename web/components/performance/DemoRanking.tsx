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
import { fmtActivePp, fmtDate, fmtPct, fmtReturn } from "@/lib/format";
import { themeLabel } from "@/lib/constants";
import s from "./demo-ranking.module.css";

const OPTIONS: {value:RankingBasis;label:string;hint:string}[] = [
  {value:"return",label:"Return · 수익률 높은 순",hint:"누적수익률이 높은 순서입니다."},
  {value:"excess",label:"Excess · 초과수익률 높은 순",hint:"개인 수익률 − CORE 수익률의 %p 차이입니다. 같은 CORE이므로 Return과 순위가 같습니다."},
  {value:"mdd",label:"MDD · 최대 낙폭 작은 순",hint:"MDD는 음수로 표시합니다. 0에 가까울수록 낙폭이 작습니다."},
  {value:"volatility",label:"Volatility · 변동성 낮은 순",hint:"같은 기간의 실현 변동성이 낮은 순서입니다."},
  {value:"sharpe",label:"Sharpe · 위험 대비 수익 높은 순",hint:"가상 NAV 기준 실현 Sharpe입니다. 무위험수익률 0, 연율화 252일을 적용합니다."},
];

export function DemoRanking() {
  const [basis,setBasis] = useState<RankingBasis>("return");
  const user = useCurrentUser();
  const router = useRouter();
  const query = useQuery({queryKey:["comparison-ranking",basis],queryFn:()=>get<ComparisonRanking>(`/api/v1/comparison/rankings?basis=${basis}`)});
  const rows = query.data?.items ?? [];
  const metricColumn = (key: RankingBasis, label: string, format: (row:ComparisonRow)=>string): Column<ComparisonRow> => ({
    key, header:label,numeric:true,ariaSort:basis === key ? key === "volatility" ? "ascending" : "descending" : undefined,
    render:r=><span className={`${key === "return" || key === "excess" ? s.primaryMetric : s.secondaryMetric} ${basis === key ? s.selectedMetric : ""}`}>{format(r)}</span>,
  });
  const columns:Column<ComparisonRow>[] = [
    {key:"rank",header:"Rank",numeric:true,render:r=><span className={r.rank <= 3 ? s.topRank : s.rank}>{String(r.rank).padStart(2,"0")}</span>},
    {key:"participant",header:"Participant",render:r=><Link href={`/participants/${r.participant_id}`} className={s.person} onClick={e=>e.stopPropagation()}>{r.display_name}{user?.participant_id === r.participant_id && <small>ME</small>}<ArrowUpRight size={14}/></Link>},
    {key:"themes",header:"Views",render:r=><span className={s.themes}>{r.themes.map(theme=><span className={s.themeChip} key={theme}>{themeLabel(theme)}</span>)}</span>},
    metricColumn("return","Return",r=>fmtReturn(r.metrics.cumulative_return)),
    metricColumn("excess","Excess",r=>fmtActivePp(r.metrics.excess_return)),
    metricColumn("mdd","MDD",r=>fmtPct(r.metrics.mdd)),
    ...(basis === "volatility" ? [metricColumn("volatility","Volatility",r=>fmtPct(r.metrics.volatility))] : []),
    metricColumn("sharpe","Sharpe",r=>r.metrics.sharpe?.toFixed(2) ?? "—"),
  ];
  return <AppShell headerTitle="참여자 성과 비교" softBackground><div className={s.page}>
    <header className={s.header}><div><p className="ui-eyebrow">SAME CORE · DIFFERENT VIEWS</p><h1 className="page-title">Forward Test Ranking</h1><p className="page-desc">같은 CORE에서 시작한 13명, 서로 다른 View가 만든 성과를 비교합니다.</p></div><Link href="/dashboard" className="btn-secondary">내 성과 보기</Link></header>
    <DemoNote/>
    <section className={s.context} aria-label="공통 실험 조건">
      <div className={s.conditions}>
        <span><strong>{query.data?.total ?? 13}</strong> Participants</span>
        <span><strong>Same CORE</strong><small>V0.3</small></span>
        <span>Max <strong>2</strong> Views</span>
        <span>NAV <strong>100</strong><small>공통 시작값</small></span>
      </div>
      <div className={s.benchmark}><div><span>CORE Benchmark Return</span><small>{fmtDate(query.data?.start)} — {fmtDate(query.data?.end)}</small></div><strong>{rows.length ? fmtReturn(rows[0].metrics.core_return) : "—"}</strong></div>
    </section>
    <section className={s.panel}>
      <div className={s.toolbar}><div><h2>참여자 비교 <span>{query.data?.total ?? 13}명</span></h2><p>참여자를 선택하면 상세 성과와 투자 구성을 볼 수 있습니다.</p></div><label>정렬 기준<span className={s.selectWrap}><select className="input" value={basis} onChange={e=>setBasis(e.target.value as RankingBasis)}>
        <optgroup label="Return · 수익">{OPTIONS.slice(0,2).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>
        <optgroup label="Risk · 위험">{OPTIONS.slice(2,4).map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</optgroup>
        <optgroup label="Risk-adjusted · 위험 대비 수익"><option value="sharpe">{OPTIONS[4].label}</option></optgroup>
      </select><ChevronDown size={16} aria-hidden="true"/></span></label></div>
      <p className={s.sortHint} aria-live="polite">{OPTIONS.find(o=>o.value===basis)?.hint}</p>
      {query.isLoading ? <LoadingSkeleton rows={13}/> : query.isError ? <ErrorState message="참여자 비교 데이터를 불러오지 못했습니다." onRetry={()=>query.refetch()}/> : !rows.length ? <EmptyState title="참여자 seed가 필요합니다."/> :
        <DataTable columns={columns} rows={rows} rowKey={r=>r.participant_id} onRowClick={r=>router.push(`/participants/${r.participant_id}`)} rowClassName={r=>`${s.row} ${r.rank<=3?s.topRow:""}`}/>}
      <p className={s.footnote}>현재 정렬 기준의 Top 3를 강조합니다. 전체 지표와 구성은 참여자 상세에서 확인하세요.</p>
    </section>
    <footer className={s.guide}>
      <dl><div><dt>Return</dt><dd>누적수익률 · Excess는 CORE 대비 %p 차이</dd></div><div><dt>Risk</dt><dd>MDD는 최대 낙폭 · Volatility는 연율 변동성</dd></div><div><dt>Risk-adjusted</dt><dd>Sharpe는 NAV 기준 실현 위험 대비 수익</dd></div></dl>
      <p>Volatility는 해당 정렬 시 표시 · 계산과 정렬은 반올림 전 값 기준</p>
    </footer>
  </div></AppShell>;
}
