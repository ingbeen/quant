# Implementation Plan: 백테스트 4P 전환 후 리팩토링

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

**작성일**: 2026-03-13 22:00
**마지막 업데이트**: 2026-03-14 01:30
**관련 범위**: backtest, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `docs/plans/PLAN_backtest_4p_transition.md`
**선행 계획서**: `PLAN_backtest_4p_transition.md` (완료), `PLAN_backtest_cleanup.md` (완료)

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

- [x] 4P 확정 파라미터 상수를 `constants.py`에 단일 원천(Source of Truth)으로 통합한다
- [x] `load_best_grid_params()` Dead Code를 제거한다
- [x] `BaseStrategyParams` 불필요한 상속 계층을 제거한다
- [x] `BufferZoneConfig`에서 `grid_results_path` 필드를 제거하고, `override_*` 필드를 직접 파라미터명으로 변경하여 보일러플레이트를 축소한다
- [x] `resolve_buffer_params()`의 grid 폴백 분기를 제거하여 간소화한다
- [x] `__init__.py`의 공개 API(`__all__`)를 정리한다

## 2) 비목표(Non-Goals)

- `parameter_stability.py` 파일 통합 (독립 모듈로 유지, 상수 중복만 해결)
- `run_buffer_strategy()` 301줄 함수 분해 (핵심 전략 로직, "간결성: 불필요한 추상화 지양" 원칙)
- `run_walkforward.py` 모드별 실행 코드 변경 (Mode 3이 Mode 1에 의존, 현재 코드가 명시적)
- CSV 반올림 규칙 중앙화 (각 CSV 타입별 고유 규칙, 이동 시 코드 근접성 저하)
- 대시보드 앱 (`app_*.py`) 변경
- 전략 핵심 로직 (`buffer_zone_helpers.py`의 신호 감지/주문 실행/에쿼티 계산) 변경
- `walkforward.py` 비즈니스 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

PLAN_backtest_4p_transition 및 PLAN_backtest_cleanup 완료 후, 다음 리팩토링 대상이 식별되었다:

1. **상수 중복**: 4P 확정값(MA=200, buy=0.03, sell=0.05, hold=3)이 `buffer_zone.py`의 `_4P_*` 상수와 `parameter_stability.py`의 `_CURRENT_VALUES`에 이중 정의됨. 프로젝트 규칙 "상수 중복 금지 - 계층 간 중복 정의 시 즉시 통합"에 위배
2. **Dead Code**: `load_best_grid_params()` 함수가 존재하나 모든 CONFIGS의 `grid_results_path=None`이므로 실행 불가한 코드 경로. 관련 테스트(TestLoadBestGridParams 5개)도 Dead Code를 보호
3. **불필요한 추상화**: `BaseStrategyParams`가 `initial_capital` 속성 하나만 정의하는 기본 클래스이며 `BufferStrategyParams`만 상속. `BuyAndHoldParams`는 별도 정의되어 상속 효과 없음
4. **BufferZoneConfig 비대**: 8개 config 모두 `grid_results_path=None`, `override_*` 5개가 동일한 `_4P_*` 값으로 반복. config당 12줄 중 7줄이 보일러플레이트
5. **resolve_buffer_params() 복잡성**: "OVERRIDE -> grid -> DEFAULT" 3단 폴백 체인이지만, 4P 전환 후 grid 분기는 실행 불가, DEFAULT 분기도 도달 불가. 113줄 함수 중 상당 부분이 Dead Code
6. **__init__.py 누락**: `calculate_regime_summaries()`, `RegimeSummaryDict`, `MarketRegimeDict` 등이 외부에서 사용되지만 `__all__`에 미등록

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 4P 상수가 `constants.py`에 단일 정의, `buffer_zone.py`와 `parameter_stability.py`가 이를 참조
- [x] `load_best_grid_params()` 함수 및 관련 테스트 제거됨
- [x] `BaseStrategyParams` 제거, `BufferStrategyParams`에 `initial_capital` 직접 포함
- [x] `BufferZoneConfig`에서 `grid_results_path` 필드 제거됨
- [x] `BufferZoneConfig`의 `override_*` 필드가 직접 파라미터명으로 변경되고 기본값 설정됨
- [x] CONFIGS 보일러플레이트가 축소됨 (config당 필수 필드만 명시)
- [x] `resolve_buffer_params()`에서 grid 폴백 분기 제거됨
- [x] `__init__.py __all__` 정리됨
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md 파일들)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

소스 변경:
- `src/qbt/backtest/constants.py`: FIXED_4P_* 상수 5개 추가
- `src/qbt/backtest/strategies/buffer_zone.py`: `_4P_*` 상수 제거, config 필드 리네이밍, CONFIGS 축소, `resolve_params_for_config()` 간소화
- `src/qbt/backtest/strategies/buffer_zone_helpers.py`: `BaseStrategyParams` 제거, `BufferStrategyParams` 수정, `resolve_buffer_params()` 간소화
- `src/qbt/backtest/analysis.py`: `load_best_grid_params()` 제거
- `src/qbt/backtest/parameter_stability.py`: `_CURRENT_VALUES`를 `constants.py` 참조로 변경
- `src/qbt/backtest/__init__.py`: export 정리
- `src/qbt/backtest/strategies/__init__.py`: export 정리

스크립트 변경:
- `scripts/backtest/run_param_plateau_all.py`: `override_*` -> 직접 파라미터명으로 변경

테스트 변경:
- `tests/test_analysis.py`: `TestLoadBestGridParams` 클래스 제거
- `tests/test_buffer_zone.py`: config 구조 변경 반영, grid 폴백 테스트 제거/재작성
- `tests/test_buffer_zone_helpers.py`: `BaseStrategyParams` 제거 반영, `resolve_buffer_params` 테스트 수정

### 데이터/결과 영향

- 없음. 비즈니스 로직 변경 없음 (순수 리팩토링)
- 전략 실행 결과, CSV 출력, summary 구조 모두 동일

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 통합 + Dead Code 제거 + BaseStrategyParams 제거

**작업 내용**:

- [x] `src/qbt/backtest/constants.py` 수정: FIXED_4P_* 상수 5개 추가
  - `FIXED_4P_MA_WINDOW = 200`
  - `FIXED_4P_BUY_BUFFER_ZONE_PCT = 0.03`
  - `FIXED_4P_SELL_BUFFER_ZONE_PCT = 0.05`
  - `FIXED_4P_HOLD_DAYS = 3`
  - `FIXED_4P_RECENT_MONTHS = 0`
- [x] `src/qbt/backtest/strategies/buffer_zone.py` 수정: `_4P_*` 로컬 상수 제거, `constants.py`의 `FIXED_4P_*` import
- [x] `src/qbt/backtest/parameter_stability.py` 수정: `_CURRENT_VALUES` dict를 `constants.py`의 `FIXED_4P_*` 참조로 변경
- [x] `src/qbt/backtest/analysis.py` 수정: `load_best_grid_params()` 함수 제거
- [x] `src/qbt/backtest/__init__.py` 수정: `load_best_grid_params` import/export 제거
- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` 수정:
  - `BaseStrategyParams` 클래스 제거
  - `BufferStrategyParams`에 `initial_capital: float` 직접 포함 (상속 제거)
  - docstring에서 "학습 포인트" 상속 설명 제거
  - `load_best_grid_params` import 제거
- [x] `tests/test_analysis.py` 수정: `TestLoadBestGridParams` 클래스 전체 제거 (5개 테스트), import 정리
- [x] `tests/test_buffer_zone_helpers.py` 수정: `BaseStrategyParams` 관련 참조 확인 및 수정

---

### Phase 2 — BufferZoneConfig 간소화 + 폴백 체인 정리

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone.py` 수정:
  - `BufferZoneConfig` 필드 변경:
    - `grid_results_path: Path | None` 제거
    - `override_ma_window: int | None` -> `ma_window: int = FIXED_4P_MA_WINDOW`
    - `override_buy_buffer_zone_pct: float | None` -> `buy_buffer_zone_pct: float = FIXED_4P_BUY_BUFFER_ZONE_PCT`
    - `override_sell_buffer_zone_pct: float | None` -> `sell_buffer_zone_pct: float = FIXED_4P_SELL_BUFFER_ZONE_PCT`
    - `override_hold_days: int | None` -> `hold_days: int = FIXED_4P_HOLD_DAYS`
    - `override_recent_months: int | None` -> `recent_months: int = FIXED_4P_RECENT_MONTHS`
    - `ma_type: str` -> `ma_type: str = "ema"` (기본값 추가)
  - CONFIGS 리스트: config당 차이점(strategy_name, display_name, 경로)만 명시, 나머지는 기본값 활용
  - `resolve_params_for_config()`: 새 필드명에 맞게 수정
  - docstring 업데이트 (OVERRIDE/grid/DEFAULT 폴백 설명 -> 직접 파라미터 설명)
- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` 수정:
  - `resolve_buffer_params()` 간소화:
    - `grid_results_path` 파라미터 제거
    - `override_*: T | None` -> 직접 파라미터 `T` (non-Optional)
    - grid 폴백 분기 (~50줄) 제거
    - None 체크 5개 제거
    - sources 딕셔너리 간소화 ("FIXED"로 통일)
    - docstring 업데이트
- [x] `scripts/backtest/run_param_plateau_all.py` 수정:
  - `replace()` 호출의 `override_*` -> 직접 파라미터명으로 변경
  - 4개 실험 블록 각각 수정
- [x] `tests/test_buffer_zone.py` 수정:
  - `BufferZoneConfig` 생성 코드: `grid_results_path`, `override_*` -> 새 필드명
  - `test_grid_fallback_when_override_is_none()`: grid 폴백 제거로 테스트 삭제
  - `test_default_fallback_when_no_grid()`: DEFAULT 폴백 제거로 테스트 재작성 (기본값 검증으로 변경)
  - `test_override_params_used_when_set()`: 직접 파라미터 설정 검증으로 변경
  - 기타 config 생성부 일괄 수정
- [x] `tests/test_buffer_zone_helpers.py` 수정: `resolve_buffer_params()` 호출부 시그니처 변경 반영

---

### Phase 3 — __init__.py 정리 + 문서 정리 + 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/__init__.py` 수정: `__all__`에 `calculate_regime_summaries` 추가
- [x] `src/qbt/backtest/types.py` 확인: `RegimeSummaryDict`, `MarketRegimeDict` export 필요 여부 판단
  - 외부 스크립트에서 직접 import 사용 → `__init__.py`에 추가
- [x] `src/qbt/backtest/CLAUDE.md` 갱신:
  - `parameter_stability.py` 섹션: 상수 참조 변경 반영
  - `buffer_zone.py` 섹션: BufferZoneConfig 필드 변경, CONFIGS 구조 변경 반영
  - `buffer_zone_helpers.py` 섹션: BaseStrategyParams 제거, resolve_buffer_params 간소화 반영
  - `analysis.py` 섹션: load_best_grid_params 제거 반영
- [x] `scripts/CLAUDE.md` 갱신: 변경 불필요 (override/grid/DEFAULT 폴백 직접 언급 없음)
- [x] `tests/CLAUDE.md` 갱신: 변경 불필요 (TestLoadBestGridParams 직접 언급 없음)
- [x] 루트 `CLAUDE.md` 갱신: 변경 불필요 (FIXED_4P_*는 도메인 상수로 backtest/constants.py에 이미 정의)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 4P 전환 후 Dead Code 제거 + BufferZoneConfig 간소화 리팩토링
2. 백테스트 / 상수 중복 통합 + grid 폴백 제거 + config 보일러플레이트 축소
3. 백테스트 / resolve_buffer_params 간소화 + BaseStrategyParams 제거 + API 정리
4. 백테스트 / 4P 고정 완료 후 불필요한 추상화 계층 제거 리팩토링
5. 백테스트 / grid search 잔여 코드 정리 + BufferZoneConfig 필드 단순화

## 7) 리스크(Risks)

- **BufferZoneConfig 필드 리네이밍으로 인한 테스트 대량 수정**: Phase 2에서 config 생성부 일괄 수정. 테스트 수가 많으므로 누락 방지를 위해 grep 기반 전수 확인
- **resolve_buffer_params() 시그니처 변경으로 인한 호출부 누락**: `resolve_buffer_params`와 `resolve_params_for_config`의 호출부를 grep으로 전수 확인
- **run_param_plateau_all.py의 replace() 호출 변경 누락**: 4개 실험 블록 모두 확인
- **walkforward.py에서 run_grid_search 사용에 영향**: `run_grid_search`는 변경하지 않으므로 영향 없음. walkforward.py는 `resolve_buffer_params()`를 직접 호출하지 않음

## 8) 메모(Notes)

- `run_grid_search()`는 `walkforward.py`에서 여전히 사용하므로 유지
- `BestGridParams` TypedDict는 `walkforward.py`의 `select_best_calmar_params()` 반환 타입으로 유지
- 4P 상수 명명: `FIXED_4P_*` 접두사 사용 (기존 `DEFAULT_*`와 구분, "확정된 고정값"임을 명시)
- `parameter_stability.py`는 `app_parameter_stability.py` 전용 데이터 로딩 모듈로 명확한 책임이 있어 독립 유지
- `resolve_buffer_params()` 간소화 후에도 파라미터 검증과 `sources` 딕셔너리는 유지 (디버깅/로깅 가치)
- `BufferZoneConfig`의 `ma_type` 필드 기본값 "ema"는 현재 8개 config 모두 동일하므로 기본값으로 설정

### 진행 로그 (KST)

- 2026-03-13 22:00: 계획서 초안 작성
- 2026-03-14 00:30: Phase 1 완료 (상수 통합 + Dead Code 제거 + BaseStrategyParams 제거)
- 2026-03-14 01:00: Phase 2 완료 (BufferZoneConfig 간소화 + 폴백 체인 정리)
- 2026-03-14 01:30: Phase 3 완료 (__init__.py 정리 + 문서 갱신 + 최종 검증 passed=334, failed=0, skipped=0)

---
