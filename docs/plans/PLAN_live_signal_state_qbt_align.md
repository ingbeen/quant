# Implementation Plan: AssetLiveState.signal_state 를 QBT 동일 Literal["buy","sell"] 로 축소

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

**작성일**: 2026-04-12 13:00
**마지막 업데이트**: 2026-04-12 13:00
**관련 범위**: live
**관련 문서**: [live/CLAUDE.md](../../live/CLAUDE.md), [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드" 허용, Phase 1부터는 **그린 유지**.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**.
- 스킵은 가능하면 **Phase 분해로 제거**.

---

## 1) 목표(Goal)

- [x] `AssetLiveState.signal_state` 를 QBT 와 동일한 `Literal["buy", "sell"]` 2 값으로 축소
- [x] `SignalDetection.state` 는 live 전용 `Literal["buy", "sell", "none"]` 유지 (당일 신호 감지용, QBT 에 대응 없음)
- [x] `SignalStateLiteral` 공통 타입 폐지 → 각각 독립 타입
- [x] `_build_asset_states` 매핑/방어벽 코드 제거 → QBT `AssetState` 로 직접 pass-through
- [x] `SCHEMA_VERSION: 2 → 3`
- [x] 설계서 / live CLAUDE.md 업데이트

## 2) 비목표(Non-Goals)

- QBT 본체(`src/qbt/`) 수정 없음
- `SignalDetection.state` 의 `"none"` 제거 없음 (당일 신호 감지에 필요)
- CLI / notifier / chart_data 로직 변경 없음 (SignalDetection 쪽은 기존 그대로)

## 3) 배경/맥락(Context)

### 현재 문제점

Plan 2 에서 `AssetLiveState.signal_state` 와 `SignalDetection.state` 를 같은 `SignalStateLiteral = Literal["buy", "sell", "none"]` 으로 묶었으나, 두 필드의 의미가 다르다:

- `AssetLiveState.signal_state`: **누적 상태** (보유 중 / 미보유). QBT 와 동일 모델.
- `SignalDetection.state`: **당일 감지** (오늘 매수/매도/신호없음). live 전용.

QBT 백테스트는 초기값을 `AssetState(position=0, signal_state="sell")` 로 세팅하며, "초기 상태" 와 "매도 후 상태" 를 구분하지 않는다. live 도 동일 모델을 따르면 매핑 코드가 사라지고 일관성이 높아진다.

### 영향받는 규칙

- [CLAUDE.md](../../CLAUDE.md), [live/CLAUDE.md](../../live/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

## 4) 완료 조건(Definition of Done)

- [x] `AssetLiveState.signal_state: Literal["buy", "sell"]` (3값 → 2값)
- [x] `create_initial_state` 의 초기값 `signal_state="sell"` (QBT 동일)
- [x] `_asset_live_state_from_dict` 검증이 `{"buy", "sell"}` 만 허용
- [x] `SignalDetection.state: Literal["buy", "sell", "none"]` 유지 (별도 타입)
- [x] `SignalStateLiteral` / `VALID_SIGNAL_STATES` 제거, 각 필드에 인라인 Literal 사용
- [x] `_build_asset_states` 매핑/방어벽 코드 전면 삭제 → pass-through
- [x] `SCHEMA_VERSION: 2 → 3` bump
- [x] `DESIGN_QBT_LIVE_FINAL.md` 5.1 절 signal_state 설명 갱신
- [x] `live/CLAUDE.md` 원칙 갱신
- [x] 테스트 업데이트 (AssetLiveState 관련 `"none"` → `"sell"`, 방어벽 테스트 제거)
- [x] `poetry run python validate_project.py` 통과 (passed=880, failed=0, skipped=0)
- [x] `poetry run black .` 실행
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `live/src/live/models.py` — SignalStateLiteral 제거, AssetLiveState 타입 축소, SignalDetection 독립 유지
- `live/src/live/constants.py` — SCHEMA_VERSION 3
- `live/src/live/state.py` — 초기값 "sell", 검증 {"buy","sell"}
- `live/src/live/daily_runner.py` — `_build_asset_states` 단순화
- `live/CLAUDE.md` — 원칙 갱신
- `docs/DESIGN_QBT_LIVE_FINAL.md` — 5.1 절 갱신
- `live/tests/` — 관련 테스트 갱신
- `README.md`: **변경 없음**

### 데이터/결과 영향

- `SCHEMA_VERSION: 2 → 3`. 사용자가 방금 `init` 재실행했으므로 다시 `init` 필요.
- `qbt-live-state` 에 저장된 `signal_state: "none"` → `"sell"` 로 변경됨

## 6) 단계별 계획(Phases)

### Phase 1 — 모델/초기값/매핑 변경 (그린 유지)

- [x] `models.py`: `SignalStateLiteral` / `VALID_SIGNAL_STATES` 제거, `__all__` 에서 삭제
- [x] `models.py`: `AssetLiveState.signal_state: Literal["buy", "sell"]`
- [x] `models.py`: `SignalDetection.state` 는 인라인 `Literal["buy", "sell", "none"]` 유지, docstring 에 "당일 감지 전용, AssetLiveState 와 다른 타입" 명시
- [x] `constants.py`: `SCHEMA_VERSION = 3`, 주석 "v2 → v3: AssetLiveState.signal_state 를 {buy,sell} 2 값으로 축소"
- [x] `state.py`: `create_initial_state` 의 `signal_state="sell"`, `_asset_live_state_from_dict` 검증 `{"buy", "sell"}`
- [x] `state.py`: `VALID_SIGNAL_STATES` import 제거
- [x] `daily_runner.py`: `_build_asset_states` 를 pass-through 로 축소 (매핑/방어벽 전면 삭제)

### Phase 2 — 테스트 갱신 (그린 유지)

- [x] `test_state.py`: `signal_state == "none"` → `"sell"`, 수동 JSON fixture `schema_version: 3`
- [x] `test_constants.py`: `SCHEMA_VERSION == 3`
- [x] `test_models.py`: AssetLiveState Literal 검증 `{"buy", "sell"}`, SignalDetection 은 `{"buy", "sell", "none"}` 유지
- [x] `test_daily_runner.py`: 방어벽 테스트 (`TestSignalStateNoneInvariant`) 제거, 초기 signal_state `"sell"` 검증
- [x] 나머지 테스트에서 AssetLiveState 관련 `"none"` → `"sell"` 치환

### Phase 3 — 문서/설계서 갱신 (그린 유지)

- [x] `DESIGN_QBT_LIVE_FINAL.md` 5.1 절: signal_state 설명을 "QBT 와 동일 Literal[buy,sell]" 로 갱신, SignalDetection 은 별도 설명
- [x] `live/CLAUDE.md`: 원칙 갱신 ("signal_state 는 QBT 와 동일 2 값")

### 마지막 Phase — 최종 검증

- [x] `poetry run black .`
- [x] `poetry run python validate_project.py` (passed=880, failed=0, skipped=0)
- [x] DoD / Phase 체크리스트 최종 업데이트

#### Commit Messages (Final candidates)

1. live / AssetLiveState.signal_state 를 QBT 동일 Literal["buy","sell"] 로 축소
2. live / signal_state 모델 QBT 정렬 — "none" 제거 + 매핑 코드 삭제 + SCHEMA_VERSION v3
3. live / 원장 signal_state 와 당일 감지 state 타입 분리 (QBT 일관성)

## 7) 리스크

- `SCHEMA_VERSION: 2 → 3` — 사용자가 방금 init 완료했으므로 다시 init 필요. 단, 아직 실매매 진입 전이라 데이터 손실 없음.

## 8) 메모

- Plan 2 에서 도입한 `SignalStateLiteral` 공통 타입이 두 필드의 의미 차이를 가렸던 설계 실수를 수정

### 진행 로그 (KST)

- 2026-04-12 13:00: 계획서 작성 + 즉시 실행

---
