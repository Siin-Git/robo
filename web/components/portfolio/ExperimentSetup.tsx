"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { CoreConfirmation } from "./CoreConfirmation";
import { SetupProgress } from "./SetupProgress";
import { ThemesStep } from "@/app/(app)/setup/portfolio/ThemeSelection";
import { ReviewStep } from "@/app/(app)/setup/portfolio/ReviewStep";
import { ErrorState, LoadingSkeleton } from "@/components/shared/ui";
import { ApiError, get, post, put } from "@/lib/api/client";
import type { Theme } from "@/lib/api/types";
import type { ExperimentStatus, ExperimentConditions, ExperimentDraft } from "@/lib/api/experiment";
import { themeLabel } from "@/lib/constants";

export function ExperimentSetup({ status }: {status: ExperimentStatus}) {
  const router = useRouter(), qc = useQueryClient();
  const [draft, setDraft] = useState<ExperimentDraft>({core_id:"CORE_V0.3",theme_ids:[],reason:"",current_step:"risk",...status.draft});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(true);
  const pending = useRef<Promise<unknown>>(Promise.resolve());
  const changed = useRef(false);
  const latestDraft = useRef(draft);
  latestDraft.current = draft;
  const conditions = useQuery({queryKey:["experiment-conditions"], queryFn:()=>get<ExperimentConditions>("/api/v1/me/experiment/conditions")});
  const themes = useQuery({queryKey:["experiment-themes"], queryFn:()=>get<{items:Theme[]}>("/api/v1/themes?active=true")});

  function save(value: ExperimentDraft) {
    setSaved(false);
    const request = pending.current.catch(()=>undefined).then(()=>put("/api/v1/me/experiment/draft", value));
    pending.current = request;
    request.then(()=>{if(pending.current===request && JSON.stringify(latestDraft.current)===JSON.stringify(value)) setSaved(true);}).catch(()=>{setMessage("선택을 저장하지 못했습니다. 다시 저장해 주세요.");setSaved(false);});
    return request;
  }
  useEffect(()=>{
    if(!changed.current) return;
    const timer=setTimeout(()=>{void save(draft);},350);
    return ()=>clearTimeout(timer);
  },[draft]);
  function change(next: Partial<ExperimentDraft>) {changed.current=true;setSaved(false);setMessage("");setDraft(d=>({...d,...next}));}
  async function navigate(step: ExperimentDraft["current_step"]) {
    setBusy(true);setMessage("");
    try {const next={...draft,current_step:step};await save(next);changed.current=false;setDraft(next);} catch { /* save exposes error */ }
    finally {setBusy(false);}
  }
  async function complete() {
    setBusy(true);setMessage("");
    try {await save(draft);await post("/api/v1/me/experiment/complete",draft);await qc.invalidateQueries({queryKey:["experiment-status"]});await qc.invalidateQueries({queryKey:["comparison"]});await qc.invalidateQueries({queryKey:["comparison-ranking"]});await qc.invalidateQueries({queryKey:["comparison-analytics"]});await qc.invalidateQueries({queryKey:["experiment-setup-status"]});router.push("/portfolio?source=demo&created=1");}
    catch(e) {setMessage(e instanceof ApiError?e.message:"생성하지 못했습니다. 저장 상태를 확인한 뒤 다시 시도해 주세요.");}
    finally {setBusy(false);}
  }
  const c=conditions.data;
  const match=c?.scenarios.find(s=>[...s.themes].sort().join() === [...draft.theme_ids].sort().join());
  const notice=<p>{c?.market_comparison ? "모든 지원 Theme 조합을 같은 시장 가격과 기간으로 평가합니다. 생성 후 수익률과 순위를 확인할 수 있습니다." : match?`${match.scenario_id} · 선택 조합에 배정된 가상 NAV · 실제 금융 엔진 산출 결과가 아닙니다. 2026-04-01 — 2026-09-11`:"선택 조합의 시연 데이터가 없습니다. 확정 후 성과 집계 대기로 표시됩니다."}</p>;
  const catalog=c?.market_comparison ? null : <details className="ui-note mt-[20px]"><summary>가상 시연 성과가 제공되는 조합</summary><p>다른 조합도 확정할 수 있지만 성과 집계 대기로 표시됩니다.</p><div className="scenario-grid">{c?.scenarios.map(s=><button className="btn-secondary" key={s.scenario_id} onClick={()=>change({theme_ids:s.themes})}>{s.themes.map(themeLabel).join(" + ")}</button>)}</div></details>;
  return <AppShell headerTitle="첫 포트폴리오 설정"><div className="experiment-page">
    <SetupProgress step={draft.current_step}/>
    {draft.current_step==="risk"&&<header><p className="ui-eyebrow">첫 설정 · {status.registered}/{status.capacity}명 확정</p><h1 className="page-title">공통 CORE에서 나의 투자 관점으로</h1><p className="page-desc">{c?.market_comparison ? "공통 CORE에서 시작해 Theme를 선택하세요. 생성 후에도 재구성할 수 있고, 저장한 구성으로 비교 결과가 갱신됩니다." : "이번 비교 실험에서는 공통 CORE를 사용합니다. 확정 이후 자유 설계의 변경은 이 실험에 반영되지 않습니다."}</p></header>}
    {conditions.isLoading||themes.isLoading?<LoadingSkeleton rows={5}/>:conditions.isError||themes.isError||!c?<ErrorState message="실험 조건을 불러오지 못했습니다." onRetry={()=>{conditions.refetch();themes.refetch();}}/>:<>
      {draft.current_step==="risk"&&<CoreConfirmation conditions={c} pending={busy} onNext={()=>navigate("themes")}/>}
      {draft.current_step==="themes"&&<ThemesStep themesQ={themes} selected={draft.theme_ids} setSelected={value=>change({theme_ids:typeof value==="function"?value(draft.theme_ids):value})} onBack={()=>navigate("risk")} onNext={ids=>{if(ids) {const next={...draft,theme_ids:ids,current_step:"review" as const};setBusy(true);save(next).then(()=>{changed.current=false;setDraft(next);}).catch(()=>undefined).finally(()=>setBusy(false));}else void navigate("review");}} onIssues={()=>undefined} pending={busy} saveError={!!message} selectedBase={{frontier_id:c.benchmark}} experiment={{reason:draft.reason,onReason:reason=>change({reason}),notice,catalog}}/>}
      {draft.current_step==="review"&&<ReviewStep basePoint={{frontier_id:c.benchmark}} themeIds={draft.theme_ids} onBack={()=>navigate("themes")} onComplete={complete} pending={busy} error={!!message} experiment={{reason:draft.reason,notice}}/>}
    </>}
    <div className="ui-actions"><p role="status" aria-label="설정 저장 상태" className="caption">{saved?"서버에 저장됨":"저장 대기 중"}</p>{!saved&&<button className="btn-secondary" disabled={busy} onClick={()=>save(draft)}>선택 저장</button>}</div>
    {message&&<p role="alert" className="ui-note">{message}</p>}
  </div></AppShell>;
}
