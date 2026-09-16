import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PortfolioPage from "@/app/(app)/portfolio/page";

const state = vi.hoisted(() => ({ data: {
  base: { frontier_id: "F036", expected_return: .0578, volatility: .0851, weights: [{asset_id:"us_equity",weight:.6},{asset_id:"us_treasury",weight:.4}], groups:{equity:.6,fixed_income:.4} },
  personalized: {volatility:.0957,tracking_error:.0193,weights:[{asset_id:"us_equity",weight:.52},{asset_id:"us_treasury",weight:.4},{asset_id:"semiconductor",weight:.08}],groups:{broad_equity:.52,fixed_income:.4,themes:.08}},
  themes:[{theme_id:"semiconductor",ticker:"SOXX",weight:.08}],
  risk_comparison:{base_volatility:.0857 as number|null,personalized_volatility:.0957 as number|null,as_of:"2026-09-11",method:"5Y weekly Ledoit-Wolf"},
} }));
vi.mock("@tanstack/react-query", () => ({useQuery:()=>({data:state.data,isLoading:false,isError:false})}));
vi.mock("@/components/layout/AppShell",()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
describe("portfolio dashboard",()=>{
  afterEach(cleanup);
  beforeEach(()=>{state.data.risk_comparison.base_volatility=.0857;state.data.risk_comparison.personalized_volatility=.0957;});
  it("connects chart and list with actual theme holdings and keeps detail collapsed",()=>{
    render(<PortfolioPage/>);
    const chart=screen.getByRole("group",{name:"현재 자산 구성 도넛 차트"});
    fireEvent.focus(within(chart).getByRole("button",{name:"반도체 8.00%"}));
    const list=screen.getByRole("list",{name:"현재 자산별 비중"});
    expect(within(list).getByRole("button",{name:/반도체/})).toHaveAttribute("aria-pressed","true");
    const table=screen.getByText("자산별 변경 내역 보기").closest("details");
    expect(table).not.toHaveAttribute("open");
    const row=within(table!).getByText("반도체").closest("tr");
    expect(within(row!).getByText("8.00%")).toBeInTheDocument();
    expect(within(row!).getByText("+8.00%p")).toBeInTheDocument();
  });
  it("uses comparable risk and labels expected return as base-only",()=>{
    render(<PortfolioPage/>);
    expect(screen.getByText("8.57%")).toBeInTheDocument();
    expect(screen.getByText("+1.00%p")).toBeInTheDocument();
    expect(screen.queryByText("+1.06%p")).not.toBeInTheDocument();
    expect(screen.getByText("기본 구성의 기대수익률").closest("details")).not.toHaveAttribute("open");
  });
  it("does not infer a risk difference from incompatible baselines",()=>{
    state.data.risk_comparison.base_volatility=null;
    state.data.risk_comparison.personalized_volatility=null;
    render(<PortfolioPage/>);
    expect(screen.getByText("같은 기준의 위험 지표를 산출할 데이터가 부족합니다.")).toBeInTheDocument();
    expect(screen.queryByText("+1.06%p")).not.toBeInTheDocument();
  });
});
