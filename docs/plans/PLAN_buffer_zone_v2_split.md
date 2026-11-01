# Implementation Plan: 버퍼존 V2 · 스플릿 매매 추가와 단일 백테스트 전략 목록 정리

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-01 01:12
**마지막 업데이트**: 2026-11-01 10:10
**관련 범위**: backtest(전략 · 엔진 · 러너 · 대시보드 차트), common_constants, scripts/backtest, tests, docs
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md, docs/CLAUDE.md, docs/COMMANDS.md

---

## 1) 목표(Goal)

- [x] 목표 1: 버퍼존 V2 를 QQQ · QLD · TQQQ · GLD · TLT 다섯 전략으로 `run_single_backtest.py` 에 추가한다
- [x] 목표 2: 스플릿 매매를 TQQQ 합성 전 구간과 2004년 시작, 두 전략으로 추가한다
- [x] 목표 3: 기존 버퍼존 · Buy & Hold 에 QLD 를 추가하고 UGL · UBT 4개를 뺀다
- [x] 목표 4: 새 전략과 QLD 가 `app_single_backtest.py` 탭으로 표출된다
- [x] 목표 5: 같은 시세에서 기존 전략 결과는 코드 변경으로 한 글자도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- 워크포워드 · 파라미터 고원 · 포트폴리오에 V2 · 스플릿 · QLD 추가
- 파라미터 튜닝 (밴드 · 21거래일 · 5% · 30칸은 사용자가 정한 값이다)
- 2004년 시작 Buy & Hold 탭 — 사용자가 스플릿만 요청했다. 비교 수치는 보고서에 남긴다
- 현금 이자, 손절선의 차트 표시, 칸 번호 열
- `run_param_plateau_all.py` 재실행 — 고원 CSV 의 UGL · UBT 행은 다음 재실행 때 사라진다
- `download_data.py` 실행, 시세 파일 · 다운로드 목록 · 연구 문서 §49 ~ §50 변경
- 전략 채택 판단 — 이 계획은 결과를 만들고 기록까지 한다

## 3) 배경/맥락(Context)

### 사용자 요청과 결정 (2026-11-01)

**버퍼존 V2 규칙** — 신호와 매매는 같은 티커, 이평선 200일(SMA), 밴드는 상단 · 하단 모두 5% × 레버리지 배수

| 전략 | 시세 | 밴드 |
|---|---|---|
| QQQ | `QQQ_max.csv` | 5% |
| QLD | `QLD_synthetic_max.csv` | 10% |
| TQQQ | `TQQQ_synthetic_max.csv` | 15% |
| GLD | `GLD_max.csv` | 5% |
| TLT | `TLT_max.csv` | 5% |

| 단계 | 규칙 |
|---|---|
| 한달 | 돌파일을 1일째로 세어 **21거래일** (Q2). 저장소 관용 `TRADING_DAYS_PER_YEAR // 12` (`allocators/haa.py:24`) |
| 닿음 | **종가 기준** (Q3). 매수 대기는 종가 ≤ 이평선, 매도 대기 · 손절선은 종가 ≥ 이평선 |
| 매수 돌파 | 전일 종가 ≤ 전일 상단 AND 당일 종가 > 당일 상단 (`detect_buy_signal`) |
| 매수 대기 | 1 ~ 21일째 종가가 이평선에 닿으면 취소. 밴드 안으로 돌아와도 닿지 않으면 계속 센다 |
| 매수 신호 | 21일째를 포함해 그 이후 처음으로 종가 < 상단인 날. 다음 날 시가 체결. 21일째가 지난 뒤에는 닿아도 취소하지 않는다 |
| 매도 돌파 | 전일 종가 ≥ 전일 하단 AND 당일 종가 < 당일 하단 (`detect_sell_signal`) |
| 매도 대기 | 1 ~ 21일째 종가가 이평선에 닿으면 취소. 닿지 않고 21일째가 끝나면 손절선 = 그 기간 **장중 저가**의 최저 |
| 손절 | 다음 날부터 저가 < 손절선이면 그 가격에 **장중 체결**. 시가가 이미 아래면 시가에 체결. 대기 중에는 손절하지 않고, 손절 말고 다른 매도는 없다 |
| 손절선 해제 | 손절선이 있는 동안 종가가 이평선에 닿으면 취소 (Q1). 다시 하향돌파하면 새로 센다. 손절선이 살아 있는 동안의 새 하향돌파는 무시한다 |

**스플릿 매매 규칙** — 합성 TQQQ, 전 구간(1999-03-10 시작)과 2004년 시작(첫날 2004-01-02) 두 전략 (Q4)

| 항목 | 규칙 |
|---|---|
| 고점 | 시작일부터 누적한 최고 종가. 칸이 모두 비어 있을 때 새 최고 종가가 나오면 갱신. 2004년 시작은 2004년 첫 종가부터 센다 (2000년 고점을 이어받으면 첫날 30칸이 다 찬다) |
| 칸 가격 | k번째 칸의 매수가 = 고점 × 0.95^k, 매도가 = 고점 × 0.95^(k-1). 칸은 1번부터 순서대로 차고, 깊은 칸부터 팔린다 |
| 체결 | **장중 지정가** (Q6). 저가 · 고가가 그 가격에 닿으면 그 가격에 체결 (`≤` · `≥`). 시가가 건너뛰면 시가에 체결하고 칸 가격은 그대로 둔다 |
| 같은 날 순서 | **캔들 방향** (Q8). 양봉(종가 ≥ 시가)은 시가 → 저가 → 고가 → 종가, 음봉은 시가 → 고가 → 저가 → 종가 |
| 금액 | **사이클 복리** (Q5). 칸이 모두 빈 상태에서 첫 칸을 살 때 칸 금액 = 그때 자산 ÷ 30, 다시 모두 빌 때까지 고정 |
| 30칸 이후 | 추가 매수 · 손절 없음. 30번째 칸은 29번째 칸의 매수가까지 버틴다 |
| 비용 | 매수 · 매도 각 `SLIPPAGE_RATE` (기존 모델). 현금 이자 0. 첫날은 고점만 기록한다 |

**목록 정리**: QLD 버퍼존은 QQQ 신호 + QLD 합성 매매 + 기존 4P, QLD Buy & Hold 는 QLD 합성. UGL · UBT 는 `CONFIGS` · 고원 러너 · 경로 상수 · 결과 폴더 · 테스트에서 뺀다 (Q7)

### 왜 엔진을 나누는가

- **V2 는 `run_backtest` 를 쓴다.** 매수는 기존 「종가 신호 → 다음 날 시가」 그대로이고, 다른 것은 손절 한 곳이다. 복제하면 체결 · 기록 코드가 두 벌이 된다
- **스플릿은 새 엔진이 필요하다.** `run_backtest` 는 「최대 1 포지션 + 다음 날 시가」 라 칸마다 다른 진입가 · 장중 지정가를 담지 못한다

### 실측 근거 (2026-11-01 01:11, 커밋 `91ffb6c` 의 시세 — 끝 2026-10-29, 저장소 밖 임시 코드)

지표 계산은 Buy & Hold 4개를 2026-09-24 로 잘라 돌렸을 때 저장소 `summary.json` 의 CAGR · MDD 와 일치했다. 전략 규칙 부분은 테스트 전 임시 코드다.

**V2 기대값** (CAGR / MDD / 끝난 거래 수 / 마지막 보유 진입일)

| | 결과 | 비교: 기존 버퍼존 (끝 2026-09-24) |
|---|---|---|
| QQQ | 10.30% / -34.54% / 4 / 2023-03-06 | 9.61% / -30.26% / 14 |
| QLD | 16.75% / -51.72% / 5 / 2023-10-23 | 없음 |
| TQQQ | 19.74% / -69.92% / 5 / 2023-05-03 | 17.57% / -74.67% / 14 |
| GLD | 9.99% / -26.41% / 5 / 보유 없음 | 7.64% / -41.12% / 11 |
| TLT | 0.91% / -38.99% / 8 / 2025-11-12 | 1.15% / -31.56% / 11 |

신호 날 종가가 이평선 이하였던 사례와, 21일째 뒤 종가가 이평선에 닿은 사례는 다섯 전략 모두 0건이다 — 「21일째 뒤에는 닿아도 취소하지 않는다」가 결과를 바꾼 적이 없다.

**한달 길이 민감도** (확정 규칙에서 길이만 바꿈, CAGR / MDD / 끝난 거래 수): 22거래일은 21거래일과 비슷하고 20거래일만 크게 달라진다. 값을 고르려는 표가 아니라 거래 하나가 결과를 좌우한다는 근거다.

| | 20거래일 | 21거래일 | 22거래일 |
|---|---|---|---|
| QQQ | 12.06% / -32.37% / 4 | 10.30% / -34.54% / 4 | 10.32% / -34.54% / 4 |
| QLD | 13.55% / -52.71% / 7 | 16.75% / -51.72% / 5 | 16.65% / -51.72% / 5 |
| TQQQ | 11.85% / -73.10% / 8 | 19.74% / -69.92% / 5 | 19.65% / -69.92% / 5 |
| GLD | 9.97% / -26.40% / 5 | 9.99% / -26.41% / 5 | 9.88% / -28.94% / 5 |
| TLT | 0.97% / -38.68% / 8 | 0.91% / -38.99% / 8 | 0.89% / -38.89% / 8 |

**스플릿 기대값** (사이클 복리, 추천 순서: CAGR / MDD / 끝난 거래 수)

| | 결과 | 같은 구간 B&H | 평균 칸 | 빈 날 | 30칸 찬 날 | 마지막 칸 수 |
|---|---|---|---|---|---|---|
| 전 구간 | 1.15% / -72.02% / 383 | 2.18% / -99.98% | 28.7 | 1.1% | 92.1% | 25 |
| 2004년 시작 | 8.96% / -72.15% / 1,183 | 24.16% / -94.7% | 8.5 | 13.4% | 5.6% | 4 |

고점 기준 칸 가격 대조: 100 기준 30회차 21.4639, 29회차 22.59355 (요청의 값과 같다). 합성 최고 종가 249.4793(2000-03-27), 30번째 칸 53.5479, 최저 종가 0.048248(2009-03-09), 마지막 종가 69.26 — 전 구간은 2001 ~ 2024년 내내 30칸이 차 있다.

**같은 날 순서 (Q8)**: 하루에 매수가와 매도가가 다 닿은 날의 처리

| 순서 | 전 구간 | 2004년 시작 | 같은 날 사고 판 칸 (전 구간 / 2004) |
|---|---|---|---|
| 캔들 방향 (추천) | 1.15% / -72.02% / 383 | 8.96% / -72.15% / 1,183 | 97 / 119 |
| 항상 고가 먼저 | 1.84% / -65.55% / 501 | 9.96% / -70.39% / 1,339 | 176 / 199 |
| 항상 저가 먼저 | 2.09% / -62.46% / 553 | 10.80% / -66.70% / 1,480 | 319 / 506 |
| 같은 날 왕복 없음 (매도 우선) | 1.89% / -62.52% / 321 | 9.26% / -70.95% / 1,117 | 0 / 0 |

### 재사용 함수 호출처 (정의 제외, `src` · `scripts` grep)

| 함수 | 실제 호출 | 쓰는 곳 |
|---|---|---|
| `run_backtest` | 7곳, 테스트 3곳 | V2 — 손절 칸을 더한다 (아래 Scope) |
| `execute_buy_order` | 2곳, 테스트 4곳 | V2(엔진 경유) · 스플릿 |
| `execute_sell_order` | 3곳, 테스트 10곳 | 손절 · 스플릿 |
| `create_trade_record` | 1곳, 테스트 2곳 | 스플릿 |
| `record_equity` | 2곳, 테스트 0곳 | 스플릿 |
| `calculate_summary` | 5곳, 테스트 12곳 | 스플릿 |
| `compute_bands` | 2곳, 테스트 5곳 | V2 |
| `detect_buy_signal` · `detect_sell_signal` | 각 1곳, 테스트 0곳 — `BufferZoneStrategy` 만 부른다. 식이 한 줄이고 V2 의 돌파 정의와 같아 재사용하며, 새 테스트가 V2 를 통해 고정한다 | V2 |
| `enrich_equity_with_bands` | 2곳, 테스트 2곳 | V2 |
| `add_single_moving_average` · `filter_valid_rows` | 7곳 · 4곳 | V2 |
| `build_trade_markers` | 3곳, 테스트 4곳 (`open_entry_date` 인자는 앱 2곳 · 테스트 1곳) | 인자를 여러 날짜로 넓힌다 |

`scripts/` 를 import 하는 테스트는 0건이다 — 러너 등록 · 저장 · 앱 변경은 pytest 로 잡히지 않으므로 Phase 3 의 실행 대조로 검증한다.

`CONFIGS` 는 `run_single_backtest.py` 외에 `app_single_backtest.py` 가 읽고, `get_config` 는 `run_param_plateau_all.py:150` · `run_walkforward.py:357` 이 부른다. 워크포워드 대상은 TQQQ · QQQ 뿐이라 영향이 없고, 고원은 `_ASSET_CONFIGS` 두 줄을 함께 뺀다.

**관련 과거 결정**: `docs/research/전략_검증_보고서.md` §25 가 기각한 「분할」은 이동평균 150 · 200 · 250 3분할이라 이 사다리 매매와 다른 전략이다. §25.6 자유도 경고는 그대로 유효하다 — 값을 고르지 않는다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」, 「가격 반올림 자릿수」, `docs/MEMORY.md`
- `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`
- `tests/CLAUDE.md`, 전역 `~/.claude/rules/python.md`, `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] V2 다섯 전략과 스플릿 두 전략이 결과 폴더를 만들고, 실행 결과가 Context 기대값과 일치한다 (다르면 원인을 찾아 기록한다)
- [x] 규칙 대조: 다섯 V2 전략에서 끝난 거래마다 청산가 = 손절선(또는 시가) × (1 - `SLIPPAGE_RATE`) 이고, 스플릿 끝난 거래마다 청산가 ÷ 진입가 ≥ 0.997 ÷ (0.95 × 1.003) 이다
- [x] 에쿼티 대조: 스플릿 최종 자본 = 초기 자본 + 거래 손익 합 + 미청산 칸 평가 손익 (오차 0.01 이내), `open_lots` 주수 합 = 마지막 `position`
- [x] 같은 시세에서 기존 전략 9개 결과 파일이 Phase 0 기준값과 바이트까지 같다
- [x] QLD 버퍼존 · Buy & Hold 결과가 생기고 UGL · UBT 결과 폴더 · 설정 · 상수 · 참조가 코드에서 사라진다 (`grep` 0건, 연구 문서 · 다운로드 목록 · 시세 파일 제외)
- [x] 고원 러너의 자산 이름이 모두 `get_config` 로 풀린다
- [x] `app_single_backtest.py` 가 18개 탭을 예외 없이 그린다 (일회성 `AppTest`)
- [x] 회귀/신규 테스트 추가 (V2 상태 전이 · 손절 체결 · 스플릿 칸 · 순서 · 금액 · 설정 표 · 마커)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 (`docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md` 는 변경 없음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (`docs/research/전략_검증_보고서.md` 부록 N 에 규칙 · 결정 · 탈락안 · 실측)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」) → **해당 없음** — 고치지 않은 지적은 전부 거르는 기준에 들었다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**새 파일**

- `src/qbt/backtest/strategies/buffer_zone_v2.py` — `BufferZoneV2Config`(이름 · 시세 · 결과 폴더 · 배수), `CONFIGS`, 상수(기본 밴드 · 이평선 · 한달), `BufferZoneV2Strategy`. `check_sell` 은 늘 False 이고 손절선을 세우기만 한다
- `src/qbt/backtest/strategies/split_ladder.py` — `SplitLadderConfig`(이름 · 시세 · 결과 폴더 · 시작일), `CONFIGS`, 상수(하락 폭 · 칸 수)
- `src/qbt/backtest/engines/split_engine.py` — `run_split_backtest(df, initial_capital, drop_pct, max_lots)`. 상태는 고점 + 칸 스택(후입선출) + 칸 금액. 체결 · 기록 · 요약은 `execute_*_order` · `create_trade_record` · `record_equity` · `calculate_summary` 재사용
- `tests/qbt/test_buffer_zone_v2.py`, `tests/qbt/test_split_engine.py`

**고치는 파일**

- `src/qbt/backtest/strategies/strategy_common.py` — `IntradayStopStrategy` Protocol (`stop_price() -> float | None`). `SignalStrategy` 는 그대로 — 기존 전략 · 포트폴리오 엔진을 고치지 않는다
- `src/qbt/backtest/engines/backtest_engine.py` — `run_backtest` 에 장중 손절 칸 (시가 체결 뒤 · 에쿼티 기록 앞). 전략 종류 판정은 루프 밖에서 하고 전략이 바뀔 때만 다시 한다 (그리드 서치 일별 루프에 비용을 더하지 않는다). 손절 전략인데 매매 시세에 `Low` 가 없으면 `ValueError`. 매도 체결 · 기록은 예약 매도와 한 곳을 쓴다
- `src/qbt/backtest/engines/engine_common.py` — `execute_buy_order` · `execute_sell_order` 의 인자 `open_price` 를 `price_raw` 로 (이제 손절가 · 지정가도 받는다 — 호출은 전부 위치 인자라 호출부는 그대로), docstring
- `src/qbt/backtest/engines/__init__.py` — 패키지 docstring 에 스플릿 엔진
- `src/qbt/backtest/strategies/buffer_zone.py` — UGL · UBT 설정과 import 제거, `buffer_zone_qld` 추가
- `src/qbt/backtest/strategies/buy_and_hold.py` — UGL · UBT 설정과 import 제거, `buy_and_hold_qld` 추가
- `src/qbt/backtest/strategies/__init__.py` — 모듈 목록 docstring
- `src/qbt/common_constants.py` — `UGL_DATA_PATH` · `UBT_DATA_PATH` 제거 (이 변경으로 호출 0건)
- `src/qbt/backtest/runners.py` — `create_buffer_zone_v2_runner` · `create_split_runner`, docstring
- `src/qbt/backtest/types.py` — `SummaryDict.open_lots: NotRequired[list[OpenPositionDict]]`
- `src/qbt/backtest/dashboard_charts.py` — `build_trade_markers` 의 `open_entry_date` 를 `open_entry_dates: Sequence[str] = ()` 로
- `scripts/backtest/run_single_backtest.py` — 두 설정 목록 등록, `_save_summary_json` 에 `open_lots`, docstring
- `scripts/backtest/app_single_backtest.py` — 두 설정 목록 탐색, 미청산 칸 마커, 「보유 중인 칸」 표, docstring
- `scripts/backtest/app_portfolio_backtest.py` — 바뀐 마커 인자 한 줄 (동작 같음)
- `scripts/backtest/run_param_plateau_all.py` — `_ASSET_CONFIGS` 두 줄 제거
- `tests/qbt/test_buy_and_hold.py` — UGL · UBT 기대 제거, QLD 추가
- `tests/qbt/test_buffer_zone.py` — QLD 설정 계약, UGL · UBT 부재
- `tests/qbt/test_dashboard_charts.py` — 마커 인자, 여러 미청산 칸
- `tests/qbt/test_strategy_interface.py` — 기존 전략이 `IntradayStopStrategy` 가 아님을 고정
- `README.md` — 기능 소개에 V2 · 스플릿
- `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md` (모듈 지도, 도메인 규칙 3 · 5 의 예외: V2 손절 · 스플릿 지정가 · 다중 칸), `src/qbt/CLAUDE.md` (상태를 갖는 예외에 `BufferZoneV2Strategy`)
- `docs/research/전략_검증_보고서.md` — 부록 N, 목차 한 줄
- `docs/COMMANDS.md`: **변경 있음** — 항목 2 의 설명 줄(비교 대상 · 선행 합성에 QLD). 실행 명령과 CLI 옵션은 그대로 (`--strategy` 선택지는 `--help` 가 정본)

**바꾸지 않는 것**: `BufferZoneStrategy` · `BuyAndHoldStrategy`, 포트폴리오 엔진 · 설정, 워크포워드, `strategy_registry.py`, 시세 파일, `download_data.py`

### 데이터/결과 영향

- 신규: `storage/results/backtest/` 의 `buffer_zone_v2_{qqq,qld,tqqq,gld,tlt}` · `split_tqqq` · `split_tqqq_2004` · `buffer_zone_qld` · `buy_and_hold_qld`
- 삭제: `buffer_zone_ugl` · `buffer_zone_ubt` · `buy_and_hold_ugl` · `buy_and_hold_ubt` — 파일 4개씩, git 추적 중이라 되돌릴 수 있다
- 갱신: 기존 9개 결과의 끝이 2026-09-24 에서 2026-10-29 로 바뀌고 과거 행도 달라진다. **코드가 아니라 시세 커밋 때문이다** — Phase 0 기준값으로 코드 영향이 0 임을 분리한다
- `summary.json` 에 스플릿 전용 `open_lots` 가 생긴다. 스플릿은 `open_position` 을 쓰지 않는다 (칸마다 진입가가 달라 한 줄로 합치면 평균이 진입가처럼 읽힌다)
- 작업 트리는 `91ffb6c` 기준 깨끗하다

## 6) 단계별 계획(Phases)

### Phase 0 — 기준값 확보와 계약 테스트(레드)

**작업 내용**:

- [x] 변경 전 코드로 `run_single_backtest.py` 전체를 실행하고 기존 결과 폴더를 scratchpad 에 기준값으로 복사한다 (이 실행이 시세 효과를 흡수한다)
- [x] `test_buffer_zone_v2.py` 상태 전이 — `month_days=3` 짧은 합성 표로 고정:
      신호일과 다음 날 시가 체결 · 21일째까지 상단 위면 대기, 처음 상단 아래인 날 신호 · 종가 닿으면 취소, 재돌파에 1부터 · 저가만 닿으면 취소 안 됨(Q3) · 밴드 안 복귀는 계속 셈 · 21일째 뒤 닿아도 취소 안 됨 · 손절선 = 장중 저가 최저(돌파일 포함, 종가 아님) · 대기 중 취소 · 손절선 해제와 재돌파(Q1) · 손절선 있는 동안 새 돌파 무시 · `check_sell` 늘 False · 범위 밖 생성자 `ValueError`
- [x] `test_buffer_zone_v2.py` 엔진 — 손절가 체결과 슬리피지 손계산 · 시가 갭은 시가 체결 · 저가 = 손절선은 미체결 · 세운 날에는 작동 안 함 · 손절 뒤 에쿼티 = 현금, 같은 날 종가 신호는 정상 · 마지막 날 손절 · `Low` 없으면 `ValueError`, 기존 전략은 `Low` 없어도 동작
- [x] `test_buffer_zone_v2.py` 설정 표 — 배수 · 밴드 · 시세 경로를 숫자와 상수로 고정 (`{"qqq": 0.05, "qld": 0.10, "tqqq": 0.15, "gld": 0.05, "tlt": 0.05}`), 21 숫자 고정, **네 설정 목록을 합쳐** 전략 이름 · 결과 폴더 겹침 없음 (`STRATEGY_RUNNERS` 는 딕셔너리라 겹치면 조용히 덮어쓴다)
- [x] `test_split_engine.py` — 100 기준 95 · 90.25 · 85.7375 체결 · 매도가는 앞 칸 매수가(후입선출) · 첫날 매매 없음 · 양봉 · 음봉 순서 손계산(서로 다른 결과) · 같은 날 왕복 · 시가 갭 매수 · 매도 · 하루 여러 칸 · 칸 한도 뒤 추가 매수 없음 · 30칸 21.4639 / 22.59355 · 사이클 복리(사이클 안 고정, 모두 비면 재계산, 주수 내림 손계산) · 고점 갱신은 빈 상태에서만 · 에쿼티 전 행 · `open_lots` 내용 · 시작일 자르기와 고점(러너) · 입력 검증 · 금액 부족이면 칸을 건너뛰지 않고 다음 날 재시도
- [x] `test_dashboard_charts.py` · `test_buy_and_hold.py` · `test_buffer_zone.py` · `test_strategy_interface.py` 계약 추가 · 수정

**Validation**:

- [x] 새 계약 테스트가 구현 전이라 실패하는 것을 확인한다 (특정 파일 `pytest`)

> 테스트를 먼저 모아 쓰므로, 아직 구현하지 않은 Phase 의 테스트는 그 Phase 까지 레드로 남는다. 각 Phase 는 자기 범위의 테스트 파일과 기존 테스트만 그린으로 본다.

---

### Phase 1 — 버퍼존 V2 구현(그린 유지)

**작업 내용**:

- [x] `strategy_common.py` Protocol, `buffer_zone_v2.py`, `backtest_engine.py` 손절 칸, `engine_common.py` 인자 이름, `runners.py` V2 러너

**Validation**:

- [x] V2 테스트 전부 통과, 기존 엔진 · 버퍼존 테스트 통과 (특정 파일 `pytest`)

---

### Phase 2 — 스플릿 구현(그린 유지)

**작업 내용**:

- [x] `split_ladder.py`, `split_engine.py`, `runners.py` 스플릿 러너, `types.py` `open_lots`
- [x] 도달 불가 조건은 `RuntimeError` 로 막는다 — 보유 중 새 최고 종가, 칸 금액이 현금 초과. 추천 순서 기준으로 임시 코드 두 구간 모두 보유 중 새 최고 종가 0건이다

**Validation**:

- [x] 스플릿 테스트 전부 통과 (특정 파일 `pytest`)

---

### Phase 3 — 목록 정리 · 등록 · 실행 대조

**작업 내용**:

- [x] `buffer_zone.py` · `buy_and_hold.py` · `common_constants.py` · `run_param_plateau_all.py` 정리와 QLD 추가, `strategies/__init__.py`
- [x] `run_single_backtest.py` 등록과 `open_lots` 저장, `dashboard_charts.py` 인자, `app_single_backtest.py` · `app_portfolio_backtest.py`
- [x] UGL · UBT 결과 폴더 4개 삭제
- [x] `run_single_backtest.py` 전체 실행 — 다른 러너 · 다운로드는 돌리지 않는다
- [x] 일회성 화면 확인: `streamlit.testing.v1.AppTest` 로 scratchpad 에서 앱을 돌린다. 서버 · 포트를 쓰지 않고 저장소 테스트로 넣지 않는다 (사용자 승인 2026-11-01). 커스텀 차트 컴포넌트가 `AppTest` 에서 막히면 그 사실을 기록하고 차트 설정 함수를 전략별로 직접 불러 대신 확인한다

**Validation**:

- [x] 기존 9개 전략 결과 파일(`signal` · `equity` · `trades` · `summary`)이 Phase 0 기준값과 바이트까지 같다
- [x] V2 · 스플릿 지표와 거래 수가 Context 기대값과 일치한다
- [x] V2 다섯 전략의 끝난 거래를 원본 시세에서 따로 재계산해 대조한다 — 돌파일 · 21거래일 동안 종가가 이평선에 닿지 않음 · 최저 저가 = 손절선 · 첫 저가 이탈일 = 청산일 · 청산가
- [x] 스플릿: 청산가 ÷ 진입가 하한, 최종 자본 항등식, `open_lots` 주수 합 = 마지막 `position`, 행 수 = 시세 행 수(잘린 구간은 2004년 이후 행 수를 따로 세어 맞춤)
- [x] 고원 러너 `_ASSET_CONFIGS` 이름이 모두 `get_config` 로 풀린다 (결과를 쓰지 않는 일회성 확인)
- [x] `grep` — 코드 · 테스트 · 스크립트에 `UGL` · `UBT` 참조는 다운로드 목록뿐이다
- [x] 18개 탭 이름과 예외 0건을 확인한다
- [x] `git status` — Scope 밖 변경 0건, 끝난 뒤 streamlit 상주 프로세스 0개

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 업데이트: `docs/COMMANDS.md`(변경 있음) · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- [x] 근거 승격: `docs/research/전략_검증_보고서.md` 부록 N — 규칙 · 사용자 결정(Q1 ~ Q8) · 탈락안과 수치 · 실행 결과 · 거래 수의 한계 · 일별 데이터로 장중 순서를 모른다는 한계
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] 사용자용 대시보드 확인 안내: 실행 명령과 볼 지점 (AI 는 띄우지 않는다)
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 15건 — 버그 5 [무거움 3 · 가벼움 2] · 그 외 10 · 조치: 고칠 것 0. 무거움 3 은 닿지 않음. 이 계획 때문에 사실과 달라진 문서 3건만 수정)
- [x] 수정분 검증 — 해당 없음 (마지막 회차에 고친 버그 없음)
- [x] `poetry run python validate_project.py` (passed=994, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 버퍼존 V2 · 스플릿 매매 추가와 단일 백테스트 전략 목록 정리
2. 백테스트 / 한달 대기와 장중 손절의 버퍼존 V2, 합성 TQQQ 30칸 스플릿 매매 추가
3. 백테스트 / 단일 백테스트에 버퍼존 V2 5종 · 스플릿 2종 · QLD 2종 추가, UGL · UBT 4종 제거와 대시보드 18개 탭 표출
4. 백테스트 / run_backtest 장중 손절 칸과 새 스플릿 엔진으로 시가 체결 밖 매매 지원, 기존 전략 결과의 코드 영향 0 확인
5. 백테스트 / 신호와 매매를 같은 티커로 하는 버퍼존 V2와 사다리 매매 구현, 규칙 · 버린 안 · 한계의 부록 N 기록

## 7) 리스크(Risks)

- **결과의 통계적 신뢰가 낮다** — V2 는 전략마다 끝난 거래가 4 ~ 8건이고 거래 하나가 좌우한다 (TQQQ 2012-05-17 ~ 2018-12-17 +914.81%, 21거래일 19.74%, 20거래일 11.85%). 완화: 보고서에 기록하고 값을 고르지 않는다
- **공유 엔진 `run_backtest` 변경** — 호출 7곳(그리드 · 워크포워드 포함). 완화: 전략 판정으로 분기를 막고, 기존 결과 바이트 대조와 기존 테스트로 확인한다
- **`build_trade_markers` 인자 변경** — 포트폴리오 앱 한 줄이 함께 바뀐다. 완화: 값이 같은 호출로 옮기고 테스트로 고정한다
- **장중 순서를 모른다** — 일봉에는 순서가 없어 스플릿 CAGR 이 가정에 따라 전 구간 1.15 ~ 2.09%, 2004년 시작 8.96 ~ 10.80% 로 달라진다. 완화: 사용자가 Q8 로 정하고 네 안의 수치를 보고서에 남긴다
- **지정가 체결은 낙관적이다** — 저가가 닿았다고 실제로 다 체결되지는 않는다. 비용 0.3% 를 그대로 두어 일부 상쇄한다. 완화: 보고서에 기록
- **상장 전 고가 · 저가는 시뮬레이션이다** — V2 손절선과 스플릿 체결이 그 값을 쓴다 (QLD 2006-06-21 전, TQQQ 2010-02-11 전). 완화: 보고서에 기록
- **현금 이자 0** — 스플릿은 현금 비중이 커서(2004년 시작 평균 8.5칸) 불리하게 나온다. 기존 전략과 같은 가정을 유지한다
- **대시보드가 무거워진다** — 탭 18개, `split_tqqq_2004` 마커 2,300개 이상. 완화: 사용자가 확인한다. 느리면 다음 판단 대상이지 이번 범위가 아니다
- **고원 CSV 의 UGL · UBT 행이 남는다** — 다음 재실행 때 사라지고, 그때까지 고원 앱에 그려진다. 사용자 선택 범위 안이다
- **다른 PC** — 삭제된 결과 폴더와 새 결과는 같은 커밋으로 넘어간다
- **검증 중 시세 재다운로드** — 대조가 깨진다. 완화: 작업 중 `download_data.py` 를 돌리지 않는다

## 8) 메모(Notes)

### 결정

- 2026-11-01 사용자 결정 — Q1 손절선은 이평선에 닿으면 취소 · Q2 21거래일 · Q3 닿음은 종가 기준, 손절만 장중 가격 · Q4 합성 전 구간 + 합성 2004년 시작 · Q5 사이클 복리 · Q6 장중 지정가 · Q7 고원 러너에서도 UGL · UBT 제거. 그 밖의 읽은 내용은 「언급 없는 것은 추천대로」
- 2026-11-01 사용자 요청: `app_single_backtest` 까지 표출
- 2026-11-01 사용자 결정 — Q8 스플릿의 같은 날 순서는 캔들 방향(네 안 중 CAGR 이 가장 낮아 보수적이다), Q9 일회성 `AppTest` 승인, 계획 승인 (「전부 추천대로」)
- 탈락안 — Q1 손절선 유지(QQQ 는 2011-09-06 의 43.8059 가 2026-10-29 까지 남아 2022년 하락에도 안 판다) · 저점을 종가 최저로(말씀은 「장중 저가가 저점을 하향돌파」) · 칸 가격을 실제 체결가에서 잇기(요청의 100 기준 사다리와 어긋난다) · 스플릿을 `run_backtest` 에 얹기(1 포지션 전제) · V2 전용 엔진 복제(체결 코드 두 벌)

### 계획서 자체 검증 (2026-11-01)

| 회차 | 각도 | 결과 |
|---|---|---|
| 1 | 논리 · 누락 | `get_config` 를 부르는 고원 러너가 UGL · UBT 제거로 멈춤 → Q7 · 일회성 이름 확인 추가. `scripts` 를 부르는 테스트 0건 → 실행 대조 추가 |
| 2 | 다른 로직 영향 | `run_backtest` 호출 7곳 → 전략 판정을 루프 밖으로, 기존 결과 바이트 대조. 마커 인자가 포트폴리오 앱에 닿음 → Scope 에 추가 |
| 3 | 오류 · 불변식 | 보유 중 새 최고 종가 · 칸 금액이 현금 초과는 손계산으로 도달 불가 → `RuntimeError`. 금액 부족 때 칸을 건너뛰면 칸 순서가 깨짐 → 재시도로 고정 |
| 4 | 사용자 결정 대조 | 종가 터치면 돌파일이 이평선에 닿을 수 없음 → 돌파일 터치 분기를 뺌 |
| 5 | 단순화 | 칸마다 가격을 저장하지 않고 고점 + 칸 번호로 계산. `open_position` 에 합치는 안 대신 `open_lots` 하나 |
| 6 | 적은 숫자 대조 | 리스크의 민감도가 이전 조건(장중 터치)의 값 → 확정 규칙으로 다시 재어 표로 넣음. 나머지 표는 출력과 일치 |
| 7 | 문서 · 이름 | `src/qbt/CLAUDE.md` 상태 예외 목록 추가. `open_price` 인자가 손절가 · 지정가도 받아 이름이 거짓이 됨 → `price_raw` 로(키워드 호출 0건). 네 설정 목록 합친 이름 겹침 테스트 추가 |
| 8 | Phase 구성 | 테스트를 Phase 0 에 모으면 뒤 Phase 테스트가 레드로 남음 → 그린 범위를 Phase 별로 명시. 어색한 Phase 2 Validation 줄 정리 |
| 9 | 요청 원문 대조 | 개선 없음 — 요청 항목이 모두 Goal · Context · Scope 에 있음 |
| 10 | 데이터 · 결과 경로 | 개선 없음 — 입력 시세 전부 추적 중, 결과 폴더는 `BACKTEST_RESULTS_DIR` 아래 |
| 11 | 검증 수단의 강도 | 개선 없음 — 바이트 대조 · 원본 재계산 · 항등식 · 화면 확인이 서로 다른 경로. 연속 3회 개선 없어 종료 |

### 진행 로그 (KST)

- 2026-11-01 01:12: 사용자 답변 반영해 초안 작성, Q8 과 `AppTest` 승인 대기
- 2026-11-01 01:15: 자체 검증 11회차까지. 민감도 표를 확정 규칙으로 다시 쟀다
- 2026-11-01 01:21: 사용자 승인 「전부 추천대로」 — Q8 캔들 방향, Q9 `AppTest`. Phase 0 착수. 변경 전 코드로 전체 실행해 결과 13개 전략 폴더를 scratchpad 에 기준값으로 복사
- 2026-11-01 01:26: 레드 확인 — 새 파일 · Protocol 없는 3개 파일 수집 실패, 나머지 3개 파일에서 새 계약 7건 실패 · 36건 통과
- 2026-11-01 01:29: Phase 1 그린 — V2 · 기존 엔진 · 버퍼존 테스트 8개 파일 114건 통과
- 2026-11-01 01:30: Phase 2 그린 — 스플릿 · 공통 체결 테스트 36건 통과, 목록 정리 전이라 전략 목록 계약 1건만 레드로 남음
- 2026-11-01 01:32: Phase 3 — 테스트 6개 파일 140건 통과. UGL · UBT 결과 폴더 4개 삭제(각 파일 4개), 전체 실행 18개 전략
- 2026-11-01 01:33: 실행 대조 — 기존 9개 전략 결과 파일 36 / 36 바이트 동일. V2 · 스플릿 7개 전략의 CAGR · MDD · 거래 수 · 보유 진입일이 Context 기대값과 일치. V2 끝난 거래 27건을 원본 시세에서 재계산해 불일치 0건. 스플릿 행 수 6,954 = 원본 6,954, 5,743 = 2004년 이후 원본 5,743. 칸 주수 합 = 마지막 position (93,362 · 120,768), 최소 청산 ÷ 진입 1.046335 = 하한
- 2026-11-01 01:34: 항등식 오차가 0.4250 · -0.2152 로 기준 0.01 을 넘어 원인 확인 — `open_lots` 진입가의 소수 4자리 반올림 때문이었다. `ROUND_PRICE` 만 12자리로 바꿔 다시 재니 두 전략 모두 오차 0.0
- 2026-11-01 01:34: `AppTest` — 예외 0건, 탭 18개, 앱이 컴포넌트에 넘긴 차트 18개. V2 는 이동평균 · 밴드 선 3개, 스플릿은 0개. 「Buy (보유중)」 마커 스플릿 25 · 4, 스플릿 2004 마커 합계 2,370. 「보유 중인 칸」 소제목 표출. streamlit 상주 프로세스 0개. 고원 러너 이름 4개 모두 `get_config` 로 풀림. `UGL` · `UBT` 참조는 다운로드 목록과 제거를 고정하는 테스트뿐이다
- 2026-11-01 01:36: 문서 · 부록 N 작성, `black` 적용 (테스트 파일 1개 재포맷)
- 2026-11-01 10:08: 리뷰 1회차 15건 판정. 지적 1(신호일 종가가 이미 하단 아래면 손절선이 안 섬)을 합성 표로 재현(거래 0건 · MDD -58.8%)하고 실제 시세를 셌다 — 상단 위에서 하루 만에 하단 아래로 간 날 QQQ 6,755행 · QLD 6,755행 · TQQQ 6,755행 · GLD 5,322행 · TLT 5,904행 모두 0건
- 2026-11-01 10:09: 이 계획 때문에 사실과 달라진 문서 수정 — `COMMANDS.md` 합성 설명 2곳, `engine_common.py` docstring 2곳과 `backtest/CLAUDE.md` 의 「두 엔진 공통」, 부록 N.7 의 재현 조건. 부록 N.6 에 지적 1 을 한계로 기록
- 2026-11-01 10:09: 품질 검증 passed=994, failed=0, skipped=0. 그 뒤 고친 것은 문서뿐이다
- 2026-11-01 10:09: 고치지 않은 지적 처리 — 옮긴 항목 없음. 거른 지적(기준 번호): 신호일 종가가 이미 하단 아래면 손절선이 안 섬(1, 근거: 위 0건, 필요 하락 -9.5 ~ -26.1%. 부록 N.6 에 기록) · 예약 매도가 장중 손절에 덮임(1, `check_sell` 이 True 인 손절 전략이 없다) · 신호와 매매가 다른 종목이면 손절선 단위가 어긋남(1, V2 러너는 같은 시세만 넘긴다) · 칸 간격이 왕복 비용보다 좁으면 `RuntimeError`(2, 잘못된 값에서 멈춘다. 지금 값 5%) · 스케줄 교체나 `signal_df` 의 `Low` 누락이 `KeyError`(1, 2) · 부록 재현 문구의 조건(3, 문서라 수정함) · 엔진의 `open_lots` 반올림 위치(3, `run_backtest` 의 `open_position` 과 같은 관용) · 불변조건 `RuntimeError` 테스트 없음(3) · 낡은 합성 설명(3, 문서라 수정함) · 낡은 `engine_common` 설명(3, 문서라 수정함) · 전략 상수를 `constants.py` 아닌 전략 모듈에 둠(3) · 주석 문체(3) · 앱의 설정 목록 반복 루프(3) · 생성자의 칸 금액 계산(3) · `iloc` 반복(3)
- 2026-11-01 10:10: `/commit` 후보를 옮기고 Done 처리

---
