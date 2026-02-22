# Implementation Plan: WFO WFE/PC 지표 보강 + JSON 반올림

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

**작성일**: 2026-02-22 23:30
**마지막 업데이트**: 2026-02-23 00:15
**관련 범위**: backtest (walkforward, types, constants)
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

- [x] WFE를 CAGR 기반으로 추가하여 폭주 문제 해소 (`wfe_cagr`)
- [x] Calmar 기반 WFE의 robust 버전 추가 (`wfe_calmar_robust`, `gap_calmar_median`)
- [x] Profit Concentration 지표 추가 (`profit_concentration_max`, `profit_concentration_window_idx`)
- [x] `walkforward_summary.json` 반올림 규칙 적용 (백분율 2자리, 비율 4자리)

## 2) 비목표(Non-Goals)

- `min_trades` 제약 추가 (→ Plan 2에서 수행)
- ATR 스탑 도입 (→ Plan 3에서 수행)
- WFO 재실행 (이 Plan은 지표 추가만, 행동 변화 없음)
- OOS 플래그 컬럼 추가 (불필요)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **WFE 폭주**: 현재 `wfe_calmar = oos_calmar / is_calmar`만 존재. IS Calmar가 0 근처이면 -1835 같은 비정상 값 발생. `walkforward_summary.json`의 `wfe_calmar_mean: -161.66`이 이를 실증.

2. **Profit Concentration 부재**: TQQQ Dynamic의 max_share=0.673으로 총 이익의 67%가 특정 윈도우에 집중. TradeStation 휴리스틱(50% 초과 시 경고)에 해당하나, 현재 코드에 이 진단 지표가 없음.

3. **JSON 반올림 미적용**: `walkforward_summary.json`의 수치가 소수점 15자리까지 출력되어 가독성 저하.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- 루트 `CLAUDE.md` (출력 데이터 반올림 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `WfoWindowResultDict`에 `wfe_cagr` 필드 추가
- [x] `WfoModeSummaryDict`에 `wfe_cagr_mean`, `wfe_cagr_median`, `gap_calmar_median`, `wfe_calmar_robust`, `profit_concentration_max`, `profit_concentration_window_idx` 필드 추가
- [x] `run_walkforward()`에서 `wfe_cagr` 계산 로직 구현
- [x] `calculate_wfo_mode_summary()`에서 새 지표 계산 로직 구현
- [x] `_save_results()`에서 JSON 반올림 규칙 적용
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/types.py` — `WfoWindowResultDict`, `WfoModeSummaryDict` 필드 추가
- `src/qbt/backtest/walkforward.py` — `wfe_cagr` 계산, Profit Concentration 계산, robust WFE 계산
- `scripts/backtest/run_walkforward.py` — JSON 반올림 적용, 출력 테이블에 새 지표 반영
- `tests/test_backtest_walkforward.py` — 새 지표 테스트 추가

### 데이터/결과 영향

- `walkforward_*.csv`: `wfe_cagr` 컬럼 1개 추가
- `walkforward_summary.json`: 새 지표 필드 추가 + 기존 값 반올림 적용
- 기존 백테스트 행동(파라미터 선택, 거래 로직)에는 변화 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 새 지표 정의 및 테스트 선행 작성(레드)

**작업 내용**:

- [x] `WfoWindowResultDict`에 `wfe_cagr: float` 필드 추가
- [x] `WfoModeSummaryDict`에 새 필드 6개 추가:
  - `wfe_cagr_mean: float` — CAGR 기반 WFE 평균
  - `wfe_cagr_median: float` — CAGR 기반 WFE 중앙값
  - `gap_calmar_median: float` — OOS Calmar - IS Calmar 중앙값
  - `wfe_calmar_robust: float` — IS Calmar > 0인 윈도우만 집계한 WFE Calmar 중앙값
  - `profit_concentration_max: float` — 최대 Profit Concentration (0~1)
  - `profit_concentration_window_idx: int` — 최대 PC가 발생한 윈도우 인덱스
- [x] 테스트 추가 (레드):
  - `wfe_cagr` 계산 검증 (IS CAGR > 0, IS CAGR ≤ 0 케이스)
  - `wfe_calmar_robust` 계산 검증 (IS Calmar ≤ 0인 윈도우 제외)
  - `profit_concentration_max` 계산 검증 (V2 방식: end - prev_end)
  - JSON 반올림 검증 (백분율 2자리, 비율 4자리)

---

### Phase 1 — 핵심 구현(그린 유지)

**작업 내용**:

- [x] `walkforward.py`의 `run_walkforward()`에 `wfe_cagr` 계산 추가:
  ```
  wfe_cagr = oos_cagr / is_cagr  (is_cagr > EPSILON일 때)
  wfe_cagr = 0.0                  (is_cagr ≤ EPSILON일 때)
  ```
- [x] `walkforward.py`의 `calculate_wfo_mode_summary()`에 새 지표 계산 추가:
  - `wfe_cagr_mean`, `wfe_cagr_median`: wfe_cagr 리스트의 평균/중앙값
  - `gap_calmar_median`: `[oos_calmar - is_calmar for each window]`의 중앙값
  - `wfe_calmar_robust`: IS Calmar > 0인 윈도우만 필터링 → wfe_calmar 중앙값 (해당 윈도우 없으면 0.0)
  - `profit_concentration_max`, `profit_concentration_window_idx`: stitched equity 기반 PC 계산 (V2 방식)
- [x] Profit Concentration 계산 함수 신규 추가 (`_calculate_profit_concentration`):
  - 입력: stitched equity의 윈도우별 시작/종료 equity 값
  - 각 윈도우 기여분 = end_equity - prev_end_equity (V2)
  - total_net_profit = final_equity - initial_equity
  - 각 윈도우 share = 기여분 / total_net_profit
  - max_share, max_window_idx 반환
- [x] Phase 0 레드 테스트 통과 확인

---

### Phase 2 — JSON 반올림 + 문서 정리 + 최종 검증

**작업 내용**:

- [x] `scripts/backtest/run_walkforward.py`의 `_save_results()`에서 JSON 반올림 적용:
  - 백분율 (CAGR, MDD, 승률, 수익률): 소수점 2자리
  - 비율 (Calmar, WFE, PC): 소수점 4자리
  - 정수 (윈도우 수, 거래수, 인덱스): 그대로
  - 파라미터 배열: 그대로
- [x] `_print_mode_summary()`에 새 지표 출력 행 추가
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (새 필드 반영)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=347, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFE·PC 진단 지표 추가 및 JSON 반올림 적용
2. 백테스트 / WFO 지표 보강 (wfe_cagr, profit_concentration, robust WFE)
3. 백테스트 / 워크포워드 진단 도구 확충 + summary.json 반올림
4. 백테스트 / WFE 폭주 해소 + Profit Concentration 경고등 추가
5. 백테스트 / WFO 요약 지표 6종 추가 및 출력 정밀도 정리

## 7) 리스크(Risks)

- Profit Concentration 계산 시 total_net_profit ≤ 0인 경우 (전체 손실) → share 계산이 무의미하므로 0.0 반환 처리 필요
- `WfoWindowResultDict`, `WfoModeSummaryDict` 필드 추가로 기존 테스트의 dict 구조 불일치 가능 → NotRequired 사용 또는 기존 테스트 업데이트

## 8) 메모(Notes)

- 참고: `buffer_zone_tqqq_improvement_log.md` Session 14, 15의 합의 내용
- WFE CAGR 정의: `oos_cagr / is_cagr` (TradeStation의 연환산 수익률 비교 방식에 근거)
- PC V2 방식: 각 윈도우 기여분 = `end_equity - prev_end_equity` (stitched equity에서 윈도우 경계 기준)
- 이 Plan은 행동 변화 없음 (진단 도구 추가만). Plan 2, 3의 전후 비교 기반이 됨.

### 진행 로그 (KST)

- 2026-02-22 23:30: Plan 작성 완료 (Draft)
- 2026-02-23 00:15: 전체 Phase 완료 (passed=347, failed=0, skipped=0)

---
