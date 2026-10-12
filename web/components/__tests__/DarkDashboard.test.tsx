import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {DarkDashboard} from '../dashboard/DarkDashboard';
const state=vi.hoisted(()=>({history:{} as any,forward:{} as any,ledger:{} as any,source:null as string|null}));
vi.mock('next/navigation',()=>({useSearchParams:()=>({get:(key:string)=>key==='source'?state.source:null})}));
vi.mock('../layout/AppShell',()=>({AppShell:({children}:any)=><>{children}</>}));
vi.mock('../layout/AppSidebar',()=>({useCurrentUser:()=>({participant_id:'P001'})}));
vi.mock('../dashboard/HistoricalPreview',()=>({useHistoricalPreview:()=>state.history}));
vi.mock('@tanstack/react-query',()=>({useQuery:({queryKey}:any)=>queryKey[0]==='dashboard-performance'?state.forward:state.ledger}));
vi.mock('../dashboard/HistoricalLedger',()=>({HistoricalLedger:()=> <div>Saved ledger</div>}));
vi.mock('../dashboard/LedgerHistory',()=>({LedgerHistory:()=> <div>Forward ledger</div>}));
vi.mock('../dashboard/ForwardOperations',()=>({ForwardOperations:()=> <div>Forward status</div>}));
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,LineChart:()=>null,Line:()=>null,XAxis:()=>null,YAxis:()=>null,CartesianGrid:()=>null,Tooltip:()=>null,PieChart:()=>null,Pie:()=>null,Cell:()=>null,ReferenceLine:()=>null,AreaChart:()=>null,Area:()=>null}));
afterEach(cleanup);
beforeEach(()=>{
 state.source=null;
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
 render(<DarkDashboard/>);fireEvent.click(screen.getByRole('button',{name:'자동운용',exact:true}));
 expect(screen.getByText('운용 기록을 기다리고 있어요')).toBeVisible();
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
 expect(screen.getByRole('button',{name:'자동운용',exact:true})).toHaveAttribute('aria-pressed','true');
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
 fireEvent.click(screen.getByRole('button',{name:'개별 자산',exact:true}));
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/미국주식 \+6.00%p/);
 expect(screen.getByRole('img',{name:/누적 기여도:/})).toHaveAccessibleName(/한국주식 \+3.00%p/);
 fireEvent.click(screen.getByRole('button',{name:'자동운용',exact:true}));
 expect(screen.queryByRole('img',{name:/누적 기여도:/})).not.toBeInTheDocument();
});
it('does not fabricate archived contribution when only summary NAV exists',()=>{
 render(<DarkDashboard/>);
 expect(screen.queryByRole('img',{name:/누적 기여도:/})).not.toBeInTheDocument();
});
