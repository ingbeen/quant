# QBT Live 구현 TODO

> **필독**: 구현 전 반드시 `DESIGN_QBT_LIVE_FINAL.md` 설계서를 전체 정독할 것.
> 문서 경로: `/home/yblee/workspace/quant/docs/`

---

## 인프라 정보 (사전 준비 완료)

| 항목 | 값 |
|------|---|
| QBT 리포 (퍼블릭) | `https://github.com/ingbeen/quant` |
| 상태 리포 (프라이빗) | `https://github.com/ingbeen/qbt-live-state.git` |
| Firebase 프로젝트 | `qbt-live` (Spark) |
| RTDB URL | `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Android 패키지 | `com.ingbeen.qbtlive` |
| OWNER_UID | `SxwvCeg6fRUeUrK9IpyazTzrLJJ2` |
| 텔레그램 봇 | `@qbt_live_alert_bot` |
| GitHub Secrets | `FIREBASE_CONFIG`, `STATE_REPO_PAT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

---

## 공통 규칙

```
1. QBT 본체(src/qbt/)는 절대 수정 금지. live/ 안에서만 작업.
2. CLAUDE.md 코딩 규칙 준수.
3. 테스트: Given-When-Then. mock 사용. 외부 네트워크 호출 금지.
4. 장애 시 자동 복구/롤백 금지. 즉시 중단 + 에러 상세 포함 알림.
5. 한 Step 완료 시 체크박스 체크.
6. 다음 Step 전에 기존 테스트 전체 통과 확인.

🤖 = AI(Claude Code)가 수행
👤 = 사용자가 직접 수행
```

---

## Phase 0: 사전 준비 ✅ 완료

- [x] 👤 GitHub 프라이빗 리포: `ingbeen/qbt-live-state`
- [x] 👤 Firebase 프로젝트: `qbt-live` (Spark, Auth, RTDB)
- [x] 👤 Firebase 서비스 계정 키 다운로드
- [x] 👤 Android 앱 등록: `com.ingbeen.qbtlive`, `google-services.json`
- [x] 👤 텔레그램 봇: `@qbt_live_alert_bot`
- [x] 👤 GitHub Secrets 4개 등록
- [x] 👤 Firebase Auth 계정 + UID + RTDB Rules 배포

---

## Phase 1: 엔진 코어

### Step 1: 폴더 구조 생성 🤖

```
설계서: DESIGN_QBT_LIVE_FINAL.md > 1.3

live/src/live/ 및 live/tests/ 전체 구조 생성.
빈 파일 + docstring만. 구현은 하지 않음.
pyproject.toml에 live extras 추가.
CLAUDE.md 업데이트.
```

- [x] 🤖 `live/src/live/` 전체 파일 생성
- [x] 🤖 `live/tests/` 전체 파일 생성
- [x] 🤖 `pyproject.toml` live extras 추가
- [x] 🤖 CLAUDE.md 업데이트 (루트 + `live/CLAUDE.md` 신설)
- [x] 🤖 `poetry lock` 및 `poetry install -E live` 정상 확인

---

### Step 2: 데이터 모델 + 상수 🤖

```
설계서: 부록 B, 5.1

constants.py: LIVE_TICKERS, SIGNAL_TRADE_MAP, DRIFT 임계값
models.py: 설계서 부록 B 전체 dataclass
```

- [x] 🤖 `constants.py` 구현
- [x] 🤖 `models.py` 전체 dataclass 구현
- [x] 🤖 PendingOrderDict에 execute_on 없음 확인
- [x] 🤖 model/actual 필드 분리 확인

---

### Step 3: 상태 직렬화 (state.py) 🤖

```
설계서: 5장

load_state, save_state, create_initial_state,
load_applied_fill_ids, save_applied_fill_ids, cleanup_old_fill_ids
```

- [x] 🤖 `state.py` 구현
- [x] 🤖 `test_state.py` 작성 및 통과

**테스트 시나리오 (🤖 AI 실행):**

```
[T-3.1] create_initial_state(100_000_000) -> save -> load -> 원본과 일치
[T-3.2] 설계서 부록 예시 JSON 파일 -> load -> 필드 검증
[T-3.3] applied_fill_ids 저장/로드 왕복
[T-3.4] cleanup_old_fill_ids: 90일 초과 ID 제거, 최근 ID 유지
[T-3.5] 존재하지 않는 파일 load -> 적절한 에러
```

---

### Step 4: BufferZoneStrategy 직렬화 🤖

```
설계서: 4.3

extract_buffer_state, restore_buffer_state
QBT BufferZoneStrategy import. QBT 수정 금지.
```

- [x] 🤖 `extract_buffer_state` 구현
- [x] 🤖 `restore_buffer_state` 구현
- [x] 🤖 테스트 통과

**테스트 시나리오 (🤖):**

```
[T-4.1] hold_state 없는 전략 -> extract -> restore -> 원본과 일치
[T-4.2] hold_state 있는 전략 -> extract -> restore -> 원본과 일치
[T-4.3] 모든 private 변수 왕복 검증 (prev_upper, prev_lower 등)
```

---

### Step 5: 데이터 수집 + CSV (data_fetcher.py) 🤖

```
설계서: 2장

fetch_recent_ohlc, append_today_to_csv, rebuild_full_csv, load_csv
```

- [x] 🤖 `data_fetcher.py` 구현
- [x] 🤖 테스트 통과

**테스트 시나리오 (🤖, mock yfinance):**

```
[T-5.1] CSV에 3행 있을 때 append -> 4행
[T-5.2] 이미 같은 날짜 있을 때 append -> 행수 변화 없음 (중복 방지)
[T-5.3] load_csv -> QBT 본체 CSV 형식과 호환
[T-5.4] 빈 CSV에 append -> 정상 동작
```

---

### Step 6: 데이터 검증 (data_validator.py) 🤖

```
설계서: 3장. 3개만 구현.
```

- [x] 🤖 `data_validator.py` 구현
- [x] 🤖 `test_data_validator.py` 통과

**테스트 시나리오 (🤖):**

```
[T-6.1] 정상 OHLC -> 에러 없음
[T-6.2] High < Low -> 에러 반환
[T-6.3] Close = 0 -> 에러 반환
[T-6.4] Close = -5 -> 에러 반환
[T-6.5] CSV Close 580 vs yfinance Close 290 (50% 차이) -> 에러
[T-6.6] CSV Close 580 vs yfinance Close 579.5 (0.09%) -> 에러 없음
[T-6.7] 날짜 연속 (금->월, 휴장 포함) -> 에러 없음
[T-6.8] 거래일 누락 -> 에러 반환
```

---

### Step 7: 일일 실행 메인 (daily_runner.py) 🤖

```
설계서: 4.2

run_daily() 구현. QBT 코어 import. I/O 없음.
```

- [x] 🤖 `run_daily` 구현
- [x] 🤖 QBT 코어 import 정상
- [x] 🤖 `test_daily_runner.py` 통과

**테스트 시나리오 (🤖):**

```
[T-7.1] 초기 상태 + 1일 데이터 -> DailyResult 정상 반환
[T-7.2] pending 없는 날 -> model 변경 없음
[T-7.3] signal 발생 시 -> pending_order 생성 확인
[T-7.4] pending 있는 상태에서 다음 날 실행 -> model 체결 확인
[T-7.5] run_daily 내부에서 파일 I/O 없음 확인
```

---

### Step 8: fill 자동 매칭 + drift (drift.py) 🤖

```
설계서: 6장
```

- [x] 🤖 `drift.py` 구현
- [x] 🤖 `test_drift.py` 통과

**테스트 시나리오 (🤖):**

```
[T-8.1] classify_fill: SSO pending(매수) + SSO 매수 fill -> system_fill
[T-8.2] classify_fill: SSO pending(매수) + QLD 매도 fill -> personal_trade
[T-8.3] classify_fill: pending 없음 + GLD 매수 fill -> personal_trade
[T-8.4] apply_fills_idempotent: 새 fill 반영 -> actual 변경
[T-8.5] apply_fills_idempotent: 같은 fill 두 번 -> 한 번만 반영
[T-8.6] compute_drift: model=actual -> drift 0%
[T-8.7] compute_drift: model≠actual -> 올바른 % 계산
[T-8.8] compute_drift: 5% 초과 -> recommendation "보정 필요"
```

---

### Step 9: 회귀 검증 🤖

```
설계서: 4.4

과거 1년 run_daily() vs run_portfolio_backtest()
equity/positions/cash 일치 (pytest.approx(abs=1.0))
```

- [x] 🤖 `test_regression.py` 구현
- [x] 🤖 **회귀 검증 통과**

**테스트 시나리오 (🤖):**

```
[T-9.1] 과거 1년 구간: 매일 equity 차이 < 1원
[T-9.2] 과거 1년 구간: 매일 positions 정수 일치
[T-9.3] 과거 1년 구간: 매일 cash 차이 < 1원
```

---

### Step 10: CLI (cli.py) 🤖

```
설계서: 부록 A

명령어: run-daily, init, init-data, rebuild-data,
       fetch-state, push-state, fetch-fills, history, drift, notify-failure

프라이빗 리포: https://github.com/ingbeen/qbt-live-state.git
```

- [x] 🤖 `cli.py` 전체 명령어 구현 (Step 11~15 미완성 명령은 placeholder)
- [x] 🤖 에러 발생 시 자동 복구 없이 즉시 중단 + 알림 발송 확인

**테스트 시나리오 (🤖):**

```
[T-10.1] init --capital 100000000 -> live_state.json 생성, 4자산 초기화
[T-10.2] run-daily 에서 데이터 검증 실패 -> 중단 + 알림 호출
[T-10.3] run-daily 에서 계산 실패 -> 중단 + 알림 호출, 상태 변경 없음
```

**수동 테스트 (👤):**

```
[M-10.1] 👤 poetry run python -m live.cli init --capital 100000000 실행
[M-10.2] 👤 poetry run python -m live.cli init-data 실행 (yfinance 실제 호출)
[M-10.3] 👤 생성된 CSV 파일 확인 (6종, 행수 > 1000)
```

---

### Step 11: GitHub Actions 🤖

```
설계서: 12장

daily_run.yml: cron '50 17 * * 1-5', timezone America/New_York
keepalive.yml: 매월 1일
```

- [x] 🤖 `daily_run.yml` 생성
- [x] 🤖 `keepalive.yml` 생성
- [x] 🤖 Poetry 캐싱 (actions/cache@v4) 포함
- [x] 🤖 retry + notify-failure job 포함

**수동 테스트 (👤):**

```
[M-11.1] 👤 GitHub Actions 탭에서 workflow_dispatch로 수동 실행
[M-11.2] 👤 실행 로그 확인 (정상 완료 or 에러 알림 수신)
[M-11.3] 👤 5거래일 연속 자동 실행 확인
```

---

### Phase 1 완료 조건

- [ ] 🤖 Step 1~11 전체 완료
- [ ] 🤖 `poetry run pytest live/tests/` 통과
- [ ] 🤖 `test_regression.py` 통과
- [ ] 👤 GitHub Actions 5거래일 연속 정상

---

## Phase 2: 알림 + RTDB

### Step 12: RTDB 게이트웨이 (rtdb_gateway.py) 🤖

```
설계서: 10장

RTDB URL: https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app
```

- [x] 🤖 `rtdb_gateway.py` 구현
- [x] 🤖 Firebase Admin SDK 초기화 로직 포함

**수동 테스트 (👤):**

```
[M-12.1] 👤 Firebase 콘솔 RTDB 탭에서 데이터 확인
[M-12.2] 👤 RTDB에 테스트 데이터 기록 -> 삭제 확인
```

---

### Step 13: 알림 (notifier.py) 🤖

```
설계서: 8장

FCM + 텔레그램 항상 동시. 200일선 근접도 포함.
에러 알림에 에러 상세 메시지 포함.
```

- [x] 🤖 `notifier.py` 구현

**수동 테스트 (👤):**

```
[M-13.1] 👤 notify-failure 명령으로 FCM 수신 확인 (핸드폰)
[M-13.2] 👤 텔레그램 @qbt_live_alert_bot 채팅에서 메시지 수신 확인
[M-13.3] 👤 FCM과 텔레그램 내용 동일한지 확인
```

---

### Step 14: 차트 시계열 (chart_data.py) 🤖

```
설계서: 7장

CSV 전체 -> ChartSeries. 자산별 전체 기간. user_buys/user_sells 포함.
```

- [ ] 🤖 `chart_data.py` 구현

**테스트 시나리오 (🤖):**

```
[T-14.1] 1년치 CSV -> ChartSeries 생성, dates/close/ema_200 길이 일치
[T-14.2] buy_signals/sell_signals 인덱스가 dates 범위 내
[T-14.3] EMA-200 초기 199일은 None
```

---

### Step 15: 히스토리 (history.py) 🤖

```
설계서: 10.1

전체 영구 보존. 자동 정리 없음.
```

- [ ] 🤖 `history.py` 구현

**테스트 시나리오 (🤖):**

```
[T-15.1] save_daily_log -> JSON 파일 생성 확인
[T-15.2] append_summary -> JSONL 1행 추가
[T-15.3] append_user_trade -> JSONL 1행 추가
[T-15.4] 같은 날짜 2번 append -> 2행 추가 (덮어쓰기 아님)
```

---

### Phase 2 완료 조건

- [ ] 🤖 Step 12~15 완료
- [ ] 👤 FCM 푸시 수신 확인 (실제 디바이스)
- [ ] 👤 텔레그램 메시지 수신 확인
- [ ] 👤 RTDB 데이터 정상 확인 (Firebase 콘솔)

---

## Phase 3: Android 앱

### Step 16: React Native 프로젝트 초기화 🤖

```
qbt-live-app/ 디렉토리에 생성.
Firebase SDK, react-native-webview, bottom-tabs.
google-services.json (com.ingbeen.qbtlive)
```

- [ ] 🤖 RN 프로젝트 생성
- [ ] 🤖 Firebase SDK 연동
- [ ] 🤖 4탭 네비게이션

**수동 테스트 (👤):**

```
[M-16.1] 👤 npx react-native run-android -> 에뮬레이터/디바이스에서 앱 실행
[M-16.2] 👤 4탭 네비게이션 동작 확인
```

---

### Step 17: 인증 + FCM 🤖

```
LoginScreen: Firebase Auth Email/Password
FCM 토큰 -> RTDB /device_tokens/
```

- [ ] 🤖 LoginScreen 구현
- [ ] 🤖 FCM 토큰 등록 로직

**수동 테스트 (👤):**

```
[M-17.1] 👤 앱에서 이메일/비밀번호 로그인
[M-17.2] 👤 Firebase 콘솔 RTDB > /device_tokens/ 에 토큰 등록 확인
[M-17.3] 👤 앱 종료 후 재시작 -> 로그인 유지 확인
```

---

### Step 18: 홈 화면 🤖

```
RTDB /latest/portfolio 읽기. 포트폴리오, 200일선, 신호, 마지막 실행 시각.
```

- [ ] 🤖 HomeScreen 구현

**수동 테스트 (👤):**

```
[M-18.1] 👤 앱 홈에서 포트폴리오 데이터 표시 확인
[M-18.2] 👤 200일선 근접도 표시 확인
[M-18.3] 👤 마지막 실행 시각 표시 확인
```

---

### Step 19: 차트 화면 🤖

```
RTDB /latest/chart_data/ 읽기. WebView + TradingView Lightweight Charts.
기간 [3M/6M/1Y/전체]. 자산 선택.
```

- [ ] 🤖 ChartScreen 구현
- [ ] 🤖 TradingViewChart 컴포넌트

**수동 테스트 (👤):**

```
[M-19.1] 👤 차트 화면에서 SPY 종가 + EMA-200 + 밴드 표시 확인
[M-19.2] 👤 기간 변경 (3M -> 1Y -> 전체) 동작 확인
[M-19.3] 👤 자산 변경 (SPY -> QQQ -> GLD) 동작 확인
[M-19.4] 👤 신호 마커/체결 마커 표시 확인
```

---

### Step 20: 거래 화면 🤖

```
체결 입력 (과거 날짜, 자동 매칭), 자산 직접 수정, 체결 히스토리, Drift.
```

- [ ] 🤖 TradeScreen 구현

**수동 테스트 (👤):**

```
[M-20.1] 👤 체결 입력 폼에서 SSO 매수 42주 $82.05 제출
[M-20.2] 👤 Firebase 콘솔 RTDB > /fills/inbox/ 에 데이터 확인
[M-20.3] 👤 과거 날짜 선택하여 체결 입력
[M-20.4] 👤 자산 직접 수정 (주수/현금 변경) -> 저장 -> RTDB 확인
[M-20.5] 👤 체결 히스토리에서 필터 (전체/시스템/개인/보정) 동작 확인
[M-20.6] 👤 Drift 상세 화면 표시 확인
```

---

### Step 21: 설정 + APK 빌드 🤖

```
SettingsScreen. APK 빌드.
```

- [ ] 🤖 SettingsScreen 구현
- [ ] 🤖 APK 빌드 설정

**수동 테스트 (👤):**

```
[M-21.1] 👤 APK 빌드: cd android && ./gradlew assembleRelease
[M-21.2] 👤 디바이스에 APK 설치
[M-21.3] 👤 전체 화면 순회: 로그인 -> 홈 -> 차트 -> 거래 -> 설정
```

---

### Phase 3 완료 조건

- [ ] 🤖 Step 16~21 완료
- [ ] 👤 APK 설치 후 전 화면 정상
- [ ] 👤 FCM 푸시 수신 -> 앱 이동

---

## Phase 4: 체결 + Drift E2E

### Step 22: 엔드투엔드 테스트 👤

```
실제 운영 시나리오를 사용자가 직접 테스트한다.
```

**수동 테스트 (👤):**

```
[M-22.1] 👤 daily runner가 pending 생성하는 날을 기다림 (또는 테스트 데이터 주입)
[M-22.2] 👤 FCM 알림 수신 확인
[M-22.3] 👤 텔레그램 알림 수신 확인 + 내용 동일 확인
[M-22.4] 👤 앱에서 체결 입력 (자산/수량/가격/체결일)
[M-22.5] 👤 다음 daily runner 실행 후:
         - Firebase 콘솔에서 fills processed=true 확인
         - 앱 Drift 화면에서 actual 반영 확인
         - 알림에 drift % 표시 확인
[M-22.6] 👤 같은 체결 다시 입력 -> 중복 반영 안 되는지 확인
[M-22.7] 👤 개인 매매 입력 (pending 없는 자산 매도) -> personal_trade 분류 확인
[M-22.8] 👤 2건 이상 밀린 후 한꺼번에 입력 -> 각각 올바르게 매칭 확인
[M-22.9] 👤 체결 미입력 상태 -> 다음 날 리마인더 알림 수신 확인
[M-22.10] 👤 자산 직접 수정 (잔고 보정) -> drift 변화 확인
```

- [ ] 👤 시스템 체결 자동 매칭 정상
- [ ] 👤 개인 매매 분류 정상
- [ ] 👤 밀린 체결 처리 정상
- [ ] 👤 idempotency 확인
- [ ] 👤 미입력 리마인더 정상
- [ ] 👤 자산 직접 수정 -> drift 반영

---

## Phase 5: 안정화

### Step 23: 운영 안정화

**수동 테스트 (👤):**

```
[M-23.1] 👤 FCM 실패 시뮬레이션: Firebase 콘솔에서 앱 삭제 후 재설치
         -> 텔레그램은 정상 수신 확인
[M-23.2] 👤 데이터 검증 실패 시뮬레이션: CSV 마지막 행 종가를 수동 변경
         -> 실행 중단 + 에러 알림 수신 확인 (자동 복구 없음)
[M-23.3] 👤 live_state.json 손상 시뮬레이션: 파일 내용 깨뜨리기
         -> 실행 중단 + 에러 알림 수신 확인 (자동 복구 없음)
[M-23.4] 👤 keepalive commit 동작 확인 (매월 1일 이후 Actions 로그)
[M-23.5] 👤 30거래일 연속 무중단 운영 달성
```

- [ ] 👤 FCM/텔레그램 상호 독립 확인
- [ ] 👤 에러 시 자동 복구 없이 중단 + 알림 확인
- [ ] 👤 keepalive 동작
- [ ] 👤 30거래일 무중단

### Step 24: 문서화 + App Check 🤖+👤

- [ ] 🤖 README.md 작성
- [ ] 🤖 장애 대응 절차 문서화
- [ ] 👤 App Check 도입 검토

---

## 최종 완료

- [ ] Phase 1~5 전체 완료
- [ ] 👤 30거래일 무중단
- [ ] 🤖 회귀 테스트 유지
