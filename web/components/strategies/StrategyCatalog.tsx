"use client";
import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {getStrategies} from '@/lib/api/strategies';

export function StrategyCatalog(){
  const q=useQuery({queryKey:['strategy-research'],queryFn:getStrategies});
  return <section aria-label="주도주·수출 전략 자료" style={{marginTop:24,padding:20,border:'1px solid #dce4ee',borderRadius:8}}>
    <h2>주도주·수출 전략 자료</h2><p>과거 모델의 규칙·구성·성과를 검토할 수 있습니다. 정의와 갱신 입력이 확정되기 전에는 포트폴리오 선택·Frontier·확정·자동 운용에 편입하지 않습니다.</p>
    {q.isLoading?<p role="status">전략 자료 조회 중</p>:q.isError?<p role="alert">전략 자료 조회 실패 <button onClick={()=>q.refetch()}>다시 조회</button></p>:<ul>{q.data?.items.map(s=><li key={s.id}><Link href={`/strategies?strategy=${s.id}`}>{s.label} · 자료 검토</Link> · 운용 준비 전</li>)}</ul>}
  </section>;
}
