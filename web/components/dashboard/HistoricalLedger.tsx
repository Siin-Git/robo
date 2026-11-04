"use client";
import type {History} from './HistoricalPreview';
import {LedgerHistory} from './LedgerHistory';
import {assetName} from '@/app/(app)/dashboard/performance-data';
import {fmtDate,fmtPct} from '@/lib/format';
import s from '@/app/(app)/dashboard/dashboard.module.css';
const money=(value:number)=>`${value.toLocaleString('ko-KR',{maximumFractionDigits:0})}원`;
export function HistoricalLedger({report}:{report:NonNullable<History['report']>}){
 const ledger=report.ledger,latest=ledger?.snapshots.at(-1);
 if(!ledger||!latest)return null;
 return <section className={s.details} aria-label="보유자산·운용 내역">
  <div className={s.detailContent}>
   <section className={s.operations} aria-label="모의운용 기록 요약">
    <h2>보유자산·운용 내역</h2>
    <p>위 성과 그래프와 같은 기간·같은 투자 구성의 기록입니다.</p>
    <dl className={s.operationGrid}>
     <div><dt>운용 기록</dt><dd>평가 {ledger.snapshots.length}회</dd></div>
     <div><dt>마지막 평가일</dt><dd>{fmtDate(latest.date)}</dd></div>
     <div><dt>총 평가액</dt><dd>{money(latest.nav)}</dd></div>
     <div><dt>현금</dt><dd>{money(latest.cash_balance)}</dd></div>
     <div><dt>체결 기록</dt><dd>{ledger.trades.length}건</dd></div>
     <div><dt>운용 방식</dt><dd>최초 매수 후 보유</dd></div>
    </dl>
    <h3>목표 비중과 보유 비중</h3>
    <div className={s.operationTableWrap}><table className={s.operationTable}><thead><tr><th>자산</th><th>확정 목표 비중</th><th>평가일 보유 비중</th></tr></thead><tbody>{latest.holdings.map(h=><tr key={h.asset_id}><th>{assetName(h.asset_id)}</th><td>{fmtPct(report.weights[h.asset_id])}</td><td>{fmtPct(h.weight)}</td></tr>)}</tbody></table></div>
    <p>이 기록은 최초 매수 후 보유 방식입니다. 자동운용의 다음 리밸런싱 일정과 매매 판단은 ‘자동운용’ 화면에서 확인합니다.</p>
   </section>
   <LedgerHistory data={ledger}/>
   <details><summary>기록 생성 기준</summary><p>사후 계산한 모의 주문·체결·평가 기록입니다. 주문 기준 시각은 모의실험 안의 기준이며 실제 제출 시각이 아닙니다. 기록 보관 시각: {report.ledger_archived_at??'—'}. 자동운용 원장에는 합산하지 않습니다.</p></details>
  </div>
 </section>;
}
