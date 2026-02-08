# Implementation Plan: 월별 데이터 조회 함수를 data_loader.py로 추출

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-08 21:30
**마지막 업데이트**: 2026-02-08 21:30
**관련 범위**: tqqq (data_loader, simulation, analysis_helpers), tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] `simulation.py`의 월별 데이터 조회 함수 6개를 `data_loader.py`로 추출하여 코드 중복 제거
- [ ] `analysis_helpers.py`의 중복 FFR 조회 함수 2개를 제거하고 `data_loader.py`에서 임포트
- [ ] 동작 변경 없음 (순수 리팩토링)

## 2) 비목표(Non-Goals)

- 함수 로직 변경 (시그니처, 반환값, 예외 동작 모두 동일 유지)
- `validate_ffr_coverage` 등 simulation.py 고유 함수의 이동
- data_loader.py의 기존 파일 I/O 함수 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

이전 작업(PLAN_aggregate_monthly_ffr_fallback)에서 `aggregate_monthly`의 FFR 매칭을 2개월 fallback으로 교체하면서, 순환 임포트 제약(`simulation.py` → `analysis_helpers.py` 기존 임포트)으로 FFR 조회 로직을 `analysis_helpers.py`에 별도 구현했다.

현재 중복 상태:

| 함수 | simulation.py | analysis_helpers.py |
|------|--------------|---------------------|
| FFR 딕셔너리 생성 | `_create_ffr_dict` (L458) | `_build_ffr_dict` (L261) |
| FFR 월별 조회 | `_lookup_ffr` (L476) | `_lookup_ffr_for_period` (L295) |

근본 원인인 제네릭 함수도 simulation.py에 있어 공유 불가:

| 제네릭 함수 | 위치 | 용도 |
|------------|------|------|
| `_create_monthly_data_dict` (L368) | simulation.py | FFR/Expense 딕셔너리 생성의 공통 로직 |
| `_lookup_monthly_data` (L407) | simulation.py | FFR/Expense 월별 조회의 공통 로직 |

해결: `data_loader.py`로 추출하면 순환 임포트 없이 양쪽에서 공유 가능.

의존성 방향 (변경 후):
```
constants.py ← data_loader.py ← simulation.py
                               ← analysis_helpers.py
```
순환 임포트 없음 확인: `data_loader.py`는 `constants.py`만 임포트.

### 이동 대상 함수 (6개)

| 현재 위치 (simulation.py) | 새 위치 (data_loader.py) | 접근 수준 변경 |
|--------------------------|--------------------------|-------------|
| `_create_monthly_data_dict` (L368) | `create_monthly_data_dict` | private → public |
| `_lookup_monthly_data` (L407) | `lookup_monthly_data` | private → public |
| `_create_ffr_dict` (L458) | `create_ffr_dict` | private → public |
| `_lookup_ffr` (L476) | `lookup_ffr` | private → public |
| `_create_expense_dict` (L495) | `create_expense_dict` | private → public |
| `_lookup_expense` (L513) | `lookup_expense` | private → public |

### 호출처 변경 영향

**simulation.py** (함수 호출 → 임포트로 교체):
- `_create_ffr_dict`: 6곳 (L321, L947, L1474, L1677, L1880, L2030)
- `_lookup_ffr`: 4곳 (L331, L698, L771, L2114)
- `_create_expense_dict`: 4곳 (L955, L1475, L1683, L1886)
- `_lookup_expense`: 2곳 (L701, L774)

**analysis_helpers.py** (중복 함수 제거 → 임포트로 교체):
- `_build_ffr_dict` → `create_ffr_dict` 임포트
- `_lookup_ffr_for_period` → `lookup_ffr` 임포트 (Period→date 변환 추가)

**test_tqqq_simulation.py** (임포트 경로 변경):
- `_create_ffr_dict`: 상단 임포트 + 18곳 호출
- `_lookup_ffr`: 상단 임포트 + 4곳 호출
- `_create_expense_dict`: 상단 임포트 + 8곳 호출
- 인라인 임포트 2곳 (L1268, L2396-2397, L2519-2520)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`: 모듈 구성, FFR 데이터 검증 규칙
- `src/qbt/utils/CLAUDE.md`: 유틸리티 설계 원칙 (참고)
- `tests/CLAUDE.md`: 테스트 작성/수정 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 6개 함수가 `data_loader.py`에 public으로 존재
- [ ] `simulation.py`에서 6개 private 함수 제거, `data_loader.py`에서 임포트로 교체
- [ ] `analysis_helpers.py`에서 `_build_ffr_dict` / `_lookup_ffr_for_period` 제거, `data_loader.py`에서 임포트로 교체
- [ ] 기존 테스트 임포트 경로 갱신 (simulation → data_loader)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (`src/qbt/tqqq/CLAUDE.md` data_loader 섹션)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/tqqq/data_loader.py`: 함수 6개 추가, import 추가
- `src/qbt/tqqq/simulation.py`: 함수 6개 정의 제거, import 추가, 호출부 `_` 접두사 제거
- `src/qbt/tqqq/analysis_helpers.py`: 중복 함수 2개 제거, import 경로 변경
- `tests/test_tqqq_simulation.py`: import 경로 변경 (simulation → data_loader)
- `src/qbt/tqqq/CLAUDE.md`: data_loader 모듈 설명 갱신

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 동작 변경 없음 (순수 리팩토링)

## 6) 단계별 계획(Phases)

### Phase 1 — data_loader.py에 함수 추가 + simulation.py 정리(그린 유지)

**작업 내용**:

- [ ] `data_loader.py`에 필요한 import 추가 (`date`, `MAX_FFR_MONTHS_DIFF`, `MAX_EXPENSE_MONTHS_DIFF`, `COL_EXPENSE_VALUE`)
- [ ] `data_loader.py`에 제네릭 함수 2개 추가 (simulation.py에서 복사, `_` 접두사 제거):
  - `create_monthly_data_dict(df, date_col, value_col, data_type) -> dict[str, float]`
  - `lookup_monthly_data(date_value, data_dict, max_months_diff, data_type) -> float`
- [ ] `data_loader.py`에 래퍼 함수 4개 추가 (simulation.py에서 복사, `_` 접두사 제거):
  - `create_ffr_dict(ffr_df) -> dict[str, float]`
  - `lookup_ffr(date_value, ffr_dict) -> float`
  - `create_expense_dict(expense_df) -> dict[str, float]`
  - `lookup_expense(date_value, expense_dict) -> float`
- [ ] `simulation.py`에서 6개 private 함수 정의 제거
- [ ] `simulation.py`에 `data_loader.py`에서 임포트 추가
- [ ] `simulation.py` 내 모든 호출부의 `_` 접두사 제거 (16곳)

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 2 — analysis_helpers.py 중복 제거 + 테스트 임포트 갱신(그린 유지)

**작업 내용**:

- [ ] `analysis_helpers.py`에서 `_build_ffr_dict` 함수 제거
- [ ] `analysis_helpers.py`에서 `_lookup_ffr_for_period` 함수 제거
- [ ] `analysis_helpers.py`에 `data_loader.py`에서 임포트 추가 (`create_ffr_dict`, `lookup_ffr`)
- [ ] `aggregate_monthly` 내 FFR 매칭 코드 갱신:
  - `_build_ffr_dict(ffr_df)` → `create_ffr_dict(ffr_df)`
  - `_lookup_ffr_for_period(period, ffr_dict)` → Period를 date로 변환 후 `lookup_ffr(date_value, ffr_dict)` 호출
- [ ] `tests/test_tqqq_simulation.py` 임포트 경로 변경:
  - 상단 임포트: `from qbt.tqqq.simulation import _create_ffr_dict, ...` → `from qbt.tqqq.data_loader import create_ffr_dict, ...`
  - 인라인 임포트 3곳 (L1268, L2396-2397, L2519-2520) 동일 변경
  - 테스트 코드 내 함수 호출부 `_` 접두사 제거

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/tqqq/CLAUDE.md` data_loader 섹션에 새 함수 설명 추가
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 월별 데이터 조회 함수를 data_loader로 추출하여 중복 제거
2. TQQQ시뮬레이션 / FFR·Expense 조회 함수를 data_loader.py로 통합
3. TQQQ시뮬레이션 / simulation·analysis_helpers 간 FFR 조회 로직 공유 모듈 추출
4. TQQQ시뮬레이션 / 순환 임포트 해소를 위한 월별 조회 함수 data_loader 이동
5. TQQQ시뮬레이션 / create_ffr_dict·lookup_ffr를 data_loader로 추출 (리팩토링)

## 7) 리스크(Risks)

- **변경 범위 넓음**: simulation.py 16곳 + test 30곳 이상의 호출부 수정. 기계적 치환이지만 누락 가능
  - 완화: PyRight strict 모드가 누락된 임포트/참조를 즉시 감지
- **테스트 임포트 누락**: 인라인 임포트 3곳이 grep에서 놓치기 쉬움
  - 완화: Phase별 validate_project.py 실행으로 즉시 발견

## 8) 메모(Notes)

- 이전 작업: PLAN_aggregate_monthly_ffr_fallback (이 리팩토링의 동기)
- data_loader.py 현재 역할: "TQQQ 도메인 전용 데이터 로딩 유틸리티" → 확장: "데이터 로딩 + 월별 데이터 조회"
- `_lookup_ffr_for_period`는 Period 객체를 받지만 `lookup_ffr`는 date 객체를 받음. 변환 코드 `date(period.year, period.month, 1)` 추가 필요

### 진행 로그 (KST)

- 2026-02-08 21:30: 계획서 Draft 작성
