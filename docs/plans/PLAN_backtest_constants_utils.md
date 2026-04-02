# Implementation Plan: 백테스트 상수/유틸 인프라 정비

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

**작성일**: 2026-04-02 15:00
**마지막 업데이트**: 2026-04-02 18:30
**관련 범위**: backtest, utils, scripts, common_constants
**관련 문서**: `docs/plans/REPORT_backtest_code_review.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] 반올림 규칙 상수를 정의하고 모든 백테스트 스크립트가 리터럴 대신 상수 사용 (리포트 3-4)
- [x] 핵심 컬럼명 6개를 COL_* 상수로 정의하고 해당 파일들이 상수 사용 (리포트 3-5, 확정 방침 5-3)
- [x] MA 컬럼명 생성 함수를 추출하고 `f"ma_{window}"` 패턴 제거 (리포트 3-7)
- [x] 16개 결과 디렉토리 상수를 제거하고 CONFIGS에 인라인 구성 (리포트 3-6, 확정 방침 5-4)
- [x] drawdown_pct 공용 함수를 `analysis.py`에 추가하고 CLI 중복 해소 (리포트 3-2)
- [x] `csv_export.py` 모듈을 생성하여 trades/change_pct 중복 해소 (리포트 3-1, 3-15)
- [x] `load_signal_trade_pair` 공용 함수를 추가하여 데이터 로딩 중복 해소 (리포트 3-3)
- [x] 단순 수정 6건 완료: frozen=True(1-1), df.copy()(1-4), import 수정(2-9), 오타(2-11), ma_window 검증(3-13), type:ignore 수정(3-14)
- [x] CLAUDE.md 문서 불일치 2건 수정 (리포트 1-5)

## 2) 비목표(Non-Goals)

- 포트폴리오 엔진의 engine_common 통합 (Plan 2 범위: 리포트 1-3, 5-1)
- pnl_pct 계산 방식 통일 (Plan 2 범위: 리포트 2-1)
- `run_walkforward.py` 비즈니스 로직 이동 (Plan 3 범위: 리포트 1-2, 5-2)
- drawdown 방어 로직 통일 — `portfolio_data.py`의 `peak + EPSILON` 방식 (Plan 2 범위: 리포트 2-4)
- params_schedule 전환 로직 수정 (Plan 2 범위: 리포트 2-2)
- 기존 테스트의 대규모 리팩토링
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`REPORT_backtest_code_review.md`에서 식별된 상수 관리 미비, 코드 중복, 문서 불일치 문제를 해결한다. 이 Plan은 후속 Plan 2(버그 수정 + 엔진 통합), Plan 3(계층 분리)의 **선행 의존성**이다.

**상수 관리 미비**:

- 반올림 규칙이 루트 CLAUDE.md에 명시되어 있으나, 구현은 `run_portfolio_backtest.py`만 로컬 상수(`_PRICE_ROUND=6` 등) 사용. 나머지 3개 스크립트는 리터럴 숫자 직접 사용
- 핵심 컬럼명(`"equity"`, `"pnl"`, `"entry_date"` 등)이 문자열 리터럴로 3개 이상 파일에서 반복 → 오타 시 런타임 에러로만 발견 가능
- `f"ma_{window}"` 패턴이 최소 3곳에서 반복 → MA 컬럼 네이밍 규칙 변경 시 여러 곳 수정 필요
- 16개 결과 디렉토리 상수가 `common_constants.py`에 정의되어 있으나 대부분 단일 파일(CONFIGS)에서만 사용 → 상수 관리 3계층 규칙 위반

**코드 중복**:

- trades CSV 저장 패턴이 3개 스크립트에 동일하게 반복 (holding_days 계산, 반올림, int 변환)
- drawdown_pct 계산 패턴이 2개 스크립트에 동일하게 반복
- signal/trade 데이터 로딩 패턴이 3곳에 동일하게 반복 (signal_path == trade_path 분기 + overlap 추출)
- change_pct 계산이 2개 스크립트에 반복 (단, `run_walkforward.py`는 change_pct를 참조만 하고 계산하지 않는 문제 발견)

**문서/코드 불일치**:

- `BufferStrategyParams`에 `frozen=True` 누락 (CLAUDE.md와 불일치)
- `_prepare_buy_and_hold_signal_df`가 `df.copy()` 없이 원본 반환 (데이터 불변성 원칙 위반 가능)
- `walkforward.py`에서 `__import__("datetime")` 비관습적 패턴 사용
- `portfolio_configs.py` docstring 오타
- `resolve_buffer_params`에서 `ma_window` 양수 검증 누락
- `buffer_zone.py`에서 `type: ignore[assignment]` 사용 (명시적 narrowing 가능)
- backtest CLAUDE.md 문서 자체의 코드 불일치 2건

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`: 상수 관리 3계층, 상수 명명 규칙, 반올림 규칙, 데이터 불변성 원칙
- `src/qbt/backtest/CLAUDE.md`: 도메인 규칙, 모듈 구성
- `src/qbt/utils/CLAUDE.md`: 유틸리티 패키지 설계 원칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 부동소수점 비교, 파일 격리)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 반올림 상수 4개가 `constants.py`에 정의되고 4개 스크립트가 리터럴 대신 상수 사용
- [x] 컬럼명 상수 6개가 `constants.py`에 COL_* 정의되고 해당 파일들이 상수 사용
- [x] `ma_col_name()` 함수가 정의되고 `f"ma_{window}"` 리터럴 패턴 제거
- [x] `common_constants.py`에서 16개 개별 결과 디렉토리 상수 제거, CONFIGS 인라인 구성 완료
- [x] `calculate_drawdown_pct_series()` 함수가 `analysis.py`에 존재하고 2개 스크립트가 사용
- [x] `csv_export.py`가 존재하고 trades 저장 / change_pct 중복 해소
- [x] `load_signal_trade_pair()` 함수가 `data_loader.py`에 존재하고 3곳이 사용
- [x] 단순 수정 6건 완료 (1-1, 1-4, 2-9, 2-11, 3-13, 3-14)
- [x] backtest CLAUDE.md 문서 불일치 2건 수정 (1-5a, 1-5b)
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=451, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (backtest CLAUDE.md, tests CLAUDE.md)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**src/qbt/ (비즈니스 로직)**:

| 파일 | 변경 내용 |
|------|-----------|
| `common_constants.py` | 16개 결과 디렉토리 상수 제거 |
| `backtest/constants.py` | ROUND_* 4개, COL_* 6개, `ma_col_name()` 함수 추가 |
| `backtest/types.py` | `BufferStrategyParams`에 `frozen=True` 추가 |
| `backtest/analysis.py` | `calculate_drawdown_pct_series()` 추가, `ma_col_name()` 사용 |
| `backtest/csv_export.py` | **신규 생성** — `prepare_trades_for_csv()`, `calculate_change_pct()` |
| `backtest/walkforward.py` | `__import__("datetime")` → 정상 import |
| `backtest/strategies/buffer_zone.py` | ma_window 검증, type:ignore 수정, CONFIGS 인라인 경로 |
| `backtest/strategies/buy_and_hold.py` | CONFIGS 인라인 경로 |
| `backtest/strategy_registry.py` | `df.copy()` 추가 |
| `backtest/portfolio_configs.py` | docstring 오타 수정 |
| `backtest/runners.py` | COL_* 상수, `ma_col_name()`, `load_signal_trade_pair()` 사용 |
| `backtest/engines/engine_common.py` | COL_* 상수 사용 |
| `backtest/engines/backtest_engine.py` | `ma_col_name()` 사용 |
| `utils/data_loader.py` | `load_signal_trade_pair()` 추가 |

**scripts/backtest/**:

| 파일 | 변경 내용 |
|------|-----------|
| `run_single_backtest.py` | ROUND_* 상수, `csv_export` 사용, `calculate_drawdown_pct_series()` 사용 |
| `run_walkforward.py` | ROUND_* 상수, `csv_export` 사용, `calculate_drawdown_pct_series()` 사용 |
| `run_portfolio_backtest.py` | ROUND_* 상수 (로컬 상수 제거), `csv_export` 사용 |
| `run_param_plateau_all.py` | `load_signal_trade_pair()` 사용 |

**tests/**:

| 파일 | 변경 내용 |
|------|-----------|
| `test_csv_export.py` | **신규 생성** — trades 준비, change_pct 테스트 |
| `test_analysis.py` | `calculate_drawdown_pct_series()` 테스트 추가 |
| `test_data_loader.py` | `load_signal_trade_pair()` 테스트 추가 |
| `test_buffer_zone.py` | ma_window 검증 테스트 추가 |
| `test_buffer_zone_contracts.py` | frozen=True 테스트 추가 |
| 16개 상수 import 파일 | import 경로 수정 (해당 시) |

**문서**:

| 파일 | 변경 내용 |
|------|-----------|
| `src/qbt/backtest/CLAUDE.md` | 1-5a/1-5b 수정, csv_export.py 모듈 설명 추가 |
| `tests/CLAUDE.md` | test_csv_export.py 추가 |
| `README.md` | 변경 없음 (내부 인프라 리팩토링) |

### 데이터/결과 영향

- 출력 스키마 변경 없음 (동일한 CSV/JSON 출력)
- 기존 결과와 수치 차이 없음 (동작 변경 없는 리팩토링)

## 6) 단계별 계획(Phases)

### Phase 0 — 신규 계약 테스트 고정 (레드)

> frozen=True 불변성, ma_window 검증, 신규 유틸 함수 3개의 계약을 테스트로 먼저 고정한다.
> 구현이 아직 없으므로 레드(실패) 상태가 허용된다.

**작업 내용**:

- [x] `test_buffer_zone_contracts.py`에 frozen=True 테스트 추가
  - `BufferStrategyParams` 필드 변경 시 `FrozenInstanceError` (또는 `AttributeError`) 발생 검증
- [x] `test_buffer_zone.py`에 ma_window 검증 테스트 추가
  - `resolve_buffer_params(ma_window=0, ...)` → `ValueError` 발생 검증
  - `resolve_buffer_params(ma_window=-10, ...)` → `ValueError` 발생 검증
- [x] `test_analysis.py`에 `calculate_drawdown_pct_series()` 테스트 추가
  - 기본 drawdown 계산 정확성 (상승→하락→상승 시나리오)
  - peak=0일 때 division by zero 방지 (EPSILON 방어)
  - 단조 증가 시 drawdown=0 검증
- [x] `test_csv_export.py` 신규 생성
  - `prepare_trades_for_csv()`: holding_days 계산, 반올림 적용, shares int 변환
  - `prepare_trades_for_csv()`: 빈 DataFrame 입력 시 빈 DataFrame 반환
  - `calculate_change_pct()`: 전일대비 변동률(%) 정확히 계산
- [x] `test_data_loader.py`에 `load_signal_trade_pair()` 테스트 추가
  - signal_path == trade_path일 때 독립 복사본 반환 (원본 불변성)
  - signal_path != trade_path일 때 겹치는 기간 추출
  - 겹치는 기간 없을 때 ValueError 전파

---

### Phase 1 — 상수 인프라 정비 + 단순 수정 (그린 유지)

> 새 상수를 정의하고, 호출부를 리터럴에서 상수로 전환한다.
> 동시에 단순 수정 6건을 처리한다.
> Phase 0의 frozen=True, ma_window 검증 테스트가 이 Phase에서 GREEN으로 전환된다.

**1-a. 반올림 규칙 상수 정의 (리포트 3-4)**:

- [x] `backtest/constants.py`에 반올림 상수 4개 추가

```python
# --- 반올림 규칙 상수 (루트 CLAUDE.md "출력 데이터 반올림 규칙" 참조) ---
ROUND_PRICE: int = 6       # 가격 (종가, 시가, 밴드, 체결가 등)
ROUND_CAPITAL: int = 0     # 자본금 (equity, pnl) → 정수
ROUND_PERCENT: int = 2     # 백분율 (수익률, MDD, 승률, 드로우다운)
ROUND_RATIO: int = 4       # 비율 (0~1, buy_buffer_zone_pct, pnl_pct)
```

- [x] `run_single_backtest.py`: 리터럴 (`6`, `0`, `2`, `4`) → ROUND_* 상수 전환
- [x] `run_walkforward.py`: 리터럴 → ROUND_* 상수 전환
- [x] `run_portfolio_backtest.py`: 로컬 상수 (`_PRICE_ROUND` 등) 제거, ROUND_* 상수 전환
- [x] `run_param_plateau_all.py`: 리터럴 → ROUND_* 상수 전환 (해당 시)

**1-b. 컬럼명 상수 정의 (리포트 3-5, 확정 방침 5-3: B안 핵심 6개)**:

- [x] `backtest/constants.py`에 컬럼명 상수 6개 추가

```python
# --- 핵심 컬럼명 상수 (도메인 내 2개 이상 파일에서 사용) ---
COL_EQUITY: str = "equity"
COL_PNL: str = "pnl"
COL_ENTRY_DATE: str = "entry_date"
COL_EXIT_DATE: str = "exit_date"
COL_UPPER_BAND: str = "upper_band"
COL_LOWER_BAND: str = "lower_band"
```

- [x] `analysis.py`: `"equity"`, `"pnl"`, `"entry_date"`, `"exit_date"` → COL_* 전환
- [x] `engines/engine_common.py`: `"equity"`, `"pnl"`, `"entry_date"`, `"exit_date"` → COL_* 전환
- [x] `runners.py`: `"upper_band"`, `"lower_band"` → COL_* 전환
- [x] 스크립트 및 기타 해당 파일: COL_* 전환
- [x] TypedDict 키는 리터럴 유지, 주석으로 `# COL_EQUITY` 대응 관계 명시

**1-c. MA 컬럼명 생성 함수 (리포트 3-7)**:

- [x] `backtest/constants.py`에 함수 추가

```python
def ma_col_name(window: int) -> str:
    """MA 컬럼명을 생성한다. 예: ma_col_name(200) -> 'ma_200'"""
    return f"ma_{window}"
```

- [x] `backtest_engine.py` (175, 526행): `f"ma_{window}"` → `ma_col_name(window)` 전환
- [x] `analysis.py` (60행): `f"ma_{window}"` → `ma_col_name(window)` 전환
- [x] 기타 해당 위치: 전환

**1-d. 단순 수정 6건**:

- [x] **1-1**: `types.py` — `@dataclass` → `@dataclass(frozen=True)` (BufferStrategyParams)
- [x] **1-4**: `strategy_registry.py` (128행) — `_prepare_buy_and_hold_signal_df`에서 `return df` → `return df.copy()`
- [x] **2-9**: `walkforward.py` (155행) — `__import__("datetime").timedelta` → 상단 import에 `from datetime import timedelta` 추가
- [x] **2-11**: `portfolio_configs.py` — docstring `"정의돈"` → `"정의된"` 수정
- [x] **3-13**: `buffer_zone.py` — `resolve_buffer_params()`에 `if ma_window < 1: raise ValueError(...)` 검증 추가
- [x] **3-14**: `buffer_zone.py` (363, 456행) — `type: ignore[assignment]` → `assert` 또는 `cast` 사용

**Phase 0 테스트 전환**: frozen=True(1-1), ma_window 검증(3-13) 테스트 → GREEN

---

### Phase 2 — 공용 함수 추출 + 결과 디렉토리 정리 (그린 유지)

> 중복된 로직을 공용 함수로 추출하고 호출부를 전환한다.
> 16개 결과 디렉토리 상수를 제거하고 CONFIGS에 인라인 구성한다.
> Phase 0의 나머지 테스트(drawdown, csv_export, data_loader)가 이 Phase에서 GREEN으로 전환된다.

**2-a. drawdown_pct 공용 함수 추출 (리포트 3-2)**:

- [x] `analysis.py`에 함수 추가

```python
def calculate_drawdown_pct_series(equity_series: pd.Series) -> pd.Series:
    """에쿼티 시리즈로부터 drawdown_pct(%) 시리즈를 계산한다.

    Args:
        equity_series: 에쿼티 값 시리즈

    Returns:
        drawdown_pct 시리즈 (0 이하 값, 단위: %)
    """
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    return (equity_series - peak) / safe_peak * 100
```

- [x] `run_single_backtest.py` (132~135행): 인라인 계산 → `calculate_drawdown_pct_series()` 호출 전환
- [x] `run_walkforward.py` (362~365행): 인라인 계산 → `calculate_drawdown_pct_series()` 호출 전환

**2-b. csv_export.py 모듈 생성 (리포트 3-1, 3-15)**:

- [x] `src/qbt/backtest/csv_export.py` 신규 생성

```python
def prepare_trades_for_csv(trades_df: pd.DataFrame) -> pd.DataFrame:
    """거래 DataFrame에 holding_days 추가, 반올림, 정수 변환을 적용한다.

    빈 DataFrame 입력 시 빈 복사본을 반환한다.
    """

def calculate_change_pct(df: pd.DataFrame, close_col: str = COL_CLOSE) -> pd.Series:
    """전일대비 변동률(%) 시리즈를 계산한다."""
```

- [x] `prepare_trades_for_csv` 내부에서 ROUND_* 상수 사용
  - `entry_price` → ROUND_PRICE, `exit_price` → ROUND_PRICE
  - `pnl` → ROUND_CAPITAL (+ int 변환), `pnl_pct` → ROUND_RATIO
  - `buy_buffer_pct` → ROUND_RATIO (존재 시)
  - `holding_days`: `(exit_date - entry_date).days` 계산
- [x] `run_single_backtest.py` (166~193행): 인라인 trades 저장 → `prepare_trades_for_csv()` 호출 전환
- [x] `run_walkforward.py` (380~402행): 인라인 trades 저장 → `prepare_trades_for_csv()` 호출 전환
- [x] `run_portfolio_backtest.py` (85~110행): 인라인 trades 저장 → `prepare_trades_for_csv()` 호출 전환
- [x] `run_single_backtest.py`: 인라인 change_pct → `calculate_change_pct()` 호출 전환
- [x] `run_portfolio_backtest.py`: 인라인 change_pct → `calculate_change_pct()` 호출 전환

**2-c. load_signal_trade_pair 함수 추출 (리포트 3-3)**:

- [x] `utils/data_loader.py`에 함수 추가

```python
def load_signal_trade_pair(
    signal_path: Path, trade_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """시그널 + 매매 데이터를 로드하고, 경로가 다르면 겹치는 기간을 추출한다.

    Args:
        signal_path: 시그널 데이터 CSV 경로
        trade_path: 매매 데이터 CSV 경로

    Returns:
        (signal_df, trade_df) 튜플. 두 DataFrame은 독립 복사본.
    """
```

- [x] `runners.py` (119~127행): 인라인 로딩 → `load_signal_trade_pair()` 호출 전환
- [x] `run_walkforward.py`의 `_load_data` (78~92행): 인라인 로딩 → `load_signal_trade_pair()` 호출 전환
- [x] `run_param_plateau_all.py`의 `_load_asset_data` (146~167행): 인라인 로딩 → `load_signal_trade_pair()` 호출 전환

**2-d. 결과 디렉토리 상수 정리 (리포트 3-6, 확정 방침 5-4: A안)**:

- [x] `common_constants.py`에서 16개 상수 제거

제거 대상 (8 + 8 = 16개):

```
BUFFER_ZONE_TQQQ_RESULTS_DIR, BUFFER_ZONE_QQQ_RESULTS_DIR,
BUFFER_ZONE_SPY_RESULTS_DIR, BUFFER_ZONE_IWM_RESULTS_DIR,
BUFFER_ZONE_EFA_RESULTS_DIR, BUFFER_ZONE_EEM_RESULTS_DIR,
BUFFER_ZONE_GLD_RESULTS_DIR, BUFFER_ZONE_TLT_RESULTS_DIR,
BUY_AND_HOLD_QQQ_RESULTS_DIR, BUY_AND_HOLD_TQQQ_RESULTS_DIR,
BUY_AND_HOLD_SPY_RESULTS_DIR, BUY_AND_HOLD_IWM_RESULTS_DIR,
BUY_AND_HOLD_EFA_RESULTS_DIR, BUY_AND_HOLD_EEM_RESULTS_DIR,
BUY_AND_HOLD_GLD_RESULTS_DIR, BUY_AND_HOLD_TLT_RESULTS_DIR
```

- [x] `buffer_zone.py` CONFIGS: 8개 `result_dir` → `BACKTEST_RESULTS_DIR / "buffer_zone_tqqq"` 형태로 인라인 전환 (import 정리)
- [x] `buy_and_hold.py` CONFIGS: 8개 `result_dir` → `BACKTEST_RESULTS_DIR / "buy_and_hold_qqq"` 형태로 인라인 전환 (import 정리)
- [x] 테스트 코드에서 16개 상수를 import하는 곳 검색 → import 경로 수정 또는 인라인 전환

**Phase 0 테스트 전환**: drawdown, csv_export, data_loader 테스트 → GREEN

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] backtest CLAUDE.md 문서 불일치 수정 (리포트 1-5)
  - **(a)** `BufferZoneStrategy` 생성자 시그니처에서 `ma_type="ema"` 파라미터 기술 제거 (실제 클래스에 없음)
  - **(b)** `StrategySpec`의 `supports_single`, `supports_portfolio` 필드 기술을 실제 코드와 일치하도록 수정
- [x] backtest CLAUDE.md에 `csv_export.py` 모듈 설명 추가
- [x] tests CLAUDE.md에 `test_csv_export.py` 항목 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=451, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 상수-유틸 인프라 정비 (반올림, 컬럼명 상수화 + 공용 함수 추출)
2. 백테스트 / 중복 코드 제거 및 상수 관리 체계 정립
3. 백테스트 / csv_export, drawdown, data_loader 공용 함수 추출 + 상수 통일
4. 백테스트 / 리팩토링 — 상수 인프라 + 유틸 함수 + 결과 디렉토리 정리
5. 백테스트 / 코드 리뷰 Plan 1 — 상수/유틸 인프라 정비 및 단순 수정 15건

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| 16개 상수 제거 시 테스트/스크립트 import 깨짐 | 빌드 실패 | Phase 2에서 grep으로 모든 import 위치를 사전 검색 후 일괄 수정 |
| TypedDict 키에 COL_* 상수 사용 불가 | 이중 관리 발생 | 주석으로 COL_* 대응 관계 명시 (확정 방침 5-3) |
| frozen=True 적용 시 기존 코드에서 필드 변경하는 곳이 있으면 깨짐 | 런타임 에러 | 리포트 분석 결과 변경하는 코드 없음 확인. Phase 0 테스트로 사전 검증 |
| 공용 함수 추출 시 미세한 동작 차이 가능 | 결과 불일치 | Phase 0 테스트로 기대 동작 고정 후 추출 |
| `run_portfolio_backtest.py`의 trades 패턴이 다른 스크립트와 미묘하게 다름 | 통합 함수 설계 복잡화 | `buy_buffer_pct` 컬럼은 존재 시에만 조건부 반올림 (기존 패턴 유지) |

## 8) 메모(Notes)

### 탐사 중 발견된 추가 사항

- `run_walkforward.py` (335행): signal CSV 컬럼 목록에 `"change_pct"`를 포함하고 반올림 규칙도 정의하지만, 실제 `pct_change()` 계산을 수행하지 않음. `csv_export.py`의 `calculate_change_pct()` 도입 시 이 문제도 함께 해결 가능. 단, `run_walkforward.py`의 신호 CSV 저장 로직 전체는 Plan 3 범위(비즈니스 로직 이동)이므로, Plan 1에서는 함수만 제공하고 Plan 3에서 적용

### 설계 결정 사항

- **반올림 상수 배치**: `backtest/constants.py` (도메인 내 2개 이상 파일에서 사용, 상수 관리 3계층 규칙)
- **컬럼명 상수 배치**: `backtest/constants.py` (동일 근거)
- **`csv_export.py` 위치**: `src/qbt/backtest/csv_export.py` (백테스트 도메인 전용 CSV 변환)
- **`load_signal_trade_pair` 위치**: `src/qbt/utils/data_loader.py` (기존 `load_stock_data`, `extract_overlap_period`와 동일 모듈에서 조합)
- **`prepare_trades_for_csv` 설계**: DataFrame 변환만 수행, CSV 저장은 호출부 담당. 빈 DataFrame 입력 시 빈 복사본 반환
- **`calculate_change_pct` 설계**: `pd.Series` 반환. 호출부에서 `df["change_pct"] = calculate_change_pct(df)` 형태로 사용

### 후속 Plan 참고

- **Plan 2**: 이 Plan의 ROUND_* 상수, COL_* 상수, `calculate_drawdown_pct_series()` 활용
- **Plan 3**: 이 Plan의 `csv_export.py` 모듈, `load_signal_trade_pair()` 함수 활용

### 진행 로그 (KST)

- 2026-04-02 15:00: Plan 작성 완료 (Draft)
- 2026-04-02 18:30: 전체 Phase 완료, validate_project.py 통과 (passed=451, failed=0, skipped=0)

---
