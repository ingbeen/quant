# Implementation Plan: live 비즈니스 로직 오류 + fail-fast 누락 수정

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

**작성일**: 2026-04-12 22:00
**마지막 업데이트**: 2026-04-12 22:00
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

- [x] daily_runner.py 의 intent → signal 매핑에서 INCREASE_TO_TARGET / REDUCE_TO_TARGET 누락 수정
- [x] 내부 불변조건 위반인데 ValueError 를 사용하는 곳을 RuntimeError 로 교체
- [x] 검증 없이 암묵적 가정에 의존하는 곳에 명시적 검증 추가
- [x] drift.py 의 model_equity ≤ 0 fallback 을 RuntimeError 로 교체
- [x] history.py 의 JSONL 파싱 실패를 RuntimeError 로 명시화

## 2) 비목표(Non-Goals)

- 소수점 반올림 (Plan 2 에서 처리)
- 상수화 / 주석 정리 (Plan 3 에서 처리)
- cli.py `_cmd_run_daily` 함수 분리 (현행 유지)
- state.py required fields 자동 생성 (현행 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **intent 매핑 누락 (심각)**: `daily_runner.py` 의 `_build_signal_detections()` 와 signal_state 갱신 로직이
   `ENTER_TO_TARGET` / `EXIT_ALL` 만 인식. `INCREASE_TO_TARGET` (비중 증가 매수) / `REDUCE_TO_TARGET`
   (비중 감소 매도) 를 무시하여 알림에 "신호 없음" 표시, 원장의 signal_state 미갱신.

2. **ValueError vs RuntimeError 혼용**: `_find_trade_index()` 는 내부 전용 함수이며 trade_date 가 trade_df 에
   없는 것은 내부 불변조건 위반인데 ValueError 로 처리.

3. **trade_df 날짜 동일성 미검증**: 모든 자산의 trade_df 가 동일 날짜 집합이라 가정하나 검증 없음.

4. **drift model_equity fallback**: `model_equity ≤ 0` 일 때 drift_ratio = 0.0 으로 silently fallback.
   초기 자본이 항상 양수이고 전략이 전량 매도해도 현금이 남으므로 도달 불가능 조건.

5. **history.py JSONL 손상**: `json.loads(line)` 실패 시 JSONDecodeError 가 무방비 전파.
   데이터 무결성 최우선 원칙에 따라 RuntimeError 로 명시화.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `live/CLAUDE.md`
- `tests/CLAUDE.md`
- 루트 `CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `_build_signal_detections` 에서 BUY_INTENT_TYPES / SELL_INTENT_TYPES 기반 매핑
- [x] signal_state 갱신 로직: EXIT_ALL/ENTER_TO_TARGET 만 전환 (REDUCE/INCREASE 는 유지) — 포지션 보유 여부 원장이므로 정확
- [x] `_find_trade_index` 의 ValueError → RuntimeError 교체
- [x] trade_df 날짜 집합 동일성 검증 추가
- [x] `drift.py` model_equity ≤ 0 → RuntimeError
- [x] `history.py` JSONL 파싱 실패 → RuntimeError
- [x] 각 수정에 대한 테스트 추가/수정
- [x] `poetry run python validate_project.py` 통과 (passed=889, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `live/src/live/daily_runner.py`
- `live/src/live/drift.py`
- `live/src/live/history.py`
- `live/tests/test_daily_runner.py`
- `live/tests/test_drift.py`
- `live/tests/test_history.py`
- `README.md`: 변경 없음

### 데이터/결과 영향

- 기존 정상 흐름에서 동작 변경 없음 (도달 불가능 분기의 에러 처리 변경)
- INCREASE_TO_TARGET / REDUCE_TO_TARGET intent 가 발생하는 경우에만 알림/원장 동작이 달라짐

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트로 정책 고정 (레드)

**작업 내용**:

- [x] `test_daily_runner.py`: INCREASE_TO_TARGET → SignalDetection.state == "buy" 테스트
- [x] `test_daily_runner.py`: REDUCE_TO_TARGET → SignalDetection.state == "sell" 테스트
- [x] `test_daily_runner.py`: INCREASE/REDUCE intent 시 signal_state 갱신 테스트
- [x] `test_daily_runner.py`: trade_df 날짜 불일치 시 RuntimeError 테스트
- [x] `test_drift.py`: model_equity ≤ 0 시 RuntimeError 테스트
- [x] `test_history.py`: JSONL 손상 행 시 RuntimeError 테스트

---

### Phase 1 — 구현 수정 (그린)

**작업 내용**:

- [x] `daily_runner.py` `_build_signal_detections`: BUY_INTENT_TYPES / SELL_INTENT_TYPES 사용
- [x] `daily_runner.py` signal_state 갱신: 동일하게 상수 기반 매핑
- [x] `daily_runner.py` `_find_trade_index`: ValueError → RuntimeError
- [x] `daily_runner.py` trade_df 날짜 동일성 검증 추가
- [x] `drift.py` `compute_drift`: model_equity ≤ 0 → RuntimeError
- [x] `history.py` `load_user_trades` / `load_signal_history`: json.loads 실패 → RuntimeError

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=889, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. live / intent 매핑 누락 수정 + fail-fast 정책 보강
2. live / BUY/SELL_INTENT_TYPES 기반 신호 매핑 통일 및 불변조건 검증 강화
3. live / daily_runner signal 감지 버그 수정 + RuntimeError 전환
4. live / INCREASE/REDUCE intent 누락 수정 및 내부 불변조건 fail-fast 적용
5. live / 비즈니스 로직 오류 수정 + 불가능 조건 RuntimeError 전환

## 7) 리스크(Risks)

- `model_equity ≤ 0` RuntimeError 가 예상치 못한 정상 케이스를 중단시킬 가능성 → 초기 자본 양수 + 강제 청산 없음 원칙으로 도달 불가 확인 완료
- history.py RuntimeError 가 손상된 JSONL 로 run-daily 실패 유발 → 히스토리 파일이 run_daily 핵심 경로에서 사용되지 않음을 확인 필요

## 8) 메모(Notes)

- `BUY_INTENT_TYPES = {"ENTER_TO_TARGET", "INCREASE_TO_TARGET"}` 이미 constants.py 에 정의됨
- `SELL_INTENT_TYPES = {"EXIT_ALL", "REDUCE_TO_TARGET"}` 이미 constants.py 에 정의됨
- history.py 의 load 함수는 cli.py 의 `_persist_history` / `_cmd_history` 에서 호출되며, run_daily 순수 계산 경로와 독립

### 진행 로그 (KST)

- 2026-04-12 22:00: Plan 작성 완료, 착수
