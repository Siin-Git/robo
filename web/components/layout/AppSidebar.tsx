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
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { post } from "@/lib/api/client";
import type { AuthUser } from "@/lib/api/types";

const ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/views", label: "Weekly View", icon: Vote },
  { href: "/performance", label: "Performance", icon: BarChart3 },
  { href: "/ranking", label: "Ranking", icon: Trophy },
];

export function AppSidebar({ user }: { user: AuthUser | null }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function logout() {
    try {
      await post("/api/v1/auth/logout");
    } finally {
      window.location.assign("/login");
    }
  }

  const nav = (
    <nav className="flex flex-col gap-[4px] px-[12px]" aria-label="Primary">
      {ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`flex h-[40px] items-center gap-[12px] rounded-[6px] px-[12px] text-[14px] font-medium leading-[20px] ${
              active ? "bg-brand-soft text-brand" : "text-text-primary hover:bg-surface-subtle"
            }`}
          >
            <Icon size={18} aria-hidden />
            {item.label}
          </Link>
        );
      })}
      {user?.role === "admin" && (
        <Link
          href="/admin"
          aria-current={pathname.startsWith("/admin") ? "page" : undefined}
          className={`flex h-[40px] items-center gap-[12px] rounded-[6px] px-[12px] text-[14px] font-medium leading-[20px] ${
            pathname.startsWith("/admin")
              ? "bg-brand-soft text-brand"
              : "text-text-primary hover:bg-surface-subtle"
          }`}
        >
          <Settings size={18} aria-hidden />
          Admin
        </Link>
      )}
    </nav>
  );

  const badge = process.env.NEXT_PUBLIC_APP_PROFILE === "local"
    ? "LOCAL"
    : process.env.NEXT_PUBLIC_APP_PROFILE === "replay"
      ? "LOCAL REPLAY"
      : null;

  return (
    <>
      <button
        className="btn-secondary mb-[12px] md:hidden"
        onClick={() => setMobileOpen((v) => !v)}
        aria-expanded={mobileOpen}
        aria-label="Toggle navigation"
      >
        Menu
      </button>
      <aside className="hidden w-[224px] shrink-0 border-r border-border bg-white md:block">
        <div className="flex h-full flex-col py-[16px]">
          <div className="px-[12px] pb-[12px] text-[14px] font-semibold">Robo Advisor</div>
          {nav}
          <div className="mt-auto flex flex-col gap-[4px] px-[12px] pt-[16px]">
            {badge ? (
              <span className="mx-[12px] inline-block self-start rounded-[999px] bg-warning-soft px-[8px] py-[2px] text-[12px] font-semibold leading-[17px] text-warning">
                {badge}
              </span>
            ) : null}
            <Link
              href="/account"
              className="flex h-[40px] items-center gap-[12px] rounded-[6px] px-[12px] text-[14px] font-medium leading-[20px] text-text-primary hover:bg-surface-subtle"
            >
              <User size={18} aria-hidden />
              Account
            </Link>
            <button
              onClick={logout}
              className="flex h-[40px] items-center gap-[12px] rounded-[6px] px-[12px] text-left text-[14px] font-medium leading-[20px] text-text-primary hover:bg-surface-subtle"
            >
              <LogOut size={18} aria-hidden />
              Logout
            </button>
          </div>
        </div>
      </aside>
      {mobileOpen && (
        <div className="mb-[16px] border border-border bg-white md:hidden" role="dialog" aria-label="Navigation">
          {nav}
        </div>
      )}
    </>
  );
}

export function useCurrentUser() {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  return user;
}
