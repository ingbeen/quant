# Implementation Plan: 포트폴리오 대시보드 — Sharpe/Sortino + QQQ 연간 벤치마크

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

**작성일**: 2026-04-20 (KST)
**마지막 업데이트**: 2026-04-20 (KST)
**관련 범위**: backtest (analysis), scripts (run_portfolio_backtest, app_portfolio_backtest)
**관련 문서**: [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [scripts/CLAUDE.md](../../scripts/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] 포트폴리오 성과 지표에 **샤프 비율(Sharpe Ratio)**과 **소르티노 비율(Sortino Ratio)** 를 추가하여 리스크 조정 수익률 비교 가능
- [x] 월별 수익률 섹션의 "연간 수익률"을 **QQQ 벤치마크**와 비교할 수 있는 전용 시각화 영역 신설
- [x] 비즈니스 연산은 `src/qbt/backtest/analysis.py`에 구현하고 CLI(`run_portfolio_backtest.py`)가 호출, 대시보드는 저장된 값을 읽기만 하도록 계층 분리 준수

## 2) 비목표(Non-Goals)

- 무위험 수익률(Risk-Free Rate) 외부 데이터 연동 — **0 기준 고정**으로 단순화
- SPY, TLT 등 QQQ 외 벤치마크 지원
- 단일 백테스트 대시보드(`app_single_backtest.py`) 변경
- 소르티노/샤프 이외의 추가 리스크 지표 (Ulcer Index, Information Ratio 등)
- 기존 summary.json 스키마의 파괴적 변경 (기존 키는 유지, 신규 키만 추가)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 포트폴리오 대시보드의 성과 지표는 CAGR / MDD / Calmar / 총수익률 / 총거래수로 구성되며, **수익 변동성 관점의 리스크 조정 지표가 없다**.
- "연간 수익률"을 히트맵 "연간" 열로 확인할 수 있으나, 시장 수익률(QQQ)과의 상대 비교가 없어 **전략이 단순히 시장에 편승한 것인지, 실제로 초과 성과를 내는지 판단이 어렵다**.
- 대시보드(Streamlit 앱) 내부에서 도메인 연산을 수행하는 것은 CLAUDE.md 계층 분리 원칙에 위배되므로, 벤치마크와 리스크 지표 모두 **사전 계산 → 저장 → 읽기** 구조로 구성해야 한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트: [CLAUDE.md](../../CLAUDE.md)
- 도메인: [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)
- CLI: [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- 테스트: [tests/CLAUDE.md](../../tests/CLAUDE.md)
- 문서: [docs/CLAUDE.md](../CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `analysis.py`에 `calculate_sharpe_ratio`, `calculate_sortino_ratio`, `calculate_benchmark_yearly_returns` 추가 (타입 힌트·docstring 포함)
- [x] `run_portfolio_backtest.py`가 각 실험 summary.json에 `sharpe_ratio`, `sortino_ratio`를 저장
- [x] `run_portfolio_backtest.py`가 글로벌 시작일 확정 직후 `storage/results/portfolio/benchmark_qqq.json` 생성
- [x] `app_portfolio_backtest.py` 전체 비교 탭 성과 지표 테이블과 실험별 탭 요약 지표에 Sharpe/Sortino 컬럼 노출
- [x] `app_portfolio_backtest.py` 실험별 탭에 "연간 수익률 vs QQQ" 바차트 섹션 신설 (월별 히트맵 아래)
- [x] 신규 analysis 함수의 유닛 테스트 추가 (`tests/qbt/test_analysis.py`)
- [x] `poetry run python validate_project.py` 통과 (passed=1030, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py` — 3개 함수 추가 (`calculate_sharpe_ratio`, `calculate_sortino_ratio`, `calculate_benchmark_yearly_returns`)
- `scripts/backtest/run_portfolio_backtest.py` — summary 저장 로직에 Sharpe/Sortino 계산·저장, 글로벌 시작일 기반 QQQ 벤치마크 JSON 생성 로직 추가
- `scripts/backtest/app_portfolio_backtest.py` — 성과 지표 테이블 컬럼 확장, 요약 지표 섹션 Sharpe/Sortino metric 추가, "연간 수익률 vs QQQ" 바차트 섹션 신설
- `tests/qbt/test_analysis.py` — 신규 함수 유닛 테스트 추가
- `src/qbt/backtest/CLAUDE.md` — `analysis.py` 함수 목록 갱신, 대시보드 섹션에 신규 영역 1줄 추가
- `scripts/CLAUDE.md` — 포트폴리오 대시보드 주요 섹션 목록에 "연간 수익률 vs QQQ" 추가
- `README.md`: 변경 없음 (실행 명령어 변경 없음)
- `docs/COMMANDS.md`: 변경 없음 (CLI 옵션·실행 명령어 변경 없음)

### 데이터/결과 영향

- `storage/results/portfolio/{experiment_name}/summary.json`: `portfolio_summary` 블록에 `sharpe_ratio`, `sortino_ratio` 키 추가 (기존 키는 유지)
- `storage/results/portfolio/benchmark_qqq.json`: 신규 생성 — 스키마 `{ "start_date": str, "end_date": str, "yearly_returns": [{"year": int, "return_pct": float}, ...] }`
- 기존 실험 결과 CSV(equity / trades / signal / execution_comparison / state_log)는 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — `analysis.py` 계산 함수 추가 (그린 유지)

**작업 내용**:

- [x] `calculate_sharpe_ratio(equity_df, risk_free_rate=0.0) -> float` 추가
- [x] `calculate_sortino_ratio(equity_df, risk_free_rate=0.0) -> float` 추가
- [x] `calculate_benchmark_yearly_returns(benchmark_df, start_date, end_date) -> list[dict]` 추가

---

### Phase 2 — `run_portfolio_backtest.py` 통합 (그린 유지)

**작업 내용**:

- [x] `_save_portfolio_results()` 내부 summary 계산 구간에서 `calculate_sharpe_ratio`, `calculate_sortino_ratio`를 호출하여 `portfolio_summary` 딕셔너리에 `sharpe_ratio`, `sortino_ratio` 키 추가 (ROUND_PERCENT 반올림)
- [x] `main()`의 글로벌 시작일(`global_start_date`) 확정 직후, 실험 루프 시작 전에 `_save_benchmark_qqq_json(global_start_date)` 호출 → `PORTFOLIO_RESULTS_DIR / "benchmark_qqq.json"` 저장
- [x] 기존 `validate_portfolio_result` 호출 순서·검증 로직은 변경하지 않음

---

### Phase 3 — 대시보드 업데이트 (그린 유지)

**작업 내용**:

- [x] `_COL_SHARPE`, `_COL_SORTINO` 로컬 상수 추가
- [x] 전체 비교 탭 성과 지표 테이블에 `Sharpe`, `Sortino` 컬럼 추가 (Calmar 뒤 → 총수익률 앞)
- [x] 실험별 탭 "요약 지표" 섹션의 metric을 4열에서 6열로 확장
- [x] `_render_benchmark_comparison_section(exp)` 신설 — Plotly 2-row subplot (grouped bar + 초과 수익 %p)
- [x] 실험별 탭 호출 순서: 월별 히트맵 → **연간 수익률 vs QQQ** → 자산별 수익 기여도

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `tests/qbt/test_analysis.py`에 신규 유닛 테스트 추가
  - `TestCalculateSharpeRatio`: 정상 계산 / std=0 경계 / 데이터 부족 경계
  - `TestCalculateSortinoRatio`: 정상 계산 / downside=0 경계 / 모든 수익 양수 경계
  - `TestCalculateBenchmarkYearlyReturns`: 정상 계산 / 빈 기간 경계
- [x] `src/qbt/backtest/CLAUDE.md` analysis.py 섹션에 신규 3개 함수 라인 추가
- [x] `scripts/CLAUDE.md` 포트폴리오 대시보드 실험별 탭 섹션 목록에 "연간 수익률 vs QQQ" 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1030, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / Sharpe·Sortino 지표 및 QQQ 연간 벤치마크 비교 추가
2. 포트폴리오 / 리스크 조정 지표(Sharpe, Sortino) 도입 및 QQQ 대비 연간 수익률 시각화
3. 백테스트 / analysis에 Sharpe·Sortino·벤치마크 연간 수익률 함수 추가 + 대시보드 통합
4. 대시보드 / 포트폴리오 성과 지표 확장(Sharpe/Sortino) + 연간 수익률 QQQ 벤치마크 섹션
5. 포트폴리오 / 리스크 조정 수익률 지표 2종 추가 + QQQ 벤치마크 연간 비교 뷰

## 7) 리스크(Risks)

- **Sharpe/Sortino 분모 0 경계**: 수익률 std 또는 downside deviation이 0에 근접할 때 폭주 가능. → 명시적 0.0 반환 규칙을 코드와 테스트 양쪽에 고정.
- **벤치마크 기간 불일치**: 글로벌 시작일과 QQQ 데이터 시작일의 갭으로 벤치마크 첫 해가 부분 기간이 될 수 있음. → 기존 `calculate_yearly_returns`가 연도별 월 수익률 복리이므로 부분 기간도 일관 처리. 첫/마지막 해가 부분 기간일 수 있다는 점을 대시보드 caption으로 안내.
- **summary.json 스키마 확장**: 기존 소비자(대시보드)가 해당 키가 없어도 동작해야 함. → 대시보드 로드 코드에서 `.get(..., "N/A")` 패턴 사용.
- **benchmark_qqq.json 누락 방어**: `run_portfolio_backtest.py` 미실행 환경에서 앱 로드 시 안전하게 정보 메시지 처리.

## 8) 메모(Notes)

- 무위험 수익률은 **0 기준**으로 고정 (사용자 합의). 추후 FFR 연동이 필요하면 후속 plan으로 분리.
- 벤치마크 티커는 **QQQ 단일** (사용자 합의). SPY 등 추가는 후속 plan.
- 샤프/소르티노 연율화 상수는 `TRADING_DAYS_PER_YEAR=252` ([common_constants.py](../../src/qbt/common_constants.py))를 사용.
- 벤치마크 JSON은 **매 실행마다 재생성** (글로벌 시작일 변경 즉시 반영).

### 진행 로그 (KST)

- 2026-04-20: Plan 초안 작성 및 In Progress 전환
- 2026-04-20: Phase 1~3 + 최종 Phase 완료. validate_project.py passed=1030, failed=0, skipped=0. 상태 Done으로 전환
