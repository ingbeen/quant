# CLI 스크립트 계층 가이드

> CRITICAL: CLI 계층 작업 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

CLI 스크립트 계층(`scripts/`)은 사용자 인터페이스를 제공하며,
비즈니스 로직(`src/qbt/`)을 호출하고 실행 결과를 사용자에게 전달합니다.

계층 원칙: 도메인 로직 구현 금지, 오직 인터페이스 제공만 담당

---

## 핵심 책임

### 1. 사용자 인터페이스

- 명령행 인자 파싱
- 사용자 입력 검증
- 실행 옵션 해석

### 2. 실행 환경 설정

- 로거 초기화
- 로그 레벨 설정
- 환경 변수 처리

### 3. 비즈니스 로직 호출

- 적절한 도메인 모듈 선택
- 파라미터 전달
- 결과 수령

### 4. 결과 표시

- 성공/실패 메시지
- 요약 통계 출력
- 테이블 형식 결과 표시
- 실행 이력 파일은 남기지 않는다 — 실행 파라미터는 각 결과의 `summary.json` 에, 생성 시점은 git 이력에 있다. 이력을 쌓던 `meta.json` 은 읽는 코드가 0 이었고 최근 5칸이 한 번 실행(포트폴리오 실험 5개)으로 덮여 출처 기록으로도 쓸 수 없어 지웠다(2026-10-11)

### 5. 예외 처리

책임: 모든 예외를 사용자 친화적 메시지로 변환

- `@cli_exception_handler` 데코레이터 사용 (자동 예외 처리)
- 자동 수행:
  - 예외 캐치 및 ERROR 로그 기록
  - 스택 트레이스 포함
  - 종료 코드 1 반환 (실패)
- 데코레이터는 스크립트의 모듈 레벨 `logger` 변수를 쓴다 (없으면 KeyError)
- 실행 위치에 `storage` 폴더가 없으면 본문을 실행하지 않고 「저장소 루트에서 실행하세요」로 실패한다 — 입력 · 결과 경로가 실행 위치 기준이다
- CLI 계층에서만 ERROR 로그 사용 가능 (비즈니스 로직에서는 금지)

근거 위치: [src/qbt/utils/cli_helpers.py](../src/qbt/utils/cli_helpers.py)

---

## 표준 구조

### 필수 구성 요소

임포트 섹션:

- 표준 라이브러리
- 도메인 모듈
- 유틸리티 모듈
- 상수 모듈

로거 초기화:

- 모듈 레벨에서 로거 생성 (변수 이름 `logger`)
- 예외 처리 데코레이터가 이 로거를 쓴다

main 함수:

- 데코레이터 적용
- 종료 코드 반환 (0=성공, 1=실패)
- 명확한 단계별 로직

진입점 보호:

- `if __name__ == "__main__"` 사용
- 병렬 처리 환경 고려

### 실행 흐름

1. 로거 초기화
2. 명령행 인자 파싱 (필요 시)
3. 데이터 로딩
4. 비즈니스 로직 호출
5. 결과 표시
6. 성공 코드 반환

---

## 도메인별 스크립트

### 데이터 수집 (data/)

- 외부 소스에서 데이터 다운로드
- 엄격한 검증 수행
- 검증 통과 후 저장
- 다운로드 통계 출력
- 대용 시계열 생성 (`generate_proxy_series.py`): 실물 ETF 상장 전 구간을 대용 시세로 채운 파일을 만든다 — 이어 붙인 판 `{TICKER}_synthetic_max.csv`, 전 구간 합성 `VXUS_proxy_max.csv`. 계산은 `src/qbt/utils/proxy_series.py` 가 하고, 저장은 다운로더와 같은 함수(`stock_downloader.save_stock_csv` — 가격 반올림 → 검사 → 저장)다. 대상 · 대용 원본을 다시 받으면 다시 실행해야 한다
- 장기 대체 시계열 생성 (`generate_long_proxy_series.py`): 대체 판(실물이 없던 2000-08 이전부터 전 기간 대체)이 쓰는 파일 중 계산이 필요한 것만 만든다 — `SSO_proxy_max.csv` · `QLD_proxy_max.csv`(SPY · QQQ 2배 합성, `qbt.tqqq.simulation.simulate` 를 배율 2 로), `BIL_proxy_max.csv`(연방기금금리 누적, `proxy_series.build_rate_accrual_series`), `DBC_synthetic_max.csv`(S&P GSCI → DBC 이어 붙임). 같은 펀드의 뮤추얼 클래스 · 금 선물처럼 받은 시세를 그대로 쓰는 대체는 만들지 않는다. 저장 순서는 위 스크립트와 같다
- 대체-실물 비교 (`generate_proxy_comparison.py`): 등록 쌍(스크립트의 묶음별 `*_PAIRS` 표)마다 전체 · 연도별 · 국면별 비교를 `storage/results/proxy_comparison/` 의 `summary.csv` · `periods.csv` 로 저장한다(한글 헤더, UTF-8 BOM). 계산과 열 이름은 `src/qbt/utils/proxy_comparison.py`, 스크립트는 쌍 목록 · 반올림 · 저장만 한다
- 대시보드 앱 `app_proxy_comparison.py`: 대체-실물 비교 대시보드 (Streamlit + Plotly)
  - 선행: `generate_proxy_comparison.py` 실행 (등록 쌍 표를 읽는다). 요약 파일이 없어도 「직접 고르기」는 동작한다
  - 고른 쌍의 차트 · 기간별 표는 같은 `src` 함수로 즉석 계산한다 — 등록 쌍과 직접 고른 쌍이 같은 경로를 쓰고, 일별 CSV 를 저장하지 않는다

### 백테스트 (backtest/)

- 전략 파라미터 설정
- 단일 백테스트 또는 그리드 탐색 실행
- 성과 지표 계산
- 결과 요약 및 저장
- 데이터 로딩: `load_stock_data` + `extract_overlap_period` (공통 유틸 사용)
- 워크포워드 검증:
  - `run_walkforward.py`: WFO 2-Mode 비교 실행 (Dynamic/Fully Fixed)
    - `--strategy` 인자로 실행 전략 선택 (기본값: all). 대상 전략 목록은 변경될 수 있으므로 `run_walkforward.py`의 `STRATEGY_NAMES`를 직접 확인할 것.
    - 각 모드별 CSV + Stitched Equity CSV + walkforward_summary.json 저장
    - 윈도우별 상세 CSV 저장: `wfo_windows_dynamic/` 및 `wfo_windows_fully_fixed/` 하위에 w{idx}_signal.csv(OHLC + 그 윈도우의 이동평균 + 4종 전일대비%), w{idx}_equity.csv, w{idx}_trades.csv (캔들차트 시각화용)
- 포트폴리오 실험:
  - `run_portfolio_backtest.py`: 포트폴리오 실험 실행
    - `--experiment` 인자로 실행할 실험을 선택한다 (기본값: all). 실험 목록은 변경 빈도가 높아 본 문서에 직접 명시하지 않으며, 최신 값은 `src/qbt/backtest/portfolio_configs.py`의 `PORTFOLIO_CONFIGS`를 직접 확인할 것.
    - 결과: `storage/results/portfolio/{experiment_name}/` 디렉토리에
      equity.csv, trades.csv, summary.json, signal_{asset_id}.csv 저장
    - 매매법이 여럿인 실험: 자산 키가 `{method_id}.{asset_id}` 이고 ledger.csv(매매법별 장부) · netting.csv(종목 단위 상계 내역)와 summary.json 의 per_method · netting · account_holdings · pnl_check 를 더한다. 계산은 `src/`(portfolio_methods 의 summarize_methods · account_target_weights)가 하고 러너는 반올림 · 저장만 한다
    - 실험별 독립 시작일: 각 실험은 자신의 자산 조합에 대해 `compute_portfolio_effective_start_date(config)`로 산출한 유효 시작일(자산 교집합 + MA 워밍업 이후 첫 거래일)을 사용한다(설정에 `min_start_date` 가 있는 실험은 아래). 실험마다 자산 구성이 다르면 백테스트 기간이 달라질 수 있으며, 이는 설계된 동작이다.
    - 시작일 하한 정책: 유효 시작일이 `DEFAULT_PORTFOLIO_START_DATE`(2005-01-01)보다 이르면 이 하한으로 끌어올려 실행한다 (2005년 이전 데이터는 스킵). 이 상수는 현재 스크립트 단일 파일에서만 사용되므로 `run_portfolio_backtest.py` 로컬 상수로 관리한다
    - 설정에 `min_start_date` 가 있는 실험(보완 전략 등록 실험)은 하한 정책 대신 그 날짜에 시작한다 — 시세가 바뀌어 늦게 시작하면 대시보드 숫자가 그리드 결과와 기간만큼 어긋나기 때문이다. 두 번 대조한다: 실행 전에 계산한 데이터 기준 시작일이 그 날짜보다 늦은 실험이 하나라도 있으면 어느 실험도 돌리기 전에 ValueError 로 멈추고(데이터가 늦게 시작하는 경우를 앞 실험의 결과를 새 시세로 덮어쓰기 전에 잡는다 — 2026-10-11 사용자 결정), 실행 뒤에는 그리드 워커와 같은 `run_with_start_check` 가 실제 첫 거래일이 그날인지 본다. 데이터가 더 일찍 시작하는데 그날 행만 빠진 경우는 실행 뒤 대조에서야 멈춘다(앞 실험은 이미 저장됨 — 두 우연이 겹쳐야 생겨 받아들였다)
    - 저장 전에 그 실험 폴더의 `signal_*.csv` · `ledger.csv` · `netting.csv` 를 지운다(`csv_export.remove_config_dependent_files`) — 구성에 따라 생기는 파일이라, 구성이 바뀐 실험을 같은 폴더에 다시 저장하면 지금 실험에 없는 자산 · 매매법의 파일이 남고 대시보드는 파일이 있으면 그린다. 폴더째 지우지 않는다(실험 이름이 비면 `result_dir` 이 결과 폴더 전체다)
- 보완 전략 비중 그리드:
  - `run_supplement_grid.py`: 「Q-2-2XS (100−w)% + 후보 w%」 실행 목록을 병렬로 돌려 요약 CSV 만 저장한다 (인자 없음). 실행 목록 · 판정 · 대용 검증 계산은 `src/qbt/backtest/supplement_experiment.py` 가 하고 러너는 반올림 · 한글 헤더 · 저장만 한다
    - 실행마다 정합성 검사기를 돌려 위반이 있으면 그 구성과 함께 ERROR 로그를 남기고 중단한다 (포트폴리오 러너와 같은 정책). 실제 시작일이 묶음 시작일과 다르면 워커가 멈춘다
    - 결과: `storage/results/portfolio_grid/` 의 `grid_runs.csv` · `judgment.csv` · `proxy_gate.csv` (한글 헤더, UTF-8 BOM — 사람이 읽는 산출물이고 대시보드는 읽지 않는다)
  - `run_combo_grid.py`: 「Q-2-2XS (100 − h − r)% + HAA h% + 로테이션 r%」 비중 격자를 대체 판 · 이어 붙인 판 · 완전 실물판(과 대체 판 확인용 겹침 묶음)으로 돌리고, 같은 합계의 기준선 · HAA 단독 · 로테이션 단독 · Q-2-2XS 단독을 함께 돌려 요약 CSV 만 저장한다 (인자 없음). 실행 목록 · 판정 · 대체 판 확인 계산은 `src/qbt/backtest/combo_experiment.py` 가 하고 러너는 반올림 · 한글 헤더 · 저장만 한다
    - 정합성 위반 · 실제 시작일 처리는 `run_supplement_grid.py` 와 같다
    - 결과: `storage/results/portfolio_combo_grid/` 의 `combo_runs.csv` · `combo_judgment.csv` · `combo_alt_check.csv` (한글 헤더, UTF-8 BOM)
- 파라미터 고원 분석:
  - `run_param_plateau_all.py`: 파라미터(hold_days, sell_buffer, buy_buffer, ma_window) 통합 고원 분석
    - `--experiment` 인자: all(기본) / hold_days / sell_buffer / buy_buffer / ma_window
    - 결과: `param_plateau/` 디렉토리에 피벗 CSV 저장 (calmar/cagr/mdd/trades × 분석 파라미터)
- 대시보드 앱:
  - `app_single_backtest.py`: 전략별 동적 탭 대시보드 (Streamlit + lightweight-charts + Plotly)
    - 선행: `run_single_backtest.py` 실행 필요 (결과 CSV/JSON 로드)
    - 전략 자동 탐색: `BACKTEST_RESULTS_DIR` 하위 폴더를 스캔하여 전략별 탭 자동 생성
    - Feature Detection: 데이터 존재 여부로 차트 오버레이 결정 (전략명 분기 없음)
    - 미청산 포지션 마커: `summary.open_position` 존재 시 `"Buy (보유중)"` 마커 자동 표시
    - customValues 기반 tooltip: 전일대비%, 이평선, 상단/하단 밴드 표시
    - 날짜 표기: `localization.dateFormat` 설정으로 한국식 "yyyy-MM-dd" 형식 적용
    - vendor fork: `vendor/streamlit-lightweight-charts-v5/` (tooltip 지원 추가)
  - `app_parameter_stability.py`: 4개 파라미터(MA Window, Buy Buffer, Sell Buffer, Hold Days) 고원 시각화 대시보드
    - 선행: `run_param_plateau_all.py` 실행 필요 (고원 분석 CSV 로드)
    - 각 탭: 다자산 Calmar 라인차트, 확정값 마커, 고원 구간 하이라이트, 보조 지표(CAGR/MDD/거래수) expander
  - `app_walkforward.py`: WFO 2-Mode 결과 시각화 대시보드 (Streamlit + Plotly + lightweight-charts)
    - 선행: `run_walkforward.py` 실행 필요 (WFO 결과 CSV/JSON 로드)
    - 전략 자동 탐색: walkforward_summary.json 존재 여부로 유효 전략 판별, 전략별 좌우 비교 통합 뷰
    - 주요 섹션: 모드 요약 비교, Stitched Equity 곡선, IS/OOS 성과 바차트, 파라미터 추이, 윈도우별 상세 차트
    - 윈도우별 상세 차트: Selectbox 네비게이션 (지표 × 윈도우 조합), IS+OOS 결합 캔들차트 + Buy/Sell 마커 + MA + 밴드 + 에쿼티 + 드로우다운, OOS 시작일 경계 마커, lightweight-charts 사용
    - VERBATIM 패턴: 각 섹션에 용어 설명 / 해석 방법 / 현재 판단 3부분 구조 적용
  - `app_portfolio_backtest.py`: 포트폴리오 실험 비교 대시보드 (Streamlit + Plotly)
    - 선행: `run_portfolio_backtest.py` 실행 필요 (결과 CSV/JSON 로드)
    - 실험 자동 탐색: `PORTFOLIO_RESULTS_DIR` 하위 summary.json 존재 여부로 유효 실험 판별, 알파벳 순 탭 자동 생성
    - 주요 섹션:
      - 전체 비교 탭: 성과 지표 비교 테이블, 에쿼티 곡선 비교, 드로우다운 비교
      - 실험별 탭: 요약 지표, 에쿼티+드로우다운 서브플롯, 자산별 비중 추이, 시그널 차트(자산 선택), 월별 수익률 히트맵, 자산별 수익 기여도
      - 매매법이 여럿인 실험(ledger.csv 존재): 「매매법별 손익」 섹션 추가

### 레버리지 시뮬레이션 (tqqq/)

- 합성 데이터 생성 (`generate_synthetic.py`)
- 일별 비교 데이터 생성 (`generate_daily_comparison.py`, softplus 동적 스프레드 사용)
- 대시보드 앱:
  - `app_daily_comparison.py`: 일별 비교 대시보드

### 스프레드 모델 검증 결과 열람 (tqqq/spread_lab/)

- 대시보드 앱:
  - `app_rate_spread_lab.py`: 금리-오차 관계 · softplus 튜닝 · 워크포워드 결과 열람 전용 (단일 흐름: 오차분석→튜닝→워크포워드 RMSE 비교→상세분석). RMSE 로 과최적화를 판정하지 않고 수치와 잰 기간만 보인다 — 이유와 결과 CSV 를 만든 스크립트의 자리는 앱 docstring

---

## 코딩 규칙

### 예외 처리

데코레이터 사용:

- try-except 블록 불필요

예외 전파:

- 비즈니스 로직에서 발생한 예외를 그대로 전파
- 변환하거나 숨기지 않음

### Streamlit 앱 규칙

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

### 명령행 인자

기본 원칙: 명령행 인자 최소화

- CLI 스크립트는 기본적으로 명령행 인자를 받지 않음
- 모든 파라미터는 상수 파일에서 정의
  - 공통 상수: `src/qbt/common_constants.py`
  - 도메인 상수: 각 도메인의 `constants.py` (예: `src/qbt/backtest/constants.py`)
  - 상수 명명 규칙: [src/qbt/CLAUDE.md](../src/qbt/CLAUDE.md) 「2. 상수 관리」 참고
- 예외 사례 1: 데이터 다운로드 스크립트(`scripts/data/download_data.py`)
  - ticker(선택)를 명령행 인자로 받음. 늘 전체 기간을 받아 `{TICKER}_max.csv` 로 저장한다
  - ticker 미지정 시 `DEFAULT_TICKERS` 전체 종목 일괄 다운로드
  - 이유: 다양한 종목에 대한 유연한 데이터 수집 필요
- 예외 사례 2: 단일 백테스트 스크립트(`scripts/backtest/run_single_backtest.py`)
  - `--strategy` 인자로 실행 전략 선택 (기본값: all). 선택 가능한 전략 목록은 변경 빈도가 높으므로 본 문서에 직접 나열하지 않으며, 최신 값은 `STRATEGY_RUNNERS` 키 (= buffer_zone / buy_and_hold CONFIGS 기반 자동 등록)를 직접 확인할 것.
  - cross-asset 전략은 CONFIGS 기반 자동 등록
  - 이유: 전략별 독립 실행 및 비교 실행 지원
    근거 위치: [scripts/data/download_data.py](data/download_data.py), [scripts/backtest/run_single_backtest.py](backtest/run_single_backtest.py)
