# 미룬 지적 — 판단 대기열

> 계획서가 고치지 않고 넘긴 코드 리뷰 지적을 모은다. 계획서는 임시 문서라 지워지므로, 남길 지적은 여기로 옮긴다.
>
> **이 파일을 처리할 때는 `/impl-plan` 「미룬 지적 옮기기」의 「처리」 순서를 따른다** —
> 항목마다 재현 → 재현 결과와 추천을 표로 → 고칠지는 사용자가 고른다.
> 버린 항목은 바로, 고친 항목은 그 계획서가 Done 될 때 지운다.
>
> 항목 형식: **자리**(옮긴 시점의 `파일:줄`과 함수 이름) · **무엇**(어떤 입력·상태에서 무엇이 틀리는가) · **종류**(무거운 버그 / 가벼운 버그) · **출처**(계획서 이름과 날짜, 평문)

---

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

## 마지막 날 체결 테스트가 「전날 신호 → 마지막 날 체결」을 만들지 못한다

- **자리**: `tests/qbt/test_buffer_zone_execution_rules.py:427` `test_last_day_pending_execution`. 지키려는 동작은 `src/qbt/backtest/engines/backtest_engine.py:323` `run_backtest` 의 「4-1. 예약된 주문 실행」 — 마지막 날에도 전날 종가로 예약한 주문을 그날 시가에 체결한다(`src/qbt/backtest/CLAUDE.md` 도메인 규칙 7)
- **무엇**: 테스트 데이터는 8일째(인덱스 7) 종가가 돌파해 9일째에 사고 마지막 날(10일째)에는 이미 들고 있다 — 「N-1일 신호 → N일 체결」이 일어나지 않아 마지막 날 position > 0 단언이 체결 규칙과 무관하게 참이다. 엔진이 마지막 날의 예약 주문을 버리게 바꿔도(4-1 앞에 `pending_order is not None and i == len(trade_df) - 1` 이면 `None`) 관련 테스트가 모두 통과한다 — 저장소 밖 사본에서 906 passed, 실패 1건은 사본에 `pyproject.toml` 이 없어 변형 없이도 나는 `test_logger` 의 루트 찾기다. 9일째에 돌파하는 데이터(종가 `[100]*8 + [107, 112]`, 시가 `[100]*8 + [105, 110]`, `ma_5` `[100]*8 + [103, 106]`)는 원래 엔진에서 마지막 날 90주, 그 변형에서 0주라 잡힌다
- **종류**: 무거운 버그 (검사 공백 — 막는 결함은 「마지막 날 매매가 조용히 빠져 틀린 수치가 에러 없이 나간다」)
- **출처**: PLAN_docs_comment_errors (2026-10-24) 사용자 결정 뒤 수정분 검증이 찾음, 2026-10-25 재현해 옮김

## 합성 스크립트가 상품 표를 저장 경로로 잇는 한 줄을 지키는 테스트가 없다

- **자리**: `scripts/tqqq/generate_synthetic.py:102` `main` 의 `save_stock_csv(merged_df, SYNTHETIC_DATA_PATHS[product_name], check_price_spikes=False)`. 표는 `src/qbt/tqqq/constants.py` 의 `DAILY_COMPARISON_TARGETS` · `SYNTHETIC_DATA_PATHS` 이고, 테스트 `tests/qbt/test_tqqq_simulation_outputs.py` `TestDailyComparisonTargets` 가 표의 값만 지킨다. 같은 모양이 `scripts/tqqq/generate_daily_comparison.py` `main` 의 반복문에도 있다
- **무엇**: 그 줄을 `SYNTHETIC_DATA_PATHS["TQQQ"]` 로 잘못 고치면 QLD 2배 시세가 전략이 읽는 `TQQQ_synthetic_max.csv` 를 에러 없이 덮어쓰는데, 전체 테스트가 통과한다 — 테스트는 scripts 를 불러오지 않는다. 배율 · 실물 시세를 넘기는 자리도 같다. 지금 코드는 맞게 잇고, 생성 파일은 실물 행 · QQQ 대비 기울기 대조로 확인했다. 막으려면 상품 하나의 합성 표를 돌려주는 함수를 `src/qbt/tqqq` 로 옮겨 테스트가 부르게 해야 한다
- **종류**: 무거운 버그 (검사 공백 — 막는 결함이 「틀린 수치가 에러 없이 나간다」)
- **출처**: PLAN_qld_synthetic (2026-11-01) 코드 리뷰 2회차 — 사용자가 고른 범위(파일 생성만)를 넘어 고치지 않고 옮김
