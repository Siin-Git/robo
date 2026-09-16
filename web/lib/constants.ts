export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Robo Advisor";

export const BENCHMARK_LABELS: Record<string, string> = {
  CORE_V0_3: "CORE V0.3",
  CORE_V0_3_: "CORE V0.3",
  neutral_60_40: "Neutral 60/40",
  equal_weight: "Equal Weight",
};

export const ASSET_LABELS: Record<string, string> = {
  us_equity: "미국주식",
  developed_ex_us: "선진국 ex-US",
  emerging_markets: "신흥국",
  korea_equity: "한국주식",
  us_treasury: "미국국채",
  korea_treasury: "한국국채",
  tips: "TIPS",
  gold: "금",
  global_reit: "글로벌 REIT",
  cash: "현금",
};

export const THEME_LABELS: Record<string, string> = {
  semiconductor: "반도체",
  ai: "AI",
  robotics: "로보틱스",
  defense: "방산",
  nuclear: "원자력",
  power_grid: "전력망",
  biotech: "바이오",
  cybersecurity: "사이버보안",
  cloud_data_center: "클라우드",
  optical_networking: "광네트워크",
};

export function assetLabel(id: string): string {
  return ASSET_LABELS[id] ?? THEME_LABELS[id] ?? id;
}

export function themeLabel(id: string): string {
  return THEME_LABELS[id] ?? id;
}

export function benchmarkLabel(id: string): string {
  return BENCHMARK_LABELS[id] ?? id;
}
