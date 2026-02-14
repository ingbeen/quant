# Implementation Plan: 연속 워크포워드 RMSE 연산 위치 이동 + UI 해석 텍스트 + README 현행화

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

**작성일**: 2026-02-14 20:30
**마지막 업데이트**: 2026-02-14 21:00
**관련 범위**: tqqq, scripts
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 목표 1: 연속 워크포워드 RMSE 연산을 `validate_walkforward.py` 스크립트로 이동하여, 앱에서 연산 없이 저장된 값을 읽기만 하도록 변경
- [x] 목표 2: "RMSE 정합 비교" 섹션의 "현재 지표 해석 & 판단(결과)" 영역에 실제 수치 기반 해석 텍스트 작성
- [x] 목표 3: README.md를 현행화하고, 앱 실행 시 선행해야 할 스크립트를 명확히 기재

## 2) 비목표(Non-Goals)

- `calculate_stitched_walkforward_rmse()` 함수 자체의 로직 변경
- 기존 워크포워드 CSV (`tqqq_rate_spread_lab_walkforward.csv`) 컬럼 변경
- RMSE 수식 변경
- 새로운 지표 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **앱 내 연산**: 현재 연속 워크포워드 RMSE는 Streamlit 앱(`app_rate_spread_lab.py`)에서 계산됨. `_calculate_stitched_rmse()` 함수가 QQQ, TQQQ, FFR, Expense 데이터를 모두 로드하고 `simulate()`를 호출하여 연산 수행. 앱에서 연산 작업을 하지 않는 것이 바람직함.
2. **해석 텍스트 부재**: "현재 지표 해석 & 판단(결과)" 영역이 일반적인 안내 문구만 있고, 실제 수치(정적 RMSE 1.0467% vs 연속 워크포워드 RMSE 2.9258%)에 대한 구체적 해석이 없음.
3. **README 비현행**: 앱 실행 전 필요한 선행 스크립트 목록이 명확하지 않음. 워크포워드 관련 내용 보완 필요.

### 변경 전략

- `validate_walkforward.py`에서 워크포워드 완료 직후 `calculate_stitched_walkforward_rmse()`를 호출
- 결과를 `WalkforwardSummaryDict`에 `stitched_rmse` 키로 추가
- `save_walkforward_summary()`가 이 값을 summary CSV에 포함
- `app_rate_spread_lab.py`에서는 summary CSV에서 `stitched_rmse` 값을 읽기만 함
- 앱의 `_calculate_stitched_rmse()` 함수 및 `calculate_stitched_walkforward_rmse` import 제거

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `validate_walkforward.py`에서 연속 RMSE를 계산하고 summary에 포함하여 저장
- [x] `WalkforwardSummaryDict`에 `stitched_rmse` 키 추가
- [x] `save_walkforward_summary()`가 `stitched_rmse`를 CSV에 저장
- [x] `app_rate_spread_lab.py`에서 연산 로직 제거, summary CSV에서 값 읽기로 전환
- [x] "현재 지표 해석 & 판단(결과)" 영역에 수치 기반 해석 텍스트 추가
- [x] README.md 현행화 (앱 실행 전 선행 스크립트 명시)
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=266, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/tqqq/types.py`: `WalkforwardSummaryDict`에 `stitched_rmse` 키 추가
- `src/qbt/tqqq/analysis_helpers.py`: `save_walkforward_summary()`에 optional 키 처리 추가
- `scripts/tqqq/validate_walkforward.py`: 연속 RMSE 계산 로직 추가, summary에 포함
- `scripts/tqqq/app_rate_spread_lab.py`: 연산 로직 제거 → summary CSV에서 읽기로 전환 + 해석 텍스트 작성
- `README.md`: 현행화 + 선행 스크립트 명시
- `tests/test_tqqq_analysis_helpers.py`: `save_walkforward_summary` 테스트에 `stitched_rmse` 키 추가 + 하위호환성 테스트 추가

### 데이터/결과 영향

- `tqqq_rate_spread_lab_walkforward_summary.csv`: `stitched_rmse` 행 추가 (기존 행 유지)
- 기존 CSV의 다른 컬럼/행에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — summary에 stitched_rmse 저장 지원 + 스크립트 이동 (그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/types.py`: `WalkforwardSummaryDict`에 `stitched_rmse: NotRequired[float]` 키 추가
- [x] `src/qbt/tqqq/analysis_helpers.py`: `save_walkforward_summary()`에 optional 키 처리 추가 (required_keys와 별도)
- [x] `scripts/tqqq/validate_walkforward.py`:
  - `calculate_stitched_walkforward_rmse` import 추가
  - 워크포워드 완료 후(결과 요약 출력 전) 연속 RMSE 계산 호출
  - `summary` dict에 `stitched_rmse` 값 삽입 (run_walkforward_validation 반환 후)
  - 결과 로그 출력
  - 메타데이터에도 `stitched_rmse` 포함
- [x] `tests/test_tqqq_analysis_helpers.py`: `save_walkforward_summary` 관련 테스트에 `stitched_rmse` 키 추가 + 하위호환성 테스트 추가
- [x] `tests/test_tqqq_simulation.py`: 기존 `TestCalculateStitchedWalkforwardRmse` 테스트 영향 없음 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=266, failed=0, skipped=0)

---

### Phase 2 — 앱 연산 제거 + 읽기 전환 + 해석 텍스트 (그린 유지)

**작업 내용**:

- [x] `scripts/tqqq/app_rate_spread_lab.py`:
  - `_calculate_stitched_rmse()` 함수 삭제
  - `calculate_stitched_walkforward_rmse` import 제거
  - `load_stock_data`, `load_expense_ratio_data` import 제거 (stitched 전용 사용분)
  - `QQQ_DATA_PATH`, `TQQQ_DATA_PATH`, `EXPENSE_RATIO_DATA_PATH` import 제거
  - `_render_rmse_comparison()` 수정: summary dict에서 `stitched_rmse` 키로 값 읽기
  - `_render_rmse_interpretation()` 신규 함수 추가: 정적/연속 RMSE 대소 관계에 따른 동적 해석 텍스트 생성

**Validation**:

- [x] `poetry run python validate_project.py` (passed=266, failed=0, skipped=0)

---

### Phase 3 (마지막) — README 현행화 + 문서 정리 + 최종 검증

**작업 내용**

- [x] `README.md` 현행화:
  - 워크플로우 2의 앱 실행 전 선행 스크립트를 명확히 정리
  - 대시보드 앱 섹션 분리: 각 앱별 선행 번호 명시
  - 번호 순서 정리 (기존 "# 5" 중복 수정 → 합성 데이터를 #7로 이동)
  - 주요 결과 파일에 `walkforward_summary.csv` 추가
  - 문제 해결 섹션 업데이트
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=266, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 연속 워크포워드 RMSE 연산을 스크립트로 이동하여 앱 연산 제거
2. TQQQ시뮬레이션 / stitched RMSE를 워크포워드 스크립트에서 사전 계산 후 summary CSV에 저장
3. TQQQ시뮬레이션 / 앱 내 연속 RMSE 연산 제거 및 사전 계산 방식으로 전환
4. TQQQ시뮬레이션 / 연속 워크포워드 RMSE 사전 계산 + 해석 텍스트 + README 현행화
5. TQQQ시뮬레이션 / stitched RMSE 계산 위치를 앱에서 CLI 스크립트로 이동

## 7) 리스크(Risks)

- **기존 summary CSV 호환성**: 기존에 생성된 summary CSV에는 `stitched_rmse` 행이 없음
  - 완화: 앱에서 `stitched_rmse` 키가 없으면 "N/A" 표시 (graceful fallback)
- **WalkforwardSummaryDict 변경**: TypedDict에 키 추가 시 기존 `run_walkforward_validation()` 반환에도 포함해야 함
  - 완화: `NotRequired`로 선언하여 `run_walkforward_validation()`은 수정 불필요, 스크립트에서 삽입

## 8) 메모(Notes)

- `run_walkforward_validation()`의 반환 타입인 `WalkforwardSummaryDict`에 `stitched_rmse`를 `NotRequired`로 추가하여, 기존 함수 수정 없이 스크립트에서 삽입 가능
- 앱의 `_render_rmse_comparison()` 에서 `stitched_rmse` 키가 summary dict에 없는 경우(이전 버전 CSV) None으로 처리
- 이미지에서 확인한 수치: 정적 RMSE 1.0467%, 연속 워크포워드 RMSE 2.9258%, 월별 리셋 평균 RMSE 0.1201%
- 해석 텍스트는 하드코딩이 아닌 동적 생성 (`_render_rmse_interpretation()` 함수)으로 구현하여, 워크포워드 재실행 시 자동으로 갱신됨

### 진행 로그 (KST)

- 2026-02-14 20:30: 계획서 작성
- 2026-02-14 20:40: Phase 1 완료 (TypedDict + analysis_helpers + script + 테스트)
- 2026-02-14 20:50: Phase 2 완료 (앱 연산 제거 + 해석 함수 추가)
- 2026-02-14 21:00: Phase 3 완료 (README 현행화 + Black + 최종 검증)

---
