# QBT 실행 명령어 레퍼런스

> 이 파일은 QBT 프로젝트 실행 명령어의 **단일 SoT(Source of Truth)** 입니다.
> README.md 등 다른 문서에는 실행 명령어를 기재하지 않으며, 필요 시 이 문서를 참조합니다.
> 관련 규칙: 전역 `~/.claude/CLAUDE.md` 「개인 프로젝트 공통」

---

## 빠른 시작

```bash
# 의존성 설치
poetry install

# 품질 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py
```

---

## 워크플로우 1: 백테스트 전략 분석

이동평균 기반 버퍼존 전략의 성과를 평가합니다.

```bash
# 1. 데이터 다운로드 (전체 종목 일괄)
poetry run python scripts/data/download_data.py
# 또는 특정 종목만
poetry run python scripts/data/download_data.py QQQ

# 2. 단일 전략 검증 + 결과 저장 (선행: 1, TQQQ 합성 — 워크플로우 2 의 3)
# 출력: 콘솔 (버퍼존 vs Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)
# --strategy 인자로 특정 전략만 실행 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_single_backtest.py
poetry run python scripts/backtest/run_single_backtest.py --strategy <strategy_name>

# 3. 포트폴리오 백테스트 (선행: 원본 시세 전부 · 대용 시계열 생성 — 아래 「시세를 다시 받은 뒤 다시 돌리는 순서」 ① · ④)
# 출력: storage/results/portfolio/{experiment_name}/ (equity, trades, summary, signal_{asset_id}, state_log, 매매법이 여럿이면 ledger · netting)
# 실행 직후 정합성 검증 — 위반이 있으면 결과를 저장한 뒤 멈춘다 (ValueError)
poetry run python scripts/backtest/run_portfolio_backtest.py
# --experiment 인자로 특정 실험 선택 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment <experiment_name>

# 3-1. 보완 전략 비중 그리드 — 「Q-2-2XS (100−w)% + 후보 w%」 (선행: 원본 시세 전부 · 대용 시계열 생성 — 아래 「시세를 다시 받은 뒤 다시 돌리는 순서」 ① · ④)
# 출력: storage/results/portfolio_grid/ (grid_runs.csv 실행별 지표, judgment.csv 통과 판정, proxy_gate.csv 대용 검증 — 실험별 결과 폴더는 만들지 않음)
# 실행마다 정합성 검증 — 위반이 있으면 멈춘다. 소요: 병렬로 1 – 2분
poetry run python scripts/backtest/run_supplement_grid.py

# 3-2. 조합 그리드 — Q-2-2XS + HAA + 로테이션, 세 판 (선행: 원본 시세 전부 · 대용 · 장기 대체 시계열 생성 — 아래 「시세를 다시 받은 뒤 다시 돌리는 순서」 ① · ④)
# 출력: storage/results/portfolio_combo_grid/ (combo_runs.csv 실행별 지표, combo_judgment.csv 판정 기준별 지도, combo_alt_check.csv 대체 판 확인 — 실험별 결과 폴더는 만들지 않음)
# 실행마다 정합성 검증 — 위반이 있으면 멈춘다. 소요: 병렬로 2 – 3분
poetry run python scripts/backtest/run_combo_grid.py

# 4. 워크포워드 검증 (선행: 1, TQQQ 합성 — 워크플로우 2 의 3)
# 출력: storage/results/backtest/{전략명}/ (walkforward_*.csv, walkforward_summary.json, 윈도우별 상세 wfo_windows_*/)
# 소요: 수 분 — 그리드 서치라 그리드 범위 · 윈도우 수에 따라 달라진다 (약 6분)
poetry run python scripts/backtest/run_walkforward.py

# --strategy 인자로 특정 전략만 실행 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_walkforward.py --strategy <strategy_name>

# 5. 파라미터 고원 분석 (선행: 1)
poetry run python scripts/backtest/run_param_plateau_all.py
# --experiment 인자로 특정 실험만 실행 가능 (기본값: all, 선택지는 --help)
# 출력: storage/results/backtest/param_plateau/ (피벗 CSV)

# 6. 대시보드 시각화 (선행: 2)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 7. 포트폴리오 비교 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_portfolio_backtest.py

# 8. WFO 결과 시각화 대시보드 (선행: 4)
poetry run streamlit run scripts/backtest/app_walkforward.py

# 9. 파라미터 고원 시각화 대시보드 (선행: 5)
poetry run streamlit run scripts/backtest/app_parameter_stability.py
```

**파라미터 변경**: [src/qbt/backtest/constants.py](../src/qbt/backtest/constants.py)

---

## 워크플로우 2: TQQQ · QLD 레버리지 ETF 시뮬레이션

QQQ로부터 TQQQ · QLD를 시뮬레이션하고 실제 데이터와 비교하여 비용 모델을 검증합니다.

```bash
# 1. 필수 데이터 다운로드 (전체 종목 일괄)
poetry run python scripts/data/download_data.py
# 또는 개별 다운로드
poetry run python scripts/data/download_data.py QQQ
poetry run python scripts/data/download_data.py TQQQ
poetry run python scripts/data/download_data.py QLD

# 2. 일별 비교 데이터 생성 (softplus 동적 스프레드 모델, 두 상품을 함께 만든다)
poetry run python scripts/tqqq/generate_daily_comparison.py
# 출력: storage/results/tqqq/tqqq_daily_comparison.csv · qld_daily_comparison.csv

# 3. 합성 TQQQ 데이터 생성 (워크플로우 1 의 단일 백테스트 · 워크포워드의 TQQQ 전략이 읽는다)
poetry run python scripts/tqqq/generate_synthetic.py
# 출력: storage/stock/TQQQ_synthetic_max.csv
```

### 대시보드 앱 실행

```bash
# 일별 비교 대시보드 (상품과 시가 · 고가 · 저가 · 종가를 골라 본다)
# 선행: 1 → 2
# 필요: storage/results/tqqq/tqqq_daily_comparison.csv · qld_daily_comparison.csv
poetry run streamlit run scripts/tqqq/app_daily_comparison.py
```

### 스프레드 모델 검증 결과 열람 (spread_lab/)

스프레드 모델 파라미터는 확정 상태이며, 결과 열람용 시각화 앱만 제공합니다.

```bash
# 금리-오차 관계 분석 앱 (시각화 전용)
# 필수: storage/results/tqqq/tqqq_daily_comparison.csv
# 필수: storage/results/tqqq/spread_lab/ 하위 결과 CSV (git 추적 — 만드는 스크립트는 저장소에 없다)
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

**파라미터 변경**: [src/qbt/tqqq/constants.py](../src/qbt/tqqq/constants.py)

## 품질 검증 (통합)

```bash
# 전체 검증 (Ruff + PyRight + Pytest) - 권장
poetry run python validate_project.py

# 테스트 + 커버리지만 (Ruff · PyRight 는 돌지 않는다)
poetry run python validate_project.py --cov

# 테스트만 실행
poetry run python validate_project.py --only-tests

# Ruff 린트만 실행
poetry run python validate_project.py --only-lint

# PyRight 타입 체크만 실행
poetry run python validate_project.py --only-pyright
```

## 테스트 (특정 모듈/파일)

```bash
# qbt 특정 모듈만 테스트
poetry run pytest tests/qbt/test_buffer_zone_run.py -v

# 특정 클래스만 테스트
poetry run pytest tests/qbt/test_buffer_zone_run.py::TestRunBufferStrategy -v

# 실패한 테스트만 재실행
poetry run pytest --lf -v

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/qbt/test_xxx.py -s -vv
```

## 코드 포맷

```bash
# 포맷 적용 (마지막 단계에서만)
poetry run black .

# ruff 자동 수정 (예외적 사용)
poetry run ruff check --fix .
```

## 커버리지

```bash
# HTML 리포트 생성 (직접 pytest 사용)
poetry run pytest --cov=src/qbt --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

---

## 시세를 다시 받은 뒤 다시 돌리는 순서

생성 파일과 결과 파일은 만들 때의 시세로 굳은 사본이다. 원본 시세를 다시 받으면 ① 부터, `storage/etc` 의 월별 파일만 고쳤으면 ③ 부터 끝까지 차례로 다시 돌린다 — 일부만 돌리면 같은 결과 폴더에 기준일이 다른 산출물이 섞인다. **단계마다 끝까지 성공한 것을 보고 다음 단계로 간다** — 아래 블록은 실패하면 그 자리에서 멈춘다.

**① 원본 시세** — `storage/stock` 의 `*_max.csv` 중 생성 파일(`*_synthetic_max` · `*_proxy_max`)이 아닌 것 전부. 인자 없는 `download_data.py` 는 `DEFAULT_TICKERS` 만 받는다.

```bash
for f in storage/stock/*_max.csv; do
  case "$f" in *_synthetic_max.csv | *_proxy_max.csv) continue ;; esac
  poetry run python scripts/data/download_data.py "$(basename "$f" _max.csv)" || { echo "[중단] $f 받기 실패"; break; }
done
```

**② `storage/etc` 월별 파일** — 손으로 갱신한다. 열은 `DATE`(yyyy-mm) · `VALUE`(비율), 달마다 한 행, 줄 끝은 기존 행과 같은 CRLF. 편집기로 붙인다 — 파일 끝에 줄바꿈이 없으면 셸 `>>` 는 마지막 행에 이어 붙인다.

- `federal_funds_rate_monthly.csv`: FRED 의 `FEDFUNDS`(월별, %) ÷ 100
- `tqqq_net_expense_ratio_monthly.csv`: ProShares TQQQ Summary Prospectus 의 Net expense ratio(%) ÷ 100 — 설명서 날짜 다음 달부터 그 값
- 시세 끝이 파일 끝보다 `MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF`([src/qbt/tqqq/data_loader.py](../src/qbt/tqqq/data_loader.py))를 넘게 뒤면 두 파일을 읽는 생성 스크립트(③ · ④ 의 장기 대체 · ⑤)가 멈춘다

**③ – ⑥ 생성 · 결과** — 블록의 줄 순서대로 ③ TQQQ 합성(단일 백테스트 · 워크포워드의 TQQQ 전략이 읽는다), ④ 대용 · 장기 대체 시계열(포트폴리오 · 두 그리드가 읽는다)과 대체-실물 비교, ⑤ TQQQ · QLD 일별 비교, ⑥ 결과 러너. 하나가 실패하면 뒤는 돌지 않는다(`set -e` 는 괄호 안 하위 셸에만 걸린다). 블록 안에는 주석을 두지 않는다 — 주석 옵션(`interactivecomments`)이 꺼진 대화형 zsh 는 `#` 줄을 명령으로 읽어 첫 줄에서 멈춘다.

```bash
(
  set -e
  poetry run python scripts/tqqq/generate_synthetic.py

  poetry run python scripts/data/generate_proxy_series.py
  poetry run python scripts/data/generate_long_proxy_series.py
  poetry run python scripts/data/generate_proxy_comparison.py

  poetry run python scripts/tqqq/generate_daily_comparison.py

  poetry run python scripts/backtest/run_single_backtest.py
  poetry run python scripts/backtest/run_walkforward.py
  poetry run python scripts/backtest/run_param_plateau_all.py
  poetry run python scripts/backtest/run_portfolio_backtest.py
  poetry run python scripts/backtest/run_supplement_grid.py
  poetry run python scripts/backtest/run_combo_grid.py
)
```

---

## 데이터 다운로드 옵션

```bash
# 전체 종목 일괄 다운로드 (대상 티커는 scripts/data/download_data.py 의 DEFAULT_TICKERS 참조)
poetry run python scripts/data/download_data.py

# 특정 종목 전체 기간 (특수 문자가 든 티커는 따옴표로 감싼다 — "^SPGSCI" · "GC=F". 파일 이름도 티커 그대로)
poetry run python scripts/data/download_data.py TICKER
```

### 대용 시계열 생성 (실물 ETF 상장 전 구간 채우기)

```bash
# 선행: 대상 · 대용 티커를 위 「특정 종목 전체 기간」으로 하나씩 받는다
#       목록은 scripts/data/generate_proxy_series.py 의 ONE_TO_ONE_PROXIES · VXUS_COMPOSITE_WEIGHTS 참고
#       (DEFAULT_TICKERS 에 없어 인자 없는 전체 다운로드로는 받아지지 않는다)
# 출력: storage/stock/{TICKER}_synthetic_max.csv (상장 전은 대용, 상장 후는 실물을 이어 붙인 판)
#       storage/stock/VXUS_proxy_max.csv (전 구간 EFA · EEM 합성)
poetry run python scripts/data/generate_proxy_series.py
```

### 장기 대체 시계열 생성 (대체 판 — 2000-08 이전부터 전 기간 대체)

```bash
# 선행: 이 스크립트가 읽는 시세(src/qbt/common_constants.py 의 경로 상수 — 파일 이름이 곧 티커)와 storage/etc 의 금리 · 운용보수 파일
#       저장소에 있는 시세는 「시세를 다시 받은 뒤 다시 돌리는 순서」 ① 이 모두 받는다
# 출력: storage/stock/SSO_proxy_max.csv · QLD_proxy_max.csv (SPY · QQQ 2배 합성, TQQQ 비용 모델을 배율 2 로)
#       storage/stock/BIL_proxy_max.csv (연방기금금리로 이자를 누적한 초단기채 대체)
#       storage/stock/DBC_synthetic_max.csv (DBC 상장 전은 S&P GSCI 지수, 상장 후는 DBC 실물)
poetry run python scripts/data/generate_long_proxy_series.py
```

### 대체-실물 비교 (계산 · 대시보드)

```bash
# 선행: 위 두 생성 스크립트와 비교 쌍의 시세 (쌍 목록은 scripts/data/generate_proxy_comparison.py 의 묶음별 *_PAIRS 표)
# 비교는 기준(대개 실물) 첫 거래일부터 두 시세가 모두 있는 날만 쓴다
# 출력: storage/results/proxy_comparison/summary.csv (쌍마다 전체 상관 · CAGR · MDD · 12개월 상관 최저)
#       storage/results/proxy_comparison/periods.csv (쌍 × 연도 · 국면 상관 · 수익률)
poetry run python scripts/data/generate_proxy_comparison.py

# 대시보드 (선행: 위 계산 — 등록 쌍 표를 읽는다. 「직접 고르기」는 storage/stock 의 아무 두 시세나 비교)
poetry run streamlit run scripts/data/app_proxy_comparison.py
```
