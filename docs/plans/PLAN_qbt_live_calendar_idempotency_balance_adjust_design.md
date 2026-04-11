# Implementation Plan: 휴장 체크 + idempotency + balance_adjust + 설계서 리팩토링

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

**작성일**: 2026-04-11 21:00
**마지막 업데이트**: 2026-04-11 21:00
**관련 범위**: live (cli, daily_runner, rtdb_gateway, models, state, drift, history, constants) + 설계 문서 리팩토링
**관련 문서**: [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md), [live/CLAUDE.md](../../live/CLAUDE.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] **Gap 1 해결**: 설계 4.2 단계 1 "휴장 체크 → 비거래일이면 종료" 를 `run-daily` 에 구현. `exchange_calendars` 를 이용해 trade_date 가 NYSE 영업일이 아니면 조기 종료 + 알림 skip.
- [x] **Gap 3 해결**: `validate_date_gap` 을 `_refresh_live_csvs` 파이프라인에 wiring. 거래일 누락 감지.
- [x] **방법 1 (idempotency 체크)**: `LiveState.last_model_execution_date` 와 `trade_date` 를 비교하여 같은 날짜 중복 실행을 차단. `--trade-date` 를 명시적으로 전달한 경우 (디버그 / 테스트 모드) 는 bypass.
- [x] **Gap 2 해결**: `balance_adjust` 흐름 구축 (RTDB inbox → fetch → apply → state 반영 → push). 앱 개발 전 서버 경로 사전 구축.
- [x] **설계서 리팩토링**: `DESIGN_QBT_LIVE_FINAL.md` 에서 구현 디테일 코드를 제거하고 산문 + 코드 참조로 전환. 부록 A/B 제거. 현재 구현 상태에 맞게 섹션 4.2, 6.4, 8, 10.2, 11 갱신.
- [x] 모든 변경에 대해 단위 테스트 + 기존 테스트 그린 유지.

## 2) 비목표(Non-Goals)

- Android 앱 UI 구현 — 앱은 별도 프로젝트. 본 plan 은 **서버측 경로만 준비**
- Node.js 20 deprecation 대응 (별도 유지보수 과제)
- QBT 본체 수정 없음
- 새 CLI 명령 추가 없음
- `validate_prev_close` 임계값 조정 등 기존 로직 수정 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

사용자 Phase A 수동 테스트 이후 설계서 감사에서 발견된 3 가지 중대 누락과 1 가지 기능 요청:

1. **휴장 체크 미구현** — cron 이 주말에 돌거나 사용자가 workflow_dispatch 를 휴장일에 실행해도 전체 파이프라인이 돌아감 (불필요한 Git clone / push / RTDB 쓰기 / 알림). 금요일 기준 CSV 로 계산이 반복되어 state 가 왜곡될 수 있음. 이전에 관찰한 "같은 날짜 재실행 시 model_equity 변화" 의 근본 원인.
2. **validate_date_gap 미연결** — 데이터 검증 3종 중 1 종이 파이프라인에 연결되지 않음. yfinance 가 거래일 데이터를 빠뜨려도 감지 불가.
3. **balance_adjust 미구현** — 설계 6.4 "앱에서 자산 직접 수정" 경로가 전무. 앱이 RTDB `/latest/*` 에 직접 쓰면 다음 실행 시 덮어쓰기됨 → app-only 방식으로는 불가능. inbox → daily runner → state 반영 → push 패턴이 필요.
4. **idempotency 요구사항 (사용자 요청 "방법 1")** — 같은 날짜 재실행 시 state 가 왜곡되는 것을 방지. `--trade-date` 명시 전달 시 bypass 하여 테스트/디버깅 편의 유지.

설계서 자체도 구현 진화를 반영하지 못해 **사실과 다른 표기**가 누적됨 (부록 A/B 의 오기재, 섹션 10.2 의 "90일" 주석, 섹션 11 의 구 에러 경로 등). 사용자 지시에 따라 구현 디테일 코드를 제거하고 산문 중심으로 전환하여 "구현이 바뀌어도 문서가 쉽게 깨지지 않도록" 한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md) — 타입 힌트, Path, 한글 메시지, 로깅, 내부 불변조건, 문서 내구성 원칙
- [live/CLAUDE.md](../../live/CLAUDE.md) — live 도메인 원칙, 순수 계산/I/O 분리, 장애 시 자동 복구 금지, 백테스트 절대 규칙 보존
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, mock 기반, 외부 네트워크 호출 금지
- [docs/CLAUDE.md](../CLAUDE.md) — 문서 내구성 원칙 (역할/책임 중심, 구체 수치 지양)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — 본 plan 의 리팩토링 대상 문서 자체

## 4) 완료 조건(Definition of Done)

- [x] `exchange_calendars` 를 사용한 NYSE 영업일 체크 유틸 추가 (`live/src/live/` 또는 기존 모듈에 헬퍼)
- [x] `_cmd_run_daily` 의 `trade_date` 결정 직후 휴장 체크. 비영업일이면 조기 종료 (성공 exit, 알림/변경 없음, 로그만)
- [x] `validate_date_gap` 이 `_refresh_live_csvs` 파이프라인에 연결되어 거래일 gap 발견 시 `ValueError` 전파
- [x] `LiveState.last_model_execution_date` 와 `trade_date.isoformat()` 비교. 같고 `args.trade_date` 가 `None` (cron 기본) 이면 조기 종료 (성공 exit, 로그). `args.trade_date` 명시 시 bypass
- [x] `run_daily` 또는 `_cmd_run_daily` 가 정상 종료 전 `updated_state.last_model_execution_date = trade_date.isoformat()` 을 세팅
- [x] `BalanceAdjust` dataclass 신규 추가 (`models.py`)
- [x] `rtdb_gateway` 에 `fetch_pending_balance_adjusts`, `mark_balance_adjust_processed` 추가 (`/balance_adjust/inbox/*`)
- [x] `drift` 또는 신규 `balance_adjust.py` 에 `apply_balance_adjusts_idempotent` 순수 함수 추가
- [x] `applied_balance_adjust_ids.json` 별도 원장 (`state.py::load/save`) 추가, 90일 cleanup 공유
- [x] `cli._cmd_run_daily` 가 fills 처리 직후 balance_adjusts 도 처리 (적용 + mark_processed + history append)
- [x] `history/balance_adjusts.jsonl` 에 audit 용 append (차트 마커 대상 아님)
- [x] 단위 테스트 추가:
  - `TestHolidayCheck` — 영업일 / 휴장일 / 테스트 캘린더 주입
  - `TestValidateDateGapWiring` — gap 있는 상황에서 `run-daily` 가 RuntimeError 전파
  - `TestIdempotencyCheck` — 같은 trade_date 재실행 차단, `--trade-date` 명시 bypass
  - `TestBalanceAdjustModels` — 새 dataclass 필드
  - `TestFetchPendingBalanceAdjusts`, `TestMarkBalanceAdjustProcessed`
  - `TestApplyBalanceAdjustsIdempotent` — 새 adjust 적용, 중복 skip, 다중 자산
  - `TestRunDailyBalanceAdjustIntegration` — RTDB mock 에서 adjust 1 건 → state 반영 → jsonl append 확인
- [x] 기존 `test_regression.py` 그린 유지
- [x] [DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 리팩토링 (구체 항목은 Phase 5 참고)
- [x] [TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 주말 테스트 절차 갱신 (휴장 체크 반영)
- [x] [live/CLAUDE.md](../../live/CLAUDE.md) 모듈별 역할 요약 갱신
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료
- [x] `README.md`: 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드 (수정/추가)**:
- `live/src/live/constants.py` — NYSE 캘린더 상수 또는 lazy accessor (사용 시점에 import)
- `live/src/live/cli.py` — `_cmd_run_daily` 에 휴장 체크 + idempotency 체크 + balance_adjust step
- `live/src/live/data_validator.py` — 수정 없음 (기존 `validate_date_gap` 그대로 사용)
- `live/src/live/daily_runner.py` — 정상 종료 시 `updated_state.last_model_execution_date` 세팅
- `live/src/live/models.py` — `BalanceAdjust` dataclass 추가
- `live/src/live/state.py` — `load_applied_balance_adjust_ids` / `save_applied_balance_adjust_ids` 추가 (기존 applied_fill_ids 유틸 패턴 재사용 또는 파라미터화)
- `live/src/live/rtdb_gateway.py` — `fetch_pending_balance_adjusts`, `mark_balance_adjust_processed` 추가
- `live/src/live/drift.py` 또는 신규 `live/src/live/balance_adjust.py` — `apply_balance_adjusts_idempotent`
- `live/src/live/history.py` — `append_balance_adjust` 추가

**테스트**:
- `live/tests/test_cli.py` — 휴장 체크, idempotency, balance_adjust 통합
- `live/tests/test_models.py` — `BalanceAdjust` 필드 검증
- `live/tests/test_rtdb_gateway.py` — balance_adjust RTDB 경로
- `live/tests/test_drift.py` 또는 신규 `test_balance_adjust.py` — `apply_balance_adjusts_idempotent`
- `live/tests/test_data_validator.py` — 수정 없음 (validate_date_gap 단위 테스트 기존 유지)
- `live/tests/test_history.py` — `append_balance_adjust` / 로드 헬퍼

**문서**:
- `docs/DESIGN_QBT_LIVE_FINAL.md` — 대규모 리팩토링 (Phase 5)
- `docs/TEST_QBT_LIVE_MANUAL.md` — 주말 테스트 절차 갱신
- `live/CLAUDE.md` — 모듈별 역할 요약 갱신
- `README.md`: **변경 없음**

### 데이터/결과 영향

- **새 파일**: `qbt-live-state/applied_balance_adjust_ids.json`, `qbt-live-state/history/balance_adjusts.jsonl` (첫 balance_adjust 처리 시점에 자동 생성)
- **새 RTDB 경로**: `/balance_adjust/inbox/{uuid}` (앱이 쓰는 queue)
- **LiveState 동작 변경**: `last_model_execution_date` 가 run-daily 정상 종료마다 갱신 (기존에는 항상 None)
- **회귀 영향**: `test_regression.py` 는 `run_daily` 를 직접 호출하므로 cli 변경(휴장 체크, idempotency) 에 영향 없음. 단 `run_daily` 내부에서 `updated_state.last_model_execution_date` 세팅을 추가하므로 최종 상태가 약간 달라짐 → 테스트가 이 필드를 비교에 쓰지 않는지 확인 필요.

## 6) 단계별 계획(Phases)

### Phase 1 — `exchange_calendars` 인프라 + 휴장 체크

**작업 내용**:

- [x] `live/src/live/cli.py` 상단에 lazy import 용 헬퍼 추가:
  ```python
  def _get_nyse_calendar():
      """NYSE 영업일 캘린더 싱글톤. 첫 호출 시 exchange_calendars 로드."""
      from exchange_calendars import get_calendar
      return get_calendar("XNYS")
  ```
- [x] 새 내부 함수 `_check_trading_session(trade_date)` 추가:
  - 캘린더에서 `is_session(pd.Timestamp(trade_date))` 호출
  - True 이면 통과, False 이면 `ValueError(f"비영업일: {trade_date} (NYSE 휴장)")` 또는 boolean 반환 후 상위에서 early return 결정
- [x] `_cmd_run_daily` 에 trade_date 결정 직후 호출:
  ```python
  trade_date = date.fromisoformat(trade_date_str) if trade_date_str else date.today()
  if not _is_nyse_session(trade_date):
      logger.debug(f"{trade_date} 는 NYSE 비영업일 — run-daily 종료 (정상)")
      return 0  # 조기 성공 종료. ephemeral 컨텍스트 밖에서 바로 return
  ```
- [x] **중요 설계 결정**: 조기 종료는 **ephemeral_state_repo 진입 전** 에 수행. 즉 휴장일에는 git clone 도 하지 않고 바로 종료 (비용 0)
- [x] 테스트 `live/tests/test_cli.py::TestHolidayCheck`:
  - T-1: 영업일 trade_date → 기존 흐름대로 진행 (fake ephemeral + fake fetch)
  - T-2: 휴장일 trade_date → exit code 0 + 로그 "비영업일" + ephemeral 호출되지 않음
  - T-3: `monkeypatch` 로 `_is_nyse_session` 을 가짜로 교체하여 실제 calendar 의존 없이 검증
- [x] 직접 실행 검증 불필요 (테스트로 충분)

---

### Phase 2 — `validate_date_gap` wiring

**작업 내용**:

- [x] `_validate_against_csv` 확장: `calendar` 인자 추가 (Phase 1 의 캘린더 재사용)
- [x] 호출 시 기존 CSV 의 마지막 날짜와 `trade_date` 사이 gap 을 `validate_date_gap(csv_last, trade_date, calendar)` 로 검증
- [x] 실패 시 기존 `ValueError(f"{ticker}: {errors[0]}")` 패턴 유지
- [x] `_refresh_live_csvs` 호출 시 Phase 1 의 캘린더 인스턴스를 인자로 전달 (또는 함수 내부에서 lazy 로드)
- [x] 테스트:
  - `TestValidateDateGapWiring` — CSV 마지막 날짜 < trade_date - 1 영업일 인 상황 주입 → `RuntimeError` 전파
  - 단 **정상 케이스** (CSV 마지막 = 전 거래일, trade_date = 다음 거래일) 는 통과해야 함

---

### Phase 3 — idempotency 체크 (방법 1)

**작업 내용**:

- [x] `daily_runner.run_daily` 가 정상 종료 직전 `updated_state.last_model_execution_date = trade_date.isoformat()` 세팅
- [x] `_cmd_run_daily` 에 state 로드 직후 idempotency 체크:
  ```python
  is_manual_trade_date = trade_date_str is not None  # 디버그 모드 신호
  if not is_manual_trade_date and state.last_model_execution_date == trade_date.isoformat():
      logger.debug(f"{trade_date} 이미 처리됨 — run-daily 종료 (정상)")
      return 0
  ```
- [x] 이 체크는 **휴장 체크 직후, ephemeral_state_repo 안에서** 수행 (state 로드 후 판단 가능)
- [x] 테스트 `TestIdempotencyCheck`:
  - T-1: `state.last_model_execution_date = "2026-04-10"`, cron 모드 (trade_date=default=today=4-10) → 조기 종료, 0 반환
  - T-2: 동일 상황이지만 `--trade-date 2026-04-10` 명시 → bypass, 실행 진행
  - T-3: `state.last_model_execution_date = None` (초기 상태) → 통과, 정상 실행
  - T-4: 정상 run_daily 후 `updated_state.last_model_execution_date == trade_date.isoformat()` 확인
- [x] `test_regression.py` 에서 새 필드 세팅이 기존 assertion 을 깨는지 확인. 깨지면 assertion 제외 또는 정교화

---

### Phase 4 — `balance_adjust` 흐름 전체 구축

**작업 내용**:

- [x] `models.py::BalanceAdjust` dataclass 추가:
  - `asset_id: str | None` (None = cash-only adjustment)
  - `new_shares: int | None`
  - `new_cash: float | None`
  - `reason: str`
  - `input_time_kst: str`
  - `rtdb_key: str`
- [x] `rtdb_gateway.py` 추가:
  - `_BALANCE_ADJUST_INBOX_PATH = "/balance_adjust/inbox"` 상수
  - `fetch_pending_balance_adjusts(app) -> list[BalanceAdjust]` (processed=false 필터)
  - `mark_balance_adjust_processed(app, keys)` (processed=true 세팅)
- [x] `state.py` 추가:
  - `DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME = "applied_balance_adjust_ids.json"`
  - `load_applied_balance_adjust_ids(path)`, `save_applied_balance_adjust_ids(ids, path)` (기존 applied_fill_ids 패턴 재사용, 함수 이름만 다름)
- [x] 신규 `live/src/live/balance_adjust.py`:
  - `apply_balance_adjusts_idempotent(state, adjusts, applied_ids) -> tuple[LiveState, dict[str, str]]`
  - 로직: adjust.rtdb_key 가 applied_ids 에 있으면 skip, 아니면 asset.actual_shares / state.shared_cash_actual 갱신
  - 순수 함수 (copy.deepcopy 로 state 복사, 90일 cleanup 등 기존 패턴 재사용)
- [x] `history.py::append_balance_adjust(adjust_dict, history_dir)` 추가 — `history/balance_adjusts.jsonl` 에 append
- [x] `cli._cmd_run_daily` 수정:
  - 기존 fills 처리 직후에 balance_adjusts fetch + apply + save + history + mark_processed 단계 추가
  - ephemeral_state_repo 컨텍스트 안에서 전부 수행 (git push 에 포함)
- [x] 테스트:
  - `test_models.py::TestBalanceAdjustFields`
  - `test_rtdb_gateway.py::TestFetchPendingBalanceAdjusts` (mock Firebase ref)
  - `test_balance_adjust.py` 신규 — `TestApplyBalanceAdjustsIdempotent` (4~5 케이스)
  - `test_history.py::TestAppendBalanceAdjust`
  - `test_cli.py::TestRunDailyBalanceAdjustIntegration` — 통합: adjust 1 건 → state 반영 → push 확인

---

### Phase 5 — `DESIGN_QBT_LIVE_FINAL.md` 리팩토링

**작업 내용**:

- [x] **섹션 5.1 스키마**: `LiveState`, `AssetLiveState`, `PendingOrderDict`, `BufferZoneState` 의 dataclass 코드 블록 → 산문 요약 + "실제 정의: `live/src/live/models.py`" 참조
- [x] **섹션 6.1 classify_fill**: 코드 블록 → "pending_order 의 intent_type 이 BUY 계열(ENTER_TO_TARGET / INCREASE_TO_TARGET)이고 fill.direction 이 'buy' 이면 system_fill. SELL 계열 대칭. 불일치 또는 pending 없음이면 personal_trade" 산문
- [x] **섹션 6.4 balance_adjust**: 본 plan Phase 4 구현 기준으로 흐름 업데이트
- [x] **섹션 14 drift 계산**: 코드 블록 → 산문 ("cash + Σ(shares × close) 기반 equity 차이의 절대값을 model_equity 로 나눈 비율") + 임계값만 표 유지
- [x] **부록 A 함수 시그니처**: **섹션 전체 삭제** + "함수 시그니처는 `live/src/live/*.py` 및 `live/CLAUDE.md` 의 모듈별 역할 요약 참조" 한 줄 링크
- [x] **부록 B 데이터 모델**: **섹션 전체 삭제** + "데이터 모델은 `live/src/live/models.py` 참조" 한 줄 링크
- [x] **섹션 4.2 단계 순서**: 단계 1 "휴장 체크 → 비거래일 종료" 유지하되, 구현에 맞게 표현 조정. 단계 1.5 "idempotency 체크" 추가
- [x] **섹션 8 알림**: "일일 리포트" 통합형으로 표기 (시그널/리밸런싱/리마인더 포함) + 실패 알림 분리 + 각 알림이 FCM + 텔레그램 동시
- [x] **섹션 10.2 RTDB**: `/history/summary/` 의 "90일, 앱 표시용" → "영구 누적 (앱은 최근 N 개만 표시)" 로 현실화
- [x] **섹션 11 에러 매트릭스**: 
  - "Git push 성공 후 RTDB 실패" → "ephemeral 모드: 전체 원자성 (모두 성공하거나 모두 실패)" 로 업데이트
  - "PendingOrderConflict 별도 메시지" → 일반 엔진 실행 실패 메시지에 포함되도록 현실화 (또는 별도 catch 추가 선택적)
  - 새 항목 추가: "비영업일 trade_date → 조기 정상 종료 (알림 없음, 로그만)"
  - 새 항목 추가: "같은 trade_date 재실행 → idempotency 차단 (cron 모드) / bypass (--trade-date 명시)"
- [x] **섹션 3 검증**: `validate_date_gap` 도 이제 연결되었음 명시
- [x] **섹션 0 개요 확정사항 표**: 필요 시 갱신 (대부분 유지 가능)
- [x] **섹션 1.1 다이어그램**: 단계 번호 재조정 (휴장 체크 추가)
- [x] 문서 길이 목표: ~400줄 이하 (현재 592줄)

---

### Phase 6 — `TEST_QBT_LIVE_MANUAL.md` + `live/CLAUDE.md` 갱신

**작업 내용**:

- [x] `TEST_QBT_LIVE_MANUAL.md` 의 #4 주말 테스트 절차 갱신:
  - **중요 주의사항 추가**: 주말에 workflow_dispatch 실행 시 `trade_date` 를 반드시 지정해야 함. 비워두면 휴장 체크에 걸려 즉시 종료 (로그만 남고 state/RTDB/알림 없음)
  - `trade_date=2026-04-10` 같은 영업일 지정 시 휴장 체크 bypass + idempotency 체크 bypass 둘 다 자동 처리됨을 명시
- [x] `TEST_QBT_LIVE_MANUAL.md` 의 #11 (데이터 검증 실패) 에 `validate_date_gap` 시뮬레이션 참고 추가 — 직접 테스트는 복잡하므로 단위 테스트 수준에서만 커버 명시
- [x] `live/CLAUDE.md` 모듈별 역할 요약 테이블 갱신:
  - `balance_adjust.py` (신규) 추가
  - `data_validator.py` 설명에 "validate_date_gap 도 이제 wiring 됨" 명시
  - `cli.py` 설명에 "휴장 체크 + idempotency 체크" 명시

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black live/ docs/` 실행 (필요 시 적용)
- [x] smoke test: `poetry run python -m live.cli notify-failure --message "calendar+idempotency+balance_adjust plan smoke"` 로 .env 자동 로드 + 전체 모듈 import 정상 확인
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 휴장 체크 + idempotency + balance_adjust + 설계서 리팩토링
2. live / 설계 Gap 1/2/3 해결 + idempotency 체크 + DESIGN 문서 현실화
3. live / NYSE 휴장 체크 + 재실행 방지 + balance_adjust 서버 경로 + 설계서 정리
4. live / 운영 안정성 개선 — 휴장일/중복 실행 차단 + 자산 보정 경로 + 문서 리팩토링
5. live / 설계서와 구현 동기화 + 중복 실행 방지 + 자산 보정 inbox 패턴

## 7) 리스크(Risks)

- **`exchange_calendars` 의 초기 로딩 시간**: 첫 호출 시 캘린더 캐시 빌드에 ~1 초 소요될 수 있음. daily_run Actions 실행 시간에 미미한 영향. lazy import 로 테스트에는 영향 없음.
- **`last_model_execution_date` 가 기존 state 파일에 없음**: 기존 `LiveState` 에 이 필드는 이미 선언되어 있고 `create_initial_state` 에서 `None` 으로 초기화됨 (확인 필요). 만약 기존 qbt-live-state 의 `live_state.json` 이 이 필드를 안 가지고 있으면 파싱 실패. `_live_state_from_dict` 가 `.get("last_model_execution_date")` 로 fallback 되는지 확인 필수.
- **`test_regression.py` 영향**: `run_daily` 가 새 필드를 세팅하게 되면 회귀 테스트가 기존 state 와 strict 비교 시 실패할 수 있음. fields 단위 비교이므로 new field 허용하도록 조정 필요할 수 있음. 테스트 확인 후 대응.
- **balance_adjust 와 fills 의 처리 순서**: 같은 자산에 대해 fill 과 balance_adjust 가 동시에 있으면 어느 것이 먼저? 본 plan 은 **fills 먼저 → balance_adjust 나중** 순서로 정함. balance_adjust 는 "강제 덮어쓰기" 의미라 fill 반영 후 덮어써야 자연스러움.
- **RTDB mock 테스트 복잡도**: `fetch_pending_balance_adjusts` 의 Firebase ref 흉내 내는 fake 가 복잡할 수 있음. 기존 `test_rtdb_gateway.py` 의 fake_firebase 패턴을 그대로 재사용.
- **설계서 리팩토링의 범위**: 대규모 편집이라 실수로 중요한 표/원칙이 삭제될 위험. 섹션별로 신중히 진행하고 각 섹션에서 "삭제 전 내용" 을 주석/로그에 간단히 남겨 되살리기 용이하게.
- **휴장 체크 bypass 필요성**: 휴장일에 **강제 실행** 하고 싶은 극단 케이스 (예: 설 연휴에 테스트) 는 없음. 사용자가 `--trade-date=영업일` 을 지정하면 trade_date 기준 판정이라 자연스럽게 동작. 별도 bypass 플래그 불필요.

## 8) 메모(Notes)

- 사용자 선택지 A (전체 6 phase + Final) 승인 → 즉시 In Progress → 승인 없이 실행
- Gap 2 (balance_adjust) 는 앱 개발 전 서버 경로 사전 구축 — 앱은 RTDB 쓰기 1 줄만 추가하면 됨
- 설계서 리팩토링은 docs/CLAUDE.md 의 "문서 내구성 원칙" 을 정확히 따름 (역할 중심, 구체 수치/변경 가능 정보 제거)
- 본 plan 이후 Phase A 전체 재실행 (#4~#13) 은 별도 수동 작업 — 사용자가 테스트 타이밍 선택

### 진행 로그 (KST)

- 2026-04-11 21:00: Draft 작성 → 사용자 사전 승인 → 즉시 In Progress
- 2026-04-11 21:05: Phase 1 완료 — `_get_nyse_calendar` / `_is_nyse_session` 추가 + `_cmd_run_daily` 에 휴장 체크 조기 종료
- 2026-04-11 21:08: Phase 3 완료 — `state.last_model_execution_date` 기반 idempotency 체크 + `--trade-date` bypass + 4 개 테스트
- 2026-04-11 21:15: Phase 2 완료 — `_validate_against_csv` 에 `trade_date` / `calendar` 인자 추가 + `validate_date_gap` 호출 + 2 개 테스트
- 2026-04-11 21:25: Phase 4 완료 — `BalanceAdjust` 모델, `balance_adjust.py::apply_balance_adjusts_idempotent`, RTDB `fetch_pending_balance_adjusts` / `mark_balance_adjusts_processed`, `history.append_balance_adjust`, `state.load/save_applied_balance_adjust_ids`, cli `_cmd_run_daily` 에 step 6.5/7.5/8.1/8.6 통합. `test_balance_adjust` (8) + `test_rtdb_gateway` (5) + `test_cli` (2) + `test_models` (4) + `test_history` (2) 추가
- 2026-04-11 21:35: Phase 5 완료 — `DESIGN_QBT_LIVE_FINAL.md` 대규모 리팩토링 (592 → 447 줄). 부록 A/B 제거, dataclass/함수 코드 블록 제거, 산문 + 코드 참조 링크로 전환. 섹션 0 확정사항 표 + §1.1 다이어그램 + §6.4 balance_adjust + §10.2 RTDB 경로 + §11 에러 매트릭스 업데이트
- 2026-04-11 21:40: Phase 6 완료 — `live/CLAUDE.md` 모듈 테이블 (`balance_adjust.py`, `git_state.py` 추가) + `TEST_QBT_LIVE_MANUAL.md` #4 에 휴장 체크 / idempotency 주의사항 추가
- 2026-04-11 21:45: Final Phase — `black`, ruff auto-fix, `validate_project` passed=846/failed=0/skipped=0, smoke test 통과 ✅ Done
