# Implementation Plan: 버그 수정 및 방어 코드 보강

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

**작성일**: 2026-02-20 20:00
**마지막 업데이트**: 2026-02-21 00:30
**관련 범위**: backtest (strategies, analysis), scripts/backtest
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

- [x] 목표 1: 그리드 서치 정렬 기준을 문서와 코드 간 일치시킴 (보고서 A-1)
- [x] 목표 2: 매도 주문 시 죽은 코드 제거 (보고서 A-2)
- [x] 목표 3: `_save_summary_json`의 KeyError 방어 (보고서 A-3)

## 2) 비목표(Non-Goals)

- 그리드 서치 알고리즘 변경: 정렬 기준만 문서에 일치시킴, 탐색 로직 변경 없음
- 새로운 전략 추가
- CLI 계층 비즈니스 로직 분리 (별도 계획서 대상)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- A-1: 문서(CLAUDE.md)에서는 "CAGR 내림차순"이라고 명시하지만, 코드는 `COL_TOTAL_RETURN_PCT`(총 수익률) 기준 정렬. 동일 기간에서는 결과가 같으나 문서-코드 불일치
- A-2: `_execute_sell_order()` 내부에서 `hold_days_used`를 설정하지만, 호출 직후 덮어쓰므로 죽은 코드가 됨
- A-3: Buy & Hold 전략에서는 `win_rate` 키가 없을 수 있어 `summary["win_rate"]` 접근 시 KeyError 발생 가능

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 성과 지표 계산, 그리드 서치 규칙
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] A-1: 그리드 서치 정렬 기준이 문서와 코드에서 일치
- [x] A-2: 매도 주문 죽은 코드 제거
- [x] A-3: `_save_summary_json`에서 KeyError 방어 완료
- [x] 각 수정에 대한 테스트 추가 또는 기존 테스트로 검증
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — 정렬 기준 수정(A-1), 죽은 코드 제거(A-2)
- `scripts/backtest/run_single_backtest.py` — KeyError 방어(A-3)
- `tests/test_strategy.py` — A-1, A-2 관련 기존 테스트 확인/보강

### 데이터/결과 영향

- A-1 (정렬 기준): 동일 기간 그리드 서치에서는 총 수익률과 CAGR 순위가 동일하므로 **기존 결과 변경 없음**. 단, 향후 혼합 기간 지원 시 결과가 달라질 수 있음
- A-2: 죽은 코드 제거이므로 동작 변경 없음
- A-3: 기존에 에러가 발생하지 않았던 경로에 방어 코드 추가이므로 정상 경로 동작 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 버그 수정 (그린 유지)

**작업 내용**:

- [x] A-1: `buffer_zone_helpers.py:735` — `sort_values(by=COL_TOTAL_RETURN_PCT)` → `sort_values(by=COL_CAGR)` 변경
  - `load_best_grid_params`에서도 동일 기준 사용 확인
  - 기존 그리드 서치 결과 CSV와 비교하여 순위 변경 없음 검증
- [x] A-2: `buffer_zone_helpers.py` — `_execute_sell_order()` 내부의 `hold_days_used`/`recent_buy_count` 설정 제거 (줄 539-540)
  - 대신 줄 878-879의 `entry_hold_days`/`entry_recent_buy_count` 덮어쓰기가 유일한 할당으로 유지
- [x] A-3: `run_single_backtest.py:205` — `summary["win_rate"]` → `summary.get("win_rate")` 변경, None 체크 추가
- [x] `calculate_summary`에서 pnl=0 거래를 `losing_trades`로 분류하는 부분(analysis.py:153)에 명확한 주석 추가: "pnl=0은 손실로 분류 (winning + losing = total)"

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] 필요한 문서 업데이트 (CLAUDE.md 내 정렬 기준 설명이 이미 "CAGR 내림차순"이므로 코드가 이에 맞춰짐을 확인)
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 그리드서치 정렬 기준 CAGR로 수정 + 죽은 코드 제거 + KeyError 방어
2. 백테스트 / 버그 수정 3건 (정렬 기준, 죽은 코드, KeyError)
3. 백테스트 / 문서-코드 정렬 기준 일치 + 방어 코드 보강
4. 백테스트 / 그리드서치 정렬 수정 및 _execute_sell_order 죽은 코드 정리
5. 백테스트 / A-1~A-3 버그 수정 (동작 동일, 정합성 개선)

## 7) 리스크(Risks)

- A-1: 동일 기간 그리드 서치에서는 총 수익률과 CAGR 순위가 동일하므로 결과 변경 위험 없음. 실행 후 기존 결과와 비교하여 검증
- A-2: 덮어쓰기 제거이므로 동작 변경 위험 없음. 기존 테스트로 회귀 확인
- A-3: `.get()` 변경은 기존 정상 경로에 영향 없음

## 8) 메모(Notes)

- 이 계획서는 `PROJECT_ANALYSIS_REPORT.md`의 A-1, A-2, A-3 항목을 대상으로 함
- A-1에서 정렬 기준을 CAGR로 변경하는 것은 문서에 맞추는 수정임 (코드 → 문서 방향이 아님)
- `losing_trades`에 pnl=0 포함 건은 주석 추가로 정책 명시 (동작 변경 아님)

### 진행 로그 (KST)

- 2026-02-20 20:00: 계획서 초안 작성
- 2026-02-21 00:30: Phase 1~2 완료, 전체 검증 통과 (passed=301, failed=0, skipped=0)

---
