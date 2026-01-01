# Implementation Plan: ruff + mypy 통합 코드 체크 스크립트

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

**작성일**: 2026-01-01 10:44
**마지막 업데이트**: 2026-01-01 11:06
**관련 범위**: 프로젝트 전체 (코드 품질 도구)
**관련 문서**: docs/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: ruff + mypy를 통합 실행하는 `check_code.py` 스크립트 생성
- [x] 목표 2: AI가 스크립트를 실행하고 로그를 읽어 문제를 수정할 수 있도록 명확한 출력 제공
- [x] 목표 3: 프로젝트 전체 문서에서 `poetry run ruff check .` 명령을 `python check_code.py`로 통일

## 2) 비목표(Non-Goals)

- mypy 오류를 즉시 모두 수정하는 것은 목표가 아님 (단계적 개선)
- 기존 ruff 설정 변경은 목표가 아님
- 테스트 코드의 린트/타입 체크 제외는 목표가 아님 (전체 프로젝트 체크)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재는 ruff만 단독으로 실행하고 있어 타입 체크가 누락됨
- AI가 타입 체킹을 직접 할 수 없어 사용자가 수동으로 확인해야 함
- ruff + mypy를 별도로 실행해야 하는 번거로움
- AI가 체크 스크립트를 실행하고 로그를 읽어 문제를 수정할 수 있도록 통합 필요

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `docs/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족
  - [x] `check_code.py` 스크립트가 ruff + mypy를 통합 실행
  - [x] 명확한 출력 포맷 (섹션별 구분, 오류/경고 개수 표시)
  - [x] 종료 코드 반환 (오류 있으면 1, 없으면 0)
- [x] 회귀/신규 테스트 추가 (해당 없음 - 스크립트 도구)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `python check_code.py` 통과 (새로운 체크 스크립트 자체 검증)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
  - [x] docs/CLAUDE.md
  - [x] docs/plans/_template.md
  - [x] README.md
  - [x] tests/CLAUDE.md
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 새로 생성:
  - `check_code.py` (루트)
- 수정:
  - `pyproject.toml` (mypy 의존성 및 설정 추가)
  - `docs/CLAUDE.md` (Ruff 실행 원칙 섹션)
  - `docs/plans/_template.md` (Validation 명령어)
  - `README.md` (빠른 시작, 코드 품질, 문제 해결 섹션)
  - `tests/CLAUDE.md` (품질 게이트 커맨드 섹션)

### 데이터/결과 영향

- 없음 (코드 품질 도구 추가)

## 6) 단계별 계획(Phases)

### Phase 1 — 통합 체크 스크립트 생성 및 mypy 설정

**작업 내용**:

- [x] pyproject.toml에 mypy 의존성 추가
- [x] pyproject.toml에 mypy 기본 설정 추가
- [x] poetry install 실행하여 mypy 설치
- [x] check_code.py 스크립트 작성
  - [x] ruff check 실행
  - [x] mypy 실행 (src/, scripts/, tests/ 전체)
  - [x] 각 도구별 결과를 섹션으로 구분하여 출력
  - [x] 오류/경고 개수 집계 및 표시
  - [x] 종료 코드 반환 (오류 있으면 1, 없으면 0)

**Validation**:

- [x] `python check_code.py` 실행 (Ruff 통과, Mypy 통과)
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

---

### Phase 2 — 문서 업데이트

**작업 내용**:

- [x] docs/CLAUDE.md 업데이트
  - [x] "Ruff 실행 원칙" → "코드 품질 체크 원칙"으로 변경
  - [x] `poetry run ruff check .` → `python check_code.py`로 변경
- [x] docs/plans/_template.md 업데이트
  - [x] 모든 Validation 섹션의 `poetry run ruff check .` → `python check_code.py`
- [x] README.md 업데이트
  - [x] "빠른 시작" 섹션: `poetry run ruff check .` → `python check_code.py`
  - [x] "코드 품질" 섹션: ruff/mypy 통합 체크 명령어 안내
  - [x] "문제 해결" 섹션: 린트 검사 명령어 업데이트
- [x] tests/CLAUDE.md 업데이트
  - [x] "품질 게이트 커맨드" 섹션: `poetry run ruff check .` → `python check_code.py`

**Validation**:

- [x] `python check_code.py` (Ruff 통과, Mypy 통과)
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 모든 문서 업데이트 확인
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 새로운 체크 스크립트를 사용하여 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `python check_code.py` (Ruff 통과, Mypy 통과)
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 코드품질 / ruff+mypy 통합 체크 스크립트 추가 및 문서 전면 업데이트
2. 개발도구 / 린트+타입체크 통합 자동화 (check_code.py)
3. 코드품질 / mypy 도입 + 품질 게이트 명령어 통일 (check_code.py)
4. 인프라 / ruff/mypy 통합 실행 스크립트 + 전체 문서 정비
5. 개발도구 / AI 친화적 코드 체크 스크립트 도입 (ruff+mypy)

## 7) 리스크(Risks)

- mypy 도입으로 기존 코드에서 타입 오류가 다수 발견될 수 있음
  - 완화책: 단계적으로 수정, 초기에는 기록만 하고 점진적 개선
- 새로운 스크립트 실행 시간이 기존보다 길어질 수 있음
  - 완화책: ruff와 mypy를 순차 실행하므로 큰 차이 없을 것으로 예상

## 8) 메모(Notes)

- mypy 설정은 기본(non-strict)으로 시작하여 점진적으로 강화 예정
- check_code.py는 향후 다른 도구(예: bandit, pylint)도 추가 가능하도록 확장성 고려

### 진행 로그 (KST)

- 2026-01-01 10:44: 계획서 초안 작성
- 2026-01-01 10:44-11:06: Phase 1-2 완료 및 최종 검증 완료
  - mypy 설치 및 설정 완료
  - check_code.py 스크립트 작성 완료
  - 모든 타입 오류 수정 완료 (pandas-stubs 설치, type ignore 추가)
  - 전체 문서 업데이트 완료 (docs/CLAUDE.md, _template.md, README.md, tests/CLAUDE.md)
  - 최종 검증: Ruff 통과, Mypy 통과, 테스트 182개 모두 통과
- 2026-01-01 11:06: ✅ Done

---
