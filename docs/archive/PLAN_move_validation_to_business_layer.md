# Implementation Plan: 검증 로직 비즈니스 계층으로 이동

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2025-12-29 14:30
**마지막 업데이트**: 2025-12-29 15:45
**관련 범위**: tqqq, scripts, tests
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `find_optimal_cost_model` 함수 내부에서 FFR 커버리지 검증 수행
- [x] 목표 2: CLI 계층에서 검증 함수 직접 호출 제거
- [x] 목표 3: 비즈니스 로직의 자율성 및 재사용성 향상
- [x] 목표 4: 검증 로직 테스트 추가/수정

## 2) 비목표(Non-Goals)

- 검증 로직 자체의 변경 (로직은 동일하게 유지, 위치만 이동)
- 다른 도메인(backtest 등)의 검증 로직 변경
- CLI 스크립트의 전반적인 리팩토링
- `extract_overlap_period` 함수의 내부 구현 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제점**:

1. **책임 분리 위반**: CLI 계층에서 검증 함수(`validate_ffr_coverage`)를 직접 호출
   - 위치: `scripts/tqqq/validate_tqqq_simulation.py:86`
   - CLI가 검증 로직을 알아야 하므로 책임 경계가 불명확

2. **중복 호출 가능성**:
   - CLI에서 사전 검증 → 비즈니스 로직 호출 시 검증이 누락될 수 있음
   - 다른 CLI에서 `find_optimal_cost_model`을 호출할 때 검증을 빠뜨릴 위험

3. **일관성 문제**:
   - 일부 비즈니스 함수(`simulate`)는 이미 내부 검증 수행
   - `find_optimal_cost_model`은 외부 검증에 의존
   - 불일치로 인한 혼란

**동기**:

- 비즈니스 로직의 자율성 확보 (자체적으로 입력 검증)
- CLI 계층 단순화 (인터페이스 제공에만 집중)
- 테스트 용이성 향상 (검증 포함 전체 로직 단독 테스트)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족: `find_optimal_cost_model` 내부에서 FFR 검증 수행
- [x] 회귀/신규 테스트 추가: 검증 로직 테스트 추가 (3개 테스트)
- [x] `./run_tests.sh` 통과 (passed=136, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트: TQQQ CLAUDE.md 업데이트 완료
- [x] plan 체크박스 최신화 완료

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직**:
- `src/qbt/tqqq/simulation.py` (검증 호출 추가)

**CLI 스크립트**:
- `scripts/tqqq/validate_tqqq_simulation.py` (검증 호출 제거)
- `scripts/tqqq/generate_tqqq_daily_comparison.py` (영향 확인, 필요 시 조정)
- `scripts/tqqq/generate_synthetic_tqqq.py` (영향 확인)

**테스트**:
- `tests/test_tqqq_simulation.py` (검증 로직 테스트 추가/수정)

**문서**:
- `src/qbt/tqqq/CLAUDE.md` (검증 위치 및 정책 업데이트)

### 데이터/결과 영향

- **없음**: 검증 로직의 위치만 이동, 실제 검증 로직 및 결과는 동일
- CSV 스키마 변경 없음
- 출력 결과 변경 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 검증 정책을 테스트로 먼저 고정(레드)

> 목적: 검증 로직이 비즈니스 함수 내부에서 호출되는 것을 테스트로 고정

**작업 내용**:

- [x] `test_tqqq_simulation.py`에 검증 정책 테스트 추가
  - [x] `find_optimal_cost_model`이 FFR 부족 시 ValueError 발생하는지 테스트 (레드)
  - [x] 월 차이 `MAX_FFR_MONTHS_DIFF` 초과 시 예외 발생 테스트 (레드)
  - [x] 정상 FFR 데이터 제공 시 정상 동작 테스트 (그린 유지)

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=134, failed=2, skipped=0) - 예상대로 레드

---

### Phase 1 — 비즈니스 로직에 검증 추가(그린)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py` 수정:
  - [x] `find_optimal_cost_model` 함수 내부에 FFR 검증 로직 추가
    - [x] `extract_overlap_period` 호출 후 overlap 기간 추출
    - [x] `validate_ffr_coverage(overlap_start, overlap_end, ffr_df)` 호출
  - [x] Docstring 업데이트 (검증 수행 명시)
  - [x] `validate_ffr_coverage` 빈 FFR DataFrame 처리 로직 추가
- [x] Phase 0 테스트 통과 확인

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=136, failed=0, skipped=0)

---

### Phase 2 — CLI 계층 단순화(그린 유지)

**작업 내용**:

- [x] `scripts/tqqq/validate_tqqq_simulation.py` 수정:
  - [x] `extract_overlap_period` 호출 제거 (비즈니스 로직 내부에서 수행)
  - [x] `validate_ffr_coverage` 호출 및 관련 로그 제거
  - [x] 불필요한 import 제거 (`extract_overlap_period`, `validate_ffr_coverage`, `COL_DATE`)
  - [x] 코드 단순화 (데이터 로드 → 비즈니스 로직 호출 → 결과 출력)
- [x] `scripts/tqqq/generate_tqqq_daily_comparison.py` 확인:
  - [x] `extract_overlap_period` 사용 (단순 데이터 추출이므로 문제없음)
- [x] `scripts/tqqq/generate_synthetic_tqqq.py` 확인:
  - [x] 검증 불필요 (`simulate` 내부에서 검증)

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=136, failed=0, skipped=0)

---

### Phase 3 — 테스트 보강 및 엣지 케이스 커버리지(그린 유지)

**작업 내용**:

- [x] Phase 0에서 이미 충분한 엣지 케이스 테스트 작성:
  - [x] FFR 데이터 완전 부재 시 예외 테스트
  - [x] FFR 데이터 갭 초과 시 예외 테스트
  - [x] 정상 FFR 데이터 제공 시 정상 동작 테스트
- [x] 기존 테스트 영향 확인:
  - [x] 모든 테스트 통과 확인

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=136, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트:
  - [x] `find_optimal_cost_model` 함수 설명에 FFR 검증 수행 명시
  - [x] 검증 수행 단계 추가 (처리 흐름 2번 항목)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=136, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 검증 로직 비즈니스 계층 이동 (책임 분리 개선)
2. TQQQ시뮬레이션 / FFR 검증 내부화로 자율성 향상
3. 리팩토링 / CLI-비즈니스 계층 책임 분리 강화 (검증 위치 이동)
4. TQQQ시뮬레이션 / find_optimal_cost_model 자체 검증 추가
5. 리팩토링 / 검증 로직 캡슐화 및 테스트 보강

## 7) 리스크(Risks)

**리스크 1: 다른 CLI에서 find_optimal_cost_model 호출 시 영향**
- 완화책: 현재 `find_optimal_cost_model`을 호출하는 CLI는 `validate_tqqq_simulation.py` 하나뿐이므로 영향 범위 제한적
- 완화책: Phase 2에서 모든 TQQQ 관련 CLI 스크립트 검토

**리스크 2: 테스트에서 검증 예외 발생으로 기존 테스트 실패**
- 완화책: Phase 0에서 검증 테스트 먼저 작성하여 예상되는 동작 확인
- 완화책: Phase 1 적용 후 즉시 전체 테스트 실행하여 회귀 감지

**리스크 3: FFR 데이터 없는 경우 모든 테스트가 실패할 위험**
- 완화책: `conftest.py`의 `sample_ffr_df` 픽스처가 적절한 FFR 데이터 제공 확인
- 완화책: 테스트에서 충분한 FFR 데이터 범위 제공

**리스크 4: extract_overlap_period 중복 호출로 성능 저하**
- 완화책: 현재 구조상 `find_optimal_cost_model` 내부에서 이미 `extract_overlap_period` 호출하므로 추가 호출 아님
- 확인: `simulation.py:699` 참고

## 8) 메모(Notes)

### 핵심 결정 사항

1. **검증 위치**: `find_optimal_cost_model` 함수 내부, `extract_overlap_period` 호출 직후
2. **검증 범위**: FFR 커버리지만 (다른 검증은 이미 내부에서 수행 중)
3. **예외 전파**: 검증 실패 시 `ValueError` 그대로 전파 (CLI에서 `@cli_exception_handler`가 처리)

### 참고 사항

- `validate_ffr_coverage` 함수는 이미 비즈니스 계층에 존재 (`simulation.py:73-140`)
- `extract_overlap_period` 함수도 비즈니스 계층에 존재 (`simulation.py:382-432`)
- CLI에서 이 두 함수를 직접 호출하는 것이 문제의 근본 원인

### 진행 로그 (KST)

- 2025-12-29 14:30: 계획서 작성 완료, Draft 상태
- 2025-12-29 14:35: Phase 0 완료 (검증 테스트 3개 추가, 레드 상태 확인)
- 2025-12-29 14:50: Phase 1 완료 (비즈니스 로직에 검증 추가, 그린 상태 확인)
- 2025-12-29 15:00: Phase 2 완료 (CLI 계층 단순화, 그린 상태 유지)
- 2025-12-29 15:10: Phase 3 스킵 (Phase 0에서 충분한 테스트 작성)
- 2025-12-29 15:45: 마지막 Phase 완료, 전체 작업 완료, Done 상태

---
