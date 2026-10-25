# Implementation Plan: 안내 문서 · 주석 실오류 정리 — 시세 갱신 순서 블록과 화면 문구 · 테스트 주석

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-24 08:45
**마지막 업데이트**: 2026-10-25 11:06
**관련 범위**: 문서(`docs/COMMANDS.md` · `scripts/CLAUDE.md` · `docs/AUDIT_REPORT.md`), 설정 주석(`pytest.ini`), scripts(대시보드 둘의 화면 문구 · 생성 스크립트 둘의 docstring), tests(주석 · docstring · 이름 둘 — 코드 리뷰 뒤 셋 · 유지일 테스트 하나), src(일별 비교 히스토그램 문자열 — 사용자 결정 2026-10-24), `tests/CLAUDE.md`(코드 리뷰 2회차)
**관련 문서**: `docs/AUDIT_REPORT.md`(19절 12단계 1 · 13-B · 13-C · 13-T · 15-T · 결정 13 · 3-5), `docs/COMMANDS.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

---

## 1) 목표(Goal)

- [x] 목표 1: `docs/COMMANDS.md` 에 「시세를 다시 받은 뒤 다시 돌리는 순서」 블록 하나를 두고(13-B D4 · 결정 13 · 3-5), 흩어진 「다시 받으면 다시 실행」 5곳을 그 블록으로 대신한다
- [x] 목표 2: `docs/COMMANDS.md` 의 실오류를 고친다 — 커버리지 명령 설명(D1), 러너 선택지 출처(D2), 대시보드 선행 번호 · 틀린 화면 설명(D3), 틀린 선행 조건(D4)
- [x] 목표 3: 화면 문구 실오류 둘을 고친다 — 일별 비교 대시보드(C9), 고원 대시보드의 기준 자산 라벨(C10)
- [x] 목표 4: 테스트 주석 · docstring 의 실오류(13-T)와 과거 상태 · 이력 문구(15-T)를 지금 코드에 맞게 고친다. 같은 모양으로 찾은 자리도 함께
- [x] 목표 5: `pytest.ini` 의 파일 패턴 주석(D17 남은 몫)
- [x] 목표 6: 실행 동작 · 결과 파일 변화 0 — 테스트 AST 는 docstring 을 빼면 이름 둘만 다르고, 앱 둘은 바꾼 문자열만 다르다 (2026-10-24 조정: 코드 리뷰 · 사용자 결정으로 이름 셋 · 기대 문자열 둘 · 유지일 테스트 하나, src 화면 문자열 셋 — 결과 파일 변화 0 은 그대로)

## 2) 비목표(Non-Goals)

- **결정 번호 토큰(D○○)** — 19절 12단계 1 이 4번(16-B, 설계서 처리)과 함께 하라고 정했다. src · scripts · tests 모두
- **12단계 2 몫** — 안내 문서 경량화(18-B · 18-D), D5 · D7 · D8 · D9 · D15, 14절의 가변 수치 · 목록(COMMANDS 의 실측 소요 시간 · 「2개월」 등), 15절 「안내 문서」. 이 계획서가 새로 쓰는 줄에는 숫자를 복사하지 않고 상수 이름을 쓴다
- **12단계 3 몫** — 연구 문서(13-A · 18-C · 14-R · 15-R)
- **`scripts/CLAUDE.md` 의 러너 선택지 포인터**(`STRATEGY_NAMES` · `PORTFOLIO_CONFIGS` · 고원 실험 목록) — D8(12단계 2)의 「인자를 받는 스크립트는 `--help` 가 정본」으로 함께 정리한다. 이 계획서는 COMMANDS 의 네 곳만
- **COMMANDS 의 대체 시세 선행 목록**(「선행 1: … VGTSX … "GC=F"」 등) — 처음 받을 때의 안내라 남긴다. 블록과 겹치는 것은 18-B(12단계 2)에서 본다
- **테스트가 지키지 않는 계약을 새 테스트로 메우는 일** — 예: `record_equity` 계약 테스트, 「final_capital = cash + position × 종가」 역산. 지금 주석이 거짓으로 약속하는 문장만 지운다
- **`test_logger` 「기존 로거」 · `test_portfolio_planning` 「기존 보유 자산」 · `test_portfolio_execution` 「기존 position」 · `test_tqqq_data_loader` 「기존 딕셔너리 값」 · `test_ma_type_policy` 의 EMA** — 이력이 아니라 그 자리의 뜻(이미 있는 것 · SMA 고정 정책의 비교 대상)이다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 12단계 1(문서)이다. 직전 계획서는 `PLAN_tests_cleanup.md`(Done, `29bb6dd`). 사용자 결정(2026-10-23): 남은 단계는 19절 그대로 — 단계를 묶지 않는다
- 12단계 1 에 배정된 항목을 HEAD `29bb6dd` 에서 다시 쟀다(보고서 줄 번호는 `40011ad` 기준이라 내용으로 다시 찾았다). 이미 처리된 것: D11 · D12 · D13 · D14 · D16, D17 의 마커, 13-C C2 – C8, C10 의 세 앱 자리, 15절 「코드 주석 · docstring」(D○○ 제외), 13-T 넷, 15-T 일곱 자리(11단계 tests 가 지운 테스트 · 헬퍼와 함께). **새로 확인한 것**: 13-T `test_tqqq_data_loader.py` 「날짜 파싱 및 정렬 ↔ 날짜 파싱을 하지 않음」은 이미 한 문장으로 고쳐져 있다(5-6 로더 통합, 2026-10-14) — 보고서에 그렇게 적는다
- 남은 것

**안내 문서** (`docs/COMMANDS.md` 줄은 HEAD 기준)

| 항목 | 지금 | 바꾸는 것 |
|---|---|---|
| D1 | `:149` 「커버리지 포함 전체 검증」 — `validate_project.py --cov` 는 Ruff · PyRight 를 끄고 테스트 + 커버리지만 돈다(`validate_project.py:165-166`). 같은 명령이 「커버리지」 절 `:191-192` 에 한 번 더 | 설명을 「테스트 + 커버리지만 (Ruff · PyRight 는 돌지 않는다)」로, 「커버리지」 절의 중복 두 줄 삭제. 절 자체와 HTML 리포트 명령은 남긴다 — `tests/CLAUDE.md` 「커버리지」가 이 절을 가리킨다 |
| D2 | 선택지 출처를 문서가 적는다: 단일 `:33-35`, 포트폴리오 `:47`, 워크포워드 `:71-72`(「`buffer_zone.py::CONFIGS`」 — 틀림, 실제는 `STRATEGY_NAMES` 둘), 고원 `:78`(목록 복사) | 네 곳 모두 「선택지는 `--help`」. 네 러너의 `--help` 가 argparse 선택지를 그대로 보인다(확인함) |
| D3 | 워크포워드 대시보드 「(선행: 3)」 · 고원 대시보드 「(선행: 4)」 — 워크포워드는 4, 고원은 5. 「시각화:」 주석 셋 — 워크포워드 줄의 「QQQ vs TQQQ」 · 「WFE 분포」는 화면에 없다 | 선행 번호를 4 · 5 로. 「시각화:」 세 줄 삭제(화면 구성은 앱 docstring 이 정본) |
| D4 | 포트폴리오 「(선행: 1, TQQQ 합성 데이터 필요)」 — 등록 실험 다섯 중 TQQQ 합성을 읽는 것 0, 채택 조합이 읽는 것은 대용 시계열 생성 산출물(`VEA` · `BIL` · `PDBC` · `VXUS` 이어 붙인 판). 「합성 TQQQ 데이터 생성 (선택)」 — 단일 백테스트(`buffer_zone_tqqq` · `buy_and_hold_tqqq`)와 워크포워드(`buffer_zone_tqqq`)가 읽는다. 실행 순서가 어디에도 없어 합성 파일이 반년 낡았다(2-1) | 포트폴리오 선행을 「대용 시계열 생성」으로, 단일 · 워크포워드에 「TQQQ 합성」 선행, 합성 줄의 「(선택)」 대신 읽는 곳. 새 절 「시세를 다시 받은 뒤 다시 돌리는 순서」(설계 결정 1) |
| D4 의 5곳 | 「다시 받으면 다시 실행」 — COMMANDS `:219` · `:234`, `scripts/CLAUDE.md:105` 끝 문장, `generate_proxy_series.py:9` · `generate_long_proxy_series.py:13` docstring | 다섯 줄 삭제. `scripts/CLAUDE.md` 「데이터 수집」에 블록을 가리키는 한 줄. COMMANDS `:233` 「… 2개월 넘게 뒤까지 있으면 멈춘다」도 블록 ② 가 상수 이름으로 말하므로 삭제 |
| 결정 13 | 금리 · 운용비율 파일의 출처 · 갱신 방법이 문서 0건 | 블록 ② 에 세 줄(출처 · 단위 · 적용 시점, 파일 형식) |
| 3-5 | HAA · 로테이션 원본(IWM · VWO · VNQ · IEF · TIP · EWY)이 COMMANDS 0건 | 블록 ① 이 원본을 「`storage/stock/` 의 `*_max.csv` 중 생성 파일이 아닌 것 전부」로 정의해 함께 풀린다(추적 43개 = 원본 33 + 생성 10) |
| D17 | `pytest.ini:8` 「(test_*.py 또는 *_test.py)」 — 설정은 `test_*.py` 뿐 | 괄호 삭제 |

**화면 문구** (scripts)

| 항목 | 지금 | 바꾸는 것 |
|---|---|---|
| C9 | `app_daily_comparison.py:111-112` 「일일수익률의 차이(실제 - 시뮬레이션) … 평균이 0에 가깝고」 — 차트는 절대차(`COL_DAILY_RETURN_ABS_DIFF`)라 평균이 0 일 수 없다. `:120-124` 「누적수익률 차이」 — 차트는 누적배수 로그차이(`COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED`, 차트 제목도 그렇다) | 「일일수익률 절대차이 \|실제 − 시뮬레이션\| … 0 쪽에 몰릴수록」, 섹션 3 제목 · 첫 줄 · 주석을 「누적배수 로그차이」로. 양수 · 음수 설명은 산식(`100 × ln(M_sim / M_real)`)과 맞아 그대로 |
| C10 | `app_parameter_stability.py:131` · `:134` 고원 칠하기 라벨 「고원 구간 (80%…)」 — 여섯 자산 선 위에 QQQ 행으로만 칠하는데 라벨에 기준 자산이 없다 | 라벨 앞에 「QQQ」 |

**테스트 주석 · docstring** (13-T · 15-T, 「찾음」은 같은 모양으로 이번에 찾은 자리)

| 파일 | 지금 | 바꾸는 것 |
|---|---|---|
| `test_buffer_zone.py` | 머리말 「`create_runner()`」(없는 이름) · 「8개 자산」(`CONFIGS` 7) · 4P 숫자 복사, `:71` 「8개 설정을 포함하는지」(단언은 비어 있지 않음), `:255-256` 「sources 딕셔너리 제거 후 … (리포트 3-12, 확정 방침 5-5)」 | `runners.create_buffer_zone_runner()` · 개수 삭제 · `FIXED_4P_*`, 「비어 있지 않은지」, 「BufferStrategyParams 만 반환한다」 |
| `test_analysis.py` | `:867` 「저장 계층 → 계산 계층 방향이 자연스럽다」(단언은 csv_export 가 analysis 를 import 하지 않음 — 반대), `:870` 「fresh import」(평범한 import), `:885` 「과거에는 … 무음 반환되었으나」 | 정책 문장을 단언과 같은 방향으로, 「import 한 모듈」, 이력 줄 삭제 |
| `test_engine_common.py` | `:3` 머리말이 이 파일에 없는 `record_equity` 테스트를 적는다, `:104` 「(리포트 2-1 통일)」 | 머리말에서 그 이름 삭제, 괄호 삭제 |
| `test_backtest_engine.py` | `TestParamsScheduleWhile`, `:106-107` 「현재 `if` 로직에서는 … 실패하고, `while` 루프로 변경 후에야 통과한다」 | 이름 `TestParamsScheduleDataGap`, 두 줄을 「갭 동안 지난 전환 날짜를 모두 적용한다 — 하나만 적용하면 1/5 전략이 남는다」로 |
| `test_walkforward_verdict.py` | `:83` 「과거 사고가 재현된 것이다」, `:748-749` 「과거에는 이 표가 정적 텍스트여서 …」 | 머리말을 가리키는 한 줄, 「정적 텍스트면 데이터를 갱신해도 … 그대로 남는다」 한 줄 |
| `test_strategy_interface.py` | 「새 인터페이스」 5곳(`:3` · `:47` · `:52` · `:345` · `:350`) | 토큰 삭제(머리말은 「계약:」) |
| `test_buffer_zone_execution_rules.py` | `:123` 「버그 재현: range(1, len(df)) 루프로 첫 날 누락」, `:162` · `:170` 「(정책 변경)」, `:172` 「정책 변경:」, `:524` Then 「final_capital == cash + position x last_close」와 `:559-563` 그 검증의 주석 처리 코드(「구현 후 활성화」 — 에쿼티 기록에 cash 가 없다), `:579-580` 「상태머신 방식으로 구현됨 · 이 테스트는 이제 통과해야 함」 | 「첫 날도 기록한다」 계약 문장, 토큰 삭제, 「정책:」, 검증하지 않는 Then 줄과 주석 처리 코드 삭제, 두 줄 삭제 |
| `test_walkforward_schedule.py` | `:28` · `:31` · `:115` · `:118` 「EMA」, `:115` 「현재 구현은 OOS에서 EMA 리셋 발생」(지금은 전체 시세에 계산한 뒤 자른다), `:100` 「프로덕션 기본 MA 유형」(찾음 — 유형 선택이 없다) | 「이동평균」, 「run_walkforward 가 이동평균을 계산한다」, 「프로덕션 이동평균 함수」 |
| `test_buffer_zone_run.py` | `:89` 「EMA 자동 계산 가능」 | 「이동평균 자동 계산 가능」 |
| `test_portfolio_state_log.py` (찾음) | `:36` 「EMA 수렴」 | 「이동평균 수렴」 |
| `test_portfolio_backtest_scenarios.py` | `:778` · `:819` 「기존 동작과 동일」, `:886` · `:889` · `:891` 「SMA, NaN 워밍업이 발생하는 유형」 · 「SMA 사용 시」 · 「SMA 타입 사용」(유형 선택이 없다) | 「자연 시작일을 쓴다」, 유형 표현 삭제 |
| `test_parameter_stability.py` | `:352` 「기존 find_plateau_range와 동일」 | 「필터 없는 find_plateau_range 와 같은」 |
| `test_csv_export.py` | `:12-13` 「여러 스크립트에 중복되어 있었으며, 공용 함수로 추출한 뒤」 | 「여러 러너가 이 공용 함수로 변환하므로」 |
| `test_portfolio_execution.py` | `test_signal_sell_still_full_sell`, `:181` 「여전히 … (변경 없음)」 | 이름 `test_signal_sell_is_full_sell`, 「신호 기반 매도는 전량 매도임을 검증」 |
| `test_portfolio_strategy_types.py` | `:23-26` 「always_invested 테스트 목적 … always_invested=True라면」 — 그 이름은 src 0건(지금은 `strategy_id="buy_and_hold"`) | 지금 쓰는 세 테스트의 뜻(「버퍼존은 신호가 없고 매수 후 보유는 산다」)으로 |
| `test_portfolio_configs.py` (찾음) | `:15` · `:120` · `:224` 「기존 실험」 | 「시작일 하한(`min_start_date`)이 없는 실험」 쪽 표현으로 |
| `test_portfolio_methods.py` (찾음) | `:319` 「(기존 결과 파일과 같다)」 | 괄호 삭제 |

### 설계 결정

1. **블록 「시세를 다시 받은 뒤 다시 돌리는 순서」** — 「데이터 다운로드 옵션」 절 앞에 둔다. 순서: ① 원본 시세(정의 + 받는 명령 — Notes 의 결정 대기) ② `storage/etc` 두 파일(출처 · 단위 · 적용 시점 · 형식 `DATE`=`yyyy-mm` · `VALUE`=비율 · 줄 끝 CRLF, 시세 끝이 파일 끝보다 `MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF` 를 넘게 뒤면 두 파일을 읽는 생성 셋 — ③ TQQQ 합성 · ④ 의 장기 대체 · ⑤ 일별 비교 — 이 멈춘다. ④ 의 대용 시계열 생성 · 비교는 두 파일을 읽지 않는다(코드로 확인)) ③ `generate_synthetic.py` ④ `generate_proxy_series.py` → `generate_long_proxy_series.py` → `generate_proxy_comparison.py` ⑤ `generate_daily_comparison.py` ⑥ 단일 → 워크포워드 → 고원 → 포트폴리오 → 보완 그리드 → 조합 그리드. 생성 단계마다 무엇이 읽는지 한 마디를 붙인다(③ 단일 · 워크포워드의 TQQQ 전략, ④ 포트폴리오 · 두 그리드). 결정 20(대체 판 재생성은 다음 시세 갱신 때 그리드와 함께)과 같은 순서다
2. **D3 의 선행 번호는 고친다** — 보고서 제안은 「순서 블록으로 대체」인데, 대시보드는 블록에 없고(블록은 다시 만드는 순서) 「어느 러너의 결과를 읽나」는 대시보드마다 다르므로 번호를 바로잡아 남긴다
3. **D1 의 「커버리지」 절은 남긴다** — `tests/CLAUDE.md` 가 그 절을 가리키고, HTML 리포트 명령은 거기에만 있다. 중복 두 줄만 지운다
4. **「다시 받으면 다시 실행」 안내는 COMMANDS 블록 한 곳** — 생성 스크립트 docstring 두 줄은 지우고 「선행:」 줄은 남긴다. 에이전트가 읽는 `scripts/CLAUDE.md` 에는 블록을 가리키는 한 줄만 둔다
5. **이름 둘을 바꾼다** — `TestParamsScheduleWhile` · `test_signal_sell_still_full_sell` 은 이름이 이력(「while 로 바꾼」 · 「여전히」)이다. 테스트 본문은 그대로

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)
- `docs/CLAUDE.md` · `scripts/CLAUDE.md` · `tests/CLAUDE.md` · `src/qbt/CLAUDE.md`
- 전역 `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 블록의 원본 정의가 추적 파일과 맞는다 — 블록의 받기 명령을 출력만 하게 돌린 티커 목록 = `git ls-files storage/stock` 에서 `*_synthetic_max.csv` · `*_proxy_max.csv` 를 뺀 목록(33개)
- [x] 테스트 파일 AST(모듈 · 클래스 · 함수 docstring 을 뺀 것)가 HEAD 와 같다 — 다른 것은 이름 셋(설계 결정 5 의 둘 + 코드 리뷰 1회차 ⑨ 하나) · 기대 문자열 둘(범례 이름 · 단언 메시지) · `test_hold_days_no_lookahead` 하나(사용자 결정, 변형 확인)뿐(2026-10-24 조정). 수집 테스트 수 907 그대로
- [x] 앱 둘의 AST 차이가 바꾼 문자열 상수뿐이고, 생성 스크립트 둘은 docstring 을 빼면 같다. 앱 둘을 Streamlit `AppTest` 로 그려 예외 0 · 새 문구 있음 · 옛 문구 없음
- [x] src 는 일별 비교 히스토그램의 화면 문자열 셋뿐(사용자 결정 2026-10-24 — 처음 기준 「src 변경 0」), `storage/` 변경 0
- [x] 위 표의 옛 문구가 대상 파일에 0건(진행 로그에 grep 결과)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md`(이 계획서의 대상 — 실행 명령 추가: 블록), `scripts/CLAUDE.md`(한 줄 교체 · 한 줄 추가), `tests/CLAUDE.md`(커버리지 포인터 — 코드 리뷰 2회차), `docs/AUDIT_REPORT.md`(처리 표시 · 19절 12단계 1), `docs/DEFERRED_FINDINGS.md`(항목 1 추가). `README.md` 변경 없음(실행 명령을 싣지 않는다)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다. 남길 「왜」는 살아있는 문서와 코드에 있다: 블록을 단계로 나누고 ② 를 산문으로 둔 이유 · 블록 안 주석을 두지 않는 이유 · 편집기로 붙이는 이유(COMMANDS 그 절), 유지일 테스트의 전제 단언 이유(그 테스트 주석), 원본 정의(COMMANDS ①). 처리 사실 · 검증 수치 · 사용자 결정은 점검 보고서 해당 행과 19절 12단계 1
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 옮긴 것 1(「마지막 날 체결 테스트가 전날 신호 → 마지막 날 체결을 만들지 못한다」 — 무거움, 재현함), 나머지는 거르는 기준에 들었다(진행 로그). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 문서: `docs/COMMANDS.md`, `scripts/CLAUDE.md`, `docs/AUDIT_REPORT.md`
- 설정: `pytest.ini`(주석 한 줄)
- scripts: `scripts/tqqq/app_daily_comparison.py`, `scripts/backtest/app_parameter_stability.py`(화면 문구), `scripts/data/generate_proxy_series.py`, `scripts/data/generate_long_proxy_series.py`(docstring 한 줄씩)
- 코드 리뷰 · 사용자 결정으로 더한 것(2026-10-24): `tests/CLAUDE.md`(커버리지 포인터), `src/qbt/tqqq/visualization.py`(히스토그램 범례 · hover · docstring), `tests/qbt/test_tqqq_visualization.py`(범례 기대값), `test_buffer_zone_execution_rules.py` 의 `test_hold_days_no_lookahead`(데이터 · 단언)
- tests: `test_{analysis, backtest_engine, buffer_zone, buffer_zone_execution_rules, buffer_zone_run, csv_export, engine_common, parameter_stability, portfolio_backtest_scenarios, portfolio_configs, portfolio_execution, portfolio_methods, portfolio_state_log, portfolio_strategy_types, strategy_interface, walkforward_schedule, walkforward_verdict}.py`(주석 · docstring, 이름 둘)
- `docs/COMMANDS.md`: 변경 있음 — 블록(원본 시세 받기 · 생성 · 러너 순서) 추가, 선행 조건 · 선택지 안내 수정. CLI 옵션 변경 없음
- `README.md`: 변경 없음

### 데이터/결과 영향

- 결과 파일 변화 0 — src 를 바꾸지 않고 러너 · 생성 스크립트를 돌리지 않는다(블록의 명령은 출력만 하게 바꿔 목록만 확인한다)
- 화면: 일별 비교 대시보드 섹션 2 · 3 의 설명 문구 · 섹션 3 제목, 고원 대시보드의 칠하기 라벨

## 6) 단계별 계획(Phases)

### Phase 1 — 안내 문서와 설정 주석

**작업 내용**:

- [x] `docs/COMMANDS.md` — 블록 추가(설계 결정 1), D1 · D2 · D3 · D4 의 줄, 「다시 실행」 두 줄과 「2개월 … 멈춘다」 한 줄 삭제
- [x] `scripts/CLAUDE.md` — `:105` 끝 문장 삭제, 「데이터 수집」에 블록을 가리키는 한 줄
- [x] `pytest.ini:8` 주석

**Validation**:

- [x] 블록 ① 의 반복문을 `poetry run …` 대신 `echo` 로 돌린 목록 = 추적 원본 33개(정렬 후 `diff` 0) — zsh · bash 둘 다
- [x] COMMANDS 에서 「TQQQ 합성 데이터 필요」 · 「(선택)」 · 「buffer_zone.py::CONFIGS 를 직접 참고」 · 「시각화:」 · 「다시 실행한다」 0건, `scripts/CLAUDE.md` 「다시 실행해야 한다」 0건

---

### Phase 2 — 화면 문구 · 생성 스크립트 docstring

**작업 내용**:

- [x] `app_daily_comparison.py` 섹션 2 · 3 문구(C9)
- [x] `app_parameter_stability.py` 라벨 둘(C10)
- [x] 생성 스크립트 둘의 docstring 한 줄씩

**Validation**:

- [x] AST 대조(HEAD ↔ 작업 트리) — 앱 둘은 바꾼 문자열 상수만(일별 비교 3 · 고원 2), 생성 스크립트 둘은 docstring 을 빼면 같다
- [x] `AppTest` 로 두 앱을 그려 예외 0, 새 문구 있음 · 옛 문구 없음(고원 앱은 탭 넷의 차트 사양에서 라벨 4개 모두 「QQQ 고원 구간」, 그중 저거래 제외 1)

---

### Phase 3 — 테스트 주석 · docstring

**작업 내용**:

- [x] 위 표의 테스트 파일 17개

**Validation**:

- [x] AST 대조(docstring 뺌) — 17개 중 15개 같음, 두 파일은 이름 하나씩(`ClassDef.name` · `FunctionDef.name`)만 다름
- [x] `pytest --collect-only -q` 수 907(HEAD `git archive` 사본도 907), 바뀐 테스트 ID 는 이름 둘의 것뿐

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] `docs/AUDIT_REPORT.md` — 처리 표시(D1 – D4 · D17 · 결정 13 · 3-5 · C9 · C10 · 13-T · 15-T), 13-T `test_tqqq_data_loader` 는 「이미 고쳐져 있었다」, 19절 12단계 1 줄
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 14건 — 버그 5 [무거움 3 · 가벼움 2] · 그 외 9 · 조치: 무거움 3 수정(블록이 실패 · 수동 단계에서 멈추지 않음 · 포트폴리오 · 그리드 선행의 원본 누락 · 금리 파일 끝 줄바꿈) · 가벼움 2 수정 · 그 외 6 수정 · 그 외 2 미반영, 진행 로그)
- [x] `/code-review xhigh` **2회차**(상한) (발견 10건 — 버그 4 [무거움 2 · 가벼움 2] · 그 외 6 · 조치: 가벼움 1 수정(커버리지 포인터) · 그 외 2 수정(유지일 테스트 docstring · 기록) · 무거움 2 미조치(같은 자리 두 번 1 · 계획서 범위 밖 1 — 사용자에게) · 가벼움 1 미조치(src — 사용자에게) · 그 외 4 미조치(같은 자리 두 번 1 — 사용자에게 · 3 기준 3), 진행 로그)
- [x] 수정분 검증 (수정 6 hunk · 발견 5건 — 무거움 0 · 조치: 고치지 않음(규칙) — 사용자에게, 진행 로그)
- [x] 수정분 검증 — 사용자 결정 뒤 수정 (수정 14 hunk · 발견 9건 — 무거움 1(diff 밖 · 앞부터) · 조치: 고치지 않음 — 무거움 1 은 재현해 미룬 지적으로, 가벼움 8 은 거름, 진행 로그)
- [x] `poetry run python validate_project.py` (passed=907, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 문서 / 시세 갱신 뒤 다시 돌리는 순서 블록 추가와 안내 문서 · 주석 실오류 정리
2. 문서 / 원본 33개 받기부터 결과 러너까지 실패에서 멈추는 순서 블록과 틀린 선행 조건 다섯 곳 수정
3. 문서 / 점검 보고서 12단계 1 처리 — COMMANDS 순서 블록 · 화면 문구 둘 · 테스트 이력 주석
4. 문서 / 합성 TQQQ 가 낡았던 원인인 실행 순서 누락 해소와 테스트 주석의 과거 이력 제거
5. 문서 / 안내 문서 · 화면 문구 · 테스트 주석 실오류 정리와 늘 통과하던 유지일 테스트 보강

## 7) 리스크(Risks)

- **블록의 순서가 틀리면 그대로 따른 사람이 낡은 결과를 만든다** — 생성 스크립트마다 읽는 파일을 코드에서 확인했다(Context 표 D4). 블록 명령은 지금 실행하지 않으므로 순서의 실제 검증은 다음 시세 갱신 때다. 완화: 각 생성 스크립트는 입력이 없거나 금리 · 운용비율 파일이 허용 개월 수보다 낡으면 멈춘다
- **원본 받기 반복문의 셸 차이** — zsh · bash 모두 같은 문법(`for` · `case` · `basename`)만 쓴다. `^SPGSCI` 처럼 특수 문자가 든 이름은 따옴표로 넘긴다. 출력만 하게 돌려 목록을 확인한다
- **테스트 이름 변경** — `-k` 로 그 이름을 부르는 안내 · 스크립트가 있으면 깨진다. 저장소 안 참조를 grep 해 0 이면 진행한다(문서 · 계획서 포함)

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 19절 12단계 1, 13-B D1 – D4 · D17, 결정 13 · 20, 3-5, 13-C C9 · C10, 13-T, 15-T
- 과거 결정: 결정 13 답(2026-10-09 — 금리 = FRED `FEDFUNDS` 월평균 ÷ 100, 기존 331개월 전부 일치 / 운용비율 = ProShares TQQQ Summary Prospectus 의 Net 비율을 설명서 날짜 다음 달부터, 파일과 일치), 결정 17(2026-10-15 · 10-22 처리), 결정 20(대체 판 재생성은 다음 시세 갱신 때), 남은 단계는 19절 그대로(2026-10-23)
- 사용자 결정(2026-10-24, 「추천대로」): 계획서 승인. 블록 ① 원본 받기는 (나) 정의 + 반복문 한 블록 — `download_data.py` 는 인자 없이는 `DEFAULT_TICKERS` 9개만 받아 나머지 24개를 빠뜨리는 것이 2-1 과 같은 모양의 낡음을 만든다. 버린 안 (가) 는 정의 한 줄만(보고서 제안, 사용자가 33개를 하나씩 받는다)
- 사용자 결정(2026-10-24, 코드 리뷰 2회차 보고에 대해 「언급 없는 것은 추천대로 · 3. 해당 내용 고치는데, 공수 많이 안 들어가면 진행」): ① zsh 블록 안 주석 → 블록 안 주석을 빼고 단계 이름은 산문으로 ② `test_analysis` 정책 문장 → 규칙 한 줄만 ③ 늘 통과하던 `test_hold_days_no_lookahead` → 고친다(공수 작음 — 데이터 한 줄 · 전제 단언 · 포지션 단언) ④ 같은 히스토그램의 src 문구 → 이 계획서에서 고치고 DoD 「src 변경 0」을 「src 는 화면 문자열뿐」으로 ⑤ 수정분 검증의 기록 불일치 · 유지일 스케줄 테스트 표현 → 고친다
- 이 계획서 다음은 12단계 2(19절)

### 진행 로그 (KST)

- 2026-10-24 08:15 ~ 08:40: 19절 12단계 1 항목을 HEAD `29bb6dd` 에서 다시 쟀다(Context). 네 러너의 `--help` 출력 확인, 생성 스크립트 · 러너가 읽는 시세 경로를 코드에서 확인, `storage/etc` 두 파일 형식(`DATE,VALUE` · CRLF) 확인, 미룬 지적 파일과 겹침 0
- 2026-10-24 08:45: 계획서 작성(Draft)
- 2026-10-24 08:50: 자체 검증 — ① 배정 대조(19절 12단계 1 의 항목을 보고서 행마다 처리 여부로 대조, 이미 처리된 것은 Context 첫 표 위에 적음 · 15절 「코드 주석」 scripts 의 「신규 섹션」 · `VERBATIM` 0건 확인) ② 블록 ② 의 문장 — 「③ – ⑤ 가 멈춘다」가 틀렸다(대용 시계열 생성 · 비교는 금리 · 운용비율을 읽지 않는다 — 스크립트 grep) → 「두 파일을 읽는 생성 셋」으로 고쳤다 ③ 이름 둘의 참조 — 저장소 안 실행 코드 · 안내 문서 0건, 점검 보고서 · 지난 계획서의 기록뿐 ④ 검증 수단 — AST 대조는 주석을 보지 않고 docstring 을 빼므로 테스트 동작 동일성을 직접 보이고, 화면 문구는 `AppTest`(Streamlit 1.63.0 에 있음)로 본다. 그 밖에 고칠 것 없음
- 2026-10-24 09:57: 승인 — 사용자 「추천대로」(Notes). Phase 1 착수
- 2026-10-24 09:58 ~ 10:00: Phase 1 — COMMANDS · `scripts/CLAUDE.md` · `pytest.ini`. 블록 ① 반복문을 문서에서 그대로 뽑아 `poetry run …` 만 `echo` 로 바꿔 zsh · bash 로 돌린 목록 33개 = `git ls-files storage/stock` 에서 생성 파일 10개를 뺀 33개(`diff` 0). 옛 문구 grep 0건(COMMANDS 6종 · `scripts/CLAUDE.md` 1종)
- 2026-10-24 10:00 ~ 10:02: Phase 2 — 스크래치 `step12a/ast_diff.py`(HEAD ↔ 작업 트리, docstring 을 뺀 AST 노드 대조): 일별 비교 앱은 문자열 상수 3 · 고원 앱은 2 만 다르고 생성 스크립트 둘은 같다. `step12a/apptest_check.py`(Streamlit `AppTest`): 두 앱 예외 0, 새 문구 있음 · 옛 문구 없음, 고원 라벨 4개(탭 넷) 모두 「QQQ 고원 구간」 · 그중 저거래 제외 1. 첫 실행은 차트 사양 JSON 의 한글 이스케이프로 라벨 0 이 나와 JSON 을 풀어 다시 셌다
- 2026-10-24 10:03 ~ 10:08: Phase 3 — 테스트 17개. AST 대조 15개 같음 · 2개는 이름 하나씩. 수집 ID — HEAD `git archive` 사본(`step12a/base`) 907 · 작업 트리 907, 다른 ID 는 이름 둘의 것뿐. 옛 문구 grep(31종) 남은 것 둘 — `test_walkforward_verdict.py:4` 머리말의 근거 사건(계획대로 남김) · `test_parameter_stability.py:77` 4P 숫자(그 테스트가 같은 숫자를 단언하는 정책 값 고정 테스트 — 결정 14 (나), 남김)
- 2026-10-24 10:08 ~ 10:10: 점검 보고서 처리 표시. 15-T 의 `test_portfolio_execution.py:262` 를 「찾음」으로 적었다가 보고서 「그 밖」 목록에 원래 있던 자리임을 보고 계획서 표 · 보고서 모두 바로잡았다. black 변경 0, src · `storage/` 변경 0
- 2026-10-24 10:10 ~ 10:21: `/code-review xhigh` 1회차 — 발견 14건. 고치기 전 사본은 두지 않았다(2회차가 이 수정을 본다)
  - 고친 것 — 버그 5: ① 무거움 — 블록이 붙여 넣는 한 덩어리라 손으로 하는 ② 를 건너뛰고 실패해도 결과 러너까지 돈다(낡은 입력으로 결과가 에러 없이 나간다) → 모양 「여러 단계를 한 블록에 두고 실패 · 수동 단계에서 멈추지 않는다」, diff 안 같은 모양 1곳(이 블록). ① · ② · ③ – ⑥ 으로 나눠 ② 는 산문 목록, ① 반복문은 실패하면 `[중단]` 한 줄과 함께 멈추고 ③ – ⑥ 은 `( set -e … )` 하위 셸. 변형: 가짜 `poetry` 함수로 EFA 받기 · `generate_long_proxy_series` · `run_walkforward` 를 실패시키면 zsh · bash 모두 그 자리에서 멈춘다(호출 4 · 3 · 7, 부모 셸 살아 있음), 실패 없으면 33 · 11 ② 무거움 — 포트폴리오 「선행: 1」(DEFAULT_TICKERS 만)이 HAA · 로테이션 원본을 빠뜨린다(끝 날짜가 낡은 파일 쪽으로 조용히 당겨진다) → 모양 「선행이 실제로 읽는 원본 일부만 적는다」, 같은 모양 2곳 더(3-1 · 3-2 그리드 줄 — diff 밖이지만 3-5 가 이 단계의 항목이라 함께). 세 줄 모두 블록 ① · ④ 를 가리킨다. 단일 · 워크포워드 · 고원은 읽는 원본이 모두 DEFAULT_TICKERS 라 그대로 ④ 무거움 — 「줄 끝 CRLF」 안내 ↔ 금리 파일 마지막 줄에 줄바꿈이 없다(셸 `>>` 로 붙이면 마지막 행과 이어져 다음 생성이 파싱 오류로 멈춘다) → 「편집기로 붙인다 — 파일 끝에 줄바꿈이 없으면 셸 `>>` 는 마지막 행에 이어 붙인다」(파일 상태와 무관한 문장). 운용비율 파일은 CRLF 로 끝난다 ③ 가벼움 — 「월별 파일을 다시 받으면 … 모두」가 월별 파일만 고친 경우에도 ① 재다운로드를 시킨다 → 「원본이면 ① 부터, 월별 파일만이면 ③ 부터」 ⑧ 가벼움 — 일별 비교 섹션 2 제목 · 주석이 「차이 분포」 그대로 → 「절대차이」(C9 와 같은 모양, 섹션 3 은 이미 고침)
  - 고친 것 — 그 외 6: ⑤ 검증하지 않는 「final_capital = cash + position x last_close」 인바리언트 줄(같은 docstring 의 Then 줄을 지운 근거와 같다) ⑥ `generate_long_proxy_series.py` docstring 에서 지운 줄이 금리 · 운용비율 의존의 유일한 표시였다 → 「선행:」 줄에 그 파일 ⑦ `test_analysis` 의 「순환 import 가능성」(analysis 가 csv_export 를 import 하지 않아 순환이 생길 수 없다) → 「계산 결과를 받아 저장용으로 바꾸기만 한다」 ⑨ `test_configs_list_has_expected_count` — 단언은 비어 있지 않음 → `test_configs_list_not_empty`(저장소 참조 0) ⑪ 점검 보고서 16-A · 18-A · 2-1 · 2-23 의 D4 상태 ⑬ 새로 고친 `#` 주석 셋이 간결체가 아니다(전역 주석 규칙) ⑭ 계획서 마지막 업데이트 · 진행 로그
  - 고치지 않은 것 — 그 외 2: ⑩ `TestForcedLiquidation` 이름(정책 주제의 이름이지 이력이 아니다) ⑫ 고원 앱의 「QQQ」 리터럴이 라벨 둘을 더해 다섯 곳(상수로 묶는 것은 리팩토링 — 이 계획서는 문자열만 바꾼다) — 기준 3(그 외)
  - 수정 뒤 재검증: AST — 21개 중 16개 같음, 다른 것은 앱 둘의 문자열(일별 비교 4 · 고원 2)과 이름 셋. 수집 907, 다른 ID 는 이름 셋의 것뿐. `AppTest` 통과(섹션 2 제목 포함). 반복문 목록 33개 그대로
- 2026-10-24 10:22 ~ 10:40: `/code-review xhigh` 2회차(상한) — 발견 10건. 고치기 전 사본은 스크래치 `step12a/r2_before/`
  - 사실 확인: ② zsh 의 블록 안 `#` 주석 — `zsh -f -i` 에 블록 모양을 넣으면 「command not found: #」 · 종료 127, 첫 명령이 돌지 않는다. bash `-i` 와 이 맥의 zsh(`interactivecomments` 켜짐 — oh-my-zsh)는 정상. ① `test_hold_days_no_lookahead` — 그 데이터를 `hold_days` 0 · 1 · 2 로 돌려 모두 거래 0(첫 유효일은 전날 밴드가 없고 그다음 날은 이미 밴드 위 — 돌파가 한 번도 없다). 미리 주문을 넣는 결함은 `test_hold_days_1_timeline`(돌파일 · 확정일 position 0, 체결일 > 0)이 잡을 것으로 보이나 변형으로 확인하지 않았다
  - 고친 것: ④ 가벼움 — `tests/CLAUDE.md` 「커버리지」 포인터가 이제 직접 `pytest --cov` 명령만 남은 절을 가리킨다(D1 이 그 절의 `--cov` 를 지웠다) → 「품질 검증」의 `--cov`(HTML 리포트는 「커버리지」). 모양 「내용을 바꾼 COMMANDS 절을 가리키는 포인터」 — 저장소 안 다른 절 포인터는 모두 그대로 맞다(grep) ⑧ 그 외 — 유지일 테스트의 새 줄이 목적 「최종 전략만 적용」과 어긋난다 → 「모두 처리해 마지막 것(1/10)의 전략이 남는다」 ⑨ 그 외 — 점검 보고서 기록(옛 클래스 이름 1 · D17 · C10 판정 칸 · 「이름 둘」 → 셋)
  - 사용자에게 올린 것: ② 무거움 — zsh 의 블록 안 주석(1회차 ① 이 고친 자리 — 같은 자리 두 번) ③ 그 외 — `test_analysis` 정책 문장이 또 틀렸다(csv_export 는 holding_days · 변동률 · 밴드를 계산한다 — 1회차 ⑦ 이 고친 자리) ① 무거움 — 룩어헤드 테스트가 늘 통과한다(이 계획서 범위 밖 — 테스트 데이터를 바꿔야 한다) ⑥ 가벼움 — 일별 비교 히스토그램의 범례 「일일수익률 차이」 · hover 「차이 범위」 · 함수 docstring 이 src(`tqqq/visualization.py`)에 남았다(C9 와 같은 모양, src 변경 0 인 계획서 범위 밖)
  - 고치지 않은 것: ⑤ 같은 파일의 다른 테스트 docstring 이 검증하지 않는 것을 약속한다(「포지션이 있으면 평가액 포함」 · trades_df 일관성 — 13-T 목록 밖) ⑦ 생성 파일이 원천보다 일찍 끝나면 멈추는 코드 가드 제안(새 기능) ⑩ `download_data.py` 를 여러 티커로 받게 하는 효율 제안(코드 변경) — 기준 3(그 외)
- 2026-10-24 10:40 ~ 10:46: 수정분 검증 — 수정분 diff(6 hunk)와 각 수정이 겨냥한 지적만 `general-purpose` 서브에이전트에게 줬다. 무거움 0. 세 질문 모두 답: 회귀 없음(포인터 대상 존재 · docstring 만 다름을 AST 로 확인 · 기록 문장 모두 사실), 방향은 위험 → 안전 또는 그대로. 발견 5건(모두 가벼움 — 고치지 않음, 사용자에게): 점검 보고서 15-T 가 유지일 테스트의 바뀌기 전 문장을 인용 · 처리가 끝났는데 판정 칸에 표시가 없는 행(D13 · D16 · C5 · C7 · C8, 13-T 「일부 처리함 … 나머지는 남았다」 — 앞 단계부터) · 세 번째 이름(`test_configs_list_not_empty`)이 점검 보고서에 없음 · 계획서의 「이름 둘」(관련 범위 · 목표 6 · Scope)과 Scope · DoD 에 `tests/CLAUDE.md` 빠짐 · 유지일 테스트의 Given · Then · 단언 메시지가 데이터와 「건너뛰고」 표현으로 어긋남(앞부터)
- 2026-10-24 10:46: black 변경 0 · `validate_project.py` — Ruff · PyRight 통과, passed=907 · failed=0 · skipped=0. src · `storage/` 변경 0. 상한 회차라 멈추고 사용자에게 보고한다. 상태를 Draft(사용자 결정 대기)로 — 결정 전에는 미룬 지적 옮김과 커밋 후보를 확정할 수 없다
- 2026-10-24 23:33: 사용자 결정(Notes) — 상태를 진행 중으로. 고치기 전 사본은 스크래치 `step12a/r3_before/`(`test_tqqq_visualization.py` 는 HEAD 와 같아 HEAD 를 기준으로)
- 2026-10-24 23:33 ~ 2026-10-25 00:05: 결정대로 고쳤다
  - ① COMMANDS ③ – ⑥ 블록 안 주석을 빼고 단계 이름을 산문으로. 가짜 `poetry` 로 `zsh -f -i`(주석 옵션 꺼짐) · `bash --norc -i` 에서 실패 없음 11 호출 · `generate_long_proxy_series` 실패 3 · `run_combo_grid` 실패 11 에서 멈추고 부모 셸 살아 있음, 「command not found」 0. ① 반복문은 EFA 실패에서 4 호출로 멈춘다
  - ② `test_analysis` 정책 문장을 규칙 한 줄로
  - ③ `test_hold_days_no_lookahead` — 종가 `[100, 100, 100, 110, 115, 100, 95]`(i=3 돌파 · i=4 유지 · i=5 상단 밴드 아래)로 바꾸고 「같은 데이터에서 유지일 1 이면 산다」 전제 단언과 거래 0 · 전 구간 position 0 단언. 엔진으로 유지일 0 · 1 은 거래 1, 2 · 3 은 0. 변형(저장소 밖 사본 `step12a/mut`, `PYTHONDONTWRITEBYTECODE=1`): M1 유지일 무시 · M2 하루 일찍 확정 · M3 실패해도 대기 유지 — 고치기 전 테스트는 셋 다 1 passed, 고친 뒤 테스트는 셋 다 1 failed(M1 · M2 거래 단언, M3 포지션 단언 — 마지막 날 사서 거래 기록에 남지 않는다). 사본 src 를 원본과 대조해 되돌림 확인
  - ④ `tqqq/visualization.py` 히스토그램 범례 · hover 둘 · docstring 을 「절대차이」로. 범례 이름을 단언하던 `test_tqqq_visualization.py` 의 기대값 · docstring 둘도(grep 으로 찾음). `AppTest` — 범례 · hover 「절대차이」 있음, 옛 문구 0
  - ⑤ 점검 보고서 판정 칸(D13 · D16 · C5 · C7 · C8 · 13-T 한 줄) · 15-T 인용 · 세 번째 이름 · 19절 줄, 계획서 「이름 둘」 · Scope · DoD 조정(Notes), 유지일 스케줄 테스트의 목적 · Given · Then · 단언 메시지
  - 재검증: AST — 23개 중 15개 같음, 다른 것은 앱 둘 · src 하나의 문자열, 이름 셋, 기대 문자열 둘, `test_hold_days_no_lookahead`(그 함수를 빼면 파일 AST 동일). 수집 907, 다른 ID 는 이름 셋의 여섯 줄. black 변경 0 · `validate_project.py` passed=907 · failed=0 · skipped=0, `storage/` 변경 0
- 2026-10-25 00:05 ~ 10:55: 수정분 검증 — 수정분 diff(14 hunk)와 각 수정이 겨냥한 지적만 `general-purpose` 서브에이전트에게 줬다(첫 실행이 세션 한도로 끊겨 같은 에이전트를 이어 받았다). 14 hunk 모두 세 질문에 답, 회귀 0 · 위험 쪽 방향 0. 발견 9건
  - 무거움 1 — diff 밖 · 앞부터: `test_last_day_pending_execution` 이 「N-1일 신호 → N일 체결」을 만들지 못한다. 재현(사본 `step12a/mutL`): 엔진이 마지막 날 예약 주문을 버리게 바꿔도 906 passed · 실패 1 은 사본에 `pyproject.toml` 이 없어 변형 없이도 나는 `test_logger` 루트 찾기. 9일째 돌파 데이터는 원래 엔진 마지막 날 90주 · 변형 0주. → 미룬 지적 파일로 옮겼다
  - 거른 것(가벼움 · 그 외 8): 점검 보고서 13-T 판정 칸에 「처리함」과 10-14 메모의 「나머지는 남았다」가 함께 — 기준 3(그 외 — 임시 문서 기록) · 판정 칸에 표시가 없는 행 25개(3-5 · 3-13 · 앞 단계 23) — 기준 3 · 룩어헤드 테스트 이름이 덮는 범위보다 넓다(미리 주문 넣기 변형은 `test_hold_days_1_timeline` · 전략 계약 테스트가 잡는다) — 기준 3 · `test_last_day_signal_ignored` 의 docstring 과 늘 참인 단언(다음 날이 없어 막을 결함이 없다) — 기준 1 · 다른 테스트 둘의 Then 일부 미단언(그 변형은 다른 테스트가 잡는다) — 기준 3 · `src/qbt/backtest/CLAUDE.md` 의 없는 의존 화살표(점검 보고서 D7 이 12단계 2 에서 다룬다) — 기준 3 · 「건너뛴다」 표현이 남은 엔진 주석 · 테스트 이름 — 기준 3 · COMMANDS 「첫 줄」 표현 — 기준 3
  - 앞 회차에 고치지 않은 지적의 판정: 1회차 ⑩ ⑫ · 2회차 ⑤ ⑦ ⑩ — 모두 기준 3(그 외), 2회차의 사용자에게 올린 넷은 사용자 결정으로 모두 고쳤다
- 2026-10-25 11:06: 마무리 — 미룬 지적 파일에 1건, DoD · Phase 체크, 근거 승격(DoD 줄)

---
