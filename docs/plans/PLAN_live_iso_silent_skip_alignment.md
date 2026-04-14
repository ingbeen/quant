# Implementation Plan: live ISO 파싱 silent skip 원칙 정렬

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

**작성일**: 2026-04-14 00:20
**마지막 업데이트**: 2026-04-14 00:20
**관련 범위**: live
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] 목표 1: [src/live/chart_data.py](../../src/live/chart_data.py) `_filter_markers_in_range` 의 ISO 파싱 silent skip 을 소스별 분기로 전환한다 (signal_history → 내부 불변조건 → `RuntimeError`, user_trades → 외부 입력 → `ValueError`).
- [x] 목표 2: [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) `prune_history_summary` 의 ISO 파싱 실패 경로에 WARNING 로그를 추가하여 침해를 기록한다 (skip 동작 자체는 "파손 키 보호" 의도 유지).
- [x] 목표 3: 각 변경을 검증하는 회귀 테스트를 추가한다.

## 2) 비목표(Non-Goals)

- `_filter_markers_in_range` 의 predicate 로직 / 슬라이스 동작 변경은 범위 외.
- `prune_history_summary` 의 retention 기준 / cutoff 계산 변경은 범위 외.
- RTDB 경로 구조, `_HISTORY_SUMMARY_PATH` 위치 변경은 범위 외.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **chart_data silent skip**: [src/live/chart_data.py:152-156](../../src/live/chart_data.py#L152-L156) 의 `_filter_markers_in_range` 는 ISO 파싱 실패 시 `continue` 로 조용히 스킵한다. 입력 소스는 두 가지:
  - `signal_history`: [src/live/history.py](../../src/live/history.py) `append_signal_history` 에서 live 시스템이 내부적으로 생성 → ISO 포맷이 깨지면 **내부 불변조건 위반**
  - `user_trades`: RTDB `UserTrade.date` 에서 앱이 입력 → **외부 입력 검증** 대상
  루트 CLAUDE.md "불가능 값 처리" 원칙상 내부 불변조건 위반은 `RuntimeError`, 외부 입력 유효성은 `ValueError` 로 즉시 실패해야 한다. 현재는 둘 다 silent skip 되어 데이터 파손이 감지되지 않는다.
- **rtdb_gateway prune 의 silent skip**: [src/live/rtdb_gateway.py:306-311](../../src/live/rtdb_gateway.py#L306-L311) `prune_history_summary` 는 ISO 파싱 실패 키를 `continue` 로 스킵하며, docstring 에 "파손 키 보호" 의도가 명시되어 있다. 이 의도는 유지되어야 하지만 침해가 로그로 남지 않아 운영자가 RTDB 파손을 인지하기 어렵다. WARNING 로그를 추가하여 `prune` 은 계속 진행하되 침해 사실만 기록한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `_filter_markers_in_range` 가 signal_history/user_trades 소스 구분에 따라 RuntimeError / ValueError 를 발생시킨다
- [x] `prune_history_summary` 가 파손 키 발견 시 WARNING 로그를 남기고 skip 한다
- [x] 각 동작에 대한 회귀 테스트 추가 ([tests/live/](../../tests/live/))
- [x] `poetry run python validate_project.py` 통과 (passed=918, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/chart_data.py` — `_filter_markers_in_range` 시그니처/로직 수정 (소스 구분)
- `src/live/rtdb_gateway.py` — `prune_history_summary` 에 logger.warning 추가
- `tests/live/test_chart_data.py` (또는 기존 파일) — `_filter_markers_in_range` 파손 입력 테스트
- `tests/live/test_rtdb_gateway.py` (또는 기존 파일) — `prune_history_summary` 파손 키 경고 테스트
- `README.md`: 변경 없음

### 데이터/결과 영향

- 정상 경로 동작 변화 없음.
- 파손 입력이 있을 때만 예외 전파 / WARNING 로그 발생 (정상적으로는 발생하지 않는 경로).

## 6) 단계별 계획(Phases)

### Phase 0 — 레드 테스트 먼저 고정

**작업 내용**:

- [x] `tests/live/` 에 `_filter_markers_in_range` 가 signal_history 파손 시 `RuntimeError("내부 불변조건 위반")` 를 발생시키는 테스트 추가 (레드)
- [x] `tests/live/` 에 `_filter_markers_in_range` 가 user_trades 파손 시 `ValueError` 를 발생시키는 테스트 추가 (레드)
- [x] `tests/live/` 에 `prune_history_summary` 가 파손 키 발견 시 WARNING 로그를 남기고 skip 하는 테스트 추가 (레드, `caplog` 사용)

---

### Phase 1 — 구현 (그린 전환)

**작업 내용**:

- [x] `_filter_markers_in_range` 시그니처에 소스 구분 파라미터 (예: `source_kind: Literal["signal_history", "user_trades"]`) 추가
- [x] 호출부 ([src/live/chart_data.py:187-208](../../src/live/chart_data.py#L187-L208) 내부 `_build_slice`) 에서 각 호출에 적절한 `source_kind` 전달
- [x] 파싱 실패 시 `source_kind` 에 따라 `RuntimeError` / `ValueError` 발생
- [x] `prune_history_summary` 의 `except ValueError` 블록에 `logger.warning(...)` 추가 (키 값 + 파손 사유)
- [x] Phase 0 테스트 통과 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/live/CLAUDE.md` 의 "즉시 실패" 불변조건 리스트에 해당 항목 추가 여부 검토 (추가 시 반영)
- [x] `poetry run black .` 실행
- [x] DoD / Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=918, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / ISO 파싱 silent skip 원칙 정렬 (내부/외부 소스 분기 + prune WARNING)
2. live / chart_data 마커 파손 즉시 실패 + prune_history_summary 침해 로그
3. live / 불가능 값 처리 원칙 재확인 (_filter_markers_in_range + prune)
4. live / 데이터 파손 감지 경로 명시화 (RuntimeError/ValueError/Warning)
5. live / silent skip 제거 및 회귀 테스트 추가

## 7) 리스크(Risks)

- `_filter_markers_in_range` 시그니처 변경으로 호출부 누락 시 정적 분석 실패 — PyRight 가 잡아주므로 리스크 낮음.
- 실제 운영 환경에서 파손 데이터가 존재할 경우 기존에는 조용히 넘어갔지만 이제 RuntimeError 로 전체 차트 빌드가 멈춘다 — 이는 의도된 fail-fast 이며 운영자 인지가 필요한 상태.

## 8) 메모(Notes)

- 본 plan 은 전수 분석 결과 파생 4 종 중 두 번째이다. 선행: [PLAN_live_chart_import_and_delta_amount_unit.md](PLAN_live_chart_import_and_delta_amount_unit.md).

### 진행 로그 (KST)

- 2026-04-14 00:20: plan 작성 시작
- 2026-04-14 00:35: chart_data `_filter_markers_in_range` 소스별 분기 + rtdb_gateway WARNING 로그 구현
- 2026-04-14 00:40: caplog 캡처 실패 → qbt logger propagate=False 대응 (handler 직접 부착)
- 2026-04-14 00:45: validate_project.py 통과 (918/0/0), src/live/CLAUDE.md 즉시 실패 리스트 갱신, plan Done 처리
