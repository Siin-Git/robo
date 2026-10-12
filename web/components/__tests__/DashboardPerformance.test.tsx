import { render,screen,fireEvent,cleanup,within } from "@testing-library/react";
import { afterEach,describe,expect,it,vi } from "vitest";
import DashboardPage from "@/app/(app)/dashboard/page";
import { exampleReport,contributionView,PERIODS,reportChartPoints } from "@/app/(app)/dashboard/performance-data";
vi.mock("next/navigation",()=>({usePathname:()=>"/dashboard",useSearchParams:()=>new URLSearchParams("view=details")}));
const baseState = vi.hoisted(()=>({status:"selected",isError:false, archive:null as any, report:null as any}));
vi.mock("@tanstack/react-query",()=>({useQuery:({queryKey}:{queryKey:string[]})=>queryKey[0]==="base-portfolio"?{data:baseState.isError?undefined:{status:baseState.status},isError:baseState.isError}:
  queryKey[0]==="own-historical-preview"?{data:baseState.archive??{available:false},isLoading:false,isError:false}:
  queryKey[0]==="ledger-status"||queryKey[0]==="ledger-alerts"?{data:null,isLoading:false,isError:false}:
  ({data:baseState.report??{status:"INSUFFICIENT_HISTORY",series:[],assets:[],metrics:{},quality:{unresolved_intervals:0,stale_observations:0,missing_nav_dates:0}},isLoading:false,isError:false})}));
vi.mock("@/components/layout/AppShell",()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
vi.mock("@/app/(app)/dashboard/performance-panels",()=>({PerformancePanels:({riskPanel}:{riskPanel:React.ReactNode})=> <div>성과 차트{riskPanel}</div>}));
afterEach(()=>{cleanup();baseState.status="selected";baseState.isError=false;baseState.report=null;baseState.archive=null;});
describe("performance dashboard",()=>{
  it("keeps all replay observations and adds null markers for excluded source dates",()=>{
    const a=exampleReport('ALL');
    a.start='2026-10-01';a.end='2026-10-05';
    a.series=[{date:'2026-10-01',personal:0,benchmark:0,drawdown:0},{date:'2026-10-05',personal:-.2,benchmark:0,drawdown:-.2}];
    a.replay_context={run_id:'test',kind:'HISTORICAL_REPLAY',label:'test',status:'COMPLETE',ready:15,required:15,completed:15,start:a.start,end:a.end,dates:['2026-10-01','2026-10-05'],forward_start:'2026-10-06',forward_started:false,initial_capital_krw:1e8,excluded_dates:[{date:'2026-10-02',missing_assets:['__FX__'],reason:'missing'}]};
    expect(reportChartPoints(a)).toEqual([
      {date:'2026-10-01',personal:0,benchmark:0,drawdown:0},
      {date:'2026-10-02',personal:null,benchmark:null,drawdown:null},
      {date:'2026-10-05',personal:-20,benchmark:0,drawdown:-20}
    ]);
  });
  it("aligns the common chart on actual dates without deleting losses or bridging an owner gap",()=>{
    const a=exampleReport('ALL');
    a.comparison_window={start:'2026-10-01',end:'2026-10-05',dates:['2026-10-01','2026-10-02','2026-10-05'],status:'AVAILABLE',reason:null};
    a.series=[{date:'2026-10-01',personal:0,benchmark:0,drawdown:0},{date:'2026-10-02',personal:-.5,benchmark:0,drawdown:-.5},{date:'2026-10-05',personal:0,benchmark:0,drawdown:0}];
    expect(reportChartPoints(a)[1]).toEqual({date:'2026-10-02',personal:-50,benchmark:0,drawdown:-50});
    a.series.splice(1,1);
    expect(reportChartPoints(a)[1]).toEqual({date:'2026-10-02',personal:null,benchmark:null,drawdown:null});
  });
  it("connects across confirmed closures while retaining unknown gaps and recorded losses",()=>{
    const a=exampleReport('ALL');
    a.start='2026-09-23';a.end='2026-09-30';a.attribution=[];
    a.series=[{date:'2026-09-23',personal:0,benchmark:0,drawdown:0},{date:'2026-09-28',personal:-.5,benchmark:0,drawdown:-.5},{date:'2026-09-30',personal:0,benchmark:0,drawdown:0}];
    a.replay_context={run_id:'test',kind:'HISTORICAL_REPLAY',label:'test',status:'COMPLETE',ready:15,required:15,completed:15,start:a.start,end:a.end,dates:a.series.map(p=>p.date),forward_start:'2026-10-06',forward_started:false,initial_capital_krw:1e8,excluded_dates:[{date:'2026-09-24',missing_assets:['korea_equity'],reason:'MARKET_CLOSED'},{date:'2026-09-29',missing_assets:['__FX__'],reason:'SOURCE_OBSERVATION_MISSING'}]};
    const before=JSON.stringify(a);
    expect(reportChartPoints(a)).toEqual([
      {date:'2026-09-23',personal:0,benchmark:0,drawdown:0},
      {date:'2026-09-28',personal:-50,benchmark:0,drawdown:-50},
      {date:'2026-09-29',personal:null,benchmark:null,drawdown:null},
      {date:'2026-09-30',personal:0,benchmark:0,drawdown:0}
    ]);
    expect(JSON.stringify(a)).toBe(before);
    // A recorded point always wins over a calendar label.
    a.replay_context.excluded_dates.push({date:'2026-09-28',missing_assets:[],reason:'MARKET_CLOSED'});
    expect(reportChartPoints(a).find(p=>p.date==='2026-09-28')?.personal).toBe(-50);
  });
  it("displays one real valuation as KRW and an index anchor, without zero performance",()=>{
    baseState.report={status:"INSUFFICIENT_HISTORY",observations:1,start:"2026-10-05",end:"2026-10-05",valuation:{date:"2026-10-05",nav_krw:123456,cash_krw:456,index100:100},series:[],assets:[],metrics:{cumulative_return:null},quality:{}};
    render(<DashboardPage/>);
    expect(screen.getByRole("region",{name:"기록된 평가액"})).toHaveTextContent("123,456원");
    expect(screen.getByText(/첫 평가 기록 1건/)).toBeInTheDocument();
    expect(screen.queryByText("내 누적수익률")).not.toBeInTheDocument();
    expect(screen.queryByText("성과 차트")).not.toBeInTheDocument();
  });
  it("does not mix example performance into the empty real account",()=>{
    render(<DashboardPage/>);
    expect(screen.getByText("포트폴리오는 저장되어 있어요")).toBeInTheDocument();
    expect(screen.queryByText("성과 차트")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"예시 데이터로 화면 살펴보기"}));
    expect(screen.getByText("DEMO / EXAMPLE · 가상 데이터")).toBeInTheDocument();
    expect(screen.getByText("성과 차트")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"내 모의운용 기록으로 돌아가기"}));
    expect(screen.queryByText("성과 차트")).not.toBeInTheDocument();
    expect(screen.getByText("포트폴리오는 저장되어 있어요")).toBeInTheDocument();
  });
  it("guides a saved account to its portfolio instead of showing empty return metrics",()=>{
    render(<DashboardPage/>);
    expect(screen.getByRole("link",{name:"저장된 포트폴리오 확인"})).toHaveAttribute("href","/portfolio");
    expect(screen.queryByText("내 누적수익률")).not.toBeInTheDocument();
  });
  it("guides a new account to setup without claiming it was saved",()=>{
    baseState.status="not_selected";
    render(<DashboardPage/>);
    expect(screen.getByRole("link",{name:"기본 포트폴리오 설계 시작"})).toHaveAttribute("href","/setup/portfolio?step=risk");
    expect(screen.queryByText("포트폴리오는 저장되어 있어요")).not.toBeInTheDocument();
  });
  it("does not claim a saved portfolio when the status request fails",()=>{
    baseState.isError=true;
    render(<DashboardPage/>);
    expect(screen.getByRole("button",{name:"저장 상태 다시 확인"})).toBeInTheDocument();
    expect(screen.queryByText("포트폴리오는 저장되어 있어요")).not.toBeInTheDocument();
  });
  it("recalculates displayed example period and keeps risk unavailable for short history",()=>{
    render(<DashboardPage/>);
    fireEvent.click(screen.getByRole("button",{name:"예시 데이터로 화면 살펴보기"}));
    fireEvent.click(within(screen.getByRole("group",{name:"성과 조회 기간"})).getByRole("button",{name:"1개월"}));
    expect(screen.getByText(/연율 위험 지표는 유효한 수익률 30개 이상/)).toBeInTheDocument();
    expect(screen.getAllByText(/2026.08.11 — 2026.09.11/)).toHaveLength(2);
  });
  it.each(PERIODS.map(p=>p.key))("reconciles group and asset contributions after %s rebasing",period=>{
    const report=exampleReport(period);
    expect(report.series[0].personal).toBe(0);
    expect(report.series[0].benchmark).toBe(0);
    for(const point of report.attribution)expect(Object.values(point.values).reduce((a,b)=>a+b,0)).toBeCloseTo(point.total,10);
    for(const mode of ["groups","assets"] as const){
      const view=contributionView(report,mode);
      expect(view.ranking.reduce((sum,r)=>sum+r.value,0)).toBeCloseTo(report.metrics.cumulative_return!,10);
      view.points.forEach(p=>expect(view.series.reduce((sum,series)=>sum+Number(p[series.id]),0)).toBeCloseTo(Number(p.total),10));
    }
  });
});

it("shows the saved ledger without the empty forward panel and keeps forward selectable",()=>{
 baseState.archive={available:true,report:{start:'2026-10-02',end:'2026-10-09',decision_confirmed_at:'2026-10-06',is_current_configuration:true,cost_bps:5,weights:{us_equity:1},price_dates:{},summary:{personal_return:.01,core_return:0,observations:2},series:[{date:'2026-10-02',personal_index:100,core_index:100},{date:'2026-10-09',personal_index:101,core_index:100}],ledger:{data_kind:'HISTORICAL_REPLAY',as_of:'2026-10-09',snapshots:[{date:'2026-10-09',nav_status:'OK',nav:1010,cash_balance:10,nav_base100:101,cumulative_return:.01,holdings:[{asset_id:'us_equity',weight:.99,quantity:2,market_value:1000,price:500,price_date:'2026-10-08',price_status:'carried_forward'}]}],orders:[{order_id:'O1',asset_id:'us_equity',side:'buy',target_weight:1,submitted_at:'2026-10-02T00:00',effective_at:'2026-10-02',status:'executed'}],trades:[{trade_id:'T1',order_id:'O1',asset_id:'us_equity',execution_at:'2026-10-02',quantity:2,execution_price:500,transaction_cost:1}]}}};
 render(<DashboardPage/>);
 expect(screen.queryByText('포트폴리오는 저장되어 있어요')).not.toBeInTheDocument();
 expect(screen.getByText('총 평가액').parentElement).toHaveTextContent('1,010원');
 expect(screen.getByText('주문 History (1)')).toBeInTheDocument();
 expect(screen.getByText('체결 History (1)')).toBeInTheDocument();
 expect(screen.getByText('모의 주문 기준 시각')).toBeInTheDocument();
 expect(screen.getByText('2026-10-08')).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'자동운용',exact:true}));
 expect(screen.getByText('포트폴리오는 저장되어 있어요')).toBeInTheDocument();
 expect(screen.queryByText('모의 주문 기준 시각')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'2026.10.02 기준 모의운용'}));
 expect(screen.getByText('체결 History (1)')).toBeInTheDocument();
});
