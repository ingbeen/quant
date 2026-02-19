# Implementation Plan: Buy & Hold 마지막날 매도 제거

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

**작성일**: 2026-02-19 23:00
**마지막 업데이트**: 2026-02-19 23:10
**관련 범위**: backtest
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `run_buy_and_hold` 전략에서 마지막날 매도 로직을 제거하여, 버퍼존 전략과 동일하게 "강제청산 없음" 정책을 적용한다
- [x] 핵심 성과 지표(CAGR, MDD, total_return_pct, final_capital)가 변하지 않음을 보장한다
- [x] 관련 테스트를 업데이트하여 새 정책을 반영한다

## 2) 비목표(Non-Goals)

- `run_buy_and_hold`의 반환 타입(`tuple[pd.DataFrame, BuyAndHoldResultDict]`) 변경
- `calculate_summary` 함수 수정
- 버퍼존 전략 코드 수정
- `run_single_backtest.py`의 출력 로직 수정 (trades=0으로 자연스럽게 표시됨)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_buffer_strategy`는 마지막날 강제청산 없음 정책 적용 (line 865: "백테스트 종료 (강제청산 없음)")
- `run_buy_and_hold`는 마지막날 종가에 매도 실행 (lines 467-485) — 두 전략 간 정책 불일치
- Buy & Hold의 의미("매수 후 보유")에도 마지막날 매도는 부자연스러움

### 핵심 안전성 분석

**변하지 않는 지표** (equity_df 기반 산출):

| 항목 | 산출 경로 |
|------|----------|
| `final_capital` | `equity_df.iloc[-1]["equity"]` (analysis.py:125) |
| `total_return_pct` | `final_capital`에서 파생 (analysis.py:127) |
| `cagr` | `final_capital`에서 파생 (analysis.py:136) |
| `mdd` | `equity_df["equity"]`에서 계산 (analysis.py:141-147) |

equity_df는 매도 로직 이전에 계산 완료(strategy.py:461-465)되므로 영향 없음.

**변하는 지표** (trades_df 기반 산출):

| 항목 | 현재 | 변경 후 |
|------|------|---------|
| `total_trades` | 1 | 0 |
| `winning_trades` / `losing_trades` | 0 or 1 | 0 |
| `win_rate` | 값 있음 | 0.0 |

`calculate_summary`는 빈 trades_df를 이미 정상 처리함 (analysis.py:150-158).

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md` — 마지막 날 규칙, Equity 정의, Final Capital 정의
- `tests/CLAUDE.md` — 테스트 작성 원칙, Given-When-Then 패턴

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `run_buy_and_hold`에서 마지막날 매도 로직 제거
- [x] 빈 trades_df로 `calculate_summary` 호출
- [x] 함수 docstring 업데이트
- [x] 깨지는 테스트 2개 수정 (`total_trades == 0`)
- [x] `poetry run python validate_project.py` 통과 (passed=284, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/strategy.py` — `run_buy_and_hold` 함수 수정
- `tests/test_strategy.py` — `TestRunBuyAndHold::test_normal_execution`, `TestDualTickerStrategy::test_buy_and_hold_uses_trade_df` 수정

### 데이터/결과 영향

- 핵심 성과 지표(CAGR, MDD, total_return_pct, final_capital) 변화 없음
- `total_trades`가 1→0으로 변경 (비교 테이블 출력에 반영)
- 기존 저장된 결과 파일은 영향 없음 (Buy & Hold 결과는 파일로 저장되지 않음)

## 6) 단계별 계획(Phases)

### Phase 1 — 코드 수정 및 테스트 업데이트 (그린 유지)

**작업 내용**:

**strategy.py 수정** (`src/qbt/backtest/strategy.py`):

- [x] docstring 업데이트 (line 419): "마지막 날 trade_df 종가에 매도한다" 제거 → "매수 후 보유, 강제청산 없음" 명시
- [x] 매도 로직 제거 (lines 467-470): `sell_price_raw`, `sell_price`, `sell_amount` 변수 삭제
- [x] 거래 내역 생성 제거 (lines 472-485): trades_df 생성 코드 삭제
- [x] 빈 trades_df 생성으로 대체: `trades_df = pd.DataFrame()` (calculate_summary 호출을 위해)

**test_strategy.py 수정** (`tests/test_strategy.py`):

- [x] `TestRunBuyAndHold::test_normal_execution` (line 65): `assert summary["total_trades"] == 1` → `== 0`
- [x] `TestRunBuyAndHold::test_normal_execution` docstring (line 43): "1개 거래 (첫날 매수 → 마지막날 매도)" → "마지막날 매도 없음 (보유 유지)" 반영
- [x] `TestDualTickerStrategy::test_buy_and_hold_uses_trade_df` (line 1457): `assert summary["total_trades"] == 1` → `== 0`
- [x] `TestDualTickerStrategy::test_buy_and_hold_uses_trade_df` docstring: 마지막날 매도 관련 설명 업데이트

---

### 마지막 Phase — 포맷 적용 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Buy & Hold 마지막날 매도 제거 (강제청산 없음 정책 통일)
2. 백테스트 / Buy & Hold 전략 버퍼존과 동일한 종료 정책 적용
3. 백테스트 / Buy & Hold 마지막날 강제청산 제거 및 테스트 반영
4. 백테스트 / run_buy_and_hold 종료 시 포지션 유지로 변경
5. 백테스트 / Buy & Hold 강제청산 없음 정책 적용 (버퍼존 전략과 통일)

## 7) 리스크(Risks)

- **리스크**: `total_trades` 0으로 변경 시 하위 호출자에서 오류 발생 가능
  - **완화**: `calculate_summary`는 빈 trades_df 처리 로직 내장 확인 완료 (analysis.py:150-158)
  - **완화**: `run_single_backtest.py`에서 Buy & Hold 결과는 로그 출력만 사용 (파일 저장 없음)

## 8) 메모(Notes)

- 이전 대화에서 영향 분석 완료: 핵심 성과 지표(CAGR, MDD, total_return_pct, final_capital)는 모두 equity_df 기반 산출이므로 변화 없음
- Buy & Hold의 equity 곡선은 매도 로직 이전에 `capital_after_buy + shares * close`로 계산되어 영향 없음

### 진행 로그 (KST)

- 2026-02-19 23:00: 계획서 작성 (Draft)
- 2026-02-19 23:10: 구현 완료, 검증 통과 (passed=284, failed=0, skipped=0)
