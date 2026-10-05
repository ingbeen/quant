# 미룬 지적 — 판단 대기열

> 계획서가 고치지 않고 넘긴 코드 리뷰 지적을 모은다. 계획서는 임시 문서라 지워지므로, 남길 지적은 여기로 옮긴다.
>
> **이 파일을 처리할 때는 `/impl-plan` 「미룬 지적 옮기기」의 「처리」 순서를 따른다** —
> 항목마다 재현 → 재현 결과와 추천을 표로 → 고칠지는 사용자가 고른다.
> 버린 항목은 바로, 고친 항목은 그 계획서가 Done 될 때 지운다.
>
> 항목 형식: **자리**(옮긴 시점의 `파일:줄`과 함수 이름) · **무엇**(어떤 입력·상태에서 무엇이 틀리는가) · **종류**(무거운 버그 / 가벼운 버그) · **출처**(계획서 이름과 날짜, 평문)

---

## 정합성 검사기가 엔진의 매매 판단을 다시 계산하지 않아, 엔진이 할 일을 «안 한» 경우를 정당하게 0 인 경우와 구별하지 못한다

- **자리**: 세 곳이 뿌리가 같다
  - 규칙 1 — `src/qbt/backtest/portfolio_validation.py:59` `_check_signal_execution_lag` 와 `src/qbt/backtest/engines/portfolio_engine.py:886` `_append_state_log_columns`(처리한 의도는 0주여도 `{키}_executed_intent` 에 남김)
  - 규칙 2 — `src/qbt/backtest/portfolio_validation.py:109` `_check_rebalance_weight_consistency`(매매법 하나 · 계좌 단위) · `:230` `_check_method_rebalance_weight_consistency`(매매법 단위)
  - 규칙 7 이전 — `src/qbt/backtest/portfolio_validation.py:344` `_check_capped_transfer`(상한 예외)
- **무엇**: 검사기는 「엔진이 한 일이 계획대로인가」는 보지만 「엔진이 해야 할 일을 했는가」는 판단을 다시 계산하지 않아 보지 못한다. 그래서 엔진 결함으로 할 일이 빠져도 정당하게 0 인 경우와 같은 모양이면 통과한다
  - 규칙 1: 0주 체결도 「처리됨」으로 기록하므로(1주 미만 주문이 검사기를 멈추던 문제의 수정) 「전날 의도를 다음 날 처리했나」만 본다. 모든 매수가 0주로 끝나는 엔진 결함을 넣으면 실제 설정 5개 모두 「위반 0 · 거래 0 · 최종 자본 10000000」이다(2026-10-04 재현). 0주가 정당했는지(목표 금액이 1주 값보다 작았나, 현금 부족으로 줄었나)를 보려면 엔진이 매수 축소 비율이나 0주 사유를 기록해야 한다. 이 수정 전(PLAN_rebalance_month_end 시점)에는 체결 기록이나 보유 변화가 있을 때만 기록해 규칙 1 이 이 결함을 잡았다
  - 규칙 2: 검사할 날을 엔진이 남긴 리밸런싱 표시(`rebalanced == True`)로 고른다. 판단일(월 마지막 거래일)에 매매법 안 편차가 임계값(10%)을 넘었는데 다음 날 리밸런싱이 통째로 빠지면 검사 대상이 아니다. 매매법 안 판정은 신호 청산 · 판정 제외 자산(그날 진입하거나 목표가 바뀐 자산)을 반영한 예상 상태로 하므로, 막으려면 검사기가 그 예상 상태를 상태 로그에서 다시 만들어야 한다
  - 규칙 7 이전: 판단일 장부로 계획 이전액을 다시 계산해 상한 규칙을 확인하지만, 「계획보다 적게 냈어도 그날 끝 현금이 0 이면 상한 때문」으로 인정하고 실제로 매도했는지는 보지 않는다. 판정이 넘었는데 엔진이 아무것도 안 했고 내주는 쪽이 원래 다 투자해 현금이 1 이하인 날을 통과시킨다. 「판정을 아예 안 하는」 엔진 결함으로 세면 판단일 1,619일 중 113일(7.0%)을 놓치고(예: 다 투자한 QLD 버퍼존 매매법, 남은 현금 0.21 – 0.31), 실행 단위로는 62회 중 61회를 잡는다(놓친 1회는 정상 이전액 0.14 로 허용 오차 1.0 아래). 장부만으로는 정당한 0 원 상한(내주는 쪽 매도가 1주 미만이라 0주 · 현금 0)과 구별되지 않는다 — `tests/qbt/test_portfolio_methods.py` 의 `TestMethodTransferCheck` `capped_to_zero` 가 그 모양을 통과로 고정한다. 막으려면 상태 로그에서 내주는 쪽이 그날 리밸런싱 의도를 처리했는지도 봐야 한다(위 규칙 1 의 0주 기록과 얽힌다)
  - 같은 뿌리의 작은 자리: 규칙 2 는 리밸런싱 뒤 0주로 끝난 자산을 건너뛴다(`portfolio_validation.py:118` · `:246` 의 `shares <= 0: continue`), 규칙 3 은 `EXIT_ALL` 을 처리한 행만 본다(기존 코드)
  - 지금 엔진은 이 셋을 빠뜨리지 않는다(실제 산출물 5개 위반 0). 계획서 ③ 은 엔진을 고치지 않으므로(설계서 D27) 드러날 계기는 엔진을 다시 고칠 때다
- **종류**: 무거운 버그 (검사를 비켜 간다)
- **출처**: PLAN_multi_method_engine (2026-10-04) 수정분 검증 — 규칙 2 는 F5 를 고칠 때 같은 모양 찾기(계좌 단위는 PLAN_rebalance_month_end 부터 있던 코드, 매매법 단위는 그것을 옮긴 코드), 규칙 1 · 규칙 7 은 규칙 7 재설계의 수정분 검증. 사용자가 미루기로 정함

## 매매법 장부의 cash · cost · target_share 열을 대조하는 검사 규칙이 없다

- **자리**: `src/qbt/backtest/engines/portfolio_engine.py:765` · `:767` · `:769` (장부 행 기록) · `src/qbt/backtest/portfolio_validation.py:465` `_check_method_shares_after_transfer`(목표를 장부 `target_share` 열에서 읽음)
- **무엇**: 장부의 `equity` · `pnl` · `transfers` 는 규칙 6, `share` 는 규칙 7 이 대조하지만 `cash`(매매법 자본 = 현금 + Σ 주수 × 종가), `cost`(단독 매매 비용 누적), `target_share`(설정의 몫)는 어떤 규칙도 대조하지 않는다. 엔진이 이 열을 잘못 기록해도 통과한다 — 예: 체결일 매매법 현금을 3,000,000 늘린 장부는 규칙 5 · 6 이 잡지 못하고 규칙 7 의 되돌리기 뒤 몫만 반응했다. `cash` 는 규칙 4(매매법) · 규칙 7 이, `target_share` 는 규칙 7 의 되돌리기 뒤 몫이 입력으로 쓰고, `cost` 는 `summary.json` 매매법 요약과 대시보드에 나간다. 2026-10-04 실제 산출물 5개에서 |자본 − (현금 + Σ주수×종가)| 최대 0, `target_share ≠ 설정` 0건(엔진은 맞게 기록한다)
- **종류**: 가벼운 버그 (검사 범위의 빈틈)
- **출처**: PLAN_multi_method_engine (2026-10-04) 수정분 검증 F8 과, F3(장부 `share` 열 미대조)을 고칠 때 같은 모양 찾기

## 같은 매매 데이터를 매매법마다 다른 자산 id 로 들면 상계되지 않는다

- **자리**: `src/qbt/backtest/engines/portfolio_data.py:170` `validate_portfolio_config`(같은 자산 id → 같은 매매 데이터만 검사)
- **무엇**: 설정 검증은 「같은 자산 id 면 같은 매매 데이터 경로」만 강제하고 반대(같은 경로 · 다른 자산 id)는 막지 않는다. 예: 매매법 q2_2xs 는 `gld`, 매매법 gold 는 `gold` 로 둘 다 GLD 데이터를 들면, 매매법 사이 되돌리기 날 한쪽이 팔고 다른 쪽이 사도 상계 행이 생기지 않아 절감이 빠지고(계좌 손익이 그만큼 낮게 나온다), `account_holdings` 에 같은 종목이 두 줄로 나온다. 경고 없이 검증을 통과한다. 2026-10-04 실제 산출물 5개 설정에서 0건. 계획서 ③ 에서 TLT 를 Q-2-2XS 와 HAA 가 같이 든다(D17)
- **종류**: 가벼운 버그 (틀린 수치가 에러 없이 나간다)
- **출처**: PLAN_multi_method_engine (2026-10-04) 코드 리뷰 1회차

## 매매법이 하나로 바뀐 실험을 다시 돌려도 이전 실행의 ledger.csv · netting.csv 가 남아 대시보드가 낡은 장부를 그린다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:474` `_save_portfolio_results` · `scripts/backtest/app_portfolio_backtest.py:212` `_load_ledger_csv`
- **무엇**: 러너는 매매법이 여럿일 때만 두 파일을 쓰고, 하나일 때는 지우지 않는다. 대시보드는 파일이 있는지만 보고 「매매법별 손익」 섹션을 그린다. 그래서 매매법이 여럿이던 실험을 `asset_slots`(매매법 하나)로 바꾸거나 같은 `result_dir` 을 재사용해 다시 돌리면, 새 결과와 무관한 매매법 손익 · 몫 추이가 오류 없이 보인다. 2026-10-04 실제 산출물 5개 폴더에서 0건
- **종류**: 가벼운 버그 (틀린 수치가 에러 없이 보인다)
- **출처**: PLAN_multi_method_engine (2026-10-04) 코드 리뷰 2회차

## 배분 규칙의 새 비중을 직전 목표와 float 로 정확히 비교해, 연속값 비중 규칙은 매일 조정 주문을 낸다

- **자리**: `src/qbt/backtest/engines/portfolio_methods.py:274` `generate_allocation_intents`
- **무엇**: `new_weight != old_targets[asset_id]` 로 목표 변경을 판정한다. 변동성 역가중처럼 연속값 비중을 내는 규칙은 부동소수점 잡음만 다른 비중(0.33333 대 0.3333300000001)에도 매일 REDUCE / INCREASE 의도를 만든다 — 대부분 0주로 끝나 상태 로그에 0주 체결이 쌓이고, 가끔 1주 매매로 비용이 나며 리밸런싱일이 대량으로 생긴다. 계획서 ③ 후보(HAA 0.25 단위 · 로테이션과 EWY 0 또는 1)는 이산 비중이라 해당하지 않는다. 2026-10-04 배분 규칙 등록 0 개
- **종류**: 가벼운 버그 (불필요한 매매 · 비용이 에러 없이 생긴다)
- **출처**: PLAN_multi_method_engine (2026-10-04) 코드 리뷰 2회차

## 성과 대시보드 「체결 전후 비교」가 매수만 있는 체결일을 빠뜨리고, 같은 날의 신호 체결을 「월초 정기」로 표시한다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:105` `_build_execution_comparison_df` · `scripts/backtest/app_portfolio_backtest.py:374` `_render_execution_comparison_section`
- **무엇**: ① 체결일 목록을 매도 거래의 `exit_date` 에서만 뽑는다. 매수만 있는 날(월중 버퍼존 재진입, 현금만으로 끝나는 리밸런싱)은 표에서 조용히 빠지고 「총 N개 체결일」 캡션도 줄어든 값이 나온다. 월말 판단 규칙에서는 월중 재진입이 매수만으로 끝나므로, 매수 진입(`ENTER_TO_TARGET`) 체결일(백테스트 첫 진입일 포함) 중 표에 나오는 날이 Q-2 는 21일 중 18일에서 1일로, Q-2-2XS 는 20일 중 16일에서 1일로 줄었다(예: Q-2-2XS 2007-08-27 qld, 2016-04-18 sso 누락). ② 사유를 그날의 `rebalance_reason` 하나로 붙여, 리밸런싱이 있는 날에는 같은 날 신호로 체결된 자산까지 「월초 정기」로 표시한다(예: Q-2-2XS 2010-07-01 qld 신호 매도). 진단 대시보드(`app_portfolio_debug.py`)의 체결 상세 표는 자산별 체결 유형을 먼저 보도록 고쳐져 이 문제가 없다
- **종류**: 가벼운 버그 (표시만 틀리고 성과 수치는 맞다)
- **출처**: PLAN_rebalance_month_end (2026-10-03) 코드 리뷰 1회차 · 2회차. 고치려면 러너가 만드는 `execution_comparison.csv` 형식(자산별 체결 유형)을 바꿔야 한다

## EWY 200일선 배분 규칙의 매수 체결 기록에 hold_days_used 가 0 으로 남아, 같은 신호의 버퍼존 슬롯(3)과 다르다

- **자리**: `src/qbt/backtest/allocators/ewy_buffer_zone.py:56` `EwyBufferZoneAllocator.target_weights` · `src/qbt/backtest/engines/portfolio_methods.py:217` `generate_allocation_intents`
- **무엇**: 규칙은 `BufferZoneStrategy` 로 신호를 내지만 `get_buy_meta()`(유지일 정보)를 넘길 길이 없다 — 배분 규칙은 비중만 반환하고, 배분 변화로 만든 진입 의도에는 `hold_days_used` 칸을 채우지 않는다. 그래서 EWY 규칙 실험의 매수 거래는 `trades.csv` 의 `hold_days_used` 가 늘 0 이고, 체결일이 같은 EWY 버퍼존 슬롯은 3 을 기록한다. 성과 · 체결일은 같다(2026-10-04 실데이터 체결일 29개 일치). 2026-10-04 기준 EWY 규칙을 쓰는 저장된 실험 0 개 — 계획서 ③-3 이 EWY 실험을 등록하면 그 결과 파일에 나타난다. 고치려면 배분 규칙 인터페이스나 배분 의도 생성(엔진)을 바꿔야 해 「엔진 무변경」(설계서 D27)과 부딪힌다
- **종류**: 가벼운 버그 (기록 칸이 에러 없이 틀린 값을 낸다, 성과 수치는 맞다)
- **출처**: PLAN_supplement_allocators (2026-10-04) 코드 리뷰 2회차

## HAA 배분 규칙이 입력 시세의 거래일 정렬을 확인하지 않는다 (로테이션 규칙은 확인한다)

- **자리**: `src/qbt/backtest/allocators/haa.py:78` `HaaAllocator._past_month_ends` · `:35` `momentum_scores`
- **무엇**: 월말 행을 TIP 시세의 날짜로 정하고, 다른 9개 시세는 같은 행 번호(`iloc`)로 읽는다. 10개 시세가 같은 거래일 행으로 정렬돼 있다는 엔진의 약속에 기대며 직접 확인하지 않는다 — 한 시세의 행이 하루 어긋나면 다른 날 종가로 수익률을 계산해 예외 없이 틀린 순위를 낸다. 로테이션 규칙(`us_weakness_rotation.py:58`)은 같은 가정을 날짜 대조로 확인하고 다르면 ValueError 를 낸다. 지금 엔진은 배분 규칙 시세를 공통 거래일로 맞춰 넘기므로 엔진 안에서는 생기지 않고(2026-10-04 실데이터 HAA 판단 231 개가 엔진 밖 단독 실행과 일치), 엔진의 자르기 방식이 바뀌거나 엔진 밖에서 정렬이 다른 시세로 부를 때 생긴다. 같은 자리의 작은 빈틈: TIP 점수가 NaN 이면 `NaN <= 0` 이 거짓이라 피신하지 않고 공격 자산으로 간다(다운로더 검증을 통과한 시세에는 NaN 이 없다)
- **종류**: 가벼운 버그 (틀린 순위가 에러 없이 나간다 — 지금 경로에서는 일어나지 않음)
- **출처**: PLAN_supplement_allocators (2026-10-04) 코드 리뷰 2회차

## 배분 규칙 생성자가 이동평균 기간 · 버퍼 비율 · 유지일을 검증하지 않는다

- **자리**: `src/qbt/backtest/allocators/ewy_buffer_zone.py:32` `EwyBufferZoneAllocator.__init__` · `src/qbt/backtest/allocators/us_weakness_rotation.py:30` `UsWeaknessRotationAllocator.__init__`
- **무엇**: `EwyBufferZoneAllocator(0, -0.1, 0.05, -1)` 처럼 잘못된 값으로도 만들어진다. 이동평균 기간 0 은 첫 호출의 `add_single_moving_average` 에서야 ValueError 가 나고, 음수 버퍼 · 유지일이나 퍼센트로 착각한 버퍼(5 = 500%)는 끝까지 엉뚱한 밴드로 돈다. 같은 검증을 하는 `resolve_buffer_params`(`src/qbt/backtest/strategies/buffer_zone.py:54`)가 이미 있다. 지금은 레지스트리가 `FIXED_4P_*` 상수만 넘겨 생기지 않는다(2026-10-04)
- **종류**: 가벼운 버그 (잘못된 파라미터가 에러 없이 결과를 낸다)
- **출처**: PLAN_supplement_allocators (2026-10-04) 코드 리뷰 1회차 · 2회차

## 보완 전략 등록 실험의 실제 시작일을 min_start_date 와 대조하지 않아, 데이터가 바뀌면 대시보드 숫자가 그리드와 조용히 어긋날 수 있다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:653` `main`(시작일 = max(엔진 유효 시작일, 2005-01-01, `min_start_date`)) · `src/qbt/backtest/portfolio_types.py` `PortfolioConfig.min_start_date`
- **무엇**: `min_start_date` 는 하한이라, 시세가 바뀌어 등록 실험(`portfolio_q2_2xs_{shy,gold,haa,rotation}25`)의 엔진 유효 시작일이 그 날짜(2007-06-22)보다 늦어지면 실험이 그 늦은 날부터 돌고 대시보드 숫자가 그리드 결과(`storage/results/portfolio_grid/`)와 기간만큼 달라진다. 러너는 실제 시작일이 `min_start_date` 와 같은지 보지 않는다(그리드 워커 `run_grid_case` 는 같은 상황에서 ValueError 로 멈춘다). 엔진은 이 칸을 읽지 않으므로 포트폴리오 러너 밖에서 `run_portfolio_backtest(config)` 를 부르는 코드는 칸 자체를 무시한다. 2026-10-04 실제 산출물: 등록 넷 모두 2007-06-22 시작(0건)
- **종류**: 가벼운 버그 (기간이 다른 숫자가 에러 없이 보인다)
- **출처**: PLAN_supplement_grid_judgment (2026-10-04) 코드 리뷰 1회차

## 배분 규칙 매매법의 비중 조정 사유를 「리밸런싱한 날 + 빈 사유」로 추론해, 설정 순서에 따라 정기 리밸런싱이 「배분 조정」으로 보이거나 조정이 「월초 정기」에 가려진다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:139` `_build_execution_comparison_df`(빈 사유 → `allocation`) · `scripts/backtest/app_portfolio_backtest.py:1228` 리밸런싱 마커 hover · `src/qbt/backtest/engines/portfolio_engine.py:632`(계좌 사유 = 설정 순서상 처음으로 리밸런싱한 매매법의 사유) · `scripts/backtest/app_portfolio_debug.py:334` · `:546`
- **무엇**: 엔진은 배분 규칙 매매법이 비중만 조정한 날 사유를 빈 값으로 남기고, 소비자 두 곳이 「리밸런싱했는데 사유가 빈 날 = 배분 조정」으로 추론한다(설계서 D40 — 엔진은 고치지 않는다). ① 배분 규칙 매매법이 슬롯 매매법보다 **앞에** 있는 설정이면, 같은 날 슬롯 매매법의 정기 리밸런싱이 계좌 사유에서 가려져 그날이 「배분 조정」으로 보인다 — 「Q-2-2XS 매매법이 앞」은 `build_experiment_config` 만 지키고 설정 순서를 검사하는 곳은 없다 ② 반대로 슬롯 매매법이 앞이면 같은 날의 배분 조정은 「월초 정기」에 가려진다(D40 이 받아들인 범위) — 2026-10-04 `portfolio_q2_2xs_haa25` 에서 HAA 장부가 조정한 18일 중 5일(2009-01-02 · 2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-03-01)이 「월초 정기」, 13일이 「배분 조정」으로 보인다 ③ 앞으로 사유 없이 `rebalanced` 를 세우는 엔진 경로가 생기면 그날도 「배분 조정」으로 잘못 보인다 ④ 진단 대시보드는 같은 날을 「예」 · 「리밸런싱」으로 보여 성과 대시보드와 표기가 다르다. 성과 수치는 모두 맞다. 2026-10-04 실제 산출물에서 ① · ③ 은 0건(등록 설정 모두 Q-2-2XS 가 앞). 근원 수정은 엔진이 조정 의도를 쓸 때 사유를 남기는 것이다(엔진 변경)
- **종류**: 가벼운 버그 (표시만 틀린다)
- **출처**: PLAN_supplement_grid_judgment (2026-10-04) 코드 리뷰 1회차 · 2회차. PLAN_multi_method_engine (2026-10-04) 코드 리뷰에서 옮겼던 「배분 규칙 매매법이 비중만 조정한 날 리밸런싱 사유가 틀리게 표시된다」 중 D40 으로 고치지 않은 부분

## 신호 일치율이 배분 규칙의 판단 보류 달(첫 판단 전의 0 비중)도 판단으로 센다

- **자리**: `src/qbt/backtest/supplement_experiment.py:462` `extract_decision_targets` · `:145` `HAA_GATE_START_DATE`
- **무엇**: 판단 비중표는 「월 마지막 거래일 다음 거래일 행」을 모두 그 달의 판단으로 센다. 배분 규칙이 판단을 보류(None)한 달에는 직전 목표(첫 판단 전이면 전부 0)가 그대로 들어가, 한쪽 판만 보류한 달이 「불일치」로 에러 없이 세진다. HAA 관문 시작일 2015-11-09 는 실물 PDBC(2014-11-07 시작)로 첫 판단일 2015-11-30 의 이전 월말이 정확히 12개라 여유가 0 이다 — PDBC 첫 행이 한 달만 늦어도 실물판 첫 달이 0 비중이 된다. HAA 관문 ② 는 0.9462(130달 중 123달, 95% 는 123.5달)라 한 달이 통과 · 탈락을 가른다. 2026-10-04 실제 산출물: 관문 실물판 · VEA 쌍 · BIL 쌍 모두 첫 행 비중 합 1.0, 합 0 인 판단 행 0건
- **종류**: 가벼운 버그 (일치율이 에러 없이 낮게 나올 수 있다)
- **출처**: PLAN_supplement_grid_judgment (2026-10-04) 코드 리뷰 2회차

## 대체-실물 비교의 「상장 전 교차 확인」 쌍이 실제로 상장 전까지만 잘리는지 강제하지 않는다

- **자리**: `scripts/data/generate_proxy_comparison.py:92` `PAIRS`(교차 확인 3쌍은 `:110` – `:112`) · `:149` `main` 의 `before` 계산 · `src/qbt/utils/proxy_comparison.py:170` `align_closes` 의 `before` 거르기
- **무엇**: 교차 확인 묶음(`GROUP_CROSS`)의 쌍은 넷째 칸에 실물 경로를 넣어야 그 실물 첫 거래일 앞까지만 잰다. 그런데 그 칸이 `None` 이어도, 실물 첫날이 비교 끝보다 늦어 `before` 가 아무 행도 자르지 않아도 오류 없이 전 구간으로 잰다. 그러면 요약 수치 대부분이 실물이 이미 있던 기간에서 나오는데, CSV · 대시보드는 그 묶음을 「실물이 없는 구간의 비교」로 보여 준다(2회차 리뷰가 고친 결함이 다시 생기는 길). 지금 3쌍은 모두 실제로 잘린다(비교일 6,312 → 1,484 · 5,906 → 1,963 · 5,906 → 480) — 0건이고, 계기는 `PAIRS` 에 교차 확인 쌍을 새로 더할 때다
- **종류**: 무거운 버그 (확인하지 않은 구간을 확인한 것처럼 보인다)
- **출처**: PLAN_long_proxy_comparison (2026-10-05) 2회차 수정분 검증
