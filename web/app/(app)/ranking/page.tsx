"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { RankingTable, type RankingRow } from "@/components/performance/RankingTable";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { get } from "@/lib/api/client";
import type { RankingItem } from "@/lib/api/types";

type Tab = "week" | "cumulative";

export default function RankingPage() {
  const [tab, setTab] = useState<Tab>("week");
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
    <AppShell headerTitle="Ranking">
      <PageHeader title="Ranking" description="참가자의 Core 대비 Active 성과를 비교합니다." />
      <div className="mb-[12px] flex flex-wrap items-center gap-[8px]">
        <div className="flex gap-[4px]" role="group" aria-label="Period">
          {(["week", "cumulative"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={`h-[32px] px-[12px] text-[13px] font-semibold leading-[20px] ${
                tab === t ? "bg-text-primary text-white" : "bg-white text-text-secondary border border-border"
              }`}
              style={{ borderRadius: 6 }}
            >
              {t === "week" ? "This Week" : "Cumulative"}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-[8px] text-[13px] leading-[20px] text-text-secondary">
          기준
          <select
            className="input h-[32px] w-auto"
            value={comparison}
            onChange={(e) => setComparison(e.target.value)}
          >
            <option value="common_period">Common Period</option>
            <option value="since_inception">Since Inception</option>
          </select>
        </label>
      </div>
      {rk.isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : rk.isError ? (
        <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => rk.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title="랭킹 데이터가 아직 없습니다." />
      ) : (
        <>
          <SectionHeader title={tab === "week" ? "This Week" : "Cumulative"} />
          <RankingTable rows={rows} />
        </>
      )}
    </AppShell>
  );
}
