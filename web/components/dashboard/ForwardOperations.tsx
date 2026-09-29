"use client";

import { useQuery } from "@tanstack/react-query";
import { getLedgerAlerts, getLedgerStatus } from "@/lib/api/ledger";
import { assetName } from "@/app/(app)/dashboard/performance-data";
import { fmtDate, fmtPct } from "@/lib/format";
import s from "@/app/(app)/dashboard/dashboard.module.css";

const driftLabel = { WITHIN_BAND: "밴드 이내", OUTSIDE_BAND: "밴드 이탈", UNAVAILABLE: "판정 대기" };
const waitingLabel = {
  NO_VALUATION: "실제 운용 평가 기록을 기다리고 있습니다.",
  INCOMPLETE_VALUATION: "평가가 불완전하거나 가격이 지연되어 매매 판정을 보류합니다.",
  NO_HOLDINGS: "평가일의 실제 보유 내역을 기다리고 있습니다.",
  NO_TARGET: "평가일에 유효한 목표 비중을 기다리고 있습니다.",
};

function eventDetail(detail: Record<string, unknown>) {
  const asset = typeof detail.asset === "string" ? detail.asset : detail.asset_id;
  return [typeof asset === "string" ? assetName(asset) : null,
    typeof detail.order_id === "string" ? `주문 ${detail.order_id}` : null,
    typeof detail.side === "string" ? detail.side.toUpperCase() : null,
    typeof detail.latest_price_date === "string" ? `최근 가격 ${fmtDate(detail.latest_price_date)}` : null,
  ].filter(Boolean).join(" · ");
}

export function ForwardOperations({ latestValuationDate, observations }: {
  latestValuationDate: string | null;
  observations: number | null;
}) {
  const status = useQuery({ queryKey: ["ledger-status"], queryFn: getLedgerStatus });
  const alerts = useQuery({ queryKey: ["ledger-alerts"], queryFn: getLedgerAlerts });
  const data = status.data;
  const rebalance = data?.rebalance;
  const rows = rebalance?.assets ?? [];
  const events = alerts.data?.items ?? [];
  const hasRecords = data?.has_history ?? (observations == null ? null : observations > 0);
  const valuationDate = data?.last_valuation_date ?? latestValuationDate;

  return <section className={s.operations} aria-label="운용 및 리밸런싱 상태">
    <div className={s.sectionHeading}><div><span className={s.eyebrow}>FORWARD OPERATIONS</span><h2>운용 및 리밸런싱 상태</h2><p>사용자별 운용 기록과 실행 이벤트를 표시합니다.</p></div></div>
    <dl className={s.operationGrid}>
      <div><dt>운용 기록</dt><dd>{hasRecords == null ? "확인 중" : hasRecords ? "기록 중" : "운용 기록 대기"}</dd></div>
      <div><dt>마지막 평가일</dt><dd>{valuationDate ? fmtDate(valuationDate) : "대기 중"}</dd></div>
      <div><dt>다음 정기 리밸런싱 (예정)</dt><dd>{data?.next_rebalance_date ? fmtDate(data.next_rebalance_date) : "운용 기록 대기"}</dd></div>
      <div><dt>최근 평가 상태</dt><dd>{rebalance?.nav_status ?? "상태 정보 대기 중"}</dd></div>
      <div><dt>최근 시장 데이터</dt><dd>{data?.latest_price_date ? fmtDate(data.latest_price_date) : "확인 대기 중"}{data?.data_freshness === "STALE" ? " · 가격 지연" : ""}</dd></div>
      <div><dt>첫 평가일</dt><dd>{data?.first_valuation_date ? fmtDate(data.first_valuation_date) : "대기 중"}</dd></div>
    </dl>
    <p>예정일은 정기 운용 일정 기준이며, 휴장일에는 실제 가격이 제공되는 거래일에 체결됩니다.</p>
    {status.isError && <p className={s.infoNote} role="alert">운용 상태를 불러오지 못했습니다. <button onClick={() => status.refetch()}>다시 시도</button></p>}
    <div className={s.operationEvents}><h3>목표 비중과 실제 보유 비중</h3>
      <p>마지막 평가일의 보유 비중과 그날 유효한 목표를 비교합니다.
        {rebalance?.band && ` ${rebalance.band.type === "relative" ? "목표 대비 상대" : "절대"} ±${fmtPct(rebalance.band.threshold)} band 기준입니다.`}
        {rebalance?.target_effective_date && ` 목표 효력일: ${fmtDate(rebalance.target_effective_date)}.`}</p>
      {rebalance && rebalance.status !== "READY" && <p>{waitingLabel[rebalance.status]}</p>}
      {status.isLoading ? <p role="status">비중을 확인하는 중입니다.</p> : rows.length === 0 ? <p>표시할 목표 또는 보유 내역이 없습니다.</p> :
        <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>자산</th><th>목표 비중</th><th>현재 비중</th><th>Drift 상태</th><th>매매 필요</th><th>대기 주문</th></tr></thead><tbody>
          {rows.map(row => <tr key={row.asset_id}><th>{assetName(row.asset_id)}</th><td>{row.target_weight == null ? "—" : fmtPct(row.target_weight)}</td><td>{row.current_weight == null ? "—" : fmtPct(row.current_weight)}</td><td>{driftLabel[row.drift_status]}</td><td>{row.action === "HOLD" ? "유지" : row.action ?? "판정 대기"}</td><td>{row.pending_orders.length ? row.pending_orders.map(order => <div key={order.order_id}>{order.side} · {fmtDate(order.effective_at)}</div>) : "없음"}</td></tr>)}
        </tbody></table></div>}
      <p>매매 필요는 평가일 기준 판정이며, 대기 주문은 이미 생성된 주문입니다.</p>
    </div>
    <div className={s.operationEvents}><h3>최근 리밸런싱·주문 이벤트</h3>
      {alerts.isLoading ? <p role="status">이벤트를 확인하는 중입니다.</p> : alerts.isError ?
        <p role="alert">이벤트를 불러오지 못했습니다. <button onClick={() => alerts.refetch()}>이벤트 다시 시도</button></p> : !events.length ? <p>표시할 운용 이벤트가 없습니다.</p> :
        <ul>{events.map(event => <li key={event.alert_id}><time dateTime={event.occurred_at ?? event.date}>{fmtDate(event.date)}</time><div><strong>{event.title}</strong><p>{eventDetail(event.detail)}</p></div></li>)}</ul>}
    </div>
  </section>;
}
