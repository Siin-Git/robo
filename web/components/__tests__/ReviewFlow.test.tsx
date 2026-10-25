import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import ReviewPage from '@/app/(app)/review/page';
import {getDecisions,getReview,getChoices,saveChoice,type Decision,type Review,type Choice} from '@/lib/api/decisions';
import {get} from '@/lib/api/client';
import {readRehearsalContext} from '@/lib/rehearsal-context';

const {push,params}=vi.hoisted(()=>({push:vi.fn(),params:new URLSearchParams('decision_id=new&source=rehearsal&period=2022&initial_amount=1000000')}));
vi.mock('next/navigation',()=>({useRouter:()=>({push}),useSearchParams:()=>params}));
vi.mock('@/components/layout/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><main>{children}</main>}));
vi.mock('@/lib/api/decisions',()=>({getDecisions:vi.fn(),getReview:vi.fn(),getChoices:vi.fn(),saveChoice:vi.fn()}));
vi.mock('@/lib/api/client',()=>({get:vi.fn()}));
const decision=(id:string,version:number):Decision=>({decision_id:id,version,account_id:'account',target_id:`target-${id}`,previous_decision_id:null,
  confirmed_at:'2026-10-01T00:00:00Z',target_effective_date:'2026-10-26',weights:{us_equity:1},reason:'원래 이유',expectations:{},
  provenance:{frontier_id:'frontier',risk_model_version:'saved',price_data_as_of:null,artifact_sha256:{}}});
const latest=decision('new',2),old=decision('old',1);
let client:QueryClient;
beforeEach(()=>{
  vi.clearAllMocks();client=new QueryClient({defaultOptions:{queries:{retry:false,retryDelay:1,gcTime:0}}});
  vi.mocked(getDecisions).mockResolvedValue({items:[latest,old],legacy_status:null});
  vi.mocked(getChoices).mockResolvedValue({items:[]});
  vi.mocked(getReview).mockImplementation(async id=>({decision:id==='new'?latest:old,first_execution_date:null,valuation_date:null,observation_start:null,observation_end:null,
    actual:{observations:0,status:'INSUFFICIENT_HISTORY',metrics:{}} as Review['actual'],review_only:true,review_reasons:[],comparisons:[],weight_changes:[],horizons:[]}));
  vi.mocked(get).mockResolvedValue({status:'AVAILABLE',period:{start:'2022-01-03',end:'2022-12-30'},initial_amount:1000000,base:{max_drawdown:-.14},personalized:{max_drawdown:-.16}});
  vi.mocked(saveChoice).mockImplementation(async body=>({...body,choice_id:'choice',selected_at:'2026-10-26T00:00:00Z',effect:{pending_orders:'unchanged',target_changed:false}}));
});
afterEach(()=>{cleanup();client.clear();});
function show(){return render(<QueryClientProvider client={client}><ReviewPage/></QueryClientProvider>);}

it('keeps the selected retrospective comparison visible beside the review and separates actual evidence',async()=>{
  show();expect(await screen.findByText('-16.00%')).toBeVisible();
  expect(screen.getByText('2022.01.03 ~ 2022.12.30 · 각 1,000,000원')).toBeVisible();
  expect(screen.getByText(/실제 운용 관측 0개/)).toBeVisible();
  expect(screen.getByText(/미래 손실 한도/)).toBeVisible();
  expect(screen.getByLabelText('선택 이유')).toBeVisible();
  expect(screen.getByRole('button',{name:'구성 유지 선택'})).toBeDisabled();
  expect(screen.getByRole('link',{name:'← 같은 조건의 리허설로 돌아가기'})).toHaveAttribute('href','/portfolio/rehearsal?decision_id=new&period=2022&initial_amount=1000000');
  expect(screen.getByText('확정 당시 판단 · v2')).not.toBeVisible();
  fireEvent.click(screen.getByText('확정 당시 예상과 실제 관측 근거 확인'));
  expect(screen.getByText('확정 당시 판단 · v2')).toBeVisible();
});

it('discards a draft when switching decisions and never offers saving on historical decisions',async()=>{
  show();const input=await screen.findByLabelText('선택 이유');fireEvent.change(input,{target:{value:'새 판단의 이유'}});
  fireEvent.change(screen.getByLabelText('판단 버전'),{target:{value:'old'}});
  expect(await screen.findByText(/이전 판단은 조회만 가능합니다/)).toBeVisible();
  expect(screen.queryByLabelText('선택 이유')).not.toBeInTheDocument();
  expect(screen.queryByText('-16.00%')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('판단 버전'),{target:{value:'new'}});
  expect(await screen.findByLabelText('선택 이유')).toHaveValue('');
  expect(saveChoice).not.toHaveBeenCalled();
});

it('retries the same save idempotently, preserves the original decision and focuses the saved result',async()=>{
  vi.mocked(saveChoice).mockRejectedValueOnce(new Error('저장 실패'));
  show();fireEvent.change(await screen.findByLabelText('선택 이유'),{target:{value:'  분산 목적이 유지되는지 다시 확인  '}});
  fireEvent.click(screen.getByRole('button',{name:'구성 유지 선택'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('저장 실패');
  fireEvent.click(screen.getByRole('button',{name:'구성 유지 선택'}));
  await screen.findByText('유지 선택을 저장했습니다. 목표 유지 · 정기 운용 계속');
  expect(vi.mocked(saveChoice).mock.calls[0][0]).toEqual(vi.mocked(saveChoice).mock.calls[1][0]);
  expect(saveChoice).toHaveBeenLastCalledWith(expect.objectContaining({decision_id:'new',target_id:'target-new',action:'KEEP',reason:'분산 목적이 유지되는지 다시 확인'}));
  await waitFor(()=>expect(screen.getByText('유지 선택을 저장했습니다. 목표 유지 · 정기 운용 계속').parentElement).toHaveFocus());
  expect(latest.reason).toBe('원래 이유');expect(push).not.toHaveBeenCalled();
});

it('does not redirect a different decision when an earlier adjustment completes late',async()=>{
  let finish!:(c:Choice)=>void;vi.mocked(saveChoice).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  show();fireEvent.change(await screen.findByLabelText('선택 이유'),{target:{value:'재검토'}});
  fireEvent.click(screen.getByRole('button',{name:'조정 검토 · 재설계'}));
  await waitFor(()=>expect(saveChoice).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('판단 버전'),{target:{value:'old'}});
  await screen.findByText(/이전 판단은 조회만 가능합니다/);
  finish({choice_id:'late',decision_id:'new',target_id:'target-new',action:'ADJUST',reason:'재검토',selected_at:'now',effect:{pending_orders:'unchanged',target_changed:false}});
  await waitFor(()=>expect(client.isMutating()).toBe(0));expect(push).not.toHaveBeenCalled();
});

it('opens redesign after an adjustment for the active decision',async()=>{
  show();fireEvent.change(await screen.findByLabelText('선택 이유'),{target:{value:'목표를 다시 살펴볼 필요가 있음'}});
  fireEvent.click(screen.getByRole('button',{name:'조정 검토 · 재설계'}));
  await waitFor(()=>expect(push).toHaveBeenCalledWith('/setup/portfolio?adjustment_choice_id=choice&step=risk'));
});

it('shows context failure instead of retrospective numbers and can retry',async()=>{
  vi.mocked(get).mockRejectedValue(new Error('offline'));show();
  expect(await screen.findByRole('alert')).toHaveTextContent('리허설 결과를 불러오지 못했습니다');
  expect(screen.queryByText('-16.00%')).not.toBeInTheDocument();
  vi.mocked(get).mockResolvedValue({status:'UNAVAILABLE',reason:'저장 비중 미확보'});
  fireEvent.click(screen.getByRole('button',{name:'리허설 다시 조회'}));
  expect(await screen.findByText(/비교 자료 미확보/)).toBeVisible();
});

it('accepts only supported amounts and simple period identifiers from navigation',()=>{
  expect(readRehearsalContext(new URLSearchParams('period=https://example.com&initial_amount=-1'))).toEqual({period:'all',amount:10000000});
  expect(readRehearsalContext(params)).toEqual({period:'2022',amount:1000000});
});
