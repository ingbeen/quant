# live 도메인 가이드

> CRITICAL: live 도메인 작업 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.
> 이 문서가 live 도메인의 **현행 규칙 / 아키텍처 SoT** 입니다.
> 구체 함수 시그니처 / dataclass 정의는 `live/src/live/` 하위 코드가 SoT 입니다.

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
│   ├── buffer_serializer.py # BufferZoneStrategy 직렬화 어댑터 (extract/restore)
│   ├── rtdb_gateway.py     # Firebase RTDB 게이트웨이
│   ├── notifier.py         # FCM + 텔레그램 동시 발송
│   ├── chart_data.py       # TradingView Lightweight Charts 시계열
│   ├── history.py          # 영구 히스토리 저장
│   └── cli.py              # CLI 엔트리포인트
└── tests/
    ├── __init__.py
    ├── conftest.py         # 공통 픽스처 (mock Firebase / yfinance 등)
    └── test_*.py           # 모듈별 단위/통합 테스트
```

## 모듈별 역할 요약

> 각 모듈의 공개 API / 내부 단계는 코드가 SSoT 이다. 아래 표는 "한 줄 책임" 만 담는다.

| 모듈                   | 역할                                                                                |
| ---------------------- | ----------------------------------------------------------------------------------- |
| `constants.py`         | 도메인 공통 상수 / 경로 / 환경변수 키 / 임계값 / 헬퍼 함수                          |
| `models.py`            | dataclass / TypedDict / Literal 타입 정의 (QBT 본체 타입 재노출 포함)               |
| `state.py`             | `LiveState` JSON 직렬화/역직렬화 및 `applied_*_ids` 원장 관리                       |
| `data_fetcher.py`      | yfinance OHLC 수집 및 CSV 누적/재다운로드                                           |
| `data_validator.py`    | OHLC / 전일 종가 / 거래일 gap 검증 (순수 함수)                                      |
| `daily_runner.py`      | 순수 계산 `run_daily` (파일 I/O 없음, QBT 포트폴리오 엔진 1 일치 호출)              |
| `drift.py`             | fill 분류 + idempotent 반영 + `compute_drift` 정본                                  |
| `balance_adjust.py`    | `BalanceAdjust` idempotent 반영 (`run_daily` 내부 fills 직후 호출)                  |
| `buffer_serializer.py` | `BufferZoneStrategy` 내부 상태 추출/복원 어댑터 (QBT 본체 수정 없음)                |
| `rtdb_gateway.py`      | Firebase Admin SDK 초기화 및 RTDB 읽기/쓰기 게이트웨이                              |
| `notifier.py`          | FCM + 텔레그램 동시 발송 (발송 실패는 로그만)                                       |
| `chart_data.py`        | 자산별 전체 기간 차트 시계열 생성                                                   |
| `history.py`           | Git 정본 히스토리 append / load                                                     |
| `git_state.py`         | ephemeral shallow clone / commit / push 헬퍼                                        |
| `cli.py`               | CLI 엔트리포인트, 휴장 체크, ephemeral 컨텍스트, `main()` 공통 알림 훅              |

## 핵심 원칙

### 1. 장애 시 자동 복구 금지 + 무조건 알림

- 데이터 수집/검증/계산/RTDB/Git push 중 어떤 단계든 실패하면 **즉시 중단** 한다.
- 자동 롤백, 자동 재시도(GitHub Actions retry job 제외), 자동 복원 **모두 금지**.
- `cli.py` 의 `main()` 공통 예외 훅이 모든 커맨드의 예외에 대해
  `_safe_notify_failure` 를 호출하여 FCM + 텔레그램으로 실패 알림을 발송한다.
  - 예외: `notify-failure` 커맨드 자체는 재귀 방지를 위해 알림을 다시 발송하지 않는다.
- **알림 채널 자체의 실패는 로그로만 기록한다**. FCM / 텔레그램 발송이 실패한
  상황에서 다시 알림을 보내는 것은 모순 / 무한 루프이므로 금지.
- 에러 알림 본문에는 실패 원인(커맨드 이름 + 예외 메시지) 을 반드시 포함.

### 2. model / actual 분리

- `LiveState` 에서 `model_*` 와 `actual_*` 필드는 명시적으로 분리.
- model 체결은 actual 을 덮어쓰지 않는다.
- actual 은 RTDB 로 들어오는 체결 입력(`fills/inbox/`) 또는 직접 보정
  (`balance_adjust/inbox/`) 으로만 갱신된다.
- drift 계산은 `drift.compute_drift` 가 유일 정본이며, 임계값은
  `DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO` 를 따른다.

### 3. 순수 계산 / I/O 분리

- `daily_runner.run_daily()` 는 파일 I/O / 네트워크 호출이 없다.
- 모든 입력(`pending_fills`, `pending_adjusts`, `applied_*_ids` 등) 은 파라미터로
  받고, 결과는 `DailyResult` 로 반환한다.
- `run_daily` 내부 적용 순서: **fills 먼저 → balance_adjust 나중**. 사용자 직접
  보정이 fill 이후의 최종 잔고를 덮어쓴다.
- 회귀 검증(`test_regression.py`) 가능하도록 결정적(deterministic) 이어야 한다.

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
- 회귀 검증(`test_regression.py`): `run_daily()` 를 과거 구간에 대해 순차 호출하여
  `run_portfolio_backtest()` 와 비교. 매일 equity / positions / cash 가 일치해야 한다.

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
# 초기 1회 (원격 qbt-live-state 리포에 초기 상태 push)
poetry run python -m live.cli init --capital 100000000
poetry run python -m live.cli init-data

# 매일 (GitHub Actions 가 자동 실행, 로컬에서 수동 실행도 가능)
poetry run python -m live.cli run-daily

# 디버깅 / 조회
poetry run python -m live.cli drift
poetry run python -m live.cli history --tail 20
poetry run python -m live.cli fetch-fills
poetry run python -m live.cli notify-failure -m "수동 테스트"
```

**ephemeral state repo**: CLI 는 state 가 필요한 모든 명령에 대해 매 실행마다 `qbt-live-state` 프라이빗 리포를 임시 디렉토리에 `--depth 1` shallow clone 하고, 작업 후 변경사항을 자동 commit/push 한 뒤 임시 디렉토리를 삭제합니다. **로컬과 GitHub Actions 가 동일한 코드 경로**를 타므로 두 환경의 실행 결과는 항상 같은 원격 커밋으로 수렴합니다. 프로젝트 폴더에는 어떤 state 파일도 남지 않습니다.

**환경변수**: 로컬 실행 시 프로젝트 루트의 `.env` 파일이 자동 로드됩니다 (`python-dotenv`). 필요한 변수:

- `STATE_REPO_PAT` — `qbt-live-state` 리포에 clone/push 할 GitHub Personal Access Token
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — 알림 발송용
- `GOOGLE_APPLICATION_CREDENTIALS` — Firebase service account JSON 절대 경로

이미 `os.environ` 에 값이 있으면 `.env` 가 덮어쓰지 않으므로 GitHub Actions 의 `env:` 블록이 항상 우선됩니다.

## 인프라 정보

| 항목                 | 값                                                                   |
| -------------------- | -------------------------------------------------------------------- |
| QBT 리포 (퍼블릭)    | `https://github.com/ingbeen/quant`                                   |
| 상태 리포 (프라이빗) | `https://github.com/ingbeen/qbt-live-state.git`                      |
| Firebase 프로젝트    | `qbt-live` (Spark)                                                   |
| RTDB URL             | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지       | `com.ingbeen.qbtlive`                                                |
| OWNER_UID            | `SxwvCeg6fRUeUrK9IpyazTzrLJJ2`                                       |
| 텔레그램 봇          | `@qbt_live_alert_bot`                                                |

## 참고 문서

- [docs/plans/](../docs/plans/): 변경 계획서 (plan) 저장소
- [live/src/live/models.py](src/live/models.py): 데이터 모델 SoT
- [live/src/live/cli.py](src/live/cli.py): CLI 엔트리 및 `main()` 공통 알림 훅
- [live/src/live/daily_runner.py](src/live/daily_runner.py): 순수 계산 `run_daily` SoT
