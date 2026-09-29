import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ForwardOperations } from "../dashboard/ForwardOperations";

vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    data: queryKey[0] === "forward-ledger" ? {
      as_of: "2026-09-28",
      snapshots: [{ date: "2026-09-28", nav_status: "OK", holdings: [{ asset_id: "theme:ai", weight: .08 }] }],
      orders: [{ order_id: "O-1", asset_id: "theme:ai", side: "buy", target_weight: .1,
        submitted_at: "2026-09-28T10:00:00+09:00", effective_at: "2026-09-29", status: "pending", action_required: true }],
      trades: [{ trade_id: "T-1", order_id: "O-0", asset_id: "theme:ai", execution_at: "2026-09-27" }],
    } : queryKey[0] === "summary-portfolio" ? { personalized: { weights: [{ asset_id: "ai", weight: .1 }] } } :
      { latest_market_data_date: "2026-09-28", forward_test_inception_at: "2026-09-20" },
    isLoading: false, isError: false, refetch: vi.fn(),
  }),
}));

afterEach(cleanup);

describe("forward operations", () => {
  it("shows persisted holdings and orders without deriving a drift verdict or schedule", () => {
    render(<ForwardOperations latestValuationDate={null} observations={null} />);
    const row = screen.getByRole("row", { name: /10.00% 8.00%/ });
    expect(within(row).getByText("BUY")).toBeInTheDocument();
    expect(within(row).getByText("판정 대기")).toBeInTheDocument();
    expect(screen.getByText("일정 API 대기 중")).toBeInTheDocument();
    expect(screen.getByText(/BUY 주문/)).toBeInTheDocument();
    expect(screen.getByText(/체결/)).toBeInTheDocument();
  });
});
