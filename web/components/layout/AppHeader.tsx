import type { ReactNode } from "react";

const BADGE = process.env.NEXT_PUBLIC_APP_PROFILE === "replay"
  ? "LOCAL REPLAY"
  : process.env.NEXT_PUBLIC_APP_PROFILE === "local"
    ? "LOCAL"
    : null;

export function AppHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <header className="app-header flex h-[64px] items-center justify-between border-b border-border bg-surface px-[20px] md:px-[32px]">
      <div className="flex items-center gap-[12px]">
        <h2 className="text-[14px] font-semibold leading-[20px]">{title}</h2>
        {BADGE ? (
          <span className="rounded-[999px] bg-warning-soft px-[8px] py-[2px] text-[12px] font-semibold leading-[17px] text-warning">
            {BADGE}
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-[16px]">{right}</div>
    </header>
  );
}

export function PageHeader({
  title,
  description,
  right,
}: {
  title: string;
  description?: string;
  right?: ReactNode;
}) {
  return (
    <div className="page-heading mb-[20px] flex items-start justify-between gap-[16px]">
      <div>
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-desc mt-[4px]">{description}</p> : null}
      </div>
      {right}
    </div>
  );
}

export function SectionHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <div className="mb-[12px] flex items-center justify-between">
      <h2 className="section-title">{title}</h2>
      {right}
    </div>
  );
}
