# Implementation Plan: Pyright 타입 체커 단일화 및 src 엄격 모드 적용

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

**작성일**: 2026-01-02 19:38
**마지막 업데이트**: 2026-01-02 19:50
**관련 범위**: 프로젝트 전체 (설정, 문서, 품질 검증 스크립트)
**관련 문서**:
- CLAUDE.md (루트)
- docs/CLAUDE.md
- tests/CLAUDE.md
- scripts/CLAUDE.md
- src/qbt/utils/CLAUDE.md
- src/qbt/backtest/CLAUDE.md
- src/qbt/tqqq/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] mypy를 프로젝트에서 완전히 제거하여 타입 체커를 Pyright 하나로 단일화
- [x] Pyright 설정을 pyrightconfig.json에 통합하고 src만 strict 모드 적용
- [x] validate_project.py를 Ruff + Pyright + Pytest 기준으로 정리
- [x] 문서 전반에서 mypy 언급 제거 및 Pyright-only 운영 기준 반영

## 2) 비목표(Non-Goals)

- 타입 힌트 자체를 수정하거나 보완하는 작업은 이번 plan의 범위 밖
- TypedDict/dataclass 중심 리팩토링은 별도 plan으로 진행
- archive 폴더 내 과거 문서는 수정하지 않음 (과거 기록 유지)
- .claude/settings.local.json 등 로컬 설정 파일은 변경하지 않음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 프로젝트는 mypy와 Pyright를 동시 사용 중
- 두 타입 체커 간 설정/기준 불일치로 운영 복잡도 증가
- 1인 개발 + AI 위임 비중이 높아 명시적 타입(=스펙) 중심 운영이 효율적
- Pyright를 단일 타입 체커로 통일하고 src만 strict 적용으로 운영 단순화 필요

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `docs/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] mypy 관련 코드/설정/문서 언급이 레포에서 완전히 제거됨 (검색으로 재확인)
- [x] Pyright 설정이 pyrightconfig.json로 통일되고 src만 strict로 동작
- [x] validate_project.py가 mypy 없이 정상 동작 (Ruff + Pyright + Pytest)
- [x] docs/CLAUDE.md, docs/plans/_template.md가 최신 기준으로 업데이트됨
- [x] docs/archive는 변경되지 않음
- [x] .mypy_cache/ 제거 및 .gitignore에 추가 완료
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=182, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `pyproject.toml` (mypy 제거, Pyright 설정 추가)
- `validate_project.py` (mypy 로직 제거, Ruff + Pyright + Pytest만)
- `.gitignore` (.mypy_cache/ 추가)
- `CLAUDE.md` (루트 - 품질 검증 섹션 업데이트)
- `docs/CLAUDE.md` (품질 검증 도구/절차 갱신)
- `docs/plans/_template.md` (예시 커맨드 갱신)
- `tests/CLAUDE.md` (품질 게이트 커맨드 갱신)
- `scripts/CLAUDE.md` (필요시)
- `.mypy_cache/` 디렉토리 (삭제)

### 데이터/결과 영향

- 데이터/결과 파일에는 영향 없음 (설정/문서/도구만 변경)
- 타입 체킹 기준 변경으로 일부 타입 오류가 새로 발견될 수 있음 (즉시 수정)

## 6) 단계별 계획(Phases)

### Phase 1 — mypy 제거 및 Pyright 설정 추가

**작업 내용**:

- [x] pyproject.toml에서 mypy dev dependency 제거
- [x] pyproject.toml에서 [tool.mypy] 섹션 및 관련 설정 전부 제거
- [x] pyrightconfig.json 생성 (pyproject.toml에서 Pyright executionEnvironments 미지원)
  - pythonVersion = "3.12"
  - include = ["src", "tests", "scripts"]
  - exclude = ["storage", "**/__pycache__", "**/.ruff_cache"]
  - extraPaths = ["src"]
  - reportMissingTypeStubs = "none"
  - executionEnvironments 설정 (src = strict, tests/scripts = basic)
- [x] .gitignore에 .mypy_cache/ 추가
- [x] .mypy_cache/ 디렉토리 제거

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### Phase 2 — validate_project.py에서 mypy 로직 제거

**작업 내용**:

- [x] validate_project.py에서 mypy 관련 모든 코드 제거
  - run_mypy() 함수 제거
  - --only-mypy 옵션 제거
  - mypy 실행 로직 및 출력 파싱 제거
  - 결과 요약에서 mypy 언급 제거
- [x] 전체 플로우를 Ruff → Pyright → Pytest 기준으로 정리
- [x] docstring 및 help 메시지 업데이트 (mypy 제거)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### Phase 3 — 문서 업데이트 (지정 파일만)

**작업 내용**:

- [x] CLAUDE.md (루트) 업데이트
  - 품질 검증 섹션에서 mypy 언급 제거
  - 예시 커맨드를 Pyright-only로 교체
  - "Ruff + Pypy + PyRight + Pytest" → "Ruff + PyRight + Pytest"
- [x] docs/CLAUDE.md 업데이트
  - 품질 검증 도구/절차를 Ruff + Pyright + Pytest 기준으로 갱신
  - 예시 커맨드에서 mypy 제거
  - "src만 strict" 운영 스코프 반영
- [x] docs/plans/_template.md 확인 (mypy 언급 없음, 수정 불필요)
- [x] tests/CLAUDE.md 업데이트
  - 품질 게이트 커맨드에서 mypy 제거
  - 통합 검증 스크립트 설명 갱신
- [x] scripts/CLAUDE.md 확인 (mypy 언급 없음, 수정 불필요)
- [x] docs/archive/** 는 변경하지 않음 (과거 기록 유지)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### Phase 4 — 전체 검증 및 타입 오류 수정

**작업 내용**:

- [x] poetry run python validate_project.py 실행
- [x] Pyright strict 모드에서 타입 오류 없음 확인 (새로운 오류 발견되지 않음)
- [x] 모든 품질 검증 통과 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] 레포 전체에서 "mypy" 키워드 검색하여 누락된 언급 제거 (계획서 제외)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 개발도구 / Pyright 타입 체커 단일화 및 src 엄격 모드 적용
2. 개발도구 / mypy 제거 및 Pyright-only 운영 체계 확립
3. 개발도구 / 타입 체킹 SoT를 Pyright로 통일 (src=strict)
4. 개발도구 / mypy 완전 제거 + Pyright 설정 통합 및 문서 갱신
5. 개발도구 / 타입 체커 단일화로 운영 복잡도 감소 (Pyright-only)

## 7) 리스크(Risks)

- Pyright strict 모드에서 기존에 발견되지 않은 타입 오류 발견 가능 → Phase 4에서 즉시 수정
- 문서 업데이트 시 누락 가능 → 마지막 Phase에서 "mypy" 키워드 전체 검색으로 재확인
- archive 폴더 수정 금지 규칙 준수 필요 → 명시적으로 제외

## 8) 메모(Notes)

- Pyright executionEnvironments 설정으로 src만 strict, tests/scripts는 basic 적용
- reportMissingTypeStubs = "none"으로 서드파티 타입 스텁 부족 경고 완화
- validate_project.py는 Ruff → Pyright → Pytest 순서로 실행
- 로컬 설정 파일(.claude/settings.local.json 등)은 변경하지 않음

### 진행 로그 (KST)

- 2026-01-02 19:38: 계획서 초안 작성 완료
- 2026-01-02 19:40: Phase 1-2 완료 (mypy 제거, Pyright 설정, validate_project.py 수정)
- 2026-01-02 19:45: Phase 3 완료 (문서 업데이트)
- 2026-01-02 19:48: Phase 4 완료 (타입 오류 없음 확인)
- 2026-01-02 19:50: 마지막 Phase 완료 (전체 검증 통과, 계획서 업데이트)

---
