# Implementation Plan: [작업명/기능명]

**상태**: 🟡 Draft / 🔄 In Progress / ✅ Done  
**작성일**: YYYY-MM-DD  
**마지막 업데이트**: YYYY-MM-DD  
**관련 범위**: (예: backtest, tqqq, utils, scripts)  
**관련 문서**: (예: src/qbt/backtest/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

✅ Validation 실패 시 즉시 수정(지워지면 안 됨)

- Validation에서 `poetry run ruff check .` 오류가 나오면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Validation에서 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.

✅ 레드/그린 경계(지워지면 안 됨)

- Phase 0은 “의도적으로 실패하는 테스트(레드) 추가”까지 허용한다.
- Phase 1부터는 **전체 테스트가 통과(그린)하는 상태**를 유지해야 한다.
  - (Phase 0이 있었다면 Phase 1에서 반드시 그린으로 만든다)

✅ 이미 만들어진 계획서 수정 금지(지워지면 안 됨)

- 이미 생성된 `docs/plans/PLAN_<short_name>.md`는 **체크리스트 업데이트 외에는 수정하지 않습니다.**
- (예: 진행 상황 체크, Done 처리, 날짜 업데이트 등은 가능)
- 체크리스트 업데이트란: [ ] -> [x], 상태/날짜 갱신, 진행 로그 추가만 포함(서술/규칙/구조 수정은 금지).
- 내용/구조/규칙을 바꾸고 싶으면 **새 계획서로 작성**합니다.

---

## 1) 목표(Goal)

- 이 작업으로 달성할 “정확한 결과”를 1~3개로 명시한다.
- (예) 핵심 로직/정의/절대 규칙을 변경하고, 그 규칙을 테스트로 고정한다.
- (예) 비용 모델 계산식을 정리하고, 결과 스키마/출력 규칙을 확정한다.

## 2) 비목표(Non-Goals)

- 이번 작업에서 하지 않을 것을 명확히 적는다.
- (예) UI 대규모 개편은 범위 밖
- (예) 새로운 데이터 소스 추가는 범위 밖
- (예) 성능 최적화는 범위 밖(필요하면 별도 plan)

## 3) 배경/맥락(Context)

- 왜 필요한가?
- 현재 문제/불편/버그는 무엇인가?
- 영향을 받는 규칙/정책은 무엇인가?
  - (예) 루트/도메인 `CLAUDE.md`의 불변 규칙
  - (예) “절대 규칙/정의/핵심 로직”이 존재하는 경우 그 규칙

## 4) 완료 조건(Definition of Done)

- [ ] 기능 요구사항 충족
- [ ] 회귀/신규 테스트 추가
- [ ] `./run_tests.sh` 통과
- [ ] `poetry run ruff check .` 통과
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서)
- [ ] 필요한 문서(README/CLAUDE/plan) 업데이트

---

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- (예) `src/qbt/backtest/strategy.py`
- (예) `src/qbt/tqqq/simulation.py`
- (예) `src/qbt/tqqq/constants.py`
- (예) `scripts/...`

### 데이터/결과 영향

- (예) 결과 CSV 스키마/컬럼 영향 여부
- (예) 저장 포맷(meta.json 등) 영향 여부
- (예) 기존 결과 비교(전/후 동일 조건) 필요 여부

---

## 6) 단계별 계획(Phases)

> 아래 Phase들은 예시 템플릿이다.  
> 실제 plan에서는 문맥에 맞게 Phase 수를 조정하되, `docs/CLAUDE.md` 규칙을 따른다.

### (선택) Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 아래 조건 중 하나라도 해당하면 이 Phase를 만든다:
>
> - 핵심 인바리언트/정합성(절대 규칙/정의/중요 로직)의 변경 또는 추가
> - 최종 결과(지표/정의/산식/판단 기준)가 달라질 수 있는 변경
> - 에러 처리 정책 변경(중단 조건/예외 조건/실패 규칙 변경 등)

- [ ] 변경하려는 정책/인바리언트를 관련 문서(도메인 `CLAUDE.md` 등)에 명확히 정리
- [ ] 그 정책을 검증하는 테스트를 먼저 작성(현재 구현에서 실패하도록)
- [ ] 실패 이유 요약(기대값/현재값/왜 중요한지)

**Validation**

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh` (의도한 테스트가 실패하는지 확인)

---

### Phase 1 — 동일 문맥 변경(코드 + 테스트 + 문서)

> 가장 흔한 형태: 같은 목적/같은 문맥의 수정은 한 Phase로 끝낸다.  
> (예: 로직 변경 + 해당 로직 검증 테스트 + 관련 문서 업데이트)

- [ ] 코드 수정(동일 문맥 범위)
- [ ] 관련 테스트 추가/수정(같은 목적의 검증)
- [ ] 관련 문서 업데이트(README/도메인 CLAUDE/plan)

**Validation**

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh`

---

### (선택) 승인 요청 + Commit Messages (Phase 1)

> Phase 2 이상이 존재할 때만 작성한다.
> 커밋 메시지 규칙은 docs/CLAUDE.md의 "커밋 메시지(Commit Messages) 규칙"을 참고

- [ ] Phase 2(또는 다음 Phase)로 진행해도 되는지 승인 요청

#### Commit Messages (Phase 1)

1.
2.
3.

---

### (선택) Phase 2 — 다른 문맥의 리팩토링/정리(성격이 다를 때만)

- [ ] 분리된 목적의 리팩토링/정리
- [ ] 필요 시 추가 테스트/문서 정리

**Validation**

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh`

---

### (선택) 승인 요청 + Commit Messages (Phase 2)

> Phase 3 이상이 존재할 때만 작성한다.  
> 커밋 메시지 규칙은 docs/CLAUDE.md의 "커밋 메시지(Commit Messages) 규칙"을 참고

- [ ] Phase 3(또는 다음 Phase)로 진행해도 되는지 승인 요청

#### Commit Messages (Phase 2)

1.
2.
3.

---

### (선택) 승인 요청 + Commit Messages (Phase N)

> Phase 3 이상이 존재하면, 아래 블록을 “Phase 전환마다” 동일 패턴으로 추가한다.
> 승인 요청이 있는 지점에는 항상 `Commit Messages (Phase N)`이 함께 있어야 한다.

- [ ] 다음 Phase로 진행해도 되는지 승인 요청

#### Commit Messages (Phase N)

1.
2.
3.

---

### 마지막 Phase — 마무리/정리

- [ ] 문서 업데이트(README/CLAUDE/plan)
- [ ] 불필요 파일/산출물 정리
- [ ] `poetry run black .` 실행 (자동 포맷)
- [ ] 최종 검증

**Validation**

- [ ] `poetry run ruff check .`
- [ ] `./run_tests.sh`

#### Commit Messages (Final)

> 커밋 메시지 규칙은 docs/CLAUDE.md의 "커밋 메시지(Commit Messages) 규칙"을 참고

1.
2.
3.

---

## 7) 리스크(Risks)

- (예) 결과 스키마(CSV 컬럼) 변경으로 기존 분석 파이프라인이 깨짐
- (예) 비용 모델/핵심 로직 변경으로 과거 결과와 비교가 어려움
- (예) 핵심 정책 변경으로 성과 지표가 달라짐

### 리스크 완화(Mitigation)

- (예) 출력 컬럼/정렬 규칙을 문서화 + 테스트로 보호
- (예) 변경 전/후 동일 조건 비교 테스트 추가
- (예) 핵심 정책은 Phase 0에서 테스트(레드)로 먼저 고정

---

## 8) 메모(Notes)

- 참고 링크/실험 로그/결정 사항 기록
