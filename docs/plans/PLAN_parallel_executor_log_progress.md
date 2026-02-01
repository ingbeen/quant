# Implementation Plan: parallel_executor 진행도 로깅 제어 파라미터 추가

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

**작성일**: 2026-01-30 19:00
**마지막 업데이트**: 2026-01-30 20:15
**관련 범위**: utils, tqqq
**관련 문서**: `src/qbt/utils/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `execute_parallel` 및 `execute_parallel_with_kwargs`에 진행도 로깅 제어 파라미터(`log_progress`) 추가
- [x] 기본값은 `True` (기존 동작 유지)
- [x] `_local_refine_search`에서 `log_progress=False`를 전달하여 진행도 로깅 비활성화

## 2) 비목표(Non-Goals)

- 진행도 로깅 로직 자체의 변경 (출력 형식, 빈도 등)
- 다른 `execute_parallel` 호출 지점의 동작 변경 (기본값 `True`로 기존 동작 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `_local_refine_search`는 워크포워드 검증에서 매 월(약 60~120회) 반복 호출된다.
- 각 호출마다 `execute_parallel`의 진행도 로그("진행도: N/M (X%)")가 출력되어 로그가 과도하게 생성된다.
- 국소 탐색(local refine)은 조합 수가 적고 빠르게 완료되므로 진행도 로깅이 불필요하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/utils/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `execute_parallel`에 `log_progress: bool = True` 파라미터 추가
- [x] `execute_parallel_with_kwargs`에 `log_progress: bool = True` 파라미터 추가 및 전달
- [x] `_local_refine_search`에서 `execute_parallel` 호출 시 `log_progress=False` 전달
- [x] 기존 호출 지점은 기본값(`True`)으로 동작 유지 (변경 없음)
- [x] 테스트 추가: `log_progress=False` 전달 시 진행도 로깅이 출력되지 않는지 검증
- [x] `poetry run python validate_project.py` 통과 (passed=250, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/utils/parallel_executor.py`: `log_progress` 파라미터 추가
- `src/qbt/tqqq/simulation.py`: `_local_refine_search` 내 `execute_parallel` 호출 수정
- `tests/test_parallel_executor.py`: `log_progress=False` 테스트 추가

### 데이터/결과 영향

- 없음 (로깅 동작만 변경, 계산 결과 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — 핵심 구현 (그린 유지)

**작업 내용**:

- [x] `parallel_executor.py`의 `execute_parallel` 함수에 `log_progress: bool = True` 파라미터 추가
  - 진행도 로깅 블록(`_should_log_progress` 호출 및 `logger.debug` 출력)을 `log_progress` 조건으로 감싸기
  - 시작/완료 로그(`"병렬 실행 시작"`, `"병렬 실행 완료"`)는 항상 출력 (이것은 작업 추적용이므로 `log_progress`와 무관)
- [x] `parallel_executor.py`의 `execute_parallel_with_kwargs` 함수에 `log_progress: bool = True` 파라미터 추가
  - `execute_parallel` 호출 시 `log_progress` 전달
- [x] `simulation.py`의 `_local_refine_search`에서 `execute_parallel` 호출에 `log_progress=False` 추가
- [x] Docstring 업데이트 (두 함수 모두 `log_progress` 파라미터 설명 추가)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=248, failed=0, skipped=0)

---

### Phase 2 — 테스트 추가 및 최종 검증 (그린 유지)

**작업 내용**:

- [x] `tests/test_parallel_executor.py`에 `log_progress=False` 테스트 추가
  - `log_progress=False`로 실행 시 진행도 로그가 출력되지 않는지 검증
  - `log_progress=True`(기본값)로 실행 시 진행도 로그가 출력되는지 검증
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=250, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 병렬처리 / parallel_executor 진행도 로깅 제어 파라미터 추가 (log_progress)
2. 유틸리티 / execute_parallel 진행도 로깅 on/off 파라미터 추가
3. TQQQ시뮬레이션 / local refine 탐색 시 불필요한 진행도 로깅 비활성화
4. 병렬처리 / log_progress 파라미터 추가 + local refine 로깅 최적화
5. 유틸리티 / 병렬 실행 진행도 로깅 제어 기능 추가 및 적용

## 7) 리스크(Risks)

- 리스크 낮음: 기본값 `True`로 기존 동작이 모두 유지됨
- 시그니처 변경이지만 기본값이 있어 기존 호출 코드 수정 불필요

## 8) 메모(Notes)

### `execute_parallel` 호출 지점 현황

| 위치 | 함수 | 변경 여부 | 비고 |
|------|------|-----------|------|
| `simulation.py:1427` | `find_optimal_cost_model` | 변경 없음 (기본값 True) | 대규모 탐색, 진행도 필요 |
| `simulation.py:1654` | `find_optimal_softplus_model` Stage 1 | 변경 없음 (기본값 True) | 대규모 탐색, 진행도 필요 |
| `simulation.py:1709` | `find_optimal_softplus_model` Stage 2 | 변경 없음 (기본값 True) | 대규모 탐색, 진행도 필요 |
| `simulation.py:1847` | `_local_refine_search` | `log_progress=False` | 반복 호출, 소규모 탐색 |
| `strategy.py:593` | `run_grid_search` | 변경 없음 (기본값 True, kwargs 경유) | 대규모 탐색, 진행도 필요 |

### 진행 로그 (KST)

- 2026-01-30 19:00: 계획서 작성 완료
- 2026-01-30 20:15: Phase 1, Phase 2 완료. 모든 검증 통과 (passed=250, failed=0, skipped=0)

---
