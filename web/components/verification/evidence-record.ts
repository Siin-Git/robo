/** Audited snapshot, not a live CI badge. Update only against a completed run. */
export const evidenceRecord = {
  commit: 'a7f16fdf0a7e39f878eabea5d79d778c858081bc',
  completedAt: '2026-10-27T03:22:24Z',
  runUrl: 'https://github.com/MinchoLover/robo/actions/runs/40442696571',
  backend: 863,
  frontend: 182,
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


/** Completed tests at the pinned commit above. These are not live account results. */
export const verificationMethods = [
  {title:'최초 판단 보존', method:'현재 모형을 바꾸고 검토 이유를 저장한 뒤 원본을 대조', result:'최초 예상·비중 유지, 검토 기록만 추가', path:'tests/api/test_decision_verification.py'},
  {title:'계산과 장부', method:'정답이 있는 가격을 입력하고 보유자산·현금·평가액 대조', result:'수익률·최대 낙폭 계산 및 평가액 합계 일치', path:'tests/forward/test_performance_report.py'},
  {title:'동일 조건 비교', method:'양 계좌의 날짜를 다르게 넣고 누락·지연 자료를 섞음', result:'공통 정상 날짜만 비교, 부족한 자료는 미확보', path:'tests/api/test_decision_verification.py'},
  {title:'반복 실행·부분 실패', method:'같은 작업을 반복하고 일부 계좌만 실패시킴', result:'완료 기록 보존, 허용된 조건에서 누락 계좌만 재시도', path:'tests/forward/test_nav_watchdog.py'},
  {title:'접근 권한·화면 오류', method:'다른 계정 자료를 요청하고 화면 조회 실패를 재현', result:'권한 없는 접근 차단, 이전 조회와 갱신 실패 구분', path:'web/components/__tests__/VerificationStatus.test.tsx'},
  {title:'자산별 3·6개월 추적', method:'시험 날짜를 이동하고 정해진 가격으로 관측값 대조', result:'관측·점검 상태 일치. 실제 경과 검증과는 별도', path:'tests/api/test_internal_tracking.py'},
].map(item=>({...item,href:`${source}/${item.path}`}));
