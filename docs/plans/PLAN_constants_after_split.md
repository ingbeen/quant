# Implementation Plan: 데이터 이관 뒤 공통 상수 자리 정리

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-12 08:22
**마지막 업데이트**: 2026-11-12 08:42
**관련 범위**: common_constants, backtest(constants · analysis · period_performance · walkforward_verdict · allocators/haa), utils(data_loader), pyproject
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/utils/CLAUDE.md, tests/CLAUDE.md

---

## 1) 목표(Goal)

- [x] 목표 1: `ANNUAL_DAYS` · `TRADING_DAYS_PER_YEAR` 를 `src/qbt/backtest/constants.py` 로 옮긴다 — 이름 · 값 그대로
- [x] 목표 2: `REQUIRED_COLUMNS` · `PRICE_COLUMNS` 를 `src/qbt/utils/data_loader.py` 상단으로 옮긴다 — 이름 · 값 그대로
- [x] 목표 3: `TRADING_DAYS_PER_YEAR` 주석을 지금 쓰임에 맞게 고치고, `common_constants.py` 모듈 docstring 에서 옮긴 것(「연간 영업일」)을 뺀다
- [x] 목표 4: `pyproject.toml` 의 description 에서 「with CSV data management」를 뺀다

## 2) 비목표(Non-Goals)

- 경로 상수(`STOCK_DIR` · `*_SYNTHETIC_DATA_PATH` · 결과 폴더) — backtest 만 쓰지만 `src/qbt/CLAUDE.md` 「시세 파일 이름」이 경로 상수의 정본을 `common_constants.py` 로 정했다
- `ROUND_*` — backtest 와 scripts 가 쓰고, 루트 `CLAUDE.md` 「가격 반올림 자릿수」가 `common_constants.py` 의 `ROUND_PRICE` 를 기준으로 지목한다
- `COL_VOLUME` — `REQUIRED_COLUMNS` 를 옮기면 그것을 쓰는 src 코드는 data_loader 하나가 되지만, `COL_*` 시세 열 이름 묶음이고 테스트 11파일이 함께 import 한다
- `EPSILON` — 이관 전부터 backtest 전용이라 이번 이관이 만든 어긋남이 아니다
- 상수 이름 바꾸기(`_` 접두 등) — 옮기기만 한다
- 결과 재생성 — 값이 같아 결과가 바뀌지 않는다. 확인은 1분 이내 러너로만 한다(워크포워드 약 13분은 돌리지 않음 — Phase 마지막 「결과 불변」)
- `src/qbt/backtest/CLAUDE.md` 모듈 지도의 `constants.py` 나열에 더하기 — 그 나열은 이미 전부가 아니고, 전역 「문서」 원칙대로 목록을 늘리지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 2026-11-11 시세 받기 · 합성을 quant-data 로 옮기면서(`9530ce9`) tqqq 도메인과 utils 의 받기 · 합성 모듈이 지워졌다. 그 모듈들과 함께 쓰던 상수가 한 도메인 · 한 파일 전용으로 남았다 — 사용자 요청(2026-11-12 이관 사이드이펙트 점검 → 「추천대로」)

  | 상수 | 이관 직전에 쓴 도메인 | 지금 쓰는 코드 파일 |
  |---|---|---|
  | `ANNUAL_DAYS` | backtest · tqqq · utils | `backtest/analysis.py` · `backtest/period_performance.py` · `backtest/walkforward_verdict.py` |
  | `TRADING_DAYS_PER_YEAR` | backtest · tqqq · utils | `backtest/analysis.py` · `backtest/allocators/haa.py` |
  | `REQUIRED_COLUMNS` | tqqq · utils | `utils/data_loader.py` |
  | `PRICE_COLUMNS` | tqqq · utils | `utils/data_loader.py` |

  잰 법: 이관 직전은 `git grep -lw <상수> 9530ce9^ -- src scripts`, 지금은 `git grep -lw <상수> -- 'src/*.py' 'scripts/*.py'` (2026-11-12)
- 배치 규칙은 `src/qbt/CLAUDE.md` 「2. 상수 관리 (3계층)」 — 2개 이상 도메인이 쓰면 `common_constants.py`, 도메인 안 2개 이상 파일이면 `도메인/constants.py`, 1개 파일이면 그 파일 상단
- `TRADING_DAYS_PER_YEAR` 주석 「일일 비용과 연간 비용을 서로 환산할 때 쓴다」는 옮겨 간 레버리지 비용 모형의 쓰임이다. 지금은 Sharpe · Sortino 연율화(`analysis.py`)와 HAA 워밍업 행 수(개월 → 거래일, `haa.py`)에 쓰인다
- 이동으로 깨질 곳을 미리 쟀다(2026-11-12)
  - 테스트 · `docs/research/*.py` 는 네 상수를 import 하지 않는다(0파일). 문서는 이름으로만 적어(경로 없음) 옮겨도 깨지지 않는다
  - `import *` 0건. 저장소 밖에서 qbt 를 import 하는 곳은 verify-lab `reference/test_examples/conftest_qbt_example.py` 하나이고 `COL_*` 만 쓴다(실행되지 않는 참고 예시)
  - import 순환 없음 — `qbt.backtest.constants` 는 `typing` 만 import 한다. 배분 규칙이 `qbt.backtest.constants` 를 import 하는 관용은 이미 있다(`ewy_buffer_zone.py` · `us_weakness_rotation.py` 의 `ma_col_name`)
- `pyproject.toml` description 「Stock backtesting framework with CSV data management」 — 시세 관리는 quant-data 몫이 됐다. description 이 `poetry.lock` 정합에 닿지 않는지는 Phase 1 Validation 에서 `poetry check --lock` 으로 확인한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 · 「스크립트 실행 규칙」 · 「가격 반올림 자릿수」 · `docs/MEMORY.md`
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`
- 전역 `~/.claude/rules/python.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 목표 1 ~ 4 충족 — 네 상수의 정의가 새 자리에 한 곳씩, `qbt.common_constants` 에서 그 넷을 import 하는 곳 0건 → Phase 1 Validation
- [x] 회귀/신규 테스트 — 새 테스트는 두지 않는다(값 · 동작이 그대로라 새로 지킬 계약이 없다). 이 상수를 쓰는 계산(CAGR · Sharpe · Sortino · 구간 성과 · 시세 로딩)의 기존 테스트가 그대로 통과한다 → 품질 검증 passed=668
- [x] 결과 불변 — 1분 이내 러너 셋을 다시 돌려 `storage/results/` git diff 0 → 08:35 변경 0
- [x] 대시보드 4종 AppTest 예외 0건 → 08:35
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` · `README.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` 모두 변경 없음(네 상수를 이름으로만 적어 자리가 바뀌어도 맞다)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
      → 해당 없음: 옮긴 이유는 커밋 메시지가 말하고, 남긴 경로 상수 · `ROUND_*` 의 근거는 이미 `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md` 에 있다. `EPSILON` · `COL_VOLUME` 을 남긴 것은 리뷰가 다시 짚어 Done 보고에서 사용자에게 올린다
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
      → 해당 없음: 1회차 10건 모두 거르는 기준 3(그 외), 진행 로그 08:40
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py` — 네 상수의 정의와 빈 절 제목(「컬럼 그룹」) 삭제, 모듈 docstring 의 「연간 영업일」 삭제
- `src/qbt/backtest/constants.py` — 「백테스트 기본 설정」 절에 `ANNUAL_DAYS` · `TRADING_DAYS_PER_YEAR` 추가, 모듈 docstring 첫 항목에 연율화 일수
- `src/qbt/backtest/analysis.py` · `period_performance.py` · `walkforward_verdict.py` · `allocators/haa.py` — import 자리만
- `src/qbt/utils/data_loader.py` — `REQUIRED_COLUMNS` · `PRICE_COLUMNS` 정의, import 를 `COL_*` 로
- `pyproject.toml` — description
- `tests/` — 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · CLI 옵션 그대로)
- `README.md`: 변경 없음 (기능 · 구조 소개에 닿지 않음)

### 데이터/결과 영향

- 없음 — 이름 · 값이 같다. `storage/results/` 는 바뀌지 않아야 하고, 바뀌면 그것이 회귀다

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 이동과 문구 (그린 유지)

**작업 내용**:

- [x] `backtest/constants.py` 「백테스트 기본 설정」 절에 두 상수를 더한다 — `ANNUAL_DAYS` 주석은 그대로 옮기고, `TRADING_DAYS_PER_YEAR` 주석은 「연간 거래일 수(주말 · 공휴일 제외) — 일 단위와 연 단위를 서로 바꿀 때 씀」으로 쓴다(쓰는 곳을 나열하지 않는다)
- [x] `analysis.py` · `period_performance.py` · `walkforward_verdict.py` · `allocators/haa.py` 의 import 를 `qbt.backtest.constants` 로 옮긴다 — 이미 그 모듈을 import 하는 파일은 기존 import 줄에 더한다
- [x] `utils/data_loader.py` 상단(기존 `_SYNTHETIC_SUFFIX` 앞)에 `REQUIRED_COLUMNS` · `PRICE_COLUMNS` 를 둔다 — import 는 `COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME`
- [x] `common_constants.py` 에서 네 정의 · 빈 절 제목 · docstring 의 「연간 영업일」을 지운다
- [x] `pyproject.toml` description 을 「Stock backtesting framework」로

**Validation**:

- [x] `git grep -nwE "ANNUAL_DAYS|TRADING_DAYS_PER_YEAR|REQUIRED_COLUMNS|PRICE_COLUMNS" -- src scripts tests 'docs/research/*.py'` — 정의는 새 자리에 한 곳씩(`backtest/constants.py:25 · :28`, `utils/data_loader.py:16 · :19`), `common_constants` 를 거치는 import 0건
- [x] 새 자리의 값이 그대로다 — `365.25` · `252` · `['Date', 'Open', 'High', 'Low', 'Close', 'Volume']` · `['Open', 'High', 'Low', 'Close']`(`poetry run python -c` 출력), `common_constants` 에 남은 이름 `[]`
- [x] `poetry check --lock` exit 0

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` · `README.md` · `CLAUDE.md` 셋의 변경 여부를 확인해 DoD 에 적는다
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 결과 불변 — 실행 전 `storage/results/` 가 깨끗한지 보고, `run_single_backtest.py` · `run_portfolio_backtest.py` · `run_param_plateau_all.py` 를 COMMANDS 대로 돌린 뒤 `git diff --stat storage/results` 가 비었는지 본다. 워크포워드는 돌리지 않는다 — 같은 `analysis` 계산을 쓰고, `walkforward_verdict` 의 `ANNUAL_DAYS` 는 대시보드 문구라 아래 AppTest 가 지난다
- [x] 대시보드 4종 AppTest (`streamlit.testing.v1`) 예외 0건
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 10건 — 버그 0 [무거움 0 · 가벼움 0] · 그 외 10 · 조치: 없음 — 고칠 것 0 이라 1회차에서 끝냄, 목록은 진행 로그)
- [x] 수정분 검증 (해당 없음 — 1회차에 고친 것 없음)
- [x] `poetry run python validate_project.py` (passed=668, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 데이터 / quant-data 이관 뒤 정리
2. 데이터 / 이관 뒤 공통 상수 자리 정리 · 판 요약 재내보내기 · 받기 · 합성 계획서 삭제
3. 데이터 / 한 도메인 전용이 된 공통 상수 이동과 옛 시세 파일 이름 읽는 법 추가
4. 데이터 / 판 요약 커밋 기록 갱신과 이관 잔재 정리 — 결과 수치 변화 없음
5. 정리 / quant-data 분리가 남긴 상수 배치 어긋남 · 낡은 출처 기록 · 옮겨 간 계획서 정리

## 7) 리스크(Risks)

- import 를 빠뜨림 → PyRight · 테스트 수집이 그 자리에서 실패한다(조용히 지나가지 않음)
- 러너 재실행이 결과 파일을 덮어쓴다 → 값이 같으면 diff 0 이고, 다르면 그 자체가 회귀 신호다. `storage/results/` 는 git 추적이라 되돌릴 수 있고, 실행 전에 깨끗한지 본다
- 같은 작업 트리에 이 계획 밖의 변경(판 요약 재내보내기 · 연구 문서 주석 · 계획서 5개 삭제 · conftest docstring)이 먼저 있다 → 이 계획의 diff 와 섞이지 않게 진행 로그에 시작 시점의 변경 목록을 남기고, 커밋 후보는 이 계획의 변경만 대상으로 낸다

## 8) 메모(Notes)

- 점검 근거: 2026-11-12 이관 사이드이펙트 점검(대화) — 이 계획의 대상 외 항목(판 요약 · 문서 · 계획서 정리)은 계획서 없이 처리했다

### 진행 로그 (KST)

- 2026-11-12 08:22: 계획서 작성 (Draft)
- 2026-11-12 08:28: 사용자 승인(「추천대로」) → In Progress. 시작 시점의 이 계획 밖 변경 — `docs/plans/` 의 계획서 5개 삭제(`PLAN_download_revision` · `PLAN_leveraged_extension` · `PLAN_proxy_qqq` · `PLAN_proxy_spy` · `PLAN_proxy_tlt_gld`), `docs/research/` 세 문서의 머리말 「읽는 법」, `storage/stock/quant_data_edition.json`(재내보내기 — 커밋 칸만), `tests/qbt/conftest.py`(docstring 예시)
- 2026-11-12 08:31: Phase 1 완료 — 상수 4개 이동 · 주석 · pyproject description. Validation 셋 통과
- 2026-11-12 08:35: 마지막 Phase — 문서 변경 필요 없음 확인(`docs/COMMANDS.md` · `README.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` — 네 상수는 이름으로만 적혀 있음). `black .` 102 files left unchanged. 실행 전 `storage/results` 변경 0 → 단일 · 고원 · 포트폴리오 러너 모두 exit 0 → `storage/results` 변경 0. AppTest 4종 예외 0 · error 0 · warning 0
- 2026-11-12 08:40: `/code-review xhigh` 1회차 10건 — 버그 0, 모두 「그 외」라 고치지 않고 미룬 지적으로도 옮기지 않음(거르는 기준 3). 지적별:
  1. 연구 문서 세 곳의 머리말 「읽는 법」이 배당 때 다시 계산되는 것을 실물 수정주가로만 적음 — 합성도 상장 뒤 구간이 수정주가라 함께 바뀜(quant-data 판에서 TLT 합성 10,197행 중 10,171행) — 문서, 기준 3. 이 계획 밖의 문서 변경이라 사용자에게 올림
  2. `COL_VOLUME` 을 쓰는 src 코드가 `utils/data_loader.py` 하나로 줄었는데 `common_constants.py` 에 남음 — 정리, 기준 3. 비목표에 이유를 적었으나 규칙이 테스트를 세지 않는다는 지적이라 사용자에게 올림
  3. `EPSILON` 이 backtest 전용인데 `common_constants.py` 에 남음 — 정리, 기준 3(비목표). 사용자에게 올림
  4. 「읽는 법」 문장이 세 문서에 복제되고 quant-data 내부 경로를 적음, Q2 문서 본문에는 `_synthetic_max` 가 없음 — 문서, 기준 3
  5. `TRADING_DAYS_PER_YEAR` 주석 · 모듈 docstring 「연율화 일수」가 HAA 의 개월 → 거래일 환산을 덮지 못함 — 주석, 기준 3
  6. `data_loader.py` 의 두 상수가 공개 이름(같은 파일의 `_SYNTHETIC_SUFFIX` 와 다름)이고 `Final` list 라 내용 변경을 못 막음 — 정리, 기준 3(이름 바꾸기는 비목표 · 내용 변경은 그 list 를 고치는 새 호출 코드가 있어야 함)
  7. 새로 넣은 이웃 두 주석의 문체가 「쓴다」 · 「씀」으로 다름 — 주석, 기준 3
  8. `conftest.py` docstring 예시는 새 이름인데 호출처는 옛 이름 `_max.csv` — 문서, 기준 3
  9. 3계층 배치 규칙을 지키는 자동 검사가 없음 — 검사 보강, 막는 결함(상수 자리)이 「버그의 무게」 넷에 들지 않아 기준 3
  10. 지운 계획서 5개의 이름이 quant-data `docs/research/합성_시세_연장.md` 7장 표와 `docs/DEFERRED_FINDINGS.md` 출처에 남음 — 문서, 기준 3. 평문 이력이고(링크 아님 — 출처는 평문이 규칙) 내용은 quant git 이력에 있음
- 2026-11-12 08:42: `/commit` — 그 명령의 범위 규칙(staged 0건 → unstaged + untracked 전체)대로 이 계획 밖 변경까지 포함한 후보 5개를 옮김. 이 계획 변경만 따로 커밋할 때의 메시지는 Done 보고의 분리 제안에 냄 → Done

---
