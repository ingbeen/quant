# Implementation Plan: ATR(14,3.0) vs (22,3.0) OOS 비교 실험

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

**작성일**: 2026-02-28 03:00
**마지막 업데이트**: 2026-02-27 22:00
**관련 범위**: backtest, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] ATR(14, 3.0)과 ATR(22, 3.0)을 IS 최적화 없이 고정하여 WFO Dynamic OOS 성과 비교
- [x] PBO 0.65 경고에 대한 독립적 검증 근거 제공
- [x] 윈도우별 + Stitched 지표 비교 결과를 CSV/JSON으로 저장

## 2) 비목표(Non-Goals)

- 기존 WFO 파이프라인(walkforward.py, buffer_zone_helpers.py) 변경
- 3-Mode 비교 (Dynamic/Sell Fixed/Fully Fixed) — Dynamic만 실행
- ATR 파라미터를 3개 이상 비교 (14 vs 22만)
- 대시보드 시각화

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- CSCV 분석에서 ATR TQQQ의 PBO 0.65 (과최적화 경고)
- 원인: ATR 차원 추가로 탐색 공간 4배 확대 (432 → 1,728)
- WFO에서 ATR(14, 3.0)이 33/33 전 윈도우 수렴 — PBO와 모순
- IS 최적화 없이 고정 비교 → "우연히 잘 맞은 것"인지 "구조적으로 우수한 것"인지 검증

### 핵심 발견

`run_walkforward()`는 `atr_period_list`, `atr_multiplier_list`를 외부에서 주입 가능.
`atr_period_list=[14]`, `atr_multiplier_list=[3.0]`으로 전달하면 그리드 432개 (ATR 고정).
기존 코드 변경 없이 실험 가능.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 상수 관리 3계층, 타입 힌트, 비율 표기, 반올림, 로깅
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (계층 분리, 예외 처리, 메타데이터)
- `tests/CLAUDE.md`: Given-When-Then, 결정적 테스트, 부동소수점 비교

## 4) 완료 조건(Definition of Done)

- [x] ATR 비교 비즈니스 로직 (`atr_comparison.py`) 구현 및 테스트 통과
- [x] CLI 스크립트 (`run_atr_comparison.py`) 구현
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (CLAUDE.md 4개)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 신규 파일

- `src/qbt/backtest/atr_comparison.py` -- ATR 고정 WFO 실행, 윈도우별 비교, 요약 통계
- `scripts/backtest/run_atr_comparison.py` -- CLI 스크립트
- `tests/test_atr_comparison.py` -- 단위/통합 테스트

### 수정 파일

- `src/qbt/backtest/constants.py` -- 파일명 상수 2개 추가
- `src/qbt/utils/meta_manager.py` -- VALID_CSV_TYPES에 `"atr_comparison"` 추가
- `src/qbt/backtest/CLAUDE.md` -- atr_comparison.py 모듈 설명
- `scripts/CLAUDE.md` -- run_atr_comparison.py 설명
- `tests/CLAUDE.md` -- test_atr_comparison.py 추가
- `CLAUDE.md` (루트) -- 디렉토리 구조 + 결과 파일 추가

### 미수정 (기존 로직 변경 없음)

- `walkforward.py`, `buffer_zone_helpers.py`, `analysis.py`, `cpcv.py` -- 모두 그대로

### 데이터/결과 영향

- 기존 결과 파일 변경 없음
- 신규 결과 파일 추가:
  - `storage/results/backtest/buffer_zone_atr_tqqq/atr_comparison_windows.csv`
  - `storage/results/backtest/buffer_zone_atr_tqqq/atr_comparison_summary.json`

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트 선행 + 상수/메타 추가 (Red)

**작업 내용**:

- [x] `src/qbt/backtest/constants.py`에 파일명 상수 추가:
  - `ATR_COMPARISON_WINDOWS_FILENAME`
  - `ATR_COMPARISON_SUMMARY_FILENAME`
- [x] `src/qbt/utils/meta_manager.py`의 `VALID_CSV_TYPES`에 `"atr_comparison"` 추가
- [x] `tests/test_atr_comparison.py` 작성:
  - TestBuildWindowComparison: 윈도우 수 불일치 ValueError, 차이 계산, 행 구조
  - TestBuildComparisonSummary: wins 카운트, 필수 필드, 차이 평균/중앙값
  - TestRunSingleAtrConfig: 소규모 통합 (축소 WFO 설정으로 반환 구조 검증)

---

### Phase 1 — 비즈니스 로직 구현 (Green)

**작업 내용**:

- [x] `src/qbt/backtest/atr_comparison.py` 구현:
  - TypedDict 정의 (AtrComparisonResultDict, WindowComparisonRow)
  - `run_single_atr_config()`: run_walkforward() + Stitched Equity + calculate_wfo_mode_summary()
  - `build_window_comparison()`: 윈도우별 비교 + 차이 계산
  - `build_comparison_summary()`: 요약 통계 (Stitched 지표, 우위 카운트, 차이 통계)
- [x] Phase 0 테스트 전체 통과 확인

---

### Phase 2 (Final) — CLI + 문서 + 최종 검증

**작업 내용**:

- [x] `scripts/backtest/run_atr_comparison.py` CLI 스크립트:
  - 데이터 로딩 (QQQ + TQQQ synthetic)
  - ATR(14,3.0) / ATR(22,3.0) 순차 실행
  - 윈도우별 비교 + 요약 생성
  - TableLogger 결과 출력
  - CSV/JSON 저장 + 메타데이터
- [x] CLAUDE.md 4개 업데이트
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=404, failed=0, skipped=0)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 백테스트 / ATR(14,3.0) vs (22,3.0) OOS 비교 실험 모듈 추가
2. 백테스트 / ATR 파라미터 고정 OOS 비교 실험 구현
3. 백테스트 / PBO 경고 검증을 위한 ATR 고정 WFO 비교 도구 추가
4. 백테스트 / ATR 일반화 가능성 검증 실험 (IS 최적화 없이 고정 비교)
5. 백테스트 / ATR period 14 vs 22 고정 OOS 성과 비교 모듈 추가

## 7) 리스크(Risks)

| 리스크 | 심각도 | 완화책 |
|--------|--------|--------|
| Stitched Equity 로직이 CLI에만 존재하여 재구현 필요 | 중 | public 함수 조합으로 비즈니스 로직 계층에 구현 |
| 소규모 통합 테스트의 데이터 크기 | 하 | initial_is_months=6, oos_months=3 축소 설정 사용 |
| ATR 고정 시 IS 최적 버퍼존 파라미터가 달라질 수 있음 | 하 | 실험 목적 자체가 ATR 차원 제거 후 OOS 성과 유지 여부 확인 |
| PyRight strict 타입 체크 | 중 | 정확한 TypedDict 정의, 반환 타입 명시 |

## 8) 메모(Notes)

### 핵심 설계 결정

- Dynamic 모드만 실행 (TQQQ의 primary mode, PBO 0.65 대상)
- ATR 설정은 로컬 상수로 정의 (1개 파일에서만 사용)
- 기존 walkforward.py의 public 함수만 조합하여 사용

### 참조할 기존 함수

- `walkforward.run_walkforward()` — atr_period_list, atr_multiplier_list 외부 주입
- `walkforward.build_params_schedule()` — 윈도우별 파라미터 스케줄
- `walkforward.calculate_wfo_mode_summary()` — 모드 요약 통계
- `buffer_zone_helpers.run_buffer_strategy()` — 전략 실행 (params_schedule 지원)
- `analysis.calculate_summary()` — 성과 지표 계산

### 진행 로그 (KST)

- 2026-02-28 03:00: 계획서 작성 완료
- 2026-02-27 22:00: Phase 0~2 완료, validate_project.py 통과 (passed=404, failed=0, skipped=0)

---
