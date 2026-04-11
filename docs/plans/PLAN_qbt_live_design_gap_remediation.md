# Implementation Plan: 설계 / 구현 Gap 정리 (data_validator 연결 + 5 개 누락 보완)

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

**작성일**: 2026-04-11 20:00
**마지막 업데이트**: 2026-04-11 20:00
**관련 범위**: live (cli, daily_runner, chart_data, drift, history, models)
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

- [x] **Gap 1**: `data_validator.py` 의 검증 함수를 `run-daily` 파이프라인에 와이어링
- [x] **Gap 2**: `chart_data.build_chart_series` 의 `buy_signals` / `sell_signals` 실제 값 채우기
- [x] **Gap 3 + Gap 4**: fill 처리 시 `history/user_trades.jsonl` append + `build_chart_series` 에 전달
- [x] **Gap 5**: `DailyResult.chart_series` dead field 제거
- [x] **Gap 6**: `pending_fill_reminders` 논리 수정 (일부 체결 케이스)

## 2) 비목표(Non-Goals)

- Android 앱 관련 작업은 범위 밖 (앱 구현은 별도 프로젝트)
- Node.js 20 deprecation 대응 (Gap 7) 은 범위 밖 — 별도 유지보수 plan 으로 분리 권장
- QBT 본체 (`src/qbt/`) 수정 없음
- 새 CLI 명령 추가 없음 (기존 서브명령만 수정)
- data_validator 의 3 가지 검증 로직 **자체** 는 수정하지 않음 — 이미 구현 + 단위 테스트 완료됨. 본 plan 은 **연결 (wiring) + 관련 후속 작업** 만 수행

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

이번 Phase A 수동 테스트 진행 중 테스트 #11 (데이터 검증 실패 시뮬레이션) 이 동작하지 않는 것을 사용자가 발견하여 시작된 감사 작업의 결과물.

**발견된 6 개 gap 상세**:

1. **Gap 1 — data_validator 미연결**: Step 6 구현은 완료되었으나 Step 7 (daily_runner) 통합 시 와이어링 누락. 설계서 3장의 "3 가지 검증 필수" 요구사항이 실행 경로에서 빠져있음.
2. **Gap 2 — buy_signals/sell_signals 하드코딩**: `chart_data.py:120-121` 이 빈 리스트 리터럴. 설계서 7장 "차트 신호 마커" 미구현.
3. **Gap 3 — user_trades 전달 누락**: `cli.py:242` 가 `build_chart_series` 를 인자 없이 호출. chart_data 의 user marker 기능이 사용 불가.
4. **Gap 4 — append_user_trade 호출처 부재**: `history.append_user_trade` 는 정의만 있고 어디에서도 호출되지 않음. Gap 3 의 원인 — 데이터 자체가 누적되지 않음.
5. **Gap 5 — dead field**: `DailyResult.chart_series` 가 선언은 있으나 항상 빈 dict 로 반환되고 cli 는 별도 경로로 데이터 생성 → 혼동 유발.
6. **Gap 6 — 리마인더 논리 결함**: `not pending_fills` 조건이 "**모두** 체결되지 않은 경우만" 으로 작동. 일부 자산만 체결된 경우의 리마인더 누락.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md) — 타입 힌트, Path 사용, 로깅, 내부 불변조건 처리
- [live/CLAUDE.md](../../live/CLAUDE.md) — **특히 "순수 계산 / I/O 분리" 원칙 (daily_runner 는 파일 I/O 금지)**, "장애 시 자동 복구 금지"
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, mock 기반
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — 3장 (데이터 검증), 4.2 (일일 실행 루프), 6장 (drift), 7장 (차트)

## 4) 완료 조건(Definition of Done)

- [x] `validate_ohlc_logic` / `validate_prev_close` 가 `_refresh_live_csvs` 에서 호출. `validate_date_gap` 은 본 plan 범위 외로 남김 (exchange_calendars 의존성 주입 필요)
- [x] 테스트 #11 의 핵심 시나리오 (CSV 손상) 가 `_validate_against_csv` 에서 `ValueError` 전파되어 run-daily 중단되는 단위 테스트 추가
- [x] `build_chart_series` 가 `signal_history` 인자에서 `buy_signals` / `sell_signals` 인덱스 채움
- [x] `_cmd_run_daily` 가 신규 applied fill 을 식별해 `history.append_user_trade` 호출
- [x] `_publish_to_rtdb` 가 `history.load_user_trades` + `history.load_signal_history` 를 로드하여 `build_chart_series` 에 전달
- [x] `DailyResult.chart_series` 필드 제거 + `test_models.py` 업데이트
- [x] `pending_fill_reminders` 논리 수정 + `TestPendingFillReminderLogic` (3 케이스) 추가
- [x] 신규 단위 테스트 23 개 추가
- [x] 기존 테스트 그린 유지 확인 (특히 `test_regression.py`)
- [x] [TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) #11 절차 갱신
- [x] [live/CLAUDE.md](../../live/CLAUDE.md) `data_validator` 항목 업데이트
- [x] `poetry run python validate_project.py` 통과 (passed=**819**, failed=**0**, skipped=**0**)
- [x] `poetry run black live/` 실행 완료
- [x] `README.md`: 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드 (수정)**:
- `live/src/live/cli.py`
  - `_build_market_bundle` 또는 `_refresh_live_csvs` 에 `data_validator` 검증 호출 추가
  - `_publish_to_rtdb` / `build_chart_series` 호출 경로에 `user_trades` 로드 연결
- `live/src/live/daily_runner.py`
  - `pending_fill_reminders` 논리 수정
  - `DailyResult` 생성 시 `chart_series` 키 제거
- `live/src/live/chart_data.py`
  - `build_chart_series` 에 `signal_history_dir` 또는 `signals_by_asset` 인자 추가
  - `buy_signals` / `sell_signals` 실제 채우기 로직
- `live/src/live/drift.py`
  - `_apply_single_fill` 또는 `apply_fills_idempotent` 에 `history_dir` 인자 추가 → `history.append_user_trade` 호출
- `live/src/live/history.py`
  - 새 `load_user_trades(history_dir) -> dict[str, list[UserTrade]]` 함수 추가
  - 기존 `append_user_trade` 유지
- `live/src/live/models.py`
  - `DailyResult.chart_series` 필드 제거

**테스트**:
- `live/tests/test_cli.py` — data_validator wiring 통합 테스트 (잘못된 CSV 주입 → RuntimeError)
- `live/tests/test_chart_data.py` — buy_signals/sell_signals 실제 값 검증 + user_trades 전달 검증
- `live/tests/test_drift.py` — apply_fills_idempotent 가 append_user_trade 호출하는지 검증
- `live/tests/test_history.py` — load_user_trades 단위 테스트
- `live/tests/test_daily_runner.py` — pending_fill_reminders 일부 체결 케이스
- `live/tests/test_regression.py` — 기존 통과 유지 확인

**문서**:
- `docs/TEST_QBT_LIVE_MANUAL.md` — #11 시나리오 재검증 (필요 시 절차 보강)
- `README.md`: **변경 없음**

### 데이터/결과 영향

- **새 파일**: `qbt-live-state/history/user_trades.jsonl` (기존에 없던 파일. 첫 fill 처리 시 자동 생성)
- **기존 결과 영향**: `DailyResult.chart_series` 제거는 모델 변경이지만 어차피 dead field 였으므로 기존 호출자에 영향 없음. 단 모델 직렬화/역직렬화 경로 (`state.py`) 는 DailyResult 를 저장하지 않으므로 영향 없음
- **RTDB 영향**: `/latest/chart_data/` 에 `buy_signals`, `sell_signals`, `user_buys`, `user_sells` 가 **이제부터 값이 있으면 저장됨** (Firebase 가 빈 배열은 저장하지 않는 특성 때문에 지금까지 없었음)
- **run-daily 동작 변경 가능성**: 기존에 CSV 가 이상해도 계산이 진행되었지만, 이제는 검증 실패 시 중단됨. 회귀 테스트가 **"정상 CSV 기반"** 이므로 영향 없어야 함 — 확인 필수

## 6) 단계별 계획(Phases)

### Phase 1 — data_validator wiring (Gap 1)

**핵심 설계 결정**:

- `validate_prev_close` 를 **"yfinance 가 반환한 최근 5 일 × CSV 의 같은 날짜"** 전체 쌍에 대해 비교. 1 개 날짜만 비교하는 것보다 넓게 가 A (스플릿) / C (사용자 조작) 모두 자연스럽게 감지.
- 호출 위치: `_refresh_live_csvs` 내부, yfinance 수집 직후 & CSV append 이전.
- `validate_date_gap` 은 이번 phase 에서 제외 — 휴장일 계산이 복잡하고 `exchange_calendars` 의존성 추가 필요. 별도 후속 작업으로 분리.

**작업 내용**:

- [ ] `cli.py::_refresh_live_csvs` 를 다음 흐름으로 리팩토링:
  1. `fetch_recent_ohlc(ticker, days=5)` 호출
  2. 기존 CSV 가 존재하면 `load_csv` 로 로드
  3. yfinance 의 5 일치 각 행에 대해 `validate_ohlc_logic` 호출 (High/Low/Close 논리 검증)
  4. yfinance 행 중 CSV 와 **겹치는 날짜들** 에 대해 `validate_prev_close(csv_close, yf_close)` 호출 — A (스플릿) / C (사용자 조작) 모두 감지
  5. 모든 검증 통과 후 기존 append 로직 수행
- [ ] 검증 실패 시 `ValueError(f"{ticker} {yf_date}: {msg}")` 형태로 메시지 구성 → 기존 `_cmd_run_daily` 의 try/except 가 `RuntimeError("데이터 검증 실패: ...")` 로 래핑
- [ ] 새 헬퍼 함수 도입 가능: `_validate_against_csv(ticker, recent_df, csv_df) -> None` (순수 함수로 분리하여 단위 테스트 용이)
- [ ] `live/tests/test_cli.py::TestDataValidatorWiring` 추가:
  - T-1: 정상 CSV + 정상 yfinance → run-daily 성공
  - T-2: yfinance 행 중 하나가 `High < Low` → `RuntimeError("데이터 검증 실패:...")` 전파
  - T-3: CSV 의 과거 날짜 종가가 조작됨 (yfinance 와 10% 차이) → `RuntimeError` 전파 (C 시나리오)
  - T-4: 각 실패 케이스에서 `_safe_notify_failure` 호출 확인
- [ ] `live/tests/test_data_validator.py` 는 기존 단위 테스트 유지 — 수정 없음
- [ ] Phase 1 단위 그린 확인

---

### Phase 2 — chart_data buy_signals/sell_signals 실제 값 채우기 (Gap 2)

**작업 내용**:

- [ ] `build_chart_series` signature 확장: `signals_history: dict[str, list[tuple[str, str]]] | None = None` 추가 (자산 ID → [(date, "buy"|"sell"), ...])
- [ ] 신호 이력 수집 방식 결정 및 구현:
  - **옵션 A**: `history/daily/{date}.json` 파일들을 스캔해 각 날짜의 `result.signals` 에서 `state == "buy"|"sell"` 이었던 자산 추출
  - **옵션 B**: 새 `history/signals.jsonl` 파일을 만들어 `run-daily` 마다 append
  - **추천 A**: 기존 파일 재사용. 단 `save_daily_log` 의 `daily_payload` 에 `signals` 필드 추가 필요
- [ ] `history.py::save_daily_log` 가 저장하는 payload 에 `signals` (asset_id → state 매핑) 포함하도록 `cli.py::_persist_history` 수정
- [ ] `history.py::load_signals_history(history_dir) -> dict[str, list[tuple[str, str]]]` 신규 추가
- [ ] `chart_data.py` 에서 date → index 매핑으로 `buy_signals` / `sell_signals` 리스트 구성
- [ ] `test_chart_data.py` 에 신호 채우기 테스트 추가

---

### Phase 3 — user_trades 흐름 구축 (Gap 3 + Gap 4)

**작업 내용**:

- [ ] `drift.py::apply_fills_idempotent` signature 확장: `history_dir: Path | None = None` 추가
- [ ] 각 fill 이 적용될 때 `UserTrade` 객체 생성 → `history.append_user_trade` 호출
  - 단 `history_dir is None` 이면 skip (테스트 격리용)
- [ ] `history.py::load_user_trades(history_dir) -> dict[str, list[UserTrade]]` 신규 추가 — `user_trades.jsonl` 파싱
- [ ] `cli.py::_cmd_run_daily` 에서 `drift.apply_fills_idempotent(..., history_dir=_history_dir(state_dir))` 로 호출
- [ ] `cli.py::_publish_to_rtdb` 에서 `user_trades = history.load_user_trades(_history_dir(state_dir))` 후 `build_chart_series(state_dir, user_trades=user_trades)` 호출
- [ ] `test_drift.py` 에 append_user_trade 호출 검증 추가
- [ ] `test_history.py::TestLoadUserTrades` 신규 추가
- [ ] `test_chart_data.py` 에 user_trades 인자 전달 시 user_buys/user_sells 채워지는지 검증

---

### Phase 4 — DailyResult.chart_series dead field 제거 (Gap 5)

**작업 내용**:

- [ ] `models.py::DailyResult` 에서 `chart_series` 필드 제거
- [ ] `daily_runner.py` 의 `DailyResult(...)` 생성 시 `chart_series={}` 인자 제거
- [ ] 전체 코드베이스에서 `result.chart_series` 참조 검색 → 없어야 함 (cli 는 별도 경로로 호출하므로)
- [ ] `test_daily_runner.py` 에서 `DailyResult` 생성/검증하는 헬퍼 수정

---

### Phase 5 — pending_fill_reminders 논리 수정 (Gap 6)

**작업 내용**:

- [ ] `daily_runner.py::run_daily` 의 `pending_fill_reminders` 계산 로직 수정:
  ```python
  incoming_asset_ids = {f.asset_id for f in pending_fills}
  pending_fill_reminders = [
      asset_id
      for asset_id, asset in working_state.assets.items()
      if asset.pending_order is not None and asset_id not in incoming_asset_ids
  ]
  ```
- [ ] `test_daily_runner.py` 에 시나리오 추가:
  - T-1: 2 자산에 pending, 체결 0 건 → 2 자산 모두 리마인더
  - T-2: 2 자산에 pending, 1 자산만 체결됨 → 나머지 1 자산만 리마인더 (**기존 로직에서는 0 개였음**)
  - T-3: 2 자산에 pending, 2 자산 모두 체결 → 리마인더 0
  - T-4: pending 없음 → 리마인더 0

---

### Phase 6 — 문서 갱신

**작업 내용**:

- [ ] `docs/TEST_QBT_LIVE_MANUAL.md` #11 절차 재검토:
  - 현재 절차대로 CSV 의 종가를 10% 이상 수정했을 때 어떤 validator 가 트리거되는지 명확화
  - `validate_prev_close` 가 이 케이스에서 작동하는지 확인 (기본 임계값 1% 이상 차이 → 트리거)
  - 테스트 재실행 절차 명시
- [ ] `live/CLAUDE.md` "모듈별 역할 요약" 에 data_validator 가 run-daily 파이프라인에 통합되었음을 명시

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
  - `test_regression.py` 가 그린 유지 (정상 CSV 기반이라 영향 없어야 함)
  - 단위 테스트 전체 그린
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / data_validator 를 run-daily 에 연결하고 chart/user_trades 흐름 완성 + 리마인더 논리 수정
2. live / 설계 누락 6 개 일괄 보완 (validator wiring, chart signals, user_trades, dead field, reminder logic)
3. live / Phase A 감사 결과 반영 — 데이터 검증 실파이프라인 통합 + 차트 마커 + 리마인더 버그
4. live / run-daily 파이프라인 완성 및 chart_data marker/user_trade 누락 보완
5. live / 설계/구현 gap 정리 — 검증 와이어링 + 차트 signal/user marker + dead field + reminder 버그

## 7) 리스크(Risks)

- **Phase 1 의 validate_date_gap 이 exchange_calendars 의존성을 요구**: `poetry install -E live` 로 이미 설치되어 있지만, 검증 호출 시 calendar 인스턴스 생성 경로 필요. 기존 코드 재사용 가능한지 확인 필요. 불가능하면 `from exchange_calendars import get_calendar("XNYS")` 직접 호출.
- **Phase 2 의 신호 이력 스캔 비용**: `history/daily/*.json` 이 쌓이면 매 run-daily 마다 수천 개 파일 로드 가능. 초기에는 무시 가능하지만 장기적으로는 성능 이슈. **완화**: 파일 수가 임계치를 초과하면 `history/signals_cache.json` 으로 캐싱 고려 (plan 범위 밖, 미래 작업)
- **Phase 3 의 apply_fills_idempotent signature 변경**: 기존 호출자 (daily_runner) 를 함께 수정해야 함. 순수 함수 원칙 유지를 위해 history_dir 주입을 daily_runner 가 받아 전달하는 구조.
- **Phase 4 의 dead field 제거가 외부 호출자 깨뜨림**: 전체 코드베이스에서 `result.chart_series` 참조 없음을 grep 으로 확인해야 함 (이미 1차 확인됨 — cli 는 별도 경로). 테스트에서만 dict 비교 가능.
- **Phase 5 의 리마인더 논리 수정으로 기존 기대값 변경**: `test_daily_runner.py` 의 기존 pending_fill_reminders 관련 assertion 이 깨질 수 있음. 테스트 업데이트 필요.
- **Gap 1 의 data_validator 가 과잉 엄격하여 정상 케이스 차단 가능**: `validate_prev_close` 의 기본 임계값 1% 는 변동성 큰 장세에서 오탐 가능. 필요 시 임계값을 더 완화 (예: 20%) 하거나 **경고 로그만 남기고 계속 진행** 하도록 조정. 설계 의도 재검토 필요.
- **기존 Phase A 테스트 재실행**: Plan 완료 후 #4~#9 를 다시 돌려 회귀 없음을 확인해야 함. 실제 원격 리포에 영향.

## 8) 메모(Notes)

- 사용자 발견 계기: 2026-04-11 Phase A 수동 테스트 중 #11 이 실패로 감지되지 않는 것을 확인 → 전면 감사 요청
- Gap 5 (pending_fill_reminders) 는 엄밀히 "버그" 지만 사용자 요청에 포함되어 같이 처리
- Gap 7 (Node.js 20 deprecation) 은 GitHub 측 변화로 설계 누락 아님 → 별도 plan 권장. 긴급도는 낮음 (2026-06-02 까지 유예)
- Plan 크기가 큰 편 (6 phase + 마지막) — Phase 간 독립성이 높아 중간 Phase 완료 시점에 validate_project 를 **선택적으로** 돌려도 무방 (규칙상 마지막 Phase 에서만 필수)
- Plan 완료 후 [TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) 의 Phase A (#11~#13) 를 다시 실행하여 최종 검증

### 진행 로그 (KST)

- 2026-04-11 20:00: Draft 작성
- 2026-04-11 20:05: 사용자 사전 승인 → In Progress
- 2026-04-11 20:10: Phase 1 완료 — `_validate_against_csv` + `TestValidateAgainstCsv` (6) + `TestRunDailyValidatorIntegration` (4). data_validator wiring 완료
- 2026-04-11 20:15: Phase 2 완료 — `append_signal_history` / `load_signal_history` 추가, `chart_data` 에 `signal_history` 파라미터, 5 개 테스트 추가
- 2026-04-11 20:20: Phase 3 완료 — `_cmd_run_daily` 에 신규 fill 필터 + `append_user_trade` 호출, `load_user_trades` + `UserTrade` 스키마 맞춤, 2 개 통합 테스트 추가
- 2026-04-11 20:22: Phase 4 완료 — `DailyResult.chart_series` 제거, `daily_runner` / `test_models` 정리
- 2026-04-11 20:25: Phase 5 완료 — `pending_fill_reminders` 에 `incoming_fill_asset_ids` 도입, `TestPendingFillReminderLogic` (3) 추가
- 2026-04-11 20:27: Phase 6 완료 — `TEST_QBT_LIVE_MANUAL.md` #11 절차 갱신, `live/CLAUDE.md` `data_validator` 항목 업데이트
- 2026-04-11 20:30: Final Phase — `black live/`, `validate_project` passed=819/failed=0/skipped=0, smoke test (notify-failure) 통과 ✅ Done
