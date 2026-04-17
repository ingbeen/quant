# Implementation Plan: live 실패 알림 정책 전환 — allow-list (`run-daily` 만 알림)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-17 13:53
**마지막 업데이트**: 2026-04-17 14:45
**관련 범위**: live (CLI — `main()` 공통 예외 훅)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [src/live/cli.py](../../src/live/cli.py), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] `main()` 공통 예외 훅의 실패 알림 발송 조건을 **deny-list (`notify-failure` 제외)** 에서 **allow-list (`run-daily` 만 허용)** 로 전환한다.
- [x] 사용자 직접 실행 커맨드 (`init` / `reset` / `rebuild-data` / `drift` / `fetch-fills` / `backfill-chart-archive`) 의 실패는 **터미널 stderr + ERROR 로그** 로만 사용자에게 노출되며, FCM / 텔레그램 알림은 발송하지 않는다.
- [x] `run-daily` 실패 시의 기존 알림 동작 (FCM + 텔레그램 발송) 은 그대로 보존한다.
- [x] 관련 문서 ([src/live/CLAUDE.md](../../src/live/CLAUDE.md) "핵심 원칙 1", [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 알림 경로 설명) 의 문구를 신규 정책에 맞게 갱신한다.

## 2) 비목표(Non-Goals)

- **`notify-failure` 커맨드 제거 금지**: workflow 레벨 2 차 방어선 역할. 제거하지 않는다. `notify-failure` 자체는 호출되면 항상 알림을 발송하며, 공통 훅의 수정은 `main()` 의 예외 경로에만 적용된다.
- **알림 내용 / 포맷 변경 금지**: `_safe_notify_failure` 의 메시지 템플릿 / FCM payload / 텔레그램 포맷은 그대로.
- **로그 레벨 변경 금지**: 실패 시 ERROR 로그는 현재대로 유지 (알림 suppress 와 로그 suppress 는 별개).
- **CLI 표면 변경 금지**: 커맨드 제거 / 통합은 [Plan 1](PLAN_LIVE_CLI_COMMAND_CONSOLIDATION.md).
- **`reset` 동작 변경 금지**: [Plan 2](PLAN_LIVE_RESET_REDESIGN.md).
- **QBT 본체 수정 금지**.
- **`run-daily` 내부 알림 경로 (FCM 만료 토큰 정리 등) 수정 금지**.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `main()` 공통 예외 훅 ([src/live/cli.py:1288-1291](../../src/live/cli.py#L1288-L1291)):

```python
command_name = getattr(args, "command", None)
if command_name != "notify-failure":
    _safe_notify_failure(None, f"{command_name or 'unknown'} 실패: {exc}")
```

구조는 deny-list: "`notify-failure` 커맨드 자체" 만 재귀 방지를 위해 제외되고 나머지 모든 커맨드의 실패는 FCM / 텔레그램 알림을 발송한다.

문제는 커맨드별 실행 주체 분석 결과 **자동 실행 커맨드는 `run-daily` 한 가지뿐** 이라는 점이다 ([.github/workflows/daily_run.yml](../../.github/workflows/daily_run.yml)):

- cron / workflow_dispatch 로 자동 실행: `run-daily`
- 사용자 수동 실행: `init`, `reset`, `rebuild-data`, `drift`, `fetch-fills`, `backfill-chart-archive`
- workflow 내부 훅: `notify-failure`

사용자가 직접 터미널에서 실행한 커맨드가 실패하면 **stderr + ERROR 로그가 즉시 보이므로 FCM/텔레그램 알림은 중복/소음** 이 된다. 특히 `reset` 같은 파괴적 명령은 오히려 "실패했으니 재실행" 이라는 명확한 터미널 피드백이 더 효율적이다.

### 해결 방향

- **allow-list 전환**: "자동화된 명령만 알림" 이라는 설계 의도를 코드 한 줄로 드러낸다.
- **재귀 방지 자동 해결**: `notify-failure` 는 allow-list 에 없으므로 별도 제외 로직 불필요.
- **미래 안전성**: 새 조회/운영 커맨드를 추가해도 기본값이 "알림 없음" 이라 실수로 알림이 발송되지 않는다. 새 자동화 커맨드를 만들 때만 allow-list 에 명시적으로 추가.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 정책 / CLI 계층 ERROR 로그 사용 규칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — **"핵심 원칙 1 — 장애 시 자동 복구 금지 + 무조건 알림"** 섹션. 본 plan 에서 문구 수정 대상.
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / mock / 결정적 테스트
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `main()` 공통 예외 훅의 조건이 `if command_name in _NOTIFY_FAILURE_COMMANDS:` 로 변경되고 `_NOTIFY_FAILURE_COMMANDS = frozenset({"run-daily"})` 상수 도입됨 (Option B 채택)
- [x] `run-daily` 실패 시 `_safe_notify_failure` 가 호출됨을 검증하는 테스트 유지 / 확장 (`test_run_daily_failure_still_notifies` + 기존 `TestRunDailyPreTryCoverage` / `TestHistoryPersistFailureRaises` / `TestCalendarLoadFailureRaises`)
- [x] `init`, `reset`, `rebuild-data` (티커 명시/생략), `drift`, `fetch-fills`, `backfill-chart-archive` 실패 시 `_safe_notify_failure` 가 **호출되지 않음** 을 파라미터화 테스트 1 건으로 검증 (`TestMainAllowListNotifyPolicy::test_user_executed_command_failure_does_not_notify` 7 개 파라미터)
- [x] `notify-failure` 커맨드 자체가 예외를 던져도 재귀 알림이 발송되지 않음 (`TestNotifyFailureCommandNoRecursion` 2 건 유지)
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) "핵심 원칙 1" 섹션 문구가 "자동 실행 커맨드 (`run-daily`) 실패 시 알림 발송" 취지로 갱신됨
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 알림 경로 설명은 run-daily 맥락에서 기술되어 있어 allow-list 전환 후에도 기술상 정합 (본 plan 에서 별도 수정 없음).
- [x] [src/live/cli.py](../../src/live/cli.py) `main()` 함수의 docstring (에러 처리 정책 블록) 이 allow-list 방식을 반영하도록 갱신됨
- [x] `poetry run python validate_project.py` 통과 (passed=996, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase)
- [x] `README.md` **변경 없음** (알림 정책은 README 에 기재되어 있지 않음 — 재확인 완료)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/cli.py](../../src/live/cli.py) `main()` (1269-1293 라인) — 조건 변경 (1 줄) + docstring 갱신.
  - 구현 옵션:
    - **Option A (간단)**: `if command_name == "run-daily":` 로 직접 변경.
    - **Option B (확장성)**: 모듈 레벨 상수 `_NOTIFY_FAILURE_COMMANDS: frozenset[str] = frozenset({"run-daily"})` 도입 후 `if command_name in _NOTIFY_FAILURE_COMMANDS:` 로. 미래에 자동 커맨드 추가 시 상수만 수정.
  - 추천: **Option B** — 의도가 상수 이름에 명시되고, 향후 `monitor-drift` 등 자동 커맨드 추가 시 깔끔.
- [tests/live/test_cli.py](../../tests/live/test_cli.py) (또는 `test_cli_main.py` 에 해당하는 테스트 파일) — 알림 훅 검증 테스트 재구성.
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) "핵심 원칙 1" 섹션 — 문구 수정.
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — 알림 경로 섹션 확인 후 필요 시 갱신.
- `README.md`: **변경 없음** (재확인 후 확정. 알림 정책 관련 문구가 없을 것으로 예상).

### 데이터/결과 영향

- **자동화 파이프라인 영향 없음**: `run-daily` 실패 시 알림 발송은 기존 그대로 (workflow 의 `notify-failure` job 도 유지).
- **사용자 수동 실행 커맨드 실패 시 UX 변화**: FCM / 텔레그램 알림이 오지 않고 **터미널 stderr + ERROR 로그 + exit code 1** 만 남는다. 사용자가 터미널 앞에 있는 시나리오이므로 문제 없음.
- **RTDB / Git 정본 영향 없음**: 알림 훅의 변경은 예외 전파 이후 경로이며, state/charts 쓰기는 관련 없다.

## 6) 단계별 계획(Phases)

> 본 plan 은 에러 처리 정책 변경 (deny-list → allow-list) 에 해당하므로 [docs/CLAUDE.md](../CLAUDE.md) 의 Phase 0 (정책/인바리언트 테스트 먼저 고정) 권장 조건을 충족한다.

---

### Phase 0 — 알림 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] 신규 테스트 추가:
  - `TestMainAllowListNotifyPolicy::test_user_executed_command_failure_does_not_notify[<command>]` — 7 개 파라미터 (`init`, `reset`, `rebuild-data SPY`, `rebuild-data`, `drift`, `fetch-fills`, `backfill-chart-archive`) 각각 예외 발생 시 `_safe_notify_failure` 호출 없음 + exit 1.
  - `TestMainAllowListNotifyPolicy::test_run_daily_failure_still_notifies` — `run-daily` 실패 시 `_safe_notify_failure` 1 회 호출 + 메시지에 "run-daily" 포함.
  - 기존 `TestNotifyFailureCommandNoRecursion` 2 건 유지 — allow-list 방식에서도 재귀 방지 성립 재확인.
  - 기존 `TestRunDailyPreTryCoverage` / `TestHistoryPersistFailureRaises` / `TestCalendarLoadFailureRaises` 모두 run-daily 맥락이므로 유지.
- [x] mock 전략:
  - `cli_module._cmd_*` 함수를 `monkeypatch.setattr` 로 RuntimeError raise 함수로 교체하여 `main()` except 블록 진입 유도 (커맨드 내부 경로 mock 불필요).
  - `cli_module._safe_notify_failure` 를 spy 함수로 교체하여 호출 여부 / 횟수 / 메시지 검증.
  - 외부 I/O 는 기존 conftest 로 격리.
- [x] 구 테스트 정리:
  - `TestMainAlertHookCoversAllCommands` 클래스의 5 개 테스트 (init/drift/fetch-fills/rebuild-single/rebuild-all) 제거 — 정책이 반대 방향으로 바뀌어 의미가 뒤집혔으므로.
  - `TestFetchFills::test_fetch_fills_rtdb_init_failure_*` / `TestCmdBackfillChartArchive::test_backfill_rtdb_init_failure_*` 를 "notify 미발송 + exit 1" 검증으로 수정 (구체 경로의 회귀 방지 보존).

---

### Phase 1 — `main()` allow-list 전환 구현(그린 유지)

**작업 내용**:

- [x] [src/live/cli.py](../../src/live/cli.py) 모듈 레벨에 `_NOTIFY_FAILURE_COMMANDS: frozenset[str] = frozenset({"run-daily"})` 상수 추가 + 의도 설명 주석.
- [x] `main()` 의 except 블록 조건을 `if command_name in _NOTIFY_FAILURE_COMMANDS:` 로 변경. 기존 `or 'unknown'` fallback 제거 (allow-list 는 None 자동 제외).
- [x] `main()` 함수 docstring 재작성: allow-list 정책 / 사용자 직접 실행 커맨드 목록 / notify-failure 재귀 방지 명시.
- [x] Phase 0 레드 테스트 모두 그린 전환 (`poetry run pytest tests/live/test_alert_coverage.py -q` 14 passed).

**Validation**:

- [x] `poetry run pytest tests/live/test_alert_coverage.py -q` 14 passed. 전체 `validate_project.py` 는 마지막 Phase.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) "### 1. 장애 시 자동 복구 금지 + (자동 실행 커맨드만) 알림" 섹션 제목 + 본문 문구 재작성. 사용자 직접 실행 커맨드 목록과 "알림 없음" 명시. 마지막 조건 목록의 도입 문구도 "run-daily 경로 / 수동 명령 경로" 분기로 명확화.
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 의 알림 경로 기술은 run-daily 맥락에서 작성되어 있어 allow-list 전환 후에도 정합. 본 plan 에서 별도 수정 없음.
- [x] [README.md](../../README.md) 에 알림 관련 기술 없음을 재확인 — **변경 없음**.
- [x] `poetry run black .` 실행.
- [x] `poetry run python validate_project.py` 실행 → Ruff / PyRight / Pytest 전부 통과.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=996, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 실패 알림 정책 allow-list 전환 — run-daily 만 알림 발송
2. live / main() 공통 훅 간소화 (deny-list → allow-list) + CLAUDE.md 갱신
3. live / 사용자 직접 실행 커맨드 실패 시 FCM/텔레그램 알림 억제
4. live / 자동 실행(run-daily) 에만 실패 알림 한정 + 문서 동기화
5. live / 알림 경로 명확화 — allow-list 상수 도입 및 원칙 1 문구 갱신

## 7) 리스크(Risks)

- **리스크 1**: 미래에 `run-daily` 외의 커맨드가 Actions 에서 자동 실행되도록 추가될 때 allow-list 업데이트를 누락하면 알림이 오지 않는다.
  - 완화: allow-list 상수를 모듈 상단에 두고 docstring 으로 의도 명시. 신규 자동 커맨드 PR 리뷰 시 체크리스트에 포함.
- **리스크 2**: 기존 운영 중 사용자가 "reset 실패는 알림으로 받는다" 를 암묵적으로 기대하고 있었을 수 있다.
  - 완화: 사용자가 직접 실행하는 명령이므로 터미널에서 실패를 즉시 인지. CLAUDE.md 문구 갱신으로 공식화.
- **리스크 3**: Plan 2 (reset 재설계) 가 아직 적용되지 않은 상태에서 본 plan 만 적용되면, reset 실패 시 알림이 발송되지 않으면서 기존 순서 (RTDB 먼저 삭제) 의 불일치 위험이 알림 없이 장기 방치될 수 있다.
  - 완화: 가능하면 Plan 2 와 함께 또는 Plan 2 먼저 적용. 본 plan 은 Plan 1 / Plan 2 와 독립적으로 배포 가능하지만, 순서상 Plan 1 → Plan 2 → Plan 3 을 권장.
- **리스크 4**: 테스트에서 기존 deny-list 동작을 검증하던 케이스가 남아있으면 Phase 1 변경 시 레드가 된다.
  - 완화: Phase 0 의 파라미터화 테스트가 기존 케이스를 대체. 구 테스트 삭제 / 병합을 Phase 1 에서 수행.

## 8) 메모(Notes)

- Option B (상수 도입) 를 채택하면 미래에 `monitor-drift` 같은 자동 커맨드 추가 시 한 줄만 수정하면 된다. YAGNI 관점에서는 Option A (직접 `==`) 가 더 간단하지만, 본 plan 은 정책 변경을 명시적으로 코드에 드러내는 것이 목적이므로 상수 도입이 의도 전달에 유리.
- `_safe_notify_failure` 자체는 변경하지 않는다. 함수의 "절대 raise 하지 않음" 계약과 내부 try/except 는 allow-list 와 독립이다.
- Plan 1 / Plan 2 와 파일 충돌 범위가 작다 (`main()` 블록만 수정). 순서상 Plan 3 을 마지막에 적용해도 됨.

### 진행 로그 (KST)

- 2026-04-17 13:53: plan 초안 작성.
- 2026-04-17 14:40: Phase 0 — `TestMainAllowListNotifyPolicy` 클래스 신규 (7 파라미터화 + run-daily 단건) + 구 `TestMainAlertHookCoversAllCommands` 5 건 제거.
- 2026-04-17 14:42: Phase 1 — `_NOTIFY_FAILURE_COMMANDS = frozenset({"run-daily"})` 상수 도입 + `main()` 조건 전환 + docstring 재작성.
- 2026-04-17 14:43: 구 `test_*_rtdb_init_failure_triggers_notify` 2 건을 "notify 미발송 + exit 1" 로 수정.
- 2026-04-17 14:44: 문서 갱신 — `src/live/CLAUDE.md` 핵심 원칙 1 섹션 제목/본문 allow-list 반영.
- 2026-04-17 14:45: `black` + `validate_project.py` 통과 (passed=996, failed=0, skipped=0). 상태 → ✅ Done.

---
