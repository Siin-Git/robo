# Render 데모 배포

기존 `render.yaml`은 일반 PostgreSQL 모드입니다. 이번 시연은 **`render.demo.yaml`**을 사용합니다.

## 생성할 리소스

- `robo-capstone-web`: Next.js public Web Service, Starter, Singapore
- `robo-capstone-api`: FastAPI Private Service, Starter, Singapore, 단일 프로세스
- `capstone-demo-data`: API에 연결되는 1 GB 영구 디스크(`/var/data`)
- DB: `/var/data/capstone_demo.db` — PostgreSQL은 만들지 않음

두 서버와 영구 디스크는 유료입니다. 생성 전 Render 화면의 월 예상 비용을 확인하세요.
자동 배포는 꺼져 있습니다. 코드 변경 후 해당 서비스에서 Manual Deploy를 실행합니다.

## 최초 배포

1. Render에 로그인하고 **New → Blueprint**를 선택합니다.
2. GitHub에서 `Siin-Git/robo` 저장소 접근을 연결합니다. 권한을 선택할 수 있다면 이 저장소만 선택합니다.
3. Branch: `feat/capstone-demo-mvp` (main에 병합한 뒤라면 main)
4. Blueprint Path: `render.demo.yaml`
5. Blueprint 이름을 정하고 위 리소스와 비용을 확인한 뒤 생성합니다.
6. API 시작 시 seed가 자동 실행됩니다. 최초에는 13명을 만들고, 이후 실행은 기존 계정·NAV·비밀번호를 덮어쓰지 않습니다.
7. `robo-capstone-web` 화면의 실제 `https://…onrender.com` 주소를 엽니다.

내부 API 주소는 Blueprint의 `fromService.hostport`로 자동 연결합니다. Next.js 시작 명령이 HTTP URL을 구성합니다. 브라우저는 같은 웹사이트의 `/api/v1`만 호출하므로 별도의 브라우저용 API URL이나 CORS 도메인 입력이 필요하지 않습니다.

## 접속 검증

- capstone01 로그인 → Dashboard 테마·성과·차트 확인
- Ranking 13명 및 Return / Sharpe / MDD 정렬 → 02 상세 페이지 확인
- Logout → capstone03 로그인 → 새로고침 후 계정 유지 확인
- 응답 쿠키 `ra_session`: HttpOnly, Secure, SameSite=Lax
- API 서비스를 재시작한 뒤 계정·NAV 및 기존 유효 세션 유지 확인

계정: `capstone01@example.com` ~ `capstone13@example.com`
초기 비밀번호: `Capstone-Demo-2026!`

이 초기 비밀번호는 저장소에 공개된 시연용 값입니다. 실제 개인정보·자산을 넣지 마세요. 팀원별 사용 구분이 필요하면 각자 Account 화면에서 비밀번호를 변경한 뒤 사용합니다. seed 재실행은 변경된 비밀번호를 초기화하지 않습니다.

## 로그 / 장애 확인

- API 로그에서 `13 demo accounts ready`와 uvicorn 시작을 확인합니다.
- 웹에서 503 `UPSTREAM_UNAVAILABLE`이면 API가 Live인지 먼저 확인합니다.
- 비교 데이터가 없으면 API 설정의 `APP_PROFILE=local`, `CAPSTONE_DEMO=1`, `CAPSTONE_DATA_DIR=/var/data`와 disk mount를 확인합니다.
- 웹이 일반 모드로 보이면 `NEXT_PUBLIC_CAPSTONE_DEMO=1`을 설정한 상태에서 다시 **빌드**합니다.
- `.env.local` 및 로컬 DB를 업로드하지 않습니다. 필요한 설정은 Blueprint에 들어 있습니다.
- 영구 디스크를 삭제하면 계정 변경 내용과 세션이 사라집니다. 디스크를 유지하세요.

## 공유 문구

실제 배포 완료 후 `<웹 주소>`를 교체하여 팀원에게 전달합니다.

> 교수님 시연용 Robo Advisor: <웹 주소>/login
> 계정: capstoneXX@example.com (배정된 번호)
> 초기 비밀번호는 별도로 전달합니다.
> 로그인 → 내 성과 → 참여자 성과 비교 → 참가자 상세 순서로 확인해주세요.
> 표시되는 NAV와 성과는 시연용 가상 데이터입니다.

실제 팀원 이름·연락처·계정 배정 목록은 저장소에 기록하지 않습니다.
