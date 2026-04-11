# Implementation Plan: QBT Live - Step 6 데이터 검증 (data_validator.py)

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

**작성일**: 2026-04-11 13:24
**마지막 업데이트**: 2026-04-11 13:24
**관련 범위**: live
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (3장, 11장, 부록 A)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 6)
- [live/CLAUDE.md](../../live/CLAUDE.md)

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드" 허용, Phase 1부터 **그린 유지**.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**.

---

## 1) 목표(Goal)

- [x] 목표 1: 설계서 3장의 3 개 검증 함수 구현 (`validate_ohlc_logic`, `validate_prev_close`, `validate_date_gap`)
- [x] 목표 2: TODO T-6.1 ~ T-6.8 테스트 시나리오 전체 통과
- [x] 목표 3: 보간 금지, 즉시 에러 메시지 리스트 반환 (호출자가 중단 여부 결정)

## 2) 비목표(Non-Goals)

- daily_runner 에서의 호출 흐름 (Step 7)
- yfinance 호출 / CSV I/O (Step 5 완료)

## 3) 배경/맥락

### 동기

- live 환경에서 CSV append 전에 주가 데이터 이상을 검출해야 한다 (설계서 3장)
- 3 가지 검증만 수행: OHLC 논리 / 전일 종가 연속성 (스플릿 감지) / 거래일 누락
- 보간 금지 원칙에 따라 이상 발견 시 에러 메시지를 반환만 하고, 호출자가 즉시 중단 + 알림

### 영향받는 규칙

- [CLAUDE.md](../../CLAUDE.md), [live/CLAUDE.md](../../live/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)
- 설계서 3장, 11장

### 설계 결정

#### D1. 반환 타입 — **`list[str]`** (부록 A 그대로)

- 각 검증 함수는 에러 메시지 리스트 반환
- 빈 리스트 = 검증 통과
- 호출자(CLI) 가 리스트가 비어있지 않으면 중단 + 알림 발송

#### D2. 전일 종가 연속성 임계값 — **1% (0.01)**

- 설계서 2.3 "전일 종가 1%+ 차이 -> 즉시 중단 + 알림. 수동: live.cli rebuild-data --period max"
- 1% 임계값은 스플릿/무상증자 감지 용도

#### D3. 거래일 누락 검증 — **exchange_calendars NYSE 사용**

- `exchange_calendars.get_calendar("XNYS")` 로 NYSE 달력 조회
- CSV 마지막 거래일과 오늘 사이에 누락된 거래일이 있는지 확인
- 달력 파라미터는 호출자가 주입 (테스트 가능성)

#### D4. 입력 타입

- `validate_ohlc_logic(row)`: 1 행 DataFrame 또는 `pd.Series` (Open/High/Low/Close 필드)
- `validate_prev_close(csv_close, yf_close)`: float 2 개
- `validate_date_gap(csv_last, today, calendar)`: date 2 개 + calendar 객체

## 4) 완료 조건(DoD)

- [x] `live/src/live/data_validator.py` 에 3 개 함수 구현
- [x] `live/tests/test_data_validator.py` 작성 및 통과 (T-6.1 ~ T-6.8 전체)
- [x] exchange_calendars 실제 달력 사용 (live extras 에 이미 설치됨)
- [x] QBT 본체 수정 없음
- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] TODO Step 6 체크박스 체크
- [x] plan 체크박스 최신화

## 5) 변경 범위

### 신규 작성

- `live/src/live/data_validator.py` (내용 채우기)
- `live/tests/test_data_validator.py`

### 수정

- `docs/TODO_QBT_LIVE.md`

### README 변경 여부

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] `test_data_validator.py` 작성 (T-6.1 ~ T-6.8 + 경계 케이스)

### Phase 1 — 구현

- [x] `validate_ohlc_logic(row) -> list[str]`
  - High < Low → 에러
  - 가격 0 또는 음수 → 에러
  - Open/Close 가 High~Low 범위 밖 → 에러
- [x] `validate_prev_close(csv_close, yf_close) -> list[str]`
  - `abs(yf - csv) / csv > 0.01` → 에러 (설계서 2.3)
  - csv_close <= 0 → 에러 (분모 0 방지)
- [x] `validate_date_gap(csv_last, today, calendar) -> list[str]`
  - `calendar.sessions_in_range(csv_last + 1일, today - 1일)` 이 비어있지 않으면 누락
  - today 가 거래일이면 그 전날까지 비교. 거래일이 아니면 다음 거래일 기준.

### Phase 2 — 문서 동기화

- [x] TODO Step 6 체크박스 체크

### 마지막 Phase — 최종 검증

- [x] black + validate_project
- [x] plan Done 처리

**Validation**:

- [x] `poetry run python validate_project.py` (passed=650, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / 데이터 검증 3종 (Step 6)`
2. `live / data_validator.py — OHLC/종가연속성/날짜누락`
3. `live / 스플릿 감지 + 거래일 누락 검증`
4. `live / exchange_calendars 기반 거래일 검증`
5. `live / Step 6 data_validator + T-6.1~T-6.8`

## 7) 리스크

- exchange_calendars 달력 로드 속도 (첫 호출 시 lazy init) — 테스트에서는 calendar 를 픽스처로 캐싱
- NYSE 휴일 데이터가 라이브러리에서 주기적으로 업데이트됨

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 13:24: 계획서 작성

---
