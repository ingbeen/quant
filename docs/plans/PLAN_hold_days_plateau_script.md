# Implementation Plan: hold_days 고원 분석 래퍼 스크립트

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

**작성일**: 2026-03-09 16:00
**마지막 업데이트**: 2026-03-09 16:30
**관련 범위**: scripts/backtest
**관련 문서**: `docs/PLAN_hold_days_plateau_analysis.md`, `docs/hold_days_2_experiment_results.md`

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

- [x] `scripts/backtest/run_hold_days_plateau.py` 스크립트 1개를 새로 생성하여, 7자산 x 8 hold_days = 56회 백테스트를 실행하고 결과를 CSV로 저장한다
- [x] 기존 비즈니스 로직(`run_buffer_strategy`, `BufferZoneConfig`)을 100% 재사용하며, 기존 코드 변경 없이 구현한다
- [x] `PLAN_hold_days_plateau_analysis.md` §5에 정의된 결과 파일 6종(상세 1 + 피벗 5)을 생성한다

## 2) 비목표(Non-Goals)

- 기존 코드(`src/qbt/`, `scripts/backtest/run_single_backtest.py`) 수정
- 56회 각각의 중간 결과 파일(signal.csv, equity.csv, trades.csv, summary.json) 저장
- 결과 해석 및 최적값 선택 로직
- 새 테스트 추가 (CLI 스크립트이며, 호출하는 비즈니스 로직은 기존 테스트에서 검증 완료)
- 스크립트 직접 실행 (사용자가 직접 실행)
- `common_constants.py` 또는 CLAUDE.md 문서 업데이트 (일회성 실험이므로)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`PLAN_hold_days_plateau_analysis.md`에서 hold_days 0~10 그리드 서치 실험을 정의했다. 목적은 hold_days=3이 "고원(plateau)의 일부"인지 "봉우리(spike)"인지 판별하는 것이다.

56회 백테스트를 실행해야 하는데, 기존 `run_single_backtest.py`를 그대로 사용하면:
- 56세트의 중간 결과 파일(224개)이 불필요하게 생성된다
- 기존 결과 디렉토리에 영향을 줄 위험이 있다
- 결과 집계를 별도로 수행해야 한다

이를 해결하기 위해 가벼운 래퍼 스크립트를 1개 만든다:
- 기존 비즈니스 로직을 직접 호출하여 summary만 수집
- 중간 파일 저장 없이 최종 집계 CSV만 생성
- 자산별 데이터 로딩 및 MA 계산을 1회로 최적화 (56회 -> 7회)

### 설계 핵심

1. **기존 config 재사용**: `buffer_zone.py`의 `get_config()`로 기존 config를 가져온 뒤, `dataclasses.replace(config, override_hold_days=N)`으로 hold_days만 교체
2. **데이터 로딩 최적화**: 자산별 1회 로딩 + 1회 MA 계산 후, 8개 hold_days에 대해 전략만 반복 실행
3. **중간 저장 생략**: `run_buffer_strategy()`의 반환값(summary dict)만 수집, `_save_results()` 미호출
4. **별도 경로 저장**: `storage/results/backtest/hold_days_plateau/`에 집계 CSV만 저장

### 고정 파라미터 (PLAN_hold_days_plateau_analysis.md §2)

| 파라미터 | 값 |
|---|---|
| ma_window | 200 (EMA) |
| buy_buffer_zone_pct | 0.03 (3%) |
| sell_buffer_zone_pct | 0.05 (5%) |
| recent_months | 0 |
| hold_days | **[0, 1, 2, 3, 4, 5, 7, 10]** (탐색 변수) |

### 대상 자산 및 사용할 config

| 자산 | config_name | 비고 |
|---|---|---|
| QQQ | `buffer_zone_qqq_4p` | signal=QQQ, trade=QQQ |
| SPY | `buffer_zone_spy` | signal=SPY, trade=SPY |
| IWM | `buffer_zone_iwm` | signal=IWM, trade=IWM |
| EFA | `buffer_zone_efa` | signal=EFA, trade=EFA |
| EEM | `buffer_zone_eem` | signal=EEM, trade=EEM |
| GLD | `buffer_zone_gld` | signal=GLD, trade=GLD |
| TLT | `buffer_zone_tlt` | signal=TLT, trade=TLT |

모든 config는 고정 파라미터(override)를 사용하며, hold_days만 `replace()`로 교체한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `scripts/backtest/run_hold_days_plateau.py` 스크립트가 생성됨
- [x] 기존 코드 변경 없음 (diff 확인)
- [x] 스크립트가 표준 CLI 패턴을 따름 (`@cli_exception_handler`, 로거, 종료 코드)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- **신규**: `scripts/backtest/run_hold_days_plateau.py` (래퍼 스크립트)

### 변경하지 않는 파일

- `src/qbt/backtest/strategies/buffer_zone.py` (CONFIGS, create_runner 등)
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` (run_buffer_strategy 등)
- `src/qbt/common_constants.py`
- `scripts/backtest/run_single_backtest.py`
- CLAUDE.md 문서들 (일회성 실험이므로)

### 데이터/결과 영향

- 기존 결과 디렉토리(`storage/results/backtest/buffer_zone_*`)에 영향 없음
- 새 결과는 `storage/results/backtest/hold_days_plateau/`에 저장
- 생성 파일 (6개):
  - `hold_days_plateau_analysis_detail.csv` (56행 상세)
  - `hold_days_plateau_analysis_calmar.csv` (7x8 피벗)
  - `hold_days_plateau_analysis_cagr.csv` (7x8 피벗)
  - `hold_days_plateau_analysis_mdd.csv` (7x8 피벗)
  - `hold_days_plateau_analysis_trades.csv` (7x8 피벗)
  - `hold_days_plateau_analysis_winrate.csv` (7x8 피벗)

## 6) 단계별 계획(Phases)

### Phase 1 (마지막) — 스크립트 구현 및 최종 검증

**작업 내용**:

- [x] `scripts/backtest/run_hold_days_plateau.py` 생성
  - [x] 로컬 상수 정의:
    - `_RESULT_DIR`: `BACKTEST_RESULTS_DIR / "hold_days_plateau"`
    - `_HOLD_DAYS_VALUES`: `[0, 1, 2, 3, 4, 5, 7, 10]`
    - `_ASSET_CONFIGS`: config_name과 표시 레이블 매핑 (7개)
  - [x] `_run_all_experiments()` 함수:
    - 자산별 데이터 로딩 1회 + MA 계산 1회 (최적화)
    - 각 hold_days에 대해 `dataclasses.replace(config, override_hold_days=N)` -> `resolve_params_for_config()` -> `run_buffer_strategy()` 호출
    - summary에서 cagr, mdd, calmar, trades, win_rate, period_start, period_end 수집
    - 반올림 규칙 적용 (백분율 2자리, Calmar 2자리, 거래수 정수)
    - 결과를 `pd.DataFrame`으로 반환
  - [x] `_save_pivot_csv()` 함수: 메트릭별 피벗 테이블 CSV 저장 (자산 순서 보장)
  - [x] `_save_results()` 함수: 상세 CSV 1개 + 피벗 CSV 5개 저장
  - [x] `_print_pivot_table()` 함수: `TableLogger` 기반 터미널 출력
  - [x] `main()` 함수: `@cli_exception_handler`, 실행 -> 저장 -> 출력 흐름
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / hold_days 고원 분석 래퍼 스크립트 추가 (56회 일괄 실행)
2. 백테스트 / hold_days 0~10 그리드 서치 실험 스크립트 추가
3. 백테스트 / hold_days plateau 형태 확인용 래퍼 스크립트 신규 생성
4. 백테스트 / 7자산 x 8 hold_days 비교 실험 스크립트 추가
5. 백테스트 / hold_days 고원 분석 스크립트 추가 (기존 코드 변경 없음)

## 7) 리스크(Risks)

- **데이터 불변성 의존**: `run_buffer_strategy()`가 입력 DataFrame을 변경하지 않는다는 전제 하에 자산별 1회 로딩 최적화를 적용함. 프로젝트 원칙("데이터 불변성")에 의해 보장되나, 만약 위반 시 2번째 이후 hold_days 결과가 오염될 수 있음 -> 완화: 기존 hold=0, hold=2 결과와 교차 검증 (§7.1)
- **PyRight 호환성**: 새 스크립트가 `scripts/` 하위이므로 완화된 PyRight 규칙이 적용되나, 타입 힌트는 최대한 명시함

## 8) 메모(Notes)

### 실행 안내 (사용자용)

```bash
poetry run python scripts/backtest/run_hold_days_plateau.py
```

### 결과 검증 포인트 (PLAN_hold_days_plateau_analysis.md §7.1)

스크립트 실행 후 아래 기존 값과 일치하는지 확인:

| 확인 항목 | 기대값 |
|---|---|
| QQQ hold=0 Calmar | 0.20 |
| QQQ hold=2 Calmar | 0.21 |
| SPY hold=0 Calmar | 0.35 |
| SPY hold=2 Calmar | 0.46 |
| GLD hold=0 Calmar | 0.20 |
| GLD hold=2 Calmar | 0.25 |

### 진행 로그 (KST)

- 2026-03-09 16:00: 계획서 작성
- 2026-03-09 16:30: 전체 작업 완료 (Phase 1, validate_project passed=479/failed=0/skipped=0)

---
