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

# 2. 단일 전략 검증 + 결과 저장 (선행: 1, TQQQ · QLD 합성 — 워크플로우 2 의 2)
# 출력: 콘솔 (버퍼존 · Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)
# --strategy 인자로 특정 전략만 실행 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_single_backtest.py
poetry run python scripts/backtest/run_single_backtest.py --strategy <strategy_name>

# 3. 포트폴리오 백테스트 (선행: 1)
# 출력: storage/results/portfolio/{experiment_name}/ (equity, trades, summary, signal_{asset_id}, state_log, 매매법이 여럿이면 ledger · netting)
# 실행 직후 정합성 검증 — 위반이 있으면 결과를 저장한 뒤 멈춘다 (ValueError)
poetry run python scripts/backtest/run_portfolio_backtest.py
# --experiment 인자로 특정 실험 선택 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment <experiment_name>

# 4. 워크포워드 검증 (선행: 1, TQQQ 합성 — 워크플로우 2 의 2)
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

## 워크플로우 2: 합성 시세 (QQQ · SPY 와 그 2 · 3배, TLT · GLD)

실물 ETF 상장 전 구간을 채운 합성 시세를 스크립트 하나로 모두 만듭니다 — QQQ 는 나스닥 100 지수로, SPY 는 S&P 500 인덱스 펀드(VFINX)로 채우고, TQQQ · QLD 는 그 QQQ 합성, SSO · UPRO 는 그 SPY 합성으로부터 시뮬레이션해 채우고, TLT 는 뱅가드 장기국채 펀드(VUSTX)로, GLD 는 Perth Mint 금값과 금 선물(GC=F)을 이은 금 사슬로 채우고, 실물 첫 거래일부터는 실물로 이어 붙입니다. 새 시세를 받으면 아래 두 명령을 돌립니다 — 다운로드가 월별 금리(FRED)와 금 사슬의 원본(Perth Mint 금값 · FRED 호주달러 환율)도 함께 받습니다. 운용비율 파일만 손으로 갱신하며, 시세 끝보다 너무 낡으면 레버리지 합성이 멈춥니다 — 아래 「시세를 다시 받은 뒤 다시 돌리는 순서」 ②.

```bash
# 1. 데이터 다운로드 (전체 종목 일괄 + 월별 금리 · 금 사슬 원본 — 합성이 읽는 시세가 모두 DEFAULT_TICKERS 에 있다)
poetry run python scripts/data/download_data.py

# 2. 합성 시세 생성 (TQQQ · QLD 판은 워크플로우 1 의 단일 백테스트가 읽고 — Buy & Hold 는 QQQ 실물 기간만 — TQQQ 판은 워크포워드의 TQQQ 전략도 읽는다)
# 출력: storage/stock/ 의 QQQ · SPY · TQQQ · QLD · SSO · UPRO · TLT · GLD 합성 ({TICKER}_synthetic_max.csv)
#       storage/results/proxy_validation/ — summary.csv · years.csv (대용 ↔ 실물 — 금 사슬은 이음매마다), tracking.csv (레버리지 합성 ↔ 실물 추적),
#       funds.csv · fund_years.csv (ETF 상장 전 펀드 대조), assumptions.csv (가정만 바꾼 판)
#       연도별 · 해마다 표 밖의 표는 콘솔에 직전 저장값과 나란히 나온다
poetry run python scripts/data/generate_synthetic.py
```

**파라미터 변경**: 레버리지 비용 모델 · 가산금리 상한 · 레버리지 상품 표(`LEVERAGED_SYNTHETIC_TARGETS` — 상품마다 기초 시세)는 [src/qbt/tqqq/constants.py](../src/qbt/tqqq/constants.py), 1배 대용 대상 표(`PROXY_TARGETS`) · 금 사슬의 미국 달력(`US_CALENDAR_DATA_PATH`) · 펀드 대조 · 가정만 바꾼 판의 대상 표(`ASSUMPTION_TARGETS`)는 [scripts/data/generate_synthetic.py](../scripts/data/generate_synthetic.py)

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

**① 원본 시세** — `storage/stock` 의 `*_max.csv` 중 생성 파일(`*_synthetic_max`)이 아닌 것 전부. 모두 `DEFAULT_TICKERS` 에 두므로 인자 없는 다운로드가 받는다(규칙은 [scripts/CLAUDE.md](../scripts/CLAUDE.md) 「스크립트 지도」). 같은 다운로드가 GLD 합성의 금 사슬 원본 `storage/etc/perth_mint_gold_daily.csv`(Perth Mint 하루 평균 금값 — 2015-12-31 에 끝난 보관 파일) · `aud_usd_daily.csv`(FRED `DEXUSAL`)도 받는다 — 손으로 고치지 않는다.

```bash
poetry run python scripts/data/download_data.py
```

**② `storage/etc` 월별 파일** — 금리 `federal_funds_rate_monthly.csv` 는 ① 의 인자 없는 다운로드가 FRED `FEDFUNDS`(월별, %) 전체 기간을 받아 ÷ 100 해 다시 쓴다(티커를 주고 돌리면 받지 않는다). 운용비율만 손으로 갱신한다. 열은 `DATE`(yyyy-mm) · `VALUE`(비율), 달마다 한 행, 줄 끝은 기존 행과 같은 CRLF. 편집기로 붙인다 — 파일 끝에 줄바꿈이 없으면 셸 `>>` 는 마지막 행에 이어 붙인다.

- `tqqq_net_expense_ratio_monthly.csv`: ProShares TQQQ Summary Prospectus 의 Net expense ratio(%) ÷ 100 — 설명서 날짜 다음 달부터 그 값
- 시세 끝이 파일 끝보다 `MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF`([src/qbt/tqqq/data_loader.py](../src/qbt/tqqq/data_loader.py))를 넘게 뒤면 두 파일을 읽는 ③ 의 합성 생성이 멈춘다

**③ – ④ 생성 · 결과** — 블록의 줄 순서대로 ③ 합성 시세 QQQ · SPY 와 그 2 · 3배 · TLT · GLD(TQQQ · QLD 판은 단일 백테스트가 읽고, TQQQ 판은 워크포워드의 TQQQ 전략도 읽는다), ④ 결과 러너. 하나가 실패하면 뒤는 돌지 않는다(`set -e` 는 괄호 안 하위 셸에만 걸린다). 블록 안에는 주석을 두지 않는다 — 주석 옵션(`interactivecomments`)이 꺼진 대화형 zsh 는 `#` 줄을 명령으로 읽어 첫 줄에서 멈춘다.

```bash
(
  set -e
  poetry run python scripts/data/generate_synthetic.py

  poetry run python scripts/backtest/run_single_backtest.py
  poetry run python scripts/backtest/run_walkforward.py
  poetry run python scripts/backtest/run_param_plateau_all.py
  poetry run python scripts/backtest/run_portfolio_backtest.py
)
```

---

## 데이터 다운로드 옵션

```bash
# 전체 종목 일괄 다운로드 + 월별 연방기금금리(FRED) · 금 사슬 원본(Perth Mint 금값 · FRED 호주달러 환율) (대상 티커는 scripts/data/download_data.py 의 DEFAULT_TICKERS 참조)
poetry run python scripts/data/download_data.py

# 특정 종목 전체 기간 — 금리 · 금 사슬 원본은 받지 않는다 (특수 문자가 든 티커는 따옴표로 감싼다 — "^SPGSCI" · "GC=F". 파일 이름도 티커 그대로)
poetry run python scripts/data/download_data.py TICKER
```
