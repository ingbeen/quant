# QBT Live 실시간 매매 알림 시스템 설계서

> 이 문서는 **역할 / 원칙 / 아키텍처** 를 담당합니다.
> 구체적인 함수 시그니처 / dataclass 정의 / 구현 디테일은 코드가 SoT (Source of Truth) 입니다.
>
> - 모듈별 역할: [live/CLAUDE.md](../live/CLAUDE.md)
> - 데이터 모델: [live/src/live/models.py](../live/src/live/models.py)
> - CLI 명령: [live/src/live/cli.py](../live/src/live/cli.py)

## 0. 개요

QBT 프로젝트의 포트폴리오 전략을 **Android 앱 + 일일 실행 엔진** 구조로 실매매 알림 시스템으로 이식한다. 현재 전략은 Q-2-2XS (SSO/QLD/GLD/TLT 조합) 이며, 전략은 `portfolio_configs.py` 수준에서 변경 가능하다.

### 전체 확정 사항

| 항목 | 확정 |
|------|------|
| UI | Android 앱 (React Native). 웹 없음 |
| 앱 인증 | Firebase Auth Email/Password |
| 푸시 알림 | FCM (텍스트) + 텔레그램 봇 (동시 발송) |
| 스케쥴러 | GitHub Actions (퍼블릭 리포, 무료) |
| 휴장 체크 | exchange_calendars NYSE 달력 |
| 정본 원장 | JSON + Git (프라이빗 리포 `qbt-live-state`) |
| 주가 데이터 | CSV (프라이빗 리포, 매일 1 행 누적) |
| 앱 데이터 버스 | Firebase RTDB (Spark 무료) |
| 체결 입력 | 앱 → RTDB inbox → daily runner (자동 매칭 + idempotency) |
| 자산 직접 수정 | 앱 → RTDB `/balance_adjust/inbox/` → daily runner |
| 차트 | RTDB 시계열 + TradingView Lightweight Charts |
| FCM 토큰 | RTDB `/device_tokens/`, 복수 토큰 대응 |
| 의존성 | Poetry (`poetry install -E live`) |
| model/actual | 명시적 분리 원장. 서로 덮어쓰기 금지 |
| PendingOrder | 단일 슬롯, `execute_on` 없음 |
| cron | timezone-aware `America/New_York` |
| keepalive | 월 1 회 빈 commit (`quant` 퍼블릭 리포 대상) |
| 히스토리 | 전체 영구 보존 |
| ephemeral 원칙 | CLI 는 매 실행마다 상태 리포를 temp clone → 작업 → push → cleanup |
| 로컬 / Actions 동일성 | 완전히 같은 CLI 코드 경로 |
| 비용 | 사실상 ₩0/월 |

### 인프라 정보

| 항목 | 값 |
|---|---|
| QBT 리포 (퍼블릭) | `https://github.com/ingbeen/quant` |
| 상태 리포 (프라이빗) | `https://github.com/ingbeen/qbt-live-state.git` |
| Firebase 프로젝트 | `qbt-live` (Spark 요금제) |
| RTDB URL | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지 | `com.ingbeen.qbtlive` |
| 텔레그램 봇 | `@qbt_live_alert_bot` |
| GitHub Secrets | `FIREBASE_CONFIG`, `STATE_REPO_PAT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

### 백테스트 절대 규칙 (예외 없음)

- 신호(i일 종가) / 체결(i+1일 시가) 분리
- 매수/매도 각각 고정 슬리피지 적용
- `equity = cash + Σ(shares × close)`, 강제 청산 없음
- Pending Order 단일 슬롯, 충돌 시 내부 예외
- hold_days 상태 머신 (Lookahead 금지)
- SSO/QLD: signal 은 SPY/QQQ, trade 는 SSO/QLD (비대칭)

---

## 1. 전체 아키텍처

### 1.1 다이어그램

```
[GitHub Actions schedule]
  KST 07:50 (timezone: America/New_York, ET 17:50)
        |
        v
+-------------------------------------------------------------------+
| cli.main() (공통 알림 훅)                                          |
|                                                                    |
|  ├─ 휴장 체크 (NYSE)  → 비영업일이면 조기 정상 종료               |
|  ├─ ephemeral_state_repo: qbt-live-state shallow clone            |
|  │   ├─ live_state.json 로드 + idempotency 체크                    |
|  │   ├─ yfinance 최근 OHLC → 검증 3 종 → CSV append                |
|  │   ├─ market_bundle 준비 (EMA 재계산)                            |
|  │   ├─ RTDB: fills / balance_adjusts 가져오기                     |
|  │   ├─ run_daily() [순수 계산, 파일 I/O 없음]                     |
|  │   │   1. fills → actual 축 반영 (idempotent)                    |
|  │   │   2. 전일 pending → 당일 시가 체결 (model 축)               |
|  │   │   3. 당일 종가 model_equity                                 |
|  │   │   4. 시그널 → projected → 리밸런싱 → 익일 pending 생성     |
|  │   │   5. balance_adjust → actual 축 교체 (idempotent)           |
|  │   │   6. drift.compute_drift → DriftReport 생성                 |
|  │   ├─ state + applied_*_ids 저장                                 |
|  │   ├─ history 영구 append (fail-fast, silent continue 없음)      |
|  │   ├─ RTDB /latest/* + chart_data 갱신                           |
|  │   └─ FCM + 텔레그램 일일 리포트 동시 발송                      |
|  └─ commit / push / tempdir cleanup                                |
|                                                                    |
|  어느 단계에서든 예외 발생 시:                                     |
|     main() 공통 훅이 _safe_notify_failure 로 실패 알림 발송        |
|     (notify-failure 커맨드 자체는 재귀 방지를 위해 제외)           |
+-------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
 [qbt-live-state]      [Firebase RTDB]      [FCM + 텔레그램]
  정본 원장 / 데이터     앱 입출력 버스        알림 (동시)
                              ^
                              |
                       [Android 앱]
```

### 1.2 핵심 원칙

- **앱이 유일한 UI**. 웹 없음
- **Git = 정본, RTDB = 앱 버스**. 앱은 Git 에 직접 접근하지 않는다
- **앱에 GitHub 토큰 절대 없음**
- **model / actual 분리**. actual 은 앱 입력(fills / balance_adjust) 으로만 갱신
- **EMA 는 CSV 전체를 매일 재계산**. 중간값 의존 없음
- **ephemeral 모드**: CLI 는 상태 리포를 매 실행 clone/push. 로컬 / Actions 가 동일 경로
- **체결 입력은 pending 과 자동 매칭**. 분류 결과(system_fill / personal_trade) 는 audit
- **알림은 FCM + 텔레그램 항상 동시 발송**. 한쪽 실패가 다른 쪽을 막지 않는다
- **알림 채널 자체의 실패는 로그로만 기록** — 알림 발송이 실패한 상태에서 다시 알림을
  보내는 것은 모순이므로 재발송 금지
- **히스토리 전체 영구 보존**. 자동 정리는 `applied_*_ids.json` 만 (최대 보관 일수는
  `constants.APPLIED_FILL_IDS_MAX_AGE_DAYS`)
- **장애 시 자동 복구하지 않는다 + 무조건 알림**: 어떤 CLI 커맨드든 예외 발생 시
  `cli.main()` 공통 훅이 `_safe_notify_failure` 로 실패 알림을 발송한 뒤 종료한다.
  `notify-failure` 커맨드 자체는 재귀 방지를 위해 훅에서 제외된다.
- **silent fallback 금지**: history 저장 실패 / NYSE 달력 로드 실패 등 어떤 fallback 도
  삼키지 않고 예외를 상위로 전파한다
- **원자성**: 모든 변경은 ephemeral 컨텍스트 내에서 원자적 — RTDB 쓰기가 실패하면
  Git push 도 건너뛴다

### 1.3 리포지토리 구성

```
quant/                              ← QBT 모노리포 (퍼블릭)
├── src/qbt/                        ← 기존 백테스트 코드
├── live/                           ← 실매매 도메인
│   ├── src/live/                   ← 모듈 목록은 live/CLAUDE.md 참고
│   └── tests/
├── docs/
│   ├── DESIGN_QBT_LIVE_FINAL.md    ← 본 문서
│   ├── TEST_QBT_LIVE_MANUAL.md     ← 수동 테스트 가이드
│   └── plans/                      ← 작업 계획서
├── .github/workflows/
│   ├── daily_run.yml               ← cron + workflow_dispatch (trade_date 입력)
│   └── keepalive.yml               ← 월 1 회 quant 빈 commit
└── pyproject.toml                  ← live extras

qbt-live-state/                    ← 프라이빗 상태 리포
├── live_state.json                 ← model/actual 정본
├── applied_fill_ids.json           ← fill idempotency 원장 (90일 cleanup)
├── applied_balance_adjust_ids.json ← balance_adjust idempotency 원장 (90일 cleanup)
├── data/stock/*.csv                ← 주가 시계열
└── history/
    ├── daily/*.json                ← 일별 상세 (덮어쓰기 가능)
    ├── summary.jsonl               ← 일별 요약 (영구 append)
    ├── user_trades.jsonl           ← fill 처리 audit (차트 마커)
    ├── signals.jsonl               ← 신호 이력 (차트 마커)
    └── balance_adjusts.jsonl       ← 자산 보정 audit
```

---

## 2. 주가 데이터: CSV 누적

### 2.1 초기 시드

최초 1 회 `init-data` 명령으로 yfinance 에서 전체 기간을 받아 `data/stock/{TICKER}.csv` 를 생성한다. ephemeral 모드에서는 CLI 가 자동으로 qbt-live-state 를 clone → CSV 생성 → commit / push.

### 2.2 매일 실행

1. yfinance 로 최근 N 거래일 다운로드 (`DEFAULT_RECENT_FETCH_DAYS` 참고)
2. 데이터 검증 3 종 (§3 참고)
3. 검증 통과 시 오늘 1 행을 기존 CSV 에 append
4. MA 는 매일 CSV 전체를 기반으로 재계산 (중간값 의존 없음)

### 2.3 스플릿 대응

`validate_prev_close` 가 CSV 와 yfinance 의 **같은 날짜** 종가를 비교하여 1% 이상 차이 시 즉시 중단한다. 이 검증은 구조적으로 다음 두 가지 모두를 감지한다.

- 스플릿 / 무상증자 (yfinance 가 과거 가격을 재조정)
- 사용자의 수동 CSV 조작 (스플릿 의심과 동일한 증상)

스플릿 복구는 `rebuild-data {TICKER}` 명령으로 전체 기간 재다운로드.

---

## 3. 데이터 검증 (3 종)

모든 검증 함수는 `live/src/live/data_validator.py` 에 정의되고 `_refresh_live_csvs` 가 매 실행마다 호출한다.

| 검증 | 트리거 | 대응 |
|------|------|------|
| **OHLC 논리** | High < Low, 가격 0/음수, Close 범위 이탈 | 즉시 중단 + 알림 |
| **전일 종가 연속성** | CSV vs yfinance 동일 날짜 종가 1% 이상 차이 | 즉시 중단 + 알림 |
| **거래일 누락** | NYSE 달력 기준 CSV 마지막 날짜와 trade_date 사이에 누락된 영업일 존재 | 즉시 중단 + 알림 |

---

## 4. 알고리즘 이식

### 4.1 QBT 코어 재사용

시그널 / 체결 / 리밸런싱 로직은 새로 구현하지 않는다. QBT 백테스트 코어 (`qbt.backtest.*`) 를 직접 import 하여 재사용한다.

재사용 모듈의 종류 (`strategies/buffer_zone`, `engines/portfolio_planning`, `engines/portfolio_rebalance`, `engines/portfolio_execution`, `portfolio_configs` 등) 는 시간이 지나며 변화할 수 있으므로, 항상 `live/src/live/daily_runner.py` 의 import 선언을 SoT 로 참조한다.

### 4.2 일일 실행 순서 (run-daily)

CLI 진입점(`cli.main()`) 이 공통 예외 훅으로 전 과정을 감싸고, 실제 계산은
`daily_runner.run_daily()` 가 순수 함수로 수행한다.

`run_daily()` 의 시그니처와 처리 순서:

```python
def run_daily(
    trade_date,
    state,
    market_bundle,
    pending_fills,
    applied_fill_ids,
    pending_adjusts=None,
    applied_balance_adjust_ids=None,
) -> DailyResult:
```

1. fills → actual 축 반영 (idempotent)
2. 전일 pending → 당일 시가 체결 (model 축)
3. 당일 종가 model_equity 산출
4. 시그널 생성 → projected → 리밸런싱 → 익일 pending 저장
5. balance_adjust → actual 축 교체 (idempotent) — fills 보다 나중
6. `drift.compute_drift` 호출 → 완전 `DriftReport` 생성

주요 원칙:

- **휴장 / idempotency 체크는 ephemeral clone 전** — 불필요한 git clone 비용 차단
- **`run_daily` 는 순수 계산** — 파일 I/O / 네트워크 호출 없음. CLI 계층이 I/O 를 감싼다
- **fills 먼저, balance_adjust 나중** — 신호 기반 체결이 먼저 반영된 뒤 사용자 직접
  보정이 최종 잔고를 덮어쓴다. 이 순서는 `run_daily` **내부에서** 보장된다.
- **drift 는 `drift.compute_drift` 가 유일 정본** — daily_runner 는 간이 계산을 하지
  않고 `DailyResult.drift_report` 에 완전 `DriftReport` 를 담아 반환한다.
- **모든 Git/RTDB 쓰기는 원자적** — 중간 실패 시 push 도 건너뛴다
- **fail-fast**: history 저장 실패 / NYSE 달력 로드 실패 등은 silent continue 하지 않고
  예외를 전파해 `cli.main()` 공통 알림 훅에 도달하게 한다

### 4.3 BufferZoneStrategy 직렬화

QBT 코어를 수정하지 않고 어댑터 (`buffer_serializer.py`) 로 BufferZoneStrategy 의 내부 상태를 추출 / 복원한다.

### 4.4 회귀 검증

`test_regression.py` 가 과거 1 년 구간에 대해 `run_daily()` 를 순차 호출한 model 축 결과와 `run_portfolio_backtest()` 의 결과를 비교한다. 두 경로가 매일 동일한 equity / positions / cash 를 반환해야 한다.

---

## 5. model / actual 원장 분리

### 5.1 개념

`live_state.json` 은 model 축과 actual 축을 **두 개의 독립된 원장** 으로 유지한다. model 은 daily runner 의 이론 포지션이고, actual 은 사용자가 실제로 체결한 포지션이다. 두 축은 서로를 덮어쓰지 않는다.

실제 dataclass 정의 (`LiveState`, `AssetLiveState`, `BufferZoneState`, `PendingOrderDict`) 는 `live/src/live/models.py` 를 참조. 필드 변경 시 이 섹션은 업데이트하지 않아도 됨 — 코드가 SoT.

**signal_state**: `AssetLiveState.signal_state` 는 QBT 포트폴리오 엔진의
`AssetState.signal_state` 와 **동일한** `Literal["buy", "sell"]` 2 값을 사용한다.
별도 매핑 계층 없이 `daily_runner._build_asset_states` 가 그대로 전달한다.

- `"buy"`: 가장 최근 signal intent 가 `ENTER_TO_TARGET` 이었다 (매수 방향)
- `"sell"`: 가장 최근 signal intent 가 `EXIT_ALL` 이었다 (매도 방향). 초기 상태도 `"sell"` (포지션 없음)

참고: `SignalDetection.state` 는 **당일 감지 결과** 를 나타내는 별도 타입이며
`Literal["buy", "sell", "none"]` 3 값을 가진다. `BUY_INTENT_TYPES`
(`ENTER_TO_TARGET`, `INCREASE_TO_TARGET`) 이면 `"buy"`, `SELL_INTENT_TYPES`
(`EXIT_ALL`, `REDUCE_TO_TARGET`) 이면 `"sell"`, 없으면 `"none"` (오늘 새 신호 없음).
`AssetLiveState.signal_state` (누적 원장) 와는 수명 / 저장 여부 / 값 집합이 모두 다르다.

참고: QBT `BufferZoneStrategy._hold_state` 는 전략 내부의 hold_days 상태머신(매수
확정 대기) 이며 live 의 `signal_state` 와는 전혀 다른 개념이다.

**SCHEMA_VERSION 정책**: `live.constants.SCHEMA_VERSION` 은 `live_state.json` 포맷이
변경될 때마다 증가한다. 기존 버전 파일은 `state.load_state` 가 `ValueError` 로
즉시 실패하며, 사용자는 `init` 재실행 또는 수동으로 JSON 을 마이그레이션해야 한다.

### 5.2 갱신 규칙

| 이벤트 | model 갱신 | actual 갱신 |
|---|---|---|
| 초기화 | 0 주, cash = 초기 자본 | model 과 동일 |
| 전일 pending 의 model 체결 | ✅ | 변경 없음 |
| actual fill 도착 (`/fills/inbox/`) | 변경 없음 | ✅ |
| balance_adjust 도착 (`/balance_adjust/inbox/`) | 변경 없음 | ✅ (교체) |
| fill 미입력 날 | ✅ | 이전 값 유지 |

---

## 6. 체결 입력 및 자산 보정

### 6.1 fill 자동 매칭

앱은 `/fills/inbox/{uuid}` 에 체결 레코드를 쓴다. daily runner 는 이를 읽어 다음 규칙으로 분류한다.

- **system_fill**: 해당 자산에 pending_order 가 있고, pending 의 방향 (buy/sell) 과 fill 의 방향이 일치
- **personal_trade**: pending 이 없거나 방향이 다름

분류 결과는 actual 축에 동일하게 반영되며, 분류 자체는 audit / drift 분석 용도로 기록된다. 실제 분류 로직은 `drift.classify_fill` 참고.

### 6.2 idempotency

`applied_fill_ids.json` (Git 정본) 에 처리된 rtdb_key 를 기록한다. 90 일 초과 ID 는 자동 정리. 동일 key 의 재실행은 항상 no-op.

### 6.3 미입력 리마인더

당일 실행 시 pending_order 가 있는 자산 중 해당 자산에 대한 fill 이 들어오지 않은 경우 리마인더에 포함된다. 일부 자산만 체결된 상황에서도 나머지 미체결 pending 은 리마인더에 남는다.

### 6.4 자산 직접 수정 (balance_adjust)

사용자가 앱에서 잔고를 직접 덮어쓰고 싶을 때 (세금/배당/오프라인 거래 일괄 반영 등) 사용하는 경로.

**흐름**:

1. 앱이 `/balance_adjust/inbox/{uuid}` 에 `{asset_id?, new_shares?, new_cash?, reason, input_time_kst}` 기록
2. daily runner 가 해당 inbox 를 읽고 fills 처리 직후에 각 adjust 를 적용
3. `asset_id` + `new_shares` 가 있으면 해당 자산의 `actual_shares` 를 **덮어쓴다** (평균가 / entry_date 는 유지, 단 shares=0 이면 리셋)
4. `new_cash` 가 있으면 `shared_cash_actual` 을 덮어쓴다
5. `applied_balance_adjust_ids.json` 으로 idempotency 보장 (90 일 정리)
6. `history/balance_adjusts.jsonl` 에 audit append. 차트 마커 대상이 아님
7. 처리 완료 후 RTDB inbox 의 `processed=true` 로 마킹

balance_adjust 는 "이벤트" 가 아니라 "최종 잔고 교체" 이므로 차트에는 표시되지 않는다.

---

## 7. 차트: TradingView Lightweight Charts

CSV 전체를 읽어 자산별 시계열 (dates, close, ma_value, upper_band, lower_band) 을 생성하고 RTDB `/latest/chart_data/{asset_id}` 에 덮어쓴다. 자산 ID 는 live 포트폴리오의 각 슬롯 `asset_id` 를 그대로 사용한다 (소문자).

마커:

- **buy_signals / sell_signals**: `history/signals.jsonl` 에 누적된 과거 신호 이력을 인덱스로 변환
- **user_buys / user_sells**: `history/user_trades.jsonl` 에 누적된 fill 처리 기록을 인덱스로 변환

`ma_value` 는 자산 슬롯의 `ma_window` 에 독립적이며, 앞
`ma_window - 1` 개 인덱스는 워밍업 구간으로 `null` 이다. Firebase RTDB 는 빈 배열을
저장하지 않으므로 마커 리스트가 비어 있으면 해당 키가 아예 생성되지 않는다.

앱은 WebView + TradingView Lightweight Charts 로 시계열을 렌더링하며, 기간 선택 (3M / 6M / 1Y / 전체) 은 앱 측에서 처리한다.

---

## 8. 알림: FCM + 텔레그램

| 종류 | 내용 | 빈도 |
|---|---|---|
| **일일 리포트** | model/actual equity, drift, 시그널(buy/sell), MA 근접도, 리밸런싱 여부, 미입력 리마인더 건수 | 매 run-daily 정상 실행 |
| **실패 알림** | 실패 커맨드 이름 + 에러 상세 메시지 | 어떤 CLI 커맨드든 예외 발생 시 (`notify-failure` 제외) |

MA 근접도 = `(close − ma_value) / ma_value` (비율, 음수 가능). `ma_value` 는 자산
슬롯의 `ma_window` 에 따라 결정된다.

`SignalDetection.upper_band / lower_band` 는 live 에서 즉시 재계산하지 않고
`BufferZoneStrategy._prev_upper / _prev_lower` (전략이 다음 거래일 판단에 사용하는
밴드 값) 를 `buffer_serializer.get_current_bands` 어댑터로 읽어 그대로 노출한다.
이를 통해 알림/차트에 표시되는 밴드 값과 전략의 실제 판단 기준이 일치한다.

**발송 구조**:

- `cli.main()` 의 공통 예외 훅이 모든 커맨드의 예외를 캐치하여
  `_safe_notify_failure` 를 호출한다. 이 훅은 `notify-failure` 커맨드 자체는 재귀
  방지를 위해 통과시키지 않는다.
- FCM 과 텔레그램은 **항상 동시 발송** 하며, 한쪽 채널의 실패가 다른 쪽을 막지
  않는다. FCM 은 device_tokens 대상이 없어도 오류가 발생하지 않는다 (no-op).
  만료 토큰은 RTDB `/device_tokens/` 에서 자동 정리된다.
- **알림 채널 자체의 실패는 로그로만 기록한다** (`logger.error(..., exc_info=True)`).
  이미 실패한 흐름에서 알림 발송이 또 실패했다고 알림을 다시 보내는 것은 모순이며
  무한 루프 / 토큰 낭비를 유발하므로 절대 재발송하지 않는다. 실제 구현은
  `notifier._safe_fcm` / `_safe_telegram` 참고.

---

## 9. Android 앱 (React Native)

별도 프로젝트 (`qbt-live-app`) 에서 구현되며 본 설계서의 범위 밖이다. 앱 요구사항 요약:

- Firebase Auth (Email/Password) 로 1 회 로그인
- FCM 토큰을 RTDB `/device_tokens/` 에 등록
- 홈/차트/거래/설정 4 탭
- `/latest/*` 를 읽어 포트폴리오 / 시그널 / 차트 표시
- `/fills/inbox/` 와 `/balance_adjust/inbox/` 에 쓰기

---

## 10. 상태 저장

### 10.1 Git 정본 (qbt-live-state)

모든 히스토리는 영구 보존한다. 자동 정리는 `applied_fill_ids.json` 과 `applied_balance_adjust_ids.json` 두 파일의 90 일 초과 ID 에만 적용된다. 실제 거래 기록 / 신호 / 요약은 자동 삭제되지 않는다.

### 10.2 RTDB 경로 구조

```
/latest/portfolio              ← 전체 자산 요약 + assets/{sso,qld,gld,tlt}
/latest/signals/{asset}        ← 시그널 상태 / 밴드 / EMA
/latest/pending_orders/{asset} ← 익일 체결 예정 주문
/latest/drift                  ← model vs actual 차이
/latest/chart_data/{asset}     ← 차트용 시계열
/history/summary/{YYYY-MM-DD}  ← 일별 요약 (영구 누적, 앱은 최근 N 개만 표시)
/fills/inbox/{uuid}            ← 앱이 쓰는 체결 queue
/balance_adjust/inbox/{uuid}   ← 앱이 쓰는 잔고 보정 queue
/device_tokens/{device_id}     ← FCM 토큰
```

RTDB 는 "앱 ↔ daily runner" 버스이며, 정본 저장소가 아니다. `/latest/*` 는 매 실행마다 전체 갱신되므로 앱이 직접 쓰면 다음 실행에서 덮어써진다 (inbox 패턴을 쓰는 이유).

### 10.3 역할 분리

| 경로 | 쓰기 주체 | 읽기 주체 |
|---|---|---|
| qbt-live-state (Git) | daily runner (ephemeral) | daily runner |
| `/latest/*`, `/history/*` | daily runner (Admin SDK) | 앱 |
| `/fills/*`, `/balance_adjust/*` | 앱 | daily runner (Admin SDK) |
| `/device_tokens/*` | 앱 | daily runner (Admin SDK) |

---

## 11. 실패 / 예외 대응

**원칙: 자동 복구하지 않는다. 어떤 단계든 실패하면 즉시 중단 + 무조건 알림.**

| 시나리오 | 대응 |
|---|---|
| 비영업일 trade_date (NYSE 휴장) | 조기 정상 종료 (알림 없음, 로그만) |
| 같은 trade_date 재실행 (cron 모드) | 조기 정상 종료 (알림 없음, 로그만). `--trade-date` 명시 시 bypass |
| 잘못된 `--trade-date` 입력 (ISO 파싱 실패) | 중단 + 알림 |
| NYSE 달력 로드 실패 (`_get_nyse_calendar`) | 중단 + 알림 (fallback 금지 — gap 검증 skip 하지 않음) |
| 데이터 수집 실패 (yfinance 에러) | 중단 + 알림 |
| 데이터 검증 실패 (OHLC / 종가 / 날짜 gap) | 중단 + 알림 |
| state 파일 파싱 실패 | 중단 + 알림 |
| 계산 실패 (engine RuntimeError) | 중단 + 알림. state 는 저장되지 않음 |
| RTDB 초기화 실패 (`run-daily` / `fetch-fills`) | 중단 + 알림. `_require_rtdb_app` 가 RuntimeError 전파 |
| RTDB 읽기 실패 (fills / balance_adjusts) | 중단 + 알림 |
| `compute_drift` 에 closes 누락 (내부 불변조건) | 중단 + 알림 (`RuntimeError("내부 불변조건 위반")`) |
| fill 의 direction 이 buy/sell 외 값 | 입구(`rtdb_gateway`) 에서 `ValueError`, 내부(`drift`) 에서 `RuntimeError("내부 불변조건 위반")` |
| balance_adjust 의 new_shares/new_cash 가 둘 다 null | 중단 + 알림 (`ValueError`) |
| unknown asset_id 가 포함된 fill/balance_adjust | 중단 + 알림 (`ValueError("알 수 없는 asset_id")`) |
| 보유량 초과 매도 fill (`actual_shares < fill.shares`) | 중단 + 알림 (`ValueError("보유량 초과 매도")`) |
| 매수 체결로 `shared_cash_actual < 0` | 중단 + 알림 (`ValueError("현금 부족")`) |
| `applied_*_ids.json` 의 타임스탬프 파싱 실패 | 중단 + 알림 (`ValueError`) |
| history 저장 실패 (`_persist_history`) | 중단 + 알림 (silent continue 금지) |
| RTDB 쓰기 실패 (`_publish_to_rtdb`) | 중단 + 알림. **ephemeral 컨텍스트 미종료 → Git push 도 건너뜀 (원자성)** |
| Git clone / push 실패 | 중단 + 알림 |
| 타 커맨드(`init`, `init-data`, `drift`, `history` 등) 실패 | `main()` 공통 훅이 `_safe_notify_failure` 호출 |
| FCM 전송 실패 (`UNREGISTERED`/`NOT_FOUND` 외) | `logger.warning` 으로 기록 (조용히 묻히지 않게). 재발송 금지. 텔레그램은 독립 발송 |
| FCM 토큰 만료 (`UNREGISTERED`/`NOT_FOUND`) | RTDB `/device_tokens/` 에서 자동 제거 (정상 동작) |
| 텔레그램 전송 실패 | `logger.error` 기록만. 재발송 금지. FCM 은 독립 발송 |
| fill / balance_adjust 중복 수신 | `applied_*_ids.json` 으로 skip (정상 동작) |
| 체결 미입력 | 매 실행 리마인더 알림에 포함 |
| `notify-failure` 커맨드 자체 실패 | 재귀 방지 — `main()` 훅에서 알림 발송 건너뜀, 예외만 로그 기록 후 exit 1 |
| GitHub Actions 실패 (retry 포함 2회 연속) | `notify-failure` job 에서 FCM + 텔레그램 재전송 |

모든 에러 알림에는 실패 커맨드 이름 + 에러 상세 메시지를 포함한다. 자동 롤백 /
자동 재시도 (Actions retry job 제외) 는 하지 않는다.

---

## 12. 스케쥴링

`daily_run.yml` cron: 평일 ET 17:50 (`'50 17 * * 1-5'`, `timezone: America/New_York`). `workflow_dispatch` 에는 수동 테스트용 `trade_date` 입력을 허용하며, 이 입력이 명시된 경우 휴장 체크와 idempotency 체크가 모두 bypass 된다.

Poetry 캐싱 + 실패 시 5 분 후 1 회 재시도 + 최종 실패 시 notify-failure job.

`keepalive.yml` 은 매월 1 일에 `quant` 퍼블릭 리포에 **빈 commit** 을 남긴다. GitHub 의 60 일 비활성 정책으로 인해 daily_run 의 cron 이 자동 일시 정지되는 것을 방지하기 위함이다. qbt-live-state (프라이빗) 는 60 일 정책 대상이 아니므로 건드리지 않는다.

---

## 13. 보안

GitHub Secrets 4 종:

- `FIREBASE_CONFIG`: Admin SDK 서비스 계정 JSON
- `STATE_REPO_PAT`: 프라이빗 리포 Git clone / push 용 PAT
- `TELEGRAM_BOT_TOKEN`: 봇 토큰
- `TELEGRAM_CHAT_ID`: 채팅 ID

로컬 개발에는 프로젝트 루트의 `.env` 파일로 같은 값을 공급하며 (python-dotenv 자동 로드), `.env` 와 `secrets/` 는 `.gitignore` 로 보호된다.

보안 계층: Firebase Auth Email/Password + RTDB Rules. App Check 도입은 운영 안정화 단계의 선택 사항.

---

## 14. Drift

drift 는 **model equity 와 actual equity 의 상대 차이** 이다.

```
drift_pct = |model_equity − actual_equity| / model_equity   (비율, 0~1. 0.03 = 3%)
```

QBT 비율 원칙(`_pct` = 0~1)에 따라 `drift_pct` 는 0~1 범위의 비율이다.
RTDB 에 쓸 때만 `× 100` 변환하여 앱 호환성을 유지한다.

**유일 정본**: `drift.compute_drift(state, closes)` 가 완전 `DriftReport` 를 생성한다.
`daily_runner.run_daily()` 는 내부적으로 이 함수를 호출하여 결과를
`DailyResult.drift_report` 에 채워 반환한다. daily_runner 에 간이 drift 계산은 없다.

**임계값** (비율 기준, `constants.DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`):

| 구간 (비율) | 상태 (`recommendation`) |
|---|---|
| 0 ~ 0.03 | "정상" |
| 0.03 ~ 0.05 | "주의" |
| 0.05 이상 | "보정 필요" |

**자산별 drift**: `DriftReport.per_asset` 에 `AssetDrift` 리스트로 포함된다.
모델이 0 주인데 실제 보유 중인 경우(`model_value=0, actual_value>0`)
`asset_drift_pct = 1.0` (100% 이탈) 을 반환하여 사용자가 차이를 인지할 수 있다.
일일 리포트 알림 본문에는 전체 `drift_pct` 스칼라 값만 포함된다.

---

## 15. 구현 현황

본 설계서의 서버사이드 범위는 구현 완료 상태이며 `live/` 도메인 코드와
`.github/workflows/` 의 GitHub Actions 워크플로우로 운영된다.

- **엔진 / state / CSV / 검증 / 회귀 / cron / keepalive**: 완료 (`live/src/live/`,
  `test_regression.py`, `.github/workflows/daily_run.yml`, `keepalive.yml`)
- **FCM + 텔레그램 / chart_data / RTDB read model**: 완료 (`notifier.py`,
  `chart_data.py`, `rtdb_gateway.py`)
- **체결 자동 매칭 / drift / 미입력 리마인더**: 완료 (`drift.py`, `daily_runner.py`)
- **Android 앱**: 별도 프로젝트(`qbt-live-app`) 에서 유지

변경 이력 및 세부 작업 계획은 `docs/plans/` 하위 계획서를 참조한다.

---

## 16. 비용

사실상 **₩0/월**. 한도 초과 시 과금 가능.

| 항목 | 무료 한도 | 예상 사용 |
|---|---|---|
| GitHub Actions | 퍼블릭 리포 무제한 | 월 ~200 분 |
| Firebase FCM | 무제한 | 일 ~5 건 |
| Firebase RTDB | 1 GB / 10 GB | ~1 MB / ~100 MB |
| Firebase Auth | 50K MAU | 1 명 |
| 텔레그램 | 무제한 | 일 ~5 건 |
| yfinance | 무료 | 일 6 건 |

---

## 17. 참고

함수 시그니처 / dataclass / 내부 구현 디테일은 아래를 참조:

- [live/CLAUDE.md](../live/CLAUDE.md) — 모듈별 역할 / 코딩 규칙 / 실행 방법
- [live/src/live/models.py](../live/src/live/models.py) — 데이터 모델
- [live/src/live/cli.py](../live/src/live/cli.py) — CLI 엔트리
- [live/src/live/daily_runner.py](../live/src/live/daily_runner.py) — 일일 실행 로직
- [docs/TEST_QBT_LIVE_MANUAL.md](TEST_QBT_LIVE_MANUAL.md) — 수동 테스트 가이드
- [docs/plans/](plans/) — Phase 별 구현 계획서
