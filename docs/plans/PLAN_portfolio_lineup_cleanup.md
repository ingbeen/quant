# Implementation Plan: 포트폴리오 실험 목록 정리 — D-1-2X · SHY 20% 기준선 삭제, QQQ B&H 등록, 디버그 대시보드 삭제

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-05 22:26
**마지막 업데이트**: 2026-10-06 08:48
**관련 범위**: backtest(실험 등록 `portfolio_configs`), scripts(디버그 대시보드 삭제), tests, storage/results/portfolio, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/CLAUDE.md`, `docs/research/전략_검증_보고서.md`, `docs/research/Q2_2XS_보완_전략_설계.md`, `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: **두 실험 삭제** — `portfolio_d1_2x`(QLD 100%) · `portfolio_q2_2xs_shy20`(Q-2-2XS 80% + SHY 20% 기준선)을 공식 실험 목록 `PORTFOLIO_CONFIGS` 에서 지운다 — 설정 · 테스트 · 결과 폴더. 대시보드는 목록을 그대로 비추므로 앱 코드는 고치지 않는다(사용자 결정 2026-10-05 — 「대시보드에서만 숨김」 기각)
- [x] 목표 2: **QQQ B&H 등록** — 「QQQ 100% 매수 후 보유」를 포트폴리오 실험 `portfolio_qqq_bh` 로 등록한다. 시작일은 기존 정책 그대로 2005-01-03(정책 하한 2005-01-01, `min_start_date` 없음 — 사용자 결정 2026-10-05, 「채택 조합과 같은 2007-06-22」 기각). 목록 맨 앞에 둬 대시보드 첫 실험 탭이 기준점이 되게 한다
- [x] 목표 3: **디버그 대시보드 삭제** — `scripts/backtest/app_portfolio_debug.py` 를 지우고 그 파일을 가리키는 문서를 정리한다. `state_log.csv` 는 계속 저장한다
- [x] 목표 4: **결과 확인** — 남는 실험 4개(D-1 · Q-2 · Q-2-2XS · 채택 조합)와 `benchmark_qqq.json` 이 바이트까지 그대로이고, QQQ B&H 결과가 정합성 위반 0 이며 엔진 밖 손계산과 같음을 확인한다. 사용자가 대시보드를 확인한다(확인 지점 1)

## 2) 비목표(Non-Goals)

- **엔진 · 러너 · 대시보드 코드 수정** — `src/qbt/backtest/engines/` · `scripts/backtest/run_portfolio_backtest.py` · `scripts/backtest/app_portfolio_backtest.py` 는 고치지 않는다. `state_log.csv` 저장도 그대로 둔다(디버그 앱만 읽지만 연구 기록이 분석 근거로 써 왔고, 끄면 러너 변경이라 요청 범위 밖)
- **삭제한 실험의 이름이 다시 조회되지 않음을 고정하는 테스트** — 과거 상태를 테스트에 남기지 않는다(기존 25% 경계 테스트는 그대로 둔다)
- **그리드 재실행** — `storage/results/portfolio_grid/` · `portfolio_combo_grid/` 는 다시 돌리지 않는다. SHY 20% 기준선 비교 수치는 `combo_runs.csv` 에 그대로 남는다
- **미룬 지적 고치기** — `docs/DEFERRED_FINDINGS.md` 항목은 고치지 않고, 지운 파일 · 실험을 가리키는 문구만 맞춘다
- **데이터** — 시세를 다시 받지 않는다
- **이미 있던 문서 부정확** — `scripts/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` 가 대시보드 탭을 「알파벳 순」이라 적었으나 실제는 `PORTFOLIO_CONFIGS` 등록 순서다. 이 계획서와 무관한 기존 문구라 고치지 않고 언급만 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 요청(2026-10-05): ① `app_portfolio_debug.py` 제거 ② 포트폴리오 대시보드에서 `portfolio_q2_2xs_shy20` · `portfolio_d1_2x` 제거, QQQ 바이앤홀드 추가
- **대시보드에는 실험 목록이 따로 없다** — `app_portfolio_backtest.py` 의 `_discover_experiments` 가 `PORTFOLIO_CONFIGS` 를 돌며 결과 폴더가 있는 실험만 탭으로 만든다. 그래서 대시보드에서 빼려면 목록에서 빼야 한다
- **두 실험은 문서가 「남긴다」고 정한 것이다** — 이번 결정이 그것을 뒤집으므로 근거 문서에 새 결정으로 적는다
  - SHY 20%: 설계서 D52 「결론에서 채택한 후보, 그리고 그와 같은 비중의 SHY 기준선만 공식 목록에 남긴다」, 커밋 `38cdf3f` 에서 등록. 기준선 대비 수치(반올림 전 CAGR 13.0797 · MDD -22.7338 · Calmar 0.575340)는 `storage/results/portfolio_combo_grid/combo_runs.csv` 이어 붙인 판과 설계서 D75 · 0.2 에 남는다
  - D-1-2X: 보고서 H.9 「`portfolio_d1_2x`(QLD 100%, sell=0.05)는 남겼다 — 실전 후보로 검토 중이며(부록 I), D-1(1배)과 나란히 둬야 레버리지 효과가 보인다」. 수치는 부록 H.8.3 · I · L 표에 남는다. 부록 J 의 측정 방법 표 한 줄이 `portfolio_d1_2x/equity.csv` 를 산출 근거로 가리킨다
- **QQQ B&H** — 포트폴리오 엔진은 B&H 슬롯을 이미 지원한다(Q-2 의 GLD · TLT, `strategy_id="buy_and_hold"`, 워밍업 0). 기존 `benchmark_qqq.json` 은 연도별 수익률만 있어 수익 곡선 · MDD · 탭을 만들 수 없다
- **디버그 대시보드 참조** — 코드 · 테스트 참조 0건(`grep -rn app_portfolio_debug src scripts tests`, 자기 자신 제외). 문서 참조: `docs/COMMANDS.md` 7-1 · `README.md` 대시보드 목록 · `scripts/CLAUDE.md` 항목 · `docs/DEFERRED_FINDINGS.md` 두 항목. `docs/plans/` 의 완료 계획서 셋도 언급하지만 이력이라 고치지 않는다
  - 알고 지우는 것: 미룬 지적 「성과 대시보드 「체결 전후 비교」가 매수만 있는 체결일을 빠뜨리고 …」에 따르면 디버그 앱의 체결 상세 표에는 그 문제가 없다. 지우면 날짜별 체결을 자산 단위로 정확히 보는 화면이 없어진다(사용자에게 알림, 2026-10-05)
- 실측(2026-10-05, `summary.json`): 지울 결과 폴더 `portfolio_d1_2x` 1.7M · `portfolio_q2_2xs_shy20` 6.0M. 남는 실험의 기간 — D-1 · Q-2 2005-01-03 ~ 2026-09-24, Q-2-2XS 2007-04-09 ~ 2026-09-24, 채택 조합 2007-06-22 ~ 2026-09-24

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」(결과 파일 덮어쓰기 · 대시보드는 사용자가 실행)
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md`
- `docs/CLAUDE.md` — 과거 이력은 `docs/research/` 본문에 남긴다
- `docs/DEFERRED_FINDINGS.md` 머리말 — 항목 형식

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `PORTFOLIO_CONFIGS` 이름 목록이 `portfolio_qqq_bh` · `portfolio_d1` · `portfolio_q2` · `portfolio_q2_2xs` · `portfolio_q2_2xs_haa10_rotation10` 순서다
- [x] `scripts/backtest/app_portfolio_debug.py` 가 없고, `src` · `scripts` · `tests` · 살아있는 문서(`docs/plans/` 제외)에 그 이름이 남지 않는다 (`grep` 0건)
- [x] 회귀/신규 테스트 — QQQ B&H 설정 계약 테스트 추가, 시작일 하한 테스트를 채택 조합 하나로, 기준선 테스트 삭제
- [x] 결과 폴더 `portfolio_d1_2x` · `portfolio_q2_2xs_shy20` 삭제, `portfolio_qqq_bh` 생성. 남는 실험 4개 폴더와 `benchmark_qqq.json` 은 git diff 0
- [x] QQQ B&H 결과: 정합성 위반 0, 시작일 2005-01-03, 최종 자본이 엔진 밖 손계산(2005-01-04 시가 매수 주수 × 2026-09-24 종가 + 남은 현금)과 같다, 매도 거래 0 · 리밸런싱일 0
- [x] 대시보드 확인 안내 — 완료 보고에 실행 명령과 볼 지점(탭 다섯의 순서 · QQQ B&H 탭)을 적는다 (확인 지점 1, 사용자 지시로 확인은 계획서 완료 후 — Notes)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md`(변경 있음: 7-1 삭제) · `README.md`(변경 있음: 대시보드 목록) · `scripts/CLAUDE.md`(변경 있음) · `docs/DEFERRED_FINDINGS.md`(문구) · `src/qbt/backtest/CLAUDE.md`(변경 없음 — 실험 목록을 적지 않는다) · `tests/CLAUDE.md`(변경 없음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (결정은 설계서 D77 · 보고서 H.9, 실측은 같은 곳)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_configs.py` — `_CONFIG_D1_2X` 삭제, `_SUPPLEMENT_CONFIGS` 에서 기준선 삭제(이로써 안 쓰이게 되는 import `CANDIDATE_BASELINE` · `build_experiment_config` 정리), `_CONFIG_QQQ_BH` 추가(QQQ 신호 · QQQ 매매 100%, `strategy_id="buy_and_hold"`), 목록 순서, 모듈 docstring · 절 주석에서 지운 실험 · 기준선 언급 정리
- `tests/qbt/test_portfolio_configs.py` — QQQ B&H 계약 테스트 추가, `test_baseline_has_the_adopted_total_weight` 삭제, `test_only_supplement_configs_have_start_date_floor` 를 채택 조합 하나로, 머리 docstring · 클래스 docstring 의 기준선 언급 정리
- `scripts/backtest/app_portfolio_debug.py` — 삭제
- `docs/COMMANDS.md` — 7-1 디버그 대시보드 블록 삭제
- `README.md` — 대시보드 목록에서 「디버그」 삭제
- `scripts/CLAUDE.md` — `app_portfolio_debug.py` 항목 삭제
- `docs/DEFERRED_FINDINGS.md` — 「체결 전후 비교」 항목의 디버그 앱 문장, 「배분 조정 사유」 항목의 자리 `app_portfolio_debug.py:334 · :546` 과 ④, 「등록 실험 시작일 미대조」 항목의 `portfolio_q2_2xs_shy20` 언급
- `docs/research/Q2_2XS_보완_전략_설계.md` — 결정 D77(기준선 등록 삭제 · QQQ B&H 등록), 0.2 「현재 저장소 상태」의 공식 실험 줄, 0.3 표에 이 정리 한 줄
- `docs/research/전략_검증_보고서.md` — H.9 「남겼다」 문장을 삭제 사실 · 수치가 남은 곳 · 되살리는 법으로, 부록 J 측정 방법 표의 `portfolio_d1_2x/equity.csv` 줄에 그 폴더가 없어졌음을 덧붙임
- `docs/COMMANDS.md`: 변경 있음 (7-1 삭제 — 실행 명령 하나가 없어진다. 러너 CLI 옵션은 그대로)

### 데이터/결과 영향

- `storage/results/portfolio/` — 폴더 둘 삭제(`portfolio_d1_2x` · `portfolio_q2_2xs_shy20`), 새 폴더 하나(`portfolio_qqq_bh`). 남는 4개 · `benchmark_qqq.json` 은 바뀌지 않아야 한다(벤치마크 시작일은 전 실험 유효 시작일의 최솟값을 2005-01-01 로 끌어올린 값이라 그대로 2005-01-01)
- `storage/results/meta.json` — 러너 실행 이력이 늘어난다
- 대시보드 색: 실험 색은 이름을 정렬한 순서로 정해지므로, 목록이 바뀌면 남는 실험의 색도 바뀔 수 있다(표시만)
- QQQ B&H 탭의 「연간 수익률 vs QQQ」는 자기 자신과 비교라 초과 수익이 거의 0 이다(첫해 매수일 · 매수 비용 차이만)

## 6) 단계별 계획(Phases)

### Phase 0 — 실험 목록 계약을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `tests/qbt/test_portfolio_configs.py` 에 QQQ B&H 계약 테스트 추가 — `portfolio_qqq_bh` 는 슬롯 하나(`qqq`, 목표 1.0), 신호 · 매매 경로 모두 `QQQ_DATA_PATH`, `strategy_id == "buy_and_hold"`, `min_start_date is None`, 설정 검증 통과
- [x] `test_only_supplement_configs_have_start_date_floor` 의 기대 집합을 `{"portfolio_q2_2xs_haa10_rotation10"}` 로, docstring 을 「채택 조합뿐」으로
- [x] `test_baseline_has_the_adopted_total_weight` 삭제, 이로써 안 쓰이는 import(`CANDIDATE_BASELINE` · `build_experiment_config`) 정리, 머리 docstring 8번 · `TestSupplementConfigs` docstring · 25% 경계 테스트 docstring 의 기준선 근거 문구 정리

**Validation**:

- [x] `poetry run pytest tests/qbt/test_portfolio_configs.py` — 실패가 새 QQQ B&H 테스트(「실험명을 찾을 수 없습니다」)와 시작일 하한 테스트(기준선이 아직 있음) 둘뿐이다 (레드)

---

### Phase 1 — 실험 목록 변경 · 디버그 대시보드 삭제(그린)

**작업 내용**:

- [x] `portfolio_configs.py` — `_CONFIG_D1_2X` 삭제, 기준선을 `_SUPPLEMENT_CONFIGS` 에서 삭제하고 안 쓰이는 import 정리, `_CONFIG_QQQ_BH` 추가, `PORTFOLIO_CONFIGS = [QQQ B&H, D-1, Q-2, Q-2-2XS, 채택 조합]`, 모듈 docstring 에 QQQ B&H 한 줄 · 절 주석에서 기준선 · D52 언급 정리
- [x] `scripts/backtest/app_portfolio_debug.py` 삭제

**Validation**:

- [x] `poetry run pytest tests/qbt/test_portfolio_configs.py tests/qbt/test_supplement_experiment.py tests/qbt/test_combo_experiment.py` — 실패 0 (그린)
- [x] `grep -rn "app_portfolio_debug\|portfolio_d1_2x\|q2_2xs_shy20\|_CONFIG_D1_2X" src scripts tests` 0건

---

### Phase 2 — 결과 재산출 · 대조

**작업 내용**:

- [x] `git status --short storage/` 가 비어 있음을 확인한다 (결과 비교 전 작업 트리 깨끗)
- [x] 결과 폴더 `storage/results/portfolio/portfolio_d1_2x` · `portfolio_q2_2xs_shy20` 삭제
- [x] 포트폴리오 러너 전체 실행 (`docs/COMMANDS.md` 의 `run_portfolio_backtest.py`, 인자 없음) — 5개 실험 모두 정합성 검증 통과
- [x] `git diff --stat storage/results/portfolio/` — 지운 두 폴더 밖의 변경 경로 0 (남는 4개 · `benchmark_qqq.json` 바이트 동일). `portfolio_qqq_bh` 는 untracked 새 폴더, `storage/` 의 그 밖 변경은 `meta.json` 뿐
- [x] QQQ B&H 손계산 대조 (스크래치, 엔진을 쓰지 않음) — `QQQ_max.csv` 로 주수 = int(10,000,000 ÷ (2005-01-04 시가 × 1.003)), 최종 자본 = 10,000,000 − 주수 × 매수가 + 주수 × 2026-09-24 종가를 내고 `summary.json` 의 `final_capital`(정수 반올림) · 시작일 · 끝날과 대조. `trades.csv` 매도 0행, `equity.csv` 의 `rebalanced` 참 0일

**Validation**:

- [x] 위 대조가 모두 맞다 (수치는 진행 로그에 도구 출력 그대로)
- [x] **확인 지점 1** — 대시보드(`app_portfolio_backtest.py`) 확인은 계획서 완료 후 사용자가 한다(사용자 지시 2026-10-06). AI 는 완료 보고에 실행 명령과 볼 지점(탭 다섯의 순서 · QQQ B&H 탭)을 적는다

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] `docs/COMMANDS.md` 7-1 블록 삭제 · `README.md` 대시보드 목록 · `scripts/CLAUDE.md` 디버그 항목 삭제
- [x] `docs/DEFERRED_FINDINGS.md` — 지운 앱 · 실험을 가리키는 문구 정리(항목 자체는 그대로)
- [x] 설계서 D77 · 0.2 · 0.3, 보고서 H.9 · 부록 J 측정 방법 표 — 현재형으로, 결정 날짜(2026-10-05)와 수치가 남은 곳 · 되살리는 법을 함께
- [x] `grep -rn "app_portfolio_debug" --include="*.md" . | grep -v "^./docs/plans/"` 0건, `portfolio_d1_2x` · `q2_2xs_shy20` 의 살아있는 문서 언급은 「지웠다 / 수치가 남은 곳」 문맥뿐
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 14건 — 버그 2 [무거움 0 · 가벼움 2] · 그 외 12 · 조치: 버그 고치지 않음 — ① 매도 0 인 실험의 체결 전후 비교 파일 없음은 diff 밖 기존 러너 코드 · 계획서 비목표라 미룬 지적 ③ 으로(사용자 보고), ② `meta.json` 의 없는 파일 경로는 거르는 기준 2. 그 외 중 계획서 문서 줄을 어긴 넷(결정 날짜 · 수치 출처 · H.9 문단 순서 · 0.2 요약)은 그 줄의 이행으로 고침, 나머지 8건 고치지 않음 — 진행 로그)
- [x] 수정분 검증 (수정 4건 · 발견 9건 — 무거움 0 · 조치: 고치지 않음, 모두 문서 표현이라 거르는 기준 3 — 진행 로그 · 완료 보고)
- [x] `poetry run python validate_project.py` (passed=857, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / QQQ B&H 실험 등록과 D-1-2X · SHY 20% 기준선 · 디버그 대시보드 삭제
2. 백테스트 / 포트폴리오 실험 목록 정리와 QQQ 매수 후 보유 기준점 추가
3. 백테스트 / 포트폴리오 공식 실험을 QQQ B&H · D-1 · Q-2 · Q-2-2XS · 채택 조합 다섯으로 정리
4. 백테스트 / 대시보드 첫 탭용 QQQ B&H 기준점 등록, 쓰지 않는 비교 실험 둘과 디버그 대시보드 제거
5. 백테스트 / D-1-2X · SHY 20% 기준선 결과 삭제, QQQ B&H 결과 산출과 결정 D77 기록

## 7) 리스크(Risks)

- **결과 파일 덮어쓰기** — 러너는 전 실험 결과를 다시 쓴다. Phase 2 첫 줄에서 `storage/` 가 깨끗한지 확인하고, 남는 4개가 바이트 동일한지로 회귀를 잡는다(같은 날 체결 순서는 설정 순서로 고정돼 재실행 결과가 같다 — `src/qbt/backtest/CLAUDE.md`)
- **되돌리기** — 두 실험의 결과 폴더는 git 추적이라 커밋 전에는 `git restore` 로, 커밋 뒤에는 이력에서 되살릴 수 있다. 설정은 보고서 H.9 · 설계서 D77 의 「되살리는 법」대로 다시 넣으면 같은 결과가 나온다
- **D52 · 부록 I 결정 뒤집기** — 근거 문서에 새 결정으로 남기지 않으면 다음 세션이 「남긴다」를 현재로 읽는다. 마지막 Phase 의 문서 줄이 막는다
- **기간이 다른 비교** — QQQ B&H(2005-01-03 부터)와 채택 조합(2007-06-22 부터)은 기간이 달라 대시보드 수치를 바로 비교할 수 없다. 사용자가 알고 고른 것이다(2026-10-05)
- **디버그 화면 상실** — 자산 단위 체결 확인 화면이 없어진다. 남은 「체결 전후 비교」 표의 결함은 미룬 지적에 그대로 있다

## 8) 메모(Notes)

- 사용자 결정(2026-10-05): ① 두 실험은 공식 목록에서 삭제(「대시보드에서만 숨김」 기각) ② QQQ B&H 는 포트폴리오 실험으로 등록(「비교 차트에 선만 추가」 기각) ③ QQQ B&H 시작일 2005-01-03(「채택 조합과 같은 2007-06-22」 기각)
- 이름 · 표시 이름 · 목록 위치(`portfolio_qqq_bh` · 「QQQ B&H (QQQ 100% 보유)」 · 맨 앞)는 계획서 제안이다 — 승인 때 바꿀 수 있다
- 계획서 조정(사용자 지시 2026-10-06 「계획서대로 진행, 대시보드 확인은 계획서 완료 후 안내」): 확인 지점 1 을 「Phase 2 에서 사용자 확인」에서 「완료 보고에 안내」로 바꿨다 — DoD 한 줄 · Phase 2 Validation 한 줄. 이름 · 표시 이름 · 목록 위치는 제안대로 승인됐다

### 진행 로그 (KST)

- 2026-10-05 22:26: 계획서 작성. 착수 전 실측 — 대시보드 실험 탐색은 `PORTFOLIO_CONFIGS` 만 돈다, `app_portfolio_debug.py` 코드 · 테스트 참조 0건, `state_log.csv` 를 파일로 읽는 곳은 디버그 앱뿐(러너가 쓰고 검사기는 메모리의 표를 쓴다), 지울 결과 폴더 1.7M · 6.0M
- 2026-10-06 08:25: 사용자 승인 「계획서대로 진행」 → In Progress. 작업 트리는 이 계획서(untracked) 외 깨끗
- 2026-10-06 08:31: Phase 0 — QQQ B&H 계약 테스트 추가, 시작일 하한 테스트를 채택 조합 하나로, 기준선 테스트와 그 import 삭제, docstring 정리. `pytest tests/qbt/test_portfolio_configs.py` 「2 failed, 16 passed」 — 실패는 `test_qqq_bh_holds_qqq_without_trading_rule`(「실험명을 찾을 수 없습니다: 'portfolio_qqq_bh'」)와 `test_only_supplement_configs_have_start_date_floor`(「Extra items in the left set: 'portfolio_q2_2xs_shy20'」) 둘뿐 (레드)
- 2026-10-06 08:36: Phase 1 — `portfolio_configs.py` 에서 `_CONFIG_D1_2X` · 기준선 등록과 그 import(`CANDIDATE_BASELINE` · `build_experiment_config`) 삭제, `_CONFIG_QQQ_BH` 추가, 모듈 docstring · 절 주석 정리. `app_portfolio_debug.py` 삭제(git 추적 파일). 세 테스트 파일 「136 passed」(그린). 이름 목록 `['portfolio_qqq_bh', 'portfolio_d1', 'portfolio_q2', 'portfolio_q2_2xs', 'portfolio_q2_2xs_haa10_rotation10']`. grep — `.py` 0건, 남은 1건은 `scripts/CLAUDE.md:199`(마지막 Phase 문서 줄이 지운다)
- 2026-10-06 08:28: Phase 2 — `git status --short storage/` 비어 있음 → 결과 폴더 둘 삭제 → 러너 전체 실행 「exit=0 소요=12초」, 5개 실험 모두 「정합성 검증 통과 (7개 규칙 모두 정상)」. `portfolio_qqq_bh` 「start_date=2005-01-01 (데이터 기준 1999-03-10, 하한 2005-01-01, 실험 하한 None)」. `git diff --stat storage/` 「19 files changed, 54 insertions(+), 61993 deletions(-)」 — 지운 두 폴더 밖의 변경 경로는 `storage/results/meta.json` 뿐(남는 4개 · `benchmark_qqq.json` 바이트 동일, `cmp` 로도 확인). 새 폴더 `portfolio_qqq_bh` 파일 5개(equity · signal_qqq · state_log · summary · trades)
- 2026-10-06 08:30: QQQ B&H 손계산(`QQQ_max.csv` 만 사용) — 「2005-01-04 시가 33.725541 매수가 33.826718 주수 295624 남은 현금 10.4294 2026-09-24 종가 741.099976 최종 자본 219086949.7344 → 반올림 219086950」, `summary.json` 「final_capital 219086950, start_date 2005-01-03, end_date 2026-09-24, cagr 15.27, mdd -53.4, calmar 0.29, total_trades 0」, `open_position` 「entry_date 2005-01-04, entry_price 33.8267, shares 295624」. `equity.csv` 5466행 · `rebalanced` 참 0 · `trades.csv` 0행 — 모두 일치
- 2026-10-06 08:30: 발견 — `portfolio_qqq_bh` 에는 `execution_comparison.csv` 가 없다. 러너는 체결일을 매도 거래의 `exit_date` 로만 뽑고 표가 비면 파일을 쓰지 않는데(`run_portfolio_backtest.py:365`), B&H 는 매도가 0 이다. 대시보드는 「체결 전후 비교 데이터가 없습니다. run_portfolio_backtest.py를 재실행하세요.」를 보인다 — 재실행해도 생기지 않는다. 미룬 지적 「체결 전후 비교가 매수만 있는 체결일을 빠뜨린다」와 뿌리가 같아 그 항목에 이 모양을 덧붙인다(비목표 — 러너 · 대시보드 무변경). `meta.json` 의 이 실험 `execution_comparison_csv` 경로도 없는 파일을 가리킨다(기존 동작, 파일이 비는 모든 실험 공통)
- 2026-10-06 08:52: 마지막 Phase 문서 — `docs/COMMANDS.md` 7-1 삭제 · `README.md` 「디버그」 삭제 · `scripts/CLAUDE.md` 디버그 항목 삭제. `docs/DEFERRED_FINDINGS.md` — 「체결 전후 비교」 항목의 디버그 앱 문장을 지우고 ③(매도 0 인 실험은 파일이 안 생기고 대시보드가 「재실행하세요」라고 안내, `portfolio_qqq_bh`)을 덧붙임, 「배분 조정 사유」 항목의 디버그 앱 자리 · ④ 삭제, 「등록 실험 시작일 미대조」 항목을 채택 조합 하나로. 설계서 — D77 추가 · 세션 문장에 D77 · 0.2 표에 이 정리 한 줄(바로 위 「계획서 등록 실험 정리」 줄의 「커밋 전」은 실제 커밋 `38cdf3f` 로 바로잡음) · 「현재 저장소 상태」의 공식 실험 줄. 보고서 — H.9 의 「남겼다」 문단을 삭제 사실 · 수치가 남은 곳(H.8.3 · I · L.6) · 마지막 산출 수치 · 되살리는 법으로, 측정 방법 표 한 줄에 폴더 삭제를 덧붙임. **계획서의 「부록 J 측정 방법 표」는 실제로는 부록 K.3.1 이었다**(표기 오류, 고친 자리는 같다)
- 2026-10-06 08:53: grep — `app_portfolio_debug` 는 `docs/plans/` 밖에서 설계서 D77(지웠다는 문맥) 1곳뿐, `portfolio_d1_2x` · `q2_2xs_shy20` 의 살아있는 문서 언급은 설계서 D77 · 보고서 H.8.3 표(과거 수치) · H.9 · K.3.1(지웠다는 문맥)뿐. `poetry run black .` 「136 files left unchanged」
- 2026-10-06 08:41: 진행 로그 시각 바로잡음 — 위 08:31 · 08:36 · 08:52 · 08:53 은 `date` 로 재지 않고 적은 값이라 틀렸다(코드 리뷰 지적). 파일 수정 시각(`stat`)으로 본 실제 순서: 테스트 08:26:36(Phase 0) → `portfolio_configs.py` 08:27:11(Phase 1) → `portfolio_qqq_bh/summary.json` 08:27:42(Phase 2 러너) → `docs/COMMANDS.md` 08:28:50 · `README.md` 08:28:56 · `scripts/CLAUDE.md` 08:28:57 · 보고서 08:30:43(마지막 Phase 문서). 내용은 그대로이고 순서 · 시각만 이 줄이 맞다
- 2026-10-06 08:41: `/code-review xhigh` 1회차 — 발견 14건. 분류: 버그 2(가벼움 2) — ① `run_portfolio_backtest.py:365` 매도가 0 인 실험(`portfolio_qqq_bh`)은 체결 전후 비교 파일이 안 생기고 대시보드가 「재실행하세요」를 보인다: 닿음(지금 산출물), diff 밖 기존 러너 코드 · 계획서 비목표(러너 · 대시보드 무변경)라 고치지 않고 미룬 지적 「체결 전후 비교」 항목 ③ · 출처에 덧붙임, 완료 보고에서 사용자에게 올림 ② `run_portfolio_backtest.py:501` `meta.json` 이 쓰지 않은 파일 경로를 적음: 거르는 기준 2(그 경로를 읽는 코드 0 — 열면 FileNotFoundError 로 멈출 뿐). 그 외 12 — ③ D77 반올림 전 SHY 수치의 출처가 틀림 ④ 디버그 화면 상실(사용자가 알고 고름) ⑤ `supplement_experiment.py` `build_experiment_config` docstring 과 `src/qbt/backtest/CLAUDE.md` 의 「등록 실험을 이 함수로 만든다」 문구가 이제 맞지 않음 ⑥ H.9 의 sell10 되살리기 문장이 D-1-2X 문단 뒤로 밀려 오독 ⑦ 결정 날짜 10-06(실제 10-05) ⑧ 설계서 0.2 굵은 요약이 기준선 등록 상태 ⑨ `scripts/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` 의 「알파벳 순 탭」(실제 등록 순서 — QQQ B&H 맨 앞이 그 순서에 기댄다) ⑩ 목록 순서를 고정하는 테스트 없음 ⑪ 진행 로그 시각(위 줄로 바로잡음) ⑫ `docs/COMMANDS.md` 출력 목록이 execution_comparison 을 늘 있는 것처럼 적음 ⑬ `state_log.csv` 를 읽는 곳 0(계획서가 유지로 정함) ⑭ `_SUPPLEMENT_CONFIGS` 가 한 원소 리스트. 조치: ③ ⑥ ⑦ ⑧ 은 마지막 Phase 문서 줄(「결정 날짜(2026-10-05)와 수치가 남은 곳 · 되살리는 법」 · 「0.2」)을 어긴 것이라 그 줄의 이행으로 고침(사본을 뜬 뒤). 나머지 그 외 8건은 고치지 않음(거르는 기준 3, 완료 보고 표). 고칠 버그 0 이라 1회차로 끝
- 2026-10-06 08:44: 그 외 넷 수정 — 설계서 D77 의 출처를 「`combo_runs.csv` 「이어 붙인 판 · SHY(기준선) · 합계 20」 행(13.08 · -22.73 · 0.5753) · 우위 0.0411 은 D75 · 반올림 전 값은 0.2 에만」으로, D77 · 세션 문장 · 보고서 H.9 의 결정 날짜를 2026-10-05 로(실측 · 삭제 날짜 10-06 은 그대로), H.9 에서 sell10 되살리기 문단을 표 바로 뒤로 옮기고 「위 대조군 넷을」 · D-1-2X 는 sell 0.05 기본값 슬롯이라는 문장을 더함, 0.2 맨 위에 2026-10-06 D77 한 줄. 수정분 검증(맥락 없는 서브에이전트, `diff -u` 사본 대 현재 48줄) — 네 hunk 모두 ① 회귀 없음(CSV 58행 「13.08,-22.73,0.5753」 대조, 반올림 전 값은 HEAD 의 지운 equity.csv 로 다시 계산해 「13.0797 -22.7338 0.57534」) ② 같은 모양 잔존 가벼움 9 ③ 위험 방향 전환 없음. 발견 9 — 이 계획서 44행이 같은 틀린 출처 문장을 가짐 · 「0.2 에만」이 D77 · 계획서와 겹치고 git `38cdf3f` 로 다시 만드는 경로가 빠짐 · CSV 행끼리 빼면 0.0412(D75 0.0411 은 반올림 전 차이, `combo_judgment.csv` 23행) · 0.2 의 「비교 수치는 그리드 CSV 두 벌에」 문장 · S9 요약의 「(커밋 전)」과 0.2 제목 시각 · 행 이름이 「대체 판 (이어 붙인 판 시작일부터)」와 부분 일치 · H.9 제목의 「대조군」이 D-1-2X 문단까지 감쌈 · 이름 · 목록 위치 승인은 10-06 · D52 행에 D77 표시 없음(관례 없음). 무게와 관계없이 고치지 않음(review.md 「수정분 검증」) — 모두 문서 표현이라 거르는 기준 3
- 2026-10-06 08:47: 품질 검증 — 문서 수정 뒤 다시 실행 「Ruff 통과 · PyRight 통과 · passed=857, failed=0, skipped=0」(첫 실행도 같은 수, 21초). 미룬 지적 — 새 항목 없음, 「체결 전후 비교」 항목에 ③ 과 출처를 덧붙임. 거른 지적: 리뷰 ②(기준 2) · 그 외 8건(기준 3) · 수정분 검증 9건(기준 3). 근거 승격 — 결정 · 실측은 설계서 D77 · 0.2 와 보고서 H.9 · K.3.1 에 있다
- 2026-10-06 08:48: `/commit` 후보 5개를 Commit Messages 절에 옮김 → ✅ Done. 대시보드 확인(확인 지점 1)은 완료 보고에서 안내
