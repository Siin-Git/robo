import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {DarkDashboard} from '../dashboard/DarkDashboard';
const state=vi.hoisted(()=>({history:{} as any,forward:{} as any,ledger:{} as any,continuity:{} as any,source:null as string|null}));
vi.mock('next/navigation',()=>({useSearchParams:()=>({get:(key:string)=>key==='source'?state.source:null})}));
vi.mock('../layout/AppShell',()=>({AppShell:({children}:any)=><>{children}</>}));
vi.mock('../layout/AppSidebar',()=>({useCurrentUser:()=>({participant_id:'P001'})}));
vi.mock('../dashboard/HistoricalPreview',()=>({useHistoricalPreview:()=>state.history}));
vi.mock('@tanstack/react-query',()=>({useQuery:({queryKey}:any)=>queryKey[0]==='dashboard-performance'?state.forward:queryKey[0]==='own-continuity'?state.continuity:state.ledger}));
vi.mock('../dashboard/HistoricalLedger',()=>({HistoricalLedger:()=> <div>Saved ledger</div>}));
vi.mock('../dashboard/LedgerHistory',()=>({LedgerHistory:()=> <div>Forward ledger</div>}));
vi.mock('../dashboard/OperationReadiness',()=>({OperationReadiness:()=> <div>서버가 확인한 운용 대기 사유</div>}));
vi.mock('../dashboard/ForwardOperations',()=>({ForwardOperations:()=> <div>Forward status</div>}));
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,LineChart:()=>null,Line:()=>null,XAxis:()=>null,YAxis:()=>null,CartesianGrid:()=>null,Tooltip:()=>null,PieChart:()=>null,Pie:()=>null,Cell:()=>null,ReferenceLine:()=>null,AreaChart:()=>null,Area:()=>null}));
afterEach(cleanup);
beforeEach(()=>{
 state.source=null;
 state.continuity={isLoading:false,isError:false,data:{available:false},refetch:vi.fn()};
 state.forward={isLoading:false,isError:false,data:{series:[],metrics:{},observations:0},refetch:vi.fn()};
 state.ledger={data:{snapshots:[],trades:[],orders:[]},refetch:vi.fn()};
 state.history={isLoading:false,isError:false,refetch:vi.fn(),data:{available:true,report:{start:'2026-10-02',end:'2026-10-09',decision_confirmed_at:'2026-10-06',is_current_configuration:true,cost_bps:5,price_dates:{},summary:{personal_return:-.0085,core_return:-.009,observations:2},series:[{date:'2026-10-02',personal_index:100,core_index:100},{date:'2026-10-09',personal_index:99.15,core_index:99.1}],ledger:{snapshots:[{date:'2026-10-09',nav:99100000,cash_balance:100000,holdings:[]}],orders:[],trades:[]}}}};
});
it('uses saved server values and preserves provenance, not demo gains',()=>{
 render(<DarkDashboard/>);
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('99,100,000원');
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('-0.85%');
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('+0.05%p');
 expect(screen.getByText(/사후 계산한 모의운용입니다/)).toBeInTheDocument();
 expect(screen.getByRole('link',{name:'상세 분석'})).toHaveAttribute('href','/dashboard?view=details&source=archive');
});
it('switches to empty forward without substituting saved results',()=>{
 render(<DarkDashboard/>);fireEvent.click(screen.getByText('계산 기준과 데이터 확인'));fireEvent.click(screen.getByRole('button',{name:'시작 이후 기록'}));
 expect(screen.getByText('서버가 확인한 운용 대기 사유')).toBeVisible();
 expect(screen.queryByText('99,100,000원')).not.toBeInTheDocument();
 expect(screen.getByRole('link',{name:'상세 분석'})).toHaveAttribute('href','/dashboard?view=details&source=forward');
});
it('does not silently hide archive fetch failure as an empty record',()=>{
 state.history={...state.history,isError:true,data:undefined};render(<DarkDashboard/>);
 expect(screen.getByRole('alert')).toHaveTextContent('불러오지 못했어요');
 fireEvent.click(screen.getByRole('button',{name:'다시 불러오기'}));expect(state.history.refetch).toHaveBeenCalled();
});
it('waits for source selection before rendering numbers',()=>{
 state.forward.isLoading=true;render(<DarkDashboard/>);
 expect(screen.getByRole('status')).toHaveTextContent('불러오고 있어요');
 expect(screen.queryByRole('region',{name:'성과 요약'})).not.toBeInTheDocument();
});
it('honors an explicit forward link when archived results exist',()=>{
 state.source='forward';render(<DarkDashboard/>);
 fireEvent.click(screen.getByText('계산 기준과 데이터 확인'));expect(screen.getByRole('button',{name:'시작 이후 기록'})).toHaveAttribute('aria-pressed','true');
 expect(screen.queryByText('99,100,000원')).not.toBeInTheDocument();
});

it('shows archived server attribution and toggles asset groups without mixing forward records',()=>{
 state.history.data.report.performance_report={
  start:'2026-10-02',end:'2026-10-09',period:'ALL',observations:2,
  metrics:{cumulative_return:.08,benchmark_return:.02,mdd:0},
  series:[{date:'2026-10-02',personal:0,benchmark:0,drawdown:0},{date:'2026-10-09',personal:.08,benchmark:.02,drawdown:0}],
  assets:[{asset_id:'us_equity',group:'equity',contribution:.06},{asset_id:'korea_equity',group:'equity',contribution:.03},{asset_id:'costs',group:'costs',contribution:-.01}],
  attribution:[{date:'2026-10-02',total:0,values:{us_equity:0,korea_equity:0,costs:0}},{date:'2026-10-09',total:.08,values:{us_equity:.06,korea_equity:.03,costs:-.01}}],
  quality:{unresolved_intervals:0,benchmark_complete:true}
 };
 render(<DarkDashboard/>);
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/일반 주식 \+9.00%p/);
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/거래비용 -1.00%p/);
 fireEvent.click(screen.getByRole('button',{name:'개별 자산'}));
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/미국주식 \+6.00%p/);
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/한국주식 \+3.00%p/);
 fireEvent.click(screen.getByText('계산 기준과 데이터 확인'));fireEvent.click(screen.getByRole('button',{name:'시작 이후 기록'}));
 expect(screen.queryByRole('img',{name:/누적 기여도:/})).not.toBeInTheDocument();
});
it('does not fabricate archived contribution when only summary NAV exists',()=>{
 render(<DarkDashboard/>);
 expect(screen.queryByRole('img',{name:/누적 기여도:/})).not.toBeInTheDocument();
});


it('preserves previous forward data and distinguishes refresh failure',()=>{
 state.source='forward';state.forward.isError=true;
 render(<DarkDashboard/>);
 expect(screen.getByRole('alert')).toHaveTextContent('이전 조회 결과');
 expect(screen.getByRole('region',{name:'성과 요약'})).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'다시 조회'}));
 expect(state.forward.refetch).toHaveBeenCalled();
});

function connected(){
 state.continuity.data={available:true,forward_start:'2026-10-26',historical_start:'2026-10-01',historical_end:'2026-10-24',forward_observations:1,
 summary:{start:'2026-10-01',end:'2026-10-26',observations:3,personal_return:-.04,core_return:-.05,difference_pp:.01,missing_observations:0},
 snapshot:{date:'2026-10-26',nav:96000000,cash_balance:100000,holdings:[]},
 series:[{date:'2026-10-01',personal_nav:100000000,core_nav:100000000,personal_index:100,core_index:100,data_kind:'HISTORICAL_REPLAY'},
 {date:'2026-10-23',personal_nav:97000000,core_nav:96000000,personal_index:97,core_index:96,data_kind:'HISTORICAL_REPLAY'},
 {date:'2026-10-26',personal_nav:96000000,core_nav:95000000,personal_index:96,core_index:95,data_kind:'FORWARD_SIMULATION'}]};
}
it('defaults to server-verified continuity without a duplicate chart or attribution from another period',()=>{
 connected();render(<DarkDashboard/>);
 expect(screen.getByRole('group',{name:'운용 기록 선택'})).not.toBeVisible();
 expect(screen.getByRole('link',{name:'내 선택 점검'})).toHaveAttribute('href','/portfolio#portfolio-check');
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('96,000,000원');
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('-4.00%');
 expect(screen.getByText(/저장된 구성을 과거 가격에 적용한 결과/)).not.toBeVisible();
 expect(screen.getAllByRole('img',{name:/누적 수익률/})).toHaveLength(1);
 expect(screen.queryByRole('img',{name:/누적 기여도/})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('link',{name:'기간별 평가액'}));
 expect(screen.getByRole('table',{name:'저장된 NAV · 원'})).toBeVisible();
 expect(screen.getByText(/저장된 구성을 과거 가격에 적용한 결과/)).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:'시작 이후 기록'}));
 expect(screen.queryByText('96,000,000원')).not.toBeInTheDocument();
 expect(screen.getByText('서버가 확인한 운용 대기 사유')).toBeVisible();
});
it('does not replace an explicit forward view with the combined curve',()=>{
 connected();state.source='forward';render(<DarkDashboard/>);
 fireEvent.click(screen.getByText('계산 기준과 데이터 확인'));expect(screen.getByRole('button',{name:'시작 이후 기록'})).toHaveAttribute('aria-pressed','true');
 expect(screen.queryByText('96,000,000원')).not.toBeInTheDocument();
});
it('keeps the selected combined record and clearly marks refresh failure',()=>{
 connected();state.continuity.isError=true;render(<DarkDashboard/>);
 expect(screen.getByRole('alert')).toHaveTextContent('이전 조회 결과');
 expect(screen.getByRole('region',{name:'성과 요약'})).toHaveTextContent('96,000,000원');
});
it('does not silently fall back when an explicit combined record is unavailable',()=>{
 state.source='all';render(<DarkDashboard/>);
 expect(screen.getByRole('alert')).toHaveTextContent('불러오지 못했어요');
 expect(screen.queryByRole('region',{name:'성과 요약'})).not.toBeInTheDocument();
});
it('marks missing valuation dates instead of claiming complete daily coverage',()=>{
 connected();state.continuity.data.summary.missing_observations=1;render(<DarkDashboard/>);
 expect(screen.getByText(/평가 미확보 1일/)).toBeVisible();
});

it('shows stored residual cash with pending-order context and opens its history',()=>{
 connected();state.continuity.data.snapshot.cash_balance=520.1554;
 state.ledger.data.orders=[{status:'pending'},{status:'filled'},{status:'pending'}];
 render(<DarkDashboard/>);
 const metric=screen.getByText('미투자 현금').parentElement!;
 expect(metric).toHaveTextContent('520원');expect(metric).toHaveTextContent('대기 주문 2건');
 fireEvent.click(screen.getByRole('link',{name:'현금 내역'}));
 expect(document.getElementById('dark-records')).toHaveAttribute('open');
});
it('preserves zero recorded cash instead of substituting an earlier balance',()=>{
 connected();state.continuity.data.snapshot.cash_balance=0;render(<DarkDashboard/>);
 expect(screen.getByText('미투자 현금').parentElement).toHaveTextContent('0원');
});
