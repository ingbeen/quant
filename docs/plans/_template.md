# Implementation Plan: [작업명/기능명]

> 작성/운영 규칙: 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft / 🔄 In Progress / ✅ Done  
**작성일**: YYYY-MM-DD  
**마지막 업데이트**: YYYY-MM-DD  
**관련 범위**: (예: backtest, tqqq, utils, scripts)  
**관련 문서**: (예: src/qbt/backtest/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **삭제 금지 + 수정 금지**  
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**  
> 규칙을 바꾸고 싶다면 이 plan을 고치지 말고 **새 계획서를 작성**하세요.  
> (새 plan에서도 이 블록을 “원문 그대로” 복사합니다.)

✅ Validation 실패 시 즉시 수정(지워지면 안 됨)

- Validation에서 `poetry run ruff check .` 오류가 나오면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Validation에서 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.

✅ 레드/그린 경계(지워지면 안 됨)

- Phase 0은 “의도적으로 실패하는 테스트(레드) 추가”까지 허용한다.
- Phase 1부터는 **전체 테스트가 통과(그린)하는 상태**를 유지해야 한다.
  - (Phase 0이 있었다면 Phase 1에서 반드시 그린으로 만든다)

✅ 스킵(Skipped) 테스트 절대 금지(지워지면 안 됨)

- 어떤 이유로든 테스트를 `skip` 상태로 남겨서는 안 된다.
- `./run_tests.sh` 결과에 **skipped가 1개라도 있으면**:
  - Phase 완료/성공/그린 선언 불가
  - plan 전체 **✅ Done 처리 불가**
- 진행이 어렵다면:
  - Done 처리하지 말고 **상태를 In Progress로 유지**하거나,
  - **새 plan으로 분리**하여 해결한다.

✅ 이미 만들어진 계획서 수정 금지(지워지면 안 됨)

- 이미 생성된 `docs/plans/PLAN_<short_name>.md`는 **체크리스트 업데이트 외에는 수정하지 않습니다.**
- (예: 진행 상황 체크, Done 처리, 날짜 업데이트 등은 가능)
- 체크리스트 업데이트란: [ ] -> [x], 상태/날짜 갱신, 진행 로그 추가만 포함(서술/규칙/구조 수정은 금지).
- 내용/구조/규칙을 바꾸고 싶으면 **새 계획서로 작성**합니다.

✅ 승인 요청 전 체크박스 업데이트 의무(지워지면 안 됨)

- Phase 전환 승인 요청을 하기 전, **반드시 plan의 체크박스를 최신 상태로 업데이트**한다.
- “완료/성공/Done” 같은 표현은 **체크박스와 Validation 증거가 갖춰진 뒤에만** 사용한다.

---

## 1) 목표(Goal)

- [ ] 목표 1:
- [ ] 목표 2:
- [ ] 목표 3:

## 2) 비목표(Non-Goals)

- 범위 밖인 것들을 명확히 적는다.
  - (예) 성능 최적화는 범위 밖(필요하면 별도 plan)
  - (예) UI/대시보드 변경은 범위 밖

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- (왜 이 작업이 필요한가)
- (무엇이 잘못되어 있고, 어떤 위험이 있는가)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.  
> (여기에는 규칙을 요약/나열하지 말고 “문서 목록”만 둡니다.)

- [ ] `CLAUDE.md` (루트)
- [ ] 작업 도메인 `CLAUDE.md`: `src/qbt/<domain>/CLAUDE.md` 또는 `scripts/CLAUDE.md` 등
- [ ] 테스트를 추가/수정한다면 `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 “서술”이 아니라 “체크리스트 + 증거”로만 판단합니다.

- [ ] 기능 요구사항 충족
- [ ] 회귀/신규 테스트 추가
- [ ] `./run_tests.sh` 통과 (**skipped=0**)
- [ ] `poetry run ruff check .` 통과
- [ ] `poetry run black .` 실행 완료 (마지막 Phase)
- [ ] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- (예) `src/qbt/...`
- (예) `tests/...`
- (예) `docs/...`

### 데이터/결과 영향

- (예) 출력 스키마 변경 여부
- (예) 저장 포맷(meta.json 등) 영향 여부
- (예) 기존 결과 비교(전/후 동일 조건) 필요 여부

## 6) 단계별 계획(Phases)

> 아래 Phase들은 **예시 템플릿**입니다.  
> 실제 plan에서는 문맥에 맞게 Phase 수를 조정하되, `docs/CLAUDE.md` 규칙을 따릅니다.

### (선택) Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 아래 조건 중 하나라도 해당하면 이 Phase를 만든다:
>
> - 핵심 인바리언트/정합성(절대 규칙/정의/중요 로직)의 변경
> - “무엇이 맞는가”를 먼저 테스트로 고정해야 하는 작업

**작업 내용**:

- [ ] (예) 핵심 정책을 문서에 명확히 기록
- [ ] (예) 실패 예상 테스트 추가(레드)
- [ ] (예) 커스텀 예외/타입/상수의 인터페이스만 먼저 고정

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (**skipped=0**)

---

### Phase 1 — 핵심 구현/수정(그린 유지, skipped=0)

**작업 내용**:

- [ ] ...
- [ ] ...

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (**skipped=0**)

---

### 승인 요청 + Commit Messages (Phase 1) _(Phase 2 이상이 있다면 필수)_

> ✅ 승인 요청을 올리기 전, 위 Phase 체크박스를 먼저 업데이트한다.

- [ ] **승인 요청**: Phase 2로 진행해도 되는지 요청

**이번 Phase에서 체크된 항목 요약**:

- (예) [x] A, [x] B, [x] C

**Validation 결과**:

- `poetry run ruff check .`: (통과/실패 + 핵심 메시지)
- `./run_tests.sh`: (통과/실패 + passed/failed/skipped 수)
  - skipped가 1 이상이면 승인 요청을 “완료 기반”으로 올릴 수 없다(스킵 제거 후 재요청).

#### Commit Messages (Phase 1)

1. 기능명 / ...
2. 기능명 / ...
3. 기능명 / ...

---

### Phase 2 — (선택) 리팩토링/정리/추가 작업(그린 유지, skipped=0)

**작업 내용**:

- [ ] ...
- [ ] ...

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (**skipped=0**)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] 필요한 문서 업데이트
- [ ] `poetry run black .` 실행(자동 포맷)
- [ ] 최종 검증

**Validation**:

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (**skipped=0**)

#### Commit Messages (Final)

1. 기능명 / ...
2. 기능명 / ...
3. 기능명 / ...

## 7) 리스크(Risks)

- (예) 결과 지표 정의 변경으로 기존 결과와 차이 발생
- (예) 리팩토링 중 회귀 위험
- (예) 테스트가 프로덕션 코드와 불일치할 위험

### 리스크 완화(Mitigation)

- (예) 변경 전/후 비교 테스트 추가
- (예) 핵심 정책은 Phase 0에서 테스트로 고정
- (예) Phase마다 Validation 수행

## 8) 메모(Notes)

- 참고 링크/실험 로그/핵심 결정 사항 기록
