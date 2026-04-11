# Implementation Plan: QBT Live - Step 2 데이터 모델 + 상수

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

**작성일**: 2026-04-11 12:35
**마지막 업데이트**: 2026-04-11 12:50
**관련 범위**: live (신규 도메인)
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (설계서 — 특히 부록 B, 5.1)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 2 체크리스트)
- [docs/plans/PLAN_qbt_live_step01_skeleton.md](PLAN_qbt_live_step01_skeleton.md) (선행 Step)
- [live/CLAUDE.md](../../live/CLAUDE.md) (live 도메인 가이드)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) (QBT 백테스트 타입 재사용 파악용)

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

- [x] 목표 1: 설계서 부록 B에 정의된 모든 데이터 모델을 `live/src/live/models.py` 에 정의
- [x] 목표 2: live 도메인 상수를 `live/src/live/constants.py` 에 정의 (DRIFT 임계값, 포트폴리오 ID, 경로 기본값, signal→trade 매핑 빌더 등)
- [x] 목표 3: PendingOrderDict 에 `execute_on` 필드가 없음을 테스트로 고정
- [x] 목표 4: model / actual 필드가 AssetLiveState 에서 명시적으로 분리되어 있음을 테스트로 고정
- [x] 목표 5: `LIVE_PORTFOLIO_ID` 및 signal→trade 매핑이 QBT 코어 `PORTFOLIO_CONFIGS` 와 정합함을 테스트로 고정 (SSoT 원칙)

## 2) 비목표(Non-Goals)

- `state.py` 구현 (Step 3)
- `daily_runner.py` 구현 (Step 7)
- `drift.py` 구현 (Step 8)
- 실제 JSON 직렬화/역직렬화 로직 (Step 3)
- 외부 네트워크 호출
- QBT 본체(`src/qbt/`) 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- Step 1 에서 생성한 스켈레톤 파일(`constants.py`, `models.py`)을 실제 정의로 채워야 Step 3 이후 구현이 가능
- 설계서 부록 B 에는 dataclass 시그니처가 명시되어 있으나 일부 필드(SignalDetection 내부, AssetDrift)는 미정의 → 추가 설계 필요
- QBT 본체에 이미 정의된 타입(`OrderIntent`, `ExecutionResult`, `HoldState`, `PendingOrder`) 의 재사용 여부 결정 필요 → live 신규 정의는 **중복 금지**, QBT 본체 타입은 **import 재사용**

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (부록 B, 5.1, 8장, 14장)

### 확정된 설계 선택 (사용자 합의)

1. **SignalDetection**: dataclass 로 정의. 필드: `state`, `close`, `upper_band`, `lower_band`, `ema_200`, `ema_distance_pct`. 알림(200일선 근접도) 및 차트에서 재사용.
2. **AssetDrift**: 표준 필드 — `asset_id`, `model_shares`, `actual_shares`, `shares_diff`, `model_value`, `actual_value`, `value_diff`, `drift_pct`.
3. **PendingOrderDict**: 설계서 명시대로 `TypedDict` (JSON 왕복 단순, `execute_on` 없음).
4. **경로 상수**: CLI 파라미터로 전달. `constants.py` 에는 `DEFAULT_LIVE_STATE_DIR = Path("qbt-live-state")` 기본값만 정의.
5. **타임스탬프**: ISO 8601 KST 문자열 (`str`). 설계서 그대로.
6. **LIVE_TICKERS / 포트폴리오 구성**: QBT 코어 `PORTFOLIO_CONFIGS` 만 재사용 (SSoT). live 측에는 `LIVE_PORTFOLIO_ID = "portfolio_q2_2xs"` 와 `build_signal_trade_map()` 함수만 제공.

## 4) 완료 조건(Definition of Done)

- [x] `live/src/live/models.py` 에 설계서 부록 B 의 모든 dataclass / TypedDict 정의 완료
- [x] `live/src/live/constants.py` 에 live 도메인 상수 및 `build_signal_trade_map()` 함수 정의 완료
- [x] `PendingOrderDict` 에 `execute_on` 필드가 없음을 테스트로 고정
- [x] `AssetLiveState` 의 `model_*` / `actual_*` 필드 분리 테스트 고정
- [x] QBT 코어 타입(`OrderIntent`, `ExecutionResult`, `HoldState`) 은 import 로 재사용 (live 에서 중복 정의 금지)
- [x] `build_signal_trade_map()` 결과가 `PORTFOLIO_CONFIGS` 의 Q-2-2XS 슬롯 구성과 일치함을 테스트로 고정
- [x] `live/tests/test_models.py` 작성 및 통과
- [x] `live/tests/test_constants.py` 작성 및 통과
- [x] `poetry run python validate_project.py` 통과 (passed=559, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 관련 문서 체크박스 업데이트 (TODO Step 2, 계획서 상태)
- [x] 추가: `pytest.ini` 및 `validate_project.py` 에 `live/tests/` 경로 포함 (pytest 수집 누락 방지)

## 5) 변경 범위(Scope)

### 변경 대상 파일

#### 신규 작성 (내용 채우기)

- `live/src/live/models.py` (현재 docstring 만 있음 → 본 Step 에서 구현)
- `live/src/live/constants.py` (현재 docstring 만 있음 → 본 Step 에서 구현)

#### 신규 생성 (테스트)

- `live/tests/test_models.py`
- `live/tests/test_constants.py`

#### 수정

- `docs/TODO_QBT_LIVE.md` (Step 2 체크박스 체크)
- `live/CLAUDE.md` (필요 시 models/constants 핵심 책임 업데이트)

#### README 변경 여부

- `README.md`: **변경 없음** (Step 24 에서 문서화)

### 데이터/결과 영향

- 없음 (데이터 모델 정의만, 실제 실행 로직 없음)
- 기존 `tests/` 결과에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 계약/불변조건 테스트 선작성 (레드 허용) ✓ 완료

> 데이터 모델의 "필드 분리", "SSoT 정합성", "execute_on 부재" 는 절대 규칙이므로 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `live/tests/test_models.py` 에 다음 테스트 작성 (구현 전에는 ImportError 로 red):
  - `test_pending_order_dict_has_no_execute_on` — `PendingOrderDict.__annotations__` 에 `execute_on` 키가 없음
  - `test_pending_order_dict_required_keys` — `asset_id, intent_type, signal_date, current_amount, target_amount, delta_amount, target_weight, hold_days_used, reason` 모두 존재
  - `test_asset_live_state_has_model_and_actual_fields_separated` — `model_shares, model_avg_entry_price, model_entry_date, actual_shares, actual_avg_entry_price, actual_entry_date` 모두 존재
  - `test_live_state_has_both_model_and_actual_cash` — `shared_cash_model` 과 `shared_cash_actual` 분리
  - `test_live_state_has_required_metadata` — `schema_version, portfolio_id, created_at, updated_at` 존재
  - `test_buffer_zone_state_fields` — `prev_upper, prev_lower, hold_state, last_buy_buffer_pct, last_hold_days_used, schema_version` 필드 검증
  - `test_signal_detection_fields` — `state, close, upper_band, lower_band, ema_200, ema_distance_pct`
  - `test_signal_detection_state_literal` — `state` 가 `"buy" | "sell" | "hold"` 중 하나만 허용
  - `test_actual_fill_fields` — `asset_id, direction, actual_price, actual_shares, trade_date, input_time_kst, memo, rtdb_key, reason`
  - `test_daily_result_fields` — `execution_date, updated_state, updated_applied_fill_ids, signals, order_intents, executions, rebalance_triggered, model_equity, actual_equity, drift_pct, ema_distances, notification_body, pending_fill_reminders, chart_series`
  - `test_chart_series_fields` — `dates, close, ema_200, upper_band, lower_band, buy_signals, sell_signals, user_buys, user_sells`
  - `test_drift_report_fields` — `model_equity, actual_equity, drift_pct, per_asset, recommendation`
  - `test_asset_drift_fields` — `asset_id, model_shares, actual_shares, shares_diff, model_value, actual_value, value_diff, drift_pct`
  - `test_imports_reuse_qbt_order_intent` — `live.models.OrderIntent is qbt.backtest.engines.portfolio_planning.OrderIntent` (동일 객체 재사용 확인)
  - `test_imports_reuse_qbt_execution_result` — 동일
- [x] `live/tests/test_constants.py` 에 다음 테스트 작성:
  - `test_live_portfolio_id_matches_qbt_config` — `LIVE_PORTFOLIO_ID` 가 `PORTFOLIO_CONFIGS` 에 존재하는 실험명
  - `test_drift_thresholds_are_ratios` — `DRIFT_WARNING_RATIO = 0.03`, `DRIFT_CORRECTION_RATIO = 0.05` (0~1 소수)
  - `test_drift_warning_less_than_correction` — warning < correction
  - `test_default_live_state_dir_is_path` — `DEFAULT_LIVE_STATE_DIR` 은 `Path` 인스턴스
  - `test_applied_fill_ids_max_age_days` — `APPLIED_FILL_IDS_MAX_AGE_DAYS = 90`
  - `test_build_signal_trade_map_matches_q2_2xs` — 반환 dict 키/값이 Q-2-2XS 슬롯의 `signal_data_path` / `trade_data_path` 에서 파생된 티커명과 일치
  - `test_build_signal_trade_map_returns_immutable_copy` — 반환값 수정이 원본에 영향 없음

### Phase 1 — constants.py 구현 (그린 유지)

**작업 내용**:

- [x] `live/src/live/constants.py` 구현:
  - `LIVE_PORTFOLIO_ID: str = "portfolio_q2_2xs"`
  - `DRIFT_WARNING_RATIO: float = 0.03` (drift 3% 이상은 주의)
  - `DRIFT_CORRECTION_RATIO: float = 0.05` (drift 5% 이상은 보정 필요)
  - `APPLIED_FILL_IDS_MAX_AGE_DAYS: int = 90`
  - `DEFAULT_LIVE_STATE_DIR: Path = Path("qbt-live-state")`
  - `DEFAULT_DATA_STOCK_SUBDIR: Path = Path("data/stock")`
  - `DEFAULT_LIVE_STATE_FILENAME: str = "live_state.json"`
  - `DEFAULT_APPLIED_FILL_IDS_FILENAME: str = "applied_fill_ids.json"`
  - `SCHEMA_VERSION: int = 1`
  - `KST_TZ_NAME: str = "Asia/Seoul"`
  - `build_signal_trade_map() -> dict[str, str]`: `PORTFOLIO_CONFIGS` 에서 Q-2-2XS 슬롯을 찾아 `{signal_ticker: trade_ticker}` 매핑을 빌드. 티커는 경로(`Path`)의 `stem` 에서 첫 단어(`TICKER_...`)를 추출하거나, 더 안정적인 방법으로 추출.
  - `get_live_portfolio_config()`: `get_portfolio_config(LIVE_PORTFOLIO_ID)` 의 래퍼

### Phase 2 — models.py 구현 (그린 유지)

**작업 내용**:

- [x] QBT 본체 타입 import (재사용):
  - `from qbt.backtest.engines.portfolio_planning import OrderIntent`
  - `from qbt.backtest.engines.portfolio_execution import ExecutionResult`
  - `from qbt.backtest.strategies.buffer_zone_helpers import HoldState`
- [x] dataclass / TypedDict 정의:
  - `PendingOrderDict(TypedDict)`: `asset_id, intent_type, signal_date, current_amount, target_amount, delta_amount, target_weight, hold_days_used, reason` (execute_on 없음)
  - `BufferZoneState(@dataclass)`: `prev_upper, prev_lower, hold_state, last_buy_buffer_pct, last_hold_days_used, schema_version=1`
  - `AssetLiveState(@dataclass)`: `asset_id, model_shares, model_avg_entry_price, model_entry_date, actual_shares, actual_avg_entry_price, actual_entry_date, pending_order, signal_state, entry_hold_days, buffer_zone_state`
  - `LiveState(@dataclass)`: `schema_version, portfolio_id, last_signal_date, last_model_execution_date, last_rebalance_date, shared_cash_model, shared_cash_actual, assets, created_at, updated_at`
  - `ActualFill(@dataclass)`: `asset_id, direction, actual_price, actual_shares, trade_date, input_time_kst, memo, rtdb_key, reason`
  - `SignalDetection(@dataclass)`: `state: Literal["buy", "sell", "hold"]`, `close, upper_band, lower_band, ema_200, ema_distance_pct`
  - `ChartSeries(@dataclass)`: `dates, close, ema_200, upper_band, lower_band, buy_signals, sell_signals, user_buys, user_sells`
  - `AssetDrift(@dataclass)`: `asset_id, model_shares, actual_shares, shares_diff, model_value, actual_value, value_diff, drift_pct`
  - `DriftReport(@dataclass)`: `model_equity, actual_equity, drift_pct, per_asset, recommendation`
  - `DailyResult(@dataclass)`: `execution_date, updated_state, updated_applied_fill_ids, signals, order_intents, executions, rebalance_triggered, model_equity, actual_equity, drift_pct, ema_distances, notification_body, pending_fill_reminders, chart_series`
- [x] Phase 0 테스트 통과 확인

### Phase 3 — 문서 동기화

**작업 내용**:

- [x] `docs/TODO_QBT_LIVE.md` Step 2 체크박스 체크
- [x] `live/CLAUDE.md` 의 "모듈별 역할 요약" 에 constants / models 의 구체 책임 추가 (필요 시) — 기존 요약이 충분히 일치하여 추가 수정 없음

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행 및 결과 기록
- [x] DoD 체크리스트 최종 업데이트
- [x] plan 상태 Done 으로 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=559, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `live / 데이터 모델 및 상수 정의 (Step 2)`
2. `live / models.py 전체 dataclass + constants.py 상수 추가`
3. `live / 설계서 부록 B 데이터 모델 구현 + SSoT 테스트`
4. `live / PendingOrderDict / LiveState / DailyResult 정의`
5. `live / QBT 코어 타입 재사용 + live 도메인 모델 신설`

## 7) 리스크(Risks)

- **QBT 본체 타입 재사용 시 순환 import 위험**: `models.py` 가 `qbt.backtest.engines.*` 를 import 하는 순간 live 가 qbt 에 의존. Step 7 의 `daily_runner.py` 도 동일하게 QBT 코어를 import 할 예정이므로 일관된 의존 방향 유지.
  - 완화책: live → qbt 단방향만 허용. qbt 가 live 를 import 하는 일이 없도록 확인.
- **SignalDetection 의 `state` literal 타입 검증이 pyright strict 에서 막힘**: `Literal["buy", "sell", "hold"]` 사용 시 strict mode 에서 엄격히 검사됨. 테스트에서 문자열 리터럴 직접 전달 시 잘 작동해야 함.
  - 완화책: dataclass 필드 타입 명시 + 생성 시 검증 (`__post_init__`).
- **`build_signal_trade_map()` 티커 추출 방식이 `PORTFOLIO_CONFIGS` 경로 규칙에 의존**: `AssetSlotConfig.signal_data_path` 는 `Path` 객체이며 파일명 형식은 `{TICKER}_max.csv` 또는 `{TICKER}_{START}_{END}.csv`.
  - 완화책: 경로 `stem` 에서 첫 `_` 이전 부분을 대문자화하여 티커로 사용. 테스트로 Q-2-2XS 기준 SPY/QQQ/GLD/TLT 와 SSO/QLD/GLD/TLT 매핑이 맞는지 검증.

## 8) 메모(Notes)

### 주요 결정 사항

- SignalDetection 상세 dataclass (B안), AssetDrift 표준 필드 (B안), PendingOrderDict TypedDict (A안), 경로 CLI 파라미터 (C안), timestamp str (A안), 포트폴리오 QBT 코어 재사용 (C안)
- QBT 본체 타입 재사용: `OrderIntent`, `ExecutionResult`, `HoldState`
- `LIVE_PORTFOLIO_ID = "portfolio_q2_2xs"` 는 단일 실험 고정. 전략 변경 시 이 상수만 업데이트.

### 진행 로그 (KST)

- 2026-04-11 12:35: 계획서 초안 작성, 사용자 선택지 반영 완료
- 2026-04-11 12:40: Phase 0 테스트 52개 선작성 (test_models.py 38개 + test_constants.py 14개)
- 2026-04-11 12:45: Phase 1 constants.py 구현 완료 (LIVE_PORTFOLIO_ID, DRIFT 임계값, 경로 기본값, build_signal_trade_map)
- 2026-04-11 12:47: Phase 2 models.py 구현 완료 (QBT 코어 타입 import 재사용 + live 전용 10개 dataclass/TypedDict)
- 2026-04-11 12:48: live/tests/ 52개 테스트 통과 확인
- 2026-04-11 12:50: black + validate_project 통과 (passed=559, failed=0, skipped=0)
- 2026-04-11 12:50: pytest.ini / validate_project.py 에 live/tests 경로 포함 수정 (수집 누락 방지)

---
