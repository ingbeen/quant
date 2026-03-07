# Implementation Plan: 버퍼존 통합 전략 모듈 생성

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-07 15:00
**마지막 업데이트**: 2026-03-07 15:00
**관련 범위**: backtest, utils, common_constants
**관련 문서**: cross_asset_validation_plan.md (§9 구현 방안), src/qbt/backtest/CLAUDE.md

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

- [x] `BufferZoneConfig` 기반 config-driven 통합 전략 모듈(`buffer_zone.py`) 생성
- [x] `common_constants.py`에 cross-asset 6개 자산 데이터 경로 + 결과 디렉토리 상수 추가
- [x] `resolve_buffer_params`의 `grid_results_path` 타입을 `Path | None`으로 확장
- [x] 통합 모듈 테스트(`test_buffer_zone.py`) 추가
- [x] 기존 모듈(`buffer_zone_tqqq.py`, `buffer_zone_qqq.py`) 유지 (하위 호환성 보장)

## 2) 비목표(Non-Goals)

- 스크립트(`scripts/`) 마이그레이션 → 후속 Plan(`PLAN_CROSS_ASSET_SCRIPT_MIGRATION`)에서 수행
- 기존 모듈(`buffer_zone_tqqq.py`, `buffer_zone_qqq.py`) 삭제 → 후속 Plan에서 수행
- 데이터 다운로드 (사용자가 `download_data.py`로 직접 실행)
- Buy & Hold 벤치마크에 신규 자산 추가
- `buffer_zone_atr_tqqq.py` 통합 (ATR 트레일링 스탑 전용 로직, 별도 유지)
- `donchian_channel_tqqq.py` 통합 (독립 프레임워크)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `buffer_zone_tqqq.py`와 `buffer_zone_qqq.py`가 거의 동일한 구조로 코드 중복이 심함
- 교차 자산 검증(cross_asset_validation_plan.md §4)을 위해 6개 추가 자산 + QQQ 3P 기준선에 동일 전략 적용 필요
- 개별 모듈 방식으로 9개(기존 2 + 신규 7) 모듈을 관리하는 것은 비효율적
- `buy_and_hold.py`의 `CONFIGS` 패턴이 이미 검증된 config-driven 접근법을 제공

### 설계 근거 (cross_asset_validation_plan.md §9.1)

| # | 결정 사항 | 선택 | 근거 |
|---|---|---|---|
| 1 | 전략 모듈 구조 | config-driven 통합 모듈 1개 | 코드 중복 제거, 확장 용이 |
| 2 | 3파라미터 엔진 | 기존 엔진 래핑 | hold_days=0, recent_months=0 내부 전달, 검증된 엔진 재사용 |
| 3 | hold_days/recent_months | 외부 인터페이스에서 제거 | cross-asset은 3파라미터만 노출, 기존은 5파라미터 유지 |
| 4 | signal ≠ trade 지원 | signal_data_path/trade_data_path 분리 | TQQQ(signal≠trade) + cross-asset(signal=trade) 모두 지원 |
| 5 | 파라미터 결정 | override → grid → DEFAULT 폴백 체인 | cross-asset은 override 고정, 기존은 폴백 체인 유지 |
| 6 | 백테스트 기간 | 각 자산 상장 이후 최대 기간 | SPY는 1993년부터 |

### CONFIGS 목록 (9개)

| # | strategy_name | signal | trade | 파라미터 결정 |
|---|---|---|---|---|
| 1 | buffer_zone_tqqq | QQQ | TQQQ (합성) | override(None) → grid → DEFAULT |
| 2 | buffer_zone_qqq | QQQ | QQQ | override(None) → grid → DEFAULT |
| 3 | buffer_zone_qqq_3p | QQQ | QQQ | 고정: MA=200, buy=3%, sell=5%, hold=0, recent=0 |
| 4 | buffer_zone_spy | SPY | SPY | 고정 (동일) |
| 5 | buffer_zone_iwm | IWM | IWM | 고정 (동일) |
| 6 | buffer_zone_efa | EFA | EFA | 고정 (동일) |
| 7 | buffer_zone_eem | EEM | EEM | 고정 (동일) |
| 8 | buffer_zone_gld | GLD | GLD | 고정 (동일) |
| 9 | buffer_zone_tlt | TLT | TLT | 고정 (동일) |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `BufferZoneConfig` dataclass + 9개 `CONFIGS` 리스트 구현
- [x] `create_runner(config)` 팩토리 함수 구현 (signal=trade 분기 포함)
- [x] `resolve_params_for_config(config)` 함수 구현
- [x] `resolve_buffer_params`의 `grid_results_path: Path | None` 타입 확장
- [x] `common_constants.py`에 13개 상수 추가 (데이터 경로 6개 + 결과 디렉토리 7개)
- [x] 기존 모듈(`buffer_zone_tqqq.py`, `buffer_zone_qqq.py`) 미변경, 기존 테스트 통과
- [x] 통합 모듈 테스트(`test_buffer_zone.py`) 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=479, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성:**

- `src/qbt/backtest/strategies/buffer_zone.py` — 통합 config-driven 전략 모듈
- `tests/test_buffer_zone.py` — 통합 모듈 테스트

**수정:**

- `src/qbt/common_constants.py` — 6개 자산 데이터 경로 + 7개 결과 디렉토리 상수 추가
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — `resolve_buffer_params` 시그니처 `Path | None` 확장 (1줄)
- `src/qbt/backtest/strategies/__init__.py` — buffer_zone 모듈 export 추가

**영향 없음 (변경 불필요):**

- `src/qbt/backtest/strategies/buffer_zone_tqqq.py` — 기존 모듈 그대로 유지
- `src/qbt/backtest/strategies/buffer_zone_qqq.py` — 기존 모듈 그대로 유지
- `scripts/backtest/*.py` — 후속 Plan에서 마이그레이션
- `tests/test_buffer_zone_tqqq.py` — 기존 테스트 그대로 통과
- `tests/test_buffer_zone_qqq.py` — 기존 테스트 그대로 통과

### 데이터/결과 영향

- 기존 결과 파일 영향 없음 (출력 포맷 동일)
- 6개 신규 자산 데이터 파일은 사용자가 `download_data.py`로 다운로드 필요

## 6) 단계별 계획(Phases)

### Phase 0 — 통합 모듈 인터페이스 테스트 선작성 (Red)

**작업 내용** (`tests/test_buffer_zone.py` 신규 생성):

- [x] `TestBufferZoneConfig` 클래스
  - [x] `test_config_frozen_dataclass` — BufferZoneConfig 인스턴스 생성 및 frozen 불변성 검증
  - [x] `test_configs_list_has_expected_count` — CONFIGS 리스트가 9개 설정을 포함하는지 검증
  - [x] `test_configs_unique_strategy_names` — 모든 strategy_name이 고유한지 검증
  - [x] `test_get_config_returns_correct_config` — `get_config("buffer_zone_tqqq")`가 올바른 설정 반환
  - [x] `test_get_config_raises_for_unknown` — 존재하지 않는 이름에 ValueError 발생
- [x] `TestResolveParamsForConfig` 클래스
  - [x] `test_override_params_used_when_set` — override 값이 모두 설정된 config에서 해당 값 사용 (cross-asset 패턴)
  - [x] `test_grid_fallback_when_override_is_none` — override=None + grid 파일 존재 시 grid 값 사용
  - [x] `test_default_fallback_when_no_grid` — override=None + grid_results_path=None 시 DEFAULT 사용
  - [x] `test_three_param_config_sets_hold_days_zero` — cross-asset config의 hold_days=0, recent_months=0 확인
- [x] `TestCreateRunner` 클래스
  - [x] `test_create_runner_returns_callable` — create_runner가 호출 가능 함수를 반환
  - [x] `test_run_single_returns_single_backtest_result` — 반환값이 SingleBacktestResult 구조 충족
  - [x] `test_signal_equals_trade_no_overlap` — signal_path == trade_path 시 extract_overlap_period 미호출
  - [x] `test_signal_differs_trade_calls_overlap` — signal_path != trade_path 시 extract_overlap_period 호출
  - [x] `test_data_info_contains_paths` — data_info에 signal_path, trade_path 포함

---

### Phase 1 — 상수 추가 + resolve_buffer_params 확장 (Green)

**작업 내용:**

- [x] `src/qbt/common_constants.py` — 데이터 경로 상수 추가 (6개)
  - `SPY_DATA_PATH`, `IWM_DATA_PATH`, `EFA_DATA_PATH`, `EEM_DATA_PATH`, `GLD_DATA_PATH`, `TLT_DATA_PATH`
  - 패턴: `STOCK_DIR / "{TICKER}_max.csv"`
- [x] `src/qbt/common_constants.py` — 결과 디렉토리 상수 추가 (7개)
  - `BUFFER_ZONE_QQQ_3P_RESULTS_DIR`, `BUFFER_ZONE_SPY_RESULTS_DIR`, `BUFFER_ZONE_IWM_RESULTS_DIR`, `BUFFER_ZONE_EFA_RESULTS_DIR`, `BUFFER_ZONE_EEM_RESULTS_DIR`, `BUFFER_ZONE_GLD_RESULTS_DIR`, `BUFFER_ZONE_TLT_RESULTS_DIR`
  - 패턴: `BACKTEST_RESULTS_DIR / "buffer_zone_{ticker_lower}"`
- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` — `resolve_buffer_params` 시그니처 변경
  - `grid_results_path: Path` → `grid_results_path: Path | None`
  - 내부: `grid_best = load_best_grid_params(grid_results_path) if grid_results_path is not None else None`
  - 기존 호출자(`buffer_zone_tqqq.py`, `buffer_zone_qqq.py`)는 `Path`를 전달하므로 하위 호환

---

### Phase 2 — 통합 모듈(buffer_zone.py) 생성 (Green)

**작업 내용** (`src/qbt/backtest/strategies/buffer_zone.py` 신규 생성):

- [x] `BufferZoneConfig` frozen dataclass 구현
  - 필드: `strategy_name`, `display_name`, `signal_data_path`, `trade_data_path`, `result_dir`, `grid_results_path` (`Path | None`), `override_ma_window` (`int | None`), `override_buy_buffer_zone_pct` (`float | None`), `override_sell_buffer_zone_pct` (`float | None`), `override_hold_days` (`int | None`), `override_recent_months` (`int | None`), `ma_type` (`str`)
- [x] `CONFIGS: list[BufferZoneConfig]` — 9개 설정 리스트
  - 기존 2개: buffer_zone_tqqq (override=None, grid=Path), buffer_zone_qqq (override=None, grid=Path)
  - QQQ 3P 기준선 1개: buffer_zone_qqq_3p (override=고정, grid=None)
  - cross-asset 6개: buffer_zone_spy/iwm/efa/eem/gld/tlt (override=고정, grid=None)
  - cross-asset 고정값: `ma_window=200, buy_buffer_zone_pct=0.03, sell_buffer_zone_pct=0.05, hold_days=0, recent_months=0`
- [x] `get_config(strategy_name: str) -> BufferZoneConfig` — 이름으로 설정 조회, 미존재 시 ValueError
- [x] `resolve_params_for_config(config: BufferZoneConfig) -> tuple[BufferStrategyParams, dict[str, str]]`
  - `resolve_buffer_params(config.grid_results_path, config.override_*, ...)` 위임
- [x] `create_runner(config: BufferZoneConfig) -> Callable[[], SingleBacktestResult]` 팩토리 함수
  - `run_single()` 클로저 반환
  - signal_path == trade_path 분기: 같으면 `trade_df.copy()`, 다르면 `extract_overlap_period()` 호출
  - `add_single_moving_average()` → `run_buffer_strategy()` → `SingleBacktestResult` 구성
  - `data_info`에 `signal_path`, `trade_path` 포함
- [x] `__init__.py`에 buffer_zone 모듈 export 추가 (`BufferZoneConfig`, `get_config`, `create_runner`, `resolve_params_for_config`)
- [x] Phase 0 테스트 전부 통과

---

### Phase 3 — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 기존 테스트(`test_buffer_zone_tqqq.py`, `test_buffer_zone_qqq.py`) 통과 확인
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / BufferZoneConfig 기반 통합 전략 모듈 생성 (cross-asset 9개 설정)
2. 백테스트 / 버퍼존 전략 config-driven 통합 모듈 + cross-asset 상수 추가
3. 백테스트 / buffer_zone.py 통합 모듈 생성 및 테스트 추가
4. 백테스트 / 교차 자산 검증용 통합 전략 모듈 + resolve_buffer_params 타입 확장
5. 백테스트 / 버퍼존 통합 모듈(CONFIGS 패턴) + 6개 자산 경로 상수 추가

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|---|---|---|
| resolve_buffer_params 시그니처 변경으로 기존 호출자 영향 | 낮음 | `Path`는 `Path \| None`의 하위 타입이므로 하위 호환. 기존 테스트로 검증 |
| cross-asset 데이터 파일 미존재 시 런타임 에러 | 중간 | 데이터 파일은 사용자가 다운로드. 상수 추가만으로는 에러 없음 |
| CONFIGS 리스트가 커져 모듈 가독성 저하 | 낮음 | 각 config가 frozen dataclass로 명시적. buy_and_hold.py 패턴과 동일 |
| __init__.py export 추가 시 순환 import | 낮음 | buffer_zone.py는 buffer_zone_helpers.py만 import. 기존 모듈과 동일 의존 관계 |

## 8) 메모(Notes)

### 핵심 결정 사항

- **모듈 파일명**: `buffer_zone.py` (기존 `buy_and_hold.py` 네이밍 패턴 일치)
- **QQQ 3P 기준선**: `buffer_zone_qqq_3p`로 기존 `buffer_zone_qqq`(5파라미터, grid 폴백)와 구분
- **기존 모듈 유지**: 이 Plan에서는 삭제하지 않아 스크립트 변경 없이 검증 가능
- **후속 Plan 의존성**: `PLAN_CROSS_ASSET_SCRIPT_MIGRATION`에서 스크립트 마이그레이션 + 기존 모듈 삭제

### 참고 문서

- `cross_asset_validation_plan.md` §9 구현 방안
- `src/qbt/backtest/strategies/buy_and_hold.py` — CONFIGS 패턴 참고

### 진행 로그 (KST)

- 2026-03-07 15:00: Plan 초안 작성

---
