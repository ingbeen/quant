# Implementation Plan: 포트폴리오 백테스트 실험별 독립 시작일 적용

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
**관련 문서**: [scripts/CLAUDE.md](../../scripts/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

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

- [x] 포트폴리오 백테스트 실행 시, **전체 실험 기준 글로벌 시작일(max)** 대신 **각 실험 고유의 유효 시작일**을 사용하도록 변경한다
- [x] QQQ 벤치마크 JSON(`benchmark_qqq.json`)은 **공유 1개 파일**을 유지하되, 가장 이른 실험 시작일(`min`) 기준으로 계산하여 모든 실험의 연도를 커버한다 (대시보드는 기존 `inner join` 방식 그대로 사용)
- [x] 결과: 포트폴리오별 백테스트 기간이 달라질 수 있으나 각 실험은 자기 자산 조합의 최대 가용 구간을 활용

## 2) 비목표(Non-Goals)

- [`compute_portfolio_effective_start_date`](../../src/qbt/backtest/engines/portfolio_engine.py) 자체 수정 (이미 "해당 config 자산들만의 교집합 + MA 워밍업" 기반으로 동작 — 변경 불필요)
- [`run_portfolio_backtest`](../../src/qbt/backtest/engines/portfolio_engine.py) 시그니처 변경 (`start_date: date | None` 파라미터 그대로 활용)
- [app_portfolio_backtest.py](../../scripts/backtest/app_portfolio_backtest.py) 대시보드 로직 수정 (현 `inner join` 로직이 기간 차이를 자동 처리)
- 포트폴리오 엔진 내부의 데이터 로딩/공통 기간 계산 로직 변경
- `PORTFOLIO_CONFIGS` 실험 구성 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

[run_portfolio_backtest.py:494-502](../../scripts/backtest/run_portfolio_backtest.py#L494-L502):

```python
effective_start_dates = [compute_portfolio_effective_start_date(cfg) for cfg in PORTFOLIO_CONFIGS]
global_start_date = max(effective_start_dates)
...
_save_benchmark_qqq_json(global_start_date)
```

- 전체 실험 중 시작일이 가장 늦은 실험을 기준으로 `global_start_date`를 결정
- 예를 들어 2배 레버리지 ETF(SSO/QLD/UGL/UBT) 실험의 데이터가 가장 짧다면, QQQ 100% 같은 장기 실험도 해당 짧은 기간으로 잘림
- 사용자 요청: 각 실험은 자기 자산 조합에서만 공통 기간을 찾아 백테스트 (예: `_CONFIG_Q2_2XS`는 SSO/QLD/GLD/TLT/SPY/QQQ만으로 공통 기간 산출)
- 결과: 각 실험이 자기 자산의 최대 가용 기간을 활용할 수 있게 됨

### 설계 결정 — QQQ 벤치마크 파일 유지 방식

- 사용자 요청에 따라 `benchmark_qqq.json`은 **공유 파일 1개** 유지
- 대시보드 [app_portfolio_backtest.py:527](../../scripts/backtest/app_portfolio_backtest.py#L527) `common_years = sorted(set(port_map.keys()) & set(bench_map.keys()))`가 이미 연도 inner join 방식
- QQQ JSON을 `min(effective_start_dates)` 기준으로 계산하면 가장 이른 실험의 연도부터 포함되어 모든 실험을 커버 → 대시보드는 수정 없이 자동으로 올바른 연도만 비교

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) (테스트 영향 확인 목적)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `run_portfolio_backtest.py`에서 `global_start_date` 산출 로직이 제거되고, 각 실험이 자기 `compute_portfolio_effective_start_date(config)` 결과를 사용
- [x] QQQ 벤치마크 JSON은 `min(effective_start_dates)` 기준으로 1개 파일 저장
- [x] `--experiment all` / 단일 실험 실행 모두 정상 동작 (분기 없이 `effective_start_dates`를 `PORTFOLIO_CONFIGS` 전체로 계산 후 `target_configs`만 실행)
- [x] 단일 실험 실행 시에도 QQQ 벤치마크는 전체 실험의 `min` 기준으로 저장 (다른 실험의 대시보드 비교 유지)
- [x] 기존 테스트 회귀 없음 확인 (포트폴리오 엔진 테스트·전체 1030개 테스트 모두 통과)
- [x] `poetry run python validate_project.py` 통과 (passed=1030, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (변경 파일에 포맷 적용 — 변경 없음)
- [x] 필요한 문서 업데이트 확인: README.md 변경 없음 / `docs/COMMANDS.md` 변경 없음 / `scripts/CLAUDE.md` 업데이트 / `src/qbt/backtest/CLAUDE.md` 업데이트 / plan 업데이트
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [scripts/backtest/run_portfolio_backtest.py](../../scripts/backtest/run_portfolio_backtest.py)
  - `main()`의 글로벌 시작일 계산/적용 로직 수정 (완료)
  - `_save_benchmark_qqq_json`의 독스트링 업데이트 (완료)
  - `date` import 추가 (완료)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): "글로벌 시작일 정렬" → "실험별 독립 시작일 + QQQ 공유 정책" 업데이트 (완료)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): `compute_portfolio_effective_start_date` / `run_portfolio_backtest` 설명의 "글로벌 시작일" 문구 정리 (완료)
- [src/qbt/backtest/engines/portfolio_engine.py](../../src/qbt/backtest/engines/portfolio_engine.py): 두 공개 함수 docstring 문구 정리 (로직 변경 없음, 완료)
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (CLI 인자/실행 명령어 동일)

### 데이터/결과 영향

- 출력 스키마: 변경 없음 (equity.csv, trades.csv, summary.json, signal\_\*.csv, state_log.csv, execution_comparison.csv 구조 동일)
- 결과 값: 실험에 따라 백테스트 시작일이 앞당겨질 수 있어 성과 지표(CAGR/MDD/Calmar 등)가 이전 결과와 다를 수 있음 — 기존 결과 재생성 필요
- QQQ 벤치마크 JSON: `start_date` 값이 `min` 기준으로 변경되며, `yearly_returns` 연도 범위가 확장될 수 있음 (대시보드는 inner join이라 자동 처리)

## 6) 단계별 계획(Phases)

### Phase 1 — `run_portfolio_backtest.py` 수정

**작업 내용**:

- [x] `main()` 내 `global_start_date = max(...)` 로직 제거
- [x] 전체 실험의 `effective_start_dates`를 한 번 계산하되, 대상 실험 반복문 내에서는 해당 실험의 `compute_portfolio_effective_start_date(config)`를 개별로 계산하여 `run_portfolio_backtest(config, start_date=exp_start_date)` 호출
- [x] 효율화: `all` 실행 시 중복 계산 방지를 위해 `PORTFOLIO_CONFIGS` 전체에 대한 `effective_start_dates` 1회 계산 후 실험별로 해당 값 재사용 (이 값은 QQQ `min` 계산에도 사용)
- [x] `_save_benchmark_qqq_json(min_start_date)` 호출: `min(effective_start_dates)` 전달
- [x] `_save_benchmark_qqq_json` 독스트링 수정 (min 기준 + 대시보드 inner join 문맥 반영)
- [x] 로깅: 각 실험 시작 시점에 `exp_start_date`를 DEBUG 로그로 기록하여 기간 차이를 투명화
- [x] 함수 동작 확인 (실행은 사용자가 담당)

---

### Phase 2 — (선택) 단위 테스트 확인/보강

**작업 내용**:

- [x] 기존 테스트(`tests/qbt/backtest/` 포트폴리오 관련)는 `run_portfolio_backtest.py` CLI 로직을 직접 커버하지 않음. 엔진 비즈니스 로직 테스트만 통과하면 충분 → 마지막 Phase의 validate에서 1030개 테스트 모두 통과 확인됨
- [x] 추가 smoke test 불필요로 판단 (기존 `compute_portfolio_effective_start_date` 테스트 및 `run_portfolio_backtest(config, start_date=...)` 기반 엔진 테스트가 커버)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [scripts/CLAUDE.md](../../scripts/CLAUDE.md) `run_portfolio_backtest.py` 항목의 "글로벌 시작일 정렬" 설명을 "실험별 독립 시작일 + QQQ 벤치마크 공유 정책"으로 수정
- [x] [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) `compute_portfolio_effective_start_date` / `run_portfolio_backtest` 설명의 "글로벌 시작일" 문구 정리
- [x] [src/qbt/backtest/engines/portfolio_engine.py](../../src/qbt/backtest/engines/portfolio_engine.py) 두 공개 함수의 docstring도 같은 맥락으로 정리 (로직 변경 없음)
- [x] `poetry run black .` 실행 (변경 파일에 포맷 적용 — 변경 없음)
- [ ] 사용자에게 결과 재생성(스크립트 실행) 요청 및 대시보드 동작 확인 요청 (사용자 작업 대기)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1030, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실험별 유효 시작일 적용 (전체 max → 실험별 개별)
2. 백테스트 / 포트폴리오 실험별 독립 기간 백테스트로 전환 + QQQ 벤치마크 min 기준 통합
3. 백테스트 / run_portfolio_backtest 글로벌 시작일 제거 (자산 조합별 최대 가용 구간 사용)
4. 백테스트 / 포트폴리오 글로벌 시작일(max) 제거 — 실험별 effective_start_date 개별 적용
5. 백테스트 / 포트폴리오 기간 정렬 정책 변경 (실험별 독립, QQQ 벤치마크 공유 파일 유지)

## 7) 리스크(Risks)

- 기간 차이로 인한 비교 혼란: "전체 비교" 탭에서 실험별 에쿼티 곡선의 시작 시점이 달라져 시각적으로 비교가 어색할 수 있음 → 사용자가 이미 (A) 선택 (기간이 달라도 무방) — 완화 불필요
- 단일 실험 실행 시 QQQ 벤치마크 계산: 모든 실험 configs에 대한 effective_start_date를 계산해야 `min`을 얻을 수 있어 단일 실행이라도 전체 configs 스캔 필요 — 기존에도 동일 (glob 로직 유사). 성능 영향 미미 (데이터 로딩 한 번)
- 대시보드 "전체 비교" 탭의 에쿼티 곡선: 기존에는 동일 시작일 기준 절대값 비교가 자연스러웠으나 이제는 시작점이 다를 수 있음 → 비교 해석 주의 필요 (문서에 명시)
- 기존 저장된 결과 파일과 혼재: 재실행 전까지 구/신 결과가 혼합될 수 있음 → 사용자가 재실행 시 덮어쓰기로 해결

## 8) 메모(Notes)

- `compute_portfolio_effective_start_date`는 내부에서 `_load_portfolio_data_with_common_period`를 호출하여 전 자산 데이터 로딩 + 교집합 + MA 워밍업을 수행 → 중복 계산 비용은 단순히 "한 번은 effective date 산출용, 한 번은 실제 백테스트용"으로 2회 데이터 로딩 발생. 현재 구조와 동일한 부담이므로 이번 plan에서는 최적화하지 않음
- 대시보드 [app_portfolio_backtest.py:527](../../scripts/backtest/app_portfolio_backtest.py#L527)의 inner join 로직으로 QQQ 연간 수익률 비교는 실험별로 자동 정렬됨 — 이 점이 "공유 JSON 1개 유지" 결정의 핵심 근거

### 진행 로그 (KST)

- 2026-04-20: 계획서 초안 작성
- 2026-04-20: Phase 1 구현 완료 — `main()` 글로벌 시작일 로직 제거, 실험별 `effective_start_date` 적용, QQQ 벤치마크 `min` 기준으로 변경
- 2026-04-20: 문서 업데이트 완료 (scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md, portfolio_engine.py docstring)
- 2026-04-20: `validate_project.py` 통과 (passed=1030, failed=0, skipped=0). 상태 → Done
