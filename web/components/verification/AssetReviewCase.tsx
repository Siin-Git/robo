"use client";
import {useQuery} from '@tanstack/react-query';
import {get} from '@/lib/api/client';
import {fmtDate,fmtPct} from '@/lib/format';
import {ASSET_META} from '@/app/(app)/setup/portfolio/asset-meta';
import {THEME_INFO} from '@/app/(app)/setup/portfolio/theme-content';
import {finite} from './status';
import s from './verification-status.module.css';
export type AssetCase={available:false;decision_id:string;message:string}|{
 available:true;decision_id:string;decision_version:number;asset_id:string;confirmed_weight:number;selection_reason:string;
 initial_estimate:{expected_return:number|null;volatility:number|null;unit:string|null;horizon:string|null}|null;
 window_start:string;window_end_exclusive:string;window_status:string;as_of:string;data_kind:string;
 observation:{count:number;start:string|null;end:string|null;first_price:number|null;last_price:number|null;price_return:number|null;excluded:boolean;sources:string[];missing_dates:string[];invalid_dates:string[];curve:{date:string;price:number|null;source:string|null}[]};
 horizons:{months:number;due_date:string;status:string}[];
 assessment:{label:string;action:string;kind:string;reasons:{code:string;text:string}[];next_step:string;recorded_human_review:boolean};
};
const pct=(v:number|null|undefined)=>finite(v)?fmtPct(v):'미확보';
const price=(v:number|null)=>finite(v)?`${v.toLocaleString('ko-KR',{maximumFractionDigits:4})}원`:'미확보';
export function AssetReviewCase({decisionId}:{decisionId:string|undefined}){
 const q=useQuery({queryKey:['asset-review-case',decisionId],queryFn:()=>get<AssetCase>(`/api/v1/me/decisions/${encodeURIComponent(decisionId!)}/asset-review-case`),enabled:!!decisionId,refetchInterval:60_000,refetchIntervalInBackground:false,retry:1});
 const d=q.data && q.data.decision_id===decisionId && q.data.available ? q.data : undefined;
 const name=d?(ASSET_META[d.asset_id]?.name??THEME_INFO[d.asset_id.replace(/^theme:/,'')]?.name??d.asset_id):'';
 return <section className={s.assetCase} aria-label="자산 검토 사례">
  <div className={s.sectionHeading}><div><h3>실제 저장 자료로 본 자산 한 건</h3><p>{d?`${name} · 판단 v${d.decision_version} · ${fmtDate(d.as_of)} 조회 기준`:'본인 계정의 저장 판단과 가격 기록'}</p></div>{decisionId&&<button className="btn-secondary" disabled={q.isFetching} onClick={()=>void q.refetch()}>{q.isFetching?'조회 중':'사례 새로고침'}</button>}</div>
  {q.isError&&<p role="alert">{d?'사례 갱신 실패 · 이전 조회 결과입니다.':'검토 사례를 불러오지 못했습니다. 다시 조회해 주세요.'}</p>}
  {!d?<p>{!decisionId?'확정된 판단이 있어야 검토 사례를 연결할 수 있습니다.':q.isLoading?'저장된 자산 자료를 확인하고 있습니다.':q.isError?'조회 오류로 검토 결론을 표시하지 않습니다.':q.data?.available===false?q.data.message:'검토 자료 미확보'}</p>:<>
   <div className={s.caseColumns}>
    <div><h4>1. 최초 예상</h4><dl className={s.rows}>
     <div><dt>예상 연수익률</dt><dd>{pct(d.initial_estimate?.expected_return)}</dd></div>
     <div><dt>예상 연변동성</dt><dd>{pct(d.initial_estimate?.volatility)}</dd></div>
     <div><dt>확정 비중</dt><dd>{pct(d.confirmed_weight)}</dd></div>
     <div><dt>판단 효력일</dt><dd>{fmtDate(d.window_start)}</dd></div>
    </dl>{!d.initial_estimate&&<p>최초 자산별 예상이 저장되지 않았습니다.</p>}</div>
    <div><h4>2. 이후 관측</h4><dl className={s.rows}>
     <div><dt>유효한 가격 관측</dt><dd>{d.observation.count}일</dd></div>
     <div><dt>첫 관측 · {fmtDate(d.observation.start)}</dt><dd>{price(d.observation.first_price)}</dd></div>
     <div><dt>마지막 관측 · {fmtDate(d.observation.end)}</dt><dd>{price(d.observation.last_price)}</dd></div>
     <div><dt>기간 가격 변화율</dt><dd>{d.observation.price_return==null?'계산 대기':pct(d.observation.price_return)}</dd></div>
    </dl><p>저장된 원화 가격 기준 · 비용 제외</p></div>
   </div>
   <div className={s.caseVerdict}><h4>3. 자료 기준 검토 결과 · {d.assessment.label}</h4><ul>{d.assessment.reasons.map(reason=><li key={reason.code}>{reason.text}</li>)}</ul><p>{d.assessment.next_step}</p><small>이 결론은 자료의 비교 가능 여부를 점검한 결과이며, 담당자의 저장된 검토 의견이나 매매 지시가 아닙니다.</small></div>
   <details className={s.evidence}><summary>선정 이유와 원본 관측값</summary><div className={s.evidenceBody}><p>{d.selection_reason}</p><p>판단 효력일 이후부터 다음 판단 효력일 전까지의 자료를 사용합니다. 최초 예상은 현재 모형으로 다시 계산하지 않습니다.</p>
    <p>{d.horizons.map(h=>`${h.months}개월 점검 ${fmtDate(h.due_date)} · ${h.status==='REACHED'?'기간 도달':h.status==='UNVERIFIED'?'관측 근거 미확보':'기간 미도달'}`).join(' / ')}</p>
    <p>가격 출처: {d.observation.sources.join(', ')||'미확보'}{d.observation.excluded?' · 시험·재생 또는 미확인 출처 제외':''}</p>
    <div className={s.methodTable}><table><caption>{name} 저장 가격</caption><thead><tr><th>관측일</th><th>원화 가격</th><th>출처</th></tr></thead><tbody>{d.observation.curve.map(row=><tr key={row.date}><td>{fmtDate(row.date)}</td><td>{price(row.price)}</td><td>{row.source||'미확보'}</td></tr>)}</tbody></table></div>
   </div></details>
  </>}
 </section>;
}
