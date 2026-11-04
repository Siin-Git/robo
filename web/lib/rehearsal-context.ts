export type RehearsalContext = {period: string; amount: number};
export function readRehearsalContext(params: {get(name: string): string | null}): RehearsalContext {
  const period = params.get("period") ?? "all";
  const amount = Number(params.get("initial_amount"));
  return {period: period === "all" || /^\d{4}$/.test(period) ? period : "all",
    amount: [1_000_000, 10_000_000, 100_000_000].includes(amount) ? amount : 10_000_000};
}
export function rehearsalHref(decisionId: string, context: RehearsalContext, review = false) {
  const params = new URLSearchParams({decision_id: decisionId, period: context.period, initial_amount: String(context.amount)});
  if (review) params.set("source", "rehearsal");
  return `${review ? "/review" : "/portfolio/rehearsal"}?${params}`;
}
