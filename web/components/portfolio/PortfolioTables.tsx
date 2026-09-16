"use client";

import { assetLabel } from "@/lib/constants";
import { fmtActivePp, fmtPct } from "@/lib/format";
import type { WeightLeg } from "@/lib/api/types";
import { DataTable } from "../tables/DataTable";

export function AllocationBars({ weights }: { weights: WeightLeg[] }) {
  const rows = [...weights].sort((a, b) => b.weight - a.weight);
  const max = Math.max(0.0001, ...rows.map((r) => r.weight));
  return (
    <div className="flex flex-col gap-[8px]">
      {rows.map((r) => (
        <div key={r.asset_id} className="grid grid-cols-[140px_1fr_64px] items-center gap-[12px]">
          <span className="truncate text-[13px] leading-[20px]">{assetLabel(r.asset_id)}</span>
          <div className="h-[8px] bg-surface-subtle">
            <div
              className="h-[8px]"
              style={{
                width: `${(r.weight / max) * 100}%`,
                background: r.asset_type === "theme" ? "var(--brand)" : "var(--text-primary)",
              }}
            />
          </div>
          <span className="tnum text-right text-[13px] font-medium leading-[20px]">
            {fmtPct(r.weight)}
          </span>
        </div>
      ))}
    </div>
  );
}

export interface ActiveRow {
  asset_id: string;
  core: number;
  mine: number;
  active: number;
}

export function PortfolioComparisonTable({ rows }: { rows: ActiveRow[] }) {
  return (
    <DataTable<ActiveRow>
      columns={[
        { key: "asset", header: "Asset", render: (r) => assetLabel(r.asset_id) },
        { key: "core", header: "Core", numeric: true, render: (r) => fmtPct(r.core) },
        { key: "mine", header: "Mine", numeric: true, render: (r) => fmtPct(r.mine) },
        {
          key: "active",
          header: "Active",
          numeric: true,
          render: (r) => (
            <span className={r.active > 0 ? "text-positive" : r.active < 0 ? "text-negative" : ""}>
              {r.active === 0 && r.core === 0 && r.mine === 0 ? "—" : fmtActivePp(r.active)}
            </span>
          ),
        },
      ]}
      rows={rows}
      rowKey={(r) => r.asset_id}
    />
  );
}
