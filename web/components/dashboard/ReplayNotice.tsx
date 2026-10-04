"use client";
import {useQuery} from "@tanstack/react-query";
import {useSearchParams,usePathname} from "next/navigation";
import Link from "next/link";
import {get} from "@/lib/api/client";
import type {ReplayContext} from "@/app/(app)/dashboard/performance-data";

export function useLocalReplay() {
  return useQuery({queryKey:["local-replay-context"],queryFn:()=>get<{enabled:boolean;replay_context:ReplayContext|null}>("/api/v1/me/performance/replay"),refetchInterval:15_000});
}
export function ReplayNotice() {
  const query=useLocalReplay();
  const params=useSearchParams(),pathname=usePathname();
  if(!query.data?.enabled)return null;
  if(params?.get("source")==="demo"||pathname==="/strategies")return <aside role="status" className="mb-5 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm leading-6">이 화면은 기존 과거 가격 비교·연구 자료입니다. 15명 경쟁 재생 원장과 별도이며 실제 forward 실적이 아닙니다. <Link href="/dashboard">15명 경쟁 재생 성과 보기</Link></aside>;
  const run=query.data.replay_context;
  return <aside className="mb-5 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm leading-6" role="status" aria-label="로컬 과거 재생 시연">
    <strong>{run?.label??"로컬 시연 참가자 준비 중 · 과거 가격 모의실험"}</strong>
    {run&&<><p>시연용 설정 · READY {run.ready}/{run.required} · 처리 {run.completed}/{run.required} · {run.status==="COMPLETE"?"전체 재생 완료":"재생 미완료 · 순위 보류"}</p>
      <p>공통 기간 {run.start} — {run.end} · 누락을 제외한 공통 관측일 {run.dates.length}개 (연속 10거래일 아님) · 동일 초기 가상 투자금 {run.initial_capital_krw.toLocaleString("ko-KR")}원</p>
      {!!run.excluded_dates.length&&<details><summary>원본 가격 누락으로 제외한 날짜 확인</summary><ul>{run.excluded_dates.map(d=><li key={d.date}>{d.date}: {d.missing_assets.join(", ")} · 이전 가격으로 채우지 않음</li>)}</ul></details>}</>}
    <p>현재 구성을 과거에 알았다고 가정한 계산입니다. 시작 이후 실제 forward 성과나 3개월·6개월 추적 실적이 아닙니다. 최초 판단 검토는 별도 실제 운용 기록을 조회합니다.</p>
    <p>준비 시점의 확정 구성을 고정한 실행입니다. 재설계 후 확정한 구성은 새 재생 실행에 반영해야 합니다.</p>
  </aside>;
}
