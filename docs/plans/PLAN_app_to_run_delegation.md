# Implementation Plan: app -> run 도메인 연산 위임 (밴드/기여도/OHLC 전일대비%)

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

**작성일**: 2026-04-14 12:00
**마지막 업데이트**: 2026-04-14 13:30
**관련 범위**: backtest, scripts/backtest
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md

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

- [x] 목표 1: 대시보드(`app_single_backtest.py`, `app_portfolio_backtest.py`)에 잔존하는 도메인 연산을 `run_*.py` 또는 비즈니스 로직 계층으로 위임하여 "CLI 계층 도메인 로직 금지" 원칙을 회복한다.
- [x] 목표 2: 포트폴리오 시그널 CSV에 `upper_band` / `lower_band` 컬럼을 사전 계산해 저장하고, 대시보드는 컬럼을 읽기만 하도록 단순화한다.
- [x] 목표 3: 포트폴리오 에쿼티 CSV에 `{asset_id}_contribution` 컬럼(실현+미실현)을 사전 계산해 저장하고, 대시보드의 자산별 기여도 섹션에서 합산 로직을 제거한다 (legacy fallback 경로 완전 제거).
- [x] 목표 4: 단일/포트폴리오 시그널 CSV에 OHLC 4종 전일대비% 컬럼(`open_pct`, `high_pct`, `low_pct`, `close_pct`)을 사전 계산해 저장하고, 두 대시보드의 캔들 데이터 변환에서 `prev_close.shift(1)` 기반 % 계산 로직을 제거한다.

## 2) 비목표(Non-Goals)

- 기존 결과(CSV/JSON)와의 호환성 유지 또는 마이그레이션 도구 작성. (사용자가 모든 백테스트 스크립트를 재실행할 예정)
- legacy fallback 경로 (`_render_contribution_section_legacy`, PnL 컬럼 미존재 분기) 보존. 이 plan에서 완전히 제거한다.
- 시각화 변환에 가까운 단순 산술(`pnl_pct * 100`, `cash_weight = 1 - sum`, 도넛용 잔여 비중, 분기별 `resample("QE").diff()`, `pivot_table`)은 위임 대상이 아니며 app에 유지한다.
- 새 전략/자산 추가 또는 백테스트 비즈니스 로직 변경.
- 리밸런싱 빈도/편차 통계 사전 계산(목표 1~4 범위 외).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)는 "CLI 계층에 도메인 로직 포함 금지, 단순히 비즈니스 로직 호출만 담당"을 명시한다. 그러나 두 dashboard 파일에는 다음 도메인 연산이 잔존한다:
  - [app_portfolio_backtest.py:1415-1435](../../scripts/backtest/app_portfolio_backtest.py#L1415) `_compute_bands_for_signal()` — `upper_band = ma * (1 + buy_buffer)`, `lower_band = ma * (1 - sell_buffer)`. 명백한 전략 밴드 계산.
  - [app_portfolio_backtest.py:802-808](../../scripts/backtest/app_portfolio_backtest.py#L802) 자산별 기여도 = `realized_pnl + unrealized_pnl` 직접 합산.
  - [app_portfolio_backtest.py:922-973](../../scripts/backtest/app_portfolio_backtest.py#L922) `_render_contribution_section_legacy()` — value 기반 fallback (사용자 재실행 전제이므로 제거 가능).
  - [app_single_backtest.py:230, 258-264](../../scripts/backtest/app_single_backtest.py#L230) 및 [app_portfolio_backtest.py:1456, 1487-1490](../../scripts/backtest/app_portfolio_backtest.py#L1456) `prev_close = signal_df[COL_CLOSE].shift(1)` + OHLC 4종 전일대비% 계산. 두 파일에 중복.
- 이 연산들은 매 렌더링 시 반복 수행되며, 도메인 변경 시 두 파일을 동시에 수정해야 하는 부담이 있다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 데이터 불변성, 출력 데이터 반올림 규칙(`ROUND_PRICE`, `ROUND_PERCENT`, `ROUND_CAPITAL`), 비율 표기 규칙
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md) — CLI 계층 책임/비즈니스 로직 분리 원칙
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md) — 계층 분리, 상수 관리, 데이터 처리 규칙
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) — `csv_export.py` 의존 방향 규칙(analysis → csv_export 단방향), portfolio `equity_df` 컬럼 명세, 대시보드 Feature Detection 패턴
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 기준 (변경 시)

위 문서들에 기재된 규칙을 모두 숙지하고 준수한다.

## 4) 완료 조건(Definition of Done)

- [x] `app_portfolio_backtest.py`에서 `_compute_bands_for_signal`, `_find_asset_config`, prev_close shift 기반 OHLC% 계산, `realized + unrealized` 합산, `_render_contribution_section_legacy`, `has_pnl_cols` 분기가 모두 제거되었다.
- [x] `app_single_backtest.py`에서 prev_close shift 기반 OHLC% 계산이 제거되었다.
- [x] `signal_{asset_id}.csv` (포트폴리오)와 `signal.csv` (단일)에 `open_pct`, `high_pct`, `low_pct`, `close_pct` 4컬럼이 저장된다 (반올림: `ROUND_PERCENT`).
- [x] `signal_{asset_id}.csv`에 buffer_zone 전략 자산만 `upper_band`, `lower_band` 컬럼이 저장된다 (반올림: `ROUND_PRICE`). buy_and_hold 자산은 해당 컬럼이 존재하지 않는다 (Feature Detection 일관 적용).
- [x] `equity.csv` (포트폴리오)에 `{asset_id}_contribution` 컬럼이 저장된다 (반올림: `ROUND_CAPITAL`, 정수 캐스팅).
- [x] `portfolio_types.py`의 `PortfolioResult` docstring과 `src/qbt/backtest/CLAUDE.md`의 equity_df / signal_df 컬럼 명세가 신규 컬럼을 반영한다.
- [x] 기존 `calculate_change_pct` 호출/테스트가 신규 헬퍼(`add_ohlc_change_pct`)로 교체되었다.
- [x] 회귀/신규 테스트 추가 (csv_export `add_ohlc_change_pct`/`add_buffer_zone_bands` 단위 테스트, portfolio_data `_contribution` 컬럼 컨트랙트 테스트).
- [x] `poetry run python validate_project.py` 통과 (passed=927, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (README.md 변경 없음; src/qbt/backtest/CLAUDE.md 갱신; portfolio_types.py docstring 갱신)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

비즈니스 로직 계층:

- `src/qbt/backtest/csv_export.py` — OHLC 4종 전일대비% 헬퍼 추가 (`add_ohlc_change_pct(df) -> df`). 기존 `calculate_change_pct` 폐기 또는 close 전용 thin wrapper 결정.
- `src/qbt/backtest/engines/portfolio_data.py` — `_attach_holding_view_columns()`에 `{asset_id}_contribution = realized_pnl + unrealized_pnl` 컬럼 추가. 또는 별도 헬퍼로 분리.
- `src/qbt/backtest/portfolio_types.py` — `PortfolioResult.equity_df` 컬럼 명세 docstring 업데이트.

CLI 스크립트(저장 단계):

- `scripts/backtest/run_single_backtest.py` — `_save_signal_csv()`에서 신규 OHLC% 헬퍼 사용, 4컬럼 반올림 등록.
- `scripts/backtest/run_portfolio_backtest.py` — `_save_portfolio_results()`에서:
  1. 시그널 CSV 저장 직전에 OHLC 4종 % 컬럼 추가 + buffer_zone 자산에 한해 `upper_band`/`lower_band` 컬럼 추가 (전략 파라미터는 `PortfolioConfig.asset_slots`에서 직접 조회).
  2. equity CSV 반올림 사전에 `{asset_id}_contribution`을 `ROUND_CAPITAL` + int 캐스팅 대상에 포함.

CLI 스크립트(대시보드):

- `scripts/backtest/app_single_backtest.py` — `_build_candle_data()` 에서 `prev_close.shift` 및 % 계산 제거, 컬럼 직접 읽기.
- `scripts/backtest/app_portfolio_backtest.py`:
  - `_compute_bands_for_signal`, `_find_asset_config` 삭제.
  - `_build_portfolio_candle_data()` % 계산 제거.
  - `_render_signal_chart()`에서 `display_df = signal_df` 단순화 + 자산 전략 분기 제거.
  - `_render_contribution_section()` 합산 로직 제거 (`{asset_id}_contribution` 컬럼 직접 사용), `has_pnl_cols` 분기 + `_render_contribution_section_legacy` 함수 완전 삭제.

테스트:

- `tests/qbt/backtest/test_csv_export.py` (신규/수정) — OHLC 전일대비% 헬퍼 단위 테스트.
- `tests/qbt/backtest/test_portfolio_data.py` (또는 동등 위치) — `{asset_id}_contribution` 파생 컬럼 단위 테스트.
- 기존 `calculate_change_pct` 사용 테스트 시그니처 정리.

문서:

- `src/qbt/backtest/CLAUDE.md` — `csv_export.py` 함수 목록, `equity_df` 파생 뷰 컬럼, signal CSV 저장 컬럼 설명 갱신.
- `README.md`: **변경 없음**.

### 데이터/결과 영향

- `signal.csv`(단일): 기존 `change_pct` 컬럼명/계산이 OHLC 4종으로 확장 또는 대체됨. 사용자 재실행 필수.
- `signal_{asset_id}.csv`(포트폴리오): OHLC 4종 % 컬럼 신규 추가, buffer_zone 자산은 `upper_band`/`lower_band` 신규 추가. 사용자 재실행 필수.
- `equity.csv`(포트폴리오): `{asset_id}_contribution` 컬럼 신규 추가. 사용자 재실행 필수.
- 비즈니스 로직 수치 결과(에쿼티, 거래 손익, MDD, CAGR 등)는 일체 변경되지 않는다 (저장 직전 파생 컬럼 추가만).
- legacy fallback 경로(value 기반 기여도)가 사라지므로, 구버전 결과 폴더로는 contribution 섹션이 동작하지 않는다 → 사용자 재실행 전제.

## 6) 단계별 계획(Phases)

### Phase 1 — 비즈니스 로직 헬퍼 추가 + 기존 호출부 정리

**작업 내용**:

- [x] `src/qbt/backtest/csv_export.py`에 OHLC 4종 전일대비% 헬퍼 추가
  - 시그니처: `add_ohlc_change_pct(df: pd.DataFrame) -> pd.DataFrame` (복사본 반환, `open_pct`/`high_pct`/`low_pct`/`close_pct` 4컬럼 추가)
  - 기존 `calculate_change_pct(df, close_col)` 폐기. `add_buffer_zone_bands(df, ma_col, buy_pct, sell_pct) -> pd.DataFrame` 도메인 헬퍼도 함께 추가
  - 상수 노출: `OHLC_CHANGE_PCT_COLUMNS`, `BUFFER_BAND_COLUMNS`
  - 데이터 불변성: 원본 DataFrame 변경 금지, 복사본 사용 확인
  - 의존 방향 유지: `csv_export.py`는 `analysis.py`를 import하지 않음
- [x] `src/qbt/backtest/engines/portfolio_data.py`의 `_attach_holding_view_columns()`에 `{asset_id}_contribution` 계산 추가
  - 식: `equity_df[f"{asset_id}_contribution"] = equity_df[f"{asset_id}_realized_pnl"] + equity_df[f"{asset_id}_unrealized_pnl"]`
  - 컬럼 부재 시: RuntimeError("내부 불변조건 위반") 발생 (portfolio_engine이 항상 채워줌)
- [x] `src/qbt/backtest/portfolio_types.py`의 `PortfolioResult.equity_df` docstring에 `{asset_id}_contribution` 추가
- [x] 단위 테스트 추가/수정:
  - `add_ohlc_change_pct` 7개 케이스 (4컬럼 추가, 첫행 NaN, close_pct 산식, OHL 산식, 빈 DF, 누락 컬럼 ValueError, 원본 불변성)
  - `add_buffer_zone_bands` 4개 케이스 (산식, 컬럼 존재, 누락 ma_col ValueError, 원본 불변성)
  - `test_portfolio_backtest_scenarios.py`에 `test_contribution_column_equals_realized_plus_unrealized` 추가

### Phase 2 — run_*.py 저장 단계 위임 적용

**작업 내용**:

- [x] `scripts/backtest/run_single_backtest.py::_save_signal_csv()`
  - 기존 `signal_export["change_pct"] = calculate_change_pct(signal_export)` → `add_ohlc_change_pct(result.signal_df)` 호출로 교체
  - `signal_round`에 `OHLC_CHANGE_PCT_COLUMNS` 4컬럼 모두 `ROUND_PERCENT` 등록
- [x] `scripts/backtest/run_portfolio_backtest.py::_save_portfolio_results()` (signal 저장 블록)
  - 자산별 시그널 CSV 저장 직전:
    1. `add_ohlc_change_pct`로 % 컬럼 추가 (반올림 등록 포함)
    2. 해당 자산 슬롯이 `strategy_id == "buffer_zone"`이면 `result.config.asset_slots`에서 슬롯 dict 조회 후 `add_buffer_zone_bands(signal_export, ma_col, slot.buy_buffer_zone_pct, slot.sell_buffer_zone_pct)` 호출
    3. `signal_round`에 `BUFFER_BAND_COLUMNS`를 `ROUND_PRICE`로 등록
  - 산식은 `add_buffer_zone_bands` 도메인 헬퍼에 캡슐화. CLI는 산식을 직접 쓰지 않음.
- [x] `scripts/backtest/run_portfolio_backtest.py::_save_portfolio_results()` (equity 저장 블록)
  - `equity_round` 구성 루프에 `_contribution` suffix 분기 추가 → `ROUND_CAPITAL`
  - int 캐스팅 루프에 `_contribution` suffix 포함

### Phase 3 — 대시보드 정리 (도메인 연산 제거)

**작업 내용**:

- [x] `scripts/backtest/app_single_backtest.py::_build_candle_data()`
  - `prev_close = signal_df[COL_CLOSE].shift(1)` 및 OHLC 4종 % 산식 제거
  - `signal_df`의 4종 % 컬럼을 numpy 배열로 미리 추출 후 인덱스 접근 (정적 타입 체커 완전 호환, type ignore 미사용)
- [x] `scripts/backtest/app_portfolio_backtest.py`
  - `_compute_bands_for_signal`, `_find_asset_config` 함수 삭제
  - `_render_signal_chart()`에서 buffer params 조회/분기 코드 삭제 → `signal_df`를 직접 사용 (밴드 컬럼은 이미 CSV에 존재)
  - `_render_signal_chart()` 시그니처에서 `summary` 인자 제거
  - `_build_portfolio_candle_data()`의 `prev_close.shift` + % 산식 제거 (numpy 배열 인덱스 방식)
  - `_render_contribution_section()`:
    - `has_pnl_cols` 분기 제거, `_render_contribution_section_legacy` 호출 제거
    - `df[col] = realized + unrealized` 합산 라인 제거 → `equity_df[f"{aid}_contribution"]`을 직접 사용
    - 컬럼 부재 시 사용자에게 재실행 안내 (`st.error`)
  - `_render_contribution_section_legacy()` 함수 완전 삭제
  - 분기별 `resample("QE").last().diff()`는 시각화 변환이므로 유지

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 갱신
  - `csv_export.py` 함수 목록에 `add_ohlc_change_pct`/`add_buffer_zone_bands` 추가, `calculate_change_pct` 항목 제거
  - `OHLC_CHANGE_PCT_COLUMNS`/`BUFFER_BAND_COLUMNS` 상수 노출 명시
  - `PortfolioResult.equity_df` 파생 뷰 컬럼 명세에 `{asset_id}_contribution` 추가
  - 대시보드 섹션의 customValues 설명 갱신 (전일대비% 4종 컬럼이 CSV에서 직접 온다는 점 명시)
  - signal CSV 컬럼 설명 (`upper_band`/`lower_band`가 buffer_zone 자산에 한해 포함됨)
- [x] `scripts/backtest/run_*.py` 도크스트링 점검 (출력 컬럼 변경 반영)
- [x] README.md 변경 불필요 확인
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=927, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 대시보드 도메인 연산을 run_*.py 저장 단계로 위임 (밴드/기여도/OHLC%)
2. 백테스트 / signal CSV에 upper/lower 밴드 + OHLC 전일대비% 4종 사전 계산
3. 백테스트 / 포트폴리오 equity_df에 자산별 contribution 컬럼 추가 + legacy fallback 제거
4. 백테스트 / app_*.py 도메인 로직 제거하고 csv_export/portfolio_data 헬퍼로 이관
5. 백테스트 / CLI 계층 도메인 로직 분리 원칙 회복 (밴드/기여도/전일대비% 위임)

## 7) 리스크(Risks)

- **리스크 1**: 사용자가 plan 진행 중 구버전 결과 폴더로 대시보드를 실행하면 신규 컬럼 부재로 KeyError 발생 가능.
  - **완화**: 사용자에게 "스크립트 전부 재실행 예정"을 이미 확인받음. 추가로 app 측 로딩 단계에서 명시적인 ValueError("...재실행하세요") 메시지를 추가하는 옵션 검토.
- **리스크 2**: `calculate_change_pct` 시그니처 변경 시 기존 호출부(타 스크립트/테스트) 누락.
  - **완화**: Grep으로 전체 호출부 추적 후 일괄 정리, 마지막 Phase의 `validate_project.py`로 회귀 검증.
- **리스크 3**: `_attach_holding_view_columns`에 contribution 추가 시 PnL 컬럼이 없는 입력(이론적으로만 가능)이 들어오면 RuntimeError 발생.
  - **완화**: portfolio_engine에서 항상 PnL 컬럼이 채워지는지 확인 후, 불변조건으로 명시 (CLAUDE.md "내부 불변조건 위반" 규칙).
- **리스크 4**: `signal_round` 등록 누락 시 새 컬럼이 반올림 없이 저장되어 CSV 가독성 저하.
  - **완화**: Phase 2 작성 시 반올림 등록을 체크리스트에 명시, 테스트로 컬럼 존재/타입 검증.
- **리스크 5**: buy_and_hold 자산의 signal CSV에 `upper_band`/`lower_band` 컬럼이 없는 경우 vs NaN으로 채워진 경우 — 대시보드 컬럼 존재 검사가 일관되어야 함.
  - **완화**: "buffer_zone 자산에만 컬럼 추가, buy_and_hold는 컬럼 자체 없음" 정책으로 통일하고 app 측은 `"upper_band" in df.columns`로 분기.

## 8) 메모(Notes)

- 사용자 요청: A 그룹(밴드, 기여도) + B 그룹(OHLC 전일대비%) 동시 진행. fallback 미고려, 스크립트 전부 재실행 예정.
- 시각화 변환 항목(C 그룹: pnl_pct*100, cash_weight, 도넛 잔여비중, 분기 resample, pivot_table)은 명시적으로 유지.
- `_render_rebalancing_history_section()`의 빈도/편차 산술도 도메인 통계에 가깝지만 본 plan 범위 외(별도 plan 후보).

### 진행 로그 (KST)

- 2026-04-14 12:00: Draft 생성 (사용자 확인 요청: A+B 그룹 동시 진행, fallback 제거)
- 2026-04-14 12:15: 사용자 추천안 승인 (1번 A: change_pct → 4컬럼 교체 / 2번 A: buffer_zone 자산만 밴드 컬럼 추가). 상태 In Progress.
- 2026-04-14 12:30: Phase 1 완료 — `add_ohlc_change_pct`/`add_buffer_zone_bands` 헬퍼 추가, `_attach_holding_view_columns`에 `_contribution` 컬럼, 단위 테스트 11개 추가.
- 2026-04-14 12:50: Phase 2 완료 — `run_single_backtest._save_signal_csv()`/`run_portfolio_backtest._save_portfolio_results()` 위임 적용, equity CSV `_contribution` 반올림 등록.
- 2026-04-14 13:10: Phase 3 완료 — 두 대시보드의 도메인 연산 제거, `_compute_bands_for_signal`/`_find_asset_config`/`_render_contribution_section_legacy` 삭제. `summary` 인자 제거.
- 2026-04-14 13:25: 마지막 Phase — `src/qbt/backtest/CLAUDE.md` 갱신, black 적용, validate_project.py 통과 (passed=927, failed=0, skipped=0).
- 2026-04-14 13:30: 사용자 피드백 — `# type: ignore` 사용 금지. 4종 % 컬럼을 numpy 배열로 미리 추출해 인덱스 접근하는 방식으로 근본 해결. 재검증 통과 (passed=927). 상태 Done.

---
