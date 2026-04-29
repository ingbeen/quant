# Implementation Plan: run-daily / reset / backfill 의 자산 로드 중복 제거

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

**작성일**: 2026-04-30 00:25
**마지막 업데이트**: 2026-04-30 00:25
**관련 범위**: live (chart_data, cli, data_fetcher, tests)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `append_today_to_csv` 시그니처를 `existing_df` 인자를 받도록 확장하여, 이미 로드된 frame 이 있으면 재로드하지 않도록 한다.
- [x] 목표 2: `_refresh_live_csvs` 가 자산당 한 번만 CSV 를 읽도록 변경한다 (`load_csv` → `append_today_to_csv` 의 재로드 제거).
- [x] 목표 3: `build_chart_meta_and_year_slices(state_dir, years, ...) -> tuple[dict[str, ChartMeta], dict[int, dict[str, ChartSeries]]]` 통합 함수를 추가하여 차트 빌더가 자산 frame 을 1회만 로드하도록 한다.
- [x] 목표 4: `_cmd_reset`, `_cmd_backfill_chart_years`, `_publish_to_rtdb` 가 통합 함수를 사용하도록 전환한다.
- [x] 목표 5: 동일 입력 / 동일 출력 보장 (회귀 없음).

## 2) 비목표(Non-Goals)

- `_build_market_bundle` 의 frame 을 차트 빌더와 공유하는 작업은 비목표 (자산 집합이 signal+trade 와 trade 만으로 달라 복잡도 대비 이득이 작음).
- 단일 연도용 함수 (`build_chart_year_slice`, `build_equity_year_slice`, `build_chart_meta`, `build_equity_meta`) 의 시그니처 변경은 비목표 (호환성 유지).
- 단일 연도용 함수 제거는 비목표 (다른 호출처가 있을 수 있고, 회귀 위험 회피).
- 단일 연도 / 복수 연도 빌더 (`build_chart_year_slices`, `build_equity_year_slices`) 도 그대로 유지 (외부 호출자 호환).
- DESIGN 문서 갱신은 비목표.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 로그 분석 결과, run-daily 한 번 실행 시 자산 데이터가 약 26회 로드된다 (이론적 최소: 6회). 4.3배 비효율.
- 가장 큰 비효율 두 곳:
  1. `_refresh_live_csvs` 가 자산당 `load_csv` 1회 + `append_today_to_csv` 내부의 `load_stock_data` 1회 = 자산당 2회 로드
  2. `_publish_to_rtdb` 의 `build_chart_meta` + `build_chart_year_slices` 가 같은 자산 frame 을 두 번 로드
- 직전 plan ([PLAN_chart_year_slices_batch_loader.md](PLAN_chart_year_slices_batch_loader.md)) 에서 N+1 (연도 × 자산) 패턴은 제거했으나, 함수 간 frame 공유는 미해결.
- 사용자 합의로 (A) append_today_to_csv 재로드 제거 + (B) 차트 빌더 통합 함수 도입 채택.

### 영향받는 규칙(반드시 읽고 전체 숙지)

- 루트 [CLAUDE.md](../../CLAUDE.md): 코딩 표준 / 데이터 불변성
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md): live 도메인 핵심 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): Given-When-Then 패턴

## 4) 완료 조건(Definition of Done)

- [x] `append_today_to_csv` 시그니처에 `existing_df: pd.DataFrame | None = None` 옵셔널 인자가 추가되어, 주어지면 내부 재로드를 건너뛴다
- [x] `_refresh_live_csvs` 가 자신이 로드한 `csv_df` 를 `append_today_to_csv` 에 전달하여 자산당 로드 횟수가 2회 → 1회로 감소
- [x] `build_chart_meta_and_year_slices` 신규 추가 — 자산 frame 을 1회 로드 후 meta + slices 한 번에 반환
- [x] `_cmd_reset` 의 8단계가 통합 함수 1회 호출로 변경
- [x] `_cmd_backfill_chart_years` 의 주가 차트 부분이 통합 함수 1회 호출로 변경
- [x] `_publish_to_rtdb` 의 차트 빌더 호출이 통합 함수 1회 호출로 변경
- [x] 회귀/신규 테스트 추가
  - `tests/live/test_data_fetcher.py`: `append_today_to_csv` 의 `existing_df` 인자 동작 검증
  - `tests/live/test_chart_data.py`: `TestBuildChartMetaAndYearSlices` — meta + slices 동시 반환 정합성 / 자산 frame 1회 로드 보장
- [x] `tests/live/test_cli.py` 의 reset / backfill / run-daily 스파이가 통합 함수 시그니처로 갱신
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트
  - [x] `README.md` / `docs/COMMANDS.md` / `src/live/CLAUDE.md` / `docs/DESIGN_QBT_LIVE_FINAL.md`: 변경 없음 (외부 인터페이스 동일)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**구현 코드**:

- `src/live/data_fetcher.py`
  - `append_today_to_csv` 에 `existing_df: pd.DataFrame | None = None` 인자 추가
  - existing_df 가 None 이면 기존 동작 (load_stock_data 호출), 주어지면 그것을 사용
- `src/live/chart_data.py`
  - `build_chart_meta_and_year_slices(state_dir, years, user_trades, signal_history) -> tuple[meta_map, slices_map]` 신규 추가
  - 내부에 `_load_all_slot_frames(state_dir) -> dict[asset_id, (slot, dates, close, ma)]` 헬퍼 추가
  - `__all__` 갱신
  - 기존 함수들 (`build_chart_meta`, `build_chart_year_slice`, `build_chart_year_slices`) 유지
- `src/live/cli.py`
  - `_refresh_live_csvs`: `csv_df` 를 `append_today_to_csv` 에 전달
  - `_cmd_reset`: `build_chart_meta` + `build_chart_year_slices` → `build_chart_meta_and_year_slices` 1회 호출
  - `_cmd_backfill_chart_years`: 주가 차트 부분을 통합 함수로 전환
  - `_publish_to_rtdb`: 동일 패턴으로 전환
  - import 갱신

**테스트**:

- `tests/live/test_data_fetcher.py`
  - `append_today_to_csv` 의 `existing_df` 인자 동작 검증 — 주어지면 load_stock_data 재호출 안 함 (mock 으로 검증)
- `tests/live/test_chart_data.py`
  - `TestBuildChartMetaAndYearSlices` 신규 클래스 — meta + slices 결과가 단일 함수 결과와 동등 / `_load_slot_frame` 호출이 자산 수만큼만 발생
- `tests/live/test_cli.py`
  - reset 스파이의 `build_chart_meta` + `build_chart_year_slices` → `build_chart_meta_and_year_slices` 로 통합
  - backfill 스파이도 동일 갱신
  - `_publish_to_rtdb` 테스트의 빌더 mock 갱신

### 데이터/결과 영향

- RTDB 페이로드 / Git state 결과: **변경 없음**
- 성능: run-daily 26 → 16회 (38% 감소), reset 8 → 4회 (50% 감소), backfill 8 → 4회 (50% 감소)

## 6) 단계별 계획(Phases)

### Phase 1 — `append_today_to_csv` 시그니처 확장

**작업 내용**:

- [x] `data_fetcher.py`: `append_today_to_csv` 에 `existing_df` 옵셔널 인자 추가, None 이면 기존처럼 `load_stock_data` 호출, 주어지면 그것을 사용
- [x] `cli.py:_refresh_live_csvs`: `append_today_to_csv(csv_path, today_row, existing_df=csv_df)` 형태로 호출

**Validation**:

- [x] import 검증

---

### Phase 2 — `chart_data.py` 통합 빌더 추가

**작업 내용**:

- [x] `_load_all_slot_frames(state_dir)` 내부 헬퍼 추가 — 자산별 (slot, dates, close, ma) 튜플을 dict 로 1회 로드
- [x] `build_chart_meta_and_year_slices(state_dir, years, user_trades, signal_history)` 신규 추가 — 헬퍼 1회 호출 후 meta_map / slices_map 동시 생성
- [x] `__all__` 에 새 함수 등록
- [x] 기존 단일 함수들은 그대로 유지

**Validation**:

- [x] `poetry run python -c "from live.chart_data import build_chart_meta_and_year_slices; print('OK')"`

---

### Phase 3 — cli.py 호출처 전환

**작업 내용**:

- [x] `cli.py` import 갱신
- [x] `_publish_to_rtdb` (run-daily): 차트 meta + 현재 연도 슬라이스 호출을 통합 함수 1회로 변경 (years=[current_year])
- [x] `_cmd_reset`: meta_map 만들기와 year_slices_map 만들기를 통합 함수 1회로 변경
- [x] `_cmd_backfill_chart_years`: 주가 차트 빌더 호출을 통합 함수 1회로 변경 (equity 는 별도)

**Validation**:

- [x] `python -m live --help` 변동 없음 / 코드 컴파일 OK

---

### Phase 4 — 테스트 갱신

**작업 내용**:

- [x] `test_data_fetcher.py`: `append_today_to_csv` 의 `existing_df` 동작 검증 (load_stock_data mock 호출 횟수 어서션)
- [x] `test_chart_data.py`: `TestBuildChartMetaAndYearSlices` 신규 클래스 — 결과 정합성 + 1회 로드 검증
- [x] `test_cli.py`: reset / backfill / run-daily 스파이를 통합 함수 시그니처로 갱신

**Validation**:

- [x] `poetry run pytest tests/live/ -x` 통과

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 / Phase 체크박스 최종 갱신

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1025, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / run-daily 자산 로드 중복 제거 — append + 차트 빌더 통합
2. live / append_today_to_csv 재로드 제거 + chart_meta+slices 통합 함수 도입
3. live / 차트 빌더 통합 (build_chart_meta_and_year_slices) + append 시그니처 확장
4. live / run-daily / reset / backfill 의 자산 frame 1회 로드 보장
5. live / 데이터 로드 N+1 제거 (frame 공유 + append 재로드 제거)

## 7) 리스크(Risks)

- **리스크 1**: `append_today_to_csv` 시그니처 변경으로 기존 호출처 호환성 깨질 수 있음. 옵셔널 기본값 None 으로 두어 기본 동작은 변동 없도록.
- **리스크 2**: 통합 함수와 단일 함수가 결과가 다를 수 있음. Phase 4 의 테스트로 결과 정합성을 명시적 검증.
- **리스크 3**: cli.py 의 reset / backfill / run-daily 가 동일한 통합 함수를 쓰는데, run-daily 는 단일 연도라 years=[current_year] 1개 원소 리스트 전달. 빈 리스트 입력 시 빈 dict 반환을 명시.

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-30 00:25: plan 초안 작성, Auto mode 로 즉시 진행
- 2026-04-30 00:30: Phase 1 (`append_today_to_csv` 시그니처에 `existing_df` 추가, `_refresh_live_csvs` 가 csv_df 전달) 완료
- 2026-04-30 00:33: Phase 2 (`build_chart_meta_and_year_slices` 통합 함수 추가, `years=None` 자동 합집합 모드 포함) 완료
- 2026-04-30 00:38: Phase 3 (`_publish_to_rtdb`, `_cmd_reset`, `_cmd_backfill_chart_years` 가 통합 함수 사용) 완료
- 2026-04-30 00:42: Phase 4 (test_data_fetcher / test_chart_data / test_cli 갱신, N+1 회피 어서션 추가) 완료
- 2026-04-30 00:48: 마지막 Phase (black + Ruff/PyRight 정리) 완료, **1025 passed / 0 failed / 0 skipped** (신규 7 테스트 추가)

---
