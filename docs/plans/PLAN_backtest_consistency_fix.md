# Implementation Plan: 백테스트 도메인 정합성 점검 — 문서/코드 최소 수정

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

**작성일**: 2026-03-25 00:00
**마지막 업데이트**: 2026-03-25 01:00
**관련 범위**: backtest
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

- [ ] `src/qbt/backtest/CLAUDE.md`를 현재 코드 기준으로 정확히 반영한다
  - `run_backtest` 4번째 인자 `params` → `initial_capital: float` 수정
  - 섹션 번호 뒤섞임(7/8/10/9/11) 재정렬
- [ ] `buffer_zone.py`의 불필요한 로컬 import 제거 (메서드 내 → 최상단으로 이동)

## 2) 비목표(Non-Goals)

- `run_backtest` 시그니처 자체를 변경하는 것 (이미 `initial_capital: float`로 구현 완료)
- `run_buffer_strategy` 제거 (WFO 경로에서 유효하게 사용 중)
- 테스트 추가 (동작 변경 없음, 문서+코드 정리만)
- `portfolio_engine.py`, `walkforward.py` 등 다른 파일 수정

## 3) 배경/맥락(Context)

### 실제 불일치 분류

코드 분석 결과:

**코드상 구현은 되어 있으나 문서가 뒤처진 항목:**

1. `run_backtest` 시그니처 불일치
   - CLAUDE.md: `run_backtest(strategy, signal_df, trade_df, params, ...)`
   - 실제 코드: `run_backtest(strategy, signal_df, trade_df, initial_capital: float, ...)`
   - 배경: `PLAN_backtest_stability_refactor.md`의 Non-Goal("run_backtest 시그니처에서 BufferStrategyParams 타입 의존성 제거")로 분류됐으나, 실제 구현 시 `initial_capital: float`로 이미 변경되어 있음. 문서만 미반영.

2. 섹션 번호 뒤섞임
   - 현재: `### 7. portfolio_types.py` → `### 8. engines/` → `### 10. portfolio_configs.py` → `### 9. strategies/` → `### 11. runners.py`
   - 코드 구조와 무관한 가독성 이슈

**단순 잔여물 (코드):**

3. `buffer_zone.py`의 로컬 import
   - `check_buy()` (line 348), `check_sell()` (line 443) 내부에 `from qbt.common_constants import COL_CLOSE` 존재
   - 순환 의존성 이유 없음 (`common_constants`는 backtest 모듈을 import하지 않음)
   - `buffer_zone.py`는 이미 최상단에서 `qbt.common_constants`를 import 중 → `COL_CLOSE`만 추가하면 됨
   - 이전 리팩터링 과정의 잔여물로 판단

**유지하기로 한 항목 (변경 없음):**

- `run_buffer_strategy`: WFO에서 직접 호출 경로로 유효하게 사용 중, 제거 안 함
- `backtest/__init__.py`: `run_buffer_strategy`, `run_grid_search` export — CLAUDE.md에 미기술이지만 backtest 패키지 공개 API로 자연스러운 구조
- `runners.py` docstring의 "기존" 상태 설명: 역사적 맥락으로 남겨두는 것이 적절

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `src/qbt/backtest/CLAUDE.md`의 `run_backtest` 4번째 인자가 `initial_capital: float`로 정확히 기술됨
- [x] `src/qbt/backtest/CLAUDE.md`의 섹션 번호가 순서대로 정렬됨
- [x] `buffer_zone.py`의 로컬 import 제거 완료 (최상단으로 이동)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/CLAUDE.md` — 문서 업데이트
- `src/qbt/backtest/strategies/buffer_zone.py` — 로컬 import 정리

### 데이터/결과 영향

- 없음 (동작 변경 없음)

## 6) 단계별 계획(Phases)

### Phase 1 — CLAUDE.md 문서 업데이트 + buffer_zone.py 코드 정리

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 수정
  - `run_backtest` 시그니처에서 `params` → `initial_capital: float`로 변경
  - 섹션 번호 재정렬 (7→6 portfolio_types, 8→7 engines, 10→8 portfolio_configs, 9 strategies 유지, 11→10 runners)
- [x] `buffer_zone.py` 수정
  - `check_buy()` 내부의 `from qbt.common_constants import COL_CLOSE` 제거
  - `check_sell()` 내부의 `from qbt.common_constants import COL_CLOSE` 제거
  - 최상단 import에 `COL_CLOSE` 추가

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=389, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / CLAUDE.md 정합성 수정 — run_backtest 시그니처 + 로컬 import 정리
2. 백테스트 / 문서-코드 불일치 수정 — initial_capital 시그니처 반영 + buffer_zone local import 제거
3. 백테스트 / 구현 정합성 점검 — CLAUDE.md 업데이트 + 잔여물 정리
4. 백테스트 / 정합성 수정 (문서 업데이트 + 코드 잔여물 제거)
5. 백테스트 / run_backtest 시그니처 문서 반영 + buffer_zone.py 로컬 import 정리

## 7) 리스크(Risks)

- 없음 (동작 변경 없이 문서+로컬 import 정리만)

## 8) 메모(Notes)

### 유지 결정 내역

- `run_buffer_strategy` 유지: walkforward.py(`build_params_schedule` 스케줄 기반 WFO)에서 직접 호출하는 유효 경로. 제거 불필요.
- `backtest/__init__.py`의 `run_buffer_strategy`/`run_grid_search` export: CLAUDE.md에 기술되어 있지 않지만 패키지 공개 API로서 올바른 구조. 문서에 추가하지 않아도 됨 (엔진 함수는 스크립트에서 직접 import).
- `runners.py` docstring의 역사적 맥락("기존" 주석): 삭제하지 않음. 리팩터링 배경을 이해하는 데 도움이 됨.

### 진행 로그 (KST)

- 2026-03-25 00:00: 계획서 작성
