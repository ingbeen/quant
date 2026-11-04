# 레버리지 ETF 시뮬레이션 도메인 가이드

> 이 문서는 `src/qbt/tqqq/` 패키지의 레버리지 ETF 시뮬레이션 도메인에 대한 가이드입니다.

## 도메인 목적

레버리지 ETF 시뮬레이션 도메인은 기초 자산 데이터로부터 레버리지 상품의 가격을 모델링합니다.
QQQ(기초 자산)로부터 TQQQ(3배) · QLD(2배)의 상장 전 구간을 재현해 실물에 이어 붙인 합성 시세를 만드는 것이 주요 사용 사례입니다. 대상 상품은 `constants.py` 의 `DAILY_COMPARISON_TARGETS` 입니다.
비용 모델을 실물과 일별로 대조한 검증(일별 비교 · 스프레드 랩)은 커밋 `ee6d23d` 까지 저장소에 있었고, 결과와 근거는 `docs/research/전략_검증_보고서.md` §47 · §49.4 에 있습니다.

---

## 모듈 지도

함수 · 시그니처 · 열 이름은 각 모듈 docstring 이 정본입니다.

- `constants.py` — 도메인 상수 (데이터 경로, 레버리지 스펙, 비용 모델 기본값, 월별 CSV 열 이름)
- `data_loader.py` — 월별 데이터(연방기금금리 · 운용비율) 로딩, 월별 값 딕셔너리 생성 · 조회
- `simulation.py` — 시뮬레이션 엔진(`simulate`)과 softplus 스프레드

---

## 도메인 규칙

### 1. 시뮬레이션 규칙

일일 리밸런싱 모델:

- 매일 목표 레버리지 배율로 포지션 재조정
- 기초 자산의 일일 수익률에 배율 적용
- 복리 효과 반영 (전일 가격 기준으로 누적)

레버리지 배율:

- 목표 레버리지 배율: `DEFAULT_LEVERAGE_MULTIPLIER`
- 일일 수익률에 배율 적용: `leveraged_return = underlying_return * leverage - daily_cost`

시가 · 고가 · 저가:

- 전날 시뮬 종가에서 기초 자산의 그 값을 배율로 키운다: `X(t) = Close_sim(t-1) * (1 + (X_underlying(t) / Close_underlying(t-1) - 1) * leverage)`. 장중 노출은 전날 종가에 고정되므로 펀드 값은 기초 자산에 선형이다
- 일일 비용은 종가에서만 빠지므로 기초 자산이 저가에 마감한 날은 식의 저가가 종가 위로 나간다 — 고가 · 저가를 시가 · 종가로 맞춘다
- 첫날은 전날 종가가 없어 네 값 모두 시작 가격이다. 그 밖의 결측은 메우지 않는다
- 남은 전략은 시가 · 종가만 읽는다 — 고가 · 저가는 signal CSV · 캔들 · 내보내기에만 쓰인다

### 2. 비용 구조 (동적 비용 모델)

자금 조달 비용:

```
funding_spread = softplus(a + b * FFR_pct)  # a, b 기본값은 아래 상수 참조
일일 자금 조달 비용 = (FFR + funding_spread) * (leverage - 1) / TRADING_DAYS_PER_YEAR
```

- funding_spread는 softplus 모델로 금리에 따라 동적 결정 — 고정 스프레드(0.0034)는 고금리 구간에서 비용을 과소 반영해 시뮬레이션이 실제보다 높게 나온다. 근거는 고정 스프레드로 만든 일별 비교의 「금리 수준 vs 월말 누적 오차」 추세선 우상향이다 `[실측] 2026-02-08`(커밋 `8b43280`)
- 기본 파라미터: `DEFAULT_SOFTPLUS_A`, `DEFAULT_SOFTPLUS_B` — 스프레드 랩 튜닝의 전체기간 RMSE 최소값이다. 스프레드 랩의 워크포워드 RMSE 는 과최적화 여부를 가리지 못한다(이유는 커밋 `ee6d23d` 의 `scripts/tqqq/spread_lab/app_rate_spread_lab.py` docstring)
- 레버리지 차입 비율: `leverage - 1` (예: 3배 레버리지 -> 2배 차입)
- 금리는 월별 FFR 데이터 사용 (년-월 기준 조회)

운용 비용:

```
일일 운용 비용 = expense_ratio(date) / TRADING_DAYS_PER_YEAR
```

- 데이터 소스: `storage/etc/tqqq_net_expense_ratio_monthly.csv`
- 월별로 실제 운용비율을 동적으로 적용
- 파일 시작보다 먼저 상장한 QLD 는 `build_extended_expense_dict` 로 그 앞 구간을 고정값으로 채운다 — `create_expense_dict` 그대로면 상장일에서 ValueError 다
- QLD 도 스프레드 파라미터와 이 파일을 그대로 쓴다. 재튜닝 · QLD 전용 보수를 택하지 않은 근거는 `docs/research/전략_검증_보고서.md` §49.4

총 비용:

```
총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용
```

### 3. 데이터 요구사항

기초 자산 데이터: OHLCV, 날짜순 정렬, 결측치 없음

금리 데이터 (FFR) · 운용비율 데이터 (Expense Ratio):

- 금리 `federal_funds_rate_monthly.csv` 는 1999-01 부터다 — 합성 생성은 QQQ 첫날(1999-03-10)부터 돌아 그 앞 금리가 필요 없다
- 형식: `DATE` (`"yyyy-mm"` 문자열 — `datetime.date` 객체가 아니다), `VALUE` (0~1 비율)
- 날짜마다 그 달 값을 조회하고, 없으면 허용 개월 수(`MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF`) 안의 이전 달 값을 쓴다 — 그보다 비면 ValueError

두 파일 모두 값이 빈 칸 · inf 이거나 상한(`data_loader.py` 의 `MAX_FFR_VALUE` · `MAX_EXPENSE_VALUE`) 이상이면 ValueError 다 — 손으로 고치는 파일이라 % 로 적은 값(설명서 표기 그대로의 운용비율 0.82 등)이 들어올 수 있다. 하한은 없다(음수 금리를 그대로 쓴다).
