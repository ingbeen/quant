# Implementation Plan: 차트 빌더 N+1 로드 제거 — 복수 연도 일괄 빌더 도입

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

**작성일**: 2026-04-29 23:55
**마지막 업데이트**: 2026-04-29 23:55
**관련 범위**: live (chart_data, cli, tests)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md)

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

- [x] 목표 1: 자산별 CSV + MA 계산을 1회만 수행하고 연도별로 슬라이스하는 **복수 연도 일괄 빌더** `build_chart_year_slices`, `build_equity_year_slices` 를 도입한다.
- [x] 목표 2: `_cmd_reset`, `_cmd_backfill_chart_years` 가 단일 연도 함수 반복 호출 패턴 → 복수 연도 일괄 호출 패턴으로 전환된다.
- [x] 목표 3: `_cmd_run_daily` 의 단일 연도 호출은 그대로 유지 (1회 호출이라 비효율 영향 없음).
- [x] 목표 4: 동일 입력 / 동일 출력을 보장 (회귀 없음). 기존 단위 테스트는 새 함수 기반으로 재작성하되 동일 계약을 검증한다.

## 2) 비목표(Non-Goals)

- 단일 연도 함수 (`build_chart_year_slice`, `build_equity_year_slice`) 의 시그니처 변경은 비목표. 그대로 유지하여 run-daily 의 1회 호출 호환성 보존.
- 모듈 레벨 캐시 / lru_cache 도입은 비목표 (테스트 격리 어려움).
- DESIGN 문서 갱신은 비목표 (사용자가 직접 처리).
- run-daily 의 trade_date 자동 결정 로직 (질문 1 의 별개 운영 이슈) 변경은 비목표.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- reset 의 8번 단계 (RTDB 주가 차트 재생성) 가 자산별 CSV (4개) 를 25 연도 × 4 자산 = **100회 로드 + EMA 재계산** 한다. 매 호출마다 같은 4994/5393/5975 행 CSV 를 디스크에서 다시 읽고 EMA(200) 를 다시 계산.
- backfill-chart-years 도 동일 패턴 (대상 연도 × 자산).
- 정확성 문제는 없으나 명백한 N+1 query 패턴. 운영 연차가 늘수록 연도 수가 선형 증가하므로 시간이 지날수록 비효율이 누적.
- 사용자 합의로 옵션 A (자산별 frame 1회 로드 + 연도별 슬라이싱) 채택.

### 영향받는 규칙(반드시 읽고 전체 숙지)

- 루트 [CLAUDE.md](../../CLAUDE.md): 코딩 표준 / 데이터 불변성 (원본 DataFrame 변경 금지)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md): live 도메인 핵심 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): Given-When-Then 패턴

## 4) 완료 조건(Definition of Done)

- [x] `build_chart_year_slices(state_dir, years: list[int], ...) -> dict[int, dict[str, ChartSeries]]` 신규 추가 — 자산별 frame 을 1회 로드 후 연도별로 슬라이싱
- [x] `build_equity_year_slices(state_dir, years: list[int]) -> dict[int, EquityChartSeries]` 신규 추가 — summary.jsonl 1회 로드 후 연도별 필터링
- [x] `chart_data.py.__all__` 에 새 함수 등록
- [x] `_cmd_reset` 의 8번 단계가 `build_chart_year_slices` 1회 호출로 변경
- [x] `_cmd_backfill_chart_years` 의 주가 / equity 루프가 새 복수 함수 1회 호출로 변경
- [x] `_cmd_run_daily` 의 단일 연도 호출은 그대로 유지 (단일 함수 사용)
- [x] 기존 단일 함수 (`build_chart_year_slice`, `build_equity_year_slice`) 는 제거하지 않고 유지 (run-daily 가 사용)
- [x] `tests/live/test_chart_data.py` 에 신규 함수의 단위 테스트 추가 (1회 로드 검증 / 다중 연도 출력 정합성)
- [x] `tests/live/test_cli.py` 의 reset / backfill 스파이를 새 함수 시그니처로 갱신
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트
  - [x] `README.md`: 변경 없음
  - [x] `docs/COMMANDS.md`: 변경 없음 (CLI 표면 동일)
  - [x] `src/live/CLAUDE.md`: 변경 없음 (모듈 책임은 동일)
  - [x] `docs/DESIGN_QBT_LIVE_FINAL.md`: 변경 없음 (사용자가 직접 처리)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**구현 코드**:

- `src/live/chart_data.py`
  - 새 함수 `build_chart_year_slices` 추가 — 자산별 frame 을 dict 로 1회 캐싱 후 연도 루프
  - 새 함수 `build_equity_year_slices` 추가 — summary 로우를 1회 로드 후 연도별 필터링
  - `__all__` 갱신 (4 → 6)
  - 기존 단일 함수는 그대로 유지 (run-daily 가 사용)

- `src/live/cli.py`
  - `_cmd_reset`: `build_chart_year_slices(state_dir, sorted(years), ...)` 1회 호출로 전환
  - `_cmd_backfill_chart_years`: 주가 / equity 양쪽 모두 새 복수 함수 사용
  - `_cmd_run_daily`: 변경 없음 (단일 연도 호출 유지)
  - import 갱신 (새 함수 추가)

**테스트**:

- `tests/live/test_chart_data.py`
  - `TestBuildChartYearSlices` 신규 클래스 — 다중 연도 입력 / 출력 정합성 / 1회 로드 보장 (모듈 monkeypatch 로 `_load_slot_frame` 호출 횟수 검증)
  - `TestBuildEquityYearSlices` 신규 클래스 — 동일 패턴
- `tests/live/test_cli.py`
  - reset / backfill 스파이의 `build_chart_year_slice` 모킹 → `build_chart_year_slices` 로 갱신
  - 호출 인자 검증 (`years` 리스트가 정렬된 전체 집합인지)

### 데이터/결과 영향

- RTDB 페이로드: **변경 없음** — 동일 경로에 동일 페이로드 기록.
- 성능: reset / backfill 의 차트 재생성 단계가 약 100배 빠르게 동작 (자산 로드 1회 + 연도 슬라이싱은 메모리 연산).
- 운영 영향: 사용자가 reset / backfill 실행 시 진행이 빠르게 끝남. CLI 옵션 / 출력 포맷은 동일.

## 6) 단계별 계획(Phases)

### Phase 1 — chart_data.py 에 복수 연도 빌더 추가

**작업 내용**:

- [x] 자산별 frame 을 한 번 로드해 `dict[asset_id, (dates, close_list, ma_list, slot)]` 로 캐싱하는 내부 헬퍼 추가
- [x] `build_chart_year_slices(state_dir, years: list[int], user_trades, signal_history)` 추가 — 헬퍼로 1회 로드 후 연도 루프
- [x] `build_equity_year_slices(state_dir, years: list[int])` 추가 — `_load_summary_rows` 1회 호출 후 연도별 필터링
- [x] `__all__` 에 두 함수 등록
- [x] 기존 단일 함수 동작 영향 없음을 import 체크로 확인

**Validation**:

- [x] `poetry run python -c "from live.chart_data import build_chart_year_slices, build_equity_year_slices; print('OK')"`

---

### Phase 2 — cli.py 호출처 전환

**작업 내용**:

- [x] `cli.py` import 에 `build_chart_year_slices`, `build_equity_year_slices` 추가
- [x] `_cmd_reset` 8번 단계: for 루프를 `build_chart_year_slices(state_dir, sorted(years), ...)` 1회 호출로 변경. 결과 dict 를 순회하며 `write_chart_year_slice(year=year, year_map=year_map)` 호출 (write 는 연도별 1회씩)
- [x] `_cmd_backfill_chart_years` 의 주가 루프: `build_chart_year_slices(state_dir, target_prices_years, ...)` 1회 호출 후 결과 dict 를 순회하며 write
- [x] `_cmd_backfill_chart_years` 의 equity 루프: `build_equity_year_slices(state_dir, target_equity_years)` 1회 호출 후 결과 dict 를 순회하며 write
- [x] `_cmd_run_daily` 는 변경 없음 (`build_chart_year_slice` 단일 호출 유지)

**Validation**:

- [x] `poetry run python -m live --help` 출력 변동 없음 (CLI 표면 동일)

---

### Phase 3 — 테스트 갱신

**작업 내용**:

- [x] `tests/live/test_chart_data.py`:
  - 신규 클래스 `TestBuildChartYearSlices`: 입력 연도 리스트 → 키가 정확히 일치하는 dict 반환 / 각 연도별 슬라이스 내용이 단일 함수 결과와 동일 / `_load_slot_frame` mock 으로 1회만 호출 (자산 수만큼) 보장
  - 신규 클래스 `TestBuildEquityYearSlices`: 입력 연도 리스트 → 연도별 dict / `_load_summary_rows` 1회만 호출
- [x] `tests/live/test_cli.py`:
  - `_install_reset_spies` 의 `build_chart_year_slice` 스파이를 `build_chart_year_slices` 로 교체 (시그니처: state_dir, years, user_trades, signal_history)
  - reset 테스트의 어서션 갱신: 호출 횟수 = 1, 인자 years 리스트가 meta 의 연도 합집합과 일치
  - backfill 테스트의 `_setup_common_mocks` 도 동일하게 갱신

**Validation**:

- [x] `poetry run pytest tests/live/ -x` 통과

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 / Phase 체크박스 최종 갱신

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1018, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / chart 빌더 N+1 로드 제거 — 복수 연도 일괄 빌더 도입
2. live / build_chart_year_slices 추가 — reset/backfill 의 자산 CSV 반복 로드 제거
3. live / 차트 재생성 성능 최적화 — 자산 frame 1회 로드 + 연도 슬라이싱
4. live / chart_data 복수 연도 일괄 빌더 추가 + reset/backfill 호출처 전환
5. live / N+1 로드 패턴 제거 (chart + equity 빌더 일괄화)

## 7) 리스크(Risks)

- **리스크 1**: 새 복수 함수와 단일 함수가 둘 다 존재 → 향후 누가 어느 쪽을 써야 할지 혼동. 함수 docstring 에 "단일 연도 호출은 단일 함수 / 복수 연도는 복수 함수" 가이드 명시로 완화.
- **리스크 2**: reset / backfill 의 mock 시그니처 변경으로 기존 테스트 깨질 가능성. Phase 3 에서 일괄 갱신.
- **리스크 3**: 결과 페이로드 동등성 — 새 함수는 frame 을 한 번만 로드하므로 단일 함수와 동일한 슬라이싱 로직 결과를 반환해야 함. Phase 3 의 테스트로 명시적 비교.

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-29 23:55: plan 초안 작성, Auto mode 로 즉시 진행
- 2026-04-30 00:05: Phase 1 (chart_data.py 에 build_chart_year_slices / build_equity_year_slices 추가) 완료, import 검증 통과
- 2026-04-30 00:08: Phase 2 (cli.py 의 reset / backfill 호출처를 새 복수 함수로 전환, run-daily 는 단일 함수 유지) 완료, --help 출력 변동 없음
- 2026-04-30 00:12: Phase 3 (test_chart_data.py 에 TestBuildChartYearSlices / TestBuildEquityYearSlices 신규 클래스 추가, test_cli.py 의 reset/backfill 스파이 갱신) 완료, pytest 499 passed
- 2026-04-30 00:15: 마지막 Phase (black + validate_project.py) 완료, 1018 passed / 0 failed / 0 skipped (신규 11 테스트 추가). N+1 회피 보장이 _load_slot_frame / _load_summary_rows 호출 횟수 어서션으로 명시적으로 고정됨.

---
