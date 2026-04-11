# Implementation Plan: QBT Live 알림 커버리지 · 통합 · 문서 내구성 정비

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-11 22:11
**마지막 업데이트**: 2026-04-11 22:45
**관련 범위**: live (src/live, tests, .github/workflows)
**관련 문서**: [live/CLAUDE.md](../../live/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: `cli.py` 의 **모든** 커맨드에서 예외 발생 시 중단 + 실패 알림(FCM + 텔레그램) 발송이 보장되도록 알림 훅을 `main()` 레벨로 일원화한다. 조용히 삼켜지는 `fallback` / `silent continue` 를 제거한다.
- [x] 목표 2: `balance_adjust` 적용을 `run_daily` 내부로 이관하여 "fills 먼저 → balance_adjust 나중" 순서를 순수 계산 함수 내부에서 보장한다. CLI 의 post-processing 제거.
- [x] 목표 3: `daily_runner` 내부의 간이 drift 계산을 제거하고 `drift.compute_drift` 를 유일한 정본으로 삼는다. `DailyResult` 가 전체 `DriftReport` 를 보유.
- [x] 목표 4: live 도메인 내 모든 "부록 B / 설계서 장번호(§N.N) / Step N / Gap N / Phase N" 주석/docstring/yml 주석을 전량 제거하고, 역할 중심 설명으로 교체한다. `DESIGN_QBT_LIVE_FINAL.md` 는 추후 삭제 예정이므로 **설계서를 참조하지 않는다**.
- [x] 목표 5: 타입 안전성(Literal 좁히기) 강화, 티커 추출 로직 중복 통합, history 파일명 / `SCHEMA_VERSION` 상수화 등 누적 리팩토링 부채 정리.
- [x] 목표 6: FCM/텔레그램 발송 실패는 **알림으로 재발송하지 않고 로그만 기록**한다 (알림 실패 시 알림 재시도는 모순).

## 2) 비목표(Non-Goals)

- 앱(React Native) / Firebase RTDB Rules / GitHub Secrets 운영 자체는 수정 범위 밖.
- `qbt-live-state` 리포의 데이터 스키마 마이그레이션은 범위 밖. `SCHEMA_VERSION` 일원화는 상수 참조만 통합하고 값은 그대로 유지한다.
- QBT 본체(`src/qbt/`) 코드 수정은 금지. 모든 변경은 `live/` 내부에서 수행한다.
- `DESIGN_QBT_LIVE_FINAL.md` 자체의 삭제/이관/재작성은 범위 밖. 본 plan 은 **live 코드/주석이 설계서를 참조하지 않게 만드는 것** 까지만 담당.
- live/CLAUDE.md 의 구조 전면 재작성은 범위 밖. 설계서 참조 제거 및 모듈표 정리 수준까지.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**치명 (사용자 요구 "무조건 알림" 위반)**

- `main()` top-level 의 예외 처리가 `logger.error + return 1` 에 그쳐, `_cmd_run_daily` 외 모든 커맨드(`init`, `init-data`, `rebuild-data`, `drift`, `fetch-fills`, `history`) 실패 시 알림이 발송되지 않는다.
- `_cmd_run_daily` 의 try 진입 **전** 코드(trade_date 파싱, NYSE 세션 체크)는 알림 훅 바깥이라 실패해도 알림이 가지 않는다.
- [live/src/live/cli.py:502-505](../../live/src/live/cli.py#L502-L505) history 저장 실패 시 `logger.error(...); # 계속 진행` 로 예외를 삼킨다 → 상위 알림 훅에 도달 못 함.
- [live/src/live/cli.py:598-601](../../live/src/live/cli.py#L598-L601) `_get_nyse_calendar()` 실패 시 `calendar = None` 으로 gap 검증을 통째로 skip. 데이터 검증 무력화.
- [live/src/live/notifier.py:143-157](../../live/src/live/notifier.py#L143-L157) `_safe_fcm` / `_safe_telegram` 이 예외를 삼키면서 **로그조차 기록하지 않음** → 실패 원인 추적 불가.

**설계 원칙 위반 / 로직 중복**

- `balance_adjust` 적용이 `run_daily` 밖의 CLI 계층에 있어 순수 계산 함수 경계가 모호하고, `dataclasses.replace` 를 위한 runtime import([cli.py:437](../../live/src/live/cli.py#L437))가 발생.
- `daily_runner.run_daily` 가 `drift.compute_drift` 를 호출하지 않고 [daily_runner.py:320-324](../../live/src/live/daily_runner.py#L320-L324) 에서 간이 drift 계산을 중복 구현. 자산별 `AssetDrift` / recommendation 이 누락된 채 `DailyResult.drift_pct` 에만 담긴다.

**문서 내구성 위반**

- `DESIGN_QBT_LIVE_FINAL.md` 의 "부록" 섹션이 이미 제거되었는데 live 코드 4곳이 여전히 "부록 B" 를 참조 ([constants.py:9](../../live/src/live/constants.py#L9), [models.py:3, 4, 60](../../live/src/live/models.py#L3)).
- `Step 3 D1`, `Step 4 어댑터`, `Step 5`, `Step 6`, `Step 7`, `Step 8`, `Step 13`, `Gap 2`, `Gap 3/4`, `Gap 6` 등 과거 작업 단계 번호 주석이 15+ 곳에 남아있음.
- `.github/workflows/daily_run.yml` 에 `"테스트 코드 ... 기존은 ... 였다 — 아래 주석 참고"` 변경 이력 주석 3곳, `keepalive.yml` 에 `=== [이전 버전 — qbt-live-state 타겟 참고용 보관] ===` 25 줄짜리 레거시 주석 블록.
- `DESIGN_QBT_LIVE_FINAL.md` 는 추후 삭제 예정이므로, 설계서 장번호/파일 참조 자체를 코드/주석/docstring/CLAUDE.md 에서 제거해야 향후 설계서 삭제 시 깨지지 않는다.

**타입/리팩토링 부채**

- [daily_runner.py:125, 197](../../live/src/live/daily_runner.py#L125) 의 `# type: ignore[arg-type]` 2건은 `PendingOrderDict.intent_type` / `SignalDetection.state` 를 `Literal` 로 좁히면 근본 제거 가능.
- 티커 추출 로직이 `cli.py`, `chart_data.py`, `constants.py` 4곳에 중복.
- [history.py:36-40](../../live/src/live/history.py#L36-L40) 의 `_DAILY_SUBDIR`, `_*_FILENAME` 이 모듈 프라이빗이어서 경로 구조 변경 시 호출처와 동기화가 암묵적.
- `constants.SCHEMA_VERSION`, `LiveState.schema_version`, `BufferZoneState.schema_version` 세 곳의 버전 값이 독립적으로 표류 가능.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 계층 분리, 상수 관리 3계층, 코딩 표준, 로깅 정책, 불가능 조건 처리, 주석 작성 원칙, 문서 내구성 원칙
- [live/CLAUDE.md](../../live/CLAUDE.md) — QBT 본체 수정 금지, 장애 시 자동 복구 금지, model/actual 분리, 순수 계산/I/O 분리, 백테스트 절대 규칙, 테스트 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, 외부 네트워크 mock, `@freeze_time`, `pytest.approx`
- [docs/CLAUDE.md](../CLAUDE.md) — plan 운영, Phase 구성, Commit Messages 규칙, KST 표기

## 4) 완료 조건(Definition of Done)

- [x] `main()` 단일 예외 훅에서 `_safe_notify_failure` 가 호출되며, `notify-failure` 커맨드를 제외한 모든 커맨드의 예외가 이 훅을 통과함 (단위 테스트로 증명).
- [x] `_cmd_run_daily` 내부의 중복 try/except 및 `_cmd_run_daily` 진입 전 코드의 알림 사각지대가 제거됨.
- [x] history 저장 실패 / calendar 로드 실패가 `raise` 로 전파되어 알림 훅에 도달함 (테스트로 증명).
- [x] `notifier._safe_fcm` / `_safe_telegram` 가 예외를 삼키되 `logger.error` 로 원인을 기록함. 실패 시 알림을 **재발송하지 않음**.
- [x] `run_daily(pending_fills, pending_adjusts)` 시그니처가 유효하며, balance_adjust 가 fills 직후 내부에서 idempotent 하게 적용됨. `DailyResult` 는 최종 상태만 보유.
- [x] `DailyResult.drift_report: DriftReport` 가 존재하며 `drift.compute_drift` 결과로 채워짐. 기존 간이 계산 제거.
- [x] `PendingOrderDict.intent_type` / `SignalDetection.state` 가 `Literal` 로 좁혀져 `# type: ignore[arg-type]` 2건이 제거됨.
- [x] 티커 추출 로직이 단일 유틸로 통합됨 (`extract_ticker_from_path`).
- [x] history 파일명 / subdir 가 `constants.py` 로 승격됨. 모듈 프라이빗 상수 제거.
- [x] `SCHEMA_VERSION` 일원화: `LiveState.schema_version` 은 `create_initial_state` 에서 `constants.SCHEMA_VERSION` 을 주입. `BufferZoneState.schema_version` 은 독립 버전 필드 (역할 다름) 로 유지.
- [x] live 도메인 내 **"부록 B / 설계서 N장 / §N.N / Step N / Gap N / Phase N"** 주석/docstring/yml 주석이 0 건 (`test_doc_durability.py` 로 증명).
- [x] `daily_run.yml` / `keepalive.yml` 의 변경 이력/레거시 주석 블록이 전량 제거되어 "현재 상태" 만 기술함.
- [x] `live/CLAUDE.md` 의 설계서(`DESIGN_QBT_LIVE_FINAL.md`) 참조가 제거되고 모듈표의 "관련 설계서" 열이 삭제됨.
- [x] 회귀 테스트(`test_regression.py`) 가 그대로 통과 (model 축 equity/positions/cash 동등성 유지).
- [x] 회귀/신규 테스트 추가 (`test_alert_coverage.py`, `test_doc_durability.py`, `test_daily_runner.py` 확장, `test_notifier.py` 확장)
- [x] `poetry run python validate_project.py` 통과 (passed=882, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase)
- [x] 필요한 문서 업데이트 완료 (`live/CLAUDE.md`, `.github/workflows/*.yml`; `README.md` 변경 없음)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드**

- `live/src/live/cli.py` — `main()` 공통 알림 훅, `_cmd_run_daily` 내부 try 제거, history silent continue 제거, calendar fallback 제거, post-processing balance_adjust 블록 제거, runtime import 승격, 설계서 번호/Step/Gap 주석 제거
- `live/src/live/daily_runner.py` — `pending_adjusts` 파라미터 추가, balance_adjust 적용 호출, 간이 drift 계산 제거 후 `drift.compute_drift` 호출, `DailyResult.drift_report` 채움, `# type: ignore` 2건 해소, Step/Gap 주석 제거
- `live/src/live/models.py` — `DailyResult.drift_report: DriftReport` 추가, `PendingOrderDict.intent_type` Literal 좁히기, `SignalDetection.state` Literal 이미 선언됨(주석 재확인), 부록 B/Step 주석 제거, `schema_version` 기본값을 `constants.SCHEMA_VERSION` 참조
- `live/src/live/state.py` — `LiveState.schema_version` 기본값 / 역직렬화 경로의 상수 참조 통합 (값 변경 없음)
- `live/src/live/drift.py` — 주석 내 설계서 장번호 제거, 역할 중심 docstring 으로 교체
- `live/src/live/balance_adjust.py` — 순수 함수로서 `run_daily` 내부 호출을 전제로 하는 docstring 업데이트
- `live/src/live/notifier.py` — `_safe_fcm` / `_safe_telegram` / 실제 발송 함수 내 `except` 에 `logger.error` 추가
- `live/src/live/data_validator.py` — 설계서 번호/Step 주석 제거
- `live/src/live/data_fetcher.py` — Step 주석 제거, `_PRICE_DECIMALS` 를 `constants.DEFAULT_PRICE_DECIMALS` 로 승격
- `live/src/live/history.py` — 모듈 프라이빗 파일명 상수를 `constants.py` 로 승격, Step 주석 제거
- `live/src/live/chart_data.py` — Step/Gap 주석 제거, 티커 추출을 공통 유틸 호출로 대체
- `live/src/live/constants.py` — 부록 B 참조 제거, history 파일명 상수 추가, `DEFAULT_PRICE_DECIMALS` 추가, `SCHEMA_VERSION` 일원화 보장
- `live/src/live/buffer_serializer.py` — 설계서 번호/Step 주석 제거, docstring 역할 중심 재작성
- `live/src/live/rtdb_gateway.py` — 설계서 번호/Step 주석 점검 및 제거
- `live/src/live/__init__.py` — 필요 시 Literal 타입 별칭 재익스포트

**테스트**

- `live/tests/test_cli.py` — main() 알림 훅 커버리지 테스트, history 실패 raise 테스트, calendar 실패 raise 테스트, `_cmd_run_daily` 진입 전 알림 테스트, notify-failure 재귀 방지 테스트
- `live/tests/test_daily_runner.py` — `pending_adjusts` 파라미터 적용, drift_report 검증, fills→adjust 순서 검증
- `live/tests/test_drift.py` — daily_runner 통합 후 회귀 검증 (기존 테스트 유지)
- `live/tests/test_notifier.py` — `_safe_fcm` / `_safe_telegram` 예외 시 `logger.error` 호출 검증
- `live/tests/test_regression.py` — 새로운 run_daily 시그니처 호환성 확인
- `live/tests/test_balance_adjust.py` — run_daily 내부 호출 경로 시나리오 추가
- `live/tests/test_workflows.py` — yml 내 `이전`, `기존`, `Step`, `Phase`, `Gap`, `§`, `부록` 문자열 0 건 검증

**문서 / 워크플로우**

- `live/CLAUDE.md` — 설계서 링크 / 부록 / 장번호 참조 제거, 모듈표의 "관련 설계서" 열 삭제
- `.github/workflows/daily_run.yml` — 변경 이력 주석 3곳, `"설계서 12장"` 주석 제거. 로직 동작은 유지.
- `.github/workflows/keepalive.yml` — `=== [이전 버전 ... ===` 25 줄 레거시 주석 블록 삭제
- `README.md`: **변경 없음** (live 도메인은 루트 README 범위 밖)

### 데이터/결과 영향

- `live_state.json` 스키마: 변경 없음.
- `DailyResult` 객체 스키마: `drift_report: DriftReport` 필드 추가. 기존 `drift_pct` 필드는 유지하되 `drift_report.drift_pct` 와 동일 값으로 설정 (호환성). DoD 재검토 후 필요하면 제거.
- `run_daily` 시그니처: `pending_adjusts: list[BalanceAdjust] | None = None` 추가 (기본값 None 으로 기존 호출자 호환).
- RTDB `/latest/*` 페이로드: 기존과 동일.
- history 파일 포맷: 변경 없음.
- qbt-live-state 리포의 JSON 포맷: 변경 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — 정책/인바리언트를 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] **알림 커버리지 테스트 (test_alert_coverage.py 신규)**: 모든 `_cmd_*` (init, init-data, rebuild-data, drift, fetch-fills, history) 가 예외 발생 시 `_safe_notify_failure` 를 호출하는지 monkeypatch spy 로 검증. `notify-failure` 는 재귀 방지(스스로는 호출 안 함) 확인.
- [x] **_cmd_run_daily 진입 전 알림 테스트**: `--trade-date 2026-13-40` (잘못된 날짜) / `_is_nyse_session` RuntimeError 주입 시 `_safe_notify_failure` 가 호출되는지 검증.
- [x] **history 저장 실패 raise 테스트**: `_persist_history` monkeypatch 로 RuntimeError 발생 시 `run-daily` 가 중단되고 알림 훅이 호출되는지 검증.
- [x] **calendar 로드 실패 raise 테스트**: `_get_nyse_calendar` monkeypatch 로 실패 주입 시 gap 검증 skip 없이 중단 + 알림 훅 호출 검증.
- [x] **run_daily pending_adjusts 파라미터 테스트 (test_daily_runner.py 확장)**: `run_daily(pending_fills=[...], pending_adjusts=[balance_adjust])` 호출 시 balance_adjust 가 fills 반영 이후에 적용되고 결과 `DailyResult.updated_state` 가 최종 상태를 갖는지 검증.
- [x] **DailyResult.drift_report 필드 테스트**: `run_daily` 결과가 `DriftReport` 타입의 `drift_report` 를 가지며 `drift_pct` 스칼라와 일치함을 검증.
- [x] **notifier 예외 시 logger.error 테스트 (test_notifier.py 확장)**: `_safe_fcm` / `_safe_telegram` 에 예외를 주입하고 logger spy 로 `logger.error` 기록 여부 검증. 함수가 raise 하지 않고 로그만 남기는 것을 확인.
- [x] **문서 내구성 grep 테스트 (test_doc_durability.py 신규)**: live/src/live/\*\*.py, live/CLAUDE.md, .github/workflows/\*.yml 에 대해 금지 패턴의 출현 횟수가 0 임을 검증.

**Validation (Phase 0)**:

- [x] 새 테스트가 의도한 대로 실패함 (레드 상태 27/36 실패 확인).
- [x] 기존 테스트는 그대로 통과 상태 유지.

---

### Phase 1 — 알림 커버리지 및 치명 fallback 제거(그린)

**작업 내용**:

- [x] **`main()` 공통 알림 훅 구현 (cli.py)**.
- [x] **`_cmd_run_daily` 내부 try 제거 (cli.py)**.
- [x] **history 저장 silent continue 제거**: `raise RuntimeError(f"히스토리 저장 실패: {exc}") from exc` 로 교체.
- [x] **calendar fallback 제거**: `_get_nyse_calendar()` 실패는 `raise` 로 전파.
- [x] **notifier 로그 추가**: `_safe_fcm` / `_safe_telegram` 의 except 블록에 `logger.error(..., exc_info=True)` 추가. 실패는 알림 재발송 없이 로그만 남김.
- [x] **Phase 0 테스트 그린 전환**: 알림 커버리지 테스트 28/28 통과 확인.

**Validation (Phase 1)**:

- [x] Phase 0 알림/fallback 관련 테스트 전부 통과.
- [x] 기존 live 테스트 회귀 없음.

---

### Phase 2 — balance_adjust 통합 + drift 일원화(그린)

**작업 내용**:

- [x] **`run_daily` 시그니처 확장**: `pending_adjusts` / `applied_balance_adjust_ids` 파라미터 추가.
- [x] **balance_adjust 적용 이관**: fills 처리 직후 `apply_balance_adjusts_idempotent` 호출.
- [x] **`DailyResult` 확장**: `updated_applied_balance_adjust_ids` + `drift_report: DriftReport` 필드 추가.
- [x] **간이 drift 계산 제거**: `drift.compute_drift` 호출로 교체. `actual_equity` / `drift_pct` 는 `drift_report` 에서 파생.
- [x] **CLI post-processing 삭제**: `dataclasses.replace` 블록 제거 및 `run_daily` 통합 호출로 일원화.
- [x] **테스트 보강**: Phase 0 의 balance_adjust / drift_report 테스트 전부 그린 전환.
- [x] **회귀 테스트 유지**: `test_regression.py` 포함 전체 테스트 365/365 통과.

**Validation (Phase 2)**:

- [x] balance_adjust / drift 관련 단위 테스트 전부 통과.
- [x] `test_regression.py` 회귀 테스트 통과.

---

### Phase 3 — 타입 / 상수 / 리팩토링 정리(그린)

**작업 내용**:

- [x] **`PendingOrderDict.intent_type` Literal 좁히기**: `IntentTypeLiteral` 타입 별칭 도입.
- [x] **`SignalDetection.state` Literal 선언 + `# type: ignore` 제거**.
- [x] **`_pending_order_from_dict` 역직렬화 검증 강화**: 허용 값 집합 체크 + 명시적 `cast`.
- [x] **티커 추출 유틸 통합**: `extract_ticker_from_path` 를 public 으로 승격하고 `cli.py` / `chart_data.py` / `build_signal_trade_map` 가 공통 유틸을 사용.
- [x] **history 파일명 상수 승격**: `HISTORY_*_FILENAME` / `HISTORY_DAILY_SUBDIR` 을 `constants.py` 로 이동.
- [x] **`DEFAULT_PRICE_DECIMALS` 승격**.
- [x] **`SCHEMA_VERSION` 일원화**: `create_initial_state` 가 `constants.SCHEMA_VERSION` 을 주입 (기존 구조 유지).
- [x] **기존 단위 테스트 회귀 없음**: 365/365 통과.

**Validation (Phase 3)**:

- [x] `grep "# type: ignore" live/src/live` 결과 0 건.
- [x] 티커 추출 중복 제거 확인.
- [x] 관련 단위 테스트 통과 + PyRight 0 에러.

---

### Phase 4 — 문서 내구성: 설계서 참조 / 변경 이력 주석 전량 제거(그린)

**작업 내용**:

- [x] **부록 B 참조 제거** (`constants.py`, `models.py`).
- [x] **Step N / Gap N / Phase N 주석 제거** (모든 live 코드).
- [x] **설계서 장번호 / §N.N 참조 제거** (`grep` 결과 0 건).
- [x] **`DESIGN_QBT_LIVE_FINAL.md` 파일 참조 제거** (live 코드 + `live/CLAUDE.md`).
- [x] **live/CLAUDE.md 업데이트**: 설계서 링크 제거, 모듈표의 "관련 설계서" 열 삭제, 역할 중심 재작성.
- [x] **daily_run.yml 변경 이력 주석 제거** 및 `printf '%s'` 로 Firebase 자격증명 안전 기록.
- [x] **keepalive.yml 레거시 주석 블록 삭제**.
- [x] **test_workflows.py 뒤집기**: 과거 "변경 이력 주석 유지" 테스트를 "금지" 테스트로 교체.
- [x] **test_doc_durability.py 그린 전환**.

**Validation (Phase 4)**:

- [x] live 코드 / live/CLAUDE.md / .github/workflows 금지 패턴 0 건.
- [x] 문서 내구성 테스트 통과.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] live/CLAUDE.md 최종 검토 (설계서 참조 제거, 모듈표 "관련 설계서" 열 삭제, 역할 중심 설명).
- [x] README.md 변경 없음 재확인 (live 도메인은 범위 밖).
- [x] `poetry run black .` 실행 (9 파일 포맷 적용).
- [x] 변경 기능 및 전체 플로우 최종 검증.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=882, failed=0, skipped=0) — Ruff / PyRight / Pytest 전부 통과.

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `live / CLI 알림 경로 일원화 및 자동 복구 fallback 제거`
2. `live / run_daily 내부에서 balance_adjust 통합 + drift 계산 일원화`
3. `live / 타입 안정성 강화 (Literal 좁히기) 및 상수/유틸 중복 제거`
4. `live / 설계서 참조 및 변경 이력 주석 전량 제거 (문서 내구성 확보)`
5. `live / 알림 정책 · run_daily 통합 · 문서 내구성 일괄 정비`

## 7) 리스크(Risks)

- **`run_daily` 시그니처 변경**: `pending_adjusts` 파라미터 추가가 기존 호출부 / 회귀 테스트에 영향. 기본값 `None` 으로 하위 호환 확보하되, test_regression.py 가 명시적 인자로 호출하는 경우 수정 필요.
- **`DailyResult.drift_report` 추가**: 테스트 스냅샷이 DailyResult 를 직렬화해 비교하는 경우 스냅샷 갱신 필요.
- **`drift.compute_drift` 수치 차이**: 간이 계산과 완전 계산이 `model_equity == 0` 또는 극한 상황에서 다른 값을 반환할 수 있음. 회귀 테스트에서 drift_pct 동등성 확인 필요.
- **`main()` 알림 훅 일원화 시 `rtdb_app` 초기화 범위**: 커맨드별로 rtdb_app 초기화 시점이 다르므로, `main()` 에서 `_safe_notify_failure` 호출 시 `rtdb_app=None` 을 전달할 수밖에 없는 경로가 생긴다. 이 경우 텔레그램만 발송되며 FCM 은 토큰 조회 실패로 no-op. 설계 허용 범위 (텔레그램 단독 알림도 충분히 사용자에게 전달된다) — 리스크는 낮음.
- **calendar fail-fast 전환**: `poetry install -E live` 가 완전히 설치되지 않은 로컬 환경에서 이전에는 gap 검증만 skip 되던 것이 이제 RuntimeError + 알림으로 동작. 의도된 변경이지만 사용자가 최초 실행 시 설치 완결성을 확인해야 함.
- **yml 주석 제거가 CI 동작에 영향**: yml 주석은 동작에 영향 없음. 테스트로 일부 주석 문자열을 assert 하고 있지 않은지 `test_workflows.py` 검토 필요.
- **`PendingOrderDict.intent_type` Literal 좁히기**: QBT 본체 `OrderIntent.intent_type` 의 Literal 과 불일치 시 타입 오류. QBT 본체의 Literal 을 import 하여 재사용하는 방식으로 해결.
- **타이밍 리스크**: `DESIGN_QBT_LIVE_FINAL.md` 가 이 plan 진행 중 삭제될 경우 docs/plans/ 내 링크가 깨질 수 있음 — 본 plan 은 설계서를 참조하지 않으므로 영향 없음.

## 8) 메모(Notes)

### 알림 정책 요약 (사용자 확정)

- **에러 발생 시 무조건 알림**: 모든 CLI 커맨드에서 예외 → 중단 → `_safe_notify_failure` 호출.
- **알림 실패는 로그만**: FCM / 텔레그램 발송 자체가 실패하면 알림으로 재발송하지 않고 `logger.error` 로만 기록 (재시도는 모순).
- **`notify-failure` 커맨드**: 재귀 방지를 위해 main() 훅에서 이 커맨드는 skip.

### 선택 근거 요약 (사용자 확정 A안)

- 확인 요청 1 (알림 훅) → A: `main()` 일원화.
- 확인 요청 2 (balance_adjust 위치) → A: `run_daily(pending_fills, pending_adjusts)` 내부 통합.
- 확인 요청 3 (drift 중복) → A: `DailyResult.drift_report: DriftReport` 도입.
- 확인 요청 4 (설계서 참조) → A: 역할 중심 설명. **`DESIGN_QBT_LIVE_FINAL.md` 는 추후 삭제 예정이므로 설계서 파일 참조 자체를 하지 않는다.**

### 진행 로그 (KST)

- 2026-04-11 22:11: 계획서 작성. 치명 (알림 커버리지) → 통합 (balance_adjust/drift) → 리팩 (타입/상수) → 문서 내구성 (설계서 참조 제거) → 최종 검증 순으로 5 Phase 구성.
- 2026-04-11 22:22: Phase 0 완료. `test_alert_coverage.py` / `test_doc_durability.py` 신규 + `test_daily_runner.py` / `test_notifier.py` 확장. 27 건 red 고정.
- 2026-04-11 22:30: Phase 1 완료. `main()` 공통 알림 훅 도입, `_cmd_run_daily` 내부 try 제거, history/calendar fallback 제거, notifier 로그 추가. 알림 커버리지 28/28 통과.
- 2026-04-11 22:36: Phase 2 완료. `run_daily` 에 `pending_adjusts` / `applied_balance_adjust_ids` 추가, `DailyResult.drift_report` 도입, 간이 drift 계산 제거. 365/365 통과.
- 2026-04-11 22:40: Phase 3 완료. `IntentTypeLiteral` 도입으로 `# type: ignore` 2건 제거, 티커 추출 유틸 통합, history 파일명 / `DEFAULT_PRICE_DECIMALS` 상수 승격. PyRight 0 에러.
- 2026-04-11 22:43: Phase 4 완료. 부록 B / 설계서 장번호 / Step / Gap / Phase 주석 전량 제거. `live/CLAUDE.md` 및 `.github/workflows/*.yml` 재작성. `test_workflows.py` 의 legacy-comment-preservation 테스트를 "금지" 테스트로 뒤집음. 375/375 통과.
- 2026-04-11 22:45: 마지막 Phase. `poetry run black .` (9 파일), `poetry run python validate_project.py` 통과 (passed=882, failed=0, skipped=0). Ruff / PyRight / Pytest 전부 OK.

---
