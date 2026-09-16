"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { post } from "@/lib/api/client";
import { APP_NAME } from "@/lib/constants";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await post("/api/v1/auth/register", { email, password, display_name: name });
      // Auto-login
      await post("/api/v1/auth/login", { email, password });
      window.location.assign("/setup/portfolio");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("EMAIL_ALREADY_EXISTS")) setError("이미 가입된 이메일입니다.");
      else if (msg.includes("PASSWORD_TOO_SHORT")) setError("비밀번호는 12자 이상 입력해주세요.");
      else if (msg.includes("REGISTRATION_DISABLED")) setError("현재 회원가입이 비활성화되어 있습니다.");
      else setError("가입에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-[16px]">
      <div className="w-[400px] border border-border bg-white p-[32px]" style={{ borderRadius: 8 }}>
        <p className="text-[14px] font-semibold leading-[20px] text-text-secondary">{APP_NAME}</p>
        <h1 className="page-title mt-[8px]">계정 만들기</h1>
        <p className="page-desc mt-[4px]">나만의 포트폴리오를 설정하고 성과를 추적해보세요.</p>
        <form onSubmit={submit} className="mt-[20px] flex flex-col gap-[12px]">
          <label className="block">
            <span className="kpi-label">Email</span>
            <input className="input mt-[4px]" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block">
            <span className="kpi-label">Display Name</span>
            <input className="input mt-[4px]" type="text" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block">
            <span className="kpi-label">Password</span>
            <input className="input mt-[4px]" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <span className="caption">12자 이상, 128자 이하</span>
          </label>
          <label className="block">
            <span className="kpi-label">Confirm Password</span>
            <input className="input mt-[4px]" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </label>
          {error ? <p role="alert" className="text-[13px] leading-[20px] text-negative">{error}</p> : null}
          <button className="btn-primary btn-cta w-full" type="submit" disabled={busy}>
            {busy ? "생성 중…" : "계정 만들기"}
          </button>
        </form>
        <p className="caption mt-[16px] text-center">
          이미 계정이 있으신가요? <Link href="/login" className="font-semibold text-brand">로그인</Link>
        </p>
      </div>
    </div>
  );
}
