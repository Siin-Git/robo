"use client";

import {useQuery} from '@tanstack/react-query';
import type {ContinuityData} from '../dashboard/Continuity';
import {get} from '@/lib/api/client';
import {fmtDate,fmtPct,fmtActivePp} from '@/lib/format';
import {finite,koreaTime} from './status';
import s from './verification-status.module.css';

const money=(value:number|null)=>finite(value)?`${Math.round(value).toLocaleString('ko-KR')}원`:'미확보';

/** Account-wide history, not performance attributable to the latest saved decision. */
export function AccountComparison(){
  const q=useQuery({queryKey:['own-continuity'],queryFn:()=>get<ContinuityData>('/api/v1/me/performance/continuity'),refetchInterval:60_000,refetchIntervalInBackground:false,staleTime:30_000,retry:1});
  const d=q.data;
  const summary=d?.summary;
  const ready=!!(d?.available&&summary&&summary.observations>=2&&summary.start&&summary.end&&summary.start<summary.end&&finite(summary.personal_return)&&finite(summary.core_return)&&finite(summary.difference_pp));
  return <section className={s.accountComparison} aria-label="전체 기간 성과 비교">
    <div className={s.sectionHeading}><div><h2>전체 기간 성과 비교</h2><p>대시보드와 같은 계좌 기록 · 현재 판단 한 건에 한정하지 않습니다.</p></div><button className="btn-secondary" disabled={q.isFetching} onClick={()=>void q.refetch()}>{q.isFetching?'조회 중':'전체 기록 새로고침'}</button></div>
    {q.isError&&<p role="alert">{ready?'전체 기록 갱신 실패 · 아래는 이전 조회 결과입니다.':'전체 기록을 불러오지 못했습니다. 다시 조회해 주세요.'}</p>}
    {ready&&summary&&d?<>
      <div className={s.comparisonPeriod}><strong>{fmtDate(summary.start)} — {fmtDate(summary.end)}</strong><span>{summary.observations}개 공통 평가일{q.isError?' · 이전 조회':''}</span></div>
      <dl className={s.comparisonMetrics}><div><dt>내 포트폴리오</dt><dd>{fmtPct(summary.personal_return)}</dd></div><div><dt>CORE</dt><dd>{fmtPct(summary.core_return)}</dd></div><div><dt>수익률 차이</dt><dd>{fmtActivePp(summary.difference_pp)}</dd></div></dl>
      <p className={s.comparisonNote}>{fmtDate(d.historical_start)}–{fmtDate(d.historical_end)}은 저장된 구성을 과거 가격에 적용한 구간이며, {fmtDate(d.forward_start)}부터 이어받은 평가 기록을 포함합니다. 이 전체 기간 결과만으로 현재 판단의 적중 여부를 판정하지 않습니다.</p>
      {!!summary.missing_observations&&<p role="status">평가 미확보 {summary.missing_observations}일 · 해당 날짜의 값을 채우거나 정상 평가로 세지 않았습니다.</p>}
      <details className={s.evidence}><summary>전체 기간 계산 근거와 일별 평가액</summary><div className={s.evidenceBody}>
        <p>각 계좌의 같은 시작일 평가액을 기준으로 계산한 수익률입니다. CORE는 시장지수가 아닙니다. 과거 구간에 적용한 구성의 확정 시각: {koreaTime(d.decision_confirmed_at)} · 한국 시간.</p>
        <p>조회 성공 {koreaTime(q.dataUpdatedAt)} · 한국 시간. 저장된 정상 평가액만 사용하며 원장이나 최초 판단을 변경하지 않습니다.</p>
        <div className={s.methodTable}><table><caption>전체 기간의 저장 평가액</caption><thead><tr><th>평가일</th><th>자료 구분</th><th>내 포트폴리오</th><th>CORE</th></tr></thead><tbody>{d.series.map(row=><tr key={row.date}><th scope="row">{fmtDate(row.date)}</th><td>{row.data_kind==='HISTORICAL_REPLAY'?'과거 가격 적용':'시작 이후 기록'}</td><td>{money(row.personal_nav)}</td><td>{money(row.core_nav)}</td></tr>)}</tbody></table></div>
      </div></details>
    </>:<p>{q.isLoading?'전체 기간 기록을 불러오는 중입니다.':q.isError?'조회 오류로 비교 가능 여부를 판단할 수 없습니다.':'전체 기간을 연결할 공통 평가 기록이 부족합니다.'}</p>}
  </section>;
}
