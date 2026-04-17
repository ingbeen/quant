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
poetry run python -m live init --capital 100000000
poetry run python -m live rebuild-data   # 티커 생략 시 전체 운영 티커 다운로드
```

각 명령은 자동으로 원격 리포에 새 커밋을 push 합니다.

**확인 사항** (GitHub 웹에서):

- [x] `https://github.com/ingbeen/qbt-live-state` 에 `live_state.json` 존재
- [x] `data/stock/` 하위에 SPY / QQQ / SSO / QLD / GLD / TLT CSV 6 종 존재
- [x] 커밋 메시지가 `auto: live init ...` / `auto: live rebuild-data ...` 형식

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
poetry run python -m live notify-failure --message "수동 테스트 from local"
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

**사전 조건**:

- 2, 3 번 완료
- `ingbeen/qbt-live-state` 프라이빗 리포에 초기 상태 시드 완료 (Phase A #1)
- **`quant` 리포의 `main` 브랜치에 `.github/workflows/daily_run.yml` 이 push 되어 있어야 함**. `workflow_dispatch` 모달에 `trade_date` 입력란이 보이려면 **GitHub 에 반영된 최신 yml 이 필요** 하므로, 로컬 수정이 있다면 먼저 commit + push:
  ```bash
  cd ~/workspace/quant
  git add .github/workflows/daily_run.yml .github/workflows/keepalive.yml
  git commit -m "ci / daily_run workflow_dispatch trade_date + keepalive quant target"
  git push origin main
  ```

**절차**:

1. `https://github.com/ingbeen/quant/actions` 접속
2. 좌측 목록에서 **`Daily Run`** 선택
3. 우측 상단 **[Run workflow]** 드롭다운 클릭 → Branch `main` 선택
4. `trade_date` 입력란 처리:
   - **평일 정상 테스트**: 비워둠 (기본값 "오늘" 사용)
   - **주말 또는 과거 재현 테스트**: `YYYY-MM-DD` 형식으로 최근 거래일 지정 (예: `2026-04-10`). 휴장일 / 주말에 수동 테스트를 돌릴 때 사용
   - ⚠️ **중요**: `trade_date` 를 비워둔 상태로 주말에 실행하면 **휴장 체크** (NYSE) 에 걸려 즉시 조기 종료 (로그만 남고 state/알림 없음) 됩니다. 주말 수동 테스트는 반드시 `trade_date=2026-04-10` 같은 최근 영업일을 명시하세요
   - ⚠️ **중요**: `trade_date` 를 비워둔 상태로 같은 날에 두 번 실행하면 **idempotency 체크** 에 걸려 두 번째는 조기 종료됩니다. 재실행이 필요하면 역시 `trade_date` 를 명시하여 bypass 하세요
5. **[Run workflow]** 녹색 버튼 클릭
6. 페이지 새로고침하여 새 실행 항목이 큐에 올라오는지 확인

> 만약 `trade_date` 입력란이 보이지 않는다면 워크플로우 yml 이 아직 `main` 에 push 되지 않은 것입니다. 위 사전 조건의 commit/push 명령을 먼저 실행하세요.

**확인 사항**:

- [x] 새 실행 항목이 큐에 등록됨 (회색 원 또는 노란 원)

---

### 5. GitHub Actions 실행 결과 확인

**목적**: 4 번 실행의 성공 / 실패 여부를 확인하고 알림 + `qbt-live-state` push 가 정상 동작하는지 검증.

**사전 조건**: 4 번 완료.

**절차**:

1. Actions 탭에서 4 번 실행 항목 클릭
2. `run-daily` job 클릭 → 각 step 펼쳐가며 로그 확인
3. 결과 상태 확인 (녹색 / 빨간색)

**확인 사항 (정상 케이스)**:

- [x] job 결과가 녹색 체크
- [x] `Run daily` step 로그에 `run-daily 완료: equity=..., pending=..., drift=...` 출력
- [x] `qbt-live-state` 리포에 새 커밋 `auto: live run-daily YYYY-MM-DD HH:MM:SS KST` 푸시됨 (push 동작 검증 — ephemeral CLI 가 clone → 작업 → commit/push)
- [x] 텔레그램에 `[QBT Live] {execution_date}` 수신, 본문에 model/actual equity, drift, 시그널, 200 일선 근접도, 리밸런싱 여부 포함

**확인 사항 (실패 케이스)**:

- [ ] job 결과가 빨간 X
- [ ] 텔레그램에 `[QBT Live 실패]` 수신 (에러 상세 메시지 포함)
- [ ] `qbt-live-state` 리포에 새 커밋이 **추가되지 않음** (실패 시 push 없음)

---

### 6. RTDB 포트폴리오 read model 확인

**목적**: Step 12 `rtdb_gateway` 와 `run-daily` 의 read model 쓰기 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. `https://console.firebase.google.com/` → 프로젝트 `qbt-live` → Realtime Database 탭
2. 루트 트리에서 `/latest/portfolio` 펼치기

**실제 스키마** (from [rtdb_gateway.py::write_read_model](src/live/rtdb_gateway.py#L133)):

```
/latest/portfolio
  ├─ execution_date       # "YYYY-MM-DD"
  ├─ model_equity         # 정수
  ├─ actual_equity        # 정수
  ├─ drift_pct            # 0~1 비율
  ├─ shared_cash_model    # 정수
  ├─ shared_cash_actual   # 정수
  └─ assets/
       ├─ sso/            # trade ticker 기준 자산 ID
       │   ├─ model_shares
       │   ├─ actual_shares
       │   └─ signal_state   # "holding" / "cash" 등
       ├─ qld/
       ├─ gld/
       └─ tlt/
```

**확인 사항**:

- [x] `execution_date` 가 4 번 실행 시 선택한 거래일과 일치
- [x] `model_equity`, `actual_equity`, `drift_pct` 필드 존재 및 숫자 값 확인
- [x] `shared_cash_model`, `shared_cash_actual` 필드 존재
- [x] `assets/` 하위에 `sso`, `qld`, `gld`, `tlt` 4 개 노드 존재
- [x] 각 자산 하위에 `model_shares`, `actual_shares`, `signal_state` 필드 존재

---

### 7. RTDB 주가 차트 데이터 확인

**목적**: Step 14 `chart_data` (주가 차트) 의 RTDB 쓰기 및 경로 이동 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. 같은 RTDB 화면에서 `/charts/prices/` 펼치기
2. 자산별(sso / qld / gld / tlt) 하위 노드 펼치기 — **자산 ID 는 trade ticker 소문자**
3. 각 자산의 `meta` / `recent` / `archive/{현재_연도}` 3 노드가 존재하는지 확인
4. 배열이 길 경우 검색창에 `/charts/prices/sso/recent/dates/0` 형태의 구체 경로로 값 확인

**실제 스키마** (from [chart_data.py](src/live/chart_data.py)):

```
/charts/prices/{sso|qld|gld|tlt}/
  ├─ meta      # first_date / last_date / ma_window / recent_months / archive_years
  ├─ recent    # dates / close / ma_value / upper_band / lower_band / 마커 4 종
  └─ archive/{YYYY}  # 연도별 slice
```

> Firebase RTDB 는 빈 배열을 저장하지 않으므로, `buy_signals` / `sell_signals` / `user_buys` / `user_sells` 가 모두 빈 상태라면 키 자체가 생성되지 않습니다. **보이지 않는 것이 정상**입니다.

**확인 사항**:

- [x] 4 개 자산 노드 `sso`, `qld`, `gld`, `tlt` 모두 존재 (`/charts/prices/` 하위)
- [x] 각 자산의 `meta` / `recent` / `archive/{현재_연도}` 3 노드 존재
- [x] `recent.dates`, `recent.close`, `recent.ma_value`, `recent.upper_band`, `recent.lower_band` 배열 길이 동일
- [x] `recent.ma_value` / `recent.upper_band` / `recent.lower_band` 의 워밍업 구간은 `null`
- [x] **구 경로 `/latest/chart_data/*` 는 더 이상 존재하지 않음** (Breaking change — reset 후 재생성 기준)

---

### 8. RTDB equity 차트 데이터 확인

**목적**: `/charts/equity/` 3 분할(meta + recent + archive/{YYYY}) RTDB 쓰기 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. RTDB 화면에서 `/charts/equity/` 펼치기
2. `meta` / `recent` / `archive/{현재_연도}` 3 노드가 존재하는지 확인
3. `recent` 의 배열 4 개 (`dates`, `model_equity`, `actual_equity`, `drift_pct`) 길이가 같은지 확인

**실제 스키마** (from [chart_data.py](src/live/chart_data.py) equity 빌더):

```
/charts/equity/
  ├─ meta            # first_date / last_date / recent_months / archive_years
  ├─ recent          # dates / model_equity / actual_equity / drift_pct
  └─ archive/{YYYY}  # 연도별 slice (구조는 recent 와 동일)
```

**확인 사항**:

- [x] `/charts/equity/meta` 의 `archive_years` 에 현재 연도가 포함됨
- [x] `/charts/equity/recent` 의 `dates` / `model_equity` / `actual_equity` / `drift_pct` 길이 동일
- [x] `/charts/equity/archive/{현재_연도}` 존재 (daily runner 가 매 실행 재생성)
- [x] `model_equity` / `actual_equity` 는 정수, `drift_pct` 는 0~1 범위의 소수점 4 자리
- [x] **구 경로 `/history/summary/*` 는 더 이상 존재하지 않음** (Breaking change — reset 후 재생성 기준)
- [x] `python -m live backfill-chart-archive --target equity --year <과거_연도>` 실행 후 해당 연도 archive 가 신규 생성/갱신됨

---

### 8b. RTDB `/history/*` 미러 (fills / balance_adjusts / signals) 확인

**목적**: `/history/fills/`, `/history/balance_adjusts/`, `/history/signals/` 3 경로가 daily runner 의 미러 쓰기로 채워지는지 확인 + `backfill-history` 명령으로 Git 정본 전체가 RTDB 에 복원되는지 확인.

**사전 조건**: 5 번 정상 완료. RTDB `/fills/inbox/` 또는 `/balance_adjust/inbox/` 에 새 레코드 1 건 이상 주입 후 `run-daily` 실행 (없으면 signals 만 검증 가능).

**절차**:

1. RTDB 화면에서 `/history/` 를 펼쳐 `fills/`, `balance_adjusts/`, `signals/` 3 노드 확인
2. `signals/{오늘_날짜}/` 하위에 4 자산 (`sso`, `qld`, `gld`, `tlt`) 모두 존재 확인
3. fill 을 새로 처리한 경우 `fills/{trade_date}/{UUID}/` 페이로드에 `applied_at` 포함 + `rtdb_key` 미포함 확인
4. balance_adjust 를 새로 처리한 경우 `balance_adjusts/{applied_at[:10]}/{UUID}/` 에 동일 검증

**확인 사항**:

- [ ] `/history/signals/{오늘_날짜}/{sso|qld|gld|tlt}` 4 자산 모두 존재 + `state` / `close` / `ma_value` / `ma_distance_pct` / `upper_band` / `lower_band` 필드 포함
- [ ] (fill 처리한 경우) `/history/fills/{trade_date}/{UUID}` 의 페이로드에 `applied_at` 존재, `rtdb_key` 미존재
- [ ] (balance_adjust 처리한 경우) `/history/balance_adjusts/{applied_at_date}/{UUID}` 페이로드 검증
- [ ] 같은 run-daily 배치에서 처리된 모든 신규 레코드의 `applied_at` 이 동일 timestamp

---

### 9. qbt-live-state 히스토리 파일 확인

**목적**: Step 15 `history` 의 파일 시스템 쓰기 + git push 검증.

**사전 조건**: 5 번 정상 완료.

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/qbt-live-state/tree/main/history` 접속
2. `history/daily/`, `history/states/`, `history/summary.jsonl` 존재 확인
3. `history/states/{실행 날짜}.json` 파일 내용을 같은 커밋의 `live_state.json` 과 비교

**확인 사항**:

- [x] `history/daily/{YYYY-MM-DD}.json` 파일 존재
- [x] `history/summary.jsonl` 파일에 `date`, `model_equity`, `actual_equity`, `drift_pct` 필드 포함된 줄 존재
- [x] `history/summary.jsonl` 마지막 줄이 최근 실행 날짜 요약
- [x] 같은 날짜로 재실행 시 `summary.jsonl` 줄 수가 1 증가 (덮어쓰기 아님 — 영구 보존 원칙 검증됨)
- [ ] `history/states/{실행 날짜}.json` 파일 존재 + 내용이 같은 커밋의 `live_state.json` 과 바이트 단위로 동일

---

### 10. RTDB 쓰기 권한 점검

**목적**: Firebase 콘솔에서 수동 쓰기/삭제가 규칙 위반 없이 수행되는지 확인.

**사전 조건**: 없음.

**절차**:

1. Firebase 콘솔 RTDB 화면에서 루트 노드 옆 **+** 클릭
2. 이름 `_debug_write_check`, 값 `"hello"` 로 추가
3. 방금 만든 노드 옆 **X** 로 삭제

**확인 사항**:

- [x] 쓰기가 permission_denied 없이 성공
- [x] 삭제도 성공

---

## Phase B: 운영 안정화 시뮬레이션

### 11. 데이터 검증 실패 시뮬레이션

**목적**: 데이터 검증 실패 시 자동 복구 없이 중단되는지 확인.

**검증 메커니즘**: `run-daily` 시작 시 `_refresh_live_csvs` → `_validate_against_csv` 가 yfinance 에서 받은 최근 5 거래일의 종가를 CSV 의 같은 날짜 종가와 비교합니다. 1% 이상 차이 나면 `RuntimeError("데이터 검증 실패: ...")` 로 중단 + 텔레그램 실패 알림 전송.

**사전 조건**:

- Phase A 완료
- 이 plan 에 따른 `_validate_against_csv` wiring 이 `main` 브랜치에 push 되어 있어야 함

**절차**:

1. 브라우저에서 `https://github.com/ingbeen/qbt-live-state/blob/main/data/stock/SPY.csv` 접속
2. 연필 아이콘 **Edit this file** 클릭
3. **최근 5 거래일 이내** 행의 종가를 1% 이상 임의로 변경 후 커밋 (예: `2026-04-10, ..., 450.12` → `..., 550.00`). 1 주일보다 오래된 행은 yfinance 가 반환하는 5 일 범위 밖이라 감지 안 됨
4. GitHub Actions `Daily Run` workflow_dispatch 수동 실행
   - `trade_date` 입력란에 최근 거래일 지정 (주말이면 `2026-04-10` 같은 금요일)
5. 검증 완료 후 해당 커밋을 GitHub 웹 Revert 로 원상복구

**확인 사항**:

- [x] Actions job 이 빨간 X 로 종료
- [x] 텔레그램에 `[QBT Live 실패]` 수신, 메시지에 `데이터 검증 실패: SPY 2026-04-10: 전일 종가 불일치` 형식 포함
- [x] `qbt-live-state` 리포에 `auto: live run-daily ...` 커밋이 **추가되지 않음** (실패 시 push 없음)
- [x] Revert 후 재실행 시 정상 동작 — 녹색 체크 + 새 커밋 push + 텔레그램 정상 알림

**참고 — 대체 감지 패턴**:

- `High < Low` 같은 OHLC 논리 위반: `_validate_against_csv` 의 첫 번째 검증 (`validate_ohlc_logic`) 에서 감지
- `Close = 0` 또는 음수: 동일하게 `validate_ohlc_logic` 감지. 단 이 케이스는 yfinance 원본에 실제로 없어서 재현이 어려움 — 재현하려면 `_make_recent_df` mock 을 써야 함 (단위 테스트 영역)

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

- [x] Actions job 이 빨간 X 로 종료
- [x] 텔레그램에 `[QBT Live 실패]` 수신 (`상태 파일 로드 실패: live_state.json 파싱 실패: ... Extra data: line 2 column 19`)
- [x] `qbt-live-state` 리포에 새 run-daily 커밋 없음 (실패 시 push 없음)
- [x] revert 후 다음 실행이 정상

---

### 13. keepalive commit 동작 확인

**목적**: GitHub Actions 의 **60일 비활성 정책** 으로부터 `daily_run.yml` 의 cron 스케줄을 보호하기 위한 keepalive 동작 검증. `quant` (퍼블릭) 리포에 월 1 회 빈 commit (`git commit --allow-empty`) 을 남겨 activity 를 유지한다.

**사전 조건**: `keepalive.yml` 배포 완료.

**절차**:

1. `https://github.com/ingbeen/quant/actions` → 좌측 `Keepalive` 워크플로우 선택
2. 실행 이력에서 매월 1 일자 실행 로그 확인
3. `quant` 리포 커밋 히스토리 (`https://github.com/ingbeen/quant/commits/main`) 에서 `keepalive: YYYY-MM-DD` 메시지 커밋 존재 여부 확인

**확인 사항**:

- [x] 매월 1 일 `Keepalive` 실행 로그 존재 (또는 workflow_dispatch 수동 실행)
- [x] 실행 결과 정상 (녹색)
- [x] `quant` 리포에 `keepalive: YYYY-MM-DD` 빈 commit 이 push 됨

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
poetry run python -m live notify-failure --message "FCM 수동 테스트"
```

**확인 사항**:

- [ ] 설치된 디바이스에서 FCM 푸시 알림 수신
- [ ] 알림 내용이 동일 시점 텔레그램 메시지와 포맷 일치

---

## 최종 완료 체크

- [ ] Phase A (1~10) 모두 완료
- [ ] Phase B (11~13) 모두 완료
- [ ] Phase C (14) 완료 — 앱 구현 후 진행
