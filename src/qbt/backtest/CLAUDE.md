# 백테스트 도메인 가이드

> 이 문서는 `src/qbt/backtest/` 패키지의 백테스트 도메인에 대한 상세 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

백테스트 도메인은 과거 데이터를 기반으로 거래 전략을 시뮬레이션하고 성과를 측정합니다.
이동평균 기반 버퍼존 전략 및 매수 후 보유(Buy & Hold) 벤치마크 전략을 제공합니다.

---

## 모듈 구성

### 1. constants.py

**백테스트 도메인 전용 상수를 정의합니다** (공통 상수는 `common_constants.py` 참고):

**거래 비용**:

- `SLIPPAGE_RATE = 0.003` (거래당 0.3%, 슬리피지 + 수수료 통합)

**기본 파라미터**:

- `DEFAULT_INITIAL_CAPITAL = 10_000_000.0` (초기 자본금)
- `DEFAULT_MA_WINDOW`: 이동평균 기간
- `DEFAULT_BUFFER_ZONE_PCT`: 버퍼존 비율 (0일 = 버퍼존만 모드)
- `DEFAULT_HOLD_DAYS`: 유지조건 일수
- `DEFAULT_RECENT_MONTHS`: 최근 매수 기간 (개월)

**제약 조건**:

- `MIN_BUFFER_ZONE_PCT`: 최소 버퍼존 비율
- `MIN_HOLD_DAYS`: 최소 유지조건 일수
- `MIN_VALID_ROWS`: 백테스트 최소 데이터 행 수
- `BUFFER_INCREMENT_PER_BUY`: 최근 매수 1회당 버퍼존 증가량
- `HOLD_DAYS_INCREMENT_PER_BUY`: 최근 매수 1회당 유지조건 증가량
- `DAYS_PER_MONTH`: 최근 기간 계산용 월당 일수

**그리드 서치 기본값**:

- `DEFAULT_MA_WINDOW_LIST`: 이동평균 기간 후보 리스트
- `DEFAULT_BUFFER_ZONE_PCT_LIST`: 버퍼존 비율 후보 리스트
- `DEFAULT_HOLD_DAYS_LIST`: 유지조건 일수 후보 리스트
- `DEFAULT_RECENT_MONTHS_LIST`: 최근 매수 기간 후보 리스트

**컬럼 및 레이블**:

- DataFrame 컬럼명: `COL_MA_WINDOW`, `COL_BUFFER_ZONE_PCT`, `COL_HOLD_DAYS` 등
- 출력용 레이블: `DISPLAY_MA_WINDOW`, `DISPLAY_BUFFER_ZONE`, `DISPLAY_CAGR` 등

근거 위치: [src/qbt/backtest/constants.py](constants.py)

---

### 2. analysis.py

**이동평균 계산 및 성과 지표 분석 함수를 제공합니다.**

**주요 함수**:

**`add_single_moving_average(df, window, ma_type)`**:

- 단일 이동평균(SMA 또는 EMA)을 계산하여 DataFrame에 컬럼 추가
- 입력: DataFrame, 윈도우 크기, 이동평균 타입 (`"sma"` or `"ema"`)
- 반환: 이동평균 컬럼이 추가된 DataFrame
- 원본 DataFrame 불변 (복사본 반환)

**`calculate_summary(trades, equity_history)`**:

- 거래 내역과 자본 곡선으로부터 성과 지표 계산
- 입력: 거래 내역 리스트, 에쿼티 이력 리스트
- 반환: 성과 요약 딕셔너리
  - 수익률 지표: `total_return_pct`, `cagr` (연평균 복리 수익률)
  - 리스크 지표: `mdd` (최대 낙폭)
  - 거래 통계: `total_trades`, `win_rate`, `profitable_trades`, `losing_trades`

근거 위치: [src/qbt/backtest/analysis.py](analysis.py)

---

### 3. strategy.py

**전략 실행 엔진의 핵심 모듈입니다** (944줄).

#### 데이터 클래스

**`BufferStrategyParams`** (데이터클래스):

- 버퍼존 전략 파라미터 캡슐화
- 필드: `initial_capital`, `ma_window`, `buffer_zone_pct`, `hold_days`, `recent_months`

**`BuyAndHoldParams`** (데이터클래스):

- Buy & Hold 전략 파라미터
- 필드: `initial_capital`

**`PendingOrder`** (데이터클래스):

- 예약 주문 정보
- 필드: `execute_date`, `order_type`, `price_raw`, `signal_date`, `buffer_zone_pct`, `hold_days_used`, `recent_buy_count`
- 역할: 신호 발생일(i일 종가)과 체결일(i+1일 시가)을 명확히 분리

#### 예외 클래스

**`PendingOrderConflictError`**:

- Pending Order 충돌 예외 (Critical Invariant 위반)
- 발생 조건: pending_order가 이미 존재하는 상태에서 새로운 신호가 발생할 때
- 중요도: 매우 크리티컬한 버그로, 발견 즉시 백테스트 중단

#### 주요 함수

**`run_buffer_strategy(params, df)`**:

- 버퍼존 전략 실행
- 입력: BufferStrategyParams, 주가 DataFrame
- 반환: `(trades, equity_history, summary)` 튜플

**`run_buy_and_hold(params, df)`**:

- 매수 후 보유 벤치마크 전략 실행
- 입력: BuyAndHoldParams, 주가 DataFrame
- 반환: `(trades, equity_history, summary)` 튜플

**`run_grid_search(params_list, df)`**:

- 파라미터 그리드 탐색
- 입력: BufferStrategyParams 리스트, 주가 DataFrame
- 반환: 결과 DataFrame (정렬: CAGR 내림차순)
- 병렬 처리: `execute_parallel_with_kwargs` 사용

근거 위치: [src/qbt/backtest/strategy.py](strategy.py)

---

## 도메인 규칙

### 1. 전략 파라미터

**이동평균 기간 (`ma_window`)**:

- 추세 판단의 기준 기간 (예: 200일)
- 범위: 1 이상 (검증: `_validate_buffer_strategy_inputs`)

**버퍼존 (`buffer_zone_pct`)**:

- 이동평균선 주변 허용 범위 (비율, 0~1)
- 거래 빈도 조절 수단
- 최소값: `MIN_BUFFER_ZONE_PCT` (0.01 = 1%)
- 동적 조정: 최근 매수 1회당 `BUFFER_INCREMENT_PER_BUY` 증가

**유지 조건 (`hold_days`)**:

- 신호 확정까지 대기 기간 (일)
- 잦은 거래 방지
- 최소값: `MIN_HOLD_DAYS` (0일 = 버퍼존만 모드)
- 동적 조정: 최근 매수 1회당 `HOLD_DAYS_INCREMENT_PER_BUY` 증가

**조정 기간 (`recent_months`)**:

- 최근 거래를 분석할 기간 (개월)
- 0이면 동적 조정 비활성화
- 동적 파라미터 조정 범위 결정

근거 위치: [constants.py](constants.py), [strategy.py의 \_validate_buffer_strategy_inputs](strategy.py)

---

### 2. 비용 모델

**거래 비용**:

- 매수/매도 시 일정 비율 적용
- `SLIPPAGE_RATE = 0.003` (0.3%, 슬리피지 + 수수료 통합)
- 적용 방식:
  - 매수: `price_raw × (1 + SLIPPAGE_RATE)`
  - 매도: `price_raw × (1 - SLIPPAGE_RATE)`

근거 위치: [constants.py의 SLIPPAGE_RATE](constants.py), [strategy.py의 \_execute_buy_order, \_execute_sell_order](strategy.py)

---

### 3. 체결 타이밍 규칙 (절대 규칙)

**신호 발생과 체결 실행의 분리**:

- **신호 발생**: i일 종가 기준으로 상단/하단 밴드 돌파 감지
- **체결 실행**: i+1일 시가에 실제 매수/매도 (hold_days=0 기준)
- **비용 적용**: 시가에 슬리피지 적용 (비용 모델 참조)

근거 위치: [strategy.py의 run_buffer_strategy 메인 루프](strategy.py)

---

### 4. Equity 및 Final Capital 정의 (절대 규칙)

**Equity 정의**:

- 모든 시점에서 `equity = cash + position_shares × close`
- 포지션 보유 시: 현금 + 주식 평가액 (종가 기준)
- 포지션 없을 시: 현금만

**Final Capital 정의**:

- 마지막 날 `final_capital = cash + position_shares × last_close`
- 마지막에 포지션이 남아 있을 수 있음
- 강제청산/강제매도 없음 (Trade 생성 안 함)
- 최종 자본은 항상 "현금 + 평가액" 기준

근거 위치: [strategy.py의 \_record_equity, run_buffer_strategy 종료 로직](strategy.py), [analysis.py의 calculate_summary](analysis.py)

---

### 5. Pending Order 정책 (절대 규칙)

**단일 슬롯 원칙**:

- `pending_order`는 반드시 단일 변수로 관리 (리스트 누적 금지)
- 신호일에 생성: i일 종가에서 신호 확정 시 `PendingOrder` 생성
- 체결일에 실행: i+1일 시가에 `pending_order` 실행 후 `None`으로 초기화

**Critical Invariant (충돌 감지)**:

- `pending_order`가 존재하는 동안 새로운 신호가 발생하면 안 됨
- 위반 시: 즉시 `PendingOrderConflictError` 예외 발생 + 백테스트 중단
- 이는 매우 크리티컬한 버그로 간주됨

근거 위치: [strategy.py의 PendingOrderConflictError, \_check_pending_conflict, run_buffer_strategy 메인 루프](strategy.py)

---

### 6. hold_days 규칙 (Lookahead 방지, 절대 규칙)

**hold_days = 0 (버퍼존만 모드)**:

- 돌파일(i일) 종가에서 신호 확정
- i일 종가에 `pending_order` 생성
- i+1일 시가에 체결

**hold_days = 1**:

- 돌파일(i일)에는 `pending` 생성 안 함 (카운트 시작만)
- i+1일 종가에서 유지조건 충족 시 `pending_order` 생성
- i+2일 시가에 체결

**일반화 (hold_days = H)**:

- 돌파일: i
- 유지조건 체크: i+1 ~ i+H일 종가
- 신호 확정일: i+H일 종가
- 체결일: i+H+1일 시가

**유지조건**:

- 각 체크일 d에서 조건 만족 필요 (예: 매수 기준 `close[d] > upper_band[d]`)
- 실패 시: hold 트래킹 리셋

**Lookahead 금지**:

- **금지**: i일에 i+1 ~ i+H를 미리 검사해 `pending`을 선적재하는 방식
- **필수**: 매일 순차적으로 유지조건 체크 (상태머신 방식)
- **구현 방식**:
  - 돌파 발생 시: hold_state 초기화 (days_passed=0)
  - 매일: hold_state가 존재하면 유지조건 체크
    - 조건 통과: days_passed += 1
    - 조건 실패: hold_state = None (리셋)
    - days_passed == hold_days_required: pending_order 생성 후 hold_state = None
- **이유**: 미래 정보 사용 방지, 실제 거래와 동일한 순차 검증

근거 위치: [strategy.py의 run_buffer_strategy 메인 루프, hold tracking 로직](strategy.py)

---

### 7. 마지막 날 규칙

**전날 pending**:

- 마지막 날(N일) 시가가 존재하므로, N-1일 종가에서 생성된 `pending`은 N일 시가에서 정상 체결됨

**당일 신호**:

- N일 종가에서 발생한 신호는 N+1일 시가가 없으므로 `pending` 생성하지 않음 (드롭/무시)

**마지막 Equity 및 Final Capital**:

- N일 종가 기준으로 `equity = cash + position × close[N]` 계산
- `final_capital = equity[N]` (마지막 날 equity와 동일)
- **강제청산 없음**: 마지막 날에 포지션이 남아있어도 강제로 매도하지 않음
  - 이유: equity_df, trades_df, summary.final_capital 간 일관성 보장
  - trades_df는 실제 신호에 의한 거래만 기록
  - final_capital은 항상 "현금 + 평가액" 기준

근거 위치: [strategy.py의 run_buffer_strategy 메인 루프 종료 부분](strategy.py)

---

### 8. 에쿼티 기록

**각 날짜의 에쿼티**:

- 해당일에 실행된 주문 이후 상태를 반영
- 신호 발생일에는 아직 포지션이 없으므로 `position=0` (`pending`만 존재)
- 체결일부터 포지션이 반영됨

근거 위치: [strategy.py의 \_record_equity, run_buffer_strategy 메인 루프](strategy.py)

---

### 9. 파라미터 최적화

**그리드 탐색**:

- 다차원 파라미터 조합 탐색
- 파라미터 리스트를 받아 모든 조합 실행
- 병렬 처리로 성능 최적화 (`execute_parallel_with_kwargs`)
- 결과는 CAGR 내림차순 정렬

**동적 조정**:

- 최근 거래 빈도 분석 (`recent_months` 기반)
- 최근 매수 횟수에 따라 버퍼존 및 유지조건 자동 조정
- `BUFFER_INCREMENT_PER_BUY`, `HOLD_DAYS_INCREMENT_PER_BUY` 상수 사용

근거 위치: [strategy.py의 run_grid_search, 동적 조정 로직](strategy.py), [constants.py](constants.py)

---

## 검증 규칙

### 최소 데이터 요구사항

- 백테스트에 필요한 최소 데이터 행 수: `MIN_VALID_ROWS = 2`
- 유효하지 않은 경우 즉시 예외 발생

근거 위치: [constants.py의 MIN_VALID_ROWS](constants.py)

### 필수 컬럼

- `Date`, `Open`, `Close` 등 필수 필드 검증
- `common_constants.py`의 `REQUIRED_COLUMNS` 사용
- 이동평균 컬럼 (`ma_col`) 존재 여부 확인

근거 위치: [strategy.py의 \_validate_buffer_strategy_inputs](strategy.py), [common_constants.py](../../common_constants.py)

---

## 구현 원칙

### 1. 데이터 불변성

- 원본 DataFrame을 변경하지 않음
- 계산 시 복사본 사용 (예: `df.copy()`)

### 2. 명시적 검증

- 파라미터 유효성 즉시 검증
- 유효하지 않은 입력 시 즉시 예외 발생 (ValueError)

### 3. 상태 비저장

- 함수는 상태를 유지하지 않음
- 모든 입력을 파라미터로 전달
- 순수 함수 스타일

### 4. 병렬 처리 지원

- 독립적인 백테스트는 병렬 실행 가능
- 순서 보장 필요 시 중앙 병렬 처리 모듈 사용 (`utils/parallel_executor.py`)
- pickle 가능한 함수만 사용

근거 위치: [strategy.py](strategy.py), [utils/parallel_executor.py](../../utils/parallel_executor.py)

---

## 출력 형식

### 거래 내역 (Trades)

- 리스트 형태
- 각 거래: 날짜, 방향, 가격, 수량, 손익 등

### 자본 곡선 (Equity History)

- 리스트 형태
- 각 기록: 날짜, equity, position, buffer_zone_pct, upper_band, lower_band

### 요약 지표 (Summary)

- 딕셔너리 형태
- 수익률, 리스크, 거래 통계 포함
- 키 예시: `total_return_pct`, `cagr`, `mdd`, `total_trades`, `win_rate`

### 그리드 탐색 결과 (Grid Search Results)

- DataFrame 형태
- 파라미터 조합별 성과 지표
- 한글 컬럼명으로 변환하여 CSV 저장 (`storage/results/grid_results.csv`)
- 정렬: CAGR 내림차순

근거 위치: [strategy.py](strategy.py), [analysis.py](analysis.py)

---

## CSV 파일 형식

### grid_results.csv

**경로**: `storage/results/grid_results.csv`

**컬럼** (파라미터 4개 + 지표 6개 = 총 10개):

1. `이평기간`: 이동평균 기간
2. `버퍼존`: 버퍼존 비율 (%)
3. `유지일`: 유지조건 (일)
4. `조정기간(월)`: 최근 매수 기간 (개월)
5. `수익률`: 총 수익률 (%)
6. `CAGR`: 연평균 복리 수익률 (%)
7. `MDD`: 최대 낙폭 (%)
8. `거래수`: 총 거래 횟수
9. `승률`: 승률 (%)
10. `최종자본`: 최종 자본금

**정렬**: CAGR 내림차순

**용도**: 최적 파라미터 조합 탐색, 전략 성과 비교

근거 위치: [scripts/backtest/run_grid_search.py](../../../scripts/backtest/run_grid_search.py), [constants.py](constants.py)

---

## 핵심 계산 로직

### 버퍼존 밴드 계산

```
upper_band = ma × (1 + buffer_zone_pct)
lower_band = ma × (1 - buffer_zone_pct)
```

근거 위치: [strategy.py의 \_compute_bands](strategy.py)

### 동적 파라미터 조정

```
adjusted_buffer_pct = base_buffer_pct + (recent_buy_count × BUFFER_INCREMENT_PER_BUY)
adjusted_hold_days = base_hold_days + (recent_buy_count × HOLD_DAYS_INCREMENT_PER_BUY)
```

**상수 사용 필수**:

- `BUFFER_INCREMENT_PER_BUY`: 최근 매수 1회당 버퍼존 증가량 (0.01 = 1%)
- `HOLD_DAYS_INCREMENT_PER_BUY`: 최근 매수 1회당 유지조건 증가량 (1일)
- **주의**: 하드코딩 금지 (`+ recent_buy_count` 대신 `+ recent_buy_count × HOLD_DAYS_INCREMENT_PER_BUY` 사용)
- **이유**: 정책 변경 시 상수만 수정하면 되도록

근거 위치: [strategy.py의 동적 조정 로직](strategy.py), [constants.py](constants.py)

### 성과 지표 계산

- **총 수익률**: `(final_capital - initial_capital) / initial_capital × 100`
- **CAGR**: `((final_capital / initial_capital) ^ (ANNUAL_DAYS / 총일수)) - 1`
- **MDD**: 자본 곡선에서 최대 낙폭 계산
- **승률**: `profitable_trades / total_trades × 100`

근거 위치: [analysis.py의 calculate_summary](analysis.py)

---

## 사용 예시

### 단일 백테스트

```python
from qbt.backtest import run_buffer_strategy
from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL

params = BufferStrategyParams(
    initial_capital=DEFAULT_INITIAL_CAPITAL,
    ma_window=200,
    buffer_zone_pct=0.03,
    hold_days=0,
    recent_months=0
)

trades, equity_history, summary = run_buffer_strategy(params, df)
```

### 그리드 탐색

```python
from qbt.backtest import run_grid_search

params_list = [
    BufferStrategyParams(initial_capital=10_000_000, ma_window=100, buffer_zone_pct=0.01, hold_days=0, recent_months=0),
    BufferStrategyParams(initial_capital=10_000_000, ma_window=200, buffer_zone_pct=0.03, hold_days=1, recent_months=6),
    # ...
]

results_df = run_grid_search(params_list, df)
```

근거 위치: [scripts/backtest/run_single_backtest.py](../../../scripts/backtest/run_single_backtest.py), [scripts/backtest/run_grid_search.py](../../../scripts/backtest/run_grid_search.py)

---

## 테스트 커버리지

**주요 테스트 파일**: [tests/test_strategy.py](../../../tests/test_strategy.py) (983줄)

**테스트 범위**:

- 신호 생성 로직
- 거래 체결 타이밍
- Pending Order 충돌 감지
- 파라미터 유효성 검증
- 엣지 케이스 (빈 데이터, 극단값)
- 동적 파라미터 조정
- 그리드 서치 병렬 처리

근거 위치: [tests/test_strategy.py](../../../tests/test_strategy.py), [tests/test_analysis.py](../../../tests/test_analysis.py)
