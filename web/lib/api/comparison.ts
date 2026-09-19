import type { WeightLeg } from "./types";

export const DEMO_MODE = process.env.NEXT_PUBLIC_CAPSTONE_DEMO === "1";
export interface ComparisonMetrics {
  nav: number; cumulative_return: number; core_return: number;
  excess_return: number; mdd: number; volatility: number | null; sharpe: number | null;
}
export interface Comparison {
  participant_id: string; display_name: string; themes: string[];
  benchmark: string; data_source: string; risk_free_rate: number;
  start: string; end: string; observations: number; metrics: ComparisonMetrics;
  series: { date: string; personalized_nav: number; core_nav: number }[];
  allocation: WeightLeg[]; core_allocation: WeightLeg[];
}
export interface ComparisonRow {
  participant_id: string; display_name: string; themes: string[];
  rank: number; metrics: ComparisonMetrics;
}
export type RankingBasis = "return" | "excess" | "mdd" | "volatility" | "sharpe";
export interface ComparisonRanking {
  basis: RankingBasis; total: number; start: string; end: string; items: ComparisonRow[];
}
