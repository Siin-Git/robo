"use client";
import {useQuery} from '@tanstack/react-query';
import {get} from '@/lib/api/client';
import {ResponsiveContainer,LineChart,Line,XAxis,YAxis,Tooltip,ReferenceLine} from 'recharts';
import {fmtDate} from '@/lib/format';
import s from './DarkDashboard.module.css';
export type ContinuityData={available:boolean;historical_start:string;historical_end:string;forward_start:string;decision_confirmed_at:string;forward_observations:number;opening:{as_of:string;nav:number;cash_balance:number;holdings:{asset_id:string;quantity:number}[]};
 summary?:{start:string;end:string;observations:number;personal_return:number;core_return:number;difference_pp:number;missing_observations:number};
 snapshot?:{date:string;nav:number;cash_balance:number;holdings:{asset_id:string;quantity:number;market_value:number}[]};
 series:{date:string;personal_nav:number|null;core_nav:number|null;personal_index:number|null;core_index:number|null;data_kind:string;valid?:boolean}[]};
export function useContinuity(){return useQuery({queryKey:['own-continuity'],queryFn:()=>get<ContinuityData>('/api/v1/me/performance/continuity'),refetchInterval:60_000,refetchIntervalInBackground:false,staleTime:30_000,retry:1});}
export function Continuity(){
 const q=useQuery({queryKey:['own-continuity'],queryFn:()=>get<ContinuityData>('/api/v1/me/performance/continuity'),refetchInterval:60_000,staleTime:30_000,retry:1});
 const d=q.data;
 if(q.isError&&!d)return <p role="alert">승계 운용 기록을 확인하지 못했습니다. <button onClick={()=>q.refetch()}>다시 조회</button></p>;
 if(!d?.available)return null;
 return <section className={s.card} aria-label="과거 재현을 포함한 연속 모의운용">
  <div className={s.cardHeading}><div><h2>과거 재현을 포함한 모의운용</h2><p>{fmtDate(d.historical_start)} — {fmtDate(d.historical_end)} 과거 가격 재현 · {fmtDate(d.forward_start)}부터 자동 모의운용</p></div></div>
  {q.isError&&<p role="alert">갱신에 실패했습니다. 이전 조회 결과입니다. <button onClick={()=>q.refetch()}>다시 조회</button></p>}
  <p>구성 확정 {new Date(d.decision_confirmed_at).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul'})}. 확정된 구성을 과거 가격에 적용한 결과로, 당시 투자 판단의 실적을 뜻하지 않습니다.</p>
  <p>{fmtDate(d.opening.as_of)} 평가자산 {Math.round(d.opening.nav).toLocaleString('ko-KR')}원 · 현금 {Math.round(d.opening.cash_balance).toLocaleString('ko-KR')}원과 보유 수량을 승계했습니다.</p>
  <p role="status">{d.forward_observations?`시작일 이후 정상 공동 평가 ${d.forward_observations}회`:`${fmtDate(d.forward_start)} 이후 첫 정상 평가 대기`}. 자동운용 구간은 별도 기록되며 과거 실적과 구분합니다.</p>
  <div style={{height:240}} role="img" aria-label="첫 재현 평가액을 100으로 한 Personalized와 CORE 연속 모의운용 지수">
   <ResponsiveContainer width="100%" height="100%"><LineChart data={d.series} margin={{left:0,right:24,top:20,bottom:10}}>
    <XAxis dataKey="date" tickFormatter={v=>v.slice(5)} stroke="#91a2b8" minTickGap={30}/><YAxis domain={['auto','auto']} tickFormatter={v=>v.toFixed(1)} stroke="#91a2b8" width={52}/>
    <Tooltip contentStyle={{background:'#1b293b',border:'1px solid #42526b',color:'#edf3fb'}} labelFormatter={v=>`${v} · ${String(v)<d.forward_start?'과거 재현':'자동 모의운용'}`}/>
    <ReferenceLine x={d.forward_start} stroke="#ddbf83" strokeDasharray="4 4" label={{value:'자동운용 시작',fill:'#ddbf83',position:'insideTopRight'}}/>
    <Line type="linear" dataKey="personal_index" name="내 구성" stroke="#659bff" dot={false} connectNulls={false} isAnimationActive={false}/><Line type="linear" dataKey="core_index" name="CORE" stroke="#98afc6" dot={false} connectNulls={false} isAnimationActive={false}/>
   </LineChart></ResponsiveContainer>
  </div>
  <details><summary>기간별 평가액 구분</summary><p>첫 재현 평가액 = 100. 휴장일의 평가액을 추가하지 않습니다. 최초 매수 비용은 첫 재현 평가액에 포함됩니다. 연간 기대수익률의 적중 여부는 이 짧은 기간으로 판단하지 않습니다.</p><div className={s.tableWrap}><table><thead><tr><th>평가일</th><th>구분</th><th>내 구성</th><th>CORE</th></tr></thead><tbody>{d.series.map(p=><tr key={p.date}><td>{p.date}</td><td>{p.data_kind==='HISTORICAL_REPLAY'?'과거 재현':'자동 모의운용'}</td><td>{p.personal_index?.toFixed(4)??'미확보'}</td><td>{p.core_index?.toFixed(4)??'미확보'}</td></tr>)}</tbody></table></div></details>
 </section>;
}
