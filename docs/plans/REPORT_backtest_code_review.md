# 백테스트 코드 리뷰 보고서 (리팩토링 후)

> 작성일: 2026-04-08
> 대상: 대규모 리팩토링 이후 백테스트 도메인 전체
> 분석 범위: `src/qbt/backtest/` (27개 파일) + `scripts/backtest/` (4개 스크립트) + `src/qbt/common_constants.py`
> 참고: `docs/strategy_validation_report.md`

---

## 이전 리팩토링으로 해결된 사항 (확인 완료)

- `csv_export.py` 모듈 추가로 trades/equity/signal CSV 저장 로직 중복 해소
- `run_stitched_equity`, `run_window_detail_backtests`가 `walkforward.py`로 이동하여 CLI 계층 분리 개선
- `BufferStrategyParams`에 `frozen=True` 적용 완료
- `params_schedule` 전환이 `while` 루프로 수정 완료
- 포트폴리오 엔진이 `engine_common.py`의 `execute_sell_order`를 공유하여 pnl_pct 계산 통일
- `PortfolioTradeRecord` TypedDict 정의 완료
- `COL_EQUITY`, `COL_PNL`, `COL_ENTRY_DATE`, `COL_EXIT_DATE` 등 핵심 컬럼명 상수화 완료
- `ROUND_PRICE`, `ROUND_PERCENT` 등 반올림 상수 정의 완료

---

## 1. 문서 규칙 위반 사항

### 1-1. [중간] 계층 분리 위반 — CLI에 비즈니스 로직 잔존

- **파일**: `scripts/backtest/run_portfolio_backtest.py:51-156`
- `_build_execution_comparison_df()` 함수가 자산별 체결 전후 비중/평가액/수량 비교를 계산하는 비즈니스 로직을 포함
- CLAUDE.md 규칙: "CLI 계층에 도메인 로직 포함 금지"

### 1-2. [낮음] CLAUDE.md 문서와 코드 불일치

- **파일**: `src/qbt/backtest/types.py:17`
- docstring에 `strategy_common.py: HoldState`라고 기재되어 있으나, 실제 `HoldState`는 `buffer_zone_helpers.py`에 정의됨
- 이전 리팩토링 후 docstring이 업데이트되지 않음

### 1-3. [정보] 상수 명명 규칙과 현실의 괴리

CLAUDE.md에서 "4가지 접두사만 사용" (`COL_`, `KEY_`, `DISPLAY_`, `DEFAULT_`)으로 명시하고 있으나, `constants.py`의 상당수 상수가 이 카테고리에 맞지 않음:

| 상수 | 현재 이름 | 비고 |
|------|-----------|------|
| 슬리피지 | `SLIPPAGE_RATE` | 제약조건 성격, DEFAULT_ 부적합 |
| MDD=0 대용 | `CALMAR_MDD_ZERO_SUBSTITUTE` | 수치 안정성 상수 |
| 확정 파라미터 | `FIXED_4P_MA_WINDOW` 등 | 확정값 성격 |
| 제약조건 | `MIN_BUY_BUFFER_ZONE_PCT` 등 | 하한선 성격 |
| 파일명 | `WALKFORWARD_DYNAMIC_FILENAME` 등 | 파일명 상수 |
| 반올림 | `ROUND_PRICE` 등 | 반올림 규칙 |

**판단**: 문서 규칙 자체가 현실의 상수 유형을 충분히 커버하지 못함. 규칙 확장 또는 현행 유지 중 선택 필요.

---

## 2. 논리적 오류 및 잠재적 버그

### 2-1. [중간] _update_bands 이중 호출 시 상태 오염 위험

- **파일**: `src/qbt/backtest/strategies/buffer_zone.py:302-347`
- `_update_bands()`는 호출될 때마다 `_prev_upper`/`_prev_lower`를 현재 값으로 갱신
- 같은 `i`에서 `check_buy()`와 `check_sell()`을 순서대로 호출하면, 두 번째 호출 시 prev 값이 이미 덮어써져 돌파 감지 실패
- 현재 엔진은 포지션 유무에 따라 한쪽만 호출하므로 문제 없으나, **Protocol 계약에 이 제약이 문서화되어 있지 않음**
- 향후 양쪽을 모두 호출하는 코드가 추가되면 버그 발생

### 2-2. [중간] walkforward.py에서 ma_type 리터럴과 상수 혼용

- `src/qbt/backtest/walkforward.py:679` — `run_stitched_equity()` 내 `ma_type="ema"` 리터럴
- `src/qbt/backtest/walkforward.py:747` — `run_window_detail_backtests()` 내 `ma_type="ema"` 리터럴
- `src/qbt/backtest/walkforward.py:294` — `run_walkforward()` 내에서는 `DEFAULT_BUFFER_MA_TYPE` 상수 사용
- **같은 파일에서 상수를 import하고 있으면서 2개 함수에서만 리터럴 사용** → `DEFAULT_BUFFER_MA_TYPE` 값 변경 시 동기화 깨짐

### 2-3. [중간] run_walkforward.py에서 반올림 매직넘버 잔존

- `scripts/backtest/run_walkforward.py:227-231,242-246`
- `6`, `2`, `0`, `4` 등의 매직넘버로 반올림 자릿수 직접 기재
- 같은 계층의 `run_single_backtest.py`와 `run_portfolio_backtest.py`는 `ROUND_PRICE`, `ROUND_PERCENT` 등 상수를 사용
- **동일 계층 스크립트 간 불일치**

### 2-4. [중간] portfolio_engine.py — weight 계산 비대칭

- `portfolio_engine.py:355` — equity_rows: `val / (current_equity + EPSILON)` (current_equity > 0 검사 없음)
- `portfolio_engine.py:385` — state_log: `val / (current_equity + EPSILON) if current_equity > 0 else 0.0`
- equity_rows에서 current_equity=0일 때 EPSILON으로 나누면 매우 큰 weight 기록 가능
- 실질적으로 `portfolio_rebalance.py:56`에서 RuntimeError로 도달 불가이나, 방어 로직 비대칭

### 2-5. [낮음] run_walkforward.py — OHLC 컬럼명 리터럴 사용

- `scripts/backtest/run_walkforward.py:224` — `"Open"`, `"High"`, `"Low"`, `"Close"` 리터럴
- `COL_DATE`는 import하여 사용하면서 나머지 OHLC 상수(`COL_OPEN`, `COL_HIGH`, `COL_LOW`, `COL_CLOSE`)는 누락

### 2-6. [낮음] run_walkforward.py — 불필요한 이중 타입 변환

- `scripts/backtest/run_walkforward.py:79-80` — `Path(str(config["signal_path"]))` (이미 Path 타입인 값을 str→Path)
- `scripts/backtest/run_walkforward.py:380` — 동일 패턴

### 2-7. [낮음] walkforward.py — generate_wfo_windows()의 미사용 변수

- `src/qbt/backtest/walkforward.py:117,145` — `window_idx` 변수가 while 루프 내에서 증가하지만 어디서도 참조되지 않음

### 2-8. [낮음] portfolio_engine.py — dead code

- `portfolio_engine.py:442-443` — `if "trade_type" not in trades_df.columns: trades_df["trade_type"] = "signal"`
- `PortfolioTradeRecord`에 `trade_type`이 필수 필드이므로 trades가 있으면 항상 존재. 도달 불가능한 코드

### 2-9. [낮음] portfolio_engine.py — 빈 trades_df 컬럼과 PortfolioTradeRecord 필드 불일치

- `portfolio_engine.py:445-458` — 빈 DataFrame 생성 시 컬럼 목록이 `PortfolioTradeRecord`의 `pre_shares`, `post_shares`, `order_amount` 필드를 누락할 가능성
- 거래 0건 시 빈 DataFrame의 컬럼 구조가 거래 있는 경우와 다를 수 있음

---

## 3. 상수화 / 통합함수 / 모듈화 리팩토링 대상

### 3-1. [높음] TradeRecord 키 문자열 리터럴 상수화 미완

`COL_ENTRY_DATE`, `COL_EXIT_DATE`, `COL_PNL`은 상수화되었으나, 나머지 키들이 3개 이상 파일에서 리터럴로 반복:

| 리터럴 | 반복 파일 수 | 비고 |
|--------|:----------:|------|
| `"entry_price"` | 3+ | engine_common, portfolio_execution, csv_export |
| `"exit_price"` | 3+ | 동일 |
| `"shares"` | 3+ | 동일 |
| `"pnl_pct"` | 3+ | 동일 |
| `"buy_buffer_pct"` | **8개** | 가장 광범위, 오타 위험 최대 |
| `"hold_days_used"` | 3+ | engine_common, csv_export, buffer_zone |
| `"holding_days"` | 2+ | analysis, csv_export |

도메인 내 2개 이상 파일에서 사용되므로 `constants.py`에 `COL_*` 상수 정의 대상.

### 3-2. [높음] "drawdown_pct", "change_pct" 등 파생 컬럼명 반복

| 리터럴 | 반복 위치 | 비고 |
|--------|----------|------|
| `"drawdown_pct"` | 2개 비즈니스 파일 + 3개 스크립트 | 계산 + 저장 양쪽에서 사용 |
| `"change_pct"` | 3개 스크립트 | CSV 저장 전 계산 시 사용 |

### 3-3. [중간] holding_days 계산 중복

동일한 holding_days 계산 로직이 2곳에서 반복:

- `analysis.py:324-328` — `regime_trades["holding_days"] = regime_trades.apply(lambda row: (row[COL_EXIT_DATE] - row[COL_ENTRY_DATE]).days, axis=1)`
- `csv_export.py:40` — `export["holding_days"] = export.apply(lambda row: (row[COL_EXIT_DATE] - row[COL_ENTRY_DATE]).days, axis=1)`

공용 함수로 추출 가능.

### 3-4. [중간] equity_df 밴드 보강 로직 중복

- `runners.py:60-94` — `_enrich_equity_with_bands()` 함수
- `walkforward.py:786-794` — 동일한 upper/lower band + buffer_pct 컬럼 추가 로직

`runners.py`의 함수를 `walkforward.py`에서 재사용 가능.

### 3-5. [중간] 데이터 로딩 패턴 중복 잔존

signal/trade 데이터 로딩 + overlap 처리 패턴이 여전히 2곳에서 반복:

- `scripts/backtest/run_walkforward.py:76-89` — `_load_data()` 함수
- `scripts/backtest/run_param_plateau_all.py:146-167` — `_load_asset_data()` 함수

`data_loader.py`의 `load_signal_trade_pair()` 등으로 통합 가능.

### 3-6. [중간] portfolio_engine.py — state_log 행 생성 코드 중복

- `portfolio_engine.py:345-434` — 90행에 달하는 state_log 행 생성
- equity_rows 생성(345-363)과 state_log_rows 생성(366-434)에서 동일한 val 계산(`position * close`) 반복

### 3-7. [중간] "rebalance" / "signal" 문자열 리터럴 반복

- `portfolio_execution.py:126`, `portfolio_engine.py:443,467` 등에서 `"signal"`, `"rebalance"`, `"asset_id"`, `"trade_type"` 리터럴 반복
- 상수화 미적용

### 3-8. [중간] walkforward.py — grid_df 접근 시 COL_ 상수 미사용

- `walkforward.py:220-224,326-329` — `"ma_window"`, `"buy_buffer_zone_pct"` 등 리터럴로 grid_df 컬럼 접근
- `COL_MA_WINDOW`, `COL_BUY_BUFFER_ZONE_PCT` 등이 `constants.py`에 이미 정의되어 있으나 미사용

### 3-9. [낮음] common_constants.py — tqqq 전용 상수 잔존

- `DISPLAY_DATE` (77행) — tqqq 도메인 파일에서만 사용, backtest에서 미사용
- `COL_VOLUME` (65행) — `tqqq/simulation.py`에서만 직접 사용 (단, `REQUIRED_COLUMNS`에 포함되어 간접 사용)
- tqqq 도메인 전용 상수로 이동 적합

### 3-10. [낮음] portfolio_execution.py — 상수/리터럴 혼용

- `portfolio_execution.py:115-129` — 같은 `PortfolioTradeRecord` 딕셔너리 내에서 `COL_ENTRY_DATE`(상수)와 `"entry_price"`(리터럴)가 혼용

---

## 4. 요약

### 전체 통계

| 카테고리 | 건수 | 긴급 | 높음 | 중간 | 낮음/정보 |
|---------|:----:|:----:|:----:|:----:|:--------:|
| 문서 규칙 위반 | 3건 | 0 | 0 | 1 | 2 |
| 논리적 오류/버그 | 9건 | 0 | 0 | 4 | 5 |
| 리팩토링 대상 | 10건 | 0 | 2 | 6 | 2 |
| **합계** | **22건** | **0** | **2** | **11** | **9** |

### 핵심 발견

이전 리팩토링으로 **긴급/높음 수준의 버그와 아키텍처 위반은 모두 해소**되었다. 잔존 이슈는 주로:

1. **상수화 미완**: `"entry_price"`, `"exit_price"`, `"buy_buffer_pct"` 등 TradeRecord 관련 키가 여전히 리터럴로 반복 (3-1, 3-2)
2. **리터럴/상수 혼용**: walkforward.py의 `ma_type="ema"`, run_walkforward.py의 반올림 매직넘버 (2-2, 2-3)
3. **소규모 중복**: holding_days 계산, 밴드 보강, 데이터 로딩 패턴 (3-3, 3-4, 3-5)
4. **방어적 개선**: `_update_bands` Protocol 제약 문서화, weight 계산 비대칭 (2-1, 2-4)

### 긍정적 평가

- **핵심 비즈니스 규칙 완전 준수**: 체결 타이밍, Pending Order, hold_days, Equity 정의, 비용 모델
- **두 엔진 간 계산 일관성 확보**: pnl_pct 통일, `execute_sell_order` 공유
- **계층 분리 대폭 개선**: stitched equity/window detail 로직이 src로 이동
- **CSV 저장 로직 통합**: `csv_export.py` 모듈로 중복 해소
- **ERROR 로그 규칙 준수**: 비즈니스 로직 계층에서 ERROR 로그 사용 없음
- **데이터 불변성 전반 준수**: df.copy() 적절히 사용
