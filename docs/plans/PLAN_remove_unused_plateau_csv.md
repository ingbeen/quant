# Implementation Plan: 미사용 파라미터 고원 CSV 제거

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

**작성일**: 2026-03-14 15:00
**마지막 업데이트**: 2026-03-14 16:00
**관련 범위**: scripts/backtest, storage/results, docs
**관련 문서**: `scripts/CLAUDE.md`, `docs/CLAUDE.md`

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

- [x] 앱(시각화)에서 사용되지 않는 파라미터 고원 CSV 5개 삭제
- [x] `run_param_plateau_all.py`에서 해당 CSV 생성 로직 제거
- [x] `overfitting_analysis_report.md`에 승률 피벗 결과 아카이빙 및 삭제 사유 기재

## 2) 비목표(Non-Goals)

- walkforward CSV 파일 처리 (별도 판단 완료, 보관 유지)
- `app_parameter_stability.py` 변경 (이미 win_rate를 사용하지 않음)
- 피벗 CSV 구조/포맷 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`storage/results/backtest/param_plateau/`에 앱에서 사용되지 않는 파일 5개가 존재:

1. **`param_plateau_all_detail.csv`** (182행): 모든 실험의 원본 상세 데이터. 피벗 CSV가 동일 정보를 구조화하여 제공하므로 중복. 재실행으로 재현 가능.

2. **`param_plateau_*_win_rate.csv`** (4개): 승률 피벗 데이터. 앱에서 미사용.
   - 삭제 근거: 보고서 §7에서 거래 수(7~27회)로는 승률의 통계적 유의성이 없음이 확인됨. §18.3에서 "거래 수 (핵심 — Calmar보다 중요)"로 판단 기준이 확정됨. 승률 피벗을 시각화하면 잘못된 판단을 유도할 위험이 있음.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 5개 CSV 파일 삭제 완료
- [x] `run_param_plateau_all.py`에서 `win_rate` 피벗 및 `all_detail.csv` 생성 로직 제거
- [x] `overfitting_analysis_report.md`에 승률 피벗 결과 테이블 및 삭제 사유 기재
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=334, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/run_param_plateau_all.py` — `_METRICS`에서 win_rate 제거, `_save_results()`에서 all_detail 저장 제거
- `docs/overfitting_analysis_report.md` — 부록에 승률 피벗 결과 아카이빙 + 삭제 사유 기재

### 삭제 대상 파일

- `storage/results/backtest/param_plateau/param_plateau_all_detail.csv`
- `storage/results/backtest/param_plateau/param_plateau_hold_days_win_rate.csv`
- `storage/results/backtest/param_plateau/param_plateau_sell_buffer_win_rate.csv`
- `storage/results/backtest/param_plateau/param_plateau_buy_buffer_win_rate.csv`
- `storage/results/backtest/param_plateau/param_plateau_ma_window_win_rate.csv`

### 데이터/결과 영향

- 앱 동작에 영향 없음 (`app_parameter_stability.py`는 이 파일들을 참조하지 않음)
- `run_param_plateau_all.py` 재실행 시 생성되는 파일이 5개 줄어듦 (20개 → 16개: calmar/cagr/mdd/trades × 4 파라미터)

## 6) 단계별 계획(Phases)

### Phase 1 — CSV 삭제 및 생성 로직 제거

**작업 내용**:

- [x] 5개 CSV 파일 삭제
- [x] `run_param_plateau_all.py` 수정:
  - `_METRICS`에서 `("win_rate", "승률(%)")` 제거
  - `_save_results()`에서 `param_plateau_all_detail.csv` 저장 로직 제거
  - `_build_row()`에서 `win_rate` 관련 필드 제거

---

### Phase 2 (마지막) — 보고서 기재 및 최종 검증

**작업 내용**:

- [x] `overfitting_analysis_report.md` 부록에 승률 피벗 결과 아카이빙 (§부록 B):
  - 4개 승률 피벗 테이블 (hold_days, sell_buffer, buy_buffer, ma_window)
  - 삭제 사유: 거래 수 부족으로 통계적 유의성 없음 (§7 참조)
  - 삭제일 기록
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 정리 / 미사용 파라미터 고원 CSV 제거 및 생성 로직 정리
2. 고원분석 / 통계적으로 무의미한 win_rate 피벗 및 중복 상세 CSV 삭제
3. 정리 / param_plateau 불필요 CSV 5개 삭제 + 보고서 아카이빙
4. 고원분석 / win_rate 피벗 제거 (거래 수 부족으로 통계적 유의성 없음)
5. 정리 / 앱 미사용 고원 분석 결과 파일 정리 및 보고서 반영

## 7) 리스크(Risks)

- **낮음**: 삭제 대상 파일이 앱에서 사용되지 않음이 확인됨. 생성 로직 제거도 기존 동작에 영향 없음.
- **복원 가능**: all_detail.csv는 `run_param_plateau_all.py` 재실행으로 재현 가능. win_rate 피벗은 보고서 부록에 아카이빙.

## 8) 메모(Notes)

- 승률(win_rate)이 통계적으로 무의미한 근거: 보고서 §7 "거래 수와 통계적 신뢰도" — 14거래에서 71% 승률의 p-value ~9%, 유의수준 5% 미달
- 보고서 §18.3에서 "거래 수 (핵심 — Calmar보다 중요)" 판단 확정
- walkforward CSV 14개는 재실행 비용이 높아 보관 유지 (별도 판단 완료)

### 진행 로그 (KST)

- 2026-03-14 15:00: 계획서 작성
- 2026-03-14 16:00: Phase 1~2 완료, 전체 검증 통과 (passed=334, failed=0, skipped=0)

---
