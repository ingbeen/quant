# Implementation Plan: 구간별 고정 스프레드 모델 (오라클)

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

**작성일**: 2026-02-16 23:30
**마지막 업데이트**: 2026-02-17 00:30
**관련 범위**: tqqq, scripts, constants, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `lookup_spread.py`에 사용자 정의 구간 경계 기반 스프레드 테이블 생성·조회 함수 추가
- [x] 목표 2: CLI 스크립트로 전체 기간 실현 스프레드 역산 → 구간별 고정 스프레드 테이블 생성·평가·저장
- [x] 목표 3: 앱 UI에 3번째 모드 "구간별 고정 스프레드 (오라클)" 추가
- [x] 목표 4: 새 함수에 대한 단위 테스트 추가

## 2) 비목표(Non-Goals)

- 워크포워드 검증 구현 (오라클 모델이므로 불필요)
- `generate_synthetic.py` 수정 (1999~2009 시뮬레이션은 별도 작업)
- `generate_daily_comparison.py` 수정 (기존 softplus 모델 기반 유지)
- 기존 룩업테이블/softplus 모델 코드 변경
- `simulation.py`의 `simulate()` 함수 시그니처 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 2가지 스프레드 모델이 존재: (1) Softplus, (2) 룩업테이블 (균등 구간 폭 + 그리드 서치)
- TQQQ가 존재하지 않는 1999~2009 기간 시뮬레이션에 사용할 "오라클" 모델이 필요
- 오라클 모델: 전체 TQQQ 기간(2010~2025)의 데이터를 활용해 금리 구간별 스프레드를 확정
- 미래 데이터를 참조하는 전제이므로 워크포워드 불필요, 인샘플 RMSE로 적합도 평가
- 기존 `build_lookup_table()`은 균등 `bin_width` 기반이라 비균등 경계를 지원하지 않음 → 별도 함수 필요

### 구간 분할 근거: [0, 2, 4, ∞) 3구간

FFR 데이터 분석 결과:

| 구간 | TQQQ 데이터(2010~) | 1999~2009 사용처 |
|------|-------------------|-----------------|
| 0~2% | 139개월 (72%) | 53개월 (40%) |
| 2~4% | 19개월 (10%) | 24개월 (18%) |
| 4%+ | 35개월 (18%) | 55개월 (42%) |

4구간 [0,1,3,5,∞) 대안은 5%+ 구간에 TQQQ 데이터가 17개월뿐이라 불안정. 3구간이 더 안전.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `CLAUDE.md` (루트)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `build_segment_table()` 구현: 구간별 스프레드 집계 정확
- [x] `lookup_spread_from_segments()` 구현: 구간 경계 기반 조회 정확
- [x] `build_monthly_spread_map_from_segments()` 구현: FundingSpreadSpec 호환 dict 반환
- [x] `evaluate_segment_combination()` 구현: 인샘플 RMSE 계산
- [x] CLI 스크립트 `generate_segment_spread.py`: 구간별 스프레드 생성, RMSE 평가, CSV/메타 저장
- [x] 앱 사이드바에 3번째 모드 추가 및 렌더링 완료
- [x] 회귀/신규 테스트 추가 (14개 신규, 총 301 passed)
- [x] `poetry run python validate_project.py` 통과 (passed=301, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/constants.py` — 구간별 고정 스프레드 상수 추가
- `src/qbt/tqqq/lookup_spread.py` — 함수 4개 추가
- `src/qbt/utils/meta_manager.py` — `VALID_CSV_TYPES`에 `"tqqq_segment_spread"` 추가
- `scripts/tqqq/spread_lab/generate_segment_spread.py` — 새 CLI 스크립트
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — 3번째 모드 추가
- `tests/test_tqqq_lookup_spread.py` — 테스트 클래스 3개 추가
- `src/qbt/tqqq/CLAUDE.md` — 함수 목록 업데이트
- `scripts/CLAUDE.md` — 스크립트 목록 업데이트
- `CLAUDE.md` (루트) — CSV 파일 목록 업데이트

### 데이터/결과 영향

- `storage/results/spread_lab/tqqq_segment_spread.csv` — 새로 생성 (구간, 스프레드, 관측일수, RMSE)
- `storage/results/meta.json` — `tqqq_segment_spread` 항목 추가
- 기존 CSV/결과에는 영향 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트로 핵심 정책/인터페이스 고정 (레드)

**근거**: 새 함수 3개의 핵심 정책(구간 분류 로직, 경계값 포함/미포함 규칙, 음수 스프레드 클램핑)이 결과값에 직접 영향을 주는 인바리언트이므로 테스트로 먼저 고정.

**작업 내용**:

- [x] `tests/test_tqqq_lookup_spread.py`에 `TestBuildSegmentTable` 클래스 추가
  - `test_three_segments_mean_aggregation`: boundaries=[0,2,4], 각 구간에 데이터 배분 후 mean 스프레드 정확성
  - `test_three_segments_median_aggregation`: median 통계량 정확성
  - `test_single_segment_all_data`: 모든 데이터가 한 구간에 속할 때 정확한 집계
  - `test_empty_segment_excluded`: 데이터가 없는 구간은 테이블에서 제외
  - `test_invalid_stat_func_raises`: 지원하지 않는 stat_func → ValueError
  - `test_boundaries_must_be_ascending`: 비오름차순 경계 → ValueError
  - `test_boundaries_minimum_two`: 경계값 1개 미만 → ValueError (최소 2개로 1구간)
- [x] `tests/test_tqqq_lookup_spread.py`에 `TestLookupSpreadFromSegments` 클래스 추가
  - `test_exact_segment_lookup`: 구간 내부 금리값 → 올바른 스프레드 반환
  - `test_boundary_value_at_lower`: 구간 하한(0, 2, 4)은 해당 구간에 포함 (하한 포함, 상한 미포함)
  - `test_last_segment_includes_infinity`: 마지막 구간은 상한 +inf (ffr_pct=10.0 → 4%+ 구간)
  - `test_negative_ffr_fallback`: ffr_pct < 0 → 첫 구간으로 fallback
  - `test_empty_table_raises`: 빈 테이블 → ValueError
- [x] `tests/test_tqqq_lookup_spread.py`에 `TestBuildMonthlySpreadMapFromSegments` 클래스 추가
  - `test_monthly_map_structure`: FFR 데이터 3개월 → dict[str, float] 형태 반환
  - `test_all_spreads_positive`: 모든 스프레드 값 > 0 (음수/0은 EPSILON 클램핑)

---

### Phase 1 — 상수 추가 및 비즈니스 로직 구현 (그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 상수 추가:
  - `DEFAULT_SEGMENT_BOUNDARIES: Final = (0.0, 2.0, 4.0)` — 구간 경계 (%, 암묵적 +inf)
  - `DEFAULT_SEGMENT_STAT_FUNC: Final = "median"` — 기본 통계량
  - `SEGMENT_SPREAD_CSV_PATH: Final = SPREAD_LAB_DIR / "tqqq_segment_spread.csv"`
  - `__all__`에 새 상수 추가
- [x] `src/qbt/tqqq/lookup_spread.py`에 함수 4개 추가:
  - `build_segment_table(realized_df, boundaries, stat_func) -> dict[tuple[float, float], float]`
    - boundaries 유효성 검증 (최소 2개, 오름차순, stat_func 검증)
    - boundaries=[0,2,4] → 구간: [(0,2), (2,4), (4,inf)]
    - 각 구간의 mean/median 스프레드 집계
    - 데이터 없는 구간은 테이블에서 제외
    - `realized_df.copy()` 사용 (원본 불변)
  - `lookup_spread_from_segments(ffr_pct, segment_table, boundaries) -> float`
    - `boundaries[i] <= ffr_pct < boundaries[i+1]` (마지막 구간은 상한 없음)
    - ffr_pct < boundaries[0] → 첫 구간으로 fallback
    - 빈 테이블 시 ValueError
  - `build_monthly_spread_map_from_segments(ffr_df, segment_table, boundaries) -> dict[str, float]`
    - FFR의 각 월별 금리를 구간 테이블에서 조회
    - 음수/0 스프레드는 EPSILON으로 클램핑
    - FundingSpreadSpec dict 호환
  - `evaluate_segment_combination(realized_df, boundaries, stat_func, ffr_df, expense_df, underlying_df, actual_df, leverage) -> dict[str, object]`
    - 기존 `evaluate_lookup_combination()` 패턴을 따름
    - 반환: boundaries, stat_func, rmse_pct, n_segments, segment_details
- [x] Phase 0의 모든 레드 테스트가 그린 전환 확인 (14 passed)

---

### Phase 2 — CLI 스크립트 및 메타데이터 (그린 유지)

**작업 내용**:

- [x] `src/qbt/utils/meta_manager.py`의 `VALID_CSV_TYPES`에 `"tqqq_segment_spread"` 추가
- [x] `scripts/tqqq/spread_lab/generate_segment_spread.py` 생성:
  - 패턴: 기존 `tune_lookup_params.py` 참고
  - `@cli_exception_handler` + `logger = get_logger(__name__)`
  - `main()` 흐름:
    1. 데이터 로딩 (QQQ, TQQQ, FFR, Expense)
    2. 실현 스프레드 역산 (`calculate_realized_spread()`)
    3. 구간별 스프레드 테이블 생성 (`build_segment_table()`)
    4. 인샘플 RMSE 평가 (`evaluate_segment_combination()`)
    5. 결과 로그 출력 (구간, 스프레드, 관측일수, RMSE)
    6. CSV 저장 (`SEGMENT_SPREAD_CSV_PATH`)
    7. 메타데이터 저장 (`save_metadata("tqqq_segment_spread", ...)`)
    8. `return 0`
  - `if __name__ == "__main__": sys.exit(main())`

---

### Phase 3 — 앱 UI 추가 (그린 유지)

**작업 내용**:

- [x] `app_rate_spread_lab.py` 사이드바 수정:
  - `st.radio` 선택지에 `"구간별 고정 스프레드 (오라클)"` 추가
  - 메인 분기에 `elif` 추가 → `_render_segment_mode()` 호출
- [x] `_render_intro()` 내 스프레드 모델 변천사 `st.info()`에 3번째 모델 추가
- [x] `_render_segment_mode()` 함수 구현:
  - `st.header("구간별 고정 스프레드 모델 (오라클)")`
  - 오라클 모델 설명 `st.warning()` (미래 데이터 참조 전제, 용도: 1999~2009 시뮬레이션)
  - `_render_segment_table_section()` 호출
  - `_render_segment_rmse_section()` 호출
- [x] `_render_segment_table_section()` 함수 구현:
  - CSV 존재 확인, 없으면 `st.warning()` + 실행 명령어 안내 + `return`
  - 구간별 스프레드 테이블 `st.dataframe()` 표시
  - `st.metric()` 4개: 구간 수, 통계량, 인샘플 RMSE, 총 관측일수
- [x] `_render_segment_rmse_section()` 함수 구현:
  - 다른 모델(softplus, 룩업테이블)과 인샘플 RMSE 비교 테이블
  - 용어 설명·해석 방법·지표 판단 마크다운 섹션

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트: `lookup_spread.py` 섹션에 구간별 고정 스프레드 함수 추가
- [x] `scripts/CLAUDE.md` 업데이트: `spread_lab/` 섹션에 `generate_segment_spread.py` 추가
- [x] `CLAUDE.md` (루트) 업데이트: `storage/results/spread_lab/` 섹션에 `tqqq_segment_spread.csv` 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 구간별 고정 스프레드 오라클 모델 구현 및 앱 UI 추가
2. TQQQ시뮬레이션 / 금리 3구간 고정 스프레드 모델 추가 (1999~2009 시뮬레이션 준비)
3. TQQQ시뮬레이션 / 비균등 금리 구간별 스프레드 역산 모델 구현 및 테스트
4. TQQQ시뮬레이션 / 오라클 스프레드 모델(전체기간 역산) 추가 및 spread_lab 앱 3모드 확장
5. TQQQ시뮬레이션 / 구간별 고정 스프레드 모델 추가로 spread_lab 3번째 모델 완성

## 7) 리스크(Risks)

- 2~4% 구간에 TQQQ 관측 19개월로 통계적 신뢰도 상대적으로 낮음 → CSV에 관측일 수 포함하여 사용자 판단 가능
- TQQQ 최대 FFR 5.33%, 1999~2009 최대 FFR 6.54% → 4%+ 구간에서 6%대 외삽(extrapolation) 발생 → 오라클 전제이므로 수용
- `segment_table` 키 타입 `tuple[float, float]`이 기존 `dict[float, float]`와 달라 혼동 가능 → `_from_segments` 접미사로 명확 분리
- 앱 3개 모드로 코드 복잡도 증가 → 모드별 렌더 함수 분리로 관리

## 8) 메모(Notes)

### 핵심 설계 결정

- `build_segment_table()` 반환 타입: `dict[tuple[float, float], float]`
  - 비균등 구간에서는 "구간 중앙"이 무의미 → 하한/상한 쌍이 명확
  - 기존 `build_lookup_table()`의 `dict[float, float]` (중앙값 키)와 의도적으로 다름
- boundaries 파라미터는 % 단위 (비율 아님): 기존 `bin_width_pct`와 일관성 유지
- `calculate_realized_spread()`: 기존 함수 그대로 재사용 (변경 없음)
- `evaluate_segment_combination()`: 기존 `evaluate_lookup_combination()` 패턴 동일하게 적용

### 진행 로그 (KST)

- 2026-02-16 23:30: 계획서 작성
- 2026-02-17 00:30: Phase 0~4 완료 (passed=301, failed=0, skipped=0)

---
