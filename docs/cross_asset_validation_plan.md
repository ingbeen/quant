# 교차 자산 검증 (3단계) 구현 참고 문서

> 작성일: 2026-03-07
> 목적: overfitting_analysis_report.md 11.4절 "3단계: 교차 자산 검증" 구현 시 참고
> 전제: 1단계 파라미터 안정성 검증 완료 (조건부 통과)

---

## 목차

1. [검증 목표](#1-검증-목표)
2. [파라미터 설정](#2-파라미터-설정)
3. [검증 자산 목록](#3-검증-자산-목록)
4. [실행 계획](#4-실행-계획)
5. [상관관계와 검증력에 대한 분석](#5-상관관계와-검증력에-대한-분석)
6. [DSR 처리 원칙](#6-dsr-처리-원칙)
7. [결과 해석 기준](#7-결과-해석-기준)
8. [의사결정 경로](#8-의사결정-경로)
9. [구현 방안](#9-구현-방안)

---

## 1. 검증 목표

### 1.1 답하려는 질문

"버퍼존 전략이 QQQ 과거 데이터를 암기한 것인가, 아니면 범용적 추세추종인가?"

### 1.2 검증의 두 가지 층위

| 질문 | 방법 | 의미 |
|---|---|---|
| A. "이 특정 파라미터가 범용적인가?" | 파라미터 완전 고정 | 가장 강한 증거 |
| B. "이 전략 구조가 범용적인가?" | 구조 고정, 파라미터만 재최적화 | 차선의 증거 |

본 검증은 **질문 A(파라미터 완전 고정)**로 수행한다.
파라미터를 고정하면 다중 검정 문제가 발생하지 않으므로 DSR 보정이 불필요하다.

질문 B는 Step 1(고정)에서 실패한 자산에 대해서만 선택적으로 수행한다.

---

## 2. 파라미터 설정

### 2.1 3파라미터 버전 사용 (hold_days, recent_months 제거)

| 파라미터 | 값 | 상태 |
|---|---|---|
| ma_window | 200 | **고정** |
| ma_type | ema | 고정 |
| buy_buffer_zone_pct | 0.03 (3%) | **고정** |
| sell_buffer_zone_pct | 0.05 (5%) | **고정** |
| hold_days | 0 | **제거** (돌파 즉시 매수 확정) |
| recent_months | 0 | **제거** (동적 조정 미사용) |

### 2.2 hold_days와 recent_months 제거 근거

1. **1단계 검증에서 확인**: Hold Days 차트에서 0~5 전체가 70% 임계선 위로 안정적. hold_days 변경이 성과에 미치는 영향 미미.
2. **최적 파라미터가 이미 recent_months=0**: 동적 조정 메커니즘 미사용이 최적이므로 제거가 자연스러움.
3. **경제적 논거 약함**: 보고서 8.2절에서 hold_days는 B~C등급(경제적 방어 거의 불가)으로 평가. 논거가 약한 파라미터 제거는 전략 방어력 향상.
4. **교차 검증의 순수성 향상**: 파라미터 3개로 줄면 "이 3개가 다른 자산에서도 작동하는가"라는 질문이 깔끔해짐.

### 2.3 공통 실행 조건

| 항목 | 값 |
|---|---|
| 롱 온리 | 최대 1 포지션 |
| 시그널 소스 | 각 자산 자체 (QQQ→QQQ, SPY→SPY, ...) |
| 매매 대상 | 시그널 소스와 동일 |
| 체결 | 다음 영업일 시가 |
| 슬리피지 (매수) | +0.3% |
| 슬리피지 (매도) | -0.3% |
| 초기 자본 | 10,000,000원 |

---

## 3. 검증 자산 목록

### 3.1 자산별 상세 정보

| Ticker | 이름 | 상장일 | 추적 대상 | QQQ와 상관관계 | 검증력 |
|---|---|---|---|---|---|
| **QQQ** | Invesco QQQ Trust | 1999-03-10 | 나스닥 100 | — (기준) | 기준선 |
| **SPY** | SPDR S&P 500 | 1993-01-22 | S&P 500 | ~0.92 | 약함 |
| **IWM** | iShares Russell 2000 | 2000-05-22 | 러셀 2000 소형주 | ~0.84 | 약~중간 |
| **EFA** | iShares MSCI EAFE | 2001-08-14 | 선진국 (미국 제외) | ~0.75 | 중간 |
| **TLT** | iShares 20+ Year Treasury | 2002-07-22 | 미국 장기 국채 | ~-0.10 | 강함 |
| **EEM** | iShares Emerging Markets | 2003-04-07 | 신흥국 주식 | ~0.65 | 중간~강 |
| **GLD** | SPDR Gold Shares | 2004-11-18 | 금 현물 | ~0.05 | 강함 |

### 3.2 백테스트 기간

각 자산의 백테스트 시작일은 해당 자산의 상장일 이후로 한다.
200일 EMA 계산을 위해 최소 200거래일의 웜업 기간이 필요하므로,
실질적 첫 시그널 발생은 상장일로부터 약 10개월 후이다.

| Ticker | 데이터 시작 | 첫 시그널 가능 (약) | 백테스트 종료 |
|---|---|---|---|
| QQQ | 1999-03-10 | 1999-12경 | 2026-02-17 |
| SPY | 1993-01-22 (또는 1999-03-10으로 통일) | — | 2026-02-17 |
| IWM | 2000-05-22 | 2001-02경 | 2026-02-17 |
| EFA | 2001-08-14 | 2002-05경 | 2026-02-17 |
| TLT | 2002-07-22 | 2003-04경 | 2026-02-17 |
| EEM | 2003-04-07 | 2004-01경 | 2026-02-17 |
| GLD | 2004-11-18 | 2005-08경 | 2026-02-17 |

참고: SPY는 1993년 상장이지만, QQQ와 동일 기간 비교를 위해 1999-03-10부터 시작하는 것도 고려. 두 가지 버전(전체 기간 / QQQ 동일 기간) 모두 유의미할 수 있음.

### 3.3 자산 성격 분류

```
미국 주식 (QQQ와 높은 상관관계):
  SPY  — 대형주 분산. QQQ 대비 변동성 낮음. 쉬운 시험.
  IWM  — 소형주. 추세가 더 자주 끊김. 중간 시험.

해외 주식 (중간 상관관계):
  EFA  — 선진국. 미국과 다른 추세 패턴. 어려운 시험.
  EEM  — 신흥국. 높은 변동성, 다른 시장 구조. 어려운 시험.

비주식 (낮은/역 상관관계):
  TLT  — 채권. 주식과 역상관 가능. 가장 어려운 시험.
  GLD  — 금. 거의 무상관. 가장 어려운 시험.
```

---

## 4. 실행 계획

### 4.1 실행 순서

```
Step 1: QQQ 3파라미터 백테스트 (기준선 확보)
  → MA=200, buy=3%, sell=5%, hold=0, recent=0
  → 기존 5파라미터(Calmar 0.301)와 비교하여 hold_days 제거 영향 확인

Step 2: 동일 파라미터로 6개 자산 백테스트 (파라미터 완전 고정)
  → SPY, IWM, EFA, EEM, GLD, TLT
  → 각 자산의 시그널 소스 = 해당 자산 자체

Step 3: 결과 비교 테이블 작성

Step 4: 해석 및 판정
```

### 4.2 결과 비교 테이블 (템플릿)

| 자산 | 기간 | CAGR | MDD | Calmar | 거래수 | 승률 | 평균보유일 | B&H CAGR | B&H MDD | B&H Calmar |
|---|---|---|---|---|---|---|---|---|---|---|
| QQQ (5p, 기존) | 1999~2026 | 10.99% | -36.49% | 0.301 | 14 | 71.43% | 462 | 10.26% | -82.96% | 0.12 |
| QQQ (3p, 기준선) | 1999~2026 | ? | ? | ? | ? | ? | ? | 10.26% | -82.96% | 0.12 |
| SPY | ?~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| IWM | 2000~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| EFA | 2001~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| TLT | 2002~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| EEM | 2003~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |
| GLD | 2004~2026 | ? | ? | ? | ? | ? | ? | ? | ? | ? |

### 4.3 거래 내역도 기록

각 자산별 거래 내역(진입일, 청산일, 진입가, 청산가, 손익률, 보유일)을 기록한다.
거래 특성(거래 수, 보유 기간, 승률)이 자산마다 어떻게 달라지는지 비교하기 위함이다.

---

## 5. 상관관계와 검증력에 대한 분석

### 5.1 높은 상관관계 자산(SPY/IWM)의 검증 한계

QQQ, SPY, IWM은 모두 미국 주식시장이라는 하나의 큰 요인에 지배된다.
수익률의 상관관계가 높으므로, SPY/IWM에서 통과했다고 전략의 범용성을 확신할 수 없다.

### 5.2 그러나 완전히 무의미하지는 않은 이유

검증 대상은 "수익률의 상관관계"가 아니라 "시그널의 작동 여부"이다.
수익률은 높은 상관관계를 보이지만, 200일 EMA와의 관계(시그널)는 자산마다 다르다.

구체적으로 차이가 나는 부분:

1. **추세의 강도와 지속 기간**: QQQ는 기술주 중심이라 추세가 강하고 오래 지속(FAANG 주도). IWM은 소형주 중심이라 추세가 더 자주 끊기고 횡보 구간이 많음.
2. **200일 EMA 돌파의 빈도와 신뢰도**: QQQ는 14거래, 평균 보유 462일로 매우 긴 추세를 탐. IWM은 200일 EMA를 더 자주 오가며 가짜 돌파(fake breakout)가 더 많을 수 있음.
3. **버퍼의 실질적 의미**: 3% 매수 버퍼와 5% 매도 버퍼는 QQQ 변동성 수준에 맞춰진 것. 변동성이 다른 자산에서는 같은 퍼센트 버퍼의 노이즈 필터 효과가 달라짐.

### 5.3 자산별로 알 수 있는 것과 없는 것

**SPY/IWM으로 알 수 있는 것:**
- "200일 EMA + 버퍼존"이라는 시그널 구조가 QQQ 고유인지 미국 주식 전반에 적용 가능한지
- 매수/매도 버퍼 3%/5%가 QQQ 변동성에 과적합되었는지
- 전략의 거래 특성(거래 수, 보유 기간)이 자산마다 어떻게 달라지는지

**SPY/IWM으로 알 수 없는 것:**
- 미국 주식시장 전체의 구조적 추세에 의존하는지 (셋 다 같은 방향이므로)
- 2009~2024 같은 장기 상승장 편향이 있는지 (셋 다 같은 기간)
- 진짜 독립적인 시장에서도 작동하는지

**EFA/EEM으로 추가로 알 수 있는 것:**
- 미국 시장 외에서도 추세추종이 작동하는지
- 다른 시장 구조(유럽/일본/신흥국)에서 200일 EMA 시그널이 유효한지

**GLD/TLT로 추가로 알 수 있는 것:**
- 추세추종이 주식이 아닌 자산군에서도 작동하는지
- 단, 같은 파라미터(200일 EMA, 3%/5% 버퍼)가 비주식에서 안 맞는 것은 자연스러움.
  실패가 "전략의 실패"인지 "파라미터의 부적합"인지 구분 필요.

### 5.4 검증력 계층 구조

```
SPY/IWM 통과: 최소 일관성 확인 (쉬운 시험)
  → SPY/IWM 실패 시: QQQ 극도의 과적합. 전략 재설계 필요.

EFA/EEM 통과: 미국 외 시장에서도 작동 (어려운 시험)
  → EFA/EEM 실패 시: "미국 시장 한정 전략"으로 한정하여 운용.

GLD/TLT 통과: 자산군 초월 범용성 (가장 어려운 시험)
  → GLD/TLT 실패 시: "주식 전용 전략"으로 판단 (정상적 결과일 수 있음).
```

---

## 6. DSR 처리 원칙

### 6.1 핵심 원칙: ticker별 별도 N, 별도 DSR

DSR의 N은 **동일한 데이터셋에서 시도한 횟수**만 카운트한다.
다른 ticker에서의 시행은 해당 ticker의 N에 포함되지 않는다.

```
QQQ 데이터에서:
  그리드 서치 432개 + 이전 탐색 → N ≈ 2,500+
  → QQQ의 DSR 계산에만 사용

SPY 데이터에서 (파라미터 고정):
  N = 1 (시행 없음, 1개 파라미터만 적용)
  → DSR 불필요 — 선택 편향이 없으므로
```

### 6.2 파라미터 고정이 강력한 이유

파라미터를 고정하면 **다중 검정 문제 자체가 사라진다.**

- QQQ: 432개 중 최적을 골랐으므로 선택 편향 존재 → DSR 필요
- SPY (고정 적용): 1개만 적용, 선택 없음 → 선택 편향 없음 → DSR 불필요
- SPY에서 양(+) 수익이 나오면: "QQQ에서 과최적화된 파라미터인데 SPY에서도 작동" = 별도 보정 없이 유의미

### 6.3 재최적화 시 DSR 처리 (Step 2 진행 시)

파라미터 고정에서 실패한 자산에 대해 재최적화를 수행하면,
해당 자산의 별도 DSR을 계산해야 한다.

```
예: EFA에서 파라미터 고정 → 실패 → 재최적화(432개 탐색)
  → EFA의 N = 432
  → EFA의 별도 DSR 계산
  → QQQ의 N(2,500+)에는 영향 없음
```

---

## 7. 결과 해석 기준

### 7.1 자산별 해석 기준

| 자산 | 통과 조건 | 통과 의미 | 실패 의미 |
|---|---|---|---|
| QQQ (3p) | 기존 5p(0.301)과 비슷한 Calmar 유지 | hold_days 제거 정당화 | hold_days=3이 중요한 파라미터였음 |
| SPY | CAGR > 0%, Calmar > B&H | 미국 대형주 전반에 적용 가능 | QQQ 특수 패턴에 의존 |
| IWM | CAGR > 0%, Calmar > B&H | 소형주에서도 시그널 작동 | QQQ 추세 특성에 의존 |
| EFA | CAGR > 0% | 선진국 시장에서도 작동 | 미국 시장 한정 전략 |
| EEM | CAGR > 0% | 신흥국에서도 작동 | 선진국 시장 한정 |
| GLD | CAGR > 0% | 자산군 초월 범용성 | 주식 전용 전략 (정상일 수 있음) |
| TLT | CAGR > 0% | 자산군 초월 범용성 | 주식 전용 전략 (정상일 수 있음) |

### 7.2 종합 해석 기준

| 통과 자산 수 | 해석 |
|---|---|
| 6/6 (전부 통과) | 전략 구조와 파라미터 모두 범용적. 최강의 증거 |
| SPY + IWM + EFA or EEM (4~5개) | 주식시장 전반에서 작동. 충분히 강한 증거 |
| SPY + IWM (2~3개) | 미국 주식 한정 작동. 제한적이나 운용 가능 |
| SPY만 통과 (1개) | QQQ와 매우 유사한 자산에서만 작동. 검증 불충분 |
| 전부 실패 | QQQ 과거 데이터 암기. 과최적화 확정 |

### 7.3 GLD/TLT 실패 시 추가 분석

GLD/TLT에서 실패해도 즉시 "전략 실패"로 판정하지 않는다.
비주식 자산은 변동성 구조가 근본적으로 다르므로 같은 퍼센트 버퍼가 안 맞는 것은 자연스럽다.

```
GLD 일평균 변동성: ~0.8% → 매도 버퍼 5% = 약 6.3일치 변동 (너무 넓음)
TLT 일평균 변동성: ~1.0% → 매도 버퍼 5% = 약 5.0일치 변동 (넓음)
QQQ 일평균 변동성: ~1.5% → 매도 버퍼 5% = 약 3.3일치 변동 (적절)
```

GLD/TLT 실패 시 해석:
- CAGR이 음(-)이면: 파라미터 부적합 가능성. 전략 구조 자체의 실패는 아닐 수 있음.
- 거래 수가 극히 적으면(3개 이하): 데이터 부족으로 판단 보류.

---

## 8. 의사결정 경로

### 8.1 Step 1 결과에 따른 분기

```
QQQ 3p 결과:
  Calmar ≈ 0.30 (5p와 유사) → hold_days 제거 정당화. Step 2 진행.
  Calmar << 0.30 (크게 하락) → hold_days가 중요한 파라미터.
                                 5p로 교차 검증하거나, hold_days 재검토.
```

### 8.2 Step 2 결과에 따른 분기

```
SPY/IWM 모두 양(+):
  → 미국 주식시장에서 전략 작동 확인
  → EFA/EEM 결과 확인하여 범용성 수준 결정

SPY/IWM 중 하나 이상 음(-):
  → QQQ 과적합 가능성 높음
  → 거래 내역을 분석하여 "어떤 구간에서 실패했는지" 확인
  → 파라미터 고정의 문제인지 전략 구조의 문제인지 구분 필요

EFA/EEM 양(+):
  → 전략이 미국 시장을 넘어 범용적
  → 높은 확신으로 실전 투입 가능

GLD/TLT 양(+):
  → 자산군 초월 범용성 (보너스)
  → 매우 강한 전략 검증 증거

GLD/TLT 음(-):
  → 주식 전용 전략으로 한정 (정상적 결과일 수 있음)
  → 전략 폐기 사유 아님
```

### 8.3 최종 의사결정

```
1단계 (조건부 통과) + 3단계 (SPY/IWM/EFA 중 2개+ 통과):
  → 버퍼존 QQQ 전략을 소규모 실전 투입 가능
  → 6~12개월 페이퍼 트레이딩으로 최종 검증 (유일한 순수 OOS)
  → TQQQ 버전은 매매 대상만 교체하여 동시 모니터링

1단계 (조건부 통과) + 3단계 (SPY만 통과):
  → QQQ/SPY 한정 전략으로 제한적 운용
  → 추가 검증(2단계 WFO 분석) 수행 권장

1단계 (조건부 통과) + 3단계 (전부 실패):
  → 과최적화 확정
  → 전략 폐기 또는 경제적 논거 기반으로 파라미터를 사전 결정하여 재설계
```

---

## 9. 구현 방안

### 9.1 핵심 설계 결정

| # | 결정 사항 | 선택 | 근거 |
|---|---|---|---|
| 1 | 전략 모듈 구조 | 통합 config-driven 모듈 1개 | 기존 buffer_zone_tqqq/qqq도 함께 리팩토링하여 코드 중복 제거 |
| 2 | 3파라미터 엔진 | 기존 엔진 래핑 (B) | hold_days=0, recent_months=0으로 내부 전달. 검증된 엔진 재사용, 테스트 중복 방지 |
| 3 | hold_days/recent_months | 외부 인터페이스에서 제거 | 내부적으로 0 전달하되, 사용자에게는 3파라미터만 노출 |
| 4 | 시장 구간별 분석 (regime_summaries) | 유지 (선택적 적용) | 기존 QQQ/TQQQ 전략은 그대로 적용, cross-asset 전략은 빈 리스트 |
| 5 | Buy & Hold 벤치마크 | 신규 자산 미추가 | cross-asset 전략만 추가. B&H 비교는 결과 테이블에서 수동 확인 |
| 6 | 백테스트 기간 | 각 자산 상장 이후 최대 기간 | SPY는 1993년부터 (QQQ 동일 기간으로 통일하지 않음) |

### 9.2 통합 전략 모듈 설계

기존 `buffer_zone_tqqq.py`, `buffer_zone_qqq.py`를 하나의 config-driven 모듈로 통합한다.
`buy_and_hold.py`의 `CONFIGS` 패턴을 참고한다.

**통합 대상:**

- `buffer_zone_tqqq.py` (signal=QQQ, trade=TQQQ 합성) → 통합 모듈의 설정으로 대체
- `buffer_zone_qqq.py` (signal=QQQ, trade=QQQ) → 통합 모듈의 설정으로 대체
- cross-asset 6개 (signal=trade=각 자산 자체) → 통합 모듈에 설정 추가

**통합하지 않는 모듈:**

- `buffer_zone_atr_tqqq.py`: ATR 트레일링 스탑 로직이 별도이므로 제외
- `donchian_channel_tqqq.py`: 독립 프레임워크이므로 제외
- `buy_and_hold.py`: 이미 config-driven, 변경 불필요

**config 구조 (개념):**

```python
@dataclass(frozen=True)
class BufferZoneConfig:
    strategy_name: str          # "buffer_zone_tqqq", "buffer_zone_spy" 등
    display_name: str           # "버퍼존 전략 (TQQQ)", "버퍼존 전략 (SPY)" 등
    signal_data_path: Path      # 시그널 소스 경로
    trade_data_path: Path       # 매매 대상 경로
    result_dir: Path            # 결과 저장 디렉토리
    grid_results_path: Path | None  # 그리드 서치 결과 (없으면 None)
    # 파라미터 오버라이드 (None = grid/DEFAULT 폴백, 값 설정 = 고정)
    override_ma_window: int | None
    override_buy_buffer_zone_pct: float | None
    override_sell_buffer_zone_pct: float | None
    ma_type: str                # "ema" 등
```

**signal ≠ trade 지원:**

- `signal_data_path`와 `trade_data_path`를 분리하여 두 패턴 모두 지원
- signal = trade인 경우 (cross-asset, QQQ): overlap 처리 불필요
- signal ≠ trade인 경우 (TQQQ): `extract_overlap_period` 자동 호출

**파라미터 결정 방식:**

- cross-asset: override로 3파라미터 고정 (grid_results_path=None)
- 기존 TQQQ/QQQ: override → grid_results.csv → DEFAULT 폴백 체인 유지

### 9.3 영향받는 파일

**전략 모듈 (리팩토링 대상):**

| 파일 | 변경 내용 |
|---|---|
| `src/qbt/backtest/strategies/buffer_zone_tqqq.py` | 통합 모듈로 대체 (삭제) |
| `src/qbt/backtest/strategies/buffer_zone_qqq.py` | 통합 모듈로 대체 (삭제) |
| `src/qbt/backtest/strategies/` (신규) | 통합 config-driven 모듈 생성 |
| `src/qbt/backtest/strategies/__init__.py` | export 변경 |
| `src/qbt/common_constants.py` | 6개 자산 경로 + 결과 디렉토리 상수 추가 |

**스크립트 (import 변경):**

| 파일 | 변경 내용 |
|---|---|
| `scripts/backtest/run_single_backtest.py` | import 변경 + 전략 레지스트리 + regime_summaries 분기 |
| `scripts/backtest/run_grid_search.py` | import 변경 + 설정 구조 대응 |
| `scripts/backtest/run_walkforward.py` | import 변경 + 설정 구조 대응 |
| `scripts/backtest/run_cpcv_analysis.py` | import 변경 + 설정 구조 대응 |

**영향 없음 (코드 수정 불필요):**

| 파일 | 이유 |
|---|---|
| `scripts/backtest/app_single_backtest.py` | Feature Detection 기반, 자동 호환 |
| `scripts/backtest/run_wfo_stitched_backtest.py` | buffer_zone_atr_tqqq만 사용 |
| `scripts/backtest/run_atr_comparison.py` | buffer_zone_atr_tqqq만 사용 |
| `scripts/backtest/run_wfo_comparison.py` | buffer_zone_atr_tqqq만 사용 |
| `src/qbt/backtest/strategies/buffer_zone_helpers.py` | 핵심 엔진, 변경 없음 |
| `src/qbt/backtest/strategies/buffer_zone_atr_tqqq.py` | ATR 전용, 변경 없음 |
| `src/qbt/backtest/analysis.py` | regime_summaries 함수 유지 |
| `src/qbt/backtest/constants.py` | MARKET_REGIMES 유지 |

**테스트 (전환 대상):**

| 파일 | 변경 내용 |
|---|---|
| `tests/test_buffer_zone_tqqq.py` | 통합 모듈 테스트로 전환 |
| `tests/test_buffer_zone_qqq.py` | 통합 모듈 테스트로 전환 |

### 9.4 작업 순서 (우선순위별)

> **구현 완료**: 아래 Step 1~4, 6~7은 두 개의 Implementation Plan으로 완료되었다.
> - `PLAN_BUFFER_ZONE_UNIFIED_MODULE`: Step 1~3 (통합 모듈 + 상수 + 테스트)
> - `PLAN_CROSS_ASSET_SCRIPT_MIGRATION`: Step 4, 6~7 (스크립트 전환 + 레거시 삭제 + 문서)
> - Step 5 (비교 테이블 출력)는 사용자가 스크립트 실행 후 결과로 확인한다.

```
Step 1: 경로 상수 + 데이터 준비 (선행 조건, 리스크 낮음) ✅ 완료
  - common_constants.py에 6개 자산 데이터 경로 + 결과 디렉토리 상수 추가
  - 사용자가 download_data.py로 6개 자산 다운로드 (사용자 실행 필요)

Step 2: 3파라미터 인터페이스 생성 (핵심 변경, 리스크 중간) ✅ 완료
  - 3파라미터 전용 외부 인터페이스 (ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct)
  - 내부적으로 BufferStrategyParams(hold_days=0, recent_months=0) 래핑

Step 3: 통합 전략 모듈 생성 (가장 큰 변경, 리스크 높음) ✅ 완료
  - BufferZoneConfig dataclass + CONFIGS 리스트 (9개)
  - signal_path/trade_path 분리 지원
  - 파라미터 결정: 고정(cross-asset) vs OVERRIDE/grid 폴백(기존)
  - 기존 buffer_zone_tqqq.py, buffer_zone_qqq.py 삭제 (통합 모듈로 대체)

Step 4: 스크립트 업데이트 (리스크 중간) ✅ 완료
  - run_single_backtest.py: 전략 레지스트리 + regime_summaries 분기
  - run_grid_search.py: import 변경 + 설정 구조 대응
  - run_walkforward.py: import 변경 + 설정 구조 대응
  - run_cpcv_analysis.py: import 변경 + 설정 구조 대응

Step 5: cross-asset 결과 비교 출력 (리스크 낮음)
  - run_single_backtest.py에서 일괄 실행 시 4.2절 비교 테이블 출력
  - (사용자가 스크립트 실행 후 결과로 확인)

Step 6: 테스트 전환 (리스크 중간) ✅ 완료
  - test_buffer_zone_tqqq.py → test_buffer_zone.py로 통합
  - test_buffer_zone_qqq.py → test_buffer_zone.py로 통합
  - 3파라미터 인터페이스 + config-driven 설정 검증

Step 7: 품질 검증 + 문서 업데이트 (마무리) ✅ 완료
  - poetry run python validate_project.py (passed=479, failed=0, skipped=0)
  - poetry run black .
  - CLAUDE.md 업데이트 (backtest 도메인, 루트, scripts, tests)
```

### 9.5 재실행이 필요한 스크립트

> **구현 완료 후 상태**: Step 1~4, 6~7 완료. 아래 스크립트는 사용자가 직접 실행해야 한다.

**신규 실행 (필수):**

| 순서 | 스크립트 | 명령어 | 목적 |
|---|---|---|---|
| 1 | `download_data.py` x 6회 | `poetry run python scripts/data/download_data.py SPY` (+ IWM, EFA, EEM, GLD, TLT) | 6개 자산 데이터 다운로드 |
| 2 | `run_single_backtest.py` | `poetry run python scripts/backtest/run_single_backtest.py` | cross-asset 전략 포함 전체 실행 |

**기존 결과 재실행 (선택):**

- 기존 CSV/JSON 결과는 유효 (출력 포맷 동일). 원하면 재실행 가능.
- `run_grid_search.py`, `run_walkforward.py`, `run_cpcv_analysis.py`는 재실행 불필요 (import만 변경, 기존 결과 유효).

### 9.6 시각화 대시보드 호환성

`app_single_backtest.py`는 Feature Detection 기반이므로 코드 수정 없이 자동 호환된다.

| 대시보드 기능 | cross-asset 전략에서 | 결과 |
|---|---|---|
| 탭 자동 생성 | summary.json 존재 | 자동 탭 생성 |
| 캔들스틱 + MA + 밴드 | signal.csv + equity.csv | 정상 표시 |
| Buy/Sell 마커 | trades.csv | 정상 표시 |
| 에쿼티/드로우다운 | equity.csv | 정상 표시 |
| 월별 히트맵 | summary.json > monthly_returns | 정상 표시 |
| 시장 구간별 분석 | regime_summaries = 빈 리스트 | "데이터가 없습니다" 자동 표시 |
| 거래 상세 테이블 | hold_days_used=0, recent_sell_count=0 | 정상 (항상 0인 컬럼이 약간 노이즈) |

**참고: 탭 개수**

기존 6개 + 신규 cross-asset 7개(QQQ 3P + 6개 자산) = 최대 13개 탭.
`--strategy` 옵션으로 특정 전략만 실행하여 탭 수 제한 가능.

---

## 10. 구현 이력

| 날짜 | Plan | 내용 |
|---|---|---|
| 2026-03-07 | `PLAN_BUFFER_ZONE_UNIFIED_MODULE` | BufferZoneConfig 기반 통합 전략 모듈 생성 (9개 CONFIGS) |
| 2026-03-07 | `PLAN_CROSS_ASSET_SCRIPT_MIGRATION` | 스크립트 마이그레이션 + 레거시 모듈 삭제 + 문서 업데이트 |

**다음 단계**: 사용자가 6개 자산 데이터를 다운로드하고 `run_single_backtest.py`를 실행하여 §4.2 결과 비교 테이블을 작성한다.
