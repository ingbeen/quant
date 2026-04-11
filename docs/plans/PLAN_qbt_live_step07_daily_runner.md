# Implementation Plan: QBT Live - Step 7 일일 실행 메인 (daily_runner.py)

> 작성/운영 규칙(SoT): [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**Done 처리 규칙**: DoD 모두 [x] + failed=0 + skipped=0.

---

**작성일**: 2026-04-11 13:30
**마지막 업데이트**: 2026-04-11 13:30
**관련 범위**: live
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (4.1, 4.2, 부록 A)
- [src/qbt/backtest/engines/portfolio_engine.py](../../src/qbt/backtest/engines/portfolio_engine.py) (메인 루프 참고)

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project.py 는 마지막 Phase 에서만 실행
- Phase 0 레드 허용, Phase 1 이후 그린 유지

---

## 1) 목표

- [x] 목표 1: `run_daily(trade_date, state, market_bundle, pending_fills, applied_fill_ids) -> DailyResult` 구현
- [x] 목표 2: 파일 I/O 및 외부 네트워크 호출 없음 (순수 계산)
- [x] 목표 3: QBT 코어 재사용 — `generate_signal_intents`, `compute_projected_portfolio`, `merge_intents`, `DEFAULT_REBALANCE_POLICY`, `execute_orders`
- [x] 목표 4: `MarketBundle` 타입을 `live.models` 에 추가 (자산별 signal_df + trade_df 묶음)
- [x] 목표 5: TODO T-7.1 ~ T-7.5 통과

## 2) 비목표

- fill 자동 매칭 / drift 계산 (Step 8)
- 회귀 검증 (Step 9)
- CLI (Step 10)
- RTDB / 알림 / Git push (Step 12+)

## 3) 배경/맥락

### 동기

- run_daily 는 매일 실행의 핵심 순수 계산 함수. QBT 의 `run_portfolio_backtest` 의 1 iteration 과 동등한 동작을 "1 일치" 로 추출한 것이다.
- 설계서 4.2 실행 순서 중 **5 ~ 9** 단계를 담당 (파일 I/O 는 CLI 에서 처리):
  - 5. RTDB fills → pending 자동 매칭 → actual 반영 (Step 8 완료 후 통합)
  - 6. 전일 pending → 당일 시가 model 체결
  - 7. 당일 종가 equity (model + actual)
  - 8. signal intents → projected → rebalance → merge
  - 9. 익일 pending 생성
- 입력 state 는 **불변**으로 다루고 새 `LiveState` 를 반환.

### 설계 결정

#### D1. `MarketBundle` 타입

```python
@dataclass
class AssetMarketData:
    signal_df: pd.DataFrame  # MA 컬럼 포함 (ma_200 등)
    trade_df: pd.DataFrame   # 체결용 trade CSV

MarketBundle = dict[str, AssetMarketData]  # asset_id -> data
```

`live.models` 에 `AssetMarketData` dataclass 만 추가하고, `MarketBundle` 은 type alias 로 둔다.

#### D2. fill 처리 — **Step 7 에서는 빈 처리**

- Step 7 에서는 `apply_fills_idempotent` 가 미구현. `pending_fills` 입력을 받되 처리 로직은 Step 8 에서 통합.
- Step 7 의 run_daily 는 `pending_fills` 가 비어있지 않으면 일단 `updated_applied_fill_ids` 에 ID 만 추가하고 actual 상태는 변경하지 않는 placeholder 로 구현.
- **주석으로 "Step 8 에서 실제 fill 반영 로직 연결" 명시**. 후속 Step 에서 이 부분을 완성한다.

#### D3. 1 iteration 로직 — QBT 루프 복제

- `execute_orders`, `generate_signal_intents`, `compute_projected_portfolio`, `merge_intents`, `DEFAULT_REBALANCE_POLICY`, `is_first_trading_day_of_month` 를 그대로 import 하여 호출
- QBT 의 루프 변수(`asset_states`, `shared_cash`, `entry_prices`, 등) 를 `LiveState` 에서 복원하고 1 iteration 수행 후 `LiveState` 로 재조립.
- `BufferZoneStrategy` 는 `buffer_serializer.restore_buffer_state` 로 복원하고, iteration 후 `extract_buffer_state` 로 재추출.

#### D4. 인덱스 결정

- `trade_date` 는 `market_bundle` 의 한 자산 `trade_df[COL_DATE]` 에 존재해야 한다. 위치 = 인덱스 `i`.
- 전 자산의 `trade_df` 는 동일 날짜 집합이라 가정 (MarketBundle 준비 시 호출자가 보장).

#### D5. DailyResult 구성

- `updated_state`: 새 `LiveState` (model_* 및 strategies buffer_zone_state 갱신)
- `signals`: `{asset_id: SignalDetection}` (state / close / upper_band / lower_band / ema_200 / ema_distance_pct)
- `order_intents`: merged_intents (익일 체결 예정)
- `executions`: `ExecutionResult | None` (전일 pending 이 있으면 set)
- `rebalance_triggered`: bool
- `model_equity`, `actual_equity`, `drift_pct` (Step 8 에서 정교화, Step 7 은 단순 계산)
- `ema_distances`: `{asset_id: (close - ema) / ema}`
- `notification_body`: 간단 요약 문자열 (Step 13 notifier 에서 교체 가능)
- `pending_fill_reminders`: `list[str]` (Step 8 완성 후 실제 활용)
- `chart_series`: 빈 dict (Step 14)

## 4) 완료 조건(DoD)

- [x] `live/src/live/models.py` 에 `AssetMarketData` dataclass + `MarketBundle` type alias 추가
- [x] `live/src/live/daily_runner.py` 에 `run_daily` 구현
- [x] `live/tests/test_daily_runner.py` 작성 및 통과 (T-7.1 ~ T-7.5)
- [x] QBT 본체 수정 없음
- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] TODO Step 7 체크박스 체크
- [x] plan 체크박스 최신화

## 5) 변경 범위

### 수정

- `live/src/live/models.py` (AssetMarketData / MarketBundle 추가)
- `live/src/live/daily_runner.py` (구현)
- `docs/TODO_QBT_LIVE.md`

### 신규

- `live/tests/test_daily_runner.py`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 계약 테스트 선작성

- [x] `test_daily_runner.py`:
  - T-7.1: 초기 상태 + 1 일 데이터 → DailyResult 정상 반환
  - T-7.2: pending 없는 초기 상태 → model 변경 없음 (shares 모두 0)
  - T-7.3: 상향 돌파 signal 발생 시 → pending_order 생성 확인 (state.assets 에 저장)
  - T-7.4: pending 있는 상태 + 다음 날 → model 체결 확인 (shares > 0)
  - T-7.5: run_daily 내부에서 파일 I/O 없음 — `open()` / `Path.write_*` / `Path.read_*` monkeypatch 로 감시

### Phase 1 — 구현

- [x] models.py 에 AssetMarketData / MarketBundle 추가
- [x] daily_runner.py 구현:
  - `_find_trade_index(trade_df, trade_date) -> int`
  - `_restore_strategies(state, slot_dict) -> dict[str, SignalStrategy]`
  - `_extract_buffer_states(strategies, state) -> dict[str, BufferZoneState]`
  - `_build_asset_states_from_live(state) -> dict[str, AssetState]`
  - `run_daily(trade_date, state, market_bundle, pending_fills, applied_fill_ids) -> DailyResult`

### Phase 2 — 문서 동기화

- [x] TODO Step 7 체크박스 체크

### 마지막 Phase — 최종 검증

- [x] black + validate_project
- [x] plan Done 처리

**Validation**: `poetry run python validate_project.py` (passed=658, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / run_daily 순수 계산 구현 (Step 7)`
2. `live / daily_runner.py — QBT 루프 1 iteration 복제`
3. `live / Step 7 run_daily + MarketBundle 타입 추가`
4. `live / LiveState 기반 1일치 실행 엔진`
5. `live / run_daily + T-7.1~T-7.5 테스트`

## 7) 리스크

- **QBT 루프 내부 변수 복원/재조립의 정합성**: Step 9 회귀 검증에서 완전 일치 확인 필요. Step 7 에서는 구조만 검증.
- **fill 처리 placeholder**: Step 8 에서 연결 누락 시 actual 축이 미갱신. Step 8 에서 통합 테스트 추가.

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 13:30: 계획서 작성
