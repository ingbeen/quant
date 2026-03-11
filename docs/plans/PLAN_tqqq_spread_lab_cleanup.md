# Implementation Plan: TQQQ 스프레드 모델 검증 코드 정리

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

**작성일**: 2026-03-11 12:00
**마지막 업데이트**: 2026-03-11 12:00
**관련 범위**: tqqq, scripts, tests, storage
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `docs/archive/backtest_removed_modules.md` (형식 참고)
**선행 계획서**: 없음 (독립 작업)

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

- [x] Softplus 스프레드 모델 검증 완료에 따라 일회성 CLI 스크립트 3개를 삭제한다
- [x] 삭제 스크립트 전용 소스 모듈 2개(optimization.py, walkforward.py)를 삭제한다
- [x] analysis_helpers.py에서 삭제 스크립트 전용 함수 8개를 제거한다
- [x] types.py, constants.py에서 삭제 모듈 전용 항목을 정리한다
- [x] 삭제 대상의 목적, 결론, 주요 수치를 `docs/archive/`에 문서화한다
- [x] README.md를 업데이트한다

## 2) 비목표(Non-Goals)

- `app_rate_spread_lab.py` 변경 또는 삭제 (유지)
- `simulation.py` 로직 변경
- `data_loader.py` 변경
- `visualization.py` 변경 (앱이 4개 차트 함수 모두 사용)
- `generate_daily_comparison.py`, `generate_synthetic.py` 변경
- `app_daily_comparison.py` 변경
- 앱이 로드하는 8개 결과 CSV 삭제

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- Softplus 동적 스프레드 모델 파라미터가 확정되었다 (a=-6.1, b=0.37)
- 워크포워드 3-Mode 검증이 완료되었다 (과최적화 진단 완료)
- `scripts/CLAUDE.md`에서 spread_lab을 "스프레드 모델 확정 후 재검증이 필요한 경우에만 사용하는 스크립트"로 정의하고 있다
- 결론 완료된 일회성 CLI 스크립트(tune, validate, generate)가 남아 있으면 유지보수 부담 증가
- 해당 스크립트 전용 소스 모듈(optimization.py, walkforward.py)도 불필요
- 단, `app_rate_spread_lab.py`(시각화 대시보드)는 유지하여 결과를 열람 가능하게 한다
- 앱은 이미 생성된 CSV를 로드만 하므로, CSV 생성 스크립트 삭제와 무관하게 동작한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 삭제 대상 스크립트 3개 삭제 완료
- [x] 삭제 대상 소스 모듈 2개 삭제 완료
- [x] analysis_helpers.py에서 삭제 스크립트 전용 함수 8개 제거 완료
- [x] types.py에서 삭제 모듈 전용 TypedDict 3개 제거 완료
- [x] constants.py에서 삭제 모듈 전용 상수 제거 완료
- [x] 삭제 대상 테스트 2개 삭제, 1개 수정 완료
- [x] 앱 미사용 결과 CSV 3개 삭제 완료
- [x] 삭제 대상 문서화 완료 (`docs/archive/tqqq_removed_modules.md`)
- [x] `app_rate_spread_lab.py` 정상 동작 확인 (import 에러 없음)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] README.md 업데이트 완료
- [x] CLAUDE.md 파일들 갱신 완료 (루트, tqqq, scripts, tests)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 삭제 대상 파일

소스 모듈 (2개):
- `src/qbt/tqqq/optimization.py`
- `src/qbt/tqqq/walkforward.py`

스크립트 (3개):
- `scripts/tqqq/spread_lab/generate_rate_spread_lab.py`
- `scripts/tqqq/spread_lab/tune_softplus_params.py`
- `scripts/tqqq/spread_lab/validate_walkforward.py`

테스트 (2개):
- `tests/test_tqqq_optimization.py`
- `tests/test_tqqq_walkforward.py`

### 삭제 대상 결과 데이터

앱 미사용 CSV (3개):
- `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_monthly.csv`
- `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_summary.csv`
- `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_model.csv`

### 수정 대상 파일

소스:
- `src/qbt/tqqq/analysis_helpers.py`: 삭제 스크립트 전용 함수 8개 제거
- `src/qbt/tqqq/types.py`: TypedDict 3개 제거 (SimulationCacheDict, SoftplusCandidateDict, WalkforwardSummaryDict)
- `src/qbt/tqqq/constants.py`: 삭제 모듈 전용 상수 제거 (grep으로 사용처 개별 확인)

테스트:
- `tests/test_tqqq_analysis_helpers.py`: 삭제 함수 테스트 제거, 유지 함수 테스트 보존

문서:
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- 루트 `CLAUDE.md`
- `README.md`

### 신규 생성 파일

- `docs/archive/tqqq_removed_modules.md`: 삭제 대상 문서화

### 데이터/결과 영향

- 앱이 로드하는 8개 결과 CSV (튜닝, 워크포워드)는 유지됨
- 삭제되는 3개 CSV (monthly, summary, model)는 앱에서 로드하지 않으므로 영향 없음
- `tqqq_daily_comparison.csv`는 유지됨 (앱 + generate_daily_comparison.py 공용)
- 향후 재검증이 필요한 경우 git history에서 삭제된 스크립트/모듈 복원 가능

## 6) 단계별 계획(Phases)

### Phase 1 — 삭제 대상 문서화

**작업 내용**:

- [x] `docs/archive/tqqq_removed_modules.md` 작성
  - 삭제 대상 2개 모듈 각각에 대해: 목적, 핵심 함수, 폐기 사유
  - 삭제 대상 3개 스크립트에 대해: 쓰임새, 선행/후행 관계
  - analysis_helpers.py에서 삭제되는 8개 함수 목록 및 사유
  - 삭제 대상 결과 CSV 3개 기록

---

### Phase 2 — 소스 모듈/스크립트/테스트 삭제

**작업 내용**:

- [x] 소스 모듈 2개 삭제
  - `src/qbt/tqqq/optimization.py`
  - `src/qbt/tqqq/walkforward.py`
- [x] 스크립트 3개 삭제
  - `scripts/tqqq/spread_lab/generate_rate_spread_lab.py`
  - `scripts/tqqq/spread_lab/tune_softplus_params.py`
  - `scripts/tqqq/spread_lab/validate_walkforward.py`
- [x] 테스트 2개 삭제
  - `tests/test_tqqq_optimization.py`
  - `tests/test_tqqq_walkforward.py`
- [x] 결과 CSV 3개 삭제
  - `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_monthly.csv`
  - `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_summary.csv`
  - `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_model.csv`

---

### Phase 3 — 잔여 코드 정리

**작업 내용**:

- [x] `src/qbt/tqqq/analysis_helpers.py` 수정: 삭제 스크립트 전용 함수 8개 제거
  - `add_rolling_features`
  - `build_model_dataset`
  - `save_monthly_features`
  - `save_summary_statistics`
  - `save_model_csv`
  - `save_walkforward_results`
  - `save_walkforward_summary`
  - `save_static_spread_series`
  - 불필요해진 import 정리 (WalkforwardSummaryDict 등)
- [x] `src/qbt/tqqq/types.py` 수정: TypedDict 3개 제거
  - `SimulationCacheDict`
  - `SoftplusCandidateDict`
  - `WalkforwardSummaryDict`
- [x] `src/qbt/tqqq/constants.py` 수정: 삭제 모듈 전용 상수 제거
  - grep으로 남은 코드(simulation.py, data_loader.py, visualization.py, analysis_helpers.py, app_rate_spread_lab.py, app_daily_comparison.py)에서의 사용 여부 확인
  - 사용처 없는 상수만 삭제
  - 삭제 대상 카테고리: Grid Search 범위 (Stage 1/2 a/b), 워크포워드 학습 파라미터 (DEFAULT_TRAIN_WINDOW_MONTHS), 삭제 CSV 경로 상수, 삭제 함수 전용 분석 기본값
- [x] `src/qbt/tqqq/__init__.py` 확인: 삭제 모듈 export 여부 확인 (현재 simulation만 export, 변경 불필요 예상)
- [x] `tests/test_tqqq_analysis_helpers.py` 수정: 삭제 함수 테스트 제거, 유지 함수 테스트 보존

---

### Phase 4 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 갱신: 삭제 모듈 섹션 제거, analysis_helpers 함수 목록 갱신
- [x] `scripts/CLAUDE.md` 갱신: 삭제 스크립트 제거, spread_lab 설명 갱신 (앱만 유지)
- [x] `tests/CLAUDE.md` 갱신: 삭제 테스트 파일 제거
- [x] 루트 `CLAUDE.md` 갱신: 디렉토리 구조 업데이트 (spread_lab 내 삭제 파일 반영, validate_walkforward_fixed_b/fixed_ab 잘못된 항목 제거)
- [x] `README.md` 갱신: spread_lab 섹션에서 삭제 스크립트 명령어 제거, 앱 실행 명령만 유지
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=352, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 스프레드 모델 검증 완료 코드 삭제 및 정리
2. TQQQ시뮬레이션 / spread_lab 일회성 스크립트·모듈 삭제 + 아카이브 문서화
3. TQQQ시뮬레이션 / optimization·walkforward 모듈 제거 및 analysis_helpers 경량화
4. TQQQ시뮬레이션 / 모델 확정 후 검증 코드 정리 (2모듈+3스크립트+2테스트 삭제)
5. TQQQ시뮬레이션 / 확정 파라미터 기반 일회성 검증 코드 아카이빙 + README 갱신

## 7) 리스크(Risks)

- **constants.py 상수 오삭제**: 앱(app_rate_spread_lab.py)이 직접 import하는 상수를 실수로 삭제할 위험. 대응: grep으로 남은 모든 소스/스크립트에서 사용 여부를 개별 확인 후 삭제
- **analysis_helpers.py 함수 오삭제**: simulation.py가 사용하는 2개 함수(calculate_signed_log_diff_from_cumulative_returns, validate_integrity)를 실수로 삭제할 위험. 대응: 유지 함수 목록을 명확히 정의하고 삭제 대상 8개만 제거
- **test_tqqq_analysis_helpers.py 수정 시 유지 함수 테스트 손실**: 대응: 삭제 함수 테스트만 선별 제거, 유지 함수 테스트는 그대로 보존
- **테스트 수 감소**: 현재 passed=405에서 감소 예상. 핵심 기능(simulation, data_loader, visualization) 테스트에 영향 없음

## 8) 메모(Notes)

- 삭제 근거: Softplus 파라미터 확정 (a=-6.1, b=0.37), 워크포워드 3-Mode 검증 완료
- `app_rate_spread_lab.py` 유지 결정: 결과 열람용 시각화 대시보드로서 가치 있음
- 앱이 로드하는 8개 결과 CSV는 유지: 튜닝(2개) + 워크포워드 3-Mode(6개)
- 앱 미사용 3개 CSV(monthly, summary, model)만 삭제: generate_rate_spread_lab.py 전용 출력
- 루트 CLAUDE.md에 `validate_walkforward_fixed_b.py`, `validate_walkforward_fixed_ab.py`가 기재되어 있으나 실제 파일이 존재하지 않음 (이미 validate_walkforward.py에 통합됨). Phase 4에서 수정
- 향후 재검증 필요 시 git history에서 복원 가능

### 진행 로그 (KST)

- 2026-03-11 12:00: 계획서 초안 작성

---
