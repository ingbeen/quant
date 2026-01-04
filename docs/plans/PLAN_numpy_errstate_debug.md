# Implementation Plan: NumPy errstate 디버깅 유틸리티 추가

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
**관련 범위**: utils, tests
**관련 문서**: src/qbt/utils/CLAUDE.md, tests/CLAUDE.md

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

- [ ] NumPy errstate를 활용한 부동소수점 오류 감지 유틸리티 추가 (디버깅/테스트용)
- [ ] 테스트 환경에서 부동소수점 연산 오류(division by zero, overflow, invalid 등) 조기 발견
- [ ] 프로덕션 코드는 기존 EPSILON 방식 유지 (errstate는 선택적 활용)

## 2) 비목표(Non-Goals)

- 프로덕션 코드의 모든 연산에 errstate 적용 (성능 저하 우려)
- 기존 EPSILON 기반 안전 장치 제거
- 테스트가 아닌 일반 실행에서 errstate 강제 활성화

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 상태**:
- EPSILON (`1e-12`) 사용으로 분모 0 및 로그 계산 안정성 확보
- 부동소수점 오류는 사전 방지 방식으로 처리 중
- 잠재적 문제: EPSILON으로 방지하지 못한 오류는 조용히 전파될 수 있음

**Context7 Best Practice**:
- `np.errstate(all='warn')`: 부동소수점 오류 발생 시 경고 출력
- 디버깅 및 테스트에서 유용 (오류 조기 감지)

**개선 방향**:
- 테스트 환경에서 errstate를 활성화하여 숨은 부동소수점 오류 감지
- 프로덕션은 기존 EPSILON 방식 유지 (성능 및 안정성)
- 선택적 디버깅 모드 제공 (환경 변수 또는 플래그)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/utils/CLAUDE.md` (유틸리티 패키지)
- `tests/CLAUDE.md` (테스트 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] errstate 유틸리티 함수 또는 픽스처 추가
- [ ] 테스트 환경에서 errstate 활성화 옵션 제공 (pytest 플러그인 또는 conftest 픽스처)
- [ ] 기존 테스트 모두 통과 (errstate로 인한 새 경고는 문서화)
- [ ] 프로덕션 코드 동작 변경 없음 확인
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 사용법 문서화 (README 또는 utils/CLAUDE.md)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**유틸리티 추가**:
- `src/qbt/utils/` - 새 모듈 `numpy_debug.py` 또는 기존 모듈에 함수 추가 (선택)
- `tests/conftest.py` - errstate 활성화 픽스처 추가 (선택)

**문서**:
- `src/qbt/utils/CLAUDE.md` 또는 `README.md` - 사용법 안내

### 데이터/결과 영향

- 프로덕션 실행 결과 변경 없음
- 테스트 환경에서 부동소수점 경고 출력 가능 (디버깅 정보)

## 6) 단계별 계획(Phases)

### Phase 1 — errstate 유틸리티 설계 및 구현

**작업 내용**:

- [ ] 구현 방식 결정 (2가지 옵션 중 선택)
  - **옵션 A**: pytest 픽스처로 제공 (tests/conftest.py)
    - 장점: 테스트에서 선택적으로 사용 가능
    - 예: `def test_foo(enable_numpy_warnings): ...`
  - **옵션 B**: 유틸리티 함수/컨텍스트 매니저 제공 (src/qbt/utils/)
    - 장점: 테스트 외에도 디버깅 스크립트에서 사용 가능
    - 예: `with numpy_errstate_debug(): ...`
- [ ] 선택한 방식으로 구현
  - Context7 Best Practice: `np.errstate(all='warn')` 사용
  - 경고 필터 설정 (invalid, divide, overflow, underflow 등)
- [ ] 간단한 테스트 작성 (errstate가 정상 작동하는지 검증)
  - 예: 0으로 나누기 시 경고 발생 확인

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

---

### Phase 2 — 기존 테스트에 선택적 적용 및 검증

**작업 내용**:

- [ ] 핵심 수치 계산 테스트에 errstate 적용 (선택적)
  - `tests/test_analysis.py` (이동평균, 성과 지표 계산)
  - `tests/test_tqqq_simulation.py` (레버리지 시뮬레이션)
- [ ] errstate 활성화 시 발생하는 경고 확인
  - 예상된 경고 (EPSILON으로 방지 중): 무시 또는 문서화
  - 예상치 못한 경고: 원인 분석 및 수정 고려
- [ ] 프로덕션 코드 실행하여 동작 변경 없음 확인
  - errstate는 테스트/디버깅 환경에서만 활성화됨을 검증

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] 사용법 문서 작성
  - `src/qbt/utils/CLAUDE.md` 또는 README에 errstate 유틸리티 사용법 추가
  - 예시 코드 및 활용 시나리오 제공 (디버깅, 테스트)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 유틸 / NumPy errstate 디버깅 유틸리티 추가 (테스트/디버깅용)
2. 개선 / 부동소수점 오류 조기 감지를 위한 errstate 지원
3. 테스트 / NumPy 경고 활성화 옵션 추가 (디버깅 편의성 향상)
4. 유틸 / Context7 Best Practice 적용 (NumPy errstate)
5. 리팩토링 / 수치 안정성 디버깅 도구 추가 (선택적 활용)

## 7) 리스크(Risks)

- **리스크**: errstate 활성화로 예상치 못한 경고 대량 발생 가능
  - **완화**: 선택적 활성화 방식으로 기본 동작 유지, 경고 필터링 옵션 제공
- **리스크**: 성능 저하 우려
  - **완화**: 테스트/디버깅 환경에서만 사용, 프로덕션은 기존 EPSILON 방식 유지
- **리스크**: 테스트 실패 증가 가능성
  - **완화**: 각 Phase에서 즉시 검증, 예상 경고는 문서화하여 관리

## 8) 메모(Notes)

- Context7 Best Practice: `with np.errstate(all='warn'): ...`
- NumPy errstate 옵션:
  - `all='warn'`: 모든 부동소수점 오류를 경고로 출력
  - `divide='warn'`: 0으로 나누기 경고
  - `invalid='warn'`: NaN 생성 경고
  - `overflow='warn'`: 오버플로 경고
- 현재 프로젝트는 EPSILON으로 사전 방지 중이므로 errstate는 보조 도구로 활용

### 진행 로그 (KST)

- 2026-01-03 18:20: 계획서 초안 작성 완료

---
