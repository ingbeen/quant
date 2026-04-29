# Implementation Plan: live `init` 명령 제거

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-29 23:30
**마지막 업데이트**: 2026-04-29 23:30
**관련 범위**: live (cli, tests)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/COMMANDS.md](../COMMANDS.md)

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

- [x] 목표 1: `live` CLI 의 `init` 서브커맨드와 `_cmd_init` 함수를 제거한다.
- [x] 목표 2: `init` 의 동작은 `reset` 의 부분집합이므로 운영 시나리오는 `reset` 으로 일원화된다.
- [x] 목표 3: 테스트 fixture 가 `main(["init", ...])` 에 의존하던 부분을 직접 `live_state.json` 을 생성하는 경량 헬퍼로 교체하여 회귀 없이 그린 유지.
- [x] 목표 4: 문서 (`docs/COMMANDS.md`, `src/live/CLAUDE.md`, `cli.py` 모듈 docstring, allow-list 정책 docstring) 에서 `init` 언급을 제거한다.

## 2) 비목표(Non-Goals)

- `reset` 의 동작 변경은 비목표 (기존 9 단계 그대로 유지).
- `rebuild-data` / `drift` / `fetch-fills` / `backfill-chart-years` 등 다른 사용자 직접 실행 커맨드의 변경은 비목표.
- `docs/DESIGN_QBT_LIVE_FINAL.md` 갱신은 비목표 — DESIGN 문서에 `init` 언급이 없음을 grep 으로 확인.
- 운영 환경의 RTDB / state repo 데이터 정리는 비목표 — 본 작업은 코드 / 테스트 / 문서 변경만 다룸.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `init` 은 "최초 1회 state repo 셋업" 시나리오에서만 의미가 있는 명령. 운영 중에는 `reset` 이 동일 동작 (live_state.json 새로 만들기) 을 포함하면서 RTDB / history / CSV 까지 함께 처리하므로 `init` 사용 빈도는 사실상 0.
- 사용자(단일 운영자) 가 직전 archive→years 마이그레이션 작업 중 `init` 과 `reset` 을 혼동하여 RTDB 가 정리되지 않는 사고를 겪음. 명령어 표면이 두 개라 운영 혼란이 발생.
- `init` 만의 차별점은 "Firebase 의존성 없이 동작" 이지만, 본 프로젝트의 ephemeral state repo 패턴 + Firebase 가 항상 셋업되어 있는 운영 모델에서는 의미가 없음.
- 사용자 합의로 제거 결정.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md): 코딩 표준 / 로깅 정책
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md): live 도메인 핵심 원칙 (allow-list 정책 포함)
- [tests/CLAUDE.md](../../tests/CLAUDE.md): 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

- [x] `live` CLI 에 `init` 서브커맨드가 더 이상 등록되지 않음 (`python -m live --help` 출력에서 미노출)
- [x] `_cmd_init` 함수가 `src/live/cli.py` 에서 제거됨
- [x] `cli.py` 모듈 docstring 의 명령어 목록에서 `init` 라인 제거됨
- [x] `cli.py` 의 allow-list 정책 docstring (`_NOTIFY_FAILURE_COMMANDS` 주변, `main()` docstring) 에서 `init` 언급 제거됨
- [x] `tests/live/test_cli.py` 의 `TestCmdInit` 클래스 제거됨
- [x] `tests/live/test_cli.py` 의 다른 테스트들이 사용하던 `main(["init", "--capital", ...])` 호출이 직접 `live_state.json` 을 생성하는 헬퍼로 교체됨 (회귀 없음)
- [x] `tests/live/test_alert_coverage.py` 의 allow-list 검증 파라미터에서 `init` 제거, `_cmd_init` 모킹 제거, init 사용처가 다른 fixture 헬퍼로 교체됨
- [x] `docs/COMMANDS.md` 의 `init --capital` 라인 제거됨
- [x] `src/live/CLAUDE.md` 핵심 원칙 §1 의 "사용자 직접 실행 커맨드" 목록에서 `init` 제거됨
- [x] 회귀/신규 테스트 갱신
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트
  - [x] `README.md`: 변경 없음 (init 언급 없음)
  - [x] `docs/COMMANDS.md`: 변경 있음
  - [x] `src/live/CLAUDE.md`: 변경 있음
  - [x] `docs/DESIGN_QBT_LIVE_FINAL.md`: 변경 없음 (grep 결과 init 언급 없음)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**구현 코드**:

- `src/live/cli.py`
  - 모듈 docstring (line 1-23 부근) 의 명령어 목록에서 `init` 라인 제거
  - `_cmd_init` 함수 (line 378-385) 제거
  - argparse subcommand `init` 등록 (line 1115-1117) 제거
  - `_NOTIFY_FAILURE_COMMANDS` 주변 docstring 의 `init` 언급 제거
  - `main()` docstring 의 사용자 직접 실행 커맨드 목록에서 `init` 제거

**테스트 코드**:

- `tests/live/test_cli.py`
  - `TestCmdInit` 클래스 (line 112-132) 제거
  - 공통 헬퍼 섹션에 `_create_state_file(state_dir, capital)` 함수 추가 — `live_state.json` 을 직접 생성
  - 다른 테스트의 `main(["init", "--capital", "100000000"])` 호출 (약 14곳) 을 `_create_state_file(state_dir)` 로 교체
  - `test_main_accepts_argv_list` (line ~1049) 는 init 대신 다른 가벼운 명령(`rebuild-data SPY` mock 사용)으로 교체
  - `commit_subcommand="init"` 가 들어있는 테스트 (line ~1218) 는 다른 임의 문자열로 교체 (해당 테스트의 본질은 commit_subcommand 인자 처리이므로 값 자체는 무관)
- `tests/live/test_alert_coverage.py`
  - allow-list 검증 파라미터 리스트에서 `["init", "--capital", "100000000"]` 항목 제거 (line 101)
  - `_cmd_init` 모킹 항목 제거 (line 126)
  - line 245, 277 의 init 호출처는 `_create_state_file` 류 헬퍼로 교체 또는 다른 실패 시나리오 명령으로 변경

**문서**:

- `docs/COMMANDS.md`
  - line 146 의 `poetry run python -m live init --capital 1000000` 라인 제거
- `src/live/CLAUDE.md`
  - line 85 부근의 사용자 직접 실행 커맨드 목록에서 `init` 제거
- `README.md`: 변경 없음 (grep 결과 init 언급 없음)
- `docs/DESIGN_QBT_LIVE_FINAL.md`: 변경 없음 (grep 결과 init 언급 없음)

### 데이터/결과 영향

- 운영 영향: **없음** — `init` 은 사용자(단일 운영자)가 사용하지 않던 명령. 제거 후에도 운영 흐름 변화 없음.
- 향후 최초 배포 시나리오: `init` 대신 `reset --capital N` 1회 실행으로 동일 효과 + 추가 정리 (RTDB / history / CSV) 까지 한 번에 처리.

## 6) 단계별 계획(Phases)

### Phase 1 — `cli.py` 에서 `init` 제거

**작업 내용**:

- [x] `src/live/cli.py` 모듈 docstring 의 명령어 목록에서 `init` 라인 제거
- [x] `_cmd_init` 함수 제거
- [x] argparse subcommand `init` 등록 제거
- [x] `_NOTIFY_FAILURE_COMMANDS` 주변 / `main()` docstring 의 `init` 언급 제거
- [x] `python -m live --help` 로 init 미노출 확인

**Validation**:

- [x] `poetry run python -m live --help` 출력에서 `init` 미등록 확인

---

### Phase 2 — 테스트 갱신

**작업 내용**:

- [x] `tests/live/test_cli.py` 공통 헬퍼 섹션에 `_create_state_file(state_dir, capital)` 추가 (`create_initial_state` + `save_state` 호출)
- [x] `TestCmdInit` 클래스 제거
- [x] `main(["init", "--capital", "100000000"])` 호출 14곳을 `_create_state_file(state_dir)` 로 교체
- [x] `test_main_accepts_argv_list` 가 사용하던 init 호출을 가벼운 대체로 교체 (rebuild-data SPY + rebuild_full_csv mock)
- [x] `commit_subcommand="init"` 가 있는 테스트는 다른 임의 문자열 (예: "test-commit") 로 교체
- [x] `tests/live/test_alert_coverage.py` 의 allow-list 검증 파라미터에서 `init` 제거, `_cmd_init` 모킹 제거, init 호출처를 헬퍼로 교체

**Validation**:

- [x] `poetry run pytest tests/live/ -x` 통과

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `docs/COMMANDS.md` 의 init 라인 제거
- [x] `src/live/CLAUDE.md` 의 init 언급 제거
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 / Phase 체크박스 최종 갱신

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1007, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / init 명령 제거 — reset 으로 일원화
2. live / 사용 빈도 0 인 init 서브커맨드 제거 + 테스트 fixture 정리
3. live / CLI 표면 정리 — init 제거 (reset 의 부분집합)
4. live / init 명령 폐기 + 테스트 헬퍼로 fixture 단순화
5. live / 운영 혼란 방지를 위해 init 명령 제거

## 7) 리스크(Risks)

- **리스크 1**: 테스트의 `main(["init", ...])` 호출을 `_create_state_file` 로 교체하는 과정에서 ephemeral_state_repo 컨텍스트가 yield 하는 `tmp_path` 의 결과와 동일한 동작을 보장해야 함 — `state_dir` fixture 가 이미 `tmp_path` 를 yield 하므로 단순히 그 안에 `live_state.json` 만 만들면 동등.
- **리스크 2**: `_cmd_init` 가 `ephemeral_state_repo(push_on_success=True)` 를 호출하므로 이를 통한 git push 동작 검증이 사라짐. 다만 동일 push 흐름은 `_cmd_reset`, `_cmd_run_daily`, `_cmd_rebuild_data` 등 다른 명령에서 동일하게 검증되므로 커버리지 손실은 무시할 수준.
- **리스크 3**: 향후 "최초 배포" 시나리오 발생 시 사용자가 혼란 — `reset` 으로 대체 가능함을 `docs/COMMANDS.md` 에 명시하지 않으면 사용자가 갈피를 못 잡을 수 있음. 다만 단일 운영자 환경이라 본인이 인지하면 충분.

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-29 23:30: plan 초안 작성, Auto mode 로 즉시 진행
- 2026-04-29 23:35: Phase 1 (cli.py 에서 init 제거) 완료, `python -m live --help` 에서 init 미노출 확인
- 2026-04-29 23:40: Phase 2 (테스트 갱신 — `_create_state_file` 헬퍼 추가, 14곳 호출처 교체, allow-list 정합화) 완료, pytest tests/live/ 488 passed
- 2026-04-29 23:45: 마지막 Phase (docs/COMMANDS.md / src/live/CLAUDE.md 갱신, black, validate_project.py) 완료, 1007 passed / 0 failed / 0 skipped
- 2026-04-29 23:55: 추가 정합화 — `src/live/cli.py:373` 의 `# init` 섹션 헤더 주석을 `# reset` 으로 갱신, `tests/live/test_cli.py` 두 클래스의 `_init_state` 메서드명을 `_setup_state` 로 통일 (호출처 6곳 일괄 교체). pytest tests/live/ 488 passed

---
