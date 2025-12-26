# Implementation Plan: TQQQ 전용 상수를 도메인 constants로 이동

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done
**작성일**: 2025-12-26 10:30
**마지막 업데이트**: 2025-12-26 10:50
**관련 범위**: tqqq, common_constants
**관련 문서**: src/qbt/tqqq/CLAUDE.md, CLAUDE.md (루트)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] `common_constants.py`에 있는 TQQQ 도메인 전용 상수를 `tqqq/constants.py`로 이동
- [x] 모든 임포트를 새 위치로 변경하여 정상 동작 확인
- [x] 상수 관리 원칙(도메인 전용 상수는 도메인 내 위치) 준수

## 2) 비목표(Non-Goals)

- 상수 값 자체의 변경이나 검증
- TQQQ 도메인 로직의 수정
- 다른 도메인(backtest 등)의 상수 이동

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `common_constants.py`에 TQQQ 도메인 전용 상수가 5개 정의되어 있음:
  - `TQQQ_DATA_PATH`: 실제 TQQQ 데이터 경로
  - `TQQQ_SYNTHETIC_PATH`: 합성 TQQQ 데이터 경로
  - `FFR_DATA_PATH`: 연방기금금리 데이터 경로
  - `TQQQ_VALIDATION_PATH`: TQQQ 검증 결과 경로
  - `TQQQ_DAILY_COMPARISON_PATH`: TQQQ 일별 비교 결과 경로

- 이 상수들은 TQQQ 도메인(`scripts/tqqq/`, `src/qbt/tqqq/`)에서만 사용되며, 백테스트나 다른 도메인에서는 사용되지 않음

- 프로젝트 가이드라인 "상수 관리 원칙"에 따르면:
  - 공통 상수는 `common_constants.py`
  - 도메인 전용 상수는 각 도메인의 `constants.py`에 위치

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.
> (규칙을 요약/나열하지 말고 "문서 목록"만 둡니다.)

- [x] `CLAUDE.md` (루트)
- [x] `src/qbt/tqqq/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 5개 상수를 `tqqq/constants.py`로 이동 완료
- [x] `common_constants.py`에서 해당 상수 제거 완료
- [x] 모든 임포트 경로 업데이트 완료 (scripts/tqqq/ 4개 파일 모두 이미 `tqqq.constants` 사용 중)
- [x] `tqqq/constants.py`의 `__all__` 업데이트 완료
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=111, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] `tqqq/CLAUDE.md` 확인 완료 (상수 설명이 이미 정확히 반영되어 있음)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py`: 5개 상수 제거
- `src/qbt/tqqq/constants.py`: 5개 상수 추가, `__all__` 업데이트
- `scripts/tqqq/generate_synthetic_tqqq.py`: 임포트 변경
- `scripts/tqqq/generate_tqqq_daily_comparison.py`: 임포트 변경
- `scripts/tqqq/validate_tqqq_simulation.py`: 임포트 변경
- `scripts/tqqq/streamlit_app.py`: 임포트 변경

### 데이터/결과 영향

- 없음 (경로 상수 값 변경 없음, 위치만 이동)
- 기존 테스트 및 스크립트 정상 동작 유지

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 이동 및 임포트 업데이트

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 5개 경로 상수 추가
  - `TQQQ_DATA_PATH`
  - `TQQQ_SYNTHETIC_PATH`
  - `FFR_DATA_PATH`
  - `TQQQ_VALIDATION_PATH`
  - `TQQQ_DAILY_COMPARISON_PATH`
- [x] `src/qbt/tqqq/constants.py`의 `__all__`에 5개 상수 추가
- [x] `src/qbt/common_constants.py`에서 5개 상수 및 주석 제거
- [x] `scripts/tqqq/generate_synthetic_tqqq.py`: 이미 `tqqq.constants`에서 임포트 중 (변경 불필요)
- [x] `scripts/tqqq/generate_tqqq_daily_comparison.py`: 이미 `tqqq.constants`에서 임포트 중 (변경 불필요)
- [x] `scripts/tqqq/validate_tqqq_simulation.py`: 이미 `tqqq.constants`에서 임포트 중 (변경 불필요)
- [x] `scripts/tqqq/streamlit_app.py`: 이미 `tqqq.constants`에서 임포트 중 (변경 불필요)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### Phase 2 — 최종 검증 및 문서 확인

**작업 내용**:

- [x] `tqqq/CLAUDE.md` 문서 확인 (상수 설명이 이미 정확히 반영되어 있는지 확인)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 최종 테스트 실행

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 상수관리 / TQQQ 전용 상수를 도메인 constants로 이동 (계층 원칙 준수)
2. 리팩토링 / TQQQ 경로 상수를 tqqq/constants.py로 재배치 (명확성 개선)
3. 구조개선 / 도메인 전용 상수를 공통에서 도메인으로 이동 (설계 원칙 준수)
4. TQQQ시뮬레이션 / 상수 위치를 common에서 domain으로 이동 (관심사 분리)
5. 리팩토링 / 상수 관리 원칙 적용 (TQQQ 상수를 도메인으로 이동)

## 7) 리스크(Risks)

- 낮음: 임포트 경로만 변경, 값 변경 없음
- 테스트 커버리지가 충분하여 회귀 발생 시 즉시 감지 가능
- 변경 범위가 명확하고 제한적 (TQQQ 도메인만)

## 8) 메모(Notes)

- `tqqq/constants.py`는 이미 `common_constants`에서 `STOCK_DIR`, `RESULTS_DIR`, `ETC_DIR`를 임포트하여 재사용하고 있음
- 이동할 상수들은 이러한 기본 디렉토리 상수를 사용하여 정의됨
- `tqqq/CLAUDE.md`의 40-44줄에 이미 이 상수들이 문서화되어 있으므로, 실제로는 코드만 이동하면 됨

### 진행 로그 (KST)

- 2025-12-26 10:30: 계획서 초안 작성 완료
- 2025-12-26 10:35: Phase 1 완료 - 상수 이동 및 검증 통과 (모든 스크립트 파일이 이미 `tqqq.constants`에서 임포트 중이어서 임포트 변경 불필요)
- 2025-12-26 10:50: Phase 2 완료 - 최종 검증 및 Black 포맷팅 완료, 모든 테스트 통과 (passed=111, failed=0, skipped=0)

---
