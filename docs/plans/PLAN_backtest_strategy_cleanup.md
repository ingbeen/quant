# Implementation Plan: 백테스트 전략 리팩토링 후속 정리

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

**작성일**: 2026-02-19
**마지막 업데이트**: 2026-02-19
**관련 범위**: backtest, scripts/backtest, tests
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [x] `types.py`에서 전략 전용 타입을 해당 전략 모듈로 이동하여 `types.py`의 전략 무관성 확보
- [x] 전략명(`strategy_name`)·표시명(`display_name`) 상수화로 하드코딩 제거
- [x] `run_single_backtest.py`의 argparse choices 동적 생성 + `print_summary` logger 파라미터 제거

## 2) 비목표(Non-Goals)

- 새 전략 추가
- 비즈니스 로직 변경 (순수 구조 정리)
- 대시보드 앱(`app_single_backtest.py`) 변경
- `strategies/__init__.py` 레지스트리 패턴 전환 (YAGNI, 현재 2개 전략)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

이전 계획서(`PLAN_backtest_strategy_separation.md`, `PLAN_run_single_backtest_refactor.md`)에서 전략 파일 분리와 `run_single_backtest.py` 리팩토링을 완료했다. 후속 검증에서 다음 문제가 확인되었다:

1. **`types.py`에 전략 전용 타입 혼재**: `BuyAndHoldResultDict`, `BufferStrategyResultDict`, `EquityRecord`, `TradeRecord`, `HoldState`, `GridSearchResult`가 모두 특정 전략에서만 사용됨에도 `types.py`에 위치
2. **전략명·표시명 하드코딩**: `"buffer_zone"`, `"buy_and_hold"`, `"버퍼존 전략"`, `"Buy & Hold"` 등이 전략 모듈, 스크립트에 분산
3. **argparse choices 하드코딩**: `choices=["all", "buffer_zone", "buy_and_hold"]`가 `STRATEGY_RUNNERS`와 별도 관리
4. **`print_summary`에 불필요한 logger 파라미터**: 모듈 레벨 `logger`와 동일한 인스턴스를 파라미터로 전달

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `types.py`에 전략 전용 타입 없음 (공통 타입만 유지: `SummaryDict`, `BestGridParams`, `SingleBacktestResult`)
- [x] 각 전략 모듈에 `STRATEGY_NAME`, `DISPLAY_NAME` 상수 존재
- [x] 전략 모듈 내 하드코딩된 전략명이 상수로 교체됨
- [x] `run_single_backtest.py`의 argparse choices가 `STRATEGY_RUNNERS`에서 동적 생성
- [x] `print_summary`에서 logger 파라미터 제거
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (passed=293, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (`src/qbt/backtest/CLAUDE.md`)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직**:

- `src/qbt/backtest/types.py` — 전략 전용 타입 6개 제거
- `src/qbt/backtest/strategies/buffer_zone.py` — 타입 이동 수용 + `STRATEGY_NAME`/`DISPLAY_NAME` 상수 추가 + 하드코딩 교체
- `src/qbt/backtest/strategies/buy_and_hold.py` — 타입 이동 수용 + `STRATEGY_NAME`/`DISPLAY_NAME` 상수 추가 + 하드코딩 교체

**스크립트**:

- `scripts/backtest/run_single_backtest.py` — import 변경 + argparse 동적화 + `print_summary` logger 파라미터 제거

**문서**:

- `src/qbt/backtest/CLAUDE.md` — types.py 모듈 구성 업데이트

### 데이터/결과 영향

- 결과 파일 경로/형식 변경 없음
- 비즈니스 로직 변경 없음 → 동일 파라미터 기준 백테스트 결과 동일

## 6) 단계별 계획(Phases)

### Phase 1 — 전략별 타입 이동 + 전략명 상수화

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone.py` 변경:
  - `STRATEGY_NAME = "buffer_zone"`, `DISPLAY_NAME = "버퍼존 전략"` 상수 추가
  - `types.py`에서 이동할 타입 정의 (파일 내 직접 정의):
    - `BufferStrategyResultDict` (SummaryDict 상속)
    - `EquityRecord`
    - `TradeRecord`
    - `HoldState`
    - `GridSearchResult`
  - `from qbt.backtest.types import` 에서 이동된 타입 제거
  - 하드코딩된 `"buffer_zone"` → `STRATEGY_NAME`, `"버퍼존 전략"` → `DISPLAY_NAME` 교체 (3곳: summary dict, run_single의 strategy_name, run_single의 display_name)

- [x] `src/qbt/backtest/strategies/buy_and_hold.py` 변경:
  - `STRATEGY_NAME = "buy_and_hold"`, `DISPLAY_NAME = "Buy & Hold"` 상수 추가
  - `types.py`에서 이동할 타입 정의:
    - `BuyAndHoldResultDict` (SummaryDict 상속)
  - `from qbt.backtest.types import` 에서 이동된 타입 제거
  - 하드코딩된 `"buy_and_hold"` → `STRATEGY_NAME`, `"Buy & Hold"` → `DISPLAY_NAME` 교체 (4곳: summary dict, run_single의 strategy_name/display_name, params_json)

- [x] `src/qbt/backtest/types.py` 변경:
  - 이동된 타입 6개 제거: `BuyAndHoldResultDict`, `BufferStrategyResultDict`, `EquityRecord`, `TradeRecord`, `HoldState`, `GridSearchResult`
  - 불필요해진 import 정리 (`date` 등)
  - 남은 타입: `SummaryDict`, `BestGridParams`, `SingleBacktestResult`

- [x] 기존 테스트 통과 확인: `poetry run pytest tests/test_strategy.py tests/test_integration.py tests/test_analysis.py -v`

---

### Phase 2 — run_single_backtest.py 정리

**작업 내용**:

- [x] `scripts/backtest/run_single_backtest.py` 변경:
  - import 변경: `from qbt.backtest.strategies import buffer_zone, buy_and_hold` (모듈 직접 import)
  - `STRATEGY_RUNNERS` 레지스트리를 상수로 구성:
    ```python
    STRATEGY_RUNNERS: dict[str, Callable[[pd.DataFrame, pd.DataFrame], SingleBacktestResult]] = {
        buffer_zone.STRATEGY_NAME: buffer_zone.run_single,
        buy_and_hold.STRATEGY_NAME: buy_and_hold.run_single,
    }
    ```
  - argparse choices 동적 생성: `choices=["all", *STRATEGY_RUNNERS.keys()]`
  - `print_summary` 함수에서 `logger` 파라미터 제거, 모듈 레벨 `logger` 직접 사용
  - `print_summary` 호출부에서 `logger` 인자 제거
  - `import logging` 제거 (더 이상 사용되지 않음)

- [x] 기존 테스트 통과 확인: `poetry run pytest tests/test_strategy.py tests/test_integration.py -v`

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - types.py 모듈 설명에서 이동된 타입 제거
  - 전략 모듈 설명에 `STRATEGY_NAME`/`DISPLAY_NAME` 상수, 이동된 타입 추가
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=293, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 전략 전용 타입 이동 + 전략명 상수화 + argparse 동적화
2. 백테스트 / types.py 전략 무관화 + 전략명·표시명 하드코딩 제거
3. 백테스트 / 전략 리팩토링 후속 정리 (타입 이동, 상수화, CLI 개선)
4. 백테스트 / 전략별 타입 캡슐화 + STRATEGY_NAME/DISPLAY_NAME 상수 도입
5. 백테스트 / 전략 모듈 자기완결성 강화 (타입·상수·CLI 정리)

## 7) 리스크(Risks)

- **타입 이동 시 import 누락**: 전략 전용 타입이 예상 외 모듈에서 사용될 가능성
  - 완화: 사전 조사로 사용처 확인 완료 (전략 모듈 내부에서만 사용)
  - 완화: Phase 1에서 테스트 실행으로 즉시 검증
- **`strategies/__init__.py` 기존 export 영향**: 기존 aliased export (`buffer_zone_run_single` 등)를 유지하므로 하위 호환성 보장
- **`print_summary` logger 제거**: 모듈 레벨 logger와 동일하므로 동작 변경 없음

## 8) 메모(Notes)

### 타입 이동 대상 상세

| 타입 | 현재 위치 | 이동 대상 | 사용처 |
|------|----------|----------|--------|
| `BufferStrategyResultDict` | types.py | buffer_zone.py | buffer_zone.py만 |
| `EquityRecord` | types.py | buffer_zone.py | buffer_zone.py만 |
| `TradeRecord` | types.py | buffer_zone.py | buffer_zone.py만 |
| `HoldState` | types.py | buffer_zone.py | buffer_zone.py만 |
| `GridSearchResult` | types.py | buffer_zone.py | buffer_zone.py만 |
| `BuyAndHoldResultDict` | types.py | buy_and_hold.py | buy_and_hold.py만 |

### 하드코딩 교체 대상

| 파일 | 현재 값 | 교체 후 |
|------|---------|---------|
| buffer_zone.py:796 | `"strategy": "buffer_zone"` | `"strategy": STRATEGY_NAME` |
| buffer_zone.py:928 | `strategy_name="buffer_zone"` | `strategy_name=STRATEGY_NAME` |
| buffer_zone.py:929 | `display_name="버퍼존 전략"` | `display_name=DISPLAY_NAME` |
| buy_and_hold.py:96 | `"strategy": "buy_and_hold"` | `"strategy": STRATEGY_NAME` |
| buy_and_hold.py:144 | `"strategy": "buy_and_hold"` | `"strategy": STRATEGY_NAME` |
| buy_and_hold.py:150 | `strategy_name="buy_and_hold"` | `strategy_name=STRATEGY_NAME` |
| buy_and_hold.py:151 | `display_name="Buy & Hold"` | `display_name=DISPLAY_NAME` |
| run_single_backtest.py:48 | `"buffer_zone": buffer_zone_run_single` | `buffer_zone.STRATEGY_NAME: buffer_zone.run_single` |
| run_single_backtest.py:49 | `"buy_and_hold": buy_and_hold_run_single` | `buy_and_hold.STRATEGY_NAME: buy_and_hold.run_single` |
| run_single_backtest.py:365 | `choices=["all", "buffer_zone", "buy_and_hold"]` | `choices=["all", *STRATEGY_RUNNERS.keys()]` |

### 테스트 코드 하드코딩 유지 사유

`test_strategy.py`의 assert 문에서 `"buffer_zone"`, `"Buy & Hold"` 등의 리터럴은 의도적으로 유지한다.
테스트가 상수를 참조하면 상수 값이 잘못 변경되어도 테스트가 통과하는 문제가 발생하기 때문이다.

### 진행 로그 (KST)

- 2026-02-19: 계획서 작성 완료 (Draft)
- 2026-02-19: Phase 1~3 완료, 전체 검증 통과 (passed=293, failed=0, skipped=0)

---
