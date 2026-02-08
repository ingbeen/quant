# Implementation Plan: 동적 Spread(Softplus) CSV 산출 확장 + Streamlit 반영

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

**작성일**: 2026-02-08 (KST)
**마지막 업데이트**: 2026-02-08 (KST)
**관련 범위**: tqqq, scripts
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `run_softplus_tuning.py` 실행 후 전체기간 단일 최적 (a, b)에 대한 **월별 spread 시계열 CSV** 추가 생성
- [x] `run_walkforward_validation.py` 실행 후 워크포워드 결과 CSV에 **ffr_pct_test, spread_test 컬럼** 추가
- [x] `streamlit_rate_spread_lab.py`에서 위 두 CSV를 읽어 **고정 vs 워크포워드 spread 비교 시각화** (라인차트 + 산점도)

## 2) 비목표(Non-Goals)

- 기존 softplus 튜닝/워크포워드 알고리즘 변경
- spread 계산식 변경 (기존 `softplus(a + b * ffr_pct)` 유지)
- 새로운 테스트 프레임워크 도입
- Streamlit에서 무거운 연산 수행 (CSV 기반 시각화만)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 워크포워드에서 b 파라미터가 월별로 변동하지만, 최종 산출물인 **spread(비용)**가 얼마나 변동하는지 직접 확인할 방법이 없음
- "b가 흔들린다"가 "좋은 적응"인지 "불필요한 출렁임"인지 판단하려면, **고정 기준선**(전체기간 최적 a,b로 만든 spread 시계열)과 비교해야 함
- 현재 Streamlit은 a, b 파라미터 추이만 시각화하고, spread 자체의 시계열은 표시하지 않음

### 핵심 설계 결정

**FFR 누락 월 처리**: 시뮬레이션 표준 방식 적용 (`_lookup_monthly_data` → 최대 2개월 이전 값 fallback, 초과 시 ValueError)

**파일명**: `tqqq_softplus_spread_series_static.csv` (RESULTS_DIR에 저장)

**워크포워드 대상**: 메인 결과 CSV(`tqqq_rate_spread_lab_walkforward.csv`)에 2개 컬럼 추가

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `run_softplus_tuning.py` 실행 후 `tqqq_softplus_spread_series_static.csv` 생성 (month, ffr_pct, a_global, b_global, spread_global 컬럼, month 오름차순)
- [x] `run_walkforward_validation.py` 실행 후 기존 워크포워드 CSV에 `ffr_pct_test`, `spread_test` 컬럼 추가 (`spread_test = softplus(a_best + b_best * ffr_pct_test)`)
- [x] Streamlit에서 계산 없이 CSV 기반으로 (1) 월별 spread 시계열 라인차트, (2) FFR vs spread 산점도 표시
- [x] 기존 테스트 회귀 없음 + 신규 비즈니스 로직 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=258, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/qbt/tqqq/constants.py` | 경로 상수 1개 추가, `__all__` 업데이트 |
| `src/qbt/tqqq/simulation.py` | `generate_static_spread_series()` 함수 추가, `run_walkforward_validation()` 수정 |
| `src/qbt/tqqq/analysis_helpers.py` | 워크포워드 컬럼 상수 2개 추가, `_WALKFORWARD_REQUIRED_COLUMNS` 업데이트, `save_walkforward_results()` 수정, `save_static_spread_series()` 추가 |
| `scripts/tqqq/run_softplus_tuning.py` | 정적 spread 시계열 CSV 생성/저장 로직 추가 |
| `scripts/tqqq/streamlit_rate_spread_lab.py` | spread 비교 시각화 섹션 추가 |
| `tests/test_tqqq_simulation.py` | 새 함수 테스트 추가 |
| `tests/test_tqqq_analysis_helpers.py` | 기존 `save_walkforward_results` 테스트 픽스처 업데이트 (새 컬럼 반영) + 새 save 함수 테스트 |

### 데이터/결과 영향

- **신규 CSV**: `storage/results/tqqq_softplus_spread_series_static.csv`
- **기존 CSV 스키마 변경**: `tqqq_rate_spread_lab_walkforward.csv`에 2개 컬럼 추가 (기존 컬럼은 유지)
- 기존 결과 비교 불필요 (추가 컬럼만)

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 + 비즈니스 로직 (그린 유지)

**작업 내용**:

**1.1 `src/qbt/tqqq/constants.py`**:
- [x] `SOFTPLUS_SPREAD_SERIES_STATIC_PATH: Final = RESULTS_DIR / "tqqq_softplus_spread_series_static.csv"` 추가
- [x] `__all__`에 `SOFTPLUS_SPREAD_SERIES_STATIC_PATH` 추가

**1.2 `src/qbt/tqqq/simulation.py`** — `generate_static_spread_series()` 추가:
- [x] 로컬 컬럼 상수 정의: `COL_SS_MONTH`, `COL_SS_FFR_PCT`, `COL_SS_A_GLOBAL`, `COL_SS_B_GLOBAL`, `COL_SS_SPREAD_GLOBAL`
- [x] `generate_static_spread_series(ffr_df, a, b, underlying_overlap_df)` 함수 추가
  - 입력: FFR DataFrame, a, b 파라미터, 기초자산 overlap DataFrame
  - 처리: overlap 기간 고유 월 추출 → 각 월 FFR 조회(`_create_ffr_dict` + `_lookup_ffr`) → `compute_softplus_spread` 계산
  - 출력: DataFrame (month, ffr_pct, a_global, b_global, spread_global), month 오름차순
  - 빈 overlap이면 ValueError

**1.3 `src/qbt/tqqq/simulation.py`** — `run_walkforward_validation()` 수정:
- [x] 루프 이전: `ffr_dict = _create_ffr_dict(ffr_df)` 호출 (한 번만)
- [x] 각 iteration에서 a_best, b_best 결정 후:
  ```
  test_month → date 변환 → _lookup_ffr(date, ffr_dict) → ffr_ratio_test
  ffr_pct_test = ffr_ratio_test * 100.0
  spread_test = compute_softplus_spread(a_best, b_best, ffr_ratio_test)
  ```
- [x] result dict에 `"ffr_pct_test"`, `"spread_test"` 키 추가

**1.4 `src/qbt/tqqq/analysis_helpers.py`** — 워크포워드 저장 함수 업데이트:
- [x] `COL_WF_FFR_PCT_TEST = "ffr_pct_test"`, `COL_WF_SPREAD_TEST = "spread_test"` 추가
- [x] `_WALKFORWARD_REQUIRED_COLUMNS`에 2개 컬럼 추가
- [x] `save_walkforward_results()`의 `numeric_cols` 리스트에 2개 컬럼 추가

**1.5 `src/qbt/tqqq/analysis_helpers.py`** — `save_static_spread_series()` 추가:
- [x] 입력: DataFrame, output_path
- [x] 처리: month 오름차순 정렬, 수치 컬럼 4자리 라운딩(spread_global은 6자리), CSV 저장
- [x] 부모 디렉토리 자동 생성

**1.6 기존 테스트 픽스처 업데이트** (`tests/test_tqqq_analysis_helpers.py`):
- [x] `TestSaveWalkforwardResults` 클래스의 4개 테스트 픽스처에 `ffr_pct_test`, `spread_test` 컬럼 추가
  - `test_save_walkforward_results_success` (line 1060)
  - `test_save_walkforward_results_rounding` (line 1107)
  - `test_save_walkforward_results_missing_column_raises` (line 1142) — missing 검증 대상도 업데이트
  - `test_save_walkforward_results_sorted_by_test_month` (line 1171)
- [x] 새 컬럼의 라운딩 및 저장 검증 assert 추가

**Validation**:

- [x] `poetry run python validate_project.py` (passed=252, failed=0, skipped=0)

---

### Phase 2 — 스크립트 + Streamlit + 테스트 (그린 유지)

**작업 내용**:

**2.1 `scripts/tqqq/run_softplus_tuning.py`** 수정:
- [x] 임포트 추가: `extract_overlap_period`, `generate_static_spread_series`, `save_static_spread_series`, `SOFTPLUS_SPREAD_SERIES_STATIC_PATH`
- [x] 튜닝 완료 후 정적 spread 시계열 생성:
  1. `extract_overlap_period(qqq_df, tqqq_df)` → overlap 데이터 추출
  2. `generate_static_spread_series(ffr_df, a_best, b_best, overlap_underlying)` → DataFrame 생성
  3. `save_static_spread_series(df, SOFTPLUS_SPREAD_SERIES_STATIC_PATH)` → CSV 저장
  4. 로그 출력, 메타데이터에 새 파일 정보 추가

**2.2 `scripts/tqqq/streamlit_rate_spread_lab.py`** 수정:
- [x] 임포트 추가: `SOFTPLUS_SPREAD_SERIES_STATIC_PATH`
- [x] `_load_static_spread_csv()` 캐시 함수 추가 (SOFTPLUS_SPREAD_SERIES_STATIC_PATH 로드)
- [x] `_render_spread_comparison_section()` 함수 추가:
  - 정적 CSV + 워크포워드 CSV 로드 (이미 로드된 result_df 재사용)
  - 파일 없으면 st.warning 표시 후 리턴
  - **차트 1: 월별 spread 시계열 라인차트**
    - x축: month, y축: spread
    - 두 라인: spread_global (정적, 모든 월) + spread_test (워크포워드, test_month만)
    - 같은 그래프에 겹쳐 표시 (색상/범례 구분)
  - **차트 2: FFR vs spread 산점도**
    - 정적: x=ffr_pct, y=spread_global
    - 워크포워드: x=ffr_pct_test, y=spread_test
    - 같은 그래프에 색상/범례로 구분
  - 설명 텍스트 (VERBATIM 스타일: 용어 설명 + 해석 방법 + 판단)
- [x] `_render_softplus_section()` 또는 `_render_walkforward_section()` 끝에서 `_render_spread_comparison_section()` 호출

**2.3 테스트 추가** (`tests/test_tqqq_simulation.py`):
- [x] `generate_static_spread_series` 테스트:
  - 정상 케이스: FFR 데이터와 overlap 기간이 주어지면 올바른 spread 계산
  - spread = softplus(a + b * ffr_pct) 검증
  - month 오름차순 정렬 검증
  - 컬럼 존재 검증
- [x] `run_walkforward_validation` 결과에 `ffr_pct_test`, `spread_test` 컬럼 존재 검증 (기존 테스트 수정 or 추가)
  - spread_test = softplus(a_best + b_best * ffr_pct_test) 일치 검증

**Validation**:

- [x] `poetry run python validate_project.py` (passed=258, failed=0, skipped=0)

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=258, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 동적 Spread(Softplus) 월별 시계열 CSV 산출 + Streamlit 비교 시각화 추가
2. TQQQ시뮬레이션 / softplus 정적 spread 시계열 CSV + 워크포워드 spread 컬럼 추가 + 시각화
3. TQQQ시뮬레이션 / spread 비교 기반 추가 (정적 CSV 생성 + 워크포워드 확장 + Streamlit 차트)
4. TQQQ시뮬레이션 / 고정 vs 워크포워드 spread 비교를 위한 CSV 확장 및 시각화 구현
5. TQQQ시뮬레이션 / 동적 Spread CSV 산출 확장 (정적 시계열 + 워크포워드 spread + 비교 차트)

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| 기존 워크포워드 테스트가 새 컬럼으로 인해 실패 | `_WALKFORWARD_REQUIRED_COLUMNS` 변경에 맞춰 테스트 픽스처 업데이트 |
| FFR 누락 월에서 fallback 실패 가능 | 기존 `_lookup_ffr` + MAX_FFR_MONTHS_DIFF(2개월) 방어적 체크 재사용 |
| Streamlit에서 신규 CSV 미존재 시 크래시 | 파일 존재 체크 후 st.warning 표시, 기존 패턴 동일 적용 |
| 정적 spread와 워크포워드 spread의 month 범위 불일치 | 라인차트에서 각각 고유 x축 범위로 표시 (겹치는 구간에서만 비교 의미 있음) |

## 8) 메모(Notes)

### 핵심 설계 결정

1. **`generate_static_spread_series`를 simulation.py에 배치**: 기존 private 함수(`_create_ffr_dict`, `_lookup_ffr`, `compute_softplus_spread`)를 재사용하기 위함. analysis_helpers.py에 두면 순환 임포트 발생.

2. **워크포워드 결과 dict에 직접 추가**: `run_walkforward_validation()`에서 각 iteration마다 spread_test를 계산하여 result dict에 포함. 별도 후처리 불필요.

3. **Streamlit 차트는 인라인 생성**: 기존 워크포워드 차트(fig_a, fig_b, fig_rmse)도 인라인 plotly.graph_objects로 생성하므로 동일 패턴 유지.

4. **spread 라운딩**: spread_global은 6자리, ffr_pct는 4자리 (기존 프로젝트 정밀도 가이드라인 참고)

### 핵심 함수/상수 참조 (재사용 대상)

- `compute_softplus_spread(a, b, ffr_ratio)`: `simulation.py:138` — spread 계산 핵심 함수
- `build_monthly_spread_map(ffr_df, a, b)`: `simulation.py:178` — FFR DataFrame → 월별 spread dict
- `_create_ffr_dict(ffr_df)`: `simulation.py:372` — FFR DataFrame → dict 변환
- `_lookup_ffr(date_value, ffr_dict)`: `simulation.py:390` — FFR 조회 (2개월 fallback)
- `extract_overlap_period(underlying_df, actual_leveraged_df)`: `simulation.py` — 겹치는 기간 추출
- `save_walkforward_results(result_df, output_path)`: `analysis_helpers.py:1067` — 워크포워드 결과 저장
- `_WALKFORWARD_REQUIRED_COLUMNS`: `analysis_helpers.py:1053` — 워크포워드 필수 컬럼 리스트

### 진행 로그 (KST)

- 2026-02-08: Plan 작성 시작
- 2026-02-08: Phase 1 구현 완료 (상수 + 비즈니스 로직 + 테스트 픽스처 업데이트)
- 2026-02-08: Phase 1 Validation 통과 (passed=252, failed=0, skipped=0)
- 2026-02-08: Phase 2 구현 완료 (스크립트 + Streamlit + 테스트)
- 2026-02-08: Phase 2 Validation 통과 (passed=258, failed=0, skipped=0)
- 2026-02-08: Phase 3 완료 (Black 포맷 + 최종 검증)
- 2026-02-08: Phase 3 Validation 통과 (passed=258, failed=0, skipped=0)
- 2026-02-08: 상태 → Done

---
