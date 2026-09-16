export const CATEGORIES = ["전체", "기술", "산업·인프라", "에너지", "헬스케어"] as const;
export type Category = typeof CATEGORIES[number];
export interface ThemeInfo { name: string; description: string; categories: Category[]; question: string; detail: string }
export const THEME_INFO: Record<string, ThemeInfo> = {
  ai: { name: "인공지능", description: "데이터를 학습하고 새로운 서비스를 만드는 AI", categories: ["기술"], question: "AI 활용이 늘면 기업의 매출도 함께 늘어날까요?", detail: "AI 기술과 관련 서비스를 살펴보는 테마입니다. 기술의 발전 속도와 기업이 실제로 수익을 내는 속도는 다를 수 있습니다." },
  semiconductor: { name: "반도체", description: "AI와 디지털 기기의 연산을 담당하는 핵심 기술", categories: ["기술"], question: "늘어나는 연산 수요가 어떤 반도체의 수요로 이어질까요?", detail: "칩 설계·제조·장비 등 반도체 산업을 살펴보는 테마입니다. 설비 투자 주기와 수급 변화가 중요합니다." },
  cloud_data_center: { name: "클라우드·데이터센터", description: "데이터를 저장하고 서비스를 연결하는 기반", categories: ["기술", "산업·인프라"], question: "데이터 사용량의 증가가 서비스 기업의 이익으로 연결될까요?", detail: "클라우드 서비스와 데이터 인프라를 살펴보는 테마입니다. 테마 이름과 개별 ETF의 실제 편입 범위는 다를 수 있으므로 구성 종목도 확인해 보세요." },
  cybersecurity: { name: "사이버보안", description: "기업의 정보와 디지털 서비스를 지키는 기술", categories: ["기술"], question: "보안의 필요성이 커질 때 고객이 지출을 늘릴까요?", detail: "네트워크·클라우드·정보 보안을 살펴보는 테마입니다. 고객의 보안 예산, 경쟁과 서비스 가격을 함께 생각해 보세요." },
  robotics: { name: "로봇·자동화", description: "공장과 일상에서 사람의 작업을 돕는 기술", categories: ["기술", "산업·인프라"], question: "로봇 도입 비용보다 생산성 개선 효과가 클까요?", detail: "로봇과 자동화 기술을 살펴보는 테마입니다. 기술 시연에서 실제 사업장 도입까지 걸리는 시간과 비용이 중요합니다." },
  defense: { name: "방산·항공우주", description: "국방 체계와 항공·우주 산업의 변화", categories: ["산업·인프라"], question: "늘어난 예산이 실제 계약과 매출로 이어지는 데 얼마나 걸릴까요?", detail: "방위산업과 항공우주를 살펴보는 테마입니다. 정부 예산, 계약 일정, 수출 규제에 따라 사업 환경이 달라집니다." },
  power_grid: { name: "전력 인프라", description: "전기를 안정적으로 공급하는 전력망과 설비", categories: ["산업·인프라", "에너지"], question: "전력 수요가 늘면 어떤 설비가 먼저 필요해질까요?", detail: "송배전·전력 설비와 전력망 관련 산업을 살펴보는 테마입니다. 수요뿐 아니라 인허가와 설비 공급 여건도 확인할 필요가 있습니다." },
  nuclear: { name: "원자력·우라늄", description: "원자력 발전과 연료 공급을 둘러싼 산업", categories: ["에너지"], question: "원전 확대 계획은 언제 실제 발전과 연료 수요로 이어질까요?", detail: "원자력과 우라늄 관련 산업을 살펴보는 테마입니다. 에너지 정책, 건설 일정과 원자재 가격의 영향을 받습니다." },
  biotech: { name: "바이오테크", description: "새로운 치료제와 의약 기술을 개발하는 산업", categories: ["헬스케어"], question: "연구 성과가 승인과 상용화까지 이어질 수 있을까요?", detail: "신약과 바이오 기술을 살펴보는 테마입니다. 임상 결과, 승인 여부와 연구개발 비용에 따라 기업 가치가 크게 달라질 수 있습니다." },
  optical_networking: { name: "광통신", description: "많은 데이터를 빠르게 전송하는 연결 기술", categories: ["기술", "산업·인프라"], question: "데이터 이동량이 늘면 어떤 연결 기술이 필요해질까요?", detail: "광통신 관련 테마는 준비 중입니다. 현재는 포트폴리오에 추가할 수 없습니다." },
};
export const THOUGHTS: { title: string; question: string; category: Category; themes: string[] }[] = [
  { title: "AI가 더 널리 쓰인다면", question: "AI 서비스 외에 반도체, 전력, 보안 중 무엇이 더 필요해질까요?", category: "기술", themes: ["ai", "semiconductor", "cybersecurity"] },
  { title: "일하는 방식이 달라진다면", question: "로봇이 어떤 일을 맡을 수 있고, 도입 비용을 회수할 수 있을까요?", category: "산업·인프라", themes: ["robotics", "power_grid"] },
  { title: "전기를 더 많이 쓴다면", question: "발전량을 늘리는 일과 전력망을 확충하는 일 중 무엇이 먼저일까요?", category: "에너지", themes: ["power_grid", "nuclear"] },
];
