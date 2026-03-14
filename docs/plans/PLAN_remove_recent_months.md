# Implementation Plan: recent_months 및 동적 조정 메커니즘 전체 제거

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

**작성일**: 2026-03-14 15:00
**마지막 업데이트**: 2026-03-14 15:00
**관련 범위**: backtest, scripts, tests, docs
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

- [ ] `recent_months` 파라미터를 상수, 타입, config, 비즈니스 로직, 테스트에서 전부 제거
- [ ] `recent_months`에 의존하는 동적 조정 메커니즘 전체 제거 (`_calculate_recent_sell_count`, 동적 조정 상수, `recent_sell_count` 필드, `all_exit_dates` 추적)
- [ ] 관련 CLAUDE.md 문서 및 주석 업데이트

## 2) 비목표(Non-Goals)

- `buy_buffer_pct`, `hold_days_used` 필드 제거 (동적 조정과 무관하게 파라미터 기록 용도로 유지)
- `docs/overfitting_analysis_report.md` 수정 (분석 보고서는 과거 기록이므로 보존)
- `docs/archive/` 하위 문서 수정
- `storage/results/` 하위 기존 CSV/JSON 결과 파일 삭제 (스크립트 재실행으로 덮어쓰기)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `recent_months`는 `FIXED_4P_RECENT_MONTHS = 0`으로 확정되어 **사실상 비활성화** 상태
- overfitting_analysis_report.md §2.1에서 그리드 서치 최적값이 `recent_months=0`으로 확인됨
- 코드에는 5개 파라미터(ma_window, buy_buffer, sell_buffer, hold_days, recent_months) 중 하나로 깊이 통합되어 있어 불필요한 복잡성 유발
- WFO 그리드 서치에서 `recent_months_list = [0, 4, 8, 12]`로 4배의 조합 증가를 유발하지만 최적값은 항상 0

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

---

## 영향도 분석

### 🔴 치명적 (CSV 스키마 변경 — 스크립트 재실행 필수)

| 영향 | 상세 | 대응 |
|------|------|------|
| **trades.csv 스키마** | `recent_sell_count` 컬럼 제거 | 모든 전략 스크립트 재실행 |
| **grid_results.csv 스키마** | `recent_months` 컬럼 제거 | `run_single_backtest.py` 재실행 |
| **walkforward CSV 스키마** | `best_recent_months` 컬럼 제거 | `run_walkforward.py` 재실행 |
| **walkforward_summary.json** | `param_recent_months` 키 제거 | `run_walkforward.py` 재실행 |
| **summary.json params** | `recent_months` 키 제거 | `run_single_backtest.py` 재실행 |
| **WFO 그리드 서치 조합 감소** | 4배 감소 (recent_months 차원 제거) | 성능 개선, 부작용 없음 |
| **대시보드 표시** | app_walkforward.py의 "Recent Months" 파라미터 추이 제거 | 기존 JSON과 호환 불가, 재실행 필요 |
| **대시보드 trades 테이블** | app_single_backtest.py의 "최근청산횟수" 컬럼 제거 | 기존 CSV와 호환 불가, 재실행 필요 |

### 🟡 주의 (로직 변경 — 테스트 수정 필수)

| 영향 | 상세 |
|------|------|
| **`BufferStrategyParams` 필드 축소** | `recent_months` 제거 → 모든 params 생성 코드 수정 |
| **`PendingOrder` 필드 축소** | `recent_sell_count` 제거 → 주문 생성/기록 코드 수정 |
| **`run_buffer_strategy()` 간소화** | 동적 조정 블록(856~869행) 제거, `all_exit_dates` 추적 제거 |
| **`run_grid_search()` 차원 축소** | `recent_months_list` 루프 제거, 파라미터 조합 감소 |
| **`run_walkforward()` 파라미터 축소** | `recent_months_list` 인자 제거, 최적 파라미터에서 제외 |
| **`resolve_buffer_params()` 인자 축소** | `recent_months` 인자 제거 |
| **`BufferZoneConfig` 필드 축소** | `recent_months` 기본값 필드 제거 |
| **TypedDict 3개 수정** | `BestGridParams`, `WfoWindowResultDict`, `WfoModeSummaryDict` |
| **테스트 파일 5개 수정** | 파라미터 전달, 결과 검증, 전용 테스트 제거 |

### 🟢 경미 (문서/주석만)

| 영향 | 상세 |
|------|------|
| `src/qbt/backtest/CLAUDE.md` | "조정 기간" 파라미터 설명, 동적 조정 섹션, 타입 설명 업데이트 |
| `scripts/CLAUDE.md` | WFO 파라미터 리스트 설명 업데이트 |
| `docs/tranche_architecture.md` | `recent_months=0` 언급 제거 |
| `docs/plans/PLAN_app_walkforward.md` | `param_recent_months` 언급 제거 |

---

## 제거 대상 상세 목록

### 상수 (`src/qbt/backtest/constants.py`)
- `DEFAULT_RECENT_MONTHS`
- `FIXED_4P_RECENT_MONTHS`
- `DEFAULT_WFO_RECENT_MONTHS_LIST`
- `COL_RECENT_MONTHS`
- `DISPLAY_RECENT_MONTHS`

### 동적 조정 상수 (`src/qbt/backtest/strategies/buffer_zone_helpers.py`)
- `DEFAULT_BUFFER_INCREMENT_PER_BUY`
- `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY`
- `DEFAULT_DAYS_PER_MONTH`

### 함수
- `_calculate_recent_sell_count()` (buffer_zone_helpers.py)

### 타입 필드
- `BestGridParams.recent_months`
- `WfoWindowResultDict.best_recent_months`
- `WfoModeSummaryDict.param_recent_months`
- `BufferStrategyParams.recent_months`
- `PendingOrder.recent_sell_count`
- `EquityRecord.recent_sell_count` (TypedDict 내)
- `GridSearchResultDict.recent_months` (TypedDict 내)
- `BufferZoneConfig.recent_months`

### 로직 블록
- `run_buffer_strategy()` 내 동적 조정 블록 (4-1 섹션)
- `run_buffer_strategy()` 내 `all_exit_dates` 관련 코드
- `run_buffer_strategy()` 내 `entry_recent_sell_count` 관련 코드
- `run_grid_search()` 내 `recent_months_list` 루프
- `run_walkforward()` 내 `recent_months_list` 파라미터 및 관련 로직
- `resolve_buffer_params()` 내 `recent_months` 인자
- `_validate_buffer_strategy_inputs()` 내 `recent_months` 검증

---

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] `recent_months` 관련 상수·타입·로직·주석 전부 제거
- [ ] 동적 조정 메커니즘 전부 제거 (상수, 함수, 로직 블록)
- [ ] `recent_sell_count` 필드 전부 제거 (EquityRecord, PendingOrder, trades 기록)
- [ ] 테스트 수정 (관련 테스트 삭제/업데이트)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] CLAUDE.md 문서 업데이트 (backtest, scripts)
- [ ] 기타 문서 업데이트 (tranche_architecture.md, plans)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직 (src/qbt/backtest/)**:
- `constants.py` — 상수 5개 제거
- `types.py` — TypedDict 필드 3개 제거
- `strategies/buffer_zone_helpers.py` — 동적 조정 상수 3개, 함수 1개, 타입 필드, 로직 블록 제거
- `strategies/buffer_zone.py` — config 필드 1개, import 1개 제거
- `walkforward.py` — 파라미터, import, 로직 제거

**스크립트 (scripts/backtest/)**:
- `run_walkforward.py` — `recent_months_list` 전달 제거
- `run_param_plateau_all.py` — `_FIXED_RECENT_MONTHS` 및 사용처 제거
- `app_walkforward.py` — "Recent Months" 파라미터 추이 제거
- `app_single_backtest.py` — "최근청산횟수" 컬럼 매핑 제거

**테스트 (tests/)**:
- `test_buffer_zone_helpers.py` — `_calculate_recent_sell_count` 테스트 삭제, params 수정
- `test_buffer_zone.py` — `FIXED_4P_RECENT_MONTHS` 검증 제거
- `test_integration.py` — `recent_months=0` 제거
- `test_backtest_walkforward.py` — `recent_months` 관련 제거
- `test_wfo_stitched.py` — `recent_months` 컬럼 검증 제거

**문서**:
- `src/qbt/backtest/CLAUDE.md` — 파라미터 설명, 동적 조정 섹션, 타입 설명
- `scripts/CLAUDE.md` — WFO 파라미터 리스트 언급 (해당 시)
- `docs/tranche_architecture.md` — `recent_months=0` 언급
- `docs/plans/PLAN_app_walkforward.md` — `param_recent_months` 언급

### 데이터/결과 영향

- **trades.csv**: `recent_sell_count` 컬럼 소멸 → 스크립트 재실행 필요
- **grid_results.csv**: `recent_months` 컬럼 소멸 → 스크립트 재실행 필요
- **walkforward CSV**: `best_recent_months` 컬럼 소멸 → 스크립트 재실행 필요
- **walkforward_summary.json**: `param_recent_months` 키 소멸 → 스크립트 재실행 필요
- **summary.json**: params 내 `recent_months` 키 소멸 → 스크립트 재실행 필요
- **param_plateau CSV**: `recent_months` 고정값 전달 제거, CSV 스키마 자체는 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 상수·타입·config 제거 (그린 유지 불가, 컴파일 오류 허용)

**작업 내용**:

- [ ] `src/qbt/backtest/constants.py`: 상수 5개 제거 (`DEFAULT_RECENT_MONTHS`, `FIXED_4P_RECENT_MONTHS`, `DEFAULT_WFO_RECENT_MONTHS_LIST`, `COL_RECENT_MONTHS`, `DISPLAY_RECENT_MONTHS`)
- [ ] `src/qbt/backtest/types.py`: TypedDict 필드 3개 제거 (`BestGridParams.recent_months`, `WfoWindowResultDict.best_recent_months`, `WfoModeSummaryDict.param_recent_months`)
- [ ] `src/qbt/backtest/strategies/buffer_zone_helpers.py`:
  - 동적 조정 상수 3개 제거 (`DEFAULT_BUFFER_INCREMENT_PER_BUY`, `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY`, `DEFAULT_DAYS_PER_MONTH`)
  - `_calculate_recent_sell_count()` 함수 삭제
  - `BufferStrategyParams.recent_months` 필드 제거
  - `PendingOrder.recent_sell_count` 필드 제거
  - `EquityRecord` TypedDict에서 `recent_sell_count` 제거
  - `GridSearchResultDict`에서 `recent_months` 제거
  - `resolve_buffer_params()`에서 `recent_months` 인자 제거
  - `_validate_buffer_strategy_inputs()`에서 `recent_months` 검증 제거
  - `run_buffer_strategy()`에서 동적 조정 블록 제거, `all_exit_dates` 제거, `entry_recent_sell_count` 제거
  - `run_grid_search()`에서 `recent_months_list` 파라미터 및 루프 제거
  - `_run_buffer_strategy_for_grid()` 결과에서 `recent_months` 제거
  - 관련 주석·docstring 정리
- [ ] `src/qbt/backtest/strategies/buffer_zone.py`:
  - `FIXED_4P_RECENT_MONTHS` import 제거
  - `BufferZoneConfig.recent_months` 필드 제거
  - `resolve_params_for_config()` 내 `recent_months` 전달 제거
- [ ] `src/qbt/backtest/walkforward.py`:
  - `DEFAULT_WFO_RECENT_MONTHS_LIST` import 제거
  - `run_walkforward()` 파라미터에서 `recent_months_list` 제거
  - 최적 파라미터 추출에서 `recent_months` 제거
  - OOS 평가 시 params 생성에서 `recent_months` 제거
  - `_WFO_CSV_REQUIRED_COLUMNS`, `_WFO_CSV_INT_COLUMNS`에서 제거
  - `calculate_wfo_mode_summary()`에서 `param_recent_months` 제거
  - Stitched Equity `build_params_schedule()` 내 `recent_months` 제거
  - 관련 주석·docstring 정리

---

### Phase 2 — 스크립트 수정 (그린 유지)

**작업 내용**:

- [ ] `scripts/backtest/run_walkforward.py`:
  - `DEFAULT_WFO_RECENT_MONTHS_LIST` import 제거
  - `_run_single_mode()` 파라미터에서 `recent_months_list` 제거
  - Fully Fixed 모드 params 생성에서 `recent_months` 제거
  - 메타데이터에서 `recent_months_list` 제거
- [ ] `scripts/backtest/run_param_plateau_all.py`:
  - `_FIXED_RECENT_MONTHS` 상수 제거
  - 4개 실험 함수에서 `recent_months=_FIXED_RECENT_MONTHS` 전달 제거
- [ ] `scripts/backtest/app_walkforward.py`:
  - `("param_recent_months", "Recent Months")` 항목 제거
- [ ] `scripts/backtest/app_single_backtest.py`:
  - `"recent_sell_count": "최근청산횟수"` 매핑 제거

---

### Phase 3 — 테스트 수정 (그린 유지)

**작업 내용**:

- [ ] `tests/test_buffer_zone_helpers.py`:
  - `_calculate_recent_sell_count` 관련 테스트 클래스/메서드 전부 삭제
  - `BufferStrategyParams` 생성에서 `recent_months` 제거
  - `PendingOrder` 생성에서 `recent_sell_count` 제거
  - 그리드 서치 결과 검증에서 `COL_RECENT_MONTHS` 제거
  - 동적 조정 관련 테스트 삭제
- [ ] `tests/test_buffer_zone.py`:
  - `FIXED_4P_RECENT_MONTHS` import 및 assert 제거
  - `resolve_params_for_config()` 테스트에서 `recent_months` 검증 제거
- [ ] `tests/test_integration.py`:
  - `BufferStrategyParams` 생성에서 `recent_months=0` 제거
- [ ] `tests/test_backtest_walkforward.py`:
  - WFO 파라미터에서 `recent_months_list` 제거
  - 결과 검증에서 `best_recent_months` 제거
- [ ] `tests/test_wfo_stitched.py`:
  - `recent_months` 컬럼 관련 검증 제거

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - "조정 기간 (`recent_months`)" 파라미터 설명 제거
  - "동적 파라미터 조정 (청산 기반)" 섹션 전체 제거
  - `BufferStrategyParams` 설명에서 `recent_months` 제거
  - `BestGridParams` 설명에서 `recent_months` 제거
  - `WfoWindowResultDict` 설명에서 `best_recent_months` 제거
  - 동적 조정 상수 (`DEFAULT_BUFFER_INCREMENT_PER_BUY` 등) 설명 제거
  - `_calculate_recent_sell_count` 헬퍼 함수 목록에서 제거
  - "동적 파라미터 조정" 테스트 범위 설명 제거
  - "upper_band: recent_sell_count 기반 동적 확장" 등 주석 업데이트
- [ ] `docs/tranche_architecture.md`:
  - `recent_months=0` 언급 제거
- [ ] `docs/plans/PLAN_app_walkforward.md`:
  - `param_recent_months` 언급 제거
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

## 변경 후 재실행이 필요한 스크립트 목록

> 코드 변경 완료 후, 아래 스크립트를 순서대로 재실행하여 CSV/JSON 결과를 갱신해야 합니다.

| 순서 | 스크립트 | 사유 | 영향받는 결과 파일 |
|------|----------|------|-------------------|
| 1 | `scripts/backtest/run_single_backtest.py --strategy all` | trades.csv에서 `recent_sell_count` 제거, grid_results.csv에서 `recent_months` 제거, summary.json params 변경 | `storage/results/backtest/*/trades.csv`, `grid_results.csv`, `summary.json` |
| 2 | `scripts/backtest/run_walkforward.py --strategy all` | walkforward CSV에서 `best_recent_months` 제거, summary에서 `param_recent_months` 제거, WFO 그리드 조합 감소 | `storage/results/backtest/*/walkforward_*.csv`, `walkforward_summary.json` |
| 3 | `scripts/backtest/run_param_plateau_all.py` | `recent_months` 고정값 전달 제거 (CSV 스키마 자체는 변경 없으나 결과값 변경 가능) | `storage/results/backtest/param_plateau/*.csv` |

> 대시보드 앱(`app_single_backtest.py`, `app_walkforward.py`, `app_parameter_stability.py`)은
> 위 스크립트 재실행 후 자동으로 갱신된 데이터를 읽으므로 별도 실행 불필요.

---

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / recent_months 및 동적 조정 메커니즘 전체 제거
2. 백테스트 / 미사용 recent_months 파라미터·동적 조정 로직 제거
3. 백테스트 / recent_months 제거로 전략 파라미터 5P→4P 축소
4. 리팩토링 / 비활성 recent_months·동적 조정 코드 전체 정리
5. 백테스트 / 불필요한 recent_months 차원 제거 및 문서 정리

## 7) 리스크(Risks)

| 리스크 | 영향도 | 완화책 |
|--------|--------|--------|
| CSV 스키마 변경으로 기존 대시보드 깨짐 | 높음 | 스크립트 재실행으로 결과 파일 갱신 |
| WFO 그리드 조합 감소로 과거 결과와 수치 불일치 | 중간 | `recent_months=0`이 항상 최적이었으므로 동일 결과 예상 |
| 테스트 누락으로 회귀 발생 | 중간 | validate_project.py 전체 검증으로 대응 |
| `docs/overfitting_analysis_report.md`와 코드 불일치 | 낮음 | 보고서는 과거 분석 기록이므로 수정하지 않음 (Non-Goals) |

## 8) 메모(Notes)

- `recent_months`는 overfitting_analysis_report.md에서 "1위 파라미터가 가장 단순: recent_months=0으로 동적 조정 미사용"으로 확인됨
- `FIXED_4P_RECENT_MONTHS = 0`으로 확정된 이후 코드 전반에서 항상 0으로 사용되어 실질적 효과 없음
- WFO 그리드에서 `recent_months_list = [0, 4, 8, 12]` 제거 시 조합 4배 감소 → 실행 성능 개선 기대
- `buy_buffer_pct`, `hold_days_used` 필드는 동적 조정 없이도 파라미터 기록 용도로 유지

### 진행 로그 (KST)

- 2026-03-14 15:00: 계획서 초안 작성 (Draft)
