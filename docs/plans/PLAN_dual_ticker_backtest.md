# Implementation Plan: 백테스트 듀얼 티커 (QQQ 시그널 + TQQQ 매매)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-16 18:30
**마지막 업데이트**: 2026-02-16 19:05
**관련 범위**: backtest, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] `run_buffer_strategy(signal_df, trade_df, params, ...)` 시그니처로 변경하여 QQQ 시그널 + TQQQ 매매 지원
- [x] `run_buy_and_hold(signal_df, trade_df, params)` 동일하게 변경
- [x] `run_grid_search` 및 `_run_buffer_strategy_for_grid` 듀얼 티커 지원
- [x] 하위 호환 없음: 모든 호출부를 신규 시그니처로 일괄 변경

## 2) 비목표(Non-Goals)

- TQQQ 시뮬레이션 모듈(`src/qbt/tqqq/`) 변경
- 새로운 시그널 로직 추가 (기존 버퍼존 전략 그대로 사용)
- 데이터 로더 변경 (기존 `load_stock_data` 재사용)
- 공통 상수에 TQQQ_SYNTHETIC_PATH 추가 (이미 `tqqq/constants.py`에 존재)
- 백테스트 도메인 CLAUDE.md 업데이트 (별도 plan으로 분리)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 백테스트는 단일 DataFrame(QQQ)에서 시그널 생성과 매매를 모두 수행한다. 사용자는 QQQ 이동평균 시그널로 TQQQ를 매매하는 전략으로 전환하고자 한다.

근거:
- TQQQ(3배 레버리지)의 높은 변동성으로 인해 거짓 신호(false signal)가 빈번함
- QQQ 중심의 시장 참여자 행동을 따라가기 위해 QQQ 시그널 사용
- "Signal on X, Trade on Y" 패턴은 퀀트 투자에서 일반적인 접근법

### 핵심 데이터 흐름 (변경 후)

```
signal_df (QQQ)                    trade_df (TQQQ)
  ├── Close → MA 계산                ├── Open → 매수/매도 체결가
  ├── Close → 밴드 비교              └── Close → 에쿼티 평가
  └── Close → 돌파 감지 (시그널)
```

- 시그널: QQQ 종가 vs QQQ 이동평균 밴드
- 체결: 다음 날 TQQQ 시가 × (1 ± 슬리피지)
- 에쿼티: 현금 + 포지션 수량 × TQQQ 종가

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `run_buffer_strategy(signal_df, trade_df, ...)` 시그니처 변경 완료
- [x] `run_buy_and_hold(signal_df, trade_df, ...)` 시그니처 변경 완료
- [x] `run_grid_search` 듀얼 티커 지원
- [x] signal_df로 시그널 생성, trade_df로 체결/에쿼티 계산 분리 확인
- [x] 기존 체결 타이밍 규칙 유지 (i일 signal_df 종가 시그널 → i+1일 trade_df 시가 체결)
- [x] 기존 테스트 전부 신규 시그니처로 업데이트
- [x] 듀얼 티커 전용 테스트 추가
- [x] 스크립트(`run_single_backtest.py`, `run_grid_search.py`) 업데이트
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=279, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/strategy.py`: `run_buffer_strategy`, `run_buy_and_hold`, `run_grid_search`, `_run_buffer_strategy_for_grid`, `_validate_buffer_strategy_inputs` 시그니처 및 내부 로직 변경
- `src/qbt/backtest/__init__.py`: 변경 없음 (export 인터페이스 동일)
- `src/qbt/common_constants.py`: `TQQQ_SYNTHETIC_DATA_PATH` 상수 추가
- `tests/test_strategy.py`: 모든 테스트 함수의 시그니처 업데이트 + 듀얼 티커 테스트 추가
- `tests/test_integration.py`: `run_buffer_strategy` 호출부 시그니처 업데이트
- `scripts/backtest/run_single_backtest.py`: TQQQ 데이터 로딩 추가, 함수 호출 변경
- `scripts/backtest/run_grid_search.py`: TQQQ 데이터 로딩 추가, 함수 호출 변경

### 데이터/결과 영향

- `storage/results/grid_results.csv`: TQQQ 기준 수익률로 변경됨 (재생성 필요)
- 기존 QQQ 단일 백테스트 결과와 직접 비교 불가 (의도된 변경)

## 6) 단계별 계획(Phases)

### Phase 0 — 듀얼 티커 정책 테스트 (레드)

**작업 내용**:

- [x] `tests/test_strategy.py`에 `TestDualTickerStrategy` 클래스 추가
- [x] 테스트 1: `test_signal_from_signal_df_trade_from_trade_df` — signal_df(QQQ)로 돌파 감지, trade_df(TQQQ) 시가로 체결 확인
- [x] 테스트 2: `test_equity_uses_trade_df_close` — 에쿼티가 trade_df의 종가로 계산되는지 확인
- [x] 테스트 3: `test_buy_and_hold_uses_trade_df` — Buy & Hold가 trade_df의 시가/종가를 사용하는지 확인
- [x] 테스트 4: `test_date_alignment_validation` — signal_df와 trade_df의 날짜 불일치 시 ValueError 발생 확인

---

### Phase 1 — strategy.py 핵심 구현 (그린 유지)

**작업 내용**:

#### 1-1. `run_buffer_strategy` 시그니처 및 내부 로직 변경

- [x] 시그니처: `(signal_df, trade_df, params, log_trades=True)` → signal_df에서 MA/밴드/돌파, trade_df에서 체결/에쿼티
- [x] 날짜 정렬 검증: signal_df와 trade_df의 날짜가 일치하는지 검증 (직접 비교)
- [x] 시그널 관련 변수 (`close`, `prev_close`, `ma_value`, 밴드 계산)는 signal_df에서 추출
- [x] 체결 관련 변수 (`open`, `close` for equity)는 trade_df에서 추출
- [x] `_record_equity`: trade_df의 close로 에쿼티 계산
- [x] `_execute_buy_order`, `_execute_sell_order`: trade_df의 open으로 체결

#### 1-2. `run_buy_and_hold` 시그니처 변경

- [x] 시그니처: `(signal_df, trade_df, params)` → trade_df 기준 매수/매도, signal_df는 미사용 (일관성 유지)
- [x] 첫날 trade_df 시가에 매수, 마지막날 trade_df 종가에 매도
- [x] 에쿼티 계산: trade_df 종가 기준

#### 1-3. `run_grid_search` 및 병렬 처리 변경

- [x] `run_grid_search`: signal_df, trade_df 두 개 받도록 변경
- [x] `_run_buffer_strategy_for_grid`: WORKER_CACHE에서 signal_df, trade_df 모두 조회
- [x] `init_worker_cache` 호출 시 두 DataFrame 모두 캐시

#### 1-4. 기존 테스트 시그니처 업데이트

- [x] `TestRunBuyAndHold`: 모든 테스트에서 `run_buy_and_hold(df, df, params)` 형태로 변경 (동일 df 전달)
- [x] `TestRunBufferStrategy`: 모든 테스트에서 `run_buffer_strategy(df, df, params, ...)` 형태로 변경
- [x] `TestExecutionTiming`: 동일 패턴 적용
- [x] `TestForcedLiquidation`: 동일 패턴 적용
- [x] `TestCoreExecutionRules`: 동일 패턴 적용
- [x] `TestBacktestAccuracy`: 동일 패턴 적용
- [x] `TestRunGridSearch`: signal_df, trade_df 두 개 전달
- [x] `test_integration.py`: `run_buffer_strategy` 호출부 업데이트
- [x] Phase 0 테스트 전부 통과 확인

---

### Phase 2 — 스크립트 업데이트 (그린 유지)

**작업 내용**:

- [x] `src/qbt/common_constants.py`: `TQQQ_SYNTHETIC_DATA_PATH` 상수 추가
- [x] `scripts/backtest/run_single_backtest.py`: TQQQ 데이터 로딩 + 함수 호출 변경
- [x] `scripts/backtest/run_grid_search.py`: TQQQ 데이터 로딩 + 함수 호출 변경

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=279, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / QQQ 시그널 + TQQQ 매매 듀얼 티커 전략 구현
2. 백테스트 / signal_df/trade_df 분리로 듀얼 티커 백테스트 지원
3. 백테스트 / 시그널-매매 분리 아키텍처 도입 (QQQ→TQQQ)
4. 백테스트 / run_buffer_strategy 듀얼 티커 시그니처 변경 및 전체 호출부 업데이트
5. 백테스트 / QQQ 시그널 기반 TQQQ 매매 전략으로 백테스트 엔진 전환

## 7) 리스크(Risks)

- **날짜 정렬 불일치**: QQQ와 TQQQ synthetic의 날짜가 다를 수 있음
  - 완화: 날짜 일치 검증 로직 추가, 불일치 시 ValueError
- **기존 테스트 대량 수정**: 모든 테스트가 시그니처 변경 영향을 받음
  - 완화: 동일 df를 signal_df/trade_df로 모두 전달하면 기존 동작과 동일
- **그리드 서치 병렬 처리**: WORKER_CACHE에 두 개의 DataFrame 저장 필요
  - 완화: 기존 패턴과 동일하게 딕셔너리 키만 추가

## 8) 메모(Notes)

- TQQQ synthetic 데이터의 Open에는 이미 오버나이트 갭이 반영되어 있음 (PLAN_simulate_open_overnight_gap.md 완료)
- 하위 호환 불필요: 외부 소비자 없음, 모든 호출부가 프로젝트 내부
- 단일 종목 백테스트가 필요하면 signal_df와 trade_df에 같은 DataFrame을 전달하면 됨
- `common_constants.py`에 `TQQQ_SYNTHETIC_DATA_PATH` 추가 (백테스트 스크립트에서 사용, 2개 도메인 이상에서 참조)

### 진행 로그 (KST)

- 2026-02-16 18:30: 계획서 초안 작성
- 2026-02-16 19:05: 전체 구현 완료, validate_project.py 통과 (passed=279, failed=0, skipped=0)
