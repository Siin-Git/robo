"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { DataTable } from "@/components/tables/DataTable";
import { get } from "@/lib/api/client";
import { fmtDate } from "@/lib/format";

const SYSTEM_LABELS: Record<string,string> = { benchmark_version:"CORE 버전", theme_universe_version:"테마 버전", benchmark_model_date:"모델 기준일", benchmark_snapshot_date:"CORE 저장일", forward_test_inception_at:"운용 시작일", first_execution_at:"첫 실행일", latest_market_data_date:"최근 시장 가격", latest_valuation_date:"최근 평가일", active_participants:"활성 참여자", pending_orders:"대기 주문" };

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
      <AppShell headerTitle="관리자 운영 현황">
        <PageHeader title="관리자 운영 현황" />
        <EmptyState title="관리자 권한이 필요합니다." hint="관리자 계정으로 로그인하면 운영 기록을 확인할 수 있습니다." />
      </AppShell>
    );
  }

  const kv = (obj: Record<string, unknown> | undefined, keys: string[]) =>
    keys.map((k) => ({ k, v: obj?.[k] }));
  const SYS_KEYS = ["benchmark_version", "theme_universe_version", "benchmark_model_date",
    "benchmark_snapshot_date", "forward_test_inception_at", "first_execution_at",
    "latest_market_data_date", "latest_valuation_date", "active_participants", "pending_orders"];

  return (
    <AppShell headerTitle="관리자 운영 현황">
      <PageHeader title="관리자 운영 현황" description="가격·평가·참여자와 실행 기록을 한곳에서 확인합니다." />
      <p className="admin-tracking-entry"><Link className="btn-primary" href="/admin/tracking">내부 판단 추적 · 자산별 관측과 revision 검토</Link></p>
      <div className="flex flex-col gap-[32px]">
        <section className="ui-panel">
          <SectionHeader title="시스템 상태" />
          {status.isLoading ? <LoadingSkeleton rows={4} /> : status.isError || !status.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => status.refetch()} />
          ) : (
            <DataTable<{ k: string; v: unknown }>
              columns={[
                { key: "k", header: "항목", render: (r) => SYSTEM_LABELS[r.k] ?? r.k },
                { key: "v", header: "현재 값", render: (r) => String(r.v ?? "—") },
              ]}
              rows={kv(status.data, SYS_KEYS)}
              rowKey={(r) => r.k}
            />
          )}
        </section>
        <section className="ui-panel">
          <SectionHeader title="참여자" />
          {users.isLoading ? <LoadingSkeleton rows={3} /> : !users.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => users.refetch()} />
          ) : (
            <DataTable
              columns={[
                { key: "u", header: "계정", render: (r: (typeof users.data.items)[number]) => r.email },
                { key: "r", header: "권한", render: (r) => r.role },
                { key: "s", header: "상태", render: (r) => r.status },
                { key: "p", header: "참여자", render: (r) => r.participant_id ?? "—" },
              ]}
              rows={users.data.items}
              rowKey={(r) => r.user_id}
            />
          )}
        </section>
        <section className="ui-panel">
          <SectionHeader title="대기 중인 주문" />
          {orders.isLoading ? <LoadingSkeleton rows={3} /> : !orders.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => orders.refetch()} />
          ) : orders.data.items.length === 0 ? (
            <EmptyState title="대기 중인 주문이 없습니다." />
          ) : (
            <DataTable
              columns={[
                { key: "o", header: "주문", render: (r: (typeof orders.data.items)[number]) => r.order_id },
                { key: "a", header: "계좌", render: (r) => r.account_id },
                { key: "s", header: "자산", render: (r) => r.asset_id },
                { key: "t", header: "상태", render: (r) => r.status },
              ]}
              rows={orders.data.items}
              rowKey={(r) => r.order_id}
            />
          )}
        </section>
        <section className="ui-panel">
          <SectionHeader title="예약·실행 기록" />
          {jobs.isLoading ? <LoadingSkeleton rows={3} /> : !jobs.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => jobs.refetch()} />
          ) : jobs.data.items.length === 0 ? (
            <EmptyState title="아직 실행 기록이 없습니다." />
          ) : (
            <DataTable
              columns={[
                { key: "j", header: "작업 · 예정일", render: (r: (typeof jobs.data.items)[number]) => `${r.job_type} · ${r.scheduled_for}` },
                { key: "s", header: "상태", render: (r) => r.status },
                { key: "e", header: "오류 내용", render: (r) => r.error_message ?? "—" },
              ]}
              rows={jobs.data.items}
              rowKey={(r) => r.job_id}
            />
          )}
        </section>
        <section className="ui-panel">
          <SectionHeader title="최근 체결" />
          {trades.isLoading ? <LoadingSkeleton rows={3} /> : !trades.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => trades.refetch()} />
          ) : trades.data.items.length === 0 ? (
            <EmptyState title="아직 체결 기록이 없습니다." />
          ) : (
            <DataTable
              columns={[
                { key: "t", header: "체결", render: (r: (typeof trades.data.items)[number]) => r.trade_id },
                { key: "a", header: "계좌", render: (r) => r.account_id },
                { key: "d", header: "체결일", render: (r) => fmtDate(r.execution_at) },
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
