# Implementation Plan: 테스트 코드 상수 사용 정리

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

**작성일**: 2025-12-30 09:00
**마지막 업데이트**: 2025-12-30 09:30
**관련 범위**: tests
**관련 문서**: tests/CLAUDE.md, src/qbt/tqqq/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 내부 계약(컬럼명, 거래일수 등)을 검증하는 테스트에서 하드코딩된 값을 프로덕션 상수로 교체
- [x] 외부 스키마 검증 테스트는 리터럴 유지 및 주석으로 의도 명시
- [x] 테스트 코드의 오타/드리프트 취약성 제거 및 회귀 탐지 능력 강화

## 2) 비목표(Non-Goals)

- 프로덕션 코드(src/qbt/) 수정은 포함하지 않음 (상수 구조는 이미 적절함)
- 테스트의 검증 로직이나 assert 조건 변경은 포함하지 않음 (동작 유지)
- 새로운 테스트 추가는 포함하지 않음 (기존 테스트 개선만)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제점**:
- 테스트 코드에 `"DATE"`, `"VALUE"`, `252` 같은 값이 하드코딩되어 있어 오타/드리프트에 취약함
- 프로덕션 상수가 변경되어도 테스트가 독립적으로 통과하여 회귀를 놓칠 수 있음

**동기**:
- 내부 계약(프로젝트 내부에서 의미가 고정된 상수)은 프로덕션 상수와 동기화되어야 회귀 탐지 가능
- 외부 스키마 검증(원본 CSV 컬럼명 검증 등)은 리터럴을 유지하여 상수 변경에도 회귀 탐지 가능

**원칙**:
1. **내부 계약**: 프로덕션 상수 import로 사용 (예: `COL_FFR_DATE`, `TRADING_DAYS_PER_YEAR`)
2. **외부 스키마 검증**: 리터럴 유지 + "원본 스키마 회귀 탐지 목적" 주석 추가
3. **샘플 데이터 값**: 가독성 위해 리터럴 유지 허용

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `tests/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/common_constants.py` (상수 정의)
- `src/qbt/tqqq/constants.py` (TQQQ 도메인 상수 정의)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 내부 계약 검증 테스트에서 하드코딩 제거 (컬럼명, 거래일수)
- [x] 외부 스키마 검증 테스트에 회귀 탐지 목적 주석 추가
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=154, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(필요 시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**테스트 파일**:
- `tests/test_tqqq_simulation.py` — `calculate_daily_cost` 관련 테스트에서 `252` → `TRADING_DAYS_PER_YEAR` 교체
- `tests/test_tqqq_data_loader.py` — 외부 스키마 검증 테스트에 주석 추가
- `tests/conftest.py` — 픽스처에서 사용하는 컬럼명 상수 교체 검토 (필요 시)

### 데이터/결과 영향

- 출력 스키마 변경: 없음
- 기존 결과 비교 필요: 없음 (테스트 로직 동작 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — 테스트 코드 상수 교체 및 검증 (그린 유지)

**작업 내용**:

- [x] `tests/test_tqqq_simulation.py` 분석:
  - `test_calculate_daily_cost_leverage_2`, `test_calculate_daily_cost_leverage_4`에서 `252` → `qbt.common_constants.TRADING_DAYS_PER_YEAR` 교체
  - `"DATE"`, `"VALUE"` 하드코딩 → `qbt.tqqq.constants.COL_FFR_DATE`, `COL_FFR_VALUE` 등 상수 교체 (내부 계약 검증 목적)
- [x] `tests/test_tqqq_data_loader.py` 분석:
  - `load_ffr_data`, `load_expense_ratio_data` 테스트에서 `"DATE"`, `"VALUE"` 리터럴 유지
  - 원본 스키마 검증 목적 주석 추가 (예: "원본 CSV 스키마 회귀 탐지를 위해 리터럴 유지")
- [x] `tests/conftest.py` 분석:
  - `sample_ffr_df`, `sample_expense_df` 픽스처의 컬럼명 검토
  - 외부 스키마 시뮬레이션 목적으로 리터럴 유지, 주석 추가
- [x] import 최소화: 필요한 상수만 추가 import

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (없음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 전체 테스트 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / 내부 계약 검증 테스트의 하드코딩을 프로덕션 상수로 교체 (회귀 탐지 강화)
2. 테스트 / 상수 사용 정리 - 내부 계약 vs 외부 스키마 검증 구분 명확화
3. 테스트 / 컬럼명 및 거래일수 하드코딩 제거, 오타/드리프트 취약성 개선
4. 테스트 / TRADING_DAYS_PER_YEAR 등 프로덕션 상수 사용으로 일관성 강화
5. 테스트 / 외부 스키마 검증 의도 주석 추가 및 내부 계약 상수 교체

## 7) 리스크(Risks)

- **낮음**: 테스트 로직 동작은 동일하므로 회귀 위험 없음
- **import 추가**: 순환 임포트 없음 (테스트는 프로덕션 코드 import, 역방향 없음)
- **상수 오류**: 잘못된 상수 사용 시 테스트 실패로 즉시 탐지 가능

## 8) 메모(Notes)

### 구체적 수정 예시

**Before** (`test_calculate_daily_cost_leverage_2`):
```python
expected_daily_cost = expected_annual_cost / 252
```

**After**:
```python
from qbt.common_constants import TRADING_DAYS_PER_YEAR

expected_daily_cost = expected_annual_cost / TRADING_DAYS_PER_YEAR
```

**Before** (`test_tqqq_data_loader.py`):
```python
ffr_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.045]})
```

**After** (내부 계약 검증 목적이면):
```python
from qbt.tqqq.constants import COL_FFR_DATE, COL_FFR_VALUE

ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
```

**After** (외부 스키마 검증 목적이면):
```python
# 원본 CSV 스키마 회귀 탐지를 위해 리터럴 유지
ffr_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.045]})
```

### 진행 로그 (KST)

- 2025-12-30 09:00: 계획서 초안 작성 완료
- 2025-12-30 09:10: Phase 1 작업 완료 - test_tqqq_simulation.py 상수 교체 (252 → TRADING_DAYS_PER_YEAR, "DATE"/"VALUE" → 상수)
- 2025-12-30 09:15: test_tqqq_data_loader.py 외부 스키마 검증 주석 추가
- 2025-12-30 09:18: conftest.py 픽스처 주석 추가 (리터럴 유지 목적 명시)
- 2025-12-30 09:20: Validation 통과 (ruff, tests: 154 passed, 0 failed, 0 skipped)
- 2025-12-30 09:25: Black 자동 포맷 적용 및 최종 검증 완료
- 2025-12-30 09:30: 계획서 업데이트 완료, 상태 Done으로 변경

---
