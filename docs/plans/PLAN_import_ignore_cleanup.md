# Implementation Plan: 함수 안 import 상단 이동과 불필요한 무시 주석 정리 — 동작은 그대로 두고 린트 · 타입 검사가 재발을 막게 한다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-10 12:05
**마지막 업데이트**: 2026-10-10 12:39
**관련 범위**: tests(`tests/qbt/`), backtest(`portfolio_validation` · `engines/portfolio_methods` · `allocators/`), scripts(대시보드 3개), 설정(`pyproject.toml` · `pyrightconfig.json`)
**관련 문서**: `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(10절 · 11절 · 19절 5단계)

---

## 1) 목표(Goal)

- [x] 목표 1: 함수 · 클래스 안에 있는 import 를 전부 모듈 상단으로 옮기고, 린트가 다시 생기는 것을 막는다
- [x] 목표 2: 효과가 없는 타입 무시 주석(`# type: ignore` · `# pyright: ignore`)과 린트 무시 주석(`# noqa`)을 지우고, 타입 검사 · 린트가 다시 생기는 것을 막는다
- [x] 목표 3: 프로덕션 동작과 결과 파일은 하나도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- **테스트 내용 정리** — 늘 통과하는 테스트(점검 보고서 6-17) · 중복 테스트(5-11 · 7-9) · 효과 없는 픽스처(6-9)는 19절 11단계. 이 계획서가 지우는 테스트는 동적 import 를 쓰는 1개뿐이다(아래 설계 결정 3)
- **tests · scripts 의 타입 검사 완화를 걷는 일** — `pyrightconfig.json` 의 두 실행 환경이 꺼 둔 검사(`reportArgumentType` 등)는 그대로 둔다. 지금 무시 주석 대부분이 불필요한 이유가 이 완화이므로, 완화를 걷으면 다시 필요해진다(점검 보고서 11절 3번)
- **ruff 버전 올리기** — 함수 안 import 금지 규칙이 안정 규칙이 된 버전으로 올리면 미리보기 설정 없이 켤 수 있지만, 의존성 변경은 이 계획서 밖이다
- **`make_mock_strategy` 의 `name` 인자 삭제**(6-9 ⑤) — 반환 타입만 바꾼다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 5단계다. 4단계(4-1 포함)까지 끝났고(커밋 `e375205`), 이 단계는 「동작 변화 0 인 기계적 정리 한 커밋」으로 잡혀 있다
- 2026-10-10 지금 코드에서 다시 잰 값(점검 보고서의 190건 · 152줄은 커밋 `40011ad` 기준이고, 그 뒤 계획서 셋이 테스트를 더했다)

| 무엇 | 지금 | 근거 |
|---|---|---|
| 함수 · 클래스 안 import | 205건 · 28파일, 전부 `tests/` (src · scripts 0) | ruff 의 함수 안 import 검사(`PLC0415`) 집계 = AST 집계 |
| 동적 import | 1곳 — `tests/qbt/test_walkforward_summary.py` 의 `TestJsonRounding` 이 `importlib` 로 `scripts/backtest/run_walkforward.py` 를 읽는다 | `grep importlib` |
| 무시 주석 | 153줄 = `type: ignore` 101 · `pyright: ignore` 19 · `noqa` 33 (src 6 · scripts 11 · tests 136) | `grep` |

- **사본 재현**(저장소 밖 사본에 아래 Phase 순서를 그대로 적용, 2026-10-10)
  - import 205건을 상단으로 옮겨도 이름 충돌 0, `868 passed`(지금 저장소와 같은 수). 사본의 `storage/` 는 테스트 실행 뒤에도 원본과 같다 — 경로 상수를 패치한 뒤 함수 안에서 늦게 import 하던 자리는 없다(함수 안 import 와 패치를 함께 쓰는 6파일을 하나씩 확인: 패치 대상 이름과 함수 안 import 이름이 겹치지 않는다)
  - 옮기면 같은 import 가 합쳐져 무시 주석 7줄이 함께 사라진다(153 → 146줄)
  - 불필요한 타입 무시 주석 검출을 켜면 101줄이 걸린다(tests 91 · scripts 10 — `vendor` 경로를 타입 검사 경로에 더해 불필요해지는 3줄 포함). 지운 뒤 pyright 0 errors. 그중 1줄은 지우는 테스트(`TestJsonRounding`) 안에 있어, 테스트를 먼저 지우는 실제 순서에서는 100줄이다
  - 쓰이지 않는 `noqa` 는 18줄이다(`ARG002` 15 · `ARG005` 3 — 이 저장소 ruff 설정이 켜지 않은 규칙. src 3 · tests 15)
  - 남는 27줄 = 실제로 작동하는 `noqa: E712`(`== True` 비교 경고) 15 + 코드를 고치면 없어지는 9 + 정당한 3(frozen dataclass 에 값을 넣어 보는 시험)
  - 검산: 153 − 1(지우는 테스트) − 7(import 병합) − 100(불필요) − 18(쓰이지 않는 `noqa`) − 9(코드 수정) − 15(`E712`) = 3
  - 전부 적용한 사본: ruff 통과 · pyright 0 errors · `867 passed`(지우는 테스트 1개만큼 줄었다). 변경은 tests 33파일(+286 / −549) · src 5파일(6줄) · scripts 3파일(11줄) · 설정 2파일. 남는 무시 주석은 3줄이다

### 설계 결정

1. **함수 안 import 는 일괄 상단 이동** — 함수 안에 있어야 하는 import(순환 · 패치 순서 · import 시점 부작용)는 사본 재현에서 0건이었다. AST 로 옮기는 일회용 스크립트(세션 스크래치)를 쓰고, 중복 · 정렬은 ruff 자동 수정(`I` · `F811` · `F401`)에 맡긴다
2. **재발 방지는 ruff 의 `PLC0415`** — 이 저장소의 ruff 0.8.6 에서는 미리보기 규칙이라 `[tool.ruff.lint]` 에 `preview = true` 와 `explicit-preview-rules = true` 를 함께 둔다. 뒤의 설정이 「미리보기 규칙은 이름을 적은 것만 켠다」라서 다른 미리보기 규칙은 켜지지 않는다
   - 부작용 하나: 미리보기에서는 안 쓰는 변수 검사(`F841`)가 튜플 언패킹까지 본다 → 37건(`trades_df, equity_df, summary = …` 에서 안 쓰는 이름). ruff 자동 수정이 `_` 접두를 붙인다(`summary` → `_summary`). 전부 tests 다
3. **동적 import 테스트는 지운다** — `TestJsonRounding` 은 허용오차(±0.01 · ±0.0001)가 반올림 단위와 같거나 커서 러너의 반올림을 통째로 지워도 통과한다(점검 보고서 10절 3번). 막는 것이 없는 테스트라 지우면 `importlib` · 무시 주석 · `scripts/backtest/__pycache__` 부산물이 함께 사라진다
   - 버린 대안: 러너의 `_round_summary_for_json` 을 src 로 옮기고 정확 비교로 다시 쓴다 — 프로덕션 코드 자리가 바뀌어 「동작 변화 0 인 기계적 정리」를 벗어난다. 반올림 테스트의 허용오차 문제는 6단계(2-29)가 다룬다
4. **무시 주석의 재발 방지는 둘** — pyright 루트에 `reportUnnecessaryTypeIgnoreComment: error`(tests · scripts 환경의 같은 키 `none` 2줄 삭제), ruff 에 `RUF100`(쓰이지 않는 `noqa`)
5. **`noqa: E712` 15줄은 식을 고쳐 없앤다** — 대상 열 `rebalanced` · `is_month_end` 는 엔진이 파이썬 bool 로 만들고, 저장된 다섯 실험의 `equity.csv` · `state_log.csv` 에서 dtype bool · 결측 0 이다(2026-10-10 확인). `df[df["rebalanced"] == True]` → `df[df["rebalanced"]]`, 스칼라 1곳은 `assert not …`
6. **코드 수정 9줄 · 정당한 3줄**
   - `test_walkforward_schedule.py` 6줄: `isinstance(…, BufferZoneStrategy)` 로 좁힌 뒤 비공개 속성을 읽는다
   - `test_backtest_engine.py` 3줄: `make_mock_strategy` 의 반환 타입을 `MagicMock` 으로
   - frozen 시험 3줄: mypy 식 `# type: ignore[misc]` 를 `# pyright: ignore[reportAttributeAccessIssue]` 로 바꾸고, 모든 예외를 통과시키는 `pytest.raises((AttributeError, Exception))` 를 `dataclasses.FrozenInstanceError` 로 좁힌다 — pyright 는 mypy 식 괄호 코드를 읽지 않고 줄 전체를 무시하므로, 그대로 두면 그 줄에 앞으로 생길 오류까지 가린다

### 관용에서 벗어나는 점 하나 (승인 필요)

- 전역 파이썬 규칙은 「품질 검증은 `validate_project.py` 로만 — `ruff` · `pyright` 를 따로 돌리지 않는다」이다. 이 계획서는 Phase 1 · 2 에서 **ruff 와 pyright 를 «변환 도구»로 직접 부른다** — ruff 는 자동 수정(`--fix`), pyright 는 지울 주석 목록(`--outputjson`)을 얻는 데 쓴다. `validate_project.py` 는 두 기능을 내보내지 않는다. 품질 검증 자체는 규칙대로 마지막 Phase 에서 `validate_project.py` 로만 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 함수 · 클래스 안 import 0건, `importlib` 로 스크립트를 읽는 테스트 0건(ruff 가 `PLC0415` 로 검사한다)
- [x] 무시 주석이 frozen 시험 3줄만 남는다(`grep`), 불필요한 타입 무시 주석 · 쓰이지 않는 `noqa` 가 품질 검증에서 오류로 잡힌다(설정)
- [x] 동작 변화 0 — 포트폴리오 러너를 사본에서 다시 돌린 결과가 저장된 결과와 같고, 대시보드의 리밸런싱 행 선택이 다섯 실험에서 수정 전과 같다
- [x] 회귀/신규 테스트 — 해당 없음(동작을 바꾸지 않는다). 테스트 수는 868 → 867(지우는 1개)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`(10절 · 11절 · 19절 5단계 처리 표시). `README.md` · `docs/COMMANDS.md` · 각 `CLAUDE.md` 변경 없음(린트 · 타입 설정을 말하는 문서가 없다 — `grep` 확인)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] 미룬 지적 옮김 — 해당 없음(옮길 것 0 · 이 계획서가 고친 미룬 지적 항목 0). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `tests/qbt/` — import 이동 28파일을 포함해 약 33파일(무시 주석 · `_` 접두 · 손 수정)
- `src/qbt/backtest/portfolio_validation.py` · `src/qbt/backtest/engines/portfolio_methods.py` — `== True` 비교 3곳
- `src/qbt/backtest/allocators/ewy_buffer_zone.py` · `haa.py` · `us_weakness_rotation.py` — 쓰이지 않는 `noqa` 3줄
- `scripts/backtest/app_portfolio_backtest.py` · `app_single_backtest.py` · `app_walkforward.py` — 불필요한 무시 주석 10줄, `== True` 비교 1곳
- `pyproject.toml` — ruff 설정 4줄(`preview` · `explicit-preview-rules` · `PLC0415` · `RUF100`)
- `pyrightconfig.json` — 3곳(`vendor` 경로 · 루트 검출 키 · 환경 2곳의 `none` 삭제)
- `docs/AUDIT_REPORT.md` — 처리 표시
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · 옵션 그대로)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 없음. `storage/` 의 어떤 파일도 바뀌지 않는다(검증용 재실행은 사본에서 한다 — 저장소에서 러너를 돌리면 `meta.json` 의 실행 시각이 바뀐다)

## 6) 단계별 계획(Phases)

### Phase 1 — 함수 안 import 를 상단으로(그린 유지)

**작업 내용**:

- [x] `tests/qbt/test_walkforward_summary.py` 의 `TestJsonRounding` 삭제(먼저 지워야 그 import 가 상단으로 올라가지 않는다)
- [x] 일회용 AST 스크립트로 `tests/` 의 함수 · 클래스 안 import 를 상단으로 이동 — 이름 충돌이 하나라도 나오면 멈추고 보고한다
- [x] `ruff check --fix --select I,F811,F401 tests` 로 중복 · 정렬 · 안 쓰는 import 정리
- [x] `tests/qbt/test_portfolio_planning.py` — 이동으로 한 줄이 된 별칭 import `AssetState as NewAssetState`(엔진 모듈 경유)를 `portfolio_types.AssetState` 직접 import 로 바꾸고 사용 8곳의 이름을 맞춘다(점검 보고서 15-T 가 10절과 함께 하라고 적은 것. 사본에서 21 passed)
- [x] `pyproject.toml` — `preview = true` · `explicit-preview-rules = true` · `select` 에 `PLC0415`
- [x] 미리보기에서 새로 잡히는 `F841`(튜플 언패킹의 안 쓰는 이름) 을 `ruff check --select F841 --fix --unsafe-fixes` 로 `_` 접두 — 건수가 사본 재현(37)과 다르면 멈추고 확인한다
- [x] 부산물 `scripts/backtest/__pycache__/*.pyc` 삭제(gitignore 대상, 스크립트를 import 하는 코드가 없어진다)

**Validation**:

- [x] 변환에 쓴 ruff 의 남은 진단 0건(함수 안 import 0건 포함)
- [x] 바뀐 테스트 파일만 `poetry run pytest <파일들>` — 전부 통과
- [x] `git status` 에서 `storage/` 변경 0

---

### Phase 2 — 무시 주석 정리(그린 유지)

**작업 내용**:

- [x] `pyrightconfig.json` — `extraPaths` 에 `vendor/streamlit-lightweight-charts-v5`, 루트에 `reportUnnecessaryTypeIgnoreComment: error`, tests · scripts 환경의 같은 키 `none` 삭제
- [x] `pyright --outputjson` 이 「불필요」로 가리킨 줄의 무시 주석만 일회용 스크립트로 삭제 — 다른 종류의 진단이 섞여 있거나 건수가 100(사본 재현 101 − 지운 테스트 안의 1)과 다르면 멈추고 확인한다
- [x] `pyproject.toml` `select` 에 `RUF100`, `ruff check --fix` 로 쓰이지 않는 `noqa` 삭제(사본 재현 18)
- [x] 손 수정 — `isinstance` 좁히기 6줄 · `MagicMock` 반환 타입 3줄 · frozen 시험 3줄 · `== True` 15줄(설계 결정 5 · 6)

**Validation**:

- [x] 변환에 쓴 pyright · ruff 의 남은 진단 0건
- [x] 남은 무시 주석이 frozen 시험 3줄뿐(`grep`)
- [x] 바뀐 테스트 파일만 `poetry run pytest <파일들>` — 전부 통과

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 동작 변화 0 확인(스크래치) — ① 수정한 저장소를 사본으로 떠서 `run_portfolio_backtest.py` 를 돌리고 `storage/results/portfolio/` 가 저장소의 저장된 결과와 같은지(`meta.json` 제외) ② 다섯 실험의 `equity.csv` 에서 `df[df["rebalanced"] == True]` 와 `df[df["rebalanced"]]` 가 같은 행인지
- [x] 문서 — `docs/AUDIT_REPORT.md` 처리 표시. `README.md` · `docs/COMMANDS.md` · 각 `CLAUDE.md` 변경 없음
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 4건 — 버그 1 [무거움 0 · 가벼움 1] · 그 외 3 · 조치: 그 외 3 반영 · 버그 1 미조치 — 잘못된 입력에서 멈추는 쪽이고 지금 산출물 0건)
- [x] 수정분 검증 — 해당 없음 (마지막 회차에 고친 버그 없음. 반영한 그 외 3건은 빈 줄 · 독스트링 · 설정 주석이라 수정 전 사본과 AST 대조로 확인 — 41파일 중 40 동일 · 1은 모듈 독스트링만 다름)
- [x] `poetry run python validate_project.py` (passed=867, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 테스트 / 함수 안 import 상단 이동과 불필요한 무시 주석 정리
2. 테스트 / 함수 안 import 203건 상단 이동, 타입 · 린트 무시 주석 153줄을 3줄로 축소, 재발 방지용 ruff · pyright 설정 추가
3. 테스트 / 함수 안 import 와 효과 없는 무시 주석이 다시 쌓이지 않도록 린트 · 타입 검사 규칙 추가
4. 테스트 / 점검 보고서 5단계 처리 — import 일괄 이동 · 무시 주석 삭제 · 동적 import 테스트 삭제
5. 테스트 / PLC0415 · RUF100 · 불필요한 타입 무시 검출 도입과 그에 맞춘 테스트 코드 기계적 정리

## 7) 리스크(Risks)

- **import 를 올리면 실행 시점이 바뀐다** — 함수 안 import 는 그 테스트가 돌 때, 상단 import 는 수집 때 실행된다. 패치한 값을 늦게 읽던 테스트가 있으면 실경로를 건드릴 수 있다. 완화: 사본 재현에서 `storage/` 무변경 · 868 passed 를 확인했고, Phase 1 뒤 저장소에서도 `git status` 로 `storage/` 무변경을 본다
- **미리보기 설정** — `preview = true` 는 안정 규칙의 미리보기 동작도 켠다. 지금 버전에서 드러난 것은 `F841` 하나다. ruff 를 올리면 다른 것이 더 잡힐 수 있다 — 그때 품질 검증이 멈추는 쪽으로 드러난다
- **무시 주석 검출을 오류로** — 앞으로 타입 정의가 바뀌어 불필요해진 주석이 생기면 품질 검증이 멈춘다. 의도한 동작이다(주석이 조용히 쌓이지 않는다)
- **diff 가 크다(약 43파일)** — 대부분 기계적 이동이라 리뷰에서 실제 변경이 묻힐 수 있다. 완화: 손 수정 27줄과 설정 2파일은 진행 로그에 자리(`파일:줄`)를 따로 적는다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 10절 · 11절 · 19절 5단계
- 이 계획서와 별개로 같은 날 문서 2개를 먼저 고쳤다(코드 변경 아님): `docs/DEFERRED_FINDINGS.md` 에서 버리기로 정한 5건 삭제, `docs/AUDIT_REPORT.md` 19절에 배정이 빠져 있던 항목 번호 배정

### 진행 로그 (KST)

- 2026-10-10 12:05: 계획서 작성(Draft). 지금 코드에서 수치를 다시 재고(205건 · 153줄), 저장소 밖 사본에 Phase 순서를 그대로 적용해 최종 상태(ruff 통과 · pyright 0 · 867 passed · `storage/` 무변경)를 확인했다. 자체 검증 — ① 테스트 삭제를 import 이동 «앞»에 둬야 지운 테스트의 import 가 상단에 남지 않는다(사본에서 순서를 반대로 했다가 안 쓰는 import 2건이 남았다) ② 쓰이지 않는 `noqa` 는 프로젝트 규칙을 켠 채 재야 한다(`--select RUF100` 단독은 작동 중인 `E712` 15줄까지 「쓰이지 않음」으로 센다) ③ `== True` 를 걷는 근거(열이 늘 bool)를 결과 파일에서 확인했다 ④ 「불필요」 101줄 중 1줄이 지우는 테스트 안에 있어 실제 순서의 기대 건수를 100 으로 고쳤다 ⑤ 점검 보고서 15-T 의 `NewAssetState` 별칭 정리(「10절과 함께」)를 Phase 1 에 넣었다 ⑥ Phase 검증 문구를 「변환 도구의 남은 진단 0」으로 — 품질 검증 명령은 마지막 Phase 에서만 돈다
- 2026-10-10 12:10: 승인 — 사용자 「승인」. 문서 2개 변경은 사용자가 먼저 커밋함(`b870926`, 이 계획서 초안 포함 — 작업 트리 깨끗). Phase 1 착수
- 2026-10-10 12:12: Phase 1 — `TestJsonRounding` 삭제 → AST 스크립트로 203건 이동(205 − 지운 테스트 안의 2, 28파일, 이름 충돌 0) → ruff `I` · `F811` · `F401` 자동 수정 157건 → `test_portfolio_planning.py` 별칭 정리(`NewAssetState` 0건) → `pyproject.toml` 미리보기 · `PLC0415` → `F841` 정확히 37건을 `_` 접두로 → ruff 남은 진단 0. 바뀐 테스트 30파일 478 passed, `storage/` 변경 0. 부산물 `.pyc` 2개 삭제
- 2026-10-10 12:13: Phase 2 — `pyrightconfig.json` 3곳 → 「불필요」 진단 **99건**(tests 89 · scripts 10)으로 기대 100 과 달라 멈추고 확인: 사본과 파일별로 대조하니 차이는 둘뿐이다 — 지운 테스트 안의 1줄(예상)과 `test_portfolio_planning.py` 의 1줄(Phase 1 에서 별칭 import 줄을 지우며 그 줄의 주석이 함께 사라졌다. 자체 검증 ⑤ 를 넣으면서 기대 건수에 반영하지 못했다). 나머지 파일은 사본과 같아 진행 — 99줄 삭제(13파일), pyright 0 errors → `RUF100` 정확히 18건 자동 삭제 → 손 수정 27줄
  - 손 수정 자리: `== True` 15 — `portfolio_validation.py` `_check_rebalance_weight_consistency` · `_check_method_rebalance_weight_consistency`, `portfolio_methods.py` `summarize_methods`, `app_portfolio_backtest.py` 리밸런싱 마커, `test_portfolio_execution.py` 5(스칼라 1곳은 `assert not …`) · `test_portfolio_state_log.py` 1 · `test_portfolio_backtest_scenarios.py` 5 / `isinstance` 좁히기 6 — `test_walkforward_schedule.py` 일정 테스트 둘 / `MagicMock` 반환 타입 3 — `test_backtest_engine.py` `make_mock_strategy` / frozen 3 — `test_buffer_zone.py` 1 · `test_buffer_zone_contracts.py` 2(독스트링의 「또는 AttributeError」도 맞췄다)
  - 검산(실제): 153 − 1(지운 테스트) − 7(import 병합) − 1(별칭 import 줄) − 99 − 18 − 9 − 15 = 3
  - 변환 도구의 남은 진단 0(ruff · pyright), 남은 무시 주석은 frozen 3줄, 바뀐 테스트 33파일 528 passed
- 2026-10-10 12:15: 마지막 Phase — `black` 적용(11파일). 프로덕션 쪽 diff 는 `== True` 4곳 · 주석 13줄 · 설정 2파일뿐임을 줄 단위로 확인. 동작 변화 0 확인: ① 수정한 저장소를 스크래치 사본으로 떠 `run_portfolio_backtest.py` 실행 — 다섯 실험 정합성 통과, `storage/results/portfolio/` 51개 파일이 저장소와 바이트 단위로 같다(다른 것은 `meta.json` 의 실행 시각뿐) ② 다섯 `equity.csv` 에서 `df[df["rebalanced"] == True]` 와 `df[df["rebalanced"]]` 가 같다(리밸런싱 행 0 · 59 · 73 · 105 · 0). 저장소의 `storage/` 변경 0
- 2026-10-10 12:30: `/code-review xhigh` 1회차 — 발견 4건, 고칠 닿는 버그 0
  - 미조치 버그 1(가벼움): 대시보드 리밸런싱 마커가 CSV 에서 읽은 `rebalanced` 열을 그대로 마스크로 써서, 열이 bool 로 읽히지 않으면(빈 칸 · 잘린 행 · 0/1) 전에는 조용히 False 로 넘기던 것이 예외로 멈춘다. 저장된 다섯 실험은 전부 bool · 결측 0 이라 지금 산출물 0건이고, 틀리는 방향이 「잘못된 입력에서 멈춘다」(거르는 기준 2)라 고치지 않고 옮기지도 않는다 — 조용히 넘기지 않는 쪽이 이 저장소의 방향이기도 하다(전역 파이썬 규칙 「불가능 조건 처리」, 점검 보고서 9-9 · 6-15). 엔진 메모리 경로 3곳은 파이썬 bool 로 만들어 해당 없음
  - 반영한 그 외 3: ① `test_walkforward_summary.py` 모듈 독스트링의 「JSON 반올림」(지운 테스트를 가리킨다) 삭제 ② `pyproject.toml` 주석 — 미리보기가 안정 규칙의 동작(`F841`)도 바꾼다는 것과 두 줄을 걷는 조건을 적었다 ③ import 를 뺀 자리에 남은 빈 줄 150줄 삭제(27파일 — 함수 독스트링 · 구획 주석 바로 뒤. HEAD 에도 있던 빈 줄은 함수 이름 · 주석 글로 맞춰 남겼다. 일회용 스크립트가 파일마다 AST 동일을 확인)
  - 리뷰가 직접 확인한 것: 함수 안 import 0건(AST), 패치한 값을 늦게 읽던 자리 0건, 바뀐 테스트 파일을 하나씩 따로 수집해도 import 순서 문제 없음, `portfolio_engine.AssetState` 는 `portfolio_types.AssetState` 와 같은 클래스
  - 리뷰가 다시 찾았지만 앞선 계획서가 이미 판정한 것 5건(판단 문구 꼬리 — 점검 보고서 1-10, 캐시 헬퍼 두 벌 · 상한 — 7-1, 공통 기간 함수의 기존 열 · `eval_ma_window` · 저거래 필터 — 각 계획서에서 닿지 않음으로 거름)은 그대로 둔다
- 2026-10-10 12:36: 수정 전 사본(스크래치 `r1_before/`, 43파일)과 대조 — 리뷰 반영분은 파이썬 41파일 중 40 AST 동일 · 1(모듈 독스트링), `pyproject.toml` 은 주석 3줄, `pyrightconfig.json` 동일. 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=867, failed=0, skipped=0. `storage/` 변경 0
- 2026-10-10 12:37: 재발 방지 설정의 변형 확인(스크래치 사본에 테스트 함수 하나를 더해 함수 안 import · 불필요한 `type: ignore` · 쓰이지 않는 `noqa` 를 넣음) — 변형 전 ruff 통과 · pyright 0 errors, 변형 후 `PLC0415` 1 · `RUF100` 1 · `reportUnnecessaryTypeIgnoreComment` 1. 저장소에는 넣지 않았다
- 2026-10-10 12:37: 미룬 지적 — 옮길 것 없음(미조치 버그 1은 기준 2, 나머지는 반영). 이 계획서가 고친 `DEFERRED_FINDINGS.md` 항목 없음. 근거 승격 — 미리보기 설정의 이유 · 부작용 · 걷는 조건은 `pyproject.toml` 주석, 남긴 무시 주석 3줄은 pyright 규칙 코드가 이유를 말한다, 처리 사실과 「요약 반올림 함수를 실행하는 테스트가 없다」는 점검 보고서 10절 · 11절 처리 표시. Scope 와 달라진 것: 리뷰 반영으로 빈 줄 150줄 삭제가 더해졌다(파일 목록은 같다)
- 2026-10-10 12:39: `/commit` — 대상은 unstaged 전체(staged · untracked 없음, 45파일). 모두 이 계획서 한 묶음이라 분리 제안 없음. 후보 5개를 옮기고 Done

---
