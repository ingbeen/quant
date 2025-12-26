# Implementation Plan: [작업명/기능명]

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft / 🔄 In Progress / ✅ Done  
**작성일**: YYYY-MM-DD HH:MM  
**마지막 업데이트**: YYYY-MM-DD HH:MM  
**관련 범위**: (예: backtest, tqqq, utils, scripts)  
**관련 문서**: (예: src/qbt/backtest/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**  
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**  
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 “레드(의도적 실패 테스트)” 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다. 스킵이 남아있으면 **Done 처리/DoD 체크 금지**.

---

## 1) 목표(Goal)

- [ ] 목표 1:
- [ ] 목표 2:
- [ ] 목표 3:

## 2) 비목표(Non-Goals)

- 범위 밖인 것들을 명확히 적는다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- (왜 이 작업이 필요한가)
- (무엇이 잘못되어 있고, 어떤 위험이 있는가)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.  
> (규칙을 요약/나열하지 말고 “문서 목록”만 둡니다.)

- [ ] `CLAUDE.md` (루트)
- [ ] 작업 도메인 `CLAUDE.md`: `src/qbt/<domain>/CLAUDE.md` 또는 `scripts/CLAUDE.md` 등
- [ ] 테스트를 추가/수정한다면 `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 “서술”이 아니라 “체크리스트 상태”로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 기능 요구사항 충족
- [ ] 회귀/신규 테스트 추가
- [ ] `./run_tests.sh` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run ruff check .` 통과
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- (예) `src/qbt/...`
- (예) `tests/...`
- (예) `docs/...`

### 데이터/결과 영향

- (예) 출력 스키마 변경 여부
- (예) 기존 결과 비교 필요 여부

## 6) 단계별 계획(Phases)

### (선택) Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 아래 조건 중 하나라도 해당하면 이 Phase를 만든다:
>
> - 핵심 인바리언트/정합성(절대 규칙/정의/중요 로직)의 변경 또는 추가
> - 최종 결과(지표/정의/산식/판 판단 기준)가 달라질 수 있는 변경
> - 에러 처리 정책 변경(중단 조건/예외 조건/실패 규칙 변경 등)

**작업 내용**:

- [ ] (예) 핵심 정책/정의를 문서에 명확히 기록
- [ ] (예) 만들 수 있는 테스트를 최대한 먼저 추가(레드 허용)
- [ ] (예) 인터페이스/예외/타입/상수 형태를 먼저 고정

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (passed=**, failed=**, skipped=\_\_)

---

### Phase 1 — 핵심 구현/수정(그린 유지)

**작업 내용**:

- [ ] ...
- [ ] ...

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (passed=**, failed=**, skipped=\_\_)

---

### Phase 2 — (선택) 리팩토링/정리/추가 작업(그린 유지)

**작업 내용**:

- [ ] ...
- [ ] ...

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (passed=**, failed=**, skipped=\_\_)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] 필요한 문서 업데이트
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 최종 검증

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (passed=**, failed=**, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 기능명 / 핵심 변경 요약 (정확성/정합성/정책 반영)
2. 기능명 / 버그 수정 + 테스트 보강 (회귀 방지)
3. 기능명 / 정책 변경 반영 및 검증 로직 정리
4. 기능명 / 리팩토링(동작 동일) + 린트/포맷 정리
5. 기능명 / 문서/규칙 업데이트 + 구현 반영

## 7) 리스크(Risks)

- (예) 최종 지표/정의 변경으로 기존 결과와 차이 발생
- (예) 리팩토링 중 회귀 위험

## 8) 메모(Notes)

- 참고 링크/실험 로그/핵심 결정 사항 기록
- 스킵이 존재한다면 반드시 사유/해제 조건/후속 plan 기록

### 진행 로그 (KST)

- YYYY-MM-DD HH:MM: ...
- YYYY-MM-DD HH:MM: ...

---

<!--
(옵션 블록 라이브러리) — 사용자가 요청한 경우에만, 특정 Phase 아래에 복사해서 사용

### 승인 요청 (Optional)

> ✅ 승인 요청을 올리기 전, 위 Phase 체크박스를 먼저 업데이트한다.

- [ ] **승인 요청**: 다음 Phase로 진행해도 되는지 요청

**이번 Phase에서 체크된 항목 요약**:

- (예) [x] A, [x] B, [x] C

**Validation 결과**:

- `poetry run ruff check .`: (통과/실패 + 핵심 메시지)
- `./run_tests.sh`: (통과/실패 + passed/failed/skipped 수)
