"use client";

import { themeLabel } from "@/lib/constants";
import { fmtPct, fmtReturn } from "@/lib/format";
import type { RankingItem } from "@/lib/api/types";
import { DataTable } from "../tables/DataTable";

export interface RankingRow extends RankingItem {
  display_view?: string;
  cumulative?: number | null;
  mdd?: number | null;
  te?: number | null;
}

export function RankingTable({ rows, basis = "week" }: { rows: RankingRow[]; basis?: "week" | "cumulative" }) {
  return (
    <DataTable<RankingRow>
      columns={[
        { key: "rank", header: "순위", numeric: true, render: (r: RankingRow) => r.active_return == null ? "대기" : String(r.rank) },
        { key: "p", header: "참여자", render: (r: RankingRow) => r.display_name },
        { key: "v", header: "투자 테마", render: (r: RankingRow) => r.display_view ? r.display_view.split(", ").map(themeLabel).join(" · ") : "—" },
        {
          key: "a", header: basis === "week" ? "주간 초과수익률" : "누적 초과수익률", numeric: true,
          render: (r: RankingRow) => <span className={r.active_return && r.active_return > 0 ? "text-positive" : r.active_return && r.active_return < 0 ? "text-negative" : ""}>{fmtReturn(r.active_return)}</span>,
        },
        { key: "c", header: "누적 CORE 대비", numeric: true, render: (r: RankingRow) => fmtReturn(r.cumulative) },
        { key: "m", header: "최대 낙폭", numeric: true, render: (r: RankingRow) => fmtPct(r.mdd) },
        { key: "t", header: "추적오차", numeric: true, render: (r: RankingRow) => fmtPct(r.te) },
      ].filter(column => basis === "week" || column.key !== "c")}
      rows={rows}
      rowKey={(r) => r.participant_id}
    />
  );
}
