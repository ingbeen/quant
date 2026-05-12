# Implementation Plan: GCS state_workspace 진입 전 Firebase 초기화 강제

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

**작성일**: 2026-05-12 09:45
**마지막 업데이트**: 2026-05-12 09:55
**관련 범위**: live
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] `state_workspace` 컨텍스트를 진입하는 **모든 CLI 명령**이, 진입 전에 Firebase Admin SDK 를 초기화하도록 정합화한다 (`reset` 패턴 적용).
- [x] `run-daily` 가 Firebase 초기화 누락으로 인한 `ValueError: The default Firebase app does not exist` 없이 정상 진행되도록 한다.
- [x] 동일 회귀의 재발을 방지하기 위해, "Firebase 초기화 실패 시 `state_workspace` 미진입" 회귀 테스트를 영향 받는 모든 명령에 추가한다.

## 2) 비목표(Non-Goals)

- `storage_gateway` 내부에 lazy Firebase 초기화를 추가하지 않는다 (모듈 책임 경계 유지 — `rtdb_gateway` 만 Firebase 초기화 책임).
- Firebase 초기화 자체의 로직 / 환경변수 / credential 처리 방식은 변경하지 않는다.
- `state_workspace` 인터페이스 / 시그니처 / 동작은 변경하지 않는다.
- `daily_runner` / 회계 로직 / drift 계산 등 비즈니스 로직은 변경하지 않는다.
- 운영자 자격증명 / GCS 버킷 정책 변경 없음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 커밋 `620cbb8` (GCS 단독 정본화) 이후 `storage_gateway.state_workspace` 가 `firebase_admin.storage.bucket()` 을 호출하지만, 이 함수는 **default Firebase app** 을 요구한다.
- 현재 `cli.py` 의 5개 명령 중 `_cmd_reset` 만 `_require_rtdb_app()` 을 `state_workspace` 진입 **이전** 에 호출하고 있다.
- `_cmd_run_daily` / `_cmd_backfill_chart_years` 는 Firebase 초기화가 `state_workspace` 진입 **이후** 에 일어나며, `_cmd_rebuild_data` / `_cmd_drift` 는 Firebase 초기화 호출 자체가 없다.
- 결과적으로 위 4개 명령은 모두 GCS bucket 핸들 획득 단계에서 `ValueError: The default Firebase app does not exist` → `RuntimeError("GCS 버킷 핸들 획득 실패: ...")` 로 즉시 실패한다.
- `run-daily` 는 GitHub Actions 정기 실행이며, 현재 상태로는 매일 자동 실행이 실패한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md)
- live 도메인 [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- 테스트 규칙 [tests/CLAUDE.md](../../tests/CLAUDE.md)
- docs 규칙 [docs/CLAUDE.md](../CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `state_workspace` 를 사용하는 5개 CLI 명령(`reset` / `run-daily` / `rebuild-data` / `drift` / `backfill-chart-years`) 모두 **`state_workspace` 진입 전에** Firebase Admin SDK 가 초기화되어 있음을 코드 흐름상 보장한다.
- [x] `run-daily` / `rebuild-data` / `drift` / `backfill-chart-years` 각각에 "Firebase 초기화 실패 시 `state_workspace` 미진입" 회귀 테스트를 추가한다 (`reset` 의 기존 테스트와 동일 패턴).
- [x] `poetry run python validate_project.py` 통과 (passed=1025, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 문서 업데이트 여부 명시: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / `src/live/CLAUDE.md` 변경 없음 / plan 체크리스트 갱신
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/cli.py` — `_cmd_run_daily` / `_cmd_rebuild_data` / `_cmd_drift` / `_cmd_backfill_chart_years` 의 Firebase 초기화 호출 위치를 `state_workspace` 진입 직전으로 이동/추가
- `tests/live/test_cli.py` — 위 4개 명령에 회귀 테스트 추가
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어 / CLI 옵션 변동 없음)

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 기존 결과 비교 불필요 (코드 흐름 순서 정정만)
- `drift` / `rebuild-data` / `backfill-chart-years` 는 환경변수 `GOOGLE_APPLICATION_CREDENTIALS` 가 없으면 사실상 실행 불가였으나, 이번 변경으로 **실패 시점이 명시적인 RuntimeError 로 앞당겨진다** (운영 측면에서 개선)

## 6) 단계별 계획(Phases)

### Phase 0 — 회귀 테스트 선행 추가 (레드 허용)

> 이 작업은 "코드 흐름 순서" 라는 정책을 코드로 고정하는 것이므로 Phase 0 으로 분리한다.

**작업 내용**:

- [x] `tests/live/test_cli.py` 에 `_cmd_run_daily` 회귀 테스트 추가: Firebase 초기화 실패 시 `state_workspace` 미진입 + exit 1.
- [x] `_cmd_rebuild_data` 동일 패턴 회귀 테스트 추가 (단일 ticker / 전체 ticker 각 1 개).
- [x] `_cmd_drift` 동일 패턴 회귀 테스트 추가 (새 `TestCmdDrift` 클래스).
- [x] `_cmd_backfill_chart_years` 동일 패턴 회귀 테스트 추가.
- [x] 이 시점에서는 새 테스트가 **실패(레드)** 함을 확인 (5 failed, reset 의 기존 그린 테스트 1 passed).

---

### Phase 1 — `cli.py` Firebase 초기화 순서 정합화 (그린 유지)

**작업 내용**:

- [x] `_cmd_run_daily`: 휴장 체크 / `applied_at_kst` 산출 직후, `state_workspace` 진입 **이전**에 `_require_rtdb_app()` 을 호출하도록 이동. 기존 state_workspace 내부의 `_require_rtdb_app()` 호출은 제거하고, 그 결과 `rtdb_app` 변수를 컨텍스트 안에서 그대로 사용한다.
- [x] `_cmd_rebuild_data`: 함수 시작 부분(두 분기 공통)에서 `_require_rtdb_app()` 호출 추가. 반환 값은 사용하지 않지만 Firebase default app 초기화가 목적.
- [x] `_cmd_drift`: `state_workspace` 진입 전에 `_require_rtdb_app()` 호출 추가. drift 자체는 RTDB 를 쓰지 않지만 GCS bucket 접근에 필요.
- [x] `_cmd_backfill_chart_years`: 함수 시작 부분에서 `_require_rtdb_app()` 호출하고 결과를 `rtdb_app` 으로 보관. `state_workspace` 내부 후반부의 기존 `_require_rtdb_app()` 호출은 제거하고, 보관해둔 `rtdb_app` 을 사용한다.
- [x] Phase 0 의 회귀 테스트가 모두 **그린** 으로 통과함을 확인.
- [x] `state_dir` fixture 가 GCS state_workspace 진입의 사전조건인 Firebase 초기화도 함께 no-op 으로 차단하도록 갱신 (테스트 격리 — 환경변수 / 자격증명 의존 제거). 회귀 테스트는 monkeypatch 로 raise 동작을 직접 덮어쓴다.
- [x] 기존 `test_backfill_rtdb_init_failure_exits_without_notify` 의 mock 패턴을 새 코드 흐름에 맞춰 `_require_rtdb_app` raise 로 갱신.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `README.md` / `docs/COMMANDS.md` 변경 불필요 확인.
- [x] `src/live/CLAUDE.md` 의 "GCS 정본 워크스페이스" 단락이 본 변경과 모순되지 않음을 확인 (변경 없음).
- [x] `poetry run black .` 실행 (자동 포맷 적용).
- [x] 변경된 4개 명령의 단위 테스트 + 기존 cli 테스트 전체가 그린임을 확인.
- [x] DoD 체크리스트 최종 업데이트.
- [x] 전체 Phase 체크리스트 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1025, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / GCS state_workspace 진입 전 Firebase 초기화 강제 (run-daily 회복)
2. live / state_workspace 사용 명령 전수 Firebase init 순서 정합화 + 회귀 테스트
3. live / GCS 단독 정본화 이후 default Firebase app 초기화 순서 버그 수정
4. live / run-daily / drift / rebuild-data / backfill-chart-years Firebase init 선행 강제
5. live / GCS bucket 접근 전 Firebase init 보장 — cli 5개 명령 정합화 및 회귀 방지

## 7) 리스크(Risks)

- `drift` / `rebuild-data` / `backfill-chart-years` 는 그간 환경변수가 누락된 상태에서도 "GCS 단계까지 가다가" 실패했는데, 이번 변경으로 더 이른 시점에 RuntimeError 가 발생한다. → 실패 시점만 앞당겨질 뿐 사용자 영향은 동일 또는 개선. 별도 마이그레이션 불필요.
- 기존 테스트 중 `_initialize_rtdb_app` 만 mock 하고 `_require_rtdb_app` 은 mock 하지 않는 케이스가 있을 수 있음. Phase 1 적용 후 테스트 그린을 검증해 회귀 여부 확인.
- 회귀 테스트는 monkeypatch 로 `_require_rtdb_app` 을 `raise RuntimeError` 로 만든 뒤 `state_workspace` 가 호출되지 않음을 검증 — `reset` 의 기존 패턴과 동일하므로 추가 리스크 낮음.

## 8) 메모(Notes)

- 이 plan 은 코드 흐름 순서 정정에 집중하며, 비즈니스 로직 / 인터페이스 / 환경변수 / 외부 API 는 변경하지 않는다.
- `storage_gateway` 자체에는 lazy init / 자동 복구 코드를 추가하지 않는다 ([src/live/CLAUDE.md](../../src/live/CLAUDE.md) "1. 장애 시 자동 복구 금지" 원칙).

### 진행 로그 (KST)

- 2026-05-12 09:45: plan 작성
- 2026-05-12 09:48: Phase 0 — `tests/live/test_cli.py` 에 4 개 명령 회귀 테스트 추가 (5 failed / 1 passed 확인 = 레드)
- 2026-05-12 09:50: Phase 1 — `src/live/cli.py` 의 `_cmd_run_daily` / `_cmd_rebuild_data` / `_cmd_drift` / `_cmd_backfill_chart_years` 에 Firebase 초기화 선행 적용
- 2026-05-12 09:51: Phase 1 후속 — `state_dir` fixture 갱신 + `test_backfill_rtdb_init_failure_exits_without_notify` mock 패턴 정합화
- 2026-05-12 09:55: 최종 검증 — `validate_project.py` passed=1025, failed=0, skipped=0

---
