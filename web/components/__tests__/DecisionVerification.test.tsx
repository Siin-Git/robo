import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PortfolioPage from "@/app/(app)/portfolio/page";
import type { DecisionVerification } from "@/components/portfolio/DecisionVerificationPanel";

vi.mock("next/navigation",()=>({useSearchParams:()=>new URLSearchParams()}));
vi.mock("@/components/layout/AppShell",()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
const state = vi.hoisted(()=>({record:null as DecisionVerification|null, error:false, loading:false, refetch:vi.fn()}));
const summary = {
  decision_id:"decision-1",
  base:{frontier_id:"F001",expected_return:.99,volatility:.99,weights:[{asset_id:"us_equity",weight:1}],groups:{equity:1}},
  personalized:{expected_return:.99,volatility:.99,tracking_error:null,weights:[{asset_id:"us_equity",weight:1}],groups:{equity:1}},
  themes:[],risk_comparison:null,
};
vi.mock("@tanstack/react-query",()=>({useQuery:({queryKey}:{queryKey:string[]})=>({
  data:queryKey[0]==="summary-portfolio"?summary:queryKey[0]==="decision-verification"?state.record:{points:[],assets:[]},
  isLoading:queryKey[0]==="decision-verification" && state.loading,
  isError:queryKey[0]==="decision-verification" && state.error,refetch:state.refetch,
})}));

beforeEach(()=>{
  state.error=false;state.loading=false;state.refetch.mockReset();
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  state.record={decision_id:"decision-1",version:1,confirmed_at:"2026-09-01T15:30:00+00:00",effective_date:"2026-09-03",reason:"주식 비중 제한",superseded_effective_date:null,
    original:{base:{expected_return:.05,volatility:.08,weights:{us_equity:.6,us_treasury:.4}},personalized:{expected_return:.05,volatility:.09,weights:{us_equity:.5,us_treasury:.4,"theme:ai":.1}},
      frontier:{version:"frozen",points:[{frontier_id:"F001",expected_return:.05,volatility:.08}]},return_basis:"themes inherit the funding equity average",risk_basis:"5Y weekly Ledoit-Wolf",price_data_as_of:"2026-08-31"},
    actual:{status:"UNAVAILABLE",reason:"동일 날짜의 정상 NAV가 필요합니다.",start:null,end:null,observations:0,excluded_rows:0,personalized_return:null,core_return:null,difference_pp:null,personalized_nav:null,core_nav:null},
    review:{status:"IN_PROGRESS",horizon_end:"2027-09-03",basis:"연간 기대수익률과 단기 실현수익률의 차이로 판단의 적중 여부를 판정하지 않습니다.",choice:null},
  };
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it("opens three sections from each point, preserves historical coordinates, closes with Escape",()=>{
  render(<PortfolioPage/>);
  expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  const base=screen.getByRole("button",{name:"테마 적용 전 Base Portfolio"});
  fireEvent.keyDown(base,{key:"Enter"});
  const panel=screen.getByRole("complementary",{name:"투자 판단 검증"});
  expect(within(panel).getAllByRole("heading",{level:4})).toHaveLength(3);
  expect(within(panel).getByText("5.00%")).toBeInTheDocument();
  expect(within(panel).queryByText("99.00%")).not.toBeInTheDocument();
  expect(within(panel).getByText("2026. 9. 2.")).toBeInTheDocument();
  expect(within(panel).getByText(/성과 비교 미확보/)).toBeInTheDocument();
  expect(within(panel).getByText("검증 진행 중")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"테마 적용 후 Personalized Portfolio"}));
  expect(within(panel).getByText("인공지능")).toBeInTheDocument();
  expect(within(panel).getByText("10.00%")).toBeInTheDocument();
  fireEvent.keyDown(panel,{key:"Escape"});
  expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"테마 적용 후 Personalized Portfolio"})).toHaveFocus();
});

it("shows only the paired period NAV returns and an explicit CORE benchmark",()=>{
  state.record!.actual={status:"AVAILABLE",reason:null,start:"2026-09-03",end:"2026-09-05",observations:3,excluded_rows:1,
    personalized_return:.02,core_return:.01,difference_pp:.01,personalized_nav:{start:1000000,end:1020000},core_nav:{start:1000000,end:1010000}};
  render(<PortfolioPage/>);
  fireEvent.click(screen.getByRole("button",{name:"Base · 판단 보기"}));
  const panel=screen.getByRole("complementary");
  expect(within(panel).getByText("2.00%")).toBeInTheDocument();
  expect(within(panel).getByText("+1.00%p")).toBeInTheDocument();
  expect(within(panel).getByText(/별도 CORE 계좌/)).toBeInTheDocument();
  expect(within(panel).getByText(/1,020,000원/)).toBeInTheDocument();
  expect(within(panel).getByText("검증 진행 중")).toBeInTheDocument();
});

it("does not borrow a current curve or forecast when the historical values are missing",()=>{
  state.record!.original.frontier.points=[];
  state.record!.original.personalized.expected_return=null;
  render(<PortfolioPage/>);
  expect(screen.queryByRole("button",{name:"테마 적용 후 Personalized Portfolio"})).not.toBeInTheDocument();
  expect(screen.getByText(/당시 Frontier 곡선 미확보/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Base · 판단 보기"}));
  expect(screen.getByRole("complementary")).toBeInTheDocument();
});

it("retries failed evidence reads without presenting current estimates as the decision",()=>{
  state.error=true;state.record=null;
  render(<PortfolioPage/>);
  expect(screen.getByText("판단 기록을 불러오지 못했습니다.")).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"테마 적용 전 Base Portfolio"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Retry"}));
  expect(state.refetch).toHaveBeenCalled();
});

it("connects the same decision to existing review history and displays stored risk evidence",()=>{
  state.record!.original.risk_basis="5Y weekly Ledoit-Wolf annualized covariance";
  state.record!.original.personalized.weights={};
  render(<PortfolioPage/>);
  fireEvent.click(screen.getByRole("button",{name:"Personalized · 판단 보기"}));
  const panel=screen.getByRole("complementary");
  expect(within(panel).getByText(/Ledoit–Wolf 공분산을 연율화/)).toBeInTheDocument();
  expect(within(panel).getByText("당시 자산 비중 미확보")).toBeInTheDocument();
  expect(within(panel).getByRole("link",{name:"이 판단의 검토 기록 보기"})).toHaveAttribute("href","/review?decision_id=decision-1");
  fireEvent.click(screen.getByRole("button",{name:"Base · 판단 보기"}));
  expect(within(panel).queryByText(/테마의 독립 전망/)).not.toBeInTheDocument();
  expect(within(panel).getByText(/Base는 확정 당시 선택한 기본 구성의 저장값/)).toBeInTheDocument();
});


it("keeps prior evidence visible but explicitly reports an automatic refresh failure",()=>{
  state.error=true;
  state.record!.valuation_job={status:"failed",scheduled_for:"2026-09-05",completed_at:null};
  render(<PortfolioPage/>);
  expect(screen.getByRole("alert")).toHaveTextContent("이전 조회 결과");
  fireEvent.click(screen.getByRole("button",{name:"Base · 판단 보기"}));
  const panel=screen.getByRole("complementary");
  expect(within(panel).getByText(/전체 계좌 평가 작업.*실패/)).toBeInTheDocument();
  expect(within(panel).getByText(/성과 비교 미확보/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"다시 조회"}));
  expect(state.refetch).toHaveBeenCalled();
});


it("never labels a successful process as completed valuation without server evidence",()=>{
  state.record!.valuation_job={status:"success",scheduled_for:"2026-09-05",completed_at:null};
  const view=render(<PortfolioPage/>);
  fireEvent.click(screen.getByRole("button",{name:"Base · 판단 보기"}));
  expect(screen.getByText(/작업 성공 · 평가 완료 여부 미확인/)).toBeInTheDocument();
  state.record!.valuation_job={...state.record!.valuation_job,state:"START_WAIT",message:"공동 운용 시작 대기",valuation_completed:false};
  view.rerender(<PortfolioPage/>);
  expect(screen.getByText(/공동 운용 시작 대기/)).toBeInTheDocument();
  expect(screen.queryByText(/작업 성공 · 평가 완료 여부 미확인/)).not.toBeInTheDocument();
});
