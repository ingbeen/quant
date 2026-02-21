# 버퍼존 전략 (TQQQ) 개선 작업 로그

> 작성 시작: 2026-02-21
> 목적: 버퍼존 TQQQ 전략의 성과 분석 및 단계적 개선을 위한 히스토리 문서
> 참고 대상: 이 프로젝트를 분석하는 모든 AI 모델 및 개발자
> 업데이트 방식: 새로운 분석/논의/개선이 있을 때마다 하단에 섹션 추가

## 연구 방법론

이 문서의 모든 연구 및 분석은 **웹 리서치(Web Research)**를 기본으로 합니다.
- 이론적 근거: 학술 논문, 금융 리서치 기관 자료, ETF 발행사 공시 등 외부 출처 참조
- 실증 분석: 프로젝트 내 실제 데이터(equity.csv, trades.csv, grid_results.csv 등)와 비교 검증
- 결론 도출: 웹 리서치 + 코드/데이터 분석을 통합해 근거 있는 방향 제시

---

## 목차

1. [프로젝트 구조 및 도메인 이해](#1-프로젝트-구조-및-도메인-이해)
2. [버퍼존 전략 상세 설명](#2-버퍼존-전략-상세-설명)
3. [백테스트 핵심 규칙](#3-백테스트-핵심-규칙)
4. [데이터 소스 및 파일 구조](#4-데이터-소스-및-파일-구조)
5. [Session 1 — 전략별 성과 비교 분석](#5-session-1--전략별-성과-비교-분석)
6. [Session 2 — 분할 매수 도입 가능성 연구](#6-session-2--분할-매수-도입-가능성-연구)
7. [Session 3 — 시계열 데이터 심층 분석 및 개선 방향](#7-session-3--시계열-데이터-심층-분석-및-개선-방향)
8. [현재까지 도출된 개선 방향 요약](#8-현재까지-도출된-개선-방향-요약)
9. [앞으로의 개선 계획](#9-앞으로의-개선-계획)
10. [Session 4 — AI 모델 간 토론](#10-session-4--ai-모델-간-토론-외부-ai-분석-검토-및-반론)
11. [Session 5 — 매수/매도 버퍼 분리 구현 완료](#11-session-5--매수매도-버퍼-분리-구현-완료)

---

## 1. 프로젝트 구조 및 도메인 이해

### 1.1 프로젝트 개요

- **프로젝트명**: QBT (Quant BackTest)
- **목적**: 주식 백테스팅 CLI 도구
- **기술 환경**: Python 3.12, Poetry, pandas, yfinance, Plotly, Streamlit
- **타입 체커**: PyRight (strict mode)

### 1.2 디렉토리 구조 (핵심 경로)

```
quant/
├── src/qbt/
│   ├── backtest/
│   │   ├── constants.py          # 백테스트 전용 상수 (슬리피지, 기본 파라미터 등)
│   │   ├── types.py              # TypedDict 정의 (SummaryDict, BestGridParams 등)
│   │   ├── analysis.py           # 이동평균 계산, 성과 지표 분석
│   │   └── strategies/
│   │       ├── buffer_zone_helpers.py   # 버퍼존 전략 핵심 로직 (공유)
│   │       ├── buffer_zone_tqqq.py      # 버퍼존 (QQQ 시그널 + TQQQ 매매)
│   │       ├── buffer_zone_qqq.py       # 버퍼존 (QQQ 시그널 + QQQ 매매)
│   │       └── buy_and_hold.py          # Buy & Hold 벤치마크
│   └── utils/
│       ├── parallel_executor.py   # 병렬 처리
│       └── meta_manager.py        # 실행 메타데이터
├── scripts/
│   └── backtest/                  # CLI 스크립트 (argparse, 로거 초기화)
├── storage/
│   └── results/backtest/
│       ├── buffer_zone_tqqq/      # 결과 파일 저장 위치
│       │   ├── signal.csv
│       │   ├── equity.csv
│       │   ├── trades.csv
│       │   ├── summary.json
│       │   └── grid_results.csv
│       ├── buffer_zone_qqq/
│       ├── buy_and_hold_qqq/
│       └── buy_and_hold_tqqq/
└── storage/stock/
    ├── QQQ_max.csv                # QQQ 전체 기간 데이터 (시그널 및 매매 소스)
    └── TQQQ_synthetic_max.csv     # TQQQ 합성 데이터 (1999년부터 역산된 시뮬레이션 데이터)
```

### 1.3 아키텍처 원칙

- **CLI 계층** (`scripts/`): argparse 파싱, 로거 초기화, `@cli_exception_handler` 데코레이터 사용, 비즈니스 로직 호출
- **비즈니스 로직 계층** (`src/qbt/`): 핵심 도메인 로직, ERROR 로그 금지, 예외는 `raise`로 전파
- **계층 분리 원칙**: CLI에서만 입출력 처리, 비즈니스 로직은 순수 함수 스타일

---

## 2. 버퍼존 전략 상세 설명

### 2.1 전략 개념

버퍼존 전략은 **이동평균(MA) 기반 추세 추종 전략**입니다.
이동평균선 주변에 "버퍼존(완충 구간)"을 설정하고, 가격이 이 구간을 명확히 이탈할 때만 거래합니다.

핵심 철학: **"노이즈를 걸러내고 명확한 추세에서만 진입"**

**신호 방향 (절대 규칙):**
- **매수 신호**: 가격이 상단 밴드를 **상향 돌파** (`prev_close <= upper_band AND close > upper_band`)
- **매도 신호**: 가격이 하단 밴드를 **하향 돌파** (`prev_close >= lower_band AND close < lower_band`)
- 매수는 hold_days 상태머신 적용 (돌파 후 N일 유지 확인), 매도는 hold_days 없이 즉시 다음날 시가에 체결

### 2.2 밴드 계산

```
upper_band = MA × (1 + buffer_zone_pct)
lower_band = MA × (1 - buffer_zone_pct)
```

예시 (MA=100, buffer_zone_pct=0.04):
- 상단 밴드 = 104 → 이 위로 올라오면 매수 신호
- 하단 밴드 = 96 → 이 아래로 내려가면 매도 신호

### 2.3 버퍼존 TQQQ vs 버퍼존 QQQ 차이

| 구분 | 버퍼존 TQQQ | 버퍼존 QQQ |
|---|---|---|
| 시그널 소스 | QQQ 가격 | QQQ 가격 |
| 실제 매매 대상 | TQQQ 합성 데이터 | QQQ |
| 특징 | QQQ 추세로 판단, TQQQ로 레버리지 수익 | 시그널=매매 동일 |
| 데이터 파일 | signal: QQQ_max.csv / trade: TQQQ_synthetic_max.csv | 둘 다 QQQ_max.csv |

**핵심**: 버퍼존 TQQQ는 QQQ의 이동평균 신호로 진입/청산 타이밍을 잡고, 실제 자산은 3배 레버리지인 TQQQ 합성 데이터로 매매합니다. 시그널 소스(QQQ)와 매매 소스(TQQQ)가 분리되어 있기 때문에 `extract_overlap_period`를 통해 기간을 맞춥니다.

### 2.4 전략 파라미터

```python
# buffer_zone_tqqq.py 기준 (grid_best 기준 최적 파라미터)
ma_window        = 150      # EMA 기간 (일)
ma_type          = "ema"    # 이동평균 유형
buffer_zone_pct  = 0.04     # 버퍼존 비율 (0.04 = 4%)
hold_days        = 3        # 유지 조건 일수
recent_months    = 2        # 동적 조정 기간 (개월)
initial_capital  = 10_000_000  # 초기 자본 (원)
```

### 2.5 파라미터 결정 폴백 체인

```
1순위: OVERRIDE 상수 (코드에 하드코딩된 강제 값)
2순위: grid_results.csv 의 CAGR 1위 파라미터 (load_best_grid_params)
3순위: DEFAULT 상수 (constants.py 기본값)
```

이 체인은 `resolve_buffer_params()` → `resolve_params()` 구조로 구현됩니다.

### 2.6 동적 파라미터 조정 메커니즘

최근 `recent_months` 기간 내 매수 횟수(`recent_buy_count`)가 늘어날수록 버퍼존과 유지 조건을 자동으로 강화합니다:

```python
adjusted_buffer_pct  = base_buffer_pct + (recent_buy_count × 0.01)
adjusted_hold_days   = base_hold_days  + (recent_buy_count × 1)
```

목적: 연속 매수 발생 시 더 신중하게 진입해서 휩소(whipsaw) 방지.

---

## 3. 백테스트 핵심 규칙

### 3.1 비용 모델

```
매수 체결가 = 시가 × (1 + 0.003)   # SLIPPAGE_RATE = 0.003 (0.3%, 슬리피지+수수료 통합)
매도 체결가 = 시가 × (1 - 0.003)
```

### 3.2 체결 타이밍 (절대 규칙)

lookahead bias 방지를 위한 엄격한 분리:

```
신호 발생: i일 종가 기준으로 상단/하단 밴드 돌파 감지
체결 실행: (i + hold_days + 1)일 시가에 실제 매수/매도
```

예시 (hold_days=3):
- i일: 하단 밴드 이탈 감지 → pending 상태 전환
- i+1 ~ i+3일: 유지 조건 체크 (하단 밴드 아래 유지되는지 확인, 상태머신 방식)
- i+3일 종가: 신호 확정
- i+4일 시가: 실제 체결

### 3.3 Equity 정의

```
Equity = cash + position_shares × close_price
```

- **Final Capital** = 마지막 날 equity (강제청산 없음)
- 현금 보유 구간에서는 equity가 변하지 않음
- 미청산 포지션이 있어도 강제 청산하지 않음 → summary에 `open_position` 포함

### 3.4 Pending Order 정책 (절대 규칙)

- `pending_order`는 단일 변수로만 관리 (리스트 누적 금지)
- 신호일에 생성, 체결일에 실행 후 `None` 초기화
- **Critical Invariant**: pending_order가 존재하는 동안 새 신호 발생 시 `PendingOrderConflictError` 예외

### 3.5 마지막 날 규칙

- N-1일 종가 신호 → N일 시가 정상 체결
- N일 종가 신호 → N+1일 시가가 없으므로 무시
- 강제청산 없음: 마지막 날 포지션 보유 시 summary에 `open_position` 기록

### 3.6 성과 지표 계산

```python
총 수익률  = (final_capital - initial_capital) / initial_capital × 100
CAGR       = ((final_capital / initial_capital) ^ (252 / 총일수)) - 1
MDD        = 자본 곡선에서 누적 최고점 대비 최대 낙폭
승률       = winning_trades / total_trades × 100
```

### 3.7 그리드 서치

- 병렬 처리 기반 (ProcessPoolExecutor)
- 탐색 파라미터: `ma_window`, `buffer_zone_pct`, `hold_days`, `recent_months`
- 결과: `grid_results.csv` (CAGR 내림차순 저장)
- 현재 최적 파라미터는 grid_results.csv 1행에서 자동 로딩

---

## 4. 데이터 소스 및 파일 구조

### 4.1 TQQQ 합성 데이터

TQQQ는 2010년에 상장되었지만, 백테스트는 1999년부터 시작합니다.
`TQQQ_synthetic_max.csv`는 1999년부터 QQQ 가격 데이터를 기반으로 역산한 **합성 데이터**입니다.

이 합성 데이터는 `scripts/tqqq/generate_synthetic.py`로 생성됩니다.

**합성 비용 모델 (`src/qbt/tqqq/simulation.py` — `_calculate_daily_cost`):**
단순 QQQ × 3이 아닌, 실제 3배 레버리지 ETF의 비용 구조를 정밀하게 모델링합니다:

```
일일 비용 = (annual_cost) / 252거래일

annual_cost = leverage_cost + expense_ratio
leverage_cost = (FFR + softplus_spread(a, b, FFR)) × (leverage - 1)
           # 차입 비용 = 연방기금금리 + 동적 스프레드 × 2배 차입분

softplus_spread = softplus(a + b × FFR_pct)
           # Softplus 함수: 저금리→낮은 스프레드, 고금리→높은 스프레드 (S자 곡선)

expense_ratio = TQQQ 운용보수 (월별 실제 데이터)
FFR = 연방기금금리 (월별 실제 데이터)
```

이후 TQQQ 상장 시점(2010년)의 실제 가격으로 스케일링해 병합합니다. 이 과정에서 `tqqq/spread_lab/`의 워크포워드 검증으로 softplus 파라미터를 최적화합니다.

**이 비용 모델은 이 프로젝트의 핵심 강점입니다.** 단순 3배 역산 대비 닷컴버블/금융위기 시기의 비용 현실을 더 정확히 반영합니다.

> **강조**: 합성 TQQQ가 "단순 QQQ × 3"이라는 오해를 방지합니다.
> FFR이 5% 이상이었던 2000~2001년, 2006~2007년 구간에서 동적 스프레드(softplus)가
> 레버리지 비용을 추가로 반영하므로 해당 구간의 합성 수익률이 QQQ × 3보다 더 낮게 산출됩니다.
> 이는 실제 TQQQ 운용 현실과 더 가까운 모델입니다.

### 4.2 결과 파일 구조

```
storage/results/backtest/buffer_zone_tqqq/
├── signal.csv      # OHLC + MA + 상/하단 밴드 + 전일대비% (시그널 데이터)
├── equity.csv      # Date, equity, position, buffer_zone_pct, upper_band, lower_band, drawdown_pct
├── trades.csv      # entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, buffer_zone_pct, hold_days_used, recent_buy_count, holding_days
├── summary.json    # 요약 지표 + 파라미터 + 월별 수익률 + open_position
└── grid_results.csv # 이평기간, 버퍼존, 유지일, 조정기간, 수익률, CAGR, MDD, 거래수, 승률, 최종자본 (CAGR 내림차순)
```

---

## 5. Session 1 — 전략별 성과 비교 분석

**날짜**: 2026-02-21

### 5.1 분석 대상 4개 전략

| 전략명 | 코드 위치 | 설명 |
|---|---|---|
| 버퍼존 전략 (TQQQ) | `strategies/buffer_zone_tqqq.py` | QQQ 시그널 + TQQQ 합성 데이터 매매 |
| 버퍼존 전략 (QQQ) | `strategies/buffer_zone_qqq.py` | QQQ 시그널 + QQQ 매매 |
| Buy & Hold (QQQ) | `strategies/buy_and_hold.py` | QQQ 단순 매수 후 보유 |
| Buy & Hold (TQQQ) | `strategies/buy_and_hold.py` | TQQQ 합성 데이터 단순 매수 후 보유 |

### 5.2 핵심 지표 비교

**분석 기간**: 1999-03-10 ~ 2026-02-17 (약 27년)
**초기 자본**: 10,000,000원

| 지표 | 버퍼존 (TQQQ) | 버퍼존 (QQQ) | Buy & Hold (QQQ) | Buy & Hold (TQQQ) |
|---|---|---|---|---|
| **최종 자본** | 1,442,622,674원 | 159,073,095원 | 138,832,962원 | 12,878,086원 |
| **총 수익률** | **+14,326%** | +1,491% | +1,288% | +29% |
| **CAGR** | **+20.26%** | +10.81% | +10.26% | +0.94% |
| **MDD** | -85.68% | **-42.83%** | -82.96% | -99.98% |
| **Calmar Ratio** | 0.237 | **0.252** | 0.124 | 0.009 |
| **총 거래 수** | 16회 | 14회 | - | - |
| **승률** | 68.75% | **78.57%** | - | - |

> **Calmar Ratio** = CAGR / |MDD|. 높을수록 단위 리스크당 수익이 좋음.

### 5.3 전략별 최적 파라미터 (summary.json에서 확인된 grid_best 기준)

**버퍼존 TQQQ** (`storage/results/backtest/buffer_zone_tqqq/summary.json`):
```json
{
  "ma_window": 150,
  "ma_type": "ema",
  "buffer_zone_pct": 0.04,
  "hold_days": 3,
  "recent_months": 2
}
```

**버퍼존 QQQ** (`storage/results/backtest/buffer_zone_qqq/summary.json`):
```json
{
  "ma_window": 150,
  "ma_type": "ema",
  "buffer_zone_pct": 0.05,
  "hold_days": 2,
  "recent_months": 8
}
```

### 5.4 시장 국면별 비교

| 시장 국면 | 버퍼존 TQQQ | 버퍼존 QQQ | B&H QQQ | B&H TQQQ |
|---|---|---|---|---|
| 닷컴버블 붕괴 (2000~2003) | 현금 보유 (대부분 0%) | 현금 보유 | -83% MDD | 사실상 전멸 |
| 금융위기 (2008~2009) | 대부분 현금 보유 | 대부분 현금 보유 | 극심한 하락 | 극심한 하락 |
| 코로나 (2020.3) | 부분 손실 후 빠른 복구 | 소폭 손실 | -7.29% | -38% |
| 인플레이션 (2022 전체) | 현금 보유 (0%) | 현금 보유 (0%) | 누적 -35%↓ | 누적 -70%↓ |
| 상승장 (2017, 2020~2021) | 월 10~35% 수익 발생 | 월 3~11% 수익 발생 | 완전 참여 | 완전 참여 |

### 5.5 종합 평가

```
절대수익 순위:    버퍼존 TQQQ > 버퍼존 QQQ > B&H QQQ >> B&H TQQQ
위험조정 순위:    버퍼존 QQQ > 버퍼존 TQQQ > B&H QQQ >> B&H TQQQ
심리적 수용성:    버퍼존 QQQ > B&H QQQ > 버퍼존 TQQQ >> B&H TQQQ
```

**주요 인사이트:**
- B&H TQQQ: CAGR 0.94%, MDD -99.98% → 레버리지 상품의 **변동성 감쇄(Volatility Decay)** 효과로 장기 단순 보유는 파국. **TQQQ는 반드시 추세 추종 전략과 결합 필요.**
- 버퍼존 전략의 효용 검증: 버퍼존 QQQ는 B&H QQQ 대비 CAGR 거의 동일(+0.55%p)하지만 MDD를 절반 이하로 감소.

### 5.6 결정: 버퍼존 TQQQ 선택

- 수익 극대화 방향으로 버퍼존 TQQQ를 기반으로 개선 진행
- MDD -85.68%를 줄이는 것이 핵심 목표

---

## 6. Session 2 — 분할 매수 도입 가능성 연구

**날짜**: 2026-02-21
**질문**: 버퍼존은 상승을 확인한 후 들어가는 거라 진입 타이밍이 늦는 단점이 있어. 이러한 상태에서 분할 매수하는 것이 올바른 선택일까?

### 6.1 버퍼존 전략의 진입 타이밍 구조 재확인

```
하단 밴드 이탈 감지 (i일 종가)
→ hold_days(3일) 동안 유지 확인 (상태머신 방식)
→ i+3일 종가에서 신호 확정
→ i+4일 시가에 100% 전량 진입
```

사용자가 지적한 문제: "상승 확인 후 들어가서 이미 많이 오른 상태에서 진입"

### 6.2 웹 리서치 결과

**Vanguard 연구** (Morgan Stanley 인용):
- 시장이 우상향하는 국면에서 일괄 투자(Lump Sum)가 DCA 대비 **75% 확률로 우위**
- 평균 초과수익: 2.4% (전체 주식 포트폴리오 기준)

**UConn 학술 연구**:
- 순수 모멘텀 전략에서 Lump Sum이 DCA보다 **32bp 우위**
- 하락 추세에서만 DCA가 유리

**SetupAlpha 리서치**:
- 3x 레버리지 ETF 전략에서 트레일링 스탑 적용 시 CAGR 23.8%, MDD 38.7% 달성 사례

### 6.3 분할 매수가 오히려 역효과인 이유

| 구분 | 버퍼존 전략 | 분할 매수 |
|---|---|---|
| 전제 | 추세가 확인됨 (상승 중) | 방향이 불확실함 |
| 적합 국면 | 추세 추종 | 변동성 완화 |
| 진입 행동 | 확신하고 전량 진입 | 의심하며 분산 진입 |

> **핵심 논리**: 버퍼존은 "상승 추세 확인 → 진입"이라는 **확신의 신호**입니다.
> 이 신호에 분할 매수를 붙이는 것은 "확인했지만 반은 믿지 못하겠다"는 논리 모순입니다.
> TQQQ 레버리지 특성상 진입 지연은 복리 효과 손실을 의미합니다.

### 6.4 진입 타이밍 문제의 올바른 해결 방향

분할 매수는 "진입 타이밍 지연" 문제를 해결하지 못하고 오히려 악화시킵니다.
올바른 해결 방향은 **신호 생성 속도** 또는 **청산 타이밍** 개선입니다:

| 해결책 | 방법 | 기대 효과 | 부작용 |
|---|---|---|---|
| `hold_days` 단축 | 3일 → 1~2일 | 진입 앞당김 | 노이즈 신호 증가 |
| 버퍼존 축소 | 4% → 2~3% | 신호 빨리 발생 | 허위 신호 증가 |
| ATR 기반 동적 버퍼존 | 변동성 낮을 때 버퍼 줄임 | 추세별 최적화 | 구현 복잡도 상승 |
| **청산 타이밍 개선** | 트레일링 스탑 추가 | **MDD 감소** | 조기 청산 리스크 |

### 6.5 결론

**분할 매수는 버퍼존 전략에 적합하지 않습니다.**
분할 매수가 의미 있는 유일한 경우는 심리적 안정을 위한 도구로서(Schwab 연구)이며, 전략적 성과 개선 효과는 없습니다.

진입 타이밍보다 **청산 타이밍 개선(트레일링 스탑)** 이 더 효과적인 개선 방향으로 확인되었습니다.

---

## 7. Session 3 — 시계열 데이터 심층 분석 및 개선 방향

**날짜**: 2026-02-21
**질문**: `storage/results/backtest/buffer_zone_tqqq` 시계열 데이터를 분석해서 어떠한 방향으로 개선하면 좋을지 연구, 분석해줘

### 7.1 trades.csv 전체 거래 내역

```
 # 진입일          청산일          진입가         청산가         PnL(%)   보유일
 1 1999-04-08    2000-04-17    44.969471     65.370352    +45.37%   375일
 2 2000-06-19    2000-09-22    88.590163     59.774334    -32.53%    95일  ← 손실
 3 2003-03-24    2004-07-27     0.219900      0.374764    +70.43%   491일
 4 2004-11-02    2005-04-18     0.462894      0.366010    -20.93%   167일  ← 손실
 5 2005-07-20    2006-05-19     0.503868      0.449078    -10.87%   303일  ← 손실
 6 2006-10-10    2008-01-09     0.493206      0.538353     +9.15%   456일
 7 2008-05-07    2008-07-03     0.555779      0.414298    -25.46%    57일  ← 손실
 8 2009-05-05    2010-06-30     0.115948      0.189646    +63.56%   421일
 9 2010-09-17    2011-08-09     0.257965      0.288113    +11.69%   326일
10 2011-11-09    2012-11-15     0.381327      0.444508    +16.57%   372일
11 2013-03-13    2015-08-24     0.600231      1.488287   +147.95%   894일
12 2015-10-29    2016-01-11     2.397584      1.849997    -22.84%    74일  ← 손실
13 2016-07-20    2018-10-25     2.206265      6.078874   +175.53%   827일
14 2019-03-18    2020-03-10     6.636726      8.105240    +22.13%   358일
15 2020-04-20    2022-01-24     7.819365     25.682091   +228.44%   644일
16 2023-02-07    2025-03-11    11.974996     29.367288   +145.24%   763일
```

**현재 오픈 포지션** (미청산, 2025-05-16 진입):
```json
{
  "entry_date": "2025-05-16",
  "entry_price": 35.472617,
  "shares": 29837078
}
```

### 7.2 손실 거래 패턴 분류

| 거래 | 기간 | 손실률 | 보유일 | 발생 배경 |
|---|---|---|---|---|
| #2 | 2000-06-19 ~ 2000-09-22 | -32.53% | 95일 | 닷컴버블 붕괴 중 반등 포착 실패 |
| #4 | 2004-11-02 ~ 2005-04-18 | -20.93% | 167일 | 닷컴 회복기 변동성 |
| #5 | 2005-07-20 ~ 2006-05-19 | -10.87% | 303일 | 횡보장 장기 보유 |
| #7 | 2008-05-07 ~ 2008-07-03 | -25.46% | 57일 | 금융위기 중 반등 포착 실패 |
| #12 | 2015-10-29 ~ 2016-01-11 | -22.84% | 74일 | 변동성 구간 단기 손실 |

**공통 패턴:**
- 하락 추세 또는 변동성 구간에서 반등을 잘못 포착
- 진입 후 30일 내 손실은 대부분 -12% 이하로 시작 → 초기에는 정상처럼 보임
- 최저점에서 청산 (하단 밴드 이탈 신호가 바닥에서 발동)

### 7.3 MDD -85.68% 원인 분석

**MDD 최저점**: 2009-05-13
**해당 시점 Equity**: 7,990,703원
**포지션 상태**: 투자 중 (거래 #8 진입 8일째)

```
MDD는 단일 사건이 아닌 복수 손실의 누적입니다:

1999~2000: 닷컴버블 고점 물림 → 거래 #1 내부 MDD -73.95%
2000:      반등 포착 실패 → 거래 #2 -32.53% 확정 손실
2001~2003: 현금 보유로 대기 (회복 기회 없음)
2004~2008: 손실 3연타 (거래 #4, #5, #7)
2009-05:   금융위기 바닥 반등 진입 → 누적 소진 끝 → MDD 최저
```

### 7.4 거래별 내부 MDD 분석 (equity.csv 기반)

```
 # 진입일          결과     거래내MDD   MDD발생일          진입후10d   진입후30d
 1 1999-04-08      WIN    -73.95%    청산일 당일        -30.16%    -30.16%
 2 2000-06-19     LOSS    -43.92%    청산일 당일         -1.87%    -19.24%
 3 2003-03-24      WIN    -35.94%    청산일 전날         -2.39%     -9.95%
 4 2004-11-02     LOSS    -38.19%    청산일 당일          0.00%      0.00%
 5 2005-07-20     LOSS    -30.76%    청산일 전날         -1.11%     -6.77%
 6 2006-10-10      WIN    -41.73%    청산일 전날         -2.44%     -4.51%
 7 2008-05-07     LOSS    -32.28%    청산일 전날          0.00%      0.00%
 8 2009-05-05      WIN    -40.30%    청산일 당일         -5.38%    -19.36%
 9 2010-09-17      WIN    -40.10%    청산일 전날          0.00%      0.00%
10 2011-11-09      WIN    -31.94%    2012-06-01         -0.71%     -6.56%
11 2013-03-13      WIN    -41.27%    청산일 당일         -0.06%     -4.79%
12 2015-10-29     LOSS    -26.86%    청산일 3일 전       -4.33%    -12.63%
13 2016-07-20      WIN    -32.52%    청산일 전날         -1.39%     -4.41%
14 2019-03-18      WIN    -48.14%    청산일 당일         -3.03%    -15.90%
15 2020-04-20      WIN    -39.38%    청산일 당일         -5.25%    -18.63%
16 2023-02-07      WIN    -37.37%    2024-08-07         -3.69%    -16.66%
```

**평균 내부 MDD:**
- 손실 거래 (5건): 평균 -34.4%
- 승리 거래 (11건): 평균 -41.9%
- 전체: **평균 -39.7%**

### 7.5 치명적 패턴 발견: "청산일 = MDD 최저점"

> 16개 거래 중 **10개(62.5%)의 내부 MDD가 청산일 당일 또는 전날** 발생합니다.

**이것이 의미하는 바:**
현재 전략의 청산 신호(하단 밴드 하향 돌파)는 **이미 크게 하락한 직후에 발동**됩니다.
즉, 전략이 바닥 근처에서 팔고 있습니다.

> ⚠️ **정정 (2026-02-21)**: 이전 표현 "청산 신호(상단 밴드 이탈)"는 오기입니다.
> 코드 기준: 매수 = 상단 밴드 상향 돌파, **매도 = 하단 밴드 하향 돌파**.
> 분석 결론("청산이 늦다")은 동일하게 유효합니다.

또한 **승리 거래도 내부 MDD가 -30% ~ -74%에 달합니다.** 이것을 버텨야만 최종 수익이 납니다.

### 7.6 MAE(Maximum Adverse Excursion) 요약

- 진입 후 10일 내 평균 최대 손실: **-6.48%**
- 진입 후 30일 내 평균 최대 손실: **-10.53%**
- 가장 빠른 하락: 거래 #1 (진입 후 10일 내 -30.16%)
- 진입 직후 하락 없는 케이스: 거래 #4, #7, #9 (초기에는 정상처럼 보이다가 후에 손실)

### 7.7 그리드 서치 결과 분석 (grid_results.csv 상위 5개)

```
이평기간  버퍼존   유지일  조정기간(월)  수익률      CAGR    MDD      거래수  승률
150      0.04     3      2           14326.23   20.26   -85.68   16    68.75  ← 현재 최적
150      0.05     2      6/8         14106.70   20.20   -89.35   14    71.43
150      0.05     2      12          13561.69   20.02   -87.88   14    71.43
150      0.05     2      0           13518.54   20.01   -89.79   15    66.67
150      0.04     3      8           13144.32   19.88   -85.81   16    68.75
```

**인사이트:**
- MDD를 줄이는 파라미터 조합이 그리드 서치 상위에 존재하지 않음
- 현재 그리드 서치는 CAGR만 최적화 → MDD 개선은 구조적 변경 필요
- 이평 200일, 버퍼존 1%, 유지일 1일, 조정기간 12개월: CAGR 19.16%, MDD -84.0% (아주 약간 개선)

### 7.8 웹 리서치 결과 종합

**ATR 트레일링 스탑 근거:**
- [Medium - ATR Trailing Stop for Trend Following](https://medium.com/@redsword_23261/trend-following-average-true-range-trailing-stop-loss-strategy-75f6ccad5586)
- [SetupAlpha - 3x Leveraged ETF Strategy](https://medium.com/@setupalpha.capital/3x-leveraged-etf-strategy-2-600-return-with-38-drawdown-trading-strategy-rules-f4dad806bc25): 3x 레버리지 ETF에 트레일링 스탑 적용 → **CAGR 23.8%, MDD 38.7%** 달성 사례

**MAE 기반 손절 근거:**
- [AnalyzingAlpha - MAE](https://analyzingalpha.com/maximum-adverse-excursion): John Sweeney의 연구 — 승리 거래의 80% MAE 이내 손절선 설정 시 불필요한 손실 70~80% 차단 가능
- [QuantifiedStrategies - MAE/MFE](https://www.quantifiedstrategies.com/maximum-adverse-excursion-and-maximum-favorable-excursion/)

### 7.9 개선 방향 도출

#### 방향 1: ATR 트레일링 스탑 (최우선 권장)

**기존 청산 조건**: 상단 밴드 이탈 시에만 청산
**추가 청산 조건**: 고점 대비 `N × ATR` 하락 시 조기 청산

```
트레일링 스탑 = 진입 후 도달한 최고 equity - (ATR14 × 배율)
→ 이 선 이하로 하락 시 다음 시가에 청산
```

| 기대 효과 | 현재 | 개선 후 (추정) |
|---|---|---|
| MDD | -85.68% | -40% 수준 |
| CAGR | 20.26% | 소폭 감소 가능 |
| Calmar Ratio | 0.237 | 상승 예상 |

**근거:** 16개 거래 중 10개가 청산일에 MDD 최저점 → 트레일링 스탑은 이 손실을 사전에 차단 가능

#### 방향 2: MAE 기반 하드 스탑 (제한적 효과)

현재 데이터에서 도출된 기준:
- 손실 거래 내부 MDD 범위: -26% ~ -43%
- 승리 거래 내부 MDD 범위: -30% ~ -74%

> **문제점**: 승리 거래도 -30% 이상 MDD를 감수해야 합니다.
> TQQQ 3배 레버리지 특성 때문에 너무 좁은 손절선은 오히려 승리 거래를 조기 청산해 역효과.
> 적절한 구간이 있다면 **-35% ~ -40%** 수준이지만, 검증 필요.

#### 방향 3: 변동성 기반 포지션 사이징

```
포지션 크기 = 목표위험액 / (ATR × 배율)
→ ATR이 클 때(고변동성) → 적게 투자
→ ATR이 작을 때(저변동성) → 많이 투자
```

**현재 맹점:** 100% 투자 또는 0% 현금의 이분법 → 고변동성 구간 진입 시 리스크 급증

### 7.10 개선 방향 우선순위

| 순위 | 방법 | 예상 MDD 개선 | 예상 CAGR 영향 | 구현 난이도 |
|---|---|---|---|---|
| **1위** | ATR 트레일링 스탑 | -85% → -40% 수준 | 소폭 감소 가능 | 중 |
| **2위** | 변동성 기반 포지션 사이징 | -85% → -55% 수준 | 감소 최소화 | 중 |
| **3위** | MAE 기반 하드 스탑 | 제한적 | TQQQ 특성상 역효과 위험 | 낮 |

---

## 8. 현재까지 도출된 개선 방향 요약

### 8.1 핵심 문제

> **MDD -85%의 근본 원인은 "청산이 항상 너무 늦다"는 구조적 문제입니다.**
> 하단 밴드 하향 돌파 청산 신호가 이미 크게 하락한 후 발동되기 때문입니다.

### 8.2 현재 전략의 강점 (유지해야 할 것)

1. **현금 보유 능력**: 닷컴버블(2000~2003), 금융위기(2008~2009), 인플레이션(2022 전체)에서 현금 보유로 큰 손실 회피
2. **거래 횟수 최소화**: 27년간 16회(연 0.6회) → 슬리피지/수수료 최소화
3. **장기 추세 포착**: 894일 보유 거래에서 +147.95%, 827일 보유에서 +175.53% 등 대형 추세를 최대한 활용
4. **QQQ 시그널 분리**: 노이즈가 적은 QQQ 이평 신호로 TQQQ 매매 → 레버리지 상품 신호 왜곡 방지

### 8.3 개선이 필요한 것

1. **거래 내 MDD 평균 -39.7%** → 투자자가 버티기 어려운 수준
2. **청산 신호 지연** → 상단 밴드 이탈만으로는 하락 중반 이후 청산
3. **이분법적 포지션** → 100% 투자 or 0% 현금, 중간 단계 없음

### 8.4 다음 실험 계획

**Phase 1: ATR 트레일링 스탑 추가 실험**
- 기존 청산 조건(상단 밴드 이탈) 유지
- 추가: 보유 중 최고 equity 대비 `X × ATR14` 하락 시 조기 청산
- 목표: MDD -85% → -50% 이하 달성 (CAGR 손실 최소화)

**Phase 2: 변동성 기반 포지션 사이징**
- 진입 시점 ATR14 기반 포지션 비율 결정
- 목표: 고변동성 구간의 대규모 손실 방지

---

## 9. 앞으로의 개선 계획

### 9.1 개선 원칙

- **모든 개선은 백테스트 비교를 통해 검증** (기존 성과 vs 개선 후 성과)
- **Calmar Ratio 유지 또는 향상**을 목표로 함 (현재 0.237)
- 코드 변경 전 반드시 `docs/plans/`에 계획서 작성 (프로젝트 CLAUDE.md 규칙)
- 웹 리서치로 이론적 근거 확보 후 구현

### 9.2 평가 지표

| 지표 | 현재 | 목표 |
|---|---|---|
| CAGR | 20.26% | 18% 이상 유지 |
| MDD | -85.68% | -50% 이하 |
| Calmar Ratio | 0.237 | 0.35 이상 |
| 승률 | 68.75% | 70% 이상 |
| 거래 횟수 | 16회 | 크게 증가하지 않을 것 |

### 9.3 검토 예정 개선 사항

1. **ATR 트레일링 스탑**: `buffer_zone_helpers.py`의 `run_buffer_strategy()` 함수에 트레일링 스탑 로직 추가
2. **변동성 기반 포지션 사이징**: 진입 시 `initial_capital` 대비 실제 투자 비율을 ATR 기반으로 결정
3. **그리드 서치 목적함수 변경**: CAGR → Calmar Ratio (또는 MDD 패널티 항 추가)
4. **시장 레짐 필터**: 장기 추세(200일 EMA 등)가 하락 중일 때 진입 억제

---

---

## 10. Session 4 — AI 모델 간 토론 (외부 AI 분석 검토 및 반론)

**날짜**: 2026-02-21
**형식**: 외부 AI 모델이 이 문서를 분석한 결과를 검토하고, 코드 기반으로 팩트체크 후 동의/수정/반론을 정리

---

### 10.1 코드 기반 팩트체크 결과

#### ✅ (A) "TQQQ 합성 = QQQ × 3 단순 역산" — 과소설명 맞음, 수정 완료

`src/qbt/tqqq/simulation.py`의 `_calculate_daily_cost` 함수 확인:

```python
# simulation.py 실제 구현
annual_cost = leverage_cost + expense_ratio
leverage_cost = (FFR + softplus_spread(a, b, FFR)) × (leverage - 1)
daily_cost = annual_cost / 252
```

단순 3배 역산이 아닌, FFR + 동적 스프레드(softplus) + 운용보수를 모두 반영한 정밀 모델입니다.
4.1절에 이 강점을 명시하도록 수정 완료.

#### ✅ (B) "청산 신호 = 상단 밴드 이탈" 오기 — 수정 완료

`buffer_zone_helpers.py` 코드로 확인:

```python
# _detect_buy_signal: 상단 밴드 상향 돌파 = 매수 신호
return prev_close <= prev_upper_band and close > upper_band

# _detect_sell_signal: 하단 밴드 하향 돌파 = 매도 신호
return prev_close >= prev_lower_band and close < lower_band
```

7.5절 및 8.1절의 표현 "상단 밴드 이탈"을 "하단 밴드 하향 돌파"로 정정 완료.
분석 결론("청산이 늦다")은 동일하게 유효합니다.

#### ✅ (C) "recent_buy_count → 진입 직후 자동 밴드 확장" — 지적이 정확, 추가 발견 있음

외부 AI가 지적한 메커니즘을 코드로 확인:

```python
# _calculate_recent_buy_count (line 610)
cutoff_date = current_date - timedelta(days=recent_months * DEFAULT_DAYS_PER_MONTH)
count = sum(1 for d in entry_dates if d >= cutoff_date and d < current_date)
```

`d < current_date` 조건으로 현재 오픈 포지션의 진입일이 포함됩니다.
`recent_months=2`(60일)이면 진입 직후 60일간 `recent_buy_count=1`이 유지되어:

```
adjusted_buffer_pct  = 0.04 + (1 × 0.01) = 0.05
lower_band = MA × (1 - 0.05) = MA × 0.95   ← 하단 밴드가 더 낮아짐
```

**내가 추가로 발견한 사실**: `recent_months=0`(동적 조정 비활성)은 MDD가 오히려 더 나쁩니다.

```
recent_months=2 (현재 최적): CAGR 20.26%, MDD -85.68%
recent_months=0 (비활성):    CAGR 20.01%, MDD -89.79%  ← 더 나쁨
```

이것이 의미하는 바:
- 동적 조정이 완전히 없으면 MDD가 더 나쁩니다. 즉 동적 조정 **자체**가 나쁜 게 아닙니다.
- 문제는 `adjusted_buffer_pct`가 **upper_band와 lower_band를 동시에** 조정한다는 설계입니다.
- "진입 직후 밴드를 넓힌다" = 상단도 높아지고 **하단도 낮아져서** 매도가 더 어려워집니다.
- 개선 방향: 동적 조정을 유지하되, 매도 밴드에는 적용하지 않거나 반대 방향으로 적용

---

### 10.2 외부 AI와 견해가 다른 부분

#### 🔄 "sell 버퍼 분리가 구현 난이도 낮음" — 난이도 재평가 필요

외부 AI가 "ATR보다 훨씬 쉬움"이라고 했으나, 현재 코드 구조를 고려하면 다릅니다.

현재 `_compute_bands`는 단일 `buffer_zone_pct`로 upper/lower 동시 결정:

```python
upper_band = ma_value * (1 + buffer_zone_pct)
lower_band = ma_value * (1 - buffer_zone_pct)
```

sell/buy 버퍼를 분리하면 연쇄 변경이 발생합니다:
- `_compute_bands` 시그니처 변경
- `BufferStrategyParams` TypedDict 확장 (`sell_buffer_pct` 추가)
- `recent_buy_count` 동적 조정 로직 분기
- `HoldState`와 `EquityRecord`의 `buffer_zone_pct` 필드 분리
- 그리드 서치 파라미터 공간 확장 (탐색 시간 증가)

**결론**: 구현 난이도는 "낮음"이 아닌 "중간"이며, ATR 트레일링 스탑과 유사한 수준입니다.
방향성 자체는 동의합니다. "청산 밴드를 더 타이트하게"는 MDD 문제를 직접 겨냥합니다.

#### 🔄 "ATR 스탑을 레버리지 축소(3x→1x)로 시작" — 현재 아키텍처와 불일치

현재 코드는 이분법적 포지션 모델입니다 (전량 매수 또는 전량 매도, 중간 없음):

```python
# run_buffer_strategy: position_shares는 전량 또는 0
position_shares = available_cash / buy_price  # 전량 매수
# or
position_shares = 0  # 전량 청산
```

TQQQ→QQQ 전환이나 포지션 비율 관리를 도입하면:
- `position_shares` 대신 포트폴리오 비율 관리 체계 필요
- equity 계산 방식 전면 개편
- 이는 현재 전략 철학(추세 확인 후 전량 진입/청산) 자체를 바꾸는 수준

**제안**: 전량 ATR 스탑을 먼저 구현하고 성과를 검증한 후, 레버리지 축소 방식 검토.

---

### 10.3 내가 추가하는 관점

#### 매도 신호의 hold_days 부재와 62.5% 패턴의 연결

코드 확인: 매도 신호에는 hold_days 검증이 **없습니다**. 하단 밴드 하향 돌파 감지 즉시 다음날 시가에 청산 pending.

```python
# 매수: hold_days 상태머신 (N일 유지 확인)
if buy_signal and pending_order is None and position == 0:
    hold_state = HoldState(...)  # N일 대기

# 매도: 즉시 pending (hold_days 없음)
elif sell_signal and position > 0:
    pending_order = PendingOrder(order_type="sell", ...)
```

그럼에도 불구하고 16개 거래 중 10개(62.5%)에서 청산일 당일/전날에 내부 MDD 최저점 발생.

**이것이 의미하는 바**: 매도가 "느린 것"이 아니라, **하단 밴드 자체의 위치가 너무 낮습니다.**
하단 밴드 = `MA × (1 - 0.05)` (동적 조정 포함)이면,
가격이 150일 EMA의 95%까지 하락한 후에야 청산 신호가 발생합니다.
레버리지 3배 상품에서 이 정도 하락이면 이미 TQQQ 기준 상당한 손실이 확정된 상태입니다.

**진단**: 문제의 핵심은 "청산 집행이 느리다"가 아니라 "청산 트리거 조건 자체가 너무 관대하다"입니다.

#### 워크포워드 인프라 이식 가능성

16회 거래 데이터로 grid_best를 확정하는 것은 통계적으로 불안정합니다.
단, 이 프로젝트는 `scripts/tqqq/spread_lab/validate_walkforward.py` 형태로
워크포워드 인프라가 이미 다른 도메인(`tqqq/`)에 구현되어 있습니다.
`src/qbt/tqqq/walkforward.py`의 구조를 참고해 백테스트 도메인으로 이식하는 것이 현실적입니다.

---

### 10.4 외부 AI 제안 수용 및 개선 우선순위 최종 조정

외부 AI 분석과 코드 검토를 통합한 우선순위:

| 순위 | 방법 | 근거 | 예상 난이도 | 상태 |
|---|---|---|---|---|
| **1** | **recent_months 실험** (=0 vs =2 grid 비교) | ~~코드 변경 없이 즉시 검증~~ → **검증 완료** (10.5(3) 참조) | 낮음 | ✅ 완료 |
| **2** | **sell/buy 버퍼 분리 + recent_sell_count 도입** | 진행 확정 (사용자 결정). 청산 밴드 타이트 + 재진입 억제 메커니즘 재설계 | 중간 | 진행 예정 |
| **3** | **ATR 트레일링 스탑** (전량 청산형, 이분법 유지) | 청산 트리거 조건 개선, 기존 아키텍처와 일관성 | 중간 | 대기 |
| **4** | **그리드 서치 목적함수 → Calmar** | CAGR 단독 최적화로는 MDD 개선 불가 | 중간 | 대기 |
| **5** | **워크포워드 검증** | tqqq 도메인 인프라 재활용, 과최적화 논쟁 해소 | 중간 | 대기 |

**기존 9절의 Phase 1/2와의 관계**:

| 이전 계획 | 최종 조정 |
|---|---|
| Phase 1: ATR 트레일링 스탑 | 3순위로 조정 (sell/buy 분리 먼저) |
| Phase 2: 변동성 기반 포지션 사이징 | 후순위 이동 (아키텍처 변경 규모가 큼) |
| (신규) recent_months 실험 | ✅ 검증 완료 |
| (신규) sell/buy 버퍼 분리 + recent_sell_count | 2순위 — 진행 확정 |
| (신규) Calmar 목적함수 | 4순위 |
| (신규) 워크포워드 검증 | 5순위 |

---

### 10.5 사용자 추가 의견 및 즉시 검증

#### (1) sell 버퍼 분리 — 진행 확정

> **사용자 결정**: sell 버퍼 분리(buy_buffer ≠ sell_buffer)는 진행한다.

외부 AI가 "구현 난이도 낮음"으로 평가했고, 본 문서(10.2절)에서 "중간"으로 재평가했으나,
방향성에는 양측이 동의합니다. 청산 밴드를 더 타이트하게 하는 것이 MDD 문제를 직접 겨냥합니다.
개선 우선순위 4순위에서 진행 확정으로 격상합니다.

---

#### (2) recent_buy_count 타이밍 설계 오류 — 사용자 지적

> **사용자 지적**: equity.csv에서 buffer_zone_pct가 0.04→0.05로 늘어난 후 일정 기간 유지되는데, 이 타이밍이 잘못되었다.
> 예시: 2000-04-17에 매도하면, **그 이후 2달간** 0.05가 유지되어야 한다.

**equity.csv 실제 데이터로 확인:**

```
1999-04-08: buffer=0.04 (진입일, position=222373)
1999-04-09: buffer=0.05 (진입 다음날부터 확장, recent_buy_count=1)
...
2000-04-17: buffer=0.04 (매도일, position=0 — 즉시 원복)  ← 잘못된 부분
2000-04-18: buffer=0.04 (매도 후 현금 보유)
...
2000-06-19: buffer=0.04 (다음 거래 진입, 63일 후)
```

**현재 구현 vs 사용자 제안:**

| 구분 | 현재 구현 | 사용자 제안 |
|---|---|---|
| 버퍼 확장 시점 | 매수 다음날부터 (진입 후 60일) | 매도 이후부터 (청산 후 60일) |
| 버퍼 확장 효과 | 보유 중 lower_band를 낮춤 → 청산이 더 어려움 | 재진입 시 upper_band를 높임 → 재진입이 더 어려움 |
| 휩소 방지 메커니즘 | 진입 직후 밴드 확장으로 조기 청산 억제 | 청산 직후 밴드 확장으로 즉각 재진입 억제 |
| MDD 영향 | 보유 중 하단 밴드 낮아짐 → MDD 소폭 악화 가능 | 보유 중 밴드 변화 없음 → MDD 영향 없음 |

**설계 철학 차이:**

현재 구현은 "진입 직후에는 더 오래 버텨라"는 의도로 lower_band를 낮춥니다.
하지만 이는 **MDD가 이미 발생하는 중에 더 늦게 청산**하게 만드는 부작용이 있습니다.

사용자 제안은 "방금 팔았으면 바로 사지 마라"는 의도로 upper_band를 높입니다.
이는 **보유 중 밴드에는 영향을 주지 않고**, 재진입 판단에만 보수성을 추가합니다.

**구현 완료** (아래 11절에 상세 기록):
- `recent_buy_count` → `recent_sell_count` (청산 날짜 기반으로 변경)
- 확장된 버퍼는 upper_band에만 적용 (재진입 억제), lower_band는 고정
- `buffer_zone_pct` → `buy_buffer_zone_pct` + `sell_buffer_zone_pct` 분리 완료
- 그리드 서치 탐색 공간: 840 → 4,200 조합으로 확장

---

#### (3) recent_months 즉시 검증 — grid_results.csv 분석 결과

> **코드 변경 없이 기존 grid_results.csv 데이터로 검증 완료.**

동일 파라미터(ma=150, buffer=0.04, hold=3)에서 recent_months만 변경한 결과:

| recent_months | CAGR | MDD | 거래수 | 승률 | 비고 |
|---|---|---|---|---|---|
| 0 | 17.01% | -88.46% | **19** | 57.89% | 동적 조정 없음, 최악 |
| **2** | **20.26%** | **-85.68%** | **16** | **68.75%** | **현재 최적** |
| 4 | 19.88% | -85.81% | 16 | 68.75% | 4/6/8 동일 결과 |
| 6 | 19.88% | -85.81% | 16 | 68.75% | |
| 8 | 19.88% | -85.81% | 16 | 68.75% | |
| 10 | 19.26% | -86.99% | 16 | 68.75% | |
| 12 | 19.16% | -87.29% | 16 | 68.75% | |

**검증 결과 해석:**

1. **recent_months=0 (비활성)**: 거래수 19회 (vs 다른 경우 16회) → 동적 조정이 없으면 3회 추가 휩소 진입 발생
2. **CAGR 격차**: 17.01% vs 20.26%, 무려 3.25%p 차이 → 휩소 방지 효과가 CAGR에 크게 기여
3. **MDD 격차**: -88.46% vs -85.68%, 2.78%p 차이 → MDD 개선 효과도 있음
4. **4/6/8개월 동일**: 거래 패턴이 동일하다는 의미 → 해당 구간에서는 recent_months가 실제 결정에 영향을 주지 않음
5. **12개월 이상에서 악화**: 과거 진입 이력이 너무 오래 기억되어 정상 신호도 억제

**결론**: 현재 recent_months=2 설정이 이 파라미터 조합에서 최적입니다.
단, 위(2)에서 지적한 대로 **기준 날짜를 진입일 → 청산일로 변경**하면 같은 2개월 설정이더라도 전혀 다른 결과를 낼 수 있습니다.
sell/buy 버퍼 분리 구현과 함께 이 변경을 적용한 후 재검증이 필요합니다.

---

### 10.6 DCA 결론 프레이밍 수정 (외부 AI 제안 수용)

외부 AI 제안: "DCA가 틀렸다"보다 "이 전략의 목표함수(CAGR/Calmar)를 높이려면 DCA는 도구가 아니다"가 더 정확.

**기존 6.5절 결론은 유지하되, 아래 보완 추가**:

> DCA가 유의미한 유일한 맥락은 **심리적 안정(후회 최소화, regret minimization)** 목적입니다.
> 수익 극대화 또는 위험조정수익(Calmar) 개선이 목표라면 DCA는 도구가 되지 않습니다.
> 버퍼존 TQQQ의 개선 목표가 "Calmar Ratio 향상"이므로, DCA는 검토 대상에서 제외합니다.

---

## 11. Session 5 — 매수/매도 버퍼 분리 구현 완료

**날짜**: 2026-02-21
**상태**: 구현 완료 (코드레벨 검증 통과)

### 11.1 구현 배경

10.5절에서 도출된 두 가지 설계 이슈를 해결하기 위해 구현을 진행했습니다:

1. **매수/매도 버퍼가 단일 값으로 공유되는 문제**: `buffer_zone_pct` 하나로 upper_band(매수)와 lower_band(매도)를 동시에 결정하여, 동적 조정 시 lower_band도 같이 변해 MDD를 악화시킴
2. **동적 조정 타이밍 오류**: `entry_dates`(매수일) 기반으로 계산하여, 진입 직후부터 밴드가 확장되는 구조적 문제

### 11.2 핵심 변경 사항

#### (1) 매수/매도 버퍼 분리

```
변경 전: buffer_zone_pct 단일 값
  upper_band = MA x (1 + buffer_zone_pct)
  lower_band = MA x (1 - buffer_zone_pct)

변경 후: buy_buffer_zone_pct / sell_buffer_zone_pct 분리
  upper_band = MA x (1 + buy_buffer_zone_pct)   # 동적 확장 가능
  lower_band = MA x (1 - sell_buffer_zone_pct)   # 항상 고정
```

- `sell_buffer_zone_pct`는 동적 조정의 영향을 받지 않으므로, 보유 중 lower_band가 불필요하게 낮아지는 부작용이 제거됨
- 기본값: `DEFAULT_BUY_BUFFER_ZONE_PCT = 0.03`, `DEFAULT_SELL_BUFFER_ZONE_PCT = 0.03`

#### (2) 동적 조정 기준 변경 (entry → exit)

```
변경 전: _calculate_recent_buy_count(entry_dates, current_date, recent_months)
  → 진입일 기반, 진입 직후 60일간 밴드 확장 (보유 중 lower_band 낮아짐)

변경 후: _calculate_recent_sell_count(exit_dates, current_date, recent_months)
  → 청산일 기반, 청산 후 60일간 upper_band만 확장 (재진입 억제)
```

- 가산 누적 지원: 60일 내 청산이 2회 발생하면 `recent_sell_count=2` → 더 높은 upper_band
- `hold_days` 동적 조정도 동일하게 `recent_sell_count` 기반으로 변경

#### (3) 전체 rename: buffer_zone_pct → buy_buffer_zone_pct

비즈니스 로직(`src/`), 스크립트(`scripts/`), 테스트(`tests/`) 전체에서 기존 이름을 완전히 제거했습니다:

| 변경 전 | 변경 후 |
|---|---|
| `DEFAULT_BUFFER_ZONE_PCT` | `DEFAULT_BUY_BUFFER_ZONE_PCT` |
| `MIN_BUFFER_ZONE_PCT` | `MIN_BUY_BUFFER_ZONE_PCT` |
| `DEFAULT_BUFFER_ZONE_PCT_LIST` | `DEFAULT_BUY_BUFFER_ZONE_PCT_LIST` |
| `COL_BUFFER_ZONE_PCT` | `COL_BUY_BUFFER_ZONE_PCT` |
| `DISPLAY_BUFFER_ZONE` ("버퍼존") | `DISPLAY_BUY_BUFFER_ZONE` ("매수버퍼존") |
| `OVERRIDE_BUFFER_ZONE_PCT` | `OVERRIDE_BUY_BUFFER_ZONE_PCT` |
| `BufferStrategyParams.buffer_zone_pct` | `BufferStrategyParams.buy_buffer_zone_pct` |
| `BestGridParams.buffer_zone_pct` | `BestGridParams.buy_buffer_zone_pct` |
| `_calculate_recent_buy_count` | `_calculate_recent_sell_count` |
| `EquityRecord.buffer_zone_pct` | `EquityRecord.buy_buffer_pct` + `sell_buffer_pct` |
| `TradeRecord.recent_buy_count` | `TradeRecord.recent_sell_count` |

#### (4) 그리드 서치 탐색 공간 확장

```
변경 전: 4 x 5 x 6 x 7 = 840 조합
  ma_window x buffer_zone_pct x hold_days x recent_months

변경 후: 4 x 5 x 5 x 6 x 7 = 4,200 조합
  ma_window x buy_buffer_zone_pct x sell_buffer_zone_pct x hold_days x recent_months
```

- `sell_buffer_zone_pct` 탐색 범위: [0.01, 0.02, 0.03, 0.04, 0.05]

#### (5) CSV 스키마 변경

| 파일 | 변경 전 | 변경 후 |
|---|---|---|
| equity.csv | `buffer_zone_pct` | `buy_buffer_pct` + `sell_buffer_pct` |
| trades.csv | `recent_buy_count` | `recent_sell_count` |
| grid_results.csv | `버퍼존` | `매수버퍼존` + `매도버퍼존` |
| summary.json | `buffer_zone_pct` | `buy_buffer_zone_pct` + `sell_buffer_zone_pct` |

기존 storage 파일은 `run_single_backtest.py` / `run_grid_search.py` 재실행으로 재생성 필요.

### 11.3 변경된 파일 목록

**비즈니스 로직 (6개)**:
- `src/qbt/backtest/constants.py` — buy/sell buffer 상수 rename + 신규
- `src/qbt/backtest/types.py` — `BestGridParams` rename + 확장
- `src/qbt/backtest/analysis.py` — `_GRID_CSV_REQUIRED_COLUMNS`, `load_best_grid_params`
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — 핵심 변경 (TypedDict, DataClass, 함수 전체)
- `src/qbt/backtest/strategies/buffer_zone_tqqq.py` — OVERRIDE rename, `resolve_params`, `params_json`
- `src/qbt/backtest/strategies/buffer_zone_qqq.py` — 동일

**스크립트 (3개)**:
- `scripts/backtest/run_grid_search.py` — buy/sell buffer 파라미터 + TableLogger + metadata
- `scripts/backtest/run_single_backtest.py` — equity/trades CSV rounding
- `scripts/backtest/app_single_backtest.py` — 거래 내역 레이블 딕셔너리

**테스트 (1개)**:
- `tests/test_buffer_zone_helpers.py` — 전체 BufferStrategyParams 업데이트 + 신규 테스트

**문서 (1개)**:
- `src/qbt/backtest/CLAUDE.md` — rename 및 동적 조정 로직 반영

### 11.4 검증 결과

코드레벨 검증 결과:

| Phase | 항목 수 | 완료 | 미완료 |
|---|---|---|---|
| Phase 0 (레드 테스트) | 11 | 11 | 0 |
| Phase 1 (constants/types) | 12 | 12 | 0 |
| Phase 2 (helpers 핵심) | 27 | 27 | 0 |
| Phase 3 (연쇄 업데이트) | 22 | 22 | 0 |
| Phase 4 (테스트 보강) | 7 | 7 | 0 |
| 마지막 Phase (문서/검증) | 5 | 5 | 0 |
| **합계** | **84** | **84** | **0** |

기존 이름 잔존 확인: `src/`, `scripts/`, `tests/`에서 `buffer_zone_pct`(접미사 제외), `recent_buy_count`, `_calculate_recent_buy_count` 등 기존 이름 **완전 제거** 확인.

### 11.5 다음 단계

이 구현은 10.4절 우선순위 2번(sell/buy 버퍼 분리)에 해당합니다.
그리드 서치 재실행 후 새로운 최적 파라미터로 성과를 비교해야 합니다:

- 기존: `buffer_zone_pct=0.04` (매수/매도 동일)
- 신규: `buy_buffer_zone_pct=?`, `sell_buffer_zone_pct=?` (독립 탐색)

재실행 후 다음 항목을 확인해야 합니다:
1. 새 최적 파라미터에서의 CAGR/MDD/Calmar Ratio 변화
2. `sell_buffer_zone_pct`가 `buy_buffer_zone_pct`보다 작은 값(타이트한 매도)이 최적으로 선택되는지
3. `recent_sell_count` 기반 동적 조정이 기존 대비 어떤 차이를 만드는지

이후 우선순위:
- 3순위: ATR 트레일링 스탑 (전량 청산형, 이분법 유지)
- 4순위: 그리드 서치 목적함수 변경 (CAGR → Calmar)
- 5순위: 워크포워드 검증 (tqqq 도메인 인프라 재활용)

---

*이 문서는 지속적으로 업데이트됩니다. 새로운 세션마다 하단에 섹션을 추가하세요.*
