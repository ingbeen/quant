# Implementation Plan: 테스트 품질 개선

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

**작성일**: 2026-02-20 20:00
**마지막 업데이트**: 2026-02-20 21:20
**관련 범위**: tests
**관련 문서**: `tests/CLAUDE.md`

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

- [x] 목표 1: `try/except/pass` 패턴으로 미검증되는 테스트 수정 (보고서 A-4)
- [x] 목표 2: 조건부 가드(`if len >= N`)로 인한 assert 누락 패턴 개선 (보고서 G-1)
- [x] 목표 3: 타임존 의존적 하드코딩 수정 (보고서 G-2)
- [x] 목표 4: `caplog` 미활용 테스트 수정 (보고서 G-3)

## 2) 비목표(Non-Goals)

- 프로덕션 코드 변경: 테스트 코드만 수정
- 새로운 테스트 시나리오 추가: 기존 테스트의 품질 개선에 집중
- 커버리지 목표 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- A-4: `test_ffr_fallback_within_2_months`가 ValueError 시 `pass`로 넘기므로, fallback이 실제로 동작하는지 전혀 검증하지 않음. 성공/실패 모두 통과하는 무의미한 테스트
- G-1: `test_strategy.py`의 여러 테스트에서 `if len(equity_df) >= N:` 가드 안에 assert를 감싸 데이터가 예상보다 짧으면 검증을 건너뜀
- G-2: `test_meta_manager.py`에서 `"2024-01-15T19:30:00+09:00"` 하드코딩. KST가 아닌 타임존에서 실패
- G-3: `test_data_loader.py`에서 `caplog`을 인자로 받으면서 경고 로그 검증 없음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `tests/CLAUDE.md`: 결정적 테스트, Given-When-Then 패턴, 부동소수점 비교 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] A-4: `test_ffr_fallback_within_2_months`가 fallback 동작을 명확히 검증
- [x] G-1: 조건부 가드 앞에 데이터 길이 assert 추가 (또는 가드 제거 후 직접 assert)
- [x] G-2: 타임존 의존성 제거, 날짜 부분 매칭 또는 타임존 독립적 검증으로 변경
- [x] G-3: `caplog` 사용 시 경고 로그 발생 여부 검증 추가, 또는 `caplog` 인자 제거
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `tests/test_tqqq_simulation.py` — A-4: `test_ffr_fallback_within_2_months` 수정
- `tests/test_strategy.py` — G-1: 줄 502, 810, 855, 896 등 조건부 가드 개선
- `tests/test_meta_manager.py` — G-2: 줄 397 타임존 하드코딩 수정
- `tests/test_data_loader.py` — G-3: 줄 30, 119 `caplog` 활용 또는 제거

### 데이터/결과 영향

- 없음. 테스트 코드만 변경하므로 프로덕션 출력에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 테스트 검증 로직 수정 (그린 유지)

**작업 내용**:

- [x] A-4: `test_ffr_fallback_within_2_months` 수정
  - `try/except/pass` 패턴 제거
  - fallback이 동작하면 `daily_cost > 0` 검증
  - fallback이 실패해야 하는 경우는 `pytest.raises(ValueError)`로 명시적 검증
  - 프로덕션 코드의 실제 동작(fallback 성공 or 실패)을 먼저 확인 후 적절한 방향 결정
- [x] G-1: `test_strategy.py`의 조건부 가드 개선 (4개 위치)
  - 방안 A: 가드 제거 후 데이터 길이를 직접 assert (`assert len(equity_df) >= N`)
  - 방안 B: 가드 앞에 선행 assert 추가 (`assert len(equity_df) >= N, "데이터 부족"`)
  - 기존 테스트 의도를 확인하여 적합한 방안 선택

---

### Phase 2 — 결정적 테스트 및 미활용 인자 수정 (그린 유지)

**작업 내용**:

- [x] G-2: `test_meta_manager.py:397` 타임존 하드코딩 수정
  - `assert entry["timestamp"] == "2024-01-15T19:30:00+09:00"` → 날짜 부분만 매칭
  - 예: `assert "2024-01-15" in entry["timestamp"]` (기존 같은 파일의 다른 테스트 패턴과 동일)
- [x] G-3: `test_data_loader.py` `caplog` 수정
  - 줄 30 (`test_normal_load`): `caplog` 인자가 불필요하면 제거
  - 줄 119 (`test_duplicate_dates_removed`): 경고 로그 검증 추가
    - 예: `assert any("중복" in record.message for record in caplog.records)` 또는 프로덕션 코드의 실제 경고 메시지 확인 후 매칭

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / 미검증 패턴 수정 + 결정적 테스트 강화 (fallback, 타임존, caplog)
2. 테스트 / A-4, G-1~G-3 테스트 품질 개선 (프로덕션 변경 없음)
3. 테스트 / try/except/pass 제거 + 조건부 가드 보강 + caplog 활용
4. 테스트 / 테스트 신뢰성 향상 — 미검증 경로 및 환경 의존성 해소
5. 테스트 / 품질 개선 4건 (fallback 검증, 가드 assert, 타임존, caplog)

## 7) 리스크(Risks)

- A-4: 프로덕션 코드의 실제 fallback 동작을 확인해야 함. fallback이 성공하는 케이스와 실패하는 케이스가 다를 수 있음
- G-1: 기존 가드가 의도적(방어적)인 경우 제거하면 CI에서 실패할 수 있음. 데이터 크기가 보장되는지 먼저 확인
- G-3: 프로덕션 코드에서 실제로 경고 로그를 출력하는지 확인 필요. 로그가 없다면 `caplog` 제거가 적합

## 8) 메모(Notes)

- 이 계획서는 `PROJECT_ANALYSIS_REPORT.md`의 A-4, G-1, G-2, G-3 항목을 대상으로 함
- 모든 변경은 테스트 코드에 한정되며 프로덕션 코드에 영향 없음

### 진행 로그 (KST)

- 2026-02-20 20:00: 계획서 초안 작성
- 2026-02-20 21:20: Phase 1~3 완료, 전체 검증 통과 (passed=301, failed=0, skipped=0)

---
