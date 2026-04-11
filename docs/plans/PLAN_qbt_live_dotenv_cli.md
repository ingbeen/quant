# Implementation Plan: live CLI `.env` 자동 로드 (python-dotenv)

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

**작성일**: 2026-04-11 15:30
**마지막 업데이트**: 2026-04-11 15:30
**관련 범위**: live (수동 테스트 지원)
**관련 문서**: [live/CLAUDE.md](../../live/CLAUDE.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] 로컬에서 `poetry run python -m live.cli ...` 실행 시 프로젝트 루트의 `.env` 파일을 **자동으로 로드**하여 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `GOOGLE_APPLICATION_CREDENTIALS` 등을 매번 `export` / `source` 하지 않아도 쓰게 한다.
- [x] GitHub Actions 환경에서는 `.env` 파일 없이도 동일 코드가 **분기 없이** 동작한다 (워크플로우 `env:` 블록이 제공하는 환경변수 사용).
- [x] 이미 `os.environ` 에 값이 있을 경우 `.env` 파일이 이를 **덮어쓰지 않는다** (`load_dotenv(override=False)` 기본 동작).

## 2) 비목표(Non-Goals)

- `.env` 파일 생성/관리는 사용자 책임 (예시만 문서로 안내, 값 배포는 하지 않음).
- 다른 CLI (`scripts/...`) 에는 적용하지 않는다. live 도메인 CLI 에만 한정.
- Firebase Admin SDK 가 실제로 동작하도록 자격증명을 설정하는 것은 이 plan 범위가 아니다. 단지 `.env` 에서 경로를 읽을 수 있게만 한다.
- `python-dotenv` 이외의 파일 포맷 (YAML 등) 지원은 없음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `live.cli` 는 `os.environ.get()` 만 호출하므로, 로컬에서 실행하려면 매 터미널마다 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 를 직접 `export` 해야 한다.
- 수동 테스트([docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)) 진행 중 환경변수 누락으로 `TELEGRAM_BOT_TOKEN 미설정` 상태에서 알림이 조용히 실패하는 사고가 이미 한 번 발생했다.
- GitHub Secrets 는 Actions 런타임에만 주입되므로, 로컬에서 쓰려면 별도 보관 수단이 반드시 필요하다.
- `python-dotenv` 의 `load_dotenv()` 는 파일이 없으면 no-op 이므로, 로컬과 Actions 양쪽에서 **단일 코드 경로**로 동작한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md) — 타입 힌트, Path 사용, 한글 메시지, 로깅 정책, 내부 불변조건 처리 등 공통 규칙
- [live/CLAUDE.md](../../live/CLAUDE.md) — live 도메인 원칙 (QBT 본체 수정 금지, 순수 계산 분리, 장애 시 자동 복구 금지)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, mock 기반, 외부 네트워크 호출 금지

## 4) 완료 조건(Definition of Done)

- [x] `pyproject.toml` 의 `live` extras 에 `python-dotenv` 추가
- [x] `poetry lock` 및 `poetry install -E live` 정상 수행 (`python-dotenv 1.2.2` 설치)
- [x] `live/src/live/cli.py` 의 `main()` 진입 시 `.env` 자동 로드 로직 추가 (override=False)
- [x] `.env.example` 파일 생성 (프로젝트 루트) — 필요한 변수 목록 주석 포함, 실제 값은 placeholder
- [x] `.gitignore` 의 `.env` 엔트리 기존 존재 확인 (33 번 줄)
- [x] `live/tests/test_cli.py` 에 `TestDotenvLoading` 추가 (4 개 테스트)
- [x] 기존 테스트가 새 로직의 영향을 받지 않음을 확인 (live 272 / 전체 779 passed)
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 2 번 테스트 절차를 `.env` 방식으로 갱신
- [x] [live/CLAUDE.md](../../live/CLAUDE.md) 실행 방법 섹션에 `.env` 자동 로드 안내 추가
- [x] `poetry run python validate_project.py` 통과 (passed=779, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md`: 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `pyproject.toml` — `live` extras 에 `python-dotenv = "^1.0"` 추가
- `poetry.lock` — lock 갱신 (자동 생성)
- `live/src/live/cli.py` — `main()` 최상단에서 `_load_dotenv_if_present()` 호출
- `live/tests/test_cli.py` — `.env` 로드 동작 테스트 추가
- `.env.example` (신규) — 프로젝트 루트에 예시 파일
- `.gitignore` — `.env` 엔트리 추가 (없으면)
- `docs/TEST_QBT_LIVE_MANUAL.md` — 2 번 "텔레그램 실패 알림 수신 확인" 절차 업데이트
- `live/CLAUDE.md` — 한 줄 안내 추가
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 기존 출력 스키마 변경 없음
- 기존 결과 CSV/JSON 파일 영향 없음
- Actions 워크플로우 YAML 변경 없음 (`env:` 블록은 그대로)

## 6) 단계별 계획(Phases)

### Phase 1 — 의존성 추가 및 CLI 로드 로직 구현

**작업 내용**:

- [x] `pyproject.toml` 수정: `python-dotenv` 를 live extras 에 추가
- [x] `poetry lock` 실행
- [x] `poetry install -E live` 실행 (python-dotenv 1.2.2 설치 확인)
- [x] `live/src/live/cli.py` 수정:
  - `_PROJECT_ROOT` / `_DOTENV_PATH` 모듈 상수 추가 (`Path(__file__).resolve().parents[3]`)
  - `_load_dotenv_if_present()` 함수 추가 (파일 없으면 no-op, `override=False`)
  - `dotenv.load_dotenv` 를 모듈 top-level import 로 이동 — 미설치 시 `ImportError` 전파 (사용자 요구사항: 즉시 실패하여 인지)
  - `main()` 에서 `parser = _build_parser()` 이전에 호출
- [x] 경로 계산 검증: `_PROJECT_ROOT == /home/yblee/workspace/quant` 확인 완료

---

### Phase 2 — 테스트 추가

**작업 내용**:

- [x] `live/tests/test_cli.py` 에 `TestDotenvLoading` 클래스 추가 (T-1, T-2, T-3 + `_PROJECT_ROOT` 가드 테스트)
- [x] 테스트 격리: `tmp_path` + `dotenv_path` 파라미터 직접 주입
- [x] 전체 live 테스트 그린 유지 확인 (272 passed)

---

### Phase 3 — 문서 갱신 및 보조 파일

**작업 내용**:

- [x] `.env.example` 생성 (프로젝트 루트) — TELEGRAM, GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_DB_URL 예시 포함
- [x] `.gitignore` 확인 — `.env` 엔트리가 이미 존재 (33 번 줄)
- [x] `docs/TEST_QBT_LIVE_MANUAL.md` 의 2 번 절차 업데이트 (`.env` 방식)
- [x] `live/CLAUDE.md` 실행 방법 섹션에 `.env` 자동 로드 안내 2 줄 추가

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (README.md 변경 없음)
- [x] `poetry run black .` 적용 (`cli.py`, `test_cli.py` 2 파일 포맷)
- [x] 코드 레벨 smoke test 통과 (`_load_dotenv_if_present` 임시 `.env` 로 `os.environ` 주입 확인)
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=**779**, failed=**0**, skipped=**0**)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / CLI 진입 시 프로젝트 루트 `.env` 자동 로드 (python-dotenv)
2. live / 로컬 환경변수 관리 개선: `.env` 지원 + 예시 파일 추가
3. live / `.env` 자동 로드로 수동 테스트 편의성 개선
4. live / CLI 로컬 실행 시 `.env` 자동 로드 + 테스트 커버리지 추가
5. live / python-dotenv 도입 및 수동 테스트 문서 갱신

## 7) 리스크(Risks)

- **GitHub Actions 환경에서 의도치 않게 `.env` 파일이 생성/커밋될 위험** → `.gitignore` 로 차단 + `.env.example` 만 커밋.
- **`override=False` 동작 오해** → Actions 의 `env:` 값이 `.env` 로 덮어써질 걱정은 없음. 하지만 테스트로 명시적으로 검증 (Phase 2 T-3).
- **프로젝트 루트 경로 계산 오류** → `Path(__file__).resolve().parents[3]` 가 정확한지 테스트에서 검증. 레이아웃 변경 시 취약할 수 있으므로 상수로 정의.
- **`python-dotenv` 미설치 상태에서 CLI 실행 실패** → 의도적으로 `ImportError` 를 전파하여 즉시 실패한다. graceful degradation 금지: 사용자가 상황을 즉시 인지하고 `poetry install -E live` 로 복구할 수 있어야 한다. (사용자 피드백 반영, 2026-04-11)
- **기존 `test_cli.py` 가 사용하는 환경변수 monkeypatch 와 충돌** → `.env` 로드 순서가 `parse_args()` 이전이므로 monkeypatch 가 override=False 를 이기도록 테스트에서 순서 점검.

## 8) 메모(Notes)

- `python-dotenv` 는 Flask/FastAPI/Django 등 대부분의 Python 앱에서 표준처럼 쓰이는 라이브러리. 유지보수 활발, MIT 라이선스.
- `find_dotenv()` 대신 명시적 경로를 쓰는 이유: `find_dotenv()` 는 현재 작업 디렉토리부터 위로 탐색하므로 테스트 격리가 어렵다.
- 방법 1 (direnv), 방법 2 (~/.bashrc) 대비 선택 이유: 코드 레벨 통합이므로 쉘 종류/OS 에 무관하고, Actions 와 코드 경로가 통합되며, cron / 다른 실행 경로에서도 동일 동작한다.

### 진행 로그 (KST)

- 2026-04-11 15:30: Draft 작성
- 2026-04-11 15:32: 사용자 승인 → In Progress. Phase 1 `pyproject.toml` + `cli.py` 구현.
- 2026-04-11 15:33: Phase 2 `TestDotenvLoading` 4 개 테스트 추가, live 272 passed.
- 2026-04-11 15:35: Phase 3 `.env.example`, `TEST_QBT_LIVE_MANUAL.md`, `live/CLAUDE.md` 갱신.
- 2026-04-11 15:36: 마지막 Phase — black 적용, `validate_project.py` passed=779 failed=0 skipped=0.
- 2026-04-11 15:37: 사용자 피드백 반영 — `ImportError` graceful handling 제거, `dotenv.load_dotenv` top-level import 로 이동. 실 credential 기반 `.env` + `secrets/qbt-live-adminsdk.json` 생성 (권한 600, `.gitignore` 매칭 확인). 실제 `notify-failure` smoke test 로 `.env` 자동 로드 동작 확인.
