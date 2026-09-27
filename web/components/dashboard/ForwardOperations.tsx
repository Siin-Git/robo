"use client";

import { useQuery } from "@tanstack/react-query";
import { getForwardSystemStatus, getLedgerAlerts, getLedgerStatus } from "@/lib/api/ledger";
import { fmtDate } from "@/lib/format";
import s from "@/app/(app)/dashboard/dashboard.module.css";

export function ForwardOperations({ latestValuationDate, observations }: {
  latestValuationDate: string | null;
  observations: number | null;
}) {
  const status = useQuery({ queryKey: ["ledger-status"], queryFn: getLedgerStatus, retry: false });
  const alerts = useQuery({ queryKey: ["ledger-alerts"], queryFn: getLedgerAlerts, retry: false });
  const system = useQuery({ queryKey: ["forward-system-status"], queryFn: getForwardSystemStatus });
  const ledger = status.data;
  const hasRecords = ledger?.has_records ?? (observations == null ? null : observations > 0);
  const valuationDate = ledger?.latest_valuation_date ?? latestValuationDate;

  return <section className={s.operations} aria-label="운용 및 리밸런싱 상태">
    <div className={s.sectionHeading}><div><span className={s.eyebrow}>FORWARD OPERATIONS</span><h2>운용 및 리밸런싱 상태</h2><p>사용자별 운용 기록과 실행 이벤트를 표시합니다.</p></div></div>
    <dl className={s.operationGrid}>
      <div><dt>운용 기록</dt><dd>{hasRecords == null ? "확인 중" : hasRecords ? "기록 중" : "선택 기간 평가 기록 대기"}</dd></div>
      <div><dt>마지막 평가일</dt><dd>{valuationDate ? fmtDate(valuationDate) : "대기 중"}</dd></div>
      <div><dt>다음 정기 리밸런싱</dt><dd>{ledger?.next_rebalance_date ? fmtDate(ledger.next_rebalance_date) : "일정 정보 대기 중"}</dd></div>
      <div><dt>데이터 상태</dt><dd>{ledger?.data_freshness ?? "상태 정보 대기 중"}</dd></div>
      <div><dt>시스템 최근 시장 데이터</dt><dd>{system.data?.latest_market_data_date ? fmtDate(system.data.latest_market_data_date) : "확인 대기 중"}</dd></div>
      <div><dt>시스템 Forward 시작</dt><dd>{system.data?.forward_test_inception_at ? fmtDate(system.data.forward_test_inception_at) : "시작 정보 대기 중"}</dd></div>
    </dl>
    {status.data === null && <p className={s.infoNote}>사용자별 운용 상세 상태 API 연결 대기 중입니다.</p>}
    {status.isError && <p className={s.infoNote} role="alert">운용 상세 상태를 불러오지 못했습니다. <button onClick={() => status.refetch()}>다시 시도</button></p>}
    <div className={s.operationEvents}><h3>리밸런싱·매매 이벤트</h3>
      {alerts.isLoading ? <p role="status">이벤트를 확인하는 중입니다.</p> : alerts.isError ?
        <p role="alert">이벤트를 불러오지 못했습니다. <button onClick={() => alerts.refetch()}>다시 시도</button></p> :
        alerts.data === null ? <p>이벤트 API 연결 대기 중입니다.</p> :
        !alerts.data?.items.length ? <p>표시할 실행 이벤트가 없습니다.</p> :
        <ul>{alerts.data.items.map((event, index) => <li key={event.id ?? `${event.type}-${event.date}-${index}`} data-severity={event.severity}>
          <time dateTime={event.date}>{fmtDate(event.date)}</time><div><strong>{event.title}</strong><small>{event.type} · {event.severity}</small><p>{event.detail}</p></div>
        </li>)}</ul>}
    </div>
  </section>;
}
