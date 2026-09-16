# GitHub 전달 체크리스트

## 1. 권장 저장소 형태

- 개발팀 조직의 비공개 저장소를 권장합니다.
- 기본 브랜치는 `main`으로 둡니다.
- 최초 전달 커밋에 `prototype-v1` 태그를 붙입니다.
- 이 문서의 체크가 끝나기 전에는 공개 저장소로 전환하지 않습니다.

## 2. 업로드 전 확인

- [ ] `.env`, `.env.local`, API 키, 실제 비밀번호가 없음
- [ ] `*.db`, `data/archive/`, 사용자·세션 백업이 없음
- [ ] `.work/`, `node_modules/`, `.next*`, 테스트 결과, 로그가 없음
- [ ] 재현에 필요한 `config/`, `data/snapshots/`, `outputs/frozen/`이 있음
- [ ] `npm ci`, Python 의존성 설치가 새 디렉터리에서 성공함
- [ ] SQLite 초기화 후 로그인과 온보딩이 성공함
- [ ] Python 테스트, 프론트 테스트, TypeScript 검사, 빌드가 통과함
- [ ] 예시 데이터와 실제 데이터가 혼동되지 않음
- [ ] 이미지·가격 데이터의 재배포 권리를 확인함

## 3. 최초 커밋 권장 구성

```text
feat: hand off robo advisor prototype

- add risk and theme onboarding flow
- add personalized portfolio review
- add portfolio allocation dashboard
- add benchmark performance and contribution report
- add API, local setup, tests, and handoff documentation
```

태그:

```powershell
git tag -a prototype-v1 -m "Robo advisor prototype handoff"
```

## 4. GitHub 저장소 설명 예시

> 위험 수준 기반 기본 자산배분과 제한된 테마 틸트를 결합하고, CORE 벤치마크 대비 모의운용 성과와 자산별 기여도를 보여주는 로보어드바이저 프로토타입

## 5. 개발팀에 함께 전달할 메시지

> `README.md`의 개발팀 인수인계 순서부터 확인해 주세요. 이 버전은 제품 흐름과 계산 구조를 검증하는 프로토타입이며 실제 주문을 실행하지 않습니다. 로컬 SQLite로 전체 흐름을 재현할 수 있고, 운영 배포 전 필요한 항목은 `docs/STATUS_AND_NEXT_STEPS.md`에 우선순위별로 정리했습니다.
