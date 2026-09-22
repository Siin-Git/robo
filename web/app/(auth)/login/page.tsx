"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { safeNext } from "@/lib/auth-navigation";
import { ApiError, post, get } from "@/lib/api/client";
import { APP_NAME } from "@/lib/constants";
import { DEMO_MODE, LAB_MEETING_MODE } from "@/lib/api/comparison";

function LoginForm() {
  const params = useSearchParams();
  const [ready, setReady] = useState(false);
  useEffect(()=>setReady(true),[]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await post("/api/v1/auth/login", { email, password });
      const setup = DEMO_MODE ? await get<{status:string}>("/api/v1/me/experiment") : null;
      window.location.assign(setup?.status === "setup_required" ? "/setup/portfolio" : safeNext(params.get("next")));
    } catch (err: unknown) {
      setError(err instanceof ApiError && err.status === 401
        ? "이메일 또는 비밀번호가 올바르지 않습니다. 다시 확인해 주세요."
        : "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="ui-eyebrow">{APP_NAME} · 모의운용 프로토타입</p>
        <h1 className="page-title mt-[8px]">{LAB_MEETING_MODE ? "우리의 선택으로 비교하는 포트폴리오" : DEMO_MODE ? "같은 CORE, 서로 다른 투자 관점" : "내 관점으로 만드는 포트폴리오"}</h1>
        <p className="page-desc mt-[12px]">{LAB_MEETING_MODE ? "배정받은 아이디와 안내받은 비밀번호로 로그인해 주세요. 13명이 각자 섹터·테마를 선택하고, 저장한 포트폴리오의 순위를 함께 비교합니다." : DEMO_MODE ? "13명의 참여자가 선택한 Theme/View와 성과를 비교합니다. 초대받은 이메일로 가입하거나 기존 계정으로 로그인해 주세요." : "위험 수준에 맞는 기본 구성에 투자 인사이트를 더하고, 모의운용 성과를 비교해 보세요."}</p>
        <ol className="auth-journey"><li>{LAB_MEETING_MODE ? "01 로그인·기본 설계" : DEMO_MODE ? "01 가입·CORE 확인" : "01 기본 설계"}</li><li>{DEMO_MODE ? "02 Theme 선택·생성" : "02 인사이트 반영"}</li><li>{DEMO_MODE ? "03 성과 비교" : "03 성과 확인"}</li></ol>
        {process.env.NEXT_PUBLIC_APP_PROFILE === "local" ? (
          <p className="ui-note">
            {LAB_MEETING_MODE ? "순위는 같은 과거 가격 기간에 현재 선택을 적용한 결과입니다. 저장할 때마다 갱신되며 실제 운용 수익률은 아닙니다." : DEMO_MODE ? "모의 포트폴리오 비교 환경입니다. 실제 계좌의 운용 성과가 아닙니다." : "로컬 시연 환경입니다. 테스트 계정으로 로그인하거나 새 계정을 만들 수 있습니다."}
          </p>
        ) : null}
        <form aria-busy={busy} onSubmit={submit} className="mt-[20px] flex flex-col gap-[12px]">
          <label className="block">
            <span className="kpi-label">이메일</span>
            <input
              className="input mt-[4px]" type="email" autoComplete="email" required disabled={!ready || busy} aria-describedby={error ? "login-error" : undefined}
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="kpi-label">비밀번호</span>
            <input
              className="input mt-[4px]" type="password" autoComplete="current-password" required disabled={!ready || busy} aria-describedby={error ? "login-error" : undefined}
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error ? (
            <p id="login-error" role="alert" className="text-[13px] leading-[20px] text-negative">{error}</p>
          ) : null}
          <button className="btn-primary btn-cta w-full" type="submit" disabled={!ready || busy}>
            {busy ? "로그인 중…" : "로그인"}
          </button>
        </form>
        {LAB_MEETING_MODE ? <p className="caption mt-[16px] text-center">아이디는 capstone01@example.com부터 capstone13@example.com까지입니다.<br/>01~09번은 숫자 앞에 0을 입력해 주세요.</p> : <p className="caption mt-[16px] text-center">
          계정이 없으신가요? <Link href="/signup" className="font-semibold text-brand">회원가입</Link>
        </p>}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
