# Implementation Plan: Poetry 명령어 및 Type Ignore 수정

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

**작성일**: 2026-01-02 09:38
**마지막 업데이트**: 2026-01-02 09:52
**관련 범위**: docs, tests, utils
**관련 문서**: tests/CLAUDE.md, src/qbt/utils/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python check_code.py` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: 모든 관련 문서에서 `python check_code.py`를 `poetry run python check_code.py`로 변경하여 일관성 확보
- [x] 목표 2: 테스트 코드의 모든 `# type: ignore` 주석을 근본적으로 해결하여 타입 안정성 향상

## 2) 비목표(Non-Goals)

- `docs/archive/` 폴더의 과거 문서는 수정하지 않음 (docs/CLAUDE.md 규칙에 따라 archive는 무시)
- 테스트 코드 외의 `# type: ignore`는 범위 밖
- `check_code.py` 스크립트 자체의 로직 변경은 범위 밖

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1: Poetry 명령어 일관성 부족**
- 현재 문서에 `python check_code.py`로 기재되어 있으나, 프로젝트는 Poetry로 의존성을 관리함
- 일관성을 위해 모든 Python 스크립트 실행은 `poetry run python` 형태로 통일해야 함
- 영향 받는 문서:
  - `tests/CLAUDE.md` (라인 90)
  - `README.md`
  - `docs/plans/_template.md` (라인 35, 110, 124, 138, 155)
  - `docs/CLAUDE.md` (라인 60)

**문제 2: Type Ignore 사용**
- 테스트 코드에서 5곳에 `# type: ignore` 사용 중
- 타입 안정성을 저해하고, 잠재적 타입 오류를 숨길 수 있음
- 영향 받는 파일:
  - `tests/test_tqqq_analysis_helpers.py`: 3곳 (`[arg-type]`, `[unreachable]`)
  - `tests/test_formatting.py`: 2곳 (`[comparison-overlap]`)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족
- [x] 회귀/신규 테스트 추가 (기존 테스트만 수정하므로 해당 없음)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run python check_code.py` 통과 (ruff + mypy)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 완료
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**문서 파일 (4개)**:
- `tests/CLAUDE.md`
- `README.md`
- `docs/plans/_template.md`
- `docs/CLAUDE.md`

**테스트 파일 (2개)**:
- `tests/test_tqqq_analysis_helpers.py`
- `tests/test_formatting.py`

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 기존 테스트 동작 변경 없음 (타입 체크만 개선)

## 6) 단계별 계획(Phases)

### Phase 1 — Poetry 명령어 통일

**작업 내용**:

- [x] `tests/CLAUDE.md` 라인 90: `python check_code.py` → `poetry run python check_code.py`
- [x] `README.md`: `python check_code.py` → `poetry run python check_code.py`
- [x] `docs/plans/_template.md`: 모든 `python check_code.py` → `poetry run python check_code.py` (라인 35, 110, 124, 138, 155)
- [x] `docs/CLAUDE.md` 라인 60: `python check_code.py` → `poetry run python check_code.py`

**Validation**:

- [x] `poetry run python check_code.py`
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

---

### Phase 2 — Type Ignore 근본 해결

**작업 내용**:

- [x] `tests/test_tqqq_analysis_helpers.py` 분석 및 수정
  - 라인 67, 159: `[arg-type]` 해결 (`.values` → `.to_numpy()`)
  - 라인 313: `[unreachable]` 해결 (DataFrame 접근 방식 변경)
- [x] `tests/test_formatting.py` 분석 및 수정
  - 라인 479, 480: `[comparison-overlap]` 해결 (Enum 비교 테스트를 집합 기반으로 재작성)

**Validation**:

- [x] `poetry run python check_code.py`
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 변경사항 최종 확인
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python check_code.py`
- [x] `./run_tests.sh` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서/테스트 / Poetry 명령어 통일 및 타입 안정성 개선
2. 품질개선 / Poetry run 명령어 일관성 확보 + type ignore 제거
3. 문서/테스트 / 명령어 표준화 및 타입 체크 강화
4. 리팩토링 / Poetry 명령어 통일 + 테스트 타입 안정성 향상
5. 문서/테스트 / check_code 명령어 수정 및 type ignore 해결

## 7) 리스크(Risks)

- **리스크 1**: Type ignore 제거 시 예상치 못한 타입 오류 발생 가능
  - **완화책**: 각 수정 후 즉시 `poetry run python check_code.py` 및 `./run_tests.sh` 실행하여 회귀 방지

- **리스크 2**: 문서 수정 시 누락 가능
  - **완화책**: Phase 1 완료 후 전체 검색으로 누락 확인

## 8) 메모(Notes)

### 참고 사항

- `type: ignore` 5개 위치:
  1. `tests/test_tqqq_analysis_helpers.py:67` - `[arg-type]`
  2. `tests/test_tqqq_analysis_helpers.py:159` - `[arg-type]`
  3. `tests/test_tqqq_analysis_helpers.py:313` - `[unreachable]`
  4. `tests/test_formatting.py:479` - `[comparison-overlap]`
  5. `tests/test_formatting.py:480` - `[comparison-overlap]`

### 진행 로그 (KST)

- 2026-01-02 09:38: 계획서 초안 작성 완료
- 2026-01-02 09:43: 계획서 상태를 In Progress로 변경, Phase 1 시작
- 2026-01-02 09:44: Phase 1 완료 (모든 문서에서 poetry run python check_code.py로 통일)
- 2026-01-02 09:47: Phase 2 완료 (모든 type ignore 근본 해결)
- 2026-01-02 09:52: 마지막 Phase 완료, 계획서 상태를 Done으로 변경

---
