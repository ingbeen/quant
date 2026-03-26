# PLAN: Strategy Registry + Config + Rebalance Policy

- 작성일: 2026-03-26 10:00
- 마지막 업데이트: 2026-03-26 14:30
- 상태: Done

---

## Goal

1. `StrategySpec` 데이터클래스 + `STRATEGY_REGISTRY` 딕셔너리를 구현하여 전략 확장 가능 구조를 확보한다.
2. `AssetSlotConfig.strategy_type` → `strategy_id`로 필드명을 변경한다 (값은 그대로 유지).
3. `portfolio_engine.py`와 `compute_portfolio_effective_start_date`의 모든 `strategy_type` 분기를 제거하고 registry 경유로 대체한다.
4. `RebalancePolicy` 클래스로 리밸런싱 정책 로직을 분리한다.

---

## Non-Goals

- `strategy_params: dict[str, Any]` 전환 금지 — `AssetSlotConfig`의 typed 필드 구조 유지
- `BufferZoneConfig`, `BuyAndHoldConfig` (단일 백테스트용) 구조 변경 없음
- `runners.py` 내부 MA 계산 로직 변경 없음 (이미 전략별 함수로 분리되어 `strategy_type` 분기 없음)
- 새 전략 추가 없음 (기존 `buffer_zone`, `buy_and_hold` 유지)
- Backward compatibility 레이어 없음 (내부 프로젝트, 완전 교체)

---

## Context

### 현재 문제

- `AssetSlotConfig.strategy_type` 하드코딩: `portfolio_engine.py`에서 총 6곳에 `if slot.strategy_type == "buffer_zone"` 분기 존재
- MA 계산 위치 분산: `_load_and_prepare_data`(portfolio_engine), `create_buffer_zone_runner`(runners) 양쪽에서 각각 `add_single_moving_average` 호출
- `compute_portfolio_effective_start_date`도 `if slot.strategy_type != "buffer_zone": continue` 분기로 MA 워밍업 로직 처리
- 리밸런싱 로직이 `_build_rebalance_intents` 함수 안에 threshold 체크 + intent 생성이 혼재

### 확정된 설계 방향

| 질문 | 결정 |
|------|------|
| Backward compat | 불필요 (완전 교체, 값은 동일) |
| strategy_params 타입 | typed 필드 유지. registry factory는 AssetSlotConfig 전체를 받음 |
| MA 계산 이동 | registry에 이동. `prepare_signal_df` + `get_warmup_periods` hook 함께 등록 |

### 설계 명세

**StrategySpec** (`strategy_registry.py` 신규):

```python
@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    create_strategy: Callable[[AssetSlotConfig], SignalStrategy]
    prepare_signal_df: Callable[[pd.DataFrame, AssetSlotConfig], pd.DataFrame]
    get_warmup_periods: Callable[[AssetSlotConfig], int]
    supports_single: bool = True
    supports_portfolio: bool = True

STRATEGY_REGISTRY: dict[str, StrategySpec] = {
    "buffer_zone": StrategySpec(...),
    "buy_and_hold": StrategySpec(...),
}
```

- `create_strategy(slot)`: BufferZoneStrategy 또는 BuyAndHoldStrategy 생성
- `prepare_signal_df(df, slot)`: buffer_zone → MA 컬럼 추가, buy_and_hold → df 그대로 반환
- `get_warmup_periods(slot)`: buffer_zone → `slot.ma_window`, buy_and_hold → `0`

**AssetSlotConfig** 변경:
- `strategy_type: Literal["buffer_zone", "buy_and_hold"]` → `strategy_id: str`
- 값(`"buffer_zone"`, `"buy_and_hold"`)은 동일, registry key와 일치

**RebalancePolicy** (`portfolio_engine.py` 내부):

```python
@dataclass(frozen=True)
class RebalancePolicy:
    monthly_threshold_rate: float
    daily_threshold_rate: float

    def get_threshold(self, is_month_start: bool) -> float: ...
    def should_rebalance(
        self, projected, slot_dict, total_equity_projected, is_month_start
    ) -> bool: ...
    def build_rebalance_intents(
        self, projected, slot_dict, total_equity_projected, current_date
    ) -> dict[str, OrderIntent]: ...
```

### 영향받는 규칙 (전체 숙지 선언)

아래 문서에 기재된 규칙을 모두 숙지하고 준수한다:

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/CLAUDE.md](../CLAUDE.md)

---

## Definition of Done

- [x] `STRATEGY_REGISTRY`에 `"buffer_zone"`, `"buy_and_hold"` 모두 등록
- [x] `prepare_signal_df`: buffer_zone → MA 컬럼 추가, buy_and_hold → 원본 반환
- [x] `get_warmup_periods`: buffer_zone → `slot.ma_window`, buy_and_hold → `0`
- [x] `AssetSlotConfig.strategy_type` → `strategy_id` 변경 완료 (모든 사용처 포함)
- [x] `portfolio_engine.py`의 모든 `strategy_type` 분기 제거 (총 6곳)
- [x] `compute_portfolio_effective_start_date`의 `strategy_type` 분기 제거
- [x] `RebalancePolicy` 클래스 분리 완료 (`should_rebalance` + `build_rebalance_intents`)
- [x] `MONTHLY_REBALANCE_THRESHOLD_RATE`, `DAILY_REBALANCE_THRESHOLD_RATE` 로컬 상수 → `RebalancePolicy` 기본값으로 이동
- [x] PyRight strict: 오류 0
- [x] Pytest: failed=0, skipped=0
- [x] Black 포맷 적용

---

## Scope

### 변경 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `src/qbt/backtest/strategy_registry.py` | **신규** | StrategySpec + STRATEGY_REGISTRY |
| `src/qbt/backtest/portfolio_types.py` | 수정 | `strategy_type` → `strategy_id` |
| `src/qbt/backtest/portfolio_configs.py` | 수정 | `strategy_type=` → `strategy_id=` |
| `src/qbt/backtest/engines/portfolio_engine.py` | 수정 | strategy 분기 제거, registry 경유, RebalancePolicy 분리 |
| `src/qbt/backtest/CLAUDE.md` | 수정 | strategy_registry, RebalancePolicy 모듈 설명 추가 |
| `tests/test_strategy_registry.py` | **신규** | StrategySpec / STRATEGY_REGISTRY 계약 테스트 |
| `tests/test_portfolio_strategy.py` | 수정 | `strategy_type` → `strategy_id` 일괄 치환 |
| `tests/test_portfolio_configs.py` | 수정 | `strategy_type` → `strategy_id` 일괄 치환 |

### README.md

변경 없음

---

## Phases

### Phase 0 (RED): STRATEGY_REGISTRY 계약 테스트 작성

**목표**: 구현 전에 registry의 핵심 계약을 테스트로 고정한다. 모두 실패(ImportError)여야 한다.

**할 일**:

- `tests/test_strategy_registry.py` 신규 작성
  - `TestStrategyRegistryKeys`: `"buffer_zone"`, `"buy_and_hold"` 키 존재
  - `TestStrategySpecCreateStrategy`:
    - buffer_zone → `BufferZoneStrategy` 반환 (SignalStrategy Protocol 구현 확인)
    - buy_and_hold → `BuyAndHoldStrategy` 반환
  - `TestStrategySpecPrepareSignalDf`:
    - buffer_zone: MA 컬럼(`ma_{ma_window}`)이 추가됨
    - buy_and_hold: df 컬럼 변화 없음
  - `TestStrategySpecGetWarmupPeriods`:
    - buffer_zone: `slot.ma_window` 반환
    - buy_and_hold: `0` 반환

**Validation**:

```bash
poetry run pytest tests/test_strategy_registry.py -v
# 예상: ImportError (strategy_registry.py 없음) → 모두 RED
```

---

### Phase 1 (GREEN): strategy_registry.py 구현

**목표**: Phase 0 테스트를 모두 통과시킨다.

**할 일**:

- `src/qbt/backtest/strategy_registry.py` 신규 작성
  - `StrategySpec` 데이터클래스 정의 (frozen=True)
  - `_create_buffer_zone_strategy(slot: AssetSlotConfig) -> SignalStrategy`
  - `_prepare_buffer_zone_signal_df(df: pd.DataFrame, slot: AssetSlotConfig) -> pd.DataFrame`
    - `add_single_moving_average(df, slot.ma_window, slot.ma_type)` 래퍼
  - `_get_buffer_zone_warmup_periods(slot: AssetSlotConfig) -> int`
    - `return slot.ma_window`
  - `_create_buy_and_hold_strategy(slot: AssetSlotConfig) -> SignalStrategy`
  - `_prepare_buy_and_hold_signal_df(df: pd.DataFrame, slot: AssetSlotConfig) -> pd.DataFrame`
    - `return df` (변경 없음)
  - `_get_buy_and_hold_warmup_periods(slot: AssetSlotConfig) -> int`
    - `return 0`
  - `STRATEGY_REGISTRY: dict[str, StrategySpec]` 구성

**Validation**:

```bash
poetry run pytest tests/test_strategy_registry.py -v
# 예상: 모두 GREEN
```

---

### Phase 2: AssetSlotConfig 변경 + 사용처 일괄 치환

**목표**: `strategy_type` → `strategy_id` 필드명을 전체 코드베이스에서 교체한다. 타입은 `str`로 변경하되, 유효성 검증은 engine에서 registry key 조회 시 ValueError로 처리한다.

**할 일**:

- `src/qbt/backtest/portfolio_types.py` 수정
  - `from typing import Literal` 에서 Literal 제거 (strategy_type에서만 사용하던 경우)
  - `strategy_type: Literal["buffer_zone", "buy_and_hold"] = "buffer_zone"` → `strategy_id: str = "buffer_zone"`
  - docstring에서 `strategy_type` 언급 → `strategy_id`로 변경

- `src/qbt/backtest/portfolio_configs.py` 수정
  - `strategy_type="buy_and_hold"` → `strategy_id="buy_and_hold"` (G-2, G-3, G-4)

- `src/qbt/backtest/engines/portfolio_engine.py` 수정
  - `slot.strategy_type` 참조 6곳 → `slot.strategy_id`로 변경 (registry 경유 전환은 Phase 3에서)
  - `signal_key` 문자열에서 `strategy_type` → `strategy_id`
  - `params_json`의 `"strategy_type"` 키 → `"strategy_id"`

- `tests/test_portfolio_strategy.py` 수정
  - `strategy_type=` → `strategy_id=`
  - `slot.strategy_type` → `slot.strategy_id`
  - `"strategy_type"` key 검증 → `"strategy_id"`

- `tests/test_portfolio_configs.py` 수정
  - `strategy_type` 관련 언급 → `strategy_id`

**Validation**:

```bash
poetry run python validate_project.py --only-pyright
# 예상: 오류 0
poetry run python validate_project.py --only-tests
# 예상: failed=0, skipped=0
```

---

### Phase 3: portfolio_engine.py strategy_id 분기 → registry 경유

**목표**: `if slot.strategy_id ==` 분기를 모두 제거하고 `STRATEGY_REGISTRY` 경유로 대체한다.

**할 일**:

- `src/qbt/backtest/engines/portfolio_engine.py` 수정

  1. `_create_strategy_for_slot` 함수 교체:
     ```python
     # 기존: if slot.strategy_id == "buffer_zone": ... elif ...: ... raise
     # 변경:
     def _create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy:
         spec = STRATEGY_REGISTRY.get(slot.strategy_id)
         if spec is None:
             raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
         return spec.create_strategy(slot)
     ```

  2. `_load_and_prepare_data` 함수 내 분기 교체:
     ```python
     # 기존: if slot.strategy_type == "buffer_zone": add_single_moving_average(...)
     # 변경:
     spec = STRATEGY_REGISTRY.get(slot.strategy_id)
     if spec is None:
         raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
     signal_df = spec.prepare_signal_df(signal_df, slot)
     ```

  3. `compute_portfolio_effective_start_date` 내 분기 교체:
     - 기존: `if slot.strategy_id != "buffer_zone": continue` + MA 컬럼 직접 체크
     - 변경: `warmup = STRATEGY_REGISTRY[slot.strategy_id].get_warmup_periods(slot)` 로 MA 워밍업 기간 조회, `warmup == 0`이면 valid_start 계산 스킵

  4. 필요 시 `strategy_registry.py` import 추가

**Validation**:

```bash
poetry run python validate_project.py --only-tests
# 예상: failed=0, skipped=0
```

---

### Phase 4: RebalancePolicy 클래스 분리

**목표**: `_build_rebalance_intents` 함수(threshold 체크 + intent 생성)를 `RebalancePolicy` 클래스로 분리한다.

**할 일**:

- `src/qbt/backtest/engines/portfolio_engine.py` 수정

  1. `RebalancePolicy` 데이터클래스 정의 (frozen=True, `portfolio_engine.py` 내부):
     ```python
     @dataclass(frozen=True)
     class RebalancePolicy:
         monthly_threshold_rate: float
         daily_threshold_rate: float

         def get_threshold(self, is_month_start: bool) -> float: ...
         def should_rebalance(
             self,
             projected: _ProjectedPortfolio,
             slot_dict: dict[str, AssetSlotConfig],
             total_equity_projected: float,
             is_month_start: bool,
         ) -> bool: ...
         def build_rebalance_intents(
             self,
             projected: _ProjectedPortfolio,
             slot_dict: dict[str, AssetSlotConfig],
             total_equity_projected: float,
             current_date: date,
         ) -> dict[str, OrderIntent]: ...
     ```

  2. 기존 로컬 상수를 `RebalancePolicy` 기본 인스턴스로 대체:
     ```python
     # 기존:
     # MONTHLY_REBALANCE_THRESHOLD_RATE: float = 0.10
     # DAILY_REBALANCE_THRESHOLD_RATE: float = 0.20
     # 변경:
     _DEFAULT_REBALANCE_POLICY = RebalancePolicy(
         monthly_threshold_rate=0.10,
         daily_threshold_rate=0.20,
     )
     ```

  3. `_build_rebalance_intents` 함수 제거 → `RebalancePolicy.build_rebalance_intents`로 대체
  4. 기존 `_build_rebalance_intents` 호출 코드 → `policy.should_rebalance(...)` + `policy.build_rebalance_intents(...)` 패턴으로 교체
  5. `run_portfolio_backtest` 내부에서 `_DEFAULT_REBALANCE_POLICY` 사용
  6. `CLAUDE.md`의 `portfolio_engine.py` 설명 업데이트 (`RebalancePolicy` 항목 추가, 로컬 상수 항목 갱신)

**Validation**:

```bash
poetry run python validate_project.py --only-tests
# 예상: failed=0, skipped=0
```

---

### Phase 5: 최종 검증 및 문서 업데이트

**목표**: 전체 검증 통과 + CLAUDE.md 업데이트

**할 일**:

- `src/qbt/backtest/CLAUDE.md` 수정
  - `### 9. strategy_registry.py` 항목 추가 (StrategySpec, STRATEGY_REGISTRY 설명)
  - `### 6. portfolio_types.py` 의 `AssetSlotConfig` 설명에서 `strategy_type` → `strategy_id`
  - `### 7. engines/portfolio_engine.py` 에서 `RebalancePolicy` 클래스 설명 추가, 로컬 상수 항목 갱신
- Black 포맷 적용

**Validation**:

```bash
poetry run black .
poetry run python validate_project.py
# 예상: passed=N, failed=0, skipped=0
```

---

## Risks

| 리스크 | 확률 | 완화책 |
|--------|------|--------|
| `Literal` 제거로 PyRight 오류 발생 | 중 | registry key 조회 시 ValueError로 런타임 검증 대체. Phase 2 Validation에서 조기 발견 |
| `compute_portfolio_effective_start_date` 의 warmup 계산 로직 변경으로 유효 시작일 오차 | 낮 | `get_warmup_periods` 반환값이 기존 `ma_col not in sdf.columns` 체크와 동등한지 테스트로 고정 |
| `RebalancePolicy.should_rebalance` 분리 시 threshold 초과 체크 이중 호출 | 낮 | `should_rebalance`가 내부적으로 임계값 체크만 수행, `build_rebalance_intents`는 threshold 체크 없이 항상 생성 |
| 테스트 파일 `strategy_type` 대규모 치환 시 빠뜨리는 케이스 | 낮 | Phase 2 Validation(PyRight + Pytest)으로 조기 발견 |

---

## Notes

### 결정 사항

- `strategy_id: str` 타입: 유효 값 검증은 `STRATEGY_REGISTRY.get(slot.strategy_id)` 조회 후 `None` 체크로 처리 (Literal 대신 런타임 검증)
- `RebalancePolicy`는 `portfolio_engine.py` 내부에 정의 (별도 파일 분리 불필요 — 포트폴리오 엔진 전용)
- `runners.py`는 이미 전략별 팩토리 함수로 분리되어 `strategy_type` 분기 없음 → 변경 대상 제외
- `StrategySpec.prepare_signal_df`는 `(pd.DataFrame, AssetSlotConfig) → pd.DataFrame` 시그니처 (typed 필드 유지 결정에 따라 `dict` 인자 없음)

### 진행 로그

- 2026-03-26 10:00 — 계획서 초안 작성
- 2026-03-26 14:30 — Phase 0~5 완료. Ruff/PyRight/Pytest 모두 통과 (passed=426, failed=0, skipped=0)

---

## Commit Messages (Final candidates)

1. `백테스트 / StrategySpec + STRATEGY_REGISTRY + RebalancePolicy 도입 — strategy_id registry 경유 + 리밸런싱 정책 클래스 분리`
2. `백테스트 / strategy_registry + RebalancePolicy — 전략 확장 구조 + 이중 트리거 정책 객체화`
3. `백테스트 / 포트폴리오 엔진 리팩토링 — STRATEGY_REGISTRY 경유 전략 팩토리 + RebalancePolicy 클래스 분리`
4. `백테스트 / strategy_id registry + RebalancePolicy — strategy_type 하드코딩 제거 + 리밸런싱 정책 캡슐화`
5. `백테스트 / 전략 레지스트리 + 리밸런싱 정책 — StrategySpec 등록 구조 + RebalancePolicy frozen dataclass`

---

```
