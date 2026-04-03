# Implementation Plan: 포트폴리오 대시보드 보유현황/체결비교 UX 개선

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
**관련 범위**: scripts/backtest (대시보드 앱, 포트폴리오 백테스트 실행)
**관련 문서**: `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] 포트폴리오 보유 현황: 거래일만 선택 가능하도록 `st.slider` → `st.select_slider` 변경
- [x] 포트폴리오 보유 현황: `@st.fragment`로 섹션 격리하여 위젯 변경 시 해당 섹션만 재렌더링 (성능 개선)
- [x] 체결 전후 비교: `run_portfolio_backtest.py`에서 `execution_comparison.csv` 사전 생성
- [x] 체결 전후 비교: 대시보드에서 selectbox 대신 긴 표 형태로 표시 (기본 숨김)

## 2) 비목표(Non-Goals)

- equity.csv 스키마 변경
- 다른 섹션(리밸런싱 히스토리, 월별 수익률 등)의 UX 변경
- run_portfolio_backtest.py의 백테스트 로직 변경
- 별도 holdings.csv 사전 생성 (equity.csv에 이미 데이터 존재)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **보유 현황 날짜 선택**: `st.slider`는 연속 날짜를 허용하여 거래일이 아닌 날짜(주말, 공휴일) 선택 시 "선택한 날짜의 데이터가 없습니다" 경고 발생
2. **보유 현황 성능**: 날짜 변경 시 Streamlit이 전체 페이지를 재실행하여 모든 섹션을 다시 렌더링. `@st.fragment`로 보유 현황 섹션만 격리하면 해당 섹션만 재렌더링됨
3. **체결 전후 비교 성능/UX**: selectbox로 체결일 선택할 때마다 전체 페이지 재실행. 모든 체결일의 전후 비교 데이터를 사전 생성하면 대시보드에서는 로드만 하면 됨

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md` (CLI 스크립트 / Streamlit 앱 규칙)
- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인, portfolio_engine equity_df 스키마)
- `CLAUDE.md` (루트 - 상수 관리, 반올림 규칙, 코딩 표준)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 보유 현황: `st.select_slider`로 거래일만 선택 가능
- [x] 보유 현황: `@st.fragment`로 섹션 격리
- [x] 체결 전후 비교: `run_portfolio_backtest.py`에서 `execution_comparison.csv` 생성
- [x] 체결 전후 비교: 대시보드에서 긴 표 + `st.expander` 기본 숨김
- [x] `poetry run python validate_project.py` 통과 (passed=483, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)
- [x] `README.md` 변경 없음

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/run_portfolio_backtest.py`: `execution_comparison.csv` 생성 로직 추가
- `scripts/backtest/app_portfolio_backtest.py`: 보유 현황 UX 개선 + 체결 전후 비교 UX 변경
- `README.md`: 변경 없음

### 데이터/결과 영향

- 새 파일 추가: `storage/results/portfolio/{experiment_name}/execution_comparison.csv`
- 기존 파일 변경 없음

### execution_comparison.csv 스키마

체결이 발생한 날짜의 전후 비교 데이터를 저장한다. 각 행은 (체결일 x 자산)으로, 현금 행도 포함한다.

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| date | str | 체결 발생일 (YYYY-MM-DD) |
| asset_id | str | 자산 ID (예: qqq, spy) 또는 "cash" |
| pre_shares | int | 전일 보유 주수 (현금은 0) |
| post_shares | int | 당일 보유 주수 (현금은 0) |
| pre_weight_pct | float | 전일 비중 (%) |
| post_weight_pct | float | 당일 비중 (%) |
| pre_value | int | 전일 평가액 |
| post_value | int | 당일 평가액 |
| delta_shares | int | 주수 변동 |
| delta_value | int | 금액 변동 |
| trade_info | str | 거래 내역 요약 텍스트 |
| rebalance_reason | str | 리밸런싱 사유 (monthly/daily/"") |

## 6) 단계별 계획(Phases)

### Phase 1 — run_portfolio_backtest.py에 execution_comparison.csv 생성 추가

**작업 내용**:

- [x] `_build_execution_comparison_df()` 함수 작성: equity_df + trades_df에서 체결일의 전후 비교 DataFrame 생성
- [x] `_save_portfolio_results()`에서 `execution_comparison.csv` 저장 호출 추가
- [x] 반올림 규칙 적용 (비중: ROUND_PERCENT, 금액: ROUND_CAPITAL)

---

### Phase 2 — app_portfolio_backtest.py 보유 현황 UX 개선

**작업 내용**:

- [x] `_render_holdings_section()` 내 `st.slider` → `st.select_slider`로 변경 (equity_df의 Date만 옵션으로 제공)
- [x] `_render_holdings_section()`에 `@st.fragment` 데코레이터 적용

---

### Phase 3 — app_portfolio_backtest.py 체결 전후 비교 UX 변경

**작업 내용**:

- [x] `_render_execution_comparison_section()` 리팩토링: selectbox 제거, execution_comparison.csv 로드 후 긴 표로 표시
- [x] `st.expander`로 감싸서 기본 숨김 처리 (expanded=False)
- [x] CSV 로드 함수 추가 (`@st.cache_data`)
- [x] 체결일별 구분이 시각적으로 명확하도록 날짜 그룹 표시

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=483, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 대시보드 / 보유현황 거래일 전용 선택 + 체결비교 사전생성 테이블로 전환
2. 포트폴리오 대시보드 / 보유현황 select_slider + fragment 격리, 체결비교 CSV 사전생성
3. 포트폴리오 대시보드 / 보유현황·체결비교 UX 개선 (성능 + 거래일 제한)
4. 포트폴리오 대시보드 / 보유현황 성능 개선 + 체결 전후 비교 긴 표 전환
5. 포트폴리오 대시보드 / 보유현황 fragment 격리 + 체결비교 execution_comparison.csv 도입

## 7) 리스크(Risks)

- `@st.fragment`는 Streamlit 1.33+ 필요 → 현재 1.54.0이므로 문제 없음
- `execution_comparison.csv` 추가로 `run_portfolio_backtest.py` 실행 시간 미미하게 증가 (equity_df 순회만이므로 무시 가능)
- 기존 결과 디렉토리에 execution_comparison.csv가 없는 경우 대시보드에서 graceful fallback 필요

## 8) 메모(Notes)

- equity.csv에 shares/avg_price 컬럼이 없는 구 형식 실험(예: portfolio_f5)은 `_has_holdings_data()` 검사에 의해 이미 스킵됨
- execution_comparison.csv가 없는 실험도 동일하게 "데이터 없음" 안내 표시

### 진행 로그 (KST)

- 2026-04-03 22:00: 계획서 작성 완료
- 2026-04-03 22:30: Phase 1~4 구현 및 검증 완료 (passed=483, failed=0, skipped=0)

---
