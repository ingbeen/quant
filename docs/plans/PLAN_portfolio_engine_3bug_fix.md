# Implementation Plan: 포트폴리오 엔진 3대 버그 수정

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

**작성일**: 2026-03-25 00:00
**마지막 업데이트**: 2026-03-25 13:40
**관련 범위**: backtest (engines/portfolio_engine.py), tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 문제 1: 리밸런싱 추가매수(top-up buy) 미체결 버그 수정 — position > 0인 자산에 대한 리밸런싱 매수도 실제로 체결되어야 한다
- [x] 문제 2: signal cache key 충돌 위험 제거 — 동일 signal_data_path를 공유하는 슬롯이 서로 다른 MA 파라미터를 사용해도 각자 올바른 계산 결과를 사용해야 한다
- [x] 문제 3: `rebalanced` 컬럼 의미 정확화 — "pending_order 생성일"이 아닌 "실제 체결 완료일"에 True가 기록되어야 한다

## 2) 비목표(Non-Goals)

- 싱글 백테스트 엔진(`backtest_engine.py`) 수정 — 이번 작업은 포트폴리오 엔진만 대상
- 리밸런싱 로직 전면 재설계 — 기존 이중 트리거 구조(월 첫날 10% / 매일 20%)는 유지
- equity_df 컬럼 추가 또는 구조 변경 — `rebalanced` 컬럼명 유지, 의미만 재정의
- 포트폴리오 대시보드(`app_portfolio_backtest.py`) 수정 — `rebalanced` 컬럼명이 유지되므로 영향 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1 — 리밸런싱 추가매수 미체결**

`portfolio_engine.py:649`의 buy pending_order 체결 루프에 `if state.position == 0:` 조건이 있다.
리밸런싱으로 생성된 매수 pending_order도 이 조건을 통과해야만 체결된다.
결과적으로 이미 보유 중인 자산의 추가매수는 전혀 체결되지 않고, 리밸런싱 시 과소 자산은 그대로 남으며 현금만 쌓인다.

추가 결정 사항 (사용자 확인): 리밸런싱 추가매수 후 entry_price는 가중평균으로 업데이트한다. entry_date는 최초 진입일을 유지한다.

**문제 2 — signal cache key 충돌**

`run_portfolio_backtest`와 `compute_portfolio_effective_start_date` 모두에서 signal_data_path 문자열만으로 캐시 키를 생성한다 (`signal_key = str(slot.signal_data_path)`).
같은 경로를 공유하는 두 슬롯이 서로 다른 ma_window 또는 ma_type을 사용할 경우, 먼저 계산된 슬롯의 결과가 뒤 슬롯에 그대로 재사용된다.
현재 PORTFOLIO_CONFIGS에서는 QQQ/TQQQ가 동일 signal_data_path와 동일 MA 파라미터(ma_window=200)를 공유하므로 실제 발생은 없으나, 잠재적 정확성 위험이다.

**문제 3 — `rebalanced` 의미 왜곡**

현재 `rebalanced_today = True`는 `_execute_rebalancing()` 호출 직후(7-4 단계, pending_order 생성일인 i일)에 기록된다.
실제 체결은 다음 날(i+1일) 시가에 이루어지므로, equity_df의 `rebalanced=True`인 날과 실제 체결 완료일이 1일 어긋난다.
문제 1과 결합 시, 추가매수가 미체결되어도 `rebalanced=True`로 기록되어 결과를 오해할 수 있다.

추가 결정 사항 (사용자 확인): 기존 `rebalanced` 컬럼명 유지, 의미를 "실제 체결 완료일"로 재정의한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙 (체결 타이밍, Pending Order 정책, equity 정의 등)
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 부동소수점 비교, 파일 격리 등)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] 문제 1: position > 0 상태에서 리밸런싱 buy pending_order가 실제로 체결됨을 테스트로 검증
- [x] 문제 1: 리밸런싱 추가매수 후 entry_price가 가중평균으로 업데이트됨을 테스트로 검증
- [x] 문제 1: 과소 비중 자산이 리밸런싱 후 실제로 비중이 회복됨을 테스트로 검증
- [x] 문제 2: 동일 signal_data_path + 다른 ma_window 슬롯이 각자 올바른 MA 컬럼을 사용함을 테스트로 검증
- [x] 문제 3: `rebalanced=True`가 실제 체결 완료일에 기록됨을 테스트로 검증
- [x] 문제 3: 리밸런싱 pending 생성일(체결 전날)에는 `rebalanced=False`임을 테스트로 검증
- [x] 초기 진입(첫 buy)이 리밸런싱으로 잘못 기록되지 않음을 테스트로 검증
- [x] 기존 테스트 수정: `test_partial_sell_keeps_position` — 의미 변경에 맞게 검증 로직 업데이트
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=394, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/engines/portfolio_engine.py` (핵심 수정)
- `tests/test_portfolio_strategy.py` (테스트 추가 + 기존 테스트 수정)

### 데이터/결과 영향

- equity_df의 `rebalanced` 컬럼 값이 기존 대비 최대 1일 늦게 True가 기록됨 (pending 생성일 → 체결 완료일)
- trades_df의 entry_price가 리밸런싱 추가매수 시 가중평균으로 업데이트됨 (PnL 계산 영향)
- 기존에 저장된 CSV 결과 파일은 재생성 필요 (로직 변경으로 수치가 달라질 수 있음)

## 6) 단계별 계획(Phases)

### Phase 0 — 버그 재현 테스트 및 정책 고정 (레드)

**작업 내용 (tests/test_portfolio_strategy.py에 추가)**:

- [x] `TestRebalancingTopUpBuy` 클래스 추가
  - `test_top_up_buy_executes_when_position_exists`: position > 0인 자산에 리밸런싱 buy pending_order 생성 후 체결 루프를 통과하면 position이 실제로 증가하는지 검증 (현재는 체결 안 됨 → RED)
  - `test_top_up_buy_updates_entry_price_weighted_avg`: 리밸런싱 추가매수 후 entry_price가 가중평균으로 업데이트되는지 검증

- [x] `TestWeightRecoveryAfterRebalancing` 클래스 추가
  - `test_underweight_asset_increases_after_rebalancing`: 과소 비중(position > 0) 자산이 리밸런싱 후 실제로 비중이 증가하는지 end-to-end 검증 (현재는 매도만 발생 → RED)

- [x] `TestCacheKeyWithDifferentMAParams` 클래스 추가
  - `test_same_path_different_ma_window_no_collision`: 동일 signal_data_path를 공유하는 두 슬롯이 ma_window=5와 ma_window=10을 각각 사용할 때 예외 없이 각자 올바른 MA 컬럼을 사용하는지 검증 (현재는 캐시 충돌 → RED)

- [x] `TestRebalancedColumnMeaning` 클래스 추가
  - `test_rebalanced_true_on_execution_day_not_pending_day`: 리밸런싱 pending 생성일(i일)에는 `rebalanced=False`이고, 실제 체결 완료일(i+1일)에 `rebalanced=True`가 기록됨을 검증 (현재는 i일에 True → RED)
  - `test_initial_entry_not_marked_as_rebalanced`: 첫 매수 체결 완료일에 `rebalanced=False`임을 검증

**Validation**:
- Phase 0에서는 새로 추가된 테스트 중 RED(실패)인 항목이 존재해야 정상 (레드 허용)
- 기존 테스트는 모두 통과하는 상태 유지

---

### Phase 1 — 버그 수정 (그린 유지)

**작업 내용 (engines/portfolio_engine.py)**:

#### 문제 1 수정

- [x] `_PortfolioPendingOrder` 데이터클래스에 `is_rebalance: bool = False` 필드 추가
  - 리밸런싱으로 생성된 매수 주문임을 표시하는 플래그
  - 매도 주문은 `rebalance_sell_amount > 0.0`으로 이미 구분 가능 (변경 없음)

- [x] `_execute_rebalancing` 함수: buy pending_order 생성 시 `is_rebalance=True` 설정
  ```python
  asset_states[asset_id].pending_order = _PortfolioPendingOrder(
      order_type="buy",
      signal_date=current_date,
      capital=capital,
      is_rebalance=True,  # 추가
  )
  ```

- [x] 2패스 buy 체결 로직 수정: `if state.position == 0:` → `if state.position == 0 or order.is_rebalance:`

- [x] 리밸런싱 추가매수(position > 0) 체결 후 처리:
  - entry_price 가중평균 업데이트: `(기존_entry_price × 기존_수량 + 매수가 × 신규_수량) / (기존_수량 + 신규_수량)`
  - entry_date는 최초 진입일 유지 (변경 없음)
  - 초기 진입(position == 0)은 기존과 동일하게 entry_price/entry_date 모두 기록

#### 문제 2 수정

- [x] `run_portfolio_backtest` 함수의 캐시 키 확장:
  - 기존: `signal_key = str(slot.signal_data_path)`
  - 수정: `signal_key = f"{slot.signal_data_path}::{slot.strategy_type}::{slot.ma_window}::{slot.ma_type}"`

- [x] `compute_portfolio_effective_start_date` 함수의 캐시 키도 동일하게 확장

#### 문제 3 수정

- [x] 7-4 단계(`_execute_rebalancing` 호출 후)에서 `rebalanced_today = True` 제거

- [x] 7-1 체결 루프(1패스 sell)에서 리밸런싱 매도 체결 완료 시 `rebalanced_today = True` 설정:
  - 조건: `order.rebalance_sell_amount > 0.0 and shares_sold > 0`

- [x] 7-1 체결 루프(2패스 buy)에서 리밸런싱 매수 체결 완료 시 `rebalanced_today = True` 설정:
  - 조건: `order.is_rebalance and shares > 0`

**기존 테스트 수정 (tests/test_portfolio_strategy.py)**:

- [x] `TestPartialSellKeepsPosition::test_partial_sell_keeps_position` 수정 (line 1342)
  - 기존 검증: `rebalanced=True`인 날의 `+1일`에 qqq_value > 0 체크
  - 수정 후 검증: `rebalanced=True`인 날 자체가 체결 완료일이므로, 같은 날 qqq_value > 0 체크 (부분 매도로 포지션 유지)

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] plan 상태 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=394, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 엔진 3대 버그 수정 — 리밸런싱 추가매수 체결 + 캐시 키 확장 + rebalanced 의미 정확화
2. 백테스트 / 포트폴리오 엔진 수정 — top-up buy 미체결 버그 + signal 캐시 충돌 + rebalanced 체결일 기준 수정
3. 백테스트 / 포트폴리오 리밸런싱 정확성 개선 — 추가매수 체결 + 가중평균 단가 + 캐시 키 충돌 방지
4. 백테스트 / 포트폴리오 엔진 버그 수정 — rebalanced 의미 재정의(체결 완료일) + 추가매수 체결 + 캐시 키
5. 백테스트 / 포트폴리오 엔진 정합성 수정 — 리밸런싱 동작이 설계 의도와 일치하도록 3가지 핵심 버그 제거

## 7) 리스크(Risks)

- 문제 1 수정 후 리밸런싱 추가매수가 실제로 체결되면, 이전과 백테스트 수치(equity, CAGR, MDD)가 달라진다. 기존 저장된 결과 CSV는 재생성 필요.
- `rebalanced` 컬럼 의미가 1일 이동하면 대시보드 마커 위치가 달라진다. 컬럼명이 유지되므로 코드 변경은 없지만 시각적으로 차이가 난다.
- `is_rebalance` 플래그 추가로 인해 기존 `_PortfolioPendingOrder` 사용처를 모두 확인해야 한다 (default=False이므로 기존 호환성은 유지됨).

## 8) 메모(Notes)

- 사용자 결정 사항 (2026-03-25):
  - 질문 1(entry_price 처리): B안 — 가중평균으로 entry_price 업데이트, entry_date는 최초 유지
  - 질문 2(rebalanced 컬럼): B안 — 컬럼명 유지, 의미를 "실제 체결 완료일"로 재정의
- 현재 PORTFOLIO_CONFIGS에서 문제 2(캐시 키 충돌)는 실제 발생하지 않으나, 잠재적 정확성 위험으로 예방적 수정 포함
- `buy_and_hold` 전략의 캐시 키는 ma_window=200, ma_type="ema" 기본값이 사용되지 않으므로 캐시 키 확장 시에도 문제 없음 (strategy_type이 포함되므로 경로가 달라 충돌 불가)

### 진행 로그 (KST)

- 2026-03-25 00:00: 계획서 작성 완료, Phase 0 시작 예정
- 2026-03-25 13:40: 전체 작업 완료 — Phase 0 (RED 테스트 추가), Phase 1 (버그 수정), 최종 검증 통과 (passed=394)
