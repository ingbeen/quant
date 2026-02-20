# QBT 프로젝트 전체 분석 보고서

**분석일**: 2026-02-20
**분석 범위**: src/qbt/, scripts/, tests/, docs/, 설정 파일 전체
**분석 목적**: 리팩토링 기회, 문서 불일치, 주석/소스 가독성, 버그, 논리적 어긋남 파악

---

## 요약

| 카테고리 | 건수 | 심각도 |
|---------|------|--------|
| A. 버그 및 논리적 오류 | 5건 | 높음 |
| B. 문서와 코드 불일치 | 5건 | 중간 |
| C. CLI 계층 규칙 위반 | 3건 | 중간 |
| D. 리팩토링 기회 | 9건 | 중간~낮음 |
| E. 주석 및 가독성 | 4건 | 낮음 |
| F. 일관성 문제 | 6건 | 낮음 |
| G. 테스트 품질 | 3건 | 낮음~중간 |
| H. 설정 파일 | 2건 | 낮음 |
| **합계** | **37건** | |

---

## A. 버그 및 논리적 오류 (심각도: 높음)

### A-1. 그리드 서치 정렬 기준이 문서와 코드에서 불일치

- **코드**: `src/qbt/backtest/strategies/buffer_zone_helpers.py:735` — `sort_values(by=COL_TOTAL_RETURN_PCT)` (총 수익률 기준)
- **문서**: `CLAUDE.md`, `src/qbt/backtest/CLAUDE.md` — "CAGR 내림차순"으로 명시
- **영향**: 동일 기간 그리드 서치에서는 순위 동일하지만, 문서-코드 불일치로 향후 혼란 가능

### A-2. 매도 주문 실행 시 `hold_days_used` 덮어쓰기 — 죽은 코드

- **위치**: `src/qbt/backtest/strategies/buffer_zone_helpers.py:878-879`
- `_execute_sell_order()` 내부(줄 539-540)에서 `order`로부터 값 복사 후, 체결 직후 줄 878-879에서 `entry_hold_days`로 다시 덮어씀
- `_execute_sell_order` 내부 코드가 죽은 코드(dead code)

### A-3. `_save_summary_json`에서 `summary["win_rate"]` KeyError 가능성

- **위치**: `scripts/backtest/run_single_backtest.py:205`
- `summary.get("winning_trades", 0)`은 `.get()` 사용하지만, `summary["win_rate"]`는 직접 접근
- Buy & Hold 등 `win_rate` 키가 없는 전략에서 KeyError 발생 가능

### A-4. 테스트가 실제로 검증하지 않는 `try/except/pass` 패턴

- **위치**: `tests/test_tqqq_simulation.py:110-124`
- `test_ffr_fallback_within_2_months` — ValueError가 발생해도 `pass`로 넘기므로 fallback 동작 미검증

### A-5. `BufferStrategyParams` docstring 비율 표기 오류

- **위치**: `src/qbt/backtest/strategies/buffer_zone_helpers.py:195`
- `buffer_zone_pct: float  # 초기 버퍼존 비율 (예: 5.0 = 5%)` — 실제로는 0~1 범위(0.03 = 3%)
- 루트 CLAUDE.md 비율 표기 규칙과 불일치

---

## B. 문서와 실제 코드 불일치 (심각도: 중간)

### B-1. `buffer_zone.py` 파일명이 문서에 잔존

- `src/qbt/backtest/types.py:10` — `buffer_zone.py` 참조 (실제: `buffer_zone_helpers.py`)
- `tests/CLAUDE.md:104` — 동일 오류

### B-2. `meta_manager.py` docstring의 사라진 `tqqq_validation` 타입

- `src/qbt/utils/meta_manager.py:126` — docstring에 `"tqqq_validation"` 예시
- `scripts/CLAUDE.md:56` — 동일 오류
- 실제 `VALID_CSV_TYPES`에 존재하지 않으며, 누락된 신규 타입 다수

### B-3. `pyproject.toml` description에 DuckDB 참조 잔존

- `pyproject.toml:5` — `"Stock backtesting framework with DuckDB and CSV data management"`
- 프로젝트 어디에도 DuckDB 사용하지 않음

### B-4. `test_strategy.py` 파일 docstring 정책 불일치

- `tests/test_strategy.py:7` — `"4. 포지션이 남았을 때 강제 청산되는가?"`
- 현재 정책은 "강제청산 없음"

### B-5. `tqqq/CLAUDE.md`의 `extract_overlap_period` 위치 오해 유발

- `src/qbt/tqqq/CLAUDE.md:67` — `simulation.py` 함수 목록에 기재
- 실제로는 `utils/data_loader.py`에서 임포트하여 사용

---

## C. CLI 계층 규칙 위반 (심각도: 중간)

### C-1. `download_data.py` — 비즈니스 로직이 CLI에 구현

- `scripts/data/download_data.py:35-172`
- `validate_stock_data()`와 `download_stock_data()` 모두 비즈니스 로직

### C-2. `validate_walkforward_fixed_ab.py` — ~220줄의 비즈니스 로직

- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py:253-472`
- 내부 함수(`_calculate_metrics_fast`)까지 직접 import하여 모듈 캡슐화 위반

### C-3. `generate_synthetic.py` — `_build_extended_expense_dict` 비즈니스 로직

- `scripts/tqqq/generate_synthetic.py:53-92`

---

## D. 리팩토링 기회 (심각도: 중간~낮음)

### D-1. `_prepare_monthly_data` 함수 완전 중복

- `scripts/tqqq/spread_lab/generate_rate_spread_lab.py:60-113`
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py:143-196`
- 동일 코드가 두 파일에 복사됨

### D-2. `COL_A`, `COL_B`, `COL_RMSE_PCT` 상수 4곳 중복 정의

- `tune_softplus_params.py`, `validate_walkforward_fixed_b.py`, `validate_walkforward_fixed_ab.py`, `app_rate_spread_lab.py`

### D-3. 3개 워크포워드 검증 스크립트의 구조적 중복

- `validate_walkforward.py`, `validate_walkforward_fixed_b.py`, `validate_walkforward_fixed_ab.py`
- 데이터 로딩 → 출력 → 실행 → 저장 패턴 거의 동일

### D-4. `simulation.py` 파일 크기 과대 (2108줄)

- simulate, softplus 최적화, 워크포워드 검증 등 서로 다른 관심사가 한 파일에 밀집

### D-5. `app_rate_spread_lab.py` 파일 크기 과대 (1762줄)

- 데이터 로딩, 차트 렌더링, 해석 로직 등 여러 관심사가 단일 파일에 집중

### D-6. `find_optimal_softplus_params`와 `_local_refine_search`의 ~40줄 초기화 코드 중복

- `src/qbt/tqqq/simulation.py:1255-1294` vs `src/qbt/tqqq/simulation.py:1466-1505`

### D-7. `calculate_stitched_walkforward_rmse`와 `calculate_fixed_ab_stitched_rmse`의 구조 중복

- `src/qbt/tqqq/simulation.py:1780-1898` vs `src/qbt/tqqq/simulation.py:1901-2015`

### D-8. `TQQQ_SYNTHETIC_PATH`와 `TQQQ_SYNTHETIC_DATA_PATH` 경로 상수 중복

- `src/qbt/common_constants.py:39` vs `src/qbt/tqqq/constants.py:26`
- 동일 경로를 두 곳에서 정의 — 상수 중복 금지 원칙 위반

### D-9. `buy_and_hold.py`에서 `iterrows()` 사용

- `src/qbt/backtest/strategies/buy_and_hold.py:147` — 벡터화 연산으로 대체 가능

---

## E. 주석 및 가독성 (심각도: 낮음)

### E-1. 금지된 개발 단계 표현이 주석에 잔존

- `tests/test_strategy.py:1141, 1185` — `(레드)` 표현
- `tests/test_meta_manager.py:209, 299` — `Phase 6` 표현
- `tests/test_tqqq_simulation.py:984, 1113` — `레드` 표현
- CLAUDE.md 규칙: "Phase 0, 레드, 그린 등 개발 단계 표현 사용 금지"

### E-2. `app_rate_spread_lab.py`에서 변수명과 표시 레이블 불일치

- `scripts/tqqq/spread_lab/app_rate_spread_lab.py:842`
- `fixed_b_value`를 `a=`로 표시하는 혼란

### E-3. 과도한 "학습 포인트:" 주석

- `common_constants.py`, `analysis.py`, `simulation.py`, `logger.py` 등 다수 파일
- 비즈니스 로직 이해에 불필요한 노이즈

### E-4. `aggregate_monthly`에서 `sum_daily_m`이 항상 NA 설정

- `src/qbt/tqqq/analysis_helpers.py:351-353`
- placeholder NaN이 후속 함수에 전달될 수 있음. 주석 보강 필요

---

## F. 일관성 문제 (심각도: 낮음)

### F-1. `COL_` 접두사 한글/영문 혼재

- `src/qbt/tqqq/constants.py` — `COL_ACTUAL_CLOSE = "종가_실제"` 등 한글값
- CLAUDE.md: `COL_`은 "내부 계산용 영문 토큰"

### F-2. CSV 인코딩 불일치

- `src/qbt/tqqq/simulation.py:1004` — `utf-8-sig` (BOM 포함)
- `src/qbt/tqqq/analysis_helpers.py` — `utf-8` (BOM 미포함)

### F-3. 로거 초기화 방식 불일치

- `scripts/tqqq/spread_lab/app_rate_spread_lab.py:79` — `setup_logger()` (유일)
- 나머지 12개 스크립트 — `get_logger()` 사용

### F-4. `__all__` 사용이 일부 모듈에서만 정의

- `tqqq/constants.py`, `analysis_helpers.py` — 사용
- `backtest/constants.py`, `common_constants.py`, `buffer_zone_helpers.py` — 미사용

### F-5. 누락 컬럼 검증 패턴 혼재

- `set` 차집합 vs 리스트 컴프리헨션 패턴이 파일마다 다름

### F-6. `os.path.getmtime` 사용 (Path 규칙 위반)

- `scripts/tqqq/app_daily_comparison.py:41` — `path.stat().st_mtime`으로 대체 필요

---

## G. 테스트 품질 (심각도: 낮음~중간)

### G-1. 조건부 가드로 assert가 실행되지 않을 수 있는 패턴

- `tests/test_strategy.py` — 줄 502, 810, 855, 896 등
- `if len(equity_df) >= N:` 가드 안에 assert가 있어 건너뛸 수 있음

### G-2. 타임존 의존적 하드코딩

- `tests/test_meta_manager.py:397`
- `assert entry["timestamp"] == "2024-01-15T19:30:00+09:00"`
- UTC+09:00이 아닌 CI 환경에서 실패 가능

### G-3. `caplog` 인자를 받으면서 실제 검증하지 않는 테스트

- `tests/test_data_loader.py:30, 119` — 경고 로그 검증 누락

---

## H. 설정 파일 (심각도: 낮음)

### H-1. `pytest.ini`의 `[coverage:*]` 섹션이 무효할 수 있음

- `pytest.ini:43-53` — coverage.py는 `pytest.ini`에서 설정을 읽지 않음
- `.coveragerc` 또는 `pyproject.toml`의 `[tool.coverage.*]`로 이동 필요

### H-2. `pytest.ini` minversion 불일치

- `pytest.ini:18` — `minversion = 7.0` vs 실제 의존성 `pytest = "^9.0.2"`

---

## 개선 계획

위 발견 사항을 아래 6개 계획서로 분리하여 단계적으로 개선합니다.
모든 계획서는 동작 동일성(behavioral equivalence)을 보장합니다.

| 계획서 | 범위 | 리스크 |
|--------|------|--------|
| Plan 1: 문서/주석/설정 정비 | B, E, H, A-5 항목 | 매우 낮음 |
| Plan 2: 버그 수정 및 방어 코드 보강 | A-1~3 항목 | 낮음 |
| Plan 3: 상수 통합 및 코드 일관성 | D-2, D-8, F 항목 | 낮음~중간 |
| Plan 4: 코드 중복 제거 및 리팩토링 | D-1, D-6, D-7, D-9 항목 | 중간 |
| Plan 5: 테스트 품질 개선 | A-4, G 항목 | 낮음 |
| Plan 6: 최종 통합 검증 | 전체 계획서 통합 검증 | 없음 |

### 향후 과제 (이번 계획서 범위 외)

아래 항목은 대규모 구조 변경으로, 별도의 독립 계획서로 다루는 것을 권장합니다:

- **C-1~3**: CLI 계층 비즈니스 로직 분리 (download_data.py, validate_walkforward_fixed_ab.py, generate_synthetic.py)
- **D-3**: 3개 워크포워드 스크립트 통합
- **D-4, D-5**: simulation.py(2108줄), app_rate_spread_lab.py(1762줄) 파일 분할

---
