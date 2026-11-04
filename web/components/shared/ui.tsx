import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  const color =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "";
  return (
    <div className="rounded-card border border-border bg-surface p-[16px]">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value mt-[4px] ${color}`}>{value}</div>
      {sub ? <div className="caption mt-[4px]">{sub}</div> : null}
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  Active: "bg-positive-soft text-positive",
  Pending: "bg-warning-soft text-warning",
  new: "bg-positive-soft text-positive",
  hold: "bg-brand-soft text-brand",
  closed: "bg-surface-subtle text-text-secondary",
  rejected: "bg-negative-soft text-negative",
  EXECUTED: "bg-positive-soft text-positive",
  PENDING: "bg-warning-soft text-warning",
};

export function StatusBadge({ children }: { children: string }) {
  const tone = BADGE_TONES[children] ?? "bg-surface-subtle text-text-secondary";
  return (
    <span className={`inline-block rounded-[999px] px-[8px] py-[2px] text-[12px] font-medium leading-[18px] ${tone}`}>
      {children}
    </span>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-border bg-surface px-[20px] py-[32px] text-center">
      <p className="text-[14px] font-semibold leading-[20px]">{title}</p>
      {hint ? <p className="caption mt-[4px]">{hint}</p> : null}
      {action ? <div className="mt-[12px]">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-card border border-border bg-surface px-[20px] py-[24px] text-center">
      <p className="text-[14px] leading-[21px]">{message}</p>
      <p className="caption mt-[4px]">잠시 후 다시 시도해주세요.</p>
      {onRetry ? (
        <button className="btn-secondary mt-[12px]" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="mb-[8px] h-[46px] animate-pulse bg-surface-subtle" />
      ))}
    </div>
  );
}
