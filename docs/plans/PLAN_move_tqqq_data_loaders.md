# Implementation Plan: TQQQ 전용 데이터 로더 함수 이동

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done
**작성일**: 2025-12-26 14:45
**마지막 업데이트**: 2025-12-26 16:30
**관련 범위**: utils, tqqq, scripts/tqqq, tests
**관련 문서**: src/qbt/utils/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] `load_ffr_data` 함수를 `utils/data_loader.py`에서 `tqqq/data_loader.py`로 이동
- [x] `load_comparison_data` 함수를 `utils/data_loader.py`에서 `tqqq/data_loader.py`로 이동
- [x] 모든 임포트 경로를 새 위치로 수정 (scripts/tqqq, tests)
- [x] 테스트 코드를 `test_tqqq_data_loader.py`로 이동 및 수정
- [x] utils 패키지의 도메인 독립성 강화

## 2) 비목표(Non-Goals)

- 함수의 내부 로직 변경 (단순 이동만)
- 데이터 검증 로직 개선
- 새로운 데이터 로더 추가
- 기존 `load_stock_data` 함수 이동 (여러 도메인에서 사용 중)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제점**:
- `utils/data_loader.py`의 `load_ffr_data`, `load_comparison_data` 두 함수는 TQQQ 도메인에서만 사용됨
- utils 패키지는 "도메인 로직과 독립적인 기술적 기능"만 담당해야 하는데, 이 함수들은 TQQQ 전용
- `tqqq.constants`를 임포트하여 순환 임포트 위험 존재
- utils의 역할이 불명확해지고 도메인 경계가 흐려짐

**필요성**:
- utils 패키지의 도메인 독립성 원칙 준수 (utils/CLAUDE.md)
- 도메인별 모듈 독립성 유지 (루트 CLAUDE.md)
- 순환 임포트 방지 및 명확한 의존성 방향 확립

**현재 사용처 분석**:
- `load_ffr_data`:
  - scripts/tqqq/generate_synthetic_tqqq.py
  - scripts/tqqq/generate_tqqq_daily_comparison.py
  - scripts/tqqq/validate_tqqq_simulation.py
  - tests/test_data_loader.py (2개 테스트)
- `load_comparison_data`:
  - scripts/tqqq/streamlit_app.py
  - tests/test_data_loader.py (2개 테스트)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.
> (규칙을 요약/나열하지 말고 "문서 목록"만 둡니다.)

- [x] `CLAUDE.md` (루트)
- [x] `src/qbt/utils/CLAUDE.md`
- [x] `src/qbt/tqqq/CLAUDE.md`
- [x] `tests/CLAUDE.md`

**핵심 규칙 준수 사항**:
- utils는 도메인 독립적 기술 기능만 제공 (utils/CLAUDE.md)
- 도메인별 모듈 독립성 유지 (루트 CLAUDE.md)
- FFR 데이터는 DATE 컬럼이 "yyyy-mm" 문자열 (tqqq/CLAUDE.md, tests/CLAUDE.md)
- 테스트 파일 격리 및 Given-When-Then 패턴 (tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 두 함수가 `src/qbt/tqqq/data_loader.py`로 이동
- [x] scripts/tqqq/ 내 모든 스크립트의 임포트 경로 수정
- [x] `tests/test_tqqq_data_loader.py` 생성 및 테스트 이동
- [x] `utils/data_loader.py`에서 tqqq 관련 임포트 제거
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=111, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (tqqq/CLAUDE.md, utils/CLAUDE.md)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**생성**:
- `src/qbt/tqqq/data_loader.py` (새 파일, 76줄 예상)
- `tests/test_tqqq_data_loader.py` (새 파일, 약 120줄 예상)

**수정**:
- `src/qbt/utils/data_loader.py` (두 함수 + 관련 임포트 제거, 약 55줄 감소)
- `scripts/tqqq/generate_synthetic_tqqq.py` (임포트 1줄 수정)
- `scripts/tqqq/generate_tqqq_daily_comparison.py` (임포트 1줄 수정)
- `scripts/tqqq/validate_tqqq_simulation.py` (임포트 1줄 수정)
- `scripts/tqqq/streamlit_app.py` (임포트 1줄 수정)
- `tests/test_data_loader.py` (4개 테스트 메서드 제거, 약 80줄 감소)
- `src/qbt/tqqq/CLAUDE.md` (새 모듈 설명 추가)
- `src/qbt/utils/CLAUDE.md` (데이터 로딩 섹션 수정)

### 데이터/결과 영향

- **없음**: 함수 로직은 동일하게 유지, 위치만 변경
- CSV 스키마 변경 없음
- 실행 결과 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 새 파일 생성 및 함수 이동

**작업 내용**:

- [x] `src/qbt/tqqq/data_loader.py` 파일 생성
- [x] 파일 상단 docstring 작성 (모듈 목적: TQQQ 도메인 전용 데이터 로딩)
- [x] `load_ffr_data` 함수 복사
  - [x] 필요한 임포트: `Path`, `pandas`, `common_constants.COL_FFR_*`, `tqqq.constants.*`, `utils.get_logger`
  - [x] 함수 시그니처 및 docstring 유지
  - [x] 로직 동일하게 유지
- [x] `load_comparison_data` 함수 복사
  - [x] 필요한 임포트: 동일
  - [x] 함수 시그니처 및 docstring 유지
  - [x] 로직 동일하게 유지
- [x] 모듈 레벨 로거 생성 (`logger = get_logger(__name__)`)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### Phase 2 — 스크립트 임포트 경로 수정

**작업 내용**:

- [x] `scripts/tqqq/generate_synthetic_tqqq.py` 임포트 수정
  - 변경 전: `from qbt.utils.data_loader import load_ffr_data, load_stock_data`
  - 변경 후: `from qbt.tqqq.data_loader import load_ffr_data` + `from qbt.utils.data_loader import load_stock_data`
- [x] `scripts/tqqq/generate_tqqq_daily_comparison.py` 임포트 수정 (동일 패턴)
- [x] `scripts/tqqq/validate_tqqq_simulation.py` 임포트 수정 (동일 패턴)
- [x] `scripts/tqqq/streamlit_app.py` 임포트 수정
  - 변경 전: `from qbt.utils.data_loader import load_comparison_data`
  - 변경 후: `from qbt.tqqq.data_loader import load_comparison_data`

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### Phase 3 — 테스트 코드 이동 및 수정

**작업 내용**:

- [x] `tests/test_tqqq_data_loader.py` 파일 생성
- [x] 테스트 클래스 생성: `TestLoadFfrData`, `TestLoadComparisonData`
- [x] `tests/test_data_loader.py`에서 다음 4개 테스트 메서드 추출 및 이동:
  - [x] `test_normal_load` (FFR)
  - [x] `test_file_not_found` (FFR)
  - [x] `test_normal_load` (Comparison)
  - [x] `test_missing_columns` (Comparison)
- [x] 이동한 테스트의 임포트 수정:
  - 변경 전: `from qbt.utils.data_loader import load_ffr_data, load_comparison_data`
  - 변경 후: `from qbt.tqqq.data_loader import load_ffr_data, load_comparison_data`
- [x] 필요한 픽스처 임포트 (`sample_ffr_df` 등)
- [x] FFR 데이터 형식 검증 (DATE 컬럼이 "yyyy-mm" 문자열임을 확인)
- [x] Given-When-Then 주석 유지
- [x] `tests/test_data_loader.py`에서 이동된 4개 테스트 메서드 제거

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)
- [x] 테스트 개수 확인: 이동 전후 총 passed 수 동일 (111개)

---

### Phase 4 — utils/data_loader.py 정리

**작업 내용**:

- [x] `src/qbt/utils/data_loader.py`에서 `load_ffr_data` 함수 제거
- [x] `src/qbt/utils/data_loader.py`에서 `load_comparison_data` 함수 제거
- [x] 불필요한 임포트 제거:
  - [x] `from qbt.tqqq.constants import COL_FFR, COL_FFR_DATE, COL_FFR_VALUE_RAW, COMPARISON_COLUMNS` 제거
  - [x] `DISPLAY_DATE` 임포트도 제거 (미사용)
- [x] 파일 상단 docstring 업데이트 (공통 CSV 로딩 강조, TQQQ 참조 추가)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - [x] "모듈 구성" 섹션에 `data_loader.py` 추가 (섹션 1)
  - [x] 함수 설명: `load_ffr_data`, `load_comparison_data`
  - [x] 데이터 형식 명시: FFR DATE는 "yyyy-mm" 문자열
  - [x] 이후 섹션 번호 조정 (constants.py → 섹션 2, simulation.py → 섹션 3 등)
- [x] `src/qbt/utils/CLAUDE.md` 업데이트
  - [x] "데이터 로딩 통합" 섹션 수정
  - [x] 공통 로더만 제공함을 명시 (현재: load_stock_data만)
  - [x] "도메인 전용 로더" 하위 섹션 추가 (TQQQ 참조)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 최종 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 리팩토링 / TQQQ 전용 데이터 로더를 utils에서 tqqq 도메인으로 이동 (도메인 독립성 강화)
2. 리팩토링 / load_ffr_data, load_comparison_data를 tqqq/data_loader.py로 이동 및 문서 업데이트
3. 리팩토링 / utils 패키지 정리 - TQQQ 전용 함수를 tqqq 도메인으로 분리 (순환 임포트 방지)
4. TQQQ시뮬레이션 / 도메인 전용 데이터 로더 분리 (utils → tqqq/data_loader.py)
5. 리팩토링 / 도메인별 데이터 로더 분리 및 utils 역할 명확화 (도메인 경계 강화)

## 7) 리스크(Risks)

**1. 임포트 경로 누락 위험**
- 위험: 일부 스크립트에서 임포트 수정을 누락하여 런타임 에러 발생
- 완화책:
  - Phase 2에서 Ruff 검증으로 미사용 임포트 감지
  - 각 Phase에서 ./run_tests.sh 실행으로 즉시 검출
  - 전체 코드베이스에서 `from qbt.utils.data_loader import load_ffr_data` 검색으로 이중 확인

**2. 테스트 이동 중 누락 위험**
- 위험: 일부 테스트 메서드를 누락하거나 잘못 이동
- 완화책:
  - Phase 3에서 이동할 4개 테스트 메서드를 명시적으로 나열
  - ./run_tests.sh의 passed/failed/skipped 수를 Phase별로 기록하여 테스트 손실 검출
  - 이동 전후 테스트 개수 비교

**3. FFR 데이터 형식 불일치**
- 위험: 테스트에서 FFR DATE 컬럼을 date 객체로 잘못 작성
- 완화책:
  - tests/CLAUDE.md 규칙 준수: DATE는 "yyyy-mm" 문자열
  - Phase 3에서 명시적으로 형식 검증
  - conftest.py의 sample_ffr_df 픽스처 활용

**4. 문서 업데이트 누락**
- 위험: CLAUDE.md 업데이트 누락으로 향후 혼란 발생
- 완화책:
  - 마지막 Phase에서 문서 업데이트를 명시적으로 체크
  - DoD에 "필요한 문서 업데이트" 항목 포함

## 8) 메모(Notes)

### 설계 결정 사항

**새 파일 위치**:
- 경로: `src/qbt/tqqq/data_loader.py`
- 이유:
  - tqqq 도메인 전용 기능임을 명확히 표현
  - utils와 동일한 파일명으로 역할 일관성 유지
  - 향후 TQQQ 관련 데이터 로딩 함수 추가 시 자연스럽게 확장 가능

**테스트 파일 위치**:
- 경로: `tests/test_tqqq_data_loader.py`
- 이유:
  - 기존 test_data_loader.py와 명확히 구분
  - tqqq 도메인 테스트임을 파일명으로 표현

**임포트 경로 패턴**:
- `load_stock_data`는 utils에 유지 (여러 도메인에서 사용)
- `load_ffr_data`, `load_comparison_data`는 tqqq로 이동
- 스크립트에서는 두 곳에서 임포트 필요:
  ```python
  from qbt.utils.data_loader import load_stock_data
  from qbt.tqqq.data_loader import load_ffr_data
  ```

### 참고 사항

- FFR 데이터 형식: DATE 컬럼은 `datetime.date` 객체가 아닌 `"yyyy-mm"` 문자열 (tqqq/CLAUDE.md, tests/CLAUDE.md)
- COMPARISON_COLUMNS 상수는 tqqq.constants에 정의되어 있음
- utils/data_loader.py는 약 160줄 → 105줄로 감소 예상

### 진행 로그 (KST)

- 2025-12-26 14:45: 계획서 초안 작성 (관련 규칙 문서 전체 숙지 완료)
- 2025-12-26 15:00: Phase 1 완료 - 새 파일 생성 및 함수 이동 (Ruff 통과, 테스트 111개 통과)
- 2025-12-26 15:15: Phase 2 완료 - 스크립트 임포트 경로 수정 (4개 파일 수정)
- 2025-12-26 15:30: Phase 3 완료 - 테스트 코드 이동 (4개 테스트 이동, 테스트 개수 유지)
- 2025-12-26 15:45: Phase 4 완료 - utils/data_loader.py 정리 (함수 및 임포트 제거)
- 2025-12-26 16:00: 마지막 Phase 완료 - 문서 업데이트 및 최종 검증
- 2025-12-26 16:30: 전체 작업 완료 - 계획서 체크박스 최신화 (상태: Done)
