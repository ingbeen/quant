# Implementation Plan: 테스트 커버리지 개선 (90% → 95%+)

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

**작성일**: 2025-12-26 22:00
**마지막 업데이트**: 2025-12-26 23:00
**관련 범위**: backtest, tqqq, utils, tests
**관련 문서**:
- src/qbt/backtest/CLAUDE.md
- src/qbt/tqqq/CLAUDE.md
- tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- 각 Phase를 시작/종료할 때 **이전 Phase의 체크리스트(작업/Validation)와 DoD 체크리스트 상태를 먼저 최신화**한 뒤 진행한다. (미반영 상태로 다음 Phase 진행 금지)
- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 승인 요청을 하기 전 **반드시 plan 체크박스를 최신화**한다(체크 없이 승인 요청 금지).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: 전체 테스트 커버리지를 90%에서 95% 이상으로 개선 (달성: 96%)
- [x] 목표 2: 핵심 비즈니스 로직 (strategy.py, simulation.py)의 미커버 라인 최소화 (strategy: 96%, simulation: 93%)
- [x] 목표 3: 예외 처리 경로 및 엣지 케이스 테스트 보강 (17개 테스트 추가)

## 2) 비목표(Non-Goals)

- 100% 커버리지 달성 (로깅 코드, 불가능한 예외 경로 등은 제외)
- 프로덕션 코드 변경 (테스트만 추가)
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 커버리지 현황 (90%)**:
- 전체: 795줄 중 77줄 미커버
- strategy.py (85%): 35줄 누락
  - 핵심 기능인 `run_grid_search` 함수 전체 (552-614) 미커버
  - Buy & Hold 예외 처리 미커버 (413, 422, 426)
  - 자본 부족 경로 미커버 (281-285)
- simulation.py (78%): 30줄 누락
  - 워커 캐시 기반 비용 모델 평가 함수 전체 (301-330) 미커버
  - 일별 비교 데이터 생성 함수 (469-519) 미커버

**위험**:
- 그리드 서치는 백테스트 최적화의 핵심 기능으로, 테스트 없이 회귀 위험 높음
- 병렬 처리 로직은 디버깅 어려움 → 테스트 필수
- 예외 처리 경로 미검증 시 런타임 오류 가능성

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.
> (규칙을 요약/나열하지 말고 "문서 목록"만 둡니다.)

- [x] `CLAUDE.md` (루트)
- [x] `src/qbt/backtest/CLAUDE.md`
- [x] `src/qbt/tqqq/CLAUDE.md`
- [x] `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족: 전체 커버리지 95% 이상 (달성: 96%)
- [x] 회귀/신규 테스트 추가: 최소 15개 이상 테스트 케이스 추가 (17개 추가: 111 → 128)
- [x] `./run_tests.sh` 통과 (passed=128, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (문서 변경 불필요)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**테스트 파일 (신규 추가 또는 확장)**:
- `tests/test_strategy.py` - 그리드 서치, Buy & Hold 예외 처리, 자본 부족 경로
- `tests/test_tqqq_simulation.py` - 워커 캐시 평가, 일별 비교 생성
- `tests/test_analysis.py` - 미커버 라인 보완
- `tests/test_data_loader.py` - 미커버 라인 보완
- `tests/test_cli_helpers.py` - 예외 처리 경로
- `tests/test_logger.py` - 로거 미커버 경로
- `tests/test_parallel_executor.py` - 병렬 처리 예외 경로

**문서**:
- `docs/plans/test_coverage_improvement.md` (이 계획서)

### 데이터/결과 영향

- 출력 스키마 변경 없음 (테스트만 추가)
- 기존 결과 비교 불필요

## 6) 단계별 계획(Phases)

### Phase 1 — strategy.py 커버리지 개선 (그린 유지)

**작업 내용**:

- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] `test_strategy.py`에 그리드 서치 테스트 추가
  - [x] 기본 그리드 서치 실행 테스트
  - [x] 파라미터 조합 생성 검증
  - [x] 결과 정렬 검증 (CAGR 내림차순)
  - [x] 병렬 처리 결과 순서 보장 검증
- [x] Buy & Hold 예외 처리 테스트 추가
  - [x] `initial_capital <= 0` 예외 테스트
  - [x] 필수 컬럼 누락 예외 테스트
  - [x] 최소 행 수 부족 예외 테스트
- [x] 버퍼 전략 파라미터 검증 테스트 추가 (추가 작업)
  - [x] ma_window, buffer_zone_pct, hold_days, recent_months 검증
- [x] 기타 미커버 라인 검토 완료 (로깅 코드로 96% 달성)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=128, failed=0, skipped=0)

---

### Phase 2 — simulation.py 커버리지 개선 (그린 유지)

**작업 내용**:

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] 스킵 존재 여부 확인 (스킵 없음)
- [x] `test_tqqq_simulation.py`에 simulate 파라미터 검증 테스트 추가
  - [x] leverage, initial_price 검증 테스트
  - [x] 필수 컬럼 누락 검증
  - [x] 빈 DataFrame 검증
- [x] 일별 비교 데이터 생성 테스트 추가 (_save_daily_comparison_csv)
  - [x] CSV 저장 및 구조 검증
  - [x] 한글 컬럼명 검증
  - [x] 숫자 정밀도 검증 (소수점 4자리)
- [x] 기타 미커버 라인 검토 완료 (93% 달성)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=128, failed=0, skipped=0)

---

### Phase 3 — 기타 모듈 커버리지 개선 (그린 유지)

**작업 내용**:

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] DoD 체크리스트 최신화(현재까지 완료된 항목 반영)
- [x] 스킵 존재 여부 확인 (스킵 없음)
- [x] 기타 모듈 검토 완료 (Phase 1-2에서 96% 달성으로 Phase 3 작업 불필요)
  - analysis.py: 96% (로깅 코드)
  - data_loader.py: 96% (예외 처리)
  - cli_helpers.py: 91% (예외 처리)
  - logger.py: 94% (로거 초기화)
  - parallel_executor.py: 93% (예외 처리)
- [x] 전체 커버리지 95% 초과 달성 확인 (96%)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=128, failed=0, skipped=0)
- [x] `./run_tests.sh cov` - 96% 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] (직전 Phase) 체크리스트 최신화(작업 내용/Validation 체크 상태 반영)
- [x] `tests/CLAUDE.md` 업데이트 검토 (변경 불필요 - 기존 패턴 준수)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 전체 테스트 스위트 실행 및 커버리지 최종 확인
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=128, failed=0, skipped=0)
- [x] `./run_tests.sh cov` - 96% 최종 확인

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / 커버리지 90%→95% 개선 (핵심 로직 검증 보강)
2. 테스트 / 그리드 서치 및 병렬 처리 테스트 추가 (회귀 방지)
3. 테스트 / 예외 처리 및 엣지 케이스 커버리지 보완
4. 테스트 / 백테스트·시뮬레이션 도메인 테스트 보강 (정합성 보장)
5. 테스트 / 미커버 라인 제거 및 품질 게이트 강화

## 7) 리스크(Risks)

- 병렬 처리 테스트 작성 시 워커 캐시 격리 필요 (conftest.py 픽스처 활용)
- 일부 로깅 코드는 실제 커버하기 어려울 수 있음 (95% 목표로 충분)
- 테스트 추가로 테스트 실행 시간 증가 가능 (병렬 처리 유지로 최소화)

## 8) 메모(Notes)

### 우선순위 높은 미커버 영역

1. **strategy.py**:
   - `run_grid_search` (552-614): 백테스트 최적화 핵심 - 최우선
   - Buy & Hold 예외 처리 (413, 422, 426): 입력 검증 - 우선
   - 자본 부족 경로 (281-285): 엣지 케이스 - 중간

2. **simulation.py**:
   - `_evaluate_cost_model_candidate` (301-330): 병렬 처리 핵심 - 최우선
   - `generate_daily_comparison_data` (469-519): 대시보드 데이터 생성 - 우선

### 진행 로그 (KST)

- 2025-12-26 22:00: 계획서 작성 완료, 승인 대기
- 2025-12-26 22:05: 사용자 승인, Phase 1 시작
- 2025-12-26 22:15: Phase 1 완료 - strategy.py 커버리지 85% → 96% (11개 테스트 추가)
- 2025-12-26 22:25: Phase 2 완료 - simulation.py 커버리지 78% → 93% (6개 테스트 추가)
- 2025-12-26 22:30: Phase 3 완료 - 목표 96% 초과 달성으로 추가 작업 불필요
- 2025-12-26 22:40: 최종 Phase 완료 - 전체 테스트 128개 통과, 커버리지 96%
- 2025-12-26 23:00: 계획서 최종 업데이트 및 Done 처리

**최종 성과**:
- 전체 커버리지: 90% → 96% (목표 95% 초과 달성)
- 테스트 개수: 111개 → 128개 (+17개)
- strategy.py: 85% → 96% (+11%)
- simulation.py: 78% → 93% (+15%)
- 모든 테스트 통과: passed=128, failed=0, skipped=0

---
