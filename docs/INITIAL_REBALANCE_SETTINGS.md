# 초기 Frontier의 리밸런싱 주기

2026-10-04, 원격 develop `f3110f6`에서 분리한 `feat/initial-rebalance-settings`.
원래 루트·robo·기존 worktree 변경, 3063/3073 앱, 실제 SQLite 데이터와
LaunchAgent를 보존했다. 푸시·병합·배포·운영 DB 변경은 하지 않았다.

## 연결 범위와 확인한 누락

기존 `rebalance_schedule.py`에는 매월·매분기 판정이 있지만 onboarding API와
초안/판단에는 사용자별 주기가 없었다. 월간 배치와 다음 예정일도 전역 YAML만
읽었다. 프론트에서만 저장한 것처럼 표시하지 않도록 최소 저장·실행 연결을 추가했다.

- 첫 Frontier/risk 화면의 기존 위험 설정 아래 매월·매분기 선택. 신규 기본값은
  매월이며 초안/확정 판단에 값이 있으면 복원한다. 테마·뒤로 이동·결과·새로고침에서도
  기존 초안 API를 통해 유지한다.
- 뒤쪽 Frontier 결과에는 설정 단계를 추가하지 않았다. 확정 전 요약과 확정 후
  포트폴리오에서 선택/저장된 값만 읽기 전용으로 표시한다.
- 기존 `GET/PUT /api/v1/me/onboarding/draft`,
  `POST /api/v1/me/onboarding/complete`에 `rebalance_frequency`를 추가했다.
  `monthly`/`quarterly`만 허용하며 다른 값은 422다. 부분 수정/주기 생략 시 저장값을 유지한다.
- 초안은 `onboarding_drafts.rebalance_frequency`, 확정은 immutable
  `portfolio_decisions.provenance_json.rebalance_frequency`에 저장한다. 주기 변경도
  새 판단 버전이며 과거 판단은 보존한다. 동일 확정 재요청은 같은 판단을 반환한다.
- 기존 `GET /api/v1/me/portfolio/summary`는 최신 확정 주기를 반환한다.
  과거 판단에 저장 근거가 없으면 null이다. 초기 설정의 매월 기본값을 과거 저장 사실로 표시하지 않는다.
- 기존 monthly 엔진은 personal 계좌의 **기준일에 효력이 있는 판단**의 주기를
  읽고 기존 `is_rebalance_period`를 호출한다. 적용 대기 판단은 현재 주기를 바꾸지 않는다.
  core/shadow 및 레거시 계좌는 전역 설정을 유지한다. 다음 리밸런싱 날짜도 현재 운용
  판단의 주기를 사용한다. 금융 판정·주문 계획·가격·거래 보호·중복 방지는 기존 엔진이다.

`0008`은 nullable 초안 컬럼의 additive migration이다. 과거 판단을 채우지 않는다.
SQLite 추가 업그레이드 및 이후 Alembic 적용은 폐기용 DB에서 검증했다.
실제 로컬/원격 DB에는 적용하지 않았다. 프론트는 주기 계약이 없는 API에서 설정 진행을
막고, 저장/확정 응답이 선택값을 확인해 주어야 성공 처리한다.

기존 band는 relative 0.10, min_absolute 0이다.
`within_band`는 `abs(current-target) <= abs(target)*0.10 + 1e-12`로 판정한다.
목표 20%에서 18%·22%는 허용되고, 그 미만/초과가 조정 대상이라는 문구를 썼다.
임계값/계산식은 바꾸지 않았다. 기존 목표 0·경계 회귀도 통과했다.

주기는 정기 드리프트 교정에 적용한다. 초기 편입, 일간 평가, 새 구성 확정을
지연시키는 설정이 아니다. 주기 선택으로 예약 실행이나 알림 전송을 등록하지 않는다.
현재 실제 로컬 LaunchAgent는 기존 daily 하나이며 monthly 예약을 추가하지 않았다.
정기 교정에는 이 변경을 사용하는 기존 monthly 실행 주체가 필요하다.

## 실행한 검증

- Python 3.11 전체 `pytest tests -q`: **504 passed, 16 skipped**.
  폐기용 PostgreSQL URL이 필요한 API/DB/복원 검사는 이번 실행에서 건너뛰었다.
- 마지막 스키마 회귀 추가 후 `test_legacy_design_upgrade.py` 및
  `test_migration_covers_models.py` 재검사: **10 passed**. 최종 API/배치/기존 원장/스키마 관련 재검사는 **51 passed**이며,
  추가 예정일 경계 검증을 포함한 주기 API 재검사도 **8 passed**다.
- 사용자 격리·초안/확정 저장·반복 요청·재로그인·불변 버전·효력일 전후 주기,
  개인별 monthly/quarterly·전역 quarterly gate·분기말·dry-run 읽기 전용 검증 포함.
- 프론트 **62 passed (13 files)**, `tsc --noEmit` 및 Next.js 프로덕션 빌드 통과.
  별도 ESLint 명령은 package.json에 없다.
- Chrome E2E **2 passed**: desktop 1440×1000, mobile 390×844.
  매월 기본값 → 매분기 → 테마 → 뒤로 → 결과 요약 → 새로고침 → 확정 →
  새로고침 → 로그아웃/재로그인 → 저장값/API/초기 화면 확인. 가로 넘침/pageerror 없음.
  모바일 로그아웃은 기존 메뉴 열기 경로를 사용한다.
- 실제 Chrome 새 탭에서 격리 계정 로그인·첫 화면 라디오/안내·다음 단계 이동 확인.
  모바일 초기/결과 화면 PNG도 육안 확인했다.

초기 실패는 테스트 서버 경로/가상환경, 신규 계정의 기존 setup 리다이렉트,
모바일 숨김 메뉴를 테스트가 반영하지 못한 경우다. 테스트 환경·검증 경로를
수정한 최종 흐름은 통과했다. 제품 동작으로 우회하지 않았다.

## 로컬 확인

**http://127.0.0.1:3083/setup/portfolio**, 테스트 API 8083.
DB·계정 파일·로그·PNG는 `/private/tmp/robo-initial-rebalance-ccfu7i5p/`에 있다.
Chrome에 연 계정은 `capstone06@example.com`이며 비밀번호는 이 디렉터리의
`accounts.json`/`accounts.md`에서만 확인한다. 04/05/08/09/10/11/12/13번은 테스트에서 매분기 확정을
검증했다. 다른 미설정 테스트 계정도 남아 있다. 합성 월요일 시계/자료를 사용하는
폐기용 환경이며 3073 실제 날짜 로컬 운용과 별개다.

매월/매분기 → 다음: 투자 인사이트 반영 → 테마 → 위험 수준 다시 보기 →
다음: 변경 전·후 비교 → 주기 요약 → 포트폴리오 확정 · 성과 확인 순서다.
새로고침/재로그인 후 내 포트폴리오와 구성 변경 화면에서 저장 값을 확인한다.

재현에는 새 빈 디렉터리와 비어 있는 두 포트를 사용한다. 기존 데이터를 초기화하지 않는다.

```sh
cd .work/initial-rebalance-settings
../local-forward-operation/.venv/bin/python scripts/start_monday_demo.py \
  --directory /private/tmp/robo-initial-rebalance-fresh --port 3084 --api-port 8084
```

다른 터미널의 이 worktree `web`에서:

```sh
E2E_BASE_URL=http://127.0.0.1:3084 \
E2E_OPERATIONS_DATA_DIR=/private/tmp/robo-initial-rebalance-fresh \
npx --no-install playwright test --config playwright.frequency.config.ts
```

E2E에는 미설정 04/05번 계정이 필요하다. 같은 폐기용 디렉터리에서 재검사할 때
`E2E_ACCOUNT_OFFSET`으로 다른 미설정 계정을 지정할 수 있다.
로그인 자격값 보호를 위해 trace/video는 수집하지 않는다.
현재 테스트 서버 로그는 `api.log`/`web.log`, PID는 `servers.json`이다.
