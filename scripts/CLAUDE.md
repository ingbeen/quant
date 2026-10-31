# CLI 스크립트 계층 가이드

## 폴더 목적

CLI 스크립트 계층(`scripts/`)은 사용자 인터페이스를 제공하며,
비즈니스 로직(`src/qbt/`)을 호출하고 실행 결과를 사용자에게 전달합니다.

계층 원칙: 도메인 로직 구현 금지 — 계산은 `src/qbt/` 가 하고, 스크립트는 인자 해석 · 호출 · 반올림 · 저장 · 표시만 한다.

실행 명령 · 선행 순서 · 출력 폴더는 [docs/COMMANDS.md](../docs/COMMANDS.md)가 정본이다. 시세를 다시 받은 뒤 생성 스크립트 · 러너를 다시 돌리는 순서도 그 문서의 「시세를 다시 받은 뒤 다시 돌리는 순서」.

---

## 표준 구조

- 모듈 레벨에서 로거를 만든다 (변수 이름 `logger` — 예외 처리 데코레이터가 이 이름을 읽는다, 없으면 KeyError)
- `main()` 에 `@cli_exception_handler` 를 붙이고 종료 코드를 반환한다 (0 = 성공, 1 = 실패)
- `if __name__ == "__main__":` 로 진입점을 보호한다 — 병렬 처리(spawn)가 모듈을 다시 import 한다
- 실행 이력 파일은 남기지 않는다 — 실행 파라미터는 각 결과의 `summary.json` 에, 생성 시점은 git 이력에 있다

### 예외 처리

- `@cli_exception_handler` 가 예외를 ERROR 로그(스택 트레이스 포함)로 남기고 종료 코드 1 을 반환한다 — 스크립트에 try-except 를 두지 않고, 비즈니스 로직의 예외를 변환하거나 숨기지 않는다
- 실행 위치에 `storage` 폴더가 없으면 본문을 실행하지 않고 「저장소 루트에서 실행하세요」로 실패한다 — 입력 · 결과 경로가 실행 위치 기준이다
- ERROR 로그는 CLI 계층에서만 쓴다 (비즈니스 로직에서는 금지)

근거 위치: [src/qbt/utils/cli_helpers.py](../src/qbt/utils/cli_helpers.py)

### 명령행 인자

- 파라미터는 명령행 인자 대신 상수 파일에 둔다 (배치는 [src/qbt/CLAUDE.md](../src/qbt/CLAUDE.md) 「2. 상수 관리」)
- 인자를 받는 스크립트(다운로드할 티커, 실행할 전략 · 실험 고르기)의 선택지는 `--help` 가 정본이다

---

## 스크립트 지도

데이터 (`data/`):

- `download_data.py` — 시세 다운로드. 늘 전체 기간을 받아 `{TICKER}_max.csv` 로 저장하고, 티커를 주지 않으면 `DEFAULT_TICKERS` 를 받는다
- `generate_proxy_series.py` · `generate_long_proxy_series.py` — 대용 · 장기 대체 시계열 생성. 계산은 `src/qbt/utils/proxy_series.py`(2배 합성은 `qbt.tqqq.simulation.simulate`), 저장은 다운로더와 같은 `stock_downloader.save_stock_csv`
- `generate_proxy_comparison.py` — 대체-실물 비교 요약 CSV. 계산과 열 이름은 `src/qbt/utils/proxy_comparison.py`
- `app_proxy_comparison.py` — 대체-실물 비교 대시보드. 고른 쌍의 차트 · 기간별 표는 같은 src 함수로 즉석 계산하고 일별 CSV 를 저장하지 않는다

백테스트 (`backtest/`):

- `run_single_backtest.py` · `run_walkforward.py` · `run_param_plateau_all.py` — 단일 전략 · 워크포워드 · 파라미터 고원
- `run_portfolio_backtest.py` — 포트폴리오 실험. 데이터 기준 시작일이 `DEFAULT_PORTFOLIO_START_DATE` 보다 이르면 그 하한으로 끌어올리고, 설정에 `min_start_date` 가 있는 실험은 그 날짜에 시작한다
- `run_supplement_grid.py` · `run_combo_grid.py` — 보완 전략 비중 그리드 · 조합 그리드. 요약 CSV 만 저장한다(한글 헤더, UTF-8 BOM — 사람이 읽는 산출물이고 대시보드는 읽지 않는다)
- 대시보드 `app_single_backtest.py` · `app_portfolio_backtest.py` · `app_walkforward.py` · `app_parameter_stability.py` — 화면 구성은 각 앱 docstring, 세 앱이 같이 쓰는 차트는 `src/qbt/backtest/dashboard_charts.py`. 포트폴리오 대시보드에 체결일별 전후 표는 두지 않는다 — 체결일의 자산별 주수 · 비중 · 평가액은 `equity.csv` · `state_log.csv` 에 이미 있다

레버리지 시뮬레이션 (`tqqq/`):

- `generate_synthetic.py` — TQQQ · QLD 합성 시세 (상장 전은 시뮬레이션, 상장 후는 실물, 상품 표는 `tqqq/constants.py`)
- `generate_daily_comparison.py` · `app_daily_comparison.py` — TQQQ · QLD 일별 비교 CSV(softplus 동적 스프레드, 상품 표는 `tqqq/constants.py`)와 그 대시보드
- `spread_lab/app_rate_spread_lab.py` — 스프레드 모델 검증 결과 열람 전용. RMSE 로 과최적화를 판정하지 않고 수치와 잰 기간만 보인다 — 이유와 결과 CSV 를 만든 스크립트의 자리는 앱 docstring

---

## Streamlit 앱 규칙

width 파라미터 사용:

- 너비 지정은 `width` 파라미터로만 한다 (`use_container_width`는 사용하지 않는다)
- 전체 너비 사용 시: `width="stretch"`
- 콘텐츠 크기 맞춤 시: `width="content"`

적용 대상 위젯:

- `st.button()`
- `st.dataframe()`
- `st.plotly_chart()`
- `st.download_button()`
- 기타 width 관련 파라미터를 지원하는 위젯
