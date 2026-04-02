# 5개 계획서 완료 후 검증 보고서

**작성일**: 2026-04-02
**대상 커밋**: `86de002`(Plan 1) ~ `a50fa9a`(Plan 4) — 총 5개 커밋

---

## 1. 완료된 계획서 요약

| # | 계획서 | 커밋 | 핵심 변경 | 테스트 결과 |
|---|--------|------|-----------|-------------|
| 1 | `PLAN_backtest_constants_utils` | `86de002` | 반올림 상수화, 컬럼명 COL_*, MA 함수, 16개 결과 디렉토리 정리, 공용 함수 추출 | 451 passed |
| 2 | `PLAN_backtest_engine_integration` | `b745f53` | pnl_pct 통일, params_schedule while, CAGR -100%, 엔진 통합, filter_valid_rows | 463 passed |
| 3 | `PLAN_backtest_layer_separation` | `33729e7` | CLI 비즈니스 로직 walkforward.py 이동, _update_bands 추출, sources 제거 | 470 passed |
| 4 | `PLAN_type_safety_invariant` | `966fbb1` | type:ignore 4곳 제거, 내부 import 3곳 제거, 불가능 분기 7곳 RuntimeError | 465 passed |
| 5 | `PLAN_defensive_invariant_guards` | `a50fa9a` | simulation 분모 0 방어, entry_price 불변조건, 빈 equity_df 키 보장 | 470 passed |

---

## 2. 실행해야 할 스크립트 목록

### 2-1. 자동 테스트 (필수 - 최우선 실행)

```bash
# 전체 품질 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py
```

**기대 결과**: Ruff 0 errors, PyRight 0 errors, Pytest **passed >= 470, failed=0, skipped=0**

---

### 2-2. 백테스트 스크립트 (사용자 실행)

소스 변경으로 인해 결과가 달라질 수 있는 스크립트만 표시합니다.

#### A. 단일 백테스트 (결과 변경 위험: 낮음)

```bash
poetry run python scripts/backtest/run_single_backtest.py
# 또는 특정 전략만:
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_tqqq
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_tqqq
```

**기대 결과**:
- `storage/results/backtest/{strategy}/` 하위에 signal.csv, equity.csv, trades.csv, summary.json 생성
- **정상 경로 동작은 변경 없음** (리팩토링 + 방어 코드 추가만)
- trades.csv의 컬럼 구성/반올림 규칙은 `csv_export.py` 공용 함수로 통일되었으므로 동일해야 함

**비교 포인트**:
- signal.csv: 동일 (MA, 밴드 계산 로직 불변)
- equity.csv: 동일 (체결 로직 불변)
- trades.csv: 동일 (pnl_pct 단일엔진은 변경 없음, holding_days 계산은 공용 함수로 이동만)
- summary.json: **CAGR 주의** — `final_capital <= 0`인 극단 케이스에서 0.0 -> -100.0 변경됨 (정상 케이스 동일)

#### B. 워크포워드 검증

```bash
poetry run python scripts/backtest/run_walkforward.py
# 또는 특정 전략만:
poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_tqqq
```

**기대 결과**:
- `storage/results/backtest/{strategy}/` 하위에 walkforward_*.csv, walkforward_summary.json 생성
- `wfo_windows_dynamic/`, `wfo_windows_fully_fixed/` 하위에 윈도우별 CSV 생성

**비교 포인트**:
- walkforward_dynamic.csv / walkforward_fully_fixed.csv: 동일 (WFO 로직 불변)
- walkforward_equity_*.csv: 동일 (stitched equity 로직이 CLI에서 walkforward.py로 이동했지만 동작은 동일)
- walkforward_summary.json: 동일
- 윈도우별 CSV: 동일 (비즈니스 로직이 `run_window_detail_backtests()`로 이동했지만 동작은 동일)

#### C. 포트폴리오 백테스트

```bash
poetry run python scripts/backtest/run_portfolio_backtest.py
# 또는 특정 실험만:
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment {experiment_name}
```

**기대 결과**:
- `storage/results/portfolio/{experiment_name}/` 하위에 equity.csv, trades.csv, summary.json, signal_*.csv 생성

**비교 포인트 (주의 필요)**:
- **trades.csv의 pnl_pct**: Plan 2에서 포트폴리오 엔진의 pnl_pct 계산이 변경됨 (`(e_price + EPSILON)` 분모 -> `entry_price` 분모). **미세한 수치 차이 발생 가능** (의도된 버그 수정)
- **equity.csv의 drawdown_pct**: `(peak + EPSILON)` -> `peak.replace(0, EPSILON)` 방식 변경. peak > 0인 정상 케이스에서는 차이 없음
- equity.csv의 equity 값 자체: 동일 (체결 로직 불변, SLIPPAGE_RATE 동일)

#### D. 파라미터 고원 분석

```bash
poetry run python scripts/backtest/run_param_plateau_all.py
# 또는 특정 파라미터만:
poetry run python scripts/backtest/run_param_plateau_all.py --experiment hold_days
```

**기대 결과**:
- `storage/results/backtest/param_plateau/` 하위에 피벗 CSV 생성
- 동일 (데이터 로딩이 `load_signal_trade_pair()`로 통일되었지만 동작은 동일)

### 2-3. TQQQ 시뮬레이션 스크립트

```bash
poetry run python scripts/tqqq/generate_daily_comparison.py
```

**기대 결과**:
- `storage/results/tqqq/tqqq_daily_comparison.csv` 생성
- 동일 (Plan 5에서 분모 0 방어만 추가, 정상 데이터에서는 해당 경로 도달 불가)

---

## 3. 테스트 실행 가이드

### 3-1. 전체 검증 (권장)

```bash
poetry run python validate_project.py
```

정상 결과:
```
Ruff: All checks passed!
PyRight: 0 errors, 0 warnings
Pytest: 470 passed, 0 failed, 0 skipped
```

### 3-2. 변경 영향 범위별 테스트

각 계획서 변경과 관련된 테스트 파일을 개별적으로 실행할 수 있습니다:

**Plan 1 관련 (상수/유틸 인프라)**:
```bash
poetry run pytest tests/test_csv_export.py tests/test_analysis.py tests/test_data_loader.py tests/test_buffer_zone.py tests/test_buffer_zone_contracts.py -v
```

**Plan 2 관련 (엔진 통합/버그 수정)**:
```bash
poetry run pytest tests/test_engine_common.py tests/test_analysis.py tests/test_backtest_engine.py tests/test_portfolio_execution.py tests/test_portfolio_planning.py -v
```

**Plan 3 관련 (계층 분리)**:
```bash
poetry run pytest tests/test_walkforward_schedule.py tests/test_buffer_zone.py tests/test_wfo_stitched.py -v
```

**Plan 4 관련 (타입 안전성)**:
```bash
poetry run pytest tests/test_analysis.py tests/test_portfolio_execution.py -v
```

**Plan 5 관련 (방어 코드)**:
```bash
poetry run pytest tests/test_tqqq_simulation_outputs.py tests/test_engine_common.py tests/test_analysis.py -v
```

### 3-3. 통합 테스트

```bash
poetry run pytest tests/test_integration.py -v
```

---

## 4. 스크립트 재실행 후 결과 파일 변경 분석 (실측)

### 4-1. 전체 요약

| 항목 | 수치 |
|------|------|
| 총 결과 파일 | 390개 |
| **변경된 파일** | **30개** |
| 변경 없는 파일 | 360개 |

### 4-2. 변경된 파일 30개 상세 분류

#### A. meta.json (1개) -- 정상

| 파일 | 변경 원인 | 판정 |
|------|-----------|------|
| `storage/results/meta.json` | 스크립트 재실행 시 타임스탬프 갱신 | **정상** |

#### B. buffer_zone summary.json (4개) -- 정상 (의도된 변경)

| 파일 | 변경 내용 | 판정 |
|------|-----------|------|
| `buffer_zone_gld/summary.json` | `param_source` 구조 변경 | **정상** |
| `buffer_zone_qqq/summary.json` | 동일 | **정상** |
| `buffer_zone_tlt/summary.json` | 동일 | **정상** |
| `buffer_zone_tqqq/summary.json` | 동일 | **정상** |

**변경 내용**: Plan 3에서 `resolve_buffer_params`의 `sources` 딕셔너리를 제거하면서, `param_source`가 4개 필드 딕셔너리에서 단일 문자열 `"FIXED"`로 변경됨.

변경 전:
```json
"param_source": {
    "ma_window": "FIXED",
    "buy_buffer_zone_pct": "FIXED",
    "sell_buffer_zone_pct": "FIXED",
    "hold_days": "FIXED"
}
```

변경 후:
```json
"param_source": "FIXED"
```

**근거**: Plan 3 (`PLAN_backtest_layer_separation`) 목표 -- `resolve_buffer_params`에서 sources 딕셔너리 제거. 모든 파라미터가 항상 `"FIXED"`이므로 의미 있는 정보 손실 없음.

**확인 완료**: 대시보드 앱(`app_single_backtest.py`)에서 `param_source`를 직접 파싱하는 코드 없음 (Grep 검증 완료). 에러 위험 없음.

**추가 발견**: 재실행하지 않은 4개 전략(buffer_zone_efa, buffer_zone_eem, buffer_zone_spy, buffer_zone_iwm)의 summary.json은 여전히 이전 딕셔너리 형태를 유지하고 있음. 전체 전략을 재실행하면 모두 문자열 형태로 통일됨.

#### C. 포트폴리오 trades.csv (25개) -- 정상 (의도된 변경)

모든 `portfolio_*/trades.csv`가 변경되었으며, 두 가지 차이가 있음:

**차이 1: `buy_buffer_pct` 컬럼 추가**

Plan 2에서 `PortfolioTradeRecord` TypedDict를 도입하면서 `buy_buffer_pct` 필드가 추가됨. 모든 값은 `0.0` (포트폴리오 전략은 버퍼존을 사용하지 않으므로 상수값).

이전 컬럼 (11개): `entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, hold_days_used, asset_id, trade_type, holding_days`

현재 컬럼 (12개): `entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, **buy_buffer_pct**, hold_days_used, asset_id, trade_type, holding_days`

**차이 2: 행 순서 변경 (같은 날 체결 내)**

같은 리밸런싱 날짜에 여러 자산이 매도되는 경우, 거래 기록의 순서가 미세하게 변경됨. 이는 `portfolio_execution.py`에서 `order_intents` 딕셔너리 반복 순서가 리팩토링 과정에서 변경되었기 때문.

예시 (portfolio_a1):
```
이전: spy(01-31~05-26), qqq(05-26~09-20), spy(01-31~09-20)
현재: spy(01-31~05-26), spy(01-31~09-20), qqq(05-26~09-20)
```

**수치 값 자체는 동일**: `buy_buffer_pct` 컬럼을 제외하고 정렬하면 내용이 완전히 일치함을 확인 완료.

**판정**: 모두 **정상** (의도된 스키마 변경 + 정렬 순서는 사양 미정의 영역)

### 4-3. 변경 없음 확인 (360개) -- 정상

| 파일 유형 | 개수 | 상태 |
|-----------|------|------|
| 단일 자산 signal.csv (16개) | 16 | 동일 |
| 단일 자산 equity.csv (16개 + split 2개) | 18 | 동일 |
| 단일 자산 trades.csv (16개 + split 2개) | 18 | 동일 |
| 단일 자산 summary.json (16개 + split 2개 - buffer_zone 4개) | 14 | 동일 |
| walkforward CSV (8개) | 8 | 동일 |
| walkforward_summary.json (2개) | 2 | 동일 |
| wfo_windows CSV (~132개) | ~132 | 동일 |
| param_plateau CSV (16개) | 16 | 동일 |
| tqqq_daily_comparison.csv (1개) | 1 | 동일 |
| spread_lab CSV (~20개) | ~20 | 동일 |
| 포트폴리오 equity.csv (25개) | 25 | 동일 |
| 포트폴리오 signal_*.csv (~60개) | ~60 | 동일 |
| 포트폴리오 summary.json (25개) | 25 | 동일 |

---

## 5. 이상 징후 리스트

### 확인 필요 항목 (1건)

| # | 항목 | 내용 | 위험도 |
|---|------|------|--------|
| 1 | `param_source` 형식 불일치 | 재실행한 4개 전략은 문자열 `"FIXED"`, 미실행 4개(efa, eem, spy, iwm)는 딕셔너리 형태 혼재. 전체 재실행으로 통일 권장 | **낮음** (대시보드 미사용 확인) |

### 이상 없음 확인 완료 항목

| 항목 | 결과 |
|------|------|
| 단일 자산 signal/equity/trades CSV | 전부 동일 -- 체결/MA/밴드 로직 불변 확인 |
| walkforward 전체 | 전부 동일 -- WFO 로직 불변 확인 |
| TQQQ 시뮬레이션 | 동일 -- 핵심 로직 불변 확인 |
| 파라미터 고원 분석 | 동일 -- 분석 로직 불변 확인 |
| 포트폴리오 equity/signal/summary | 동일 -- 에쿼티 계산/시그널/성과 지표 불변 확인 |
| 포트폴리오 trades pnl_pct 값 | 동일 (EPSILON 분모 제거 효과가 실제 데이터에서 관측 불가 수준) |

### 대시보드 앱 실행 권장

결과 CSV/JSON을 읽어서 시각화하는 대시보드 앱은 스키마 변경의 영향을 받을 수 있으므로, 아래 앱을 한번씩 실행하여 에러 없이 동작하는지 확인을 권장합니다:

```bash
# 단일 백테스트 대시보드 (param_source 구조 변경 영향 확인)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 포트폴리오 대시보드 (buy_buffer_pct 컬럼 추가 영향 확인)
poetry run streamlit run scripts/backtest/app_portfolio_backtest.py

# 워크포워드 대시보드 (변경 없지만 로직 이동 확인)
poetry run streamlit run scripts/backtest/app_walkforward.py
```
