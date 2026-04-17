# Implementation Plan: Git 정본 `history/states/{YYYY-MM-DD}.json` 일일 스냅샷 도입

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

**작성일**: 2026-04-17 15:30
**마지막 업데이트**: 2026-04-17 16:10
**관련 범위**: live (Git 정본 히스토리)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [src/live/history.py](../../src/live/history.py), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] `qbt-live-state` 리포에 `history/states/{YYYY-MM-DD}.json` 일별 스냅샷을 도입하여 과거 시점의 `live_state.json` 전체 상태를 git log 파싱 없이 파일 단위로 조회 가능하게 한다.
- [x] 스냅샷 내용은 해당 일자의 최종 `live_state.json` **완전 복사본** 이어야 하며 (`buffer_zone_state` / `pending_order` 등 모든 필드 보존), 직렬화 포맷은 `save_state` 와 100% 동일해야 한다.
- [x] `run-daily` 실행 시 항상 저장되며, 같은 날짜 재실행 시 덮어쓴다 (별도 옵션 플래그 없음, 항상 동작).

## 2) 비목표(Non-Goals)

- **과거 분 소급 생성 금지**: 본 plan 적용 시점 이전 날짜의 스냅샷은 만들지 않는다 (기존 `git log -p live_state.json` 으로 접근 가능).
- **자동 정리 / rolling 삭제 도입 금지**: 10 년 누적 용량이 수 MB 수준이라 영구 보존한다. retention 상수 / cleanup 함수 추가하지 않는다.
- **RTDB `/history/summary/` 제거는 본 plan 범위 밖**: 별도 Plan 2 (RTDB 재구성) 에서 다룬다. 본 plan 은 Git 정본만 건드린다.
- **`applied_*_ids.json` 3 파일 통합 금지**: 본 plan 에서 변경하지 않는다 (각 원장 독립 유지).
- **`live_state.json` 구조 / 직렬화 포맷 변경 금지**: 스냅샷은 복사본이므로 원본 포맷 수정 불필요.
- **`history/daily/{date}.json` 과 병합 금지**: `history/daily/` = "그 날 발생한 일" (결과 로그), `history/states/` = "그 날 종료 시점 상태". 관심사 다름.
- **앱(Android) / RTDB 스키마 / daily_runner 순수 계산 / 공통 예외 훅 / ephemeral clone·push 메커니즘**: 모두 변경하지 않음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `qbt-live-state` 정본 리포는 `live_state.json` 1 파일이 매일 덮어써지는 방식으로 포트폴리오 상태를 유지한다. 과거 특정 시점의 상태를 확인하려면 `git log -p live_state.json` 으로 commit diff 를 훑어야 하는데, 다음 문제가 있다:

1. **빠른 조회 불가** — "3월 15일 SSO 의 actual_shares 가 얼마였지?" 같은 질의에 git 명령 + diff 파싱이 필요해 일상 운영에서 실용적이지 않다.
2. **시계열 분석 불가** — 특정 필드 (예: `drift_pct`) 의 날짜별 추이를 쉽게 뽑을 수 없다. git log 출력은 사람 읽기용이지 기계 처리용이 아니다.
3. **완전 복구 번거로움** — 특정 시점으로 되돌리려면 `git show <commit>:live_state.json > live_state.json` 조합이 필요하고, 잘못된 커밋 선택 시 일관성이 깨질 수 있다.

`history/states/{YYYY-MM-DD}.json` 을 날짜 키 파일로 추가하면 위 세 문제를 동시에 해소할 수 있다. 용량 부담도 거래일 252 × 10 년 × 약 3KB ≈ 7.6MB 수준으로 무시 가능하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 / 장애 대응 원칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 아키텍처 / 장애 시 자동 복구 금지 + 무조건 알림 / QBT 본체 수정 금지 / 순수 계산·I/O 분리
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / 파일 I/O 격리 / 결정적 테스트
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `HISTORY_STATES_SUBDIR` 상수가 `src/live/constants.py` 에 추가됨
- [x] `run-daily` 실행 후 `history/states/{execution_date}.json` 파일이 생성되고, 그 내용이 같은 시점에 저장된 `live_state.json` 과 **바이트 단위로 일치**함
- [x] 같은 날짜로 `run-daily` 재실행 시 `history/states/{date}.json` 이 덮어쓰기로 정상 갱신됨 (suffix 추가 없음)
- [x] 저장 실패 시 예외가 그대로 전파되어 공통 예외 훅이 실패 알림을 발송함 (자동 복구 / 재시도 / 롤백 없음)
- [x] 신규 단위 테스트 추가 (`tests/live/test_state.py`: `TestSaveStateSnapshot` 4 건 + `tests/live/test_cli.py`: 통합 테스트에 스냅샷 바이트 동일성 assert 추가): 생성 여부 / 내용 동일성 / 덮어쓰기 시나리오
- [x] `src/live/history.py` docstring 의 "파일 종류" 섹션에 `history/states/{YYYY-MM-DD}.json` 항목 추가
- [x] `docs/TEST_QBT_LIVE_MANUAL.md` Phase A 에 수동 확인 항목 1 건 추가
- [x] `poetry run python validate_project.py` 통과 (passed=949, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase)
- [x] `README.md` 변경 없음 (실행 명령어/환경변수 불변)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/constants.py](../../src/live/constants.py) — `HISTORY_STATES_SUBDIR = "states"` 상수 추가 (기존 `HISTORY_DAILY_SUBDIR` 와 동일 섹션에 배치)
- [src/live/state.py](../../src/live/state.py) — 스냅샷 저장 헬퍼 (또는 기존 `save_state` 재사용만으로 충분하면 신규 함수 없이 호출 측에서 경로만 다르게 사용). 구현 시 판단하되, 의도를 명확히 하는 별도 함수 (`save_state_snapshot` 등) 를 두는 쪽을 우선 검토한다.
- [src/live/cli.py](../../src/live/cli.py) — `_cmd_run_daily` 에서 `save_state(result.updated_state, state_path)` **직후** 스냅샷 저장 호출 1 줄 추가. `trade_date.isoformat()` 을 파일명으로 사용.
- [src/live/history.py](../../src/live/history.py) — 모듈 docstring 의 "파일 종류" 목록에 `history/states/{YYYY-MM-DD}.json` 1 줄 추가 (파일 종류 설명만, 함수 구현 변경 없음).
- `tests/live/test_state.py` 또는 `tests/live/test_cli.py` — 시나리오 테스트 추가 (어느 파일이 적합한지는 구현 시 판단: 저수준 함수 단위면 `test_state.py`, `_cmd_run_daily` 통합이면 `test_cli.py`).
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) — Phase A 에 "`history/states/{날짜}.json` 존재 및 `live_state.json` 과 내용 동일" 확인 항목 추가.
- `README.md`: **변경 없음** (실행 명령어 / 환경변수 / 외부 계약 불변).

### 데이터/결과 영향

- **Git 정본 추가 파일**: `qbt-live-state/history/states/{YYYY-MM-DD}.json` — 기존 커밋 로직이 `state_dir` 변경 전체를 포함하므로 자동으로 같은 커밋에 포함된다. 추가 CI 작업 / 워크플로우 변경 없음.
- **RTDB 스키마 영향 없음**.
- **출력 포맷 영향 없음**: 스냅샷은 `save_state` 직렬화 규칙 (indent=2, `ensure_ascii=False`, `default=_json_default`) 을 그대로 사용하므로 diff 비교 시 잡음이 발생하지 않는다.
- **문서 내구성 판단**: 사용자 초안은 `DESIGN_QBT_LIVE_FINAL.md §8.1` 도 갱신 대상으로 제안했으나, §8.1 은 파일 트리를 기재하지 않고 "파일 트리 / 내부 스키마는 `src/live/CLAUDE.md` 및 `src/live/` 코드가 정본" 이라고 명시하고 있다. 따라서 §8.1 은 수정 대상에서 제외하고, 파일 종류 목록이 있는 `src/live/history.py` docstring 에만 반영한다.

## 6) 단계별 계획(Phases)

> 이 plan 은 핵심 인바리언트 / 지표 정의 / 에러 정책을 변경하지 않는다 (기존 저장 / 공통 예외 훅 / 직렬화 규칙을 그대로 재사용한다). 따라서 Phase 0 (레드) 없이 Phase 1 에서 테스트와 구현을 함께 추가한다.

---

### Phase 1 — 스냅샷 저장 구현 + 단위 테스트(그린 유지)

**작업 내용**:

- [x] `src/live/constants.py` 에 `HISTORY_STATES_SUBDIR: Final[str] = "states"` 추가 (`HISTORY_DAILY_SUBDIR` 바로 아래, 설명 주석 포함).
- [x] `src/live/state.py` 에 `save_state_snapshot(state, history_dir, execution_date) -> Path` 추가 (Option A, thin wrapper — 경로 계산 후 `save_state` 재사용). `__all__` 및 `HISTORY_STATES_SUBDIR` import 갱신.
- [x] `src/live/cli.py` `_cmd_run_daily` 수정: `save_state(result.updated_state, state_path)` 직후 `save_state_snapshot(result.updated_state, _history_dir(state_dir), trade_date)` 호출 추가. 실패 시 예외 그대로 전파 (공통 `main()` 훅이 `_safe_notify_failure` 호출).
- [x] 단위 테스트 추가:
  - `tests/live/test_state.py::TestSaveStateSnapshot` 4 건 — 경로 생성 / 바이트 단위 동일성 (pending_order + buffer_zone_state 포함) / 같은 날짜 덮어쓰기 / 중첩 디렉토리 자동 생성.
  - `tests/live/test_cli.py::test_run_daily_persists_history` 확장 — `history/states/{date}.json` 존재 + `live_state.json` 과 바이트 동일성 assert 추가.
  - 파일 I/O 격리: `tmp_path` 사용. 외부 네트워크 / Firebase / yfinance 는 기존 `conftest.py` autouse fixture 및 `_mock_rtdb_for_cli` 로 차단.
- [x] 신규 픽스처 도입하지 않음 (기존 픽스처로 충분).

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/live/history.py` 모듈 docstring "파일 종류" 목록에 `history/states/{YYYY-MM-DD}.json` — 일별 `live_state.json` 전체 스냅샷 (덮어쓰기 가능) 항목 추가 + `save_state_snapshot` 링크.
- [x] `docs/TEST_QBT_LIVE_MANUAL.md` Phase A "#9 qbt-live-state 히스토리 파일 확인" 에 절차 1 줄 + 체크 항목 1 건 추가 ("`history/states/{실행 날짜}.json` 존재 + 내용이 같은 커밋의 `live_state.json` 과 바이트 단위로 동일").
- [x] `README.md`: 변경 없음 확인 (실행 명령어 / 환경변수 / 외부 계약 불변).
- [x] `poetry run black .` 실행 (자동 포맷 적용 — `146 files left unchanged`, 이번 변경분은 이미 Black 규격 준수).
- [x] `poetry run python validate_project.py` 실행 → Ruff / PyRight / Pytest 모두 통과.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정 (`상태: ✅ Done`).

**Validation**:

- [x] `poetry run python validate_project.py` (passed=949, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / `history/states/{날짜}.json` 일일 스냅샷 추가 (Git 정본)
2. live / run-daily 직후 live_state.json 스냅샷을 `history/states/` 로 보존
3. live / 과거 시점 상태 조회 용 일별 스냅샷 도입 (history/states)
4. live / Git 정본에 일별 포트폴리오 상태 스냅샷 추가 + 수동 테스트 가이드 갱신
5. live / history/states 스냅샷 구현 + history.py 파일 목록 문서 갱신

## 7) 리스크(Risks)

- **리스크 1**: 스냅샷 저장이 `save_state` 직후에 실행되므로, 이 사이에 프로세스가 중단되면 `live_state.json` 은 이미 갱신됐지만 스냅샷은 누락될 수 있다.
  - 완화: 원칙적으로 이 중단 창은 `_atomic_write_text` 두 번의 간극이며 매우 짧다. 발생하더라도 다음 날 실행 시 다시 커밋된 `live_state.json` 으로 진행하므로 본체 정합성에는 영향 없다. 스냅샷 누락은 `history/states/` 에 해당 날짜 파일이 비는 형태로만 드러나며 운영자가 git log 로 복구 가능 (누락 일자 1 일에 한정).
  - 자동 재시도 / 롤백은 프로젝트 원칙(자동 복구 금지) 에 따라 도입하지 않는다.
- **리스크 2**: 같은 날짜에 `--trade-date` 를 명시한 재실행 결과가 초기 실행과 미세하게 달라지는 경우, 덮어쓰기로 인해 최초 실행 결과의 원본이 사라진다.
  - 완화: `run-daily` 는 idempotent 설계이며, 같은 날짜 재실행은 논리적으로 동일 결과를 낸다. 부득이한 차이는 git commit 이력으로 추적 가능 (직전 스냅샷 커밋을 `git show` 로 조회).
- **리스크 3**: 테스트 작성 시 기존 `_cmd_run_daily` 전체 경로를 모킹해야 하는 부담이 클 수 있다.
  - 완화: 저수준 (`save_state_snapshot`) 단위 테스트 + 기존 `test_cli.py` 의 `run-daily` 통합 테스트에 단일 assert 추가 방식으로 분할하여 모킹 범위를 최소화한다.

## 8) 메모(Notes)

- 설계서 §8.1 은 파일 트리 상세를 기재하지 않고 "`src/live/CLAUDE.md` 및 `src/live/` 코드가 정본" 이라고 명시. 따라서 설계서 수정은 생략하고 `src/live/history.py` docstring 의 파일 종류 목록에만 반영한다 (문서 내구성 원칙).
- `live_state.json` 는 `_atomic_write_text` 로 저장되므로 원자성이 보장된다. 스냅샷도 동일 경로 (`save_state` → `_atomic_write_text`) 를 통하므로 추가 atomic 고려 불필요.
- Option A 구현 시 `save_state_snapshot` 은 `save_state` 의 **thin wrapper** 로, 경로 계산 외 추가 로직을 넣지 않는다 (YAGNI).
- Plan 2 / Plan 3 과 독립. 순서 제약 없음.

### 진행 로그 (KST)

- 2026-04-17 15:30: plan 초안 작성.
- 2026-04-17 15:40: Phase 1 착수 (상태 → In Progress).
- 2026-04-17 15:55: 구현 완료 (`HISTORY_STATES_SUBDIR` 상수 / `save_state_snapshot` 헬퍼 / `_cmd_run_daily` 호출 / 단위 테스트 4 건 + 통합 테스트 1 건 확장).
- 2026-04-17 16:05: 문서 갱신 완료 (`history.py` docstring, `TEST_QBT_LIVE_MANUAL.md` Phase A #9).
- 2026-04-17 16:10: `black` + `validate_project.py` 통과 (passed=949, failed=0, skipped=0). 상태 → ✅ Done.

---
