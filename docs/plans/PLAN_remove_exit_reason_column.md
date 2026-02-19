# Implementation Plan: exit_reason 컬럼 제거

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

**작성일**: 2026-02-19 21:10
**마지막 업데이트**: 2026-02-19 21:10
**관련 범위**: backtest, scripts
**관련 문서**: `CLAUDE.md` (루트), `src/qbt/backtest/CLAUDE.md`

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

- [x] `exit_reason` 필드를 전체 파이프라인에서 제거 (타입 → 전략 → CLI → 대시보드 → 문서)

## 2) 비목표(Non-Goals)

- 새로운 매도 사유 메커니즘 추가 (향후 필요 시 재도입)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `exit_reason`은 `_execute_sell_order()`에서 `"signal"`로 하드코딩
- 매도 경로가 신호(하향돌파) 한 가지뿐이고 강제청산도 없으므로 항상 동일한 값
- 불변 값 컬럼은 정보 가치가 없으므로 제거

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `TradeRecord` TypedDict에서 `exit_reason` 필드 제거
- [x] `_execute_sell_order()`에서 `exit_reason` 생성 제거
- [x] CLI 테이블 출력에서 사유 컬럼 제거
- [x] 대시보드 컬럼 매핑에서 `exit_reason` 제거
- [x] `backtest_strategy_architecture.md`에서 `exit_reason` 행 제거
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/types.py`: `TradeRecord`에서 `exit_reason: str` 제거
- `src/qbt/backtest/strategy.py`: `_execute_sell_order()`에서 `"exit_reason": "signal"` 제거
- `scripts/backtest/run_single_backtest.py`: CLI 테이블 출력에서 사유 컬럼 제거
- `scripts/backtest/app_single_backtest.py`: `TRADE_COLUMN_RENAME`에서 `exit_reason` 제거
- `backtest_strategy_architecture.md`: exit_reason 행 제거

### 데이터/결과 영향

- trades CSV에서 `exit_reason` 컬럼 사라짐 (스크립트 재실행 시)

## 6) 단계별 계획(Phases)

### Phase 1 — exit_reason 제거

**작업 내용**:

- [x] `types.py`: `TradeRecord`에서 `exit_reason: str` 제거
- [x] `strategy.py`: `_execute_sell_order()`에서 `"exit_reason": "signal",` 제거
- [x] `run_single_backtest.py`: CLI 테이블 출력에서 사유 컬럼 제거
- [x] `app_single_backtest.py`: `TRADE_COLUMN_RENAME`에서 `"exit_reason": "청산사유",` 제거
- [x] `backtest_strategy_architecture.md`: exit_reason 행 제거

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=287, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / exit_reason 불변 컬럼 제거 (항상 "signal"이므로 정보 가치 없음)
2. 백테스트 / trades 결과에서 exit_reason 컬럼 제거
3. 백테스트 / 불필요한 exit_reason 필드 전체 파이프라인에서 정리
4. 백테스트 / TradeRecord에서 exit_reason 제거 (단일 매도 경로)
5. 백테스트 / 거래 내역 exit_reason 컬럼 삭제 및 관련 코드 정리

## 7) 리스크(Risks)

- 낮음: 테스트에서 exit_reason 참조 없음 (grep 확인 완료)
- 낮음: 하드코딩 불변값 제거이므로 로직 변경 없음

## 8) 메모(Notes)

- 향후 stop-loss, trailing stop 등 새로운 매도 메커니즘 추가 시 재도입 가능

### 진행 로그 (KST)

- 2026-02-19 21:10: 계획서 작성
- 2026-02-19 21:12: Phase 1 완료 (5곳 제거)
- 2026-02-19 21:12: 최종 검증 통과 (passed=287, failed=0, skipped=0), Done
