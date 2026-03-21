# Implementation Plan: 포트폴리오 리밸런싱 V2

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

**작성일**: 2026-03-20 00:00
**마지막 업데이트**: 2026-03-21 00:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] **리밸런싱 로직 개선**: 월 첫 거래일(10% 임계값) + 매일(20% 임계값) 이중 트리거 체계로 전환
- [ ] **부분 매도/매수 도입**: 리밸런싱 시 전량 매도 → 편차만큼 부분 매도로 수정
- [ ] **전략 독립성 강화**: `always_invested` 제거 → `strategy_type` 필드로 명확화. 단독 실행과 포트폴리오 실행이 동일 소스 파일 참조
- [ ] **Split 백테스트 제거**: `run_split_backtest.py`, `app_split_backtest.py`, `split_strategy.py` 삭제
- [ ] **버퍼존 매도 후 비중 보존**: 매도 시그널로 전량 매도된 자산의 현금은 해당 목표 비중으로 보존되고, 잔존 자산의 편차 발생 시 리밸런싱이 정상 동작

---

## 2) 비목표(Non-Goals)

- `run_single_backtest.py`의 전략 실행 로직 변경 없음 (단독 실행 전량 매수/매도 유지)
- `run_buffer_strategy()` 함수 자체 변경 없음 (단독 백테스트의 핵심 엔진)
- 포트폴리오 실험 설정(A/B/C/D/E/F/G/H 시리즈 구성 비중) 변경 없음
- 대시보드(`app_portfolio_backtest.py`) 주요 기능 변경 없음 (params_json 키 변경에 따른 소규모 수정만 허용)
- 워크포워드, 그리드서치 로직 변경 없음

---

## 3) 배경/맥락(Context)

### 현재 문제점

#### 문제 1: 리밸런싱 트리거가 너무 소극적
현재 조건: "월 첫 거래일 AND 편차 > 20%"
→ 장기 추세 자산이 40%+ 벌어져도 다음 달 초까지 방치 가능

#### 문제 2: 리밸런싱 시 전량 매도 버그 (중요)
`_execute_rebalancing`이 초과 자산에 대해 "전량 매도" pending_order를 생성하지만,
재매수 pending_order는 생성하지 않습니다.

```
GLD 50% (목표 40%) → 전량 매도 → GLD 0% → 새 매수 신호 전까지 보유 없음
```

즉, 현재 코드의 리밸런싱은 **비중 복원이 아닌 강제 청산**으로 동작합니다.
부분 매도(편차분만 매도)로 수정해야 진정한 리밸런싱이 됩니다.

#### 문제 3: `always_invested` 개념이 불명확
Boolean 플래그(`always_invested=True`)로 B&H 동작을 표현하여
포트폴리오 설정의 의도를 읽기 어렵습니다.

#### 문제 4: 버퍼존 매도 후 비중 보존 보장 필요
QQQ가 매도 시그널로 청산되면 40%가 현금으로 보존되어야 합니다.
현재는 다른 자산의 가격 변동으로 편차가 발생해도 "월 첫날 + 20% 초과"가 아니면
리밸런싱이 발동되지 않습니다.
→ 이중 트리거(매일 20%)가 도입되면 자연스럽게 해결됩니다.

### 아키텍처 설계 방향: 단독 실행 vs 포트폴리오 실행의 공유 구조

```
공유 파일 (변경 없음)
────────────────────────────────────────────────────────
buffer_zone_helpers.py
  - _compute_bands()          ← 밴드 계산
  - _detect_buy_signal()      ← 매수 신호 감지
  - _detect_sell_signal()     ← 매도 신호 감지
  - HoldState                 ← hold_days 상태머신 타입
  - run_buffer_strategy()     ← 단독 백테스트용 (전량 매수/매도)

buy_and_hold.py
  - run_buy_and_hold()        ← 단독 B&H 백테스트용

────────────────────────────────────────────────────────
단독 실행 계층                   포트폴리오 실행 계층
────────────────────────────────────────────────────────
run_single_backtest.py          run_portfolio_backtest.py
  ↓ (변경 없음)                    ↓
buffer_zone.create_runner()     portfolio_strategy.run_portfolio_backtest()
  ↓                                ↓
run_buffer_strategy()           ← 신호 감지: _detect_buy/sell_signal (공유)
  (전량 매수/매도)                  ← 실행: 포트폴리오 자체 코드 (부분 매수/매도)
                                  ← 전략 타입: slot.strategy_type 분기
                                    "buffer_zone" → 버퍼존 신호 사용
                                    "buy_and_hold" → 항상 투자 상태 유지
```

**핵심 원칙**: 신호 생성 로직은 `buffer_zone_helpers.py`를 공유. 실행(체결) 로직은 단독/포트폴리오가 분리.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)

---

## 4) 완료 조건(Definition of Done)

- [x] 이중 트리거 리밸런싱 동작 (월 10% + 매일 20%)
- [x] 부분 매도 동작 (리밸런싱 시 편차분만 매도, 신호 기반 매도는 전량 유지)
- [x] `strategy_type` 필드로 B&H / 버퍼존 구분 명확화
- [x] `always_invested` 필드 완전 제거
- [x] Split 관련 파일 4개 삭제
- [x] 버퍼존 매도 후 현금 비중 보존 + 타 자산 편차 리밸런싱 동작
- [x] 회귀/신규 테스트 추가 및 기존 테스트 수정
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=375, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 관련 CLAUDE.md 문서 업데이트
- [x] plan 체크박스 최신화

---

## 5) 변경 범위(Scope)

### 변경 대상 파일

#### 핵심 로직 (수정)

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/portfolio_types.py` | `AssetSlotConfig.always_invested` → `strategy_type` 필드 |
| `src/qbt/backtest/portfolio_strategy.py` | 이중 트리거, 부분 매도, strategy_type 분기, 상수 변경 |
| `src/qbt/backtest/portfolio_configs.py` | 임계값 상수 변경, G2/G3/G4 설정 수정 |

#### 삭제

| 파일 | 사유 |
|------|------|
| `src/qbt/backtest/split_strategy.py` | Split 백테스트 제거 |
| `scripts/backtest/run_split_backtest.py` | Split 백테스트 제거 |
| `scripts/backtest/app_split_backtest.py` | Split 백테스트 제거 |
| `tests/test_split_strategy.py` | Split 백테스트 제거 |

#### 테스트 (수정/추가)

| 파일 | 변경 내용 |
|------|----------|
| `tests/test_portfolio_strategy.py` | `always_invested` → `strategy_type` 리네이밍, 부분 매도 테스트 추가, 이중 트리거 테스트 추가 |
| `tests/test_portfolio_configs.py` | `strategy_type` 필드 반영 |

#### 문서 (수정)

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/CLAUDE.md` | split_strategy 섹션 제거, portfolio_strategy 업데이트 |
| `scripts/CLAUDE.md` | 분할 매수매도 관련 내용 제거 |
| `tests/CLAUDE.md` | `test_split_strategy.py` 항목 제거 |

#### 소규모 수정 (파급 영향)

| 파일 | 변경 내용 |
|------|----------|
| `scripts/backtest/app_portfolio_backtest.py` | `params_json`의 `always_invested` → `strategy_type` 키 변경 반영 |

### 데이터/결과 영향

- **기존 결과 파일 무효화**: `storage/results/portfolio/` 하위 모든 CSV/JSON 재생성 필요
  - 이유: 리밸런싱 빈도 증가(매일 체크) + 부분 매도로 동작이 근본적으로 달라짐
- **출력 스키마 변경**: `summary.json`의 `params_json.assets[].always_invested` → `strategy_type`
- **trades.csv 변경**: 부분 매도 시 `shares` 컬럼 값이 달라짐

---

## 6) 단계별 계획(Phases)

### Phase 0 — 핵심 인바리언트 테스트 먼저 고정 (레드)

> 부분 매도, 이중 트리거, strategy_type은 기존 계약을 변경하는 핵심 변경이므로 Phase 0 적용

**작업 내용**:

- [x] `tests/test_portfolio_strategy.py` — 부분 매도 인바리언트 테스트 추가 (레드 허용)
  - 리밸런싱 후 초과 자산의 `position > 0` 유지 (전량 매도 금지)
  - `rebalance_sell_amount` 저장 정확성 (excess_value 그대로 저장)
  - 체결 시 `shares = int(rebalance_sell_amount / execution_price)` 내림 처리
  - 체결 순서: 전 자산 매도 완료 후 매수 진행 검증
  - 신호 기반 매도는 여전히 전량 매도
- [x] `tests/test_portfolio_strategy.py` — 이중 트리거 테스트 추가 (레드 허용)
  - 월 첫날 10% 초과 시 트리거 (기존 20%에서 변경)
  - 월 중간 20% 초과 시 트리거 (신규)
  - 편차 < 10%이면 월 첫날에도 패스
  - 편차 10~20% 구간이면 월 첫날에만 트리거, 월 중간에는 패스
- [x] `tests/test_portfolio_strategy.py` — `always_invested` 테스트를 `strategy_type` 기반으로 수정 (레드 허용)
  - `strategy_type="buy_and_hold"` 자산의 즉시 매수 동작
  - `strategy_type="buy_and_hold"` 자산의 매도 신호 무시 동작
  - `strategy_type="buffer_zone"` (기본값) 동작 불변 확인

---

### Phase 1 — portfolio_types.py 수정

**작업 내용**:

- [x] `AssetSlotConfig.always_invested: bool = False` 제거
- [x] `AssetSlotConfig.strategy_type: Literal["buffer_zone", "buy_and_hold"] = "buffer_zone"` 추가
- [x] `PortfolioConfig` docstring 업데이트

**검증**: `test_portfolio_configs.py` 통과 확인

---

### Phase 2 — portfolio_configs.py 수정

**작업 내용**:

- [x] `_DEFAULT_REBALANCE_THRESHOLD = 0.20` → `0.10` 변경
- [x] G2: `gld` 슬롯 `always_invested=True` → `strategy_type="buy_and_hold"` 변경
- [x] G3: `tlt` 슬롯 `always_invested=True` → `strategy_type="buy_and_hold"` 변경
- [x] G4: `gld`, `tlt` 슬롯 동일 변경

---

### Phase 3 — portfolio_strategy.py 핵심 수정

**작업 내용**:

#### 3-1. 상수 및 타입 변경

- [x] `REBALANCE_THRESHOLD_RATE: float = 0.20` → `MONTHLY_REBALANCE_THRESHOLD_RATE: float = 0.10` 변경
- [x] `DAILY_REBALANCE_THRESHOLD_RATE: float = 0.20` 상수 추가
- [x] `_PortfolioPendingOrder` 데이터클래스에 `rebalance_sell_amount: float = 0.0` 필드 추가
  - `0.0` = 전량 매도 (신호 기반 매도 기본값)
  - `> 0.0` = 부분 매도 (리밸런싱 기반 매도, 대금 기준)

#### 3-2. `_check_rebalancing_needed` 함수 수정

- [x] `threshold` 파라미터 추가: `threshold: float | None = None`
  - `None`이면 `config.rebalance_threshold_rate` 사용 (기존 동작)
  - 값이 있으면 해당 임계값으로 체크
- [x] `config.rebalance_threshold_rate` 참조를 `threshold or config.rebalance_threshold_rate`로 변경

#### 3-3. `_execute_rebalancing` 함수 수정 (부분 매도 핵심)

현재 로직:
```
초과 자산 → 전량 매도 pending_order 생성
미달 자산 → 목표금액 매수 pending_order 생성
```

변경 후 로직:
```
초과 자산 → excess_value(대금)를 rebalance_sell_amount로 저장, pending_order 생성
            excess_value = equity_vals[asset_id] - target_amount
미달 자산 → 목표금액 매수 pending_order 생성 (변경 없음)
```

수량 계산은 체결 시점(다음날 시가)에 수행:
```
shares_to_sell = int(rebalance_sell_amount / (open_price * (1 - SLIPPAGE_RATE)))
```

- [x] 함수 시그니처에서 `asset_closes` 파라미터 **불필요** (수량을 사전 계산하지 않음)
- [x] 초과 자산 처리 로직 수정: `excess_value = equity_vals[asset_id] - target_amount`
  - `excess_value > 0`인 경우만 pending_order 생성
- [x] `_PortfolioPendingOrder(order_type="sell", ..., rebalance_sell_amount=excess_value)` 생성

#### 3-4. 메인 루프 6-1 (pending_order 체결) 수정 — 2패스 방식으로 변경

리밸런싱 매도 대금이 매수 자본으로 쓰이므로, 매도를 먼저 전부 처리한 뒤 매수를 처리한다.

- [x] 루프 6-1을 **2패스**로 분리:
  ```
  # 1패스: 전 자산 sell pending_order 체결
  for asset_id, state in asset_states.items():
      if state.pending_order?.order_type == "sell": 처리

  # 2패스: 전 자산 buy pending_order 체결
  for asset_id, state in asset_states.items():
      if state.pending_order?.order_type == "buy": 처리
  ```
- [x] "sell" 체결 시 `rebalance_sell_amount` 분기 추가:
  ```
  if order.rebalance_sell_amount > 0.0:   # 부분 매도 (리밸런싱, 대금 기준)
      execution_price = open_price * (1 - SLIPPAGE_RATE)
      shares_to_sell = int(order.rebalance_sell_amount / execution_price)  # 내림
      shares_sold = min(shares_to_sell, state.position)
  else:                                    # 전량 매도 (신호 기반)
      shares_sold = state.position
  ```
- [x] `state.position -= shares_sold` (부분 매도 후 포지션 감소)
- [x] `trade_record["shares"] = shares_sold`로 수정 (실제 매도량)
- [x] 부분 매도 시 `state.position > 0` 이므로 `entry_date`, `entry_price` 초기화 금지

#### 3-5. 메인 루프 6-3 (시그널 판정) 수정

- [x] `if slot.always_invested:` → `if slot.strategy_type == "buy_and_hold":`으로 변경
- [x] `asset_states` 초기화: `"buy" if slot.always_invested else "sell"` → `"buy" if slot.strategy_type == "buy_and_hold" else "sell"`
- [x] 초기 pending_order 생성: `if slot.always_invested:` → `if slot.strategy_type == "buy_and_hold":`

#### 3-6. 메인 루프 6-4 (리밸런싱 판정) 수정

현재:
```python
if _is_first_trading_day_of_month(trade_dates, i):
    if _check_rebalancing_needed(...):
        _execute_rebalancing(...)
```

변경 후:
```python
is_month_start = _is_first_trading_day_of_month(trade_dates, i)
if is_month_start:
    # 월 첫날: 10% 임계값 (MONTHLY_REBALANCE_THRESHOLD_RATE)
    if _check_rebalancing_needed(..., threshold=MONTHLY_REBALANCE_THRESHOLD_RATE):
        _execute_rebalancing(..., asset_closes=asset_closes_map)
        rebalanced_today = True
elif _check_rebalancing_needed(..., threshold=DAILY_REBALANCE_THRESHOLD_RATE):
    # 매일: 20% 임계값 (DAILY_REBALANCE_THRESHOLD_RATE)
    _execute_rebalancing(..., asset_closes=asset_closes_map)
    rebalanced_today = True
```

- [x] 6-4 로직 수정 적용
- [x] `_execute_rebalancing` 호출 시 `asset_closes_map` **불필요** (수량 사전 계산 제거됨)

---

### Phase 4 — Split 관련 파일 삭제

**작업 내용**:

- [x] `src/qbt/backtest/split_strategy.py` 삭제
- [x] `scripts/backtest/run_split_backtest.py` 삭제
- [x] `scripts/backtest/app_split_backtest.py` 삭제
- [x] `tests/test_split_strategy.py` 삭제

---

### Phase 5 — 테스트 수정/추가 (그린 복원)

**작업 내용**:

- [x] `tests/test_portfolio_strategy.py` — Phase 0에서 추가한 테스트가 통과하도록 확인
- [x] `tests/test_portfolio_strategy.py` — `TestAlwaysInvested` 클래스 전면 수정 (`TestStrategyTypeBehavior`로 변경)
  - `always_invested=True/False` → `strategy_type="buy_and_hold"/"buffer_zone"`으로 변경
  - 테스트 로직 자체는 동일, 필드명만 변경
- [x] `tests/test_portfolio_strategy.py` — 부분 매도 시나리오 테스트 보강
  - 리밸런싱 후 초과 자산의 `qqq_value > 0` 검증
  - 신호 기반 매도는 여전히 `qqq_value == 0` 검증
- [x] `tests/test_portfolio_configs.py` — `strategy_type` 필드 참조 없음 (변경 불필요)

---

### Phase 6 — app_portfolio_backtest.py 소규모 수정

**작업 내용**:

- [x] `params_json.assets[].always_invested` 키를 참조하는 코드가 있으면 `strategy_type`으로 변경
  - 확인 결과: `always_invested` 표시 없음 → 변경 불필요

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - `portfolio_strategy.py` 섹션: 상수명 변경, `strategy_type` 필드, 이중 트리거 설명 반영
  - `split_strategy.py` 섹션 전체 제거
- [x] `scripts/CLAUDE.md` 업데이트
  - 분할 매수매도 관련 내용 전체 제거 (`run_split_backtest.py`, `app_split_backtest.py`)
- [x] `tests/CLAUDE.md` 업데이트
  - `test_split_strategy.py` 항목 제거
  - `test_portfolio_strategy.py` 항목 추가 (strategy_type 관련)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=375, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 리밸런싱 V2 — 이중 트리거 + 부분 매도 + strategy_type 도입
2. 백테스트 / 포트폴리오 리밸런싱 버그 수정 및 전략 독립성 강화
3. 백테스트 / 포트폴리오 리밸런싱 정책 변경 + Split 백테스트 제거
4. 백테스트 / 포트폴리오 리밸런싱 V2 — 부분 매도 구현 + always_invested 제거
5. 백테스트 / 포트폴리오 엔진 리팩토링 — 이중 트리거·부분 매도·strategy_type

---

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| 부분 매도 후 entry_price 추적 복잡성 | 거래 기록 PnL 오차 | 평균 단가 고정 방식 사용(단순화 허용). 테스트로 명시적 검증 |
| 이중 트리거로 거래 빈도 급증 | 비용 증가, 성과 변동 | 임계값 20%(매일)는 의도적으로 높게 설정하여 과잉 리밸런싱 방지 |
| 2패스 실행으로 루프 구조 변경 | 기존 단일 루프 테스트 깨짐 | Phase 0에서 체결 순서 테스트 먼저 추가 후 Phase 3에서 구현 |
| 기존 결과 파일 무효화 | 대시보드에서 오래된 결과 표시 | 사용자가 `run_portfolio_backtest.py` 재실행 필요 (안내 필요) |
| Split 삭제로 테스트 수 감소 | 커버리지 저하 | 포트폴리오 테스트 강화로 상쇄 |

---

## 8) 메모(Notes)

### 핵심 설계 결정

#### 결정 1: 부분 매도 방식 — 대금(금액) 기준

신호일 종가로 수량을 사전 계산하면, 체결일(다음날 시가)의 가격 변동에 의해 실제 대금이 달라진다.

**채택 방식**: `rebalance_sell_amount = excess_value` (대금 기준으로 pending_order에 저장)
체결 시점에 `shares_to_sell = int(rebalance_sell_amount / execution_price)` 계산 (내림 처리).

- execution_price = open_price × (1 − SLIPPAGE_RATE)
- 실제 매도 대금 ≈ `rebalance_sell_amount` (내림으로 인해 소량 미달 허용)
- 체결 순서: 전 자산 매도 완료 후 매수 진행 (2패스)

#### 결정 2: 신호 기반 매도는 여전히 전량 매도 유지
버퍼존 전략의 "하단 밴드 하향 돌파 → 전량 청산" 정책은 불변.
부분 매도는 오직 리밸런싱에만 적용.

#### 결정 3: 매도 후 현금 보존은 아키텍처적으로 보장됨
QQQ가 매도 시그널로 전량 청산 → `signal_state = "sell"`, 현금은 `shared_cash`에 유지.
`_check_rebalancing_needed`는 `signal_state != "buy"` 자산을 건너뜀.
→ QQQ의 현금은 리밸런싱에서 제외 = 자동 보존.
다른 자산(GLD, SPY)의 편차 검사 시 `total_equity`에는 QQQ 현금이 포함됨 → 목표 비중 계산에 올바르게 반영.

#### 결정 4: 이중 트리거 임계값 설정
- 월 첫 거래일: 10% (더 민감, 정기 리밸런싱 목적)
- 매일: 20% (긴급, 급격한 편차만 대응)
- 이 구간 차이(10%~20%)는 의도적: 월 중간에 10~19% 편차는 "다음 월 첫날까지 대기" 허용

#### 결정 5: `strategy_type` 필드명 및 타입
`Literal["buffer_zone", "buy_and_hold"]`로 제한.
추후 다른 전략 유형 추가 시 확장 가능.

### 진행 로그 (KST)

- 2026-03-20 00:00: 계획서 초안 작성
- 2026-03-20 00:00: Q1/Q2 검토 반영 — 대금 기준 부분 매도(rebalance_sell_amount), 2패스 체결, asset_closes 파라미터 제거
- 2026-03-21 00:00: 전 Phase 완료 — validate passed=375, failed=0, skipped=0

---
