# Implementation Plan: 포트폴리오 엔진 — OrderIntent 기반 전면 리팩토링

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

**작성일**: 2026-03-26 00:00
**마지막 업데이트**: 2026-03-26 14:57
**관련 범위**: backtest (engines/portfolio_engine.py)
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

- [x] `pending_order` 완전 제거 — `OrderIntent` 기반 주문 모델로 교체
- [x] Signal → ProjectedPortfolio → Rebalance → Execution 흐름 확립
- [x] signal과 rebalance 충돌 해소 (`merge_intents` 우선순위 규칙)
- [x] 매도 signal이 planning에 반영되지 않던 문제 해소 (`compute_projected_portfolio`)
- [x] 출력 포맷(CSV/JSON) 동일 유지

## 2) 비목표(Non-Goals)

- 출력 스키마(equity.csv, trades.csv, summary.json) 변경 없음
- 리밸런싱 규칙(월초 10% / 매일 20%) 변경 없음
- 체결 기준(open 가격) 변경 없음
- 단일 자산 백테스트 엔진(`backtest_engine.py`) 변경 없음
- 전략 인터페이스(`SignalStrategy` Protocol) 변경 없음
- inactive 자산 처리(cash 유지, 재분배 없음) 변경 없음

## 3) 배경/맥락(Context)

### 현재 문제점

**문제 A — 주문 충돌 (pending_order 기반 설계)**

같은 자산에 signal sell과 rebalance sell이 분리 생성될 수 있다. 현재 구현은 `pending_order is None` 체크로 선착순 처리하여 한쪽이 누락된다. signal buy + rebalance buy도 동일한 문제가 발생한다. 자산당 주문이 1개여야 한다는 계약이 없다.

**문제 B — projected state 왜곡 (planning 기준 오류)**

signal sell이 발생했어도 해당 자산은 당일까지 position > 0 상태이다. 현재 rebalancing은 "현재 상태(signal 미반영)"를 기준으로 total_equity를 산정하므로, 내일 청산될 자산의 평가액이 분모에 포함된다. 이로 인해 다른 active 자산의 target_amount가 부풀려진다.

**두 문제의 관계 — 왜 C(A+B 모두)인가**

- A만 해결 시: 주문 충돌은 사라지지만 planning 기준이 여전히 왜곡됨
- B만 해결 시: planning은 정확해지지만 최종 주문 통합 규칙 없이 충돌 재발 가능
- 두 문제 모두 해결이 필요하다

### 확정된 설계 결정

| 항목 | 결정 |
|------|------|
| position state | shares (int) — 변경 없음 |
| planning/rebalance/projected | amount (float) — 명확히 분리 |
| signal_state 관리 | 엔진 (`_AssetState`) 관리 유지 |
| 전략 역할 | "판단"만 (check_buy/check_sell 결과 반환) |

### OrderIntent 4종류

| intent_type | 의미 |
|-------------|------|
| `EXIT_ALL` | 보유 전량 청산 (signal sell) |
| `ENTER_TO_TARGET` | 신규 진입하여 target_amount 도달 (signal buy) |
| `REDUCE_TO_TARGET` | 초과분 매도하여 target_amount 도달 (rebalance) |
| `INCREASE_TO_TARGET` | 미달분 매수하여 target_amount 도달 (rebalance) |

### merge_intents 우선순위 규칙

| signal intent | rebalance intent | merge 결과 |
|---------------|-----------------|-----------|
| EXIT_ALL | (any) | EXIT_ALL |
| ENTER_TO_TARGET | INCREASE_TO_TARGET | ENTER_TO_TARGET (rebalance target 사용) |
| (없음) | REDUCE_TO_TARGET | REDUCE_TO_TARGET |
| (없음) | INCREASE_TO_TARGET | INCREASE_TO_TARGET |
| EXIT_ALL + REDUCE → 불가 | — | compute_projected_portfolio가 선행되므로 발생 안 함 |

### 새로운 메인 루프 흐름

```
for i in range(0, n):
    Step A: SELL 체결 (전일 merged intents 기반, i일 open 가격)
    Step B: BUY 체결 (전일 merged intents 기반, i일 open 가격)
    Step C: Equity 계산 (체결 후 종가 기준)
    Step D: Signal 판정 → ProjectedPortfolio → Rebalance → MergeIntents
        D.1 generate_signal_intents (strategy 호출)
        D.2 compute_projected_portfolio (signal intents 반영)
        D.3 build_rebalance_intents (projected 기준, threshold 체크 포함)
        D.4 merge_intents (signal + rebalance → 자산당 1개)
        D.5 signal_state 업데이트
        D.6 next_day_intents 저장
    Step E: Equity row 기록
```

`next_day_intents: dict[str, OrderIntent]` 가 `pending_order` 를 대체한다.

### 영향받는 규칙 (반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

---

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `OrderIntent`, `_ProjectedPortfolio` 모델 구현 완료
- [x] `_generate_signal_intents`, `_compute_projected_portfolio`, `_build_rebalance_intents`, `_merge_intents` 구현 완료
- [x] 메인 루프 전면 재작성 (pending_order 완전 제거)
- [x] `_PortfolioPendingOrder` 삭제, `_AssetState.pending_order` 필드 삭제
- [x] 기존 tests 중 제거된 심볼 import 수정 완료
- [x] 새로운 계약 테스트 통과 (generate_signal_intents, compute_projected_portfolio, build_rebalance_intents, merge_intents)
- [x] 기존 통합 테스트 (`run_portfolio_backtest`, `compute_portfolio_effective_start_date`) 통과
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=402, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 관련 CLAUDE.md 문서 업데이트 (portfolio engine 설명 반영)
- [x] plan 체크박스 최신화

---

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/engines/portfolio_engine.py` — 핵심 리팩토링 대상
- `tests/test_portfolio_strategy.py` — 기존 테스트 수정 + 새 계약 테스트 추가
- `src/qbt/backtest/CLAUDE.md` — portfolio engine 섹션 설명 업데이트
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 파일 스키마 변경 없음 (equity.csv, trades.csv, summary.json)
- 계산 결과는 의미상 동일해야 하나, pending_order 설계 버그 수정으로 일부 수치 변동 가능 (이는 버그 수정의 결과이며 의도된 변화)
- `portfolio_types.py`: 변경 없음 (OrderIntent는 engine 내부 private 모델)

---

## 6) 단계별 계획(Phases)

### Phase 0 — 새 계약을 테스트로 먼저 고정(레드)

새 함수들이 아직 존재하지 않으므로 테스트는 모두 실패한다(레드). Phase 1에서 구현 후 그린으로 전환한다.

**작업 내용**:

- [x] `test_portfolio_strategy.py`에 새 계약 테스트 클래스 추가:
  - `TestOrderIntentModel`: `OrderIntent` 4종류 intent_type 정의 검증
  - `TestGenerateSignalIntents`: EXIT_ALL(매도 신호), ENTER_TO_TARGET(매수 신호), HOLD(신호 없음) 계약 검증
  - `TestComputeProjectedPortfolio`: EXIT_ALL → active에서 제거 + cash 증가 / ENTER → active에 추가 계약 검증
  - `TestBuildRebalanceIntents`: active 자산만 대상 / threshold 미초과 시 빈 dict 반환 / 초과 시 REDUCE/INCREASE 생성 검증
  - `TestMergeIntents`: EXIT_ALL 우선 / 자산당 1개 보장 / ENTER+INCREASE → ENTER_TO_TARGET 검증

**Validation (레드 확인)**:

- [x] 새 테스트들이 `ImportError` 또는 `AttributeError`로 실패하는지 확인
  ```
  poetry run pytest tests/test_portfolio_strategy.py::TestOrderIntentModel -v
  ```

---

### Phase 1 — 전면 구현 및 메인 루프 재작성(그린 전환)

**작업 내용**:

1. **새 내부 모델 추가** (`portfolio_engine.py`):
   - [x] `OrderIntent` dataclass: `asset_id`, `intent_type`, `current_amount`, `target_amount`, `delta_amount`, `target_weight`, `reason`, `hold_days_used` (int, 기본 0)
   - [x] `_ProjectedPortfolio` dataclass: `projected_amounts` (dict[str, float]), `projected_cash` (float), `active_assets` (set[str])

2. **새 함수 구현** (`portfolio_engine.py`):
   - [x] `_generate_signal_intents(asset_states, strategies, asset_signal_dfs, equity_vals, slot_dict, current_equity, i, current_date) -> dict[str, OrderIntent]`
     - position=0 + buy signal → ENTER_TO_TARGET, `get_buy_meta()`로 `hold_days_used` 보존
     - position>0 + sell signal → EXIT_ALL
     - 그 외 → intent 생성 안 함 (HOLD)
   - [x] `_compute_projected_portfolio(asset_states, signal_intents, equity_vals, asset_closes_map, shared_cash) -> _ProjectedPortfolio`
     - EXIT_ALL 자산: `projected_amounts[asset_id] = 0`, active에서 제거, cash 증가(현재 평가액 추가)
     - ENTER_TO_TARGET 자산: active에 추가 (아직 position=0이므로 projected_amounts=0이나 active에는 포함)
     - 나머지: 현재 상태 유지
   - [x] `_build_rebalance_intents(projected, slot_dict, total_equity_projected, threshold, current_date) -> dict[str, OrderIntent]`
     - active_assets 중 |actual/target - 1| > threshold인 자산이 하나도 없으면 `{}` 반환
     - 하나라도 초과 시: 전체 active 자산에 대해 REDUCE_TO_TARGET(초과) / INCREASE_TO_TARGET(미달) 생성
     - scale_factor: projected_cash + 예상 매도 수익 기준 매수 가능액 계산 (기존 로직 이관)
   - [x] `_merge_intents(signal_intents, rebalance_intents) -> dict[str, OrderIntent]`
     - EXIT_ALL 항상 우선
     - ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance target_amount 사용)
     - 그 외는 signal 또는 rebalance 단독 사용
     - 결과: 자산당 1개 보장

3. **메인 루프 재작성** (`run_portfolio_backtest`):
   - [x] `_AssetState.pending_order` 필드 제거
   - [x] `_PortfolioPendingOrder` 클래스 제거
   - [x] `next_day_intents: dict[str, OrderIntent] = {}` 변수 추가
   - [x] Step A (SELL 체결): `next_day_intents` 중 EXIT_ALL, REDUCE_TO_TARGET 처리
     - EXIT_ALL → 전량 매도 (기존 signal sell과 동일)
     - REDUCE_TO_TARGET → 부분 매도 (`delta_amount` 기준 수량 계산)
   - [x] Step B (BUY 체결): `next_day_intents` 중 ENTER_TO_TARGET, INCREASE_TO_TARGET 처리
     - ENTER_TO_TARGET → 신규 진입 (`target_amount` 기준, position=0 확인)
     - INCREASE_TO_TARGET → 추가매수 (기존 is_rebalance=True와 동일, entry_price 가중평균)
   - [x] Step C: equity 계산 (변경 없음)
   - [x] Step D: signal → projected → rebalance → merge 순서로 재구성
   - [x] Step D.5: signal_state 업데이트 (EXIT_ALL → "sell", ENTER_TO_TARGET → "buy")
   - [x] Step D.6: `next_day_intents = merged_intents`
   - [x] Step E: equity row 기록 (변경 없음)

4. **기존 테스트 정비**:
   - [x] `test_portfolio_strategy.py` import 수정 (`_PortfolioPendingOrder`, `_execute_rebalancing` 제거)
   - [x] `_check_rebalancing_needed`, `_execute_rebalancing` 직접 테스트 → 새 함수 테스트로 교체
   - [x] Phase 0 테스트가 모두 그린으로 전환 확인

**Validation (그린 확인)**:

- [x] Phase 0 테스트 모두 통과 확인
  ```
  poetry run pytest tests/test_portfolio_strategy.py -v
  ```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트: `portfolio_engine.py` 섹션에서 pending_order 제거, OrderIntent 기반 흐름 반영
- [x] `portfolio_engine.py` 모듈 docstring 업데이트 (새 설계 반영)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=402, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 엔진 OrderIntent 리팩토링 — pending_order 제거 + Signal-Projected-Rebalance-Execution 흐름 확립
2. 백테스트 / 포트폴리오 엔진 전면 재설계 — 주문 충돌 및 planning 왜곡 버그 수정
3. 백테스트 / 포트폴리오 엔진 OrderIntent 기반 리팩토링 — ProjectedPortfolio + merge_intents 도입
4. 백테스트 / 포트폴리오 엔진 리팩토링 — pending_order → OrderIntent 교체 + 설계 결함 수정
5. 백테스트 / 포트폴리오 엔진 재설계 — Signal 우선 원칙 + Projected 기반 리밸런싱 + 단일 주문 보장

---

## 7) 리스크(Risks)

| 리스크 | 확률 | 완화책 |
|--------|------|--------|
| 기존 통합 테스트(`run_portfolio_backtest`)가 새 로직과 충돌 | 중 | Phase 1에서 기존 테스트 병행 실행하며 확인 |
| `entry_hold_days` 보존 누락으로 trade log 오염 | 중 | `OrderIntent.hold_days_used` 필드로 명시적 이관 |
| scale_factor 계산이 projected_cash 기준으로 바뀌며 수치 변동 | 저 | 의도된 버그 수정 결과, Notes에 기록 |
| `compute_portfolio_effective_start_date` 에 미치는 영향 | 저 | 해당 함수는 data loading + MA 계산만 담당, engine 흐름 미사용이므로 영향 없음 |

## 8) 메모(Notes)

### 핵심 설계 결정 요약

- **position 기준**: shares (int) 유지 — "평가액"과 "보유상태" 분리 원칙
- **planning 기준**: amount (float) — `OrderIntent.target_amount`, `delta_amount` 모두 금액
- **signal_state 소유자**: 엔진 (`_AssetState`) — 전략은 판단만, 상태 관리는 엔진
- **충돌 해결**: 두 문제(A: 주문 충돌, B: projected 왜곡) 모두 해결 필요

### `_build_rebalance_intents` 임계값 체크 위치

기존에는 `_check_rebalancing_needed` → `_execute_rebalancing` 2단계였다.
새 설계에서는 `_build_rebalance_intents` 내부에서 threshold 체크 + intent 생성을 통합한다.
임계값 초과 자산이 없으면 `{}` 반환으로 단락된다.

### 제거 대상 심볼

제거되는 내부 심볼 (테스트 import 수정 필요):
- `_PortfolioPendingOrder` (dataclass)
- `_check_rebalancing_needed` (함수)
- `_execute_rebalancing` (함수)
- `_AssetState.pending_order` (필드)

유지되는 심볼:
- `_AssetState` (pending_order 필드 제거 후 유지)
- `_compute_portfolio_equity`
- `_is_first_trading_day_of_month`
- `run_portfolio_backtest`
- `compute_portfolio_effective_start_date`

### 진행 로그 (KST)

- 2026-03-26 00:00: 계획서 초안 작성 — 확인 질문 3개 답변 수렴 후 설계 확정
- 2026-03-26 14:57: 전체 구현 완료 — validate_project.py 통과 (passed=402, failed=0, skipped=0)
