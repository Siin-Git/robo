"use client";
import { getDecisions } from "@/lib/api/decisions";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { StrategyFrontierChart as FrontierChart, GROUP_COLORS, ASSET_COLORS, type FrontierData } from "./FrontierChart";
import { useSetupStyles } from "../style-context";
import { ThemesStep } from "./ThemeSelection";
import { ReviewStep } from "./ReviewStep";
import { ASSET_META } from "./asset-meta";
import { ArrowRight, RotateCcw, ChevronDown } from "lucide-react";
import { SetupProgress } from "@/components/portfolio/SetupProgress";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { get, post, put } from "@/lib/api/client";
import { DEMO_MODE } from "@/lib/api/comparison";
import type { ExperimentStatus } from "@/lib/api/experiment";
import { ExperimentSetup } from "@/components/portfolio/ExperimentSetup";
import { fmtPct } from "@/lib/format";
import { REBALANCE_LABELS, type RebalanceFrequency } from "@/lib/rebalance";

interface Theme {
  theme_id: string;
  display_name: string;
  ticker: string | null;
  active: boolean;
}


function riskLabel(vol: number): string {
  if (vol < 0.06) return "안정형";
  if (vol < 0.08) return "중립형";
  if (vol < 0.10) return "중립-공격형";
  return "공격형";
}
function groupsOf(weights: { asset_id: string; weight: number }[]) {
  const m: Record<string, number> = {};
  weights.forEach((w) => (m[w.asset_id] = w.weight));
  const equity = (m.us_equity || 0) + (m.developed_ex_us || 0) + (m.emerging_markets || 0) + (m.korea_equity || 0);
  const fixed = (m.us_treasury || 0) + (m.korea_treasury || 0) + (m.tips || 0);
  const alt = (m.gold || 0) + (m.global_reit || 0);
  const cash = m.cash || 0;
  return { equity, fixed, alt, cash };
}

function SetupPortfolioInner({market = false}: {market?: boolean}) {
  const { risk: styles } = useSetupStyles();
  const router = useRouter();
  const params = useSearchParams();
  const priorDecision = useQuery({queryKey:["decisions"],queryFn:getDecisions});
  const withAdjustment = (path:string) => params.get("adjustment_choice_id") ? `${path}${path.includes("?")?"&":"?"}adjustment_choice_id=${encodeURIComponent(params.get("adjustment_choice_id")!)}` : path;
  const qc = useQueryClient();
  const stepParam = params.get("step");
  const [step, setStep] = useState<"risk" | "themes" | "review">(
    stepParam === "themes" ? "themes" : stepParam === "review" ? "review" : "risk"
  );
  useEffect(() => {
    if (stepParam === "themes" || stepParam === "review" || stepParam === "risk") setStep(stepParam as "risk" | "themes" | "review");
  }, [stepParam]);

  const frontier = useQuery({
    queryKey: ["frontier"],
    queryFn: () => get<FrontierData>("/api/v1/me/frontier"),
    staleTime: 1000 * 60 * 60,
  });
  const draftQ = useQuery({
    queryKey: ["onboarding-draft"],
    queryFn: () => get<{ status: string; frontier_id?: string; theme_ids?: string[]; reason?: string; current_step?: string; rebalance_frequency?: RebalanceFrequency }>("/api/v1/me/onboarding/draft"),
  });
  const themesActive = useQuery({
    queryKey: ["themes-active"],
    queryFn: () => get<{ items: Theme[] }>("/api/v1/themes?active=true"),
  });
  const themesInactive = useQuery({
    queryKey: ["themes-inactive"],
    queryFn: () => get<{ items: Theme[] }>("/api/v1/themes?active=false"),
  });
  const themesQ = {
    data: themesActive.data && themesInactive.data ? { items: [...themesActive.data.items, ...themesInactive.data.items] } : undefined,
    isLoading: themesActive.isLoading || themesInactive.isLoading,
    isError: themesActive.isError || themesInactive.isError,
    refetch: () => { themesActive.refetch(); themesInactive.refetch(); },
  } as { data?: { items: Theme[] }; isLoading: boolean; isError: boolean; refetch: () => void };

  const points = frontier.data?.points ?? [];
  const initialIdx = useMemo(() => {
    if (!frontier.data) return 0;
    const draftFid = draftQ.data?.frontier_id;
    if (draftFid) {
      const i = points.findIndex((p) => p.frontier_id === draftFid);
      if (i >= 0) return i;
    }
    const benchIdx = points.findIndex((p) => p.frontier_id === frontier.data!.benchmark_frontier_id);
    return benchIdx >= 0 ? benchIdx : Math.floor(points.length / 2);
  }, [frontier.data, draftQ.data, points]);

  const [idx, setIdx] = useState<number | null>(null);
  const curIdx = idx ?? initialIdx;
  const selected = points[curIdx];
  const [selectedThemes, setSelectedThemes] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [frequency, setFrequency] = useState<RebalanceFrequency>("monthly");
  const [inspectedAssetId, setInspectedAssetId] = useState<string | null>(null);
  const [pieAssetId, setPieAssetId] = useState<string | null>(null);

  const draftHydrated = useRef(false);
  const navigating = useRef(false);
  const [navigationPending, setNavigationPending] = useState(false);
  const [saveError, setSaveError] = useState(false);
  useEffect(() => {
    if (!draftQ.data?.rebalance_frequency || !(draftQ.data.rebalance_frequency in REBALANCE_LABELS) || draftHydrated.current) return;
    setSelectedThemes(draftQ.data.theme_ids ?? []);
    setReason(draftQ.data.reason ?? "");
    setFrequency(draftQ.data.rebalance_frequency ?? "monthly");
    draftHydrated.current = true;
  }, [draftQ.data]);

  const mutateDraft = useMutation({
    mutationFn: async (body: { frontier_id?: string; theme_ids?: string[]; reason?: string; current_step: string; rebalance_frequency: RebalanceFrequency }) => {
      const saved = await put<{rebalance_frequency: RebalanceFrequency}>("/api/v1/me/onboarding/draft", body);
      if (saved.rebalance_frequency !== body.rebalance_frequency) throw new Error("Frequency was not acknowledged by the API.");
      return saved;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-draft"] }),
  });
  const mutateComplete = useMutation({
    mutationFn: async (body: { frontier_id: string; theme_ids: string[]; reason?: string; rebalance_frequency: RebalanceFrequency }) => {
      const saved = await post<{rebalance_frequency: RebalanceFrequency}>("/api/v1/me/onboarding/complete", {...body, adjustment_choice_id: params.get("adjustment_choice_id"), expected_decision_id:priorDecision.data?.items[0]?.decision_id});
      if (saved.rebalance_frequency !== body.rebalance_frequency) throw new Error("Frequency was not acknowledged by the API.");
      return saved;
    },
    onSuccess: async () => {
      await Promise.all(["base-portfolio", "summary-portfolio", "dashboard-performance", "onboarding-draft", "my-views", "comparison", "comparison-ranking", "comparison-analytics", "own-experiment", "experiment-status", "experiment-setup-status", "decisions", "decision-review", "portfolio-choices", "forward-ledger", "ledger-status"].map(key => qc.invalidateQueries({ queryKey: [key] })));
      router.push("/portfolio");
    },
  });

  async function saveAndNavigate(destination: "themes" | "review" | "issues", ids = selectedThemes, clearReason = false) {
    if (!selected || navigating.current) return;
    navigating.current = true;
    setNavigationPending(true);
    setSaveError(false);
    const nextReason = clearReason ? "" : reason;
    try {
      await mutateDraft.mutateAsync({
        frontier_id: selected.frontier_id, theme_ids: ids, reason: nextReason,
        rebalance_frequency: frequency,
        current_step: destination === "issues" ? "themes" : destination,
      });
      setSelectedThemes(ids);
      setReason(nextReason);
      if (destination === "issues") router.push(withAdjustment("/setup/issues"));
      else {
        setStep(destination);
        router.push(withAdjustment(`/setup/portfolio?step=${destination}`));
      }
    } catch {
      setSaveError(true);
    } finally {
      navigating.current = false;
      setNavigationPending(false);
    }
  }
  function goNext(ids?: string[]) {
    void saveAndNavigate(step === "risk" ? "themes" : "review", ids, !market && ids?.length === 0);
  }
  function goBack() {
    if (step === "themes") {
      setStep("risk");
      router.push(withAdjustment("/setup/portfolio?step=risk"));
    } else if (step === "review") {
      setStep("themes");
      router.push(withAdjustment("/setup/portfolio?step=themes"));
    }
  }

  if (draftQ.isLoading) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><LoadingSkeleton rows={4} /></AppShell>;
  if (draftQ.isError) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><ErrorState message="저장한 선택을 불러오지 못했습니다." onRetry={() => draftQ.refetch()} /></AppShell>;
  if (!draftQ.data?.rebalance_frequency || !(draftQ.data.rebalance_frequency in REBALANCE_LABELS)) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><ErrorState message="API에서 리밸런싱 주기 저장 지원을 확인하지 못했습니다. API 업데이트 후 다시 시도해 주세요." onRetry={() => draftQ.refetch()} /></AppShell>;
  if (frontier.isLoading) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><LoadingSkeleton rows={6} /></AppShell>;
  if (frontier.isError || !frontier.data) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><ErrorState message="포트폴리오 데이터를 불러오지 못했습니다." onRetry={() => frontier.refetch()} /></AppShell>;
  if (points.length === 0) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><EmptyState title="Frontier 데이터가 없습니다." /></AppShell>;
  if (!selected) return <AppShell headerTitle="내 기본 포트폴리오 선택" setup><LoadingSkeleton rows={4} /></AppShell>;

  const benchPoint = points.find((p) => p.frontier_id === frontier.data!.benchmark_frontier_id);
  const groups = groupsOf(selected.weights);
  const allocation = [
    { label: "주식", value: groups.equity, color: GROUP_COLORS.주식 },
    { label: "채권", value: groups.fixed, color: GROUP_COLORS.채권 },
    { label: "대체", value: groups.alt, color: GROUP_COLORS.대체 },
    { label: "현금", value: groups.cash, color: GROUP_COLORS.현금 },
  ];

  const assetWeights = [...selected.weights].sort((a, b) => b.weight - a.weight);

  return (
    <AppShell headerTitle={step === "review" ? "포트폴리오 설계" : "내 기본 포트폴리오 선택"} setup hideDesignNotice={step === "review"}>
      <SetupProgress step={step} />
      {step === "risk" && saveError && <p role="alert" className="text-negative">선택 내용을 저장하지 못했습니다. 다시 시도해 주세요.</p>}
      {step === "risk" && (
        <div className={styles.page}>
          <div className={styles.hero}>
          <header className={styles.intro}>
            <h1>위험 수준에 맞는 기본 포트폴리오를 설계하세요</h1>
            <p>Efficient Frontier에서 감수할 위험을 선택합니다. 슬라이더를 움직이면 기대수익률·예상 변동성·자산 비중이 함께 바뀝니다.</p>
          </header>

          <div className={styles.workspace}>
            <section className={styles.explorer} aria-labelledby="frontier-heading">
              <div className={styles.chartHeading}>
                <h2 id="frontier-heading">위험과 수익의 균형</h2>
                <span>Efficient Frontier</span>
              </div>
              <FrontierChart points={points} assets={frontier.data.assets.map(a => ({ ...a, name: ASSET_META[a.asset_id]?.name ?? a.display_name, cat: ASSET_META[a.asset_id]?.cat ?? "현금" }))}
                benchmark={benchPoint} selected={selected} inspectedId={inspectedAssetId} onInspect={setInspectedAssetId} />
              <div className={styles.riskControl}>
                <div className={styles.controlHeading}>
                  <label htmlFor="portfolio-risk">위험 수준</label>
                  <span>{riskLabel(selected.volatility)}</span>
                </div>
                <input id="portfolio-risk" type="range" min={0} max={points.length - 1} value={curIdx}
                  onChange={(e) => setIdx(Number(e.target.value))} aria-label="위험 수준"
                  aria-valuetext={`${riskLabel(selected.volatility)}, 예상 변동성 ${fmtPct(selected.volatility)}`}
                  className={styles.slider}
                  style={{ background: `linear-gradient(to right, var(--brand) ${points.length > 1 ? curIdx / (points.length - 1) * 100 : 0}%, var(--border) 0%)` }} />
                <div className={styles.rangeLabels}><span>안정적으로</span><span>적극적으로</span></div>
                <p>파란 선 위의 선택 지점과 오른쪽 요약을 함께 확인하세요. 다음 단계에서는 이 기본 구성에 투자 인사이트를 반영합니다.</p>
              </div>
              <fieldset className={styles.rebalanceSettings} disabled={navigationPending} aria-describedby="rebalance-description rebalance-band">
                <legend>정기 리밸런싱 주기</legend>
                <p id="rebalance-description">선택한 구성의 비중을 점검할 주기입니다. 최종 확정할 때 함께 저장됩니다.</p>
                <div className={styles.frequencyOptions}>
                  {(["monthly", "quarterly"] as const).map(value => <label key={value} data-selected={frequency === value}>
                    <input type="radio" name="rebalance-frequency" value={value} checked={frequency === value} onChange={() => setFrequency(value)} />
                    <span>{REBALANCE_LABELS[value]}</span>
                  </label>)}
                </div>
                <p id="rebalance-band">비중 이탈 기준은 목표 비중 대비 상대 10%입니다. 목표가 20%라면 18% 미만 또는 22% 초과일 때 조정 대상으로 판정하며, 경계값은 허용 범위에 포함됩니다.</p>
              </fieldset>
            </section>

            <aside className={styles.result} aria-label="현재 선택 포트폴리오">
              <div className={styles.eyebrow}>현재 선택 포트폴리오</div>
              <h2>{riskLabel(selected.volatility)}</h2>
              <p className={styles.resultDescription}>내가 선택한 기본 투자 구성</p>
              <div className={styles.metrics} aria-live="polite" aria-atomic="true">
                <div><span>기대수익률</span><strong className="kpi-value">{fmtPct(selected.expected_return)}</strong></div>
                <div><span>예상 변동성</span><strong className="kpi-value">{fmtPct(selected.volatility)}</strong></div>
              </div>
              <div className={styles.allocationHeading}><h3>자산 구성</h3><span>비중</span></div>
              <div className={styles.allocationBar} aria-hidden="true">
                {allocation.map((a) => <div key={a.label} style={{ width: `${a.value * 100}%`, background: a.color }} />)}
              </div>
              <ul className={styles.allocationList}>
                {allocation.map((a) => <li key={a.label}><span><i style={{ background: a.color }} />{a.label}</span><strong>{fmtPct(a.value)}</strong></li>)}
              </ul>
              <p className={styles.estimateNote}>기대수익률과 변동성은 모형의 추정치이며,<br />실제 투자 결과와 다를 수 있습니다.</p>
            </aside>
          </div>

          <a className={styles.scrollPrompt} href="#asset-allocation">상세 자산 구성 보기<ChevronDown size={17} aria-hidden="true" /></a>
          </div>

          <section id="asset-allocation" className={styles.assets} aria-labelledby="assets-heading">
            <div className={styles.sectionHeading}><div><h2 id="assets-heading">상세 자산별 구성</h2><p>선택한 위험 수준에 맞춘 투자 비중입니다.</p></div><span>{riskLabel(selected.volatility)}</span></div>
            <div className={styles.allocationDetail}>
              <div className={styles.piePanel} onMouseLeave={() => setPieAssetId(null)} role="group" aria-label="자산별 비중 파이차트">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart><Pie data={assetWeights.filter(w => w.weight > 0)} dataKey="weight" nameKey="asset_id" cx="50%" cy="50%" outerRadius="90%" startAngle={90} endAngle={-270} stroke="#ffffff" strokeWidth={2} isAnimationActive={false}>
                    {assetWeights.filter(w => w.weight > 0).map(w => <Cell key={w.asset_id}
                      fill={ASSET_COLORS[w.asset_id] ?? GROUP_COLORS.현금}
                      stroke={pieAssetId === w.asset_id ? "var(--text-primary)" : "#ffffff"} strokeWidth={pieAssetId === w.asset_id ? 3 : 2}
                      onMouseEnter={() => setPieAssetId(w.asset_id)} onFocus={() => setPieAssetId(w.asset_id)} onBlur={() => setPieAssetId(null)}
                      onClick={() => setPieAssetId(w.asset_id)} tabIndex={0} role="button"
                      aria-label={`${ASSET_META[w.asset_id]?.name ?? w.asset_id} ${fmtPct(w.weight)}`} />)}
                  </Pie></PieChart>
                </ResponsiveContainer>
              </div>
              <ul className={styles.assetList}>
                {assetWeights.map(w => <li key={w.asset_id} data-asset-id={w.asset_id} data-active={pieAssetId === w.asset_id}
                  tabIndex={0} onMouseEnter={() => setPieAssetId(w.asset_id)} onMouseLeave={() => setPieAssetId(null)}
                  onFocus={() => setPieAssetId(w.asset_id)} onBlur={() => setPieAssetId(null)}>
                  <i className={styles.assetSwatch} style={{ background: ASSET_COLORS[w.asset_id] ?? GROUP_COLORS.현금 }} />
                  <div><span>{ASSET_META[w.asset_id]?.name ?? w.asset_id}</span><small>{ASSET_META[w.asset_id]?.desc}</small></div>
                  <strong>{fmtPct(w.weight)}</strong>
                </li>)}
              </ul>
            </div>
          </section>

          <details className={styles.details}>
            <summary>상세 지표와 계산 설명<ChevronDown size={17} aria-hidden="true" /></summary>
            <div className={styles.detailContent}>
              <dl><div><dt>샤프지수</dt><dd>{selected.sharpe.toFixed(2)}</dd></div>
                <div><dt>포트폴리오 ID</dt><dd>{selected.frontier_id}</dd></div>
                {benchPoint && <div><dt>기준 대비 변동성</dt><dd>{selected.volatility > benchPoint.volatility ? "+" : ""}{((selected.volatility - benchPoint.volatility) * 100).toFixed(2)}%p</dd></div>}
              </dl>
              <p>Efficient Frontier는 같은 위험 수준에서 더 높은 기대수익을 목표로 하는 포트폴리오의 집합입니다. 그래프의 점은 자산군 색상으로 구분한 개별 자산입니다.</p>
              <div className={styles.tableScroll}><table className="fin-table"><thead><tr><th>자산</th><th>자산군</th><th className="num">비중</th><th className="num">기준 대비</th></tr></thead><tbody>
                {selected.weights.map((w) => {
                  const difference = w.weight - (benchPoint?.weights.find((b) => b.asset_id === w.asset_id)?.weight ?? 0);
                  return <tr key={w.asset_id}><td>{ASSET_META[w.asset_id]?.name ?? w.asset_id}</td><td>{ASSET_META[w.asset_id]?.cat}</td><td className="num">{fmtPct(w.weight)}</td><td className="num">{benchPoint ? `${difference > 0 ? "+" : ""}${(difference * 100).toFixed(2)}%p` : "—"}</td></tr>;
                })}
              </tbody></table></div>
            </div>
          </details>

          <footer className={styles.footer}>
            <button className={styles.reset} disabled={!benchPoint} onClick={() => { const i = points.findIndex((p) => p.frontier_id === benchPoint?.frontier_id); if (i >= 0) setIdx(i); }}><RotateCcw size={15} aria-hidden="true" />기준 구성으로 되돌리기</button>
            <button className={styles.next} disabled={navigationPending} onClick={() => goNext()}>{navigationPending ? "선택 저장 중…" : "다음: 투자 인사이트 반영"}<ArrowRight size={18} aria-hidden="true" /></button>
          </footer>
        </div>
      )}

      {step === "themes" && (
        <ThemesStep
          themesQ={themesQ}
          selected={selectedThemes}
          setSelected={setSelectedThemes}
          onBack={goBack}
          onNext={goNext}
          onIssues={() => { void saveAndNavigate("issues"); }}
          pending={navigationPending}
          saveError={saveError}
          initialCategory={params.get("category")}
          selectedBase={selected}
        />
      )}

      {step === "review" && (
        <ReviewStep
          basePoint={selected}
          frontierData={frontier.data}
          themeIds={selectedThemes}
          rebalanceFrequency={frequency}
          onBack={goBack}
          onComplete={() => mutateComplete.mutate({ frontier_id: selected.frontier_id, theme_ids: selectedThemes, reason, rebalance_frequency: frequency })}
          onCompleteBase={() => mutateComplete.mutate({ frontier_id: selected.frontier_id, theme_ids: [], reason, rebalance_frequency: frequency })}
          selectionReason={{value:reason,onChange:setReason}}
          pending={mutateComplete.isPending}
          error={mutateComplete.isError}
        />
      )}
    </AppShell>
  );
}

export default function SetupPortfolioPage() {
  const experiment=useQuery({queryKey:["experiment-setup-status"],queryFn:()=>get<ExperimentStatus>("/api/v1/me/experiment"),enabled:DEMO_MODE});
  if(DEMO_MODE&&experiment.isLoading)return <AppShell headerTitle="첫 설정"><LoadingSkeleton rows={4}/></AppShell>;
  if(DEMO_MODE&&experiment.isError)return <AppShell headerTitle="첫 설정"><ErrorState message="설정 상태를 불러오지 못했습니다." onRetry={()=>experiment.refetch()}/></AppShell>;
  if(experiment.data?.status==="setup_required" && !experiment.data.market_comparison)return <ExperimentSetup status={experiment.data}/>;
  return (
    <Suspense fallback={<AppShell headerTitle="내 기본 포트폴리오 선택" setup><LoadingSkeleton rows={6} /></AppShell>}>
      <SetupPortfolioInner market={experiment.data?.market_comparison} />
    </Suspense>
  );
}
