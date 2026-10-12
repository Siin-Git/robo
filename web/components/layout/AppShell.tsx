import { useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { get } from "@/lib/api/client";
import type { ExperimentStatus } from "@/lib/api/experiment";
import type { ReactNode } from "react";
import { useCurrentUser, AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";
import { usePathname } from "next/navigation";
import { DEMO_MODE, LAB_MEETING_MODE } from "@/lib/api/comparison";
import {ReplayNotice,useLocalReplay} from "@/components/dashboard/ReplayNotice";

export function AppShell({
  children,
  headerTitle,
  headerRight,
  hideDesignNotice = false,
}: {
  children: ReactNode;
  headerTitle: string;
  headerRight?: ReactNode;
  hideDesignNotice?: boolean;
  setup?: boolean;
  softBackground?: boolean;
}) {
  const user = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();
  // Internal review requires admin authorization, not a participant portfolio.
  const adminPage = pathname === "/admin" || pathname.startsWith("/admin/");
  const replay = useLocalReplay(!adminPage);
  const enrollment = useQuery({queryKey:["experiment-status", user?.user_id],queryFn:()=>get<ExperimentStatus>("/api/v1/me/experiment"),enabled:DEMO_MODE&&!!user&&!adminPage});
  const needsSetup = enrollment.data?.status === "setup_required";
  // Strategy evidence is read-only and must be available before confirmation.
  useEffect(()=>{if(needsSetup && !adminPage && !pathname.startsWith("/setup/") && pathname!=="/account" && pathname!=="/strategies" && !(LAB_MEETING_MODE && pathname==="/ranking")) router.replace("/setup/portfolio");},[needsSetup,adminPage,pathname,router]);
  const designPage = ["/setup", "/portfolio", "/views"].some(p => pathname === p || pathname.startsWith(p + "/"));
  return (
    <div className="app-shell" data-workspace={adminPage ? "admin" : "user"}>
      <a href="#main-content" className="skip-link">본문으로 이동</a>
      <AppSidebar user={user} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader title={headerTitle} right={headerRight ?? <span className="header-account"><span className="header-avatar" aria-hidden>{(user?.display_name ?? user?.participant_id ?? "R").slice(0,1)}</span>{user?.display_name ?? user?.participant_id ?? "내 계정"}{user?.role === "admin" && <span className="ui-badge">관리자</span>}</span>} />
        <main id="main-content" tabIndex={-1} className="app-content mx-auto w-full max-w-[1440px] px-[16px] pt-[28px] md:px-[32px]">
          {!adminPage && <Suspense fallback={null}><ReplayNotice/></Suspense>}
          {DEMO_MODE && !replay.data?.enabled && designPage && !needsSetup && !hideDesignNotice && <p className="mb-[20px] rounded-[8px] bg-brand-soft px-[16px] py-[12px] text-[13px] leading-[20px] text-text-secondary">{enrollment.data?.market_comparison ? "포트폴리오를 재구성하고 저장하면 내 구성과 비교 결과가 함께 갱신됩니다. 주간 의견은 별도로 기록됩니다." : "확정된 실험 구성과 이후 자유 설계는 별도로 보관됩니다. 자유 설계·주간 의견의 수정은 과거 비교 성과를 덮어쓰지 않습니다."}</p>}
          {children}
        </main>
      </div>
    </div>
  );
}
