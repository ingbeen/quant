# Implementation Plan: 백테스트 4P 전환 + 고원 대시보드 + 스크립트 통합

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
**마지막 업데이트**: 2026-03-10 24:00
**관련 범위**: backtest, scripts, tests
**관련 문서**: `docs/overfitting_analysis_report.md`, `src/qbt/backtest/CLAUDE.md`
**선행 계획서**: `PLAN_backtest_cleanup.md` (완료 후 착수)

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

- [x] buffer_zone.py의 전체 CONFIGS를 4P 고정 파라미터(MA=200, buy=0.03, sell=0.05, hold=3)로 통일한다
- [x] buffer_zone_qqq_4p config를 buffer_zone_qqq로 통합하여 중복 제거한다
- [x] 고원 분석 스크립트 2개(run_hold_days_plateau.py + run_param_plateau.py)를 1개로 통합한다
- [x] parameter_stability.py를 고원 데이터 분석 모듈로 변환한다
- [x] app_parameter_stability.py를 QQQ 4개 파라미터 고원 시각화 대시보드로 변환한다
- [x] grid search 관련 코드를 정리한다 (스크립트 삭제, 결과 파일 삭제)

## 2) 비목표(Non-Goals)

- 버퍼존 전략 핵심 로직(buffer_zone_helpers.py) 변경
- buy_and_hold 전략 변경
- walkforward.py 모듈 변경 (Plan A에서 ATR 분기만 제거됨)
- 대시보드 app_single_backtest.py 변경 (전략 자동 탐색으로 변경 불필요)
- 새로운 전략 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- overfitting_analysis_report.md §2.1에서 최종 파라미터가 확정되었다: MA=200, buy=0.03, sell=0.05, hold=3
- 현재 buffer_zone.py CONFIGS에는 3가지 파라미터 결정 방식이 혼재한다:
  - buffer_zone_tqqq/qqq: `grid_results_path` 기반 폴백 (더 이상 불필요)
  - buffer_zone_qqq_4p: 고정 파라미터 (hold_days=2, 최종값 3이 아님)
  - cross-asset 6개: 고정 파라미터 (hold_days=2, 최종값 3이 아님)
- `_CROSS_ASSET_HOLD_DAYS = 2`이나 보고서 최종 확정값은 hold_days=3이다
- buffer_zone_qqq와 buffer_zone_qqq_4p가 사실상 동일 목적으로 중복 존재한다
- 고원 분석 스크립트 2개(hold_days + param_plateau)가 동일 패턴으로 중복이다
- app_parameter_stability.py는 grid_results.csv 기반 분석으로, 이미 결론 완료된 11.2절 전용이다
- run_grid_search.py는 4P 고정 전환 후 더 이상 실행할 대상이 없다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] buffer_zone.py CONFIGS 전체가 4P 고정 (8개, qqq_4p 통합)
- [x] hold_days=3이 전 자산에 적용됨
- [x] grid_results_path가 전 config에서 None
- [x] 고원 분석 스크립트 1개로 통합됨
- [x] parameter_stability.py가 고원 데이터 분석 모듈로 변환됨
- [x] app_parameter_stability.py가 4개 파라미터 고원 시각화 대시보드로 변환됨
- [x] test_parameter_stability.py가 새 모듈에 맞게 재작성됨
- [x] run_grid_search.py 삭제됨
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=405, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(CLAUDE.md 파일들)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

소스 변경:
- `src/qbt/backtest/strategies/buffer_zone.py`: CONFIGS 4P 전환, qqq_4p 제거
- `src/qbt/backtest/parameter_stability.py`: 고원 데이터 분석 모듈로 전면 재작성
- `src/qbt/common_constants.py`: `BUFFER_ZONE_QQQ_4P_RESULTS_DIR` 제거

스크립트 변경:
- `scripts/backtest/app_parameter_stability.py`: 고원 시각화 대시보드로 전면 재작성

스크립트 통합 (삭제 + 신규):
- `scripts/backtest/run_hold_days_plateau.py`: 삭제
- `scripts/backtest/run_param_plateau.py`: 삭제
- `scripts/backtest/run_param_plateau_all.py`: 신규 (4파라미터 통합)

스크립트 삭제:
- `scripts/backtest/run_grid_search.py`: 4P 전환으로 더 이상 불필요

테스트 변경:
- `tests/test_parameter_stability.py`: 새 모듈에 맞게 재작성
- `tests/test_buffer_zone.py`: buffer_zone_qqq_4p config 제거 반영

### 삭제 대상 결과 데이터

- `storage/results/backtest/buffer_zone_qqq_4p/`: qqq로 통합됨
- `storage/results/backtest/buffer_zone_tqqq/grid_results.csv`: 4P 전환으로 불필요
- `storage/results/backtest/buffer_zone_qqq/grid_results.csv`: 4P 전환으로 불필요

### 데이터/결과 영향

- 기존 고원 분석 결과 CSV (`hold_days_plateau/`, `param_plateau/`)는 유지 (대시보드 데이터 소스)
- buffer_zone_qqq_4p 결과는 삭제되나, buffer_zone_qqq 재실행 시 동일 결과 생성 가능
- grid_results.csv 삭제 후 run_single_backtest.py 실행 시 grid 폴백 없이 고정 파라미터 사용 (정상 동작)

## 6) 단계별 계획(Phases)

### Phase 1 — buffer_zone.py 4P 전환 + grid search 정리

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone.py` 수정:
  - `_CROSS_ASSET_HOLD_DAYS`: 2 → 3
  - buffer_zone_tqqq config: override 5개 설정, grid_results_path=None, ma_type="ema" 유지
  - buffer_zone_qqq config: override 5개 설정, grid_results_path=None
  - buffer_zone_qqq_4p config: 삭제 (buffer_zone_qqq와 통합)
  - CONFIGS 리스트: 9개 → 8개
  - 파라미터 확정값: MA=200, buy=0.03, sell=0.05, hold=3, recent=0
- [x] `src/qbt/common_constants.py` 수정: `BUFFER_ZONE_QQQ_4P_RESULTS_DIR` 제거
- [x] `scripts/backtest/run_grid_search.py` 삭제
- [x] `storage/results/backtest/buffer_zone_tqqq/grid_results.csv` 삭제
- [x] `storage/results/backtest/buffer_zone_qqq/grid_results.csv` 삭제
- [x] `storage/results/backtest/buffer_zone_qqq_4p/` 폴더 삭제
- [x] `tests/test_buffer_zone.py` 수정: buffer_zone_qqq_4p 관련 테스트 제거/수정

---

### Phase 2 — 고원 분석 스크립트 통합

**작업 내용**:

- [x] `scripts/backtest/run_param_plateau_all.py` 신규 작성:
  - 4개 실험 통합: hold_days + sell_buffer + buy_buffer + ma_window
  - 기존 2개 스크립트의 공통 패턴 추출:
    - 자산별 데이터 로딩 (1회) → 파라미터 변경 반복 실행 → summary 수집 → 피벗 CSV 생성
  - `--experiment` 인자: all(기본) / hold_days / sell_buffer / buy_buffer / ma_window
  - 결과 저장: 기존과 동일한 `param_plateau/` 디렉토리에 통합
  - hold_days 결과도 `param_plateau/`에 저장 (기존 `hold_days_plateau/`에서 이동)
- [x] `scripts/backtest/run_hold_days_plateau.py` 삭제
- [x] `scripts/backtest/run_param_plateau.py` 삭제
- [x] 고원 분석 스크립트 내 `buffer_zone_qqq_4p` 참조 → `buffer_zone_qqq`로 변경

---

### Phase 3 — parameter_stability 모듈 + 대시보드 변환

**작업 내용**:

- [x] `src/qbt/backtest/parameter_stability.py` 전면 재작성:
  - 기존: grid_results.csv 기반 분석 (히스토그램, 히트맵, 인접 비교, 판정)
  - 변경: 고원 분석 CSV 로딩 + 시각화용 데이터 가공
  - 주요 함수:
    - `load_plateau_pivot(param_name, metric)`: 피벗 CSV 로드 (예: `param_plateau_buy_buffer_calmar.csv`)
    - `load_plateau_detail()`: 상세 CSV 로드 (`param_plateau_all_detail.csv`)
    - `get_current_value(param_name)`: 현재 확정 파라미터값 반환 (MA=200, buy=0.03 등)
    - `find_plateau_range(series, threshold_ratio)`: 고원 구간 탐지 (최대값 대비 threshold 이상인 연속 범위)
- [x] `scripts/backtest/app_parameter_stability.py` 전면 재작성:
  - 4개 탭: ma_window / buy_buffer / sell_buffer / hold_days
  - 각 탭 구성:
    - Calmar 라인차트: X=파라미터값, Y=Calmar, 7자산 각각 라인 (Plotly)
    - 현재 확정값 마커: 수직 점선 + 주석
    - 고원 구간 하이라이트: 배경 음영
    - 보조 지표: CAGR, MDD 라인차트 (접을 수 있는 expander)
    - 거래 수 라인차트 (sell_buffer의 "거래 수 함정" 시각화용)
  - 데이터 소스: `storage/results/backtest/param_plateau/` + `hold_days_plateau/`
- [x] `tests/test_parameter_stability.py` 재작성:
  - 기존: grid_results 분석 함수 테스트
  - 변경: 고원 CSV 로딩, 고원 구간 탐지, 현재값 반환 함수 테스트

---

### Phase 4 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 갱신:
  - parameter_stability.py 섹션 재작성 (고원 분석 모듈)
  - buffer_zone.py CONFIGS 목록 갱신 (8개, 4P 고정)
  - grid_results.csv 관련 내용 정리
- [x] `scripts/CLAUDE.md` 갱신:
  - 고원 분석 스크립트 통합 반영
  - run_grid_search.py 제거 반영
  - app_parameter_stability.py 설명 갱신
- [x] `tests/CLAUDE.md` 갱신: test_parameter_stability.py 설명 갱신
- [x] 루트 `CLAUDE.md` 갱신: 디렉토리 구조, 스크립트 목록 업데이트
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=405, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 4P 고정 파라미터 전환 + 고원 시각화 대시보드 구현
2. 백테스트 / buffer_zone 전략 4P 통일 및 파라미터 안정성 대시보드 리뉴얼
3. 백테스트 / 파라미터 확정(MA200/buy3%/sell5%/hold3) + 고원 분석 통합
4. 백테스트 / grid search 폐지, 4P 고정 전환, 고원 대시보드 변환
5. 백테스트 / 과최적화 검증 완료 기반 4P 확정 + 시각화 리팩토링

## 7) 리스크(Risks)

- **buffer_zone_qqq_4p 삭제 시 고원 분석 스크립트 오동작**: Phase 2에서 참조를 buffer_zone_qqq로 변경하여 대응
- **grid_results.csv 삭제 후 run_single_backtest.py 영향**: grid_results_path=None이므로 grid 폴백이 자동으로 스킵됨. 영향 없음
- **parameter_stability.py 전면 재작성 시 기존 테스트 전체 실패**: Phase 3에서 모듈과 테스트를 함께 재작성하여 대응
- **고원 분석 결과 CSV가 stale 상태**: 통합 스크립트 실행 시 재생성 가능. 사용자가 직접 실행

## 8) 메모(Notes)

- 파라미터 확정 근거: overfitting_analysis_report.md §2.1 (방어 등급 A~B+)
- hold_days=3 근거: §17 (7자산 고원 교집합 3~5의 좌단, 4가지 학술 메커니즘)
- buffer_zone_tqqq의 ma_type은 "ema" 유지 (기존과 동일)
- resolve_buffer_params()와 load_best_grid_params() 함수는 유지 (grid_results_path=None 처리 가능, 향후 확장성)
- run_grid_search.py 삭제 근거: 4P 고정 전환으로 그리드 서치 대상이 없음. 향후 필요 시 git history에서 복원 가능
- 고원 분석 결과 CSV 파일명 규칙:
  - 피벗: `param_plateau_{param_name}_{metric}.csv` (예: `param_plateau_buy_buffer_calmar.csv`)
  - 상세: `param_plateau_all_detail.csv`
  - hold_days 결과는 Phase 2 이후 `param_plateau/` 디렉토리로 통합

### 진행 로그 (KST)

- 2026-03-10 22:00: 계획서 초안 작성
- 2026-03-10 24:00: 전체 Phase 완료, validate_project.py 통과 (passed=405, failed=0, skipped=0)

---
