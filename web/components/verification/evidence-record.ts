/** Audited snapshot, not a live CI badge. Update only against a completed run. */
export const evidenceRecord = {
  commit: '2dca67185f360fcad8b7ce33568eb91c09c575c1',
  completedAt: '2026-10-25T18:21:54Z',
  runUrl: 'https://github.com/MinchoLover/robo/actions/runs/40219993587',
  backend: 805,
  frontend: 146,
  build: '통과',
} as const;
const source = `https://github.com/MinchoLover/robo/blob/${evidenceRecord.commit}`;
export const evidenceLinks = [
  {title:'최초 판단과 소유권', description:'저장된 예상·비중 유지, 다른 계정 접근 차단, 누락값 소급 생성 방지',
    href:`${source}/tests/api/test_decision_verification.py`},
  {title:'성과·평가 조건', description:'공통 정상 NAV만 비교, 합성·재생 자료 제외, 작업 성공과 평가 완료 구분',
    href:`${source}/tests/api/test_decision_verification.py`},
  {title:'사용 흐름과 화면', description:'격리 API에서 구성 확정·검토 저장·모바일 화면 확인. 운영 성과 증거는 아닙니다.',
    href:`${source}/docs/PAGE_CONSISTENCY.md`},
] as const;
