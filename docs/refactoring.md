`CLAUDE.md`들은 루트 포함 전부 읽고, 그 기준으로 `backtest` 중심 코드와 관련 테스트를 같이 봤습니다.
관련 pytest 일부도 돌려봤는데 눈에 띄는 실패는 없었습니다. 다만 테스트가 아직 못 잡는 구현상 불일치가 몇 군데 있습니다.

## 1) backtest를 중점으로 리팩토링하면 좋은 지점

### 1. WFO의 데이터 준비 경로를 하나로 묶는 것

가장 먼저 손댈 만합니다.

- 현재 `run_walkforward()`와 `scripts/backtest/run_walkforward.py::_run_stitched_equity()`가 각각 OOS 데이터를 자르고, MA를 계산하고, 유효 구간을 필터링합니다.
- 그런데 이 과정이 `단일 backtest / grid search / stitched equity`마다 조금씩 다릅니다.
- 특히 WFO는 “전체 히스토리에서 지표를 만든 뒤 OOS만 평가”해야 해석이 안정적인데, 지금은 OOS를 먼저 자른 다음 MA를 다시 계산하는 경로가 있습니다.

관련 위치:

- `src/qbt/backtest/walkforward.py:327-350`
- `scripts/backtest/run_walkforward.py:117-145`

추천 방향:

- `prepare_signal_trade_pair(...)` 또는 `prepare_backtest_input(...)` 같은 공용 헬퍼를 두고
  - 데이터 로딩
  - overlap 추출
  - 필요한 MA들 사전 계산
  - warmup/valid row 처리
  - 평가용 slice 생성
    을 한 군데서 처리하는 편이 좋습니다.

---

### 2. 성과지표 계산 로직, 특히 Calmar를 단일 함수로 통합

지금은 같은 개념이 여러 군데에 흩어져 있고, 구현도 서로 다릅니다.

관련 위치:

- `src/qbt/backtest/analysis.py:145-150`
- `src/qbt/backtest/engines/backtest_engine.py:192-199`
- `src/qbt/backtest/walkforward.py:183-194`
- `src/qbt/backtest/walkforward.py:405-412`

추천 방향:

- `analysis.py`나 별도 `metrics.py`로 `safe_calmar(cagr, mdd)`를 하나만 두고 전부 재사용

이건 단순 미관 문제가 아니라, 같은 전략을 다른 경로로 실행했을 때 지표가 달라질 수 있는 영역이라 우선순위가 높습니다.

---

### 3. portfolio preflight 로직을 facade 밖으로 빼는 것

`portfolio_engine.py`에서 다음 준비 단계가 두 번 반복됩니다.

- 자산별 데이터 로딩
- 공통 날짜 교집합 계산
- MA warmup 반영
- valid_start 계산

관련 위치:

- `src/qbt/backtest/engines/portfolio_engine.py:61-151`
- `src/qbt/backtest/engines/portfolio_engine.py:185-263`

추천 방향:

- `prepare_portfolio_data_bundle(config)` 같은 함수로 추출
- `compute_portfolio_effective_start_date()`와 `run_portfolio_backtest()`가 같은 준비 결과를 공유

이 부분은 버그보다는 유지보수 비용 절감 효과가 큽니다.

---

### 4. 스크립트 레벨의 실험 루프를 도메인 로직과 더 분리

`run_param_plateau_all.py`는 실험 자체는 단순한데, 데이터 준비/고정 파라미터/루프/실행이 한 파일에서 많이 섞여 있습니다.

관련 위치:

- `scripts/backtest/run_param_plateau_all.py:145-280`

추천 방향:

- “실험 정의”와 “실행”을 분리
- 파라미터 하나 바꿔가며 같은 실행을 반복하는 부분을 작은 helper로 추출

---

## 2) 버그, 논리적 오류, 문서/주석/코드 불일치

### 1. [중요] WFO OOS 평가가 OOS 구간만 잘라서 MA를 다시 계산함

이건 가장 중요한 항목입니다.

관련 위치:

- `src/qbt/backtest/walkforward.py:327-350`
- 문서 설명: `src/qbt/backtest/CLAUDE.md:80-85`

문제:

- `run_walkforward()`는 OOS 구간만 먼저 slice 한 뒤, 그 OOS 조각에 대해 `add_single_moving_average()`를 다시 적용합니다.
- 기본 MA 타입이 `ema`라서(`src/qbt/backtest/constants.py:33`) EMA 상태가 OOS 시작점에서 리셋됩니다.
- 즉, 실제 운용처럼 “과거 히스토리를 이어받은 EMA”가 아니라 “OOS 첫날부터 새로 시작한 EMA”가 됩니다.

영향:

- OOS 성과가 실제 운용과 다르게 측정될 수 있습니다.
- 문서상 “OOS 독립 평가”와 구현상 “OOS 내부 재초기화”가 미묘하게 어긋납니다.

---

### 2. [중요] stitched equity도 같은 warmup/EMA reset 문제를 반복함

관련 위치:

- `scripts/backtest/run_walkforward.py:117-145`

문제:

- stitched equity도 `first_oos_start ~ last_oos_end`만 먼저 잘라서, 그 구간에서 필요한 MA들을 다시 계산합니다.
- 따라서 stitched equity 역시 OOS 첫 지점 기준으로 EMA가 재시작합니다.

영향:

- 윈도우별 OOS 결과와 stitched 결과를 비교할 때, 둘 다 “전체 히스토리 기반”이 아니라는 점이 섞여 들어갑니다.
- stitched equity를 “연속 자본곡선”으로 해석할 때 왜곡이 생길 수 있습니다.

---

### 3. [중요] Calmar의 MDD=0 처리 로직이 모듈마다 다름

관련 위치:

- `src/qbt/backtest/analysis.py:145-150`
- `src/qbt/backtest/engines/backtest_engine.py:192-199`
- `src/qbt/backtest/walkforward.py:183-194`
- `src/qbt/backtest/walkforward.py:405-412`

문제:

- `analysis.py`, `backtest_engine.py`, `select_best_calmar_params()`는
  `CALMAR_MDD_ZERO_SUBSTITUTE + cagr`
- `walkforward._safe_calmar()`는
  `CALMAR_MDD_ZERO_SUBSTITUTE`
  로 처리합니다.

영향:

- 같은 `cagr/mdd`라도 summary, grid ranking, WFO summary에서 Calmar 값이 다를 수 있습니다.
- 특히 tie-break 느낌으로 CAGR를 더 반영하느냐 마느냐가 달라집니다.

이건 명확한 내부 논리 불일치입니다.

---

### 4. [중간] 문서상 4P 확정값 단일 소스 원칙과 스크립트 구현이 어긋남

관련 위치:

- 문서: `src/qbt/backtest/CLAUDE.md:59-69`
- 코드: `scripts/backtest/run_param_plateau_all.py:55-59`

문제:

- 문서에는 4P 확정값을 `constants.py`의 `FIXED_4P_*`를 참조한다고 정리돼 있습니다.
- 그런데 `run_param_plateau_all.py`는 `_FIXED_MA_WINDOW = 200`, `_FIXED_BUY_BUFFER = 0.03` 등으로 동일 값을 로컬 재정의합니다.

영향:

- 한쪽만 바뀌면 plateau 결과와 다른 분석 결과가 조용히 어긋날 수 있습니다.

---

### 5. [낮음] 주석과 실제 조건이 완전히 같지는 않음

관련 위치:

- `scripts/backtest/run_single_backtest.py:293-298`

문제:

- 주석은 “QQQ 시그널 전략만 MARKET_REGIMES 적용”이라고 되어 있습니다.
- 실제 코드는 “전략 종류”가 아니라 `signal_path == QQQ_DATA_PATH`인지로 판정합니다.

영향:

- 지금 의도와 거의 맞을 가능성은 크지만, 엄밀히는 “QQQ 시그널을 쓰는 모든 전략”에 적용될 수 있습니다.
- 설명을 코드 기준으로 더 정확히 써두는 편이 좋습니다.

---

## 3) 반복적이거나 비슷해서 통합하면 좋은 부분

### 1. Calmar 안전 계산

관련 위치:

- `analysis.py`
- `backtest_engine.py`
- `walkforward.py`

통합 가치가 큽니다.
현재는 중복 + 불일치가 동시에 있습니다.

---

### 2. signal/trade 로딩 + overlap 추출

관련 위치:

- `src/qbt/backtest/runners.py:118-128`
- `scripts/backtest/run_walkforward.py:74-88`
- `scripts/backtest/run_param_plateau_all.py:145-166`
- `src/qbt/backtest/engines/portfolio_data.py:27-39`

거의 같은 패턴이 여러 번 나옵니다.
단일/포트폴리오/스크립트가 같은 규칙을 공유하게 만들면 drift가 줄어듭니다.

---

### 3. MA 계산 + valid row 필터링

관련 위치:

- `src/qbt/backtest/runners.py:133-140`
- `src/qbt/backtest/engines/backtest_engine.py:532-543`
- `src/qbt/backtest/walkforward.py:333-339`

이 부분도 공통 helper로 빼기 좋습니다.
특히 이번 WFO 문제도 이 중복이 원인 중 하나입니다.

---

### 4. portfolio의 공통 날짜 교집합 + warmup 적용

관련 위치:

- `src/qbt/backtest/engines/portfolio_engine.py:97-151`
- `src/qbt/backtest/engines/portfolio_engine.py:206-263`

사실상 같은 로직이 두 번 있습니다.
버그 가능성보다 “한 군데 고치고 한 군데 놓치기 쉬운 구조”라는 점이 더 문제입니다.

---

### 5. `run_param_plateau_all.py`의 실험 반복 루프

관련 위치:

- `scripts/backtest/run_param_plateau_all.py:191-278`

`hold_days`, `sell_buffer`, `buy_buffer`, `ma_window` 루프가 거의 같은 모양입니다.
“바뀌는 필드명 / 값 목록 / signal_df”만 받아서 실행하는 helper 하나로 줄일 수 있습니다.

---

## 4) 상수화를 진행하면 좋은 부분

### 1. `run_param_plateau_all.py`의 4P 고정값

관련 위치:

- `scripts/backtest/run_param_plateau_all.py:55-59`

이건 로컬 상수보다 `src/qbt/backtest/constants.py`의 아래 상수를 직접 import 하는 게 맞습니다.

- `FIXED_4P_MA_WINDOW`
- `FIXED_4P_BUY_BUFFER_ZONE_PCT`
- `FIXED_4P_SELL_BUFFER_ZONE_PCT`
- `FIXED_4P_HOLD_DAYS`

이건 상수화라기보다 “기존 상수 재사용”이 더 정확합니다.

---

### 2. 포트폴리오 기본 자본금

관련 위치:

- `src/qbt/backtest/portfolio_configs.py:32`
- `src/qbt/backtest/constants.py:23`

`_DEFAULT_TOTAL_CAPITAL = 10_000_000.0`는 `DEFAULT_INITIAL_CAPITAL`과 값이 같습니다.
정말 포트폴리오만 별도 의미가 있는 값이 아니라면 하나로 묶는 편이 낫습니다.

---

### 3. plateau 대상 자산 목록

관련 위치:

- `scripts/backtest/run_param_plateau_all.py:45-53`

완전한 “상수”라기보다 중앙화 대상입니다.
현재는 `buffer_zone` 설정 집합과 별도로 유지돼서, 대상 자산 추가/삭제 시 스크립트만 따로 drift할 수 있습니다.

---

## 5) 과도한 오버엔지니어링

여기는 많지 않았습니다. 억지로 늘리지 않겠습니다.

### 1. `StrategySpec.supports_single / supports_portfolio` 예약 필드

관련 위치:

- `src/qbt/backtest/strategy_registry.py:43-52`

현재 코드에서 실사용 흔적이 없습니다.
확장 대비용으로 넣은 것 같지만, 아직 쓰지 않는다면 오히려 구조를 읽는 비용만 늘립니다.

---

### 2. `BufferZoneStrategy`의 `ma_type` 보관

관련 위치:

- `src/qbt/backtest/strategies/buffer_zone.py:295-307`
- `src/qbt/backtest/strategy_registry.py:69-75`

`ma_type`은 실제 시그널 계산에서 쓰이지 않고, 이미 외부에서 계산된 `ma_col`만 소비합니다.
즉 전략 객체가 굳이 들고 있을 필요가 거의 없습니다.

이 필드는 지금 당장 버그는 아니지만,

- “전략이 MA를 계산하는가?”
- “전략은 계산된 컬럼만 읽는가?”
  경계를 흐리게 만듭니다.

---

## 정리하면, 우선순위는 이 순서가 좋습니다

1. `walkforward` / `stitched equity`의 MA warmup·EMA reset 문제 수정
2. Calmar 계산 함수 단일화
3. signal/trade 로딩 + overlap + MA valid filtering 공용화
4. portfolio preflight 로직 중복 제거

가장 실질적인 건 1번입니다.
나머지는 리팩토링인데, 1번은 결과 해석을 바꿀 수 있는 항목입니다.
