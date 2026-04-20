# Implementation Plan: 포트폴리오 백테스트 최소 시작일 2005-01-01 하한 적용

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

**작성일**: 2026-04-20 (KST)
**마지막 업데이트**: 2026-04-20 (KST)
**관련 범위**: scripts/backtest
**관련 문서**: [scripts/CLAUDE.md](../../scripts/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 포트폴리오 백테스트의 실험별 시작일에 **2005-01-01 최소 하한**을 적용한다
- [x] 각 실험의 `effective_start_date`가 2005-01-01 이전이라면 2005-01-01로 끌어올려 백테스트한다 (이전 데이터는 스킵)
- [x] QQQ 벤치마크 JSON의 시작일에도 동일한 하한을 적용한다
- [x] 하드코딩 대신 명시적 상수(`DEFAULT_PORTFOLIO_START_DATE`)로 관리한다

## 2) 비목표(Non-Goals)

- `compute_portfolio_effective_start_date` 수정 (자산 교집합 + MA 워밍업 계산은 그대로 유지)
- `run_portfolio_backtest` 엔진 시그니처 변경 (`start_date` 파라미터 그대로 사용)
- 자산별 원본 데이터 파일(`storage/stock/*.csv`) 자체 변경 — 단순히 시작일 하한 필터만 적용
- 워크포워드/단일 백테스트 스크립트에 대한 동일 정책 전파 (포트폴리오 범위 한정)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 각 실험이 자기 자산 조합의 가용 최대 구간(= `compute_portfolio_effective_start_date`)부터 시작함
- 사용자 요청: "2005-01-01부터 시작. 2005년 이전 데이터가 있어도 스킵"
- 이유: 실무상 초기 연도의 데이터 품질/해석 리스크를 제거하고, 모든 실험의 비교 기준을 2005년 이후 장(長) 구간으로 통일

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] 각 실험의 실제 백테스트 시작일이 `max(effective_start_date, DEFAULT_PORTFOLIO_START_DATE)`로 결정
- [x] QQQ 벤치마크 JSON 시작일도 `max(min(effective_start_dates), DEFAULT_PORTFOLIO_START_DATE)`로 결정
- [x] `DEFAULT_PORTFOLIO_START_DATE = date(2005, 1, 1)` 상수가 `run_portfolio_backtest.py` 상단에 정의 (사용 범위 단일 파일 → 로컬 상수 원칙)
- [x] `poetry run python validate_project.py` 통과 (passed=1023, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (변경 파일 포맷 변경 없음)
- [x] 필요한 문서 업데이트: README.md 변경 없음 / `docs/COMMANDS.md` 변경 없음 / `scripts/CLAUDE.md` 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [scripts/backtest/run_portfolio_backtest.py](../../scripts/backtest/run_portfolio_backtest.py)
  - 상단에 `DEFAULT_PORTFOLIO_START_DATE = date(2005, 1, 1)` 로컬 상수 추가 (이미 `date` import 있음)
  - `main()`에서 실험별 `exp_start_date = max(effective_start_dates[name], DEFAULT_PORTFOLIO_START_DATE)`
  - `main()`에서 QQQ 벤치마크용 `benchmark_start_date = max(min(effective_start_dates.values()), DEFAULT_PORTFOLIO_START_DATE)`
  - 관련 DEBUG 로그 업데이트 (하한 적용 사실 투명화)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): `run_portfolio_backtest.py` 설명에 "2005-01-01 하한 정책" 한 줄 추가
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어/CLI 옵션 동일)

### 데이터/결과 영향

- 출력 스키마: 변경 없음
- 결과 값: 실험별 시작일이 2005-01-01 이후로 이동할 수 있어 성과 지표가 이전 결과와 달라질 수 있음
- QQQ 벤치마크 JSON: `start_date` 값이 하한 적용 후로 이동, `yearly_returns` 범위 축소 가능

## 6) 단계별 계획(Phases)

### Phase 1 — `run_portfolio_backtest.py` 수정

**작업 내용**:

- [x] 상단에 `DEFAULT_PORTFOLIO_START_DATE: date = date(2005, 1, 1)` 상수 정의 (의미를 설명하는 한 줄 주석 포함)
- [x] `main()`의 실험별 시작일 결정부에 `max(..., DEFAULT_PORTFOLIO_START_DATE)` 적용
- [x] QQQ 벤치마크 전달값도 동일한 하한 적용
- [x] 로깅: 하한 적용 전/후 값을 DEBUG 로그에 명시

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [scripts/CLAUDE.md](../../scripts/CLAUDE.md)의 `run_portfolio_backtest.py` 설명에 2005-01-01 하한 정책 문구 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1023, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실행 시작일에 2005-01-01 최소 하한 적용
2. 백테스트 / run_portfolio_backtest 2005-01-01 하한 + QQQ 벤치마크 동기화
3. 백테스트 / 포트폴리오 시작일 상수 도입(DEFAULT_PORTFOLIO_START_DATE=2005-01-01)
4. 백테스트 / 포트폴리오 초기 구간(≤2004) 제외 — 공통 최소 시작일 고정
5. 백테스트 / 포트폴리오 실행 정책: 실험별 시작일에 2005-01-01 floor 도입

## 7) 리스크(Risks)

- 데이터가 2005 이전부터 있는 실험(예: D-1 QQQ는 1999부터)이 2005년으로 축소되어 성과 지표가 달라짐 → 의도된 변경이므로 위험 아님
- 2005-01-01 이 거래일이 아닐 경우 `mask_t = tdf[COL_DATE] >= start_date` 필터에서 2005-01-03(월)부터 자연 편입 → 엔진이 이미 처리하므로 추가 작업 불요

## 8) 메모(Notes)

- 사용 범위 판정: `DEFAULT_PORTFOLIO_START_DATE`는 현재 `run_portfolio_backtest.py` 1개 파일에서만 사용 → 루트 CLAUDE.md의 상수 3계층 규칙에 따라 **로컬 상수**로 배치. 향후 다른 스크립트/도메인에서도 쓰이면 `backtest/constants.py` 또는 `common_constants.py`로 승격.
- 기존 저장 결과 디렉토리는 자동으로 덮어쓰기됨 (실험 이름이 유지되므로).

### 진행 로그 (KST)

- 2026-04-20: 계획서 작성 및 In Progress 시작
- 2026-04-20: Phase 1 구현 완료 — `DEFAULT_PORTFOLIO_START_DATE` 상수 추가, 실험별 `max(...)` 및 QQQ 벤치마크 동일 하한 적용
- 2026-04-20: scripts/CLAUDE.md에 2005-01-01 하한 정책 문구 추가
- 2026-04-20: `validate_project.py` 통과 (passed=1023, failed=0, skipped=0). 상태 → Done
