# QBT Live 실시간 매매 알림 시스템 설계서

> **[중요] §0~§13 은 2026-08-30 부로 폐기 예정 설계다.**
> 현재 `daily_run` 워크플로는 수동 중지 상태이며, 알림 시스템을 상태 없는 구조로 재설계하기로 결정했다.
> **먼저 [§14 재설계 결정](#14-재설계-결정-2026-08-30)을 읽을 것.** §0~§13 은 구현 이력으로 남긴다.

> 본 문서는 **앱(qbt-live-app) ↔ live 서버** 를 잇는 데이터 계약과 전체 아키텍처를 담당한다.
> live 내부 구현 / 운영 상세 (모듈 / 상수 / CLI / 예외 / 배포) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 와 `src/live/` 코드가 정본이다.

## 0. 개요

QBT 포트폴리오 전략을 **Android 앱 + 일일 실행 엔진(live)** 구조로 실매매 알림 시스템으로 이식한다. live 는 평일 장 마감 후 GitHub Actions 로 실행되어 GCS 정본(`gs://qbt-live.firebasestorage.app`) 과 Firebase RTDB 를 갱신하고, 앱은 RTDB 를 통해 데이터를 읽고 체결을 입력한다.

### 앱 관점 확정 사항

| 항목                | 확정                                                      |
| ------------------- | --------------------------------------------------------- |
| UI                  | Android 앱 (React Native). 웹 없음                        |
| 앱 인증             | Firebase Auth Email/Password                              |
| 푸시 알림           | FCM (텍스트) + 텔레그램 봇 (동시 발송)                    |
| 앱 데이터 버스      | Firebase RTDB (Spark 무료)                                |
| 체결 입력           | 앱 → RTDB `/fills/inbox/{uuid}` (자동 매칭 + idempotency) |
| 자산 직접 수정      | 앱 → RTDB `/balance_adjust/inbox/{uuid}`                  |
| 차트                | RTDB 시계열 + TradingView Lightweight Charts              |
| FCM 토큰            | RTDB `/device_tokens/{device_id}` (복수 기기 대응)        |
| 정본 원장           | GCS 버킷 (앱은 접근하지 않음)                             |
| model / actual 분리 | 두 축을 RTDB 에서 별도로 읽고 표시                        |
| PendingOrder        | 단일 슬롯, `execute_on` 없음 (익일 시가 자동 확정)        |
| 스케쥴              | 평일 ET 17:27 cron, 매일 1 회 `/latest/*` 갱신            |

### 인프라 정보 (앱 설정에 필요)

| 항목              | 값                                                                   |
| ----------------- | -------------------------------------------------------------------- |
| Firebase 프로젝트 | `qbt-live` (Blaze 요금제 — GCS 사용을 위한 결제수단 등록)            |
| RTDB URL          | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지    | `com.ingbeen.qbtlive`                                                |
| 텔레그램 봇       | `@qbt_live_alert_bot`                                                |

**식별자 규칙**: RTDB 경로의 `{asset_id}` 는 항상 **소문자** (예: `sso`, `qld`, `gld`, `tlt`). 자산 목록과 live 서버 내부 상수 (`LIVE_PORTFOLIO_ID`, `SCHEMA_VERSION`, 드리프트 임계값 등) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 1. 전체 아키텍처

### 1.1 컴포넌트 다이어그램

```
                      [GitHub Actions cron]
                       평일 ET 17:27 1회
                              |
                              v
                      +----------------+
                      |  live (서버)   |
                      |  (src/live/)   |
                      +----------------+
                        |            |
           원장 read/write            read/write
                        v            v
              [GCS 정본]          [Firebase RTDB]  --- FCM/텔레그램 알림 --->  [Android 앱]
               (qbt-live.fire-    /latest/*                                          ^
                storage.app)      /charts/prices/*                                   |
               (앱 접근 불가)                                                         |
                                 /charts/equity/*                                    |
                                 /history/fills/*                                    |
                                 /history/balance_adjusts/*                          |
                                 /history/signals/*                                  |
                                 /fills/inbox       <------ 체결 / 보정 입력 --------+
                                 /balance_adjust/                                    |
                                 /device_tokens                                      |
                                                    <------ /latest/*, /charts/*,    |
                                                            /history/* --------------+
```

- **live** 는 평일 장 마감 후 GitHub Actions 에서 1 회 실행되어 GCS 정본과 RTDB 를 갱신한다.
- **GCS 정본** (`gs://qbt-live.firebasestorage.app`) 은 live 전용 정본 원장이며 **앱은 접근하지 않는다**.
- **Firebase RTDB** 는 앱 ↔ live 양방향 버스이다. 앱은 `/latest/*` 와 `/charts/*` 를 읽고, `/fills/inbox/*` 와 `/balance_adjust/inbox/*` 에 쓰며, `/device_tokens/*` 로 FCM 토큰을 등록한다.
- **FCM + 텔레그램** 은 live 가 매 실행 끝에 동시 발송한다 (일일 리포트 + 실패 알림).

live 내부 실행 순서 / 예외 훅 / GCS ephemeral 워크스페이스 메커니즘 등은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

### 1.2 앱 관점 핵심 원칙

- **앱이 유일한 UI** — 웹 없음.
- **GCS = 정본, RTDB = 앱 버스** — 앱은 GCS 에 직접 접근하지 않는다. **앱에 GCS 자격증명 절대 없음**.
- **model / actual 분리** — actual 축은 앱 입력(`/fills/inbox/` 또는 `/balance_adjust/inbox/`) 으로만 갱신된다. live 는 actual 을 덮어쓰지 않는다.
- **inbox 패턴** — `/latest/*` 는 live 가 매 실행마다 전체 덮어쓰므로 앱이 직접 쓰면 다음 실행에서 사라진다. 앱의 모든 쓰기는 `/fills/inbox/` / `/balance_adjust/inbox/` / `/device_tokens/` 세 경로에만 가능하다.
- **알림 동시 발송** — FCM + 텔레그램 은 독립 채널로 동시 발송된다. 한쪽 채널 실패는 다른 쪽을 막지 않는다.

### 1.3 통화 기준 (Currency)

**모든 금액 필드는 `USD` (미국 달러) 기준으로 저장된다.** 본 시스템은 환율 변환을 수행하지 않으며, 데이터 소스인 yfinance 에서 미국 상장 ETF 의 USD 원본 가격을 그대로 사용한다.

**적용 대상 필드** (RTDB / GCS 정본 공통):

- 자본금 / 현금: `model_equity`, `actual_equity`, `shared_cash_model`, `shared_cash_actual`
- 가격: `close`, `ma_value`, `upper_band`, `lower_band`, `actual_price` (체결 단가)
- 시계열: `/charts/prices/{asset_id}/years/{YYYY}.close`, `/charts/equity/years/{YYYY}.{model_equity,actual_equity}`
- inbox 입력값: 앱이 쓰는 체결 단가 / 보정 금액도 모두 USD

**비중 계산 (앱 계층 수식)**: 자산별 비중은 USD 단위 내에서 직접 계산 가능하다.

```
asset_weight[i] = (actual_shares[i] × close[i]) / actual_equity
cash_weight    = shared_cash_actual / actual_equity
```

환율 변환 / 통화 혼합 처리가 필요 없으며, 분자·분모 모두 USD 단위로 정합된다.

**범위**: 자산은 USD 단위 4종 (SSO / QLD / GLD / TLT) 으로 고정. 다른 통화 / 시장의 자산은 현재 스키마에서 지원되지 않으며, 포함하려면 자산별 `currency` / `market` 필드 도입 + 통화별 평가액 필드 분리 등 스키마 확장이 필요하다 (본 문서의 재설계 동반).

---

## 2. 알고리즘 / 주가 데이터 / 검증

live 는 QBT 백테스트 코어 (`qbt.backtest.*`) 를 직접 재사용하여 매일 신호 / 체결 / 리밸런싱을 계산하고, yfinance OHLC 수집 / 데이터 검증 (OHLC 논리 / 전일 종가 연속성 / 거래일 gap) / MA·밴드 계산 / `run_daily` 실행 순서 등의 내부 동작은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 와 `src/live/` 코드가 정본이다.

**앱이 알아야 할 것은 결과물뿐이다** — live 가 매일 계산한 포지션 / 시그널 / 밴드 / drift 스칼라는 RTDB `/latest/*` 로, equity 시계열(`model_equity` / `actual_equity`) 은 `/charts/equity/*` 로 노출된다 (§8.2 참고). 스플릿·무상증자 감지 / 회귀 검증 / BufferZoneStrategy 직렬화 같은 live 내부 로직은 앱에 영향을 주지 않는다.

---

## 3. model / actual 원장 분리

live 는 model 축과 actual 축을 **두 개의 독립된 원장** 으로 유지한다.

- **model** — daily runner 의 이론 포지션 (신호 → 전일 pending → 당일 시가 자동 체결)
- **actual** — 사용자가 실제로 체결한 포지션. `/fills/inbox/` 또는 `/balance_adjust/inbox/` 로만 갱신되며 model 이 actual 을 덮어쓰지 않는다.

두 값의 차이가 **drift** 이며 §12 에서 정의한다. 앱은 `/latest/portfolio` 에서 `model_*` 와 `actual_*` 두 쌍을 모두 받아 화면에 나란히 표시한다.

**signal_state 2 값 (`"buy"` / `"sell"`)** 은 누적 원장 상태이고, **SignalDetection.state 3 값 (`"buy"` / `"sell"` / `"none"`)** 은 당일 감지 결과이다. 두 개념은 수명 / 저장 여부 / 노출 경로가 다르며, 각각 `/latest/portfolio` (§8.2.1) 와 `/latest/signals` (§8.2.2) 로 노출된다.

---

## 4. 체결 입력 및 자산 보정

> 입력 스키마 / 필수 필드 / 검증 규칙 / idempotency / processed 필드 규칙은 §8.2.7 (`/fills/inbox`) 과 §8.2.8 (`/balance_adjust/inbox`) 이 정본이다. 본 섹션은 적용 순서와 의미 차이만 정의한다.

### 4.1 미입력 리마인더

`run-daily` 실행 시 `pending_order` 가 있는 자산 중 해당 자산에 대한 fill 이 아직 들어오지 않은 경우 `DailyResult.pending_fill_reminders` 에 포함되어 일일 리포트 본문(§6.2)에 건수로 노출된다. 일부 자산만 체결되어도 나머지 미체결 pending 은 다음 실행에서 다시 리마인더에 올라온다.

### 4.2 balance_adjust 의미와 적용 순서

`ActualFill` 은 "buy/sell 이벤트 누적" 이고 `BalanceAdjust` 는 "현재 잔고를 이 값으로 덮어쓰기" 이다. 이 의미 차이 때문에 `balance_adjust` 는 차트 마커 대상이 아니다.

적용 순서는 `run_daily` **내부에서** 고정되어 있다 — **fills 먼저, balance_adjust 나중** (사용자 직접 보정이 신호 기반 체결을 덮어쓰는 구조). 자산 shares / 현금의 실제 교체 규칙과 idempotency 는 §8.2.8 을 정본으로 한다.

### 4.3 model_sync 의미와 적용 순서

`ModelSync` 는 "지금 내 실제 포지션을 새 출발점으로 삼겠다" 는 사용자 선언이다. model 축과 actual 축이 체결 타이밍 차이 / 슬리피지 / 개인 매매 누적으로 점진적으로 벌어진 상태에서, 앱이 `/model_sync/inbox/{uuid}` 에 요청을 쓰면 다음 `run-daily` 가 **model 축 전체를 actual 값으로 일괄 교체**한다.

`run_daily` 내부 적용 순서:

1. fills 반영 (Stage 1, actual 축 누적)
2. balance_adjust 반영 (Stage 2, actual 축 덮어쓰기)
3. **model_sync 반영 (Stage 3, 신규)** — 모든 자산의 `model_shares` / `model_avg_entry_price` / `model_entry_date` 를 actual 값으로 복사하고 `shared_cash_model = shared_cash_actual` 로 교체. 동시에 모든 자산의 `pending_order = None`, `unfilled_order_date = None` 으로 초기화.
4. 전일 pending → 당일 시가 체결 (Stage 4). Stage 3 이 적용되면 pending 이 모두 비어 자연스럽게 skip.
5. 시그널 / 리밸런싱 / 익일 pending 생성 (Stage 5~7). 새 model 기준으로 재계산된다.

**pending 취소 규칙**: Stage 3 직전에 존재하던 모든 `pending_order` 는 **예외 없이** None 으로 초기화된다. 이전 model 기준으로 만들어진 pending 은 동기화 후 새 model 기준과 일관되지 않기 때문이다. 필요한 pending 은 Stage 7 에서 새로 생성된다.

**BufferZoneStrategy 내부 상태는 교체하지 않는다** — `buffer_zone_state` (prev_upper / prev_lower / hold_state 등) 는 유지해야 hold_days 상태머신이 끊기지 않는다. model_sync 는 "포지션(주수 / 가격 / 진입일 / 현금)" 만 교체한다.

**멱등성**: "model = actual" 덮어쓰기이므로 같은 요청을 여러 번 처리해도 결과가 같다. 같은 배치 안에 `ModelSync` 가 N 건 있으면 1 회만 적용 (N 회 반복하지 않음). 별도 `applied_model_sync_ids.json` 원장을 두지 않고 RTDB `processed` 플래그만으로 중복 방지한다 — 상세는 §8.2.9a.

**엣지 케이스**:

| 케이스                                | 결과                                                                         |
| ------------------------------------- | ---------------------------------------------------------------------------- |
| fill + model_sync 동일 배치           | Stage 1 이 actual 을 먼저 갱신, Stage 3 가 갱신된 actual 복사                |
| balance_adjust + model_sync 동일 배치 | Stage 2 가 actual 을 먼저 덮어쓰고, Stage 3 가 덮어쓴 actual 복사            |
| 전일 pending + model_sync             | Stage 3 이 pending 모두 해제 → Stage 4 에서 체결 없음 (`executions is None`) |
| model_sync 연속 2 일                  | 멱등 — 동일 결과                                                             |

---

## 5. 차트: TradingView Lightweight Charts

자산별 CSV 를 읽어 차트 시계열을 생성하고 RTDB `/charts/prices/{asset_id}/` 하위에 **2 분할 구조** 로 저장한다. 자산 ID 는 live 포트폴리오의 각 슬롯 `asset_id` 를 그대로 사용한다 (소문자). equity(포트폴리오 평가액) 시계열은 별도의 `/charts/equity/` 경로로 노출된다 (§8.2.6).

**RTDB 구조 (주가 차트 2 경로)**:

```
/charts/prices/{asset_id}/meta                ← 차트 메타 (first/last 날짜, years 등)
/charts/prices/{asset_id}/years/{YYYY}        ← 연도별 slice (현재 연도만 daily 갱신)
```

**시계열 필드** (years): `dates`, `close`, `ma_value`, `upper_band`, `lower_band`
**마커 필드** (years): `buy_signals`, `sell_signals`, `user_buys`, `user_sells` — 모두 **ISO 8601 날짜 문자열 배열** (인덱스 아님). 분할된 연도 사이에서 위치 독립적.

| 마커 종류                      | 출처                                 | 의미                          |
| ------------------------------ | ------------------------------------ | ----------------------------- |
| `buy_signals` / `sell_signals` | GCS 정본 `history/signals.jsonl`     | 과거 신호 발생일 (ISO 날짜)   |
| `user_buys` / `user_sells`     | GCS 정본 `history/user_trades.jsonl` | 사용자 체결 발생일 (ISO 날짜) |

정확한 페이로드 스키마와 필드 타입은 §8.2.5 를 참고한다.

**연도 슬라이스 정책**: 연도 단위 고정 slice. daily runner 는 "현재 연도" 슬라이스만 매 실행 덮어쓰고, 이전 연도는 건드리지 않는다. 최초 배포 시와 스플릿/무상증자 감지 시에는 운영자가 backfill CLI 로 전체 연도를 재생성한다. 연도별로 비중첩이라 dedupe 가 불필요하다.

**앱 로딩 플로우 (권장)**:

1. 앱 진입: `meta` 로드 → `meta.last_date - 12개월` 이 속한 연도부터 현재 연도까지의 `years/{YYYY}` 병렬 fetch (보통 2개) → 결합 후 `setData(merged)`. 진입 직후 최소 12개월 표시 보장.
2. 사용자가 좌측 끝으로 줌아웃: `meta.years` 참고하여 추가 연도 `years/{YYYY}` 점진 로드, 결합 후 `setData(merged)`.
3. 전체 보기: `meta.years` 전체를 순회 로드 (로컬 캐시 재사용).

`ma_value` 는 자산 슬롯의 `ma_window` 에 독립적이며, 앞 `ma_window - 1` 개 인덱스는 워밍업 구간으로 `null` 이다. `upper_band` / `lower_band` 는 `ma_value × (1 ± buffer_zone_pct)` 로 계산되며 MA 가 null 이면 밴드도 null 이다. Firebase RTDB 는 빈 배열을 저장하지 않으므로 마커 리스트가 비어 있으면 해당 키가 아예 생성되지 않는다 (앱은 키 부재를 "빈 배열" 로 해석).

`balance_adjust` 는 이벤트가 아니라 "최종 잔고 교체" 이므로 차트 마커 대상이 **아니다** (§4.2 참고).

앱은 WebView + TradingView Lightweight Charts 로 시계열을 렌더링한다.

---

## 6. 알림: FCM + 텔레그램

live 는 매 실행 끝에 FCM + 텔레그램을 동시 발송한다. 두 채널은 독립이며 한쪽 실패가 다른 쪽을 막지 않는다. 본문 텍스트는 두 채널이 동일하다.

| 종류        | 내용                                                                        | 빈도                      |
| ----------- | --------------------------------------------------------------------------- | ------------------------- |
| 일일 리포트 | model/actual equity, drift, 시그널, MA 근접도, 리밸런싱 여부, 리마인더 건수 | 매 run-daily 정상 실행    |
| 실패 알림   | 실패한 커맨드 이름 + 예외 메시지                                            | live 실행 중 예외 발생 시 |

### 6.1 FCM 메시지 구조 (앱 파싱 계약)

- `notification.title` = `"QBT Live"` (고정)
- `notification.body` = 아래 §6.2 / §6.3 의 본문 텍스트 (일일/실패 동일 구조)
- **data payload 없음** — 앱은 `notification.body` 텍스트를 그대로 표시한다.

**텔레그램**: Bot API `sendMessage` 로 `chat_id` + `text` 전송. `text` 는 FCM `body` 와 동일 문자열.

### 6.2 일일 리포트 본문 (예시)

```
[QBT Live] 2026-04-10

Model 동기화 적용
시그널: SSO buy, QLD sell
리밸런싱: 발생
미입력 체결 리마인더: 1 건

model equity: 12,345,678
actual equity: 12,300,000
drift: 0.37%
MA 근접도: SPY +2.45%, QQQ -1.05%, GLD +0.80%, TLT -1.20%
```

본문은 **강조 블록** (사용자 행동 필요 항목) 과 **일반 블록** (equity / drift / MA) 으로 구성되며, 빈 줄로 구분된다. 강조 블록이 비어있으면 빈 줄과 블록 자체를 생성하지 않는다.

행 구성 규칙:

- 1 행: `[QBT Live] {execution_date}` (prefix 고정)
- (빈 줄) → 강조 블록 (있을 때만):
  - `Model 동기화 적용`: 이번 실행에서 model_sync (§4.3 / §8.2.9a) 가 적용된 경우에만 **최상단** 에 노출. 이벤트의 원인이 되는 항목이므로 시그널 / 리밸런싱 / 리마인더보다 먼저 배치
  - `시그널`: 자산별 `state in ("buy","sell")` 만 `{ASSET_UPPER} {state}` 로 나열. 없으면 라인 생략
  - `리밸런싱: 발생`: 리밸런싱 발생 시에만 출력
  - `미입력 체결 리마인더: N 건`: fill 입력 또는 스킵(`/fill_dismiss/inbox/`) 전까지 **매일 반복** 표출. §8.2.9 참고
- (빈 줄) → 일반 블록:
  - `model equity` / `actual equity`: 천 단위 콤마 정수
  - `drift`: `{drift_pct * 100:.2f}%` (§11 참고)
  - `MA 근접도`: `{SIGNAL_TICKER} ±X.XX%` (자산별 signal 티커 기준, `(close - ma_value) / ma_value`)

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

### 8.1 GCS 정본 (qbt-live.firebasestorage.app)

live 서버는 `gs://qbt-live.firebasestorage.app` GCS 버킷을 원장(JSON + CSV + history) 으로 사용한다. **앱은 GCS 정본에 접근하지 않으며**, 앱이 보는 모든 데이터는 RTDB 경로(§8.2) 로만 전달된다. GCS 정본의 객체 키 트리 / 내부 스키마 / idempotency 원장 / history JSONL 포맷은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 및 `src/live/` 코드가 정본이다. 매 CLI 실행마다 `storage_gateway.state_workspace` 가 버킷을 임시 디렉토리에 download → 작업 → 변경된 파일만 upload 하는 ephemeral 워크스페이스 방식으로 동작한다 (`live_state.json` 마지막 upload). 사고 복구는 GCS Soft Delete 30일 보호 + 일별 스냅샷 (`history/states/{date}.json`) 으로 수행한다.

### 8.2 RTDB 경로 구조

```
/latest/portfolio                                ← 전체 자산 요약 + drift 스칼라 + assets/{asset_id}
/latest/signals/{asset_id}                       ← 시그널 상태 / 종가 / MA / 밴드
/latest/pending_orders/{asset_id}                ← 익일 체결 예정 주문 (pending 있는 자산만)
/charts/prices/{asset_id}/meta                   ← 주가 차트 메타 (first/last 날짜, years 등)
/charts/prices/{asset_id}/years/{YYYY}           ← 주가 차트 연도별 slice (현재 연도만 daily 갱신)
/charts/equity/meta                              ← equity 차트 메타 (운영 시작일 / 마지막일 / years)
/charts/equity/years/{YYYY}                      ← equity 연도별 slice (현재 연도만 daily 갱신)
/history/fills/{YYYY-MM-DD}/{uuid}               ← 체결 이력 영구 보존 (GCS 정본 user_trades.jsonl 미러)
/history/balance_adjusts/{YYYY-MM-DD}/{uuid}     ← 잔고 보정 이력 영구 보존 (GCS 정본 미러)
/history/signals/{YYYY-MM-DD}/{asset_id}         ← 신호 이력 영구 보존 (GCS 정본 signals.jsonl 미러)
/fills/inbox/{uuid}                              ← 앱이 쓰는 체결 queue
/balance_adjust/inbox/{uuid}                     ← 앱이 쓰는 잔고 보정 queue
/fill_dismiss/inbox/{uuid}                       ← 앱이 쓰는 체결 리마인더 스킵 queue
/model_sync/inbox/{uuid}                         ← 앱이 쓰는 model 동기화 요청 queue
/device_tokens/{device_id}                       ← FCM 토큰
```

RTDB 는 "앱 ↔ daily runner" 버스이며, 정본 저장소가 아니다. `/latest/*` 는 "오늘의 스냅샷" 이고 매 실행마다 전체 갱신되며 (inbox 패턴을 쓰는 이유), `/charts/*` 는 "시계열 데이터" 로 매일 meta + 현재 연도 슬라이스만 daily 갱신된다.

**예제 JSON 표기 주의**: 본 절 이하의 예제 JSON 에 등장하는 날짜 / 연도 / 가격 등 구체값은 작성 시점의 예시이며, 실제 값은 RTDB 에서 동적 결정된다. 필드 의미와 타입만 계약 SoT 로 본다.

**식별자 규칙**: asset_id 소문자 / ticker 대문자 규칙은 §0 "식별자 규칙" 참고.

**drift_pct 스케일**: RTDB 의 `drift_pct` 필드(`/latest/portfolio`) 는 내부 계산 / GCS 정본과 동일하게 **0~1 ratio** 로 저장된다 (프로젝트 네이밍 관례: `_pct` 접미사 = 0~1 범위. `.claude/rules/python.md` "비율 표기 규칙" 참고). 정밀도는 `ROUND_RATIO = 4` 자리. 앱이 표시할 때 `× 100` 변환은 앱 계층의 책임. 정의 / 임계값 / 라벨은 §12 참고. drift 는 RTDB 에 스칼라 형태로만 노출되며 시계열은 제공하지 않는다 (§8.2.4 / §8.2.6 참고).

#### 8.2.1 `/latest/portfolio` — 전체 포트폴리오 요약

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.LiveState`. 매 `run-daily` 실행마다 전체 덮어쓰기.

```json
{
  "execution_date": "2026-04-10",
  "model_equity": 10500,
  "actual_equity": 10300,
  "drift_pct": 0.0037,
  "shared_cash_model": 500.0,
  "shared_cash_actual": 498.5,
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

| 필드                              | 타입              | null | 설명                                                                                                                                                                                                                                       |
| --------------------------------- | ----------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `execution_date`                  | str               | 불가 | ISO 8601 날짜 (**미국 거래일 ET 기준**, 예: `"2026-04-10"`). GitHub Actions runner 가 `TZ=America/New_York` 에서 `date.today()` 를 사용하므로, cron 실행 시각이 한국 시간 기준 다음 날이어도 필드 값은 실행일 기준 미국 거래일로 저장된다. |
| `model_equity`                    | number            | 불가 | model 축 총 자산가치 (**USD 기준**, `ROUND_CAPITAL = 0` 자리)                                                                                                                                                                              |
| `actual_equity`                   | number            | 불가 | actual 축 총 자산가치 (**USD 기준**, `ROUND_CAPITAL = 0` 자리)                                                                                                                                                                             |
| `drift_pct`                       | number            | 불가 | drift 비율 (0~1 ratio, `ROUND_RATIO = 4` 자리, 예: `0.0037` = 0.37%). §12 참고                                                                                                                                                             |
| `shared_cash_model`               | number            | 불가 | model 축 공유 현금 (**USD 기준**)                                                                                                                                                                                                          |
| `shared_cash_actual`              | number            | 불가 | actual 축 공유 현금 (**USD 기준**)                                                                                                                                                                                                         |
| `assets.{asset_id}.model_shares`  | int               | 불가 | model 축 보유 주식 수                                                                                                                                                                                                                      |
| `assets.{asset_id}.actual_shares` | int               | 불가 | actual 축 보유 주식 수                                                                                                                                                                                                                     |
| `assets.{asset_id}.signal_state`  | `"buy"`\|`"sell"` | 불가 | 누적 원장 신호 상태. 초기값 `"sell"` (포지션 없음). §3 참고                                                                                                                                                                                |

**자산 키 보장**: `assets.{asset_id}` 는 항상 4 자산 (`sso`, `qld`, `gld`, `tlt`) 전부를 포함한다. 자산을 전량 매도하여 0 주 상태가 되어도 키는 유지되며 `model_shares=0`, `actual_shares=0`, `signal_state="sell"` 로 저장된다. 앱은 키 존재를 가정해도 안전하다.

#### 8.2.2 `/latest/signals/{asset_id}` — 당일 시그널 / MA / 밴드

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.SignalDetection`. 매 실행 자산 전체 덮어쓰기.

```json
{
  "sso": {
    "state": "buy",
    "close": 123.45,
    "ma_value": 120.5,
    "ma_distance_pct": 0.0245,
    "upper_band": 126.525,
    "lower_band": 114.475
  },
  "qld": {
    "state": "none",
    "close": 85.2,
    "ma_value": 86.1,
    "ma_distance_pct": -0.0105,
    "upper_band": null,
    "lower_band": null
  }
}
```

| 필드              | 타입                        | null | 설명                                                                                                  |
| ----------------- | --------------------------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `state`           | `"buy"`\|`"sell"`\|`"none"` | 불가 | **당일 감지** 된 신호. `"none"` = 오늘 새 신호 없음. 누적 원장(`signal_state`) 과는 별개. §3 참고     |
| `close`           | number                      | 불가 | 당일 종가 (**USD**, `ROUND_PRICE = 6` 자리)                                                           |
| `ma_value`        | number                      | 가능 | 자산 슬롯의 `ma_window` 기준 MA 값 (**USD**, 워밍업 구간은 null)                                      |
| `ma_distance_pct` | number                      | 불가 | `(close - ma_value) / ma_value` (비율 0~1, 음수 가능, `ROUND_RATIO = 4` 자리)                         |
| `upper_band`      | number                      | 가능 | BufferZone 상단 밴드 (**USD**, 버퍼존 미사용 자산은 null). 전략이 다음 거래일 판단에 사용할 값과 동일 |
| `lower_band`      | number                      | 가능 | BufferZone 하단 밴드 (**USD**, 버퍼존 미사용 자산은 null)                                             |

#### 8.2.3 `/latest/pending_orders/{asset_id}` — 익일 체결 예정 주문

**SoT**: `live.rtdb_gateway.write_read_model`, `live.models.PendingOrderDict`. 매 실행 전체 덮어쓰기 (pending_order 가 있는 자산만 기록).

```json
{
  "sso": {
    "asset_id": "sso",
    "intent_type": "ENTER_TO_TARGET",
    "signal_date": "2026-04-10",
    "current_amount": 0.0,
    "target_amount": 3500.0,
    "delta_amount": 3500.0,
    "target_weight": 0.35,
    "hold_days_used": 0,
    "reason": "buffer upper band 돌파 — 매수 진입"
  }
}
```

| 필드             | 타입                                                                            | 설명                                                                                             |
| ---------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `asset_id`       | str                                                                             | 소문자 자산 ID (중복 저장 — 최상위 key 와 동일)                                                  |
| `intent_type`    | `"EXIT_ALL"`\|`"ENTER_TO_TARGET"`\|`"REDUCE_TO_TARGET"`\|`"INCREASE_TO_TARGET"` | QBT `OrderIntent.intent_type` 과 동일한 Literal                                                  |
| `signal_date`    | str                                                                             | 신호 발생 날짜 (ISO 8601). 체결 예정일은 **다음 거래일 시가** 자동 확정 — `execute_on` 필드 없음 |
| `current_amount` | number                                                                          | 현재 자산 평가액 (**USD**)                                                                       |
| `target_amount`  | number                                                                          | 목표 자산 평가액 (**USD**)                                                                       |
| `delta_amount`   | number                                                                          | 증감량 (**USD**, 음수=매도, 양수=매수)                                                           |
| `target_weight`  | number                                                                          | 목표 비중 (0~1 비율)                                                                             |
| `hold_days_used` | int                                                                             | BufferZone hold_days 누적 (매수 확정 대기 일수)                                                  |
| `reason`         | str                                                                             | 신호 이유 설명 (앱 리마인더 본문)                                                                |

#### 8.2.4 drift 스칼라 — `/latest/portfolio` 에 통합

drift 스칼라 요약 (`drift_pct` / `model_equity` / `actual_equity`) 은 `/latest/portfolio` (§8.2.1) 에서 읽는다. 자산별 drift 가 필요하면 `/latest/portfolio` + `/latest/signals` 로 앱에서 계산하거나, 운영자가 GCS 정본 `history/daily/{date}.json` 을 조회한다.

#### 8.2.5 `/charts/prices/{asset_id}/` — 주가 차트 데이터 (meta + years/{YYYY})

**SoT**:

- meta: `live.chart_data.build_chart_meta`, `live.models.ChartMeta`, `live.rtdb_gateway.write_chart_meta`
- years: `live.chart_data.build_chart_year_slice`, `live.models.ChartSeries`, `live.rtdb_gateway.write_chart_year_slice`

**갱신 주체**: daily runner (`run-daily`) 가 매 실행마다 `meta` / `years/{현재_연도}` 를 덮어쓴다. 이전 연도 슬라이스는 daily 갱신 대상이 아니며, 최초 배포 / 스플릿 / 무상증자 시 운영자가 backfill CLI 로 재생성한다.

##### 8.2.5.1 `/charts/prices/{asset_id}/meta`

```json
{
  "first_date": "2013-01-02",
  "last_date": "2026-04-14",
  "ma_window": 200,
  "years": [
    2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024,
    2025, 2026
  ]
}
```

| 필드         | 타입      | 설명                                                                         |
| ------------ | --------- | ---------------------------------------------------------------------------- |
| `first_date` | str       | 자산 CSV 의 첫 거래일 (ISO 8601)                                             |
| `last_date`  | str       | 자산 CSV 의 마지막 거래일 (ISO 8601)                                         |
| `ma_window`  | int       | 자산 슬롯의 MA 윈도우 (워밍업 길이 계산용)                                   |
| `years`      | list[int] | CSV 가 포함하는 연도 목록 (오름차순). 앱이 줌아웃 시 로드할 연도 경로를 결정 |

앱은 `meta` 를 가장 먼저 한 번 읽고, `last_date - 12개월` 이 속한 연도부터 현재 연도까지의 `years/{YYYY}` 를 병렬 로드한다 (진입 시 12개월 보장). 이후 사용자 좌측 스크롤 시 추가 연도를 점진 로드.

##### 8.2.5.2 `/charts/prices/{asset_id}/years/{YYYY}`

특정 연도 전체 슬라이스 (1월 1일 ~ 12월 31일 범위 내 거래일). daily runner 는 **현재 연도 만** 갱신하고, 이전 연도 슬라이스는 backfill CLI 또는 수동 재생성 시에만 쓴다.

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

| 필드           | 타입                 | 설명                                                                                  |
| -------------- | -------------------- | ------------------------------------------------------------------------------------- |
| `dates`        | list[str]            | 해당 연도 거래일 (ISO 8601)                                                           |
| `close`        | list[number]         | 종가 (**USD**, `ROUND_PRICE = 6` 자리)                                                |
| `ma_value`     | list[number \| null] | MA (**USD**). 워밍업 구간은 null                                                      |
| `upper_band`   | list[number \| null] | `ma_value × (1 + buy_buffer_zone_pct)` (**USD**)                                      |
| `lower_band`   | list[number \| null] | `ma_value × (1 - sell_buffer_zone_pct)` (**USD**)                                     |
| `buy_signals`  | list[str]            | 해당 연도 내 매수 신호 발생일 (ISO 8601). GCS 정본 `history/signals.jsonl` 에서 파생  |
| `sell_signals` | list[str]            | 해당 연도 내 매도 신호 발생일 (ISO 8601)                                              |
| `user_buys`    | list[str]            | 해당 연도 내 사용자 매수 체결일 (ISO 8601). GCS 정본 `history/user_trades.jsonl` 에서 파생 |
| `user_sells`   | list[str]            | 해당 연도 내 사용자 매도 체결일 (ISO 8601)                                            |

##### 8.2.5.3 중요 사항 (빈 배열 / null 처리)

- Firebase RTDB 는 **빈 배열 `[]` 을 저장하지 않는다**. 마커 리스트가 비어 있으면 해당 키(`buy_signals` 등) 가 아예 생성되지 않으므로, 앱은 키 부재를 "빈 배열" 로 해석해야 한다.
- `ma_value` / `upper_band` / `lower_band` 의 워밍업 구간은 `null` 값으로 채워진다 (배열 인덱스는 유지, 값만 null).
- 슬라이스는 연도별로 **비중첩**이라 dedupe 가 불필요하다. 앱은 단순 정렬 + 결합으로 충분.

#### 8.2.6 `/charts/equity/` — equity 차트 (meta + years/{YYYY})

**SoT**:

- meta: `live.chart_data.build_equity_meta`, `live.models.EquityChartMeta`, `live.rtdb_gateway.write_equity_meta`
- years: `live.chart_data.build_equity_year_slice`, `live.models.EquityChartSeries`, `live.rtdb_gateway.write_equity_year_slice`

**데이터 소스**: GCS 정본 `history/summary.jsonl` 전체. 앱은 차트 진입 시 `meta` 를 먼저 읽고, `last_date - 12개월` 이 속한 연도부터 현재 연도까지의 `years/{YYYY}` 를 병렬 로드한다 (12개월 보장). 줌아웃 시에는 추가 연도를 점진 로드. 주가 차트와 달리 **포트폴리오 전체 1 개 시계열** 을 대상으로 하므로 자산 반복이 없으며, 한 경로에 `dates` / `model_equity` / `actual_equity` 세 배열을 같은 날짜 인덱스로 저장한다. drift 스칼라는 `/latest/portfolio.drift_pct` 에서 별도 노출되며 시계열 형태로는 제공하지 않는다.

**갱신 주체**: daily runner (`run-daily`) 가 매 실행마다 `meta` / `years/{현재_연도}` 를 덮어쓴다. 이전 연도 슬라이스는 daily 갱신 대상이 아니며, 최초 배포 / 스플릿 / 무상증자 시 운영자가 `backfill-chart-years --target equity` 로 재생성한다 (§9.1 참고).

##### 8.2.6.1 `/charts/equity/meta`

```json
{
  "first_date": "2024-01-02",
  "last_date": "2026-04-14",
  "years": [2024, 2025, 2026]
}
```

| 필드         | 타입      | 설명                                             |
| ------------ | --------- | ------------------------------------------------ |
| `first_date` | str       | summary.jsonl 의 첫 날짜 (ISO 8601, 운영 시작일) |
| `last_date`  | str       | summary.jsonl 의 마지막 날짜 (ISO 8601)          |
| `years`      | list[int] | summary.jsonl 이 포함하는 연도 목록 (오름차순)   |

##### 8.2.6.2 `/charts/equity/years/{YYYY}`

특정 연도 전체 슬라이스. 해당 연도에 summary 로우가 없으면 모든 배열이 빈 슬라이스가 반환된다.

```json
{
  "dates": ["2025-01-02", "…", "2025-12-31"],
  "model_equity": [...],
  "actual_equity": [...]
}
```

| 필드            | 타입         | 설명                                                      |
| --------------- | ------------ | --------------------------------------------------------- |
| `dates`         | list[str]    | 해당 연도 거래일 (ISO 8601)                               |
| `model_equity`  | list[number] | model 축 총 자산가치 (**USD**, `ROUND_CAPITAL = 0` 자리)  |
| `actual_equity` | list[number] | actual 축 총 자산가치 (**USD**, `ROUND_CAPITAL = 0` 자리) |

**불변조건**: 3 배열은 모두 같은 길이 / 같은 날짜 인덱스. summary.jsonl 스키마상 null 이 나올 수 없다.

##### 8.2.6.3 중요 사항

- **Firebase RTDB 의 빈 배열 저장 정책**: equity 차트는 summary.jsonl 상 각 날짜에 3 필드 모두 값이 존재하므로 null / 빈 값 케이스는 발생하지 않는다. 단 `years/{YYYY}` 에 해당 연도 데이터가 아예 없는 경우 모든 배열이 비어 있을 수 있다.
- **정본 위치**: 자산별 상세·전체 equity 시계열은 GCS 정본 `history/summary.jsonl` 이 유일 정본이며 **영구 누적** 된다. RTDB 쪽은 앱 표시용 소비 데이터로만 취급한다.
- 슬라이스는 연도별로 비중첩이라 dedupe 가 불필요하다 (§8.2.5.3 과 동일).

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

| 필드             | 타입              | 설명                                                                           |
| ---------------- | ----------------- | ------------------------------------------------------------------------------ |
| `asset_id`       | str               | 소문자 자산 ID. live 포트폴리오에 존재해야 함 (미보유 → `ValueError`)          |
| `direction`      | `"buy"`\|`"sell"` | **대소문자 민감**. 다른 값은 `ValueError("fill direction 값이 유효하지 않음")` |
| `actual_price`   | number            | 체결 가격 (**USD**)                                                            |
| `actual_shares`  | int               | 체결 수량                                                                      |
| `trade_date`     | str               | ISO 8601 날짜 (예: `"2026-04-10"`)                                             |
| `input_time_kst` | str               | ISO 8601 KST 타임스탬프 (예: `"2026-04-10T15:30:22+09:00"`)                    |

**선택 필드**:

| 필드     | 타입        | 설명                                                                                                                                                                                                                 |
| -------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `memo`   | str \| null | 사용자 자유 메모 (기본 null)                                                                                                                                                                                         |
| `reason` | str         | 앱이 전송한 **자유 텍스트 사유** (기본 `""`). 서버는 이 값을 변환하지 않고 `ActualFill.reason` 에 그대로 저장하며 `/history/fills/` 미러에도 동일 값이 들어간다. 체결 탭 UI 는 현재 입력을 받지 않아 항상 `""` 이다. |

**서버측 검증 (거부 조건)** — 위반 시 `run-daily` 가 즉시 중단되고 FCM + 텔레그램 실패 알림 발송:

1. unknown `asset_id` → `ValueError("알 수 없는 asset_id=...")`
2. 매도 시 `actual_shares > actual_shares(보유)` → `ValueError("보유량 초과 매도")`
3. 매수 체결로 `shared_cash_actual < 0` → `ValueError("현금 부족")`

**idempotency**: `rtdb_key` (UUID) 기반. `applied_fill_ids.json` 에 이미 기록된 key 는 skip. 90 일 초과 key 는 자동 정리. `processed` 필드 규칙은 §8.3 참고.

#### 8.2.8 `/balance_adjust/inbox/{uuid}` — 잔고 직접 보정 (앱 → 서버)

**SoT**: `live.rtdb_gateway._dict_to_balance_adjust`, `live.models.BalanceAdjust`, `live.balance_adjust.apply_balance_adjusts_idempotent`. 앱이 UUID key 를 생성하여 append, daily runner 가 `processed=false` 만 필터링해 읽는다.

**actual 축 전용**: balance*adjust 는 `AssetLiveState.actual*_`/`shared*cash_actual`만 건드리며`model*_`/`shared_cash_model` 은 절대 변경하지 않는다 (§1.2 "model / actual 분리" 원칙).

**예시 1** — 자산 + 현금 동시 보정:

```json
{
  "asset_id": "sso",
  "new_shares": 150,
  "new_cash": 500.0,
  "reason": "오프라인 매수 반영",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**예시 2** — 현금만 보정 (배당 / 세금):

```json
{
  "new_cash": 510.0,
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

**예시 4** — 평균가만 직접 보정 (주수는 유지):

```json
{
  "asset_id": "sso",
  "new_avg_price": 82.55,
  "reason": "평균가 재입력",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**예시 5** — 주수 + 평균가 + 진입일 동시 보정 (포지션 재집계):

```json
{
  "asset_id": "sso",
  "new_shares": 500,
  "new_avg_price": 82.55,
  "new_entry_date": "2026-04-01",
  "reason": "오프라인 거래 재집계",
  "input_time_kst": "2026-04-10T15:30:22+09:00"
}
```

**필드**:

| 필드             | 타입           | 필수 여부 | 설명                                                                                                                                                         |
| ---------------- | -------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `asset_id`       | str \| null    | 조건부    | 자산 축 보정 시 필수 (`new_shares` / `new_avg_price` / `new_entry_date` 중 하나라도 지정 시). 현금만 보정하면 null / 생략 가능. unknown → `ValueError`       |
| `new_shares`     | int \| null    | 조건부    | 자산 shares 교체값. `0` 이면 평균가 / entry_date 리셋 (평균가 / 진입일 보정보다 우선)                                                                        |
| `new_avg_price`  | number \| null | 조건부    | `actual_avg_entry_price` 교체값 (**USD**). `asset_id` 필수. `actual_shares == 0` 인 자산에 단독 지정 시 `ValueError`. `new_shares=0` 시 무시됨               |
| `new_entry_date` | str \| null    | 조건부    | `actual_entry_date` 교체값 (ISO 8601 날짜 `YYYY-MM-DD`). `asset_id` 필수. `actual_shares == 0` 인 자산에 단독 지정 시 `ValueError`. `new_shares=0` 시 무시됨 |
| `new_cash`       | number \| null | 조건부    | `shared_cash_actual` 교체값 (**USD**)                                                                                                                        |
| `reason`         | str            | 권장      | 보정 사유 (audit 로그용)                                                                                                                                     |
| `input_time_kst` | str            | 권장      | ISO 8601 KST 타임스탬프                                                                                                                                      |

**핵심 제약** (live daily runner 가 검증하며, 위반 시 즉시 `ValueError` fail-fast):

1. **`new_shares` / `new_avg_price` / `new_entry_date` / `new_cash` 네 필드 모두 null 이면 `ValueError("balance_adjust 에 유효한 new_shares / new_avg_price / new_entry_date / new_cash 값이 없음")`** — 앱은 빈 adjust 를 절대 전송하지 말 것.
2. 자산 축 보정 (`new_shares` / `new_avg_price` / `new_entry_date` 중 하나라도 지정) 시 `asset_id` 가 live 포트폴리오에 존재해야 한다 (unknown → `ValueError`).
3. `new_avg_price` / `new_entry_date` 지정 시 `asset_id` 는 필수 (`None` 이면 `ValueError`). 어느 자산의 값을 바꿀지 특정할 수 없기 때문.
4. 현재 `actual_shares == 0` 인 자산에 `new_avg_price` / `new_entry_date` 를 **단독** 지정하면 `ValueError("보유 주수가 0 인 자산의 평균가 / 진입일을 설정할 수 없음")`. 포지션이 없는데 평균가 / 진입일이 있는 것은 논리적 오류이기 때문.
5. `new_shares=0` 리셋 규칙은 `new_avg_price` / `new_entry_date` 보다 우선 — `new_shares=0` + `new_avg_price` 동시 지정 시 평균가 / 진입일은 무시되고 0.0 / None 으로 리셋된다.
6. `new_shares > 0` + `new_avg_price` / `new_entry_date` 동시 지정 시 해당 필드가 함께 갱신된다. 동시 지정하지 않으면 기존 값이 유지된다.
7. `balance_adjust` 는 차트 마커 대상이 **아니다** (교체 이벤트이므로 과거 시점에 표시되지 않는다).

**idempotency**: `rtdb_key` (UUID) 기반. `applied_balance_adjust_ids.json` 에 기록. 90 일 자동 정리. `processed` 필드 규칙은 §8.3 참고.

##### 8.2.8.1 입력 검증 역할 분담 (앱 ↔ live)

balance_adjust 의 입력 유효성 검사는 **2 단계** 로 이루어진다. 앱과 live 가 각기 다른 목적의 검증을 담당한다.

**1 단계 — 앱 (Android) 클라이언트 측 즉시 검증 (UX 목적)**

앱 UI 에서 사용자가 "잔고 보정" 입력 버튼을 누르는 순간 클라이언트 측에서 즉시 검증하고, 실패 시 사용자에게 인라인 피드백을 표시한다. **잘못된 데이터가 애초에 RTDB `/balance_adjust/inbox/` 에 도달하지 않도록 차단** 하는 것이 목적이다.

앱이 강제해야 할 규칙:

- `new_shares` / `new_avg_price` / `new_entry_date` / `new_cash` 중 적어도 하나는 값이 있어야 한다 (저장 버튼 비활성화).
- `new_avg_price` / `new_entry_date` 가 입력되면 자산 선택 (`asset_id`) 필수 (드롭다운 필수 선택).
- 선택한 자산의 현재 `actual_shares == 0` 이면 `new_avg_price` / `new_entry_date` 단독 입력 버튼 비활성화 ("포지션 없음" 안내).
- `new_entry_date` 는 ISO 8601 날짜 (`YYYY-MM-DD`) 형식 (date picker 로 입력 강제).
- `new_shares=0` 선택 시 "평균가 / 진입일은 함께 리셋됩니다" 안내 표시.

**2 단계 — live `daily_runner` 측 최후 방어선 (안전성 목적)**

GitHub Actions cron 으로 실행되는 daily runner 가 RTDB `/balance_adjust/inbox/` 를 읽어 반영하기 직전에 `live.rtdb_gateway._dict_to_balance_adjust` + `live.balance_adjust._apply_single_adjust` 두 지점에서 계약을 재검증한다. 위반 시 silent skip 대신 즉시 `ValueError` 를 발생시키고, `cli.py` 의 `main()` 공통 예외 훅이 FCM + 텔레그램으로 실패 알림을 발송한다. **앱 검증이 우회되었거나(구버전 앱 / 조작된 요청 / 앱 버그) 앱 로직에 허점이 있을 경우의 마지막 안전 장치** 역할이다.

**왜 두 단계가 모두 필요한가**:

- 1 단계만 있으면: 앱 버그 / 구버전 앱 / 수동 RTDB 조작 등으로 잘못된 데이터가 서버에 도달할 수 있다. live 가 이를 무심코 처리하면 actual 상태가 깨진다.
- 2 단계만 있으면: 사용자는 하루 뒤 장마감 후 cron 실행 시점에야 "보정 실패" 알림을 받는다. UX 가 나쁘고, 그동안 다른 보정 입력도 쌓여서 어느 것이 문제인지 추적이 어려워진다.
- 두 단계 모두 있으면: 1 단계가 UX 즉시 피드백을 담당하고, 2 단계가 안전성과 감사(audit) 를 담당한다. 이 역할 분담은 본 설계서의 핵심 원칙 §1.2 "inbox 패턴" 및 `src/live/CLAUDE.md` 의 "silent skip 금지 + 무조건 알림" 원칙과 일관된다.

#### 8.2.9 `/fill_dismiss/inbox/{uuid}` — 체결 리마인더 스킵 (앱 → 서버)

**SoT**: `live.rtdb_gateway._dict_to_fill_dismiss`, `live.models.FillDismiss`. 앱이 UUID key 를 생성하여 append, daily runner 가 `processed=false` 만 필터링해 읽는다.

사용자가 시그널에 따른 체결을 입력하지 않기로 결정했을 때 "스킵" 버튼으로 전송한다. live 는 이 레코드를 처리하여 해당 자산의 `unfilled_order_date` 를 `None` 으로 해제하고 리마인더를 중지한다. **잔고(actual 축)는 일체 변경하지 않는다.**

**예시**:

```json
{
  "asset_id": "sso",
  "reason": "수동 스킵",
  "input_time_kst": "2026-04-15T20:00:00+09:00"
}
```

**필드**:

| 필드             | 타입 | 필수 여부 | 설명                                                         |
| ---------------- | ---- | --------- | ------------------------------------------------------------ |
| `asset_id`       | str  | 필수      | 리마인더를 해제할 자산 ID. unknown → live 에서 무시 (로그만) |
| `reason`         | str  | 권장      | 스킵 사유 (audit 로그용)                                     |
| `input_time_kst` | str  | 권장      | ISO 8601 KST 타임스탬프                                      |

**핵심 제약**:

1. `asset_id` 가 없으면 `ValueError` (fail-fast).
2. fill_dismiss 는 `actual_shares` / `actual_avg_entry_price` / `shared_cash_actual` 등 **잔고를 일체 변경하지 않는다**. 리마인더 해제 전용.
3. `balance_adjust` 와 독립: balance_adjust 로 주수를 보정해도 리마인더는 해제되지 않으며, fill_dismiss 로 리마인더를 해제해도 잔고는 변하지 않는다.

**리마인더 지속성**: model 이 pending_order 를 체결한 뒤 fill 이 미도착하면 `AssetLiveState.unfilled_order_date` 가 set 된다. 이 플래그는 **fill 입력 또는 fill_dismiss** 가 도착할 때까지 매일 유지되며, 일일 리포트 알림에 "미입력 체결 리마인더: N 건" 으로 반복 표출된다.

**idempotency**: `rtdb_key` (UUID) 기반. `applied_fill_dismiss_ids.json` 에 기록. 90 일 자동 정리. `processed` 필드 규칙은 §8.3 참고.

#### 8.2.9a `/model_sync/inbox/{uuid}` — model 동기화 요청 (앱 → 서버)

**SoT**: `live.rtdb_gateway._dict_to_model_sync`, `live.models.ModelSync`. 앱이 UUID key 를 생성하여 append, daily runner 가 `processed=false` 만 필터링해 읽는다.

사용자가 "지금 내 실제 포지션을 새 출발점으로 삼겠다" 고 선언했을 때 앱이 확인 다이얼로그 1 회를 거쳐 전송한다. live 는 다음 `run-daily` 에서 **모든 자산의 `model_*` 축을 `actual_*` 값으로 일괄 교체**하고, 동시에 모든 `pending_order` / `unfilled_order_date` 를 `None` 으로 해제한다. 적용 순서 / pending 취소 규칙은 §4.3 참고.

**예시**:

```json
{
  "input_time_kst": "2026-04-15T20:00:00+09:00"
}
```

**필드**:

| 필드             | 타입 | 필수 여부 | 설명                                                   |
| ---------------- | ---- | --------- | ------------------------------------------------------ |
| `input_time_kst` | str  | 필수      | 사용자가 앱에서 동기화 버튼을 누른 시각 (ISO 8601 KST) |

**의도적으로 두지 않은 필드**:

- `asset_id` — 전체 동기화 전용이므로 자산을 지정하지 않는다.
- `reason` — 확인 다이얼로그 1 회로 충분하므로 사유 입력 UI 가 없다.

**핵심 제약**:

1. `input_time_kst` 가 없거나 빈 문자열이면 `ValueError` (fail-fast).
2. 여러 건이 동시에 쌓여도 1 회만 적용 (멱등). "model = actual" 덮어쓰기이므로 N 회 반복 의미가 없다.
3. 별도 `applied_model_sync_ids.json` 원장을 두지 않는다 — RTDB `processed` 플래그가 유일한 중복 방지 수단.

**idempotency**: `rtdb_key` (UUID) 기반. 적용 여부와 무관하게 읽어온 모든 key 는 `processed=true` 로 마킹된다. `processed` 필드 규칙은 §8.3 참고.

**이력 추적**: `/history/model_syncs/` RTDB 미러 / 별도 JSONL 은 제공하지 않는다. 발생 빈도가 월 0~1 회 수준이며, GCS 정본 `history/daily/{date}.json` 의 `model_sync_applied: bool` 과 `history/states/{date}.json` 전후 스냅샷으로 충분히 추적 가능하다 (§8.2.14 비미러 항목 참고).

#### 8.2.10 `/device_tokens/{device_id}` — FCM 토큰 등록 (앱 → 서버)

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

| 필드             | 타입          | 설명                                                                                      |
| ---------------- | ------------- | ----------------------------------------------------------------------------------------- |
| `{device_id}` 값 | str \| object | str 이면 토큰 그 자체. object 면 `token` 필드에서 추출 (다른 필드는 무시되지만 저장 가능) |
| `token`          | str           | FCM registration token (객체 형식에서만 사용)                                             |

**자동 정리**: daily runner 가 FCM 발송 시 `UnregisteredError` / `NOT_FOUND` 코드를 받으면 해당 토큰을 `remove_invalid_tokens` 로 `/device_tokens/` 에서 삭제한다. 앱은 앱 실행 시 자신의 토큰이 여전히 등록되어 있는지 확인하고 없으면 재등록하는 로직을 구현해야 한다.

**device_id 선택 원칙**: 앱이 기기별로 고유한 키를 선택한다 (예: 설치 UUID). 동일 기기에서 재설치하면 새 UUID 를 쓰는 것이 안전하다 (이전 토큰이 invalid 로 남을 수 있으나 서버가 자동 정리).

#### 8.2.11 `/history/fills/{YYYY-MM-DD}/{uuid}` — 체결 이력 영구 보존

**SoT**: `live.rtdb_gateway.write_history_fills`, `live.models.ActualFill`. GCS 정본 `history/user_trades.jsonl` 의 RTDB 미러. daily runner 가 매 실행마다 **이번 실행에서 새로 적용된 fill 만** 추가하고, 기존 레코드는 idempotent 덮어쓰기.

```json
{
  "asset_id": "sso",
  "direction": "buy",
  "actual_price": 82.05,
  "actual_shares": 420,
  "trade_date": "2026-04-10",
  "input_time_kst": "2026-04-10T20:00:00+09:00",
  "memo": null,
  "reason": "",
  "applied_at": "2026-04-11T07:27:15+09:00"
}
```

| 필드             | 타입              | null | 설명                                                                                                 |
| ---------------- | ----------------- | ---- | ---------------------------------------------------------------------------------------------------- |
| `asset_id`       | str               | 불가 | 자산 ID 소문자 (sso/qld/gld/tlt)                                                                     |
| `direction`      | `"buy"`\|`"sell"` | 불가 | 체결 방향                                                                                            |
| `actual_price`   | number            | 불가 | 체결 단가 (**USD**, `ROUND_PRICE = 6` 자리)                                                          |
| `actual_shares`  | int               | 불가 | 체결 주식 수                                                                                         |
| `trade_date`     | str               | 불가 | 사용자가 입력한 체결 일자 (ISO 8601). 폴더 키와 동일                                                 |
| `input_time_kst` | str               | 불가 | 사용자가 앱에서 입력한 시각 (ISO 8601 KST)                                                           |
| `memo`           | str               | 가능 | 사용자 메모 (UI 입력)                                                                                |
| `reason`         | str               | 불가 | 앱이 전송한 원본 값 그대로 (주로 `""`). `/history/fills/` 는 `ActualFill.reason` 을 그대로 미러한다. |
| `applied_at`     | str               | 불가 | run-daily 가 이 fill 을 반영한 시각 (ISO 8601 KST). 같은 배치 내 모든 신규 레코드에 동일 부여        |

**키 전략**:

- 폴더 키 = `trade_date` (사용자 입력 체결 일자).
- 레코드 키 = `ActualFill.rtdb_key` (앱이 생성한 UUID). 본문 페이로드에는 중복 저장하지 않는다 (상위 노드 키이므로).

**idempotency**: UUID 가 `applied_fill_ids.json` 에 이미 있으면 run-daily 가 fill 자체를 skip 하므로 RTDB history 에도 추가되지 않는다 (자연 방지). 같은 UUID 로 재호출되면 set 으로 덮어쓰기.

**보존 정책**: 영구. rolling 삭제 / cleanup 없음. `reset` 은 GCS 정본 `history/` 와 RTDB `/history/*` 를 모두 초기화하며, 이후 `run-daily` 가 매일 당일분을 GCS 정본 + RTDB 양쪽에 누적한다.

#### 8.2.12 `/history/balance_adjusts/{YYYY-MM-DD}/{uuid}` — 잔고 보정 이력 영구 보존

**SoT**: `live.rtdb_gateway.write_history_balance_adjusts`, `live.models.BalanceAdjust`. GCS 정본 `history/balance_adjusts.jsonl` 의 RTDB 미러.

```json
{
  "asset_id": "sso",
  "new_shares": 420,
  "new_avg_price": null,
  "new_entry_date": null,
  "new_cash": null,
  "reason": "년초 잔고 조정",
  "input_time_kst": "2026-04-10T20:00:00+09:00",
  "applied_at": "2026-04-11T07:27:15+09:00"
}
```

| 필드             | 타입   | null | 설명                                      |
| ---------------- | ------ | ---- | ----------------------------------------- |
| `asset_id`       | str    | 가능 | 보정 대상 자산 ID. cash 단독 보정 시 null |
| `new_shares`     | int    | 가능 | 교체할 actual_shares. 미지정 시 null      |
| `new_avg_price`  | number | 가능 | 교체할 actual_avg_entry_price             |
| `new_entry_date` | str    | 가능 | 교체할 actual_entry_date (ISO 8601)       |
| `new_cash`       | number | 가능 | 교체할 shared_cash_actual                 |
| `reason`         | str    | 불가 | 보정 사유 (앱 입력)                       |
| `input_time_kst` | str    | 불가 | 사용자 입력 시각                          |
| `applied_at`     | str    | 불가 | run-daily 반영 시각 (배치 통일)           |

**키 전략**:

- 폴더 키 = `applied_at` 의 날짜 부분 (`YYYY-MM-DD`). fill 은 사용자 체결일 기준이지만 balance_adjust 는 "교체 시점" 기준.
- 레코드 키 = `BalanceAdjust.rtdb_key` (UUID). 본문 페이로드 미포함.

**idempotency**: `applied_balance_adjust_ids.json` 으로 1 차 방어, RTDB set 으로 2 차 방어. 영구 보존.

#### 8.2.13 `/history/signals/{YYYY-MM-DD}/{asset_id}` — 신호 이력 영구 보존

**SoT**: `live.rtdb_gateway.write_history_signals`, `live.models.SignalDetection`. GCS 정본 `history/signals.jsonl` 의 RTDB 미러. daily runner 가 매 실행마다 **당일 4 자산 전체** 를 덮어쓴다 (idempotent).

```json
{
  "state": "buy",
  "close": 82.05,
  "ma_value": 80.0,
  "ma_distance_pct": 0.0256,
  "upper_band": 84.0,
  "lower_band": 76.0
}
```

| 필드              | 타입                        | null | 설명                                         |
| ----------------- | --------------------------- | ---- | -------------------------------------------- |
| `state`           | `"buy"`\|`"sell"`\|`"none"` | 불가 | 당일 감지된 신호 상태                        |
| `close`           | number                      | 불가 | 당일 종가 (**USD**, `ROUND_PRICE = 6` 자리)  |
| `ma_value`        | number                      | 가능 | MA 값 (**USD**, 워밍업 구간 null)            |
| `ma_distance_pct` | number                      | 불가 | MA 근접도 (비율 0~1, `ROUND_RATIO = 4` 자리) |
| `upper_band`      | number                      | 가능 | BufferZone 상단 밴드 (**USD**)               |
| `lower_band`      | number                      | 가능 | BufferZone 하단 밴드 (**USD**)               |

**키 전략 — UUID 없음**:

- 폴더 키 = `execution_date`.
- 레코드 키 = `asset_id` 소문자.
- 서버 결정론적 계산이라 경쟁 조건이 없고, 자산당 하루 1 건이 보장되므로 자연스러운 키. Firebase 콘솔에서 자산명으로 즉시 펼쳐볼 수 있어 가독성 우선.

**보존 정책**: 영구. 4 자산 × 일 1 건 × 252 거래일 / 년 = 1008 레코드 / 년 — Spark 한도 대비 충분.

#### 8.2.14 `/history/` 비미러 항목

다음 두 항목은 **RTDB `/history/` 에 미러하지 않는다**:

- **`fill_dismiss`** (체결 리마인더 스킵): "리마인더 해제" 관리 행위이고 앱에서 사후 조회할 실질 수요가 없기 때문 (GCS 정본 `applied_fill_dismiss_ids.json` + `fill_dismisses.jsonl` 만 유지).
- **`model_sync`** (model 축 동기화 요청): 발생 빈도가 월 0~1 회 수준으로 매우 낮고, 이벤트의 결과(동기화 직전/직후 상태)는 `history/daily/{date}.json` 의 `model_sync_applied` 플래그와 `history/states/{date}.json` 전후 스냅샷 diff 로 이미 추적 가능하기 때문. 별도 JSONL 원장도 두지 않는다.

### 8.3 역할 분리

| 경로                            | 쓰기 주체                                          | 읽기 주체                |
| ------------------------------- | -------------------------------------------------- | ------------------------ | --------------------------------------- | -------------- |
| GCS 정본 버킷                    | daily runner (ephemeral)                           | daily runner             |
| `/latest/*`, `/charts/*`        | daily runner (Admin SDK)                           | 앱                       |
| `/history/{fills                | balance_adjusts                                    | signals}/\*`             | daily runner (Admin SDK, GCS 정본 미러) | 앱 (이력 조회) |
| `/fills/*`, `/balance_adjust/*` | 앱 (레코드 본문) / daily runner (`processed` 필드) | daily runner (Admin SDK) |
| `/fill_dismiss/*`               | 앱 (레코드 본문) / daily runner (`processed` 필드) | daily runner (Admin SDK) |
| `/model_sync/*`                 | 앱 (레코드 본문) / daily runner (`processed` 필드) | daily runner (Admin SDK) |
| `/device_tokens/*`              | 앱 (등록) / daily runner (만료 토큰 삭제)          | daily runner (Admin SDK) |

**`processed` 필드 규칙**: `/fills/inbox/{uuid}` / `/balance_adjust/inbox/{uuid}` / `/fill_dismiss/inbox/{uuid}` / `/model_sync/inbox/{uuid}` 의 `processed` 필드는 **daily runner 만 쓴다**. 앱은 이 필드를 쓰지 않으며, 읽기는 허용한다. 앱은 "미처리 inbox 레코드" 를 필터링할 때 `processed !== true` 조건을 사용할 수 있으며, 실제 사용처는 앱의 `ReminderBlock` 에서 사용자가 이미 체결 / 스킵을 입력한 자산을 리마인더 목록에서 숨기는 용도다. 체결 / 보정 반영 상태는 `/latest/portfolio` 의 `actual_shares` / `model_shares` 변화나 `/latest/pending_orders` 의 소멸로도 확인 가능하며, 두 경로를 보조적으로 병용한다. model_sync 는 `model_shares` 가 `actual_shares` 와 일치하는 것으로 반영 여부를 판단할 수 있다.

**마킹 후 잔존**: 처리 완료 (`processed=true`) 마킹된 inbox 레코드는 RTDB 에서 **삭제되지 않고 잔존**한다. `/history/*` 는 별도 미러이며 inbox 레코드가 이동하는 구조가 아니다. 현재 rolling 정리 로직이 없으므로 운영상 누적된다 (Spark 플랜 + 연간 수천 건 규모까지 허용). 전체 초기화는 `reset` 명령이 네 inbox 경로를 통째 삭제한다.

**실패 처리 계약**: 실패 시 자동 DLQ / 재시도 큐 / per-UUID 결과 채널은 없다. 다음 cron 실행 또는 `workflow_dispatch` 수동 재실행이 재시도를 담당하며, `applied_*_ids.json` 원장과 RTDB `set()` 덮어쓰기가 중복 반영을 방지한다. 반영 실패는 전체 `run-daily` 실패와 동일하게 FCM + 텔레그램 실패 알림 (§6.3) 으로만 전달된다.

**`/history/*` 정본 관계**: GCS 정본 (`history/user_trades.jsonl`, `balance_adjusts.jsonl`, `signals.jsonl`) 이 단일 정본이며 RTDB 는 미러. `reset` 은 GCS 정본 `history/` 와 RTDB `/history/*` 를 같은 워크스페이스에서 초기화한다. 과거 이력은 GCS Soft Delete 30일 보호로 복원 가능하며 (그 이상은 일별 스냅샷 `history/states/{date}.json` 으로 시점 복원), `run-daily` 가 reset 이후 시점부터 다시 누적한다.

---

## 9. 실패 / 예외 대응 (앱 관점)

**원칙: live 는 어떤 단계든 실패하면 즉시 중단 + FCM + 텔레그램 실패 알림 발송 + exit 1.** 자동 복구 / 자동 재시도 (Actions retry job 제외) 는 없다.

앱 측 영향은 다음 두 가지뿐이다.

1. **실패 알림 수신**: 앱은 §6.3 형식의 본문을 FCM / 텔레그램으로 받는다. 추가 조치 없음.
2. **RTDB 데이터 미갱신**: live 가 중단되면 `/latest/*` 와 `/charts/*` 가 그날 업데이트되지 않는다. 앱은 `/latest/portfolio.execution_date` 필드로 최신 여부를 판단한다.

live 내부 예외 시나리오 전체 매트릭스(yfinance / 데이터 검증 / GCS 동기화 / RTDB / fill 검증 / idempotency 등) 는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

### 9.1 스플릿 / 무상증자 수동 대응 절차

스플릿 / 무상증자는 드문 이벤트이고 오탐지 리스크가 있어, live 는 "자동 복구 금지 + 무조건 알림" 원칙에 따라 **감지만 하고 대응은 운영자가 수동으로 수행** 한다. 자동 조정 모듈은 제공하지 않는다 (의도된 선택).

**감지**:

- `data_validator.validate_prev_close` 가 전일 종가 대비 **1% 이상 괴리** 를 감지하면 `ValueError("전일 종가 불일치 (스플릿 의심): ...")` 를 던져 run-daily 가 즉시 중단된다.
- 공통 예외 훅이 FCM + 텔레그램으로 실패 알림을 발송한다.

**확인**:

1. 운영자는 알림을 받고 yfinance 또는 증권사 공시에서 해당 자산의 스플릿 / 무상증자 사실과 비율을 확인한다.
2. 실제 스플릿이면 비율 (예: `2:1`) 을 메모한다.

**수동 보정 절차** (정본 → 캐시 순):

1. **CSV 재다운로드**: `python -m live rebuild-data {TICKER}` — yfinance 에서 조정된 전체 주가를 다시 받아 CSV 를 덮어쓴다 (GCS 정본으로 자동 업로드).
2. **live_state.json 수동 조정**: GCS 콘솔에서 `gs://qbt-live.firebasestorage.app/live_state.json` 을 다운로드 (또는 `gsutil cp gs://qbt-live.firebasestorage.app/live_state.json -`) 한 뒤 영향받은 자산에 대해:
   - `model_shares *= ratio`, `model_avg_entry_price /= ratio`
   - `actual_shares *= ratio`, `actual_avg_entry_price /= ratio`
   - `buffer_zone_state` 내부 가격 필드 (있다면) 도 동일 비율로 조정. BufferZoneStrategy 내부 상태는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 의 직렬화 규약을 따른다.
3. **GCS 재업로드**: 수정한 `live_state.json` 을 `gsutil cp live_state.json gs://qbt-live.firebasestorage.app/live_state.json` 으로 다시 올린다 (덮어쓰기). Soft Delete 30일 보호로 이전 버전은 자동 보관된다.
4. **차트 연도 슬라이스 재생성**: `python -m live backfill-chart-years` 실행 — 주가 차트 `/charts/prices/{asset_id}/years/{YYYY}` 와 equity 차트 `/charts/equity/years/{YYYY}` 를 전체 연도 재생성 / 업로드한다. 기본 동작은 `--target all` (주가 + equity) × years 전체 순회이며, `--target prices|equity` 로 한쪽만, `--year YYYY` 로 단일 연도만, `--dry-run` 으로 사전 확인도 가능.
5. **다음 run-daily 확인**: 다음날 자동 실행 (또는 수동 `run-daily`) 에서 정상 진행을 확인한다.

**history JSONL 은 건드리지 않는다**. `history/signals.jsonl` / `history/user_trades.jsonl` / `history/summary.jsonl` / `history/daily/{date}.json` 은 **과거 사실의 증거** 이며, 날짜 / 금액 기반이라 스플릿 영향이 없다. `history/balance_adjusts.jsonl` 의 append-only 기록이 조정 audit log 역할을 한다.

**backfill-chart-years 는 스플릿/무상증자 대응 시 수동 실행한다** (과거 연도 슬라이스를 새 조정가 기준으로 재생성). daily runner 는 매일 `years/{현재_연도}` 만 덮어쓰므로, 이전 연도는 스플릿 후 값이 재조정된 CSV 를 기준으로 별도 재생성 필요. 최초 배포 및 `reset` 직후에는 `reset` 자체가 주가 차트 (meta + years 전체 연도) 를 자동 재생성하므로 별도 `backfill-chart-years` 실행은 불필요하다.

**`/history/*` 및 equity 차트는 매일 `run-daily` 가 누적**. `reset` 으로 GCS 정본 `history/` 와 RTDB `/history/*` / `/charts/equity/*` 가 모두 초기화된 뒤에는 별도 backfill 명령이 없으며, `run-daily` 가 매일 당일분을 양쪽에 기록한다. 연말에 해가 바뀌면 새 연도의 equity 슬라이스도 자연스럽게 생성된다.

---

## 10. 스케쥴링

live 는 평일 ET 17:27 (cron, `timezone: America/New_York`) 에 GitHub Actions 로 자동 실행된다. 앱이 알아야 할 유일한 의미는 "장 마감 후 매일 한 번 `/latest/*` 데이터가 갱신된다" 는 것이다. cron / keepalive / 재시도 정책 등 상세는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 11. 보안

앱은 Firebase Auth (Email/Password) 로 로그인하며, 인증된 사용자만 RTDB 경로에 접근한다. RTDB Rules 로 `OWNER_UID` 만 읽기/쓰기를 허용한다 (값은 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 인프라 정보 표 참고).

각 RTDB 경로의 접근 권한 설계 (Firebase Console Rules 에 반영):

| 경로                                                                                        | 읽기                     | 쓰기                                |
| ------------------------------------------------------------------------------------------- | ------------------------ | ----------------------------------- |
| `/latest/*`, `/charts/*`, `/history/*`                                                      | `auth.uid === OWNER_UID` | 쓰기 금지 (Admin SDK 는 Rules 우회) |
| `/fills/inbox/*`, `/balance_adjust/inbox/*`, `/fill_dismiss/inbox/*`, `/model_sync/inbox/*` | `auth.uid === OWNER_UID` | `auth.uid === OWNER_UID`            |
| `/device_tokens/{device_id}`                                                                | `auth.uid === OWNER_UID` | `auth.uid === OWNER_UID`            |

- Admin SDK (Service Account) 는 Rules 를 우회한다. 서버 daily runner 의 모든 쓰기는 Rules 와 무관하게 성공한다.
- 앱은 Firebase Auth Email/Password 로 로그인한 `OWNER_UID` 계정으로만 접근한다.
- `/device_tokens/{device_id}` 의 "타 사용자 deviceId 덮어쓰기" 리스크는 `OWNER_UID` 단일 계정 전제하에서 자연 차단된다. 같은 사용자의 기기 간 `device_id` 고유성은 앱이 UUID 등으로 보장한다.

앱에는 **GitHub 토큰이 절대 들어가지 않는다** (GCS 정본 접근은 live 서버 전용). 서버 측 GitHub Secrets / `.env` / PAT / App Check 등 운영 상세는 [src/live/CLAUDE.md](../src/live/CLAUDE.md) 참고.

---

## 12. Drift

drift 는 **model equity 와 actual equity 의 상대 차이** 이다.

```
drift_pct = |model_equity − actual_equity| / model_equity   (내부 비율, 0~1. 0.03 = 3%)
```

QBT 비율 원칙(`_pct` = 0~1)에 따라 내부 계산, GCS 정본(`live_state.json`, `history/*`), RTDB (`/latest/portfolio`) 의 `drift_pct` 는 **모두 0~1 범위의 비율** 로 통일된다. 정밀도는 `ROUND_RATIO = 4` 자리 (예: `0.0350` = 3.5%). 앱이 화면에 `X.XX%` 로 표시할 때 `× 100` 변환은 **앱 계층의 책임** 이다 (서버/데이터 저장 계층에서는 변환하지 않는다). drift 는 RTDB 에 스칼라(`/latest/portfolio.drift_pct`) 형태로만 노출되며 시계열로는 제공하지 않는다 (§8.2.6).

**유일 정본**: `drift.compute_drift(state, closes)` 가 완전 `DriftReport` 를 생성한다.
`daily_runner.run_daily()` 는 내부적으로 이 함수를 호출하여 결과를
`DailyResult.drift_report` 에 채워 반환한다. daily_runner 에 간이 drift 계산은 없다.

**임계값과 recommendation 라벨** (비율 기준, `constants.DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`):

| 비율 구간 (0~1)    | `recommendation` (한글 라벨) | 앱 표시 예 (× 100 변환 후) |
| ------------------ | ---------------------------- | -------------------------- |
| 0 ~ 0.03 (미만)    | `"정상"`                     | `0.00%` ~ `2.99%`          |
| 0.03 ~ 0.05 (미만) | `"주의"`                     | `3.00%` ~ `4.99%`          |
| 0.05 이상          | `"보정 필요"`                | `5.00%` 이상               |

`recommendation` 문자열은 한글 리터럴이며 RTDB 에 저장되지 않는다 (GCS 정본 `history/daily/{date}.json` 및 일일 리포트 알림에만 노출). 앱이 상태 라벨을 자체 렌더링할 경우 저장된 `drift_pct` (0~1 ratio) 를 임계값과 **동일 스케일로 직접 비교** 하면 된다 (별도 스케일 변환 불필요).

**자산별 drift**: `DriftReport.per_asset` 에 `AssetDrift` 리스트로 포함된다.
모델이 0 주인데 실제 보유 중인 경우(`model_value=0, actual_value>0`)
`asset_drift_pct = 1.0` (100% 이탈) 을 반환하여 사용자가 차이를 인지할 수 있다.
일일 리포트 알림 본문에는 전체 `drift_pct` 스칼라 값만 포함되며, **RTDB `/latest/portfolio` 도 per_asset drift 를 포함하지 않는다**. 자산별 상세가 필요하면 앱이 `/latest/portfolio` + `/latest/signals` 로 자체 계산하거나, 운영자가 GCS 정본 `history/daily/{date}.json` 을 조회한다.

---

## 13. 참고

live 서버 내부 구현 / 운영 상세 (모듈 / CLI / 상수 / 실패 처리 / 배포 / 비용) 는 본 설계서의 범위 밖이다. 정본 위치:

- [src/live/CLAUDE.md](../src/live/CLAUDE.md) — live 도메인 규칙·모듈 역할·인프라 정보
- [src/live/](../src/live/) — 코드 SoT

---

## 14. 재설계 결정 (2026-08-30)

§0~§13의 설계(GCS 정본 + Firebase RTDB + Android 앱 + FCM)를 **폐기하고, 상태를 갖지 않는 최소 알림 시스템으로 재설계**하기로 결정했다. 이 절은 그 결정과 근거를 담는다. 구현은 아직 착수하지 않았다.

### 14.1 계기 — 2026-08-26~29 거래일 누락 사고

`daily_run` 워크플로의 cron(`27 22 * * 1-5` = 07:27 KST)이 GitHub 측 사유로 심하게 지연되면서, **2026-08-27 거래일이 어느 실행에서도 처리되지 않았다.**

| 예정(UTC) | 실제 실행(UTC) | 지연 | 실행 시점 NY 날짜 | 결과 |
| --- | --- | --- | --- | --- |
| 08-25 22:27 | 08-25 22:51 | 25분 | 08-25 (화) | 성공 |
| 08-26 22:27 | 08-27 03:24 | 4시간 58분 | 08-26 23:24 (수) | 성공 (37분 차로 세이프) |
| 08-27 22:27 | 08-28 06:11 | **7시간 45분** | **08-28 02:11 (금)** | 실패 |
| 08-28 22:27 | 08-29 03:45 | 5시간 19분 | 08-28 23:45 (금) | 실패 |

**인과**: 워크플로가 `TZ: America/New_York` 을 설정하고 `cli.py` 가 `date.today()` 로 처리 대상 거래일을 정한다. 실행이 자정을 넘기면 대상 날짜가 하루 밀리고, 그 결과 08-27은 처리 기회를 잃었다. 이후 `validate_date_gap` 이 CSV 마지막(08-26)과 대상일(08-28) 사이의 누락을 감지해 중단시켰다. 「보간 금지 / 자동 복구 금지」 원칙상 자동으로는 영원히 풀리지 않는다.

**부수 확인**: job 실행 자체는 55초로 정상이었다. 문제는 **cron 트리거 발화 지연**이며, 큐 대기(created_at → started_at)는 3초였다. 즉 GitHub Actions 의 실행 능력이 아니라 스케줄러의 best-effort 특성이 원인이다.

### 14.2 실측 — 알림 발송 시각 분포

텔레그램 로그 3개월치(2026-06-02 ~ 08-27, 정상 리포트 61건)를 파싱한 결과다. cron 은 이 기간 내내 07:27 KST 로 동일했다.

| 통계 | 발송 시각(KST) | 예정 대비 지연 |
| --- | --- | --- |
| 최소 | 07:46 | 19분 |
| **중앙값** | **08:31** | **64분** |
| 75% | 08:48 | 81분 |
| 최대 | 12:25 | 4시간 58분 |

월별로는 6월 중앙 1시간 23분 → 7월 1시간 1분 → 8월 37분으로 개선 추세였다. **평상시에도 1시간 안팎 지연되는 것이 정상 상태였다**는 점이 중요하다. 최근 며칠만 보면 20분대로 보여 오판하기 쉽다.

판단 시각별로 "그때까지 알림이 안 온 정상 건"의 비율:

| 판단 시각 | 아직 안 온 건 | 비율 |
| --- | --- | --- |
| 08:30 | 31/61 | 50.8% |
| 08:45 | 16/61 | 26.2% |
| 09:00 | 6/61 | 9.8% |
| 13:00 | 0/61 | **0.0%** |

### 14.3 결정 사항

**① 알림 내용을 MA 근접도만으로 축소한다.**

현재 알림은 model/actual equity, drift, 미입력 체결 리마인더, 시그널, 리밸런싱, MA 근접도를 담는다. 이 중 **MA 근접도만 남긴다.**

```
MA 근접도: SPY +11.56%, QQQ +19.38%, GLD +2.46%, TLT -0.98%
```

**이 결정이 사고의 근원을 제거한다.** MA 근접도는 종가와 이동평균만으로 계산되며 **누적 상태가 없다.** 따라서 `live_state.json`, GCS 정본, `validate_date_gap` 이 모두 불필요해지고, **실행이 하루 누락되거나 8시간 지연돼도 피해가 없다.** 다음 날 오면 그만이다.

**② 계산은 알림 프로젝트가 직접 수행한다 (quant 의존 없음).**

SMA 전환(부록 G) 덕분에 가능해졌다. EMA 는 재귀식이라 quant 와 동일한 값을 내려면 전체 히스토리가 필요했지만, **SMA 는 최근 1년치만 받아도 누가 계산하든 같은 값**이 나온다. 알림 프로젝트는 티커 목록과 MA 기간(200)만 알면 되고, `rolling(200).mean()` 한 줄로 끝난다.

**③ 발송은 텔레그램만. FCM 과 앱을 폐기한다.**

FCM 을 제거하면 `firebase_admin` 의존성, 서비스 계정 JSON, `GOOGLE_APPLICATION_CREDENTIALS`, `secrets/` 생성 스텝이 전부 사라진다. 시크릿이 텔레그램 토큰 2개로 줄어 Claude Routine 에서 다루기도 쉬워진다.

**④ 별도 프라이빗 리포로 분리한다.**

verify-lab 이 곧 시그널을 내므로 알림 소스가 둘 이상이 된다. 알림 프로젝트의 값어치는 발송 자체가 아니라 **여러 프로젝트의 스케줄과 감시를 한곳에 모으는 것**이다.

프라이빗 리포로 만드는 실익:
- quant 는 퍼블릭이라 시크릿 취급이 조심스러운데, 프라이빗이면 자유롭다
- **60일 무활동 자동 정지는 퍼블릭 리포 규칙이므로 keepalive 워크플로가 불필요해진다**
- Actions 무료 분수(월 2,000분)는 하루 1분이면 충분하다

**⑤ 발송과 감시의 축을 분리한다.**

| 역할 | 담당 | 시각(KST) | 동작 |
| --- | --- | --- | --- |
| 발송 | GitHub Actions cron | 07:27 (실제 도착 ~08:30) | MA 근접도 계산 → 텔레그램 |
| 감시 겸 백업 | **Claude Code Routine** | **08:45** | 오늘 발송 성공 여부 확인 → 미발송이면 `workflow_dispatch` 트리거 |

**Claude 가 텔레그램 토큰을 갖지 않는다**는 점이 이 구조의 이점이다. Claude 는 GitHub 만 건드리고, 토큰은 GitHub Secrets 에만 남는다.

축 분리가 유효한 이유: 이번 사고의 실패 지점은 **cron 발화 지연**이지 GitHub 실행 능력이 아니었다(job 55초). 따라서 Claude 가 트리거하면 실행은 즉시 된다.

**⑥ 중복 발송은 시각 컷오프로 막는다 — 공유 DB 불필요.**

GitHub Actions 실행 이력 자체가 이미 공유 상태다. Claude 는 API 로 오늘 실행 결과를 읽을 수 있다. 반대 방향(GitHub 이 Claude 결과를 읽기)은 어렵지만, **GitHub 이 먼저 돌기 때문에 확인할 것이 없다.**

남는 경우는 "GitHub 이 심하게 밀려 Claude 보다 늦게 도착"뿐이며, 워크플로에 컷오프를 넣어 막는다.

> 지금이 **08:40 KST 를 넘었으면 발송하지 않고 종료한다.**

| 상황 | GitHub | Claude 08:45 | 발송 |
| --- | --- | --- | --- |
| 정상 (08:00 도착) | 발송 | 성공 확인 → 안 함 | 1건 |
| 지연 (09:30 발화) | **컷오프로 skip** | 미발송 판단 → dispatch | 1건 |
| 미실행 | — | dispatch | 1건 |
| 실행됐으나 실패 | 실패 | 미발송 판단 → dispatch | 1건 |

**[구현 필수] 컷오프는 `github.event_name == 'schedule'` 일 때만 적용한다.** Claude 가 보내는 `workflow_dispatch` 는 08:45 에 도착하므로, 이 구분이 없으면 자기 컷오프에 걸려 아무것도 하지 않는다.

**추가 주의**: 컷오프로 skip 한 실행도 GitHub 상으로는 "성공"으로 끝난다. 따라서 Claude 는 성공 여부만 보면 안 되고 **실행 시각까지 확인**해야 한다 — 08:40 이후에 시작된 실행은 skip 된 것으로 판단한다.

### 14.4 폐기 대상

| 대상 | 규모 | 사유 |
| --- | --- | --- |
| `rtdb_gateway.py` | 685줄 | 앱 폐기로 RTDB 불필요 |
| `chart_data.py` | 607줄 | 차트 폐기 |
| `daily_runner.py` | 551줄 대부분 | 포트폴리오 엔진 호출 불필요 |
| `state.py` | 499줄 | 보유수량·평단 원장 불필요 |
| `storage_gateway.py` · `history.py` · `drift.py` · `balance_adjust.py` · `buffer_serializer.py` | 980+줄 | 상태가 없어져 전부 불필요 |
| `data_validator.py` 대부분 | 152줄 | `validate_date_gap` 은 개념 자체가 사라짐 |
| Firebase 프로젝트 | — | FCM·RTDB·GCS 모두 미사용 |
| `keepalive.yml` | — | 프라이빗 리포는 60일 규칙 대상 아님 |

`src/live/` 5,958줄 중 **남길 것은 150~200줄 안팎**이다.

### 14.5 채택하지 않은 안

| 안 | 기각 사유 |
| --- | --- |
| **healthchecks.io 등 dead man's switch** | 상태가 없어지면 "안 왔다"의 피해가 사라져 침묵 감지의 값어치가 급감한다. Claude Routine 이 같은 역할을 겸한다 |
| **Claude 가 MA 를 직접 추론 계산** | 200일 이동평균을 LLM 추론으로 매일 계산하면 백테스트와 다른 값이 나올 수 있고 틀려도 티가 안 난다. Routine 이 리포를 클론해 **스크립트를 실행**하는 방식이면 이 문제가 없다 |
| **Claude 가 텔레그램으로 직접 발송** | 토큰을 Anthropic 인프라에 추가로 두게 된다. GitHub 트리거 방식이면 불필요 |
| **공유 DB(Firebase/Sheets)로 중복 방지** | 상태를 없애려는 목적과 모순. 시각 컷오프로 해결된다 |
| **cron 을 더 앞당기기** | 미국 서머타임 때문에 겨울(EST) 장 마감이 21:00 UTC 다. 여유가 줄어 겨울에 깨진다 |
| **자동 재시도 (실패한 실행 재실행)** | `src/live/CLAUDE.md` 「자동 복구 금지」 위반. 데이터 검증 실패는 재시도해도 같은 자리에서 실패한다. **"실행이 없음"과 "실행됐으나 실패"는 다르게 다뤄야 한다** |

### 14.6 미해결 사항

- **알림 프로젝트 리포 신설** — 이름, 위치, verify-lab 시그널을 어떤 형태로 받을지 미정
- **Claude Code Routine 설정** — GitHub 커넥터 권한 범위, 트리거용 인증 방식
- **기존 GCS/Firebase 자원 정리 시점** — 재설계 완료 후 삭제
- **현재 `daily_run`·`keepalive` 워크플로는 2026-08-29 수동 중지 상태**다. 재개하려면 정본 CSV 의 거래일 공백(2026-08-27·08-28)을 먼저 해소해야 하나, 재설계 후에는 CSV 자체가 불필요해진다
