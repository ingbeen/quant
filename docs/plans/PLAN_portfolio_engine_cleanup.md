# Implementation Plan: 포트폴리오 엔진 · 보완 실험 정리 — 유지일 상태와 날짜 인자 단순화 · 읽지 않는 칸 삭제 · Q-2-2XS 슬롯과 결과 파일 이름을 한 곳에

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-18 09:17
**마지막 업데이트**: 2026-10-19 13:47
**관련 범위**: backtest(`engines/portfolio_*.py` · `engines/engine_common.py` · `engines/backtest_engine.py` · `engines/__init__.py` · `portfolio_types.py` · `portfolio_validation.py` · `portfolio_configs.py` · `supplement_experiment.py` · `combo_experiment.py` · `allocator_registry.py` · `allocators/` · `strategy_registry.py` · `strategies/` · `constants.py` · `csv_export.py` · `types.py`), scripts(`run_portfolio_backtest.py` · `run_supplement_grid.py` · `run_combo_grid.py` · `app_portfolio_backtest.py`), tests(포트폴리오 · 배분 규칙 · 보완 실험 · 전략 인터페이스 · CSV 저장)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 11단계 「backtest」)

---

## 1) 목표(Goal)

- [x] 목표 1: 버퍼존 유지일 상태를 「지난 날 수」 하나로 줄이고(6-4), 그 뒤 쓰이지 않게 되는 날짜 인자를 사슬째 지운다 — 전략 `check_buy`, 신호 의도 생성, 매매법 계획, 배분 규칙 `target_weights`
- [x] 목표 2: 읽는 코드가 없는 칸 · 상수 · 분기를 지운다 — 배분 규칙 자산의 신호 경로(6-5, 사용자 결정), 주문 의도의 칸 넷(6-5, 사용자 결정), 장부의 처음 자본 · 결과의 실험 이름(6-5), 레지스트리 명세의 id(4-7), 관문 목록(4-9), 자르고 읽지 않는 신호용 시세(6-2), 늘 참인 분기 · 쓰지 않는 로거(6-7)
- [x] 목표 3: 조용히 기본값으로 넘기던 자리를 직접 인덱싱으로(12-6) — 리밸런싱의 `.get(…, 0.0)`, 에쿼티의 종가 없는 자산 건너뛰기, 이전 상한의 `max(현금, 0)`, 비중의 「자본 0 이하면 0」 · 분모 EPSILON
- [x] 목표 4: 같은 것을 한 곳에 — Q-2-2XS 슬롯(8-1, 인자 20곳 → 상수 하나), 주문 의도 종류 묶음(3-9), 포트폴리오 결과 파일 이름과 구성 의존 파일 지우기(3-3, 테스트를 붙인다), 시그널 CSV 반올림(7-6), 이동평균 열 이름(3-18), 실험 선택지(4-8), 유효 시작일(7-13), 배분 비중 채우기 · 엔진 행 만들기 · 자산 키 목록(7-8)
- [x] 목표 5: 코드와 어긋난 주석 · docstring 을 고친다 — 없는 실험 예시(C2), 코드 사본인 명세 블록과 틀린 서술(C5), 코드에서 나오는 개수(14절), 「기존」 · 「C안」 같은 이력 표현(15절)
- [x] 목표 6: 결과 파일은 등록 조합 실험의 `summary.json` 하나만 바뀐다(설정 사본에서 배분 규칙 자산의 `signal_data_path` 칸 삭제). 나머지 결과 파일 273개와 모든 성과 수치는 바이트까지 같다

## 2) 비목표(Non-Goals)

- **체결 · 계획 함수의 「사전에 그 자산이 있나」 가드(7-8 의 일부)** — 남긴다(사용자 결정 2026-10-17). 전역 규칙이 불가능 조건을 「내부 불변조건 위반」 RuntimeError 로 정하고, 테스트 2개와 안내 문서가 계약으로 적어 두었다
- **포트폴리오 거래 기록의 `buy_buffer_pct`(6-5 의 일부)** — 결정 8 (가)(2026-10-11, `trades.csv` 의 기록 전용 열 유지)대로 둔다
- **엔진 로더와 `list_position_keys` 의 자산 키 열거 통합(7-8 의 일부)** — 하지 않는다. 키 정보(`PositionKeyInfo`)가 배분 규칙 자산의 시세 경로를 갖지 않아 칸을 늘려야 하고, 얻는 것이 작다. 열 이름에서 키를 뽑던 자리(`build_combined_equity`)만 엔진 장부의 키를 받게 한다
- **대시보드 안의 다른 정리** — `app_portfolio_backtest.py` 는 결과 파일 이름 상수(3-3)만 고친다. 거래 기록 열의 표시 이름 사전(`"shares"` · `"hold_days_used"` 리터럴, 4-6 의 연결 누락)과 나머지는 11단계 대시보드
- **결정 번호(D○○) 토큰** — 16-B 와 함께. **안내 문서의 이력 · 가변 수치(15절 「안내 문서」 · 14절의 문서 자리)** — 12단계 2. 이번에는 이 변경으로 거짓이 되는 문장과 C2 의 없는 실험 이름만 고친다
- **임시 문서(설계서 `Q2_2XS_보완_전략_설계.md` · 지난 계획서)의 옛 시그니처** — 고치지 않는다(지울 문서)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계 넷째 줄(backtest)의 둘째 계획서다(첫째 단일 · 워크포워드 · 고원은 `20d6458`). 줄에 남은 포트폴리오 엔진 · 보완 실험 항목과, 앞 계획서들이 넘긴 포트폴리오 자리를 처리한다
- 항목마다 지금 무엇이 문제인가 (2026-10-17 저장소 사본에서 다시 쟀다. 스크래치 `step11e/`. 점검 보고서 줄 번호는 기준 커밋 `40011ad` 값이라 함수 이름으로 가리킨다)

| 항목 | 지금 | 재현 · 근거 → 바꾸는 것 |
|---|---|---|
| 6-4 유지일 상태 | `HoldState` 4칸 중 `start_date` 는 쓰기만 하고 `buffer_pct` · `hold_days_required` 는 생성자 값의 복사본. `_last_buy_buffer_pct` · `_last_hold_days_used` 도 매수 직후에는 늘 생성자 값 | `_hold_days_passed: int \| None` 하나로, `get_buy_meta` 는 생성자 값. 그러면 `check_buy` 의 `current_date` 를 읽는 곳이 0 이 되어 사슬째 지운다 — `SignalStrategy` · 두 전략 · 단일 엔진 호출 · `generate_signal_intents` · `_plan_book` · `WeightAllocator.target_weights`(HAA · 로테이션은 원래 안 썼고 EWY 는 `check_buy` 로 넘기기만 했다). 테스트 호출 약 70곳. 점검 보고서가 함께 적은 `noqa` 2줄은 5단계에서 이미 없어졌다 |
| 6-5 배분 자산 신호 경로 | `AllocationAssetConfig.signal_data_path` — 설정을 만드는 12곳(src 1 · 테스트 11) 모두 매매 경로와 같고, 두 경로를 가르는 테스트가 없다. 판단에만 쓰는 시세는 `SignalSeriesConfig` 가 따로 있다 | 칸 삭제(사용자 결정). 엔진은 매매 시세로 판단하고 공통 기간의 「배분 자산 신호 날짜」 항이 함께 없어진다(매매 날짜와 같았다) |
| 6-5 주문 의도 칸 넷 | `OrderIntent` 의 `asset_id`(사전의 키와 같은 값) · `current_amount` · `target_amount` · `target_weight` — 읽는 코드 0(병합 때 복사만). 체결은 `delta_amount` 만, 상태 로그도 그것만 | 칸 삭제(사용자 결정). src 생성 8곳 · 테스트 생성 18곳 · 그 칸을 단언하던 테스트 6곳은 증감액 단언으로 |
| 6-5 그 밖 | `MethodBook.initial_capital` · `PortfolioResult.experiment_name` 읽기 0. `portfolio_execution` 의 `buy_buffer_pct` 0.0 | 앞 둘 삭제. 뒤는 결정 8 로 유지(비목표) |
| 4-7 | `AllocatorSpec.allocator_id` · `StrategySpec.strategy_id` — 레지스트리 사전의 키와 같은 값, 읽기 0 | 칸 삭제 |
| 4-9 | `supplement_experiment.GATE_IDS` — src · scripts 사용 0(테스트 1줄) | 삭제. 테스트는 관문 다섯을 직접 적는다 |
| 6-2 | 엔진이 `data.series_dfs`(배분 규칙의 신호용 시세)를 워밍업 · 시작일로 자르는데, 배분 규칙은 자르기 전 복사본을 받고 잘린 것은 아무도 읽지 않는다 | 자르는 루프 둘과 복사 삭제 — 배분 규칙은 `data.series_dfs` 를 그대로 받는다(받는 값은 같다) |
| 6-7 | `engine_common` 의 쓰지 않는 로거, `summarize_methods` 의 「상계 절감 열이 없으면 0」(매매법이 여럿일 때만 부르고 그때 늘 있다), 러너의 `if not result.state_log_df.empty`(검사기가 빈 상태 로그에서 먼저 멈춘다)와 같은 블록의 늘 참인 열 검사, 엔진의 `else pd.DataFrame()`(2행 미만이면 실행 전에 멈춘다) | 삭제 |
| 12-6 | `RebalancePolicy` 의 `projected_amounts.get(aid, 0.0)` 4곳, `compute_portfolio_equity` 의 `if aid in asset_closes`, `cap_transfers` 의 `max(현금, 0.0)`, 엔진 비중의 `val / (equity + EPSILON) if equity > 0 else 0.0` 2곳 | 직접 인덱싱 · 분기 삭제(키는 늘 있고 현금은 음수가 아니며 자본은 0 이 아니다 — 깨지면 멈춘다). 점검 보고서가 「규칙 2 가 비중 열을 견준다」로 남기자던 EPSILON 은 7-4 로 그 근거가 없어졌고, 실험 다섯을 분모 EPSILON 0 으로 돌려 비중 열이 반올림 전 값부터 0건 다르다(자본이 천만 원 단위라 1e-12 를 더해도 같은 부동소수) |
| 3-3 | 포트폴리오 러너 ↔ 대시보드의 결과 파일 이름 리터럴(`equity.csv` · `trades.csv` · `summary.json` · `ledger.csv` · `signal_{키}.csv`), 구성 의존 파일 지우기가 러너(테스트가 불러올 수 없는 스크립트)에 있다 — 미룬 지적 「낡은 장부」를 막는 장치인데 그 줄을 지워도 품질 검증이 통과한다(8단계 코드 리뷰, 사용자 결정 「src 함수로 옮겨 테스트」) | `backtest/constants.py` 에 `LEDGER_FILENAME` · `NETTING_FILENAME` · `PORTFOLIO_SIGNAL_PREFIX` · `portfolio_signal_filename`(나머지 셋은 단일 결과와 같은 상수), `csv_export.remove_config_dependent_files` + 테스트 2. `state_log.csv` 는 러너만 쓴다 → 러너 상단 상수 |
| 3-9 | 의도 종류 튜플 리터럴 — 엔진 2곳(매도 · 매수) · 엔진 `_plan_book` 2곳 · 체결 2곳 · 검사기 1곳 | `portfolio_planning` 에 `SELL_INTENT_TYPES` · `BUY_INTENT_TYPES` · `REBALANCE_INTENT_TYPES`(목표 금액으로 증감). 점검 보고서는 둘이라 했지만 `_plan_book` · 검사기가 쓰는 것은 셋째 묶음이다 |
| 8-1 | Q-2-2XS 슬롯을 순환 import 를 피하려고 `q2_2xs_slots` 인자로 src · scripts 20곳에 넘긴다(테스트 약 40곳) | 슬롯 튜플을 `supplement_experiment.Q2_2XS_SLOTS` 상수로, `portfolio_configs` 의 `portfolio_q2_2xs` 가 그것을 쓴다(이미 그 방향으로 import 한다). 인자 삭제. 다른 슬롯을 넣어 보던 테스트 하나는 상수를 바꿔 넣는다 |
| 7-6 · 3-18 · 4-8 | 러너의 시그널 반올림 블록(`round_signal_for_csv` 와 같은 규칙), `f"ma_{slot.ma_window}"`, `_CONFIG_MAP`(선택지에만 쓴다) | `round_signal_for_csv` · `ma_col_name` · 선택지 인라인 |
| 7-13 | `compute_portfolio_effective_start_date` 가 첫 행을 얻으려고 잘라 `reset_index` 하고 이미 `date` 인 값을 다시 만든다 | 행 수 확인 뒤 `iloc[valid_start]` |
| 7-8 | `run_portfolio_backtest` 본체(약 356줄)에 행 만들기 인라인, 배분 비중을 `_validate_allocation` 과 `_plan_book` 이 두 번 채운다(둘째는 `.get(key, 0.0)`), `build_combined_equity` 가 자산 키를 열 이름의 `_shares` 접미사에서 뽑는다 | 에쿼티 행 · 장부 행을 함수로(`_equity_row` · `_ledger_rows`), 검증 · 채우기를 `resolve_allocation` 한 번(엔진이 부르고 `generate_allocation_intents` 는 채운 목표를 받는다 — 배분 규칙의 None(목표 변경 없음)은 엔진이 의도를 만들지 않는다), `build_combined_equity(rows, asset_keys)`. 가드 · 키 열거 통합은 비목표 |
| C2 | 러너 docstring 의 `portfolio_a2` · `portfolio_c1`, `portfolio_types` 의 「G 시리즈」 · 「B시리즈」 · `"portfolio_a2"` · `"A-2 (…)"` — 없는 실험(argparse 가 거부). 안내 문서 두 줄에도 같은 이름 | 있는 실험(`portfolio_d1`)으로 바꾸거나 지운다 |
| C5 | 체결 docstring 의 축소 방식(금액을 줄인다 ↔ 실제는 주수를 줄인다)과 처리 흐름 사본, 리밸런싱의 「should_rebalance 가 True 일 때만 호출」(매매법 사이 되돌리기도 부른다), 계획 주석의 「KeyError 로 중단」(실제 RuntimeError), 예상 상태의 「signal_state == buy 기준」(배분 규칙은 목표 > 0), 엔진 루프 Step 목록(B 없음 · F 있음), `engines/__init__.py` 목록(`portfolio_methods` 없음), `portfolio_types` 머리말(없는 TypedDict) · `PortfolioResult` 열 명세(빠진 열), 러너 저장 파일 목록(`state_log.csv` 없음) | 틀린 서술은 고치고, 코드 사본인 목록 · 열 명세는 계약 몇 줄과 정본 포인터(`backtest/CLAUDE.md` · `asset_*_col`)로 줄인다 |
| 14절 | 「계 149」 · 「w 7단계」 · 「16칸」 · 「= 152」 · 「7개 정합성 규칙」 · 러너 로그의 「7개 규칙」 | 수치 삭제, 오류 메시지는 `len(W_PCTS)` |
| 15절 | 「기존 동작대로」 · 「C안 장부 비용」(2곳) · 「기존 결과 파일의 열 이름이 바뀌지 않는다」 · 「결과 파일이 달라졌다」 · 「기존 그리드 러너 … 기존 결과 CSV」 · 「활성 실험만 선택 가능」 | 「왜」만 현재형으로 |
| 4-6 | 한 파일(`portfolio_execution`)만 상수로 쓰는 `COL_SHARES` · `COL_HOLD_DAYS_USED` | 옮기지 않는다 — 같은 뜻 리터럴 `"shares"` · `"hold_days_used"` 가 엔진 공통 `create_trade_record` · 포트폴리오 엔진(체결 주수 합) · 대시보드 표시 사전에 있어 한 파일 전용이 아니라 연결 누락이다(전역 `python.md` 「미사용 판정」). src 의 거래 기록 두 자리가 상수를 쓰게 하고, 대시보드는 11단계 대시보드. `TRADE_TYPE_REBALANCE` 는 3-8 결정대로 둔다 |

### 설계 결정

1. **유지일 상태** — `_hold_days_passed` 가 None 이면 대기 중이 아니다. 대기 중 종가가 상단 밴드 «이하»면 대기를 풀고(같으면 유지로 세지 않는다 — 지금 코드와 같다), 위면 하루 더 세고 유지일을 채우면 매수한다. 유지일 0 은 돌파한 날이 신호다
2. **날짜 인자** — `SignalStrategy.check_buy(signal_df, i)` · `WeightAllocator.target_weights(data, i, is_check_day)`. 날짜가 필요한 전략은 `signal_df` 의 i 행에서 읽는다(지금은 그런 전략이 없다)
3. **배분 규칙 자산** — `AllocationAssetConfig(asset_id, trade_data_path)`. 판단은 매매 시세로, 판단에만 쓰는 시세는 `signal_series`
4. **주문 의도** — `OrderIntent(intent_type, delta_amount, reason, hold_days_used)`. 자산은 의도 사전의 키다
5. **배분 비중** — `resolve_allocation(new_weights, assets)` 이 검증하고 매매법 전 자산 순서로 채운다(지금과 같은 순서 · 같은 `float` 변환이라 체결 순서가 같다)
6. **Q-2-2XS 슬롯** — `supplement_experiment.Q2_2XS_SLOTS`. 공식 실험 · 보완 실험 · 조합이 같은 튜플을 쓴다
7. **포트폴리오 결과 파일** — 이름은 `backtest/constants.py`(단일 결과와 같은 자리 · 같은 `EQUITY_FILENAME` 등), 구성 의존 파일 지우기는 `csv_export.remove_config_dependent_files`(결과 CSV 저장 보조의 자리 — 모듈 머리말에 「저장 전 정리」를 더한다)
8. **테스트** — 지운 계약의 테스트를 바꾼다: 배분 비중 검증 · NaN 은 `resolve_allocation` 을 직접, 의도 단언은 증감액, 배분 규칙 기록은 날짜 대신 그 행의 날짜를 엔진 첫 거래일과 견준다. 「None 이면 의도 없음」 단위 테스트는 그 판단이 엔진으로 옮겨 지우고 변형 확인으로 엔진 테스트가 잡는 것을 본다. 더하는 테스트: 배분 비중 채우기 1 · 구성 의존 파일 지우기 2 · 대기 중 종가 = 상단 밴드 1 · 유지일을 채운 매수의 메타 1

### 사본 재현 (착수 전 확인, 2026-10-17 ~ 18)

저장소 밖 사본(스크래치 `step11e/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **레드 단계는 두지 않는다** — 성과 수치를 바꾸지 않는 정리이고, 동작이 바뀌는 곳(직접 인덱싱으로 멈춤 · 시그니처)은 새 테스트와 변형 확인으로 본다
- **924 passed**(지금 920 − 지운 1 + 더한 5), Ruff 통과, PyRight 0 errors(테스트 포함), black 적용
- **변형 확인 11종을 모두 테스트가 잡는다** — 유지일 하루 늦게 · 대기 중 밴드와 같은 종가를 유지로 · 유지일 0 도 하루 대기 · 매수 메타 유지일 0 · 배분 규칙 None 을 빈 비중으로 · 배분 비중을 채우지 않음 · 기여 손익 열을 첫 매매법만 · 구성 의존 파일 지우기에서 장부 빼먹음 · 유효 시작일 하루 늦게 · 배분 의도의 신호 · 조정 가르기 · 검사기 규칙 2 가 비중 늘림을 안 봄. 그중 둘(대기 경계 · 매수 메타 유지일)은 처음에 못 잡아 테스트를 더했다 — 지금 코드에도 없던 공백이다
- **결과 파일** — 러너 여섯(단일 · 고원 · 워크포워드 · 포트폴리오 · 보완 그리드 · 조합 그리드)을 수정 전 · 후 사본에서 돌렸다
  - 수정 전 사본의 재실행 결과 = 저장소 `storage/`(차이 0)
  - 수정 후 ↔ 수정 전: 274개 중 다른 파일은 `portfolio_q2_2xs_haa10_rotation10/summary.json` 하나 — 그 설정 사본(`portfolio_config`)의 배분 규칙 자산 11개에서 `signal_data_path` 줄만 빠졌다. 성과 수치 · 다른 칸 · 나머지 273개는 바이트까지 같다
- **화면 대조** — 대시보드 넷을 서버 없이 `main()` 한 번 실행해 화면 요소를 기록했다(기록 도구에 `st.json` 을 더했다). 넷 다 오류 0
  - 포트폴리오(96요소): 다른 것은 채택 조합 탭의 「설정」 JSON 하나(위 11칸)
  - 단일 · 워크포워드 · 고원: 수정 전과 같다
- **바꾼 API 의 다른 사용처** — `docs/research` 의 스크립트 · 보고서에 0건(설계서 · 지난 계획서에만 옛 시그니처가 있다 — 비목표)
- **변경 규모(포맷 적용 뒤)** — src +334 / −507, 스크립트 +74 / −81, 테스트 +268 / −273, 안내 문서 +23 / −26

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」(대시보드는 사용자가 띄운다 · 결과 파일은 덮어써진다) 절
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `HoldState` · `_hold_state` · `_last_buy_buffer_pct` · `_last_hold_days_used` · `q2_2xs_slots` · `GATE_IDS` · `_CONFIG_MAP` · `_SELL_INTENT_TYPES` · `_BUY_INTENT_TYPES` · `_REBALANCE_INTENT_TYPES` · `allocator_series_dfs` · `_validate_allocation` · `allocator_keys` 를 가리키는 코드 · 안내 문서가 src · scripts · tests · `docs/research` 에 0 이다
- [x] 결과 파일: 바뀐 것은 `portfolio_q2_2xs_haa10_rotation10/summary.json` 하나이고, 저장소에서 다시 만든 결과가 사본(`step11e/exp`)의 결과와 바이트까지 같다
- [x] 대시보드 넷을 서버 없이 실행해 오류 0건이고, 수정 전과 다른 화면 요소는 채택 조합의 「설정」 JSON 하나다
- [x] 새로 넣거나 고친 검사마다 결함을 일부러 넣어 테스트가 실패하는 것을 봤다(변형 확인)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`, `src/qbt/backtest/CLAUDE.md`(결과 파일명 · `AllocationAssetConfig` · `OrderIntent` · 의도 생성 함수 시그니처 · 배분 비중 함수 · `WeightAllocator` · `AllocatorSpec` · `StrategySpec` · `check_buy` · 유지일 상태 · 보완 실험 구성 함수 · CSV 저장 함수, C2 의 두 줄), `scripts/CLAUDE.md`(구성 의존 파일 지우기의 자리). `docs/COMMANDS.md` 변경 없음(실행 명령 · CLI 옵션 그대로), `README.md` 변경 없음, `tests/CLAUDE.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 새로 옮긴 것 1(1회차 ④ — 러너가 구성 의존 파일 지우기를 부르는 한 줄을 지키는 테스트가 없다, 사용자 결정 2026-10-19), 이 계획서가 고친 파일 항목 0(남은 원래 1건은 11단계 tests 배정 그대로). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- src: `src/qbt/backtest/{allocator_registry, combo_experiment, constants, csv_export, portfolio_configs, portfolio_types, portfolio_validation, strategy_registry, supplement_experiment, types}.py`, `engines/{__init__, backtest_engine, engine_common, portfolio_data, portfolio_engine, portfolio_execution, portfolio_methods, portfolio_planning, portfolio_rebalance}.py`, `allocators/{ewy_buffer_zone, haa, us_weakness_rotation}.py`, `strategies/{__init__, buffer_zone, buffer_zone_helpers, buy_and_hold, strategy_common}.py`
- scripts: `scripts/backtest/{run_portfolio_backtest, run_supplement_grid, run_combo_grid, app_portfolio_backtest}.py`
- tests: `tests/qbt/test_{allocators, combo_experiment, csv_export, portfolio_configs, portfolio_execution, portfolio_methods, portfolio_planning, portfolio_validation, strategy_interface, supplement_experiment}.py`
- 위 DoD 문서 줄의 문서
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션(`--experiment` 선택지)은 그대로
- `README.md`: 변경 없음

### 데이터/결과 영향

- `storage/results/portfolio/portfolio_q2_2xs_haa10_rotation10/summary.json` — `portfolio_config.methods[*].assets[*].signal_data_path` 11줄 삭제(대시보드 「설정」 JSON 에만 보인다)
- 그 밖의 결과 파일 · 성과 수치는 그대로다(Context 「결과 파일」)

## 6) 단계별 계획(Phases)

### Phase 1 — 사본에서 검증한 코드 · 테스트 · 안내 문서 반영(그린)

**작업 내용**:

- [x] 저장소의 src · scripts · tests · `docs/research` · 안내 문서 둘이 사본의 수정 전 기준(`step11e/base`)과 같은지 확인한다(`diff -rq`)
- [x] 설계 결정 1 – 8 — 사본(`step11e/exp`)에서 검증한 파일 43개(코드 31 · 테스트 10 · 안내 문서 2)를 그대로 넣는다

**Validation**:

- [x] 사라질 이름을 가리키는 코드 · 안내 문서가 0건(DoD 첫 줄의 `grep`)
- [x] 이번에 고친 테스트 파일 10개 — 전부 통과(375 passed)

---

### Phase 2 — 결과 파일 다시 만들기

**작업 내용**:

- [x] 작업 트리의 `storage/` 변경이 0 인지 확인한 뒤 저장소에서 러너 여섯을 돈다 — 단일 · 고원 · 워크포워드 · 포트폴리오 · 보완 그리드 · 조합 그리드(약 10분, `docs/COMMANDS.md` 의 명령)

**Validation**:

- [x] `git status` 의 `storage/` 변경이 1개(등록 조합 `summary.json`)이고, 저장소 `storage/` 가 사본(`step11e/exp/storage`)과 같다(`diff -rq` 차이 0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 저장소의 src · scripts · tests 가 사본에서 검증한 코드와 같은지 `diff -rq` 로 확인한다 — 같으면 사본의 재현(결과 대조 · 화면 대조 · 변형 11종)이 최종 코드의 결과다
- [x] 문서 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 13건 — 버그 6 [무거움 5 · 가벼움 1] · 그 외 7 · 조치: 무거움 1 수정(배분 비중 검증이 엔진 경로에서 빠져도 잡는 테스트가 없다 — 엔진 테스트 2개) · 그 외 5 수정(이 계획서가 새로 어긴 규칙 · 거짓이 된 문장) · 나머지 버그 5 미조치(닿지 않음 · 막는 쪽 · 이 설계로 닫을 수 없음 1 은 사용자에게, 진행 로그) · 그 외 2 미반영)
- [x] `/code-review xhigh` **2회차** (발견 9건 — 버그 0 · 그 외 9 · 1회차와 같은 결함 0 · 조치: 그 외 6 수정(이 계획서가 거짓으로 만든 문장 · 잃은 「왜」 · 할 일이 없어진 래퍼 · 새 테스트의 부동소수 의존) · 그 외 3 미반영)
- [x] 수정분 검증 (2회차 반영분 수정 6건 · 파일 6 · hunk 10 · 발견 2건 — 무거움 0 · 가벼움 1 · 그 외 1 · 조치: 절차대로 고치지 않음, 진행 로그)
- [x] `poetry run python validate_project.py` (passed=926, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 포트폴리오 엔진 · 보완 실험 정리와 Q-2-2XS 슬롯 · 결과 파일 이름 일원화
2. 백테스트 / 버퍼존 유지일 상태의 「지난 날 수」 하나로 단순화와 check_buy · 배분 규칙 target_weights · 신호 의도 생성의 날짜 인자 사슬 삭제
3. 백테스트 / 읽지 않던 배분 자산 신호 경로 · 주문 의도 칸 넷 · 장부 처음 자본 · 결과 실험 이름 · 레지스트리 id · 관문 목록 삭제와 조용한 기본값 대체의 직접 인덱싱 전환
4. 백테스트 / 낡은 장부를 막는 구성 의존 파일 지우기의 src 이동 · 테스트 추가와 조용히 기본값으로 넘기던 리밸런싱 · 에쿼티 · 비중 계산을 멈추는 쪽으로 변경
5. 백테스트 / 점검 보고서 11단계 backtest 둘째 묶음(포트폴리오 엔진 · 보완 실험) 처리 — 3-3 · 3-9 · 4-7 · 4-9 · 6-2 · 6-4 · 6-5 · 7-8 · 7-13 · 8-1 · 12-6

## 7) 리스크(Risks)

- **전략 · 배분 규칙 인터페이스가 바뀐다** — `check_buy` · `target_weights` 에서 날짜 인자가 빠진다. 저장소 안 호출처는 모두 고쳤고(PyRight 0) `docs/research` 의 스크립트에는 없다. 새 전략이 날짜가 필요하면 `signal_df` 의 행에서 읽는다(설계 결정 2)
- **직접 인덱싱으로 바뀐 자리(12-6)는 키가 빠지면 KeyError 로 멈춘다** — 지금 경로에서는 키가 늘 있다(테스트 · 러너 여섯 통과). 조용히 0 으로 넘기던 것이 멈추는 쪽으로 바뀐다
- **결과를 바꾸지 않는 변경이 대부분이라 재실행만으로는 회귀가 드러나지 않는다** — 완화: 결과 파일 바이트 대조 · 화면 대조 · 변형 확인
- **러너 여섯이 약 10분 걸린다** — Bash 기본 제한(2분)을 넘으므로 백그라운드로 돌린다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 3-3 · 3-9 · 3-18 · 4-6 · 4-7 · 4-8 · 4-9 · 6-2 · 6-4 · 6-5 · 6-7 · 7-6 · 7-8 · 7-13 · 8-1 · 12-6 · 13-C C2 · C5 · 14절 · 15절, 19절 11단계, 결정 8
- 사용자 결정(2026-10-17): ① 배분 규칙 자산의 신호 경로 칸 「지운다」 ② 주문 의도의 읽지 않는 칸 넷 「지운다」 ③ 체결 · 계획 함수의 사전 가드 「남긴다」
- 이 계획서로 11단계 backtest 줄이 끝난다. 다음은 11단계 대시보드 → tests

### 진행 로그 (KST)

- 2026-10-17 16:19: 직전 세션의 커밋 후보를 마무리했다(`PLAN_single_wfo_cleanup.md` Done, 사용자가 16:20 에 `20d6458` 로 커밋)
- 2026-10-17 16:29: 점검 보고서에서 이 묶음 항목을 모으고 대상 코드 · 호출처를 읽었다. 사본(`step11e/base`) 기준 920 passed, 저장소 변경 0. 비중 분모 EPSILON 을 0 으로 한 실험 다섯의 비중 열 차이 0건
- 2026-10-17 21:16: 사용자 결정 셋(Notes)
- 2026-10-17 21:19 ~ 22:07: 사본(`step11e/exp`)에 변경을 얹었다 — 러너 여섯 결과 대조(수정 전 사본 = 저장소, 수정 후는 1개 파일만 다름), 대시보드 넷 화면 대조. 사본에 쓰는 명령에서 계획서 게이트 확인창이 두 번 떴다 — 쓰기는 모두 스크래치 안이었다
- 2026-10-18 09:10: 변형 11종(처음 9종을 잡아 경계 · 매수 메타 테스트 2개를 더한 뒤 11종), 924 passed, Ruff · PyRight · black 통과
- 2026-10-18 09:14: 화면 기록 도구에 `st.json` 을 더해 포트폴리오 화면을 다시 대조했다(96요소 중 「설정」 JSON 하나만 다름)
- 2026-10-18 09:17: 계획서 작성(Draft). 자체 검증 세 각도(배정 항목 대조 · 다른 로직 영향 · 실행 위험) — 파일 수(43)와 진행 로그 시각 하나를 바로잡았고 세 번째 각도에서는 고칠 것이 없었다
- 2026-10-18 09:19: 승인 — 사용자 「승인」. 저장소의 src · scripts · tests · `docs/research` · `storage` · 설정 파일 · 안내 문서가 사본의 수정 전 기준과 같음을 확인했다(추적 파일 차이 0 — 저장소에만 있는 `src/live` · `tests/live` 는 `__pycache__` 만 남은 폴더)
- 2026-10-18 09:19: Phase 1 — 사본에서 검증한 파일 43개를 줄 단위로 넣었다(저장소 = `step11e/exp`, src · scripts · tests `diff -rq` 차이 0). 사라질 이름 0건, 고친 테스트 파일 10개 375 passed. Phase 2 — `storage/` 변경 0 을 확인하고 저장소에서 러너 여섯을 백그라운드로 돌렸다
- 2026-10-18 09:21: 문서 — `docs/AUDIT_REPORT.md` 25곳(항목 행 3-3 · 3-9 · 3-18 · 4-6 · 4-7 · 4-8 · 4-9 · 6-2 · 6-4 · 6-5 · 6-7 · 7-6 · 7-8 · 7-13 · 8-1 · 12-6 · C2 · C5 · 14절 · 15절 두 줄 · 6-T · 20절 12-6 줄 · 19절 backtest · 대시보드 줄). 8-1 행이 함께 사라진다고 적은 「13-6 의 낡은 문구」는 지금 판에 없는 번호이고, 가리킨 문구(슬롯을 인자로 받는 이유 · 순환 설명)는 docstring · 안내 문서에서 함께 없어졌다
- 2026-10-18 09:25: Phase 2 결과 — 러너 여섯 모두 rc=0(단일 4초 · 고원 40초 · 워크포워드 150초 · 포트폴리오 9초 · 보완 그리드 60초 · 조합 그리드 84초). `storage/` 변경 1개(등록 조합 `summary.json`), 저장소 `storage/` = 사본 `step11e/exp/storage`(`diff -rq` 차이 0)
- 2026-10-18 09:27: black 변경 0, 저장소 src · scripts · tests = 사본(`diff -rq` 차이 0). 리뷰 전 사본은 스크래치 `step11e/r1_before/`
- 2026-10-18 09:41: `/code-review xhigh` 1회차 — 발견 13건. 버그 6 [무거움 5 · 가벼움 1] · 그 외 7
  - 고친 버그 1(무거움 · 비켜 간다): ③ 배분 비중 검증(모르는 자산 · NaN · 음수 · 합 1 초과)을 `resolve_allocation` 으로 떼어 내 그 함수만 단위 테스트가 부르므로, 엔진의 `_plan_book` 이 그 호출 대신 검증 없는 채우기를 해도 전체 테스트가 통과한다 — 고치기 전에는 엔진이 부르는 `generate_allocation_intents` 를 테스트가 불러 엔진 경로까지 지켜졌다. 엔진 테스트 `test_engine_rejects_invalid_allocator_weights`(합 1.2 · 모르는 자산 q) 2개를 더했다. 모양(「검증을 공개 함수로 떼어 낸 뒤 그 함수만 단위 테스트한다」)을 diff 에서 찾아 이것 하나. 변형: 엔진의 검증 호출을 채우기로 바꾸면 2 failed · 924 passed, 되돌린 뒤 사본 대조로 변형 없음 확인
  - 고친 그 외 5(이 계획서가 새로 어긴 규칙 · 거짓이 된 문장): ⑥ 슬롯 인자를 지워 `test_combo_experiment.py` 의 `_Q2_SLOTS` · `get_portfolio_config` import 가 쓰이지 않게 됐다(전역 「수술적 변경」의 orphan) → 삭제 ⑦ 의도 종류 묶음 셋을 네 파일이 쓰는데 엔진 하위 모듈에 뒀다(`src/qbt/CLAUDE.md` 3계층 규칙) → `backtest/constants.py` 로, 검사기가 엔진 모듈을 import 하지 않게 됐다. 같은 모양으로 `Q2_2XS_SLOTS`(두 파일)를 봤으나 설정 객체(`AssetSlotConfig` 튜플)이고 `constants.py` 로 옮기면 `portfolio_types` 와 순환하므로 실험 설정 쪽에 둔다 ⑧ 대체 판 변환 설명의 「배분 자산의 신호 · 매매 경로」(지운 칸) — `_to_alt` docstring · `backtest/CLAUDE.md` · 테스트 docstring 셋 ⑨ 새로 쓴 `delta_amount` 주석 「목표 금액 − 현재 평가액」이 현금이 모자라 줄인 리밸런싱 매수액에서 틀린다 → 줄인 금액임을 밝혔다 ⑪ 거래 기록 열 이름 연결을 `shares` 만 했다 → 같은 파일의 `pnl` · `exit_price` 읽기도 상수로(`asset_id` 는 상수가 없다)
  - 고치지 않은 버그 5: ① `generate_allocation_intents` 에 일부 자산만 담은 목표를 넘기면 빠진 자산의 청산을 만들지 않는다(무거운 모양) — 기준 1(닿지 않음): 유일한 호출부(엔진)가 `resolve_allocation` 으로 채운 목표를 넘긴다 ② `cap_transfers` 에서 `max(현금, 0)` 을 지워 매도 뒤 현금이 음수면 이전 방향이 뒤집힌다(무거운 모양) — 기준 1 · 2: 매도 뒤 현금은 전날 끝 현금 + 매도 대금이라, 음수가 되려면 전날 끝 현금이 음수여야 하고 그 날은 검사기 규칙 4 가 먼저 잡아 러너가 멈춘다 ④ 러너가 `remove_config_dependent_files` 를 부르는 한 줄은 여전히 테스트가 닿지 않는다(그 줄을 지우면 낡은 장부가 남는다 — 무거운 모양) — 이 계획서의 설계(2026-10-11 사용자 결정: 로직을 src 로 옮겨 테스트)로는 닫을 수 없다. 러너는 테스트가 불러올 수 없는 스크립트라 저장 전체를 src 로 옮겨야 한다 → 마무리 때 사용자에게 올린다 ⑤ 대기 판정을 `not (종가 > 밴드)` 에서 `종가 <= 밴드` 로 바꿔 밴드가 NaN 이면 대기를 풀지 않고 센다(무거운 모양) — 기준 1: 단일 엔진은 이동평균이 빈 행을 실행 전에 거르고(`filter_valid_rows`), 포트폴리오 슬롯은 워밍업 뒤에만 돌며, 로더가 결측 가격을 막아 시작 뒤 NaN 이 생기지 않는다 ⑩ `summarize_methods` 의 「상계 절감 열 없음」 분기를 지워 매매법 하나짜리 결과에 부르면 안내 없는 KeyError — 기준 2(멈추는 쪽, 유일한 호출부는 매매법이 여럿일 때만 부른다)
  - 반영하지 않은 그 외 2: ⑫ `portfolio_q2_2xs` 의 표시 이름이 슬롯 비중을 문자열로 적는데 슬롯이 다른 모듈로 옮겨졌다(지금 값은 맞고, 옮기기 전에도 같은 파일 안 두 벌이었다) ⑬ 배분 자산 시세의 `.copy()` 가 불필요하다(성능)
  - 1회차 반영 뒤 관련 테스트 301 passed, Ruff · black 통과. 점검 보고서 3-9 행의 자리를 `backtest/constants.py` 로 맞췄다. 2회차 전 사본은 스크래치 `step11e/r2_before/`
- 2026-10-18 09:56: `/code-review xhigh` 2회차(상한) — 발견 9건. 버그 0 · 그 외 9(리뷰가 같이 돌린 품질 검증 926 passed). 1회차 미조치 항목은 다시 내지 않았다
  - 고친 그 외 6: ① `backtest/CLAUDE.md` 실험 설정 절의 「슬롯은 `portfolio_configs.py`」가 거짓이 됐다 → `Q2_2XS_SLOTS` 자리를 덧붙였다 ② `position_key` docstring 을 15절대로 현재형으로 고치며 「왜」(매매법 하나짜리 실험의 결과 열 이름이 자산 id 라 늘 접두사를 붙이면 결과 파일 · 대시보드 열 이름이 바뀐다)를 잃었다 → 되살렸다 ③ `SignalStrategy` docstring 의 지운 상태 이름 `hold_state`(DoD 의 `_hold_state` 검색에 안 걸린다) ④ 테스트 docstring 의 「넘긴 슬롯 그대로」 ⑦ 신호 경로 칸이 없어져 `_allocation_asset` 가 할 일 없는 한 줄 래퍼가 됐다 → 삭제, 호출 5곳을 `AllocationAssetConfig` 로 ⑨ 새 경계 테스트가 종가를 `98.0 * (1 + 0.03)` 로 손으로 만들어 밴드 산식이 바뀌면 「같다」를 더는 시험하지 않을 수 있다 → `compute_bands` 로 만든다. 변형 M02(대기 중 밴드와 같은 종가를 유지로)를 다시 넣어 그 테스트가 실패하는 것을 봤다(1 failed · 925 passed)
  - 반영하지 않은 그 외 3: ⑤ `_equity_row` 의 위치 인자 8개(키워드로 부르면 안전하다 — 지금 호출은 맞다) ⑥ `_plan_book` 이 배분 의도를 「조정 묶음이 아니면 신호」로 가른다(다섯째 의도 종류가 생기면 신호로 섞인다 — 고치기 전 방식은 둘 다에서 빠졌다, 둘 다 조용하다) ⑧ `PortfolioResult.display_name` 도 설정 값의 복사본이다(러너가 읽는다 — 점검 보고서 6-5 의 정정대로 남긴다)
- 2026-10-18 09:57: 2회차 반영 뒤 black · Ruff 통과, 관련 테스트 170 passed. 품질 검증 `validate_project.py` — Ruff · PyRight 통과, passed=926 · failed=0 · skipped=0(사본 924 + 1회차 엔진 테스트 2). 2회차 반영분(파일 6 · hunk 10)의 수정분 검증을 서브에이전트에 맡겼고, 저장소에서 포트폴리오 러너 · 두 그리드를 다시 돌려 결과가 바뀌지 않는지 보는 중
- 2026-10-18 09:59: 최종 확인 — 리뷰 반영 뒤 저장소에서 포트폴리오 러너 · 두 그리드를 다시 돌려(모두 rc=0) `storage/` 가 사본(`step11e/exp/storage`)과 같다(바뀐 파일은 여전히 1개). 대시보드 넷을 저장소 최종 코드로 서버 없이 실행해 화면 요소가 사본(`exp`) 기록과 같다(앱 오류 0). 사본과 달라진 코드는 리뷰 반영분뿐이다(1회차 엔진 테스트 · 상수 자리 · 주석, 2회차 문장 · 래퍼 · 테스트 종가) — 결과 · 화면 대조로 사본의 재현이 최종 코드에도 성립한다
- 2026-10-18 10:05: 수정분 검증 결과(2회차 반영분 — 서브에이전트가 hunk 10개마다 세 물음에 답했다) — 무거움 0 · 가벼움 1 · 그 외 1. 래퍼 삭제(E)는 두 사본에서 구성 함수로 만든 설정 전부(성공 184 · 예외 770 · 그리드 실행 목록 149 · 조합 152 · 등록 실험 5)를 덤프해 1,262줄이 같고, 경계 테스트의 새 종가는 전략이 계산하는 상단 밴드와 비트까지 같다(밴드 산식을 조금 올린 변형 + 대기 경계 변형을 함께 넣으면 옛 테스트는 놓치고 새 테스트는 잡는다)
  - 가벼움 1(절차대로 고치지 않음): 같은 경계 테스트의 i=0 · i=1 종가(100.0 · 101.5)는 손으로 넣은 값이라, 밴드 산식이 크게 바뀌어 i=1 돌파가 사라지면 이 테스트는 아무것도 시험하지 않는다 — 거르는 기준 1(닿지 않음: 계기가 밴드 산식을 바꾸는 앞으로의 변경뿐이고, 그 변형에서 형제 테스트 `test_get_buy_meta_hold_days_used_after_waiting` 과 `test_buffer_zone_contracts.py` 의 밴드 식 테스트 2개가 실패해 스위트는 조용히 지나가지 않는다)
  - 그 외 1: `position_key` docstring 의 「결과 열 이름(… 시그널 파일)」에서 시그널은 파일 이름이다 · 같은 키를 쓰는 `trades.csv` 의 `asset_id` 값과 `summary.json` 이 목록에 없다(뜻은 맞다)
- 2026-10-19 07:18: 사용자 결정 — 1회차 ④(러너가 구성 의존 파일 지우기를 부르는 한 줄을 지키는 테스트가 없다) 「미룬 지적으로 옮긴다」. `docs/DEFERRED_FINDINGS.md` 에 항목을 더하고 점검 보고서 3-3 행에 적었다
- 2026-10-19 07:20: 근거 승격 — 남길 「왜」는 코드와 살아있는 문서에 있다: Q-2-2XS 슬롯의 자리(`supplement_experiment` 상수 주석 · `backtest/CLAUDE.md` 8 · 8-3), 배분 규칙이 매매 시세로 판단하는 이유(`AllocationAssetConfig` docstring · `backtest/CLAUDE.md` 6), 배분 비중을 한 번 채우고 None 은 엔진이 다루는 이유(`resolve_allocation` · `_plan_book` · `backtest/CLAUDE.md` 7), 구성 의존 파일을 지우는 이유(`remove_config_dependent_files` docstring · `scripts/CLAUDE.md`), 자산 키를 열 이름에서 뽑지 않는 이유(`build_combined_equity` docstring), 매매법 하나짜리 실험의 자산 키 규칙(`position_key` docstring), 유지일 대기의 경계(`check_buy` docstring). 처리 사실과 재현 수치(274개 중 1개 · 11줄 · 비중 EPSILON 차이 0건 · 변형 11종)는 점검 보고서 해당 행
- 2026-10-19 07:20: 마무리 — 미룬 지적: 새로 옮긴 것 1(1회차 ④ — 사용자 결정). 거른 지적과 기준 — 1회차 ① ⑤ 는 기준 1, ② 는 기준 1 · 2, ⑩ 은 기준 2, ⑫ ⑬ 과 2회차 ⑤ ⑥ ⑧ · 수정분 검증 그 외 1 은 기준 3, 수정분 검증 가벼움 1 은 기준 1. 미룬 지적 파일의 원래 항목(표시용 열의 테스트 공백)은 이 계획서의 대상이 아니다(11단계 tests). 이 계획서를 지워도 잃는 것이 없다 — 근거 승격(위 줄)과 처리 사실 · 재현 수치(점검 보고서), 남은 지적(미룬 지적 파일)

---
