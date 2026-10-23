# 미룬 지적 — 판단 대기열

> 계획서가 고치지 않고 넘긴 코드 리뷰 지적을 모은다. 계획서는 임시 문서라 지워지므로, 남길 지적은 여기로 옮긴다.
>
> **이 파일을 처리할 때는 `/impl-plan` 「미룬 지적 옮기기」의 「처리」 순서를 따른다** —
> 항목마다 재현 → 재현 결과와 추천을 표로 → 고칠지는 사용자가 고른다.
> 버린 항목은 바로, 고친 항목은 그 계획서가 Done 될 때 지운다.
>
> 항목 형식: **자리**(옮긴 시점의 `파일:줄`과 함수 이름) · **무엇**(어떤 입력·상태에서 무엇이 틀리는가) · **종류**(무거운 버그 / 가벼운 버그) · **출처**(계획서 이름과 날짜, 평문)

---

## 엔진이 에쿼티 표 · 상태 로그에 쓰는 표시용 열의 매매법 여럿 정의를 지키는 테스트가 없다

- **자리**: `src/qbt/backtest/engines/portfolio_engine.py:561` `run_portfolio_backtest` 의 계좌 사유(`rebalance_reason_today`) · `:643` 에쿼티 행의 `rebalance_reason` · `:651` 에쿼티 행의 `{키}_weight` · `:779` `_append_state_log_columns` 의 상태 로그 `{키}_weight`. 읽는 곳은 `scripts/backtest/app_portfolio_backtest.py` 의 자산별 비중 추이 차트(`_weight_columns`)와 리밸런싱 마커의 사유(매매법이 하나인 실험은 에쿼티의 계좌 사유를 쓴다)
- **무엇**: 엔진 코드를 아래처럼 바꿔도 전체 테스트(928개)가 통과한다 — ① 에쿼티 표의 `{키}_weight` 를 절반 값으로 ② 에쿼티 표의 `rebalance_reason` 을 늘 빈 값으로 ③ 계좌 사유를 그날 리밸런싱한 매매법 중 «마지막» 매매법의 사유로 ④ 상태 로그의 `{키}_weight` 를 계좌 자본이 아니라 매매법 자본 대비로. ①은 대시보드의 비중 추이가, ② ③은 매매법 하나짜리 실험의 리밸런싱 마커 사유가 에러 없이 틀리게 보인다. 상태 로그의 비중 · 리밸런싱 표시 · 사유를 지키는 테스트(`TestStateLogWeightColumn` · `TestMonthEndRebalanceSchedule::test_rebalance_logged_on_execution_day`)는 매매법 하나짜리 시나리오만 쓰고, 에쿼티 표의 같은 열은 지키는 테스트가 없다. 정합성 검사기는 이 열들을 읽지 않는다(규칙 2 는 장부와 주수 × 종가로 다시 계산한다). 지금 값은 맞다 — 같은 변형이 9단계 전 코드에서도 모두 통과했다
- **종류**: 무거운 버그 (검사 공백 — 막는 결함이 「틀린 수치가 에러 없이 나간다」)
- **출처**: PLAN_portfolio_validation (2026-10-11) 코드 리뷰 2회차의 수정분 검증

## 포트폴리오 러너가 구성 의존 파일 지우기를 부르는 한 줄을 지키는 테스트가 없다

- **자리**: `scripts/backtest/run_portfolio_backtest.py:106` `_save_portfolio_results` 의 `remove_config_dependent_files(result.config.result_dir)`. 함수는 `src/qbt/backtest/csv_export.py:207` `remove_config_dependent_files` 이고 테스트 `tests/qbt/test_csv_export.py` `TestRemoveConfigDependentFiles` 가 함수만 지킨다
- **무엇**: 그 호출 한 줄을 지워도 전체 테스트가 통과한다 — 테스트는 scripts 를 불러오지 않는다. 지워진 채로 매매법이 여럿이던 실험을 매매법 하나로 바꿔 같은 결과 폴더에 다시 저장하면 낡은 `ledger.csv` · `signal_{매매법}.{자산}.csv` 가 남고, 대시보드는 `ledger.csv` 가 있으면 「매매법별 손익」 섹션을 그 옛 장부로 에러 없이 그린다. 지금 코드는 맞게 부른다. 막으려면 포트폴리오 결과 저장(`_save_portfolio_results`)을 src 로 옮겨 테스트가 부르게 해야 한다
- **종류**: 무거운 버그 (검사 공백 — 막는 결함이 「틀린 수치가 에러 없이 나간다」)
- **출처**: PLAN_portfolio_engine_cleanup (2026-10-18) 코드 리뷰 1회차, 사용자 결정 「미룬 지적으로 옮긴다」(2026-10-19)

## 워크포워드 윈도우 차트가 윈도우 끝에 보유 중인 포지션의 Buy 마커를 그리지 않는다

- **자리**: `scripts/backtest/app_walkforward.py:621` `_render_window_detail` 의 `markers = [oos_start_marker, *build_trade_markers(trades_df)]` — 미청산 진입일(`open_entry_date`)을 넘기지 않는다. 윈도우 상세 결과는 `scripts/backtest/run_walkforward.py:199` `_save_window_detail_csvs` 가 시그널 · 에쿼티 · 거래 CSV 셋만 저장하고(`src/qbt/backtest/walkforward.py:592` `run_window_detail_backtests` 의 결과), 미청산 포지션 정보는 어디에도 남지 않는다
- **무엇**: 윈도우 상세 차트는 닫힌 거래만 Buy · Sell 마커로 그려, 윈도우가 끝날 때 아직 들고 있는 포지션은 진입 Buy 마커가 없다 — 에쿼티 패널은 보유 중으로 움직이는데 캔들에는 그 진입이 보이지 않는다. 지금 결과의 윈도우 에쿼티 44개 중 34개가 포지션을 들고 끝난다(마지막 행 `position > 0`). 단일 · 포트폴리오 대시보드는 결과의 `open_position` 으로 「Buy (보유중)」을 그린다(`dashboard_charts.build_trade_markers` 의 `open_entry_date`). 고치는 길은 러너가 윈도우마다 미청산 진입일을 저장하는 것이다(워크포워드 재실행 · 결과 파일 변화) — 대시보드가 에쿼티의 `position` 에서 계산하면 「대시보드는 도메인 계산을 하지 않는다」와 부딪힌다
- **종류**: 가벼운 버그 (표시 누락 — 수치가 틀리지는 않는다)
- **출처**: PLAN_dashboard_charts (2026-10-23) 코드 리뷰 2회차, 사용자 결정 「미룬 지적으로 옮긴다」(2026-10-23)
