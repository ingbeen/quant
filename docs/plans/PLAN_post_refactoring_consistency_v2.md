# Implementation Plan: 리팩토링 후 문서/주석/코드 정합성 복원 v2

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

**작성일**: 2026-03-13 15:00
**마지막 업데이트**: 2026-03-13 16:00
**관련 범위**: backtest, tqqq, scripts, tests, docs
**관련 문서**: CLAUDE.md(루트), src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [x] 대규모 리팩토링 후 남은 14건의 문서/주석/코드 불일치를 전부 수정
- [x] Dead code 제거 (CSCV/PBO/DSR TypedDict, ATR 테스트, Donchian Channel 코드)
- [x] 삭제된 스크립트 참조 수정 (app_rate_spread_lab.py)
- [x] 문서(CLAUDE.md, README) 정합성 복원

## 2) 비목표(Non-Goals)

- 기능 변경 또는 새 기능 추가
- 테스트 로직 변경 (dead code 제거 외)
- 런타임 동작 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

6건의 대규모 리팩토링 후 문서/주석/소스코드 간 불일치 14건이 발견됨:
- Dead Code 3건 (A-1~A-3)
- 삭제된 스크립트 참조 1건 (B-1, 8곳)
- 문서-코드 불일치 6건 (C-1~C-6)
- 금지된 주석 패턴 4건 (D-1~D-4)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 14건 불일치 모두 수정
- [x] Dead code 제거 완료 (CSCV/PBO/DSR TypedDict, ATR 테스트, Donchian dead code)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 관련 CLAUDE.md 문서 업데이트 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

Phase 1 (소스코드):
- `src/qbt/backtest/types.py` — CSCV/PBO/DSR TypedDict 삭제 + docstring 수정 (A-1, C-6)
- `src/qbt/tqqq/simulation.py` — docstring 수정 + 금지 패턴 주석 수정 (C-1, D-3, D-4)
- `tests/test_wfo_stitched.py` — ATR 테스트/docstring 수정 (A-2)
- `tests/test_backtest_walkforward.py` — Phase 표현 제거 (D-1)
- `tests/test_buffer_zone_helpers.py` — Phase 0 레드 표현 제거 (D-2)
- `scripts/backtest/run_single_backtest.py` — Donchian dead code 제거 (A-3)
- `scripts/backtest/app_single_backtest.py` — Donchian dead code 제거 (A-3)
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — 삭제된 스크립트 참조 수정 (B-1)

Phase 2 (문서):
- `CLAUDE.md` (루트) — 디렉토리 트리 보완 (C-3)
- `src/qbt/backtest/CLAUDE.md` — run_buy_and_hold 반환 타입 수정 (C-2)
- `scripts/CLAUDE.md` — meta_manager 타입 목록 수정 (C-4)
- `tests/CLAUDE.md` — 테스트 파일 목록 보완 (C-5)

### 데이터/결과 영향

- 없음. 모든 변경은 dead code 제거, 주석/docstring 수정, 문서 업데이트

## 6) 단계별 계획(Phases)

### Phase 1 — 소스코드 Dead Code 제거 + 주석/docstring 수정 (그린 유지)

**작업 내용**:

- [x] A-1: `types.py`에서 `PboResultDict`, `DsrResultDict`, `CscvAnalysisResultDict` 삭제 + 모듈 docstring 수정
- [x] A-2: `test_wfo_stitched.py` 모듈 docstring에서 ATR 언급 제거, ATR 테스트 메서드 삭제
- [x] A-3: `run_single_backtest.py`에서 upper_channel/lower_channel 처리 코드 삭제
- [x] A-3: `app_single_backtest.py`에서 upper_channel/lower_channel 처리 코드 삭제
- [x] B-1: `app_rate_spread_lab.py`에서 삭제된 스크립트 참조를 git history 복원 안내로 수정
- [x] C-1: `simulation.py`의 `calculate_validation_metrics()` docstring Returns 수정
- [x] D-1: `test_backtest_walkforward.py` 모듈 docstring에서 Phase 표현 제거
- [x] D-2: `test_buffer_zone_helpers.py` 클래스 docstring에서 Phase 0 레드 표현 제거
- [x] D-3: `simulation.py` 95행 "기존 동작" 주석 수정
- [x] D-4: `simulation.py` 155행 "프롬프트 요구사항" 주석 수정

---

### Phase 2 (마지막) — 문서 업데이트 + 최종 검증

**작업 내용**:

- [x] C-2: `backtest/CLAUDE.md`에서 `run_buy_and_hold` 반환 타입을 `tuple[pd.DataFrame, SummaryDict]`로 수정
- [x] C-3: 루트 `CLAUDE.md` 디렉토리 트리에 `walkforward.py`, `parameter_stability.py`, `stock_downloader.py` 추가
- [x] C-4: `scripts/CLAUDE.md`에서 삭제된 meta_manager 타입 제거 + `backtest_walkforward` 추가
- [x] C-5: `tests/CLAUDE.md` 파일 목록에 `test_stock_downloader.py`, `test_wfo_stitched.py` 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트 / 리팩토링 후 문서-주석-코드 정합성 복원 v2 (14건 불일치 수정)
2. 프로젝트 / Dead Code 제거 + 문서 정합성 복원 (CSCV/ATR/Donchian 잔존 코드 정리)
3. 프로젝트 / 대규모 리팩토링 후 잔존 불일치 14건 일괄 수정
4. 프로젝트 / 문서-코드 정합성 v2 (dead code 삭제 + docstring + CLAUDE.md 보정)
5. 프로젝트 / 리팩토링 후속 정리 (TypedDict dead code + 삭제 스크립트 참조 + 문서 보정)

## 7) 리스크(Risks)

- Dead code 제거 시 실제 사용 중인 코드를 삭제할 위험 → grep으로 사전 확인 완료
- 테스트 삭제 시 커버리지 감소 → ATR 전략이 삭제되었으므로 해당 테스트는 무의미

## 8) 메모(Notes)

- 이전 정합성 복원: PLAN_post_refactoring_consistency.md (11건 수정, Done)
- 이번은 그 이후 추가 발견된 14건에 대한 후속 작업

### 진행 로그 (KST)

- 2026-03-13 15:00: 계획서 작성 완료, Phase 1 착수
- 2026-03-13 16:00: Phase 1, 2 완료. Validation passed=334, failed=0, skipped=0. Done
