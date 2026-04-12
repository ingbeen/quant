# Implementation Plan: live fail-fast 정책 적용 (fallback 제거 + RuntimeError/ValueError 정립)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-12 09:00
**마지막 업데이트**: 2026-04-12 09:00
**관련 범위**: live
**관련 문서**: [live/CLAUDE.md](../../live/CLAUDE.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

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

- [ ] `drift.compute_drift` 의 `closes.get(asset_id, 0.0)` silent fallback 제거 → `RuntimeError("내부 불변조건 위반")`
- [ ] `drift._apply_single_fill` 의 unknown asset_id silent skip → `ValueError`
- [ ] `drift._apply_single_fill` 의 매도 초과 시 `new_shares < 0 → 0` 클리핑 제거 → `ValueError`
- [ ] `drift._apply_single_fill` 의 매수 시 shared_cash_actual 음수 방어 추가 (`ValueError`)
- [ ] `balance_adjust._apply_single_adjust` 의 unknown asset_id silent skip → `ValueError`
- [ ] `state._load_applied_ids` 의 타임스탬프 파싱 실패 시 "보수적 유지" → `ValueError` 전파
- [ ] `cli._initialize_rtdb_app` 동작 분기: `run-daily` 경로에서는 실패 시 즉시 `RuntimeError`, 나머지 커맨드(`drift`, `fetch-fills`, `notify-failure`, `history`)는 기존 동작 유지
- [ ] `cli._cmd_fetch_fills` 의 `return 1` → `RuntimeError` 전파 (알림 발송 경로 통합)
- [ ] `notifier._send_fcm_messages` 에서 `UNREGISTERED/NOT_FOUND` 외 오류에 WARNING 로그 추가 (조용히 묻히지 않도록)
- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md` 11절(실패/예외 대응) 표 업데이트

## 2) 비목표(Non-Goals)

- `history.load_user_trades` / `load_signal_history` 의 JSONL 파손 라인 처리 (현재 정책 "즉시 실패" 유지)
- `notifier._safe_fcm / _safe_telegram` 의 "알림 채널 자체 실패는 로그만" 정책 유지 (재발송 금지)
- `cli._refresh_live_csvs` 의 `today_row.empty → continue` 처리 — 이건 휴장 감지 후 분기이므로 현재 정책 유지
- `data_validator.validate_date_gap` 의 예외 래핑 방식 변경 (검증 에러 메시지 리스트 반환 원칙 유지)
- QBT 본체 수정 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- [drift.py:158](../../live/src/live/drift.py#L158) `closes.get(asset_id, 0.0)` — 종가 누락 시 drift 값이 왜곡된 채로 알림 발송
- [drift.py:77-79](../../live/src/live/drift.py#L77-L79) unknown asset_id 가 들어온 fill 을 silent skip → 앱의 버그 / 데이터 파손을 가림
- [drift.py:96-97](../../live/src/live/drift.py#L96-L97) `new_shares < 0 → 0` 클리핑 — 사용자가 보유량보다 많이 매도 입력해도 파이프라인이 무사히 돌아 잘못된 상태 저장
- [drift.py:83-92](../../live/src/live/drift.py#L83-L92) 매수 시 cash 가 음수가 되어도 방어 없음 — 매도 경로와 비대칭
- [balance_adjust.py:82-88](../../live/src/live/balance_adjust.py#L82-L88) unknown asset_id silent skip
- [state.py:446-452](../../live/src/live/state.py#L446-L452) 타임스탬프 파싱 실패 시 "보수적 유지" — 파손 데이터가 조용히 쌓임
- [cli.py:238-242](../../live/src/live/cli.py#L238-L242) `_initialize_rtdb_app` 실패 시 `None` 반환 → `run-daily` 가 `pending_fills=[]` 로 계속 진행되어 사용자 체결 반영이 묵살될 수 있음
- [cli.py:707-726](../../live/src/live/cli.py#L707-L726) `_cmd_fetch_fills` 의 `return 1` 은 `main()` 의 예외 훅을 우회하여 알림 미발송
- [notifier.py:131-137](../../live/src/live/notifier.py#L131-L137) FCM 실패 중 `UNREGISTERED/NOT_FOUND` 외 오류(quota 초과 등) 가 조용히 묻힘 — 로그 기록 누락
- 루트 CLAUDE.md "불가능 조건 처리" / live CLAUDE.md "자동 복구 금지 + 무조건 알림" 원칙과 위 fallback 들이 상충

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) — "불가능 조건 처리" 섹션
- [live/CLAUDE.md](../../live/CLAUDE.md) — "장애 시 자동 복구 금지 + 무조건 알림" 섹션
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 11장

## 4) 완료 조건(Definition of Done)

- [ ] `compute_drift` 에서 `closes` 에 `state.assets` 의 asset_id 가 누락되면 `RuntimeError("내부 불변조건 위반")`
- [ ] `_apply_single_fill` 에서 `state.assets` 에 없는 `fill.asset_id` 는 `ValueError("알 수 없는 asset_id")` (테스트에서는 pending 없이도 처리되는 fill 과 구분 필요 — `classify_fill` 은 유지하되, 반영 함수에서만 실패)
- [ ] `_apply_single_fill` 의 매도 초과 경우 (`new_shares < 0`) `ValueError("보유량 초과 매도")`
- [ ] `_apply_single_fill` 의 매수 결과 `shared_cash_actual < 0` 이면 `ValueError("현금 부족")`
- [ ] `_apply_single_adjust` 의 unknown asset_id → `ValueError("알 수 없는 asset_id")`
- [ ] `_load_applied_ids` 의 타임스탬프 파싱 실패 시 `ValueError` 전파
- [ ] `_initialize_rtdb_app` 의 시그니처/동작 변경 최소화 — 대신 `run-daily` 분기에서 "RTDB 필수" 를 강제하는 래퍼 또는 별도 함수 (`_require_rtdb_app()`) 를 추가해 `run-daily` 에서 호출. `fetch-fills`, `drift`, `history`, `notify-failure`, `init`, `init-data` 는 기존 `_initialize_rtdb_app` 사용
- [ ] `_cmd_fetch_fills` 에서 RTDB 초기화 실패 시 `RuntimeError` 발생 → `main()` 공통 훅이 알림 발송하도록 통합
- [ ] `_send_fcm_messages` 가 `UNREGISTERED/NOT_FOUND` 외 실패 토큰에 대해 `logger.warning("FCM 발송 실패: token=..., code=..., exc=...")` 1 줄 남김
- [ ] 영향 받는 테스트 갱신 + 신규 계약 테스트 추가:
  - [ ] `test_drift.py` — unknown asset, closes 누락, 매도 초과, 매수 초과 cash 각각의 예외 경로 검증
  - [ ] `test_balance_adjust.py` — unknown asset 예외 경로
  - [ ] `test_state.py` — 파손된 타임스탬프 로드 시 ValueError
  - [ ] `test_cli.py` — `fetch-fills` 실패가 `main()` 훅을 거쳐 알림 발송되는지 (`_safe_notify_failure` 가 호출되었는지 mock 검증)
  - [ ] `test_notifier.py` — `UNREGISTERED` 외 오류에 대해 `logger.warning` 호출 여부
- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md` 11장 표:
  - [ ] "unknown asset fill / balance_adjust" 행 추가 — "중단 + 알림"
  - [ ] "매도 초과 / 매수 cash 부족" 행 추가 — "중단 + 알림"
  - [ ] "closes 누락 (불변조건 위반)" 행 추가
  - [ ] "applied_*_ids 타임스탬프 파싱 실패" 행 추가
  - [ ] "RTDB 초기화 실패 (run-daily)" 행 추가 — "중단 + 알림"
- [ ] `live/CLAUDE.md` 원칙 섹션에 "unknown asset / 보유량 초과 매도 / cash 부족 / closes 누락 은 즉시 실패" 한 줄 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/drift.py` — compute_drift, `_apply_single_fill` 가드 강화
- `live/src/live/balance_adjust.py` — `_apply_single_adjust` unknown asset 가드
- `live/src/live/state.py` — `_load_applied_ids` 의 파싱 실패 가드
- `live/src/live/cli.py` — `_require_rtdb_app`, `_cmd_fetch_fills`, `_cmd_run_daily` 분기 업데이트
- `live/src/live/notifier.py` — FCM 실패 로그 추가
- `docs/DESIGN_QBT_LIVE_FINAL.md` — 11장 표 업데이트
- `live/CLAUDE.md` — 원칙 한 줄 추가
- `live/tests/` — 영향 테스트 갱신 + 신규 계약 테스트
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 출력 스키마 / LiveState JSON 변경 없음
- 기존 `test_alert_coverage.py` 의 "silent fallback 방어" 테스트가 본 Plan 의 강화 정책과 일관될 것으로 예상, 필요 시 갱신
- 운영 중 다음 시나리오에서 동작이 바뀜:
  - 사용자가 보유량 초과 매도 fill 입력 → 기존: 0 으로 클리핑 후 진행, 변경 후: 중단 + 알림
  - 앱이 존재하지 않는 asset_id 를 fill/balance_adjust inbox 에 기록 → 기존: silent skip, 변경 후: 중단 + 알림
  - Firebase 초기화 실패로 run-daily 진행 → 기존: RTDB 없이 진행, 변경 후: 중단 + 알림

## 6) 단계별 계획(Phases)

### Phase 0 — 실패 경로 계약 테스트 먼저 작성 (레드 허용)

**작업 내용**:

- [ ] `test_drift.py`:
  - [ ] `closes` 에 asset_id 가 누락된 경우 `RuntimeError` (match="내부 불변조건")
  - [ ] `fills` 에 state 에 없는 asset_id 가 포함된 경우 `ValueError` (match="알 수 없는 asset_id")
  - [ ] `fills` 의 sell 이 보유량 초과인 경우 `ValueError` (match="보유량 초과")
  - [ ] `fills` 의 buy 로 `shared_cash_actual` 가 음수가 되는 경우 `ValueError` (match="현금 부족")
- [ ] `test_balance_adjust.py`:
  - [ ] unknown asset_id 가 포함된 `BalanceAdjust` → `ValueError`
- [ ] `test_state.py`:
  - [ ] `applied_fill_ids.json` 의 value 가 "파싱 불가" 타임스탬프일 때 `load_applied_fill_ids` 가 ValueError
- [ ] `test_cli.py`:
  - [ ] `_cmd_fetch_fills` 가 RTDB 초기화 실패 시 `RuntimeError` 발생 (monkeypatch 로 `_initialize_rtdb_app` 이 None 반환)
  - [ ] `main()` 이 해당 RuntimeError 를 캐치하여 `_safe_notify_failure` 호출 (mock 으로 검증)
  - [ ] `_cmd_run_daily` 에서 `_require_rtdb_app()` 이 None 일 때 `RuntimeError`
- [ ] `test_notifier.py`:
  - [ ] FirebaseError 가 `UNREGISTERED` 코드가 아닌 경우, `_send_fcm_messages` 후 `logger.warning` 호출 여부 (caplog 활용)

---

### Phase 1 — drift / balance_adjust / state 가드 구현 (그린 유지)

**작업 내용**:

- [ ] `drift.compute_drift`:
  - [ ] `closes.get(asset_id, 0.0)` → `if asset_id not in closes: raise RuntimeError(...)`; `close = float(closes[asset_id])`
- [ ] `drift._apply_single_fill`:
  - [ ] unknown asset_id 에 대해 `raise ValueError(f"알 수 없는 asset_id={fill.asset_id}")`
  - [ ] buy 경로: 계산 후 `new_cash = state.shared_cash_actual - proceeds`; `if new_cash < 0: raise ValueError(...)`; 그 다음 `state.shared_cash_actual = new_cash`
  - [ ] sell 경로: `new_shares = asset.actual_shares - fill.actual_shares`; `if new_shares < 0: raise ValueError(...)`; 클리핑 제거
- [ ] `drift.apply_fills_idempotent`:
  - [ ] 기존 deepcopy 를 통한 입력 불변성은 유지하되, 실제로는 `_apply_single_fill` 에서 raise 하면 예외가 호출자로 전파되어 deepcopy 된 working state 는 버려짐 — **호출자(state)의 불변성 유지 계약이 깨지지 않음** (raise 전 부분 반영된 state 는 호출자에게 전달되지 않음)
- [ ] `balance_adjust._apply_single_adjust`:
  - [ ] unknown asset_id 경우 `raise ValueError(f"알 수 없는 asset_id={adjust.asset_id}")`
  - [ ] 단, `asset_id is None and new_cash is not None` 는 정상 케이스 (cash 만 보정) — 그대로 통과
- [ ] `state._load_applied_ids`:
  - [ ] 타임스탬프 파싱은 `_load_applied_ids` 에서 하지 않고 `cleanup_old_applied_ids` 에서 수행되므로, 본 DoD 항목은 `cleanup_old_applied_ids` 의 파싱 실패 ValueError 로 이동
- [ ] `state.cleanup_old_applied_ids`:
  - [ ] 파싱 실패 ID 는 `raise ValueError(f"applied_ids 타임스탬프 파싱 실패: id={fill_id!r}, value={iso_ts!r}")`
  - [ ] docstring 업데이트: "파손된 타임스탬프 발견 시 보수적 유지 대신 ValueError 로 즉시 실패"

---

### Phase 2 — cli / notifier 경로 수정 (그린 유지)

**작업 내용**:

- [ ] `cli._initialize_rtdb_app` 은 기존 동작 유지 (경고 로그 + None 반환). 용도: 실패해도 계속 진행해도 되는 경로 (`drift`, `history`, `notify-failure`)
- [ ] `cli._require_rtdb_app()` 신규 함수 추가:
  - [ ] 내부에서 `_initialize_rtdb_app()` 호출 → None 이면 `raise RuntimeError("Firebase 초기화 실패 — run-daily 진행 불가")`
- [ ] `cli._cmd_run_daily`: `rtdb_app = _initialize_rtdb_app()` → `rtdb_app = _require_rtdb_app()`. 이후 `if rtdb_app is not None:` 분기는 모두 삭제 (항상 존재한다는 전제)
- [ ] `cli._cmd_fetch_fills`:
  - [ ] `_initialize_rtdb_app()` 결과가 None 이면 `raise RuntimeError("Firebase 초기화 실패 — fetch-fills 진행 불가")`
  - [ ] `return 1` 제거
- [ ] `main()` 공통 훅은 현재 구조 그대로 작동 (RuntimeError 를 잡아 `_safe_notify_failure` 호출)
- [ ] `notifier._send_fcm_messages`:
  - [ ] invalid 검출 로직 분기에 else 분기 추가:
    ```python
    if "UNREGISTERED" in code or "NOT_FOUND" in code:
        invalid.append(token)
    else:
        logger.warning(f"FCM 발송 실패 (정리 대상 아님): token={token}, code={code}, exc={err}")
    ```

---

### Phase 3 — 테스트 갱신 및 계약 테스트 그린 확인 (그린 유지)

**작업 내용**:

- [ ] Phase 0 의 계약 테스트가 Phase 1/2 구현 후 그린 통과하는지 확인
- [ ] 기존 `test_alert_coverage.py` 의 "silent fallback 방어" 테스트를 본 Plan 의 강화 정책과 일관되게 조정 (과거 "silent skip 하지 않음" 에서 "즉시 예외 + 알림" 으로)
- [ ] `test_regression.py` 가 unknown asset 시나리오를 다루지 않는지 확인 (실제 데이터 기반이라 영향 없음을 기대)
- [ ] `test_cli.py` 에서 `_cmd_run_daily` mock 시나리오가 RTDB 성공 경로를 사용하도록 monkeypatch 조정

---

### Phase 4 — 문서/설계서 반영 (그린 유지)

**작업 내용**:

- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md` 11장:
  - [ ] 기존 표에 아래 행 추가:
    - `unknown asset_id 가 포함된 fill/balance_adjust` → `중단 + 알림 (ValueError)`
    - `보유량 초과 매도 fill` → `중단 + 알림 (ValueError)`
    - `매수 체결로 shared_cash_actual < 0` → `중단 + 알림 (ValueError)`
    - `compute_drift 에 closes 누락 (내부 불변조건)` → `중단 + 알림 (RuntimeError)`
    - `applied_*_ids 타임스탬프 파싱 실패` → `중단 + 알림 (ValueError)`
    - `RTDB 초기화 실패 (run-daily / fetch-fills)` → `중단 + 알림 (RuntimeError)`
  - [ ] 기존 "FCM 전송 실패" 행에 "UNREGISTERED 외 오류는 WARNING 로그 기록" 한 줄 추가
- [ ] `live/CLAUDE.md` "핵심 원칙" 에 한 줄 추가:
  - "unknown asset_id / 보유량 초과 매도 / 현금 부족 / closes 누락 / applied_ids 파싱 실패 는 자동 복구하지 않고 즉시 실패 + 알림"

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / fail-fast 정책 적용 — drift/balance_adjust/state/cli fallback 제거 + 설계서 반영
2. live / unknown asset / 보유량 초과 / cash 부족 / closes 누락 즉시 실패 + 알림
3. live / 자동 복구 금지 원칙 강화 — silent fallback 제거 + 계약 테스트 보강
4. live / run-daily RTDB 필수 + fetch-fills 알림 경로 통합 + drift/adjust 가드
5. live / 에러 정책 정립 (ValueError/RuntimeError) + 11장 실패 대응 표 갱신

## 7) 리스크(Risks)

- 실제 운영 중 사용자가 보유량 초과 매도를 빈번히 입력하는 습관이 있다면, 기존 silent 클리핑보다 체감 부담이 커짐. 완화책: 에러 알림 메시지에 보유량/입력값 함께 표시
- `apply_fills_idempotent` 에서 예외 발생 시 일부 fill 만 applied_ids 에 추가된 중간 상태가 생기지 않는지 재확인 (deepcopy 원본이 호출자에게 반환되지 않으므로 안전)
- `_cmd_fetch_fills` 의 알림 경로 통합으로 기존 테스트(`test_cli.py`) 가 `return 1` 경로를 기대한다면 조정 필요
- `test_alert_coverage.py` 가 silent fallback 을 테스트로 방어하고 있는데, 본 Plan 의 강화로 "더 엄격한 방어" 가 되므로 해당 테스트의 기대값을 업데이트
- Firebase 초기화 실패 케이스의 로컬 개발 경험: `GOOGLE_APPLICATION_CREDENTIALS` 미설정 환경에서 `run-daily` / `fetch-fills` 가 항상 실패하게 됨. 사용자가 인지해야 함

## 8) 메모(Notes)

- 본 Plan 은 PLAN_live_base_cleanup, PLAN_live_signal_state_none, PLAN_live_chart_ma_rename 완료 이후 진행한다
- `_require_rtdb_app` 은 독립 함수로 분리하여 재사용성 확보

### 진행 로그 (KST)

- 2026-04-12 09:00: 계획서 초안 작성

---
