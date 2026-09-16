"use client";

import { fmtActivePp, fmtPct, fmtReturn } from "@/lib/format";
import type { RankingItem } from "@/lib/api/types";
import { DataTable } from "../tables/DataTable";

export interface RankingRow extends RankingItem {
  display_view?: string;
  cumulative?: number | null;
  mdd?: number | null;
  te?: number | null;
}

export function RankingTable({ rows }: { rows: RankingRow[] }) {
  return (
    <DataTable<RankingRow>
      columns={[
        { key: "rank", header: "Rank", numeric: true, render: (r) => String(r.rank) },
        { key: "p", header: "Participant", render: (r) => r.display_name },
        { key: "v", header: "Current View", render: (r) => r.display_view ?? "—" },
        {
          key: "a", header: "Active Return", numeric: true,
          render: (r) => <span className={r.active_return && r.active_return > 0 ? "text-positive" : r.active_return && r.active_return < 0 ? "text-negative" : ""}>{fmtReturn(r.active_return)}</span>,
        },
        { key: "c", header: "Cumulative Active", numeric: true, render: (r) => fmtReturn(r.cumulative) },
        { key: "m", header: "MDD", numeric: true, render: (r) => fmtPct(r.mdd) },
        { key: "t", header: "TE", numeric: true, render: (r) => fmtPct(r.te) },
      ]}
      rows={rows}
      rowKey={(r) => r.participant_id}
    />
  );
}
