# Implementation Plan: QBT Live - Step 1 폴더 구조 생성

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

**작성일**: 2026-04-11 12:12
**마지막 업데이트**: 2026-04-11 12:35
**관련 범위**: live (신규 도메인)
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (설계서 — 특히 1.3, 부록 A/B)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 1 체크리스트)
- [docs/PROMPT_QBT_LIVE.md](../PROMPT_QBT_LIVE.md) (구현 지시서)

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

- [x] 목표 1: `live/` 신규 도메인의 디렉토리 구조(`live/src/live/`, `live/tests/`)와 각 모듈 스켈레톤(docstring만 포함한 빈 파일) 생성
- [x] 목표 2: `pyproject.toml`에 `live` extras 그룹을 추가하여 후속 Step에서 필요한 외부 의존성 설치 진입점 마련
- [x] 목표 3: 루트 `CLAUDE.md`, 신규 `live/CLAUDE.md`, `docs/DESIGN_QBT_LIVE_FINAL.md`, `docs/TODO_QBT_LIVE.md`를 일관되게 업데이트하여 후속 Step 작업 시 맥락 전달 보장

## 2) 비목표(Non-Goals)

- 모듈 내부 로직 구현 (Step 2 이후에서 수행)
- 테스트 시나리오 작성 (각 Step에서 해당 모듈과 함께 추가)
- GitHub Actions workflow 파일 (Step 11)
- 외부 네트워크(Firebase, 텔레그램, yfinance) 실제 호출
- QBT 본체(`src/qbt/`) 코드 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- QBT Live(실매매 알림 시스템) 구현을 시작하기 위한 최초 Step
- 후속 Step들이 참조할 수 있는 모듈 스켈레톤과 의존성 진입점이 필요
- 각 Step에서 구현 대상 파일을 바로 `Edit`할 수 있도록 미리 파일을 만들어 두는 단계

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [docs/CLAUDE.md](../CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [docs/PROMPT_QBT_LIVE.md](../PROMPT_QBT_LIVE.md)

## 4) 완료 조건(Definition of Done)

- [x] `live/src/live/` 아래 12개 모듈 파일(docstring only)이 모두 생성됨
- [x] `live/src/live/__init__.py`, `live/tests/__init__.py`, `live/tests/conftest.py` 생성
- [x] `live/CLAUDE.md` 생성 (도메인 맥락, 코딩 규칙, QBT 본체 수정 원칙 포함)
- [x] `pyproject.toml`에 `[tool.poetry.extras]` 및 `live` optional 의존성 정의
- [x] 루트 `CLAUDE.md`의 디렉토리 구조 트리에 `live/` 포함 및 포인터 추가
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 및 `docs/TODO_QBT_LIVE.md` 상태/체크박스 동기화
- [x] `poetry lock` 및 `poetry install -E live` 정상 완료 확인 (사용자 승인 하에 실행)
- [x] `poetry run python validate_project.py` 통과 (passed=507, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

#### 신규 생성 (live/ 도메인)

- `live/src/live/__init__.py`
- `live/src/live/constants.py`
- `live/src/live/models.py`
- `live/src/live/state.py`
- `live/src/live/data_fetcher.py`
- `live/src/live/data_validator.py`
- `live/src/live/daily_runner.py`
- `live/src/live/drift.py`
- `live/src/live/rtdb_gateway.py`
- `live/src/live/notifier.py`
- `live/src/live/chart_data.py`
- `live/src/live/history.py`
- `live/src/live/cli.py`
- `live/tests/__init__.py`
- `live/tests/conftest.py`
- `live/CLAUDE.md`

#### 수정

- `pyproject.toml` (live extras 추가, `packages` 선언에 `live` 포함)
- `CLAUDE.md` (루트, 디렉토리 구조 및 포인터 업데이트)
- `docs/DESIGN_QBT_LIVE_FINAL.md` (필요 시 1.3 구조에 `history.py` 등 누락 모듈 반영 확인)
- `docs/TODO_QBT_LIVE.md` (Step 1 체크박스 체크)

#### README 변경 여부

- `README.md`: **변경 없음** (Step 24에서 문서화 예정)

### 데이터/결과 영향

- 없음 (로직 미구현, 스켈레톤만 생성)
- `storage/` 디렉토리 영향 없음
- `tests/` 기존 테스트 결과 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 계획서 작성 및 사전 점검 (현재 Phase)

**작업 내용**:

- [x] 루트/도메인 CLAUDE.md 및 DESIGN/TODO/PROMPT 문서 숙지
- [x] 사용자에게 질문하여 선택지 확정 (계획서 작성, minimal extras, tests 파일 범위, CLAUDE 업데이트 범위, live/CLAUDE.md 생성)
- [x] 계획서 작성

### Phase 2 — live/ 스켈레톤 생성

**작업 내용**:

- [x] `live/src/live/__init__.py` 생성
- [x] `live/src/live/` 아래 12개 모듈(docstring만 포함) 생성
- [x] `live/tests/__init__.py` 생성
- [x] `live/tests/conftest.py` 생성

### Phase 3 — 의존성/패키징 설정

**작업 내용**:

- [x] `pyproject.toml` 수정 (packages + optional deps + extras)
- [x] `pyrightconfig.json` 수정 (live/src, live/tests 포함)
- [x] `poetry lock` 실행
- [x] `poetry install -E live` 실행 (firebase-admin 7.4.0, exchange-calendars 4.13.2, requests 2.33.1 설치)

### Phase 4 — 문서 업데이트 (live/CLAUDE.md, 루트 CLAUDE.md, DESIGN, TODO)

**작업 내용**:

- [x] `live/CLAUDE.md` 신규 작성
- [x] 루트 `CLAUDE.md` 업데이트 (live 포인터 + QBT 본체 수정 원칙 + 디렉토리 트리)
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 1.3 리포지토리 구성 동기화
- [x] `docs/TODO_QBT_LIVE.md` Step 1 체크박스 체크

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(125 files left unchanged)
- [x] `poetry run python validate_project.py` 실행 및 결과 기록
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=507, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `실매매 / live 도메인 스켈레톤 및 문서 기반 마련 (Step 1)`
2. `실매매 / live 모듈 빈 파일 생성 + poetry extras 추가`
3. `실매매 / QBT Live Phase 1 Step 1 - 폴더 구조 및 의존성 진입점`
4. `실매매 / live 패키지 초기화 + CLAUDE.md 신설 + DESIGN/TODO 동기화`
5. `실매매 / live 스켈레톤 도입 (Firebase/텔레그램/exchange-calendars extras)`

## 7) 리스크(Risks)

- **Poetry lock 실패 가능성**: `firebase-admin` / `exchange-calendars` 버전 충돌 가능
  - 완화책: 실패 시 버전 제약 완화(`^` → `*`) 또는 설계서에 명시된 패키지만 유지
- **빈 파일이 `ruff`/`pyright` 경고 유발 가능**: docstring만 있는 모듈은 일반적으로 문제 없으나, `__all__` 미정의 등으로 경고 가능
  - 완화책: docstring + `pass` 대신 docstring only 유지 (Python에서는 docstring이 유효한 module-level statement)
- **`live/src/live/` 패키지 인식 실패**: `from = "live/src"` 경로가 pyproject.toml에서 인식되지 않을 수 있음
  - 완화책: `poetry lock`/`install` 단계에서 확인, 실패 시 경로 조정
- **pyright strict 모드 영향**: `pyrightconfig.json`이 `executionEnvironments`로 `live/` 경로 포함 여부 확인 필요
  - 완화책: 필요 시 `pyrightconfig.json` 업데이트

## 8) 메모(Notes)

### 주요 결정 사항

- **계획서 작성 여부**: A안 채택 (사용자 지시)
- **extras 패키지 범위**: 최소(A안) — firebase-admin, exchange-calendars, requests
- **테스트 파일 범위**: C안 — `__init__.py`와 `conftest.py`만 생성, 각 Step별 테스트 파일은 해당 Step에서 추가
- **루트 CLAUDE.md 업데이트 범위**: B안(표준) — 디렉토리 트리 + 포인터. 단, **QBT 본체(`src/qbt/`) 수정은 원칙 금지이나 사용자 승인 하에 가능**이라는 예외 조항 포함
- **live/CLAUDE.md 생성**: 사용자 지시에 따라 포함

### 진행 로그 (KST)

- 2026-04-11 12:12: 계획서 초안 작성, 사용자와 선택지 합의 완료
- 2026-04-11 12:25: live/src/live 12개 모듈 + tests 초기 구조 + live/CLAUDE.md 생성
- 2026-04-11 12:30: pyproject.toml / pyrightconfig.json / 루트 CLAUDE.md / DESIGN / TODO 업데이트
- 2026-04-11 12:33: poetry lock + install -E live 성공 (firebase-admin 7.4.0, exchange-calendars 4.13.2, requests 2.33.1)
- 2026-04-11 12:35: black + validate_project 통과 (passed=507, failed=0, skipped=0), Done

---
