# Implementation Plan: BalanceAdjust 에 new_avg_price / new_entry_date 필드 추가

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

**작성일**: 2026-04-16 15:00
**마지막 업데이트**: 2026-04-16 16:30
**관련 범위**: live (balance_adjust, models, rtdb_gateway, history, cli)
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [src/live/balance_adjust.py](../../src/live/balance_adjust.py)
- [src/live/models.py](../../src/live/models.py)
- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §8.2.8
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

- [x] `BalanceAdjust` 에 `new_avg_price: float | None` 필드 추가 (앱이 `actual_avg_entry_price` 를 직접 보정할 수 있게 한다)
- [x] `BalanceAdjust` 에 `new_entry_date: str | None` 필드 추가 (앱이 `actual_entry_date` 를 직접 보정할 수 있게 한다)
- [x] actual 축만 영향을 주며 model 축은 절대 건드리지 않는 `_apply_single_adjust` 분기 구현
- [x] 잘못된 조합 (예: 보유 주수 0 인 자산에 평균가 단독 설정) 을 fail-fast `ValueError` 로 거부
- [x] 설계 문서 §8.2.8 에 신규 필드와 "앱 ↔ live 입력 검증 2 단계 역할 분담" 섹션 반영
- [x] 회귀 테스트 및 신규 계약 테스트 추가

## 2) 비목표(Non-Goals)

- `ActualFill` 모델 변경 — fill 은 이벤트 기반이므로 이번 plan 범위 밖
- `run_daily` 실행 순서 변경 (fills → balance_adjust → drift 유지)
- `drift.compute_drift` 공식 변경 (equity = cash + Σ(shares × close) 유지)
- `applied_balance_adjust_ids` idempotency 구조 변경
- `AssetLiveState` 스키마 변경 (`actual_avg_entry_price`, `actual_entry_date` 는 이미 존재)
- model 축 (`model_*` 필드) 변경 — balance_adjust 는 actual 축만 다룬다
- 앱 (Android / React Native) 측 구현 — 앱은 아직 개발 전이며 본 plan 은 live 서버 + 설계서만 다룬다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `BalanceAdjust` 는 `new_shares` 와 `new_cash` 만 지원한다. 사용자는 앱에서 평균단가(`actual_avg_entry_price`) 와 진입일(`actual_entry_date`) 을 직접 수정할 수 없다.
- 평균가가 잘못 기록되었거나 오프라인 거래 결과로 최종 평균가를 직접 입력하고 싶을 때 우회 절차 (주수 리셋 → fill 재입력) 가 필요하다.
- 평균가를 바꾸면 "언제 그 평균가가 만들어졌는가" (진입일) 도 자연스럽게 함께 바꾸고 싶은 경우가 존재한다 (예: 포지션을 새로 집계했을 때).
- `BalanceAdjust` 의 본래 목적은 "actual 축의 현재 상태를 한 번에 원하는 값으로 맞추는 것" 이므로, 주수 / 현금뿐 아니라 평균가 / 진입일도 보정 대상에 포함되어야 완전한 보정이 가능하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지** 하고 준수합니다.

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 핵심 원칙 (model/actual 분리, silent skip 금지 + 무조건 알림, 순수 계산/I/O 분리)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then 패턴, `pytest.approx` 사용, 결정적 테스트 원칙
- 루트 [CLAUDE.md](../../CLAUDE.md) — 타입 힌트 / 예외 정책 / 네이밍 / 문서화 원칙
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §8.2.8 — `/balance_adjust/inbox/` 입력 스키마 정본

## 4) 완료 조건(Definition of Done)

- [x] `BalanceAdjust` dataclass 에 `new_avg_price`, `new_entry_date` 필드 추가 완료
- [x] `_apply_single_adjust` 에 신규 분기 구현 완료 (model 축 불변 보장)
- [x] `_dict_to_balance_adjust` 에 신규 필드 파싱 + validation 갱신 완료
- [x] `append_balance_adjust` 호출부(`cli.py`) 에 신규 필드 기록 완료
- [x] 신규/회귀 테스트 추가 완료 (최소 시나리오: T-BA.1 ~ T-BA.9)
- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` §8.2.8 갱신 완료 (필드 표 + 예시 + 입력 검증 역할 분담 섹션)
- [x] `src/live/CLAUDE.md` 갱신 완료 (balance_adjust 의미 / 핵심 제약 갱신)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화 완료

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/models.py` — `BalanceAdjust` dataclass + docstring
- `src/live/balance_adjust.py` — `_apply_single_adjust` 분기 + 모듈 docstring
- `src/live/rtdb_gateway.py` — `_dict_to_balance_adjust` 필드 파싱 + validation
- `src/live/history.py` — docstring 만 보강 (스키마는 free-form dict 이므로 구조적 변경 없음)
- `src/live/cli.py` — `append_balance_adjust` 호출부의 dict literal 에 신규 필드 포함
- `src/live/CLAUDE.md` — balance_adjust 의미 / 핵심 제약 갱신
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §8.2.8 필드 표 / 예시 / 입력 검증 역할 분담 섹션 추가
- `tests/live/test_balance_adjust.py` — 신규 시나리오 추가
- `tests/live/test_rtdb_gateway.py` — `_dict_to_balance_adjust` 파싱 테스트 보강 (있는 경우)
- `README.md`: **변경 없음**

### 데이터/결과 영향

- RTDB `/balance_adjust/inbox/{uuid}` 스키마 확장: `new_avg_price`, `new_entry_date` 필드 추가 (JSON 스키마리스, 기존 레코드 호환)
- `qbt-live-state/history/balance_adjusts.jsonl` 라인 포맷 확장: 신규 필드 포함 (JSONL 스키마리스, 기존 라인 호환)
- `AssetLiveState` 직렬화 스키마 변경 **없음** (`actual_avg_entry_price` / `actual_entry_date` 는 이미 존재)
- `drift_pct` 계산 결과 변경 **없음** (평균가 / 진입일은 equity 공식에 영향 없음)

## 6) 단계별 계획(Phases)

### Phase 0 — 정책 / 계약을 테스트로 먼저 고정(레드)

> 조건: balance_adjust 는 live 의 핵심 상태 변경 경로이며, 이번 변경은 "어떤 조합이 허용되고 어떤 조합이 거부되는가" 라는 정책을 새로 정의한다. 따라서 Phase 0 에 테스트를 먼저 작성하여 레드 상태로 두고, Phase 1 에서 그린으로 돌리는 TDD 순서를 따른다.

**작업 내용**:

- [x] `tests/live/test_balance_adjust.py` 에 아래 시나리오 추가 (레드 허용)
  - [x] `[T-BA.1]` `new_avg_price` 단독 지정 (`actual_shares > 0`) → `actual_avg_entry_price` 변경, `actual_shares` / `actual_entry_date` 유지
  - [x] `[T-BA.2]` `new_shares > 0` + `new_avg_price` 동시 → 두 필드 모두 변경, `actual_entry_date` 유지
  - [x] `[T-BA.3]` `new_shares=0` + `new_avg_price` 동시 → `new_shares=0` 리셋 규칙 우선 (`actual_avg_entry_price=0.0`, `actual_entry_date=None`), `new_avg_price` 무시
  - [x] `[T-BA.4]` `new_avg_price` 단독 + `actual_shares=0` → `ValueError("보유 주수가 0")`
  - [x] `[T-BA.5]` `new_avg_price` 지정 + `asset_id=None` → `ValueError("new_avg_price 지정 시 asset_id 필수")`
  - [x] `[T-BA.6]` `new_entry_date` 단독 지정 (`actual_shares > 0`) → `actual_entry_date` 변경, `actual_avg_entry_price` / `actual_shares` 유지
  - [x] `[T-BA.7]` `new_entry_date` 단독 + `actual_shares=0` → `ValueError("보유 주수가 0")`
  - [x] `[T-BA.8]` 모든 필드 (`new_shares`, `new_avg_price`, `new_entry_date`, `new_cash`) None → `ValueError("유효한 값이 없음")`
  - [x] `[T-BA.9]` `new_avg_price` 적용 후 model 축 불변 검증 (`model_shares`, `model_avg_entry_price`, `model_entry_date`, `shared_cash_model` 모두 입력 state 와 동일)
- [x] `tests/live/test_rtdb_gateway.py` 에 `_dict_to_balance_adjust` 신규 필드 파싱 테스트 추가 (존재 시)

**Validation**:

- 이 Phase 는 레드 허용. 테스트 실행은 하지 않고 Phase 1 에서 그린으로 돌린다.

---

### Phase 1 — live 코어 구현 (그린 유지)

**작업 내용**:

- [x] `src/live/models.py` `BalanceAdjust` dataclass 에 필드 추가
  ```python
  new_avg_price: float | None = None
  new_entry_date: str | None = None
  ```
- [x] `BalanceAdjust` docstring 갱신: 신규 필드 의미 / 허용 조합 / model 축 불변 원칙 명시
- [x] `src/live/balance_adjust.py` `_apply_single_adjust` 분기 재작성
  - [x] `new_avg_price` 또는 `new_entry_date` 가 지정된 경우 `asset_id` 필수 검증 (fail-fast `ValueError`)
  - [x] `new_shares` 가 지정된 경우: 기존 로직 유지 + `new_shares > 0` 이고 `new_avg_price` 가 지정되었으면 `actual_avg_entry_price = new_avg_price`
  - [x] `new_shares` 가 지정된 경우: `new_shares > 0` 이고 `new_entry_date` 가 지정되었으면 `actual_entry_date = new_entry_date`
  - [x] `new_shares=0` 리셋 규칙은 `new_avg_price` / `new_entry_date` 보다 우선 (포지션 없는데 평균가 / 진입일이 있는 것은 무의미)
  - [x] `new_shares` 가 None 이고 `new_avg_price` 또는 `new_entry_date` 가 지정된 경우: `asset.actual_shares == 0` 이면 `ValueError`, 아니면 해당 필드만 갱신
  - [x] `new_cash` 처리는 기존 동작 유지
- [x] `src/live/balance_adjust.py` 모듈 / 함수 docstring 갱신 (현재 규칙 반영)
- [x] `src/live/rtdb_gateway.py` `_dict_to_balance_adjust` 갱신
  - [x] `new_avg_price_raw = raw.get("new_avg_price")` 파싱 (`float` 캐스팅)
  - [x] `new_entry_date_raw = raw.get("new_entry_date")` 파싱 (`str` 캐스팅, 공백 / 빈 문자열은 None 처리)
  - [x] validation 확장: `new_shares`, `new_avg_price`, `new_entry_date`, `new_cash` 모두 None 이면 `ValueError("balance_adjust 에 유효한 new_shares / new_avg_price / new_entry_date / new_cash 값이 없음")`
- [x] `src/live/cli.py` `append_balance_adjust` 호출부 dict literal 에 `"new_avg_price"`, `"new_entry_date"` 필드 추가

**Validation**:

- [x] Phase 0 에서 레드였던 테스트가 모두 그린으로 전환되는지 로컬에서 직접 `pytest tests/live/test_balance_adjust.py` 수동 실행하여 확인 (마지막 Phase 의 전체 검증 전 smoke test)

---

### Phase 2 — 문서 갱신 (그린 유지)

**작업 내용**:

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` §8.2.8 갱신
  - [x] 필드 표에 `new_avg_price`, `new_entry_date` 행 추가
  - [x] 예시 4 ("평균가 직접 보정") / 예시 5 ("평균가 + 진입일 동시 보정") 추가
  - [x] 핵심 제약 3 번 ("`new_shares > 0` 시 기존 `actual_avg_entry_price` / `actual_entry_date` 는 유지") 를 **"`new_avg_price` / `new_entry_date` 를 동시 지정하지 않으면 기존 값 유지"** 로 수정
  - [x] 핵심 제약에 "보유 주수 0 인 자산에 `new_avg_price` / `new_entry_date` 단독 지정 불가" 규칙 추가
  - [x] 신규 섹션 §8.2.8.1 **"입력 검증 역할 분담 (앱 ↔ live)"** 추가 — 아래 내용 포함
    - 1 단계: 앱 클라이언트 측 즉시 검증 (UX 목적 — 사용자에게 즉시 피드백, 잘못된 데이터가 RTDB 에 도달하지 않게 차단)
    - 2 단계: live `daily_runner` 측 최후 방어선 (안전성 목적 — silent skip 금지 + `ValueError` fail-fast + 공통 알림 훅으로 FCM/텔레그램 통보)
    - 두 단계를 모두 두는 이유: 앱 검증은 UX, live 검증은 안전성. 한쪽만 있으면 부족.
- [x] `src/live/CLAUDE.md` 갱신
  - [x] §4.3 (또는 balance_adjust 를 설명하는 섹션) 에 "평균가 / 진입일 단독 보정" 케이스 추가
  - [x] 핵심 제약 목록에 "보유 주수 0 인 자산에 평균가 / 진입일 단독 설정 불가" 추가
  - [x] 핵심 원칙 1 "장애 시 silent skip 금지" 예시 목록에 "balance_adjust 에서 `actual_shares=0` 자산에 `new_avg_price` / `new_entry_date` 단독 설정" 케이스 추가

**Validation**:

- [x] 문서 렌더링 확인 (마크다운 표 구조 / 링크 깨짐 여부 육안 검토)

---

### Phase 3 — 마지막 Phase: 최종 검증 및 포맷 적용

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] plan 상태를 Done 으로 변경 (DoD 모두 [x] + failed=0 + skipped=0 조건 충족 시)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=938, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / balance_adjust 에 new_avg_price / new_entry_date 필드 추가
2. live / BalanceAdjust 평균가 직접 보정 경로 구현 + 설계서 반영
3. live / actual 축 평균가 / 진입일 직접 보정 기능 + 입력 검증 2 단계 문서화
4. live / balance_adjust 확장 (new_avg_price, new_entry_date) + 테스트/문서 동반 갱신
5. live / 잔고 보정 경로에 평균가 / 진입일 필드 추가 및 fail-fast 검증 보강

## 7) 리스크(Risks)

- **기존 RTDB 레코드 호환성**: 기존에 inbox 에 쌓여있던 레코드에는 `new_avg_price` / `new_entry_date` 필드가 없다. `dict.get()` 은 None 반환이므로 호환성 문제 없음. 테스트에서 확인.
- **`applied_balance_adjust_ids` 원장**: 이미 적용된 레코드는 `rtdb_key` 만 키로 사용하므로 스키마 변경 영향 없음.
- **model / actual 축 경계 위반**: `_apply_single_adjust` 작성 시 실수로 `model_*` 필드를 건드리지 않도록 T-BA.9 테스트로 계약 고정.
- **`new_shares=0` + `new_avg_price` 우선순위**: 문서 / 테스트로 명확히 고정하지 않으면 나중에 회귀 발생 가능 → T-BA.3 로 고정.
- **`new_entry_date` 포맷**: ISO 8601 날짜 문자열 (`YYYY-MM-DD`) 을 그대로 저장. 형식 검증은 이번 plan 범위에 포함하지 않음 (앱이 UI 단에서 date picker 로 입력하도록 설계됨). 후속 plan 에서 정규식 검증 추가 가능.

## 8) 메모(Notes)

### 설계 결정 근거

- **질문 1 (`new_entry_date` 포함 여부)**: 사용자와의 협의 결과 **D 안** (`new_avg_price` + `new_entry_date` 두 필드 동시 추가) 으로 확정. `BalanceAdjust` 는 actual 축만 건드리므로 model 축은 그대로 유지됨.
- **질문 2 (`asset_id` 필수 검증)**: 사용자와의 협의 결과 **A 안** (fail-fast `ValueError`) 로 확정. 앱 미구현 상태이므로 앱 구현 시 이 규칙을 처음부터 반영 가능. live 는 2 단계 검증의 "최후 방어선" 역할.

### 진행 로그 (KST)

- 2026-04-16 15:00: plan 작성 시작
- 2026-04-16 15:00: 사용자 확정 — 질문 1 = D 안, 질문 2 = A 안, 계획서 작성 후 승인 없이 바로 진행
- 2026-04-16 15:30: Phase 0 (계약 테스트 9 개 T-BA.1 ~ T-BA.9 + rtdb_gateway 파싱 테스트 2 개) 작성 완료
- 2026-04-16 16:00: Phase 1 (models / balance_adjust / rtdb_gateway / cli 구현) 완료. smoke test 50 개 그린
- 2026-04-16 16:15: Phase 2 (DESIGN §8.2.8 + §8.2.8.1 신설, src/live/CLAUDE.md 원칙 2 / 원칙 1 예시 갱신) 완료
- 2026-04-16 16:30: Phase 3 — black 포맷 적용 (1 파일 reformat), `test_models.py::test_fields` 기대값 갱신 후 validate_project.py 통과 (passed=938, failed=0, skipped=0)

---
