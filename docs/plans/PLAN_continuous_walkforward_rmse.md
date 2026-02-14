# Implementation Plan: 연속 워크포워드 RMSE 추가

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

**작성일**: 2026-02-14 19:00
**마지막 업데이트**: 2026-02-14 19:30
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

- [x] 목표 1: 워크포워드 결과를 **연속으로 붙인(stitched) 시뮬레이션** 기반 RMSE를 산출하여, 정적(전체기간 최적 a,b) RMSE와 **동일 정의로 비교** 가능하게 한다
- [x] 목표 2: Streamlit 워크포워드 검증 결과 섹션에 **연속 워크포워드 RMSE**를 표시하여, 기존 월별 리셋 기반 평균 RMSE와 함께 사용자가 비교 판단할 수 있게 한다

## 2) 비목표(Non-Goals)

- 워크포워드 CSV 컬럼 추가 (이미 `ffr_pct_test`, `spread_test` 존재)
- 정적 spread 시계열 CSV 생성 (이미 `tqqq_softplus_spread_series_static.csv` 생성됨)
- Spread 비교 섹션 UI (이미 `_render_spread_comparison_section()` 구현됨)
- 연속 RMSE의 CSV 저장이나 로그 출력 (Streamlit 표시만)
- 구간별(기간 분리) RMSE 산출

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 워크포워드 평균 RMSE(≈0.1201%)는 **월별 테스트 시 initial_price를 실제 월초 가격으로 리셋**하는 방식이라, 장기 누적 오차가 상쇄되어 값이 작게 나온다
- 정적 RMSE(≈1.0467%)는 **전체기간 연속 시뮬레이션** 기반이라 누적 드리프트가 반영된다
- 이 두 값은 **평가 방식(연속 vs 월별 리셋)이 달라 1:1 비교가 불가능**하다
- "워크포워드가 더 낫다"를 판단하려면, **동일한 연속 시뮬레이션 정의**로 산출한 RMSE가 필요하다

### 핵심 설계: "연속(stitched) 워크포워드" 시뮬레이션

- 워크포워드 테스트 시작 월부터 끝까지 전체 기간 사용
- 초기값: 첫 테스트 월의 실제 TQQQ 가격으로 시작
- 이후 월에서는 **이전 월 시뮬 결과(마지막 가격)를 다음 월의 initial_price로 사용** (리셋 없음)
- 각 월의 spread: 워크포워드로 산출된 `spread_test` (= softplus(a_best, b_best, ffr_test)) 사용
- RMSE 수식: 정적 RMSE와 완전 동일 (`_calculate_metrics_fast` 또는 `_calculate_cumul_multiple_log_diff`)
  - `M_actual(t) = actual_prices(t) / actual_prices(0)`
  - `M_simul(t) = simulated_prices(t) / simulated_prices(0)`
  - `log_diff_abs_pct = |ln(M_actual / M_simul)| * 100`
  - `RMSE = sqrt(mean(log_diff_abs_pct²))`, 단위: %

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `calculate_stitched_walkforward_rmse()` 함수가 `simulation.py`에 구현되고, 워크포워드 result_df와 실제 데이터로부터 연속 RMSE를 계산한다
- [x] Streamlit 워크포워드 결과 섹션에 "연속 워크포워드 RMSE"가 정적 RMSE와 나란히 표시된다
- [x] 연속 시뮬레이션의 RMSE가 정적 RMSE와 동일 수식/스케일로 계산됨이 테스트로 검증된다
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=265, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/simulation.py`: `calculate_stitched_walkforward_rmse()` 함수 추가
- `scripts/tqqq/app_rate_spread_lab.py`: 워크포워드 결과 섹션에 연속 RMSE 표시 추가
- `tests/test_tqqq_simulation.py`: 연속 RMSE 계산 테스트 추가

### 데이터/결과 영향

- 기존 CSV 출력 스키마 변경 없음
- 기존 결과에 영향 없음 (읽기 전용으로 활용)

## 6) 단계별 계획(Phases)

### Phase 0 — 연속 RMSE 계산 함수의 인터페이스 및 핵심 테스트 작성(레드)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py`에 `calculate_stitched_walkforward_rmse()` 함수 시그니처 정의
  - 입력: `result_df` (워크포워드 결과 DataFrame), `underlying_df` (기초 자산), `actual_df` (실제 TQQQ), `ffr_df`, `expense_df`, `leverage`
  - 반환: `float` (연속 RMSE %)
  - 로직 개요:
    1. 워크포워드 result_df에서 `test_month`, `spread_test` 추출
    2. 첫 테스트 월부터 마지막 테스트 월까지의 실제 데이터/기초자산 데이터 필터링
    3. 첫 테스트 월의 실제 TQQQ 가격을 initial_price로 설정
    4. spread_test를 월별 funding_spread dict로 구성하여 전체 기간 1회 simulate() 호출
    5. 전체 연속 시뮬레이션 가격과 실제 가격으로 `_calculate_metrics_fast()` 호출
    6. RMSE 반환
- [x] `tests/test_tqqq_simulation.py`에 테스트 클래스 `TestCalculateStitchedWalkforwardRmse` 작성
  - 정상 케이스: 간단한 2~3개월 워크포워드 result_df로 연속 RMSE 계산 검증
  - 경계 케이스: result_df가 비어있을 때 ValueError
  - 경계 케이스: 필수 컬럼 누락 시 ValueError
  - 정합성 검증: 워크포워드 1개월만 있을 때, 월별 리셋 RMSE와 연속 RMSE가 동일해야 함

**Validation**:

- [x] `poetry run python validate_project.py` (passed=265, failed=0, skipped=0)

---

### Phase 1 — 연속 RMSE 계산 함수 구현(그린 유지)

**작업 내용**:

- [x] `calculate_stitched_walkforward_rmse()` 구현 (Phase 0에서 함께 완성)
  - spread_map dict를 FundingSpreadSpec으로 전달하여 전체 기간 1회 simulate() 호출
  - 최종 연속 가격 배열과 실제 가격 배열로 `_calculate_metrics_fast()` 호출
  - FFR 누락 월 처리: 기존 규칙(최대 2개월 fallback) 그대로 적용
- [x] Phase 0의 모든 테스트 통과 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=265, failed=0, skipped=0)

---

### Phase 2 — Streamlit UI에 연속 RMSE 표시(그린 유지)

**작업 내용**:

- [x] `scripts/tqqq/app_rate_spread_lab.py`에 `_calculate_stitched_rmse()` 캐시 함수 추가
  - QQQ, TQQQ, FFR, Expense 데이터를 로드하여 연속 RMSE 계산
  - `@st.cache_data`로 1회만 계산
  - 오류 시 None 반환
- [x] `_render_rmse_comparison()` 함수 추가
  - 정적 RMSE, 연속 워크포워드 RMSE, 월별 리셋 평균 RMSE를 3칼럼으로 나란히 표시
  - 각 지표의 의미와 해석 방법을 VERBATIM 텍스트로 제공
- [x] `_display_walkforward_result()`에서 `_render_rmse_comparison()` 호출 추가

**Validation**:

- [x] `poetry run python validate_project.py` (passed=265, failed=0, skipped=0)

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=265, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 연속 워크포워드 RMSE 추가로 정적 RMSE와 동일 기준 비교 가능하게 함
2. TQQQ시뮬레이션 / stitched 워크포워드 RMSE 산출 함수 구현 및 Streamlit 표시
3. TQQQ시뮬레이션 / 워크포워드 RMSE 정합화 - 월별 리셋 기반 vs 연속 기반 비교 지원
4. TQQQ시뮬레이션 / 연속(stitched) 워크포워드 시뮬레이션 RMSE 계산 및 UI 반영
5. TQQQ시뮬레이션 / 정적-워크포워드 RMSE 비교를 위한 연속 시뮬레이션 RMSE 추가

## 7) 리스크(Risks)

- **성능**: 연속 RMSE 계산 시 Streamlit 앱 로딩에서 `simulate()`를 호출하므로 초기 로딩 시간 증가 가능
  - 완화: `@st.cache_data`로 캐싱하여 1회만 계산
  - 구현 최적화: 월별 호출 대신 spread_map dict로 전체 기간 1회 simulate() 호출
- **데이터 의존성**: 연속 RMSE 계산에 기초자산(QQQ), 실제 TQQQ, FFR, Expense 데이터가 모두 필요
  - 완화: 데이터 로드 실패 시 None 반환하고 "N/A" 표시

## 8) 메모(Notes)

- 사용자 확인 완료 사항:
  - 워크포워드 CSV 컬럼 추가: 이미 구현됨 (추가 불필요)
  - 평가 구간: 전체 테스트 기간 (워크포워드 첫 테스트 월 ~ 마지막 테스트 월)
  - 워크포워드 spread 정의: `spread_test` (= softplus(a_best, b_best, ffr_test)) 유지
  - 결과 표시: Streamlit만
- RMSE 수식: `_calculate_metrics_fast()`와 동일한 누적배수 로그차이 RMSE (단위: %)
- 구현 최적화: 각 월별 simulate() 호출 대신, 월별 spread를 dict로 구성하여 전체 기간 1회 simulate() 호출로 최적화

### 진행 로그 (KST)

- 2026-02-14 19:00: 계획서 초안 작성
- 2026-02-14 19:10: Phase 0+1 완료 (함수 구현 + 테스트 4개 통과)
- 2026-02-14 19:20: Phase 2 완료 (Streamlit UI 추가)
- 2026-02-14 19:30: Phase 3 완료 (Black 포맷 + 최종 검증 통과)

---
