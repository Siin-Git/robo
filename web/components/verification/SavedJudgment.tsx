import type {DecisionVerification} from '@/components/portfolio/DecisionVerificationPanel';
import {ASSET_META} from '@/app/(app)/setup/portfolio/asset-meta';
import {THEME_INFO} from '@/app/(app)/setup/portfolio/theme-content';
import {fmtActivePp,fmtDate,fmtPct} from '@/lib/format';
import {finite} from './status';
import s from './verification-status.module.css';
const pct=(n:number|null|undefined)=>finite(n)?fmtPct(n):'미확보';
const name=(id:string)=>ASSET_META[id]?.name??THEME_INFO[id.replace(/^theme:/,'')]?.name??id;
export function SavedJudgment({data}:{data:DecisionVerification}) {
  const {base,personalized}=data.original;
  const risk=data.risk_change;
  const paired=risk?.status==='AVAILABLE'&&[risk.base_volatility,risk.personalized_volatility,risk.difference_pp].every(finite);
  const assets=Array.from(new Set([...Object.keys(base.weights),...Object.keys(personalized.weights)]))
    .filter(id=>[base.weights[id],personalized.weights[id]].some(value=>finite(value)&&value>0));
  return <div className={s.judgment}>
    <div className={s.judgmentGrid}>
      <div><h3>확정 당시 예상</h3><table><caption className={s.srOnly}>확정 당시 예상 수익률과 변동성</caption><thead><tr><th>구성</th><th>연수익률</th><th>연변동성</th></tr></thead><tbody>
        <tr><th scope="row">기본 구성 · Frontier</th><td>{pct(base.expected_return)}</td><td>{pct(base.volatility)}</td></tr>
        <tr><th scope="row">내 선택</th><td>{pct(personalized.expected_return)}</td><td>{pct(personalized.volatility)}</td></tr>
      </tbody></table><p>효력일 {fmtDate(data.effective_date)}</p><p>선택 이유: {data.reason||'미입력'}</p></div>
      <div className={s.riskSummary}><h3>테마 포함 기준의 예상 위험 변화</h3>{paired?<>
        <div className={s.riskPair}><span>기본 구성 <b>{pct(risk.base_volatility)}</b></span><span aria-hidden>→</span><span>내 선택 <b>{pct(risk.personalized_volatility)}</b></span></div>
        <strong className={s.riskDelta}>{fmtActivePp(risk.difference_pp! / 100)}</strong>
      </>:<p>확정 당시 비교할 위험 값이 저장되지 않았습니다.</p>}</div>
    </div>
    <details className={s.evidence}><summary>확정 당시 비중 보기</summary>{assets.length?<div className={s.weightTable}><table><caption className={s.srOnly}>확정 당시 자산 비중</caption><thead><tr><th>자산</th><th>기본 구성</th><th>내 선택</th></tr></thead><tbody>{assets.map(id=><tr key={id}><th scope="row">{name(id)}</th><td>{id in base.weights?pct(base.weights[id]):'—'}</td><td>{id in personalized.weights?pct(personalized.weights[id]):'—'}</td></tr>)}</tbody></table></div>:<p>당시 자산 비중 미확보</p>}</details>
  </div>;
}
