"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { DataTable } from "@/components/tables/DataTable";
import { ApiError, del, get, post } from "@/lib/api/client";
import type { AuthUser } from "@/lib/api/types";
import { fmtDateTime } from "@/lib/format";

interface SessionRow {
  session_id: string;
  created_at: string;
  last_seen_at: string | null;
  expires_at: string;
  current: boolean;
}

export default function AccountPage() {
  const me = useQuery({
    queryKey: ["me-full"],
    queryFn: () => get<AuthUser>("/api/v1/auth/me"),
  });
  const sessions = useQuery({
    queryKey: ["my-sessions"],
    queryFn: () => get<{ items: SessionRow[] }>("/api/v1/auth/sessions"),
  });
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      await post("/api/v1/auth/change-password", { current_password: cur, new_password: next });
      setMsg("비밀번호가 변경되었습니다. 다른 세션은 로그아웃됩니다.");
      setCur("");
      setNext("");
      sessions.refetch();
    } catch {
      setErr("변경할 수 없습니다. 현재 비밀번호와 새 비밀번호(12자 이상)를 확인해주세요.");
    }
  }

  async function revoke(id: string) {
    await del(`/api/v1/auth/sessions/${id}`);
    sessions.refetch();
  }

  return (
    <AppShell headerTitle="Account">
      <PageHeader title="Account" description="내 계정과 세션을 관리합니다." />
      <div className="flex flex-col gap-[32px]">
        <section>
          <SectionHeader title="Profile" />
          {me.isLoading ? <LoadingSkeleton rows={2} /> : me.isError || !me.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => me.refetch()} />
          ) : (
            <DataTable
              columns={[
                { key: "k", header: "Field", render: (r: { k: string; v: string }) => r.k },
                { key: "v", header: "Value", render: (r) => r.v },
              ]}
              rows={[
                { k: "Email", v: me.data.email },
                { k: "Role", v: me.data.role },
                { k: "Participant", v: me.data.participant_id ?? "—" },
              ]}
              rowKey={(r) => r.k}
            />
          )}
        </section>
        <section>
          <SectionHeader title="Change Password" />
          <form onSubmit={changePassword} className="flex max-w-[480px] flex-col gap-[12px]">
            <input className="input" type="password" autoComplete="current-password"
              placeholder="현재 비밀번호" value={cur} onChange={(e) => setCur(e.target.value)} required />
            <input className="input" type="password" autoComplete="new-password"
              placeholder="새 비밀번호 (12자 이상)" value={next} onChange={(e) => setNext(e.target.value)} required />
            {msg ? <p role="status" className="text-[13px] leading-[20px] text-positive">{msg}</p> : null}
            {err ? <p role="alert" className="text-[13px] leading-[20px] text-negative">{err}</p> : null}
            <button className="btn-secondary w-fit" type="submit">비밀번호 변경</button>
          </form>
        </section>
        <section>
          <SectionHeader title="Sessions" />
          {sessions.isLoading ? <LoadingSkeleton rows={2} /> : !sessions.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => sessions.refetch()} />
          ) : sessions.data.items.length === 0 ? (
            <EmptyState title="활성 세션이 없습니다." />
          ) : (
            <DataTable<SessionRow>
              columns={[
                { key: "s", header: "Session", render: (r) => `${r.session_id.slice(0, 8)}…${r.current ? " (current)" : ""}` },
                { key: "c", header: "Created", render: (r) => fmtDateTime(r.created_at) },
                { key: "e", header: "Expires", render: (r) => fmtDateTime(r.expires_at) },
                {
                  key: "x", header: "", render: (r) =>
                    r.current ? null : (
                      <button className="btn-secondary h-[32px]" onClick={() => revoke(r.session_id)}>
                        Revoke
                      </button>
                    ),
                },
              ]}
              rows={sessions.data.items}
              rowKey={(r) => r.session_id}
            />
          )}
        </section>
      </div>
    </AppShell>
  );
}
