import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InvestmentRehearsal, type Rehearsal } from "@/components/portfolio/InvestmentRehearsal";
import { get } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({ get: vi.fn() }));
vi.mock("@/components/dashboard/PerformanceChart", () => ({
  CORE_LINE: { color: "gray", width: 1 }, MY_LINE: { color: "blue", width: 2 },
  PerformanceChart: () => <div aria-label="비교 그래프"/>,
}));
let client: QueryClient;
let report: Rehearsal;
beforeEach(() => {
  vi.clearAllMocks();
  client = new QueryClient({ defaultOptions: { queries: { retryDelay: 1, gcTime: 0 } } });
  report = { status: "AVAILABLE", reason: null, kind: "HISTORICAL_REHEARSAL", actual_account_history: false,
    decision_id: "saved-1", confirmed_at: "2026-10-01T15:30:00Z", selection_reason: "주식 비중을 제한",
    initial_amount: 10_000_000, currency: "KRW", source: null,
    periods: [{id: "all", label: "전체 자료 기간", start: "2020-01-02", end: "2022-12-30", observations: 700},
      {id: "2022", label: "2022년", start: "2022-01-03", end: "2022-12-30", observations: 250}],
    period: {id: "all", label: "전체 자료 기간", start: "2020-01-02", end: "2022-12-30", observations: 700},
    base: {weights: {us_equity: 1}, end_value: 11_000_000, cumulative_return: .1, max_drawdown: -.25},
    personalized: {weights: {us_equity: .9, "theme:ai": .1}, end_value: 12_000_000, cumulative_return: .2, max_drawdown: -.3}, series: [] };
  vi.mocked(get).mockImplementation(async () => report);
});
afterEach(() => { cleanup(); client.clear(); });
const show = () => render(<QueryClientProvider client={client}><InvestmentRehearsal decisionId="saved-1"/></QueryClientProvider>);

it("labels retrospective values, saved date in KST, exclusions and the original review link", async () => {
  show();
  expect(await screen.findByText("12,000,000원")).toBeVisible();
  expect(screen.getByText("-30.00%")).toBeVisible();
  expect(screen.getByText(/실제 계좌 성과가 아닙니다/)).toBeVisible();
  expect(screen.getByText(/2026. 10. 2./)).toBeVisible();
  expect(screen.getByRole("link", {name: "기존 판단 검토하기"})).toHaveAttribute("href", "/review?decision_id=saved-1");
  fireEvent.click(screen.getByText("비교한 비중과 계산 기준"));
  expect(screen.getByText(/수수료·세금은 제외/)).toBeVisible();
  expect(screen.getByText(/미국 국채·TIPS/)).toBeVisible();
});

it("never shows old period values while the requested period is loading", async () => {
  show(); await screen.findByText("12,000,000원");
  let finish!: (value: Rehearsal) => void;
  vi.mocked(get).mockImplementation(() => new Promise(resolve => { finish = resolve as typeof finish; }));
  fireEvent.change(screen.getByLabelText("비교 기간"), {target: {value: "2022"}});
  await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.stringContaining("period=2022")));
  expect(screen.queryByText("12,000,000원")).not.toBeInTheDocument();
  finish({...report, period: report.periods[1], personalized: {...report.personalized!, end_value: 9_000_000}});
  expect(await screen.findByText("9,000,000원")).toBeVisible();
  expect(screen.getByText(/2022.01.03 ~ 2022.12.30/)).toBeVisible();
});

it("sends the amount to the server and renders its response", async () => {
  show(); await screen.findByText("12,000,000원");
  vi.mocked(get).mockResolvedValue({...report, initial_amount: 1_000_000,
    personalized: {...report.personalized!, end_value: 1_200_000}});
  fireEvent.change(screen.getByLabelText("가정 투자금"), {target: {value: "1000000"}});
  expect(await screen.findByText("1,200,000원")).toBeVisible();
  expect(get).toHaveBeenLastCalledWith(expect.stringContaining("initial_amount=1000000"));
});

it("shows missing evidence without zero returns or charts", async () => {
  vi.mocked(get).mockResolvedValue({...report, status: "UNAVAILABLE", reason: "확정 당시 비중 미확보", base: null, personalized: null});
  show(); expect(await screen.findByText("확정 당시 비중 미확보")).toBeVisible();
  expect(screen.queryByText("0.00%")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("비교 그래프")).not.toBeInTheDocument();
});

it("exposes network failure and retries without keeping stale metrics", async () => {
  vi.mocked(get).mockRejectedValue(new Error("offline"));
  show(); expect(await screen.findByRole("alert")).toHaveTextContent("리허설을 불러오지 못했습니다");
  expect(screen.queryByText("12,000,000원")).not.toBeInTheDocument();
  vi.mocked(get).mockResolvedValue(report);
  fireEvent.click(screen.getByRole("button", {name: "다시 조회"}));
  expect(await screen.findByText("12,000,000원")).toBeVisible();
});
