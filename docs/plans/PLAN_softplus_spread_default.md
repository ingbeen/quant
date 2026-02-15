# Implementation Plan: Softplus 동적 스프레드를 기본 비용 모델로 반영

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-15 16:00
**마지막 업데이트**: 2026-02-15 17:00
**관련 범위**: tqqq, scripts, constants, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 목표 1: `generate_daily_comparison.py`가 softplus 동적 스프레드 모델 `(a=-6.1, b=0.37)`을 사용하여 일별 비교 CSV를 생성하도록 변경
- [x] 목표 2: `tune_cost_model.py` (고정 spread 그리드 서치 스크립트) 제거
- [x] 목표 3: softplus 기본 파라미터 `(a, b)`를 상수로 정의하여 재사용 가능하게 관리

## 2) 비목표(Non-Goals)

- `generate_synthetic.py`의 spread 모델 변경 (별도 작업으로 분리)
- `simulate()` 함수의 기본 파라미터(`funding_spread`) 시그니처 변경
- `find_optimal_cost_model()` 함수 제거 (기존 테스트 유지, 유틸로 존속)
- `DEFAULT_FUNDING_SPREAD` 상수 제거 (`simulate()` 기본값 및 `generate_synthetic.py`에서 사용 중)
- `tqqq_validation.csv` 삭제 (기존 이력 데이터로 보존)
- `app_daily_comparison.py` UI 변경 (CSV를 읽어서 표시하므로 자동으로 반영됨)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `generate_daily_comparison.py`는 고정 스프레드(`DEFAULT_FUNDING_SPREAD = 0.0034`)를 사용하여 TQQQ를 시뮬레이션함
- 과최적화 진단(완전 고정 a,b 워크포워드) 결과, softplus 모델 `(a=-6.1, b=0.37)`이 고정 스프레드보다 우수함이 확인됨:
  - IS-OOS 격차: 0.31%p (< 0.5%p 기준) → 과최적화 아님
  - RMSE 순서: 고정(1.36%) < b고정(2.12%) < 동적(2.92%) → 고정 모델이 가장 안정적
  - 기존 고정 스프레드 RMSE: 2.01% → softplus RMSE: 1.05% (약 48% 개선)
- `tune_cost_model.py`는 고정 스프레드 최적화 스크립트로, softplus 도입으로 역할이 `tune_softplus_params.py`로 완전 대체됨

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `CLAUDE.md` (루트)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `generate_daily_comparison.py`가 softplus spread map을 사용하여 시뮬레이션 실행
- [x] `tune_cost_model.py` 파일 삭제
- [x] `DEFAULT_SOFTPLUS_A`, `DEFAULT_SOFTPLUS_B` 상수가 `constants.py`에 정의됨
- [x] `build_monthly_spread_map`이 `__init__.py`에서 export됨
- [x] 메타데이터에 softplus 파라미터 (a, b) 기록
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=274, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (README, CLAUDE.md, scripts/CLAUDE.md, src/qbt/tqqq/CLAUDE.md)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/constants.py` — `DEFAULT_SOFTPLUS_A`, `DEFAULT_SOFTPLUS_B` 상수 추가, `TQQQ_VALIDATION_PATH` 제거
- `src/qbt/tqqq/__init__.py` — `build_monthly_spread_map` export 추가
- `scripts/tqqq/generate_daily_comparison.py` — softplus spread map 사용으로 변경
- `scripts/tqqq/tune_cost_model.py` — 파일 삭제
- `tests/test_meta_manager.py` — `tqqq_validation` → `tqqq_daily_comparison`으로 테스트 조정
- `src/qbt/utils/meta_manager.py` — `tqqq_validation` CSV 타입 제거
- `README.md` — `tune_cost_model.py` 참조 제거, 워크플로우 번호 재정리
- `scripts/CLAUDE.md` — `tune_cost_model.py` 참조 제거
- `src/qbt/tqqq/CLAUDE.md` — 비용 모델 설명 갱신, `tqqq_validation.csv` 섹션 제거
- `CLAUDE.md` (루트) — `tqqq_validation.csv` 참조 제거

### 데이터/결과 영향

- `tqqq_daily_comparison.csv` — softplus 기반으로 재생성됨 (RMSE 2.01% → ~1.05% 예상)
- `tqqq_validation.csv` — 더 이상 재생성되지 않으나 기존 파일 보존
- `meta.json` — `tqqq_daily_comparison` 항목에 `softplus_a`, `softplus_b` 파라미터 추가, `funding_spread` 고정값 제거

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 추가 및 export 정리

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 `DEFAULT_SOFTPLUS_A = -6.1`, `DEFAULT_SOFTPLUS_B = 0.37` 추가
- [x] `src/qbt/tqqq/constants.py`의 `__all__`에 새 상수 추가
- [x] `src/qbt/tqqq/__init__.py`에 `build_monthly_spread_map` export 추가

---

### Phase 2 — generate_daily_comparison.py 변경

**작업 내용**:

- [x] `generate_daily_comparison.py`에서 `DEFAULT_FUNDING_SPREAD` 대신 softplus spread map 사용
  - FFR 데이터로 `build_monthly_spread_map(ffr_df, DEFAULT_SOFTPLUS_A, DEFAULT_SOFTPLUS_B)` 호출
  - `simulate()`의 `funding_spread` 파라미터에 spread map (dict) 전달
- [x] 로그 출력 변경: 고정 spread 표시 → softplus (a, b) 표시
- [x] 메타데이터 변경: `funding_spread` → `softplus_a`, `softplus_b`, `funding_spread_mode: "softplus"`

---

### Phase 3 — tune_cost_model.py 제거 및 정리

**작업 내용**:

- [x] `scripts/tqqq/tune_cost_model.py` 파일 삭제
- [x] `src/qbt/utils/meta_manager.py`의 `VALID_CSV_TYPES`에서 `"tqqq_validation"` 제거
- [x] `tests/test_meta_manager.py`에서 `tqqq_validation` 참조를 `tqqq_daily_comparison`으로 조정
- [x] `src/qbt/tqqq/constants.py`에서 `TQQQ_VALIDATION_PATH` 제거 (`tune_cost_model.py`에서만 사용)
  - `DEFAULT_SPREAD_RANGE`, `DEFAULT_SPREAD_STEP`, `MAX_TOP_STRATEGIES`는 `simulation.py`의 `find_optimal_cost_model()`에서 사용되므로 유지
- [x] `find_optimal_cost_model` export 유지 (테스트에서 사용 중)

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` 업데이트: `tune_cost_model.py` 참조 제거, 워크플로우 번호 재정리
- [x] `scripts/CLAUDE.md` 업데이트: `tune_cost_model.py` 항목 제거
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트: 비용 모델 설명을 softplus 기반으로 갱신
- [x] `CLAUDE.md` (루트) 업데이트: `tqqq_validation.csv` 참조 제거
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=274, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / softplus 동적 스프레드를 기본 비용 모델로 적용하고 고정 스프레드 탐색 스크립트 제거
2. TQQQ시뮬레이션 / 과최적화 검증된 softplus (a,b) 파라미터를 일별 비교 파이프라인에 반영
3. TQQQ시뮬레이션 / 비용 모델을 고정 스프레드에서 softplus 동적 스프레드로 전환
4. TQQQ시뮬레이션 / softplus 모델 반영 및 tune_cost_model 제거로 비용 모델 파이프라인 정리
5. TQQQ시뮬레이션 / 금리 연동 softplus 스프레드 적용으로 추적 오차 개선 (RMSE 2.01→1.05%)

## 7) 리스크(Risks)

- `generate_synthetic.py`가 여전히 고정 스프레드를 사용하므로 합성 데이터와 일별 비교 데이터 간 비용 모델 불일치 → 비목표로 명시하여 별도 작업으로 분리
- `find_optimal_cost_model()` 함수와 관련 테스트가 남아있으나 호출하는 CLI 스크립트가 없음 → 테스트 자체는 유지하되 향후 정리 가능
- `tqqq_validation.csv`가 더 이상 재생성되지 않음 → 기존 파일 보존하여 이력 확인 가능

## 8) 메모(Notes)

### 핵심 수치 (변경 전 → 변경 후 예상)

| 지표 | 변경 전 (고정 0.0034) | 변경 후 (softplus a=-6.1, b=0.37) |
|------|----------------------|----------------------------------|
| RMSE | 2.01% | ~1.05% |
| 평균 | 1.72% | 낮아질 것 |
| 최대 | 6.32% | 낮아질 것 |

### 이력 보존

- `meta.json`이 실행 이력을 배열로 자동 누적하므로, 변경 전 수치는 이전 실행 기록에 보존됨
- `tqqq_validation.csv`는 삭제하지 않고 보존

### 진행 로그 (KST)

- 2026-02-15 16:00: 계획서 작성
- 2026-02-15 17:00: 전체 Phase 완료, validate_project.py 통과 (274 passed, 0 failed, 0 skipped)

---
