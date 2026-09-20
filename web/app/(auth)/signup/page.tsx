"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ApiError, post } from "@/lib/api/client";
import { DEMO_MODE } from "@/lib/api/comparison";
import { APP_NAME } from "@/lib/constants";

export default function SignupPage() {
  const [ready, setReady] = useState(false);
  useEffect(()=>setReady(true),[]);
  const [invitation, setInvitation] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [registered, setRegistered] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || registered) return;
    if (password !== confirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setError(null);
    setBusy(true);
    let created = false;
    try {
      await post("/api/v1/auth/register", { email, password, display_name: name, invitation_code: invitation || undefined });
      created = true;
      setRegistered(true);
      // Auto-login
      await post("/api/v1/auth/login", { email, password });
      window.location.assign(DEMO_MODE ? "/setup/portfolio" : "/dashboard");
    } catch (err: unknown) {
      const code = err instanceof ApiError ? err.code : "";
      if (created) setError("계정은 생성되었지만 자동 로그인에 실패했습니다. 아래 로그인 링크로 다시 접속해 주세요.");
      else if (code === "EMAIL_ALREADY_EXISTS") setError("이미 가입된 이메일입니다. 로그인해 주세요.");
      else if (code === "PASSWORD_TOO_SHORT" || code === "PASSWORD_TOO_LONG") setError("비밀번호는 12자 이상, 128자 이하로 입력해 주세요.");
      else if (code === "INVALID_INVITATION") setError("초대 코드와 예약 이메일을 확인해 주세요.");
      else if (code === "COHORT_FULL") setError("비교군의 예약 자리가 모두 사용되었습니다.");
      else if (code === "REGISTRATION_DISABLED") setError("현재 회원가입이 비활성화되어 있습니다. 기존 계정으로 로그인해 주세요.");
      else setError("가입에 실패했습니다. 입력 내용과 서버 연결을 확인해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="ui-eyebrow">{APP_NAME}</p>
        <h1 className="page-title mt-[8px]">계정 만들기</h1>
        <p className="page-desc mt-[4px]">나만의 포트폴리오를 설정하고 성과를 추적해보세요.</p>
        <form aria-busy={busy} onSubmit={submit} className="mt-[20px] flex flex-col gap-[12px]">
          <label className="block">
            <span className="kpi-label">이메일</span>
            <input className="input mt-[4px]" type="email" autoComplete="email" required disabled={!ready || busy || registered} value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block">
            <span className="kpi-label">표시 이름</span>
            <input className="input mt-[4px]" type="text" autoComplete="name" required disabled={!ready || busy || registered} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block">
            <span className="kpi-label">비밀번호</span>
            <input className="input mt-[4px]" aria-label="비밀번호" type="password" autoComplete="new-password" minLength={12} maxLength={128} required disabled={!ready || busy || registered} value={password} onChange={(e) => setPassword(e.target.value)} />
            <span className="caption">12자 이상, 128자 이하</span>
          </label>
          <label className="block">
            <span className="kpi-label">비밀번호 확인</span>
            <input className="input mt-[4px]" type="password" autoComplete="new-password" minLength={12} maxLength={128} required disabled={!ready || busy || registered} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </label>
          {DEMO_MODE && <label className="block"><span className="kpi-label">시연 초대 코드</span><input className="input mt-[4px]" autoComplete="off" aria-label="시연 초대 코드" type="password" required disabled={!ready || busy || registered} value={invitation} onChange={e=>setInvitation(e.target.value)}/><span className="caption">지정된 이메일과 초대 코드로 예약된 비교군에 참여합니다.</span></label>}
          {error ? <p role="alert" className="text-[13px] leading-[20px] text-negative">{error}</p> : null}
          <button className="btn-primary btn-cta w-full" type="submit" disabled={!ready || busy || registered}>
            {busy ? "계정 생성 및 로그인 중…" : registered ? "계정 생성 완료" : "계정 만들기"}
          </button>
        </form>
        <p className="caption mt-[16px] text-center">
          이미 계정이 있으신가요? <Link href="/login" className="font-semibold text-brand">로그인</Link>
        </p>
      </div>
    </div>
  );
}
