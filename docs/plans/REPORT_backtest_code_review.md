# 백테스트 코드 리뷰 보고서

> 작성일: 2026-04-01
> 대상: 대규모 리팩토링 이후 백테스트 도메인 전체 (`src/qbt/backtest/`, `scripts/backtest/`, `src/qbt/common_constants.py`)
> 목적: 문서-코드 불일치, 논리적 오류/잠재 버그, 리팩토링 대상 식별
> 분석 범위: 30+ 파일 전체 정밀 분석
> 상세 보고서: `docs/backtest_code_review_detailed.md` (초보자 친화적 상세 설명 포함)

---

## 목차

1. [문서 규칙 위반 사항](#1-문서-규칙-위반-사항)
2. [논리적 오류 및 잠재적 버그](#2-논리적-오류-및-잠재적-버그)
3. [상수화 / 통합함수 / 모듈화 리팩토링 대상](#3-상수화--통합함수--모듈화-리팩토링-대상)
4. [요약 및 우선순위](#4-요약-및-우선순위)
5. [확정된 구현 방침](#5-확정된-구현-방침)
6. [계획서 분할 전략](#6-계획서-분할-전략)

---

## 1. 문서 규칙 위반 사항

### 1-1. `BufferStrategyParams`에 `frozen=True` 누락 — 문서 불일치

- **파일**: `src/qbt/backtest/types.py` (116행)
- **문서**: backtest CLAUDE.md에서 "dataclass, frozen=True"로 명시
- **현실**: `@dataclass`만 사용, `frozen=True` 없음
- **영향**: 불변 객체 의도인데 외부에서 필드 변경 가능. 병렬 처리 시 안전성 미보장

### 1-2. 계층 분리 원칙 위반 — CLI에 비즈니스 로직 포함

CLAUDE.md의 "CLI 계층에 도메인 로직 포함 금지" 원칙을 위반하는 경우가 여러 곳에서 발견됨.

**(a) `_run_stitched_equity` (run_walkforward.py, 95~168행)**

- OOS 날짜 범위 결정, MA 윈도우 수집/사전 계산, OOS 구간 데이터 슬라이싱, 엔진 호출 후 `window_end_equities` 계산 등 핵심 비즈니스 로직을 CLI 스크립트에서 직접 수행
- `SignalStrategy` Protocol의 private 속성 `_ma_col`에 직접 접근하면서 `type: ignore[attr-defined]` 사용 (130, 133행) — 캡슐화 위반

**(b) `_save_window_detail_csvs` (run_walkforward.py, 264~404행)**

- 140행에 달하는 함수 내에서 `BufferZoneStrategy`를 직접 인스턴스화하고 `run_backtest`를 호출
- MA 계산, 밴드 계산, drawdown 계산 등 비즈니스 로직 직접 수행
- 이 로직은 `src/qbt/backtest/walkforward.py`에 위치해야 함

**(c) drawdown_pct 계산 (run_single_backtest.py 132~135행, run_walkforward.py 362~365행)**

- 동일한 drawdown 계산 로직이 CLI 스크립트 2곳에 존재
- 비즈니스 분석 로직이므로 `analysis.py`에 위치해야 함

**확정 방침**: **C안** — stitched equity 로직은 `walkforward.py`로 이동, CSV 저장 관련 공통 로직(drawdown, trades 저장)은 별도 csv_export 유틸로 추출. 3-1/3-2번 중복 해소도 동시 달성

### 1-3. 포트폴리오 엔진이 engine_common.py를 미사용 — 아키텍처 위반

- **문서**: CLAUDE.md에서 `engine_common.py`를 "두 엔진이 공유하는 공통 로직"으로 정의
- **현실**: 포트폴리오 엔진(`portfolio_execution.py`)은 `execute_buy_order()`, `execute_sell_order()`, `record_equity()` 등 공유 함수를 전혀 사용하지 않고 독자적으로 체결 로직 구현
- **결과**: SLIPPAGE_RATE 적용 로직이 두 곳에 분산, `TradeRecord` TypedDict 미사용, `pnl_pct` 계산 방식 차이 발생 (2-1 참조)
- **확정 방침**: **A안 (완전 통합)** — 포트폴리오 엔진도 engine_common의 함수를 호출하도록 리팩토링. 포트폴리오 전용 로직(scale_factor, 부분 매도)은 engine_common 인터페이스 확장으로 대응

### 1-4. 데이터 불변성 원칙 위반 가능성

- **파일**: `src/qbt/backtest/strategy_registry.py` (128행)
- `_prepare_buy_and_hold_signal_df`가 원본 DataFrame을 `df.copy()` 없이 그대로 반환
- 반면 `_prepare_buffer_zone_signal_df`는 내부에서 새 DataFrame이 반환되므로 일관성 불일치

### 1-5. CLAUDE.md 문서 자체의 코드 불일치 (2건)

**(a) `BufferZoneStrategy` 생성자 시그니처**

- 문서에 `ma_type="ema"` 파라미터를 나열하지만, 실제 `BufferZoneStrategy` 클래스는 `ma_type`을 받지 않음
- MA 계산은 runner에서 처리하므로 전략 클래스가 알 필요 없는 구조

**(b) `StrategySpec`의 `supports_single`, `supports_portfolio` 필드**

- 문서에 "예약 필드"로 언급되어 있으나 실제 코드에 존재하지 않음

---

## 2. 논리적 오류 및 잠재적 버그

### 2-1. [높음] pnl_pct 계산 방식 불일치

- **단일 엔진** (`engine_common.py` 164행): `pnl_pct = (sell_price - entry_price) / entry_price`
- **포트폴리오 엔진** (`portfolio_execution.py` 123행): `pnl_pct = (sell_price - e_price) / (e_price + EPSILON)`
- 포트폴리오 엔진에서만 분모에 EPSILON을 더함. entry_price가 0인 것은 비정상 상태이며, EPSILON 추가는 결과를 왜곡할 수 있음
- **두 엔진 간 동일 거래에서 미세한 수치 차이 발생 가능**

### 2-2. [높음] params_schedule 전환 시 건너뛴 날짜 처리 미비

- **파일**: `src/qbt/backtest/engines/backtest_engine.py` (300~304행)
- `next_switch_idx`를 한 번에 1만 증가시킴
- 만약 같은 날짜에 2개 이상의 전환이 있거나, 데이터에 빈 거래일이 있어 여러 전환 날짜를 건너뛰어야 하는 경우, 의도하지 않은 중간 전략이 하루 이상 적용될 수 있음
- `while` 루프로 현재 날짜 이전의 모든 전환을 처리하는 것이 안전

### 2-3. [중간] IS/OOS trade_df에 signal_df 마스크 직접 적용

- **파일**: `src/qbt/backtest/walkforward.py` (291~293행, 329~331행), `scripts/backtest/run_walkforward.py` (143행)
- `signal_df_with_ma`에서 생성된 boolean 마스크를 `trade_df`에 그대로 적용
- `signal_df`와 `trade_df`의 인덱스가 정확히 일치한다는 암묵적 가정
- 현재 호출 체인에서는 overlap 처리가 선행되므로 실제 버그는 아니지만, trade_df에 대해 독립적인 날짜 기반 마스크를 사용하는 것이 방어적

### 2-4. [중간] drawdown 계산 방어 로직 불일치

- `analysis.py`: `peak.replace(0, EPSILON)` 사용
- `portfolio_data.py`: `peak + EPSILON` 사용
- 동일 목적(분모 0 방지)이지만 다른 방어 로직 → 미세한 수치 차이 가능

### 2-5. [중간] `_enrich_equity_with_bands`에서 compute_bands 이중 호출

- **파일**: `src/qbt/backtest/runners.py` (82~83행)
- 동일한 MA 값에 대해 `compute_bands`를 2번 호출하여 각각 `[0]`, `[1]`만 사용
- 한 번 호출 후 unpack하면 되는 불필요한 중복 계산

### 2-6. [중간] check_buy/check_sell 상태 비동기화 가능성

- 포트폴리오 엔진(`portfolio_planning.py` 128~163행)에서 `position == 0`이면 `check_buy()`만, `position > 0`이면 `check_sell()`만 호출
- `BufferZoneStrategy`의 `_prev_upper`, `_prev_lower` 상태가 한쪽에서만 갱신되어, 다른 쪽의 prev 상태가 최신이 아닐 수 있음
- 단일 백테스트 엔진도 동일한 호출 패턴이므로 현재는 일관되지만, 전략 객체의 내부 상태 관리가 호출 순서에 암묵적으로 의존

### 2-7. [낮음] `execute_buy_order` / `execute_sell_order`의 미사용 `order` 파라미터

- **파일**: `src/qbt/backtest/engines/engine_common.py` (84~169행)
- 두 함수 모두 `order: PendingOrder` 파라미터를 받지만 본문에서 전혀 사용하지 않음
- YAGNI 원칙 위반
- **확정 방침**: **A안 (파라미터 제거)** — `order` 파라미터 삭제, 호출부도 수정

### 2-8. [낮음] `calculate_summary`의 final_capital ≤ 0 시 CAGR=0 반환

- **파일**: `src/qbt/backtest/analysis.py` (150행)
- `final_capital`이 0 이하인 극단 손실 케이스에서 CAGR을 0.0으로 반환하지만, 실제로는 -100% CAGR이어야 함
- 현재 구조에서 도달 가능성 극히 낮음

### 2-9. [낮음] `__import__("datetime")` 비관습적 패턴

- **파일**: `src/qbt/backtest/walkforward.py` (155행)
- `datetime`이 이미 상단에서 일부 import되어 있으므로 `timedelta`를 추가 import하면 됨
- `.replace(day=1)`도 이미 `date(year, month+1, 1)`로 보장되어 중복

### 2-10. [낮음] `STRATEGY_CONFIG` 타입 주석 부정확

- **파일**: `scripts/backtest/run_walkforward.py` (64행)
- 실제 값은 `Path`만 포함하는데 타입에 `list[int] | list[float] | None`이 불필요하게 포함

### 2-11. [낮음] `portfolio_configs.py` docstring 오타

- 줄 2: `"정의돈 실험을"` → `"정의된 실험을"`

### 2-12. [낮음] `PortfolioResult.config`의 빈 기본값

- **파일**: `src/qbt/backtest/portfolio_types.py` (147~155행)
- `total_capital=0.0`, `result_dir=Path(".")`의 기본값은 의미 없는 결과 생성 가능
- 실제로는 항상 명시적으로 전달되므로 문제 없으나, 필수 파라미터로 만드는 것이 타입 안전

---

## 3. 상수화 / 통합함수 / 모듈화 리팩토링 대상

### 3-1. [높음] trades CSV 저장 로직 3중 중복 → 공용 함수 추출

동일한 패턴이 3개 스크립트에 반복됨:
- `run_single_backtest.py` (166~193행, `_save_trades_csv`)
- `run_walkforward.py` (380~402행, `_save_window_detail_csvs` 내부)
- `run_portfolio_backtest.py` (85~110행, `_save_portfolio_results` 내부)

반복 패턴:
```python
trades_export["holding_days"] = trades_export.apply(
    lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
)
# + 동일한 반올림 딕셔너리 + int 변환
```

### 3-2. [높음] drawdown_pct 계산 로직 2중 중복 → analysis.py로 통합

동일한 패턴이 2개 스크립트에 반복 + analysis.py에 유사 로직 존재:
```python
equity_series = equity_export["equity"].astype(float)
peak = equity_series.cummax()
safe_peak = peak.replace(0, EPSILON)
equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
```

### 3-3. [높음] 데이터 로딩 패턴 3중 중복 → 공용 함수 추출

signal_path == trade_path 분기 + overlap 추출 패턴이 3곳에 반복:
- `run_walkforward.py` (78~92행)
- `run_param_plateau_all.py` (146~167행)
- `src/qbt/backtest/runners.py` (119~127행)

### 3-4. [높음] 반올림 규칙 상수 미통일

CLAUDE.md에 반올림 규칙이 명시되어 있으나, 구현은 파일별로 다름:
- `run_portfolio_backtest.py`만 `_PRICE_ROUND=6` 등 상수 사용
- 나머지 스크립트는 리터럴 숫자 직접 사용 (`6`, `0`, `4`, `2`)
- 공통 상수로 정의하여 전 스크립트에서 참조해야 함

### 3-5. [높음] 반복 사용 컬럼명 상수화 미적용

다수의 문자열 리터럴이 2개 이상 파일에서 반복 사용됨 (상수 관리 규칙 위반):

| 문자열 | 사용 파일 수 | 비고 |
|--------|-------------|------|
| `"equity"` | 3+ | analysis.py, engine_common.py, portfolio_data.py 등 |
| `"pnl"` | 3+ | analysis.py, engine_common.py, portfolio_execution.py |
| `"entry_date"`, `"exit_date"` | 3+ | analysis.py, engine_common.py, 스크립트들 |
| `"upper_band"`, `"lower_band"` | 2+ | runners.py, 앱 스크립트들 |
| `"buy_buffer_pct"`, `"hold_days_used"` | 2+ | buffer_zone.py, engine_common.py |
| `"position"` | 2+ | engine_common.py, backtest_engine.py |

`COL_EQUITY`, `COL_PNL`, `COL_ENTRY_DATE`, `COL_EXIT_DATE` 등으로 `constants.py`에 정의해야 함

**확정 방침**: **B안 (핵심만 상수화)** — 가장 빈번하게 사용되는 6개(`equity`, `pnl`, `entry_date`, `exit_date`, `upper_band`, `lower_band`)만 상수화

### 3-6. [중간] common_constants.py의 개별 결과 디렉토리 상수 과잉

16개의 개별 결과 디렉토리 상수(`BUFFER_ZONE_SPY_RESULTS_DIR`, `BUY_AND_HOLD_EEM_RESULTS_DIR` 등)가 대부분 단일 파일에서만 사용됨. 상수 관리 3계층 규칙에 따르면:
- `BACKTEST_RESULTS_DIR`만 공통 상수로 유지
- 개별 전략 디렉토리는 `BACKTEST_RESULTS_DIR / f"buffer_zone_{ticker}"` 패턴으로 동적 생성 가능

**확정 방침**: **A안** — `BACKTEST_RESULTS_DIR`만 공통 상수로 남기고, 16개 개별 상수는 각 CONFIGS에서 인라인 구성. 테스트 코드 import 변경도 함께 처리

### 3-7. [중간] MA 컬럼명 구성 패턴 반복

`f"ma_{window}"` 패턴이 최소 3곳에서 반복:
- `backtest_engine.py` (175행, 526행)
- `analysis.py` (60행)

MA 컬럼 네이밍 규칙 변경 시 여러 곳 수정 필요. 생성 함수나 상수 템플릿으로 추출 가능.

### 3-8. [중간] 유효 행 필터링 패턴 2중 중복

```python
valid_mask = signal_df[ma_col].notna()
filtered_signal = signal_df[valid_mask].reset_index(drop=True)
filtered_trade = trade_df[valid_mask].reset_index(drop=True)
```

`_run_backtest_for_grid` (176~178행)과 `run_buffer_strategy` (534~536행)에서 동일 반복.

### 3-9. [중간] portfolio_engine.py 내 데이터 로딩/필터링 중복

`compute_portfolio_effective_start_date()`와 `run_portfolio_backtest()`에서 다음 로직이 거의 동일하게 중복:
1. `signal_cache` 캐시 관리
2. 공통 기간 추출 (`date_sets` 교집합)
3. MA 워밍업 구간 필터링

### 3-10. [중간] 포트폴리오 체결 로직 — engine_common.py와 통합 가능

포트폴리오 엔진의 핵심 체결 산식 (`buy_price = open * (1 + SLIPPAGE_RATE)`, `shares = int(amount / buy_price)`)은 engine_common.py와 공유 가능. 멀티 자산 특성(`scale_factor`, 가중평균 `entry_price`)만 확장하면 됨.

### 3-11. [중간] check_buy/check_sell 내부 밴드 계산/prev 갱신 중복

`BufferZoneStrategy`의 `check_buy`와 `check_sell` 모두:
1. `compute_bands` 호출
2. `_prev_upper is None` / `_prev_lower is None` 체크
3. 현재 행으로 `_prev_upper`, `_prev_lower` 갱신

내부 메서드 `_update_bands(signal_df, i)`로 추출 가능.

### 3-12. [중간] `resolve_buffer_params`의 `sources` 딕셔너리 — 항상 "FIXED"

4P 고정 전환 후 분기 없이 무조건 `"FIXED"`를 반환. 함수 존재 의의가 "검증 + `BufferStrategyParams` 생성"으로 축소됨. 간소화 가능.

**확정 방침**: **A안 (sources 제거)** — `resolve_buffer_params`가 `BufferStrategyParams`만 반환하도록 변경. 호출부(4~5곳) 함께 수정

### 3-13. [낮음] `resolve_buffer_params`에서 `ma_window` 검증 누락

`buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`는 최솟값 검증이 있으나 `ma_window` 양수 검증 없음.

### 3-14. [낮음] `type: ignore[assignment]` 대신 명시적 narrowing

`buffer_zone.py` (363행, 456행)에서 `type: ignore` 대신 `assert` 또는 `cast` 사용이 더 안전.

### 3-15. [낮음] signal CSV의 change_pct 계산 2중 중복

`run_single_backtest.py`와 `run_portfolio_backtest.py`에서 동일 패턴 반복.

### 3-16. [낮음] 포트폴리오 trade_record가 `dict[str, Any]` — 타입 불안전

`portfolio_execution.py`에서 `TradeRecord` TypedDict를 사용하지 않고 `dict[str, Any]`로 직접 구성. 포트폴리오용 TradeRecord TypedDict 별도 정의 가능.

### 3-17. [낮음] `compute_projected_portfolio`의 미사용 `asset_closes_map` 파라미터

`portfolio_planning.py` (172행)에서 본문에서 전혀 사용하지 않는 파라미터. YAGNI 위반.

### 3-18. [낮음] `PendingOrder`의 strategies 패키지 re-export

`strategies/__init__.py`에서 `engine_common.py`의 `PendingOrder`를 re-export하는 것은 계층 분리 원칙에 어긋남.

---

## 4. 요약 및 우선순위

### 4-1. 우선순위 분류

| 우선순위 | 카테고리 | ID | 핵심 내용 |
|---------|---------|-----|-----------|
| **긴급** | 규칙 위반 | 1-2 | CLI에 비즈니스 로직 포함 (run_walkforward.py) |
| **긴급** | 버그 | 2-1 | pnl_pct 계산 방식 불일치 (단일 vs 포트폴리오 엔진) |
| **높음** | 버그 | 2-2 | params_schedule 전환 시 건너뛴 날짜 미처리 |
| **높음** | 규칙 위반 | 1-3 | 포트폴리오 엔진이 engine_common.py 미사용 |
| **높음** | 리팩토링 | 3-1 | trades CSV 저장 로직 3중 중복 |
| **높음** | 리팩토링 | 3-2 | drawdown_pct 계산 2중 중복 |
| **높음** | 리팩토링 | 3-3 | 데이터 로딩 패턴 3중 중복 |
| **높음** | 리팩토링 | 3-4 | 반올림 규칙 상수 미통일 |
| **높음** | 리팩토링 | 3-5 | 반복 사용 컬럼명 상수화 미적용 |
| **중간** | 규칙 위반 | 1-1 | BufferStrategyParams frozen=True 누락 |
| **중간** | 버그 | 2-3 | trade_df 마스크 적용 시 인덱스 정합성 가정 |
| **중간** | 버그 | 2-4 | drawdown 방어 로직 불일치 |
| **중간** | 버그 | 2-5 | compute_bands 이중 호출 |
| **중간** | 리팩토링 | 3-6~3-12 | 상수 과잉, 중복 패턴, 함수 간소화 |
| **낮음** | 버그 | 2-7~2-12 | 미사용 파라미터, 타입 주석, 오타 등 |
| **낮음** | 리팩토링 | 3-13~3-18 | 검증 누락, 타입 안전, re-export 정리 |

### 4-2. 핵심 위험 요약

1. **계층 분리 위반**: `run_walkforward.py`에 비즈니스 로직이 과도하게 포함되어 있음. 특히 `_run_stitched_equity`와 `_save_window_detail_csvs`는 `src/qbt/backtest/`로 이동 필요
2. **두 엔진 간 일관성 부재**: 포트폴리오 엔진이 engine_common.py를 공유하지 않아 pnl_pct 계산, drawdown 방어, trade_record 구조가 미묘하게 다름
3. **중복 코드 과다**: trades 저장, drawdown 계산, 데이터 로딩, 반올림 등 동일 패턴이 3~4곳에 분산되어 유지보수 리스크 높음
4. **상수 관리 미비**: 다수의 컬럼명이 리터럴로 사용되어 오타 발생 시 런타임 에러로만 발견 가능

### 4-3. 긍정적 평가

- **핵심 비즈니스 규칙 준수**: 체결 타이밍 (i일 신호 → i+1일 시가 체결), Pending Order 정책 (단일 슬롯, 충돌 예외), hold_days 상태머신 (Lookahead 방지), Equity 정의 (`cash + position * close`)는 모두 도메인 규칙에 정확히 부합
- **비용 모델 일관성**: 매수 `price * (1 + SLIPPAGE_RATE)`, 매도 `price * (1 - SLIPPAGE_RATE)` 정확히 적용
- **테스트 커버리지**: 핵심 계약/불변조건에 대한 테스트가 충분히 작성되어 있음
- **parameter_stability.py**: 상수 관리, 검증, docstring, 타입 힌트 모두 양호

---

## 5. 확정된 구현 방침

사용자 결정(2026-04-01)에 따라 각 핵심 설계 결정을 확정한다.

### 5-1. 포트폴리오 엔진 × engine_common 통합 → A안 (완전 통합)

- 포트폴리오 엔진도 `engine_common.py`의 함수를 호출하도록 리팩토링
- 포트폴리오 전용 로직(scale_factor, 부분 매도, 가중평균 entry_price)은 engine_common 인터페이스 확장으로 대응
- pnl_pct 계산 불일치 완전 해소, TradeRecord TypedDict 재사용
- 관련 항목: 1-3, 2-1, 3-10, 3-16

### 5-2. run_walkforward.py 비즈니스 로직 이동 → C안 (walkforward.py + csv_export 분리)

- stitched equity 로직(`_run_stitched_equity`)은 `src/qbt/backtest/walkforward.py`로 이동
- 윈도우별 상세 백테스트 로직(`_save_window_detail_csvs`의 비즈니스 부분)은 `walkforward.py`로 이동
- CSV 저장 공통 로직(drawdown 계산, trades 저장, signal 저장)은 별도 유틸 모듈로 추출
- 3-1/3-2/3-15번 중복 해소를 동시 달성
- 관련 항목: 1-2, 3-1, 3-2, 3-15

### 5-3. 컬럼명 상수화 → B안 (핵심 6개만 상수화)

- 대상: `equity`, `pnl`, `entry_date`, `exit_date`, `upper_band`, `lower_band`
- 배치: `backtest/constants.py` (도메인 내 2개 이상 파일에서 사용)
- TypedDict 키는 리터럴이어야 하므로 이중 관리가 불가피하나, 주석으로 COL_* 상수와의 대응 관계를 명시
- 관련 항목: 3-5

### 5-4. common_constants.py 결과 디렉토리 상수 → A안 (CONFIGS 인라인)

- `BACKTEST_RESULTS_DIR`만 공통 상수로 유지
- 16개 개별 상수 제거, 각 CONFIGS에서 `BACKTEST_RESULTS_DIR / "buffer_zone_spy"` 형태로 인라인 구성
- 테스트 코드에서 참조하는 경우 import 경로 변경 함께 처리
- 관련 항목: 3-6

### 5-5. resolve_buffer_params sources 제거 → A안

- `resolve_buffer_params`가 `BufferStrategyParams`만 반환하도록 변경
- 호출부(4~5곳) 함께 수정
- 관련 항목: 3-12

### 5-6. execute_buy/sell_order의 order 파라미터 제거 → A안

- 두 함수에서 미사용 `order: PendingOrder` 파라미터 삭제
- 호출부(backtest_engine.py)도 수정
- 관련 항목: 2-7

---

## 6. 계획서 분할 전략

영향도 기준으로 3개 계획서로 분할한다. 먼저 구현하면 후속 계획서에 영향을 주는 것(인프라성 변경)을 우선 배치한다.

### Plan 1: 상수/유틸 인프라 정비 (선행 의존성)

후속 Plan에서 참조할 상수와 공용 함수를 먼저 정비한다. 이 Plan이 완료되어야 Plan 2, 3에서 새 상수와 유틸을 사용할 수 있다.

| ID | 핵심 내용 | 비고 |
|----|-----------|------|
| 3-4 | 반올림 규칙 상수 통일 | `constants.py`에 정의, 전 스크립트 참조 |
| 3-5 | 핵심 컬럼명 6개 상수화 | `constants.py`에 COL_* 정의 |
| 3-6 | 결과 디렉토리 16개 상수 → CONFIGS 인라인 | `common_constants.py` 정리 |
| 3-3 | 데이터 로딩 패턴 공용 함수 추출 | `data_loader.py`에 추가 |
| 3-1 | trades CSV 저장 공용 함수 추출 | 새 csv_export 모듈 |
| 3-2 | drawdown_pct 계산 공용 함수 추출 | `analysis.py`에 추가 |
| 3-7 | MA 컬럼명 생성 함수 추출 | `constants.py` 또는 `analysis.py` |
| 1-1 | BufferStrategyParams frozen=True | 단순 수정 |
| 1-4 | _prepare_buy_and_hold_signal_df에 df.copy() 추가 | 단순 수정 |
| 1-5 | CLAUDE.md 문서 불일치 2건 수정 | 문서만 수정 |
| 2-9 | `__import__("datetime")` → 정상 import | 단순 수정 |
| 2-11 | docstring 오타 수정 | 단순 수정 |
| 3-13 | ma_window 양수 검증 추가 | 단순 수정 |
| 3-14 | type: ignore → assert/cast | 단순 수정 |
| 3-15 | change_pct 중복 → csv_export에 통합 | 3-1과 함께 |

### Plan 2: 버그 수정 + 엔진 통합 (핵심 로직)

계산 불일치와 잠재 버그를 수정하고, 두 엔진의 체결 로직을 통합한다. Plan 1의 상수/유틸을 활용.

| ID | 핵심 내용 | 비고 |
|----|-----------|------|
| 2-1 | pnl_pct 계산 방식 통일 | 1-3과 함께 |
| 1-3 | 포트폴리오 엔진 engine_common 완전 통합 | A안 |
| 2-2 | params_schedule 전환 if → while | 단독 수정 |
| 2-4 | drawdown 방어 로직 통일 | Plan 1의 공용 함수 활용 |
| 2-7 | execute_buy/sell_order의 order 파라미터 제거 | A안, 1-3 과정에서 함께 |
| 3-10 | 포트폴리오 체결 산식 공용화 | 1-3 과정에서 함께 |
| 3-16 | 포트폴리오 TradeRecord TypedDict 정의 | 1-3 과정에서 함께 |
| 2-3 | trade_df 마스크 독립 날짜 기반으로 변경 | 방어적 수정 |
| 2-5 | compute_bands 이중 호출 → 1회 호출 | 단독 수정 |
| 2-8 | CAGR=0 → final_capital=0 시 -100% | 단독 수정 |
| 3-8 | 유효 행 필터링 패턴 헬퍼 함수 추출 | 단독 수정 |
| 3-17 | 미사용 asset_closes_map 파라미터 제거 | 단독 수정 |

### Plan 3: 계층 분리 + 구조 정리

CLI에서 비즈니스 로직을 분리하고, 남은 구조적 정리를 수행한다. Plan 1의 csv_export 유틸 활용.

| ID | 핵심 내용 | 비고 |
|----|-----------|------|
| 1-2(a) | `_run_stitched_equity` → walkforward.py | C안 |
| 1-2(b) | `_save_window_detail_csvs` 비즈니스 로직 → walkforward.py | C안 |
| 1-2(c) | drawdown_pct 계산 → Plan 1의 공용 함수 호출 | C안 |
| 2-10 | STRATEGY_CONFIG 타입 주석 정확화 | run_walkforward.py 수정 중 함께 |
| 3-9 | portfolio_engine.py 데이터 로딩 중복 → 헬퍼 추출 | 단독 수정 |
| 3-11 | check_buy/check_sell 밴드 계산 → _update_bands 추출 | 단독 수정 |
| 3-12 | resolve_buffer_params sources 제거 | A안 |
| 2-6 | check_buy/check_sell 상태 관리 명확화 | 3-11과 함께 |
| 2-12 | PortfolioResult.config 빈 기본값 제거 | 단독 수정 |
| 3-18 | PendingOrder re-export 제거 | 단독 수정 |

### 실행 순서 근거

```
Plan 1 (상수/유틸 인프라)
  ↓ 새 상수(COL_*, ROUND_*) + 공용 함수(csv_export, load_signal_trade_pair) 제공
Plan 2 (버그 수정 + 엔진 통합)
  ↓ engine_common 통합 완료, 계산 불일치 해소
Plan 3 (계층 분리 + 구조 정리)
  ↓ CLI → src 이동 시 Plan 1의 유틸 + Plan 2의 통합 엔진 활용
```

Plan 1이 "토대"이므로 먼저 완료하면, Plan 2/3에서 새 상수와 유틸을 즉시 활용할 수 있어 중복 수정을 방지한다.
