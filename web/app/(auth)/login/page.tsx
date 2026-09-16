"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { post } from "@/lib/api/client";
import { APP_NAME } from "@/lib/constants";

function LoginForm() {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await post("/api/v1/auth/login", { email, password });
      window.location.assign(params.get("next") || "/dashboard");
    } catch (err: unknown) {
      setError("이메일 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-[16px]">
      <div className="w-[380px] border border-border bg-white p-[32px]" style={{ borderRadius: 8 }}>
        <p className="text-[14px] font-semibold leading-[20px] text-text-secondary">{APP_NAME}</p>
        <h1 className="page-title mt-[8px]">로그인</h1>
        {process.env.NEXT_PUBLIC_APP_PROFILE === "local" ? (
          <p className="caption mt-[8px] border border-warning-soft bg-warning-soft px-[12px] py-[8px] text-warning">
            Local Preview — 테스트 계정이 준비되어 있습니다. 터미널의 로그인 정보를 사용하세요.
          </p>
        ) : null}
        <form onSubmit={submit} className="mt-[20px] flex flex-col gap-[12px]">
          <label className="block">
            <span className="kpi-label">Email</span>
            <input
              className="input mt-[4px]" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="kpi-label">Password</span>
            <input
              className="input mt-[4px]" type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error ? (
            <p role="alert" className="text-[13px] leading-[20px] text-negative">{error}</p>
          ) : null}
          <button className="btn-primary btn-cta w-full" type="submit" disabled={busy}>
            {busy ? "로그인 중…" : "로그인"}
          </button>
        </form>
        <p className="caption mt-[16px] text-center">
          계정이 없으신가요? <a href="/signup" className="font-semibold text-brand">회원가입</a>
        </p>
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
