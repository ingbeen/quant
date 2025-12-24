# docs 폴더 가이드

> 이 문서는 `docs/` 폴더의 문서 작성 및 계획서(Implementation Plan) 관리 규칙을 정의합니다.  
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

`docs/`는 QBT 프로젝트의 개발/운영 문서와 변경 계획서(Implementation Plan)를 관리합니다.

## 폴더 구조

```
docs/
├── CLAUDE.md           # docs 관련 규칙 (이 문서)
├── plans/              # 변경 계획서 저장소
│   ├── _template.md    # 계획서 템플릿
└── archive/            # 과거 문서 보관소(기본 무시)
```

### docs/archive 정책 (중요)

- `docs/archive`는 과거 문서 보관용입니다.
- 현재 작업의 규칙/근거/소스 오브 트루스(Source of Truth)로 사용하지 않습니다.
- 현행 규칙은 **루트 `CLAUDE.md` + 각 도메인 `CLAUDE.md` + 최신 plan**만을 기준으로 합니다.

---

## 포맷/린트/테스트 규칙

### Black 실행 원칙

- Phase 진행 중에는 Black을 실행하지 않습니다.
- 마지막 Phase에서만 자동 포맷을 적용합니다.

  - `poetry run black .`

### Ruff 실행 원칙

- 각 Phase의 Validation에서 린트 체크를 수행합니다.

  - `poetry run ruff check .`

- Validation에서 `poetry run ruff check .` 오류가 나오면 **해당 Phase에서 즉시 수정 후 재검증**합니다.
- 마지막 Phase에서도 최종 확인을 위해 한 번 더 실행합니다.

### 테스트 실행 원칙

- 각 Phase의 Validation에서 테스트를 수행합니다.

  - `./run_tests.sh`

- `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**합니다.

---

## plans 폴더 사용 규칙

### 파일 네이밍

- 템플릿: `docs/plans/_template.md`
- 계획서: `docs/plans/PLAN_<short_name>.md`

  - 예: `PLAN_tqqq_cost_model_refactor.md`
  - 예: `PLAN_backtest_grid_results_schema.md`

---

## 계획서 작성 방법 (AI 모델이 반드시 따를 것)

`docs/plans/_template.md`를 복사하여 새 계획서를 작성합니다.

### 1) 계획서에 반드시 포함해야 하는 섹션

계획서는 아래 구성을 반드시 포함합니다.

- Goal: 목표 설정
- Non-Goals: 범위 제외 항목
- Context: 배경/필요성/영향 받는 규칙
- Definition of Done: 완료 조건 체크리스트 (아래 6개 항목)

  - 기능 요구사항 충족
  - 회귀/신규 테스트 추가
  - 테스트 통과 (`./run_tests.sh`)
  - 린트 통과 (`poetry run ruff check .`)
  - 포맷 적용 (`poetry run black .`) — 마지막 Phase에서 실행
  - 필요한 문서(README/CLAUDE/plan) 업데이트

- Scope: 변경 범위(변경 대상 파일, 데이터/결과 영향)
- Phases: 단계별 계획(각 Phase의 할 일 + Validation)
- Risks: 리스크와 완화책
- Notes: 메모/결정사항/링크

### 2) Phase 통합/분리 규칙 (문맥 기반)

> Phase는 “파일 수”가 아니라 **문맥(context)** 기준으로 구성합니다.

- 동일한 파일 작업: 기본적으로 Phase 1개

  - 단, 작업량이 정말 많아 Validation/리스크 관리가 어렵다면 분리할 수 있습니다.

- 여러 파일이어도 작은 수정이거나 동일 문맥이면 Phase 1개

  - 예: 함수 변경으로 인해 CSV 컬럼까지 변경되는 경우 → 동일 문맥이므로 Phase 통합

- 서로 다른 성격/문맥의 리팩토링이면 Phase를 분리

  - 예: 핵심 로직 변경과 무관한 별도 정리(이름 변경, 유틸 정리 등)를 같이 하려는 경우

✅ 예외(유지): **핵심 인바리언트/정합성(절대 규칙/정의/중요 로직 등)을 수정하는 작업**은
테스트를 먼저(레드) 고정하는 Phase를 분리합니다.

- “정책을 먼저 테스트로 잠그고(레드), 그 다음 구현을 맞춘다(그린)” 흐름을 강제합니다.

### 3) 승인(Approval) 규칙

- 간단한 계획(Phase 1 + 마지막 Phase 정도)이라면 중간 승인 없이 진행할 수 있습니다.
- Phase 2 이상으로 늘어나는 경우에는 **Phase 전환 시점마다 승인 요청 블록이 있어야 합니다.**

  - 예: Phase 1 완료 후 Phase 2로 넘어가기 전 승인
  - 예: Phase 2 완료 후 Phase 3로 넘어가기 전 승인
  - Phase 3 이상도 동일 패턴으로 반복합니다.

### 4) 커밋 메시지(Commit Messages) 규칙

커밋 메시지는 plan 작성 시점부터 계획서 안에 함께 작성합니다.

- 커밋 메시지 형식 규칙:

  - 반드시 `기능명 / ` 형태로 시작
  - 간결하고 명확한 한국어 표현 사용
  - 변경사항의 핵심 내용 반영
  - ✅ 추정(상상)으로 쓰지 말고, 해당 Phase에서 실제로 변경하는 범위를 기준으로 작성

- 파일 경로 기반 기능명 추천 규칙(권장)

  - `src/qbt/backtest/` 변경: `백테스트 / `
  - `src/qbt/tqqq/` 변경: `TQQQ시뮬레이션 / `
  - 그 외는 변경 내용을 보고 그때그때 적절한 기능명을 선택한다.
  - 두 영역이 함께 변경되면 변경의 중심이 되는 기능명 하나로 통일한다(애매하면 문서에 근거를 적고 선택).

- 계획이 간단한 경우:

  - 마지막 Phase에 `Commit Messages (Final)` 섹션을 두고 **3개** 작성

- 계획이 복잡한 경우(Phase 2 이상):

  - **승인 요청이 있는 모든 Phase 전환 지점마다**

    - `승인 요청` 블록 + `Commit Messages (Phase N)`(3개)이 **세트로 반드시 존재**해야 합니다.
    - (즉, 승인 요청이 있으면 commit 메시지도 반드시 존재)

  - 이 규칙에 의해 Phase 2 이상이 존재하면 Phase 1에도

    - `승인 요청` + `Commit Messages (Phase 1)`이 반드시 포함되어야 합니다.

  - 마지막 Phase에는 반드시 `Commit Messages (Final)` 섹션을 두고

    - 작업 전체를 아우르는 **종합 커밋 메시지 3개**를 추가 작성

### 5) 이미 만들어진 계획서 수정 금지 (중요)

- 이미 생성된 `docs/plans/PLAN_<short_name>.md`는 **체크리스트 업데이트 외에는 수정하지 않습니다.**
- (예: 진행 상황 체크, Done 처리, 날짜 업데이트 등은 가능)
- 체크리스트 업데이트란: [ ] -> [x], 상태/날짜 갱신, 진행 로그 추가만 포함(서술/규칙/구조 수정은 금지).
- 내용/구조/규칙을 바꾸고 싶으면 **새 계획서로 작성**합니다.

---

## 완료 후 문서 처리

- 완료/폐기된 계획서는 사용자가 수동으로 `docs/archive`로 이동할 수 있습니다.
- 파일명은 유지합니다.
