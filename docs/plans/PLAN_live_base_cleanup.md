# Implementation Plan: live 도메인 기반 정리 (상수·데드코드·lazy import·문서 내구성)

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

- [x] live 도메인의 의미 없는 import 유지 코드(`_ = replace` 등) 제거
- [x] 공통 KST 타임존을 `constants.py` 단일 정본으로 통합
- [x] CSV 컬럼 문자열 하드코딩(`"Date"`, `"Close"`, `"Open"` 등)을 `COL_*` 상수로 치환
- [x] `_live_csv_path` 중복 정의를 공용 헬퍼로 통합
- [x] `_VALID_INTENT_TYPES` 등 `IntentTypeLiteral` 과 중복 정본을 `typing.get_args()` 로 파생
- [x] `_BUY_INTENT_TYPES / _SELL_INTENT_TYPES` 집합 정본화 (`constants.py`)
- [x] `_PREV_CLOSE_DIFF_THRESHOLD` 를 `constants.py` 로 승격
- [x] `FIREBASE_DB_URL`, `_ENV_*` 환경변수 키를 `constants.py` 로 이동
- [x] `cleanup_old_fill_ids` → `cleanup_old_applied_ids` 범용 이름으로 리네임
- [x] firebase_admin / exchange_calendars / requests lazy import 를 모두 모듈 상단 import 로 이동
- [x] live/CLAUDE.md 를 "문서 내구성" 원칙에 맞게 축약 (모듈 표는 역할 한 줄로, 하드코딩 수치/리스트 제거)

## 2) 비목표(Non-Goals)

- `signal_state` 의 `"hold"` → `"none"` 마이그레이션 (PLAN_live_signal_state_none 에서 처리)
- `ChartSeries.ema_200` → `ma_value` 리네임 (PLAN_live_chart_ma_rename 에서 처리)
- fallback 제거 / RuntimeError/ValueError 정책 강화 (PLAN_live_failfast_policy 에서 처리)
- 테스트의 `T-X.Y` / 과거 주석 / `pytest.approx` 일괄 청소 (PLAN_live_tests_cleanup 에서 처리)
- `cli.py` 파일 분리 (범위 외)
- QBT 본체(`src/qbt/`) 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `daily_runner.py`, `state.py`, `notifier.py` 에 `_ = replace`, `_ = AssetLiveState`, `_ = KST_TZ_NAME`, `_ = Any` 같은 무의미한 import 유지 코드가 있음 → YAGNI 원칙 위반
- `_KST = timezone(timedelta(hours=9))` 가 `state.py`, `drift.py`, `balance_adjust.py` 3곳에 중복 정의되어 있고, `cli.py` 만 `ZoneInfo("Asia/Seoul")` 를 사용 → SSoT 부재
- `cli.py:553`, `cli.py:599`, `cli.py:692` 등에서 `row["Date"]`, `row["Close"]` 문자열 직접 접근 → `COL_*` 상수 미사용
- `_live_csv_path(state_dir, ticker)` 가 `cli.py` 와 `chart_data.py` 두 곳에 동일 복제
- `state.py:297-299` 의 `_VALID_INTENT_TYPES` 집합과 `models.py:55` 의 `IntentTypeLiteral` 이 수동 이중 정본
- `drift.py:34-35` 의 `_BUY_INTENT_TYPES / _SELL_INTENT_TYPES` 가 도메인 의미론이므로 상수화 가치 있음
- `_PREV_CLOSE_DIFF_THRESHOLD = 0.01` 이 `data_validator.py` 파일 로컬에만 있음 → 튜닝 가능 임계값은 `constants.py` 가 적절
- `FIREBASE_DB_URL`, `_ENV_FIREBASE_CRED` 등 환경/인프라 상수가 `cli.py` 에 하드코딩 → 재사용성 저하
- `cleanup_old_fill_ids` 가 balance_adjust 원장에도 재사용되는데 이름은 fill 고정 → 가독성 저하
- `firebase_admin` / `exchange_calendars` / `requests` 가 lazy import 되어 있어 타입 체커 추적이 어렵고, 런타임 시점에 import 실패가 발생할 수 있음. live extras 가 필수 의존성이므로 근본 해결 가능
- `live/CLAUDE.md` 가 폴더 구조 트리/모듈 역할 표/인프라 표를 상세히 나열 → 일부 항목은 "문서 내구성" 원칙(코드에서 파생 가능한 정보 복제 금지) 위반

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트 — 상수 관리 3계층, 네이밍 규칙, 문서 내구성 원칙)
- [live/CLAUDE.md](../../live/CLAUDE.md) (live 도메인 가이드)
- [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (인프라 정보는 본 문서와 `constants.py` 가 정본)

## 4) 완료 조건(Definition of Done)

- [x] live 도메인 내 의미 없는 `_ = XXX` 코드 모두 제거 + 해당 미사용 import 정리
- [x] `constants.py` 에 `KST_TIMEZONE`, `FIREBASE_DB_URL`, `FIREBASE_CRED_ENV_KEY`, `TELEGRAM_TOKEN_ENV_KEY`, `TELEGRAM_CHAT_ENV_KEY`, `STATE_REPO_PAT_ENV_KEY`, `NYSE_CALENDAR_CODE`, `PREV_CLOSE_DIFF_THRESHOLD`, `BUY_INTENT_TYPES`, `SELL_INTENT_TYPES`, `VALID_INTENT_TYPES` 상수 추가
- [x] `state.py`, `drift.py`, `balance_adjust.py` 에서 `_KST` 로컬 정의 제거 → `constants.KST_TIMEZONE` 사용
- [x] `cli.py`, `chart_data.py`, `data_validator.py` 의 CSV 컬럼 문자열 하드코딩을 `qbt.common_constants.COL_*` / `PRICE_COLUMNS` 로 치환
- [x] `live_csv_path(state_dir, ticker)` 공용 헬퍼를 `constants.py` 에 추가하고 `cli.py` / `chart_data.py` 에서 재사용
- [x] `state._VALID_INTENT_TYPES` 삭제 후 `models.VALID_INTENT_TYPES = frozenset(get_args(IntentTypeLiteral))` 로 파생
- [x] `drift._BUY_INTENT_TYPES / _SELL_INTENT_TYPES` 를 `constants.BUY_INTENT_TYPES / SELL_INTENT_TYPES` 로 이동
- [x] `cleanup_old_fill_ids` → `cleanup_old_applied_ids` 리네임 (cli.py 호출부 2곳 포함)
- [x] `rtdb_gateway.py` 의 `firebase_admin`, `credentials`, `db` lazy import → 모듈 상단
- [x] `notifier.py` 의 `firebase_admin.messaging`, `FirebaseError`, `requests` lazy import → 모듈 상단
- [x] `cli.py` 의 `exchange_calendars.get_calendar` lazy import → 모듈 상단, `_get_nyse_calendar` 함수는 유지하되 단순 호출 래퍼로 변경
- [x] `live/CLAUDE.md` 수정: 폴더 구조 트리 유지, 모듈 역할 표는 "한 줄 책임" 만 남기고 구현 디테일(실행 순서 등) 제거, 인프라 표 유지
- [x] 회귀/신규 테스트 추가 또는 기존 테스트 업데이트 (상수 이름 변경, 헬퍼 경로 변경 반영)
- [x] `poetry run python validate_project.py` 통과 (passed=872, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(`README.md` 변경 없음 명시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/constants.py` — 상수 추가 (KST/env keys/intent sets/helper)
- `live/src/live/state.py` — `_KST` 제거, `_VALID_INTENT_TYPES` 제거, `_ = KST_TZ_NAME` 제거, `cleanup_old_fill_ids` → `cleanup_old_applied_ids` 리네임
- `live/src/live/drift.py` — `_KST`, `_BUY/_SELL_INTENT_TYPES` 제거
- `live/src/live/balance_adjust.py` — `_KST` 제거
- `live/src/live/daily_runner.py` — `_ = replace`, `_ = AssetLiveState` 제거 + 미사용 import 정리
- `live/src/live/notifier.py` — `_ = Any` 제거, lazy import 상단 이동
- `live/src/live/rtdb_gateway.py` — lazy import 상단 이동
- `live/src/live/cli.py` — env key / FIREBASE_DB_URL 상수화, exchange_calendars 상단 import, CSV 컬럼 상수 사용, `cleanup_old_fill_ids` 호출부 리네임
- `live/src/live/chart_data.py` — `_live_csv_path` 제거 (공용 헬퍼 사용), CSV 컬럼 상수 사용
- `live/src/live/models.py` — `VALID_INTENT_TYPES` export 추가
- `live/src/live/data_validator.py` — `_PREV_CLOSE_DIFF_THRESHOLD` 제거
- `live/CLAUDE.md` — 모듈 표 축약
- `live/tests/` — 경로/상수명 변경이 반영되는 기존 테스트 업데이트
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 출력 스키마 변경 없음
- LiveState JSON 포맷 변경 없음 (`SCHEMA_VERSION` bump 없음)
- RTDB 페이로드 변경 없음
- 기존 `qbt-live-state` 데이터 호환성 유지

## 6) 단계별 계획(Phases)

### Phase 1 — constants.py 확장 및 공용 헬퍼 준비 (그린 유지)

**작업 내용**:

- [x] `live/src/live/constants.py` 에 다음 상수 추가:
  - [x] `KST_TIMEZONE: Final[ZoneInfo] = ZoneInfo(KST_TZ_NAME)` (기존 `KST_TZ_NAME` 은 유지, 역할은 "문자열 이름")
  - [x] `FIREBASE_DB_URL: Final[str] = "https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app"`
  - [x] `NYSE_CALENDAR_CODE: Final[str] = "XNYS"`
  - [x] `FIREBASE_CRED_ENV_KEY: Final[str] = "GOOGLE_APPLICATION_CREDENTIALS"`
  - [x] `TELEGRAM_TOKEN_ENV_KEY: Final[str] = "TELEGRAM_BOT_TOKEN"`
  - [x] `TELEGRAM_CHAT_ENV_KEY: Final[str] = "TELEGRAM_CHAT_ID"`
  - [x] `STATE_REPO_PAT_ENV_KEY: Final[str] = "STATE_REPO_PAT"`
  - [x] `PREV_CLOSE_DIFF_THRESHOLD: Final[float] = 0.01` (주석: 스플릿/무상증자/사용자 수동 조작 탐지 임계값)
  - [x] `BUY_INTENT_TYPES: Final[frozenset[str]] = frozenset({"ENTER_TO_TARGET", "INCREASE_TO_TARGET"})`
  - [x] `SELL_INTENT_TYPES: Final[frozenset[str]] = frozenset({"EXIT_ALL", "REDUCE_TO_TARGET"})`
  - [x] 공용 헬퍼 `live_csv_path(state_dir: Path, ticker: str) -> Path` 추가 (기존 `DEFAULT_DATA_STOCK_SUBDIR / f"{ticker}.csv"` 로직)
- [x] `live/src/live/models.py` 에 `VALID_INTENT_TYPES = frozenset(get_args(IntentTypeLiteral))` 파생 상수 추가 + `__all__` 업데이트
- [x] 이 Phase 범위에서는 신규 상수 정의만 추가하고, 기존 하드코딩 제거는 Phase 2~3 에서 수행한다.

---

### Phase 2 — 공통화 / 데드코드 제거 (그린 유지)

**작업 내용**:

- [x] `state.py`: `_KST` 로컬 정의 제거 → `from live.constants import KST_TIMEZONE` 사용. `_now_kst_iso()` 내부도 `KST_TIMEZONE` 사용
- [x] `state.py`: `_VALID_INTENT_TYPES` 삭제 → `from live.models import VALID_INTENT_TYPES` 재사용
- [x] `state.py`: 맨 아래 `_ = KST_TZ_NAME` 제거 + `KST_TZ_NAME` import 제거
- [x] `state.py`: `cleanup_old_fill_ids(ids, max_age_days=...)` → `cleanup_old_applied_ids(ids, max_age_days=...)` 로 리네임, docstring 도 "applied_*_ids 원장" 으로 일반화
- [x] `drift.py`: `_KST` 제거 + `_BUY_INTENT_TYPES / _SELL_INTENT_TYPES` 제거 → `constants.KST_TIMEZONE / BUY_INTENT_TYPES / SELL_INTENT_TYPES` 사용
- [x] `balance_adjust.py`: `_KST` 제거 → `constants.KST_TIMEZONE` 사용
- [x] `daily_runner.py`: `_ = replace`, `_ = AssetLiveState` 제거 + 관련 미사용 import (`dataclasses.replace`) 제거
- [x] `notifier.py`: `_ = Any` 제거 + `Any` import 제거
- [x] `data_validator.py`: `_PREV_CLOSE_DIFF_THRESHOLD` 로컬 정의 제거 → `from live.constants import PREV_CLOSE_DIFF_THRESHOLD` 사용
- [x] `chart_data.py`: 로컬 `_live_csv_path` 제거 → `from live.constants import live_csv_path` 사용
- [x] `cli.py`: 로컬 `_live_csv_path` 제거 → `from live.constants import live_csv_path` 사용
- [x] `cli.py`: `cleanup_old_fill_ids` 호출 2곳을 `cleanup_old_applied_ids` 로 업데이트
- [x] 각 파일 수정 후 `from live.constants import ...` 를 알파벳 순 정렬 유지

---

### Phase 3 — 환경/CSV 컬럼 상수화 + lazy import 해제 (그린 유지)

**작업 내용**:

- [x] `cli.py`:
  - [x] `FIREBASE_DB_URL`, `_ENV_FIREBASE_CRED`, `_ENV_TG_TOKEN`, `_ENV_TG_CHAT`, `_ENV_STATE_REPO_PAT` 로컬 정의 제거 → `constants` 에서 import
  - [x] `_initialize_rtdb_app`, `_safe_notify_failure`, `_send_daily_notifications` 등에서 새 상수 사용
  - [x] `_get_nyse_calendar` 의 lazy import 제거: 모듈 상단에 `from exchange_calendars import ExchangeCalendar, get_calendar` 추가, 함수 본문은 `get_calendar(NYSE_CALENDAR_CODE)` 만 호출. `ExchangeCalendar` 타입 힌트 추가로 `Any` 제거
  - [x] `_validate_against_csv`, `_refresh_live_csvs` 에서 `recent_df["Date"]`, `yf_row["Date"]`, `csv_by_date = {row["Date"]: float(row["Close"])}` 등 CSV 문자열 접근을 `COL_DATE`, `COL_CLOSE` 로 치환. `qbt.common_constants` 에서 import
  - [x] `_cmd_drift` 의 `md.trade_df["Close"].iloc[-1]` → `md.trade_df[COL_CLOSE].iloc[-1]`
- [x] `chart_data.py`: CSV 컬럼 문자열이 이미 `COL_DATE/COL_CLOSE` 사용 중인지 점검, 누락 있으면 치환
- [x] `data_validator.py`: `validate_ohlc_logic` 의 `series["Open"]`, `series["High"]`, `series["Low"]`, `series["Close"]` 문자열 접근은 yfinance 행의 raw 컬럼이므로 `qbt.common_constants.PRICE_COLUMNS` 또는 개별 `COL_OPEN/COL_HIGH/COL_LOW/COL_CLOSE` 사용으로 치환
- [x] `rtdb_gateway.py`:
  - [x] 모듈 상단에 `import firebase_admin`, `from firebase_admin import credentials, db` 이동
  - [x] `_db_reference` 내부 lazy import 제거
  - [x] `initialize_firebase_app` 내부 lazy import 제거
  - [x] `FirebaseAppLike = Any` 타입 별칭 유지 가능하나, 상단에 `from firebase_admin import App` 을 추가하고 `type FirebaseAppLike = App` 로 변경 (타입 체커가 실제 App 을 인식하도록)
- [x] `notifier.py`:
  - [x] 모듈 상단에 `from firebase_admin import messaging`, `from firebase_admin.exceptions import FirebaseError`, `import requests` 이동
  - [x] `_send_fcm_messages`, `_send_telegram_message` 내부 lazy import 제거
- [x] 테스트에서 `firebase_admin` / `requests` / `exchange_calendars` 를 mock 하는 방식이 여전히 동작하는지 확인 (module 상단 import 이므로 monkeypatch 경로 변경 필요할 수 있음 → 기존 테스트 갱신)

---

### Phase 4 — live/CLAUDE.md 축약 (그린 유지)

**작업 내용**:

- [x] `live/CLAUDE.md` 의 "폴더 구조" 트리는 파일명 수준까지 유지 (코드에서 직접 확인 가능하지만, 독자 가이드용으로 허용)
- [x] "모듈별 역할 요약" 표는 각 모듈당 **한 줄 책임 서술** 만 남기고, 실행 순서/내부 단계 나열을 제거 (예: `daily_runner.py` 의 "fills → pending → equity → 시그널 → balance_adjust → drift" 나열 삭제. 대신 "순수 계산 `run_daily` — 파일 I/O 없음" 정도)
- [x] "핵심 원칙" 섹션은 유지 (정책이므로 SSoT)
- [x] "인프라 정보" 표 유지 (코드 파생 불가)
- [x] "의존성 설치" / "실행 방법" / "참고 문서" 섹션 유지
- [x] `SSO → QLD`, `SPY → SSO` 같은 예시 나열은 제거 (`constants.build_signal_trade_map` 이 SSoT)
- [x] 설계서(`docs/DESIGN_QBT_LIVE_FINAL.md`) 는 본 Plan 에서 **변경하지 않는다**. 이후 signal_state / ma_value / fail-fast Plan 에서 관련 섹션만 수정한다

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 확인 (`README.md` 변경 없음 명시)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=872, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 공통 상수 통합 및 lazy import 정리 (KST/env/CSV 컬럼/intent 집합 SSoT 통합)
2. live / 기반 정리 — 데드코드 제거, KST 타임존 단일화, lazy import 상단 이동
3. live / 상수 SSoT 통합 + firebase/exchange_calendars 상단 import + CLAUDE.md 축약
4. live / 하드코딩 상수 제거 및 공용 헬퍼 승격 (cleanup_old_applied_ids 리네임 포함)
5. live / 문서 내구성 원칙 적용 + 상수/lazy import 정리

## 7) 리스크(Risks)

- lazy import → 상단 import 이동 과정에서 기존 테스트의 mock/patch 경로가 변경될 수 있음 (예: `live.rtdb_gateway._db_reference` 내부에서 `from firebase_admin import db` 가 사라지면 monkeypatch 위치가 달라짐). 영향 파일: `test_rtdb_gateway.py`, `test_notifier.py`, `test_cli.py` → Phase 3 에서 테스트 수정 필수
- `cleanup_old_fill_ids` 리네임은 CLI 호출부 2곳 외에도 테스트 호출 다수 존재 → `test_state.py` 업데이트 필수
- `_ = replace` 제거 시 `dataclasses.replace` import 도 함께 제거해야 미사용 import lint 에 걸리지 않음
- `rtdb_gateway.FirebaseAppLike` 타입이 mock 테스트에 영향 줄 수 있음 — 테스트는 duck typing 사용하므로 타입 별칭만 변경하고 실제 mock 동작은 그대로 유지

## 8) 메모(Notes)

- 본 Plan 은 "의미 없는 코드 정리 + SSoT 통합 + 문서 내구성" 에만 집중한다
- 후속 Plan 이 이 Plan 의 상수/헬퍼/KST 를 전제로 작성되므로 먼저 완료되어야 한다

### 진행 로그 (KST)

- 2026-04-12 09:00: 계획서 초안 작성

---
