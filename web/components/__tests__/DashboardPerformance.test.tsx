import { render,screen,fireEvent,cleanup,within } from "@testing-library/react";
import { afterEach,describe,expect,it,vi } from "vitest";
import DashboardPage from "@/app/(app)/dashboard/page";
import { exampleReport,contributionView,PERIODS } from "@/app/(app)/dashboard/performance-data";
vi.mock("@tanstack/react-query",()=>({useQuery:()=>({data:{status:"INSUFFICIENT_HISTORY",series:[],assets:[],metrics:{},quality:{unresolved_intervals:0,stale_observations:0,missing_nav_dates:0}},isLoading:false,isError:false})}));
vi.mock("@/components/layout/AppShell",()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
vi.mock("@/app/(app)/dashboard/performance-panels",()=>({PerformancePanels:()=> <div>성과 차트</div>}));
afterEach(cleanup);
describe("performance dashboard",()=>{
  it("does not mix example performance into the empty real account",()=>{
    render(<DashboardPage/>);
    expect(screen.getByText("성과 데이터를 쌓고 있어요")).toBeInTheDocument();
    expect(screen.queryByText("성과 차트")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"예시 데이터로 화면 살펴보기"}));
    expect(screen.getByText("화면 예시 · 실제 투자 성과가 아닙니다.")).toBeInTheDocument();
    expect(screen.getByText("성과 차트")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"실제 데이터로 돌아가기"}));
    expect(screen.queryByText("성과 차트")).not.toBeInTheDocument();
    expect(screen.getByText("성과 데이터를 쌓고 있어요")).toBeInTheDocument();
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
