"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import {
  CORE_LINE,
  EQUAL_LINE,
  MY_LINE,
  NEUTRAL_LINE,
  PerformanceChart,
} from "@/components/dashboard/PerformanceChart";
import { EmptyState, ErrorState, LoadingSkeleton, MetricCard } from "@/components/shared/ui";
import { get } from "@/lib/api/client";
import type { NavPoint, Performance } from "@/lib/api/types";
import { fmtDate, fmtReturn } from "@/lib/format";
import { DEMO_MODE } from "@/lib/api/comparison";
import { useComparisonMode } from "@/lib/api/use-comparison-mode";
import { ParticipantPerformance } from "@/components/dashboard/ParticipantPerformance";

const PERIODS = [
  { key: "1M", days: 30 },
  { key: "3M", days: 90 },
  { key: "YTD", days: -1 },
  { key: "1Y", days: 365 },
  { key: "ALL", days: 0 },
] as const;

function filterPeriod<T extends { date: string }>(items: T[], days: number): T[] {
  if (days === 0 || items.length === 0) return items;
  const end = new Date(items[items.length - 1].date).getTime();
  let start: number;
  if (days === -1) {
    start = new Date(`${items[items.length - 1].date.slice(0, 4)}-01-01`).getTime();
  } else {
    start = end - days * 86400_000;
  }
  return items.filter((p) => new Date(p.date).getTime() >= start);
}

export function HistoricalPerformancePage() {
  const mode = useComparisonMode();
  if(DEMO_MODE && mode.isLoading)return <LoadingSkeleton rows={6}/>;
  if(DEMO_MODE && mode.isError)return <ErrorState message="비교 설정을 불러오지 못했습니다." onRetry={()=>mode.refetch()}/>;
  return mode.data?.market_comparison ? <ParticipantPerformance/> : <LegacyPerformancePage/>;
}

function LegacyPerformancePage() {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>(PERIODS[4]);
  const perf = useQuery({
    queryKey: ["perf-full"],
    queryFn: () => get<Performance>("/api/v1/me/performance"),
  });
  const nav = useQuery({
    queryKey: ["nav-full"],
    queryFn: () => get<{ items: NavPoint[] }>("/api/v1/me/performance/nav"),
  });
  const bench = useQuery({
    queryKey: ["bench-all"],
    queryFn: async () => {
      const [n, e] = await Promise.all([
        get<{ items: { date: string; nav: number }[] }>(
          "/api/v1/benchmarks/performance?benchmark_version=neutral_60_40"),
        get<{ items: { date: string; nav: number }[] }>(
          "/api/v1/benchmarks/performance?benchmark_version=equal_weight"),
      ]);
      return { neutral: n.items, equal: e.items };
    },
  });

  const m = perf.data?.metrics ?? {};
  const insufficient = perf.data?.status === "INSUFFICIENT_HISTORY";
  const items = filterPeriod(nav.data?.items ?? [], period.days);
  const byDate = (arr: { date: string; nav: number }[]) => {
    const map = new Map(arr.map((p) => [p.date, p.nav]));
    return (d: string) => {
      const v = map.get(d);
      return v == null ? null : v;
    };
  };
  const getN = bench.data ? byDate(bench.data.neutral) : () => null;
  const getE = bench.data ? byDate(bench.data.equal) : () => null;
  const data = items.map((p) => {
    const base = (v: number | null) => (v == null ? null : (v / 100 - 1) * 100);
    const n = getN(p.date);
    const e = getE(p.date);
    const n0 = bench.data && bench.data.neutral.length > 0 ? bench.data.neutral[0].nav : null;
    const e0 = bench.data && bench.data.equal.length > 0 ? bench.data.equal[0].nav : null;
    return {
      date: p.date,
      mine: base(p.personalized_nav),
      core: base(p.core_nav),
      neutral: n == null || n0 == null ? null : (n / n0 - 1) * 100,
      equal: e == null || e0 == null ? null : (e / e0 - 1) * 100,
    };
  });

  return (
    <AppShell headerTitle="Performance">
      <PageHeader title="Performance" description="포트폴리오 성과와 Benchmark 대비 결과입니다." />
      {perf.isLoading || nav.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : perf.isError ? (
        <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => perf.refetch()} />
      ) : items.length < 2 ? (
        <EmptyState title="Forward Test가 아직 시작되지 않았습니다." hint="시작 후 이곳에 실제 성과가 표시됩니다." />
      ) : (
        <>
          <div className="mb-[12px] flex gap-[4px]" role="group" aria-label="Period">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                onClick={() => setPeriod(p)}
                aria-pressed={period.key === p.key}
                className={`h-[32px] px-[12px] text-[13px] font-semibold leading-[20px] ${
                  period.key === p.key
                    ? "bg-text-primary text-white"
                    : "bg-surface text-text-secondary border border-border"
                }`}
                style={{ borderRadius: 6 }}
              >
                {p.key}
              </button>
            ))}
          </div>
          <PerformanceChart
            data={data}
            series={[
              { key: "mine", label: "My Portfolio", color: MY_LINE.color, width: MY_LINE.width, dataKey: "mine" },
              { key: "core", label: "CORE V0.3", color: CORE_LINE.color, width: CORE_LINE.width, dataKey: "core" },
              { key: "neutral", label: "Neutral 60/40", color: NEUTRAL_LINE.color, width: NEUTRAL_LINE.width, dataKey: "neutral" },
              { key: "equal", label: "Equal Weight", color: EQUAL_LINE.color, width: EQUAL_LINE.width, dataKey: "equal" },
            ]}
            height={380}
            yFormat={(v) => `${v.toFixed(1)}%`}
          />
          <div className="mt-[32px]">
            <SectionHeader title="Metrics" />
            <div className="grid grid-cols-2 gap-[16px] lg:grid-cols-3">
              <MetricCard label="Cumulative Return" value={insufficient ? "—" : fmtReturn(m.cumulative_return)} />
              <MetricCard label="Active Return" value={insufficient ? "—" : fmtReturn(m.active_cumulative)} />
              <MetricCard label="Annualized Vol" value={insufficient ? "—" : fmtReturn(m.annualized_volatility)} />
              <MetricCard label="MDD" value={insufficient ? "—" : fmtReturn(m.mdd)} />
              <MetricCard label="Tracking Error" value={insufficient ? "—" : fmtReturn(m.tracking_error)} />
              <MetricCard label="Information Ratio" value={m.information_ratio == null ? "—" : Number(m.information_ratio).toFixed(2)} />
            </div>
            {insufficient ? <p className="caption mt-[8px]">데이터 축적 중</p> : null}
          </div>
          <div className="mt-[32px]">
            <SectionHeader title="Theme Contribution" />
            <ThemeAttribution />
          </div>
        </>
      )}
    </AppShell>
  );
}

function ThemeAttribution() {
  const attr = useQuery({
    queryKey: ["attr"],
    queryFn: () => get<{
      core_return: number | null;
      active_return: number | null;
      transaction_cost: number | null;
      theme_contributions: { theme_id: string; contribution: number }[];
    }>("/api/v1/me/performance/attribution"),
  });
  if (attr.isLoading) return <LoadingSkeleton rows={3} />;
  if (attr.isError || !attr.data) return <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => attr.refetch()} />;
  const rows = [...attr.data.theme_contributions].sort((a, b) => b.contribution - a.contribution);
  if (rows.length === 0) return <EmptyState title="테마 기여도가 아직 없습니다." />;
  const max = Math.max(0.0001, ...rows.map((r) => Math.abs(r.contribution)));
  return (
    <div className="flex flex-col gap-[8px]">
      {rows.map((r) => (
        <div key={r.theme_id} className="grid grid-cols-[140px_1fr_80px] items-center gap-[12px]">
          <span className="truncate text-[13px] leading-[20px]">{r.theme_id}</span>
          <div className="flex h-[8px] justify-center bg-surface-subtle">
            <div
              className="h-[8px]"
              style={{
                width: `${(Math.abs(r.contribution) / max) * 50}%`,
                marginLeft: r.contribution < 0 ? "auto" : undefined,
                marginRight: r.contribution >= 0 ? "auto" : undefined,
                background: r.contribution >= 0 ? "var(--positive)" : "var(--negative)",
              }}
            />
          </div>
          <span className={`tnum text-right text-[13px] font-medium leading-[20px] ${r.contribution >= 0 ? "text-positive" : "text-negative"}`}>
            {fmtReturn(r.contribution)}
          </span>
        </div>
      ))}
    </div>
  );
}
