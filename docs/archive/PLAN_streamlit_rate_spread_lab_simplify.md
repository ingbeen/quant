# Implementation Plan: Streamlit Rate Spread Lab 화면 단순화 + CSV 자동 저장

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

**작성일**: 2026-01-05 21:30
**마지막 업데이트**: 2026-01-05 23:00
**관련 범위**: tqqq, scripts, utils
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, src/qbt/utils/CLAUDE.md

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

- [x] Streamlit 앱 UI 단순화: 핵심(Level) 기본 노출, 고급(Delta/교차검증) Expander로 숨김
- [x] 해석 가이드 상시 제공: 용어/부호 해석/예시 문장 포함, 초보자도 차트 의미 파악 가능
- [x] CSV 자동 저장(2종): 앱 실행 시 `storage/results/`에 월별 피처 + 요약 통계 저장
- [x] meta.json 실행 이력 관리: 신규 CSV 타입 추가 및 메타데이터 자동 기록

## 2) 비목표(Non-Goals)

- 기존 차트 생성 로직 변경 (visualization.py는 필요 시만 최소 수정)
- 기존 analysis_helpers.py 계산 로직 변경
- 다른 Streamlit 앱(streamlit_daily_comparison.py) 수정
- 기존 CSV(tqqq_daily_comparison.csv, tqqq_validation.csv) 형식 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `scripts/tqqq/streamlit_rate_spread_lab.py`가 연구용 기능/용어 중심이라 초보자가 해석하기 어려움
- 시각화/탭이 많아 "무엇을 봐야 하는지"가 불명확함
- 분석 결과가 UI에만 표시되고 CSV로 저장되지 않아 AI가 해석/모델링에 활용하기 어려움
- 핵심: Level(금리 수준 → 월말 누적 오차 e_m)만 명확히 보이고, 고급 분석은 선택적으로 열어볼 수 있어야 함

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기본 화면: Level 핵심 + 최근 12개월 요약 테이블 + 해석 가이드만 노출
- [x] 고급 분석(Delta/교차검증): st.expander로 기본 숨김
- [x] 앱 실행 시 결과 CSV 2종(월별 피처 + 요약 통계)이 `storage/results/`에 자동 저장
- [x] meta.json에 신규 CSV 타입 실행 이력 기록
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=196, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/tqqq/streamlit_rate_spread_lab.py` (UI 재구성 + CSV 저장 트리거)
- `src/qbt/tqqq/constants.py` (결과 CSV 경로 상수 추가 + __all__ 반영)
- `src/qbt/utils/meta_manager.py` (VALID_CSV_TYPES에 신규 타입 추가)
- `src/qbt/tqqq/analysis_helpers.py` (필요 시 요약 통계/피처 생성 helper 추가)
- `src/qbt/tqqq/visualization.py` (필요 시 Level 차트 단순화/신규 helper 추가)

### 데이터/결과 영향

- 신규 CSV 2종 생성: `tqqq_rate_spread_lab_monthly.csv`, `tqqq_rate_spread_lab_summary.csv`
- 기존 CSV 형식은 변경 없음
- meta.json에 신규 타입 `"tqqq_rate_spread_lab"` 추가

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 추가 및 meta_manager 업데이트

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 결과 CSV 경로 상수 2개 추가
  - `TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH = RESULTS_DIR / "tqqq_rate_spread_lab_monthly.csv"`
  - `TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH = RESULTS_DIR / "tqqq_rate_spread_lab_summary.csv"`
- [x] `__all__`에 위 상수 추가
- [x] `src/qbt/utils/meta_manager.py`의 `VALID_CSV_TYPES`에 `"tqqq_rate_spread_lab"` 추가

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0)

---

### Phase 2 — CSV 저장 헬퍼 함수 추가 (analysis_helpers.py)

**작업 내용**:

- [x] `src/qbt/tqqq/analysis_helpers.py`에 `save_monthly_features()` 함수 추가
  - 입력: monthly_df (month, rate_pct, dr_m, dr_lag1, dr_lag2, e_m, de_m, sum_daily_m)
  - 출력: CSV 저장 (정렬: month 오름차순, dtype/NaN 처리 일관성)
- [x] `save_summary_statistics()` 함수 추가
  - Level 요약(rate_pct vs e_m): n, corr, slope, intercept
  - Delta 요약(lag 0/1/2): dr_m.shift(lag) vs de_m, dr_m.shift(lag) vs sum_daily_m
  - 교차검증 요약: max_abs_diff, mean_abs_diff, std_diff
- [x] `__all__`에 신규 함수 추가

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0)

---

### Phase 3 — Streamlit UI 재구성 (핵심/고급 분리)

**작업 내용**:

- [x] Level 탭: y축 선택 라디오 제거, y=e_m 고정
- [x] 최근 12개월 요약 테이블 추가 (month, rate_pct, e_m, de_m, sum_daily_m)
- [x] 해석 가이드 문구 추가 (용어 별칭, 부호 해석, 예시 문장 2~3개, 상관≠인과 주의)
- [x] Delta 분석: st.expander로 기본 숨김 (y축은 de_m 기본, lag 0/1/2 선택 유지)
- [x] 교차검증: st.expander로 기본 숨김

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0)

---

### Phase 4 — CSV 자동 저장 로직 추가 (Streamlit 앱)

**작업 내용**:

- [x] `prepare_monthly_data()` 호출 후 dr_lag1, dr_lag2 파생 컬럼 추가
- [x] `save_monthly_features()` 호출하여 월별 피처 CSV 저장
- [x] `save_summary_statistics()` 호출하여 요약 통계 CSV 저장
- [x] `save_metadata()` 호출하여 meta.json에 실행 이력 기록
  - csv_type: `"tqqq_rate_spread_lab"`
  - metadata: 입력 파일 경로/mtime, 출력 파일 경로 2개, 분석기간(month min/max), 월 개수

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (문서 수정 불필요 확인)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Rate Spread Lab 화면 단순화 + AI용 CSV 자동 저장
2. TQQQ시뮬레이션 / 금리-오차 앱 초보자 해석 가이드 + 피처/통계 CSV 저장
3. TQQQ시뮬레이션 / Streamlit 앱 UI 개선(핵심/고급 분리) + 분석 결과 CSV 생성
4. TQQQ시뮬레이션 / 연구용 앱 사용성 개선 + 모델링용 데이터 자동 추출
5. TQQQ시뮬레이션 / Rate Spread Lab 해석 가이드 강화 + meta.json 이력 관리

## 7) 리스크(Risks)

- Streamlit expander 동작이 기대와 다를 수 있음 → Context7 문서 참고하여 구현
- CSV 컬럼 수가 너무 많아질 수 있음 → 최소 필수 컬럼만 포함
- 요약 통계 계산 시 NaN/결측 처리 필요 → dropna() + 샘플 수 기록

## 8) 메모(Notes)

- Streamlit expander 사용법: `with st.expander("제목", expanded=False):`
- 해석 가이드 예시 문장:
  - "금리가 높을수록 e_m이 +로 커지면 → 고금리 구간에서 시뮬 과대 → 비용(조달비용) 가정이 낮았을 가능성"
  - "반대로 -로 커지면 → 비용 가정이 높았을 가능성"
- 최근 12개월 요약 테이블: `monthly_df.tail(12)`로 추출

### 진행 로그 (KST)

- 2026-01-05 21:30: 계획서 작성 완료

---
