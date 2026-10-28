# 백테스트 도메인 가이드

> 이 문서는 `src/qbt/backtest/` 패키지의 백테스트 도메인에 대한 가이드입니다.

## 도메인 목적

백테스트 도메인은 과거 데이터를 기반으로 거래 전략을 시뮬레이션하고 성과를 측정합니다.
이동평균 기반 버퍼존 전략 및 매수 후 보유(Buy & Hold) 벤치마크 전략을 제공합니다.

---

## 모듈 지도

함수 · 필드 · 시그니처 · 열 이름은 각 모듈 docstring 이 정본입니다. 여기에는 모듈의 책임과 docstring 에 없는 「왜」만 둡니다.

공통 · 분석:

- `types.py` — 도메인 공통 TypedDict · dataclass (성과 요약 · 미청산 포지션 · 버퍼존 파라미터 · 단일 실행 결과 · 워크포워드 결과). 전략 전용 타입은 각 전략 모듈에 둔다
- `constants.py` — 도메인 상수 (비용 `SLIPPAGE_RATE` · 초기 자본 · 4P 확정값 `FIXED_4P_*` · 워크포워드 그리드와 판단 기준 · 결과 파일명 · 리밸런싱 사유 값)
- `analysis.py` — 이동평균(SMA — 도메인 규칙 1-1)과 성과 지표(요약 · 월별 · 연간 수익률 · Sharpe · Sortino)
- `csv_export.py` — 결과 CSV 저장 직전 변환(거래 표 · 전일대비% · 밴드 · 시그널 반올림)과 포트폴리오 폴더의 구성 의존 파일 지우기. 대시보드가 도메인 계산을 다시 하지 않도록 러너가 시그널 CSV 에 미리 넣는다
- `dashboard_charts.py` — 단일 · 포트폴리오 · 워크포워드 대시보드가 같은 모양으로 그리는 차트(lightweight-charts 캔들 패널 · 월별 히트맵). src 에 둔 것은 세 앱이 같은 코드를 쓰고 테스트가 부를 수 있게 하려는 것이다

전략:

- `strategies/strategy_common.py` — 두 엔진이 같이 쓰는 전략 인터페이스 `SignalStrategy` Protocol
- `strategies/buffer_zone.py` · `buffer_zone_helpers.py` — 버퍼존 전략 `BufferZoneStrategy`(stateful)와 자산별 설정 `CONFIGS`(전 자산 4P), 밴드 · 돌파 감지 함수
- `strategies/buy_and_hold.py` — Buy & Hold 벤치마크 전략과 티커별 `CONFIGS`
- `strategy_registry.py` — `STRATEGY_REGISTRY`: 포트폴리오 엔진이 `strategy_id` 문자열로 전략을 만든다. 새 전략은 등록만 하고 엔진은 고치지 않는다
- `runners.py` — 단일 백테스트 설정을 실행 함수로 만드는 팩토리 (전략 모듈 ↔ 엔진 순환 의존을 끊는 자리)
- `strategies/` · `qbt.backtest` 패키지는 재노출하지 않는다 — 각 모듈을 직접 import 한다

단일 · 워크포워드 · 고원:

- `engines/backtest_engine.py` — 단일 자산 백테스트(`run_backtest`, 전략 주입)와 병렬 그리드 서치. 그리드 · 고원 이동평균 실험은 모든 조합을 같은 기간으로 평가한다(`prepare_common_period`)
- `walkforward.py` — Expanding Anchored 워크포워드 (윈도우 생성 · IS 그리드 최적 선택 · OOS 평가 · 이어 붙인 자본곡선 · 모드 요약)
- `walkforward_verdict.py` — 워크포워드 결과로 대시보드의 판단 문구를 만든다
- `parameter_stability.py` — 고원 분석 CSV 로딩과 고원 구간 탐지

포트폴리오:

- `portfolio_types.py` — 실험 설정(`PortfolioConfig` · 슬롯 · 매매법) · 런타임 상태 · 결과 데이터클래스와 결과 파일의 자산 키 규칙
- `portfolio_configs.py` — 등록 실험 `PORTFOLIO_CONFIGS`. 보완 전략 등록 실험은 `supplement_experiment` 의 구성 함수로 만든다
- `engines/` — 포트폴리오 엔진: `portfolio_engine.py`(facade · 일별 루프) · `portfolio_planning.py`(주문 의도 · 예상 상태 · 병합) · `portfolio_methods.py`(매매법 장부 · 배분 변화 · 매매법 사이 비중 · 상계 · 요약) · `portfolio_rebalance.py`(리밸런싱 정책 · 판단일) · `portfolio_execution.py`(매도 → 매수 체결) · `portfolio_data.py`(로딩 · 설정 검증 · 에쿼티 표), 두 엔진 공통은 `engine_common.py`(예약 주문 · 체결 계산 · 거래 기록)
- `portfolio_validation.py` — 실행 직후 결과 정합성 검사 (규칙 목록은 그 docstring). 위반이 있으면 러너가 결과를 저장한 뒤 멈춘다
- `allocator_registry.py` · `allocators/` — 비중이 바뀌는 매매법의 배분 규칙. 새 규칙은 `allocators/` 에 구현해 등록하고 엔진은 고치지 않는다. 규칙은 이동평균 · 월말 행 같은 파생 계산을 첫 호출의 data 로 한 번 만든다 — 엔진은 실행마다 규칙을 새로 만들고 같은 data 를 매일 넘긴다. 행 i 의 판단은 i 이하 행만 쓴다
- `supplement_experiment.py` — 보완 전략 비중 그리드의 구성 · 실행 목록 · 지표 · 판정 · 대용 검증. 결정 근거는 `docs/research/전략_검증_보고서.md` 부록 M
- `combo_experiment.py` — 조합 그리드(Q-2-2XS + HAA + 로테이션)의 실행 목록 · 판정 · 대체 판 확인. 결정 근거는 `docs/research/전략_검증_보고서.md` 부록 M

---

## 도메인 규칙

### 1. 전략 파라미터

- 이동평균 기간 (`ma_window`): 추세 판단의 기준 기간, 1 이상
- 매수 버퍼존 (`buy_buffer_zone_pct`): upper_band 기준 매수 진입 허용 범위 (비율, 0~1)
- 매도 버퍼존 (`sell_buffer_zone_pct`): lower_band 기준 매도 청산 허용 범위 (비율, 0~1)
- 유지 조건 (`hold_days`): 신호 확정까지 대기 기간 (일), 0 = 버퍼존만 모드

범위 검증은 파라미터마다 한 곳이다 — 버퍼존 비율(하한 `MIN_*_BUFFER_ZONE_PCT` 이상 1 미만)과 유지일수(`MIN_HOLD_DAYS` 이상)는 `BufferZoneStrategy` 생성자, 이동평균 기간은 `add_single_moving_average`. 전략을 만드는 모든 경로가 그 둘을 지나므로 호출부에 같은 검사를 다시 두지 않는다. 범위 밖 값은 검증이 없으면 예외 없이 다른 결과를 낸다. 포트폴리오 설정 검증은 슬롯마다 전략을 한 번 만들어 보아, 시세를 읽기 전에 어느 슬롯의 값인지와 함께 알린다.

> 이동평균 유형은 파라미터가 아니다. **SMA 로 고정**되어 있다 (아래 규칙 참고).

### 1-1. 이동평균은 SMA 하나뿐이다 (절대 규칙)

`add_single_moving_average` 는 **유형을 고르는 파라미터를 갖지 않으며**, 항상 단순이동평균을 계산한다.
EMA 계산 경로와 `ma_type` 파라미터·상수·필드는 없다.
`tests/qbt/test_ma_type_policy.py` 가 시그니처에 `ma_type` 이 없음을 검증하여 재도입을 막는다.
채택 근거는 `docs/research/전략_검증_보고서.md` 부록 G.1.

**부작용**: SMA 는 앞 `ma_window - 1` 행이 NaN 이므로 그만큼 백테스트 유효 시작일이 뒤로 밀린다.
짧은 합성 데이터로 테스트를 만들 때는 `ma_window` 를 데이터 길이에 맞춰 지정해야 워밍업 구간에 갇히지 않는다.

### 2. 비용 모델

- 매수: `price_raw * (1 + SLIPPAGE_RATE)`
- 매도: `price_raw * (1 - SLIPPAGE_RATE)`
- 왕복(매수+매도) 비용은 `2 × SLIPPAGE_RATE`이며, 매수와 매도가 각각 별도의 비용 이벤트로 누적된다. 이는 의도된 설계이며 슬리피지 이중 적용이 아니다.

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
- 체결일 아침에 pending 을 비운 뒤 그날 신호를 보므로, 신호 시점에 남은 pending 이 없다 (루프 순서로 보장 — 충돌 검사를 따로 두지 않는다)

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
- 미청산 포지션 기록: 종료 시 포지션이 남아있으면 summary에 `open_position` (entry_date, entry_price, shares) 포함. 대시보드에서 `"Buy (보유중)"` 마커로 표시된다

### 8. 포트폴리오 규칙

- **리밸런싱**: 엔진 고정 정책 `DEFAULT_REBALANCE_POLICY`(실험 설정으로 바꾸지 않는다). 월 마지막 거래일 종가에 목표 비중 대비 상대 편차가 임계값을 넘으면 다음 거래일 시가에 목표로 맞춘다. 월중에는 리밸런싱하지 않으며, 월중 버퍼존 재진입은 가용 현금으로 목표액만큼만 산다. 판단일에 진입 신호가 났거나 목표 비중이 바뀐 자산은 편차 판정에서 빠진다 — 남은 자산의 편차가 임계값을 넘을 때만 리밸런싱하고, 그때는 진입 자산까지 맞춘다 (결정 근거: `docs/research/전략_검증_보고서.md` 부록 L)
- **매매법**: 매매법마다 장부(몫 · 현금 · 보유 주수 · 손익)를 둔다. 매매법이 하나인 실험은 장부 하나가 곧 계좌다. 같은 판단일에 어느 매매법이든 몫(매매법 자본 합 대비)의 상대 편차가 임계값을 넘으면 전 매매법을 목표 몫으로 되돌리고, 각자 보유 종목 전부를 새 몫으로 맞춘다
- **체결 순서**: 전 매매법 매도 → 매매법 사이 이전 → 전 매매법 매수. 이전은 내주는 쪽의 매도 뒤 현금 안에서만 하고 모자라면 받는 쪽을 계획 비율대로 줄이며, 매수 총액이 현금을 넘으면 주수를 비례 축소한다 — 어느 장부도 현금이 음수가 되지 않는다. 같은 날 체결 순서는 설정 순서로 고정한다 — 집합 순서(문자열 해시 무작위화)로 돌면 같은 코드에서도 결과 파일이 실행마다 달라진다
- **종목 단위 상계**: 장부는 단독 매매처럼 비용을 내고, 같은 날 같은 자산의 반대 매매로 계좌에서 아낀 비용 (Σ|Δ| − |ΣΔ|) × 시가 × `SLIPPAGE_RATE` 는 상계 절감으로 계좌 현금에 둔다(매매법에 나누지 않음) — Σ 매매법 손익 + 상계 절감 = 계좌 손익
- **신호 시세**: 슬롯마다 따로 읽고, 매매 시세와 겹치는 기간으로 자른 뒤 이동평균을 계산한다 — 신호 시세가 더 길어도 워밍업은 매매 시세 첫날부터다
- **현금 버퍼**: 목표 비중 합이 1 미만이면 나머지는 현금으로 둔다
- **시작일**: 실험마다 자산 교집합 + 이동평균 워밍업 뒤 첫날이다(`compute_portfolio_effective_start_date`). 설정에 `min_start_date` 가 있는 실험은 그날 시작하고, 러너 · 그리드 워커가 실제 시작일을 대조한다(`run_with_start_check`)

---

## 핵심 계산 로직

### 버퍼존 밴드 계산

```
upper_band = ma * (1 + buy_buffer_zone_pct)   # 매수 진입 기준
lower_band = ma * (1 - sell_buffer_zone_pct)   # 매도 청산 기준
```

### 성과 지표 계산

- 총 수익률: `(final_capital - initial_capital) / initial_capital * 100`
- CAGR: `((final_capital / initial_capital) ^ (ANNUAL_DAYS / 총일수)) - 1`
- MDD: 자본 곡선에서 최대 낙폭 계산
- Calmar: `CAGR / |MDD|` (|MDD| < EPSILON이면 CAGR > 0일 때 `CALMAR_MDD_ZERO_SUBSTITUTE` + CAGR, 아니면 0.0)
- 승률: `profitable_trades / total_trades * 100`
