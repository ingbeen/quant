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

- `download_data.py` — 시세 다운로드. 늘 전체 기간을 받아 `{TICKER}_max.csv` 로 저장하고, 티커를 주지 않으면 `DEFAULT_TICKERS` 와 월별 연방기금금리(FRED, `storage/etc` 금리 파일), GLD 합성의 금 사슬 원본(Perth Mint 금값 · FRED 호주달러 환율, `storage/etc`)을 받는다
- `generate_synthetic.py` — 합성 시세 전부: 1배 대용 합성(대상 표 `PROXY_TARGETS`, GLD 는 금 사슬 — `src/qbt/utils/gold_proxy.py` — 에서 GLD 운용보수를 뺀 것)과 그 1배 합성으로 만든 레버리지 합성(상품마다 기초를 정한 상품 표는 `src/qbt/tqqq/constants.py`). 검증 표(대용 ↔ 실물, 레버리지 합성 ↔ 실물, ETF 상장 전 펀드 대조, 가정만 바꾼 판)를 저장하고 콘솔에 직전 저장값과 나란히 낸다
- **새 시세를 받을 때 사용자는 이 둘만 돌린다** (사용자 요청 2026-11-05) — 그래서 야후에서 받는 원본 시세(검증에만 쓰는 펀드 포함)는 모두 `DEFAULT_TICKERS` 에 두고, 합성 시세(`*_synthetic_max.csv`)는 모두 `generate_synthetic.py` 가 만든다. 어긋나도 에러가 없다 — 빠진 시세만 낡은 채 남는다. 운용비율(`storage/etc`)만 손으로 갱신하고, 낡으면 레버리지 합성이 멈춘다(COMMANDS 「시세를 다시 받은 뒤 다시 돌리는 순서」 ②)

백테스트 (`backtest/`):

- `run_single_backtest.py` · `run_walkforward.py` · `run_param_plateau_all.py` — 단일 전략 · 워크포워드 · 파라미터 고원. 단일 전략은 버퍼존 · Buy & Hold 의 설정 목록을 모두 돌고, 대시보드가 같은 목록을 읽는다. 세 러너 모두 설정이 가리키는 합성 시세로 돈다
- `run_portfolio_backtest.py` — 포트폴리오 실험. 설정에 `min_start_date` 가 없는 등록 실험은 모두 같은 날 — 그 실험들의 데이터 시작일 중 가장 늦은 날 — 에 시작하고(하나만 돌려도 등록 실험 전부를 재서 같은 날), `min_start_date` 가 있는 실험은 그 날짜에 시작한다 (`docs/research/합성_시세_연장.md` 결정 10). 실제 시작일이 그날과 다르면 멈춘다
- 대시보드 `app_single_backtest.py` · `app_portfolio_backtest.py` · `app_walkforward.py` · `app_parameter_stability.py` — 화면 구성은 각 앱 docstring, 세 앱이 같이 쓰는 차트는 `src/qbt/backtest/dashboard_charts.py`. 포트폴리오 대시보드에 체결일별 전후 표는 두지 않는다 — 체결일의 자산별 주수 · 비중 · 평가액은 `equity.csv` · `state_log.csv` 에 이미 있다

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
