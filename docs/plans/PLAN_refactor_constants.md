# Implementation Plan: 상수 리팩토링 (사용 위치 기반 배치)

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

**작성일**: 2026-01-17 22:30
**마지막 업데이트**: 2026-01-18
**관련 범위**: common, backtest, tqqq, utils, scripts
**관련 문서**: `CLAUDE.md` (루트), `src/qbt/tqqq/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 한 파일에서만 사용되는 상수를 해당 파일 상단으로 이동
- [x] 상수 파일(constants.py)을 경량화하여 실제로 공유되는 상수만 유지
- [x] 코드 근접성(Locality) 향상으로 가독성 개선

## 2) 비목표(Non-Goals)

- 상수 값 자체의 변경 (순수 위치 이동만 수행)
- 새로운 상수 추가
- 상수 명명 규칙 변경 (기존 COL_/KEY_/DISPLAY_/DEFAULT_ 규칙 유지)
- 테스트 코드 내의 상수 정의 방식 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **상수 파일 비대화**: `tqqq/constants.py`가 364줄, 170개 이상의 상수 보유
- **코드 근접성 부족**: 한 파일에서만 사용되는 상수가 상수 파일에 있어 코드 이해가 어려움
- **불필요한 임포트**: 실제로 공유되지 않는 상수도 임포트 체인에 포함

### 새로운 상수 배치 규칙

| 사용 범위 | 배치 위치 |
|-----------|----------|
| 2개 이상 도메인에서 사용 | `common_constants.py` |
| 도메인 내 2개 이상 파일에서 사용 | `도메인/constants.py` |
| 1개 파일에서만 사용 | 해당 파일 상단 |

**카운트 규칙**:
- 제외: 테스트 코드 (`tests/`), 단순 로그 출력
- 포함: 비즈니스 로직 (`src/`, `scripts/`)

**특수 케이스**:
- 컬럼 그룹 상수: 그룹에 포함된 개별 `COL_*`은 그룹과 같은 위치에 유지

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 이동 대상 상수가 모두 해당 파일로 이동 완료
- [x] 상수 파일에서 이동된 상수 제거 및 `__all__` 업데이트
- [x] 임포트 구문 정리 (제거된 상수 임포트 삭제)
- [x] `poetry run python validate_project.py` 통과 (passed=205, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 루트 `CLAUDE.md`의 상수 배치 규칙 업데이트
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**상수 파일 (상수 제거)**:
- `src/qbt/common_constants.py` (1개 상수 제거)
- `src/qbt/backtest/constants.py` (13개 상수 제거)
- `src/qbt/tqqq/constants.py` (약 50개 상수 제거)

**대상 파일 (상수 추가)**:
- `src/qbt/utils/meta_manager.py`
- `src/qbt/backtest/strategy.py`
- `src/qbt/tqqq/simulation.py`
- `src/qbt/tqqq/analysis_helpers.py`
- `src/qbt/tqqq/data_loader.py`
- `scripts/backtest/run_grid_search.py`
- `scripts/tqqq/streamlit_rate_spread_lab.py`

### 데이터/결과 영향

- 출력 스키마 변경 없음 (상수 값 동일)
- 기존 결과 비교 불필요 (동작 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — common_constants.py 리팩토링

**이동 대상 (1개)**:
| 상수명 | 이동 위치 |
|--------|----------|
| MAX_HISTORY_COUNT | meta_manager.py |

**작업 내용**:

- [x] `MAX_HISTORY_COUNT`를 `src/qbt/utils/meta_manager.py` 상단으로 이동 (이미 완료됨)
- [x] `common_constants.py`에서 해당 상수 제거 (이미 완료됨)
- [x] `meta_manager.py`의 임포트 구문 정리 (이미 완료됨)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 2 — backtest/constants.py 리팩토링

**이동 대상 (13개)**:

| 상수명 | 이동 위치 |
|--------|----------|
| BUFFER_INCREMENT_PER_BUY | strategy.py |
| HOLD_DAYS_INCREMENT_PER_BUY | strategy.py |
| DAYS_PER_MONTH | strategy.py |
| DISPLAY_MA_WINDOW | run_grid_search.py |
| DISPLAY_BUFFER_ZONE | run_grid_search.py |
| DISPLAY_HOLD_DAYS | run_grid_search.py |
| DISPLAY_RECENT_MONTHS | run_grid_search.py |
| DISPLAY_TOTAL_RETURN | run_grid_search.py |
| DISPLAY_CAGR | run_grid_search.py |
| DISPLAY_MDD | run_grid_search.py |
| DISPLAY_TOTAL_TRADES | run_grid_search.py |
| DISPLAY_WIN_RATE | run_grid_search.py |
| DISPLAY_FINAL_CAPITAL | run_grid_search.py |

**작업 내용**:

- [x] `BUFFER_INCREMENT_PER_BUY`, `HOLD_DAYS_INCREMENT_PER_BUY`, `DAYS_PER_MONTH`을 `strategy.py` 상단으로 이동 (이미 완료됨)
- [x] `DISPLAY_*` 10개 상수를 `run_grid_search.py` 상단으로 이동 (이미 완료됨)
- [x] `backtest/constants.py`에서 해당 상수 제거 (이미 완료됨)
- [x] 임포트 구문 정리 (이미 완료됨)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 3 — tqqq/constants.py 리팩토링 (simulation.py)

**이동 대상**:
| 상수명 | 이동 위치 |
|--------|----------|
| INTEGRITY_TOLERANCE | simulation.py |
| MAX_EXPENSE_MONTHS_DIFF | simulation.py |

**작업 내용**:

- [x] `INTEGRITY_TOLERANCE`, `MAX_EXPENSE_MONTHS_DIFF`를 `simulation.py` 상단으로 이동 (이미 완료됨)
- [x] `tqqq/constants.py`에서 해당 상수 제거 및 `__all__` 업데이트 (이미 완료됨)
- [x] 임포트 구문 정리 (이미 완료됨)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 4 — tqqq/constants.py 리팩토링 (data_loader.py)

**이동 대상**:
| 상수명 | 이동 위치 |
|--------|----------|
| COMPARISON_COLUMNS | data_loader.py |

**작업 내용**:

- [x] `COMPARISON_COLUMNS`를 `data_loader.py` 상단으로 이동 (그룹에 포함된 COL_*도 함께) (이미 완료됨)
- [x] `tqqq/constants.py`에서 해당 상수 제거 및 `__all__` 업데이트 (이미 완료됨)
- [x] 임포트 구문 정리 (이미 완료됨)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 5 — tqqq/constants.py 리팩토링 (analysis_helpers.py)

**이동 대상 (약 40개)**:

| 카테고리 | 상수 목록 |
|----------|----------|
| 모델 스키마 | MODEL_SCHEMA_VERSION, COL_MODEL_* (14개) |
| 요약 통계 컬럼 | COL_CATEGORY, COL_X_VAR, COL_Y_VAR, COL_LAG, COL_N, COL_CORR, COL_SLOPE, COL_INTERCEPT, COL_MAX_ABS_DIFF, COL_MEAN_ABS_DIFF, COL_STD_DIFF |
| 요약 통계 출력 | DISPLAY_CATEGORY, DISPLAY_X_VAR, DISPLAY_Y_VAR, DISPLAY_LAG, DISPLAY_N, DISPLAY_CORR, DISPLAY_SLOPE, DISPLAY_INTERCEPT, DISPLAY_MAX_ABS_DIFF, DISPLAY_MEAN_ABS_DIFF, DISPLAY_STD_DIFF |
| 월별 피처 출력 | DISPLAY_MONTH, DISPLAY_DR_M, DISPLAY_E_M, DISPLAY_DE_M, DISPLAY_SUM_DAILY_M, DISPLAY_DR_LAG1, DISPLAY_DR_LAG2 |
| 기본값 | DEFAULT_LAG_LIST |

**작업 내용**:

- [x] 위 상수들을 `analysis_helpers.py` 상단으로 이동 (DISPLAY_RATE_PCT 추가 포함)
- [x] `tqqq/constants.py`에서 해당 상수 제거 및 `__all__` 업데이트
- [x] 임포트 구문 정리

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 6 — tqqq/constants.py 리팩토링 (streamlit_rate_spread_lab.py)

**이동 대상 (8개)**:

| 상수명 | 용도 |
|--------|------|
| DEFAULT_HISTOGRAM_BINS | 히스토그램 기본 bins |
| DEFAULT_LAG_OPTIONS | Delta 분석 lag 선택지 |
| DEFAULT_STREAMLIT_COLUMNS | 요약 통계 표시용 컬럼 개수 |
| KEY_META_TYPE_RATE_SPREAD_LAB | 메타데이터 타입 |
| DISPLAY_CHART_DIFF_DISTRIBUTION | 히스토그램 차트명 |
| DISPLAY_AXIS_DIFF_PCT | X축 레이블 |
| DISPLAY_AXIS_FREQUENCY | Y축 레이블 |
| DISPLAY_DELTA_MONTHLY_PCT | Delta 차트 y축 |

**작업 내용**:

- [x] 위 상수들을 `streamlit_rate_spread_lab.py` 상단으로 이동 (일부 상수는 새로 정의)
- [x] `tqqq/constants.py`에서 해당 상수 제거 및 `__all__` 업데이트
- [x] 임포트 구문 정리

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

---

### Phase 7 — 문서 정리 및 최종 검증

**작업 내용**

- [x] 루트 `CLAUDE.md`의 상수 배치 규칙 섹션 업데이트 (새 규칙 반영)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=205, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 상수 리팩토링 / 사용 위치 기반 상수 재배치 (코드 근접성 향상)
2. 상수 리팩토링 / 단일 파일 사용 상수를 해당 파일로 이동
3. 상수 리팩토링 / constants.py 경량화 및 로컬 상수 분리
4. 리팩토링 / 상수 배치 규칙 적용 (공유 vs 로컬 분리)
5. 리팩토링 / 상수 파일 정리 및 코드 근접성 개선

## 7) 리스크(Risks)

- **임포트 누락**: 상수 이동 시 임포트 구문 누락 가능 → 각 Phase에서 validate_project.py로 검증
- **테스트 실패**: 테스트 코드가 상수를 직접 임포트하는 경우 → 테스트 코드의 임포트 경로 확인 필요
- **순환 임포트**: 상수 이동으로 인한 새로운 순환 임포트 발생 가능 → Phase별 검증으로 조기 발견

## 8) 메모(Notes)

### 상수 사용 현황 분석 결과

**common_constants.py**:
- 이동 대상: 1개 (MAX_HISTORY_COUNT)
- 유지: 나머지 (2개 이상 파일에서 사용)

**backtest/constants.py**:
- 이동 대상: 13개
- 유지: 나머지 (strategy.py + scripts에서 공유)

**tqqq/constants.py**:
- 이동 대상: 약 50개
- 유지: 경로 상수, 비용 모델 파라미터, 공유 컬럼명 등

### 진행 로그 (KST)

- 2026-01-17 22:30: 계획서 초안 작성 완료, 사용자 승인 대기
- 2026-01-18: Phase 1-4 완료
- 2026-01-18: Phase 5-6 완료 (DISPLAY_*, DEFAULT_*, KEY_* 상수 이동)
- 2026-01-18: Phase 7 완료 (문서 정리 및 최종 검증) - 모든 검증 통과 ✅

---
