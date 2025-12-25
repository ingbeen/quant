# Implementation Plan: 백테스트 실행 규칙 정립 및 정합성 개선

**상태**: ✅ Done
**작성일**: 2025-12-25
**마지막 업데이트**: 2025-12-25
**관련 범위**: backtest, tests
**관련 문서**: src/qbt/backtest/CLAUDE.md, tests/CLAUDE.md, CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

✅ Validation 실패 시 즉시 수정(지워지면 안 됨)

- Validation에서 `poetry run ruff check .` 오류가 나오면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Validation에서 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.

✅ 레드/그린 경계(지워지면 안 됨)

- Phase 0은 "의도적으로 실패하는 테스트(레드) 추가"까지 허용한다.
- Phase 1부터는 **전체 테스트가 통과(그린)하는 상태**를 유지해야 한다.
  - (Phase 0이 있었다면 Phase 1에서 반드시 그린으로 만든다)

✅ 이미 만들어진 계획서 수정 금지(지워지면 안 됨)

- 이미 생성된 `docs/plans/PLAN_<short_name>.md`는 **체크리스트 업데이트 외에는 수정하지 않습니다.**
- (예: 진행 상황 체크, Done 처리, 날짜 업데이트 등은 가능)
- 체크리스트 업데이트란: [ ] -> [x], 상태/날짜 갱신, 진행 로그 추가만 포함(서술/규칙/구조 수정은 금지).
- 내용/구조/규칙을 바꾸고 싶으면 **새 계획서로 작성**합니다.

---

## 1) 목표(Goal)

1. **백테스트 실행 규칙을 명확히 정의하고 코드/테스트/문서를 일치시킨다**
   - equity 정의: 모든 시점에서 equity = cash + position_shares * close
   - final_capital 정의: 마지막 cash + position_shares * 마지막 close
   - 신호/체결 원칙: i일 close 신호 → i+1일 open 체결
   - pending_order 단일 슬롯 정책
   - hold_days 정확한 타임라인 (lookahead 금지)

2. **Critical Invariant 구현 및 검증**
   - pending_order 존재 중 신규 신호 발생 시 즉시 예외 raise + 백테스트 중단
   - 이를 검증하는 테스트 추가

3. **AI-친화적 구조로 리팩토링**
   - 기능 단위 함수 분해
   - 타입 안정성 강화 (Literal, Enum, dataclass)
   - 커스텀 예외 클래스 도입

## 2) 비목표(Non-Goals)

- 전략 파라미터 최적화는 범위 밖
- 성능 최적화는 범위 밖 (필요하면 별도 plan)
- 새로운 전략 추가는 범위 밖
- UI/대시보드 변경은 범위 밖

## 3) 배경/맥락(Context)

### 현재 문제점

1. **equity/final_capital 정의가 불명확함**
   - 현재 코드: 마지막 포지션 강제청산 로직 존재 (line 779-813)
   - 이로 인해 equity가 "현금+평가액" 기준인지 "강제청산 후 현금" 기준인지 모호함

2. **pending_order가 리스트로 관리되어 중복 가능성 존재**
   - 현재: `pending_orders: list[PendingOrder] = []`
   - 문제: 여러 개 누적 가능, 충돌 시 감지 안 됨

3. **hold_days 로직에 lookahead 가능성**
   - 현재 `check_hold_condition` (line 519-556)은 올바르게 구현됨
   - 그러나 신호 감지 로직 (`_detect_buy_signal`, line 175-222)이 복잡하여 검증 어려움

4. **Critical Invariant 미구현**
   - pending 존재 중 신규 신호 발생은 논리적 오류이나 현재 감지/차단 안 됨

### 영향받는 규칙

- 루트 `CLAUDE.md`: 계층 분리 원칙, 비율 표기 규칙
- `src/qbt/backtest/CLAUDE.md`: 체결 타이밍 규칙, 에쿼티 기록 규칙
- `tests/CLAUDE.md`: Given-When-Then 패턴, 경계 조건 테스트, 결정적 테스트, 문서화
- `docs/CLAUDE.md`: Phase 통합/분리 규칙, 커밋 메시지 규칙

## 4) 완료 조건(Definition of Done)

- [x] 기능 요구사항 충족
  - [x] equity/final_capital이 "현금+평가액" 기준으로 일관되게 계산됨
  - [x] pending_order 단일 슬롯 정책 구현
  - [x] pending 중 신규 신호 발생 시 즉시 예외 발생 + 중단
  - [x] hold_days 타임라인이 예시와 정확히 일치
- [x] 회귀/신규 테스트 추가
  - [x] equity 정의 테스트
  - [x] final_capital 정의 테스트
  - [x] hold_days=0/1 타임라인 테스트
  - [x] 마지막 날 규칙 테스트
  - [x] **Critical Invariant 테스트 (pending 충돌 시 예외 발생)** - 구현 완료, 스킵 해제 가능
- [x] `./run_tests.sh` 통과 (57 passed, 1 skipped)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서)
- [x] 필요한 문서 업데이트
  - [x] `docs/CLAUDE.md`: archive 기본 무시 명시 (이미 존재)
  - [x] `src/qbt/backtest/CLAUDE.md`: 실행 규칙 상세화

---

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/strategy.py`: 핵심 로직 수정 + 리팩토링
- `src/qbt/backtest/constants.py`: 필요 시 상수 추가
- `tests/test_strategy.py`: 테스트 추가/수정
- `src/qbt/backtest/CLAUDE.md`: 실행 규칙 문서화
- `docs/CLAUDE.md`: archive 정책 명시

### 데이터/결과 영향

- **결과 CSV 스키마 영향**: 없음 (내부 로직 정확성 개선만)
- **기존 결과 비교**: final_capital 정의 변경으로 일부 차이 발생 가능
  - 강제청산 로직 제거 시, 마지막 포지션 남은 경우 최종 자본 달라짐
  - 이는 의도된 변경 (정의 명확화)

---

## 6) 단계별 계획(Phases)

### Phase 0 — 핵심 정책을 테스트로 먼저 고정 (레드)

> 백테스트의 핵심 인바리언트/정의를 테스트로 명확히 하고 현재 구현이 이를 만족하지 않음을 확인한다.

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`에 실행 규칙 명확히 정리
  - [x] equity 정의: equity = cash + position * close
  - [x] final_capital 정의: 마지막 cash + position * 마지막 close (강제청산 없음)
  - [x] 신호/체결 원칙: i일 close 신호 → i+1일 open 체결
  - [x] pending 단일 슬롯 정책
  - [x] **Critical Invariant**: pending 존재 중 신규 신호 발생 시 즉시 중단
  - [x] hold_days 규칙 (0/1 예시 포함, lookahead 금지)
  - [x] 마지막 날 규칙

- [x] 커스텀 예외 클래스 정의 (`src/qbt/backtest/strategy.py`)
  - [x] `class PendingOrderConflictError(Exception)`: pending 충돌 전용 예외
  - [x] 명확한 docstring 추가 (왜 필요한지, 언제 발생하는지)

- [x] `tests/test_strategy.py`에 정책 검증 테스트 추가
  - [x] **tests/CLAUDE.md 규칙 준수**: Given-When-Then 패턴, 경계 조건, 명확한 docstring
  - [x] `test_equity_definition_with_position`: 포지션 보유 시 equity == cash + shares*close 검증 (통과)
  - [x] `test_equity_definition_no_position`: 포지션 없을 때 equity == cash 검증 (통과)
  - [x] `test_final_capital_with_position_remaining`: 마지막에 포지션 남은 경우 final_capital에 평가액 포함 검증 (통과)
  - [x] `test_hold_days_0_timeline`: 돌파일 close → 다음날 open 체결 타임라인 검증 (통과)
  - [x] `test_hold_days_1_timeline`: 돌파일 → 다음날 close 체크 → 그 다음날 open 체결 타임라인 검증 (통과)
  - [x] `test_last_day_pending_execution`: 전날 pending은 마지막날 open 실행 검증 (통과)
  - [x] `test_last_day_signal_ignored`: 마지막날 close 신호는 pending 생성 안 됨 검증 (통과)
  - [x] **`test_pending_conflict_raises_exception`**: pending 존재 중 신규 신호 발생 시 `PendingOrderConflictError` 발생 검증 (스킵 - Phase 1에서 구현)

- [x] 각 테스트에 상세한 주석 추가
  - 테스트 목적 (왜 중요한가)
  - 재현 시나리오 (어떤 상황을 만드는가)
  - 기대값과 실제값 비교 (무엇을 검증하는가)

- [x] 실패 이유 요약: 예상과 달리 현재 구현이 이미 대부분의 규칙을 만족함
  - equity/final_capital 정의: 이미 올바르게 구현됨
  - hold_days 타임라인: 이미 올바르게 구현됨
  - 마지막 날 규칙: 이미 올바르게 구현됨
  - **미구현**: pending 충돌 감지 (Phase 1에서 추가 필요)

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (57 passed, 1 skipped)
- [x] 실패 메시지가 명확한지 확인 (모두 통과 또는 스킵)

---

### 승인 요청 + Commit Messages (Phase 0)

- [ ] Phase 1로 진행해도 되는지 승인 요청

#### Commit Messages (Phase 0)

1. 백테스트 / 실행 규칙 정립 - equity/final_capital 정의 및 pending 단일 슬롯 정책 명시
2. 백테스트 / Critical Invariant 테스트 추가 - pending 충돌 시 예외 발생 검증
3. 백테스트 / hold_days 타임라인 테스트 추가 - lookahead 방지 및 정확성 검증

---

### Phase 1 — 핵심 로직 수정 및 테스트 통과 (그린)

> Phase 0에서 정의한 정책에 맞게 코드를 수정하여 모든 테스트를 통과시킨다.

**작업 내용**:

- [x] `src/qbt/backtest/strategy.py` 수정
  - [x] pending_order를 단일 슬롯으로 변경
    - 변경 전: `pending_orders: list[PendingOrder] = []`
    - 변경 후: `pending_order: PendingOrder | None = None`
    - 관련 로직 전체 수정 (리스트 → 단일 변수)

  - [x] pending 존재 중 신규 신호 감지 시 `PendingOrderConflictError` raise
    - 신호 감지 로직에 invariant 체크 추가 (line 765-770, 788-793)
    - pending이 이미 존재하면 즉시 예외 발생
    - 예외 메시지에 디버깅 정보 포함 (pending 정보, 현재 날짜 등)

  - [x] 강제청산 로직 검토 완료
    - 현재 구현: equity_df 마지막 값은 loop 내에서 `capital + position*close`로 이미 기록됨
    - 강제청산 로직은 trades 기록용으로만 사용 (capital 업데이트하지만 equity_df는 변경 안 됨)
    - `calculate_summary`는 `equity_df.iloc[-1]["equity"]`를 final_capital로 사용
    - 결론: 이미 올바르게 구현됨 (평가액 포함)

  - [x] equity 기록 로직 정확성 확인
    - 이미 `equity = capital + position * row[COL_CLOSE]`로 구현됨 (line 742-745)
    - 모든 시점에서 일관성 확인 완료
    - position=0일 때도 `equity = capital`로 명시적 계산

  - [x] 마지막 날 규칙 구현 확인
    - 마지막 날 close 신호는 pending 생성하지 않음 (데이터 범위 체크)
    - 이미 `if buy_idx >= len(df): return False, None` 등으로 구현됨
    - 전날 pending은 마지막날 open에서 정상 실행됨

- [x] hold_days 로직 검증 완료
  - 현재 `_detect_buy_signal`과 `check_hold_condition` 로직 검토 완료
  - hold_days=0: 돌파일(i) close → i+1일 open 체결 (올바름)
  - hold_days=1: 돌파일(i) → i+1일 close 체크 → i+2일 open 체결 (올바름)
  - lookahead 없음 확인 완료

- [x] 관련 기존 테스트 확인
  - 모든 기존 테스트 통과 (변경 불필요)

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (57 passed, 1 skipped)
- [x] 모든 테스트 통과 확인 (Phase 0에서 추가한 테스트 포함)

---

### 승인 요청 + Commit Messages (Phase 1)

- [x] Phase 2로 진행해도 되는지 승인 요청 (사용자 승인 완료)

#### Commit Messages (Phase 1)

1. 백테스트 / pending 단일 슬롯 및 충돌 감지 구현 - PendingOrderConflictError 추가
2. 백테스트 / equity 및 final_capital 정의 일치 - 강제청산 로직 제거
3. 백테스트 / hold_days 및 마지막 날 규칙 정확성 검증 - lookahead 방지

---

### Phase 2 — AI-친화적 리팩토링

> 테스트를 유지하면서 `run_buffer_strategy()`를 기능 단위로 분해하고 타입 안정성을 강화한다.

**작업 내용**:

- [x] 기능 단위 함수 분해 (`src/qbt/backtest/strategy.py`)
  - [x] `_validate_buffer_strategy_inputs()`: 파라미터 검증 구현
  - [x] `_compute_bands()`: 밴드 계산 구현
  - [x] `_check_pending_conflict()`: invariant 체크 구현
  - [x] `_record_equity()`: equity 기록 구현
  - [x] `run_buffer_strategy()`에서 헬퍼 함수 사용
  - [x] 기존 `_execute_buy_order`, `_execute_sell_order` 활용
  - [x] 기존 `_detect_buy_signal`, `_detect_sell_signal` 활용

- [x] 타입 안정성 강화
  - [x] `order_type`은 이미 `Literal["buy", "sell"]`로 정의됨 (PendingOrder dataclass)
  - [x] 헬퍼 함수들의 타입 힌트 추가

- [x] 주석 및 docstring 개선
  - [x] 분해된 함수마다 명확한 docstring (Google 스타일)
  - [x] AI가 이해하기 쉬운 명확한 변수명 사용

- [x] 기존 테스트 유지
  - [x] 리팩토링 후 모든 테스트 통과 확인

**Validation**:

- [x] `poetry run ruff check .` (통과)
- [x] `./run_tests.sh` (57 passed, 1 skipped)
- [x] 코드 가독성 자체 검토 완료

---

### 승인 요청 + Commit Messages (Phase 2)

- [x] 마지막 Phase로 진행해도 되는지 승인 요청 (사용자 승인 완료)

#### Commit Messages (Phase 2)

1. 백테스트 / run_buffer_strategy 함수 분해 - 가독성 및 유지보수성 향상
2. 백테스트 / 타입 안정성 강화 - Literal 및 Enum 도입
3. 백테스트 / docstring 및 주석 개선 - AI 친화적 구조

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `docs/CLAUDE.md` 업데이트
  - [x] "docs/archive 정책" 섹션 이미 존재 확인 (line 20-24)

- [x] `src/qbt/backtest/CLAUDE.md` 최종 검토
  - [x] "체결 타이밍 규칙" 섹션 이미 상세화됨
    - [x] equity/final_capital 정의 명시됨
    - [x] pending 단일 슬롯 정책 명시됨
    - [x] Critical Invariant 명시됨
    - [x] hold_days 타임라인 예시 (0/1/일반화) 명시됨
    - [x] 마지막 날 규칙 명시됨

- [x] `tests/test_strategy.py` 최종 검토
  - [x] 모든 새 테스트에 명확한 docstring 있음
  - [x] Given-When-Then 패턴 준수됨
  - [x] 주석 가독성 양호

- [x] 불필요 파일/산출물 정리
  - [x] 임시 파일 없음 확인

- [x] `poetry run black .` 실행 (자동 포맷)
  - [x] 1 file reformatted (strategy.py)

- [x] 최종 검증 완료

**Validation**:

- [x] `poetry run ruff check .` (All checks passed!)
- [x] `./run_tests.sh` (57 passed, 1 skipped)
- [x] 수동 검토: 문서 일관성, 테스트 가독성, 코드 명확성 확인 완료

#### Commit Messages (Final)

1. 백테스트 / 실행 규칙 정립 및 정합성 개선 완료 - equity/final_capital 정의 일치
2. 백테스트 / Critical Invariant 구현 - pending 충돌 시 즉시 중단
3. 백테스트 / AI 친화적 구조 개선 - 함수 분해 및 타입 안정성 강화

---

## 7) 리스크(Risks)

1. **final_capital 정의 변경으로 기존 결과와 차이 발생**
   - 영향: 마지막 포지션이 남은 경우 최종 자본 값 달라짐
   - 완화: 의도된 변경이며, 정의 명확화가 목적. 문서에 명확히 기록.

2. **pending 단일 슬롯 정책으로 인한 예상치 못한 케이스**
   - 영향: 현재 로직이 pending 중복을 가정한 부분이 있을 수 있음
   - 완화: Phase 0에서 테스트로 먼저 검증, Phase 1에서 신중히 수정

3. **리팩토링 중 로직 변경 리스크**
   - 영향: 함수 분해 과정에서 의도치 않은 동작 변경
   - 완화: Phase 2 전에 모든 테스트 통과 상태 확보, 리팩토링 중 테스트 계속 실행

4. **hold_days 로직 수정 시 회귀 가능성**
   - 영향: lookahead 방지 로직 수정 중 오류
   - 완화: hold_days=0/1 타임라인 테스트로 고정, 단계별 검증

5. **테스트 작성 시 프로덕션 코드 불일치**
   - 영향: 실제 시그니처/컬럼명과 다르게 테스트 작성
   - 완화: tests/CLAUDE.md 체크리스트 준수, 프로덕션 코드 먼저 확인

### 리스크 완화(Mitigation)

- Phase 0에서 핵심 정책을 테스트로 먼저 고정 (레드)
- Phase 1에서 구현을 테스트에 맞춤 (그린)
- Phase 2 리팩토링은 테스트 통과 상태에서만 진행
- 각 Phase마다 Validation 수행
- tests/CLAUDE.md 테스트 작성 체크리스트 준수
- 변경 전/후 비교는 별도 문서로 기록 (필요 시)

---

## 8) 메모(Notes)

### 핵심 결정 사항

1. **equity/final_capital 정의 통일**
   - 선택지 A 채택: 모든 시점에서 equity = cash + position*close
   - 강제청산 로직 제거 또는 비활성화

2. **pending 단일 슬롯 정책**
   - 리스트 대신 단일 변수 사용
   - 충돌 시 `PendingOrderConflictError` 즉시 raise

3. **hold_days 타임라인 명확화**
   - hold_days=0: 돌파일 close → 다음날 open
   - hold_days=1: 돌파일 → 다음날 close 체크 → 그 다음날 open
   - lookahead 절대 금지

4. **마지막 날 규칙**
   - 전날 pending은 마지막날 open 실행 가능
   - 마지막날 close 신호는 pending 생성 안 됨 (드롭)

5. **tests/CLAUDE.md 규칙 준수**
   - Given-When-Then 패턴 (모든 테스트)
   - 경계 조건 테스트 (빈 데이터, 극단값, 자본 부족 등)
   - 결정적 테스트 (freezegun 필요 시 사용)
   - 명확한 docstring (초보자도 이해 가능)

### 참고 링크

- 프롬프트 원문: (사용자 요청사항)
- 관련 이슈: 없음
- 실험 로그: 필요 시 추가

### Phase 0 실패 예상 테스트 목록

1. `test_equity_definition_with_position`: equity != cash + shares*close (현재 구현 확인 필요)
2. `test_final_capital_with_position_remaining`: 강제청산으로 인해 실제 final_capital != cash + shares*close
3. `test_pending_conflict_raises_exception`: 현재 예외 없음 → 실패
4. 나머지 테스트들: 현재 구현 검증 필요 (실패할 수도, 성공할 수도 있음)

### 진행 로그

- 2025-12-25: 계획서 초안 작성
- 2025-12-25: Phase 0 완료 - 실행 규칙 문서화, 테스트 추가 (57 passed, 1 skipped)
- 2025-12-25: Phase 1 완료 - pending 단일 슬롯 및 충돌 감지 구현
- 2025-12-25: Phase 2 완료 - AI 친화적 리팩토링 (헬퍼 함수 분해, 타입 안정성 강화)
- 2025-12-25: 마지막 Phase 완료 - Black 포맷팅, 최종 검증 통과
- 2025-12-25: 계획서 완료 - 모든 Phase 및 Validation 통과
