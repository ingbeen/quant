# Implementation Plan: dict[str, Any] → TypedDict 리팩토링

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-06 (KST)
**마지막 업데이트**: 2026-02-07 (KST)
**관련 범위**: backtest, tqqq, utils, common_constants
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] `src/` 내 `dict[str, Any]` 사용을 `TypedDict`로 대체하여 타입 안전성 향상
- [x] 상수 파일에 `Final` 어노테이션 추가하여 PyRight 리터럴 타입 추론 활성화
- [x] 리팩토링 전후 런타임 동작 100% 동일 보장 (TypedDict는 컴파일 타임 전용)

## 2) 비목표(Non-Goals)

- `parallel_executor.py`의 제네릭 `Any` 변경 (의도적 범용 설계)
- `cli_helpers.py`, `logger.py`의 래퍼 패턴 `Any` 변경
- `meta_manager.py`의 `MetaDict = dict[str, Any]` 변경 (JSON 범용)
- `tests/`, `scripts/` 내 타입 힌트 변경
- CLAUDE.md에 TypedDict 가이드라인 추가 (별도 작업)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- PyRight strict 모드 사용 중이나 `reportUnknown*` 5개 규칙을 `none`으로 설정하여 `Any` 경고 없음
- `src/` 내 **58회** `Any` 사용 중, 이 중 약 **20~25회**는 구조가 고정된 딕셔너리에 불필요하게 사용
- `dict[str, Any]`는 키 존재 여부와 값 타입 정보를 잃어 IDE 자동완성과 타입 체크 무력화
- TypedDict 적용 시 딕셔너리 구조가 코드 자체로 문서화됨

### 핵심 기술 결정

**1. TypedDict 선택 근거**: 컴파일 타임 전용 → 런타임 동작 변경 0%

**2. `Final` 어노테이션 필요 이유**:
- 상수 `COL_MA_WINDOW = "ma_window"` 사용 시, PyRight는 `str`로 추론
- `Final` 적용 시 `Literal["ma_window"]`로 추론 → TypedDict 키 매칭 가능
- `Final`도 런타임 영향 0% (재할당 방지 + 타입 추론 개선)

**3. 딕셔너리 구성 패턴 변경**:
- 기존: `summary = calculate_summary(...); summary["strategy"] = "buy_and_hold"` (점진적 추가)
- 변경: `summary = {**calculate_summary(...), "strategy": "buy_and_hold"}` (스프레드 구성)
- 동일한 딕셔너리 생성, TypedDict 호환

**4. TypedDict 파일 배치 (기존 상수 스코핑 규칙 준용)**:
- 도메인 내 공유: `backtest/types.py`, `tqqq/types.py`

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `backtest/types.py` 생성 (7개 TypedDict 정의)
- [x] `tqqq/types.py` 생성 (5개 TypedDict 정의)
- [x] 상수 파일 3개에 `Final` 어노테이션 적용
- [x] `analysis.py`, `strategy.py` → TypedDict 적용
- [x] `simulation.py`, `analysis_helpers.py` → TypedDict 적용
- [x] `pd.Series[Any]` → `pd.Series[float]` 수정 (analysis.py:138)
- [x] 기존 테스트 전체 통과 (동작 변경 없음 확인)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**신규 생성 (2개):**
- `src/qbt/backtest/types.py` (~70줄)
- `src/qbt/tqqq/types.py` (~70줄)

**수정 (7개):**
- `src/qbt/common_constants.py` — `Final` 추가 (~19개 상수)
- `src/qbt/backtest/constants.py` — `Final` 추가 (~23개 상수)
- `src/qbt/backtest/analysis.py` — 반환 타입 + `pd.Series[Any]` 수정
- `src/qbt/backtest/strategy.py` — `dict[str, Any]` → TypedDict (~11곳)
- `src/qbt/tqqq/constants.py` — `Final` 추가 (KEY_*, COL_* 등 ~60개 상수)
- `src/qbt/tqqq/simulation.py` — `dict[str, Any]` → TypedDict (~14곳)
- `src/qbt/tqqq/analysis_helpers.py` — `dict[str, Any]` → TypedDict (~5곳)

**미변경:**
- `src/qbt/utils/parallel_executor.py` (범용 설계 유지)
- `src/qbt/utils/cli_helpers.py` (래퍼 패턴 유지)
- `src/qbt/utils/logger.py` (래퍼 패턴 유지)
- `src/qbt/utils/meta_manager.py` (JSON 범용 유지)
- `tests/` 전체 (동작 변경 없으므로 수정 불필요)
- `scripts/` 전체

### 데이터/결과 영향

- **없음**: TypedDict와 Final은 컴파일 타임 전용. 런타임 출력/CSV/메타데이터 동일.

## 6) 단계별 계획(Phases)

### Phase 1 — backtest 도메인 (상수 Final + TypedDict)

**작업 내용**:

- [x] `src/qbt/common_constants.py`: 모든 상수에 `Final` 추가, `from typing import Final` 임포트
- [x] `src/qbt/backtest/constants.py`: 모든 상수에 `Final` 추가
- [x] `src/qbt/backtest/types.py` 생성:

```python
# TypedDict 정의 목록
SummaryDict          # calculate_summary() 반환 (12키, start_date/end_date는 NotRequired)
EquityRecord         # _record_equity() 반환 (Date, equity, position, buffer_zone_pct, upper_band, lower_band)
TradeRecord          # _execute_sell_order() 거래 기록 (11키)
HoldState            # hold_state 상태 딕셔너리 (4키)
GridSearchResult     # _run_buffer_strategy_for_grid() 반환 (10키, COL_* 값 기반)
BuyAndHoldResultDict(SummaryDict)      # + strategy
BufferStrategyResultDict(SummaryDict)  # + strategy, ma_window, buffer_zone_pct, hold_days
```

- [x] `src/qbt/backtest/analysis.py` 수정:
  - `calculate_summary()` 반환 타입: `dict[str, Any]` → `SummaryDict`
  - line 138: `pd.Series[Any]` → `pd.Series[float]`
  - `from typing import Any` 제거 (더 이상 사용하지 않으면)

- [x] `src/qbt/backtest/strategy.py` 수정:
  - `_record_equity()` 반환: `EquityRecord`
  - `_execute_sell_order()` 반환 튜플: `tuple[int, float, TradeRecord]`
  - `trades: list[TradeRecord]`, `equity_records: list[EquityRecord]`
  - `hold_state: HoldState | None`
  - `run_buy_and_hold()` 반환: `tuple[pd.DataFrame, BuyAndHoldResultDict]`
    - 점진적 `summary["strategy"] = ...` → 스프레드 패턴 `{**base, "strategy": ...}`
  - `run_buffer_strategy()` 반환: `tuple[pd.DataFrame, pd.DataFrame, BufferStrategyResultDict]`
    - 동일하게 스프레드 패턴 적용
  - `_run_buffer_strategy_for_grid()` 반환: `GridSearchResult`
  - `param_combinations: list[dict[str, BufferStrategyParams]]` (Any → BufferStrategyParams)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=250, failed=0, skipped=0)

---

### Phase 2 — tqqq 도메인 (상수 Final + TypedDict)

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`: 모든 상수에 `Final` 추가 (KEY_*, COL_*, DEFAULT_*, PATH 등)
  - 주의: `__all__` 리스트는 Final 미적용
- [x] `src/qbt/tqqq/types.py` 생성:

```python
# TypedDict 정의 목록
ValidationMetricsDict      # calculate_validation_metrics() 반환 (12키, KEY_* 값 기반)
CostModelCandidateDict(ValidationMetricsDict)   # + leverage, spread
SoftplusCandidateDict(ValidationMetricsDict)    # + a, b, leverage
SimulationCacheDict        # WORKER_CACHE 구조 (9키: ffr_dict, expense_dict 등)
WalkforwardSummaryDict     # run_walkforward_validation() 요약 통계 (11키)
```

- [x] `src/qbt/tqqq/simulation.py` 수정:
  - `calculate_validation_metrics()` 반환: `ValidationMetricsDict`
  - `_evaluate_cost_model_candidate()` 반환: `CostModelCandidateDict`
  - `_evaluate_softplus_candidate()` 반환: `SoftplusCandidateDict`
  - `find_optimal_cost_model()` 반환: `list[CostModelCandidateDict]`
  - `cache_data` 구성 시 `SimulationCacheDict` 타입 어노테이션 적용
  - `run_walkforward_validation()` 반환: `tuple[pd.DataFrame, WalkforwardSummaryDict]`

- [x] `src/qbt/tqqq/analysis_helpers.py` 수정:
  - `save_walkforward_summary()` 파라미터: `Mapping[str, float | int]` → `WalkforwardSummaryDict`

**Validation**:

- [x] `poetry run python validate_project.py` (passed=250, failed=0, skipped=0)

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=250, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 타입 안전성 / dict[str, Any] → TypedDict 리팩토링 + 상수 Final 적용
2. 타입 안전성 / TypedDict 도입으로 딕셔너리 구조 명시화 (동작 동일)
3. 리팩토링 / Any 타입 사용 최소화 (TypedDict + Final 어노테이션)
4. 타입 힌트 개선 / 구조화된 딕셔너리 타입 정의 및 상수 Final 적용
5. 코드 품질 / TypedDict 기반 타입 안전성 강화 (런타임 변경 없음)

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| `Final` 추가 시 PyRight 새로운 에러 발생 | 낮음 | Phase별 즉시 검증, `Final`은 타입을 좁히므로 기존 코드에 호환 |
| 스프레드 패턴 변경 시 딕셔너리 키 누락 | 낮음 | TypedDict가 컴파일 타임에 누락 감지, 기존 테스트가 런타임 검증 |
| `cast()` 사용 증가 (WORKER_CACHE) | 낮음 | 기존에도 `cast` 사용 중 (simulation.py:18), 최소한으로 적용 |

## 8) 메모(Notes)

### 변경 후 예상 `Any` 현황

| 파일 | 변경 전 | 변경 후 | 비고 |
|------|---------|---------|------|
| backtest/analysis.py | 3 | 0 | TypedDict + pd.Series[float] |
| backtest/strategy.py | 11 | 0~1 | TypedDict (param_combinations 잔여 가능) |
| tqqq/simulation.py | 14 | 2~3 | TypedDict + cast (WORKER_CACHE 잔여) |
| tqqq/analysis_helpers.py | 5 | 0~1 | TypedDict |
| utils/parallel_executor.py | 19 | 19 | 미변경 (범용) |
| utils/cli_helpers.py | 2 | 2 | 미변경 (래퍼) |
| utils/logger.py | 2 | 2 | 미변경 (래퍼) |
| utils/meta_manager.py | 2 | 2 | 미변경 (JSON) |
| **합계** | **58** | **~28** | **약 30개 제거 (52% 감소)** |

### 진행 로그 (KST)

- 2026-02-06: 계획서 초안 작성, Phase 1 시작
- 2026-02-06: Phase 1 완료 (backtest 도메인)
- 2026-02-07: Phase 2 완료 (tqqq 도메인)
- 2026-02-07: Phase 3 완료 (최종 검증), 상태 Done
