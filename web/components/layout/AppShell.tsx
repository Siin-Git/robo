import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { get } from "@/lib/api/client";
import type { ExperimentStatus } from "@/lib/api/experiment";
import type { ReactNode } from "react";
import { useCurrentUser, AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";
import { usePathname } from "next/navigation";
import { DEMO_MODE } from "@/lib/api/comparison";

export function AppShell({
  children,
  headerTitle,
  headerRight,
}: {
  children: ReactNode;
  headerTitle: string;
  headerRight?: ReactNode;
  setup?: boolean;
  softBackground?: boolean;
}) {
  const user = useCurrentUser();
  const pathname = usePathname();
  const router = useRouter();
  const enrollment = useQuery({queryKey:["experiment-status", user?.user_id],queryFn:()=>get<ExperimentStatus>("/api/v1/me/experiment"),enabled:DEMO_MODE&&!!user});
  const needsSetup = enrollment.data?.status === "setup_required";
  useEffect(()=>{if(needsSetup && pathname!=="/setup/portfolio" && pathname!=="/account") router.replace("/setup/portfolio");},[needsSetup,pathname,router]);
  const designPage = ["/setup", "/portfolio", "/views", "/performance"].some(p => pathname === p || pathname.startsWith(p + "/"));
  return (
    <div className="app-shell">
      <AppSidebar user={user} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader title={headerTitle} right={headerRight} />
        <main className="mx-auto w-full max-w-[1440px] px-[16px] pt-[28px] md:px-[32px]">
          {DEMO_MODE && designPage && !needsSetup && <p className="mb-[20px] rounded-[8px] bg-brand-soft px-[16px] py-[12px] text-[13px] leading-[20px] text-text-secondary">{enrollment.data?.market_comparison ? "포트폴리오를 재구성하고 저장하면 내 구성과 비교 결과가 함께 갱신됩니다. 주간 의견은 별도로 기록됩니다." : "확정된 실험 구성과 이후 자유 설계는 별도로 보관됩니다. 자유 설계·주간 의견의 수정은 과거 비교 성과를 덮어쓰지 않습니다."}</p>}
          {children}
        </main>
      </div>
    </div>
  );
}
