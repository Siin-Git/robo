"use client";
import { useQuery } from '@tanstack/react-query';
import { getForwardLedger } from '@/lib/api/ledger';
import { assetName } from '@/app/(app)/dashboard/performance-data';
import { fmtPct, fmtDate } from '@/lib/format';
import s from '@/app/(app)/dashboard/dashboard.module.css';
const money=(n:number|null|undefined)=>n==null?'—':`${n.toLocaleString('ko-KR',{maximumFractionDigits:0})}원`;
export function LedgerHistory(){
  const q=useQuery({queryKey:['forward-ledger'],queryFn:getForwardLedger});
  const l=q.data, latest=l?.snapshots?.at(-1);
  return <section className={s.operations} aria-label="운용 원장"><h2>운용 원장 · 보유자산과 History</h2>
    {q.isError?<p role="alert">원장을 불러오지 못했습니다. <button onClick={()=>q.refetch()}>원장 다시 조회</button></p>:q.isLoading?<p>운용 기록 조회 중</p>:<>
    <p>{l?.data_kind === "TEST_FIXTURE" && <strong>검증용 합성 데이터 · 실제 운용 기록 아님 · </strong>}평가일 {latest?fmtDate(latest.date):'첫 체결·평가 대기'} · 원화 평가액 {money(latest?.nav)} · 현금 {money(latest?.cash_balance)} · 기준 100 NAV {latest?.nav_base100?.toFixed(2)??'—'}</p>
    <p>금액은 원화, NAV 지수는 기준 100, 비중과 수익률은 백엔드가 반환한 비율입니다. 모의운용 기록이며 실제 증권 계좌가 아닙니다.</p>
    <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>보유자산</th><th>수량</th><th>원화 평가액</th><th>현재 비중</th><th>적용 가격일</th><th>가격 상태</th></tr></thead><tbody>{latest?.holdings.map(h=><tr key={h.asset_id}><th>{assetName(h.asset_id)}</th><td>{h.quantity?.toLocaleString('ko-KR')}</td><td>{money(h.market_value)}</td><td>{fmtPct(h.weight)}</td><td>{h.price_date??'—'}</td><td>{h.price_status}</td></tr>)}</tbody></table></div>
    {!latest&&<p>기록이 없습니다. 설정 확정과 목표 효력일 이후 실제 가격의 체결·평가를 기다립니다.</p>}
    <details><summary>평가 History ({l?.snapshots?.length??0})</summary><div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>평가일</th><th>평가액</th><th>현금</th><th>NAV · 100</th><th>누적수익률 · 계좌 전체</th><th>상태</th></tr></thead><tbody>{l?.snapshots?.map(n=><tr key={n.date}><td>{n.date}</td><td>{money(n.nav)}</td><td>{money(n.cash_balance)}</td><td>{n.nav_base100?.toFixed(2)}</td><td>{fmtPct(n.cumulative_return)}</td><td>{n.nav_status}</td></tr>)}</tbody></table></div></details>
    <details><summary>주문 History ({l?.orders?.length??0})</summary><div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>주문</th><th>자산</th><th>방향</th><th>목표 비중</th><th>제출 시각</th><th>효력일</th><th>상태</th></tr></thead><tbody>{l?.orders?.map(o=><tr key={o.order_id}><td>{o.order_id}</td><td>{assetName(o.asset_id)}</td><td>{o.side}</td><td>{fmtPct(o.target_weight)}</td><td>{o.submitted_at}</td><td>{o.effective_at}</td><td>{o.status}</td></tr>)}</tbody></table></div></details>
    <details><summary>체결 History ({l?.trades?.length??0})</summary><div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>체결</th><th>자산</th><th>체결일</th><th>수량</th><th>원화 가격</th><th>거래비용</th></tr></thead><tbody>{l?.trades?.map(t=><tr key={t.trade_id}><td>{t.trade_id}</td><td>{assetName(t.asset_id)}</td><td>{t.execution_at}</td><td>{t.quantity?.toLocaleString('ko-KR')}</td><td>{money(t.execution_price)}</td><td>{money(t.transaction_cost)}</td></tr>)}</tbody></table></div></details>
    </>}
  </section>;
}
