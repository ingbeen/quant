# Implementation Plan: live 소수점 반올림 + 데이터 무결성 (QBT 원칙 통일)

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

**작성일**: 2026-04-12 22:30
**마지막 업데이트**: 2026-04-12 22:30
**관련 범위**: live
**관련 문서**: `live/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] QBT 반올림 규칙을 live 전체에 일관 적용 (저장/직렬화/RTDB 직전에만 반올림)
- [x] data_fetcher.py append_today_to_csv 의 반올림 누락 수정
- [x] rtdb_gateway.py 의 RTDB 데이터 필드 검증 추가

## 2) 비목표(Non-Goals)

- 내부 연산 정밀도 변경 (무한 정밀도 유지)
- 상수화 / 주석 정리 (Plan 3)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

QBT 반올림 규칙: 가격 6자리, 자본금 정수(0자리), 백분율 2자리, 비율 4자리.
live 도메인은 이 규칙을 저장/출력 경로에 적용하지 않아 무한 정밀도 float 가 그대로
JSON / RTDB / CSV 에 기록된다.

적용 대상 (저장/직렬화/RTDB 업로드 직전):
- `data_fetcher.py`: CSV 저장 직전 가격 반올림 누락
- `chart_data.py`: RTDB 업로드용 시계열 값 반올림 없음
- `drift.py`: drift_pct 는 표시/알림용이므로 반올림 필요
- `daily_runner.py`: DailyResult 의 equity / ma_distance_pct
- `balance_adjust.py`: shared_cash_actual 반올림
- `rtdb_gateway.py`: RTDB 입력 데이터 필드 검증 부재

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `live/CLAUDE.md`
- `tests/CLAUDE.md`
- 루트 `CLAUDE.md` (출력 데이터 반올림 규칙)

## 4) 완료 조건(Definition of Done)

- [x] `data_fetcher.py`: append_today_to_csv concat 후 반올림 추가
- [x] `chart_data.py`: close/MA/밴드 값 가격 반올림 적용
- [x] `drift.py`: drift_pct / asset_drift_pct 백분율 반올림
- [x] `daily_runner.py`: model_equity/actual_equity 정수 반올림, ma_distance_pct 비율 반올림
- [x] `balance_adjust.py`: shared_cash_actual 정수 반올림
- [x] `rtdb_gateway.py`: _dict_to_actual_fill / _dict_to_balance_adjust 필수 필드 검증
- [x] 테스트 통과
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/data_fetcher.py`
- `live/src/live/chart_data.py`
- `live/src/live/drift.py`
- `live/src/live/daily_runner.py`
- `live/src/live/balance_adjust.py`
- `live/src/live/rtdb_gateway.py`
- `live/tests/test_rtdb_gateway.py` (검증 테스트 추가)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 기존 동작 변경: CSV / JSON / RTDB 에 저장되는 값의 소수점 자릿수가 제한됨
- 내부 계산 결과는 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 소수점 반올림 적용 + RTDB 검증

**작업 내용**:

- [x] `data_fetcher.py`: concat 후 `combined[PRICE_COLUMNS].round(DEFAULT_PRICE_DECIMALS)` 추가
- [x] `chart_data.py`: close/MA/밴드 값에 `round(v, 6)` 적용
- [x] `drift.py`: `asset_drift_pct = round(...)` 2자리, `drift_pct = round(...)` 2자리
- [x] `daily_runner.py`: `model_equity = round(..., 0)`, `actual_equity = round(..., 0)`, `ma_distance_pct = round(..., 4)`
- [x] `balance_adjust.py`: `state.shared_cash_actual = round(float(adjust.new_cash), 0)`
- [x] `rtdb_gateway.py`: _dict_to_actual_fill / _dict_to_balance_adjust 에 필수 필드 존재 검증 + ValueError
- [x] `test_rtdb_gateway.py`: 필수 필드 누락 시 ValueError 테스트 추가

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=891, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. live / QBT 반올림 규칙 적용 + RTDB 입력 검증 강화
2. live / 소수점 정밀도 통일 및 데이터 무결성 검증 추가
3. live / 저장/직렬화 경로 반올림 적용 + RTDB 필드 검증
4. live / 가격 6자리·자본금 정수·백분율 2자리 반올림 통일
5. live / CSV·RTDB·JSON 출력 반올림 규칙 적용 및 입력 검증

## 7) 리스크(Risks)

- 기존 테스트의 pytest.approx 허용 오차가 반올림으로 인해 실패할 수 있음 → 허용 오차 조정
- chart_data 반올림이 프론트엔드 표시에 영향 → 6자리 정밀도는 시각적 차이 없음

## 8) 메모(Notes)

- QBT 규칙: 가격 6자리, 자본금 정수, 백분율 2자리, 비율 4자리
- "저장/직렬화 직전에만" 원칙 — 내부 연산은 무한 정밀도 유지

### 진행 로그 (KST)

- 2026-04-12 22:30: Plan 작성 완료, 착수
