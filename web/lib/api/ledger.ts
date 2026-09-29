import { get } from "./client";

// The persisted, user-scoped forward ledger exposed by the current backend.
export interface ForwardLedger {
  as_of: string | null;
  snapshots: {
    date: string;
    nav_status: string;
    holdings: { asset_id: string; weight: number }[];
  }[];
  orders: {
    order_id: string;
    asset_id: string;
    side: "buy" | "sell";
    target_weight: number;
    submitted_at: string;
    effective_at: string;
    status: string;
    action_required: boolean;
  }[];
  trades: {
    trade_id: string;
    order_id: string;
    asset_id: string;
    execution_at: string;
  }[];
}

export interface ForwardSystemStatus {
  profile: string;
  forward_test_inception_at: string | null;
  first_execution_at: string | null;
  latest_market_data_date: string | null;
  latest_valuation_date: string | null;
}

export const getForwardLedger = () => get<ForwardLedger>("/api/v1/me/performance/ledger");
export const getForwardSystemStatus = () => get<ForwardSystemStatus>("/api/v1/system/status");
