# Implementation Plan: 미입력 체결 리마인더 지속성 + fill_dismiss 경로

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🔄 In Progress

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-16 18:00
**마지막 업데이트**: 2026-04-16 18:00
**관련 범위**: live (daily_runner, models, rtdb_gateway, cli, state, notifier)
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan 은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] 미입력 체결 리마인더를 **fill 입력 또는 스킵 전까지 매일 반복** 표출
- [ ] `AssetLiveState` 에 `unfilled_order_date: str | None` 필드 추가
- [ ] RTDB `/fill_dismiss/inbox/{uuid}` 신규 경로 + `FillDismiss` 모델 추가
- [ ] `applied_fill_dismiss_ids` idempotency 원장 추가
- [ ] 리마인더 해제 경로 2 가지: (A) fill 입력, (B) 앱에서 스킵 (fill_dismiss)
- [ ] balance_adjust 는 리마인더를 해제하지 않음 (관심사 분리)

## 2) 비목표(Non-Goals)

- 앱 (Android / React Native) 측 구현 — 앱 미개발 상태
- `pending_order` 생명주기 변경 — 기존 model 축 동작 유지
- drift 계산 / equity 공식 변경
- 기존 fill / balance_adjust idempotency 구조 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `pending_order` 는 model 축 개념이며, model 이 체결을 실행하면 매일 `None` 으로 소멸
- 리마인더가 `pending_order is not None` 에 의존 → 시그널 다음날 1 회만 표출
- fill 을 입력하지 않아도 2 일째부터 리마인더가 사라져 사용자가 미입력 사실을 잊을 수 있음
- 사용자 요구: "fill 입력 전까지 매일 반복 알림이 필요해"
- 추가 요구: "스킵 버튼으로 리마인더를 명시적으로 중지할 수 있어야 함"

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지** 하고 준수합니다.

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- 루트 [CLAUDE.md](../../CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)

## 4) 완료 조건(Definition of Done)

- [ ] `AssetLiveState.unfilled_order_date` 필드 추가 + state 직렬화 호환
- [ ] `FillDismiss` dataclass + `_dict_to_fill_dismiss` 파서 구현
- [ ] `rtdb_gateway`: `/fill_dismiss/inbox/` fetch + mark_processed 구현
- [ ] `daily_runner.run_daily`: unfilled_order_date set/clear 로직 구현
- [ ] `cli.py`: fill_dismiss fetch + history append + applied_ids 관리
- [ ] `state.py`: `applied_fill_dismiss_ids` load/save 함수 추가
- [ ] 테스트 추가 (최소 시나리오 목록은 Phase 0 참고)
- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md` §8.2.x 신규 경로 추가
- [ ] `src/live/CLAUDE.md` 갱신
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] plan 체크박스 최신화 완료

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/models.py` — `AssetLiveState` 필드 추가, `FillDismiss` 신규, `DailyResult` 확장
- `src/live/daily_runner.py` — 리마인더 계산 로직 재작성 (unfilled_order_date 기반)
- `src/live/rtdb_gateway.py` — `/fill_dismiss/inbox/` fetch/mark
- `src/live/state.py` — `applied_fill_dismiss_ids` load/save, `create_initial_state` 갱신
- `src/live/cli.py` — fill_dismiss fetch + history + applied_ids 관리
- `src/live/history.py` — `append_fill_dismiss` 함수 추가
- `src/live/balance_adjust.py` — **변경 없음** (리마인더와 무관)
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §8.2.x 신규
- `src/live/CLAUDE.md` — 모듈 표 / 핵심 원칙 갱신
- `tests/live/test_daily_runner.py` — 리마인더 지속성 시나리오
- `tests/live/test_rtdb_gateway.py` — fill_dismiss 파싱 테스트
- `tests/live/test_models.py` — AssetLiveState / FillDismiss 필드 테스트
- `tests/live/test_state.py` — applied_fill_dismiss_ids 직렬화
- `README.md`: **변경 없음**

### 데이터/결과 영향

- `AssetLiveState` 스키마 확장: `unfilled_order_date` 필드 추가 (기존 JSON 에 없으면 `None` 으로 역직렬화 — 하위 호환)
- RTDB 신규 경로: `/fill_dismiss/inbox/{uuid}`
- `qbt-live-state` 에 `applied_fill_dismiss_ids.json` 파일 추가
- `history/fill_dismisses.jsonl` 파일 추가

## 6) 단계별 계획(Phases)

### Phase 0 — 정책 테스트 먼저 고정 (레드)

**작업 내용**:

- [ ] `tests/live/test_daily_runner.py` 리마인더 지속성 시나리오 추가
  - [ ] [T-REM.1] 시그널 → model 체결 → fill 미입력 → `unfilled_order_date` set + 리마인더 표출
  - [ ] [T-REM.2] 다음날 실행 → fill 여전히 미입력 → `unfilled_order_date` 유지 + 리마인더 반복
  - [ ] [T-REM.3] fill 입력 → `unfilled_order_date = None` → 리마인더 해제
  - [ ] [T-REM.4] fill_dismiss 입력 → `unfilled_order_date = None` → 리마인더 해제, 잔고 불변
  - [ ] [T-REM.5] balance_adjust → `unfilled_order_date` 유지 (리마인더 해제 안 됨)
  - [ ] [T-REM.6] 시그널 없음 (pending_order 미생성) → `unfilled_order_date` 변화 없음
- [ ] `tests/live/test_rtdb_gateway.py` fill_dismiss 파싱 테스트
  - [ ] [T-REM.7] 유효한 fill_dismiss dict → `FillDismiss` 변환 성공
  - [ ] [T-REM.8] asset_id 누락 → `ValueError`
- [ ] `tests/live/test_models.py` 필드 테스트
  - [ ] [T-REM.9] `AssetLiveState` 에 `unfilled_order_date` 필드 존재 확인
  - [ ] [T-REM.10] `FillDismiss` 필드 집합 확인

**Validation**: 레드 허용.

---

### Phase 1 — 코어 구현 (그린 유지)

**작업 내용**:

- [ ] `src/live/models.py`
  - [ ] `AssetLiveState` 에 `unfilled_order_date: str | None` 필드 추가 (default `None`, 전략 상태 블록 아래)
  - [ ] `FillDismiss` dataclass 신규 (rtdb_key, input_time_kst, reason, asset_id)
  - [ ] `DailyResult` 에 `updated_applied_fill_dismiss_ids: dict[str, str]` 필드 추가
  - [ ] `__all__` 갱신
- [ ] `src/live/state.py`
  - [ ] `create_initial_state` 에 `unfilled_order_date=None` 추가
  - [ ] `load_state` / `save_state` 에서 `unfilled_order_date` 역/직렬화 (없으면 `None` — 하위 호환)
  - [ ] `load_applied_fill_dismiss_ids` / `save_applied_fill_dismiss_ids` 함수 추가 (fill_ids 와 동일 패턴)
  - [ ] `__all__` 갱신
- [ ] `src/live/rtdb_gateway.py`
  - [ ] `_dict_to_fill_dismiss` 파서 (asset_id 필수, 없으면 `ValueError`)
  - [ ] `fetch_pending_fill_dismisses` 함수 (fetch_unprocessed_fills 와 동일 패턴)
  - [ ] `mark_fill_dismisses_processed` 함수
- [ ] `src/live/daily_runner.py` — `run_daily` 리마인더 로직 재작성
  - [ ] 시그니처에 `pending_dismisses: list[FillDismiss] | None`, `applied_fill_dismiss_ids: dict[str, str] | None` 추가
  - [ ] 단계 3 재작성:
    1. fill 도착한 자산 → `unfilled_order_date = None`
    2. fill_dismiss 도착한 자산 → `unfilled_order_date = None` (잔고 불변)
    3. `pending_order is not None` 이고 fill/dismiss 미도착 → `unfilled_order_date = trade_date` (신규 감지)
    4. 리마인더 목록 = `unfilled_order_date is not None` 인 모든 자산
  - [ ] fill_dismiss idempotency 처리 (`applied_fill_dismiss_ids`)
  - [ ] `DailyResult` 에 `updated_applied_fill_dismiss_ids` 포함

**Validation**:

- [ ] Phase 0 레드 테스트가 그린으로 전환되는지 `pytest tests/live/test_daily_runner.py tests/live/test_rtdb_gateway.py tests/live/test_models.py` 확인

---

### Phase 2 — CLI + history + 문서 (그린 유지)

**작업 내용**:

- [ ] `src/live/history.py` — `append_fill_dismiss` 함수 추가 (audit 용 JSONL append)
- [ ] `src/live/cli.py`
  - [ ] `_cmd_run_daily` 에서 `fetch_pending_fill_dismisses` 호출
  - [ ] `applied_fill_dismiss_ids` load/save 추가
  - [ ] 신규 적용된 dismiss 에 대해 `history.append_fill_dismiss` + `mark_fill_dismisses_processed`
  - [ ] `run_daily` 호출 시 `pending_dismisses`, `applied_fill_dismiss_ids` 인자 전달
- [ ] `docs/DESIGN_QBT_LIVE_FINAL.md`
  - [ ] §8.2.x `/fill_dismiss/inbox/{uuid}` 신규 섹션 (필드 표 + 예시 + 핵심 제약)
  - [ ] §6.2 리마인더 설명에 "fill 입력 또는 스킵 전까지 매일 반복" 문구 추가
- [ ] `src/live/CLAUDE.md`
  - [ ] 모듈 표에 fill_dismiss 관련 설명 보강
  - [ ] 핵심 원칙 1 예외 목록에 "fill_dismiss 필수 필드 누락" 추가

---

### Phase 3 — 마지막 Phase: 최종 검증 및 포맷 적용

**작업 내용**:

- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 미입력 체결 리마인더를 fill 입력 또는 스킵 전까지 매일 반복 표출
2. live / unfilled_order_date 필드 + fill_dismiss 경로 추가로 리마인더 지속성 구현
3. live / 체결 미입력 알림 지속성 + /fill_dismiss/inbox/ 신규 RTDB 경로 추가
4. live / fill 미입력 시 리마인더 매일 반복 + 앱 스킵 경로(fill_dismiss) 구현
5. live / 리마인더 1회 → 매일 반복으로 변경 + FillDismiss 모델 및 idempotency 추가

## 7) 리스크(Risks)

- **AssetLiveState 스키마 확장**: `unfilled_order_date` 가 기존 JSON 에 없으면 `None` 으로 역직렬화. `state.py` 의 `load_state` 에서 `.get("unfilled_order_date")` 로 처리하면 하위 호환 보장.
- **회귀 테스트 (`test_regression.py`)**: `run_daily` 시그니처 변경 (새 파라미터 추가) 이 regression 호출부에 영향을 줄 수 있음. 기본값 `None` 으로 하위 호환.
- **applied_fill_dismiss_ids 파일 부재**: 최초 실행 시 파일이 없을 수 있으므로 `FileNotFoundError` → `{}` 로 초기화 (기존 fill_ids 와 동일 패턴).

## 8) 메모(Notes)

### 설계 결정 근거

- **balance_adjust 는 리마인더를 해제하지 않음**: 사용자 확정. balance_adjust 는 "잔고 교체" 목적, 리마인더는 "체결 입력 독촉" 목적으로 관심사가 분리됨.
- **fill_dismiss 는 잔고를 건드리지 않음**: dismiss 는 "이 체결은 안 할래" 라는 명시적 의사 표현이며, actual_shares / actual_avg_entry_price 등 일체 변경 없음.
- **unfilled_order_date 는 model 체결 시점 기록**: pending_order 가 model 에 의해 소비되었는데 fill 이 미도착한 날짜를 기록. 이후 리마인더에 "N 일째 미입력" 표시 확장 가능.

### 진행 로그 (KST)

- 2026-04-16 18:00: plan 작성

---
