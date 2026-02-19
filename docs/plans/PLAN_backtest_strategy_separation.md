# Implementation Plan: 백테스트 전략 파일 분리

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

**작성일**: 2026-02-19
**마지막 업데이트**: 2026-02-19
**관련 범위**: backtest, scripts/backtest, tests, common_constants
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [x] strategy.py를 전략별 파일로 분리 (`strategies/buffer_zone.py`, `strategies/buy_and_hold.py`)
- [x] 결과 파일을 전략별 폴더 구조로 변경 (`buffer_zone/`, `buy_and_hold/`)
- [x] Buy & Hold 결과 파일 생성 기능 추가 (signal.csv, equity.csv, trades.csv, summary.json)
- [x] 리팩토링 전후 백테스트 결과 동일성 보장 (기존 테스트 전체 통과)

## 2) 비목표(Non-Goals)

- 대시보드 앱(`app_single_backtest.py`) 기능 변경/확장 (깨진 import 최소 수정만 포함)
- 새 전략 추가
- helpers.py 별도 생성 (YAGNI 원칙에 따라 향후 필요 시 추출)
- 비즈니스 로직 변경 (순수 구조 분리)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `strategy.py` (865줄)에 버퍼존 + Buy&Hold + 그리드서치 + 헬퍼 함수 + 예외 클래스가 전부 한 파일에 존재
- 새 전략을 추가하려면 strategy.py를 직접 수정해야 함
- 전략 간 공통 코드(매수/매도 체결, 밴드 계산 등) 재사용 구조 부재
- 결과 파일이 flat 구조(`single_backtest_*.csv`)로 전략 구분 불가

### 설계 결정 사항 (사용자 확인 완료)

1. **helpers.py 미생성**: 버퍼존 전용 코드 → `buffer_zone.py`, 바이앤홀드 전용 코드 → `buy_and_hold.py`에 직접 배치
2. **Buy & Hold 결과 파일**: 4개 파일 모두 생성 (아키텍처 문서대로)
3. **대시보드**: 이번 범위에서 제외 (깨진 import 방지를 위한 최소 경로 수정만 포함)
4. **기존 flat 파일**: 상수 제거 + 새 폴더 구조 도입 (기존 파일은 수동 삭제 안내)

### 아키텍처 문서와의 차이점

원본 아키텍처 문서(`backtest_strategy_architecture.md`)와 비교하여 다음 사항이 변경됨:

| 항목 | 아키텍처 문서 | 이 계획서 |
|------|-------------|----------|
| helpers.py | 별도 파일 생성 (9개 헬퍼 + 공통 클래스) | 미생성. buffer_zone.py에 직접 배치 |
| test_integration.py | 영향 범위에 누락 | 변경 범위에 포함 |
| 대시보드 앱 | 결과 로딩 경로 변경 포함 | 최소 import 수정만 (기능 변경 제외) |
| conftest.py | 미언급 | mock_storage_paths 업데이트 포함 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] strategy.py 삭제, strategies/ 패키지에 buffer_zone.py + buy_and_hold.py 생성
- [x] 모든 import 경로 새 위치로 변경 (`__init__.py`, tests, scripts)
- [x] common_constants.py 결과 경로 상수 변경 (전략별 폴더)
- [x] run_single_backtest.py: 전략별 폴더 저장 + Buy & Hold 파일 생성
- [x] run_grid_search.py: grid_results.csv 새 경로
- [x] app_single_backtest.py: import 경로 최소 수정 (깨진 import 방지)
- [x] conftest.py: mock_storage_paths 새 상수 반영
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=287, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] backtest/CLAUDE.md 업데이트
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성**:

- `src/qbt/backtest/strategies/__init__.py`
- `src/qbt/backtest/strategies/buffer_zone.py`
- `src/qbt/backtest/strategies/buy_and_hold.py`

**삭제**:

- `src/qbt/backtest/strategy.py`

**변경**:

- `src/qbt/backtest/__init__.py` — import 경로 변경
- `src/qbt/common_constants.py` — 결과 경로 상수 변경
- `scripts/backtest/run_single_backtest.py` — 경로 + Buy & Hold 파일 생성
- `scripts/backtest/run_grid_search.py` — grid_results 경로
- `scripts/backtest/app_single_backtest.py` — import 경로 최소 수정
- `tests/test_strategy.py` — import 경로
- `tests/test_integration.py` — import 경로
- `tests/conftest.py` — mock_storage_paths
- `src/qbt/backtest/CLAUDE.md` — 모듈 구성 업데이트

### 데이터/결과 영향

결과 파일 저장 구조 변경:

```
변경 전:
  storage/results/backtest/
  ├── single_backtest_signal.csv
  ├── single_backtest_equity.csv
  ├── single_backtest_trades.csv
  ├── single_backtest_summary.json
  └── grid_results.csv

변경 후:
  storage/results/backtest/
  ├── buffer_zone/
  │   ├── signal.csv
  │   ├── equity.csv
  │   ├── trades.csv
  │   ├── summary.json
  │   └── grid_results.csv
  ├── buy_and_hold/
  │   ├── signal.csv
  │   ├── equity.csv
  │   ├── trades.csv
  │   └── summary.json
  └── (meta.json은 상위 results/에 유지)
```

비즈니스 로직 변경 없음 → 동일 파라미터 기준 백테스트 결과 동일

## 6) 단계별 계획(Phases)

### Phase 1 — 코드 분리 (strategy.py → strategies/ 패키지)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/` 디렉토리 생성
- [x] `src/qbt/backtest/strategies/__init__.py` 생성 (공개 API export)
- [x] `src/qbt/backtest/strategies/buffer_zone.py` 생성
  - `BaseStrategyParams`, `BufferStrategyParams`, `PendingOrder` 데이터 클래스
  - `PendingOrderConflictError` 예외 클래스
  - 로컬 상수 3개 (`DEFAULT_BUFFER_INCREMENT_PER_BUY`, `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY`, `DEFAULT_DAYS_PER_MONTH`)
  - 9개 헬퍼 함수 (`_validate_buffer_strategy_inputs`, `_compute_bands`, `_check_pending_conflict`, `_record_equity`, `_execute_buy_order`, `_execute_sell_order`, `_detect_buy_signal`, `_detect_sell_signal`, `_calculate_recent_buy_count`)
  - `run_buffer_strategy`, `run_grid_search`, `_run_buffer_strategy_for_grid`
- [x] `src/qbt/backtest/strategies/buy_and_hold.py` 생성
  - `BuyAndHoldParams` 데이터 클래스
  - `run_buy_and_hold` 함수
- [x] `src/qbt/backtest/__init__.py` 업데이트 (새 import 경로)
- [x] `src/qbt/backtest/strategy.py` 삭제
- [x] `tests/test_strategy.py` import 경로 변경
  - `qbt.backtest.strategy` → `qbt.backtest.strategies.buffer_zone` / `qbt.backtest.strategies.buy_and_hold`
- [x] `tests/test_integration.py` import 경로 변경
- [x] 기존 테스트 실행으로 코드 분리 검증: `poetry run pytest tests/test_strategy.py tests/test_integration.py -v`

---

### Phase 2 — 결과 폴더 구조 변경 + Buy & Hold 파일 생성

**작업 내용**:

- [x] `src/qbt/common_constants.py` 업데이트
  - 추가:
    - `BUFFER_ZONE_RESULTS_DIR = BACKTEST_RESULTS_DIR / "buffer_zone"`
    - `BUY_AND_HOLD_RESULTS_DIR = BACKTEST_RESULTS_DIR / "buy_and_hold"`
    - `BUFFER_ZONE_SIGNAL_PATH`, `BUFFER_ZONE_EQUITY_PATH`, `BUFFER_ZONE_TRADES_PATH`, `BUFFER_ZONE_SUMMARY_PATH`
    - `BUY_AND_HOLD_SIGNAL_PATH`, `BUY_AND_HOLD_EQUITY_PATH`, `BUY_AND_HOLD_TRADES_PATH`, `BUY_AND_HOLD_SUMMARY_PATH`
  - 변경: `GRID_RESULTS_PATH` → `BUFFER_ZONE_RESULTS_DIR / "grid_results.csv"`
  - 삭제: `SINGLE_BACKTEST_SIGNAL_PATH`, `SINGLE_BACKTEST_EQUITY_PATH`, `SINGLE_BACKTEST_TRADES_PATH`, `SINGLE_BACKTEST_SUMMARY_PATH`
- [x] `scripts/backtest/run_single_backtest.py` 업데이트
  - Buffer zone 결과를 `buffer_zone/` 폴더에 저장 (기존 `_save_results` 함수 경로 변경)
  - Buy & Hold 결과 파일 생성 추가:
    - `signal.csv`: trade_df의 OHLC 데이터 (MA 없음)
    - `equity.csv`: equity + position
    - `trades.csv`: 빈 DataFrame (매도 없음)
    - `summary.json`: 요약 지표
  - import 경로 변경 (`SINGLE_BACKTEST_*` → 새 상수)
  - 메타데이터 저장도 새 경로 반영
- [x] `scripts/backtest/run_grid_search.py` 업데이트
  - `GRID_RESULTS_PATH` → 새 경로 상수 사용
- [x] `scripts/backtest/app_single_backtest.py` import 수정
  - `SINGLE_BACKTEST_*` → `BUFFER_ZONE_*` 상수로 변경 (최소 수정, 기능 변경 없음)
- [x] `tests/conftest.py` 업데이트
  - `mock_results_dir`, `mock_storage_paths` 픽스처에 새 상수 패치 추가:
    - `BUFFER_ZONE_RESULTS_DIR`, `BUY_AND_HOLD_RESULTS_DIR` 디렉토리 생성 및 패치
    - `BUFFER_ZONE_*_PATH`, `BUY_AND_HOLD_*_PATH` 상수 패치
    - `GRID_RESULTS_PATH` 패치 (새 경로)
    - 기존 `SINGLE_BACKTEST_*_PATH` 패치 제거
- [x] 기존 결과 파일 삭제 안내 메시지 추가 (수동 삭제)
  - 대상: `storage/results/backtest/single_backtest_*.csv`, `single_backtest_summary.json`

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - 모듈 구성에 strategies/ 패키지 반영
  - strategy.py → strategies/buffer_zone.py + strategies/buy_and_hold.py
  - helpers.py 미생성 결정 사항 기록
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=287, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 전략 파일 분리 (strategy.py → strategies/ 패키지) + 결과 폴더 구조 개편
2. 백테스트 / buffer_zone·buy_and_hold 전략 분리 + 전략별 결과 폴더 도입
3. 백테스트 / 전략 아키텍처 리팩토링 + Buy & Hold 결과 파일 생성 추가
4. 백테스트 / strategy.py 분해 (buffer_zone.py, buy_and_hold.py) + 결과 경로 정리
5. 백테스트 / 전략 모듈화 + 전략별 폴더 결과 저장 + import 경로 정비

## 7) 리스크(Risks)

- **import 경로 누락**: 리팩토링 중 import 경로 변경 누락으로 런타임 에러 발생 가능
  - 완화: Phase 1에서 전체 테스트 실행으로 즉시 검증
- **conftest mock 누락**: 결과 경로 상수 변경 시 conftest의 mock 패치 누락 가능
  - 완화: Phase 2에서 테스트 실행으로 검증
- **대시보드 앱**: 기능 변경은 제외하나, 기존 데이터 파일 삭제 시 대시보드에서 데이터 표시 불가
  - 완화: 백테스트 재실행 필요 안내, 최소 import 수정 포함
- **buffer_zone.py 파일 크기**: helpers.py 미생성으로 ~780줄 규모 예상
  - 완화: 향후 버퍼존 계열 전략 추가 시 helpers.py 추출 가능 (YAGNI)
- **grid_results.csv 경로 변경**: 분석 워크플로에서 기존 경로 참조 가능
  - 완화: common_constants.py의 상수를 통해 중앙 관리, load_best_grid_params도 새 경로 사용

## 8) 메모(Notes)

### 설계 결정 근거

- **helpers.py 미생성**: 사용자 결정. YAGNI 원칙 적용. 현재 buffer_zone.py만 헬퍼를 사용하므로 별도 파일 불필요. 향후 StopLoss, Trailing 등 버퍼존 계열 전략 추가 시 공통 헬퍼를 추출하여 helpers.py 생성 예정.
- **Buy & Hold 결과 파일 생성**: 아키텍처 문서의 "출력만 통일" 원칙에 따라, signal.csv (MA 없는 OHLC), equity.csv, trades.csv (빈 DataFrame), summary.json 모두 생성.
- **대시보드 제외**: 기능 변경은 별도 작업으로 분리. 이 계획서에서는 깨진 import 방지를 위한 최소 경로 수정만 수행.

### 참고 문서

- 원본 아키텍처 문서: `backtest_strategy_architecture.md`

### 분리 후 디렉토리 구조

```
src/qbt/backtest/
├── __init__.py              # 패키지 공개 API (import 경로 변경)
├── analysis.py              # 변경 없음
├── constants.py             # 변경 없음
├── types.py                 # 변경 없음
├── strategies/              # [신규] 전략 파일들
│   ├── __init__.py
│   ├── buffer_zone.py       # 버퍼존 전략 전체 (클래스, 헬퍼, 실행 함수)
│   └── buy_and_hold.py      # Buy & Hold 전략 전체
├── strategy.py              # [삭제]
└── CLAUDE.md                # 업데이트
```

### buffer_zone.py 구성요소 (strategy.py에서 이동)

| 카테고리 | 구성요소 | 수량 |
|---------|---------|------|
| 데이터 클래스 | BaseStrategyParams, BufferStrategyParams, PendingOrder | 3개 |
| 예외 클래스 | PendingOrderConflictError | 1개 |
| 로컬 상수 | DEFAULT_BUFFER_INCREMENT_PER_BUY, DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY, DEFAULT_DAYS_PER_MONTH | 3개 |
| 헬퍼 함수 | _validate_buffer_strategy_inputs, _compute_bands, _check_pending_conflict, _record_equity, _execute_buy_order, _execute_sell_order, _detect_buy_signal, _detect_sell_signal, _calculate_recent_buy_count | 9개 |
| 전략 함수 | run_buffer_strategy, run_grid_search, _run_buffer_strategy_for_grid | 3개 |

### buy_and_hold.py 구성요소 (strategy.py에서 이동)

| 카테고리 | 구성요소 | 수량 |
|---------|---------|------|
| 데이터 클래스 | BuyAndHoldParams | 1개 |
| 전략 함수 | run_buy_and_hold | 1개 |

### 진행 로그 (KST)

- 2026-02-19: 계획서 작성 완료 (Draft)
- 2026-02-19: 전체 구현 완료 (Phase 1~3)
- 2026-02-19: 소스 레벨 검증 + validate_project.py 실행 (passed=287, failed=0, skipped=0), 체크리스트 업데이트 완료

---
