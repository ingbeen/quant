# Implementation Plan: 자산별 수익 기여도 개선 (실현/미실현 손익 기반)

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

**작성일**: 2026-04-03 22:00
**마지막 업데이트**: 2026-04-03 22:30
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

- [x] 포트폴리오 엔진이 일별 자산별 누적 실현손익(`{asset_id}_realized_pnl`)과 미실현손익(`{asset_id}_unrealized_pnl`)을 equity_df에 기록한다
- [x] 대시보드의 "자산별 수익 기여도" 섹션이 누적 실현손익 + 미실현손익 기반으로 자산별 진정한 기여도를 표시한다

## 2) 비목표(Non-Goals)

- 포트폴리오 엔진의 핵심 로직(시그널 생성, 체결 순서, 리밸런싱 정책) 변경 없음
- 기존 equity_df 컬럼(`_value`, `_weight`, `_signal`, `_shares`, `_avg_price`) 의미/계산 변경 없음
- 대시보드의 다른 섹션(보유 현황, 체결 전후 비교, 리밸런싱 히스토리 등) 변경 없음
- 새로운 전략이나 실험 추가 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 "자산별 수익 기여도"는 `{asset_id}_value`(보유수량 x 종가)의 변동분을 분기별/누적으로 표시한다.
그러나 자산이 매도되면 value=0이 되면서 그동안의 실현 수익 기여가 사라진다.
예: QQQ +100만 수익 후 매도 → QQQ value=0 → 기여도 차트에서 +100만→0으로 급락.
실현손익이 cash에 흡수되면서 해당 자산의 기여 이력이 단절되는 구조적 문제.

### 해결 방안

엔진에서 일별로 두 가지 손익을 추적한다:
- **누적 실현손익** (`realized_pnl`): 해당 자산의 모든 과거 거래 pnl 누적합. 매도 후에도 유지.
- **미실현손익** (`unrealized_pnl`): `(종가 - 평균매입가) x 보유수량`. 미보유 시 0.
- **총 기여도** = `realized_pnl + unrealized_pnl`. 매도 후에도 기여 이력이 끊기지 않음.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인 규칙)
- `scripts/CLAUDE.md` (CLI/대시보드 스크립트 규칙)
- `tests/CLAUDE.md` (테스트 작성 규칙)
- `src/qbt/utils/CLAUDE.md` (유틸리티 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] equity_df에 `{asset_id}_realized_pnl`, `{asset_id}_unrealized_pnl` 컬럼 추가
- [x] 누적 실현손익: 해당 자산의 과거 모든 거래 pnl 합산, 매도 후에도 유지
- [x] 미실현손익: (종가 - 평균매입가) x 보유수량, 미보유 시 0
- [x] CSV 저장 시 신규 컬럼 반올림 적용 (ROUND_CAPITAL)
- [x] 대시보드 기여도 섹션이 realized + unrealized 기반으로 동작
- [x] 기존 테스트 그린 유지 + 신규 컬럼 검증 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/engines/portfolio_engine.py` — equity_df 행에 `_realized_pnl`, `_unrealized_pnl` 컬럼 추가
- `scripts/backtest/run_portfolio_backtest.py` — CSV 저장 시 신규 컬럼 반올림/정수 변환
- `scripts/backtest/app_portfolio_backtest.py` — `_render_contribution_section()` 교체
- `tests/test_portfolio_backtest_scenarios.py` — 신규 컬럼 검증 테스트 추가
- `src/qbt/backtest/CLAUDE.md` — equity_df 컬럼 명세 업데이트
- `README.md`: 변경 없음

### 데이터/결과 영향

- equity.csv 컬럼 추가: `{asset_id}_realized_pnl` (정수), `{asset_id}_unrealized_pnl` (정수)
- 기존 컬럼의 값/의미 변경 없음
- 기존 결과 CSV와 호환 — 대시보드는 신규 컬럼 미존재 시 graceful fallback

## 6) 단계별 계획(Phases)

### Phase 1 — 엔진 레이어: realized/unrealized PnL 컬럼 추가 (그린 유지)

**작업 내용**:

- [x] `portfolio_engine.py`: 메인 루프 초기화부에 `cumulative_realized_pnl` 딕셔너리 추가 (자산별 0.0 초기화)
- [x] 메인 루프 Step A+B 이후, `exec_result.new_trades`의 pnl을 `cumulative_realized_pnl`에 누적
- [x] 메인 루프 Step E에서 자산별 2개 컬럼 추가:
  - `{asset_id}_realized_pnl`: `cumulative_realized_pnl[asset_id]`
  - `{asset_id}_unrealized_pnl`: `(close - avg_price) * shares` (shares=0이면 0)

---

### Phase 2 — CSV 저장 로직 업데이트 (그린 유지)

**작업 내용**:

- [x] `run_portfolio_backtest.py` `_save_portfolio_results()`:
  - equity_round에 `_realized_pnl` → ROUND_CAPITAL, `_unrealized_pnl` → ROUND_CAPITAL 추가
  - int 변환 목록에 `_realized_pnl`, `_unrealized_pnl` 추가

---

### Phase 3 — 대시보드 기여도 섹션 교체 (그린 유지)

**작업 내용**:

- [x] `_render_contribution_section()` 교체:
  - 데이터 소스: `{asset_id}_realized_pnl` + `{asset_id}_unrealized_pnl`
  - 총 기여도 = realized + unrealized
  - 분기별 기여도 스택 바차트: 분기별 총 기여도 diff
  - 누적 기여도 면적 차트: 일별 총 기여도 스택
- [x] graceful fallback: `_realized_pnl` 컬럼 미존재 시 기존 방식(value 기반) 유지

---

### Phase 4 (마지막) — 테스트 + 문서 + 최종 검증

**작업 내용**:

- [x] `test_portfolio_backtest_scenarios.py`에 신규 컬럼 검증 테스트 추가:
  - equity_df에 `_realized_pnl`, `_unrealized_pnl` 컬럼 존재 확인
  - 매도 후 realized_pnl > 0 유지, unrealized_pnl = 0 확인
  - realized_pnl + unrealized_pnl이 자산별 진정한 기여도 반영 확인
- [x] `src/qbt/backtest/CLAUDE.md` equity_df 컬럼 명세에 신규 컬럼 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=483, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 자산별 수익 기여도를 실현+미실현 손익 기반으로 개선 (엔진 컬럼 추가 + 대시보드 교체)
2. 포트폴리오 / equity_df에 realized/unrealized PnL 컬럼 추가 + 기여도 차트 교체
3. 포트폴리오 / 매도 후 기여 이력 단절 문제 해결 (realized+unrealized PnL 추적)
4. 백테스트 / 자산별 누적 실현손익·미실현손익 추적 + 대시보드 기여도 섹션 리뉴얼
5. 포트폴리오 엔진 / 자산별 PnL 컬럼 추가 및 수익 기여도 시각화 개선

## 7) 리스크(Risks)

- equity.csv 컬럼 수 소폭 증가 (자산 3개 기준 +6 컬럼, 무시할 수준)
- 기존 CSV 재생성 필요 (run_portfolio_backtest.py 재실행) — 대시보드는 graceful fallback으로 대응
- 부동소수점 누적 오차 — ROUND_CAPITAL로 정수 저장하므로 무시할 수준

## 8) 메모(Notes)

- 대안(A안: 대시보드에서만 계산) 대비 B안(엔진 컬럼 추가)을 선택한 이유:
  - equity.csv에 저장되어 재사용 가능
  - 대시보드 로직이 단순해짐
  - 다른 분석 도구에서도 활용 가능
- unrealized_pnl 계산: `(close - avg_price) * shares`에서 shares=0이면 자동으로 0
  - avg_price=0일 때 shares=0이므로 별도 예외 처리 불필요

### 진행 로그 (KST)

- 2026-04-03 22:00: 계획서 작성
- 2026-04-03 22:30: 전체 구현 완료 (Phase 1~4), validate_project.py 통과 (passed=483, failed=0, skipped=0)
