# Implementation Plan: QBT Live - Step 10 CLI (cli.py)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 14:00
**관련 문서**: 설계서 부록 A, 11장, TODO Step 10

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: argparse subcommand 구조로 `live.cli` 진입점 구현
- [x] 목표 2: **핵심 명령어** 구현 — `init`, `run-daily`, `init-data`, `rebuild-data`, `drift`
- [x] 목표 3: **플레이스홀더 명령어** — `fetch-state`, `push-state`, `fetch-fills`, `history`, `notify-failure` (NotImplementedError 또는 후속 Step 에서 통합)
- [x] 목표 4: 에러 발생 시 자동 복구 없이 즉시 중단 + 알림 훅 호출 (Step 13 완성 전까지 mockable 함수 경유)
- [x] 목표 5: T-10.1 ~ T-10.3 테스트 통과

## 2) 비목표

- RTDB 통신 (Step 12)
- 알림 실제 발송 (Step 13)
- Git push/pull 실제 구현 (Step 11 GitHub Actions 에서 주로 처리)
- M-10.1~M-10.3 수동 테스트 (사용자 수행)

## 3) 배경/맥락

### 동기

- 설계서 부록 A 의 CLI 명령어 10 여 종을 묶어 매일 실행과 운영 유틸리티를 제공
- 핵심 흐름 `run-daily` 는 data_fetcher / data_validator / state / daily_runner / drift 를 통합
- 에러 발생 시 자동 복구 금지 원칙: 즉시 중단 + 실패 알림 훅 호출

### 설계 결정

#### D1. argparse subcommand 구조

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="live.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init")
    p_init.add_argument("--capital", type=float, required=True)
    p_init.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)

    # run-daily
    p_run = sub.add_parser("run-daily")
    p_run.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_run.add_argument("--trade-date", type=str)  # YYYY-MM-DD 생략 시 NYSE 기준 최근 거래일

    # ...

    args = parser.parse_args(argv)
    return _dispatch(args)
```

#### D2. `run-daily` 흐름

1. `load_state(state-dir/live_state.json)`
2. `load_applied_fill_ids(state-dir/applied_fill_ids.json)`
3. NYSE 달력으로 비거래일이면 종료 (설계서 4.2)
4. 각 자산 티커에 대해 `fetch_recent_ohlc` → 검증 → `append_today_to_csv`
   - 검증 실패 시 `_notify_failure` 호출 후 `ValueError` 전파
5. `load_csv` 후 MA 계산 (`add_single_moving_average` 재사용) → `market_bundle` 구성
6. `run_daily(trade_date, state, market_bundle, pending_fills=[], applied_fill_ids)` 호출
   - 현재는 `pending_fills=[]` 고정 (Step 12 에서 rtdb 연결)
7. 결과 `save_state` + `save_applied_fill_ids`
8. `cleanup_old_fill_ids` 후 재저장

#### D3. 에러 처리 — `@cli_exception_handler` + 내부 try

- CLI main 함수는 `@cli_exception_handler` 데코레이터 적용 → ValueError/RuntimeError 를 ERROR 로그 + exit 1
- 단, run-daily 실패 시 notify-failure 를 먼저 호출하고 예외를 재전파해야 한다
- `notify-failure` 는 Step 13 notifier 완성 전까지 placeholder 함수 (stdout 출력)

#### D4. 알림 훅 — `_notify_failure(message: str) -> None`

- 본 모듈에 **모듈 레벨 함수**로 정의
- 후속 Step (Step 13) 에서 실제 notifier.send_failure_all 로 교체
- 테스트에서는 monkeypatch 로 감시

#### D5. `init-data` / `rebuild-data` — yfinance 실호출

- scripts/ 실행 금지 규칙은 live 의 CLI 에도 적용되나, 본 명령들은 "사용자가 수동 실행" 하는 영역 (M-10.1~M-10.3). AI 는 테스트에서 mock 만 사용.
- `init-data`: 6 종 티커 모두 `rebuild_full_csv` 호출
- `rebuild-data`: 단일 티커 `rebuild_full_csv`

## 4) DoD

- [x] `live/src/live/cli.py` 구현 (핵심 + 플레이스홀더)
- [x] `live/tests/test_cli.py` 작성 및 통과 (T-10.1 ~ T-10.3)
- [x] `main(argv)` 가 argv 리스트를 인자로 받을 수 있는 구조 (테스트 용이)
- [x] `python -m live.cli` 실행 가능 (`__main__` 지원)
- [x] black + validate_project 통과
- [x] TODO Step 10 체크박스 체크
- [x] plan Done

## 5) 변경 범위

### 수정

- `live/src/live/cli.py` (구현)
- `docs/TODO_QBT_LIVE.md`

### 신규

- `live/src/live/__main__.py` (`python -m live.cli` 지원)
- `live/tests/test_cli.py`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] `test_cli.py`:
  - T-10.1: `init --capital 100000000` → `live_state.json` 파일 생성 + 4 자산 초기화
  - T-10.2: `run-daily` 도중 데이터 검증 실패 → ValueError 전파 + `_notify_failure` 호출 확인
  - T-10.3: `run-daily` 도중 run_daily 계산 실패 (RuntimeError) → 전파 + 상태 파일 변경 없음 확인
  - 보조: `main(["init", "--capital", ...])` 호출 시 exit code 0
  - 보조: 파싱 에러 시 exit code 0 이 아님

### Phase 1 — 구현

- [x] `live/src/live/__main__.py` — `if __name__ == "__main__": sys.exit(main())`
- [x] `live/src/live/cli.py`:
  - `_notify_failure(message)` 플레이스홀더
  - `_cmd_init(args) -> int`
  - `_cmd_run_daily(args) -> int`
  - `_cmd_init_data(args) -> int`
  - `_cmd_rebuild_data(args) -> int`
  - `_cmd_drift(args) -> int`
  - `_cmd_placeholder(args)` — fetch-state / push-state / fetch-fills / history / notify-failure 통합 (후속 Step 에서 개별 구현)
  - `main(argv=None)` — argparse + dispatch

### Phase 2 — 문서 동기화

- [x] TODO Step 10 체크박스 체크

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=697, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / CLI 진입점 + run-daily 통합 (Step 10)`
2. `live / cli.py — init / run-daily / init-data / rebuild-data / drift`
3. `live / Step 10 argparse subcommand + 실패 알림 훅`
4. `live / CLI T-10.1~T-10.3 + __main__ 모듈`
5. `live / live.cli 통합 진입점`

## 7) 리스크

- 플레이스홀더 명령어 (fetch-state/push-state 등) 는 Step 12+ 에서 완성. 지금은 NotImplementedError 가 아닌 "명령 미구현" 메시지 + exit 1
- run-daily 의 실제 통합 흐름은 CSV append + 검증 + daily_runner 이므로 테스트에서는 monkeypatch 로 외부 호출을 감시

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:00: 계획서 작성
