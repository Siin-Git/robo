"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader, SectionHeader } from "@/components/layout/AppHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { ThemeSelector } from "@/components/views/ThemeSelector";
import { ApiError, post } from "@/lib/api/client";
import { get } from "@/lib/api/client";
import type { Theme, View } from "@/lib/api/types";
import { THEME_LABELS } from "@/lib/constants";
import { fmtDate } from "@/lib/format";

const viewStatus: Record<string, string> = {new: "신규 의견", hold: "유지 의견", closed: "종료"};
const executionStatus: Record<string, string> = {PENDING: "체결 대기", EXECUTED: "체결 기록 있음"};

export default function ViewsPage() {
  const themesActive = useQuery({
    queryKey: ["themes-active"],
    queryFn: () => get<{ items: Theme[] }>("/api/v1/themes?active=true"),
  });
  const themesInactive = useQuery({
    queryKey: ["themes-inactive"],
    queryFn: () => get<{ items: Theme[] }>("/api/v1/themes?active=false"),
  });
  const themes = {
    isLoading: themesActive.isLoading || themesInactive.isLoading,
    isError: themesActive.isError || themesInactive.isError,
    refetch: () => { themesActive.refetch(); themesInactive.refetch(); },
    data: themesActive.data && themesInactive.data
      ? { items: [...themesActive.data.items, ...themesInactive.data.items] }
      : undefined,
  };
  const current = useQuery({
    queryKey: ["my-views"],
    queryFn: () => get<{ items: View[] }>("/api/v1/me/views/current"),
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<View[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length >= 2 ? s : [...s, id]));
  }

  async function submit() {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const r = await post<{ views: View[] }>("/api/v1/me/views", {
        theme_ids: selected,
        reason,
      });
      setResult(r.views);
      setSelected([]);
      setReason("");
      current.refetch();
    } catch (e: unknown) {
      setError(e instanceof ApiError ? "제출할 수 없습니다. 선택을 확인해주세요." : "제출 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell headerTitle="주간 투자 의견">
      <PageHeader
        title="주간 투자 의견"
        description="이번 주 관심 산업을 최대 2개 선택하세요."
        right={
          <span className="caption">
            제출 마감 · 금요일 18:00 (한국 시간)
          </span>
        }
      />
      <div className="weekly-views">
        <div>
          {themes.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : themes.isError || !themes.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => themes.refetch()} />
          ) : (
            <>
              <details className="view-rules">
                <summary>테마 비중 한도 · 합계 15%, 개별 10%</summary>
                <p>기본 주식 비중 안에서 반영하며, 위험 한도를 넘으면 테마 비중을 조정합니다. 선택 이유는 투자 의견과 함께 저장됩니다.</p>
              </details>
              <ThemeSelector themes={themes.data.items} selected={selected} onToggle={toggle} />
              {selected.length > 0 && (
                <div className="mt-[16px] rounded-card border border-border bg-surface p-[16px]">
                  <div className="card-heading mb-[8px]">선택한 투자 의견</div>
                  <div className="flex flex-wrap gap-[12px]">
                    {selected.map((id) => {
                      const t = themes.data!.items.find((x) => x.theme_id === id);
                      return (
                        <div key={id} className="flex-1 rounded-[6px] border border-border bg-surface-subtle p-[12px] text-center">
                          <div className="text-[14px] font-semibold leading-[20px]">{THEME_LABELS[id] ?? t?.display_name ?? id}</div>
                          <div className="caption">{t?.ticker ?? ""}</div>
                          <div className="caption mt-[4px]">{selected.length === 1 ? "10%" : "7.5%"}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              <div className="mt-[20px]">
                <SectionHeader title="선택 이유" />
                <label className="block max-w-[640px]">
                  <span className="sr-only">선택 이유</span>
                  <textarea className="input" placeholder="이번 주 이 산업을 긍정적으로 보는 이유를 간단히 입력하세요." value={reason} onChange={(e) => setReason(e.target.value)} />
                </label>
              </div>
              <div className="mt-[20px] flex flex-wrap items-center gap-[12px]">
                <button className="btn-secondary" onClick={() => { setSelected([]); setReason(""); }} disabled={busy}>선택 초기화</button>
                <button className="btn-primary btn-cta" onClick={submit} disabled={busy || selected.length === 0}>{busy ? "제출 중…" : "투자 의견 제출"}</button>
              </div>
              {error ? <p role="alert" className="mt-[12px] text-[13px] leading-[20px] text-negative">{error}</p> : null}
              {result ? (
                <div className="mt-[20px] border border-border bg-surface p-[20px]" style={{ borderRadius: 8 }} role="status">
                  <h3 className="card-heading mb-[12px]">제출 완료</h3>
                  {result.map((v) => (
                    <p key={v.view_id} className="text-[13px] leading-[20px]">{THEME_LABELS[v.theme_id] ?? v.theme_id} · 의견 기준일 {fmtDate(v.cycle_date)} · 적용 기준일 {fmtDate(v.effective_at)} · {executionStatus[v.execution_status] ?? "체결 상태 확인 필요"}</p>
                  ))}
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
      <div className="mt-[32px]">
        <SectionHeader title="저장된 투자 의견" />
        {current.isLoading ? (
          <LoadingSkeleton rows={2} />
        ) : current.isError ? (
          <ErrorState message="저장된 투자 의견을 불러오지 못했습니다." onRetry={() => current.refetch()} />
        ) : !current.data || current.data.items.length === 0 ? (
          <EmptyState title="아직 저장된 투자 의견이 없습니다." />
        ) : (
          <ul className="flex flex-col gap-[8px]">
            {current.data.items.map((v) => (
              <li key={v.view_id} className="border border-border bg-surface px-[20px] py-[12px] text-[13px] leading-[20px]" style={{ borderRadius: 8 }}>
                <strong>{THEME_LABELS[v.theme_id] ?? v.theme_id}</strong><span className="caption"> · {viewStatus[v.status] ?? "상태 확인 필요"} · 적용 기준일 {fmtDate(v.effective_at)} · {executionStatus[v.execution_status] ?? "체결 상태 확인 필요"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
