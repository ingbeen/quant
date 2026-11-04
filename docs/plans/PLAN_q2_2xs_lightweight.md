# Implementation Plan: Q-2-2XS 단독 확정에 맞춘 저장소 경량화

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-04 13:47
**마지막 업데이트**: 2026-11-04 14:56
**관련 범위**: scripts 전 영역, src/qbt/backtest · tqqq · utils, tests, storage, docs
**관련 문서**: CLAUDE.md, docs/MEMORY.md, docs/CLAUDE.md, docs/COMMANDS.md, README.md, scripts/CLAUDE.md, src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, src/qbt/utils/CLAUDE.md, tests/CLAUDE.md, docs/research/전략_검증_보고서.md

---

## 1) 목표(Goal)

- [x] 목표 1: 운용안 Q-2-2XS 단독(`portfolio_q2_2xs`)에 쓰이지 않는 묶음 셋을 지운다 — 보완 전략(M), V2 · 스플릿 · 민감도 · 세 줄(N), TQQQ 일별 비교 · 스프레드 랩(T-ⓑ)
- [x] 목표 2: 그로 인해 고아가 되는 src · tests · 결과 · 시세 · 상수 · 문서 참조를 함께 정리한다 (등록은 양방향)
- [x] 목표 3: 남는 실험 · 러너의 결과 파일이 지우기 전과 바이트 단위로 같다

## 2) 비목표(Non-Goals)

- 워크포워드 · 파라미터 고원(W), 단일 백테스트(S), TQQQ · QLD 합성 생성(T-ⓐ), 등록 실험 QQQ 보유 · D-1 · Q-2 · Q-2-2XS 는 남긴다 (질문 라운드 Q1, 2026-11-04)
- 포트폴리오 엔진의 여러 매매법 기능(장부 · 상계 · 매매법 사이 되돌리기 · 배분 규칙 `allocators/` · `allocator_registry.py`)과 그 테스트는 그대로 둔다 (Q2 ⓐ)
- 시세 다시 받기(`download_data.py`) — 결과 대조가 깨진다(루트 CLAUDE.md)
- 남는 코드의 리팩터링 · 이름 바꾸기 (예: 합성 생성이 쓰는 `DAILY_COMPARISON_TARGETS` 의 이름은 그대로 둔다)
- 보고서의 과거 기록(UGL · UBT 연구, 부록 M · N 의 측정)을 고쳐 쓰는 일 — 재현 위치만 커밋 해시로 바꾼다
- git 조작 — 커밋은 사용자가 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 결정(2026-11-04): 운용 포트폴리오를 Q-2-2XS 단독으로 확정하고 「scripts 에서 불필요한것들을 제거하면서 프로젝트 경량화」. 경량화 전에 방법론 · 결론 · 연구 결과는 보고서로 옮겼다(부록 N.21 ~ N.30 · 부록 O, 2026-11-04)
- 질문 라운드(2026-11-04, 「추천대로 진행」): Q1 묶음 M · N · T-ⓑ 제거, W · S · T-ⓐ · 기타 등록 실험 유지 / Q2 ⓐ 엔진 기능 유지 / Q3 지운 묶음의 결과 · 시세 파일도 지우고 UGL · UBT 도 뺀다 / Q4 문서 자리(완료) / Q5 부수 문서 정리 / Q6 MEMORY 확정 기록(완료) / Q7 이력은 두고 HANDOFF.md 는 삭제만
- 지우기 전 코드 · 결과는 커밋 `ee6d23d`(HEAD, 사용자 커밋 · 푸시됨)에 모두 있다. 그 뒤 코드 변경은 없다

### 연결 지도 (조사 2026-11-04, `grep` — 정의부 제외)

| 지울 것 | 남는 코드가 기대는 곳 | 처리 |
| --- | --- | --- |
| `supplement_experiment.py` | `portfolio_configs.py` (`Q2_2XS_SLOTS` · 채택 조합 구성 함수), `run_portfolio_backtest.py` (`run_with_start_check`), `tests/qbt/helpers.py` (`RunSummary`), `generate_proxy_comparison.py` · `app_proxy_comparison.py` (`PHASE_WINDOWS` — 둘 다 지움) | `Q2_2XS_SLOTS` 는 `portfolio_configs.py` 로, `run_with_start_check` 는 결정 D1 대로 |
| `utils/proxy_series.py` | `scripts/tqqq/generate_synthetic.py` 가 `splice_proxy` 를 쓴다 | `splice_proxy` 와 그 내부 도우미만 남기고, 지운 스크립트만 쓰던 `build_daily_rebalanced_composite` · `build_rate_accrual_series` 는 지운다 |
| `strategies/strategy_common.py` 의 `IntradayStopStrategy` | `engines/backtest_engine.py` 의 장중 손절 판정 · 「4-1-1」 블록 | 판정 줄과 블록만 지운다. 매도 가격 변수(`sell_price_raw`) 구조는 손절 없이도 같은 결과를 내므로 둔다 |
| `simulate_long_history` · `LONG_HISTORY_SPREAD_CAP` · `FFR_PRE1999_DATA_PATH` | 세 줄 러너 하나뿐 | 함께 지운다 (+ `storage/etc/federal_funds_rate_pre1999_monthly.csv`) |
| TQQQ 일별 비교 · 스프레드 랩 | `analysis_helpers.py`(전체) · `spread_lab_helpers.py` · `visualization.py` · `simulation.calculate_validation_metrics` · `_save_daily_comparison_csv` · `data_loader.load_comparison_data` · 비교 CSV 열 · `KEY_*` 상수 | 남는 호출처가 0 이 되는 것만 지운다. `simulate` · 금리 · 운용비율 · `DAILY_COMPARISON_TARGETS` · `SYNTHETIC_DATA_PATHS` 는 합성 생성이 쓴다 |
| `min_start_date` (설정 칸) | 보완 실험만 값을 넣는다 — 남는 네 실험은 모두 `None` | 결정 D1 |

- 외부: 실매매 알림 저장소(quant-notify)는 이 저장소 코드를 import 하지 않고, 설계 문서가 Q-2-2XS 구성의 정본으로 「quant `portfolio_configs.py`」를 가리킨다 — `Q2_2XS_SLOTS` 를 그 파일로 옮기면 그 기술이 사실이 된다
- `scripts/` 를 import 하는 테스트는 없다 → 스크립트 · 대시보드는 실행 · `AppTest` 로 검증한다

### 남는 것 (경량화 뒤)

- scripts 10개: `data/download_data.py` · `backtest/run_portfolio_backtest.py` · `app_portfolio_backtest.py` · `run_single_backtest.py` · `app_single_backtest.py` · `run_walkforward.py` · `app_walkforward.py` · `run_param_plateau_all.py` · `app_parameter_stability.py` · `tqqq/generate_synthetic.py` — 지금 23개에서 M 6 · N 4 · T-ⓑ 3 = 13개를 지운다 (질문 라운드에서 「남는 scripts 13개」라고 한 것은 셈이 틀렸다)
- 시세 `storage/stock` 9개: SPY · QQQ · GLD · TLT · SSO · QLD · TQQQ (원본 7) + `TQQQ_synthetic` · `QLD_synthetic`
- 결과: `portfolio/` 의 네 실험, `backtest/` 의 버퍼존 · Buy & Hold 단일 결과와 워크포워드 · 고원

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절, 「스크립트 실행 규칙」(대시보드는 `AppTest` 만, 결과 파일 덮어쓰기, `download_data.py` 금지), 「가격 반올림 자릿수」, `docs/MEMORY.md`
- `docs/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `tests/CLAUDE.md`
- 전역 `~/.claude/rules/python.md` 「미사용 판정에는 «왜 안 쓰이는가»가 함께 필요하다」 · 전역 `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `scripts/` 의 `.py` 가 「남는 것」의 10개뿐이다
- [x] 남는 러너 다섯을 다시 돌린 결과가 Phase 0 기준선과 같다 — W(워크포워드 · 고원)는 보관본 `baseline_fresh_20261104/` 과 `diff -r` 0건, 그 밖은 `git status --short storage` 에 `D`(지운 파일) 말고 `M` 이 0건. 대조 뒤 W 추적 파일은 커밋 상태로 되돌린다(D3 = A)
- [x] 지운 모듈 · 함수 · 상수 · 파일 이름이 `src` · `scripts` · `tests` 에 0건이고, 추적 문서에는 과거 기록과 커밋 해시를 단 재현 안내로만 남는다
- [x] 바뀐 대시보드 · 등록 목록을 읽는 대시보드가 `AppTest` 에서 예외 0건 (`app_single_backtest.py` · `app_portfolio_backtest.py`)
- [x] 옮긴 함수(D1)의 테스트가 있다
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 있음(지운 명령 · 순서 블록), README 변경 있음(기능 목록), 하위 `CLAUDE.md` 여섯(scripts · src/qbt · backtest · tqqq · utils · tests) 변경 있음, 루트 `CLAUDE.md` 변경 있음(가격 반올림 표의 저장 스크립트 목록 한 줄 — 디렉터리 구조는 그대로)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (보고서 부록 D.9 에 지운 등록 실험 행, 재현 절의 커밋 해시)
- [x] 미룬 지적 옮김 — 해당 없음: 고치지 않은 리뷰 지적 15건이 모두 「그 외」(거르는 기준 3)라 옮긴 것이 없다. 거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다. 이 계획서가 그 파일에서 지운 항목은 지운 코드에 대한 둘(민감도 대시보드 · 세 줄 러너)이다
- [x] `HANDOFF.md` 삭제 (사용자 요청 「완료 후 HANDOFF.md 삭제」)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**지우는 파일**

| 묶음 | scripts | src | tests |
| --- | --- | --- | --- |
| M | `backtest/run_supplement_grid.py` · `run_combo_grid.py`, `data/generate_proxy_series.py` · `generate_long_proxy_series.py` · `generate_proxy_comparison.py` · `app_proxy_comparison.py` | `backtest/supplement_experiment.py` · `combo_experiment.py`, `utils/proxy_comparison.py` | `test_supplement_experiment.py` · `test_combo_experiment.py` · `test_proxy_comparison.py` |
| N | `backtest/run_buffer_zone_sensitivity.py` · `app_buffer_zone_sensitivity.py` · `run_buffer_zone_three_lines.py` · `app_buffer_zone_three_lines.py` | `backtest/buffer_zone_sensitivity.py` · `buffer_zone_three_lines.py`, `strategies/buffer_zone_v2.py` · `split_ladder.py`, `engines/split_engine.py` | `test_buffer_zone_sensitivity.py` · `test_buffer_zone_three_lines.py` · `test_buffer_zone_v2.py` · `test_split_engine.py` · `test_tqqq_simulation_long_history.py` |
| T-ⓑ | `tqqq/generate_daily_comparison.py` · `app_daily_comparison.py` · `spread_lab/app_rate_spread_lab.py` (폴더째) | `tqqq/analysis_helpers.py` · `spread_lab_helpers.py` · `visualization.py` | `test_tqqq_analysis_helpers.py` · `test_tqqq_spread_lab_helpers.py` · `test_tqqq_visualization.py` |

**고치는 파일**

- src: `backtest/portfolio_configs.py` · `engines/portfolio_engine.py`(D1) · `engines/backtest_engine.py` · `strategies/strategy_common.py` · `strategies/__init__.py` · `runners.py` · `types.py` · `common_constants.py` · `utils/proxy_series.py` · `tqqq/simulation.py` · `tqqq/data_loader.py` · `tqqq/constants.py` · `tqqq/__init__.py` (+ 지운 뒤 고아 검사에서 나오는 상수 파일)
- scripts: `backtest/run_portfolio_backtest.py` · `run_single_backtest.py` · `app_single_backtest.py`, `data/download_data.py`(`DEFAULT_TICKERS` 에서 UGL · UBT)
- tests: `helpers.py` · `test_portfolio_configs.py` · `test_proxy_series.py` · `test_strategy_interface.py` · `test_tqqq_simulation_outputs.py` · `test_tqqq_data_loader.py` · `test_integration.py` · D1 테스트를 둘 파일
- docs: `docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `tests/CLAUDE.md` · `docs/MEMORY.md` · `docs/DEFERRED_FINDINGS.md` · `docs/research/전략_검증_보고서.md`
- 지우는 문서: `docs/plans/` 의 완료 계획서 5개(`PLAN_buffer_zone_sensitivity` · `PLAN_buffer_zone_three_lines` · `PLAN_buffer_zone_v2_split` · `PLAN_qld_daily_comparison` · `PLAN_qld_synthetic`), `HANDOFF.md`. `docs/plans/` 폴더는 이 계획서가 남아 유지된다
- `docs/COMMANDS.md`: 변경 있음 — 지운 명령 13개 · 「시세를 다시 받은 뒤 다시 돌리는 순서」 블록 · 「데이터 다운로드 옵션」의 대용 · 장기 대체 · 대체-실물 비교 절

### 데이터/결과 영향

- 지우는 결과: `storage/results/portfolio_grid/` · `portfolio_combo_grid/` · `proxy_comparison/` · `tqqq/`(일별 비교 · 스프레드 랩 CSV), `portfolio/portfolio_q2_2xs_haa10_rotation10/`, `backtest/buffer_zone_sensitivity/` · `buffer_zone_three_lines/` · `buffer_zone_v2_{qqq,qld,tqqq,gld,tlt}/` · `split_tqqq/` · `split_tqqq_2004/`
- 지우는 시세 38개: M 전용 33(`VEA` · `BIL` · `PDBC` · `VXUS` 의 `_synthetic`, `SSO` · `QLD` · `BIL` · `VXUS` 의 `_proxy`, `DBC_synthetic`, 뮤추얼 펀드 8 VTMGX · VEIEX · VGSIX · VGTSX · VUSTX · VFITX · VFISX · VIPSX, EFA · EEM · IWM · VWO · VNQ · IEF · TIP · SHY · BIL · DBC · PDBC · VEA · VXUS · EWY · GC=F · ^SPGSCI), N 전용 3(^GSPC · ^NDX · ^IXIC), 아무도 읽지 않는 UGL · UBT
- 지우는 기타: `storage/etc/federal_funds_rate_pre1999_monthly.csv`
- 남는 결과는 바뀌지 않아야 한다 — D1 을 B 안으로 정하면 남는 네 실험의 `summary.json` 에서 `"min_start_date": null` 줄이 빠진다(그 밖은 같다)

## 6) 단계별 계획(Phases)

### Phase 0 — 기준선 (코드 변경 없음)

**작업 내용**:

- [x] `git status` 로 작업 트리 확인 — 코드 · 결과는 `ee6d23d` 그대로인지
- [x] `storage/` 를 통째로 scratchpad 에 사본으로 둔다(`cp -Rp`) — 러너가 추적 결과를 덮어쓰고 git 되돌리기는 사용자 몫이라, 기준선이 커밋과 다르면 사본을 복사해 되돌린다
- [x] 지금 코드로 남는 러너 다섯을 다시 돌린다: `generate_synthetic.py` → `run_single_backtest.py` → `run_walkforward.py`(약 6분) → `run_param_plateau_all.py` → `run_portfolio_backtest.py`

**Validation**:

- [x] `git status --short storage` 가 빈 출력 — 지금 코드로 돌려도 커밋된 결과와 같다(대조 기준 성립). 다르면 사본으로 되돌리고 멈춰 보고한다 — W 158파일이 달라(낡은 커밋 결과, 진행 로그 14:13) 되돌렸고 D3 = A 로 대조 기준을 나눴다: W 는 보관본 `baseline_fresh_20261104/`, 나머지는 커밋

---

### Phase 1 — 보완 전략(M) 제거

**작업 내용**:

- [x] `Q2_2XS_SLOTS` 를 `portfolio_configs.py` 로 옮기고, 채택 조합 등록(`_SUPPLEMENT_CONFIGS`)과 그 import 를 지운다
- [x] D1 대로 `run_with_start_check` 를 처리하고 `run_portfolio_backtest.py` 의 import · 경고 문구(지운 모듈을 가리키는 「supplement_experiment.py 의 묶음 시작일」)를 고친다
- [x] M 의 scripts 6 · src 3 · tests 3 을 지운다
- [x] `proxy_series.py` 에서 지운 스크립트만 쓰던 함수 둘과 그 테스트(`test_proxy_series.py` 의 해당 클래스)를 지운다
- [x] `common_constants.py` 에서 호출처가 0 이 된 경로 상수(M 전용 시세 · `PORTFOLIO_GRID_RESULTS_DIR` · `PORTFOLIO_COMBO_GRID_RESULTS_DIR` · `PROXY_COMPARISON_RESULTS_DIR`)를 지운다 — 상수마다 `grep` 으로 0건 확인
- [x] `tests/qbt/helpers.py` 의 `run_summary` 와 `supplement_experiment` import 를 지운다(`weekdays` 는 배분 규칙 테스트가 쓴다)
- [x] `test_portfolio_configs.py` 의 보완 등록 계약을 지우고, `min_start_date` 실험 목록 단언을 남는 등록(없음)에 맞춘다
- [x] D1 의 테스트 1건 추가 — 실제 시작일이 설정과 다르면 `ValueError`

---

### Phase 2 — V2 · 스플릿 · 민감도 · 세 줄(N) 제거

**작업 내용**:

- [x] N 의 scripts 4 · src 5 를 지운다
- [x] `runners.py` 의 V2 · 스플릿 실행 함수와 import, `types.py` 의 `open_lots`, `strategies/__init__.py` · `strategy_common.py` 의 V2 · 장중 손절 부분을 지운다
- [x] `backtest_engine.py` 에서 장중 손절 판정(`stop_strategy`)과 「4-1-1」 블록, docstring 의 예외 문구를 지운다
- [x] `run_single_backtest.py` · `app_single_backtest.py` 에서 V2 · 스플릿 등록 · `open_lots` 저장 · 표시를 지운다
- [x] `tqqq` 에서 `simulate_long_history` · `LONG_HISTORY_SPREAD_CAP` · `FFR_PRE1999_DATA_PATH`, `common_constants.py` 에서 `GSPC_DATA_PATH` · `NDX_DATA_PATH` · `IXIC_DATA_PATH` 를 지운다 — 각각 `grep` 0건 확인
- [x] N 의 tests 5 를 지우고 `test_strategy_interface.py` 의 `IntradayStopStrategy` 단언을 지운다
- [x] 백테스트 상수 파일(`backtest/constants.py`)에서 지운 모듈만 쓰던 상수를 `grep` 으로 찾아 지운다

---

### Phase 3 — TQQQ 일별 비교 · 스프레드 랩(T-ⓑ) 제거

**작업 내용**:

- [x] T-ⓑ 의 scripts 3(spread_lab 폴더째) · src 3 을 지운다
- [x] `simulation.py` 의 `calculate_validation_metrics` · `_save_daily_comparison_csv` · `ValidationMetricsDict` · `ROUND_DAILY_COMPARISON_PERCENT`, `data_loader.py` 의 `load_comparison_data` · `COMPARISON_COLUMNS`, `constants.py` 의 비교 CSV 경로 · 열 · `KEY_*` · `ROLLING_CORR_WINDOW_MONTHS` 등 남는 호출처가 0 인 것, `__init__.py` 의 재노출을 지운다 — 이름마다 `grep` 0건 확인
- [x] T-ⓑ 의 tests 3 을 지우고, `test_tqqq_simulation_outputs.py` 의 검증 지표 · 비교 CSV 클래스, `test_tqqq_data_loader.py` 의 `TestLoadComparisonData`, `test_integration.py` 의 TQQQ 파이프라인에서 검증 지표 단계를 지운다 (`TestDailyComparisonTargets` · `simulate` 단계는 남긴다)

---

### Phase 4 — 시세 · 결과 · 기타 파일 정리 (Q3)

**작업 내용**:

- [x] 「데이터/결과 영향」의 결과 폴더 · 시세 38개 · 금리 파일을 지운다
- [x] `download_data.py` 의 `DEFAULT_TICKERS` 에서 UGL · UBT 를 뺀다

**Validation**:

- [x] `storage/stock` 이 9개, 지운 파일 이름이 `src` · `scripts` · `tests` 에 0건

---

### Phase 5 — 문서

**작업 내용**:

- [x] `docs/COMMANDS.md` — 지운 명령 · 순서 블록 · 대용 절, ② 의 금리 파일 목록
- [x] `README.md` 기능 목록, `scripts/CLAUDE.md` 스크립트 지도, `src/qbt/CLAUDE.md`(상태를 갖는 예외 · 시세 파일 이름의 `_proxy_max`), `src/qbt/backtest/CLAUDE.md`(도메인 목적 · 모듈 지도 · 규칙 3 의 예외 · 규칙 7 의 `open_lots`), `src/qbt/tqqq/CLAUDE.md`(모듈 지도 · 규칙 1 의 V2 문장 · 규칙 3 의 금리 두 파일 · 스프레드 랩 근거를 커밋 해시로), `src/qbt/utils/CLAUDE.md`, `tests/CLAUDE.md`(지운 핵심 로직 줄), 루트 `CLAUDE.md`(변경 여부 확인)
- [x] 보고서 — 재현 절(M.12 · N.7 · N.14 · N.20 · N.30 · O.14)과 §49.4 첫 단락을 `ee6d23d` 로, 부록 D.9 에 지운 등록 실험 행(채택 조합 · 단일 V2 5 · 스플릿 2 와 마지막 산출 수치), 부록 M 철회 상자 · N 머리 · O.2 · O.13 의 「지우기로 했다」를 「지웠다」로
- [x] `docs/MEMORY.md`(Q5) — 「스플릿 매매는 TQQQ 전용」 · 「V2 세 줄 · RSI 없음」 · 「눌림 제거 기본」을 지우고(내용은 부록 N.4 · N.22 · N.28), 「1배 신호 · 종가 손절」의 「저장소 러너는 아직 …」 문장과 「1 · 2 · 3배」 항목의 스플릿 예시를 지운다
- [x] `docs/DEFERRED_FINDINGS.md` — 지운 코드에 대한 두 항목(민감도 대시보드 · 세 줄 러너)을 지우고, 합성 스크립트 항목의 일별 비교 언급을 고친다
- [x] 완료 계획서 5개를 지운다(결론이 보고서 N.1 ~ N.20 · §49.4 에 있는지 확인한 뒤)

---

### 마지막 Phase — 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 남는 러너 다섯을 Phase 0 순서로 다시 돌려 기준선과 대조한다
- [x] `AppTest` — `app_single_backtest.py` · `app_portfolio_backtest.py` (예외 0건)
- [x] 지운 이름 전수 `grep` (DoD 3번째 줄)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] `HANDOFF.md` 삭제
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] W 결과가 보관본과 `diff -r` 0건이고, W 를 커밋 상태로 되돌린 뒤 `git status --short storage` 에 `M` 0건 (남는 결과가 기준선과 같다)
- [x] `/code-review xhigh` **1회차** (발견 15건 — 버그 0 [무거움 0 · 가벼움 0] · 그 외 15 · 조치: 고칠 것 0 — 회차 종료. 다만 그중 1건(`src/qbt/CLAUDE.md` 의 지운 일별 비교 CSV 두 줄)은 이 계획서 DoD 3번째 줄 위반이라 완료 조건으로 고쳤다. 나머지 14건은 목록만 진행 로그에)
- [x] 수정분 검증 — 해당 없음 (리뷰 지적을 버그로 고친 것 없음 · 고친 1건은 규칙 문서 두 줄 삭제이고 코드 변경 없음)
- [x] `poetry run python validate_project.py` (passed=705, failed=0, skipped=0 — Ruff · PyRight 통과)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 운용 포트폴리오 Q-2-2XS 단독 확정과 쓰이지 않는 실험 묶음 정리
2. 백테스트 / 보완 전략 · 버퍼존 V2 · 스플릿 · TQQQ 일별 비교 제거와 연구 결과의 보고서 부록 N · O 이전
3. 백테스트 / 채택 조합 철회에 따른 scripts 23개 중 13개 삭제와 고아 src · 테스트 · 시세 · 결과 정리
4. 백테스트 / 1998년부터 잰 성과 · 세금 · V2 연구 기록과 남는 러너 결과 불변의 경량화
5. 백테스트 / 경량화 — 시작일 대조의 엔진 이전, 단일 엔진 장중 손절 제거, 합성 생성만 남긴 TQQQ 도메인

## 7) 리스크(Risks)

- **단일 엔진 수정이 단일 백테스트 · 워크포워드 · 고원 결과를 바꿀 위험** — 장중 손절 판정은 V2 객체에서만 켜지므로 남는 전략에는 닿지 않아야 한다. Phase 0 기준선과 마지막 Phase 재실행의 `git status` 로 확인한다
- **고아 판정의 누락 · 과잉** — 이름마다 `grep` 으로 호출처를 세고, 「왜 안 쓰이는가」가 「지운 기능의 잔여물」인 것만 지운다. 연결 누락으로 보이는 것은 지우지 않고 보고한다
- **테스트가 scripts 를 부르지 않는다** — 러너는 실행, 대시보드는 `AppTest` 로 검증한다
- **결과 파일 덮어쓰기** — Phase 0 의 `storage` 사본으로 되돌릴 수 있게 한다. 코드는 `ee6d23d` 에 있다
- **문서의 죽은 링크 · 낡은 문장** — 지운 이름 `grep` 을 추적 문서 전체에 돌린다. 과거 기록(보고서 본문 · 부록의 측정)은 고쳐 쓰지 않는다
- **배분 규칙(HAA · 로테이션 · EWY)이 등록 실험 없이 남는다** — Q2 ⓐ 에서 받아들인 상태다. 호출처는 테스트뿐이다

## 8) 메모(Notes)

### 결정 필요 — D1. 시작일 고정 기능(`min_start_date`)과 그 대조 함수

- **현재 확인된 사실**: `run_with_start_check` 는 러너의 `min_start_date` 분기에서 쓰이고, `min_start_date` 에 값을 넣는 실험은 보완 실험뿐이다. 남는 네 실험의 `summary.json` 에는 `"min_start_date": null` 줄이 있다. 엔진은 이 칸을 읽지 않는다
- **과거 결정**: 질문 라운드 Q2 ⓐ(2026-11-04)에서 「시작일 대조 함수는 쓰는 곳이 0이 되므로 지웁니다」라고 했는데 **틀린 설명이었다** — 러너의 분기가 남는 한 그 함수는 지울 수 없다
- **가능한 선택지와 영향**
  - A. 기능 유지 — 대조 함수를 `engines/portfolio_engine.py` 로 옮긴다. 남는 결과 파일이 그대로다. 값을 넣는 실험이 없는 칸이 남는다(배분 규칙과 같은 상태)
  - B. 기능 제거 — 설정 칸 · 러너 분기 · 대조 함수 · 관련 테스트를 지운다. 남는 네 실험의 `summary.json` 에서 `"min_start_date": null` 줄이 빠진다
- **추천: A** — Q2 ⓐ(엔진 기능 유지)와 같은 판단이고, 남는 결과를 한 글자도 바꾸지 않아 대조가 가장 단단하다

### 정해 둔 것 (이의가 있으면 알려 주세요)

- 부록 D.9 의 「커밋」 칸은 경량화 커밋 해시를 모르는 채 쓰므로 「경량화 (지우기 전 `ee6d23d`)」로 적는다. 재현 안내는 모두 `ee6d23d` 를 가리킨다 — 그 커밋에 지울 코드 · 결과 · 명령이 모두 있고, 이력을 다시 쓰지 않기로 했다(Q7)
- MEMORY 「레버리지 전략은 1 · 2 · 3배를 나란히」의 원칙은 남기고 스플릿 예시만 뺀다

### 진행 로그 (KST)

- 2026-11-04 13:47: 계획서 작성. 연결 지도는 Context 표. 문서 옮기기(보고서 부록 N.21 ~ N.30 · 부록 O, MEMORY 확정 항목)는 이 계획서 전에 마쳤다
- 2026-11-04 14:08: 사용자 「추천대로 진행」 — 문서 확인 · 계획 승인 · **D1 = A**(시작일 고정 기능 유지, 대조 함수를 `engines/portfolio_engine.py` 로) · D2(인계서 8절의 설명 선호 두 항목을 `docs/MEMORY.md` 로) 승인
- 2026-11-04 14:13: Phase 0 — 다섯 러너 모두 종료코드 0. 합성 시세 · 단일 백테스트 · 포트폴리오 결과는 커밋과 같다(변경 0). **워크포워드 · 고원(W) 결과 158파일이 커밋과 다르다** — QQQ · TQQQ 워크포워드 각 71(요약 5 + 윈도우 66), 고원 16. 커밋된 W 결과가 낡았다: 워크포워드 마지막 갱신 `20d6458`(2026-10-17) · 고원 `96c935f`(2026-10-10)이고, 그 뒤 시세 갱신(QQQ `c8d7007` 2026-10-31 · 합성 TQQQ `771be2d` 2026-11-01)과 고원 대상에서 UGL · UBT 를 뺀 변경(`123ccf5`)이 반영되지 않았다. 예: TQQQ 워크포워드 OOS CAGR 평균 26.92 → 25.81 · 이어 붙인 CAGR 21.79 → 20.97, 고원 QQQ sell=0.05 CAGR 9.61 → 9.43 · UGL · UBT 행 없어짐. 코드 탓이 아니다. 계획서대로 새 W 결과를 scratchpad `baseline_fresh_20261104/` 에 보관하고 추적 파일을 사본으로 되돌렸다(`git status --short storage` 0건). 기준선 전제가 W 에서 깨져 대조 방법 조정(D3)을 사용자에게 묻고 멈춘다
- 2026-11-04 14:15: 사용자 「추천대로」 — **D3 = A**: 이번 커밋에서 W 결과는 낡은 채 두고, 마지막 검증에서 다시 돌린 W 결과를 보관본과 대조한 뒤 추적 파일을 커밋 상태로 되돌린다. W 결과 갱신은 경량화 커밋 뒤 따로. DoD · 마지막 Validation 의 대조 문구를 이 결정대로 고쳤다
- 2026-11-04 14:29: Phase 1 ~ 3 코드 정리. 계획서에 없던 것 셋 — ① 상품 표 `DAILY_COMPARISON_TARGETS` 의 넷째 칸(일별 비교 CSV 경로)과 그 경로 상수 둘을 지웠다: 합성 생성은 그 칸을 버리고(`_`) 지운 기능의 잔여물이라서다. 표의 이름은 그대로 ② `TQQQ_RESULTS_DIR` · `DISPLAY_DATE` 도 사용처가 0 이 되어 지웠다 ③ `simulate` 의 0 이하 가격 가드는 남기고 이유 주석만 고쳤다(일별 비교 CSV 를 가리키던 이유가 사라짐). `src` 전체 고아 검사에서 새로 생긴 고아는 `DISPLAY_DATE` 하나였다 — 나머지는 같은 파일 안에서 쓰이는 이름이다. 관련 테스트 실행: Phase 1 212 passed · Phase 2 198 passed · Phase 3 81 passed. 옮긴 시작일 대조는 조건을 끄면 새 테스트가 실패함을 확인하고 되돌렸다
- 2026-11-04 14:37: Phase 4 · 5 — 시세 38개 · 결과 폴더 14개 · 1999 년 이전 금리 파일 · 완료 계획서 5개 삭제(`storage/stock` 9개 남음). 문서: COMMANDS(지운 명령 · 순서 블록 ③ – ④ · 대용 절), README, 루트 `CLAUDE.md`(가격 반올림 표의 저장 스크립트 목록 한 줄 — 디렉터리 구조는 그대로 맞음), 하위 `CLAUDE.md` 여섯, MEMORY(V2 · 스플릿 세 항목 삭제 · 두 문장 고침), DEFERRED(두 항목 삭제 · 한 문장 고침), 보고서(재현 절 M.12 · N.7 · N.14 · N.20 머리에 `ee6d23d` 안내, O.14 · §49.4 · D.9 안내문, D.9 두 행, 「지우기로 했다」 → 「지웠다」). 배분 규칙 설명에 「등록 실험 없이 엔진 기능으로 남겼다」를 덧붙였다(Q2 ⓐ 의 이유)
- 2026-11-04 14:51: 마지막 Phase — 러너 다섯 재실행: 합성 시세 · 단일 · 포트폴리오 결과가 커밋과 바이트 단위로 같다(`M` 0건, Q-2-2XS `summary.json` 포함), W 158파일이 Phase 0 보관본과 바이트 단위로 같다 → W 를 사본으로 커밋 상태로 되돌림(`storage` 의 `M` 0 · `D` 113). `AppTest` 단일 대시보드 예외 0 · 탭 11, 포트폴리오 대시보드 예외 0 · 탭 5. black 3파일 줄바꿈. `/code-review xhigh` 1회차 15건 — 버그 0. 품질 검증 705 passed. `HANDOFF.md` 삭제
- 2026-11-04 14:51: 거른 리뷰 지적 15건 (모두 기준 3 「그 외」 — 옮기지 않음, 사용자에게 Done 보고 표로 냄)
  1. `test_portfolio_configs.py` 의 「시작일 하한을 쓰는 등록 실험 없음」 단언이 D1 = A 로 남긴 기능의 사용을 막는다 — 테스트가 지금 등록 상태를 고정하는 계약이고, 쓰려면 그 단언을 함께 고치면 된다(막는 쪽)
  2. `HANDOFF.md` 미삭제 — 마지막 Phase 의 할 일로 처리함(삭제)
  3. 고원 · 워크포워드 결과가 낡았다(UGL · UBT 행) — D3 = A 로 받아들임, 경량화 커밋 뒤 따로
  4. softplus a · b 의 근거(스프레드 랩 docstring · 튜닝 CSV)를 보고서로 옮기지 않았다 — 문서. 근거 자리는 `ee6d23d`
  5. `src/qbt/CLAUDE.md` 의 일별 비교 CSV 두 줄 — DoD 로 고침
  6. `engine_common.py` · `engines/__init__.py` 의 docstring 이 스플릿 · 손절 · 지정가를 설명하고 매개변수 이름이 `price_raw` 다 — 주석 · 이름
  7. `portfolio_types.py` 의 `min_start_date` docstring 이 지운 보완 그리드를 가리킨다 — 주석
  8. 테스트 docstring 다섯(`test_tqqq_simulation_core.py` · `test_tqqq_simulation_cost_model.py` · `test_stock_downloader.py` · `test_allocators.py` · `test_dashboard_charts.py`)과 `stock_downloader.py` 머리말이 지운 기능을 근거로 든다 — 주석
  9. `build_trade_markers` 의 여러 진입일 API 를 하나로 되돌리지 않았다 — 정리(계획서가 둔 것)
  10. 단일 엔진의 `sell_price_raw` 우회 구조 — 정리(계획서가 둔 것, 결과 동일 확인)
  11. `DAILY_COMPARISON_TARGETS` 이름 — 계획서 비목표
  12. 상수 3계층 규칙상 한 파일만 쓰는 TQQQ 상수들(`DEFAULT_PRE_LISTING_EXPENSE_RATIO` 등)을 옮기지 않았다 — 정리
  13. COMMANDS ① 루프가 이제 `DEFAULT_TICKERS` 와 같은 일을 한다 — 문서 간소화
  14. 옮긴 `_to_date` 대신 `pd.Timestamp(...).date()` 관용 — 정리
  15. 철회 실험 이름 테스트가 「모르는 이름은 ValueError」 계약과 겹친다 — 테스트 정리

---
