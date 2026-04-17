# Implementation Plan: RTDB `/history/` 확장 — fills / balance_adjusts / signals 이력 영구 보존

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-17 18:10
**마지막 업데이트**: 2026-04-17 19:30
**관련 범위**: live (RTDB `/history/` 트리 / Git 정본 JSONL 스키마 / CLI 파이프라인)
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py)
- [src/live/cli.py](../../src/live/cli.py)
- [src/live/history.py](../../src/live/history.py)
- [src/live/models.py](../../src/live/models.py)
- [src/live/constants.py](../../src/live/constants.py)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] RTDB `/history/` 하위에 `fills` / `balance_adjusts` / `signals` 3 경로를 신규 추가하고, **영구 보존** (rolling 삭제 / cleanup 없음) 한다.
- [x] Git 정본 JSONL 3 종 (`user_trades.jsonl` / `balance_adjusts.jsonl` / `signals.jsonl`) 의 스키마를 RTDB 페이로드와 동등한 정보량을 갖도록 확장한다 (A안: 누락 필드 추가).
- [x] `run-daily` 가 이번 실행에서 **새로 적용된** fill / balance_adjust 만 RTDB `/history/` 에 미러하고, signals 는 당일 4 자산 전체를 매번 덮어쓴다 (idempotent).
- [x] `applied_at` 은 `run-daily` 진입 시점의 단일 KST ISO timestamp 로 결정되어 **이번 실행에서 새로 적용된 모든 레코드에 동일 값** 으로 부여된다 (배치 단위 통일).
- [x] `backfill-history --target fills|balance_adjusts|signals|all` CLI 신규 추가 — Git 정본 JSONL 을 전체 읽어 RTDB 의 대응 경로에 일괄 기록한다 (`--dry-run` 옵션 포함).
- [x] `reset` CLI 의 RTDB 초기화 경로 목록에 `/history` 최상위를 추가하여, 리셋 후 신규 3 경로가 깨끗이 비워진다.

## 2) 비목표(Non-Goals)

- **`/history/fill_dismisses/` 신설 금지** — fill_dismiss 는 "리마인더 해제" 관리 행위이며 앱에서 조회할 이력 수요가 없다. Git 정본 (`fill_dismisses.jsonl` + `applied_fill_dismiss_ids.json`) 만 유지.
- **rolling 삭제 / retention 상수 / cleanup 함수 도입 금지** — 영구 보존이 단일 정책. Firebase Spark 한도(1 GB) 대비 10 년 누적 ~수 MB 로 충분.
- **Git 정본을 RTDB 의 백업으로 취급 금지** — Git 이 단일 정본, RTDB 는 미러. 리셋 후 `backfill-history --target all` 로 재생성 가능해야 함.
- **`/history/summary/` 부활 금지** — Plan 2 에서 제거 완료. equity 시계열은 `/charts/equity/` 가 흡수.
- **`applied_*_ids.json` 3 파일 통합 금지** — 사용자 결정으로 현재 3 파일 유지.
- **`daily_runner.run_daily()` 순수 계산 변경 금지** — RTDB I/O 는 cli 계층에서만.
- **`ActualFill` / `BalanceAdjust` / `SignalDetection` dataclass 정의 변경 금지** — 본 plan 에서 신규 필드 도입 없음.
- **`load_user_trades` / `load_signal_history` 의 차트 마커 빌더 동작 변경 금지** — 새 필드는 무시하고 기존 필드만 추출 (호환).
- **공통 예외 훅 / ephemeral shallow clone / `/latest/*` / `/charts/*` / `/fills/inbox/*` / `/balance_adjust/inbox/*` / `/fill_dismiss/inbox/*` / `/device_tokens/`** — 변경 없음.
- **앱(Android) 구현** — 본 plan 범위 밖. 본 plan 은 신규 RTDB 경로의 페이로드 계약 정의까지만.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

Plan 2 (`PLAN_LIVE_CHARTS_RESTRUCTURE`) 적용 후 `/history/` 하위가 완전히 비었다. 그러나 운영자가 일상적으로 던지는 다음과 같은 이력성 질의는 앱에서 답할 수 없다:

1. "지난달 언제 SSO 를 얼마에 샀지?" — 체결 이력
2. "최근에 잔고 보정한 적 있나?" — 보정 이력
3. "이번 주 어떤 시그널이 떴지?" — 신호 이력

현재 운영자는 이 질의에 답하기 위해 `qbt-live-state` 리포의 JSONL 파일을 직접 열어봐야 한다. 앱에서는 조회 불가. Git 이 유일 정본이라는 원칙은 유지하되, 앱이 읽을 수 있도록 RTDB 에 **미러** 를 두면 된다.

체결 빈도는 월 ~10 건, 신호는 일 최대 4 건 수준이라 RTDB Spark 무료 한도 내에서 영구 보존이 가능하다.

### Git 정본 JSONL 스키마 확장 (A안 결정)

Plan 본문이 요구하는 RTDB 페이로드 (`actual_price`, `actual_shares`, `ma_value`, `upper_band` 등) 는 현재 JSONL 에 없다. 사용자 결정에 따라 **A안 (스키마 확장)** 으로 진행한다.

- 차트 마커 전용 빌더 (`load_user_trades` / `load_signal_history`) 는 필요한 필드만 추출하므로 기존 동작 그대로 유지된다.
- 과거 JSONL 줄 (확장 전 기록) 은 옛 스키마 그대로 남으며, backfill 시 누락 필드는 `null` 로 채운다.

### `applied_at` 결정 규칙

`run-daily` 진입 직후 1 회 계산한 KST ISO 8601 문자열 (예: `"2026-04-11T07:27:15+09:00"`) 을 이번 실행에서 새로 적용된 모든 fill / balance_adjust 의 `applied_at` 으로 동일하게 부여한다. 마이크로초 단위 구분은 하지 않는다 (배치 통일 = 직관적, `input_time_kst` 와 명확히 구분).

### 최종 RTDB `/history/` 구조

```
/history/
├── fills/
│   └── {YYYY-MM-DD}/                    ← 키: ActualFill.trade_date
│       └── {UUID}: {                    ← 키: ActualFill.rtdb_key
│             asset_id, direction, actual_price, actual_shares,
│             trade_date, input_time_kst, memo, reason, applied_at
│           }
├── balance_adjusts/
│   └── {YYYY-MM-DD}/                    ← 키: applied_at 의 날짜 부분
│       └── {UUID}: {                    ← 키: BalanceAdjust.rtdb_key
│             asset_id, new_shares, new_avg_price, new_entry_date,
│             new_cash, reason, input_time_kst, applied_at
│           }
└── signals/
    └── {YYYY-MM-DD}/                    ← 키: execution_date
        └── {asset_id}: {                ← 키: 자산 ID 소문자 (sso/qld/gld/tlt)
              state, close, ma_value, ma_distance_pct,
              upper_band, lower_band
            }
```

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 / 장애 대응 원칙 / 출력 정밀도(`ROUND_PRICE` / `ROUND_RATIO`) / Path 사용 원칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 아키텍처 / 자동 복구 금지 + 무조건 알림 / QBT 본체 수정 금지 / 순수 계산·I/O 분리 / qbt 상수 재사용 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / 파일 I/O 격리 / 결정적 테스트 / 외부 네트워크 mock
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — §8.2 RTDB 경로 / §8.3 역할 분리

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `rtdb_gateway.py` 에 `write_history_fills` / `write_history_balance_adjusts` / `write_history_signals` 3 함수가 추가되었고 `__all__` 에 포함되었다 (+ backfill 전용 `*_raw` 3 함수).
- [x] 3 함수는 모두 같은 키 (날짜 폴더 / UUID / asset_id) 재호출 시 덮어쓰기로 동작한다 (idempotent, 테스트로 강제).
- [x] `write_history_fills` / `write_history_balance_adjusts` 는 빈 리스트 입력 시 RTDB 호출이 발생하지 않는다 (no-op, 테스트로 강제).
- [x] `cli._cmd_run_daily` 가 이번 실행에서 새로 적용된 fill / balance_adjust 만 RTDB `/history/` 에 기록하고, signals 는 당일 전체를 덮어쓴다.
- [x] `applied_at` 은 `run-daily` 진입 시점의 KST ISO timestamp 로 단일 결정되어, 이번 실행의 모든 신규 적용 레코드에 동일 값으로 부여된다.
- [x] Git 정본 JSONL 3 종 (`user_trades.jsonl` / `balance_adjusts.jsonl` / `signals.jsonl`) 이 RTDB 페이로드와 동등한 정보량으로 확장되었다 (신규 줄 한정).
- [x] `load_user_trades` / `load_signal_history` 는 새 필드를 무시하고 기존 차트 마커 동작을 그대로 유지한다 (기존 테스트 그린).
- [x] `backfill-history --target fills|balance_adjusts|signals|all [--dry-run]` CLI 가 동작한다.
- [x] `backfill-history` 는 옛 스키마 줄 (`rtdb_key`/`applied_at` 누락) 을 skip 카운트로 처리한다.
- [x] `reset` CLI 의 RTDB 초기화 경로 목록에 `/history` 가 추가되어, 리셋 후 신규 3 경로가 비어 있다.
- [x] 신규 단위 테스트가 추가되었다 (gateway / cli / history 빌더).
- [x] 기존 `_publish_to_rtdb` / `run-daily` 통합 테스트가 신규 경로 검증을 포함하도록 수정되었다.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 의 모듈별 역할 표가 신규 함수 / CLI 를 반영한다.
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §8.2 / §8.3 이 신규 경로를 반영한다.
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) Phase A 에 수동 확인 절차가 추가되었다.
- [x] `poetry run python validate_project.py` 통과 (passed=995, failed=0, skipped=0).
- [x] `poetry run black .` 실행 완료 (마지막 Phase, 146 files unchanged).
- [x] `README.md` 변경 없음 — 실행 명령어 / 환경변수 변경 없음.
- [x] plan 체크박스 최신화 (Phase / DoD / Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/constants.py](../../src/live/constants.py)
  - 신규 상수: `HISTORY_FILLS_SUBDIR = "fills"`, `HISTORY_BALANCE_ADJUSTS_SUBDIR = "balance_adjusts"`, `HISTORY_SIGNALS_SUBDIR = "signals"` 추가 — RTDB `/history/{*}` 의 1 단계 경로명. (주: Git 정본 JSONL 파일명 상수와는 별개. JSONL 은 단일 파일이고, RTDB 는 날짜 폴더 단위.)
  - 또는 `rtdb_gateway.py` 내부 모듈 상수로만 두는 것도 검토 (외부에서 재사용할 일 없으면 모듈 private 로 두는 쪽 우선).
- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py)
  - `_HISTORY_PATH = "/history"` 모듈 상수 추가.
  - `write_history_fills(app, fills, applied_at)` 신규 — `fills` 는 `list[ActualFill]`, 빈 리스트면 no-op. 각 fill 을 `/history/fills/{trade_date}/{rtdb_key}` 에 dict 로 기록. payload 는 `asdict(fill)` 에서 `rtdb_key` 제거 + `applied_at` 추가.
  - `write_history_balance_adjusts(app, adjusts, applied_at)` 신규 — `adjusts` 는 `list[BalanceAdjust]`, 빈 리스트면 no-op. 폴더 키는 `applied_at` 의 날짜 부분 (`YYYY-MM-DD` 슬라이스). payload 는 `asdict(adjust)` 에서 `rtdb_key` 제거 + `applied_at` 추가.
  - `write_history_signals(app, execution_date, signals)` 신규 — `signals` 는 `dict[str, SignalDetection]`. 항상 4 자산 전체 덮어쓰기. payload 는 `asdict(signal)`.
  - `__all__` 에 3 함수 추가.
  - `delete_all_except_device_tokens` 의 `paths_to_delete` 에 `_HISTORY_PATH` 추가.
- [src/live/cli.py](../../src/live/cli.py)
  - `_cmd_run_daily` 본문 상단에 `applied_at_kst = _now_kst_iso()` 변수 도입 (이번 실행 통일 timestamp).
    - 기존 `_now_kst_for_commit()` 와 다른 이유: 후자는 커밋 메시지 표기용 (`YYYY-MM-DD HH:MM:SS KST`) 이고 `applied_at` 은 ISO 8601 (`+09:00` 오프셋 포함). `state.py._now_kst_iso` 패턴과 일치시킨다 (cli 내부 헬퍼로 import 또는 신규 정의).
  - 신규 적용된 fill / balance_adjust 분기에서 RTDB 미러 호출 추가:
    - `newly_applied_ids` 식별 직후 `pending_fills` 에서 신규 fill 들을 골라 `write_history_fills(rtdb_app, newly_fills, applied_at_kst)` 호출.
    - `newly_applied_adjust_keys` 식별 직후 `pending_adjusts` 에서 신규 adjust 들을 골라 `write_history_balance_adjusts(rtdb_app, newly_adjusts, applied_at_kst)` 호출.
  - `_publish_to_rtdb` 끝부분에 `write_history_signals(rtdb_app, execution_date, result.signals)` 호출 추가 (당일 4 자산 전체 덮어쓰기).
  - JSONL append 호출의 dict 페이로드를 확장된 스키마로 업데이트:
    - `append_user_trade` 호출: `actual_price` / `actual_shares` / `trade_date` / `input_time_kst` / `memo` / `reason` / `rtdb_key` / `applied_at` 추가.
    - `append_balance_adjust` 호출: `applied_at` 추가.
    - `append_signal_history` 호출: `close` / `ma_value` / `ma_distance_pct` / `upper_band` / `lower_band` 추가.
  - `_cmd_backfill_history` 신규 — `--target {fills|balance_adjusts|signals|all}` + `--dry-run`. ephemeral state repo clone (read-only). JSONL 전체 로드 → 대상 경로에 일괄 기록. 옛 줄 (누락 필드) 은 `null` 로 채워 기록.
  - `_cmd_reset` — gateway 변경에 따라 cli 본문 수정 거의 없음 (경로 목록은 gateway 내부).
  - argparse 등록: `backfill-history` subparser 추가.
- [src/live/history.py](../../src/live/history.py)
  - `load_user_trades` / `load_signal_history` — 새 필드는 **무시** (기존 차트 마커 빌더 호환). 본문 변경 거의 없음. 다만 `load_user_trades` 가 `UserTrade` dataclass 만 반환하므로 backfill 용 raw dict 로더 신규 필요:
    - `load_user_trades_raw(history_dir) -> list[dict[str, Any]]` 신규 — JSONL 각 줄을 dict 그대로 반환 (backfill 용).
    - `load_balance_adjusts_raw(history_dir) -> list[dict[str, Any]]` 신규.
    - `load_signal_history_raw(history_dir) -> list[dict[str, Any]]` 신규.
  - 손상 JSONL 처리는 기존 `RuntimeError("손상된 JSONL ...")` 패턴 그대로.
  - docstring 의 "파일 종류" / 각 append 함수 docstring 에 확장된 스키마 명시.
- [src/live/models.py](../../src/live/models.py) — **변경 없음**. `ActualFill` / `BalanceAdjust` / `SignalDetection` 모두 그대로 사용.
- [src/live/daily_runner.py](../../src/live/daily_runner.py) — **변경 없음**. 순수 계산 영향 없음.
- [src/live/state.py](../../src/live/state.py) — **변경 없음**.
- [tests/live/test_rtdb_gateway.py](../../tests/live/test_rtdb_gateway.py)
  - `TestWriteHistoryFills` 신규 — 빈 리스트 no-op / 단일 fill 기록 / 다수 fill 기록 / 같은 UUID 덮어쓰기 / 페이로드에 `applied_at` 포함 + `rtdb_key` 미포함.
  - `TestWriteHistoryBalanceAdjusts` 신규 — 빈 리스트 no-op / 폴더 키가 `applied_at` 의 날짜 부분 / 페이로드 검증.
  - `TestWriteHistorySignals` 신규 — 4 자산 일괄 덮어쓰기 / 같은 자산 재호출 시 덮어쓰기 / 페이로드 필드 검증.
  - `TestDeleteAllExceptDeviceTokens` — `_HISTORY_PATH` 가 삭제 목록에 포함되었는지 assert 추가.
- [tests/live/test_cli.py](../../tests/live/test_cli.py)
  - `_publish_to_rtdb` / `run-daily` 통합 테스트에서 `write_history_signals` 호출이 4 자산 페이로드로 발생하는지 검증.
  - 이번 실행에서 새로 적용된 fill / adjust 만 `write_history_*` 에 전달되는지 검증 (이미 `applied_*_ids` 에 있던 키는 제외).
  - JSONL append payload 가 확장된 스키마 (모든 필드 포함) 인지 assert.
  - `backfill-history` subcommand 시나리오: `--target fills|balance_adjusts|signals|all`, `--dry-run`, 누락 필드 → null, JSONL 미존재 시 동작.
- [tests/live/test_history.py](../../tests/live/test_history.py)
  - 신규 `*_raw` 로더 테스트: 빈 / 정상 / 옛 스키마 (누락 필드) / 손상 JSONL.
  - 기존 `load_user_trades` / `load_signal_history` 가 새 필드를 무시하는 회귀 테스트 추가.
- [tests/live/test_constants.py](../../tests/live/test_constants.py)
  - 신규 상수가 추가되었다면 (또는 모듈 private 로 두지 않았다면) 노출 여부 / 값 스모크 테스트 1 건.
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
  - §8.2 상단 트리에 `/history/fills/`, `/history/balance_adjusts/`, `/history/signals/` 3 경로 노드 추가.
  - 각 경로의 신규 섹션 추가 (payload 표 / 예시 / 보존 정책 (영구) / idempotency 규칙 / 키 전략).
  - §8.3 역할 분리 표 갱신 (쓰기: daily runner, 읽기: 앱).
  - §1.1 다이어그램에 `/history/{fills|balance_adjusts|signals}` 노드 추가.
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
  - 모듈별 역할 표의 `rtdb_gateway.py` / `cli.py` / `history.py` 설명 갱신.
  - "주요 명령어" 또는 별도 섹션에 `backfill-history` 추가.
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)
  - Phase A 수동 확인 절차:
    - run-daily 실행 후 Firebase 콘솔에서 `/history/fills/{오늘날짜}/`, `/history/balance_adjusts/{오늘날짜}/`, `/history/signals/{오늘날짜}/{sso|qld|gld|tlt}` 존재 확인.
    - `backfill-history --target all` 실행 후 Git 전체 이력이 RTDB 에 반영되는지 확인.
    - `reset` 후 `/history/*` 가 비어있는지 + `backfill-history --target all` 로 복원 가능한지 확인.
- `README.md`: **변경 없음** — 실행 명령어 / 환경변수 / 외부 계약 불변.

### 데이터/결과 영향

- **RTDB**: `/history/` 하위 신규 3 경로. Plan 2 에서 비워진 이후 첫 추가. 앱 미구현 — 현재 소비자 없음.
- **Git 정본 JSONL 스키마 확장 (A안)**: 신규 줄은 풍부한 페이로드, 과거 줄은 옛 스키마. backfill 시 누락 필드는 `null`. **append-only 원칙 유지** — 과거 줄을 다시 쓰지 않는다.
- **Firebase Spark 한도**: 월 ~10 fill + 일 4 signals × 252 거래일 × 10 년 ≈ 수 MB. 1 GB 한도 대비 충분.
- **출력 정밀도**: RTDB 페이로드는 `ROUND_PRICE` / `ROUND_RATIO` 등 기존 정밀도 규칙을 그대로 따른다 (저장 직전 반올림). 비즈니스 계산 정밀도 변경 없음.
- **부분 성공 시 자기 수렴**: 다음 `run-daily` 가 signals 를 덮어쓰고, fills / balance_adjusts 는 idempotency 로 동일 UUID 재시도 시 덮어씀. 트랜잭션 / 롤백 / 자동 재시도 도입하지 않음 (원칙 1).

## 6) 단계별 계획(Phases)

> 이 plan 은 인바리언트 / 지표 정의 / 에러 정책을 변경하지 않는다. 자동 복구 금지 / 무조건 알림 / 순수 계산·I/O 분리 / 반올림 규칙 모두 그대로 유지한다. 따라서 Phase 0 (레드) 은 두지 않고, "데이터 계층 → CLI 통합 → backfill CLI → 문서/검증" 순으로 Phase 1 / 2 / 3 / 마지막 Phase 로 나눈다.

---

### Phase 1 — 데이터 계층 ("RTDB gateway 함수 + JSONL 스키마 확장 + raw 로더")

**목표**: cli 변경 전에 RTDB 쓰기 함수 / JSONL raw 로더 / 확장 스키마를 모두 그린 상태로 만든다. 이 Phase 종료 시점에는 cli 가 아직 호출하지 않으므로 동작 흐름은 변하지 않는다.

**작업 내용**:

- [x] [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) — `_HISTORY_PATH` / 3 경로 상수 + `write_history_fills` / `write_history_balance_adjusts` / `write_history_signals` + `delete_all_except_device_tokens` 갱신.
- [x] [src/live/history.py](../../src/live/history.py) — `load_user_trades_raw` / `load_balance_adjusts_raw` / `load_signal_history_raw` 추가 + docstring "확장 스키마" 명시.
- [x] 신규 / 갱신 테스트: `TestWriteHistoryFills` (5건) / `TestWriteHistoryBalanceAdjusts` (4건) / `TestWriteHistorySignals` (3건) / `TestDeleteAllExceptDeviceTokens` (1건) / `TestLoad*Raw` 3 클래스 / `TestChartMarkerBuildersIgnoreExtraFields` (회귀).
- [x] `pytest tests/live/test_rtdb_gateway.py tests/live/test_history.py` 그린 (82건).

---

### Phase 2 — CLI 통합 ("run-daily 미러 + JSONL 페이로드 확장 + reset 갱신")

**목표**: `run-daily` 가 매 실행마다 (a) 신규 fill / balance_adjust 를 RTDB `/history/` 에 미러하고, (b) 당일 signals 4 자산을 덮어쓰고, (c) Git 정본 JSONL 에 확장된 스키마로 append 하도록 한다. `reset` 은 gateway 변경 자동 반영 (paths_to_delete) 으로 동작 변경 없음.

**작업 내용**:

- [x] [src/live/cli.py](../../src/live/cli.py) — `_now_kst_iso()` 헬퍼 + `_cmd_run_daily` 진입 시 단일 `applied_at_kst` 산출 + `write_history_fills` / `write_history_balance_adjusts` 호출 + `_publish_to_rtdb` 끝에 `write_history_signals` 호출 + JSONL append 페이로드 확장 (user_trades / balance_adjusts / signals).
- [x] 테스트 갱신 (`tests/live/test_cli.py`) — `_publish_to_rtdb` 의 `write_history_signals` assert / `run-daily` 통합 시나리오의 `write_history_fills` / `write_history_balance_adjusts` 호출 + `applied_at` 통일 / JSONL 확장 필드 assert.
- [x] `pytest tests/live/` 전체 480건 그린.

---

### Phase 3 — `backfill-history` CLI 신규 추가

**목표**: 최초 배포 직후 / 리셋 후 복원에 사용할 `backfill-history` 명령을 신설한다.

**작업 내용**:

- [x] [src/live/cli.py](../../src/live/cli.py) — `_cmd_backfill_history` 신규 + argparse 등록 (`--target` / `--dry-run`) + 옛 스키마 줄 skip 정책 + stdout 카운트 출력. RTDB 쓰기는 gateway 의 `write_history_*_raw` 3 함수에 위임 (PyRight private 접근 회피).
- [x] [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) — backfill 전용 `write_history_fills_raw` / `write_history_balance_adjusts_raw` / `write_history_signals_raw` 3 함수 추가 + `__all__`.
- [x] 테스트 (`tests/live/test_cli.py::TestCmdBackfillHistory` — 7건): `--dry-run` no-write / target fills / target balance_adjusts / target signals / target all / 옛 스키마 skip / 빈 history 디렉토리.
- [x] `pytest tests/live/test_cli.py::TestCmdBackfillHistory` 7건 그린.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 갱신: §1.1 다이어그램 / §8.2 트리 / §8.2.11~14 신규 4 섹션 (fills / balance_adjusts / signals / 비미러 항목) / §8.3 역할 분리 표 / §9.1 backfill-history 안내.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 갱신: 모듈별 역할 표의 `rtdb_gateway.py` / `cli.py` / `history.py` 설명 갱신.
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) Phase A 에 Step 8b "RTDB `/history/*` 미러 (fills / balance_adjusts / signals) 확인" 신규 (수동 확인 + backfill 검증 시나리오 포함).
- [x] `README.md` 변경 없음 재확인.
- [x] `poetry run black .` 실행 (146 files unchanged — 사전 포맷 완료 상태).
- [x] `poetry run python validate_project.py` 실행 — passed=995, failed=0, skipped=0.
- [x] DoD 체크리스트 최종 업데이트.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 ✅ Done 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=995, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / RTDB `/history/*` 미러 신규 (fills + balance_adjusts + signals 영구 보존)
2. live / `/history/{fills|balance_adjusts|signals}` 추가 + JSONL 스키마 확장 + `backfill-history` CLI
3. live / 체결 / 보정 / 신호 이력 RTDB 미러 + Git 정본 정보량 동등화
4. live / RTDB `/history/` 3 경로 신설 — daily runner 미러 + backfill 명령
5. live / 이력 영구 보존 — RTDB `/history/*` + JSONL 풀 페이로드 + `backfill-history` 도입

## 7) 리스크(Risks)

- **리스크 1 — JSONL 스키마 확장 후 차트 마커 빌더 호환성 회귀**.
  - 완화: 기존 `load_user_trades` / `load_signal_history` 가 새 필드를 무시하는지 회귀 테스트로 강제 (Phase 1 테스트).
- **리스크 2 — `_publish_to_rtdb` 내부에서 `write_history_*` 일부 성공 후 실패 → RTDB 가 부분 상태**.
  - 완화: 다음 `run-daily` 가 signals 를 덮어쓰고, fills / balance_adjusts 는 idempotency 로 동일 UUID 재시도 시 덮어씀 → 자동 수렴. 트랜잭션 / 롤백 / 재시도 도입 안 함 (원칙 1). 공통 예외 훅이 실패 알림 발송.
- **리스크 3 — `backfill-history --target all` 누적 데이터 대량 시 RTDB 쓰기 레이턴시 증가**.
  - 완화: 운영 초기 배치는 수십 줄 수준. 10 년 누적도 수천 줄. Firebase Admin SDK 의 단일 `set` 호출은 빠름. 필요 시 `--target` 으로 종류별 분할 실행.
- **리스크 4 — `reset` 의 `_HISTORY_PATH` 추가 실수로 `/device_tokens` 가 삭제되면 FCM 알림 끊김**.
  - 완화: `TestDeleteAllExceptDeviceTokens` 에서 `/device_tokens` 가 삭제 목록에 없음을 assert (Plan 2 부터 강제). 본 plan 도 동일 테스트 유지.
- **리스크 5 — `applied_at` 누락된 옛 `balance_adjusts.jsonl` 줄을 backfill 할 때 폴더 키를 산출할 수 없음**.
  - 완화: 옛 줄은 skip + WARNING. 운영자가 사후 식별 가능. 정본 은 Git 에 그대로 있으므로 정보 손실 없음. 사용자 피드백을 위해 backfill stdout 에도 skip 카운트 표기.
- **리스크 6 — `applied_fill_dismiss_ids.json` 와 `fill_dismisses.jsonl` 이 누적되어 RTDB 와 불일치 (의도된 비대칭) — 향후 혼동**.
  - 완화: 본 plan 의 비목표 / DESIGN §8.3 / live CLAUDE.md 에 "fill_dismiss 는 RTDB 미러하지 않음 (앱 조회 수요 없음)" 이 명문화되도록 한다.

## 8) 메모(Notes)

- **Plan 2 다음 적용**: Plan 2 가 `/history/summary/` 를 제거한 뒤 본 plan 이 `/history/` 하위 3 경로를 채운다. Plan 2 → Plan 3 순서가 자연스럽다 (Plan 2 는 이미 Done 상태).
- **Plan 1 (`history/states/`) 와 독립**: touch 영역이 다르므로 (Plan 1 은 Git `history/states/`, 본 plan 은 RTDB `/history/` + Git JSONL 스키마 확장) 순서 무관.
- `applied_at` 은 ISO 8601 포맷 (`+09:00` 오프셋 포함) 으로 통일. 폴더 키는 `applied_at[:10]` 슬라이스 (`YYYY-MM-DD`). state.py 의 `_now_kst_iso` 와 동일 패턴.
- `backfill-history` 의 옛 스키마 줄 skip 정책: `rtdb_key` / `applied_at` 등 키 산출에 필수인 필드가 없으면 skip. 페이로드 필드만 누락된 경우는 `null` 로 기록.
- `write_history_signals` 는 항상 호출 (4 자산 보장 — `result.signals` 가 비어있는 케이스는 daily_runner 의 내부 불변조건상 발생 불가).
- 본 plan 의 모든 RTDB 쓰기는 `set` (덮어쓰기) — `update` 사용 금지. idempotency 보장.

### 진행 로그 (KST)

- 2026-04-17 18:10: plan 초안 작성 (상태 → 🟡 Draft).
- 2026-04-17 18:30: 사용자 승인 — 스키마 확장 A안 / fill_dismiss 미러 안 함 / `applied_at` 배치 통일 (상태 → 🔄 In Progress).
- 2026-04-17 18:50: Phase 1 완료 — `rtdb_gateway` 에 `_HISTORY_PATH` / 3 경로 상수 + `write_history_fills` / `write_history_balance_adjusts` / `write_history_signals` + `delete_all_except_device_tokens` 갱신. `history.py` 에 raw 로더 3 종 + 확장 스키마 docstring. 신규 테스트 `pytest tests/live/test_rtdb_gateway.py tests/live/test_history.py` 82건 그린.
- 2026-04-17 19:00: Phase 2 완료 — `cli._cmd_run_daily` 진입 시 `applied_at_kst` 단일 산출, fill / balance_adjust 분기에 `write_history_*` 호출 추가, `_publish_to_rtdb` 끝에 `write_history_signals` 호출 추가. JSONL append payload 확장 (user_trades / balance_adjusts / signals). `pytest tests/live/` 480건 그린.
- 2026-04-17 19:15: Phase 3 완료 — `_cmd_backfill_history` + argparse + `write_history_*_raw` gateway 헬퍼 (PyRight private 접근 회피). 옛 스키마 줄 skip 카운트 출력. `TestCmdBackfillHistory` 7 건 신규.
- 2026-04-17 19:30: 마지막 Phase — 문서 갱신 (DESIGN §1.1 / §8.2 / §8.2.11~14 / §8.3 / §9.1, src/live/CLAUDE.md 모듈 표, TEST_QBT_LIVE_MANUAL.md Step 8b) + `black` (146 files unchanged) + `validate_project.py` 통과 (passed=995, failed=0, skipped=0). 상태 → ✅ Done.

---
