"use client";
import {useQuery} from '@tanstack/react-query';
import {get} from '@/lib/api/client';
import {fmtReturn,fmtActivePp} from '@/lib/format';
import s from './HistoricalPreview.module.css';
import type { ForwardLedger } from '@/lib/api/ledger';
type Point={date:string;personal_index:number;core_index:number};
export type History={available:boolean;report?:{start:string;end:string;decision_confirmed_at:string;is_current_configuration:boolean;series:Point[];summary:{personal_return:number;core_return:number;observations:number};price_dates:Record<string,Record<string,string>>;cost_bps:number;ledger?:ForwardLedger;weights:Record<string,number>;ledger_archived_at?:string}};
export function useHistoricalPreview(){return useQuery({queryKey:['own-historical-preview'],queryFn:()=>get<History>('/api/v1/me/performance/history'),staleTime:60_000,retry:1});}
export function HistoricalPreview(){
 const q=useHistoricalPreview();
 if(q.isError)return <section className={s.card} role="alert">모의운용 결과를 불러오지 못했습니다. <button className="btn-secondary" onClick={()=>q.refetch()}>다시 조회</button></section>;
 const r=q.data?.report;
 if(!q.data?.available||!r||r.series.length<2)return null;
 const points=r.series;
 const values=points.flatMap(p=>[p.personal_index,p.core_index]);
 const lo=Math.min(...values),hi=Math.max(...values),pad=Math.max((hi-lo)*.15,.2),min=lo-pad,max=hi+pad;
 const x=(i:number)=>58+i/(points.length-1)*804;
 const y=(v:number)=>226-(v-min)/(max-min)*196;
 const line=(key:'personal_index'|'core_index')=>points.map((p,i)=>`${x(i)},${y(p[key])}`).join(' ');
 const carried=Object.entries(r.price_dates).flatMap(([day,assets])=>Object.entries(assets).filter(([,d])=>d!==day).map(([asset,d])=>`${day} · ${asset}: ${d} 가격`));
 return <section className={s.card} aria-label="모의운용 성과">
  <div className={s.top}><div><span className={s.badge}>모의운용</span><h2>모의운용 성과</h2><p>{r.start} — {r.end} · 평가 {r.summary.observations}회</p></div><span className={s.status}>운용 기준일 {r.start.replaceAll('-','.')}</span></div>
  <p className={s.description}>저장된 투자 구성의 성과를 기준 포트폴리오 CORE와 비교합니다.</p>
  {!r.is_current_configuration&&<p className={s.description}>구성을 변경하기 전의 저장된 결과입니다.</p>}
  <div className={s.metrics}><div><span>내 구성</span><strong>{fmtReturn(r.summary.personal_return)}</strong></div><div><span>기준 CORE</span><strong>{fmtReturn(r.summary.core_return)}</strong></div><div><span>CORE 대비</span><strong>{fmtActivePp(r.summary.personal_return-r.summary.core_return)}</strong></div></div>
  <div className={s.legend}><span>━ 내 구성</span><span>━ 기준 CORE</span><small>첫 평가액 = 100</small></div>
  <svg viewBox="0 0 900 270" role="img" aria-label="모의운용 평가 지수 그래프" className={s.chart}>
   {[0,1,2,3].map(i=>{const v=min+(max-min)*i/3;return <g key={i}><line x1="58" x2="862" y1={y(v)} y2={y(v)} stroke="var(--border)"/><text x="45" y={y(v)+4} textAnchor="end" fontSize="12" fill="var(--text-secondary)">{v.toFixed(1)}</text></g>})}
   <polyline points={line('core_index')} fill="none" stroke="var(--text-secondary)" strokeWidth="2"/>
   <polyline points={line('personal_index')} fill="none" stroke="#74a8ff" strokeWidth="3"/>
   {points.map((p,i)=><g key={p.date}><circle cx={x(i)} cy={y(p.personal_index)} r="4" fill="#74a8ff"><title>{p.date} · 내 구성 {p.personal_index.toFixed(2)} · CORE {p.core_index.toFixed(2)}</title></circle><text x={x(i)} y="253" textAnchor="middle" fontSize="12" fill="var(--text-secondary)">{p.date.slice(5).replace('-','.')}</text></g>)}
  </svg>
  <details className={s.details}><summary>계산 기준과 일별 값</summary><p>구성 확정: {r.decision_confirmed_at.slice(0,10)}. 이 구성과 해당 기간의 시장 가격으로 사후 계산한 모의운용 결과입니다. 기준일부터 실제로 자동 수집·운용한 기록을 뜻하지 않으며, 확정 이후 쌓이는 운용 기록과 합산하지 않습니다. 최초 매수 후 보유하며 거래비용 {r.cost_bps}bp를 적용했습니다. 수익률은 첫 평가액 이후의 변화로, 최초 매수비용은 출발 평가액에 반영됩니다.</p><p>각 평가일에 이용 가능한 마지막 관측 가격을 사용합니다. 시장별 가격 날짜가 다를 수 있으며, 없는 가격을 새로 만들지 않습니다.</p><div className={s.table}><table><thead><tr><th>평가일</th><th>내 구성 지수</th><th>CORE 지수</th></tr></thead><tbody>{points.map(p=><tr key={p.date}><td>{p.date}</td><td>{p.personal_index.toFixed(4)}</td><td>{p.core_index.toFixed(4)}</td></tr>)}</tbody></table></div>{carried.length>0&&<p>{carried.join(' / ')}</p>}</details>
 </section>;
}
