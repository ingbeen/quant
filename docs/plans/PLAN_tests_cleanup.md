# Implementation Plan: 테스트 정리 — 늘 통과하는 테스트 · 중복 테스트 · 복붙 헬퍼 정리와 표시용 열 테스트 추가

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-23 09:50
**마지막 업데이트**: 2026-10-24 08:02
**관련 범위**: tests(`tests/qbt/` 25개 파일 · `helpers.py` 신규 · `test_numpy_warnings.py` 삭제), 설정(`pytest.ini` · `pyproject.toml`), 문서(`tests/CLAUDE.md` · `docs/AUDIT_REPORT.md` · `docs/DEFERRED_FINDINGS.md`)
**관련 문서**: `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 11단계 「tests」 줄), `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 늘 통과하는 테스트를 실제 단언으로 바꾸거나 지운다(6-17, 6-9 ②) — 같은 모양 셋을 더 찾았다(설계 결정 2)
- [x] 목표 2: 같은 데이터에 같은 단언인 중복 테스트 · 만들고 되읽기만 하는 테스트를 지운다(5-11)
- [x] 목표 3: 테스트 파일끼리 복사해 둔 헬퍼를 공용 모듈 `tests/qbt/helpers.py` 하나로 모으고, 같은 인자로 `run_walkforward` 를 두 번 부르던 테스트를 하나로 합친다(7-9, 사용자 결정)
- [x] 목표 4: pytest 가 RuntimeWarning 을 에러로 다루게 하고, 효과가 없던 경고 픽스처 · 그 테스트 파일 · 쓰이지 않는 마커 · 읽히지 않는 mock 이름을 지운다(6-9 ① ③ ⑤, 결정 15 (가))
- [x] 목표 5: 미룬 지적 「엔진이 에쿼티 표 · 상태 로그에 쓰는 표시용 열의 매매법 여럿 정의를 지키는 테스트가 없다」를 테스트로 고친다(2026-10-11 사용자 결정 — 테스트만)
- [x] 목표 6: 테스트에 손으로 박은 값(3-21)은 결정 14 대로 둔다 — 정책 값은 숫자 고정, 상수 참조는 그대로(코드 변경 없음, 판정만 기록)
- [x] 목표 7: src · scripts · 결과 파일 변화 0

## 2) 비목표(Non-Goals)

- **12단계 1 의 테스트 쪽 몫** — 13-T(테스트 주석 실오류) · 15-T(테스트 이력 주석, 결정 번호 포함) · D17 의 `pytest.ini` 파일 패턴 주석(「`test_*.py` 또는 `*_test.py`」). 사용자 결정(2026-10-23 「19절 그대로」 — 단계를 묶지 않는다). 다만 이 계획서가 지우는 테스트 · 옮기는 헬퍼 안에 있던 자리는 함께 없어진다: 13-T `test_buffer_zone_execution_rules.py` 「현재 구현은 강제청산 로직이 있어 실패할 수 있음」 · `test_walkforward_selection.py` 의 docstring 값(10.0 / 8.0 / 0.8), 15-T `test_tqqq_simulation_core.py` 「기존 수식 · 기존 로직」 · `test_portfolio_backtest_scenarios.py` 「EMA 수렴」(옮긴 헬퍼는 「이동평균 수렴」). D17 의 마커 삭제는 6-9 ③ 과 같은 줄이라 여기서 한다
- **작업 중 찾은 다른 테스트 주석 오류** — `test_engine_common.py` 머리말이 이 파일에 없는 `record_equity` 테스트를 적는다. 13-T 성격이라 12단계 1 로 넘긴다(점검 보고서 13-T 에 한 줄)
- **`_fake_run`(7-9 목록)** — 테스트마다 그 테스트의 지역 표를 잡는 두 줄짜리 클로저라 공용으로 빼면 인자 넘기는 줄이 더 길다. 버림
- **`test_portfolio_state_log.py` 의 시세 헬퍼** — 본문이 다른 시세(12% 상승 · 18% 하락 · 80행)라 그대로 둔다. 같은 파일의 설정 헬퍼만 공용으로 바꾼다
- **pandas 의 DeprecationWarning 9건** — 수정 전과 같다(`resample` 내부)
- **미룬 지적 파일의 다른 두 항목** — 이 계획서의 대상이 아니다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계의 마지막 줄(tests)이다. 직전 계획서는 `PLAN_dashboard_charts.md`(Done, `ab40a64`). 사용자 결정은 Notes
- 항목마다 지금 무엇이 문제인가 (2026-10-23 HEAD `ab40a64` 에서 잼, 보고서 줄 번호는 `40011ad` 기준이라 지금 자리로 다시 찾았다)

| 항목 | 지금 | 바꾸는 것 |
|---|---|---|
| 6-9 ① · 결정 15 | `enable_numpy_warnings` 픽스처(conftest) · `test_numpy_warnings.py`(3개) · 사용 2곳 · `tests/CLAUDE.md` 13줄. 테스트 본문이 스스로 경고를 켜서 픽스처를 빼도 결과가 같다 | 지우고 `pytest.ini` 에 `error::RuntimeWarning` — 사본에서 지금 테스트 그대로 938 passed |
| 6-9 ② | `test_portfolio_state_log.py` 규칙 2 테스트 — 픽스처 76행 중 리밸런싱 행 0 이라 단언 없이 끝난다 | 삭제. 규칙 2 는 `test_portfolio_validation.py` 의 매매법 단위 규칙 2 테스트가 지킨다. 파일 머리말에 그 자리를 적는다 |
| 6-9 ③ | `pytest.ini` 마커 셋(사용 0) · `tests/CLAUDE.md` 「마커 설정은 참고용」 | 삭제 |
| 6-9 ④ | 없는 픽스처 권장 · 경고 픽스처 docstring | ⑥(2026-10-11) 과 ① 로 없어진다 |
| 6-9 ⑤ | `test_backtest_engine.py` 의 `make_mock_strategy(name)` · `s._name`(읽는 곳 0) | 인자째 삭제 |
| 6-17 | 늘 통과하는 테스트(아래 표) | 실제 단언으로 바꾸거나 삭제 |
| 5-11 | 중복 · 되읽기 테스트(아래 표) | 삭제(겹치지 않는 단언 하나는 옮긴다) |
| 7-9 | 파일을 넘는 복사본 — `_weekdays` 2 · `_summary` 2 · 포트폴리오 헬퍼 셋(`_make_stock_df` · `_make_stock_df_with_sell` · `_make_portfolio_config`) 2 + 상태 로그의 같은 설정 헬퍼 1(보고서 밖), 같은 파일 안 `_build_equity_df` 2, 같은 인자의 `run_walkforward` 호출 두 테스트(각 2.3초) | `helpers.py`(설계 결정 3), 같은 파일 안은 모듈 함수 하나, 워크포워드는 한 테스트로 |
| 3-21 · 결정 14 | 숫자 고정 7곳 · 상수 참조 18줄 | 그대로(설계 결정 5) |
| 미룬 지적 1건 | 에쿼티 표 `{키}_weight` · `rebalance_reason`, 계좌 사유 고르기, 상태 로그 `{키}_weight` 의 분모를 바꾸는 결함 넷을 전체 테스트가 통과한다 | 매매법 둘인 시나리오 테스트 3개(설계 결정 4) |

**6-17 · 같은 모양** (「보고서 밖」은 이번에 찾은 것)

| 테스트 | 왜 늘 통과하나 | 처리 |
|---|---|---|
| `test_buffer_zone_execution_rules` `test_open_position_absent_when_all_closed` | `assert True` | 거래 1 · 마지막 날 position 0 · `open_position` 없음 |
| 같은 파일 `test_equity_definition_no_position` | `if len(...) > 0:` 안에서 첫 행만 본다 | 조건 없이 — 거래 없음 · 전 구간 position 0 · equity = 초기 자본 |
| `test_buffer_zone_run` `test_forced_liquidation_at_end` · `test_hold_days_zero_vs_positive` | 열 존재 · 반환 타입만 | 삭제 — 강제청산 없음은 `TestForcedLiquidation` · `test_backtest_end_consistency`, 유지일 경로는 타임라인 테스트가 지킨다 |
| `test_walkforward_selection` 동률 테스트(`in [100, 150]`) | — | 1-8 처리(2026-10-17) 때 `== 150` 으로 이미 고쳐졌다 |
| 같은 파일 `test_wfe_cagr_zero_is_cagr` | WFE 0 을 넣고 요약 평균 0 을 되읽는다 | `run_walkforward` 를 가격이 변하지 않는 시세로 돌려 IS 성과 0 → WFE 0 을 본다(schedule 파일) |
| 같은 파일 `test_wfe_cagr_positive_is_cagr` (보고서 밖) | 시세가 꾸준히 오르기만 해 7개 윈도우 모두 거래 0 · IS CAGR 0 — 나눗셈 쪽을 한 번도 타지 않는다 | 같은 인자의 구조 테스트와 합치며 추세 + 진동 시세로(윈도우 3개 IS 거래 3 · 6 · 8회), 나눗셈 쪽을 타는지 먼저 단언 |
| `test_parallel_executor` `test_cache_clear_on_reinit` | 프로덕션 `init_worker_cache` 대신 테스트 파일의 사본을 쓰고, 실행마다 프로세스를 새로 띄운다 | 프로덕션 함수를 프로세스 안에서 두 번 불러 앞 키가 지워지는지. 워커 초기화 테스트도 프로덕션 함수로 |
| 같은 파일 `test_cache_read_only` (보고서 밖) | 프로세스가 나뉘어 원본이 바뀔 수 없다 | 삭제 |

**5-11**

| 지운 것 | 같은 것 | 비고 |
|---|---|---|
| `test_portfolio_strategy_types` `TestStrategyType` 4개 | `TestStrategyTypeBehavior` 의 같은 이름 넷 | 빈 거래 표의 열 단언(2-8 · 2-12 때 붙은 것)은 새 테스트 `test_no_trades_keeps_trade_record_columns` 로 옮긴다 |
| `test_buffer_zone_execution_rules` `test_hold_days_0_timeline` · `test_final_capital_with_position_remaining` | `test_buy_execution_timing_separation` · `test_forced_liquidation_equity_consistency` | 데이터 · 단언 같음 |
| `test_tqqq_simulation_core` `test_close_unchanged_after_open_improvement` · `test_invalid_leverage` 3개 | `test_leverage_effect`(허용오차를 좁은 쪽 0.01 로) · `test_invalid_numeric_params_raise` | |
| `test_engine_common` `TestExecuteSellOrder` 3개 | `TestExecuteSellOrderPure` · `TestCreateTradeRecord` | |
| `test_buffer_zone` TQQQ · QQQ 설정의 run_single 구조 2개 | `test_run_single_returns_single_backtest_result` · `test_data_info_contains_paths` | 머리말 목록 7번 줄 삭제 |
| `test_strategy_registry` 키 존재 2 + 개수 1 · Protocol 메서드 2 · 매수 후 보유 열 · 행 수 2 · 워밍업 「ma_window 무관」 1 | 키 집합 1 · `isinstance` 테스트 · 원본과 같은 표 1(`assert_frame_equal`) · `test_buy_and_hold_returns_zero` | 이동평균 10 · 20, 워밍업 10 · 200 의 두 값 테스트는 남긴다 — 「고정값 반환」 결함을 다른 값이 잡는다 |
| `test_portfolio_planning` `TestOrderIntentModel` 4개 · `test_buffer_zone_contracts` `TestBuyBufferZonePctField` 2개 | — | dataclass 를 만들고 되읽기만 한다. 두 파일 머리말을 맞춘다 |
| `test_analysis` `TestAddSingleMovingAverage::test_normal_calculation` | `test_ma_type_policy` 의 두 테스트 | 7-9 의 「중복 3쌍」 중 이름이 적힌 쌍 |
| (보고서의 `test_tqqq_data_loader.py:375-423`) | — | 5-6 처리(2026-10-14) 때 로더를 합치며 이미 없어졌다(`40011ad` 와 대조) |
| (보고서의 `test_meta_manager.py`) | — | 결정 6(2026-10-11) 으로 파일째 없다 |

### 설계 결정

1. **RuntimeWarning** — `pytest.ini` 의 `filterwarnings` 끝에 `error::RuntimeWarning`(주석 한 줄). 마지막 일치 항목이 이기므로 끝에 둔다
2. **늘 통과하던 테스트는 지우기보다 실제 단언** — 그 계약이 다른 테스트에 없을 때(미청산 없음 · 무포지션 에쿼티 · WFE 두 분기 · 캐시 초기화). 다른 테스트가 같은 계약을 지키면 지운다
3. **공용 헬퍼** — `tests/qbt/helpers.py`(`weekdays` · `run_summary` · `make_rising_stock_df` · `make_rise_then_fall_stock_df` · `make_portfolio_config`). pytest 가 테스트 폴더를 import 경로에 넣고 pyright 실행 환경의 root 가 `tests/qbt` 라 `from helpers import …` 가 그대로 잡힌다. 지금 테스트끼리 import 하는 곳은 0건이라 새 관용이다(사용자 결정) — `tests/CLAUDE.md` 폴더 구조에 한 줄, ruff isort `known-local-folder = ["helpers"]`(외부 패키지 묶음에 섞이지 않게). 포트폴리오 시세 헬퍼는 이름이 파일마다 다른 본문의 `_make_stock_df` 와 겹쳐 모양을 드러내는 이름으로 바꾼다
4. **표시용 열 테스트** — `test_portfolio_methods.py` 의 `TestAccountDisplayColumns`. 매매법 a(슬롯, x · y 반반)와 b(테스트용 배분 규칙 — 신호용 시세가 100 을 넘으면 x 0.75 · z 0.25, 아니면 반반). x 가 1월 중순 +30% 라 a 는 1월 말 판단으로 정기 리밸런싱하고, 같은 날 신호용 시세가 뛰어 b 는 사유 없는 비중 조정을 한다 → 2024-02-01 에 두 매매법이 다른 사유로 함께 리밸런싱한다(「첫 매매법」을 가를 수 있는 날). 테스트 3개(비중 열 — 에쿼티 표 · 상태 로그 두 판 / 계좌 사유). 비중 기대값은 입력 시세 종가로 계산한다(`_value` 열을 되읽지 않는다)
5. **3-21(결정 14)** — 숫자 고정 7곳은 정책 값이라 그대로: 비용률(0.003 · 99.7 · 100.3), 4P 값, 4P 유지일 3, 리밸런싱 임계값 0.10, 배분 규칙 워밍업 253 · 200 · 200, 운용비율 확장 136개월(1999-01 시작 — 코드에 상수 없이 적힌 정책). 상수 참조 18줄(`SLIPPAGE_RATE` 11 · `TRADING_DAYS_PER_YEAR` 5 · `ANNUAL_DAYS` 2)도 그대로 — 정책 상수마다 숫자로 고정한 테스트가 있다(위 0.003 · 99.7, Sharpe · Sortino 의 √21 · √84, 보완 실험 회전율의 365.25, 4P)

### 사본 재현 (착수 전 확인, 2026-10-23)

저장소 밖 사본에 이 계획서의 변경을 그대로 얹어 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **사본** — HEAD `ab40a64` 를 `git archive` 로 뽑은 수정 전(스크래치 `step11t/base`) · 수정 후(`step11t/exp`) · 변형 되돌리기용 원본(`step11t/pristine`). 저장소 `.venv` 파이썬에 `PYTHONPATH=사본/src`, 사본을 cwd 로
- **레드 단계는 두지 않는다** — src 를 바꾸지 않고, 새 · 고친 테스트는 사본에서 결함을 넣어 실패를 봤다(아래)
- **품질** — black 변경 0(편집한 13개 파일을 정리한 뒤), Ruff 통과, PyRight 0 errors, 906 passed(지금 938 − 지움 40 + 더함 8, 수집 목록으로 대조). 경고 9건은 수정 전과 같다. 전체 테스트 18.3 → 14.3초
- **테스트 코드** — `tests/` 24,537 → 23,455줄
- **변형 확인** (수정 전 테스트 → 수정 후 테스트)

| 넣은 결함 | 수정 전 | 수정 후 |
|---|---|---|
| 에쿼티 표 `{키}_weight` 를 절반으로 | 938 passed | 1 failed |
| 에쿼티 표 `rebalance_reason` 을 늘 빈 값으로 | 938 passed | 1 failed |
| 계좌 사유를 리밸런싱한 매매법 중 마지막 매매법의 것으로 | 938 passed | 1 failed |
| 상태 로그 `{키}_weight` 를 매매법 자본 대비로 | 938 passed | 1 failed |
| 샤프 계산 안에 0 나누기 한 줄(값은 그대로) | 938 passed(경고 11) | 2 failed |
| 청산 뒤에도 `open_position` 을 남김 | 938 passed | 1 failed |
| WFE CAGR 나눗셈을 IS ÷ OOS 로 뒤집음 | 938 passed | 1 failed |
| IS CAGR 이 0 이면 WFE CAGR 1 | 1 failed(옛 「양수」 테스트가 0 쪽만 타서 잡았다) | 1 failed |
| `init_worker_cache` 의 `clear()` 삭제 | 938 passed | 1 failed |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `src/qbt/backtest/CLAUDE.md`(포트폴리오 결과 열의 정의 — 설계 결정 4)
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 저장소의 tests · `pytest.ini` · `pyproject.toml` · `tests/CLAUDE.md` 가 Phase 1 에서 사본(`step11t/exp`)과 같고(`diff -rq` 차이 0), src · scripts 변경 0 — 그 뒤 달라진 것은 코드 리뷰 반영분(테스트 · `conftest.py` · `pytest.ini` 주석)뿐이고 src · scripts 는 끝까지 0(2026-10-24 조정)
- [x] `enable_numpy_warnings` · `test_numpy_warnings` · `_init_worker_cache` · `_try_modify_cache` · `TestStrategyType` · `TestOrderIntentModel` · `TestBuyBufferZonePctField` · `TestExecuteSellOrder` · `TestRebalanceWeightConsistency` · `_make_portfolio_config_for_state_log` 과 테스트 파일의 헬퍼 정의 `def _weekdays` · `def _summary` · `def _build_equity_df` · `def _make_stock_df_with_sell` 이 tests 와 안내 문서에 0 이다(점검 보고서 · 계획서 제외 — `_summary` 는 버리는 변수 이름으로도 쓰여 정의만 센다)
- [x] 결과 파일 변화 0 — 작업 트리의 `storage/` 변경 0
- [x] 새로 넣은 · 고친 검사마다 결함을 일부러 넣어 실패하는 것을 봤다(변형 확인)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `tests/CLAUDE.md`(사본에서 반영 — 폴더 구조 한 줄 · 마커 줄 · 경고 픽스처 절), `docs/AUDIT_REPORT.md`(처리 표시 · 결정 14 · 15 · 19절, 13-T 에 찾은 한 줄), `docs/DEFERRED_FINDINGS.md`(고친 항목 삭제). `docs/COMMANDS.md` 변경 없음(실행 명령 · CLI 옵션 그대로), `README.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 옮긴 것 0: 2회차 ④ 는 사용자가 받아들였고(2026-10-24), 나머지 고치지 않은 지적은 거르는 기준에 들었다(진행 로그). 이 계획서가 고친 미룬 지적 파일의 첫 항목은 지웠다. 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- tests: `tests/qbt/helpers.py`(신규), `tests/qbt/test_numpy_warnings.py`(삭제), `tests/qbt/conftest.py`, `test_{allocators, analysis, backtest_engine, buffer_zone, buffer_zone_contracts, buffer_zone_execution_rules, buffer_zone_run, combo_experiment, engine_common, parallel_executor, portfolio_backtest_scenarios, portfolio_execution, portfolio_methods, portfolio_planning, portfolio_state_log, portfolio_strategy_types, strategy_registry, supplement_experiment, tqqq_simulation_core, tqqq_simulation_cost_model, walkforward_schedule, walkforward_selection}.py`
- 설정: `pytest.ini`, `pyproject.toml`(ruff isort 한 줄)
- 문서: `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`, `docs/DEFERRED_FINDINGS.md`
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션 그대로
- `README.md`: 변경 없음

### 데이터/결과 영향

- 결과 파일 변화 0 — src · scripts 를 바꾸지 않고 러너를 돌리지 않는다
- 테스트 수 938 → 906. 테스트가 수치 경고를 내면 이제 실패한다

## 6) 단계별 계획(Phases)

### Phase 1 — 사본에서 검증한 테스트 · 설정 · 안내 문서 반영(그린)

**작업 내용**:

- [x] 저장소의 src · scripts · tests · 설정 · 안내 문서가 사본의 수정 전 기준(`step11t/base`)과 같은지 확인한다(`diff -rq`)
- [x] 사본(`step11t/exp`)에서 검증한 파일을 그대로 넣는다(신규 1 · 삭제 1 · 수정 26)

**Validation**:

- [x] 저장소 tests · 설정 · `tests/CLAUDE.md` = 사본 `exp`(`diff -rq` 차이 0), src · scripts 차이 0, DoD 둘째 줄의 이름 0건

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 — `docs/AUDIT_REPORT.md`(6-9 · 6-17 · 5-11 · 7-9 · 3-21 · 결정 14 · 15 처리 표시, 13-T 에 찾은 한 줄, 19절 11단계 tests 줄), `docs/DEFERRED_FINDINGS.md`(고친 항목 삭제)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 12건 — 버그 6 [무거움 4 · 가벼움 2] · 그 외 6 · 조치: 무거움 4 수정(검사 공백 — 워커 프로세스의 경고 필터 · WFE 평균 · 중앙값 · WFE 0 대체 · 계좌 사유의 설정 순서) · 그 외 1 수정(제 변경이 남긴 빈 절 머리) · 가벼움 2 미조치(닿지 않음) · 그 외 5 미반영, 진행 로그)
- [x] `/code-review xhigh` **2회차**(상한) (발견 13건 — 버그 4 [무거움 3 · 가벼움 1] · 그 외 9 · 1회차와 같은 지적 4 · 조치: 무거움 1 수정(윈도우 WFE Calmar 나눗셈 단언) · 가벼움 1 수정(통합한 레지스트리 테스트가 입력 변경을 못 잡음) · 무거움 2 미조치(같은 자리 두 번 1 — 사용자에게, 닿지 않음 1) · 그 외 3 수정(제 변경의 orphan 헬퍼 · 보고서 수치 · 새 주석 문체) · 그 외 6 미반영)
- [x] 수정분 검증 (수정 9 hunk · 발견 0건 — 무거움 0 · 조치: 없음. 변형 7종 대조)
- [x] `poetry run python validate_project.py` (passed=907, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 테스트 / 늘 통과하던 테스트 · 중복 테스트 정리와 공용 헬퍼 모듈 분리
2. 테스트 / 결함을 넣어도 통과하던 검사 보강 — 워커 프로세스 경고 필터 · WFE 두 분기 · 매매법 여럿의 표시용 열
3. 테스트 / 점검 보고서 11단계 tests 줄 처리 — 6-9 · 6-17 · 5-11 · 7-9 · 3-21 과 미룬 지적 1건
4. 테스트 / RuntimeWarning 의 테스트 실패 처리와 효과 없던 경고 픽스처 · 마커 삭제
5. 테스트 / 같은 데이터 · 같은 단언 테스트 40개 삭제와 실제 단언 테스트 9개 추가(938 → 907)

## 7) 리스크(Risks)

- **테스트끼리 import 하는 새 관용** — `helpers.py` 를 pytest 가 아닌 다른 실행기(IDE 의 단일 파일 실행 등)로 돌리면 import 경로가 다를 수 있다. 저장소의 실행 경로(`validate_project.py` · `poetry run pytest`)는 사본에서 확인했다
- **`error::RuntimeWarning` 이 앞으로의 테스트를 막을 수 있다** — 일부러 0 나누기를 재는 테스트가 생기면 `pytest.warns` 로 감싸야 한다. 지금 그런 테스트는 0 이다(사본 906 passed)
- **지운 테스트가 지키던 것** — 지운 40개는 표의 「같은 것」이 같은 데이터 · 같은 단언으로 지키거나(5-11), 단언이 없었다(6-17). 겹치지 않던 단언 하나(빈 거래 표의 열)는 옮겼다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 6-9 · 6-17 · 5-11 · 7-9 · 3-21 · 결정 14 · 15, 19절 11단계 tests, `docs/DEFERRED_FINDINGS.md` 첫 항목
- 사용자 결정(2026-10-23):
  - 남은 단계는 19절 그대로 — 단계를 묶지 않는다(11단계 tests → 12단계 1 – 6 을 따로)
  - 결정 15 (가) — `error::RuntimeWarning` 을 넣는다
  - 결정 14 남은 몫 — 상수 참조를 그대로 둔다(정책 값마다 숫자 고정 테스트가 있다)
  - 7-9 — 공용 모듈 하나(`tests/qbt/helpers.py`)
- 사용자 결정(2026-10-24, 「추천대로」): 코드 리뷰 2회차 ④(conftest 가 `PYTHONWARNINGS` 를 덮어써 개발자가 둔 값이 워커에서 사라진다)는 받아들인다 (가) — 막는 쪽으로만 틀리고 그 변수를 쓰는 실행 안내가 없다. 점검 보고서 결정 15 행에 받아들인 한계로 적었다
- 과거 결정: 결정 14 의 기준 「정책 값은 숫자 고정, 단순 픽스처 값은 상수 참조」(2026-10-09 보고서 추천), 단일 엔진 신호 · 매매 테스트의 비용률 · Sharpe · Sortino 의 252 를 숫자로 고정(2026-10-10), 미룬 지적 「표시용 열 테스트」 고친다 — 테스트만(2026-10-11)
- 이 계획서 다음은 12단계 1(19절)

### 진행 로그 (KST)

- 2026-10-23 09:05 ~ 09:20: 점검 보고서 19절로 남은 단계를 정리하고 tests 줄 항목을 지금 코드에서 쟀다. 사본에 `error::RuntimeWarning` 을 넣어 938 passed. 결정 4건(묶음 · 결정 15 · 결정 14 남은 몫 · 7-9 헬퍼 자리)을 올렸고 사용자가 답했다(Notes)
- 2026-10-23 09:20 ~ 09:45: 사본(`step11t`)을 HEAD `ab40a64` 로 만들고 변경을 얹었다. 합친 워크포워드 테스트가 처음에 실패해 옛 「양수」 테스트의 데이터가 거래 0 이었음을 찾았다(6-17 표). 수정 전 사본 복구 경로의 실수로 `base` 의 엔진 파일에 변형이 남은 것을 `git show` 원본으로 되살리고, 변형마다 따로 다시 쟀다(`pristine` 사본에서 되돌린다). 변형 확인 9종 · 906 passed
- 2026-10-23 09:50: 계획서 작성(Draft)
- 2026-10-23 09:55: 자체 검증 네 각도 — ① 배정 항목 대조(19절 tests 줄: 6-9 · 6-17 · 5-11 · 7-9 · 3-21 · 결정 14 · 15 · 미룬 지적 1건, 6-18 은 2026-10-11 처리됨) ② 다른 로직 영향(src · scripts 0, `known-local-folder` 는 `helpers` 라는 이름에만 걸리고 그 이름의 모듈은 `tests/qbt/helpers.py` 하나) ③ 수치 대조(상수 참조 3 + 2 + 6 · 4 + 1 · 2 = 18줄, 숫자 고정 7곳, 변경 파일 26 + 신규 1 + 삭제 1, 테스트 938 − 40 + 8 = 906) ④ DoD 의 이름 목록을 사본에 grep — `_summary` 가 버리는 변수 이름으로 13곳 남아 「헬퍼 정의」로 좁혔다. 그 밖에 고칠 것 없음
- 2026-10-23 22:00: 승인 — 사용자 「진행」. 저장소의 src · scripts · tests · `docs/research` · `storage` · vendor · 설정 · 안내 문서가 사본의 수정 전 기준(`step11t/base`)과 같다(`diff -rq` — 추적 밖 `src/live` · `tests/live` · vendor 의 egg-info 는 제외)
- 2026-10-23 22:01: Phase 1 — 사본 `exp` 의 tests/qbt(`rsync --delete`, 추적 밖 `tests/live` 는 대상 밖) · `tests/CLAUDE.md` · `pytest.ini` · `pyproject.toml` 을 넣었다. 저장소 = 사본 `exp`(`diff -rq` 차이 0), src · scripts 차이 0, DoD 둘째 줄의 이름 0건
- 2026-10-23 22:05: 문서 — `docs/AUDIT_REPORT.md`(결정 14 · 15 · 3-21 · 5-11 · 6-9 · 6-17 · 7-9 · D17 · 13-T 둘 + 찾은 한 줄 · 15-T 둘 · 19절 tests 줄), `docs/DEFERRED_FINDINGS.md`(고친 첫 항목 삭제). black 변경 0
- 2026-10-23 22:06: `/code-review xhigh` 1회차 첫 실행은 세션 한도로 결과 없이 끝났다
- 2026-10-23 23:05 ~ 23:23: `/code-review xhigh` 1회차(재실행) — 발견 12건. 고치기 전 사본은 스크래치 `step11t/r1_before/`
  - 고친 것 5: ① 무거움 — `error::RuntimeWarning` 이 그리드 서치의 spawn 워커 프로세스에 닿지 않는다(워커 안 0 나누기가 inf 로 통과) → 모양 「pytest 설정이 워커 프로세스에 닿지 않는다」, diff 에서 같은 모양 1곳(경고 필터뿐). `conftest.py` 가 `PYTHONWARNINGS=error::RuntimeWarning` 을 환경 변수로 물려준다(`pytest.ini` 주석 한 줄). 변형 「그리드 워커 함수 안 0 나누기 한 줄」: 수정 전 conftest 2 passed → 수정 후 2 failed(`test_basic_grid_search` · `test_grid_search_parameter_combinations`) ② 무거움 — 모드 요약의 WFE 평균 · 중앙값을 지키는 테스트가 없다(지운 되읽기 테스트도 두 지표 입력이 모두 0 이라 못 지켰다) → Robust 테스트의 윈도우 셋을 모듈 상수 `_THREE_WINDOWS` 로 올리고 `TestWfeMeanMedian` 1개. 같은 모양(지운 테스트만 참조하던 출력 키)을 지운 40개의 문자열 키 75개로 대조 — 지금 테스트가 참조하지 않는 키는 테스트 안 이름 · 경고 문구 · 설정 이름뿐(0곳). 변형 「CAGR 평균을 Calmar 값으로」 · 「Calmar 중앙값을 평균으로」: 수정 전 906 passed → 수정 후 각 1 failed ③ 무거움 — 새 「IS 성과 0 → WFE 0」 테스트가 OOS 도 0 이라 「OOS ÷ (IS + ε)」 대체와 갈리지 않는다 → IS 구간만 평평하고 OOS 는 추세 + 진동(윈도우 1 — OOS CAGR −13.9 · Calmar −0.73 · 거래 4). 변형 「OOS ÷ (IS + ε)」: 수정 전 906 passed → 수정 후 1 failed ⑤ 무거움 — 계좌 사유 테스트의 매매법 이름 a → b 가 이름순과 같아 「설정 순서상 첫」을 가르지 못한다 → 매매법 이름을 slot(첫째) · alloc(둘째)으로. ③ ⑤ 는 같은 모양(「픽스처가 결함과 정답을 같은 값으로 만든다」) — 이 계획서가 더하거나 고친 테스트 9개를 다시 봐 더 없음. 변형 「이름순 첫 매매법」: 수정 전 906 passed → 수정 후 1 failed ⑩ 그 외 — 헬퍼를 옮기고 남은 빈 「공통 헬퍼」 절 머리(전역 「본인 변경으로 생긴 orphan 정리」)
  - 변형은 저장소 사본(`r1_nofix` = 수정 전 테스트 · `r1_exp2` = 수정 후)에서 돌리고 `pristine` 원본으로 되돌렸다 — 두 사본의 src 가 원본과 같음을 대조했다
  - 고치지 않은 지적 7: ④ 공용 시세 헬퍼가 행 수 40(상승만은 10) 미만이면 조용히 짧은 표를 낸다(옛 사본은 길이 불일치로 멈췄다) — 기준 1(지금 호출 20곳 — 상승만 20 · 30 · 50행, 상승 뒤 하락 60행. 새 호출 코드가 있어야 닿는다) ⑪ `_equity_df` 가 값 31개를 넘으면 날짜 오류 — 기준 1 · 2(지금 호출 8곳 최대 6개, 넘으면 멈춘다) ⑥ 포트폴리오 시나리오 `_make_jump_df` ≡ 매매법 테스트 `_price_df` 복사본 ⑦ 같은 날짜 루프가 8곳 더 ⑧ 표시용 열 테스트가 같은 백테스트를 세 번 ⑨ 빈 거래 표 테스트가 다른 테스트와 같은 시나리오를 다시 돈다 ⑫ 새 테스트 함수의 타입 힌트(이웃 테스트 관용과 같다) — 모두 기준 3(그 외)
- 2026-10-23 23:24 ~ 23:31: `/code-review xhigh` 2회차(상한) — 발견 13건. 1회차와 같은 지적 4(③ = 1회차 ④ · ⑦ ⑪ = 1회차 ⑥ ⑦ · ⑬ ⑫ = 1회차 ⑧ ⑫). 고치기 전 사본은 스크래치 `step11t/r2_before/`
  - 고친 것: ① 가벼움 — 매수 후 보유 레지스트리 테스트를 합치며 호출 뒤의 `df` 와 견줘, 입력 표를 그 자리에서 바꾸는 결함을 못 잡는다(합치기 전 테스트는 잡았다 — 이 계획서의 통합이 약하게 했다) → 호출 전 사본과 결과 · 입력을 모두 견준다. 변형 「입력에 열을 더하고 그 표를 반환」: 수정 전 907 passed → 수정 후 1 failed ② 무거움 — 윈도우 WFE Calmar(`oos_calmar / is_calmar`)를 지키는 테스트가 없다(나눗셈을 뒤집어도 907 passed) → 합친 구조 테스트의 루프에 Calmar 단언과 「IS Calmar ≠ 0」 전제. 같은 모양(그 테스트의 다른 WFE 분기) — 0 쪽은 두 지표 모두 「IS 성과 0」 테스트가 본다. 변형 「IS ÷ OOS」: 수정 전 907 passed → 수정 후 1 failed ⑤ 그 외 — 1회차 수정으로 `test_walkforward_schedule.py` 의 `_make_stock_df` 호출이 0 이 되었다(전역 「본인 변경으로 생긴 orphan 정리」) → 삭제 ⑥ 그 외 — 점검 보고서의 테스트 수(906 → 907) · 「두 번 부른다」(실제는 앞 키를 넣어 둔 캐시에 한 번) → 고쳤다 ⑩ 그 외 — 새로 쓴 `#` 주석 6줄이 간결체가 아니다(전역 주석 규칙) → 간결체로
  - 사용자에게 올린 것(같은 자리 두 번): ④ conftest 가 `PYTHONWARNINGS` 를 덮어써 개발자가 이미 둔 값(예: `default::RuntimeWarning`)이 워커에서 사라진다 — 1회차 ① 이 고친 자리. 틀리는 방향은 더 엄격한 쪽(워커의 수치 경고가 실패)이다
  - 고치지 않은 것: ③ 공용 시세 헬퍼의 행 수 40 미만 — 기준 1(1회차 ④ 와 같다) ⑦ 같은 OHLC 표 만드는 블록 두 번 · 주말이 섞인 날짜 계산(기존 테스트와 같은 방식) ⑧ 「IS 성과 0」 전제의 `== 0.0` 정확 비교(코드가 0.0 을 넣는 분기의 전제라 그 값이다) ⑨ 새 함수의 타입 힌트 ⑪ `_trading_dates` 사본 ⑫ 같은 백테스트 세 번 ⑬ 모듈 상수 `_THREE_WINDOWS` 를 테스트가 바꿀 수 있다(바꾸는 테스트 0) — 모두 기준 3(그 외)
- 2026-10-23 23:32 ~ 23:42: 수정분 검증 — 수정분 diff(9 hunk)와 각 수정이 겨냥한 지적만 `general-purpose` 서브에이전트에게 줬다. 발견 0. 변형 7종: 나눗셈 뒤집기 · Calmar 를 CAGR 로 · 입력 변경 둘은 수정 후만 실패, 두 키 뒤바꾸기는 양쪽 실패, 「Calmar 가드를 CAGR 로」는 동등 변형(IS Calmar 가 0 일 때만 IS CAGR 이 0), 「같은 객체 반환」은 수정 전부터의 공백(수정 범위 밖). 덧붙인 것(diff 밖): `test_portfolio_backtest_scenarios.py:130` 주석이 옛 이름 `_make_stock_df` 를 가리킨다 — 헬퍼 이름을 바꾼 본 변경의 같은 모양이라 diff 전체에서 옛 헬퍼 이름이 남은 주석 · docstring 을 찾았고 그 1곳을 고쳤다(주석)
- 2026-10-23 23:44: 자동 포맷(black 변경 0) · `validate_project.py` — Ruff · PyRight 통과, passed=907 · failed=0 · skipped=0. `storage/` 변경 0. 상한 회차라 멈추고 사용자에게 보고한다 — ④ 의 처리
- 2026-10-23 23:46: 상태를 Draft(사용자 결정 대기)로 — 결정 전에는 미룬 지적 옮김(DoD)과 커밋 후보를 확정할 수 없다(종료 훅 안내 — 상태 표기는 정해진 셋 중 하나만 받는다)
- 2026-10-24 08:00: 사용자 결정 「추천대로」 — ④ 받아들임(Notes). 상태를 진행 중으로 되돌렸다. 리뷰 반영 뒤 DoD 둘째 줄의 이름 0건 · `storage/` 변경 0 을 다시 확인했다
- 2026-10-24 08:02: 마무리
  - 문서 — 점검 보고서 결정 15 행에 받아들인 한계, DoD 첫 줄을 리뷰 반영분에 맞췄다(src · scripts 0 은 그대로)
  - 근거 승격 — 남길 「왜」는 코드와 살아있는 문서에 있다: 워커 프로세스에 경고 필터를 물려주는 이유(`conftest.py` 주석 · `pytest.ini` 주석), 공용 헬퍼를 import 하는 방법과 isort 묶음(`helpers.py` 머리말 · `tests/CLAUDE.md` 폴더 구조 · `pyproject.toml` 주석), 표시용 열 테스트의 시나리오와 설정 순서를 이름순과 반대로 둔 이유(`TestAccountDisplayColumns` docstring), WFE 테스트가 거래가 생기는 시세를 쓰는 이유(그 테스트 docstring), 상태 로그의 규칙 2 를 맡는 파일(그 파일 머리말). 사용자 결정 · 처리 사실 · 변형 확인 수치는 점검 보고서 해당 행과 19절. 이 계획서를 지워도 잃는 것이 없다
  - 거른 지적 표(Done 보고): 1회차 ④ · 2회차 ③ 공용 시세 헬퍼의 짧은 행 수 — 기준 1(지금 호출 20곳 모두 기준 이상) · 1회차 ⑪ `_equity_df` 값 31개 초과 — 기준 1 · 2(호출 8곳 최대 6개, 넘으면 멈춘다) · 1회차 ⑥ ⑦ ⑧ ⑨ ⑫ · 2회차 ⑦ ⑧ ⑨ ⑪ ⑫ ⑬ — 기준 3(그 외)

---
