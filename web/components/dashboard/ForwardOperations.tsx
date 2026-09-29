"use client";

import { useQuery } from "@tanstack/react-query";
import { getForwardLedger, getForwardSystemStatus } from "@/lib/api/ledger";
import { get } from "@/lib/api/client";
import { assetName } from "@/app/(app)/dashboard/performance-data";
import { fmtDate, fmtPct } from "@/lib/format";
import s from "@/app/(app)/dashboard/dashboard.module.css";

type Target = { personalized: { weights: { asset_id: string; weight: number }[] } };
const assetKey = (id: string) => id.replace(/^theme:/, "");

export function ForwardOperations({ latestValuationDate, observations }: {
  latestValuationDate: string | null;
  observations: number | null;
}) {
  const ledger = useQuery({ queryKey: ["forward-ledger"], queryFn: getForwardLedger });
  const target = useQuery({ queryKey: ["summary-portfolio"], queryFn: () => get<Target>("/api/v1/me/portfolio/summary") });
  const system = useQuery({ queryKey: ["forward-system-status"], queryFn: getForwardSystemStatus });
  const snapshot = ledger.data?.snapshots.at(-1);
  const holdings = new Map(snapshot?.holdings.map(row => [assetKey(row.asset_id), row.weight]) ?? []);
  const targets = target.data?.personalized.weights ?? [];
  const rows = [...targets, ...(snapshot?.holdings.filter(row => !targets.some(t => assetKey(t.asset_id) === assetKey(row.asset_id))) ?? [])]
    .map(row => ({ id: assetKey(row.asset_id), target: targets.find(t => assetKey(t.asset_id) === assetKey(row.asset_id))?.weight ?? null,
      current: holdings.get(assetKey(row.asset_id)) ?? null }));
  const pending = new Map(ledger.data?.orders.filter(order => order.action_required).map(order => [assetKey(order.asset_id), order.side]) ?? []);
  const events = [
    ...(ledger.data?.orders.map(order => ({ id: order.order_id, date: order.submitted_at, title: `${assetName(order.asset_id)} ${order.side.toUpperCase()} 주문`, detail: `${order.status} · 실행 예정 ${fmtDate(order.effective_at)}` })) ?? []),
    ...(ledger.data?.trades.map(trade => ({ id: trade.trade_id, date: trade.execution_at, title: `${assetName(trade.asset_id)} 체결`, detail: `주문 ${trade.order_id}` })) ?? []),
  ].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
  const hasRecords = ledger.data ? ledger.data.snapshots.length > 0 : observations == null ? null : observations > 0;
  const valuationDate = ledger.data?.as_of ?? latestValuationDate;

  return <section className={s.operations} aria-label="운용 및 리밸런싱 상태">
    <div className={s.sectionHeading}><div><span className={s.eyebrow}>FORWARD OPERATIONS</span><h2>운용 및 리밸런싱 상태</h2><p>사용자별 운용 기록과 실행 이벤트를 표시합니다.</p></div></div>
    <dl className={s.operationGrid}>
      <div><dt>운용 기록</dt><dd>{hasRecords == null ? "확인 중" : hasRecords ? "기록 중" : "운용 기록 대기"}</dd></div>
      <div><dt>마지막 평가일</dt><dd>{valuationDate ? fmtDate(valuationDate) : "대기 중"}</dd></div>
      <div><dt>다음 정기 리밸런싱</dt><dd>일정 API 대기 중</dd></div>
      <div><dt>최근 평가 상태</dt><dd>{snapshot?.nav_status ?? "상태 정보 대기 중"}</dd></div>
      <div><dt>시스템 최근 시장 데이터</dt><dd>{system.data?.latest_market_data_date ? fmtDate(system.data.latest_market_data_date) : "확인 대기 중"}</dd></div>
      <div><dt>시스템 Forward 시작</dt><dd>{system.data?.forward_test_inception_at ? fmtDate(system.data.forward_test_inception_at) : "시작 정보 대기 중"}</dd></div>
    </dl>
    {(ledger.isError || target.isError) && <p className={s.infoNote} role="alert">운용 내역 또는 목표 비중을 불러오지 못했습니다. <button onClick={() => { ledger.refetch(); target.refetch(); }}>다시 시도</button></p>}
    <div className={s.operationEvents}><h3>목표 비중과 실제 보유 비중</h3>
      <p>목표는 저장된 설계 구성, 현재는 마지막 Forward 평가일의 실제 보유 비중입니다. 상대 ±10% drift 판정은 백엔드 상태 API 연결 대기 중입니다.</p>
      {ledger.isLoading || target.isLoading ? <p role="status">비중을 확인하는 중입니다.</p> : rows.length === 0 ? <p>표시할 목표 또는 보유 내역이 없습니다.</p> :
        <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>자산</th><th>목표 비중</th><th>현재 비중</th><th>Drift 상태</th><th>매수/매도</th></tr></thead><tbody>
          {rows.map(row => <tr key={row.id}><th>{assetName(row.id)}</th><td>{row.target == null ? "—" : fmtPct(row.target)}</td><td>{row.current == null ? "—" : fmtPct(row.current)}</td><td>판정 대기</td><td>{pending.get(row.id)?.toUpperCase() ?? "필요 여부 대기"}</td></tr>)}
        </tbody></table></div>}
      {pending.size > 0 && <p>BUY / SELL은 백엔드가 생성한 대기 주문만 표시합니다. 새로운 주문 필요 여부는 아직 제공되지 않습니다.</p>}
    </div>
    <div className={s.operationEvents}><h3>최근 리밸런싱·주문 이벤트</h3>
      {ledger.isLoading ? <p role="status">이벤트를 확인하는 중입니다.</p> : ledger.isError ?
        <p role="alert">이벤트를 불러오지 못했습니다.</p> : !events.length ? <p>표시할 주문·체결 이벤트가 없습니다.</p> :
        <ul>{events.map(event => <li key={event.id}><time dateTime={event.date}>{fmtDate(event.date)}</time><div><strong>{event.title}</strong><p>{event.detail}</p></div></li>)}</ul>}
    </div>
  </section>;
}
