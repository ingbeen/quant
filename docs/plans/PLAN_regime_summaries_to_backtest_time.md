# Implementation Plan: 시장 구간별 분석 연산 시점 변경 (대시보드 → 백테스트)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-02 23:30
**마지막 업데이트**: 2026-03-02 23:50
**관련 범위**: backtest, scripts/backtest
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

- [ ] `calculate_regime_summaries()` 연산을 대시보드(app) 런타임에서 백테스트 실행 시점으로 이동
- [ ] `run_single_backtest.py`와 `run_wfo_stitched_backtest.py` 양쪽에서 계산하여 `summary.json`에 `regime_summaries` 키로 저장
- [ ] 대시보드는 저장된 결과를 로드하여 렌더링만 수행 (Feature Detection)
- [ ] 불필요해진 대시보드 임포트 및 연산 코드 제거

## 2) 비목표(Non-Goals)

- `_render_regime_table()`, `_render_cagr_bar_chart()` 등 대시보드 렌더링 로직 변경
- `calculate_regime_summaries()` 함수 시그니처 변경
- `MARKET_REGIMES` 상수, `MarketRegimeDict`, `RegimeSummaryDict` 타입 변경
- 기존 테스트 삭제/수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

이전 계획(`PLAN_regime_analysis_dashboard.md`)에서 시장 구간별 분석 기능을 구현할 때, `calculate_regime_summaries()`를 대시보드 런타임에서 호출하도록 설계했다. 이로 인해:

1. **대시보드 로딩 시마다 반복 연산**: 전략 탭마다 19개 구간 × `calculate_summary()` 호출이 매번 발생
2. **아키텍처 비일관성**: 다른 지표(monthly_returns 등)는 백테스트 시 계산 후 summary.json에 저장하는데, regime_summaries만 런타임 계산
3. **대시보드에 비즈니스 로직 의존성**: `app_single_backtest.py`가 `calculate_regime_summaries`와 `MARKET_REGIMES`를 직접 임포트

### 변경 방향

- `run_single_backtest.py`와 `run_wfo_stitched_backtest.py` 양쪽의 `_save_summary_json()`에서 `calculate_regime_summaries()` 호출
- 결과를 각 `summary.json`에 `regime_summaries` 키로 저장 (반올림 적용)
- `app_single_backtest.py`는 `summary_data["regime_summaries"]`를 읽어 렌더링만 수행

### 대상 스크립트 2개

| 스크립트 | 결과 디렉토리 | `_save_summary_json` 시그니처 |
|----------|-------------|------------------------------|
| `run_single_backtest.py` | 전략별 (`buffer_zone_tqqq/` 등 5개) | `(result: SingleBacktestResult, monthly_returns, ...)` |
| `run_wfo_stitched_backtest.py` | `buffer_zone_atr_tqqq_wfo/` | `(summary: dict, equity_df, window_results, result_dir)` |

두 스크립트 모두 `summary.json`을 생성하며 `app_single_backtest.py`가 자동 탐색한다.

### holding_days 컬럼 처리

현재 `calculate_regime_summaries()`는 `trades_df["holding_days"]` 컬럼이 있으면 `avg_holding_days`를 계산하고, 없으면 0.0을 반환한다. 문제는:

- 대시보드에서 호출할 때: CSV에서 로드한 `trades_df`에 `holding_days`가 이미 존재 (정상 동작)
- 백테스트 시점에서 호출할 때: 원시 `result.trades_df`에 `holding_days` 미존재 (`_save_trades_csv()`에서 추가)

**해결**: `calculate_regime_summaries()`에서 `holding_days` 컬럼이 없을 때 `entry_date`와 `exit_date`로 자동 계산하는 폴백 로직 추가. 이렇게 하면 호출 시점에 무관하게 정확한 결과 반환.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

- [ ] `calculate_regime_summaries()`에 holding_days 자동 계산 폴백 추가
- [ ] `run_single_backtest.py`에서 regime_summaries 계산 및 summary.json 저장
- [ ] `run_wfo_stitched_backtest.py`에서 regime_summaries 계산 및 summary.json 저장
- [ ] `app_single_backtest.py`에서 런타임 연산 제거, summary_data에서 로드
- [ ] `app_single_backtest.py`에서 `calculate_regime_summaries`, `MARKET_REGIMES` 임포트 제거
- [ ] summary.json에 `regime_summaries` 키 없는 경우 대응 (Feature Detection)
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/analysis.py` | `calculate_regime_summaries()`에 holding_days 폴백 로직 추가 |
| `scripts/backtest/run_single_backtest.py` | regime_summaries 계산 및 summary.json 저장 |
| `scripts/backtest/run_wfo_stitched_backtest.py` | regime_summaries 계산 및 summary.json 저장 |
| `scripts/backtest/app_single_backtest.py` | 런타임 연산 제거, summary_data에서 로드, 불필요 임포트 제거 |
| `tests/test_analysis.py` | holding_days 자동 계산 테스트 추가 |
| `src/qbt/backtest/CLAUDE.md` | summary.json 스키마 변경 문서화 |

### 데이터/결과 영향

- `summary.json` 스키마에 `regime_summaries` 키 추가 (두 스크립트 모두)
- 기존 summary.json에는 `regime_summaries` 키 없음 → Feature Detection으로 대응
- 기존 `signal.csv`, `equity.csv`, `trades.csv` 변경 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트 작성 (레드)

**작업 내용**:

- [ ] `tests/test_analysis.py`의 `TestCalculateRegimeSummaries`에 테스트 추가:
  - `test_holding_days_auto_computed`: `trades_df`에 `holding_days` 컬럼 없이 `entry_date`/`exit_date`만 있을 때 `avg_holding_days`가 정확히 계산되는지 검증

  ```python
  def test_holding_days_auto_computed(self):
      """trades_df에 holding_days 컬럼이 없을 때 entry_date/exit_date로 자동 계산"""
      # Given: trades_df에 entry_date, exit_date, pnl만 있고 holding_days 없음
      #   거래 2건: (2021-02-01 ~ 2021-05-01 = 89일), (2021-08-01 ~ 2021-11-01 = 92일)
      # When: calculate_regime_summaries 호출
      # Then: avg_holding_days == (89 + 92) / 2 = 90.5
  ```

---

### Phase 1 — 비즈니스 로직 + 스크립트 변경 (그린)

**작업 내용**:

- [ ] `analysis.py`의 `calculate_regime_summaries()`에 holding_days 폴백 로직 추가
  - 구간 필터링된 `regime_trades`에 `holding_days` 컬럼이 없고 `entry_date`/`exit_date`가 있으면 자동 계산
  ```python
  # holding_days 자동 계산 (컬럼 미존재 시)
  if not regime_trades.empty and "holding_days" not in regime_trades.columns:
      if "entry_date" in regime_trades.columns and "exit_date" in regime_trades.columns:
          regime_trades["holding_days"] = regime_trades.apply(
              lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
          )
  ```
- [ ] Phase 0 테스트 통과 확인

- [ ] `run_single_backtest.py` 변경:
  - `calculate_regime_summaries`, `MARKET_REGIMES` 임포트 추가
  - `_save_summary_json()` 시그니처에 `regime_summaries` 파라미터 추가
  - 반올림 적용 후 `summary_data`에 `regime_summaries` 키 추가
  - `_save_results()`에서 `calculate_regime_summaries()` 호출하여 전달

- [ ] `run_wfo_stitched_backtest.py` 변경:
  - `calculate_regime_summaries` 임포트 추가 (기존 analysis 임포트에 병합)
  - `MARKET_REGIMES` 임포트 추가 (기존 constants 임포트에 병합)
  - `_save_summary_json()` 시그니처에 `regime_summaries` 파라미터 추가
  - 반올림 적용 후 `summary_data`에 `regime_summaries` 키 추가
  - `main()`에서 `calculate_regime_summaries()` 호출하여 전달

- [ ] `app_single_backtest.py` 변경:
  - `from qbt.backtest.analysis import calculate_regime_summaries` 임포트 제거
  - `from qbt.backtest.constants import MARKET_REGIMES` 임포트 제거
  - `_render_strategy_tab()`의 Section 2에서 런타임 연산 제거
  - `summary_data.get("regime_summaries", [])` 로드 방식으로 변경 (Feature Detection)

**`run_single_backtest.py` 변경 상세**:

`_save_results()` (line 236~):
```python
# regime_summaries 계산 추가
regime_summaries = calculate_regime_summaries(
    result.equity_df, result.trades_df, MARKET_REGIMES
)
summary_path = _save_summary_json(result, monthly_returns, regime_summaries)
```

`_save_summary_json()` (line 184~):
```python
def _save_summary_json(
    result: SingleBacktestResult,
    monthly_returns: list[dict[str, Any]],
    regime_summaries: list[dict[str, Any]],  # 추가
) -> Path:
```

**`run_wfo_stitched_backtest.py` 변경 상세**:

`main()` (line 335~):
```python
# regime_summaries 계산 추가
regime_summaries = calculate_regime_summaries(
    equity_df, trades_df, MARKET_REGIMES
)
summary_path = _save_summary_json(
    summary, equity_df, window_results, RESULT_DIR, regime_summaries
)
```

`_save_summary_json()` (line 175~):
```python
def _save_summary_json(
    summary: dict[str, object],
    equity_df: pd.DataFrame,
    window_results: list[dict[str, object]],
    result_dir: Path,
    regime_summaries: list[dict[str, Any]],  # 추가
) -> Path:
```

**공통: regime_summaries 반올림 후 저장** (두 스크립트 동일 패턴):
```python
regime_data: list[dict[str, Any]] = []
for rs in regime_summaries:
    regime_data.append({
        "name": rs["name"],
        "regime_type": rs["regime_type"],
        "start_date": rs["start_date"],
        "end_date": rs["end_date"],
        "trading_days": rs["trading_days"],
        "total_return_pct": round(float(str(rs["total_return_pct"])), 2),
        "cagr": round(float(str(rs["cagr"])), 2),
        "mdd": round(float(str(rs["mdd"])), 2),
        "calmar": round(float(str(rs["calmar"])), 2),
        "total_trades": rs["total_trades"],
        "winning_trades": rs["winning_trades"],
        "win_rate": round(float(str(rs["win_rate"])), 2),
        "avg_holding_days": round(float(str(rs["avg_holding_days"])), 1),
        "profit_factor": round(float(str(rs["profit_factor"])), 2),
    })

summary_data["regime_summaries"] = regime_data
```

**`app_single_backtest.py` Section 2 변경**:
```python
# ---- Section 2: 시장 구간별 분석 ----
st.header("2. 시장 구간별 분석")
regime_summaries = summary_data.get("regime_summaries", [])
if regime_summaries:
    _render_regime_table(regime_summaries, chart_key=strategy["strategy_name"])
    _render_cagr_bar_chart(regime_summaries, chart_key=strategy["strategy_name"])
    st.caption("QQQ 기준 시장 구간 분류 (19개 구간: 상승 10개, 횡보 3개, 하락 6개)")
else:
    st.info("시장 구간별 분석 데이터가 없습니다. 백테스트를 재실행하세요.")
```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트
  - analysis.py 섹션: `calculate_regime_summaries()`에 holding_days 폴백 설명 추가
  - summary.json에 `regime_summaries` 키 저장 사실 문서화
- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 시장 구간별 분석 연산을 대시보드에서 백테스트 실행 시점으로 이동
2. 백테스트 / regime_summaries를 summary.json에 사전 계산·저장하고 대시보드는 로드만 수행
3. 백테스트 / 시장 구간별 분석 연산 시점 변경 (app 런타임 → 백테스트 저장)
4. 백테스트 / 대시보드 런타임 연산 제거, summary.json에 regime_summaries 사전 저장
5. 백테스트 / 구간별 분석을 백테스트 시 계산·저장하여 대시보드 의존성 제거

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| 기존 summary.json에 `regime_summaries` 키 없음 | Feature Detection: `summary_data.get("regime_summaries", [])` → 키 없으면 재실행 안내 |
| 원시 trades_df에 holding_days 미존재 | `calculate_regime_summaries()` 내부 폴백으로 entry_date/exit_date에서 자동 계산 |
| summary.json 크기 증가 | 최대 19개 구간 × ~14 필드 = 미미한 증가 (수 KB) |
| 두 스크립트에 동일 반올림 코드 중복 | 14개 필드의 단순 반올림이므로 유틸 추출보다 인라인이 적절 (YAGNI) |

## 8) 메모(Notes)

- 이 계획은 `PLAN_regime_analysis_dashboard.md`의 Non-Goal이었던 "summary.json에 구간별 지표 저장"을 구현하는 후속 작업
- `_render_regime_table()`과 `_render_cagr_bar_chart()`의 입력 타입이 `list[dict[str, object]]`이므로, summary.json에서 로드한 `list[dict[str, Any]]`와 호환됨
- 사용자는 변경 후 `run_single_backtest.py`와 `run_wfo_stitched_backtest.py`를 재실행해야 새 summary.json이 생성됨

### 진행 로그 (KST)

- 2026-03-02 23:30: 계획서 초안 작성
- 2026-03-02 23:50: `run_wfo_stitched_backtest.py` 범위 추가

---
