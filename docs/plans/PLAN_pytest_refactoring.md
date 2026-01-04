# Implementation Plan: Pytest 테스트 코드 리팩토링 (Parametrize 및 픽스처 모듈화)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-01-03 18:20
**마지막 업데이트**: 2026-01-03 18:20
**관련 범위**: tests
**관련 문서**: tests/CLAUDE.md

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

- [ ] `@pytest.mark.parametrize` 데코레이터 활용으로 반복 테스트 코드 간소화
- [ ] conftest.py의 픽스처 모듈화로 테스트 의도 명확화 및 격리 강화
- [ ] 테스트 유지보수성 향상 (새 케이스 추가 용이, 불필요한 mock 제거)

## 2) 비목표(Non-Goals)

- 테스트 커버리지 대폭 확대 (기존 테스트 개선에 집중)
- 테스트 프레임워크 교체 또는 플러그인 추가
- 프로덕션 코드 수정 (테스트 코드만 리팩토링)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**Parametrize 부재**:
- 현재: 유사한 테스트 케이스가 개별 메서드로 중복 작성됨
- 예: `test_analysis.py`에서 다양한 윈도우 크기를 각각 별도 메서드로 테스트
- Context7 Best Practice: `@pytest.mark.parametrize` 사용으로 중복 제거
- 개선 효과: 코드 간소화, 새 케이스 추가 용이, 실패 시 원인 명확

**픽스처 일괄 패치**:
- 현재: `mock_storage_paths` 픽스처가 모든 경로를 한 번에 패치
- Context7 Best Practice: 세분화된 픽스처 제공 (모듈화)
- 개선 효과: 테스트가 필요한 mock만 명시, 의도 명확화, 격리 강화

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `tests/CLAUDE.md` (테스트 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] parametrize 적용으로 중복 테스트 메서드 통합
- [ ] conftest.py 픽스처 모듈화 (세분화된 픽스처 제공)
- [ ] 기존 테스트 모두 통과 (동작 변경 없음, 테스트 개수는 동일하거나 증가 가능)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**Parametrize 적용**:
- `tests/test_analysis.py` - 이동평균 윈도우 테스트
- `tests/test_strategy.py` - 전략 파라미터 조합 테스트 (필요 시)
- `tests/test_tqqq_simulation.py` - 레버리지/비용 조합 테스트 (필요 시)

**픽스처 모듈화**:
- `tests/conftest.py` - `mock_storage_paths` 분해

### 데이터/결과 영향

- 테스트 동작 및 커버리지는 동일 (리팩토링만 수행)
- 테스트 실행 결과는 변경 없음 (passed 수는 동일하거나 증가 가능)

## 6) 단계별 계획(Phases)

### Phase 1 — Parametrize 적용으로 반복 테스트 통합

**작업 내용**:

- [ ] `tests/test_analysis.py` 분석
  - 이동평균 윈도우 테스트에서 반복 패턴 식별
  - `@pytest.mark.parametrize("window", [3, 5, 10, 20])` 형태로 통합 가능 여부 확인
- [ ] parametrize 적용
  - 중복 메서드를 하나의 파라미터화된 메서드로 통합
  - Given-When-Then 패턴 유지
  - docstring에 파라미터 설명 추가
- [ ] 다른 테스트 파일 검토 (test_strategy.py, test_tqqq_simulation.py)
  - 유사한 반복 패턴 존재 시 parametrize 적용
  - 단, 테스트 의도가 달라지지 않도록 주의

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

---

### Phase 2 — 픽스처 모듈화 (세분화)

**작업 내용**:

- [ ] `tests/conftest.py` 분석
  - 현재 `mock_storage_paths` 픽스처가 패치하는 경로 목록 확인
  - 각 경로별 사용 빈도 및 테스트 의존성 분석
- [ ] 세분화된 픽스처 생성
  - `mock_stock_dir`: STOCK_DIR만 패치
  - `mock_results_dir`: RESULTS_DIR만 패치
  - `mock_etc_dir`: ETC_DIR만 패치
  - 기존 `mock_storage_paths`는 하위 호환성을 위해 유지 (모든 픽스처 조합)
- [ ] 테스트 코드에서 필요한 픽스처만 선택적으로 사용
  - 각 테스트가 실제로 필요한 픽스처만 인자로 받도록 수정
  - 예: 주식 데이터만 필요한 테스트는 `mock_stock_dir`만 사용
- [ ] 픽스처 docstring 작성 (용도 및 패치 대상 명시)

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `tests/CLAUDE.md`에 parametrize 및 픽스처 모듈화 예시 추가 (필요 시)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 전체 테스트 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / Parametrize 및 픽스처 모듈화로 유지보수성 개선
2. 리팩토링 / Pytest 테스트 코드 간소화 (중복 제거, 의도 명확화)
3. 테스트 / Context7 Best Practice 적용 (parametrize, 픽스처 분리)
4. 개선 / 테스트 코드 품질 향상 (반복 통합, mock 격리 강화)
5. 테스트 / Pytest 리팩토링 (동작 동일, 구조 개선)

## 7) 리스크(Risks)

- **리스크**: parametrize 적용 시 테스트 의도가 모호해질 수 있음
  - **완화**: docstring 및 파라미터 이름으로 의도 명확히 표현, Given-When-Then 유지
- **리스크**: 픽스처 분리로 기존 테스트 실패 가능성
  - **완화**: 기존 `mock_storage_paths` 유지로 하위 호환성 확보, 각 Phase에서 즉시 검증
- **리스크**: 테스트 개수 변화로 회귀 감지 어려움
  - **완화**: Validation에서 passed 수 기록 및 비교, 동작 변경 없음 확인

## 8) 메모(Notes)

- Context7 Best Practice 참고:
  - `@pytest.mark.parametrize`: 반복 테스트 간소화
  - 픽스처 모듈화: 테스트별 필요한 mock만 명시
- parametrize는 클래스 레벨에도 적용 가능 (클래스 내 모든 메서드에 적용)
- 픽스처 분리 시 각 픽스처가 독립적으로 동작하도록 설계

### 진행 로그 (KST)

- 2026-01-03 18:20: 계획서 초안 작성 완료

---
