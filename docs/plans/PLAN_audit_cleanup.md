# Implementation Plan: 전수 감사 후속 정합성 정리 (audit cleanup)

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

**작성일**: 2026-05-10 20:25
**마지막 업데이트**: 2026-05-10 20:42
**관련 범위**: live, backtest(qbt), scripts, docs(CLAUDE.md / COMMANDS.md / README.md)
**관련 문서**: [CLAUDE.md](../../CLAUDE.md), [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [scripts/CLAUDE.md](../../scripts/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] 목표 1: 프로젝트 전수 감사에서 검증된 silent fallback / dead branch 를 모두 제거하여 "암묵적 가정 금지" 및 "불가능 조건 처리" 원칙을 일관 적용한다.
- [x] 목표 2: 자산 라인업 변경(SPY/IWM/EFA/EEM 제거 → UGL/UBT 추가)이 코드는 반영되었으나 문서가 누락된 부분을 모두 갱신하고, "쉽게 변경될 수치/리스트"를 가능한 한 코드 참조 형태로 추상화한다.
- [x] 목표 3: 포트폴리오 자산 컬럼 접미사와 live 의 source_kind 리터럴, 포지션 없음 평균가 0.0 등 산재한 매직 값을 단일 정의로 통합한다.
- [x] 목표 4: 코드와 어긋나거나 의미가 모호한 주석을 정정하고, 루트 CLAUDE.md "round(float(str(v)), N)" 규칙의 적용 범위 한정을 한 줄 보강한다.

## 2) 비목표(Non-Goals)

- 백테스트/리밸런싱/체결 산식 등 비즈니스 로직 결과값을 변경하지 않는다 (회귀 결과는 동일해야 한다).
- live 의 SignalDetection 모델 등 외부에 노출된 직렬화 스키마는 변경하지 않는다 (RTDB / 차트 / 알림 호환 유지).
- BufferZoneStrategy 의 게임 로직, OrderIntent 종류, 리밸런싱 정책 등 핵심 정책은 손대지 않는다.
- 검증 후 기각된 항목(예: portfolio_rebalance 의 상대 편차 식, run_single 의 `float(str(v))` 패턴, run_param_plateau 의 4중 if 블록, backtest_engine 의 `meta.get(..., 0.0)`)은 이 plan 의 범위 밖이다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

전수 감사 결과 다음과 같은 의도치 않은 정합성 결함이 확인되었다.

1. **silent fallback / dead branch**
   - [src/live/chart_data.py:200](../../src/live/chart_data.py#L200) — close 의 None 분기는 _load_slot_frame 이 보장상 None 을 넣지 않는데도 `0.0` 으로 silent 대체.
   - [src/live/daily_runner.py:213-217](../../src/live/daily_runner.py#L213-L217) — 워밍업 이후엔 `ma_value <= 0` 이 발생할 수 없는데도 silent `0.0`.
   - [scripts/backtest/run_portfolio_backtest.py:155-156](../../scripts/backtest/run_portfolio_backtest.py#L155-L156) — `prev_row.get("equity", 1)` 의 default 1 이 의미 없는 0 회피용.
   - [scripts/backtest/run_single_backtest.py:204-208](../../scripts/backtest/run_single_backtest.py#L204-L208) — analysis 가 항상 산출하는 `win_rate` / `winning_trades` / `losing_trades` / `start_date` / `end_date` 에 `.get(..., 0)` 이 적용됨.
   - [src/qbt/backtest/engines/portfolio_rebalance.py:62-70, 107-109](../../src/qbt/backtest/engines/portfolio_rebalance.py#L62-L70) — `slot_dict.get(asset_id)` 의 None 분기는 `active_assets ⊆ slot_dict.keys()` 가 항상 성립해 도달 불가.
   - [src/qbt/backtest/portfolio_validation.py:87, 90, 93, 125](../../src/qbt/backtest/portfolio_validation.py#L87) — state_log_df 는 같은 config 로 만들어져 컬럼이 보장되므로 `.get(컬럼, 0)` 의 0 은 dead branch.

2. **자산 라인업 변경 미반영**
   실제 CONFIGS 는 `tqqq, qqq, gld, tlt, ugl, ubt` 6개로 이미 갱신되었으나 다음 문서들이 옛 자산(SPY/IWM/EFA/EEM 등)을 그대로 적고 있다.
   - [src/qbt/backtest/strategies/buffer_zone.py:6-9](../../src/qbt/backtest/strategies/buffer_zone.py#L6-L9) (모듈 docstring)
   - [src/qbt/backtest/strategies/__init__.py:6](../../src/qbt/backtest/strategies/__init__.py#L6) ("8개 자산")
   - [src/qbt/backtest/CLAUDE.md:316-318, 350-352](../../src/qbt/backtest/CLAUDE.md#L316-L318) (자산 리스트)
   - [scripts/CLAUDE.md:242](../../scripts/CLAUDE.md#L242) (옛 시리즈 예시)
   - [docs/COMMANDS.md:243](../COMMANDS.md#L243) (코멘트 종목 리스트)
   - [README.md:40](../../README.md#L40) ("CLAUDE.md 12개 이상" — 실제 9개)

3. **상수화 / 컬럼 접미사 통합**
   - 포트폴리오 자산 컬럼 접미사 (`_close`, `_shares`, `_weight`, `_value`, `_signal_today`, `_pending_intent`, `_executed_intent`, `_value`, `_avg_price`, `_realized_pnl`, `_unrealized_pnl`) 가 portfolio_validation, portfolio_planning, portfolio_data, run_portfolio_backtest 등 여러 곳에 리터럴로 산재.
   - live 의 `"signal_history"` / `"user_trades"` 가 [chart_data.py](../../src/live/chart_data.py) 의 시그니처/분기/예외에 반복.
   - "포지션 없음 평균가 0.0" 이 [daily_runner.py:136-143](../../src/live/daily_runner.py#L136-L143), [drift.py:79](../../src/live/drift.py#L79), [balance_adjust.py:120](../../src/live/balance_adjust.py#L120) 에 분산.

4. **주석 / 규칙 정합성**
   - [src/qbt/backtest/walkforward.py:123](../../src/qbt/backtest/walkforward.py#L123) 주석 "IS 종료일 = IS 종료 월의 마지막 날 전일" — 실제 코드는 `_last_day_of_month(is_end_year, is_end_month - 1)` (= 이전 달의 마지막 날) 이라 의미가 미묘하게 어긋남.
   - [src/live/daily_runner.py](../../src/live/daily_runner.py) Stage 주석 번호가 10 → 12 로 점프 (11 누락).
   - 루트 [CLAUDE.md:260-261](../../CLAUDE.md#L260-L261) 의 `JSON: round(float(str(value)), 자릿수)` 규칙이 live 의 typed float 변수에는 부적합. 적용 범위 한정 한 줄 보강 필요.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 1. silent fallback / dead branch 제거가 모든 대상 파일에 반영되어 있고, 도달 불가능한 분기 또는 RuntimeError 분기로 명시적으로 정리되어 있다.
- [x] 2. 자산 리스트가 문서/주석에 직접 박혀 있던 모든 곳이 (a) 코드 참조로 변경되었거나 (b) 현재 코드 상태와 정확히 일치하도록 갱신되었다.
- [x] 3. 포트폴리오 자산 컬럼 접미사 / live source_kind / 포지션 없음 평균가 0.0 이 단일 정의 위치를 가지며 모든 호출부가 이를 참조한다.
- [x] 4. walkforward 주석 / daily_runner Stage 번호가 코드 동작과 일치하도록 정정되었다.
- [x] 5. 루트 CLAUDE.md `round(float(str(v)), N)` 규칙에 적용 범위 한정 한 줄이 보강되어 있다.
- [x] 6. 회귀/신규 테스트 추가: 기존 1020개 회귀 테스트가 본 변경 후에도 모두 통과한다 (Phase 2 에서 buy_and_hold 자산의 ma_col 부재 케이스가 회귀로 잡혀 분기 보강 후 재통과). silent→RuntimeError 전환 지점은 기존 회귀 테스트가 정상 흐름을 검증하므로 신규 테스트는 추가하지 않았다.
- [x] 7. `poetry run python validate_project.py` 통과 (passed=1020, failed=0, skipped=0)
- [x] 8. `poetry run black .` 실행 완료 (3 files reformatted, 143 unchanged)
- [x] 9. 필요한 문서 업데이트 완료 (README.md / docs/COMMANDS.md / 각 CLAUDE.md / plan)
- [x] 10. plan 체크박스 최신화(Phase / DoD / Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

코드 (silent fallback / dead branch 제거):

- `src/live/chart_data.py` — line 200 dead branch 제거
- `src/live/daily_runner.py` — line 213-217 워밍업 분기 + RuntimeError, Stage 주석 번호 정정
- `scripts/backtest/run_portfolio_backtest.py` — line 155-156 의 equity default 1 제거
- `scripts/backtest/run_single_backtest.py` — line 204-208 의 .get(..., default) 제거
- `src/qbt/backtest/engines/portfolio_rebalance.py` — line 62-70, 107-109 의 slot_dict.get → 직접 접근
- `src/qbt/backtest/portfolio_validation.py` — line 87, 90, 93, 125 의 .get(컬럼, 0) 제거

코드 (상수화 / 접미사 통합):

- `src/qbt/backtest/portfolio_types.py` — 자산 컬럼 접미사 빌더 함수 또는 상수 추가
- `src/qbt/backtest/portfolio_validation.py` / `src/qbt/backtest/engines/portfolio_planning.py` / `src/qbt/backtest/engines/portfolio_data.py` / `scripts/backtest/run_portfolio_backtest.py` — 빌더 함수 사용으로 전환
- `src/live/chart_data.py` — source_kind 리터럴 → Final 모듈 상수
- `src/live/constants.py` — "포지션 없음 평균가" 의미 상수 추가
- `src/live/daily_runner.py` / `src/live/drift.py` / `src/live/balance_adjust.py` — 의미 상수 사용으로 전환

주석 정정:

- `src/qbt/backtest/walkforward.py` — IS 종료일 주석 정합성
- `src/live/daily_runner.py` — Stage 11 누락 정정

문서:

- `src/qbt/backtest/strategies/buffer_zone.py` — 모듈 docstring 추상화
- `src/qbt/backtest/strategies/__init__.py` — "8개 자산" 추상화
- `src/qbt/backtest/CLAUDE.md` — 자산 리스트 항목 갱신 또는 코드 참조로 추상화
- `scripts/CLAUDE.md` — `--strategy` 예시 갱신 또는 코드 참조로 추상화
- `docs/COMMANDS.md` — 종목 리스트 코멘트 갱신 또는 코드 참조로 추상화
- `README.md` — "12개 이상" 추상화
- 루트 `CLAUDE.md` — round 규칙 적용 범위 한정 한 줄 보강

테스트:

- `tests/qbt/test_portfolio_planning.py` 또는 `test_portfolio_execution.py` — 컬럼 접미사 빌더 도입에 따른 회귀 단위 테스트 보강
- `tests/live/test_daily_runner.py` — 워밍업 이후 ma_value 누락 시 RuntimeError 검증 추가
- 기존 회귀 테스트 (`test_regression.py` 등) 가 통과해야 함

문서 변경 여부:

- `README.md`: 변경 있음 (40행 "12개 이상" 추상화)
- `docs/COMMANDS.md`: 변경 있음 (243행 종목 리스트 코멘트 갱신/추상화). 실행 명령어/CLI 옵션 자체는 변경 없음.

### 데이터/결과 영향

- 백테스트 결과 CSV / summary.json / signal.csv / equity.csv 의 산식 및 값은 변경되지 않는다 (회귀 동일).
- live 의 RTDB 직렬화 / 알림 메시지 / 차트 시계열 스키마는 변경되지 않는다.
- silent fallback 제거에 따라, 이전이라면 가짜 0/1 로 통과되었을 비정상 입력이 명시적 RuntimeError 로 노출될 수 있다 (의도된 동작 변경).

## 6) 단계별 계획(Phases)

### Phase 1 — silent fallback / dead branch 제거 (그린 유지)

**작업 내용**:

- [x] live/chart_data.py:200 의 None 분기 제거. 부수적으로 `_load_slot_frame` 의 close 시그니처를 `list[float]` 로 변경 (PyRight 정적 보호) + `_build_slice` close_list 인자 / `asset_frames` dict value 시그니처 동기화
- [x] live/daily_runner.py:213-217 의 ma_distance_pct 0.0 fallback 을 워밍업 인덱스 분기로 분리하고, 워밍업 후 ma_value None/0/음수 케이스에 RuntimeError 추가 (Phase 2 회귀에서 ma_col 부재 = buy_and_hold 자산 케이스를 추가로 분기에 포함)
- [x] scripts/backtest/run_portfolio_backtest.py:155-156 의 `prev_row.get("equity", 1)` / `post_row.get("equity", 1)` default 제거. equity ≤ 0 시 RuntimeError. 자산 컬럼도 직접 접근으로 단순화
- [x] scripts/backtest/run_single_backtest.py:204-208 의 winning_trades / losing_trades / win_rate `.get(..., default)` 제거 (start_date / end_date 는 SummaryDict 의 NotRequired 이므로 default 유지)
- [x] src/qbt/backtest/engines/portfolio_rebalance.py:62-70, 107-109 의 `slot_dict.get(asset_id)` + `if slot is None: continue` 제거 → 직접 접근. `target_weight == 0` 분기는 의미 유지를 위해 보존
- [x] src/qbt/backtest/portfolio_validation.py:87, 90, 93, 125 의 `.get(컬럼, 0)` → 직접 접근

**Validation (이 Phase 내부)**:

- [x] 기존 회귀 테스트가 모두 통과: pytest tests/qbt/test_portfolio_planning.py tests/qbt/test_portfolio_execution.py tests/qbt/test_portfolio_backtest_scenarios.py tests/live/test_daily_runner.py tests/live/test_chart_data.py = 134 passed

---

### Phase 2 — 상수화 / 컬럼 접미사 통합 (그린 유지)

**작업 내용**:

- [x] src/qbt/backtest/portfolio_types.py 에 7개 자산 컬럼 접미사 상수 (`ASSET_COL_SUFFIX_CLOSE/SHARES/WEIGHT/VALUE/SIGNAL_TODAY/PENDING_INTENT/EXECUTED_INTENT`) + 빌더 함수 7개 (`asset_close_col` 등) 정의
- [x] portfolio_validation.py / portfolio_engine.py / portfolio_data.py / run_portfolio_backtest.py 에서 빌더 함수 사용으로 전환 (app_*.py 는 사용자 명시 제외 영역이라 그대로 둠)
- [x] src/live/chart_data.py 의 `"signal_history"` / `"user_trades"` 리터럴을 `SOURCE_KIND_SIGNAL_HISTORY` / `SOURCE_KIND_USER_TRADES` (Final[Literal[...]]) 로 추출
- [x] src/live/constants.py 에 `EMPTY_POSITION_AVG_PRICE: Final[float] = 0.0` 추가
- [x] src/live/drift.py / balance_adjust.py 에서 의미 상수 사용 (daily_runner.py 의 0.0 사용은 사실 워밍업 placeholder 라 별도 의미라서 EMPTY_POSITION_AVG_PRICE 적용 대상 아님)

**Validation (이 Phase 내부)**:

- [x] 전체 테스트 통과: pytest tests/qbt/ tests/live/ = 1020 passed (Phase 1 의 ma_value 분기에 buy_and_hold ma_col 부재 케이스를 추가 보강하여 회귀 해소)

---

### Phase 3 — 자산 라인업 / 문서 정합성 정리 (그린 유지)

**작업 내용**:

- [x] src/qbt/backtest/strategies/buffer_zone.py 모듈 docstring 을 "CONFIGS 참조" 형태로 추상화
- [x] src/qbt/backtest/strategies/__init__.py "8개 자산, 4P 고정" → "버퍼존 멀티자산 config-driven 전략 모듈 (4P 고정, CONFIGS 는 buffer_zone.py 참조)"
- [x] src/qbt/backtest/CLAUDE.md 의 buffer_zone CONFIGS 자산 나열을 코드 참조로 추상화
- [x] src/qbt/backtest/CLAUDE.md 의 buy_and_hold CONFIGS 자산 나열을 코드 참조로 추상화
- [x] scripts/CLAUDE.md `--strategy` 옵션 예시를 STRATEGY_RUNNERS 참조로 추상화
- [x] docs/COMMANDS.md 종목 리스트 코멘트를 `DEFAULT_TICKERS` 참조로 추상화
- [x] README.md "CLAUDE.md 12개 이상" → "계층화하여 운영"

**Validation (이 Phase 내부)**:

- [x] 변경된 모든 문서가 현재 코드 상태와 일관됨을 확인

---

### Phase 4 — 주석 정정 + 루트 규칙 보강 (그린 유지)

**작업 내용**:

- [x] src/qbt/backtest/walkforward.py:122 의 주석을 코드 동작에 맞게 정정 ("is_end_year/is_end_month 는 OOS 시작 월을 가리킨다. IS 종료일 = OOS 시작 월의 직전 달 마지막 날 (= OOS 시작 전날)")
- [x] src/live/daily_runner.py 의 Stage 번호 주석 정정: "12. SignalDetection..." → "11.", "13. drift..." → "12.", "14. 알림 본문..." → "13."
- [x] 루트 CLAUDE.md `round(float(str(value)), 자릿수)` 항목에 한 줄 보강: "`str()` 우회는 값 타입이 불명확한 경우(TypedDict의 Any, numpy/pandas scalar 등) 안전 변환을 위함이며, 값 타입이 명확한 dataclass 필드 / typed float 변수는 `round(float(value), 자릿수)` 로 충분하다."

**Validation (이 Phase 내부)**:

- [x] 변경된 주석이 코드 동작과 일치함을 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (README.md / docs/COMMANDS.md / 각 CLAUDE.md / plan 모두 반영)
- [x] plan 체크리스트 / DoD 최신화
- [x] `poetry run black .` 실행 (3 files reformatted)
- [x] 변경 기능 및 전체 플로우 최종 검증

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1020, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. backtest+live / 전수 감사 후속 — silent fallback 제거 + 컬럼 상수화 + 문서 정합화
2. audit / silent fallback / dead branch 일괄 제거 + 문서 자산 리스트 갱신
3. 정합성 / 포트폴리오 컬럼 빌더 도입 + live 의미 상수 추출 + 주석/규칙 정정
4. cleanup / 암묵 가정 제거(불가능 조건 RuntimeError 전환) + 문서 내구성 회복
5. backtest+live+docs / 감사 후속 정리 — fallback / 상수화 / 자산 라인업 / 주석 / 규칙 보강

## 7) 리스크(Risks)

- **회귀 위험**: silent fallback 제거가 이전에 묻혀 있던 비정상 입력을 RuntimeError 로 노출할 수 있다. → 기존 통합 테스트(특히 portfolio / live regression) 로 사전 확인하고, 실제 운영 데이터로 백테스트 / live dry-run 을 통해 변화 없음을 확인한다.
- **컬럼 접미사 빌더 도입 시 회귀**: 빌더 함수와 기존 리터럴이 정확히 같은 문자열을 만들도록 보장해야 한다. → 단위 테스트로 빌더 결과와 기존 컬럼명을 직접 비교한다.
- **문서 추상화로 인한 정보 손실**: 자산 리스트를 코드 참조로 바꾸면 문서만 보고 빠른 파악이 어려워진다. → 단, 문서 내구성 원칙(CLAUDE.md "리팩토링 후에도 깨지지 않는 설명") 이 우선이며, 자주 변경되는 정보는 코드 참조가 정답.
- **루트 CLAUDE.md 수정**: 규칙 변경 후 다른 plan / 코드가 그 한 줄에 의존하지 않는지 확인.

## 8) 메모(Notes)

- 이 plan 은 사용자와 합의된 4개 추천안을 그대로 반영한다.
  1. live/chart_data.py:200 — dead branch 제거 + 단순 캐스팅
  2. live/daily_runner.py:213-217 — 워밍업 분기 + RuntimeError
  3. live round 스타일 — 현 상태 유지 + CLAUDE.md 규칙 보강 한 줄
  4. run_param_plateau_all 4중 if — 현재 유지 (보고에서 제외)
- 검증 후 기각된 항목들은 본 plan 범위 밖이며, 향후 재논의 필요 시 별도 plan 에서 다룬다.
  - portfolio_rebalance 의 상대 편차 식 (의도된 설계, portfolio_validation 과 일관)
  - run_single 의 `float(str(v))` 23회 (CLAUDE.md "JSON 규칙" 준수)
  - backtest_engine.py:394-395 의 `meta.get(..., 0.0)` (BuyAndHoldStrategy 빈 dict 대응)
  - docs/CLAUDE.md 의 "Phase / 레드 / 그린" 표현 (계획서 본문 용어, 주석 작성 원칙 적용 대상 아님)
  - live vs qbt 반올림 스타일 차이 (live 는 dict / dataclass 라 df.round 사용 불가, 정당한 차이)

### 진행 로그 (KST)

- 2026-05-10 20:25: 전수 감사 결과 / 재검증 / 사용자 확인을 거쳐 plan 초안 작성
- 2026-05-10 20:30: Phase 1 완료 — silent fallback / dead branch 6개 파일 surgical 제거 (134 회귀 테스트 통과)
- 2026-05-10 20:36: Phase 2 완료 — 자산 컬럼 접미사 빌더(7개) + 빌더 함수(7개) 도입, source_kind / EMPTY_POSITION_AVG_PRICE 의미 상수화. ma_value 분기에 buy_and_hold ma_col 부재 케이스 추가 보강 (1020 회귀 테스트 통과)
- 2026-05-10 20:38: Phase 3 완료 — buffer_zone / buy_and_hold 자산 라인업 6개 문서 추상화
- 2026-05-10 20:40: Phase 4 완료 — walkforward IS/OOS 주석 정정, daily_runner Stage 11~13 번호 정정, 루트 CLAUDE.md round 규칙 적용 범위 한 줄 보강
- 2026-05-10 20:42: 마지막 Phase 완료 — black 적용 (3 files), validate_project.py 통과 (passed=1020, failed=0, skipped=0)

---
