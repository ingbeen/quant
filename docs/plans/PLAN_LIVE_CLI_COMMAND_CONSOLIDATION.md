# Implementation Plan: live CLI 커맨드 통합 (init-data / history / backfill-history 제거 + rebuild-data 흡수)

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
**마지막 업데이트**: 2026-04-17 14:15
**관련 범위**: live (CLI 표면)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [src/live/cli.py](../../src/live/cli.py), [README.md](../../README.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] `init-data` 서브커맨드를 제거하고, `rebuild-data` 의 `ticker` 위치 인자를 선택형(`nargs="?"`) 으로 확장하여 티커 생략 시 전체 티커 재다운로드 동작을 지원한다.
- [x] `history` 서브커맨드를 제거한다 (사용자는 GitHub UI 에서 `qbt-live-state` 리포의 `history/summary.jsonl` 을 직접 조회한다).
- [x] `backfill-history` 서브커맨드를 제거한다 (실제 발동 시나리오가 없어 커맨드 표면에서 삭제).
- [x] CLI 표면을 11 → 8 커맨드로 축소하고, argparse / 테스트 / 문서 (README / TEST_MANUAL / src/live/CLAUDE.md / cli.py 모듈 docstring) 를 일관되게 갱신한다.

## 2) 비목표(Non-Goals)

- **`reset` 동작 변경 금지**: 순서 재배치 / 주가 차트 재생성 통합은 별도 [Plan 2](PLAN_LIVE_RESET_REDESIGN.md) 에서 다룬다.
- **알림 정책 변경 금지**: `main()` 공통 예외 훅의 allow-list 전환은 별도 [Plan 3](PLAN_LIVE_FAILURE_NOTIFY_ALLOWLIST.md) 에서 다룬다.
- **`backfill-chart-archive` 유지**: 스플릿 대응 전용으로 사용 사례가 남아있으므로 제거하지 않는다 (옵션/동작 변경 없음).
- **`notify-failure` 유지**: workflow 레벨의 2차 방어선 역할. 제거하지 않는다.
- **QBT 본체 (`src/qbt/`) 수정 금지**: 루트 CLAUDE.md 원칙 준수.
- **RTDB / Git 정본 스키마 변경 금지**: 제거되는 커맨드가 읽던 JSONL 파일 형식은 그대로 두며, 다른 커맨드 / `run-daily` 가 계속 사용한다.
- **`history.py` 의 `load_user_trades_raw` / `load_balance_adjusts_raw` / `load_signal_history_raw` 등 `*_raw` 로더 삭제 여부는 본 plan 범위 밖**: 다른 호출자가 있거나 미래 복원에 쓰일 수 있으므로 제거는 별도 판단. 본 plan 에서는 CLI 표면만 정리한다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `live.cli` 는 11 개의 서브커맨드를 제공한다. 사용 빈도 / 실 발동 시나리오 / 다른 수단으로의 대체 가능성을 종합하면 다음 3 개는 제거 가치가 크다:

1. **`init-data`** — 내부 동작이 "모든 운영 티커에 대해 `rebuild_full_csv(period='max')` 호출" 이며, `rebuild-data TICKER` 와 유일한 차이는 대상 범위뿐이다. `rebuild-data` 의 ticker 인자를 선택형으로 확장하면 같은 기능을 제공할 수 있어 커맨드 중복이 해소된다.
2. **`history`** — `summary.jsonl` 의 최근 N 줄을 stdout 에 출력하는 읽기 전용 조회. `qbt-live-state` 가 GitHub 리포이므로 브라우저 UI 로 같은 파일을 직접 열 수 있다. 터미널 단축 수단의 가치보다 커맨드 수 감소 가치가 크다.
3. **`backfill-history`** — daily runner 가 매 실행마다 새 분만 RTDB 에 기록하므로 "최초 배포 / reset 복원" 상황에서 과거를 RTDB 로 일괄 미러하는 전용 수단. 그러나 실제 사용 사례를 점검한 결과 (1) `reset` 은 `history/` 를 통째로 삭제하므로 직후의 `backfill-history` 는 빈 결과, (2) "Git 은 살아있는데 RTDB 만 선택적으로 깨진 상황" 은 실제 발생 이력이 없다. 즉 커맨드로 상시 제공할 필요가 낮다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 / QBT 본체 수정 금지 / 계획서 작성 규칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 아키텍처 / CLI 계층 예외 / qbt 상수 재사용
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / 외부 네트워크 mock / 결정적 테스트
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `live.cli` argparse 에서 `init-data`, `history`, `backfill-history` subparser 3 개가 제거됨
- [x] `rebuild-data` 의 `ticker` 위치 인자가 `nargs="?"` 로 선언되고, 생략 시 `_collect_all_tickers()` 전체 재다운로드가 수행됨
- [x] `_cmd_init_data`, `_cmd_history`, `_cmd_backfill_history` 함수 및 관련 import (`HISTORY_SUMMARY_FILENAME`, `DEFAULT_HISTORY_TAIL_LINES`, `history.load_*_raw` 등) 가 `cli.py` 에서 제거되되, **다른 호출자가 남아있으면 해당 import 는 유지** (Grep 으로 재검증)
- [x] `rebuild-data` 티커 생략 시 전체 순회 동작을 검증하는 단위 테스트 1 건 이상 신규 추가
- [x] 제거된 3 커맨드를 커버하던 기존 테스트들이 삭제 또는 대체되어 `pytest` 가 통과함 (`skipped=0`)
- [x] `tests/live/test_workflows.py` 는 수정 불필요 (검증 대상이 `run-daily` / `notify-failure` 이므로) — 실제 수정 없음을 재확인
- [x] [README.md](../../README.md) 의 `python -m live init-data` / `python -m live history --tail 20` / (명시되어 있다면) `backfill-history` 예시가 제거되고, `rebuild-data` 사용법에 "티커 생략 시 전체" 주석이 반영됨
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 의 해당 커맨드 테스트 절차가 `rebuild-data` 전체 모드 / GitHub UI 조회로 대체됨 (또는 삭제됨)
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 의 `cli.py` 한줄 역할에서 "`backfill-history` 수동 명령" 문구가 제거됨
- [x] [src/live/cli.py](../../src/live/cli.py) 모듈 docstring 의 "명령어" 목록이 최신 8 커맨드로 갱신됨
- [x] `poetry run python validate_project.py` 통과 (passed=988, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase)
- [x] `README.md` **변경 있음** (커맨드 예시 3 건 제거 + 1 건 수정)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/cli.py](../../src/live/cli.py) — subparser 3 개 제거 / `p_rebuild` 확장 / `_cmd_*` 함수 3 개 제거 / `_cmd_rebuild_data` 분기 추가 / 모듈 docstring 갱신 / 미사용 import 정리.
- [tests/live/test_cli.py](../../tests/live/test_cli.py) 및 관련 테스트 파일 — `init-data` / `history` / `backfill-history` 를 대상으로 하던 테스트 케이스 삭제 또는 재구성, `rebuild-data` 전체 모드 케이스 신규 추가.
- [README.md](../../README.md) — live 섹션의 커맨드 예시 정리 (3 건 제거 + 1 건 수정).
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) — 30-31 라인 (`init-data`), 265 라인 (언급 있을 경우), 291-292 라인 (`backfill-history --dry-run` / `reset + backfill-history`), 66 / 436 라인 (`notify-failure` 는 유지이므로 건드리지 않음) 점검 후 갱신.
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 72 라인 전후 — 모듈별 역할 표에서 "`backfill-history` 수동 명령" 제거.
- `README.md`: **변경 있음** (live 커맨드 레퍼런스 3 개 제거 + 1 개 수정).

### 데이터/결과 영향

- **자동화 파이프라인 영향 없음**: [.github/workflows/daily_run.yml](../../.github/workflows/daily_run.yml) 은 `run-daily` / `notify-failure` 만 호출하므로 본 plan 변경과 무관하다.
- **RTDB / Git 정본 스키마 변경 없음**: 제거되는 3 커맨드는 기존 데이터를 **읽기만 하거나 미러만 하던** 수단이다. 파일 포맷, 경로, 키 스키마에는 영향이 없다.
- **기존 `qbt-live-state` 리포 상태 영향 없음**: 본 plan 실행 후에도 기존 커밋 이력 / 파일은 그대로 유지된다.
- **사용자 체감 변경**: 구 커맨드 입력 시 argparse 가 `unknown command` 로 실패. deprecated 별칭은 도입하지 않는다 (사용자 수 제한적, 문서 업데이트로 충분).

## 6) 단계별 계획(Phases)

> 본 plan 은 인바리언트 / 지표 / 에러 정책 변경이 없다 (기존 동작의 "표면 축소" 가 목적). Phase 0 없이 Phase 1 에서 테스트와 구현을 함께 진행한다.

---

### Phase 1 — CLI 표면 정리 + 테스트 재구성(그린 유지)

**작업 내용**:

- [x] [src/live/cli.py](../../src/live/cli.py) argparse 수정:
  - `p_init_data = sub.add_parser("init-data", ...)` 블록과 `p_init_data.set_defaults(func=_cmd_init_data)` 제거
  - `p_hist = sub.add_parser("history", ...)` 블록과 `p_hist.add_argument("--tail", ...)` / `set_defaults` 제거
  - `p_backfill_hist = sub.add_parser("backfill-history", ...)` 블록과 관련 `add_argument` / `set_defaults` 제거
  - `p_rebuild.add_argument("ticker")` 를 `p_rebuild.add_argument("ticker", nargs="?", default=None, help="선택. 티커 생략 시 전체 운영 티커 재다운로드")` 로 확장
- [x] `_cmd_init_data`, `_cmd_history`, `_cmd_backfill_history` 함수 본체 삭제 (관련 section 주석 포함).
- [x] `_cmd_rebuild_data` 수정: `ticker = args.ticker` → None 분기. `ticker is None` 이면 `_collect_all_tickers()` 를 순회하며 각 티커에 대해 `rebuild_full_csv(..., period="max")` 호출 (commit 은 컨텍스트 매니저가 일괄 처리). `ticker is not None` 경로는 기존 단일 티커 동작 유지.
- [x] 불필요해진 import 정리: `HISTORY_SUMMARY_FILENAME` / `DEFAULT_HISTORY_TAIL_LINES` 제거. 모듈 단위 import (`history`, `rtdb_gateway`) 는 다른 호출자가 있으므로 유지. `history.load_*_raw` / `rtdb_gateway.write_history_*_raw` 는 모듈 레벨 import 하에서 사용처 없음만 확인.
- [x] 모듈 docstring (cli.py 1-26 라인) 의 "명령어" 블록을 8 커맨드로 갱신.
- [x] 테스트 업데이트:
  - `tests/live/test_cli.py` 에서 `TestCmdBackfillHistory` / `TestHistoryCmd` 클래스 일괄 삭제.
  - `tests/live/test_alert_coverage.py` 에서 `test_init_data_failure_triggers_notify` / `test_history_failure_triggers_notify` 삭제, `test_rebuild_data_failure_triggers_notify` → 단일/전체 2 종으로 확장.
  - `tests/live/test_cli.py::TestCmdRebuildData` 클래스 신규 추가 (단일 티커 / 전체 순회 / 소문자 대문자 변환 3 건).

**Validation**:

- [x] 이 Phase 내에서 `poetry run pytest tests/live/test_cli.py tests/live/test_alert_coverage.py -q` 국소 실행으로 회귀 없음 확인 (전체 `validate_project.py` 는 마지막 Phase).

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [README.md](../../README.md) 의 live 섹션 갱신:
  - `poetry run python -m live init-data` 예시 제거
  - `poetry run python -m live history --tail 20` 예시 제거
  - `rebuild-data` 사용법에 "티커 생략 시 전체 재다운로드" 주석 / 예시 추가
  - 영구 이력 조회는 GitHub UI 사용 안내 추가
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 갱신:
  - `init-data` 단계를 `rebuild-data` (티커 생략) 로 대체
  - `backfill-history --dry-run` / `reset + backfill-history` 테스트 절차 블록 삭제
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 표의 `cli.py` 행에서 "`backfill-history` 수동 명령" → "`backfill-chart-archive` 수동 명령" 로 교체.
- [x] `poetry run black .` 실행 (자동 포맷 적용 — 146 files left unchanged).
- [x] `poetry run python validate_project.py` 실행 → Ruff / PyRight / Pytest 전부 통과.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=988, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / CLI 커맨드 통합 — init-data/history/backfill-history 제거 + rebuild-data 전체 모드 흡수
2. live / CLI 표면 11→8 축소 (중복/저사용 커맨드 3 종 제거)
3. live / rebuild-data 에 전체 다운로드 지원 + 불필요 커맨드 제거
4. live / init-data/history/backfill-history 제거 + 관련 문서 일괄 갱신
5. live / CLI 간소화 — argparse 정리 및 `rebuild-data` 확장

## 7) 리스크(Risks)

- **리스크 1**: 사용자의 근육 기억으로 `python -m live init-data` 등을 입력하면 argparse 가 `unknown command` 로 거부한다.
  - 완화: README / TEST_MANUAL 갱신으로 충분. deprecated 별칭은 도입하지 않음 (사용자 수 제한적).
- **리스크 2**: `_cmd_backfill_history` 만 사용하던 `history.load_*_raw` 등 하위 함수가 "죽은 코드" 가 될 수 있다.
  - 완화: 본 plan 에서는 함수 자체 삭제는 보류 (Non-Goal). 향후 dead-code 점검에서 함께 정리.
- **리스크 3**: `rebuild-data` 티커 생략 모드 실행 시 연속으로 yfinance 호출이 발생하여 rate-limit 가능성.
  - 완화: 기존 `init-data` 가 이미 동일 동작을 해왔고 실제 운영에서 문제없음이 확인됨 (동등 치환).
- **리스크 4**: `tests/live/test_workflows.py` 의 workflow 파일 문자열 검증이 `init-data` / `history` 같은 문자열을 포함하지 않는지 재확인 필요.
  - 완화: Grep 으로 사전 재확인 (현재 `run-daily` / `notify-failure` 만 검증 중임).

## 8) 메모(Notes)

- 본 plan 실행 후에도 `qbt-live-state` 리포의 `history/*.jsonl` 파일은 `run-daily` 가 계속 append 한다. GitHub UI 조회는 이 파일들을 대상으로 한다.
- `backfill-chart-archive` 는 유지. 스플릿 대응 절차 ([docs/DESIGN_QBT_LIVE_FINAL.md §9.1](../DESIGN_QBT_LIVE_FINAL.md) 에 기재) 의 핵심 단계이며, Plan 2 (reset 재설계) 와도 공존.
- Plan 2 / Plan 3 과 독립. 파일 충돌 최소 (cli.py 수정 범위가 겹치므로 병합 시 순서상 Plan 1 → Plan 2 → Plan 3 권장).

### 진행 로그 (KST)

- 2026-04-17 13:53: plan 초안 작성.
- 2026-04-17 14:00: Phase 1 착수 — cli.py argparse / `_cmd_*` 함수 3 종 제거 / `_cmd_rebuild_data` 확장 / 모듈 docstring 갱신.
- 2026-04-17 14:05: 테스트 재구성 — `TestCmdBackfillHistory` / `TestHistoryCmd` 삭제, `test_init_data_failure_triggers_notify` / `test_history_failure_triggers_notify` 삭제, `TestCmdRebuildData` 3 건 신규 추가, `test_rebuild_data_failure_triggers_notify` 를 단일/전체 2 종으로 확장.
- 2026-04-17 14:10: 문서 갱신 — README / TEST_MANUAL / src/live/CLAUDE.md.
- 2026-04-17 14:15: `black` + `validate_project.py` 통과 (passed=988, failed=0, skipped=0). 상태 → ✅ Done.

---
