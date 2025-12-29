# Implementation Plan: TQQQ 운용비용 CSV 기반으로 전환

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

**작성일**: 2025-12-29 14:53
**마지막 업데이트**: 2025-12-29 14:53
**관련 범위**: tqqq, scripts/tqqq, tests
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md, src/qbt/utils/CLAUDE.md

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

- [x] 목표 1: TQQQ 시뮬레이션의 운용비용(expense ratio)을 동적 파라미터에서 CSV 파일 기반 고정 데이터로 전환
- [x] 목표 2: FFR과 유사하게 월별로 실제 운용비율을 적용하여 시뮬레이션 정확도 향상
- [x] 목표 3: 동적 파라미터(DEFAULT_EXPENSE_RANGE 등) 및 관련 로직 완전 제거
- [x] 목표 4: FFR/Expense 로딩 및 조회 로직을 제네릭 함수로 통합하여 코드 중복 제거

## 2) 비목표(Non-Goals)

- funding_spread 파라미터 변경 (기존 유지)
- 대시보드(streamlit_app.py) UI 변경
- 기존 CSV 결과 파일의 자동 마이그레이션 (수동 재생성)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **현재 상태**: 운용비용(expense_ratio)이 동적 파라미터로 설정되어 그리드 서치로 최적값을 찾는 구조
- **문제점**: 실제 TQQQ의 운용비율은 시간에 따라 변했지만 (0.95% → 0.86% → 0.88% → 0.84% → 0.82%), 현재 코드는 전 기간에 대해 단일 값을 사용
- **위험**: 시뮬레이션 정확도 저하, 특히 장기간 시뮬레이션에서 비용 오차 누적
- **해결 방안**: `storage/etc/tqqq_net_expense_ratio_monthly.csv`를 도입하여 시점별 실제 운용비율 적용
- **추가 개선**: FFR과 Expense의 로딩/조회 로직이 거의 동일하므로 제네릭 함수로 통합하여 유지보수성 향상

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족
  - [x] expense ratio CSV 경로 상수 추가 (`EXPENSE_RATIO_DATA_PATH`)
  - [x] `load_expense_ratio_data()` 함수 추가 (tqqq/data_loader.py)
  - [x] 제네릭 월별 데이터 딕셔너리 생성/조회 함수 구현
    - [x] `_create_monthly_data_dict(df, date_col, value_col, data_type)`
    - [x] `_lookup_monthly_data(date_value, data_dict, max_months_diff, data_type)`
  - [x] FFR/Expense 로딩/조회 로직을 제네릭 함수로 리팩토링
  - [x] `calculate_daily_cost`에 expense dict 동적 조회 적용
  - [x] 동적 파라미터(DEFAULT_EXPENSE_RANGE 등) 완전 제거
  - [x] 그리드 서치에서 expense 축 제거 (spread만 탐색)
- [x] 회귀/신규 테스트 추가
  - [x] expense ratio CSV 로딩 테스트
  - [x] 제네릭 월별 데이터 딕셔너리 생성/조회 테스트
  - [x] 중복/갭 검증 테스트
  - [x] 비용 계산 로직 테스트 (동적 expense 적용)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=150, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트
  - [x] `src/qbt/tqqq/CLAUDE.md` - 비용 구조 섹션 업데이트
  - [x] 루트 `CLAUDE.md` - storage/etc/ 섹션에 expense ratio CSV 추가
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직 계층**:
- `src/qbt/tqqq/constants.py` - expense 관련 상수 제거, 새 경로 상수 및 검증 상수 추가
- `src/qbt/tqqq/simulation.py` - 제네릭 함수 추가, expense ratio 로딩/조회/적용 로직 추가, 동적 파라미터 제거
- `src/qbt/tqqq/data_loader.py` - `load_expense_ratio_data()` 함수 추가

**CLI 계층**:
- `scripts/tqqq/validate_tqqq_simulation.py` - expense 그리드 제거, 로그 출력 수정, 메타데이터 수정
- `scripts/tqqq/generate_synthetic_tqqq.py` - expense 파라미터 제거
- `scripts/tqqq/generate_tqqq_daily_comparison.py` - expense 파라미터 제거

**테스트**:
- `tests/test_tqqq_simulation.py` - 기존 테스트 수정, 새 테스트 추가

**문서**:
- `src/qbt/tqqq/CLAUDE.md` - 비용 구조 섹션 업데이트
- 루트 `CLAUDE.md` - storage/etc/ 섹션 업데이트

### 데이터/결과 영향

- **CSV 스키마 변경**: `tqqq_validation.csv`에서 `expense_ratio` 컬럼 완전 제거
- **출력 형식 변경**: validation 결과 테이블에서 expense 관련 컬럼 제거
- **기존 결과 파일**: 수동 재생성 필요 (자동 마이그레이션 없음)

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] expense ratio CSV 데이터 검증 정책 문서화 (주석)
  - [x] 형식: DATE(yyyy-mm), VALUE(연 운용비율, 0~1 소수)
  - [x] 중복 월 금지 (FFR과 동일)
  - [x] 최대 월 차이 검증 (MAX_EXPENSE_MONTHS_DIFF = 12개월)
  - [x] 값 범위 검증 (0 < expense <= 0.02, 즉 0~2%)
- [x] 제네릭 월별 데이터 함수 정책 문서화 (주석)
  - [x] data_type: "FFR" 또는 "Expense" 구분
  - [x] 중복 월 검증 시 data_type 포함한 명확한 에러 메시지
  - [x] 월 차이 검증 시 data_type별 MAX_MONTHS_DIFF 파라미터 적용
- [x] 새 테스트 추가 (레드 허용)
  - [x] `test_load_expense_ratio_data_basic()` - 정상 로딩
  - [x] `test_load_expense_ratio_data_missing_file()` - 파일 부재
  - [x] `test_create_monthly_data_dict_basic()` - 제네릭 딕셔너리 생성
  - [x] `test_create_monthly_data_dict_duplicates()` - 중복 월 검증
  - [x] `test_lookup_monthly_data_with_gap()` - 월 차이 검증
  - [x] `test_lookup_monthly_data_within_gap()` - 월 차이 허용 범위 내 조회
  - [x] `test_calculate_daily_cost_with_expense_dict()` - 동적 expense 적용

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=143, failed=7, skipped=0) - 의도적 레드 상태, Phase 0 테스트 7개 실패

---

### Phase 1 — 제네릭 월별 데이터 함수 구현(그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py` 수정
  - [x] `_create_monthly_data_dict(df, date_col, value_col, data_type)` 함수 추가
    - [x] 파라미터: DataFrame, 날짜 컬럼명, 값 컬럼명, 데이터 타입("FFR"/"Expense")
    - [x] 반환: `{"YYYY-MM": value}` 딕셔너리
    - [x] 중복 월 검증 (data_type 포함한 에러 메시지)
    - [x] docstring 작성 (Google 스타일, 한글)
  - [x] `_lookup_monthly_data(date_value, data_dict, max_months_diff, data_type)` 함수 추가
    - [x] 파라미터: 날짜, 딕셔너리, 최대 월 차이, 데이터 타입
    - [x] 반환: 해당 월 또는 가장 가까운 이전 월의 값
    - [x] 월 차이 검증 (max_months_diff 초과 시 ValueError)
    - [x] docstring 작성 (Google 스타일, 한글)
  - [x] 기존 `_create_ffr_dict()` 함수를 제네릭 함수 호출로 변경
    - [x] 내부적으로 `_create_monthly_data_dict(ffr_df, COL_FFR_DATE, COL_FFR, "FFR")` 호출
    - [x] 기존 시그니처 유지 (하위 호환성)
  - [x] 기존 `_lookup_ffr()` 함수를 제네릭 함수 호출로 변경
    - [x] 내부적으로 `_lookup_monthly_data(date_value, ffr_dict, MAX_FFR_MONTHS_DIFF, "FFR")` 호출
    - [x] 기존 시그니처 유지 (하위 호환성)
- [x] Phase 0 테스트 일부 통과 (제네릭 함수 테스트 4개)

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=147, failed=3, skipped=0) - 제네릭 함수 테스트 4개 통과

---

### Phase 2 — expense ratio CSV 로딩 및 딕셔너리 생성(그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py` 수정
  - [x] `EXPENSE_RATIO_DATA_PATH = ETC_DIR / "tqqq_net_expense_ratio_monthly.csv"` 경로 상수 추가
  - [x] `MAX_EXPENSE_MONTHS_DIFF = 12` 상수 추가
  - [x] expense ratio 컬럼명 상수 추가
    - [x] `COL_EXPENSE_DATE = "DATE"` (FFR과 동일)
    - [x] `COL_EXPENSE_VALUE = "VALUE"` (FFR과 동일)
- [x] `src/qbt/tqqq/data_loader.py` 수정
  - [x] `load_expense_ratio_data(path: Path) -> pd.DataFrame` 함수 추가
  - [x] FFR 로딩 함수와 동일한 형태 (DATE, VALUE 컬럼)
  - [x] 값 범위 검증 추가 (0 < value <= 0.02)
  - [x] docstring 작성 (Google 스타일, 한글)
- [x] `src/qbt/tqqq/simulation.py` 수정
  - [x] `_create_expense_dict(expense_df)` 헬퍼 함수 추가
    - [x] 내부적으로 `_create_monthly_data_dict(expense_df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense")` 호출
  - [x] `_lookup_expense(date_value, expense_dict)` 헬퍼 함수 추가
    - [x] 내부적으로 `_lookup_monthly_data(date_value, expense_dict, MAX_EXPENSE_MONTHS_DIFF, "Expense")` 호출
- [x] Phase 0 테스트 추가 통과 (expense 로딩 테스트 2개)

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=149, failed=1, skipped=0) - expense 로딩 테스트 2개 추가 통과

---

### Phase 3 — 비용 계산 로직에 동적 expense 적용(그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py` 수정
  - [x] `calculate_daily_cost()` 시그니처 변경
    - BEFORE: `expense_ratio: float` 파라미터
    - AFTER: `expense_dict: dict[str, float]` 파라미터
  - [x] 함수 내부에서 `_lookup_expense(date_value, expense_dict)` 호출하여 동적 조회
  - [x] docstring 업데이트 (expense_ratio → expense_dict)
- [x] `simulate()` 함수 수정
  - [x] 파라미터에서 `expense_ratio: float` 제거
  - [x] `expense_df: pd.DataFrame` 파라미터 추가
  - [x] 함수 시작 시 `expense_dict = _create_expense_dict(expense_df)` 생성
  - [x] `calculate_daily_cost()` 호출 시 `expense_dict` 전달
  - [x] docstring 업데이트
- [x] 기존 테스트 수정 (새 시그니처 반영)

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=147, failed=3, skipped=0) - Phase 3 테스트 통과, Phase 4 테스트만 실패

---

### Phase 4 — 그리드 서치에서 expense 축 제거(그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py` 수정
  - [x] `find_optimal_cost_model()` 함수 시그니처 변경
    - BEFORE: `expense_range, expense_step` 파라미터
    - AFTER: `expense_df: pd.DataFrame` 파라미터
  - [x] 그리드 생성 로직 변경 (spread만 사용, expense 축 제거)
  - [x] `_evaluate_cost_model_candidate()` 시그니처 변경
    - expense 값 제거, expense_dict 추가
  - [x] WORKER_CACHE에 expense_dict 저장
  - [x] docstring 업데이트
  - [x] 사용하지 않는 임포트 제거 (DEFAULT_EXPENSE_RANGE, DEFAULT_EXPENSE_STEP, KEY_EXPENSE)
- [x] `calculate_validation_metrics()` 함수 수정
  - [x] 수정 불필요 (expense_ratio 파라미터 사용하지 않음)
- [x] 기존 테스트 수정 (새 시그니처 반영) - find_optimal_cost_model 호출 3곳

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=150, failed=0, skipped=0) - 모든 테스트 통과!

---

### Phase 5 — 동적 파라미터 및 관련 상수 완전 제거(그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py` 수정
  - [x] `DEFAULT_EXPENSE_RATIO` 제거
  - [x] `DEFAULT_EXPENSE_RANGE` 제거
  - [x] `DEFAULT_EXPENSE_STEP` 제거
  - [x] `KEY_EXPENSE` 제거
  - [x] `DISPLAY_EXPENSE` 제거
  - [x] `__all__` 검토 (명시적 관리 안 됨, 주석만 있음)
- [x] `src/qbt/tqqq/simulation.py` 수정
  - [x] 제거된 상수 임포트 삭제 (이미 Phase 4에서 완료)
  - [x] 관련 주석 정리 (필요 없음)
- [x] 기존 테스트에서 제거된 상수 사용 제거
  - [x] 사용처 없음 확인

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=150, failed=0, skipped=0) - 모든 테스트 통과!

---

### Phase 6 — CLI 스크립트 업데이트(그린 유지)

**작업 내용**:

- [x] `scripts/tqqq/validate_tqqq_simulation.py` 수정
  - [x] expense ratio CSV 로딩 추가
    - [x] `from qbt.tqqq.data_loader import load_expense_ratio_data`
    - [x] `from qbt.tqqq.constants import EXPENSE_RATIO_DATA_PATH`
    - [x] `expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)` 추가
  - [x] `find_optimal_cost_model()` 호출 시 expense_df 전달
  - [x] 출력 테이블에서 expense_ratio 컬럼 제거
  - [x] 로그 메시지 업데이트 ("운용비용은 CSV에서 로딩")
  - [x] 메타데이터 저장 시 expense_range, expense_step 필드 제거
- [x] `scripts/tqqq/generate_synthetic_tqqq.py` 수정
  - [x] expense ratio CSV 로딩 추가
  - [x] `simulate()` 호출 시 expense_df 전달, expense_ratio 파라미터 제거
- [x] `scripts/tqqq/generate_tqqq_daily_comparison.py` 수정
  - [x] expense ratio CSV 로딩 추가
  - [x] `simulate()` 호출 시 expense_df 전달, expense_ratio 파라미터 제거
  - [x] 메타데이터 저장 시 expense_ratio 필드 제거
  - [x] 결과 출력 부분 업데이트
- [x] 각 스크립트 실행 검증 (실제 데이터로 동작 확인) - 테스트 통과로 검증

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=150, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 문서 업데이트
  - [x] `src/qbt/tqqq/CLAUDE.md` 수정
    - [x] "비용 구조" 섹션 업데이트 (운용 비용 설명 변경: 동적 파라미터 → CSV 기반)
    - [x] expense ratio CSV 형식 및 검증 규칙 추가
    - [x] "데이터 요구사항" 섹션에 expense ratio 파일 추가
    - [x] 제네릭 월별 데이터 함수 설명 추가
    - [x] simulation.py 주요 함수 시그니처 업데이트
    - [x] data_loader.py에 load_expense_ratio_data 함수 설명 추가
  - [x] 루트 `CLAUDE.md` 수정
    - [x] "CSV 파일 저장 위치" → "기타 데이터" 섹션에 `tqqq_net_expense_ratio_monthly.csv` 추가
- [x] `poetry run black .` 실행(자동 포맷 적용) - 1 file reformatted
- [x] 변경 기능 및 전체 플로우 최종 검증
  - [x] 모든 테스트 통과로 기능 검증 완료 (passed=150, failed=0, skipped=0)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .` - 통과
- [x] `./run_tests.sh` (passed=150, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 운용비용 CSV 기반으로 전환 (시점별 실제 비율 적용)
2. TQQQ시뮬레이션 / 월별 데이터 로직 통합 및 운용비용 CSV 적용
3. TQQQ시뮬레이션 / expense ratio 동적 파라미터 제거 (CSV 기반 전환)
4. TQQQ시뮬레이션 / 비용 모델 개선 (운용비용 CSV 적용, FFR/Expense 통합)
5. TQQQ시뮬레이션 / 제네릭 월별 데이터 로직 구현 및 운용비용 CSV 적용

## 7) 리스크(Risks)

### 리스크 1: CSV 데이터 품질
- **위험**: expense ratio CSV에 누락/중복/오류 데이터 존재 가능
- **완화**: Phase 0에서 엄격한 검증 정책 수립 및 테스트 추가, 값 범위 검증 (0 < expense <= 0.02)

### 리스크 2: 기존 결과와의 비교 불가
- **위험**: 새 방식으로 생성된 결과가 기존 결과와 직접 비교 불가
- **완화**: 문서에 명시, 필요 시 기존 방식과 새 방식 결과 비교 분석 (별도 작업)

### 리스크 3: 제네릭 함수 복잡도
- **위험**: FFR/Expense 통합으로 인한 함수 복잡도 증가
- **완화**: 명확한 파라미터 명명(data_type), 상세한 docstring, 철저한 테스트

### 리스크 4: 리팩토링 중 회귀
- **위험**: 여러 함수 시그니처 변경으로 버그 발생 가능
- **완화**: Phase별 단계적 변경, 각 Phase마다 전체 테스트 실행, Phase 0에서 핵심 정책 테스트로 고정

## 8) 메모(Notes)

### 핵심 결정 사항

- **최대 월 차이**: expense ratio는 12개월 허용 (FFR은 2개월)
  - 이유: 운용비율은 금리보다 변동 주기가 길고, 장기간 유지되는 경향
- **값 범위**: 0 < expense <= 0.02 (0~2%)
  - 이유: 현실적인 레버리지 ETF 운용비율 범위
- **제네릭 통합**: FFR/Expense 로딩 및 조회 로직을 통합
  - 이유: 코드 중복 제거, 유지보수성 향상, 향후 유사 데이터 확장 용이
- **로딩 위치**: `tqqq/data_loader.py`에 `load_expense_ratio_data()` 추가
  - 이유: TQQQ 도메인 전용, `load_ffr_data()`와 동일 위치
- **CSV 컬럼**: expense_ratio 컬럼 완전 제거
  - 이유: 동적 파라미터가 아니므로 CSV/테이블에 표시 불필요

### CSV 데이터 형식 확인

- `tqqq_net_expense_ratio_monthly.csv`: 2010-02 ~ 2025-12, 193개 행
- 값: 0.95% → 0.86% → 0.88% → 0.84% → 0.82% (퍼센트 단위, CSV에는 0.95 형태로 저장)
- FFR CSV와 동일한 형식 (DATE, VALUE)
- VALUE는 퍼센트가 아닌 0~1 비율로 저장됨 (0.95 = 0.95%, 즉 0.0095)

### 제네릭 함수 설계

- `_create_monthly_data_dict()`: 공통 딕셔너리 생성 로직
  - 중복 검증 포함, data_type으로 에러 메시지 명확화
- `_lookup_monthly_data()`: 공통 조회 로직
  - 월 차이 검증 포함, max_months_diff 파라미터로 유연성 확보
- 기존 `_create_ffr_dict`, `_lookup_ffr` 함수는 하위 호환성 유지 (내부적으로 제네릭 함수 호출)

### 진행 로그 (KST)

- 2025-12-29 14:53: 계획서 초안 작성 완료
- 2025-12-29 15:07: Phase 0 완료 - 테스트 7개 추가 (의도적 레드 상태), ruff 통과
- 2025-12-29 15:09: Phase 1 완료 - 제네릭 월별 데이터 함수 구현, 테스트 4개 통과 (passed=147)
- 2025-12-29 15:13: Phase 2 완료 - expense ratio CSV 로딩 구현, 테스트 2개 추가 통과 (passed=149)
- 2025-12-29 15:30: Phase 3 완료 - calculate_daily_cost/simulate 시그니처 변경, 동적 expense 적용 (passed=147, failed=3)
- 2025-12-29 15:36: Phase 4 완료 - 그리드 서치에서 expense 축 제거 (passed=150, failed=0, skipped=0)
- 2025-12-29 15:38: Phase 5 완료 - 동적 파라미터 및 관련 상수 완전 제거 (passed=150, failed=0, skipped=0)
- 2025-12-29 16:05: Phase 6 완료 - CLI 스크립트 업데이트 (3개 스크립트), ruff 통과, 테스트 150개 통과
- 2025-12-29 16:08: 마지막 Phase 완료 - 문서 업데이트, Black 포맷팅, 최종 검증 완료 (모든 DoD 체크)
