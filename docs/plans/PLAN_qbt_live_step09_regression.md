# Implementation Plan: QBT Live - Step 9 회귀 검증

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 13:55
**관련 문서**: 설계서 4.4, TODO Step 9

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: 과거 1 년 구간에서 `run_daily` 를 순차 호출한 결과가 `run_portfolio_backtest` 와 일치하는지 검증
- [x] 목표 2: T-9.1 (equity < 1원), T-9.2 (positions 정수 일치), T-9.3 (cash < 1원) 통과

## 2) 비목표

- run_daily 자체의 로직 수정 (Step 7 에서 완료)
- 실제 GitHub Actions 실행 (Step 11)

## 3) 배경/맥락

### 동기

- live 의 `run_daily` 가 QBT 백테스트 엔진의 1 iteration 과 완전히 동등함을 증명해야 한다. 이 동등성이 회귀 검증의 기준이다.
- 과거 1 년 데이터로 반복 실행하며 매일 model equity / positions / cash 를 비교하면 경로 독립성(Path independence) 이 보장된다.

### 설계 결정

#### D1. 데이터 소스 — **`storage/stock/*.csv` 실파일 사용**

- 테스트 환경에서 `storage/stock/SPY_max.csv`, `QQQ_max.csv`, `SSO_max.csv`, `QLD_max.csv`, `GLD_max.csv`, `TLT_max.csv` 6 종이 이미 존재함을 확인.
- `load_stock_data` 로 로드 후 최근 1 년 구간만 슬라이싱.
- 테스트는 이 파일들을 읽기 전용으로 사용하므로 격리 불필요. 단 파일 미존재 시 `pytest.skip` 처리 가능.

#### D2. 비교 기준 — **`run_portfolio_backtest` 의 equity_df 와 포지션**

- QBT `run_portfolio_backtest(_CONFIG_Q2_2XS, start_date=1년전)` 실행 → equity_df, per_asset, shared_cash 를 "기준값" 으로 확보
- live `run_daily` 를 동일 구간에 대해 일별 순차 호출 → 매일 `DailyResult` 에서 equity/positions/cash 추출
- 비교 허용 오차: `pytest.approx(abs=1.0)` (equity/cash), 정수 일치 (positions)

#### D3. 테스트 속도

- 과거 1 년 ≈ 252 거래일. 매일 run_daily 호출 + QBT 전체 백테스트 = 수 초 예상
- pytest 수행 시간 30 초 이내 목표. 느리면 3 개월로 축소.

#### D4. 테스트 구조

- `tests/test_regression.py` 가 아니라 **`live/tests/test_regression.py`** 에 배치 (live 전용 회귀)
- 실제 CSV 파일 존재 확인 후 `pytest.skip` 으로 누락 시 graceful

## 4) DoD

- [x] `live/tests/test_regression.py` 작성
- [x] 회귀 테스트 3 개 (T-9.1, T-9.2, T-9.3) 통과
- [x] 파일 미존재 시 `pytest.skip` 으로 fallback (CI 환경 대응)
- [x] black + validate_project 통과 (skipped 는 허용되지 않으나 CSV 가 실제로 있다면 통과해야 함)
- [x] TODO Step 9 체크박스 체크
- [x] plan Done

## 5) 변경 범위

### 신규

- `live/tests/test_regression.py`

### 수정

- `docs/TODO_QBT_LIVE.md`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 설계

- [x] `live/tests/test_regression.py` 구현:
  - `@pytest.fixture` CSV 파일 6종 존재 확인, 없으면 skip
  - Helper: `_build_market_bundle_from_portfolio(config, start_date)` — QBT 내부 `_load_portfolio_data_with_common_period` 과 동일한 로직으로 자산별 signal_df/trade_df 준비
  - Helper: `_run_live_iteratively(state, bundle, trade_dates)` — 일별 `run_daily` 순차 호출, 매일 결과 수집
  - T-9.1: 매일 model_equity 차이 < 1.0 (pytest.approx abs=1.0)
  - T-9.2: 매일 positions (model_shares) 정수 일치
  - T-9.3: 매일 cash (shared_cash_model) 차이 < 1.0

### Phase 1 — 구현 및 디버깅

- [x] 테스트 실행
- [x] 불일치 시 run_daily 의 로직 버그 수정 (Step 7 보강)
  - 가능한 이슈: is_first_trading_day_of_month 판정 시 트레이드일 리스트 차이 / BufferZoneStrategy 상태 복원 누락 / actual 축 혼입 등

### Phase 2 — 문서 동기화

- [x] TODO Step 9 체크박스

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=684, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / 회귀 검증 — run_daily vs run_portfolio_backtest (Step 9)`
2. `live / test_regression — 1년 구간 equity/positions/cash 일치`
3. `live / Step 9 경로 독립성 회귀 테스트`
4. `live / run_daily 동등성 검증`
5. `live / T-9.1~9.3 과거 1년 회귀`

## 7) 리스크

- **불일치 발견 시 run_daily 수정 범위 증가**: 설계서 4.4 가 이를 예상하므로 Step 7 보강이 정상 경로.
- **CSV 없는 환경**: pytest.skip 으로 graceful.
- **테스트 속도**: 1 년이 느리면 3 개월로 축소.

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 13:55: 계획서 작성
