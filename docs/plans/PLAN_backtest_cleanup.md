# Implementation Plan: 백테스트 폐기 코드 삭제 및 정리

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

**작성일**: 2026-03-10 22:00
**마지막 업데이트**: 2026-03-10 23:30
**관련 범위**: backtest, scripts, tests, storage
**관련 문서**: `docs/overfitting_analysis_report.md`

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

- [x] overfitting_analysis_report.md에서 폐기/결론 완료된 백테스트 모듈, 스크립트, 테스트, 결과 파일을 삭제한다
- [x] 삭제 대상의 목적, 결론, 주요 결과 수치를 `docs/archive/`에 문서화한다
- [x] 삭제 후 남은 코드의 참조 정리 (`__init__.py`, 스크립트 분기, CLAUDE.md 등)

## 2) 비목표(Non-Goals)

- buffer_zone.py CONFIGS의 4P 전환 (후속 계획서 PLAN_backtest_4p_transition에서 수행)
- app_parameter_stability.py 고원 시각화 변환 (후속 계획서에서 수행)
- 고원 분석 스크립트 통합 (후속 계획서에서 수행)
- grid_results.csv 관련 코드 변경 (후속 계획서에서 수행)
- run_grid_search.py 변경 (후속 계획서에서 수행)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- overfitting_analysis_report.md (§2.5, §3.3, §12.3)에서 다음 전략/실험이 폐기 또는 결론 완료되었다:
  - ATR WFO 전략: "실전 투입 부적절" 판정 (PBO 0.65, DSR Z-Score -0.390)
  - Donchian Channel 전략: 보고서에서 한 번도 언급되지 않은 실험적 전략
  - ATR 비교 실험 (ATR 14 vs 22): 결론 완료된 일회성 실험
  - WFO 비교 실험 (Expanding vs Rolling): ATR WFO 폐기에 따라 불필요
  - CSCV/PBO/DSR 분석: 결론 완료, 보고서에 수치 기록됨
  - WFO Stitched 백테스트: ATR WFO 폐기에 따라 불필요
  - B&H cross-asset 비교: 결론 완료된 일회성 분석
- 이들 코드가 남아 있으면 유지보수 부담 증가, 코드 탐색 시 혼란 유발

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 삭제 대상 모듈/스크립트/테스트 파일 모두 삭제 완료
- [x] 삭제 대상 결과 파일/폴더 모두 삭제 완료
- [x] 삭제 대상의 문서화 완료 (`docs/archive/backtest_removed_modules.md`)
- [x] 참조 코드 정리 완료 (import, 분기, export)
- [x] CLAUDE.md 파일들 갱신 완료 (루트, backtest, scripts, tests)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=408, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 삭제 대상 파일

소스 모듈 (6개):
- `src/qbt/backtest/strategies/donchian_helpers.py`
- `src/qbt/backtest/strategies/donchian_channel_tqqq.py`
- `src/qbt/backtest/strategies/buffer_zone_atr_tqqq.py`
- `src/qbt/backtest/atr_comparison.py`
- `src/qbt/backtest/wfo_comparison.py`
- `src/qbt/backtest/cpcv.py`

스크립트 (5개):
- `scripts/backtest/run_atr_comparison.py`
- `scripts/backtest/run_wfo_comparison.py`
- `scripts/backtest/run_cpcv_analysis.py`
- `scripts/backtest/run_wfo_stitched_backtest.py`
- `scripts/backtest/run_cross_asset_bh_comparison.py`

테스트 (4개):
- `tests/test_atr_comparison.py`
- `tests/test_wfo_comparison.py`
- `tests/test_cpcv.py`
- `tests/test_donchian_helpers.py`

### 삭제 대상 결과 데이터

폴더 전체 삭제:
- `storage/results/backtest/donchian_channel_tqqq/`
- `storage/results/backtest/buffer_zone_atr_tqqq_wfo/`
- `storage/results/backtest/buffer_zone_qqq_3p/`

폴더 내 특정 파일 삭제:
- `storage/results/backtest/buffer_zone_atr_tqqq/` 내: `cscv_*`, `walkforward_*`, `atr_comparison_*`, `wfo_comparison_*` 파일
- `storage/results/backtest/buffer_zone_tqqq/` 내: `cscv_*`, `walkforward_*` 파일
- `storage/results/backtest/buffer_zone_qqq/` 내: `cscv_*`, `walkforward_*` 파일
- `storage/results/backtest/cross_asset_bh_comparison.csv`, `cross_asset_bh_detail.csv`

### 수정 대상 파일

- `src/qbt/backtest/strategies/__init__.py`: Donchian, ATR export 제거
- `src/qbt/backtest/__init__.py`: 삭제 모듈 export 확인 및 제거
- `scripts/backtest/run_single_backtest.py`: Donchian 전략 매핑 제거
- `scripts/backtest/run_walkforward.py`: buffer_zone_atr_tqqq 분기 제거
- `src/qbt/common_constants.py`: 삭제 전략 전용 경로 상수 확인 및 제거
- CLAUDE.md 파일: 루트, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

### 신규 생성 파일

- `docs/archive/backtest_removed_modules.md`: 삭제 대상 문서화

### 데이터/결과 영향

- 기존 결과 데이터가 삭제되나, 핵심 수치는 overfitting_analysis_report.md에 이미 기록되어 있음
- buffer_zone_tqqq/qqq의 signal, equity, trades, summary, grid_results는 유지됨
- buffer_zone_atr_tqqq의 signal, equity, trades, summary는 유지됨 (대시보드 비교용, 후속 계획서에서 판단)

## 6) 단계별 계획(Phases)

### Phase 1 — 삭제 대상 문서화

**작업 내용**:

- [x] `docs/archive/backtest_removed_modules.md` 작성
  - 삭제 대상 6개 모듈 각각에 대해: 목적, 핵심 함수/클래스, 결론/폐기 사유, 주요 결과 수치
  - overfitting_analysis_report.md 참조 섹션 명시
  - 삭제 대상 스크립트 5개에 대해: 쓰임새, 선행/후행 관계 기록

---

### Phase 2 — 소스/스크립트/테스트 삭제 + 참조 정리

**작업 내용**:

- [x] 소스 모듈 6개 삭제
- [x] 스크립트 5개 삭제
- [x] 테스트 4개 삭제
- [x] `src/qbt/backtest/strategies/__init__.py` 수정: Donchian export 제거
- [x] `src/qbt/backtest/__init__.py` 수정: 삭제 모듈 export 확인 및 제거
- [x] `scripts/backtest/run_single_backtest.py` 수정: donchian_channel_tqqq 매핑 제거
- [x] `scripts/backtest/run_walkforward.py` 수정: buffer_zone_atr_tqqq 분기 제거
- [x] `src/qbt/common_constants.py` 수정: 삭제 전략 전용 경로 상수 제거 (사용처 없는 것만)

---

### Phase 3 — 결과 데이터 삭제

**작업 내용**:

- [x] `storage/results/backtest/donchian_channel_tqqq/` 폴더 삭제
- [x] `storage/results/backtest/buffer_zone_atr_tqqq_wfo/` 폴더 삭제
- [x] `storage/results/backtest/buffer_zone_qqq_3p/` 폴더 삭제
- [x] `storage/results/backtest/buffer_zone_atr_tqqq/` 내 cscv/walkforward/atr_comparison/wfo_comparison 파일 삭제
- [x] `storage/results/backtest/buffer_zone_tqqq/` 내 cscv/walkforward 파일 삭제
- [x] `storage/results/backtest/buffer_zone_qqq/` 내 cscv/walkforward 파일 삭제
- [x] `storage/results/backtest/cross_asset_bh_comparison.csv`, `cross_asset_bh_detail.csv` 삭제

---

### Phase 4 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 갱신: 삭제된 모듈 섹션 제거
- [x] `scripts/CLAUDE.md` 갱신: 삭제된 스크립트 참조 제거
- [x] `tests/CLAUDE.md` 갱신: 삭제된 테스트 파일 참조 제거
- [x] 루트 `CLAUDE.md` 갱신: 디렉토리 구조, 결과 폴더 목록 업데이트
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=408, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 폐기 전략·실험 모듈 삭제 및 결과 정리
2. 백테스트 / overfitting 결론 완료 코드 삭제 + 아카이브 문서화
3. 백테스트 / Donchian·ATR·CSCV 폐기 모듈 제거 및 참조 정리
4. 백테스트 / 미사용 전략·실험 코드 일괄 삭제 + docs/archive 기록
5. 백테스트 / 과최적화 분석 완료 코드 정리 (6모듈+5스크립트+4테스트 삭제)

## 7) 리스크(Risks)

- **common_constants.py 경로 상수 오삭제**: 삭제 전략 전용 상수가 다른 곳에서 사용되는지 grep으로 확인 후 삭제. 결과 폴더 경로 상수는 대시보드(app_single_backtest.py)에서 자동 탐색하므로 상수 삭제가 대시보드에 영향 없음
- **run_walkforward.py ATR 분기 제거 시 기존 전략 영향**: buffer_zone_tqqq/qqq WFO 분기는 유지, ATR 전용 분기만 제거
- **테스트 수 감소**: 현재 passed=481에서 상당수 감소 예상. 핵심 전략(buffer_zone, buy_and_hold) 테스트는 영향 없음

## 8) 메모(Notes)

- 삭제 근거: `docs/overfitting_analysis_report.md` §2.5 (최종 결론), §3.3 (ATR WFO 폐기 판정), §12.3 (의사결정 이력)
- Donchian Channel은 보고서에서 한 번도 언급되지 않아 실험적 코드로 판단
- buffer_zone_qqq_3p는 코드에 config가 없는 결과 폴더 잔여물 (§12.3 "hold_days 제거 정당화되지 않음" 결론)
- buffer_zone_atr_tqqq의 signal/equity/trades/summary는 이번 계획서에서 유지. 후속 계획서(4P 전환)에서 대시보드 표시 여부 결정
- 추가 삭제: `src/qbt/backtest/constants.py`에서 ATR 관련 상수 6개 제거 (DEFAULT_ATR_PERIOD, DEFAULT_ATR_MULTIPLIER, DEFAULT_WFO_ATR_PERIOD_LIST, DEFAULT_WFO_ATR_MULTIPLIER_LIST, DEFAULT_WFO_ROLLING_IS_MONTHS, ATR/WFO 비교 실험 파일명 상수 4개)
- 테스트 수 변동: 481 → 408 (73개 감소, 핵심 전략 테스트에 영향 없음)

### 진행 로그 (KST)

- 2026-03-10 22:00: 계획서 초안 작성
- 2026-03-10 23:30: 전체 Phase 완료, validate_project.py 통과 (passed=408, failed=0, skipped=0)

---
