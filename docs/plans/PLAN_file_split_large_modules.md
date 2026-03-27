# Implementation Plan: 대형 모듈 파일 분리

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

**작성일**: 2026-03-27 00:00
**마지막 업데이트**: 2026-03-27 12:00
**관련 범위**: backtest, tqqq, tests
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

- [x] 1000줄 이상 대형 파일 5개를 책임 단위로 분리하여 가독성/유지보수성 향상
- [x] 분리 후 기존 동작 완전 보존 (공개 API 변경 없음, 테스트 전량 통과)
- [x] `tests/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md` 신규 파일 구조 반영

## 2) 비목표(Non-Goals)

- 로직 변경, 버그 수정, 신규 기능 추가
- 신규 헬퍼 함수 추출 (기존 함수 이동만 수행)
- `app_rate_spread_lab.py` 분리 (제외)
- 공개 API 시그니처 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 5개 파일이 1000줄을 초과하여 AI 모델이 한 번에 읽지 못함 (분할 읽기 → 토큰/시간 낭비)
- 단일 파일에 서로 다른 책임이 혼재 (예: portfolio_engine.py에 planning/rebalance/execution/data 혼재)
- 테스트 실패 시 원인 파악이 느림 (planning 문제인지 execution 문제인지 구분 불가)

### 분리 대상 파일 및 분리 후 구조

| 원본 파일 | 줄 수 | 분리 후 파일 수 |
|-----------|-------|----------------|
| `src/qbt/backtest/engines/portfolio_engine.py` | 1,173 | 5개 |
| `tests/test_portfolio_strategy.py` | 2,774 | 4개 |
| `tests/test_buffer_zone_helpers.py` | 1,449 | 4개 |
| `tests/test_tqqq_simulation.py` | 1,441 | 3개 |
| `tests/test_backtest_walkforward.py` | 1,302 | 4개 |

#### portfolio_engine.py → 5개 파일

모두 `src/qbt/backtest/engines/` 아래에 생성한다.

| 신규 파일 | 포함 내용 |
|-----------|----------|
| `portfolio_planning.py` | `OrderIntent`, `_ProjectedPortfolio`, `_create_strategy_for_slot`, `_compute_portfolio_equity`, `_generate_signal_intents`, `_compute_projected_portfolio`, `_merge_intents` |
| `portfolio_rebalance.py` | `RebalancePolicy`, `_DEFAULT_REBALANCE_POLICY`, `_is_first_trading_day_of_month` |
| `portfolio_execution.py` | `_AssetState`, `_ExecutionResult`, `_execute_orders` |
| `portfolio_data.py` | `_load_and_prepare_data`, `_validate_portfolio_config`, `_build_combined_equity` |
| `portfolio_engine.py` (facade) | `compute_portfolio_effective_start_date`, `run_portfolio_backtest` |

#### test_portfolio_strategy.py → 4개 파일

| 신규 파일 | 포함 클래스 |
|-----------|------------|
| `test_portfolio_backtest_scenarios.py` | TestQQQTQQQSharedSignal, TestPortfolioEquityFormula, TestMonthlyRebalancing, TestB1CashBuffer, TestInvalidConfig, TestNoOverlapPeriod, TestSingleAssetPortfolio, TestC1FullCashOnSell, TestStartDateConstraint, TestComputeEffectiveStartDate, TestCacheKeyWithDifferentMAParams |
| `test_portfolio_strategy_types.py` | TestStrategyTypeBehavior, TestStrategyType |
| `test_portfolio_planning.py` | _MockBuyStrategy, _MockSellStrategy, _MockHoldStrategy, TestOrderIntentModel, TestGenerateSignalIntents, TestComputeProjectedPortfolio, TestBuildRebalanceIntents, TestMergeIntents, TestDualTriggerThreshold |
| `test_portfolio_execution.py` | TestPartialSellInvariant, TestRebalancingTopUpBuy, TestWeightRecoveryAfterRebalancing, TestRebalancedColumnMeaning, TestExecuteOrders |

헬퍼 함수 배치 원칙:
- `_make_stock_df`, `_make_stock_df_with_sell`, `_make_portfolio_config` → `test_portfolio_backtest_scenarios.py`
- `_make_flat_price_df`, `_make_sell_signal_df` → `test_portfolio_strategy_types.py`
- 각 파일에서만 필요한 헬퍼는 해당 파일 내부에 재정의 (conftest.py로 올리지 않음)

#### test_buffer_zone_helpers.py → 4개 파일

| 신규 파일 | 포함 클래스 |
|-----------|------------|
| `test_buffer_zone_contracts.py` | TestBuyBufferZonePctField, TestUpperLowerBandSeparation |
| `test_buffer_zone_run.py` | TestRunBufferStrategy, TestRunGridSearch |
| `test_buffer_zone_execution_rules.py` | TestExecutionTiming, TestForcedLiquidation, TestOpenPosition, TestCoreExecutionRules, TestBacktestAccuracy |
| `test_buffer_zone_dual_ticker.py` | TestDualTickerStrategy |

#### test_tqqq_simulation.py → 3개 파일

| 신규 파일 | 포함 클래스 |
|-----------|------------|
| `test_tqqq_simulation_cost_model.py` | TestCalculateDailyCost, TestValidateFfrCoverage, TestCalculateDailyCostWithDynamicExpense, TestSoftplusFunctions, TestDynamicFundingSpread |
| `test_tqqq_simulation_core.py` | TestSimulate, TestSimulateValidation, TestSimulateOvernightOpen |
| `test_tqqq_simulation_outputs.py` | TestCalculateValidationMetrics, TestSaveDailyComparisonCsv |

`TestSimulateOvernightOpen`은 `simulate()` 본체 계약이므로 core에 배치한다.

#### test_backtest_walkforward.py → 4개 파일

| 신규 파일 | 포함 클래스 |
|-----------|------------|
| `test_walkforward_windows.py` | TestGenerateWfoWindows, TestRollingWfoWindows (+ `_make_stock_df` 헬퍼) |
| `test_walkforward_schedule.py` | TestParamsSchedule, TestBuildParamsSchedule, TestRunWalkforward |
| `test_walkforward_selection.py` | TestCalmarSelection, TestCalmarSelectionMinTrades, TestWfeCagr, TestWfeCalmarRobust |
| `test_walkforward_summary.py` | TestCalculateWfoModeSummary, TestProfitConcentration, TestJsonRounding |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 5개 원본 파일이 계획서 기준으로 분리됨
- [x] 분리된 모든 파일에서 임포트 오류 없음
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료
- [x] `tests/CLAUDE.md` 파일 구조 업데이트
- [x] `src/qbt/backtest/CLAUDE.md` engines 섹션 업데이트
- [x] `src/qbt/backtest/engines/__init__.py` 모듈 목록 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**생성:**
- `src/qbt/backtest/engines/portfolio_planning.py`
- `src/qbt/backtest/engines/portfolio_rebalance.py`
- `src/qbt/backtest/engines/portfolio_execution.py`
- `src/qbt/backtest/engines/portfolio_data.py`
- `tests/test_portfolio_backtest_scenarios.py`
- `tests/test_portfolio_strategy_types.py`
- `tests/test_portfolio_planning.py`
- `tests/test_portfolio_execution.py`
- `tests/test_buffer_zone_contracts.py`
- `tests/test_buffer_zone_run.py`
- `tests/test_buffer_zone_execution_rules.py`
- `tests/test_buffer_zone_dual_ticker.py`
- `tests/test_tqqq_simulation_cost_model.py`
- `tests/test_tqqq_simulation_core.py`
- `tests/test_tqqq_simulation_outputs.py`
- `tests/test_walkforward_windows.py`
- `tests/test_walkforward_schedule.py`
- `tests/test_walkforward_selection.py`
- `tests/test_walkforward_summary.py`

**수정:**
- `src/qbt/backtest/engines/portfolio_engine.py` (facade로 축소)
- `src/qbt/backtest/engines/__init__.py` (모듈 목록 업데이트)

**삭제:**
- `tests/test_portfolio_strategy.py`
- `tests/test_buffer_zone_helpers.py`
- `tests/test_tqqq_simulation.py`
- `tests/test_backtest_walkforward.py`

**문서:**
- `tests/CLAUDE.md` (파일 목록 업데이트)
- `src/qbt/backtest/CLAUDE.md` (engines 모듈 목록 업데이트)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 없음. 순수 코드 구조 변경이며 공개 API 시그니처 불변.

## 6) 단계별 계획(Phases)

### Phase 1 — portfolio_engine.py 분리 + test_portfolio_strategy.py 분리

portfolio_engine.py의 private helper를 test에서 로컬 임포트로 직접 참조하므로,
소스 분리와 테스트 분리를 동일 Phase에서 수행한다.

**작업 내용**:

- [x] `portfolio_planning.py` 생성 (OrderIntent, ProjectedPortfolio, create_strategy_for_slot, compute_portfolio_equity, generate_signal_intents, compute_projected_portfolio, merge_intents 이동)
- [x] `portfolio_rebalance.py` 생성 (RebalancePolicy, DEFAULT_REBALANCE_POLICY, is_first_trading_day_of_month 이동)
- [x] `portfolio_execution.py` 생성 (AssetState, ExecutionResult, execute_orders 이동)
- [x] `portfolio_data.py` 생성 (load_and_prepare_data, validate_portfolio_config, build_combined_equity 이동)
- [x] `portfolio_engine.py` facade로 축소 (4개 신규 모듈 임포트, 공개 API 2개만 유지)
- [x] `test_portfolio_backtest_scenarios.py` 생성 (시나리오 테스트 + 공통 헬퍼 이동, 임포트 경로 업데이트)
- [x] `test_portfolio_strategy_types.py` 생성 (전략 타입 테스트 이동, 임포트 경로 업데이트)
- [x] `test_portfolio_planning.py` 생성 (planning/rebalance 테스트 이동, 임포트 경로 업데이트)
- [x] `test_portfolio_execution.py` 생성 (execution 테스트 이동, 임포트 경로 업데이트)
- [x] `tests/test_portfolio_strategy.py` 삭제

**Validation**:

```bash
poetry run pytest tests/test_portfolio_backtest_scenarios.py tests/test_portfolio_planning.py tests/test_portfolio_strategy_types.py tests/test_portfolio_execution.py -v
```

---

### Phase 2 — test_buffer_zone_helpers.py 분리

**작업 내용**:

- [x] `test_buffer_zone_contracts.py` 생성 (TestBuyBufferZonePctField, TestUpperLowerBandSeparation 이동)
- [x] `test_buffer_zone_run.py` 생성 (TestRunBufferStrategy, TestRunGridSearch 이동)
- [x] `test_buffer_zone_execution_rules.py` 생성 (TestExecutionTiming, TestForcedLiquidation, TestOpenPosition, TestCoreExecutionRules, TestBacktestAccuracy 이동)
- [x] `test_buffer_zone_dual_ticker.py` 생성 (TestDualTickerStrategy 이동)
- [x] `tests/test_buffer_zone_helpers.py` 삭제

**Validation**:

```bash
poetry run pytest tests/test_buffer_zone_contracts.py tests/test_buffer_zone_run.py tests/test_buffer_zone_execution_rules.py tests/test_buffer_zone_dual_ticker.py -v
```

---

### Phase 3 — test_tqqq_simulation.py 분리

**작업 내용**:

- [x] `test_tqqq_simulation_cost_model.py` 생성 (TestCalculateDailyCost, TestValidateFfrCoverage, TestCalculateDailyCostWithDynamicExpense, TestSoftplusFunctions, TestDynamicFundingSpread 이동)
- [x] `test_tqqq_simulation_core.py` 생성 (TestSimulate, TestSimulateValidation, TestSimulateOvernightOpen 이동)
- [x] `test_tqqq_simulation_outputs.py` 생성 (TestCalculateValidationMetrics, TestSaveDailyComparisonCsv 이동)
- [x] `tests/test_tqqq_simulation.py` 삭제

**Validation**:

```bash
poetry run pytest tests/test_tqqq_simulation_cost_model.py tests/test_tqqq_simulation_core.py tests/test_tqqq_simulation_outputs.py -v
```

---

### Phase 4 — test_backtest_walkforward.py 분리

**작업 내용**:

- [x] `test_walkforward_windows.py` 생성 (TestGenerateWfoWindows, TestRollingWfoWindows 이동)
- [x] `test_walkforward_schedule.py` 생성 (TestParamsSchedule, TestBuildParamsSchedule, TestRunWalkforward 이동)
- [x] `test_walkforward_selection.py` 생성 (TestCalmarSelection, TestCalmarSelectionMinTrades, TestWfeCagr, TestWfeCalmarRobust 이동)
- [x] `test_walkforward_summary.py` 생성 (TestCalculateWfoModeSummary, TestProfitConcentration, TestJsonRounding 이동)
- [x] `tests/test_backtest_walkforward.py` 삭제

**Validation**:

```bash
poetry run pytest tests/test_walkforward_windows.py tests/test_walkforward_schedule.py tests/test_walkforward_selection.py tests/test_walkforward_summary.py -v
```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `tests/CLAUDE.md` 파일 목록 업데이트 (신규 파일 추가, 삭제 파일 제거)
- [x] `src/qbt/backtest/CLAUDE.md` engines 모듈 목록 업데이트 (신규 4개 모듈 추가)
- [x] `src/qbt/backtest/engines/__init__.py` 모듈 목록 업데이트
- [x] README.md 변경 없음 확인
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=426, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 대형 모듈 파일 분리 — portfolio_engine + 테스트 4종 책임 단위로 분리
2. 백테스트 / 파일 분리 리팩토링 — portfolio_engine planning/rebalance/execution/data 계층 분리
3. 백테스트 / 1000줄 초과 파일 분리 — 소스 1개 + 테스트 4개 파일 책임 분리
4. 백테스트 / 모듈 분리(동작 동일) — 임포트 경로 업데이트 + 린트/포맷 정리
5. 백테스트 / 파일 구조 정리 — 대형 모듈 분리 및 CLAUDE.md 문서 업데이트

## 7) 리스크(Risks)

- **임포트 순환 참조**: 4개 신규 모듈 간 순환 임포트 발생 가능. 의존 방향: `portfolio_engine` → `portfolio_planning/rebalance/execution/data` (단방향 유지 필수)
- **로컬 임포트 누락**: test_portfolio_strategy.py의 테스트 메서드 내부 로컬 임포트가 많아 (약 35개), 분리 시 임포트 경로 변경 누락 가능. Phase 1 Validation으로 검증.
- **PyRight 타입 체크**: private 심볼 임포트 시 `# pyright: ignore[reportPrivateUsage]` 주석 유지 필요.

## 8) 메모(Notes)

### 주요 결정사항

- `RebalancePolicy`는 실질적 동작(build_rebalance_intents)을 포함하므로 `portfolio_rebalance.py`에 배치 (models 불가).
- `OrderIntent`, `_ProjectedPortfolio`는 planning 결과물이므로 `portfolio_planning.py`에 배치 (execution 불가).
- `TestSimulateOvernightOpen`은 `simulate()` 본체 계약 → `test_tqqq_simulation_core.py` (metrics 불가).
- softplus/spread 테스트는 비용 모델의 일부 → `test_tqqq_simulation_cost_model.py` (단독 파일 불필요).
- `test_backtest_walkforward.py`는 4분할 (windows/schedule/selection/summary) — 수정 이유가 4개 축으로 명확히 다름.
- 신규 헬퍼 함수 추출(load_slot_frames 등)은 이 plan 범위 밖. 별도 plan으로 처리.

### 진행 로그 (KST)

- 2026-03-27 00:00: plan 초안 작성
- 2026-03-27 12:00: 전 Phase 완료. validate_project.py passed=426, failed=0, skipped=0. private 심볼 접두사 제거(_→공개)로 PyRight cross-module 오류 해소.

---
