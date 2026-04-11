# QBT Live 실시간 매매 알림 시스템 설계서 (최종)

> **앱은 Firebase Auth로 1회 로그인 후 사용하며, GitHub 리포지토리 토큰은 앱에 절대 포함하지 않는다.**

## 0. 개요

QBT 프로젝트의 포트폴리오 전략을 **Android 앱 단독 + 일일 실행 엔진** 구조로
실매매 알림 시스템으로 이식하기 위한 최종 설계서이다.
현재 적용 전략은 Q-2-2XS(SSO 35% / QLD 35% / GLD 15% B&H / TLT 15% B&H)이며,
전략은 언제든 변경 가능하다.

### 전체 확정 사항

| 항목 | 확정 |
|------|------|
| UI | **Android 앱 단독** (React Native). 웹 없음 |
| 앱 인증 | **Firebase Auth Email/Password** |
| 푸시 알림 | **FCM** (텍스트만) |
| 백업 알림 | **텔레그램 봇** (FCM과 항상 동일 발송, 히스토리 역할) |
| 스케쥴링 | **GitHub Actions** (퍼블릭, 영구 무료, KST 07:20 이후) |
| 휴장 체크 | **exchange_calendars** (NYSE 공식) |
| 정본 원장 | **JSON + Git** (프라이빗 리포) |
| 주가 데이터 | **CSV** (프라이빗 리포, 매일 1행 누적) |
| 앱 데이터 버스 | **Firebase RTDB** (읽기+쓰기, Spark 무료) |
| 체결 입력 | **앱 -> RTDB -> daily runner** (자동 매칭 + idempotency) |
| 자산 직접 수정 | 앱에서 임의 매매/잔고 보정 가능 |
| 차트 | **RTDB 시계열(자산별 전체 기간) + TradingView Lightweight Charts** |
| FCM 토큰 | **RTDB `/device_tokens/`**, 복수 토큰 대응 |
| QBT 동기화 | **모노리포 + 브랜치 분리** (main=안정, dev=실험) |
| 의존성 | **Poetry** (`poetry install -E live`) |
| model/actual | **명시적 분리** (actual은 독립 원장, model로 덮어쓰기 금지) |
| PendingOrder | **execute_on 없음** |
| cron | **timezone-aware** (`America/New_York`), UTC fallback |
| keepalive | 월 1회 heartbeat |
| 히스토리 | **전체 영구 보존** |
| 비용 | 사실상 **₩0/월** |

### 인프라 정보 (사전 준비 완료)

| 항목 | 값 |
|------|---|
| QBT 리포 (퍼블릭) | `https://github.com/ingbeen/quant` |
| 상태 리포 (프라이빗) | `https://github.com/ingbeen/qbt-live-state.git` |
| Firebase 프로젝트 | `qbt-live` (Spark 요금제) |
| RTDB URL | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| RTDB 위치 | 싱가포르 (asia-southeast1) |
| Android 패키지 | `com.ingbeen.qbtlive` |
| Firebase Auth UID | `SxwvCeg6fRUeUrK9IpyazTzrLJJ2` |
| 텔레그램 봇 | `@qbt_live_alert_bot` |
| GitHub Secrets | `FIREBASE_CONFIG`, `STATE_REPO_PAT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

### 백테스트 절대 규칙 보존 (예외 없음)

- 신호(i일 종가) / 체결(i+1일 시가) 분리
- `SLIPPAGE_RATE = 0.003` (매수/매도 각 0.3%)
- `equity = cash + sum(shares * close)`, 강제 청산 없음
- Pending Order 단일 슬롯, 충돌 시 `PendingOrderConflictError`
- hold_days 상태머신 (Lookahead 금지)
- SSO/QLD: signal은 SPY/QQQ, trade는 SSO/QLD (비대칭)

---

## 1. 전체 아키텍처

### 1.1 다이어그램

```
[GitHub Actions schedule]
  KST 07:20+ (timezone: America/New_York, ET 17:50)
        |
        v
+-------------------------------------------------------------------+
| Daily Runner (Python 3.12, QBT 모노리포 main)                     |
|                                                                    |
| [1] 휴장 체크 -> 비거래일이면 종료                                 |
| [2] yfinance 최근 5일 수집 -> 검증 -> CSV에 오늘 1행 append       |
| [3] CSV 전체 읽기 -> EMA-200 재계산                                |
| [4] 프라이빗 리포 live_state.json 복원                             |
| [5] RTDB unprocessed fills -> pending 자동 매칭 -> actual 반영     |
| [6] 전일 pending -> 당일 시가 model 체결                           |
| [7] 신호 계산 -> projected -> 리밸런싱 -> merge -> 익일 pending    |
| [8] 미입력 체크 (pending 있었는데 fill 없으면 리마인더)            |
| [9] 정본 저장 -> Git push (state + history + CSV)                  |
| [10] RTDB 갱신 (latest, chart_data, history/summary)               |
| [11] 알림: FCM + 텔레그램 동시 발송                                |
+-------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
 [qbt-live-state]      [Firebase RTDB]      [FCM + 텔레그램]
  정본 원장              앱 입출력 버스        알림 (동시)
  - live_state.json     - latest/*
  - applied_fill_ids    - latest/chart_data/*
  - data/stock/*.csv    - history/summary/*
  - history/*           - fills/inbox/*
                        - device_tokens/*
                              ^
                              |
                       [Android 앱]
                       (React Native + FCM)
                       Firebase Auth
```

### 1.2 핵심 원칙

- **앱이 유일한 UI**. 웹 없음.
- **Git = 정본, RTDB = 앱 버스**. 앱은 Git에 직접 접근하지 않음.
- **앱에 GitHub 토큰 절대 없음**.
- **model/actual 분리**. actual은 독립 원장.
- **CSV에서 EMA-200 매일 재계산**. 중간값 의존 없이 항상 원본에서 계산.
- **차트 데이터는 전체 기간**. RTDB에 저장, 앱에서 기간 선택.
- **체결 입력은 pending과 자동 매칭**. 사용자가 사유를 직접 고를 필요 없음.
- **알림은 FCM + 텔레그램 항상 동시**.
- **히스토리 전체 영구 보존**.
- **장애 시 자동 복구하지 않는다**. 즉시 중단 + 알림. 사용자가 상황을 파악하여 디버깅.

### 1.3 리포지토리 구성

```
quant/                              ← QBT 모노리포 (퍼블릭, ingbeen/quant)
├── src/qbt/backtest/               ← 기존 백테스트 코드
├── live/                           ← 실매매 코드 (신규 도메인)
│   ├── CLAUDE.md                   ← live 도메인 가이드
│   ├── src/live/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── models.py
│   │   ├── state.py
│   │   ├── data_fetcher.py
│   │   ├── data_validator.py
│   │   ├── daily_runner.py
│   │   ├── drift.py
│   │   ├── rtdb_gateway.py
│   │   ├── notifier.py
│   │   ├── chart_data.py
│   │   ├── history.py
│   │   └── cli.py
│   └── tests/
│       ├── __init__.py
│       └── conftest.py
├── docs/                           ← 설계 문서
│   ├── DESIGN_QBT_LIVE_FINAL.md
│   ├── TODO_QBT_LIVE.md
│   ├── PROMPT_QBT_LIVE.md
│   └── plans/                      ← Step 별 Implementation Plan
├── pyproject.toml                  ← live extras 포함 (firebase-admin, exchange-calendars, requests)
├── .github/workflows/
│   ├── validate.yml
│   ├── daily_run.yml
│   └── keepalive.yml
└── CLAUDE.md

qbt-live-state/                    ← 프라이빗 (ingbeen/qbt-live-state)
├── live_state.json
├── applied_fill_ids.json
├── data/stock/*.csv
└── history/

qbt-live-app/                      ← React Native 앱
```

**브랜치**: `main`(안정, Actions) / `dev`(실험)

---

## 2. 주가 데이터: CSV 누적

### 2.1 초기 셋업 (1회)

```bash
poetry run python -m live.cli init-data
# yfinance.download(ticker, period="max") -> data/stock/{ticker}.csv (6종)
```

### 2.2 매일 실행

```
1. yfinance 6종 최근 5일 다운로드
2. 데이터 검증 (yfinance 어제 Close vs CSV 마지막 Close)
3. 검증 통과 -> 오늘 1행 CSV append
4. CSV 전체 pandas 읽기 -> EMA-200 계산
5. 신호 판단
6. CSV Git push
```

### 2.3 스플릿 대응

전일 종가 1%+ 차이 -> 즉시 중단 + 알림. 수동: `live.cli rebuild-data --period max`

---

## 3. 데이터 검증 (3개만)

| 검증 | 조건 | 대응 |
|------|------|------|
| **OHLC 논리** | High < Low, 가격 0/음수 | 즉시 중단 + 알림 |
| **전일 종가 연속성** | CSV vs yfinance 1%+ 차이 | 즉시 중단 + 알림 |
| **날짜 누락** | 거래일 빠짐 | 즉시 중단 + 알림 |

---

## 4. 알고리즘 이식

### 4.1 QBT 코드 재사용

시그널/체결/리밸런싱은 **새로 구현하지 않음**. QBT 코어 직접 import.

| 모듈 | 재사용 |
|------|--------|
| `strategies/buffer_zone.py` | `BufferZoneStrategy` |
| `strategies/buy_and_hold.py` | `BuyAndHoldStrategy` |
| `engines/portfolio_planning.py` | `generate_signal_intents`, `compute_projected_portfolio`, `merge_intents` |
| `engines/portfolio_rebalance.py` | `DEFAULT_REBALANCE_POLICY` |
| `engines/portfolio_execution.py` | `execute_orders` |
| `portfolio_configs.py` | `_CONFIG_Q2_2XS` (SSoT) |
| `constants.py` | `SLIPPAGE_RATE` |

### 4.2 일일 실행 순서

```
1.  휴장 체크 -> 비거래일 종료
2.  yfinance 5일 -> 검증 -> CSV append
3.  CSV 전체 -> EMA-200
4.  live_state.json 복원
5.  RTDB fills -> pending 자동 매칭 -> actual 반영
6.  전일 pending -> 당일 시가 model 체결
7.  당일 종가 equity (model + actual)
8.  signal intents -> projected -> 리밸런싱 -> merge
9.  익일 pending 생성
10. 미입력 체크 -> 리마인더
11. Git push (state + history + CSV)
12. RTDB 갱신
13. FCM + 텔레그램 동시 발송
```

### 4.3 BufferZoneStrategy 직렬화

QBT 수정 없이 어댑터로 추출/복원.

### 4.4 회귀 검증

과거 1년 `run_daily()` 순차(model) vs `run_portfolio_backtest()` 비교.

---

## 5. model/actual 원장 분리

### 5.1 LiveState 스키마

```python
@dataclass
class LiveState:
    schema_version: int
    portfolio_id: str
    last_signal_date: str | None
    last_model_execution_date: str | None
    last_rebalance_date: str | None
    shared_cash_model: float
    shared_cash_actual: float
    assets: dict[str, AssetLiveState]
    created_at: str
    updated_at: str

@dataclass
class AssetLiveState:
    asset_id: str
    model_shares: int
    model_avg_entry_price: float
    model_entry_date: str | None
    actual_shares: int
    actual_avg_entry_price: float
    actual_entry_date: str | None
    pending_order: PendingOrderDict | None
    signal_state: str
    entry_hold_days: int
    buffer_zone_state: BufferZoneState | None

class PendingOrderDict(TypedDict):
    """execute_on 없음."""
    asset_id: str
    intent_type: str
    signal_date: str
    current_amount: float
    target_amount: float
    delta_amount: float
    target_weight: float
    hold_days_used: int
    reason: str

@dataclass
class BufferZoneState:
    prev_upper: float | None
    prev_lower: float | None
    hold_state: dict[str, Any] | None
    last_buy_buffer_pct: float
    last_hold_days_used: int
    schema_version: int = 1
```

### 5.2 갱신 규칙

| 상황 | model | actual |
|------|-------|--------|
| 초기 | 0주, cash=1억 | model과 동일 |
| model 체결 | model 갱신 | 변경 없음 |
| actual fill | 변경 없음 | actual 갱신 |
| 입력 없는 날 | model 갱신 | **이전 actual 유지** |

---

## 6. 체결 입력: 자동 매칭

### 6.1 자동 매칭

```python
def classify_fill(fill: ActualFill, state: LiveState) -> str:
    asset = state.assets.get(fill.asset_id)
    if asset and asset.pending_order:
        pending = asset.pending_order
        pending_is_buy = pending["intent_type"] in ("ENTER_TO_TARGET", "INCREASE_TO_TARGET")
        fill_is_buy = fill.direction == "buy"
        if pending_is_buy == fill_is_buy:
            return "system_fill"
    return "personal_trade"
```

### 6.2 idempotency

`applied_fill_ids.json`(Git 정본)으로 중복 방지. 90일 초과 자동 정리.

### 6.3 미입력 리마인더

전일 pending 후 fill 없으면 매일 알림 반복.

### 6.4 자산 직접 수정

앱에서 주수/현금 직접 수정 -> RTDB에 `balance_adjust`로 기록.

---

## 7. 차트: TradingView Lightweight Charts

CSV 전체에서 시계열 -> RTDB에 매일 덮어쓰기. 자산별 전체 기간. ~780KB.
앱: WebView + TradingView LC. 기간 [3M/6M/1Y/전체]. 신호/체결 마커.

---

## 8. 알림: FCM + 텔레그램 동시

| 종류 | 빈도 |
|------|------|
| **일일 리포트** (200일선 근접도 포함) | 매일 |
| **시그널 신호** | 발생 시 |
| **리밸런싱** | 발생 시 |
| **에러** | 발생 시 |
| **미입력 리마인더** | 입력까지 매일 |

200일선 근접도: `(close - ema_200) / ema_200 * 100`

---

## 9. Android 앱 (React Native)

인증: Firebase Auth Email/Password. UID: `SxwvCeg6fRUeUrK9IpyazTzrLJJ2`.

메뉴 (하단 4탭):

| 탭 | 내용 |
|----|------|
| **홈** | 포트폴리오, 200일선 근접도, 신호, 체결 예정, 마지막 실행 시각, 알림 히스토리 |
| **차트** | 자산 선택, TradingView LC, 기간 선택, 신호/체결 마커 |
| **거래** | 내 자산 관리(직접 수정), 체결 입력(과거 날짜, 자동 매칭), 체결 히스토리(필터), Drift |
| **설정** | 계정, 알림, 시스템 상태, 버전 |

---

## 10. 상태 저장

### 10.1 Git 정본 (qbt-live-state)

모든 히스토리 **영구 보존**. 자동 정리 없음.
`applied_fill_ids.json`만 90일 초과 ID 자동 정리.

### 10.2 RTDB

```
/latest/portfolio, signals, pending_orders, drift
/latest/chart_data/ (6자산 전체 기간)
/history/summary/ (90일, 앱 표시용)
/fills/inbox/{uuid}
/device_tokens/{device_id}
```

### 10.3 역할 분리

| 경로 | 쓰기 | 읽기 |
|------|------|------|
| Git 전체 | daily runner | daily runner |
| RTDB `/latest/*`, `/history/*` | daily runner (Admin) | 앱 |
| RTDB `/fills/*` | 앱 | daily runner (Admin) |
| RTDB `/device_tokens/*` | 앱 | daily runner (Admin) |

---

## 11. 실패/예외 대응

**원칙: 자동 복구하지 않는다. 즉시 중단하고 알림을 보낸다.**
사용자가 상황을 직접 파악하여 디버깅할 수 있어야 한다.

| 시나리오 | 대응 |
|---------|------|
| 데이터 수집 실패 | **중단** + FCM/텔레그램: "yfinance 수집 실패. 에러: {상세}" |
| 데이터 검증 실패 (OHLC) | **중단** + FCM/텔레그램: "OHLC 논리 오류. {자산} High<Low. 값: {상세}" |
| 데이터 검증 실패 (종가 연속성) | **중단** + FCM/텔레그램: "전일 종가 불일치. {자산} CSV:{값} vs yfinance:{값}. 스플릿 의심" |
| 데이터 검증 실패 (날짜 누락) | **중단** + FCM/텔레그램: "거래일 누락. CSV 마지막: {날짜}, 오늘: {날짜}" |
| 계산 실패 (RuntimeError) | **중단** + FCM/텔레그램: "엔진 실행 실패. 에러: {상세}. 상태 변경 없음" |
| FCM 전송 실패 | 텔레그램은 독립 발송. FCM 에러 로그 기록 |
| 텔레그램 전송 실패 | FCM은 독립 발송. 텔레그램 에러 로그 기록 |
| RTDB 읽기 실패 (fills) | **중단** + FCM/텔레그램: "RTDB fills 읽기 실패. 에러: {상세}" |
| RTDB 쓰기 실패 | **중단** + FCM/텔레그램: "RTDB 갱신 실패. Git 정본은 저장됨. 에러: {상세}" |
| Git push 실패 | **중단** + FCM/텔레그램: "Git push 실패. 상태 미저장. 에러: {상세}" |
| fill 중복 반영 위험 | applied_fill_ids로 skip + 로그 기록 (정상 동작) |
| pending order 충돌 | **중단** + FCM/텔레그램: "PendingOrderConflict. {자산}. 상태 변경 없음" |
| live_state.json 파싱 실패 | **중단** + FCM/텔레그램: "상태 파일 손상. 파싱 에러: {상세}" |
| FCM 토큰 만료 | send_each 후 unregistered 감지 -> 해당 토큰 RTDB에서 제거 (정상 동작) |
| 체결 미입력 | 매일 리마인더 FCM/텔레그램 |
| GitHub Actions 실패 (retry 포함) | notify-failure job에서 FCM/텔레그램: "2회 연속 실패" |

**모든 에러 알림에는 에러 상세 메시지를 포함**하여 사용자가 원인을 파악할 수 있게 한다.
자동 롤백, 자동 복원, 자동 재시도(Actions retry job 제외)는 하지 않는다.

---

## 12. 스케쥴링

```yaml
cron: '50 17 * * 1-5'
timezone: America/New_York
```

Poetry 캐싱. retry(5분 후 1회). 실패 시 FCM+텔레그램. keepalive 매월 1일.

---

## 13. 보안

| 시크릿 | 용도 |
|--------|------|
| `FIREBASE_CONFIG` | Admin SDK |
| `STATE_REPO_PAT` | 프라이빗 리포 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 |
| `TELEGRAM_CHAT_ID` | 텔레그램 |

보안 계층: Email/Password + RTDB Rules(기본). App Check(Phase 5, 선택).

---

## 14. Drift

```python
model_equity = shared_cash_model + sum(model_shares * close)
actual_equity = shared_cash_actual + sum(actual_shares * close)
drift_pct = abs(model_equity - actual_equity) / model_equity * 100
```

0~3% 정상 / 3~5% 주의 / 5%+ 보정 필요.

---

## 15. 구현 로드맵

| Phase | 범위 |
|-------|------|
| **1** | 엔진, state, CSV, 검증, regression, cron, keepalive |
| **2** | FCM+텔레그램, chart_data, RTDB read model |
| **3** | RN앱: Login, 홈/차트/거래/설정, TradingView LC |
| **4** | 체결 자동 매칭, drift, 미입력 리마인더 E2E |
| **5** | 안정화, 문서화, App Check 검토 |

---

## 16. 비용

사실상 **₩0/월**. 한도 초과 시 과금 가능.

| 항목 | 무료 한도 | 예상 사용 |
|------|----------|----------|
| GitHub Actions | 무제한 (퍼블릭) | ~150분/월 |
| Firebase FCM | 무제한 | ~5건/일 |
| Firebase RTDB | 1GB / 10GB | ~1MB / ~100MB |
| Firebase Auth | 50K MAU | 1명 |
| 텔레그램 | 무제한 | ~5건/일 |
| yfinance | 무료 | 6건/일 |

---

## 부록 A: 함수 시그니처

```python
# daily_runner.py
def run_daily(trade_date, state, market_bundle, pending_fills, applied_fill_ids) -> DailyResult

# state.py
def load_state(path) -> LiveState
def save_state(state, path) -> None
def create_initial_state(total_capital) -> LiveState
def load_applied_fill_ids(path) -> dict[str, str]  # ID → ISO 8601 KST 타임스탬프
def save_applied_fill_ids(ids: dict[str, str], path) -> None
def cleanup_old_fill_ids(ids: dict[str, str], max_age_days=90) -> dict[str, str]

# data_fetcher.py
def fetch_recent_ohlc(ticker, days=5) -> pd.DataFrame
def append_today_to_csv(csv_path, today_row) -> None
def rebuild_full_csv(ticker, csv_path, period="max") -> None

# data_validator.py
def validate_ohlc_logic(row) -> list[str]
def validate_prev_close(csv_close, yf_close) -> list[str]
def validate_date_gap(csv_last, today, calendar) -> list[str]

# rtdb_gateway.py
def fetch_unprocessed_fills(app) -> list[ActualFill]
def mark_fills_processed(app, keys) -> None
def write_read_model(app, state, result) -> None
def write_chart_data(app, series) -> None
def read_device_tokens(app) -> list[str]
def remove_invalid_tokens(app, tokens) -> None

# notifier.py
def send_all(tokens, tg_token, tg_chat, result) -> None
def send_failure_all(tokens, tg_token, tg_chat, msg) -> None

# drift.py
def classify_fill(fill, state) -> str
def apply_fills_idempotent(state, fills, applied_ids) -> tuple[LiveState, set[str]]
def compute_drift(state, closes) -> DriftReport

# chart_data.py
def build_chart_series(csv_dir, user_trades) -> dict[str, ChartSeries]
```

## 부록 B: 데이터 모델

```python
@dataclass
class DailyResult:
    execution_date: date
    updated_state: LiveState
    updated_applied_fill_ids: dict[str, str]  # ID → ISO 타임스탬프
    signals: dict[str, SignalDetection]
    order_intents: dict[str, OrderIntent]
    executions: ExecutionResult | None
    rebalance_triggered: bool
    model_equity: float
    actual_equity: float
    drift_pct: float
    ema_distances: dict[str, float]
    notification_body: str
    pending_fill_reminders: list[str]
    chart_series: dict[str, ChartSeries]

@dataclass
class ActualFill:
    asset_id: str
    direction: str
    actual_price: float
    actual_shares: int
    trade_date: str
    input_time_kst: str
    memo: str | None
    rtdb_key: str
    reason: str = ""

@dataclass
class ChartSeries:
    dates: list[str]
    close: list[float]
    ema_200: list[float | None]
    upper_band: list[float | None]
    lower_band: list[float | None]
    buy_signals: list[int]
    sell_signals: list[int]
    user_buys: list[int]
    user_sells: list[int]

@dataclass
class DriftReport:
    model_equity: float
    actual_equity: float
    drift_pct: float
    per_asset: dict[str, AssetDrift]
    recommendation: str
```
