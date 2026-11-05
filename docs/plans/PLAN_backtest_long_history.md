# Implementation Plan: 백테스트를 합성 시세로 늘리기 — 1980년대부터 (합성 시세 연장 계획 5)

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-05 16:53
**마지막 업데이트**: 2026-11-05 18:12
**관련 범위**: utils(대용 보수), scripts/data(합성 생성), backtest(전략 · 포트폴리오 설정, Buy & Hold 실행), scripts/backtest(포트폴리오 러너), storage(stock · results), docs
**관련 문서**: CLAUDE.md, docs/MEMORY.md, docs/CLAUDE.md, docs/COMMANDS.md, README.md, scripts/CLAUDE.md, src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/utils/CLAUDE.md, tests/CLAUDE.md, docs/research/합성_시세_연장.md

---

## 1) 목표(Goal)

- [x] 목표 1: GLD 합성의 대용 구간에서 GLD 운용보수 연 0.40% 를 뺀다(결정 13) — 이음매(2004-11-18) 뒤는 실물 GLD 행 그대로
- [x] 목표 2: 버퍼존 · Buy & Hold · 포트폴리오 설정이 읽는 시세를 모두 `*_synthetic_max.csv` 로 바꾼다(결정 10) — 워크포워드 · 고원은 버퍼존 설정을 따라 함께 길어진다
- [x] 목표 3: 버퍼존에 S&P 500 2 · 3배(신호 SPY 합성, 매매 SSO · UPRO 합성)를 더한다(사용자 요청 2026-11-05)
- [x] 목표 4: 포트폴리오 2005 하한을 「등록 실험이 모두 같은 날 시작」으로 바꾼다 — 그날은 실험들의 데이터 시작일 중 가장 늦은 날
- [x] 목표 5: 회귀 ⑦ — 새 설정을 지금 결과의 기간으로 돌리면 지금 결과와 자본 차 0
- [x] 목표 6: 결과를 다시 만들고, 「전체 / 실물 구간」으로 나눈 표와 세전 · 세후를 연구 문서에 한 번 싣는다 — 이 계획서와 `HANDOFF.md` 를 지워도 잃는 것이 없게 한다

## 2) 비목표(Non-Goals)

- 버퍼존 SSO · UPRO 를 워크포워드 · 고원 대상에 넣기 — 요청은 버퍼존 전략 추가다. 워크포워드는 TQQQ · QQQ, 고원은 1배 넷(QQQ · SPY · GLD · TLT) 그대로다
- Buy & Hold SPY · SSO · UPRO 더하기 — Q1 (Notes)
- 결과 파일 · 대시보드에 「실물 구간」 지표 넣기 — 결정 10 의 택하지 않은 안. 나눠 본 표는 연구 문서에만
- 시작일에 「이미 들고 있던 것으로 치는」 출발 — 긴 판도 빈 장부로 시작한다(사용자가 가정을 받아들임 2026-11-05)
- 대시보드 코드 수정 — 결과 모양이 바뀌지 않는다. AppTest 로 예외만 본다
- 다른 1배 대용의 보수 · 배당 보정 — `^NDX` 는 QQQ 보수(0.20%)도 빠졌지만 배당이 더 커 이미 실물보다 낮다(결정 2). VFINX · VUSTX 는 자기 보수를 담는다
- `docs/research/` 의 기존 수치 고치기 — 그 시점 기록으로 둔다(`HANDOFF.md` 4절 계획 5). 새 수치는 `합성_시세_연장.md` 에 쓴다
- 인자 없는 `download_data.py` 실행 — 결과 변화의 원인을 가를 수 없다(루트 `CLAUDE.md`). 새 시세를 받지 않는다
- `docs/DEFERRED_FINDINGS.md` 의 항목 처리 — 이 계획이 고치는 자리와 겹치는 항목이 없다(포트폴리오 러너 항목은 결과 저장의 지우기 호출 줄이고, 이 계획은 시작일 계산만 바꾼다)
- git 조작 — 커밋은 사용자가 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 요청(2026-11-04): 「최대한 테스트 기간을 늘리는게 중요해」. 계획 1 ~ 4 가 합성 시세를 만들었고(QQQ 1985 · SPY 1980 · QLD · TQQQ 1985 · SSO · UPRO 1980 · TLT 1986 · GLD 1980), 백테스트는 아직 실물 파일을 읽는다 — 시작일이 QQQ · QLD · TQQQ 버퍼존 1999-12-21, Q-2-2XS 2007-04-09 에 묶여 있다
- 2026-11-05 질문 넷의 답: 「# 버퍼존 SPY에 2배, 3배도 추가 # 나머지는 추천대로」 → 연구 문서 결정 10 · 13. 범위는 연구 문서 7장 5행이다. `HANDOFF.md` 4절의 「모든 계획」 · 「계획 5」 항목은 이 절 · Risks · Notes 의 S 항목에 넣었다
- 착수 전 측정(설정만 바꿔 저장 없이 돌린 값)은 연구 문서 6.11 이다 — Q-2-2XS 2007-04-09 부터 연 15.16% · 최악 낙폭 -27.93% 가 1986-07-16 부터 13.47% · -45.78% 가 된다(세전). 그 측정은 2005 하한을 걷은 판이라 QQQ 보유는 1985-10-01 부터였다 — 이 계획의 「같은 날 시작」이면 1986-07-16 부터다

### 착수 전 확인한 사실 (2026-11-05)

**바꿀 자리 — 실물 경로를 읽는 백테스트 설정**

| 설정 | 지금 신호 · 매매 | 바꾼 뒤 |
|---|---|---|
| 버퍼존 TQQQ · QLD | `QQQ_DATA_PATH` · TQQQ · QLD 합성 | 신호 `QQQ_SYNTHETIC_DATA_PATH` |
| 버퍼존 QQQ · SPY · GLD · TLT | 실물 · 실물 | 그 1배 합성 · 합성 |
| 버퍼존 SSO · UPRO (새) | — | `SPY_SYNTHETIC_DATA_PATH` · SSO · UPRO 합성 |
| Buy & Hold QQQ · GLD · TLT | 실물 | 그 1배 합성 |
| Buy & Hold TQQQ · QLD | 합성, 기간은 `QQQ_DATA_PATH` 에 묶음(`period_data_path`) | 합성, 묶음 없음 |
| 포트폴리오 넷의 슬롯 | 실물(SSO · QLD 는 실물 `SSO_max` · `QLD_max`) | 모두 합성 |

- 워크포워드(`run_walkforward.py` 의 TQQQ · QQQ)와 고원(`run_param_plateau_all.py` 의 QQQ · SPY · GLD · TLT)은 `buffer_zone.get_config` 의 경로를 읽어 함께 길어진다. 대시보드 `app_single_backtest.py` 는 두 `CONFIGS` 의 결과 폴더를 읽어 SSO · UPRO 가 저절로 보인다
- `period_data_path` 를 쓰는 곳은 `buy_and_hold.py` 의 TQQQ · QLD 두 줄과 `runners.create_buy_and_hold_runner` 의 분기, `tests/qbt/test_buy_and_hold.py` 둘, `src/qbt/backtest/CLAUDE.md` 한 줄이다(`grep`) — 두 줄의 묶음을 풀면 쓰는 설정이 0 이 된다
- `DEFAULT_PORTFOLIO_START_DATE` 는 `run_portfolio_backtest.py` 와 `scripts/CLAUDE.md` 에만 있다. 테스트는 scripts 러너를 부르지 않는다. 설정에 `min_start_date` 를 둔 등록 실험은 0 이다(`test_no_config_has_start_date_floor`)
- 포트폴리오 엔진은 슬롯마다 신호 · 매매를 겹치는 날로 맞춰 이동평균을 낸 뒤 모든 자산의 공통 거래일로 자른다(`_load_portfolio_data_with_common_period`) — 금 합성에 없는 미국 거래일은 이동평균 창을 바꾸지 않고 포트폴리오 달력에서만 빠진다
- 실물 경로를 고정하는 테스트: `test_buffer_zone.py` `test_qld_config_trades_synthetic_on_qqq_signal`(신호 `QQQ_DATA_PATH`) · `test_portfolio_configs.py` `test_qqq_bh_holds_qqq_without_trading_rule`(QQQ) · `test_q2_2xs_gld_tlt_buy_and_hold`(GLD · TLT) · `test_buy_and_hold.py` `test_synthetic_configs_bound_to_qqq_period` · `test_period_data_limits_dates`
- SSO · UPRO 합성은 SPY 합성과 겹치는 날로 읽혀 11,803행, 1980-01-02 ~ 2026-10-29 다. 하루 최대 하락 SSO -40.97% · UPRO -61.47%(1987-10-19)에도 `load_signal_trade_pair` 의 검사를 통과한다
- quant-notify 는 `portfolio_configs.py` 의 티커 · 비중만 옮겨 적고 시세 경로를 읽지 않는다(그 저장소에 `_max.csv` · `DATA_PATH` 참조 0) — 신호 티커 · 비중 · Buy & Hold 여부가 그대로라 알림에 영향이 없다
- 결과 폴더 크기: `storage/results/backtest` 34M · `portfolio` 12M (기간이 두 배 남짓이 된다)
- **같은 날 시작 미리 재기** (저장 없이, GLD 보수 전): 데이터 시작일 QQQ 보유 1985-10-01 · D-1 · Q-2 · Q-2-2XS 1986-07-16 → 넷 모두 1986-07-16 에 시작해 정합성 검사(`validate_portfolio_result`) 위반 0. 연 수익 · 최악 낙폭 · 거래 수: QQQ 보유 14.42% · -82.96% · 0, D-1 11.06% · -43.36% · 23, Q-2 9.56% · -25.77% · 222, Q-2-2XS 13.47% · -45.78% · 306 (측정 코드 `/private/tmp/claude-501/-Users-yubeen-Workspace-quant/e8739064-0110-4405-89a0-d3fb4a45cdb6/scratchpad/probe/validate_long.py`)

**GLD 합성** — 11,606행 중 이음매 앞 6,085행(1980-01-02 ~ 2004-11-17). 보수를 뺀 판의 첫 행 종가는 59.473452 → 65.709597 이다(6.11 측정 — 2004-11-18 에 맞춘 뒤 (1 − 0.004)^(−경과 연수)).

### 기존 함수 재사용 — 호출처 (전역 「기존 함수 재사용 전 검증」, 정의 제외)

- 그대로 쓴다: `build_proxy_synthetic`(scripts 2 — GLD 는 `_save_proxy_synthetic` 이 부른다), `compute_portfolio_effective_start_date`(scripts 1 — 러너가 실행 전에 실험마다 부른다), `run_portfolio_backtest`(scripts · tests 다수), `load_signal_trade_pair`(src · scripts 다수 — 버퍼존 runner 의 관용 경로)
- 새로 만든다: 대용에 연 보수를 빼는 함수 — 같은 일을 하는 함수가 없다. 레버리지 비용(`tqqq/simulation._calculate_daily_cost`)은 운용보수를 거래일마다 ÷ 252 로 빼지만 레버리지 시뮬레이션 안쪽 함수라 쓰지 않는다(S1)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절, 「스크립트 실행 규칙」(대시보드는 사용자가 띄움 · AppTest 는 AI 가 돌림 · 결과 파일 덮어쓰기), 「가격 반올림 자릿수」, `docs/MEMORY.md`(세전 · 세후, 1 · 2 · 3배 나란히, 용어는 풀어서)
- `docs/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `tests/CLAUDE.md`
- 전역 `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`
- `docs/research/합성_시세_연장.md` — 3장 결정 10 · 13 · 5장 검증 ⑦ · 6.11 · 8장 한계 · 9장 재현 방법
- `docs/research/전략_검증_보고서.md` 부록 O.7 — 세후(판 것만) 계산 방식

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] GLD 합성 — 이음매 앞 6,085행만 바뀌고, 그 행마다 (새 종가 ÷ 지금 종가) 가 (1 − 0.004)^(−(2004-11-18 − 그날) ÷ 365.25) 와 상대 1e-6 안에서 같다(첫 행 1980-01-02 은 59.473452 → 65.7096 안팎 — 6.11 측정 65.709597, 마지막 자리는 반올림 순서로 다를 수 있다). 이음매 뒤 줄이 `GLD_max.csv` 데이터 줄과 같다(`diff` 0줄) — 상대 오차 최대 3.54e-08, 첫 행 65.709597, `diff` 0줄 (진행 로그 17:20)
- [x] 생성 뒤 다른 합성 일곱(QQQ · TQQQ · QLD · SPY · SSO · UPRO · TLT)과 `tracking.csv` · `funds.csv` · `fund_years.csv` · `assumptions.csv` 가 바이트까지 같다(`git status` 에 `M` 없음). `summary.csv` · `years.csv` 는 GLD 행만 바뀌고 다른 행은 열마다 같다. ① GLD 행의 대용 연 수익이 10.59% 에서 보수만큼(약 10.15%) 내려간다 — 10.15%, GLD 아닌 행 같음
- [x] 백테스트 설정 — 버퍼존 8 · Buy & Hold 5 · 포트폴리오 4 실험의 모든 시세 경로가 `*_synthetic_max.csv` 이다(테스트가 지킨다). `period_data_path` 가 저장소에 0 건이다(`grep`) — 코드 0 건, 문서는 연구 문서의 측정 기록 둘뿐. 리뷰 2회차로 신호 · 매매 짝도 테스트가 지킨다
- [x] 버퍼존 SSO · UPRO — 신호 SPY 합성 · 매매 SSO · UPRO 합성, 4P 기본값(테스트가 지킨다). 결과 폴더 둘이 생긴다 — 1980-10-14 부터 13.27% · −61.03% / 15.42% · −80.05%
- [x] 포트폴리오 시작일 — 네 실험의 `summary.json` 시작일이 같은 날이다(기대 1986-07-16). `--experiment portfolio_q2_2xs` 하나만 돌려도 같은 날에 시작한다 — 넷 1986-07-16, 단독 실행 결과 8 파일 `cmp` 같음(리뷰 1회차 수정 뒤 Q-2 단독도 같음)
- [x] 회귀 ⑦ — 포트폴리오 넷은 새 설정을 지금 결과의 시작일(2005-01-03 · 2007-04-09)부터, 단일 열하나는 새 설정의 시세를 지금 입력의 첫날부터 잘라 돌린 자본 곡선이 지금 `equity.csv` 와 같다(차 0 — 저장 자릿수로 반올림해 견줌). 버퍼존 SSO · UPRO 는 시세를 실물 SSO · UPRO 첫날부터 자른 판이 실물 `SSO_max` · `UPRO_max` 와 `SPY_max` 로 돈 판과 같다 — 모두 자본 차 0 (진행 로그 17:12)
- [x] 결과 — COMMANDS ④ 러너 넷이 종료코드 0, 포트폴리오 정합성 위반 0. 단일 13 · 포트폴리오 4 의 시작일 · 연 수익 · 최악 낙폭 · 거래 수를 진행 로그에 적는다(6.11 과 다르면 그 칸과 이유) — 진행 로그 17:14 · 17:25
- [x] 대시보드 넷 — `AppTest` 로 돌려 예외 0
- [x] 새 · 바꾼 테스트 — 대용 보수 함수(첫 행 그대로, 4년 뒤 (1 − 보수)^4, 보수 0 이면 그대로, 음수 · 1 이상 ValueError, 원본 불변, 거래량 그대로), 설정 셋(모든 경로가 합성), 버퍼존 SSO · UPRO — 리뷰로 더함: `planned_start_dates` 넷, 설정 짝 셋
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` 변경 있음(Scope), 루트 `CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `tests/CLAUDE.md` 변경 없음(서술이 그대로 맞는지 Phase 4 에서 다시 본다) — 리뷰 1회차로 엔진 docstring 셋도 고침
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (연구 문서 1 · 3 · 5 · 6 · 7 · 8 · 9장, `HANDOFF.md`) — 연구 문서 결정 10 · 13(실행), 1장 시작일(VUSTX 가 정한다는 서술을 실측으로 바로잡음), 5장 ⑦, 5.1 · 6.10 GLD, 6.11 · 6.12(결과 · 회귀 ⑦ · 나눈 표 · 세후 · 빠진 날 · 워크포워드 · 고원), 7 · 8 · 9장, 인계서 1 · 4 · 6절. 미룬 지적 넷은 `docs/DEFERRED_FINDINGS.md`
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다. — 4건 옮김(함께 시작할 날이 거래일이 아닐 때 · 부분 실행과 그 계약의 테스트 · 합성 생성을 건너뛸 때 · 짝 테스트의 배분 규칙 공백), 나머지는 거름 · 받아들임(진행 로그 17:39 · 17:50 · 18:12). 이 계획서가 그 파일의 기존 항목을 고친 것 없음
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 고치는 파일
  - `src/qbt/utils/proxy_series.py` — 대용에서 연 보수를 빼는 함수(S1)
  - `scripts/data/generate_synthetic.py` — 금 사슬에 GLD 보수(상수 `GLD_EXPENSE_RATIO`), ① GLD 행의 대용 이름, docstring
  - `src/qbt/backtest/strategies/buffer_zone.py` — 경로를 합성으로, SSO · UPRO 두 줄(S2)
  - `src/qbt/backtest/strategies/buy_and_hold.py` — 경로를 합성으로, `period_data_path` 칸 지우기(S3)
  - `src/qbt/backtest/runners.py` — Buy & Hold 의 기간 묶음 분기 지우기(S3)
  - `src/qbt/backtest/portfolio_configs.py` — 슬롯 경로를 합성으로
  - `scripts/backtest/run_portfolio_backtest.py` — 2005 하한 → 같은 날 시작(S4)
  - 테스트: `tests/qbt/test_proxy_series.py` · `test_buffer_zone.py` · `test_buy_and_hold.py` · `test_portfolio_configs.py`
- 데이터 · 결과: `storage/stock/GLD_synthetic_max.csv`, `storage/results/proxy_validation/summary.csv` · `years.csv`, `storage/results/backtest/` 전부(새 폴더 `buffer_zone_sso` · `buffer_zone_upro`, 워크포워드 · 고원 포함) · `storage/results/portfolio/` 전부
- 문서: `docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `docs/research/합성_시세_연장.md` · `HANDOFF.md`
- `docs/COMMANDS.md`: 변경 있음 — 워크플로우 1 의 선행(단일 · 포트폴리오 · 워크포워드 · 고원이 모두 합성 시세를 읽는다), 워크플로우 2 의 2 와 「시세를 다시 받은 뒤」 ③ 의 「TQQQ · QLD 판은 … Buy & Hold 는 QQQ 실물 기간만」 문장, 워크포워드 소요(다시 잰다). 실행 명령 · CLI 옵션은 바뀌지 않는다(`--strategy` 선택지는 `--help` 가 정본)
- `README.md`: 변경 있음 — 백테스트가 상장 전까지 늘린 합성 시세로 1980년대부터 돈다는 한 줄

### 데이터/결과 영향

- GLD 합성의 이음매 앞 행과 ① 의 GLD 행이 바뀐다. 다른 합성 · 검증 표는 그대로다
- 단일 · 포트폴리오 · 워크포워드 · 고원 결과가 모두 바뀐다 — 시작일이 1980 ~ 1987 로 옮겨간다. 결과 파일 모양(열 · 파일 이름)은 그대로다
- 대표 숫자가 바뀐다 — 운용 포트폴리오 Q-2-2XS 의 결과가 2007 년부터에서 1986 년부터가 된다(6.11). `전략_검증_보고서.md` 의 숫자는 그 시점 기록으로 남는다

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트 먼저 (레드)

**작업 내용**:

- [x] 대용 보수 함수 — 첫 행은 그대로, 첫날에서 1,461일(4 × 365.25) 뒤 행의 가격 넷이 (1 − 보수)^4 배, 보수 0 이면 그대로, 보수 음수 · 1 이상 ValueError, 날짜 역순 · 중복 ValueError, 원본 불변, 거래량 그대로 — 하루 뒤 행(행 수로 세면 연수가 달라지는 행)도 넣음
- [x] 버퍼존 설정 — QLD 의 신호가 QQQ 합성(기존 테스트 고침), SSO · UPRO 줄(신호 SPY 합성 · 매매 그 합성 · 4P 기본값), 모든 줄의 신호 · 매매 경로가 `_synthetic_max.csv`
- [x] Buy & Hold 설정 — 모든 줄의 경로가 `_synthetic_max.csv`. 기간 묶음 테스트 둘(`test_period_data_limits_dates` · `test_synthetic_configs_bound_to_qqq_period`)은 지운다 — 지킬 기능이 없어진다(S3)
- [x] 포트폴리오 설정 — QQQ 보유 · Q-2-2XS 의 GLD · TLT 경로 테스트를 합성으로 고침, 모든 실험 · 슬롯의 신호 · 매매 경로가 `_synthetic_max.csv` — 배분 규칙 매매법의 매매 · 신호용 시세도 센다(`resolve_methods`, 이 파일의 관용)

**Validation**:

- [x] 새 · 바꾼 테스트가 실패 또는 수집 단계 오류로 레드 (`pytest` 해당 파일만) — `test_proxy_series.py` 수집 단계 오류 1(없는 이름 import), 설정 셋 8 failed · 46 passed

---

### Phase 1 — GLD 보수 (그린)

**작업 내용**:

- [x] `proxy_series.py` — 대용 보수 함수(S1) — `deduct_annual_fee`, 연 환산 일수는 기존 `ANNUAL_DAYS`(CAGR 과 같은 상수)
- [x] `generate_synthetic.py` — `_gold_pairs` 에서 금 사슬에 보수를 걸고 그 사슬을 GLD 합성과 ① GLD 행에 함께 쓴다, 대용 이름에 보수 표기, docstring
- [x] 합성 생성을 돌린다 — 종료코드 0 — 5초, ERROR · WARNING 0

**Validation**:

- [x] 대용 보수 함수 테스트 통과 (`pytest tests/qbt/test_proxy_series.py`) — 32 passed
- [x] DoD 의 GLD 합성 · 다른 합성 · 검증 표 두 줄을 대조 — 행 수는 따로 세고, 이음매 뒤는 `diff`, `summary.csv` · `years.csv` 는 GLD 아닌 행을 열마다 견준다 — 진행 로그 17:20
- [x] 대용 보수 함수의 변형 둘(지수 부호를 바꿈 · 경과 연수를 행 수 ÷ 252 로 셈)에서 함수 테스트가 실패하고, 되돌리면 통과 (`PYTHONDONTWRITEBYTECODE=1`, 원본 `cmp`). 스크립트가 사슬에 보수를 거는 한 줄은 테스트가 지키지 못한다 — 위 GLD 합성 대조가 확인한다(계획 2 ~ 4 와 같은 판단: 스크립트의 표 · 연결은 테스트 밖) — 변형 둘 각 1 failed · 31 passed, 원본 `cmp` 같음 · 32 passed

---

### Phase 2 — 설정 · 러너 (그린)

**작업 내용**:

- [x] `buffer_zone.py` — 경로를 합성으로, SSO · UPRO 줄(S2)
- [x] `buy_and_hold.py` · `runners.py` — 경로를 합성으로, `period_data_path` 칸과 분기를 지운다(S3) — runner 는 계획 2 전의 한 줄(`load_stock_data(config.trade_data_path)`)로 되돌림
- [x] `portfolio_configs.py` — 슬롯 경로를 합성으로 — 본문 18곳 · 가져오기 6곳 치환(남은 실물 경로 0)
- [x] `run_portfolio_backtest.py` — 같은 날 시작(S4), `DEFAULT_PORTFOLIO_START_DATE` 를 지운다 — 그 상수만 쓰던 `from datetime import date` 도 지움

**Validation**:

- [x] Phase 0 의 테스트와 관련 테스트 파일 통과 (`pytest` — `test_buffer_zone*.py` · `test_buy_and_hold.py` · `test_portfolio_*.py` · `test_proxy_series.py`) — 311 passed
- [x] `grep period_data_path` · `grep DEFAULT_PORTFOLIO_START_DATE` 가 src · scripts · tests 의 `.py` 에서 0 건 (도메인 문서의 서술은 Phase 4 에서 고친 뒤 다시 센다) — 0 건

---

### Phase 3 — 회귀 ⑦ 과 결과 다시 만들기

**작업 내용**:

- [x] 실행 전 `git status --short storage/results` 가 비어 있는지 본다(루트 `CLAUDE.md` — 결과 파일은 덮어써진다) — Phase 1 의 `proxy_validation` 둘만 `M`, `backtest` · `portfolio` 는 깨끗함
- [x] 회귀 ⑦ — 결과를 다시 만들기 «전에» 저장소 밖 임시 코드로 돈다(S6). 저장된 지금 결과와 견준다 — 진행 로그 17:12
- [x] COMMANDS 「시세를 다시 받은 뒤」 ④ 의 러너 넷을 돈다 — 실행 시간을 잰다(워크포워드는 늘어난다 — COMMANDS 소요를 고친다) — 단일 7초 · 포트폴리오 8초 · 워크포워드 331초 · 고원 50초. 워크포워드 5.5분이라 COMMANDS 의 「약 6분」은 그대로 맞아 고치지 않음
- [x] `--experiment portfolio_q2_2xs` 하나만 다시 돌려 시작일이 같은지 본다(결과 파일이 바이트까지 같아야 한다) — 1986-07-16, 결과 8 파일 모두 `cmp` 같음
- [x] 대시보드 넷을 `AppTest` 로 돈다 — 넷 모두 예외 0 (단일 대시보드 탭 13 = 버퍼존 8 + Buy & Hold 5)

**Validation**:

- [x] DoD 의 ⑦ · 결과 · 포트폴리오 시작일 · 대시보드 줄을 각각 대조 — 숫자는 출력을 그대로 진행 로그에 옮긴다 — 진행 로그 17:12 · 17:14 · 17:25
- [x] `git status --short storage/results` — 바뀐 파일 목록이 `storage/results/backtest` · `portfolio` 밖에 없다(`proxy_validation` 은 Phase 1 의 둘뿐) — `M` 224 · `??` 86, 밖은 `proxy_validation/summary.csv` · `years.csv` 둘뿐. 새 폴더 `buffer_zone_sso` · `buffer_zone_upro`, 워크포워드 윈도우 w11 ~ w17 파일

---

### Phase 4 — 연구 문서 · 문서 · 근거 승격

**작업 내용**:

- [x] 연구 문서 새 절(6.12, S5) — 긴 판 결과(단일 13 · 포트폴리오 4, 세전 · 세후), 「전체 / 실물 구간」 표, 포트폴리오 달력에서 빠진 금 날 수, 워크포워드 · 고원의 바뀐 요약, 결과를 읽을 때 함께 볼 가정(8장 — 비용 가정 구간 · 급락한 달 · 가짜 시가 · 금 하루 잡음 · 금 1980-01 고점 · `^NDX` 배당 · SSO · UPRO 기초) — 워크포워드는 4P 를 고를 때 보지 않은 1991 ~ 1999 구간을 따로 잘라 냄
- [x] 연구 문서 — 1장(지금 시작일 문장), 3장 결정 10 · 13 의 실행 상태, 5장 ⑦ 의 기준선, 5.1 · 6.10 의 GLD 행과 6.10 「들고만 있었을 때」의 GLD 열(보수 뺀 값), 7장 5행, 8장 「금 대용의 보수」(반영됨), 9장 재는 법(⑦ · 나눈 표 · 세후) — 1장의 「Q-2-2XS 시작일은 VUSTX 가 정한다」를 실측(나스닥 100 첫날 + 200일선 = 1986-07-16)으로 바로잡음, 8장 「금」 · 「측정 코드」 행도 고침
- [x] `docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md`(포트폴리오 러너의 시작일, 단일 백테스트가 합성을 읽는다) · `src/qbt/backtest/CLAUDE.md`(Buy & Hold 기간 묶음 문장 지움, 포트폴리오 「시작일」 규칙에 같은 날 시작) · `src/qbt/utils/CLAUDE.md`(`proxy_series.py` 에 대용 보수) — 문서에 남은 `period_data_path` · `DEFAULT_PORTFOLIO_START_DATE` 0 건(계획서 · 인계서 · 연구 문서의 기록 제외). 고치지 않은 루트 `CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `tests/CLAUDE.md` 에 어긋나는 서술 없음(`grep`)
- [x] `HANDOFF.md` — 1절 5행 · 머리 · 6절(세션 마무리 3절 5단계에서) — 4절의 「Q-2-2XS 시작일은 장기채가 정한다」도 실측으로 바로잡음

---

### 마지막 Phase — 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 자동 포맷 적용 (`poetry run black .`) — 4파일 · 리뷰 2회차 뒤 1파일
- [x] 합성 생성을 한 번 더 돌려 합성 · 검증 파일이 바이트 단위로 같고 콘솔의 직전 값이 이번 값과 같은지 본다 — 14 파일 같음 · 「바뀜」 0 (리뷰 수정은 합성 경로를 건드리지 않음)
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 11건 — 버그 4 [무거움 2 · 가벼움 2] · 그 외 7 · 조치: 닿는 버그 3 수정(무거움 ① 같은 날 시작을 대조하지 않음 · 무거움 ⑥ 그 규칙의 테스트 0 → src 순수 함수와 테스트 · 가벼움 ⑦ 테스트 키 겹침), 가벼움 ② 는 계획서가 받아들인 모양(결정 6 · 보간 금지), 그 외 중 ④ 는 ① 과 같은 모양이라 함께, ⑩ 은 사용자 주석 규칙 위반이라 고침, ③ ⑤ ⑧ ⑨ ⑪ 은 고치지 않음 — ⑧ 은 ⑥ 수정으로 사라짐. 목록은 진행 로그 17:39)
- [x] `/code-review xhigh` **2회차** (발견 13건 — 버그 5 [무거움 1 · 가벼움 4] · 그 외 8 · 조치: 무거움 ⑤ 수정(설정의 신호 · 매매 짝을 테스트가 고정하지 않음 → 짝 테스트 셋), 가벼움 ① ② ③ ⑨ 는 1회차가 고친 자리라 「같은 자리 두 번」 — 고치지 않고 미룬 지적으로 옮김(사용자에게 올림), 가벼움 ④ 는 판정할 수 없어 옮김, 그 외 8 은 고치지 않음. 목록은 진행 로그 17:50)
- [x] 수정분 검증 (수정 1건 · 발견 2건 — 무거움 0 · 조치: 고치지 않음(`review.md` 「수정분 검증의 발견은 고치지 않는다」). 6 hunk 모두 ① 결과가 바뀌는 입력 없음 · ③ 위험한 쪽으로 바뀜 아니오, ② 남은 자리 1(배분 규칙 매매법) — 미룬 지적으로 옮김, 다른 1(Q-2-2XS 구성 자체를 고정하지 않음, diff 밖)은 거름. 목록은 진행 로그 18:12)
- [x] `poetry run python validate_project.py` (passed=856, failed=0, skipped=0 — Ruff · PyRight 통과)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 전 전략 · 포트폴리오의 합성 시세 전환으로 1980년대부터 백테스트
2. 백테스트 / 버퍼존 · Buy & Hold · 포트폴리오 설정을 상장 전까지 늘린 합성 시세로 전환하고 포트폴리오 2005 하한을 등록 실험 같은 날 시작으로 변경
3. 백테스트 / 버퍼존 S&P 500 2 · 3배(SSO · UPRO) 추가와 GLD 합성의 운용보수 0.40% 차감
4. 백테스트 / 합성 시세 연장 계획 5 — 긴 판 결과 재생성과 회귀 ⑦ 자본 차 0 확인, 세전 · 세후와 실물 구간을 나눈 결과 기록
5. 백테스트 / 포트폴리오 시작일 결정의 엔진 이동과 실제 시작일 대조, 설정의 신호 · 매매 짝 테스트 추가

## 7) 리스크(Risks)

- **대표 숫자가 나빠 보인다** — Q-2-2XS 의 최악 낙폭이 -27.93% 에서 -45% 안팎이 되고, 그 고점 회복이 7년 7개월이다(6.11, 1987 ~ 1995). 그 구간은 대조할 레버리지 상품이 없는 비용 가정 구간이고(금리 6 ~ 10% — 2배 연 비용 8 ~ 12% 안팎), 급락한 달은 모형이 실제보다 좋게 잡고(8장 「급락한 달」), 시가가 그날 종가다(결정 3). 결과 절에 이 가정을 함께 적는다. 운용 판단 문서(부록 O)는 그 시점 기록으로 둔다 — 운용 포트폴리오를 바꾸는 결정은 이 계획 밖이다
- **앞 구간의 1배 대용이 실물과 다르게 움직인다** — `^NDX` 는 배당이 빠져 연 0.57%p 낮고(결정 2), SSO · UPRO 합성은 기초(저장소 SPY)의 1990년대 흔들림으로 연 0.4 · 0.7%p 낮게 잡히고(결정 5 · 6.9), 금은 1980 ~ 1991 에 하루 잡음이 낀다(결정 6). 대부분 덜 좋게 잡는 쪽이다
- **금 합성에 없는 미국 거래일** — 금이 든 포트폴리오(Q-2 · Q-2-2XS)는 그날이 모든 자산에서 빠진다(Context). 그 수를 결과 절에 적는다
- **같은 날 시작이 실험마다 다른 데이터에 묶인다** — 시작일은 가장 늦게 시작하는 실험이 정한다(지금은 나스닥 100 첫날 + 200일선 준비 기간 1986-07-16). 새 실험의 데이터가 더 늦게 시작하면 모든 실험이 그날로 옮겨간다 — 러너가 실험마다 시작일과 그 이유(가장 늦은 실험 이름)를 로그에 낸다
- **워크포워드 · 고원이 바뀐다** — 윈도우 수 · 공통 기간이 데이터 첫날에 따라 달라져 ⑦ 로 견줄 수 없다. 바뀐 요약을 결과 절에 그대로 보인다. 워크포워드 시간이 늘어난다(COMMANDS 「약 6분」 — 다시 잰다)
- **결과 파일이 커진다** — 기간이 두 배 남짓이라 `storage/results` 의 CSV 가 커진다(지금 46M). git 추적 대상이다 — 크기를 진행 로그에 적는다
- **결과 파일 덮어쓰기** — 실행 전 작업 트리를 확인하고, ⑦ 은 덮어쓰기 «전에» 돈다. 되돌림은 git 이력에 있다
- **Buy & Hold 기간 묶음을 지우는 것** — 칸을 지우면 나중에 같은 필요가 생겼을 때 다시 만들어야 한다. 결정 10 으로 묶을 이유(실물 기간 유지)가 사라졌다 — 지금 남기면 쓰는 곳 없는 칸이 된다(전역 「수술적 변경」 — 내 변경이 만든 orphan 정리)
- **⑦ 이 자명하게 통과할 위험** — 이음매 뒤 행이 실물과 같으니(⑥) 자르면 같은 것이 당연하다. ⑦ 이 잡는 것은 설정의 경로 짝 실수(신호와 매매를 다른 합성으로 짝지음)와 `period_data_path` 를 지운 runner 의 변화다 — 포트폴리오는 이동평균을 긴 시세로 내도 같은 시작일부터 같은지까지 본다
- **러너의 같은 날 시작을 테스트가 지키지 못한다** — 테스트는 scripts 러너를 부르지 않는다(지금 하한 2005 도 같다). 설정 쪽(모든 경로가 합성)은 테스트가 지키고, 같은 날 시작은 Phase 3 의 실행(넷의 시작일 · 하나만 돌린 실행)으로 확인한다
- **quant-notify** — `portfolio_configs.py` 의 경로만 바뀌고 티커 · 비중 · Buy & Hold 여부는 그대로라 알림에 영향이 없다(Context)
- **SSO · UPRO 를 더한 대시보드** — 앱 코드는 그대로이고 두 `CONFIGS` 의 결과 폴더를 읽는다. AppTest 로 예외만 본다 — 화면은 사용자가 본다

## 8) 메모(Notes)

### 결정 (사용자 「추천대로 진행」 2026-11-05 17:06)

- **Q1 = A** — Buy & Hold SPY · SSO · UPRO 는 더하지 않는다
- **S1 ~ S7** 그대로

### 사용자에게 물은 것 (계획서 승인과 한 라운드)

- **Q1. Buy & Hold SPY · SSO · UPRO 를 더할지** — 지금 Buy & Hold 는 QQQ · QLD · TQQQ · GLD · TLT 다섯이고 SPY 는 1배도 없다. 버퍼존 SSO · UPRO 를 더하면 S&P 500 쪽만 「들고만 있었을 때」 비교 줄이 없다. 선택지: A 더하지 않는다 — 요청 범위 밖이고, 1 · 2 · 3배 들고만 있었을 때 숫자는 연구 문서 6.9 에 있고 6.12 에도 나란히 낸다(결과 파일 · 대시보드에는 없다) / B 셋을 더한다 — 대시보드에서 버퍼존과 나란히 볼 수 있다, 결과 폴더 셋 · 설정 세 줄. **추천: A** — 필요하면 한 줄씩 더하면 되고 지금 결정에 쓰이지 않는다

### 정해 둔 것 (승인 대상)

- **S1. GLD 보수는 금 사슬 전체에 건다** — `proxy_series` 에 대용의 가격 넷(시가 · 고가 · 저가 · 종가)에 첫 행부터 달력일로 잰 경과 연수 t 마다 (1 − 보수)^t 를 곱하는 함수를 두고(거래량 그대로, 보수는 0 이상 1 미만), 스크립트 `_gold_pairs` 가 금 사슬에 걸어 그 사슬을 GLD 합성과 ① GLD 행에 함께 쓴다. GLD 합성은 이음매에서 실물 종가로 맞추므로 이음매 앞 행만 바뀐다. ① GLD 행은 보수를 뺀 사슬과 GLD 를 견줘, 대용 연 수익이 실물에 얼마나 다가가는지 보인다(사슬 안 고리 행 GC=F · Perth 달러는 고리끼리라 그대로). 보수 0.40% 는 스크립트 상수 `GLD_EXPENSE_RATIO`(파일 하나에서만 쓴다 — `src/qbt/CLAUDE.md` 「상수 관리」), ① 의 대용 이름에 「연 보수 0.4% 뺌」을 붙인다. 달력일로 나누는 이유: GLD 는 보수를 해마다 매기고, 금 사슬에는 미국 거래일 중 빈 날이 있어 거래일 수로 나누면 해마다 다르게 빠진다(측정 6.11 도 달력일). 택하지 않은 안: 이음매 앞 행에만 걸기(① 이 보수가 차이를 설명하는지 보이지 못한다), 거래일마다 ÷ 252(레버리지 비용 모형의 방식 — 빈 날만큼 덜 뺀다), `build_gold_proxy` 의 인자(사슬 잇기와 보수 가정이 섞인다)
- **S2. 버퍼존 SSO · UPRO** — `BufferZoneConfig("buffer_zone_sso", "버퍼존 전략 (SSO)", 신호 SPY_SYNTHETIC_DATA_PATH, 매매 SSO_SYNTHETIC_DATA_PATH)` · UPRO 같은 모양, 4P 기본값, 결과 폴더 `buffer_zone_sso` · `buffer_zone_upro`. 순서는 TQQQ · QLD · QQQ · UPRO · SSO · SPY · GLD · TLT — 나스닥 100 쪽과 같은 3 · 2 · 1배 순. 신호는 1배 시세다(`docs/MEMORY.md` 「버퍼존 레버리지는 1배 신호」)
- **S3. `period_data_path` 칸을 지운다** — 쓰던 두 줄(TQQQ · QLD)의 묶음을 풀면 쓰는 설정이 0 이다 — 이 변경이 만든 쓰이지 않는 칸이라 칸 · runner 분기 · 테스트 둘 · 도메인 문서 한 줄을 함께 지운다. 택하지 않은 안: 칸을 남겨 둠(지킬 동작이 없는 기능이 남는다)
- **S4. 포트폴리오는 등록 실험이 모두 같은 날 시작한다** — 러너가 실행 전에 `PORTFOLIO_CONFIGS` 의 실험(설정에 `min_start_date` 가 없는 것) 모두의 데이터 시작일(`compute_portfolio_effective_start_date`)을 재서 그중 가장 늦은 날에 모두 시작한다. `--experiment` 로 하나만 돌려도 같은 날이다 — 대상 실험만 재면 부분 실행이 다른 기간을 낸다. 그 대가로 하나만 돌려도 등록 실험 넷의 시세를 모두 읽는다(몇 초, 어느 시세가 깨졌으면 그 실험을 돌리지 않아도 멈춘다). 로그에 그날과 그날을 정한 실험을 낸다. `min_start_date` 가 있는 실험은 지금처럼 그날 시작한다(지금 0 건). 택하지 않은 안: 실험마다 `min_start_date=1986-07-16`(날짜를 손으로 적어, 데이터가 앞으로 늘면 낡는다), 하한 상수 값만 1986-07-16 으로(어느 실험의 데이터가 그날보다 늦게 시작하면 실험마다 다시 갈린다)
- **S5. 「전체 / 실물 구간」 표 (연구 문서 6.12)** — 경계는 그 전략이 읽는 모든 시세가 실물인 첫날이다: 버퍼존 QQQ · Buy & Hold QQQ · D-1 · QQQ 보유 1999-03-10, SPY 1993-01-29, QLD · SSO · Q-2-2XS 2006-06-21, UPRO 2009-06-25, TQQQ 2010-02-11, GLD · Q-2 2004-11-18, TLT 2002-07-30. 긴 판 자본 곡선을 경계에서 잘라 앞 · 뒤 · 전체의 연 수익 · 최악 낙폭을 잰다 — 그날 들고 있던 것이 이어진다(6.11 「지금 시작일부터 잘라 본 값」). 세후는 부록 O.7 의 「판 것만」(그해 매도 손익 합이 양수면 22% 를 그해 마지막 종가에 전체 자산에서 덜어냄, 손실이면 0, 이월 없음)이다 — Buy & Hold 는 팔지 않아 세전과 같다. 측정 코드는 저장소 밖이고 재는 법은 9장이다
- **S6. 회귀 ⑦** — 결과를 다시 만들기 전에 저장소 밖에서 돈다. 포트폴리오: 새 설정을 `run_portfolio_backtest(설정, 지금 결과의 시작일)` 로 돌린 자본 곡선과 지금 `equity.csv`. 단일: 새 설정의 신호 · 매매 시세를 지금 입력의 첫날(지금 신호 시세 · Buy & Hold 기간 시세의 첫날)부터 잘라 같은 runner 로 돌린 자본 곡선 · 거래와 지금 `equity.csv` · `trades.csv`. 버퍼존 SSO · UPRO 는 지금 결과가 없어, 실물 첫날부터 자른 판을 실물 `SSO_max` · `UPRO_max` 와 `SPY_max` 로 돈 판과 견준다. 워크포워드 · 고원은 대상이 아니다(Risks). 견주기 전에 지금 설정을 같은 코드로 돌린 자본 곡선이 저장 결과와 같은지 먼저 본다 — 계획 2 에서 커밋된 결과가 그 전 시세로 만들어진 채였다(`HANDOFF.md` 4절). 6.11 측정에서 단일 11 · 포트폴리오 4 의 요약 값은 저장 결과와 같았다
- **S7. 결과는 COMMANDS ④ 의 러너 넷으로 다시 만든다** — 단일 · 워크포워드 · 고원 · 포트폴리오. 합성 생성은 Phase 1 에서 한 번(GLD 보수), 마지막 Phase 에서 같은지 다시 본다

### 진행 로그 (KST)

- 2026-11-05 16:53: 계획서 작성 — 결정 10 · 13 확정(사용자 「# 버퍼존 SPY에 2배, 3배도 추가 # 나머지는 추천대로」) 뒤. 착수 전 측정은 연구 문서 6.11
- 2026-11-05 17:06: 승인(「추천대로 진행」) — Phase 0 착수
- 2026-11-05 17:20: Phase 1 대조 — `git status --short storage` 에 `GLD_synthetic_max.csv` · `summary.csv` · `years.csv` 셋만 `M`. GLD 합성 11,606 / 11,606행 · 날짜 같음, 바뀐 행 6,085 = 이음매 앞 행 6,085 (이음매 뒤 바뀐 행 0), 행마다 (새 ÷ 지금) 비율과 (1 − 0.004)^(−(2004-11-18 − 그날) ÷ 365.25) 의 상대 오차 최대 3.54e-08 (가격 넷), 거래량 같음, 첫 행 종가 59.473452 → 65.709597, 이음매 뒤 줄 ↔ `GLD_max.csv` `diff` 0줄. `summary.csv` 6 / 6행 · GLD 아닌 5행 같음, GLD 행 바뀐 열: 대용 파일(「(연 보수 0.4% 뺌)」), 대용 CAGR 10.59 → 10.15, CAGR 차 0.46 → 0.02, 대용 MDD −44.36 → −45.32, MDD 차 1.19 → 0.24, 12개월 상관 최저 0.7511 → 0.7512. `years.csv` 151 / 151행 · GLD 아닌 128행 같음, GLD 행은 일간 상관 · 대용 수익률 · 수익률 차만 바뀜
- 2026-11-05 17:12: 회귀 ⑦ (결과를 다시 만들기 전, `scratchpad/probe/regression7.py`) — 단일 11 모두 행 · 날짜 같음 · 자본 차 최대 0.0 · 거래 같음 · 미청산 같음(버퍼존 TQQQ · QLD · QQQ 6,755행, SPY 8,297, GLD 5,322, TLT 5,904, Buy & Hold QQQ · TQQQ · QLD 6,954, GLD 5,521, TLT 6,103). SSO · UPRO 합성 자른 판 ↔ 실물 판 자본 곡선 · 거래 같음(시작 2007-04-09 · 2010-04-12, 4,923 · 4,165행, 거래 8 · 7, 연 14.71% · 22.20%). 포트폴리오 넷 행 · 날짜 같음 · 자본 차 최대 0.0 · 주수 열 같음 · 거래 수 같음(QQQ 보유 · D-1 · Q-2 5,491행 2005-01-03, Q-2-2XS 4,923행 2007-04-09)
- 2026-11-05 17:14: 러너 — 단일 7초 · 포트폴리오 8초 종료코드 0 · ERROR 0. 포트폴리오 넷 모두 1986-07-16 시작(로그 「같은 날 시작 — 가장 늦은 실험 portfolio_d1」 — D-1 · Q-2 · Q-2-2XS 가 같은 날이라 처음 것), 정합성 검증 통과 넷. 단일 13 · 포트폴리오 4 의 시작일 · 연 수익 · 최악 낙폭 · 거래 수는 6.11 과 10 개가 같고, 다른 다섯은 GLD 보수 넷(버퍼존 GLD 4.04 → 4.07 · −47.10 → −45.15, Buy & Hold GLD 3.87 → 3.65 · −69.67 → −71.97, Q-2 9.56 → 9.53 · −25.77 → −25.82, Q-2-2XS 13.47 → 13.44 · −45.78 → −45.83)과 같은 날 시작한 QQQ 보유(1985-10-01 14.94% → 1986-07-16 14.42%). 새 버퍼존 SSO 1980-10-14 ~ 2026-10-29 13.27% · −61.03% · 15, UPRO 15.42% · −80.05% · 15. 금이 든 Q-2 · Q-2-2XS 는 미국 거래일 110일이 빠짐(10,151 → 10,041행)
- 2026-11-05 17:25: 워크포워드 331초 · 고원 50초 종료코드 0 · ERROR 0. 워크포워드 윈도우 11 → 18, OOS 2005-03-01 → 1991-10-01 부터. `--experiment portfolio_q2_2xs` 단독 실행 1986-07-16 시작, 결과 8 파일 `cmp` 같음. AppTest 넷 예외 0. 결과 폴더 `backtest` 34M → 76M · `portfolio` 12M → 21M. 연구 문서 6.12 에 옮긴 숫자 — 표 17행(세전 전체 칸은 엔진 요약과 같음), 6.11 대비 달라진 다섯, 워크포워드 · 고원 37개 문자열을 출력 파일에서 기계적으로 대조(없는 것 0)
- 2026-11-05 17:28: 마지막 Phase — `black` 4파일, 합성 생성 다시 돌림 14 파일 바이트 같음 · 콘솔 「바뀜」 0 · 「같음」 308
- 2026-11-05 17:39: 코드 리뷰 1회차 — 11건(사본: `scratchpad/review1_before/`). 고침:
  - ① 「같은 날」 경로가 실제 시작일을 대조하지 않음 — 엔진 시작일은 하한이라 그날 시세가 빈 자산(금 합성 110일)이 있는 실험은 조용히 다음 날 시작. 무거움(위험한 쪽 — 같은 날이라 말하고 다른 기간), 닿음(계기: 새 등록 실험 · 재수집으로 가장 늦은 날이 바뀜). 모든 실험을 `run_with_start_check` 로 부름(같은 모양 — 시작일 정책을 서술한 docstring 셋 · 도메인 문서 둘도 고침: `compute_portfolio_effective_start_date` · `run_portfolio_backtest` · `run_with_start_check` 와 그 오류 문구, `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`)
  - ⑥ 같은 날 규칙을 지키는 테스트가 0 이고 계산이 scripts 에 있음 — 막는 결함(시작일이 에러 없이 갈림)이 무거워 「비켜 간다」. 순수 함수 `portfolio_engine.planned_start_dates` 로 옮기고 테스트 넷(`TestPlannedStartDates`). 변형: 최댓값 → 최솟값 2 failed, 시작일을 정한 실험까지 묶음에 넣음 1 failed, 원본 `cmp` 같음 · 4 passed. ⑧(최댓값을 실험마다 다시 셈 · 같은 날 이름 하나만)은 같은 자리라 함께 없어짐 — 로그는 등록 실험의 데이터 시작일 전부를 냄
  - ⑦ 설정 테스트의 배분 규칙 분기에서 자산 · 신호용 시세 id 가 같으면 키가 겹쳐 실물 경로를 놓침 — 닿음(계기: 새 배분 규칙 실험), 목록으로 모음
  - ⑩ 이번에 쓴 주석 일곱이 사용자 규칙(간결체 · 이유)과 다름 — 그 외지만 사용자 규칙 위반이라 고침
  - 고친 뒤: 포트폴리오 테스트 두 파일 61 passed, 러너 전체 · Q-2 단독 재실행 결과가 고치기 전과 바이트 같음(`diff -rq`), 모두 1986-07-16
  - 고치지 않음 — ② 금 합성에 없는 미국 거래일 110일(그중 월 마지막 거래일 29일)이 금이 든 포트폴리오에서 빠짐: 결정 6 · `src/qbt/utils/CLAUDE.md` 「시세는 메우지 않는다」와 계획서 Risks 가 받아들인 모양 — 29일은 직접 세어 연구 문서 6.12 에 더함 · ③ 다른 실험의 데이터에 시작일이 묶임(S4 로 정함 · Risks) · ④ 는 ① 과 함께 고침 · ⑤ 포트폴리오 대시보드 캡션 「실험마다 시작일이 다릅니다」(그 외 — 표시, 대시보드 수정은 비목표) · ⑨ 하나만 돌려도 등록 실험 전부를 읽음(그 외 — 성능, S4 의 대가) · ⑪ 인계서 머리 · 4절이 어긋남(그 외 — 세션 마무리에서 고침)
- 2026-11-05 17:50: 코드 리뷰 2회차 — 13건(사본: `scratchpad/review2_before/`). 고침:
  - ⑤ 새 설정 테스트가 파일 이름 끝만 보고 신호 · 매매 짝을 고정하지 않음 — 운용 포트폴리오의 SSO · QLD 짝을 바꿔도 통과. 막는 결함(다른 상품 · 지수로 사고판 결과가 에러 없이 나감)이 무거워 「비켜 간다」. 1회차가 고친 함수와 다른 새 테스트로: 같은 모양 셋(버퍼존 · Buy & Hold · 포트폴리오 설정) — 매매 파일이 이름 · 자산 id 의 티커이고 신호가 그 지수의 1배 합성(`helpers.ONE_TIMES_SIGNAL_OF`). 변형 넷: 포트폴리오 sso 매매 → QLD 1 failed, qld 신호 → SPY 1 failed, 버퍼존 sso 매매 → UPRO 2 failed, Buy & Hold qld 매매 → TQQQ 2 failed, 원본 셋 `cmp` 같음 · 57 passed
  - 옮김(「같은 자리 두 번」 — 1회차가 고친 같은 날 시작 장치): ① 함께 시작할 날이 어느 실험의 거래일이 아니면 실행 도중 멈춰 앞 실험만 새 기간으로 저장 · ② 그날이 공통 거래일인지 보지 않고 오류 문구의 해결(그 실험에 min_start_date)이 같은 기간 비교를 깨뜨림 → 한 항목, ③ 하나만 돌리면 다른 실험의 저장 결과와 시작일이 갈릴 수 있음 · ⑨ 등록 실험 전부로 날을 정하는 계약의 테스트 없음 → 한 항목. 예시 날짜(1986-12-31 · 1987-04-20)가 미국 달력에 있고 Q-2-2XS 결과에 없음을 확인
  - 옮김(판정할 수 없음): ④ 합성 생성을 건너뛰면 모든 백테스트가 옛 끝날로 조용히 돎 — 정한 순서를 한 단계 건너뛰는 실수가 계기라 닿는지 판정하지 못함
  - 고치지 않음(그 외): ⑥ 단일 Buy & Hold 는 합성 첫날(1985-10-01), 짝 버퍼존은 1986-07-16 부터라 시작일이 9개월 어긋남 — 계획 5 전에도 단일 전략은 각자 데이터 첫날부터였다(Buy & Hold QQQ 1999-03-10 · 버퍼존 QQQ 1999-12-21) · ⑦ 포트폴리오 대시보드 캡션(1회차 ⑤ 와 같음) · ⑧ 로그가 그날을 정한 실험 이름 대신 데이터 시작일 표 전체를 `datetime.date(...)` 모양으로 냄 · ⑩ `deduct_annual_fee` 가 `tqqq/leveraged_comparison._with_annual_drift`(달력일 비례 연 복리 가격 보정, 그 파일 224행 · 호출 1곳)와 같은 계산 — 계획서 Context 의 「같은 일을 하는 함수가 없다」는 틀렸다. utils 는 tqqq 를 가져오지 못해 합치려면 함수를 utils 로 옮겨야 함 · ⑪ 단독 실행이 데이터를 두 번 준비(성능) · ⑫ 인계서 머리 · 4절이 어긋남(세션 마무리에서 고침) · ⑬ 인계서가 전역 「인계 문서를 두지 않는다」에 걸림(사용자가 명시적으로 요청한 문서)
  - 품질 검증: `black` 1파일, `validate_project.py` passed=856 · failed=0 · skipped=0 (Ruff · PyRight 통과, 경고 9 — 모두 `tests/qbt/test_analysis.py` 의 pandas 경고로 이번 변경과 무관)
- 2026-11-05 18:12: 수정분 검증(맥락 없는 서브에이전트, 사본과의 `diff -u` 6 hunk — 한 번 사용량 한도로 멈춰 사용자 「이어서 진행」 뒤 이어 돌림). 6 hunk 모두 ① 지금 설정에서 바뀌는 결과 없음(바뀐 세 파일 57 passed, `helpers` 를 쓰는 다른 네 파일 103 passed) · ③ 위험한 쪽으로 바뀜 아니오. 변형 14종 중 짝을 틀린 12종 실패, 통과 둘은 아래 발견. 발견 2 — 무거움 0, 고치지 않음:
  - 옮김: 포트폴리오 짝 테스트가 배분 규칙 매매법의 자산을 건너뜀(가벼움 — 등록 0개, 다시 등록하는 날 닿음)
  - 거름(기준 1 — 닿지 않음): Q-2-2XS 구성 자체(sso · qld 슬롯)를 고정하는 테스트가 없음(diff 밖, 원래 있던 구멍) — `asset_id` 와 매매 파일 두 칸을 함께 바꾸는 의도한 구성 변경일 때만 통과하고, 한 칸만 틀리면 잡힌다
  - 참고(발견 아님): `result_dir` · `display_name` 은 짝 테스트 밖, 포트폴리오 짝 테스트는 B&H 슬롯에도 1배 신호를 요구(어기면 실패하는 쪽)
