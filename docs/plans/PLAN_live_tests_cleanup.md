# Implementation Plan: live 테스트 정리 (과거 주석/하드코딩 수치 제거, pytest.approx 적용, noqa 정리)

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
**관련 문서**: [tests/CLAUDE.md](../../tests/CLAUDE.md), [live/CLAUDE.md](../../live/CLAUDE.md)

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

- [x] live 테스트의 모든 `TODO T-X.Y`, `TODO_QBT_LIVE.md`, `설계서 X장/X.Y`, `Phase X`, `레드/그린` 과거 상태 표기 제거
- [x] 테스트 docstring/주석에서 `"과거 구조:"`, `"기존 구조:"`, `"이전에는"` 식 설명 제거
- [x] 하드코딩된 수치/리스트 복제 제거 (예: `"4 자산"`, `"6 종"`, `"Q-2-2XS"`, `"portfolio_q2_2xs"`, `"252 거래일"`, `"200 일"`)
- [x] 연산 결과 float 비교에 `pytest.approx()` 적용 (초기값/라벨/정수 비교는 `==` 유지)
- [x] `# noqa: ANN001` (함수 인자 타입 힌트 누락) 를 픽스처 타입힌트 추가로 제거
- [x] 테스트 docstring 은 "무엇을 검증하는가" 계약 중심으로 단순화 (Given-When-Then 구조 유지)

## 2) 비목표(Non-Goals)

- 테스트 케이스의 검증 범위 변경 없음 (오로지 "표현 / 복제 / 단위 정밀도" 정리)
- 신규 테스트 추가는 하지 않음 (선행 Plan 에서 이미 추가됨)
- `type: ignore` 는 live 에 0건이므로 대상 없음
- QBT 본체 테스트(`tests/`) 수정 없음
- 커버리지 변화 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 11개 이상의 live 테스트 파일이 `TODO T-X.Y` 태스크 번호를 docstring 에 기재 → 루트 CLAUDE.md "계획 단계 표현 금지" 원칙 위반
- `test_state.py`, `test_data_fetcher.py`, `test_daily_runner.py`, `test_chart_data.py`, `test_balance_adjust.py`, `test_notifier.py`, `test_constants.py` 등에 `"4 자산 (sso/qld/gld/tlt)"`, `"portfolio_q2_2xs"`, `"Q-2-2XS"` 같은 수치/ID 복제 → "문서 내구성" 원칙 위반
- `test_alert_coverage.py:299-302, 337-339` 등 `"과거 구조: cli.py:502-505..."` 식 과거 라인 번호 주석 → 현재 코드 상태만 기록해야 한다는 원칙 위반
- `test_state.py:77-78, 84-85` 등에서 float `== 0.0` 비교가 있는데, 대부분 초기값 비교라 허용 가능하나 일부 계산 결과 비교는 `pytest.approx()` 로 전환 필요
- `test_git_state.py`, `test_daily_runner.py`, `test_rtdb_gateway.py`, `test_alert_coverage.py` 에 `# noqa: ANN001` 이 과다 → 픽스처 타입힌트 추가로 제거 가능
- 본 Plan 은 앞선 4개 Plan 완료 후 마지막에 실행되어, 그 과정에서 수정된 테스트를 포함해 일괄 청소

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) — 문서화 / 주석 / 문서 내구성 / 부동소수점 비교 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, pytest.approx, noqa 지양
- [live/CLAUDE.md](../../live/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `live/tests/` 하위 모든 `.py` 파일에서 다음 패턴 제거:
  - [x] `TODO T-X.Y` (및 변형 `T-X.Y`)
  - [x] `TODO_QBT_LIVE.md` 참조
  - [x] `설계서 X장`, `설계서 X.Y`, `부록 A/B`, `Gap N`
  - [x] `Phase X`, `레드`, `그린`, `1차/2차 마이그레이션` 등 단계 표현
  - [x] `"과거 구조:"`, `"기존 구조:"`, `"이전에는"`, `"과거에는"` 식 서술
- [x] live 테스트 docstring/주석에서 다음 하드코딩 수치/ID 제거 또는 "현재 포트폴리오 기준" 으로 일반화:
  - [x] `"4 자산"`, `"4 개 자산"`
  - [x] `"6 종"`, `"6 개 티커"`
  - [x] `"Q-2-2XS"`, `"portfolio_q2_2xs"` (상수 참조로 대체)
  - [x] `"252 거래일"` (필요 시 `ANNUAL_TRADING_DAYS` 상수 참조 혹은 docstring 에서 삭제)
  - [x] `"200 일"`, `"200일선"`, `"EMA-200"` (`slot.ma_window` 기반으로 일반화)
  - [x] `"SPY→SSO, QQQ→QLD, GLD→GLD, TLT→TLT"` (하드코딩된 매핑 예시)
- [x] 계산 결과 float 비교에 `pytest.approx()` 적용:
  - [x] `test_drift.py` 의 drift_pct / equity 계산 결과
  - [x] `test_daily_runner.py` 의 model_equity / ma_distance_pct 계산 결과
  - [x] `test_buffer_serializer.py` 의 `_prev_upper / _prev_lower` 왕복값 (단, 초기 상수값 복원은 `==` 허용)
  - [x] 초기값/정수/라벨/날짜 비교는 `==` 유지
- [x] `# noqa: ANN001` 제거:
  - [x] `test_daily_runner.py` — 픽스처 함수 반환 타입 힌트 추가
  - [x] `test_git_state.py` — subprocess 관련 mock 헬퍼 타입 힌트
  - [x] `test_rtdb_gateway.py` — mock 클래스에 적절한 Protocol / TypedDict
  - [x] `test_alert_coverage.py` — 픽스처 타입 힌트
- [x] 테스트 docstring 은 Given-When-Then 구조 유지 + 목적 한 줄 + 핵심 계약 한 줄 이상
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/tests/test_alert_coverage.py`
- `live/tests/test_balance_adjust.py`
- `live/tests/test_buffer_serializer.py`
- `live/tests/test_chart_data.py`
- `live/tests/test_cli.py`
- `live/tests/test_constants.py`
- `live/tests/test_daily_runner.py`
- `live/tests/test_data_fetcher.py`
- `live/tests/test_data_validator.py`
- `live/tests/test_drift.py`
- `live/tests/test_git_state.py`
- `live/tests/test_history.py`
- `live/tests/test_models.py`
- `live/tests/test_notifier.py`
- `live/tests/test_regression.py`
- `live/tests/test_rtdb_gateway.py`
- `live/tests/test_state.py`
- `live/tests/test_workflows.py`
- `live/tests/conftest.py` (필요 시)
- `README.md`: **변경 없음**

### 데이터/결과 영향

- 없음 (테스트 문구 / 비교 연산자 / 타입 힌트 정리만 수행)
- 테스트 통과 수 동일 (이전 Plan 들의 DoD 가 이미 달성된 상태 가정)

## 6) 단계별 계획(Phases)

### Phase 1 — 과거 표기 / 태스크 번호 제거 (그린 유지)

**작업 내용**:

- [x] 각 파일 상단 모듈 docstring 의 `TODO T-X.Y`, `TODO_QBT_LIVE.md`, `설계서 X장` 제거. 필요 시 한 줄 요약 ("buffer_serializer 어댑터 왕복 계약 테스트") 으로 대체
- [x] 각 테스트 메서드 docstring 의 `"T-X.Y:"` 접두사 제거
- [x] `"과거 구조:"`, `"기존 구조:"`, `"이전에는"` 식 주석/docstring 제거
- [x] `Phase X`, `레드`, `그린`, `1차` 등 단계 표현 제거
- [x] `부록 A/B`, `Gap N` 문구 제거

---

### Phase 2 — 하드코딩 수치/ID 정리 (그린 유지)

**작업 내용**:

- [x] `"4 자산"`, `"4 개 자산"` → `"포트폴리오 자산"` 또는 삭제
- [x] `"6 종"`, `"6 개 티커"` → `"포트폴리오 자산 티커"` 또는 `len(_collect_all_tickers())` 참조
- [x] `"Q-2-2XS"`, `"portfolio_q2_2xs"` → `LIVE_PORTFOLIO_ID` 상수 참조. 테스트 내에서 실제 문자열 비교가 필요한 경우 `from live.constants import LIVE_PORTFOLIO_ID` 후 `assert config.experiment_name == LIVE_PORTFOLIO_ID` 식으로 변경
- [x] `"200 일"` / `"200일선"` / `"EMA-200"` → `slot.ma_window` 기반 표현 또는 MA 일반화. notifier 본문 테스트는 `"MA 근접도"` 로 이미 업데이트됨 (PLAN_live_chart_ma_rename)
- [x] `"SPY→SSO, QQQ→QLD"` 같은 매핑 예시 주석 제거 — `build_signal_trade_map()` 함수 실행 결과로 검증하되 구체 값은 주석에 남기지 않음
- [x] `"252 거래일"` 은 `ANNUAL_TRADING_DAYS` 라는 공통 상수가 있는지 확인 후 참조 또는 제거

---

### Phase 3 — pytest.approx 적용 및 noqa 제거 (그린 유지)

**작업 내용**:

- [x] 각 테스트 파일에서 다음 패턴을 검토:
  - `result.drift_pct == 0.0` → `result.drift_pct == pytest.approx(0.0)` (계산 결과인 경우)
  - `asset.model_avg_entry_price == 0.0` → **`==` 유지** (초기값 할당)
  - 밴드/equity/pnl 등 계산 결과 → `pytest.approx(expected, abs=적절한 허용오차)`
- [x] 허용오차 기준은 `tests/CLAUDE.md` 표 참조 (equity → 0.01~0.1, drift_pct → 0.1 등)
- [x] `# noqa: ANN001` 대상:
  - [x] 픽스처 함수의 인자 타입 힌트(`tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`, `caplog: pytest.LogCaptureFixture`) 추가
  - [x] mock 클래스의 `__init__` / 메서드 인자에 `Any` 또는 실제 타입 지정
- [x] lint 오류가 발생하면 ruff/pyright 메시지에 따라 수정

---

### Phase 4 — 최종 청소 및 스타일 일치 (그린 유지)

**작업 내용**:

- [x] 각 테스트 파일을 훑어 Given-When-Then 3 단계 주석이 누락된 부분이 있는지 확인, 필요 시 최소한 `# Given / # When / # Then` 주석 추가 (기존 구조가 이미 있으면 유지)
- [x] docstring 이 과도하게 장황한 경우 한두 줄로 압축
- [x] 테스트 파일 import 순서/알파벳 정렬 통일
- [x] `conftest.py` 의 픽스처 타입힌트 점검

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (`README.md` 변경 없음 명시)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=881, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 테스트 문서 내구성 정리 — 과거 주석/하드코딩 수치 제거 + approx 적용
2. live / 테스트 docstring/주석 청소 및 noqa ANN001 제거
3. live / 테스트 계약 유지하며 표현 정리 (T-X.Y 제거, MA/포트폴리오 일반화)
4. live / pytest.approx 일괄 적용 + 픽스처 타입힌트 + 주석 최소화
5. live / CLAUDE.md 문서 내구성 원칙 테스트 파일에 적용

## 7) 리스크(Risks)

- 대량 치환 과정에서 실제 계약 로직이 섞인 주석을 실수로 삭제할 수 있음 → Phase 1/2 를 파일 단위로 나눠 진행, diff 리뷰 필수
- `pytest.approx` 전환 중 허용오차를 잘못 설정하여 회귀 발생 가능 → tests/CLAUDE.md 표 기준 엄격 준수
- `# noqa: ANN001` 제거 중 `Any` 대체가 타입 체커 경고를 유발할 수 있음 → Protocol 정의 또는 mock 라이브러리 타입 참조
- `"portfolio_q2_2xs"` 문자열을 제거하는 과정에서 동작 검증(실제 문자열 비교) 테스트와 표기 개선(주석) 을 구분해야 함

## 8) 메모(Notes)

- 본 Plan 은 4개 선행 Plan 완료 이후 마지막에 진행한다
- 실행 순서: 파일 단위로 `test_state.py` → `test_drift.py` → `test_daily_runner.py` → `test_cli.py` → 기타
- 각 파일 변경 후 해당 파일만 `poetry run pytest live/tests/test_xxx.py -v` 로 부분 검증 (마지막 Phase 만 validate_project.py 실행)

### 진행 로그 (KST)

- 2026-04-12 09:00: 계획서 초안 작성

---
