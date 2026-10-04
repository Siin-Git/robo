# 공개 운영 연결 인수 기록 — 2026-10-04

목표는 완성 기능을 Siin-Git/robo의 공개 운영으로 연결하는 것이다. 기존 체크아웃·미커밋 작업·실제 데이터는 보존한다. 새로운 전략·비교 기준을 추가하지 않는다.

## 코드 및 현지 검증

develop `cb5c778`에 성과·랭킹 `09e92ad`를 별도 `integration/public-release` worktree에서 통합했다. main `643ea82`와 PR #12는 보존한다.

CI는 Python 3.11과 폐기 PostgreSQL 18의 일반·인증·운용 DB를 사용해 tests 전체를 실행한다. backup은 PR #12의 독립 CI를 유지한다. optimizer/frontier/covariance/returns 등 루트 계산 검사를 포함하며 운영 secrets를 테스트에 주입하지 않는다.

현지 Python 3.11 + 폐기 PostgreSQL 14에서 비백업 511개 통과. 백업 검사 12개는 전용 역할명이 달라 환경 오류가 발생했다. 폐기 클러스터에 backup_test 역할을 만든 후 백업 검사 35개 모두 통과했다. 제품 코드나 검사를 우회하지 않았다. Vitest 67개 및 Next production 빌드 통과.

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

Actions 37191062722의 Neon: 인증 robo_auth, 운용 robo_design. 당시 사용자 15, 운용 계좌 33·주문 292·체결 266·평가 124. 로컬과 다른 기록을 덮어쓰지 않는다. 이 보고서만으로 앱의 연결을 증명하지 않는다. 최신 ID 지문·실제/합성 출처 대조 후 원본과 이전 대상을 결정해야 한다.

## 실행자·백업·복구

실제 실행자는 이 맥의 daily LaunchAgent, 매일 07:30 KST. 월간 예약은 없다. Actions daily/monthly/weekly는 active이고 forward-jobs concurrency를 공유한다. FORWARD_EXECUTOR 미설정으로 정상 예약은 비활성화다. 외부 실행자 상태를 사용자에게 질문했다. 새 환경이 준비되기 전 기존 실행자를 중단하지 않는다.

PR #12 backup.yml은 변경하지 않는다. PG_BACKUP_CLIENT_MAJOR=18, 두 DB secrets 존재. BACKUP_AUTH_HOST/DATABASE·BACKUP_DESIGN_HOST/DATABASE는 미설정이다. 앱과 독립적인 대상 대조 후 설정해야 한다. 아직 실제 운영 덤프·복원 성공으로 보고하지 않는다. 폐기 DB 검사와 SQLite 원본 백업은 별도 증거이며 PostgreSQL 백업이 SQLite를 보호하지 않는다.

다음: CI/develop PR 병합, 배포 저장소 확인 후 main 릴리스 PR/CI/병합. 확인된 API/DB를 먼저 배포하고 그 다음 Vercel 프론트. 충돌 기록은 선택지를 제시하고 보존한다. 새 실행자 준비 후 기존 daily 중단·Actions 전환. 실패 시 Actions 비활성화 후 기존 원본/예약 복구; 분기 기록은 자동 덮어쓰지 않는다. 두 실제 덤프는 빈 폐기 PostgreSQL 18에만 복원한다.

공개 사용자 흐름은 아직 미검증이다. 실제 체결·평가가 없으면 대기를 유지한다. 0/1/MDD/null·이전 판단 브라우저 검사는 별도 합성 fixture에서 수행하며 운영 데이터로 복사하지 않는다.
