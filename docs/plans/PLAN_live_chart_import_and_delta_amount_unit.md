# Implementation Plan: live 소규모 정리 — chart_data 런타임 import 제거 + delta_amount 단위 주석

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

**작성일**: 2026-04-14 00:00
**마지막 업데이트**: 2026-04-14 00:00
**관련 범위**: live
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: [src/live/chart_data.py](../../src/live/chart_data.py) 에서 이유 없는 함수 내부 runtime import (`from live.constants import CHART_RECENT_MONTHS`) 를 제거하고 top-level import 로 이동한다.
- [x] 목표 2: [src/live/models.py](../../src/live/models.py) `PendingOrderDict.delta_amount` 필드 주석에 단위(금액, 원화)를 명시한다.

## 2) 비목표(Non-Goals)

- QBT 본체 `OrderIntent.delta_amount` 주석 수정은 본 plan의 범위가 아니다 (live 작업 중 QBT 본체 수정 금지 원칙).
- 다른 TypedDict / dataclass 필드 주석 정리는 범위 외.
- `chart_data.py` 의 다른 리팩토링은 범위 외.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **chart_data runtime import**: [src/live/chart_data.py:239](../../src/live/chart_data.py#L239), [src/live/chart_data.py:282](../../src/live/chart_data.py#L282) 에서 `build_chart_meta` / `build_chart_recent` 함수 내부에 `from live.constants import CHART_RECENT_MONTHS` lazy import 가 존재한다. 같은 파일의 top-level ([src/live/chart_data.py:29-33](../../src/live/chart_data.py#L29-L33)) 에서 이미 `live.constants` 의 다른 심볼 (`extract_ticker_from_path`, `get_live_portfolio_config`, `live_csv_path`) 을 import 하고 있으므로 순환 참조 회피 목적이 아니다. 이유 없이 함수 내부로 내려온 import 로 판단되며 **근본 해결 가능**.
- **delta_amount 단위 불명**: [src/live/models.py:81](../../src/live/models.py#L81) `delta_amount: float  # 음수 = 매도, 양수 = 매수` 주석에 방향만 기재되어 있고 단위 (금액 vs 주수) 가 누락되어 있다. 코드 흐름상 QBT 본체 `OrderIntent.delta_amount` 와 동일하게 "금액(원)" 이며 [src/live/daily_runner.py:164](../../src/live/daily_runner.py#L164) 근처의 `_intent_to_pending_order` / `_pending_order_to_intent` 변환 지점에서도 금액으로 사용된다. 후속 유지보수/읽는 사람의 오해 방지를 위해 단위 주석이 필요하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `chart_data.py` 의 함수 내부 `CHART_RECENT_MONTHS` import 2건 제거, top-level 로 이동
- [x] `models.py` `PendingOrderDict.delta_amount` 필드 주석에 단위 명시
- [x] 신규/회귀 테스트 추가 불필요 (동작 불변) — 대신 기존 테스트가 모두 그대로 통과해야 함
- [x] `poetry run python validate_project.py` 통과 (passed=915, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (변경 파일 2건, 포맷 변경 없음)
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/chart_data.py` — runtime import 제거 + top-level import 병합
- `src/live/models.py` — `PendingOrderDict.delta_amount` 주석 단위 보강
- `README.md`: 변경 없음

### 데이터/결과 영향

- 동작/결과 변화 없음 (동일한 값을 동일한 시점에 import 하도록 위치만 변경).
- 주석만 추가되므로 직렬화 스키마 영향 없음.

## 6) 단계별 계획(Phases)

### Phase 1 — 구현 (그린 유지)

**작업 내용**:

- [x] `src/live/chart_data.py` 상단 `from live.constants import (...)` 블록에 `CHART_RECENT_MONTHS` 를 추가
- [x] `src/live/chart_data.py` `build_chart_meta` 함수 내부의 `from live.constants import CHART_RECENT_MONTHS` 제거
- [x] `src/live/chart_data.py` `build_chart_recent` 함수 내부의 `from live.constants import CHART_RECENT_MONTHS` 제거
- [x] `src/live/models.py` `PendingOrderDict.delta_amount` 주석을 `금액(원). 음수 = 매도, 양수 = 매수` 형태로 수정

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` 변경 없음 확인
- [x] `poetry run black .` 실행 (자동 포맷)
- [x] 변경 파일 diff 최종 확인
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=915, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / chart_data 런타임 import 제거 + delta_amount 단위 주석 보강
2. live / chart_data CHART_RECENT_MONTHS 를 top-level import 로 통합
3. live / 함수 내부 lazy import 정리 및 PendingOrder 단위 명시
4. live / import 위치 정리 + models.py delta_amount 단위 주석
5. live / 소규모 코드 정리 (런타임 import 제거 + 주석 보강)

## 7) 리스크(Risks)

- 순환 참조 회피 목적의 lazy import 였을 가능성 → 사전 확인됨 (top-level 에서 이미 동일 모듈 import 중이므로 리스크 없음). `validate_project.py` 의 pytest 가 chart_data import 경로를 실제로 검증해주므로 회귀 감지 가능.
- `delta_amount` 단위는 코드 사용 맥락으로 이미 확정되어 있고 직렬화 포맷 변경이 아니므로 리스크 없음.

## 8) 메모(Notes)

- 본 plan 은 [PLAN_live_iso_silent_skip_alignment.md](PLAN_live_iso_silent_skip_alignment.md) (Plan 2), [PLAN_live_drift_pct_ratio_storage.md](PLAN_live_drift_pct_ratio_storage.md) (Plan 3), [PLAN_qbt_market_regimes_ongoing.md](PLAN_qbt_market_regimes_ongoing.md) (Plan 4) 와 함께 전수 분석 결과로부터 파생된 4 종 계획서 중 첫 번째이다.

### 진행 로그 (KST)

- 2026-04-14 00:00: plan 작성 시작
- 2026-04-14 00:10: Phase 1 구현 완료 (chart_data import 병합 + delta_amount 단위 주석)
- 2026-04-14 00:15: validate_project.py 통과 (915/0/0), plan Done 처리
