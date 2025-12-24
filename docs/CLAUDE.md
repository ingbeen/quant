# docs 폴더 가이드

> 이 문서는 `docs/` 폴더의 문서 작성 및 계획서 관리 규칙에 대한 상세 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

docs 폴더는 QBT 프로젝트의 개발/운영 문서와 변경 계획서를 관리합니다.

**폴더 구조**:

```
docs/
├── CLAUDE.md           # docs 관련 규칙 (이 문서)
├── plans/              # 변경 계획서 저장소
│   ├── _template.md    # 계획서 템플릿
│   └── PLAN_*.md       # 실제 계획서
└── archive/            # 완료/폐기된 계획서 및 작업 문서
```

**핵심 원칙**:

- 문서는 안전한 변경을 위한 도구입니다 (문서 자체가 목적이 아님)
- 작은 변경은 계획 없이 진행
- 큰 변경은 `plans/`에 계획 작성 후 진행

---

## AI 작업 흐름

### 계획서가 필요한 경우

다음 중 하나라도 해당하면 `docs/plans/`에 계획서를 먼저 작성합니다:

- 여러 파일/여러 모듈에 걸친 변경
- `storage/*` CSV 스키마, 저장 규칙, 결과 컬럼 등 불변 규칙에 영향
- 백테스트/시뮬레이션 핵심 로직 변경 (수익률, 비용, 체결 규칙 등)
- 테스트 추가가 다수 필요하거나 회귀 가능성이 높음
- 완료 기준이 명확하지 않음

작은 변경(단일 버그 픽스/주석/로그/포맷)은 계획서 없이 진행합니다.

### 표준 작업 절차

**0) 규칙/맥락 로딩**:

- 루트 `CLAUDE.md` 확인
- 작업 대상 폴더의 `CLAUDE.md` 확인
- 데이터 관련이면 `utils/data_loader.py`, `common_constants.py` 규칙 확인

**1) 계획서 작성** (필요 시):

1. 이 문서(`docs/CLAUDE.md`)를 읽습니다
2. `docs/plans/_template.md`를 기반으로 계획서 작성
   - 파일명: `docs/plans/PLAN_<short_name>.md`
   - Phase는 3~7개로 분해
   - 각 Phase마다 Validation 명시
3. 계획서 내용:
   - Goal: 목표 설정
   - Non-Goals: 범위 제외 항목
   - Context: 배경/필요성/영향 받는 규칙
   - Definition of Done: 완료 조건 체크리스트
   - Scope: 변경 대상 파일 및 데이터/결과 영향
   - Phases: 단계별 계획 (각 Phase별 Validation)
   - Risks: 예상 위험 및 완화 전략

**2) Phase 단위 구현**:

각 Phase는 다음을 만족해야 다음 Phase로 진행합니다:

- 구현 코드 + 테스트 코드 (또는 기존 테스트 보강)
- 포맷/린트/테스트 통과
- Plan 문서의 체크박스 업데이트

**3) 마무리**:

- Plan의 완료 조건 충족 확인
- 필요한 경우 문서 업데이트
- 회귀 위험이 있는 변경이면 테스트 케이스 반드시 작성

**완료/폐기된 계획서 처리**:

- 완료되거나 폐기된 계획서는 `docs/archive/`로 이동
- 히스토리 관리 목적이며, 향후 유사 작업 시 참고 자료로 활용

---

## 품질 게이트

로컬에서 다음 중 최소 1개 이상을 실행해 확인합니다 (변경 규모에 따라 조합):

### 테스트

```bash
# 전체 테스트
./run_tests.sh

# 커버리지 포함
./run_tests.sh cov
```

### 린트/포맷

```bash
# 린트
poetry run ruff check .

# 포맷 검사
poetry run black --check .
```

---

## plans 폴더 사용 규칙

### 파일 네이밍

- 템플릿: `docs/plans/_template.md`
- 계획서: `docs/plans/PLAN_<short_name>.md`
  - 예: `PLAN_tqqq_cost_model_refactor.md`
  - 예: `PLAN_backtest_grid_results_schema.md`

### 템플릿 구성

`docs/plans/_template.md`를 복사하여 새 계획서를 작성합니다:

1. **상단 메타정보**: 상태, 작성일, 관련 범위, 관련 문서
2. **Goal**: 목표 설정
3. **Non-Goals**: 범위 제외 항목
4. **Context**: 배경/필요성/영향 받는 규칙
5. **Definition of Done**: 완료 조건 체크리스트 (6개 항목)
   - 기능 요구사항 충족
   - 회귀/신규 테스트 추가
   - 테스트 통과 (`./run_tests.sh`)
   - 린트 통과 (`poetry run ruff check .`)
   - 포맷 통과 (`poetry run black --check .`)
   - 문서 업데이트
6. **Scope**: 변경 대상 파일 및 데이터/결과 영향
7. **Phases**: 단계별 계획 (3~7개, 각 Phase별 Validation)
8. **Risks**: 예상 위험 및 완화 전략
9. **Notes**: 참고 사항

### Phase 구성

Phase는 3~7개로 구성하며, 각 Phase는:

- 명확한 목표와 범위
- 독립적으로 검증 가능
- Validation 섹션에 검증 커맨드 명시

### 운영 목적

계획서는 다음을 명확히 하여 변경을 안전하게 만드는 것이 목적입니다:

- 리스크 분해 (Phase)
- 검증 커맨드 명시
- 롤백 전략

---

## archive 정책

`docs/archive/` 폴더는 다음을 보관합니다:

- 완료된 계획서: 성공적으로 완료된 PLAN\_\*.md 파일
- 폐기된 계획서: 취소되거나 중단된 계획서
- 작업 중 생성된 임시 문서: 테스트 진행 상황, 요약 문서 등

**목적**:

- 히스토리 관리
- 향후 유사 작업 시 참고 자료로 활용
- 현재 진행 중인 계획서와 분리

**규칙**:

- 완료/폐기된 계획서는 사용자가 수동으로 이동
- 파일명은 그대로 유지
- 필요시 완료 날짜를 파일명에 추가 가능
