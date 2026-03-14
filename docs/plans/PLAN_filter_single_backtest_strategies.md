# Implementation Plan: 단일 백테스트 전략 QQQ/TQQQ 필터링

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

**작성일**: 2026-03-14 22:00
**마지막 업데이트**: 2026-03-14 22:10
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] `run_single_backtest.py`와 `app_single_backtest.py`에서 QQQ/TQQQ 관련 전략(4개)만 실행/표출하도록 필터링
- [x] 필터링 대상 전략 이름을 `backtest/constants.py`에 공통 상수로 정의

## 2) 비목표(Non-Goals)

- `buffer_zone.py`와 `buy_and_hold.py`의 CONFIGS에서 cross-asset 전략을 삭제하지 않음 (CONFIGS는 그대로 유지)
- `run_walkforward.py`, `run_param_plateau_all.py` 등 다른 스크립트에는 영향 없음
- 기존 cross-asset 결과 폴더 삭제 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `run_single_backtest.py --strategy all`은 16개 전략(8 buffer_zone + 8 buy_and_hold)을 모두 실행
- 실제 투자에 사용하는 전략은 QQQ/TQQQ 관련 4개뿐이며, cross-asset 6종(SPY, IWM, EFA, EEM, GLD, TLT)은 검증 용도로만 사용
- `app_single_backtest.py`도 결과 폴더를 자동 탐색하여 16개 탭을 모두 표출하므로 불필요한 정보가 표시됨
- 필터링 대상 전략을 상수로 관리하면 두 스크립트 간 일관성이 보장됨

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `backtest/constants.py`에 `DEFAULT_SINGLE_BACKTEST_STRATEGIES` 상수 추가
- [x] `run_single_backtest.py`에서 상수 기반 필터링 적용 (`--strategy` 선택지 및 `all` 동작)
- [x] `app_single_backtest.py`에서 상수 기반 필터링 적용 (`_discover_strategies()` 결과 필터)
- [x] `poetry run python validate_project.py` 통과 (passed=334, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/constants.py` — 상수 추가
- `scripts/backtest/run_single_backtest.py` — STRATEGY_RUNNERS 필터링
- `scripts/backtest/app_single_backtest.py` — _discover_strategies() 필터링

### 데이터/결과 영향

- 출력 스키마 변경 없음
- `--strategy all` 실행 시 기존 16개 → 4개 전략만 실행/저장
- cross-asset 결과 폴더는 그대로 남으나 신규 실행/표출에서 제외

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 정의 및 필터링 적용 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/constants.py`에 상수 추가:
  ```python
  DEFAULT_SINGLE_BACKTEST_STRATEGIES: list[str] = [
      "buffer_zone_tqqq",
      "buffer_zone_qqq",
      "buy_and_hold_qqq",
      "buy_and_hold_tqqq",
  ]
  ```
- [x] `scripts/backtest/run_single_backtest.py` 수정:
  - `DEFAULT_SINGLE_BACKTEST_STRATEGIES` import
  - STRATEGY_RUNNERS 딕셔너리 빌드 후 상수에 포함된 전략만 필터링
  - argparse `--strategy` choices를 필터링된 키 목록으로 변경
- [x] `scripts/backtest/app_single_backtest.py` 수정:
  - `DEFAULT_SINGLE_BACKTEST_STRATEGIES` import
  - `_discover_strategies()` 결과를 상수 리스트로 필터링

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] `scripts/CLAUDE.md` 업데이트 (필터링 동작 반영 — 불필요, 기존 문서에 이미 --strategy 설명 포함)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / QQQ·TQQQ 전략만 실행·표출하도록 필터링 상수 추가
2. 백테스트 / 단일 백테스트 전략 필터링 (cross-asset 제외)
3. 백테스트 / DEFAULT_SINGLE_BACKTEST_STRATEGIES 상수 기반 전략 필터링
4. 백테스트 / run/app_single_backtest에서 QQQ·TQQQ 4개 전략만 활성화
5. 백테스트 / 전략 필터링 상수화 및 스크립트 적용

## 7) 리스크(Risks)

- 기존 cross-asset 결과 폴더가 남아있으나 앱에서 표출되지 않음 → 의도된 동작
- 추후 cross-asset 재활성화 시 상수 리스트에 추가만 하면 됨

## 8) 메모(Notes)

- CONFIGS 자체는 유지하므로 `run_walkforward.py`, `run_param_plateau_all.py` 등 다른 스크립트에는 영향 없음
- 필터링 대상: `buffer_zone_tqqq`, `buffer_zone_qqq`, `buy_and_hold_qqq`, `buy_and_hold_tqqq`

### 진행 로그 (KST)

- 2026-03-14 22:00: 계획서 작성 (Draft)
- 2026-03-14 22:10: 구현 완료, 전체 검증 통과 (passed=334, failed=0, skipped=0)
