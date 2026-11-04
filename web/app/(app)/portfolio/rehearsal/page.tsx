"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { LoadingSkeleton } from "@/components/shared/ui";
import { InvestmentRehearsal } from "@/components/portfolio/InvestmentRehearsal";

import {readRehearsalContext} from "@/lib/rehearsal-context";

function Content() {
  const params = useSearchParams();
  const decisionId = params.get("decision_id"), context = readRehearsalContext(params);
  return <AppShell headerTitle="내 투자 리허설" hideDesignNotice softBackground>{decisionId ? <InvestmentRehearsal key={`${decisionId}:${context.period}:${context.amount}`} decisionId={decisionId} initialContext={context}/> :
    <div role="status"><p>내 포트폴리오에서 저장된 판단을 선택해 리허설을 열어 주세요.</p><Link className="btn-secondary" href="/portfolio">내 포트폴리오</Link></div>}</AppShell>;
}
export default function RehearsalPage() { return <Suspense fallback={<LoadingSkeleton rows={4}/>}><Content/></Suspense>; }
