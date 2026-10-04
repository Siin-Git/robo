import {fmtActivePp,fmtPct} from '@/lib/format';

export interface MetricComparison {
  metric:string;difference:number|null;difference_unit?:string;reason:string|null;reasons?:string[];status:string;
  actual?:{value:number|null;unit:string};expected?:{value:number|null;unit:string};
  alignment?:Record<string,{expected:unknown;actual:unknown;matches:boolean}>;
}
const labels:Record<string,string>={expected_return:'예상 수익률',volatility:'예상 변동성',tracking_error:'예상 추적오차'};
const axes:Record<string,string>={unit:'단위',start:'시작일',end:'종료일',currency:'통화',cost_basis:'비용 처리',dividend_basis:'배당 처리',return_definition:'수익률·위험 정의',sampling:'산출 주기',portfolio_reference:'판단 기준',benchmark_reference:'비교 기준'};
const reasons:Record<string,string>={ORIGINAL_METRIC_UNAVAILABLE:'확정 당시 예상값 없음',ORIGINAL_COMPARISON_BASIS_NOT_RECORDED:'확정 당시 비교 기준 미기록',INSUFFICIENT_ACTUAL_HISTORY:'실제 관측 부족',ACTUAL_RISK_OBSERVATION_GAPS:'위험 관측의 공백·오래된 가격'};
const definitions:Record<string,string>={fraction:'비율',fraction_per_year:'연간 비율',EXCLUDES_TRANSACTION_COSTS:'거래비용 제외',TRANSACTION_COSTS_INCLUDED:'거래비용 포함',PROVIDER_ADJUSTED_OR_CLOSE:'공급자 조정종가 또는 일반 종가',BL_ANNUAL_STRATEGIC_RETURN:'BL 연간 전략 예상 수익률',WEEKLY_LEDOIT_WOLF_COVARIANCE:'주간 Ledoit-Wolf 공분산',NAV_CHANGE_NO_EXTERNAL_FLOWS:'외부 입출금 없는 평가액 변동',STD_SAMPLE_RETURNS:'수익률 표본 표준편차',STD_SAMPLE_ACTIVE_RETURNS:'기준 대비 초과수익률 표본 표준편차',annual_model:'연간 모형',OBSERVED_ENDPOINTS:'관측 시작·종료 평가액',D_252:'일간 · 연 252일', 'W-FRI_52':'금요일 주간 · 연 52주',NONE:'해당 없음'};
function definitionText(key:string,value:unknown,matches:boolean){
  if(value==null)return '미기록';
  if(key==='portfolio_reference')return matches?'동일한 확정 판단':'판단 기준 불일치';
  if(key==='benchmark_reference'&&value!=='NONE'&&!String(value).startsWith('CORE'))return '사용자 선택 기본 구성';
  return definitions[String(value)]??String(value);
}
function reasonText(reason:string){
  if(reasons[reason])return reasons[reason];
  const key=reason.replace(/_(DIFFERS|NOT_RECORDED)$/,'').toLowerCase();
  if(axes[key])return `${axes[key]} ${reason.endsWith('DIFFERS')?'불일치':'미기록'}`;
  return reason;
}
export function ExpectationComparison({items}:{items:MetricComparison[]}){
  return <div aria-label="예상 실제 비교 조건">{items.map(c=><div key={c.metric} style={{marginBottom:16}}>
    <p><strong>{labels[c.metric]??c.metric}</strong>: {c.status==='COMPARABLE'&&c.difference!=null?`실제 − 예상 ${fmtActivePp(c.difference)}`:'비교 불가'}</p>
    {c.actual&&c.expected&&<p>저장 예상 {fmtPct(c.expected.value)} ({definitions[c.expected.unit]??c.expected.unit}) · 관측 실제 {fmtPct(c.actual.value)} ({definitions[c.actual.unit]??c.actual.unit})</p>}
    {c.status!=='COMPARABLE'&&<p>{(c.reasons??(c.reason?[c.reason]:[])).map(reasonText).join(' · ')}</p>}
    {c.alignment&&<details><summary>기간·단위·통화·비용·기준 대조</summary><p>작은 화면에서는 표를 좌우로 밀어 전체 조건을 확인하세요.</p><div style={{overflowX:'auto'}}><table style={{minWidth:600,width:'100%',textAlign:'left',borderSpacing:'8px'}}><thead><tr><th>조건</th><th>저장 예상</th><th>관측 실제</th><th>일치</th></tr></thead><tbody>{Object.entries(c.alignment).map(([key,v])=><tr key={key}><th>{axes[key]??key}</th><td style={{overflowWrap:'anywhere'}}>{definitionText(key,v.expected,v.matches)}</td><td style={{overflowWrap:'anywhere'}}>{definitionText(key,v.actual,v.matches)}</td><td>{v.matches?'일치':'불일치 / 미기록'}</td></tr>)}</tbody></table></div></details>}
  </div>)}</div>;
}
