# Implementation Plan: ChartSeries.ema_200 → ma_value 리네임 및 밴드 값 전략 내부 상태 기반화

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

- [x] `ChartSeries.ema_200`, `SignalDetection.ema_200`, `ema_distance_pct` 의 "200일 고정" 느낌을 제거하고 `ma_value`, `ma_distance_pct` 로 일반화
- [x] `ChartSeries` 필드명을 `ma_value / upper_band / lower_band` (기존 `ema_200`) 로 리네임하여 `slot.ma_window` 에 독립적이 되도록 함
- [x] 알림 본문의 `"200일선 근접도"` 문구를 `"이동평균(MA{N}) 근접도"` 또는 `"MA 근접도"` 로 일반화
- [x] `daily_runner._build_signal_detections` 에서 버퍼존 밴드값을 **즉시 계산(`ema * (1 ± buffer_pct)`)** 하는 대신 `BufferZoneStrategy._prev_upper / _prev_lower` 를 조회하여 실제 전략이 판단에 사용한 값을 사용
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 의 차트 / 알림 섹션을 업데이트 (`ema_200` → `ma_value`, "200 일선 근접도" → MA N 근접도)

## 2) 비목표(Non-Goals)

- RTDB `/latest/chart_data/{asset_id}` 스키마의 외부 호환성 유지 불필요 (앱 미구현)
- `ChartSeries.ema_200` 필드명 유지 및 주석만 업데이트하는 소극적 대안 (B안 채택)
- QBT 본체 수정 없음
- signal_state 값 집합 변경 (PLAN_live_signal_state_none)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- [live/src/live/models.py:259](../../live/src/live/models.py#L259) 의 `ChartSeries.ema_200` 필드명은 `slot.ma_window == 200` 을 가정. 전략 파라미터가 바뀌거나 다른 ma_window 자산이 추가되면 의미 왜곡
- [live/src/live/chart_data.py:91](../../live/src/live/chart_data.py#L91) 는 `f"ma_{slot.ma_window}"` 로 동적 컬럼명을 계산하므로 코드는 이미 일반화되어 있음 → 필드명만 맞춰주면 됨
- [live/src/live/notifier.py:83](../../live/src/live/notifier.py#L83) 의 `"200일선 근접도: ..."` 문구도 마찬가지
- [live/src/live/daily_runner.py:179-181](../../live/src/live/daily_runner.py#L179-L181) 는 `upper_band = ema * (1.0 + slot.buy_buffer_zone_pct)`, `lower_band = ema * (1.0 - slot.sell_buffer_zone_pct)` 로 **당일 종가 기준 밴드** 를 즉시 계산
- 그러나 `BufferZoneStrategy` 의 매수/매도 판단은 `_prev_upper / _prev_lower` (전일 값) 기준으로 이뤄지며, `_update_bands` 호출 이후 `prev` 가 **당일 값으로 갱신**되어 버퍼존 전략의 "현재 상태" 와 일치
- 즉 `BufferZoneStrategy._prev_upper / _prev_lower` 를 읽으면 "전략이 다음 거래일에 판단 기준으로 쓰는 밴드값" 을 정확히 얻을 수 있음
- 현재 구현은 이와 유사하지만 독립적으로 재계산하므로, 전략 내부 상태와 **의미가 같은지 보장되지 않음** (예: `_update_bands` 가 아직 호출되지 않은 초기 상태에서는 값이 다를 수 있음)
- 앱이 아직 구현되지 않은 시점이므로 RTDB 스키마 리네임 비용이 낮음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

## 4) 완료 조건(Definition of Done)

- [x] `ChartSeries` 필드: `ema_200: list[float | None]` → `ma_value: list[float | None]`
- [x] `SignalDetection` 필드: `ema_200: float | None` → `ma_value: float | None`, `ema_distance_pct: float` → `ma_distance_pct: float`
- [x] `chart_data.build_chart_series` 내부 변수/주석 업데이트 (`ema_list` → `ma_list`, 관련 docstring 의 "EMA 200" 표현 제거)
- [x] `daily_runner._build_signal_detections` 가 `BufferZoneStrategy._prev_upper / _prev_lower` 를 조회하여 `SignalDetection.upper_band / lower_band` 를 채운다. 전략이 BufferZoneStrategy 가 아니거나 prev 값이 `None` 인 경우 `upper_band / lower_band` 는 `None` 으로 설정
- [x] `daily_runner._build_signal_detections` 가 `ma_value` 와 `ma_distance_pct` 를 `(close - ma_value) / ma_value` 로 계산 (ma_value > 0 일 때만)
- [x] `DailyResult.ema_distances` → `DailyResult.ma_distances` 로 리네임
- [x] `notifier._build_daily_body` 의 `"200일선 근접도"` → `"MA 근접도"` (실제 ma_window 수치는 표시하지 않음 — slot 마다 다를 수 있으므로)
- [x] `rtdb_gateway.write_read_model` 의 `/latest/signals` payload 에서 `"ema_200"` 키를 `"ma_value"` 로, `"ema_distance_pct"` 를 `"ma_distance_pct"` 로 변경
- [x] `history._persist_history` 의 `daily_payload["ema_distances"]` → `"ma_distances"` 로 키 이름 변경 (jsonl 과거 레코드는 그대로 유지 — 읽기 루틴이 이 키를 쓰지 않음)
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 의 7장(차트) / 8장(알림) 업데이트
- [x] `daily_runner._build_signal_detections` 에 `BufferZoneStrategy._prev_upper/_prev_lower` 를 private 접근 대신 어댑터 형태로 읽는 헬퍼 추가 (`buffer_serializer.get_current_bands(strategy) -> tuple[float|None, float|None]`)
- [x] 회귀/신규 테스트 추가 (밴드값이 strategy 내부 상태와 일치하는지 계약 고정)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/models.py` — `ChartSeries` / `SignalDetection` / `DailyResult` 필드 리네임
- `live/src/live/chart_data.py` — 변수명, docstring, 컬럼 접근 업데이트
- `live/src/live/daily_runner.py` — `_build_signal_detections` 구현 변경, `ma_distances` 채움
- `live/src/live/buffer_serializer.py` — `get_current_bands(strategy)` 헬퍼 추가 (private 속성을 getattr 로 읽는 어댑터)
- `live/src/live/notifier.py` — 본문 문구 업데이트
- `live/src/live/rtdb_gateway.py` — payload 키 이름 업데이트
- `live/src/live/cli.py` — `_persist_history` 호출부에서 `ma_distances` 키 사용
- `live/src/live/history.py` — 해당 키 이름 업데이트 (docstring 만)
- `docs/DESIGN_QBT_LIVE_FINAL.md` — 7장 / 8장 업데이트
- `live/tests/` — 필드명 변경 반영
- `README.md`: **변경 없음**

### 데이터/결과 영향

- RTDB `/latest/signals` payload 키 변경 (`ema_200` → `ma_value`, `ema_distance_pct` → `ma_distance_pct`) — 앱 미구현이라 외부 영향 없음
- RTDB `/latest/chart_data/{asset_id}` payload 키 변경 (`ema_200` → `ma_value`) — 앱 미구현이라 외부 영향 없음
- history/daily/*.json 파일의 `ema_distances` 키가 `ma_distances` 로 변경 — 과거 레코드는 그대로 유지, 새 레코드만 신규 키 사용
- 알림 본문 문구 변경 (`"200일선 근접도"` → `"MA 근접도"`)

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 먼저 작성 (레드 허용)

**작업 내용**:

- [x] `live/tests/test_daily_runner.py` 에 다음 계약 테스트 추가:
  - [x] `_build_signal_detections` 가 반환하는 `SignalDetection.upper_band / lower_band` 가 `BufferZoneStrategy._prev_upper / _prev_lower` 와 정확히 일치 (strategy 인스턴스를 생성하고 `_update_bands` 를 수동 호출한 상태에서 비교)
  - [x] BuyAndHoldStrategy 자산은 `upper_band / lower_band` 가 `None`
  - [x] ma_window=200 이 아닌 슬롯을 실험 config 로 가정한 mock 시나리오에서 `ma_value` 필드가 올바르게 채워지고 `ma_distance_pct = (close - ma_value) / ma_value`
- [x] `live/tests/test_chart_data.py` 에 필드명이 `ma_value` 로 변경되었는지 검증
- [x] `live/tests/test_notifier.py` 에 본문 문구가 `"MA 근접도"` 포함하도록 업데이트 (기존 `"200일선 근접도"` 기대 제거)
- [x] `live/tests/test_buffer_serializer.py` 에 `get_current_bands(strategy)` 헬퍼 계약 추가 (초기 상태 None, _update_bands 호출 후 실제 값)

---

### Phase 1 — 모델/어댑터/계산 로직 구현 (그린 유지)

**작업 내용**:

- [x] `live/src/live/models.py`:
  - [x] `ChartSeries.ema_200` → `ma_value`
  - [x] `SignalDetection`: `ema_200` → `ma_value`, `ema_distance_pct` → `ma_distance_pct`, docstring 내 "200일선" 표현 일반화
  - [x] `DailyResult.ema_distances` → `ma_distances`
- [x] `live/src/live/buffer_serializer.py`:
  - [x] `get_current_bands(strategy: BufferZoneStrategy) -> tuple[float | None, float | None]` 헬퍼 추가 (docstring 에 `_prev_upper` 가 `_update_bands` 호출 직후 "당일 값" 이라는 점 명시)
  - [x] `__all__` 에 추가
- [x] `live/src/live/chart_data.py`:
  - [x] 내부 변수명/주석의 `ema` → `ma`
  - [x] `raw_ema` → `raw_ma`, `ema_list` → `ma_list`
  - [x] docstring 의 "EMA-200" / "200 일" 표현 제거
- [x] `live/src/live/daily_runner.py` `_build_signal_detections`:
  - [x] `ma_value` 계산: 기존 `ema_200` 로직 그대로이되 변수명만 변경
  - [x] `upper_band / lower_band`: `isinstance(strategy, BufferZoneStrategy)` 일 때 `get_current_bands(strategy)` 호출 결과 사용. 그 외는 `None`
  - [x] `ma_distance_pct = (close - ma_value) / ma_value if ma_value and ma_value > 0 else 0.0`
  - [x] `ma_distances: dict[str, float]` 반환 (기존 `ema_distances` 변수명 변경)
- [x] `live/src/live/notifier.py`:
  - [x] `_build_daily_body`: `"200일선 근접도"` → `"MA 근접도"` 로 변경
  - [x] `result.ma_distances` 참조
- [x] `live/src/live/rtdb_gateway.py` `write_read_model`:
  - [x] signals payload 의 `"ema_200"` → `"ma_value"`, `"ema_distance_pct"` → `"ma_distance_pct"`
- [x] `live/src/live/cli.py` `_persist_history`:
  - [x] `daily_payload["ema_distances"]` → `daily_payload["ma_distances"]`
- [x] `live/src/live/history.py`: 변경 없음. docstring 의 관련 표현만 한 번 훑어 정리

---

### Phase 2 — 테스트 업데이트 + 설계서 반영 (그린 유지)

**작업 내용**:

- [x] Phase 0 에서 작성한 계약 테스트가 그린 통과하는지 확인
- [x] 기존 테스트의 `ema_200` / `ema_distance_pct` / `ema_distances` / `"200일선"` 참조를 새 이름으로 일괄 교체
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md`:
  - [x] 7장(차트): `dates, close, ema_200, upper_band, lower_band` → `dates, close, ma_value, upper_band, lower_band`. "EMA-200 의 앞 199 개 인덱스" 문구를 "MA 의 워밍업 구간 (slot.ma_window - 1 개 인덱스)" 으로 일반화
  - [x] 8장(알림): `"200일선 근접도"` 표현을 "MA 근접도 ((close − ma_value) / ma_value, 비율)" 로 변경. `SignalDetection.ma_distance_pct` 필드 언급
  - [x] 필요 시 `ChartSeries` 구조 설명 업데이트

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=876, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / ChartSeries/SignalDetection 필드 리네임 (ema_200 → ma_value) + MA 근접도 일반화
2. live / 밴드값을 BufferZoneStrategy 내부 상태 기반으로 전환 + ma_value 리네임
3. live / 알림/차트 용어 일반화 (200일선 표현 제거) + buffer_serializer 어댑터 확장
4. live / ma_window 독립 필드명 정리 + daily_runner 계약 강화
5. live / 차트/시그널 일반화 + 설계서 반영

## 7) 리스크(Risks)

- `BufferZoneStrategy._prev_upper / _prev_lower` 는 `_update_bands` 호출 시점에 "직전 값 → 당일 값" 으로 갱신된다. 이 시점의 값을 `SignalDetection.upper_band / lower_band` 로 노출해도 의미가 맞는지 이중 확인 필요 (`daily_runner` 는 `generate_signal_intents` → `_build_signal_detections` 순서로 호출하며, signal intents 생성 내부에서 `check_buy/check_sell` 이 호출되고 `_update_bands` 가 실행되므로 `_prev_*` 는 "당일 값" 이 담긴 상태)
- `buffer_serializer.get_current_bands` 가 private 속성(`_prev_upper` 등) 을 getattr 로 읽는 것은 기존 `extract_buffer_state` 와 동일한 어댑터 패턴이라 QBT 본체 수정 없이 가능
- payload 키 변경은 RTDB 역사 레코드와 호환되지 않을 수 있으나 앱 미구현이라 실질 영향 없음
- `history/daily/*.json` 의 기존 `ema_distances` 키는 과거 레코드에 남아있지만 읽기 코드가 이 키를 참조하지 않으므로 호환 문제 없음

## 8) 메모(Notes)

- 본 Plan 은 PLAN_live_base_cleanup, PLAN_live_signal_state_none 완료 이후 순서로 진행한다
- `ma_window != 200` 자산이 포트폴리오에 추가되는 시나리오를 선제 대응하는 목적

### 진행 로그 (KST)

- 2026-04-12 09:00: 계획서 초안 작성

---
