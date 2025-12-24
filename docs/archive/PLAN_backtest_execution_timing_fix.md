# Implementation Plan: 백테스트 체결 타이밍 및 정합성 오류 수정

**상태**: ✅ Done
**작성일**: 2024-12-24
**마지막 업데이트**: 2024-12-24
**관련 범위**: backtest, tests
**관련 문서**: src/qbt/backtest/CLAUDE.md, CLAUDE.md

---

## 1) 목표(Goal)

- 백테스트 전략(`run_buffer_strategy`)에서 발견된 3가지 중대 버그를 수정한다
- 체결 타이밍 오류 수정: 신호일과 체결일을 명확히 분리하여 정확한 에쿼티 곡선 생성
- 강제청산 정합성 보장: equity_df 마지막 값과 final_capital이 슬리피지를 반영한 값으로 일치
- 첫 날 에쿼티 누락 해결: 전체 데이터 기간에 대한 완전한 에쿼티 곡선 생성
- 비율 표기 규칙 통일: 코드/주석/문서에서 0~1 비율 표기 일관성 확보
- 회귀 방지 테스트 추가: 버그 재발 방지를 위한 검증 테스트 작성

## 2) 비목표(Non-Goals)

- 전략 로직 자체 변경 (버퍼존, 유지조건, 동적 조정 등)
- 성과 지표 계산 방식 변경
- CLI 스크립트 변경
- 시각화/대시보드 변경

## 3) 배경/맥락(Context)

### 현재 문제

**버그 1: 체결 타이밍 오류** (중대)
- 위치: `src/qbt/backtest/strategy.py` 라인 453-620
- 문제: 신호는 i일 종가로 판단하고, 체결은 i+1일 시가로 실행되어야 하는데, 현재 구현은 포지션/자본/에쿼티를 신호일(i일)에 즉시 반영
- 영향: 신호일~체결일 사이 잘못된 에쿼티 기록 → MDD, CAGR 등 모든 성과 지표 오류 전파

**버그 2: 강제청산 정합성 오류** (중대)
- 위치: `src/qbt/backtest/strategy.py` 라인 626-660
- 문제: 데이터 종료 시 슬리피지를 적용하여 청산하지만, equity_records에 추가하지 않음
- 영향: equity_df 마지막 값과 실제 final_capital이 슬리피지만큼 불일치

**버그 3: 첫 날 에쿼티 누락** (경미)
- 위치: `src/qbt/backtest/strategy.py` 라인 453
- 문제: `range(1, len(df))` 루프로 인해 첫 영업일 에쿼티 미기록
- 영향: 시각화 시 첫 날 데이터 누락

### 영향 받는 불변 규칙

- 백테스트 체결 규칙: "신호 발생 → 유지조건 확인 → 다음 영업일 시가 체결"
- 슬리피지 적용: 매수 +0.3%, 매도 -0.3%
- 비율 표기: 모든 비율 값은 0~1 사이 소수 (0.03 = 3%)

## 4) 완료 조건(Definition of Done)

- [x] 3가지 버그 모두 수정 완료 (체결 타이밍, 강제청산, 첫 날 누락)
- [x] 회귀 테스트 4개 추가 및 통과
- [x] `./run_tests.sh` 통과 (기존 + 신규 테스트)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black --check .` 통과
- [x] 문서 업데이트 (백테스트 CLAUDE.md, 루트 CLAUDE.md)

---

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**핵심 수정**:
- `src/qbt/backtest/strategy.py` (라인 40-676): PendingOrder 데이터클래스 추가, 헬퍼 함수 추가, run_buffer_strategy() 리팩토링
- `tests/test_strategy.py`: 회귀 테스트 추가 (TestExecutionTiming, TestForcedLiquidation 클래스)

**문서 업데이트**:
- `src/qbt/backtest/CLAUDE.md`: 체결 타이밍 규칙 상세 명시
- `CLAUDE.md`: 비율 표기 규칙 추가

**검토 대상**:
- `src/qbt/backtest/analysis.py` (라인 82-157): calculate_summary() 함수가 새 에쿼티 구조를 정확히 처리하는지 확인

### 데이터/결과 영향

- `storage/results/grid_results.csv`: 버그 수정으로 CAGR, MDD 등 지표 변경 (정확도 향상)
- equity_df 구조: 첫 날 행 추가, 마지막 날 슬리피지 반영
- 기존 결과와 비교 불가 → 필요 시 수정 전 결과 백업

---

## 6) 단계별 계획(Phases)

### Phase 1 — 검증 테스트 먼저 작성 (TDD 레드)

**목표**: 버그를 재현하는 실패 테스트 작성

- [x] `tests/test_strategy.py`에 `TestExecutionTiming` 클래스 추가
  - `test_buy_execution_timing_separation()`: 신호일에는 position=0, 체결일부터 position>0
  - `test_sell_execution_timing_separation()`: 매도도 동일 검증
  - `test_first_day_equity_recorded()`: equity_df 길이 = 전체 데이터 길이
- [x] `TestForcedLiquidation` 클래스 추가
  - `test_forced_liquidation_equity_consistency()`: equity_df[-1] == final_capital (슬리피지 반영)

**Validation**

- [x] `./run_tests.sh` 실행 → 새 테스트 실패 확인 (레드)
  - test_buy_execution_timing_separation: FAILED (신호일에 position=94, 기대값=0)
  - test_first_day_equity_recorded: FAILED (equity_df 길이=9, 기대값=10)

---

### Phase 2 — 헬퍼 함수 추가

**목표**: 기존 로직을 건드리지 않고 새 함수 추가

- [x] `src/qbt/backtest/strategy.py` 라인 377 직전에 헬퍼 함수 추가:
  - `_execute_buy_order()`: 매수 주문 실행 (슬리피지 적용, 자본 차감, 포지션 설정)
  - `_execute_sell_order()`: 매도 주문 실행 (슬리피지 적용, 자본 증가, 거래 기록)
  - `_detect_buy_signal()`: 상향돌파 감지 및 유지조건 확인 → 체결일 반환
  - `_detect_sell_signal()`: 하향돌파 감지 → 체결일 반환
- [x] 모든 함수에 타입 힌트 및 Google 스타일 docstring 추가
- [x] `PendingOrder` 데이터클래스 추가
- [x] `from datetime import date` 임포트 추가

**Validation**

- [x] `poetry run ruff check .` - 통과
- [x] `poetry run black --check .` - 통과

---

### Phase 3 — 체결 예약 시스템 도입

**목표**: run_buffer_strategy() 함수를 예약 시스템 사용하도록 재작성

- [x] `PendingOrder` 데이터클래스 추가 (Phase 2에서 완료)
- [x] 초기화 섹션 수정:
  - `pending_orders: list[PendingOrder] = []` 추가
  - 첫 날(i=0) 에쿼티 기록 추가
- [x] 루프 구조 변경:
  - 순서: (1) 예약 주문 실행 → (2) 에쿼티 기록 → (3) 신호 감지 및 주문 예약
  - 매수/매도 신호 감지 시 `_detect_buy_signal()`, `_detect_sell_signal()` 사용
  - pending_orders에 추가만 (즉시 실행 금지)
  - 루프 시작 시 당일 실행 대상 주문 처리 (`_execute_buy_order()`, `_execute_sell_order()` 사용)
- [x] 강제청산 수정:
  - 청산 후 `equity_records[-1]["equity"] = capital` 업데이트
  - `equity_records[-1]["position"] = 0` 설정

**Validation**

- [x] `./run_tests.sh` - 50개 테스트 모두 통과
- [x] Phase 1의 실패 테스트가 통과 (그린):
  - test_buy_execution_timing_separation: PASSED ✅
  - test_first_day_equity_recorded: PASSED ✅

---

### Phase 4 — 비율 표기 규칙 통일

**목표**: 코드 전체에서 0~1 비율 표기 일관성 확보

- [x] 주석 수정:
  - `backtest/constants.py`: `# 버퍼존 기본값 (%)` → `# 버퍼존 비율 (0.03 = 3%)`
  - `tqqq/constants.py`: `# FFR 스프레드 (%)` → `# FFR 스프레드 비율 (0.004 = 0.4%)`
  - `strategy.py` docstring: `(예: 5.0 = 5%)` → `(0.03 = 3%)`

- [x] 잘못된 예시 제거 및 올바른 예시로 교체

**Validation**

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh`

---

### Phase 5 — 문서 업데이트

**목표**: 체결 규칙 문서화 및 비율 표기 규칙 추가

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - "실행 규칙" 섹션에 체결 타이밍 상세 명시
  - 신호 발생 시점 vs 체결 시점 분리 설명
  - 슬리피지 적용 규칙
  - 에쿼티 기록 규칙

- [x] `CLAUDE.md` 업데이트:
  - "코딩 표준" 섹션에 비율 표기 규칙 추가
  - 모든 비율 값은 0~1 사이 소수로 정의
  - 주석 형식: "비율 (0.03 = 3%)"

**Validation**

- [x] 문서 업데이트 완료 확인
- [x] `./run_tests.sh` 최종 통과

---

### Phase 6 — 최종 검증 및 정리

**목표**: 모든 변경 사항 통합 검증 및 계획서 정리

- [x] 전체 품질 게이트 확인:
  - `./run_tests.sh` 전체 통과
  - `poetry run ruff check .` 통과
  - `poetry run black --check .` 통과

- [x] 새 테스트 4개 모두 통과 확인
- [x] 기존 테스트 모두 통과 확인
- [x] 계획서 체크박스 모두 완료 표시

**Validation**

- [x] 완료 조건 6개 항목 모두 충족
- [x] 계획서 상태를 ✅ Done으로 변경

---

## 7) 리스크(Risks)

### 리스크 1: 기존 그리드 서치 결과 변경

**위험**: 수정 후 CAGR, MDD 등 지표가 변경되어 기존 결과와 비교 불가

**완화 전략**:
- 버그 수정으로 인한 정확도 향상임을 문서화
- 필요 시 `storage/results/grid_results_before_fix.csv` 백업
- 변경 전/후 결과를 동일 조건에서 비교하는 테스트 추가 (선택)

### 리스크 2: 회귀 발생

**위험**: 리팩토링 과정에서 새로운 버그 유입

**완화 전략**:
- Phase별로 검증 커맨드 실행
- 기존 테스트가 모두 통과하는지 지속 확인
- TDD 접근 (레드 → 그린 → 리팩토링)
- 각 Phase는 작게 완결되어야 함

### 리스크 3: 성능 저하

**위험**: 예약 시스템 도입으로 루프 복잡도 증가

**완화 전략**:
- pending_orders 리스트 크기는 일반적으로 0~2개 수준 (매수/매도 대기)
- 병렬 실행(`run_grid_search`)에서는 독립적이므로 영향 없음
- 필요 시 성능 테스트 추가 (선택)

---

## 8) 메모(Notes)

### 올바른 체결 규칙 (구현 기준)

```
T일 종가: 신호 감지 (상향돌파/하향돌파)
T+1 ~ T+hold_days일: 유지조건 확인 (종가가 밴드 내부 유지)
T+hold_days+1일 시가: 실제 체결 (포지션/자본 변경)
  - hold_days=0이면 T+1일 시가 체결
```

### 예약 시스템 루프 순서

```python
for i in range(1, len(df)):
    # 1. 예약된 주문 실행 (당일 실행 대상만)
    for order in pending_orders:
        if order.execute_date == current_date:
            # position, capital 업데이트

    # 2. 에쿼티 기록 (주문 실행 후 상태)
    equity_records.append(...)

    # 3. 신호 감지 및 주문 예약 (미래 날짜로)
    if 상향돌파:
        pending_orders.append(PendingOrder(...))
```

### 참고 에이전트 분석

- 탐색 에이전트 1 (a441ef3): 백테스트 전략 구현 분석 완료
- 탐색 에이전트 2 (aa13007): 기존 테스트 구조 분석 완료
- 탐색 에이전트 3 (a59e1ad): 문서 구조 및 규칙 분석 완료
- 계획 에이전트 (ad2c997): 상세 구현 계획 수립 완료
