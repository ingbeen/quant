# Implementation Plan: WFO OOS EMA 연속성 버그 수정

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

**작성일**: 2026-03-27 00:00
**마지막 업데이트**: 2026-04-01 11:30
**관련 범위**: backtest, scripts/backtest
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

- [x] `run_walkforward()`에서 OOS 평가 시 EMA를 OOS 구간 기준으로 리셋하지 않고, 전체 히스토리 기반 EMA를 유지한다.
- [x] `_run_stitched_equity()`에서 stitched 자본곡선 생성 시 동일하게 전체 히스토리 기반 EMA를 사용한다.
- [x] 두 경로가 동일한 EMA 계산 규칙을 따르도록 일관성을 확보한다.

## 2) 비목표(Non-Goals)

- Calmar 계산 불일치 수정 (별도 plan 대상)
- 4P 고정값 로컬 재정의 수정 (별도 plan 대상)
- portfolio preflight 중복 제거 (별도 plan 대상)
- `run_walkforward()`의 public API(파라미터, 반환 타입) 변경
- WFO 결과 CSV 형식 변경
- SMA 방식 동작 변경 (SMA는 EMA와 달리 슬라이스 방식으로도 동일 결과가 나오므로 영향 없음)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`run_walkforward()`는 각 OOS 윈도우마다 다음 순서로 동작한다.

1. 전체 `signal_df`에서 OOS 구간을 먼저 자른다 (`signal_df[oos_mask]`)
2. 잘린 OOS 조각에 `add_single_moving_average()`를 호출한다

EMA는 `pandas.ewm().mean()` 특성상 전달된 시리즈의 첫 행부터 새로 계산된다. 따라서 OOS 구간이 잘린 뒤 EMA를 계산하면, OOS 첫날의 EMA 상태가 전체 히스토리를 이어받은 값이 아니라 OOS 시작점 기준으로 리셋된 값이 된다.

결과적으로 실제 운용 시 발생하는 EMA 값과 WFO 평가에 사용된 EMA 값이 다를 수 있으며, OOS 성과(CAGR, MDD, Calmar, WFE)가 실제와 다르게 측정된다.

`_run_stitched_equity()`도 동일한 구조적 문제를 가지고 있다. OOS 전체 범위를 먼저 자른 뒤 MA를 계산하므로, stitched 자본곡선 역시 동일한 EMA 리셋 문제를 공유한다.

함수의 docstring(`signal_df: MA 컬럼 미포함, 내부에서 계산`)은 호출자가 raw signal_df를 전달하도록 규정하고 있으며, 이 계약은 수정 후에도 유지된다.

**수정 방향 (B안)**: 내부에서 전체 `signal_df`에 필요한 모든 MA window를 먼저 계산한 뒤, IS/OOS 슬라이스를 수행한다. 호출자의 계약은 변경되지 않는다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `run_walkforward()` — OOS 슬라이스 전 전체 signal_df에 모든 MA window 사전 계산
- [x] `_run_stitched_equity()` — OOS 슬라이스 전 전체 signal_df에 필요한 MA window 사전 계산
- [x] EMA 연속성 인바리언트를 검증하는 테스트 추가 (전체 히스토리 EMA 슬라이스 == 사전 계산 결과)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=428, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/walkforward.py` — `run_walkforward()` 내부 수정
- `scripts/backtest/run_walkforward.py` — `_run_stitched_equity()` 내부 수정
- `tests/test_walkforward_schedule.py` — EMA 연속성 인바리언트 테스트 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- 수정 후 WFO OOS EMA 값이 달라진다. 이에 따라 OOS 성과 지표(CAGR, MDD, Calmar, WFE)가 기존 결과와 달라질 수 있다.
- 기존 `storage/results/backtest/*/walkforward_*.csv` 파일은 수정 전 동작 기준으로 생성된 값이므로, 수정 후 `run_walkforward.py`를 재실행해야 정확한 결과를 얻는다.
- 출력 CSV 스키마(컬럼명, 파일명) 변경 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — EMA 연속성 인바리언트를 테스트로 먼저 고정 (레드)

핵심 인바리언트:
- "OOS 구간의 EMA 값은 전체 히스토리 기반으로 계산된 EMA를 해당 구간만 잘랐을 때의 값과 동일해야 한다"

이 인바리언트를 테스트로 고정한다. 현재 구현에서는 이 테스트가 실패한다(레드).

**작업 내용**:

- [x] `tests/test_walkforward_schedule.py`에 `TestEmaContiniuty` 클래스 추가
  - [x] `test_oos_ema_matches_full_history_ema`: 현재 `run_walkforward()`가 OOS에서 EMA를 리셋함을 확인하는 회귀 방지 테스트 (Phase 0에서는 실패 예상)
    - Given: 충분한 길이의 signal_df (IS + OOS 포함), ma_window=10
    - When: run_walkforward() 실행 후 첫 번째 OOS 윈도우의 EMA 값 확인
    - Then: 전체 히스토리로 계산한 EMA를 슬라이스한 값과 일치해야 함
  - [x] `test_stitched_equity_ema_matches_full_history_ema`: `_run_stitched_equity()`도 동일 인바리언트 검증

**Validation (Phase 0)**:

```bash
poetry run pytest tests/test_walkforward_schedule.py::TestEmaContiniuty -v
# 결과: 새 테스트 2개 FAILED (레드 확인 완료)
```

---

### Phase 1 — run_walkforward() 수정 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/walkforward.py`의 `run_walkforward()` 수정
  - [x] 윈도우 루프 진입 전, `ma_window_list`의 모든 window에 대해 `signal_df` 전체에 MA 사전 계산
  - [x] 루프 내 IS/OOS 슬라이스를 `signal_df_with_ma` 기준으로 변경
  - [x] 루프 내 OOS MA 재계산 블록 제거 (`if oos_ma_col not in oos_signal.columns: ...`)
  - [x] `run_grid_search` 내부에서 MA를 항상 재계산하므로 IS 평가에 영향 없음 확인

**Validation (Phase 1)**:

```bash
poetry run pytest tests/test_walkforward_schedule.py::TestEmaContiniuty -v
# 결과: test_oos_ema_matches_full_history_ema PASSED
```

---

### Phase 2 — _run_stitched_equity() 수정 (그린 유지)

**작업 내용**:

- [x] `scripts/backtest/run_walkforward.py`의 `_run_stitched_equity()` 수정
  - [x] `params_schedule`에서 필요한 MA window 목록 수집 로직을 OOS 슬라이스 전으로 이동
  - [x] 전체 `signal_df`에 필요한 MA window 사전 계산 후 OOS 슬라이스 수행
  - [x] 기존 OOS 슬라이스 후 MA 계산 블록 제거

**Validation (Phase 2)**:

```bash
poetry run pytest tests/test_walkforward_schedule.py::TestEmaContiniuty -v
# 결과: 2개 모두 PASSED (그린)
poetry run pytest tests/test_wfo_stitched.py -v
# 결과: 기존 테스트 5개 모두 PASSED (회귀 없음)
```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/walkforward.py` — `run_walkforward()` docstring 주석 업데이트 (내부 MA 계산 순서 명시)
- [x] `README.md` 변경 없음
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=428, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFO OOS EMA 연속성 버그 수정 — 전체 히스토리 기반 사전 계산으로 변경
2. 백테스트 / WFO OOS·stitched equity EMA 리셋 버그 수정 + 테스트 추가
3. 백테스트 / WFO 평가 정합성 수정 — OOS MA를 전체 히스토리 기준으로 통일
4. 백테스트 / walkforward EMA 계산 순서 수정 (슬라이스 전 사전 계산)
5. 백테스트 / WFO OOS EMA 상태 연속성 보장 — run_walkforward + stitched equity 동일 규칙 적용

## 7) 리스크(Risks)

- **결과값 변경**: 수정 후 OOS EMA 값이 달라지므로 기존 walkforward_*.csv와 수치가 다를 수 있다. 사용자가 직접 `run_walkforward.py`를 재실행해야 최신 기준 결과를 얻는다.
- **IS 그리드 서치 계산량**: 전체 signal_df에 MA를 사전 계산하면 IS 슬라이스가 이미 MA를 포함하므로, `run_grid_search` 내부의 `run_buffer_strategy`가 중복 계산을 시도할 수 있다. `if ma_col not in signal_df.columns` 가드가 이를 방어하므로 실질적 문제는 없으나, Phase 1에서 명시적으로 확인이 필요하다.
- **stitched equity 수치 변경**: stitched equity 기반 WFE, Profit Concentration 등 지표도 달라질 수 있다.

## 8) 메모(Notes)

- 이 plan은 `docs/refactoring.md` 항목 2-1, 2-2에 해당하는 버그를 수정한다.
- 수정 방향은 B안 — 내부에서 전체 히스토리 기준 MA 사전 계산, 이후 슬라이스. public contract 변경 없음.
- Calmar 계산 불일치(refactoring.md 항목 2-3), 4P 고정값 재정의(2-4) 등은 별도 plan으로 처리한다.
- SMA는 ewm 특성이 없으므로 슬라이스 이후 계산해도 결과가 동일하다. 그러나 이 수정 후에는 SMA도 일관되게 전체 히스토리 기반으로 계산된다.

### 진행 로그 (KST)

- 2026-03-27 00:00: plan 초안 작성
- 2026-04-01 11:30: 전체 Phase 완료 (Phase 0 레드 확인 → Phase 1 run_walkforward 수정 → Phase 2 _run_stitched_equity 수정 → 최종 검증 통과)
