# Implementation Plan: 단일 · 워크포워드 · 고원 정리 — 쓰이지 않는 경로 삭제 · 판단 문구를 Dynamic 값으로 · 결과 이름과 반올림을 한 곳에

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-16 08:59
**마지막 업데이트**: 2026-10-17 16:19
**관련 범위**: backtest(`walkforward.py` · `walkforward_verdict.py` · `analysis.py` · `csv_export.py` · `runners.py` · `types.py` · `constants.py` · `parameter_stability.py` · `engines/backtest_engine.py` · `strategies/`), scripts(`run_single_backtest.py` · `run_walkforward.py` · `run_param_plateau_all.py` · `app_single_backtest.py` · `app_walkforward.py`), `docs/research/late_entry_rally_opportunities.py`, tests(워크포워드 · 분석 · CSV 저장 · 버퍼존 실행)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 11단계 「backtest」)

---

## 1) 목표(Goal)

- [x] 목표 1: 쓰이지 않는 경로를 지운다 — 워크포워드 Rolling 윈도우(6-1), 워크포워드 결과 CSV 로더(5-8), 구조상 닿지 않는 대기 주문 충돌 검사(6-3), 편의 함수의 일정 인자 · 러너의 쓰이지 않는 인자 · 칸(6-5), 아무도 읽지 않는 요약 · 그리드 칸(6-12), 패키지 재노출(6-6), 늘 참인 분기(6-7)
- [x] 목표 2: 조용히 기본값으로 넘기던 곳을 멈추게 한다 — 이어 붙인 요약이 없으면 0 으로 숨기던 경로(6-11 · 12-2), 판단 문구의 「데이터 없음」 안전 getter(12-3), 빈 에쿼티 → 지표 0(12-4), 러너의 `.get` · `isinstance` · `default=str`(12-8 · 12-11)
- [x] 목표 3: 워크포워드 판단 문구의 재현성 · 「양호」 판단을 Dynamic 값으로만 정한다 — 지금은 4P 를 포함한 두 모드 중 큰 값이다(1-10)
- [x] 목표 4: 같은 계산 · 이름을 한 곳에 — 최적 선택은 그리드의 Calmar 로 「거래수 필터 뒤 최댓값, 같으면 그리드 입력 순서」(1-8), Calmar 재계산 · MDD 두 벌 · 유효 행 필터 · 이동평균 사전 계산 루프 · 판단 문구 블록 · 시그널 CSV 반올림(7-6 · 5-6), 밴드 산식(7-5 · 8-2), 결과 파일 이름 · 워크포워드 모드 키(3-3), 고원 결과 경로(3-4), 이미 있는 상수(3-14 · 3-18), 한 파일 전용 상수의 자리(4-6), 러너의 한 줄 래퍼 · 같은 모양 블록(4-8 · 5-7 · 7-7 의 고원 러너)
- [x] 목표 5: 워크포워드 윈도우 시그널 CSV 가 4종 전일대비%를 저장하고 대시보드는 그것을 읽는다(1-7 · 4-1)
- [x] 목표 6: 결과 파일은 워크포워드 요약 JSON 2개(읽지 않는 칸 셋 삭제)와 윈도우 시그널 CSV 44개(전일대비% 4열 추가)만 바뀌고 나머지 성과 수치 · 파일은 바이트까지 같다

## 2) 비목표(Non-Goals)

- **포트폴리오 엔진 · 보완 실험** — 같은 11단계 backtest 줄의 나머지(3-9 · 4-7 · 4-9 · 6-2 · 7-8 · 7-13 · 8-1 · 12-6 과 3-3 · 3-18 · 4-6 · 4-8(`_CONFIG_MAP`) · 6-5 · 6-7 · 7-6 · 13-C · 14절 · 15절의 포트폴리오 자리)는 다음 계획서다. 항목이 많아 두 계획서로 나눈다
- **6-4(유지일 상태 단순화)** — 단순화하면 `check_buy` 의 `current_date` 가 쓰이지 않게 되는데, 그 인자는 포트폴리오 계획(`generate_signal_intents` · `_plan_book`)과 배분 규칙(`target_weights`)까지 이어진다(테스트 호출 약 60곳 중 대부분이 포트폴리오 쪽). 사슬째 포트폴리오 계획서로 옮긴다
- **대시보드 안의 다른 정리** — `app_walkforward.py` · `app_single_backtest.py` 는 결과 이름 상수(3-3) · 전일대비% 열(1-7 · 3-14)만 고친다. 6-7 · 3-14 의 대시보드 자리와 「파일이 없으면 None」 로더(12-9 · 9-9)는 11단계 대시보드(차트 공용 모듈 7-1 이 그 함수들을 다시 쓴다)
- **9-7(윈도우 상세 백테스트의 이동평균 빈 행 거르기)** — 넣지 않는다(버림). 아래 Context 의 실측대로 지금 빈 행이 0 이다
- **안내 문서 경량화(18-B · 18-D)와 13-B 의 D2(COMMANDS 의 WFO 대상 설명)** — 12단계. 이번에는 이 변경으로 거짓이 되는 문장만 고친다
- **결정 번호(D○○) 토큰** — 16-B 와 함께

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계의 넷째 줄(backtest)이다(셋째 스프레드 랩은 `2f0fa8c`). 줄의 항목을 단일 · 워크포워드 · 고원(이 계획서)과 포트폴리오(다음 계획서)로 나눈다
- 대상마다 지금 무엇이 문제인가 (2026-10-16 저장소 사본에서 다시 쟀다. 스크래치 `step11d/`)

| 항목 | 지금 | 재현 · 근거 |
|---|---|---|
| 6-1 Rolling WFO | `generate_wfo_windows(rolling_is_months=)` · `run_walkforward(rolling_is_months=)` · `_first_day_months_before` | 프로덕션 호출 0, 테스트 5개(`TestRollingWfoWindows`)뿐. 점검 보고서: 실제로 쓰면 IS 구간만으로 이동평균을 다시 계산해 틀린 결과를 낸다 |
| 5-8 WFO CSV 로더 | `load_wfo_results_from_csv` · `_WFO_CSV_*` | 프로덕션 호출 0, `test_wfo_stitched.py` 5개만 부른다. 그 파일의 일정 연결 단언은 `test_walkforward_schedule.py` 의 `TestBuildParamsSchedule` 이 이미 고정한다 |
| 6-11 · 12-2 | `calculate_wfo_mode_summary(stitched_summary=None)` 경로는 테스트 4곳만 쓴다. 키가 없으면 `.get(…, 0.0)` · `isinstance` 로 수익 집중도 · CAGR 이 0 으로 숨는다. 러너는 `if "stitched_cagr" in summary` | 이어 붙인 요약 · 윈도우 끝 에쿼티를 필수 인자로, `run_stitched_equity` 는 (에쿼티, 요약, 윈도우 끝 에쿼티)를 돌려준다 |
| 6-12 | 요약의 `oos_calmar_std` · `oos_win_rate_mean` · `stitched_total_return_pct`, 그리드 결과의 `total_return_pct` · `final_capital` | 읽는 코드 0 — 대시보드가 읽는 요약 키는 8개(이어 붙인 CAGR · MDD · Calmar, OOS CAGR 평균 · MDD 최악, WFE Robust, PC 최대, OOS 거래수)와 판단 문구가 읽는 것뿐이고 연구 문서도 0건. 그리드 결과는 저장하지 않는다 |
| 1-8 최적 선택 | Calmar 를 다시 계산하고 불안정 정렬한 뒤 첫 행 · 탈락 로그(조건 누락) | 그리드가 이미 Calmar 를 준다. 거래수 필터 뒤 그리드 Calmar 의 최댓값 첫 행(`argmax`)으로. `run_grid_search` 는 안정 정렬이라 동률이면 그리드 입력 순서다. 고친 뒤 워크포워드를 다시 돌려 선택이 44개 윈도우 모두 같다(아래 「결과 파일」) |
| 1-10 판단 문구 | WFE 재현성 꼬리 문장과 이어 붙인 Calmar 「양호」를 두 모드 중 큰 값으로 정한다 — 4P 는 OOS 를 포함한 전 기간을 보고 정한 값이다 | 지금 결과로는 결론이 같다(Dynamic 만으로도 WFE QQQ 3.82 · TQQQ 3.30 ≥ 1, 이어 붙인 Calmar QQQ 0.45 · TQQQ 0.33 < 1). 화면 문구 두 줄이 「Dynamic이 …」로 판단 근거를 밝히도록 바뀐다 |
| 12-3 안전 getter | `_get_mode` · `_get_number` · `_get_number_list` · 「데이터 없음」 분기 · `_describe_span` 의 try/except | 결과 JSON 은 러너가 한 번에 쓰고 대시보드는 요약이 있는 전략만 넘긴다 — 키가 빠지는 것은 저장 형식이 바뀐 때뿐이고, 그때 「데이터 없음」이 그것을 가린다. 직접 인덱싱(KeyError) |
| 12-4 | `calculate_summary` 가 빈 에쿼티면 지표 0 · 날짜 None 을 돌려준다 | 호출부 둘(단일 엔진은 2행 미만이면 실행 전에 멈춘다 · 포트폴리오 엔진도 2행 이상)에 빈 표가 올 수 없다. RuntimeError. 요약의 시작 · 끝 날짜는 필수 `str` 이 되고 러너의 `.get("start_date", "")` 가 사라진다 |
| 6-3 | `_check_pending_conflict` · `PendingOrderConflictError` | 루프가 체결일 아침에 pending 을 비운 뒤에 그날 신호를 보므로 도달하지 않는다(`backtest_engine.run_backtest` 4-1 → 4-3). 「Critical Invariant」 문서(D12)를 「루프 순서로 보장」으로 |
| 6-5 | `run_buffer_strategy(params_schedule=)`(호출 2곳 모두 넘기지 않음 · 테스트 3개만), 워크포워드 러너 `_save_results(strategy_name)`(안 씀), 고원 러너 행의 `param_name` · `period_start` · `period_end`(피벗이 읽지 않음) | 삭제. `TestParamsSchedule` 3개 삭제(프로덕션 경로인 `run_backtest` 의 일정은 `TestParamsScheduleWhile` 이 지킨다) |
| 7-5 · 8-2 밴드 | `runners.enrich_equity_with_bands` 가 행마다 `compute_bands` 를 apply 하고, 워크포워드가 그 함수를 `runners` 에서 가져온다 | `csv_export.add_buffer_zone_bands`(같은 산식, 벡터)를 부르게 하고 `csv_export` 로 옮긴다. 단일 · 윈도우 에쿼티 CSV 가 바이트까지 같다 |
| 7-6 · 5-6 | Calmar 재계산 5곳(그리드 워커 · 최적 선택 · IS · OOS · 이어 붙인 요약), MDD 두 벌(`calculate_summary` ↔ `calculate_drawdown_pct_series`), 유효 행 필터 손 구현 2곳, 이동평균 사전 계산 루프 3곳, 판단 문구의 CAGR 블록 2벌, 시그널 CSV 반올림 블록(단일 · 워크포워드 러너), 손으로 쓴 표본 표준편차 `_std` | 요약 · 그리드의 값 사용, `calculate_drawdown_pct_series`, `filter_valid_rows`, `analysis.add_moving_averages`(이미 있는 열은 다시 계산하지 않는다 — `prepare_common_period` 가 하던 규칙을 옮김), `_cagr_gap_lines`, `csv_export.round_signal_for_csv`, `statistics.stdev`(윈도우 하나면 0 — 지금과 같은 규칙). 포트폴리오 러너의 시그널 반올림은 다음 계획서가 같은 함수를 쓴다 |
| 1-7 · 4-1 | 워크포워드 윈도우 시그널 CSV 에 전일대비%가 없고, 대시보드가 4자리로 반올림된 종가로 `close_pct` 하나만 다시 계산한다. `COL_CHANGE_PCT` 는 만드는 코드가 없는 열이다 | 러너가 `add_ohlc_change_pct` 로 4종을 저장하고 대시보드가 그것을 읽는다. 앱의 재계산과 표시(소수 2자리)가 0.01 다른 행: 44개 파일 합 1,556행 |
| 3-3 | 결과 파일 이름(`signal.csv` 등)이 단일 러너 ↔ 대시보드에, 윈도우 상세 파일 이름(`w{idx:02d}_…`)이 워크포워드 러너 ↔ 대시보드에, 모드 키 `"dynamic"` · `"fully_fixed"` 가 러너 · 판단 문구(비공개) · 대시보드에 따로 있다 | `constants.py` 의 `SIGNAL_FILENAME` · `EQUITY_FILENAME` · `TRADES_FILENAME` · `SUMMARY_FILENAME` · `wfo_window_filename` · `WFO_MODE_*`. 포트폴리오 러너 · 대시보드와 「구성에 따라 생기는 파일 지우기」의 src 이동은 다음 계획서 |
| 3-4 | 고원 결과 폴더 · 파일 이름 규칙이 러너(`_RESULT_DIR` · f-string)와 `parameter_stability` 에 두 벌 | 러너가 `get_plateau_dir()` · `plateau_csv_path()` 를 쓴다 |
| 3-14 · 3-18 · C8 | `365.25`(판단 문구), 전일대비% 열 튜플(단일 대시보드), `"calmar"` 리터럴(최적 선택), 연구 스크립트의 `MA_COL = "ma_200"` · 「EMA200」 주석 · 결과 파일 이름 | `ANNUAL_DAYS` · `OHLC_CHANGE_PCT_COLUMNS` · `COL_CALMAR` · `ma_col_name(FIXED_4P_MA_WINDOW)` · 이름 상수. 연구 스크립트 출력은 수정 전과 같다(QQQ 139줄 · GLD 103줄) |
| 4-6 | 한 파일만 쓰는 상수가 `backtest/constants.py` 에: `CALMAR_MDD_ZERO_SUBSTITUTE`(analysis) · `MIN_BUY/SELL_BUFFER_ZONE_PCT` · `MIN_HOLD_DAYS`(buffer_zone) · `COL_HOLDING_DAYS`(csv_export) | 그 파일 상단으로. 포트폴리오 전용(`COL_SHARES` · `COL_HOLD_DAYS_USED`)은 다음 계획서. `TRADE_TYPE_REBALANCE` 는 3-8 결정대로 남긴다 |
| 4-8 · 5-7 · 7-7 | 고원 러너의 `_VALID_EXPERIMENTS`(= 실험 표의 키) · `_load_asset_data`(한 줄 래퍼) · 같은 모양 실험 블록 넷 · 같은 피벗 두 벌, 워크포워드 러너의 `STRATEGY_CONFIG` 사전 · `_load_data` | 실험 표 하나 · 루프 하나 · 피벗 함수 하나, 워크포워드는 `STRATEGY_NAMES` 튜플 + `get_config`. 7-7 은 19절이 대시보드에 배정했지만 고원 러너 부분은 이 러너를 고치는 이 계획서가 한다(앱 히트맵 부분은 대시보드에 남는다) |
| 6-6 | `backtest/__init__.py` 재노출 8개 · `strategies/__init__.py` `__all__` 5개 | 이름으로 쓰는 곳 0(`from qbt.backtest import runners` 같은 하위 모듈 import 만 있다) |
| 6-7 | 늘 참인 분기: 윈도우 상세의 `if win_signal.empty: continue` · 모드 요약의 `if n > 0` · 수익 집중도의 빈 목록 · 러너의 `if not eq_df.empty` · `if "win_rate" in summary` · 거래 표 반올림의 열 존재 검사, 미청산 기록의 `entry_date is not None`(같은 함수의 불변조건을 건너뜀 — RuntimeError 로), `runners` 의 쓰지 않는 로거 | 삭제 |
| 12-8 · 12-11 | 단일 러너의 `.get("start_date", "")` · `open_position` 의 `isinstance`, 워크포워드 러너의 `.get("strategy", "")` · 모드 루프의 `isinstance` · `json.dump(default=str)` | 직접 인덱싱. 미청산 포지션은 `SingleBacktestResult.summary` 를 `SummaryDict` 로 두어 타입으로 좁힌다. JSON 값은 모두 기본 타입이다(재실행에서 `default=str` 없이 저장됨) |
| 7-14 · 15절 · 13-C | `analysis.py` 의 「학습 포인트」 두 블록 · 코드를 옮겨 적은 주석, 「B&H 첫 매수 타이밍 fix」 · 「(이전: …)」 · 「이동하였다」 · 「기존 전략만」 · 「(V2)」 · 「기존 해석이 0.64%p … 관행」 · 「hold_days 결과도 이 디렉토리로 통합」, 「6자리」(C3), 없는 타입 · 문서 · 모듈 소개(C6 — 테스트 한 줄 포함) | 「왜」만 현재형으로 남긴다 |
| 9-7 | 윈도우 상세 백테스트에 이동평균 빈 행이 들어가는지 | 지금 결과 44개 윈도우 모두 0행 — IS 시작이 가장 긴 이동평균의 첫 유효일 이후다(10월 10일 1-11 처리). 거르는 장치를 넣지 않는다(버림) |

### 설계 결정

1. **최적 선택의 동률 규칙** — 그리드 결과의 Calmar 최댓값 중 첫 행이다. `run_grid_search` 의 Calmar 내림차순을 안정 정렬(`kind="stable"`)로 두어 「첫 행 = 그리드 입력 순서」가 참이 된다. 지금 결과의 동률 0건이라 선택은 바뀌지 않는다
2. **이어 붙인 요약은 필수** — `run_stitched_equity` 가 (에쿼티, `SummaryDict`, 윈도우 끝 에쿼티)를 돌려주고 `calculate_wfo_mode_summary(window_results, stitched_summary, window_end_equities)` 가 받는다. 이어 붙인 Calmar 는 요약의 값이다
3. **판단은 Dynamic 값으로** — 재현성 꼬리 문장 · 「양호」는 Dynamic 값으로 정하고 문장에 「Dynamic이 …」로 밝힌다. Fixed 값은 함께 보이되 판단에 쓰지 않는다
4. **판단 문구는 키가 빠지면 멈춘다** — 대시보드의 모드 요약 표(`.get` → N/A)는 대시보드 단계가 맡는다
5. **결과 파일 이름은 `backtest/constants.py`** — `ma_col_name` 처럼 이름 생성 함수(`wfo_window_filename(idx, SIGNAL_FILENAME)` → `w03_signal.csv`)도 그 자리에 둔다
6. **시그널 CSV 반올림은 `csv_export.round_signal_for_csv`** — 가격 · 이동평균(`ma_*`) · 밴드는 `ROUND_PRICE`, 전일대비%는 `ROUND_PERCENT`, 없는 열은 건너뛴다. 단일 러너 · 워크포워드 윈도우가 쓴다
7. **워크포워드 윈도우 시그널 CSV** — `Date · OHLC · 그 윈도우의 이동평균 · 4종 전일대비%`. 전일대비%는 윈도우 조각에서 계산해 첫 행이 빈다(대시보드가 하던 계산과 같은 범위)
8. **고원 러너** — 실험 표 `(실험 이름 = 결과 파일의 파라미터 이름, 바꾸는 설정 칸, 피벗 머리 접두사, 탐색 값)` 하나로 돈다. 이동평균 실험만 공통 기간(`prepare_common_period`), 나머지는 4P 이동평균
9. **테스트** — 지운 경로의 테스트는 지우고(18개), 바뀐 계약은 테스트로 고정한다: 동률이면 앞선 행 · Dynamic 값으로만 판단(2) · 키가 빠지면 KeyError · 빈 에쿼티 RuntimeError · 있는 이동평균 열은 그대로 · 에쿼티 밴드 날짜 결합 · 시그널 반올림 자릿수 · 이어 붙인 Calmar 는 요약의 값

### 사본 재현 (착수 전 확인, 2026-10-16)

저장소 밖 사본(스크래치 `step11d/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **레드 단계는 두지 않는다** — 성과 수치를 바꾸지 않는 정리이고, 동작이 바뀌는 곳(빈 에쿼티 · 판단 문구의 키 누락에서 멈춤, Dynamic 값 판단, 동률 규칙)은 새 테스트와 변형 확인으로 본다
- **919 passed**(지금 931 − 지운 18 + 더한 6), Ruff 통과, PyRight 0 errors, black 변경 0
- **변형 확인 10종 중 9종을 테스트가 잡는다** — 동률이면 뒤 행 · 거래수 필터 건너뜀 · 재현성에 Fixed 섞기 · 「양호」에 Fixed 섞기 · 이어 붙인 Calmar 재계산 · 있는 이동평균 열 재계산 · 에쿼티 밴드의 매수 · 매도 버퍼 바꿔 넣기 · 전일대비%를 가격 자릿수로 · 빈 에쿼티 검사 삭제. 잡지 못한 1종은 그리드 정렬을 불안정 정렬로 되돌리는 것이다 — 동률일 때만 결과가 갈리고 지금 결과의 동률은 0건이다(Risks)
- **결과 파일** — 러너 여섯(단일 · 고원 · 워크포워드, 그리고 `calculate_summary` 를 함께 쓰는 포트폴리오 · 보완 그리드 · 조합 그리드)을 수정 전 · 후 사본에서 돌렸다
  - 수정 전 사본의 재실행 결과 = 저장소 `storage/` (차이 0) — 다시 돌려도 결과가 그대로다
  - 수정 후 ↔ 수정 전: 다른 파일은 46개뿐 — `walkforward_summary.json` 2개(모드마다 칸 셋 삭제, 나머지 칸의 값 · 순서는 같다 — `statistics.stdev` 로 바꾼 `oos_cagr_std` 포함)와 윈도우 시그널 CSV 44개(기존 열의 값은 같고 4열이 더해졌다). 단일 결과 13개 × 4종, 고원 CSV 24개, 워크포워드 윈도우 결과 · 이어 붙인 에쿼티 · 윈도우 에쿼티 · 거래 CSV, 포트폴리오 · 두 그리드의 결과 53개는 바이트까지 같다
- **화면 대조** — 대시보드 셋을 서버 없이 `main()` 한 번 실행(8단계에 허락받은 방식)해 화면 요소와 차트 데이터를 기록했다. 셋 다 오류 0
  - 단일(219요소 · 캔들 13개) · 고원(28요소): 수정 전과 같다
  - 워크포워드(25요소): 다른 것 셋 — 판단 문구 두 줄(「Dynamic이 1 이상이라 …」 · 「… 입니다. Dynamic이 1.0에 못 미쳐 …」, 결론은 같다)과 윈도우 캔들 툴팁(전일대비% `close_pct` 1종 → 4종)
- **연구 스크립트** — `late_entry_rally_opportunities.py --asset qqq/gld` 출력이 수정 전과 같다
- **9-7 실측** — 저장된 워크포워드 결과 44개 윈도우의 `IS 시작 ~ OOS 끝` 구간에서 고른 이동평균의 빈 행 합계 0
- **변경 규모(포맷 적용 뒤)** — src +309 / −745, 스크립트 +183 / −376, 테스트 +230 / −688(파일 하나 삭제), 연구 스크립트 +19 / −12, 안내 문서 +21 / −35

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」(대시보드는 사용자가 띄운다 · 결과 파일은 덮어써진다) 절
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `rolling_is_months` · `load_wfo_results_from_csv` · `_check_pending_conflict` · `PendingOrderConflictError` · `COL_CHANGE_PCT` · `COL_TOTAL_RETURN_PCT` · `COL_FINAL_CAPITAL` · `oos_calmar_std` · `oos_win_rate_mean` · `stitched_total_return_pct` · `STRATEGY_CONFIG` · `_VALID_EXPERIMENTS` · `_get_mode` · `_get_number` · `_NO_DATA` · `default=str` 를 가리키는 코드가 src · scripts · tests · `docs/research` 에 0 이다
- [x] 결과 파일: 바뀐 것은 `walkforward_summary.json` 2개와 워크포워드 윈도우 시그널 CSV 44개뿐이고, 저장소에서 다시 만든 결과가 사본(`step11d/exp`)의 결과와 바이트까지 같다
- [x] 대시보드 셋을 서버 없이 실행해 오류 0건이고, 수정 전과 다른 화면 요소는 판단 문구 두 줄과 윈도우 캔들 툴팁뿐이다
- [x] 새로 넣거나 고친 검사마다 결함을 일부러 넣어 테스트가 실패하는 것을 봤다(변형 확인)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`, `src/qbt/backtest/CLAUDE.md`(상수 범주 · 분석 · 고원 · 워크포워드 · 엔진 · 전략 · 러너 · CSV 저장 함수 설명, 대기 주문 규칙 · 테스트 범위), `scripts/CLAUDE.md`(워크포워드 대상 목록의 자리 · 윈도우 시그널 CSV 내용), `tests/CLAUDE.md`(Pending Order 정책 줄). `docs/COMMANDS.md` 변경 없음(실행 명령 · CLI 옵션 그대로), `README.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 해당 없음: 새로 옮긴 것 0(고치지 않은 지적은 모두 거르는 기준에 걸리거나, 같은 자리 두 번인 손실 PC 가드를 사용자가 「받아들인다」로 정했다 — 진행 로그), 이 계획서가 고친 파일 항목 0(남은 1건은 11단계 tests 배정 그대로). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- src: `src/qbt/backtest/{__init__, analysis, constants, csv_export, parameter_stability, runners, types, walkforward, walkforward_verdict}.py`, `engines/backtest_engine.py`, `strategies/{__init__, buffer_zone, strategy_common}.py`
- scripts: `scripts/backtest/{run_single_backtest, run_walkforward, run_param_plateau_all, app_single_backtest, app_walkforward}.py`
- `docs/research/late_entry_rally_opportunities.py`
- tests: `tests/qbt/test_{analysis, buffer_zone, buffer_zone_execution_rules, buffer_zone_run, buy_and_hold, csv_export, walkforward_schedule, walkforward_selection, walkforward_summary, walkforward_verdict, walkforward_windows}.py`, `test_wfo_stitched.py` 삭제
- 위 DoD 문서 줄의 문서
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션(`--strategy` 선택지 · `--experiment` 선택지)은 그대로
- `README.md`: 변경 없음

### 데이터/결과 영향

- `storage/results/backtest/buffer_zone_{qqq,tqqq}/walkforward_summary.json` — 모드마다 `oos_calmar_std` · `oos_win_rate_mean` · `stitched_total_return_pct` 삭제(읽는 코드 0)
- `storage/results/backtest/buffer_zone_{qqq,tqqq}/wfo_windows_{dynamic,fully_fixed}/w*_signal.csv` 44개 — `open_pct` · `high_pct` · `low_pct` · `close_pct` 열 추가
- 그 밖의 결과 파일 · 성과 수치는 그대로다(Context 「결과 파일」)
- 워크포워드 대시보드는 새 열을 읽으므로 위 CSV 를 다시 만든 뒤에 뜬다(Phase 2)

## 6) 단계별 계획(Phases)

### Phase 1 — 사본에서 검증한 코드 · 테스트 · 안내 문서 반영(그린)

**작업 내용**:

- [x] 저장소의 src · scripts · tests · `docs/research` · 안내 문서 셋이 사본의 수정 전 기준(`step11d/base`)과 같은지 확인한다(`diff -rq`)
- [x] 설계 결정 1 – 9 — 사본(`step11d/exp`)에서 검증한 파일 33개(코드 · 테스트 30 · 안내 문서 3)를 그대로 넣고 `test_wfo_stitched.py` 를 지운다

**Validation**:

- [x] 사라질 이름을 가리키는 코드가 0건(DoD 첫 줄의 `grep`)
- [x] 이번에 고친 테스트 파일 11개 — 전부 통과(185 passed)

---

### Phase 2 — 결과 파일 다시 만들기

**작업 내용**:

- [x] 작업 트리의 `storage/` 변경이 0 인지 확인한 뒤 저장소에서 러너 셋을 돈다 — `run_single_backtest.py` · `run_param_plateau_all.py` · `run_walkforward.py`(약 4분, `docs/COMMANDS.md` 의 명령)

**Validation**:

- [x] `git status` 의 `storage/` 변경이 46개(요약 JSON 2 · 윈도우 시그널 CSV 44)이고, 저장소 `storage/` 가 사본(`step11d/exp/storage`)과 같다(`diff -rq` 차이 0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 저장소의 src · scripts · tests 가 사본에서 검증한 코드와 같은지 `diff -rq` 로 확인한다 — 같으면 사본의 재현(결과 대조 · 화면 대조 · 변형 10종)이 최종 코드의 결과다
- [x] 문서 — `docs/AUDIT_REPORT.md`(처리 표시 · 재배정 · 19절)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 14건 — 버그 9 [무거움 5 · 가벼움 4] · 그 외 5 · 조치: 무거움 1 수정(손실 자본곡선의 자리표시 PC 를 「양호」로 읽음) · 그 외 1 수정(이 계획서가 새로 어긴 「연결 누락」 — `COL_HOLDING_DAYS` 이동 되돌림) · 나머지 버그 8 미조치(닿지 않음 · 막는 쪽, 진행 로그) · 그 외 4 미반영)
- [x] `/code-review xhigh` **2회차** (발견 12건 — 버그 6 [무거움 2 · 가벼움 4] · 그 외 6 · 1회차와 같은 결함 4 · 새것 8 · 조치: 그 외 3 수정(이 계획서가 새로 어긴 규칙 — JSON 키 상수의 `KEY_` 접두사 · 타입이 정해진 값의 `float(str())` · 문서의 「넘는」) · 같은 자리 두 번 1(1회차의 손실 PC 가드 — 사용자에게 올림) · 나머지 버그 5 미조치(닿지 않음 · 막는 쪽, 진행 로그) · 그 외 3 미반영)
- [x] 수정분 검증 (2회차 반영분 수정 3건 · 파일 6(+ 점검 보고서 1) · hunk 17 · 발견 4건 — 무거움 0 · 가벼움 1 · 그 외 3 · 조치: 절차대로 고치지 않음, 진행 로그)
- [x] `poetry run python validate_project.py` (passed=920, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 단일 · 워크포워드 · 고원 정리와 워크포워드 판단의 4P 값 제외
2. 백테스트 / 쓰이지 않던 Rolling 윈도우 · WFO 결과 CSV 로더 · 대기 주문 충돌 검사 · 요약 칸 셋 삭제와 빈 자본곡선 · 이어 붙인 요약 누락의 0 대체 제거
3. 백테스트 / OOS 까지 보고 정한 4P 값을 재현성 · 양호 판단에서 빼고, 결과 키가 빠지면 「데이터 없음」 대신 멈추는 워크포워드 판단 문구
4. 백테스트 / 점검 보고서 11단계 backtest 첫 묶음(단일 · 워크포워드 · 고원) 처리 — 6-1 · 5-8 · 6-3 · 6-11 · 6-12 · 1-8 · 1-10 · 1-7 · 12-3 · 12-4
5. 백테스트 / 최적 선택의 그리드 Calmar 재사용, Calmar · MDD · 밴드 · 이동평균 · 시그널 반올림 · 결과 파일명 · 모드 키 일원화와 워크포워드 윈도우 시그널 CSV 의 전일대비% 4종 저장

## 7) 리스크(Risks)

- **워크포워드 대시보드 화면이 바뀐다** — 판단 문구 두 줄의 표현과 윈도우 캔들 툴팁(전일대비% 4종). 결론 · 수치 · 차트는 그대로다(Context 「화면 대조」). 서버를 띄운 확인은 사용자가 한다(루트 `CLAUDE.md` 「스크립트 실행 규칙」) — 볼 곳: 「모드별 요약 비교」 · 「Stitched Equity 곡선」의 판단 문구, 「윈도우별 상세 차트」 캔들의 툴팁
- **옛 결과 파일로는 워크포워드 대시보드가 멈춘다** — 판단 문구는 요약의 키가 없으면 KeyError, 윈도우 캔들은 전일대비% 열이 없으면 KeyError. Phase 2 가 같은 작업 안에서 결과를 다시 만든다
- **동률 규칙은 테스트가 지키지 않는다** — 그리드 정렬을 불안정 정렬로 되돌려도 테스트가 통과한다(변형 확인). 동률이 있을 때만 선택이 갈리고 지금 결과의 동률은 0건이다. 선택 함수 쪽 규칙(앞선 행)은 테스트가 지킨다
- **결과를 바꾸지 않는 변경이 대부분이라 재실행만으로는 회귀가 드러나지 않는다** — 완화: 결과 파일 바이트 대조 · 화면 대조 · 변형 확인
- **`run_walkforward.py` 가 약 4분 걸린다** — Bash 기본 제한(2분)을 넘으므로 제한을 늘려 돈다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 1-7 · 1-8 · 1-10 · 3-3 · 3-4 · 3-14 · 3-18 · 4-1 · 4-6 · 4-8 · 5-6 · 5-7 · 5-8 · 6-1 · 6-3 · 6-5 · 6-6 · 6-7 · 6-11 · 6-12 · 7-5 · 7-6 · 7-7 · 7-14 · 8-2 · 9-7 · 12-2 · 12-3 · 12-4 · 12-8 · 12-11 · 13-C C3 · C6 · C8 · 13-B D12 · 15절, 19절 11단계
- 점검 보고서의 줄 번호는 기준 커밋(`40011ad`) 값이다. 그 뒤 워크포워드 · 엔진이 바뀌어 대부분 어긋나므로 이 계획서는 함수 이름으로 가리킨다. 12-8 · 6-7 의 러너 자리는 기준 커밋에서 대조했다
- 이 계획서가 일부만 처리하는 항목: 3-3 · 3-14 · 3-18 · 4-6 · 4-8 · 6-5 · 6-7 · 7-6(단일 · 워크포워드 · 고원 · 연구 스크립트 자리), 7-7(고원 러너만), 13-C C6(포트폴리오 밖 자리), 15절(backtest 단일 · 워크포워드 자리)
- 재배정: 6-4 → 다음 계획서(포트폴리오), 6-7 · 3-14 의 대시보드 자리 → 11단계 대시보드, 7-7 의 고원 러너 → 이 계획서
- 11단계 다음 계획서: 포트폴리오 엔진 · 보완 실험 → 대시보드 → tests

### 진행 로그 (KST)

- 2026-10-16 08:21: 이전 세션 셋의 로그 · 점검 보고서 · 미룬 지적 파일 · 직전 계획서를 읽고, 11단계 넷째 줄(backtest)을 이어받았다. 대상 코드 · 테스트 · 대시보드 연결부와 호출처를 읽었다
- 2026-10-16 08:26: 사본(`step11d/base`) 기준 931 passed, 저장소 변경 0
- 2026-10-16 08:58: 사본(`step11d/exp`)에 변경을 얹었다 — 919 passed, Ruff · PyRight · black 통과, 러너 셋 결과 대조(수정 전 사본 = 저장소, 수정 후는 46개 파일만 다름), 대시보드 셋 화면 대조, 변형 10종(9종 잡음), 연구 스크립트 출력 대조, 9-7 실측. 사본에 쓰는 명령에서 계획서 게이트 확인창이 한 번 떴다 — 쓰기는 모두 스크래치 안이었다
- 2026-10-16 08:59: 계획서 작성(Draft)
- 2026-10-16 09:08: 계획서 자체 검증 — 배정 항목 대조로 비목표의 포트폴리오 목록에 4-8(`_CONFIG_MAP`)을 더했고, `calculate_summary` 를 포트폴리오 엔진도 쓰므로 포트폴리오 러너 · 두 그리드도 수정 전 · 후 사본에서 돌려 결과 53개가 같음을 확인했다. 판단 문구의 「약 N% 재현」 문장이 black 으로 암묵적 이어 붙이기가 되어 한 문자열로 합쳤다(지금 결과로는 타지 않는 분기 · 판단 문구 테스트 29 passed)
- 2026-10-17 15:13: 승인 — 사용자 「승인」 · 9-7 「버린다」. 저장소의 src · scripts · tests · `docs/research` · `storage` · `pyrightconfig.json` · `pyproject.toml` 이 사본의 수정 전 기준과 같음을 확인했다(추적 파일 차이 0 — 저장소에만 있는 `src/live` · `tests/live` 는 `__pycache__` 만 남은 git 무시 폴더)
- 2026-10-17 15:15: Phase 1 — 사본에서 검증한 파일 33개를 넣고 `test_wfo_stitched.py` 를 지웠다(저장소 = `step11d/exp`, `diff -rq` 차이 0). 사라질 이름 0건, 고친 테스트 파일 11개 185 passed. 처음 복사는 zsh 가 따옴표 없는 변수를 줄로 나누지 않아 한 건도 안 됐고(오류 「File name too long」), 줄 단위로 다시 넣었다
- 2026-10-17 15:17: 문서 — `docs/AUDIT_REPORT.md` 46줄(항목 행 39 · 6-T 7행 · 15절 · 19절의 backtest · 대시보드 줄). 6-7 이 짚은 `engine_common.py` 의 쓰지 않는 로거는 이 계획서 범위(Scope)에 넣지 않았고 두 엔진 공용 모듈이라 포트폴리오 묶음 몫으로 적었다
- 2026-10-17 15:19: Phase 2 — `storage/` 변경 0 을 확인하고 저장소에서 러너 셋을 돌렸다(단일 5초 · 고원 47초 · 워크포워드 162초, 모두 rc=0). `storage/` 변경 46개(요약 JSON 2 · 윈도우 시그널 CSV 44), 저장소 `storage/` = 사본 `step11d/exp/storage`(`diff -rq` 차이 0)
- 2026-10-17 15:20: 진행 로그 정정 — 작성(08:59) · 자체 검증(09:08) · Phase 1(15:15) · 문서(15:17) · Phase 2(15:19) 시각을 처음에 `date` 확인 없이 적었다. 사본 파일 시각(첫 러너 끝 08:55 · 판단 문구 수정 09:02 · 포트폴리오 러너 끝 09:07)과 `date` 결과로 바로잡았다
- 2026-10-17 15:29: `/code-review xhigh` 1회차(첫 실행은 세션 한도로 끊겨 다시 돌렸다 — 그사이 저장소 = 리뷰 전 사본 `step11d/r1_before` 확인) — 발견 14건. 버그 9 [무거움 5 · 가벼움 4] · 그 외 5
  - 고친 버그 1(무거움 · 닿는다): ① 이어 붙인 자본곡선이 손실이면 `_calculate_profit_concentration` 이 자리표시 (0, W0)을 돌려주는데 판단 문구가 「PC 최대 0.00 (최대 기여 윈도우 W0) — … 고르게 분산되어 있어 양호」로 읽는다 — 지금 두 전략은 이익(이어 붙인 CAGR QQQ 10.68 · TQQQ 21.79)이라 화면에 없지만, 워크포워드 대상 튜플(`STRATEGY_NAMES`, 사용자가 정하는 상수)에 손실 전략을 더하면 나온다. 이어 붙인 CAGR 이 0 이하면 「수익 집중도를 재지 않습니다」로(조건은 그 함수의 「순이익 0 이하」와 같다). 같은 모양(잴 수 없어 0 으로 둔 자리표시를 판단 문구가 측정값으로 읽는다)을 diff 전체에서 찾아 둘 — 이것과 ③. 변형: 가드를 지우면 새 테스트 `test_losing_stitched_equity_is_not_judged` 가 실패(1 failed, 29 passed), 되돌린 뒤 통과 · 사본 대조로 변형 없음 확인
  - 고친 그 외 1: ⑬ 한 파일 전용으로 보고 `csv_export.py` 로 옮긴 `COL_HOLDING_DAYS` 는 단일 대시보드가 같은 열을 `"holding_days"` 리터럴로 쓴다 — 전역 `python.md` 「미사용 판정」의 연결 누락을 이 계획서가 새로 어긴 것이라 `backtest/constants.py` 로 되돌렸다(앱이 상수를 쓰게 하는 것은 11단계 대시보드 — 점검 보고서 4-6 행 · 19절에 적었다). Context 표의 4-6 행 중 이 상수는 이 줄이 정정이다
  - 고치지 않은 버그 8: ② 두 모드의 MDD 가 같으면 「Fixed 쪽 낙폭이 더 얕다」 — 기준 1(닿지 않음): 같아지려면 Dynamic 이 모든 윈도우에서 4P 를 골라야 하는데 지금 0/22 윈도우다(드문 계기) ③ 모든 IS Calmar 가 0 이하라 `wfe_calmar_robust` 가 자리표시 0 이면 「재현되지 않았다 · 과최적화 의심」 — ①과 같은 모양이지만 가볍고 안전한 쪽(더 의심하게 한다)이며 기준 1(지금 IS Calmar 0 이하 윈도우 QQQ 0/11 · TQQQ 3/11, 전부여야 생긴다). 판단 문구는 요약만 받아 고치려면 요약 형식(잴 수 없음 표시)을 바꿔야 한다 ④(무거운 모양) 이어 붙인 자본곡선 · 윈도우 상세가 이미 있는 이동평균 열을 다시 계산하지 않아, 구간을 잘라 계산한 열을 붙여 넘기면 그 값으로 계산한다 — 기준 1: 유일한 호출부(러너)는 원본 시세를 넘긴다 ⑤(무거운 모양) 행이 없는 윈도우 표면 「붕괴 패턴 없음」 — 기준 1: 윈도우가 0 개면 `generate_wfo_windows` 가 멈추고 러너는 빈 표를 쓰지 않는다 ⑥(무거운 모양) 빈 파라미터 목록이면 「모든 파라미터가 달라진다」 — 기준 1(같은 이유) ⑦(무거운 모양) `window_results` 와 `window_end_equities` 의 길이를 대조하지 않는다 — 기준 1: 유일한 호출부가 같은 윈도우 목록으로 둘을 만든다 ⑧ 전략 이름 확인이 루프 안이라 앞 전략을 저장한 뒤 멈춘다 — 기준 2(멈추는 쪽, 앞 전략은 같은 코드의 올바른 재산출) ⑨ 옛 결과 파일이면 대시보드가 안내 없는 KeyError — 기준 2(멈추는 쪽, Phase 2 로 옛 파일이 없다 · Risks)
  - 반영하지 않은 그 외 4: ⑩ 그리드의 안정 정렬을 지키는 테스트가 없다(Risks — 동률이면 둘 다 같은 Calmar 라 틀린 값이 아니다) ⑪ 최적 행을 파라미터 마스크로 다시 찾는다 ⑫ 에쿼티 CSV 반올림이 단일 · 워크포워드 러너에 두 벌 ⑭ 단일 러너 요약의 `round(float(str(...)))` 가 타입이 분명해진 뒤에도 남았다(이 계획서 전부터 있던 줄)
- 2026-10-17 15:43: 1회차 반영 뒤 ruff · black 통과, 관련 테스트 101 passed. 2회차 전 사본은 스크래치 `step11d/r2_before/`
- 2026-10-17 15:48: `/code-review xhigh` 2회차(상한) — 발견 12건. 버그 6 [무거움 2 · 가벼움 4] · 그 외 6. 1회차와 같은 결함 4(이동평균 열 재사용 · 같은 MDD · 자리표시 0 · `float(str())`), 새것 8
  - 같은 자리 두 번(고치지 않고 사용자에게 올림): ㉠(가벼움) 1회차에 넣은 손실 PC 가드가 반올림된 JSON 의 `stitched_cagr <= 0` 으로 판정해, PC 를 만드는 쪽의 조건(순이익 ≤ EPSILON)과 어긋난다 — 이어 붙인 CAGR 이 0 과 0.005% 사이면 잰 PC 를 숨기고, 정확히 0 이면 손익 0 을 「손실」이라 적는다 ㉡(그 외) 그 가드의 경계(CAGR 정확히 0) 테스트가 없다 ㉢(그 외 · 근원 제안) 잴 수 없는 지표(PC · WFE Robust)를 0 자리표시 대신 None 으로 저장하면 읽는 쪽마다 다시 가를 필요가 없다(1회차 ③ 도 함께 풀린다)
  - 고친 그 외 3(이 계획서가 새로 어긴 규칙): ① 새 모드 키 상수가 JSON 키인데 전역 `python.md` 「네이밍」의 `KEY_` 접두사가 없었다 → `KEY_WFO_DYNAMIC` · `KEY_WFO_FULLY_FIXED`(값 그대로, 파일 5 · 옛 이름 0건 — 계획서 본문의 `WFO_MODE_*` 는 이 줄이 정정) ② 단일 러너 요약이 `SummaryDict` 로 타입이 정해진 뒤에도 7칸을 `round(float(str(...)))` 로 감쌌다(같은 함수의 미청산 포지션은 이 계획서가 이미 바꿨다 — 「타입이 불명확할 때만 안전 변환」) → `round(...)` ③ `backtest/CLAUDE.md` 의 「min_trades 를 넘는」 → 「이상인」(코드는 `>=`)
  - 고치지 않은 버그 5: (무거운 모양) 이어 붙인 자본곡선 · 윈도우 상세의 이동평균 열 재사용 — 1회차 ④ 와 같다, 기준 1 · 같은 MDD — 1회차 ② 의 근거 「모든 윈도우에서 4P」는 지나치게 강했다(최대 낙폭이 난 윈도우 하나에서만 같으면 된다). 고쳐 말해도 Dynamic 이 그 윈도우에서 4P 를 골라야 하고 지금 4P 를 고른 윈도우가 0/22 라 드문 계기다, 기준 1 · OOS 유효 행 필터가 날짜 대신 위치로 걸러 시그널 · 매매 날짜가 다르면 인덱싱 오류 — 기준 1 · 2(`load_signal_trade_pair` 가 날짜를 맞추고, 어긋나면 멈춘다) · 연구 스크립트의 이동평균 열을 4P 로 고정해 설정이 다른 기간을 쓰면 KeyError — 기준 2(멈춘다, 수정 전 `"ma_200"` 리터럴과 같은 동작) · (무거운 모양) `add_moving_averages` 가 더할 열이 없으면 입력 객체를 그대로 돌려준다(뒤에 열을 대입하는 호출자가 있으면 원본이 바뀐다) — 기준 1(지금 호출자는 자르기 · 조회만 한다)
  - 반영하지 않은 그 외 3: 위 ㉡ · ㉢(사용자 결정), 워크포워드 대시보드의 전일대비% 툴팁 루프가 단일 대시보드와 두 벌(11단계 대시보드의 차트 공용 모듈 7-1)
- 2026-10-17 16:00: 2회차 반영(그 외 3) 뒤 ruff · black · PyRight(0 errors) 통과. 반영분(6파일 · hunk 17)의 수정분 검증을 서브에이전트에 맡겼고, 단일 · 워크포워드 러너를 저장소에서 다시 돌려 결과가 바뀌지 않는지 보는 중
- 2026-10-17 16:04: 최종 확인 — 2회차 반영 뒤 저장소에서 단일 · 워크포워드 러너를 다시 돌려 `storage/` 가 사본(`step11d/exp/storage`)과 같다(바뀐 파일은 여전히 46개). 품질 검증 `validate_project.py` — Ruff · PyRight 통과, passed=920 · failed=0 · skipped=0(사본 919 + 1회차 PC 가드 테스트 1). 대시보드 셋을 저장소에서 서버 없이 실행해 화면 요소가 사본(`exp`) 기록과 같다(앱 오류 0). 사본과 달라진 코드는 리뷰 반영분뿐이다(1회차 PC 가드 · `COL_HOLDING_DAYS` 되돌림, 2회차 그 외 3) — 결과 · 화면 대조로 사본의 재현이 최종 코드에도 성립한다
- 2026-10-17 16:04: 근거 승격 — 남길 「왜」는 코드와 살아있는 문서에 있다: 최적 선택의 동률 규칙(`walkforward.select_best_calmar_params` docstring · `run_grid_search` 정렬 주석), 판단을 Dynamic 값으로만 하는 이유(`walkforward_verdict._describe_wfe` docstring · 이어 붙인 Calmar 판단 주석), 손실 자본곡선의 PC 를 서술하지 않는 이유(`_describe_profit_concentration` docstring), 있는 이동평균 열을 다시 계산하지 않는 이유(`analysis.add_moving_averages`), 윈도우 하나의 표준편차 규칙(`calculate_wfo_mode_summary` 주석), 대기 주문이 구조로 보장되는 이유(`backtest/CLAUDE.md` 도메인 규칙 5 · `run_backtest` docstring), 판단 문구가 키 누락에서 멈추는 이유(`walkforward_verdict` 모듈 docstring). 처리 사실과 재현 수치(1,556행 · 46개 파일 · 0/22 윈도우 · 9-7 의 빈 행 0)는 점검 보고서 해당 행
- 2026-10-17 16:10: 수정분 검증 결과(2회차 반영분 — 서브에이전트가 hunk 17개를 셋으로 묶어 답했다) — 무거움 0 · 가벼움 1 · 그 외 3. hunk 마다 세 물음(맞던 것의 변화 · 같은 모양 · 위험한 쪽으로의 변화)에 답이 있다. 근거: 러너 재실행 결과와 `r2_before` 대조 — `summary.json` 13개 · 워크포워드 결과 차이 0, 실행 로그(시각 제외) 단일 624줄 · 워크포워드 832줄 차이 0. 단일 요약 7칸은 13개 전략 모두 `builtins.float` 이고 옛식 · 새식 `json.dumps` 차이 0
  - 가벼움 1(절차대로 고치지 않음): 요약 저장에서 `float()` 까지 걷어(`round(x)`), 앞으로 `calculate_summary` 가 numpy 스칼라를 돌려주게 바뀌면 numpy 반올림을 타 소수 둘째 자리 경계에서 값이 에러 없이 달라질 수 있다(np.float64 는 float 의 하위 타입이라 PyRight 가 못 잡는다). 지금 경로에는 없다 — 거르는 기준 1(닿지 않음: 계기가 앞으로의 코드 변경뿐이고, 그 변경은 `calculate_summary` 의 `float()` 를 지워야 생긴다). 같은 모양: `run_param_plateau_all.py` 의 `_build_row`
  - 그 외 3: 계획서 본문의 옛 이름 `WFO_MODE_*`(16:00 줄이 정정) · 모드 키 상수가 JSON 키 말고 로그 라벨(`_run_single_mode` 의 `mode_name`)로도 넘어간다(출력 같음) · `docs/AUDIT_REPORT.md:135` 의 이름 변경이 검증용 diff 에 빠졌다(같은 방향으로 바뀐 것을 서브에이전트가 직접 확인)
- 2026-10-17 16:12: 사용자 결정 — 같은 자리 두 번인 손실 PC 가드(2회차 ㉠ ㉡ ㉢) 「받아들인다」. 받아들인 이유: 경계는 이어 붙인 CAGR 이 0 과 0.005% 사이이거나 정확히 0 일 때만 생기고(약 20년 OOS 동안 순이익이 사실상 0 — 지금 QQQ 10.68% · TQQQ 21.79%), 그때도 판단을 멈추는 쪽으로만 틀린다. 근원 제안(잴 수 없는 지표를 None 으로)은 하지 않는다
- 2026-10-17 16:12: 마무리 — 미룬 지적: 새로 옮긴 것 0. 거른 지적과 기준 — 1회차 ② ③ ④ ⑤ ⑥ ⑦ · 2회차의 이동평균 열 재사용 · 같은 MDD · `add_moving_averages` 반환 객체 · 수정분 검증 가벼움 1 은 기준 1, 1회차 ⑧ ⑨ · 2회차 연구 스크립트 이동평균 열은 기준 2, 2회차 위치 필터는 기준 1 · 2, 1회차 ⑩ ⑪ ⑫ ⑭ · 2회차 툴팁 두 벌 · 수정분 검증 그 외 3 은 기준 3, 2회차 ㉠ ㉡ ㉢ 은 사용자가 받아들임. 미룬 지적 파일의 남은 1건(표시용 열의 테스트 공백)은 이 계획서의 대상이 아니다(11단계 tests). 이 계획서를 지워도 잃는 것이 없다 — 근거 승격(16:04 줄)과 처리 사실 · 재현 수치(점검 보고서)

---
