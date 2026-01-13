# Implementation Plan: Rate Spread Lab UI 개선 (CSV 재생성 방지 및 한글화)

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

**작성일**: 2026-01-13 12:00
**마지막 업데이트**: 2026-01-13 17:10
**관련 범위**: tqqq, scripts
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md

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

- [ ] Lag 선택 시 CSV 재생성 방지 (앱 초기 로딩 시 1회만 저장)
- [ ] 사용자 화면의 모든 영문 표현을 한글로 변경 (기술 용어는 "한글 (영문)" 형식)
- [ ] 사용자 경험 개선 (명확한 레이블, 설명, 메트릭 표시)

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 (analysis_helpers.py, visualization.py 등)
- CSV 저장 로직 제거 (결과는 계속 저장되어야 함)
- 데이터 처리 알고리즘 변경
- 차트 생성 로직 변경 (visualization.py는 수정하지 않음)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1: CSV 재생성 동작**
- 현재 `prepare_monthly_data()` 함수가 실행될 때마다 CSV가 저장됨 (286~289줄)
- Streamlit 캐시 TTL(600초) 만료 시 함수가 재실행되어 CSV 재생성
- 사용자가 Lag 선택을 변경할 때 캐시 만료와 겹치면 불필요한 CSV 저장 발생
- 로그: `save_monthly_features` 및 `save_summary_statistics` 호출 로그가 Lag 선택 시 출력됨

**문제 2: 사용자 화면 가독성**
- 기술 변수명(e_m, de_m, sum_daily_m 등)이 그대로 노출되어 비전문가가 이해하기 어려움
- 영문 레이블/설명이 많아 한국어 사용자 경험 저하
- 메트릭 레이블이 간결하지만 의미가 불명확함

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `scripts/CLAUDE.md` (CLI 스크립트 계층)
- `src/qbt/tqqq/CLAUDE.md` (TQQQ 도메인)
- `tests/CLAUDE.md` (테스트 작성 시)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] CSV 저장이 앱 초기 로딩 시 1회만 실행됨 (Lag 선택 시 재생성 안 됨) ✅
- [x] 모든 사용자 화면 텍스트가 "한글 (영문)" 형식으로 변경됨 ✅
- [x] 메트릭 레이블이 명확한 한글로 표시됨 ✅
- [x] Lag 선택 UI에 명확한 설명이 포함됨 ✅
- [x] `poetry run python validate_project.py` 통과 (passed=196, failed=0, skipped=0) ✅
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용) ✅
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영) ✅

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/tqqq/streamlit_rate_spread_lab.py` (주요 변경)
  - CSV 저장 로직 위치 조정
  - 모든 사용자 화면 텍스트 한글화

### 데이터/결과 영향

- CSV 파일 내용/형식 변경 없음
- 화면 표시 텍스트만 변경 (비즈니스 로직 동일)
- 기존 결과와의 비교 불필요

## 6) 단계별 계획(Phases)

### Phase 1 — CSV 재생성 방지 (그린 유지)

**작업 내용**:

- [x] CSV 저장 로직을 Streamlit session_state로 1회만 실행하도록 변경
  - 현재 문제: 284~316줄의 CSV 저장 로직이 위젯 상호작용 시마다 재실행됨
  - 원인: Streamlit은 위젯 변경 시 전체 스크립트를 재실행하며, 캐시 외부 코드는 매번 실행됨
  - 해결: `st.session_state`를 사용하여 CSV 저장을 앱 세션당 1회만 실행
- [x] CSV 저장 로직 수정 (284~316줄)
  ```python
  # CSV 저장 (세션당 1회만)
  if "csv_saved" not in st.session_state:
      try:
          save_monthly_features(monthly_df, TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH)
          save_summary_statistics(monthly_df, TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH)
          metadata = {...}
          save_metadata("tqqq_rate_spread_lab", metadata)
          st.session_state.csv_saved = True
          st.success("✅ 결과 CSV 자동 저장 완료")
      except Exception as e:
          st.warning(f"⚠️ CSV 저장 실패 (계속 진행):\n\n{str(e)}")
  ```
- [x] CSV 저장 로직의 위치는 유지 (276줄 직후, 월별 집계 성공 직후)
- [x] 에러 핸들링: CSV 저장 실패 시에도 앱 계속 진행

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0) ✅
- [x] Lag 선택 시 CSV 저장 로그가 출력되지 않는지 확인 (session_state로 차단됨) ✅
- [x] 앱 재시작 시 CSV가 1회만 저장되는지 확인 ✅
- [x] 위젯(Lag selectbox 등) 여러 번 변경 시 CSV 저장이 1회만 실행되는지 확인 ✅

---

### Phase 2 — 사용자 화면 한글화 (그린 유지)

**작업 내용**:

- [x] 페이지 타이틀 및 설명 한글화
  - "spread 조정 전략" → "스프레드 조정 전략 (Spread Adjustment Strategy)"
  - "Delta 분석, 교차검증" → "델타 분석 (Delta Analysis), 교차검증 (Cross Validation)"
- [x] 데이터 로딩 섹션 메시지 한글화
  - "데이터 로딩" → "데이터 로딩 (Data Loading)"
- [x] 월별 데이터 준비 섹션 한글화
  - "월별 데이터 준비" → "월별 데이터 준비 (Monthly Data Preparation)"
- [x] 메트릭 레이블 한글화
  - "분석 기간" → "분석 기간 (Period)"
  - "금리 범위" → "금리 범위 (Rate Range, %)"
  - "월말 오차 범위" → "월말 오차 범위 (End-of-Month Error, %)"
- [x] Level 탭 한글화
  - 용어 설명 영문 추가:
    - "금리 수준 (rate_pct)" → "금리 수준 (Rate Level, rate_pct)"
    - "월말 누적 오차 (e_m)" → "월말 누적 오차 (End-of-Month Error, e_m)"
  - "연방기금금리(FFR)" → "연방기금금리 (Federal Funds Rate, FFR)"
  - "시뮬" → "시뮬레이션"
- [x] Delta 탭 한글화
  - 제목: "📊 고급 분석: 델타 (Delta - 금리 변화 vs 오차 변화)"
  - Lag 선택 레이블: "시차 (Lag, 개월):"
  - Lag 설명에 영문 추가: "시차 효과 (Lag Effect)"
  - st.info 메시지 한글화:
    - "샘플 수" → "샘플 수 (Sample Size)"
    - "상관 해석 주의점" → "상관 해석 주의점 (Correlation Interpretation)"
    - "Lag 효과" → "시차 효과 (Lag Effect)"
- [x] 교차검증 탭 한글화
  - 제목: "✅ 고급 분석: 교차검증 (Cross Validation - de_m vs sum_daily_m)"
  - 함수 내부 제목: "교차검증 (Cross Validation): de_m vs sum_daily_m"
  - 설명에 영문 추가:
    - "`de_m` (월간 변화, Difference)"
    - "`sum_daily_m` (일일 증분 월합, Sum of Daily)"
    - "차이 원인 (Difference Causes)"
  - 메트릭 레이블 한글화:
    - "최대 절댓값 차이 (Max Abs Diff)"
    - "평균 절댓값 차이 (Mean Abs Diff)"
    - "표준편차 (Std Dev)"
  - "차이가 큰 상위 5개월" → "차이가 큰 상위 5개월 (Top 5 Months with Largest Diff)"
- [x] 최근 12개월 요약 테이블 한글화
  - "최근 12개월 요약" → "최근 12개월 요약 (Recent 12 Months Summary)"

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0) ✅
- [x] 화면의 모든 영문이 "한글 (영문)" 형식으로 표시되는지 확인 ✅ (코드 레벨 검증 완료)
- [x] Lag 선택 시 명확한 설명이 표시되는지 확인 ✅ (코드 레벨 검증 완료)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `scripts/tqqq/streamlit_rate_spread_lab.py` docstring 업데이트 (변경 사항 반영) ✅
- [x] `poetry run black .` 실행(자동 포맷 적용) ✅
- [x] Streamlit 앱 전체 흐름 최종 검증 ✅ (코드 레벨 검증 완료)
  - 앱 시작 → CSV 1회 저장 확인 ✅
  - Lag 선택 변경 → CSV 재생성 안 됨 확인 ✅
  - 모든 화면 텍스트 한글화 확인 ✅
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료 ✅
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정 ✅

**Validation**:

- [x] `poetry run python validate_project.py` (passed=196, failed=0, skipped=0) ✅

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Rate Spread Lab UI 개선 (CSV 재생성 방지 및 한글화)
2. TQQQ시뮬레이션 / Streamlit 앱 사용자 경험 개선 (불필요한 CSV 저장 방지)
3. TQQQ시뮬레이션 / Rate Spread Lab 화면 가독성 향상 (한글화 및 명확한 레이블)
4. TQQQ시뮬레이션 / CSV 저장 로직 최적화 및 UI 한글화
5. TQQQ시뮬레이션 / Lag 선택 시 CSV 재생성 방지 + 전체 화면 한글화

## 7) 리스크(Risks)

- **리스크 1**: CSV 저장 로직 분리 시 함수 호출 순서 오류
  - **완화책**: 코드 리뷰 시 호출 순서 명확히 확인, 에러 핸들링 추가
- **리스크 2**: 한글화 시 일부 영문 누락 가능성
  - **완화책**: 전체 화면을 처음부터 끝까지 실행하며 육안 검증
- **리스크 3**: Streamlit 캐시 동작 변경으로 예상치 못한 부작용
  - **완화책**: 캐시 로직은 변경하지 않고, CSV 저장 위치만 변경

## 8) 메모(Notes)

### 핵심 결정 사항

- CSV 저장은 앱 기능에 필수이므로 제거하지 않고 위치만 조정
- 비즈니스 로직(analysis_helpers.py, visualization.py)은 수정하지 않음
- 화면 텍스트만 변경하므로 테스트 추가 불필요 (기존 테스트 통과 확인만)

### 진행 로그 (KST)

- 2026-01-13 12:00: 계획서 작성 완료
- 2026-01-13 12:10: Phase 1 해결 방안 수정 (session_state 사용으로 변경)
- 2026-01-13 12:15: Phase 1 코드 수정 완료 및 검증 통과 (passed=196, failed=0, skipped=0)
- 2026-01-13 12:20: Phase 1 수동 검증 완료 (사용자 확인: CSV 1회만 저장)
- 2026-01-13 12:25: Phase 2 코드 수정 완료 및 검증 통과 (passed=196, failed=0, skipped=0)
- 2026-01-13 17:00: 마지막 Phase 완료 (docstring 업데이트, black 포맷팅)
- 2026-01-13 17:05: 최종 품질 검증 통과 (passed=196, failed=0, skipped=0)
- 2026-01-13 17:10: DoD 및 계획서 체크리스트 최종 업데이트 완료

---
