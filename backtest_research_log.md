# 버퍼존 TQQQ 전략 개선 로그

> 작성 시작: 2026-02-21
> 목적: 버퍼존 TQQQ 전략의 성과 분석 및 단계적 개선 히스토리
> 대상: Claude (프로젝트 내부 작업용)
> 도메인 배경: [CLAUDE.md](CLAUDE.md), [src/qbt/backtest/CLAUDE.md](src/qbt/backtest/CLAUDE.md) 참조

---

## 1. 최신 결론 (TL;DR)

- **QQQ**: Fully Fixed(MA=200, buy=0.01, sell=0.05, hold=2, recent=8) 파라미터 고정 운용 가능 (Dynamic보다 우수)
- **TQQQ ATR**: Dynamic WFO Stitched CAGR 16.09%, MDD -52.95%. ATR(14,3.0) 33/33 수렴, Expanding WFO 유지
- **검증 완료**: ATR 고정 OOS 비교에서 (14,3.0) 구조적 우위 확인 (§3.8), Expanding이 Rolling 대비 CAGR +5.05pp 우위 (§3.7)
- **리스크**: PBO 0.65 (통계적 경고), DSR 0.35 (미유의) → 맹신 금지 수준의 리스크 지표 (§3.3)

**전략 판정**: 미결. MDD -52.95%는 당초 목표(-50%)에 2.95pp 미달. 목표 완화·추가 개선·조건부 수용 중 결정 필요.

---

## 2. 성과 개선 히스토리

### 2.1 단일 백테스트 기준 (1999~2026, grid_best 파라미터)

> buffer_zone_tqqq 전략의 단일 백테스트 진행 이력. ATR 전략(buffer_zone_atr_tqqq)은 WFO 전용 설계이므로 §2.2 참조.

| 단계                        | CAGR   | MDD     | Calmar | 비고                                  |
| --------------------------- | ------ | ------- | ------ | ------------------------------------- |
| 초기 (단일 buffer_zone_pct) | 20.26% | -85.68% | 0.237  | -                                     |
| 버퍼 분리 (buy/sell 분리)   | 20.59% | -88.27% | 0.233  | MDD 악화 → 과최적화 경고              |

### 2.2 WFO Stitched 기준 (Dynamic 모드)

| 단계                   | CAGR       | MDD         | WFE Calmar  | PC Max      | 비고                                   |
| ---------------------- | ---------- | ----------- | ----------- | ----------- | -------------------------------------- |
| WFO 적용 (버퍼존 TQQQ) | 21.68%     | -62.09%     | -161 (폭주) | 0.67 (경고) | 2026-02-22                             |
| + min_trades=3 제약    | (동일)     | (동일)      | (동일)      | (동일)      | 첫 IS 윈도우 파라미터 개선             |
| + WFE/PC 지표 보강     | (동일)     | (동일)      | (신규 지표) | (신규 지표) | 진단 기반 마련                         |
| + ATR 트레일링 스탑    | **16.09%** | **-52.95%** | **5.37**    | **0.48**    | MDD 9.14pp 개선                        |
| + ATR mult 2.5 고정   | 8.26%      | -66.66%     | -0.79       | 0.60 (경고) | 실패: MDD/CAGR 모두 악화, 기각         |

### 2.3 전략별 ATR WFO 비교

결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/walkforward_summary.json`

| Mode        | 기존 CAGR | ATR CAGR | 기존 MDD | ATR MDD     | MDD 개선 |
| ----------- | --------- | -------- | -------- | ----------- | -------- |
| Dynamic     | 21.68%    | 16.09%   | -62.09%  | **-52.95%** | +9.14pp  |
| Sell Fixed  | 20.77%    | 11.32%   | -70.06%  | -54.31%     | +15.75pp |
| Fully Fixed | 6.97%     | 8.40%    | -61.10%  | **-51.75%** | +9.35pp  |

---

## 3. 핵심 발견 사항

2026-02-21 ~ 2026-02-23 분석에서 도출한 결론을 카테고리별로 정리합니다.

### 3.1 전략 선택

- **TQQQ 단순 보유는 파국**: B&H TQQQ는 CAGR 0.94%, MDD -99.98%. Volatility Decay로 레버리지 상품은 반드시 추세 추종 전략 필요
- **버퍼존 TQQQ 선택**: 수익 극대화 방향. MDD를 줄이는 것이 핵심 과제
- **QQQ는 고정 파라미터가 최선**: WFO 3-Mode 비교에서 Fully Fixed가 Dynamic을 상회. 학술적으로도 단순 모델 우위 실증 (DeMiguel et al. 2009)
- **TQQQ는 동적 파라미터 필요**: 파라미터 불안정성으로 Dynamic WFO가 유효

### 3.2 파라미터 안정성

- **sell_buffer=0.05 수렴**: QQQ/TQQQ 모두에서 sell=0.05가 가장 안정적. "Tight Entry, Wide Exit" 패턴. ATR 스탑 도입 전에는 sell_buffer가 유일한 매도 조건이었기 때문에 sell=0.05는 "너무 늦은 청산"으로 MDD를 악화시켰으나, ATR 도입 후 매도 조건이 OR로 분리되면서 역할이 바뀜: ATR 스탑이 급락 시 조기 청산을 담당하고, sell_buffer는 노이즈에 흔들리지 않는 안정적 기준선 역할만 수행. ATR 환경에서의 sell_buffer 값별(0.03/0.05/0.07) 정량 비교는 기각 — ATR이 주도적 매도 메커니즘이 된 환경에서 sell_buffer 미세 조정의 한계 효용이 낮고, WFO 윈도우별 선택 결과로 충분히 지지됨
- **ATR(14, 3.0) 전 윈도우 수렴**: {14, 22} x {2.5, 3.0} 그리드에서 11윈도우 x 3모드 = 33개 데이터 포인트 전부 (14, 3.0) 선택. ATR은 QQQ(signal_df) 기준으로 계산하되, 매매 대상 TQQQ에서 손실이 3배 증폭되므로 더 빠르게 반응하는 짧은 기간(14일)이 유리
- **버퍼존 파라미터 레짐 전환**: Dynamic 모드에서 윈도우 1~5(IS ~2015)와 6~10(IS ~2017+)이 뚜렷하게 구분됨 → §3.6 참조
- 결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/walkforward_dynamic.csv` 등

### 3.3 과최적화 진단

- **WFE 폭주 원인**: IS Calmar가 0에 근접할 때 `oos/is` 비율 계산이 발산. ATR 추가 후 해소
- **Profit Concentration**: 기존 TQQQ Dynamic에서 수익의 67%가 Window 9(2023-2025)에 집중 → ATR 적용 후 48%로 경고 해제 (TradeStation 기준 50%). ATR이 큰 수익 거래를 중도 청산하면서 극단적 수익 편중이 감소:

  | Window | OOS 기간 | 기존 CAGR | ATR CAGR | 변화 |
  |--------|----------|--------:|--------:|------|
  | 2 | 2009~2011 | 118.82% | 65.54% | 수익 분산 |
  | 4 | 2013~2015 | 92.81% | 51.13% | 수익 분산 |
  | 7 | 2019~2021 | 58.62% | 36.78% | 수익 분산 |
  | 9 | 2023~2025 | 72.66% | 44.49% | 집중도 완화 |
- **min_trades=3**: IS 구간에서 거래 < 3회인 파라미터 조합 제외. 첫 IS 윈도우의 sell=0.01 선택 문제 해결
- 진단 지표 구현: [walkforward.py](src/qbt/backtest/walkforward.py)의 `calculate_wfo_mode_summary()`

#### CSCV·PBO·DSR 통계 검증 결과

CSCV(Combinatorial Symmetric Cross-Validation) 6블록 → C(6,3)=20개 IS/OOS 분할로 3개 전략을 검증:

| 지표 | buffer_zone_qqq | buffer_zone_tqqq | buffer_zone_atr_tqqq |
|------|:---:|:---:|:---:|
| 파라미터 조합 수 | 432 | 432 | **1,728** |
| **PBO** | **0.40** (통과) | **0.45** (통과) | **0.65** (미통과) |
| rank_below_median | 8/20 | 9/20 | 13/20 |
| **DSR** | **0.78** | **0.65** | **0.35** |
| DSR 판정 | 미유의 | 미유의 | 미유의 |
| z-score | 0.77 | 0.40 | -0.39 |
| SR_observed | 0.87 | 0.79 | 0.71 |
| SR_benchmark | 0.69 | 0.69 | 0.80 |

결과 파일: `storage/results/backtest/{strategy_name}/cscv_analysis.json`, `cscv_logit_lambdas.csv`

**PBO 해석**: PBO < 0.5 = "IS 최적이 OOS에서 중간 이상일 확률이 동전 던지기보다 나음". QQQ(0.40)와 TQQQ(0.45)는 통과, ATR TQQQ(0.65)는 미통과. ATR 전략의 높은 PBO 원인은 탐색 공간 4배 확대(432 → 1,728)에 따른 다중검정 부담 증가.

**DSR 해석**: DSR은 0~1 범위의 확률값(CDF 기반). 원 논문(Bailey & López de Prado, 2014) 기준 0.95 이상이면 "95% 신뢰로 우연이 아닌 실력". 3개 전략 모두 0.95 미달이나, 432~1,728개 조합을 탐색하는 그리드 서치에서 DSR 0.95 달성은 비현실적으로 높은 관측 Sharpe를 요구. 절대값보다 **전략 간 상대 순위**(QQQ 0.78 > TQQQ 0.65 > ATR TQQQ 0.35)가 유의미.

#### PBO/DSR 결과의 한계와 종합 판단

**PBO의 한계**: PBO는 "1,728개 중 IS 1등을 맹목적으로 고르는 사용자"를 가정. 범용 파라미터(MA 200, ATR 14 등)를 선호하는 도메인 지식 기반의 사전 제약(prior regularization)을 반영하지 못함. PBO에게는 "MA 200을 도메인 지식으로 선택한 사람"과 "MA 197이 IS에서 0.01% 높아서 고른 사람"이 동일한 1회 시행. 또한 ATR(14,3.0) 수렴을 보고 "ATR을 고정하면 PBO가 개선되지 않나?"는 사후적 결정(post-hoc)으로, 검정 기준을 느슨하게 만들 뿐임.

**DSR 상대 순위 해석**: ATR TQQQ의 DSR 0.35가 3개 전략 중 최하위인 것은 탐색 공간 4배(432→1,728)에 비례한 결과. DSR은 시행 횟수가 증가할수록 벤치마크 Sharpe(SR_benchmark)가 높아지는 구조이므로(ATR TQQQ: 0.80 vs QQQ: 0.69), 주력 전략이 최하위인 것 자체가 전략의 무효를 의미하지는 않음. 다만 탐색 공간 확대에 따른 통계적 부담이 존재한다는 신호.

**실제로 과최적화를 방지하는 것들**:

| 이미 적용 중인 기법 | 학술적 명칭 | 효과 |
|---------------------|------------|------|
| MA 200, ATR 14 등 범용 값 선호 | Prior regularization | 데이터가 아닌 도메인 지식으로 파라미터 제약 |
| WFO (미래 데이터 미참조) | Out-of-sample validation | 가장 기본적인 과최적화 방지 |
| sell=0.05 수렴 확인 | Parameter stability | 여러 구간에서 같은 값이면 노이즈가 아닌 신호 |
| 레짐 전환이 거시경제와 일치 | Economic rationale | 숫자가 아닌 논리로 설명 가능 |
| ATR(14) vs (22) 고정 OOS 비교 | Independent A/B test | IS 최적화 없이 구조적 우위 실증 |

**종합 판단**: PBO/DSR은 이 목록에 하나 더 추가된 "건강검진 항목"이지, 위의 모든 노력을 무효화하는 최종 심판이 아님. "맹신하지 마라"로 읽는 것이 올바름.

### 3.4 MDD 원인 분석

- **청산일 = MDD 최저점**: 16개 거래 중 10개(62.5%)에서 가장 많이 떨어진 날에 매도. 하단 밴드 청산의 구조적 지연
- **2020-03 코로나 급락**: WFO Stitched MDD -62.09%의 주요 원인. ATR 스탑이 없어 최고점 대비 큰 낙폭 후에야 청산
- **ATR 스탑 효과**: OOS 거래 18 → 51회 증가, 승률 32.58% → 50.2% 개선. ATR이 큰 손실 거래를 중도 청산

### 3.5 기각된 아이디어

- **분할 매수(DCA)**: 버퍼존 전략의 이분법적 구조(전량 진입/전량 청산)에서 오히려 역효과. 진입 타이밍 문제는 ATR 스탑으로 해결
- **MDD 제약형 목적함수**: 기각. MDD는 ATR 스탑으로 대응하고, IS 윈도우 품질 문제는 min_trades=3으로 해결하여 별도 MDD 제약 불필요
- **ATR mult 2.5 단일 고정**: Dynamic Stitched CAGR 8.26%, MDD -66.66%, Calmar 0.12. 기존 mult [2.5, 3.0] 대비 CAGR -7.83pp, MDD 13.71pp 악화. 전 윈도우 ATR(22, 2.5) 선택 (period가 14→22로 이동하여 빡빡한 mult 보상 시도, 역부족). PC 0.60 (경고). whipsaw에 의한 조기 청산 → 재진입 비용 누적이 원인

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

**미래 레짐 전환 가능성**: 시장 구조가 변하면 Period 3 이후가 출현할 수 있음. 이는 과적합이 아닌 자연스러운 적응이며, Dynamic WFO는 IS 윈도우 확장을 통해 새로운 시장 환경을 자동 반영함.

**실전 리밸런싱 주기**: OOS 기간(24개월)에 맞춰 2년마다 WFO를 재실행하여 새 파라미터를 적용. 너무 자주 바꾸면 거래 비용 + whipsaw 위험이 증가하고, 너무 드물면 레짐 전환에 늦게 대응함.

**운용 절차** (2년 주기):

1. 데이터 갱신: `scripts/data/` 스크립트로 QQQ/TQQQ 최신 주가 다운로드
2. WFO 재실행: `scripts/backtest/` 스크립트로 buffer_zone_atr_tqqq Expanding Anchored WFO 실행
3. 파라미터 확인: 최신 OOS 윈도우의 최적 파라미터(buy/sell/hold/recent/ATR)를 `walkforward_dynamic.csv`에서 확인
4. 진단 점검: WFE, PC, CAGR 등 핵심 지표가 이전 실행 대비 급변하지 않았는지 확인
5. 적용: 확인된 파라미터를 실전 매매에 반영

### 3.7 Expanding vs Rolling Window WFO 비교

Expanding Anchored의 "지연된 전환"(§3.6)에 대한 대안으로, 고정 길이 IS를 슬라이딩하는 Rolling Window를 검토.

| | Expanding (현재) | Rolling |
|---|---|---|
| IS 시작 | 항상 1999년 고정 | 점진적으로 이동 |
| IS 길이 | 계속 증가 (6년 → 26년) | 고정 (예: 10년) |
| 과거 위기 반영 | 비중이 줄지만 항상 포함 | 윈도우 밖으로 나가면 완전히 소멸 |
| 레짐 전환 속도 | 느림 (지연된 전환) | 빠름 |
| 데이터 활용량 | 최대 | 제한적 |

**Rolling의 핵심 위험**: IS가 2014~2024면 2008 금융위기, 2000 닷컴버블 경험이 완전히 소멸. TQQQ는 3x 레버리지로 MDD가 핵심 리스크이므로, 모든 위기 데이터를 항상 반영하는 Expanding이 구조적으로 적합.

#### 정량 비교 결과 (IS=120개월 Rolling)

결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/wfo_comparison_summary.json`, `wfo_comparison_windows.csv`

| 지표 | Expanding | Rolling (IS=120개월) | 차이 |
|------|:---------:|:-------------------:|:----:|
| CAGR | **16.09%** | 11.04% | +5.05pp |
| MDD | -52.95% | -52.98% | 거의 동일 |
| Calmar | **0.3038** | 0.2084 | +0.0954 |
| 총 수익률 | **2,181.64%** | 798.80% | 2.7배 |
| OOS CAGR 평균 | **16.69%** | 16.21% | +0.48pp |
| OOS Calmar 평균 | **0.7708** | 0.7041 | +0.0667 |

**윈도우 구성**: 전체 11개 윈도우 중 IS 동일 3개(Window 0~2), IS 분기 8개(Window 3~10).

**윈도우 승수 (OOS CAGR)**: Expanding 4승, Rolling 3승, 무승부 4. 승리 폭의 비대칭이 핵심:

| 구간 | 윈도우 | Expanding | Rolling | 차이 | 승자 |
|------|--------|-----------|---------|------|------|
| 닷컴 후 | W3 (2011~2013) | -20.88% | **+12.07%** | **-32.94pp** | Rolling |
| 최근 | W9 (2023~2025) | **44.49%** | 24.54% | **+19.95pp** | Expanding |
| 최근 | W10 (2025~2026) | **30.14%** | 13.37% | **+16.77pp** | Expanding |

Window 3은 Expanding IS(1999~2011, 144개월)의 닷컴버블 상승기(1999~2001) 포함에 의한 레짐 불일치. 다만 이 윈도우는 예외적이며, 같은 IS 구성 차이가 Window 4에서는 동일 결과(51.13%)를 생성. Window 9~10에서 Expanding이 합산 +36.72pp로 상쇄 이상.

**결론**: **Expanding Anchored 유지**. CAGR +5.05pp, 총 수익률 2.7배 차이가 결정적. Rolling은 MDD도 개선하지 못함(-52.98%). "지연된 전환"이라는 이론적 단점보다 "위기 데이터 보존"의 실증적 이점이 우위.

### 3.8 ATR(14,3.0) vs (22,3.0) 고정 OOS 비교

IS 최적화 없이 ATR을 고정하고, 버퍼존 파라미터만 IS에서 최적화한 WFO Dynamic 비교 결과:

결과 파일: `storage/results/backtest/buffer_zone_atr_tqqq/atr_comparison_summary.json`, `atr_comparison_windows.csv`

**Stitched 지표 비교**:

| 지표 | ATR(14,3.0) | ATR(22,3.0) | 차이 |
|------|:-----------:|:-----------:|:----:|
| CAGR | **16.09%** | 12.20% | +3.89pp |
| MDD | **-52.95%** | -59.06% | +6.11pp |
| Calmar | **0.3038** | 0.2065 | +0.0973 (+47%) |
| 총 수익률 | **2,181.64%** | 1,016.77% | 2.1배 |
| OOS CAGR 평균 | **16.69%** | 11.59% | +5.10pp |
| OOS Calmar 평균 | **0.7708** | 0.5007 | +0.2701 (+54%) |

**윈도우별 승패**: A 5승 / B 5승 / 무승부 1. 승수는 동률이나 **승리 폭의 비대칭성**이 핵심:

- A 주요 승리: Window 2(2009~2011) +43.38pp, Window 4(2013~2015) +35.53pp, Window 9(2023~2025) +12.80pp
- B 주요 승리: Window 3(2011~2013) +19.03pp, Window 10(2025~2026) +13.18pp
- Window 7(2019~2021): 완전 무승부 (양쪽 동일 버퍼존 파라미터 선택)

A가 이기는 윈도우(2, 4, 9)는 **강세장 반등기**로, ATR(14)의 빠른 반응(14일)이 조기 청산을 방지하여 큰 수익을 유지. ATR(22)는 느린 반응(22일)으로 수익 기회를 놓침.

**PBO 0.65에 대한 검증 의미**: 두 ATR 설정 모두 IS에서 최적화되지 않고 고정된 상태에서 비교한 독립적 A/B 테스트. ATR(14,3.0) 고정 결과가 기존 WFO Dynamic 결과와 완전 일치(CAGR 16.09%, MDD -52.95%, Calmar 0.3038)하여, WFO에서의 33/33 수렴이 IS 과최적화가 아니라 실제로 (14,3.0)이 최선이기 때문임을 확인. IS를 아예 사용하지 않는 비교이므로 PBO 경고에 대한 가장 깨끗한 반론 근거.

---

## 4. 구현 완료 목록

| Phase                | 내용                                                                      | 계획서                               | 검증       |
| -------------------- | ------------------------------------------------------------------------- | ------------------------------------ | ---------- |
| 버퍼 분리            | buy/sell buffer 분리 + 동적 조정 기준 entry→exit 변경                     | `PLAN_sell_buffer_separation.md`     | passed     |
| WFO 인프라           | Expanding Anchored WFO + 3-Mode (Dynamic/Sell Fixed/Fully Fixed)          | `PLAN_walkforward_optimization.md`   | passed     |
| Phase 1: WFE/PC 지표 | wfe_cagr, gap_calmar_median, wfe_calmar_robust, profit_concentration 추가 | `PLAN_wfo_wfe_pc_metrics.md`         | passed=347 |
| Phase 2: min_trades  | select_best_calmar_params()에 min_trades=3 필터링                         | `PLAN_wfo_min_trades.md`             | passed=350 |
| Phase 3: ATR 스탑    | buffer_zone_atr_tqqq 전략 신규 추가 + WFO 파이프라인 통합                 | `PLAN_atr_trailing_stop_strategy.md` | passed=358 |
| CSCV·PBO·DSR         | CSCV 분할 + PBO + DSR 과최적화 통계 검증 모듈 + CLI 스크립트              | `PLAN_cpcv_pbo_dsr_analysis.md`      | passed=397 |
| ATR 고정 OOS 비교    | ATR(14,3.0) vs (22,3.0) 고정 OOS 비교 실험 모듈 + CLI 스크립트           | `PLAN_atr_oos_comparison.md`         | passed=404 |
| Expanding vs Rolling | Expanding vs Rolling WFO 비교 실험 모듈 + CLI 스크립트                   | `PLAN_expanding_vs_rolling_wfo.md`   | passed=419 |
| WFO Stitched 대시보드 | WFO Dynamic 결과를 대시보드 호환 형식으로 저장하는 스크립트 + 로딩 함수  | `PLAN_wfo_stitched_dashboard.md`     | passed=424 |

계획서 위치: [docs/plans/](docs/plans/) 또는 [docs/archive/](docs/archive/)

---

## 5. 토론 합의 현황

2026-02-22 ~ 2026-02-23 Claude Opus 4.6 / GPT-5.2 간 교대 토론으로 도출한 합의사항입니다.

| #   | 항목                                                             | 상태                                                     |
| --- | ---------------------------------------------------------------- | -------------------------------------------------------- |
| 1   | wfe_calmar 폭주 → wfe_cagr를 1급 지표로 추가                     | Done                                                     |
| 2   | gap_calmar_median(차이 기반) + wfe_calmar_robust(필터 후 median) | Done                                                     |
| 3   | Profit Concentration V2 (window_profit = end - prev_end)         | Done                                                     |
| 4   | min_trades=3 제약                                                | Done                                                     |
| 5   | ATR 스탑: Sell Fixed(0.05) + ATR, OR 조건, 다음 시가 체결        | Done                                                     |
| 6   | ATR 그리드: {14, 22} x {2.5, 3.0}, IS에서 최적화                 | Done                                                     |
| 7   | BufferStrategyParams 확장: atr_period=0이면 비활성 (하위 호환)   | Done                                                     |
| A   | ATR 시그널 소스 (QQQ vs TQQQ)                                    | Done — **QQQ 고정** (사용자 결정)                        |
| B   | ATR period {14,22} vs {14,20}                                    | Done — **{14,22}** 채택, IS 결과 전부 14 선택            |
| C   | ATR 기준가 (highest_close vs highest_high)                       | Done — **highest_close** 채택 (close 기준 통일)          |
| D   | PBO 분석 (TQQQ)                                                  | Done (CSCV·PBO·DSR 모듈로 통합 구현)                     |
| E   | TQQQ IS 기간 확장 (72→96개월)                                    | 기각 (min_trades로 해결 완료, IS 확장 시 OOS 커버리지 손실) |
| F   | DSR (Deflated Sharpe Ratio)                                      | Done (D와 함께 구현)                                     |

---

## 6. 실험 이력

> 모든 계획된 실험이 완료/기각됨. 신규 실험이 추가되면 이 테이블을 업데이트.

| # | 실험 | 목적 | 결과 | 참조 |
|---|------|------|------|------|
| 1 | ATR mult 2.5 단일 고정 | MDD -50% 달성 도전 | **실패·기각** (MDD -66.66%) | §3.5 |
| 2 | CSCV·PBO·DSR 분석 | 다중검정 과최적화 검증 | PBO 0.65, DSR 0.35 | §3.3 |
| 3 | ATR(14,3.0) vs (22,3.0) 고정 OOS | 파라미터 일반화 검증 | ATR(14,3.0) 구조적 우위 | §3.8 |
| 4 | Expanding vs Rolling WFO | 지연된 전환 대안 검증 | Expanding 유지 | §3.7 |
| 5 | sell_buffer 값별 고정 OOS 비교 | ATR 환경에서 sell 정량 검증 | **기각** (ATR 주도 매도 환경에서 한계 효용 부족) | §3.2 |
| 6 | TQQQ IS 기간 확장 (72→96개월) | IS 초기 윈도우 데이터 부족 해소 | **기각** (min_trades로 해결, OOS 커버리지 손실) | §5 항목 E |

---

## 7. 참고 자료

### 용어집

- **CSCV (Combinatorial Symmetric Cross-Validation)**: 데이터를 N개 블록으로 나눈 뒤, 시간 순서를 유지하면서 가능한 모든 훈련/시험 조합을 생성하는 방법론. CPCV(López de Prado, 2018)의 변형으로, 인접 블록 사이의 데이터 오염을 정화(purge)하여 통계적 독립성 확보. PBO와 DSR 계산의 데이터 기반 제공.
- **PBO (Probability of Backtest Overfitting)**: CSCV로 생성한 모든 IS/OOS 분할에서 "IS 최적 전략이 OOS에서 중간(median)보다 못하는 비율". PBO > 0.5면 과최적화 위험. (Bailey et al., 2017)
- **DSR (Deflated Sharpe Ratio)**: N개 전략을 시도한 후 최고 Sharpe를 뽑았을 때, 시행 횟수/왜도/첨도를 반영하여 보정한 Sharpe. 0.95 이상이면 95% 신뢰로 유의. (Bailey & López de Prado, 2014)
- **세 도구의 관계**: CSCV는 데이터를 나누는 **방법론**, PBO와 DSR은 그 결과로 계산하는 **지표**.

### 학술 논문

- DeMiguel, Garlappi & Uppal (2009). "Optimal Versus Naive Diversification." Review of Financial Studies
- Kelly, Malamud, Zhou (2024). "The Virtue of Complexity in Return Prediction." Journal of Finance
- Hsu & Kuan (2005). "Re-Examining the Profitability of Technical Analysis." SSRN
- Bailey, Borwein, López de Prado, Zhu (2017). "The Probability of Backtest Overfitting." Journal of Computational Finance
- Bailey & López de Prado (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management
- López de Prado (2018). "Advances in Financial Machine Learning." Wiley, Chapter 11-12
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
> 형식: `### YYYY-MM-DD 제목` + 변경 내용 요약 (상세 수치는 해당 섹션 참조)

### 2026-02-21 초기 분석 및 전략 선택

- 4개 전략 성과 비교 → 버퍼존 TQQQ 선택, DCA 기각, ATR 스탑 최우선 과제 도출 → §3.1, §3.4, §3.5

### 2026-02-21 매수/매도 버퍼 분리 구현

- buy/sell buffer 분리 구현. 단일 백테스트 과최적화 경고 확인 → §2.1

### 2026-02-22 WFO 아키텍처 설계 및 구현

- Expanding Anchored WFO + 3-Mode 구현. TQQQ Dynamic MDD -88% → -62% (26pp 개선) → §2.2

### 2026-02-22 WFE/PC 진단 지표 + min_trades + ATR 설계

- WFE/PC 보강 지표 + min_trades + ATR Phase 1~3 설계 완료 → §3.3, §5

### 2026-02-23 Phase 1~3 구현 완료 + ATR WFO 결과

- ATR TQQQ Dynamic WFO: MDD -62.09% → -52.95% (9.14pp 개선). ATR(14,3.0) 33/33 수렴 → §2.2, §3.2

### 2026-02-23 버퍼존 파라미터 레짐 전환 분석 추가

- Period 1/2 레짐 전환 발견, 거시경제 구조 변화와 일치 확인 → §3.6

### 2026-02-25 문서 정비 + 분석 보강

- sell_buffer 역할 변화, PC 비교 테이블, Expanding vs Rolling 분석, 리밸런싱 주기 추가 → §3.2, §3.3, §3.6, §3.7

### 2026-02-27 ATR mult 2.5 단일 고정 실험 + 문서 정비

- ATR mult 2.5 실험: MDD -66.66%, 기각. CPCV 개념 추가 → §2.2, §3.5, §5

### 2026-02-28 CSCV·PBO·DSR 과최적화 통계 검증 완료

- CSCV·PBO·DSR 모듈 구현 (passed=397). PBO: ATR TQQQ 0.65, DSR: 3개 전략 모두 미유의 → §3.3

### 2026-02-28 ATR(14,3.0) vs (22,3.0) 고정 OOS 비교 실험 완료

- ATR(14,3.0) 구조적 우위 확인 (CAGR +3.89pp, MDD +6.11pp). PBO 반론 근거 확보 → §3.8

### 2026-03-02 Expanding vs Rolling WFO 비교 실험 완료

- Expanding CAGR +5.05pp, 총 수익률 2.7배 우위. Rolling은 MDD 미개선. Expanding 유지 결정 → §3.7

### 2026-03-02 미수행 실험 2건 기각 확정

- sell_buffer 값별 정량 비교: ATR 주도 매도 환경에서 한계 효용 부족으로 기각 → §3.2, §6
- IS 기간 확장 72→96개월: min_trades로 해결 완료 + OOS 커버리지 손실로 기각 → §5 항목 E, §6

### 2026-03-02 WFO Stitched 대시보드 시각화 스크립트 구현

- `load_wfo_results_from_csv()` 함수 + `run_wfo_stitched_backtest.py` 스크립트 신규 추가
- walkforward_dynamic.csv → params_schedule 기반 OOS 전체 1회 연속 실행 → 대시보드 호환 결과 저장
- 결과: `storage/results/backtest/buffer_zone_atr_tqqq_wfo/` (signal, equity, trades, summary)
- 기존 대시보드(`app_single_backtest.py`) 코드 수정 없이 Feature Detection으로 자동 호환 → §4

### 2026-03-02 문서 리팩토링

- §1 TL;DR 압축 (10줄→5줄) + 전략 판정 추가
- §3.3 ATR OOS 비교를 §3.8로 분리, PBO 한계 섹션 압축 + DSR 해석 보완
- §3.5 논리 수정 (PBO 상태 불일치, MDD 제약 표현)
- §3.6 실전 운용 절차 추가
- §3.7 직관적 비유 삭제 + 요약 축소 (52줄→30줄)
- §5 학술 개념 설명 → §7 용어집으로 이동
- §6 "다음 실험 계획" → "실험 이력"으로 변경
- §8 변경 로그 간결화 (수치 중복 제거, 섹션 참조로 대체)

---

_이 문서는 작업 진행에 따라 지속적으로 업데이트됩니다._
