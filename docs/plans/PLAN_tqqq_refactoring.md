# Implementation Plan: TQQQ 도메인 리팩토링

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

**작성일**: 2026-03-11 15:00
**마지막 업데이트**: 2026-03-11 16:30
**관련 범위**: tqqq, scripts, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/archive/tqqq_removed_modules.md`
**선행 계획서**: `docs/plans/PLAN_tqqq_spread_lab_cleanup.md` (완료, 참고용)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] Dead Code 삭제: 이전 cleanup 이후 프로덕션에서 미사용되는 함수 2개 제거 (`calculate_metrics_fast`, `generate_static_spread_series`)
- [x] 모듈 통합: `types.py` → `simulation.py` 인라인 통합 (파일 삭제)
- [x] 접근 제어 정리: 내부 전용 함수 private 전환 (`compute_softplus_spread`, `validate_ffr_coverage`, `create_monthly_data_dict`, `lookup_monthly_data`)
- [x] 앱 전용 함수 분리: `analysis_helpers.py`의 spread_lab 앱 전용 함수를 `spread_lab_helpers.py`로 분리
- [x] 타입 축소: `FundingSpreadSpec`에서 미사용 `Callable` 타입 제거
- [x] 상수 정리: `DEFAULT_FUNDING_SPREAD` 삭제, `__all__` 제거, `INTEGRITY_TOLERANCE` 이동, `DEFAULT_TOP_N_CROSS_VALIDATION` 앱 전용으로 이동
- [x] 코드 품질: 학습 포인트 주석 정리, 삭제된 스크립트 참조 docstring 수정

## 2) 비목표(Non-Goals)

- `_resolve_spread()` 내부 검증 로직 변경 (방어적 코드 유지)
- `simulation.py` 핵심 시뮬레이션 로직 변경 (동작 동일 리팩토링)
- `visualization.py` 변경
- 스크립트(`generate_synthetic.py`, `generate_daily_comparison.py`, `app_daily_comparison.py`) 로직 변경
- 결과 CSV 파일 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 이전 cleanup(PLAN_tqqq_spread_lab_cleanup.md)에서 optimization.py, walkforward.py를 삭제했으나 그 전용 함수/상수가 잔여물로 남아 있다
- `calculate_metrics_fast()`는 삭제된 그리드 서치 전용, `generate_static_spread_series()`는 삭제된 튜닝 스크립트 전용으로 프로덕션에서 미사용 (테스트에서만 호출)
- `types.py`에 TypedDict 1개만 존재하여 별도 파일 유지 의미가 없다
- `analysis_helpers.py`의 `prepare_monthly_data`, `add_rate_change_lags`는 spread_lab 앱에서만 호출되는 앱 전용 함수이다
- `FundingSpreadSpec`의 `Callable` 타입은 사용처 없이 복잡성만 증가시킨다
- `data_loader.py`의 제네릭 함수(`create_monthly_data_dict`, `lookup_monthly_data`)가 공개 API로 노출되어 있으나 내부 래퍼 전용이다
- simulation.py에 교육용 "학습 포인트" 주석이 다수 존재하여 가독성 저하

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] Dead Code 함수 2개 삭제 + 관련 테스트 삭제 완료
- [x] types.py → simulation.py 인라인 통합 + types.py 파일 삭제 완료
- [x] 내부 전용 함수 4개 private 전환 완료
- [x] spread_lab_helpers.py 신규 파일 생성 + 앱 전용 함수 2개 이동 완료
- [x] FundingSpreadSpec에서 Callable 제거 완료
- [x] 상수 정리 완료 (DEFAULT_FUNDING_SPREAD 삭제, __all__ 제거, INTEGRITY_TOLERANCE 이동, DEFAULT_TOP_N_CROSS_VALIDATION 이동)
- [x] 학습 포인트 주석 정리 + docstring 수정 완료
- [x] 관련 테스트 수정/이동 완료 (import 경로, 삭제 함수 테스트)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] CLAUDE.md 파일들 갱신 완료 (tqqq, tests)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 삭제 대상 파일

- `src/qbt/tqqq/types.py` (simulation.py로 인라인 이동)

### 신규 생성 파일

- `src/qbt/tqqq/spread_lab_helpers.py` (앱 전용 분석 함수)
- `tests/test_tqqq_spread_lab_helpers.py` (이동된 함수의 테스트)

### 수정 대상 파일

소스:

- `src/qbt/tqqq/simulation.py`: Dead Code 삭제, private 전환, types 인라인, FundingSpreadSpec 축소, 주석 정리
- `src/qbt/tqqq/data_loader.py`: 제네릭 함수 private 전환, `lookup_funding_spread` 신규 추가
- `src/qbt/tqqq/analysis_helpers.py`: 앱 전용 함수 2개 제거 (spread_lab_helpers.py로 이동)
- `src/qbt/tqqq/constants.py`: `__all__` 제거, `INTEGRITY_TOLERANCE` 추가, `DEFAULT_FUNDING_SPREAD` 삭제, `DEFAULT_TOP_N_CROSS_VALIDATION` 삭제
- `src/qbt/tqqq/__init__.py`: types.py import 제거 확인

스크립트:

- `scripts/tqqq/spread_lab/app_rate_spread_lab.py`: import 경로 변경 + docstring 수정 + `DEFAULT_TOP_N_CROSS_VALIDATION` 로컬 상수화

테스트:

- `tests/test_tqqq_simulation.py`: 삭제 함수 테스트 제거, import 경로 수정 (private 함수, ValidationMetricsDict)
- `tests/test_tqqq_data_loader.py`: import 경로 수정 (private 함수)
- `tests/test_tqqq_analysis_helpers.py`: 이동 함수 테스트 제거

문서:

- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`

### 데이터/결과 영향

- 없음 (순수 리팩토링, 동작 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — simulation.py 핵심 정리 + types.py 통합

**작업 내용**:

- [x] `types.py`의 `ValidationMetricsDict`를 `simulation.py` 상단에 인라인 정의, `types.py` 파일 삭제
- [x] `calculate_metrics_fast()` 함수 삭제
- [x] `generate_static_spread_series()` 함수 + `COL_STATIC_*` 로컬 상수 5개 삭제
- [x] `compute_softplus_spread()` → `_compute_softplus_spread()` private 전환
- [x] `validate_ffr_coverage()` → `_validate_ffr_coverage()` private 전환
- [x] `FundingSpreadSpec`에서 `Callable` 타입 제거 (`float | dict[str, float]`로 축소)
- [x] `DEFAULT_FUNDING_SPREAD` 삭제: `simulate()` 함수의 `funding_spread` 매개변수 기본값 제거 (필수 인자로 변경)
- [x] `INTEGRITY_TOLERANCE` → `constants.py`로 이동, `simulation.py`에서는 import
- [x] 학습 포인트 주석 (`# 학습 포인트: ...`) 정리
- [x] `_resolve_spread()`의 `Callable` 분기 제거 (방어적 검증은 유지)
- [x] `tests/test_tqqq_simulation.py` 수정:
  - 삭제 함수 테스트 제거 (`calculate_metrics_fast`, `generate_static_spread_series`)
  - import 경로 수정 (`_compute_softplus_spread`, `_validate_ffr_coverage`, `ValidationMetricsDict`)
  - `DEFAULT_FUNDING_SPREAD` 기본값에 의존하는 테스트에 명시적 `funding_spread` 전달
- [x] `tests/test_integration.py` 확인: `simulate()` 호출 시 `funding_spread` 명시적 전달 여부 확인/수정

---

### Phase 2 — data_loader.py + analysis_helpers.py 모듈 재구성

**작업 내용**:

- [x] `data_loader.py`: `create_monthly_data_dict` → `_create_monthly_data_dict` private 전환
- [x] `data_loader.py`: `lookup_monthly_data` → `_lookup_monthly_data` private 전환
- [x] `data_loader.py`: `lookup_funding_spread()` 신규 공개 함수 추가 (`_lookup_monthly_data` 래퍼, MAX_FFR_MONTHS_DIFF, "funding_spread")
- [x] `simulation.py`: `_resolve_spread()`에서 `lookup_monthly_data` → `lookup_funding_spread` 호출로 변경, import 수정
- [x] `spread_lab_helpers.py` 신규 파일 생성: `prepare_monthly_data`, `add_rate_change_lags` 이동 (analysis_helpers.py에서 import하여 사용)
- [x] `analysis_helpers.py`: `prepare_monthly_data`, `add_rate_change_lags` 함수 제거
- [x] `app_rate_spread_lab.py`: import 경로 변경 (`analysis_helpers` → `spread_lab_helpers`), docstring에서 삭제된 스크립트 참조 제거
- [x] `tests/test_tqqq_spread_lab_helpers.py` 신규 파일 생성: `test_tqqq_analysis_helpers.py`에서 해당 함수 테스트 이동
- [x] `tests/test_tqqq_analysis_helpers.py`: 이동된 함수 테스트 제거
- [x] `tests/test_tqqq_data_loader.py`: import 경로 수정 (`_create_monthly_data_dict`, `_lookup_monthly_data`)

---

### Phase 3 (마지막) — constants.py 정리 + 문서 갱신 + 최종 검증

**작업 내용**

- [x] `constants.py`: `__all__` 블록 제거
- [x] `constants.py`에서 `DEFAULT_TOP_N_CROSS_VALIDATION` 삭제, `app_rate_spread_lab.py` 상단에 로컬 상수로 이동
- [x] `src/qbt/tqqq/CLAUDE.md` 갱신: types.py 제거, spread_lab_helpers.py 추가, 함수 목록 갱신
- [x] `tests/CLAUDE.md` 갱신: test_tqqq_spread_lab_helpers.py 추가
- [x] `poetry run black .` 실행
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=346, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Dead Code 삭제 + 모듈 재구성 리팩토링 (동작 동일)
2. TQQQ시뮬레이션 / types.py 통합, 미사용 함수 삭제, 앱 전용 모듈 분리
3. TQQQ시뮬레이션 / 리팩토링 — 접근 제어 정리 + 모듈 분리 + Dead Code 제거
4. TQQQ시뮬레이션 / 코드 정리 (미사용 함수 삭제, private 전환, spread_lab 분리)
5. TQQQ시뮬레이션 / 모듈 경량화 및 책임 분리 (types 통합, 앱 전용 함수 분리)

## 7) 리스크(Risks)

- **simulate() 기본값 제거**: `DEFAULT_FUNDING_SPREAD` 삭제로 `funding_spread`가 필수 인자가 됨. 기존 기본값에 의존하는 테스트가 있으면 수정 필요. 대응: grep으로 모든 simulate() 호출처를 확인하여 명시적 인자 전달 보장
- **private 전환 시 테스트 import 오류**: private 함수명 변경으로 기존 테스트의 import가 깨질 수 있음. 대응: 각 변경 대상 함수를 grep하여 모든 import 위치를 사전에 파악하고 일괄 수정
- **spread_lab_helpers.py 분리 시 순환 import**: 새 모듈이 analysis_helpers.py를 import하면서 순환 의존 발생 가능성. 대응: spread_lab_helpers → analysis_helpers 단방향 의존만 허용, 역방향 import 금지

## 8) 메모(Notes)

- 순수 리팩토링: 모든 변경은 동작 동일. 비즈니스 로직, 시뮬레이션 결과, CSV 출력에 영향 없음
- Phase 0 불필요: 핵심 인바리언트/정책 변경 없음 (기존 테스트가 동작 보장)
- `_resolve_spread()` 내부 검증(NaN, inf, 0 이하)은 사용자 요청에 따라 유지
- `lookup_funding_spread` 신규 추가: 기존 `lookup_ffr`, `lookup_expense` 패턴과 동일한 특화 래퍼

### 진행 로그 (KST)

- 2026-03-11 15:00: 계획서 초안 작성
- 2026-03-11 15:30: Phase 1 완료 (simulation.py 핵심 정리 + types.py 통합)
- 2026-03-11 16:00: Phase 2 완료 (data_loader.py + analysis_helpers.py 모듈 재구성)
- 2026-03-11 16:30: Phase 3 완료 (constants.py 정리 + 문서 갱신 + 최종 검증 통과)

---
