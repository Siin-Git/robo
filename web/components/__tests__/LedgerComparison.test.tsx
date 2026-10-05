import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {LedgerComparison} from '@/components/performance/LedgerComparison';
const state=vi.hoisted(()=>({data:null as any,chart:null as any}));
vi.mock('@tanstack/react-query',()=>({useQuery:({queryKey}:{queryKey:string[]})=>({data:queryKey[0]==='comparison-identity'?{participant_id:'A'}:state.data})}));
vi.mock('@/components/layout/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
vi.mock('@/components/dashboard/PerformanceChart',()=>({CORE_LINE:{color:'grey',width:1},MY_LINE:{color:'blue',width:2},PerformanceChart:(props:unknown)=>{state.chart=props;return <div>기준 100 차트</div>;}}));
afterEach(()=>{cleanup();state.chart=null;state.data=null;vi.unstubAllGlobals();});
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
 fireEvent.click(screen.getByText('비교 기준 보기'));
 expect(within(screen.getByRole('region',{name:'선택 참여자 성과'})).getByText(/연율 변동성 —/)).toBeInTheDocument();
});
it('retains the interior loss and null gap, and distinguishes observed MDD from annualized risk and ranks',()=>{
 const a={...peer('A'),observations:3,rank:null,reason:'INSUFFICIENT_COMPARABLE_METRIC',metrics:{...metrics,cumulative_return:0,mdd:-.5},series:[{date:'2026-10-01',personal_index100:100,core_index100:100},{date:'2026-10-02',personal_index100:50,core_index100:100},{date:'2026-10-05',personal_index100:100,core_index100:100}]};
 const b={...peer('B'),observations:2,rank:null,reason:'OBSERVATION_GAPS',metrics:{...metrics,cumulative_return:.01,mdd:0},quality:{missing_nav_dates:1,stale_observations:0,missing_comparison_dates:['2026-10-02']},metric_quality:{mdd:{status:'OBSERVED_ONLY',rankable:false,reason:'OBSERVATION_GAPS'},volatility:{status:'UNAVAILABLE',rankable:false,reason:'OBSERVATION_GAPS',return_observations:1,minimum_return_observations:30}},series:[{date:'2026-10-01',personal_index100:100,core_index100:100},{date:'2026-10-02',personal_index100:null,core_index100:null},{date:'2026-10-05',personal_index100:101,core_index100:100}]};
 state.data={items:[a,b],dates:['2026-10-01','2026-10-02','2026-10-05'],start:'2026-10-01',end:'2026-10-05',ranked:0,registered:2,status:'UNAVAILABLE',reason:'INSUFFICIENT_COMPARABLE_METRIC'};
 render(<LedgerComparison/>);
 expect(state.chart.data[1]).toEqual({date:'2026-10-02',A:50,B:null,core:100});
 expect(state.chart.connectNulls).toBe(false);
 expect(state.chart.curve).toBe('linear');
 expect(state.chart.showPoints).toBe(true);
 expect(screen.getAllByText(/-50.00%/).length).toBeGreaterThan(0);
 fireEvent.click(screen.getByRole('button',{name:'B'}));
 fireEvent.click(screen.getByText('비교 기준 보기'));
 const detail=screen.getByRole('region',{name:'선택 참여자 성과'});
 expect(detail).toHaveTextContent('MDD는 유효 평가 2건 이상');
 expect(detail).toHaveTextContent('연율 변동성은 별도로 유효 수익률 30개 이상');
 expect(detail).toHaveTextContent('위험 순위 보류');
 expect(detail).toHaveTextContent('유효 수익률 1개 / 필요 30개');
 fireEvent.change(screen.getByLabelText('순위 기준'),{target:{value:'mdd'}});
 expect(screen.getByRole('region',{name:'운용 기록 참여자 순위'})).toHaveTextContent('MDD 순위 보류');
});

it('keeps full precision server return ranks for top-five and KPI when the table uses a risk basis',()=>{
 const items=Array.from({length:6},(_,i)=>({...peer(i===0?'A':`P${i}`),rank:null,return_rank:6-i,observations:2,
   metrics:{...metrics,cumulative_return:.01},series:[{date:'2026-10-02',personal_index100:100,core_index100:100},{date:'2026-10-05',personal_index100:101,core_index100:102}]}));
 state.data={items,dates:['2026-10-02','2026-10-05'],ranked:0,return_ranked:6,registered:6};
 render(<LedgerComparison/>);
 fireEvent.change(screen.getByLabelText('순위 기준'),{target:{value:'mdd'}});
 expect(screen.getByRole('region',{name:'투자 성과 비교'})).toHaveTextContent('6위');
 fireEvent.click(screen.getByRole('button',{name:'상위 5명'}));
 expect(state.chart.series.filter((s:any)=>s.key!=='core')).toHaveLength(5);
 expect(state.chart.series.some((s:any)=>s.key==='A')).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'나와 기준'}));
 expect(state.chart.series.map((s:any)=>s.key)).toEqual(['A','core']);
});

it('does not present measured volatility as an available scatter point when server quality blocks it',()=>{
 const a={...peer('A'),observations:32,metrics:{...metrics,cumulative_return:.1,volatility:.2},metric_quality:{volatility:{rankable:false,reason:'OBSERVATION_GAPS'}}};
 state.data={items:[a,{...a,participant_id:'B',display_name:'B'}],dates:[],ranked:0,registered:2};
 render(<LedgerComparison/>);
 expect(screen.getByRole('region',{name:'위험과 수익 비교'})).toHaveTextContent('현재 산출 가능한 참여자 0명');
 expect(screen.queryByRole('button',{name:'A 비교'})).not.toBeInTheDocument();
 expect(screen.getByText('비교 기준 보기').closest('details')).not.toHaveAttribute('open');
});

it('shows risk comparison controls only for participants passing the server volatility gate',()=>{
 vi.stubGlobal('ResizeObserver',class {observe(){} unobserve(){} disconnect(){}});
 const a={...peer('A'),observations:32,metrics:{...metrics,cumulative_return:.1,volatility:.2},metric_quality:{mdd:{status:'AVAILABLE',rankable:true,reason:null},volatility:{status:'AVAILABLE',rankable:true,reason:null}}};
 state.data={items:[a,{...a,participant_id:'B',display_name:'B'},{...a,participant_id:'C',display_name:'C',metric_quality:{...a.metric_quality,volatility:{status:'UNAVAILABLE',rankable:false,reason:'STALE_VALUATIONS'}}}],dates:[],ranked:2,registered:3};
 render(<LedgerComparison/>);
 const risk=screen.getByRole('region',{name:'위험과 수익 비교'});
 expect(within(risk).getByRole('button',{name:'A 비교'})).toBeInTheDocument();
 expect(within(risk).getByRole('button',{name:'B 비교'})).toBeInTheDocument();
 expect(within(risk).queryByRole('button',{name:'C 비교'})).not.toBeInTheDocument();
 fireEvent.click(within(risk).getByRole('button',{name:'B 비교'}));
 expect(screen.getByRole('region',{name:'투자 성과 비교'})).toHaveTextContent('B 수익률');
});
