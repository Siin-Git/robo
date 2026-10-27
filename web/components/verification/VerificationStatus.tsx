"use client";

import type {ReactNode} from 'react';
import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {Activity,ArrowUpRight,ClipboardCheck,GitCompareArrows,RefreshCw} from 'lucide-react';
import {AppShell} from '@/components/layout/AppShell';
import {LoadingSkeleton} from '@/components/shared/ui';
import {get} from '@/lib/api/client';
import {getDecisions} from '@/lib/api/decisions';
import {fmtActivePp,fmtDate,fmtPct} from '@/lib/format';
import type {DecisionVerification} from '@/components/portfolio/DecisionVerificationPanel';
import {canCompare,checkpointLabels,finite,hasTodayJob,jobStatus,koreaTime,originalComplete,type Tone} from './status';
import {evidenceRecord,evidenceLinks} from './evidence-record';
import s from './verification-status.module.css';

const poll={refetchInterval:60_000,refetchIntervalInBackground:false};
const won=(n:number|null|undefined)=>finite(n)?`${Math.round(n).toLocaleString('ko-KR')}원`:'미확보';
const pct=(n:number|null|undefined)=>finite(n)?fmtPct(n):'미확보';
function Badge({tone,children}:{tone:Tone;children:ReactNode}) {
  return <span className={`${s.badge} ${s[tone]}`}><i aria-hidden/>{children}</span>;
}
function EvidenceCard({title,icon,label,tone,stale,children,detail}:{title:string;icon:ReactNode;label:string;tone:Tone;stale:boolean;children:ReactNode;detail:ReactNode}) {
  return <section className={s.card} aria-label={title}>
    <div className={s.cardTitle}><span className={s.icon} aria-hidden>{icon}</span><h2>{title}</h2></div>
    <Badge tone={stale?'attention':tone}>{stale?'갱신 실패 · 이전 조회':label}</Badge>
    <div className={s.cardBody}>{children}</div>
    <details className={s.evidence}><summary>{title} 근거 보기</summary><div className={s.evidenceBody}>{detail}</div></details>
  </section>;
}

export function VerificationStatus() {
  const decisions=useQuery({queryKey:['decisions'],queryFn:getDecisions,...poll});
  const id=decisions.data?.items[0]?.decision_id;
  const query=useQuery({queryKey:['decision-verification',id],queryFn:()=>get<DecisionVerification>(`/api/v1/me/decisions/${encodeURIComponent(id!)}/verification`),enabled:!!id,...poll});
  const data=query.data?.decision_id===id?query.data:undefined;
  const loading=decisions.isLoading||(!!id&&query.isLoading);
  const failed=decisions.isError||(!!id&&query.isError);
  const busy=decisions.isFetching||query.isFetching;
  const updated=data?Math.min(decisions.dataUpdatedAt,query.dataUpdatedAt):!id?decisions.dataUpdatedAt:0;
  const actual=data?.actual;
  const comparable=!!actual&&canCompare(actual);
  const job=data?.valuation_job;
  const operation=jobStatus(job);
  const todayJob=hasTodayJob(job,query.dataUpdatedAt);
  const complete=!!data&&originalComplete(data);
  async function refresh(){
    const result=await decisions.refetch();
    if(id&&result.data?.items[0]?.decision_id===id)void query.refetch();
  }
  const detailHref=id?`/portfolio?decision_id=${encodeURIComponent(id)}&inspect=personalized`:'/portfolio';
  return <AppShell headerTitle="검증 현황"><div className={s.page}>
    <header className={s.header}><div><h1>검증 현황</h1><p>확인한 기록과 아직 남은 검증을 구분합니다.</p></div>
      <button className="btn-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15} aria-hidden className={busy?s.spinning:undefined}/>{busy?'조회 중':'기록 새로고침'}</button>
    </header>
    <div className={s.context}><span>내 계정{data&&<> · 최신 판단 <b>v{data.version}</b> · 확정 {koreaTime(data.confirmed_at)}</>}</span><span>{updated?`마지막 성공 조회 ${koreaTime(updated)} · 한국 시간`:failed?'성공한 조회 기록 없음':loading?'저장된 기록 조회 중':'조회 시각 미확보'}</span></div>
    {failed&&<p role="alert" className={s.alert}>{data?'기록 갱신에 실패했습니다. 아래 계정 근거는 이전 조회 결과입니다.':'계정 근거를 불러오지 못했습니다. 기록 새로고침으로 다시 확인해 주세요.'}</p>}
    <div className={s.sectionHeading}><h2>현재 계정의 근거</h2><p>기록 조회 · 1분마다 갱신</p></div>
    {loading&&!data?<LoadingSkeleton rows={5}/>:!data?<div className={s.cards}>
      {['판단 보존','성과 비교','운용 기록'].map(title=><section key={title} className={s.card} aria-label={title}><h2>{title}</h2><Badge tone={failed?'attention':'missing'}>{failed?'조회 실패':id?'검증 근거 미확보':'확정 판단 미확보'}</Badge><p className={s.emptyCopy}>{failed?'조회 오류로 상태를 판단할 수 없습니다.':id?'해당 판단의 근거를 확보하지 못했습니다.':'확정된 판단이 있어야 이 계정의 근거를 연결할 수 있습니다.'}</p></section>)}
    </div>:<div className={s.cards}>
      <EvidenceCard title="판단 보존" icon={<ClipboardCheck size={19}/>} label={complete?'저장 기록 확인':'일부 기록 미확보'} tone={complete?'confirmed':'missing'} stale={failed} detail={<>
        <dl className={s.rows}><div><dt>확정 시각 · 한국 시간</dt><dd>{koreaTime(data.confirmed_at)}</dd></div><div><dt>목표 효력일</dt><dd>{fmtDate(data.effective_date)}</dd></div>
          <div><dt>Base 예상 연수익률 / 변동성</dt><dd>{pct(data.original.base.expected_return)} / {pct(data.original.base.volatility)}</dd></div>
          <div><dt>내 선택 예상 연수익률 / 변동성</dt><dd>{pct(data.original.personalized.expected_return)} / {pct(data.original.personalized.volatility)}</dd></div>
          <div><dt>저장된 선택 이유</dt><dd>{data.reason||'미입력'}</dd></div></dl>
        <p>확정 당시 저장값입니다. 누락된 값은 현재 모형으로 채우지 않습니다. 이 조회만으로 기록의 불변성을 다시 검사한 것은 아닙니다.</p>
        <Link href={detailHref}>당시 비중·위험 근거 보기 <ArrowUpRight size={14}/></Link>
      </>}>
        <div className={s.figure}>v{data.version}<span>확정 당시 판단</span></div><p>{complete?'기본 구성과 내 선택의 예상·비중이 저장돼 있습니다.':'당시 예상 또는 비중이 빠져 있습니다. 확보된 기록만 표시합니다.'}</p>
        <small>출처 · 확정 판단 기록</small>
      </EvidenceCard>
      <EvidenceCard title="성과 비교" icon={<GitCompareArrows size={19}/>} label={comparable?'비교 자료 확보':'비교 미확보'} tone={comparable?'confirmed':'missing'} stale={failed} detail={<>
        <p>{comparable?`${fmtDate(actual!.start)} — ${fmtDate(actual!.end)} · 공통 정상 평가액 기준`:(actual?.reason||'비교에 필요한 기간·평가액·수익률이 충분하지 않습니다.')}</p>
        {comparable&&<><dl className={s.rows}><div><dt>내 선택 · Personalized</dt><dd>{fmtPct(actual!.personalized_return)}</dd></div><div><dt>기준 계좌 · CORE</dt><dd>{fmtPct(actual!.core_return)}</dd></div><div><dt>기간 수익률 차이</dt><dd>{fmtActivePp(actual!.difference_pp)}</dd></div><div><dt>Personalized 평가액</dt><dd>{won(actual!.personalized_nav?.start)} → {won(actual!.personalized_nav?.end)}</dd></div><div><dt>CORE 평가액</dt><dd>{won(actual!.core_nav?.start)} → {won(actual!.core_nav?.end)}</dd></div></dl></>}
        <p>동일 날짜의 정상 NAV가 두 시점 이상 있어야 비교합니다. CORE는 기본 구성 Base나 시장지수와 다릅니다.</p>
        <p>정상 조건을 충족하지 않은 평가 기록 {actual?.excluded_rows??0}건 제외. 합성·과거 재생 자료는 운용 성과에 포함하지 않습니다.</p>
        {data.opening_context&&<p>{fmtDate(data.opening_context.forward_start)}부터 과거 재현의 보유자산·현금을 승계한 모의운용입니다. 위 비교에는 시작일 이후 정상 평가 기록만 포함합니다.</p>}
        <Link href={detailHref}>이 판단의 성과 상세 <ArrowUpRight size={14}/></Link>
      </>}>
        <div className={s.figure}>{actual?.observations??0}<span>공통 평가일</span></div><p>{comparable?'같은 기간의 두 계좌 기록을 비교할 수 있습니다.':'비교 조건을 충족한 기록이 필요합니다. 수익률을 0으로 대체하지 않습니다.'}</p>
        <small>출처 · Personalized·CORE 정상 NAV</small>
      </EvidenceCard>
      <EvidenceCard title="운용 기록" icon={<Activity size={19}/>} label={`최근 결과 · ${operation.label}`} tone={operation.tone} stale={failed} detail={<>
        <dl className={s.rows}><div><dt>작업 범위</dt><dd>전체 계좌</dd></div><div><dt>작업 예정일</dt><dd>{fmtDate(job?.scheduled_for)}</dd></div><div><dt>완료 시각 · 한국 시간</dt><dd>{koreaTime(job?.completed_at)}</dd></div><div><dt>평가 대상일</dt><dd>{job?.valuation_date?fmtDate(job.valuation_date):'미확보'}</dd></div><div><dt>정상 NAV 계좌 수</dt><dd>{job?.normal_nav_accounts??'미확보'}</dd></div><div><dt>가격 지연 NAV 계좌 수</dt><dd>{job?.stale_nav_accounts??'미확보'}</dd></div><div><dt>평가 대상 계좌 수</dt><dd>{job?.expected_nav_accounts??'미확보'}</dd></div><div><dt>준비 인원</dt><dd>{job?.ready!=null&&job?.required!=null?`${job.ready} / ${job.required}명`:'미확보'}</dd></div></dl>
        <p>작업 성공과 정상 평가액 저장은 별도로 확인합니다. 전체 계좌의 작업 상태가 내 계좌의 비교 자료 확보를 보장하지는 않습니다.</p>
        <p>화면 새로고침은 저장된 결과만 조회하며 운용을 실행하지 않습니다.</p>
        <Link href="/dashboard?source=forward">자동운용 기록 보기 <ArrowUpRight size={14}/></Link>
      </>}>
        <div className={`${s.figure} ${s.dateFigure}`}>{job?.scheduled_for?fmtDate(job.scheduled_for):'—'}<span>작업 예정일</span></div>
        <p><strong>{failed?'오늘 예정 작업 · 갱신 실패':todayJob?`오늘 예정 작업 · ${operation.label}`:'오늘 예정 작업 · 기록 미확보'}</strong><br/>{todayJob?'전체 계좌의 작업 결과입니다. 내 계좌의 비교 자료는 성과 비교에서 확인합니다.':'아래 근거는 최근 작업 당시의 결과입니다. 오늘 실행 여부는 이 기록만으로 알 수 없습니다.'}</p><small>작업 예정일과 평가 대상일은 다를 수 있습니다. 정상 NAV 수는 평가 대상일의 저장 기록으로 확인합니다.</small><small>출처 · 일일 작업 기록·저장 NAV</small>
      </EvidenceCard>
    </div>}
    <section className={s.remaining} aria-labelledby="remaining-title">
      <div className={s.sectionHeading}><h2 id="remaining-title">아직 확인할 내용</h2><p>기록의 확보와 성과의 입증은 구분합니다.</p></div>
      <div className={s.reviewGrid}><div className={s.reviewPlan}><h3>3·6개월 경과 검토</h3>
        {data?.review_plan?<><p>{fmtDate(data.review_plan.basis_date)} 기준 점검 일정</p><ul>{data.review_plan.checkpoints.map(item=><li key={item.months}><div><strong>{item.months}개월</strong><span>{fmtDate(item.date)}</span></div><Badge tone={failed?'attention':item.state==='UPCOMING'?'pending':item.state==='DUE'?'attention':'missing'}>{failed?'갱신 실패':checkpointLabels[item.state]??'상태 미확보'}</Badge></li>)}</ul></>:<p>{failed?'조회 실패로 점검 상태를 확인할 수 없습니다.':'점검 일정을 연결할 판단 근거가 없습니다.'}</p>}
        <small>점검일 도달이나 검토 기록만으로 판단의 적중을 판정하지 않습니다.</small>
        {id&&<Link href={`/review?decision_id=${encodeURIComponent(id)}`}>검토 이유·기록 보기 <ArrowUpRight size={14}/></Link>}
      </div><div className={s.limits}>
        <article><div><h3>지속적 초과성과·예측 정확도</h3><Badge tone="missing">미입증</Badge></div><p>기간 수익률 차이만으로 지속적 우위나 판단 적중을 결론내리지 않습니다. 연간 예상과 단기 실현수익률도 직접 빼서 평가하지 않습니다.</p></article>
        <article><div><h3>반복 사용·지불 의사</h3><Badge tone="missing">근거 미등록</Badge></div><p>외부 사용자 연구 결과는 이 페이지에 등록되지 않았습니다. 기능 검사 통과는 사용자 효용의 증거가 아닙니다.</p></article>
      </div></div>
    </section>
    <section className={s.testRecord} aria-labelledby="tests-title">
      <div className={s.sectionHeading}><div><h2 id="tests-title">기록된 기능 검사</h2><p>해당 코드 버전의 검사 결과입니다. 현재 계좌 성과와는 별도입니다.</p></div><a href={evidenceRecord.runUrl} target="_blank" rel="noreferrer" className="btn-secondary">실제 검사 결과 <ArrowUpRight size={14}/></a></div>
      <div className={s.testMeta}><span>검사 완료 {koreaTime(evidenceRecord.completedAt)} · 한국 시간</span><a href={`https://github.com/MinchoLover/robo/commit/${evidenceRecord.commit}`} target="_blank" rel="noreferrer">코드 {evidenceRecord.commit.slice(0,7)}</a><span>고정 기록 · 최신 검사 자동 연동 아님</span></div>
      <div className={s.testCounts}><span>백엔드 <b>{evidenceRecord.backend}개 통과</b></span><span>프런트 <b>{evidenceRecord.frontend}개 통과</b></span><span>프로덕션 빌드 <b>{evidenceRecord.build}</b></span></div>
      <div className={s.testLinks}>{evidenceLinks.map(item=><a key={item.title} href={item.href} target="_blank" rel="noreferrer"><div><h3>{item.title}</h3><ArrowUpRight size={15} aria-hidden/></div><p>{item.description}</p><span>검사 근거 보기</span></a>)}</div>
    </section>
  </div></AppShell>;
}
