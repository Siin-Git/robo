import type { ReactNode } from "react";
import Link from "next/link";
import { useCurrentUser, AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";

export function AppShell({
  children,
  headerTitle,
  headerRight,
  setup = false,
  softBackground = false,
}: {
  children: ReactNode;
  headerTitle: string;
  headerRight?: ReactNode;
  setup?: boolean;
  softBackground?: boolean;
}) {
  const user = useCurrentUser();
  if (setup) return (
    <div className="min-h-screen bg-background">
      <AppHeader title="Robo Advisor" right={<nav aria-label="사용자 메뉴" className="flex items-center gap-[24px] text-[14px] text-text-secondary"><Link href="/portfolio">내 포트폴리오</Link><Link href="/account">계정</Link></nav>} />
      <main className="mx-auto w-full max-w-[1480px] px-[20px] pb-[32px] pt-[24px] md:px-[40px]">{children}</main>
    </div>
  );
  return (
    <div className="app-shell">
      <AppSidebar user={user} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader title={headerTitle} right={headerRight} />
        <main className="mx-auto w-full max-w-[1440px] px-[16px] pt-[28px] md:px-[32px]">
          {children}
        </main>
      </div>
    </div>
  );
}
