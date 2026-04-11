# Implementation Plan: QBT Live - Step 4 BufferZoneStrategy 직렬화

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

**작성일**: 2026-04-11 13:00
**마지막 업데이트**: 2026-04-11 13:12
**관련 범위**: live (신규 도메인)
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (4.3 BufferZoneStrategy 직렬화)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 4 체크리스트)
- [live/CLAUDE.md](../../live/CLAUDE.md) (QBT 본체 수정 금지 원칙)
- [src/qbt/backtest/strategies/buffer_zone.py](../../src/qbt/backtest/strategies/buffer_zone.py) (BufferZoneStrategy 소스)

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

- [x] 목표 1: `BufferZoneStrategy` 의 모든 private 내부 상태(`_prev_upper`, `_prev_lower`, `_hold_state`, `_last_buy_buffer_pct`, `_last_hold_days_used`)를 `BufferZoneState` 로 추출하는 `extract_buffer_state()` 구현
- [x] 목표 2: `BufferZoneState` 를 받아 기존 `BufferZoneStrategy` 인스턴스에 내부 상태를 복원하는 `restore_buffer_state()` 구현
- [x] 목표 3: TODO T-4.1 ~ T-4.3 테스트 시나리오 전체 통과 (hold_state 유무, 모든 private 변수 왕복)
- [x] 목표 4: QBT 본체(`src/qbt/`) 를 **수정하지 않고** 어댑터로만 구현

## 2) 비목표(Non-Goals)

- `daily_runner.py` 에서 이 어댑터를 호출하는 로직 (Step 7)
- `LiveState.assets[].buffer_zone_state` 와의 통합 사용 흐름 (Step 7 이후)
- 다른 전략(`BuyAndHoldStrategy`) 의 직렬화 — `BuyAndHoldStrategy` 는 stateless 이므로 불필요
- QBT 본체 수정 (원칙 금지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `BufferZoneStrategy` 는 실행 중 내부 상태(prev 밴드, hold_days 상태머신, get_buy_meta 반환값) 를 유지하는 stateful 객체이다
- live 환경에서는 매일 실행이 중단/재개되므로 이 내부 상태를 JSON 으로 저장/복원해야 한다 (설계서 4.3)
- QBT 본체는 백테스트 전용으로 설계되어 직렬화 API 가 없으며, live 요구사항으로 QBT 본체를 수정할 수 없다 (원칙)
- 따라서 live 쪽에 "어댑터" 를 둬 QBT 의 private 속성을 읽고/쓰는 방식으로 해결

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) (BufferZoneStrategy 내부 상태 상세)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 4.3

### 설계 결정

#### D1. 어댑터 배치 — **신규 파일 `live/src/live/buffer_serializer.py`**

**이유**:

- `state.py` 는 `LiveState` JSON 왕복 담당. `BufferZoneStrategy` 의존성이 추가되면 역할 혼재.
- `models.py` 는 순수 데이터 정의 파일이므로 QBT 동작 객체를 import 하지 않음.
- 어댑터 기능은 독립적이고 단일 목적이므로 전용 모듈이 명확하다.
- 모듈명: `buffer_serializer.py` (대안: `buffer_adapter.py`).

#### D2. 함수 시그니처 — **mutate-in-place 방식**

설계서 4.3 ("QBT 수정 없이 어댑터로 추출/복원") 에 맞춰 기존 `BufferZoneStrategy` 인스턴스에 상태를 주입하는 mutate 방식을 채택한다.

```python
def extract_buffer_state(strategy: BufferZoneStrategy) -> BufferZoneState: ...
def restore_buffer_state(strategy: BufferZoneStrategy, state: BufferZoneState) -> None: ...
```

**대안**: 새 객체를 생성해 반환하는 factory 방식(`create_with_state(ma_col, ...)`). mutate 방식이 설계서 문구에 충실하고 구현이 단순함.

#### D3. private 속성 접근 — **`setattr`/`getattr` 사용 + `# type: ignore` 최소화**

`BufferZoneStrategy._prev_upper` 등의 직접 접근은 pyright strict 모드의 `reportPrivateUsage` 경고 대상. 접근 방식:

1. 함수 내부에서는 `getattr(strategy, "_prev_upper")` 사용 → strict 모드 우회
2. 대안: `setattr(strategy, "_prev_upper", value)` 역시 동일 우회 패턴
3. 런타임 동작은 직접 접근과 동일

이 방식으로 `pyrightconfig.json` 을 수정하지 않아도 strict 모드를 유지할 수 있다.

## 4) 완료 조건(Definition of Done)

- [x] `live/src/live/buffer_serializer.py` 에 `extract_buffer_state`, `restore_buffer_state` 구현
- [x] `live/tests/test_buffer_serializer.py` 작성 및 통과 (T-4.1, T-4.2, T-4.3 + 추가 엣지 케이스) — 14 개 테스트 통과
- [x] QBT 본체(`src/qbt/`) 수정 없음 (`git status src/qbt/` 로 working tree clean 확인)
- [x] `poetry run black .` 실행 완료
- [x] `poetry run python validate_project.py` 통과 (passed=600, failed=0, skipped=0)
- [x] `docs/TODO_QBT_LIVE.md` Step 4 체크박스 3 개 체크
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

#### 신규 생성

- `live/src/live/buffer_serializer.py` (본 Step 에서 신설)
- `live/tests/test_buffer_serializer.py`

#### 수정

- `docs/TODO_QBT_LIVE.md` (Step 4 체크박스)
- `live/CLAUDE.md` (모듈별 역할 요약에 `buffer_serializer.py` 추가)

#### README 변경 여부

- `README.md`: **변경 없음**

### 데이터/결과 영향

- 없음 (순수 데이터 구조 변환만)
- 기존 `tests/` 결과에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 선작성 (레드 허용)

**작업 내용**:

- [x] `live/tests/test_buffer_serializer.py` 작성:
  - `TestExtractBufferState`:
    - `test_extract_initial_strategy_has_none_bands` — 갓 생성한 strategy 의 prev_upper/prev_lower 는 None
    - `test_extract_initial_strategy_has_none_hold_state` — 초기 hold_state 는 None
    - `test_extract_after_signal_computation` — 샘플 signal_df 로 check_buy 1~2회 호출 후 추출 → 필드 값이 갱신됨
    - `test_extract_has_schema_version_1`
  - `TestRestoreBufferState`:
    - `test_restore_none_hold_state_t_4_1` — T-4.1: hold_state 없는 상태 왕복
    - `test_restore_with_hold_state_t_4_2` — T-4.2: hold_state 있는 상태 왕복
    - `test_restore_all_private_fields_t_4_3` — T-4.3: 모든 private 필드 왕복 확인
    - `test_restore_mutates_in_place` — 호출 후 동일 strategy 객체의 상태 변경 확인
    - `test_restore_does_not_affect_constructor_params` — `_ma_col`, `_buy_buffer_pct` 등 생성자 파라미터는 건드리지 않음
  - `TestExtractRestoreRoundtrip`:
    - `test_roundtrip_identity_via_extract_restore` — extract → 새 strategy 생성 → restore → 다시 extract → 동일
    - `test_roundtrip_via_json` — extract → dataclasses.asdict → json.dumps → json.loads → BufferZoneState 복원 → restore. state.py 통합 검증

### Phase 1 — buffer_serializer.py 구현 (그린 유지)

**작업 내용**:

- [x] `live/src/live/buffer_serializer.py` 신규 작성:

  ```python
  """BufferZoneStrategy 의 내부 상태를 BufferZoneState 로 추출/복원하는 어댑터.

  설계서 4.3 "BufferZoneStrategy 직렬화" 의 QBT 수정 없이 어댑터로 추출/복원.
  """
  from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
  from live.models import BufferZoneState

  def extract_buffer_state(strategy: BufferZoneStrategy) -> BufferZoneState: ...
  def restore_buffer_state(strategy: BufferZoneStrategy, state: BufferZoneState) -> None: ...
  ```

- [x] 5 개 private 속성을 `getattr` / `setattr` 로 접근하여 SSoT 재사용 (하드코딩 회피)
- [x] `restore_buffer_state` 는 `state.schema_version` 을 검증하여 불일치 시 `ValueError`
- [x] Phase 0 테스트 통과 확인 (14 개)

### Phase 2 — 문서 동기화

**작업 내용**:

- [x] `docs/TODO_QBT_LIVE.md` Step 4 체크박스 체크 (`extract`, `restore`, 테스트 통과)
- [x] `live/CLAUDE.md` 의 "모듈별 역할 요약" 에 `buffer_serializer.py` 추가

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행 및 결과 기록
- [x] DoD 체크리스트 최종 업데이트
- [x] plan 상태 Done 으로 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=600, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `live / BufferZoneStrategy 직렬화 어댑터 (Step 4)`
2. `live / buffer_serializer.py 신설 — extract/restore + 왕복 테스트`
3. `live / QBT 수정 없이 버퍼존 내부 상태 JSON 왕복`
4. `live / prev_upper/prev_lower/hold_state 직렬화 어댑터`
5. `live / Step 4 BufferZoneState 추출/복원 + private 접근 캡슐화`

## 7) 리스크(Risks)

- **QBT 본체의 BufferZoneStrategy 내부 속성 이름이 변경될 경우** 어댑터가 깨진다.
  - 완화책: 테스트에서 실제 `BufferZoneStrategy` 를 생성하고 구동하여 속성 이름 변경을 즉시 감지. 주석에 SSoT(소스 경로)를 명시.
- **pyright strict 의 `reportPrivateUsage` 경고**: 직접 `strategy._prev_upper` 접근 시 경고 발생 가능.
  - 완화책: `getattr`/`setattr` 사용으로 우회. 필요 시 `# pyright: ignore[reportPrivateUsage]` 주석으로 명시적 보호.
- **QBT 수정 금지 원칙과 private 접근의 긴장**: 외부에서 private 접근은 캡슐화 위반이나, QBT 수정 금지가 상위 원칙. 본 어댑터는 불가피한 trade-off.

## 8) 메모(Notes)

### 주요 결정 사항

- D1: 어댑터는 신규 파일 `live/src/live/buffer_serializer.py` 에 배치
- D2: mutate-in-place 방식 (`restore_buffer_state(strategy, state) -> None`)
- D3: `getattr`/`setattr` 로 private 접근, strict 모드 우회

### BufferZoneStrategy 직렬화 대상 필드 (SSoT: src/qbt/backtest/strategies/buffer_zone.py)

생성자 파라미터 (직렬화 대상 아님):

- `_ma_col`, `_buy_buffer_pct`, `_sell_buffer_pct`, `_hold_days`

내부 상태 (직렬화 대상 — `BufferZoneState` 와 1:1 매핑):

| BufferZoneStrategy 필드 | BufferZoneState 필드 |
|---|---|
| `_prev_upper: float \| None` | `prev_upper` |
| `_prev_lower: float \| None` | `prev_lower` |
| `_hold_state: HoldState \| None` | `hold_state` |
| `_last_buy_buffer_pct: float` | `last_buy_buffer_pct` |
| `_last_hold_days_used: int` | `last_hold_days_used` |

### 진행 로그 (KST)

- 2026-04-11 13:00: 계획서 초안 작성, 설계 선택 D1~D3 확정
- 2026-04-11 13:05: Phase 0 test_buffer_serializer.py 14개 테스트 선작성 (extract/restore/roundtrip + JSON 통합)
- 2026-04-11 13:08: Phase 1 buffer_serializer.py 구현 — getattr/setattr 기반 어댑터, schema_version 검증
- 2026-04-11 13:10: Phase 2 TODO Step 4 체크박스 + live/CLAUDE.md 업데이트
- 2026-04-11 13:12: Ruff I001 / B009 수정 후 black + validate_project 통과 (passed=600, failed=0, skipped=0)

---
