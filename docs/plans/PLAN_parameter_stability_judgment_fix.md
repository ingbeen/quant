# Implementation Plan: 파라미터 안정성 판정 로직 수정

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

**작성일**: 2026-03-05 21:00
**마지막 업데이트**: 2026-03-05 21:30
**관련 범위**: backtest, scripts
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

- [x] 인접 파라미터 비교 기준값을 단일 최적 Calmar에서 최적 셀 평균 Calmar로 변경
- [x] 판정 테이블을 2행에서 5행으로 확장 (히트맵 고원, MA 의존성, sell_buffer 의존성 추가)
- [x] 종합 판정을 2단계(통과/미달)에서 3단계(통과/조건부 통과/미달)로 변경

## 2) 비목표(Non-Goals)

- Calmar 분포 히스토그램(섹션 A) 변경
- MA별 히트맵(섹션 B) 변경
- Hold Days 변화 차트 변경
- 인접 파라미터 바 차트의 바 자체 변경 (기준선만 변경)
- grid_results.csv 파일 형식 또는 생성 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

overfitting_analysis_report.md 11.2절 1단계 검증 결과 분석 시, 기존 "인접 파라미터 Calmar (최적 대비 30% 이내)" 기준에 비교 대상 불일치 문제가 발견되었다.

- **기존**: 기준값 = 단일 최적 Calmar (grid_results.csv 1위, 예: 0.301). 이 값에는 hold_days=3, recent_months=0이라는 "최적 부차 파라미터"가 포함됨
- **인접값**: hold_days x recent_months 전체의 평균 집계값
- **문제**: 단일 최적값(특정 부차 파라미터) vs 평균 집계값으로 비교 기준이 공정하지 않음
- **해결**: 동일한 집계 기준(평균 대 평균)으로 비교하도록 변경

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `evaluate_stability_criteria`가 5개 기준의 판정 결과를 반환
- [x] 기준값이 최적 셀 평균 Calmar로 변경됨
- [x] 종합 판정이 3단계(통과/조건부 통과/미달)로 동작
- [x] 대시보드가 5행 판정 테이블 표시
- [x] Buy/Sell Buffer 차트의 기준선이 셀 평균 기반으로 변경
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/parameter_stability.py` — `evaluate_stability_criteria` 함수 확장
- `scripts/backtest/app_parameter_stability.py` — `_render_adjacent_comparison`, `_render_stability_summary`, `main` 수정
- `tests/test_parameter_stability.py` — 신규 테스트 파일 생성

### 데이터/결과 영향

- 출력 스키마 변경: `evaluate_stability_criteria` 반환 dict에 키 추가
- 기존 결과 CSV 영향 없음 (대시보드 표시 로직만 변경)

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트로 판정 로직 정책 고정 (레드)

**작업 내용**:

- [x] `tests/test_parameter_stability.py`에 테스트 추가 (기존 파일 확장)
- [x] 테스트 케이스 작성:
  - `test_evaluate_stability_returns_all_keys`: 반환 dict 키 완전성 검증
  - `test_evaluate_stability_opt_cell_mean_baseline`: 기준값이 셀 평균인지 검증
  - `test_evaluate_stability_plateau_detection`: 히트맵 고원 판정 검증
  - `test_evaluate_stability_adjacent_mean_vs_mean`: 평균 대 평균 비교 검증
  - `test_evaluate_stability_ma_dependency`: MA 의존성 판정 검증
  - `test_evaluate_stability_overall_three_tier_pass`: 통과 케이스 검증
  - `test_evaluate_stability_overall_three_tier_fail`: 미달 케이스 검증
  - `test_evaluate_stability_overall_three_tier_conditional`: 조건부 통과 케이스 검증

---

### Phase 1 — 비즈니스 로직 수정 (`parameter_stability.py`)

**작업 내용**:

- [x] `evaluate_stability_criteria` 시그니처 변경: `optimal_calmar` 파라미터 제거 (내부에서 셀 평균 계산)
- [x] 기준 1 (Calmar > 0) 로직 유지
- [x] 기준 2 (히트맵 고원) 추가: best_ma 내 9셀 max-min 차이 < 0.05
- [x] 기준 3 (인접 파라미터) 변경: 기준값을 최적 셀 평균으로 변경
- [x] 기준 4 (MA 의존성) 추가: MA=100 평균 vs best_ma 평균 비교
- [x] 기준 5 (sell_buffer 의존성) 추가: sell_buffer=0.01 평균 vs 전체 평균 비교
- [x] 종합 판정 3단계 로직 구현
- [x] 반환 dict에 새 키 추가 (`opt_cell_mean`, `plateau_range`, `plateau_pass`, `ma_gap_pct`, `sell_dependency_warn`, `overall_verdict`)
- [x] Phase 0 테스트 전부 통과 확인

---

### Phase 2 — 대시보드 수정 (`app_parameter_stability.py`)

**작업 내용**:

- [x] `main()`에서 `optimal_calmar` 대신 셀 평균 기반으로 전환
- [x] `_render_adjacent_comparison`: threshold 기준선을 셀 평균 x 0.70으로 변경
- [x] `_render_stability_summary`: 5행 판정 테이블 표시
- [x] 종합 판정 3단계 표시 (녹색/노란색/빨간색 배경)

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] 변경 기능 최종 검증
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=465, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 파라미터 안정성 판정 로직 수정 (평균 대 평균 비교 + 5개 기준 + 3단계 판정)
2. 백테스트 / 파라미터 안정성 기준값 불일치 수정 및 판정 테이블 확장
3. 백테스트 / 파라미터 안정성 대시보드 판정 로직 고도화 (셀 평균 기준 + 3단계)
4. 백테스트 / 파라미터 안정성 1단계 검증 기준 공정성 개선
5. 백테스트 / 파라미터 안정성 판정 기준 변경 (단일 최적 -> 셀 평균, 2행 -> 5행)

## 7) 리스크(Risks)

- `evaluate_stability_criteria` 시그니처 변경으로 기존 호출부(`app_parameter_stability.py`)도 함께 수정 필요 — Phase 2에서 처리
- MA=100이 grid에 없는 경우 MA 의존성 판정 불가 — 해당 기준 스킵 처리 필요

## 8) 메모(Notes)

- 기존 테스트 파일 없음 → Phase 0에서 신규 생성
- `build_heatmap_data` 함수를 셀 평균 계산에 재활용 가능

### 진행 로그 (KST)

- 2026-03-05 21:00: 계획서 초안 작성
- 2026-03-05 21:30: 전체 Phase 완료 (passed=465, failed=0, skipped=0)
