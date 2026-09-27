"use client";

import { useEffect, useRef, useState } from "react";
import { useSetupStyles } from "../style-context";

export const GROUP_COLORS: Record<string, string> = { 주식: "#3b72e8", 채권: "#8ba5ad", 대체: "#c6ae88", 현금: "#d6dce5" };
export const ASSET_COLORS: Record<string, string> = {
  us_equity: "#3064d8", developed_ex_us: "#5683e4", emerging_markets: "#83a6ee", korea_equity: "#b0c6f4",
  us_treasury: "#637e88", korea_treasury: "#8ba5ad", tips: "#b8c9cf", gold: "#b69a6b", global_reit: "#d8c5a4", cash: "#d6dce5",
};
export type FrontierCoordinate = { volatility: number; expected_return: number };
type Point = FrontierCoordinate;
type Asset = Point & { asset_id: string; name: string; cat: string };
export interface FrontierData {
  frontier_version: string;
  benchmark_frontier_id: string;
  min_variance_frontier_id: string;
  tangency_frontier_id: string;
  points: (Point & { frontier_id: string; index: number; sharpe: number; weights: { asset_id: string; weight: number }[] })[];
  assets: { asset_id: string; display_name: string; expected_return: number; volatility: number }[];
}

export function FrontierChart({ points, assets, benchmark, selected, personalized, inspectedId, onInspect }: {
  points: Point[]; assets: Asset[]; benchmark?: Point; selected: Point;
  personalized?: { expected_return?: number | null; volatility?: number | null } | null;
  inspectedId: string | null; onInspect: (id: string | null) => void;
}) {
  const { risk: styles } = useSetupStyles();
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 680, height: 300 });
  useEffect(() => {
    if (!host.current) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width && height) setSize({ width, height });
    });
    observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  const { width, height } = size;
  const after = personalized?.expected_return != null && personalized?.volatility != null
    && Number.isFinite(personalized.expected_return) && Number.isFinite(personalized.volatility)
    ? { expected_return: personalized.expected_return, volatility: personalized.volatility } : null;
  const all = [...points, ...assets, selected, ...(benchmark ? [benchmark] : []), ...(after ? [after] : [])];
  const minX = Math.max(0, Math.min(...all.map(p => p.volatility)) - .015);
  const maxX = Math.max(...all.map(p => p.volatility)) + .015;
  const minY = Math.min(...all.map(p => p.expected_return)) - .012;
  const maxY = Math.max(...all.map(p => p.expected_return)) + .009;
  const left = 46, right = width - 30, top = 12, bottom = height - 40;
  const x = (v: number) => left + (v - minX) / (maxX - minX) * (right - left);
  const y = (v: number) => bottom - (v - minY) / (maxY - minY) * (bottom - top);
  const coords = assets.map(a => ({ ...a, x: x(a.volatility), y: y(a.expected_return) }));
  const boxes: { x: number; y: number; width: number }[] = [];
  const labels = new Map<string, { x: number; y: number }>();
  for (const a of [...coords].sort((a, b) => b.y - a.y)) {
    const labelWidth = [...a.name].reduce((n, c) => n + (/[\uac00-\ud7a3]/.test(c) ? 12 : 7), 6);
    let chosen = { x: Math.max(left + labelWidth / 2, Math.min(right - labelWidth / 2, a.x)), y: a.y + 18 };
    search: for (const dy of [18, 34, 50, 66, 82]) {
      for (const dx of [0, -48, 48, -90, 90]) {
        const lx = Math.max(left + labelWidth / 2, Math.min(right - labelWidth / 2, a.x + dx));
        const ly = a.y + dy;
        if (ly > bottom - 5) continue;
        const collides = boxes.some(b => Math.abs(b.y - ly) < 16 && Math.abs(b.x - lx) < (b.width + labelWidth) / 2 + 5)
          || coords.some(p => Math.abs(p.y - (ly - 4)) < 13 && Math.abs(p.x - lx) < labelWidth / 2 + 8);
        if (!collides) { chosen = { x: lx, y: ly }; break search; }
      }
    }
    boxes.push({ ...chosen, width: labelWidth }); labels.set(a.asset_id, chosen);
  }
  const inspected = coords.find(a => a.asset_id === inspectedId);
  const inspectedLabel = inspected ? labels.get(inspected.asset_id) : undefined;
  return <div ref={host} className={styles.chart} onMouseLeave={() => onInspect(null)}>
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="위험과 기대수익률 차트. 자산 점에 마우스를 올리거나 키보드로 선택하면 상세 정보가 표시됩니다.">
      {Array.from({ length: 4 }, (_, i) => {
        const v = minY + (maxY - minY) * i / 3;
        return <g key={`y${i}`}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="#cbd5e1" strokeDasharray="3 4" /><text x={left - 7} y={y(v) + 4} textAnchor="end" className={styles.axisText}>{(v * 100).toFixed(1)}%</text></g>;
      })}
      {Array.from({ length: 4 }, (_, i) => {
        const v = minX + (maxX - minX) * i / 3;
        return <text key={`x${i}`} x={x(v)} y={bottom + 17} textAnchor="middle" className={styles.axisText}>{(v * 100).toFixed(1)}%</text>;
      })}
      <text x={(left + right) / 2} y={height - 3} textAnchor="middle" className={styles.axisText}>예상 변동성</text>
      <text transform={`translate(11 ${(top + bottom) / 2}) rotate(-90)`} textAnchor="middle" className={styles.axisText}>기대수익률</text>
      <polyline points={points.map(p => `${x(p.volatility)},${y(p.expected_return)}`).join(" ")} fill="none" stroke="#2563eb" strokeWidth={2.5} strokeLinejoin="round" />
      {coords.map(a => {
        const label = labels.get(a.asset_id)!;
        const active = inspectedId === a.asset_id;
        const color = GROUP_COLORS[a.cat] ?? GROUP_COLORS.현금;
        return <g key={a.asset_id} role="button" tabIndex={0} aria-label={`${a.name} 자산 정보 보기`} aria-pressed={active} className={styles.assetPoint}
          onMouseEnter={() => onInspect(a.asset_id)} onMouseLeave={() => onInspect(null)} onFocus={() => onInspect(a.asset_id)} onBlur={() => onInspect(null)} onClick={() => onInspect(a.asset_id)}
          aria-describedby={active ? "asset-point-tooltip" : undefined}
          onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onInspect(a.asset_id); } if (e.key === "Escape") onInspect(null); }}>
          <circle cx={a.x} cy={a.y} r={13} fill="transparent" />
          <circle className={styles.assetPointDot} cx={a.x} cy={a.y} r={5} fill={color} stroke="white" strokeWidth={1} />
          {active && <circle cx={a.x} cy={a.y} r={9} fill="none" stroke={color} strokeWidth={1.5} />}
          <text x={label.x} y={label.y} textAnchor="middle" className={styles.pointLabel}>{a.name}</text>
        </g>;
      })}
      <g role="img" aria-label="테마 적용 전 Base Portfolio" pointerEvents="none"><circle cx={x(selected.volatility)} cy={y(selected.expected_return)} r={8} fill="white" stroke="#2563eb" strokeWidth={2} /><circle cx={x(selected.volatility)} cy={y(selected.expected_return)} r={3.5} fill="#2563eb" /></g>
      {after && <g role="img" aria-label="테마 적용 후 Personalized Portfolio" pointerEvents="none"><circle cx={x(after.volatility)} cy={y(after.expected_return)} r={9} fill="#7654c8" stroke="white" strokeWidth={2} /><circle cx={x(after.volatility)} cy={y(after.expected_return)} r={3} fill="white" /></g>}
    </svg>
    <div style={{display:"flex",gap:16,flexWrap:"wrap",fontSize:12,color:"#435a75",padding:"0 8px 5px"}} aria-label="포트폴리오 위치 범례">
      <span><i style={{display:"inline-block",width:9,height:9,borderRadius:"50%",border:"2px solid #2563eb",marginRight:6}}/>테마 적용 전</span>
      {after && <span><i style={{display:"inline-block",width:9,height:9,borderRadius:"50%",background:"#7654c8",marginRight:6}}/>테마 적용 후</span>}
    </div>
    {inspected && inspectedLabel && <div id="asset-point-tooltip" role="tooltip" aria-label={`${inspected.name} 수익률과 변동성`} className={styles.pointTooltip}
      style={{ left: Math.max(4, Math.min(width - 204, inspectedLabel.x - 100)), top: inspectedLabel.y + 10 }}>
      <dl>
        <div><dt>기대수익률</dt><dd>{(inspected.expected_return * 100).toFixed(2)}%</dd></div>
        <div><dt>예상 변동성</dt><dd>{(inspected.volatility * 100).toFixed(2)}%</dd></div>
      </dl>
    </div>}
  </div>;
}
