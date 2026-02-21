# Implementation Plan: test_strategy.py 1:1 분할

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

**작성일**: 2026-02-20 22:00
**마지막 업데이트**: 2026-02-21 00:10
**관련 범위**: tests, backtest
**관련 문서**: `tests/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] `test_strategy.py` (1,887줄, 12개 클래스)를 소스 모듈과 1:1 대응하는 4개 파일로 분할
- [x] 모든 기존 테스트의 동작을 그대로 유지 (로직 변경 없음)
- [x] `tests/CLAUDE.md`와 `src/qbt/backtest/CLAUDE.md` 문서 업데이트

## 2) 비목표(Non-Goals)

- 테스트 로직 변경 또는 새로운 테스트 추가
- 소스 코드(`src/qbt/`) 변경
- 테스트 커버리지 변경
- conftest.py 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `test_strategy.py`가 1,887줄로 비대하여 탐색/유지보수가 어려움
- `backtest/strategies/` 하위 4개 소스 모듈이 `test_strategy.py` 하나에 N:1로 묶여 있음
- 프로젝트의 나머지 모듈은 모두 1:1 대응을 유지 중

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `tests/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 4개 테스트 파일 생성 완료 (test_buffer_zone_helpers.py, test_buffer_zone_tqqq.py, test_buffer_zone_qqq.py, test_buy_and_hold.py)
- [x] test_strategy.py 삭제 완료
- [x] 기존 테스트 수/커버리지 동일 유지 (테스트 누락/중복 없음) — 분할 전/후 모두 53개 (parametrize 포함)
- [x] `poetry run python validate_project.py` 통과 (passed=301, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`tests/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `tests/test_strategy.py` — 삭제
- `tests/test_buffer_zone_helpers.py` — 신규 생성
- `tests/test_buffer_zone_tqqq.py` — 신규 생성
- `tests/test_buffer_zone_qqq.py` — 신규 생성
- `tests/test_buy_and_hold.py` — 신규 생성
- `tests/CLAUDE.md` — 폴더 구조 및 테스트 파일 목록 업데이트
- `src/qbt/backtest/CLAUDE.md` — 테스트 커버리지 섹션 업데이트

### 데이터/결과 영향

- 없음 (테스트 코드만 재구성, 출력 스키마/결과 변경 없음)

## 6) 단계별 계획(Phases)

### Phase 1 — 4개 테스트 파일 생성 (그린 유지)

**작업 내용**:

각 클래스를 소스 모듈 기준으로 분배합니다. 혼합 클래스(`TestDualTickerStrategy`, `TestResolveParams`, `TestRunSingle`)는 메서드 단위로 분배합니다.

#### 1-1. `tests/test_buffer_zone_helpers.py` (핵심 전략 로직, ~1,200줄 예상)

대상 소스: `src/qbt/backtest/strategies/buffer_zone_helpers.py`

이동할 클래스/메서드:

| 클래스 | 라인 | 비고 |
|--------|------|------|
| `TestCalculateRecentBuyCount` | 168–217 | 전체 이동 |
| `TestRunBufferStrategy` | 219–453 | 전체 이동 |
| `TestExecutionTiming` | 455–589 | 전체 이동 |
| `TestForcedLiquidation` | 592–635 | 전체 이동 |
| `TestCoreExecutionRules` | 637–980 | 전체 이동 |
| `TestBacktestAccuracy` | 982–1186 | 전체 이동 |
| `TestRunGridSearch` | 1188–1297 | 전체 이동 |
| `TestDualTickerStrategy` | 1299–1490 | **3개 메서드만** (test_buy_and_hold_uses_trade_df 제외) |

임포트:
```python
from datetime import date
import pandas as pd
import pytest
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    PendingOrderConflictError,
    _calculate_recent_buy_count,
    run_buffer_strategy,
)
```

추가 임포트 (일부 클래스 내 지역 임포트 유지):
- `from qbt.backtest.analysis import add_single_moving_average` (TestBacktestAccuracy 등에서 사용)
- `from qbt.backtest.strategies.buffer_zone_helpers import ...` (PendingOrder, _check_pending_conflict, DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY 등)
- `from qbt.backtest.constants import ...` (COL_* 상수, TestRunGridSearch에서 사용)

- [x] 파일 생성
- [x] 모듈 docstring 작성

#### 1-2. `tests/test_buffer_zone_tqqq.py` (~200줄 예상)

대상 소스: `src/qbt/backtest/strategies/buffer_zone_tqqq.py`

이동할 클래스/메서드:

| 원본 클래스 | 메서드 | 새 클래스명 |
|------------|--------|-----------|
| `TestResolveParams` | `test_buffer_zone_resolve_params_default` | `TestResolveParams` |
| `TestResolveParams` | `test_buffer_zone_resolve_params_override` | `TestResolveParams` |
| `TestResolveParams` | `test_buffer_zone_resolve_params_grid` | `TestResolveParams` |
| `TestRunSingle` | `test_buffer_zone_tqqq_run_single_returns_result` | `TestRunSingle` |

임포트:
```python
from datetime import date
import pandas as pd
import pytest
```
(나머지는 기존 메서드 내 지역 임포트 유지)

- [x] 파일 생성
- [x] 모듈 docstring 작성

#### 1-3. `tests/test_buffer_zone_qqq.py` (~80줄 예상)

대상 소스: `src/qbt/backtest/strategies/buffer_zone_qqq.py`

이동할 클래스/메서드:

| 원본 클래스 | 메서드 | 새 클래스명 |
|------------|--------|-----------|
| `TestRunSingle` | `test_buffer_zone_qqq_run_single_returns_result` | `TestRunSingle` |

임포트:
```python
from datetime import date
import pandas as pd
import pytest
```

- [x] 파일 생성
- [x] 모듈 docstring 작성

#### 1-4. `tests/test_buy_and_hold.py` (~400줄 예상)

대상 소스: `src/qbt/backtest/strategies/buy_and_hold.py`

이동할 클래스/메서드:

| 원본 클래스 | 메서드/전체 | 새 클래스명 |
|------------|-----------|-----------|
| `TestRunBuyAndHold` | 전체 (5개 메서드) | `TestRunBuyAndHold` |
| `TestDualTickerStrategy` | `test_buy_and_hold_uses_trade_df` | `TestBuyAndHoldUsesTradeDF` |
| `TestResolveParams` | `test_buy_and_hold_resolve_params` | `TestResolveParams` |
| `TestRunSingle` | `test_buy_and_hold_qqq_create_runner_returns_result` | `TestCreateRunner` |
| `TestRunSingle` | `test_buy_and_hold_tqqq_create_runner_returns_result` | `TestCreateRunner` |
| `TestBuyAndHoldConfigs` | 전체 (4개 메서드) | `TestBuyAndHoldConfigs` |

임포트:
```python
from datetime import date
import pandas as pd
import pytest
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldParams,
    run_buy_and_hold,
)
```

- [x] 파일 생성
- [x] 모듈 docstring 작성

---

### Phase 2 — test_strategy.py 삭제 (그린 유지)

**작업 내용**:

- [x] `tests/test_strategy.py` 삭제
- [x] 삭제 전 테스트 수 확인 (53개 테스트, parametrize 포함), 분할 후 합계 동일 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `tests/CLAUDE.md` 업데이트:
  - 폴더 구조에서 `test_strategy.py` → 4개 파일로 변경
  - "핵심 로직 보호" 근거 위치 목록 업데이트
  - "테스트 커버리지" 참조 업데이트
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - "테스트 커버리지" 섹션의 주요 테스트 파일 목록 변경
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / test_strategy.py 소스 모듈 1:1 대응 4개 파일 분할
2. 테스트 / 백테스트 전략 테스트 파일 1:1 분리 + 문서 반영
3. 정리 / test_strategy.py → 4개 모듈별 테스트로 재구성
4. 테스트 / 전략 테스트 1:1 분할 리팩토링 (동작 동일)
5. 백테스트 / 테스트 파일 구조 개선 — 소스 모듈별 1:1 분리

## 7) 리스크(Risks)

- **테스트 누락**: 혼합 클래스 분배 시 메서드를 빠뜨릴 위험 → Phase 2에서 테스트 수 합계 검증으로 방지
- **임포트 누락**: 지역 임포트를 사용하는 테스트 메서드 이동 시 임포트 빠뜨림 → 분할 후 즉시 pytest 실행으로 검증
- **문서 불일치**: CLAUDE.md 업데이트 누락 → DoD 체크리스트에 포함

## 8) 메모(Notes)

### 테스트 수 검증표

분할 전: 12개 클래스, 37개 테스트 메서드

| 새 파일 | 클래스 수 | 메서드 수 |
|---------|----------|----------|
| test_buffer_zone_helpers.py | 8 | 24 |
| test_buffer_zone_tqqq.py | 2 | 4 |
| test_buffer_zone_qqq.py | 1 | 1 |
| test_buy_and_hold.py | 5 | 8 |
| **합계** | **16** | **37** |

클래스 수가 12→16으로 증가하는 이유: 혼합 클래스 3개(`TestDualTickerStrategy`, `TestResolveParams`, `TestRunSingle`)가 파일별로 분리되면서 개별 클래스로 생성됨

### 진행 로그 (KST)

- 2026-02-20 22:00: 계획서 초안 작성
- 2026-02-21 00:10: 전체 구현 완료, validate_project.py 통과 (passed=301, failed=0, skipped=0)

---
