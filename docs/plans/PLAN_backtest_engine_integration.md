# Implementation Plan: 백테스트 버그 수정 + 엔진 통합

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

**작성일**: 2026-04-02 22:30
**마지막 업데이트**: 2026-04-02 23:45
**관련 범위**: backtest/engines, backtest/analysis, backtest/runners, backtest/walkforward, utils
**관련 문서**: `docs/plans/REPORT_backtest_code_review.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] `execute_buy_order`, `execute_sell_order`를 순수 계산 함수로 리팩토링하고 미사용 `order` 파라미터 제거 (리포트 2-7)
- [x] 포트폴리오 엔진이 `engine_common.py`의 체결 함수를 호출하도록 통합 (리포트 1-3, 확정 방침 5-1 A안)
- [x] pnl_pct 계산 방식 통일 — 포트폴리오 엔진의 `(e_price + EPSILON)` 분모를 `entry_price` 분모로 변경 (리포트 2-1)
- [x] 포트폴리오 거래 기록에 `PortfolioTradeRecord` TypedDict 적용 — `dict[str, Any]` 제거 (리포트 3-16)
- [x] `params_schedule` 전환 로직을 `if` → `while`로 변경하여 건너뛴 날짜 안전 처리 (리포트 2-2)
- [x] drawdown 방어 로직 통일 — `portfolio_data.py`를 `calculate_drawdown_pct_series()` 호출로 변경 (리포트 2-4)
- [x] `compute_bands` 이중 호출 → 1회 호출로 최적화 (리포트 2-5)
- [x] CAGR 계산: `final_capital ≤ 0` 시 `-100.0` 반환으로 변경 (리포트 2-8)
- [x] 유효 행 필터링 패턴을 `filter_valid_rows()` 헬퍼로 추출 (리포트 3-8)
- [x] `trade_df` 마스크를 독립 날짜 기반으로 변경 (리포트 2-3)
- [x] 미사용 `asset_closes_map` 파라미터 제거 (리포트 3-17)

## 2) 비목표(Non-Goals)

- `run_walkforward.py` 비즈니스 로직 이동 (Plan 3 범위: 리포트 1-2, 5-2)
- `resolve_buffer_params` sources 제거 (Plan 3 범위: 리포트 3-12)
- `check_buy`/`check_sell` 밴드 계산 → `_update_bands` 추출 (Plan 3 범위: 리포트 3-11, 2-6)
- `PortfolioResult.config` 빈 기본값 제거 (Plan 3 범위: 리포트 2-12)
- `PendingOrder` re-export 제거 (Plan 3 범위: 리포트 3-18)
- 포트폴리오 데이터 로딩 중복 → 헬퍼 추출 (Plan 3 범위: 리포트 3-9)
- 기존 테스트의 대규모 리팩토링
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`REPORT_backtest_code_review.md`에서 식별된 잠재 버그, 계산 불일치, 엔진 간 아키텍처 위반을 해결한다. Plan 1(상수/유틸 인프라 정비)이 완료되어 새 상수와 공용 함수를 활용할 수 있는 상태이다.

**계산 불일치 (높음)**:

- **pnl_pct**: 단일 엔진(`engine_common.py:164`)은 `(sell_price - entry_price) / entry_price`, 포트폴리오 엔진(`portfolio_execution.py:123`)은 `(sell_price - e_price) / (e_price + EPSILON)`. 동일 거래에서 미세한 수치 차이 발생 가능. `entry_price`가 0인 것은 비정상 상태이며 EPSILON 추가는 오히려 결과를 왜곡할 수 있음
- **drawdown 방어**: `analysis.py:184`는 `peak.replace(0, EPSILON)`, `portfolio_data.py:84`는 `(peak + EPSILON)`. 동일 목적(분모 0 방지)이지만 다른 산식으로 미세한 수치 차이 가능

**잠재 버그 (높음/중간)**:

- **params_schedule 전환**: `backtest_engine.py:302-305`에서 `if`문으로 한 번에 1개씩만 전환. 데이터 갭이 있어 여러 전환 날짜를 건너뛰어야 하는 경우, 의도하지 않은 중간 전략이 적용될 수 있음
- **CAGR=0**: `analysis.py:174`에서 `final_capital ≤ 0` 시 CAGR을 `0.0`으로 반환하지만, 실제로는 전액 손실이므로 `-100.0`이 정확
- **trade_df 마스크**: `walkforward.py:294, 332`에서 `signal_df_with_ma`로 생성한 boolean 마스크를 `trade_df`에 그대로 적용. 인덱스 정합성에 대한 암묵적 가정

**아키텍처 위반 (높음)**:

- **engine_common 미사용**: 포트폴리오 엔진이 `execute_buy_order()`, `execute_sell_order()` 등 공유 함수를 사용하지 않고 독자적으로 체결 로직 구현. SLIPPAGE_RATE 적용, `TradeRecord` TypedDict 미사용, pnl_pct 계산 차이 발생
- **미사용 파라미터**: `execute_buy_order`/`execute_sell_order`의 `order: PendingOrder` 파라미터가 본문에서 사용되지 않음 (YAGNI 위반)

**코드 중복 / 비효율**:

- **유효 행 필터링**: `_run_backtest_for_grid`(176-179행)과 `run_buffer_strategy`(535-537행)에서 동일 패턴 반복
- **compute_bands 이중 호출**: `runners.py:85-86`에서 같은 MA 값으로 `compute_bands()`를 2회 호출하여 각각 `[0]`, `[1]`만 사용
- **미사용 파라미터**: `compute_projected_portfolio()`의 `asset_closes_map` 파라미터가 본문에서 사용되지 않음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`: 계층 분리 원칙, 데이터 불변성, 반올림 규칙, 상수 관리
- `src/qbt/backtest/CLAUDE.md`: 체결 타이밍 규칙, Equity 정의, Pending Order 정책, 비용 모델
- `src/qbt/utils/CLAUDE.md`: 유틸리티 패키지 설계 원칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 부동소수점 비교, 파일 격리)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `execute_buy_order(open_price, amount)` → `(shares, buy_price, cost)` 순수 계산 함수로 변경, `order` 파라미터 제거
- [x] `execute_sell_order(open_price, shares_to_sell, entry_price)` → `(sell_price, proceeds, pnl, pnl_pct)` 순수 계산 함수로 변경, `order` 파라미터 제거
- [x] `create_trade_record()` 헬퍼 함수가 `engine_common.py`에 존재
- [x] `PortfolioTradeRecord` TypedDict가 `engine_common.py`에 존재하고 `portfolio_execution.py`가 사용
- [x] `portfolio_execution.py`의 SELL/BUY 체결이 `execute_buy_order`/`execute_sell_order` 호출
- [x] pnl_pct 계산이 두 엔진에서 동일: `(sell_price - entry_price) / entry_price`
- [x] `params_schedule` 전환이 `while` 루프로 누적 건너뛰기 처리
- [x] drawdown 방어 로직이 `calculate_drawdown_pct_series()` 호출로 통일
- [x] `compute_bands` 1회 호출로 upper/lower 동시 계산
- [x] CAGR: `final_capital ≤ 0` → `-100.0` 반환
- [x] `filter_valid_rows()` 헬퍼가 `backtest_engine.py`에 존재하고 2곳이 사용
- [x] `trade_df` 마스크가 독립 날짜 컬럼 기반으로 적용 (`walkforward.py`)
- [x] `compute_projected_portfolio()`에서 `asset_closes_map` 파라미터 제거
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=463, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (backtest CLAUDE.md, tests CLAUDE.md)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**src/qbt/backtest/ (비즈니스 로직)**:

| 파일 | 변경 내용 |
|------|-----------|
| `engines/engine_common.py` | `execute_buy_order`/`execute_sell_order` 순수 계산 함수로 리팩토링, `order` 파라미터 제거, `create_trade_record()` 추가, `PortfolioTradeRecord` TypedDict 추가 |
| `engines/backtest_engine.py` | 체결 함수 호출부 업데이트, `params_schedule` while 루프, `filter_valid_rows()` 헬퍼 추출 |
| `engines/portfolio_execution.py` | `execute_buy_order`/`execute_sell_order` 호출로 전환, `PortfolioTradeRecord` 사용, pnl_pct 통일 |
| `engines/portfolio_data.py` | drawdown → `calculate_drawdown_pct_series()` 호출 |
| `engines/portfolio_planning.py` | `asset_closes_map` 파라미터 제거 |
| `engines/portfolio_engine.py` | `compute_projected_portfolio()` 호출부에서 `asset_closes_map` 인자 제거 |
| `analysis.py` | CAGR: `final_capital ≤ 0` → `-100.0` |
| `runners.py` | `compute_bands` 1회 호출 최적화 |
| `walkforward.py` | `trade_df` 마스크 독립 날짜 기반으로 변경 |

**tests/**:

| 파일 | 변경 내용 |
|------|-----------|
| `test_engine_common.py` | 기존 테스트 시그니처 업데이트 + 순수 계산 함수 테스트 추가 |
| `test_analysis.py` | CAGR -100% 테스트 추가 |
| `test_portfolio_execution.py` | engine_common 호출 검증, PortfolioTradeRecord 검증 |
| `test_portfolio_planning.py` | `asset_closes_map` 제거 반영 |
| `test_backtest_engine.py` (신규 또는 기존) | params_schedule while 테스트, filter_valid_rows 테스트 |

**문서**:

| 파일 | 변경 내용 |
|------|-----------|
| `src/qbt/backtest/CLAUDE.md` | engine_common 함수 시그니처, PortfolioTradeRecord, filter_valid_rows 반영 |
| `tests/CLAUDE.md` | 신규 테스트 파일 추가 (해당 시) |
| `README.md` | 변경 없음 (내부 리팩토링) |

### 데이터/결과 영향

- **pnl_pct 수치 변경**: 포트폴리오 엔진의 pnl_pct가 미세하게 변경됨 (`EPSILON` 분모 제거). 이는 의도된 버그 수정
- **CAGR 변경**: `final_capital ≤ 0`인 극단 손실 케이스에서 0.0 → -100.0으로 변경. 실제 발생 가능성 극히 낮음
- **drawdown_pct 수치 변경**: `portfolio_data.py`의 drawdown_pct가 `peak+EPSILON` → `peak.replace(0, EPSILON)` 방식으로 변경. peak>0인 정상 케이스에서 차이 없음
- **기능 동작**: 체결 로직의 동작은 동일 (SLIPPAGE_RATE, shares 계산 공식 불변). 리팩토링 전후 동일 결과 보장

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 고정 (레드)

> 새로운 함수 시그니처, 변경될 동작, 신규 헬퍼의 계약을 테스트로 먼저 고정한다.
> 구현이 아직 없으므로 레드(실패) 상태가 허용된다.

**작업 내용**:

- [x] `test_analysis.py`에 CAGR -100% 테스트 추가 (2-8)
  - `final_capital=0, years>0` → `cagr == pytest.approx(-100.0, abs=0.1)` 검증
  - `final_capital` 매우 작은 양수 (예: 0.01) → CAGR이 매우 큰 음수 검증

- [x] `test_engine_common.py`에 순수 계산 함수 테스트 추가 (2-7, 2-1)
  - `test_execute_buy_order_pure_calculation`: `execute_buy_order(open_price=100.0, amount=10000.0)` → `(shares, buy_price, cost)` 검증. `buy_price == 100.0 * 1.003`, `shares == int(10000 / buy_price)`, `cost == shares * buy_price`
  - `test_execute_buy_order_insufficient_funds`: `amount`이 `buy_price`보다 작을 때 → `shares=0, cost=0.0`
  - `test_execute_sell_order_pure_calculation`: `execute_sell_order(open_price=100.0, shares_to_sell=10, entry_price=95.0)` → `(sell_price, proceeds, pnl, pnl_pct)` 검증. `sell_price == 100.0 * 0.997`, `pnl_pct == (sell_price - 95.0) / 95.0`
  - `test_execute_sell_order_partial_sell`: `shares_to_sell < total_position` 시 부분 매도 정확성
  - `test_pnl_pct_no_epsilon_in_denominator`: pnl_pct 분모에 EPSILON이 없음을 확인 — `entry_price=100.0` 기준 pnl_pct가 `(sell - 100) / 100`과 정확히 일치
  - `test_create_trade_record`: 헬퍼 함수가 올바른 `TradeRecord` TypedDict 반환

- [x] `test_backtest_engine.py` (신규 또는 기존)에 params_schedule while 테스트 추가 (2-2)
  - `test_params_schedule_skips_multiple_dates`: 데이터 갭으로 2개 전환 날짜를 동시에 건너뛸 때, 최종 전략만 적용되는지 검증

- [x] `test_backtest_engine.py`에 filter_valid_rows 테스트 추가 (3-8)
  - `test_filter_valid_rows_removes_nan`: MA NaN 행 제거 후 signal/trade 동일 행수 검증
  - `test_filter_valid_rows_all_valid`: NaN 없으면 원본과 동일

---

### Phase 1 — 단독 수정 (그린 전환 1)

> 독립적으로 수정 가능한 버그/비효율을 처리한다.
> Phase 0의 일부 테스트(2-2, 2-8, 3-8)가 이 Phase에서 GREEN으로 전환된다.

**1-a. params_schedule 전환 if → while (리포트 2-2)**:

- [x] `backtest_engine.py` 302-305행: `if` → `while` 변경

변경 전:
```python
if current_date >= sorted_switch_dates[next_switch_idx]:
    strategy = params_schedule[sorted_switch_dates[next_switch_idx]]
    next_switch_idx += 1
```

변경 후:
```python
while (
    next_switch_idx < len(sorted_switch_dates)
    and current_date >= sorted_switch_dates[next_switch_idx]
):
    strategy = params_schedule[sorted_switch_dates[next_switch_idx]]
    next_switch_idx += 1
```

외부 `if params_schedule is not None and next_switch_idx < len(sorted_switch_dates):` 조건은 유지하되, 내부만 `while`로 변경.

**1-b. compute_bands 1회 호출 (리포트 2-5)**:

- [x] `runners.py` 85-86행: 2회 호출 → 1회 호출 + unpack

변경 전:
```python
band_df[COL_UPPER_BAND] = band_df[ma_col].apply(lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[0])
band_df[COL_LOWER_BAND] = band_df[ma_col].apply(lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[1])
```

변경 후:
```python
bands = band_df[ma_col].apply(lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct))
band_df[COL_UPPER_BAND] = bands.apply(lambda b: b[0])
band_df[COL_LOWER_BAND] = bands.apply(lambda b: b[1])
```

**1-c. CAGR -100% (리포트 2-8)**:

- [x] `analysis.py` 174-177행: 조건 변경

변경 전:
```python
if years > 0 and final_capital > 0:
    cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
else:
    cagr = 0.0
```

변경 후:
```python
if years > 0 and final_capital > 0:
    cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
elif years > 0 and final_capital <= 0:
    cagr = -100.0
else:
    cagr = 0.0
```

**1-d. drawdown 방어 로직 통일 (리포트 2-4)**:

- [x] `portfolio_data.py` 83-84행: 인라인 계산 → `calculate_drawdown_pct_series()` 호출

변경 전:
```python
peak = equity_df[COL_EQUITY].cummax()
equity_df["drawdown_pct"] = (equity_df[COL_EQUITY] - peak) / (peak + EPSILON) * 100.0
```

변경 후:
```python
equity_df["drawdown_pct"] = calculate_drawdown_pct_series(equity_df[COL_EQUITY])
```

`analysis.py`의 `calculate_drawdown_pct_series()`는 Plan 1에서 이미 `peak.replace(0, EPSILON)` 방식으로 구현됨. import 추가 필요.

**1-e. trade_df 마스크 독립 날짜 기반 (리포트 2-3)**:

- [x] `walkforward.py` 294행: `trade_df[is_mask]` → 독립 날짜 마스크

변경 전:
```python
is_mask = (signal_df_with_ma[COL_DATE] >= is_start) & (signal_df_with_ma[COL_DATE] <= is_end)
is_signal = signal_df_with_ma[is_mask].reset_index(drop=True)
is_trade = trade_df[is_mask].reset_index(drop=True)
```

변경 후:
```python
is_mask = (signal_df_with_ma[COL_DATE] >= is_start) & (signal_df_with_ma[COL_DATE] <= is_end)
is_signal = signal_df_with_ma[is_mask].reset_index(drop=True)
is_trade_mask = (trade_df[COL_DATE] >= is_start) & (trade_df[COL_DATE] <= is_end)
is_trade = trade_df[is_trade_mask].reset_index(drop=True)
```

- [x] `walkforward.py` 332행: OOS도 동일 패턴 적용
- [x] `walkforward.py` 339행: `oos_valid_mask`도 `oos_trade`의 자체 날짜 기반으로 변경

```python
# 변경 전
oos_valid_mask = oos_signal[oos_ma_col].notna()
oos_trade_valid = oos_trade[oos_valid_mask].reset_index(drop=True)

# 변경 후: trade_df의 자체 날짜 기반 필터링
oos_valid_dates = oos_signal[oos_signal[oos_ma_col].notna()][COL_DATE]
oos_signal_valid = oos_signal[oos_signal[oos_ma_col].notna()].reset_index(drop=True)
oos_trade_valid = oos_trade[oos_trade[COL_DATE].isin(oos_valid_dates)].reset_index(drop=True)
```

**1-f. filter_valid_rows 헬퍼 추출 (리포트 3-8)**:

- [x] `backtest_engine.py`에 헬퍼 함수 추가

```python
def filter_valid_rows(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """MA 컬럼 기준으로 유효 행(NaN 아닌 행)만 필터링한다.

    signal_df와 trade_df에서 ma_col이 NaN인 행을 제거하고,
    인덱스를 재설정하여 두 DataFrame의 행 정합성을 유지한다.

    Args:
        signal_df: 시그널 DataFrame (MA 컬럼 포함)
        trade_df: 매매 DataFrame
        ma_col: 유효성 기준이 되는 MA 컬럼명

    Returns:
        (filtered_signal, filtered_trade) 튜플
    """
    valid_mask = signal_df[ma_col].notna()
    return (
        signal_df[valid_mask].reset_index(drop=True),
        trade_df[valid_mask].reset_index(drop=True),
    )
```

- [x] `_run_backtest_for_grid` (176-179행): `filter_valid_rows()` 호출로 교체
- [x] `run_buffer_strategy` (535-537행): `filter_valid_rows()` 호출로 교체

**1-g. asset_closes_map 파라미터 제거 (리포트 3-17)**:

- [x] `portfolio_planning.py` 171행: `compute_projected_portfolio()` 시그니처에서 `asset_closes_map` 제거
- [x] `portfolio_planning.py` docstring에서 `asset_closes_map` 관련 설명 제거
- [x] `portfolio_engine.py` 345행: 호출부에서 `asset_closes_map` 인자 제거
- [x] `test_portfolio_planning.py`: 테스트 호출부에서 `asset_closes_map` 인자 제거

---

### Phase 2 — 엔진 통합 (그린 전환 2)

> `engine_common.py`의 체결 함수를 순수 계산 함수로 리팩토링하고,
> 포트폴리오 엔진이 이를 호출하도록 통합한다.
> Phase 0의 나머지 테스트(2-7, 2-1)가 이 Phase에서 GREEN으로 전환된다.

**2-a. engine_common.py 함수 리팩토링 (리포트 2-7)**:

- [x] `execute_buy_order()` 순수 계산 함수로 변경

변경 전:
```python
def execute_buy_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
) -> tuple[int, float, float, date, bool]:
```

변경 후:
```python
def execute_buy_order(
    open_price: float,
    amount: float,
) -> tuple[int, float, float]:
    """매수 체결 계산. 상태 업데이트는 호출부에서 수행한다.

    Args:
        open_price: 시가 (슬리피지 적용 전)
        amount: 매수에 사용할 금액

    Returns:
        (shares, buy_price, total_cost) 튜플.
        shares=0이면 금액 부족으로 미체결.
    """
    buy_price = open_price * (1 + SLIPPAGE_RATE)
    shares = int(amount / buy_price)
    if shares <= 0:
        return (0, buy_price, 0.0)
    cost = shares * buy_price
    return (shares, buy_price, cost)
```

- [x] `execute_sell_order()` 순수 계산 함수로 변경

변경 전:
```python
def execute_sell_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
    entry_price: float,
    entry_date: date,
    hold_days_used: int,
    buy_buffer_pct: float = 0.0,
) -> tuple[int, float, TradeRecord]:
```

변경 후:
```python
def execute_sell_order(
    open_price: float,
    shares_to_sell: int,
    entry_price: float,
) -> tuple[float, float, float, float]:
    """매도 체결 계산. 상태 업데이트는 호출부에서 수행한다.

    Args:
        open_price: 시가 (슬리피지 적용 전)
        shares_to_sell: 매도할 수량
        entry_price: 진입가

    Returns:
        (sell_price, proceeds, pnl, pnl_pct) 튜플.
    """
    sell_price = open_price * (1 - SLIPPAGE_RATE)
    proceeds = shares_to_sell * sell_price
    pnl = (sell_price - entry_price) * shares_to_sell
    pnl_pct = (sell_price - entry_price) / entry_price
    return (sell_price, proceeds, pnl, pnl_pct)
```

- [x] `create_trade_record()` 헬퍼 함수 추가

```python
def create_trade_record(
    entry_date: date,
    exit_date: date,
    entry_price: float,
    exit_price: float,
    shares: int,
    pnl: float,
    pnl_pct: float,
    buy_buffer_pct: float = 0.0,
    hold_days_used: int = 0,
) -> TradeRecord:
    """TradeRecord TypedDict를 생성한다."""
    return {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "shares": shares,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "buy_buffer_pct": buy_buffer_pct,
        "hold_days_used": hold_days_used,
    }
```

- [x] `PortfolioTradeRecord` TypedDict 추가 (리포트 3-16)

```python
class PortfolioTradeRecord(TradeRecord):
    """포트폴리오 전용 거래 기록. TradeRecord를 확장한다."""

    asset_id: str
    trade_type: str  # "signal" | "rebalance"
```

**2-b. backtest_engine.py 호출부 업데이트**:

- [x] `run_backtest()` 내 매수 체결 코드 업데이트 (312-318행)

변경 전:
```python
position, capital, entry_price, entry_date, success = execute_buy_order(
    pending_order, float(trade_row[COL_OPEN]), current_date, capital, position
)
```

변경 후:
```python
shares, buy_price, cost = execute_buy_order(
    float(trade_row[COL_OPEN]), capital
)
if shares > 0:
    position = shares
    capital -= cost
    entry_price = buy_price
    entry_date = current_date
    if log_trades:
        logger.debug(...)
```

- [x] `run_backtest()` 내 매도 체결 코드 업데이트 (322-332행)

변경 전:
```python
position, capital, trade_record = execute_sell_order(
    pending_order, float(trade_row[COL_OPEN]), current_date,
    capital, position, entry_price, entry_date,
    hold_days_used=entry_hold_days_used, buy_buffer_pct=entry_buy_buffer_pct,
)
```

변경 후:
```python
sell_price, proceeds, pnl, pnl_pct = execute_sell_order(
    float(trade_row[COL_OPEN]), position, entry_price
)
capital += proceeds
trade_record = create_trade_record(
    entry_date=entry_date,
    exit_date=current_date,
    entry_price=entry_price,
    exit_price=sell_price,
    shares=position,
    pnl=pnl,
    pnl_pct=pnl_pct,
    buy_buffer_pct=entry_buy_buffer_pct,
    hold_days_used=entry_hold_days_used,
)
trades.append(trade_record)
position = 0
```

**2-c. portfolio_execution.py engine_common 통합 (리포트 1-3, 2-1, 3-10)**:

- [x] SELL 단계: `execute_sell_order()` 호출로 전환 (100-127행)

변경 전:
```python
sell_price = open_price * (1.0 - SLIPPAGE_RATE)
# ... 인라인 계산 ...
"pnl_pct": (sell_price - e_price) / (e_price + EPSILON),
```

변경 후:
```python
sell_price, proceeds_per_share_unused, pnl, pnl_pct = execute_sell_order(
    open_price, shares_sold, e_price
)
sell_amount = shares_sold * sell_price  # proceeds 직접 계산 (execute_sell_order의 proceeds와 동일)
```

pnl_pct가 `(sell_price - e_price) / e_price`로 통일됨 (EPSILON 제거).

- [x] BUY 단계: `execute_buy_order()` 호출로 전환 (158-163행)

변경 전:
```python
buy_price = open_price * (1.0 + SLIPPAGE_RATE)
raw_shares = int(intent.delta_amount / buy_price)
```

변경 후:
```python
raw_shares, buy_price, _ = execute_buy_order(open_price, intent.delta_amount)
```

scale_factor 적용 로직은 포트폴리오 전용이므로 그대로 유지. `buy_price`를 `execute_buy_order`에서 받아서 사용.

- [x] trade_record 생성: `dict[str, Any]` → `PortfolioTradeRecord` 변경

변경 전:
```python
trade_record: dict[str, Any] = { ... }
```

변경 후:
```python
trade_record: PortfolioTradeRecord = {
    "entry_date": e_date,
    "exit_date": current_date,
    "entry_price": e_price,
    "exit_price": sell_price,
    "shares": shares_sold,
    "pnl": pnl,
    "pnl_pct": pnl_pct,
    "buy_buffer_pct": 0.0,
    "hold_days_used": e_hold_days.get(asset_id, 0),
    "asset_id": asset_id,
    "trade_type": "rebalance" if intent.intent_type == "REDUCE_TO_TARGET" else "signal",
}
```

- [x] `ExecutionResult.new_trades` 타입: `list[dict[str, Any]]` → `list[PortfolioTradeRecord]` 변경
- [x] import 정리: `engine_common`에서 `execute_buy_order`, `execute_sell_order`, `PortfolioTradeRecord` import, `SLIPPAGE_RATE` 직접 import 제거, `EPSILON` import 제거

**2-d. test_engine_common.py 기존 테스트 업데이트**:

- [x] 기존 `test_execute_sell_order_hold_days_used_param` 등 — `order` 파라미터 제거, 새 시그니처에 맞게 업데이트
- [x] `PendingOrder` import가 execute 함수 테스트에 불필요해짐 (다른 테스트에서 사용 시 유지)

**2-e. test_portfolio_execution.py 업데이트**:

- [x] `execute_orders()` 반환의 `new_trades`가 `PortfolioTradeRecord` 타입인지 검증하는 assert 추가
- [x] pnl_pct 계산 값 검증 — EPSILON 없는 정확한 값 확인

---

### Phase 3 — 최종 검증 + 문서

**작업 내용**:

- [x] 필요한 문서 업데이트
  - `src/qbt/backtest/CLAUDE.md`: engine_common 함수 시그니처 업데이트, `PortfolioTradeRecord` 추가, `filter_valid_rows()` 추가, `asset_closes_map` 제거 반영
  - `tests/CLAUDE.md`: 신규 테스트 추가 반영 (해당 시)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=463, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 엔진 통합 + 버그 수정 (pnl_pct 통일, params_schedule while, CAGR -100%)
2. 백테스트 / 포트폴리오 엔진 engine_common 완전 통합 + 잠재 버그 6건 수정
3. 백테스트 / 체결 함수 순수 계산 리팩토링 + 엔진 간 계산 불일치 해소
4. 백테스트 / engine_common 통합 리팩토링 + drawdown/pnl_pct/CAGR 버그 수정
5. 백테스트 / 두 엔진 체결 로직 통합 + 방어 로직 정비 (params_schedule, drawdown, CAGR)

## 7) 리스크(Risks)

### R1. 포트폴리오 엔진 통합 시 회귀

- **위험**: `execute_buy_order`/`execute_sell_order` 시그니처 변경이 기존 단일 백테스트 동작에 영향
- **완화**: Phase 0에서 기존 계약 테스트를 먼저 확인하고, Phase 2에서 기존 테스트를 동시에 업데이트. validate_project.py로 전체 회귀 검증

### R2. pnl_pct 수치 변경

- **위험**: EPSILON 제거로 기존 포트폴리오 결과와 미세한 차이 발생
- **완화**: EPSILON(1e-12) 수준의 차이이므로 실질적 영향 없음. 이는 의도된 버그 수정

### R3. scale_factor 적용 호환성

- **위험**: `execute_buy_order`가 순수 계산 함수가 되면서 포트폴리오의 scale_factor 로직과 호환성 확인 필요
- **완화**: `execute_buy_order`는 `(shares, buy_price, cost)`를 반환하고, scale_factor는 호출부에서 `raw_shares`에 적용. 기존 포트폴리오 시나리오 테스트가 회귀 방지

### R4. TypedDict 상속 호환성

- **위험**: `PortfolioTradeRecord(TradeRecord)` 상속이 Python 3.12에서 정상 동작하는지
- **완화**: Python 3.8+에서 TypedDict 상속 지원됨. PyRight strict 모드에서 검증

## 8) 메모(Notes)

### 설계 결정

- **순수 계산 함수 패턴**: `execute_buy_order`/`execute_sell_order`를 상태 변경 없는 순수 계산 함수로 변경. 호출부에서 명시적으로 상태를 업데이트하여 코드 가시성 향상. 포트폴리오 엔진의 `scale_factor`, 부분 매도, 가중평균 entry_price 등 특수 로직과 자연스럽게 공존 가능
- **PortfolioTradeRecord**: TradeRecord를 상속하여 `asset_id`, `trade_type` 필드 추가. `dict[str, Any]` 대비 타입 안전성 향상
- **filter_valid_rows**: `backtest_engine.py` 내부 헬퍼로 배치. 모듈 외부에서 사용할 가능성이 낮으므로 별도 유틸 모듈로 분리하지 않음
- **record_equity**: 변경 없음. 단일 엔진 전용이며 포트폴리오 엔진은 별도의 에쿼티 빌드 방식 사용

### Plan 1과의 의존 관계

- `calculate_drawdown_pct_series()`: Plan 1에서 `analysis.py`에 추가됨. 이 Plan에서 `portfolio_data.py`가 호출
- `COL_ENTRY_DATE`, `COL_EXIT_DATE`: Plan 1에서 `constants.py`에 추가됨. 이 Plan에서 `engine_common.py`의 `create_trade_record()`에서 참조 가능 (키 값은 리터럴 유지, TypedDict 제약)
- `ROUND_*` 상수: Plan 1에서 정의됨. 이 Plan에서는 반올림 로직 변경 없음

### 진행 로그 (KST)

- 2026-04-02 22:30: Plan 2 계획서 작성 완료
- 2026-04-02 22:40: Phase 0 완료 (11개 레드 테스트 작성)
- 2026-04-02 23:00: Phase 1 완료 (7건 단독 수정, 그린 전환)
- 2026-04-02 23:20: Phase 2 완료 (엔진 통합, 463 passed)
- 2026-04-02 23:45: Phase 3 완료 (Ruff+PyRight+Pytest 통과, 문서 업데이트, Done)

---
