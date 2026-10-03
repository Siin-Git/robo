export type RebalanceFrequency = "monthly" | "quarterly";
export const REBALANCE_LABELS: Record<RebalanceFrequency, string> = {
  monthly: "매월", quarterly: "매분기",
};
