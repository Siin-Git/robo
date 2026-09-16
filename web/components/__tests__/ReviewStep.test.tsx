import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewStep } from "@/app/(app)/setup/portfolio/ReviewStep";
import { SetupStyleProvider } from "@/app/(app)/setup/SetupStyleProvider";
import { reviewRows } from "@/app/(app)/setup/portfolio/review-data";

const state = vi.hoisted(() => ({
  data: {
    base: { frontier_id: "F036", expected_return: .0578, volatility: .0851, weights: [{ asset_id: "us_equity", weight: .6 }, { asset_id: "us_treasury", weight: .4 }], groups: { equity: .6, fixed_income: .4 } },
    personalized: { volatility: .0957, tracking_error: .0176, weights: [{ asset_id: "us_equity", weight: .52 }, { asset_id: "us_treasury", weight: .4 }, { asset_id: "theme:semiconductor", weight: .08 }], groups: { broad_equity: .52, fixed_income: .4, themes: .08 } },
    themes: [{ theme_id: "semiconductor", ticker: "SOXX", target_weight: .08 }], risk_guardrail_applied: true,
    risk_comparison: { base_volatility: .0857 as number | null, personalized_volatility: .0957 as number | null, max_increase_pp: 1, as_of: "2026-09-11", method: "5Y weekly Ledoit-Wolf" },
  },
}));
vi.mock("@tanstack/react-query", () => ({ useQuery: () => ({ data: state.data, isLoading: false, isError: false }) }));
const renderReview = () => render(<SetupStyleProvider><ReviewStep basePoint={{frontier_id:"F036"}} themeIds={["semiconductor"]} onBack={vi.fn()} onComplete={vi.fn()} pending={false} error={false} /></SetupStyleProvider>);
describe("final portfolio review", () => {
  afterEach(cleanup);
  beforeEach(() => { state.data.risk_comparison.base_volatility = .0857; state.data.risk_comparison.personalized_volatility = .0957; });
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
});
