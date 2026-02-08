# Implementation Plan: aggregate_monthly FFR 매칭 로직 2개월 fallback 적용

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-08 21:00
**마지막 업데이트**: 2026-02-08 21:15
**관련 범위**: tqqq, tests
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

- [x] `aggregate_monthly`의 FFR 매칭 로직을 pandas left join에서 딕셔너리 기반 2개월 fallback + fail-fast 방식으로 교체
- [x] `simulation.py`의 `_lookup_monthly_data`와 동일한 FFR 데이터 무결성 기준 적용
- [x] 스크립트 결과(CSV 출력)가 기존과 동일하게 유지됨을 보장

## 2) 비목표(Non-Goals)

- `simulation.py`의 기존 `_lookup_monthly_data` / `_create_monthly_data_dict` 함수를 공유 모듈로 추출하는 대규모 리팩토링 (순환 임포트 문제로 별도 작업 필요)
- `aggregate_monthly`의 FFR 외 다른 기능 변경
- Streamlit 앱이나 CLI 스크립트 코드 변경 (aggregate_monthly 시그니처 불변 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`aggregate_monthly`(`analysis_helpers.py`)와 `simulation.py`에서 FFR 데이터를 서로 다른 방식으로 처리한다:

| 항목 | `simulation.py` | `aggregate_monthly` |
|------|-----------------|---------------------|
| FFR 조회 방식 | 딕셔너리 + 2개월 fallback | pandas left join |
| 누락 월 처리 | 최대 2개월 이전 값 사용 | NaN으로 방치 |
| 갭 초과 시 | `ValueError` (fail-fast) | 경고 로그만 |

동일 프로젝트 내에서 FFR 데이터의 신뢰성 기준이 불일치하면 혼란을 초래한다.
`aggregate_monthly`도 `MAX_FFR_MONTHS_DIFF = 2` 규제를 적용해야 한다.

**순환 임포트 제약**: `simulation.py` → `analysis_helpers.py` 임포트가 이미 존재하므로, `analysis_helpers.py` → `simulation.py` 역방향 임포트 불가. 따라서 `analysis_helpers.py` 내에 FFR lookup 로직을 자체 구현한다.

**결과 불변 보장**: 현재 FFR 데이터(`storage/etc/federal_funds_rate_monthly.csv`)는 1999-01 ~ 2025-12 연속 데이터로 갭이 없다. 비교 데이터 기간도 이 범위 내에 포함되므로, fallback 로직이 적용되어도 직접 매칭이 성공하여 결과가 동일하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`: FFR 데이터 검증 규칙 (`MAX_FFR_MONTHS_DIFF = 2`)
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 경계 조건, 결정적 테스트)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `aggregate_monthly` FFR 매칭이 2개월 fallback + fail-fast로 변경됨
- [x] 기존 테스트 전체 통과 (결과 불변 확인)
- [x] FFR fallback 동작 테스트 추가 (1개월/2개월 fallback 성공, 3개월 초과 시 ValueError)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=261, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/analysis_helpers.py`: aggregate_monthly FFR 매칭 로직 변경 + 헬퍼 함수 2개 추가
- `tests/test_tqqq_analysis_helpers.py`: FFR fallback 동작 테스트 추가

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 실제 FFR 데이터에 갭이 없으므로 CSV 결과 동일

## 6) 단계별 계획(Phases)

### Phase 0 — FFR fallback 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `test_tqqq_analysis_helpers.py`에 `TestAggregateMonthly` 클래스에 FFR fallback 테스트 추가:
  - `test_ffr_fallback_within_1_month`: 1개월 갭일 때 이전 월 FFR 값으로 fallback 성공
  - `test_ffr_fallback_within_2_months`: 2개월 갭일 때도 fallback 성공
  - `test_ffr_gap_exceeds_max_raises_error`: 3개월 갭일 때 ValueError

**Validation**:

- [x] `poetry run python validate_project.py` (passed=258, failed=3, skipped=0) — 레드 정상

---

### Phase 1 — aggregate_monthly FFR 매칭 로직 구현(그린 유지)

**작업 내용**:

- [x] `analysis_helpers.py`에 `COL_FFR_DATE`, `MAX_FFR_MONTHS_DIFF` import 추가 (constants.py에서)
- [x] `analysis_helpers.py`에 `_build_ffr_dict(ffr_df)` 헬퍼 함수 추가
- [x] `analysis_helpers.py`에 `_lookup_ffr_for_period(period, ffr_dict)` 헬퍼 함수 추가
- [x] `aggregate_monthly` 함수의 FFR 매칭 섹션 변경:
  - 기존: `pd.PeriodIndex` + `merge(left join)` + 경고 로그
  - 변경: `_build_ffr_dict` + 각 월 `_lookup_ffr_for_period` 반복 조회
  - FFR 커버리지 검증(경고 로그) 제거 (fail-fast로 대체됨)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=261, failed=0, skipped=0)

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=261, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / aggregate_monthly FFR 매칭을 2개월 fallback + fail-fast로 교체
2. TQQQ시뮬레이션 / FFR 누락 월 처리 일관성 확보 (left join → fallback 조회)
3. TQQQ시뮬레이션 / aggregate_monthly FFR 데이터 무결성 규제 적용
4. TQQQ시뮬레이션 / analysis_helpers FFR 매칭 로직 simulation.py 기준으로 통일
5. TQQQ시뮬레이션 / aggregate_monthly FFR 갭 검증 추가 (MAX_FFR_MONTHS_DIFF=2)

## 7) 리스크(Risks)

- **코드 중복**: `analysis_helpers.py`의 `_build_ffr_dict` / `_lookup_ffr_for_period`가 `simulation.py`의 `_create_ffr_dict` / `_lookup_ffr`와 유사한 로직을 가짐
  - 완화: 순환 임포트 제약으로 현 시점에서 공유 불가. 향후 별도 리팩토링(공유 모듈 추출)으로 해결 가능
- **결과 변경 가능성**: 현재 FFR 데이터에 갭이 없어 결과 불변이지만, 만약 갭이 있는 데이터가 투입되면 기존 NaN 대신 ValueError 발생
  - 완화: 이것이 의도된 동작(fail-fast). 잘못된 분석 결과를 조용히 생성하는 것보다 나음

## 8) 메모(Notes)

- 순환 임포트 구조: `simulation.py` → `analysis_helpers.py` (기존), 역방향 불가
- FFR 데이터 현황: 1999-01 ~ 2025-12 연속(갭 없음), 총 324행
- `aggregate_monthly` 호출처: `generate_rate_spread_lab.py`, `streamlit_rate_spread_lab.py` — 시그니처 불변이므로 변경 불필요

### 진행 로그 (KST)

- 2026-02-08 21:00: 계획서 Draft 작성
- 2026-02-08 21:05: Phase 0 완료 (테스트 3개 추가, 레드 확인)
- 2026-02-08 21:10: Phase 1 완료 (구현, 전체 검증 통과 261 passed)
- 2026-02-08 21:15: Phase 2 완료 (black 포맷, 최종 검증 통과)
