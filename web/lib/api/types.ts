/** API contract types (subset of outputs/api/openapi_v1.json, kept in sync). */

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
  request_id: string;
}

export interface Participant {
  participant_id: string;
  display_name: string;
  status: string;
  join_date: string;
  leave_date: string | null;
}

export interface Theme {
  theme_id: string;
  display_name: string;
  theme_type: string;
  ticker: string | null;
  active: boolean;
  universe_version: string;
  inactive_reason: string | null;
}

export interface View {
  view_id: string;
  participant_id: string;
  theme_id: string;
  status: string;
  submitted_at: string;
  cycle_date: string;
  effective_at: string;
  execution_status: string;
  reason: string | null;
  theme_universe_version: string;
}

export interface WeightLeg {
  asset_id: string;
  weight: number;
  asset_type: string;
  ticker: string | null;
}

export interface Portfolio {
  participant_id?: string | null;
  as_of?: string | null;
  benchmark_version: string;
  expected_volatility: number | null;
  tracking_error: number | null;
  weights: WeightLeg[];
}

export interface Performance {
  status: string;
  metrics: Record<string, number | null>;
}

export interface NavPoint {
  date: string;
  personalized_nav: number | null;
  core_nav: number | null;
}

export interface RankingItem {
  rank: number;
  participant_id: string;
  display_name: string;
  active_return: number | null;
  current_themes?: string[];
  cumulative?: number | null;
  mdd?: number | null;
  te?: number | null;
}

export interface AuthUser {
  user_id: string;
  email: string;
  role: string;
  status: string;
  participant_id: string | null;
  display_name?: string | null;
}
