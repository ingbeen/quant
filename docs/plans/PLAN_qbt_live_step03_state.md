# Implementation Plan: QBT Live - Step 3 상태 직렬화 (state.py)

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

**작성일**: 2026-04-11 12:50
**마지막 업데이트**: 2026-04-11 13:05
**관련 범위**: live (신규 도메인)
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (설계서 5장, 부록 A, 6.2)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 3 체크리스트)
- [docs/plans/PLAN_qbt_live_step02_models_constants.md](PLAN_qbt_live_step02_models_constants.md) (선행 Step — 데이터 모델)
- [live/CLAUDE.md](../../live/CLAUDE.md) (live 도메인 가이드)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) (테스트 규칙)

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

- [x] 목표 1: `LiveState` 의 JSON 직렬화/역직렬화 함수(`load_state`, `save_state`) 구현
- [x] 목표 2: `create_initial_state(total_capital)` 구현 — QBT 코어 `PORTFOLIO_CONFIGS[portfolio_q2_2xs]` 기반 초기 자산 구성
- [x] 목표 3: `applied_fill_ids` 의 저장/로드/정리 함수(`load_applied_fill_ids`, `save_applied_fill_ids`, `cleanup_old_fill_ids`) 구현
- [x] 목표 4: `test_state.py` 작성 및 통과 (TODO T-3.1 ~ T-3.5 전체)

## 2) 비목표(Non-Goals)

- `daily_runner.py` 로직 (Step 7)
- `BufferZoneStrategy` 어댑터 (Step 4)
- Git push / pull (Step 10 CLI)
- QBT 본체(`src/qbt/`) 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- live_state.json 은 qbt-live-state 프라이빗 리포의 정본 원장이며 매일 runner 가 load → mutate → save 한다
- Step 2 에서 정의한 `LiveState` 등 dataclass 는 순수 데이터 모델일 뿐이며 JSON 왕복 함수가 필요
- `applied_fill_ids` 는 idempotency 를 위한 중복 방지 ID 집합으로 90일 초과 항목을 자동 정리해야 한다 (설계서 6.2)
- 후속 Step (daily_runner, drift) 들이 모두 이 함수들을 기반으로 구현되므로 계약(특히 에러 처리) 을 먼저 고정해야 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (5장, 6.2, 부록 A)
- [src/qbt/backtest/portfolio_configs.py](../../src/qbt/backtest/portfolio_configs.py) (초기 상태의 자산 슬롯 참조)

### 설계 결정 (본 Step 에서 확정)

#### D1. `applied_fill_ids` 저장 포맷 — **dict[str, str]** (ID → ISO 타임스탬프)

**문제**: 설계서 부록 A 에는 `load_applied_fill_ids(path) -> set[str]` 로 명시되어 있으나, `cleanup_old_fill_ids(ids, max_age_days)` 를 호출할 때 `set[str]` 만으로는 각 ID의 나이를 판단할 수 없다.

**해결**:

- 파일 포맷은 `dict[str, str]` 로 저장 — 키는 fill ID(`ActualFill.rtdb_key`), 값은 ISO 8601 KST 타임스탬프 (`ActualFill.input_time_kst` 또는 실제 반영 시각).
- `load_applied_fill_ids` 의 반환 타입을 `dict[str, str]` 로 확장 (부록 A 대비 미세 변경).
- `cleanup_old_fill_ids` 도 `dict[str, str]` → `dict[str, str]` 로 변경. `max_age_days` 초과 항목 제거.
- 설계서 부록 A 의 시그니처를 본 Step 에서 업데이트한다 (사용자 승인 선택지 A).

#### D2. `create_initial_state` 의 자산 목록 — **QBT 코어 SSoT 재사용**

- `constants.get_live_portfolio_config()` 로 Q-2-2XS `PortfolioConfig` 를 조회 → `asset_slots` 의 `asset_id` 를 key 로 `AssetLiveState` 를 생성
- 자산별 초기값: `model_shares=0, model_avg_entry_price=0.0, model_entry_date=None, actual_*` 동일, `pending_order=None, signal_state="hold", entry_hold_days=0, buffer_zone_state=None`
- 현금 배분: `shared_cash_model = shared_cash_actual = total_capital` (설계서 5.2 초기 규칙)
- `portfolio_id = LIVE_PORTFOLIO_ID`

#### D3. JSON 직렬화 옵션 및 에러 처리

- `json.dumps(..., indent=2, ensure_ascii=False, sort_keys=False)` — 가독성 우선, 한글 포함 가능
- 저장 시 temp 파일 + atomic rename (`os.replace`) 로 저장 중 중단에도 파일 무결성 보장
- `load_state` 에러 매트릭스:
  - 파일 없음 → `FileNotFoundError` 그대로 전파 (호출자가 초기화 여부 결정)
  - JSON 파싱 실패 → `ValueError("live_state.json 파싱 실패: ...")` (설계서 11장 "상태 파일 손상" 대응)
  - 필수 필드 누락 → `ValueError("live_state.json 필드 누락: {field}")`
  - `schema_version` 불일치 → `ValueError("live_state.json schema_version 불일치. 기대: {SCHEMA_VERSION}, 실제: {v}")`

#### D4. 역직렬화 전략 — **명시적 필드 복원 (custom from_dict)**

- `dataclasses.asdict()` 의 역방향은 표준 라이브러리에 없으므로, 각 dataclass 별로 private `_live_state_from_dict`, `_asset_live_state_from_dict`, `_buffer_zone_state_from_dict` 함수를 정의
- 이 방식은 스키마 검증과 타입 변환을 명시적으로 수행할 수 있고 pyright strict 모드에서 안전
- `PendingOrderDict` 는 그대로 dict 이므로 별도 변환 불필요

## 4) 완료 조건(Definition of Done)

- [x] `live/src/live/state.py` 에 6 개 함수 모두 구현:
  - `load_state(path: Path) -> LiveState`
  - `save_state(state: LiveState, path: Path) -> None`
  - `create_initial_state(total_capital: float) -> LiveState`
  - `load_applied_fill_ids(path: Path) -> dict[str, str]`
  - `save_applied_fill_ids(ids: dict[str, str], path: Path) -> None`
  - `cleanup_old_fill_ids(ids: dict[str, str], max_age_days: int = 90) -> dict[str, str]`
- [x] `live/tests/test_state.py` 작성 및 통과
  - T-3.1: `create_initial_state(100_000_000) → save → load → 원본과 일치`
  - T-3.2: 설계서 JSON 예시 또는 직접 구성한 JSON 파일 → `load` → 필드 검증
  - T-3.3: `applied_fill_ids` 저장/로드 왕복
  - T-3.4: `cleanup_old_fill_ids`: 90 일 초과 ID 제거, 최근 ID 유지
  - T-3.5: 존재하지 않는 파일 → `FileNotFoundError` 전파
  - 추가: JSON 파싱 실패 → `ValueError`
  - 추가: schema_version 불일치 → `ValueError`
  - 추가: atomic save (중간 중단 시에도 파일 손상 없음) 검증 — tmp → replace 패턴 사용 확인
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 부록 A 의 `applied_fill_ids` 관련 시그니처를 `dict[str, str]` 로 업데이트 (D1 결정 반영)
- [x] `docs/TODO_QBT_LIVE.md` Step 3 체크박스 체크
- [x] `poetry run black .` 실행 완료
- [x] `poetry run python validate_project.py` 통과 (passed=586, failed=0, skipped=0)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

#### 신규 작성 (내용 채우기)

- `live/src/live/state.py` (현재 docstring 만 있음)

#### 신규 생성 (테스트)

- `live/tests/test_state.py`

#### 수정

- `docs/DESIGN_QBT_LIVE_FINAL.md` (부록 A applied_fill_ids 시그니처 업데이트)
- `docs/TODO_QBT_LIVE.md` (Step 3 체크박스)
- `live/CLAUDE.md` (필요 시 state.py 책임 추가)

#### README 변경 여부

- `README.md`: **변경 없음** (Step 24 에서 문서화)

### 데이터/결과 영향

- 없음 (파일 I/O 로직 추가만, 실제 qbt-live-state 리포는 사용자가 수동 초기화)
- 기존 `tests/` 결과에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 선작성 (레드 허용)

**작업 내용**:

- [x] `live/tests/test_state.py` 작성 (구현 전에는 ImportError 로 red):
  - `TestCreateInitialState`:
    - `test_create_initial_state_basic_fields`
    - `test_create_initial_state_uses_q2_2xs_asset_slots` — `assets` 의 key 가 `{"sso", "qld", "gld", "tlt"}`
    - `test_create_initial_state_shared_cash_equal_to_capital`
    - `test_create_initial_state_all_positions_zero`
    - `test_create_initial_state_portfolio_id_matches_constant`
  - `TestSaveLoadRoundtrip`:
    - `test_save_load_roundtrip_preserves_fields` — T-3.1
    - `test_save_load_roundtrip_with_pending_order` — pending 이 있는 상태도 왕복
    - `test_save_load_roundtrip_with_buffer_zone_state` — BufferZoneState + HoldState 직렬화
  - `TestLoadStateErrors`:
    - `test_load_state_file_not_found` — `FileNotFoundError` 전파 (T-3.5)
    - `test_load_state_invalid_json` — `ValueError` (파싱 실패)
    - `test_load_state_missing_required_field` — `ValueError`
    - `test_load_state_schema_version_mismatch` — `ValueError`
  - `TestAppliedFillIds`:
    - `test_save_load_applied_fill_ids_roundtrip` — T-3.3
    - `test_cleanup_old_fill_ids_removes_old` — T-3.4 (freezegun 으로 시간 고정)
    - `test_cleanup_old_fill_ids_keeps_recent`
    - `test_cleanup_old_fill_ids_default_max_age_is_90_days`
    - `test_load_applied_fill_ids_nonexistent_returns_empty` — 파일 없으면 빈 dict 반환 (초기 실행 대응)
  - `TestAtomicSave`:
    - `test_save_state_uses_temp_then_rename` — save 중 중단 시뮬레이션은 복잡하므로, 저장 후 tmp 파일이 남아있지 않음을 확인

### Phase 1 — state.py 구현 (그린 유지)

**작업 내용**:

- [x] 공통 헬퍼:
  - `_now_kst_iso() -> str`: 현재 KST ISO 8601 타임스탬프
  - `_atomic_write_text(path: Path, content: str) -> None`: temp → replace 패턴
  - `_live_state_from_dict(data: dict) -> LiveState`: 역직렬화
  - `_asset_live_state_from_dict(data: dict) -> AssetLiveState`
  - `_buffer_zone_state_from_dict(data: dict) -> BufferZoneState | None`
- [x] `create_initial_state(total_capital: float) -> LiveState`:
  - `total_capital <= 0` 이면 `ValueError`
  - `get_live_portfolio_config()` 로 자산 슬롯 조회
  - 각 slot 별로 `AssetLiveState` 생성 (0 포지션)
  - `LiveState` 반환 (`schema_version=SCHEMA_VERSION`, `portfolio_id=LIVE_PORTFOLIO_ID`)
- [x] `save_state(state, path)`:
  - `dataclasses.asdict(state)` → `json.dumps(..., indent=2, ensure_ascii=False)` → atomic write
  - 부모 디렉토리 자동 생성 (`path.parent.mkdir(parents=True, exist_ok=True)`)
- [x] `load_state(path)`:
  - 파일 존재 확인 → 없으면 `FileNotFoundError`
  - `json.loads` → `ValueError` 변환
  - `_live_state_from_dict` 호출 (스키마 검증 포함)
- [x] `save_applied_fill_ids(ids, path)`:
  - dict → json → atomic write
- [x] `load_applied_fill_ids(path)`:
  - 파일 없으면 빈 dict 반환 (초기 실행)
  - JSON 파싱 실패 → `ValueError`
- [x] `cleanup_old_fill_ids(ids, max_age_days=90)`:
  - 현재 KST 시각 기준 `max_age_days` 이상 경과한 ID 제거
  - 새 dict 반환 (원본 불변)
- [x] Phase 0 테스트 전체 통과 확인 (`poetry run pytest live/tests/test_state.py -v`) — 27개 테스트 통과

### Phase 2 — 문서 동기화

**작업 내용**:

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 부록 A 섹션 수정:
  - `def load_applied_fill_ids(path) -> set[str]` → `dict[str, str]`
  - `def save_applied_fill_ids(ids, path) -> None` (파라미터 타입 명확화)
  - `def cleanup_old_fill_ids(ids, max_age_days=90) -> set[str]` → `dict[str, str]`
- [x] `docs/TODO_QBT_LIVE.md` Step 3 체크박스 체크
- [x] `live/CLAUDE.md` 의 `state.py` 요약이 충분한지 점검 — 기존 요약이 충분히 일치하여 추가 수정 없음

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행 및 결과 기록
- [x] DoD 체크리스트 최종 업데이트
- [x] plan 상태 Done 으로 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=586, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `live / LiveState JSON 직렬화 및 applied_fill_ids 관리 (Step 3)`
2. `live / state.py 구현 — load/save/create_initial + cleanup 정책`
3. `live / 상태 원장 JSON 왕복 + atomic save`
4. `live / live_state.json 스키마 검증 및 idempotency 저장소`
5. `live / Step 3 state 직렬화 + DESIGN 부록 A 동기화`

## 7) 리스크(Risks)

- **설계서 부록 A 시그니처 수정**: `set[str]` → `dict[str, str]` 변경은 설계서 원문 편집이므로 문서 변경을 명시적으로 기록하고 TODO/CLAUDE.md 의 참조도 함께 갱신한다.
  - 완화책: 본 plan 에서 D1 으로 명시 기록, DESIGN 수정 커밋 포함.
- **`asdict` 가 TypedDict (`PendingOrderDict`) 및 `HoldState` 를 어떻게 직렬화하는가**: TypedDict 는 dict 이므로 asdict 가 그대로 dict 로 출력. HoldState 의 `date` 필드가 `datetime.date` 일 경우 JSON 직렬화 실패.
  - 완화책: HoldState 의 `start_date` 는 `date` 객체일 수 있으므로, save 시 ISO 문자열로 변환하는 전용 encoder 를 사용하거나 `_buffer_zone_state_to_dict` 에서 명시적으로 처리. 혹은 `default=str` 옵션을 `json.dumps` 에 전달하여 `date`/`datetime` 을 자동 문자열화.
- **atomic save 의 Windows 호환성**: `os.replace` 는 POSIX/Windows 모두 지원하지만 권한 이슈 가능.
  - 완화책: 본 live 실행 환경은 GitHub Actions Linux 이므로 Windows 비지원 문제는 우선순위 낮음.
- **create_initial_state 가 PORTFOLIO_CONFIGS 를 import 하여 자산 슬롯 순회**: 이는 live → qbt 단방향 의존으로 이미 확립된 패턴.

## 8) 메모(Notes)

### 주요 결정 사항

- D1: `applied_fill_ids` 는 `dict[str, str]` 포맷 (ID → ISO 타임스탬프). 설계서 부록 A 업데이트 포함.
- D2: `create_initial_state` 는 QBT `PORTFOLIO_CONFIGS` SSoT 재사용
- D3: JSON atomic save (`temp → os.replace`), `indent=2, ensure_ascii=False`, 에러 매트릭스 고정
- D4: 역직렬화는 명시적 `_*_from_dict` 헬퍼 사용 (pyright strict 대응)

### 진행 로그 (KST)

- 2026-04-11 12:50: 계획서 초안 작성, 설계 선택 D1~D4 확정
- 2026-04-11 12:55: Phase 0 test_state.py 27개 테스트 선작성 (create_initial_state, save/load roundtrip, 에러 매트릭스, applied_fill_ids 관리, atomic save)
- 2026-04-11 13:00: Phase 1 state.py 구현 — atomic write, _json_default, 역직렬화 헬퍼, 6개 공개 함수
- 2026-04-11 13:02: Phase 2 DESIGN 부록 A 시그니처 업데이트 (`dict[str, str]`) + TODO Step 3 체크박스 체크
- 2026-04-11 13:05: Ruff UP038 / I001 수정 후 black + validate_project 통과 (passed=586, failed=0, skipped=0)

---
