# Implementation Plan: live signal_state "hold" → "none" 통일 및 SignalStateLiteral 도입

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

- [x] `AssetLiveState.signal_state` 와 `SignalDetection.state` 의 허용 값을 `"buy" / "sell" / "none"` 으로 통일
- [x] `live/src/live/models.py` 에 공통 타입 별칭 `SignalStateLiteral = Literal["buy", "sell", "none"]` 도입
- [x] QBT 본체 수정 없이 `live.AssetLiveState.signal_state` 의 `"none"` 을 QBT 엔진 `AssetState.signal_state` 의 `"sell"` 로 매핑 (기존 `"hold"→"sell"` 과 동일 의미) + 매핑 계약을 방어벽으로 강제
- [x] `SCHEMA_VERSION` 을 `1 → 2` 로 bump, 기존 v1 상태 파일 로드 시 ValueError 전파
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 에 signal_state 값 집합 변경을 반영
- [x] live 전수 테스트에서 `"hold"` 문자열을 `"none"` 으로 치환하고 계약 테스트 추가

## 2) 비목표(Non-Goals)

- QBT 본체(`src/qbt/backtest/portfolio_types.AssetState.signal_state`) 의 `Literal["buy", "sell"]` 변경 없음
- `BufferZoneStrategy._hold_state` (QBT 내부 hold_days 상태머신) 관련 변경 없음 (이름 충돌이 해소되는 것이 이 Plan 의 목적 중 하나)
- v1 → v2 자동 마이그레이션 구현 없음 (사용자가 `init` 재실행 또는 수동 변환). 이유: 현재 운영 중 live_state.json 이 프라이빗 리포에만 있고 단일 사용자 환경
- `ChartSeries.ema_200` 리네임 (PLAN_live_chart_ma_rename)
- fallback 제거 (PLAN_live_failfast_policy)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `AssetLiveState.signal_state` 의 초기값이 `"hold"` 로 설정되어 있으나, 실제 의미는 **"아직 한 번도 매수/매도 시그널이 발생하지 않은 초기 상태"** 임
- `SignalDetection.state: Literal["buy", "sell", "hold"]` 의 `"hold"` 도 실제로는 **"오늘 새로 뜬 시그널 없음"** 의미
- QBT 본체의 `BufferZoneStrategy._hold_state` 는 **"상향돌파 감지 후 hold_days 동안 유지 조건 확인 대기"** 라는 완전히 다른 개념 → 같은 단어가 두 의미로 쓰여 혼동 유발
- 매도는 `check_sell` 에서 "종가가 하단밴드 아래 → 다음날 시가 무조건 매도" 이며 hold_days 와 무관
- 두 곳의 `"hold"` 를 `"none"` (신호 없음) 으로 통일하면:
  - live 쪽 의미가 명확 ("none = 신호 없음")
  - QBT 쪽 `_hold_state` 는 전략 내부 상태로 독립되어 이름 충돌 해소
- 앱은 아직 구현 전이므로 RTDB payload 의 `"hold"` → `"none"` 변경이 외부 영향 없음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트 — 타입 힌트, Literal 사용)
- [live/CLAUDE.md](../../live/CLAUDE.md) (QBT 본체 수정 금지 원칙)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (설계서는 본 Plan 에서 갱신)

## 4) 완료 조건(Definition of Done)

- [x] `SignalStateLiteral = Literal["buy", "sell", "none"]` 이 `live.models` 에 정의되고 `AssetLiveState.signal_state` / `SignalDetection.state` 가 이 타입을 사용
- [x] `create_initial_state` 가 `signal_state="none"` 으로 초기화
- [x] `daily_runner._build_signal_detections` 의 기본 `state_str` 이 `"none"`
- [x] `daily_runner._build_asset_states` 의 매핑 규칙: `"buy" → "buy"`, `"sell"/"none" → "sell"`. 또한 `signal_state == "none" and model_shares > 0` 이면 `RuntimeError("내부 불변조건 위반: signal_state=none 이지만 model_shares>0")` 발생
- [x] `SCHEMA_VERSION = 2` 로 bump, `_live_state_from_dict` 가 v1 로드 시 기존 ValueError 경로로 실패
- [x] `_asset_live_state_from_dict` 가 `signal_state` 값이 `VALID_SIGNAL_STATES` 집합에 속하는지 검증, 아니면 ValueError
- [x] `notifier.send_all` / `rtdb_gateway.write_read_model` / `chart_data.build_chart_series` / `history` 모듈이 `"none"` 값을 자연스럽게 무시 (기존 `"buy"/"sell"` 필터 로직과 호환 확인)
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 에서 다음을 업데이트:
  - [x] 3절/6절(상태 원장) 설명에 `signal_state ∈ {"buy", "sell", "none"}` 명시
  - [x] `SCHEMA_VERSION` 정책을 "포맷 변경 시 bump, 기존 v1 파일 로드 불가" 로 보강
- [x] live 테스트 내 `"hold"` 문자열 검증 → `"none"` 으로 치환 (PLAN_live_tests_cleanup 에서 처리되는 주석 제거와는 별개로, **값 검증** 은 이 Plan 에서 즉시 처리)
- [x] 신규 테스트: `_build_asset_states` 가 `"none" + shares>0` 조합에서 `RuntimeError` 를 던지는 계약 고정
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/models.py` — `SignalStateLiteral` 정의, `AssetLiveState.signal_state`, `SignalDetection.state` 타입 좁히기, `VALID_SIGNAL_STATES` 집합 export
- `live/src/live/constants.py` — `SCHEMA_VERSION: 1 → 2`, (필요 시 주석 업데이트)
- `live/src/live/state.py`:
  - `create_initial_state`: `signal_state="none"` 으로 변경
  - `_asset_live_state_from_dict`: `signal_state` 값 검증 추가
- `live/src/live/daily_runner.py`:
  - `_build_signal_detections`: 기본 `state_str = "none"`
  - `_build_asset_states`: 매핑 로직 업데이트 + `"none" + shares>0` 방어벽
- `live/src/live/notifier.py` — 본문 빌더는 `"buy"/"sell"` 만 필터하므로 로직 변경 불필요. 타입 힌트만 `SignalStateLiteral` 로 명확화 가능
- `live/src/live/rtdb_gateway.py` — signals payload 구조 유지, `"none"` 이 그대로 직렬화됨
- `live/src/live/chart_data.py` — signal_history 로딩은 `"buy"/"sell"` 만 인덱스화하므로 로직 변경 없음
- `live/src/live/history.py` — `append_signal_history` 는 문자열 저장만 하므로 변경 없음. 과거 `"hold"` 값이 signals.jsonl 에 남아있다면 차트 빌더가 이미 무시하므로 호환성 이슈 없음
- `docs/DESIGN_QBT_LIVE_FINAL.md` — signal_state 값 집합 / SCHEMA_VERSION 정책 업데이트
- `live/tests/` — 관련 계약 테스트 업데이트
- `README.md`: **변경 없음**

### 데이터/결과 영향

- LiveState JSON `schema_version` 이 2 로 bump — **기존 v1 파일 로드 불가** (사용자가 `init` 재실행 또는 수동 변환 필요)
- RTDB `/latest/signals` 의 각 자산 `state` 필드가 `"hold"` 대신 `"none"` 으로 직렬화될 수 있음 (단, 현재 `_build_signal_detections` 는 intent 매칭 시 `"buy"/"sell"` 만 세팅하고 나머지는 `"none"` 이므로 실제로는 동일 의미)
- history/signals.jsonl 의 과거 `"hold"` 레코드는 `chart_data.build_chart_series` 가 `"buy"/"sell"` 만 필터하므로 무시되어 호환성 유지
- 기존 qbt-live-state 데이터는 사용자가 재초기화해야 함 — 본 Plan 에서는 마이그레이션 스크립트 제공하지 않음

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/계약 테스트 먼저 작성 (레드 허용)

**작업 내용**:

- [x] `live/tests/test_models.py` 또는 신규 `test_signal_state_literal.py` 에 다음 테스트 추가:
  - [x] `SignalStateLiteral` 허용 값 집합이 `{"buy", "sell", "none"}` 인지
  - [x] `AssetLiveState(signal_state="none")` 로 생성 가능
  - [x] `SignalDetection(state="none", ...)` 로 생성 가능
- [x] `live/tests/test_daily_runner.py` 에 다음 추가:
  - [x] `_build_asset_states` 가 `signal_state="none"` + `model_shares=0` 이면 QBT `signal_state="sell"` 로 매핑
  - [x] `_build_asset_states` 가 `signal_state="none"` + `model_shares=10` 이면 `RuntimeError("내부 불변조건 위반")` (match="내부 불변조건")
- [x] `live/tests/test_state.py` 에 다음 추가:
  - [x] `create_initial_state(capital=...)` 결과의 각 자산 `signal_state == "none"`
  - [x] v1 `schema_version` JSON 을 `load_state` 하면 ValueError (기존 검증 로직 확인용)
  - [x] `signal_state="hold"` 값이 섞인 JSON 을 load 하면 ValueError
- [x] 테스트는 이 Phase 에서 실행하지 않음 (Phase 1 이후 그린 유지)

---

### Phase 1 — 타입/초기값/매핑 구현 (그린 유지)

**작업 내용**:

- [x] `live/src/live/models.py`:
  - [x] `SignalStateLiteral = Literal["buy", "sell", "none"]` 정의
  - [x] `VALID_SIGNAL_STATES: frozenset[str] = frozenset(get_args(SignalStateLiteral))` 파생
  - [x] `AssetLiveState.signal_state: SignalStateLiteral` (str → 좁히기)
  - [x] `SignalDetection.state: SignalStateLiteral` (기존 `Literal["buy", "sell", "hold"]` → 교체)
  - [x] `__all__` 에 `SignalStateLiteral`, `VALID_SIGNAL_STATES` 추가
- [x] `live/src/live/constants.py`:
  - [x] `SCHEMA_VERSION: Final[int] = 2` 로 bump, 주석에 "v1 → v2: signal_state 값 집합을 {buy,sell,hold} → {buy,sell,none} 으로 변경" 한 줄 추가
- [x] `live/src/live/state.py`:
  - [x] `create_initial_state`: `AssetLiveState(..., signal_state="none", ...)` 로 초기화
  - [x] `_asset_live_state_from_dict`: `signal_state_raw = data["signal_state"]` 를 `VALID_SIGNAL_STATES` 와 비교하여 유효하지 않으면 `ValueError("signal_state 값이 유효하지 않음: ...")`. 유효하면 `cast("SignalStateLiteral", ...)`
- [x] `live/src/live/daily_runner.py`:
  - [x] `_build_signal_detections`: `state_str: SignalStateLiteral = "none"`
  - [x] `_build_asset_states`:
    ```python
    for asset_id, asset in state.assets.items():
        if asset.signal_state == "buy":
            qbt_state = "buy"
        elif asset.signal_state in ("sell", "none"):
            qbt_state = "sell"
        else:
            raise RuntimeError(
                f"내부 불변조건 위반: 알 수 없는 signal_state={asset.signal_state!r} asset_id={asset_id}"
            )
        if asset.signal_state == "none" and asset.model_shares > 0:
            raise RuntimeError(
                f"내부 불변조건 위반: signal_state='none' 인데 model_shares={asset.model_shares}>0 asset_id={asset_id}"
            )
        out[asset_id] = AssetState(position=asset.model_shares, signal_state=qbt_state)
    ```

---

### Phase 2 — 테스트 업데이트 (그린 유지)

**작업 내용**:

- [x] live 테스트 전수에서 기존 `signal_state="hold"` / `state="hold"` 문자열을 `"none"` 으로 치환. 대상 후보:
  - `live/tests/test_state.py` — `create_initial_state` 결과 비교, 수동 JSON 로드 fixtures
  - `live/tests/test_daily_runner.py` — initial state 생성, pending 없는 날 시나리오
  - `live/tests/test_drift.py` — pending 없음 fill 케이스
  - `live/tests/test_balance_adjust.py` — initial state
  - `live/tests/test_chart_data.py` — signal_history fixture
  - `live/tests/test_cli.py` — JSON fixture
  - `live/tests/test_models.py` — `SignalDetection` / `AssetLiveState` 생성
  - `live/tests/test_notifier.py` — SignalDetection fixture
  - `live/tests/test_rtdb_gateway.py` — payload assertion
  - `live/tests/test_regression.py` — 필요 시 `schema_version` 기대값 조정
- [x] Phase 0 에서 추가한 테스트를 확인하여 그린 통과
- [x] 스키마 버전 변경으로 회귀 테스트 fixture JSON 이 `"schema_version": 2` 로 갱신되어야 하는 곳 확인

---

### Phase 3 — 설계서 / 도메인 문서 반영 (그린 유지)

**작업 내용**:

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md`:
  - [x] 상태 원장 / `LiveState` 관련 섹션에 `signal_state ∈ {"buy", "sell", "none"}` 명시
  - [x] `"none"` 의 의미를 "해당 자산에 대해 매수/매도 시그널이 한 번도 발생하지 않은 초기 상태 또는 당일 신호 없음" 으로 기술
  - [x] `SCHEMA_VERSION` 정책 한 문단 추가: "포맷 변경 시 `live.constants.SCHEMA_VERSION` 을 bump 한다. 기존 버전 파일은 `load_state` 가 ValueError 로 즉시 실패한다. 마이그레이션은 `init` 재실행 또는 수동 변환"
  - [x] `SignalDetection.state` 의 `"hold"` 가 사라졌음을 한 줄 기술 (`"오늘 신호 없음" = "none"`)
  - [x] QBT `BufferZoneStrategy._hold_state` (내부 hold_days 상태머신) 는 live 의 `signal_state` 와 무관한 개념임을 명시해 이름 충돌 해소를 설명
- [x] `live/CLAUDE.md`: 핵심 원칙 섹션에 "signal_state 값 집합은 `{buy, sell, none}` 이며 QBT 의 `_hold_state` 와 이름이 같은 개념이 아니다" 한 줄 추가

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=874, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / signal_state 값 집합 {buy,sell,none} 통일 + SCHEMA_VERSION bump
2. live / SignalStateLiteral 도입 및 "hold"→"none" 리네임 (QBT 하위 호환)
3. live / 상태 원장 의미 명확화 — none 으로 신호 없음 표현, 설계서 반영
4. live / SignalDetection / AssetLiveState 타입 좁히기 + 방어벽 추가
5. live / "hold" 이름 충돌 해소 + SCHEMA_VERSION v2 + 계약 테스트 보강

## 7) 리스크(Risks)

- **v1 → v2 스키마 변경**: 사용자의 기존 `qbt-live-state` 리포에 있는 `live_state.json` 이 v1 상태라면 `load_state` 가 ValueError 를 던져 다음 `run-daily` 가 실패함. 완화책: 본 Plan 머지 후 사용자가 `init` 재실행 또는 JSON 수동 편집 (`schema_version: 2` + 모든 `signal_state: "hold"` → `"none"`)
- `SignalDetection.state` 타입 변경이 `notifier._build_daily_body` 의 `if sig.state in ("buy", "sell")` 필터와 호환되는지 재검증 필요 (이미 호환되지만 테스트로 고정)
- `_build_asset_states` 의 방어벽 추가가 기존 통합 테스트(`test_daily_runner.py`) 에 예상치 못한 회귀를 유발할 가능성 → Phase 0 에서 정상 경로 테스트도 포함해 커버
- 회귀 테스트(`test_regression.py`) 가 signal_state 를 직접 비교하지 않는다면 영향 없음, 비교한다면 `"none"` 으로 갱신 필요

## 8) 메모(Notes)

- 본 Plan 은 **데이터 스키마 변경**이 포함되므로 PLAN_live_base_cleanup 완료 후 단독 commit 단위로 처리한다
- `_build_asset_states` 의 방어벽은 PLAN_live_failfast_policy 의 fallback 제거 정책과 일관성이 있으나, 본 Plan 의 방어벽은 "signal_state 의 의미 불변조건" 에 한정됨

### 진행 로그 (KST)

- 2026-04-12 09:00: 계획서 초안 작성

---
