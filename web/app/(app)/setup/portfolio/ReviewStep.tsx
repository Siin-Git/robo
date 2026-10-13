"use client";

import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, ShieldCheck } from "lucide-react";
import { ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { post } from "@/lib/api/client";
import { fmtActivePp, fmtPct } from "@/lib/format";
import { ASSET_COLORS, StrategyFrontierChart as FrontierChart, type FrontierData } from "./FrontierChart";
import { ASSET_META } from "./asset-meta";
import { THEME_INFO } from "./theme-content";
import { ReviewData, reviewRows } from "./review-data";
import { useSetupStyles } from "../style-context";
import { REBALANCE_LABELS, type RebalanceFrequency } from "@/lib/rebalance";

const THEME_COLORS = ["#baa0f3", "#aa74d6"];
const GROUPS = [
  { key: "broad_equity", base: "equity", name: "일반 주식", color: "#3b72e8" },
  { key: "themes", base: "themes", name: "선택 테마", color: "#8560cd" },
  { key: "fixed_income", base: "fixed_income", name: "채권", color: "#7f9ca5" },
  { key: "alternatives", base: "alternatives", name: "대체", color: "#b69a6b" },
  { key: "cash", base: "cash", name: "현금", color: "#c2cad6" },
];

export function ReviewStep({ basePoint, frontierData, themeIds, onBack, onComplete, pending, error, experiment, rebalanceFrequency }: {
  basePoint: { frontier_id: string }; themeIds: string[]; onBack: () => void; onComplete: () => void; pending: boolean; error: boolean;
  frontierData?: FrontierData;
  rebalanceFrequency?: RebalanceFrequency;
  experiment?: { reason: string; notice: ReactNode };
}) {
  const { review: s } = useSetupStyles();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [inspectedAssetId, setInspectedAssetId] = useState<string | null>(null);
  const preview = useQuery({
    queryKey: [experiment ? "experiment-review-preview" : "onboarding-preview", basePoint.frontier_id, themeIds.join(",")],
    queryFn: () => post<ReviewData>(experiment ? "/api/v1/me/experiment/preview" : "/api/v1/me/onboarding/preview", experiment ? {core_id:basePoint.frontier_id, theme_ids:themeIds} : { frontier_id: basePoint.frontier_id, theme_ids: themeIds }),
  });
  if (preview.isLoading) return <LoadingSkeleton rows={6} />;
  if (preview.isError || !preview.data) return <div><ErrorState message="최종 구성을 불러오지 못했습니다." onRetry={() => preview.refetch()} /><button className="btn-secondary" onClick={onBack}>테마 다시 고르기</button></div>;
  const p = preview.data;
  const rows = reviewRows(p);
  const allocations = rows.filter(r => r.final > 0);
  const total = allocations.reduce((sum, r) => sum + r.final, 0);
  const selected = allocations.find(r => r.id === activeId);
  const color = (id: string) => {
    const index = p.themes.findIndex(t => t.theme_id === id);
    return index >= 0 ? THEME_COLORS[index % THEME_COLORS.length] : ASSET_COLORS[id] ?? "var(--text-secondary)";
  };
  const themeName = (id: string) => THEME_INFO[id]?.name ?? p.themes.find(t => t.theme_id === id)?.display_name ?? id;
  const themeTotal = rows.filter(r => r.isTheme).reduce((sum, r) => sum + r.final, 0);
  const beforeVol = p.risk_comparison?.base_volatility;
  const afterVol = p.risk_comparison?.personalized_volatility;
  const delta = beforeVol != null && afterVol != null ? afterVol - beforeVol : null;
  const limit = p.risk_comparison?.max_increase_pp;
  let offset = 0;
  return <div className={s.page}>
    <header className={s.header}><div className={s.eyebrow}>BEFORE & AFTER</div><h1>인사이트가 포트폴리오를 어떻게 바꿨나요?</h1>
      <p>{p.themes.length ? <>기본 투자 구성에 <strong>{p.themes.map(t => themeName(t.theme_id)).join(" · ")}</strong>를 반영했어요.</> : "선택한 위험 수준에 맞춘 기본 투자 구성입니다."}</p>
    </header>
    {rebalanceFrequency && <p aria-label="확정 전 리밸런싱 주기">정기 리밸런싱: <strong>{REBALANCE_LABELS[rebalanceFrequency]}</strong> · 초기 설정에서 선택한 주기로 확정합니다.</p>}

    <div className="comparison-intro" aria-label="포트폴리오 설계 관계">
      <div><span className="ui-eyebrow">BEFORE</span><h2>기본 포트폴리오</h2><p>선택한 위험 수준에 맞춘 자산배분을 출발점으로 삼습니다.</p></div>
      <div><span className="ui-eyebrow">MY INSIGHT</span><h2>{p.themes.length ? p.themes.map(t => themeName(t.theme_id)).join(" · ") : "기본 구성 유지"}</h2><p>{p.themes.length ? "나의 전망을 기존 주식 비중 안에서 반영합니다." : "추가 테마 없이 선택한 자산배분을 유지합니다."}</p></div>
      <div><span className="ui-eyebrow">AFTER</span><h2>최종 포트폴리오</h2><p>비중과 위험 변화를 확인하고 확정합니다. 성과는 연결된 데이터가 있을 때 표시됩니다.</p></div>
    </div>
    {frontierData && p.base.expected_return != null && p.base.volatility != null && <section className={s.changes} aria-label="테마 적용 전후 Efficient Frontier 위치">
      <div className={s.sectionHeading}><div><h2>Efficient Frontier에서의 위치</h2><p>기본 구성과 테마 반영 후 구성을 같은 좌표계에 표시합니다.</p></div></div>
      <FrontierChart points={frontierData.points} assets={frontierData.assets.map(a => ({...a,name:ASSET_META[a.asset_id]?.name ?? a.display_name,cat:ASSET_META[a.asset_id]?.cat ?? "현금"}))}
        selected={{expected_return:p.base.expected_return,volatility:p.base.volatility}}
        personalized={p.personalized} inspectedId={inspectedAssetId} onInspect={setInspectedAssetId}/>
      {p.personalized.expected_return == null && <p>테마 적용 후 기대수익률은 백엔드 제공 전입니다. 현재는 적용 전 위치만 표시합니다.</p>}
    </section>}
    <section className={s.changes} aria-labelledby="changes-heading">
      <div className={s.sectionHeading}><div><h2 id="changes-heading">{p.themes.length ? "선택한 테마로 이렇게 달라졌어요" : "기본 구성으로 시작해요"}</h2><p>{p.themes.length ? "기존 주식의 일부를 선택한 테마로 재배분했습니다." : "테마를 추가하지 않아 자산별 비중은 그대로 유지됩니다."}</p></div></div>
      {p.themes.length > 0 && <div className={s.themeChanges}>{p.themes.map(t => <div key={t.theme_id}><i style={{ background: color(t.theme_id) }} /><strong>{themeName(t.theme_id)}</strong><span>{t.ticker}</span><b>{fmtPct(rows.find(r => r.id === t.theme_id)?.final ?? 0)}</b></div>)}</div>}
      {p.risk_guardrail_applied && <div className={s.adjustment}><ShieldCheck size={20} /><p><strong>위험 수준에 맞춰 테마 비중을 조정했어요.</strong><span>선택한 테마는 최종 합계 {fmtPct(themeTotal)}로 반영됩니다.</span></p></div>}
      <div className={s.changeGrid}>
        <div className={s.comparison}>
          {[{name:"변경 전", groups:p.base.groups, base:true},{name:"변경 후", groups:p.personalized.groups, base:false}].map(item => <div className={s.barRow} key={item.name}><strong>{item.name}</strong><div className={s.bar} role="img" aria-label={`${item.name}: ${GROUPS.map(g => `${g.name} ${fmtPct(item.groups[item.base ? g.base : g.key] ?? 0)}`).join(", ")}`}>{GROUPS.map(g => <div key={g.key} title={`${g.name} ${fmtPct(item.groups[item.base ? g.base : g.key] ?? 0)}`} style={{ width: `${(item.groups[item.base ? g.base : g.key] ?? 0) * 100}%`, background: g.color }} />)}</div></div>)}
          <div className={s.legend}>{GROUPS.filter(g => (p.base.groups[g.base] ?? 0) + (p.personalized.groups[g.key] ?? 0) > 0).map(g => <span key={g.key}><i style={{background:g.color}} />{g.name}</span>)}</div>
        </div>
        <div className={s.risk}>
          <h3>예상 변동성의 변화</h3><div className={s.riskValues}><div><span>기본 구성</span><strong>{fmtPct(beforeVol)}</strong></div><ArrowRight size={20} /><div><span>최종 구성</span><strong>{fmtPct(afterVol)}</strong></div></div>
          <p>{delta == null ? (experiment ? "시연의 고정 목표 비중입니다. 실제 실행 전 Backend 위험 검증이 필요합니다." : "같은 기준의 위험 지표를 산출할 데이터가 부족합니다.") : <>기본 구성 대비 <b>{fmtActivePp(delta)}</b></>}</p>
          <small>{p.risk_comparison?.as_of && `${p.risk_comparison.as_of.slice(0,10).replaceAll("-", ".")} 기준 · `}두 구성에 동일한 기간과 위험 모형을 적용합니다.</small>
        </div>
      </div>
    </section>

    <section className={s.composition} aria-labelledby="final-composition-heading">
      <div className={s.sectionHeading}><div><h2 id="final-composition-heading">나의 최종 포트폴리오</h2><p>자산 위에 커서를 올려 비중을 확인해 보세요.</p></div><span className={s.totalBadge}><Check size={15} /> 총 {fmtPct(total, 0)}</span></div>
      <div className={s.compositionGrid}>
        <div className={s.chartArea}>
          <svg viewBox="0 0 380 380" className={s.donut} role="group" aria-label="최종 자산 구성 도넛 차트" onMouseLeave={() => setActiveId(null)}>
            {allocations.map(row => {
              const start = offset; const value = total > 0 ? row.final / total * 100 : 0; offset += value;
              return <circle key={row.id} cx="190" cy="190" r="142" pathLength="100" fill="none" stroke={color(row.id)} strokeWidth={activeId === row.id ? 64 : 55}
                strokeDasharray={`${value} ${100 - value}`} strokeDashoffset={-start} transform="rotate(-90 190 190)"
                role="button" tabIndex={0} aria-label={`${row.name} ${fmtPct(row.final)}`} aria-pressed={activeId === row.id}
                onMouseEnter={() => setActiveId(row.id)} onFocus={() => setActiveId(row.id)} onBlur={() => setActiveId(null)} onClick={() => setActiveId(row.id)}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveId(row.id); } }} style={{ cursor: "pointer", transition: "stroke-width .15s", pointerEvents: "visibleStroke" }} />;
            })}
            <text x="190" y="176" textAnchor="middle" className={s.centerLabel}>{selected?.name ?? "최종 투자 구성"}</text>
            <text x="190" y="218" textAnchor="middle" className={s.centerValue}>{fmtPct(selected?.final ?? total, selected ? 2 : 0)}</text>
            <text x="190" y="248" textAnchor="middle" className={s.centerHint}>{selected?.isTheme ? "내가 추가한 테마" : selected ? "전체 투자금 기준" : `${allocations.length}개 자산으로 구성`}</text>
          </svg>
          {p.themes.length > 0 && <div className={s.themePill}>내가 고른 테마 <strong>{fmtPct(themeTotal)}</strong></div>}
        </div>
        <ul className={s.assets} aria-label="최종 자산별 비중" onMouseLeave={() => setActiveId(null)}>
          {allocations.map(row => <li key={row.id} data-active={activeId === row.id} data-theme={row.isTheme}>
            <button onMouseEnter={() => setActiveId(row.id)} onFocus={() => setActiveId(row.id)} onBlur={() => setActiveId(null)} onClick={() => setActiveId(row.id)} aria-pressed={activeId === row.id}>
              <i style={{ background: color(row.id) }} /><span className={s.assetName}><strong>{row.name}{row.isTheme && <small>선택 테마</small>}</strong><span>{row.description}</span></span><b>{fmtPct(row.final)}</b>
            </button>
          </li>)}
        </ul>
      </div>
    </section>

    <details open className={s.details}><summary>자산별 변경 내역 보기<span>기본 비중 · 최종 비중 · 변화</span></summary><div className={s.tableWrap}><table><thead><tr><th>자산</th><th>기본 비중</th><th>최종 비중</th><th>변화</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} data-theme={row.isTheme}><th scope="row">{row.name}{row.isTheme && <small>선택 테마</small>}</th><td>{fmtPct(row.base)}</td><td>{fmtPct(row.final)}</td><td>{Math.abs(row.change) < 1e-9 ? "변동 없음" : fmtActivePp(row.change)}</td></tr>)}</tbody></table></div></details>
    <p className={s.explanation}>예상 변동성은 모형의 추정치이며 실제 결과와 다를 수 있습니다.{limit != null && ` 테마 반영에 따른 변동성 증가는 같은 모형으로 계산한 기본 구성 대비 ${limit.toFixed(1)}%p 이내로 관리합니다.`}</p>
    {experiment&&<section className="ui-note"><p>선택 이유: {experiment.reason}</p>{experiment.notice}</section>}
    <footer className={s.footer}><div><strong>이 투자 구성으로 시작할까요?</strong><p>{p.themes.length ? `${p.themes.length}개 테마를 반영한 구성으로 시작합니다.` : "기본 자산배분으로 포트폴리오를 시작합니다."}</p></div><div className={s.actions}><button className={s.back} onClick={onBack} disabled={pending}><ArrowLeft size={16} />테마 다시 고르기</button><button className={s.confirm} onClick={onComplete} disabled={pending}>{pending ? "설정 중…" : experiment ? "포트폴리오 생성" : "포트폴리오 확정 · 성과 확인"}<ArrowRight size={17} /></button></div></footer>
    {error && <p className={s.error} role="alert">구성을 저장하지 못했습니다. 다시 시도해 주세요.</p>}
  </div>;
}
