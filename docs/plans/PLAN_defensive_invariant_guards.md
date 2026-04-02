# Implementation Plan: 구조적 불변조건 방어 코드 추가

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

**작성일**: 2026-04-02 15:30
**마지막 업데이트**: 2026-04-02 16:00
**관련 범위**: backtest (engine_common, analysis), tqqq (simulation)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `simulation.py`의 누적수익률/종가 상대차이 계산에서 분모 0 방어 (ValueError)
- [x] `engine_common.py`의 `execute_sell_order`에서 entry_price 불변조건 위반 방어 (RuntimeError)
- [x] `analysis.py`의 `calculate_summary`에서 빈 equity_df 반환 시 start_date/end_date 키 보장

## 2) 비목표(Non-Goals)

- walkforward.py의 window_idx dead code 제거 (별도 작업)
- CAGR 문서 모호성 수정 (별도 작업)
- 리팩토링 항목 (상수화, 벡터화, 함수 추출 등)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

전략 검증 보고서 코드 리뷰에서 3건의 잠재적 결함이 확인되었다:

1. **simulation.py:745,752** — `actual_cumulative` 또는 `final_close_actual`이 0일 때 ZeroDivisionError 발생 가능. 입력 데이터 조건에 의한 문제이므로 ValueError로 즉시 중단하여 사용자에게 인지시킨다.

2. **engine_common.py:141** — `execute_sell_order`에서 `entry_price`가 0이면 ZeroDivisionError. 구조적으로 `execute_buy_order`를 통해서만 설정되므로 0이 될 수 없으나, 명시적 불변조건 방어(RuntimeError)가 없다.

3. **analysis.py:152-165** — `equity_df.empty`일 때 반환하는 딕셔너리에 `start_date`, `end_date` 키가 없어 다운스트림에서 접근 시 KeyError 위험.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `simulation.py`: 분모 0 시 ValueError 발생
- [x] `engine_common.py`: entry_price <= 0 시 RuntimeError 발생
- [x] `analysis.py`: 빈 equity_df 반환에 start_date/end_date 키 포함
- [x] 회귀/신규 테스트 추가 (3건 각각 최소 1개)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=470, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트: README.md 변경 없음
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/simulation.py` — 분모 0 검증 추가 (745행, 752행)
- `src/qbt/backtest/engines/engine_common.py` — entry_price 불변조건 검증 추가 (141행 전)
- `src/qbt/backtest/analysis.py` — 빈 equity_df 반환에 키 추가 (152-165행)
- `tests/test_tqqq_simulation_outputs.py` — 분모 0 테스트 추가
- `tests/test_engine_common.py` — entry_price=0 테스트 추가
- `tests/test_analysis.py` — 빈 equity_df 키 테스트 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 스키마 변경: `calculate_summary` 빈 반환에 `start_date`, `end_date` 키 추가 (기존 소비자에 영향 없음 — 키가 추가되는 것이므로 하위 호환)
- 기존 결과 비교: 불필요 (정상 경로 동작 변경 없음)

## 6) 단계별 계획(Phases)

### Phase 0 — 불변조건 테스트 먼저 고정 (레드)

**작업 내용**:

- [x] `tests/test_tqqq_simulation_outputs.py`: `actual_cumulative=0` 시 ValueError 발생 테스트 추가
- [x] `tests/test_tqqq_simulation_outputs.py`: `final_close_actual=0` 시 ValueError 발생 테스트 추가
- [x] `tests/test_engine_common.py`: `execute_sell_order(100.0, 10, 0.0)` 호출 시 RuntimeError 발생 테스트 추가
- [x] `tests/test_analysis.py`: 빈 equity_df 반환에 `start_date`, `end_date` 키 존재 테스트 추가

---

### Phase 1 — 방어 코드 구현 (그린)

**작업 내용**:

- [x] `src/qbt/tqqq/simulation.py:745` 전: `actual_cumulative` 0 검증 + ValueError
- [x] `src/qbt/tqqq/simulation.py:752` 전: `final_close_actual` 0 검증 + ValueError
- [x] `src/qbt/backtest/engines/engine_common.py:141` 전: `entry_price <= 0` 검증 + RuntimeError
- [x] `src/qbt/backtest/analysis.py:152-165`: 빈 반환 딕셔너리에 `"start_date": None`, `"end_date": None` 추가

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=470, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 버그수정 / 구조적 불변조건 방어 코드 추가 (simulation, engine_common, analysis)
2. 버그수정 / 분모 0 방어 + entry_price 불변조건 + 빈 equity_df 키 보장
3. 안정성 / 잠재적 ZeroDivision 3건 방어 코드 및 테스트 추가
4. 백테스트+TQQQ / 구조적 불변조건 위반 시 즉시 중단 로직 추가
5. 방어코드 / simulation·engine_common·analysis 불변조건 가드 + 테스트

## 7) 리스크(Risks)

- `calculate_summary` 빈 반환에 `start_date: None` 추가 시, 다운스트림에서 `None`을 처리하지 않는 코드가 있을 수 있음 → `NotRequired` 타입이므로 기존 접근 패턴은 동일하게 동작 (키 존재만 보장)
- `execute_sell_order`에 RuntimeError 추가 시, 혹시 entry_price=0으로 호출하는 테스트가 있으면 실패 → 기존 테스트 확인 완료, entry_price=0 테스트 없음

## 8) 메모(Notes)

- 발견 경위: `docs/strategy_validation_report.md` 기반 코드 리뷰에서 도출
- entry_price=0은 구조적으로 불가능 (execute_buy_order → buy_price = open_price * (1+slippage) > 0) 하지만 방어적 프로그래밍 원칙에 따라 RuntimeError 추가
- actual_cumulative=0은 실제 TQQQ 데이터에서 극히 드물지만 이론적으로 가능 → ValueError

### 진행 로그 (KST)

- 2026-04-02 15:30: 계획서 작성
- 2026-04-02 16:00: Phase 0~2 완료, validate_project.py 통과 (470 passed, 0 failed, 0 skipped)

---
