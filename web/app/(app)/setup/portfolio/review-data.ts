import { ASSET_META } from "./asset-meta";
import { THEME_INFO } from "./theme-content";

export interface Weight { asset_id: string; weight: number }
export interface ReviewData {
  base: { frontier_id: string; expected_return: number | null; volatility: number | null; weights: Weight[]; groups: Record<string, number> };
  personalized: { expected_return?: number | null; volatility: number | null; tracking_error: number | null; weights: Weight[]; groups: Record<string, number> };
  themes: { theme_id: string; display_name?: string; ticker?: string | null; target_weight: number }[];
  risk_guardrail_applied: boolean;
  risk_comparison?: { base_volatility: number | null; personalized_volatility: number | null; max_increase_pp: number | null; as_of: string | null; method: string | null };
}
const normalize = (id: string) => id.startsWith("theme:") ? id.slice(6) : id;
export function reviewRows(p: {
  base: { weights: Weight[] }; personalized: { weights: Weight[] };
  themes: { theme_id: string; display_name?: string; ticker?: string | null }[];
}) {
  const before = new Map(p.base.weights.map(w => [normalize(w.asset_id), w.weight]));
  const after = new Map(p.personalized.weights.map(w => [normalize(w.asset_id), w.weight]));
  return Array.from(new Set([...before.keys(), ...after.keys()])).map(id => {
    const theme = p.themes.find(t => t.theme_id === id);
    const base = before.get(id) ?? 0;
    const final = after.get(id) ?? 0;
    return { id, name: theme ? THEME_INFO[id]?.name ?? theme.display_name ?? id : ASSET_META[id]?.name ?? id,
      description: theme ? (theme.ticker ? `${theme.ticker} · 내가 추가한 테마` : "내가 추가한 테마") : ASSET_META[id]?.desc ?? "",
      base, final, change: final - base, isTheme: !!theme };
  }).filter(r => r.base > 0 || r.final > 0).sort((a, b) => b.final - a.final);
}
