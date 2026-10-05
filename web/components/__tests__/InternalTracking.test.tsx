import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import InternalTrackingPage from "@/app/(app)/admin/tracking/page";
import { getTrackingDecisions, getTrackingReport, saveTrackingReview } from "@/lib/api/internal-tracking";
import type { TrackingReport } from "@/lib/api/internal-tracking";

vi.mock("@/components/layout/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/lib/api/internal-tracking", () => ({ getTrackingDecisions: vi.fn(), getTrackingReport: vi.fn(), saveTrackingReview: vi.fn() }));
vi.mock("@/components/dashboard/PerformanceChart", () => ({ MY_LINE: { color: "blue", width: 2 }, PerformanceChart: (p: { connectNulls: boolean; data: unknown }) =>
  <div data-testid="price-curve" data-connect-nulls={String(p.connectNulls)}>{JSON.stringify(p.data)}</div> }));
const data: TrackingReport = {
  decision_id: "D1", participant_id: "P1", version: 1, snapshot_status: "RECORDED", as_of: "2026-10-04",
  window_start: "2026-10-01", window_end_exclusive: "2026-10-05", window_status: "ACTIVE", data_kind: "TEST_FIXTURE",
  observation_source: "DESIGN_FORWARD_LEDGER", historical_replay_excluded: true,
  snapshot: { risk_data_as_of: "2026-09-30", frontier: { version: "F1", points: [{ frontier_id: "F001", expected_return: .1, volatility: .2 }] } },
  portfolio_expectations: { expected_return: { value: .1 }, volatility: { value: .2 } }, provenance: {},
  actual_ledger: { status: "INSUFFICIENT_HISTORY", observations: 0, start: null, end: null, metrics: { cumulative_return: null, volatility: null } },
  reviews: [], assets: [{ asset_id: "theme:ai", confirmed_weight: .1,
    initial_estimate: { expected_return: .1, volatility: .2, return_basis: "existing", independent_theme_forecast: false },
    price_status: "OBSERVED", observations: 2, observed_start: "2026-10-01", observed_end: "2026-10-03", cumulative_price_return: .05,
    ledger_contribution: null, ledger_observation_start: null, ledger_observation_end: null,
    missing_price_dates: ["2026-10-02"], invalid_price_dates: [],
    price_curve: [{ date: "2026-10-01", price: 100, index100: 100, source: "SYNTHETIC_TEST" }, { date: "2026-10-02", price: null, index100: null, source: null }, { date: "2026-10-03", price: 105, index100: 105, source: "SYNTHETIC_TEST" }],
    horizons: [{ months: 3, due_date: "2027-01-01", status: "NOT_REACHED", observations: 2, observed_end: "2026-10-03", cumulative_price_return: null, due_basis: "FIRST_OBSERVED_PRICE" }],
    comparison: { status: "NOT_COMPARABLE", difference: null, reason: "FORECAST_HORIZON_AND_DEFINITION_NOT_AGREED" } }],
};
function open() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><InternalTrackingPage /></QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getTrackingDecisions).mockResolvedValue({ items: [{ decision_id: "D1", participant_id: "P1", version: 1, effective_date: "2026-10-01", snapshot_status: "RECORDED" }], total: 1 });
  vi.mocked(getTrackingReport).mockResolvedValue(structuredClone(data));
});
afterEach(cleanup);
describe("internal tracking", () => {
  it("denies non-admin access without requesting a report", async () => {
    vi.mocked(getTrackingDecisions).mockRejectedValue({ status: 403 });
    open();
    expect(await screen.findByText(/관리자 권한이 필요합니다/)).toBeInTheDocument();
    expect(getTrackingReport).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "내부 검토 기록 저장" })).not.toBeInTheDocument();
  });
  it("separates price gains from missing ledger results and keeps graph gaps", async () => {
    open();
    expect(await screen.findByText(/검증용 합성 데이터/)).toBeInTheDocument();
    expect(screen.getByText("평가 기록 부족")).toBeInTheDocument();
    expect(screen.getByTestId("price-curve")).toHaveAttribute("data-connect-nulls", "false");
    expect(screen.getByTestId("price-curve")).toHaveTextContent('"index100":null');
    expect(screen.getByText(/독립적인 테마 전망은 아닙니다/)).toBeInTheDocument();
    expect(screen.getByText(/동일 기간·산출 정의가 정해지지 않아 비교 보류/)).toBeInTheDocument();
    expect(screen.getByText(/과거 가격 재생은 이 추적과 3·6개월 관측에 포함하지 않습니다/)).toBeInTheDocument();
  });
  it("stores internal review direction and trimmed reason, preserving the retry key", async () => {
    vi.mocked(saveTrackingReview).mockRejectedValueOnce(new Error("network error")).mockResolvedValueOnce({ review_id: "R1", recorded_at: "2026-10-04", reviewer_id: "A1", asset_id: "theme:ai", action: "REVISION_REVIEW", reason: "검토 필요", observation: { as_of: "2026-10-04", observations: 2, price_return: .05, data_kind: "TEST_FIXTURE" } });
    open();
    const save = await screen.findByRole("button", { name: "내부 검토 기록 저장" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("검토 방향"), { target: { value: "REVISION_REVIEW" } });
    fireEvent.change(screen.getByLabelText("검토 근거"), { target: { value: "  검토 필요  " } });
    fireEvent.click(save);
    await screen.findByText("network error");
    fireEvent.click(save);
    await waitFor(() => expect(saveTrackingReview).toHaveBeenCalledTimes(2));
    expect(vi.mocked(saveTrackingReview).mock.calls[0]).toEqual(vi.mocked(saveTrackingReview).mock.calls[1]);
    expect(vi.mocked(saveTrackingReview).mock.calls[0][1]).toMatchObject({ asset_id: "theme:ai", action: "REVISION_REVIEW", reason: "검토 필요" });
  });
});
