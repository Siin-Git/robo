import { ApiError, get } from "./client";

// These endpoints are planned. Keep the transport separate from presentation
// until the backend finalizes its response contract.
export interface LedgerStatus {
  has_records?: boolean | null;
  first_valuation_date?: string | null;
  latest_valuation_date?: string | null;
  observation_count?: number | null;
  last_updated_at?: string | null;
  data_freshness?: string | null;
  next_rebalance_date?: string | null;
}

export interface ForwardSystemStatus {
  profile: string;
  forward_test_inception_at: string | null;
  first_execution_at: string | null;
  latest_market_data_date: string | null;
  latest_valuation_date: string | null;
}

export interface LedgerAlert {
  id?: string;
  type: "INITIAL_EXECUTION" | "REBALANCE_EXECUTED" | "TRADE_EXECUTED" | "PRICE_STALE" | "RUN_FAILED" | string;
  date: string;
  title: string;
  severity: string;
  detail: string;
}

async function optionalEndpoint<T>(path: string): Promise<T | null> {
  try {
    return await get<T>(path);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export const getLedgerStatus = () => optionalEndpoint<LedgerStatus>("/api/v1/me/ledger/status");
export const getLedgerAlerts = () => optionalEndpoint<{ items: LedgerAlert[] }>("/api/v1/me/alerts");
export const getForwardSystemStatus = () => get<ForwardSystemStatus>("/api/v1/system/status");
