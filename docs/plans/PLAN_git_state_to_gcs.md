# Implementation Plan: live 정본 저장소 git → Firebase Cloud Storage 이관

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-05-09 16:00
**마지막 업데이트**: 2026-05-09 16:00
**관련 범위**: live (storage_gateway 신설, cli ephemeral 컨텍스트 교체, git_state 제거)
**관련 문서**:

- [docs/BRIEFING_git_state_to_gcs.md](../BRIEFING_git_state_to_gcs.md) — 본 plan 의 입력이 되는 사전 합의서 (§3 결정사항 / §6 구현 방향성 / §7 영향 범위 / §8 리스크)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 SoT
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙

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

- [ ] live 정본(LiveState / 멱등 원장 / 주가 CSV / 일별 스냅샷 / 감사 로그) 의 저장 매체를 `qbt-live-state` 프라이빗 git 리포에서 Firebase Cloud Storage(GCS) 버킷으로 이관한다.
- [ ] `STATE_REPO_PAT` 환경변수를 제거하고 `GOOGLE_APPLICATION_CREDENTIALS` 단일 자격증명으로 정본 접근을 통일한다.
- [ ] 기존 데이터(qbt-live-state git 리포)를 1회성 마이그레이션 스크립트로 GCS 버킷에 디렉토리 구조 그대로 복제한다.
- [ ] 회귀 테스트(`test_regression.py`)로 `equity` / `positions` / `cash` 가 이관 전후 동일함을 보장한다.

## 2) 비목표(Non-Goals)

다음은 본 이관 plan 의 범위가 **아니다**. BRIEFING §9 와 동일.

- `chart_data` 가 RTDB 에 직접 write 하는 부분의 GCS 이관 (RTDB 적합성 유지)
- Object Versioning 활성화 (Soft Delete 30일만 사용)
- 다중 리전 / cross-region 백업
- GCS lifecycle 규칙
- 외부 객체 스토리지 (R2 등) 도입
- `qbt-live-state` git 리포 자체의 archive / 삭제 (이관 검증 후 사용자가 수동 결정)
- 코드 레벨 임계치 검사 (BRIEFING §3.5 사용자 명시 거부)
- 결제 자동 차단 인프라 (Pub/Sub + Cloud Function — BRIEFING §3.5 사용자 명시 거부)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `qbt-live-state` git 리포가 매일 CSV / JSON / JSONL 변경분을 commit 받아 영구 누적 (repo bloat).
- 매 CLI 실행마다 shallow clone 트래픽 발생.
- 본질적으로 git 은 객체 저장소가 아니라 변경 이력 추적 도구. "프로그램이 매 실행마다 파일을 올리고 받는 객체 저장소" 용도로는 의미상 무리.
- 상세 배경은 [BRIEFING §1](../BRIEFING_git_state_to_gcs.md#L21).

### 영향받는 규칙 (반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 프로젝트 전반 규칙 / 코딩 표준
- [docs/CLAUDE.md](../CLAUDE.md) — 계획서 작성 / 운영 규칙 (SoT)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 SoT (특히 핵심 원칙 1 "장애 시 자동 복구 금지", 원칙 3 "순수 계산 / I/O 분리")
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙 (Given-When-Then, 결정적 / 파일 격리 / 외부 네트워크 mock)
- [docs/BRIEFING_git_state_to_gcs.md](../BRIEFING_git_state_to_gcs.md) — 본 plan 의 입력. **§3 결정사항은 재검토 대상이 아님**

### Pre-conditions (사용자 인프라 작업 — 별도 Phase 로 분해하지 않음)

BRIEFING §4 의 5단계가 모두 완료된 상태:

1. ✅ Blaze 플랜 업그레이드 (2026-05-08)
2. ✅ Cloud Storage 버킷 생성 (`qbt-live.firebasestorage.app`, `us-central1`) (2026-05-08)
3. ✅ Soft Delete 30일 적용 (2026-05-08)
4. ✅ 예산 알림 (50% / 90% / 100%, ₩1, `qbt-live` 프로젝트만)
5. ✅ Service Account Storage 권한 (저장소 관리자 + Firebase Admin SDK 관리자 서비스 에이전트)

> 버킷 이름 `qbt-live.firebasestorage.app` 의 정확한 문자열은 사용자 공유 후 Phase 2 진입 시점에 `constants.py` 의 `STATE_BUCKET_NAME` 상수로 확정.

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] `src/live/storage_gateway.py` 신설 + 단위 테스트 통과
- [ ] `cli.py` 의 `ephemeral_state_repo` 컨텍스트 → GCS 다운로드 / 업로드 기반으로 교체 완료
- [ ] `live_state.json` 마지막 업로드 순서 보호 (BRIEFING §6.5)
- [ ] `constants.py` 에서 git 관련 상수 제거 + `STATE_BUCKET_NAME` 추가
- [ ] `git_state.py` + `tests/live/test_git_state.py` 제거
- [ ] `.github/workflows/daily_run.yml` 의 `STATE_REPO_PAT` secret 사용 제거
- [ ] 1회성 마이그레이션 스크립트 작성 (사용자가 cutover 직전 1회 실행)
- [ ] 회귀 테스트 (`test_regression.py`) 통과 — equity / positions / cash 이관 전후 일치
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase 에서)
- [ ] 문서 업데이트:
  - `README.md`: **변경 있음** (live 섹션 인프라 설명에서 git 정본 → GCS 정본 표현 갱신)
  - `docs/COMMANDS.md`: **변경 있음** (live 워크플로우 환경변수 안내 갱신, 마이그레이션 스크립트 사용법 추가)
  - `src/live/CLAUDE.md`: **변경 있음** ("ephemeral state repo" 섹션 → "GCS 버킷 워크스페이스" 섹션, 모듈 표에서 `git_state.py` 제거, 환경변수 목록에서 `STATE_REPO_PAT` 제거)
  - `docs/DESIGN_QBT_LIVE_FINAL.md`: **변경 있음** (git 정본 기술 부분 GCS 정본으로 갱신)
  - `docs/BRIEFING_git_state_to_gcs.md`: **변경 없음** (사전 합의 문서, 본 plan 의 입력)
- [ ] plan 체크박스 최신화 (Phase / DoD / Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

**신설**:

- `src/live/storage_gateway.py` — GCS 객체 read / write / list / delete 단일 객체 단위 래퍼 + 다운로드/업로드 워크스페이스 컨텍스트
- `tests/live/test_storage_gateway.py` — storage_gateway 단위 테스트 (firebase_admin.storage 모킹)
- `scripts/migrate/git_state_to_gcs.py` — 1회성 데이터 마이그레이션 스크립트 (qbt-live-state git 리포 → GCS 버킷)

**수정**:

- `src/live/cli.py` — `ephemeral_state_repo` 컨텍스트를 GCS 워크스페이스로 교체, `git_state` import 제거, `_now_kst_for_commit` / commit message 로직 제거
- `src/live/constants.py` — 제거: `STATE_REPO_URL` / `STATE_REPO_PAT_ENV_KEY` / `GIT_BOT_NAME` / `GIT_BOT_EMAIL`. 추가: `STATE_BUCKET_NAME` (값은 사용자 공유 후 확정).
- `tests/live/conftest.py` — `firebase_admin.storage` 모킹 픽스처 추가
- `.github/workflows/daily_run.yml` — `STATE_REPO_PAT` env / secrets 제거 (run-daily / notify-failure 두 job 모두)
- `README.md` — live 섹션 인프라 설명
- `docs/COMMANDS.md` — live 환경변수 안내 + 마이그레이션 스크립트 사용법
- `src/live/CLAUDE.md` — ephemeral state repo → GCS 버킷 워크스페이스
- `docs/DESIGN_QBT_LIVE_FINAL.md` — git 정본 기술 부분

**제거**:

- `src/live/git_state.py` — 전체 삭제
- `tests/live/test_git_state.py` — 전체 삭제

### 데이터/결과 영향

- 출력 스키마 / 산식 / 비즈니스 로직 변경 없음.
- LiveState / DailyResult / 회귀 검증 영향 없음.
- 정본 위치만 변경: `qbt-live-state` git 리포 → `gs://qbt-live.firebasestorage.app/...` (디렉토리 구조 1:1 미러링).
- 환경변수: `STATE_REPO_PAT` 제거. `GOOGLE_APPLICATION_CREDENTIALS` 그대로 유지.

## 6) 단계별 계획(Phases)

### Phase 0 — storage_gateway 정책 / 인터페이스를 테스트로 먼저 고정 (레드)

> 핵심 인바리언트(예외 정책 / 변경된 파일만 upload / live_state.json 마지막 upload 순서 / generation precondition) 를 테스트로 먼저 고정한다. 본 Phase 는 레드 허용.

**작업 내용**:

- [x] `tests/live/conftest.py` 에 `firebase_admin.storage` 모킹 픽스처 추가 (네트워크 격리 autouse 와 함께) — `FakeBucket` / `FakeBlob` + `fake_gcs_bucket` 픽스처
- [x] `tests/live/test_storage_gateway.py` 신설 (16개 테스트):
  - [x] download / upload / list_with_prefix / delete 의 단위 테스트
  - [x] 실패 시 `RuntimeError` 전파 (자동 복구 금지)
  - [x] generation precondition (`if_generation_match`) 동작 — 412 Precondition Failed → `RuntimeError`
  - [x] 워크스페이스 컨텍스트 정책: tempdir 생성 → prefix 기반 download → yield → 변경된 파일만 upload → tempdir 자동 삭제
  - [x] 변경 감지 정책: download 시점 sha256 스냅샷 → 컨텍스트 종료 시 비교
  - [x] write 순서 보호: `live_state.json` 이 항상 마지막 upload 가 되는지
  - [x] read-only 모드 (`push_on_success=False`): upload skip
  - [x] 컨텍스트 본문 예외 시 upload skip (LiveState 일관성 보호)
- [x] 레드 상태 확인 — `ImportError: cannot import name 'storage_gateway' from 'live'` (의도된 레드)

> 주의: Phase 0 의 테스트는 storage_gateway 의 **공개 API 시그니처** 를 고정한다. 시그니처가 흔들리면 Phase 1 / 2 가 어려워지므로 인터페이스 결정에 신중을 기한다.

---

### Phase 1 — storage_gateway 구현 (그린 유지)

Phase 0 테스트가 통과하도록 storage_gateway 를 구현한다.

**작업 내용**:

- [x] `src/live/constants.py` 에 `STATE_BUCKET_NAME` 추가 (Phase 2 작업 분담 — Phase 1 의 storage_gateway import 의존성 해소)
- [x] `src/live/storage_gateway.py` 작성:
  - [x] `firebase_admin.storage.bucket(name=STATE_BUCKET_NAME)` 으로 버킷 핸들 획득
  - [x] `download_blob(blob_path: Path | str, dest_local_path: Path) -> None`
  - [x] `upload_blob(local_path: Path, blob_path: Path | str, *, if_generation_match: int | None = None) -> int` — 업로드 후 generation 반환
  - [x] `list_blobs_with_prefix(prefix: str) -> list` — google blob 객체 그대로 반환 (호출자가 `.name` / `.size` / `.generation` 사용)
  - [x] `delete_blob(blob_path: Path | str) -> None` — Soft Delete 가 자동 보호
  - [x] `state_workspace(*, push_on_success: bool)` 컨텍스트 매니저:
    - tempdir 생성 → 모든 blob download → sha256 스냅샷 기록 → yield workspace → 변경된 파일만 upload → tempdir 자동 삭제
    - `push_on_success=False` 시 upload skip
    - `_sort_for_upload` 가 `live_state.json` 을 가장 마지막에 정렬
    - 본문 예외 시 yield 가 raise → upload 단계 미진입 (LiveState 일관성 보호)
  - [x] 모든 실패 → `RuntimeError` 전파 (live 도메인 핵심 원칙 1)
- [x] Phase 0 테스트 모두 통과 확인 (그린) — **17 passed**

---

### Phase 2 — cli.py 의 ephemeral 컨텍스트 교체 + constants 갱신 (그린 유지)

기존 `ephemeral_state_repo` 컨텍스트를 storage_gateway 의 `state_workspace` 로 교체한다. 비즈니스 로직 (run-daily / reset / rebuild-data / drift / backfill-chart-years) 은 변경하지 않는다 — `state_dir` 시그니처가 동일하므로 컨텍스트만 바꾸면 됨.

**작업 내용**:

- [x] `src/live/constants.py` 갱신:
  - [x] 추가: `STATE_BUCKET_NAME: Final[str] = "qbt-live.firebasestorage.app"` (Phase 1 에서 미리 처리)
  - [x] 제거: `STATE_REPO_URL` / `STATE_REPO_PAT_ENV_KEY` / `DEFAULT_LIVE_STATE_DIR` (그린 유지를 위해 `GIT_BOT_NAME` / `GIT_BOT_EMAIL` 은 Phase 3 의 `git_state.py` 제거와 함께 정리)
- [x] `src/live/cli.py` 갱신:
  - [x] `from live import data_validator, git_state, history, ...` → `git_state` 제거, `storage_gateway` 추가
  - [x] `ephemeral_state_repo` 컨텍스트 함수 자체를 제거하고 호출 측 6곳을 `storage_gateway.state_workspace(push_on_success=...)` 직접 호출로 교체 (PLAN 본문은 "이름 유지" 표현이지만, dead code 잔존 방지를 위해 함수 자체 제거가 더 깔끔)
  - [x] `_now_kst_for_commit` 함수 제거 (commit message 불필요)
  - [x] `STATE_REPO_PAT` 환경변수 검사 로직 제거 — `ephemeral_state_repo` 함수와 함께 사라짐
  - [x] orphan import 정리 — `tempfile`, `from collections.abc import Iterator`, `from contextlib import contextmanager`
  - [x] read-only 명령 (`drift` / `backfill-chart-years`) 의 `push_on_success=False` 그대로 유지
- [x] 회귀 테스트 통과 확인 — `test_storage_gateway` 17 + `test_constants` 18 + `test_cli` 50 = **85 passed**
- [x] 기존 통합 테스트의 mock 을 storage 버전으로 교체:
  - [x] `state_dir` 픽스처 — `cli_module.storage_gateway.state_workspace` 를 mock
  - [x] `test_reset_aborts_on_firebase_init_failure` — git_clone 검증 → workspace 진입 검증
  - [x] `test_holiday_early_exit_skips_state_workspace` (이름 변경) — `_fail_workspace` sentinel
  - [x] `TestEphemeralStateRepo` 클래스 전체 폐기 (storage_gateway 단위 테스트로 대체)
  - [x] `test_constants.py` — `DEFAULT_LIVE_STATE_DIR` 검증 항목 제거, `STATE_BUCKET_NAME` 검증 추가

> 주의: 이 시점에 `git_state.py` 파일과 `GIT_BOT_*` 상수는 아직 존재하지만 cli.py 에서 import 하지 않으므로 dead code. Phase 3 에서 삭제.

---

### Phase 3 — git_state 제거 + 워크플로우 yaml 정리 (그린 유지)

역할이 사라진 git 관련 코드와 secret 사용을 제거한다.

**작업 내용**:

- [ ] `src/live/git_state.py` 삭제
- [ ] `tests/live/test_git_state.py` 삭제
- [ ] `.github/workflows/daily_run.yml` 갱신:
  - [ ] `run-daily` job 의 `env:` 블록에서 `STATE_REPO_PAT: ${{ secrets.STATE_REPO_PAT }}` 라인 제거
  - [ ] `notify-failure` job 도 동일하게 STATE_REPO_PAT 사용 시 제거
  - [ ] `GOOGLE_APPLICATION_CREDENTIALS` 등 기존 패턴 그대로 유지
- [ ] live 관련 다른 워크플로우 (`keepalive.yml` 등) 에서 STATE_REPO_PAT 참조 여부 확인 및 정리
- [ ] grep 으로 잔존 참조 확인: `git_state` / `STATE_REPO_PAT` / `STATE_REPO_URL` / `GIT_BOT_NAME` 가 코드 / 테스트 / 문서 / yaml 어디에도 남지 않았는지 (단, BRIEFING 문서의 변경 이력 / docs/archive 는 예외)

---

### Phase 4 — 1회성 데이터 마이그레이션 스크립트 (그린 유지)

사용자가 cutover 직전 1회 실행할 마이그레이션 스크립트를 작성한다.

**작업 내용**:

- [ ] `scripts/migrate/` 디렉토리 신설 (또는 `scripts/live/` 안에 위치 — 폴더 분류 규칙은 [scripts/CLAUDE.md](../../scripts/CLAUDE.md) 확인 후 결정)
- [ ] `scripts/migrate/git_state_to_gcs.py` 작성:
  - [ ] 기존 `qbt-live-state` 리포를 일반 clone (depth 미지정)
  - [ ] 모든 파일을 GCS 버킷에 업로드 (디렉토리 구조 1:1 미러링)
  - [ ] 업로드 검증: 객체 수 비교 / 총 사이즈 비교 / 핵심 파일(`live_state.json`) sha256 비교
  - [ ] 검증 실패 시 즉시 stderr + `sys.exit(1)`
  - [ ] dry-run 옵션 (실제 업로드 전 카운트 / 사이즈만 출력)
- [ ] `docs/COMMANDS.md` 에 실행 가이드 추가 (사용자가 직접 실행)
- [ ] 본 스크립트 자체는 1회 실행 후 더 이상 필요 없으나, 폐기 / 보존은 사용자 결정 (Notes 에 기록)

> 주의: AI 모델은 [루트 CLAUDE.md "스크립트 실행 규칙"](../../CLAUDE.md) 에 따라 본 스크립트를 직접 실행하지 않는다. 사용자가 cutover 시점에 직접 실행한다.

---

### Phase 5 — 도메인 문서 갱신 (그린 유지)

변경된 인프라 / 환경변수 / 모듈 구조에 맞춰 도메인 문서를 갱신한다.

**작업 내용**:

- [ ] `src/live/CLAUDE.md`:
  - [ ] "폴더 구조" 의 `git_state.py` 행 제거, `storage_gateway.py` 행 추가
  - [ ] "모듈별 역할 요약" 표에서 `git_state.py` 제거, `storage_gateway.py` 추가
  - [ ] "실행 방법" 의 ephemeral state repo 단락 → GCS 버킷 워크스페이스 단락으로 갱신
  - [ ] "환경변수" 목록에서 `STATE_REPO_PAT` 제거
  - [ ] "인프라 정보" 표의 "상태 리포 (프라이빗)" 행 제거 또는 "GCS 버킷" 으로 교체
- [ ] `README.md` 의 live 섹션 인프라 설명 갱신
- [ ] `docs/COMMANDS.md`:
  - [ ] live 워크플로우 환경변수 안내 (STATE_REPO_PAT 제거)
  - [ ] 마이그레이션 스크립트 실행 가이드 추가 (Phase 4 와 함께)
- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md` 의 git 정본 기술 부분 갱신 (해당 절 검색 후 GCS 정본으로 정정)

---

### 마지막 Phase — 최종 검증 (그린 + 포맷)

DoD 체크리스트 / Validation 마무리 + 자동 포맷 적용.

**작업 내용**:

- [ ] `poetry run black .` 실행 (자동 포맷 적용 — 본 plan 에서 처음으로 한 번만)
- [ ] DoD 체크리스트 최종 업데이트
- [ ] 전체 Phase 체크리스트 최종 업데이트
- [ ] 상태 → ✅ Done

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / git_state 를 GCS 기반 storage_gateway 로 교체 (정본 마이그레이션)
2. live / qbt-live-state 리포 어뷰징 해소 — Firebase Cloud Storage 단독 정본화
3. live / ephemeral state repo → GCS 버킷, STATE_REPO_PAT 제거
4. live / 정본 저장소 git → GCS 이관 + 1회성 마이그레이션 스크립트
5. live / GCS storage_gateway 신설 + 환경변수 단일화 (GOOGLE_APPLICATION_CREDENTIALS)

## 7) 리스크(Risks)

BRIEFING §8 의 리스크 표를 본 plan 의 검증 단계에 매핑.

- **부분 업로드로 LiveState 일관성 깨짐**: `live_state.json` 을 마지막에 upload (Phase 1 / 2). 다음 실행 시 download 로 정합 복원.
- **동시 실행 (Actions + 사용자 수동) 으로 덮어쓰기 충돌**: Phase 0 / 1 의 generation precondition 옵션 제공. 1차로는 운영 가이드로 회피 (Phase 5 문서).
- **Blaze 한도 초과 청구**: BRIEFING §3.5 정책 (예산 메일 알림 + 사용자 수동 차단). 본 plan 범위 외.
- **Service Account 권한 부족**: Pre-condition 5단계에서 확인 완료 (저장소 관리자 + Firebase Admin SDK 관리자 서비스 에이전트).
- **데이터 이관 누락**: Phase 4 마이그레이션 스크립트의 객체 수 / 사이즈 / sha256 비교 검증.
- **회귀 (equity / positions / cash 변화)**: Phase 2 직후 회귀 테스트 통과 확인. 마지막 Phase 의 validate_project.py 가 최종 보장.
- **Soft Delete 만으로 복구 불가능한 사고**: 일별 스냅샷 (`history/states/{date}.json`) 1차 복구 수단 — 그대로 보존.

## 8) 메모(Notes)

### 사전 합의 (재검토 금지)

본 plan 은 [docs/BRIEFING_git_state_to_gcs.md](../BRIEFING_git_state_to_gcs.md) 의 §3 결정사항을 그대로 입력으로 한다. 다음 결정은 plan 작성 / 실행 단계에서 **재검토 대상이 아니다**:

- 옵션 A (GCS 단독) 채택
- Soft Delete 30일 적용 (Object Versioning 미사용)
- 리전 `us-central1`
- 자격증명: `GOOGLE_APPLICATION_CREDENTIALS` 재사용
- 청구 보호: 메일 알림 + 사용자 수동 차단 (자동 차단 / 코드 임계치 모두 미도입)

### 사용자 공유 정보 (확인 완료)

| 항목 | 값 |
| --- | --- |
| Blaze 업그레이드 | 예 |
| 버킷 이름 | `qbt-live.firebasestorage.app` (Phase 2 진입 전 확정 필요) |
| 버킷 리전 | `us-central1` |
| Soft Delete 30일 | 예 |
| 예산 알림 | 예 (50/90/100%, ₩1, qbt-live 프로젝트만) |
| Service Account Storage 권한 | 자동 포함 (저장소 관리자 + Firebase Admin SDK 관리자 서비스 에이전트) |

### Phase 4 마이그레이션 스크립트 폐기

1회 실행 후 폐기 / 보존은 사용자 결정. `docs/archive/` 로 이동하거나 git 에서 제거 — 본 plan 범위 외.

### 진행 로그 (KST)

- 2026-05-09 16:00: 본 plan 신설 (사전 합의 [BRIEFING_git_state_to_gcs.md](../BRIEFING_git_state_to_gcs.md) 입력)

---
