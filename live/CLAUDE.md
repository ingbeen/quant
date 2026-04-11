# live 도메인 가이드

> CRITICAL: live 도메인 작업 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.
> 설계서: [docs/DESIGN_QBT_LIVE_FINAL.md](../docs/DESIGN_QBT_LIVE_FINAL.md)
> 구현 체크리스트: [docs/TODO_QBT_LIVE.md](../docs/TODO_QBT_LIVE.md)

## 폴더 목적

`live/` 는 QBT 포트폴리오 전략의 **실매매 알림 시스템** 을 담당하는 신규 도메인입니다.
GitHub Actions 에서 매일 장 마감 후 실행되어 주가 수집 → 시그널 감지 → FCM/텔레그램 알림을 수행하며,
Android 앱에서 포트폴리오 확인 / 차트 / 체결 입력 인터페이스를 제공합니다.

## QBT 본체 수정 원칙

- 원칙: **QBT 본체(`src/qbt/`) 코드는 절대 수정 금지**. 모든 live 작업은 `live/` 내부에서만 수행한다.
- 예외: **사용자 승인이 명시적으로 있을 경우에만** QBT 본체 수정 가능.
  - 수정 전 반드시 사용자에게 수정 범위/이유를 설명하고 승인 요청.
  - 승인 없이 임의로 QBT 본체를 변경하지 않는다.
- QBT 코어(전략/엔진/리밸런싱/체결) 는 live 에서 **import 만 하여 재사용**한다.
  - 예: `from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy`

## 폴더 구조

```
live/
├── CLAUDE.md               # 이 문서
├── src/live/               # 실매매 코드
│   ├── __init__.py
│   ├── constants.py        # 티커, 임계값, 경로 상수
│   ├── models.py           # dataclass / TypedDict
│   ├── state.py            # LiveState 직렬화
│   ├── data_fetcher.py     # yfinance → CSV 누적
│   ├── data_validator.py   # OHLC / 종가 연속성 / 날짜 누락 검증
│   ├── daily_runner.py     # run_daily (순수 계산)
│   ├── drift.py            # fill 자동 매칭 + drift
│   ├── rtdb_gateway.py     # Firebase RTDB 게이트웨이
│   ├── notifier.py         # FCM + 텔레그램 동시 발송
│   ├── chart_data.py       # TradingView Lightweight Charts 시계열
│   ├── history.py          # 영구 히스토리 저장
│   └── cli.py              # CLI 엔트리포인트
└── tests/
    ├── __init__.py
    ├── conftest.py         # 공통 픽스처 (mock Firebase / yfinance 등)
    └── test_*.py           # 각 Step 에서 해당 모듈과 함께 추가
```

## 모듈별 역할 요약

| 모듈 | 역할 | 관련 설계서 |
|------|------|-------------|
| `constants.py` | 티커 목록, SIGNAL_TRADE_MAP, DRIFT 임계값 등 상수 | 5.1, 부록 B |
| `models.py` | `LiveState`, `DailyResult`, `ActualFill`, `ChartSeries`, `DriftReport` 등 데이터 모델 | 부록 B |
| `state.py` | `LiveState` JSON 직렬화/역직렬화, 초기화, applied_fill_ids 관리 | 5장, 부록 A |
| `data_fetcher.py` | yfinance 호출, CSV 누적 append, 전체 재다운로드 | 2장, 부록 A |
| `data_validator.py` | 설계서 3장의 3가지 검증 (OHLC / 종가 / 날짜 누락) | 3장, 부록 A |
| `daily_runner.py` | 순수 계산 기반 `run_daily` (파일 I/O 금지) | 4.2, 부록 A |
| `drift.py` | fill → system_fill / personal_trade 분류, idempotency, drift 계산 | 6장, 14장, 부록 A |
| `rtdb_gateway.py` | Firebase Admin SDK 초기화 및 RTDB 읽기/쓰기 | 10장, 부록 A |
| `notifier.py` | FCM + 텔레그램 동시 발송 (일일 리포트, 에러, 리마인더) | 8장, 부록 A |
| `chart_data.py` | 자산별 전체 기간 차트 시계열 생성 | 7장, 부록 A |
| `history.py` | Git 정본 히스토리 저장 (영구 보존) | 10.1 |
| `cli.py` | `run-daily`, `init`, `init-data`, `notify-failure` 등 명령어 | 부록 A |

## 핵심 원칙

### 1. 장애 시 자동 복구 금지

- 데이터 수집/검증/계산/RTDB/Git push 중 어떤 단계든 실패하면 **즉시 중단** 하고 알림만 보낸다.
- 자동 롤백, 자동 재시도(GitHub Actions retry job 제외), 자동 복원 **모두 금지**.
- 사용자가 상황을 직접 파악하여 디버깅할 수 있도록 한다.
- 에러 알림에는 **에러 상세 메시지(stack trace 포함 가능)** 를 반드시 포함.

### 2. model / actual 분리

- `LiveState` 에서 `model_*` 와 `actual_*` 필드는 명시적으로 분리.
- model 체결은 actual 을 덮어쓰지 않는다.
- actual 은 RTDB 로 들어오는 체결 입력(`fills/inbox/`) 으로만 갱신된다.
- drift 계산은 `(model_equity - actual_equity) / model_equity * 100` 의 절대값.

### 3. 순수 계산 / I/O 분리

- `daily_runner.run_daily()` 는 파일 I/O / 네트워크 호출이 없다.
- 모든 입력은 파라미터로 받고, 결과는 `DailyResult` 로 반환.
- 회귀 검증(Step 9) 가능하도록 결정적(deterministic) 이어야 한다.

### 4. 백테스트 절대 규칙 보존

QBT 백테스트의 절대 규칙은 live 에서도 **예외 없이 동일**하게 적용된다.

- 신호(i일 종가) / 체결(i+1일 시가) 분리
- `SLIPPAGE_RATE = 0.003` (매수/매도 각 0.3%)
- `equity = cash + sum(shares * close)`, 강제 청산 없음
- Pending Order 단일 슬롯, 충돌 시 `PendingOrderConflictError`
- hold_days 상태머신 (Lookahead 금지)
- SSO/QLD: signal 은 SPY/QQQ, trade 는 SSO/QLD (비대칭)

## 코딩 규칙

루트 [CLAUDE.md](../CLAUDE.md)의 "코딩 표준" 섹션과 동일하게 적용한다. 핵심만 재확인:

- 타입 힌트 필수, `str | None` 문법 사용 (Optional 금지)
- `pathlib.Path` 사용 (문자열 경로 금지)
- 비율은 0~1 소수 (0.03 = 3%)
- 로깅: INFO 금지. DEBUG / WARNING / ERROR 만 사용
- 이모지 금지, 한글 메시지
- 네이밍: 함수/변수 snake_case, 클래스 PascalCase, 상수 UPPER_SNAKE_CASE
- 내부 불변조건 위반 → `RuntimeError("내부 불변조건 위반 ...")`
- 입력 검증 실패 → `ValueError`
- CLI 계층(`cli.py`) 만 ERROR 로그 사용 가능. 비즈니스 로직은 예외 전파만.

## 테스트 원칙

테스트 작성 규칙은 [tests/CLAUDE.md](../tests/CLAUDE.md) 를 그대로 따르며, live 만의 추가 규칙:

- **외부 네트워크 호출 금지**: Firebase Admin SDK, yfinance, 텔레그램 Bot API 는 **항상 mock**.
- **파일 I/O 격리**: `tmp_path` 또는 monkeypatch 로 qbt-live-state 디렉토리 경로 격리.
- **결정적**: `@freeze_time` 으로 날짜 고정, RTDB mock 응답 고정.
- Given-When-Then 패턴, `pytest.approx()` 로 부동소수점 비교.
- 회귀 검증(`test_regression.py`, Step 9) 은 `run_daily()` 를 과거 1년 순차 호출하여 `run_portfolio_backtest()` 와 비교: 매일 equity / positions / cash 가 일치해야 한다 (`pytest.approx(abs=1.0)`).

## 의존성 설치

live 는 외부 서비스 (Firebase, 텔레그램, exchange calendars) 에 의존하므로 별도 extras 로 분리되어 있다.

```bash
poetry install -E live
```

이 명령으로 다음이 설치된다:

- `firebase-admin`: Firebase Admin SDK (RTDB / FCM)
- `exchange-calendars`: NYSE 영업일 달력
- `requests`: 텔레그램 Bot API 호출

## 실행 방법

```bash
# 초기 1회
poetry run python -m live.cli init --capital 100000000
poetry run python -m live.cli init-data

# 매일 (GitHub Actions)
poetry run python -m live.cli run-daily
```

## 인프라 정보

| 항목 | 값 |
|------|---|
| QBT 리포 (퍼블릭) | `https://github.com/ingbeen/quant` |
| 상태 리포 (프라이빗) | `https://github.com/ingbeen/qbt-live-state.git` |
| Firebase 프로젝트 | `qbt-live` (Spark) |
| RTDB URL | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지 | `com.ingbeen.qbtlive` |
| OWNER_UID | `SxwvCeg6fRUeUrK9IpyazTzrLJJ2` |
| 텔레그램 봇 | `@qbt_live_alert_bot` |

## 참고 문서

- [docs/DESIGN_QBT_LIVE_FINAL.md](../docs/DESIGN_QBT_LIVE_FINAL.md): 전체 설계서 (반드시 정독)
- [docs/TODO_QBT_LIVE.md](../docs/TODO_QBT_LIVE.md): Step 별 체크리스트
- [docs/PROMPT_QBT_LIVE.md](../docs/PROMPT_QBT_LIVE.md): 구현 지시서
