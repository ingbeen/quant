# Implementation Plan: CSV VALUE 값 소수화 (퍼센트 → 0~1 비율)

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

**작성일**: 2025-12-29 20:31
**마지막 업데이트**: 2025-12-29 20:52
**관련 범위**: tqqq, utils, scripts, tests, docs
**관련 문서**:
- src/qbt/tqqq/CLAUDE.md
- src/qbt/utils/CLAUDE.md
- scripts/CLAUDE.md
- tests/CLAUDE.md

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

- [x] 목표 1: `federal_funds_rate_monthly.csv`의 VALUE 값을 퍼센트에서 0~1 비율로 변환 (예: 4.63 → 0.0463)
- [x] 목표 2: `tqqq_net_expense_ratio_monthly.csv`의 VALUE 값을 퍼센트에서 0~1 비율로 변환 (예: 0.95 → 0.0095)
- [x] 목표 3: 데이터 형식 변경에 따른 모든 관련 코드, 테스트, 문서 최신화

## 2) 비목표(Non-Goals)

- 비용 계산 로직 자체의 수식 변경 (형식만 변경, 계산 로직은 동일)
- 다른 CSV 파일의 스키마 변경
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 상태**:
- `federal_funds_rate_monthly.csv`: VALUE가 `4.63` (= 4.63%)
- `tqqq_net_expense_ratio_monthly.csv`: VALUE가 `0.95` (= 0.95%)

**변경 이유**:
- 프로젝트 전체의 "비율 표기 규칙"은 0~1 사이 소수로 통일 (`CLAUDE.md` 참고)
- 현재 FFR과 Expense CSV는 퍼센트 값으로 저장되어 규칙과 불일치
- 코드에서 `/ 100` 변환 로직이 필요하여 혼란 및 실수 가능성 증가

**변경 목표**:
- CSV VALUE 값을 0~1 비율로 저장 (FFR: 4.63 → 0.0463, Expense: 0.95 → 0.0095)
- 코드에서 `/100` 변환 제거, 직접 사용 가능하도록 단순화
- 프로젝트 전체 비율 표기 규칙과 일치

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] CSV 파일 2개 VALUE 값 변환 완료
- [x] 관련 코드 (데이터 로더, 시뮬레이션) 수정 완료
- [x] 회귀/신규 테스트 추가 및 수정
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=154, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(CLAUDE.md, 주석 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**데이터 파일**:
- `storage/etc/federal_funds_rate_monthly.csv`
- `storage/etc/tqqq_net_expense_ratio_monthly.csv`

**비즈니스 로직**:
- `src/qbt/tqqq/data_loader.py` (데이터 로딩 후 변환 로직 제거 확인)
- `src/qbt/tqqq/simulation.py` (비용 계산 로직에서 `/100` 제거 가능성 확인)

**테스트**:
- `tests/test_tqqq_data_loader.py` (픽스처 및 검증 로직 업데이트)
- `tests/test_tqqq_simulation.py` (FFR/Expense 테스트 데이터 업데이트)
- `tests/conftest.py` (공통 픽스처 업데이트 가능성)

**스크립트** (영향 확인 필요):
- `scripts/tqqq/validate_tqqq_simulation.py`
- `scripts/tqqq/generate_synthetic_tqqq.py`
- `scripts/tqqq/generate_tqqq_daily_comparison.py`

**문서**:
- `src/qbt/tqqq/CLAUDE.md` (데이터 형식 설명 업데이트)
- 관련 코드의 주석 (퍼센트 표기 → 비율 표기)

### 데이터/결과 영향

- **CSV 스키마 변경**: VALUE 값의 스케일이 변경됨 (퍼센트 → 0~1 비율)
- **기존 결과 재생성 필요**: 변경 후 검증 스크립트 실행하여 결과 일치 확인
  - `tqqq_validation.csv`
  - `tqqq_daily_comparison.csv`
  - `TQQQ_synthetic_max.csv`

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 핵심 인바리언트: CSV VALUE 값이 0~1 비율로 저장되어야 하며, 코드에서 추가 변환 없이 직접 사용 가능해야 함

**작업 내용**:

- [x] 기존 테스트 중 FFR/Expense 값 검증 로직 파악
- [x] CSV 형식 변경 후 예상되는 테스트 실패 지점 파악
- [x] 필요시 새로운 검증 테스트 추가 (VALUE 범위 검증: 0~1 사이)
- [x] 문서화: `src/qbt/tqqq/CLAUDE.md`에 새로운 데이터 형식 명시

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

---

### Phase 1 — CSV 데이터 변환 및 코드 수정(그린 유지)

**작업 내용**:

- [x] `federal_funds_rate_monthly.csv` VALUE 값 변환 (전체 행: VALUE / 100)
- [x] `tqqq_net_expense_ratio_monthly.csv` VALUE 값 변환 (전체 행: VALUE / 100)
- [x] 백업 파일 생성 확인 (변환 전 원본 보존)
- [x] `src/qbt/tqqq/data_loader.py` 검토 및 수정 (필요시)
  - `load_ffr_data()`, `load_expense_ratio_data()` 함수에서 `/100` 변환 로직 제거
- [x] `src/qbt/tqqq/simulation.py` 검토 및 수정 (필요시)
  - `calculate_daily_cost()` 등에서 `/100` 변환 제거
- [x] 관련 주석 업데이트 (퍼센트 → 비율 표기)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=151, failed=3, skipped=0)

---

### Phase 2 — 테스트 업데이트 및 검증(그린 유지)

**작업 내용**:

- [x] `tests/conftest.py` 픽스처 업데이트
  - `sample_ffr_df`: VALUE 값을 0~1 비율로 변경
  - `sample_expense_df` (있다면): VALUE 값을 0~1 비율로 변경
- [x] `tests/test_tqqq_data_loader.py` 업데이트
  - FFR/Expense 로더 테스트의 예상값 수정
  - VALUE 범위 검증 테스트 추가 (0~1 사이)
- [x] `tests/test_tqqq_simulation.py` 업데이트
  - 비용 계산 테스트의 FFR/Expense 값 수정
  - 예상 결과 재계산 및 업데이트
- [x] 스크립트 영향 확인 및 수정 (필요시)
  - `validate_tqqq_simulation.py`, `generate_synthetic_tqqq.py`, `generate_tqqq_daily_comparison.py`

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

---

### Phase 3 — 결과 재생성 및 검증(그린 유지)

**작업 내용**:

- [x] 기존 결과 CSV 백업 생성
  - `tqqq_validation.csv`, `tqqq_daily_comparison.csv`, `TQQQ_synthetic_max.csv`
- [x] 검증 스크립트 실행: `poetry run python scripts/tqqq/validate_tqqq_simulation.py`
- [x] 일별 비교 데이터 생성: `poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py`
- [x] 결과 비교: 백업 vs 새 결과 (값 일치 확인)
  - 주요 지표 (RMSE, 누적 수익률 등) 동일성 검증
  - 참고: `tqqq_validation.csv`는 expense 컬럼이 제거되어 구조가 달라짐 (동적 expense 사용)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)
- [x] 결과 CSV 비교 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - "데이터 요구사항" 섹션에 VALUE 형식 명시 (0~1 비율)
  - 비용 구조 설명 업데이트 (퍼센트 → 비율 표기)
- [x] 코드 주석 최종 검토 (퍼센트 표기가 남아있는지 확인)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / FFR·Expense CSV 값 소수화 (퍼센트→비율, 프로젝트 규칙 통일)
2. TQQQ시뮬레이션 / 데이터 형식 일관성 개선 (CSV VALUE 0~1 비율로 변경)
3. TQQQ시뮬레이션 / 비용 데이터 스키마 변경 (퍼센트→소수, 변환 로직 제거)
4. TQQQ시뮬레이션 / FFR·Expense 데이터 정규화 (비율 표기 규칙 준수)
5. TQQQ시뮬레이션 / CSV VALUE 스케일 변경 및 코드 단순화

## 7) 리스크(Risks)

**리스크 1: 데이터 변환 중 정밀도 손실**
- 완화책: 변환 시 충분한 소수점 자리 유지 (최소 4자리), 백업 파일 생성

**리스크 2: 기존 결과와의 차이 발생**
- 완화책: 변환 전후 결과 비교, 주요 지표 동일성 검증, 차이 발생 시 원인 파악

**리스크 3: 테스트 누락으로 인한 회귀**
- 완화책: Phase 0에서 검증 테스트 추가, 전체 테스트 스위트 실행

**리스크 4: 문서와 코드의 불일치**
- 완화책: 문서 업데이트를 별도 Phase로 분리, 최종 검토 단계에서 일관성 확인

## 8) 메모(Notes)

### 주요 결정 사항

1. **변환 방식 확정**:
   - FFR: `4.63 → 0.0463` (4.63% → 0.0463)
   - Expense: `0.95 → 0.0095` (0.95% → 0.0095)

2. **백업 정책**:
   - CSV 변환 전 원본 백업 생성
   - 결과 파일 재생성 전 백업 생성

3. **검증 기준**:
   - 주요 지표 (RMSE, 누적 수익률) 동일성 확인
   - 허용 오차: 부동소수점 정밀도 범위 내

### 진행 로그 (KST)

- 2025-12-29 20:31: 계획서 작성 완료

---
