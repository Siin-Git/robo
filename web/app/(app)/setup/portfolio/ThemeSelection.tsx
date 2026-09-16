"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Atom, Bot, BrainCircuit, Check, Cpu, Dna, Globe2, Network, Newspaper, Server, ShieldCheck, X, Zap } from "lucide-react";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { post } from "@/lib/api/client";
import { fmtPct } from "@/lib/format";
import { CATEGORIES, Category, THEME_INFO } from "./theme-content";
import { useSetupStyles } from "../style-context";

interface Theme { theme_id: string; display_name: string; ticker: string | null; active: boolean }
interface Props {
  themesQ: { data?: { items: Theme[] }; isLoading: boolean; isError: boolean; refetch: () => void };
  selected: string[];
  setSelected: (v: string[] | ((s: string[]) => string[])) => void;
  onBack: () => void; onNext: (ids?: string[]) => void; onIssues: () => void;
  pending: boolean; saveError: boolean;
  initialCategory?: string | null;
  selectedBase: { frontier_id: string; expected_return: number; volatility: number };
}
interface Impact {
  base: { groups: Record<string, number> };
  personalized: { volatility: number | null; tracking_error: number | null; groups: Record<string, number> };
  themes: { theme_id: string; target_weight: number }[];
  risk_guardrail_applied: boolean;
  risk_comparison?: { base_volatility: number | null };
}
const ICONS: Record<string, typeof Cpu> = { ai: BrainCircuit, semiconductor: Cpu, robotics: Bot, defense: Globe2, nuclear: Atom, power_grid: Zap, biotech: Dna, cybersecurity: ShieldCheck, cloud_data_center: Server, optical_networking: Network };
const validCategory = (value?: string | null): Category => CATEGORIES.find(c => c === value) ?? "전체";

export function ThemesStep(props: Props) {
  if (props.themesQ.isError) return <div><ErrorState message="관심 분야 목록을 불러오지 못했습니다." onRetry={props.themesQ.refetch} /><button className="btn-secondary mt-[16px]" onClick={props.onBack}>이전: 위험 수준</button></div>;
  if (props.themesQ.isLoading || !props.themesQ.data) return <div><p role="status" className="mb-[16px] text-[14px]">관심 분야 목록을 불러오는 중입니다.</p><LoadingSkeleton rows={4} /><button className="btn-secondary mt-[16px]" onClick={props.onBack}>이전: 위험 수준</button></div>;
  return <ThemeCatalog {...props} themes={props.themesQ.data.items} />;
}

function ThemeCatalog({ themes, selected, setSelected, onBack, onNext, onIssues, pending, saveError, selectedBase, initialCategory }: Props & { themes: Theme[] }) {
  const { theme: s } = useSetupStyles();
  const [category, setCategory] = useState<Category>(validCategory(initialCategory));
  useEffect(() => setCategory(validCategory(initialCategory)), [initialCategory]);
  const invalidSelected = selected.some(id => !themes.some(t => t.theme_id === id && t.active && t.ticker));
  const impact = useQuery({
    queryKey: ["theme-selection-preview", selectedBase.frontier_id, [...selected].sort().join(",")],
    queryFn: () => post<Impact>("/api/v1/me/onboarding/preview", { frontier_id: selectedBase.frontier_id, theme_ids: selected }),
    enabled: !invalidSelected,
    staleTime: 60_000,
  });
  const p = impact.data;
  const total = p?.themes.reduce((sum, t) => sum + t.target_weight, 0);
  const visible = themes.filter(t => category === "전체" || THEME_INFO[t.theme_id]?.categories.includes(category));
  const toggle = (id: string) => setSelected(current => current.includes(id) ? current.filter(x => x !== id) : current.length < 2 ? [...current, id] : current);
  const groupSegments = p ? [
    { label: "일반 주식", value: p.personalized.groups.broad_equity ?? 0, color: "#3b72e8" },
    { label: "선택 테마", value: p.personalized.groups.themes ?? 0, color: "#8771cd" },
    { label: "채권", value: p.personalized.groups.fixed_income ?? 0, color: "#809da5" },
    { label: "대체", value: p.personalized.groups.alternatives ?? 0, color: "#b99d70" },
    { label: "현금", value: p.personalized.groups.cash ?? 0, color: "#c2cad6" },
  ] : [];
  return <div className={s.page}>
    <div className={s.eyebrow}>02 / 관심 분야 선택</div>
    <h1 className={s.heading}>어떤 분야의 미래에 관심이 있나요?</h1>
    <p className={s.intro}>관심 있는 테마를 최대 2개 골라보세요. 내 기본 투자 구성에 반영해 드립니다.</p>

    <section className={s.newsBanner} aria-label="최신 이슈 안내">
      <div className={s.newsLead}><Newspaper size={27} /><div><strong>요즘 어떤 변화가 일어나고 있을까요?</strong><p>최근 소식과 생각할 거리를 보고, 관심 있는 분야를 찾아보세요.</p></div></div>
      <button className={s.textButton} onClick={onIssues} disabled={pending}>최신 이슈 보러가기 <ArrowRight size={17} /></button>
    </section>

    <div className={s.layout}>
      <div>
        <nav id="theme-categories" className={s.categories} aria-label="테마 카테고리">
          {CATEGORIES.map(c => <button key={c} className={s.category} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}
        </nav>
        <div className={s.catalogHeading}><h2>{category === "전체" ? "모든 테마" : `${category} 테마`} <span>{visible.length}</span></h2><span>{selected.length >= 2 ? "2개 선택 완료 · 선택한 테마를 눌러 변경" : "관심 있는 테마를 눌러 선택하세요"}</span></div>
        {visible.length === 0 && <EmptyState title="이 카테고리에는 아직 테마가 없습니다." />}
        <div className={s.grid}>
          {visible.map(t => {
            const meta = THEME_INFO[t.theme_id];
            const name = meta?.name ?? t.display_name;
            const Icon = ICONS[t.theme_id] ?? Globe2;
            const checked = selected.includes(t.theme_id);
            const unavailable = !t.active || !t.ticker;
            return <article className={s.card} key={t.theme_id} data-selected={checked} data-unavailable={unavailable}>
              <button className={s.select} aria-label={`${name} ${checked ? "선택 해제" : "선택"}`} aria-pressed={checked} disabled={pending || unavailable || (!checked && selected.length >= 2)} onClick={() => toggle(t.theme_id)}>
                <div className={s.cardTop}><span className={s.icon}><Icon size={23} strokeWidth={1.7} /></span><span className={s.check} aria-hidden="true">{checked && <Check size={14} strokeWidth={3} />}</span></div>
                <h3>{name}</h3><p>{meta?.description ?? t.display_name}</p>
              </button>
              <div className={s.cardFooter}><span>{unavailable ? "준비 중" : `연결 ETF · ${t.ticker}`}</span><span>{checked ? "선택됨" : meta?.categories[0]}</span></div>
              {meta && <details><summary>어떤 분야인가요?</summary><p>{meta.detail}</p><strong>{meta.question}</strong></details>}
            </article>;
          })}
        </div>
        <button className={s.back} disabled={pending} onClick={onBack}><ArrowLeft size={16} /> 위험 수준 다시 보기</button>
      </div>

      <aside className={s.sidebar} aria-label="선택한 테마와 투자 구성">
        <div className={s.sideHeader}><h2>내가 고른 테마</h2><span className={s.count}>{selected.length} / 2</span></div>
        <p className={s.muted}>기본 포트폴리오의 주식 비중 안에서<br />선택한 테마를 반영합니다.</p>
        {selected.length === 0 ? <div className={s.empty}>관심 있는 분야를 골라보세요.<br />테마 없이 시작해도 괜찮습니다.</div> : selected.map(id => {
          const t = themes.find(t => t.theme_id === id);
          const name = THEME_INFO[id]?.name ?? t?.display_name ?? id;
          const w = p?.themes.find(t => t.theme_id === id)?.target_weight;
          return <div className={s.chosen} key={id}><div><strong>{name}</strong><span>{t?.ticker ?? "선택 확인 필요"} · {w == null || impact.isError ? "비중 확인 중" : `반영 비중 ${fmtPct(w)}`}</span></div><button disabled={pending} aria-label={`${name} 제거`} onClick={() => toggle(id)}><X size={16} /></button></div>;
        })}
        <div className={s.impact}>
          <h3>내 투자 구성 미리보기</h3>
          {invalidSelected ? <p className={s.error} role="alert">현재 선택할 수 없는 테마가 있습니다. 해당 테마를 제거하고 다시 골라주세요.</p> : impact.isError ? <div className={s.error} role="alert">반영 비중을 불러오지 못했습니다. <button className={s.textButton} onClick={() => impact.refetch()}>다시 시도</button></div> : !p ? <p className={s.muted} role="status">선택한 테마의 반영 비중을 확인하고 있습니다.</p> : <>
            <div className={s.stat}><span>테마 합계</span><strong>{fmtPct(total ?? 0)}</strong></div>
            <div className={s.bar} role="img" aria-label={groupSegments.map(g => `${g.label} ${fmtPct(g.value)}`).join(", ")}>{groupSegments.map(g => <div key={g.label} style={{ width: `${g.value * 100}%`, background: g.color }} />)}</div>
            <div className={s.legend}>{groupSegments.filter(g => g.value > 0).map(g => <span key={g.label}><i style={{ background: g.color }} />{g.label}</span>)}</div>
            <div className={s.stat}><span>기본 예상 변동성</span><strong>{fmtPct(p.risk_comparison?.base_volatility)}</strong></div>
            <div className={s.stat}><span>반영 후 예상 변동성</span><strong>{p.personalized.volatility == null ? "산출 전" : fmtPct(p.personalized.volatility)}</strong></div>
            {p.risk_guardrail_applied && <p className={s.muted}>위험 한도에 맞춰 테마 비중이 조정되었습니다.</p>}
            {p.personalized.volatility == null && <p className={s.muted}>위험 지표를 산출할 데이터가 부족해 목표 비중만 표시합니다.</p>}
          </>}
        </div>
        <details className={s.impact}><summary className={s.muted}>어떻게 반영되나요?</summary><p className={s.muted}>테마는 최대 2개, 전체 투자금의 합계 15%, 한 테마당 10% 이내로 반영합니다. 위험 한도에 따라 비중이 줄어들 수 있습니다.</p></details>
        {saveError && <p className={s.error} role="alert">선택 내용을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.</p>}
        <button className={s.primary} onClick={() => onNext()} disabled={pending || invalidSelected}>{pending ? "선택 내용 저장 중…" : "최종 구성 확인하기"}<ArrowRight size={17} /></button>
        {selected.length > 0 && <button className={s.skip} disabled={pending} onClick={() => onNext([])}>테마 없이 기본 구성으로 계속하기</button>}
      </aside>
    </div>
  </div>;
}
