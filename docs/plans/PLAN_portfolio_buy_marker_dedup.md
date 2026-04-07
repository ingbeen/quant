# Implementation Plan: 포트폴리오 대시보드 Buy 마커 중복 표출 수정

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

**작성일**: 2026-04-07 18:00
**마지막 업데이트**: 2026-04-07 18:05
**관련 범위**: scripts/backtest (대시보드 시각화)
**관련 문서**: scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md

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

- [x] 분할 매도 시 동일 entry_date에 대해 Buy 마커가 중복 표출되는 문제 해결
- [x] 하나의 진입(매수) 이벤트에 대해 차트에 Buy 마커가 1회만 표시되도록 수정

## 2) 비목표(Non-Goals)

- trades.csv 데이터 구조 변경 (entry_date 반복 기록은 거래 이력 추적 관점에서 올바른 설계)
- 포트폴리오 엔진(portfolio_execution.py) 로직 변경
- Sell 마커 표출 방식 변경 (각 매도 체결은 개별 이벤트이므로 현행 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 포트폴리오 백테스트에서 한 번 매수 후 분할 매도(리밸런싱 등)가 발생하면, trades.csv에 동일한 entry_date를 가진 행이 여러 개 생성된다.
  - 예: SPY 2012-01-09 진입 → 7개 행(리밸런싱 6회 + 시그널 매도 1회)이 동일 entry_date 보유
- `_build_portfolio_markers()` 함수가 모든 거래 행을 순회하며 entry_date마다 Buy 마커를 생성하므로, 같은 날에 Buy 마커가 여러 개 중첩 표출된다.
- 이는 차트 가독성을 크게 저하시킨다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md` (CLI 스크립트 계층 규칙)
- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `_build_portfolio_markers()`에서 동일 자산의 동일 entry_date에 대해 Buy 마커가 1회만 생성됨
- [x] 기존 Sell 마커 동작에 영향 없음
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_portfolio_backtest.py`: `_build_portfolio_markers()` 함수 수정
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 스키마 변경 없음 (시각화 로직만 수정)
- trades.csv, equity.csv 등 결과 파일 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — Buy 마커 중복 제거 구현 + 최종 검증

**작업 내용**:

- [x] `_build_portfolio_markers()` 함수에서 `seen_entry_dates: set[str]`를 사용하여 동일 entry_date의 Buy 마커 중복 생성 방지
- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행

**Validation**:

- [x] `poetry run python validate_project.py` (passed=483, failed=0, skipped=0)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 포트폴리오 대시보드 / 분할매도 시 Buy 마커 중복 표출 수정
2. 포트폴리오 대시보드 / 시그널 차트 Buy 마커 entry_date 중복 제거
3. 포트폴리오 대시보드 / 동일 진입일 Buy 마커가 1회만 표시되도록 수정
4. 포트폴리오 대시보드 / _build_portfolio_markers 중복 Buy 마커 필터링 추가
5. 포트폴리오 대시보드 / 분할매도 거래의 Buy 마커 중첩 문제 해결

## 7) 리스크(Risks)

- 리스크 낮음: 시각화 로직만 변경하므로 데이터/엔진에 영향 없음
- INCREASE_TO_TARGET(추가매수)으로 같은 날짜에 재진입하는 경우 Buy 마커가 1개로 합쳐질 수 있으나, 현실적으로 발생 빈도가 극히 낮음

## 8) 메모(Notes)

- 방안 선택: 시각화 레벨에서 entry_date 중복 제거 (방안 1)
- trades.csv의 entry_date 반복 기록은 데이터 모델 관점에서 올바르므로 변경하지 않음

### 진행 로그 (KST)

- 2026-04-07 18:00: 계획서 작성 완료, 구현 착수
- 2026-04-07 18:05: 구현 완료, validate_project.py 통과 (passed=483, failed=0, skipped=0)

---
