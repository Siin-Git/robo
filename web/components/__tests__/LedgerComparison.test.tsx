import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {LedgerComparison} from '@/components/performance/LedgerComparison';
const state=vi.hoisted(()=>({data:null as any,chart:null as any}));
vi.mock('@tanstack/react-query',()=>({useQuery:({queryKey}:{queryKey:string[]})=>({data:queryKey[0]==='comparison-identity'?{participant_id:'A'}:state.data})}));
vi.mock('@/components/layout/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
vi.mock('@/components/dashboard/PerformanceChart',()=>({CORE_LINE:{color:'grey',width:1},MY_LINE:{color:'blue',width:2},PerformanceChart:(props:unknown)=>{state.chart=props;return <div>기준 100 차트</div>;}}));
afterEach(()=>{cleanup();state.chart=null;state.data=null;});
const metrics={cumulative_return:null,benchmark_return:null,difference_pp:null,mdd:null,volatility:null,tracking_error:null,information_ratio:null};
function peer(id:string,reason:string|null=null){return {participant_id:id,display_name:id,rank:reason?null:1,reason,metrics:{...metrics},observations:1,observed_start:'2026-10-02',observed_end:'2026-10-02',series:[]};}
it('shows one-observation reason without a fabricated return, rank or chart',()=>{
 state.data={items:[peer('A','ONE_VALUATION')],dates:[],ranked:0,registered:1,status:'UNAVAILABLE',reason:'INSUFFICIENT_PARTICIPANTS'};
 render(<LedgerComparison/>);
 expect(screen.getAllByText(/평가 기록 1건/).length).toBeGreaterThan(0);
 expect(screen.queryByText('기준 100 차트')).not.toBeInTheDocument();
 expect(screen.getByRole('region',{name:'운용 기록 참여자 순위'})).toHaveTextContent('대기');
 expect(screen.queryByText('0.00%')).not.toBeInTheDocument();
});
it('uses server index100 data and the selected peers CORE, without filling a missing observation',()=>{
 const a={...peer('A'),metrics:{...metrics,cumulative_return:.1},series:[{date:'2026-10-02',personal_index100:100,core_index100:100},{date:'2026-10-05',personal_index100:110,core_index100:null}]};
 const b={...peer('B'),metrics:{...metrics,cumulative_return:.2},series:[{date:'2026-10-02',personal_index100:100,core_index100:100},{date:'2026-10-05',personal_index100:120,core_index100:101}]};
 state.data={items:[a,b],dates:['2026-10-02','2026-10-05'],start:'2026-10-02',end:'2026-10-05',ranked:2,registered:2,status:'AVAILABLE',reason:null};
 render(<LedgerComparison/>);
 expect(state.chart.connectNulls).toBe(false);
 expect(state.chart.data[1]).toEqual({date:'2026-10-05',A:110,B:120,core:null});
 fireEvent.click(screen.getByRole('button',{name:'B'}));
 expect(state.chart.data[1].core).toBe(101);
 expect(screen.getByRole('link',{name:'공통 기간의 내 성과·기여도'})).toHaveAttribute('href','/dashboard?comparison=common&period=ALL');
 expect(within(screen.getByRole('region',{name:'선택 참여자 성과'})).getByText(/연율 변동성 —/)).toBeInTheDocument();
});
