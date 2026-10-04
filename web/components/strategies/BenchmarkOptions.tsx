"use client";
import {useQuery} from '@tanstack/react-query';
import {get} from '@/lib/api/client';

interface Candidate {id:string;label:string;currency:string;dividends:string;costs:string;period:string;note:string;source_url?:string}
export function BenchmarkOptions(){
  const q=useQuery({queryKey:['benchmark-definitions'],queryFn:()=>get<{candidates:Record<string,Candidate[]>;definitions:Record<string,unknown>}>('/api/v1/benchmarks/definitions')});
  return <details><summary>시장·안전자산 후보와 필요한 결정</summary>
    <p>후보 목록은 팀 합의가 아닙니다. 통화·배당·비용과 실제 원장 시작·종료일의 자료를 확정한 후 연결합니다.</p>
    {q.isLoading?<p>기준 후보 조회 중</p>:q.isError?<p role="alert">후보 조회 실패 <button onClick={()=>q.refetch()}>다시 조회</button></p>:Object.entries(q.data?.candidates??{}).map(([key,items])=><div key={key}><h3>{key==='market'?'시장':'안전자산'}</h3><ul>{items.map(x=><li key={x.id}><strong>{x.label}</strong> · {x.currency} · 배당 {x.dividends} · 비용 {x.costs}<p>{x.period}. {x.note}</p>{x.source_url&&<a href={x.source_url} target="_blank" rel="noreferrer">정의 출처</a>}</li>)}</ul></div>)}
  </details>;
}
