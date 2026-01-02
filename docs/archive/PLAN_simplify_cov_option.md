# Implementation Plan: validate_project.py --cov 옵션 단순화

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

**작성일**: 2026-01-02 10:39
**마지막 업데이트**: 2026-01-02 10:46
**관련 범위**: 품질 검증 도구, 문서
**관련 문서**: `docs/CLAUDE.md`, `tests/CLAUDE.md`, `CLAUDE.md` (루트)

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

- [x] `--cov` 옵션을 테스트 + 커버리지만 실행하도록 변경 (Ruff, Mypy 제외)
- [x] 관련 문서를 최신 상태로 업데이트 (`tests/CLAUDE.md`, `CLAUDE.md`)
- [x] 모든 품질 검증 통과 (failed=0, skipped=0)

## 2) 비목표(Non-Goals)

- 전체 검증 + 커버리지 기능 유지 (사용자 확인 결과: 불필요)
- 새로운 옵션 추가 (예: `--all-cov`)
- 테스트 코드 작성/수정 (로직 변경이지만 테스트 대상은 CLI 도구 자체이므로 제외)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 동작**:
- `--cov` 옵션: 전체 검증(Ruff + Mypy + Pytest) + 커버리지 실행
- `--only-tests --cov`: 테스트만 + 커버리지 실행

**문제점**:
- `--cov` 옵션이 "커버리지 포함 테스트"라는 직관적인 이름과 달리 전체 검증을 실행함
- 테스트만 빠르게 실행하고 싶을 때 `--only-tests --cov` 조합을 사용해야 하는 불편함
- 사용자가 원하는 것은 `--cov` 단독으로 테스트 + 커버리지만 실행하는 것

**변경 후 동작**:
- `--cov`: 테스트 + 커버리지만 실행 (Ruff, Mypy 제외)
- 전체 검증(Ruff + Mypy + Pytest): 옵션 없이 실행
- 전체 검증 + 커버리지: 제거 (사용자 확인 결과 불필요)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `docs/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `validate_project.py` 수정 완료 (`--cov` 옵션이 테스트+커버리지만 실행)
- [x] 관련 문서 업데이트 완료 (`tests/CLAUDE.md`, `CLAUDE.md`)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `validate_project.py`: `--cov` 옵션 로직 변경
- `tests/CLAUDE.md`: `--cov` 옵션 사용법 업데이트
- `CLAUDE.md` (루트): 품질 검증 섹션 업데이트 (필요 시)

### 데이터/결과 영향

- 없음 (CLI 도구 옵션 변경만 해당)

## 6) 단계별 계획(Phases)

### Phase 1 — validate_project.py 수정 및 검증

**작업 내용**:

- [x] `validate_project.py` 수정:
  - [x] `--cov` 옵션 검증 로직 제거 (line 226-228: `--cov`와 `--only-lint/mypy` 조합 금지)
  - [x] `--cov` 옵션이 있을 때 `run_tests=True`, `run_lint=False`, `run_type_check=False`로 설정 (line 231-233 수정)
  - [x] docstring, help 메시지, epilog 업데이트
- [x] 수정 후 동작 확인:
  - [x] `poetry run python validate_project.py --cov` 실행 → 테스트+커버리지만 실행 확인
  - [x] `poetry run python validate_project.py` 실행 → 전체 검증(Ruff+Mypy+Pytest) 실행 확인
  - [x] `poetry run python validate_project.py --only-tests` 실행 → 테스트만 실행 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### Phase 2 — 문서 업데이트 및 최종 검증

**작업 내용**:

- [x] `tests/CLAUDE.md` 업데이트:
  - [x] line 59-60: `--cov` 설명 변경 ("전체 검증 + 커버리지" → "테스트 + 커버리지")
  - [x] line 98-99: `--cov` 설명 변경
  - [x] line 356: `--cov` 설명 변경
- [x] `CLAUDE.md` (루트) 확인 및 필요 시 업데이트
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 개발도구 / --cov 옵션 단순화 (테스트+커버리지만 실행)
2. 개발도구 / 품질 검증 도구 사용성 개선 (--cov 옵션 직관화)
3. 개발도구 / validate_project.py --cov 옵션 동작 변경 및 문서 업데이트
4. 개발도구 / 통합 검증 스크립트 옵션 단순화 (--cov)
5. 개발도구 / 커버리지 옵션 직관성 개선 및 문서 정리

## 7) 리스크(Risks)

- **기존 사용 패턴 변경**: 기존에 `--cov`로 전체 검증+커버리지를 실행하던 사용자가 있다면 혼란 가능
  - 완화: 문서를 명확히 업데이트하여 변경 사항 안내
  - 완화: 현재 프로젝트는 개인 프로젝트이고 사용자가 직접 요청한 변경이므로 리스크 낮음

## 8) 메모(Notes)

### 주요 결정 사항

- 사용자 확인 결과: 전체 검증 + 커버리지 기능은 불필요
- `--cov` 옵션을 `--only-tests --cov`와 동일하게 동작하도록 변경
- 새로운 옵션 추가 없이 기존 옵션 단순화

### 진행 로그 (KST)

- 2026-01-02 10:39: 계획서 작성 완료
- 2026-01-02 10:42: Phase 1 시작 (validate_project.py 수정)
- 2026-01-02 10:43: Phase 1 완료, Phase 2 시작 (문서 업데이트)
- 2026-01-02 10:46: Phase 2 완료, 전체 작업 완료

---
