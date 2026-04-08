# Implementation Plan: 백테스트 / 상수화 및 리터럴 정리

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

**작성일**: 2026-04-08 15:00
**마지막 업데이트**: 2026-04-08 15:00
**관련 범위**: backtest, scripts, common_constants
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] 반복 사용 컬럼명 리터럴을 COL_* 상수로 정의하고 전환
- [ ] run_walkforward.py의 반올림 매직넘버를 ROUND_* 상수로 전환
- [ ] run_walkforward.py의 OHLC 리터럴을 COL_* 상수로 전환
- [ ] walkforward.py의 ma_type="ema" 리터럴을 DEFAULT_BUFFER_MA_TYPE 상수로 전환
- [ ] analysis.py의 COL_EQUITY 리터럴 혼용 수정

## 2) 비목표(Non-Goals)

- TypedDict 키의 상수 전환 (Python 문법상 불가)
- engine_common.py의 TypedDict 정의 자체 변경
- 비즈니스 로직 변경 (동작 동일 유지)
- intent_type 값 (`"EXIT_ALL"` 등)의 상수화 (enum화는 별도 작업)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

리팩토링 후 핵심 컬럼명(`COL_EQUITY`, `COL_ENTRY_DATE` 등)은 상수화되었으나, TradeRecord 관련 키(`"entry_price"`, `"buy_buffer_pct"` 등)가 여전히 리터럴로 반복 사용됨. 특히 `"buy_buffer_pct"`는 5개 파일에서 반복되어 오타 위험이 높다. 또한 `run_walkforward.py`에서 반올림 상수(`ROUND_PRICE` 등)와 COL_* 상수가 정의되어 있는데도 리터럴을 사용하여 같은 계층의 다른 스크립트와 불일치.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트) — 상수 관리 3계층, 상수 명명 규칙
- `src/qbt/backtest/CLAUDE.md` — 백테스트 도메인 상수 및 컬럼 규칙
- `scripts/CLAUDE.md` — CLI 계층 규칙
- `tests/CLAUDE.md` — 테스트 규칙

## 4) 완료 조건(Definition of Done)

- [x] `constants.py`에 새 COL_* 상수 정의 완료
- [x] 리터럴 사용 파일에서 COL_* 상수로 전환 완료
- [x] run_walkforward.py의 반올림 매직넘버 전환 완료
- [x] walkforward.py의 ma_type 리터럴 전환 완료
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/constants.py` — COL_* 상수 추가
- `src/qbt/backtest/csv_export.py` — 리터럴 → 상수 전환
- `src/qbt/backtest/engines/portfolio_execution.py` — 리터럴 → 상수 전환
- `src/qbt/backtest/analysis.py` — COL_EQUITY 리터럴 수정, 반올림 리터럴 수정
- `src/qbt/backtest/walkforward.py` — ma_type 리터럴 전환, 리터럴 컬럼명 전환
- `src/qbt/backtest/runners.py` — 리터럴 → 상수 전환
- `scripts/backtest/run_walkforward.py` — 반올림 매직넘버 + OHLC/COL 리터럴 전환
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 스키마 변경 없음 (상수값 = 기존 리터럴값)
- 동작 완전 동일

## 6) 단계별 계획(Phases)

### Phase 1 — constants.py에 COL_* 상수 추가

**작업 내용**:

- [ ] `constants.py`에 다음 COL_* 상수 추가 (2개 이상 파일에서 사용되는 것):
  - `COL_ENTRY_PRICE = "entry_price"`
  - `COL_EXIT_PRICE = "exit_price"`
  - `COL_SHARES = "shares"`
  - `COL_PNL_PCT = "pnl_pct"`
  - `COL_BUY_BUFFER_PCT = "buy_buffer_pct"`
  - `COL_SELL_BUFFER_PCT = "sell_buffer_pct"`
  - `COL_HOLD_DAYS_USED = "hold_days_used"`
  - `COL_HOLDING_DAYS = "holding_days"`
  - `COL_DRAWDOWN_PCT = "drawdown_pct"`
  - `COL_CHANGE_PCT = "change_pct"`
  - `COL_POSITION = "position"`

---

### Phase 2 — 비즈니스 로직 파일의 리터럴 전환

**작업 내용**:

- [ ] `csv_export.py` — `"entry_price"`, `"exit_price"`, `"pnl_pct"`, `"buy_buffer_pct"`, `"holding_days"` → COL_* 상수
- [ ] `portfolio_execution.py` — `"entry_price"`, `"exit_price"`, `"shares"`, `"pnl_pct"`, `"buy_buffer_pct"`, `"hold_days_used"` → COL_* 상수
- [ ] `analysis.py` — `"equity"` 리터럴(243행) → `COL_EQUITY`, `"holding_days"` → `COL_HOLDING_DAYS`, 반올림 리터럴 `2` → `ROUND_PERCENT`
- [ ] `walkforward.py` — `"buy_buffer_pct"`, `"sell_buffer_pct"`, `"drawdown_pct"` → COL_* 상수, `ma_type="ema"` → `DEFAULT_BUFFER_MA_TYPE` (2곳)
- [ ] `runners.py` — `"buy_buffer_pct"`, `"sell_buffer_pct"` → COL_* 상수

---

### Phase 3 — 스크립트 파일의 리터럴 전환

**작업 내용**:

- [ ] `run_walkforward.py` — OHLC 리터럴 → `COL_OPEN`, `COL_HIGH`, `COL_LOW`, `COL_CLOSE`
- [ ] `run_walkforward.py` — 반올림 매직넘버 → `ROUND_PRICE`, `ROUND_PERCENT`, `ROUND_CAPITAL`, `ROUND_RATIO`
- [ ] `run_walkforward.py` — `"equity"`, `"upper_band"`, `"lower_band"`, `"buy_buffer_pct"`, `"sell_buffer_pct"`, `"drawdown_pct"` → COL_* 상수

---

### Phase 4 (마지막) — 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=499, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. 백테스트 / 컬럼명 리터럴 상수화 및 매직넘버 제거
2. 백테스트 / COL_* 상수 추가 및 리터럴 전환 (동작 동일)
3. 백테스트 / 상수 관리 규칙 준수를 위한 리터럴 정리
4. 백테스트 / run_walkforward.py 반올림 상수 전환 + 컬럼명 상수화
5. 백테스트 / TradeRecord 관련 컬럼명 상수화 및 매직넘버 제거

## 7) 리스크(Risks)

- import 추가로 순환 의존성 발생 가능 → constants.py는 순수 상수 파일이므로 위험 없음
- TypedDict 키와 COL_* 상수값 불일치 → 값이 동일하므로 위험 없음

## 8) 메모(Notes)

- TypedDict 키는 Python 문법 제약으로 리터럴 유지 (주석으로 COL_* 대응 관계 명시 불필요 — 이미 동일 값)
- `"asset_id"`, `"trade_type"`, `"rebalance"`, `"signal"` 등 포트폴리오 전용 값은 이번 범위에서 제외 (Plan 2에서 처리)

### 진행 로그 (KST)

- 2026-04-08 15:00: Plan 작성 완료, 구현 시작
