# Implementation Plan: live `reset` 재설계 — 순서 재배치 + 멱등성 + RTDB 주가 차트 자동 재생성

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
**마지막 업데이트**: 2026-04-17 14:30
**관련 범위**: live (CLI — `reset` 로직)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [src/live/cli.py](../../src/live/cli.py), [src/live/chart_data.py](../../src/live/chart_data.py), [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py), [README.md](../../README.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

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

- [x] `reset` 실행 순서를 "사전 검증 → Git 원자적 commit → RTDB 삭제 → RTDB 주가 차트 재생성" 9 단계로 재배치하여, 중간 실패 시에도 **앱이 보는 RTDB 상태가 장기간 불일치로 방치되지 않도록** 한다.
- [x] `reset` 에 RTDB `/charts/prices/*/meta|recent|archive` 자동 재생성 로직을 포함시켜, **reset 직후 별도 수동 후속 명령 없이 앱의 주가 차트가 정상 표출**되도록 한다 (체결 / 시그널 마커는 빈 dict, equity 차트와 `/history/*` 는 "시간 해결 영역" 으로 명시적으로 비움).
- [x] 어느 단계에서 실패해도 `reset` 을 **재실행하여 멱등적으로 복구** 가능한 구조를 보장한다.
- [x] Firebase 초기화 실패 시 **Git / RTDB 를 전혀 건드리지 않고 즉시 중단** 하는 사전 검증 단계를 추가한다.

## 2) 비목표(Non-Goals)

- **CLI 표면 변경 금지**: `init-data` / `history` / `backfill-history` 제거 및 `rebuild-data` 확장은 별도 [Plan 1](PLAN_LIVE_CLI_COMMAND_CONSOLIDATION.md) 에서 다룬다. 본 plan 은 `reset` 로직만 건드린다.
- **알림 정책 변경 금지**: `main()` 공통 예외 훅 allow-list 전환은 별도 [Plan 3](PLAN_LIVE_FAILURE_NOTIFY_ALLOWLIST.md) 에서 다룬다. 본 plan 실행 시점에는 기존 deny-list 정책을 전제로 테스트를 구성한다.
- **`backfill-chart-archive` 제거 금지**: 스플릿 대응 전용으로 유지 (rebuild-data 후 특정 티커 차트만 재생성하는 유일한 수단).
- **equity 차트 / `/history/*` 자동 복원 금지**: equity 빌더 (`build_equity_*`) 는 `history/summary.jsonl` 에 의존하는데 reset 이 `history/` 를 통째로 삭제하므로 시점 상 불가. 매일 `run-daily` 로 점진 누적되는 설계를 유지한다.
- **`/latest`, `/charts/*/recent` 의 체결/시그널 마커 재계산 금지**: reset 직후 Git 정본에 user_trades / signal_history 가 없으므로 빈 리스트로 기록. 기존 빌더 API (`build_chart_recent(user_trades=[], signal_history=[])`) 를 그대로 사용한다.
- **QBT 본체 수정 금지**.
- **`init` 커맨드 동작 변경 금지**: 파괴적 명령과 분리된 "처음 시작" 의미를 보존.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `_cmd_reset` ([src/live/cli.py:395-445](../../src/live/cli.py#L395-L445)) 순서:

```
1. RTDB 전체 삭제 (device_tokens 제외)                 ← 가장 먼저 파괴
2. ephemeral_state_repo clone
3. live_state.json 초기화
4. applied_*_ids.json 삭제
5. history/ 삭제
6. CSV 전체 재다운로드
7. (컨텍스트 종료) Git commit + push
```

이 순서의 문제:

1. **불일치 창이 길다**: RTDB 가 먼저 비워진 상태에서 2~7 중 어느 하나라도 실패하면 "RTDB 는 비어있고 Git 은 이전 상태" 라는 불일치가 재실행 전까지 지속된다. 앱 사용자가 긴 시간 텅 빈 화면을 본다.
2. **앱 정상 구동까지 수동 후속 명령 필요**: reset 성공 후에도 주가 차트 archive 가 비어 있어 운영자가 `backfill-chart-archive` 를 추가 실행해야 앱의 과거 주가 차트가 표출된다.
3. **사전 검증 부재**: Firebase 자격증명 / URL 문제를 1 단계 시작 후에야 발견. 이미 파괴 작업 시도가 시작된 뒤의 실패라 잔여물 위험이 있다.

### 해결 방향

- **사전 검증 분리** (1 단계): `_require_rtdb_app()` 으로 Firebase 연결 가능성을 먼저 확인. 실패하면 Git / RTDB 변경 없이 즉시 중단.
- **Git 을 원자적 단위로** (2~7 단계): ephemeral_state_repo 의 commit + push 까지 끝낸 뒤에 RTDB 를 건드린다. Git push 는 성공 / 실패 2 값이라 "부분 성공" 이 없다.
- **RTDB 를 마지막에** (8~9 단계): 삭제 + 주가 차트 재생성을 같은 flow 에 포함. 실패 시 재실행으로 멱등 복구.

### chart_data 빌더 제약 확인

[src/live/chart_data.py:440-496](../../src/live/chart_data.py#L440-L496) 검토 결과:

- `build_chart_meta` / `build_chart_recent` / `build_chart_archive_year` → CSV (`{state_dir}/data/stock/*.csv`) 의존. **reset 직후 가능** (6 단계에서 CSV 재다운로드 완료 후).
- `build_equity_meta` / `build_equity_recent` / `build_equity_archive_year` → `history/summary.jsonl` 의존. **reset 직후 불가** (5 단계에서 history/ 삭제).

따라서 reset 후속에는 **주가 차트만** 생성한다. equity 는 `run-daily` 가 매일 누적.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 / 장애 시 자동 복구 금지 / 내부 불변조건 처리
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 아키텍처 / 장애 원칙 1 / ephemeral state repo
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / 외부 네트워크 mock / 결정적 테스트
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `_cmd_reset` 가 신규 9 단계 순서대로 동작하도록 재구현됨 (사전 검증 → Git clone → 파일 작업 → RTDB 삭제 → RTDB 주가 차트 재생성 → Git commit+push)
- [x] Firebase 초기화 실패 시 Git shallow clone / RTDB 쓰기가 전혀 발생하지 않음을 검증하는 단위 테스트 1 건 추가 (`test_reset_aborts_on_firebase_init_failure`)
- [x] Git push 후 RTDB 단계에서 실패했을 때 **reset 재실행으로 멱등 복구** 가 가능함을 검증하는 테스트 추가 (`test_reset_is_idempotent_when_rtdb_write_fails_midway`)
- [x] reset 성공 시 RTDB `/charts/prices/*/meta` / `/charts/prices/*/recent` / `/charts/prices/*/archive/{연도}` 에 쓰기 호출이 발생함을 검증하는 통합 테스트 1 건 추가 (`test_reset_writes_price_charts_and_skips_equity_history`)
- [x] reset 성공 시 `/charts/equity/*` / `/history/*` 는 쓰기 호출이 발생하지 않음 (비워둔 채 유지) 을 검증하는 테스트 1 건 추가 (위 테스트에 동시 assert)
- [x] 기존 `_cmd_reset` 단위 테스트가 신규 순서에 맞게 업데이트되어 `pytest` 그린 (기존 별도 단위 테스트는 없었고 `TestCmdReset` 5 건 신규 추가)
- [x] [README.md](../../README.md) 의 `reset` 설명에 "주가 차트 자동 복원 포함 / equity 는 `run-daily` 로 누적" 문구 반영
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) reset 수동 테스트 절차 (§15) 에 "앱에서 주가 차트 정상 표출 확인 / equity 는 텅 빈 상태 확인" 체크 항목 추가
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) reset 관련 설명 갱신 (§8.2.11 보존 정책 / §8.3 `/history/*` 정본 관계 / §9.1 backfill 섹션 3 곳)
- [x] `poetry run python validate_project.py` 통과 (passed=993, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase)
- [x] `README.md` **변경 있음** (reset 동작 설명)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/cli.py](../../src/live/cli.py) `_cmd_reset` — 전면 재구성. 기존 `with ephemeral_state_repo(push_on_success=True, ...)` 블록 내부 순서 조정 + 블록 종료 후 RTDB 단계 분리.
  - 구체 호출: `_require_rtdb_app()` 를 맨 앞으로 이동 → ephemeral clone → file ops (기존 2-1 ~ 2-4) → 컨텍스트 종료 시 push → 이후 `rtdb_gateway.delete_all_except_device_tokens(rtdb_app)` → `build_chart_meta` + `build_chart_recent` + 연도별 `build_chart_archive_year` + 대응 `rtdb_gateway.write_chart_*` 호출.
  - 컨텍스트 종료 시점에 이미 state_dir tempdir 이 제거되므로, 차트 재생성에 필요한 `state_dir` 참조는 **컨텍스트 내부에서 먼저 주가 차트 payload 를 모두 메모리에 build 해둔 뒤 컨텍스트 종료 후 write** 하거나, 또는 **컨텍스트 블록 안에서 모든 RTDB 쓰기까지 완료** 하는 것이 안전하다. 구현 시 판단하되 후자를 우선 검토 (더 단순, 실행 시간 조금 길어짐은 허용).
- [tests/live/test_cli.py](../../tests/live/test_cli.py) (또는 분리된 reset 테스트 파일) — 기존 reset 관련 테스트 업데이트 + 신규 시나리오 추가.
- [README.md](../../README.md) — reset 설명 갱신 (주가 차트 자동 복원 포함).
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) — reset 수동 테스트 체크 항목 확장.
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — reset 관련 섹션 확인 후 갱신 필요 시 반영 (현재 설계서가 reset 세부 순서를 기재하지 않는다면 수정 불필요).
- `README.md`: **변경 있음** (reset 동작 설명).

### 데이터/결과 영향

- **자동화 파이프라인 영향 없음**: `reset` 은 수동 실행 전용이며 `.github/workflows/daily_run.yml` 의 `run-daily` / `notify-failure` 와 무관.
- **RTDB 영향**: `reset` 실행 시 `/charts/prices/*/` 에 주가 차트 meta + recent + 연도별 archive 가 자동으로 채워진다. 기존에는 reset 후 수동 `backfill-chart-archive` 가 필요했다.
- **Git 정본 영향 없음**: reset 의 Git 작업 단계는 기존과 동일한 결과 (빈 history, 초기 state, 재다운로드된 CSV) 를 produce. 순서만 바뀐다.
- **실행 시간**: 연도 수 × 자산 수 만큼의 RTDB 쓰기가 추가되어 reset 전체 소요 시간이 증가한다 (단일 실행 수십 초 ~ 1 분대 예상). reset 은 드문 명령이라 허용.

## 6) 단계별 계획(Phases)

> reset 은 운영 파괴 명령이며 실패 시 앱 상태 불일치 위험이 있으므로, **정책 (단계 순서 / 사전 검증 / 멱등성)** 을 먼저 테스트로 고정한 뒤 구현한다 → Phase 0 레드.

---

### Phase 0 — 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] 신규 테스트 케이스 추가:
  - `test_reset_aborts_on_firebase_init_failure` — `_require_rtdb_app` 을 raise 하도록 monkeypatch 했을 때, `git_state.git_clone_shallow` / `rtdb_gateway.delete_all_except_device_tokens` / `rtdb_gateway.write_chart_*` 중 어떤 것도 호출되지 않음을 assert.
  - `test_reset_calls_git_push_before_rtdb_delete` — 호출 순서 검증 (CSV 재다운로드 = Git 파일 작업이 `delete_all_except_device_tokens` 보다 먼저).
  - `test_reset_writes_price_charts_and_skips_equity_history` — 성공 경로에서 `write_chart_meta` / `write_chart_recent` / `write_chart_archive_year` 는 호출되지만 `write_equity_*` / `write_history_*` 는 호출되지 않음.
  - `test_reset_price_chart_markers_are_empty` — `build_chart_archive_year` / `build_chart_recent` 호출 시 `user_trades={}`, `signal_history={}` 전달됨 (dict 타입).
  - `test_reset_is_idempotent_when_rtdb_write_fails_midway` — RTDB archive 쓰기 실패 후 reset 재실행 시 정상 성공 경로와 동일 결과 도달.
- [x] 모든 외부 I/O 는 기존 conftest / `_install_reset_spies` 헬퍼로 격리 (Firebase / yfinance / git subprocess 차단).
- [x] 이 Phase 종료 시점에 신규 테스트는 구현 전 기준 레드 (Phase 1 구현 후 그린 전환).

---

### Phase 1 — `_cmd_reset` 재구현(그린 유지)

**작업 내용**:

- [x] `_cmd_reset` 함수 본체 재작성. 실제 구현 순서:
  1. `rtdb_app = _require_rtdb_app()` — Firebase 초기화 시도 (실패 시 RuntimeError 전파).
  2. `with ephemeral_state_repo(push_on_success=True, commit_subcommand="reset") as state_dir:` 진입.
  3. `save_state(create_initial_state(capital), ...)`.
  4. `applied_*_ids.json` 3 개 삭제.
  5. `history/` 디렉토리 삭제.
  6. `_collect_all_tickers()` 순회하여 `rebuild_full_csv(period="max")`.
  7. `rtdb_gateway.delete_all_except_device_tokens(rtdb_app)`.
  8. 주가 차트 재생성: `build_chart_meta` + `write_chart_meta` / `build_chart_recent(user_trades={}, signal_history={})` + `write_chart_recent` / 각 archive_year 에 대해 `build_chart_archive_year` + `write_chart_archive_year`.
  9. 컨텍스트 종료 시 자동 Git commit+push (ephemeral 컨텍스트 매니저 동작).
  - 채택: **RTDB 삭제 + 차트 write 를 컨텍스트 내부 마지막 단계로** 두어 Git push 가 가장 마지막이 되게 함. 실패 시 Git 미반영 → 재실행 시 Git 재-initialize 흐름 재개로 멱등 복구.
- [x] 레드 상태였던 Phase 0 테스트 5 건이 모두 그린으로 전환됨 (`poetry run pytest tests/live/test_cli.py::TestCmdReset -q` 5 passed).
- [x] 기존 `test_cli_reset` 류 테스트는 없었으므로 갱신 대상 없음.

**Validation**:

- [x] `poetry run pytest tests/live/test_cli.py::TestCmdReset -q` 5 passed. 전체 `validate_project.py` 는 마지막 Phase.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [README.md](../../README.md) `reset` 예시 설명 수정: "실행 종료 시 RTDB 주가 차트 archive 까지 자동 재생성 / equity / 체결 이력은 비워지며 매일 run-daily 로 누적" 주석 추가.
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 에 §15 "reset 실행 시 주가 차트 자동 복원 확인 (위험 — 테스트 환경 한정)" 신규 섹션 추가. 4 자산 라인 표시 / equity 텅 빔 / 체결 이력 텅 빔 / RTDB 경로 검증 체크 항목 포함.
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §8.2.11 보존 정책 / §8.3 `/history/*` 정본 관계 / §9.1 backfill 섹션 3 곳의 `backfill-history` 언급을 제거하고 "reset 이 Git 정본 history/ 와 RTDB 를 동시 초기화, 이후 run-daily 로 누적" 취지로 재작성.
- [x] `poetry run black .` 실행 (1 file reformatted, 145 unchanged — 테스트 파일 자동 정리).
- [x] `poetry run python validate_project.py` 실행 → Ruff / PyRight / Pytest 전부 통과.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=993, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / reset 재설계 — Git 우선 + RTDB 마지막 + 주가 차트 자동 복원 + 멱등성
2. live / reset 순서 안전화 (사전검증→Git→RTDB) + 주가 archive 자동 생성
3. live / reset 이 앱 주가 차트까지 자동 복원하도록 확장 + 순서 재배치
4. live / reset 9 단계 재구성 (Firebase 선검증, RTDB 마지막, 멱등 재시도)
5. live / reset 안정화 — 중간 실패 시 재실행 복구 + 주가 차트 자동 생성

## 7) 리스크(Risks)

- **리스크 1**: 주가 차트 생성 단계에서 실패 시 "RTDB 는 부분 상태 + Git 은 이전 상태" 조합이 일시적으로 발생할 수 있다.
  - 완화: reset 재실행 시 `build_chart_*` 가 최신 CSV 로 덮어쓰기 하므로 멱등 복구 가능. Phase 0 의 `test_reset_is_idempotent_on_rtdb_failure` 로 보장.
- **리스크 2**: `build_chart_archive_year` 가 CSV 의 연도별 슬라이스를 만들 때 `archive_years` 목록이 길면 RTDB 쓰기 횟수 × 자산 수가 커진다.
  - 완화: reset 은 드문 명령. 실행 시간 증가는 허용 범위. 모니터링은 DEBUG 로그로 충분.
- **리스크 3**: `build_chart_recent(user_trades=[], signal_history=[])` 호출 시 빌더 내부에서 빈 리스트를 허용하는지 계약 확인 필요.
  - 완화: Phase 0 테스트에서 실제 호출 payload 를 assert 하여 빌더 동작 확인.
- **리스크 4**: 기존 `_cmd_reset` 테스트 중 "RTDB 먼저 삭제됨" 을 검증하던 케이스가 새 순서와 상충.
  - 완화: Phase 0 에서 새 정책 테스트를 먼저 도입하고, 기존 테스트는 Phase 1 구현 시 신규 순서에 맞게 갱신.
- **리스크 5**: `ephemeral_state_repo` 는 컨텍스트 종료 시 Git push 를 수행하는데, 컨텍스트 내부에서 RTDB 쓰기가 실패하면 push 가 아직 일어나기 전 예외가 전파되어 Git push 가 건너뛰어지는지 (= Git 변경이 실제로 반영되지 않고 tempdir 만 삭제되는지) 확인 필요.
  - 완화: [src/live/cli.py:196-206](../../src/live/cli.py#L196-L206) 의 `ephemeral_state_repo` 구조 상 예외 전파 시 `push_on_success` 블록이 건너뛰어지는 것이 이미 설계되어 있다. 구현 시 이 동작 재확인.

## 8) 메모(Notes)

- Plan 1 (CLI 단순화) 가 먼저 적용된 후 본 plan 을 적용하는 것을 권장하지만, 파일 충돌 범위가 `_cmd_reset` 함수로 국지적이므로 반대 순서로 진행해도 병합 비용 낮음.
- 컨텍스트 내부 마지막 단계로 RTDB 작업을 수행하는 채택안은 "Git push 가 가장 마지막" 이라는 관점에서 사용자 요청 ("RTDB 를 마지막에") 과 어긋나 보일 수 있다. 그러나 **앱이 보는 파괴적 작업의 마지막 단계** 관점에서는 RTDB 쓰기가 실제 "마지막 가시적 변경" 이며, Git push 실패 시엔 Git 이 이전 상태로 남는 것이 안전성에 기여한다 (다음 reset 재실행 시 Git 재-initialize 로 복구 가능). 구현 시 이 해석을 테스트로 고정.
- `_safe_notify_failure` 는 현재 deny-list 로 reset 실패 시에도 알림 발송된다. 본 plan 적용 시점엔 Plan 3 미적용 전제이므로 테스트 모킹 시 `_safe_notify_failure` 호출도 함께 차단한다 (Plan 3 적용 후 알림 skip 되지만 테스트 격리 상 영향 없음).

### 진행 로그 (KST)

- 2026-04-17 13:53: plan 초안 작성.
- 2026-04-17 14:20: Phase 0 — `TestCmdReset` 5 건 + `_install_reset_spies` 헬퍼 신규 추가 (레드 허용).
- 2026-04-17 14:22: Phase 1 — `_cmd_reset` 9 단계 재구현 (Firebase 사전 검증 → Git → RTDB 삭제 → 주가 차트 재생성 → Git push). 5 테스트 그린.
- 2026-04-17 14:28: 문서 갱신 — README / TEST_MANUAL §15 / DESIGN §8.2.11·§8.3·§9.1.
- 2026-04-17 14:30: PyRight 타입 불일치 (`list[Any]` vs `dict[str, list[UserTrade]] | None`) 수정 — 빈 리스트 `[]` → 빈 dict `{}` 로 교체.
- 2026-04-17 14:32: `black` + `validate_project.py` 통과 (passed=993, failed=0, skipped=0). 상태 → ✅ Done.

---
