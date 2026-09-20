# v1 · 캡스톤 통합 기록

## 기준과 변경 범위

- 원본 `main`: `d2b31f7`. 원격 origin과 Render fork의 main이 같은 커밋임을 확인했다.
- 검증된 캡스톤 구현: `cdd86ab`. `origin/feat/capstone-demo-mvp`에 먼저 푸시하여 보존했다.
- 통합 작업: `integration/v1-capstone`. 두 기존 브랜치를 직접 수정하지 않았다.
- main은 캡스톤 브랜치의 조상이다. 따라서 Git 텍스트 충돌은 없고, main merge 결과는 `Already up to date`였다. 코드의 기능 경로·데이터 경계를 검증하는 방식으로 통합했다.

## 보존한 기능과 주요 파일 검토

| 영역 | 검토·통합 결과 |
| --- | --- |
| auth/signup/login | 원래 `auth_service.py`의 등록·암호 해시·로그인·세션 처리는 main과 동일. 시연 가입만 예약된 이메일·초대 검증으로 제한. 기존 로그인과 원래 등록 정책은 유지 |
| onboarding | 기존 `onboarding_service.py` 및 초안/미리보기/확정 유지. `ExperimentSetup`은 예약 참가자의 첫 설정만 담당. 일반 설계는 기존 Frontier/Theme/Review 화면 사용 |
| risk/frontier/optimization | `frontier_service.py`, `base_portfolio_service.py`, `portfolio_service.py`, `src/forward/portfolio.py`는 main과 동일. 계산식·위험 가드레일·최적화 재구현 없음 |
| portfolio | 기존 자산 구성/예상 위험/구성 변경 보존. 캡스톤 실험 구성은 기본 `/portfolio`, 저장한 자유 설계는 `/portfolio?workspace=design`. 확정 실험 화면에도 저장한 자유 설계 링크 제공 |
| dashboard | 캡스톤에서 숨겨졌던 기존 운용 대시보드를 `/dashboard?workspace=design`에 연결. 자유 설계 화면의 ‘운용 성과 확인’과 ‘저장된 포트폴리오 확인’이 동일 설계 저장소를 조회. 기본 `/dashboard`는 비교 실험 성과 |
| sidebar/routing | 단일 AppSidebar·AppShell·세션. 메뉴에 앱·버전 선택 없음. 성과 분석 그룹에서 대시보드·참여자 비교로 이동 |
| participant/API types | 원래 participant 생성은 유지하고 서버가 신규 계정의 participant를 예약 슬롯에 연결. 원래 `web/lib/api/types.ts`는 main과 동일. 추가 비교 DTO만 별도 파일로 확장 |
| authorization | 기존 CSRF 검증 재사용. 캡스톤 초기 설정은 본인 슬롯·미확정 조건, 자유 설계는 분리 DB에만 쓰기 허용. 다른 사용자의 개인 계정 장부 접근은 허용하지 않음 |
| 성과 계산 | 기존 가상 NAV와 Return/Excess/MDD/Volatility/Sharpe·TE/IR 계산 보존. 통합 커밋은 비교 계산·공개 seed를 변경하지 않음 |

기존 v1 데이터베이스를 캡스톤 DB로 마이그레이션하거나 그 반대로 복사하지 않았다. 단일 앱의 시연 배포에는 v1의 설계 기능도 포함되지만, 기존 v1 설치에만 있던 계정·개인 이력을 시연 DB에 자동 이전하지 않는다. 계정 저장소 통합은 별도 이전 정책 없이는 실행하지 않는다. 일반 운영 프로필의 기존 DB·가입 정책도 계속 지원한다.

## 최종 메뉴와 사용자 흐름

- 포트폴리오: 포트폴리오 설계 / 내 포트폴리오 / 주간 투자 의견 / 기존 포트폴리오 성과.
- 성과 분석: 성과 대시보드 / 참여자 비교·랭킹.
- Participant Detail은 랭킹·차트에서 이동한다.

신규 초대 사용자: 실제 가입·기존 정책의 자동 로그인 → 공통 CORE 확인 → Theme 최대 2개·이유 → 비중 확인·생성 → 내 포트폴리오 → Dashboard → Ranking/Race/Risk–Return → Detail.

기존 비교 참가자: 로그인 → 기존 Frontier 자유 설계 → 저장한 내 포트폴리오 → 해당 설계 운용 대시보드·주간 의견 → 성과 분석의 13명 비교. 자유 설계 변경 전후의 확정 비교 응답이 동일함을 브라우저 테스트로 확인한다.

## Production 초대 설정

로컬 `/private/tmp` 파일은 발표자에게 초대를 전달하는 수단이다. Backend가 이 절대 경로를 읽어서 가입을 검증하지 않는다. 배포 설정은 **Render 서버 전용** `CAPSTONE_INVITATIONS_JSON`을 이용한다. Vercel/NEXT_PUBLIC에는 넣지 않는다.

```json
{
  "cohort_id": "professor-hosted-01",
  "invitations": [
    {"email": "presenter@example.com", "invite_sha256": "<무작위 초대 코드의 SHA-256 소문자 64자리>"}
  ]
}
```

초대 코드는 `secrets.token_urlsafe(32)` 수준의 난수여야 한다. 원문은 발표자만 보관하고, 서버 설정·DB에는 해시만 저장한다. 이메일 항목 1개면 12+1, 2개면 11+2이다. 저장소에 실제 코드나 실제 해시 설정을 추가하지 않는다.

시연 전 관리자가 기존 캡스톤 seed가 있는 **격리된 SQLite 환경**에서 다음 명령을 명시적으로 실행한다.

```bash
APP_PROFILE=local CAPSTONE_DEMO=1 DATABASE_BACKEND=sqlite \
  .venv/bin/python -m src.local.demo_cohort --from-env
```

호스팅 런타임에는 `.venv/bin/python` 대신 해당 런타임의 `python`을 사용한다. 환경변수는 제공업체의 서버 설정/secret configuration으로 주입하며 명령줄 인자로 실제 코드를 전달하지 않는다. API startup·일반 가입·seed가 이 명령을 자동 호출하지 않는다. 최초 배포 준비 단계에서 실행할 때에도 기존 저장소 보존을 먼저 확인한다.

- 같은 활성 비교군·이메일·해시로 재실행하면 아무 설정·계정·초안·확정 결과도 덮어쓰지 않는다.
- 기존 구성과 다르거나 다른 활성 비교군이 있으면 실패한다. 이름만 바꿔 서버 시작 시 비교군을 교체하지 않는다.
- PostgreSQL/live 프로필에서는 거절한다. 이 기능 때문에 운영 DB migration이 실행되지 않는다.
- 원래 `--name / --email / --out` 로컬 초대 생성 방식은 유지한다.
- 실제 가입 요청에서 이메일·코드 해시는 Backend가 검증하며 기존 인증·CSRF·슬롯 정원 정책을 적용한다.

## 데이터 persistence

**A. 교수님 단기 시연:** 현재 로컬 파일 DB는 재시작·새로고침 후 계정·초안·확정 설정을 유지한다. 명시적 준비 명령과 기존 12명+예약 1자리로 시연 가능하다. Render 임시 SQLite에서도 하나의 살아 있는 인스턴스 안에서는 저장되지만, 재배포·인스턴스 교체 후 유지되지 않는다. 초대 해시 환경변수가 남더라도 사라진 사용자·초안·확정 구성을 복구해 주지 않는다.

**B. 13명 지속 사용:** 영속 저장소와 백업·복구, 운영 migration, 실제 Forward 시작/스케줄러를 별도 작업으로 계획해야 한다. 기존 PostgreSQL 지원을 재사용하는 방안과 영속 디스크 방안을 평가해야 하며, 이번 통합에서는 DB 이전·유료 디스크·새 유료 서비스를 만들지 않는다. 기존 자유 설계 DB와 비교 DB 모두 보존 범위에 포함해야 한다.

## 로컬 검증

- Backend 전체: **143 passed, 3 skipped**. 선택적 PostgreSQL 검증은 환경 미제공으로 skip. 기존 라이브러리 deprecation 경고 존재.
- Frontend unit: **45 passed**.
- Production build: `NEXT_PUBLIC_CAPSTONE_DEMO=1`과 `0`을 각각 별도 빌드 디렉터리에서 통과했다. Next의 lint/type 검사도 함께 통과했다.
- `python web/e2e/run_integration.py`: 캡스톤 3개 + 원래 일반 프로필 1개 브라우저 테스트 통과.
- 캡스톤: 신규 2명 실제 가입·독립 이유/Theme·새로고침·생성·13명·Dashboard/Ranking/Detail 대사·기존 계정 전환·모바일.
- v1: 가입/로그인·Frontier 양 끝 위험 선택·Theme·미리보기 위험값·확정 비중·기존 운용 대시보드·주간 의견 제출·재로그인 후 저장 상태 확인. 캡스톤/일반 프로필 모두 검증.
- 실제 API 프로세스 재시작 후 13개 비교 보고서 및 신규 2명 구성 보존 확인.
- 환경 초대: idempotence, 가입 후 초안/계정 보존, 잘못된 설정, 활성 비교군 변경 차단, live 거절 테스트 6개.
- 생성 캐시·테스트 출력·로컬 DB·Vercel 연결 파일은 커밋 대상에서 제외한다. 기존 의존성과 금융 함수를 그대로 사용한다.
- GitHub CI에서 라이브러리 버전에 따라 API 테스트의 요청별 쿠키가 공유 cookie jar와 중복되어 다른 테스트 계정으로 요청되는 문제가 발견됐다. 테스트 전용 클라이언트가 명시한 쿠키 세트만 HTTP 헤더로 전송하도록 수정했다. 실제 인증 서비스나 권한 검증을 완화하지 않았다. 계정 fixture에서 응답 이메일도 확인한다.

## 배포 대상 확인과 남은 작업

읽기 전용으로 확인한 기존 대상은 Vercel `robo-q3o3` (`https://robo-q3o3.vercel.app`)과 Render `robo-capstone-api` (`https://robo-capstone-api.onrender.com`)이다. Render는 `MinchoLover/robo` fork의 `feat/capstone-demo-mvp`, 기존 성공 배포 `04e4938`에 연결되어 있다. origin은 `Siin-Git/robo`이므로 origin push만으로 Render가 갱신되지는 않는다. Render 자동 배포는 꺼져 있다.

이 문서 작성 시점에는 통합 코드 Production 배포·원격 신규 가입 흐름을 아직 실행하지 않았다. 로컬 검증 결과와 기존 원격 서비스의 응답 확인을 구분한다. Production 배포 전 임시 저장소의 기존 데이터 보존/손실 조건을 확인해야 한다.

기존 원격 서비스의 읽기 검증: Vercel `/login`은 200, `/signup`은 이전 구현의 `/login`으로 리다이렉트된다. Render `/health`는 cold start 이후 200, `/ready`는 `503 / no market data`다. 이는 통합 배포 성공을 의미하지 않는다. 현 상태에서 가격 이력이 필요한 설계 위험값까지 원격에서 검증됐다고 보고하지 않는다. Vercel Production의 `FASTAPI_INTERNAL_URL`, `NEXT_PUBLIC_CAPSTONE_DEMO=1` 연결 설정은 존재한다. DB 비밀 환경변수는 출력하거나 새 클라이언트 변수로 이동하지 않았다.

## 유지한 Analytics와 미지원 요구사항

Race, Risk–Return, 지표별 Ranking, 상대 순위, NAV 비교, 기존 TE/IR, 데이터 기준 주간, Theme 선택자 평균을 보존한다. Sortino와 가상 NAV에 대응하는 누적/주간 Asset·Base·Theme Contribution은 지원되지 않는다. 금융팀이 같은 구성·기간의 평가/보유/거래 자료와 계산 정의를 제공해야 한다. 세부 API 계약은 [운영 안내](UNIFIED_DEMO.md)의 금융팀 확인 항목을 따른다.

## 알려진 제한과 검증 주체

가상 시나리오는 신규 가입자의 과거 실제 운용 기록이 아니다. 지원하지 않는 Theme 조합은 순위에 포함하지 않고 성과 집계 대기로 남긴다. 실제 Forward 실행과 장부 기반 attribution은 시작하지 않았다. 로컬 가격 참조 파일이 없는 환경은 자유 설계의 일부 예상 위험값을 산출할 수 없으며, 수치를 만들어 채우지 않는다.

AI가 main diff와 현재 구현을 비교하고 최소 연결 수정·초대 설정·회귀 테스트·문서를 작성했다. 위 통과 결과는 실제 실행한 검사에 근거하며 원격 데이터 영속성을 입증하는 결과가 아니다.
