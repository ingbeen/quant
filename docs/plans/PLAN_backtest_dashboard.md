# Implementation Plan: 백테스트 단일 전략 시각화 대시보드

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

**작성일**: 2026-02-16 23:30
**마지막 업데이트**: 2026-02-17 00:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] `scripts/backtest/run_single_backtest.py`의 결과를 시각화하는 Streamlit 대시보드 구현
- [x] Streamlit + `streamlit-lightweight-charts-v5`를 사용한 인터랙티브 금융 차트 제공
- [x] 파라미터를 UI에서 조정하여 실시간으로 전략 결과를 확인할 수 있는 환경 제공

## 2) 비목표(Non-Goals)

- Buy & Hold 대비 오버레이 (전략 vs 벤치마크 에쿼티 비교)
- 연속 손익 통계 (최대 연승/연패 횟수)
- 새로운 비즈니스 로직 추가 (기존 `src/qbt/backtest/` 모듈만 호출)
- 테스트 코드 추가 (기존 앱 `app_daily_comparison.py`, `app_rate_spread_lab.py`와 동일하게 Streamlit 앱은 테스트 비대상)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_single_backtest.py`는 결과를 콘솔 로그로만 출력하여 시각적 분석이 불가능
- 전략의 매수/매도 시점, 에쿼티 추이, 드로우다운 구간 등을 한눈에 파악할 수 없음
- 파라미터 변경 시 스크립트를 수동으로 재실행해야 함

### 기술 선택

- **`streamlit-lightweight-charts-v5`**: TradingView 스타일의 캔들스틱 차트, 마커, 오버레이, 멀티패인, 확대/축소/팬 네이티브 지원
- **Plotly**: 히트맵, 히스토그램 등 lightweight-charts가 지원하지 않는 차트 유형에 사용
- 기존 앱(`app_daily_comparison.py`)과 패턴 일관성 유지

### 데이터 흐름

```
QQQ_max.csv → signal_df ──┐
                           ├→ run_buffer_strategy() → trades_df, equity_df, summary
TQQQ_synthetic_max.csv → trade_df ┘
grid_results.csv → 기본 파라미터 (sidebar 기본값)
```

**핵심**: `run_buffer_strategy()`가 반환하는 3개 객체를 모두 활용
- `trades_df`: 거래 내역 (Buy/Sell 마커, 거래 상세, 보유기간 계산)
- `equity_df`: 자본 곡선 + upper_band/lower_band (에쿼티 차트, 드로우다운, 밴드 오버레이)
- `summary`: 성과 지표 (요약 카드)

### CSV에 없어서 앱에서 직접 계산해야 하는 항목

| 항목 | 계산 방법 |
|---|---|
| 이동평균선 | `add_single_moving_average(signal_df, ma_window)` |
| 전일대비% | `signal_df[COL_CLOSE].pct_change() * 100` |
| 에쿼티 곡선 | `equity_df["equity"]` (전략 실행 결과) |
| 드로우다운 | `(equity - peak) / peak * 100` |
| 월별 수익률 | equity를 월말 기준 리샘플링 후 수익률 계산 |
| 보유기간 | `(exit_date - entry_date).days` |
| 밴드 | `equity_df["upper_band"]`, `equity_df["lower_band"]` |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 공통 규칙
- `scripts/CLAUDE.md`: CLI 계층 규칙 (Streamlit width 규칙, 예외 처리 등)
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족 (아래 상세)
  - [x] QQQ 캔들스틱 차트 + MA 오버레이 + 버퍼존 밴드
  - [x] Buy/Sell 체결 마커
  - [x] 호버 시 OHLC 표시 + 전일대비% 서브패인
  - [x] 확대/축소/팬
  - [x] 에쿼티 곡선 차트
  - [x] 드로우다운 차트
  - [x] 월별/연도별 수익률 히트맵
  - [x] 포지션 보유 기간 분포 히스토그램
  - [x] 버퍼존 전략 결과 요약 (st.metric)
  - [x] 전체 매수매도 상세내역 (st.dataframe)
  - [x] 사용 파라미터 표시
  - [x] sidebar에서 파라미터 조정 가능 (MA기간, MA유형, 버퍼존, 유지일, 조정기간)
- [x] `poetry run python validate_project.py` 통과 (passed=284, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (scripts/CLAUDE.md에 앱 추가)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- (신규) `scripts/backtest/app_single_backtest.py`: Streamlit 대시보드 앱
- (수정) `pyproject.toml`: `streamlit-lightweight-charts-v5` 의존성 추가
- (수정) `scripts/CLAUDE.md`: 백테스트 앱 설명 추가

### 데이터/결과 영향

- 없음 (읽기 전용 시각화, 기존 데이터/결과 변경 없음)

## 6) 단계별 계획(Phases)

> Phase 0 생략: 인바리언트/정책 변경 없음 (신규 Streamlit 앱, 기존 비즈니스 로직 호출만)

---

### Phase 1 — 의존성 추가 + 앱 구현

**작업 내용**:

- [x] `pyproject.toml`에 `streamlit-lightweight-charts-v5` 의존성 추가 + `poetry install`
- [x] `scripts/backtest/app_single_backtest.py` 생성

#### 앱 구조 상세

```
app_single_backtest.py
├── 1. 페이지 설정 (st.set_page_config)
├── 2. 데이터 로딩 (@st.cache_data)
│   ├── QQQ_max.csv → signal_df
│   ├── TQQQ_synthetic_max.csv → trade_df
│   └── grid_results.csv → 기본 파라미터
├── 3. Sidebar 파라미터 UI
│   ├── MA 기간 (st.slider: 50-300, 기본값=grid_best or DEFAULT)
│   ├── MA 유형 (st.selectbox: SMA/EMA)
│   ├── 버퍼존 비율 (st.slider: 0.01-0.10, step=0.01)
│   ├── 유지일 (st.slider: 0-10)
│   └── 조정기간 (st.slider: 0-12, 월)
├── 4. 전략 실행 (@st.cache_data, 파라미터 기반 캐싱)
│   ├── add_single_moving_average(signal_df, ma_window, ma_type)
│   ├── 공통 날짜 필터링
│   └── run_buffer_strategy(signal_df, trade_df, params)
│       → trades_df, equity_df, summary
├── 5. 요약 지표 (st.metric 카드 4개)
│   ├── 총수익률, CAGR, MDD, 거래수/승률
├── 6. 메인 차트 (lightweight_charts_v5_component)
│   ├── Pane 1: QQQ 캔들스틱
│   │   ├── 캔들스틱 시리즈 (OHLC)
│   │   ├── MA Line 오버레이 (signal_df[f"ma_{window}"])
│   │   ├── Upper Band Line 오버레이 (equity_df["upper_band"])
│   │   ├── Lower Band Line 오버레이 (equity_df["lower_band"])
│   │   └── Buy/Sell 마커 (trades_df에서 추출)
│   │       - Buy: entry_date, position="belowBar", shape="arrowUp", color=green
│   │       - Sell: exit_date, position="aboveBar", shape="arrowDown", color=red
│   ├── Pane 2: 전일대비% Histogram (signal_df[COL_CLOSE].pct_change()*100)
│   └── Pane 3: 에쿼티 곡선 (Area chart, equity_df["equity"])
├── 7. 드로우다운 차트 (별도 lightweight-charts 컴포넌트)
│   └── Area chart: (equity - peak) / peak * 100
├── 8. 월별/연도별 수익률 히트맵 (Plotly heatmap via st.plotly_chart)
│   └── equity_df → 월말 리샘플링 → 월간 수익률 → pivot(year x month)
├── 9. 포지션 보유 기간 분포 (Plotly histogram via st.plotly_chart)
│   └── trades_df → (exit_date - entry_date).days → histogram
├── 10. 사용 파라미터 (st.json)
│   └── {ma_window, ma_type, buffer_zone_pct, hold_days, recent_months, source}
└── 11. 전체 거래 상세 내역 (st.dataframe)
    └── trades_df 전체 (한글 컬럼명으로 rename, width="stretch")
```

#### 재사용하는 기존 함수/모듈

| 함수/모듈 | 위치 | 용도 |
|---|---|---|
| `load_stock_data()` | `src/qbt/utils/data_loader.py` | QQQ, TQQQ CSV 로딩 |
| `load_best_grid_params()` | `src/qbt/backtest/analysis.py` | grid_results.csv 최적 파라미터 로딩 |
| `add_single_moving_average()` | `src/qbt/backtest/analysis.py` | 이동평균 계산 |
| `run_buffer_strategy()` | `src/qbt/backtest/strategy.py` | 버퍼존 전략 실행 |
| `BufferStrategyParams` | `src/qbt/backtest/strategy.py` | 전략 파라미터 데이터클래스 |
| 경로 상수 | `src/qbt/common_constants.py` | `QQQ_DATA_PATH`, `TQQQ_SYNTHETIC_DATA_PATH`, `GRID_RESULTS_PATH` |
| 도메인 상수 | `src/qbt/backtest/constants.py` | `DEFAULT_*`, `SLIPPAGE_RATE` |

#### lightweight-charts 차트 설정 핵심

```python
# 캔들스틱 시리즈
{"type": "Candlestick", "data": [...], "options": {"upColor": ..., "downColor": ...}}

# MA 오버레이 (Line 시리즈)
{"type": "Line", "data": [{"time": ..., "value": ma_value}], "options": {"color": ..., "lineWidth": 2}}

# 밴드 오버레이 (Line 시리즈, 점선)
{"type": "Line", "data": [...], "options": {"color": "rgba(255,0,0,0.3)", "lineWidth": 1, "lineStyle": 2}}

# Buy/Sell 마커 (캔들스틱 시리즈의 markers 파라미터)
markers = [{"time": "2020-03-15", "position": "belowBar", "shape": "arrowUp", "color": "#26a69a", "text": "Buy"}]

# 멀티패인 구성
charts = [pane1_config, pane2_config, pane3_config]
lightweight_charts_v5_component(name="...", charts=charts, height=total_height, zoom_level=200)
```

#### Plotly 차트 (히트맵, 히스토그램)

- `width="stretch"` 사용 (scripts/CLAUDE.md 규칙: `use_container_width` deprecated)
- 기존 앱과 동일한 패턴

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `scripts/CLAUDE.md` 업데이트: 백테스트 앱 설명 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 단일 전략 시각화 대시보드 구현 (Streamlit + lightweight-charts)
2. 백테스트 / QQQ 캔들차트 + 전략 분석 대시보드 추가
3. 백테스트 / app_single_backtest.py 시각화 앱 신규 구현
4. 백테스트 / 인터랙티브 전략 분석 대시보드 추가 (캔들차트, 에쿼티, 히트맵)
5. 백테스트 / Streamlit 대시보드로 전략 결과 시각화 기능 추가

## 7) 리스크(Risks)

- **`streamlit-lightweight-charts-v5` 타입 스텁 부재**: `reportMissingTypeStubs: "none"`으로 이미 설정되어 있어 PyRight 통과 가능
- **파라미터 변경 시 재계산 지연**: `st.cache_data`로 동일 파라미터 캐싱하여 완화. 전략 실행 자체는 수 초 이내
- **streamlit-lightweight-charts-v5 마커/오버레이 호환성**: Context7 문서에서 markers, overlay Line series 지원 확인 완료. 미지원 기능 발견 시 Plotly 대체

## 8) 메모(Notes)

- `streamlit-lightweight-charts-v5` v0.1.8 기반 (Context7 학습 완료)
- 기존 앱 패턴 참고: `scripts/tqqq/app_daily_comparison.py` (Streamlit + Plotly)
- 실행 명령어: `poetry run streamlit run scripts/backtest/app_single_backtest.py`
- Buy & Hold 벤치마크 제외 (사용자 요청): 추후 별도 plan으로 추가 가능

### 진행 로그 (KST)

- 2026-02-16 23:30: Plan 작성 완료 (Draft)
- 2026-02-17 00:00: 구현 완료, 전체 검증 통과 (passed=284, failed=0, skipped=0)
