"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { ArrowRight } from "lucide-react";
import { useSetupStyles } from "@/app/(app)/setup/style-context";
import { ASSET_META } from "@/app/(app)/setup/portfolio/asset-meta";
import { ASSET_COLORS } from "@/app/(app)/setup/portfolio/FrontierChart";
import type { ExperimentConditions } from "@/lib/api/experiment";
import { fmtPct } from "@/lib/format";

export function CoreConfirmation({conditions:c,pending,onNext}:{conditions:ExperimentConditions;pending:boolean;onNext:()=>void}) {
  const {risk:s}=useSetupStyles();const [selected,setSelected]=useState<string|null>(null);
  const weights=c.core_allocation.filter(w=>w.weight>0).sort((a,b)=>b.weight-a.weight);
  return <div className={s.page}><div className={s.workspace}><section className={s.assets}><div className={s.sectionHeading}><div><h2>공통 모델 포트폴리오</h2><p>{c.benchmark} · 이번 비교 실험에서는 공통 CORE를 사용합니다.</p></div></div><div className={s.piePanel} style={{height:330}}><ResponsiveContainer><PieChart><Pie data={weights} dataKey="weight" nameKey="asset_id" outerRadius="90%" startAngle={90} endAngle={-270} isAnimationActive={false}>{weights.map(w=><Cell key={w.asset_id} fill={ASSET_COLORS[w.asset_id]??"#8292a9"} stroke={selected===w.asset_id?"#172b46":"white"} strokeWidth={selected===w.asset_id?3:2} onMouseEnter={()=>setSelected(w.asset_id)} onClick={()=>setSelected(w.asset_id)} />)}</Pie></PieChart></ResponsiveContainer></div><ul className={s.assetList}>{weights.map(w=><li key={w.asset_id} data-active={selected===w.asset_id} onMouseEnter={()=>setSelected(w.asset_id)} onFocus={()=>setSelected(w.asset_id)} tabIndex={0}><div><span>{ASSET_META[w.asset_id]?.name??w.asset_id}</span><small>{ASSET_META[w.asset_id]?.desc}</small></div><strong>{fmtPct(w.weight)}</strong></li>)}</ul></section>
    <aside className={s.result}><div className={s.eyebrow}>공통 비교 기준</div><h2>{c.benchmark}</h2><p className={s.resultDescription}>모든 참가자에게 동일한 기본 자산배분</p><div className={s.metrics}><div><span>모델 목표 변동성</span><strong>{fmtPct(c.target_volatility)}</strong></div><div><span>Theme Budget</span><strong>{fmtPct(c.theme_budget.max_total_weight)}</strong></div></div><p className={s.estimateNote}>목표 위험 기준은 모형 추정치입니다. 실제 변동성이나 수익률을 보장하지 않습니다.</p><div className={s.allocationHeading}><h3>모델 선정 근거</h3></div><p className={s.estimateNote}>{c.selection_basis??"확인 필요"}<br/>{c.risk_method??"위험 모형 확인 필요"}<br/>모델 기준일 {c.model_reference_date}</p><div className={s.allocationHeading}><h3>동일한 실험 조건</h3></div><ul className={s.allocationList}><li><span>초기 NAV</span><strong>{c.initial_nav}</strong></li><li><span>초기자금</span><strong>{c.initial_capital_krw.toLocaleString()}원</strong></li><li><span>실제 실행 비용 설정</span><strong>{c.costs.trading_cost_bps}bp</strong></li><li><span>Theme 수</span><strong>최대 {c.theme_budget.max_themes}개</strong></li></ul><p className={s.estimateNote}>시연 NAV는 별도의 가상 시나리오입니다. 실제 거래·비용 반영 엔진의 결과가 아닙니다.</p><footer className={s.footer}><button className={s.next} disabled={pending} onClick={onNext}>공통 CORE 확인 · 다음<ArrowRight size={18}/></button></footer></aside></div></div>;
}
