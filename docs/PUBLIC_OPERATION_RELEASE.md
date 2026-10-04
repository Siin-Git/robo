# 공개 운영 연결 인수 기록 — 2026-10-04

## 확정된 배포 대상과 작업 분담

사용자가 개인 Render 계정에서 **MinchoLover/robo 비공개 fork**로 배포하기로 확정했다. 새 운영 원본은 **3073의 현재 인증·운용 SQLite 두 개**다. 팀원 Neon 기록은 덮어쓰지 않는다. 이 결정은 이전의 Siin-Git/robo 직접 배포 권한 연결 요청과 원본 선택 보류를 대체한다.

이번 세션은 남은 CI·인수 문서·로컬 검증을 완료한다. main 병합, Render/Vercel 설정·배포, 운영 DB 연결·이전, 예약 변경은 별도 대화에서 담당한다. 3073과 기존 local daily는 유지한다. 아래 PostgreSQL 이전·복원은 이미 완료한 **로컬 복사본 검증**이며 원격 운영 이전이 아니다.

| 저장소 / 브랜치 | 확인한 커밋 | 상태 |
| --- | --- | --- |
| Siin-Git/robo develop | `250f315aaa1cf75e77bdaa3729993e4be8874f65` | PR #19/#20 병합, CI 통과 |
| Siin-Git/robo release/public-operation | `857d2d1fa57768d386f9c20c09148d94b67ab866` | Draft PR #21, CI 통과, main 미병합 |
| MinchoLover/robo develop | `250f315aaa1cf75e77bdaa3729993e4be8874f65` | 같은 이름·커밋으로 복사 확인 |
| MinchoLover/robo release/public-operation | `857d2d1fa57768d386f9c20c09148d94b67ab866` | 같은 이름·커밋으로 복사, fork CI 통과 |
| Siin-Git/robo main | `643ea822613ac0ae581eb260c3394ffe221b58ba` | PR #12 병합 이력 보존 |
| MinchoLover/robo main | `b06a6bfebef10eb72ac877f0a97621109b508159` | 기존 개인 main 보존 |

인수 문서는 별도 `docs/public-operation-handoff` 브랜치에서 갱신한다. 배포 담당자가 사용하는 develop/release 커밋은 변경하지 않는다. 새로운 전략이나 비교 기준을 추가하지 않았다.

## 완료한 코드 통합과 CI

기존 체크아웃·미커밋 작업을 보존하고 `integration/public-release` worktree에서 develop `cb5c778`과 성과·랭킹 `09e92ad`를 통합했다. PR #19는 `46db48b`, PR #20은 `250f315`로 develop에 병합됐다. 릴리스 후보는 main `643ea82`의 PR #12 이력도 포함한다. PR #12를 다시 병합하거나 이전 코드로 되돌리지 않았다. 백업 workflow와 도구는 해당 main과 동일하다.

| CI 대상 | Actions run | 결과 |
| --- | --- | --- |
| PR #19 push / PR | [37192393042](https://github.com/Siin-Git/robo/actions/runs/37192393042) / [37192493320](https://github.com/Siin-Git/robo/actions/runs/37192493320) | backend/frontend 성공 |
| PR #20 push / PR | [37193149357](https://github.com/Siin-Git/robo/actions/runs/37193149357) / [37193194229](https://github.com/Siin-Git/robo/actions/runs/37193194229) | backend/frontend 성공 |
| develop `250f315` | [37193488140](https://github.com/Siin-Git/robo/actions/runs/37193488140) | 성공 |
| release `857d2d1` push / PR #21 | [37193667347](https://github.com/Siin-Git/robo/actions/runs/37193667347) / [37193734477](https://github.com/Siin-Git/robo/actions/runs/37193734477) | backend/frontend 성공 |
| 개인 fork release `857d2d1` | [37193810605](https://github.com/MinchoLover/robo/actions/runs/37193810605) / [37193810635](https://github.com/MinchoLover/robo/actions/runs/37193810635) | 성공 |

개인 fork develop은 조회 시 Actions run이 없었다. 같은 커밋의 Siin develop CI와 fork release CI는 위 결과로 구분한다.

CI는 Python 3.11과 폐기 PostgreSQL 18의 일반·인증·운용 DB를 사용한다. `python -m pytest tests --ignore=tests/backup -q`로 optimizer/frontier/covariance/returns 등 루트 계산 검사도 포함한다. backup 검사는 PR #12의 독립 CI를 유지한다. 운영 secrets를 테스트에 주입하지 않는다.

현지 검증은 비백업 Python 511개 + 폐기 DB 백업 검사 35개, Vitest 67개, Next production 빌드가 통과했다. 처음 백업 검사 환경의 전용 역할명이 달라 발생한 오류는 폐기 클러스터에 `backup_test` 역할을 준비해 해결했다. 제품 검사를 우회하지 않았다.

Chrome 격리 fixture의 원장·동일 기간 참여자 비교 2개, MDD 중간 하락·null 공백 2개, 초기 매월/매분기→테마→확정→재로그인 흐름 2개(데스크톱/모바일)가 통과했다. 주기 검사의 Next 초기 컴파일 대기를 위해 expect timeout을 20초로 명시했다. 합성 기록·날짜는 `/private/tmp` fixture에만 있으며 실제 운영으로 복사하지 않았다.

## 3073의 확정 원본과 최종 로컬 검증

원본 경로는 저장소 루트 `.local/real-forward`다. `capstone_demo.db`가 인증, `portfolio_design.db`가 운용이다. 둘 모두 Alembic head `0008`, integrity `ok`, 외래키 오류 0건이다.

| 데이터 | 인증 | 운용 |
| --- | ---: | ---: |
| 사용자 / 계좌 | 15 / 30 | 1 신원 참조 / 2 |
| 판단 | 0 | 3 |
| 주문 / 체결 / 평가 | 0 / 0 / 0 | 8 / 0 / 0 |
| 가격 / 배치 기록 | 0 / 0 | 42,010 / 4 |

판단 v1/v2/v3와 계정 연결·판단 ID·원장은 보존됐다. 효력일은 모두 2026-10-05, 최신 가격일은 2026-10-02다. 실제 체결·평가 관측이 없어 `AWAITING_INITIAL_EFFECTIVE_DATE`, `INSUFFICIENT_HISTORY`, 비교 `UNAVAILABLE`/0명을 유지한다. 성과를 만들기 위한 날짜 변경·강제 월간 실행은 하지 않았다.

3073/8073은 앞선 통합 작업에서 `.work/public-release`의 검증 코드 `a39fc79`로 전환했고 같은 DB·계정·포트를 유지한다. 제품 코드는 develop `250f315`와 같다. 시작/중지/상태 바로가기는 해당 worktree를 가리킨다. 기존 `local-forward-operation` worktree의 미커밋 파일과 daily 예약 명령은 보존했다.

이전 검증에서 실제 기존 계정의 로그인·me·판단·History 원장·성과·기여도·참여자 비교 API, dashboard/performance/ranking/portfolio 페이지가 모두 200이었다. 재시작 후 실제 기록을 SQLite 백업과 대조해 보존을 확인했다. 로그인 시각과 세션은 정상 갱신됐다.

최신 사용자 지시 후에는 재시작·로그인·배치 실행 없이 읽기 전용으로 다시 검증했다. `/login`·`/api/v1/version` 200, 미인증 `/api/v1/auth/me` 401이며 위 표의 모든 핵심 테이블은 일관된 백업과 동일하다(사용자의 로그인/수정 시각 제외). 결과는 `.local/real-forward/final-handoff-verification.json`, 앞선 사용자 흐름 결과는 `release-local-verification.json`에 있다. 원본·자격증명·덤프는 Git에 넣지 않는다.

## 원본 백업·폐기 환경 이전·복구 결과

2026-10-04 18:21 KST에 daily.lock 및 두 DB의 BEGIN IMMEDIATE 잠금으로 쓰기를 조정하고 SQLite backup API로 일관된 복사본을 확보했다.

- SQLite 원본 백업: `.local/real-forward/backups/public-release-20261004-182128`.
- 두 파일 모두 integrity `ok`, FK 오류 0, revision `0008`. 디렉터리 700/DB·manifest 파일 600.
- 복사본을 폐기 PostgreSQL 14, `127.0.0.1:55497`의 `robo_local_auth_copy` / `robo_local_design_copy`에 이전했다.
- 원본 파일 해시 불변, 전체 테이블 PK·필드·FK·금융 합계 대조 PASS. 계정 연결·판단 ID·버전·효력일·원장을 보존했다.
- PR #12 도구로 두 덤프를 만들었다: `.local/real-forward/backups/postgres-copy-validation-20261004/robo_auth.dump` 및 `robo_design.dump`(600).
- 별도의 빈 `robo_restore_real_auth_copy` / `robo_restore_real_design_copy`에 복원 후 원본 SQLite 백업과 다시 전체 대조 PASS.
- 두 DB 모두 head `0008`, 제약 72개·불변 트리거 2개·인덱스 59개 보존. 시퀀스 0개, counters는 필드 대조로 보존.
- CHECK 표현의 ARRAY 형변환 문자열은 복원 시 동등한 형태로 바뀐다. 값/컬럼/제약 속성과 잘못된 enum·FK·판단 변경 거절을 폐기 DB 롤백 검사로 확인했다.

이 결과는 **3073 데이터 복사본의 이전·덤프·복원 검증**이다. 새 원격 운영 DB 이전이나 기존 팀원 Neon 백업의 성공 증거가 아니다. PostgreSQL 백업은 현재 원본 SQLite 파일을 보호하지 않으므로 위 SQLite 백업을 별도로 보존한다. 원격 이전 직전에는 기존 daily 쓰기를 조정하고 새 일관된 백업을 만들어야 한다.

## 유지한 실행자와 별도 배포 담당자의 후속 작업

현재 실제 실행자는 맥의 `com.roboadvisor.local-forward.daily` LaunchAgent다. 기존 명령은 `.work/local-forward-operation/scripts/local_operation.py daily`이며 매일 07:30 KST, 같은 `.local/real-forward` 운용 DB를 사용한다. 최신 읽기 전용 점검에서도 loaded 상태와 07:30 설정을 확인했다. 로컬 월간 예약은 없다.

마지막 실제 daily는 2026-10-04 07:30:00–07:30:10 KST, exit 0/COMPLETED다. 최근 가격 관측이 추가되지 않아 내부 통계는 PARTIAL, pending 8, new_points 0이다. 다음 예정은 2026-10-05 07:30 KST이며 맥이 실행 중이어야 한다. 원격 예약 성공·월간 실제 실행으로 보고하지 않는다.

현재 Siin 기본 main의 legacy Actions daily/monthly/weekly에는 새 `FORWARD_EXECUTOR` 가드가 없고 일간 DB 연결도 SQLite다. 기존 Actions 37168877811은 `sqlite3.OperationalError/no such table`로 실패했다. develop/release 후보는 실행자 가드, 인증/운용 PostgreSQL 분리 및 공유 concurrency를 포함하지만 기본 브랜치에 아직 반영하지 않았다. 개인 fork의 기존 예약과 팀원 노트북 실행 여부는 배포 담당자가 확인해야 한다. 같은 새 운영 DB에 쓰는 실행자는 하나만 선택하고, 새 환경이 준비된 뒤 기존 로컬 daily에서 전환한다.

팀원 Neon의 PR #12 사전 확인 run 37191062722에는 인증 사용자 15, 운용 계좌 33·주문 292·체결 266·평가 124가 있었다. **새 운영 원본으로 합치거나 덮어쓰지 않는다.** 그 기록은 별도 대상에 남는다. 아직 3073 기록은 공개 서비스에 이전되지 않았으며 로컬이 원본이다.

`render.paper.yaml`은 무료 PostgreSQL paper API용 준비 파일이다. `setup_postgres.py --apply`로 두 DB를 head까지 올린 뒤 단일 worker로 시작하며 seed/reset/시연 계정 생성은 하지 않는다. 실제 복사본에 반복 적용해 검증했다. 보호된 설정에서 인증/운용 URL을 분리하고 프론트는 같은 출처 프록시로 로그인 쿠키·CSRF를 전달해야 한다.

후속 담당자는 개인 fork 기준으로 API·DB→프론트 순서로 배포하고 실제 커밋·DB 대상·재시작 후 계정/판단/원장 보존·공개 사용자 흐름을 확인한다. PR #12의 두 DB 백업에 앱과 독립적으로 대조한 BACKUP_AUTH_HOST/DATABASE 및 BACKUP_DESIGN_HOST/DATABASE를 설정하고 첫 운영 덤프를 별도의 빈 폐기 PostgreSQL에 복원해야 한다. 운영 DB에 시험 복원하지 않는다. 실패 복구는 새 실행자의 쓰기를 멈추고 보존한 원본과 기존 daily로 돌아가는 순서이며 원본 초기화로 해결하지 않는다.

## 공개 운영 검증과 남은 입력

기존 공개 주소는 https://robo-q3o3.vercel.app 이다. 앞선 읽기 점검의 로그인·version 응답은 정상이나 이번 통합 코드의 배포 결과가 아니다. 당시 production target은 수동 업로드 `dpl_2R8D4gYz9fvBoaZcQjyfy7PKQ8PU`이며 Git SHA가 없어 실제 배포 커밋은 미확정이었다. 기존 Vercel 저장소는 MinchoLover/robo, web 루트, 생산 브랜치는 feat/capstone-demo-mvp였다. API 주소와 Render 서비스·운영 DB 연결은 별도 대화에서 다시 확정한다.

이번 세션에서 main·Render/Vercel·운영 DB·예약은 변경하지 않았다. 공개 로그인→Frontier 주기→테마→확정→재로그인→현재/대기 판단→History→성과·기여도·참여자 비교와 공개 재시작 보존은 후속 운영 검증이다. 코드·로컬 검증 완료와 공개 운영 완료를 구분한다.

이 세션의 필수 입력은 없다. DB 호스팅/보호된 인증·운용 연결값, 실제 서비스 대상, 배치 실행자 전환과 운영 백업 대상 확정은 별도 배포 대화의 남은 작업이다. 이전 Siin 직접 연결 및 원본 선택 승인 질문을 다시 요청하지 않는다.
