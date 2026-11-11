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

## 워크플로우 1: 합성 시세 (QQQ · SPY 와 그 2 · 3배, TLT · GLD)

워크플로우 2 의 백테스트(단일 · 포트폴리오 · 워크포워드 · 고원)는 모두 실물 ETF 상장 전 구간을 채운 합성 시세 8종(`storage/stock/{TICKER}_synthetic.csv`)을 읽습니다. 이 시세는 데이터 저장소 quant-data 가 받고 · 판정하고 · 합성해 이 저장소로 내보낸 사본이고, 이 저장소에는 받기 · 합성 명령이 없습니다 — quant-data 에서 그 저장소 `docs/COMMANDS.md` 의 「갱신」 → 「내보내기」를 돌립니다.

- 받을 파일: `storage/stock/quant_data_files.txt` (한 줄에 quant-data storage 기준 경로 하나)
- 받은 판: `storage/stock/quant_data_edition.json` — quant-data 커밋 번호 · 커밋 안 된 변경 · 기준일 · 파일별 기간

---

## 워크플로우 2: 백테스트 전략 분석

이동평균 기반 버퍼존 전략의 성과를 평가합니다.

```bash
# 1. 단일 전략 검증 + 결과 저장 (선행: 워크플로우 1. 버퍼존 · Buy & Hold 는 모두 상장 전까지 늘린 합성 시세를 읽는다)
# 출력: 콘솔 (버퍼존 · Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)
# --strategy 인자로 특정 전략만 실행 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_single_backtest.py
poetry run python scripts/backtest/run_single_backtest.py --strategy <strategy_name>

# 2. 포트폴리오 백테스트 (선행: 워크플로우 1. 등록 실험은 모두 같은 날 시작한다 — 하나만 돌려도 같다)
# 출력: storage/results/portfolio/{experiment_name}/ (equity, trades, summary, signal_{asset_id}, state_log, 매매법이 여럿이면 ledger · netting)
# 실행 직후 정합성 검증 — 위반이 있으면 결과를 저장한 뒤 멈춘다 (ValueError)
poetry run python scripts/backtest/run_portfolio_backtest.py
# --experiment 인자로 특정 실험 선택 가능 (기본값: all, 선택지는 --help)
# 다른 실험의 저장 결과가 지금 기간과 다르면(늦게 시작하는 실험을 새로 등록했거나 새 시세로 끝날이 늘었을 때) 쓰기 전에 멈춘다 — 그때는 인자 없이 전체를 돌린다
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment <experiment_name>

# 3. 워크포워드 검증 (선행: 워크플로우 1 — QQQ · QLD · TQQQ · SPY · SSO 합성)
# 출력: storage/results/backtest/{전략명}/ (walkforward_*.csv, walkforward_summary.json, 윈도우별 상세 wfo_windows_*/)
# 소요: 수 분 — 그리드 서치라 그리드 범위 · 윈도우 수에 따라 달라진다 (약 13분)
poetry run python scripts/backtest/run_walkforward.py

# --strategy 인자로 특정 전략만 실행 가능 (기본값: all, 선택지는 --help)
poetry run python scripts/backtest/run_walkforward.py --strategy <strategy_name>

# 4. 파라미터 고원 분석 (선행: 워크플로우 1 — QQQ · SPY · GLD · TLT 합성)
poetry run python scripts/backtest/run_param_plateau_all.py
# --experiment 인자로 특정 실험만 실행 가능 (기본값: all, 선택지는 --help)
# 출력: storage/results/backtest/param_plateau/ (피벗 CSV)

# 5. 대시보드 시각화 (선행: 1)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 6. 포트폴리오 비교 대시보드 (선행: 2)
poetry run streamlit run scripts/backtest/app_portfolio_backtest.py

# 7. WFO 결과 시각화 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_walkforward.py

# 8. 파라미터 고원 시각화 대시보드 (선행: 4)
poetry run streamlit run scripts/backtest/app_parameter_stability.py
```

**파라미터 변경**: [src/qbt/backtest/constants.py](../src/qbt/backtest/constants.py)

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

결과 파일은 만들 때의 시세로 굳은 사본이다. quant-data 에서 갱신 · 내보내기를 다시 해 `storage/stock` 의 합성 시세가 바뀌면 아래 결과 러너를 끝까지 차례로 다시 돌린다 — 일부만 돌리면 같은 결과 폴더에 기준일이 다른 산출물이 섞인다. **단계마다 끝까지 성공한 것을 보고 다음 단계로 간다** — 아래 블록은 실패하면 그 자리에서 멈춘다.

**① 시세 받기** — 워크플로우 1. quant-data 의 갱신이 비정상으로 멈추면 아무 파일도 쓰이지 않는다 — 처리는 quant-data `CLAUDE.md`. 갱신에서 `--exclude` 로 뺀 종목은 옛 끝날에 머물러, 그 종목의 합성이 든 결과의 끝날도 거기 묶인다 — 함께 쓰는 합성끼리 겹치는 기간으로 에러 없이 짧아진다(예: QQQ 를 빼면 QQQ 합성은 옛 끝날 · TQQQ 합성은 새 끝날이라, QQQ 신호로 TQQQ 를 사고파는 결과가 QQQ 의 옛 끝날에서 끝난다). 파일별 끝날은 `storage/stock/quant_data_edition.json`.

**② 결과 러너** — 블록의 줄 순서대로 돈다. 하나가 실패하면 뒤는 돌지 않는다(`set -e` 는 괄호 안 하위 셸에만 걸린다). 블록 안에는 주석을 두지 않는다 — 주석 옵션(`interactivecomments`)이 꺼진 대화형 zsh 는 `#` 줄을 명령으로 읽어 첫 줄에서 멈춘다.

```bash
(
  set -e
  poetry run python scripts/backtest/run_single_backtest.py
  poetry run python scripts/backtest/run_walkforward.py
  poetry run python scripts/backtest/run_param_plateau_all.py
  poetry run python scripts/backtest/run_portfolio_backtest.py
)
```
