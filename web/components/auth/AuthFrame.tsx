import type { ReactNode } from "react";
import { ArrowUpRight, Layers3, ShieldCheck, ChartNoAxesCombined } from "lucide-react";

/** Decorative brand panel: no synthetic financial performance is drawn. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return <div className="auth-page">
    <aside className="auth-story" aria-label="Robo Advisor 소개">
      <div className="auth-wordmark"><span>RA</span> Robo Advisor</div>
      <div className="auth-orbit" aria-hidden><i/><i/><i/><b/></div>
      <div className="auth-story-copy"><p className="ui-eyebrow">YOUR PERSPECTIVE. YOUR PORTFOLIO.</p><h2>투자의 기준을 세우고,<br/>선택의 결과를 살펴보세요.</h2><p>위험과 수익의 균형에서 시작해<br/>나만의 투자 관점을 차근차근 기록합니다.</p></div>
      <ul className="auth-features"><li><Layers3 size={18}/>내 관점을 담은 자산 구성</li><li><ChartNoAxesCombined size={18}/>시장 가격 기반 성과 비교</li><li><ShieldCheck size={18}/>처음의 판단부터 이어지는 기록</li></ul>
      <div className="auth-story-footer">PORTFOLIO RESEARCH WORKSPACE <ArrowUpRight size={16}/></div>
    </aside>
    <main className="auth-form-area"><div className="auth-card">{children}</div><p className="auth-footnote">Robo Advisor · 투자 연구를 위한 모의운용 서비스</p></main>
  </div>;
}
