# Implementation Plan: Rate Spread Lab CSV 생성 CLI 분리

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: Draft

---

**이 영역은 삭제/수정 금지**

**상태 옵션**: Draft / In Progress / Done

**Done 처리 규칙**:

- Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- 스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-02 21:00
**마지막 업데이트**: 2026-02-02 21:00
**관련 범위**: tqqq, scripts, docs
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> **이 영역은 삭제/수정 금지**
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] 목표 1: `streamlit_rate_spread_lab.py`에서 CSV 3개 저장 로직을 독립 CLI 스크립트 `scripts/tqqq/generate_rate_spread_lab.py`로 분리
- [ ] 목표 2: Streamlit 앱에서 CSV 저장/메타데이터 관련 코드를 완전히 제거 (시각화 전용으로 정리)
- [ ] 목표 3: `meta.json`의 기존 `tqqq_rate_spread_lab` 이력 제거 (새 CLI 실행 시 재생성됨)
- [ ] 목표 4: 관련 문서 업데이트 (`scripts/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `README.md`)

## 2) 비목표(Non-Goals)

- Streamlit 앱의 시각화 기능 변경 (UI 렌더링 로직은 그대로 유지)
- `analysis_helpers.py`의 비즈니스 로직 함수 수정 (기존 함수를 CLI에서 호출만 함)
- 새로운 테스트 추가 (비즈니스 로직 테스트는 `test_tqqq_analysis_helpers.py`에 이미 존재)
- `meta_manager.py`의 `VALID_CSV_TYPES` 수정 (`tqqq_rate_spread_lab`은 이미 등록됨)
- CSV 출력 형식/스키마 변경 (동일한 출력 보장)
- `_prepare_monthly_data()` 로직을 `analysis_helpers.py`로 이동 (과도한 리팩토링)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `streamlit_rate_spread_lab.py`가 시각화 앱이면서 동시에 CSV 3개를 부수 효과로 생성하고 있다.
- `_save_guard()` + `_save_outputs_once()` 패턴은 `st.cache_resource` 기반으로 서버 런 동안 1회만 저장하는 방식인데, 이는 Streamlit의 관심사(시각화)와 데이터 파이프라인(CSV 생성)을 혼합한다.
- 프로젝트의 다른 도메인(`generate_tqqq_daily_comparison.py`, `run_softplus_tuning.py` 등)은 이미 CLI 스크립트로 CSV를 생성하고, Streamlit 앱은 결과 CSV만 로드하는 패턴을 따른다.
- 이 변경으로 기존 패턴과의 일관성을 확보한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`: 계층 분리 원칙, 상수 관리, CLI 예외 처리 패턴
- `scripts/CLAUDE.md`: CLI 스크립트 표준 구조, 메타데이터 관리, 예외 처리 데코레이터
- `src/qbt/tqqq/CLAUDE.md`: TQQQ 도메인 모듈 구성, CSV 파일 형식

## 4) 완료 조건(Definition of Done)

- [ ] 새 CLI 스크립트 `scripts/tqqq/generate_rate_spread_lab.py`가 3개 CSV를 정상 생성
- [ ] 새 CLI 스크립트가 `meta.json`에 `tqqq_rate_spread_lab` 메타데이터를 정상 저장
- [ ] Streamlit 앱에서 CSV 저장 관련 코드가 완전히 제거됨
- [ ] Streamlit 앱의 시각화 기능이 정상 동작 유지
- [ ] `meta.json`에서 기존 `tqqq_rate_spread_lab` 이력이 제거됨
- [ ] 문서 업데이트 완료 (`scripts/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `README.md`)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `scripts/tqqq/generate_rate_spread_lab.py` | **신규 생성** | CSV 3개 생성 CLI 스크립트 |
| `scripts/tqqq/streamlit_rate_spread_lab.py` | **수정** | CSV 저장 로직/import 제거 |
| `storage/results/meta.json` | **수정** | `tqqq_rate_spread_lab` 키 제거 |
| `scripts/CLAUDE.md` | **수정** | 메타데이터 지원 타입 추가, 스크립트 목록 추가 |
| `src/qbt/tqqq/CLAUDE.md` | **수정** | CLI 스크립트 섹션 추가, Streamlit 설명 수정 |
| `README.md` | **수정** | 워크플로우에 새 CLI 스크립트 추가 |

### 데이터/결과 영향

- CSV 출력 스키마: 변경 없음 (동일한 3개 CSV를 동일한 형식으로 생성)
- `meta.json`: 기존 `tqqq_rate_spread_lab` 이력 제거 후, 새 CLI 실행 시 재생성
- Streamlit 앱: CSV 파일을 생성하지 않으나, 시각화에 필요한 데이터 빌드 로직은 유지

## 6) 단계별 계획(Phases)

### Phase 1 -- 새 CLI 스크립트 생성

**작업 내용**:

- [ ] `scripts/tqqq/generate_rate_spread_lab.py` 파일 생성

**CLI 스크립트 구조** (기존 `generate_tqqq_daily_comparison.py` 패턴 준수):

```
@cli_exception_handler
def main() -> int:
    1. 데이터 로드: load_comparison_data(), load_ffr_data()
    2. 일일 증분 signed 로그오차 계산: calculate_daily_signed_log_diff()
    3. 월별 집계: aggregate_monthly()
    4. sum_daily_m 계산 (Streamlit의 _prepare_monthly_data() 행 204-213 로직 이식)
    5. lag 컬럼 추가: add_rate_change_lags()
    6. CSV 3개 저장:
       - save_monthly_features(monthly_df, MONTHLY_PATH)
       - save_summary_statistics(monthly_df, SUMMARY_PATH)
       - build_model_dataset() + save_model_csv() (try-except ValueError)
    7. 메타데이터 저장: save_metadata("tqqq_rate_spread_lab", metadata)
    8. return 0
```

**핵심 주의사항**:

- `_prepare_monthly_data()` 로직을 직접 구현 (Streamlit private 함수이므로 호출 불가)
- `build_model_dataset()` 실패 시: WARNING 로그 후 monthly/summary CSV는 보존, model CSV만 스킵
- 스크립트 전체는 성공(return 0)으로 처리 (monthly/summary는 저장 완료)

**메타데이터 구조** (기존 Streamlit이 저장하던 것과 동일):

```python
metadata = {
    "input_files": {
        "daily_comparison": str(TQQQ_DAILY_COMPARISON_PATH),
        "ffr_data": str(FFR_DATA_PATH),
    },
    "output_files": {
        "monthly_csv": str(TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH),
        "summary_csv": str(TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH),
        # "model_csv" 조건부 추가 (성공 시)
    },
    "analysis_period": {
        "month_min": str(monthly_df[COL_MONTH].min()),
        "month_max": str(monthly_df[COL_MONTH].max()),
        "total_months": len(monthly_df),
    },
}
```

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)
- [ ] `poetry run python scripts/tqqq/generate_rate_spread_lab.py` 수동 실행 후 CSV 3개 생성 확인

---

### Phase 2 -- Streamlit 앱 수정 + meta.json 정리

**Streamlit 앱에서 제거할 코드**:

- [ ] `import threading` (행 32)
- [ ] import에서 제거: `build_model_dataset`, `save_model_csv`, `save_monthly_features`, `save_summary_statistics` (행 43-47)
- [ ] import에서 제거: `TQQQ_RATE_SPREAD_LAB_MODEL_PATH`, `TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH`, `TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH` (행 67-69)
- [ ] import에서 제거: `DEFAULT_ROLLING_WINDOW` (행 61, `_save_outputs_once` 내에서만 사용)
- [ ] import에서 제거: `from qbt.utils.meta_manager import save_metadata` (행 80)
- [ ] 상수 제거: `KEY_META_TYPE_RATE_SPREAD_LAB` (행 92)
- [ ] 함수 제거: `_save_guard()` 전체 (행 119-131)
- [ ] 함수 제거: `_save_outputs_once()` 전체 (행 415-489)
- [ ] `main()` 함수 내 `_save_outputs_once(monthly_df)` 호출 제거 (행 829)
- [ ] 모듈 Docstring에서 CSV 저장 관련 설명 수정 (행 14-17)

**Streamlit 앱에서 유지할 코드** (시각화에 필요):

- `_prepare_monthly_data()` 함수
- `build_artifacts()` 함수
- `add_rate_change_lags` import 및 호출
- `calculate_daily_signed_log_diff`, `aggregate_monthly` import
- `DEFAULT_MIN_MONTHS_FOR_ANALYSIS` import
- `TQQQ_DAILY_COMPARISON_PATH`, `FFR_DATA_PATH` import

**meta.json 정리**:

- [ ] `storage/results/meta.json`에서 `"tqqq_rate_spread_lab"` 키와 값 전체 제거

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

---

### Phase 3 (마지막) -- 문서 업데이트 + Black 포맷팅 + 최종 Validation

**문서 수정**:

- [ ] `scripts/CLAUDE.md`:
  - "지원 타입" 섹션에 `"tqqq_rate_spread_lab"` 추가
  - "레버리지 시뮬레이션 (tqqq/)" 섹션에 `generate_rate_spread_lab.py` 추가
- [ ] `src/qbt/tqqq/CLAUDE.md`:
  - "CLI 스크립트" 섹션에 `generate_rate_spread_lab.py` 추가
  - Streamlit 앱 설명에서 "CSV 1회 저장" 문구 제거
- [ ] `README.md`:
  - 워크플로우 2에 새 CLI 스크립트 단계 추가 (5번과 6번 사이)
  - Streamlit 앱 설명에서 "출력: storage/results/tqqq_rate_spread_lab_summary.csv" 제거
  - 프로젝트 구조에 `generate_rate_spread_lab.py` 추가

**포맷팅 및 최종 검증**:

- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. TQQQ시뮬레이션 / Rate Spread Lab CSV 생성 CLI 분리 (Streamlit 부수효과 제거)
2. TQQQ시뮬레이션 / generate_rate_spread_lab CLI 신규 + Streamlit CSV 저장 로직 제거
3. TQQQ시뮬레이션 / 금리-오차 분석 CSV 생성을 CLI 스크립트로 분리
4. TQQQ시뮬레이션 / Streamlit 앱에서 CSV 생성 분리하여 CLI 패턴 통일
5. TQQQ시뮬레이션 / Rate Spread Lab 연산-시각화 분리 (CLI 스크립트 추가)

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| CLI 스크립트의 월별 집계 로직이 Streamlit과 미세하게 달라질 수 있음 | `_prepare_monthly_data()` 로직을 그대로 이식. 동일한 비즈니스 로직 함수를 동일 인자로 호출 |
| `build_model_dataset()` 실패 시 CLI 비정상 종료 | Streamlit과 동일하게 try-except ValueError 처리, monthly/summary CSV 보존 |
| Streamlit import 제거 시 시각화에 필요한 import까지 제거 | Phase 2에서 유지 대상 import를 명시적으로 나열하여 검증 |
| meta.json 수동 편집 시 JSON 구문 오류 | 편집 후 JSON 파싱 확인 |

## 8) 메모(Notes)

### 결정사항

1. **`_prepare_monthly_data()` 로직 중복**: CLI에 동일 로직을 직접 구현. `analysis_helpers.py`로 이동은 과도한 리팩토링이므로 Non-Goals.
2. **`build_model_dataset()` 실패 처리**: `logger.warning()` 후 model CSV만 스킵, 스크립트는 성공(return 0) 처리.
3. **`meta_manager.py` VALID_CSV_TYPES**: `"tqqq_rate_spread_lab"`은 이미 등록됨 (변경 불필요).
4. **`scripts/CLAUDE.md` 메타데이터 타입 목록**: 현재 문서에는 3개만 나열되어 있으나, `meta_manager.py`에는 6개 등록됨. 이번 변경에서는 `tqqq_rate_spread_lab`만 추가.

### 진행 로그 (KST)

- 2026-02-02 21:00: Plan 작성 완료
