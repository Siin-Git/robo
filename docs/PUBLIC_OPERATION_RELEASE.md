# 공개 운영 연결 인수 기록 — 2026-10-04

목표는 완성 기능을 Siin-Git/robo의 공개 운영으로 연결하는 것이다. 기존 체크아웃·미커밋 작업·실제 데이터는 보존한다. 새로운 전략·비교 기준을 추가하지 않는다.

## 코드 및 현지 검증

develop `cb5c778`에 성과·랭킹 `09e92ad`를 별도 `integration/public-release` worktree에서 통합했다. main `643ea82`와 PR #12는 보존한다.

통합 커밋 `2b83b8a`는 PR #19로 제출됐다. push CI 37192393042, PR CI 37192493320의 백엔드·프론트 모두 통과한 뒤 develop에 `46db48b`로 병합했다. main은 아직 변경하지 않았다. 실제 배포 저장소 권한 확인 전에 릴리스 병합을 하지 않는다.

CI는 Python 3.11과 폐기 PostgreSQL 18의 일반·인증·운용 DB를 사용해 tests 전체를 실행한다. backup은 PR #12의 독립 CI를 유지한다. optimizer/frontier/covariance/returns 등 루트 계산 검사를 포함하며 운영 secrets를 테스트에 주입하지 않는다.

현지 Python 3.11 + 폐기 PostgreSQL 14에서 비백업 511개 통과. 백업 검사 12개는 전용 역할명이 달라 환경 오류가 발생했다. 폐기 클러스터에 backup_test 역할을 만든 후 백업 검사 35개 모두 통과했다. 제품 코드나 검사를 우회하지 않았다. Vitest 67개 및 Next production 빌드 통과.

Chrome 격리 기존 원장 흐름 2개·MDD/null 공백 흐름 2개 통과. 새 격리 주기 선택/테마/확정/재로그인 모바일 1개 및 데스크톱 1개 통과. 첫 데스크톱 검사에서는 Next 초기 컴파일 중 기본 5초 이동 제한을 넘겼다. 아직 미확정인 같은 계정으로 재실행해 통과했고 주기 검사의 expect 제한을 다른 원장 검사와 같은 20초로 명시했다. 합성 날짜와 기록은 /private/tmp fixture에서만 사용한다.

수동 daily dry-run은 읽기 전용 두 DB 목록을 기록한다. 계정·판단·원장 ID는 지문만 보존하고 비밀번호·URL·토큰·이메일을 출력하지 않는다. 실제 SQLite 복사본을 이전한 폐기 DB에서 검증했다.

## 배포 대상

Render 현재 계정은 kyu6716, My Workspace/Hobby (`tea-dan1h86gekts73fbl230`) 하나다. a·robo-web 프로젝트는 비어 있고 My project에는 무료 중단 서비스 두 개가 있다. No active services는 서비스 부재를 의미하지 않는다.

| 서비스 | 저장소·브랜치 | 마지막 성공 커밋 | 상태 |
| --- | --- | --- | --- |
| robo_ex (`srv-dan1llrtqb8s73a8p3fg`) | gue02/robo_ex main | eddb036e7bb6baefe3bb4ff0fa1082452cdbfba4 | 사용자 중단 |
| robo_ex-1 (`srv-dan4uougekts73fnk050`) | gue02/robo_ex main | 같은 커밋 | 사용자 중단 |

Python 시작 명령은 seed_capstone 실행이다. 원본을 이어가는 운영 배포 명령으로 적합하지 않다. 대상 확인 전 기존 서비스를 변경하지 않는다. 신규 Render 저장소 목록에는 MinchoLover/robo와 gue02/robo_ex만 있다. Siin-Git/robo ID=1372614355, MinchoLover/robo ID=1376858865로 서로 다른 저장소다. Siin 저장소 배포 권한 연결 또는 기존 API 소유 계정 로그인이 필요하다.

Vercel mincholover / mincholovers-projects:

| 프로젝트 | 저장소 | 생산 브랜치 | 루트 | 최신 배포 |
| --- | --- | --- | --- | --- |
| robo | MinchoLover/robo | main | 미설정 | b06a6bf, ERROR |
| robo-q3o3 | MinchoLover/robo | feat/capstone-demo-mvp | web | b06a6bf, READY |

robo-q3o3의 FASTAPI_INTERNAL_URL=https://robo-capstone-api.onrender.com. 현재 Render 계정에는 해당 API가 없다. 저장소·브랜치·API 대상이 맞지 않으므로 아직 공개 릴리스로 간주하지 않는다. Vercel 전체 비밀값 해독·임시 저장은 자동 승인 검토에서 거절되어 수행하지 않았다. 단일 DATABASE_URL 읽기 전용 조회는 승인되었지만 Vercel이 값을 반환하지 않아 대상은 미확정이다.

## 원본 보존·이전 검증

실제 원본은 루트 `.local/real-forward`의 SQLite 두 개이며 모두 Alembic 0008이다.

| 데이터 | 인증 | 운용 |
| --- | ---: | ---: |
| 사용자 / 계좌 | 15 / 30 | 1 신원 참조 / 2 |
| 판단 | 0 | 3 |
| 주문 / 체결 / 평가 | 0 / 0 / 0 | 8 / 0 / 0 |
| 가격 / 배치 기록 | 0 / 0 | 42,010 / 4 |

18:21 KST daily.lock 및 두 DB의 BEGIN IMMEDIATE 잠금으로 쓰기를 막은 동안 SQLite backup API로 일관된 복사본을 확보했다. `.local/real-forward/backups/public-release-20261004-182128`의 두 파일 integrity=ok, FK 오류 0, revision=0008. 디렉터리 700/파일 600.

복사본을 폐기 PostgreSQL 14/127.0.0.1:55497의 robo_local_auth_copy·robo_local_design_copy에 각각 이전했다. Alembic head 적용 후 원본 해시 보존과 verify_db_parity 전 테이블 PK·필드·FK·회계 항등식 PASS를 확인했다. 계정 연결·판단 ID·버전·효력일·원장을 보존했다. 기존 Neon에 쓰지 않았다.

위 이전 복사본을 PR #12 도구로 실제 두 덤프에 담아 `.local/real-forward/backups/postgres-copy-validation-20261004`에 보호했다. 빈 robo_restore_real_auth_copy·robo_restore_real_design_copy에만 복원했고 SQLite 백업과 전체 PK·필드·FK·금융 합계를 다시 대조해 PASS다. 두 DB 모두 0008, 제약 72개·불변 트리거 2개·인덱스 59개 보존. 시퀀스는 0개이며 기존 counters 데이터는 필드 대조로 보존했다. 복원 시 CHECK의 ARRAY 형변환 표현이 동등한 형태로 바뀌어 원시 문자열 비교가 실패했지만 값/컬럼/제약 속성이 일치하고 잘못된 enum·FK·판단 변경을 모두 거절하는 것을 폐기 DB 롤백 검사로 검증했다. 이 검증은 기존 Neon의 덤프·복구가 아니다.

3073/8073은 통합 코드로 전환했다. 같은 실제 DB/포트/계정/예약을 사용하며 start/stop/status 바로가기는 public-release worktree로 갱신했다. 기존 local-forward-operation worktree의 미커밋 파일과 daily 예약 명령은 보존했다. 실제 기존 계정 로그인, me/decisions/성과/기여도/비교/History 원장 API 및 dashboard/performance/ranking/portfolio 페이지가 모두 200이다. 재시작 후 판단 v1/v2/v3(효력일 모두 2026-10-05), 주문 8건·가격 42,010건·체결/평가 0건과 배치 기록이 백업과 동일하다. 로그인 시각만 정상 갱신됐다. 현재 AWAITING_INITIAL_EFFECTIVE_DATE, observations=0, 순위 UNAVAILABLE/0으로 표시하며 실제 성과를 만들지 않았다.

Actions 37191062722의 Neon: 인증 robo_auth, 운용 robo_design. 당시 사용자 15, 운용 계좌 33·주문 292·체결 266·평가 124. 로컬과 다른 기록을 덮어쓰지 않는다. 이 보고서만으로 앱의 연결을 증명하지 않는다. 최신 ID 지문·실제/합성 출처 대조 후 원본과 이전 대상을 결정해야 한다.

## 실행자·백업·복구

실제 실행자는 이 맥의 daily LaunchAgent, 매일 07:30 KST. 월간 예약은 없다. Actions daily/monthly/weekly는 active이고 forward-jobs concurrency를 공유한다. FORWARD_EXECUTOR 미설정으로 정상 예약은 비활성화다. 외부 실행자 상태를 사용자에게 질문했다. 새 환경이 준비되기 전 기존 실행자를 중단하지 않는다.

마지막 실제 성공: 2026-10-04 07:30:00–07:30:10 KST, daily/success, exit=0. 다음 로컬 예정: 2026-10-05 07:30 KST(맥 실행 필요). Actions 전환 후 준비할 월간 기본 예약은 2026-11-01 09:30 KST이며 사용자별 monthly/quarterly 주기 판정은 기존 엔진을 사용한다. 아직 원격 예약이 활성화됐거나 월간 실제 실행에 성공했다고 주장하지 않는다.

PR #12 backup.yml은 변경하지 않는다. PG_BACKUP_CLIENT_MAJOR=18, 두 DB secrets 존재. BACKUP_AUTH_HOST/DATABASE·BACKUP_DESIGN_HOST/DATABASE는 미설정이다. 앱과 독립적인 대상 대조 후 설정해야 한다. 아직 실제 운영 덤프·복원 성공으로 보고하지 않는다. 폐기 DB 검사와 SQLite 원본 백업은 별도 증거이며 PostgreSQL 백업이 SQLite를 보호하지 않는다.

자동 승인 검토가 (1) Neon ID 지문/행 수를 비공개 Siin-Git/robo Actions artifact에 7일 저장하는 읽기 전용 점검, (2) robo-q3o3를 Siin-Git/robo로 연결하고 API 준비 전 자동 빌드를 임시 보류하는 설정 변경을 거절했다. 정확한 대상·전송 범위·복구안을 사용자에게 질문했으며 응답 전 두 작업은 수행하지 않는다. 첫 Vercel 전체 secret 해독/저장 거절도 우회하지 않는다.

`render.paper.yaml`은 새 무료 PostgreSQL paper API용 준비 설정이다. 기존 setup_postgres --apply로 두 DB를 head까지 올리고 단일 worker를 시작하며 seed/reset/계정 생성은 하지 않는다. 실제 SQLite 이전 복사본의 두 DB에 반복 적용해 0008과 모든 테이블을 확인했다. 실제 서비스 생성·배포·DB 변경은 아직 하지 않았다. 인증/운용 URL은 보호된 환경 설정에서 분리하며 프론트는 동일 출처 프록시로 쿠키·CSRF를 전달한다.

다음: CI/develop PR 병합, 배포 저장소 확인 후 main 릴리스 PR/CI/병합. 확인된 API/DB를 먼저 배포하고 그 다음 Vercel 프론트. 충돌 기록은 선택지를 제시하고 보존한다. 새 실행자 준비 후 기존 daily 중단·Actions 전환. 실패 시 Actions 비활성화 후 기존 원본/예약 복구; 분기 기록은 자동 덮어쓰지 않는다. 두 실제 덤프는 빈 폐기 PostgreSQL 18에만 복원한다.

공개 사용자 흐름은 아직 미검증이다. 실제 체결·평가가 없으면 대기를 유지한다. 0/1/MDD/null·이전 판단 브라우저 검사는 별도 합성 fixture에서 수행하며 운영 데이터로 복사하지 않는다.
