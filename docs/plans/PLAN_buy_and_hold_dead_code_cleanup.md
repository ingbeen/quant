# Implementation Plan: buy_and_hold resolve_params 반환값 정리 + dead code 삭제

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

**작성일**: 2026-02-19 22:00
**마지막 업데이트**: 2026-02-19 22:10
**관련 범위**: backtest, tests
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

- [x] `buy_and_hold.resolve_params()`의 불필요한 `sources` 반환값 제거
- [x] `strategies/__init__.py`의 dead 재수출 5건 삭제

## 2) 비목표(Non-Goals)

- `buffer_zone.resolve_params()`는 변경하지 않음 (sources가 `run_single`에서 실제 사용 중)
- `backtest/__init__.py`의 재수출은 변경하지 않음 (공개 API 표면 유지)
- 파일 내부에서만 사용되는 TypedDict/상수는 삭제하지 않음 (내부 타입 안전성 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. `buy_and_hold.resolve_params()`가 `(params, sources)` 튜플을 반환하지만, 유일한 런타임 호출처인 `run_single()`에서 `sources`를 `_sources`로 버림
2. `strategies/__init__.py`에서 5개 항목을 재수출하지만 외부에서 import하는 코드가 없음:
   - `BaseStrategyParams` — 외부 소비자 없음
   - `buffer_zone_resolve_params` (alias) — 외부에서 `buffer_zone.resolve_params()`로 직접 접근
   - `buffer_zone_run_single` (alias) — 외부에서 `buffer_zone.run_single()`로 직접 접근
   - `buy_and_hold_resolve_params` (alias) — 외부에서 `buy_and_hold.resolve_params()`로 직접 접근
   - `buy_and_hold_run_single` (alias) — 외부에서 `buy_and_hold.run_single()`로 직접 접근

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `buy_and_hold.resolve_params()`가 `BuyAndHoldParams`만 반환
- [x] `run_single()`에서 `_sources` 변수 제거
- [x] `strategies/__init__.py`에서 dead 재수출 5건 제거
- [x] 테스트 `test_buy_and_hold_resolve_params` 수정 (sources 검증 제거)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/strategies/buy_and_hold.py` — `resolve_params()` 반환 타입 변경, `run_single()` 호출부 수정
- `src/qbt/backtest/strategies/__init__.py` — dead 재수출 5건 삭제
- `tests/test_strategy.py` — `test_buy_and_hold_resolve_params` 수정

### 데이터/결과 영향

- 없음. 런타임 동작 변경 없음 (사용하지 않는 코드 제거만)

## 6) 단계별 계획(Phases)

Phase 0은 불필요 (인바리언트/정책 변경 없음, 단순 dead code 제거)

### Phase 1 — 구현 (그린 유지)

**작업 내용**:

- [x] `buy_and_hold.py`: `resolve_params()` 반환 타입을 `tuple[BuyAndHoldParams, dict[str, str]]` → `BuyAndHoldParams`로 변경. `sources` 딕셔너리 생성/반환 코드 제거
- [x] `buy_and_hold.py`: `run_single()`에서 `params, _sources = resolve_params()` → `params = resolve_params()`로 변경
- [x] `strategies/__init__.py`: dead 재수출 5건 삭제 (`BaseStrategyParams`, `buffer_zone_resolve_params`, `buffer_zone_run_single`, `buy_and_hold_resolve_params`, `buy_and_hold_run_single`) + `__all__`에서도 제거
- [x] `tests/test_strategy.py`: `test_buy_and_hold_resolve_params`에서 `sources` 관련 검증 제거, `params`만 검증하도록 수정

---

### Phase 2 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=293, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / buy_and_hold resolve_params 반환값 정리 + dead 재수출 삭제
2. 백테스트 / buy_and_hold dead code 정리 (미사용 반환값 + __init__ 재수출)
3. 백테스트 / 불필요한 코드 제거 (resolve_params sources + dead re-exports)
4. 백테스트 / buy_and_hold 인터페이스 단순화 + strategies __init__ 정리
5. 백테스트 / dead code 삭제 (resolve_params 반환값 + __init__.py 재수출)

## 7) 리스크(Risks)

- 낮음. 사용되지 않는 코드만 제거하므로 런타임 동작 변경 없음
- `strategies/__init__.py` 재수출 삭제 시 혹시 놓친 외부 import가 있을 수 있음 → validate_project.py로 검증

## 8) 메모(Notes)

- `buffer_zone.resolve_params()`는 `run_single()`에서 `sources`를 `params_json`에 실제 사용하므로 변경 대상 아님
- `backtest/__init__.py`의 재수출(`BufferStrategyParams`, `BuyAndHoldParams`, `run_buffer_strategy`, `run_buy_and_hold`, `run_grid_search`)은 공개 API 표면으로 유지

### 진행 로그 (KST)

- 2026-02-19 22:00: 계획서 작성
- 2026-02-19 22:10: 전체 구현 완료, validate_project.py 통과 (passed=293, failed=0, skipped=0)
