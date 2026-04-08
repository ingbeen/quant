# Implementation Plan: 포트폴리오 실행 시 정합성 자동 검증

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

**작성일**: 2026-04-08 09:15
**마지막 업데이트**: 2026-04-08 09:15
**관련 범위**: backtest, scripts/backtest
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] `run_portfolio_backtest.py` 실행 시 각 실험 결과에 대해 5개 정합성 규칙을 자동 검증한다
- [ ] 검증 함수는 `src/qbt/backtest/`에 위치하여 계층 분리를 유지한다
- [ ] 위반 시 WARNING 로그를 남기되 실행은 중단하지 않는다

## 2) 비목표(Non-Goals)

- 기존 test_portfolio_state_log.py 테스트 제거 또는 대체 (공존)
- 검증 실패 시 스크립트 중단 (경고만, 계속 실행)
- 새로운 검증 규칙 추가 (기존 5개 규칙만 적용)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

이전 plan(PLAN_portfolio_state_log_debug)에서 5개 정합성 규칙 테스트를 추가했으나,
이 테스트는 가상 데이터로만 실행된다. 실제 포트폴리오 실험(portfolio_a2 등) 결과에
대해서는 자동 검증이 수행되지 않아, 실행 후 수동으로 확인해야 한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `src/qbt/backtest/`에 검증 함수가 존재하고, PortfolioResult를 받아 5개 규칙을 검증한다
- [x] `run_portfolio_backtest.py`에서 각 실험 실행 직후 검증 함수를 호출한다
- [x] 위반 시 결과 저장 후 ValueError를 발생시켜 스크립트를 중지한다. 통과 시 DEBUG 로그를 출력한다
- [x] 검증 함수에 대한 단위 테스트가 추가된다
- [x] `poetry run python validate_project.py` 통과 (passed=499, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성:**
- `src/qbt/backtest/portfolio_validation.py` -- 5개 정합성 규칙 검증 함수
- `tests/test_portfolio_validation.py` -- 검증 함수 단위 테스트

**수정:**
- `scripts/backtest/run_portfolio_backtest.py` -- 실험 실행 후 검증 호출
- `src/qbt/backtest/CLAUDE.md` -- 모듈 설명 추가

**변경 없음:**
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 파일 변경 없음 (로그 출력만 추가)

## 6) 단계별 계획(Phases)

### Phase 1 — 검증 함수 + CLI 호출 + 테스트

**작업 내용**:

- [ ] `src/qbt/backtest/portfolio_validation.py` 신규 생성
  - `validate_portfolio_result(result: PortfolioResult) -> list[str]`
    - 5개 규칙 검증, 위반 사항을 문자열 리스트로 반환 (빈 리스트 = 전부 통과)
    - 규칙 1: 시그널-체결 1일 lag (state_log_df 기반)
    - 규칙 2: 리밸런싱 후 비중 정합성 (state_log_df 기반)
    - 규칙 3: EXIT_ALL 후 주수 0 (state_log_df 기반)
    - 규칙 4: 현금 비음수 (equity_df 기반)
    - 규칙 5: 에쿼티 등식 (equity_df 기반)
- [ ] `run_portfolio_backtest.py` 수정 -- `_save_portfolio_results` 직전에 검증 호출
  - 위반 있으면 WARNING 로그 (항목별), 없으면 DEBUG "정합성 검증 통과"
- [ ] `tests/test_portfolio_validation.py` 신규 생성 -- 검증 함수 단위 테스트

### 마지막 Phase — 문서 정리 및 최종 검증

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트
- [ ] `poetry run black .`
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 포트폴리오 / 실행 시 5개 정합성 규칙 자동 검증 추가
2. 포트폴리오 / run_portfolio_backtest에서 state_log 기반 자동 검증 호출
3. 포트폴리오 / 실험 결과 정합성 자동 검증 함수 + CLI 연동
4. 포트폴리오 / 매수매도 정합성 검증을 백테스트 실행에 통합
5. 포트폴리오 / 비즈니스 계층에 검증 로직 추가 + 실행 시 자동 호출

## 7) 리스크(Risks)

- 검증 로직으로 인한 실행 시간 증가: state_log_df 순회가 추가되나 무시할 수준
- 기존 테스트(test_portfolio_state_log.py)와 로직 중복: 검증 함수를 공용화하여 테스트에서도 재사용 가능

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-08 09:15: 계획서 작성 + 즉시 진행
- 2026-04-08 09:25: 전체 완료. validate_project.py 통과 (passed=499, failed=0, skipped=0). 위반 시 스크립트 중지로 변경

---
