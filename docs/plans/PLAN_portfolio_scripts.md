# Implementation Plan: 포트폴리오 백테스트 CLI 스크립트 구현

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

**작성일**: 2026-03-17 22:30
**마지막 업데이트**: 2026-03-17 23:59
**관련 범위**: backtest, scripts
**관련 문서**: docs/PLAN_portfolio_experiment.md, docs/plans/PLAN_portfolio_engine.md, docs/tranche_design.md, docs/strategy_validation_report.md

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

- [ ] `src/qbt/backtest/portfolio_configs.py` 구현 — 7가지 실험(A-1~A-3, B-1~B-3, C-1) `PortfolioConfig` 정의 및 `get_portfolio_config()` 제공
- [ ] `scripts/backtest/run_portfolio_backtest.py` CLI 스크립트 구현 — `--experiment` 인자로 실험 선택, 결과 파일 저장
- [ ] `tests/test_portfolio_configs.py` 핵심 계약 테스트 고정
- [ ] `src/qbt/backtest/CLAUDE.md` — `portfolio_configs.py` 모듈 설명 추가
- [ ] `scripts/CLAUDE.md` — `run_portfolio_backtest.py` 스크립트 설명 추가

## 2) 비목표(Non-Goals)

- 포트폴리오 비교 대시보드 (`app_portfolio_backtest.py`) → **계획서 3 (PLAN_portfolio_dashboard.md)**
- `portfolio_strategy.py` / `portfolio_types.py` 변경 없음 (계획서 1에서 완료)
- `common_constants.py` 변경 없음 (`PORTFOLIO_RESULTS_DIR` 이미 추가됨)
- 파라미터 최적화 / WFO → 해당 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`PLAN_portfolio_engine.md`(계획서 1)에서 포트폴리오 백테스트 엔진(`portfolio_strategy.py`, `portfolio_types.py`)과 `PORTFOLIO_RESULTS_DIR` 상수를 구현 완료했다. 엔진은 완성되었으나 다음이 없어 실제 실험 데이터를 생성할 수 없다:

1. 7가지 실험에 대한 `PortfolioConfig` 정의 (`portfolio_configs.py`)
2. 실험을 실행하고 결과를 저장하는 CLI 스크립트 (`run_portfolio_backtest.py`)

`PLAN_portfolio_experiment.md`에서 정의한 7가지 실험(A/B/C 시리즈)을 실행할 수 있게 되면, 포트폴리오 분산·레버리지 효과 분석을 위한 실증 데이터가 확보된다.

### 7가지 실험 설정 (PLAN_portfolio_experiment.md §3 기준)

| 실험 | experiment_name | QQQ | TQQQ | SPY | GLD | 현금 버퍼 | 근거 |
|---|---|---|---|---|---|---|---|
| **A-1** | portfolio_a1 | 25% | — | 25% | 50% | 0% | 역변동성 근사(참고) |
| **A-2** | portfolio_a2 | 30% | — | 30% | 40% | 0% | 60:40 전통 배분(기본) |
| **A-3** | portfolio_a3 | 35% | — | 35% | 30% | 0% | 공격적(민감도 확인) |
| **B-1** | portfolio_b1 | 19.5% | 7% | 19.5% | 40% | 14% | TQQQ 소량, 현금 확보 |
| **B-2** | portfolio_b2 | 12% | 12% | 12% | 40% | 24% | TQQQ 증가, 현금 확보 |
| **B-3** | portfolio_b3 | 15% | 15% | 30% | 40% | 0% | 현금 없이 전액 투자 |
| **C-1** | portfolio_c1 | 50% | 50% | — | — | 0% | 레버리지만, 분산 없음 |

### 시그널 소스 규칙 (PLAN_portfolio_experiment.md §2.3, §4.2)

| 자산 | signal_data_path | trade_data_path | 비고 |
|---|---|---|---|
| QQQ | `QQQ_DATA_PATH` | `QQQ_DATA_PATH` | 동일 |
| TQQQ | **`QQQ_DATA_PATH` (공유)** | `TQQQ_SYNTHETIC_DATA_PATH` | QQQ 시그널 사용 |
| SPY | `SPY_DATA_PATH` | `SPY_DATA_PATH` | 독립 시그널 |
| GLD | `GLD_DATA_PATH` | `GLD_DATA_PATH` | 독립 시그널 |

QQQ와 TQQQ는 `signal_data_path`가 동일(`QQQ_DATA_PATH`)하므로 엔진이 항상 동시 매수/매도를 발생시킨다.

### 전 자산 공통 4P 파라미터 (PLAN_portfolio_experiment.md §4.1)

| 파라미터 | 값 |
|---|---|
| `ma_window` | 200 |
| `buy_buffer_zone_pct` | 0.03 |
| `sell_buffer_zone_pct` | 0.05 |
| `hold_days` | 3 |
| `ma_type` | "ema" |
| `rebalance_threshold_rate` | 0.20 |
| `total_capital` | 10,000,000 |

### 결과 저장 구조

```
storage/results/portfolio/
├── portfolio_a1/
│   ├── equity.csv         # 합산 에쿼티 (Date, equity, cash, drawdown_pct, {asset_id}_value/weight/signal, rebalanced)
│   ├── trades.csv         # 전 자산 거래 (+ asset_id, trade_type 컬럼)
│   ├── summary.json       # 전체 + 자산별 요약 지표 + 설정 파라미터
│   ├── signal_qqq.csv     # QQQ 시그널 데이터 (OHLCV + EMA-200 + 밴드 + 전일대비%)
│   ├── signal_spy.csv
│   └── signal_gld.csv
...
└── portfolio_c1/
    ├── equity.csv
    ├── trades.csv
    ├── summary.json
    ├── signal_qqq.csv     # C-1: TQQQ signal_data_path = QQQ → QQQ 기반
    └── signal_tqqq.csv    # TQQQ의 signal_df는 QQQ 데이터(EMA-200) 포함
```

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `portfolio_configs.py` — `PORTFOLIO_CONFIGS`(7개) + `get_portfolio_config()` 구현 완료
- [x] `run_portfolio_backtest.py` — `--experiment` 인자, 결과 파일 저장 구현 완료
- [x] `tests/test_portfolio_configs.py` — 핵심 계약 테스트 작성 및 전체 통과
- [x] `src/qbt/backtest/CLAUDE.md` — `portfolio_configs.py` 모듈 설명 추가 완료
- [x] `scripts/CLAUDE.md` — `run_portfolio_backtest.py` 스크립트 설명 추가 완료
- [x] `poetry run python validate_project.py` 통과 (passed=374, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일 (예상)

신규:

- `src/qbt/backtest/portfolio_configs.py` — `PortfolioConfig` 7개 + `get_portfolio_config()`
- `scripts/backtest/run_portfolio_backtest.py` — CLI 스크립트 (실행 + 저장 + 출력)
- `tests/test_portfolio_configs.py` — 핵심 계약 테스트

수정:

- `src/qbt/backtest/CLAUDE.md` — `portfolio_configs.py` 모듈 설명 추가
- `scripts/CLAUDE.md` — `run_portfolio_backtest.py` 스크립트 설명 추가

변경 없음:

- `src/qbt/backtest/portfolio_strategy.py` (import만 사용)
- `src/qbt/backtest/portfolio_types.py` (import만 사용)
- `src/qbt/common_constants.py` (`PORTFOLIO_RESULTS_DIR` 이미 추가됨)
- `tests/test_portfolio_strategy.py` (기존 유지)
- `tests/conftest.py` (불필요: 테스트에서 result_dir=tmp_path 직접 사용, 파일 저장 없음)

### 데이터/결과 영향

- `storage/results/portfolio/` 디렉토리는 CLI 스크립트 실행 시 자동 생성됨 (AI 모델은 직접 실행 불가)
- 기존 `storage/results/backtest/`, `storage/results/tqqq/` 결과 변경 없음

---

## 6) 단계별 계획(Phases)

### Phase 0 — 핵심 계약 테스트 (레드)

`portfolio_configs.py` 미구현 상태에서 계약/불변조건을 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `tests/test_portfolio_configs.py` 생성

  **테스트 1: PORTFOLIO_CONFIGS 개수** (`test_portfolio_configs_count`)

  ```
  When:  PORTFOLIO_CONFIGS를 가져옴
  Then:  len(PORTFOLIO_CONFIGS) == 7
  ```

  **테스트 2: target_weight 합 ≤ 1.0** (`test_all_portfolio_configs_target_weights_valid`)

  ```
  Given: PORTFOLIO_CONFIGS의 각 config
  When:  target_weight 합산
  Then:  모든 config에서 sum(slot.target_weight for slot in config.asset_slots) <= 1.0
  ```

  **테스트 3: asset_id 중복 없음** (`test_all_portfolio_configs_no_duplicate_asset_ids`)

  ```
  Given: PORTFOLIO_CONFIGS의 각 config
  When:  asset_id 목록을 set()으로 변환
  Then:  len(set) == len(list) (중복 없음)
  ```

  **테스트 4: A시리즈에 TQQQ 없음** (`test_a_series_no_tqqq`)

  ```
  Given: portfolio_a1, portfolio_a2, portfolio_a3 설정
  When:  asset_id 목록 확인
  Then:  "tqqq" not in asset_ids (각 config)
  ```

  **테스트 5: B/C시리즈 TQQQ 시그널 = QQQ** (`test_b_c_series_tqqq_signal_is_qqq`)

  ```
  Given: portfolio_b1, portfolio_b2, portfolio_b3, portfolio_c1 설정
  When:  TQQQ AssetSlotConfig의 signal_data_path 확인
  Then:  tqqq_slot.signal_data_path == QQQ_DATA_PATH (각 config)
  ```

  **테스트 6: C-1 전액 투자** (`test_c1_full_investment`)

  ```
  Given: portfolio_c1 설정 (QQQ 50% + TQQQ 50%)
  When:  target_weight 합산
  Then:  sum == pytest.approx(1.0, abs=1e-9)
         asset_ids == {"qqq", "tqqq"}
  ```

  **테스트 7: B-1 현금 버퍼** (`test_b1_cash_buffer`)

  ```
  Given: portfolio_b1 설정 (QQQ 19.5% + TQQQ 7% + SPY 19.5% + GLD 40%)
  When:  target_weight 합산
  Then:  sum == pytest.approx(0.86, abs=1e-9) (현금 14% 자동 확보)
  ```

  **테스트 8: get_portfolio_config 정상 조회** (`test_get_portfolio_config_returns_correct`)

  ```
  When:  get_portfolio_config("portfolio_a2") 호출
  Then:  반환된 config.experiment_name == "portfolio_a2"
         반환된 config.display_name이 비어있지 않음
  ```

  **테스트 9: get_portfolio_config 없는 이름** (`test_get_portfolio_config_invalid_name`)

  ```
  When:  get_portfolio_config("nonexistent") 호출
  Then:  ValueError 발생 (match="nonexistent")
  ```

---

### Phase 1 — 구현 (그린)

Phase 0 테스트를 모두 통과시킨다.

**작업 내용**:

- [x] `src/qbt/backtest/portfolio_configs.py` 생성

  **임포트**:

  ```python
  from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
  from qbt.backtest.portfolio_strategy import run_portfolio_backtest
  from qbt.common_constants import (
      GLD_DATA_PATH,
      PORTFOLIO_RESULTS_DIR,
      QQQ_DATA_PATH,
      SPY_DATA_PATH,
      TQQQ_SYNTHETIC_DATA_PATH,
  )
  ```

  **PORTFOLIO_CONFIGS 정의** — 7개 `PortfolioConfig` 인스턴스:

  ```python
  # 전 자산 공통 4P 파라미터 (PLAN_portfolio_experiment.md §4.1)
  _DEFAULT_MA_WINDOW = 200
  _DEFAULT_BUY_BUFFER = 0.03
  _DEFAULT_SELL_BUFFER = 0.05
  _DEFAULT_HOLD_DAYS = 3
  _DEFAULT_MA_TYPE = "ema"
  _DEFAULT_REBALANCE_THRESHOLD = 0.20
  _DEFAULT_TOTAL_CAPITAL = 10_000_000.0

  # A-1: 역변동성 근사 (참고용)
  # A-2: 60:40 전통 배분 (기본, 사전 결정)
  # A-3: 공격적 구성 (민감도 확인)
  # B-1: TQQQ 소량(7%) + 현금 14%
  # B-2: TQQQ 증가(12%) + 현금 24%
  # B-3: 현금 없이 전액 투자 (target_weight 합 = 1.0)
  # C-1: QQQ+TQQQ만 (분산 없는 레버리지 기준선)

  PORTFOLIO_CONFIGS: list[PortfolioConfig] = [...]
  ```

  각 config의 result_dir은 `PORTFOLIO_RESULTS_DIR / "portfolio_a1"` 형태로 직접 지정.

  **공개 함수**:

  ```python
  def get_portfolio_config(experiment_name: str) -> PortfolioConfig:
      """실험명으로 PortfolioConfig를 조회한다.

      Args:
          experiment_name: 실험명 (예: "portfolio_a2")

      Returns:
          해당 PortfolioConfig

      Raises:
          ValueError: 실험명이 PORTFOLIO_CONFIGS에 없는 경우
      """
  ```

  > 주의: `create_portfolio_runner()` 함수는 제공하지 않는다. CLI 스크립트가 `run_portfolio_backtest(config)` 직접 호출하는 방식을 사용한다 (`run_split_backtest.py` 패턴 동일).

- [x] `scripts/backtest/run_portfolio_backtest.py` 생성

  **모듈 docstring** — 실행 명령어 예시 포함:

  ```
  poetry run python scripts/backtest/run_portfolio_backtest.py
  poetry run python scripts/backtest/run_portfolio_backtest.py --experiment portfolio_a2
  poetry run python scripts/backtest/run_portfolio_backtest.py --experiment portfolio_c1
  ```

  **로컬 상수**:

  ```python
  # 반올림 규칙 (루트 CLAUDE.md §출력 데이터 반올림 규칙 참고)
  _PRICE_ROUND = 6    # 가격 (OHLCV, MA, 밴드)
  _EQUITY_ROUND = 0   # 자본금 (equity, cash, {asset_id}_value)
  _PCT_ROUND = 2      # 백분율 (drawdown_pct, change_pct, cagr, mdd 등)
  _RATIO_ROUND = 4    # 비율 0~1 ({asset_id}_weight)
  _PNL_PCT_ROUND = 4  # pnl_pct
  ```

  **내부 저장 함수** (`_save_portfolio_results(result: PortfolioResult) -> None`):

  ```
  1. result.config.result_dir 생성 (parents=True, exist_ok=True)

  2. equity.csv 저장
     - equity_df 복사 후 반올림:
       - equity, cash: int (0자리)
       - drawdown_pct: 2자리
       - {asset_id}_value: int (0자리)
       - {asset_id}_weight: 4자리
       - {asset_id}_signal: str (변환 없음)
       - rebalanced: bool (변환 없음)

  3. trades.csv 저장
     - trades_df 복사 후 반올림:
       - entry_price, exit_price: 6자리
       - pnl: int (0자리)
       - pnl_pct: 4자리
       - holding_days 컬럼 추가 (exit_date - entry_date).days
       - asset_id, trade_type: str (변환 없음)

  4. signal_{asset_id}.csv 저장 (per_asset별)
     - signal_df 복사 후 반올림:
       - OHLCV (Open/High/Low/Close): 6자리
       - ma_{N} 컬럼: 6자리
       - upper_band, lower_band: 6자리
       - change_pct (pct_change × 100): 2자리 (저장 직전 계산)

  5. summary.json 저장:
     {
       "display_name": result.display_name,
       "portfolio_summary": {
         "initial_capital": int,
         "final_capital": int,
         "total_return_pct": float(2자리),
         "cagr": float(2자리),
         "mdd": float(2자리),
         "calmar": float(2자리),
         "total_trades": int,
         "start_date": str,
         "end_date": str
       },
       "per_asset": [
         {
           "asset_id": str,
           "target_weight": float(4자리),
           "total_trades": int,
           "win_rate": float(2자리)
         }, ...
       ],
       "portfolio_config": result.params_json
     }

  6. meta_manager.save_metadata("portfolio_backtest", metadata) 호출
     metadata:
       - params: result.params_json
       - results_summary: {total_return_pct, cagr, mdd, calmar, total_trades}
       - output_files: {equity_csv, trades_csv, summary_json}
  ```

  **내부 출력 함수** (`_print_summary(result: PortfolioResult) -> None`):

  ```
  - 전체 요약 (기간, 초기/최종 자본, 수익률, CAGR, MDD, Calmar, 총 거래 수)
  - 자산별 성과 테이블 (TableLogger 사용):
    컬럼: 자산, 비중, 거래수, 수익률, CAGR, MDD, Calmar
  ```

  **main() 함수** (`@cli_exception_handler` 데코레이터 적용):

  ```python
  def main() -> int:
      # 1. 인자 파싱
      _CONFIG_MAP = {c.experiment_name: c for c in PORTFOLIO_CONFIGS}
      parser.add_argument(
          "--experiment",
          choices=["all", *_CONFIG_MAP.keys()],
          default="all",
          help="실행할 실험 (기본값: all)",
      )

      # 2. 대상 config 결정 (all → 전체 7개, 개별 → 해당 1개)

      # 3. 실험별 실행
      for config in target_configs:
          result = run_portfolio_backtest(config)
          _print_summary(result)
          _save_portfolio_results(result)

      return 0
  ```

**Validation** (Phase 1):

- [x] `poetry run python validate_project.py --only-tests` 통과 (passed=374, failed=0, skipped=0)

---

### Phase 2 — 문서 업데이트 (그린)

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트

  `portfolio_configs.py` 모듈 항목 추가 (모듈 구성 섹션):

  ```
  ### 10. portfolio_configs.py

  포트폴리오 백테스트 실험 설정을 제공한다.
  PLAN_portfolio_experiment.md에 정의된 7가지 실험(A-1~A-3, B-1~B-3, C-1)을 PortfolioConfig로 구현한다.

  설정 목록:
  - PORTFOLIO_CONFIGS: list[PortfolioConfig] (7개 실험)
    - portfolio_a1: QQQ 25% / SPY 25% / GLD 50% (역변동성 근사, 참고)
    - portfolio_a2: QQQ 30% / SPY 30% / GLD 40% (60:40 전통 배분, 기본)
    - portfolio_a3: QQQ 35% / SPY 35% / GLD 30% (공격적, 민감도)
    - portfolio_b1: QQQ 19.5% / TQQQ 7% / SPY 19.5% / GLD 40% (현금 14%)
    - portfolio_b2: QQQ 12% / TQQQ 12% / SPY 12% / GLD 40% (현금 24%)
    - portfolio_b3: QQQ 15% / TQQQ 15% / SPY 30% / GLD 40% (전액 투자)
    - portfolio_c1: QQQ 50% / TQQQ 50% (레버리지만, 분산 없음)

  주요 함수:
  - get_portfolio_config(experiment_name): 이름으로 PortfolioConfig 조회. 없으면 ValueError
  ```

- [x] `scripts/CLAUDE.md` 업데이트

  백테스트(backtest/) 섹션에 포트폴리오 실험 항목 추가:

  ```
  - 포트폴리오 실험:
    - run_portfolio_backtest.py: 7가지 포트폴리오 실험 실행 (A/B/C 시리즈)
      - --experiment 인자로 실행 실험 선택 (all / portfolio_a1 ~ portfolio_c1, 기본값: all)
      - 결과: storage/results/portfolio/{experiment_name}/ 디렉토리에
        equity.csv, trades.csv, summary.json, signal_{asset_id}.csv 저장
      - 메타데이터 타입: "portfolio_backtest"
  ```

**Validation** (Phase 2):

- [x] `poetry run python validate_project.py --only-tests` 통과 (passed=374, failed=0, skipped=0)

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=374, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실험 설정 + CLI 스크립트 구현 (A/B/C 7가지 실험)
2. 백테스트 / portfolio_configs.py + run_portfolio_backtest.py 신규 구현
3. 백테스트 / 포트폴리오 7가지 실험 설정 정의 + 결과 저장 CLI 구현
4. 백테스트 / 멀티자산 포트폴리오 실험 실행 스크립트 + 계약 테스트 고정
5. 백테스트 / 포트폴리오 실험 configs + 실행·저장 CLI (계획서 2)

---

## 7) 리스크(Risks)

| 리스크 | 설명 | 완화책 |
|---|---|---|
| B-1/B-2 현금 버퍼 비중 산술 오차 | 19.5%+7%+19.5%+40% = 86.0%을 float으로 표현 시 부동소수점 오차 발생 가능 | `pytest.approx(0.86, abs=1e-9)`으로 검증. 실제 정의 시 소수 그대로 사용 (0.195, 0.07 등) |
| TQQQ signal_csv 내용 혼동 | `signal_tqqq.csv`는 QQQ 데이터(EMA-200 기반)를 포함. 파일명과 내용 불일치로 혼동 가능 | summary.json에 signal_data_path 기록하여 명확화 |
| 7개 실험 전체 실행 시간 | GLD 시작일(2004-11) 이후 ~21년 × 7실험 × 리밸런싱 루프 → 수 분 소요 가능 | 실행 시간 예상 안내 문구 추가 (CLI 출력) |
| 기존 테스트 회귀 | portfolio_configs.py import 시 common_constants.py 경로 상수가 초기화됨 | Phase 1 완료 후 --only-tests 실행으로 즉시 확인 |
| `asset_id` 기반 동적 컬럼 저장 | equity.csv의 `{asset_id}_value/weight/signal` 컬럼은 실험마다 수가 다름 | `PortfolioResult.equity_df` 컬럼 구조를 있는 그대로 저장 (동적 컬럼 처리 루프) |

---

## 8) 메모(Notes)

### 설계 결정 기록

**portfolio_configs.py에 create_portfolio_runner() 미제공**:

`run_portfolio_backtest(config)`는 데이터 로딩부터 결과 반환까지 모든 처리를 내부에서 수행한다. CLI 스크립트에서 직접 `run_portfolio_backtest(config)`를 호출하는 것이 `run_split_backtest.py`와 동일한 패턴이며 불필요한 래퍼 함수를 줄인다.

**signal_{asset_id}.csv에 밴드 포함 여부**:

`PortfolioAssetResult.signal_df`는 `portfolio_strategy.py` 내부에서 `_compute_bands()`가 적용된 데이터를 포함한다 (PLAN_portfolio_engine.md Phase 1 구현). 따라서 저장 시 상단/하단 밴드 컬럼(`upper_band`, `lower_band`)이 포함된다. 대시보드(계획서 3)에서 매매 구간 시각화에 활용한다.

**A시리즈 자산 수 (3개) vs B/C시리즈 (4개)**:

A시리즈는 TQQQ 없이 QQQ+SPY+GLD 3자산. 따라서 signal CSV가 3개, equity_df의 자산별 컬럼도 3세트. 이는 정상이며 CLI에서 `result.per_asset`을 순회하여 동적으로 처리한다.

**계획서 전체 구성 (3개)**:

| 계획서 | 파일명 | 내용 | 상태 |
|---|---|---|---|
| 계획서 1 | PLAN_portfolio_engine.md | 엔진 + 타입 + 상수 | ✅ Done |
| 계획서 2 (현재) | PLAN_portfolio_scripts.md | CLI 스크립트 (7가지 실험 실행 + 결과 저장) | 🟡 Draft |
| 계획서 3 | PLAN_portfolio_dashboard.md | 포트폴리오 비교 대시보드 | 미작성 |

### 진행 로그 (KST)

- 2026-03-17 22:30: 계획서 초안 작성 완료
- 2026-03-17 23:59: 전체 Phase 구현 완료 (passed=374, failed=0, skipped=0) → Done
