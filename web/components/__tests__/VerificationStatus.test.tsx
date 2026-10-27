import {render,screen,fireEvent,cleanup,within,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {VerificationStatus} from '../verification/VerificationStatus';
import {canCompare,hasTodayJob,jobStatus,koreaTime} from '../verification/status';
import type {DecisionVerification} from '../portfolio/DecisionVerificationPanel';
const state=vi.hoisted(()=>({decisions:{} as any,evidence:{} as any}));
vi.mock('../layout/AppShell',()=>({AppShell:({children}:any)=><>{children}</>}));
vi.mock('@tanstack/react-query',()=>({useQuery:({queryKey}:any)=>queryKey[0]==='decisions'?state.decisions:state.evidence}));
const makeData=():DecisionVerification=>({
  decision_id:'decision-1',version:1,confirmed_at:'2026-10-25T18:00:00Z',effective_date:'2026-10-26',reason:'장기 분산 목적',superseded_effective_date:null,
  original:{base:{expected_return:.05,volatility:.08,weights:{us_equity:1}},personalized:{expected_return:.06,volatility:.1,weights:{us_equity:1}},frontier:{version:null,points:[]},return_basis:null,risk_basis:null,price_data_as_of:null},
  actual:{status:'UNAVAILABLE',reason:'동일 날짜 정상 NAV 두 시점 필요',start:null,end:null,observations:0,excluded_rows:0,personalized_return:null,core_return:null,difference_pp:null,personalized_nav:null,core_nav:null},
  valuation_job:{status:'success',state:'START_WAIT',reason_code:'START_NOT_SCHEDULED',valuation_completed:false,scheduled_for:'2026-10-25',completed_at:'2026-10-25T12:00:00Z',valuated:0,ready:15,required:15},
  review_plan:{basis_date:'2026-10-26',basis:'CALENDAR_FROM_EFFECTIVE_OR_FORWARD_START',checkpoints:[{months:3,date:'2027-01-26',state:'UPCOMING'},{months:6,date:'2027-04-26',state:'UPCOMING'}]},
  review:{status:'IN_PROGRESS',horizon_end:null,basis:'장기 관측 필요',choice:null},
});
const available=()=>({...makeData().actual,status:'AVAILABLE' as const,start:'2026-10-26',end:'2026-10-27',observations:2,personalized_return:0,core_return:0,difference_pp:0,personalized_nav:{start:100,end:100},core_nav:{start:100,end:100}});
afterEach(cleanup);
beforeEach(()=>{
  state.decisions={data:{items:[{decision_id:'decision-1'}]},isLoading:false,isError:false,isFetching:false,dataUpdatedAt:Date.parse('2026-10-26T01:00:00Z'),refetch:vi.fn(async()=>({data:state.decisions.data}))};
  state.evidence={data:makeData(),isLoading:false,isError:false,isFetching:false,dataUpdatedAt:Date.parse('2026-10-26T01:00:01Z'),refetch:vi.fn()};
});
it('separates recorded judgment, missing performance and globally waiting valuation',()=>{
  render(<VerificationStatus/>);
  expect(within(screen.getByRole('region',{name:'판단 보존'})).getByText('저장 기록 확인')).toBeVisible();
  expect(within(screen.getByRole('region',{name:'성과 비교'})).getByText('비교 미확보')).toBeVisible();
  expect(within(screen.getByRole('region',{name:'운용 기록'})).getByText('최근 결과 · 공동 운용 시작일 미지정')).toBeVisible();
  expect(screen.queryByText('최근 평가 완료')).not.toBeInTheDocument();
  expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('운용 기록 근거 보기'));
  expect(screen.getByText('전체 계좌')).toBeVisible();
  expect(screen.getByText(/화면 새로고침은 저장된 결과만/)).toBeVisible();
});
it('shows genuine zero returns only when both dates and both NAV series are available',()=>{
  state.evidence.data.actual=available();render(<VerificationStatus/>);
  expect(screen.getByText('비교 자료 확보')).toBeVisible();
  fireEvent.click(screen.getByText('성과 비교 근거 보기'));
  expect(screen.getAllByText('0.00%')).toHaveLength(2);
  expect(screen.getByText('0.00%p')).toBeVisible();
  expect(screen.getByText('미입증')).toBeVisible();
});
it.each([
  {status:'UNAVAILABLE'}, {observations:1}, {core_nav:null}, {end:null}, {personalized_return:null},
  {difference_pp:NaN}, {start:'2026-10-27'}, {end:'2026-10-25'},
])('does not display comparison values for incomplete evidence %j',(patch)=>{
  const actual={...available(),...patch} as DecisionVerification['actual'];expect(canCompare(actual)).toBe(false);
  state.evidence.data.actual=actual;render(<VerificationStatus/>);
  expect(screen.getByText('비교 미확보')).toBeVisible();expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
});
it('does not replace missing original forecasts with current values',()=>{
  state.evidence.data.original.base.expected_return=null;state.evidence.data.original.personalized.weights={};
  render(<VerificationStatus/>);expect(screen.getByText('일부 기록 미확보')).toBeVisible();
  expect(screen.queryByText('저장 기록 확인')).not.toBeInTheDocument();
});
it.each([
  ['NAV_COMPLETE',false,'평가 완료 확인 필요'],['NAV_COMPLETE',true,'최근 평가 완료'],
  ['EVALUATION_FAILED',false,'평가 실패'],['PARTIAL',false,'평가 완료 확인 필요'],
  ['PRICE_WAIT',false,'가격 확보 대기 · 평가 미완료'],
])('requires actual completion evidence for %s / %s',(jobState,completed,label)=>{
  expect(jobStatus({...makeData().valuation_job!,state:jobState,valuation_completed:completed}).label).toBe(label);
});
it('marks cached evidence stale on refresh failure and retries without losing its timestamp',async()=>{
  state.evidence.data.actual=available();state.evidence.isError=true;render(<VerificationStatus/>);
  expect(screen.getByRole('alert')).toHaveTextContent('이전 조회 결과');
  expect(screen.getAllByText('갱신 실패 · 이전 조회')).toHaveLength(3);
  expect(screen.queryByText('비교 자료 확보')).not.toBeInTheDocument();
  expect(screen.getByText(/마지막 성공 조회/)).toHaveTextContent('10:00');
  fireEvent.click(screen.getByRole('button',{name:'기록 새로고침'}));
  await waitFor(()=>expect(state.evidence.refetch).toHaveBeenCalled());
});
it('does not show account success on an initial error or a missing judgment',()=>{
  state.evidence.data=undefined;state.evidence.isError=true;
  const view=render(<VerificationStatus/>);expect(screen.getAllByText('조회 실패')).toHaveLength(3);
  state.evidence.isError=false;state.decisions.data={items:[]};view.rerender(<VerificationStatus/>);
  expect(screen.getAllByText('확정 판단 미확보')).toHaveLength(3);
  expect(screen.queryByText('조회 실패')).not.toBeInTheDocument();
  expect(screen.getByRole('link',{name:/실제 검사 결과/})).toHaveAttribute('href','https://github.com/MinchoLover/robo/actions/runs/40442696571');
});
it('never carries the old judgment evidence to a newly selected latest decision',()=>{
  state.decisions.data.items=[{decision_id:'decision-2'}];render(<VerificationStatus/>);
  expect(screen.queryByText('저장 기록 확인')).not.toBeInTheDocument();expect(screen.queryByText('v1')).not.toBeInTheDocument();
});
it('does not treat calendar arrival or a recorded review as proof of investment accuracy',()=>{
  state.evidence.data.review_plan.checkpoints[0].state='RECORDED';state.evidence.data.review_plan.checkpoints[1].state='DUE';
  render(<VerificationStatus/>);expect(screen.getByText('검토 기록 있음')).toBeVisible();expect(screen.getByText('재검토 시점')).toBeVisible();
  expect(screen.getByText('미입증')).toBeVisible();expect(screen.getByText('근거 미등록')).toBeVisible();
  expect(screen.getByText(/최신 검사 자동 연동 아님/)).toBeVisible();
});
it('formats evidence dates in Korean time without substituting now for missing timestamps',()=>{
  expect(koreaTime(null)).toBe('미확보');expect(koreaTime('invalid')).toBe('미확보');
  expect(koreaTime('2026-10-25T18:21:54Z')).toContain('26.');expect(koreaTime('2026-10-25T18:21:54Z')).toContain('03:21');
});

it('separates yesterday start wait from today rather than claiming the start is still in the future',()=>{
  state.evidence.data.valuation_job.reason_code='AWAITING_T0';
  render(<VerificationStatus/>);
  expect(screen.getByText('최근 결과 · 당시 시작일 도달 전')).toBeVisible();
  expect(screen.getByText('오늘 예정 작업 · 기록 미확보')).toBeVisible();
  expect(screen.queryByText('지정된 공동 운용 시작일 도달 전')).not.toBeInTheDocument();
});
it('uses the Korean calendar date of the successful response and never assumes execution from elapsed time',()=>{
  const job={...makeData().valuation_job!,scheduled_for:'2026-10-26'};
  expect(hasTodayJob(job,Date.parse('2026-10-25T14:59:59Z'))).toBe(false);
  expect(hasTodayJob(job,Date.parse('2026-10-25T15:00:00Z'))).toBe(true);
  expect(hasTodayJob({...job,scheduled_for:'2026-10-25'},Date.parse('2026-10-26T14:00:00Z'))).toBe(false);
  expect(hasTodayJob(null,Date.parse('2026-10-26T14:00:00Z'))).toBe(false);
});
it.each([['RUNNING',false,'평가 작업 진행 중'],['EVALUATION_FAILED',false,'평가 실패'],['NAV_COMPLETE',true,'최근 평가 완료']])('shows today recorded state %s without hiding failures',(status,completed,label)=>{
  state.evidence.data.valuation_job={...makeData().valuation_job!,scheduled_for:'2026-10-26',state:status,valuation_completed:completed};
  render(<VerificationStatus/>);
  expect(screen.getByText(`오늘 예정 작업 · ${label}`)).toBeVisible();
});

it('displays separate evidence for a current scheduled job using a prior valuation date',()=>{
 Object.assign(state.evidence.data.valuation_job,{state:'PRICE_WAIT',scheduled_for:'2026-10-26',valuation_date:'2026-10-25',valuated:30,normal_nav_accounts:0,stale_nav_accounts:30,expected_nav_accounts:30});
 render(<VerificationStatus/>);
 expect(screen.getByText('오늘 예정 작업 · 가격 확보 대기 · 평가 미완료')).toBeVisible();
 fireEvent.click(screen.getByText('운용 기록 근거 보기'));
 const region=within(screen.getByRole('region',{name:'운용 기록'}));
 expect(region.getByText('평가 대상일').parentElement).toHaveTextContent('2026.10.25');
 expect(region.getByText('정상 NAV 계좌 수').parentElement).toHaveTextContent('0');
 expect(region.getByText('가격 지연 NAV 계좌 수').parentElement).toHaveTextContent('30');
 expect(region.queryByText('최근 평가 완료')).not.toBeInTheDocument();
});

it('keeps saved forecasts, paired risk and weights on this page without requiring a portfolio visit',()=>{
 state.evidence.data.original.base.volatility=.07829124;
 state.evidence.data.risk_change={status:'AVAILABLE',base_volatility:.07885536,personalized_volatility:.08885536,difference_pp:1,as_of:'2026-09-11',method:'saved model'};
 render(<VerificationStatus/>);
 const original=within(screen.getByRole('table',{name:'확정 당시 예상 수익률과 변동성'}));
 expect(original.getByText('7.83%')).toBeVisible();
 expect(screen.getByText('7.89%')).toBeVisible();expect(screen.getByText('+1.00%p')).toBeVisible();
 fireEvent.click(screen.getByText('확정 당시 비중 보기'));
 expect(screen.getByRole('table',{name:'확정 당시 자산 비중'})).toBeVisible();
 const flow=within(screen.getByRole('navigation',{name:'검증 흐름'}));
 expect(flow.getAllByRole('link').map(a=>a.getAttribute('href'))).toEqual(['#saved-judgment','#review-evidence','#tests-title']);
 expect(screen.queryByRole('link',{name:/당시 비중·위험 근거 보기|검토 이유·기록 보기|이 판단의 성과 상세/})).not.toBeInTheDocument();
});
it('shows the actual stored review reason and time without offering a write action',()=>{
 state.evidence.data.review.choice={action:'ADJUST',reason:'위험 허용 범위를 다시 검토',recorded_at:'2026-10-25T18:00:00Z'};
 render(<VerificationStatus/>);
 const review=within(screen.getByRole('region',{name:'최근 검토 기록'}));
 expect(review.getByText('구성 조정 검토')).toBeVisible();expect(review.getByText('위험 허용 범위를 다시 검토')).toBeVisible();
 expect(review.getByText(/2026. 10. 26./)).toBeVisible();expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
 expect(screen.getByText(/모형이나 주문이 바뀌지는 않습니다/)).toBeVisible();
});
it('separates verified test methods, synthetic arithmetic examples and unverified investment outcomes',()=>{
 render(<VerificationStatus/>);
 expect(screen.getByRole('table',{name:/완료된 검사/})).toBeVisible();
 expect(screen.getByText(/계산 검사용 가상 입력입니다/)).toBeVisible();
 expect(screen.getByText('863개 통과')).toBeVisible();expect(screen.getByText('182개 통과')).toBeVisible();
 expect(screen.getByText('기록 기능 확인 · 수정 기준 미합의')).toBeVisible();
 expect(screen.getByText(/실제로 판단이 쉬워지는지/)).toBeVisible();
 expect(screen.getByText('자산별 3·6개월 추적')).toBeVisible();
});
