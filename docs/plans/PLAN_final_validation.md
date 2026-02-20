# Implementation Plan: 최종 통합 검증

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

**작성일**: 2026-02-20 20:00
**마지막 업데이트**: 2026-02-20 20:00
**관련 범위**: 프로젝트 전체
**관련 문서**: `CLAUDE.md`(루트), 모든 도메인 `CLAUDE.md`

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

- [ ] 목표 1: Plan 1~5의 모든 변경 사항이 기능 동일성을 유지하는지 통합 검증
- [ ] 목표 2: 전체 품질 게이트(Ruff + PyRight + Pytest) 통과 확인
- [ ] 목표 3: 분석 보고서(PROJECT_ANALYSIS_REPORT.md)의 해결 상태 최종 업데이트

## 2) 비목표(Non-Goals)

- 새로운 기능 추가
- 추가 리팩토링 (이미 계획서 1~5에서 완료된 범위에 한정)
- 향후 과제(C-1~3, D-3~5) 진행

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- Plan 1~5를 순차적으로 실행한 후, 전체 프로젝트가 여전히 정상 동작하는지 최종 확인이 필요
- 개별 Plan은 각자의 범위에서 검증하지만, Plan 간 상호작용으로 인한 부작용을 교차 검증해야 함

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md`(루트): 전체 프로젝트 규칙
- `tests/CLAUDE.md`: 테스트 원칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인
- `src/qbt/tqqq/CLAUDE.md`: TQQQ 도메인
- `src/qbt/utils/CLAUDE.md`: 유틸리티
- `scripts/CLAUDE.md`: CLI 스크립트

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 전체 품질 게이트 통과: `poetry run python validate_project.py` (Ruff + PyRight + Pytest)
- [ ] Ruff: 린트 에러 0건
- [ ] PyRight: 타입 에러 0건
- [ ] Pytest: failed=0, skipped=0
- [ ] `poetry run black .` 실행 후 diff 없음 (포맷 일관성)
- [ ] Plan 1~5의 DoD가 모두 [x] 상태인지 확인
- [ ] PROJECT_ANALYSIS_REPORT.md에 해결 상태 반영
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `PROJECT_ANALYSIS_REPORT.md` — 해결 상태 업데이트
- 각 Plan에서 수정된 파일에 대한 교차 검증 (수정 없이 검증만)
- Plan 간 상호작용으로 발생하는 문제가 있을 경우 해당 파일 수정

### 데이터/결과 영향

- 없음. 검증 전용 Plan이므로 프로덕션 코드/데이터에 추가 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 선행 Plan 완료 확인

**작업 내용**:

- [ ] Plan 1 (PLAN_docs_comments_cleanup.md) 상태: Done 확인
- [ ] Plan 2 (PLAN_bug_fixes.md) 상태: Done 확인
- [ ] Plan 3 (PLAN_constants_consistency.md) 상태: Done 확인
- [ ] Plan 4 (PLAN_refactoring.md) 상태: Done 확인
- [ ] Plan 5 (PLAN_test_quality.md) 상태: Done 확인

---

### Phase 2 — 통합 품질 검증

**작업 내용**:

- [ ] `poetry run black .` 실행 — 포맷 변경 없음 확인
- [ ] `poetry run python validate_project.py` 전체 실행
  - Ruff 린트: 에러 0건
  - PyRight 타입 체크: 에러 0건
  - Pytest 테스트: failed=0, skipped=0
- [ ] 실패 시: 원인 파악 후 해당 Plan 범위에서 수정, 재검증

---

### Phase 3 — 교차 검증 (Plan 간 상호작용 확인)

**작업 내용**:

- [ ] import 경로 검증: Plan 3(상수 통합) + Plan 4(함수 추출)로 변경된 import가 모든 파일에서 정상 동작하는지 확인
- [ ] 상수 참조 검증: Plan 3에서 통합된 상수가 Plan 2(버그 수정)에서 수정된 코드와 충돌하지 않는지 확인
- [ ] 테스트 검증: Plan 5에서 수정된 테스트가 Plan 2/4의 코드 변경과 호환되는지 확인

---

### Phase 4 (마지막) — 보고서 업데이트 및 최종 마무리

**작업 내용**:

- [ ] `PROJECT_ANALYSIS_REPORT.md`에 각 항목별 해결 상태 업데이트
  - 해결된 항목: 해당 Plan 번호와 함께 표기
  - 미해결 항목(향후 과제): 상태 유지
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트 / 전체 분석 보고서 기반 개선 완료 — 통합 검증 통과
2. 프로젝트 / Plan 1~5 통합 검증 완료 + 분석 보고서 상태 업데이트
3. 프로젝트 / 코드 품질 개선 6개 Plan 완료 — 최종 검증
4. 프로젝트 / 문서/버그/상수/리팩토링/테스트 전면 개선 — 통합 검증
5. 프로젝트 / PROJECT_ANALYSIS_REPORT 기반 37건 개선 — 최종 마무리

## 7) 리스크(Risks)

- Plan 간 상호작용으로 예상치 못한 충돌 가능. 특히 Plan 3(상수 이동)과 Plan 4(함수 이동)이 동일 파일을 수정할 수 있음
- 해결 전략: Phase 3에서 교차 검증으로 조기 발견

## 8) 메모(Notes)

- 이 계획서는 반드시 Plan 1~5가 모두 완료된 후에 실행
- 실행 순서: Plan 1 → Plan 2 → Plan 3 → Plan 4 → Plan 5 → Plan 6 (이 계획서)
- Plan 1~3은 독립적으로 실행 가능하나, Plan 4는 Plan 3(상수 통합) 이후 실행 권장
- Plan 5는 Plan 2(버그 수정) 이후 실행 권장 (수정된 코드를 테스트해야 하므로)

### Plan 실행 의존성 다이어그램

```
Plan 1 (문서/주석)  ──┐
Plan 2 (버그 수정)  ──┼── Plan 5 (테스트) ──┐
Plan 3 (상수 통합)  ──┼── Plan 4 (리팩토링) ──┼── Plan 6 (최종 검증)
```

### 향후 과제 (별도 계획서 대상)

- C-1: `download_data.py` 비즈니스 로직 분리
- C-2: `validate_walkforward_fixed_ab.py` 비즈니스 로직 분리
- C-3: `generate_synthetic.py` 비즈니스 로직 분리
- D-3: 3개 워크포워드 스크립트 통합
- D-4: `simulation.py` (2108줄) 파일 분할
- D-5: `app_rate_spread_lab.py` (1762줄) 파일 분할

### 진행 로그 (KST)

- 2026-02-20 20:00: 계획서 초안 작성

---
