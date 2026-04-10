# Implementation Plan: 포트폴리오 보유 현황 파생 컬럼을 엔진에서 계산 (A안)

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

**작성일**: 2026-04-10 11:10
**마지막 업데이트**: 2026-04-10 11:25
**관련 범위**: backtest, scripts, tests
**관련 문서**: 루트 CLAUDE.md, src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [x] `app_portfolio_backtest.py`의 보유 현황 섹션이 직접 수행하던 파생 계산(현재가, 자산별 수익률, 누적 손익, 누적 수익률)을 **포트폴리오 엔진**으로 이전한다.
- [x] 새 파생 컬럼 4종을 `equity_df`에 추가하여 단일 진실 공급원(SSoT)을 확립한다:
  - `{asset_id}_current_price`: shares > 0이면 `value / shares`, 아니면 0.0
  - `{asset_id}_return_pct`: avg_price > 0 and shares > 0이면 `(current_price / avg_price - 1) * 100`, 아니면 0.0
  - `total_pnl`: `equity - initial_capital`
  - `total_return_pct`: `(total_pnl / initial_capital) * 100`
- [x] `app_portfolio_backtest.py`의 보유 현황 렌더링은 새 컬럼을 단순히 읽는 형태로 단순화한다 (CLI 계층의 도메인 로직 침범 해소).
- [x] 새 컬럼이 회귀 테스트로 고정되고, 도메인 문서 및 portfolio_types.py의 컬럼 목록이 갱신된다.

## 2) 비목표(Non-Goals)

- 다른 앱(`app_portfolio_debug.py`, `app_single_backtest.py` 등)의 리팩토링은 본 plan 범위 밖이다.
- `equity_df` 외 다른 결과 객체(`summary.json`, `trades.csv`, `signal_*.csv`)의 스키마 변경 없음.
- 새 컬럼 도입 외에 기존 컬럼의 의미/값 변경 없음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `scripts/backtest/app_portfolio_backtest.py:_render_holdings_section()`이 다음 도메인 계산을 직접 수행한다:
  - `current_price = value / shares if shares > 0 else 0.0`
  - `asset_return_pct = ((current_price / avg_price - 1) * 100) if avg_price > 0 and shares > 0 else 0.0`
  - `total_pnl = total_equity - initial_capital`
  - `total_return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0`
- `scripts/CLAUDE.md` 규칙: "CLI 계층에 도메인 로직 포함 금지, 단순히 비즈니스 로직 호출만 담당".
- 이전 분석에서 사용자는 **A안**(`portfolio_engine.py`의 equity_df 빌드 단계에서 컬럼 보강)을 명시적으로 선택했다. 이로써 데이터 SSoT가 엔진/CSV에 위치하게 되고, 향후 다른 앱(`app_portfolio_debug` 등)도 동일 컬럼을 재사용할 수 있다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` (특히 "비율 표기 규칙", "출력 데이터 반올림 규칙", "데이터 불변성", "내부 불변조건 처리")
- `src/qbt/backtest/CLAUDE.md` (특히 `equity_df 컬럼` 정의, Equity/Final Capital 정의)
- `scripts/CLAUDE.md` (CLI 계층 책임 분리)
- `tests/CLAUDE.md` (Given-When-Then, 부동소수점 비교, 픽스처 사용)

## 4) 완료 조건(Definition of Done)

- [x] `build_combined_equity` (또는 그에 준하는 단계)에서 4종 파생 컬럼이 추가되며, 모든 자산에 대해 일관된 규칙으로 채워진다.
- [x] `equity_df`에 다음 컬럼이 존재함을 회귀 테스트로 고정:
  - `{asset_id}_current_price`, `{asset_id}_return_pct`
  - `total_pnl`, `total_return_pct`
- [x] `app_portfolio_backtest.py`가 4종 파생값을 엔진 컬럼에서 직접 읽으며, 함수 본문에서 동일한 계산을 수행하지 않는다.
- [x] `src/qbt/backtest/portfolio_types.py` 및 `src/qbt/backtest/CLAUDE.md`의 `equity_df` 컬럼 목록이 새 컬럼을 반영한다.
- [x] `poetry run python validate_project.py` 통과 (passed=507, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] README.md 변경 여부 명시: **변경 없음**
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/engines/portfolio_data.py` — `build_combined_equity`에 파생 컬럼 추가 로직 삽입 (또는 신규 헬퍼 함수 분리)
- `src/qbt/backtest/CLAUDE.md` — `equity_df 컬럼` 목록에 새 4종 컬럼 추가, 정의 규칙 명시
- `scripts/backtest/app_portfolio_backtest.py` — `_render_holdings_section()`에서 파생 계산 제거, 새 컬럼 직접 사용
- `tests/test_portfolio_backtest_scenarios.py` 또는 `tests/test_portfolio_state_log.py` — 4종 파생 컬럼 회귀 테스트 추가 (혹은 별도 테스트 파일)
- `README.md`: 변경 없음

### 데이터/결과 영향

- `equity_df` (그리고 `equity.csv`) 스키마에 4종 컬럼이 새로 추가된다 (기존 컬럼은 변경 없음).
- 기존 `equity.csv`를 읽는 외부 도구가 없거나 컬럼 추가에 robust 해야 한다 (현 시점 외부 사용 없음).
- 기존 산식·체결·리밸런싱 로직 변경 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트 회귀 테스트 작성 (레드)

**작업 내용**:

- [x] 새 회귀 테스트 (`tests/test_portfolio_backtest_scenarios.py::TestPortfolioHoldingViewColumns`)에서 다음 계약을 검증:
  - 포트폴리오 백테스트 실행 후 `result.equity_df`에 `{aid}_current_price`, `{aid}_return_pct`가 모든 자산에 대해 존재
  - `total_pnl`, `total_return_pct` 컬럼 존재
  - 임의의 행에 대해 다음 등식이 성립:
    - `current_price * shares == value` (shares > 0인 행)
    - `(current_price / avg_price - 1) * 100 == return_pct` (avg_price > 0 and shares > 0)
    - `equity - initial_capital == total_pnl`
    - `(total_pnl / initial_capital) * 100 == total_return_pct`
  - shares == 0 케이스에서는 `current_price`/`return_pct`가 0.0인지 검증
- [x] 새 테스트는 의도적으로 실패(레드) 상태로 둔다.

---

### Phase 1 — 엔진 측 파생 컬럼 추가 (그린 전환)

**작업 내용**:

- [x] `src/qbt/backtest/engines/portfolio_data.py`의 `build_combined_equity`에 보조 함수 `_attach_holding_view_columns`를 분리하여 4종 파생 컬럼을 in-place로 추가
  - 자산 식별: `{aid}_shares` 컬럼 접두사 기반
  - `{aid}_current_price`, `{aid}_return_pct`, `total_pnl`, `total_return_pct` 산출
- [x] `initial_capital <= 0` 가드를 `build_combined_equity` 진입부에 추가 (입력 검증)
- [x] 데이터 불변성: pandas 벡터 연산으로 처리하며 원본 입력 인자(`equity_rows`)는 변경하지 않는다.

---

### Phase 2 — app_portfolio_backtest 단순화

**작업 내용**:

- [x] `scripts/backtest/app_portfolio_backtest.py`의 `_render_holdings_section()`에서:
  - `current_price = value / shares if shares > 0 else 0.0` 라인을 `current_price = float(row.get(f"{asset_id}_current_price", 0.0))`로 교체
  - `asset_return_pct = ((current_price / avg_price - 1) * 100) ...` 라인을 `asset_return_pct = float(row.get(f"{asset_id}_return_pct", 0.0))`로 교체
  - `total_pnl`/`total_return_pct`도 row에서 직접 읽도록 교체
- [x] 새 컬럼 부재 시 fallback 없이 직접 컬럼 접근 — 사용자가 run_portfolio_backtest.py를 재실행하여 최신 스키마로 갱신해야 한다 (fail-fast 정책 일관성).

---

### Phase 3 — 도메인 문서 갱신

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`의 `equity_df 컬럼` 항목에 4종 컬럼 추가 + 정의 규칙 명시
- [x] `src/qbt/backtest/portfolio_types.py`의 `PortfolioResult` docstring에 새 컬럼 4종 + 기타 누락 컬럼들 반영

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 확인 (README.md 변경 없음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=507, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 보유 현황 파생 컬럼을 엔진에서 계산 (current_price/return_pct/total_pnl)
2. 포트폴리오 / app 도메인 로직 분리 — equity_df에 파생 컬럼 4종 추가
3. 백테스트 / equity_df 파생 뷰 컬럼 추가 + app_portfolio_backtest 단순화
4. 포트폴리오 / 보유 현황 SSoT을 엔진으로 이전 (CLI 계층 도메인 분리)
5. 백테스트 / portfolio_engine equity_df 파생 컬럼 + 회귀 테스트

## 7) 리스크(Risks)

- 새 컬럼 추가로 `equity.csv` 파일 크기가 약간 증가 (자산당 2개 + 총 2개) — 무시 가능 수준
- 기존 결과 CSV를 다시 읽어야 하는 경우 새 컬럼이 없어 KeyError가 날 수 있음 → app에서 `row.get(..., 0.0)`로 fallback 처리
- 부동소수점 차이로 인해 새 회귀 테스트에서 `pytest.approx`를 사용해야 함 (가격 abs=0.01, % abs=0.1)

## 8) 메모(Notes)

- 본 plan은 사용자가 명시적으로 선택한 **A안**에 해당한다 (B안: 새 portfolio_views.py 모듈 생성은 채택하지 않음).
- `app_portfolio_debug.py`도 동일 컬럼을 재사용할 수 있으나, 본 plan은 범위 최소화를 위해 `app_portfolio_backtest.py`만 수정한다. 후속 plan에서 다른 앱들에 동일하게 적용하는 것을 권장.

### 진행 로그 (KST)

- 2026-04-10 11:10: Plan 작성
- 2026-04-10 11:15: Phase 0 회귀 테스트 4건 추가 (TestPortfolioHoldingViewColumns)
- 2026-04-10 11:18: Phase 1 build_combined_equity에 _attach_holding_view_columns 보조 함수 추가, 4종 파생 컬럼 산출
- 2026-04-10 11:20: Phase 2 app_portfolio_backtest 보유 현황 섹션의 도메인 계산 제거
- 2026-04-10 11:22: Phase 3 도메인 문서(CLAUDE.md, portfolio_types.py docstring) 갱신
- 2026-04-10 11:25: 마지막 Phase 완료 — black + validate_project 통과 (passed=507, failed=0, skipped=0)

---
