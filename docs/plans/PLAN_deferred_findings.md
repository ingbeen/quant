# Implementation Plan: 미룬 지적 8건 처리 — 포트폴리오 시작일 · 합성 낡음 · 월 키 · 워크포워드 보유중 마커 · 테스트 공백 셋

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-06 08:12
**마지막 업데이트**: 2026-11-06 18:10
**관련 범위**: backtest(포트폴리오 엔진 · 워크포워드), utils(시세 로딩 · 대용 비교 테스트), tqqq(월별 데이터), scripts/backtest(포트폴리오 · 워크포워드 러너, 워크포워드 대시보드), tests, docs
**관련 문서**: CLAUDE.md, docs/MEMORY.md, docs/CLAUDE.md, docs/COMMANDS.md, README.md, scripts/CLAUDE.md, src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/utils/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, tests/CLAUDE.md, docs/DEFERRED_FINDINGS.md, docs/research/합성_시세_연장.md

---

## 1) 목표(Goal)

`docs/DEFERRED_FINDINGS.md` 의 항목을 아래 번호로 부른다(파일 순서). 5번(구성 의존 파일 지우기 호출의 테스트)은 사용자가 버렸다(2026-11-06) — 파일에서 이미 지웠다.

- [x] 목표 1 (항목 1): 시작일 없는 등록 실험이 함께 시작할 날을 「데이터 시작일 중 가장 늦은 날 이후, 그 실험들 모두의 거래일인 첫날」로 정한다. 시작일을 정한 실험(`min_start_date`)은 그날이 그 실험의 거래일인지 **실행 전에** 대조한다 — 어느 실험의 결과도 쓰기 전에 멈춘다. `run_with_start_check` 의 오류 문구에서 같은 기간 비교를 깨뜨리는 권고를 뺀다
- [x] 목표 2 (항목 2①): `--experiment` 로 일부만 돌릴 때, 대상이 아닌 등록 실험의 저장된 `summary.json` 시작일이 정한 날과 다르면 아무것도 쓰기 전에 「전체를 돌리세요」로 멈춘다 (사용자 결정 2026-11-06 「멈춘다」). 항목 2② 는 이 대조로 갈음한다 — 러너가 대상만으로 날을 정하게 잘못 바뀌면 실제 실행 때 저장 결과와 갈려 멈춘다 (사용자 결정 2026-11-06)
- [x] 목표 3 (항목 3): 시세를 읽을 때(`load_stock_data`) 합성 파일 `{T}_synthetic_max.csv` 의 끝날이 옆의 실물 `{T}_max.csv` 끝날보다 이르면 「합성 생성을 돌리세요」로 멈춘다 (사용자 결정 2026-11-06 「load_stock_data 한 곳」)
- [x] 목표 4 (항목 4): 설정 짝 테스트가 배분 규칙 매매법의 자산도 자산 id 와 매매 파일 이름을 견준다
- [x] 목표 5 (항목 6): 워크포워드 러너가 윈도우마다 `wNN_summary.json` 에 그 윈도우 상세 실행의 미청산 포지션(`open_position`, 보유 중일 때만)을 저장하고, 대시보드가 윈도우 차트에 「Buy (보유중)」을 그린다 (사용자 결정 2026-11-06 「윈도우마다 wNN_summary.json」)
- [x] 목표 6 (항목 7): 마지막 날 체결 테스트가 「N-1일 신호 → N일 체결」을 실제로 만든다
- [x] 목표 7 (항목 8): 월별 금리 · 운용비율 딕셔너리를 만들 때 월 키가 `yyyy-mm`(`MONTH_KEY_PATTERN`)인지 검사한다
- [x] 목표 8 (항목 9): 비교에서 빠진 날 세기의 첫날 · 끝날 포함을 테스트로 고정한다
- [x] 목표 9: 기존 결과 파일이 그대로다 — 합성 생성 · 러너 넷을 다시 돌려 기존 파일 diff 0, 늘어난 것은 워크포워드 윈도우 요약 파일뿐

## 2) 비목표(Non-Goals)

- 항목 5 — 사용자가 버렸다 (2026-11-06). 재현 결과 낡은 `ledger.csv` 는 대시보드를 KeyError 로 멈추고, 에러 없이 남는 것은 자산 선택 목록의 낡은 시그널뿐이다
- 항목 2② 의 러너 한 줄을 지키는 테스트 — 테스트가 scripts 를 불러오거나 src 가 등록 목록을 읽어야 하는데 둘 다 전례 0건이다. 목표 2 의 실행 전 대조로 갈음한다
- 포트폴리오 저장(`_save_portfolio_results`)을 src 로 옮기기 — 항목 5 를 버려 필요 없다
- 저장된 결과의 끝날 · 구성 변경 대조 — 목표 2 는 시작일만 본다
- 인자 없는 `download_data.py` 실행 — 결과 변화의 원인을 가를 수 없게 된다(루트 `CLAUDE.md`). 시세는 받지 않는다
- 대시보드 실행 — 사용자가 한다. 검증은 일회성 `AppTest`(사용자 결정 2026-11-01)
- git 조작 — 커밋은 사용자가 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 요청(2026-11-06): 「DEFERRED_FINDINGS.md 리스트 전부 해결해줘」 → 항목마다 재현 · 추천 표 → 「추천대로 진행」
- 글자 규칙이 막거나 되돌릴 수 없는 결과에 물리는 설계 — 해당 없음. 목표 3 의 파일 이름 짝은 이 저장소가 만드는 파일의 고정 이름(`src/qbt/CLAUDE.md` 「시세 파일 이름」)이고 열린 입력이 아니다. 지금 합성 8종(QQQ · SPY · TQQQ · QLD · SSO · UPRO · TLT · GLD)이 모두 짝 실물 파일을 갖는다

### 착수 전 재현 (2026-11-06, scratchpad — 저장소 파일은 읽기만)

스크립트는 `/private/tmp/claude-501/-Users-yubeen-Workspace-quant/eb2c2a1f-823d-483b-8acc-8263faee7d53/scratchpad/` 의 `repro1.py` · `repro1b.py` · `repro4.py` · `repro6.py` · `repro7.py` · `repro8.py` · `repro9.py`, 변형 사본 `mut/`(임시).

| 항목 | 재현 |
|---|---|
| 1 | 금 합성(`GLD_synthetic_max.csv`)에 1986-07-17 ~ 2004-01-02 미국 거래일 4,408일 중 110일(첫날 1986-09-26, 끝날 2004-01-02)이 없다. Q-2 를 1986-12-31 로 돌리면 `ValueError: [portfolio_q2] 실제 시작일 1987-01-02 가 정한 시작일 1986-12-31 와 다릅니다`. 러너는 실험마다 실행 → 대조 → 저장을 차례로 해 앞 실험이 먼저 저장된다. 지금 데이터 시작일: QQQ 보유 1985-10-01 · D-1 · Q-2 · Q-2-2XS 1986-07-16 → 넷 모두 1986-07-16, 그날은 넷 모두의 거래일 |
| 2① | 러너에 다른 실험의 `summary.json` 을 읽는 코드 0곳. 저장 결과 넷의 시작일 1986-07-16 · 끝날 2026-10-29 |
| 2② | scripts 를 불러오는 테스트 0개 |
| 3 | 합성 8종의 끝날이 모두 짝 실물과 같다(UPRO 는 둘 다 2026-11-03, 나머지 2026-10-29). 낡음을 보는 코드 0곳. 같은 tmp 폴더에 같은 티커의 합성 · 실물을 함께 두는 테스트 0개 |
| 4 | 테스트 판정을 그대로 돌리며 `qld`→TQQQ 합성, `gld`→TLT 합성으로 짝지은 배분 규칙 실험을 더해도 결과 `[]` |
| 6 | 워크포워드 윈도우 72개(QQQ · TQQQ × 두 모드 × 18) 중 60개가 마지막 행 `position > 0` |
| 7 | 엔진이 마지막 날 예약 주문을 버리게 바꾼 사본에서 관련 테스트 66개 통과. 지금 테스트 데이터의 포지션 `[0]*8 + [94, 94]`(8일째 돌파 → 9일째 체결). 항목의 데이터는 원래 엔진 `[0]*9 + [90]`, 바꾼 엔진 `[0]*10` |
| 8 | `2026-3` 줄에 새 운용비율 0.0080 을 넣어도 에러 없음 — 2026-03 · 04 · 09 조회가 모두 직전 값 0.0095. 지금 파일 키: 금리 868 / 868 · 운용비율 193 / 193 이 모양이 맞다 |
| 9 | `>=`→`>`, `<=`→`<` 사본에서 `TestCountUnmatchedDays` 3건 통과. 첫날 · 끝날이 한쪽에만 있는 입력은 원래 (1, 1), 바꾼 사본 (0, 0) |

### 설계

**목표 1 · 2 — 포트폴리오 시작일** (`src/qbt/backtest/engines/portfolio_engine.py`, 러너 `scripts/backtest/run_portfolio_backtest.py`)

- `compute_portfolio_trading_dates(config) -> list[date]` 를 더한다 — 공통 기간 · 워밍업 뒤의 거래일(엔진이 도는 날과 같다: 엔진은 워밍업 뒤 날짜 중 `start_date` 이상을 쓴다). `compute_portfolio_effective_start_date` 는 그 첫날을 돌려준다(동작 그대로, 호출처 18곳 유지)
- `planned_start_dates(configs, trading_dates)` — 둘째 인자를 「실험 이름 → 데이터 시작일」에서 「실험 이름 → 거래일 목록」으로 바꾼다(호출처: 러너 1 · 테스트 4)
  - 시작일 없는 실험: 바닥 = 그 실험들 첫 거래일 중 가장 늦은 날, 함께 시작할 날 = 그 실험들 모두의 거래일 중 바닥 이상인 첫날. 없으면 ValueError
  - 시작일 정한 실험: 그날이 그 실험의 거래일이 아니면 ValueError(실험 이름 · 정한 날 · 데이터 첫날) — 러너의 `late_starts` 검사(데이터가 정한 날보다 늦게 시작)를 대신한다. 그 검사는 대상 실험만 봤고 이 검사는 등록 실험 전부를 본다 — 지금 시작일 정한 등록 실험은 0개(`TestWithdrawnSupplementConfigs.test_no_config_has_start_date_floor`)
  - 거래일 목록이 빠진 실험이 있으면 ValueError (시작일 정한 실험도 대조하려면 필요하다)
- `require_saved_starts_match(configs, start_dates)` 를 더한다 — 각 실험의 `result_dir / SUMMARY_FILENAME` 이 있으면 `portfolio_summary.start_date` 를 정한 날과 견주고, 다른 것을 모아 ValueError(「하나만 돌리면 결과 폴더에 기간이 다른 결과가 섞입니다 — --experiment 없이 전체를 돌리세요」). 파일이 없으면 건너뛴다(그 실험은 대시보드에도 없다). `start_dates` 에 그 실험이 없으면 RuntimeError(내부 불변조건 위반) — 러너가 대상만으로 날을 정하게 잘못 바뀌어도 쓰기 전에 멈춘다
- `run_with_start_check` 의 오류 문구: 「이 구성의 시세가 모두 있는 날을 설정의 min_start_date 로 정하세요」를 빼고, 정한 날이 이 구성의 거래일이 아니라는 사실(워밍업 안 · 그날 시세가 빈 자산)만 알린다. 러너 경로에서는 위 대조 뒤라 닿지 않는다
- 러너: 등록 실험 전부의 거래일 → `planned_start_dates` → 대상이 아닌 등록 실험으로 `require_saved_starts_match` → 실험별 실행. 전체 실행이면 대상이 아닌 실험이 없다

**목표 3 — 합성 낡음** (`src/qbt/utils/data_loader.py` `load_stock_data`)

- 읽은 경로 이름이 `_synthetic_max.csv` 로 끝나고 같은 폴더에 `{T}_max.csv` 가 있으면, 실물의 `Date` 열만 읽어 끝날을 견준다. 합성 끝날 < 실물 끝날이면 ValueError(두 파일 · 두 끝날 · 「합성 생성(generate_synthetic.py)을 돌린 뒤 다시 실행하세요」)
- 생성 스크립트는 합성을 새로 저장한 뒤에 읽으므로 걸리지 않는다 — 1배 합성 저장(`_generate_proxy_synthetics`) → 레버리지 합성이 1배 합성을 읽음(`save_leveraged_synthetics`) → 펀드 대조가 QLD · SSO 합성을 읽음(`_save_fund_comparisons`). 실물 끝날이 합성보다 늦을 정상 경우는 없다 — 1배 · 레버리지 합성 모두 이음매 뒤가 실물 행 그대로다(`require_rows_from_seam_equal_actual`)

**목표 5 — 워크포워드 윈도우 보유중 마커**

- `src/qbt/backtest/walkforward.py` `WindowDetailData` 에 `open_position: OpenPositionDict | None` — `run_backtest` 요약의 `open_position`(엔진이 이미 만든다)
- `scripts/backtest/run_walkforward.py` `_save_window_detail_csvs` → `_save_window_details`(CSV 셋 + 요약 하나를 쓰므로, 호출처 1) — 윈도우마다 `wfo_window_filename(idx, SUMMARY_FILENAME)` 에 `{"open_position": {...}}`(보유 중) 또는 `{}` 를 쓴다. 단일 백테스트 `summary.json` 의 `open_position` 과 같은 키 · 자릿수
- `scripts/backtest/app_walkforward.py` `_render_window_detail` — 그 파일을 읽어 `build_trade_markers(trades_df, open_entry_dates=…)`. 대시보드는 도메인 계산을 하지 않는다(에쿼티 `position` 에서 진입일을 계산하지 않는다)

**목표 4 · 6 · 7 · 8** — 원 항목의 「막으려면」 그대로. 목표 7 의 구현은 `src/qbt/tqqq/data_loader.py` `_create_monthly_data_dict` 에서 `re.fullmatch(MONTH_KEY_PATTERN, month_key)`.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)
- `docs/MEMORY.md`
- `docs/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`
- `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`
- `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 「처리」

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 목표 1 ~ 9 충족
- [x] 회귀/신규 테스트 추가 — 보강한 검사마다 변형으로 실패를 본 기록이 진행 로그에 있다
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 있음(포트폴리오 줄 · 「시세를 다시 받은 뒤」), `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` 변경 있음, README 변경 없음(기능 소개 수준이라 닿지 않음), 루트 `CLAUDE.md` · `tests/CLAUDE.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (목표 1 · 2 의 정책과 금 합성 110일 근거를 `docs/research/합성_시세_연장.md` 결정 10 에)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/engines/portfolio_engine.py` — `compute_portfolio_trading_dates` · `planned_start_dates` · `require_saved_starts_match` · `run_with_start_check` 문구
- `scripts/backtest/run_portfolio_backtest.py` — 날 정하기 · 실행 전 대조
- `src/qbt/utils/data_loader.py` — `load_stock_data` 의 합성 낡음 검사
- `src/qbt/tqqq/data_loader.py` — `_create_monthly_data_dict` 의 월 키 검사
- `src/qbt/backtest/walkforward.py` — `WindowDetailData.open_position`
- `scripts/backtest/run_walkforward.py` — 윈도우 요약 저장
- `scripts/backtest/app_walkforward.py` — 윈도우 차트의 보유중 마커
- `tests/qbt/test_portfolio_backtest_scenarios.py` · `test_data_loader.py` · `test_tqqq_data_loader.py` · `test_walkforward_schedule.py` · `test_buffer_zone_execution_rules.py` · `test_proxy_comparison.py` · `test_portfolio_configs.py`
- `docs/COMMANDS.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `docs/research/합성_시세_연장.md` · `docs/DEFERRED_FINDINGS.md`
- `docs/COMMANDS.md`: 변경 있음 — 실행 명령 · CLI 옵션은 그대로이고, 포트폴리오 `--experiment` 가 멈추는 조건과 「③ 을 건너뛰면 러너가 멈춘다」를 적는다
- README.md: 변경 없음

### 데이터/결과 영향

- 기존 결과 파일: 바뀌지 않아야 한다 — 함께 시작할 날 1986-07-16 이 넷 모두의 거래일이라 그대로이고, 나머지는 검사 · 저장 추가뿐이다. 합성 생성 · 단일 · 고원 · 포트폴리오 · 워크포워드를 다시 돌려 `git status` · `git diff --stat` 으로 기존 파일 diff 0 을 본다
- 새 결과 파일: `storage/results/backtest/buffer_zone_{qqq,tqqq}/wfo_windows_{dynamic,fully_fixed}/wNN_summary.json` 72개(그중 `open_position` 있는 것 60개 기대)

## 6) 단계별 계획(Phases)

### Phase 1 — 테스트만 보강: 항목 7 · 9 · 4 (그린 유지, 변형 확인)

**작업 내용**:

- [x] 항목 7: `test_last_day_pending_execution` 데이터를 종가 `[100]*8 + [107, 112]` · 시가 `[100]*8 + [105, 110]` · `ma_5` `[100]*8 + [103, 106]` 로 바꾸고, N-1일(인덱스 8) position == 0 · N일(인덱스 9) position > 0 을 단언한다. 주석의 「9일째 시가 존재 · 8일째 돌파」를 데이터에 맞춘다
- [x] 항목 9: `TestCountUnmatchedDays` 에 실물 첫날이 대용에 없고 이른 끝날(대용 끝)이 실물에 없는 입력 → (1, 1) 테스트를 더한다
- [x] 항목 4: `TestQSeriesConfigs` 에 배분 규칙 매매법 자산마다 매매 파일이 `{ASSET_ID}_synthetic_max.csv` 인지 보는 테스트를 더한다

**Validation**:

- [x] 변형 넷 — 바꿀 파일의 사본을 세션 스크래치에 뜨고 `PYTHONDONTWRITEBYTECODE=1` 로 돌린다. ① 엔진 4-1 앞에 마지막 날 예약 주문을 버리는 줄 → 항목 7 테스트 FAILED ② `dates >= start` → `>` → 항목 9 새 테스트 FAILED ③ `dates <= end` → `<` → 같은 테스트 FAILED ④ `PORTFOLIO_CONFIGS` 에 잘못 짝지은 배분 규칙 실험을 임시로 더함 → 항목 4 새 테스트 FAILED. 되돌린 뒤 사본과 `diff` 0
- [x] 세 테스트 파일 통과 (`pytest` 파일 지정) — 73 passed

---

### Phase 2 — 월 키 모양 검사: 항목 8 (레드 → 그린)

**작업 내용**:

- [x] 테스트 먼저: `create_ffr_dict` · `create_expense_dict` 에 `2026-3` 키가 든 표 → ValueError(match 「2026-3」) — 실패를 본다
- [x] 구현: `_create_monthly_data_dict` 에서 키를 `MONTH_KEY_PATTERN` 으로 검사, 오류 문구에 그 키와 고칠 모양(예: 2026-03)을 담는다. docstring Raises 갱신

**Validation**:

- [x] 구현 전 새 테스트 FAILED, 구현 뒤 `test_tqqq_*.py` 전부 통과 — 140 passed
- [x] 실제 두 파일로 `create_ffr_dict` · `create_expense_dict` 가 통과한다(키 868 · 193)

---

### Phase 3 — 합성 낡음 검사: 항목 3 (레드 → 그린)

**작업 내용**:

- [x] 테스트 먼저 (`test_data_loader.py`): tmp 에 `X_synthetic_max.csv`(끝 D5) · `X_max.csv`(끝 D6) → ValueError / 끝날 같음 → 읽힘 / 실물 파일 없음 → 읽힘(경계) — 첫째의 실패를 본다
- [x] 구현: `load_stock_data` 에 검사, docstring Raises 갱신

**Validation**:

- [x] 구현 전 새 테스트 FAILED, 구현 뒤 `test_data_loader.py` 통과 — 17 passed
- [x] `generate_synthetic.py` · `run_single_backtest.py` · `run_param_plateau_all.py` 다시 실행 — 성공, 기존 파일 diff 0
- [x] 세션 스크래치에 실행 위치를 꾸민다(`storage/stock` 은 저장소 파일 링크, `QQQ_max.csv` 만 행 하나를 더한 사본) — 거기서 `run_single_backtest.py --strategy buffer_zone_qqq` 가 저장 전에 멈춘다. 저장소의 시세 · 결과 파일은 건드리지 않는다(원본 시세 불변 — `~/.claude/rules/python.md`)

---

### Phase 4 — 포트폴리오 시작일: 항목 1 · 2① (레드 → 그린)

**작업 내용**:

- [x] 테스트 먼저 (`test_portfolio_backtest_scenarios.py`): `TestPlannedStartDates` 의 4건을 거래일 목록 인자로 바꾸고, ① 바닥 날이 한 실험의 거래일이 아니면 그 뒤 모두의 거래일인 첫날 ② 시작일 정한 실험의 날이 그 실험의 거래일이 아니면 ValueError ③ 바닥 이상 공통 거래일이 없으면 ValueError(경계) 를 더한다. `compute_portfolio_trading_dates` 의 첫날 = `compute_portfolio_effective_start_date` 1건. `require_saved_starts_match` — 같음 → 통과 / 다름 → ValueError(실험 이름) / 파일 없음 → 통과 3건
- [x] 구현: 위 「설계」 목표 1 · 2
- [x] 러너 갱신: `late_starts` 블록을 지우고(대조는 `planned_start_dates` 가 한다) 날 정하기 → 대상 아닌 실험 대조 → 실행

**Validation**:

- [x] 구현 전 새 테스트 FAILED, 구현 뒤 `test_portfolio_*.py` 통과
- [x] 변형 셋 — ① 함께 시작할 날을 바닥 날 그대로 ② 시작일 정한 실험의 대조를 뺌 ③ 저장 결과 대조가 늘 통과 → 각 새 테스트 FAILED, 되돌린 뒤 사본 대조
- [x] 러너 전체 실행 — 성공, 결과 diff 0. `--experiment portfolio_qqq_bh` — 성공, 시작일 1986-07-16, 결과 diff 0
- [x] 저장 결과 변형 — 세션 스크래치에 실행 위치를 꾸민다(`storage/stock` 은 링크, `storage/results/portfolio` 는 사본, 그중 `portfolio_d1/summary.json` 시작일만 바꿈) — 거기서 `--experiment portfolio_qqq_bh` → 쓰기 전에 멈춤(그 사본의 `portfolio_qqq_bh` 폴더가 바뀌지 않음). 저장소 결과 파일은 건드리지 않는다

---

### Phase 5 — 워크포워드 윈도우 보유중 마커: 항목 6 (레드 → 그린)

**작업 내용**:

- [x] 테스트 먼저 (`test_walkforward_schedule.py`): `run_window_detail_backtests` — 윈도우 끝에 보유 중이면 `open_position` 의 진입일이 그 윈도우 거래의 마지막 매수일, 끝에 보유하지 않으면 None
- [x] 구현: `WindowDetailData.open_position`, 러너 `_save_window_details` 의 `wNN_summary.json`, 대시보드 마커

**Validation**:

- [x] 구현 전 새 테스트 FAILED, 구현 뒤 `test_walkforward_*.py` 통과 — 59 passed
- [x] `run_walkforward.py` 다시 실행(약 6분) — 기존 파일 diff 0, 새 `wNN_summary.json` 72개 중 `open_position` 있는 것 60개(윈도우 에쿼티 마지막 행 `position > 0` 수와 같다)이고 그 진입일이 윈도우 에쿼티에서 마지막으로 0 → 양수가 된 날과 같다
- [x] `AppTest` 로 `app_walkforward.py` 예외 0건

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서: `src/qbt/backtest/CLAUDE.md` 도메인 규칙 8 「시작일」 · `scripts/CLAUDE.md` 「스크립트 지도」(포트폴리오 러너 · 합성 생성을 건너뛰면 멈춘다) · `src/qbt/CLAUDE.md` 「CSV 데이터 로딩」 · `src/qbt/utils/CLAUDE.md` `data_loader.py` · `src/qbt/tqqq/CLAUDE.md` 「3. 데이터 요구사항」(월 키 모양도 ValueError) · `docs/COMMANDS.md`(포트폴리오 줄 · 「시세를 다시 받은 뒤」 ③) · `docs/research/합성_시세_연장.md` 결정 10(함께 시작할 날의 거래일 규칙 · 금 합성 110일 · 일부 실행의 저장 결과 대조). README 변경 없음
- [x] `docs/DEFERRED_FINDINGS.md` — 고친 항목(1 · 2 · 3 · 4 · 6 · 7 · 8 · 9)을 지운다. 이 계획서가 고치지 못한 리뷰 지적은 거르는 기준으로 걸러 옮긴다
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 13건 — 버그 3 [무거움 0 · 가벼움 3] · 그 외 10 · 조치: 닿는 버그 0. 그 외 중 사용자 문구 3(전역 「사용자 중심」 — 무엇을 해야 하는지 없음)과 문서 2(이번 변경과 어긋남 — DoD 문서 정확성)를 고침, 버그 1(일부 실행 뒤 끝날 섞임)을 미룬 지적으로, 나머지는 진행 로그에 기준과 함께)
- [x] `/code-review xhigh` **2회차** (발견 3건 — 버그 2 [무거움 0 · 가벼움 2] · 그 외 1 · 조치: 사용자 지시 「반복하지 말고 전부 해결」로 1회차에 남긴 지적과 함께 고침 — 둔 것 둘(⑦ · ⑨)과 그 이유는 진행 로그. `/code-review` 는 사용 한도로 돌지 않아 `review.md` 의 맥락 없는 `general-purpose` 서브에이전트에 diff 와 같은 기준을 주어 돌림)
- [x] 수정분 검증 (수정 8건 · 생략 — 사용자 지시 2026-11-06 「코드 리뷰시 반복되게 수정하고 리뷰하고 이런식으로 진행하지말고」. 대신 바뀐 검사마다 변형 확인 5건 · 포트폴리오 · 워크포워드 재실행 · 대시보드 AppTest · 품질 검증으로 확인)
- [x] `poetry run python validate_project.py` (passed=879, failed=0, skipped=0) — Ruff · PyRight 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 미룬 지적 일괄 해결
2. 백테스트 / 미룬 지적 처리 — 포트폴리오 기간 대조 · 합성 낡음 검사 · 월 키 검사 · 워크포워드 보유중 마커와 테스트 공백 보강
3. 백테스트 / 포트폴리오 일부 실행의 기간 섞임 차단과 함께 시작할 날의 공통 거래일 보정
4. 백테스트 / 에러 없이 틀리던 입력 차단 — 낡은 합성 시세, 모양이 틀린 월 키, 저장 결과와 기간이 다른 일부 실행
5. 백테스트 / 미룬 지적 처리(항목 5 는 낡은 장부가 대시보드를 멈춰 기각)와 윈도우별 요약 파일 추가

## 7) 리스크(Risks)

- **`load_stock_data` 는 모든 시세 읽기가 지나는 공용 함수다** — 호출처 src 7 · scripts 15곳(생성 스크립트 포함). 검사는 이름이 `_synthetic_max.csv` 이고 옆에 실물이 있을 때만 걸린다. 완화: Phase 3 에서 생성 스크립트와 러너를 다시 돌려 성공 · diff 0 을 보고, 전체 테스트로 tmp 파일 이름 충돌이 없는지 본다(재현 표 3 — 같은 티커 짝을 두는 테스트 0개)
- **실물 파일을 하나만 다시 받아도 그 합성을 읽는 모든 러너가 멈춘다** — 의도한 동작이다(COMMANDS 순서 ③ 을 지키면 생기지 않는다). 생성 스크립트 자체는 합성을 먼저 다시 만들어 멈추지 않는다
- **`planned_start_dates` 의 인자 계약이 바뀐다** — 호출처 러너 1 · 테스트 4. 시작일 정한 실험도 거래일 목록이 있어야 한다. 완화: 러너는 등록 실험 전부의 목록을 넘긴다
- **시작일 정한 실험의 대조가 대상 실험에서 등록 실험 전부로 넓어진다** — 잘못된 `min_start_date` 를 가진 다른 실험이 하나만 돌리는 실행도 막는다. 지금 그런 등록 실험은 0개라 닿지 않고, 막히면 설정 오류를 알리는 쪽이다
- **저장 결과 대조가 「전체 실행」을 요구한다** — 늦게 시작하는 실험을 새로 등록하고 그것만 돌리면 멈춘다. 전체 실행은 1분 이내이고 사용자가 「멈춘다」를 골랐다(2026-11-06)
- **워크포워드 재실행 약 6분** — 백그라운드로 돌린다. 기존 결과가 바뀌면(시세는 받지 않았다) 원인을 분리해 사용자에게 보고한다
- **결과 파일 덮어쓰기** — `storage/results/` 는 git 추적. 착수 전 작업 트리는 `docs/` 두 파일 말고 깨끗하다
- **변형 확인의 되돌리기** — 변형 전 사본을 뜨고, 되돌린 뒤 `diff` · `cmp` 로 대조한다. `.pyc` 함정은 `PYTHONDONTWRITEBYTECODE=1`

## 8) 메모(Notes)

- 사용자 결정 (2026-11-06): 항목 5 버림, 항목 2② 는 2① 로 갈음, 2① 은 「멈춘다」, 항목 3 은 `load_stock_data` 한 곳, 항목 6 은 윈도우마다 `wNN_summary.json` — 「추천대로 진행」
- 사용자 지시 (2026-11-06 17:3x): 「이어서 진행하되, 코드 리뷰시 반복되게 수정하고 리뷰하고 이런식으로 진행하지말고 전부 해결하는 것을 목표로 하자」 — 2회차 뒤 남은 지적을 한꺼번에 고치고 재리뷰 · 수정분 검증을 돌리지 않는다. 그에 따라 설계가 바뀐 곳: 저장 결과 대조를 `require_saved_starts_match`(시작일만)에서 `plan_run_start_dates`(날 정하기 + 돌리지 않는 실험의 저장 기간 — 시작일 · 끝날 — 대조를 한 함수로)로 바꿨다. 끝날 대조는 비목표였으나 1회차 지적 ③ 을 「전부 해결」로 고쳤다 — 새 시세 뒤 일부만 돌리면 멈춘다. `summary.json` 의 기간 키는 `KEY_PORTFOLIO_SUMMARY` · `KEY_START_DATE` · `KEY_END_DATE` 로 러너(쓰기)와 엔진(읽기)이 같이 쓴다. 대시보드는 윈도우 요약 파일이 없으면 경고하고 마커 없이 그린다
- `docs/DEFERRED_FINDINGS.md` 의 고칠 항목 출처 칸에 「고치는 중: PLAN_deferred_findings」를 붙였다(2026-11-06). Done 때 그 항목들을 지운다

### 진행 로그 (KST)

- 2026-11-06 08:12: 계획서 작성. 착수 전 재현은 Context 표
- 2026-11-06 08:20: 자체 검증 — 1회차 개선 셋(변형 실행을 스크래치 실행 위치로 옮겨 원본 시세 · 결과 파일을 건드리지 않음, `src/qbt/tqqq/CLAUDE.md` 를 문서 목록에, 저장 결과 대조의 정한 날 누락을 RuntimeError 로), 2 ~ 4회차(다른 로직 영향 — `load_stock_data` 호출처 · 병렬 워커 · 생성 스크립트 읽기 순서 / 규약 형식 / 더 단순한 안) 개선 없음 → 멈춤
- 2026-11-06 08:27: 사용자 승인 「진행」 → In Progress
- 2026-11-06 08:31: Phase 1 — 테스트 셋 보강 뒤 73 passed. 변형 넷(스크립트 `/private/tmp/claude-501/-Users-yubeen-Workspace-quant/eb2c2a1f-823d-483b-8acc-8263faee7d53/scratchpad/phase1/mutate.py`, `PYTHONDONTWRITEBYTECODE=1`, 바꿀 때마다 `src` 의 `__pycache__` 지움): ① 엔진 마지막 날 예약 주문 버림 → `FAILED ...::test_last_day_pending_execution` (1 failed, 13 passed) ② `dates >= start` → `>` → `FAILED ...::test_window_includes_first_and_last_day` (1 failed, 3 passed) ③ `dates <= end` → `<` → 같은 테스트 FAILED (1 failed, 3 passed) ④ `qld`→TQQQ 합성 · `gld`→TLT 합성 배분 규칙 실험을 `PORTFOLIO_CONFIGS` 에 임시 추가 → `FAILED ...::test_each_allocator_asset_trades_its_asset` (1 failed, 6 passed). 넷 모두 되돌린 파일이 사본과 바이트까지 같고(`filecmp`), `git status` 에 src 변경 없음
- 2026-11-06 08:33: Phase 2 — 새 테스트(금리 · 운용비율 × `2026-3` · `2026-13`) 구현 전 4 failed, 41 passed → 구현 뒤 `test_tqqq_*.py` 140 passed. 실제 파일 금리 868 · 운용비율 193 키 통과
- 2026-11-06 08:35: Phase 3 — 새 테스트 구현 전 `FAILED ...::test_synthetic_ending_before_actual_raises` (1 failed, 16 passed) → 구현 뒤 17 passed. 합성 이름을 쓰는 테스트 파일 8개 175 passed(tmp 이름 충돌 없음). `generate_synthetic.py` 4.3초 · `run_single_backtest.py` 6.8초 · `run_param_plateau_all.py` 50.9초 모두 exit 0, `git status --short storage/` 빈 출력. 스크래치 실행 위치(`.../scratchpad/run_stale/`, `QQQ_max.csv` 사본에 2026-10-30 한 행)에서 `run_single_backtest.py --strategy buffer_zone_qqq` → exit 1, `ValueError: 합성 시세 QQQ_synthetic_max.csv 의 끝날 2026-10-29 가 실물 QQQ_max.csv 의 끝날 2026-10-30 보다 이릅니다 …`, 그 위치의 결과 파일 0개. 저장소 `storage/` diff 없음
- 2026-11-06 08:38: Phase 4 — 새 테스트 구현 전 수집 단계 `ImportError`(새 함수 없음) → 구현 뒤 `test_portfolio_backtest_scenarios.py` · `test_portfolio_methods.py` · `test_portfolio_configs.py` 149 passed. 변형 셋(`.../scratchpad/phase4/mutate.py`): ① `shared = min(candidates)` → `shared = floor` → `FAILED ...::test_shared_start_moves_to_first_day_common_to_all` (1 failed, 7 passed) ② `if not_trading:` → `if False and not_trading:` → `FAILED ...::test_pinned_date_not_trading_day_raises[not_trading_day]` · `[before_data_start]` (2 failed, 6 passed) ③ `if saved_start != planned:` → `if False:` → `FAILED ...::test_mismatching_saved_result_raises` (1 failed, 2 passed). 셋 모두 되돌린 파일이 사본과 같다. 러너 전체 실행 exit 0(시작할 날 넷 모두 1986-07-16) · `--experiment portfolio_qqq_bh` exit 0(start_date=1986-07-16, 데이터 기준 1985-10-01), 두 번 모두 `storage/` diff 없음. 스크래치 실행 위치(`.../scratchpad/run_saved/`, 결과 사본의 `portfolio_d1` 시작일만 1986-07-17)에서 `--experiment portfolio_qqq_bh` → exit 1, `ValueError: 이번에 돌리지 않는 실험의 저장 결과가 정한 날과 다른 날에 시작합니다: portfolio_d1(저장 1986-07-17, 정한 날 1986-07-16) …`, 사본의 `portfolio_qqq_bh` 는 `diff -r` 0
- 2026-11-06 08:46: Phase 5 — 새 테스트 구현 전 `AttributeError: 'WindowDetailData' object has no attribute 'open_position'` 2 failed, 8 passed → 구현 뒤 `test_walkforward_*.py` 59 passed. `run_walkforward.py` 백그라운드 exit 0(08:39 ~ 08:45), 기존 파일 diff 0(`git status --short storage/` 에 수정 없음), 새 파일 72개 모두 `wNN_summary.json`. 대조 스크립트(`.../scratchpad/verify6.py`): 윈도우 72 · 요약 72 · `open_position` 60 · 에쿼티 마지막 행 보유 60 · 어긋남 0(진입일 = 에쿼티에서 마지막으로 0 → 양수가 된 날, 주수 = 마지막 행 주수). `AppTest`(`.../scratchpad/apptest_wfo.py`): 첫 화면 예외 0, 기본 지표 QQQ Dynamic 의 윈도우 18개(보유 15 · 비보유 W4 · W9 · W11)를 모두 골라 그려 예외 0
- 2026-11-06 08:46: 마지막 Phase 문서 — `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `docs/COMMANDS.md` · `docs/research/합성_시세_연장.md`(결정 10 · 머리말 마지막 업데이트). README 변경 없음
- 2026-11-06 08:59: `/code-review xhigh` 1회차 13건 — 갈래와 조치:
  - 버그 · 가벼움 ① 윈도우 요약 파일이 없으면 대시보드 윈도우 차트가 FileNotFoundError(`app_walkforward.py`) — 고치지 않음, 기준 2(막는 쪽): 요약 파일 없는 결과는 이번 변경 전 결과이고, 다른 윈도우 파일이 없을 때와 같은 동작이다
  - 버그 · 가벼움 ② `require_saved_starts_match` 가 러너가 쓰는 `summary.json` 키를 그대로 읽어, 키가 바뀌거나 파일이 깨지면 KeyError · JSONDecodeError — 고치지 않음, 기준 1(키를 바꾸는 새 코드가 있어야 함) · 기준 2(멈춘다). 지금 저장 결과 넷 모두 그 키가 있다
  - 버그 · 가벼움 ③ 저장 결과 대조가 시작일만 봐서, 새 시세 뒤 하나만 돌리면 끝날이 다른 결과가 섞인다 — 비목표(끝날 대조)로 둔 것이라 고치지 않고 미룬 지적으로 옮김(Done 때)
  - 그 외 ④ 정한 날 대조 문구의 「데이터 첫날」이 실제로는 워밍업 뒤 첫 거래일 ⑤ `run_with_start_check` 문구에 할 일 없음 ⑥ 「함께 시작할 날이 없습니다」 문구에 할 일 없음 — 셋 다 고침(전역 「사용자 중심」 규칙: 무엇을 해야 하는지). 같은 모양(이번 diff 의 새 사용자 문구) 전수: 6곳 중 월 키 문구도 할 일을 덧붙임, 나머지 둘(합성 낡음 · 저장 결과 대조)은 이미 할 일이 있음
  - 그 외 ⑦ `compute_portfolio_effective_start_date` 의 운영 호출처 0(테스트 6곳만) — 고치지 않음(기준 3, 테스트가 계약으로 쓰는 공개 함수)
  - 그 외 ⑧ `scripts/CLAUDE.md` 의 「어긋나도 에러가 없다」가 새 문장과 어긋남(연구 문서 결정 11 도) — 고침(DoD 문서 정확성)
  - 그 외 ⑨ 합성 읽기마다 실물 `Date` 열을 한 번 더 읽음(성능) — 고치지 않음(기준 3)
  - 그 외 ⑩ 러너의 `open_position` 직렬화가 단일 러너와 중복 · docstring 본문의 「CSV 포맷팅」 — 고치지 않음(기준 3)
  - 그 외 ⑪ 테스트의 `_stock_df_from_closes` 가 `helpers` 와 중복 — 고치지 않음(기준 3)
  - 그 외 ⑫ 공개 `create_ffr_dict` · `create_expense_dict` 의 Raises 에 월 키가 없음 — 고침(DoD 문서 정확성)
  - 그 외 ⑬ 버린 항목 5 의 기각 사유가 계획서에만 있음 — 처리 이력은 git 이 말한다(`review.md` 「처리」). 이 계획서를 함께 커밋하면 비목표 절의 사유가 git 이력에 남고, 커밋 메시지 후보 5번에도 요약을 넣었다
  - 수정 뒤 `test_portfolio_backtest_scenarios.py` · `test_tqqq_data_loader.py` 95 passed
- 2026-11-06 17:35 ~ 17:45: `/code-review xhigh` 2회차 두 번 시도 — 둘 다 「You've hit your 5-hour limit」(리뷰 하위 실행이 돌지 않음). `review.md` 의 다른 방식(맥락 없는 `general-purpose` 서브에이전트에 diff · 의도 · 1회차 지적 목록을 주고 같은 무게 기준)으로 2회차를 돌렸다
- 2026-11-06 17:57: 2회차 3건 — ① 러너가 새 대조를 부르는 줄 · 윈도우 요약 쓰기를 지키는 테스트가 없음(가벼움) ② 잘린 · 옛 형식 `summary.json` 에서 KeyError · JSONDecodeError 가 안내 없이 남(가벼움) ③ 연구 문서 결정 10 의 「금이 든 실험만 다음 날 시작한다」가 지금 동작처럼 읽힘(문구). 리뷰어가 바뀐 테스트 7개 파일 + 이웃 6개를 돌려 통과, pyright 0 · ruff 깨끗, 72 요약 파일 대조 0 어긋남, 110일 숫자 재계산 일치를 보고
- 2026-11-06 18:00: 한꺼번에 고침(사용자 지시) — 1회차 ①(요약 파일 없으면 경고 · 마커 없이) ②+2회차 ②(기간 키 상수 · 읽기 실패를 파일 이름과 할 일을 담은 ValueError 로 — src 전례 `portfolio_data.py:85` · `gold_proxy.py:90` 의 잡아서 다시 던지기) ③(끝날 대조) ⑩(직렬화 중복 → `dict(detail.open_position)`, docstring 본문) ⑪(테스트가 `helpers.make_rising_stock_df` · `make_rise_then_fall_stock_df` 를 씀) · 2회차 ①(날 정하기와 대조를 `plan_run_start_dates` 한 함수로 — 러너가 대조를 빼거나 쓰기 뒤로 옮길 수 없다. 러너가 인자를 잘못 넘기는 것까지는 scripts 를 테스트하지 않는 관용상 남는다 — 버린 항목 5 와 같은 갈래) ③(조건문으로 고쳐 씀). 1회차 ⑦ `compute_portfolio_effective_start_date` 는 둔다 — 연구 문서 9장 재현 절차(6.11)가 부른다. ⑨ 성능은 잼: `QQQ_synthetic_max.csv` 읽기 13.8 ms 중 실물 끝날 검사 2.5 ms — 둔다. ⑬ 항목 5 기각 사유는 이 계획서 비목표 절(커밋하면 git 이력에 남음)과 커밋 메시지 후보 5번
- 2026-11-06 18:00: 일괄 수정의 변형 확인(`.../scratchpad/phase_fix/mutate.py` · `mutate_wfo.py`): ① 끝날 대조 뺌(`saved != planned` → `saved[0] != planned[0]`) → `FAILED ...::test_mismatching_saved_period_raises[end_extended]` ② 돌릴 실험 건너뛰기 뺌 → `FAILED ...::test_running_all_skips_saved_check` ③ 대상만으로 날 정함 → 4 FAILED(`test_single_target_starts_on_date_of_all_registered` 외 셋) ④ 읽기 실패 안내 뺌(`except KeyError` 만) → `FAILED ...::test_unreadable_saved_result_raises` ⑤ `open_position=None` → `FAILED ...::test_open_position_when_holding_at_window_end`. 다섯 모두 되돌린 파일이 사본과 같다. `test_portfolio_backtest_scenarios.py` 54 passed · `test_walkforward_schedule.py` 10 passed
- 2026-11-06 18:02: 포트폴리오 러너 전체 exit 0 · `--experiment portfolio_q2_2xs` exit 0(start_date=1986-07-16), 두 번 모두 `storage/results/portfolio` diff 없음. 스크래치 실행 위치(`.../scratchpad/run_saved2/`, 결과 사본의 `portfolio_d1` 끝날만 2026-10-28)에서 `--experiment portfolio_q2_2xs` → exit 1, `ValueError: 이번에 돌리지 않는 실험의 저장 결과가 지금 정한 기간과 다릅니다: portfolio_d1(저장 1986-07-16 ~ 2026-10-28, 지금 1986-07-16 ~ 2026-10-29) …`, 사본의 `portfolio_q2_2xs` `diff -r` 0
- 2026-11-06 18:07: 워크포워드 다시 실행(단순화한 저장 코드) exit 0 — 기존 storage 파일 수정 0, 새 파일 72개 그대로, 대조 스크립트 윈도우 72 · 요약 72 · `open_position` 60 · 에쿼티 보유 60 · 어긋남 0. `AppTest`: 첫 화면 예외 0, 윈도우 18개 예외 0. 스크래치 실행 위치(`.../scratchpad/run_app/`, 결과 사본에서 `w00_summary.json` 만 지움)에서 예외 0, 경고 「윈도우 요약 파일(w00_summary.json)이 없어 … run_walkforward.py 를 다시 돌리세요」
- 2026-11-06 18:08: `poetry run black .` · `validate_project.py` — passed=879, failed=0, skipped=0. `docs/DEFERRED_FINDINGS.md` 의 고친 8개 항목을 지웠고 새로 옮길 지적은 없다. 거른 지적: ① 러너가 `plan_run_start_dates` 에 인자를 잘못 넘기는 것 · 윈도우 요약 쓰기 줄을 지키는 테스트 없음 — 기준 3(막는 결함이 가벼운 검사 보강, scripts 를 테스트하지 않는 관용 — 버린 항목 5 와 같은 갈래) ② `compute_portfolio_effective_start_date` 의 운영 호출처 0 — 기준 3(연구 문서 9장 재현 절차가 부름) ③ 합성 읽기마다 실물 `Date` 열을 한 번 더 읽음 — 기준 3(성능, 2.5 ms)
