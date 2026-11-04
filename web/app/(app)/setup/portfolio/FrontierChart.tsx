"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api/client";
import { useSetupStyles } from "../style-context";
import presentation from "./frontier-presentation.module.css";

export const GROUP_COLORS: Record<string, string> = { 주식: "#3b72e8", 채권: "#8ba5ad", 대체: "#c6ae88", 현금: "#d6dce5" };
export const ASSET_COLORS: Record<string, string> = {
  us_equity: "#3064d8", developed_ex_us: "#5683e4", emerging_markets: "#83a6ee", korea_equity: "#b0c6f4",
  us_treasury: "#637e88", korea_treasury: "#8ba5ad", tips: "#b8c9cf", gold: "#b69a6b", global_reit: "#d8c5a4", cash: "#d6dce5",
};
export type FrontierCoordinate = { volatility: number; expected_return: number };
type Point = FrontierCoordinate;
type Asset = Point & { asset_id: string; name: string; cat: string };
const strategyColor = (id: string) => id === "v8_surge" ? "#62cbe7" : id === "leader_stock" ? "#5dd5bc" : "#f0bd6c";
export interface FrontierData {
  frontier_version: string;
  benchmark_frontier_id: string;
  min_variance_frontier_id: string;
  tangency_frontier_id: string;
  points: (Point & { frontier_id: string; index: number; sharpe: number; weights: { asset_id: string; weight: number }[] })[];
  assets: { asset_id: string; display_name: string; expected_return: number; volatility: number }[];
}

export function FrontierChart({ points, assets, benchmark, selected, personalized, inspectedId, onInspect, comparisons = [], focus = false, className = "", chartLabel, returnAxisLabel = "기대수익률", onPortfolioInspect, inspectedPortfolio }: {
  points: Point[]; assets: Asset[]; benchmark?: Point; selected?: Point | null;
  personalized?: { expected_return?: number | null; volatility?: number | null } | null;
  comparisons?: StrategyPoint[]; focus?: boolean;
  className?: string; chartLabel?: string; returnAxisLabel?: string;
  inspectedId: string | null; onInspect: (id: string | null) => void;
  onPortfolioInspect?: (point: "base" | "personalized", trigger: HTMLElement | SVGElement) => void;
  inspectedPortfolio?: "base" | "personalized" | null;
}) {
  const { risk: styles } = useSetupStyles();
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 680, height: 300 });
  const [inspectedStrategyId, setInspectedStrategyId] = useState<string | null>(null);
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
  const visibleAssets = focus ? [] : assets;
  const all = [...points, ...visibleAssets, ...comparisons, ...(selected ? [selected] : []), ...(benchmark ? [benchmark] : []), ...(after ? [after] : [])];
  const minX = Math.max(0, Math.min(...all.map(p => p.volatility)) - .015);
  const maxX = Math.max(...all.map(p => p.volatility)) + .015;
  const minY = Math.min(...all.map(p => p.expected_return)) - .012;
  const maxY = Math.max(...all.map(p => p.expected_return)) + .009;
  const left = 64, right = width - 30, top = 12, bottom = height - 40;
  const x = (v: number) => left + (v - minX) / (maxX - minX) * (right - left);
  const y = (v: number) => bottom - (v - minY) / (maxY - minY) * (bottom - top);
  const coords = visibleAssets.map(a => ({ ...a, x: x(a.volatility), y: y(a.expected_return) }));
  const labelSize = width < 480 ? 12 : 14;
  const boxes: { x: number; y: number; width: number }[] = [];
  const labels = new Map<string, { x: number; y: number }>();
  for (const a of [...coords].sort((a, b) => b.y - a.y)) {
    const labelWidth = [...a.name].reduce((n, c) => n + (/[\uac00-\ud7a3]/.test(c) ? labelSize : labelSize * .6), 6);
    let chosen = { x: Math.max(left + labelWidth / 2, Math.min(right - labelWidth / 2, a.x)), y: Math.min(bottom - 8, a.y + 22) };
    search: for (const dy of [22, -16, 42, -36, 62, -56, 82]) {
      for (const dx of [0, -48, 48, -90, 90]) {
        const lx = Math.max(left + labelWidth / 2, Math.min(right - labelWidth / 2, a.x + dx));
        const ly = a.y + dy;
        if (ly > bottom - 8 || ly < top + labelSize) continue;
        const collides = boxes.some(b => Math.abs(b.y - ly) < 20 && Math.abs(b.x - lx) < (b.width + labelWidth) / 2 + 7)
          || coords.some(p => Math.abs(p.y - (ly - 4)) < 13 && Math.abs(p.x - lx) < labelWidth / 2 + 8);
        if (!collides) { chosen = { x: lx, y: ly }; break search; }
      }
    }
    boxes.push({ ...chosen, width: labelWidth }); labels.set(a.asset_id, chosen);
  }
  const inspected = coords.find(a => a.asset_id === inspectedId);
  const inspectedLabel = inspected ? labels.get(inspected.asset_id) : undefined;
  const inspectedStrategy = comparisons.find(p => p.id === inspectedStrategyId);
  return <><div ref={host} className={`${styles.chart} ${className}`} onMouseLeave={() => { onInspect(null); setInspectedStrategyId(null); }}>
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={chartLabel ?? "위험과 기대수익률 차트. 자산 점에 마우스를 올리거나 키보드로 선택하면 상세 정보가 표시됩니다."}>
      {Array.from({ length: 4 }, (_, i) => {
        const v = minY + (maxY - minY) * i / 3;
        return <g key={`y${i}`}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="var(--border)" strokeDasharray="3 4" /><text x={left - 7} y={y(v) + 4} textAnchor="end" className={styles.axisText}>{(v * 100).toFixed(1)}%</text></g>;
      })}
      {Array.from({ length: 4 }, (_, i) => {
        const v = minX + (maxX - minX) * i / 3;
        return <text key={`x${i}`} x={x(v)} y={bottom + 17} textAnchor="middle" className={styles.axisText}>{(v * 100).toFixed(1)}%</text>;
      })}
      <text x={(left + right) / 2} y={height - 3} textAnchor="middle" className={styles.axisText}>예상 변동성</text>
      <text transform={`translate(11 ${(top + bottom) / 2}) rotate(-90)`} textAnchor="middle" className={styles.axisText}>{returnAxisLabel}</text>
      <polyline points={points.map(p => `${x(p.volatility)},${y(p.expected_return)}`).join(" ")} fill="none" stroke="#74a8ff" strokeWidth={2.5} strokeLinejoin="round" />
      {coords.map(a => {
        const label = labels.get(a.asset_id)!;
        const active = inspectedId === a.asset_id;
        const color = GROUP_COLORS[a.cat] ?? GROUP_COLORS.현금;
        return <g key={a.asset_id} role="button" tabIndex={0} aria-label={`${a.name} 자산 정보 보기`} aria-pressed={active} className={styles.assetPoint}
          onMouseEnter={() => onInspect(a.asset_id)} onMouseLeave={() => onInspect(null)} onFocus={() => onInspect(a.asset_id)} onBlur={() => onInspect(null)} onClick={() => onInspect(a.asset_id)}
          aria-describedby={active ? "asset-point-tooltip" : undefined}
          onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onInspect(a.asset_id); } if (e.key === "Escape") onInspect(null); }}>
          <circle cx={a.x} cy={a.y} r={13} fill="transparent" />
          <circle className={styles.assetPointDot} cx={a.x} cy={a.y} r={5} fill={color} stroke="var(--surface)" strokeWidth={1} />
          {active && <circle cx={a.x} cy={a.y} r={9} fill="none" stroke={color} strokeWidth={1.5} />}
          {(Math.abs(label.x-a.x)>20 || Math.abs(label.y-a.y)>30) && <line x1={a.x} y1={a.y} x2={label.x} y2={label.y-labelSize/2} stroke={color} strokeWidth={1} opacity={.55} pointerEvents="none"/>}
          <text x={label.x} y={label.y} textAnchor="middle" className={styles.pointLabel} style={{fontSize:labelSize}}>{a.name}</text>
        </g>;
      })}
      {comparisons.map(p => <g key={p.id} role="img" aria-label={`${p.label}: 과거 수익률 추정 ${(p.expected_return*100).toFixed(2)}%, 변동성 ${(p.volatility*100).toFixed(2)}%${p.validation_status ? `, ${p.currency} 기준 검증 전 백테스트 ${p.validation_status}` : ""}`}
        tabIndex={0}
        aria-describedby={inspectedStrategy?.id === p.id ? "strategy-point-tooltip" : undefined}
        onMouseEnter={() => setInspectedStrategyId(p.id)} onMouseLeave={() => setInspectedStrategyId(null)}
        onFocus={() => setInspectedStrategyId(p.id)} onBlur={() => setInspectedStrategyId(null)} onClick={() => setInspectedStrategyId(p.id)}
        onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setInspectedStrategyId(p.id); } if (e.key === "Escape") setInspectedStrategyId(null); }}>
        <title>{p.validation_status ? `${p.label} · ${p.currency} · ${p.validation_status} · 검증 전 백테스트` : `${p.label} · 과거 구성 추정치`}</title>
        <path d={`M ${x(p.volatility)} ${y(p.expected_return)-8} l 8 8 l -8 8 l -8 -8 Z`} fill={strategyColor(p.id)} stroke="var(--surface)" strokeWidth={2}/>
        <text x={x(p.volatility)-12} y={Math.max(16, y(p.expected_return)-14)} textAnchor="end" className={styles.pointLabel}>{p.label}</text>
      </g>)}
      {selected && <g role={onPortfolioInspect ? "button" : "img"} aria-label="테마 적용 전 Base Portfolio" data-portfolio-point="base"
        tabIndex={onPortfolioInspect ? 0 : undefined} aria-pressed={onPortfolioInspect ? inspectedPortfolio === "base" : undefined}
        style={{cursor:onPortfolioInspect ? "pointer" : undefined}}
        onClick={e=>onPortfolioInspect?.("base",e.currentTarget)}
        onKeyDown={e=>{if(onPortfolioInspect && (e.key==="Enter" || e.key===" ")){e.preventDefault();onPortfolioInspect("base",e.currentTarget);}}}>
        <circle cx={x(selected.volatility)} cy={y(selected.expected_return)} r={16} fill="transparent"/>
        <circle cx={x(selected.volatility)} cy={y(selected.expected_return)} r={8} fill="var(--surface)" stroke="#74a8ff" strokeWidth={2}/><circle cx={x(selected.volatility)} cy={y(selected.expected_return)} r={3.5} fill="#74a8ff"/>
      </g>}
      {after && <g role={onPortfolioInspect ? "button" : "img"} aria-label="테마 적용 후 Personalized Portfolio" data-portfolio-point="personalized"
        tabIndex={onPortfolioInspect ? 0 : undefined} aria-pressed={onPortfolioInspect ? inspectedPortfolio === "personalized" : undefined}
        style={{cursor:onPortfolioInspect ? "pointer" : undefined}}
        onClick={e=>onPortfolioInspect?.("personalized",e.currentTarget)}
        onKeyDown={e=>{if(onPortfolioInspect && (e.key==="Enter" || e.key===" ")){e.preventDefault();onPortfolioInspect("personalized",e.currentTarget);}}}>
        <circle cx={x(after.volatility)} cy={y(after.expected_return)} r={17} fill="transparent"/>
        <circle cx={x(after.volatility)} cy={y(after.expected_return)} r={9} fill="#baa0f3" stroke="var(--surface)" strokeWidth={2}/><circle cx={x(after.volatility)} cy={y(after.expected_return)} r={3} fill="var(--surface)"/>
      </g>}
    </svg>
    {inspected && inspectedLabel && <div id="asset-point-tooltip" role="tooltip" aria-label={`${inspected.name} 수익률과 변동성`} className={styles.pointTooltip}
      style={{ left: Math.max(4, Math.min(width - 204, inspectedLabel.x - 100)), top: Math.max(4, Math.min(height - 106, inspectedLabel.y + 10)) }}>
      <dl>
        <div><dt>기대수익률</dt><dd>{(inspected.expected_return * 100).toFixed(2)}%</dd></div>
        <div><dt>예상 변동성</dt><dd>{(inspected.volatility * 100).toFixed(2)}%</dd></div>
      </dl>
    </div>}
    {inspectedStrategy && <div id="strategy-point-tooltip" role="tooltip" aria-label={`${inspectedStrategy.label} 검증 상태와 계산값`} className={presentation.comparisonTooltip}
      style={{left:Math.max(4,Math.min(width-296,x(inspectedStrategy.volatility)-146)),top:Math.max(4,Math.min(height-220,y(inspectedStrategy.expected_return)+14))}}>
      <strong>{inspectedStrategy.label}</strong>
      <p>{inspectedStrategy.validation_status
        ? <>{inspectedStrategy.currency} 기준 · 검증 전 백테스트<br/><b>{inspectedStrategy.validation_status}</b></>
        : <>종목·비중 기반 과거 구성 추정<br/>실제 운용 성과 아님</>}</p>
      <dl>
        <div><dt>과거 수익률 추정 · 연율</dt><dd>{(inspectedStrategy.expected_return*100).toFixed(2)}%</dd></div>
        <div><dt>변동성 · 연율</dt><dd>{(inspectedStrategy.volatility*100).toFixed(2)}%</dd></div>
        <div><dt>샤프</dt><dd>{inspectedStrategy.sharpe.toFixed(2)}</dd></div>
      </dl>
      <p>{inspectedStrategy.period?.start}~{inspectedStrategy.period?.end}<br/>주간 평균×52 기준 · CAGR 아님</p>
    </div>}
  </div>
    <div className={presentation.legend} aria-label="포트폴리오 위치 범례">
      <span><i style={{display:"inline-block",width:18,borderTop:"2px solid #74a8ff",marginRight:6,verticalAlign:"middle"}}/>Efficient Frontier</span>
      {comparisons.map(p=><span key={p.id} style={{color:strategyColor(p.id)}}>◆ {p.label} · {p.validation_status ? `${p.currency} · 검증 전` : "과거 추정"}</span>)}
      {selected && <span><i style={{display:"inline-block",width:9,height:9,borderRadius:"50%",border:"2px solid #74a8ff",marginRight:6}}/>{onPortfolioInspect ? <button type="button" aria-pressed={inspectedPortfolio==="base"} onClick={e=>onPortfolioInspect("base",e.currentTarget)}>Base · 판단 보기</button> : "테마 적용 전"}</span>}
      {after && <span><i style={{display:"inline-block",width:9,height:9,borderRadius:"50%",background:"#baa0f3",marginRight:6}}/>{onPortfolioInspect ? <button type="button" aria-pressed={inspectedPortfolio==="personalized"} onClick={e=>onPortfolioInspect("personalized",e.currentTarget)}>Personalized · 판단 보기</button> : "테마 적용 후"}</span>}
    </div>
  </>;
}

// One authenticated contract for setup, review and saved portfolio views.
export function StrategyFrontierChart(props: Parameters<typeof FrontierChart>[0]) {
  const comparison = useQuery({queryKey:["strategy-frontier"], queryFn:()=>get<StrategyComparison>("/api/v1/strategies/frontier-comparison"), staleTime:60*60*1000, retry:1});
  const v8 = useQuery({queryKey:["v8-frontier"], queryFn:()=>get<StrategyPoint>("/api/v1/strategies/v8-frontier-comparison"), staleTime:60*60*1000, retry:1});
  const [focus, setFocus] = useState(true);
  const items = [...(comparison.data?.items ?? []).map(item => ({...item, period:item.period ?? comparison.data?.period})), ...(v8.data ? [v8.data] : [])];
  const showModels = items.length > 0 && !focus;
  return <>
    <div className={presentation.controls} aria-label="Frontier 표시 범위">
      <button type="button" className="btn-secondary" aria-pressed={!focus} onClick={()=>setFocus(false)}>전체 비교</button>
      <button type="button" className="btn-secondary" aria-pressed={focus} onClick={()=>setFocus(true)}>Frontier 확대</button>
    </div>
    <div className={presentation.singlePlot}>
      <section className={presentation.panel} aria-label="기본 Frontier와 자산 비교">
        <FrontierChart {...props} comparisons={showModels ? items : []} focus={false} className={presentation.plot}
          returnAxisLabel={showModels ? "연율 수익률" : "기대수익률"}/>
      </section>
    </div>
    {focus && <p className={presentation.note}>기본 자산 {props.assets.length}개와 내 포트폴리오를 표시합니다. 전략 비교점은 ‘전체 비교’에서 확인하세요.</p>}
    {!focus && comparison.isLoading && <p style={{color:"var(--text-secondary)",fontSize:13}}>모델 비교 지표를 불러오는 중입니다.</p>}
    {!focus && comparison.isError && <p role="status" style={{color:"var(--text-secondary)",fontSize:13}}>모델 비교 지표를 불러오지 못했습니다. <button type="button" className="btn-secondary" onClick={()=>comparison.refetch()}>다시 시도</button></p>}
    {!focus && v8.isLoading && <p className={presentation.note}>V8 백테스트 비교값을 불러오는 중입니다.</p>}
    {!focus && v8.isError && <p role="status" className={presentation.note}>V8 비교 자료를 불러오지 못했습니다. <button type="button" className="btn-secondary" onClick={()=>v8.refetch()}>V8 다시 시도</button></p>}
    {!focus && items.length > 0 && <div style={{marginTop:24}}>
      <p className={presentation.note}>원형은 기본 자산의 기대수익률, 마름모는 과거 자료로 계산한 전략 비교점입니다. 통화·계산 기준이 달라 점의 높이로 우열을 판단하지 않습니다.</p>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12,marginTop:12}}>
        {items.map(item=><article key={item.id} style={{padding:16,border:"1px solid var(--border)",borderRadius:14,background:"var(--surface-subtle)"}} aria-label={`${item.label} 비교 지표`}>
          <strong style={{color:strategyColor(item.id)}}>{item.label}</strong>
          <p style={{fontSize:12,color:"var(--text-secondary)",margin:"6px 0"}}>{item.validation_status ? `${item.currency} 백테스트 · 검증 전 (${item.validation_status})` : `${item.snapshot_date} 구성 · ${item.weights.length}개 자산`}</p>
          <p style={{fontSize:14,lineHeight:1.8,color:"var(--text-primary)"}}>과거 수익률 추정 · 연율 <b>{(item.expected_return*100).toFixed(2)}%</b><br/>변동성 · 연율 <b>{(item.volatility*100).toFixed(2)}%</b> · 샤프 <b>{item.sharpe.toFixed(2)}</b></p>
          <details style={{fontSize:12,color:"var(--text-secondary)",lineHeight:1.7}}><summary>{item.validation_status ? "백테스트 계산 기준" : "종목·비중과 계산 기준"}</summary>
            <p>{(item.period??comparison.data?.period)?.start}~{(item.period??comparison.data?.period)?.end} · 공통 주간 수익률 {(item.period??comparison.data?.period)?.observations}개 · 무위험 수익률 연 3%{item.validation_status ? " · 주간 평균 수익률×52 · USD 기준" : " · 현금 수익 0% · 거래 비용 제외"}</p>
            {item.validation_status ? <p>{item.note}</p> : <ul>{item.weights.map(w=><li key={w.ticker}>{w.company} · {(w.weight*100).toFixed(2)}%</li>)}</ul>}
          </details>
        </article>)}
      </div>
    </div>}
  </>;
}

type StrategyPeriod = {start:string;end:string;observations:number};
type StrategyPoint = FrontierCoordinate & { id:string; label:string; sharpe:number; snapshot_date:string; weights:{ticker:string; company:string; weight:number}[]; validation_status?:string; currency?:string; period?:StrategyPeriod; note?:string };
type StrategyComparison = { items:StrategyPoint[]; period:StrategyPeriod };
