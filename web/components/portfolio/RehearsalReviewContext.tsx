"use client";
import {useQuery} from "@tanstack/react-query";
import {get} from "@/lib/api/client";
import {fmtDate, fmtPct} from "@/lib/format";
import type {Rehearsal} from "./InvestmentRehearsal";
import type {RehearsalContext} from "@/lib/rehearsal-context";
import s from "./review-flow.module.css";

export function RehearsalReviewContext({decisionId, context}: {decisionId: string; context: RehearsalContext}) {
  const {period, amount} = context;
  const q = useQuery({queryKey:["investment-rehearsal",decisionId,period,amount],
    queryFn:()=>get<Rehearsal>(`/api/v1/me/decisions/${encodeURIComponent(decisionId)}/rehearsal?period=${period}&initial_amount=${amount}`), staleTime:60_000,retry:1});
  const d = q.data;
  return <section className={s.context} aria-label="방금 본 리허설">
    <span className={s.eyebrow}>방금 본 리허설 · 과거 가정 계산</span>
    <h2>이 하락을 겪어도 선택 이유가 유지될까요?</h2>
    {q.isError ? <p role="alert">리허설 결과를 불러오지 못했습니다. <button className="btn-secondary" onClick={()=>q.refetch()}>리허설 다시 조회</button></p>
      : !d ? <p role="status">선택한 기간과 금액을 불러오는 중입니다.</p>
      : d.status !== "AVAILABLE" || !d.base || !d.personalized || !d.period ? <p role="status">비교 자료 미확보 · {d.reason}</p>
      : <><p>{fmtDate(d.period.start)} ~ {fmtDate(d.period.end)} · 각 {d.initial_amount.toLocaleString("ko-KR")}원</p>
        <dl className={s.values}><div><dt>기본 구성 · 최대 낙폭</dt><dd>{fmtPct(d.base.max_drawdown)}</dd></div><div><dt>내 구성 · 최대 낙폭</dt><dd>{fmtPct(d.personalized.max_drawdown)}</dd></div></dl></>}
    <p className={s.note}>실제 운용 성과가 아니며, 미래 손실 한도를 뜻하지 않습니다.</p>
  </section>;
}
