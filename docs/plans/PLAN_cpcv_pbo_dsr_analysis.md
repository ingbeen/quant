# Implementation Plan: CSCV/PBO/DSR 과최적화 통계 검증

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

**작성일**: 2026-02-27 21:00
**마지막 업데이트**: 2026-02-28 01:30
**관련 범위**: backtest, scripts, tests
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

- [x] CSCV (Combinatorial Symmetric Cross-Validation) 기반 PBO 계산 모듈 구현
- [x] DSR (Deflated Sharpe Ratio) 계산 모듈 구현
- [x] buffer_zone_atr_tqqq 전략의 1,728개 파라미터 조합에 대한 과최적화 통계 검증 CLI 제공
- [x] 성공 기준: PBO < 0.5, DSR > 0.95 (5% 유의수준)

## 2) 비목표(Non-Goals)

- CPCV (Combinatorial Purged Cross-Validation)의 purging/embargo 구현 (백테스트 파라미터 검증에 CSCV로 충분)
- scipy 외부 의존성 추가 (math.erf + Acklam 근사로 대체)
- Sharpe ratio를 기존 SummaryDict에 영구 추가 (cpcv.py에서 자체 계산)
- 기존 WFO 파이프라인(walkforward.py) 변경
- 대시보드 시각화 (JSON/CSV 결과만 제공)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- buffer_zone_atr_tqqq 전략 WFO에서 1,728개 파라미터 조합을 탐색하고 있다
- 기존 과최적화 진단(WFE, Gap Calmar, Profit Concentration)은 정성적 판단에 의존
- 1,728번 시도 시 "우연히" 높은 성과가 나올 확률이 높음 (다중검정 문제)
- CSCV/PBO/DSR은 동일 문제에 대한 통계적 정량 검증을 제공:
  - PBO: "IS 최적 전략이 OOS에서 중간 이하일 확률" → 과최적화 확률 정량화
  - DSR: "다중 시행 보정 Sharpe Ratio의 통계적 유의성" → 다중검정 보정

### CSCV vs CPCV 명칭

improvement_log에서는 "CPCV·PBO·DSR"로 표기하나, 구현하는 알고리즘은 Bailey et al. (2017)의 CSCV이다.
CPCV(Lopez de Prado 2018)는 purging/embargo 추가한 확장이나, 백테스트 파라미터 검증에는 CSCV로 충분하다.
코드 명칭은 `cscv`를 사용하되, 사용자 대면 문서에서는 기존 "CPCV·PBO·DSR"을 유지한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 상수 관리 3계층, 타입 힌트, 비율 표기, 반올림, 로깅
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (계층 분리, 예외 처리, 메타데이터)
- `tests/CLAUDE.md`: Given-When-Then, 결정적 테스트, 부동소수점 비교
- `src/qbt/utils/CLAUDE.md`: 병렬 처리 패턴

## 4) 완료 조건(Definition of Done)

- [x] PBO 계산 모듈 (`cpcv.py`) 구현 및 테스트 통과
- [x] DSR 계산 모듈 (`cpcv.py`) 구현 및 테스트 통과
- [x] 수익률 행렬 구축 (병렬 실행) 구현 및 테스트 통과
- [x] CLI 스크립트 (`run_cpcv_analysis.py`) 구현
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=397, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (CLAUDE.md 4개)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 신규 파일

- `src/qbt/backtest/cpcv.py` -- CSCV 분할, PBO, DSR, 수익률 행렬 구축
- `scripts/backtest/run_cpcv_analysis.py` -- CLI 스크립트
- `tests/test_cpcv.py` -- 단위 테스트

### 수정 파일

- `src/qbt/backtest/types.py` -- PboResultDict, DsrResultDict, CscvAnalysisResultDict TypedDict 추가
- `src/qbt/backtest/constants.py` -- DEFAULT_CSCV_N_BLOCKS, 파일명 상수 추가
- `src/qbt/backtest/CLAUDE.md` -- cpcv.py 모듈 문서화
- `CLAUDE.md` (루트) -- 디렉토리 구조 + 결과 파일 추가
- `scripts/CLAUDE.md` -- run_cpcv_analysis.py 문서화
- `tests/CLAUDE.md` -- test_cpcv.py 추가

### 미수정 (기존 로직 변경 없음)

- `analysis.py`, `walkforward.py`, `buffer_zone_helpers.py` -- 모두 그대로

### 데이터/결과 영향

- 기존 결과 파일 변경 없음
- 신규 결과 파일 추가:
  - `storage/results/backtest/{strategy_name}/cscv_analysis.json` -- PBO, DSR 요약
  - `storage/results/backtest/{strategy_name}/cscv_logit_lambdas.csv` -- logit lambda 분포

## 6) 단계별 계획(Phases)

### Phase 0 — 핵심 인바리언트 테스트 (Red)

핵심 수학 함수와 알고리즘의 정확성을 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `tests/test_cpcv.py` 작성:
  - TestNormFunctions: norm_cdf/ppf 수학적 정확성 (알려진 값, 왕복 검증)
  - TestLogit: logit(0.5)=0, 경계 조건
  - TestGenerateCscvSplits: C(6,3)=20, 대칭성, 블록 커버리지, 홀수 블록 ValueError
  - TestComputeSharpe: zero std, 양수 수익률, annualization
  - TestComputeCalmar: 수익률에서 Calmar 계산, MDD=0 처리
  - TestPboCalculation: 랜덤 전략 PBO ~0.5, 지배 전략 PBO ~0.0, 범위 0~1
  - TestDsrCalculation: DSR 범위 0~1, n_trials 효과

---

### Phase 1 — 핵심 모듈 구현 (Green)

types/constants 추가 + cpcv.py 핵심 함수 구현으로 Phase 0 테스트를 통과시킨다.

**작업 내용**:

- [x] `src/qbt/backtest/types.py`에 PboResultDict, DsrResultDict, CscvAnalysisResultDict 추가
- [x] `src/qbt/backtest/constants.py`에 CSCV 상수 추가
- [x] `src/qbt/backtest/cpcv.py` 구현:
  - 수학 유틸: `_norm_cdf()`, `_norm_ppf()`, `_logit()`
  - 성과 지표: `_compute_annualized_sharpe()`, `_compute_calmar_from_returns()`
  - CSCV 분할: `generate_cscv_splits()`
  - PBO: `calculate_pbo()`
  - DSR: `calculate_dsr()`
- [x] Phase 0 테스트 전체 통과 확인

---

### Phase 2 — 수익률 행렬 + CLI (Green)

병렬 실행으로 수익률 행렬을 구축하고 CLI 스크립트를 구현한다.

**작업 내용**:

- [x] `src/qbt/backtest/cpcv.py`에 추가:
  - `generate_param_combinations()`: 파라미터 리스트 → BufferStrategyParams 리스트
  - `_run_strategy_for_cscv()`: WORKER_CACHE 패턴, equity → 일별 수익률
  - `build_returns_matrix()`: 병렬 실행 + ndarray 합성
  - `run_cscv_analysis()`: 통합 오케스트레이션 (행렬 구축 → PBO → DSR)
- [x] `scripts/backtest/run_cpcv_analysis.py` CLI 스크립트:
  - argparse --strategy (all / buffer_zone_tqqq / buffer_zone_atr_tqqq / buffer_zone_qqq)
  - 데이터 로딩, 파라미터 조합 생성, MA 사전 계산
  - run_cscv_analysis() 호출
  - TableLogger 결과 출력
  - JSON/CSV 저장 + 메타데이터
- [x] `tests/test_cpcv.py`에 통합 테스트 추가:
  - TestBuildReturnsMatrix: 소규모 (3개 파라미터) 행렬 검증
  - TestRunCscvAnalysis: 소규모 종단간 검증

---

### Phase 3 (Final) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` -- cpcv.py 모듈 설명 추가
- [x] `CLAUDE.md` (루트) -- 디렉토리 구조 + 결과 파일 + 스크립트 추가
- [x] `scripts/CLAUDE.md` -- run_cpcv_analysis.py 설명 추가
- [x] `tests/CLAUDE.md` -- test_cpcv.py 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=397, failed=0, skipped=0)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 백테스트 / CSCV·PBO·DSR 과최적화 통계 검증 모듈 신규 추가
2. 백테스트 / 파라미터 과최적화 확률 검증 (PBO + DSR) 구현
3. 백테스트 / CSCV 기반 다중검정 보정 분석 모듈 추가
4. 백테스트 / 1,728개 파라미터 탐색 공간의 통계적 유의성 검증 도구 추가
5. 백테스트 / Bailey et al. (2017) PBO + DSR 과최적화 검증 구현

## 7) 리스크(Risks)

| 리스크 | 심각도 | 완화책 |
|--------|--------|--------|
| 수익률 행렬 메모리 (~88MB) | 중 | numpy ndarray 사용, 필요시 블록 단위 처리 |
| norm_ppf Acklam 근사 정밀도 | 하 | 정밀도 ~1e-9, 알려진 값 테스트로 고정 |
| 병렬 실행 pickle 제약 | 중 | 모듈 최상위 함수만 사용 (기존 그리드 서치 패턴 동일) |
| PyRight strict 타입 체크 | 중 | 정확한 TypedDict 정의, 반환 타입 명시 |

## 8) 메모(Notes)

### 핵심 참고 자료

- Bailey, Borwein, Lopez de Prado, Zhu (2017). "The Probability of Backtest Overfitting"
- Bailey & Lopez de Prado (2014). "The Deflated Sharpe Ratio"
- Lopez de Prado (2018). "Advances in Financial Machine Learning", Chapter 11-12

### 핵심 설계 결정

- CSCV 채택 (CPCV 대비 구현 단순, 목적에 충분)
- scipy 미사용 (math.erf + Acklam 근사)
- Sharpe 기반 PBO (표준) + Calmar 기반 PBO (선택 지원)
- 기존 코드 변경 없음 (analysis.py, walkforward.py, buffer_zone_helpers.py)

### 진행 로그 (KST)

- 2026-02-27 21:00: 계획서 작성 완료, 구현 시작
- 2026-02-28 01:30: 전체 구현 완료, validate_project.py 통과 (passed=397, failed=0, skipped=0)

---
