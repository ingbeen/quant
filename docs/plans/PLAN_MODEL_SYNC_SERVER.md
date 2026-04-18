# Implementation Plan: Model 동기화 기능 (서버 구현)

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

**작성일**: 2026-04-18
**마지막 업데이트**: 2026-04-18
**관련 범위**: live (daily_runner, rtdb_gateway, cli, notifier, models, state)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] 목표 1: 사용자가 앱에서 "지금 내 실제 포지션을 새 출발점으로 삼겠다" 고 요청(RTDB `/model_sync/inbox/{uuid}`)하면, 다음 `run-daily` 실행에서 model 축(주수 / 평균가 / 진입일 / 현금)을 actual 로 일괄 교체한다.
- [x] 목표 2: 동기화 시점의 모든 `pending_order` / `unfilled_order_date` 를 일괄 해제하고, 이후 stage 에서 새 model 기준으로 시그널 / 리밸런싱 / pending 을 재생성한다.
- [x] 목표 3: 처리 멱등성을 `processed` 플래그만으로 확보하고(별도 `applied_model_sync_ids.json` 원장 없음), 알림 / 히스토리 / RTDB read model 에 동기화 발생 여부가 드러나게 한다.

## 2) 비목표(Non-Goals)

- **앱 측 구현**: 확인 다이얼로그 / 버튼 / 토스트 UI, 앱의 RTDB 쓰기 로직은 이 plan 의 범위 밖이다 (서버 구현 선행).
- **자산별 / 선택 동기화**: 전체 동기화만 지원. `asset_id` 로 일부 자산만 동기화하는 기능은 만들지 않는다.
- **`reason` 사유 필드**: 동기화 페이로드에 사유 필드를 두지 않는다 (확인 다이얼로그 1 회로 충분).
- **별도 audit 원장**: `applied_model_sync_ids.json` / `/history/model_syncs/` / `history/model_syncs.jsonl` 는 만들지 않는다. `history/daily/{date}.json` 의 `DailyResult.model_sync_applied` 와 `history/states/{date}.json` 전후 스냅샷으로 추적한다.
- **`BufferZoneStrategy` 내부 상태 교체**: model_sync 는 포지션(주수 / 가격 / 진입일) 만 교체하고 `buffer_zone_state` (hold_days 상태머신 등) 는 건드리지 않는다.
- **자동 복구 / 자동 조정**: 동기화는 사용자 명시적 요청에만 수행하며, 자동 트리거는 만들지 않는다 (live 도메인 §핵심원칙 1).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- live 시스템의 model 축과 actual 축은 독립 운영된다. model 은 daily runner 가 매일 계산하고, actual 은 사용자 fill / balance_adjust 로만 갱신된다.
- 체결 타이밍 차이, 슬리피지, 개인 매매 등이 누적되면 actual 이 model 과 점진적으로 벌어진다. 격차가 커지면 model 기준 시그널 계산이 사용자 실제 포지션과 동떨어진 판단을 내릴 위험이 생긴다 (예: model 은 "SSO 300 주 전량 매도" 판단, 실제 보유는 250 주).
- drift 경고(`DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`) 만으로는 "새 출발점" 선언 수단이 없다. balance_adjust 는 actual 만 건드리므로 model 을 정렬하지 못한다.
- 사용자가 원할 때 model 을 actual 기준으로 한 번에 리셋할 수 있는 명시적 경로가 필요하다. 기존 inbox 패턴(fill / balance_adjust / fill_dismiss)을 그대로 따르되, 멱등 특성상 `processed` 플래그만으로 중복 방지가 충분하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) (live 도메인 SoT — 핵심원칙 1~4, 모듈별 역할, 코딩 규칙)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) (테스트 원칙)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §4 (처리 순서), §8 (RTDB 경로 / 계약)
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) (Phase C 수동 테스트 절차)
- [src/live/models.py](../../src/live/models.py) (데이터 모델 SoT)
- [src/live/daily_runner.py](../../src/live/daily_runner.py) (순수 계산 SoT)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `ModelSync` dataclass 가 `src/live/models.py` 에 추가되고 `__all__` 에 재노출된다.
- [x] `DailyResult.model_sync_applied: bool` 필드가 추가되고 기존 호출부가 컴파일/테스트 통과한다.
- [x] `run_daily()` 에 `pending_model_syncs: list[ModelSync] | None = None` 파라미터가 추가되고, `None` / 빈 리스트일 때 기존 동작과 완전히 동일하다 (회귀 확인).
- [x] `run_daily()` 내부에 Stage 3 "model_sync 반영" 이 fills / balance_adjust 이후, 전일 pending 체결 이전에 삽입된다.
- [x] model_sync 적용 시 모든 자산의 `model_shares` / `model_avg_entry_price` / `model_entry_date` 가 actual 값으로 교체되고, `shared_cash_model = shared_cash_actual` 로 교체된다.
- [x] model_sync 적용 시 모든 자산의 `pending_order = None`, `unfilled_order_date = None` 으로 초기화된다.
- [x] `rtdb_gateway.py` 에 `fetch_unprocessed_model_syncs` / `mark_model_syncs_processed` 가 추가되고, `delete_all_except_device_tokens` 의 삭제 경로 목록에 `/model_sync/inbox` 가 포함된다.
- [x] `cli.py` 의 `run-daily` 파이프라인이 model_sync inbox 를 읽어 `run_daily` 에 전달하고, 실행 후 `mark_model_syncs_processed` 를 호출한다.
- [x] `notifier.py` 의 일일 리포트 강조 블록에 "Model 동기화 적용" 라인이 `model_sync_applied==True` 인 경우에만 표시된다.
- [x] Phase 0 에서 고정한 정책 테스트 및 T-SYNC.1 ~ T-SYNC.8 / T-SYNC-GW.1 ~ T-SYNC-GW.3 시나리오 테스트가 모두 추가되어 통과한다.
- [x] `poetry run python validate_project.py` 통과 (passed=1019, failed=0, skipped=0).
- [x] `poetry run black .` 실행 완료 (마지막 Phase 에서 자동 포맷 적용).
- [x] 문서 업데이트 완료: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md), [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md). `README.md` 는 실행 명령어가 바뀌지 않으므로 **변경 없음**.
- [x] plan 체크박스 최신화 (Phase / DoD / Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/models.py` — `ModelSync` dataclass 추가, `DailyResult.model_sync_applied` 필드 추가, `__all__` 재노출.
- `src/live/daily_runner.py` — `run_daily` 시그니처 확장, Stage 3 (model_sync 반영) 로직 추가, `model_sync_applied` 플래그 반환.
- `src/live/rtdb_gateway.py` — `_MODEL_SYNC_INBOX_PATH` 상수, `fetch_unprocessed_model_syncs` / `mark_model_syncs_processed` 추가, `delete_all_except_device_tokens` 의 삭제 경로 목록 확장.
- `src/live/cli.py` — `run-daily` 파이프라인에 model_sync inbox fetch / mark, `run_daily` 호출 시 `pending_model_syncs` 전달.
- `src/live/notifier.py` — 일일 리포트 강조 블록에 "Model 동기화 적용" 라인 추가 (조건부).
- (선택적) `src/live/constants.py` — model_sync inbox 경로 상수가 필요하면 추가. 기본은 `rtdb_gateway.py` 내부 상수로만 둔다.
- `tests/live/test_daily_runner.py` — T-SYNC.1 ~ T-SYNC.8 시나리오 추가.
- `tests/live/test_rtdb_gateway.py` — T-SYNC-GW.1 ~ T-SYNC-GW.3 시나리오 추가.
- `tests/live/test_models.py` — `ModelSync` dataclass 구조 테스트 (최소).
- `tests/live/test_cli.py` — model_sync inbox 읽기 → mark 까지의 흐름 mock 테스트 (1 건).
- `tests/live/test_alert_coverage.py` 또는 `test_notifier.py` — 강조 블록에 "Model 동기화 적용" 라인 렌더링 테스트.
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §4 (처리 순서 + pending 취소 규칙), §8.2 (RTDB 경로), §8.3 (역할 분리 표) 갱신.
- `docs/TEST_QBT_LIVE_MANUAL.md` — Phase C 수동 테스트 절차에 "앱 동기화 → 서버 반영 확인" 추가.
- `src/live/CLAUDE.md` — 모듈별 역할 요약 / 핵심 원칙 3 (순수 계산) 설명에 model_sync 관련 내용 반영.
- `README.md`: **변경 없음** (실행 명령어 / 워크플로우 변동 없음).

### 데이터/결과 영향

- `DailyResult` 에 `model_sync_applied: bool` 필드 신규. `history/daily/{date}.json` JSON 스키마가 확장된다 (기존 키에는 영향 없음, 기존 레코드 재처리 불필요).
- `LiveState` 스키마 자체는 변경하지 않는다 (`unfilled_order_date` 는 이미 존재). `schema_version` bump 불필요.
- RTDB 에 신규 경로 `/model_sync/inbox/{uuid}` 추가. 기존 경로 / 페이로드는 변경 없음.
- 회귀 검증(`test_regression.py`) 기대값은 `pending_model_syncs=None` 기본값 경로를 타므로 결과 불변이어야 한다.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 이유: model 축 교체 / pending 취소 규칙은 live 의 핵심 정합성 불변조건에 해당하며, run_daily 의 Stage 순서 정책이 바뀌는 변경이다. 인터페이스와 정책을 먼저 테스트로 고정한 뒤 구현한다.

**작업 내용**:

- [x] `ModelSync` dataclass 스텁 추가 (`rtdb_key: str`, `input_time_kst: str`) 및 `__all__` 재노출 (`src/live/models.py`).
- [x] `DailyResult.model_sync_applied: bool` 필드 추가 (기본값 없음 — dataclass 인자 추가 후 기존 호출부 모두 업데이트).
- [x] `run_daily()` 시그니처에 `pending_model_syncs: list[ModelSync] | None = None` 추가 (Stage 3 로직은 이 Phase 에서는 비워둠 — 단지 파라미터만 수용하고 `model_sync_applied=False` 로 고정 반환).
- [x] 테스트 추가 (레드 허용):
  - [x] T-SYNC.1 (그린 가능): model_sync 없음 / `None` / 빈 리스트 → 기존 동작과 동일, `model_sync_applied==False`.
  - [x] T-SYNC.2 (레드): `pending_model_syncs=[ModelSync(...)]` 1 건 → 모든 자산의 `model_shares/avg/entry_date` 가 actual 과 동일, `shared_cash_model == shared_cash_actual`.
  - [x] T-SYNC.3 (레드): 동기화 + 전일 pending 존재 → 모든 자산의 `pending_order is None`, `unfilled_order_date is None`.
  - [x] T-SYNC.4 (레드): 동기화 + fill 같은 배치 → fill 먼저 actual 갱신 → 동기화는 갱신된 actual 을 복사 (Stage 순서 검증).
  - [x] T-SYNC.5 (레드): 동기화 + balance_adjust 같은 배치 → 보정 먼저 actual 덮어쓰기 → 동기화는 보정된 actual 을 복사.
  - [x] T-SYNC.6 (레드): 동기화 후 시그널 계산 → 새 model 기준으로 시그널이 발생하는 시나리오 1 건 (가격/보유량 조합으로 유도).
  - [x] T-SYNC.7 (레드): 동일 배치에 `ModelSync` 2 건 이상 → 1 회만 적용되며 결과는 1 회 적용과 동일 (멱등).
  - [x] T-SYNC.8 (레드): 동기화 발생 배치의 `DailyResult.model_sync_applied == True`.
  - [x] T-SYNC-GW.1 (레드): `fetch_unprocessed_model_syncs` → `processed=false` 항목만 반환.
  - [x] T-SYNC-GW.2 (레드): `mark_model_syncs_processed` → RTDB 업데이트 호출 인자에 `processed: True` 포함.
  - [x] T-SYNC-GW.3 (레드): inbox 비어있을 때 빈 리스트 반환.
  - [x] `test_regression.py` 는 수정하지 않는다 — `pending_model_syncs=None` 기본값 경로를 타므로 결과 불변이어야 한다. 실패 시 Phase 0 에서 즉시 파라미터 기본값을 바로잡는다.
- [x] `test_daily_runner.py` 기존 테스트들이 새 `DailyResult` 생성 시 `model_sync_applied` 를 명시해야 할 수 있으므로, 필요한 경우 픽스처 업데이트.

> 이 Phase 는 Phase 1 시작 시점에 의도적 실패 상태로 넘어갈 수 있다 (T-SYNC.2 ~ 8, T-SYNC-GW.1 ~ 3). T-SYNC.1 은 이 시점부터 그린이어야 한다.

---

### Phase 1 — 핵심 구현 (daily_runner Stage 3 + rtdb_gateway)

**작업 내용**:

- [x] `rtdb_gateway.py`:
  - [x] `_MODEL_SYNC_INBOX_PATH = "/model_sync/inbox"` 상수 추가.
  - [x] `_dict_to_model_sync(data, rtdb_key)` 내부 헬퍼 (`input_time_kst` 필수 / 빈 dict 허용하지 않음 → `ValueError`). `reason` / `asset_id` 는 읽지 않는다 (페이로드에 포함되더라도 무시).
  - [x] `fetch_unprocessed_model_syncs(app) -> list[ModelSync]`: `processed=false` 만 필터링.
  - [x] `mark_model_syncs_processed(app, keys)`: 각 key 경로에 `{"processed": True}` update.
  - [x] `delete_all_except_device_tokens` 의 `paths_to_delete` 에 `_MODEL_SYNC_INBOX_PATH` 추가.
  - [x] `__all__` 에 신규 함수 재노출.
- [x] `daily_runner.run_daily`:
  - [x] 파라미터 `pending_model_syncs: list[ModelSync] | None = None` 수용 (Phase 0 이미 적용됨).
  - [x] Stage 순서 확정: fills(Stage 1) → balance_adjust(Stage 2) → **model_sync(Stage 3 신규)** → 전일 pending 체결(Stage 4) → 시그널(Stage 5) → 리밸런싱(Stage 6) → pending 생성(Stage 7).
  - [x] balance_adjust 재배치 + model_sync 삽입:
    - [x] `balance_adjust` 적용을 "buffer strategy 복원 이후, 전일 pending 체결 직전" 으로 이동 (기존 Stage 11 위치에서 삭제).
    - [x] 그 직후에 `model_sync` 적용 블록을 삽입 (Stage 2.7).
    - [x] `drift` 계산은 기존과 동일하게 run_daily 마지막에서 수행 (actual 축 최신 상태 보장).
    - [x] 회귀 테스트(`test_regression.py`) 동일 결과 확인 — `balance_adjust` 이동이 과거 결과에 영향 없음 (6 건 모두 그린).
  - [x] Stage 3 블록 구체 로직:
    - [x] `if not pending_model_syncs: model_sync_applied = False` 단락 처리.
    - [x] 그렇지 않으면 아래를 1 회 수행 (리스트 길이 무관, 멱등):
      - `working_state.shared_cash_model = working_state.shared_cash_actual`
      - 모든 asset 에 대해 `model_shares = actual_shares`, `model_avg_entry_price = actual_avg_entry_price`, `model_entry_date = actual_entry_date`, `pending_order = None`, `unfilled_order_date = None`.
    - [x] `model_sync_applied = True` 로 세팅.
  - [x] `DailyResult` 반환 시 `model_sync_applied` 전달.
  - [x] `notification_body` 의 기본 요약은 기존 그대로 유지 (강조 블록은 Phase 2 에서 notifier 가 담당).
- [x] Phase 0 의 T-SYNC.1 ~ T-SYNC.8 / T-SYNC-GW.1 ~ T-SYNC-GW.3 를 모두 그린으로 전환.

---

### Phase 2 — CLI 파이프라인 + 알림 + reset 경로

**작업 내용**:

- [x] `cli.py` `run-daily` 파이프라인:
  - [x] `fetch_unprocessed_model_syncs(rtdb_app)` 호출 → 실패 시 `RuntimeError("RTDB model_syncs 읽기 실패: ...")` 즉시 중단 (기존 fill_dismiss 와 동일 패턴).
  - [x] `run_daily(..., pending_model_syncs=pending_model_syncs)` 로 전달.
  - [x] 실행 성공 후 `mark_model_syncs_processed(rtdb_app, [s.rtdb_key for s in pending_model_syncs])` 호출. **적용 여부 (`result.model_sync_applied`) 와 무관하게 읽어온 모든 key 를 mark** — 멱등이고 `processed` 가 유일한 중복 방지 수단이기 때문.
  - [x] mark 실패 시 `RuntimeError("RTDB model_syncs mark_processed 실패: ...")` 로 즉시 중단.
- [x] `cli.py` `reset` 커맨드: `rtdb_gateway.delete_all_except_device_tokens` 의 삭제 경로 목록에 `/model_sync/inbox` 가 포함되도록 반영 완료 (추가 cli.py 변경 불필요, Phase 1 에서 gateway 측에 반영됨).
- [x] `notifier._build_daily_body`:
  - [x] 강조 블록(`highlights`) 에 `"Model 동기화 적용"` 라인을 `result.model_sync_applied == True` 일 때만 추가.
  - [x] 순서: 맨 위(최우선)로 배치 — 사용자 행동의 "원인" 이벤트이므로 시그널 / 리밸런싱 / 리마인더보다 먼저.
  - [x] `send_failure_all` / `send_all` 시그니처는 건드리지 않음.
  - [x] 렌더링 테스트 3 건 추가 (`test_notifier.py::TestDailyBodyLayout::test_model_sync_*`).
- [x] `cli.py` 에 model_sync 관련 흐름 테스트 1 건 추가 (`test_cli.py::TestCmdRunDaily::test_model_sync_inbox_applied_and_marked`):
  - model_sync inbox 에 1 건 → `run_daily` 호출 시 `pending_model_syncs` 전달 → 실행 후 `mark_model_syncs_processed` 호출 + `history/daily/{date}.json` 에 `model_sync_applied: true` 기록 확인.
- [x] `_mock_rtdb_for_cli` 및 기존 `run-daily` 관련 CLI 테스트의 RTDB mock 확장 — `fetch_unprocessed_model_syncs` / `mark_model_syncs_processed` no-op 추가.

---

### Phase 3 — 문서 정리 및 최종 검증 (마지막 Phase)

**작업 내용**:

- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md):
  - §4.4 "model_sync 의미와 적용 순서" 섹션 신규 (pending 취소 규칙 + 엣지 케이스 표 포함).
  - §6.2 일일 리포트 본문 예시에 "Model 동기화 적용" 강조 라인 추가 + 행 구성 규칙 반영.
  - §8.2 RTDB 경로 구조에 `/model_sync/inbox/{uuid}` 추가.
  - §8.2.9a 신규 섹션 — 페이로드 스키마 / 필드 / 제약 / idempotency / 이력 추적 비미러 규칙.
  - §8.2.14 비미러 항목에 `model_sync` 추가 (fill_dismiss 와 동일 정책).
  - §8.3 역할 분리 표에 `/model_sync/*` 행 추가 + `processed` 필드 규칙 설명 확장.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md):
  - 모듈별 역할 표에 "(model_sync 처리)" 행 추가 (`run_daily` 내부 Stage 3 설명).
  - "RTDB 게이트웨이" 지원 경로 목록에 `/model_sync/inbox` 추가.
  - "핵심 원칙 3 (순수 계산)" 설명의 `run_daily` 입력 목록 / 적용 순서 / 멱등 규칙 확장.
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md):
  - Phase C 에 "14b. model_sync 요청 반영 확인" 신규 시나리오 추가 (앱 요청 → run-daily → processed=true / model=actual / 알림 라인 노출 / daily.json 기록 확인).
  - 최종 완료 체크리스트에 "Phase C (14, 14b)" 반영.
- [x] RTDB Rules 파일은 레포에 존재하지 않음 (운영자가 Firebase 콘솔에서 수동 관리). 상위 설계서 §8.3 역할 분리 표에 model_sync inbox 권한 정책이 반영되어 있으며, 운영자가 추후 콘솔에서 OWNER_UID 규칙을 추가해야 함 (Notes 에 기재).
- [x] `poetry run black .` 실행 (`tests/live/test_daily_runner.py` 1 파일 포맷 정리).
- [x] 전체 흐름 최종 검증 (Phase 0 ~ 2 의 모든 체크박스 완료 확인).
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1019, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / model 동기화 기능 신규 — `/model_sync/inbox` + run_daily Stage 3 + 알림 강조 블록
2. live / model_sync 파이프라인 구현 — RTDB inbox → run_daily → notifier 까지 end-to-end
3. live / model 축 동기화 요청 처리 — pending 취소 규칙 + 멱등 플래그 기반 중복 방지
4. live / `run_daily` Stage 재배치 및 model_sync 도입 (balance_adjust 순서 정상화 포함)
5. live / model 동기화 서버 구현 + 설계서 / 수동 테스트 문서 갱신

## 7) 리스크(Risks)

- **Stage 재배치 회귀 위험**: 현행 `daily_runner` 는 `balance_adjust` 를 맨 마지막에 적용한다. 본 plan 은 설계서/프롬프트 기준 순서(Stage 1 fills → 2 balance_adjust → 3 model_sync → 4 pending 체결) 로 재배치한다. 과거 회귀 구간에는 `pending_adjusts` 가 비어있어 결과 불변이어야 하지만, 이동 이후의 `entry_prices` / `entry_hold_days` 흐름 조정이 필요할 수 있다. **완화책**: Phase 1 에서 재배치 후 `test_regression.py` 를 우선 수행하여 일치 여부를 확인. 불일치 시 재배치 세부 위치를 원복 검토.
- **`DailyResult` 시그니처 변경 파급**: 기존 픽스처/테스트가 positional argument 로 `DailyResult(...)` 를 구성할 경우 깨질 수 있다. **완화책**: Phase 0 에서 기존 호출부를 모두 키워드 인자 기반으로 정리하고, `model_sync_applied` 는 기본값 없이 명시적 인자로 두어 누락을 컴파일 타임에 잡는다.
- **멱등 가정 위반**: model_sync 는 "model = actual" 덮어쓰기이므로 같은 배치 2 회 적용 결과 동일해야 한다. 그러나 만약 Stage 3 이후에 Stage 4~7 의 결과가 다시 `working_state` 를 바꾼다면 "처음 1 회 적용" 과 "다음 날 재실행" 사이에 model 이 다시 벌어질 수 있다. 이는 당연한 일상 운영이지만, 동일 run 내부에서 `pending_model_syncs` 가 2 건 이상일 때 **한 번만 적용** 하는지 테스트 T-SYNC.7 로 보장.
- **알림 본문 하위호환**: 기존 알림 수신자가 강조 블록 첫 라인이 "시그널" 이라 가정한다면 깨질 수 있다. **완화책**: 수신자는 사람(운영자) 한 명이며 앱은 FCM 푸시만 받으므로 영향 없음. 단, 수동 테스트 단계(Phase 3) 에서 실제 렌더링을 눈으로 확인.
- **RTDB Rules 누락**: 서버 코드만 배포되고 RTDB Rules 가 갱신되지 않으면 앱이 `/model_sync/inbox/` 쓰기 권한을 얻지 못한다. **완화책**: Phase 3 에서 rules 파일 존재 여부를 먼저 확인, 없으면 설계서 §8 에 "운영자 수동 반영 필요" 로 명시.

## 8) 메모(Notes)

### 설계 의사결정 요약

- `applied_model_sync_ids.json` 을 도입하지 않는다. 이유: model_sync 는 "model = actual" 덮어쓰기로 멱등 특성이 절대적이며, 기존 `processed` 플래그만으로 중복 방지가 충분하다. 원장을 추가하면 복잡도 증가 대비 얻는 이점이 없다.
- `reason` / `asset_id` 페이로드 필드를 도입하지 않는다. 이유: 확인 다이얼로그 1 회 UX 로 충분하며, 자산별 선택 동기화는 Non-Goal.
- `/history/model_syncs/{date}/{uuid}` RTDB 미러를 도입하지 않는다. 이유: `history/daily/{date}.json` + `history/states/{date}.json` 두 파일로 충분히 추적 가능, 발생 빈도가 월 0~1 회 수준.
- 알림은 FCM + 텔레그램 양쪽 모두 강조 블록으로 노출. 별도 알림 카드/토픽은 만들지 않는다.

### 스킵 사유 / 해제 조건

- 현재 계획 단계에서는 스킵 없음. `skipped > 0` 이 발생하면 Phase 를 추가 분해하여 해소.

### 후속 plan 후보

- 앱 측 동기화 버튼 / 다이얼로그 구현 plan (별도 리포).
- 동기화 이력 RTDB 미러가 필요해지면 별도 plan 으로 검토 (`/history/model_syncs/`).

### 진행 로그 (KST)

- 2026-04-18: plan 초안 작성.
- 2026-04-18: Phase 0 완료 — `ModelSync` dataclass + `DailyResult.model_sync_applied` 추가, `run_daily` 시그니처 확장, T-SYNC.1 ~ T-SYNC.8 / T-SYNC-GW.1 ~ T-SYNC-GW.3 테스트 작성.
- 2026-04-18: Phase 1 완료 — `rtdb_gateway.fetch_unprocessed_model_syncs` / `mark_model_syncs_processed` 구현, `delete_all_except_device_tokens` 경로 확장, `daily_runner` Stage 재배치 (balance_adjust → pending 체결 이전 이동) + Stage 3 (model=actual + pending 해제) 구현. 회귀 테스트(`test_regression.py`) 6 건 모두 그린.
- 2026-04-18: Phase 2 완료 — `cli.run-daily` 파이프라인이 model_sync inbox fetch / run_daily 전달 / mark_model_syncs_processed 호출, `notifier` 강조 블록 최상단에 "Model 동기화 적용" 라인 추가, 통합 테스트 추가, `history/daily/{date}.json` 에 `model_sync_applied` 기록.
- 2026-04-18: Phase 3 완료 — DESIGN §4.4 / §6.2 / §8.2 / §8.2.9a / §8.2.14 / §8.3 갱신, live CLAUDE.md 모듈/원칙 업데이트, 수동 테스트 시나리오 14b 추가, `poetry run black .` 적용, `validate_project.py` 통과 (passed=1019, failed=0, skipped=0).

---
