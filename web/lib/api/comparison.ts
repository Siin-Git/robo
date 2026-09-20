import type { WeightLeg } from "./types";

export const DEMO_MODE = process.env.NEXT_PUBLIC_CAPSTONE_DEMO === "1";
export interface ComparisonMetrics {
  nav: number; cumulative_return: number; core_return: number;
  excess_return: number; mdd: number; volatility: number | null; sharpe: number | null;
  tracking_error: number | null; information_ratio: number | null; sortino: number | null;
}
export interface ReadyComparison {
  reason?: string; frontier_id?: string;
  participant_id: string; display_name: string; themes: string[];
  benchmark: string; data_source: string; risk_free_rate: number;
  start: string; end: string; observations: number; metrics: ComparisonMetrics;
  status: "ready";
  confirmed_at?: string; forward_started_at?: string | null; scenario_id?: string;
  core_metrics: {cumulative_return:number; mdd:number; volatility:number|null; sharpe:number|null} | null;
  weekly: {week_start:string; start:string; end:string; portfolio_return:number; core_return:number; excess_return:number} | null;
  series: { date: string; personalized_nav: number; core_nav: number }[];
  allocation: WeightLeg[]; core_allocation: WeightLeg[];
}
export interface PendingComparison extends Omit<ReadyComparison, "status" | "metrics" | "start" | "end" | "core_metrics" | "weekly"> {
  status: "awaiting_performance"; metrics: null; start: null; end: null; core_metrics: null; weekly: null;
}
export type Comparison = ReadyComparison | PendingComparison;
export interface ComparisonRow {
  participant_id: string; display_name: string; themes: string[];
  rank: number; metrics: ComparisonMetrics;
}
export type RankingBasis = "return" | "excess" | "mdd" | "volatility" | "sharpe" | "te" | "ir";
export interface ComparisonRanking {
  data_source?: string;
  basis: RankingBasis; total: number; registered: number; reserved: number; capacity: number; cohort_id: string; pending: {participant_id:string; display_name:string; themes:string[]}[]; start: string; end: string; items: ComparisonRow[];
}

export interface ComparisonAnalytics {
  reports: Comparison[];
  rankings: Record<RankingBasis, ComparisonRow[]>;
  theme_selectors: {theme_id:string; count:number; cumulative_return:number; excess_return:number; mdd:number}[];
  outperformers: number; comparable: number; contribution_status: string;
}
