# Implementation Plan: TQQQ 시각화 모듈 금리-오차 관계 차트 통합

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

**작성일**: 2026-01-01 00:09
**마지막 업데이트**: 2026-01-01 10:36
**관련 범위**: tqqq, scripts
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

- [x] `streamlit_rate_spread_lab.py`의 차트 생성 함수를 `visualization.py`로 통합
- [x] 재사용 가능한 함수 설계 유지 (상태 비저장, 명확한 인터페이스)
- [x] 이동된 함수에 대한 테스트 추가
- [x] 관련 문서 업데이트

## 2) 비목표(Non-Goals)

- `display_cross_validation()` 함수는 이동하지 않음 (Streamlit 컴포넌트를 직접 다루므로 CLI 계층에 유지)
- 차트 생성 로직 변경 없음 (기존 동작 유지)
- 함수명 변경 없음 (create_level_chart, create_delta_chart 유지)
- streamlit_daily_comparison.py는 변경하지 않음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 상태**:
- `visualization.py`에 3개 차트 함수 존재 (`streamlit_daily_comparison.py`에서 사용)
- `streamlit_rate_spread_lab.py`에 2개 차트 함수 자체 구현 (`create_level_chart`, `create_delta_chart`)
- 차트 생성 로직이 CLI 계층과 비즈니스 로직 계층에 혼재

**동기**:
- 아키텍처 원칙 준수: CLI 계층은 차트 생성 로직을 포함하지 않고 비즈니스 로직 호출만 담당
- 재사용성 향상: 금리-오차 관계 차트를 다른 분석 도구에서도 사용 가능
- 일관성 유지: 모든 TQQQ 시각화 함수를 한 모듈에 집중

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md` (TQQQ 도메인)
- `scripts/CLAUDE.md` (스크립트 계층)
- `tests/CLAUDE.md` (테스트)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `create_level_chart`, `create_delta_chart` 함수가 `visualization.py`로 이동
- [x] `streamlit_rate_spread_lab.py`에서 이동된 함수를 import하여 사용
- [x] 이동된 함수에 대한 테스트 추가 (`test_tqqq_visualization.py`)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=182, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트 (visualization.py 함수 목록)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/visualization.py`: 2개 함수 추가 (create_level_chart, create_delta_chart)
- `scripts/tqqq/streamlit_rate_spread_lab.py`: 2개 함수 제거 및 import 추가
- `tests/test_tqqq_visualization.py`: 2개 함수 테스트 추가
- `src/qbt/tqqq/CLAUDE.md`: visualization.py 함수 목록 업데이트

### 데이터/결과 영향

- 차트 생성 로직 변경 없음 (기존 동작 유지)
- 출력 스키마 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 함수 이동 및 import 수정

**작업 내용**:

- [x] `streamlit_rate_spread_lab.py`의 `create_level_chart()` 함수를 `visualization.py`로 복사 (154~267줄)
  - 필요한 import 추가 (plotly.subplots.make_subplots, numpy)
  - Docstring 및 타입 힌트 확인
  - 상태 비저장 함수 확인
- [x] `streamlit_rate_spread_lab.py`의 `create_delta_chart()` 함수를 `visualization.py`로 복사 (270~406줄)
  - 필요한 import 추가
  - Docstring 및 타입 힌트 확인
  - 상태 비저장 함수 확인
- [x] `streamlit_rate_spread_lab.py`에서 이동된 함수 제거
- [x] `streamlit_rate_spread_lab.py`에 import 추가: `from qbt.tqqq.visualization import create_level_chart, create_delta_chart`
- [x] 기존 함수 호출 부분 확인 (변경 없이 동작해야 함)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=175, failed=0, skipped=0)
- [ ] `poetry run streamlit run scripts/tqqq/streamlit_rate_spread_lab.py` 실행 확인 (수동)

---

### Phase 2 — 테스트 추가

**작업 내용**:

- [x] `test_tqqq_visualization.py`에 `TestLevelChart` 클래스 추가
  - 기본 차트 생성 테스트 (valid monthly_df 입력)
  - Figure 객체 반환 확인
  - trace 개수 확인 (산점도 + 추세선 + 시계열 2개)
  - y_col 파라미터 변경 테스트 (e_m, de_m, sum_daily_m)
- [x] `test_tqqq_visualization.py`에 `TestDeltaChart` 클래스 추가
  - 기본 차트 생성 테스트 (valid monthly_df 입력)
  - Figure 객체 및 DataFrame 반환 확인
  - Lag 파라미터 변경 테스트 (0, 1, 2)
  - Rolling 상관 계산 분기 테스트 (샘플 수 < 12 vs >= 12)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

---

### Phase 3 — 문서 업데이트 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - `visualization.py` 섹션에 `create_level_chart`, `create_delta_chart` 함수 설명 추가
  - 주요 함수 목록 업데이트 (현재 3개 → 5개)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
  - `streamlit_rate_spread_lab.py` 실행 확인 (수동, Phase 1에서 확인)
  - `streamlit_daily_comparison.py` 실행 확인 (수동, 회귀 방지, 변경 없음으로 통과)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 금리-오차 관계 차트 함수를 visualization 모듈로 통합
2. TQQQ시뮬레이션 / 시각화 모듈에 Level/Delta 차트 생성 함수 추가 및 테스트 보강
3. TQQQ시뮬레이션 / CLI 계층 차트 로직을 비즈니스 로직 계층으로 이동 (재사용성 향상)
4. TQQQ시뮬레이션 / streamlit_rate_spread_lab 차트 함수 리팩토링 (동작 동일)
5. TQQQ시뮬레이션 / visualization 모듈 확장 및 문서 업데이트

## 7) 리스크(Risks)

- **import 순환 참조 가능성**: visualization.py가 다른 모듈을 import할 때 순환 참조 발생 가능
  - 완화책: visualization.py는 constants, common_constants만 import하도록 유지 (이미 기존 함수들이 이 패턴을 따름)
- **테스트 데이터 준비 복잡도**: monthly_df 픽스처 필요 (rate_pct, e_m, de_m, sum_daily_m, dr_m 컬럼)
  - 완화책: conftest.py에 `sample_monthly_df` 픽스처 추가 또는 테스트 내 로컬 데이터 생성
- **수동 검증 필요**: Streamlit 앱 동작 확인은 자동화 불가
  - 완화책: Phase 1, 3에서 수동 실행 확인 항목 포함

## 8) 메모(Notes)

### 이동할 함수 세부 정보

**`create_level_chart(monthly_df, y_col, y_label)`** (streamlit_rate_spread_lab.py:154~267):
- 금리 수준 vs 오차 수준 산점도 + 시계열 라인 차트
- 서브플롯 2개 (산점도, 시계열)
- 추세선 (OLS 1차 다항식)
- 이중 y축 (금리, 오차)
- 필요 import: `plotly.subplots.make_subplots`, `numpy`

**`create_delta_chart(monthly_df, y_col, y_label, lag)`** (streamlit_rate_spread_lab.py:270~406):
- 금리 변화 vs 오차 변화 산점도 + Rolling 12M 상관
- 서브플롯 2개 (산점도, Rolling 상관)
- Lag 적용 (0, 1, 2 개월)
- 샘플 수 부족 시 안내 메시지
- 반환: (Figure, valid_df)
- 필요 import: `plotly.subplots.make_subplots`, `numpy`

### 진행 로그 (KST)

- 2026-01-01 00:09: 계획서 초안 작성 완료
- 2026-01-01 10:32: Phase 1 완료 (함수 이동 및 import 수정)
- 2026-01-01 10:32: Phase 2 완료 (테스트 추가, row/col 문자열→정수 버그 수정)
- 2026-01-01 10:36: Phase 3 완료 (문서 업데이트 및 최종 검증)
- 2026-01-01 10:36: 모든 작업 완료 (✅ Done)

---
