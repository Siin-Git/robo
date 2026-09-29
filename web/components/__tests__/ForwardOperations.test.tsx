import { cleanup, render, screen, within, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForwardOperations } from "../dashboard/ForwardOperations";
import type { LedgerStatus } from "@/lib/api/ledger";

const state = vi.hoisted(() => ({
  data: null as LedgerStatus | null, isError: false, refetch: vi.fn(),
  alertsError: false,
}));
vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => queryKey[0] === "ledger-status" ? {
    data: state.data, isLoading: false, isError: state.isError, refetch: state.refetch,
  } : {
    data: { items: [{ alert_id: "E1", type: "ORDER_CREATED", date: "2026-09-28",
      title: "주문이 생성되었습니다", detail: { asset: "theme:ai", order_id: "O-1", nested: { ignored: true } } }] },
    isLoading: false, isError: state.alertsError, refetch: state.refetch,
  },
}));

beforeEach(() => {
  state.isError = false;
  state.alertsError = false;
  state.refetch.mockClear();
  state.data = {
    has_history: true, first_valuation_date: "2026-09-20", last_valuation_date: "2026-09-28",
    observation_count: 7, latest_price_date: "2026-09-28", data_freshness: "OK",
    next_rebalance_date: "2026-10-01",
    rebalance: { as_of: "2026-09-28", status: "READY", nav_status: "OK",
      target_effective_date: "2026-09-20", band: { type: "relative", threshold: .1 }, assets: [
        { asset_id: "theme:ai", target_weight: .1, current_weight: .08, drift_status: "OUTSIDE_BAND",
          action: "BUY", pending_orders: [{ order_id: "O-1", side: "BUY", effective_at: "2026-09-29" }] },
        { asset_id: "removed", target_weight: 0, current_weight: .05, drift_status: "OUTSIDE_BAND",
          action: "SELL", pending_orders: [] },
        { asset_id: "boundary", target_weight: .1, current_weight: .11, drift_status: "WITHIN_BAND",
          action: "HOLD", pending_orders: [] },
      ] },
  };
});
afterEach(cleanup);
const renderPanel = () => render(<ForwardOperations latestValuationDate={null} observations={null} />);

describe("forward operations", () => {
  it("renders backend schedule, drift, zero-target sell and pending orders", () => {
    renderPanel();
    const row = screen.getByRole("row", { name: /10.00% 8.00%/ });
    expect(within(row).getByText("BUY")).toBeInTheDocument();
    expect(within(row).getByText("밴드 이탈")).toBeInTheDocument();
    expect(within(row).getByText(/BUY ·/)).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /0.00% 5.00%/ })).getByText("SELL")).toBeInTheDocument();
    expect(screen.getByText("밴드 이내")).toBeInTheDocument();
    expect(screen.getByText("유지")).toBeInTheDocument();
    expect(screen.getByText("2026.10.01")).toBeInTheDocument();
    expect(screen.getByText("주문이 생성되었습니다")).toBeInTheDocument();
    expect(screen.getByText(/주문 O-1/)).toBeInTheDocument();
  });
  it("does not infer an action from weights when backend cannot judge", () => {
    state.data!.rebalance!.status = "INCOMPLETE_VALUATION";
    state.data!.rebalance!.assets = [{ asset_id: "theme:ai", target_weight: .1,
      current_weight: .08, drift_status: "UNAVAILABLE", action: null, pending_orders: [] }];
    renderPanel();
    expect(screen.queryByText("BUY")).not.toBeInTheDocument();
    expect(screen.getAllByText("판정 대기")).toHaveLength(2);
    expect(screen.getByText(/매매 판정을 보류/)).toBeInTheDocument();
  });
  it("keeps missing history empty", () => {
    state.data = { ...state.data!, has_history: false, last_valuation_date: null,
      first_valuation_date: null, next_rebalance_date: null, rebalance: null };
    renderPanel();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByText("운용 기록 대기")).toHaveLength(2);
  });
  it("offers retries for status and alerts failures", () => {
    state.isError = true;
    state.alertsError = true;
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    fireEvent.click(screen.getByRole("button", { name: "이벤트 다시 시도" }));
    expect(state.refetch).toHaveBeenCalledTimes(2);
  });
});
