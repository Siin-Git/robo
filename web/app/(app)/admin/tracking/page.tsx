"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { PerformanceChart, MY_LINE } from "@/components/dashboard/PerformanceChart";
import { assetName } from "@/app/(app)/dashboard/performance-data";
import { fmtPct, fmtDate } from "@/lib/format";
import { getTrackingDecisions, getTrackingReport, saveTrackingReview, TrackingReview } from "@/lib/api/internal-tracking";
import s from "@/app/(app)/dashboard/dashboard.module.css";

export default function InternalTrackingPage() {
  const cache = useQueryClient();
  const decisions = useQuery({ queryKey: ["internal-decisions"], queryFn: getTrackingDecisions, retry: false });
  const [selected, setSelected] = useState("");
  const [assetId, setAssetId] = useState("");
  const [reason, setReason] = useState("");
  const [action, setAction] = useState<TrackingReview["action"]>("KEEP_OBSERVING");
  const request = useRef<{ payload: string; key: string } | null>(null);
  const id = selected || decisions.data?.items[0]?.decision_id;
  const report = useQuery({ queryKey: ["internal-tracking", id], queryFn: () => getTrackingReport(id!), enabled: !!id,
    refetchInterval: 15000, retry: false });
  const data = report.data;
  const asset = data?.assets.find(a => a.asset_id === assetId)
    ?? data?.assets.find(a => a.asset_id !== "cash" && a.observations >= 2)
    ?? data?.assets.find(a => a.asset_id !== "cash" && a.confirmed_weight > 0)
    ?? data?.assets[0];
  const save = useMutation({ mutationFn: () => {
    const payload = JSON.stringify([id, asset?.asset_id, action, reason.trim()]);
    if (request.current?.payload !== payload) request.current = { payload, key: crypto.randomUUID() };
    return saveTrackingReview(id!, { asset_id: asset!.asset_id, action, reason: reason.trim(), request_key: request.current.key });
  }, onSuccess: () => cache.invalidateQueries({ queryKey: ["internal-tracking", id] }) });
  const denied = (decisions.error as { status?: number })?.status === 403 || (report.error as { status?: number })?.status === 403;
  return <AppShell headerTitle="내부 판단 추적" softBackground><div className={`${s.page} review-workspace`}>
    <header className={s.header}><div><h1>내부 판단 추적</h1><p>관리자 전용 · 최초 판단과 이후 관측을 자산별로 검토합니다.</p></div><Link href="/admin">관리 화면으로</Link></header>
    {denied ? <p role="alert">관리자 권한이 필요합니다. 내부 추적 자료를 조회할 수 없습니다.</p> : <>
      {decisions.isLoading && <p role="status">판단 목록을 확인하고 있습니다.</p>}
      {decisions.isError && <p role="alert">판단 목록 조회 실패 <button onClick={() => decisions.refetch()}>다시 시도</button></p>}
      {decisions.data?.items.length === 0 && <p>확정된 판단이 없습니다. 새 확정부터 당시 자산별 예상값을 보관합니다.</p>}
      {!!decisions.data?.items.length && <label>추적할 판단 <select className="input" aria-label="추적할 판단" style={{ maxWidth: "100%" }} value={id}
        onChange={e => { setSelected(e.target.value); setAssetId(""); setReason(""); save.reset(); }}>
        {decisions.data.items.map(d => <option key={d.decision_id} value={d.decision_id}>{d.participant_id} · v{d.version} · {d.effective_date}</option>)}
      </select></label>}
      {report.isLoading && !!id && <p role="status">관측 기록을 확인하고 있습니다.</p>}
      {report.isError && <p role="alert">추적 자료 조회 실패 <button onClick={() => report.refetch()}>다시 조회</button></p>}
      {data && <>
        <p role="status">확정 이후 운용 DB의 관측 기록을 조회합니다. 과거 가격 재생은 이 추적과 3·6개월 관측에 포함하지 않습니다.</p>
        {data.data_kind === "TEST_FIXTURE" && <p className={`${s.exampleBanner} ${s.fixtureBanner}`} role="status">검증용 합성 데이터 · 실제 운용 성과가 아닙니다.</p>}
        <section className={s.operations}><h2>고정된 최초 판단 · v{data.version}</h2>
          <p>효력일 {fmtDate(data.window_start)} · 관측 종료 경계 {fmtDate(data.window_end_exclusive)} 미포함 · 조회 기준 {fmtDate(data.as_of)}</p>
          <p>{data.window_status === "AWAITING_EFFECTIVE_DATE" ? "효력 발생 대기" : data.window_status === "SUPERSEDED" ? "이전 판단의 관측 구간" : "현재 판단의 관측 구간"}</p>
          {data.snapshot ? <>
            <p>확정 당시 연간 포트폴리오 예상 수익률 {fmtPct(data.portfolio_expectations.expected_return?.value)} · 예상 변동성 {fmtPct(data.portfolio_expectations.volatility?.value)}</p>
            <p>Frontier {data.snapshot.frontier.version} · 위험 데이터 기준일 {data.snapshot.risk_data_as_of ?? "미기록"}</p>
            <details><summary>확정 당시 Frontier 좌표 ({data.snapshot.frontier.points.length}개)</summary>
              <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>점</th><th>예상 수익률 · 연율</th><th>예상 변동성 · 연율</th></tr></thead><tbody>
                {data.snapshot.frontier.points.map(p => <tr key={p.frontier_id}><th>{p.frontier_id}</th><td>{fmtPct(p.expected_return)}</td><td>{fmtPct(p.volatility)}</td></tr>)}
              </tbody></table></div>
            </details>
          </> : <p>당시 자산별 예상값을 저장하지 않은 판단입니다. 현재 모형으로 과거 예상값을 복원하지 않습니다.</p>}
          <details><summary>모형·자료 근거</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(data.provenance, null, 2)}</pre></details>
        </section>
        <section className={s.operations}><h2>자산별 추적</h2>
          <p>연간 예상값, 시장 가격 변화, 모의운용 원장의 수익 기여도를 각각 표시합니다. 3·6개월 예상 기준이 정해지지 않아 예상과 실제의 차이는 보류합니다.</p>
          <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>자산</th><th>확정 비중</th><th>최초 예상 수익률 · 연율</th><th>최초 예상 변동성 · 연율</th><th>관측 가격 수익률</th><th>원장 기여도 · %p</th><th>가격 관측 수</th></tr></thead><tbody>
            {data.assets.map(a => <tr key={a.asset_id}><th><button onClick={() => { setAssetId(a.asset_id); setReason(""); save.reset(); }}>{assetName(a.asset_id)}</button></th><td>{fmtPct(a.confirmed_weight)}</td>
              <td>{a.initial_estimate ? fmtPct(a.initial_estimate.expected_return) : "최초 값 미기록"}</td><td>{fmtPct(a.initial_estimate?.volatility)}</td>
              <td>{a.price_status === "NOT_APPLICABLE_CASH" ? "현금 가격 수익률 없음" : fmtPct(a.cumulative_price_return)}</td><td>{a.ledger_contribution == null ? data.actual_ledger.observations < 2 ? "평가 기록 부족" : "원장 항목 없음" : `${(a.ledger_contribution * 100).toFixed(2)}%p`}</td><td>{a.observations}</td></tr>)}
          </tbody></table></div>
          <p>원장 관측 구간 {data.actual_ledger.start ?? "대기"} — {data.actual_ledger.end ?? "대기"} · 평가 {data.actual_ledger.observations}건 · 누적 수익률 {fmtPct(data.actual_ledger.metrics.cumulative_return)} · 실현 변동성 · 연율 {fmtPct(data.actual_ledger.metrics.volatility)}</p>
        </section>
        {asset && <section className={s.operations}><h2>{assetName(asset.asset_id)} 관측과 검토</h2>
          <label>추적할 자산 <select className="input" aria-label="추적할 자산" value={asset.asset_id} onChange={e => { setAssetId(e.target.value); setReason(""); save.reset(); }}>
            {data.assets.map(a => <option key={a.asset_id} value={a.asset_id}>{assetName(a.asset_id)}</option>)}
          </select></label>
          <p>시장 가격 관측 {asset.observed_start ?? "없음"} — {asset.observed_end ?? "없음"}. 원장 기여도 관측 {asset.ledger_observation_start ?? "없음"} — {asset.ledger_observation_end ?? "없음"}.</p>
          {asset.initial_estimate?.independent_theme_forecast === false && <p>테마의 예상 수익률은 조달원인 주식 자산군의 예상값을 사용합니다. 독립적인 테마 전망은 아닙니다.</p>}
          {!!asset.missing_price_dates.length && <p role="status">공통 가격 저장일 중 {asset.missing_price_dates.length}일의 이 자산 가격이 누락되었습니다. 그래프의 결측 구간은 연결하지 않습니다.</p>}
          {!!asset.invalid_price_dates.length && <p role="alert">유효하지 않은 가격 {asset.invalid_price_dates.length}건을 계산에서 제외했습니다.</p>}
          {asset.observations >= 2 ? <PerformanceChart data={asset.price_curve.map(p => ({ date: p.date, index100: p.index100 }))}
            series={[{ key: "price", dataKey: "index100", label: "저장된 시장 가격 · 최초 관측 100", ...MY_LINE }]}
            connectNulls={false} animate={false} curve="linear" showPoints height={280} /> : <p>{asset.price_status === "NOT_APPLICABLE_CASH" ? "현금에는 시장 가격 그래프를 만들지 않습니다." : "가격 기록 2건 이상이 쌓이면 변화 추이를 표시합니다."}</p>}
          <p>가격 그래프는 저장된 원화 수준의 변화이며 거래 비용을 포함한 계좌 수익률과 다릅니다.</p>
          {asset.horizons.map(h => <p key={h.months}>{h.months}개월 추적 · {h.status === "NOT_APPLICABLE" ? "현금은 시장 가격 추적 대상이 아닙니다" : <>{h.due_basis === "FIRST_OBSERVED_PRICE" ? "첫 가격 관측 기준" : "효력일 기준 잠정"} {fmtDate(h.due_date)} · {h.status === "REACHED" ? `관측 가격 수익률 ${fmtPct(h.cumulative_price_return)}` : "기간 미도달"}</>}</p>)}
          <p>예상·실제 차이: {asset.comparison.reason === "ORIGINAL_ASSET_EXPECTATIONS_NOT_RECORDED" ? "최초 값 미기록으로 비교 보류" : "동일 기간·산출 정의가 정해지지 않아 비교 보류"}</p>
          <label>검토 방향 <select className="input" aria-label="검토 방향" value={action} onChange={e => setAction(e.target.value as TrackingReview["action"])}>
            <option value="KEEP_OBSERVING">관측 계속</option><option value="REVISION_REVIEW">Revision 검토 필요</option>
          </select></label>
          <label>검토 근거 <textarea className="input" aria-label="검토 근거" maxLength={1024} style={{ display: "block", width: "100%", minHeight: 90 }} value={reason} onChange={e => setReason(e.target.value)} /></label>
          <p>검토 기록을 추가합니다. 판단·모형·주문은 변경되지 않습니다.</p>
          <button className="btn-primary" disabled={!reason.trim() || save.isPending} onClick={() => save.mutate()}>내부 검토 기록 저장</button>
          {save.isError && <p role="alert">{save.error.message}</p>}{save.isSuccess && <p role="status">내부 검토 기록을 저장했습니다.</p>}
        </section>}
        <section className={s.operations}><h2>내부 검토 이력</h2>{data.reviews.length ? <ul>{data.reviews.map(r => <li key={r.review_id}>
          <strong>{assetName(r.asset_id)} · {r.action === "REVISION_REVIEW" ? "Revision 검토 필요" : "관측 계속"}</strong>
          <p>{r.recorded_at} · 검토자 {r.reviewer_id} · 당시 가격 관측 {r.observation.observations}건</p><p>{r.reason}</p>
        </li>)}</ul> : <p>저장된 내부 검토 기록이 없습니다.</p>}</section>
      </>}
    </>}
  </div></AppShell>;
}
