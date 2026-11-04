"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LedgerComparison } from "@/components/performance/LedgerComparison";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { RankingTable, type RankingRow } from "@/components/performance/RankingTable";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { get } from "@/lib/api/client";
import type { RankingItem } from "@/lib/api/types";
import { DEMO_MODE } from "@/lib/api/comparison";
import { DemoRanking } from "@/components/performance/DemoRanking";

type Tab = "week" | "cumulative";

export default function RankingPage() {
  return <Suspense fallback={<LoadingSkeleton rows={5}/>}><RankingRoute/></Suspense>;
}

function RankingRoute() {
  const params=useSearchParams();
  return params.get("source")==="demo" ? (DEMO_MODE?<DemoRanking/>:<LegacyRankingPage/>) : <LedgerComparison/>;
}

function LegacyRankingPage() {
  const [tab, setTab] = useState<Tab>("cumulative");
  const [comparison, setComparison] = useState("common_period");
  const rk = useQuery({
    queryKey: ["ranking", tab, comparison],
    queryFn: () =>
      get<{ items: (RankingItem & { cumulative?: number | null; mdd?: number | null; te?: number | null; current_themes?: string[] })[] }>(
        `/api/v1/rankings?period=weekly&basis=${
          tab === "week" ? "active_return" : "cumulative"
        }&comparison=${comparison}`,
      ),
  });

  const rows: RankingRow[] = (rk.data?.items ?? []).map((r) => ({
    ...r,
    display_view: (r.current_themes ?? []).join(", ") || undefined,
    cumulative: (r as { cumulative?: number | null }).cumulative ?? null,
    mdd: (r as { mdd?: number | null }).mdd ?? null,
    te: (r as { te?: number | null }).te ?? null,
  }));

  return (
    <AppShell headerTitle="참여자 성과 비교" softBackground><div className="ranking-page">
      <PageHeader title="참여자 성과 비교" description="참여자가 만든 포트폴리오의 모의운용 성과를 시스템 기준 CORE와 비교합니다." right={<Link className="btn-secondary" href="/dashboard">내 운용 성과</Link>} />
      <div className="ui-note"><strong>비교 기준을 먼저 확인하세요.</strong><br />누적 초과수익률은 CORE 대비 상대 성과이며 포트폴리오 자체의 누적수익률과 다릅니다. 참여자별로 쌓인 모의운용 기록을 비교합니다.</div>
      <div className="ranking-toolbar">
        <div className="flex gap-[4px]" role="group" aria-label="순위 산정 기간">
          {(["week", "cumulative"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={`h-[32px] px-[12px] text-[13px] font-semibold leading-[20px] ${
                tab === t ? "bg-text-primary text-white" : "bg-surface text-text-secondary border border-border"
              }`}
              style={{ borderRadius: 6 }}
            >
              {t === "week" ? "최근 주간" : "누적"}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-[8px] text-[13px] leading-[20px] text-text-secondary">
          기준
          <select
            className="input w-auto"
            value={comparison}
            onChange={(e) => setComparison(e.target.value)}
          >
            <option value="common_period">공통 운용 기간</option>
            <option value="since_inception">각자 운용 시작 이후</option>
          </select>
        </label>
      </div>
      <p className="page-desc">{comparison === "common_period" ? "공통 기간 옵션은 누적 초과수익률의 비교 구간에 적용됩니다. 주간 성과와 위험 지표는 각 기록 기준입니다." : "각 참여자의 기록 기간이 다르므로 수익률과 위험을 해석할 때 운용 기간 차이를 고려하세요."}</p>
      {!rk.isLoading && !rk.isError && rows.length > 0 && rows.every(r => r.active_return == null) && <p className="ui-note mt-[16px]" role="status">아직 비교할 성과 기록이 없습니다. 참여자 목록만 표시하며, 성과가 없는 행의 순위는 ‘대기’로 표시합니다.</p>}
      {rk.isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : rk.isError ? (
        <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => rk.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title="랭킹 데이터가 아직 없습니다." />
      ) : (
        <section className="ui-panel">
          <SectionHeader title={tab === "week" ? "최근 주간" : "누적"} />
          <RankingTable rows={rows} basis={tab} />
        </section>
      )}
      <p className="page-desc mt-[20px]">최대 낙폭은 운용 중 고점 대비 하락 폭, 추적오차는 CORE와 수익률 차이의 변동성입니다. ‘—’는 산출할 기록이 부족한 값입니다.</p>
    </div></AppShell>
  );
}
