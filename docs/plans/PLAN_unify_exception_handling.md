# Implementation Plan: 병렬 처리 예외 정책 통일 및 구조 정리

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done
**작성일**: 2025-12-26 21:05
**마지막 업데이트**: 2025-12-26 21:15
**관련 범위**: backtest, tqqq, utils, docs
**관련 문서**: src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, src/qbt/utils/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- 각 Phase를 시작/종료할 때 **이전 Phase의 체크리스트(작업/Validation)와 DoD 체크리스트 상태를 먼저 최신화**한 뒤 진행한다. (미반영 상태로 다음 Phase 진행 금지)
- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: backtest 도메인의 구현 원칙을 루트 CLAUDE.md로 이동하여 전체 프로젝트의 공통 원칙으로 통합
- [x] 목표 2: backtest의 `_init_grid_search_worker`를 공통 모듈로 이동하여 tqqq와 재사용 가능하게 함
- [x] 목표 3: backtest 그리드서치 워커의 예외 처리 정책을 tqqq와 동일하게 통일 (예외 발생 시 즉시 전파, 스크립트 실패 종료)

## 2) 비목표(Non-Goals)

- 백테스트 또는 시뮬레이션 핵심 로직 변경 (수익률, 비용, 체결 규칙 등)
- storage/* CSV 스키마 변경
- 새로운 기능 추가
- 성능 최적화 (단, 예외 전파로 인한 디버깅 개선은 부수 효과)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **구현 원칙의 중복**: `src/qbt/backtest/CLAUDE.md`에 있는 "구현 원칙(데이터 불변성/명시적 검증/상태 비저장/병렬 처리 지원)" 섹션이 프로젝트 전반에 적용되어야 하나, 백테스트 도메인에만 있어 다른 도메인(tqqq 등)에서 참조 불가.

2. **워커 초기화 함수 중복**:
   - backtest: `_init_grid_search_worker` (strategy.py)
   - tqqq: `_init_cost_model_worker` (simulation.py)
   - 동일한 패턴(WORKER_CACHE 초기화)을 각 도메인에서 별도로 구현

3. **예외 처리 정책 불일치 (중요)**:
   - **backtest**: `_run_buffer_strategy_for_grid`가 `try/except`로 예외를 잡아 `None` 반환 → 에러가 숨겨지고 스크립트가 계속 진행됨
   - **tqqq**: `_evaluate_cost_model_candidate`는 예외를 처리하지 않고 그대로 전파 → 병렬 처리 중 예외 발생 시 즉시 스크립트 실패 종료
   - 일관성 부족으로 디버깅 어려움, 숨겨진 에러로 인한 잘못된 결과 가능성

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.
> (규칙을 요약/나열하지 말고 "문서 목록"만 둡니다.)

- [x] `CLAUDE.md` (루트)
- [x] `src/qbt/backtest/CLAUDE.md` (백테스트 도메인)
- [x] `src/qbt/tqqq/CLAUDE.md` (TQQQ 시뮬레이션 도메인)
- [x] `src/qbt/utils/CLAUDE.md` (유틸리티 패키지)
- [x] `docs/CLAUDE.md` (계획서 작성 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족 (3가지 목표 달성)
- [x] 회귀 테스트 통과 (기존 테스트가 모두 통과하여 동작 불변성 보장)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=111, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md 변경 사항 반영)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `CLAUDE.md` (루트): 구현 원칙 섹션 추가
- `src/qbt/backtest/CLAUDE.md`: 구현 원칙 섹션 제거, 루트 참조로 대체
- `src/qbt/backtest/strategy.py`:
  - `_init_grid_search_worker` 제거
  - `_run_buffer_strategy_for_grid`의 try/except 제거 또는 예외 전파로 변경
  - `run_grid_search`에서 None 필터링 로직 제거
- `src/qbt/tqqq/simulation.py`:
  - `_init_cost_model_worker` 제거
  - 새 공통 initializer 사용
- `src/qbt/utils/parallel_executor.py` (또는 새 파일):
  - 공통 워커 초기화 함수 추가 (`init_worker_cache`)

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 기존 결과와 동일 (단, 예외 발생 시 즉시 실패로 종료되므로 잘못된 결과 방지)

## 6) 단계별 계획(Phases)

### Phase 1 — 구현 원칙 문서 이동

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`에서 "구현 원칙" 섹션(데이터 불변성/명시적 검증/상태 비저장/병렬 처리 지원) 내용 복사
- [x] 루트 `CLAUDE.md`의 "아키텍처 원칙" 하단에 "구현 원칙" 섹션 추가
- [x] `src/qbt/backtest/CLAUDE.md`에서 해당 섹션 제거 및 루트 참조로 대체

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### Phase 2 — 공통 워커 초기화 함수 생성

**Checklist Sync (이전 Phase 최신화)**:

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] 스킵 존재 여부 확인(스킵이 있으면 사유/해제 조건/후속 plan 기록)

**작업 내용**:

- [x] `src/qbt/utils/parallel_executor.py`에 `init_worker_cache(cache_payload: dict) -> None` 함수 추가
  - WORKER_CACHE 초기화 로직 구현
  - pickle 가능하도록 모듈 최상위 레벨에 정의
  - Docstring 작성 (용도, Args, 사용 예시)
- [x] `src/qbt/backtest/strategy.py`에서 `_init_grid_search_worker` 제거
- [x] `src/qbt/backtest/strategy.py`의 `run_grid_search`에서 새 공통 initializer 사용
- [x] `src/qbt/tqqq/simulation.py`에서 `_init_cost_model_worker` 제거
- [x] `src/qbt/tqqq/simulation.py`의 `find_optimal_cost_model`에서 새 공통 initializer 사용

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### Phase 3 — 예외 처리 정책 통일

**Checklist Sync (이전 Phase 최신화)**:

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] 스킵 존재 여부 확인(스킵이 있으면 사유/해제 조건/후속 plan 기록)

**작업 내용**:

- [x] `src/qbt/backtest/strategy.py`의 `_run_buffer_strategy_for_grid` 함수 수정:
  - try/except 블록 제거 (또는 최소한 `raise`로 예외 전파)
  - 반환 타입 `dict | None` → `dict`로 변경
  - Docstring 업데이트 ("예외 발생 시 None 반환" → "예외 발생 시 즉시 전파")
- [x] `run_grid_search` 함수 수정:
  - `results = [r for r in results if r is not None]` 필터링 로직 제거
  - 병렬 실행 결과를 그대로 사용
- [x] 루트 `CLAUDE.md`의 "병렬 처리" 섹션에 예외 처리 정책 명시:
  - "병렬 워커에서 예외 발생 시 즉시 전파하여 스크립트 실패 종료"
  - "예외를 숨기고 None 반환하는 패턴 금지"

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**Checklist Sync (이전 Phase 최신화)**:

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] 스킵 존재 여부 확인(스킵이 있으면 사유/해제 조건/후속 plan 기록)

**작업 내용 (⚠️ 마지막 Phase이므로 DoD 및 전체 체크리스트 최종 반영 포함)**

- [x] `src/qbt/utils/CLAUDE.md` 업데이트 (필요 없음 - 공통 워커 초기화 함수는 이미 문서화된 패턴)
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (구현 원칙 제거 및 루트 참조 명시 완료)
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트 (필요 없음 - 기존 패턴 유지)
- [x] `poetry run black .` 실행 (자동 포맷 적용, 35 files left unchanged)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (passed=111, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 리팩토링 / 병렬 처리 예외 정책 통일 및 워커 초기화 공통화 (디버깅 개선)
2. 리팩토링 / 구현 원칙 문서 통합 및 예외 전파 정책 통일
3. 리팩토링 / 그리드서치 구조 정리 (공통 initializer, 예외 즉시 전파)
4. 리팩토링 / backtest/tqqq 병렬 처리 정합성 개선 (예외 숨김 제거)
5. 문서 / 구현 원칙 통합 + 병렬 처리 예외 정책 통일

## 7) 리스크(Risks)

- **리스크 1**: 예외 전파 정책 변경으로 기존에 숨겨지던 에러가 드러날 수 있음
  - **완화책**: 모든 테스트 통과 확인, 에러 발생 시 즉시 수정
- **리스크 2**: 공통 워커 초기화 함수 이동 중 임포트 순환 참조 가능성
  - **완화책**: parallel_executor.py는 이미 공통 유틸리티이므로 순환 참조 위험 낮음, 테스트로 검증
- **리스크 3**: 문서 이동 중 링크 깨짐 가능성
  - **완화책**: 각 Phase에서 문서 업데이트 후 즉시 검증

## 8) 메모(Notes)

- 이 작업은 동작 변경이 아닌 구조 정리 및 정책 통일이므로, 모든 기존 테스트가 통과해야 함
- 예외 전파 정책 통일은 디버깅 개선 효과가 큼 (에러가 숨겨지지 않고 즉시 드러남)
- tqqq의 `_evaluate_cost_model_candidate`는 이미 예외를 전파하므로 변경 불필요

### 진행 로그 (KST)

- 2025-12-26 21:05: 계획서 작성 완료 (Draft)
- 2025-12-26 21:06: Phase 1 완료 - 구현 원칙 문서 이동 (루트 CLAUDE.md에 통합)
- 2025-12-26 21:09: Phase 2 완료 - 공통 워커 초기화 함수 생성 (utils/parallel_executor.py에 init_worker_cache 추가)
- 2025-12-26 21:12: Phase 3 완료 - 예외 처리 정책 통일 (try/except 제거, 예외 즉시 전파)
- 2025-12-26 21:15: 마지막 Phase 완료 - 최종 검증 통과 (passed=111, failed=0, skipped=0)

---
