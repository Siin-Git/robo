"use client";

import { useState } from "react";
import type { WeightLeg } from "@/lib/api/types";
import { assetLabel } from "@/lib/constants";
import { fmtPct } from "@/lib/format";
import { ASSET_COLORS } from "@/app/(app)/setup/portfolio/FrontierChart";
import s from "./allocation-donut.module.css";

const THEME_COLORS = ["#8056ce", "#ba70c8"];
export function AllocationDonut({ weights }: { weights: WeightLeg[] }) {
  const [active, setActive] = useState<string | null>(null);
  const rows = weights.filter(w => w.weight > 0).sort((a, b) => b.weight - a.weight);
  const total = rows.reduce((sum, row) => sum + row.weight, 0);
  const themes = rows.filter(row => row.asset_type === "theme");
  const selected = rows.find(row => row.asset_id === active);
  const color = (row: WeightLeg) => row.asset_type === "theme"
    ? THEME_COLORS[themes.findIndex(t => t.asset_id === row.asset_id) % THEME_COLORS.length]
    : ASSET_COLORS[row.asset_id] ?? "#9caebe";
  let offset = 0;
  if (!total) return <p>표시할 자산 구성이 없습니다.</p>;
  return <div className={s.layout}>
    <div className={s.chart}>
      <svg viewBox="0 0 380 380" role="group" aria-label="포트폴리오 자산 비중 파이 차트" onMouseLeave={() => setActive(null)}>
        {rows.map(row => {
          const start = offset, value = row.weight / total * 100;
          offset += value;
          return <circle key={row.asset_id} cx="190" cy="190" r="142" pathLength="100" fill="none"
            stroke={color(row)} strokeWidth={active === row.asset_id ? 64 : 54}
            strokeDasharray={`${value} ${100 - value}`} strokeDashoffset={-start} transform="rotate(-90 190 190)"
            role="button" tabIndex={0} aria-label={`${assetLabel(row.asset_id)} ${fmtPct(row.weight)}`} aria-pressed={active === row.asset_id}
            onMouseEnter={() => setActive(row.asset_id)} onFocus={() => setActive(row.asset_id)} onBlur={() => setActive(null)}
            onClick={() => setActive(row.asset_id)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActive(row.asset_id); } }}
            style={{ cursor: "pointer", pointerEvents: "visibleStroke", transition: "stroke-width .15s" }}/>;
        })}
        <text x="190" y="170" textAnchor="middle" className={s.label}>{selected ? assetLabel(selected.asset_id) : "전체 투자 구성"}</text>
        <text x="190" y="218" textAnchor="middle" className={s.value}>{fmtPct(selected?.weight ?? total, selected ? 2 : 0)}</text>
        <text x="190" y="247" textAnchor="middle" className={s.hint}>{selected?.asset_type === "theme" ? "선택한 테마" : selected ? "전체 투자금 기준" : `${rows.length}개 자산으로 분산`}</text>
      </svg>
      <p>차트나 자산을 선택해 비중을 확인하세요.</p>
      {themes.length > 0 && <span className={s.themeTotal}>선택한 테마 합계 <b>{fmtPct(themes.reduce((sum, t) => sum + t.weight, 0))}</b></span>}
    </div>
    <ul className={s.legend} aria-label="자산별 투자 비중" onMouseLeave={() => setActive(null)}>
      {rows.map(row => <li key={row.asset_id}>
        <button data-active={active === row.asset_id} onMouseEnter={() => setActive(row.asset_id)} onFocus={() => setActive(row.asset_id)} onBlur={() => setActive(null)} onClick={() => setActive(row.asset_id)} aria-pressed={active === row.asset_id}>
          <i style={{ background: color(row) }}/><span>{assetLabel(row.asset_id)}{row.asset_type === "theme" && <small>테마</small>}</span><strong>{fmtPct(row.weight)}</strong>
        </button>
      </li>)}
    </ul>
  </div>;
}
