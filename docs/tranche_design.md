# 분할 매수매도 설계 문서

> 작성일: 2026-03-14
> 최종 업데이트: 2026-03-15 (구현 완료 후 소스코드 기준 최신화)
> 기반 분석: overfitting_analysis_report.md (§17~18)
> 목적: 3분할 매수매도의 파라미터 선택 근거, 아키텍처 설계, 데이터 흐름을 통합 기록
> 설계 근거 소스코드: `src/qbt/backtest/split_strategy.py`

---

## 1. 파라미터 결정

### 1.1 최종 권고: ma_window만 변경하는 3분할

| 파라미터      | 트랜치 1 | 트랜치 2 (기준) | 트랜치 3 |
| ------------- | -------- | --------------- | -------- |
| **ma_window** | **250**  | **200**         | **150**  |
| buy_buffer    | 0.03     | 0.03            | 0.03     |
| sell_buffer   | 0.05     | 0.05            | 0.05     |
| hold_days     | 3        | 3               | 3        |
| 가중치        | 33%      | 34%             | 33%      |

**변경하는 파라미터: ma_window 1개뿐. 나머지 3개(buy, sell, hold)는 전 트랜치 동일.**

### 1.2 왜 ma_window만 변경하는가

**검증된 조합만 사용한다:**

182회 고원 분석(§17~18)은 전부 **"1개 파라미터만 변경, 나머지 고정"**으로 수행되었다.

- MA=150의 Calmar 0.27 → buy=3%, sell=5%, hold=3이 고정된 상태에서 측정
- MA=200의 Calmar 0.30 → buy=3%, sell=5%, hold=3이 고정된 상태에서 측정
- MA=250의 Calmar 0.21 → buy=3%, sell=5%, hold=3이 고정된 상태에서 측정

위 3개 조합은 모두 §18.5에서 **직접 백테스트된 결과**이다. 4개 파라미터를 동시에 변경한 조합의 Calmar는 한 번도 측정한 적이 없으므로, 검증되지 않은 조합을 사용하는 것은 과최적화 방향으로의 한 걸음이다.

**분산 기여도가 가장 높은 축이 ma_window이다:**

분할 매수매도의 핵심 가치는 **"트랜치 간 시간적 분산"**이다. ma_window 변경은 추세 판단의 기준 자체를 바꾼다:

```
MA=150: 2024-01-15에 돌파 감지 → 2024-01-16 매수
MA=200: 2024-02-03에 돌파 감지 → 2024-02-04 매수  (19일 후)
MA=250: 2024-02-20에 돌파 감지 → 2024-02-21 매수  (36일 후)
```

반면 buy_buffer 변경은 같은 MA 기준으로 임계값만 이동하여 수일 차이에 불과하다. ma_window 하나만으로 분산의 대부분을 달성할 수 있으므로, 나머지 파라미터까지 변경할 필요가 없다.

**설명이 간단하다:**

"MA만 고원 내에서 3등분했고, 나머지는 검증된 확정값 그대로." 이 한 문장으로 전체 설계를 설명할 수 있다.

### 1.3 왜 3분할인가 (2분할이 아닌 이유)

| 기준            | 2분할 (MA 150/250)                       | 3분할 (MA 150/200/250)                                  |
| --------------- | ---------------------------------------- | ------------------------------------------------------- |
| **기준 트랜치** | 없음                                     | **있음 (MA=200 = 검증 완료 확정값)**                    |
| 비교 가능성     | 단일 파라미터 대비 분할의 효과 비교 불가 | 트랜치 2가 기존 단일 전략과 동일 시그널 → 비교 가능(*) |
| 시간적 분산     | MA 양극단(100일 차이)                    | 3단계 그라데이션(50일 간격) → 더 균일한 분산            |
| 복잡도          | 2개 관리                                 | 3개 관리 (차이 미미)                                    |

3분할의 핵심 장점은 **트랜치 2(MA=200)가 기존 단일 전략과 동일한 시그널**을 발생시킨다는 것이다. 이 덕분에:

- "분할이 단일 대비 MDD를 줄이는가?"를 합산 에쿼티와 단일 전략 결과를 비교하여 직접 측정 가능
- 트랜치 2의 매매 타이밍이 §17~18의 기존 백테스트 결과와 일치하는지 검증 가능 (내부 일관성 확인)
- 만약 분할의 효과가 미미하면, 기준 트랜치로 돌아가면 됨 (퇴로 확보)

(*) 공유 자본 모델 구현 시 주의: 트랜치 2는 단일 전략과 동일한 MA-200 시그널을 생성하지만, 자본 배분이 다르므로(공유 자본의 1/3 vs 전체 자본) 재무적 수익률은 상이하다. 비교 시 매매 타이밍(동일)과 수익률(상이)을 구분해야 한다.

### 1.4 각 트랜치의 근거

**트랜치 1 (MA=250) — "큰 추세만 잡고 길게 보유"**

| 항목        | 내용                                                                                  |
| ----------- | ------------------------------------------------------------------------------------- |
| 검증 데이터 | §18.5 ma_window 고원 분석에서 직접 측정                                               |
| QQQ Calmar  | 0.21 (고원 내, 바닥 0.17보다 높음)                                                    |
| SPY Calmar  | 0.42 (고원 내, MA=200의 0.43과 거의 동일)                                             |
| 거래 수     | QQQ 12회, SPY 10회 (MA=200보다 2~1회 적음)                                            |
| 특성        | 250일 MA는 약 12.5개월의 장기 추세만 감지. 단기 변동에 반응하지 않아 가짜 돌파가 적음 |
| 분산 기여   | MA=200보다 약 2~4주 늦게 진입 → 시간적 분산 확보                                      |

**트랜치 2 (MA=200) — "기준, 검증 완료"**

| 항목        | 내용                                                                       |
| ----------- | -------------------------------------------------------------------------- |
| 검증 데이터 | 182회 백테스트(§17~18) + 교차 자산 검증(§15) + B&H 비교(§19)               |
| QQQ Calmar  | 0.30 (고원 내 최고값)                                                      |
| SPY Calmar  | 0.43 (전체 최고)                                                           |
| 거래 수     | QQQ 14회, SPY 11회                                                         |
| 특성        | 가장 널리 사용되는 장기 추세 필터. 자기실현적 예언 효과. 경제적 논거 A등급 |
| 분산 기여   | 앵커 역할. 다른 트랜치의 시간적 편차를 측정하는 기준점                     |

**트랜치 3 (MA=150) — "중기 추세도 포착"**

| 항목        | 내용                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------- |
| 검증 데이터 | §18.5 ma_window 고원 분석에서 직접 측정                                                  |
| QQQ Calmar  | 0.27 (고원 내, 바닥 0.17보다 높음)                                                       |
| SPY Calmar  | 0.37 (고원 내)                                                                           |
| 거래 수     | QQQ 15회, SPY 12회 (MA=200보다 1회 많음)                                                 |
| 특성        | 150일 MA는 약 7.5개월의 중기 추세도 감지. MA=200보다 빠르게 반응하여 추세 초기 진입 가능 |
| 분산 기여   | MA=200보다 약 2~4주 빨리 진입 → 시간적 분산 확보                                         |

### 1.5 가중치 33:34:33의 근거

**균등 배분의 이유:**

- 3개 트랜치 모두 고원 안에 있으므로, 어느 쪽에도 우위를 부여할 정량적 근거가 없다
- 비대칭 가중치를 설정하려면 "왜 이 비율인가?"에 답해야 하는데, 그 답은 데이터에서 나올 수밖에 없다 → 과최적화 방향
- DeMiguel et al.(2009)의 "1/N 포트폴리오" 연구: 최적화된 가중치보다 균등 배분이 out-of-sample에서 더 나은 경우가 많음
- 트랜치 2(기준)에 1%p 높은 비중은 실질적 차이가 아니라 홀수 분배의 편의

**가중치를 바꾸지 않는 이유:**

성과 데이터가 축적되면 "잘 되는 트랜치에 비중을 늘리자"는 유혹이 생긴다. 이것은 "결과를 보고 바꾸면 과최적화"라는 원칙(§18.1)에 위배된다. 가중치를 바꾸려면 사전에 정한 규칙이 있어야 하며, 그 규칙 자체도 새로운 파라미터가 된다. 따라서 **가중치 33:34:33을 고정하고 바꾸지 않는다.**

### 1.6 이 설계가 과최적화가 아닌 이유

| 검증 항목                                                   | 상태                                                  |
| ----------------------------------------------------------- | ----------------------------------------------------- |
| 3개 트랜치 모두 고원 분석에서 **직접 백테스트된 조합**인가? | ✅ §18.5에서 MA=150/200/250 모두 측정됨               |
| 검증되지 않은 파라미터 조합이 포함되어 있는가?              | ✅ 없음. buy/sell/hold는 전 트랜치 동일(확정값)       |
| 가중치가 데이터에서 도출되었는가?                           | ✅ 아님. 균등 배분(사전 결정)                         |
| 결과를 보고 파라미터를 바꿀 여지가 있는가?                  | ✅ 없음. 고원 내 좌단/중앙/우단의 기계적 선택         |
| 새로운 파라미터가 추가되었는가?                             | ✅ 없음. MA 값과 가중치 모두 고원에서 기계적으로 결정 |

핵심: 이 설계의 모든 결정은 **고원 분석 결과에서 기계적으로 도출**된다. "MA 고원이 150~300이므로 좌단/중앙/우단을 선택"하는 것은 주관적 판단이 아니라 고원의 존재로부터 자동으로 따라오는 결론이다.

---

## 2. 구현 방식 선택

### 2.1 3가지 방식 비교

| 항목           | 방식 A (독립 러너 N회)                        | 방식 B (단일 루프 멀티 포지션)       | 방식 C (오케스트레이터)                                         |
| -------------- | --------------------------------------------- | ------------------------------------ | --------------------------------------------------------------- |
| 핵심           | `run_buffer_strategy()` N번 호출 후 결과 합산 | 하나의 루프에서 N개 포지션 독립 추적 | 오케스트레이터 모듈이 N개 트랜치를 공유 자본으로 통합 관리      |
| 기존 코드 변경 | 없음                                          | `run_buffer_strategy()` 대폭 수정    | 없음 (헬퍼 함수만 import)                                       |
| 트랜치 추적    | 사후 태깅 (tranche_id 수동 추가)              | 루프 내 상태 관리로 자연스러운 추적  | 오케스트레이터가 체계적으로 태깅                                |
| 자본 모델      | 트랜치별 독립 자본                            | 공유 자본 가능                       | 공유 자본 (shared_cash 동적 배분)                               |
| 리밸런싱 확장  | 어려움 (기간 분할 재실행 필요)                | 가능하나 복잡도 높음                 | 자연스러운 확장 지점                                            |
| 테스트 용이성  | 높음 (기존 테스트 유지)                       | 낮음 (새 상태머신 검증 필요)         | 높음 (기존 + 오케스트레이터 단위 테스트)                        |
| 시각화 데이터  | 사후 가공 필요                                | 자연스러운 산출                      | 체계적 산출                                                     |

### 2.2 방식 C를 선택한 이유

**이유 1 — 기존 코드 무변경 원칙:**
`run_buffer_strategy()`는 182회 백테스트와 교차 자산 검증으로 검증된 핵심 함수이다. 방식 C는 기존 함수를 수정하지 않으며, `buffer_zone_helpers.py`의 헬퍼 함수(`_compute_bands`, `_detect_buy_signal`, `_detect_sell_signal`)를 import하여 재사용한다.

**이유 2 — 공유 자본 모델 지원:**
독립 자본 방식(방식 A)은 매수 시점에 따른 자본 배분이 불가능하다. 공유 자본 모델에서는 매수 체결 시점의 잔여 현금을 미보유 트랜치 수로 나누어 동적 배분이 가능하다. 이를 구현하려면 날짜별 통합 루프가 필수이며, 이것이 오케스트레이터 패턴과 자연스럽게 맞는다.

**이유 3 — 미래 리밸런싱 확장:**
오케스트레이터가 존재하면 리밸런싱 로직을 오케스트레이터 레벨에 추가하기만 하면 된다.

**이유 4 — 시각화 데이터의 체계적 산출:**
오케스트레이터가 결과를 조합하는 과정에서 시각화에 필요한 크로스 트랜치 데이터(평단, 동시 보유 수 등)를 자연스럽게 계산할 수 있다.

### 2.3 설계 시점 대비 구현 변경사항

설계 시점에는 `run_buffer_strategy()`를 블랙박스로 호출하여 트랜치별 독립 실행 후 결과를 조합하는 방식을 계획했다. 구현 과정에서 **공유 자본 모델**의 필요성이 확인되어, 날짜별 통합 루프에서 트랜치별 시그널을 직접 판정하는 방식으로 변경되었다.

- 설계 시점: `run_buffer_strategy()` N회 호출 → 결과 합산
- 구현 결과: 날짜별 통합 루프 + `buffer_zone_helpers.py` 헬퍼 함수 import
- `run_buffer_strategy()` 자체는 수정하지 않음 (무변경 원칙 준수)
- `buffer_zone_helpers.py`의 private 헬퍼 함수를 `pyright: ignore[reportPrivateUsage]`로 import

---

## 3. 공유 자본 모델

### 3.1 매수 자본 배분 규칙

```
매수 체결 시점:
  unowned = 현재 미보유 트랜치 수 (자기 포함)
  buy_capital = shared_cash ÷ unowned
  shares = int(buy_capital / buy_price)   # 정수 주식만 매수
  shared_cash -= shares × buy_price
```

동일 날짜에 복수 트랜치가 매수 체결되는 경우, 처리 순서(ma250 → ma200 → ma150)에 따라 첫 번째 트랜치가 가장 많은 자본을 배분받고, 이후 트랜치는 줄어든 shared_cash에서 배분받는다.

예시 (3개 트랜치 동시 매수, shared_cash = 10,000,000):
- ma250 체결: buy_capital = 10,000,000 ÷ 3 = 3,333,333
- ma200 체결: buy_capital = (10,000,000 - 3,333,333) ÷ 2 = 3,333,333
- ma150 체결: buy_capital = (10,000,000 - 6,666,666) ÷ 1 = 3,333,334

### 3.2 매도 대금 복귀

```
매도 체결 시점:
  sell_price = trade_open × (1 - SLIPPAGE_RATE)
  sell_amount = position × sell_price
  shared_cash += sell_amount
  position = 0
```

매도 대금은 즉시 shared_cash에 복귀하므로, 동일 날짜에 다른 트랜치의 매수에 사용될 수 있다.

### 3.3 독립 자본 대비 차이

| 항목         | 독립 자본 (설계 시점)                          | 공유 자본 (구현 결과)                                      |
| ------------ | ---------------------------------------------- | ---------------------------------------------------------- |
| 자본 배분    | total_capital × weight (고정)                  | shared_cash ÷ 미보유 트랜치 수 (동적)                     |
| 매도 대금    | 해당 트랜치에 귀속                             | shared_cash에 복귀 (전 트랜치 공유)                        |
| 핵심 로직    | `run_buffer_strategy()` N회 호출               | 날짜별 통합 루프에서 트랜치별 시그널 직접 판정             |

변경 이유: 독립 자본 모델에서는 매수 시점에 따른 동적 자본 배분이 불가능하다. 공유 자본 모델은 먼저 진입한 트랜치의 매도 대금을 다른 트랜치의 매수에 활용할 수 있어, 자본 효율이 높다.

파라미터 영향: 없음. 공유 자본 모델은 자본 배분 방식만 변경하며, 핵심 결정(MA 250/200/150, buy 3%, sell 5%, hold 3, 가중치 33:34:33)은 그대로 유지된다.

---

## 4. 데이터 흐름

### 4.1 입력

```
SplitStrategyConfig (split_strategy.py에서 정의)
├── strategy_name: str                          # "split_buffer_zone_qqq" 등
├── display_name: str                           # "분할 버퍼존 (QQQ)"
├── base_config: BufferZoneConfig               # 기존 자산 설정 (데이터 경로, 4P 파라미터)
├── total_capital: float                        # 총 자본금
├── tranches: tuple[SplitTrancheConfig, ...]    # 트랜치별 설정
│     SplitTrancheConfig:
│     ├── tranche_id: str                       # "ma250", "ma200", "ma150"
│     ├── weight: float                         # 0.33, 0.34 등
│     └── ma_window: int                        # 250, 200, 150
└── result_dir: Path                            # 결과 저장 디렉토리
```

`SplitTrancheConfig`에서 `ma_window`만 트랜치별로 다르고, 나머지 파라미터(buy_buffer, sell_buffer, hold_days)는 `base_config`에서 가져온다. 이는 §1.1의 "ma_window만 변경" 원칙을 코드로 강제한다.

### 4.2 처리 흐름

```
run_split_backtest(config: SplitStrategyConfig)
│
├── 1. 입력 검증
│     중복된 tranche_id 존재 시 ValueError
│
├── 2. 데이터 로딩 (1회만)
│     signal_df = load_stock_data(base_config.signal_data_path)
│     trade_df = load_stock_data(base_config.trade_data_path)
│     (signal != trade인 경우 overlap 처리)
│
├── 3. 모든 트랜치 MA 사전 계산
│     for tranche in config.tranches:
│       signal_df = add_single_moving_average(signal_df, tranche.ma_window)
│
├── 4. MA 유효 시작점 결정
│     가장 큰 MA 윈도우(250) 기준으로 NaN 행 제거
│
├── 5. 트랜치별 상태 초기화 (_TrancheState)
│     각 트랜치: position=0, pending_order=None, hold_state=None
│     shared_cash = total_capital
│
├── 6. 날짜별 통합 루프 (i = 1 ~ len(signal_df)-1)
│     │
│     ├── 6-1. pending order 체결 (ma250 → ma200 → ma150 순서)
│     │     매수 체결:
│     │       unowned = 미보유 트랜치 수
│     │       buy_capital = shared_cash ÷ unowned
│     │       shares = int(buy_capital / buy_price)
│     │       shared_cash -= shares × buy_price
│     │     매도 체결:
│     │       sell_amount = position × sell_price
│     │       shared_cash += sell_amount
│     │       거래 기록(TradeRecord) 추가
│     │
│     ├── 6-2. 트랜치별 밴드 계산 + 에쿼티 기록
│     │     에쿼티 = position × trade_close (주식 평가액만, 현금 제외)
│     │
│     └── 6-3. 트랜치별 시그널 판정
│           매수: _detect_buy_signal() + hold_days 상태머신
│           매도: _detect_sell_signal()
│
├── 7. 결과 조합
│     ├── 트랜치별: SplitTrancheResult 생성 (trades_df, equity_df, summary)
│     ├── 미청산 포지션: position > 0인 트랜치에 open_position 기록
│     ├── combined_trades_df: _combine_trades() (tranche_id + tranche_seq 태깅)
│     └── combined_summary: _calculate_combined_summary()
│
└── 8. 합산 에쿼티 구성 (_build_combined_equity)
      ├── 트랜치별 equity merge (outer join on Date)
      ├── 현금 추적: 거래 이벤트에서 날짜별 현금 역산
      ├── equity = cash + sum(tranche_stock_values)
      ├── active_tranches 계산 (position > 0인 트랜치 수)
      └── avg_entry_price 계산 (_get_latest_entry_price)
```

### 4.3 출력

```
SplitStrategyResult (dataclass)
├── strategy_name: str                   # "split_buffer_zone_qqq"
├── display_name: str                    # "분할 버퍼존 (QQQ)"
├── combined_equity_df: pd.DataFrame     # 합산 에쿼티 (시각화 메인)
│     Date | equity | active_tranches | avg_entry_price
│     | ma250_equity | ma250_position | ma200_equity | ma200_position | ...
├── combined_trades_df: pd.DataFrame     # 전체 거래 (tranche_id 포함)
│     tranche_id | tranche_seq | entry_date | exit_date | entry_price | ...
├── combined_summary: SummaryDict        # 분할 레벨 지표
├── per_tranche: list[SplitTrancheResult] # 트랜치별 결과
│     SplitTrancheResult:
│     ├── tranche_id: str
│     ├── config: SplitTrancheConfig
│     ├── trades_df: pd.DataFrame        # 해당 트랜치의 거래
│     ├── equity_df: pd.DataFrame        # 해당 트랜치의 에쿼티 (주식 평가액만)
│     └── summary: BufferStrategyResultDict
├── config: SplitStrategyConfig          # 원본 설정 (재현성)
├── params_json: dict[str, Any]          # JSON 저장용
└── signal_df: pd.DataFrame              # 시그널 데이터 (OHLCV + 3개 MA, 시각화용)
```

---

## 5. 시각화 데이터 상세

### 5.1 combined_equity_df 컬럼

| 컬럼                | 타입          | 설명                                                                   | 시각화 용도       |
| ------------------- | ------------- | ---------------------------------------------------------------------- | ----------------- |
| `Date`              | date          | 날짜                                                                   | X축               |
| `equity`            | float         | 합산 에쿼티 (shared_cash + 전 트랜치 주식 평가액)                     | 메인 에쿼티 곡선  |
| `active_tranches`   | int           | 현재 포지션 보유 중인 트랜치 수 (0~3)                                  | 하단 서브차트     |
| `avg_entry_price`   | float or None | 보유 중인 트랜치의 가중 평균 진입가. 보유 트랜치 없으면 None           | 차트 오버레이     |
| `ma250_equity`      | float         | ma250 트랜치의 주식 평가액 (position × close)                          | 트랜치별 오버레이 |
| `ma200_equity`      | float         | ma200 트랜치의 주식 평가액                                             | 트랜치별 오버레이 |
| `ma150_equity`      | float         | ma150 트랜치의 주식 평가액                                             | 트랜치별 오버레이 |
| `ma250_position`    | int           | ma250 트랜치의 포지션 보유 수량 (0 or N)                               | 보유 상태 표시    |
| `ma200_position`    | int           | ma200 트랜치의 포지션 보유 수량                                        | 보유 상태 표시    |
| `ma150_position`    | int           | ma150 트랜치의 포지션 보유 수량                                        | 보유 상태 표시    |

주의: 트랜치별 에쿼티(`{tid}_equity`)는 주식 평가액만 포함하며 현금을 포함하지 않는다. 포지션 청산 시 0이 되므로, 트랜치 단독의 MDD는 -100%가 된다. 합산 에쿼티(`equity`)만 의미 있는 MDD를 제공한다.

### 5.2 combined_trades_df 컬럼

기존 TradeRecord의 모든 컬럼 + 추가 컬럼:

| 추가 컬럼     | 타입 | 설명                                           | 시각화 용도              |
| ------------- | ---- | ---------------------------------------------- | ------------------------ |
| `tranche_id`  | str  | 트랜치 식별자 ("ma250", "ma200", "ma150")      | 마커 색상 구분           |
| `tranche_seq` | int  | 해당 트랜치 내 거래 순번 (1-based)             | "ma250-Buy#3" 형식 마커  |
| `ma_window`   | int  | 해당 트랜치의 MA 기간                          | 거래 상세 표시           |

정렬: entry_date 오름차순 → tranche_id 오름차순

### 5.3 summary.json 구조 (저장용)

```json
{
  "display_name": "분할 버퍼존 (QQQ)",
  "split_summary": {
    "initial_capital": 10000000,
    "final_capital": 155219264,
    "total_return_pct": 1452.19,
    "cagr": 10.69,
    "mdd": -41.0,
    "calmar": 0.26,
    "total_trades": 43,
    "active_open_positions": 3
  },
  "tranches": [
    {
      "tranche_id": "ma250",
      "ma_window": 250,
      "weight": 0.33,
      "initial_capital": 3300000,
      "summary": {
        "final_capital": 51739440,
        "total_return_pct": 1467.86,
        "cagr": 10.73,
        "mdd": -100.0,
        "calmar": 0.11,
        "total_trades": 14,
        "win_rate": 71.43
      },
      "open_position": {
        "entry_date": "2025-05-16",
        "entry_price": 520.361629,
        "shares": 86628
      }
    }
  ],
  "split_config": {
    "total_capital": 10000000,
    "buy_buffer_zone_pct": 0.03,
    "sell_buffer_zone_pct": 0.05,
    "hold_days": 3,
    "ma_type": "ema",
    "tranches": [
      {
        "tranche_id": "ma250",
        "ma_window": 250,
        "weight": 0.33,
        "initial_capital": 3300000
      }
    ]
  }
}
```

### 5.4 시각화 대시보드

`scripts/backtest/app_split_backtest.py`로 구현 완료. 주요 기능:

- 합산 에쿼티 곡선 + 트랜치별 에쿼티 오버레이
- 캔들스틱 차트에 포커스 트랜치 선택 (MA + 밴드 + 매매 마커)
- 포지션 추적 (평균단가 / 보유수량 / active_tranches)
- 드로우다운 차트
- 트랜치별 색상 체계: ma250=파랑, ma200=주황, ma150=초록
- 거래 테이블 및 파라미터 표시

---

## 6. 모듈 배치 및 기존 코드 영향

### 6.1 신규 파일

| 파일                                          | 목적                                                                                                              |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `src/qbt/backtest/split_strategy.py`          | 오케스트레이터 모듈 (SplitTrancheConfig, SplitStrategyConfig, SplitStrategyResult, run_split_backtest 등)         |
| `tests/test_split_strategy.py`                | 분할 매수매도 모듈 테스트                                                                                         |
| `scripts/backtest/run_split_backtest.py`      | 분할 매수매도 백테스트 실행 스크립트                                                                              |
| `scripts/backtest/app_split_backtest.py`      | 분할 매수매도 시각화 대시보드 (Streamlit)                                                                        |

### 6.2 수정 파일

| 파일                            | 변경 내용                                  |
| ------------------------------- | ------------------------------------------ |
| `src/qbt/common_constants.py`   | 분할 전략 결과 디렉토리 경로 추가          |
| `src/qbt/backtest/constants.py` | 분할 매수매도 트랜치 MA/가중치/ID 상수 추가 |

### 6.3 변경하지 않는 파일

| 파일                     | 이유                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `buffer_zone_helpers.py` | 182회 백테스트 검증 완료. `run_buffer_strategy()` 무변경. private 헬퍼 함수는 수정 없이 import만 수행 (`pyright: ignore`) |
| `buffer_zone.py`         | 기존 config-driven 팩토리 유지                                                                                           |
| `buy_and_hold.py`        | 무관                                                                                                                     |
| `analysis.py`            | `calculate_summary()`, `add_single_moving_average()` 재사용만 함                                                        |
| `run_single_backtest.py` | 기존 단일 백테스트 스크립트 유지                                                                                         |

---

## 7. 상세 계산 로직

### 7.1 avg_entry_price (평단) 계산

combined_equity_df의 `avg_entry_price` 컬럼은 `_get_latest_entry_price()` 헬퍼 함수를 사용하여 계산한다:

```
각 날짜에 대해:
  보유 중인 트랜치를 식별 ({tid}_position > 0인 트랜치)
  보유 트랜치가 0개: avg_entry_price = None
  보유 트랜치가 1개 이상:
    각 트랜치의 entry_price를 _get_latest_entry_price()로 조회
    avg_entry_price = sum(entry_price × position) / sum(position)

_get_latest_entry_price(trades_df, equity_df, current_date, open_position):
  trades_df에서 entry_date <= current_date인 마지막 거래를 조회
  해당 거래의 exit_date > current_date이면 아직 보유 중 → entry_price 반환
  모든 거래가 청산 완료 && open_position 존재 → open_position의 entry_price 반환
  그 외 → None
```

이 계산은 오케스트레이터의 결과 조합 단계(§4.2의 8단계)에서 수행한다.

---

## 8. 실제 백테스트 결과 (1999-03-10 ~ 2026-03-12)

| 지표         | 단일 버퍼존 (QQQ) | 분할 버퍼존 (QQQ) | 단일 버퍼존 (TQQQ) | 분할 버퍼존 (TQQQ) |
| ------------ | :----------------:| :----------------:| :-----------------:| :-----------------:|
| CAGR         | 10.93%            | 10.69%            | 19.18%             | 18.73%             |
| MDD          | -36.49%           | -41.00%           | -89.30%            | -89.60%            |
| Calmar       | 0.30              | 0.26              | 0.21               | 0.21               |
| 총 거래 수   | 14                | 43                | 14                 | 43                  |

현재 데이터에서 분할 전략이 단일 전략 대비 MDD 개선 효과를 보이지 못하고 있다. 이는 MA-150/200/250의 시간적 분산이 27년 데이터의 14회 거래라는 적은 표본에서 제한적으로 나타나기 때문이다. 분할 전략의 가치는 미래 시장 환경 변화에 대한 강건성에 있으며, 현재 결과만으로 효과를 판단하기는 어렵다.

상세 비교 분석: `docs/strategy_results_comparison.md` 참고

---

## 9. 미래 확장 (참고용)

### 9.1 리밸런싱

현재 구현에서는 리밸런싱을 포함하지 않지만, 공유 자본 오케스트레이터 구조에서 자연스럽게 확장 가능:

```
현재: 리밸런싱 없는 공유 자본 운용
  run_split_backtest()가 날짜별 통합 루프에서 트랜치별 시그널로 매수/매도

미래: 리밸런싱 추가
  SplitStrategyConfig에 rebalance_schedule 추가
  → 리밸런싱 시점에서 전 트랜치 포지션 조정
  → 목표 비중으로 shared_cash 재배분
  → 기존 루프 로직은 그대로 유지
```

이 확장에서도 `run_buffer_strategy()`는 수정하지 않는다. 오케스트레이터가 리밸런싱과 자본 재배분을 담당한다.
