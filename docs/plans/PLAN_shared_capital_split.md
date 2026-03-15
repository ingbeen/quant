# Implementation Plan: 공유 자본 분할 매수매도 + 미청산 포지션 버그 수정

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

**작성일**: 2026-03-15
**마지막 업데이트**: 2026-03-15
**관련 범위**: backtest, scripts, tests, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/tranche_architecture.md`, `docs/tranche_final_recommendation.md`

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

- [x]미청산 포지션 avg_entry_price 버그 수정 (마지막 보유 기간에서 평단이 None으로 빠지는 문제)
- [x]공유 자본 매수 규칙 구현 (매수 투입 자본 = 현금 ÷ 미보유 트랜치 수)
- [x]기존 독립 자본 방식(`run_buffer_strategy()` N회 호출)에서 공유 자본 방식(날짜별 통합 루프)으로 전환
- [x]테스트 코드 작성 (공유 자본 규칙 검증)

## 2) 비목표(Non-Goals)

- 리밸런싱 (매수 시 기존 보유 트랜치 매도/조정 없음)
- 트랜치 가중치 변경 (33:34:33 고정 유지)
- `run_buffer_strategy()` 자체 수정 (기존 단일 전략 함수 무변경)
- 기존 독립 자본 방식 삭제 (공유 자본을 새 함수로 추가, 기존 유지)
- 시각화 대시보드 변경 (데이터 구조가 동일하므로 대시보드 수정 불필요)
- buffer_zone_tqqq, buffer_zone_qqq 외 다른 자산의 분할 전략

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1 — 미청산 포지션 avg_entry_price 버그:**

`_get_latest_entry_price()`가 `trades_df`만 검색하는데, 미청산 포지션(마지막 보유)은 `trades_df`에 기록되지 않고 `summary["open_position"]`에만 존재한다. 결과적으로 마지막 보유 기간의 `avg_entry_price`가 `None`으로 빠진다.

**문제 2 — 독립 자본의 비현실성:**

현재 각 트랜치가 초기 자본을 독립적으로 운용하는 방식은 실제 매매와 다르다:
- 실제로는 하나의 계좌에서 운용하므로 자본이 공유됨
- 출금, 추가 입금, 계좌 통합 등으로 "트랜치별 꼬리표 달린 돈"은 수십 년간 유지 불가능
- 먼저 수익을 낸 트랜치의 이익을 다른 트랜치가 활용할 수 없는 것은 비현실적

**공유 자본 매수 규칙 (확정):**

```
매수 투입 자본 = 현금 ÷ 미보유 트랜치 수 (자기 포함)
매도 시 = 해당 트랜치의 보유 주식 전량 매도 (기존과 동일)
```

시나리오 예시:

| 시점 | 이벤트 | 보유 | 미보유(자기포함) | 현금 | 투입 계산 | 투입액 |
|---|---|---|---|---|---|---|
| 1일 | 시작 | - | 3 | 1,000만 | - | - |
| 10일 | ma150 매수 | - | 3 | 1,000만 | 1,000 ÷ 3 | 333만 |
| 30일 | ma200 매수 | ma150 | 2 | 667만 | 667 ÷ 2 | 333만 |
| 50일 | ma250 매수 | ma150,200 | 1 | 334만 | 334 ÷ 1 | 334만 전액 |
| 80일 | ma150 매도(+50%) | ma200,250 | 1 | +500만 | - | - |
| 90일 | ma150 재매수 | ma200,250 | 1 | 500만 | 500 ÷ 1 | 500만 전액 |

핵심: 매수 체결 시점에 "나 포함 앞으로 살 트랜치가 몇 개인지"로 나눈다. 미보유가 자기뿐이면 현금 전액 투입.

### 구현 방식: 오케스트레이터 날짜 루프

현재 방식은 `run_buffer_strategy()`를 N회 독립 호출하지만, 공유 자본은 **매수 시 통합 현금을 참조**해야 하므로 `run_buffer_strategy()`를 그대로 사용할 수 없다.

새 함수 `run_split_backtest_shared_capital()`을 작성하여, 기존 `run_buffer_strategy()`의 **시그널 판정 로직(밴드 돌파, hold_days, pending order)**을 재활용하되, **자본 배분과 체결은 오케스트레이터가 관리**한다.

구체적으로:
- 기존 `run_buffer_strategy()` 내부의 시그널 판정 로직을 **추출하여 재활용**하거나,
- **날짜별 루프에서 트랜치별 시그널을 직접 판정**하고, 공유 현금에서 자본을 배분한다.

가장 안전한 접근: 기존 `run_buffer_strategy()`의 **핵심 로직(밴드 계산, 시그널 감지, hold_days 상태머신, pending order)**을 그대로 유지하면서, `initial_capital` 대신 **매수 시점의 배분 자본**을 사용하도록 오케스트레이터가 제어한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 전반 규칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙 (체결 타이밍, pending order, hold_days 등 절대 규칙)
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 규칙
- `docs/tranche_architecture.md`: 데이터 흐름/출력 구조 설계
- `docs/tranche_final_recommendation.md`: 파라미터 선택 근거

## 4) 완료 조건(Definition of Done)

- [x]`_get_latest_entry_price()` 미청산 포지션 버그 수정 (summary의 open_position entry_price 활용)
- [x]`run_split_backtest_shared_capital()` 신규 함수 구현 (공유 자본 날짜별 루프)
- [x]공유 자본 매수 규칙: `현금 ÷ 미보유 트랜치 수` 정확히 적용
- [x]매도 규칙: 해당 트랜치 보유 주식 전량 매도 (기존과 동일)
- [x]체결 타이밍 규칙 준수: 시그널 i일 종가, 체결 i+1일 시가 (절대 규칙)
- [x]pending order / hold_days 상태머신 규칙 준수 (절대 규칙)
- [x]SplitStrategyResult 출력 형식 유지 (combined_equity_df, combined_trades_df, combined_summary, signal_df)
- [x]equity.csv 컬럼 구조 유지 (Date, equity, active_tranches, avg_entry_price, {tid}_equity, {tid}_position)
- [x]CLI 스크립트 업데이트 (`run_split_backtest.py`에서 공유 자본 함수 호출)
- [x]회귀/신규 테스트 추가
- [x]`poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x]`poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x]관련 문서 업데이트
- [x]plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `src/qbt/backtest/split_strategy.py` | (1) `_get_latest_entry_price()` 버그 수정, (2) `run_split_backtest_shared_capital()` 신규 함수, (3) `SPLIT_CONFIGS` 업데이트 |
| `scripts/backtest/run_split_backtest.py` | 공유 자본 함수 호출로 변경 |
| `tests/test_split_strategy.py` | 공유 자본 규칙 테스트 추가 |
| `src/qbt/backtest/CLAUDE.md` | 공유 자본 방식 설명 추가 |
| `scripts/CLAUDE.md` | 스크립트 변경 반영 |
| `tests/CLAUDE.md` | 테스트 추가 반영 |
| `docs/tranche_architecture.md` | 공유 자본 방식 추가 기술 |

### 변경하지 않는 파일 (절대 규칙)

| 파일 | 이유 |
|---|---|
| `buffer_zone_helpers.py` | `run_buffer_strategy()` 무변경. 시그널 판정 로직 참조만 함 |
| `buffer_zone.py` | 기존 config-driven 팩토리 유지 |
| `analysis.py` | `calculate_summary()` 재사용만 함 |
| `app_split_backtest.py` | 출력 형식 동일하므로 대시보드 수정 불필요 |
| `app_single_backtest.py` | 무관 |

### 데이터/결과 영향

- 기존 결과 디렉토리 동일: `split_buffer_zone_tqqq/`, `split_buffer_zone_qqq/`
- 출력 파일 형식 동일: `signal.csv`, `equity.csv`, `trades.csv`, `summary.json`
- **수치가 달라짐**: 공유 자본이므로 기존 독립 자본 결과와 CAGR/MDD/거래수 등이 변경됨

## 6) 단계별 계획(Phases)

### Phase 0 — 미청산 포지션 버그 수정 + 인바리언트 테스트 (레드)

> 미청산 포지션 버그를 수정하고, 공유 자본 핵심 규칙을 테스트로 먼저 고정한다.

**작업 내용**:

- [x]`_get_latest_entry_price()` 버그 수정

수정 방법: 함수 시그니처에 `open_position` 파라미터 추가

```python
def _get_latest_entry_price(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    current_date: object,
    open_position: dict[str, Any] | None = None,  # 추가
) -> float | None:
```

마지막 `return None` 부분에서 `open_position`이 존재하면 `entry_price` 반환:

```python
# 모든 거래가 청산 완료 → 미청산 포지션 케이스
if open_position is not None:
    return float(open_position["entry_price"])
return None
```

- [x]`_combine_equity()` 호출부에서 `open_position` 전달

```python
open_pos = tr.summary.get("open_position")
entry_price = _get_latest_entry_price(
    tr.trades_df, tr.equity_df, current_date,
    open_position=open_pos,
)
```

- [x]미청산 포지션 버그 수정 테스트 추가

```
- test_avg_entry_price_with_open_position: 미청산 포지션 기간에 avg_entry_price가 None이 아닌지 검증
```

- [x]공유 자본 핵심 규칙 테스트 작성 (레드)

```
- test_shared_capital_first_buy_divides_by_3: 첫 매수 시 현금 ÷ 3
- test_shared_capital_second_buy_divides_by_2: 두번째 매수 시 남은 현금 ÷ 2
- test_shared_capital_last_buy_uses_all_cash: 마지막 미보유 매수 시 현금 전액
- test_shared_capital_sell_returns_to_cash: 매도 시 현금으로 복귀
- test_shared_capital_rebuy_after_profit: 수익 매도 후 재매수 시 더 큰 자본 투입
- test_shared_capital_rebuy_after_loss: 손실 매도 후 재매수 시 더 작은 자본 투입
- test_shared_capital_simultaneous_buy: 동시 매수 시 현금 ÷ 미보유 수
- test_shared_capital_result_structure: SplitStrategyResult 출력 형식 유지
```

---

### Phase 1 — 공유 자본 오케스트레이터 구현 (그린)

> `run_split_backtest_shared_capital()` 핵심 로직을 구현한다.

**작업 내용**:

- [x]`run_split_backtest_shared_capital()` 신규 함수 구현

처리 흐름:

```
1. 입력 검증 (트랜치 설정)
2. 데이터 로딩 (1회만) — base_config의 경로 사용
3. 모든 트랜치 MA 사전 계산
4. 트랜치별 상태 초기화:
   per_tranche_state = {
     tid: {
       capital: 0,        # 해당 트랜치에 투입된 주식 매수 자본 (매수 시 결정)
       position: 0,       # 보유 주수
       entry_price: 0.0,  # 진입가
       entry_date: None,  # 진입일
       pending_order: None,
       hold_state: None,
       trades: [],
       equity_records: [],
     }
   }
   shared_cash = total_capital  # 통합 현금

5. 날짜별 통합 루프:
   for i in range(1, len(signal_df)):
     # 5-1. 각 트랜치의 pending order 체결 (매수/매도)
     #   매수 체결 시: shared_cash에서 자본 차감
     #   매도 체결 시: 매도 대금 shared_cash에 복귀

     # 5-2. 각 트랜치의 시그널 판정 (종가 기준)
     #   매수 시그널: 미보유 + upper_band 이상
     #   매도 시그널: 보유 + lower_band 이하
     #   hold_days 상태머신 적용

     # 5-3. pending order 생성
     #   매수 pending: 체결 시 투입 자본 = shared_cash ÷ 미보유 트랜치 수 (체결 시점에 계산)
     #   매도 pending: 전량 매도

     # 5-4. 에쿼티 기록 (트랜치별 + 합산)

6. 결과 조합 → SplitStrategyResult 반환
```

매수 자본 계산 핵심 로직:

```python
# 매수 체결 시점 (pending_order 실행 시)
unowned_count = sum(1 for s in states.values() if s.position == 0)
buy_capital = shared_cash / unowned_count  # 미보유 트랜치 수로 나눔
shares = int(buy_capital / buy_price)      # 매수 가능 주수
actual_cost = shares * buy_price
shared_cash -= actual_cost
```

- [x]시그널 판정 로직: `buffer_zone_helpers.py`의 규칙 동일 적용
  - 밴드 계산: `upper = ma × (1 + buy_buffer_pct)`, `lower = ma × (1 - sell_buffer_pct)`
  - 매수 시그널: `close >= upper_band` (미보유 시)
  - 매도 시그널: `close <= lower_band` (보유 시)
  - hold_days: 돌파일 i → 유지조건 i+1 ~ i+H → 확정 i+H → 체결 i+H+1 시가
  - pending order: 단일 슬롯, 신호일에 생성, 체결일에 실행 후 None
  - 비용: `buy_price = open × (1 + SLIPPAGE_RATE)`, `sell_price = open × (1 - SLIPPAGE_RATE)`

- [x]`_combine_equity_shared()` 헬퍼 구현
  - 날짜별 루프에서 직접 기록하므로 기존 `_combine_equity()`보다 단순
  - equity, active_tranches, avg_entry_price, {tid}_equity, {tid}_position 동일 컬럼 구조

- [x]`_combine_trades_shared()` 헬퍼 구현
  - 기존 `_combine_trades()`와 동일 (tranche_id, tranche_seq, ma_window 태깅)

- [x]Phase 0의 레드 테스트 전부 그린 전환

---

### Phase 2 — CLI 스크립트 업데이트 + 추가 테스트 (그린)

**작업 내용**:

- [x]`run_split_backtest.py` 수정: `run_split_backtest_shared_capital()` 호출로 변경
- [x]`SPLIT_CONFIGS` 업데이트 (필요 시)
- [x]기존 `run_split_backtest()` (독립 자본) 함수는 유지 (삭제하지 않음, 비교 가능)
- [x]추가 테스트:

```
- test_shared_capital_equity_csv_columns: equity.csv 컬럼 구조 유지 검증
- test_shared_capital_total_equity_equals_cash_plus_positions: 합산 에쿼티 = 현금 + 주식 평가액
- test_shared_capital_no_negative_cash: 현금이 음수가 되지 않음
- test_shared_capital_signal_df_preserved: signal_df가 결과에 포함
```

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x]`src/qbt/backtest/CLAUDE.md` 업데이트 (공유 자본 방식 설명 추가)
- [x]`scripts/CLAUDE.md` 업데이트
- [x]`tests/CLAUDE.md` 업데이트
- [x]`docs/tranche_architecture.md` 업데이트 (공유 자본 방식 추가 기술)
- [x]`poetry run black .` 실행 (자동 포맷 적용)
- [x]변경 기능 및 전체 플로우 최종 검증
- [x]DoD 체크리스트 최종 업데이트 및 체크 완료
- [x]전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=351, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 분할 매수매도 공유 자본 방식 구현 + 미청산 포지션 버그 수정
2. 백테스트 / 공유 자본 오케스트레이터 신규 구현 (현금 ÷ 미보유 트랜치 수 배분)
3. 백테스트 / split_strategy 공유 자본 전환 — 현실적 자본 배분 + avg_entry_price 버그 수정
4. 백테스트 / 분할 전략 공유 자본 방식 추가 및 미청산 포지션 평단 누락 수정
5. 백테스트 / 공유 자본 분할 매수매도 + 날짜별 통합 루프 오케스트레이터

## 7) 리스크(Risks)

- **시그널 판정 로직 재구현**: `run_buffer_strategy()` 내부의 시그널 판정 로직을 새 함수에서 재구현해야 함. 기존 182회 검증된 로직과 정확히 동일하게 구현해야 하므로, 핵심 규칙(체결 타이밍, pending order, hold_days)을 테스트로 먼저 고정한다.
- **기존 결과와 수치 차이**: 공유 자본이므로 독립 자본 결과와 CAGR/MDD 등이 달라짐. 이는 정상 동작이며, 기존 함수를 삭제하지 않으므로 비교 가능.
- **동시 매수/매도 처리**: 같은 날 여러 트랜치에서 시그널 발생 시 처리 순서를 명확히 정의해야 함 → 트랜치 순서(ma250→ma200→ma150)로 고정.
- **pending order 체결 시점의 현금 계산**: 매수 pending 생성 시가 아니라 **체결 시점**에 `shared_cash ÷ 미보유 수`를 계산해야 함. 시그널일과 체결일 사이에 다른 트랜치가 매도할 수 있기 때문.

## 8) 메모(Notes)

### 핵심 결정 사항

- **공유 자본 매수 규칙**: `현금 ÷ 미보유 트랜치 수 (자기 포함)`. 미보유가 자기뿐이면 현금 전액.
- **매도 규칙**: 해당 트랜치 보유 전량 매도 (기존과 동일)
- **기존 함수 유지**: `run_split_backtest()` (독립 자본)은 삭제하지 않고 유지. `run_split_backtest_shared_capital()`을 새로 추가.
- **미청산 포지션 버그**: `_get_latest_entry_price()`에 `open_position` 파라미터 추가로 해결.

### 참고 문서

- 선행 계획서: `docs/plans/PLAN_split_strategy.md` (분할 매수매도 오케스트레이터 — 독립 자본)
- 설계 문서: `docs/tranche_architecture.md`
- 파라미터 근거: `docs/tranche_final_recommendation.md`

### 진행 로그 (KST)

- 2026-03-15: 계획서 작성

---
