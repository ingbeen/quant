# Implementation Plan: utils 패키지 테스트 커버리지 개선 및 병렬 처리 안정성 보완

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done
**작성일**: 2025-12-26 21:00
**마지막 업데이트**: 2025-12-26 21:25
**관련 범위**: utils, tests
**관련 문서**: src/qbt/utils/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다. 스킵이 남아있으면 **Done 처리/DoD 체크 금지**.

---

## 1) 목표(Goal)

- [x] 목표 1: `src/qbt/utils/formatting.py` 커버리지를 의미 있게 향상 (27% → 100%)
- [x] 목표 2: `src/qbt/utils/cli_helpers.py` 커버리지를 의미 있게 향상 (0% → 91%)
- [x] 목표 3: `src/qbt/utils/logger.py` 커버리지를 의미 있게 향상 (79% → 94%)
- [x] 목표 4: `ProcessPoolExecutor` 사용 시 발생하는 `multi-threaded + fork` DeprecationWarning 리스크 완화

## 2) 비목표(Non-Goals)

- CLI 스크립트를 서브프로세스로 실행하는 통합 테스트 작성 (단위 테스트만 작성)
- 100% 커버리지 달성 (의미 있는 회귀 방지 테스트에 집중)
- 병렬 처리 로직의 대규모 리팩토링 (최소 변경으로 안정성 개선)
- 기존 기능/성능 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **테스트 커버리지 취약 구간**:
  - `cli_helpers.py`: 0% - CLI 예외 처리 데코레이터의 계약이 고정되지 않음
  - `formatting.py`: 27% - 터미널 출력 포맷팅 계약이 검증되지 않음
  - `logger.py`: 79% - 로거 설정 핵심 계약의 일부가 미검증
- **병렬 처리 경고**:
  - `ProcessPoolExecutor` 사용 시 `DeprecationWarning: This process is multi-threaded, use of fork() may lead to deadlocks in the child.` 발생
  - WSL 환경에서 fork 방식의 프로세스 생성이 멀티스레드 환경과 충돌할 수 있음
- **회귀 방지 필요성**:
  - 출력 포맷 변경, 예외 처리 로직 변경 시 회귀 발견이 어려움
  - 테스트 부재로 리팩토링 위험도 높음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.
> (규칙을 요약/나열하지 말고 "문서 목록"만 둡니다.)

- [x] `CLAUDE.md` (루트)
- [x] `src/qbt/utils/CLAUDE.md`
- [x] `tests/CLAUDE.md`
- [x] `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] formatting.py, cli_helpers.py, logger.py에 대한 회귀 방지 테스트 추가
- [x] 새 테스트 파일: `tests/test_formatting.py`, `tests/test_cli_helpers.py`, `tests/test_logger.py` 생성
- [x] `ProcessPoolExecutor`에서 `spawn` 컨텍스트 사용하도록 개선
- [x] 기존 테스트 58개 모두 통과 유지 (최종 99개 통과)
- [x] `./run_tests.sh` 통과 (99 passed, 0 failed, 0 skipped)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (32 files unchanged)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 신규: `tests/test_formatting.py` (formatting.py 테스트)
- 신규: `tests/test_cli_helpers.py` (cli_helpers.py 테스트)
- 신규: `tests/test_logger.py` (logger.py 테스트)
- 수정: `src/qbt/utils/parallel_executor.py` (spawn 컨텍스트 적용)
- 수정: `tests/CLAUDE.md` (이 plan 완료 후)

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 기존 결과 비교 불필요
- 기존 기능/성능 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — formatting.py 테스트 추가 (그린 유지)

**작업 내용**:

- [x] `tests/test_formatting.py` 생성
- [x] `get_display_width()` 테스트: 한글/영문/혼용 폭 계산 검증
- [x] `format_cell()` 테스트: LEFT/RIGHT/CENTER 정렬, 폭 부족 케이스 검증
- [x] `format_row()` 테스트: 다중 셀 포맷팅, 들여쓰기 검증
- [x] `TableLogger` 테스트: 헤더/행/푸터 출력, 컬럼 수 불일치 예외 검증
- [x] `Align` enum 테스트: enum 값 접근 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`

---

### Phase 2 — cli_helpers.py 테스트 추가 (그린 유지)

**작업 내용**:

- [x] `tests/test_cli_helpers.py` 생성
- [x] `cli_exception_handler` 데코레이터 테스트: 정상 실행 시 종료 코드 0 반환 검증
- [x] 예외 처리 테스트: FileNotFoundError, ValueError, Exception 발생 시 종료 코드 1 반환 검증
- [x] 로거 자동 감지 테스트: 모듈 logger 변수 사용 검증
- [x] 폴백 로거 테스트: logger 부재 시 기본 로거 사용 검증
- [x] exc_info=True 검증: 스택 트레이스 로깅 확인

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`

---

### Phase 3 — logger.py 테스트 추가 (그린 유지)

**작업 내용**:

- [x] `tests/test_logger.py` 생성
- [x] `setup_logger()` 테스트: 로거 생성, 레벨 설정, 핸들러 설정 검증
- [x] 핸들러 중복 방지 테스트: 동일 이름으로 재호출 시 핸들러 추가 안 됨 검증
- [x] `ClickableFormatter` 테스트: 상대 경로 포맷 검증 (프로젝트 루트 기준)
- [x] `get_logger()` 테스트: 기존 로거 반환, 없으면 생성 검증
- [x] `set_log_level()` 테스트: 런타임 레벨 변경 검증
- [x] `_find_project_root()` 테스트: pyproject.toml/.git 탐색 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`

---

### Phase 4 — parallel_executor.py 병렬 처리 안정성 개선 (그린 유지)

**작업 내용**:

- [x] `parallel_executor.py`에서 `ProcessPoolExecutor` 생성 시 `multiprocessing.get_context("spawn")` 사용
- [x] `execute_parallel()` 함수 수정: spawn 컨텍스트 적용
- [x] `execute_parallel_with_kwargs()` 함수 수정: spawn 컨텍스트 적용 (동일 컨텍스트 재사용)
- [x] 변경 이유를 코드 주석으로 추가 (초보자 친화적 설명)
- [x] 기존 API 시그니처 유지 확인
- [x] 기존 병렬 처리 테스트 통과 확인

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`
- [x] 병렬 처리 사용 스크립트 실행하여 DeprecationWarning 사라졌는지 확인 (완료)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 최종 커버리지 확인 (`./run_tests.sh cov`)
- [x] 최종 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`

#### Commit Messages (Final)

1. 유틸리티 / formatting.py 테스트 추가 (커버리지 개선)
2. 유틸리티 / cli_helpers.py 테스트 추가 (커버리지 개선)
3. 유틸리티 / logger.py 테스트 추가 (커버리지 개선)
4. 유틸리티 / parallel_executor spawn 컨텍스트 적용 (안정성 개선)
5. 문서 / tests/CLAUDE.md 업데이트 (새 테스트 파일 추가)

## 7) 리스크(Risks)

- **병렬 처리 변경 리스크**: spawn 컨텍스트로 변경 시 기존 동작이 깨질 수 있음
  - 완화책: 기존 테스트 모두 통과 확인, 실제 스크립트 실행 테스트
- **테스트 작성 복잡도**: logger/cli_helpers는 모킹/패칭이 필요할 수 있음
  - 완화책: conftest.py 픽스처 활용, tests/CLAUDE.md 참고
- **커버리지 목표 미달성**: 27%→100%는 어려울 수 있음
  - 완화책: 회귀 방지 가치가 높은 핵심 계약만 집중, 100% 목표 아님

## 8) 메모(Notes)

- 참고: 현재 전체 테스트 58개 모두 통과, 총 커버리지 80%
- 참고: DeprecationWarning 위치는 병렬 실행 구간 (ProcessPoolExecutor)
- 결정: 테스트는 Given-When-Then 패턴 엄수, 부동소수점 비교는 pytest.approx 사용

### 진행 로그 (KST)

- 2025-12-26 21:00: Plan 작성 완료 (Draft 상태)
- 2025-12-26 21:05: Phase 1 시작
- 2025-12-26 21:10: Phase 1 완료 (test_formatting.py 추가, 테스트 21개 추가, 79 passed)
- 2025-12-26 21:15: Phase 2 완료 (test_cli_helpers.py 추가, 테스트 7개 추가, 86 passed)
- 2025-12-26 21:20: Phase 3 완료 (test_logger.py 추가, 테스트 13개 추가, 99 passed)
- 2025-12-26 21:22: Phase 4 완료 (parallel_executor spawn 컨텍스트 적용, DeprecationWarning 제거)
- 2025-12-26 21:25: 최종 검증 완료, Done 처리

**최종 결과**:
- 테스트: 58 → 99개 (41개 추가)
- formatting.py: 27% → 100% 커버리지
- cli_helpers.py: 0% → 91% 커버리지
- logger.py: 79% → 94% 커버리지
- parallel_executor.py: DeprecationWarning 제거 완료
