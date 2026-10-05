import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";

const state = vi.hoisted(() => ({ pathname: "/admin/tracking", replace: vi.fn(), query: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname, useRouter: () => ({ replace: state.replace }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (options: unknown) => { state.query(options); return { data: { status: "setup_required" } }; } }));
vi.mock("@/lib/api/comparison", () => ({ DEMO_MODE: true, LAB_MEETING_MODE: false }));
vi.mock("@/components/layout/AppSidebar", () => ({ useCurrentUser: () => ({ user_id: "admin1", role: "admin" }), AppSidebar: () => null }));
vi.mock("@/components/layout/AppHeader", () => ({ AppHeader: () => null }));

beforeEach(() => { vi.clearAllMocks(); state.pathname = "/admin/tracking"; });
afterEach(cleanup);
describe("internal administration enrollment boundary", () => {
  it("keeps internal review accessible without participant setup or enrollment queries", () => {
    render(<AppShell headerTitle="Internal">Internal review</AppShell>);
    expect(screen.getByText("Internal review")).toBeInTheDocument();
    expect(state.query).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    expect(screen.queryByLabelText("로컬 과거 재생 시연")).not.toBeInTheDocument();
    expect(state.query).toHaveBeenCalledWith(expect.objectContaining({queryKey:["local-replay-context"],enabled:false}));
    expect(state.replace).not.toHaveBeenCalled();
  });
  it("keeps the admin entry accessible without participant setup", () => {
    state.pathname = "/admin";
    render(<AppShell headerTitle="Admin">Admin entry</AppShell>);
    expect(state.replace).not.toHaveBeenCalled();
  });
  it("retains participant setup redirects on customer pages", () => {
    state.pathname = "/dashboard";
    render(<AppShell headerTitle="Dashboard">Dashboard</AppShell>);
    expect(state.query).toHaveBeenCalledWith(expect.objectContaining({ enabled: true }));
    expect(state.replace).toHaveBeenCalledWith("/setup/portfolio");
  });
});
