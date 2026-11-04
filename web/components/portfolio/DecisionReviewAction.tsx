"use client";
import {useEffect,useRef,useState} from "react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {useMutation,useQueryClient} from "@tanstack/react-query";
import {saveChoice,type Decision} from "@/lib/api/decisions";
import s from "./review-flow.module.css";

// Key this component by decision_id: a draft must never carry into another decision.
export function DecisionReviewAction({decision,returnHref}:{decision:Decision;returnHref?:string}) {
  const router=useRouter(),cache=useQueryClient();
  const [reason,setReason]=useState("");
  const request=useRef<{key:string;payload:string}|null>(null);
  const active=useRef(true),feedback=useRef<HTMLDivElement>(null);
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  const choice=useMutation({mutationFn:(action:"KEEP"|"ADJUST")=>{
    const payload=JSON.stringify([decision.decision_id,decision.target_id,action,reason.trim()]);
    if(request.current?.payload!==payload)request.current={key:crypto.randomUUID(),payload};
    return saveChoice({decision_id:decision.decision_id,target_id:decision.target_id,action,reason:reason.trim(),request_key:request.current.key});
  },onSuccess:c=>{
    cache.invalidateQueries({queryKey:["portfolio-choices"]});
    cache.invalidateQueries({queryKey:["decision-verification",c.decision_id]});
    if(active.current&&c.action==="ADJUST")router.push(`/setup/portfolio?adjustment_choice_id=${encodeURIComponent(c.choice_id)}&step=risk`);
  }});
  useEffect(()=>{if(choice.isSuccess&&choice.data.action==="KEEP")feedback.current?.focus();},[choice.isSuccess,choice.data]);
  return <section className={s.action} aria-labelledby="review-action-title">
    <span className={s.eyebrow}>내 판단 남기기</span><h2 id="review-action-title">무엇을 근거로 유지하거나 다시 검토하나요?</h2>
    <p className={s.original}>확정 당시 이유: {decision.reason||"저장된 이유 없음"}</p>
    <p id="review-reason-help">선택 이유가 지금도 유효한지, 어떤 조건이 달라지면 다시 살펴볼지 적어 주세요. 이번 기록은 최초 판단을 덮어쓰지 않습니다.</p>
    <label className={s.reason}>이번 검토 이유<textarea aria-label="선택 이유" aria-describedby="review-reason-help" maxLength={1024} value={reason} disabled={choice.isPending}
      placeholder="유지하거나 재검토하려는 근거와, 더 확인할 내용을 적어 주세요."
      onChange={e=>{setReason(e.target.value);if(!choice.isPending)choice.reset();}}/></label>
    <div className={s.actions}><button className="btn-primary" disabled={!reason.trim()||choice.isPending} onClick={()=>choice.mutate("KEEP")}>구성 유지 선택</button>
      <button className="btn-secondary" disabled={!reason.trim()||choice.isPending} onClick={()=>choice.mutate("ADJUST")}>조정 검토 · 재설계</button></div>
    <p className={s.note}>유지하면 현재 목표와 정기 운용을 이어갑니다. 조정은 새 설계로 이동하며, 새 확정 전에는 목표가 바뀌지 않습니다. 대기 주문이 있으면 재확정이 제한될 수 있습니다.</p>
    {choice.isPending&&<p role="status">검토 이유를 저장하고 있습니다.</p>}
    {choice.isError&&<p role="alert">{choice.error.message}</p>}
    {choice.isSuccess&&choice.data.action==="KEEP"&&<div ref={feedback} className={s.saved} tabIndex={-1} role="status"><p>유지 선택을 저장했습니다. 목표 유지 · 정기 운용 계속</p>{returnHref&&<Link href={returnHref}>같은 조건의 리허설로 돌아가기 →</Link>}</div>}
  </section>;
}
