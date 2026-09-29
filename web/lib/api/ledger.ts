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

export interface LedgerStatus {
  has_history: boolean;
  first_valuation_date: string | null;
  last_valuation_date: string | null;
  observation_count: number;
  latest_price_date: string | null;
  data_freshness: "NO_DATA" | "STALE" | "OK";
  next_rebalance_date: string | null;
  rebalance: {
    as_of: string | null;
    status: "READY" | "NO_VALUATION" | "INCOMPLETE_VALUATION" | "NO_HOLDINGS" | "NO_TARGET";
    nav_status: string | null;
    target_effective_date: string | null;
    band: { type: string; threshold: number; min_absolute?: number } | null;
    assets: {
      asset_id: string;
      target_weight: number | null;
      current_weight: number | null;
      drift_status: "WITHIN_BAND" | "OUTSIDE_BAND" | "UNAVAILABLE";
      action: "BUY" | "SELL" | "HOLD" | null;
      pending_orders: { order_id: string; side: "BUY" | "SELL"; effective_at: string }[];
    }[];
  } | null;
}

export interface LedgerAlerts {
  items: {
    alert_id: string;
    type: string;
    date: string;
    occurred_at: string | null;
    title: string;
    detail: Record<string, unknown>;
    severity: string;
  }[];
  total: number;
}

export const getLedgerStatus = () => get<LedgerStatus>("/api/v1/me/ledger/status");
export const getLedgerAlerts = () => get<LedgerAlerts>("/api/v1/me/alerts?limit=8");
