# QBT 실행 명령어 레퍼런스

> 이 파일은 QBT 프로젝트 실행 명령어의 **단일 SoT(Source of Truth)** 입니다.
> README.md 등 다른 문서에는 실행 명령어를 기재하지 않으며, 필요 시 이 문서를 참조합니다.
> 관련 규칙: [루트 CLAUDE.md](../CLAUDE.md) "실행 명령어 관리 원칙"

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

# 2. 단일 전략 검증 + 결과 저장
# 출력: 콘솔 (버퍼존 vs Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)
# --strategy 인자로 특정 전략만 실행 가능 (기본값: all)
# 전략명은 src/qbt/backtest/strategies/buffer_zone.py::CONFIGS 및
#           src/qbt/backtest/strategies/buy_and_hold.py::CONFIGS 를 직접 참고 (변경 빈도 높음)
poetry run python scripts/backtest/run_single_backtest.py
poetry run python scripts/backtest/run_single_backtest.py --strategy <strategy_name>

# 3. 포트폴리오 백테스트 (선행: 1, TQQQ 합성 데이터 필요)
# 실험 구성은 src/qbt/backtest/portfolio_configs.py의 PORTFOLIO_CONFIGS 참고 (목록은 자주 변경됨)
# 자산 슬롯별 전략 파라미터 독립 설정 (ma_window, buy/sell_buffer_zone_pct, hold_days)
# 리밸런싱: 엔진 레벨 고정 — 월 첫 거래일/매일 편차 임계값 2단 (실험 설정으로 변경 불가, 값은 DEFAULT_REBALANCE_POLICY 참조)
# 출력: storage/results/portfolio/{experiment_name}/ (equity, trades, summary, signal_{asset_id}, state_log, execution_comparison)
# 실행 직후 정합성 규칙 자동 검증 (시그널-체결 lag, 리밸런싱 비중, EXIT_ALL 주수, 현금 비음수, 에쿼티 등식)
# 위반 발견 시 결과 저장 후 스크립트 중지 (ValueError)
poetry run python scripts/backtest/run_portfolio_backtest.py
# --experiment 인자로 특정 실험 선택 가능 (실험명은 PORTFOLIO_CONFIGS 참고, 기본값: all)
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment <experiment_name>

# 4. 워크포워드 검증 (과최적화 검증, 선행: 1)
poetry run python scripts/backtest/run_walkforward.py
# 출력: 2-Mode 비교 (Dynamic/Fully Fixed) + stitched equity
# 진단 지표: WFE (CAGR/Calmar), Profit Concentration, min_trades 필터링
# 결과: storage/results/backtest/{전략명}/walkforward_*.csv, walkforward_summary.json

# --strategy 인자로 특정 전략만 실행 가능 (기본값: all)
# 대상 전략은 src/qbt/backtest/strategies/buffer_zone.py::CONFIGS 를 직접 참고
poetry run python scripts/backtest/run_walkforward.py --strategy <strategy_name>

# 5. 파라미터 고원 분석 (선행: 1)
poetry run python scripts/backtest/run_param_plateau_all.py
# 파라미터(hold_days/sell_buffer/buy_buffer/ma_window) 통합 고원 분석
# --experiment 인자: all(기본) / hold_days / sell_buffer / buy_buffer / ma_window
# 출력: storage/results/backtest/param_plateau/ (피벗 CSV)

# 6. 대시보드 시각화 (선행: 2)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 7. 포트폴리오 비교 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_portfolio_backtest.py
# 시각화: 전체 비교(에쿼티 곡선/드로우다운 비교, 성과 지표 테이블), 실험별 탭(자산별 비중 추이, 시그널 차트, 수익 기여도)

# 7-1. 포트폴리오 디버그 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_portfolio_debug.py
# 시각화: 일별 상태 네비게이터, 동기화 시계열 차트(에쿼티/비중/현금/주수), 체결 상세 테이블, 시그널-체결 추적

# 8. WFO 결과 시각화 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_walkforward.py
# 시각화: QQQ vs TQQQ 나란히 비교 (모드 요약, Stitched Equity, IS/OOS, 파라미터 추이, WFE 분포)

# 9. 파라미터 고원 시각화 대시보드 (선행: 4)
poetry run streamlit run scripts/backtest/app_parameter_stability.py
# 시각화: 4개 파라미터(MA/Buy/Sell/Hold) x 멀티자산 Calmar 라인차트, 고원 구간 하이라이트
```

**파라미터 변경**: [src/qbt/backtest/constants.py](../src/qbt/backtest/constants.py)

---

## 워크플로우 2: TQQQ 레버리지 ETF 시뮬레이션

QQQ로부터 TQQQ를 시뮬레이션하고 실제 데이터와 비교하여 비용 모델을 검증합니다.

```bash
# 1. 필수 데이터 다운로드 (전체 종목 일괄)
poetry run python scripts/data/download_data.py
# 또는 개별 다운로드
poetry run python scripts/data/download_data.py QQQ
poetry run python scripts/data/download_data.py TQQQ

# 2. 일별 비교 데이터 생성 (softplus 동적 스프레드 모델)
poetry run python scripts/tqqq/generate_daily_comparison.py
# 출력: storage/results/tqqq/tqqq_daily_comparison.csv

# 3. 합성 TQQQ 데이터 생성 (선택)
poetry run python scripts/tqqq/generate_synthetic.py
# 출력: storage/stock/TQQQ_synthetic_max.csv
```

### 대시보드 앱 실행

```bash
# 일별 비교 대시보드
# 선행: 1 → 2
# 필요: storage/results/tqqq/tqqq_daily_comparison.csv
poetry run streamlit run scripts/tqqq/app_daily_comparison.py
```

### 스프레드 모델 검증 결과 열람 (spread_lab/)

스프레드 모델 파라미터는 확정 상태이며, 결과 열람용 시각화 앱만 제공합니다.

```bash
# 금리-오차 관계 분석 앱 (시각화 전용)
# 필수: storage/results/tqqq/tqqq_daily_comparison.csv
# 선택: storage/results/tqqq/spread_lab/ 하위 결과 CSV
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

**파라미터 변경**: [src/qbt/tqqq/constants.py](../src/qbt/tqqq/constants.py)

## 품질 검증 (통합)

```bash
# 전체 검증 (Ruff + PyRight + Pytest) - 권장
poetry run python validate_project.py

# 커버리지 포함 전체 검증
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
# 커버리지 포함 검증 (권장)
poetry run python validate_project.py --cov

# HTML 리포트 생성 (직접 pytest 사용)
poetry run pytest --cov=src/qbt --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

---

## 데이터 다운로드 옵션

```bash
# 전체 종목 일괄 다운로드 (대상 티커는 scripts/data/download_data.py 의 DEFAULT_TICKERS 참조)
poetry run python scripts/data/download_data.py

# 특정 종목 전체 기간
poetry run python scripts/data/download_data.py TICKER

# 시작일 지정
poetry run python scripts/data/download_data.py TICKER --start YYYY-MM-DD

# 기간 지정
poetry run python scripts/data/download_data.py TICKER --start YYYY-MM-DD --end YYYY-MM-DD

# 예시
poetry run python scripts/data/download_data.py QQQ --start 2020-01-01
```
