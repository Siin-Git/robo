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
import { fmtDate } from "@/lib/format";

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
    <AppShell headerTitle="Weekly View">
      <PageHeader
        title="Weekly View"
        description="이번 주 유망하다고 생각하는 산업을 선택하세요. 최대 2개까지 선택할 수 있습니다."
        right={
          <span className="caption">
            이번 Cycle 마감
            <br />
            금요일 18:00 KST
          </span>
        }
      />
      <div className="grid grid-cols-1 gap-[32px] lg:grid-cols-[2fr_1fr]">
        <div>
          {themes.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : themes.isError || !themes.data ? (
            <ErrorState message="데이터를 불러오지 못했습니다." onRetry={() => themes.refetch()} />
          ) : (
            <>
              <ThemeSelector themes={themes.data.items} selected={selected} onToggle={toggle} />
              {selected.length > 0 && (
                <div className="mt-[16px] rounded-card border border-border bg-white p-[16px]">
                  <div className="card-heading mb-[8px]">선택한 View</div>
                  <div className="flex gap-[12px]">
                    {selected.map((id) => {
                      const t = themes.data!.items.find((x) => x.theme_id === id);
                      return (
                        <div key={id} className="flex-1 rounded-[6px] border border-border bg-surface-subtle p-[12px] text-center">
                          <div className="text-[14px] font-semibold leading-[20px]">{t?.display_name ?? id}</div>
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
              <div className="mt-[20px] flex items-center gap-[12px]">
                <span className="text-[13px] leading-[20px] text-text-secondary" aria-live="polite">선택 {selected.length}/2</span>
                <button className="btn-secondary" onClick={() => { setSelected([]); setReason(""); }} disabled={busy}>변경 취소</button>
                <button className="btn-primary btn-cta" onClick={submit} disabled={busy || selected.length === 0}>{busy ? "제출 중…" : "View 제출"}</button>
              </div>
              {error ? <p role="alert" className="mt-[12px] text-[13px] leading-[20px] text-negative">{error}</p> : null}
              {result ? (
                <div className="mt-[20px] border border-border bg-white p-[20px]" style={{ borderRadius: 8 }} role="status">
                  <h3 className="card-heading mb-[12px]">제출 완료</h3>
                  {result.map((v) => (
                    <p key={v.view_id} className="text-[13px] leading-[20px]">{v.theme_id} · cycle {fmtDate(v.cycle_date)} · effective {fmtDate(v.effective_at)} · {v.execution_status}</p>
                  ))}
                </div>
              ) : null}
            </>
          )}
        </div>
        <div>
          <div className="rounded-card border border-border bg-white p-[20px]">
            <div className="card-heading mb-[12px]">적용 규칙</div>
            <ul className="flex flex-col gap-[8px] text-[13px] leading-[20px]">
              <li>• 최대 2개 Theme</li>
              <li>• 총 Active Budget 최대 15%</li>
              <li>• 단일 Theme 최대 10%</li>
              <li>• Equity Sleeve 내에서 조달</li>
              <li>• 위험 한도 초과 시 Theme 비중 자동 조정</li>
              <li>• 선택 이유 저장</li>
            </ul>
          </div>
        </div>
      </div>
      <div className="mt-[32px]">
        <SectionHeader title="Current Views" />
        {current.isLoading ? (
          <LoadingSkeleton rows={2} />
        ) : !current.data || current.data.items.length === 0 ? (
          <EmptyState title="현재 선택된 View가 없습니다." />
        ) : (
          <ul className="flex flex-col gap-[8px]">
            {current.data.items.map((v) => (
              <li key={v.view_id} className="border border-border bg-white px-[20px] py-[12px] text-[13px] leading-[20px]" style={{ borderRadius: 8 }}>
                {v.theme_id} · {v.status} · effective {fmtDate(v.effective_at)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
