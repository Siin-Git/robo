import { render, screen, fireEvent, cleanup, waitFor, act } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { SetupStyleProvider } from "@/app/(app)/setup/SetupStyleProvider";
import SetupPortfolioPage from "@/app/(app)/setup/portfolio/page";

const state = vi.hoisted(() => ({
  market: false, ready: false, failed: false, pending: true, refetch: vi.fn(), save: vi.fn(), push: vi.fn(),
  frontier: { benchmark_frontier_id: "F001", points: [{ frontier_id: "F001", index: 0, expected_return: .05, volatility: .07, sharpe: .3, weights: [] }], assets: [] },
  draft: { status: "draft", frontier_id: "F001", theme_ids: ["ai"], reason: "저장한 선택 이유" },
  active: { items: [
    { theme_id: "ai", display_name: "Artificial Intelligence", ticker: "AIQ", active: true },
    { theme_id: "power_grid", display_name: "Power Grid", ticker: "GRID", active: true },
    { theme_id: "robotics", display_name: "Robotics", ticker: "BOTZ", active: true },
  ] },
  inactive: { items: [{ theme_id: "optical_networking", display_name: "Optical", ticker: null, active: false }] },
  impact: { base: { groups: { equity: .5 } }, personalized: { volatility: .08, tracking_error: .01, groups: { broad_equity: .4, themes: .1, fixed_income: .4, alternatives: .1 } }, themes: [{ theme_id: "ai", target_weight: .1 }], risk_guardrail_applied: false },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: state.push }), useSearchParams: () => new URLSearchParams("step=themes") }));
vi.mock("@/components/layout/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({ mutate: vi.fn(), mutateAsync: state.save, isPending: false, isError: false }),
  useQuery: ({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "experiment-setup-status") return {data:{status:"completed",market_comparison:state.market},isLoading:false,isError:false};
    if (queryKey[0] === "onboarding-preview") return { data: undefined, isLoading: true, isError: false };
    if (queryKey[0] === "frontier") return { data: state.frontier, isLoading: false, isError: false };
    if (queryKey[0] === "theme-selection-preview") return { data: state.impact, isLoading: false, isError: false };
    if (queryKey[0] === "onboarding-draft") return { data: state.draft, isLoading: false, isError: false };
    return { data: state.ready ? queryKey[0] === "themes-active" ? state.active : state.inactive : undefined, isLoading: state.pending, isError: state.failed, refetch: state.refetch };
  },
}));

describe("saved themes while catalog loads", () => {
  afterEach(cleanup);
  beforeEach(() => { state.market = false; state.ready = false; state.failed = false; state.pending = true; state.refetch.mockClear(); state.push.mockReset(); state.save.mockReset().mockResolvedValue({}); state.draft = { status: "draft", frontier_id: "F001", theme_ids: ["ai"], reason: "저장한 선택 이유" }; });
  it("waits for the catalog even when a selected theme was restored first, then preserves the selection", () => {
    const { rerender } = render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByRole("status")).toHaveTextContent("관심 분야 목록을 불러오는 중");
    expect(screen.queryByRole("button", { name: "최종 구성 확인하기" })).not.toBeInTheDocument();
    state.ready = true; state.pending = false;
    rerender(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByText("내가 반영할 인사이트")).toBeInTheDocument();
    expect(screen.getAllByText("인공지능")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "인공지능 선택 해제" })).toHaveAttribute("aria-pressed", "true");
  });
  it("handles a missing catalog without relying only on the loading flag", () => {
    state.pending = false;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
  it("shows retry on catalog failure instead of crashing on restored selections", () => {
    state.pending = false; state.failed = true;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByText("관심 분야 목록을 불러오지 못했습니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(state.refetch).toHaveBeenCalledTimes(2);
  });
  it("keeps one selection across categories and blocks a third or inactive theme", () => {
    state.ready = true; state.pending = false;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByRole("button", { name: "광통신 선택" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "에너지" }));
    fireEvent.click(screen.getByRole("button", { name: "전력 인프라 선택" }));
    fireEvent.click(screen.getByRole("button", { name: "산업·인프라" }));
    expect(screen.getByRole("button", { name: "전력 인프라 선택 해제" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "로봇·자동화 선택" })).toBeDisabled();
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "전력 인프라 선택 해제" }));
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
  });
  it("waits for a successful draft save before navigating to issues", async () => {
    state.ready = true; state.pending = false;
    let resolveSave!: (value: unknown) => void;
    state.save.mockImplementation(() => new Promise(resolve => { resolveSave = resolve; }));
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "최신 이슈 보러가기" }));
    expect(state.save).toHaveBeenCalledWith({ frontier_id: "F001", theme_ids: ["ai"], reason: "저장한 선택 이유", current_step: "themes" });
    expect(state.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "최신 이슈 보러가기" })).toBeDisabled();
    await act(async () => resolveSave({}));
    expect(state.push).toHaveBeenCalledWith("/setup/issues");
  });
  it("keeps the current page and selection if saving fails", async () => {
    state.ready = true; state.pending = false;
    state.save.mockRejectedValue(new Error("offline"));
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "최신 이슈 보러가기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("선택 내용을 저장하지 못했습니다");
    expect(state.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "인공지능 선택 해제" })).toHaveAttribute("aria-pressed", "true");
  });
  it("does not overwrite unsaved choices when the saved draft refetches", () => {
    state.ready = true; state.pending = false;
    const { rerender } = render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "전력 인프라 선택" }));
    state.draft = { ...state.draft, reason: "이전 저장 내용" };
    rerender(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });
  it("saves an empty theme list before continuing without themes", async () => {
    state.ready = true; state.pending = false;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "테마 없이 기본 구성으로 계속하기" }));
    await waitFor(() => expect(state.push).toHaveBeenCalledWith("/setup/portfolio?step=review"));
    expect(state.save).toHaveBeenCalledWith({ frontier_id: "F001", theme_ids: [], reason: "", current_step: "review" });
  });

  it("preserves the reason when a market participant removes all themes", async () => {
    state.market = true; state.ready = true; state.pending = false;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    expect(screen.getByLabelText("선택 이유")).toHaveValue("저장한 선택 이유");
    fireEvent.click(screen.getByRole("button", {name: "테마 없이 기본 구성으로 계속하기"}));
    await waitFor(() => expect(state.push).toHaveBeenCalledWith("/setup/portfolio?step=review"));
    expect(state.save).toHaveBeenCalledWith({frontier_id:"F001",theme_ids:[],reason:"저장한 선택 이유",current_step:"review"});
  });
  it("requires a reason before saving a reconstructed market portfolio", () => {
    state.market = true; state.ready = true; state.pending = false;
    render(<SetupStyleProvider><SetupPortfolioPage /></SetupStyleProvider>);
    fireEvent.change(screen.getByLabelText("선택 이유"), {target:{value:" "}});
    expect(screen.getByRole("button", {name:"다음: 변경 전·후 비교"})).toBeDisabled();
  });

});
