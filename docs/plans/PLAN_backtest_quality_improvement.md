# Implementation Plan: 백테스트 성능 + 코드 중복 제거 + 가독성 개선

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

**작성일**: 2026-02-19 16:00
**마지막 업데이트**: 2026-02-19 16:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`

**선행 조건**: Plan 1 (`PLAN_backtest_compliance_cleanup.md`) 완료 후 진행

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

- [ ] 앱 차트 데이터 변환 함수 성능 개선: `iterrows()` → `itertuples()` 전환
- [ ] 중복 함수 통합: `_build_line_data`와 `_build_band_data` → `_build_series_data`로 통합
- [ ] 데이터 로딩 중복 제거: `run_single_backtest.py`와 `run_grid_search.py`의 공통 로딩 로직 추출
- [ ] `_save_results` 함수 분리: signal/equity/trades/summary 개별 저장 함수로 분리
- [ ] `_load_csv` 함수에 `st.cache_data` 이유 주석 추가

## 2) 비목표(Non-Goals)

- 규칙 위반 수정 (Plan 1에서 완료)
- Dead Code 정리 (Plan 1에서 완료)
- 하위호환 로직 제거 (Plan 1에서 완료)
- 비즈니스 로직 변경 (동작은 동일해야 함)
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

전략별 분리 리팩토링 후 코드 품질 개선이 필요한 영역이 있다:

1. **성능**: `app_single_backtest.py`의 6개 데이터 변환 함수가 모두 `iterrows()`를 사용. `itertuples()`로 전환하면 약 3~5배 성능 향상. 데이터가 6,777행이므로 체감 차이 있음.

2. **함수 중복**: `_build_line_data`(signal_df 기반)와 `_build_band_data`(equity_df 기반)가 거의 동일한 로직. DataFrame과 컬럼명을 받는 하나의 함수로 통합 가능.

3. **데이터 로딩 중복**: `run_single_backtest.py`의 `_load_data()`와 `run_grid_search.py`의 메인 데이터 로딩 로직이 동일 패턴 (QQQ/TQQQ 로딩 → 공통 날짜 필터).

4. **함수 길이**: `_save_results` (137줄)가 signal/equity/trades/summary/metadata 5가지 저장을 한 함수에서 처리.

5. **주석 부재**: `_load_csv`가 프로젝트 규칙("Path 객체만 사용")과 달리 `str`을 받는 이유가 명시되지 않음.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 코딩 표준, 계층 분리
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙, Streamlit 앱 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] `app_single_backtest.py`의 데이터 변환 함수 6개가 `itertuples()` 사용
- [ ] `_build_line_data`와 `_build_band_data`가 `_build_series_data` 하나로 통합됨
- [ ] `run_single_backtest.py`와 `run_grid_search.py`에서 데이터 로딩 중복 제거됨
- [ ] `_save_results`가 개별 저장 함수로 분리됨
- [ ] `_load_csv`에 `st.cache_data` hashable 제약 주석 존재
- [ ] 동작 변경 없음 (기존과 동일한 결과 출력)
- [ ] 기존 테스트 전부 통과 (회귀 없음)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_single_backtest.py`: itertuples 전환 + 함수 통합 + 주석 추가
- `scripts/backtest/run_single_backtest.py`: `_save_results` 분리 + 데이터 로딩 공통화
- `scripts/backtest/run_grid_search.py`: 데이터 로딩 공통화

### 데이터/결과 영향

- 없음 (동작 동일, 리팩토링만 수행)

## 6) 단계별 계획(Phases)

### Phase 1 — 앱 성능 개선 + 함수 통합 (그린 유지)

**작업 내용**:

- [x] `_build_line_data`와 (Plan 1에서 수정된) `_build_band_data`를 `_build_series_data(df, col)` 하나로 통합
  - 인자: `df: pd.DataFrame, col: str`
  - 기존 호출부 (`_render_main_chart`)에서 호출 변경
- [x] `_build_candle_data`에서 `iterrows()` → `itertuples()` 전환
  - `band_map` 구성 루프도 `itertuples()` 사용
  - `signal_df` 순회도 `itertuples()` 사용 (index 기반 `change_pct` 접근 유지)
- [x] `_build_series_data` (통합된 함수): `itertuples()` 전환
- [x] `_build_markers`: `itertuples()` 전환
- [x] `_build_equity_data`: `itertuples()` 전환
- [x] `_build_drawdown_data`: `itertuples()` 전환
- [x] `_load_csv`에 `st.cache_data`가 hashable 인자만 지원하므로 `str`을 사용하는 이유 주석 추가

---

### Phase 2 — 데이터 로딩 공통화 + _save_results 분리 (그린 유지)

**작업 내용**:

- [ ] `scripts/backtest/run_single_backtest.py`의 `_load_data()`를 공통 함수로 유지하되, `run_grid_search.py`에서도 사용하도록 리팩토링
  - 방법: `_load_data()`를 `run_single_backtest.py`에서 `scripts/backtest/` 수준의 공유 모듈이 아닌, `run_grid_search.py`에서 직접 호출하도록 구성
  - 구체적: `run_single_backtest.py`의 `_load_data()` 함수를 모듈 레벨에서 재사용 가능한 형태로 export하고, `run_grid_search.py`에서 import
  - 대안: 두 스크립트가 같은 패키지가 아니므로, 공통 로직을 `_load_backtest_data()` 이름의 함수로 같은 디렉토리 내 공유 모듈에 배치
  - 최종 결정: `scripts/backtest/_common.py` 모듈 생성. 함수명 `load_backtest_data()`
- [ ] `scripts/backtest/run_grid_search.py`에서 인라인 데이터 로딩 로직을 `load_backtest_data()` 호출로 교체
- [ ] `scripts/backtest/run_single_backtest.py`에서 `_load_data()`를 `load_backtest_data()` 호출로 교체
- [ ] `_save_results` 함수를 개별 저장 함수로 분리:
  - `_save_signal_csv(result: SingleBacktestResult) -> Path`
  - `_save_equity_csv(result: SingleBacktestResult) -> Path`
  - `_save_trades_csv(result: SingleBacktestResult) -> Path`
  - `_save_summary_json(result: SingleBacktestResult, monthly_returns: list) -> Path`
  - `_save_results`는 이들을 조합 호출 + 메타데이터 저장

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `scripts/CLAUDE.md` 업데이트:
  - `scripts/backtest/_common.py` 모듈 존재 및 목적 기재
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 앱 성능 개선 + 코드 중복 제거 + 가독성 리팩토링
2. 백테스트 / itertuples 전환 + 함수 통합 + 데이터 로딩 공통화
3. 백테스트 / 성능 최적화 및 DRY 원칙 적용 리팩토링
4. 백테스트 / 앱 데이터 변환 성능 개선 + _save_results 분리 + 공통 모듈 추출
5. 백테스트 / 리팩토링 후속 품질 개선 (성능·중복·가독성)

## 7) 리스크(Risks)

- `itertuples()` 전환 시 컬럼 접근 방식 변경 (`row["col"]` → `row.col` 또는 `getattr(row, col)`)으로 인한 버그 가능 → 동적 컬럼명(ma_col 등)은 `getattr` 사용 필요
- `scripts/backtest/_common.py` 신규 모듈 생성 → 기존 아키텍처에 맞는지 확인 필요. scripts 폴더 내 공유 모듈이므로 CLI 계층 원칙에 부합 (도메인 로직 아님, 데이터 로딩 + 로깅만 수행)
- `_save_results` 분리 시 인자 전달 방식이 복잡해질 수 있음 → `SingleBacktestResult`를 그대로 전달하여 단순화

## 8) 메모(Notes)

- Plan 1 (`PLAN_backtest_compliance_cleanup.md`) 완료 후 진행
- `itertuples()`에서 `Date` 같은 컬럼 접근 시 `row.Date` 형태 사용. 예약어/특수 컬럼은 `getattr(row, col_name)` 사용.
- `_common.py`는 CLI 계층 내 공유 유틸이므로 `src/qbt/`에 배치하지 않음 (데이터 로딩 호출 + 로깅만 담당)

### 진행 로그 (KST)

- 2026-02-19 16:00: Plan 작성 완료

---
