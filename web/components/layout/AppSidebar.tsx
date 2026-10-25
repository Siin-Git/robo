"use client";

import {
  BarChart3,
  Briefcase,
  LayoutDashboard,
  LogOut,
  Settings,
  Trophy,
  User,
  Vote,
  History,
  Library,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ApiError, get, post } from "@/lib/api/client";
import type { AuthUser } from "@/lib/api/types";
import { DEMO_MODE } from "@/lib/api/comparison";
import { useComparisonMode } from "@/lib/api/use-comparison-mode";

const GROUPS = [
  { label: "내 투자 현황", items: [
    { href: "/dashboard", label: "대시보드", icon: LayoutDashboard },
  ] },
  { label: "포트폴리오", items: [
    { href: "/setup/portfolio", label: "포트폴리오 설계", icon: Settings },
    { href: "/portfolio", label: "내 포트폴리오", icon: Briefcase },
    { href: "/views", label: "주간 투자 의견", icon: Vote },
    { href: "/performance", label: "포트폴리오 성과", icon: BarChart3 },
  ] },
  { label: "성과 분석", items: [
    { href: "/review", label: "판단 기록", icon: History },
    { href: "/verification", label: "검증 현황", icon: ShieldCheck },
    { href: "/strategies", label: "투자 전략 자료실", icon: Library },
    { href: "/ranking", label: "참여자 비교·랭킹", icon: Trophy },
  ] },
];

export function AppSidebar({ user }: { user: AuthUser | null }) {
  const pathname = usePathname();
  const comparisonMode = useComparisonMode();
  const marketComparison = DEMO_MODE && comparisonMode.data?.market_comparison;
  const [mobileOpen, setMobileOpen] = useState(false);

  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);

  async function logout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError(false);
    try {
      await post("/api/v1/auth/logout");
      window.location.assign("/login");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) window.location.assign("/login");
      else { setLogoutError(true); setLoggingOut(false); }
    }
  }

  const nav = (
    <nav className="flex flex-col gap-[4px] px-[12px]" aria-label="주요 메뉴">
      {GROUPS.map(group => <section key={group.label} className="mb-[16px]" aria-label={group.label}>
        <h2 className="px-[12px] pb-[8px] pt-[16px] text-[11px] font-semibold tracking-wide text-text-secondary">{group.label}</h2>
        <div className="flex flex-col gap-[4px]">{group.items.filter(item => !marketComparison || item.href !== "/performance").map((item) => {
        const active = (marketComparison && item.href === "/dashboard" && pathname === "/performance") || pathname === item.href || pathname.startsWith(item.href + "/")
          || (item.href === "/setup/portfolio" && pathname.startsWith("/setup/"))
          || (item.href === "/ranking" && pathname.startsWith("/participants/"));
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            onClick={() => setMobileOpen(false)}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`flex h-[40px] items-center gap-[12px] rounded-[6px] px-[12px] text-[14px] font-medium leading-[20px] ${
              active ? "bg-brand-soft text-brand" : "text-text-primary hover:bg-surface-subtle"
            }`}
          >
            <Icon size={18} aria-hidden />
            {marketComparison && item.href === "/dashboard" ? "내 투자 성과" : item.label}
          </Link>
        );
      })}</div></section>)}
      {user?.role === "admin" && <section className="sidebar-admin" aria-label="관리자 전용">
        <h2>관리자 전용</h2>
        <Link href="/admin" aria-current={pathname === "/admin" ? "page" : undefined} className="sidebar-link"><ShieldCheck size={18} aria-hidden/>운영 현황</Link>
        <Link href="/admin/tracking" aria-current={pathname.startsWith("/admin/tracking") ? "page" : undefined} className="sidebar-link"><History size={18} aria-hidden/>내부 판단 추적</Link>
      </section>}
    </nav>
  );

  const badge = DEMO_MODE ? null : process.env.NEXT_PUBLIC_APP_PROFILE === "local"
    ? "LOCAL"
    : process.env.NEXT_PUBLIC_APP_PROFILE === "replay"
      ? "LOCAL REPLAY"
      : null;

  const accountActions = <div className="sidebar-account">
    {badge && <span className="ui-badge">{badge}</span>}
    <Link href="/account" className="sidebar-link"><User size={18} aria-hidden />계정 관리</Link>
    <button className="sidebar-link" onClick={logout} disabled={loggingOut}><LogOut size={18} aria-hidden />{loggingOut ? "로그아웃 중…" : "로그아웃"}</button>
    {logoutError && <p className="text-negative text-[12px]" role="alert">로그아웃에 실패했습니다. 다시 시도해 주세요.</p>}
  </div>;
  return <>
    <button className="mobile-menu btn-secondary" onClick={() => setMobileOpen(v => !v)} aria-expanded={mobileOpen} aria-controls="mobile-navigation">{mobileOpen ? "메뉴 닫기" : "메뉴 열기"}</button>
    <aside className="app-sidebar">
      <Link href="/dashboard" className="sidebar-brand"><b aria-hidden>RA</b><div>Robo Advisor<span>인사이트 기반 모의운용</span></div></Link>
      {nav}{accountActions}
    </aside>
    {mobileOpen && <div id="mobile-navigation" className="mobile-navigation" onKeyDown={e => { if (e.key === "Escape") setMobileOpen(false); }}>
      {nav}{accountActions}
    </div>}
  </>;
}

export function useCurrentUser() {
  const query = useQuery({ queryKey: ["current-user"], queryFn: () => get<AuthUser>("/api/v1/auth/me"), retry: false });
  return query.data ?? null;
}
