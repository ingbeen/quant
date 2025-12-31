# Implementation Plan: Streamlit 일별 비교 대시보드 리팩토링 및 signed 오차 전환

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

**작성일**: 2025-12-31 23:34
**마지막 업데이트**: 2025-12-31 23:43
**관련 범위**: tqqq, scripts, tests
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] streamlit_app.py를 streamlit_daily_comparison.py로 파일명 변경하여 명확성 향상
- [ ] 차트 생성 함수를 비즈니스 로직 계층(src/qbt/tqqq/visualization.py)으로 분리
- [ ] 대시보드에서 abs 기반 오차 지표를 signed 기반으로 전환하여 방향성 파악 가능하도록 개선
- [ ] 분리된 차트 생성 함수에 대한 테스트 추가
- [ ] 모든 관련 문서(CLAUDE.md) 업데이트

## 2) 비목표(Non-Goals)

- constants.py에서 COL_CUMUL_MULTIPLE_LOG_DIFF_ABS 상수를 제거하지 않음 (둘 다 유지)
- streamlit_rate_spread_lab.py는 변경하지 않음
- 차트 시각화 로직 자체는 변경하지 않음 (abs → signed만 변경)
- 데이터 생성 로직(generate_tqqq_daily_comparison.py)은 변경하지 않음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제점 1: 파일명 불명확**
- `streamlit_app.py`라는 이름이 너무 일반적이어서 무엇을 하는 앱인지 명확하지 않음
- TQQQ 도메인에는 2개의 Streamlit 앱이 있어 명확한 구분 필요
  - 일별 비교 대시보드 (현재 streamlit_app.py)
  - 금리-오차 관계 분석 앱 (streamlit_rate_spread_lab.py)

**문제점 2: 계층 분리 미흡**
- 차트 생성 함수(`create_price_comparison_chart`, `create_daily_return_diff_histogram`, `create_cumulative_return_diff_chart`)가 CLI 계층(scripts/)에 위치
- 프로젝트 아키텍처 원칙에 따르면 비즈니스 로직은 src/qbt/에 위치해야 함
- 현재 상태에서는 차트 생성 함수를 다른 곳에서 재사용할 수 없음
- 테스트 작성도 불가능함 (CLI 계층은 테스트 대상이 아님)

**문제점 3: abs 기반 오차 표시의 한계**
- 현재 대시보드는 COL_CUMUL_MULTIPLE_LOG_DIFF_ABS만 표시
- abs는 오차의 크기만 보여주고 방향(시뮬이 실제보다 높은지/낮은지)을 알 수 없음
- signed를 사용하면 방향성까지 파악 가능하여 분석 품질 향상

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트) - 프로젝트 전반 규칙
- `src/qbt/tqqq/CLAUDE.md` - TQQQ 도메인 규칙
- `scripts/CLAUDE.md` - CLI 계층 규칙
- `tests/CLAUDE.md` - 테스트 작성 규칙
- `docs/CLAUDE.md` - 계획서 작성 및 운영 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 차트 생성 함수가 src/qbt/tqqq/visualization.py로 이동 완료
- [x] streamlit_app.py가 streamlit_daily_comparison.py로 파일명 변경 완료
- [x] 대시보드에서 abs 대신 signed 오차 지표 표시
- [x] tests/test_tqqq_visualization.py 추가 (차트 생성 함수 테스트)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=175)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] src/qbt/tqqq/CLAUDE.md 업데이트 (streamlit_daily_comparison.py 반영, signed 전환 명시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성**:
- `src/qbt/tqqq/visualization.py` - 차트 생성 함수 모듈 (비즈니스 로직)
- `tests/test_tqqq_visualization.py` - visualization 모듈 테스트

**파일명 변경**:
- `scripts/tqqq/streamlit_app.py` → `scripts/tqqq/streamlit_daily_comparison.py`

**내용 수정**:
- `scripts/tqqq/streamlit_daily_comparison.py` (변경 후):
  - visualization 모듈 임포트 추가
  - 차트 생성 함수 호출로 변경
  - COL_CUMUL_MULTIPLE_LOG_DIFF_ABS → COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED
  - docstring 및 주석 업데이트

**문서 업데이트**:
- `src/qbt/tqqq/CLAUDE.md`:
  - streamlit_app.py → streamlit_daily_comparison.py 반영
  - "abs 기반 오차 지표 사용" → "signed 기반 오차 지표 사용 (방향성 파악)"
  - visualization.py 모듈 설명 추가

### 데이터/결과 영향

- CSV 데이터 스키마 변경 없음 (COL_CUMUL_MULTIPLE_LOG_DIFF_ABS, COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED 둘 다 유지)
- 대시보드 표시 내용만 변경 (abs → signed)
- 기존 CSV 파일 재생성 불필요

## 6) 단계별 계획(Phases)

### Phase 1 — visualization.py 생성 및 테스트

**작업 내용**:

- [x] `src/qbt/tqqq/visualization.py` 생성
  - [x] `create_price_comparison_chart` 함수 이동 (streamlit_app.py에서)
  - [x] `create_daily_return_diff_histogram` 함수 이동
  - [x] `create_cumulative_return_diff_chart` 함수 이동 (signed 사용하도록 수정)
  - [x] 타입 힌트, docstring 완비
  - [x] 필요한 임포트 추가
- [x] `tests/test_tqqq_visualization.py` 생성
  - [x] 각 차트 생성 함수에 대한 기본 테스트 작성
  - [x] Given-When-Then 패턴 적용
  - [x] 반환 타입 검증 (plotly.graph_objects.Figure)
  - [x] 필수 trace 존재 확인
  - [x] 결측치 처리 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=175, failed=0, skipped=0)

---

### Phase 2 — streamlit_daily_comparison.py 리팩토링

**작업 내용**:

- [x] 파일명 변경: `scripts/tqqq/streamlit_app.py` → `scripts/tqqq/streamlit_daily_comparison.py`
- [x] `streamlit_daily_comparison.py` 수정
  - [x] visualization 모듈 임포트 추가
  - [x] 차트 생성 함수 호출로 변경 (로컬 함수 제거)
  - [x] COL_CUMUL_MULTIPLE_LOG_DIFF_ABS → COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED 변경
  - [x] 모듈 docstring 업데이트 (파일명 반영)
  - [x] 실행 명령어 주석 업데이트
  - [x] 차트 제목/레이블 업데이트 (abs → signed)
- [x] Git 상태 확인 (streamlit_app.py 삭제, streamlit_daily_comparison.py 추가)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=175, failed=0, skipped=0)
- [ ] 수동 테스트: `poetry run streamlit run scripts/tqqq/streamlit_daily_comparison.py` 실행하여 차트 정상 표시 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - [x] streamlit_app.py → streamlit_daily_comparison.py 반영 (모든 참조)
  - [x] "abs 기반 오차 지표 사용" → "signed 기반 오차 지표 사용 (방향성 파악)" 수정
  - [x] visualization.py 모듈 설명 추가 (섹션 5로 추가)
  - [x] 스크립트 실행 순서 설명 업데이트 (필요 없음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
  - [x] 모든 테스트 통과 확인 (175 passed, 0 failed, 0 skipped)
  - [ ] 대시보드 실행 및 signed 차트 정상 표시 확인 (수동 테스트, 사용자 확인 필요)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=175, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 일별 비교 대시보드 리팩토링 (계층 분리, signed 오차 전환)
2. TQQQ시뮬레이션 / 차트 생성 함수 비즈니스 로직 분리 및 테스트 추가
3. TQQQ시뮬레이션 / streamlit_daily_comparison 파일명 변경 및 signed 오차 표시
4. TQQQ시뮬레이션 / visualization 모듈 분리 및 대시보드 개선
5. TQQQ시뮬레이션 / 대시보드 리팩토링 (파일명, 계층, signed 전환, 테스트)

## 7) 리스크(Risks)

**리스크 1: 파일명 변경으로 인한 문서 참조 누락**
- 완화책: src/qbt/tqqq/CLAUDE.md를 검색하여 모든 streamlit_app.py 참조를 확인하고 업데이트
- 완화책: 변경 후 문서를 재검토하여 누락 확인

**리스크 2: 차트 생성 함수 이동 시 동작 변경 가능성**
- 완화책: 함수 이동 시 코드 수정 최소화 (임포트만 추가)
- 완화책: 수동 테스트로 대시보드 정상 동작 확인

**리스크 3: signed 전환으로 인한 시각화 이해도 저하 가능성**
- 완화책: 차트 제목과 레이블에 "signed (방향성)" 명시
- 완화책: CLAUDE.md에 abs vs signed 차이 설명 추가

## 8) 메모(Notes)

### 주요 결정 사항

- **차트 생성 함수 위치**: src/qbt/tqqq/visualization.py
  - 이유: Plotly 차트 생성은 비즈니스 로직이며, 재사용 및 테스트 가능해야 함
  - CLI 계층은 visualization 모듈을 호출하는 역할만 수행

- **COL_CUMUL_MULTIPLE_LOG_DIFF_ABS 유지**:
  - constants.py에서 abs와 signed 둘 다 유지
  - 다른 스크립트(validate_tqqq_simulation.py 등)에서 abs를 사용할 수 있음
  - 대시보드만 signed로 전환

- **파일명 변경 이유**:
  - streamlit_app.py → streamlit_daily_comparison.py
  - "일별 비교 대시보드"라는 목적을 명확히 표현
  - streamlit_rate_spread_lab.py와 명확히 구분

### 진행 로그 (KST)

- 2025-12-31 23:34: 계획서 작성 시작
- 2025-12-31 23:38: Phase 1 완료 (visualization.py 및 테스트 작성)
- 2025-12-31 23:40: Phase 2 완료 (streamlit_daily_comparison.py 리팩토링)
- 2025-12-31 23:43: 마지막 Phase 완료 (CLAUDE.md 업데이트, 최종 검증 통과)

---
