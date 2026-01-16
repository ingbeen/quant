# 백테스트 도메인 가이드

> 이 문서는 `src/qbt/backtest/` 패키지의 백테스트 도메인에 대한 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

백테스트 도메인은 과거 데이터를 기반으로 거래 전략을 시뮬레이션하고 성과를 측정합니다.
이동평균 기반 버퍼존 전략 및 매수 후 보유(Buy & Hold) 벤치마크 전략을 제공합니다.

---

## 모듈 구성

### 1. constants.py

백테스트 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 거래 비용: `SLIPPAGE_RATE` (0.3%, 슬리피지 + 수수료 통합)
- 기본 파라미터: `DEFAULT_INITIAL_CAPITAL`, `DEFAULT_MA_WINDOW`, `DEFAULT_BUFFER_ZONE_PCT` 등
- 제약 조건: `MIN_BUFFER_ZONE_PCT`, `MIN_HOLD_DAYS`, `MIN_VALID_ROWS`
- 동적 조정: `BUFFER_INCREMENT_PER_BUY`, `HOLD_DAYS_INCREMENT_PER_BUY`
- 그리드 서치 기본값: `DEFAULT_MA_WINDOW_LIST`, `DEFAULT_BUFFER_ZONE_PCT_LIST` 등

### 2. analysis.py

이동평균 계산 및 성과 지표 분석 함수를 제공합니다.

주요 함수:

- `add_single_moving_average`: 단일 이동평균(SMA/EMA) 계산
- `calculate_summary`: 거래 내역과 자본 곡선으로부터 성과 지표 계산

### 3. strategy.py

전략 실행 엔진의 핵심 모듈입니다.

데이터 클래스:

- `BufferStrategyParams`: 버퍼존 전략 파라미터
- `BuyAndHoldParams`: Buy & Hold 전략 파라미터
- `PendingOrder`: 예약 주문 정보 (신호일과 체결일 분리)

예외 클래스:

- `PendingOrderConflictError`: Pending Order 충돌 예외 (Critical Invariant 위반)

주요 함수:

- `run_buffer_strategy`: 버퍼존 전략 실행
- `run_buy_and_hold`: 매수 후 보유 벤치마크 전략 실행
- `run_grid_search`: 파라미터 그리드 탐색 (병렬 처리)

---

## 도메인 규칙

### 1. 전략 파라미터

- 이동평균 기간 (`ma_window`): 추세 판단의 기준 기간, 1 이상
- 버퍼존 (`buffer_zone_pct`): 이동평균선 주변 허용 범위 (비율, 0~1)
- 유지 조건 (`hold_days`): 신호 확정까지 대기 기간 (일), 0 = 버퍼존만 모드
- 조정 기간 (`recent_months`): 최근 거래 분석 기간, 0이면 동적 조정 비활성화

### 2. 비용 모델

- 매수: `price_raw * (1 + SLIPPAGE_RATE)`
- 매도: `price_raw * (1 - SLIPPAGE_RATE)`

### 3. 체결 타이밍 규칙 (절대 규칙)

신호 발생과 체결 실행의 분리:

- 신호 발생: i일 종가 기준으로 상단/하단 밴드 돌파 감지
- 체결 실행: i+1일 시가에 실제 매수/매도 (hold_days=0 기준)

### 4. Equity 및 Final Capital 정의 (절대 규칙)

- Equity: `equity = cash + position_shares * close`
- Final Capital: 마지막 날 equity와 동일, 강제청산 없음

### 5. Pending Order 정책 (절대 규칙)

단일 슬롯 원칙:

- `pending_order`는 반드시 단일 변수로 관리 (리스트 누적 금지)
- 신호일에 생성, 체결일에 실행 후 `None`으로 초기화

Critical Invariant:

- `pending_order`가 존재하는 동안 새로운 신호 발생 시 `PendingOrderConflictError` 예외

### 6. hold_days 규칙 (Lookahead 방지, 절대 규칙)

일반화 (hold_days = H):

- 돌파일: i
- 유지조건 체크: i+1 ~ i+H일 종가
- 신호 확정일: i+H일 종가
- 체결일: i+H+1일 시가

Lookahead 금지:

- 금지: i일에 i+1 ~ i+H를 미리 검사해 `pending`을 선적재하는 방식
- 필수: 매일 순차적으로 유지조건 체크 (상태머신 방식)

### 7. 마지막 날 규칙

- N-1일 종가에서 생성된 `pending`은 N일 시가에서 정상 체결
- N일 종가에서 발생한 신호는 N+1일 시가가 없으므로 무시
- 강제청산 없음: 마지막 날에 포지션이 남아있어도 강제 매도하지 않음

---

## 핵심 계산 로직

### 버퍼존 밴드 계산

```
upper_band = ma * (1 + buffer_zone_pct)
lower_band = ma * (1 - buffer_zone_pct)
```

### 동적 파라미터 조정

```
adjusted_buffer_pct = base_buffer_pct + (recent_buy_count * BUFFER_INCREMENT_PER_BUY)
adjusted_hold_days = base_hold_days + (recent_buy_count * HOLD_DAYS_INCREMENT_PER_BUY)
```

주의: 하드코딩 금지, 상수 사용 필수

### 성과 지표 계산

- 총 수익률: `(final_capital - initial_capital) / initial_capital * 100`
- CAGR: `((final_capital / initial_capital) ^ (ANNUAL_DAYS / 총일수)) - 1`
- MDD: 자본 곡선에서 최대 낙폭 계산
- 승률: `profitable_trades / total_trades * 100`

---

## CSV 파일 형식

### grid_results.csv

경로: `storage/results/grid_results.csv`

주요 컬럼: 이평기간, 버퍼존, 유지일, 조정기간(월), 수익률, CAGR, MDD, 거래수, 승률, 최종자본

정렬: CAGR 내림차순

---

## 테스트 커버리지

주요 테스트 파일: `tests/test_strategy.py`, `tests/test_analysis.py`

테스트 범위:

- 신호 생성 로직 및 거래 체결 타이밍
- Pending Order 충돌 감지
- 파라미터 유효성 검증
- 엣지 케이스 (빈 데이터, 극단값)
- 동적 파라미터 조정
- 그리드 서치 병렬 처리
