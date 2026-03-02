# Implementation Plan: 시장 구간별 분석 및 Profit Concentration 대시보드

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

**작성일**: 2026-03-02 22:00
**마지막 업데이트**: 2026-03-02 23:00
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

- [x] 대시보드에 시장 구간(상승/횡보/하락) 19개 구간별 요약 지표 섹션 추가
- [x] 구간별 CAGR 비교 바 차트(Profit Concentration) 추가
- [x] 모든 전략(5개 탭)에 동일하게 적용

## 2) 비목표(Non-Goals)

- 시장 구간을 알고리즘으로 자동 분류하는 기능 (수동 상수 정의 사용)
- WFO 전용 Profit Concentration(`_calculate_profit_concentration`) 수정
- summary.json에 구간별 지표 저장 (대시보드 런타임 계산)
- 기존 5개 섹션(요약 지표, 메인 차트, 거래 상세, 파라미터, 히트맵/보유기간)의 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

전체 기간 최적화 파라미터로 백테스트하면 미래 데이터를 참조하는 Look-Ahead Bias가 발생한다. 이 편향의 크기를 가늠하려면 전체 성과를 시장 환경별로 분해해서 봐야 한다.

현재 대시보드는 전체 기간 요약 지표만 표시하므로:
- 상승장에서만 수익이 집중되는지, 하락장에서도 방어가 되는지 확인 불가
- 전략의 수익이 특정 시기에 편중(Profit Concentration)되었는지 판단 불가

### 대시보드 현재 구조

`_render_strategy_tab()` 렌더링 순서:
1. 요약 지표 (st.metric 5개)
2. 메인 차트 (lightweight-charts 캔들 + 에쿼티 + 드로우다운)
3. 전체 거래 상세 내역 (st.dataframe)
4. 사용 파라미터 (st.json)
5. 월별 수익률 히트맵 (Plotly)
6. 포지션 보유 기간 분포 (Plotly)

변경 후: **"2. 메인 차트"와 "3. 전체 거래 상세 내역" 사이에 새 섹션 삽입**

### 시장 구간 정의 (QQQ 기준, 사용자 확인 완료)

19개 구간 (상승 10개, 횡보 3개, 하락 6개):

| # | 시작일 | 종료일 | 유형 | 설명 |
|---|--------|--------|------|------|
| 1 | 1999-03-10 | 2000-03-27 | 상승 | 닷컴 버블 상승기 |
| 2 | 2000-03-28 | 2002-10-09 | 하락 | 닷컴 붕괴 |
| 3 | 2002-10-10 | 2004-01-26 | 상승 | 닷컴 후 초기 회복 |
| 4 | 2004-01-27 | 2006-07-21 | 횡보 | 금리인상기 박스권 |
| 5 | 2006-07-24 | 2007-10-31 | 상승 | 글로벌 성장기 |
| 6 | 2007-11-01 | 2009-03-09 | 하락 | 글로벌 금융위기 |
| 7 | 2009-03-10 | 2011-07-25 | 상승 | QE1/QE2 상승기 |
| 8 | 2011-07-26 | 2012-09-18 | 횡보 | 유럽 재정위기 횡보 |
| 9 | 2012-09-19 | 2015-07-20 | 상승 | QE3 상승기 |
| 10 | 2015-07-21 | 2016-06-30 | 횡보 | 중국/유가 불안 |
| 11 | 2016-07-01 | 2018-09-28 | 상승 | 트럼프 랠리 |
| 12 | 2018-10-01 | 2018-12-24 | 하락 | 2018 Q4 조정 |
| 13 | 2018-12-26 | 2020-02-19 | 상승 | 2019 회복 랠리 |
| 14 | 2020-02-20 | 2020-03-23 | 하락 | 코로나 급락 |
| 15 | 2020-03-24 | 2021-11-19 | 상승 | 포스트코로나 랠리 |
| 16 | 2021-11-22 | 2022-10-13 | 하락 | 금리인상 약세장 |
| 17 | 2022-10-14 | 2025-02-18 | 상승 | AI 랠리 |
| 18 | 2025-02-19 | 2025-05-12 | 하락 | 관세 충격 |
| 19 | 2025-05-13 | 2026-02-17 | 상승 | 회복기 |

### Profit Concentration 방식

복리 효과로 인한 절대 PnL 왜곡을 피하기 위해, **구간별 CAGR 비교 바 차트**를 사용한다.
CAGR은 기간을 정규화하므로 23일 코로나 급락과 600일 장기 상승을 동일 선상에서 비교할 수 있다.

### 구간별 요약 지표 항목 (8개)

기존 5개 + 추가 3개:

| 지표 | 기존/추가 | 설명 |
|------|----------|------|
| 총수익률 | 기존 | 구간 시작 에쿼티 대비 종료 에쿼티 변화율 |
| CAGR | 기존 | 연환산 복리 성장률 |
| MDD | 기존 | 구간 내 최대 낙폭 (구간 내부 peak 기준) |
| Calmar | 기존 | CAGR / \|MDD\| |
| 거래수 | 기존 | 구간 내 진입(entry_date)한 거래 수 |
| 승률 | 기존 | 수익 거래 비율 |
| 평균 보유기간 | 추가 | 구간 내 거래의 평균 holding_days (일) |
| 수익팩터 | 추가 | 총 수익 / \|총 손실\| (Profit Factor) |

구간 기간 정보(시작일/종료일/영업일)는 테이블 컬럼으로 포함한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (Streamlit width, 비즈니스 로직 분리)
- `tests/CLAUDE.md`: 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

- [x] `MARKET_REGIMES` 상수 정의 (19개 구간)
- [x] `MarketRegimeDict`, `RegimeSummaryDict` TypedDict 정의
- [x] `calculate_regime_summaries()` 비즈니스 로직 구현
- [x] 대시보드에 시장 구간별 요약 테이블 렌더링
- [x] 대시보드에 구간별 CAGR 바 차트 렌더링
- [x] 5개 전략 탭 모두에서 동작 확인 (Feature Detection)
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/constants.py` | `MARKET_REGIMES` 상수 추가 |
| `src/qbt/backtest/types.py` | `MarketRegimeDict`, `RegimeSummaryDict` TypedDict 추가 |
| `src/qbt/backtest/analysis.py` | `calculate_regime_summaries()` 함수 추가 |
| `scripts/backtest/app_single_backtest.py` | `_render_regime_analysis()`, `_render_cagr_bar_chart()` 추가, 섹션 번호 갱신 |
| `tests/test_analysis.py` | `TestCalculateRegimeSummaries` 클래스 추가 |
| `src/qbt/backtest/CLAUDE.md` | analysis.py 섹션에 새 함수 문서화 |

### 데이터/결과 영향

- 기존 결과 파일 변경 없음
- summary.json 스키마 변경 없음
- 대시보드 런타임 계산만 추가 (저장하지 않음)

## 6) 단계별 계획(Phases)

### Phase 0 — 타입 정의 + 테스트 작성 (레드)

**작업 내용**:

- [x] `types.py`에 `MarketRegimeDict` TypedDict 추가
  ```python
  class MarketRegimeDict(TypedDict):
      start: str       # ISO format "YYYY-MM-DD"
      end: str         # ISO format "YYYY-MM-DD"
      regime_type: str  # "bull", "bear", "sideways"
      name: str        # 한글 구간명 (예: "닷컴 붕괴")
  ```
- [x] `types.py`에 `RegimeSummaryDict` TypedDict 추가
  ```python
  class RegimeSummaryDict(TypedDict):
      name: str              # 구간명
      regime_type: str       # "bull" / "bear" / "sideways"
      start_date: str        # 구간 시작일 (실제 데이터 존재 첫날)
      end_date: str          # 구간 종료일 (실제 데이터 존재 마지막날)
      trading_days: int      # 영업일 수
      total_return_pct: float
      cagr: float
      mdd: float
      calmar: float
      total_trades: int
      winning_trades: int
      win_rate: float
      avg_holding_days: float   # 거래 없으면 0.0
      profit_factor: float      # 거래 없으면 0.0
  ```
- [x] `tests/test_analysis.py`에 `TestCalculateRegimeSummaries` 클래스 작성 (레드)
  - `test_basic_two_regimes`: 2개 구간(상승+하락)에 걸치는 equity+trades → 구간별 지표 검증
  - `test_regime_no_overlap`: 데이터 범위 밖 구간 → 결과 리스트에서 제외 확인
  - `test_no_trades_regime`: 거래 없는 구간 (Buy & Hold) → total_trades=0, avg_holding_days=0, profit_factor=0 확인
  - `test_profit_factor_calculation`: 수익/손실 거래 혼합 → profit_factor = 총수익 / |총손실|
  - `test_profit_factor_no_loss`: 손실 거래 없음 → profit_factor = 0.0 (무한대 대신 0 반환)

---

### Phase 1 — 상수 정의 + 비즈니스 로직 구현 (그린)

**작업 내용**:

- [x] `constants.py`에 `MARKET_REGIMES` 상수 추가
  - `list[MarketRegimeDict]` 타입 (19개 구간)
  - `typing.Final` 어노테이션 적용
- [x] `analysis.py`에 `calculate_regime_summaries()` 함수 구현

  **함수 시그니처**:
  ```python
  def calculate_regime_summaries(
      equity_df: pd.DataFrame,
      trades_df: pd.DataFrame,
      regimes: list[MarketRegimeDict],
  ) -> list[RegimeSummaryDict]:
  ```

  **핵심 로직** (각 구간에 대해):
  1. `equity_df`를 구간 날짜로 필터링 (`start <= Date <= end`)
  2. 필터링된 행이 2개 미만이면 스킵 (결과 리스트에서 제외)
  3. 구간 시작 에쿼티를 `initial_capital`로 사용
  4. 기존 `calculate_summary()`를 호출하여 기본 지표 획득 (코드 재사용)
  5. `trades_df`를 `entry_date` 기준으로 구간 필터링
  6. 추가 지표 계산:
     - `avg_holding_days`: 필터링된 거래의 `holding_days` 평균 (거래 없으면 0.0)
     - `profit_factor`: 수익 거래 PnL 합 / |손실 거래 PnL 합| (손실 없으면 0.0)
  7. `RegimeSummaryDict`로 조합하여 반환

  **`calculate_summary()` 재사용 시 주의**:
  - `initial_capital` = 구간 시작 시점의 `equity` 값
  - 슬라이스된 `equity_df`를 전달하면 MDD가 구간 내부 peak 기준으로 정확히 계산됨
  - `trades_df`는 구간 내 entry_date 기준 필터링 결과 전달

- [x] Phase 0 테스트 전부 통과 확인

---

### Phase 2 — 대시보드 렌더링 구현

**작업 내용**:

- [x] `app_single_backtest.py`에 `calculate_regime_summaries` import 추가
- [x] `app_single_backtest.py`에 `MARKET_REGIMES` import 추가
- [x] `_render_regime_table()` 함수 구현
  - `RegimeSummaryDict` 리스트 → `pd.DataFrame` 변환
  - 한글 컬럼명 매핑 (구간명, 유형, 시작일, 종료일, 영업일, 수익률, CAGR, MDD, Calmar, 거래수, 승률, 평균보유기간, 수익팩터)
  - 유형별 행 배경색: 상승(rgba(38,166,154,0.15)), 하락(rgba(239,83,80,0.15)), 횡보(rgba(255,193,7,0.15))
  - `st.dataframe(styled_df, width="stretch")`
- [x] `_render_cagr_bar_chart()` 함수 구현
  - Plotly 수평 바 차트 (go.Bar, orientation="h")
  - X축: CAGR (%), Y축: 구간명
  - 색상: 상승(#26a69a), 하락(#ef5350), 횡보(#ffc107)
  - 0% 기준선 표시
  - `st.plotly_chart(fig, width="stretch")`
- [x] `_render_strategy_tab()`에 새 섹션 삽입
  - 위치: "1. 메인 차트" 아래, "전체 거래 상세 내역" 위
  - 섹션 제목: "2. 시장 구간별 분석"
  - `calculate_regime_summaries()` 호출
  - `_render_regime_table()` + `_render_cagr_bar_chart()` 렌더링
  - st.caption으로 "QQQ 기준 시장 구간 분류" 안내 문구
- [x] 기존 섹션 번호 갱신 (2→3, 3→4, 4→5, 5→6)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - analysis.py 섹션에 `calculate_regime_summaries` 함수 문서화
  - types.py 섹션에 `MarketRegimeDict`, `RegimeSummaryDict` 추가
  - constants.py 섹션에 `MARKET_REGIMES` 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=431, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 대시보드에 시장 구간별 분석 및 CAGR 비교 차트 추가
2. 백테스트 / 시장 레짐(상승/횡보/하락) 구간별 요약 지표 대시보드 신규 섹션
3. 백테스트 / 19개 시장 구간별 성과 분석 + Profit Concentration CAGR 바 차트
4. 백테스트 / 대시보드 구간별 분석 섹션 추가 (요약 테이블 + CAGR 비교)
5. 백테스트 / 시장 구간별 분석 비즈니스 로직 + 대시보드 시각화 추가

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| 구간 날짜가 데이터 범위를 벗어남 | `equity_df` 필터링 후 2행 미만이면 스킵 |
| Buy & Hold 전략은 거래(trades)가 없음 | `total_trades=0`일 때 avg_holding_days=0, profit_factor=0 반환 |
| 짧은 구간(23일 코로나)의 CAGR이 극단적으로 증폭 | CAGR 계산 시 기간이 짧아도 연환산하되, UI에서 영업일 수를 함께 표시하여 맥락 제공 |
| 구간 경계 날짜에 해당 전략 데이터가 없을 수 있음 | 필터링 후 실제 존재하는 첫날/마지막날을 start_date/end_date로 사용 |

## 8) 메모(Notes)

- Profit Concentration은 WFO의 `_calculate_profit_concentration`과 별개 개념. WFO는 윈도우별 에쿼티 증감, 여기서는 시장 구간별 CAGR 비교
- 시장 구간은 QQQ 기준 수동 분류이므로 향후 데이터 추가 시 상수 업데이트 필요
- profit_factor: 손실 거래가 없으면 무한대가 되므로, 이 경우 0.0 반환 (N/A 의미). 대시보드에서 0.0은 "-"로 표시

### 진행 로그 (KST)

- 2026-03-02 22:00: 계획서 초안 작성
- 2026-03-02 23:00: 전체 구현 완료 (passed=431, failed=0, skipped=0)

---
