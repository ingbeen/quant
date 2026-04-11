# Implementation Plan: live CLI ephemeral state repo (로컬 파일 0개)

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

**작성일**: 2026-04-11 16:00
**마지막 업데이트**: 2026-04-11 16:00
**관련 범위**: live (CLI + 워크플로우 + 테스트 + 문서)
**관련 문서**: [live/CLAUDE.md](../../live/CLAUDE.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

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

- [x] 로컬 CLI 실행이 프로젝트 폴더에 **파일을 전혀 남기지 않도록** 한다.
- [x] 로컬 실행과 GitHub Actions 실행이 **같은 코드 경로**를 타게 한다.
- [x] CLI 에서 **거의 바뀌지 않는 플래그들을 제거**하여 명령을 단순화한다.
- [x] GitHub Actions 워크플로우를 **간결화**한다.

## 2) 비목표(Non-Goals)

- 옵션 B (`~/.cache/` 캐시 모드) 는 이번 plan 범위가 아니다. 사용자 선택은 A안 (매번 새 tempdir).
- Firebase / 텔레그램 알림 구조 변경 없음. 알림은 기존 경로 유지.
- QBT 본체 (`src/qbt/`) 수정 없음.
- 새 CLI 명령 추가 없음 (`init`, `run-daily` 등 기존 명령들의 동작만 내부 변경).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 CLI 는 `--state-dir` (기본값 `qbt-live-state`) 을 통해 **로컬 영속 디렉토리**에 state / history / CSV 를 쓴다.
- 로컬 실행 결과는 사용자가 수동으로 `push-state` 를 호출해야 원격 리포에 반영된다.
- GitHub Actions 는 별도 `actions/checkout@v4` 단계로 state 리포를 runner workspace 에 체크아웃하고, 워크플로우 shell step 에서 commit/push 를 수행한다.
- 결과적으로 **로컬과 Actions 의 실행 경로가 다르다** — 사용자가 신뢰할 수 있는 단일 진실의 원천이 없다.
- 사용자의 요구는 두 가지: "로컬에 파일이 남지 않아야 한다" + "로컬과 Actions 결과가 동일해야 한다".
- 해결책: CLI 내부에서 **매 실행마다 tempdir 에 shallow clone → 작업 → commit/push → cleanup** 흐름을 구현. 로컬과 Actions 가 같은 CLI 코드 경로를 탄다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md) — 타입 힌트, Path 사용, 한글 메시지, 로깅 정책, 내부 불변조건 처리
- [live/CLAUDE.md](../../live/CLAUDE.md) — live 도메인 원칙, 장애 시 자동 복구 금지, 백테스트 절대 규칙 보존
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, mock 기반, 외부 네트워크 호출 금지
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — 부록 A CLI 명세, 10장 git 흐름

## 4) 완료 조건(Definition of Done)

- [x] `git_state.py` 에 `git_clone_shallow()` + `embed_pat_in_url()` 추가
- [x] `cli.py` 에 `ephemeral_state_repo()` 컨텍스트 매니저 추가
- [x] CLI 명령들이 ephemeral 모드로 동작하도록 리팩토링
- [x] 플래그 제거: `--state-dir`, `--period`, `--no-rtdb`, `--no-notify`
- [x] 플래그 유지: `--capital`, `--trade-date`, `--tail`, `--message`
- [x] 명령 제거: `fetch-state`, `push-state`
- [x] `.github/workflows/daily_run.yml` 간결화
- [x] `live/tests/test_cli.py` 리팩토링 — `state_dir` fixture 추가, `TestFetchState`/`TestPushState` 삭제
- [x] `live/tests/test_workflows.py` 갱신 — 새 구조 assertion 추가
- [x] `live/tests/test_git_state.py` 에 `git_clone_shallow` + `embed_pat_in_url` 테스트 추가
- [x] `test_cli.py::TestEphemeralStateRepo` 추가 (7 개 테스트)
- [x] `docs/TEST_QBT_LIVE_MANUAL.md` 갱신
- [x] `live/CLAUDE.md` 실행 방법 섹션 갱신
- [x] `poetry run python validate_project.py` 통과 (passed=**792**, failed=**0**, skipped=**0**)
- [x] `poetry run black live/` 실행 완료
- [x] `README.md`: 변경 없음
- [ ] 로컬 `~/workspace/qbt-live-state/` 폴더 제거 (사용자 작업 — plan 범위 밖)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드**:
- `live/src/live/git_state.py` — `git_clone_shallow()` 추가
- `live/src/live/cli.py` — 주요 리팩토링:
  - `ephemeral_state_repo()` 컨텍스트 매니저 추가
  - 플래그 제거 (`--state-dir`, `--trade-date` 제외한 나머지 위에 명시)
  - 명령 제거 (`fetch-state`, `push-state`)
  - `main()` 내 디스패치를 write / read / none 세 가지 카테고리로 분류
- `live/src/live/constants.py` — 필요 시 `STATE_REPO_URL` 상수 추가

**테스트**:
- `live/tests/test_cli.py` — 대부분의 테스트에서 git 작업 mock 전환, 일부 테스트 리팩토링 또는 삭제
- `live/tests/test_git_state.py` — `git_clone_shallow` 케이스 추가
- `live/tests/test_workflows.py` — 새 워크플로우 구조 반영

**워크플로우**:
- `.github/workflows/daily_run.yml` — 간결화 (~20줄 축소 예상)

**문서**:
- `docs/TEST_QBT_LIVE_MANUAL.md` — 경로 표현 / 사용법 / 시뮬레이션 절차 갱신
- `live/CLAUDE.md` — 실행 방법 섹션 갱신
- `.env.example` — 파일 제거됨 (사용자 삭제). 이 plan 범위에서 갱신/참조하지 않음
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 기존 `~/workspace/qbt-live-state/` 폴더는 구현 완료 후 사용자가 수동 삭제. 플랜 마지막 단계에서 안내.
- 원격 `ingbeen/qbt-live-state` 리포는 기존 초기 상태를 그대로 사용 (최초 1회 시드는 이미 로컬에 있는 상태를 한 번 push 하거나, `--remote init` 후속 흐름으로 CI 에서 생성 가능)
- CLI 가 만드는 커밋 메시지 포맷 변경 가능성 있음 — `auto: live run YYYY-MM-DD HH:MM:SS` 형태로 통일
- 기존 `daily_run.yml` 의 `auto: daily run YYYY-MM-DD` 커밋 메시지도 동일 포맷으로 통일

## 6) 단계별 계획(Phases)

### Phase 1 — `git_clone_shallow` + `ephemeral_state_repo` 구현 (코어)

**작업 내용**:

- [x] `live/src/live/git_state.py` 에 `git_clone_shallow` + `embed_pat_in_url` 추가. URL PAT embed 시 비 HTTPS/빈 PAT 입력 거부, 에러 메시지에 PAT 누출 방지.
- [x] `live/src/live/constants.py` 에 `STATE_REPO_URL` 상수 추가
- [x] `live/src/live/cli.py` 에 `ephemeral_state_repo(push_on_success, commit_subcommand)` 컨텍스트 매니저 추가 — tempfile.TemporaryDirectory 기반, `STATE_REPO_PAT` 미설정 시 즉시 `ValueError`
- [x] `live/tests/test_git_state.py` 에 `TestEmbedPatInUrl` (4) + `TestGitCloneShallow` (4) 추가 → **14 passed**
- [x] `live/tests/test_cli.py` 에 `TestEphemeralStateRepo` (7) 추가 → **7 passed**

---

### Phase 2 — CLI 명령별 통합

**작업 내용**:

- [x] `cli.py` 의 각 `_cmd_*` 함수를 ephemeral 모드로 변경:
  - **쓰기 명령 (clone + push)**: `init`, `init-data`, `run-daily`, `rebuild-data` — 각각 `with ephemeral_state_repo(push_on_success=True, ...) as state_dir` 로 감쌈
  - **읽기 명령 (clone only)**: `drift`, `history` — `push_on_success=False`
  - **무관 명령 (clone 안 함)**: `notify-failure`, `fetch-fills` — 변경 없음
- [x] `run-daily` 는 ephemeral 진입 후 전체 11단계를 컨텍스트 안에서 실행. except 블록은 바깥에서 `_safe_notify_failure` 호출 후 재전파
- [x] 커밋 메시지 포맷: `auto: live {subcommand} YYYY-MM-DD HH:MM:SS KST` (KST 타임스탬프 포함)
- [x] 기존 헬퍼 (`_refresh_live_csvs`, `_build_market_bundle`, `_persist_history`) 는 state_dir 파라미터 받는 순수 함수로 유지, 내부 로직 불변

---

### Phase 3 — 플래그 제거 + 명령 제거 + 테스트 리팩토링

**작업 내용**:

- [x] `cli.py::_build_parser()` 수정:
  - `--state-dir` 전 파서에서 제거
  - `--period` (rebuild-data) 제거, 내부에서 `"max"` 하드코딩
  - `--no-rtdb`, `--no-notify` (run-daily) 제거
  - `fetch-state`, `push-state` 서브파서 제거
- [x] `_cmd_fetch_state`, `_cmd_push_state` 함수 삭제
- [x] `test_cli.py` 리팩토링 — 공통 `state_dir` fixture 추가 (ephemeral_state_repo 를 tmp_path yield 로 교체), 각 테스트에서 `--state-dir`/`--no-rtdb`/`--no-notify` 인자 제거, `_initialize_rtdb_app`/`_send_daily_notifications` mock 추가, `TestFetchState`/`TestPushState` 삭제
- [x] 전체 live 테스트 그린 유지: **283 passed**

---

### Phase 4 — Actions 워크플로우 간결화

**작업 내용**:

- [x] `.github/workflows/daily_run.yml`:
  - `Checkout qbt-live-state (private)` step 삭제
  - `--state-dir qbt-live-state` 인자 제거
  - `Commit & push state changes` step 삭제
  - run_first / run_retry 두 step 의 `env:` 에 `STATE_REPO_PAT` 추가
- [x] `test_workflows.py` 갱신:
  - `test_state_repo_checkout` → `test_state_repo_pat_injected_to_cli_env` 로 재정의
  - 새 네거티브 테스트 추가: `test_no_explicit_state_repo_checkout`, `test_no_shell_git_commit_push`, `test_run_daily_has_no_state_dir_flag`
  - `test_state_commit_and_push` 삭제 (CLI 가 담당)
  - 19 passed
- [x] `keepalive.yml` 변경 없음 (독립 흐름 유지)

---

### Phase 5 — 문서 갱신

**작업 내용**:

- [x] `docs/TEST_QBT_LIVE_MANUAL.md` 갱신:
  - #1 "원격 `qbt-live-state` 리포 초기 상태 확인" — ephemeral 시드 절차 안내
  - #2 텔레그램 테스트 — `.env.example` 참조 제거, 직접 `.env` 작성 절차 안내
  - #9 히스토리 파일 확인 — 로컬 git pull 대신 GitHub 웹 `history/` 확인
  - #27 데이터 검증 실패 시뮬레이션 — GitHub 웹 edit → workflow_dispatch → revert 방식으로 교체
  - #28 `live_state.json` 손상 시뮬레이션 — 동일하게 GitHub 웹 edit 방식
- [x] `live/CLAUDE.md` 실행 방법 섹션 갱신 — ephemeral 동작 설명, 필요 env 변수 목록, `.env.example` 참조 제거

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black live/` 실행 (3 파일 포맷)
- [x] Ruff auto-fix 1회 (`test_cli.py` import 순서)
- [x] 코드 smoke test: `poetry run python -m live.cli notify-failure --message "ephemeral plan smoke test"` → `.env` 자동 로드 + 정상 종료 확인
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=**792**, failed=**0**, skipped=**0**)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / CLI ephemeral state repo — 로컬 파일 0개 + 로컬/Actions 동일 경로
2. live / state 리포를 매 실행마다 shallow clone/push, 로컬 영속 폴더 제거
3. live / CLI 내부에서 state 리포 자동 clone/push, 플래그 단순화
4. live / 로컬과 Actions 가 단일 코드 경로를 타도록 state 관리 개편
5. live / ephemeral state repo + CLI 플래그 정리 + 워크플로우 간결화

## 7) 리스크(Risks)

- **Git clone / push 네트워크 실패**: 장애 시 자동 복구 금지 원칙에 따라 `RuntimeError` 로 즉시 중단하고 `_safe_notify_failure` 를 호출해 텔레그램 알림 발송 (기존 run-daily 예외 처리 경로 그대로 활용).
- **STATE_REPO_PAT 누락**: `ephemeral_state_repo` 진입 시점에 즉시 `ValueError` 발생하여 사용자에게 명확한 안내. ImportError graceful 금지 원칙과 일관.
- **커밋 충돌**: 단일 사용자 시나리오라 동시 push 경합은 거의 없음. 만약 경합하면 `git push` 가 reject 되고 `RuntimeError` 전파 — 사용자가 재실행하면 자동 복구됨 (CLI 가 다시 clone 하므로 최신 상태 기준).
- **tempdir cleanup 보장**: `tempfile.TemporaryDirectory` 의 `__exit__` 이 예외 상황에서도 호출되므로 안전. 테스트에서 명시적으로 검증.
- **테스트 리팩토링 범위**: `--no-rtdb`/`--no-notify` 의존 테스트가 상당수 있으면 Phase 3 작업량이 커질 수 있음. 구현 중에 범위 재평가하고 필요 시 Phase 분해.
- **원격 리포 초기 상태 부재**: 사용자가 아직 `ingbeen/qbt-live-state` 에 초기 커밋을 push 하지 않았다면 `run-daily` 첫 실행 전에 `init` + `init-data` 를 실행해야 함. 이는 자연스러운 시드 플로우이며 별도 bootstrap 워크플로우 불필요.
- **기존 로컬 `qbt-live-state/` 폴더의 처리**: 이 plan 으로 생성물이 의미가 사라짐. 구현 완료 후 사용자가 수동 삭제. 삭제 전에 중요한 로컬 변경이 있는지 `git status` 로 확인 권장.

## 8) 메모(Notes)

- 이 plan 은 이전 plan `PLAN_qbt_live_dotenv_cli.md` (✅ Done) 의 후속 작업. `.env` 자동 로드가 먼저 완성되어 있어야 `STATE_REPO_PAT` 을 무리 없이 읽을 수 있음.
- 사용자 선택: A안 (매번 새 tempdir). B안 (`~/.cache/` 캐시) 은 속도 이점이 있지만 "로컬 파일 0개" 원칙과 약하게 충돌하여 배제.
- 플래그 `--trade-date` 유지: 디버깅 시 과거 날짜 재현 용도. 실매매 운영에서는 기본값(오늘) 그대로 사용.
- `.github/workflows/daily_run.yml` 간결화 후에도 `continue-on-error` + 5분 대기 + retry 패턴은 유지. CLI 의 RuntimeError 를 Actions step 레벨에서 캡처 → 재시도 → 실패 알림 순서는 동일.
- CLI 커밋 메시지에 KST 시간 포함 — 커밋 이력을 보고 실행 시각을 사용자가 바로 파악하도록.

### 진행 로그 (KST)

- 2026-04-11 16:00: Draft 작성
- 2026-04-11 16:05: 사용자 `.env.example` 삭제 반영 (plan 에서 참조 제거). 승인 → In Progress
- 2026-04-11 16:15: Phase 1 완료 — `git_clone_shallow` + `embed_pat_in_url` + `ephemeral_state_repo`. test_git_state 14 passed + ephemeral 7 passed.
- 2026-04-11 16:25: Phase 2+3 완료 — 모든 `_cmd_*` ephemeral 적용, 플래그/명령 제거, test_cli.py 리팩토링 (state_dir fixture). live 283 passed.
- 2026-04-11 16:35: Phase 4 완료 — daily_run.yml 간결화, test_workflows 갱신. 19 passed.
- 2026-04-11 16:40: Phase 5 완료 — TEST_QBT_LIVE_MANUAL.md + live/CLAUDE.md 갱신.
- 2026-04-11 16:45: 마지막 Phase — black 적용, validate_project passed=792/failed=0/skipped=0. ✅ Done.
