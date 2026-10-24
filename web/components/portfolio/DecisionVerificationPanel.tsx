"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { fmtActivePp, fmtDate, fmtPct } from "@/lib/format";
import { ASSET_META } from "@/app/(app)/setup/portfolio/asset-meta";
import { THEME_INFO } from "@/app/(app)/setup/portfolio/theme-content";
import type { FrontierCoordinate } from "@/app/(app)/setup/portfolio/FrontierChart";
import s from "./decision-verification.module.css";
import {ValuationStatus} from "./ValuationStatus";

type Estimate = { expected_return: number | null; volatility: number | null; weights: Record<string, number> };
export interface DecisionVerification {
  decision_id: string; version: number; confirmed_at: string; effective_date: string;
  reason: string | null; superseded_effective_date: string | null;
  original: {
    base: Estimate; personalized: Estimate;
    frontier: { version: string | null; points: (FrontierCoordinate & { frontier_id: string })[] };
    return_basis: string | null; risk_basis: string | null; price_data_as_of: string | null;
  };
  risk_change?: { status: "AVAILABLE" | "UNAVAILABLE"; base_volatility: number | null;
    personalized_volatility: number | null; difference_pp: number | null; as_of: string | null; method: string | null };
  review_plan?: { basis_date: string; basis: string; checkpoints: { months: 3 | 6;
    date: string; state: "UPCOMING" | "DATA_PENDING" | "DUE" | "RECORDED" | "ENDED" }[] };
  valuation_job?: { status: "running" | "success" | "failed" | "skipped"; scheduled_for: string; completed_at: string | null;
    state?: string; reason_code?: "START_NOT_SCHEDULED" | "AWAITING_T0" | "PARTICIPANTS_NOT_READY" | null; message?: string; execution_succeeded?: boolean; valuation_completed?: boolean;
    valuated?: number | null; ready?: number | null; required?: number | null; retryable?: boolean;
  } | null;
  opening_context?: {forward_start:string;historical_start:string;historical_end:string} | null;
  actual: {
    status: "AVAILABLE" | "UNAVAILABLE"; reason: string | null;
    start: string | null; end: string | null; observations: number; excluded_rows: number;
    personalized_return: number | null; core_return: number | null; difference_pp: number | null;
    personalized_nav: { start: number; end: number } | null; core_nav: { start: number; end: number } | null;
  };
  review: { status: "IN_PROGRESS" | "REVIEW_REQUIRED"; horizon_end: string | null; basis: string;
    choice: { action: "KEEP" | "ADJUST"; reason: string; recorded_at: string } | null };
}

const percent = (value: number | null) => value == null ? "미확보" : fmtPct(value);
const nav = (value: number | undefined) => value == null ? "미확보" : `${value.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`;
const reviewState = {UPCOMING:"점검 예정",DATA_PENDING:"관측 자료 대기",DUE:"재검토 시점",RECORDED:"검토 기록 있음",ENDED:"후속 판단 적용"};

export function DecisionVerificationPanel({ point, data, onClose }: {
  point: "base" | "personalized"; data?: DecisionVerification; onClose: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, [point]);
  const estimate = data?.original[point];
  const actual = data?.actual;
  const choice = data?.review.choice;
  return <aside className={s.panel} aria-labelledby="decision-verification-title" onKeyDown={event => {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }}>
    <header className={s.header}><div><span>{point === "base" ? "Base" : "Personalized"}{data && ` · 판단 ${data.version}`}</span>
      <h3 id="decision-verification-title" ref={heading} tabIndex={-1}>투자 판단 검증</h3></div>
      <button type="button" className={s.close} onClick={onClose} aria-label="투자 판단 검증 닫기"><X size={18}/></button>
    </header>
    <section aria-label="당시 투자 판단"><h4>1. 당시 투자 판단</h4>
      {!data ? <p>확정 당시 판단 기록 미확보</p> : <>
        <dl className={s.metrics}>
          <div><dt>예상 연수익률</dt><dd>{percent(estimate!.expected_return)}</dd></div>
          <div><dt>예상 변동성 · 연율</dt><dd>{percent(estimate!.volatility)}</dd></div>
          <div><dt>판단 날짜 · 한국시간</dt><dd>{new Date(data.confirmed_at).toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}</dd></div>
          <div><dt>효력일</dt><dd>{fmtDate(data.effective_date)}</dd></div>
        </dl>
        <div className={s.riskChange} aria-label="확정 당시 기본 구성 대비 예상 위험 변화">
          <h5>내 선택이 바꾼 예상 위험</h5>
          {data.risk_change?.status === "AVAILABLE" ? <>
            <dl className={s.metrics}>
              <div><dt>기본 구성 · Base</dt><dd>{percent(data.risk_change.base_volatility)}</dd></div>
              <div><dt>내 선택 · Personalized</dt><dd>{percent(data.risk_change.personalized_volatility)}</dd></div>
            </dl>
            <p>기본 구성 대비 <strong>{fmtActivePp(data.risk_change.difference_pp! / 100)}</strong> · 연율화 변동성 추정치</p>
            <small>{fmtDate(data.risk_change.as_of)} 자료 · {data.risk_change.method} 모형</small>
          </> : <p>확정 당시 같은 기준으로 계산한 두 위험 값이 없어 변화량을 표시할 수 없습니다.</p>}
          <p>예상 변동성 변화는 실제 손실이나 향후 수익을 뜻하지 않습니다.</p>
        </div>
        {!Object.values(estimate!.weights).some(value => value > 0) && <p>당시 자산 비중 미확보</p>}
        <dl className={s.weights} aria-label="당시 자산 비중">{Object.entries(estimate!.weights).filter(([, value]) => value > 0).map(([id, weight]) => {
          const raw = id.replace(/^theme:/, "");
          return <div key={id}><dt>{ASSET_META[raw]?.name ?? THEME_INFO[raw]?.name ?? raw}</dt><dd>{fmtPct(weight)}</dd></div>;
        })}</dl>
        {data.reason && <p>선택 근거: {data.reason}</p>}
      </>}
    </section>
    <section aria-label="동일 기간 계좌 성과"><h4>2. 동일 기간 계좌 성과</h4>
      {point === "base" && <p>Base는 선택한 기본 구성입니다. 아래 비교 기준은 별도 CORE 계좌입니다.</p>}
      {actual?.status === "AVAILABLE" ? <>
        <p>{fmtDate(actual.start)}–{fmtDate(actual.end)} · 공통 평가일 {actual.observations}개</p>
        <table className={s.table}><caption>기록된 모의운용 계좌 NAV 기준 · 공통 첫 평가일 대비</caption><thead><tr><th scope="col">계좌</th><th scope="col">기간 수익률</th></tr></thead>
          <tbody><tr><th scope="row">Personalized</th><td>{fmtPct(actual.personalized_return)}</td></tr><tr><th scope="row">CORE</th><td>{fmtPct(actual.core_return)}</td></tr><tr><th scope="row">차이</th><td>{fmtActivePp(actual.difference_pp)}</td></tr></tbody></table>
        <p className={s.nav}>Personalized NAV: {nav(actual.personalized_nav?.start)} → {nav(actual.personalized_nav?.end)}<br/>CORE NAV: {nav(actual.core_nav?.start)} → {nav(actual.core_nav?.end)}</p>
      </> : <p>성과 비교 미확보{actual?.reason && ` · ${actual.reason}`}</p>}
      <p>화면이 열려 있는 동안 1분마다 저장된 평가 결과를 다시 조회합니다.</p>
      {data && <ValuationStatus job={data.valuation_job}/>}
      {data?.opening_context&&<p>{fmtDate(data.opening_context.forward_start)}부터 과거 재현의 보유자산·현금을 승계한 모의운용입니다. 이 비교에는 시작일 이후의 정상 NAV만 포함하며 과거 재현 수익률은 포함하지 않습니다.</p>}
      <p>개별 계좌 성과는 위의 공통 정상 NAV 기록을 기준으로 합니다.</p>
      {!!actual?.excluded_rows && <p>정상 평가 조건을 충족하지 않은 NAV {actual.excluded_rows}건 제외</p>}
    </section>
    <section aria-label="당시 가정의 재검토"><h4>3. 당시 가정의 재검토</h4>
      <strong className={s.status}>{data?.review.status === "REVIEW_REQUIRED" ? "재검토 필요" : "검증 진행 중"}</strong>
      <p>{data?.review.basis ?? "당시 가정과 이후 관측을 연결할 판단 기록이 필요합니다."}</p>
      {data && <>
        {point === "personalized" ? <>
          <p>{data.original.return_basis?.includes("themes inherit") ? "테마의 독립 전망은 적용하지 않고 조달한 주식의 기대수익률을 사용했습니다." : data.original.return_basis ? `기대수익률 산출 근거: ${data.original.return_basis}` : "기대수익률의 당시 산출 근거 미확보"}</p>
          <p>{data.original.risk_basis === "5Y weekly Ledoit-Wolf annualized covariance" ? "변동성은 최근 5년 주간 수익률의 Ledoit–Wolf 공분산을 연율화해 추정했습니다." : data.original.risk_basis ? `변동성 산출 근거: ${data.original.risk_basis}` : "변동성의 당시 산출 근거 미확보"}</p>
        </> : <p>Base는 확정 당시 선택한 기본 구성의 저장값입니다. 아래 예상 기간은 Personalized 판단 기준입니다.</p>}
        <p>자료 기준일: {data.original.price_data_as_of ? fmtDate(data.original.price_data_as_of) : "미확보"}{data.review.horizon_end && <><br/>당시 예상 기간 종료일: {fmtDate(data.review.horizon_end)}</>}</p>
        {data.review_plan && <div className={s.reviewPlan} aria-label="재검토 일정">
          <h5>언제 다시 살펴볼까요?</h5>
          <p>{fmtDate(data.review_plan.basis_date)} 기준 달력상 점검일입니다. 점검일이 왔다고 판단의 적중 여부가 정해지지는 않습니다.</p>
          <ul>{data.review_plan.checkpoints.map(item => <li key={item.months}>
            <span>{item.months}개월 점검 · {fmtDate(item.date)}</span><strong>{reviewState[item.state]}</strong>
          </li>)}</ul>
          <p>선택 이유나 감수할 수 있는 위험이 달라졌다면 날짜 전에도 근거를 검토하세요. 이 변화는 자동으로 감지하지 않습니다.</p>
        </div>}
        {choice ? <p>사용자 재검토: {choice.action === "KEEP" ? "유지" : "재설계 검토"} · {fmtDate(choice.recorded_at)}<br/>{choice.reason}</p> : <p>사용자 재검토 기록 미확보</p>}
        <p><Link href={`/review?decision_id=${encodeURIComponent(data.decision_id)}`}>이 판단의 검토 기록 보기</Link></p>
        {data.superseded_effective_date && <p>{fmtDate(data.superseded_effective_date)}부터 후속 판단이 적용되어 관측 구간을 종료했습니다.</p>}
      </>}
    </section>
  </aside>;
}
