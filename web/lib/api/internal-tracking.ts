import { get, post } from "./client";

export interface TrackingDecision {
  decision_id: string; participant_id: string; version: number; effective_date: string;
  snapshot_status: string;
}
export interface TrackingReview {
  review_id: string; recorded_at: string; reviewer_id: string; asset_id: string;
  action: "KEEP_OBSERVING" | "REVISION_REVIEW"; reason: string;
  observation: { as_of: string; observations: number; price_return: number | null; data_kind: string };
}
export interface TrackingAsset {
  asset_id: string; confirmed_weight: number;
  initial_estimate: { expected_return: number | null; volatility: number | null; return_basis: string;
    independent_theme_forecast: boolean | null } | null;
  price_status: string; observations: number; observed_start: string | null; observed_end: string | null;
  cumulative_price_return: number | null; ledger_contribution: number | null;
  ledger_observation_start: string | null; ledger_observation_end: string | null;
  missing_price_dates: string[]; invalid_price_dates: string[];
  price_curve: { date: string; price: number | null; index100: number | null; source: string | null }[];
  horizons: { months: number; due_date: string; status: string; observations: number;
    observed_end: string | null; cumulative_price_return: number | null; due_basis: string }[];
  comparison: { status: string; difference: number | null; reason: string };
}
export interface TrackingReport {
  decision_id: string; participant_id: string; version: number; snapshot_status: string;
  as_of: string; window_start: string; window_end_exclusive: string; window_status: string;
  data_kind: string; assets: TrackingAsset[]; reviews: TrackingReview[];
  observation_source: "DESIGN_FORWARD_LEDGER"; historical_replay_excluded: boolean;
  snapshot: { risk_data_as_of: string | null; frontier: { version: string;
    points: { frontier_id: string; expected_return: number; volatility: number }[] } } | null;
  portfolio_expectations: Record<string, { value: number | null }>;
  provenance: Record<string, unknown>;
  actual_ledger: { status: string; observations: number; start: string | null; end: string | null;
    metrics: { cumulative_return: number | null; volatility: number | null } };
}

export const getTrackingDecisions = () => get<{ items: TrackingDecision[]; total: number }>("/api/v1/admin/tracking?limit=200");
export const getTrackingReport = (id: string) => get<TrackingReport>(`/api/v1/admin/tracking/${encodeURIComponent(id)}`);
export const saveTrackingReview = (id: string, body: {
  asset_id: string; action: TrackingReview["action"]; reason: string; request_key: string;
}) => post<TrackingReview>(`/api/v1/admin/tracking/${encodeURIComponent(id)}/reviews`, body);
