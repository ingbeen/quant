# Implementation Plan: Streamlit 리팩토링 + 모델용 CSV 추가

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

**작성일**: 2026-01-16 12:00
**마지막 업데이트**: 2026-01-16 15:30
**관련 범위**: tqqq, scripts/tqqq
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] Streamlit 파일(`streamlit_rate_spread_lab.py`)에서 UI 렌더링과 orchestration만 남기고, 데이터 가공 로직을 `analysis_helpers.py`로 분리
- [x] `analysis_helpers.py`에 lag/rolling 피처 생성 함수 및 모델용 DF 생성 함수 추가
- [x] 모델용 CSV(`tqqq_rate_spread_lab_model.csv`) 생성 및 저장 기능 추가 (영문 컬럼, schema_version 포함)
- [x] rolling window 데이터 부족 시 fail-fast 정책 적용

## 2) 비목표(Non-Goals)

- Streamlit UI의 시각적 디자인 변경 (레이아웃, 색상 등)
- 기존 CSV 2개(`tqqq_rate_spread_lab_monthly.csv`, `tqqq_rate_spread_lab_summary.csv`)의 스키마 변경
- 모델 학습/추론 코드 구현 (모델용 CSV는 입력 데이터 생성만 담당)
- 다른 Streamlit 앱(`streamlit_daily_comparison.py`) 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **UI와 로직 혼재**: `streamlit_rate_spread_lab.py`에 UI 코드와 데이터 가공 로직이 섞여 있음
   - UI 수정이 곧 로직 변경으로 이어져 회귀 위험 증가
   - 피처 생성 로직을 다른 분석/모델링 코드에서 재사용하기 어려움

2. **모델용 CSV 부재**: AI 모델이 읽을 수 있는 고정 스키마의 CSV가 없음
   - 현재 월별 CSV는 한글 헤더 사용
   - rolling 파생피처 미포함
   - schema_version 관리 부재

3. **확장성 제약**: 모델용 CSV 추가 시 중복 구현 발생 가능
   - "UI는 scripts, 로직은 src" 원칙 미준수

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트) - 계층 분리 원칙, 상수 관리, 코딩 표준
- `src/qbt/tqqq/CLAUDE.md` - 시뮬레이션 도메인 규칙, Fail-fast 정책
- `scripts/CLAUDE.md` - CLI 계층 규칙, UI vs 로직 분리
- `tests/CLAUDE.md` - 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] Streamlit 앱 실행 시 UI 동작이 기존과 동일
- [x] 저장 1회 가드(`_save_guard`)가 유지됨
- [x] 기존 CSV 2개가 이전과 동일하게 생성됨:
  - `tqqq_rate_spread_lab_monthly.csv`
  - `tqqq_rate_spread_lab_summary.csv`
- [x] 신규 CSV가 추가 생성됨:
  - `tqqq_rate_spread_lab_model.csv` (영문 컬럼, schema_version 포함)
- [x] rolling window(12)보다 데이터가 적으면 예외 발생 (fail-fast 정책)
- [x] Streamlit 파일에는 st 호출 기반 UI 코드만 남음
- [x] 피처 생성/스키마 생성/가공 로직은 `analysis_helpers.py`에 집중
- [x] 신규 테스트 추가: `add_rate_change_lags`, `add_rolling_features`, `build_model_dataset`
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/constants.py`
  - 모델용 CSV 경로 상수 추가
  - 모델용 컬럼명 상수 추가 (영문)
  - schema_version 상수 추가
  - rolling window 기본값 상수 추가

- `src/qbt/tqqq/analysis_helpers.py`
  - `add_rate_change_lags()` 함수 추가
  - `add_rolling_features()` 함수 추가
  - `build_model_dataset()` 함수 추가
  - `save_model_csv()` 함수 추가

- `scripts/tqqq/streamlit_rate_spread_lab.py`
  - UI 렌더링 함수로 분리 (`_render_*`)
  - 데이터 가공 로직 제거 (analysis_helpers 호출로 대체)
  - 모델용 CSV 저장 추가

- `tests/test_tqqq_analysis_helpers.py`
  - 신규 함수 테스트 추가

### 데이터/결과 영향

- **기존 CSV**: 스키마 변경 없음, 동일하게 생성
- **신규 CSV**: `tqqq_rate_spread_lab_model.csv` 추가
  - 위치: `storage/results/`
  - 스키마: 영문 컬럼, schema_version 포함

## 6) 단계별 계획(Phases)

### Phase 0 — constants.py 상수 추가 및 테스트 골격 작성

**작업 내용**:

- [x] `constants.py`에 모델용 CSV 관련 상수 추가:
  - `TQQQ_RATE_SPREAD_LAB_MODEL_PATH`: 모델용 CSV 경로
  - `MODEL_SCHEMA_VERSION`: 스키마 버전 (예: "1.0")
  - `DEFAULT_ROLLING_WINDOW`: rolling window 기본값 (12)
  - `COL_MODEL_*`: 모델용 영문 컬럼명 상수들
    - `COL_MODEL_MONTH = "month"`
    - `COL_MODEL_SCHEMA_VERSION = "schema_version"`
    - `COL_MODEL_RATE_LEVEL_PCT = "rate_level_pct"`
    - `COL_MODEL_RATE_CHANGE_PCT = "rate_change_pct"`
    - `COL_MODEL_RATE_CHANGE_LAG1_PCT = "rate_change_lag1_pct"`
    - `COL_MODEL_RATE_CHANGE_LAG2_PCT = "rate_change_lag2_pct"`
    - `COL_MODEL_ERROR_EOM_PCT = "error_eom_pct"`
    - `COL_MODEL_ERROR_CHANGE_PCT = "error_change_pct"`
    - `COL_MODEL_ERROR_DAILY_SUM_PCT = "error_daily_sum_pct"`
    - `COL_MODEL_CV_DIFF_PCT = "cv_diff_pct"`
    - Rolling correlation 컬럼명:
      - `COL_MODEL_ROLLING_CORR_LEVEL = "rolling_corr_rate_level_error_eom"`
      - `COL_MODEL_ROLLING_CORR_DELTA = "rolling_corr_rate_change_error_change"`
      - `COL_MODEL_ROLLING_CORR_LAG1 = "rolling_corr_rate_lag1_error_change"`
      - `COL_MODEL_ROLLING_CORR_LAG2 = "rolling_corr_rate_lag2_error_change"`
- [x] `__all__` 목록 업데이트
- [x] `tests/test_tqqq_analysis_helpers.py`에 신규 함수 테스트 골격 작성 (레드 허용)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=209, failed=0, skipped=0)

---

### Phase 1 — analysis_helpers.py에 피처 생성 함수 구현

**작업 내용**:

- [x] `add_rate_change_lags()` 함수 구현:
  - 시그니처: `def add_rate_change_lags(df_monthly: pd.DataFrame, lag_list: list[int]) -> pd.DataFrame`
  - 원본 df 변경하지 않음 (copy 기반)
  - `dr_m` 컬럼의 shift로 lag 컬럼 생성
  - 컬럼명은 constants의 `COL_DR_LAG1`, `COL_DR_LAG2` 사용

- [x] `add_rolling_features()` 함수 구현:
  - 시그니처: `def add_rolling_features(df_monthly: pd.DataFrame, window: int = DEFAULT_ROLLING_WINDOW) -> pd.DataFrame`
  - **데이터 길이 < window 시 ValueError raise** (fail-fast 정책)
  - `min_periods = window`로 설정 (불완전 window 허용 금지)
  - Rolling correlation(12개월) 계산:
    - rate_level_pct ↔ error_eom_pct
    - rate_change_pct ↔ error_change_pct
    - rate_change_lag1_pct ↔ error_change_pct
    - rate_change_lag2_pct ↔ error_change_pct
  - 미래 데이터 혼입 방지 (과거 window만 사용)

- [x] 테스트 통과 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=209, failed=0, skipped=0)

---

### Phase 2 — 모델용 DF 생성 및 CSV 저장 함수 구현

**작업 내용**:

- [x] `build_model_dataset()` 함수 구현:
  - 시그니처: `def build_model_dataset(df_monthly: pd.DataFrame, window: int = DEFAULT_ROLLING_WINDOW) -> pd.DataFrame`
  - 내부에서 `add_rate_change_lags()`, `add_rolling_features()` 호출
  - 필요한 컬럼만 선택 및 영문 컬럼명으로 rename
  - `schema_version` 컬럼 추가
  - `cv_diff_pct = error_change_pct - error_daily_sum_pct` 생성

- [x] `save_model_csv()` 함수 구현:
  - 시그니처: `def save_model_csv(df_model: pd.DataFrame, output_path: Path) -> None`
  - 필수 컬럼 검증
  - month 오름차순 정렬
  - 수치 컬럼 라운딩 (4자리)
  - CSV 저장

- [x] 테스트 추가 및 통과 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=209, failed=0, skipped=0)

---

### Phase 3 — Streamlit 리팩토링

**작업 내용**:

- [x] `streamlit_rate_spread_lab.py` UI 함수 분리:
  - `_render_intro()`: 타이틀, 설명
  - `_render_dataset_metrics(df_monthly)`: 요약 통계 표시
  - `_render_level_section(df_monthly)`: Level 분석 섹션
  - `_render_delta_section(df_monthly)`: Delta 분석 섹션
  - `_render_cross_validation_section(df_monthly)`: 교차검증 섹션
  - `_save_outputs_once(df_monthly, df_summary, df_model)`: 저장 1회 가드 유지

- [x] 데이터 가공 로직 제거:
  - `prepare_monthly_data()` 함수 내용을 `analysis_helpers.py` 호출로 대체
  - lag 컬럼 생성 로직을 `add_rate_change_lags()` 호출로 대체

- [x] 모델용 CSV 저장 추가:
  - `build_model_dataset()` 호출
  - `save_model_csv()` 호출

- [x] UI 문자열은 constants의 `DISPLAY_*` 사용 확인

- [x] Streamlit 앱 실행 테스트 (수동)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=209, failed=0, skipped=0)

---

### Phase 4 — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트:
  - `analysis_helpers.py` 모듈 설명에 신규 함수 추가
  - 모델용 CSV 스펙 추가
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증:
  - Streamlit 앱 실행 후 UI 동작 확인
  - 기존 CSV 2개 생성 확인
  - 신규 모델용 CSV 생성 확인
  - rolling 데이터 부족 시 예외 발생 확인 (테스트)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=209, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Streamlit 리팩토링 및 모델용 CSV 추가 (UI/로직 분리)
2. TQQQ시뮬레이션 / analysis_helpers에 피처 생성 함수 집중 + 모델 CSV 출력
3. TQQQ시뮬레이션 / UI-로직 분리 리팩토링 및 AI 모델용 데이터셋 생성
4. TQQQ시뮬레이션 / rolling 피처 및 모델 CSV 추가 (fail-fast 정책 적용)
5. TQQQ시뮬레이션 / Streamlit 계층 정리 + 영문 스키마 모델 CSV 신규

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| Streamlit 리팩토링 중 기존 동작 회귀 | 수동 테스트로 UI 동작 확인, 기존 CSV 출력 비교 |
| rolling 함수의 min_periods 설정 오류 | 테스트에서 데이터 부족 케이스 검증 |
| 컬럼명 매핑 오류 (내부 ↔ 모델용) | constants에서 일관된 상수 사용, 테스트 검증 |
| 캐시 무효화로 인한 성능 저하 | build_artifacts 캐시 키 유지, 모델 DF 빌드는 캐시 내부에서 처리 |

## 8) 메모(Notes)

### 사용자 승인 정책 (프롬프트에서 확정)

- 모델 CSV 파일명: `tqqq_rate_spread_lab_model.csv`
- 모델 CSV 컬럼: 영문만
- rolling 파생피처 포함
- rolling 데이터 부족 시: 예외 raise (NA로 그냥 두지 않음)

### 모델용 CSV 스키마 (v1.0)

| 컬럼명 | 설명 |
|--------|------|
| month | 연월 (yyyy-mm) |
| schema_version | 스키마 버전 |
| rate_level_pct | 금리 수준 (%) |
| rate_change_pct | 금리 변화 (%p) |
| rate_change_lag1_pct | 금리 변화 Lag1 (%p) |
| rate_change_lag2_pct | 금리 변화 Lag2 (%p) |
| error_eom_pct | 월말 누적 오차 (%) |
| error_change_pct | 월간 오차 변화 (%) |
| error_daily_sum_pct | 일일 오차 월합 (%) |
| cv_diff_pct | 교차검증 차이 (%) |
| rolling_corr_rate_level_error_eom | Rolling 12M 상관: 금리수준 ↔ 월말오차 |
| rolling_corr_rate_change_error_change | Rolling 12M 상관: 금리변화 ↔ 오차변화 |
| rolling_corr_rate_lag1_error_change | Rolling 12M 상관: 금리Lag1 ↔ 오차변화 |
| rolling_corr_rate_lag2_error_change | Rolling 12M 상관: 금리Lag2 ↔ 오차변화 |

### Context7 학습 결과

- **Streamlit**: `st.cache_data`는 데이터 캐싱용, `st.cache_resource`는 글로벌 리소스(DB 연결 등) 캐싱용
- **Pandas rolling**: `df.rolling(window=N, min_periods=N).corr(other)` 형식으로 rolling correlation 계산

### 진행 로그 (KST)

- 2026-01-16 12:00: 계획서 초안 작성
- 2026-01-16 15:30: 모든 Phase 완료, Validation 통과 (passed=209, failed=0, skipped=0)

---
