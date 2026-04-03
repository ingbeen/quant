# Implementation Plan: 포트폴리오 보유 상세 대시보드

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

**작성일**: 2026-04-03 21:00
**마지막 업데이트**: 2026-04-03 21:00
**관련 범위**: backtest (engines, scripts)
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

- [ ] 포트폴리오 엔진이 일별 자산별 보유 주수, 평균매수가, 리밸런싱 사유를 equity_df에 기록한다
- [ ] 포트폴리오 trades_df에 체결 전후 주수/비중 정보가 포함된다
- [ ] 대시보드에 5개 신규 섹션 추가: 보유 현황, 체결 전후 비교, 리밸런싱 히스토리, 월별 수익률 히트맵, 자산별 수익 기여도

## 2) 비목표(Non-Goals)

- 포트폴리오 엔진의 핵심 로직(시그널 생성, 체결 순서, 리밸런싱 정책) 변경 없음
- 기존 성과 지표(CAGR, MDD, Calmar) 산출 로직 변경 없음
- 새로운 전략이나 실험 추가 없음
- run_portfolio_backtest.py의 CLI 인터페이스 변경 없음 (--experiment 인자 등)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 대시보드는 에쿼티 곡선/비중 추이/거래 테이블 등 기본 정보만 제공
- 실제 증권앱처럼 "내 보유종목", "체결 전후 비교", "리밸런싱 사유" 등 상세 정보 미제공
- 엔진 내부에서 추적하는 자산별 보유 주수(position), 평균 매수가(entry_price), 리밸런싱 트리거 사유가 CSV에 저장되지 않아 대시보드에서 활용 불가

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인 규칙)
- `scripts/CLAUDE.md` (CLI/대시보드 스크립트 규칙)
- `tests/CLAUDE.md` (테스트 작성 규칙)
- `src/qbt/utils/CLAUDE.md` (유틸리티 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] equity_df에 `{asset_id}_shares`, `{asset_id}_avg_price`, `rebalance_reason` 컬럼 추가
- [ ] PortfolioTradeRecord에 `pre_shares`, `post_shares`, `pre_weight`, `post_weight`, `order_amount` 필드 추가
- [ ] run_portfolio_backtest.py에서 신규 컬럼 CSV 저장 및 반올림 적용
- [ ] 대시보드 신규 섹션 5개 구현 (보유현황, 체결전후비교, 리밸런싱히스토리, 월별수익률, 수익기여도)
- [ ] 기존 테스트 업데이트 (신규 필드 반영)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] 필요한 문서 업데이트
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/engines/engine_common.py` — PortfolioTradeRecord 필드 추가
- `src/qbt/backtest/engines/portfolio_engine.py` — equity_df 행에 shares/avg_price/rebalance_reason 추가
- `src/qbt/backtest/engines/portfolio_execution.py` — trade 생성 시 pre/post 정보 전달
- `scripts/backtest/run_portfolio_backtest.py` — CSV 저장 시 신규 컬럼 반올림 처리
- `scripts/backtest/app_portfolio_backtest.py` — 대시보드 신규 섹션 5개
- `tests/test_portfolio_execution.py` — 신규 필드 검증
- `tests/test_portfolio_backtest_scenarios.py` — 시나리오 테스트에 신규 필드 반영
- `README.md`: 변경 없음

### 데이터/결과 영향

- equity.csv 컬럼 추가: `{asset_id}_shares` (정수), `{asset_id}_avg_price` (소수6자리), `rebalance_reason` (문자열|빈값)
- trades.csv 컬럼 추가: `pre_shares`, `post_shares` (정수), `pre_weight`, `post_weight` (소수4자리), `order_amount` (정수)
- 기존 컬럼의 값/의미 변경 없음
- 기존 결과 CSV와 호환 — 대시보드는 신규 컬럼 미존재 시 graceful fallback

## 6) 단계별 계획(Phases)

### Phase 1 — 엔진 레이어 데이터 확장 (그린 유지)

**작업 내용**:

- [ ] `engine_common.py`: PortfolioTradeRecord에 `pre_shares`, `post_shares`, `pre_weight`, `post_weight`, `order_amount` 필드 추가
- [ ] `portfolio_execution.py`: execute_orders()에서 trade 생성 시 pre/post 주수·비중·체결금액을 계산하여 기록
  - SELL: pre_shares = position(체결 전), post_shares = position - shares_sold
  - BUY: pre_shares = prev_position, post_shares = prev_position + shares
  - pre_weight/post_weight: 체결 전후 해당 자산 금액 / 총 에쿼티
  - order_amount: shares × price (체결 금액)
  - 함수 시그니처에 total_equity 파라미터 추가 (비중 계산용)
- [ ] `portfolio_engine.py`: equity_df 행에 `{asset_id}_shares`, `{asset_id}_avg_price`, `rebalance_reason` 컬럼 추가
  - shares: `asset_states[asset_id].position` (체결 후 값)
  - avg_price: `entry_prices[asset_id]` (0이면 미보유)
  - rebalance_reason: "monthly" / "daily" / 빈 문자열
  - execute_orders() 호출 시 total_equity 전달
- [ ] 기존 테스트 업데이트: 신규 필드가 포함된 PortfolioTradeRecord 검증

---

### Phase 2 — CSV 저장 로직 업데이트 (그린 유지)

**작업 내용**:

- [ ] `run_portfolio_backtest.py` `_save_portfolio_results()` 수정:
  - equity.csv: `{asset_id}_shares` (정수 변환), `{asset_id}_avg_price` (ROUND_PRICE), `rebalance_reason` (문자열)
  - trades.csv: `pre_shares`, `post_shares` (정수), `pre_weight`, `post_weight` (ROUND_RATIO), `order_amount` (ROUND_CAPITAL)
- [ ] summary.json per_asset에 `avg_buy_price`, `current_shares` 추가 (최종일 기준)
- [ ] `_TRADE_COLUMN_RENAME` 딕셔너리에 신규 필드 한글 매핑 추가

---

### Phase 3 — 대시보드 신규 섹션 구현 (그린 유지)

**작업 내용**:

- [ ] 섹션 1 - 포트폴리오 보유 현황 (My Holdings)
  - 날짜 슬라이더로 특정일 선택
  - st.metric 카드: 총 평가금액, 투자금액, 평가손익, 현금 잔고
  - 보유종목 테이블: 종목, 보유수, 평균매수가, 현재가, 평가금액, 비중, 수익률
  - 목표 비중 vs 실제 비중 이중 도넛 차트 (Plotly)
- [ ] 섹션 2 - 체결 전후 비교 (Before/After Execution)
  - 체결 발생일 selectbox
  - 비교 테이블: 종목별 체결전(주수/비중) → 체결후(주수/비중) → 변동(주수/금액)
  - 거래 사유 표시
- [ ] 섹션 3 - 리밸런싱 히스토리 (Rebalancing Log)
  - 리밸런싱 이벤트 타임라인 테이블 (일자, 트리거, 사유)
  - 리밸런싱 빈도 통계
  - 체결 전후 비중 변화 바차트
- [ ] 섹션 4 - 월별 수익률 히트맵 (Monthly Returns)
  - 년도 × 월 매트릭스 (Plotly annotated heatmap)
  - 연간 수익률 합계 행
- [ ] 섹션 5 - 자산별 수익 기여도 (Asset Contribution)
  - 분기별 수익 기여도 스택 바차트
  - 누적 기여도 스택 면적 차트
- [ ] 기존 섹션 개선
  - 거래 내역 테이블: 체결금액, 체결전후 주수 컬럼 추가
  - 비중 추이 차트: 목표 비중 수평선 오버레이 추가
  - 에쿼티 차트: 리밸런싱 마커 hover에 사유 표시
- [ ] graceful fallback: 신규 컬럼 미존재 시 해당 섹션/기능 비활성화 (기존 CSV 호환)

---

### Phase 4 (마지막) — 테스트 업데이트 및 최종 검증

**작업 내용**:

- [ ] 필요한 문서 업데이트 (CLAUDE.md 등)
- [ ] `poetry run black .` 실행
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 대시보드 / 보유 상세·체결전후·리밸런싱 히스토리·월별수익률·기여도 5개 섹션 추가
2. 포트폴리오 / equity_df·trades_df 확장 + 증권앱 스타일 상세 대시보드 구현
3. 포트폴리오 / 엔진 데이터 확장(shares, avg_price, rebalance_reason) + 대시보드 신규 섹션
4. 포트폴리오 대시보드 / 일별 보유현황·체결비교·리밸런싱로그·히트맵·기여도 추가
5. 포트폴리오 / 증권앱 수준 상세 뷰 (엔진 데이터 확장 + 대시보드 5개 섹션)

## 7) 리스크(Risks)

- equity.csv 컬럼 수 증가로 파일 크기 약간 증가 (자산 3개 기준 +6 컬럼 정도, 무시할 수준)
- 기존 CSV 재생성 필요 (run_portfolio_backtest.py 재실행) — 대시보드는 graceful fallback으로 대응
- execute_orders() 시그니처에 total_equity 파라미터 추가 시 기존 테스트 수정 필요

## 8) 메모(Notes)

- execute_orders()에 total_equity를 전달하는 대신, pre_weight/post_weight 계산은 portfolio_engine.py의 메인 루프에서 수행하는 것도 고려했으나, 체결 직전/직후의 정확한 비중을 계산하려면 execute_orders() 내부에서 계산하는 것이 가장 정확
- rebalance_reason은 portfolio_engine.py 메인 루프에서 is_month_start 변수를 활용하여 결정

### 진행 로그 (KST)

- 2026-04-03 21:00: 계획서 작성
