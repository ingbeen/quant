# 백테스트 코드 리뷰 상세 보고서

> 작성일: 2026-04-01
> 대상: 대규모 리팩토링 이후 백테스트 도메인 전체
> 목적: 문서-코드 불일치, 논리적 오류/잠재 버그, 리팩토링 대상 식별
> 분석 범위: `src/qbt/backtest/`, `scripts/backtest/`, `src/qbt/common_constants.py` (30+ 파일)

---

## 이 보고서를 읽기 전에 알아야 할 것

이 보고서는 QBT 프로젝트의 "백테스트" 관련 코드를 전수 검사한 결과입니다.
각 항목은 다음 3가지 카테고리로 분류됩니다:

1. **문서 규칙 위반**: CLAUDE.md에 "이렇게 해야 한다"고 적혀 있는데, 실제 코드가 다르게 되어 있는 경우
2. **논리적 오류 / 잠재 버그**: 코드가 의도와 다르게 동작하거나, 특정 조건에서 문제가 생길 수 있는 경우
3. **리팩토링 대상**: 동작은 하지만, 같은 코드가 여러 곳에 반복되거나 상수화가 안 되어 유지보수가 어려운 경우

각 항목에는 **심각도**(긴급/높음/중간/낮음)를 표시했습니다.

---

## 목차

- [1부. 문서 규칙 위반 사항 (5건)](#1부-문서-규칙-위반-사항)
- [2부. 논리적 오류 및 잠재적 버그 (12건)](#2부-논리적-오류-및-잠재적-버그)
- [3부. 리팩토링 대상 (18건)](#3부-리팩토링-대상)
- [4부. 긍정적 평가](#4부-긍정적-평가)
- [5부. 우선순위 요약표](#5부-우선순위-요약표)

---

# 1부. 문서 규칙 위반 사항

## 1-1. BufferStrategyParams에 frozen=True 누락

> 심각도: **중간** | 파일: `src/qbt/backtest/types.py` 116행

### 무엇이 문제인가?

`frozen=True`는 Python dataclass에서 "한번 만들어진 객체의 값을 바꿀 수 없게 잠그는" 옵션입니다.
마치 엑셀 시트의 "시트 보호"와 비슷합니다. 보호를 걸면 실수로 값을 수정하는 것을 방지합니다.

backtest CLAUDE.md 문서에는 `BufferStrategyParams`를 `"dataclass, frozen=True"`로 명시하고 있습니다.
하지만 실제 코드에는 `frozen=True`가 빠져 있습니다.

### 현재 코드

```python
# src/qbt/backtest/types.py (116행)
@dataclass          # <-- frozen=True가 없음!
class BufferStrategyParams:
    initial_capital: float
    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int
```

### 있어야 할 코드

```python
@dataclass(frozen=True)  # <-- 이렇게 되어야 함
class BufferStrategyParams:
    ...
```

### 왜 위험한가?

이 파라미터 객체는 그리드 서치에서 병렬 처리(여러 CPU가 동시에 작업)에 사용됩니다.
`frozen=True`가 없으면, 어떤 코드에서 실수로 `params.ma_window = 300`처럼
값을 변경할 수 있습니다. 병렬 처리 환경에서 이런 일이 일어나면 디버깅이 매우 어렵습니다.

---

## 1-2. CLI 계층에 비즈니스 로직 포함 (계층 분리 원칙 위반)

> 심각도: **긴급** | 파일: `scripts/backtest/run_walkforward.py`

### 배경: "계층 분리"란?

QBT 프로젝트는 코드를 2가지 계층으로 나눕니다:

- **CLI 계층** (`scripts/`): 사용자 인터페이스. "실행해줘", "결과 보여줘" 역할만 담당
- **비즈니스 로직 계층** (`src/qbt/`): 실제 계산과 분석을 수행

비유하면, CLI는 "식당 종업원"이고 비즈니스 로직은 "주방장"입니다.
종업원이 직접 요리를 하면 안 됩니다. 주문만 전달하고 결과만 서빙해야 합니다.

CLAUDE.md에도 명확히 적혀 있습니다:
> "CLI 계층에 도메인 로직 포함 금지, 오직 인터페이스 제공만 담당"

### 위반 (a): `_run_stitched_equity` 함수 (95~168행)

이 함수는 "종업원이 직접 요리하는" 경우입니다.
WFO 결과를 이어 붙여 Stitched Equity를 만드는 핵심 비즈니스 로직이 CLI 스크립트에 있습니다.

```python
# scripts/backtest/run_walkforward.py (95~168행)
def _run_stitched_equity(signal_df, trade_df, window_results, initial_capital):
    # 이 함수 안에 다음과 같은 비즈니스 로직이 들어 있음:
    
    # 1. OOS 날짜 범위 결정 (비즈니스 로직)
    first_oos_start = window_results[0]["oos_start"]
    last_oos_end = window_results[-1]["oos_end"]
    
    # 2. MA 윈도우 수집 및 사전 계산 (비즈니스 로직)
    all_ma_windows = set()
    for wr in window_results:
        all_ma_windows.add(wr["best_ma_window"])
    
    # 3. OOS 구간 데이터 슬라이싱 (비즈니스 로직)
    oos_mask = (signal_df_with_ma[COL_DATE] >= oos_start_date) & (...)
    oos_signal = signal_df_with_ma[oos_mask].reset_index(drop=True)
    oos_trade = trade_df[oos_mask].reset_index(drop=True)
    
    # 4. 엔진 호출 (비즈니스 로직)
    trades_df, equity_df, summary = run_backtest(...)
```

또한 이 함수 내부에서 `SignalStrategy` Protocol의 private 속성에 직접 접근합니다:

```python
# scripts/backtest/run_walkforward.py (130, 133행)
_initial_ma_col: str = initial_params._ma_col  # type: ignore[attr-defined]
_p_ma_col: str = _p._ma_col  # type: ignore[attr-defined]
```

`_ma_col`처럼 앞에 `_`(밑줄)이 붙은 것은 "외부에서 직접 건드리지 마세요"라는 의미입니다.
그런데 CLI 스크립트에서 이걸 직접 읽고 있고, `type: ignore`까지 달아서 타입 체커 경고를 무시합니다.

### 위반 (b): `_save_window_detail_csvs` 함수 (264~404행)

140행에 달하는 이 함수는 "저장"이라는 이름이지만, 실제로는 다음과 같은 비즈니스 로직을 수행합니다:

```python
# scripts/backtest/run_walkforward.py (320~332행 요약)
# 전략 인스턴스를 직접 생성
strategy = BufferZoneStrategy(
    ma_col=best_ma_col,
    buy_buffer_pct=wr["best_buy_buffer_zone_pct"],
    sell_buffer_pct=wr["best_sell_buffer_zone_pct"],
    hold_days=wr["best_hold_days"],
)

# 백테스트 엔진을 직접 호출
trades_df, equity_df, _ = run_backtest(
    strategy, w_signal, w_trade, initial_capital, log_trades=False
)
```

CLI 스크립트에서 `BufferZoneStrategy`를 직접 만들고 `run_backtest`를 호출하는 것은
"종업원이 냄비를 들고 직접 요리하는 것"과 같습니다.

### 위반 (c): drawdown_pct 계산

drawdown(최대 낙폭)을 계산하는 로직이 CLI 스크립트 2곳에 있습니다:

```python
# scripts/backtest/run_single_backtest.py (132~135행)
equity_series = equity_export["equity"].astype(float)
peak = equity_series.cummax()
safe_peak = peak.replace(0, EPSILON)
equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100

# scripts/backtest/run_walkforward.py (362~365행) -- 동일한 코드
equity_series = equity_export["equity"].astype(float)
peak = equity_series.cummax()
safe_peak = peak.replace(0, EPSILON)
equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
```

이 계산은 "분석"이므로 `src/qbt/backtest/analysis.py`에 있어야 합니다.

### 이 로직들은 어디에 있어야 하나?

- `_run_stitched_equity` → `src/qbt/backtest/walkforward.py`
- `_save_window_detail_csvs`의 비즈니스 로직 → `src/qbt/backtest/walkforward.py`
- drawdown_pct 계산 → `src/qbt/backtest/analysis.py`

---

## 1-3. 포트폴리오 엔진이 engine_common.py를 사용하지 않음

> 심각도: **높음** | 파일: `src/qbt/backtest/engines/portfolio_execution.py`

### 무엇이 문제인가?

`engine_common.py`는 이름 그대로 "두 엔진(단일 백테스트 / 포트폴리오)이 **공통으로** 사용하는 로직"을 모아둔 파일입니다.
backtest CLAUDE.md에도 이렇게 명시되어 있습니다:
> "engine_common.py: 체결/에쿼티 기록 등 두 엔진이 공유하는 공통 로직을 제공합니다."

하지만 실제로 포트폴리오 엔진(`portfolio_execution.py`)은 이 공통 함수를 **전혀 사용하지 않습니다**.
대신 독자적으로 체결 로직을 처음부터 다시 구현합니다.

### 비교: 단일 엔진 vs 포트폴리오 엔진

**단일 엔진** (engine_common.py 사용):
```python
# engine_common.py (109행)
buy_price = open_price * (1 + SLIPPAGE_RATE)
shares = int(capital / buy_price)
```

**포트폴리오 엔진** (독자 구현):
```python
# portfolio_execution.py (100행)
sell_price = open_price * (1.0 - SLIPPAGE_RATE)
# ... 자체 구현
```

같은 슬리피지 공식(`open_price * (1 + SLIPPAGE_RATE)`)을 두 곳에서 각각 구현하고 있습니다.
나중에 슬리피지 비율을 바꾸거나 계산 방식을 수정할 때, 한 쪽만 고치면 불일치가 발생합니다.

또한 이 불일치로 인해 `pnl_pct` 계산 방식이 실제로 다릅니다 (2-1번 참조).

---

## 1-4. 데이터 불변성 원칙 위반 가능성

> 심각도: **낮음** | 파일: `src/qbt/backtest/strategy_registry.py` 128~129행

### 무엇이 문제인가?

CLAUDE.md에는 "원본 DataFrame을 변경하지 않음, 계산 시 복사본 사용"이라고 명시되어 있습니다.
하지만 Buy & Hold 전략의 signal 준비 함수는 원본을 그대로 반환합니다:

```python
# strategy_registry.py (128~129행)
def _prepare_buy_and_hold_signal_df(df: pd.DataFrame, slot: AssetSlotConfig) -> pd.DataFrame:
    return df  # <-- 원본 그대로 반환! df.copy()가 없음
```

반면 버퍼존 전략의 동일 함수는 내부에서 `add_single_moving_average`를 호출하는데,
이 함수는 `df.copy()`를 수행합니다 (analysis.py 55행):

```python
# analysis.py (55행)
def add_single_moving_average(df, window, ...):
    df = df.copy()  # <-- 복사본 사용
```

이렇게 되면 두 전략의 동작이 일관되지 않습니다:
- 버퍼존: 원본 보호됨 (새 DataFrame 반환)
- Buy & Hold: 원본이 그대로 전달되므로, 이후 코드에서 수정하면 원본도 변경됨

---

## 1-5. CLAUDE.md 문서 자체의 코드 불일치 (2건)

> 심각도: **낮음** | 파일: `src/qbt/backtest/CLAUDE.md`

### (a) BufferZoneStrategy 생성자의 ma_type 파라미터

backtest CLAUDE.md에 `BufferZoneStrategy` 생성자 시그니처를 이렇게 적어두었습니다:
> `생성자: (ma_col, buy_buffer_pct, sell_buffer_pct, hold_days, ma_type="ema")`

하지만 실제 코드에는 `ma_type` 파라미터가 없습니다:

```python
# buffer_zone.py (294~300행)
def __init__(
    self,
    ma_col: str,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
    hold_days: int,        # <-- ma_type이 없음!
) -> None:
```

MA 계산은 runner에서 처리하므로 전략 클래스가 알 필요 없는 설계입니다.
문서가 코드와 맞지 않으므로, 문서를 수정해야 합니다.

### (b) StrategySpec의 supports_single, supports_portfolio 필드

backtest CLAUDE.md에 "예약 필드"로 `supports_single`, `supports_portfolio`를 언급하지만,
실제 `StrategySpec` 클래스에는 이 필드들이 존재하지 않습니다.

---

# 2부. 논리적 오류 및 잠재적 버그

## 2-1. pnl_pct 계산 방식 불일치

> 심각도: **긴급** | 파일: `engine_common.py` 164행 vs `portfolio_execution.py` 123행

### 무엇이 문제인가?

`pnl_pct`는 "손익률"입니다. 100원에 산 주식을 110원에 팔면 `pnl_pct = 0.10 (10%)`입니다.
이 계산 공식이 두 엔진에서 **다릅니다**.

**단일 백테스트 엔진:**
```python
# engine_common.py (164행)
"pnl_pct": (sell_price - entry_price) / entry_price,
```

**포트폴리오 엔진:**
```python
# portfolio_execution.py (123행)
"pnl_pct": (sell_price - e_price) / (e_price + EPSILON),
```

### 차이점은?

포트폴리오 엔진에서는 분모에 `EPSILON`(= 1e-12, 매우 작은 수)을 더합니다.
이는 `e_price`(진입 가격)가 0일 때 "0으로 나누기" 에러를 방지하기 위한 것입니다.

하지만 문제가 있습니다:

1. **진입 가격이 0인 것은 비정상**: 주식을 0원에 사는 것은 불가능합니다.
   0이 나왔다면 데이터 오류이므로, EPSILON으로 살짝 더하는 것은 근본 해결이 아닙니다.

2. **미세한 수치 차이**: 같은 거래를 두 엔진에서 각각 실행하면, 소수점 아래에서 미세하게 다른 결과가 나옵니다.
   예를 들어 `entry_price = 100.0`일 때:
   - 단일 엔진: `10 / 100.0 = 0.1`
   - 포트폴리오: `10 / (100.0 + 1e-12) = 0.09999999999...`

### 수정 방향

두 엔진의 계산 공식을 통일해야 합니다.
`entry_price`가 0인 경우는 상위에서 검증하고, 계산 공식 자체는 동일하게 유지합니다.

---

## 2-2. params_schedule 전환 시 건너뛴 날짜 미처리

> 심각도: **높음** | 파일: `src/qbt/backtest/engines/backtest_engine.py` 300~304행

### 배경: params_schedule이란?

WFO(Walk-Forward Optimization) Dynamic 모드에서는 OOS 구간이 바뀔 때마다
전략 파라미터(MA 기간, 버퍼 비율 등)를 교체합니다. `params_schedule`은
"어느 날짜에 어떤 전략으로 바꿀지"를 담은 스케줄입니다.

예: `{2020-01-15: 전략A, 2022-03-20: 전략B, 2024-06-01: 전략C}`

### 무엇이 문제인가?

현재 코드는 전환 날짜를 **하나씩만** 처리합니다:

```python
# backtest_engine.py (300~304행)
if params_schedule is not None and next_switch_idx < len(sorted_switch_dates):
    if current_date >= sorted_switch_dates[next_switch_idx]:
        strategy = params_schedule[sorted_switch_dates[next_switch_idx]]
        next_switch_idx += 1  # <-- 1만 증가!
```

문제 시나리오를 그림으로 보겠습니다:

```
전환 스케줄: [2020-01-15, 2020-01-16, 2022-03-20]
                    ↑ 전략A     ↑ 전략B      ↑ 전략C

만약 데이터에 2020-01-15가 공휴일이라 없고,
다음 거래일이 2020-01-17이라면:

기대하는 동작:
  2020-01-17에 전략A와 전략B를 모두 건너뛰고 → 전략B 적용

실제 동작:
  2020-01-17에 전략A만 적용 (next_switch_idx가 1만 증가)
  다음 날에야 전략B 적용
  → 하루 동안 잘못된 전략이 사용됨!
```

### 수정 방향

`if`를 `while`로 바꾸면 현재 날짜 이전의 모든 전환을 한 번에 처리합니다:

```python
# 수정 후 (개념)
while next_switch_idx < len(sorted_switch_dates):
    if current_date >= sorted_switch_dates[next_switch_idx]:
        strategy = params_schedule[sorted_switch_dates[next_switch_idx]]
        next_switch_idx += 1
    else:
        break
```

---

## 2-3. IS/OOS trade_df에 signal_df 마스크 직접 적용

> 심각도: **중간** | 파일: `src/qbt/backtest/walkforward.py` 291~293행, `scripts/backtest/run_walkforward.py` 141~143행

### 무엇이 문제인가?

"마스크(mask)"란 DataFrame에서 원하는 행만 골라내는 필터입니다.
예를 들어 `2020-01-01 ~ 2020-12-31` 사이의 데이터만 추출하고 싶을 때 사용합니다.

현재 코드에서는 **signal_df에서 만든 마스크를 trade_df에도 그대로 적용**합니다:

```python
# walkforward.py (291~293행)
is_mask = (signal_df_with_ma[COL_DATE] >= is_start) & (signal_df_with_ma[COL_DATE] <= is_end)
is_signal = signal_df_with_ma[is_mask].reset_index(drop=True)
is_trade = trade_df[is_mask].reset_index(drop=True)  # <-- signal_df의 마스크를 trade_df에 적용!
```

이것은 `signal_df`와 `trade_df`의 행 수와 인덱스가 **완전히 동일하다**는 것을 전제합니다.

### 왜 위험한가?

현재는 호출 전에 `extract_overlap_period`(겹치는 기간 추출)이 선행되므로 대부분 안전합니다.
하지만 만약 코드를 수정하면서 이 전제가 깨지면, 잘못된 행이 선택됩니다.

비유하면: "A반 출석부로 B반 학생을 호명하는 것"과 같습니다.
현재는 A반과 B반의 학생 수가 같아서 문제가 없지만, 전학생이 오면 어긋납니다.

### 수정 방향

`trade_df` 자체의 날짜 컬럼으로 독립적인 마스크를 만드는 것이 안전합니다:

```python
# 방어적 코딩 (개념)
is_signal = signal_df_with_ma[(signal_df_with_ma[COL_DATE] >= is_start) & (signal_df_with_ma[COL_DATE] <= is_end)]
is_trade = trade_df[(trade_df[COL_DATE] >= is_start) & (trade_df[COL_DATE] <= is_end)]
```

---

## 2-4. drawdown 계산 방어 로직 불일치

> 심각도: **중간** | 파일: `analysis.py` 160행 vs `portfolio_data.py` 83행

### 무엇이 문제인가?

drawdown(최대 낙폭)을 계산할 때, "최고점(peak)"이 0이면 0으로 나누기 에러가 발생합니다.
이를 방지하기 위한 "방어 코드"가 두 곳에서 **다르게** 구현되어 있습니다:

**analysis.py (160행):**
```python
safe_peak = equity_df["peak"].replace(0, EPSILON)
# peak가 정확히 0인 값만 EPSILON으로 교체
```

**portfolio_data.py (83행):**
```python
equity_df["drawdown_pct"] = (equity_df["equity"] - peak) / (peak + EPSILON) * 100.0
# 모든 peak에 EPSILON을 더함
```

### 차이점은?

- `replace(0, EPSILON)`: peak가 0인 경우**만** 보정. 나머지 값은 원래대로.
- `peak + EPSILON`: **모든** peak에 아주 작은 수를 더함. 0이 아닌 값도 미세하게 변함.

실제로 두 방식의 결과 차이는 무시할 수준(1e-12 이하)이지만,
같은 계산을 다른 방식으로 하면 유지보수 시 혼란을 줍니다.

---

## 2-5. compute_bands 이중 호출

> 심각도: **중간** | 파일: `src/qbt/backtest/runners.py` 82~83행

### 무엇이 문제인가?

`compute_bands` 함수는 MA(이동평균) 값을 받아서 상단 밴드(upper)와 하단 밴드(lower)를 **동시에** 반환합니다:

```python
def compute_bands(ma_value, buy_buffer_pct, sell_buffer_pct):
    return (upper_band, lower_band)  # 튜플로 2개 값 동시 반환
```

하지만 `_enrich_equity_with_bands`에서는 이 함수를 **2번 호출**해서 각각 하나씩만 사용합니다:

```python
# runners.py (82~83행)
band_df["upper_band"] = band_df[ma_col].apply(
    lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[0]  # 1번째 호출 → upper만 사용
)
band_df["lower_band"] = band_df[ma_col].apply(
    lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[1]  # 2번째 호출 → lower만 사용
)
```

### 왜 비효율적인가?

매 행마다 같은 함수를 2번 호출합니다. 데이터가 6000행이면 12000번 호출됩니다.
한 번 호출해서 양쪽을 다 받으면 6000번이면 됩니다.

### 수정 방향

```python
# 수정 후 (개념)
bands = band_df[ma_col].apply(
    lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)
)
band_df["upper_band"] = bands.apply(lambda x: x[0])
band_df["lower_band"] = bands.apply(lambda x: x[1])
```

---

## 2-6. check_buy/check_sell 상태 비동기화 가능성

> 심각도: **중간** | 파일: `src/qbt/backtest/engines/portfolio_planning.py` 128~162행

### 배경: 전략 객체의 "내부 상태"란?

`BufferZoneStrategy`는 "이전 날의 상단 밴드(`_prev_upper`)"와 "이전 날의 하단 밴드(`_prev_lower`)"를
기억하는 내부 상태를 가지고 있습니다. 오늘의 종가가 어제의 밴드를 돌파했는지 비교하기 위해서입니다.

`check_buy`를 호출하면 `_prev_upper`와 `_prev_lower`가 **둘 다** 갱신됩니다.
`check_sell`을 호출해도 **둘 다** 갱신됩니다.

### 무엇이 문제인가?

엔진은 포지션 상태에 따라 **한쪽만** 호출합니다:

```python
# portfolio_planning.py (133~149행)
if state.position == 0:
    buy_now = strategy.check_buy(signal_df, i, current_date)  # check_buy만 호출
elif state.position > 0:
    sell_now = strategy.check_sell(signal_df, i)               # check_sell만 호출
```

포지션이 0인 동안은 `check_sell`이 한 번도 호출되지 않습니다.
이 기간 동안 `_prev_lower`는 `check_buy` 내부에서 갱신되므로 문제가 없지만,
코드의 의도를 이해하기 어렵고 "한쪽에서만 갱신"되는 것에 암묵적으로 의존합니다.

단일 백테스트 엔진(backtest_engine.py)도 동일한 패턴이므로 현재는 일관되지만,
전략 객체의 상태 관리가 호출 순서에 강하게 의존하는 구조입니다.

---

## 2-7. execute_buy_order / execute_sell_order의 미사용 order 파라미터

> 심각도: **낮음** | 파일: `src/qbt/backtest/engines/engine_common.py` 84~169행

### 무엇이 문제인가?

두 함수 모두 첫 번째 파라미터로 `order: PendingOrder`를 받지만,
함수 본문에서 **한 번도 사용하지 않습니다**:

```python
# engine_common.py (84~119행)
def execute_buy_order(
    order: PendingOrder,      # <-- 받기만 하고 안 씀!
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
) -> tuple[...]:
    buy_price = open_price * (1 + SLIPPAGE_RATE)  # order는 어디에도 없음
    shares = int(capital / buy_price)
    ...
```

YAGNI(You Aren't Gonna Need It) 원칙에 따르면, 사용하지 않는 파라미터는 제거하는 것이 좋습니다.
불필요한 파라미터는 코드를 읽는 사람을 혼란스럽게 합니다.

---

## 2-8. calculate_summary의 final_capital <= 0 시 CAGR=0 반환

> 심각도: **낮음** | 파일: `src/qbt/backtest/analysis.py` 150행

### 무엇이 문제인가?

CAGR(복리 연환산 수익률)을 계산할 때, `final_capital > 0`인 경우에만 계산하고
그렇지 않으면 0을 반환합니다:

```python
# analysis.py (150행)
if years > 0 and final_capital > 0:
    cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
else:
    cagr = 0.0  # <-- 자본이 0이면 CAGR=0? 실제로는 -100%여야 함
```

1000만원 투자해서 자본이 0원이 되면 CAGR은 -100%이어야 합니다.
하지만 현재 코드는 0%로 반환합니다. 다만 현재 구조(슬리피지 + 정수 주식수)에서
자본이 정확히 0이 되는 경우는 극히 드뭅니다.

---

## 2-9. `__import__("datetime")` 비관습적 패턴

> 심각도: **낮음** | 파일: `src/qbt/backtest/walkforward.py` 155행

```python
# walkforward.py (155행)
def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1).replace(day=1) - __import__("datetime").timedelta(days=1)
```

`__import__("datetime")`는 Python의 저수준 import 함수를 직접 호출하는 것으로,
일반적으로 사용하지 않는 패턴입니다. 파일 상단에서 `from datetime import timedelta`를
추가하면 됩니다.

또한 `.replace(day=1)`은 이미 `date(year, month+1, 1)`로 day=1이 보장되므로 중복 호출입니다.

---

## 2-10. STRATEGY_CONFIG 타입 주석 부정확

> 심각도: **낮음** | 파일: `scripts/backtest/run_walkforward.py` 64행

```python
# run_walkforward.py (64행)
STRATEGY_CONFIG: dict[str, dict[str, Path | list[int] | list[float] | None]] = {
    _tqqq.strategy_name: {
        "signal_path": _tqqq.signal_data_path,  # Path
        "trade_path": _tqqq.trade_data_path,     # Path
        "result_dir": _tqqq.result_dir,           # Path
    },
    ...
}
```

타입 주석에 `list[int] | list[float] | None`이 포함되어 있지만,
실제 딕셔너리 값은 모두 `Path` 타입뿐입니다. 불필요한 Union 타입이 포함되어 있어
코드를 읽는 사람에게 "리스트 값도 있나?"라는 혼란을 줍니다.

---

## 2-11. portfolio_configs.py docstring 오타

> 심각도: **낮음** | 파일: `src/qbt/backtest/portfolio_configs.py` 2행

`"정의돈 실험을"` → `"정의된 실험을"`

---

## 2-12. PortfolioResult.config의 빈 기본값

> 심각도: **낮음** | 파일: `src/qbt/backtest/portfolio_types.py` 147~155행

```python
config: PortfolioConfig = field(
    default_factory=lambda: PortfolioConfig(
        experiment_name="",
        display_name="",
        asset_slots=(),
        total_capital=0.0,      # <-- 자본금 0원?
        result_dir=Path("."),   # <-- 현재 디렉토리?
    )
)
```

기본값이 의미 없는 값(`total_capital=0.0`)으로 설정되어 있습니다.
실제로는 항상 명시적으로 전달되므로 문제 없지만,
기본값 대신 필수 파라미터로 만드는 것이 안전합니다.

---

# 3부. 리팩토링 대상

## 3-1. trades CSV 저장 로직 3중 중복

> 심각도: **높음** | 해당 파일 3개

### 무엇이 문제인가?

거래 내역(trades)을 CSV로 저장하는 코드가 3개 스크립트에서 **거의 동일하게** 반복됩니다:

**파일 1: run_single_backtest.py (168~192행)**
```python
trades_export = result.trades_df.copy()
if "entry_date" in trades_export.columns and "exit_date" in trades_export.columns:
    trades_export["holding_days"] = trades_export.apply(
        lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
    )
trades_round = {}
if "entry_price" in trades_export.columns:
    trades_round["entry_price"] = 6
if "exit_price" in trades_export.columns:
    trades_round["exit_price"] = 6
if "pnl" in trades_export.columns:
    trades_round["pnl"] = 0
...
```

**파일 2: run_walkforward.py (380~402행)** — 거의 동일한 코드

**파일 3: run_portfolio_backtest.py (85~110행)** — 거의 동일한 코드 (상수 `_PRICE_ROUND` 사용)

### 왜 문제인가?

1. **유지보수**: 반올림 자릿수를 바꾸려면 3곳을 모두 수정해야 함
2. **일관성**: 한 곳만 수정하고 나머지를 빠뜨리면 스크립트마다 결과가 다름
3. **가독성**: 같은 코드가 3번 반복되면 "어떤 게 원본인지" 혼란

### 수정 방향

공용 함수로 추출합니다. 예시:
```python
# src/qbt/backtest/csv_export.py (새 모듈)
def save_trades_csv(trades_df: pd.DataFrame, path: Path) -> None:
    """trades DataFrame을 표준 형식으로 CSV 저장한다."""
    ...
```

---

## 3-2. drawdown_pct 계산 로직 2중 중복

> 심각도: **높음** | 해당 파일 2개 + analysis.py 유사 로직

동일한 drawdown 계산 패턴이 2개 스크립트에 반복됩니다 (1-2c에서 이미 설명).
`analysis.py`에도 유사한 로직이 있으므로, 여기에 공용 함수를 두는 것이 적절합니다.

```python
# 3곳에서 반복되는 패턴:
equity_series = df["equity"].astype(float)
peak = equity_series.cummax()
safe_peak = peak.replace(0, EPSILON)
df["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
```

---

## 3-3. 데이터 로딩 패턴 3중 중복

> 심각도: **높음** | 해당 파일 3개

"signal 경로와 trade 경로가 같으면 copy, 다르면 각각 로딩 후 overlap 추출"하는
패턴이 3곳에서 반복됩니다:

**파일 1: runners.py (119~127행)**
```python
if config.signal_data_path == config.trade_data_path:
    trade_df = load_stock_data(config.trade_data_path)
    signal_df = trade_df.copy()
else:
    signal_df = load_stock_data(config.signal_data_path)
    trade_df = load_stock_data(config.trade_data_path)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)
```

**파일 2: run_walkforward.py (78~92행, `_load_data`)** — 동일 패턴

**파일 3: run_param_plateau_all.py (146~167행, `_load_asset_data`)** — 동일 패턴

### 수정 방향

공용 함수로 추출합니다:
```python
# src/qbt/utils/data_loader.py에 추가
def load_signal_trade_pair(signal_path: Path, trade_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    ...
```

---

## 3-4. 반올림 규칙 상수 미통일

> 심각도: **높음**

CLAUDE.md에 반올림 규칙이 명확히 정의되어 있습니다:

| 데이터 유형 | 소수점 자릿수 |
|------------|:----------:|
| 가격 | 6자리 |
| 자본금 | 0자리 |
| 백분율 | 2자리 |
| 비율 | 4자리 |

하지만 구현에서는 파일마다 다릅니다:

**run_portfolio_backtest.py** — 상수 사용 (양호):
```python
_PRICE_ROUND = 6
_EQUITY_ROUND = 0
_PNL_PCT_ROUND = 4
```

**run_single_backtest.py** — 리터럴 숫자 직접 사용:
```python
trades_round["entry_price"] = 6   # 매직 넘버!
trades_round["pnl"] = 0          # 매직 넘버!
trades_round["pnl_pct"] = 4      # 매직 넘버!
```

**run_walkforward.py** — 역시 리터럴 숫자 직접 사용

### 수정 방향

반올림 상수를 `common_constants.py` 또는 `backtest/constants.py`에 정의하고
모든 스크립트에서 참조합니다.

---

## 3-5. 반복 사용 컬럼명 상수화 미적용

> 심각도: **높음**

CLAUDE.md 상수 명명 규칙에서 `COL_*` 접두사로 DataFrame 컬럼명을 관리하도록 규정하고 있습니다.
또한 "도메인 내 2개 이상 파일에서 사용 → constants.py에 정의"가 규칙입니다.

하지만 다수의 컬럼명이 문자열 리터럴로 여러 파일에 흩어져 있습니다:

| 문자열 리터럴 | 사용 위치 | 비고 |
|-------------|----------|------|
| `"equity"` | analysis.py, engine_common.py, portfolio_data.py | 3개 이상 파일 |
| `"pnl"` | analysis.py, engine_common.py, portfolio_execution.py | 3개 이상 파일 |
| `"entry_date"` | analysis.py, engine_common.py, 스크립트 3개 | 5개 이상 파일 |
| `"exit_date"` | analysis.py, engine_common.py, 스크립트 3개 | 5개 이상 파일 |
| `"upper_band"` | runners.py, 앱 스크립트들 | 2개 이상 파일 |
| `"lower_band"` | runners.py, 앱 스크립트들 | 2개 이상 파일 |
| `"buy_buffer_pct"` | buffer_zone.py, engine_common.py | 2개 이상 파일 |
| `"hold_days_used"` | buffer_zone.py, engine_common.py | 2개 이상 파일 |
| `"position"` | engine_common.py, backtest_engine.py | 2개 이상 파일 |

### 왜 위험한가?

오타가 발생하면 런타임 에러로만 발견됩니다. 예를 들어:
```python
df["equty"]  # 오타! "equity"가 아님. 실행해봐야 KeyError 발생
```

상수를 사용하면 IDE 자동완성과 타입 체커가 오타를 잡아줍니다:
```python
df[COL_EQUITY]  # 오타 불가능. COL_EQUTY라고 쓰면 import 시점에 에러
```

### 수정 방향

`backtest/constants.py`에 다음과 같이 정의:
```python
COL_EQUITY: Final = "equity"
COL_PNL: Final = "pnl"
COL_ENTRY_DATE: Final = "entry_date"
COL_EXIT_DATE: Final = "exit_date"
...
```

---

## 3-6. common_constants.py의 개별 결과 디렉토리 상수 과잉

> 심각도: **중간** | 파일: `src/qbt/common_constants.py` 50~67행

### 무엇이 문제인가?

16개의 개별 결과 디렉토리 상수가 `common_constants.py`에 정의되어 있습니다:

```python
# common_constants.py (50~67행)
BUFFER_ZONE_TQQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_tqqq"
BUFFER_ZONE_QQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_qqq"
BUY_AND_HOLD_QQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buy_and_hold_qqq"
BUY_AND_HOLD_TQQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buy_and_hold_tqqq"
BUFFER_ZONE_SPY_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_spy"
BUFFER_ZONE_IWM_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_iwm"
# ... 총 16개
```

CLAUDE.md의 상수 관리 규칙에 따르면:
> "1개 파일에서만 사용 → 해당 파일 상단"

이 상수들 대부분은 `buffer_zone.py`의 CONFIGS나 `buy_and_hold.py`의 CONFIGS에서만 사용됩니다.
즉, **공통 상수가 아니라 해당 파일 로컬 상수**여야 합니다.

### 수정 방향

`BACKTEST_RESULTS_DIR`만 공통 상수로 유지하고,
개별 전략 디렉토리는 CONFIGS 정의에서 직접 구성:

```python
# buffer_zone.py CONFIGS 내
result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_spy",
```

---

## 3-7. MA 컬럼명 구성 패턴 반복

> 심각도: **중간**

`f"ma_{window}"` 패턴이 최소 3곳에서 반복됩니다:

```python
# backtest_engine.py (175행)
ma_col = f"ma_{params.ma_window}"

# backtest_engine.py (526행)  
ma_col = f"ma_{params.ma_window}"

# analysis.py (59행)
col_name = f"ma_{window}"
```

MA 컬럼 네이밍 규칙이 변경될 경우(예: `"ema_200"`, `"sma_50"` 등으로 세분화)
여러 곳을 모두 수정해야 합니다.

### 수정 방향

```python
# constants.py에 추가
def make_ma_col_name(window: int) -> str:
    return f"ma_{window}"
```

---

## 3-8. 유효 행 필터링 패턴 2중 중복

> 심각도: **중간** | 파일: `backtest_engine.py` 176~178행, 534~536행

동일한 3줄 패턴이 같은 파일 내에서 2번 반복됩니다:

```python
# _run_backtest_for_grid (176~178행) 그리고 run_buffer_strategy (534~536행)
valid_mask = signal_df[ma_col].notna()
filtered_signal = signal_df[valid_mask].reset_index(drop=True)
filtered_trade = trade_df[valid_mask].reset_index(drop=True)
```

### 수정 방향

헬퍼 함수로 추출:
```python
def _filter_valid_rows(signal_df, trade_df, ma_col):
    valid_mask = signal_df[ma_col].notna()
    return (
        signal_df[valid_mask].reset_index(drop=True),
        trade_df[valid_mask].reset_index(drop=True),
    )
```

---

## 3-9. portfolio_engine.py 내 데이터 로딩/필터링 중복

> 심각도: **중간** | 파일: `src/qbt/backtest/engines/portfolio_engine.py`

`compute_portfolio_effective_start_date()`와 `run_portfolio_backtest()` 두 함수에서
다음 로직이 **거의 동일하게** 중복됩니다:

1. `signal_cache` 딕셔너리 기반 캐시 관리
2. 공통 기간 추출 (`date_sets` 교집합 → `common_dates_set`)
3. MA 워밍업 구간 필터링 (`STRATEGY_REGISTRY` → `get_warmup_periods()`)

이 세 블록을 내부 헬퍼 함수로 추출하면 중복을 제거할 수 있습니다.

---

## 3-10. 포트폴리오 체결 로직 — engine_common.py와 통합 가능

> 심각도: **중간** | 파일: `portfolio_execution.py` vs `engine_common.py`

1-3번에서 설명한 것처럼, 포트폴리오 엔진의 핵심 체결 산식은 engine_common.py와 동일합니다:

```python
# 두 엔진 모두 동일:
buy_price = open_price * (1 + SLIPPAGE_RATE)
shares = int(amount / buy_price)
sell_price = open_price * (1 - SLIPPAGE_RATE)
```

멀티 자산 특성(`scale_factor`, 가중평균 `entry_price`)만 확장하면
공통 체결 함수를 재사용할 수 있습니다.

---

## 3-11. check_buy/check_sell 내부 밴드 계산/prev 갱신 중복

> 심각도: **중간** | 파일: `src/qbt/backtest/strategies/buffer_zone.py`

`check_buy`(346~409행)와 `check_sell`(439~463행) 모두 동일한 패턴을 반복합니다:

```python
# check_buy 안 (346~368행):
row = signal_df.iloc[i]
ma_val = float(row[self._ma_col])
cur_upper, cur_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)
cur_close = float(row[COL_CLOSE])
if self._prev_upper is None:
    ...
self._prev_upper = cur_upper
self._prev_lower = cur_lower

# check_sell 안 (439~461행):
row = signal_df.iloc[i]
ma_val = float(row[self._ma_col])
cur_upper, cur_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)
cur_close = float(row[COL_CLOSE])
if self._prev_lower is None:
    ...
self._prev_upper = cur_upper
self._prev_lower = cur_lower
```

### 수정 방향

공통 부분을 내부 메서드로 추출:
```python
def _update_bands(self, signal_df, i):
    """밴드를 계산하고 prev 상태를 갱신한다."""
    ...
```

---

## 3-12. resolve_buffer_params의 sources 딕셔너리 — 항상 "FIXED"

> 심각도: **중간** | 파일: `src/qbt/backtest/strategies/buffer_zone.py` 105~110행

과거에는 WFO 등에서 동적 파라미터 소스를 구분하기 위해 사용했지만,
현재 4P 고정으로 통일된 이후 이 딕셔너리는 항상 `"FIXED"`입니다:

```python
# buffer_zone.py (105~110행)
sources = {
    "ma_window": "FIXED",
    "buy_buffer_zone_pct": "FIXED",
    "sell_buffer_zone_pct": "FIXED",
    "hold_days": "FIXED",
}
```

분기가 없으므로 함수의 존재 의의가 "파라미터 검증 + BufferStrategyParams 생성"으로
축소되었습니다. 간소화를 검토할 수 있습니다.

---

## 3-13. resolve_buffer_params에서 ma_window 검증 누락

> 심각도: **낮음** | 파일: `src/qbt/backtest/strategies/buffer_zone.py` 90~95행

다른 파라미터는 최솟값 검증이 있지만, `ma_window`에 대한 검증이 없습니다:

```python
# buffer_zone.py (90~95행)
if buy_buffer_zone_pct < MIN_BUY_BUFFER_ZONE_PCT:     # ✅ 검증 있음
    raise ValueError(...)
if sell_buffer_zone_pct < MIN_SELL_BUFFER_ZONE_PCT:    # ✅ 검증 있음
    raise ValueError(...)
if hold_days < MIN_HOLD_DAYS:                          # ✅ 검증 있음
    raise ValueError(...)
# ma_window 검증 없음!                                  # ❌ 누락
```

`ma_window`가 0이나 음수일 때 이동평균 계산에서 예상치 못한 동작이 발생할 수 있습니다.

---

## 3-14. type: ignore[assignment] 대신 명시적 narrowing

> 심각도: **낮음** | 파일: `src/qbt/backtest/strategies/buffer_zone.py` 363행, 456행

```python
# buffer_zone.py (363행)
prev_upper: float = self._prev_upper  # type: ignore[assignment]

# buffer_zone.py (456행)
prev_lower: float = self._prev_lower  # type: ignore[assignment]
```

`type: ignore`는 "타입 체커야, 이 줄은 무시해"라는 뜻입니다.
코드 앞부분에서 이미 `None`이 아님이 보장되었으므로 동작에는 문제없지만,
`assert` 또는 `cast`를 사용하면 런타임에도 안전합니다:

```python
# 더 안전한 방법:
assert self._prev_upper is not None
prev_upper = self._prev_upper
```

---

## 3-15. signal CSV의 change_pct 계산 2중 중복

> 심각도: **낮음** | 파일: `run_single_backtest.py` 101행, `run_portfolio_backtest.py` 120행

```python
# 두 파일 모두 동일:
signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100
```

---

## 3-16. 포트폴리오 trade_record가 dict[str, Any] — 타입 불안전

> 심각도: **낮음** | 파일: `src/qbt/backtest/engines/portfolio_execution.py` 116~128행

단일 엔진은 `TradeRecord` TypedDict를 사용하지만, 포트폴리오 엔진은 일반 딕셔너리를 사용합니다:

```python
# portfolio_execution.py (116~128행)
trade_record: dict[str, Any] = {    # <-- TypedDict 아님!
    "entry_date": e_date,
    "exit_date": current_date,
    "entry_price": e_price,
    "exit_price": sell_price,
    "shares": shares_sold,
    "pnl": (sell_price - e_price) * shares_sold,
    "pnl_pct": (sell_price - e_price) / (e_price + EPSILON),
    "hold_days_used": e_hold_days.get(asset_id, 0),
    "asset_id": asset_id,
    "trade_type": "rebalance" if ... else "signal",
}
```

`dict[str, Any]`는 어떤 키든 넣을 수 있으므로, 오타(`"enrty_date"`)가 발견되지 않습니다.
포트폴리오 전용 TypedDict를 정의하면 타입 안전성이 향상됩니다.

---

## 3-17. compute_projected_portfolio의 미사용 asset_closes_map 파라미터

> 심각도: **낮음** | 파일: `src/qbt/backtest/engines/portfolio_planning.py` 171행

```python
def compute_projected_portfolio(
    asset_states: dict[str, AssetState],
    signal_intents: dict[str, OrderIntent],
    equity_vals: dict[str, float],
    asset_closes_map: dict[str, float],   # <-- 본문에서 사용 안 함!
    shared_cash: float,
) -> ProjectedPortfolio:
```

docstring에 "사용 안 함, 확장성 위해 유지"라고 적혀 있지만,
YAGNI 원칙에 따르면 현재 사용하지 않는 파라미터는 제거하는 것이 좋습니다.

---

## 3-18. PendingOrder의 strategies 패키지 re-export

> 심각도: **낮음** | 파일: `src/qbt/backtest/strategies/__init__.py` 11행

```python
# strategies/__init__.py (11행)
from qbt.backtest.engines.engine_common import PendingOrder
```

`PendingOrder`는 **엔진 공통**(`engine_common.py`)에 정의된 데이터 구조입니다.
이것을 **전략** 패키지(`strategies/`)에서 re-export하는 것은
계층 구조가 어긋납니다 (전략 → 엔진 방향의 의존).

사용자는 `qbt.backtest.engines.engine_common`에서 직접 import하는 것이 명확합니다.

---

# 4부. 긍정적 평가

분석 결과, **핵심 비즈니스 로직은 모두 정확하게 구현**되어 있습니다:

| 규칙 | 상태 | 구현 위치 |
|------|:----:|----------|
| 체결 타이밍 (i일 신호 → i+1일 시가 체결) | 정상 | backtest_engine.py |
| Pending Order 정책 (단일 슬롯, 충돌 시 예외) | 정상 | engine_common.py, backtest_engine.py |
| hold_days 상태머신 (Lookahead 방지) | 정상 | buffer_zone.py |
| Equity 정의 (cash + position * close) | 정상 | engine_common.py |
| 비용 모델 (매수 +0.3%, 매도 -0.3%) | 정상 | engine_common.py, portfolio_execution.py |
| 강제청산 없음 (마지막 날 포지션 유지) | 정상 | backtest_engine.py |
| 미청산 포지션 기록 (open_position) | 정상 | backtest_engine.py |
| 신호 감지 (상향/하향 돌파) | 정상 | buffer_zone_helpers.py |

특히 `parameter_stability.py`는 상수 관리, 검증, docstring, 타입 힌트 모두 양호합니다.

테스트 커버리지도 핵심 계약/불변조건에 대해 충분히 작성되어 있습니다.
리팩토링 이후 기본 로직의 품질은 전반적으로 **양호**합니다.

---

# 5부. 우선순위 요약표

| 우선순위 | ID | 카테고리 | 핵심 내용 | 파일 |
|:-------:|:--:|---------|-----------|------|
| **긴급** | 1-2 | 규칙 위반 | CLI에 비즈니스 로직 포함 (run_walkforward.py) | run_walkforward.py |
| **긴급** | 2-1 | 버그 | pnl_pct 계산 방식 불일치 (단일 vs 포트폴리오) | engine_common.py, portfolio_execution.py |
| **높음** | 2-2 | 버그 | params_schedule 전환 시 건너뛴 날짜 미처리 | backtest_engine.py |
| **높음** | 1-3 | 규칙 위반 | 포트폴리오 엔진이 engine_common.py 미사용 | portfolio_execution.py |
| **높음** | 3-1 | 리팩토링 | trades CSV 저장 로직 3중 중복 | 스크립트 3개 |
| **높음** | 3-2 | 리팩토링 | drawdown_pct 계산 2중 중복 | 스크립트 2개 |
| **높음** | 3-3 | 리팩토링 | 데이터 로딩 패턴 3중 중복 | 3개 파일 |
| **높음** | 3-4 | 리팩토링 | 반올림 규칙 상수 미통일 | 스크립트 3개 |
| **높음** | 3-5 | 리팩토링 | 반복 사용 컬럼명 상수화 미적용 | 10+ 파일 |
| **중간** | 1-1 | 규칙 위반 | BufferStrategyParams frozen=True 누락 | types.py |
| **중간** | 2-3 | 버그 | trade_df 마스크 인덱스 정합성 가정 | walkforward.py |
| **중간** | 2-4 | 버그 | drawdown 방어 로직 불일치 | analysis.py, portfolio_data.py |
| **중간** | 2-5 | 버그 | compute_bands 이중 호출 | runners.py |
| **중간** | 2-6 | 버그 | check_buy/check_sell 상태 비동기화 | portfolio_planning.py |
| **중간** | 3-6 | 리팩토링 | common_constants.py 결과 디렉토리 상수 과잉 | common_constants.py |
| **중간** | 3-7 | 리팩토링 | MA 컬럼명 구성 패턴 반복 | 3개 파일 |
| **중간** | 3-8 | 리팩토링 | 유효 행 필터링 패턴 중복 | backtest_engine.py |
| **중간** | 3-9 | 리팩토링 | portfolio_engine.py 데이터 로딩 중복 | portfolio_engine.py |
| **중간** | 3-10 | 리팩토링 | 포트폴리오 체결 로직 통합 가능 | portfolio_execution.py |
| **중간** | 3-11 | 리팩토링 | check_buy/check_sell 밴드 계산 중복 | buffer_zone.py |
| **중간** | 3-12 | 리팩토링 | sources 딕셔너리 항상 "FIXED" | buffer_zone.py |
| **낮음** | 2-7 | 버그 | 미사용 order 파라미터 | engine_common.py |
| **낮음** | 2-8 | 버그 | CAGR=0 반환 (final_capital<=0) | analysis.py |
| **낮음** | 2-9 | 버그 | `__import__` 비관습적 패턴 | walkforward.py |
| **낮음** | 2-10 | 버그 | STRATEGY_CONFIG 타입 주석 부정확 | run_walkforward.py |
| **낮음** | 2-11 | 버그 | docstring 오타 | portfolio_configs.py |
| **낮음** | 2-12 | 버그 | PortfolioResult 빈 기본값 | portfolio_types.py |
| **낮음** | 3-13 | 리팩토링 | ma_window 검증 누락 | buffer_zone.py |
| **낮음** | 3-14 | 리팩토링 | type: ignore 대신 assert/cast | buffer_zone.py |
| **낮음** | 3-15 | 리팩토링 | change_pct 계산 중복 | 스크립트 2개 |
| **낮음** | 3-16 | 리팩토링 | trade_record 타입 불안전 | portfolio_execution.py |
| **낮음** | 3-17 | 리팩토링 | 미사용 asset_closes_map | portfolio_planning.py |
| **낮음** | 3-18 | 리팩토링 | PendingOrder re-export 계층 위반 | strategies/__init__.py |

**총 35건** (문서 위반 5건 + 버그 12건 + 리팩토링 18건)
