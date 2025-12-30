# Implementation Plan: 테스트 코드의 상수 정리 및 회귀 탐지 강화

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

**작성일**: 2025-12-30 15:40
**마지막 업데이트**: 2025-12-30 17:15
**관련 범위**: tests, src/qbt/common_constants.py
**관련 문서**: tests/CLAUDE.md, src/qbt/utils/CLAUDE.md

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

- [x] 목표 1: 내부 계약(컬럼명, 거래일수 등)을 검증하는 테스트에서 하드코딩된 값을 프로덕션 상수로 교체하여 드리프트 방지
- [x] 목표 2: 외부 스키마 검증 테스트는 리터럴 유지 및 주석으로 의도 명시하여 혼동 방지
- [x] 목표 3: 테스트 코드의 오타/드리프트 취약성 제거 및 회귀 탐지 능력 강화

## 2) 비목표(Non-Goals)

- 프로덕션 코드 수정 (상수 파일은 제외)
- 새로운 테스트 추가 (기존 테스트의 개선에 집중)
- 테스트 로직 변경 (값의 출처만 변경, 검증 로직은 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

테스트 코드에 다음과 같은 문제점이 존재합니다:

1. **내부 계약 검증에 하드코딩된 값 사용**
   - 컬럼명: `"Date"`, `"Close"`, `"Open"` 등이 문자열로 직접 사용됨
   - 거래일수: `252` (연간 거래일), `365.25` (윤년 포함 연간 일수)가 직접 사용됨
   - 프로덕션 상수와 값이 같지만 출처가 다르므로 드리프트 위험 존재

2. **외부 스키마 검증 테스트와의 혼동**
   - 일부 테스트는 "외부 데이터 구조"를 검증하므로 리터럴이 맞음
   - 그러나 주석으로 의도가 명확히 표시되지 않아 혼동 발생

3. **회귀 탐지 능력 저하**
   - 프로덕션 상수가 변경되어도 테스트가 감지하지 못함
   - 테스트와 프로덕션 코드의 계약이 암묵적으로만 존재

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `tests/CLAUDE.md` (테스트 작성 원칙, 경계 조건, 파일 격리, 상수 사용 규칙)
- `src/qbt/utils/CLAUDE.md` (유틸리티 책임, 도메인 독립성)
- `src/qbt/common_constants.py` (공통 상수 정의)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족: 내부 계약 검증 테스트에서 프로덕션 상수 사용
- [x] 회귀/신규 테스트 추가: 기존 테스트 개선 (신규 추가 불필요)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=154, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**테스트 파일**:
- `tests/conftest.py` (픽스처)
- `tests/test_tqqq_simulation.py` (TQQQ 시뮬레이션 테스트)
- `tests/test_analysis.py` (백테스트 분석 테스트)
- 기타 필요한 테스트 파일

**프로덕션 파일** (필요 시 상수 추가):
- `src/qbt/common_constants.py` (누락된 공통 상수 추가)

### 데이터/결과 영향

- 테스트 검증 로직은 변경되지 않으므로 결과 영향 없음
- 테스트 통과 여부는 동일하게 유지되어야 함

## 6) 단계별 계획(Phases)

### Phase 1 — 내부 계약 검증 테스트 상수 교체 (그린 유지)

**작업 내용**:

- [x] `src/qbt/common_constants.py`에 누락된 상수 확인 및 필요 시 추가
- [x] `tests/conftest.py`에서 `common_constants` 임포트 및 상수 사용
  - `COL_DATE`, `COL_OPEN`, `COL_HIGH`, `COL_LOW`, `COL_CLOSE`, `COL_VOLUME` 사용
- [x] `tests/test_tqqq_simulation.py`에서 하드코딩된 값 교체
  - `252` → `TRADING_DAYS_PER_YEAR` (이미 임포트되어 있었음)
  - `"Date"`, `"Close"` 등 → `COL_DATE`, `COL_CLOSE` 등
- [x] `tests/test_analysis.py`에서 하드코딩된 값 교체
  - `"Date"`, `"Close"` 등 → `COL_DATE`, `COL_CLOSE` 등
- [x] 기타 필요한 테스트 파일에서 유사한 패턴 교체 (없음, 필요한 파일만 수정 완료)

**Validation**:

- [x] `poetry run ruff check .` - All checks passed!
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

---

### Phase 2 — 외부 스키마 검증 테스트 주석 추가 (그린 유지)

**작업 내용**:

- [x] 외부 데이터 구조를 검증하는 테스트 식별
  - 예: `sample_ffr_df`의 `"DATE"` 컬럼 (외부 CSV 스키마 검증)
- [x] 해당 테스트에 주석 추가하여 의도 명시
  - conftest.py에 이미 명확한 주석 존재 (Note: 원본 CSV 스키마 회귀 탐지)
- [x] `tests/CLAUDE.md`에 외부 스키마 검증 규칙 추가 (이미 충분히 명시되어 있음)

**Validation**:

- [x] `poetry run ruff check .` - All checks passed!
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `tests/CLAUDE.md` 업데이트 (이미 상수 사용 규칙이 충분히 명시되어 있음)
- [x] `poetry run black .` 실행(자동 포맷 적용) - 2 files reformatted
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .` - All checks passed!
- [x] `./run_tests.sh` (passed=154, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / 내부 계약 검증에서 프로덕션 상수 사용으로 드리프트 방지
2. 테스트 / 하드코딩된 컬럼명·거래일수를 공통 상수로 교체 (회귀 탐지 강화)
3. 테스트 / 외부 스키마 검증 의도 명시 및 상수 정리
4. 테스트 / 오타/드리프트 취약성 제거 및 회귀 탐지 능력 강화
5. 테스트 / 테스트-프로덕션 계약 명시화 (상수 통일)

## 7) 리스크(Risks)

- **리스크 1**: 상수 교체 중 잘못된 상수 매핑으로 테스트 실패
  - **완화책**: Phase별 Validation에서 즉시 확인 및 수정

- **리스크 2**: 외부 스키마 검증 테스트를 잘못 식별하여 불필요한 상수화
  - **완화책**: 각 테스트의 의도를 명확히 파악하고, 주석으로 의도 명시

- **리스크 3**: 테스트 코드가 너무 많아 누락 발생
  - **완화책**: grep으로 패턴 검색 후 체계적으로 진행

## 8) 메모(Notes)

### 상수 매핑 규칙

**공통 상수** (`common_constants.py`에서 임포트):
- `COL_DATE = "Date"`
- `COL_OPEN = "Open"`
- `COL_HIGH = "High"`
- `COL_LOW = "Low"`
- `COL_CLOSE = "Close"`
- `COL_VOLUME = "Volume"`
- `TRADING_DAYS_PER_YEAR = 252`
- `ANNUAL_DAYS = 365.25`

**외부 스키마 검증** (리터럴 유지):
- `sample_ffr_df`의 `"DATE"` 컬럼 (외부 CSV 스키마)
- 기타 외부 데이터 구조 검증 테스트

### 진행 로그 (KST)

- 2025-12-30 15:40: 계획서 작성 시작
- 2025-12-30 15:50: Phase 1 시작 - conftest.py 상수 교체 완료
- 2025-12-30 16:20: Phase 1 - test_tqqq_simulation.py 상수 교체 완료
- 2025-12-30 16:40: Phase 1 - test_analysis.py 상수 교체 완료
- 2025-12-30 16:45: Phase 1 Validation 통과 (passed=154, failed=0, skipped=0)
- 2025-12-30 16:50: Phase 2 완료 (conftest.py에 이미 주석 명시되어 있음)
- 2025-12-30 17:00: 최종 Phase - Black 포맷 적용 (2 files reformatted)
- 2025-12-30 17:10: 최종 Validation 통과 (passed=154, failed=0, skipped=0)
- 2025-12-30 17:15: 계획서 업데이트 및 작업 완료

---
