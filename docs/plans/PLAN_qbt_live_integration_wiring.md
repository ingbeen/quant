# Implementation Plan: QBT Live - 통합 보강 (integration wiring)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**범위 표시**: 본 plan 은 TODO_QBT_LIVE.md 의 Step 번호와 무관한 "통합 보강" 작업이다.
TODO Step 1~15 의 모듈들을 실제 흐름으로 연결한다 (Phase 3 앱 개발 진입 조건).

---

**작성일**: 2026-04-11 14:30
**관련 문서**: 설계서 4.2, 6장, 8장, 10장, 11장 / 사용자 결정 (CLI 통합 → 앱 개발 순)

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만 실행
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `daily_runner.run_daily` 가 `drift.apply_fills_idempotent` 를 호출하여 actual 축을 갱신
- [x] 목표 2: `cli.run-daily` 가 RTDB / notifier / chart_data / history 모듈을 모두 호출하는 통합 흐름 구현
- [x] 목표 3: `cli.py` placeholder 명령어 5종 실제 구현 (`fetch-state`, `push-state`, `fetch-fills`, `history`, `notify-failure`)
- [x] 목표 4: 외부 호출은 `--no-rtdb`, `--no-notify` 옵션으로 비활성화 가능 (오프라인 dry-run / 테스트 격리)
- [x] 목표 5: 통합 후 회귀 검증 (`test_regression.py` 통과 유지)
- [x] 목표 6: 통합 흐름의 단위/통합 테스트 추가

## 2) 비목표

- React Native 앱 개발 (Phase 3 Step 16~21)
- 실제 GitHub Actions 5거래일 운영 검증 (사용자 운영 영역)
- 운영 안정화 (Phase 5)

## 3) 배경/맥락

### 동기

Step 1~15 에서 각 모듈이 독립적으로 구현되었으나, `daily_runner` 와 `cli.run-daily` 가 후속 모듈들을 실제로 호출하지 않아 RTDB / 알림 / 히스토리가 비어있다. Phase 3 앱 개발이 RTDB 에 의존하므로 본 통합 보강 없이는 앱 검증이 불가능하다.

### 통합 흐름 (설계서 4.2 전체)

```
1. (옵션) git pull qbt-live-state            <-- fetch-state
2. exchange_calendars 휴장 체크
3. live_state.json 로드 + applied_fill_ids 로드
4. yfinance 5일 → 검증 → CSV append
5. CSV 전체 → MA 계산 → market_bundle 구성
6. RTDB Firebase App 초기화
7. RTDB /fills/inbox → unprocessed fills 가져오기
8. run_daily(trade_date, state, bundle, fills, applied_ids)
   ├─ 내부: drift.apply_fills_idempotent (fills → actual 축 갱신)
   └─ 내부: 기존 model 축 흐름 (signal/projected/rebalance/merge/pending)
9. 결과 state 저장 + applied_ids 정리/저장
10. RTDB mark_fills_processed
11. chart_data.build_chart_series → RTDB write_chart_data
12. RTDB write_read_model (portfolio/signals/pending/drift/history)
13. history.save_daily_log + append_summary
14. (옵션) git add/commit/push qbt-live-state  <-- push-state
15. notifier.read_device_tokens → notifier.send_all (FCM + 텔레그램)
16. 만료 토큰 → notifier.remove_invalid_tokens

에러 시 (어느 단계든):
- notifier.send_failure_all 호출 (read_device_tokens 에서 실패하면 토큰 빈 리스트로 시도)
- 예외 재전파 → exit 1
```

### 설계 결정

#### D1. `daily_runner.run_daily` 의 fill 통합

- 함수 시그니처는 변경하지 않는다 (`pending_fills` 와 `applied_fill_ids` 는 이미 입력 파라미터).
- 내부에서 첫 단계로 `drift.apply_fills_idempotent(state, pending_fills, applied_fill_ids)` 호출.
- `DailyResult.updated_state` 와 `DailyResult.updated_applied_fill_ids` 에 fill 처리 결과 반영.
- **회귀 영향**: 빈 fill 리스트 → 동작 동일 (회귀 검증 유지).

#### D2. `cli.run-daily` 의 통합 흐름

- `_cmd_run_daily` 를 단계별 헬퍼로 분리하여 가독성 확보:
  - `_load_or_init_state(state_dir)`
  - `_check_trading_day(trade_date, calendar)`
  - `_fetch_and_validate_csvs(state_dir, trade_date)`
  - `_build_bundle(state_dir)`
  - `_load_rtdb_app(no_rtdb)` — `None` 이면 RTDB 비활성화
  - `_fetch_fills(rtdb_app)` — RTDB 비활성 시 빈 리스트
  - `_persist_state(state, applied_ids, state_dir)`
  - `_publish_to_rtdb(rtdb_app, state, result, bundle, history_dir)`
  - `_send_notifications(rtdb_app, result, no_notify)`
- 어떤 단계든 예외 발생 시: `_safe_notify_failure(rtdb_app, message)` 호출 후 재전파

#### D3. `--no-rtdb` / `--no-notify` 플래그

- `--no-rtdb`: Firebase 호출을 모두 skip. 로컬 dry-run 용도.
- `--no-notify`: notifier.send_all skip. 테스트 / 디버깅 용도.
- 두 플래그 모두 기본값 False (운영 환경은 모두 활성화).

#### D4. placeholder 명령어 실구현

| 명령어 | 동작 |
|---|---|
| `fetch-state` | `subprocess.run(["git", "-C", state_dir, "pull"])` |
| `push-state` | `git add -A` + `git commit -m "auto: ..."` + `git push` (변경 없으면 skip) |
| `fetch-fills` | RTDB 에서 unprocessed fills 가져와 stdout 출력 |
| `history` | `history/summary.jsonl` 의 최근 N 줄 출력 |
| `notify-failure` | `notifier.send_failure_all` 호출 (수동 알림 발송) |

#### D5. RTDB URL / 자격증명

- 환경변수:
  - `GOOGLE_APPLICATION_CREDENTIALS`: 서비스 계정 JSON 경로
  - `FIREBASE_DB_URL`: 기본값 `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: 텔레그램 발송용
- 미설정 시 RTDB 초기화 실패 → 정중하게 에러 메시지

## 4) DoD

- [x] `daily_runner.run_daily` 에 fill 처리 통합 (`apply_fills_idempotent` 호출)
- [x] `cli.run-daily` 에 RTDB / notifier / chart_data / history 통합 흐름 구현
- [x] `cli.py` 5종 placeholder 명령 실구현
- [x] `--no-rtdb`, `--no-notify` 옵션 추가
- [x] 통합 단위 테스트 (모든 외부 호출 mock)
- [x] 회귀 검증 (`test_regression.py`) 통과 유지
- [x] black + validate_project 통과
- [x] plan Done

## 5) 변경 범위

### 수정

- `live/src/live/daily_runner.py` — fill 처리 통합
- `live/src/live/cli.py` — run-daily 통합 + placeholder 실구현
- `live/tests/test_daily_runner.py` — fill 통합 테스트 추가
- `live/tests/test_cli.py` — 통합 흐름 + placeholder 명령 테스트 추가

### 신규

- `live/src/live/git_state.py` (선택, fetch/push 로직 분리)

### 미수정

- 기타 모듈 (`drift`, `rtdb_gateway`, `notifier`, `chart_data`, `history`, `state`, `data_fetcher`, `data_validator`) — 모두 그대로 재사용

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 회귀 baseline 확인

- [x] 현재 `test_regression.py` 통과 확인 (변경 후 같은 결과 나와야 함)

### Phase 1 — daily_runner fill 통합

- [x] `run_daily` 시작부에 `apply_fills_idempotent` 호출 추가
- [x] working_state 와 working_applied_ids 를 fill 처리 결과로 교체
- [x] DailyResult.updated_applied_fill_ids 가 새 dict 가리키도록
- [x] test_daily_runner.py 에 fill 통합 케이스 1~2 개 추가:
  - 빈 fill 리스트 → 기존 동작 동일
  - 1 개 fill 입력 → actual 갱신 + applied_ids 에 키 추가

### Phase 2 — git 헬퍼 분리 (선택)

- [x] `git_state.py` 신규: `git_pull(state_dir)`, `git_commit_and_push(state_dir, message)`
- [x] subprocess 기반, 실패 시 RuntimeError

### Phase 3 — cli.run-daily 통합 흐름

- [x] `_cmd_run_daily` 를 단계별 헬퍼로 분리
- [x] RTDB 초기화 / fills 가져오기 / mark / write_read_model / write_chart_data 통합
- [x] history 저장 통합
- [x] notifier 통합 (알림 발송 + 만료 토큰 정리)
- [x] `--no-rtdb`, `--no-notify` 플래그 추가
- [x] 에러 시 `_safe_notify_failure` 로 알림 후 재전파

### Phase 4 — placeholder 명령 실구현

- [x] `_cmd_fetch_state` — git pull
- [x] `_cmd_push_state` — git add/commit/push
- [x] `_cmd_fetch_fills` — RTDB 조회 + 출력
- [x] `_cmd_history` — summary.jsonl 최근 N 줄 출력
- [x] `_cmd_notify_failure` — `notifier.send_failure_all` 호출
- [x] `_build_parser` 에서 placeholder 매핑 제거하고 개별 함수 연결

### Phase 5 — 테스트 + 검증

- [x] test_daily_runner.py 에 fill 통합 테스트 추가
- [x] test_cli.py 에 통합 흐름 / placeholder 명령 테스트 추가
- [x] 회귀 검증 통과 확인 (test_regression.py)
- [x] black + validate_project 통과

**Validation**: `poetry run python validate_project.py` (passed=775, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / 통합 보강 — daily_runner + cli end-to-end (CLI integration wiring)`
2. `live / run_daily fill 처리 + cli RTDB/notifier/history 통합`
3. `live / cli.run-daily 종단 흐름 + placeholder 명령 실구현`
4. `live / Phase 3 진입 조건 (통합 보강) 완료`
5. `live / fetch-state/push-state/fetch-fills/history/notify-failure 실구현`

## 7) 리스크

- **회귀 검증 깨질 가능성**: `daily_runner` 변경으로 기존 로직이 흐트러질 수 있음
  - 완화책: 빈 fill 입력 시 동작이 동일하도록 fill 처리를 함수 시작부에 배치하고 noop 경로 우선 보장
- **Firebase Admin SDK 초기화 복잡성**: 같은 process 에서 두 번 호출 시 `ValueError` 발생
  - 완화책: lazy 초기화 + try/except 로 기존 app 재사용
- **git subprocess 의존**: GitHub Actions 외 환경에서는 git 인증 필요
  - 완화책: 본 plan 은 subprocess 만 호출하고 자격증명은 호출자(GitHub Actions) 책임
- **테스트에서 firebase_admin 실제 import 발생**: lazy import 가 아닌 곳이 있으면 mock 어려움
  - 완화책: rtdb_gateway / notifier 모두 함수 내부 lazy import 유지

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:30: 계획서 작성 + 구현 시작
