export const ASSET_META: Record<string, { name: string; desc: string; cat: string }> = {
  us_equity: { name: "미국주식", desc: "미국 전체 주식시장", cat: "주식" },
  developed_ex_us: { name: "선진국 ex-US", desc: "미국 제외 선진국 주식시장", cat: "주식" },
  emerging_markets: { name: "신흥국", desc: "중국·인도 등 신흥국 주식시장", cat: "주식" },
  korea_equity: { name: "한국주식", desc: "한국 주식시장", cat: "주식" },
  us_treasury: { name: "미국국채", desc: "미국 중기 국채", cat: "채권" },
  korea_treasury: { name: "한국국채", desc: "한국 국채", cat: "채권" },
  tips: { name: "TIPS", desc: "미국 물가연동국채", cat: "채권" },
  gold: { name: "금", desc: "금 가격을 추종하는 대체자산", cat: "대체" },
  global_reit: { name: "글로벌 REIT", desc: "글로벌 부동산/리츠", cat: "대체" },
  cash: { name: "현금", desc: "대기성 자금", cat: "현금" },
};
