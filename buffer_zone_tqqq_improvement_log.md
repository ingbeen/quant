# 버퍼존 TQQQ 전략 개선 로그

> 작성 시작: 2026-02-21
> 목적: 버퍼존 TQQQ 전략의 성과 분석 및 단계적 개선 히스토리
> 대상: Claude (프로젝트 내부 작업용)
> 도메인 배경: [CLAUDE.md](CLAUDE.md), [src/qbt/backtest/CLAUDE.md](src/qbt/backtest/CLAUDE.md) 참조

---

## 1. 최신 결론 (TL;DR)

- **QQQ 전략**: WFO 검증 통과. Fully Fixed(MA=200, buy=0.01, sell=0.05, hold=2, recent=8)가 Dynamic보다 우수 → **파라미터 고정 운용 가능**
- **TQQQ ATR 전략**: Phase 1~3 구현 완료. ATR TQQQ Dynamic WFO Stitched CAGR 16.09%, MDD **-52.95%** (기존 -62.09% → 9.14pp 개선). **목표 MDD -50%에 2.95pp 미달**
- **공통 발견**: sell_buffer=0.05가 두 전략 모두에서 가장 안정적. "Tight Entry, Wide Exit" 패턴은 구조적 특성
- **ATR 결과**: ATR(14, 3.0)이 전 윈도우(33개 데이터 포인트) 수렴. WFE 폭주 해소(-161 → 5.37). Profit Concentration 경고 해제(0.67 → 0.48). ATR source QQQ 고정(사용자 결정)
- **다음 실험**: ATR multiplier 2.5 재실험 (MDD -50% 달성 도전) / Fully Fixed(MA=150, ATR=14, mult=3.0) 단일 백테스트 검증

---

## 2. 성과 개선 히스토리

### 2.1 단일 백테스트 기준 (1999~2026, grid_best 파라미터)

| 단계                        | CAGR   | MDD     | Calmar | 비고                                  |
| --------------------------- | ------ | ------- | ------ | ------------------------------------- |
| 초기 (단일 buffer_zone_pct) | 20.26% | -85.68% | 0.237  | Session 1                             |
| 버퍼 분리 (buy/sell 분리)   | 20.59% | -88.27% | 0.233  | Session 5~6. MDD 악화 → 과최적화 경고 |

### 2.2 WFO Stitched 기준 (Dynamic 모드)

| 단계                   | CAGR       | MDD         | WFE Calmar  | PC Max      | 비고                                   |
| ---------------------- | ---------- | ----------- | ----------- | ----------- | -------------------------------------- |
| WFO 적용 (버퍼존 TQQQ) | 21.68%     | -62.09%     | -161 (폭주) | 0.67 (경고) | Session 9                              |
| + min_trades=3 제약    | (동일)     | (동일)      | (동일)      | (동일)      | Session 16. 첫 IS 윈도우 파라미터 개선 |
| + WFE/PC 지표 보강     | (동일)     | (동일)      | (신규 지표) | (신규 지표) | Session 16. 진단 기반 마련             |
| + ATR 트레일링 스탑    | **16.09%** | **-52.95%** | **5.37**    | **0.48**    | Session 16. MDD 9.14pp 개선            |

### 2.3 전략별 ATR WFO 비교

결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/walkforward_summary.json`

| Mode        | 기존 CAGR | ATR CAGR | 기존 MDD | ATR MDD     | MDD 개선 |
| ----------- | --------- | -------- | -------- | ----------- | -------- |
| Dynamic     | 21.68%    | 16.09%   | -62.09%  | **-52.95%** | +9.14pp  |
| Sell Fixed  | 20.77%    | 11.32%   | -70.06%  | -54.31%     | +15.75pp |
| Fully Fixed | 6.97%     | 8.40%    | -61.10%  | **-51.75%** | +9.35pp  |

---

## 3. 핵심 발견 사항

16개 세션(2026-02-21 ~ 2026-02-23)의 분석에서 도출한 결론을 카테고리별로 정리합니다.

### 3.1 전략 선택

- **TQQQ 단순 보유는 파국**: B&H TQQQ는 CAGR 0.94%, MDD -99.98%. Volatility Decay로 레버리지 상품은 반드시 추세 추종 전략 필요
- **버퍼존 TQQQ 선택**: 수익 극대화 방향. MDD를 줄이는 것이 핵심 과제
- **QQQ는 고정 파라미터가 최선**: WFO 3-Mode 비교에서 Fully Fixed가 Dynamic을 상회. 학술적으로도 단순 모델 우위 실증 (DeMiguel et al. 2009)
- **TQQQ는 동적 파라미터 필요**: 파라미터 불안정성으로 Dynamic WFO가 유효

### 3.2 파라미터 안정성

- **sell_buffer=0.05 수렴**: QQQ/TQQQ 모두에서 sell=0.05가 가장 안정적. "Tight Entry, Wide Exit" 패턴
- **ATR(14, 3.0) 전 윈도우 수렴**: {14, 22} x {2.5, 3.0} 그리드에서 11윈도우 x 3모드 = 33개 데이터 포인트 전부 (14, 3.0) 선택. ATR은 QQQ(signal_df) 기준으로 계산하되, 매매 대상 TQQQ에서 손실이 3배 증폭되므로 더 빠르게 반응하는 짧은 기간(14일)이 유리
- **버퍼존 파라미터 레짐 전환**: Dynamic 모드에서 윈도우 1~5(IS ~2015)와 6~10(IS ~2017+)이 뚜렷하게 구분됨 → §3.6 참조
- 결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/walkforward_dynamic.csv` 등

### 3.3 과최적화 진단

- **WFE 폭주 원인**: IS Calmar가 0에 근접할 때 `oos/is` 비율 계산이 발산. ATR 추가 후 해소
- **Profit Concentration**: 기존 TQQQ Dynamic에서 수익의 67%가 Window 9(2023-2025)에 집중 → ATR 적용 후 48%로 경고 해제 (TradeStation 기준 50%)
- **min_trades=3**: IS 구간에서 거래 < 3회인 파라미터 조합 제외. 첫 IS 윈도우의 sell=0.01 선택 문제 해결
- 진단 지표 구현: [walkforward.py](src/qbt/backtest/walkforward.py)의 `calculate_wfo_mode_summary()`

### 3.4 MDD 원인 분석

- **청산일 = MDD 최저점**: 16개 거래 중 10개(62.5%)에서 가장 많이 떨어진 날에 매도. 하단 밴드 청산의 구조적 지연
- **2020-03 코로나 급락**: WFO Stitched MDD -62.09%의 주요 원인. ATR 스탑이 없어 최고점 대비 큰 낙폭 후에야 청산
- **ATR 스탑 효과**: OOS 거래 18 → 51회 증가, 승률 32.58% → 50.2% 개선. ATR이 큰 손실 거래를 중도 청산

### 3.5 기각된 아이디어

- **분할 매수(DCA)**: 버퍼존 전략의 이분법적 구조(전량 진입/전량 청산)에서 오히려 역효과. 진입 타이밍 문제는 ATR 스탑으로 해결 (Session 2, 6)
- **MDD 제약형 목적함수**: min_trades=3으로 대체 (Session 10)
- **PBO 분석**: 우선순위 하향, 보류 합의 (Session 14)

### 3.6 버퍼존 파라미터 레짐 전환 분석

ATR TQQQ Dynamic WFO에서 버퍼존 파라미터가 두 시기로 뚜렷하게 구분됩니다.

결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/walkforward_dynamic.csv`

| 시기 | 윈도우 | MA | buy | sell | hold | recent | 특성 |
|------|--------|-----|------|------|------|--------|------|
| Period 1 | 1~5 (IS ~2015) | 200 | 0.01 | 0.03 | 0 | 0 | 타이트 진입, 즉시 반응, 동적 조정 없음 |
| Period 2 | 6~10 (IS ~2017+) | 200 | 0.03 | 0.03~0.05 | 2~3 | 0~12 | 넓은 진입, hold 대기, 동적 조정 활용 |

**과적합이 아닌 이유**: 파라미터가 무작위로 흔들리지 않고, 특정 시점을 기준으로 한 레짐에서 다른 레짐으로 이동하며, 각 레짐 내에서는 안정적임

**전환점(~2015~2017)과 일치하는 시장 구조 변화 3가지**:

1. **통화정책 전환**: 2015.12 첫 금리 인상(7년간 제로금리 종료) → 2017년 양적긴축(QT) 시작
2. **FAANG 지배력**: 2017년 기준 Big Five가 NASDAQ-100의 거의 절반 차지, QQQ 가격 행태 자체가 변화
3. **저변동성 레짐 확립**: ETF 패시브 투자 폭증 + 알고리즘 거래 증가 → VIX 구조적 하락

**Expanding Window의 "지연된 전환" 효과**:

IS가 항상 1999년부터 시작하므로, 1999~2007 위기 데이터 비중이 점차 줄어들다가 임계점(tipping point)을 넘는 순간 최적 파라미터가 전환됨. 2009 이후 강세장 데이터가 위기 데이터를 통계적으로 압도하는 시점이 IS ~2017 부근과 일치.

**파라미터 변화의 해석**:

| 파라미터 | Period 1 → 2 | 원인 |
|---------|-------------|------|
| buy: 0.01 → 0.03 | 저변동성 시장에서 작은 돌파는 가짜 신호 확률 높음 → 진입 기준 강화 |
| hold: 0 → 2~3 | whipsaw(가짜 돌파 후 복귀) 빈도 증가 → 며칠 확인 후 행동이 유리 |
| recent: 0 → 0~12 | 시장 레짐이 다양해져서 동적 적응 필요 |

**전략적 시사점**: "어느 쪽이 맞다"가 아니라 다른 시장 환경에 대한 다른 최적해. Dynamic WFO가 이 전환을 자동으로 처리하고 있음. 현재 시장(2025~2026)은 Period 2에 가까우므로 후반부 파라미터가 더 적절할 가능성이 높으나, 다시 위기가 오면 Period 1 스타일이 유리할 수 있음.

---

## 4. 구현 완료 목록

| Phase                | 내용                                                                      | 계획서                               | 검증       |
| -------------------- | ------------------------------------------------------------------------- | ------------------------------------ | ---------- |
| 버퍼 분리            | buy/sell buffer 분리 + 동적 조정 기준 entry→exit 변경                     | `PLAN_sell_buffer_separation.md`     | passed     |
| WFO 인프라           | Expanding Anchored WFO + 3-Mode (Dynamic/Sell Fixed/Fully Fixed)          | `PLAN_walkforward_optimization.md`   | passed     |
| Phase 1: WFE/PC 지표 | wfe_cagr, gap_calmar_median, wfe_calmar_robust, profit_concentration 추가 | `PLAN_wfo_wfe_pc_metrics.md`         | passed=347 |
| Phase 2: min_trades  | select_best_calmar_params()에 min_trades=3 필터링                         | `PLAN_wfo_min_trades.md`             | passed=350 |
| Phase 3: ATR 스탑    | buffer_zone_atr_tqqq 전략 신규 추가 + WFO 파이프라인 통합                 | `PLAN_atr_trailing_stop_strategy.md` | passed=358 |

계획서 위치: [docs/plans/](docs/plans/) 또는 [docs/archive/](docs/archive/)

---

## 5. 토론 합의 현황

Session 9~15에서 Claude Opus 4.6 / GPT-5.2 간 교대 토론으로 도출한 합의사항입니다.

### 합의 완료 (구현됨)

| #   | 항목                                                             | 상태 |
| --- | ---------------------------------------------------------------- | ---- |
| 1   | wfe_calmar 폭주 → wfe_cagr를 1급 지표로 추가                     | Done |
| 2   | gap_calmar_median(차이 기반) + wfe_calmar_robust(필터 후 median) | Done |
| 3   | Profit Concentration V2 (window_profit = end - prev_end)         | Done |
| 4   | min_trades=3 제약                                                | Done |
| 5   | ATR 스탑: Sell Fixed(0.05) + ATR, OR 조건, 다음 시가 체결        | Done |
| 6   | ATR 그리드: {14, 22} x {2.5, 3.0}, IS에서 최적화                 | Done |
| 7   | BufferStrategyParams 확장: atr_period=0이면 비활성 (하위 호환)   | Done |

### 종결된 미합의

| #   | 주제                                       | 결론                                                     |
| --- | ------------------------------------------ | -------------------------------------------------------- |
| A   | ATR 시그널 소스 (QQQ vs TQQQ)              | **QQQ 고정** (사용자 결정)                               |
| B   | ATR period {14,22} vs {14,20}              | **{14,22}** 채택, IS 결과 전부 14 선택                   |
| C   | ATR 기준가 (highest_close vs highest_high) | **highest_close** 채택 (전략의 모든 시그널이 close 기준) |

### 보류

| #   | 주제                          | 상태                          |
| --- | ----------------------------- | ----------------------------- |
| D   | PBO 분석 (TQQQ)               | 보류 (양측 우선순위 5로 하향) |
| E   | TQQQ IS 기간 확장 (72→96개월) | 보류 (min_trades로 우선 해결) |
| F   | DSR (Deflated Sharpe Ratio)   | 미논의                        |

---

## 6. 다음 실험 계획

| 순위 | 실험                                                   | 목적                                              | 성공 기준                             | 상태 |
| ---- | ------------------------------------------------------ | ------------------------------------------------- | ------------------------------------- | ---- |
| 1    | ATR multiplier 2.5 단일 고정 재실험                    | MDD -50% 달성 도전                                | Stitched MDD ≤ -50% AND Calmar ≥ 0.35 | 대기 |
| 2    | Fully Fixed 단일 백테스트 (MA=150, ATR=14, mult=3.0)   | ATR TQQQ Fully Fixed MDD -51.75% → 전체 기간 검증 | 과최적화 갭 확인                      | 대기 |
| 3    | ATR(14,3.0) vs (22,3.0) OOS 비교 (IS 최적화 없이 고정) | 파라미터 일반화 가능성 검증                       | OOS 성과 비교                         | 대기 |
| 4    | PBO/DSR 분석                                           | 탐색공간 1,728개 다중검정 점검                    | -                                     | 대기 |

---

## 7. 참고 자료

### 학술 논문

- DeMiguel, Garlappi & Uppal (2009). "Optimal Versus Naive Diversification." Review of Financial Studies
- Kelly, Malamud, Zhou (2024). "The Virtue of Complexity in Return Prediction." Journal of Finance
- Hsu & Kuan (2005). "Re-Examining the Profitability of Technical Analysis." SSRN
- Pardo, R.E. (2008). "The Evaluation and Optimization of Trading Strategies." Wiley

### 기술 참고

- TradeStation WFO — OOS Summary (Profit Concentration 50% rule): https://help.tradestation.com/09_01/tswfo/topics/walk-forward_summary_out-of-sample.htm
- StockCharts — Chandelier Exit: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/chandelier-exit
- Compounding Effects in Leveraged ETFs (arXiv:2504.20116): https://arxiv.org/abs/2504.20116
- Build Alpha — Robustness Testing Guide: https://www.buildalpha.com/robustness-testing-guide/
- Zorro Manual — Objective Functions for WFO: https://manual.zorro-project.com/objective.htm

---

## 8. 변경 로그

> 새로운 분석, 구현, 실험 결과가 있을 때마다 아래에 항목을 추가합니다.
> 형식: `### YYYY-MM-DD 제목` + 변경 내용 요약 + 성과 수치 변화 (해당 시)

### 2026-02-21 초기 분석 및 전략 선택

- 4개 전략(버퍼존 TQQQ/QQQ, B&H TQQQ/QQQ) 성과 비교 → 버퍼존 TQQQ 선택
- 분할 매수 도입 가능성 연구 → 기각 (이분법 구조에서 역효과)
- trades.csv 심층 분석: 청산일=MDD 최저점 패턴 발견, ATR 트레일링 스탑 최우선 과제 도출
- 외부 AI 검토: DCA 기각 확정, 매수/매도 버퍼 분리 제안 수용

### 2026-02-21 매수/매도 버퍼 분리 구현

- `buffer_zone_pct` → `buy_buffer_zone_pct` + `sell_buffer_zone_pct` 분리
- 동적 조정 기준: entry → exit 변경
- 그리드 서치 공간: 840 → 4,200 조합
- 단일 백테스트: CAGR 20.59%, MDD -88.27% (과최적화 경고)

### 2026-02-22 WFO 아키텍처 설계 및 구현

- Claude/GPT 교대 토론으로 WFO 설계 합의
- Expanding Anchored + 3-Mode (Dynamic, Sell Fixed, Fully Fixed) 구현
- WFO 결과: TQQQ Dynamic Stitched CAGR 21.68%, MDD -62.09% (단일 -88% → -62%, 26pp 개선)
- QQQ: Fully Fixed가 Dynamic 상회 → 파라미터 고정 운용 가능 확인

### 2026-02-22 WFE/PC 진단 지표 + min_trades + ATR 설계

- WFE 폭주 문제 확인 및 3개 보강 지표 설계 (wfe_cagr, gap_calmar_median, wfe_calmar_robust)
- Profit Concentration V2 설계 (window_profit 기반)
- min_trades=3 제약 설계
- ATR 트레일링 스탑 Phase 1~3 설계: 파라미터, OR 조건, 성공 기준 합의
- ATR 미합의 3건(소스/period/기준가) → Session 15에서 실험 설계, 이후 사용자 결정으로 종결

### 2026-02-23 Phase 1~3 구현 완료 + ATR WFO 결과

- Phase 1 (WFE/PC 지표): passed=347
- Phase 2 (min_trades=3): passed=350
- Phase 3 (ATR 트레일링 스탑): passed=358, ATR source QQQ 고정 (사용자 결정)
- ATR TQQQ Dynamic WFO: CAGR 16.09%, **MDD -52.95%** (기존 -62.09% → 9.14pp 개선)
- ATR(14, 3.0) 전 윈도우 수렴 (33/33 데이터 포인트)
- WFE 폭주 해소 (-161 → 5.37), PC 경고 해제 (0.67 → 0.48)
- OOS 거래 18 → 51회, 승률 32.58% → 50.2%

### 2026-02-23 버퍼존 파라미터 레짐 전환 분석 추가

- ATR TQQQ Dynamic WFO 윈도우별 최적 파라미터 분석: Period 1(IS ~2015)과 Period 2(IS ~2017+)의 뚜렷한 구분 발견
- 전환점(~2015~2017)이 실제 거시경제 구조 변화(금리 인상, FAANG 지배력, 저변동성 레짐)와 일치함을 웹 리서치로 확인
- Expanding Anchored WFO의 "지연된 전환" 효과 분석: 위기 데이터 비중이 줄어들며 임계점에서 파라미터 전환
- §3.6으로 문서화

---

_이 문서는 작업 진행에 따라 지속적으로 업데이트됩니다._
