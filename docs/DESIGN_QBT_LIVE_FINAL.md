# QBT Live 실시간 매매 알림 시스템 설계서

> 본 문서는 **앱(qbt-live-app) ↔ live 서버** 를 잇는 데이터 계약과 전체 아키텍처를 담당한다.
> live 내부 구현 / 운영 상세 (모듈 / 상수 / CLI / 예외 / 배포) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 와 `src/live/` 코드가 정본이다.

## 0. 개요

QBT 포트폴리오 전략을 **Android 앱 + 일일 실행 엔진(live)** 구조로 실매매 알림 시스템으로 이식한다. live 는 평일 장 마감 후 GitHub Actions 로 실행되어 Git 정본(`qbt-live-state`) 과 Firebase RTDB 를 갱신하고, 앱은 RTDB 를 통해 데이터를 읽고 체결을 입력한다.

### 앱 관점 확정 사항

| 항목                  | 확정 |
|-----------------------|------|
| UI                    | Android 앱 (React Native). 웹 없음 |
| 앱 인증               | Firebase Auth Email/Password |
| 푸시 알림             | FCM (텍스트) + 텔레그램 봇 (동시 발송) |
| 앱 데이터 버스        | Firebase RTDB (Spark 무료) |
| 체결 입력             | 앱 → RTDB `/fills/inbox/{uuid}` (자동 매칭 + idempotency) |
| 자산 직접 수정        | 앱 → RTDB `/balance_adjust/inbox/{uuid}` |
| 차트                  | RTDB 시계열 + TradingView Lightweight Charts |
| FCM 토큰              | RTDB `/device_tokens/{device_id}` (복수 기기 대응) |
| 정본 원장             | Git 프라이빗 리포 (앱은 접근하지 않음) |
| model / actual 분리   | 두 축을 RTDB 에서 별도로 읽고 표시 |
| PendingOrder          | 단일 슬롯, `execute_on` 없음 (익일 시가 자동 확정) |
| 스케쥴                | 평일 ET 17:50 cron, 매일 1 회 `/latest/*` 갱신 |

### 인프라 정보 (앱 설정에 필요)

| 항목                  | 값 |
|-----------------------|---|
| Firebase 프로젝트     | `qbt-live` (Spark 요금제) |
| RTDB URL              | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지        | `com.ingbeen.qbtlive` |
| 텔레그램 봇           | `@qbt_live_alert_bot` |

**식별자 규칙**: RTDB 경로의 `{asset_id}` 는 항상 **소문자** (예: `sso`, `qld`, `gld`, `tlt`). 자산 목록과 live 서버 내부 상수 (`LIVE_PORTFOLIO_ID`, `SCHEMA_VERSION`, 드리프트 임계값 등) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 1. 전체 아키텍처

### 1.1 컴포넌트 다이어그램

```
                      [GitHub Actions cron]
                       평일 ET 17:50 1회
                              |
                              v
                      +----------------+
                      |  live (서버)   |
                      |  (src/live/)   |
                      +----------------+
                        |            |
           원장 read/write            read/write
                        v            v
              [qbt-live-state]   [Firebase RTDB]  --- FCM/텔레그램 알림 --->  [Android 앱]
               (Git 프라이빗)    /latest/*                                           ^
               (앱 접근 불가)    /history/summary                                    |
                                 /fills/inbox       <------ 체결 / 보정 입력 --------+
                                 /balance_adjust/                                    |
                                 /device_tokens                                      |
                                                    <------ /latest/* read ----------+
```

- **live** 는 평일 장 마감 후 GitHub Actions 에서 1 회 실행되어 Git 원장과 RTDB 를 갱신한다.
- **qbt-live-state** (Git 프라이빗 리포) 는 live 전용 정본 원장이며 **앱은 접근하지 않는다**.
- **Firebase RTDB** 는 앱 ↔ live 양방향 버스이다. 앱은 `/latest/*` 와 `/history/summary/*` 를 읽고, `/fills/inbox/*` 와 `/balance_adjust/inbox/*` 에 쓰며, `/device_tokens/*` 로 FCM 토큰을 등록한다.
- **FCM + 텔레그램** 은 live 가 매 실행 끝에 동시 발송한다 (일일 리포트 + 실패 알림).

live 내부 실행 순서 / 예외 훅 / ephemeral clone 메커니즘 등은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

### 1.2 앱 관점 핵심 원칙

- **앱이 유일한 UI** — 웹 없음.
- **Git = 정본, RTDB = 앱 버스** — 앱은 Git 에 직접 접근하지 않는다. **앱에 GitHub 토큰 절대 없음**.
- **model / actual 분리** — actual 축은 앱 입력(`/fills/inbox/` 또는 `/balance_adjust/inbox/`) 으로만 갱신된다. live 는 actual 을 덮어쓰지 않는다.
- **inbox 패턴** — `/latest/*` 는 live 가 매 실행마다 전체 덮어쓰므로 앱이 직접 쓰면 다음 실행에서 사라진다. 앱의 모든 쓰기는 `/fills/inbox/` / `/balance_adjust/inbox/` / `/device_tokens/` 세 경로에만 가능하다.
- **체결 자동 매칭** — 앱이 입력한 fill 을 live 가 pending_order 와 방향 일치 여부로 자동 분류한다 (§4.1).
- **알림 동시 발송** — FCM + 텔레그램 은 독립 채널로 동시 발송된다. 한쪽 채널 실패는 다른 쪽을 막지 않는다.

---

## 2. 알고리즘 / 주가 데이터 / 검증

live 는 QBT 백테스트 코어 (`qbt.backtest.*`) 를 직접 재사용하여 매일 신호 / 체결 / 리밸런싱을 계산하고, yfinance OHLC 수집 / 데이터 검증 (OHLC 논리 / 전일 종가 연속성 / 거래일 gap) / MA·밴드 계산 / `run_daily` 실행 순서 등의 내부 동작은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 와 `src/live/` 코드가 정본이다.

**앱이 알아야 할 것은 결과물뿐이다** — live 가 매일 계산한 포지션 / 시그널 / 밴드 / drift 는 RTDB `/latest/*` 와 `/history/summary/{date}` 로 노출된다 (§8.2 참고). 스플릿·무상증자 감지 / 회귀 검증 / BufferZoneStrategy 직렬화 같은 live 내부 로직은 앱에 영향을 주지 않는다.

---

## 3. model / actual 원장 분리

live 는 model 축과 actual 축을 **두 개의 독립된 원장** 으로 유지한다.

- **model** — daily runner 의 이론 포지션 (신호 → 전일 pending → 당일 시가 자동 체결)
- **actual** — 사용자가 실제로 체결한 포지션. `/fills/inbox/` 또는 `/balance_adjust/inbox/` 로만 갱신되며 model 이 actual 을 덮어쓰지 않는다.

두 값의 차이가 **drift** 이며 §12 에서 정의한다. 앱은 `/latest/portfolio` 에서 `model_*` 와 `actual_*` 두 쌍을 모두 받아 화면에 나란히 표시한다.

**signal_state 2 값 (`"buy"` / `"sell"`)** 은 누적 원장 상태이고, **SignalDetection.state 3 값 (`"buy"` / `"sell"` / `"none"`)** 은 당일 감지 결과이다. 두 개념은 수명 / 저장 여부 / 노출 경로가 다르며, 각각 `/latest/portfolio` (§8.2.1) 와 `/latest/signals` (§8.2.2) 로 노출된다.

---

## 4. 체결 입력 및 자산 보정

> 입력 스키마 / 필수 필드 / 검증 규칙 / idempotency / processed 필드 규칙은 §8.2.7 (`/fills/inbox`) 과 §8.2.8 (`/balance_adjust/inbox`) 이 정본이다. 본 섹션은 분류 로직과 적용 순서만 정의한다.

### 4.1 fill 자동 매칭

`drift.classify_fill` 이 각 fill 을 다음 두 분류로 나눈다 (actual 축 반영은 분류와 무관하게 동일).

- **system_fill**: 해당 자산에 pending_order 가 있고, pending 의 intent 방향 (buy/sell) 과 fill 의 direction 이 일치
- **personal_trade**: pending 이 없거나 방향이 다름

분류 결과는 audit / drift 분석 용도로만 사용되며 체결 반영 로직에는 영향이 없다.

### 4.2 미입력 리마인더

`run-daily` 실행 시 `pending_order` 가 있는 자산 중 해당 자산에 대한 fill 이 아직 들어오지 않은 경우 `DailyResult.pending_fill_reminders` 에 포함되어 일일 리포트 본문(§6.2)에 건수로 노출된다. 일부 자산만 체결되어도 나머지 미체결 pending 은 다음 실행에서 다시 리마인더에 올라온다.

### 4.3 balance_adjust 의미와 적용 순서

`ActualFill` 은 "buy/sell 이벤트 누적" 이고 `BalanceAdjust` 는 "현재 잔고를 이 값으로 덮어쓰기" 이다. 이 의미 차이 때문에 `balance_adjust` 는 차트 마커 대상이 아니다.

적용 순서는 `run_daily` **내부에서** 고정되어 있다 — **fills 먼저, balance_adjust 나중** (사용자 직접 보정이 신호 기반 체결을 덮어쓰는 구조). 자산 shares / 현금의 실제 교체 규칙과 idempotency 는 §8.2.8 을 정본으로 한다.

---

## 5. 차트: TradingView Lightweight Charts

자산별 CSV 를 읽어 차트 시계열을 생성하고 RTDB `/latest/chart_data/{asset_id}/` 하위에 **3 분할 구조** 로 저장한다. 자산 ID 는 live 포트폴리오의 각 슬롯 `asset_id` 를 그대로 사용한다 (소문자).

**RTDB 구조 (3 경로)**:

```
/latest/chart_data/{asset_id}/meta                ← 차트 메타 (first/last 날짜, archive_years 등)
/latest/chart_data/{asset_id}/recent              ← 최근 N 개월 slice (매일 덮어쓰기)
/latest/chart_data/{asset_id}/archive/{YYYY}      ← 연도별 slice (연 1 회 또는 이벤트 시 재생성)
```

**시계열 필드** (recent / archive 공통): `dates`, `close`, `ma_value`, `upper_band`, `lower_band`
**마커 필드** (recent / archive 공통): `buy_signals`, `sell_signals`, `user_buys`, `user_sells` — 모두 **ISO 8601 날짜 문자열 배열** (인덱스 아님). 분할된 슬라이스 사이에서 위치 독립적.

| 마커 종류                      | 출처                                    | 의미                                 |
| ------------------------------ | --------------------------------------- | ------------------------------------ |
| `buy_signals` / `sell_signals` | Git 정본 `history/signals.jsonl`        | 과거 신호 발생일 (ISO 날짜)          |
| `user_buys` / `user_sells`     | Git 정본 `history/user_trades.jsonl`    | 사용자 체결 발생일 (ISO 날짜)        |

정확한 페이로드 스키마와 필드 타입은 §8.2.5 를 참고한다.

**recent 정책**: `recent_months = 6` (상수 `CHART_RECENT_MONTHS`). daily runner 는 매 실행마다 `recent` 를 덮어쓴다.

**archive 정책**: 연도 단위 고정 slice. daily runner 는 "현재 연도" archive 만 매 실행 덮어쓰고, 이전 연도 archive 는 건드리지 않는다. 최초 배포 시와 스플릿/무상증자 감지 시에는 운영자가 backfill CLI 로 전체 archive 를 재생성한다.

**recent ↔ archive 경계 중복 허용**: recent 와 archive/{현재_연도} 는 같은 날짜를 양쪽에 포함할 수 있다. 앱은 두 소스를 읽은 후 `Map<date, point>` 로 dedupe 하여 차트에 넣는다. 이 정책은 서버 쪽 구현 단순성과 정합성 안정을 우선한 선택.

**앱 로딩 플로우 (권장)**:

1. 앱 진입: `meta` 로드 → `recent` 로드 → Lightweight Charts `setData(recent)`.
2. 사용자가 좌측 끝으로 줌아웃: `meta.archive_years` 참고하여 필요한 연도 `archive/{YYYY}` 병렬 로드, Map 으로 병합 후 `setData(merged)`.
3. 전체 보기: `archive_years` 전체를 순회 로드 (로컬 캐시 재사용).

`ma_value` 는 자산 슬롯의 `ma_window` 에 독립적이며, 앞 `ma_window - 1` 개 인덱스는 워밍업 구간으로 `null` 이다. `upper_band` / `lower_band` 는 `ma_value × (1 ± buffer_zone_pct)` 로 계산되며 MA 가 null 이면 밴드도 null 이다. Firebase RTDB 는 빈 배열을 저장하지 않으므로 마커 리스트가 비어 있으면 해당 키가 아예 생성되지 않는다 (앱은 키 부재를 "빈 배열" 로 해석).

`balance_adjust` 는 이벤트가 아니라 "최종 잔고 교체" 이므로 차트 마커 대상이 **아니다** (§4.3 참고).

앱은 WebView + TradingView Lightweight Charts 로 시계열을 렌더링한다.

---

## 6. 알림: FCM + 텔레그램

live 는 매 실행 끝에 FCM + 텔레그램을 동시 발송한다. 두 채널은 독립이며 한쪽 실패가 다른 쪽을 막지 않는다. 본문 텍스트는 두 채널이 동일하다.

| 종류           | 내용                                                                          | 빈도                                      |
|----------------|-------------------------------------------------------------------------------|-------------------------------------------|
| 일일 리포트    | model/actual equity, drift, 시그널, MA 근접도, 리밸런싱 여부, 리마인더 건수   | 매 run-daily 정상 실행                    |
| 실패 알림      | 실패한 커맨드 이름 + 예외 메시지                                              | live 실행 중 예외 발생 시                 |

### 6.1 FCM 메시지 구조 (앱 파싱 계약)

- `notification.title` = `"QBT Live"` (고정)
- `notification.body` = 아래 §6.2 / §6.3 의 본문 텍스트 (일일/실패 동일 구조)
- **data payload 없음** — 앱은 `notification.body` 텍스트를 그대로 표시한다.

**텔레그램**: Bot API `sendMessage` 로 `chat_id` + `text` 전송. `text` 는 FCM `body` 와 동일 문자열.

### 6.2 일일 리포트 본문 (예시)

```
[QBT Live] 2026-04-10
model equity: 12,345,678
actual equity: 12,300,000
drift: 0.37%
시그널: SSO buy, QLD sell
MA 근접도: SSO +2.45%, QLD -1.05%, GLD +0.80%, TLT -1.20%
리밸런싱: 발생
미입력 체결 리마인더: 1 건
```

행 구성 규칙:

- 1 행: `[QBT Live] {execution_date}` (prefix 고정)
- `model equity` / `actual equity`: 천 단위 콤마 정수
- `drift`: `{drift_pct * 100:.2f}%` (§11 참고)
- `시그널`: 자산별 `state in ("buy","sell")` 만 `{ASSET_UPPER} {state}` 로 나열. 없으면 라인 생략
- `MA 근접도`: `{ASSET_UPPER} ±X.XX%` (자산별 `(close - ma_value) / ma_value`)
- `리밸런싱: 발생`: 리밸런싱 발생 시에만 출력
- `미입력 체결 리마인더: N 건`: pending fill 미입력 자산이 있을 때만. 상세는 `/latest/pending_orders/{asset_id}` 참고

### 6.3 실패 알림 본문 (예시)

```
[QBT Live 실패]
run-daily 실패: ValueError('알 수 없는 asset_id=...')
```

- 1 행: `[QBT Live 실패]` (prefix 고정)
- 2 행: `{command_name} 실패: {exception_message}`

### 6.4 FCM 토큰 관리

live 는 `/device_tokens/` 전체를 읽어 발송하며, 만료 토큰 (`UNREGISTERED` / `NOT_FOUND`) 은 발송 직후 해당 경로에서 자동 삭제한다. 앱은 앱 실행 시 자신의 토큰이 여전히 등록되어 있는지 확인하고 없으면 재등록해야 한다.

---

## 7. Android 앱 (React Native)

별도 프로젝트 (`qbt-live-app`) 에서 구현되며 본 설계서의 범위 밖이다. 앱 요구사항 요약:

- Firebase Auth (Email/Password) 로 1 회 로그인
- FCM 토큰을 RTDB `/device_tokens/` 에 등록
- 홈/차트/거래/설정 4 탭
- `/latest/*` 를 읽어 포트폴리오 / 시그널 / 차트 표시
- `/fills/inbox/` 와 `/balance_adjust/inbox/` 에 쓰기

---

## 8. 상태 저장

### 8.1 Git 정본 (qbt-live-state)

live 서버는 `qbt-live-state` 프라이빗 리포를 원장(JSON + CSV + history) 으로 사용한다. **앱은 Git 정본에 접근하지 않으며**, 앱이 보는 모든 데이터는 RTDB 경로(§8.2) 로만 전달된다. Git 정본의 파일 트리 / 내부 스키마 / idempotency 원장 / history JSONL 포맷은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 및 `src/live/` 코드가 정본이다.

### 8.2 RTDB 경로 구조

```
/latest/portfolio                                ← 전체 자산 요약 + drift 스칼라 + assets/{asset_id}
/latest/signals/{asset_id}                       ← 시그널 상태 / 종가 / MA / 밴드
/latest/pending_orders/{asset_id}                ← 익일 체결 예정 주문 (pending 있는 자산만)
/latest/chart_data/{asset_id}/meta               ← 차트 메타 (first/last 날짜, archive_years 등)
/latest/chart_data/{asset_id}/recent             ← 차트 최근 N 개월 slice (매일 덮어쓰기)
/latest/chart_data/{asset_id}/archive/{YYYY}     ← 차트 연도별 slice (현재 연도만 daily 갱신)
/history/summary/{YYYY-MM-DD}                    ← 일별 요약 (rolling window, 최근 90 일만 유지)
/fills/inbox/{uuid}                              ← 앱이 쓰는 체결 queue
/balance_adjust/inbox/{uuid}                     ← 앱이 쓰는 잔고 보정 queue
/device_tokens/{device_id}                       ← FCM 토큰
```

RTDB 는 "앱 ↔ daily runner" 버스이며, 정본 저장소가 아니다. `/latest/*` 는 매 실행마다 전체 갱신되므로 앱이 직접 쓰면 다음 실행에서 덮어써진다 (inbox 패턴을 쓰는 이유).

**식별자 규칙**: asset_id 소문자 / ticker 대문자 규칙은 §0 "식별자 규칙" 참고.

**drift_pct 스케일**: RTDB 의 `drift_pct` 필드(`/latest/portfolio`, `/history/summary/{date}`) 는 모두 `× 100` 스케일이다. 정의 / 임계값 / 라벨은 §12 참고. drift 스칼라 요약은 `/latest/portfolio` 에만 포함되며 별도 경로로 중복 저장하지 않는다 (§8.2.4 삭제됨).

#### 8.2.1 `/latest/portfolio` — 전체 포트폴리오 요약

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.LiveState`. 매 `run-daily` 실행마다 전체 덮어쓰기.

```json
{
  "execution_date": "2026-04-10",
  "model_equity": 12345678,
  "actual_equity": 12300000,
  "drift_pct": 0.37,
  "shared_cash_model": 500000.0,
  "shared_cash_actual": 498500.0,
  "assets": {
    "sso": {
      "model_shares": 120,
      "actual_shares": 120,
      "signal_state": "buy"
    },
    "qld": { "model_shares": 80, "actual_shares": 80, "signal_state": "buy" },
    "gld": { "model_shares": 15, "actual_shares": 15, "signal_state": "sell" },
    "tlt": { "model_shares": 40, "actual_shares": 40, "signal_state": "sell" }
  }
}
```

| 필드                             | 타입                   | null | 설명                                                            |
| -------------------------------- | ---------------------- | ---- | --------------------------------------------------------------- |
| `execution_date`                 | str                    | 불가 | ISO 8601 날짜 (예: `"2026-04-10"`)                              |
| `model_equity`                   | number                 | 불가 | model 축 총 자산가치 (자본금 반올림, `ROUND_CAPITAL = 0` 자리)  |
| `actual_equity`                  | number                 | 불가 | actual 축 총 자산가치 (`ROUND_CAPITAL = 0` 자리)                |
| `drift_pct`                      | number                 | 불가 | drift 값 (× 100 스케일). §12 참고                                |
| `shared_cash_model`              | number                 | 불가 | model 축 공유 현금                                              |
| `shared_cash_actual`             | number                 | 불가 | actual 축 공유 현금                                             |
| `assets.{asset_id}.model_shares` | int                    | 불가 | model 축 보유 주식 수                                           |
| `assets.{asset_id}.actual_shares`| int                    | 불가 | actual 축 보유 주식 수                                          |
| `assets.{asset_id}.signal_state` | `"buy"`\|`"sell"`      | 불가 | 누적 원장 신호 상태. 초기값 `"sell"` (포지션 없음). §3 참고    |

#### 8.2.2 `/latest/signals/{asset_id}` — 당일 시그널 / MA / 밴드

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.SignalDetection`. 매 실행 자산 전체 덮어쓰기.

```json
{
  "sso": {
    "state": "buy",
    "close": 123.450000,
    "ma_value": 120.500000,
    "ma_distance_pct": 0.0245,
    "upper_band": 126.525000,
    "lower_band": 114.475000
  },
  "qld": { "state": "none", "close": 85.200000, "ma_value": 86.100000, "ma_distance_pct": -0.0105, "upper_band": null, "lower_band": null }
}
```

| 필드               | 타입                         | null | 설명                                                                                               |
| ------------------ | ---------------------------- | ---- | -------------------------------------------------------------------------------------------------- |
| `state`            | `"buy"`\|`"sell"`\|`"none"`  | 불가 | **당일 감지** 된 신호. `"none"` = 오늘 새 신호 없음. 누적 원장(`signal_state`) 과는 별개. §3 참고 |
| `close`            | number                       | 불가 | 당일 종가 (`ROUND_PRICE = 6` 자리)                                                                 |
| `ma_value`         | number                       | 가능 | 자산 슬롯의 `ma_window` 기준 MA 값 (워밍업 구간은 null)                                            |
| `ma_distance_pct`  | number                       | 불가 | `(close - ma_value) / ma_value` (비율 0~1, 음수 가능, `ROUND_RATIO = 4` 자리)                       |
| `upper_band`       | number                       | 가능 | BufferZone 상단 밴드 (버퍼존 미사용 자산은 null). 전략이 다음 거래일 판단에 사용할 값과 동일       |
| `lower_band`       | number                       | 가능 | BufferZone 하단 밴드 (버퍼존 미사용 자산은 null)                                                    |

#### 8.2.3 `/latest/pending_orders/{asset_id}` — 익일 체결 예정 주문

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.PendingOrderDict`. 매 실행 전체 덮어쓰기 (pending_order 가 있는 자산만 기록).

```json
{
  "sso": {
    "asset_id": "sso",
    "intent_type": "ENTER_TO_TARGET",
    "signal_date": "2026-04-10",
    "current_amount": 0.0,
    "target_amount": 4320000.0,
    "delta_amount": 4320000.0,
    "target_weight": 0.35,
    "hold_days_used": 0,
    "reason": "buffer upper band 돌파 — 매수 진입"
  }
}
```

| 필드             | 타입                                                                           | 설명                                                   |
| ---------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `asset_id`       | str                                                                            | 소문자 자산 ID (중복 저장 — 최상위 key 와 동일)        |
| `intent_type`    | `"EXIT_ALL"`\|`"ENTER_TO_TARGET"`\|`"REDUCE_TO_TARGET"`\|`"INCREASE_TO_TARGET"` | QBT `OrderIntent.intent_type` 과 동일한 Literal         |
| `signal_date`    | str                                                                            | 신호 발생 날짜 (ISO 8601). 체결 예정일은 **다음 거래일 시가** 자동 확정 — `execute_on` 필드 없음 |
| `current_amount` | number                                                                         | 현재 자산 평가액                                       |
| `target_amount`  | number                                                                         | 목표 자산 평가액                                       |
| `delta_amount`   | number                                                                         | 증감량 (음수=매도, 양수=매수)                          |
| `target_weight`  | number                                                                         | 목표 비중 (0~1 비율)                                   |
| `hold_days_used` | int                                                                            | BufferZone hold_days 누적 (매수 확정 대기 일수)        |
| `reason`         | str                                                                            | 신호 이유 설명 (앱 리마인더 본문)                      |

#### 8.2.4 `/latest/drift` — (삭제됨)

이 경로는 제거되었다. 과거에는 `drift_pct` / `model_equity` / `actual_equity` 세 필드를 별도 경로로 노출했으나 모든 필드가 `/latest/portfolio` (§8.2.1) 에 이미 존재하는 완전한 중복이었고, per_asset 정보도 포함하지 않아 독립 경로로 유지할 정당성이 없었다. 앱은 drift 스칼라 요약을 `/latest/portfolio` 에서 직접 읽는다. 자산별 drift 가 필요하면 `/latest/portfolio` + `/latest/signals` 로 앱에서 계산하거나, 운영자가 Git 정본 `history/daily/{date}.json` 을 조회한다.

섹션 번호는 뒤 섹션들이 흩어지지 않도록 그대로 유지한다.

#### 8.2.5 `/latest/chart_data/{asset_id}/` — 차트 데이터 (meta + recent + archive/{YYYY})

**SoT**:

- meta: `live.chart_data.build_chart_meta`, `live.models.ChartMeta`, `live.rtdb_gateway.write_chart_meta`
- recent: `live.chart_data.build_chart_recent`, `live.models.ChartSeries`, `live.rtdb_gateway.write_chart_recent`
- archive: `live.chart_data.build_chart_archive_year`, `live.models.ChartSeries`, `live.rtdb_gateway.write_chart_archive_year`

**갱신 주체**: daily runner (`run-daily`) 가 매 실행마다 `meta` / `recent` / `archive/{현재_연도}` 를 덮어쓴다. 이전 연도 archive 는 daily 갱신 대상이 아니며, 최초 배포 / 스플릿 / 무상증자 시 운영자가 backfill CLI 로 재생성한다.

##### 8.2.5.1 `/latest/chart_data/{asset_id}/meta`

```json
{
  "first_date": "2013-01-02",
  "last_date": "2026-04-14",
  "ma_window": 200,
  "recent_months": 6,
  "archive_years": [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
}
```

| 필드           | 타입        | 설명                                                                                 |
| -------------- | ----------- | ------------------------------------------------------------------------------------ |
| `first_date`   | str         | 자산 CSV 의 첫 거래일 (ISO 8601)                                                     |
| `last_date`    | str         | 자산 CSV 의 마지막 거래일 (ISO 8601)                                                 |
| `ma_window`    | int         | 자산 슬롯의 MA 윈도우 (워밍업 길이 계산용)                                            |
| `recent_months`| int         | `recent` slice 가 포함하는 개월 수. 상수 `CHART_RECENT_MONTHS = 6`                    |
| `archive_years`| list[int]   | CSV 가 포함하는 연도 목록 (오름차순). 앱이 줌아웃 시 로드할 archive 경로를 결정       |

앱은 `meta` 를 가장 먼저 한 번 읽고, 필요한 시점에 `recent` / `archive/{YYYY}` 로드 전략을 결정한다.

##### 8.2.5.2 `/latest/chart_data/{asset_id}/recent`

최근 `recent_months` 개월 슬라이스. 매 `run-daily` 실행마다 덮어쓰기.

```json
{
  "dates": ["2025-10-15", "2025-10-16", "…", "2026-04-14"],
  "close": [123.450000, 124.000000, 124.500000],
  "ma_value": [120.500000, 120.650000, 120.800000],
  "upper_band": [124.115000, 124.270000, 124.424000],
  "lower_band": [114.475000, 114.618000, 114.760000],
  "buy_signals": ["2025-11-03"],
  "sell_signals": ["2026-01-21"],
  "user_buys": ["2025-11-04"],
  "user_sells": ["2026-01-22"]
}
```

| 필드           | 타입                 | 설명                                                                                    |
| -------------- | -------------------- | --------------------------------------------------------------------------------------- |
| `dates`        | list[str]            | recent 구간 거래일 (ISO 8601)                                                           |
| `close`        | list[number]         | 종가 (`ROUND_PRICE = 6` 자리)                                                           |
| `ma_value`     | list[number \| null] | MA. recent 는 보통 워밍업을 지난 구간이므로 전부 값이 채워진다                          |
| `upper_band`   | list[number \| null] | `ma_value × (1 + buy_buffer_zone_pct)`                                                  |
| `lower_band`   | list[number \| null] | `ma_value × (1 - sell_buffer_zone_pct)`                                                 |
| `buy_signals`  | list[str]            | 해당 구간 내 매수 신호 발생일 (ISO 8601). Git `history/signals.jsonl` 에서 파생           |
| `sell_signals` | list[str]            | 해당 구간 내 매도 신호 발생일 (ISO 8601)                                                |
| `user_buys`    | list[str]            | 해당 구간 내 사용자 매수 체결일 (ISO 8601). Git `history/user_trades.jsonl` 에서 파생    |
| `user_sells`   | list[str]            | 해당 구간 내 사용자 매도 체결일 (ISO 8601)                                              |

##### 8.2.5.3 `/latest/chart_data/{asset_id}/archive/{YYYY}`

특정 연도 전체 슬라이스 (1월 1일 ~ 12월 31일 범위 내 거래일). daily runner 는 **현재 연도 만** 갱신하고, 이전 연도 archive 는 backfill CLI 또는 수동 재생성 시에만 쓴다.

payload 구조는 `recent` 와 동일 (`dates`, `close`, `ma_value`, `upper_band`, `lower_band`, 마커 4 종). 마커도 해당 연도 범위 내 날짜만 포함한다.

```json
{
  "dates": ["2025-01-02", "…", "2025-12-31"],
  "close": [...],
  "ma_value": [...],
  "upper_band": [...],
  "lower_band": [...],
  "buy_signals": ["2025-03-15"],
  "sell_signals": [],
  "user_buys": ["2025-03-16"],
  "user_sells": []
}
```

##### 8.2.5.4 경계 중복 허용 정책

`recent` 와 `archive/{현재_연도}` 는 같은 날짜 범위를 일부 공유한다 (예: 2026-01-01 ~ 2026-04-14 구간은 양쪽에 모두 존재). 서버는 두 slice 를 독립 규칙으로 생성하고, **앱이 `Map<date, point>` 로 dedupe** 한다. 이 정책의 이유는 서버 구현을 단순하게 유지하고 경계 버그 리스크를 차단하기 위함이다.

##### 8.2.5.5 중요 사항 (빈 배열 / null 처리)

- Firebase RTDB 는 **빈 배열 `[]` 을 저장하지 않는다**. 마커 리스트가 비어 있으면 해당 키(`buy_signals` 등) 가 아예 생성되지 않으므로, 앱은 키 부재를 "빈 배열" 로 해석해야 한다.
- `ma_value` / `upper_band` / `lower_band` 의 워밍업 구간은 `null` 값으로 채워진다 (배열 인덱스는 유지, 값만 null).

#### 8.2.6 `/history/summary/{YYYY-MM-DD}` — 일별 요약 (RTDB, rolling window)

**SoT**:

- 쓰기: `live.rtdb_gateway.write_read_model` — 매 실행 해당 날짜 키 덮어쓰기.
- 정리: `live.rtdb_gateway.prune_history_summary` — 매 실행 직후 호출되어 retention 을 초과한 오래된 날짜 키를 삭제한다.

```json
{
  "execution_date": "2026-04-10",
  "model_equity": 12345678,
  "actual_equity": 12300000,
  "drift_pct": 0.37
}
```

| 필드            | 타입   | 설명                                                                |
| --------------- | ------ | ------------------------------------------------------------------- |
| `execution_date` | str    | ISO 8601 날짜 (최상위 key 와 동일)                                  |
| `model_equity`  | number | model 축 총 자산가치                                                |
| `actual_equity` | number | actual 축 총 자산가치                                               |
| `drift_pct`     | number | drift 값 (× 100 스케일). §12 참고                                    |

**Retention (rolling window)**: RTDB 의 `/history/summary/` 는 **앱 홈 탭 표시용 rolling cache** 이며, daily runner 가 매 실행 직후 `prune_history_summary` 를 호출하여 `RTDB_HISTORY_SUMMARY_RETENTION_DAYS = 90` 일을 초과한 과거 날짜 키를 삭제한다. 정확한 경계 규칙: `cutoff = execution_date - retention_days`, `entry_date < cutoff` 이면 삭제 (cutoff 일자 자체는 보존). 앱은 최근 30~90 일을 읽어 표시한다.

**정본 위치**: 자산별 상세·전체 히스토리는 Git 정본(`history/summary.jsonl`, `history/daily/{date}.json`) 이 유일 정본이며 **영구 누적** 된다. RTDB 쪽은 캐시이므로 언제든지 재빌드 가능한 소비용 데이터로만 취급한다.

#### 8.2.7 `/fills/inbox/{uuid}` — 체결 입력 (앱 → 서버)

**SoT**: `live.rtdb_gateway._dict_to_actual_fill`, `live.models.ActualFill`, `live.drift.apply_fills_idempotent`. 앱이 UUID key 를 생성하여 append, daily runner 가 `processed=false` 만 필터링해 읽는다.

```json
{
  "asset_id": "sso",
  "direction": "buy",
  "actual_price": 123.45,
  "actual_shares": 100,
  "trade_date": "2026-04-10",
  "input_time_kst": "2026-04-10T15:30:22+09:00",
  "memo": "시가 체결",
  "reason": ""
}
```

**필수 필드** (누락 시 `ValueError("fill 필수 필드 누락: [...]")`):

| 필드             | 타입              | 설명                                                                                              |
| ---------------- | ----------------- | ------------------------------------------------------------------------------------------------- |
| `asset_id`       | str               | 소문자 자산 ID. live 포트폴리오에 존재해야 함 (미보유 → `ValueError`)                             |
| `direction`      | `"buy"`\|`"sell"` | **대소문자 민감**. 다른 값은 `ValueError("fill direction 값이 유효하지 않음")`                    |
| `actual_price`   | number            | 체결 가격                                                                                         |
| `actual_shares`  | int               | 체결 수량                                                                                         |
| `trade_date`     | str               | ISO 8601 날짜 (예: `"2026-04-10"`)                                                                |
| `input_time_kst` | str               | ISO 8601 KST 타임스탬프 (예: `"2026-04-10T15:30:22+09:00"`)                                       |

**선택 필드**:

| 필드     | 타입        | 설명                                      |
| -------- | ----------- | ----------------------------------------- |
| `memo`   | str \| null | 사용자 자유 메모 (기본 null)              |
| `reason` | str         | 체결 사유 (기본 `""`)                     |

**서버측 검증 (거부 조건)** — 위반 시 `run-daily` 가 즉시 중단되고 FCM + 텔레그램 실패 알림 발송:

1. unknown `asset_id` → `ValueError("알 수 없는 asset_id=...")`
2. 매도 시 `actual_shares > actual_shares(보유)` → `ValueError("보유량 초과 매도")`
3. 매수 체결로 `shared_cash_actual < 0` → `ValueError("현금 부족")`

**idempotency**: `rtdb_key` (UUID) 기반. `applied_fill_ids.json` 에 이미 기록된 key 는 skip. 90 일 초과 key 는 자동 정리. `processed` 필드 규칙은 §8.3 참고.

#### 8.2.8 `/balance_adjust/inbox/{uuid}` — 잔고 직접 보정 (앱 → 서버)

**SoT**: `live.rtdb_gateway._dict_to_balance_adjust`, `live.models.BalanceAdjust`, `live.balance_adjust.apply_balance_adjusts_idempotent`. 앱이 UUID key 를 생성하여 append, daily runner 가 `processed=false` 만 필터링해 읽는다.

**예시 1** — 자산 + 현금 동시 보정:

```json
{
  "asset_id": "sso",
  "new_shares": 150,
  "new_cash": 500000.0,
  "reason": "오프라인 매수 반영",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**예시 2** — 현금만 보정 (배당 / 세금):

```json
{
  "new_cash": 510000.0,
  "reason": "QLD 배당 입금",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**예시 3** — 자산만 리셋 (보유 청산):

```json
{
  "asset_id": "tlt",
  "new_shares": 0,
  "reason": "수동 청산",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**필드**:

| 필드             | 타입            | 필수 여부    | 설명                                                                                 |
| ---------------- | --------------- | ------------ | ------------------------------------------------------------------------------------ |
| `asset_id`       | str \| null     | 조건부       | 자산 shares 를 보정할 때 필수. 현금만 보정하면 null / 생략 가능. unknown → `ValueError` |
| `new_shares`     | int \| null     | 조건부       | 자산 shares 교체값. `asset_id` 와 짝으로 지정. `0` 이면 평균가 / entry_date 리셋      |
| `new_cash`       | number \| null  | 조건부       | `shared_cash_actual` 교체값                                                           |
| `reason`         | str             | 권장         | 보정 사유 (audit 로그용)                                                              |
| `input_time_kst` | str             | 권장         | ISO 8601 KST 타임스탬프                                                               |

**핵심 제약** (앱이 반드시 지켜야 할 조건):

1. **`new_shares` 와 `new_cash` 가 둘 다 null 이면 `ValueError("balance_adjust 에 유효한 new_shares / new_cash 값이 없음")`** — 앱은 빈 adjust 를 절대 전송하지 말 것.
2. `asset_id + new_shares` 지정 시 `asset_id` 가 live 포트폴리오에 존재해야 한다 (unknown → `ValueError`).
3. `new_shares > 0` 시 기존 `actual_avg_entry_price` / `actual_entry_date` 는 **유지** 된다. 앱 UI 에서 "평균가도 변경하려면 어떻게?" 라는 질문이 나오면 답: 현재 경로에서는 불가능. 체결을 여러 건의 fill 로 쪼개 입력해야 한다.
4. `balance_adjust` 는 차트 마커 대상이 **아니다** (교체 이벤트이므로 과거 시점에 표시되지 않는다).

**idempotency**: `rtdb_key` (UUID) 기반. `applied_balance_adjust_ids.json` 에 기록. 90 일 자동 정리. `processed` 필드 규칙은 §8.3 참고.

#### 8.2.9 `/device_tokens/{device_id}` — FCM 토큰 등록 (앱 → 서버)

**SoT**: `live.rtdb_gateway.read_device_tokens`, `live.rtdb_gateway.remove_invalid_tokens`. 앱이 device_id 를 key 로 등록, daily runner 는 알림 발송 시 읽고 만료 토큰은 자동 삭제.

**형식 1 — 단순 문자열 (권장, 신규 구현에 적합)**:

```json
{
  "device_1": "eFwWqXYqT...",
  "device_2": "fGxXqZbRu..."
}
```

**형식 2 — 객체 (metadata 포함 시)**:

```json
{
  "device_1": {
    "token": "eFwWqXYqT...",
    "timestamp": "2026-04-10T15:30:22+09:00"
  }
}
```

| 필드        | 타입           | 설명                                                                                             |
| ----------- | -------------- | ------------------------------------------------------------------------------------------------ |
| `{device_id}` 값 | str \| object  | str 이면 토큰 그 자체. object 면 `token` 필드에서 추출 (다른 필드는 무시되지만 저장 가능)         |
| `token`     | str            | FCM registration token (객체 형식에서만 사용)                                                    |

**자동 정리**: daily runner 가 FCM 발송 시 `UnregisteredError` / `NOT_FOUND` 코드를 받으면 해당 토큰을 `remove_invalid_tokens` 로 `/device_tokens/` 에서 삭제한다. 앱은 앱 실행 시 자신의 토큰이 여전히 등록되어 있는지 확인하고 없으면 재등록하는 로직을 구현해야 한다.

**device_id 선택 원칙**: 앱이 기기별로 고유한 키를 선택한다 (예: 설치 UUID). 동일 기기에서 재설치하면 새 UUID 를 쓰는 것이 안전하다 (이전 토큰이 invalid 로 남을 수 있으나 서버가 자동 정리).

### 8.3 역할 분리

| 경로 | 쓰기 주체 | 읽기 주체 |
|---|---|---|
| qbt-live-state (Git) | daily runner (ephemeral) | daily runner |
| `/latest/*`, `/history/*` | daily runner (Admin SDK) | 앱 |
| `/fills/*`, `/balance_adjust/*` | 앱 (레코드 본문) / daily runner (`processed` 필드) | daily runner (Admin SDK) |
| `/device_tokens/*` | 앱 (등록) / daily runner (만료 토큰 삭제) | daily runner (Admin SDK) |

**`processed` 필드 규칙**: `/fills/inbox/{uuid}` 와 `/balance_adjust/inbox/{uuid}` 의 `processed` 필드는 **daily runner 만 쓰고 읽는다**. 앱은 이 필드를 읽지도 쓰지도 않으며, 체결 반영 상태는 `/latest/portfolio` 의 `actual_shares` 변화나 `/latest/pending_orders` 의 소멸로 확인한다.

---

## 9. 실패 / 예외 대응 (앱 관점)

**원칙: live 는 어떤 단계든 실패하면 즉시 중단 + FCM + 텔레그램 실패 알림 발송 + exit 1.** 자동 복구 / 자동 재시도 (Actions retry job 제외) 는 없다.

앱 측 영향은 다음 두 가지뿐이다.

1. **실패 알림 수신**: 앱은 §6.3 형식의 본문을 FCM / 텔레그램으로 받는다. 추가 조치 없음.
2. **RTDB 데이터 미갱신**: live 가 중단되면 `/latest/*` 와 `/history/summary/{date}` 가 그날 업데이트되지 않는다. 앱은 `execution_date` 필드로 최신 여부를 판단한다.

live 내부 예외 시나리오 전체 매트릭스(yfinance / 데이터 검증 / Git push / RTDB / fill 검증 / idempotency 등) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 10. 스케쥴링

live 는 평일 ET 17:50 (cron, `timezone: America/New_York`) 에 GitHub Actions 로 자동 실행된다. 앱이 알아야 할 유일한 의미는 "장 마감 후 매일 한 번 `/latest/*` 데이터가 갱신된다" 는 것이다. cron / keepalive / 재시도 정책 등 상세는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 11. 보안

앱은 Firebase Auth (Email/Password) 로 로그인하며, 인증된 사용자만 RTDB 경로에 접근한다. RTDB Rules 로 `OWNER_UID` 만 읽기/쓰기를 허용한다 (값은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 인프라 정보 표 참고).

앱에는 **GitHub 토큰이 절대 들어가지 않는다** (Git 정본 접근은 live 서버 전용). 서버 측 GitHub Secrets / `.env` / PAT / App Check 등 운영 상세는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 12. Drift

drift 는 **model equity 와 actual equity 의 상대 차이** 이다.

```
drift_pct = |model_equity − actual_equity| / model_equity   (내부 비율, 0~1. 0.03 = 3%)
```

QBT 비율 원칙(`_pct` = 0~1)에 따라 내부 계산과 Git 정본(`live_state.json`, `history/*`) 의 `drift_pct` 는 **0~1 범위의 비율** 이다. RTDB 에 쓸 때만 `× 100` 변환하여 앱 호환성을 유지한다 — `/latest/portfolio`, `/history/summary/{date}` 의 `drift_pct` 는 모두 **× 100 스케일** (`ROUND_PERCENT = 2` 자리, 예: `3.50`). 앱 개발자는 이 값을 그대로 `X.XX%` 로 표시하면 된다.

**유일 정본**: `drift.compute_drift(state, closes)` 가 완전 `DriftReport` 를 생성한다.
`daily_runner.run_daily()` 는 내부적으로 이 함수를 호출하여 결과를
`DailyResult.drift_report` 에 채워 반환한다. daily_runner 에 간이 drift 계산은 없다.

**임계값과 recommendation 라벨** (비율 기준, `constants.DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`):

| 내부 비율 구간     | `recommendation` (한글 라벨) | 앱 표시 예 (× 100 스케일) |
| ------------------ | ---------------------------- | ------------------------- |
| 0 ~ 0.03 (미만)    | `"정상"`                     | `0.00%` ~ `2.99%`         |
| 0.03 ~ 0.05 (미만) | `"주의"`                     | `3.00%` ~ `4.99%`         |
| 0.05 이상          | `"보정 필요"`                | `5.00%` 이상              |

`recommendation` 문자열은 한글 리터럴이며 RTDB 에 저장되지 않는다 (Git 정본 `history/daily/{date}.json` 및 일일 리포트 알림에만 노출). 앱이 상태 라벨을 자체 렌더링할 경우 `drift_pct / 100` 을 임계값과 비교해 동일한 규칙을 적용해야 한다.

**자산별 drift**: `DriftReport.per_asset` 에 `AssetDrift` 리스트로 포함된다.
모델이 0 주인데 실제 보유 중인 경우(`model_value=0, actual_value>0`)
`asset_drift_pct = 1.0` (100% 이탈) 을 반환하여 사용자가 차이를 인지할 수 있다.
일일 리포트 알림 본문에는 전체 `drift_pct` 스칼라 값만 포함되며, **RTDB `/latest/portfolio` 도 per_asset drift 를 포함하지 않는다**. 자산별 상세가 필요하면 앱이 `/latest/portfolio` + `/latest/signals` 로 자체 계산하거나, 운영자가 Git 정본 `history/daily/{date}.json` 을 조회한다.

---

## 13. 참고

live 서버 내부 구현 / 운영 상세 (모듈 / CLI / 상수 / 실패 처리 / 배포 / 비용) 는 본 설계서의 범위 밖이다. 정본 위치:

- [src/live/CLAUDE.md](../src/live/CLAUDE.md) — live 도메인 규칙·모듈 역할·인프라 정보
- [src/live/](../src/live/) — 코드 SoT
- [docs/TEST_QBT_LIVE_MANUAL.md](TEST_QBT_LIVE_MANUAL.md) — 수동 테스트 가이드
