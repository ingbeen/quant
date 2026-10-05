# Implementation Plan: 보완 전략 등록 실험 정리 — 채택 조합 10/10 · SHY 20% 등록, 25% 등록 넷 삭제

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-05 21:03
**마지막 업데이트**: 2026-10-05 21:39
**관련 범위**: backtest(실험 등록 `portfolio_configs`), tests, storage/results/portfolio, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `src/qbt/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/research/Q2_2XS_보완_전략_설계.md`, `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: **채택 등록** — 결론의 채택 조합 「Q-2-2XS 80% + HAA 10% + 로테이션 10%」(설계서 D75)와 같은 합계의 기준선 「Q-2-2XS 80% + SHY 20%」를 `PORTFOLIO_CONFIGS` 에 등록한다. 둘 다 그리드와 같은 구성 함수 · 같은 시작일 하한(2007-06-22)으로 만들어 대시보드 숫자가 조합 그리드 결과와 같게 한다(D52 · D75)
- [x] 목표 2: **25% 등록 넷 삭제** — `portfolio_q2_2xs_{gold,haa,rotation,shy}25` 의 설정 · 테스트 · 결과 폴더를 지운다(D52 — 채택 후보와 같은 비중의 SHY 기준선만 남긴다)
- [x] 목표 3: **결과 확인** — 남는 기존 실험 4개 · QQQ 벤치마크 결과가 바이트까지 그대로이고, 새 등록 둘의 결과가 정합성 위반 0 이며 조합 그리드 CSV(`combo_runs.csv` 이어 붙인 판)의 같은 구성 행과 같음을 확인한다. 사용자가 대시보드에서 새 두 탭을 확인한다(확인 지점 1)

## 2) 비목표(Non-Goals)

- **엔진 · 판정 · 그리드 수정** — `src/qbt/backtest/engines/` · `portfolio_types.py` · `portfolio_validation.py` · `allocators/` · `supplement_experiment.py` · `combo_experiment.py` 는 고치지 않는다(D62 와 같은 이유 — 수치 변화의 원인을 「등록」 하나로 묶는다). 두 그리드 결과(`storage/results/portfolio_grid/` · `portfolio_combo_grid/`)는 다시 돌리지 않는다
- **비교용 단독 등록** — HAA 20% · 로테이션 20% 단독은 등록하지 않는다(D52 — 채택 후보와 기준선만). 비교 수치는 조합 그리드 CSV 와 부록 M 에 남는다
- **부록 M · 참조 정리 · 문서 삭제** — 설계서 0.3 할 일 3 – 5 는 이 계획서 다음이다(계획서 없이 한다)
- **12.5 같은 소수점 비중** — 채택 비중 10 · 10 · 20 은 지금 코드(`COMBO_PCTS` · `W_PCTS`)가 받는 값이라 비중 제한을 풀지 않는다
- **미룬 지적 고치기** — `docs/DEFERRED_FINDINGS.md` 항목은 고치지 않는다. 등록 실험 이름 · 실측을 가리키는 두 항목의 문구만 새 등록에 맞춘다(착수 전 결정 ①)
- **데이터** — 시세를 다시 받지 않는다(D22)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 결론 정리의 착수 전 질문이 S9 에서 끝났다 — 채택은 조합 10/10(D75). D52 는 「채택 후보와 같은 비중의 SHY 기준선만 공식 목록에 남기고, 채택 비중이 25% 가 아니거나 조합을 채택하면 등록 실험을 새로 만든다」고 정했다
- 지금 `portfolio_configs.py` 는 D50 의 25% 등록 넷(기준선 · 금 · HAA · 로테이션)을 `build_experiment_config` 로 만든다. 채택 조합은 매매법이 셋이라 `build_combo_config` 로 만들어야 한다 — **포트폴리오 러너 · 대시보드로 도는 첫 3매매법 실험**이다(조합 그리드는 엔진을 직접 불렀다)
- 글자 규칙이 막거나 되돌릴 수 없는 결과에 물리는 설계 — 해당 없음(결과 폴더 삭제는 git 추적 대상이라 되돌릴 수 있다)

### 착수 전 결정 (답 받음 — 설계서 6장 D76: (가) 문구만 맞춘다)

| 번호 | 질문 | 현재 확인된 사실 | 선택지와 영향 | 추천 |
| --- | --- | --- | --- | --- |
| ① | 미룬 지적 「보완 전략 등록 실험의 실제 시작일을 `min_start_date` 와 대조하지 않는다」를 이번에 고칠까 | 항목 본문이 지울 등록 넷의 이름(`portfolio_q2_2xs_{shy,gold,haa,rotation}25`)과 그 실측(넷 모두 2007-06-22 시작, 0건)을 적고 있다. 러너(`run_portfolio_backtest.py` `main`)는 시작일 = max(엔진 유효 시작일, 2005-01-01, `min_start_date`) 로만 정하고 대조하지 않는다. 그리드 워커는 같은 상황에서 멈춘다(`run_with_start_check`). 설계서는 이 항목을 「실전 투입 전」 묶음에 둔다 | (가) **문구만 맞춘다** — 이름을 새 등록 둘로 바꾸고 실측(새 둘의 실제 시작일)을 다시 적는다. 코드 변경이 등록 하나로 묶인다. (나) **이번에 고친다** — 러너가 `min_start_date` 가 있는 실험의 실제 시작일이 그날과 다르면 멈춘다. 러너 코드 · 테스트가 늘고, 실제 산출물은 0건이라 결과는 같다 | (가). 이 계획서는 D52 정리이고, 그 항목은 결론 뒤 「실전 투입 전」에 미룬 지적 7건과 함께 보기로 했다(설계서 0.3) |

### 착수 전 확인한 사실 (2026-10-05 21:03, S9)

- 커밋: `75bd5ef..HEAD` 는 `eca6405`(설계서 S9 · 다른 세션의 `CLAUDE.md` 계열 문서) 하나, 작업 트리 깨끗
- 등록 설정을 읽는 곳(정의 제외): 러너 `scripts/backtest/run_portfolio_backtest.py`(실험 목록 · `--experiment` 선택지 · 유효 시작일), 대시보드 `scripts/backtest/app_portfolio_backtest.py` · `app_portfolio_debug.py`(결과 폴더 탐색 — `PORTFOLIO_CONFIGS` 를 돈다), 테스트 `tests/qbt/test_portfolio_configs.py`. 그리드 러너 둘과 테스트 둘은 `portfolio_q2_2xs` 의 슬롯만 읽는다. 등록 이름을 글자로 쓰는 코드 · 테스트는 `test_portfolio_configs.py` 뿐이다(`test_supplement_experiment.py` 의 `portfolio_q2_2xs_haa30` 등은 이름 규칙 테스트라 등록과 무관)
- 러너는 매매법이 여럿이면 `ledger.csv` · `netting.csv` · `summary.json` 의 `per_method` 등을 쓰고(`len(resolve_methods(config)) > 1`), 대시보드 「매매법별 손익」은 `per_method` 를 돈다 — 매매법 수를 2로 가정하는 곳은 찾지 못했다(`methods[` · `== 2` 검색 0건)
- QQQ 벤치마크(`benchmark_qqq.json`)의 시작일은 등록 전체의 유효 시작일 최솟값과 2005-01-01 중 늦은 날이다 — 최솟값은 기존 실험이 정하고 새 등록 둘(2007 이후)은 바꾸지 않는다
- 메타(`meta.json`)의 `portfolio_backtest` 는 실행마다 한 줄씩 쌓이고 최근 5개만 남는다(`MAX_HISTORY_COUNT`) — 전체 실행 한 번이면 지울 넷의 항목은 밀려난다
- 조합 그리드의 이어 붙인 판(2007-06-22 – 2026-09-24) 값 — 조합 10/10: CAGR 14.03 · MDD -22.77 · Calmar 0.6165 · 연 회전율 1.6867 · 매도 거래 수 460 / SHY 20%: 13.08 · -22.73 · 0.5753 · 0.7462 · 178 (`combo_runs.csv`). 묶음 시작일은 조합 2007-06-22, SHY 단독은 엔진 유효 시작일 2007-04-09 를 하한 2007-06-22 로 올린 값이다(설계서 15장 S8)
- 지울 결과 폴더: `gold25` 6.1M · `haa25` 12M · `rotation25` 6.8M · `shy25` 6.0M

### 계획서 안에서 정한 세부 (승인과 함께 확인받는다)

| 항목 | 정한 것 | 근거 |
| --- | --- | --- |
| 구성 | 조합 `build_combo_config(_CONFIG_Q2_2XS.asset_slots, 10, 10, VARIANT_SPLICED, MAIN_START_DATE)` → `portfolio_q2_2xs_haa10_rotation10`, 기준선 `build_experiment_config(_CONFIG_Q2_2XS.asset_slots, CANDIDATE_BASELINE, 20, VARIANT_SPLICED, MAIN_START_DATE)` → `portfolio_q2_2xs_shy20`. 기준선 비중은 채택 두 몫의 합으로 둔다 | 그리드와 같은 함수 · 같은 시작일 하한이라 대시보드 숫자가 그리드와 같다(D45 · D52). 합으로 두면 채택 비중이 바뀔 때 기준선이 따라간다 |
| 목록 순서 | 기존 4개 → 기준선 → 채택 조합 | 지금 순서(기준선이 보완 후보보다 앞)를 따른다. 대시보드 탭은 이름순이라 화면에는 영향이 없다 |
| 결과 폴더 | 지울 넷은 폴더째 지우고 러너를 `--experiment` 없이(전체) 돌린다 | 전체 실행이 남는 4개 실험의 바이트 동일을 함께 확인한다(D52 「남는 실험은 다시 돌려 바이트까지 같은지」) |
| 메타 | 러너가 쌓는 대로 둔다(따로 고치지 않는다) | 실행 이력이고, 전체 실행으로 지울 넷의 항목은 밀려난다 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」(대시보드는 사용자가 실행 · 결과 파일은 덮어써진다) 절 (값이 아니라 **판단 근거**)
- `docs/CLAUDE.md` — 문서 보관 정책 · `docs/plans/` 유지
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` — 실험 등록(8 · 8-3 · 8-4)
- `scripts/CLAUDE.md` — 포트폴리오 러너
- `tests/CLAUDE.md` — 테스트 작성 원칙
- `docs/research/Q2_2XS_보완_전략_설계.md` — 0.1 세션 인계 규칙 · D50 · D52 · D75 (이 작업의 근거 승격 목적지)
- `docs/MEMORY.md` — `poetry run` 은 `env -u VIRTUAL_ENV` 로

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 채택 조합 10/10 과 SHY 20% 가 그리드와 같은 구성 · 같은 시작일 하한으로 등록되고, 25% 등록 넷의 설정 · 결과 폴더가 없다
- [x] 남는 기존 실험 4개 · `benchmark_qqq.json` 바이트 동일, 새 등록 둘 정합성 위반 0 · 조합 그리드 CSV 와 수치 일치(진행 로그에 도구 출력)
- [x] 회귀/신규 테스트 — `test_portfolio_configs.py` 의 등록 계약을 새 등록으로 바꾸고, 지운 이름을 조회하면 ValueError 인 경계 조건을 더한다
- [x] **확인 지점 1 — 사용자가 대시보드에서 새 두 탭(특히 매매법 셋의 「매매법별 손익」)을 확인했다**
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `src/qbt/backtest/CLAUDE.md` 변경 있음(등록 실험 구성 함수 문장), `docs/COMMANDS.md` 변경 없음(러너 명령 · 옵션 그대로, 실험명은 `PORTFOLIO_CONFIGS` 를 가리킨다), `README.md` 변경 없음(등록 실험 목록을 적지 않는다), `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md` 는 마지막 Phase 에서 다시 보고 변경 여부를 적는다 — 셋 다 변경 없음(진행 로그)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (설계서 0.2 등록 실험 목록 · 등록 결과 대조 · D54 삭제 목록에 이 계획서 추가 · 15장 S9)
- [x] 미룬 지적 옮김 — 해당 없음: 버그 1건은 사용자가 받아들였고(D76) 이미 파일에 있으며, 그 외 10건은 기준 3(#11 은 기준 1 도) — 진행 로그 · Done 보고 표. 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_configs.py` — 25% 등록 넷 → 기준선 SHY 20% · 채택 조합 10/10, 쓰지 않게 되는 import 정리
- `tests/qbt/test_portfolio_configs.py` — `TestSupplementConfigs` 를 새 등록 계약으로
- `storage/results/portfolio/` — 폴더 넷 삭제(`portfolio_q2_2xs_{gold,haa,rotation,shy}25`), 새 폴더 둘(`portfolio_q2_2xs_shy20` · `portfolio_q2_2xs_haa10_rotation10`), `storage/results/meta.json`
- `src/qbt/backtest/CLAUDE.md` — 8 「보완 전략 등록 실험은 … 로 만든다」 문장
- `docs/DEFERRED_FINDINGS.md` — 등록 실험 이름 · 실측을 가리키는 두 항목의 문구(착수 전 결정 ① 이 (가)일 때)
- `docs/research/Q2_2XS_보완_전략_설계.md` — 근거 승격(0.2 · 0.3 할 일 5 · 15장 S9 · 6장 D76)
- `docs/COMMANDS.md`: 변경 없음 — 러너 명령 · CLI 옵션이 그대로다(`--experiment` 선택지는 `PORTFOLIO_CONFIGS` 에서 나온다)
- `README.md`: 변경 없음 — 기능 목록에 등록 실험을 적지 않는다(그리드 두 줄만 있다)

### 데이터/결과 영향

- 기존 실험 4개(`portfolio_d1` · `d1_2x` · `q2` · `q2_2xs`)와 `benchmark_qqq.json`: 바뀌지 않아야 한다 — 전체 재실행 뒤 `git diff --stat storage/results/portfolio/` 로 확인
- 새 등록 둘: 조합 그리드 CSV 의 같은 구성 행과 같은 수치(같은 함수 · 같은 시작일)
- 두 그리드 결과 CSV: 다시 돌리지 않는다(무변경)
- 결과 폴더 합계: 지울 넷 약 31M, 새 둘은 실행 뒤 잰다

## 6) 단계별 계획(Phases)

### Phase 0 — 등록 계약을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `TestSupplementConfigs` 를 새 계약으로 바꾼다 — ① 채택 조합 `portfolio_q2_2xs_haa10_rotation10` 이 `build_combo_config(Q-2-2XS 슬롯, 10, 10, VARIANT_SPLICED, MAIN_START_DATE)` 와 같은 설정이고 매매법 (q2_2xs 0.8 · haa 0.1 · rotation 0.1), 설정 검증 통과 ② 기준선 `portfolio_q2_2xs_shy20` 이 `build_experiment_config(Q-2-2XS 슬롯, "shy", 20, …)` 와 같은 설정이고 매매법 (q2_2xs 0.8 · shy 0.2) ③ 시작일 하한이 있는 실험은 이 둘뿐 ④ (경계) 지운 25% 이름 넷을 조회하면 ValueError
- [x] 파일 머리 「테스트 계약」 8번 문구를 새 계약으로

**Validation**:

- [x] `test_portfolio_configs.py` 만 돌려 새 테스트가 실패(레드)하고 나머지는 통과함을 본다 (failed=7 · passed=11 — 진행 로그)

---

### Phase 1 — 등록 바꾸기(그린)

**작업 내용**:

- [x] `portfolio_configs.py` — 25% 넷을 지우고 기준선 SHY 20% · 채택 조합 10/10 을 위 「세부」대로 만든다. 절 주석을 채택 근거(D52 · D75)로 바꾸고, 쓰지 않게 된 import(`CANDIDATE_GOLD` 등)를 지운다
- [x] 바꾸기 전 · 뒤의 `PORTFOLIO_CONFIGS` 이름 목록을 진행 로그에 남긴다

**Validation**:

- [x] `test_portfolio_configs.py` 통과 · `test_supplement_experiment.py` · `test_combo_experiment.py` 통과(등록 슬롯을 읽는 테스트) (passed=136 · failed=0 — 진행 로그)

---

### Phase 2 — 결과 폴더 정리 · 전체 재실행 · 대조 → 확인 지점 1

**작업 내용**:

- [x] 실행 전 `git status --short storage/` 가 비어 있는지 확인
- [x] 결과 폴더 넷 삭제 → 포트폴리오 러너 전체 실행(`env -u VIRTUAL_ENV poetry run python scripts/backtest/run_portfolio_backtest.py`), 소요 시간 기록
- [x] 기존 결과 불변 — `git diff --stat storage/results/portfolio/` 에 지운 넷 외 변경 0, 새 폴더 둘은 untracked 로만 보인다
- [x] 등록 vs 그리드(세션 스크래치 스크립트) — 새 둘을 `get_portfolio_config` → `run_with_start_check(config, MAIN_START_DATE)` → `summarize_run` 으로 다시 내어 `combo_runs.csv` 이어 붙인 판의 같은 행과 시작일 · 끝날 · CAGR · MDD · Calmar · 매도 거래 수 · 연 회전율 · 국면 값을 CSV 자릿수로 대조하고, 러너가 쓴 `summary.json` 의 CAGR · MDD 와도 맞춘다
- [x] 새 결과 폴더 크기 · 「매매법별 손익」 데이터(`ledger.csv` · `per_method` 매매법 셋)가 있는지 기록
- [x] **확인 지점 1 — 사용자가 대시보드를 확인한다**(대시보드는 사용자가 실행 — `docs/COMMANDS.md` 의 포트폴리오 대시보드 명령과 볼 지점을 안내: 새 두 탭의 요약 지표, 「매매법별 손익」의 매매법 셋 · 몫 추이, 배분 조정일 표시)

**Validation**:

- [x] 기존 결과 불변 · 새 등록 위반 0 · 그리드와 수치 일치 (도구 출력은 진행 로그)
- [x] 사용자 대시보드 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 필요한 문서 업데이트 — `src/qbt/backtest/CLAUDE.md` 8 등록 문장. `docs/COMMANDS.md` · `README.md` 변경 없음을 다시 확인하고, `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md`(러너 소요 시간)의 변경 여부를 적는다
- [x] `docs/DEFERRED_FINDINGS.md` — 착수 전 결정 ① 의 답대로 두 항목(「등록 실험 시작일 미대조」 · 「배분 조정 사유 추론」의 등록 실험 이름 · 실측 · `build_experiment_config` 만 지킨다는 문구) 갱신
- [x] 근거 승격 — 설계서 0.2(공식 실험 목록 · 등록 결과), 0.3 할 일 5 의 삭제 목록에 이 계획서 추가, 6장 D76(착수 전 결정 ①), 15장 S9
- [x] 자동 포맷 적용 (`env -u VIRTUAL_ENV poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 11건 — 버그 1 [무거움 0 · 가벼움 1] · 그 외 10 · 조치: 버그 1(러너가 `min_start_date` 와 실제 시작일을 대조하지 않음)은 D76 으로 받아들여 고치지 않음(미룬 지적에 이미 있음) · 그 외 중 기록 사실 오류 2건 바로잡음(설계서 0.3 표 「계획서 8개」 → 9개, 진행 로그 shy20 파일 수 13 → 12) · 나머지 8건 고치지 않음 — 진행 로그)
- [x] 수정분 검증 (해당 없음 — 마지막 회차에 고친 버그 0. 바로잡은 기록 2건은 숫자 정정이라 도구 출력과 대조로 확인)
- [x] `poetry run python validate_project.py` (passed=857, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 보완 전략 채택 조합 10/10 · SHY 20% 기준선 등록과 25% 등록 실험 넷 삭제
2. 백테스트 / Q-2-2XS 80% + HAA 10% + 로테이션 10% 채택 등록
3. 백테스트 / 등록 실험의 채택 조합 · 같은 합계 기준선 교체와 조합 그리드 수치 일치 확인 · 설계서 D73 – D76 기록
4. 백테스트 / 결론 정리 — 25% 보완 전략 등록 정리와 매매법 셋 조합의 포트폴리오 러너 · 대시보드 첫 등록
5. 백테스트 / 채택 후보와 같은 비중의 기준선만 남기는 원칙에 따른 보완 전략 등록 실험 정리 및 미룬 지적 문구 갱신

## 7) 리스크(Risks)

- **러너 · 대시보드로 도는 첫 3매매법 실험** — 매매법 수를 2로 가정한 곳은 검색에서 0건이지만 화면은 그려 봐야 안다. 완화: 러너의 정합성 검사기(위반이면 멈춤) · 「매매법별 손익」 데이터 확인 · 확인 지점 1 에서 사용자가 화면을 본다. 대시보드가 깨지면 멈추고 고칠지 묻는다(대시보드 수정은 이 계획서 범위 밖이라 범위 조정이 필요하다)
- **기존 결과가 바뀜** — 등록 목록만 바뀌므로 바뀌면 안 된다. 완화: 실행 전 `storage/` 깨끗함 확인, 실행 뒤 `git diff --stat` 로 지운 넷 외 변경 0 확인. 다르면 멈추고 원인을 찾는다
- **결과 폴더 삭제** — 약 31M 를 지운다. 완화: git 추적 대상이라 `eca6405` 에서 되살릴 수 있다(되살리는 git 명령은 사용자가 한다)
- **새 등록이 그리드와 다름** — 같은 함수 · 같은 시작일이라 같아야 한다. 다르면 시작일 하한 · 러너 경로 차이를 먼저 의심하고 멈춘다
- **시세가 바뀜** — 다운로드하지 않는다. 결과 차이가 생기면 데이터 탓으로 돌리기 전에 `git status storage/stock/` 를 본다

## 8) 메모(Notes)

- 설계서 결정: D50(25% 등록) · D52(채택 후보와 같은 비중의 기준선만 남긴다) · D75(채택 조합 10/10, 등록 방식 포함)
- 대시보드 실행은 사용자가 한다(루트 `CLAUDE.md` 「스크립트 실행 규칙」)

### 진행 로그 (KST)

- 2026-10-05 21:03: 계획서 작성 (S9, Draft). 착수 전 확인 — 위 「착수 전 확인한 사실」. 착수 전 결정 ① 은 승인과 함께 답을 받는다
- 2026-10-05 21:16: 승인 — 사용자 「진행」. ① 에 따로 답하지 않아 계획서의 추천 (가)(문구만 맞춘다 — 비목표에도 그렇게 적혀 있다)로 받고 사용자에게 알렸다 → 설계서 D76. 「세부」 표는 그대로 승인된 것으로 본다
- 2026-10-05 21:20: Phase 0 — `TestSupplementConfigs` 를 새 계약 넷(채택 조합 = `build_combo_config(10, 10, spliced, 2007-06-22)` · 매매법 0.8 / 0.1 / 0.1, 기준선 = `build_experiment_config(shy, 20, …)` · 0.8 / 0.2, 시작일 하한은 이 둘뿐, 지운 25% 이름 넷은 ValueError)로 바꿨다. `pytest tests/qbt/test_portfolio_configs.py` → 「7 failed, 11 passed」 — 실패 이유는 새 이름 「실험명을 찾을 수 없습니다」 2 · 하한 집합이 25% 넷 1 · 「DID NOT RAISE ValueError」 4(레드). Phase 1 — `portfolio_configs.py` 를 기준선 SHY 20%(비중 = 채택 두 몫의 합) · 채택 조합 10/10 으로 바꾸고 `CANDIDATE_GOLD` · `CANDIDATE_HAA` · `CANDIDATE_ROTATION` import 를 지웠다. 이름 목록 — 전: `portfolio_d1` · `d1_2x` · `q2` · `q2_2xs` · `q2_2xs_shy25` · `gold25` · `haa25` · `rotation25` / 뒤: `portfolio_d1` · `d1_2x` · `q2` · `q2_2xs` · `portfolio_q2_2xs_shy20` · `portfolio_q2_2xs_haa10_rotation10`(표시 이름 「Q-2-2XS 80% + SHY(기준선) 20%」 · 「Q-2-2XS 80% + HAA 10% + 미국 약세 로테이션 10%」, 하한 둘 다 2007-06-22). 세 테스트 파일 「136 passed」(그린)
- 2026-10-05 21:20: Phase 2 — `git status --short storage/` 비어 있음 확인 → 결과 폴더 넷 삭제 → 포트폴리오 러너 전체 실행: 「exit=0 소요=15초」, 6개 실험 모두 「정합성 검증 통과 (7개 규칙 모두 정상)」, `portfolio_q2_2xs_shy20` 「start_date=2007-06-22 (데이터 기준 2007-04-09, … 실험 하한 2007-06-22)」 · `portfolio_q2_2xs_haa10_rotation10` 「start_date=2007-06-22 (데이터 기준 2007-06-22, …)」. `git diff --stat storage/results/portfolio/` 「57 files changed, 229820 deletions(-)」 — 지운 넷 밖의 변경 경로 0(기존 4개 실험 · `benchmark_qqq.json` 바이트 동일), 새 폴더 둘은 untracked(shy20 파일 12개 6.0M · haa10_rotation10 파일 22개 14M), `storage/` 의 그 밖 변경은 `meta.json` 뿐. 등록 vs 그리드(스크래치 `registration_check.py` — `get_portfolio_config` → `run_with_start_check(…, 2007-06-22)` → `summarize_run`, CSV 자릿수로 반올림): 두 실험 모두 「비교 항목 33개, 그리드 CSV 와 다른 것: []」(시작일 · 끝날 · CAGR · MDD · Calmar · 매도 거래 수 · 연 회전율 · 국면 13구간 × 2). 반올림 전 — shy20 CAGR 13.0797 · MDD -22.7338 · Calmar 0.575340, haa10_rotation10 14.0336 · -22.7651 · 0.616454. 러너 `summary.json` 의 `portfolio_summary` 와도 맞음(13.08 · -22.73 / 14.03 · -22.77). `per_method` — shy20 (q2_2xs 0.8 · shy 0.2), 조합 (q2_2xs 0.8 · haa 0.1 · rotation 0.1), `ledger.csv` · `netting.csv` 있음. 배분 조정일(미룬 지적 문구용, 스크래치): HAA 장부가 비중만 조정한 날 17일 — 계좌 사유가 빈 값(「배분 조정」으로 보임) 13일 · 「monthly」에 가려짐 4일(2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-04-01). 로테이션은 0일(늘 한 종목 100% 라 진입 · 청산만 있다). 체결 전후 표의 `allocation` 체결일 13. 확인 지점 1 대기
- 2026-10-05 21:27: 확인 지점 1 — 사용자 「확인 완료」. 마지막 Phase — 문서: `src/qbt/backtest/CLAUDE.md` 8 등록 문장을 「조합은 `build_combo_config`, 단독 후보 · 기준선은 `build_experiment_config`」로. `scripts/CLAUDE.md`(러너 절은 `min_start_date` 를 일반적으로만 서술) · `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md`(러너 15초 — 「나머지 백테스트 스크립트는 1분 이내」 그대로) · `docs/COMMANDS.md` · `README.md` 변경 없음. 미룬 지적(D76): 「등록 실험 시작일 미대조」의 이름 · 비교 대상(조합 그리드 CSV) · 실측(2026-10-05 둘 다 2007-06-22, 0건), 「배분 조정 사유 추론」의 ① 구성 함수 둘 · ② 실측(HAA 17일 중 4일 가려짐, 로테이션 0일) · 출처에 이 계획서. 근거 승격: 설계서 0.2(굵은 줄 · 단계 표에 이 계획서 행 · 「공식 실험 6개」), 0.3 맨 앞 안내 · 할 일 5 삭제 목록 9개, 6장 D76, 15장 S9(한 일 5 · 바뀐 파일 · 넘긴 것), 머리말 시각. black 「137 files left unchanged」
- 2026-10-05 21:38: `/code-review xhigh` 1회차 — 발견 11건. 분류와 조치: ① 러너가 `min_start_date` 와 실제 시작일을 대조하지 않음(새 조합은 엔진 유효 시작일 자체가 2007-06-22 라 여유 0) — 버그 · 가벼움(계획서 비목표 · D76 이 받아들임), 미룬 지적 「등록 실험 시작일 미대조」에 이미 있어 옮기지 않음(사용자 받아들임) ② 설계서 0.3 표가 「계획서 8개 삭제」(할 일 5 는 9개) — 그 외, 바로잡음 ③ 설계서가 이 계획서를 「완료」로 적었는데 계획서는 In Progress — 그 외, Done 으로 해소 ④ `meta.json` 이 untracked 새 결과 폴더를 가리킨다 — 그 외(커밋 범위), 사용자에게 새 폴더 둘 · 계획서를 함께 커밋하라고 안내 ⑤ 진행 로그 「shy20 파일 13개」 — 그 외, `ls | wc -l` 12 로 바로잡음(조합 22 는 같은 방법으로 22) ⑥ `build_experiment_config` docstring 「그리드와 등록 실험이 같은 구성임을 이 함수 하나가 보장한다」 — 그 외(기준 3) ⑦ 새 상수 `_ADOPTED_HAA_PCT` 등의 `_pct` 접미사가 전역 「비율 표기」(0 – 1)와 다르다 — 그 외(기준 3), 기존 `haa_pct` · `w_pct` · `COMBO_PCTS` 관용을 따랐다 ⑧ 절 주석이 비중 숫자(80 · 10 · 10)를 직접 적는다 — 그 외(기준 3) ⑨ 새 주석 · 테스트 docstring 이 지울 설계서의 결정 번호(D52 · D75)를 가리킨다 — 그 외(기준 3), 설계서 0.3 할 일 4(참조 정리)가 grep 으로 바꾼다 ⑩ 25% 이름 경계 테스트가 과거 상태를 테스트에 남기고 하한 집합 테스트와 겹친다 — 그 외(기준 3), 계획서 DoD 가 정한 경계 조건 ⑪ `docs/COMMANDS.md` 포트폴리오 러너 선행 조건이 대용 시세를 적지 않는다 — 그 외 · 닿지 않음(기준 1 · 3): 대용 · 합성 시세 10개가 git 추적(`git ls-files storage/stock`)이라 새로 받은 저장소에도 있다, 이 계획서 전부터의 문구. 고친 버그 0 이라 1회차로 끝낸다. 품질 검증 — Ruff · PyRight 통과, 「passed=857, failed=0, skipped=0」. 설계서 15장 S9 끝 시각 기록

---
