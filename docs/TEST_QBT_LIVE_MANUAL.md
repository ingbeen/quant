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

### 1. 원격 `qbt-live-state` 리포 초기 상태 확인 ✅

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

- [x] `https://github.com/ingbeen/qbt-live-state` 에 `live_state.json` 존재
- [x] `data/stock/` 하위에 SPY / QQQ / SSO / QLD / GLD / TLT CSV 6 종 존재
- [x] 커밋 메시지가 `auto: live init ...` / `auto: live init-data ...` 형식

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

**사전 조건**: 2, 3 번 완료. GitHub 의 `ingbeen/qbt-live-state` 프라이빗 리포에 `live_state.json` 과 `data/stock/*.csv` 가 최소 1 회 이상 커밋되어 있어야 합니다 (Phase A #1 에서 시드 완료됨).

**절차**:

1. `https://github.com/ingbeen/quant/actions` 접속
2. 좌측 목록에서 **`Daily Run`** 선택
3. 우측 상단 **[Run workflow]** 드롭다운 클릭 → Branch `main` 선택
4. `trade_date` 입력란 처리:
   - **평일 정상 테스트**: 비워둠 (기본값 "오늘" 사용)
   - **주말 또는 과거 재현 테스트**: `YYYY-MM-DD` 형식으로 최근 거래일 지정 (예: `2026-04-10`). 휴장일 / 주말에 수동 테스트를 돌릴 때 사용
5. **[Run workflow]** 녹색 버튼 클릭
6. 페이지 새로고침하여 새 실행 항목이 큐에 올라오는지 확인

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

## Phase B: 운영 안정화 시뮬레이션

### 11. 데이터 검증 실패 시뮬레이션

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

### 12. live_state.json 손상 시뮬레이션

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

### 13. keepalive commit 동작 확인

**목적**: GitHub Actions 의 **60일 비활성 정책** 으로부터 `daily_run.yml` 의 cron 스케줄을 보호하기 위한 keepalive 동작 검증. `quant` (퍼블릭) 리포에 월 1 회 빈 commit (`git commit --allow-empty`) 을 남겨 activity 를 유지한다.

**사전 조건**: `keepalive.yml` 배포 완료.

**절차**:

1. `https://github.com/ingbeen/quant/actions` → 좌측 `Keepalive` 워크플로우 선택
2. 실행 이력에서 매월 1 일자 실행 로그 확인
3. `quant` 리포 커밋 히스토리 (`https://github.com/ingbeen/quant/commits/main`) 에서 `keepalive: YYYY-MM-DD` 메시지 커밋 존재 여부 확인

**확인 사항**:

- [ ] 매월 1 일 `Keepalive` 실행 로그 존재 (또는 workflow_dispatch 수동 실행)
- [ ] 실행 결과 정상 (녹색)
- [ ] `quant` 리포에 `keepalive: YYYY-MM-DD` 빈 commit 이 push 됨

---

## Phase C: Android 앱 연동 (앱 구현 후 진행)

> Android 앱은 별도 프로젝트 (`qbt-live-app`) 에서 구현한다.
> 앱 구현이 완료되어 FCM device token 이 RTDB `/device_tokens/` 에 등록된 이후에 아래 테스트를 진행한다.
> 앱 자체의 기능 테스트 (UI / 로그인 / 차트 화면 등) 는 앱 프로젝트의 전용 테스트 문서에서 관리한다.

### 14. FCM 수신 확인 (앱 구현 후)

**목적**: 서버에서 발송한 FCM 메시지가 실제 디바이스에 도달하는지 end-to-end 검증.

**사전 조건**: 앱 프로젝트가 구현되어 FCM device token 이 RTDB `/device_tokens/` 에 등록된 상태.

**절차**:

```bash
poetry run python -m live.cli notify-failure --message "FCM 수동 테스트"
```

**확인 사항**:

- [ ] 설치된 디바이스에서 FCM 푸시 알림 수신
- [ ] 알림 내용이 동일 시점 텔레그램 메시지와 포맷 일치

---

## 최종 완료 체크

- [ ] Phase A (1~10) 모두 완료
- [ ] Phase B (11~13) 모두 완료
- [ ] Phase C (14) 완료 — 앱 구현 후 진행
