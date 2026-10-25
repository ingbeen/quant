# QBT 프로젝트 가이드라인

@docs/MEMORY.md

---

## 계획서 규약 — 이 프로젝트의 설정 (CRITICAL)

- **Scope 에 `README.md` 를 함께 적습니다.** 다른 저장소는 `docs/COMMANDS.md` 만 요구합니다 — README 를 함께 보는 것은 QBT 의 규칙입니다.
- **별도의 설계 문서나 `docs/ROADMAP.md` 가 없습니다.** 설계 결정·탈락안·Phase 상태를 남길 곳이 필요하면 `docs/research/` 의 보고서 본문에 씁니다.

---

## 프로젝트 개요

QBT(Quant BackTest)는 주식 백테스팅 CLI 도구입니다 (`src/qbt/`). 기능 소개는 [README.md](README.md)에 있습니다.

- 주요 라이브러리: pandas, yfinance, Plotly, Streamlit, streamlit-lightweight-charts-v5 (`vendor/` 포크)

---

## 디렉토리 구조

```
quant/
├── src/qbt/    # 패키지 소스 코드 — backtest · tqqq · utils (상세: src/qbt/CLAUDE.md)
├── tests/      # 테스트 코드 (상세: tests/CLAUDE.md)
├── scripts/    # CLI 스크립트 — data · backtest · tqqq (상세: scripts/CLAUDE.md)
├── docs/       # 문서 — plans/ 계획서 · research/ 연구 보고서 (상세: docs/CLAUDE.md)
├── storage/    # 데이터 저장소 (stock, etc, results)
└── vendor/     # 서드파티 포크 (streamlit-lightweight-charts-v5)
```

---

## 스크립트 실행 규칙

`scripts/` 폴더의 스크립트는 **AI 모델이 직접 실행할 수 있습니다**(대시보드는 예외 — 아래).
실행 명령은 [docs/COMMANDS.md](docs/COMMANDS.md)를 따릅니다.

실행 전 확인 사항:

- **대시보드(`app_*.py`)는 사용자가 직접 실행합니다.** AI 모델은 실행 명령과 볼 지점만 안내합니다.
  분석에 필요한 수치는 **대시보드가 읽는 `storage/results/` 의 CSV·JSON 을 직접 계산해** 얻습니다.
  그 편이 정확하고, 화면 없이도 검증됩니다.
  - **왜**: Streamlit 앱은 종료 시점이 없는 상주 프로세스이고, 사용자가 이미 띄워둔 포트와 충돌합니다.
    `[실측] 2026-08-30` 8501 에 `app_portfolio_backtest.py` 가 떠 있어 기동에 실패했습니다.
    화면을 보는 주체도 사용자이므로, AI 가 띄우면 프로세스만 남고 판단은 사용자에게 전달되지 않습니다.
- **수 분 걸리는 러너가 있습니다** — 소요는 COMMANDS 의 각 명령에 적혀 있고, 적혀 있지 않은 백테스트 러너는 1분 이내입니다. Bash 기본 제한 시간을 넘는 것은 제한 시간을 늘리거나 백그라운드로 돌립니다.
- **결과 파일은 덮어써집니다.** `storage/results/` 는 git 추적 대상이므로 되돌릴 수 있으나,
  실행 전 작업 트리 상태를 확인합니다.
- **`download_data.py` 는 결과 비교 중일 때 함부로 실행하지 않습니다.** 데이터가 갱신되면
  결과 변화의 원인이 코드 변경인지 데이터 추가인지 분리할 수 없게 됩니다.

---

## 이 프로젝트의 개발 원칙

- **확장성**: 도메인별 모듈 독립성 유지 (`backtest`·`tqqq`·`utils` 경계)

### 가격 반올림 자릿수 — 출력은 집행 완료, 입력은 미이행 `2026-09-09`

전역 `~/.claude/rules/python.md` 의 가격 기준(**4자리 상한**)을 이 저장소는 **결과 파일(출력)에만 집행했고, 수집·합성 데이터(입력)는 6자리로 남겼다.**

| 구분 | 지점 | 값 |
|---|---|---|
| **출력 — 집행 완료** | `src/qbt/common_constants.py` `ROUND_PRICE` (모든 결과 저장 경로가 경유) | `4` |
| **입력 — 미이행** | `src/qbt/utils/stock_downloader.py` `ROUND_INPUT_PRICE` — 다운로더와 합성 · 대용 · 장기 대체 생성 스크립트가 모두 그 모듈의 `save_stock_csv` 로 저장한다 | `6` |

**왜 입력만 남겼는가.** 출력 자릿수는 저장 직전 복사본에만 걸려 **성과 지표를 바꾸지 않는다**(재실행 전후 결과 필드 대조에서 차이 0건). 반면 입력 자릿수는 백테스트의 계산 입력 자체를 바꾸므로 **CAGR·MDD·Calmar 가 전부 미세하게 달라지고 `docs/research/` 의 기록이 재현되지 않는다.** 게다가 재다운로드하면 최신 데이터가 함께 유입되어 「자릿수 효과」와 「데이터 추가 효과」를 분리할 수 없다. 4자리를 정한 근거(사용자가 **결과**를 차트와 대조할 때 방해된다)는 출력만으로 달성된다.

- **입력 쪽 6자리는 버그가 아니라 «의도된 미이행»이다.** 발견해도 조용히 고치지 않는다.
- **자릿수는 위 표의 상수로만 적는다.** 저장 지점에 숫자를 직접 적은 코드는 `round(…, 6)` 검색에 걸리지 않아 자릿수를 바꿀 때 조용히 누락된다(실제로 겪었다). `tests/qbt/test_rounding_policy.py` 가 상한을 고정한다.
