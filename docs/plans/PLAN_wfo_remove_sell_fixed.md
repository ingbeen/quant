# Implementation Plan: WFO sell_fixed 모드 제거 (2-Mode 전환)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-14 16:00
**마지막 업데이트**: 2026-03-14 16:00
**관련 범위**: scripts/backtest, src/qbt/backtest, storage/results, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`

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

- [ ] WFO 3-Mode(dynamic/sell_fixed/fully_fixed) → 2-Mode(dynamic/fully_fixed)로 전환
- [ ] sell_fixed 관련 코드, 상수, CSV 파일, 문서를 모두 제거
- [ ] 향후 WFO 시각화 대시보드 구현을 고려한 구조 유지

## 2) 비목표(Non-Goals)

- WFO 시각화 대시보드 구현 (별도 작업)
- WFO 비즈니스 로직(`walkforward.py`) 변경 — dynamic/fully_fixed 모드의 동작은 그대로 유지
- `walkforward_summary.json`의 dynamic/fully_fixed 데이터 구조 변경
- 현재 CSV 파일의 컬럼 구조 변경 (시각화 시 추가 데이터가 필요하면 별도 승인)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

WFO는 현재 3-Mode(Dynamic, Sell Fixed, Fully Fixed)를 실행한다. 분석 결과:

- **Sell Fixed는 Dynamic과 거의 동일한 결과를 보인다**: QQQ에서 Dynamic OOS CAGR 12.31% vs Sell Fixed 11.81%, TQQQ에서 29.4% vs 27.68%. Sell Fixed가 독립적으로 제공하는 인사이트가 없다.
- **핵심 비교는 Dynamic vs Fully Fixed이다**: "파라미터를 바꾸는 게 도움이 되는가?"는 이 두 모드만으로 충분히 답할 수 있다.
  - QQQ: Fully Fixed(13.2%) ≥ Dynamic(12.3%) → 파라미터 안정
  - TQQQ: Fully Fixed(15.7%) ≪ Dynamic(29.4%) → 파라미터 불안정

향후 WFO 시각화 대시보드에서도 Dynamic vs Fully Fixed 2-Mode 비교가 핵심이므로, 불필요한 Sell Fixed를 제거하여 코드/결과를 정리한다.

### 시각화 대비 현재 CSV 구조 평가

현재 WFO 결과 파일 구조가 향후 시각화에 충분한지 평가:

| 시각화 항목 | 필요 데이터 | 현재 CSV | 충분 여부 |
|---|---|---|---|
| 윈도우별 IS/OOS 성과 비교 바차트 | 윈도우별 CAGR/MDD/Calmar | `walkforward_{mode}.csv` | **충분** |
| 파라미터 진화 차트 | 윈도우별 best params | `walkforward_{mode}.csv` | **충분** |
| Stitched Equity 곡선 | 일별 equity/position/band | `walkforward_equity_{mode}.csv` | **충분** |
| WFE 분포 | 윈도우별 wfe_calmar/wfe_cagr | `walkforward_{mode}.csv` | **충분** |
| Dynamic vs Fully Fixed 요약 비교 | 모드별 통계 | `walkforward_summary.json` | **충분** |
| 개별 윈도우 OOS equity (small multiples) | 윈도우별 개별 equity 곡선 | 미존재 | **미충분** (주1) |

**(주1)** 현재 equity CSV는 stitched(연결된) 곡선만 저장한다. 개별 윈도우의 독립적 OOS equity 곡선이 필요하면, `run_walkforward.py`에서 윈도우별 equity를 별도 저장하거나 stitched equity에 `window_idx` 컬럼을 추가해야 한다. **이 변경은 본 plan 범위 밖이며, 시각화 구현 시 사용자 승인 후 진행한다.**

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] sell_fixed 관련 CSV 4개 삭제 완료
- [ ] `walkforward_summary.json` 2개에서 sell_fixed 섹션 제거 완료
- [ ] `run_walkforward.py`에서 sell_fixed 모드 실행/저장/출력 로직 제거
- [ ] `constants.py`에서 sell_fixed 관련 상수 제거
- [ ] `types.py` docstring에서 sell_fixed 참조 제거
- [ ] 문서 업데이트 완료 (`src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, 루트 `CLAUDE.md`)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드:**

- `scripts/backtest/run_walkforward.py` — sell_fixed 모드 실행/저장/출력 제거, `_save_results()` 파라미터 축소, 메타데이터에서 sell_fixed 제거
- `src/qbt/backtest/constants.py` — `DEFAULT_WFO_FIXED_SELL_BUFFER_PCT`, `WALKFORWARD_SELL_FIXED_FILENAME`, `WALKFORWARD_EQUITY_SELL_FIXED_FILENAME` 제거
- `src/qbt/backtest/types.py` — `WfoModeSummaryDict` docstring에서 sell_fixed 참조 제거

**문서:**

- `src/qbt/backtest/CLAUDE.md` — WFO 관련 설명 2-Mode로 갱신
- `scripts/CLAUDE.md` — WFO 설명에서 sell_fixed 제거
- 루트 `CLAUDE.md` — 필요 시 갱신

### 삭제 대상 파일

- `storage/results/backtest/buffer_zone_tqqq/walkforward_sell_fixed.csv`
- `storage/results/backtest/buffer_zone_tqqq/walkforward_equity_sell_fixed.csv`
- `storage/results/backtest/buffer_zone_qqq/walkforward_sell_fixed.csv`
- `storage/results/backtest/buffer_zone_qqq/walkforward_equity_sell_fixed.csv`

### 수정 대상 데이터 파일

- `storage/results/backtest/buffer_zone_tqqq/walkforward_summary.json` — `sell_fixed` 키 제거
- `storage/results/backtest/buffer_zone_qqq/walkforward_summary.json` — `sell_fixed` 키 제거

### 데이터/결과 영향

- `run_walkforward.py` 재실행 시 생성 파일이 7개 → 5개로 감소 (모드당 window CSV + equity CSV = 4개 + summary JSON 1개)
- dynamic, fully_fixed 결과는 변경 없음
- 기존 walkforward_summary.json은 sell_fixed 섹션만 프로그래밍으로 제거 (dynamic/fully_fixed 데이터 보존)

## 6) 단계별 계획(Phases)

### Phase 1 — sell_fixed CSV/JSON 정리 및 코드 제거

**작업 내용**:

- [ ] sell_fixed CSV 4개 삭제
- [ ] `walkforward_summary.json` 2개에서 `sell_fixed` 키 프로그래밍 제거 (Python으로 JSON 로드 → sell_fixed 삭제 → 저장)
- [ ] `src/qbt/backtest/constants.py` 수정:
  - `DEFAULT_WFO_FIXED_SELL_BUFFER_PCT` 상수 제거
  - `WALKFORWARD_SELL_FIXED_FILENAME` 상수 제거
  - `WALKFORWARD_EQUITY_SELL_FIXED_FILENAME` 상수 제거
- [ ] `src/qbt/backtest/types.py` 수정:
  - `WfoModeSummaryDict` docstring에서 `sell_fixed` 참조 제거
- [ ] `scripts/backtest/run_walkforward.py` 수정:
  - import에서 sell_fixed 관련 상수 제거
  - Mode 2 (Sell Fixed) 실행 블록 전체 제거 (410~423행)
  - `_save_results()` 함수에서 sell_fixed 파라미터/로직 제거
  - `_print_mode_summary("Sell Fixed", ...)` 호출 제거
  - `all_summaries`에서 `sell_fixed` 키 제거
  - 메타데이터에서 `sell_fixed_oos_cagr_mean`, `fixed_sell_buffer_pct` 제거
  - docstring "3-Mode" → "2-Mode" 갱신

---

### Phase 2 (마지막) — 문서 업데이트 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/backtest/CLAUDE.md` 갱신:
  - constants.py 섹션에서 sell_fixed 관련 상수 제거
  - WFO 결과 파일명 7개 → 5개
- [ ] `scripts/CLAUDE.md` 갱신:
  - WFO 설명 "3-Mode 비교" → "2-Mode 비교 (Dynamic/Fully Fixed)"
- [ ] 루트 `CLAUDE.md` 필요 시 갱신
- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. WFO / sell_fixed 모드 제거, Dynamic + Fully Fixed 2-Mode로 전환
2. 백테스트 / WFO 3-Mode에서 2-Mode로 간소화 (sell_fixed 제거)
3. WFO / 불필요한 Sell Fixed 모드 제거 및 문서 정리
4. 백테스트 / WFO sell_fixed 모드 제거 (Dynamic vs Fully Fixed로 단순화)
5. 정리 / WFO sell_fixed 모드 코드, 상수, CSV, 문서 일괄 제거

## 7) 리스크(Risks)

- **낮음**: sell_fixed 모드는 어떤 앱에서도 사용되지 않으며, 비즈니스 로직(`walkforward.py`)을 변경하지 않으므로 회귀 위험 없음
- **데이터 보존**: dynamic/fully_fixed 결과 CSV와 equity CSV는 변경하지 않음. walkforward_summary.json도 sell_fixed 키만 제거
- **복원 가능**: 제거된 sell_fixed 결과는 git history에서 복원 가능. 코드 복원도 git revert로 가능

## 8) 메모(Notes)

### 시각화 대비 사항

- 현재 CSV 구조(window result + stitched equity + summary JSON)는 기본적인 WFO 시각화에 충분
- 개별 윈도우 OOS equity 곡선(small multiples)이 필요하면 추가 데이터 생성이 필요하며, 시각화 구현 시 사용자 승인 후 진행
- equity CSV의 `buy_buffer_pct`/`sell_buffer_pct` 값 변화로 윈도우 경계를 추론할 수 있으나, 인접 윈도우에서 파라미터가 동일할 경우 구분 불가. 필요 시 `window_idx` 컬럼 추가를 검토

### sell_fixed 제거 근거 (overfitting_analysis_report.md 기반)

- QQQ: Dynamic(12.31%) vs Sell Fixed(11.81%) — 차이 0.5%p, WFE median 동일(2.09)
- TQQQ: Dynamic(29.4%) vs Sell Fixed(27.68%) — 유사한 분포
- Sell Fixed는 "sell_buffer를 고정해도 괜찮은가?"라는 질문에 답하는 모드인데, 이미 파라미터 고원 분석(§18.3)에서 sell_buffer=0.03~0.07이 고원임이 확인되어 이 질문은 해결됨

### 진행 로그 (KST)

- 2026-03-14 16:00: 계획서 작성

---
