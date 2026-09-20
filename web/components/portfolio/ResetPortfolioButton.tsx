"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, post } from "@/lib/api/client";

export function ResetPortfolioButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const qc = useQueryClient();
  async function reset() {
    if (busy || !window.confirm("포트폴리오를 초기화할까요?\n\n선택한 위험 수준·Theme·현재 비교 결과가 초기화됩니다. 다시 확정할 때까지 순위에서 빠집니다.\n계정과 참가자 번호, 본인의 가입 자리는 유지되며 다른 참가자에게는 영향이 없습니다.")) return;
    setBusy(true);
    setError("");
    try {
      await post("/api/v1/me/experiment/reset", { confirm: true });
      await qc.cancelQueries();
      qc.removeQueries({ predicate: q => q.queryKey[0] !== "auth-me" });
      router.replace("/setup/portfolio?step=risk");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "초기화하지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setBusy(false);
    }
  }
  return <><button className="btn-secondary" disabled={busy} onClick={reset}>{busy ? "초기화 중…" : "포트폴리오 초기화"}</button>{error && <p role="alert">{error}</p>}</>;
}
