# Implementation Plan: 백테스트 도메인 안정성 리팩터링

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

**작성일**: 2026-03-21 00:00
**마지막 업데이트**: 2026-03-21 16:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] **하드코딩 제거**: magic number(`1e10`)와 문자열 리터럴(`"ema"`) 및 중복 수치를 이름 있는 상수로 교체
- [x] **순환 의존성 완전 해결**: `BufferStrategyParams`를 `types.py`로 이동하고 `create_runner` 함수들을 새 `runners.py`로 분리하여 deferred import 0개 달성
- [x] **HoldState 안정성**: `check_buy` 시그니처에 `current_date`, `buy_buffer_pct`를 추가하여 플레이스홀더 패턴 제거 + 명시적 Protocol 상속 적용
- [x] **execute_sell_order 안정성**: `hold_days_used` 파라미터를 명시적으로 요구하여 암묵적 덮어쓰기 계약 제거
- [x] **run_buy_and_hold 제거**: B&H를 엔진 기반으로 통일하고 미사용 코드(`run_buy_and_hold`, `BuyAndHoldParams`, `resolve_params`) 삭제

## 2) 비목표(Non-Goals)

- `run_backtest` 시그니처에서 `BufferStrategyParams` 타입 의존성 제거 (더 큰 리팩터링, 별도 plan)
- `portfolio_engine`을 `engine_common`의 `execute_buy_order`/`execute_sell_order` 사용으로 통합
- 그리드 서치 `ma_type` 파라미터화 (현재 EMA 고정 정책 유지, 상수로만 표현)
- `run_buffer_strategy` 함수 제거 (WFO 등 직접 호출 경로에서 여전히 유효)

## 3) 배경/맥락(Context)

### 현재 문제점

1. **하드코딩**: `1e10`이 `analysis.py`, `backtest_engine.py`, `walkforward.py` 3개 파일에 중복. `"ema"` 문자열이 `backtest_engine.py`, `walkforward.py`에 리터럴로 존재. `run_grid_search`의 `initial_capital` 기본값이 상수 대신 숫자 리터럴.
2. **순환 의존성**: `buffer_zone.py` ↔ `backtest_engine.py` 순환으로 deferred import 3개 발생. 모든 deferred import는 `# noqa: PLC0415`로 린트 경고를 억제하고 있어 코드 가독성 저하.
3. **HoldState 플레이스홀더**: `BufferZoneStrategy.check_buy()`가 `start_date=date.min`, `buffer_pct=0.0` 플레이스홀더를 반환하고 엔진이 나중에 주입. Protocol 계약에 이 암묵적 규칙이 표현되지 않아 새 전략 구현 시 누락 위험.
4. **execute_sell_order 암묵 계약**: `execute_sell_order()`가 `hold_days_used=0`을 하드코딩하고 호출자가 반드시 덮어써야 함. 재사용 시 0이 그대로 CSV에 저장될 위험.
5. **run_buy_and_hold 이중화**: `BuyAndHoldStrategy`가 존재함에도 독립 벡터화 함수 `run_buy_and_hold`가 남아있어 두 경로가 공존.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] 하드코딩(`1e10`, `"ema"` 리터럴, `10_000_000.0` 기본값) 모두 상수로 교체
- [x] `BufferStrategyParams`가 `types.py`에 위치하고 `buffer_zone.py`에서 제거됨
- [x] `runners.py` 생성, `create_buffer_zone_runner`/`create_buy_and_hold_runner` 정의
- [x] `buffer_zone.py`와 `buy_and_hold.py`에 deferred import 0개
- [x] `backtest_engine.py`에 deferred import 0개
- [x] `check_buy` 시그니처에 `current_date`, `buy_buffer_pct` 파라미터 추가
- [x] `BufferZoneStrategy`, `BuyAndHoldStrategy` 모두 `(SignalStrategy)` 명시적 상속
- [x] `execute_sell_order` 시그니처에 `hold_days_used: int` 파라미터 추가
- [x] `backtest_engine.py`의 `trade_record["hold_days_used"] = entry_hold_days` 덮어쓰기 라인 제거
- [x] `run_buy_and_hold`, `BuyAndHoldParams`, `resolve_params` 삭제
- [x] `create_buy_and_hold_runner`가 `run_backtest(BuyAndHoldStrategy(), ...)` 사용
- [x] 회귀/신규 테스트 추가 및 기존 테스트 업데이트
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (BufferStrategyParams 위치, runners.py 설명)

## 5) 변경 범위(Scope)

### 생성 파일

| 파일 | 내용 |
|------|------|
| `src/qbt/backtest/runners.py` | `create_buffer_zone_runner`, `create_buy_and_hold_runner` 팩토리 함수 |

### 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/qbt/backtest/constants.py` | `CALMAR_MDD_ZERO_SUBSTITUTE`, `DEFAULT_BUFFER_MA_TYPE` 상수 추가 |
| `src/qbt/backtest/analysis.py` | `1e10` → `CALMAR_MDD_ZERO_SUBSTITUTE`, `ma_type: str` → `Literal["ema", "sma"]` |
| `src/qbt/backtest/walkforward.py` | `1e10` → `CALMAR_MDD_ZERO_SUBSTITUTE`, `"ema"` → `DEFAULT_BUFFER_MA_TYPE` |
| `src/qbt/backtest/types.py` | `BufferStrategyParams` dataclass 추가 |
| `src/qbt/backtest/portfolio_types.py` | `ma_type: str` → `Literal["ema", "sma"]` |
| `src/qbt/backtest/strategies/strategy_common.py` | `check_buy` Protocol 시그니처에 `current_date`, `buy_buffer_pct` 추가 |
| `src/qbt/backtest/strategies/buffer_zone.py` | `BufferStrategyParams` 제거 및 `types.py` import, `create_runner` 제거, `SignalStrategy` 명시적 상속, `check_buy` 시그니처 갱신, `ma_type: Literal` |
| `src/qbt/backtest/strategies/buy_and_hold.py` | `create_runner`/`run_buy_and_hold`/`BuyAndHoldParams`/`resolve_params` 제거, `SignalStrategy` 명시적 상속, `check_buy` 시그니처 갱신 |
| `src/qbt/backtest/engines/engine_common.py` | `execute_sell_order`에 `hold_days_used: int` 파라미터 추가 |
| `src/qbt/backtest/engines/backtest_engine.py` | imports 갱신(deferred→top-level), 상수 교체, `check_buy` 호출 갱신, HoldState 주입 코드 제거, `execute_sell_order` 호출 갱신 |
| `src/qbt/backtest/engines/portfolio_engine.py` | `check_buy` 호출 갱신, HoldState 주입 코드 제거 |
| `src/qbt/backtest/strategies/__init__.py` | exports 갱신 (`BufferStrategyParams` 출처, `run_buy_and_hold`/`BuyAndHoldParams` 제거) |
| `src/qbt/backtest/__init__.py` | exports 갱신 (`run_buy_and_hold`/`BuyAndHoldParams` 제거, `BufferStrategyParams` 출처 갱신) |
| `scripts/backtest/run_single_backtest.py` | `create_runner` 호출을 `runners.create_buffer_zone_runner`/`runners.create_buy_and_hold_runner`로 변경 |
| `tests/test_strategy_interface.py` | Phase 0 레드 테스트 추가, Phase 3에서 그린 전환 |
| `tests/test_buy_and_hold.py` | `run_buy_and_hold` 관련 테스트 제거, 엔진 기반 runner 테스트로 교체 |
| `src/qbt/backtest/CLAUDE.md` | BufferStrategyParams 위치, runners.py 설명 업데이트 |

### 데이터/결과 영향

- **CSV/JSON 출력 스키마 변경 없음**: 컬럼명, 필드명 변경 없음
- **수치 변화 (B&H 한정)**: B&H 전략의 첫 매수 시점이 day 0 → day 2로 바뀌어 총 수익률/CAGR 미세 변경. 사용자 확인 완료.
- **기존 결과 파일 재실행 필요**: `run_single_backtest.py` 재실행 시 B&H 결과 수치가 미세하게 달라짐

---

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정 (레드)

**목적**: 변경될 두 계약(`check_buy` 새 시그니처, `execute_sell_order` 새 파라미터)을 테스트로 먼저 고정한다. 현재 API가 존재하지 않으므로 이 테스트들은 의도적으로 실패한다.

**작업 내용** (`tests/test_strategy_interface.py`에 추가):

- [x] `TestBufferZoneStrategyInterface`에 테스트 2개 추가:
  - `test_check_buy_first_breakout_start_date_is_current_date`: 첫 돌파 감지 시 반환된 `hold_state["start_date"]`가 전달한 `current_date`와 일치하는지 검증 (플레이스홀더 `date.min` 방지)
  - `test_check_buy_first_breakout_buffer_pct_is_correct`: 반환된 `hold_state["buffer_pct"]`가 전달한 `buy_buffer_pct`와 일치하는지 검증 (플레이스홀더 `0.0` 방지)
  - 두 테스트 모두 새 시그니처 사용 → 현재 TypeError로 실패 (레드)

**작업 내용** (`tests/test_buffer_zone_helpers.py` 또는 신규 `tests/test_engine_common.py`에 추가):

- [x] `test_execute_sell_order_hold_days_used_param`: `execute_sell_order(..., hold_days_used=5)` 호출 → 반환된 `trade_record["hold_days_used"] == 5` 검증
  - 현재 `hold_days_used` 파라미터 없음 → TypeError로 실패 (레드)

---

### Phase 1 — 하드코딩 제거 (상수화)

**작업 내용**:

1. `src/qbt/backtest/constants.py` 수정:
   - [x] `CALMAR_MDD_ZERO_SUBSTITUTE: Final = 1e10` 추가 (Calmar MDD=0 처리 대용값)
   - [x] `DEFAULT_BUFFER_MA_TYPE: Final = "ema"` 추가 (버퍼존/그리드서치 기본 MA 유형)

2. `src/qbt/backtest/analysis.py` 수정:
   - [x] `constants` import에 `CALMAR_MDD_ZERO_SUBSTITUTE` 추가
   - [x] `1e10` → `CALMAR_MDD_ZERO_SUBSTITUTE` 교체 (line 145 근방)
   - [x] `add_single_moving_average` 시그니처: `ma_type: str` → `ma_type: Literal["ema", "sma"]`

3. `src/qbt/backtest/walkforward.py` 수정:
   - [x] `constants` import에 `CALMAR_MDD_ZERO_SUBSTITUTE`, `DEFAULT_BUFFER_MA_TYPE` 추가
   - [x] `1e10` → `CALMAR_MDD_ZERO_SUBSTITUTE` 교체 (2개소)
   - [x] `ma_type="ema"` → `ma_type=DEFAULT_BUFFER_MA_TYPE` 교체 (line 330 근방)

4. `src/qbt/backtest/engines/backtest_engine.py` 수정:
   - [x] `constants` import에 `CALMAR_MDD_ZERO_SUBSTITUTE`, `DEFAULT_BUFFER_MA_TYPE` 추가
   - [x] `1e10` → `CALMAR_MDD_ZERO_SUBSTITUTE` 교체 (line 210 근방)
   - [x] `ma_type="ema"` → `ma_type=DEFAULT_BUFFER_MA_TYPE` 교체 (line 303, 563 근방, 2개소)
   - [x] `run_grid_search` 기본값: `initial_capital: float = 10_000_000.0` → `initial_capital: float = DEFAULT_INITIAL_CAPITAL`

5. `src/qbt/backtest/strategies/buffer_zone.py` 수정:
   - [x] `BufferZoneConfig.ma_type` 타입: `str` → `Literal["ema", "sma"]` (typing import에 Literal 추가)

6. `src/qbt/backtest/portfolio_types.py` 수정:
   - [x] `PortfolioConfig.ma_type` 타입: `str` → `Literal["ema", "sma"]`

**Validation**: Phase 1 완료 후 직접 실행 확인 (`poetry run python validate_project.py --only-lint` 수준)

---

### Phase 2 — 순환 의존성 완전 해결

**목표**: `buffer_zone.py ↔ backtest_engine.py` 순환 제거 → deferred import 0개 달성

**설계 요약**:
```
변경 전:
  backtest_engine.py ──(top-level)──► buffer_zone.py (BufferStrategyParams)
  buffer_zone.create_runner ──(deferred)──► backtest_engine.py (run_backtest)
  backtest_engine._run_backtest_for_grid ──(deferred)──► buffer_zone.py (BufferZoneStrategy)
  backtest_engine.run_buffer_strategy ──(deferred)──► buffer_zone.py (BufferZoneStrategy)

변경 후:
  backtest_engine.py ──(top-level)──► types.py (BufferStrategyParams)     ✓
  backtest_engine.py ──(top-level)──► buffer_zone.py (BufferZoneStrategy) ✓ (순환 없음)
  runners.py ──(top-level)──► backtest_engine.py (run_backtest)            ✓
  runners.py ──(top-level)──► buffer_zone.py (BufferZoneStrategy, ...)     ✓
  runners.py ──(top-level)──► buy_and_hold.py (BuyAndHoldStrategy, ...)    ✓
  buffer_zone.py: backtest_engine 관련 import 없음                          ✓
```

**작업 내용**:

1. `src/qbt/backtest/types.py` 수정:
   - [x] `BufferStrategyParams` dataclass를 `buffer_zone.py`에서 이곳으로 이동
   - [x] 모듈 docstring 업데이트 (BufferStrategyParams 위치 반영)

2. `src/qbt/backtest/runners.py` **신규 생성**:
   - [x] `create_buffer_zone_runner(config: BufferZoneConfig) -> Callable[[], SingleBacktestResult]`
     - 내용: 기존 `buffer_zone.create_runner`의 `run_single` 클로저 이전 (데이터 로딩, overlap 처리, MA 계산, `run_backtest(BufferZoneStrategy(), ...)`)
   - [x] `create_buy_and_hold_runner(config: BuyAndHoldConfig) -> Callable[[], SingleBacktestResult]`
     - 내용: 기존 `buy_and_hold.create_runner`의 `run_single` 클로저 이전 (Phase 5에서 `run_buy_and_hold` → `run_backtest` 전환)
   - [x] 모듈 docstring 작성 (팩토리 역할, 순환 의존성 해결 이유 명시)

3. `src/qbt/backtest/strategies/buffer_zone.py` 수정:
   - [x] `BufferStrategyParams` 클래스 정의 제거
   - [x] `from qbt.backtest.types import BufferStrategyParams` import 추가
   - [x] `create_runner` 함수 제거 (내용이 `runners.py`로 이동)
   - [x] `from qbt.backtest.engines.backtest_engine import run_backtest` deferred import 제거

4. `src/qbt/backtest/strategies/buy_and_hold.py` 수정:
   - [x] `create_runner` 함수 제거 (내용이 `runners.py`로 이동)

5. `src/qbt/backtest/engines/backtest_engine.py` 수정:
   - [x] `from qbt.backtest.strategies.buffer_zone import BufferStrategyParams` → `from qbt.backtest.types import BufferStrategyParams`
   - [x] `_run_backtest_for_grid` 내부 deferred import → 파일 상단 top-level import로 이동: `from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy`
   - [x] `run_buffer_strategy` 내부 deferred import 제거 (이미 top-level에 있음)

6. `src/qbt/backtest/strategies/__init__.py` 수정:
   - [x] `BufferStrategyParams` import 출처: `buffer_zone` → `types`
   - [x] `create_runner` export 유지 (buy_and_hold의 것 → Phase 5에서 제거)

7. `src/qbt/backtest/__init__.py` 수정:
   - [x] `BufferStrategyParams` import 출처: `buffer_zone` → `types`

8. `scripts/backtest/run_single_backtest.py` 수정:
   - [x] `from qbt.backtest import runners` import 추가
   - [x] `buffer_zone.create_runner(_config)` → `runners.create_buffer_zone_runner(_config)`
   - [x] `buy_and_hold.create_runner(_config)` → `runners.create_buy_and_hold_runner(_config)`

**Validation**: 테스트 스위트 전체 실행하여 회귀 없음 확인

---

### Phase 3 — HoldState 안정성 (check_buy 시그니처 + 명시적 상속)

**목표**: `check_buy` 시그니처에 `current_date`, `buy_buffer_pct` 추가 → 플레이스홀더 패턴 완전 제거. 명시적 Protocol 상속으로 PyRight 컴파일 타임 계약 강제.

**작업 내용**:

1. `src/qbt/backtest/strategies/strategy_common.py` 수정:
   - [x] `SignalStrategy.check_buy` 시그니처에 `current_date: date, buy_buffer_pct: float` 파라미터 추가
   - [x] `date` import 확인 (이미 있음)
   - [x] Docstring 업데이트

2. `src/qbt/backtest/strategies/buffer_zone.py` 수정:
   - [x] `class BufferZoneStrategy(SignalStrategy):` 명시적 상속으로 변경 (SignalStrategy import 추가)
   - [x] `check_buy` 메서드 시그니처 갱신: `current_date: date, buy_buffer_pct: float` 추가
   - [x] 첫 돌파 감지 시 플레이스홀더 제거:
     ```python
     # 변경 전
     new_hold_state: HoldState = {
         "start_date": date.min,  # 플레이스홀더
         "buffer_pct": 0.0,       # 플레이스홀더
         ...
     }
     # 변경 후
     new_hold_state: HoldState = {
         "start_date": current_date,   # 직접 설정
         "buffer_pct": buy_buffer_pct, # 직접 설정
         ...
     }
     ```

3. `src/qbt/backtest/strategies/buy_and_hold.py` 수정:
   - [x] `class BuyAndHoldStrategy(SignalStrategy):` 명시적 상속으로 변경
   - [x] `check_buy` 메서드 시그니처 갱신: `current_date: date, buy_buffer_pct: float` 추가 (여전히 무시)

4. `src/qbt/backtest/engines/backtest_engine.py` 수정:
   - [x] `strategy.check_buy(...)` 호출에 `current_date=current_date, buy_buffer_pct=current_buy_buffer_pct` 추가
   - [x] HoldState 주입 코드 제거:
     ```python
     # 제거 대상 (lines ~463-466)
     if old_hold_state is None:
         new_hold_state["start_date"] = current_date
         new_hold_state["buffer_pct"] = current_buy_buffer_pct
     ```

5. `src/qbt/backtest/engines/portfolio_engine.py` 수정:
   - [x] day-0 초기화 `strategy.check_buy(...)` 호출 (line ~605): `current_date=first_date, buy_buffer_pct=config.buy_buffer_zone_pct` 추가
   - [x] 메인 루프 `strategy.check_buy(...)` 호출 (line ~744): `current_date=current_date, buy_buffer_pct=config.buy_buffer_zone_pct` 추가
   - [x] HoldState 주입 코드 제거 (lines ~773-774):
     ```python
     # 제거 대상
     new_hold_state["start_date"] = current_date
     new_hold_state["buffer_pct"] = config.buy_buffer_zone_pct
     ```

6. `tests/test_strategy_interface.py` 수정:
   - [x] 모든 `check_buy(...)` 호출에 `current_date=date(2020,1,1), buy_buffer_pct=0.03` 인자 추가
   - [x] Phase 0에서 작성한 레드 테스트가 이제 그린이 됨을 확인

**Validation**: 테스트 스위트 전체 실행 (Phase 0 레드 테스트 2개 그린 전환 확인)

---

### Phase 4 — execute_sell_order hold_days_used 파라미터화

**목표**: 암묵적 덮어쓰기 계약 제거 — `execute_sell_order`가 `hold_days_used`를 명시적으로 요구하도록 변경.

**작업 내용**:

1. `src/qbt/backtest/engines/engine_common.py` 수정:
   - [x] `execute_sell_order` 시그니처에 `hold_days_used: int` 파라미터 추가 (기존 파라미터 이후)
   - [x] `trade_record` 생성 시 `"hold_days_used": hold_days_used` (파라미터 값 사용)
   - [x] Docstring 업데이트

2. `src/qbt/backtest/engines/backtest_engine.py` 수정:
   - [x] `execute_sell_order(...)` 호출에 `hold_days_used=entry_hold_days` 명시적 전달
   - [x] `trade_record["hold_days_used"] = entry_hold_days` 덮어쓰기 라인 제거

3. 테스트 확인:
   - [x] Phase 0에서 작성한 `test_execute_sell_order_hold_days_used_param` 테스트가 그린이 됨을 확인

**Validation**: 테스트 스위트 전체 실행

---

### Phase 5 — run_buy_and_hold 제거 (B&H 엔진 기반 전환)

**목표**: `run_buy_and_hold`를 엔진 기반으로 교체하고 관련 코드(`BuyAndHoldParams`, `resolve_params`) 삭제.

**B&H 엔진 기반 설계**:
- `create_buy_and_hold_runner`에서 dummy `BufferStrategyParams`(ma_window=1, buy_buffer=MIN, sell_buffer=MIN, hold_days=0) 생성
- `signal_df = add_single_moving_average(trade_df.copy(), 1, ma_type=DEFAULT_BUFFER_MA_TYPE)`
- `run_backtest(BuyAndHoldStrategy(), signal_df, trade_df, params, strategy_name=config.strategy_name)`
- `BuyAndHoldStrategy.check_buy()` → 항상 True 반환 (ma/band 파라미터 무시)
- `BuyAndHoldStrategy.check_sell()` → 항상 False (포지션 유지)
- 결과 signal_df: trade_df의 OHLC만 추출 (ma_1 컬럼 제외)
- `params_json`: `{"strategy": config.strategy_name, "initial_capital": ...}` (dummy MA 파라미터 노출 안 함)
- **행동 변화**: 첫 매수가 day 0 시가 → day 2 시가 (사용자 확인 완료)

**작업 내용**:

1. `src/qbt/backtest/runners.py` 수정:
   - [x] `create_buy_and_hold_runner` 내부 `run_single` 구현을 `run_backtest(BuyAndHoldStrategy(), ...)` 기반으로 교체
   - [x] `run_buy_and_hold` 관련 import 제거
   - [x] `add_single_moving_average` import 추가

2. `src/qbt/backtest/strategies/buy_and_hold.py` 수정:
   - [x] `run_buy_and_hold` 함수 제거
   - [x] `BuyAndHoldParams` 클래스 제거
   - [x] `resolve_params` 함수 제거
   - [x] 더 이상 필요 없는 import 제거 (`SLIPPAGE_RATE`, `calculate_summary`, `COL_HIGH`, `COL_LOW` 등)

3. `src/qbt/backtest/strategies/__init__.py` 수정:
   - [x] `BuyAndHoldParams`, `create_runner`, `run_buy_and_hold` exports 제거
   - [x] `BuyAndHoldConfig` export는 유지

4. `src/qbt/backtest/__init__.py` 수정:
   - [x] `BuyAndHoldParams`, `run_buy_and_hold` exports 제거
   - [x] 관련 imports 제거

5. `tests/test_buy_and_hold.py` 수정:
   - [x] `import BuyAndHoldParams`, `import run_buy_and_hold` 제거
   - [x] `TestRunBuyAndHold` 클래스 제거 (6개 메서드)
   - [x] `TestOpenPosition` 클래스 제거 (2개 메서드)
   - [x] `TestResolveParams` 클래스 제거 (1개 메서드)
   - [x] `TestCreateRunner` 클래스: `buy_and_hold.create_runner` → `runners.create_buy_and_hold_runner` 호출로 교체, monkeypatch 대상 모듈 변경
   - [x] `TestBuyAndHoldUsesTradeDF` 클래스: 엔진 기반 동작 기준으로 업데이트 (2-day delay 반영)
   - [x] 신규 테스트 추가:
     - `test_buy_and_hold_runner_open_position_present`: B&H runner 실행 시 `summary["open_position"]` 존재 확인
     - `test_buy_and_hold_runner_trades_df_empty`: 매도 없으므로 `trades_df`가 비어있음 확인
     - `test_buy_and_hold_runner_signal_df_has_ohlc_no_ma`: signal_df에 ma 컬럼 없음 확인

**Validation**: 테스트 스위트 전체 실행 (B&H 관련 테스트 모두 그린 확인)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - `types.py` 섹션: `BufferStrategyParams` dataclass 추가 설명
  - `runners.py` 섹션 신규 추가: `create_buffer_zone_runner`, `create_buy_and_hold_runner` 설명
  - `buffer_zone.py` 섹션: `BufferStrategyParams`, `create_runner` 항목 제거
  - `buy_and_hold.py` 섹션: `run_buy_and_hold`, `BuyAndHoldParams`, `resolve_params` 항목 제거
  - `engine_common.py` 섹션: `execute_sell_order` 시그니처 업데이트
  - `strategy_common.py` 섹션: `check_buy` 시그니처 업데이트
  - `constants.py` 섹션: `CALMAR_MDD_ZERO_SUBSTITUTE`, `DEFAULT_BUFFER_MA_TYPE` 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=386, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 안정성 리팩터링 — 하드코딩 제거 + 순환 의존성 완전 해결 + HoldState/execute_sell_order 계약 명확화 + B&H 엔진 통일
2. 백테스트 / 아키텍처 정리 — runners.py 분리, BufferStrategyParams 이동, check_buy 시그니처 강화
3. 백테스트 / 암묵적 계약 제거 — HoldState 플레이스홀더 + hold_days_used 덮어쓰기 패턴 제거
4. 백테스트 / 모듈 구조 개선 — deferred import 0개, 명시적 Protocol 상속, 미사용 코드 삭제
5. 백테스트 / 유지보수성 강화 — 상수화, 순환 의존성 제거, Protocol 계약 명확화, B&H 엔진 통일

---

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| `BufferStrategyParams` 이동 후 `from qbt.backtest.strategies import BufferStrategyParams` 하던 외부 import 깨짐 | `strategies/__init__.py`와 `backtest/__init__.py` 모두에서 re-export 유지하여 하위 호환성 보장 |
| `check_buy` 시그니처 변경 시 `portfolio_engine.py`의 day-0 초기화 호출 누락 가능 | Phase 3 checklist에 day-0 호출 포함, `validate_project.py --only-pyright`로 타입 에러 확인 |
| Phase 5에서 B&H tests 대량 수정 중 버그 누락 | `TestBuyAndHoldConfigs` (CONFIGS 정합성) 테스트는 변경 없이 유지하여 config 회귀 방지 |
| `execute_sell_order` 시그니처 변경 후 `portfolio_engine`이 독자 체결 로직 사용 — 영향 없음 확인 필요 | portfolio_engine은 `engine_common.execute_sell_order`를 사용하지 않으므로 영향 없음 (계획서에 명시) |

## 8) 메모(Notes)

### 핵심 결정 사항

- **방안 B 선택 (순환 의존성)**: `BufferStrategyParams` 이동 + `runners.py` 생성으로 deferred import 완전 제거. scripts import 경로 변경 필요하지만 구조가 훨씬 명확해짐.
- **B&H 2-day delay 허용**: 엔진 기반 전환으로 첫 매수가 day 2로 이동. 장기 벤치마크에서 실질 영향 미미. 사용자 확인 완료.
- **BuyAndHoldParams 제거**: `run_buy_and_hold` 제거와 함께 삭제. `resolve_params`도 함께 제거.
- **명시적 Protocol 상속 추가**: `class Foo(SignalStrategy)` 형태로 변경하여 PyRight 컴파일 타임 계약 강제.
- **B&H dummy params**: `ma_window=1`(EMA-1 = close 자체, NaN 없음), `buy_buffer=MIN_BUY_BUFFER_ZONE_PCT`, `sell_buffer=MIN_SELL_BUFFER_ZONE_PCT`, `hold_days=0`. `BuyAndHoldStrategy`가 이 값들을 무시하므로 결과에 영향 없음.
- **Phase 의존 관계**: Phase 5는 Phase 2(runners.py 존재) + Phase 3(새 check_buy 시그니처)에 의존.

### 진행 로그 (KST)

- 2026-03-21 00:00: 계획서 초안 작성 완료
- 2026-03-21 16:00: 전체 Phase 완료 — Ruff/PyRight/Pytest 전체 통과 (passed=386, failed=0, skipped=0)
