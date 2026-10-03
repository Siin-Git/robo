import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SetupPortfolioPage from "@/app/(app)/setup/portfolio/page";
import { SetupStyleProvider } from "@/app/(app)/setup/SetupStyleProvider";

const state = vi.hoisted(() => ({
  search: "step=risk", frequency: "monthly" as string | undefined, save: vi.fn(), complete: vi.fn(),
  frontier: {benchmark_frontier_id:"F001", assets:[], points:[{frontier_id:"F001",expected_return:.05,volatility:.07,sharpe:.3,weights:[]}]},
  preview: {base:{frontier_id:"F001",expected_return:.05,volatility:.07,weights:[],groups:{}}, personalized:{expected_return:.05,volatility:null,tracking_error:null,weights:[],groups:{}},themes:[],risk_guardrail_applied:false},
}));
vi.mock("next/navigation", () => ({ useSearchParams:()=>new URLSearchParams(state.search), useRouter:()=>({push:vi.fn()}) }));
vi.mock("@/components/layout/AppShell", () => ({AppShell:({children}:{children:React.ReactNode})=><>{children}</>}));
vi.mock("@/app/(app)/setup/portfolio/FrontierChart", () => ({FrontierChart:()=> <div>Frontier</div>,GROUP_COLORS:{},ASSET_COLORS:{}}));
vi.mock("recharts", () => ({PieChart:()=>null,Pie:()=>null,Cell:()=>null,ResponsiveContainer:()=>null}));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient:()=>({invalidateQueries:vi.fn()}),
  useMutation:({mutationFn}:{mutationFn:unknown})=>({mutateAsync:state.save,mutate:state.complete,isPending:false,isError:false}),
  useQuery:({queryKey}:{queryKey:string[]})=>({isLoading:false,isError:false,data:
    queryKey[0]==="onboarding-draft" ? {status:"draft",frontier_id:"F001",theme_ids:[],rebalance_frequency:state.frequency} :
    queryKey[0]==="frontier" ? state.frontier : queryKey[0]==="decisions" ? {items:[]} :
    queryKey[0].includes("preview") ? state.preview : {items:[]}}),
}));

describe("frequency belongs to the initial frontier",()=>{
  beforeEach(()=>{state.search="step=risk";state.frequency="monthly";state.save.mockReset().mockResolvedValue({});state.complete.mockReset();});
  afterEach(cleanup);
  it("defaults to monthly, preserves changes across back navigation and sends both draft and confirmation",async()=>{
    render(<SetupStyleProvider><SetupPortfolioPage/></SetupStyleProvider>);
    expect(screen.getByRole("radio",{name:"매월"})).toBeChecked();
    expect(screen.getByText(/18% 미만 또는 22% 초과/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio",{name:"매분기"}));
    fireEvent.click(screen.getByRole("button",{name:"다음: 투자 인사이트 반영"}));
    await waitFor(()=>expect(screen.queryByRole("radio")).not.toBeInTheDocument());
    expect(state.save).toHaveBeenLastCalledWith(expect.objectContaining({rebalance_frequency:"quarterly",current_step:"themes"}));
    fireEvent.click(screen.getByRole("button",{name:"위험 수준 다시 보기"}));
    expect(screen.getByRole("radio",{name:"매분기"})).toBeChecked();
    fireEvent.click(screen.getByRole("button",{name:"다음: 투자 인사이트 반영"}));
    await waitFor(()=>expect(screen.getByRole("button",{name:"다음: 변경 전·후 비교"})).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button",{name:"다음: 변경 전·후 비교"}));
    await waitFor(()=>expect(screen.getByLabelText("확정 전 리밸런싱 주기")).toHaveTextContent("매분기"));
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"포트폴리오 확정 · 성과 확인"}));
    expect(state.complete).toHaveBeenCalledWith(expect.objectContaining({rebalance_frequency:"quarterly"}));
  });
  it("hydrates a saved choice once and preserves an unsaved edit during query refetch",()=>{
    state.frequency="quarterly";
    const {rerender}=render(<SetupStyleProvider><SetupPortfolioPage/></SetupStyleProvider>);
    expect(screen.getByRole("radio",{name:"매분기"})).toBeChecked();
    fireEvent.click(screen.getByRole("radio",{name:"매월"}));
    rerender(<SetupStyleProvider><SetupPortfolioPage/></SetupStyleProvider>);
    expect(screen.getByRole("radio",{name:"매월"})).toBeChecked();
  });
  it("does not pretend an older API supports persisting the selection",()=>{
    state.frequency=undefined;
    const {rerender}=render(<SetupStyleProvider><SetupPortfolioPage/></SetupStyleProvider>);
    expect(screen.getByText(/API에서 리밸런싱 주기 저장 지원을 확인하지 못했습니다/)).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    state.frequency='quarterly';
    rerender(<SetupStyleProvider><SetupPortfolioPage/></SetupStyleProvider>);
    expect(screen.getByRole('radio',{name:'매분기'})).toBeChecked();
  });
});
