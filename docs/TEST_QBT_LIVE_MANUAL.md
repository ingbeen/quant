# QBT Live 수동 테스트 가이드

> 실제 실행 가능한 순서대로 번호가 매겨져 있습니다.
> 위에서부터 순서대로 진행하세요.
> 각 테스트의 **사전 조건**이 성립한 후에만 다음 단계로 넘어갑니다.

## 진행 원칙

- 번호 순서대로 진행합니다.
- 한 단계의 사전 조건이 성립하지 않으면 해당 단계는 대기 상태입니다.
- 체크박스를 완료하면서 기록합니다.
- 장애 시 자동 복구 금지 원칙에 따라, 에러가 발생하면 즉시 중단하고 원인을 확인합니다.

---

## Phase A: 로컬 파이프라인 + GitHub Actions (Step 1~15 검증)

### 1. 원격 `qbt-live-state` 리포 초기 상태 확인

**목적**: GitHub Actions 가 읽을 원격 리포에 초기 상태(`live_state.json`, `data/stock/*.csv`) 가 커밋되어 있는지 확인.

**사전 조건**: `.env` 에 `STATE_REPO_PAT`, `TELEGRAM_*`, `GOOGLE_APPLICATION_CREDENTIALS` 설정 완료.

**원칙**: CLI 는 **ephemeral 모드** 로 동작합니다. 로컬에서 `init` / `init-data` / `run-daily` 등을 실행하면 내부적으로 `qbt-live-state` 를 임시 디렉토리에 shallow clone 하고, 작업 후 commit/push 한 뒤 임시 디렉토리를 삭제합니다. 로컬 프로젝트 폴더에는 파일이 전혀 남지 않습니다.

**절차 (원격 리포가 비어있다면 최초 1 회 시드)**:

```bash
cd ~/workspace/quant
poetry run python -m live.cli init --capital 100000000
poetry run python -m live.cli init-data
```

각 명령은 자동으로 원격 리포에 새 커밋을 push 합니다.

**확인 사항** (GitHub 웹에서):

- [ ] `https://github.com/ingbeen/qbt-live-state` 에 `live_state.json` 존재
- [ ] `data/stock/` 하위에 SPY / QQQ / SSO / QLD / GLD / TLT CSV 6 종 존재
- [ ] 커밋 메시지가 `auto: live init ...` / `auto: live init-data ...` 형식

---

### 2. 텔레그램 실패 알림 수신 확인

**목적**: 텔레그램 봇 연결과 `.env` 자동 로드가 정상 동작하는지 가장 단순한 경로로 검증.

**사전 조건**: 1 번 완료.

**절차**:

1. 텔레그램 앱에서 `@qbt_live_alert_bot` 검색 → [Start] 버튼 누르기 (최초 1 회)
2. 프로젝트 루트 `quant/.env` 파일을 에디터로 직접 생성 후 아래 항목 기입 (최초 1 회):

   ```
   TELEGRAM_BOT_TOKEN=<봇 토큰>
   TELEGRAM_CHAT_ID=<본인 chat id>
   STATE_REPO_PAT=<GitHub PAT — ephemeral clone/push 에 사용>
   GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/firebase-adminsdk.json
   ```

3. 수동 실패 알림 발송 (env export 불필요 — CLI 가 `.env` 를 자동 로드):

```bash
cd ~/workspace/quant
poetry run python -m live.cli notify-failure --message "수동 테스트 from local"
```

**확인 사항**:

- [x] 텔레그램 `@qbt_live_alert_bot` 채팅에 `[QBT Live 실패]` 메시지 수신
- [x] 메시지 본문에 smoke test 문구 포함

> `.env` 는 `.gitignore` 에 의해 커밋되지 않습니다. GitHub Actions 환경에서는 이 파일 대신 워크플로우 `env:` 블록이 사용되며, 동일한 CLI 코드가 양쪽에서 분기 없이 동작합니다.

---

### 3. GitHub Secrets 등록 확인 ✅

**목적**: GitHub Actions 가 사용할 Secret 4 종이 등록되어 있는지 확인.

**사전 조건**: Phase 0 에서 등록 완료 상태.

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/quant/settings/secrets/actions` 접속
2. 목록에 Secret 4 종 존재 확인

**확인 사항**:

- [x] `FIREBASE_CONFIG` 존재
- [x] `STATE_REPO_PAT` 존재
- [x] `TELEGRAM_BOT_TOKEN` 존재
- [x] `TELEGRAM_CHAT_ID` 존재

---

### 4. GitHub Actions `daily_run` 수동 실행

**목적**: 스케줄러 없이 워크플로우를 직접 실행해 전체 파이프라인을 검증. 이 단계가 성공하면 `run-daily` 의 모든 후속 동작 (상태 업데이트, RTDB write, history 파일 생성, `qbt-live-state` 리포 push) 이 한 번에 검증됩니다.

**사전 조건**: 2, 3 번 완료. GitHub 의 `ingbeen/qbt-live-state` 프라이빗 리포에 `live_state.json` 과 `data/stock/*.csv` 가 최소 1 회 이상 커밋되어 있어야 합니다 (없다면 로컬에서 한 번 push 후 진행).

**절차**:

1. `https://github.com/ingbeen/quant/actions` 접속
2. 좌측 목록에서 **`Daily Run`** 선택
3. 우측 상단 **[Run workflow]** 드롭다운 → Branch `main` → **[Run workflow]** 클릭
4. 페이지 새로고침하여 새 실행 항목이 큐에 올라오는지 확인

**확인 사항**:

- [ ] 새 실행 항목이 큐에 등록됨 (회색 원 또는 노란 원)

---

### 5. GitHub Actions 실행 결과 확인

**목적**: 4 번 실행의 성공 / 실패 여부를 확인하고 알림 + `qbt-live-state` push 가 정상 동작하는지 검증.

**사전 조건**: 4 번 완료.

**절차**:

1. Actions 탭에서 4 번 실행 항목 클릭
2. `run-daily` job 클릭 → 각 step 펼쳐가며 로그 확인
3. 결과 상태 확인 (녹색 / 빨간색)

**확인 사항 (정상 케이스)**:

- [ ] job 결과가 녹색 체크
- [ ] `Run daily` step 로그에 `run-daily 완료: equity=..., pending=..., drift=...` 출력
- [ ] `qbt-live-state` 리포에 새 커밋 `auto: daily run YYYY-MM-DD` 푸시됨 (push 동작 검증)

**확인 사항 (실패 케이스)**:

- [ ] job 결과가 빨간 X
- [ ] 텔레그램에 `[QBT Live 실패]` 수신 (에러 상세 메시지 포함)

---

### 6. RTDB 포트폴리오 read model 확인

**목적**: Step 12 `rtdb_gateway` 와 `run-daily` 의 read model 쓰기 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. `https://console.firebase.google.com/` → 프로젝트 `qbt-live` → Realtime Database 탭
2. 루트 트리에서 `/latest/portfolio` 펼치기

**확인 사항**:

- [ ] 4 개 자산(SPY / QQQ / GLD / TLT) 별 shares / cash / close 필드 존재
- [ ] `drift_pct` 필드 존재
- [ ] `updated_at` 이 4 번 실행 시각과 일치

---

### 7. RTDB 차트 데이터 확인

**목적**: Step 14 `chart_data` 의 RTDB 쓰기와 배열 형식 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. 같은 RTDB 화면에서 `/latest/chart_data/` 펼치기
2. 자산별(SPY / QQQ / GLD / TLT) 하위 노드 펼치기
3. 배열이 길 경우 검색창에 `/latest/chart_data/SPY/dates/0` 형태의 구체 경로로 값 확인

**확인 사항**:

- [ ] 4 개 자산 노드가 모두 존재
- [ ] 각 자산의 `dates`, `close`, `ema_200` 배열 길이가 동일
- [ ] `ema_200` 앞쪽 199 개 값이 `null`
- [ ] `dates` 마지막 원소가 최근 거래일
- [ ] `buy_signals` / `sell_signals` 는 빈 배열이거나 `dates` 범위 내 인덱스만 포함

---

### 8. RTDB 히스토리 요약 확인

**목적**: Step 15 `history.append_summary` 의 RTDB 쓰기 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. RTDB 에서 `/history/summary/{YYYY-MM-DD}` 경로 펼치기

**확인 사항**:

- [ ] 당일 날짜 키로 요약 1 건 존재
- [ ] `model_equity`, `drift_pct`, `pending_count` 필드 포함

---

### 9. qbt-live-state 히스토리 파일 확인

**목적**: Step 15 `history` 의 파일 시스템 쓰기 + git push 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/qbt-live-state/tree/main/history` 접속
2. `history/daily/` 와 `history/summary.jsonl` 존재 확인

**확인 사항**:

- [ ] `history/daily/{YYYY-MM-DD}.json` 파일 존재
- [ ] 해당 JSON 내용에 `date`, `model_equity`, `drift_pct`, `assets` 키 포함
- [ ] `history/summary.jsonl` 마지막 줄이 당일 날짜 요약
- [ ] 같은 날짜로 재실행 시 `summary.jsonl` 줄 수가 1 증가 (덮어쓰기 아님)

---

### 10. RTDB 쓰기 권한 점검

**목적**: Firebase 콘솔에서 수동 쓰기/삭제가 규칙 위반 없이 수행되는지 확인.

**사전 조건**: 없음.

**절차**:

1. Firebase 콘솔 RTDB 화면에서 루트 노드 옆 **+** 클릭
2. 이름 `_debug_write_check`, 값 `"hello"` 로 추가
3. 방금 만든 노드 옆 **X** 로 삭제

**확인 사항**:

- [ ] 쓰기가 permission_denied 없이 성공
- [ ] 삭제도 성공

---

## Phase B: Android 앱 검증 (Step 16~21 구현 후 진행)

### 11. 앱 실행

**목적**: React Native 프로젝트가 에뮬레이터 / 디바이스에서 정상 기동.

**사전 조건**: Step 16 구현 완료.

**절차**:

```bash
cd qbt-live-app
npx react-native run-android
```

**확인 사항**:

- [ ] 에뮬레이터 또는 디바이스에서 앱이 실행됨
- [ ] 4 탭 네비게이션 (홈 / 차트 / 거래 / 설정) 이동 가능

---

### 12. 로그인 + FCM 토큰 등록

**목적**: Firebase Auth 로그인과 FCM 토큰의 RTDB 등록 검증.

**사전 조건**: Step 17 구현 완료, 11 번 완료.

**절차**:

1. 앱 LoginScreen 에서 이메일 / 비밀번호 입력 후 로그인
2. Firebase 콘솔 RTDB 에서 `/device_tokens/` 경로 확인
3. 앱 종료 후 재시작

**확인 사항**:

- [ ] 로그인 성공
- [ ] RTDB `/device_tokens/` 에 토큰 등록됨
- [ ] 앱 재시작 후에도 로그인 상태 유지

---

### 13. FCM 수신 확인

**목적**: 서버 → FCM → 앱 수신 경로 검증.

**사전 조건**: 12 번 완료.

**절차**:

```bash
poetry run python -m live.cli notify-failure --message "FCM 수동 테스트"
```

**확인 사항**:

- [ ] 앱이 설치된 기기에서 FCM 푸시 알림 수신
- [ ] 알림 탭 시 앱으로 이동

---

### 14. FCM / 텔레그램 내용 일치 확인

**목적**: 두 채널의 메시지 본문이 동일 포맷인지 확인.

**사전 조건**: 13 번 완료.

**절차**: 13 번 실행 시점에 텔레그램 채팅도 열어두고 두 메시지 비교.

**확인 사항**:

- [ ] FCM 알림 본문과 텔레그램 메시지 본문이 동일

---

### 15. 홈 화면 확인

**사전 조건**: Step 18 구현 완료, 12 번 완료.

**절차**: 앱 홈 탭 이동.

**확인 사항**:

- [ ] 4 개 자산 포트폴리오 데이터 표시
- [ ] 200 일선 근접도 표시
- [ ] 마지막 실행 시각 표시

---

### 16. 차트 화면 확인

**사전 조건**: Step 19 구현 완료, 12 번 완료.

**절차**: 앱 차트 탭 이동, 기간 / 자산 변경.

**확인 사항**:

- [ ] SPY 종가 + EMA-200 + 밴드 표시
- [ ] 기간 변경 (3M → 1Y → 전체) 동작
- [ ] 자산 변경 (SPY → QQQ → GLD) 동작
- [ ] 신호 마커 / 체결 마커 표시

---

### 17. 거래 화면 - 체결 입력

**사전 조건**: Step 20 구현 완료, 12 번 완료.

**절차**: 거래 탭에서 체결 입력 폼 사용.

**확인 사항**:

- [ ] SSO 매수 42 주 $82.05 제출
- [ ] Firebase 콘솔 `/fills/inbox/` 에 데이터 확인
- [ ] 과거 날짜 선택하여 체결 입력 가능
- [ ] 자산 직접 수정 (주수 / 현금 변경) → 저장 → RTDB 반영
- [ ] 체결 히스토리 필터 (전체 / 시스템 / 개인 / 보정) 동작
- [ ] Drift 상세 화면 표시

---

### 18. APK 빌드 + 전체 화면 순회

**사전 조건**: Step 21 구현 완료.

**절차**:

```bash
cd qbt-live-app/android && ./gradlew assembleRelease
```

**확인 사항**:

- [ ] APK 빌드 성공
- [ ] 디바이스에 APK 설치 성공
- [ ] 로그인 → 홈 → 차트 → 거래 → 설정 전 화면 순회 정상

---

## Phase C: E2E 시나리오 (Phase 4)

### 19. pending 생성 테스트 데이터 주입

**목적**: 실제 장 신호를 기다리지 않고 인위적으로 pending 을 만들어 E2E 흐름 검증.

**사전 조건**: Phase B 완료.

**절차**: CSV 수동 편집 또는 과거 날짜 `run-daily` 등으로 pending 발생 조건 강제.

**확인 사항**:

- [ ] `live_state.json` 에 pending_order 기록
- [ ] FCM 알림 수신
- [ ] 텔레그램 알림 수신 (FCM 과 내용 동일)

---

### 20. 시스템 체결 자동 매칭

**사전 조건**: 19 번 완료.

**절차**:

1. 앱 거래 화면에서 pending 과 일치하는 체결 입력
2. 다음 `run-daily` 실행

**확인 사항**:

- [ ] Firebase 콘솔 `/fills/inbox/` 에서 `processed=true`
- [ ] 앱 Drift 화면에서 actual 반영
- [ ] 알림에 drift % 표시

---

### 21. idempotency 확인

**사전 조건**: 20 번 완료.

**절차**: 같은 체결을 다시 입력.

**확인 사항**:

- [ ] 중복 반영되지 않음 (actual 변경 없음)

---

### 22. 개인 매매 분류

**사전 조건**: Phase B 완료.

**절차**: pending 이 없는 자산을 매도 체결로 입력.

**확인 사항**:

- [ ] `personal_trade` 로 분류됨

---

### 23. 밀린 체결 처리

**사전 조건**: Phase B 완료.

**절차**: 2 건 이상의 체결을 밀린 상태로 한꺼번에 입력.

**확인 사항**:

- [ ] 각 체결이 올바른 pending 과 매칭

---

### 24. 미입력 리마인더

**사전 조건**: 19 번 완료 + 다음 거래일 대기.

**절차**: 체결 미입력 상태로 다음 거래일 `run-daily` 실행.

**확인 사항**:

- [ ] 리마인더 알림 수신

---

### 25. 자산 직접 수정 → drift 변화

**사전 조건**: Phase B 완료.

**절차**: 거래 화면에서 자산 주수 / 현금 직접 수정.

**확인 사항**:

- [ ] drift 수치가 즉시 반영

---

## Phase D: 운영 안정화 (Phase 5)

### 26. FCM 실패 시뮬레이션

**목적**: FCM 과 텔레그램이 상호 독립적으로 동작하는지 확인.

**사전 조건**: Phase B 완료.

**절차**: Firebase 콘솔에서 앱 삭제 → 재설치하여 토큰 무효화 → `run-daily` 실행.

**확인 사항**:

- [ ] FCM 실패해도 텔레그램은 정상 수신
- [ ] 다음 로그인 시 새 토큰 등록됨

---

### 27. 데이터 검증 실패 시뮬레이션

**목적**: 데이터 검증 실패 시 자동 복구 없이 중단되는지 확인.

**사전 조건**: Phase A 완료.

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/qbt-live-state/blob/main/data/stock/SPY.csv` 접속
2. 연필 아이콘 **Edit this file** 클릭
3. 마지막 행의 종가를 10% 이상 변경 후 커밋 (예: `... , 450.12` → `... , 550.00`)
4. GitHub Actions `Daily Run` workflow_dispatch 수동 실행
5. 검증 완료 후 해당 커밋을 GitHub 웹 Revert 로 원상복구

**확인 사항**:

- [ ] Actions job 이 빨간 X 로 종료
- [ ] 텔레그램에 `[QBT Live 실패]` 수신 (상세 에러 메시지 포함)
- [ ] `qbt-live-state` 리포에 `auto: live run-daily ...` 커밋이 **추가되지 않음** (자동 롤백 없음 = 부분 커밋도 없음)
- [ ] revert 후 다음 실행이 정상

---

### 28. live_state.json 손상 시뮬레이션

**목적**: 상태 파일 손상 시 중단 동작 확인.

**사전 조건**: Phase A 완료.

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/qbt-live-state/blob/main/live_state.json` 접속
2. Edit this file 클릭
3. JSON 파싱이 실패하도록 여는 중괄호 `{` 를 하나 제거하거나 임의 문자 삽입 후 커밋
4. GitHub Actions `Daily Run` workflow_dispatch 수동 실행
5. 검증 완료 후 GitHub 웹 Revert 로 원상복구

**확인 사항**:

- [ ] Actions job 이 빨간 X 로 종료
- [ ] 텔레그램에 `[QBT Live 실패]` 수신 (JSON 파싱 관련 메시지)
- [ ] `qbt-live-state` 리포에 새 run-daily 커밋 없음 (실패 시 push 없음)
- [ ] revert 후 다음 실행이 정상

---

### 29. keepalive commit 동작 확인

**목적**: Firebase Spark 플랜의 비활성 프로젝트 제거를 방지하는 keepalive 동작 검증.

**사전 조건**: Step 11 `keepalive.yml` 배포 완료.

**절차**: 매월 1 일 이후 Actions 탭에서 `Keepalive` 워크플로우 실행 이력 확인.

**확인 사항**:

- [ ] 매월 1 일 `Keepalive` 실행 로그 존재
- [ ] 실행 결과 정상 (녹색)

---

## 최종 완료 체크

- [ ] Phase A (1~10) 모두 완료
- [ ] Phase B (11~18) 모두 완료
- [ ] Phase C (19~25) 모두 완료
- [ ] Phase D (26~29) 모두 완료
