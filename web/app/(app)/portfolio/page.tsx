"use client";

import { DEMO_MODE } from "@/lib/api/comparison";
import { ParticipantPerformance } from "@/components/dashboard/ParticipantPerformance";
import { useComparisonMode } from "@/lib/api/use-comparison-mode";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, SlidersHorizontal, Layers3 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { get } from "@/lib/api/client";
import { fmtActivePp, fmtDate, fmtPct } from "@/lib/format";
import { reviewRows, Weight } from "../setup/portfolio/review-data";
import { THEME_INFO } from "../setup/portfolio/theme-content";
import { ASSET_COLORS } from "../setup/portfolio/FrontierChart";
import { FrontierChart, type FrontierData } from "../setup/portfolio/FrontierChart";
import { SetupStyleProvider } from "../setup/SetupStyleProvider";
import { ASSET_META } from "../setup/portfolio/asset-meta";
import s from "./portfolio.module.css";
import { REBALANCE_LABELS, type RebalanceFrequency } from "@/lib/rebalance";

export interface PortfolioSummary {
  rebalance_frequency?: RebalanceFrequency | null;
  rebalance_frequency_source?: "CONFIRMED_SELECTION" | "LEGACY_DEFAULT" | "UNCONFIRMED";
  base: { frontier_id: string | null; expected_return: number | null; volatility: number | null; weights: Weight[]; groups: Record<string, number> };
  personalized: { expected_return?: number | null; volatility: number | null; tracking_error: number | null; weights: Weight[]; groups: Record<string, number> };
  themes: { theme_id: string; display_name?: string; ticker?: string | null; weight: number }[];
  risk_comparison?: { base_volatility: number | null; personalized_volatility: number | null; as_of: string | null; method: string | null } | null;
}
const THEME_COLORS = ["#baa0f3", "#aa74d6"];
const GROUPS = [
  { key: "broad_equity", base: "equity", name: "일반 주식", color: "#3b72e8" },
  { key: "themes", base: "themes", name: "선택 테마", color: "#8560cd" },
  { key: "fixed_income", base: "fixed_income", name: "채권", color: "#718b95" },
  { key: "alternatives", base: "alternatives", name: "대체", color: "#b69a6b" },
  { key: "cash", base: "cash", name: "현금", color: "#c2cad6" },
];

export default function PortfolioPage() {
  return DEMO_MODE ? <Suspense fallback={<LoadingSkeleton rows={6}/>}><DemoPortfolioRoute/></Suspense> : <DesignPortfolioPage/>;
}

function DemoPortfolioRoute() {
  const params=useSearchParams();
  return params.get("source")==="demo" ? <DemoPortfolioPage/> : <DesignPortfolioPage/>;
}

function DemoPortfolioPage() {
  const mode = useComparisonMode();
  if(mode.isLoading)return <LoadingSkeleton rows={6}/>;
  if(mode.isError)return <ErrorState message="비교 설정을 불러오지 못했습니다." onRetry={()=>mode.refetch()}/>;
  return <ParticipantPerformance portfolioOnly/>;
}

function DesignPortfolioPage() {
  const summary = useQuery({ queryKey: ["summary-portfolio"], queryFn: () => get<PortfolioSummary>("/api/v1/me/portfolio/summary") });
  return <AppShell headerTitle={DEMO_MODE ? "내 자유 설계 포트폴리오" : "내 포트폴리오"} softBackground>
    {summary.isLoading ? <LoadingSkeleton rows={6} /> : summary.isError || !summary.data ?
      <ErrorState message="포트폴리오를 불러오지 못했습니다." onRetry={() => summary.refetch()} /> :
      <PortfolioOverview data={summary.data} />}
  </AppShell>;
}

function PortfolioOverview({ data: p }: { data: PortfolioSummary }) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const rows = reviewRows(p);
  const allocations = rows.filter(r => r.final > 0);
  const total = allocations.reduce((sum, r) => sum + r.final, 0);
  const themes = p.themes.filter(t => allocations.some(r => r.id === t.theme_id && r.isTheme));
  const themeTotal = allocations.filter(r => r.isTheme).reduce((sum, r) => sum + r.final, 0);
  const name = (id: string) => THEME_INFO[id]?.name ?? p.themes.find(t => t.theme_id === id)?.display_name ?? id;
  const color = (id: string) => { const i = themes.findIndex(t => t.theme_id === id); return i >= 0 ? THEME_COLORS[i % THEME_COLORS.length] : ASSET_COLORS[id] ?? "var(--text-secondary)"; };
  const selected = allocations.find(r => r.id === activeId);
  const before = p.risk_comparison?.base_volatility;
  const after = p.risk_comparison?.personalized_volatility;
  const delta = before != null && after != null ? after - before : null;
  const currentVol = after ?? p.personalized.volatility;
  let offset = 0;
  if (!p.base.frontier_id || !allocations.length) return <div className={s.page}><EmptyState title="아직 투자 구성이 없어요" hint="위험 수준과 관심 테마를 선택해 내 포트폴리오를 만들어 보세요." /><Link className={s.edit} href="/setup/portfolio?step=risk">투자 구성 만들기<ArrowRight size={16} /></Link></div>;

  return <div className={s.page}>
    <header className={s.header}>
      <div><span className={s.eyebrow}>CONFIRMED ALLOCATION</span><h1>{DEMO_MODE ? "내 자유 설계 포트폴리오" : "내 포트폴리오"}</h1><p>{themes.length ? <>기본 자산배분에 <strong>{themes.map(t => name(t.theme_id)).join(" · ")}</strong>를 반영했어요.</> : "선택한 위험 수준에 맞춘 기본 자산배분입니다."}</p></div>
      <div className="ui-actions">{DEMO_MODE && <Link className={s.edit} href="/portfolio?source=demo">시연 비교 구성</Link>}<Link className={s.edit} href="/setup/portfolio?step=risk"><SlidersHorizontal size={16} />구성 변경</Link></div>
    </header>
    {p.rebalance_frequency && <p aria-label="저장된 리밸런싱 주기">{p.rebalance_frequency_source === "LEGACY_DEFAULT" ? "기존 판단의 기본 정기 리밸런싱" : "확정한 정기 리밸런싱"}: <strong>{REBALANCE_LABELS[p.rebalance_frequency]}</strong>{p.rebalance_frequency_source === "LEGACY_DEFAULT" && " · 당시 선택 기록 없음"}</p>}

    <section className={s.composition} aria-labelledby="portfolio-composition">
      <div className={s.compositionHeader}><div><h2 id="portfolio-composition">나의 자산 구성</h2><p>자산 위에 커서를 올려 비중을 확인해 보세요.</p></div>
        <div className={s.metrics}><div><span>현재 구성 예상 변동성</span><strong>{fmtPct(currentVol)}</strong></div><div><span>반영한 테마 비중</span><strong className={s.purple}>{fmtPct(themeTotal)}</strong></div></div>
      </div>
      <div className={s.compositionGrid}>
        <div className={s.chartArea}>
          <svg viewBox="0 0 400 400" className={s.donut} role="group" aria-label="현재 자산 구성 도넛 차트" onMouseLeave={() => setActiveId(null)}>
            {allocations.map(row => {
              const start = offset; const value = row.final / total * 100; offset += value;
              return <circle key={row.id} cx="200" cy="200" r="150" pathLength="100" fill="none" stroke={color(row.id)} strokeWidth={activeId === row.id ? 67 : 58}
                strokeDasharray={`${value} ${100 - value}`} strokeDashoffset={-start} transform="rotate(-90 200 200)"
                role="button" tabIndex={0} aria-label={`${row.name} ${fmtPct(row.final)}`} aria-pressed={activeId === row.id}
                onMouseEnter={() => setActiveId(row.id)} onFocus={() => setActiveId(row.id)} onBlur={() => setActiveId(null)} onClick={() => setActiveId(row.id)}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActiveId(row.id); } }} />;
            })}
            <text x="200" y="181" textAnchor="middle" className={s.centerLabel}>{selected?.name ?? "전체 투자 구성"}</text>
            <text x="200" y="228" textAnchor="middle" className={s.centerValue}>{fmtPct(selected?.final ?? total, selected ? 2 : 0)}</text>
            <text x="200" y="260" textAnchor="middle" className={s.centerHint}>{selected?.isTheme ? "내가 선택한 테마" : selected ? "전체 투자금 기준" : `${allocations.length}개 자산으로 분산`}</text>
          </svg>
          <div className={s.chartCaption}><span className={s.liveDot} />현재 적용된 투자 비중</div>
        </div>
        <div className={s.assetPanel}><div className={s.listHeading}><span>자산</span><span>투자 비중</span></div>
          <ul className={s.assets} aria-label="현재 자산별 비중" onMouseLeave={() => setActiveId(null)}>
            {allocations.map(row => <li key={row.id} data-active={activeId === row.id} data-theme={row.isTheme}>
              <button onMouseEnter={() => setActiveId(row.id)} onFocus={() => setActiveId(row.id)} onBlur={() => setActiveId(null)} onClick={() => setActiveId(row.id)} aria-pressed={activeId === row.id}>
                <i style={{ background: color(row.id) }} /><span className={s.assetName}><strong>{row.name}{row.isTheme && <small>테마</small>}</strong><span>{row.description}</span></span><b>{fmtPct(row.final)}</b>
              </button>
            </li>)}
          </ul>
        </div>
      </div>
    </section>

    <PortfolioFrontier data={p}/>

    <section className={s.themes} aria-labelledby="chosen-themes"><div className={s.sectionTitle}><h2 id="chosen-themes">내가 선택한 테마</h2><span>{themes.length}개 테마 · {fmtPct(themeTotal)}</span></div>
      {themes.length ? <div className={s.themeGrid}>{themes.map(t => <article className={s.themeCard} key={t.theme_id} style={{ "--theme-color": color(t.theme_id) } as React.CSSProperties}>
        <div className={s.themeIcon}><Layers3 size={23} /></div><div className={s.themeCopy}><span>{t.ticker ?? "테마 ETF"}</span><h3>{name(t.theme_id)}</h3><p>{THEME_INFO[t.theme_id]?.description ?? "내 포트폴리오에 반영한 테마입니다."}</p></div><strong>{fmtPct(allocations.find(r => r.id === t.theme_id)?.final)}</strong>
      </article>)}</div> : <div className={s.noThemes}>추가한 테마가 없습니다. 현재는 기본 자산배분으로 구성되어 있어요.<Link href="/setup/portfolio?step=themes">테마 살펴보기<ArrowRight size={15} /></Link></div>}
    </section>

    <section className={s.changes} aria-labelledby="portfolio-changes"><div className={s.sectionTitle}><div><h2 id="portfolio-changes">{themes.length ? "테마를 반영하며 달라진 점" : "기본 구성과 현재 구성"}</h2><p>{themes.length ? "기존 주식 비중 일부를 선택한 테마에 배분했어요." : "테마를 추가하지 않은 현재 구성을 기본 자산배분과 비교합니다."}</p></div></div>
      <div className={s.changeGrid}><div>
        {[{ name: "기본 구성", groups: p.base.groups, base: true }, { name: "현재 구성", groups: p.personalized.groups, base: false }].map(item => <div className={s.barRow} key={item.name}><strong>{item.name}</strong><div className={s.bar} role="img" aria-label={`${item.name}: ${GROUPS.map(g => `${g.name} ${fmtPct(item.groups[item.base ? g.base : g.key] ?? 0)}`).join(", ")}`}>{GROUPS.map(g => {
          const value = item.groups[item.base ? g.base : g.key] ?? 0;
          return value > 0 ? <span key={g.key} style={{ width: `${value * 100}%`, background: g.color }} title={`${g.name} ${fmtPct(value)}`}>{value >= .1 ? fmtPct(value, 1) : ""}</span> : null;
        })}</div></div>)}
        <div className={s.legend}>{GROUPS.filter(g => (p.base.groups[g.base] ?? 0) + (p.personalized.groups[g.key] ?? 0) > 0).map(g => <span key={g.key}><i style={{ background: g.color }} />{g.name}</span>)}</div>
      </div><div className={s.risk}><h3>예상 변동성 변화</h3><div className={s.riskValues}><div><span>기본 구성</span><strong>{fmtPct(before)}</strong></div><ArrowRight size={20} /><div><span>현재 구성</span><strong>{fmtPct(after)}</strong></div></div>
        <p>{delta == null ? "같은 기준의 위험 지표를 산출할 데이터가 부족합니다." : <>기본 구성 대비 <b>{fmtActivePp(delta)}</b></>}</p><small>같은 기간과 위험 모형으로 비교합니다.{p.risk_comparison?.as_of && ` · ${fmtDate(p.risk_comparison.as_of)} 기준`}</small>
      </div></div>
    </section>

    <details className={s.details}><summary>자산별 변경 내역 보기<span>기본 비중 · 현재 비중 · 변화</span></summary><div className={s.tableWrap}><table><thead><tr><th>자산</th><th>기본 비중</th><th>현재 비중</th><th>변화</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} data-theme={row.isTheme}><th scope="row">{row.name}{row.isTheme && <small>테마</small>}</th><td>{fmtPct(row.base)}</td><td>{fmtPct(row.final)}</td><td>{Math.abs(row.change) < 1e-9 ? "변동 없음" : fmtActivePp(row.change)}</td></tr>)}</tbody></table></div></details>
    <details className={s.details}><summary>계산 기준과 위험 관리<span>지표 설명</span></summary><div className={s.methodGrid}>
      <div><h3>기본 구성의 기대수익률</h3><strong>{fmtPct(p.base.expected_return)}</strong><p>테마 반영 전 기본 자산배분의 추정치입니다. 현재 포트폴리오의 기대수익률을 뜻하지 않습니다.</p></div>
      <div><h3>변동성 계산 기준</h3><p>최근 5년의 주간 수익률과 Ledoit-Wolf 공분산 모형을 사용합니다. 두 구성에 같은 모형을 적용해 비교합니다.</p></div>
      <div><h3>기준 포트폴리오와의 차이</h3><strong>{fmtPct(p.personalized.tracking_error)}</strong><p>추적오차는 시스템 기준 포트폴리오(CORE)와 수익률이 얼마나 다르게 움직이는지 나타냅니다.</p></div>
      <div><h3>테마 반영 방식</h3><p>선택한 테마의 비중은 기존 주식 안에서 배분합니다. 설정 시 테마 비중과 변동성 한도를 확인하고 필요한 경우 비중을 조정합니다.</p></div>
    </div></details>
    <div className="ui-actions mt-[24px]"><Link className="btn-primary" href="/dashboard">운용 성과 확인<ArrowRight size={16} /></Link><Link className="btn-secondary" href="/ranking">참여자 성과 비교</Link></div>
    <p className={s.note}>표시된 비중은 현재 적용된 목표 비중이며 실제 보유 수량과 다를 수 있습니다. 예상 수익률과 변동성은 모형의 추정치이며 실제 투자 결과와 다를 수 있습니다.</p>
  </div>;
}

function PortfolioFrontier({data}:{data:PortfolioSummary}) {
  const [inspectedAssetId,setInspectedAssetId] = useState<string|null>(null);
  const frontier = useQuery({queryKey:["frontier"],queryFn:()=>get<FrontierData>("/api/v1/me/frontier"),enabled:data.base.expected_return!=null&&data.base.volatility!=null,staleTime:60*60*1000});
  if (data.base.expected_return == null || data.base.volatility == null) return null;
  return <section className={s.frontierPanel} aria-label="테마 적용 전후 Efficient Frontier 위치"><h2>Efficient Frontier에서의 위치</h2>
    {frontier.isLoading ? <LoadingSkeleton rows={3}/> : frontier.isError || !frontier.data ? <ErrorState message="Frontier 데이터를 불러오지 못했습니다." onRetry={()=>frontier.refetch()}/> :
      <SetupStyleProvider><FrontierChart points={frontier.data.points} assets={frontier.data.assets.map(a=>({...a,name:ASSET_META[a.asset_id]?.name??a.display_name,cat:ASSET_META[a.asset_id]?.cat??"현금"}))}
        selected={{expected_return:data.base.expected_return,volatility:data.base.volatility}}
        personalized={data.personalized} inspectedId={inspectedAssetId} onInspect={setInspectedAssetId}/></SetupStyleProvider>}
    {data.personalized.expected_return == null && <p>테마 적용 후 기대수익률은 백엔드 제공 전입니다. 현재는 적용 전 위치만 표시합니다.</p>}
  </section>;
}
