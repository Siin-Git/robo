"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { DataTable } from "@/components/tables/DataTable";
import { get } from "@/lib/api/client";
import { fmtDate } from "@/lib/format";

export default function AdminPage() {
  const status = useQuery({ queryKey: ["admin-status"], queryFn: () => get<Record<string, unknown>>("/api/v1/admin/system/status") });
  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => get<{ items: { user_id: string; email: string; role: string; status: string; participant_id: string | null }[] }>("/api/v1/admin/users"),
  });
  const orders = useQuery({
    queryKey: ["admin-orders"],
    queryFn: () => get<{ items: { order_id: string; account_id: string; asset_id: string; side: string; target_weight: number; status: string }[] }>(
      "/api/v1/admin/orders/pending"),
  });
  const trades = useQuery({
    queryKey: ["admin-trades"],
    queryFn: () => get<{ items: { trade_id: string; account_id: string; execution_at: string; execution_price: number; quantity: number }[] }>(
      "/api/v1/admin/trades?limit=20"),
  });
  const jobs = useQuery({
    queryKey: ["admin-jobs"],
    queryFn: () => get<{ items: { job_id: string; job_type: string; scheduled_for: string; status: string; started_at: string | null; completed_at: string | null; error_message: string | null }[] }>(
      "/api/v1/admin/jobs"),
  });

  if (status.isError && (status.error as { status?: number })?.status === 403) {
    return (
      <AppShell headerTitle="Admin">
        <PageHeader title="Admin" />
        <EmptyState title="Access denied." hint="Admin role required." />
      </AppShell>
    );
  }

  const kv = (obj: Record<string, unknown> | undefined, keys: string[]) =>
    keys.map((k) => ({ k, v: obj?.[k] }));
  const SYS_KEYS = ["benchmark_version", "theme_universe_version", "benchmark_model_date",
    "benchmark_snapshot_date", "forward_test_inception_at", "first_execution_at",
    "latest_market_data_date", "latest_valuation_date", "active_participants", "pending_orders"];

  return (
    <AppShell headerTitle="Admin">
      <PageHeader title="Admin" description="Operational overview. Admin role only." />
      <p><Link href="/admin/tracking">내부 판단 추적 · 자산별 관측과 revision 검토</Link></p>
      <div className="flex flex-col gap-[32px]">
        <section>
          <SectionHeader title="System Status" />
          {status.isLoading ? <LoadingSkeleton rows={4} /> : status.isError || !status.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => status.refetch()} />
          ) : (
            <DataTable<{ k: string; v: unknown }>
              columns={[
                { key: "k", header: "Key", render: (r) => r.k },
                { key: "v", header: "Value", render: (r) => String(r.v ?? "—") },
              ]}
              rows={kv(status.data, SYS_KEYS)}
              rowKey={(r) => r.k}
            />
          )}
        </section>
        <section>
          <SectionHeader title="Participants" />
          {users.isLoading ? <LoadingSkeleton rows={3} /> : !users.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => users.refetch()} />
          ) : (
            <DataTable
              columns={[
                { key: "u", header: "User", render: (r: (typeof users.data.items)[number]) => r.email },
                { key: "r", header: "Role", render: (r) => r.role },
                { key: "s", header: "Status", render: (r) => r.status },
                { key: "p", header: "Participant", render: (r) => r.participant_id ?? "—" },
              ]}
              rows={users.data.items}
              rowKey={(r) => r.user_id}
            />
          )}
        </section>
        <section>
          <SectionHeader title="Pending Orders" />
          {orders.isLoading ? <LoadingSkeleton rows={3} /> : !orders.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => orders.refetch()} />
          ) : orders.data.items.length === 0 ? (
            <EmptyState title="No pending orders." />
          ) : (
            <DataTable
              columns={[
                { key: "o", header: "Order", render: (r: (typeof orders.data.items)[number]) => r.order_id },
                { key: "a", header: "Account", render: (r) => r.account_id },
                { key: "s", header: "Asset", render: (r) => r.asset_id },
                { key: "t", header: "Status", render: (r) => r.status },
              ]}
              rows={orders.data.items}
              rowKey={(r) => r.order_id}
            />
          )}
        </section>
        <section>
          <SectionHeader title="Scheduled Jobs" />
          {jobs.isLoading ? <LoadingSkeleton rows={3} /> : !jobs.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => jobs.refetch()} />
          ) : jobs.data.items.length === 0 ? (
            <EmptyState title="No job runs recorded yet." />
          ) : (
            <DataTable
              columns={[
                { key: "j", header: "Job", render: (r: (typeof jobs.data.items)[number]) => `${r.job_type} · ${r.scheduled_for}` },
                { key: "s", header: "Status", render: (r) => r.status },
                { key: "e", header: "Error", render: (r) => r.error_message ?? "—" },
              ]}
              rows={jobs.data.items}
              rowKey={(r) => r.job_id}
            />
          )}
        </section>
        <section>
          <SectionHeader title="Recent Trades" />
          {trades.isLoading ? <LoadingSkeleton rows={3} /> : !trades.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => trades.refetch()} />
          ) : trades.data.items.length === 0 ? (
            <EmptyState title="No trades yet." />
          ) : (
            <DataTable
              columns={[
                { key: "t", header: "Trade", render: (r: (typeof trades.data.items)[number]) => r.trade_id },
                { key: "a", header: "Account", render: (r) => r.account_id },
                { key: "d", header: "Date", render: (r) => fmtDate(r.execution_at) },
              ]}
              rows={trades.data.items}
              rowKey={(r) => r.trade_id}
            />
          )}
        </section>
      </div>
    </AppShell>
  );
}
