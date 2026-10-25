"use client";

import { THEME_LABELS } from "@/lib/constants";
import { Check } from "lucide-react";
import type { Theme } from "@/lib/api/types";

export function ThemeCard({
  theme,
  selected,
  onToggle,
}: {
  theme: Theme;
  selected: boolean;
  onToggle: () => void;
}) {
  const disabled = !theme.active;
  const name = THEME_LABELS[theme.theme_id] ?? theme.display_name;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      aria-pressed={selected}
      aria-label={`${name}${disabled ? " (준비 중)" : ""}`}
      className={`relative h-[118px] min-h-[44px] p-[16px] text-left ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      } border bg-surface ${
        selected ? "border-brand bg-brand-soft" : "border-border"
      }`}
      style={{ borderRadius: 8 }}
    >
      {selected && (
        <span className="absolute right-[12px] top-[12px] text-brand" aria-hidden>
          <Check size={18} />
        </span>
      )}
      <div className="text-[14px] font-semibold leading-[20px]">{name}</div>
      <div className="caption mt-[4px]">{theme.ticker ?? "—"}</div>
      <div className="mt-[8px]">
        {disabled ? (
          <span className="inline-block rounded-[999px] bg-surface-subtle px-[8px] py-[2px] text-[12px] font-medium leading-[18px] text-text-secondary">
            준비 중
          </span>
        ) : (
          <span className="caption">{theme.theme_type === "sector" ? "산업" : "테마"}</span>
        )}
      </div>
    </button>
  );
}

export function ThemeSelector({
  themes,
  selected,
  onToggle,
  max = 2,
}: {
  themes: Theme[];
  selected: string[];
  onToggle: (id: string) => void;
  max?: number;
}) {
  return (
    <div>
      <div
        className="grid grid-cols-1 gap-[16px] min-[360px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        role="group"
        aria-label="투자 테마 선택"
      >
        {themes.map((t) => (
          <ThemeCard key={t.theme_id} theme={t} selected={selected.includes(t.theme_id)}
            onToggle={() => onToggle(t.theme_id)} />
        ))}
      </div>
      <p className="caption mt-[12px]" aria-live="polite">
        선택 {selected.length}/{max}
      </p>
    </div>
  );
}
