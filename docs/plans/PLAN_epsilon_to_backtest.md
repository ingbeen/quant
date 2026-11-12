# Implementation Plan: `EPSILON` 을 backtest 도메인 상수로 옮기기

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-12 09:09
**마지막 업데이트**: 2026-11-12 09:22
**관련 범위**: common_constants, backtest(constants · analysis · parameter_stability · walkforward · engines 의 portfolio_data · portfolio_execution · portfolio_methods · portfolio_rebalance), tests(6파일 import)
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, tests/CLAUDE.md

---

## 1) 목표(Goal)

- [x] 목표 1: `EPSILON` 을 `src/qbt/backtest/constants.py` 로 옮긴다 — 이름 · 값 · 주석 그대로
- [x] 목표 2: `EPSILON` 을 쓰는 src 7파일 · 테스트 6파일의 import 를 `qbt.backtest.constants` 로 옮긴다
- [x] 목표 3: 두 모듈 docstring 의 항목 설명을 옮긴 뒤에 맞춘다(`common_constants` 에서 「수치 안정성」을 빼고 `backtest/constants` 에 더함)

## 2) 비목표(Non-Goals)

- 시세 CSV 열 이름(`COL_DATE` ~ `COL_VOLUME`) — 묶음으로 `common_constants.py` 에 둔다(사용자 결정 2026-11-12, `src/qbt/CLAUDE.md` 「2. 상수 관리」 예외 줄)
- 경로 상수 · `ROUND_*` — 직전 계획(PLAN_constants_after_split, 2026-11-12)의 비목표 그대로(경로 상수의 정본은 `src/qbt/CLAUDE.md` 「시세 파일 이름」, `ROUND_*` 는 루트 `CLAUDE.md` 「가격 반올림 자릿수」)
- `EPSILON` 이름 · 값 바꾸기, 쓰는 곳의 계산 바꾸기
- 결과 재생성 — 값이 같아 결과가 바뀌지 않는다. 확인은 1분 이내 러너로만 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `EPSILON` 은 src · scripts 에서 backtest 도메인 7파일만 쓰는데 `common_constants.py` 에 있다 — `src/qbt/CLAUDE.md` 「2. 상수 관리 (3계층)」로는 「도메인 내 2개 이상 파일 → `도메인/constants.py`」다. 직전 계획의 코드 리뷰(2026-11-12 1회차 3번 지적)가 짚었고, 사용자가 「추천대로」(옮김)로 정했다(2026-11-12)
- 이관 전부터 backtest 전용이었다 — 이번 이관이 만든 어긋남은 아니지만, 같은 규칙을 네 상수에 적용하면서 남겨 두면 다음 점검이 같은 질문을 한다
- 쓰는 곳(2026-11-12, `git grep -lw EPSILON`)
  - src 7파일 — `backtest/analysis.py` · `backtest/parameter_stability.py` · `backtest/walkforward.py` · `backtest/engines/portfolio_data.py` · `portfolio_execution.py` · `portfolio_methods.py` · `portfolio_rebalance.py`. scripts 0파일
  - 테스트 7파일 중 import 하는 것 6파일 — `test_allocators.py` · `test_analysis.py` · `test_ma_type_policy.py` · `test_walkforward_schedule.py` · `test_walkforward_selection.py` · `test_walkforward_summary.py`. `test_engine_common.py` 는 docstring · 주석 글에만 적는다
  - 문서는 이름으로만 적는다(`src/qbt/backtest/CLAUDE.md` Calmar 산식 · `tests/CLAUDE.md` 허용오차 표) — 자리가 바뀌어도 맞다
  - `docs/research/*.py` 0건 · `import *` 0건 · 저장소 밖(quant-notify · quant-data · verify-lab · research-lab)에서 qbt 의 `EPSILON` 을 가져오는 곳 0건
- import 순환 없음 — `qbt.backtest.constants` 는 `typing` 만 import 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 · 「스크립트 실행 규칙」 · `docs/MEMORY.md`
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md`
- 전역 `~/.claude/rules/python.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 목표 1 ~ 3 충족 — `EPSILON` 정의가 `backtest/constants.py` 한 곳, `qbt.common_constants` 에서 `EPSILON` 을 import 하는 곳 0건 → Phase 1 Validation
- [x] 회귀/신규 테스트 — 새 테스트는 두지 않는다(값 · 동작이 그대로라 새로 지킬 계약이 없다). `EPSILON` 을 쓰는 계산의 기존 테스트가 그대로 통과한다 → 품질 검증 passed=668
- [x] 결과 불변 — 1분 이내 러너 셋을 다시 돌려 `storage/results/` git diff 0 → 09:16 변경 0
- [x] 대시보드 4종 AppTest 예외 0건 → 09:16
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` · `README.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `tests/CLAUDE.md` 모두 변경 없음(`EPSILON` 을 이름으로만 적어 자리가 바뀌어도 맞다. `src/qbt/backtest/CLAUDE.md` 모듈 지도의 `constants.py` 나열은 직전 계획의 비목표대로 늘리지 않음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
      → 해당 없음: 옮긴 이유는 커밋 메시지와 `src/qbt/CLAUDE.md` 「2. 상수 관리」 규칙 자체가 말한다. 남긴 시세 CSV 열 이름의 근거는 같은 절의 예외 줄에 있다
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
      → 해당 없음: 1회차 6건 모두 거르는 기준 3(그 외), 진행 로그 09:19
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py` — `EPSILON` 과 그 절 제목(「기타 데이터 상수」) 삭제, 모듈 docstring 의 「수치 안정성」 삭제
- `src/qbt/backtest/constants.py` — 「백테스트 기본 설정」 절에 `EPSILON` 추가(주석 그대로), 모듈 docstring 첫 항목에 수치 안정성
- `src/qbt/backtest/` 7파일 — import 자리만(`analysis.py` · `parameter_stability.py` · `walkforward.py` · `engines/portfolio_data.py` · `engines/portfolio_execution.py` · `engines/portfolio_methods.py` · `engines/portfolio_rebalance.py`)
- `tests/qbt/` 6파일 — import 자리만
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · CLI 옵션 그대로)
- `README.md`: 변경 없음 (기능 · 구조 소개에 닿지 않음)

### 데이터/결과 영향

- 없음 — 이름 · 값이 같다. `storage/results/` 는 바뀌지 않아야 하고, 바뀌면 그것이 회귀다

## 6) 단계별 계획(Phases)

### Phase 1 — `EPSILON` 이동 (그린 유지)

**작업 내용**:

- [x] `backtest/constants.py` 「백테스트 기본 설정」 절 끝에 `EPSILON` 을 주석과 함께 옮기고, docstring 첫 항목에 「수치 안정성」을 더한다
- [x] src 7파일의 import 를 `qbt.backtest.constants` 로 옮긴다 — 이미 그 모듈을 import 하는 파일은 기존 import 줄에 더하고, `qbt.common_constants` import 에 남는 이름이 없으면 그 줄을 지운다
- [x] 테스트 6파일의 import 를 같은 방식으로 옮긴다
- [x] `common_constants.py` 에서 `EPSILON` · 빈 절 제목 · docstring 의 「수치 안정성」을 지운다

**Validation**:

- [x] `git grep -nw EPSILON -- src scripts tests 'docs/research/*.py'` — 정의는 `backtest/constants.py:31` 한 곳, `qbt.common_constants` 를 거치는 import 0건, 새 자리에서 가져오는 곳 src 7 · tests 6
- [x] 새 자리의 값이 `1e-12` 이고 `qbt.common_constants` 에 `EPSILON` 이 없다(`poetry run python -c` 출력 `1e-12 … False`)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` · `README.md` · `CLAUDE.md` 들의 변경 여부를 확인해 DoD 에 적는다
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 결과 불변 — 실행 전 `storage/results/` 가 깨끗한지 보고, `run_single_backtest.py` · `run_param_plateau_all.py` · `run_portfolio_backtest.py` 를 COMMANDS 대로 돌린 뒤 `git diff --stat storage/results` 가 비었는지 본다. 워크포워드(약 13분)는 돌리지 않는다 — `walkforward.py` 의 `EPSILON` 은 같은 값이고, 품질 검증의 워크포워드 테스트가 지난다
- [x] 대시보드 4종 AppTest (`streamlit.testing.v1`) 예외 0건
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 6건 — 버그 0 [무거움 0 · 가벼움 0] · 그 외 6 · 조치: 없음 — 고칠 것 0 이라 1회차에서 끝냄, 목록은 진행 로그)
- [x] 수정분 검증 (해당 없음 — 1회차에 고친 것 없음)
- [x] `poetry run python validate_project.py` (passed=668, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / EPSILON 을 backtest 도메인 상수로 이동
2. 백테스트 / backtest 전용 EPSILON 을 common_constants 에서 backtest/constants 로 이동과 import 정리
3. 백테스트 / 상수 3계층 규칙에 맞춘 EPSILON 자리 이동 — 값 · 결과 변화 없음
4. 백테스트 / 이관 점검에서 남은 공통 상수 어긋남(EPSILON) 정리
5. 백테스트 / src 7 · 테스트 6파일의 EPSILON import 를 backtest/constants 로 변경

## 7) 리스크(Risks)

- import 를 빠뜨림 → PyRight · 테스트 수집이 그 자리에서 실패한다(조용히 지나가지 않음)
- 러너 재실행이 결과 파일을 덮어쓴다 → 값이 같으면 diff 0 이고, 다르면 그 자체가 회귀 신호다. `storage/results/` 는 git 추적이라 되돌릴 수 있고, 실행 전에 깨끗한지 본다
- 직전 계획(PLAN_constants_after_split)과 그 밖 정리의 변경이 아직 커밋되지 않아 같은 작업 트리에 있다 → 진행 로그에 시작 시점 변경 목록을 남기고, Done 보고에서 커밋 분리를 제안한다

## 8) 메모(Notes)

- 점검 근거: 2026-11-12 이관 사이드이펙트 점검 → 직전 계획의 코드 리뷰 1회차 3번 지적 → 사용자 「추천대로」

### 진행 로그 (KST)

- 2026-11-12 09:09: 계획서 작성 (Draft). 같은 결정으로 계획서 없이 처리한 문서 변경 — `src/qbt/CLAUDE.md` 「2. 상수 관리」에 시세 CSV 열 이름 예외 한 줄, `docs/research/` 세 문서의 「읽는 법」 문구(합성도 배당 때 다시 계산됨)
- 2026-11-12 09:10: 사용자 승인 → In Progress. 직전 변경은 사용자가 `8e8b95c` 로 커밋해 작업 트리가 깨끗한 상태에서 시작(이 계획서 Draft 도 그 커밋에 들어감)
- 2026-11-12 09:14: Phase 1 완료 — 정의 `backtest/constants.py:31`, 새 자리 import src 7 · tests 6, `common_constants` 경유 0건, 값 `1e-12`. 테스트 import 수를 처음 `git grep -E` 의 `\b` 로 세어 0 이 나왔고 `-P` 로 다시 세어 6 — ERE 는 `\b` 를 읽지 않음
- 2026-11-12 09:16: 마지막 Phase — 문서 변경 필요 없음(`docs/COMMANDS.md` · `README.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `tests/CLAUDE.md` 는 `EPSILON` 을 이름으로만 적음). `black .` 102 files left unchanged. 실행 전 `storage/results` 변경 0 → 단일 · 고원 · 포트폴리오 러너 exit 0 → 변경 0. AppTest 4종 예외 0 · error 0 · warning 0
- 2026-11-12 09:19: `/code-review xhigh` 1회차 6건 — 버그 0, 모두 「그 외」라 고치지 않고 미룬 지적으로도 옮기지 않음(거르는 기준 3). 지적별:
  1. 옮긴 `EPSILON` 주석 「분모 0 방지 및 로그 계산 안정성 확보」가 쓰임과 다름 — src 의 쓰임은 0 에 가까운지 판정 · 부동소수 합계 · 경계 비교뿐이고 로그 계산 0건(직접 확인) — 주석, 기준 3. 사용자에게 올림
  2. 리스크 절의 「직전 계획의 변경이 커밋되지 않아 섞인다」가 09:10 로그(`8e8b95c` 로 커밋 · 작업 트리 깨끗)와 어긋남 — 계획서 서술, 기준 3. 그 리스크는 시작 전 커밋으로 사라졌고 커밋 분리 제안은 하지 않는다
  3. 마지막 Phase 의 문서 확인 결과가 DoD 줄에 없고 목표가 미체크 — 계획서 체크박스, 기준 3. Done 처리에서 반영
  4. 「마지막 업데이트」가 낡음 — 계획서 서술, 기준 3. Done 처리에서 반영
  5. `common_constants.py` 모듈 docstring 이 「반올림 규칙 상수」(`ROUND_*`) 절을 나열하지 않음 — 이 계획 전부터의 누락, docstring, 기준 3
  6. `src/qbt/backtest/CLAUDE.md` 모듈 지도의 `constants.py` 나열에 수치 안정성이 없음 — 문서, 기준 3. 직전 계획의 비목표(나열을 늘리지 않음)대로 둠
- 2026-11-12 09:22: `/commit` 전에 작업 트리에서 이 계획 밖 변경을 발견 — 루트 `CLAUDE.md` · `docs/COMMANDS.md` · `src/qbt/CLAUDE.md` 가 「판 요약 `quant_data_edition.json`」을 「매니페스트 `quant_data_manifest.json`」으로 바꿈(이 세션이 쓴 것 아님 — quant-data 에도 커밋 안 된 변경이 있어 다른 곳에서 진행 중으로 봄). 손대지 않고, 후보 5개는 이 계획의 변경(src 9 · tests 6 · 이 계획서)만 대상으로 냄 → Done

---
