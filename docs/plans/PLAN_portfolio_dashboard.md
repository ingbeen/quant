# Implementation Plan: 포트폴리오 비교 대시보드 구현

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

**작성일**: 2026-03-18 10:00
**마지막 업데이트**: 2026-03-18 11:00
**관련 범위**: scripts, backtest
**관련 문서**: docs/PLAN_portfolio_experiment.md, docs/plans/PLAN_portfolio_engine.md, docs/plans/PLAN_portfolio_scripts.md, docs/strategy_validation_report.md

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

- [x] `scripts/backtest/app_portfolio_backtest.py` 구현 — 7가지 포트폴리오 실험 비교 대시보드 (Streamlit + Plotly)
- [x] `scripts/CLAUDE.md` 업데이트 — `app_portfolio_backtest.py` 스크립트 설명 추가
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 — 대시보드 앱 아키텍처 섹션에 포트폴리오 앱 설명 추가

## 2) 비목표(Non-Goals)

- 포트폴리오 엔진 변경 → 계획서 1(PLAN_portfolio_engine.md)에서 완료
- 실험 설정 및 CLI 스크립트 변경 → 계획서 2(PLAN_portfolio_scripts.md)에서 완료
- 단일 자산 기준선(QQQ/SPY/GLD 전체 기간) 대비 공정 비교 재계산 → 별도 분석 작업
- 포트폴리오 WFO / 파라미터 최적화 → 해당 없음
- 신규 테스트 추가 → Streamlit 대시보드 앱은 기존 관례상 테스트 없음 (app_single_backtest.py, app_split_backtest.py, app_walkforward.py, app_parameter_stability.py 모두 테스트 없음)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

계획서 1(엔진)과 계획서 2(CLI 스크립트)가 완료되어 7가지 포트폴리오 실험 결과가 `storage/results/portfolio/{experiment_name}/`에 생성된다. 그러나 현재 결과를 시각적으로 비교할 방법이 없다. `PLAN_portfolio_experiment.md §5.2`에서 정의한 핵심 비교(A-2 vs QQQ 단일, C-1 vs B-3 등)를 수행하려면 에쿼티 곡선·드로우다운·성과 지표를 한 화면에서 비교하는 대시보드가 필요하다.

### 결과 파일 구조 (계획서 2 확정)

```
storage/results/portfolio/{experiment_name}/
├── equity.csv        # Date, equity, cash, drawdown_pct, {asset_id}_value, {asset_id}_weight, {asset_id}_signal, rebalanced
├── trades.csv        # 전 자산 거래 (asset_id, trade_type 포함)
├── summary.json      # display_name, portfolio_summary, per_asset, portfolio_config
└── signal_{asset_id}.csv  # OHLCV + ma_{N} + upper_band + lower_band + change_pct
```

**summary.json 구조**:

```json
{
  "display_name": "A-2 (QQQ 30% / SPY 30% / GLD 40%)",
  "portfolio_summary": {
    "initial_capital": 10000000,
    "final_capital": ...,
    "total_return_pct": ...,
    "cagr": ...,
    "mdd": ...,
    "calmar": ...,
    "total_trades": ...,
    "start_date": "...",
    "end_date": "..."
  },
  "per_asset": [
    {"asset_id": "qqq", "target_weight": 0.30, "total_trades": ..., "win_rate": ...},
    ...
  ],
  "portfolio_config": {...}
}
```

### 7가지 실험 요약 (PLAN_portfolio_experiment.md §3)

| 실험 | experiment_name | 구성 요약 | 유효 주식 노출 |
|---|---|---|---|
| A-1 | portfolio_a1 | QQQ 25% / SPY 25% / GLD 50% | 50% |
| A-2 | portfolio_a2 | QQQ 30% / SPY 30% / GLD 40% | 60% |
| A-3 | portfolio_a3 | QQQ 35% / SPY 35% / GLD 30% | 70% |
| B-1 | portfolio_b1 | QQQ 19.5% / TQQQ 7% / SPY 19.5% / GLD 40% + 현금 14% | 60% |
| B-2 | portfolio_b2 | QQQ 12% / TQQQ 12% / SPY 12% / GLD 40% + 현금 24% | 60% |
| B-3 | portfolio_b3 | QQQ 15% / TQQQ 15% / SPY 30% / GLD 40% | 105% 유효 |
| C-1 | portfolio_c1 | QQQ 50% / TQQQ 50% (분산 없음) | 200% |

### 핵심 비교 질문 (PLAN_portfolio_experiment.md §5.2 기반)

- **A-2 vs QQQ 단일**: SPY+GLD 분산이 MDD를 얼마나 줄이는가?
- **A-1 vs A-2 vs A-3**: 주식:금 비율(50:50, 60:40, 70:30) 민감도
- **A-2 vs B-1**: 같은 유효 노출 60%에서 TQQQ 소량 + 현금의 효과
- **B-2 vs B-3**: 현금 24%의 MDD 완충 효과 vs 투자 효율
- **C-1 vs B-3**: 같은 레버리지 수준에서 분산(SPY+GLD)의 가치
- **C-1 vs TQQQ 단일**: QQQ:TQQQ 5:5 vs TQQQ 100% MDD 차이

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `scripts/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `app_portfolio_backtest.py` — 전체 비교 탭 + 7개 실험 상세 탭 구현 완료
- [x] `scripts/CLAUDE.md` — `app_portfolio_backtest.py` 설명 추가 완료
- [x] `src/qbt/backtest/CLAUDE.md` — 대시보드 앱 아키텍처 섹션 포트폴리오 앱 추가 완료
- [x] `poetry run python validate_project.py` 통과 (passed=374, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

신규:

- `scripts/backtest/app_portfolio_backtest.py` — 포트폴리오 비교 대시보드 앱

수정:

- `scripts/CLAUDE.md` — `app_portfolio_backtest.py` 설명 추가
- `src/qbt/backtest/CLAUDE.md` — 대시보드 앱 아키텍처 섹션에 포트폴리오 앱 항목 추가

변경 없음:

- `src/qbt/backtest/portfolio_strategy.py` (import만 사용)
- `src/qbt/backtest/portfolio_types.py` (import만 사용)
- `src/qbt/backtest/portfolio_configs.py` (import만 사용)
- `src/qbt/common_constants.py`
- `tests/` (신규 테스트 없음)

### 데이터/결과 영향

- `storage/results/portfolio/` 디렉토리 읽기 전용 (쓰기 없음)
- 기존 `storage/results/backtest/`, `storage/results/tqqq/` 결과 변경 없음

---

## 6) 단계별 계획(Phases)

> Phase 0 (레드) 생략: Streamlit 대시보드 앱은 데이터 로딩 + 시각화 계층만 담당하며, 신규 비즈니스 로직·불변조건·예외 정책이 없다. 기존 관례(app_single_backtest.py 등)와 동일하게 테스트 없이 진행한다.

---

### Phase 1 — `app_portfolio_backtest.py` 구현

**선행 조건**: `run_portfolio_backtest.py`를 먼저 실행하여 `storage/results/portfolio/` 데이터가 존재해야 한다.

**작업 내용**:

- [x] `scripts/backtest/app_portfolio_backtest.py` 생성

  **모듈 docstring** (실행 명령어 예시 포함):

  ```
  포트폴리오 비교 대시보드 — 7가지 실험(A/B/C 시리즈) 결과를 비교한다.

  선행:
      poetry run python scripts/backtest/run_portfolio_backtest.py

  실행:
      poetry run streamlit run scripts/backtest/app_portfolio_backtest.py
  ```

  **로컬 상수**:

  ```python
  # 성과 지표 테이블 컬럼 레이블
  _COL_DISPLAY_NAME = "실험"
  _COL_CAGR = "CAGR (%)"
  _COL_MDD = "MDD (%)"
  _COL_CALMAR = "Calmar"
  _COL_TOTAL_RETURN = "총 수익률 (%)"
  _COL_TOTAL_TRADES = "총 거래 수"

  # 자산별 색상 (Plotly 일관성)
  _ASSET_COLORS: dict[str, str] = {
      "qqq": "#1f77b4",    # 파랑
      "tqqq": "#ff7f0e",   # 주황
      "spy": "#2ca02c",    # 초록
      "gld": "#d62728",    # 빨강
  }

  # 실험별 색상 (전체 비교 차트용)
  _EXPERIMENT_COLORS: dict[str, str] = {
      "portfolio_a1": "#aec7e8",
      "portfolio_a2": "#1f77b4",
      "portfolio_a3": "#17becf",
      "portfolio_b1": "#ffbb78",
      "portfolio_b2": "#ff7f0e",
      "portfolio_b3": "#d62728",
      "portfolio_c1": "#9467bd",
  }
  ```

  **데이터 클래스 (모듈 상단, private)**:

  ```python
  @dataclass
  class _ExperimentData:
      """로딩된 실험 결과 데이터."""
      experiment_name: str
      display_name: str
      equity_df: pd.DataFrame      # equity.csv
      trades_df: pd.DataFrame      # trades.csv
      summary: dict[str, Any]      # summary.json
      signal_dfs: dict[str, pd.DataFrame]  # signal_{asset_id}.csv (key: asset_id)
  ```

  **데이터 로딩 함수**:

  `_discover_experiments() -> list[Path]`:

  ```
  - PORTFOLIO_RESULTS_DIR 하위 폴더를 스캔
  - 각 하위 폴더에서 summary.json 존재 여부로 유효한 실험 결과 판별
  - 존재하는 폴더 경로 리스트 반환 (알파벳 순 정렬)
  - 존재하는 실험이 없으면 빈 리스트 반환
  ```

  `_load_experiment_data(experiment_dir: Path) -> _ExperimentData`:

  ```
  1. summary.json 로딩 (json.loads)
  2. equity.csv 로딩 (pd.read_csv, parse_dates=["Date"])
  3. trades.csv 로딩 (pd.read_csv, parse_dates=["entry_date", "exit_date"])
  4. signal_{asset_id}.csv 탐색 및 로딩 (glob 패턴: signal_*.csv)
     - asset_id 추출: 파일명에서 "signal_" 제거하고 ".csv" 제거
  5. _ExperimentData 반환
  ```

  **전체 비교 탭 렌더링 함수**:

  `_render_comparison_tab(experiments: list[_ExperimentData]) -> None`:

  ```
  1. 성과 지표 비교 테이블
     - DataFrame 구성:
       실험 | CAGR(%) | MDD(%) | Calmar | 총 수익률(%) | 총 거래 수
     - st.dataframe(df, width="stretch")
     - Calmar 기준 내림차순 정렬 (참고용, 과최적화 방지 주의 문구 포함)

  2. 에쿼티 곡선 비교 (Plotly)
     - 실험 선택: st.multiselect (기본: 전체 선택)
     - go.Figure + go.Scatter (mode="lines")
     - x축: Date, y축: equity (원화, 초기 자본 10,000,000 동일)
     - 실험별 _EXPERIMENT_COLORS 색상 적용
     - hovertemplate: 날짜, 실험명, 에쿼티(원) 표시
     - 제목: "에쿼티 곡선 비교"

  3. 드로우다운 비교 (Plotly)
     - 동일 실험 선택 적용
     - go.Scatter (drawdown_pct, mode="lines", fill="tozeroy")
     - y축: 드로우다운 (%, 음수)
     - 제목: "드로우다운 비교"

  4. 실험 해설 expander
     - PLAN_portfolio_experiment.md §7.1 기반 행동 가이드 요약:
       - A-2(60:40)의 Calmar > QQQ 단일: A-2를 기본 포트폴리오로 채택
       - A-1이 A-2보다 높아도 A-2 유지 (비율은 결과로 선택하지 않음)
       - B시리즈 우위: TQQQ 포함 여부를 별도 판단
       - C-1 > B-3: 분산 가치가 없다는 증거 → 추가 분석 필요
  ```

  **개별 실험 탭 렌더링 함수**:

  `_render_experiment_tab(exp: _ExperimentData) -> None`:

  ```
  섹션 1: 요약 지표
  - st.columns(4) → CAGR, MDD, Calmar, 총 수익률 st.metric 4개
  - st.columns(len(per_asset)) → 자산별 목표 비중 st.metric (각 자산명 + 비중%)

  섹션 2: 에쿼티 + 드로우다운 (Plotly, make_subplots)
  - subplot 2행 1열 (row_heights=[0.7, 0.3], shared_xaxes=True)
  - 상단: equity 곡선 (go.Scatter, mode="lines")
  - 하단: drawdown_pct 곡선 (go.Scatter, fill="tozeroy")
  - st.plotly_chart(fig, width="stretch")

  섹션 3: 자산별 비중 추이 (Plotly)
  - equity_df의 {asset_id}_weight 컬럼들을 stacked area chart로 표시
    - go.Scatter (mode="lines", fill="tonexty", stackgroup="one")
    - 자산별 _ASSET_COLORS 색상 적용
  - 현금 비중 = 1 - sum({asset_id}_weight)도 표시 (color: "#aaaaaa")
  - hovertemplate: 날짜, 자산명, 비중(%) 표시
  - 제목: "자산별 비중 추이 (리밸런싱 효과 포함)"
  - st.plotly_chart(fig, width="stretch")

  섹션 4: 자산별 거래 현황 (Plotly)
  - trades_df를 asset_id × trade_type으로 groupby count
  - go.Bar (grouped bar chart): x=asset_id, y=count, color=trade_type
    - trade_type: "signal" (신호 거래) vs "rebalance" (리밸런싱 거래)
  - 제목: "자산별 거래 수 (신호 거래 vs 리밸런싱)"
  - st.plotly_chart(fig, width="stretch")

  섹션 5: 거래 내역 테이블
  - 자산 필터: st.selectbox("자산 선택", ["전체", *asset_ids])
  - 필터 적용 후 st.dataframe(trades_df, width="stretch")
  - 표시 컬럼: asset_id, trade_type, entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct, holding_days

  섹션 6: 시그널 차트 (자산 선택)
  - st.selectbox("시그널 차트 자산 선택", asset_ids)
  - 선택된 signal_{asset_id}.csv 로딩
  - Plotly 캔들스틱 차트:
    - go.Candlestick (OHLC 가격)
    - go.Scatter (ma_200, mode="lines", name="EMA-200")
    - go.Scatter (upper_band, mode="lines", line=dict(dash="dash"), name="상단 밴드")
    - go.Scatter (lower_band, mode="lines", line=dict(dash="dash"), name="하단 밴드")
  - 해당 자산 거래 마커 (trades_df 필터링):
    - 매수(entry): marker_symbol="triangle-up", color="green"
    - 매도(exit): marker_symbol="triangle-down", color="red"
  - st.plotly_chart(fig, width="stretch")

  섹션 7: 파라미터 정보 (expander)
  - st.expander("파라미터 상세 정보")
  - summary["portfolio_config"] 내용을 st.json()으로 표시
  ```

  **main 함수**:

  ```python
  def main() -> None:
      st.set_page_config(
          page_title="포트폴리오 비교 대시보드",
          page_icon=None,
          layout="wide",
      )
      st.title("포트폴리오 비교 대시보드")

      # 실험 탐색 및 로딩
      experiment_dirs = _discover_experiments()
      if not experiment_dirs:
          st.error(
              "포트폴리오 실험 결과가 없습니다. "
              "먼저 run_portfolio_backtest.py를 실행하세요."
          )
          return

      experiments = [_load_experiment_data(d) for d in experiment_dirs]

      # 탭 구성: "전체 비교" + 실험별 탭 (자동 탐색)
      tab_labels = ["전체 비교", *[exp.display_name for exp in experiments]]
      tabs = st.tabs(tab_labels)

      with tabs[0]:
          _render_comparison_tab(experiments)

      for i, exp in enumerate(experiments):
          with tabs[i + 1]:
              _render_experiment_tab(exp)


  if __name__ == "__main__":
      main()
  ```

  **임포트 구조**:

  ```python
  from __future__ import annotations

  import json
  from dataclasses import dataclass
  from pathlib import Path
  from typing import Any

  import pandas as pd
  import plotly.graph_objects as go
  import streamlit as st
  from plotly.subplots import make_subplots

  from qbt.common_constants import PORTFOLIO_RESULTS_DIR
  ```

**Validation** (Phase 1):

- [x] `poetry run python validate_project.py --only-tests` 통과 (passed=374, failed=0, skipped=0)

---

### Phase 2 — 문서 업데이트

- [x] `scripts/CLAUDE.md` 업데이트

  백테스트(backtest/) 섹션의 "대시보드 앱:" 항목에 추가:

  ```
  - `app_portfolio_backtest.py`: 7가지 포트폴리오 실험 비교 대시보드 (Streamlit + Plotly)
    - 선행: `run_portfolio_backtest.py` 실행 필요 (결과 CSV/JSON 로드)
    - 실험 자동 탐색: PORTFOLIO_RESULTS_DIR 하위 summary.json 존재 여부로 유효 실험 판별, 알파벳 순 탭 자동 생성
    - 주요 섹션:
      - 전체 비교 탭: 성과 지표 테이블, 에쿼티 곡선 비교, 드로우다운 비교, 실험 해설
      - 실험별 탭: 요약 지표, 에쿼티+드로우다운 서브플롯, 자산별 비중 추이, 거래 현황, 거래 내역, 시그널 차트(자산 선택), 파라미터 정보
  ```

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트

  "대시보드 앱 아키텍처" 섹션에 추가:

  ```
  ### 포트폴리오 비교 대시보드 (`scripts/backtest/app_portfolio_backtest.py`)

  포트폴리오 7가지 실험(A/B/C 시리즈) 결과를 비교하는 대시보드.

  핵심 설계:
  - **실험 자동 탐색**: `_discover_experiments()`가 PORTFOLIO_RESULTS_DIR 하위 summary.json 존재 여부로 유효 실험 판별
  - **탭 구조**: "전체 비교" 탭 + 실험별 탭(자동 생성)
  - **Plotly 전용**: lightweight-charts 없이 Plotly만 사용 (멀티 시리즈 라인 차트가 주목적)
  - **에쿼티 비교**: 초기 자본이 동일(10,000,000)이므로 정규화 없이 절대값 비교
  ```

**Validation** (Phase 2):

- [x] `poetry run python validate_project.py --only-tests` 통과 (passed=374, failed=0, skipped=0)

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=374, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 비교 대시보드 구현 (7가지 실험 A/B/C 시리즈)
2. 백테스트 / app_portfolio_backtest.py 신규 구현 (전체 비교 + 실험별 상세)
3. 백테스트 / 포트폴리오 실험 결과 시각화 대시보드 구현
4. 백테스트 / 멀티 실험 포트폴리오 비교 대시보드 + 문서 업데이트
5. 백테스트 / 포트폴리오 비교 Streamlit 앱 구현 (계획서 3)

---

## 7) 리스크(Risks)

| 리스크 | 설명 | 완화책 |
|---|---|---|
| 실험 결과 미생성 | `run_portfolio_backtest.py` 미실행 시 `storage/results/portfolio/`가 비어있어 앱이 에러 메시지 표시 | `_discover_experiments()` 빈 리스트 반환 → 친화적 에러 메시지 출력 |
| equity_df 동적 컬럼 | 실험마다 자산 수가 다르므로 `{asset_id}_weight/value/signal` 컬럼 수가 다름 | 컬럼명을 `_weight` 접미사로 필터링하여 동적 처리 |
| signal_dfs 자산 ID 불일치 | `signal_tqqq.csv`는 실제로 QQQ 데이터(EMA-200)를 포함하므로 차트 제목에 혼동 가능 | 차트 제목을 `{asset_id} 시그널 (시그널 소스: QQQ)` 형태로 명시. summary.json의 portfolio_config에서 signal_data_path 확인 |
| Plotly 캔들스틱 + 트레이드 마커 타이밍 | trades_df의 entry_date/exit_date는 체결일(시가)이고, signal_df는 종가 기준 | 마커 위치를 entry_price/exit_price로 표시(y축)하고 날짜를 체결일로 사용 — 일관성 유지 |
| 기존 테스트 회귀 | app 파일 추가로 인한 import 오류 또는 패키지 구조 변경 | Phase 1 완료 후 --only-tests 실행으로 즉시 확인 |
| 대시보드 Streamlit width 파라미터 | `use_container_width` deprecated (scripts/CLAUDE.md 규칙) | `width="stretch"` 사용 (st.dataframe, st.plotly_chart 등) |

---

## 8) 메모(Notes)

### 설계 결정 기록

**Plotly 전용 선택 (lightweight-charts 미사용)**:

`app_single_backtest.py`는 캔들스틱 + customValues 기반 tooltip이 핵심이므로 lightweight-charts v5를 사용한다. 반면 포트폴리오 대시보드는 멀티 시리즈 라인 차트(에쿼티/드로우다운 비교)가 주목적이고, 단일 자산 캔들스틱은 보조적 역할이다. Plotly는 멀티 시리즈 비교에 적합하며 의존성 추가 없이 구현 가능하다.

**자동 탐색 패턴 (기존 앱과 일관성)**:

`app_single_backtest.py`의 `_discover_strategies()` 패턴과 동일하게 디렉토리 스캔 + summary.json 존재 여부로 판별한다. 앱 코드 수정 없이 실험이 추가/삭제될 수 있다.

**에쿼티 정규화 불필요**:

7가지 실험 모두 초기 자본이 동일(10,000,000원)이므로 절대값 비교가 공정하다. 정규화(=1 기준)는 초기 자본이 다른 경우에 필요한데 여기서는 해당 없다.

**단일 자산 기준선 미포함**:

`PLAN_portfolio_experiment.md §5.1`에서 기준선(QQQ/TQQQ/SPY/GLD 단일)을 공통 기간(2004-11-18~)으로 재계산해야 한다고 명시되어 있다. 그러나 이는 `run_portfolio_backtest.py`에서 기준선 재계산을 추가하거나 별도 스크립트를 만드는 작업으로, 본 계획서 범위 밖이다. 현재 대시보드는 7가지 포트폴리오 실험 간 비교에 집중한다. 단일 자산 전체 기간 결과는 `app_single_backtest.py`를 참고한다.

**계획서 전체 구성 (3개)**:

| 계획서 | 파일명 | 내용 | 상태 |
|---|---|---|---|
| 계획서 1 | PLAN_portfolio_engine.md | 엔진 + 타입 + 상수 | ✅ Done |
| 계획서 2 | PLAN_portfolio_scripts.md | CLI 스크립트 (7가지 실험 실행 + 결과 저장) | ✅ Done |
| 계획서 3 (현재) | PLAN_portfolio_dashboard.md | 포트폴리오 비교 대시보드 | 🟡 Draft |

### 진행 로그 (KST)

- 2026-03-18 10:00: 계획서 초안 작성 완료
- 2026-03-18 11:00: Phase 1 완료 — app_portfolio_backtest.py 구현 (Black 포맷 + Ruff/PyRight/Pytest 통과)
- 2026-03-18 11:00: Phase 2 완료 — scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md 업데이트
- 2026-03-18 11:00: 최종 검증 완료 — validate_project.py passed=374, failed=0, skipped=0
