# Implementation Plan: 포트폴리오 State Log + 검증 테스트 + 디버그 대시보드

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

**작성일**: 2026-04-07 17:30
**마지막 업데이트**: 2026-04-08 09:10
**관련 범위**: backtest (engines, portfolio_types), scripts/backtest, tests
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

- [ ] 포트폴리오 엔진이 매 거래일의 내부 상태(시그널 판정, 주문 의도, 체결 결과)를 state_log_df로 수집하고, CLI에서 `state_log.csv`로 저장한다
- [ ] 5개 정합성 규칙을 자동 검증하는 테스트를 추가한다 (시그널-체결 1일 lag, 리밸런싱 비중, EXIT_ALL 주수 0, 현금 비음수, 에쿼티 등식)
- [ ] 사전 생성된 CSV를 읽어 일별 상태를 시각적으로 탐색하는 디버그 전용 Streamlit 대시보드를 생성한다

## 2) 비목표(Non-Goals)

- 기존 `app_portfolio_backtest.py` 수정 (기존 대시보드는 변경하지 않는다)
- 기존 `execution_comparison.csv` 제거 또는 대체 (역할이 다르므로 공존한다)
- 엔진 비즈니스 로직(시그널/리밸런싱/체결) 변경 (기록만 추가, 동작은 그대로)
- 성능 최적화 (state_log 수집의 오버헤드는 무시할 수준)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

포트폴리오 백테스트가 올바르게 작동하는지 검증하려면 시그널 발생 → 주문 의도 생성 → 익일 체결 → 포지션/비중 변화의 전 과정을 시계열로 추적해야 한다. 현재 equity.csv는 결과(포지션/비중/에쿼티)만 기록하고, 엔진 내부 판단 과정(어떤 시그널이 왜 발생했고, 어떤 intent가 생성되어 익일 어떻게 체결되었는지)은 기록하지 않는다.

핵심 검증 니즈:
- 시그널 발생일과 실제 체결일의 1일 lag가 정확히 지켜지는지
- 리밸런싱 후 비중이 목표 임계값 이내인지
- EXIT_ALL 후 해당 자산 주수가 0인지
- 현금이 음수가 되는 경우가 없는지
- 에쿼티 = 현금 + 자산평가액 합계 등식이 매일 성립하는지

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md` — 엔진 구조, OrderIntent 모델, 체결 흐름
- `scripts/CLAUDE.md` — CLI 계층 규칙, Streamlit 앱 규칙
- `tests/CLAUDE.md` — 테스트 작성 원칙, Given-When-Then, 부동소수점 비교

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] state_log_df가 PortfolioResult에 포함되고, 매 거래일의 시그널/intent/체결/포지션 상태를 기록한다
- [x] `run_portfolio_backtest.py` 실행 시 `state_log.csv`가 실험별 결과 디렉토리에 자동 저장된다
- [x] 5개 정합성 규칙 자동 검증 테스트가 추가되고 전부 통과한다
- [x] `app_portfolio_debug.py`가 state_log.csv + equity.csv를 읽어 일별 탐색 뷰를 제공한다
- [x] `poetry run python validate_project.py` 통과 (passed=488, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(backtest CLAUDE.md, scripts CLAUDE.md)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성:**
- `tests/test_portfolio_state_log.py` — 5개 정합성 규칙 테스트
- `scripts/backtest/app_portfolio_debug.py` — 디버그 전용 Streamlit 대시보드

**수정:**
- `src/qbt/backtest/portfolio_types.py` — PortfolioResult에 `state_log_df` 필드 추가
- `src/qbt/backtest/engines/portfolio_engine.py` — 메인 루프에서 state_log 행 수집, PortfolioResult에 포함
- `scripts/backtest/run_portfolio_backtest.py` — state_log.csv 저장 로직 추가
- `src/qbt/backtest/CLAUDE.md` — state_log 관련 설명 추가

**변경 없음:**
- `README.md`: 변경 없음
- 기존 `app_portfolio_backtest.py`: 변경 없음
- 엔진 비즈니스 로직 파일들(planning, execution, rebalance): 변경 없음

### 데이터/결과 영향

- 기존 출력 파일(equity.csv, trades.csv, signal_*.csv, execution_comparison.csv, summary.json)은 변경 없음
- `state_log.csv`가 각 실험 결과 디렉토리에 추가 생성됨
- PortfolioResult에 state_log_df 필드 추가 (기존 필드에 영향 없음)

---

## state_log.csv 스키마 설계

### 구조: Wide 포맷 (1행 = 1거래일)

기본 컬럼:

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `Date` | date | 거래일 |
| `equity` | int | 당일 합산 에쿼티 (체결 후, 종가 기준) |
| `cash` | int | 당일 현금 잔고 (체결 후) |
| `is_month_start` | bool | 월 첫 거래일 여부 |
| `rebalanced` | bool | 당일 리밸런싱 실행 여부 |
| `rebalance_reason` | str | "monthly" / "daily" / "" |

자산별 동적 컬럼 (`{asset_id}_` 접두사, 자산 수만큼 반복):

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `{aid}_close` | float | 당일 종가 |
| `{aid}_shares` | int | 당일 보유 수량 (체결 후) |
| `{aid}_weight` | float | 당일 실제 비중 (체결 후) |
| `{aid}_signal_today` | str | 당일 종가 기준 시그널 판정 ("buy" / "sell" / "hold") |
| `{aid}_pending_intent` | str | 익일 체결 예정 intent_type ("EXIT_ALL" / "ENTER_TO_TARGET" / "REDUCE_TO_TARGET" / "INCREASE_TO_TARGET" / "") |
| `{aid}_pending_reason` | str | pending intent 생성 사유 (로깅용) |
| `{aid}_pending_delta` | float | pending intent 목표 delta 금액 |
| `{aid}_executed_intent` | str | 당일 체결된 intent_type (전일 pending에서 전달, "" = 미체결) |
| `{aid}_exec_side` | str | "buy" / "sell" / "" |
| `{aid}_exec_shares` | int | 당일 체결 수량 (양수=매수, 양수=매도 — side로 구분) |
| `{aid}_exec_price` | float | 당일 체결 가격 (시가 기준) |

### 행수 예상

5~10년 기준 약 1,250~2,500행 (영업일). 자산 3개 실험 시 컬럼 수: 6(기본) + 12(자산별) × 3 = 42컬럼. 자산 8개: 6 + 12 × 8 = 102컬럼. CSV 파일 크기: 1~5MB 수준으로 부담 없음.

### 수집 위치 (엔진 메인 루프 내)

```
i번째 거래일:
  ┌─ Step A+B: execute_orders(next_day_intents) → exec_result
  │   → 여기서 "당일 체결" 정보 수집 (executed_intent, exec_side, exec_shares, exec_price)
  │
  ├─ Step C: 종가 에쿼티 계산
  │   → 여기서 "기본 컬럼" 수집 (equity, cash, shares, weight, close)
  │
  ├─ Step D: signal → projected → rebalance → merge
  │   → 여기서 "시그널 판정" 수집 (signal_today)
  │   → 여기서 "익일 pending" 수집 (pending_intent, pending_reason, pending_delta)
  │
  └─ state_log_rows.append(row)
```

---

## 5개 정합성 규칙 (자동 검증 테스트)

### 규칙 1: 시그널-체결 1일 lag

state_log에서 i일의 `{aid}_pending_intent != ""`이면, i+1일의 `{aid}_executed_intent`가 동일해야 한다.
(마지막 날의 pending은 체결 기회가 없으므로 제외)

### 규칙 2: 리밸런싱 후 비중 정합성

`rebalanced == True`인 행에서, 보유 중인(shares > 0) 모든 자산의 실제 비중이 목표 비중 대비 합리적 범위 이내여야 한다.
(리밸런싱은 목표에 수렴하지만, 정수 주식 수량 제약과 슬리피지로 인해 정확히 일치하지 않을 수 있다. 실질적 허용 오차는 리밸런싱 임계값보다 작아야 한다.)

### 규칙 3: EXIT_ALL 후 주수 0

state_log에서 `{aid}_executed_intent == "EXIT_ALL"`인 행의 `{aid}_shares`가 0이어야 한다.

### 규칙 4: 현금 비음수

모든 행에서 `cash >= 0`이어야 한다.

### 규칙 5: 에쿼티 등식

모든 행에서 `equity == cash + sum({aid}_shares * {aid}_close)` (부동소수점 허용오차 내).

---

## 6) 단계별 계획(Phases)

### Phase 0 — 스키마 정의 + 정합성 테스트 작성 (레드)

**작업 내용**:

- [ ] `portfolio_types.py`에 `PortfolioResult.state_log_df` 필드 추가 (`pd.DataFrame`, default=빈 DataFrame)
- [ ] `tests/test_portfolio_state_log.py` 신규 생성 — 5개 정합성 규칙 테스트 작성
  - [ ] 테스트용 소규모 시나리오 데이터 구성 (conftest 또는 인라인 fixture)
    - 자산 2~3개, 거래일 20~30일 수준
    - 시그널 발생, 리밸런싱 트리거, EXIT_ALL 이벤트가 포함되는 시나리오
  - [ ] `test_signal_execution_one_day_lag` — 규칙 1 검증
  - [ ] `test_rebalance_weight_consistency` — 규칙 2 검증
  - [ ] `test_exit_all_shares_zero` — 규칙 3 검증
  - [ ] `test_cash_non_negative` — 규칙 4 검증
  - [ ] `test_equity_equation` — 규칙 5 검증
- [ ] Phase 0 시점에서 state_log_df가 비어있으므로 규칙 1~3 테스트는 레드(실패) 상태 허용
  - 규칙 4, 5는 기존 equity_df만으로도 검증 가능하므로 그린 가능

**테스트 접근:**

- 테스트는 실제 `run_portfolio_backtest()` 함수를 소규모 데이터로 호출하여 PortfolioResult를 얻고, 그 안의 state_log_df / equity_df / trades_df를 검증한다.
- conftest에 테스트용 PortfolioConfig + 소규모 CSV fixture를 준비한다.

---

### Phase 1 — 엔진 state_log 수집 + CLI 저장 (그린)

**작업 내용**:

- [ ] `portfolio_engine.py` 메인 루프 수정 — state_log 행 수집
  - [ ] 루프 시작부: 전일 `next_day_intents`에서 당일 체결 정보 추출 (executed_intent, exec_side, exec_shares, exec_price)
  - [ ] Step D 후: signal_intents에서 signal_today 추출, merged_intents에서 pending_intent 추출
  - [ ] 각 루프 끝에서 state_log_row dict 구성 → state_log_rows 리스트에 추가
  - [ ] 루프 종료 후 `pd.DataFrame(state_log_rows)` → PortfolioResult.state_log_df에 할당
- [ ] `run_portfolio_backtest.py`의 `_save_portfolio_results()` 수정
  - [ ] `state_log.csv` 저장 로직 추가 (반올림 규칙 적용: 가격=6자리, 자본금=정수, 비중=4자리)
  - [ ] 메타데이터 output_files에 state_log_csv 경로 추가
- [ ] Phase 0에서 레드였던 규칙 1~3 테스트가 그린으로 전환되는지 확인

---

### Phase 2 — 디버그 Streamlit 대시보드 (그린)

**작업 내용**:

- [ ] `scripts/backtest/app_portfolio_debug.py` 신규 생성
- [ ] 데이터 로딩: state_log.csv + equity.csv + trades.csv + signal_*.csv (사전 생성된 CSV 읽기만, 연산 최소화)
- [ ] 실험 선택 UI (단일 실험 선택)
- [ ] 핵심 뷰 1: **일별 상태 네비게이터**
  - [ ] select_slider로 거래일 이동
  - [ ] 선택한 날짜의 state_log 행을 가독성 좋게 표시
    - 기본 정보: 날짜, 에쿼티, 현금, 리밸런싱 여부
    - 자산별 카드: 시그널 판정, 체결 내용, 보유 수량, 비중
    - 익일 예정: pending intent 요약
- [ ] 핵심 뷰 2: **동기화 시계열 차트**
  - [ ] Plotly 서브플롯 4행 구성:
    - (1) 에쿼티 곡선 + 리밸런싱 마커
    - (2) 자산별 비중 추이 (목표비중 수평선)
    - (3) 현금 잔고 추이
    - (4) 자산별 주수 변동 (체결일 강조)
  - [ ] 공유 x축으로 날짜 동기화, 클릭/줌 연동
- [ ] 핵심 뷰 3: **체결 상세 테이블**
  - [ ] state_log에서 체결 발생일(`{aid}_executed_intent != ""`)만 필터링
  - [ ] 컬럼: 날짜, 자산, 체결유형, 체결방향, 체결수량, 체결가격, 전후 주수, 전후 비중, 사유
- [ ] 핵심 뷰 4: **시그널-체결 추적 뷰**
  - [ ] state_log에서 시그널 발생일 + 다음날 체결을 쌍으로 표시
  - [ ] "시그널 발생 → 익일 체결" 매칭 여부를 시각적으로 확인
- [ ] width 파라미터: `width="stretch"` 사용 (`use_container_width` 사용 금지)

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트 — state_log_df 설명, 컬럼 명세 추가
- [ ] `scripts/CLAUDE.md` 업데이트 — app_portfolio_debug.py 설명 추가
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 / 일별 State Log 수집 + 정합성 자동 검증 테스트 + 디버그 대시보드 추가
2. 포트폴리오 / 매수매도 검증용 state_log.csv 생성 및 디버그 시각화 앱 신규 생성
3. 포트폴리오 / 엔진 내부 상태 기록(state_log) + 5개 정합성 규칙 자동 테스트 추가
4. 포트폴리오 / 시그널-체결 추적용 State Log + 검증 테스트 + 디버그 Streamlit 앱
5. 포트폴리오 / day-by-day state log 기반 백테스트 정합성 검증 체계 구축

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| state_log 수집으로 엔진 메인 루프 복잡도 증가 | state_log 행 구성은 루프 끝에서 dict append만 수행. 기존 비즈니스 로직 변경 없음 |
| PortfolioResult에 필드 추가 시 기존 코드 영향 | default=빈 DataFrame으로 하위 호환 보장 |
| 테스트용 소규모 시나리오에서 엣지케이스 미포함 | 시그널/리밸런싱/EXIT_ALL이 모두 발생하는 시나리오를 의도적으로 설계 |
| 디버그 앱 컬럼 수가 자산 수에 따라 가변적 | 자산별 컬럼을 동적으로 탐지하는 헬퍼 함수 사용 |

## 8) 메모(Notes)

### 핵심 결정 사항

- state_log.csv는 매 거래일 전체 기록 (이벤트 발생일만이 아님) — "시계열을 쭉 보며 추적" 목적
- 기존 execution_comparison.csv와 공존 — 역할 분리 (체결 전후 스냅샷 vs 매일 전체 상태)
- state_log.csv는 `run_portfolio_backtest.py` 실행 시 항상 생성 — 파일 크기 부담 없음
- 디버그 앱은 CSV 읽기 전용 — 앱 내 연산 최소화

### state_log 수집 시 엔진 코드 변경 최소화 전략

엔진 메인 루프(`portfolio_engine.py:260-358`)에서:
1. 루프 시작: `next_day_intents` (전일 생성)에서 당일 체결 정보 → `executed_info` dict
2. Step A+B 후: `exec_result.new_trades`에서 체결 수량/가격 추출
3. Step D 후: `signal_intents`, `merged_intents`에서 시그널/pending 정보 추출
4. 루프 끝: 위 정보 + equity/cash/shares/weight를 한 dict로 구성 → state_log_rows.append

기존 변수를 읽기만 하고 새 변수를 추가하지 않으므로 비즈니스 로직에 영향 없음.

### 진행 로그 (KST)

- 2026-04-07 17:30: 계획서 초안 작성 (Draft)
- 2026-04-08 09:10: 전체 Phase 0~3 완료, validate_project.py 통과 (passed=488, failed=0, skipped=0)

---
