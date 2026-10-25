import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {SetupStyleProvider} from '@/app/(app)/setup/SetupStyleProvider';
import {PreconfirmReview,type DraftRehearsal} from '@/app/(app)/setup/portfolio/PreconfirmReview';
import {post} from '@/lib/api/client';
vi.mock('@/lib/api/client',()=>({post:vi.fn()}));
vi.mock('@/components/dashboard/PerformanceChart',()=>({CORE_LINE:{color:'gray',width:1},MY_LINE:{color:'blue',width:2},PerformanceChart:()=> <div aria-label="비교 그래프"/>}));
let client:QueryClient;let data:DraftRehearsal;
const base=vi.fn(),themes=vi.fn();
beforeEach(()=>{
  vi.clearAllMocks();client=new QueryClient({defaultOptions:{queries:{retryDelay:1,gcTime:0}}});
  data={status:'AVAILABLE',reason:null,kind:'HISTORICAL_REHEARSAL',actual_account_history:false,decision_id:null,confirmed_at:null,selection_reason:'',currency:'KRW',initial_amount:10000000,
    period:{id:'all',label:'전체 자료 기간',start:'2020-01-02',end:'2022-12-30',observations:750},periods:[{id:'all',label:'전체 자료 기간',start:'2020-01-02',end:'2022-12-30',observations:750},{id:'2022',label:'2022년',start:'2022-01-03',end:'2022-12-30',observations:260}],
    base:{weights:{stock:1},end_value:12000000,cumulative_return:.2,max_drawdown:-.2},personalized:{weights:{stock:.8,'theme:ai':.2},end_value:13000000,cumulative_return:.3,max_drawdown:-.25},series:[],source:null,proposal:{} as DraftRehearsal['proposal']};
  vi.mocked(post).mockResolvedValue(data);
});
afterEach(()=>{cleanup();client.clear();});
function show(ids=['ai']){return render(<QueryClientProvider client={client}><SetupStyleProvider><PreconfirmReview basePoint={{frontier_id:'F1'}} themeIds={ids} onBack={vi.fn()} onComplete={themes} onCompleteBase={base} pending={false} error={false} renderDetails={()=> <div>서버 비중 상세</div>}/></SetupStyleProvider></QueryClientProvider>);}

it('compares without confirmation and offers distinct base or themed confirmation',async()=>{
  show();expect(await screen.findByText('-25.00%')).toBeVisible();expect(post).toHaveBeenCalledWith('/api/v1/me/onboarding/rehearsal',{frontier_id:'F1',theme_ids:['ai'],period:'all',initial_amount:10000000});
  expect(base).not.toHaveBeenCalled();expect(themes).not.toHaveBeenCalled();
  expect(screen.getByText('서버 비중 상세')).not.toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'기본 구성으로 확정'}));expect(base).toHaveBeenCalledOnce();expect(themes).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'선택한 테마 반영해 확정'}));expect(themes).toHaveBeenCalledOnce();
});

it('keeps controls mounted and blocks confirmation while a new period loads',async()=>{
  show();await screen.findByText('-25.00%');let finish!:(d:DraftRehearsal)=>void;
  vi.mocked(post).mockImplementation(()=>new Promise(resolve=>{finish=resolve as typeof finish;}));
  const select=screen.getByLabelText('비교 기간');select.focus();fireEvent.change(select,{target:{value:'2022'}});
  await waitFor(()=>expect(post).toHaveBeenLastCalledWith(expect.any(String),expect.objectContaining({period:'2022'})));
  expect(select).toHaveFocus();expect(screen.queryByText('-25.00%')).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'선택한 테마 반영해 확정'})).toBeDisabled();
  finish({...data,period:data.periods[1],personalized:{...data.personalized!,max_drawdown:-.12}});
  expect(await screen.findByText('-12.00%')).toBeVisible();expect(select).toHaveFocus();
});

it('rejects stale numbers after failure and enables confirmation only after a successful response',async()=>{
  vi.mocked(post).mockRejectedValue(new Error('offline'));show();await screen.findByRole('alert');
  expect(screen.queryByText('-25.00%')).not.toBeInTheDocument();expect(screen.getByRole('button',{name:'기본 구성으로 확정'})).toBeDisabled();
  vi.mocked(post).mockResolvedValue(data);fireEvent.click(screen.getByRole('button',{name:'다시 조회'}));
  expect(await screen.findByText('-25.00%')).toBeVisible();expect(screen.getByRole('button',{name:'기본 구성으로 확정'})).toBeEnabled();
});

it('labels unavailable historical data while retaining the valid proposal for explicit confirmation',async()=>{
  vi.mocked(post).mockResolvedValue({...data,status:'UNAVAILABLE',reason:'같은 기간 가격 부족',base:null,personalized:null,series:[]});
  show();expect(await screen.findByText('과거 비교 자료 미확보')).toBeVisible();expect(screen.getByText(/과거 성과 비교 없이 확정/)).toBeVisible();
  expect(screen.queryByText('0.00%')).not.toBeInTheDocument();expect(screen.getByRole('button',{name:'기본 구성으로 확정'})).toBeEnabled();
});

it('has a single base confirmation when no themes are selected',async()=>{
  show([]);await screen.findByText('-25.00%');expect(screen.queryByRole('button',{name:'선택한 테마 반영해 확정'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'기본 구성으로 확정'}));expect(themes).toHaveBeenCalledOnce();expect(base).not.toHaveBeenCalled();
});
