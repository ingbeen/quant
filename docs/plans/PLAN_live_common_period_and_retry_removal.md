# Implementation Plan: live / market_bundle 공통 기간 필터링 + CI 재시도 제거

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

**작성일**: 2026-04-12 19:30
**마지막 업데이트**: 2026-04-12 19:40
**관련 범위**: live, CI/CD
**관련 문서**: `src/live/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `_build_market_bundle()`에서 전 자산 trade_df 날짜 교집합 필터링 추가 (QBT 포트폴리오 엔진과 동일 패턴)
- [x] `daily_run.yml`의 재시도 로직 (5분 대기 + 2차 시도) 제거
- [x] 공통 기간 필터링 검증 테스트 추가

## 2) 비목표(Non-Goals)

- `_validate_trade_date_alignment` 검증 로직 자체의 변경 (검증은 정상 작동 중, 데이터 준비 단계의 문제)
- keepalive.yml 변경 (재시도 로직 없음)
- `daily_runner.py` 변경 (순수 계산 레이어는 변경 불필요)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**버그**: `_build_market_bundle()` (cli.py)이 각 자산의 CSV를 독립적으로 로드하여 서로 다른 날짜 범위의 trade_df를 생성한다. 예: SSO(2006-06-21~)와 GLD(2004-11-18~)는 시작일이 다르므로 `_validate_trade_date_alignment`에서 RuntimeError 발생.

**QBT 포트폴리오 엔진의 해법**: `_load_portfolio_data_with_common_period()` (portfolio_engine.py:111-129)에서 모든 자산의 trade_df 날짜 교집합을 계산하고 공통 기간으로 필터링한다. live의 `_build_market_bundle`에는 이 단계가 누락되어 있다.

**CI 재시도 로직**: `daily_run.yml`에 1차 실패 시 5분 대기 후 2차 재시도하는 로직이 있다. live 도메인의 핵심 원칙 "장애 시 자동 복구 금지"에 따라 제거 요청됨.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/live/CLAUDE.md`: live 도메인 규칙 (QBT 본체 수정 금지, 순수 계산/I/O 분리 등)
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `_build_market_bundle()`이 전 자산 trade_df/signal_df를 공통 날짜 교집합으로 필터링
- [x] 서로 다른 날짜 범위를 가진 자산들로 `run_daily` 정상 실행 가능
- [x] `daily_run.yml`에서 재시도 로직 (1차/2차 구분, sleep, continue-on-error) 제거
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/cli.py`: `_build_market_bundle()` 공통 기간 필터링 추가
- `tests/live/test_cli.py`: 공통 기간 필터링 테스트 추가
- `.github/workflows/daily_run.yml`: 재시도 로직 제거
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 스키마 변경 없음
- trade_df/signal_df가 공통 기간으로 잘리므로 인덱스 정합성 보장

## 6) 단계별 계획(Phases)

### Phase 1 — 핵심 구현 (그린 유지)

**작업 내용**:

- [x] `src/live/cli.py`의 `_build_market_bundle()`에 공통 기간 필터링 로직 추가
  - 모든 자산 로드 후 trade_df 날짜 교집합 계산
  - 교집합으로 signal_df, trade_df 필터링 + reset_index
  - QBT `_load_portfolio_data_with_common_period` 패턴 참고
- [x] `tests/live/test_cli.py`에 공통 기간 필터링 테스트 추가
  - 서로 다른 날짜 범위의 자산 2개로 bundle 생성 시 공통 기간 정렬 검증

---

### Phase 2 — CI 재시도 로직 제거 (그린 유지)

**작업 내용**:

- [x] `.github/workflows/daily_run.yml`에서 재시도 관련 step 제거
  - `run_first` step의 `continue-on-error: true` 제거 + id/name 정리
  - "Wait 5 minutes before retry" step 삭제
  - "Run live.cli run-daily (2차 재시도)" step 삭제

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=896, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / market_bundle 공통 기간 필터링 추가 + CI 재시도 제거
2. live / trade_df 날짜 정렬 버그 수정 + daily_run 재시도 로직 제거
3. live / _build_market_bundle 공통 기간 필터링 + workflow 단순화
4. live / 자산 간 trade_df 날짜 교집합 필터링 누락 수정 + CI 정리
5. live / QBT 포트폴리오 엔진 패턴 적용(공통 기간) + 재시도 제거

## 7) 리스크(Risks)

- 공통 기간 필터링으로 일부 자산의 초기 데이터가 잘리지만, live 실행에서는 최근 trade_date만 사용하므로 영향 없음
- signal_df 필터링 시 EMA 계산이 이미 완료된 상태이므로 EMA 값 자체는 영향 없음 (MA는 필터링 전에 계산됨)

## 8) 메모(Notes)

- keepalive.yml에는 재시도 로직이 존재하지 않으므로 변경 불필요
- QBT 포트폴리오 엔진 참고 위치: `src/qbt/backtest/engines/portfolio_engine.py:111-129`

### 진행 로그 (KST)

- 2026-04-12 19:30: 계획서 작성
- 2026-04-12 19:40: 전체 Phase 완료, validate_project.py 통과 (896 passed, 0 failed, 0 skipped)
