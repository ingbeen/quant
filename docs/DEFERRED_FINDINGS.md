# 미룬 지적 — 판단 대기열

> 계획서가 고치지 않고 넘긴 코드 리뷰 지적을 모은다. 계획서는 임시 문서라 지워지므로, 남길 지적은 여기로 옮긴다.
>
> **이 파일을 처리할 때는 `/impl-plan` 「미룬 지적 옮기기」의 「처리」 순서를 따른다** —
> 항목마다 재현 → 재현 결과와 추천을 표로 → 고칠지는 사용자가 고른다.
> 버린 항목은 바로, 고친 항목은 그 계획서가 Done 될 때 지운다.
>
> 항목 형식: **자리**(옮긴 시점의 `파일:줄`과 함수 이름) · **무엇**(어떤 입력·상태에서 무엇이 틀리는가) · **종류**(무거운 버그 / 가벼운 버그) · **출처**(계획서 이름과 날짜, 평문)

---

## 포트폴리오 리밸런싱이 1주 미만 차이에도 주문을 만들어 정합성 검사기가 실행을 멈출 수 있다

- **자리**: `src/qbt/backtest/engines/portfolio_rebalance.py:58` `RebalancePolicy.build_rebalance_intents` · `src/qbt/backtest/engines/portfolio_execution.py:132` · `:201` `execute_orders` · `src/qbt/backtest/portfolio_validation.py:43` `_check_signal_execution_lag`
- **무엇**: 리밸런싱이 발동하면 활성 자산 전부에 목표와의 차액만큼 `REDUCE_TO_TARGET` / `INCREASE_TO_TARGET` 를 만든다. 차액이 1주 가격보다 작으면 다음 날 `execute_orders` 가 0주로 처리해 체결 기록(`{자산}_executed_intent`)이 빈 값이 된다. 그러면 검사기 규칙 1(「전날 pending 이 다음 날 그대로 체결」)이 위반으로 잡고, `run_portfolio_backtest.py` 가 결과를 저장한 뒤 `ValueError` 로 멈춘다. 2026-10-03 기준 공식 결과 4개에서는 가장 작은 리밸런싱이 약 91주라 0건이지만, 자본이 작거나 1주 가격이 높은 종목, 또는 한 자산 안의 비중이 작게 쪼개지는 구성(보완 전략처럼 4종목에 나눠 담는 경우)에서는 일어날 수 있다. 판단일마다 무조건 리밸런싱하도록 바꾼 엔진 사본에서 `tests/qbt/test_portfolio_state_log.py` 의 `test_pending_intent_executed_next_day` 가 `pending=INCREASE_TO_TARGET -> 다음날 executed=` 로 실패해 재현됐다
- **종류**: 무거운 버그 (실행이 멈춘다)
- **출처**: PLAN_rebalance_month_end (2026-10-03) 코드 리뷰 2회차. 후속 엔진 확장 계획서(매매법별 장부 · 종목 단위 상계 · 비중 변동)에서 함께 다룰 후보

## 성과 대시보드 「체결 전후 비교」가 매수만 있는 체결일을 빠뜨리고, 같은 날의 신호 체결을 「월초 정기」로 표시한다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:105` `_build_execution_comparison_df` · `scripts/backtest/app_portfolio_backtest.py:374` `_render_execution_comparison_section`
- **무엇**: ① 체결일 목록을 매도 거래의 `exit_date` 에서만 뽑는다. 매수만 있는 날(월중 버퍼존 재진입, 현금만으로 끝나는 리밸런싱)은 표에서 조용히 빠지고 「총 N개 체결일」 캡션도 줄어든 값이 나온다. 월말 판단 규칙에서는 월중 재진입이 매수만으로 끝나므로, 매수 진입(`ENTER_TO_TARGET`) 체결일(백테스트 첫 진입일 포함) 중 표에 나오는 날이 Q-2 는 21일 중 18일에서 1일로, Q-2-2XS 는 20일 중 16일에서 1일로 줄었다(예: Q-2-2XS 2007-08-27 qld, 2016-04-18 sso 누락). ② 사유를 그날의 `rebalance_reason` 하나로 붙여, 리밸런싱이 있는 날에는 같은 날 신호로 체결된 자산까지 「월초 정기」로 표시한다(예: Q-2-2XS 2010-07-01 qld 신호 매도). 진단 대시보드(`app_portfolio_debug.py`)의 체결 상세 표는 자산별 체결 유형을 먼저 보도록 고쳐져 이 문제가 없다
- **종류**: 가벼운 버그 (표시만 틀리고 성과 수치는 맞다)
- **출처**: PLAN_rebalance_month_end (2026-10-03) 코드 리뷰 1회차 · 2회차. 고치려면 러너가 만드는 `execution_comparison.csv` 형식(자산별 체결 유형)을 바꿔야 한다
