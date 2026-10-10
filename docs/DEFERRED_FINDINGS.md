# 미룬 지적 — 판단 대기열

> 계획서가 고치지 않고 넘긴 코드 리뷰 지적을 모은다. 계획서는 임시 문서라 지워지므로, 남길 지적은 여기로 옮긴다.
>
> **이 파일을 처리할 때는 `/impl-plan` 「미룬 지적 옮기기」의 「처리」 순서를 따른다** —
> 항목마다 재현 → 재현 결과와 추천을 표로 → 고칠지는 사용자가 고른다.
> 버린 항목은 바로, 고친 항목은 그 계획서가 Done 될 때 지운다.
>
> 항목 형식: **자리**(옮긴 시점의 `파일:줄`과 함수 이름) · **무엇**(어떤 입력·상태에서 무엇이 틀리는가) · **종류**(무거운 버그 / 가벼운 버그) · **출처**(계획서 이름과 날짜, 평문)

---

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

## 성과 대시보드 「체결 전후 비교」가 매수만 있는 체결일을 빠뜨리고, 같은 날의 신호 체결을 「월초 정기」로 표시한다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:105` `_build_execution_comparison_df` · `scripts/backtest/app_portfolio_backtest.py:374` `_render_execution_comparison_section`
- **무엇**: ① 체결일 목록을 매도 거래의 `exit_date` 에서만 뽑는다. 매수만 있는 날(월중 버퍼존 재진입, 현금만으로 끝나는 리밸런싱)은 표에서 조용히 빠지고 「총 N개 체결일」 캡션도 줄어든 값이 나온다. 월말 판단 규칙에서는 월중 재진입이 매수만으로 끝나므로, 매수 진입(`ENTER_TO_TARGET`) 체결일(백테스트 첫 진입일 포함) 중 표에 나오는 날이 Q-2 는 21일 중 18일에서 1일로, Q-2-2XS 는 20일 중 16일에서 1일로 줄었다(예: Q-2-2XS 2007-08-27 qld, 2016-04-18 sso 누락). ② 사유를 그날의 `rebalance_reason` 하나로 붙여, 리밸런싱이 있는 날에는 같은 날 신호로 체결된 자산까지 「월초 정기」로 표시한다(예: Q-2-2XS 2010-07-01 qld 신호 매도). ③ 매도가 하나도 없는 실험은 표가 비어 러너가 `execution_comparison.csv` 를 쓰지 않고(`run_portfolio_backtest.py:365`), 대시보드는 「체결 전후 비교 데이터가 없습니다. run_portfolio_backtest.py를 재실행하세요.」를 보인다 — 재실행해도 생기지 않는다(2026-10-06 `portfolio_qqq_bh`, 첫 매수 1건뿐)
- **종류**: 가벼운 버그 (표시만 틀리고 성과 수치는 맞다)
- **출처**: PLAN_rebalance_month_end (2026-10-03) 코드 리뷰 1회차 · 2회차. ③ 은 PLAN_portfolio_lineup_cleanup (2026-10-06) 이 QQQ B&H 를 등록하며 결과 재산출에서 찾았고 그 계획서의 코드 리뷰 1회차가 다시 짚었다. 고치려면 러너가 만드는 `execution_comparison.csv` 형식(자산별 체결 유형)을 바꿔야 한다

## 보완 전략 등록 실험의 실제 시작일을 min_start_date 와 대조하지 않아, 데이터가 바뀌면 대시보드 숫자가 그리드와 조용히 어긋날 수 있다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:653` `main`(시작일 = max(엔진 유효 시작일, 2005-01-01, `min_start_date`)) · `src/qbt/backtest/portfolio_types.py` `PortfolioConfig.min_start_date`
- **무엇**: `min_start_date` 는 하한이라, 시세가 바뀌어 등록 실험(`portfolio_q2_2xs_haa10_rotation10`)의 엔진 유효 시작일이 그 날짜(2007-06-22)보다 늦어지면 실험이 그 늦은 날부터 돌고 대시보드 숫자가 조합 그리드 결과(`storage/results/portfolio_combo_grid/combo_runs.csv` 이어 붙인 판)와 기간만큼 달라진다. 러너는 실제 시작일이 `min_start_date` 와 같은지 보지 않는다(그리드 워커 `run_grid_case` · `run_combo_case` 는 같은 상황에서 ValueError 로 멈춘다). 엔진은 이 칸을 읽지 않으므로 포트폴리오 러너 밖에서 `run_portfolio_backtest(config)` 를 부르는 코드는 칸 자체를 무시한다. 2026-10-06 실제 산출물: 2007-06-22 시작(0건 — 엔진 유효 시작일 자체가 2007-06-22 라 여유가 0 이다)
- **종류**: 가벼운 버그 (기간이 다른 숫자가 에러 없이 보인다)
- **출처**: PLAN_supplement_grid_judgment (2026-10-04) 코드 리뷰 1회차. 등록 실험 이름 · 실측은 PLAN_supplement_registration (2026-10-05)에서 채택 등록으로 바꿨고, 함께 등록했던 SHY 20% 기준선은 PLAN_portfolio_lineup_cleanup (2026-10-06)에서 지웠다

## 배분 규칙 매매법의 비중 조정 사유를 「리밸런싱한 날 + 빈 사유」로 추론해, 설정 순서에 따라 정기 리밸런싱이 「배분 조정」으로 보이거나 조정이 「월초 정기」에 가려진다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:139` `_build_execution_comparison_df`(빈 사유 → `allocation`) · `scripts/backtest/app_portfolio_backtest.py:1228` 리밸런싱 마커 hover · `src/qbt/backtest/engines/portfolio_engine.py:632`(계좌 사유 = 설정 순서상 처음으로 리밸런싱한 매매법의 사유)
- **무엇**: 엔진은 배분 규칙 매매법이 비중만 조정한 날 사유를 빈 값으로 남기고, 소비자 두 곳이 「리밸런싱했는데 사유가 빈 날 = 배분 조정」으로 추론한다(설계서 D40 — 엔진은 고치지 않는다). ① 배분 규칙 매매법이 슬롯 매매법보다 **앞에** 있는 설정이면, 같은 날 슬롯 매매법의 정기 리밸런싱이 계좌 사유에서 가려져 그날이 「배분 조정」으로 보인다 — 「Q-2-2XS 매매법이 앞」은 구성 함수(`build_experiment_config` · `build_combo_config`)만 지키고 설정 순서를 검사하는 곳은 없다 ② 반대로 슬롯 매매법이 앞이면 같은 날의 배분 조정은 「월초 정기」에 가려진다(D40 이 받아들인 범위) — 2026-10-05 `portfolio_q2_2xs_haa10_rotation10` 에서 HAA 장부가 비중만 조정한 17일 중 4일(2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-04-01)이 「월초 정기」, 13일이 「배분 조정」으로 보인다(로테이션 장부는 늘 한 종목 100% 라 비중만 조정한 날이 0일) ③ 앞으로 사유 없이 `rebalanced` 를 세우는 엔진 경로가 생기면 그날도 「배분 조정」으로 잘못 보인다. 성과 수치는 모두 맞다. 2026-10-05 실제 산출물에서 ① · ③ 은 0건(등록 설정 모두 Q-2-2XS 가 앞). 근원 수정은 엔진이 조정 의도를 쓸 때 사유를 남기는 것이다(엔진 변경)
- **종류**: 가벼운 버그 (표시만 틀린다)
- **출처**: PLAN_supplement_grid_judgment (2026-10-04) 코드 리뷰 1회차 · 2회차. PLAN_multi_method_engine (2026-10-04) 코드 리뷰에서 옮겼던 「배분 규칙 매매법이 비중만 조정한 날 리밸런싱 사유가 틀리게 표시된다」 중 D40 으로 고치지 않은 부분. 실측은 PLAN_supplement_registration (2026-10-05)에서 채택 등록으로 다시 쟀다
