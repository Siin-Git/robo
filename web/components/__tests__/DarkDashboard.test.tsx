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
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,LineChart:()=>null,Line:()=>null,XAxis:()=>null,YAxis:()=>null,CartesianGrid:()=>null,Tooltip:()=>null,PieChart:()=>null,Pie:()=>null,Cell:()=>null,ReferenceLine:()=>null}));
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
