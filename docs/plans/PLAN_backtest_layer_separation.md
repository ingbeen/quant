# Implementation Plan: 백테스트 계층 분리 + 구조 정리

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

**작성일**: 2026-04-02 23:50
**마지막 업데이트**: 2026-04-03 01:00
**관련 범위**: backtest/walkforward, backtest/strategies, backtest/engines, scripts/backtest
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

- [x] `_run_stitched_equity`를 `walkforward.py`의 공개 함수 `run_stitched_equity()`로 이동하고 `_ma_col` 캡슐화 위반 해소 (리포트 1-2a)
- [x] `_save_window_detail_csvs`의 비즈니스 로직을 `walkforward.py`의 `run_window_detail_backtests()`로 분리하고, CLI에는 CSV 저장만 유지 (리포트 1-2b)
- [x] 이동 시 trade_df 마스크를 독립 날짜 기반으로 적용 (리포트 1-2c, 2-3 패턴 연장)
- [x] `STRATEGY_CONFIG` 타입 주석을 실제 값과 일치하도록 수정 (리포트 2-10)
- [x] `portfolio_engine.py`의 데이터 로딩/필터링 중복을 헬퍼 함수로 추출 (리포트 3-9)
- [x] `check_buy`/`check_sell`의 밴드 계산/prev 갱신 중복을 `_update_bands`로 추출 (리포트 3-11, 2-6)
- [x] `resolve_buffer_params`에서 sources 딕셔너리 제거, `BufferStrategyParams`만 반환 (리포트 3-12, 확정 방침 5-5)
- [x] `PortfolioResult.config`의 빈 기본값 제거, 필수 파라미터로 변경 (리포트 2-12)
- [x] `strategies/__init__.py`의 `PendingOrder` re-export 제거 (리포트 3-18)

## 2) 비목표(Non-Goals)

- 새로운 비즈니스 기능 추가
- 기존 테스트의 대규모 리팩토링
- CSV/JSON 출력 스키마 변경
- 대시보드 앱(app_*.py) 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`REPORT_backtest_code_review.md`에서 식별된 계층 분리 위반, 구조적 중복, 미사용 코드를 해결한다. Plan 1(상수/유틸 인프라)과 Plan 2(버그 수정 + 엔진 통합)가 완료되어 새 상수, 공용 함수, 통합 엔진을 활용할 수 있는 상태이다.

**계층 분리 위반 (긴급)**:

- `run_walkforward.py`의 `_run_stitched_equity`(96-169행)에 핵심 WFO 비즈니스 로직이 포함. `SignalStrategy`의 private 속성 `_ma_col`에 직접 접근하며 `type: ignore[attr-defined]` 사용 (131, 134행)
- `run_walkforward.py`의 `_save_window_detail_csvs`(265-381행)에서 `BufferZoneStrategy`를 직접 인스턴스화하고 `run_backtest`를 호출하는 비즈니스 로직 수행. 밴드 계산, drawdown 계산 포함

**구조적 중복**:

- `portfolio_engine.py`의 `compute_portfolio_effective_start_date()`(62-152행)과 `run_portfolio_backtest()`(186-263행)에서 signal_cache 구성, 날짜 교집합, MA 워밍업 필터링이 동일하게 반복
- `check_buy`(315-410행)와 `check_sell`(412-460행)에서 `compute_bands()` 호출, prev 초기화 체크, `_prev_upper`/`_prev_lower` 갱신이 동일하게 반복

**미사용/불필요 코드**:

- `resolve_buffer_params`의 sources 딕셔너리가 항상 `"FIXED"`만 반환 — 함수 존재 의의가 "검증 + 객체 생성"으로 축소
- `PortfolioResult.config`에 의미 없는 빈 기본값 (`total_capital=0.0`, `result_dir=Path(".")`)
- `strategies/__init__.py`에서 `PendingOrder`를 re-export하지만 외부에서 이 경로로 import하는 코드 없음
- `STRATEGY_CONFIG` 타입 주석에 실제 값(`Path`)과 맞지 않는 타입(`list[int]`, `list[float]`, `None`) 포함

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`: 계층 분리 원칙, 데이터 불변성, YAGNI
- `src/qbt/backtest/CLAUDE.md`: 도메인 규칙, 모듈 구성, 체결 타이밍
- `src/qbt/utils/CLAUDE.md`: 유틸리티 패키지 설계 원칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (도메인 로직 포함 금지)
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 부동소수점 비교, 파일 격리)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `walkforward.run_stitched_equity()` 공개 함수가 존재하고 `_ma_col` 접근 없이 동작
- [x] `walkforward.run_window_detail_backtests()` 공개 함수가 존재하고 `WindowDetailData` 리스트 반환
- [x] `run_walkforward.py`의 `_run_stitched_equity`가 `walkforward.run_stitched_equity` 호출로 대체
- [x] `run_walkforward.py`의 `_save_window_detail_csvs`가 `walkforward.run_window_detail_backtests` 호출 + CSV 저장만 수행
- [x] `STRATEGY_CONFIG` 타입 주석이 `dict[str, dict[str, Path]]`로 수정
- [x] `_load_portfolio_data_with_common_period()` 헬퍼가 `portfolio_engine.py`에 존재하고 두 공개 함수가 사용
- [x] `BufferZoneStrategy._update_bands()` 메서드가 존재하고 `check_buy`/`check_sell`이 사용
- [x] `resolve_buffer_params`가 `BufferStrategyParams`만 반환 (sources 딕셔너리 제거)
- [x] `resolve_params_for_config`도 `BufferStrategyParams`만 반환
- [x] `PortfolioResult.config`에 기본값 없음 (필수 파라미터)
- [x] `strategies/__init__.py`에서 `PendingOrder` import/export 제거
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (backtest CLAUDE.md, tests CLAUDE.md)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**src/qbt/backtest/ (비즈니스 로직)**:

| 파일 | 변경 내용 |
|------|-----------|
| `walkforward.py` | `run_stitched_equity()`, `run_window_detail_backtests()`, `WindowDetailData` 추가 |
| `strategies/buffer_zone.py` | `resolve_buffer_params` 반환타입 변경, `resolve_params_for_config` 반환타입 변경, `BufferZoneStrategy._update_bands()` 추출 |
| `strategies/__init__.py` | `PendingOrder` import/export 제거 |
| `engines/portfolio_engine.py` | `_load_portfolio_data_with_common_period()` 헬퍼 추출 |
| `portfolio_types.py` | `PortfolioResult.config` 기본값 제거, 필드 순서 변경 |

**scripts/backtest/**:

| 파일 | 변경 내용 |
|------|-----------|
| `run_walkforward.py` | `_run_stitched_equity` → `walkforward.run_stitched_equity` 호출, `_save_window_detail_csvs` → `run_window_detail_backtests` 호출 + CSV 저장, `STRATEGY_CONFIG` 타입 수정 |

**tests/**:

| 파일 | 변경 내용 |
|------|-----------|
| `test_walkforward_schedule.py` | `_run_stitched_equity` importlib → `walkforward.run_stitched_equity` 직접 import |
| `test_buffer_zone.py` | `resolve_buffer_params`, `resolve_params_for_config` 반환타입 변경 반영 |
| `test_engine_common.py` | `PendingOrder` import 경로 확인 (이미 `engine_common`에서 직접 import) |

**문서**:

| 파일 | 변경 내용 |
|------|-----------|
| `src/qbt/backtest/CLAUDE.md` | walkforward.py에 `run_stitched_equity`, `run_window_detail_backtests` 추가, `_update_bands` 반영, resolve_buffer_params 시그니처 변경, PortfolioResult 변경 |
| `tests/CLAUDE.md` | 변경된 테스트 반영 |
| `README.md` | 변경 없음 (내부 리팩토링) |

### 데이터/결과 영향

- 출력 스키마 변경 없음 (동일한 CSV/JSON 출력)
- 기존 결과와 수치 차이 없음 (동작 변경 없는 리팩토링)
- 예외: `run_stitched_equity`에서 trade_df 마스크를 독립 날짜 기반으로 변경하면 이론적으로 미세한 차이 가능하나, 현재 데이터에서는 signal_df와 trade_df의 날짜가 항상 정합하므로 실질 차이 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 고정 (레드)

> 새로운 공개 함수, 변경될 반환 타입의 계약을 테스트로 먼저 고정한다.
> 구현이 아직 없으므로 레드(실패) 상태가 허용된다.

**작업 내용**:

- [x] `test_walkforward_schedule.py`에 `run_stitched_equity` 직접 import 테스트 추가
  - `from qbt.backtest.walkforward import run_stitched_equity` 가능 여부 검증
  - 기존 `test_stitched_equity_ema_matches_full_history_ema` 테스트를 importlib 대신 직접 import로 변경 (이동 후 GREEN 전환 대상)

- [x] `test_buffer_zone.py`에 `resolve_buffer_params` 반환타입 테스트 추가
  - `resolve_buffer_params(200, 0.03, 0.05, 3)` → 반환값이 `BufferStrategyParams` 인스턴스인지 (tuple이 아닌지) 검증
  - `resolve_params_for_config(config)` → 반환값이 `BufferStrategyParams` 인스턴스인지 검증

---

### Phase 1 — 단독 수정 (그린 전환 1)

> 독립적으로 수정 가능한 구조 정리를 처리한다.
> Phase 0의 resolve_buffer_params 테스트가 이 Phase에서 GREEN으로 전환된다.

**1-a. resolve_buffer_params sources 제거 (리포트 3-12, 확정 방침 5-5)**:

- [x] `buffer_zone.py` `resolve_buffer_params` (59-114행):
  - 반환타입: `tuple[BufferStrategyParams, dict[str, str]]` → `BufferStrategyParams`
  - `sources` 딕셔너리 생성/반환 코드 제거
  - docstring 업데이트 (Returns 섹션)

- [x] `buffer_zone.py` `resolve_params_for_config` (240-260행):
  - 반환타입: `tuple[BufferStrategyParams, dict[str, str]]` → `BufferStrategyParams`
  - docstring 업데이트

- [x] 호출부 수정:
  - `runners.py:126`: `params, sources = resolve_params_for_config(config)` → `params = resolve_params_for_config(config)`
  - `run_param_plateau_all.py:202,223,246,270`: `params, _ = resolve_params_for_config(config)` → `params = resolve_params_for_config(config)`

- [x] `test_buffer_zone.py` 기존 테스트 수정:
  - `params, sources = resolve_params_for_config(...)` → `params = resolve_params_for_config(...)`
  - `params, _sources = resolve_buffer_params(...)` → `params = resolve_buffer_params(...)`
  - sources 관련 assert 제거

**1-b. _update_bands 추출 (리포트 3-11, 2-6)**:

- [x] `buffer_zone.py` `BufferZoneStrategy`에 `_update_bands` 메서드 추가

```python
def _update_bands(
    self, signal_df: pd.DataFrame, i: int,
) -> tuple[float, float, float, float, float, float] | None:
    """밴드를 계산하고 prev 상태를 갱신한다.

    최초 호출(i=0 또는 prev 미초기화) 시 초기화 후 None 반환.
    정상 상태이면 (prev_close, cur_close, prev_upper, cur_upper, prev_lower, cur_lower)
    반환 후 prev 상태를 현재 값으로 갱신한다.

    Args:
        signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
        i: 현재 인덱스 (0부터 시작)

    Returns:
        None이면 초기화 완료 후 신호 없음.
        6-tuple이면 신호 판단에 필요한 값.
    """
    row = signal_df.iloc[i]
    ma_val = float(row[self._ma_col])
    cur_upper, cur_lower = compute_bands(
        ma_val, self._buy_buffer_pct, self._sell_buffer_pct
    )

    # 최초 호출 처리
    if self._prev_upper is None or self._prev_lower is None:
        if i == 0:
            self._prev_upper = cur_upper
            self._prev_lower = cur_lower
            return None
        else:
            self._init_prev_from_row(signal_df, i - 1)

    assert self._prev_upper is not None and self._prev_lower is not None
    prev_upper = self._prev_upper
    prev_lower = self._prev_lower
    prev_close = float(signal_df.iloc[i - 1][COL_CLOSE])
    cur_close = float(row[COL_CLOSE])

    # prev 상태를 현재 값으로 갱신
    self._prev_upper = cur_upper
    self._prev_lower = cur_lower

    return (prev_close, cur_close, prev_upper, cur_upper, prev_lower, cur_lower)
```

- [x] `check_buy`(315-410행) 리팩토링: 밴드 계산/초기화/갱신 부분을 `_update_bands()` 호출로 대체

변경 후 구조:
```python
def check_buy(self, signal_df, i, current_date):
    ctx = self._update_bands(signal_df, i)
    if ctx is None:
        return False
    prev_close, cur_close, prev_upper, cur_upper, _, _ = ctx

    # 이하 신호 판단 로직 (hold_days 상태머신) 기존과 동일
```

- [x] `check_sell`(412-460행) 리팩토링: 밴드 계산/초기화/갱신 부분을 `_update_bands()` 호출로 대체

변경 후 구조:
```python
def check_sell(self, signal_df, i):
    ctx = self._update_bands(signal_df, i)
    if ctx is None:
        return False
    prev_close, cur_close, _, _, prev_lower, cur_lower = ctx

    return detect_sell_signal(prev_close, cur_close, prev_lower, cur_lower)
```

**1-c. PortfolioResult.config 빈 기본값 제거 (리포트 2-12)**:

- [x] `portfolio_types.py` `PortfolioResult`: `config` 필드에서 `default_factory` 제거
  - `config`가 기본값 없는 필수 필드가 되므로 `per_asset` (기본값 있음) 앞으로 이동

변경 전:
```python
per_asset: list[PortfolioAssetResult] = field(default_factory=list)
config: PortfolioConfig = field(default_factory=lambda: PortfolioConfig(...))
params_json: dict[str, Any] = field(default_factory=dict)
```

변경 후:
```python
config: PortfolioConfig
per_asset: list[PortfolioAssetResult] = field(default_factory=list)
params_json: dict[str, Any] = field(default_factory=dict)
```

- [x] `portfolio_engine.py:453` 호출부 확인 — 이미 `config=config`를 명시적으로 전달하므로 변경 불필요

**1-d. PendingOrder re-export 제거 (리포트 3-18)**:

- [x] `strategies/__init__.py`:
  - `from qbt.backtest.engines.engine_common import PendingOrder` 제거
  - `__all__`에서 `"PendingOrder"` 제거
  - docstring에서 `PendingOrder` 관련 설명 업데이트

- [x] 외부 import 영향 확인: `from qbt.backtest.strategies import PendingOrder` 패턴이 프로젝트 내 없음 확인 완료 (Grep 검증 완료)

**1-e. STRATEGY_CONFIG 타입 주석 정확화 (리포트 2-10)**:

- [x] `run_walkforward.py:65` 타입 주석 수정

변경 전:
```python
STRATEGY_CONFIG: dict[str, dict[str, Path | list[int] | list[float] | None]] = {
```

변경 후:
```python
STRATEGY_CONFIG: dict[str, dict[str, Path]] = {
```

**Phase 0 테스트 전환**: resolve_buffer_params 반환타입 테스트 → GREEN

---

### Phase 2 — 계층 분리 + 구조 정리 (그린 전환 2)

> CLI에서 비즈니스 로직을 분리하여 `walkforward.py`로 이동하고,
> 포트폴리오 엔진의 데이터 로딩 중복을 제거한다.
> Phase 0의 `run_stitched_equity` 테스트가 이 Phase에서 GREEN으로 전환된다.

**2-a. run_stitched_equity → walkforward.py (리포트 1-2a)**:

- [x] `walkforward.py`에 `run_stitched_equity()` 함수 추가

```python
def run_stitched_equity(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    window_results: list[WfoWindowResultDict],
    initial_capital: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """WFO 결과의 params_schedule로 Stitched Equity를 생성한다.

    첫 OOS 시작일부터 마지막 OOS 종료일까지 연속 자본곡선을 생성한다.
    전체 signal_df에 먼저 MA를 계산하여 EMA 연속성을 보장한 후 OOS 구간만 슬라이싱한다.

    Args:
        signal_df: 시그널용 원본 DataFrame (MA 미포함)
        trade_df: 매매용 원본 DataFrame
        window_results: WFO 윈도우 결과 리스트
        initial_capital: 초기 자본금

    Returns:
        (equity_df, summary) 튜플.
        summary에 "window_end_equities" 키 포함 (Profit Concentration 계산용).
    """
```

핵심 변경:
- `_ma_col` 직접 접근 제거: `initial_params._ma_col` 대신 `{wr["best_ma_window"] for wr in window_results}`로 MA 윈도우 수집
- trade_df 마스크 독립 날짜 기반 적용 (Plan 2의 2-3 패턴 연장):
  ```python
  oos_trade_mask = (trade_df[COL_DATE] >= oos_start_date) & (trade_df[COL_DATE] <= oos_end_date)
  oos_trade = trade_df[oos_trade_mask].reset_index(drop=True)
  ```
- 기존 `from datetime import date as date_type` 인라인 import → 모듈 상단 import 활용

- [x] `run_walkforward.py`의 `_run_stitched_equity` 함수를 `walkforward.run_stitched_equity` 호출로 대체

변경 전:
```python
equity_df, stitched_summary = _run_stitched_equity(signal_df, trade_df, window_results, initial_capital)
```

변경 후:
```python
from qbt.backtest.walkforward import run_stitched_equity
equity_df, stitched_summary = run_stitched_equity(signal_df, trade_df, window_results, initial_capital)
```

- [x] `run_walkforward.py`에서 `_run_stitched_equity` 함수 본문 삭제

**2-b. run_window_detail_backtests → walkforward.py (리포트 1-2b)**:

- [x] `walkforward.py`에 `WindowDetailData` dataclass 추가

```python
@dataclass
class WindowDetailData:
    """윈도우별 상세 백테스트 결과 데이터."""
    window_idx: int
    signal_df: pd.DataFrame   # MA 컬럼 포함
    equity_df: pd.DataFrame   # upper_band, lower_band, drawdown_pct 포함
    trades_df: pd.DataFrame
```

- [x] `walkforward.py`에 `run_window_detail_backtests()` 함수 추가

```python
def run_window_detail_backtests(
    window_results: list[WfoWindowResultDict],
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    initial_capital: float,
) -> list[WindowDetailData]:
    """각 윈도우의 best params로 IS_start~OOS_end 백테스트를 실행한다.

    캔들차트 + Buy/Sell 마커 시각화에 필요한 데이터를 생성한다.
    equity_df에 밴드(upper_band, lower_band)와 drawdown_pct를 포함한다.

    Args:
        window_results: WFO 윈도우 결과 리스트
        signal_df: 시그널용 원본 DataFrame (전체 기간)
        trade_df: 매매용 원본 DataFrame (전체 기간)
        initial_capital: 초기 자본금

    Returns:
        윈도우별 WindowDetailData 리스트 (빈 윈도우는 건너뜀)
    """
```

핵심 로직 (CLI에서 이동):
1. 모든 윈도우의 MA 윈도우 수집 → 전체 signal_df에 사전 계산 (EMA 연속성)
2. 윈도우별: IS_start~OOS_end 슬라이싱 → BufferZoneStrategy 생성 → run_backtest 실행
3. 밴드 계산 + drawdown 계산 → equity_df에 반영
4. trade_df 마스크 독립 날짜 기반 적용

- [x] `run_walkforward.py`의 `_save_window_detail_csvs` 리팩토링

변경 후:
```python
def _save_window_detail_csvs(
    window_results: list[WfoWindowResultDict],
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    result_dir: Path,
    mode_dir_name: str,
    initial_capital: float,
) -> None:
    window_dir = result_dir / mode_dir_name
    window_dir.mkdir(parents=True, exist_ok=True)

    # 비즈니스 로직은 walkforward 모듈에 위임
    details = run_window_detail_backtests(
        window_results, signal_df, trade_df, initial_capital,
    )

    # CSV 저장만 수행 (CLI 책임)
    for detail in details:
        idx = detail.window_idx
        # signal CSV
        signal_cols = [COL_DATE, "Open", "High", "Low", "Close", ...]
        signal_export = ...  # 포맷팅 + 반올림
        signal_export.to_csv(window_dir / f"w{idx:02d}_signal.csv", index=False)

        # equity CSV
        equity_export = ...  # 반올림
        equity_export.to_csv(window_dir / f"w{idx:02d}_equity.csv", index=False)

        # trades CSV
        prepare_trades_for_csv(detail.trades_df).to_csv(
            window_dir / f"w{idx:02d}_trades.csv", index=False
        )
```

**2-c. portfolio_engine.py 데이터 로딩 중복 → 헬퍼 추출 (리포트 3-9)**:

- [x] `portfolio_engine.py`에 `_load_portfolio_data_with_common_period()` 헬퍼 함수 추가

```python
def _load_portfolio_data_with_common_period(
    config: PortfolioConfig,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, AssetSlotConfig], int]:
    """자산별 데이터 로딩 → 공통 기간 필터링 → MA 워밍업 인덱스 계산.

    signal_data_path 기준 캐시, 날짜 교집합 필터링, MA 워밍업 구간 계산을
    한 곳에서 수행한다.

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        (asset_signal_dfs, asset_trade_dfs, slot_dict, valid_start_index) 튜플.
        valid_start_index: MA 워밍업 완료 후 첫 유효 인덱스.

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
```

- [x] `compute_portfolio_effective_start_date()`를 헬퍼 호출로 리팩토링

변경 후:
```python
def compute_portfolio_effective_start_date(config: PortfolioConfig) -> date:
    asset_signal_dfs, asset_trade_dfs, _, valid_start = (
        _load_portfolio_data_with_common_period(config)
    )
    first_trade_df = next(iter(asset_trade_dfs.values()))
    first_filtered = first_trade_df.iloc[valid_start:].reset_index(drop=True)
    if len(first_filtered) < 1:
        raise ValueError("유효 데이터 부족: MA 워밍업 후 데이터가 없습니다.")
    return date(
        first_filtered[COL_DATE].iloc[0].year,
        first_filtered[COL_DATE].iloc[0].month,
        first_filtered[COL_DATE].iloc[0].day,
    )
```

- [x] `run_portfolio_backtest()`를 헬퍼 호출로 리팩토링

변경 후 (데이터 로딩 부분):
```python
def run_portfolio_backtest(config, start_date=None):
    validate_portfolio_config(config)
    asset_signal_dfs, asset_trade_dfs, slot_dict, valid_start = (
        _load_portfolio_data_with_common_period(config)
    )
    # valid_start 적용
    for asset_id in asset_signal_dfs:
        asset_signal_dfs[asset_id] = asset_signal_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)
        asset_trade_dfs[asset_id] = asset_trade_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)
    # start_date 필터 (기존 로직 유지)
    if start_date is not None:
        ...
    # 이하 기존 로직 동일
```

- [x] `test_walkforward_schedule.py` 기존 `test_stitched_equity_ema_matches_full_history_ema` 테스트 업데이트: importlib → 직접 import

**Phase 0 테스트 전환**: `run_stitched_equity` 직접 import 테스트 → GREEN

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] backtest CLAUDE.md 업데이트
  - walkforward.py 섹션: `run_stitched_equity`, `run_window_detail_backtests`, `WindowDetailData` 추가
  - buffer_zone.py 섹션: `resolve_buffer_params` 반환타입 변경, `_update_bands` 추가
  - portfolio_types.py 섹션: `PortfolioResult.config` 필수 파라미터 반영
  - strategies/__init__.py 섹션: `PendingOrder` export 제거 반영
- [x] tests CLAUDE.md 업데이트 (해당 시)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=465, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 계층 분리 — CLI 비즈니스 로직을 walkforward.py로 이동 + 구조 정리
2. 백테스트 / run_walkforward.py 계층 위반 해소 + resolve_buffer_params 간소화
3. 백테스트 / stitched equity/window detail 비즈니스 로직 이동 + _update_bands 추출
4. 백테스트 / 코드 리뷰 Plan 3 — 계층 분리, 중복 제거, 미사용 코드 정리
5. 백테스트 / CLI→src 비즈니스 로직 이동 + portfolio 데이터 로딩 헬퍼 추출

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| `run_stitched_equity` 이동 시 EMA 연속성 보장 미충족 | stitched equity 수치 차이 | 기존 테스트(`test_stitched_equity_ema_matches_full_history_ema`)가 EMA 일치성 검증. 이동 후 동일 테스트 통과 확인 |
| `resolve_buffer_params` 반환타입 변경 시 호출부 누락 | 런타임 에러 | Grep으로 모든 호출부 사전 검색 완료 (buffer_zone.py, runners.py, run_param_plateau_all.py, test_buffer_zone.py) |
| `_update_bands` 추출 시 hold_days 상태머신 로직 회귀 | 매수 신호 오동작 | 기존 check_buy/check_sell 테스트(test_buffer_zone_execution_rules.py)가 신호 정확성 검증 |
| `PortfolioResult.config` 필드 순서 변경 시 위치 인자 사용 코드 깨짐 | 런타임 에러 | 유일한 생성 코드(portfolio_engine.py:453)가 키워드 인자 사용. 위치 인자 없음 확인 |
| portfolio 헬퍼 추출 시 두 함수 동작 미세 차이 미발견 | 유효 시작일 계산 오류 | 기존 portfolio 시나리오 테스트가 회귀 방지 |

## 8) 메모(Notes)

### 설계 결정

- **`_ma_col` 접근 제거**: `build_params_schedule()` 반환의 `SignalStrategy` 객체에서 private `_ma_col`을 추출하는 대신, `window_results`의 `best_ma_window` 필드에서 직접 MA 윈도우를 수집한다. 이렇게 하면 `type: ignore[attr-defined]` 2건이 완전 해소된다
- **`WindowDetailData` dataclass**: 윈도우별 백테스트 결과를 담는 경량 컨테이너. `walkforward.py` → CLI로 데이터를 전달하는 경계 인터페이스 역할
- **`_update_bands` 위치**: `BufferZoneStrategy` 내부 메서드로 배치. 외부에서 독립 사용할 가능성 없음. check_buy와 check_sell 모두 동일하게 양쪽 prev 상태를 갱신하므로 2-6의 상태 비동기화 우려 해소
- **`_load_portfolio_data_with_common_period` 설계**: valid_start 인덱스까지만 계산하고 실제 슬라이싱은 호출부에서 수행. `compute_portfolio_effective_start_date`는 인덱스를 날짜로 변환만, `run_portfolio_backtest`는 슬라이싱 + 추가 start_date 필터 적용

### Plan 1, 2와의 의존 관계

- `calculate_drawdown_pct_series()`: Plan 1에서 `analysis.py`에 추가됨. 이 Plan의 `run_window_detail_backtests`에서 사용
- `prepare_trades_for_csv()`: Plan 1에서 `csv_export.py`에 추가됨. 이 Plan의 CLI 저장 로직에서 사용
- `ma_col_name()`: Plan 1에서 `constants.py`에 추가됨. 이 Plan의 `run_stitched_equity`에서 `_ma_col` 대신 사용
- `COL_UPPER_BAND`, `COL_LOWER_BAND`: Plan 1에서 `constants.py`에 추가됨. 이 Plan의 `run_window_detail_backtests`에서 사용
- `ROUND_*` 상수: Plan 1에서 정의됨. 이 Plan의 CSV 포맷팅에서 사용
- `execute_buy_order`/`execute_sell_order`: Plan 2에서 순수 계산 함수로 변경됨. 이 Plan과 직접 관련 없음

### 진행 로그 (KST)

- 2026-04-02 23:50: Plan 3 계획서 작성 완료
- 2026-04-03 01:00: 전체 Phase 완료, validate_project.py 통과 (passed=465, failed=0, skipped=0)

---
