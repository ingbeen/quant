# Implementation Plan: 백테스트 / 잔여 리터럴 정리 및 중복 제거

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

**작성일**: 2026-04-08 17:00
**마지막 업데이트**: 2026-04-08 17:00
**관련 범위**: backtest, walkforward, portfolio, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] walkforward.py grid_df 접근 시 COL_* 상수 사용 (보고서 3-8)
- [ ] portfolio_engine.py 빈 trades_df 컬럼을 COL_* 상수로 통일 (보고서 2-9)
- [ ] portfolio_execution.py 잔여 리터럴 상수 전환 (보고서 3-7)
- [ ] holding_days 계산 공용 함수 추출 (보고서 3-3)
- [ ] 데이터 로딩 중복 패턴 공용 함수 추출 (보고서 3-5)

## 2) 비목표(Non-Goals)

- _build_execution_comparison_df의 src 이동 (계층 분리는 규모가 커서 별도 작업)
- portfolio_engine.py state_log 중복 해소 (equity_rows와 state_log는 목적이 달라 통합 부적합)
- common_constants.py의 tqqq 전용 상수 이동 (tqqq 도메인 리팩토링 시 처리)
- 비즈니스 로직 변경

## 3) 배경/맥락(Context)

Plan 1(상수화), Plan 2(버그/중복)를 완료한 후 보고서에서 미처리된 잔여 항목을 처리한다.

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] walkforward.py grid_df 접근 COL_* 전환 완료
- [x] portfolio_engine.py 빈 trades_df 컬럼 COL_* 전환 완료
- [x] portfolio_execution.py 잔여 리터럴 전환 완료 (Plan 1에서 대부분 처리됨)
- [x] holding_days 공용 함수 추출 및 호출부 전환 완료
- [x] 데이터 로딩 공용 함수 추출 및 호출부 전환 완료 (load_signal_trade_pair 이미 존재, 호출부 전환)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/walkforward.py` — grid_df COL_* 전환
- `src/qbt/backtest/engines/portfolio_engine.py` — 빈 trades_df 컬럼 상수화
- `src/qbt/backtest/engines/portfolio_execution.py` — 잔여 리터럴 전환
- `src/qbt/backtest/csv_export.py` — holding_days 공용 함수 추가
- `src/qbt/backtest/analysis.py` — holding_days 공용 함수 호출
- `src/qbt/utils/data_loader.py` — load_signal_trade_pair 함수 추가
- `scripts/backtest/run_walkforward.py` — 데이터 로딩 공용 함수 사용
- `scripts/backtest/run_param_plateau_all.py` — 데이터 로딩 공용 함수 사용
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 공용 함수 추출

- [ ] csv_export.py에 `add_holding_days(df)` 공용 함수 추가
- [ ] analysis.py, csv_export.py에서 holding_days 계산을 공용 함수 호출로 전환
- [ ] data_loader.py에 `load_signal_trade_pair(signal_path, trade_path)` 함수 추가
- [ ] run_walkforward.py, run_param_plateau_all.py에서 데이터 로딩을 공용 함수 호출로 전환

---

### Phase 2 — 잔여 리터럴 상수 전환

- [ ] walkforward.py: grid_df 접근 시 `"ma_window"` 등 → `COL_MA_WINDOW` 등
- [ ] portfolio_engine.py: 빈 trades_df 컬럼 목록을 COL_* 상수로 변경
- [ ] portfolio_execution.py: `"asset_id"`, `"trade_type"`, `"pre_shares"` 등 잔여 리터럴 상수화

---

### Phase 3 (마지막) — 최종 검증

- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=499, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. 백테스트 / 잔여 리터럴 상수화 + holding_days/데이터 로딩 공용 함수 추출
2. 백테스트 / 중복 제거 + grid_df/portfolio COL_* 전환
3. 백테스트 / 코드 리뷰 잔여 이슈 전수 처리 (동작 동일)
4. 백테스트 / load_signal_trade_pair + add_holding_days 유틸 추출
5. 백테스트 / 리팩토링 마무리 — 공용 함수 추출 및 리터럴 정리

## 7) 리스크(Risks)

- data_loader.py에 backtest 전용 함수 추가 → 도메인 독립성 위반 여부 확인 필요 (extract_overlap_period이 이미 존재하므로 동일 패턴)

## 8) 메모(Notes)

- holding_days와 hold_days_used는 다른 개념: holding_days = 달력일 (exit-entry), hold_days_used = 전략의 hold_days 파라미터 사용값

### 진행 로그 (KST)

- 2026-04-08 17:00: Plan 작성 완료, 구현 시작
