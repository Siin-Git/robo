"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { fmtActivePp, fmtDate, fmtPct } from "@/lib/format";
import { ASSET_META } from "@/app/(app)/setup/portfolio/asset-meta";
import { THEME_INFO } from "@/app/(app)/setup/portfolio/theme-content";
import type { FrontierCoordinate } from "@/app/(app)/setup/portfolio/FrontierChart";
import s from "./decision-verification.module.css";

type Estimate = { expected_return: number | null; volatility: number | null; weights: Record<string, number> };
export interface DecisionVerification {
  decision_id: string; version: number; confirmed_at: string; effective_date: string;
  reason: string | null; superseded_effective_date: string | null;
  original: {
    base: Estimate; personalized: Estimate;
    frontier: { version: string | null; points: (FrontierCoordinate & { frontier_id: string })[] };
    return_basis: string | null; risk_basis: string | null; price_data_as_of: string | null;
  };
  valuation_job?: { status: "running" | "success" | "failed" | "skipped"; scheduled_for: string; completed_at: string | null } | null;
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
      <p>화면이 열려 있는 동안 1분마다 저장된 평가 결과를 확인합니다.</p>
      {data && <p>{data.valuation_job ? `전체 계좌 평가 작업 · ${fmtDate(data.valuation_job.scheduled_for)} · ${{running:"진행 중",success:"완료",failed:"실패",skipped:"건너뜀"}[data.valuation_job.status]}` : "자동 평가 작업 기록 미확보"}<br/>개별 계좌 성과의 확보 여부는 위 NAV 기록을 기준으로 합니다.</p>}
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
        {choice ? <p>사용자 재검토: {choice.action === "KEEP" ? "유지" : "재설계 검토"} · {fmtDate(choice.recorded_at)}<br/>{choice.reason}</p> : <p>사용자 재검토 기록 미확보</p>}
        <p><Link href={`/review?decision_id=${encodeURIComponent(data.decision_id)}`}>이 판단의 검토 기록 보기</Link></p>
        {data.superseded_effective_date && <p>{fmtDate(data.superseded_effective_date)}부터 후속 판단이 적용되어 관측 구간을 종료했습니다.</p>}
      </>}
    </section>
  </aside>;
}
