# 전략 분리 아키텍처 설계

> 이 문서는 백테스트 전략을 파일 단위로 분리하고,
> 여러 전략을 동시에 비교할 수 있는 구조를 정의한다.

---

## 1. 설계 배경

### 현재 구조의 문제

```
현재:
  src/qbt/backtest/strategy.py  ← 버퍼존 + Buy&Hold + 그리드서치 전부 한 파일
  scripts/backtest/run_single_backtest.py  ← 버퍼존 전용
  storage/results/single_backtest_*.csv    ← 결과 1벌만 저장

문제:
  1. 새 전략을 테스트하려면 strategy.py를 직접 수정해야 함
  2. 결과 CSV가 1벌이라 이전 결과가 덮어써짐
  3. 여러 전략을 동시에 비교할 수 없음
  4. 전략마다 입력 데이터/시그널/매매 방법이 다를 수 있는데 구조가 이를 지원하지 않음
```

### 설계 목표

- 전략 1개 = 파일 1개 (독립적 실행, 독립적 결과)
- 기존 버퍼존과 Buy & Hold도 분리 대상
- 각 전략은 자기만의 입력 파일, 시그널 로직, 매수/매도 방법을 가질 수 있음
- 비교 대시보드는 결과 CSV만 읽어서 모든 전략을 오버레이

---

## 2. 핵심 원칙: 입력은 자유, 출력만 통일

각 전략이 공유하는 것은 **출력 형식**뿐이다.
입력 데이터, 시그널 생성, 매매 로직은 전략마다 완전히 다를 수 있다.

```
전략 A (Buy & Hold):
  입력: TQQQ 데이터만
  매수: 첫날 시가
  매도: 마지막 날 종가

전략 B (버퍼존):
  입력: QQQ(시그널) + TQQQ(매매)
  매수: QQQ 종가 > EMA 상단밴드 돌파 → 다음날 TQQQ 시가
  매도: QQQ 종가 < EMA 하단밴드 돌파 → 다음날 TQQQ 시가

전략 C (버퍼존 + Trailing):
  입력: QQQ(시그널, OHLC) + TQQQ(매매, OHLC) ← ATR 계산에 High/Low 필요
  매수: 버퍼존과 동일
  매도: MA 하향돌파 OR ATR trailing stop 이탈 시 부분 익절
```

---

## 3. 디렉토리 구조

### 비즈니스 로직 (src/qbt/backtest/)

```
src/qbt/backtest/
├── __init__.py              # 패키지 공개 API
├── analysis.py              # 공통 유틸 (MA 계산, calculate_summary, ATR 계산 등)
├── constants.py             # 공통 상수 (SLIPPAGE_RATE, 초기자본 등)
├── types.py                 # 공통 TypedDict (SummaryDict, TradeRecord, EquityRecord)
├── helpers.py               # 공통 헬퍼 함수 (strategy.py에서 분리)
│                              _compute_bands, _execute_buy_order, _execute_sell_order,
│                              _detect_buy_signal, _detect_sell_signal, _record_equity,
│                              PendingOrder, PendingOrderConflictError 등
│
├── strategies/              # 전략 파일들 (1 전략 = 1 파일)
│   ├── __init__.py
│   ├── buy_and_hold.py      # Buy & Hold
│   ├── buffer_zone.py       # 현재 버퍼존 (strategy.py에서 이동)
│   ├── buffer_stoploss.py   # 버퍼존 + Stop Loss
│   └── buffer_trailing.py   # 버퍼존 + ATR Trailing 부분 익절
│
├── strategy.py              # (기존) → 분리 완료 후 제거 또는 하위 호환 래퍼로 유지
└── CLAUDE.md
```

### 스크립트 (scripts/backtest/)

```
scripts/backtest/
├── run_single_backtest.py       # 기존 (특정 전략 하나 실행, 전략 선택 가능하도록 수정)
├── run_grid_search.py           # 기존 (그리드서치)
├── app_single_backtest.py       # 기존 (단일 전략 대시보드)
└── app_strategy_comparison.py   # 신규: 비교 대시보드
```

### 결과 저장 (storage/results/)

```
storage/results/
├── strategies/                  # 전략별 결과 폴더
│   ├── buy_and_hold/
│   │   ├── equity.csv
│   │   ├── trades.csv
│   │   └── summary.json
│   ├── buffer_zone/
│   │   ├── equity.csv
│   │   ├── trades.csv
│   │   └── summary.json
│   ├── buffer_stoploss/
│   │   ├── equity.csv
│   │   ├── trades.csv
│   │   └── summary.json
│   └── buffer_trailing/
│       ├── equity.csv
│       ├── trades.csv
│       └── summary.json
├── grid_results.csv             # 기존 그리드서치 결과 (유지)
├── single_backtest_*.csv        # 기존 단일 백테스트 결과 (과도기 유지, 이후 제거 가능)
└── meta.json
```

---

## 4. 전략 파일 규약

### 각 전략 파일이 반드시 제공하는 것

1. **Params dataclass**: 전략 고유 파라미터
2. **run() 함수**: 전략 실행 진입점
3. **반환값**: `(trades_df, equity_df, summary)` 형식 통일

### 반환 형식 상세

#### equity.csv (비교 대시보드의 핵심)

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| Date | date | O | 날짜 |
| equity | float | O | 해당 시점 평가 자산 |
| position | int | O | 보유 수량 |

전략별로 추가 컬럼 허용 (upper_band, trailing_stop 등). 비교 대시보드는 Date, equity만 사용.

#### trades.csv

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| entry_date | date | O | 진입일 |
| exit_date | date | O | 청산일 |
| entry_price | float | O | 진입가 |
| exit_price | float | O | 청산가 |
| pnl_pct | float | O | 손익률 (0~1) |
| exit_reason | str | O | 매도 사유 (signal, stop_loss, trailing 등) |

전략별로 추가 컬럼 허용. 비교 대시보드는 위 컬럼만 사용.

#### summary.json

```json
{
  "strategy_name": "buffer_zone",
  "summary": {
    "initial_capital": 10000000,
    "final_capital": 123456789,
    "total_return_pct": 1134.57,
    "cagr": 10.23,
    "mdd": -42.83,
    "total_trades": 16,
    "winning_trades": 11,
    "losing_trades": 5,
    "win_rate": 68.75,
    "start_date": "1999-03-10",
    "end_date": "2025-08-06"
  },
  "params": { ... },
  "data_info": { ... }
}
```

### 전략 파일 예시

```python
# src/qbt/backtest/strategies/buffer_stoploss.py

"""버퍼존 + Stop Loss 전략

기존 버퍼존 전략에 진입가 대비 고정 비율 손절을 추가한다.
매도 조건: MA 하향돌파 OR TQQQ 종가 < 진입가 * (1 - stop_loss_pct)
"""

from dataclasses import dataclass

from qbt.backtest.helpers import (
    BaseStrategyParams,
    _compute_bands,
    _execute_buy_order,
    _execute_sell_order,
    _record_equity,
)


@dataclass
class BufferStopLossParams(BaseStrategyParams):
    """버퍼존 + Stop Loss 전략 파라미터."""

    ma_window: int
    buffer_zone_pct: float
    hold_days: int
    recent_months: int
    stop_loss_pct: float  # 손절 비율 (0.20 = 20%)


def run(signal_df, trade_df, params):
    """
    버퍼존 + Stop Loss 전략을 실행한다.

    Args:
        signal_df: 시그널용 DataFrame (QQQ, Close + MA 필요)
        trade_df: 매매용 DataFrame (TQQQ, Open + Close 필요)
        params: BufferStopLossParams

    Returns:
        tuple: (trades_df, equity_df, summary)
    """
    # 기존 버퍼존 로직 + stop loss 조건 추가
    ...
```

---

## 5. 비교 대시보드 (app_strategy_comparison.py)

### 동작 방식

```
1. storage/results/strategies/ 하위 폴더를 스캔
2. 각 폴더에서 equity.csv + summary.json 로드
3. 전략별 equity 곡선을 하나의 Plotly 차트에 오버레이
4. 요약 지표 비교 테이블 표시
```

### 화면 구성 (안)

```
┌─────────────────────────────────────────────────────────┐
│  [전략 비교 대시보드]                                      │
│                                                         │
│  Equity 곡선 오버레이 (Plotly)                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │ ── 버퍼존 (파랑)                                  │    │
│  │ ── 버퍼존+StopLoss (빨강)                         │    │
│  │ ── 버퍼존+Trailing (초록)                         │    │
│  │ ── Buy&Hold (회색 점선)                           │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  요약 비교 테이블                                         │
│  ┌────────────────┬────────┬────────┬────────┬───────┐  │
│  │ 전략           │ CAGR   │ MDD    │ 거래수 │ 승률  │  │
│  ├────────────────┼────────┼────────┼────────┼───────┤  │
│  │ 버퍼존         │ 10.2%  │ -42.8% │ 16     │ 68.8% │  │
│  │ 버퍼존+StopLoss│ 9.8%   │ -20.0% │ 22     │ 72.7% │  │
│  │ 버퍼존+Trailing│ 11.1%  │ -28.5% │ 20     │ 70.0% │  │
│  │ Buy&Hold       │ 8.5%   │ -78.2% │ 1      │ 100%  │  │
│  └────────────────┴────────┴────────┴────────┴───────┘  │
│                                                         │
│  거래 내역 비교 (전략 선택 시 상세 표시)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 전략 추가 시 변경 범위

```
새 전략 추가 = 파일 2개만 추가:
  1. src/qbt/backtest/strategies/새전략.py   ← 전략 로직
  2. storage/results/strategies/새전략/      ← 실행 시 자동 생성

대시보드 코드 변경 없음 (폴더 스캔 방식이므로 자동 반영)
```

---

## 6. 공통 헬퍼 모듈 (helpers.py)

기존 `strategy.py`에서 전략 간 공유 가능한 함수를 분리한다.

### 분리 대상

```
strategy.py에서 helpers.py로 이동:
  - BaseStrategyParams          (기본 파라미터 클래스)
  - PendingOrder                (예약 주문 정보)
  - PendingOrderConflictError   (충돌 예외)
  - _compute_bands()            (밴드 계산)
  - _execute_buy_order()        (매수 체결)
  - _execute_sell_order()       (매도 체결)
  - _detect_buy_signal()        (상향돌파 감지)
  - _detect_sell_signal()       (하향돌파 감지)
  - _record_equity()            (에쿼티 기록)
  - _check_pending_conflict()   (pending 충돌 검사)
  - _calculate_recent_buy_count()  (최근 매수 횟수)
  - _validate_buffer_strategy_inputs()  (입력 검증)

analysis.py에 추가:
  - calculate_atr()             (ATR 계산, ATR 관련 전략들이 공유)
```

### 사용하지 않는 전략에서는 import 안 함

```python
# buy_and_hold.py → 밴드/시그널 관련 헬퍼 불필요
from qbt.backtest.helpers import BaseStrategyParams

# buffer_zone.py → 기존 헬퍼 전부 사용
from qbt.backtest.helpers import (
    BaseStrategyParams, PendingOrder, _compute_bands,
    _execute_buy_order, _execute_sell_order, ...
)

# buffer_trailing.py → 기존 헬퍼 + ATR 유틸
from qbt.backtest.helpers import (...)
from qbt.backtest.analysis import calculate_atr
```

---

## 7. 마이그레이션 단계

### Phase 1: 구조 준비

- `strategies/` 폴더 생성
- `helpers.py` 생성 (strategy.py에서 공통 함수 분리)
- `analysis.py`에 `calculate_atr()` 추가

### Phase 2: 기존 전략 분리

- `strategy.py`의 `run_buy_and_hold()` → `strategies/buy_and_hold.py`
- `strategy.py`의 `run_buffer_strategy()` → `strategies/buffer_zone.py`
- `strategy.py`의 `run_grid_search()` → `strategies/buffer_zone.py` 또는 별도 모듈
- `__init__.py` 업데이트 (하위 호환 유지)
- 결과 저장 경로를 `storage/results/strategies/` 하위로 변경

### Phase 3: 새 전략 추가

- `strategies/buffer_stoploss.py` 구현
- `strategies/buffer_trailing.py` 구현
- 각 전략 실행 스크립트 추가 또는 `run_single_backtest.py`에 전략 선택 옵션 추가

### Phase 4: 비교 대시보드

- `app_strategy_comparison.py` 구현
- `storage/results/strategies/` 하위 폴더 자동 스캔
- equity 오버레이 + 요약 테이블

---

## 8. 기존 코드와의 호환성

### __init__.py 하위 호환

분리 후에도 기존 import 경로가 동작하도록 `__init__.py`에서 re-export한다.

```python
# src/qbt/backtest/__init__.py
# 기존 import 경로 유지
from qbt.backtest.strategies.buffer_zone import run_buffer_strategy, BufferStrategyParams
from qbt.backtest.strategies.buy_and_hold import run_buy_and_hold, BuyAndHoldParams
```

### 기존 테스트

- `tests/test_strategy.py`의 import 경로를 업데이트하거나 __init__.py re-export로 유지
- 기존 테스트가 깨지지 않도록 보장

### 기존 결과 CSV

- `storage/results/single_backtest_*.csv`는 과도기에 유지
- 새 결과는 `storage/results/strategies/` 하위에 저장
- 이후 기존 CSV 제거 가능
