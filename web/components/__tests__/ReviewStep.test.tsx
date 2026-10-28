import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewStep } from "@/app/(app)/setup/portfolio/ReviewStep";
import { SetupStyleProvider } from "@/app/(app)/setup/SetupStyleProvider";
import { reviewRows } from "@/app/(app)/setup/portfolio/review-data";

const state = vi.hoisted(() => ({
  ledger: {data:{orders:[] as {status:string}[]},isLoading:false,isError:false,refetch:vi.fn()},
  data: {
    base: { frontier_id: "F036", expected_return: .0578, volatility: .0851, weights: [{ asset_id: "us_equity", weight: .6 }, { asset_id: "us_treasury", weight: .4 }], groups: { equity: .6, fixed_income: .4 } },
    personalized: { volatility: .0957, tracking_error: .0176, weights: [{ asset_id: "us_equity", weight: .52 }, { asset_id: "us_treasury", weight: .4 }, { asset_id: "theme:semiconductor", weight: .08 }], groups: { broad_equity: .52, fixed_income: .4, themes: .08 } },
    themes: [{ theme_id: "semiconductor", ticker: "SOXX", target_weight: .08 }], risk_guardrail_applied: true,
    risk_comparison: { base_volatility: .0857 as number | null, personalized_volatility: .0957 as number | null, max_increase_pp: 1, as_of: "2026-09-11", method: "5Y weekly Ledoit-Wolf" },
  },
}));
vi.mock("@tanstack/react-query", () => ({ useQuery: ({queryKey}:{queryKey:string[]}) => queryKey[0]==="forward-ledger" ? state.ledger : ({ data: state.data, isLoading: false, isError: false }) }));
const renderReview = () => render(<SetupStyleProvider><ReviewStep basePoint={{frontier_id:"F036"}} themeIds={["semiconductor"]} onBack={vi.fn()} onComplete={vi.fn()} pending={false} error={false} /></SetupStyleProvider>);
describe("final portfolio review", () => {
  afterEach(cleanup);
  beforeEach(() => { state.ledger={data:{orders:[]},isLoading:false,isError:false,refetch:vi.fn()}; state.data.risk_comparison.base_volatility = .0857; state.data.risk_comparison.personalized_volatility = .0957; });
  it("matches theme-prefixed holdings to the same asset in the chart and comparison table", () => {
    const rows = reviewRows(state.data);
    expect(rows.find(r => r.id === "semiconductor")).toMatchObject({ name: "반도체", base: 0, final: .08, change: .08, isTheme: true });
    expect(rows.reduce((sum, r) => sum + r.final, 0)).toBeCloseTo(1);
    renderReview();
    fireEvent.click(screen.getByText("자산별 변경 내역 보기"));
    const row = screen.getByRole("row", { name: /반도체/ });
    expect(within(row).getByText("8.00%")).toBeInTheDocument();
    expect(within(row).getByText("+8.00%p")).toBeInTheDocument();
  });
  it("compares volatility using the guardrail baseline instead of the stored frontier value", () => {
    renderReview();
    expect(screen.getByText("8.57%")).toBeInTheDocument();
    expect(screen.getByText("+1.00%p")).toBeInTheDocument();
    expect(screen.queryByText("+1.06%p")).not.toBeInTheDocument();
  });
  it("shows missing risk explicitly instead of substituting a different model baseline", () => {
    state.data.risk_comparison.base_volatility = null;
    state.data.risk_comparison.personalized_volatility = null;
    renderReview();
    expect(screen.getByText("같은 기준의 위험 지표를 산출할 데이터가 부족합니다.")).toBeInTheDocument();
    expect(screen.queryByText("8.51%")).not.toBeInTheDocument();
  });
  it("links donut focus to the matching asset row", () => {
    renderReview();
    const chart = screen.getByRole("group", { name: "최종 자산 구성 도넛 차트" });
    fireEvent.focus(within(chart).getByRole("button", { name: "반도체 8.00%" }));
    const list = screen.getByRole("list", { name: "최종 자산별 비중" });
    expect(within(list).getByRole("button", { name: /반도체/ })).toHaveAttribute("aria-pressed", "true");
  });

it("restores the allocation review without pre-confirmation historical controls",()=>{
  renderReview();
  expect(screen.getByRole('heading',{name:'나의 최종 포트폴리오'})).toBeVisible();
  expect(screen.queryByRole('heading',{name:'두 구성 비교'})).not.toBeInTheDocument();
  expect(screen.queryByLabelText('비교 기간')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('가정 투자금')).not.toBeInTheDocument();
});

it("shows pending orders while leaving the server to allow an idempotent confirmation",()=>{
  state.ledger.data.orders=[{status:'pending'},{status:'filled'},{status:'pending'}];
  const complete=vi.fn();
  render(<SetupStyleProvider><ReviewStep basePoint={{frontier_id:'F036'}} themeIds={['semiconductor']} onBack={vi.fn()} onComplete={complete} pending={false} error={false}/></SetupStyleProvider>);
  expect(screen.getByRole('region',{name:'구성 확정 조건'})).toHaveTextContent('대기 주문 2건');
  expect(screen.getByRole('link',{name:'대기 주문 보기'})).toHaveAttribute('href','/dashboard#dark-records');
  fireEvent.click(screen.getByRole('button',{name:'포트폴리오 확정 · 성과 확인'}));expect(complete).toHaveBeenCalledOnce();
});
it("shows the actual server rejection instead of blaming all failures on orders",()=>{
  render(<SetupStyleProvider><ReviewStep basePoint={{frontier_id:'F036'}} themeIds={['semiconductor']} onBack={vi.fn()} onComplete={vi.fn()} pending={false} error={true} errorMessage="다른 확정이 이루어졌습니다. 최신 판단에서 다시 설계해 주세요."/></SetupStyleProvider>);
  expect(screen.getByRole('alert')).toHaveTextContent('다른 확정이 이루어졌습니다');
});
it("does not label an order refresh failure as no pending orders",()=>{
  state.ledger.isError=true;renderReview();
  expect(screen.getByRole('region',{name:'구성 확정 조건'})).toHaveTextContent('주문 상태를 불러오지 못했습니다');
  fireEvent.click(screen.getByRole('button',{name:'주문 상태 다시 조회'}));expect(state.ledger.refetch).toHaveBeenCalledOnce();
  expect(screen.queryByText('대기 주문 없음')).not.toBeInTheDocument();
});

});
