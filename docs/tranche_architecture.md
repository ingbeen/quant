# 분할 매수매도 아키텍처 설계

> 작성일: 2026-03-14
> 기반 문서: tranche_final_recommendation.md
> 목적: 방식 C(오케스트레이터 패턴) 선택 근거, 데이터 흐름, 미래 요구사항을 기록

---

## 1. 구현 방식 비교 및 방식 C 선택 근거

### 1.1 3가지 방식 비교

| 항목           | 방식 A (독립 러너 N회)                        | 방식 B (단일 루프 멀티 포지션)       | 방식 C (오케스트레이터)                               |
| -------------- | --------------------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| 핵심           | `run_buffer_strategy()` N번 호출 후 결과 합산 | 하나의 루프에서 N개 포지션 독립 추적 | 오케스트레이터 모듈이 N개 러너를 관리하고 결과를 조합 |
| 기존 코드 변경 | 없음                                          | `run_buffer_strategy()` 대폭 수정    | 없음                                                  |
| 트랜치 추적    | 사후 태깅 (tranche_id 수동 추가)              | 루프 내 상태 관리로 자연스러운 추적  | 오케스트레이터가 체계적으로 태깅                      |
| 리밸런싱 확장  | 어려움 (기간 분할 재실행 필요)                | 가능하나 복잡도 높음                 | 자연스러운 확장 지점                                  |
| 테스트 용이성  | 높음 (기존 테스트 유지)                       | 낮음 (새 상태머신 검증 필요)         | 높음 (기존 + 오케스트레이터 단위 테스트)              |
| 시각화 데이터  | 사후 가공 필요                                | 자연스러운 산출                      | 체계적 산출                                           |

### 1.2 방식 C를 선택한 이유

**이유 1 — 기존 코드 무변경 원칙:**

`run_buffer_strategy()`는 182회 백테스트(§17~18)와 교차 자산 검증(§15)으로 검증된 핵심 함수이다. 이 함수를 수정하면 기존 테스트와 검증 결과의 신뢰성이 훼손된다. 방식 C는 기존 함수를 블랙박스로 호출하므로 검증 결과가 그대로 유지된다.

**이유 2 — 미래 리밸런싱 확장:**

추후 트랜치 간 또는 전략 간 리밸런싱을 구현할 예정이다. 오케스트레이터가 존재하면 리밸런싱 로직을 오케스트레이터 레벨에 추가하기만 하면 된다. 방식 A는 리밸런싱 시점에 전략을 중단/재시작해야 하므로 구조적으로 어색하다.

**이유 3 — 시각화 데이터의 체계적 산출:**

오케스트레이터가 결과를 조합하는 과정에서 시각화에 필요한 크로스 트랜치 데이터(평단, 동시 보유 수 등)를 자연스럽게 계산할 수 있다. 방식 A에서는 이를 별도 후처리 스크립트로 구현해야 한다.

**이유 4 — YAGNI와 확장성의 균형:**

방식 C는 방식 A보다 약간 복잡하지만, 새로운 모듈 1개(`split_strategy.py`)와 타입 추가만으로 구현된다. `run_buffer_strategy()` 수정이 없으므로 방식 B보다 훨씬 단순하다. 미래 요구사항을 고려하면 적절한 수준의 추상화이다.

---

## 2. 미래 요구사항 (현재 계획서 범위 밖)

현재 구현에서는 아래 기능을 **포함하지 않지만**, 아키텍처가 자연스럽게 확장 가능하도록 설계한다.

### 2.1 리밸런싱

- 특정 날짜에 트랜치 간 자본 재분배
- 트랜치 간 뿐 아니라 전략 간(버퍼존 vs Buy & Hold) 리밸런싱
- 오케스트레이터에 `rebalance_schedule` 파라미터 추가로 확장 예정

### 2.2 시각화 대시보드

별도 계획서로 작성 예정. 예상 기능:

- 합산 에쿼티 곡선 + 트랜치별 에쿼티 오버레이
- 거래 마커에 `tranche_id` 표시 (예: "ma250-Buy#3 $102.5")
- 동시 보유 트랜치 수 시계열
- 트랜치별 보유 중일 때 평단(가중 평균 진입가)
- 트랜치별 성과 비교 테이블

---

## 3. 데이터 흐름

### 3.1 입력

```
SplitStrategyConfig (split_strategy.py에서 정의)
├── strategy_name: str                          # "split_buffer_zone_qqq" 등
├── display_name: str                           # "분할 버퍼존 (QQQ)"
├── base_config: BufferZoneConfig               # 기존 자산 설정 (데이터 경로 등)
├── total_capital: float                        # 총 자본금
├── tranches: tuple[SplitTrancheConfig, ...]    # 트랜치별 설정
│     SplitTrancheConfig:
│     ├── tranche_id: str                       # "ma250", "ma200", "ma150"
│     ├── weight: float                         # 0.33, 0.34 등
│     └── ma_window: int                        # 250, 200, 150
└── result_dir: Path                            # 결과 저장 디렉토리
```

`SplitTrancheConfig`에서 `ma_window`만 트랜치별로 다르고, 나머지 파라미터(buy_buffer, sell_buffer, hold_days)는 `base_config`에서 가져온다. 이는 tranche_final_recommendation.md의 "ma_window만 변경" 원칙을 코드로 강제한다.

### 3.2 처리 흐름

```
run_split_backtest(config: SplitStrategyConfig)
│
├── 1. 데이터 로딩 (1회만)
│     signal_df = load_stock_data(base_config.signal_data_path)
│     trade_df = load_stock_data(base_config.trade_data_path)
│     (overlap 처리)
│
├── 2. 트랜치별 독립 실행 (N회)
│     for tranche in config.tranches:
│       ├── capital = total_capital × tranche.weight
│       ├── params = BufferStrategyParams(
│       │     initial_capital=capital,
│       │     ma_window=tranche.ma_window,
│       │     buy/sell/hold = base_config의 확정값
│       │   )
│       ├── signal_df에 해당 MA 계산 (add_single_moving_average)
│       ├── trades_df, equity_df, summary = run_buffer_strategy(...)
│       └── 결과에 tranche_id 태깅
│
├── 3. 결과 조합
│     ├── combined_trades_df: 전체 거래 (tranche_id + tranche_seq 컬럼 추가)
│     ├── combined_equity_df: 날짜 기준 merge → 합산 equity
│     │     + active_tranches (보유 중인 트랜치 수)
│     │     + avg_entry_price (보유 중인 트랜치의 가중 평균 진입가)
│     └── combined_summary: 합산 에쿼티로 calculate_summary() 호출
│
└── 4. SplitStrategyResult 반환
```

### 3.3 출력

```
SplitStrategyResult (dataclass)
├── strategy_name: str                    # "split_buffer_zone_qqq"
├── display_name: str                     # "분할 버퍼존 (QQQ)"
├── combined_equity_df: pd.DataFrame      # 합산 에쿼티 (시각화 메인)
│     Date | equity | active_tranches | avg_entry_price
├── combined_trades_df: pd.DataFrame      # 전체 거래 (tranche_id 포함)
│     tranche_id | tranche_seq | entry_date | exit_date | entry_price | ...
├── combined_summary: SummaryDict         # 분할 레벨 지표
├── per_tranche: list[SplitTrancheResult] # 트랜치별 결과
│     SplitTrancheResult:
│     ├── tranche_id: str
│     ├── config: SplitTrancheConfig
│     ├── trades_df: pd.DataFrame         # 해당 트랜치의 거래
│     ├── equity_df: pd.DataFrame         # 해당 트랜치의 에쿼티
│     └── summary: BufferStrategyResultDict
├── config: SplitStrategyConfig           # 원본 설정 (재현성)
└── params_json: dict[str, Any]           # JSON 저장용
```

---

## 4. 시각화에서 활용할 데이터 상세

현재 계획서에서 시각화를 구현하지는 않지만, 시각화에 필요한 데이터를 결과에 포함해야 한다.

### 4.1 combined_equity_df 컬럼

| 컬럼                | 타입          | 설명                                                         | 시각화 용도       |
| ------------------- | ------------- | ------------------------------------------------------------ | ----------------- |
| `Date`              | date          | 날짜                                                         | X축               |
| `equity`            | float         | 합산 에쿼티 (전 트랜치 equity 합)                            | 메인 에쿼티 곡선  |
| `active_tranches`   | int           | 현재 포지션 보유 중인 트랜치 수 (0~3)                        | 하단 서브차트     |
| `avg_entry_price`   | float or None | 보유 중인 트랜치의 가중 평균 진입가. 보유 트랜치 없으면 None | 차트 오버레이     |
| `ma250_equity`      | float         | ma250 트랜치의 개별 에쿼티                                   | 트랜치별 오버레이 |
| `ma200_equity`      | float         | ma200 트랜치의 개별 에쿼티                                   | 트랜치별 오버레이 |
| `ma150_equity`      | float         | ma150 트랜치의 개별 에쿼티                                   | 트랜치별 오버레이 |
| `ma250_position`    | int           | ma250 트랜치의 포지션 (0 or N)                               | 보유 상태 표시    |
| `ma200_position`    | int           | ma200 트랜치의 포지션 (0 or N)                               | 보유 상태 표시    |
| `ma150_position`    | int           | ma150 트랜치의 포지션 (0 or N)                               | 보유 상태 표시    |

### 4.2 combined_trades_df 컬럼

기존 TradeRecord의 모든 컬럼 + 추가 컬럼:

| 추가 컬럼     | 타입 | 설명                                           | 시각화 용도              |
| ------------- | ---- | ---------------------------------------------- | ------------------------ |
| `tranche_id`  | str  | 트랜치 식별자 ("ma250", "ma200", "ma150")      | 마커 색상 구분           |
| `tranche_seq` | int  | 해당 트랜치 내 거래 순번 (1-based)             | "ma250-Buy#3" 형식 마커  |
| `ma_window`   | int  | 해당 트랜치의 MA 기간                          | 거래 상세 표시           |

### 4.3 summary.json 구조 (저장용)

```json
{
  "display_name": "분할 버퍼존 (QQQ)",
  "split_summary": {
    "initial_capital": 10000000,
    "final_capital": "...",
    "total_return_pct": "...",
    "cagr": "...",
    "mdd": "...",
    "calmar": "...",
    "total_trades": "...",
    "active_open_positions": 2
  },
  "tranches": [
    {
      "tranche_id": "ma250",
      "ma_window": 250,
      "weight": 0.33,
      "initial_capital": 3300000,
      "summary": { "cagr": "...", "mdd": "...", "..." : "..." },
      "open_position": { "..." : "..." }
    },
    "..."
  ],
  "split_config": {
    "total_capital": 10000000,
    "buy_buffer_zone_pct": 0.03,
    "sell_buffer_zone_pct": 0.05,
    "hold_days": 3,
    "ma_type": "ema"
  }
}
```

---

## 5. 모듈 배치 및 기존 코드 영향

### 5.1 신규 파일

| 파일                                          | 목적                                                                                                     |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `src/qbt/backtest/split_strategy.py`          | 오케스트레이터 모듈 (SplitTrancheConfig, SplitStrategyConfig, SplitStrategyResult, run_split_backtest) |
| `tests/test_split_strategy.py`                | 분할 매수매도 모듈 테스트                                                                                |
| `scripts/backtest/run_split_backtest.py`      | 분할 매수매도 백테스트 실행 스크립트                                                                     |

### 5.2 수정 파일

| 파일                            | 변경 내용                                  |
| ------------------------------- | ------------------------------------------ |
| `src/qbt/common_constants.py`   | 분할 전략 결과 디렉토리 경로 추가          |
| `src/qbt/backtest/constants.py` | 분할 매수매도 트랜치 MA 상수 추가          |

### 5.3 변경하지 않는 파일 (절대 규칙)

| 파일                     | 이유                                                     |
| ------------------------ | -------------------------------------------------------- |
| `buffer_zone_helpers.py` | 182회 백테스트 검증 완료. `run_buffer_strategy()` 무변경 |
| `buffer_zone.py`         | 기존 config-driven 팩토리 유지                           |
| `buy_and_hold.py`        | 무관                                                     |
| `analysis.py`            | `calculate_summary()` 재사용만 함                        |
| `run_single_backtest.py` | 기존 단일 백테스트 스크립트 유지                         |

---

## 6. avg_entry_price (평단) 계산 로직

combined_equity_df의 `avg_entry_price` 컬럼은 다음과 같이 계산한다:

```
각 날짜에 대해:
  보유 중인 트랜치를 식별 (position > 0인 트랜치)
  보유 트랜치가 0개: avg_entry_price = None
  보유 트랜치가 1개 이상:
    avg_entry_price = sum(tranche.entry_price × tranche.shares) / sum(tranche.shares)
```

이 계산은 오케스트레이터의 결과 조합 단계(§3.2의 3단계)에서 수행한다. 각 트랜치의 equity_df에서 position과 entry 정보를 추출하여 날짜별로 합산한다.

---

## 7. 리밸런싱 확장 경로 (미래 참고용)

현재 구현에서는 리밸런싱을 포함하지 않지만, 방식 C의 구조에서 자연스럽게 확장 가능:

```
현재: 리밸런싱 없는 독립 실행
  run_split_backtest()가 각 트랜치를 전체 기간에 대해 독립 실행 후 결과 조합

미래: 리밸런싱 추가
  SplitStrategyConfig에 rebalance_schedule 추가
  → 리밸런싱 시점에서 기간을 분할
  → 각 구간별로 트랜치를 독립 실행
  → 구간 연결부에서 자본 재분배
  → 전체 기간 결과 연결
```

이 확장에서도 `run_buffer_strategy()`는 수정하지 않는다. 오케스트레이터가 기간 분할과 자본 재분배를 담당한다.
