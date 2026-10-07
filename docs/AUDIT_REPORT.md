# 전체 점검 보고서 (2026-10-07)

> 클라우드 세션에서 저장소 전체를 **읽기 전용**으로 점검한 결과다. 수정은 로컬 세션에서 하고, **이 문서는 처리가 끝나면 지운다**(임시 문서).
>
> - **기준**: 커밋 `c4a4d24`. 모든 줄 번호는 이 커밋 기준이다. 점검 시점 품질 검증 통과(ruff · pyright 0 · pytest 857 passed).
> - **방법**: 10개 영역(포트폴리오 엔진 / 단일 백테스트·워크포워드·실험 / tqqq·utils / scripts/backtest / scripts/data·tqqq / 안내 문서 / 연구 보고서 / 계획서 / DEFERRED / import·ignore·tests)을 전수 점검했다. 재현은 저장소 밖 임시 폴더와 메모리에서만 했다. 「틀린 값이 지금 나간다」는 지적은 결과 파일로 다시 확인했다.
> - **심각도**: 높음 = 지금 틀린 값·결론이 나간다 / 중간 = 잠재 오류(현재 데이터에선 0건)거나 단일 출처를 크게 어긴다 / 낮음 = 정리.
> - 같은 지적이 여러 카테고리에 걸리면 **한 곳에만 싣고** 다른 곳은 번호로 가리킨다.
> - **의도된 결정이라 제외한 것**: 입력 시세 반올림 6자리(루트 `CLAUDE.md`), `DEFAULT_TICKERS` 미변경(설계서 D43 ⑤), `periods.csv` 소비처 없음(D60), 금리·보수의 이전 달 대체 정책(`MAX_*_MONTHS_DIFF`).

**용어**

- **고원 구간**: 성과가 최고값의 80% 이상으로 유지되는 파라미터 범위.
- **워크포워드(WFO)**: 과거 구간(IS)에서 파라미터를 골라 이어지는 구간(OOS)에 적용해 보는 검증.
  - Dynamic = 구간마다 다시 고름.
  - Fixed = 처음 고른 값을 고정.
- **4P**: 확정 파라미터 넷(이동평균 기간 · 매수 버퍼 · 매도 버퍼 · 유지일, `FIXED_4P_*`).
- **매매법**: 한 실험 안의 독립 장부 단위(고정 비중 슬롯 묶음, 또는 HAA 같은 배분 규칙).
- **상계**: 같은 날 한 매매법이 팔고 다른 매매법이 산 같은 종목을 차이만 체결하는 것.
- **정합성 검사기**: 포트폴리오 실행 직후 결과가 규칙을 지켰는지 대조하는 `portfolio_validation.py`.

---

## 0. 먼저 볼 것 — 지금 틀린 값·결론이 나가는 곳

| # | 무엇이 틀리나 | 실측 | 항목 |
|---|---|---|---|
| 1 | 월별·연간 수익률에서 시작일~첫 월말 구간이 빠져 **모든 결과의 첫 해 연간 수익률**이 틀림 | Q-2-2XS 2007년: 저장 4.97% / 실제 5.12% | 1-1 |
| 2 | 대시보드 「연간 수익률 vs QQQ」 첫 해가 **기간이 다른 두 수익률**을 비교 | 채택 조합 2007 초과수익: 표시 −13.30%p / 같은 기간 −2.06%p | 1-2 |
| 3 | 고원 구간이 「연속 범위」가 아니라 **기준 넘는 첫 값~마지막 값** | QQQ 유지일 1 은 기준 미달(0.24 < 0.256)인데 0–10 을 칠함 | 1-3 |
| 4 | `전략_검증_보고서.md` §2.5 워크포워드 결론이 **현재 결과와 정반대** | 문서 Fixed ≥ Dynamic / 현재 QQQ Dynamic 9.46 · Fixed 5.16 | 13-R1 |
| 5 | `TQQQ_synthetic_max.csv` 가 6개월 낡아 **TQQQ 백테스트가 짧고 옛 가격** | 합성 2026-03-12 끝 / 원본 09-24 | 2-1 |
| 6 | 포트폴리오 「Buy $X (보유중)」 가격이 **진입가가 아니라 평균 단가** | Q-2 GLD 시가 42.80 캔들에 $201.9 | 1-4 |
| 7 | 스프레드 랩 「과최적화 아님」 판정이 **같은 파라미터를 기간만 달리 잰 비교** | 격차 0.31%p = 기간 차이 | 1-5 |
| 8 | 체결 전후 비교 표가 매수만 있는 날을 빠뜨리고 사유를 틀리게 붙임(DEFERRED 6 · 11) | D-1 · Q-2 · Q-2-2XS 매수 진입일 표시 0일 | 17 |

---

## 1. 비즈니스 로직 오류

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 1-1 | 높음 | `src/qbt/backtest/analysis.py:221-261` `calculate_monthly_returns` (+ `calculate_benchmark_yearly_returns` :379) | 월말 리샘플 뒤 `pct_change().dropna()` 로 시작일~첫 월말 수익이 사라진다(B&H QQQ 1999: 저장 74.16% / 실제 77.11%). → 리샘플 시리즈 앞에 첫 행 자본을 기준점으로 넣는다. CAGR·MDD·Calmar 는 에쿼티로 계산하므로 안 바뀌고, 월별·연간 표와 연구 문서의 첫 해 수치만 바뀐다(재산출 필요) |
| 1-2 | 높음 | `scripts/backtest/run_portfolio_backtest.py:202` `_save_benchmark_qqq_json` · `:641` · `app_portfolio_backtest.py:584` | QQQ 연간 수익률을 전체 실험 중 가장 이른 시작일(2005-01-01)로 한 번 계산해 공유한다. 늦게 시작한 실험의 첫 해는 「몇 달 대 1년」 비교가 되고, 캡션의 비교 기간도 벤치마크 기간이다. docstring :208 「문제 없다」도 틀렸다. → 실험마다 자기 시작일로 계산해 각 `summary.json` 에 넣는다(함수는 이미 시작일을 받는다). 그러면 공유 JSON · 시작일 계산 · 문서의 「QQQ 벤치마크 공유 정책」 단락이 함께 사라진다(정책 변경이라 결정 필요) |
| 1-3 | 높음 | `src/qbt/backtest/parameter_stability.py:82-113` `find_plateau_range` | docstring·`backtest/CLAUDE.md` 는 「연속 범위」인데 코드는 기준 이상인 첫·마지막 인덱스를 반환해 중간에 꺼진 값도 포함한다. → 최대값 위치에서 좌우로 기준 이상인 동안만 넓힌다 |
| 1-4 | 중간 | `run_portfolio_backtest.py:452-459` (`entry_price = final_avg_price`) · `app_portfolio_backtest.py:1529` `_build_portfolio_markers` | 날짜는 마지막 진입일, 가격은 이후 리밸런싱 매수가 섞인 평균 단가다(Q-2-2XS TLT 시가 47.70 자리에 $90.85). docstring 「단일 백테스트와 동일 규약」도 틀렸다. → 문구를 「보유중 · 평단 $X」로 |
| 1-5 | 중간 | `scripts/tqqq/spread_lab/app_rate_spread_lab.py:958-976` · `:829-845` · `:759-772` · `:1364-1391` · `:1074-1075` | 「완전 고정 WFO 이어 붙인 RMSE − 정적 RMSE」를 과최적화 격차로 해석한다. 두 값은 같은 (a, b)를 기간만 다르게 잰 것이고(정적 2010-02-11~, WFO 2015-02~), (a, b) 자체도 전 기간 튜닝값(meta `ab_source=global_tuning`)이라 OOS 가 아니다. → 정적 비교 판정 블록과 「과최적화 아님」 문구를 지우고, 같은 기간의 WFO 3자 비교만 남긴다. `tqqq/constants.py:69` 「(과최적화 검증 완료)」도 재검토 |
| 1-6 | 낮음 | `analysis.py:257` → `:264-303` `calculate_yearly_returns` | 반올림한 월 수익률로 연간 복리를 계산한다(`constants.py` 「반올림은 저장 직전에만」 위반, 최대 0.057%p 차). → 두 함수는 원값을 돌려주고 반올림은 저장 때 한다 |
| 1-7 | 낮음 | `app_walkforward.py:687-714` `_build_wfo_candle_data` · `run_walkforward.py:228` | WFO 대시보드만 4자리 가격으로 종가 % 를 다시 계산(1종)한다. 다른 대시보드는 러너가 저장한 4종 % 를 읽는다. → WFO 러너도 `add_ohlc_change_pct` 로 저장(7-1 과 함께) |
| 1-8 | 낮음 | `walkforward.py:202` · `backtest_engine.py:514` | 최적 파라미터 선택이 불안정 정렬이고 Calmar 동률 규칙이 없다(실데이터 22개 윈도우 동률 0건). → `kind="stable"` + 보조 키 |
| 1-9 | 낮음 | `backtest_engine.py:327-332` · `walkforward.py:430-470` `build_params_schedule` | OOS 시작마다 새 전략 객체로 바꿔 유지일 대기 상태가 버려진다(현재 결과 영향 0). → 파라미터가 같으면 schedule 에 넣지 않는다 |
| 1-10 | 낮음 | `walkforward_verdict.py:131-140` `_describe_wfe` | 두 모드 중 큰 값으로 「IS 성과의 약 N% 재현」을 쓴다(낙관 편향, 추정). → 두 값을 모두 표시 |

연구 문서의 결론 오류(§2.5 등)는 13-A 에 있다.

## 2. 버그

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 2-1 | 높음 | `storage/stock/TQQQ_synthetic_max.csv` · `docs/COMMANDS.md:116` | 2026-03-12 에서 끝나 `buffer_zone_tqqq` · `buy_and_hold_tqqq` 가 6개월 짧고 옛(배당 조정 전) 가격으로 돈다. 재생성하면 겹침 구간 종가가 최대 1.47 다르다. `tqqq_daily_comparison.csv` 도 07-24 에서 끝난다. 원인은 COMMANDS 의 「(선택)」 안내와 재실행 안내 부재다. → 재생성 + 안내 수정(일부러 고정한 것이면 무시) |
| 2-2 | 중간 | `src/qbt/tqqq/simulation.py:299-309` `_validate_ffr_coverage` | 일(day)을 유지한 채 다음 달로 넘어가 29–31일 시작이면 크래시하고(`2020-01-31` → ValueError), 끝 달을 누락한다. → 함수 삭제. 루프의 `lookup_ffr` 이 같은 정책으로 이미 fail-fast 한다 |
| 2-3 | 중간 | `src/qbt/utils/parallel_executor.py:205-237` `execute_parallel` | `except: raise` 가 `with ProcessPoolExecutor` 안이라, 남은 작업을 전부 끝낸 뒤 전파한다(10작업 실험 5.9초 / 수정 시 0.1초). `src/qbt/CLAUDE.md` 의 「즉시 전파」와 다르다. → `executor.shutdown(wait=False, cancel_futures=True)` 후 raise |
| 2-4 | 중간 | `scripts/tqqq/app_daily_comparison.py:44` `load_data(csv_path, _mtime)` | Streamlit 은 `_` 로 시작하는 인자를 캐시 키에서 뺀다. 그래서 CSV 를 다시 만들어도 옛 데이터가 보이는데 docstring(:32 · :50)은 반대로 적혀 있다. → 인자 이름을 `mtime` 으로 바꾸고(`app_proxy_comparison.py:52` 방식) `get_file_mtime` 래퍼를 삭제 |
| 2-5 | 중간 | `run_portfolio_backtest.py:291-320` `_save_portfolio_results` · `csv_export.py:67` | equity.csv 의 `{자산}_current_price` · `_return_pct` · `total_pnl` · `total_return_pct` 와 trades.csv 의 `order_amount` 가 반올림 없이 저장된다(채택 조합 equity 32개 열이 14–20자리). 루트 `CLAUDE.md` 의 「모든 저장 경로가 경유」 위반이다. → 읽는 소비자가 없으므로 저장에서 빼는 것이 가장 단순 |
| 2-6 | 중간 | `backtest_engine.py:500-501` `run_grid_search` | `os.cpu_count()==1` 이면 `max_workers=0` → ValueError. 같은 계산이 `run_supplement_grid.py:285` · `run_combo_grid.py:302` 에도 있다. → `parallel_executor` 기본값을 `max(1, cpu−1)` 하나로 두고 호출부 3곳의 계산을 지운다 |
| 2-7 | 낮음 | `run_walkforward.py:281-295` `_save_results` | `_pct` 2자리 분기가 먼저 걸려 `best_*_buffer_zone_pct` 4자리 분기에 도달하지 않는다(0.025 → 0.02, 현재 그리드 0건). → 열 이름을 명시한 사전 하나로 |
| 2-8 | 낮음 | `app_walkforward.py:632` `_load_window_csv_detail` | 거래 0건 윈도우의 1바이트 CSV 에서 `EmptyDataError` 가 난다. → `prepare_trades_for_csv` 가 빈 표에도 헤더를 쓰게 하고, `app_single_backtest.py:110` 의 예외 처리도 지운다 |
| 2-9 | 낮음 | `app_walkforward.py:591-597` `_render_param_drift` | 4행인데 높이·x축 제목은 5행 기준이다(파라미터 5개 시절 흔적). → `len(param_keys)` |
| 2-10 | 낮음 | `run_walkforward.py:301-315` | 이어 붙인 자본곡선의 equity 가 실수로 저장되고, 없는 열의 반올림 키가 있다. → 정수 · 키 삭제 |
| 2-11 | 낮음 | `src/qbt/backtest/engines/portfolio_engine.py:152-160` `_load_portfolio_data_with_common_period` | 신호 캐시 키(신호 경로 · 전략 · ma) 때문에, 같은 신호를 다른 매매 데이터로 드는 슬롯이 앞 슬롯의 교집합으로 잘린 이동평균을 받는다. 그래서 슬롯 순서에 따라 결과가 달라진다(재현 711,834 대 780,093, 현재 설정 0건). → 캐시 삭제(약 9줄) |
| 2-12 | 낮음 | `portfolio_engine.py:783-796` · `:805` | 거래가 0건이면 `trades_df` 의 열이 10개다(qqq_bh 10열 / d1 15열). → `PortfolioTradeRecord` 키 목록 하나에서 만든다 |
| 2-13 | 낮음 | `simulation.py:780-783` `calculate_validation_metrics` | 실제 누적수익률이 0 근처면 ValueError 가 나는데, 그 필드는 아무도 읽지 않는다. → 6-5 와 함께 삭제 |
| 2-14 | 낮음 | `src/qbt/utils/formatting.py:210-211` `TableLogger` | 헤더와 행이 한 칸 어긋난다(함수명 길이 차 3, 보정 2). → 모든 줄을 private 출력 메서드 하나로 |
| 2-15 | 낮음 | `validate_project.py:106-120` · `:168-196` | 개수 파싱이 첫 매칭 줄을 읽어 표시 개수가 틀릴 수 있다(통과 판정·exit code 는 정확). → 개수 파싱 삭제(약 70줄, 각 도구가 자기 요약을 출력) |
| 2-16 | 낮음 | `generate_daily_comparison.py:159-160` · `docs/research/late_entry_rally_opportunities.py:185` · `:369` | `+{x*100:.1f}%` 는 음수면 「+-」로 찍힌다 → `{x*100:+.1f}%`. 지연진입 스크립트는 기회가 0건인 자산이면 KeyError(현재 0건) |

## 3. 상수화 필요

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 3-1 | 중간 | `src/qbt/backtest/portfolio_types.py:29-70` | 자산 키 열 접미사를 7개만 중앙화했다. 나머지는 리터럴로 흩어져 있다: 엔진 f-string 10종(`portfolio_engine.py:723-729` · `:880-907`), `portfolio_data.py:233-238`, `portfolio_methods.py:359-365` · `:381-383` · `:414`, `portfolio_validation.py:242`, `supplement_experiment.py:210-212`(재정의), `app_portfolio_backtest.py:353` · `:358` · `:718` · `:814`, `run_portfolio_backtest.py:435`. → 접미사를 모두 `portfolio_types` 에 두고 `asset_col(key, SUFFIX)` 하나로 |
| 3-2 | 중간 | `portfolio_types.py:119-122` `AssetSlotConfig` 기본값 | 200/0.03/0.05/3 은 `FIXED_4P_*` 와 같은 값의 리터럴이다(배분 규칙은 상수를 쓴다). 그래서 4P 를 바꾸면 슬롯만 옛 값으로 남는다. `backtest/CLAUDE.md:100` 도 숫자를 복사했다. → `FIXED_4P_*` 를 쓰고 문서의 숫자를 지운다 |
| 3-3 | 중간 | 결과 파일 이름 | 러너와 대시보드 양쪽에 리터럴로 있다: `run_single_backtest.py:107` · `137` · `171` · `193` ↔ `app_single_backtest.py:143-146` / `run_portfolio_backtest.py:229` · `288` · `326` · `334` · `364` · `370` · `397` · `478-479` ↔ `app_portfolio_backtest.py:75` · `124` · `140` · `157` · `175` · `207` · `223` · `247` / `run_walkforward.py:240` · `254` · `257` ↔ `app_walkforward.py:886-888`. → `WALKFORWARD_*_FILENAME` 처럼 src 상수로 |
| 3-4 | 중간 | 고원 결과 | 경로·파일 패턴이 `run_param_plateau_all.py:48` · `327` ↔ `parameter_stability.py:23` · `48` 에 따로 있다. 파라미터 이름이 4곳에 나열된다(`_EXPERIMENT_META` · `_VALID_EXPERIMENTS` · 대시보드 `_TABS` · src `_CURRENT_VALUES`). 대시보드는 `"QQQ"` 를 리터럴로 찾는다(`app_parameter_stability.py:111`). → src 에 경로 함수와 파라미터 목록을 하나씩 |
| 3-5 | 중간 | 원본 티커 목록 | 4곳에 흩어져 있다(`download_data.py:31` `DEFAULT_TICKERS`, `generate_proxy_series.py:53-61`, COMMANDS 의 대체 10종 손 목록, `supplement_experiment.py`). HAA · 로테이션이 쓰는 6종(IWM · VWO · VNQ · IEF · TIP · EWY)은 어디에도 다운로드 대상으로 적혀 있지 않다. → `download_data.py` 에 「따로 받는 티커」 튜플을 두고 COMMANDS 는 그 이름만 가리킨다(`DEFAULT_TICKERS` 자체는 D43 대로 유지) |
| 3-6 | 중간 | `src/qbt/tqqq/simulation.py:692` `_save_daily_comparison_csv` | `.round(4)` 를 직접 쓴다. tqqq 는 `backtest.constants` 를 import 할 수 없어서 `ROUND_PRICE` 단일 출처 밖에 있다. → `ROUND_PRICE`(· `ROUND_RATIO`)를 `common_constants.py` 로 옮긴다 |
| 3-7 | 낮음 | 반올림 자릿수 숫자 직접 | `run_walkforward.py:182` · `184` · `291` · `293` · `295` · `477-481`, `run_single_backtest.py:202-209` · `262-267`, `run_param_plateau_all.py:116-118`, `runners.py:159-160`. 루트 규칙 「저장 지점에 숫자를 직접 적지 않는다」 위반. → `ROUND_PERCENT` · `ROUND_RATIO` |
| 3-8 | 낮음 | 리밸런싱 사유 문자열 | 엔진 비공개 `portfolio_engine.py:95-96`, `"methods"` 리터럴(`portfolio_methods.py:364` · `portfolio_validation.py:441`), 앱 재정의(`app_portfolio_backtest.py:80` · `:399`), `"allocation"`(러너 :82 · 앱 :82), 사유→문구 두 벌(앱 :399 · :1226). → `portfolio_types` 공개 상수 + 문구 사전 하나 |
| 3-9 | 낮음 | 주문 의도 종류 묶음 | `portfolio_engine.py:93-94` · `:395` · `:397`, `portfolio_execution.py:100` · `:187`, `portfolio_validation.py:48`. → `OrderIntent` 옆에 한 번만 정의 |
| 3-10 | 낮음 | `portfolio_configs.py:44/56` · `61/72` · `82/113` · `118/149` | 실험 이름을 `experiment_name` 과 `_make_result_dir` 에 두 번 적는다. `supplement_experiment.py:403` · `415` · `454` 도 같은 규칙을 따로 적는다. → 이름에서 결과 폴더를 파생 |
| 3-11 | 낮음 | `allocators/haa.py:18-19` | `HAA_ASSET_IDS = (*OFFENSIVE, "bil")` 리터럴이라 방어 자산 목록을 따라가지 않는다. → 두 목록의 합집합 |
| 3-12 | 낮음 | 화면 문구의 직접 수치 | `app_parameter_stability.py:225`(4P 값) · `:133/136`(80%), `app_portfolio_backtest.py:939`(10%), `run_supplement_grid.py:133`(95%) · `:134`(「7 중」), `app_rate_spread_lab.py:486`(RMSE 1.0467% — 바로 위 metric 은 1.0434) · 「60개월」 5곳, `app_walkforward.py:267-269` ↔ `walkforward_verdict.py:24-36` 임계값. → 원천 상수·결과에서 생성 |
| 3-13 | 낮음 | `app_walkforward.py:65` · `71` · `98` | 사전 3개가 `run_walkforward.py:77` `STRATEGY_CONFIG` 의 전략 이름을 다시 적는다. → config 에서 파생 |
| 3-14 | 낮음 | 이미 있는 상수를 안 씀 | `app_single_backtest.py:236` · `app_portfolio_backtest.py:1401`(`OHLC_CHANGE_PCT_COLUMNS`), `walkforward.py:201-234`(`"calmar"` 등 — `COL_*` 를 import 해 놓고 씀), `walkforward_verdict.py:421`(365.25 → `ANNUAL_DAYS`) |
| 3-15 | 낮음 | tqqq · utils 숫자 | 12·13개월이 5곳(`analysis_helpers.py:188`, `tqqq/constants.py:63`, `visualization.py:409` · `413` · `438`), `tqqq/data_loader.py:344-345` `fill_year = 1999`, `stock_downloader.py:139-140` · `160` 「2일」. → 이름 붙은 상수 하나씩 |
| 3-16 | 낮음 | `src/qbt/tqqq/constants.py:24` | 시세 경로 중 `TQQQ_DATA_PATH` 만 `common_constants` 밖에 있다. → 옮긴다 |

## 4. 불필요한 상수

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 4-1 | 낮음 | `src/qbt/backtest/constants.py:97` `COL_CHANGE_PCT` | 이 열을 만드는 코드가 없다(`run_walkforward.py:228` · `235` 는 걸러져 아무 일도 안 함). → 상수와 사용처 삭제 |
| 4-2 | 낮음 | `tqqq/constants.py:159-161` · `166` `KEY_FINAL_CLOSE_*` · `KEY_CUMULATIVE_RETURN_REL_DIFF` | 읽는 곳이 없고, `ValidationMetricsDict`(`simulation.py:73-91`)와 이중 표기다. → 필드와 함께 삭제(`KEY_*` 대신 TypedDict 키) |
| 4-3 | 낮음 | `tqqq/constants.py:42` `DEFAULT_SYNTHETIC_INITIAL_PRICE` | 이음매 스케일이 시작 가격을 흡수한다(200 대 1.0 결과 동일). → 삭제하고 1.0 사용 |
| 4-4 | 낮음 | `tqqq/constants.py:78-79` `WALKFORWARD_LOCAL_REFINE_A/B_DELTA` | 지워진 생성 스크립트의 설정값이고 설명문(`app_rate_spread_lab.py:1590`) 전용이다. → 삭제 |
| 4-5 | 낮음 | `tqqq/constants.py:98-103` | `COL_FFR_DATE` = `COL_EXPENSE_DATE` = `"DATE"`, `*_VALUE` 도 같다. → 한 쌍으로 |
| 4-6 | 낮음 | 한 파일에서만 쓰는데 공용 상수 파일에 있음(3계층 규칙 위반) | tqqq: `MAX_EXPENSE_MONTHS_DIFF`, `INTEGRITY_TOLERANCE`, `DEFAULT_MIN_MONTHS_FOR_ANALYSIS` · `COL_DAILY_SIGNED` · `COL_DR_LAG1/2`, `COL_CUMUL_MULTIPLE_LOG_DIFF_*`, 스프레드 랩 전용(`SOFTPLUS_*_PATH` 2 · `TQQQ_WALKFORWARD_*` 6 · `COL_A/B` · `COL_RMSE_PCT` · `DISPLAY_ERROR_END_OF_MONTH_PCT` · `SPREAD_LAB_DIR`). backtest: `CALMAR_MDD_ZERO_SUBSTITUTE`, `MIN_VALID_ROWS`, `DEFAULT_WFO_MIN_TRADES`, `COL_TOTAL_RETURN_PCT` · `COL_CALMAR` · `COL_FINAL_CAPITAL`, `COL_HOLDING_DAYS`. → 쓰는 파일 상단으로. `SPREAD_LAB_DIR` 는 `conftest.py:161` 의 patch 만 쓰는데, 파생 경로가 import 시점에 정해져 그 patch 도 효과가 없다 |
| 4-7 | 낮음 | `allocator_registry.py:61` · `67` `AllocatorSpec.allocator_id` (`StrategySpec.strategy_id` 도 같은 모양) | dict 키와 같은 값이고 읽는 곳이 0이다. → 칸 삭제 |
| 4-8 | 낮음 | scripts | `run_param_plateau_all.py:68-84` `_VALID_EXPERIMENTS`(= `_EXPERIMENT_META` 의 키, 둘째 칸 = 첫 칸), `run_portfolio_backtest.py:73` `_CONFIG_MAP`(argparse 선택지에만 쓰임), `run_supplement_grid.py:67-140` ↔ `run_combo_grid.py:62-130` 의 `DISPLAY_*` 14개 · `_YES` · `_NO` · `_CSV_ENCODING` 복붙, `app_rate_spread_lab.py:78` `DEFAULT_STREAMLIT_COLUMNS` |

## 5. 불필요한 함수

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 5-1 | 중간 | `simulation.py:540-619` `_calculate_cumul_multiple_log_diff` · `analysis_helpers.py:322-396` `validate_integrity` | 같은 공식(abs 로그차이 = 부호 있는 로그차이의 절댓값)의 두 구현을 서로 대조할 뿐이다(실데이터 4,180행 최대 차 4.6e-14). → `abs = signed.abs()` 한 줄로 바꾸고 두 함수 · `INTEGRITY_TOLERANCE` · `integrity_tolerance` 인자를 삭제(약 150줄) |
| 5-2 | 중간 | `strategies/buffer_zone.py:54-98` `resolve_buffer_params` · `backtest_engine.py:555-562` · `resolve_params_for_config`(:220) | 같은 4개 검사가 두 벌이고 한 줄 래퍼가 끼어 있다. → 검증을 `BufferStrategyParams.__post_init__` 하나로. 9-6(슬롯 파라미터)·DEFERRED 9 도 같은 자리에서 해결된다 |
| 5-3 | 중간 | `generate_proxy_series.py:64-86` ≡ `generate_long_proxy_series.py:79-106` `_save_price_csv` · `_describe` | 글자 단위로 같다. → src 저장 함수 하나로 모아 입력 `.round(6)` 지점을 1곳으로(루트 `CLAUDE.md` 반올림 표의 입력 지점 목록 갱신) |
| 5-4 | 낮음 | `spread_lab_helpers.py:88-132` `add_rate_change_lags` · `DEFAULT_LAG_LIST` · `COL_DR_LAG1/2` | 앱이 부르지만(:1645) 결과 열을 아무도 읽지 않는다(델타 차트는 직접 shift). → 삭제 |
| 5-5 | 낮음 | 「미등록 strategy_id」 검사 3벌 | `portfolio_data.py:50-52`, `portfolio_engine.py:219-221`, `portfolio_planning.py:71-73` `create_strategy_for_slot`(한 줄 래퍼). 둘은 도달하지 않는다. → `validate_portfolio_config` 에서 한 번만 |
| 5-6 | 낮음 | 중복 구현 | `proxy_series.py:27-32` ≡ `proxy_comparison.py:116-121` `_require_strictly_increasing_dates`, `tqqq/data_loader.py:59-104` FFR · 보수 로더, `walkforward.py:640` `_std`(= `statistics.stdev`), `app_portfolio_backtest.py:307` · `323` 같은 색상 함수 둘과 `_hex_to_rgba` 손 변환 2곳(:779-781 · :1286-1289), `generate_proxy_comparison.py` ↔ `app_proxy_comparison.py`(반올림 함수 · `"summary.csv"` · `"utf-8-sig"` · 이름 변환), `portfolio_execution.py:131`(매도가 하나를 구하려고 체결 함수 전체 호출) |
| 5-7 | 낮음 | 한 줄 래퍼 | `app_daily_comparison.py:28` `get_file_mtime`, `download_data.py:63` `_download_single`, `run_walkforward.py:91` `_load_data`, `run_param_plateau_all.py:145` `_load_asset_data`(`get_config` 두 번 호출 :156 · :175). → 인라인 |
| 5-8 | 낮음 | 프로덕션 호출부 없음(테스트 전용) | `walkforward.py:486` `load_wfo_results_from_csv` · `_WFO_CSV_*`, `parameter_stability.py:250` `get_plateau_dir`, `parallel_executor.py:132` `execute_parallel`(kwargs 판 내부와 테스트만). → 삭제하거나 합침 |

## 6. 데드코드

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 6-1 | 중간 | `walkforward.py` `rolling_is_months` 경로 · `_first_day_months_before` | 테스트 전용이다. 실제로 쓰면 IS 구간만으로 이동평균을 다시 계산해(`backtest_engine.py:473-474`) 틀린 결과를 낸다. `walkforward.py:258` 「IS 평가에 영향 없다」는 누적 모드에서만 맞다. → 삭제 |
| 6-2 | 중간 | `portfolio_engine.py:511-513` · `:524-528` | `data.series_dfs` 를 잘라 두고 아무도 읽지 않는다(배분 규칙은 `:505` 의 복사본을 받음). 「신호 시세도 잘린다」는 오해를 부른다. → 두 루프와 복사 삭제 |
| 6-3 | 낮음 | `backtest_engine.py:126-146` `_check_pending_conflict` · `PendingOrderConflictError` | 구조상 도달 불가(테스트가 직접 호출할 때만 발생). → 삭제하고 CLAUDE.md 의 「Critical Invariant」를 「구조로 보장」으로 |
| 6-4 | 낮음 | `strategies/buffer_zone_helpers.py:19-28` `HoldState` · `buffer_zone.py:379-412` | `start_date` 는 미사용, `buffer_pct` · `hold_days_required` 는 복사본이고, `check_buy` 의 `current_date` 는 `start_date` 용도뿐이다. → 경과 일수 하나로(Protocol 인자 제거는 별도 판단) |
| 6-5 | 낮음 | 쓰이지 않는 인자·칸 | `backtest_engine.py:527` `params_schedule`(테스트만) · `simulation.py:408` `ffr_dict`(호출 0) · `simulation.py:97` · `249-250` 고정 스프레드 float 경로(테스트만) · `simulation.py:403` · `476-482` `expense_dict` 와 `expense_df` 이중 · `simulation.py:780-807` 검증 결과 필드 4개 · `portfolio_methods.py:63` `MethodBook.initial_capital` · `portfolio_planning.py:33-36` `OrderIntent` 3칸(테스트만) · `portfolio_types.py:150-155` `AllocationAssetConfig.signal_data_path`(늘 매매 경로와 같고 엔진 `:172-173` 분기 도달 불가) · `portfolio_types.py:362-363` `PortfolioResult` 이름 2칸 · `portfolio_execution.py:154` `buy_buffer_pct`(늘 0.0) · `run_walkforward.py:263` `strategy_name` · `run_param_plateau_all.py:113` · `120-121` 행 필드 3개 · `types.py:46` `NotRequired`(항상 포함) · `analysis_helpers.py:282` · `301-304` `ffr_df=None` 분기와 `sum_daily_m` 자리채움 · `:306-310` 주석 처리 코드 · `formatting.py` `Align.CENTER` · `indent` · `logger.py:160` `level` 인자(테스트 전용) |
| 6-6 | 낮음 | 패키지 재노출 | `backtest/__init__.py` 8개, `strategies/__init__.py` `__all__` 5개, `utils/__init__.py`(`get_logger` 외)를 쓰는 곳이 없다. 그런데 import 할 때마다 엔진·병렬 모듈이 함께 로드된다. → 비운다 |
| 6-7 | 낮음 | 도달 불가 분기 | `walkforward.py:779` · `606-619`, `portfolio_engine.py:821`, `portfolio_methods.py:389`, `portfolio_data.py:240-245`(「도달 불가」 주석을 달고 0 채움, 바로 아래 :266-271 은 RuntimeError), `run_portfolio_backtest.py:263-269` · `:454`, `app_portfolio_backtest.py:1115` · `748` · `776`, `run_single_backtest.py:86` · `88`, `app_single_backtest.py:666` · `815-816`, `app_walkforward.py:128` · `849` · `878` · `1118-1119` · `1150`, `generate_synthetic.py:117-119` · `133-135`, `app_rate_spread_lab.py:1187`, 미사용 `logger`(:68 · :93), 빈 섹션 머리(:544-547) |
| 6-8 | 낮음 | 결과·메타 | `storage/results/meta.json` 의 8개 키(`grid_results` · `tqqq_validation` · `cscv_analysis` · `atr_comparison` · `wfo_comparison` · `wfo_stitched_backtest` · `cross_asset_bh_comparison` · `split_backtest`)를 쓰는 코드가 없다 → 삭제(스프레드 랩 5개는 유지). 포트폴리오 자산별 `win_rate` · `total_trades` · `final_avg_price`(`run_portfolio_backtest.py:419-461`)는 아무도 읽지 않는다. `download_data.py:57-58` `--start/--end` 결과 파일도 소비처가 없다(추정) |
| 6-9 | 중간 | tests | ① `enable_numpy_warnings` 픽스처(`conftest.py:312-340`)와 `test_numpy_warnings.py`: numpy 기본값을 시험할 뿐 효과가 없다 → 삭제(원하면 `pytest.ini` 에 `error::RuntimeWarning`, 현재 857 통과 확인). ② `test_portfolio_state_log.py:254` `test_weight_deviation_within_threshold_after_rebalance`: 픽스처에 리밸런싱 행이 0개라 항상 통과한다 → 데이터를 바꾸거나 삭제. ③ `pytest.ini:48-51` 마커 3개 사용 0. ④ `conftest.py:193` 없는 픽스처를 권장, `:333` 「Context7 Best Practice」. ⑤ `test_backtest_engine.py:141` `s._name`. ⑥ `mock_results_dir`(`conftest.py:116-168`)는 `mock_storage_paths` 의 부분집합(약 50줄) |
| 6-10 | 낮음 | `app_rate_spread_lab.py` 「파일 없음」 분기 8곳(:456-463 등) | git 이 추적하는 고정 산출물이고 생성 스크립트도 삭제됐다(추정) |

## 7. 리팩토링

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 7-1 | 중간 | 대시보드 3개(`app_single_backtest` · `app_portfolio_backtest` · `app_walkforward`) | lightweight-charts 코드가 300줄 이상 중복된다: `_detect_ma_col`(S:191 · P:1378 · W:653), 캔들(S:199 · P:1384 · W:661), 선 시리즈(S:297 · P:1460 · W:740), 마커(S:311 · P:1471 · W:751), 에쿼티·드로우다운(S:370 · 379 · W:801 · 810), 색 상수·테마. → Streamlit 에 의존하지 않는 dict 빌더 모듈 하나. scripts 끼리 import 금지라 위치는 src(`walkforward_verdict.py` 선례) — 위치는 결정 필요 |
| 7-2 | 중간 | `app_rate_spread_lab.py`(1,690줄, 여러 줄 문자열만 504줄) | 과최적화 판정 두 번, RMSE 추이 차트 두 번(:663-698 ⊂ :1019-1068), `dict(zip(...))` 6회, 정적 RMSE 로딩 3회, 동형 로더 5개. → 1-5 · 6-10 · 12-9 와 함께 약 300줄 감소 |
| 7-3 | 중간 | `scripts/tqqq/generate_synthetic.py:101-129` | `qbt.utils.proxy_series.splice_proxy` 를 손으로 재구현했다(결과 비트 동일). → `splice_proxy(synthetic_df, tqqq_df)` 한 줄(약 30줄). 이음매가 없을 때도 의미 있는 오류가 난다(9-8 해소) |
| 7-4 | 중간 | `portfolio_validation.py:90-127` · `:208-255` · `:514-522` | 정합성 규칙 2(리밸런싱 뒤 비중)를 계좌·매매법 단위 두 벌로 구현했다. 매매법이 하나면 같은 규칙이다. → 매매법 단위 하나(약 40줄) |
| 7-5 | 중간 | 버퍼존 밴드 산식 3곳 | `buffer_zone_helpers.compute_bands`, `csv_export.py:175-176`, `runners.py:80-82`(행마다 apply). → `compute_bands` 하나 |
| 7-6 | 낮음 | backtest · tqqq 계산 중복 | 유효 행 필터 3곳(`filter_valid_rows`, `runners.py:127-130`, `walkforward.py:361-364`), MDD 두 벌(`analysis.py:181-187` 과 `:85-99`), 그리드의 Calmar 재계산과 최적 행 재검색(`walkforward.py:201` · `336-348`), verdict CAGR 블록 중복(:182-192 = :225-235), MA 사전 계산 루프 3번(`walkforward.py:301` · `686` · `754`), 누적수익률 3번(`simulation.py:660` · `739` · `754`), 시그널 CSV 반올림 블록 3러너 |
| 7-7 | 낮음 | scripts 중복 | 두 그리드 러너 공용 코드(`_yes_no` · `_round_or_none` · 정합성 중단 블록 · 국면 열 루프), `run_param_plateau_all.py:182-269` 실험 블록 4개 · 피벗 두 벌, 월별 히트맵 두 구현(`app_single:585` · `app_portfolio:433`, 모양이 다름), 월별 집계가 두 함수에 쪼개짐(`aggregate_monthly` + `prepare_monthly_data`) |
| 7-8 | 낮음 | 포트폴리오 엔진 | `run_portfolio_backtest` 약 370줄(`portfolio_engine.py:467-835`, 체결 · 행 기록 인라인), 자산 키 목록 출처 3곳(엔진 루프 · `list_position_keys` · 검사기 열 파싱), 배분 비중 두 번 채움(`portfolio_methods.py:214` · 엔진 `:383-393`), 메시지용 RuntimeError 사전 검사 약 40줄(`portfolio_execution.py` · `portfolio_planning.py`) |
| 7-9 | 낮음 | tests | 복붙 헬퍼 7종(`_make_stock_df` · `_make_stock_df_with_sell` · `_make_portfolio_config`: scenarios ≡ execution / `_make_stock_df` 44줄: walkforward_schedule ≡ selection / `_weekdays` / `_fake_run` / `_build_equity_df` / `sample_monthly_df`) → 공용 모듈(이름 밑줄 없이, 복사본에서 검증함). 중복 테스트 3쌍: `test_analysis.py:35` ≡ `test_ma_type_policy.py:62` · `83`, 같은 `run_walkforward` 호출 두 번(`test_walkforward_schedule.py:414` · `test_walkforward_selection.py:283`, 합쳐 12초로 전체의 약 40%) → module-scope 픽스처, frozen 시험 두 번 |

## 8. 구조개선

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 8-1 | 중간 | `portfolio_configs.py:17-21` → `supplement_experiment`(→ 엔진 · 검사기) | 순환을 피하려고 Q-2-2XS 슬롯을 `q2_2xs_slots` 인자로 src · scripts 20곳에 넘긴다. 또 설정 목록만 import 해도 엔진·그리드 모듈이 로드된다. → 슬롯 튜플을 두 모듈이 함께 쓰는 하위 모듈로 내린다 |
| 8-2 | 낮음 | `walkforward.py:46` | `runners` 에서 `enrich_equity_with_bands` 를 가져온다(밴드 보강은 runners 의 책임이 아님). → `csv_export` 로(7-5 와 함께) |
| 8-3 | 낮음 | `portfolio_methods.py:333-416` `summarize_methods` · `account_target_weights` / `run_portfolio_backtest.py:419-461` | 러너 전용 결과 후처리가 엔진 하위 모듈과 러너에 나뉘어 있다. → 결과 후처리 모듈 하나 |
| 8-4 | 낮음 | `src/qbt/utils/proxy_series.py` · `proxy_comparison.py` | 도메인 로직인데 `utils/CLAUDE.md` 는 「도메인 독립 기능만」이라고 한다. 같은 문서가 두 모듈을 등록했으므로 의식적 배치로 보인다. → 문구 수정이 가장 싸다 |
| 8-5 | 낮음 | `tqqq/visualization.py` · `spread_lab_helpers.py` · `analysis_helpers.py` | 연구 대시보드 하나를 위한 코드가 src 3모듈에 걸쳐 있다. → 5-1 · 5-4 · 7-7 후 남는 `spread_lab_helpers`(약 30줄)는 흡수 |
| 8-6 | 낮음 | `parallel_executor.py:17` | `from qbt.utils import get_logger` 가 패키지 초기화 순서에 기댄다. → `from qbt.utils.logger import get_logger` |
| 8-7 | 낮음 | `docs/research/late_entry_rally_opportunities.py` | pyright 범위 밖이고 테스트가 없다. → `pyrightconfig.json` 의 include 에 `docs/research` 1줄 |

도메인 경계(backtest · tqqq · utils) 위반과 순환 import 는 0건이다.

## 9. 불가능 값 발생 시 중단되어야 하는데 누락된 곳

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 9-1 | 중간 | `portfolio_validation.py:168` · `:195` · 규칙 6 · 7 | NaN 비교가 모두 거짓이라 자본·현금이 NaN 인 행도 통과한다(검사기가 마지막 그물이다). → `validate_portfolio_result` 첫머리에 수치 열 NaN 검사 한 줄 |
| 9-2 | 중간 | `portfolio_validation.py:76-77` · `106-107` · `147-148` · `507-508` | 열이 없거나 상태 로그가 비면 규칙 1 · 2 · 3 · 7 을 조용히 건너뛴다(장부는 비면 멈추는 것과 불일치). → 분기를 지워 KeyError 로 멈추게 하고, :507 은 RuntimeError |
| 9-3 | 중간 | `src/qbt/tqqq/data_loader.py:164-174` `_create_monthly_data_dict` | 월별 금리·보수의 NaN · 범위를 검사하지 않는다. NaN 보수면 가격이 NaN 인데 지표는 남은 행만으로 나오고, 퍼센트 단위 FFR 이면 비용이 100배가 된다. → `isfinite and 0 <= v < 1` 한 줄(FFR · 보수 · 확장 dict 모두 이 함수를 거침) |
| 9-4 | 중간 | `simulation.py:488` · `496-498` `simulate` | 기초자산 종가 NaN 을 `pct_change` 가 앞 값으로 채워 「0% 인 날」로 처리한다. → 시작 시 `isna().any()` 면 ValueError |
| 9-5 | 낮음 | `backtest_engine.py:94-123` `_validate_backtest_inputs` | 시가·종가의 NaN · 0 이하를 검사하지 않는다(신호가 조용히 사라지거나, 자본 NaN 일 때 엉뚱한 「years <= 0」 메시지). → 한 줄 |
| 9-6 | 낮음 | `portfolio_data.py:118-178` `validate_portfolio_config` · `:73-83` `_validate_slots` | `total_capital` 0 · 음수 · NaN 이 통과한다(양수 검사가 루프 뒤 `build_combined_equity:198-200` 에 있음). 슬롯 비중 NaN 도 통과하고, 슬롯 전략 파라미터는 검증하지 않는다. → 검사를 설정 검증으로 옮기고 `not 0 <= w` 꼴로(파라미터는 5-2) |
| 9-7 | 낮음 | `walkforward.py:773-795` `run_window_detail_backtests` | 이동평균 워밍업 NaN 구간을 그대로 엔진에 넣는다(우연히 「신호 없음」이 될 뿐). → `filter_valid_rows` |
| 9-8 | 낮음 | `generate_synthetic.py:105-108` | 이음매 날짜가 없으면 메시지 없는 IndexError. → 7-3 으로 해소(`validate_stock_data` 는 3배 합성의 50% 급등락 임계와 맞지 않아 붙이지 않는다) |
| 9-9 | 낮음 | 대시보드 | `app_portfolio_backtest.py:339` · `345` · `953-1013` · `1040-1049` · `1148-1167`(키가 없으면 N/A · 0원), `app_walkforward.py:302-312` · `402` · `457`(파일이 없으면 빈 칸), `app_portfolio_backtest.py:1264-1265`(현금 비중 역산 + `clip`, 실제 cash/equity 와 0.03%p 차). → 직접 인덱싱 · 실제 열 사용 |

## 10. 내부/runtime import 전수 조사와 근본 해결

- **결과**: 함수 안 import 는 190건이고 전부 `tests/` 의 28파일에 있다. src · scripts · `validate_project.py` · `docs/research/*.py` 에는 0건이다(AST 집계 = `ruff --preview --select PLC0415` 집계).
  - 동적 import 1건: `test_walkforward_summary.py:267` 이 `importlib` 로 `scripts/backtest/run_walkforward.py` 를 읽는다.
- **원인**: 순환 회피 0건, monkeypatch 때문 0건이다(conftest 6건은 모듈 객체를 받아 setattr 하는 형태). 허용·요구하는 문서 규칙도 없다. 즉 습관이다.
- **검증**: 복사본에서 190건을 모두 상단으로 옮겼다 → pytest 857 passed · ruff I001 26건(자동 수정) · 이름 충돌 0 · pyright 0.

| 파일 | 건수 | 비고 |
|---|---|---|
| `test_buy_and_hold.py` | 23 | 고유 6개 |
| `test_tqqq_data_loader.py` | 18 | 2건은 상단과 중복 |
| `test_parameter_stability.py` · `test_tqqq_simulation_cost_model.py` · `test_walkforward_schedule.py` | 14 · 14 · 14 | schedule 은 4건이 상단과 중복 |
| `test_walkforward_selection.py` | 12 | |
| `test_buffer_zone.py` | 9 | :367 상단과 중복 |
| `test_engine_common.py` | 7 | 5건은 이미 상단에 있음(옮기다 만 상태) |
| `test_portfolio_planning.py` | 7 | `AssetState as NewAssetState` 를 `portfolio_engine` 경유로 import(실제 정의는 `portfolio_types`, 옛 이름) |
| `test_portfolio_execution.py` · `test_walkforward_windows.py` · `test_tqqq_simulation_outputs.py` | 7 · 7 · 7 | execution 은 `SLIPPAGE_RATE` × 7 |
| 나머지 16파일 | 1–6 | `test_portfolio_backtest_scenarios.py:618` 은 상단과 완전 중복 |

**근본 해결**

1. **일괄 상단 이동.** 190문장이 고유 104개로 줄고 `ruff --fix` 가 정렬한다. 동작 변화는 0이다.
2. **재발 방지.** ruff `PLC0415`(함수 안 import 금지)를 켠다.
   - 이 저장소의 ruff 0.8.6 에서는 preview 규칙이다. `preview = true` + `explicit-preview-rules = true` 를 두고 select 에 넣으면 이 규칙만 켜진다.
   - 부작용: preview 모드의 F841 이 튜플 언패킹 미사용 변수 37건을 새로 잡는다(`test_buffer_zone_execution_rules.py` 23건). `_` 로 바꾸거나, 정식 규칙인 버전으로 올린다.
3. **동적 import 제거.** `run_walkforward.py:170` `_round_summary_for_json` 을 src 로 옮긴다. 그러면 `importlib` · `# type: ignore` · `scripts/backtest/__pycache__` 부산물이 함께 사라진다. 같은 함수가 :182 · :184 에서 2 · 4 를 숫자로 적는 문제(3-7)도 해소된다.

## 11. `# type: ignore` 전수 조사와 근본 해결

- **전수**: 152줄 = `type: ignore` 100 · `pyright: ignore` 19 · `noqa` 33. 위치별로 src 6(전부 noqa) · scripts 11 · tests 135.
- **핵심 사실 (실험으로 확인)**
  - pyright 는 `# type: ignore[no-untyped-def]` 같은 mypy 괄호 코드를 읽지 않고 **줄 전체를 무시**한다. 그래서 앞으로 생길 오류까지 가린다.
  - 불필요 ignore 를 잡는 `reportUnnecessaryTypeIgnoreComment` 는 strict 에서도 기본으로 꺼져 있고, `pyrightconfig.json` 의 tests · scripts 환경은 명시적으로 `"none"` 이다.
- **참고**: pyright 는 venv 를 활성화한 조건(`poetry run`)에서만 0 errors 다. `.venv/bin/pyright` 를 직접 실행하면 pytest 를 못 찾아 약 500건이 나온다.

| 분류 | 건수 | 위치 | 해결 |
|---|---|---|---|
| 불필요(효과 없음) | 105 | tests 전반(scenarios 28 · portfolio_methods 25 · portfolio_planning 9 · strategy_types 7 · wfo_stitched 7 · execution 6 · state_log 6 · allocators 5 · 기타), `app_single_backtest.py:635-637` · `642` · `760`, `app_portfolio_backtest.py:1444` · `1448` | 삭제. tests · scripts 환경이 해당 규칙을 이미 꺼 두었다 |
| vendor import | 3 | `app_single_backtest.py:22`, `app_portfolio_backtest.py:27`, `app_walkforward.py:28` | 원인은 타입 정보 부재가 아니라, 편집 설치(import 훅)를 정적 분석기가 따라가지 못하는 것(reportMissingImports)이다. py.typed · 스텁은 소용없다. → `pyrightconfig.json` `extraPaths` 에 `vendor/streamlit-lightweight-charts-v5` 1줄 |
| 코드 수정 | 8 | `test_walkforward_schedule.py:535-548`(5, Protocol 타입으로 private 속성 접근), `test_backtest_engine.py:172` · `177` · `182`(3, MagicMock) | `assert isinstance(x, BufferZoneStrategy)` 뒤 접근 / `:137` `make_mock_strategy` 반환 타입을 `MagicMock` 으로 |
| 정당 | 3 | `test_buffer_zone.py:61`, `test_buffer_zone_contracts.py:78` · `99`(frozen dataclass 변경 시험) | `# pyright: ignore[reportAttributeAccessIssue]` 로 교체. 덤: `pytest.raises((AttributeError, Exception))` 은 모든 예외를 통과시키므로 `FrozenInstanceError` 로 좁힌다 |

- **`create_csv_file` 픽스처에 타입을 붙이면 사라지는가**: `no-untyped-def` 70건 중 56건이 이 픽스처 때문이다. 하지만 tests 환경이 그 규칙을 꺼 두어 지금도 효과가 없다. 테스트를 엄격 모드로 올릴 계획이 없으면 타입 정의보다 주석 삭제가 답이다.
  - 참고로 tests 환경의 완화를 전부 끄면 316건이 드러난다.
- **noqa 33건**
  - `ARG002` · `ARG005` 18건은 불필요하다(ruff `select` 에 ARG 규칙이 없음). 위치: src allocators 3(`ewy_buffer_zone.py:44` · `haa.py:52` · `us_weakness_rotation.py:39`), tests 15. → 삭제
  - `E712`(`== True`) 15건은 실제로 동작하지만 없앨 수 있다. 위치: `portfolio_validation.py:109` · `230`, `portfolio_methods.py:363`, `app_portfolio_backtest.py:1214`, tests 11.
  - 근거: `rebalanced` · `is_month_end` 열은 전부 bool 이고 결측 0이다. → `df[df["rebalanced"]]` 또는 `.eq(True)`
- **근본 해결** — 복사본에서 전부 적용한 뒤 pyright 0 · ruff 통과 · pytest 857 passed:
  1. `pyrightconfig.json`: 루트에 `"reportUnnecessaryTypeIgnoreComment": "error"`, tests · scripts 의 `"none"` 2줄 삭제, `extraPaths` 에 vendor 추가. 선택으로 `"enableTypeIgnoreComments": false` 까지 켜도 0 errors.
  2. 주석 126줄 삭제(ignore 108 + noqa 18). 재발 방지는 ruff `RUF100`.
  3. 코드 2곳 수정. → 저장소에 남는 ignore 는 frozen 시험 3건뿐이다.

## 12. 불필요한 fallback

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| 12-1 | 중간 | `app_parameter_stability.py:131-133` | `except (FileNotFoundError, KeyError)` 에서 필터 없는 고원을 칠하면서 라벨은 「저거래 제외」로 남는다(위험). → except 삭제 |
| 12-2 | 중간 | `walkforward.py:598-602` · `630-635` | `stitched_summary.get(..., 0.0)` · `isinstance`: 키는 항상 있고, 빠지면 수익 집중도 · CAGR 이 0 으로 숨는다. → 직접 인덱싱 |
| 12-3 | 낮음 | `walkforward_verdict.py:48-75` 안전 getter · `:411-419` try/except | 스키마 변경을 「데이터 없음」으로 숨긴다. → 직접 인덱싱 |
| 12-4 | 낮음 | `analysis.py:141-156` 빈 equity → CAGR 0 | 호출부가 2행 이상을 보장해 테스트만 이 동작을 고정한다(추정). → 예외 |
| 12-5 | 낮음 | `src/qbt/utils/data_loader.py:86-97` `load_stock_data` | 중복 날짜를 경고만 하고 지운다(문서화된 동작). 정렬이 불안정해 「첫 값 유지」도 거짓이다(실제 CSV 0건). → ValueError(결정 필요), 최소한 `kind="stable"` |
| 12-6 | 낮음 | 포트폴리오 엔진 | `portfolio_planning.py:92`(종가 없는 자산을 자본에서 조용히 뺌), `portfolio_rebalance.py:56` · `112` · `133` · `147`(키가 항상 있는 dict 에 `.get(aid, 0.0)`), `portfolio_engine.py:722` · `862`(`equity>0` 확인 뒤 EPSILON 을 또 더하고 0 이하는 0 비중), `portfolio_validation.py:81`(`=="nan"`), `portfolio_methods.py:177`(`max(cash, 0.0)`) |
| 12-7 | 낮음 | utils | `cli_helpers.py:59-66` 로거 대체 경로(테스트 전용), `logger.py:160` 알 수 없는 레벨이 조용히 DEBUG |
| 12-8 | 낮음 | 러너 | `run_single_backtest.py:267` `.get("win_rate", 0.0)`(바로 위 :196-198 주석 「silent default 금지」와 모순) · `:216`, `run_walkforward.py:318-325` · `358-361`, `run_portfolio_backtest.py:425` · `436-439` |
| 12-9 | 낮음 | 대시보드 | `app_single_backtest.py:157-164` · `708-709` · `721-723` · `738` · `797-833`(main 의 try/except — 다른 앱에는 없음), `app_portfolio_backtest.py:252`(`display_name` 폴백 — app_single 은 같은 경우 오류) · `814-815`, `app_walkforward.py:813` · `894-895`, `app_rate_spread_lab.py:862` · `988`(`else "2"`) · `:1037`(`get("b_mean", 0)`) · `.get("stitched_rmse")` 6곳 · 섹션별 `except Exception` 4곳(:197-201 등, docstring 의 즉시 중단 정책과 반대) |
| 12-10 | 낮음 | `validate_project.py:71-73` · `122-124` | 파싱 실패 기본값 1. → 2-15 와 함께 삭제 |

## 13. 문서/주석/코드 3자 불일치

### 13-A. 연구 보고서 결론·수치 ↔ 현재 결과

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| R1 | 높음 | `전략_검증_보고서.md` §2.5(L186-201) · §21.1(L1103-1119) · §22.3(L1169) · §25.5(L1362-1369) | 「Fixed ≥ Dynamic → 4P 동결 근거 유효」(QQQ 11.33/11.97)가 현재형으로 적혀 있다. 현재 `walkforward_summary.json` 은 QQQ Dynamic 9.46 / Fixed 5.16, TQQQ 19.38 / 9.25 로 정반대다. 역전은 부록 G.8 에만 기록돼 있다(G.8 은 「이 역전을 4P 동결의 반증으로 읽으면 안 된다」고 해설). → §2.5 표를 「EMA 시절 값, SMA 전환 후 역전 — 부록 G.8」 한 줄로, 나머지는 링크로 |
| R2 | 중간 | `전략_검증_보고서.md` §2.3 · §2.4(L154-184) · 부록 A.3(L1518) | 「현재」「summary.json 기준」이라고 적었지만 실제로는 EMA · 2026-03-12 기준 값이다(QQQ 문서 10.93/-36.49/0.30 · 현재 9.61/-30.26/0.32). IWM · EFA · EEM 은 결과 폴더도 없다. → 기준을 명시하고 A.3(= §19.1 중복)은 삭제 |
| R3 | 중간 | `QQQ_지연진입_연구.md` 1장 행동 규칙(L67-72) · 4장(L159-168) · 13.9 · 14.4(L672-689) | 진입가 646.816 · 폐기 기준 680.86 · 성과 1,021.37%/9.49% 를 「결과 파일 값」으로 적었다. 현재는 646.1427 · 약 680.15 · 1,066.05%/9.61% 다(수정주가 재조정 때문). → 실행 규칙 가격은 실제 체결가로 고정하거나 「데이터 갱신마다 재계산」을 명시 |
| R4 | 낮음 | `QQQ_지연진입_연구.md` L15-17 · L296-303, `전략_검증_보고서.md` G.5 L2702-2705 | 「2026-08-28 행 결측으로 갱신 불가」를 미해결로 적었는데 이미 해소됐다. → 삭제 |
| R5 | 낮음 | 그 밖 | `전략` §25.9 L1415 `split_strategy.py`(없는 파일), G.1 L2633-2635 「§14 등급표」(실제 §8.2), `지연` 12장 L375-378(같은 장 L347-351 과 자기모순), `상관` 12장 L394 「모든 수치 재현」(현재 0.6737 / 문서 0.6734), 설계서 「커밋 전」(L87 · L103 · L105, 실제 커밋됨), 지운 실험을 현재형으로(L1367 `gold30`, 7.3 L759 · 7.4 L771 · L1369 「25% 등록 D50」, L185), 머리말 「수치 예비」(L11-14, 8.3 이후는 정식 수치), D22 L663 `--end` 설명(실제 `stock_downloader.py:118-126` 과 다름) |

### 13-B. 안내 문서 ↔ 코드

| # | 심각도 | 위치 | 내용 → 제안 |
|---|---|---|---|
| D1 | 중간 | `docs/COMMANDS.md:149` (· :191) | `--cov` 「커버리지 포함 전체 검증」 ↔ 실제로는 Pytest 만 돈다(`validate_project.py:262-270`) |
| D2 | 중간 | `COMMANDS.md:72` | WFO 대상이 「`buffer_zone.py::CONFIGS`」(7개)로 적혀 있지만, 실제는 `run_walkforward.py` `STRATEGY_CONFIG` 2개다 |
| D3 | 중간 | `COMMANDS.md:88` · `:92` · `:86-94` | 대시보드 선행 번호 3 · 4 → 4 · 5. WFO 대시보드에 「WFE 분포」 섹션은 없다(실제는 윈도우별 상세) |
| D4 | 중간 | `COMMANDS.md:39` · `:116` | 포트폴리오 「TQQQ 합성 필요」는 틀렸다(5개 실험 중 0). 실제로 필요한 대용 시계열(`generate_proxy_series.py`)과 원본 IEF · IWM · SHY · TIP · VNQ · VWO(그리드는 EWY) 안내는 어디에도 없다. 반대로 TQQQ 합성은 단일 백테스트 · WFO 에 필요한데 「(선택)」이다(→ 2-1 · 3-5) |
| D5 | 중간 | `src/qbt/backtest/CLAUDE.md:583-588` · `608-610`, `scripts/CLAUDE.md:177` · `192` · `194` | 「결과 폴더를 스캔 · 알파벳 순 탭」 ↔ 실제는 `CONFIGS` · `PORTFOLIO_CONFIGS` 등록 순서다(QQQ B&H 를 맨 앞에 둔 것이 이 순서에 기댄다). 「Plotly 전용」 ↔ 실제로 lightweight-charts 를 쓴다 |
| D6 | 낮음 | `supplement_experiment.py:379` · `385`, `src/qbt/backtest/CLAUDE.md:263` | 「`build_experiment_config` 가 등록 실험과 그리드가 같은 구성임을 보장」 ↔ 등록 실험은 `build_combo_config` 만 쓴다(이 오류는 계획서에만 기록돼 있음) |
| D7 | 낮음 | `src/qbt/backtest/CLAUDE.md` 모듈 카탈로그 | `:424` `create_runner`(없음), `:448` · `450` `_enrich_equity_with_bands`(실제는 공개 함수), `:24` `grid_results.csv`(없음), `walkforward_verdict.py` 누락, Prettier 가 깨뜨린 이름(:61 · 62 · 374 · 421), 인자명(:192 `signal_date` ↔ `current_date`, `detect_buy_signal`), `:339` `strategy_common` 설명, `:460` 의존 화살표(`test_analysis.py:807-809` 와 반대, 실제는 서로 import 안 함), `:98` · `241` · `242` 「G · B 시리즈」, `:157` 내부 헬퍼(실제 8개), `:288` · `302` 결정 번호 범위가 docstring 과 다름. → 18-E1 축약으로 함께 해소 |
| D8 | 낮음 | `scripts/CLAUDE.md:247-261` · `:144` · `153-154`, `src/qbt/utils/CLAUDE.md:23-29` | CLI 인자 예외가 2개로 적혀 있지만 실제는 5개다(같은 문서 :147 · 152 · 172 와 모순). 포트폴리오 결과 목록에 `state_log` · `execution_comparison` 이 빠졌고, `load_signal_trade_pair` 도 빠졌다 |
| D9 | 낮음 | `src/qbt/CLAUDE.md` | :213 「가격 정밀도 통일」 ↔ 루트(입력 6 / 출력 4). :151 「순차 유리: 워크포워드」 ↔ 실제는 병렬 그리드. 「utils/data_loader 에서 모든 CSV 로딩」 · 「date 객체 통일」 ↔ tqqq 는 따로 로드하고 Timestamp 를 쓴다(`tqqq/data_loader.py:125`). 병렬 「즉시 전파」(→ 2-3)와 「Windows 에서 `__main__` 보호」(spawn 을 강제하므로 모든 OS 에 필요) |
| D10 | 낮음 | `.claude/plan-config.json` `evidence_home: "docs/"` | 문서 규칙은 근거·이력의 자리를 `docs/research/` 로 정한다(스킬 해석에 따라 불일치일 수 있음, 추정) |

### 13-C. 주석·docstring ↔ 코드

| # | 심각도 | 위치 | 내용 |
|---|---|---|---|
| C1 | 중간 | `app_parameter_stability.py:181` | 「거래 5회 미만(예: sell=0.15) 제외」 ↔ QQQ sell=0.15 는 거래 5회라 제외되지 않고 고원 안에 칠해진다. 같은 파일 :6 · :86 「7자산」 ↔ 실제 6자산 |
| C2 | 낮음 | `run_portfolio_backtest.py:8-9` · `portfolio_types.py:106` · `195` · `202-203` | 예시 실험 `portfolio_a2` · `c1` · 「G · B 시리즈」가 없다(argparse 가 거부) |
| C3 | 낮음 | `run_single_backtest.py:97` · `129` · `163` | 「가격 · MA · 밴드 6자리」 ↔ `ROUND_PRICE` 4 |
| C4 | 낮음 | `app_portfolio_backtest.py:704` | 기여도 「러너가 계산」 ↔ `:717` 「엔진이」 ↔ 실제는 `portfolio_data.py` |
| C5 | 낮음 | 포트폴리오 엔진 | `portfolio_execution.py:61-72`(축소 방식 ↔ :223), `portfolio_rebalance.py:72-73`(호출 조건 ↔ 엔진 :680), `portfolio_validation.py:110-111`(없는 `.get`), `portfolio_planning.py:152-153` · `199-200`(KeyError ↔ RuntimeError), `portfolio_engine.py:473-478`(Step 이름 ↔ 코드의 Step F), `engines/__init__.py`(`portfolio_methods` 누락), `portfolio_types.py:3`(TypedDict 없음), `PortfolioResult` equity_df 명세(:306-321, 열 누락), `portfolio_planning.py:52`(active_assets 기준), `current_equity` · `shared_cash` 이름(실제 값은 매매법 단위) |
| C6 | 낮음 | backtest | `types.py:17`(`BufferStrategyResultDict` 없음) · `:46`(빈 경우 설명), `strategies/__init__.py:8`(runners), `constants.py:31` · `test_buffer_zone.py:199`(`overfitting_analysis_report.md` 없음) |
| C7 | 낮음 | tqqq · utils | `tqqq/constants.py:94`(「영문 토큰」 아래 한글 `COL_*`, `src/qbt/CLAUDE.md` 의 COL=영문 원칙과도 다름), `analysis_helpers.py:63-64` · `136-137`(「날짜 범위 포함」 ↔ 실제는 행 인덱스), `common_constants.py:134`(「연간 영업일」 아래 365.25), `parallel_executor.py:51-62` · `168` · `178`(없는 호출부 예시) |
| C8 | 낮음 | scripts · tests | `late_entry_rally_opportunities.py:6` · `64`(「EMA200」 ↔ SMA200), `app_rate_spread_lab.py:1246` 주석, `test_buffer_zone.py:8` · `11` · `14`(「8개 자산」 ↔ 7), `test_walkforward_selection.py:274-278`(없는 값), `test_analysis.py:816`(「fresh import」), `tests/CLAUDE.md:152`(`mock_results_dir` 부분 설명) |

## 14. 문서 내용 중 중요하지 않지만 쉽게 변경될 수치·리스트

| 위치 | 내용 → 제안 |
|---|---|
| 루트 `CLAUDE.md:62-63` · `COMMANDS.md:54` · `62` · `165` · `173` | 날짜 붙은 실측 소요 시간(약 6분 · 76초 · 123초)이 두 문서에 중복돼 있다. → COMMANDS 한 곳에 「수 분」 정도의 범위만 |
| `src/qbt/backtest/CLAUDE.md:36` · `38` · `100` · `574` · `611`, `scripts/CLAUDE.md:158`, 루트 `CLAUDE.md:87` | 상수값 복사(0.3% · 0.6% · 1e10 · 200/0.03/0.05/3 · 10,000,000원 · 2005-01-01 · 15,012개 필드). → 상수 이름만 |
| `backtest/CLAUDE.md:150` · `157`, `tests/CLAUDE.md:139-140` | 개수(하위 모듈 5개 · 공개 API 2개 · 픽스처 3행 · 25행). → 삭제 |
| `scripts/CLAUDE.md:55-64`, `README.md:45`, `COMMANDS.md:86` · `90` · `94` · `236-238`, `src/qbt/CLAUDE.md:177-186`, 루트 `CLAUDE.md` 디렉토리 트리 | 목록: 메타 타입 10개, 대시보드 5개(일별 비교 · spread lab 누락), 대시보드 섹션 나열, 대체 티커, 결과 폴더(`wfo_windows_*` · `param_plateau` 누락), 트리(`scripts/data` 설명이 「데이터 다운로드」뿐). → 정본(코드 상수 · glob)을 가리키는 한 줄 |
| `Q2_2XS_보완_전략_설계.md` | `passed=852`(L87 외), 결과 폴더 크기 「14M」(L112, 현재 15M) · 4.5MB · 31MB, 실행 시간(L113 · 917 · 1167), 코드 줄 번호(L1589, 이미 어긋남), 「19종 · 75곳 · 8개 파일」(L136), SPY 종가 767.18 기준 계좌 하한(13장), 금리차 · 운용 규모(5.1 · 5.8) |
| `QQQ_지연진입_연구.md` | `signal.csv` 「2026-08-21, 6707행」(L152, 현재 09-24 · 6730행), 「최근 40거래일 +0.52 → 52거래일 뒤」(L688-689) |
| `전략_검증_보고서.md` | SOFR ~4.8%(L2352), UBT 운용 규모 · 거래량(L2437-2441), SSO/QLD/GLD/TLT 운용 규모(L2513 · 2578), 「테스트 6곳」(L2709), 「5,515행」(L2742) → 시장 사실은 「작성 시점」 한 줄로 묶거나 삭제 |
| `docs/DEFERRED_FINDINGS.md` | 13개 중 5개 항목의 줄 번호가 어긋났고, 날짜 붙은 실측이 낡았다 → 17절 |
| `app_rate_spread_lab.py` 화면 문구 | 「2026.02.08 기준」 10곳(:224 · 259 · 297 · 322 · 412 · 486 · 1453 · 1514 · 1555 · 1605), 「약 30-60분」(:1267) |

## 15. 문서·주석 내용 중 과거 상태·변경 이력·계획 단계

### 문서

- **루트 `CLAUDE.md`**
  - `:60`: 「2026-08-30 실측 — 8501 기동 실패」.
  - `:76-92`: 반올림 절이 결정 기록 형태다(제목의 날짜, 「통일했고」, 「15,012개 0건」, 「실제로 겪었다」, 「통일하기로 하면…」).
  - → 현재 규칙 4–5줄만 남기고 근거는 `docs/research/` 로.
- **`src/qbt/backtest/CLAUDE.md`**: `:490`(「제거되었다」), `:240`(「달랐다」), `:111`(「기존 결과 열 이름 유지」), `:288` · `302`(결정 번호).
- **`src/qbt/tqqq/CLAUDE.md`**: `:136`(「과최적화 검증 완료」 — 1-5 때문에 근거도 약함), `:239`(「git history 에서 복원」).
- **나머지 안내 문서**
  - `scripts/CLAUDE.md:209` · `COMMANDS.md:132`: 「확정 후 앱만 유지」.
  - `src/qbt/CLAUDE.md:95-99`: 「지양 접두사」(코드 사용 0건, 이행 흔적).
  - `tests/CLAUDE.md:171`.
- **`Q2_2XS_보완_전략_설계.md`**
  - 0장 세션 인계(L42-197, 155줄), 15장 세션 로그(L1476-1704, 229줄).
  - 본문의 「계획서」 190회 · `PLAN_*` 38회 · 세션 번호 S1–S9 181회, 10장 「구현 시 필요한 것」.
  - → 16-B(설계서 처리)로.
- **`전략_검증_보고서.md`**
  - 낡은 「다음 단계」: §2.6(L203-222), §11(L483-540, 이미 §13–§15 에서 실행됨), §19.4 · §41.5 · §45.5 · §53.5(「페이퍼 트레이딩 6~12개월」 3번).
  - §12.1 작업 순서 기록(L547-571).
  - §20.5 엔진 버그 6건(근거 파일 `backtest_changes_since_6f0a9bd.md` 없음).
  - G.6 · G.8.2(커밋 순서) · H.9 · J.7 · K.8.
  - L.3 「검토 중인 보완 전략」(이미 채택됨).
  - L.5 L4101 설계서 결정 번호 참조(설계서를 지우면 끊김).
- **`QQQ_지연진입_연구.md`**
  - 이력 박스 L58-61 · L83-89, 9장 정정(L287-291).
  - 9장 전체가 2026-08-27 라이브 스냅숏이다. 휩소 차단(직전 기회 뒤 60일 안의 신호를 버리는 규칙)의 만료일 9/27 도 이미 지났다.
  - 12장 스크립트 제거·복원 이력(L347-351), 13.8 「계획서 Phase 0」(L543-545).

### 코드 주석·docstring

- **src**
  - backtest: `strategy_common.py:9-10` · `:58`, `backtest_engine.py:316`(「B&H 첫 매수 타이밍 fix」), `walkforward_verdict.py:35`, `walkforward.py:528` · `549`(「(V2)」 — V1 없음), `supplement_experiment.py:243-244`.
  - 포트폴리오 엔진: `portfolio_engine.py:186` · `413`(「기존」) · `597`(「C안」), `portfolio_methods.py:54`(「C안」), `portfolio_types.py:234`, `portfolio_validation.py:516`, `portfolio_planning.py:257-258`(「달라졌다」), `portfolio_configs.py:157`(「결정 D75」).
  - tqqq: `simulation.py:669` · `676-677`, `analysis_helpers.py:306-310`(주석 처리 코드) · `330` · `340` · `355-356`, `tqqq/constants.py:69`, `tqqq/data_loader.py:327-328`.
- **결정 번호(D○○)**
  - `supplement_experiment.py` 44회, `combo_experiment.py` 23회.
  - tests 4파일 53줄(`test_combo_experiment` 16 · `test_supplement_experiment` 30 · `test_portfolio_methods` 5 · `test_portfolio_configs` 2).
  - `run_supplement_grid.py:5` · `:244`(터미널 표 제목에까지).
  - `.py` 전체 약 155곳 → 설계서 처리와 함께(16-B).
- **scripts**
  - `app_portfolio_backtest.py` 「신규 섹션」 8곳(:367 · 429 · 569 · 697 · 1351 · 1355 · 1359 · 1363).
  - `run_param_plateau_all.py:47`, `run_walkforward.py:74`(「기존 전략만」), `run_portfolio_backtest.py:616`(「활성 실험만」), `app_walkforward.py:82`(「app_single_backtest.py 패턴」).
  - `app_rate_spread_lab.py`: :139-148 모델 변천사, :225 · 260, :1001 · 1014(「삭제되었습니다」), VERBATIM #6 · #7 결번.
- **tests**
  - `test_backtest_engine.py:92` · `107-108`: `TestParamsScheduleWhile`(「if 로직에선 실패, while 로 바꾼 뒤 통과」).
  - `test_analysis.py:829`, `test_portfolio_backtest_scenarios.py:1105-1106`.
  - `NewAssetState` 8곳.
  - 「기존 동작」 9곳: `test_walkforward_schedule.py:264` · `270`, `test_walkforward_selection.py:208` · `235`, `test_portfolio_backtest_scenarios.py:764` · `805`, `test_tqqq_simulation_cost_model.py:547` · `559`, `test_tqqq_simulation_core.py:465`.
  - `test_walkforward_verdict.py:66` · `408-409`: 「과거 사고」(무엇인지 불명).

## 16. 계획서 정리

### 16-A. `docs/plans/` 10개

**결론: 10개 모두 정보 손실 없이 지울 수 있다.**

- 10개 모두 Done 이다(`[ ]` 0, TODO 0).
- 미룬 지적 13건은 전부 `DEFERRED_FINDINGS.md` 에 있다.
- 결정과 수치는 설계서(D 행 · 7.6 · 8.3 · 8.4 · 9.5 · 9.6)와 `전략_검증_보고서.md` 부록 L 에 이미 있다.
- 코드 · 테스트 · README · 루트 CLAUDE.md · COMMANDS · MEMORY · 보고서가 계획서를 참조하는 곳은 0건이다.
- DEFERRED 의 「출처」 칸은 평문이라 그대로 둬도 깨지지 않는다.

| 계획서 | 줄 | 계획서에만 있는 정보 | 권고 |
|---|---|---|---|
| `PLAN_rebalance_month_end` | 298 | 없음(부록 L.1–L.6) | 삭제 |
| `PLAN_rebalance_entering_exclusion` | 273 | 없음(부록 L.2 · L.5 · L.6) | 삭제 |
| `PLAN_multi_method_engine` | 375 | 없음(설계서 D33–D37) | 삭제 |
| `PLAN_supplement_data_proxy` | 325 | 없음(D43 · 8.3) | 삭제 |
| `PLAN_supplement_allocators` | 324 | 없음(D44 · 7.6) | 삭제 |
| `PLAN_supplement_grid_judgment` | 403 | 없음(D45–D50 · 9.5) | 삭제 |
| `PLAN_long_proxy_comparison` | 398 | 없음(D58–D61 · 8.4) | 삭제 |
| `PLAN_combo_grid` | 297 | 받아들인 한계 1건(대체 판 확인에서 기간이 어긋나면 CSV 를 하나도 저장하지 않고 멈춤 — 멈추는 쪽이고, `COMMANDS.md:243` 재생성 안내가 계기를 막음) | 삭제 |
| `PLAN_supplement_registration` | 224 | 문서 사실 오류 1건(13-B D6) | D6 을 고친 뒤 삭제 |
| `PLAN_portfolio_lineup_cleanup` | 218 | 문서 사실 오류 1건(13-B D5 의 탭 순서) | D5 를 고친 뒤 삭제 |

- **지우기 전 최소 작업**: ① 13-B 의 D5 · D6 수정 ② `docs/plans/.gitkeep` 유지(게이트 훅이 폴더 존재로 동작).
- **시점은 사용자 결정**: 설계서 D54 는 계획서를 「부록 M 확정 뒤 설계서와 함께」 지우기로 정했다. 지금 지우면 그 시점을 앞당기는 것이다.
- **참고**: 10개 모두에 같은 줄이 19개, 계획서마다 27–61줄이 양식(고정 규칙 · Done 규칙 · 경고)이다. 이는 전역 `/impl-plan` 양식 쪽 문제다(이 저장소 밖).

### 16-B. 설계서(`Q2_2XS_보완_전략_설계.md`, 1,704줄 · 265KB) — 가장 큰 문서 경량화

- **성격과 계획**: 설계서는 스스로 「설계서 + 진행 기록」을 표방하는 작업 문서다. 원래 계획(D53 · D54)은 결론을 `전략_검증_보고서.md` **부록 M** 으로 옮긴 뒤 이 문서와 계획서를 지우는 것인데, 부록 M 은 아직 없다(보고서는 부록 L 에서 끝남).
- **지우기 전에 해야 할 것**
  1. 부록 M 작성: 판정 중심, 결정 번호 없음(D53).
  2. 부록 M 에 담기지 않는 **엔진 설계 근거**(D29–D37 · D43 · D44, 탈락안, 정합성 검사기 규칙 6 · 7 의 근거)와 **알려진 한계**가 갈 곳을 정한다. 한계의 예: 「체결일에 하루 −30% 급락이 겹치면 검사기가 정상 결과에도 멈춘다」 — 설계서 :179 와 D37 에만 있다. 후보는 부록 L 또는 `src/qbt/backtest/CLAUDE.md` 「도메인 규칙」.
  3. 결정 번호 참조를 절 참조나 문장으로 바꾼다: 코드 · 테스트 `.py` 약 155곳 + `backtest/CLAUDE.md` · `DEFERRED_FINDINGS.md` 약 12곳 + 보고서 L.5. 착수할 때 `grep -rnE 'D[0-9]+|보완_전략_설계|설계서'` 로 다시 센다.
  4. 설계서를 지우지 않고 남겨 둘 동안은 상태 줄만 맞춘다: :105 「커밋 전」 → `c4a4d24`, :137 삭제 목록 9개 → 10개(`PLAN_portfolio_lineup_cleanup` 누락), :131 없는 이름 `PLAN_supplement_conclusion` → `PLAN_supplement_registration`.

## 17. DEFERRED_FINDINGS.md (13건) — 재현 결과와 추천

> 결정은 로컬 세션에서 항목마다 한다. 추천을 모으면 **고침 6건(3 · 4 · 6 · 10 · 11 · 13), 버림 7건(1 · 2 · 5 · 7 · 8 · 9 · 12)** 이다.
> 여러 항목의 근거였던 「엔진은 고치지 않는다」(설계서 D27)는 보완 전략 실험 계획서에만 걸린 조건이었다. 그 실험이 끝났으므로 이제 엔진을 고치지 못할 이유는 아니다.

| # | 항목 | 현재 자리 | 재현 | 지금 발생 | 최소 수정 | 추천 |
|---|---|---|---|---|---|---|
| 1 | 검사기가 엔진이 «하지 않은 일»을 못 봄 | validation :59 · :109 · :230 · :344(그대로), 엔진 `_append_state_log_columns` :838(적힌 :886 틀림) | 성립 | 0 | 엔진이 0주 사유를 기록하거나 검사기가 판단을 재계산(수십 줄, 엔진 로직 사본) | 버림 |
| 2 | 장부 cash · cost · target_share 를 대조하지 않음 | 엔진 :765 · :767 · :769, validation :465 | 성립 | 0 | 규칙 하나 약 10줄(cost 는 재계산 불가) | 버림 |
| 3 | 같은 매매 파일을 다른 자산 id 로 들면 상계 누락 | `portfolio_data.py:172-178` | 성립 | 0(설정 306개) | 경로→id 역방향 검사 약 5줄 | **고침** |
| 4 | 낡은 ledger · netting 파일이 남음 | 러너 `_save_portfolio_results` :272 · 앱 `_load_ledger_csv` :214 | 성립, 범위가 더 넓음 | 0 | 저장 전 `shutil.rmtree` 1–2줄 | **고침** |
| 5 | 배분 비중을 float 로 정확히 비교 | `portfolio_methods.py:274` | 성립 | 0(연속 비중 규칙 없음) | `isclose` 1줄 | 버림 |
| 6 | 체결 전후 표가 매수일을 빠뜨리고 사유를 틀리게 붙임 | 러너 `_build_execution_comparison_df` :85(날짜 :112 · 사유 :132-139 · 미저장 :365), 앱 :371 | 성립, 악화 | **발생 중** | ①③ 3–4줄, ② 약 8줄(러너만, CSV 형식 그대로) | **고침** |
| 7 | EWY 규칙의 `hold_days_used` 가 0 | ewy :56, methods :217 | 성립 | 0(EWY 탈락) | 배분 규칙 인터페이스 변경 | 버림 |
| 8 | HAA 가 입력 시세의 거래일 정렬을 확인하지 않음 | `haa.py:35` · `:78` | 성립(합성 데이터) | 0(엔진이 공통 거래일로 잘라 넘김) | 3–4줄 | 버림 |
| 9 | 배분 규칙 생성자가 파라미터를 검증하지 않음 | ewy :32, rotation :30 | 성립 | 0(상수만 들어감) | 3줄(5-2 로 함께 해결 가능) | 버림 |
| 10 | 등록 실험의 실제 시작일을 `min_start_date` 와 대조하지 않음 | 러너 :653 | 성립(여유 0일) | 0 | 기존 `run_with_start_check` 재사용 2–3줄 | **고침** |
| 11 | 배분 조정 사유를 「리밸런싱 + 빈 사유」로 추론 | 러너 :139, 앱 :1228, 엔진 :632 | 성립 | ② **발생 중** | 6② 수정 + hover 약 6줄. 엔진 변경 불필요 | **고침**(6 과 묶음) |
| 12 | 신호 일치율이 판단 보류 달을 셈 | `supplement_experiment.py:605` · `:189`(적힌 :462 · :145) | 부분(적힌 계기는 이미 막힘) | 0 | 2–3줄 | 버림 |
| 13 | 교차 확인 쌍이 상장 전까지만 잘리는지 강제하지 않음 | `generate_proxy_comparison.py:92` · `110-112` · `149`, `proxy_comparison.py:170` | 성립 | 0 | 약 4줄 | **고침** |

**항목별 핵심**

- **1**: 1주 미만 매수 결함을 넣어도 5개 실험이 모두 「위반 0 · 거래 0 · 최종 자본 10,000,000」으로 통과한다. 매매법 사이 되돌리기를 안 하는 결함은 채택 조합에서 195일 중 191일을 잡는다.
  - 적힌 「1,619일 중 113일 · 62회 중 61회」는 지워진 25% 실험 기준이다.
  - 큰 결함은 엔진 시나리오 테스트가 먼저 잡는다. 검사기의 역할을 「한 일이 맞는가」로 두고 지적을 지운다.
- **2**: 엔진이 매매법 자본을 `book.cash` 로 계산하고 같은 값을 기록한다(`portfolio_engine.py:641-643` · `:765`). 그래서 대조는 자기 확인에 가깝다. 저장 CSV 로 재면 반올림 때문에 최대 316원 차이가 난다.
- **3**: 금 20% 그리드 설정에서 금 매매법 id 만 `gld` → `gold` 로 바꿨다.
  - 설정 검증과 정합성 검사를 모두 통과하는데, 상계 2행과 절감 488원이 사라진다(145,665,823 → 145,665,335).
  - 계좌 보유 목록에도 같은 종목이 두 줄로 나온다.
- **4**: 폴더를 재사용하면 `ledger.csv` · `netting.csv` 뿐 아니라 `execution_comparison.csv` 와 낡은 `signal_*.csv` 15개도 남는다. 대시보드는 `signal_*.csv` 를 모두 읽어(`_load_experiment_data` :231) 없는 자산의 차트까지 그린다.
- **6**
  - ① 매수 진입 체결일 중 표에 나오는 날: D-1 12일 중 0, Q-2 21일 중 0, Q-2-2XS 20일 중 0, 채택 조합 158일 중 138.
  - ② 채택 조합에서 HAA · 로테이션의 새 매수 · 매도 94행이 「월초 정기」로, 31행이 「매매법 사이 비중」으로 보인다.
  - ③ QQQ B&H 는 CSV 가 없고 재실행해도 생기지 않는다.
  - 수정
    - 체결일을 `equity_df` 의 `_shares` 변화일로 뽑는다(③ 도 해결).
    - 사유는 상태 로그 전날의 `{키}_pending_reason` 에서 가져온다.
    - `rebalance_reason` 열은 이미 행마다 있어 **CSV 형식을 바꿀 필요가 없다**(본문 · D32 의 전제가 틀림). 이 함수의 테스트는 0건이다.
  - 대안: 디버그 대시보드를 지운 흐름에 맞춰 이 표 섹션과 CSV 를 아예 지운다(러너 약 115줄 · 대시보드 약 55줄, 6 · 11 의 표 부분이 함께 사라짐).
- **10**: 채택 조합의 엔진 유효 시작일 = `min_start_date` = 첫날 2007-06-22 다. 러너 :661 에서 `run_with_start_check`(`supplement_experiment.py:659`)를 부른다.
- **11**: HAA 가 비중만 조정한 17일 중 4일(2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-04-01)이 「월초 정기」로 보인다.
  - `pending_reason = "allocation change"` 인 날 17일이 장부에서 빈 사유로 리밸런싱한 날 17일과 정확히 같고, `ledger.csv` 에 매매법별 사유가 있다. 따라서 **엔진 변경은 필요 없다**(본문 「근원 수정은 엔진 변경」은 틀림).
  - 추론 2줄(러너 :138-139)을 지우고, hover 는 `ledger_df` 의 사유를 쓴다(앱 :1219-1231). `scripts/CLAUDE.md:159` · 설계서 178행의 설명도 함께 고친다.
  - 6 을 버리거나 표 섹션을 지우면 hover 만 남으므로 이 항목도 버릴 수 있다.
- **13**: 넷째 칸을 `None` 으로 두거나 실물 첫날을 비교 끝보다 늦게 주면 6,312행 전 구간을 예외 없이 잰다. → `align_closes` 에서 `before > end` 면 ValueError(2줄) + `main` 에서 교차 확인 묶음의 넷째 칸 필수(2줄).

**DEFERRED_FINDINGS.md 파일 자체**

- 줄 번호를 빼고 파일 + 함수 이름만 적는다(13개 중 5개가 이미 어긋남).
- 날짜 붙은 실측 · 계획서 이름 · 결정 번호를 본문에서 뺀다(1 · 2 · 6 · 7 · 12 의 서술이 낡음). 실측은 처리할 때 다시 재므로 출처 한 줄로 충분하다.
- 항목을 「무엇이 틀리나 · 왜 지금은 안 일어나나 · 계기 · 종류」 3–5줄로 줄인다(지금 평균 약 10줄, 1번은 15줄). 뿌리가 같은 항목(6 ↔ 11, 1 ↔ 2)은 서로 가리킨다.
- 다른 곳의 중복을 정리한다: 설계서 :128 이 이 파일의 7건을 이름으로 다시 적고, `scripts/CLAUDE.md:159` 가 11번의 추론을 설명한다. → 「DEFERRED_FINDINGS.md 참조」 한 줄로.

## 18. 문서 중복·경량화 (요청 #2 · #3 기준)

### 18-A. 사실별 정본 제안

| 사실 | 정본 | 나머지 문서 |
|---|---|---|
| 실행 명령 · 옵션 · 선행 조건 · 출력 경로 · 소요 시간 | `docs/COMMANDS.md` | README · CLAUDE.md · scripts 문서 · 스크립트 docstring 은 링크만 |
| AI 실행 규칙 · 반올림의 현재 규칙 | 루트 `CLAUDE.md`(규칙만, 날짜 · 근거 없이) | 근거 · 이력은 `docs/research/` |
| 함수 · 필드 · 시그니처 · 모듈 책임 · 정합성 규칙 목록 | 코드 docstring | 도메인 CLAUDE.md 는 모듈당 한 줄 지도 |
| 도메인 불변조건(체결 타이밍 · 유지일 · SMA · 비용 · 리밸런싱) | `src/qbt/backtest/CLAUDE.md` 「도메인 규칙」 | tests · README · COMMANDS 에서 삭제 |
| 대시보드 동작 | 각 `app_*.py` docstring | `scripts/CLAUDE.md` 에 앱당 한 줄 |
| 계층 · 예외 · 병렬 · 상수 배치 규칙 | `src/qbt/CLAUDE.md`(병렬 · 상수), `scripts/CLAUDE.md`(예외 · CLI) | utils · tests 는 링크 |
| 프로젝트 소개 | `README.md` | 루트 CLAUDE.md 개요 · `src/qbt/CLAUDE.md` 「담당 도메인」 삭제 |
| 결과 · 데이터 경로 | `common_constants.py` | 문서에는 파일명 패턴만 |
| 현재 성과 수치 | `storage/results/**/summary.json` · 부록 L.1 | 연구 문서는 링크 |
| 미룬 지적 | `docs/DEFERRED_FINDINGS.md` | 설계서 목록 삭제 |

### 18-B. 안내 문서 중복 (같은 사실이 2곳 이상)

| # | 사실 | 위치 |
|---|---|---|
| B1 | 정합성 규칙 목록(이미 서로 다름 — README 에는 규칙 7 이 없음) | `README.md:50`, `COMMANDS.md:44`, `backtest/CLAUDE.md:143`, `portfolio_validation.py:1-14` |
| B2 | 보완 · 조합 그리드 설명 | `README:39-40`, `COMMANDS:50-63`, `src/qbt/CLAUDE.md:192-198`, `scripts/CLAUDE.md:161-169`, `backtest/CLAUDE.md:286-308`, 모듈 docstring |
| B3 | 대용 · 대체 시계열 설명, 「원본을 다시 받으면 다시 실행」 5회 | `COMMANDS:220-245` · `228` · `243`, `scripts/CLAUDE.md:131-136`, `utils/CLAUDE.md:70-89`, `src/qbt/CLAUDE.md:164-166` · `200-202`, `generate_proxy_series.py:9`, `generate_long_proxy_series.py:13` |
| B4 | 대시보드 동작(13-B D5 의 오류가 함께 복제됨), 보유중 마커 4곳 | `backtest/CLAUDE.md:556` · `579-633`, `scripts/CLAUDE.md:174-198`, `COMMANDS:81-94` |
| B5 | 반올림 규칙 3곳 + 근거 문장 2곳 | 루트 `CLAUDE.md:76-92`, `scripts/CLAUDE.md:131`, `tests/CLAUDE.md:197`, `src/qbt/CLAUDE.md:213`, `test_rounding_policy.py:1-11`, `generate_*.py` `_save_price_csv` docstring |
| B6 | FFR · 운용비율 날짜 형식 6곳 | `tqqq/CLAUDE.md:50` · `162` · `167`, `tests/CLAUDE.md:143` · `148` · `185-193` |
| B7 | 병렬 처리 규칙 4곳 | `src/qbt/CLAUDE.md:109-117` · `131-151`, `utils/CLAUDE.md:39-45` · `104-106`, `scripts/CLAUDE.md:106-109`, `parallel_executor.py` |
| B8 | 예외 · ERROR 로그 계층 4곳 | `src/qbt/CLAUDE.md:51-52` · `116-117`, `scripts/CLAUDE.md:68-80` · `218-227`, `utils/CLAUDE.md:31-37` · `98`, `cli_helpers.py` |
| B9 | utils 기능 · 메타데이터 설명 | `src/qbt/CLAUDE.md:103-107` · `217-222` ↔ `utils/CLAUDE.md:23-29` · `47-52` · `62-68` ↔ `scripts/CLAUDE.md:41-66` ↔ `meta_manager.py` |
| B10 | docstring 복제 | `backtest/CLAUDE.md:314-316`(= `strategy_registry.py`), `:434-444`(≈ `runners.py`), `:233-247`(≈ `portfolio_engine.py`), `:454-458`(≈ `csv_export.py`), `:421-430`(≈ `strategies/__init__.py`) |
| B11 | SMA 채택 근거 4항목 | `backtest/CLAUDE.md:493-506` ↔ `전략_검증_보고서.md` G.1 |
| B12 | 테스트 범위 목록 | `backtest/CLAUDE.md:640-651`, `tqqq/CLAUDE.md:248-254`, `tests/CLAUDE.md:50-77` |
| B13 | 「명령은 COMMANDS 가 단일 정본」 선언이 지켜지지 않음 | `backtest/CLAUDE.md:627-632`(npm 빌드), 모든 `scripts/*.py` docstring 의 실행 예시(이미 낡음 — 13-C C2) |
| B14 | 리밸런싱 정책 5곳 | `README:38`, `COMMANDS:42`, `backtest/CLAUDE.md:107` · `215` · `238` · `243`, `portfolio_engine.py` docstring |
| B15 | 개요 · 디렉토리 트리 · 이력 위치 규칙 | 개요(`README:3` · `23-31` ↔ 루트 `CLAUDE.md:14-22` ↔ `src/qbt/CLAUDE.md:9-20`), 트리(루트 · `src/qbt/CLAUDE.md:26-35` · `tests/CLAUDE.md:18-24`), 이력 규칙(루트 `CLAUDE.md:10` ↔ `docs/CLAUDE.md:12` · `18`) |
| B16 | QQQ 벤치마크 정책(1-2 로 사라질 수 있음) | `scripts/CLAUDE.md:160` ↔ `run_portfolio_backtest.py:631-635` |
| B17 | 전역 규칙을 다시 적은 것으로 보이는 곳(추정) | `DEFERRED_FINDINGS.md:5-9`, `src/qbt/CLAUDE.md:89-99`, `tests/CLAUDE.md:81-86` · `111-131` |

### 18-C. 연구 보고서 중복

| # | 사실 | 위치 → 정본 |
|---|---|---|
| R-B1 | EMA→SMA 상관 변화 표 | `상관` 1장(L46-69) = `전략` G.7.1(L2747-2764) → 상관 1장 |
| R-B2 | 지연진입 근거가 바뀐 경위 | `지연` 1장 · 7장 · 9장 + `전략` G.7.4(L2844-2867) → 지연 |
| R-B3 | Q-2-2XS 성과 세 벌(15.43/-27.56/0.560 · 15.40/-27.56/0.56 · 15.43/-27.93/0.55)과 해명 주석 | 설계서 L15-17 · L110 · L233, `전략` §53.1 L2565-2567 · J.8 L3463-3466 · L.1 L4045 · L.6 L4110 · L4123, `상관` 3장 L133-147 → summary.json + 부록 L.1 |
| R-B4 | 「[구 규칙]」 알림(양방향) | `상관` L131, `전략` §31.2 · §53.1 · J · K · L 머리말 · L.7 · L.8, 설계서 L15-17 → L.8 표 하나 |
| R-B5 | 세금 비교 | `전략` §46.3 · §46.4 · 부록 F, 설계서 5.9 → 부록 F |
| R-B6 | 전략 Part 1 내부 반복 | §2.3 = §19.1 = A.3, §2.4 = §19.1 + §19.2, §2.5 = §20.3 = §21.1 = C.3, §2.1 ≈ §8.2, §9 ≈ §3.1 → §19 · §20 |
| R-B7 | 전략 Part 2 「교정의 연대기」 4번 | §30.2 · §34 · §41.4 · E.5, §32.1 ⊃ §38.1 · §39.1 · D.1–D.7 → §32.1 에 「제거 사유」 열 |
| R-B8 | 엔진 규칙 · 리밸런싱 규칙 | 설계서 D15 · D29 · D33–D37 ↔ `backtest/CLAUDE.md` L236-243, `상관` 3장 · `전략` §31.2 · L.2 → 현재 규칙은 CLAUDE.md, 변경 근거는 L.2 |
| R-B9 | 용어 정의(CAGR/MDD/Calmar, 밴드 산식) | `전략` J.4 · K.4, 설계서 3장, `상관` L107-120, `지연` L141-146 → 전략 맨 앞 「용어 정의」 하나 |

### 18-D. 경량화 추정

| 문서 | 현재 | 줄일 수 있는 양 | 무엇을 빼나 |
|---|---|---|---|
| `src/qbt/backtest/CLAUDE.md` | 651 | 약 −500 | 모듈 카탈로그(13–474) → 약 40줄 지도(13-B D7 오류가 함께 사라짐), 대시보드 절 · 테스트 범위, SMA 근거 축약 |
| `scripts/CLAUDE.md` | 262 | 약 −160 | 일반론(15–120), COMMANDS · docstring 과 겹치는 스크립트 설명(123–212) |
| `src/qbt/tqqq/CLAUDE.md` | 254 | 약 −95 | 모듈 구성(14–110) · 앱 설명(226–241). 비용식 · 로그차이 정의는 유지 |
| `src/qbt/utils/CLAUDE.md` | 106 | 약 −60 | 모듈 목록 → 모듈당 한 줄 |
| `tests/CLAUDE.md` | 204 | 약 −45 | 픽스처 절(conftest 복제), numpy 경고 절(6-9), 마커 |
| `src/qbt/CLAUDE.md` | 222 | 약 −45 | 저장 위치 목록 → 패턴만, 지양 접두사 |
| `COMMANDS.md` · 루트 `CLAUDE.md` · 하위 문서 머리말 | — | 약 −50 | 설계 · 정합성 주석, 커버리지 절, 반올림 일화, 7개 문서의 「루트 참고」 머리말(루트는 자동 로드됨) |
| **안내 문서 합계** | **약 2,140** | **약 −950 (45%)** | |
| `전략_검증_보고서.md` | 4,142 | 약 −900 | §2 표, §11 · §12.1 · §20.5, 반복 절(R-B6 · R-B7), 「다음 단계」 5곳, 부록 B(L1554-1607) · K.5 중간 표(L3607-3921 중 150–200, 추정) · G.8 · H.9 · J.8 · K.8, 「[구 규칙]」 주석 |
| `Q2_2XS_보완_전략_설계.md` | 1,704 | 삭제(16-B), 남긴다면 −1,300 | 0장 · 15장, 9.5 · 9.6 · 8.4 의 CSV 사본(약 350), 6장의 구현 세부(한 행 최대 5,316자) |
| `Q2_2XS_QQQ_상관계수_연구.md` | 469 | 약 −120 | 12장 계산 코드(L392-461, 이미 재현 불가 → 커밋 고정 한 줄), 3장 성과 · 리밸런싱 표 |
| `QQQ_지연진입_연구.md` | 728 | 약 −70 (거래 종료 후 −60 더) | 이력 박스, 9장 스냅숏, 12장 낡은 소절, 8장. 특정 거래의 실행 메모(1장 행동 규칙 · 14.4–14.6)는 한 블록으로 분리 |

### 18-E. 구조

- `전략_검증_보고서.md` 는 부록(G–L, 약 1,515줄)이 Part 1 본문만큼 크고, 부록 M 이 더해질 예정이다.
  - 주제별 3–4 파일로 나누는 방안이 있다(효과는 추정): 파라미터 검증 / 포트폴리오 · 레버리지 선정 / Q-2-2XS 성과 구조(J · K + 상관 연구) / 보완 전략 결론.
  - 같은 「Q-2-2XS 성과 구조」인데 J · K 는 부록으로 합쳤고 상관 연구는 별도 파일이다. 한 방식으로 통일한다.
- 결과 경로 설명이 4곳에 흩어져 있다(src 저장 위치 · COMMANDS 출력 · scripts 결과 · tqqq CSV 형식). 정본은 `common_constants.py` 다.
- 포트폴리오 · 그리드가 요구하는 원본 티커를 알려 주는 곳이 없다(3-5).
- `tests/CLAUDE.md:30` 은 문서 중간에 H1(`# pytest 설정`)이 있다.

## 19. 처리 순서 제안 (로컬 세션용)

1. **표시 수치 바로잡기** — 1-1 · 1-2 · 1-3 · 1-4 · 2-5 · C1.
   - 결과를 재산출하고 연구 문서의 해당 수치를 갱신한다.
   - CAGR · MDD · Calmar 는 바뀌지 않는다. 바뀌는 것은 월별 · 연간 표 · 고원 · 마커다.
   - `download_data.py` 는 돌리지 않는다.
2. **TQQQ 합성 재생성** — 2-1. `generate_synthetic.py` 만 실행하고 TQQQ 단일 백테스트 · WFO 를 재산출한다. 7-3(`splice_proxy`)을 먼저 하면 생성 결과가 비트 동일하다는 것도 함께 확인된다.
3. **기계적 정리 한 커밋** — 10절(import 이동) · 11절(ignore · noqa 126줄 삭제, 설정 3줄). 동작 변화는 0이다.
4. **잠재 버그 · fail-fast** — 2-2 · 2-3 · 2-4 · 2-6 · 9-1 ~ 9-4 · 12-1 · 12-2. 작은 계획서 하나.
5. **영역별 단일 출처 · 데드코드 정리** — 3 · 4 · 5 · 6 · 7 · 8 · 12절. 포트폴리오 엔진 / tqqq / scripts · 대시보드로 나눠 계획서를 쓴다. 5-1 · 6-1 · 7-1 · 7-2 가 줄 수 감소 효과가 크다.
6. **DEFERRED 결정** — 17절. 6 · 11 은 5단계의 러너 정리와 묶는다.
7. **문서**
   1. 실오류(13-B D1–D6, 13-A R1–R3)를 먼저 고친다.
   2. 안내 문서를 경량화한다(18절).
   3. 설계서를 처리한다(16-B): 부록 M → 엔진 근거 이전 → 결정 번호 치환 → 설계서 · 계획서 10개 삭제.
   4. 마지막으로 이 보고서를 삭제한다.
