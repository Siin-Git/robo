const STEPS = ["기본 포트폴리오 설계", "투자 인사이트 반영", "비교 및 확정"];

export function SetupProgress({ step }: { step: "risk" | "themes" | "review" }) {
  const current = ["risk", "themes", "review"].indexOf(step);
  return <ol className="setup-progress" aria-label="포트폴리오 설계 단계">
    {STEPS.map((label, index) => <li key={label} aria-current={index === current ? "step" : undefined} data-complete={index < current}>
      <span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong>
    </li>)}
  </ol>;
}
