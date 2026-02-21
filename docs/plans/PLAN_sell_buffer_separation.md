# Implementation Plan: 버퍼존 매수/매도 버퍼 분리 + 청산 기반 동적 조정

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-21 00:00
**마지막 업데이트**: 2026-02-21 00:00
**관련 범위**: backtest
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [ ] 매수 버퍼(`buy_buffer_zone_pct`)와 매도 버퍼(`sell_buffer_zone_pct`)를 분리하여 독립적으로 제어
- [ ] 기존 `buffer_zone_pct`를 `buy_buffer_zone_pct`로 전체 rename (상수/TypedDict/DataClass/함수 파라미터 포함)
- [ ] 동적 버퍼 확장을 upper_band(매수 신호)에만 적용, lower_band(매도 신호)는 고정
- [ ] 동적 조정 기준을 진입일(entry) → 청산일(exit) 기반으로 변경 + 가산 누적 지원
- [ ] 새 파라미터(`sell_buffer_zone_pct`)를 그리드 서치에 포함 (탐색 범위 `[0.01, 0.02, 0.03, 0.04, 0.05]`)

## 2) 비목표(Non-Goals)

- 변동성 기반 포지션 사이징 (별도 계획)
- ATR 트레일링 스탑 (별도 계획)
- 그리드 서치 목적함수 변경 (CAGR→Calmar, 별도 계획)
- 워크포워드 검증 (별도 계획)
- 기존 결과 CSV 파일의 소급 마이그레이션 (재실행으로 재생성)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `buffer_zone_pct` 단일 값이 upper_band와 lower_band를 동시에 결정한다.

```
upper_band = MA × (1 + buffer_zone_pct)   # 매수 신호 기준
lower_band = MA × (1 - buffer_zone_pct)   # 매도 신호 기준
```

이로 인해 2가지 부작용이 발생한다:

**부작용 1 — 진입 직후 lower_band 하락 (MDD 악화 유발)**

```
# 진입 다음날부터 recent_buy_count=1 → current_buffer_pct=0.05
lower_band = MA × (1 - 0.05) = MA × 0.95   ← 더 낮아짐
```

진입 후 60일간 매도 신호가 더 늦게 발생하여 MDD를 악화시킬 수 있다.

**부작용 2 — 동적 조정 타이밍 오류**

현재는 `entry_dates`(매수일) 기반으로 최근 카운트를 계산한다. 진입 직후부터 60일간 밴드가 확장된다.
사용자가 원하는 것: 청산 후 60일간 **재진입 기준**을 더 높이는 것 (재진입 억제).

**원하는 새 동작:**

```
# 고정 (always):  lower_band = MA × (1 - sell_buffer_zone_pct)  # 매도 신호 타이트, 고정
# 동적 (exit 후): upper_band = MA × (1 + buy_buffer_zone_pct)   # 재진입 기준 동적 확장
```

가산 누적: 60일 내 청산이 2회 발생하면 `recent_sell_count=2` → 더 높은 upper_band.

### 전체 rename 범위

`buffer_zone_pct` → `buy_buffer_zone_pct`로 변경되는 대상 목록:

| 변경 전 | 변경 후 | 위치 |
|---|---|---|
| `DEFAULT_BUFFER_ZONE_PCT` | `DEFAULT_BUY_BUFFER_ZONE_PCT` | `constants.py` |
| `MIN_BUFFER_ZONE_PCT` | `MIN_BUY_BUFFER_ZONE_PCT` | `constants.py` |
| `DEFAULT_BUFFER_ZONE_PCT_LIST` | `DEFAULT_BUY_BUFFER_ZONE_PCT_LIST` | `constants.py` |
| `COL_BUFFER_ZONE_PCT` | `COL_BUY_BUFFER_ZONE_PCT` | `constants.py` |
| `DISPLAY_BUFFER_ZONE = "버퍼존"` | `DISPLAY_BUY_BUFFER_ZONE = "매수버퍼존"` | `constants.py` |
| `BestGridParams.buffer_zone_pct` | `buy_buffer_zone_pct` | `types.py` |
| `BufferStrategyParams.buffer_zone_pct` | `buy_buffer_zone_pct` | `buffer_zone_helpers.py` |
| `GridSearchResult.buffer_zone_pct` | `buy_buffer_zone_pct` | `buffer_zone_helpers.py` |
| `OVERRIDE_BUFFER_ZONE_PCT` | `OVERRIDE_BUY_BUFFER_ZONE_PCT` | `buffer_zone_tqqq.py`, `buffer_zone_qqq.py` |
| `override_buffer_zone_pct` (함수 파라미터) | `override_buy_buffer_zone_pct` | `buffer_zone_helpers.py` |
| `buffer_zone_pct_list` (함수 파라미터) | `buy_buffer_zone_pct_list` | `buffer_zone_helpers.py`, `run_grid_search.py` |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)
- [루트 CLAUDE.md](../../CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [ ] `buffer_zone_pct` → `buy_buffer_zone_pct` 전체 rename 완료 (상수/TypedDict/DataClass/함수/테스트)
- [ ] `sell_buffer_zone_pct` 파라미터가 `BufferStrategyParams`에 추가됨
- [ ] upper_band에만 동적 확장 적용, lower_band는 고정 (`sell_buffer_zone_pct`) 검증
- [ ] `_calculate_recent_sell_count`가 exit_dates 기반으로 동작함 (가산 포함)
- [ ] 그리드 서치가 `buy_buffer_zone_pct_list` 및 `sell_buffer_zone_pct_list=[0.01~0.05]`를 탐색함
- [ ] `BestGridParams`, `load_best_grid_params`, `resolve_buffer_params` 업데이트
- [ ] equity.csv: `buffer_zone_pct` → `buy_buffer_pct` + `sell_buffer_pct` (스키마 변경)
- [ ] trades.csv: `recent_buy_count` → `recent_sell_count` (컬럼명 변경)
- [ ] grid_results.csv: `버퍼존` → `매수버퍼존`, `매도버퍼존` 추가 (스키마 변경)
- [ ] 회귀/신규 테스트 추가 및 통과
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] CLAUDE.md 업데이트 (rename 및 함수명 변경 반영)
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**비즈니스 로직:**
- `src/qbt/backtest/constants.py` — buy/sell buffer 상수 rename 및 신규 추가
- `src/qbt/backtest/types.py` — `BestGridParams` rename
- `src/qbt/backtest/analysis.py` — `_GRID_CSV_REQUIRED_COLUMNS`, `load_best_grid_params` 업데이트
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — 핵심 변경 (TypedDict, DataClass, 함수 전체)
- `src/qbt/backtest/strategies/buffer_zone_tqqq.py` — OVERRIDE 상수 rename, `resolve_params`, `params_json`
- `src/qbt/backtest/strategies/buffer_zone_qqq.py` — 동일

**스크립트:**
- `scripts/backtest/run_grid_search.py` — buy/sell buffer 파라미터 rename 및 추가
- `scripts/backtest/run_single_backtest.py` — 컬럼 rounding 업데이트
- `scripts/backtest/app_single_backtest.py` — 레이블 딕셔너리 업데이트

**테스트:**
- `tests/test_buffer_zone_helpers.py` — 전체 `BufferStrategyParams` rename 및 신규 테스트 추가

**문서:**
- `src/qbt/backtest/CLAUDE.md` — rename 및 동적 조정 로직 업데이트

### 데이터/결과 영향

- `equity.csv` 스키마 변경: `buffer_zone_pct` → `buy_buffer_pct`, `sell_buffer_pct` 추가
- `trades.csv` 스키마 변경: `recent_buy_count` → `recent_sell_count`
- `grid_results.csv` 스키마 변경: `버퍼존` → `매수버퍼존`, `매도버퍼존` 컬럼 추가
- **기존 storage 파일은 재실행(run_single_backtest, run_grid_search)으로 재생성 필요**

### 그리드 서치 탐색 공간

| 파라미터 | 범위 | 개수 |
|---|---|---|
| `ma_window` | [100, 150, 200, 250] | 4 |
| `buy_buffer_zone_pct` | [0.01, 0.02, 0.03, 0.04, 0.05] | 5 |
| `sell_buffer_zone_pct` | [0.01, 0.02, 0.03, 0.04, 0.05] | 5 |
| `hold_days` | [0, 1, 2, 3, 4, 5] | 6 |
| `recent_months` | [0, 2, 4, 6, 8, 10, 12] | 7 |
| **합계** | | **4 × 5 × 5 × 6 × 7 = 4,200** |

---

## 6) 단계별 계획(Phases)

### Phase 0 — 핵심 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

#### 인터페이스/정책 정의

새 동작 계약:
1. `BufferStrategyParams`는 `buy_buffer_zone_pct`와 `sell_buffer_zone_pct` 두 필드를 가져야 한다
2. `_calculate_recent_sell_count(exit_dates, current_date, recent_months)` 함수가 존재해야 한다
3. 가산 계약: 60일 내 청산 2회 → `count=2`
4. upper_band는 `recent_sell_count` 기반으로 동적 확장, lower_band는 `sell_buffer_zone_pct` 고정
5. 청산 발생 → `all_exit_dates`에 기록 → 다음 루프에서 `recent_sell_count` 반영

- [ ] `tests/test_buffer_zone_helpers.py`에 `TestCalculateRecentSellCount` 클래스 추가
  - `_calculate_recent_sell_count` import 시도 (실패 예상 — 레드)
  - 기본 동작: 지정 기간 내 exit_date만 카운트
  - 가산 동작: 60일 내 2회 청산 → count=2
  - 경계: `recent_months=0` → count=0
  - 경계: 현재 날짜 당일 청산은 미포함 (`d < current_date`)
- [ ] `BufferStrategyParams`에 `buy_buffer_zone_pct` 및 `sell_buffer_zone_pct` 필드 테스트 (AttributeError 예상 — 레드)
- [ ] upper_band 동적 확장, lower_band 고정 계약 테스트 (실패 예상 — 레드)
  - 청산 전: `upper_band = MA × (1 + base_buy_buffer)`, `lower_band = MA × (1 - sell_buffer)` 고정
  - 청산 후 (recent_months 내): `upper_band = MA × (1 + (base + 0.01))`
  - `lower_band`는 청산 전후 동일

**Validation**: Phase 0은 의도적 실패 허용 (레드). 다음 Phase에서 그린 전환.

---

### Phase 1 — constants.py 및 types.py 확장 (rename + 신규 추가)

**작업 내용**:

#### `src/qbt/backtest/constants.py` — rename + 신규 상수 추가

```python
# --- 버퍼존 전략 기본값 (rename) ---
DEFAULT_BUY_BUFFER_ZONE_PCT: Final = 0.03    # 매수 버퍼존 기본값 (기존 DEFAULT_BUFFER_ZONE_PCT)
DEFAULT_SELL_BUFFER_ZONE_PCT: Final = 0.04   # 매도 버퍼존 기본값 (신규)

# --- 제약 조건 (rename) ---
MIN_BUY_BUFFER_ZONE_PCT: Final = 0.01    # 기존 MIN_BUFFER_ZONE_PCT
MIN_SELL_BUFFER_ZONE_PCT: Final = 0.01   # 신규

# --- 그리드 서치 탐색 범위 (rename + 신규) ---
DEFAULT_BUY_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.02, 0.03, 0.04, 0.05]   # 기존 rename
DEFAULT_SELL_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.02, 0.03, 0.04, 0.05]  # 신규

# --- DataFrame 컬럼명 내부용 (rename + 신규) ---
COL_BUY_BUFFER_ZONE_PCT: Final = "buy_buffer_zone_pct"   # 기존 COL_BUFFER_ZONE_PCT rename
COL_SELL_BUFFER_ZONE_PCT: Final = "sell_buffer_zone_pct"  # 신규

# --- 그리드 서치 결과 CSV 출력용 레이블 (rename + 신규) ---
DISPLAY_BUY_BUFFER_ZONE: Final = "매수버퍼존"   # 기존 DISPLAY_BUFFER_ZONE = "버퍼존" rename
DISPLAY_SELL_BUFFER_ZONE: Final = "매도버퍼존"  # 신규
```

- [ ] 기존 `DEFAULT_BUFFER_ZONE_PCT` → `DEFAULT_BUY_BUFFER_ZONE_PCT`로 rename
- [ ] 기존 `MIN_BUFFER_ZONE_PCT` → `MIN_BUY_BUFFER_ZONE_PCT`로 rename
- [ ] 기존 `DEFAULT_BUFFER_ZONE_PCT_LIST` → `DEFAULT_BUY_BUFFER_ZONE_PCT_LIST`로 rename
- [ ] 기존 `COL_BUFFER_ZONE_PCT` → `COL_BUY_BUFFER_ZONE_PCT`로 rename
- [ ] 기존 `DISPLAY_BUFFER_ZONE = "버퍼존"` → `DISPLAY_BUY_BUFFER_ZONE = "매수버퍼존"`으로 rename
- [ ] `DEFAULT_SELL_BUFFER_ZONE_PCT`, `MIN_SELL_BUFFER_ZONE_PCT` 신규 추가
- [ ] `DEFAULT_SELL_BUFFER_ZONE_PCT_LIST`, `COL_SELL_BUFFER_ZONE_PCT`, `DISPLAY_SELL_BUFFER_ZONE` 신규 추가

#### `src/qbt/backtest/types.py` 업데이트

```python
class BestGridParams(TypedDict):
    ma_window: int
    buy_buffer_zone_pct: float    # 기존 buffer_zone_pct rename
    sell_buffer_zone_pct: float   # 신규
    hold_days: int
    recent_months: int
```

- [ ] `BestGridParams.buffer_zone_pct` → `buy_buffer_zone_pct` rename
- [ ] `BestGridParams`에 `sell_buffer_zone_pct: float` 추가

---

### Phase 2 — buffer_zone_helpers.py 핵심 변경

**작업 내용**:

#### TypedDicts 업데이트

- [ ] `EquityRecord`: `buffer_zone_pct: float` → `buy_buffer_pct: float` + `sell_buffer_pct: float` 분리
- [ ] `TradeRecord`: `recent_buy_count: int` → `recent_sell_count: int`
- [ ] `GridSearchResult`: `buffer_zone_pct: float` → `buy_buffer_zone_pct: float` rename + `sell_buffer_zone_pct: float` 추가
- [ ] `HoldState`: `buffer_pct` 필드 주석에 "매수 버퍼 (buy buffer)" 명시
- [ ] `PendingOrder`: `buffer_zone_pct` 필드 주석에 "신호 시점의 매수 버퍼 (buy buffer)" 명시

#### DataClass 업데이트

```python
@dataclass
class BufferStrategyParams(BaseStrategyParams):
    ma_window: int
    buy_buffer_zone_pct: float    # 매수 버퍼 (upper_band 기준) — 기존 buffer_zone_pct rename
    sell_buffer_zone_pct: float   # 매도 버퍼 (lower_band 기준, 고정) — 신규
    hold_days: int
    recent_months: int
```

- [ ] `BufferStrategyParams.buffer_zone_pct` → `buy_buffer_zone_pct` rename
- [ ] `BufferStrategyParams`에 `sell_buffer_zone_pct: float` 추가

#### 함수 변경

**`_calculate_recent_sell_count` (rename from `_calculate_recent_buy_count`):**

```python
def _calculate_recent_sell_count(
    exit_dates: list[date],   # entry_dates → exit_dates
    current_date: date,
    recent_months: int,
) -> int:
    cutoff_date = current_date - timedelta(days=recent_months * DEFAULT_DAYS_PER_MONTH)
    count = sum(1 for d in exit_dates if d >= cutoff_date and d < current_date)
    return count
```

- [ ] `_calculate_recent_buy_count` → `_calculate_recent_sell_count`로 rename (파라미터명 `exit_dates`)

**`_compute_bands` 시그니처 변경:**

```python
def _compute_bands(
    ma_value: float,
    buy_buffer_pct: float,    # upper_band용 (동적 조정됨)
    sell_buffer_pct: float,   # lower_band용 (항상 고정)
) -> tuple[float, float]:
    upper_band = ma_value * (1 + buy_buffer_pct)
    lower_band = ma_value * (1 - sell_buffer_pct)
    return upper_band, lower_band
```

- [ ] `_compute_bands` 시그니처 및 구현 변경

**`_validate_buffer_strategy_inputs` 업데이트:**

- [ ] `buy_buffer_zone_pct >= MIN_BUY_BUFFER_ZONE_PCT` 검증 (기존 `buffer_zone_pct` rename)
- [ ] `sell_buffer_zone_pct >= MIN_SELL_BUFFER_ZONE_PCT` 검증 신규 추가

**`_record_equity` 시그니처 변경:**

```python
def _record_equity(
    current_date, capital, position, close_price,
    buy_buffer_pct: float,   # 신규 분리
    sell_buffer_pct: float,  # 신규
    upper_band, lower_band,
) -> EquityRecord:
    return {
        ...
        "buy_buffer_pct": buy_buffer_pct,
        "sell_buffer_pct": sell_buffer_pct,
        ...
    }
```

- [ ] `_record_equity` 시그니처 및 반환 딕셔너리 업데이트

#### `run_buffer_strategy` 핵심 로직 변경

- [ ] `all_entry_dates` → `all_exit_dates: list[date]`로 변수명 및 역할 변경
- [ ] 동적 파라미터 계산 블록 변경:
  ```python
  if params.recent_months > 0:
      recent_sell_count = _calculate_recent_sell_count(
          all_exit_dates, current_date, params.recent_months
      )
      # 동적 확장은 upper_band(매수)에만 적용
      current_buy_buffer_pct = params.buy_buffer_zone_pct + (
          recent_sell_count * DEFAULT_BUFFER_INCREMENT_PER_BUY
      )
      if params.hold_days > 0:
          current_hold_days = params.hold_days + (
              recent_sell_count * DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY
          )
      else:
          current_hold_days = params.hold_days
  else:
      recent_sell_count = 0
      current_buy_buffer_pct = params.buy_buffer_zone_pct
      current_hold_days = params.hold_days
  # lower_band는 항상 고정 (sell_buffer_zone_pct)
  current_sell_buffer_pct = params.sell_buffer_zone_pct
  ```
- [ ] 매도 체결 완료 후 `all_exit_dates.append(current_date)` 추가
- [ ] `_compute_bands(ma_value, current_buy_buffer_pct, current_sell_buffer_pct)` 호출로 변경
- [ ] `_record_equity` 호출 업데이트 (buy_buffer_pct, sell_buffer_pct 분리 전달)
- [ ] first_equity_record 초기 밴드 계산 업데이트:
  ```python
  first_upper_band, first_lower_band = _compute_bands(
      first_ma_value,
      params.buy_buffer_zone_pct,   # 초기 buy buffer
      params.sell_buffer_zone_pct,  # sell buffer (고정)
  )
  ```
- [ ] `entry_recent_buy_count` → `entry_recent_sell_count` 변수명 변경
- [ ] `summary`의 `buffer_zone_pct` → `buy_buffer_zone_pct` rename

#### `resolve_buffer_params` 업데이트

```python
def resolve_buffer_params(
    grid_results_path: Path,
    override_ma_window: int | None,
    override_buy_buffer_zone_pct: float | None,    # rename
    override_sell_buffer_zone_pct: float | None,   # 신규
    override_hold_days: int | None,
    override_recent_months: int | None,
) -> tuple[BufferStrategyParams, dict[str, str]]:
```

- [ ] `override_buffer_zone_pct` → `override_buy_buffer_zone_pct` rename
- [ ] `override_sell_buffer_zone_pct: float | None` 파라미터 추가
- [ ] `sell_buffer_zone_pct` 폴백 체인 추가:
  `OVERRIDE → grid_best["sell_buffer_zone_pct"] → DEFAULT_SELL_BUFFER_ZONE_PCT`
- [ ] `BufferStrategyParams` 생성 시 `buy_buffer_zone_pct=buy_buffer_zone_pct`, `sell_buffer_zone_pct=sell_buffer_zone_pct` 적용

#### `run_grid_search` 업데이트

```python
def run_grid_search(
    signal_df, trade_df,
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],    # rename
    sell_buffer_zone_pct_list: list[float],   # 신규
    hold_days_list: list[int],
    recent_months_list: list[int],
    initial_capital: float = 10_000_000.0,
) -> pd.DataFrame:
```

- [ ] `buffer_zone_pct_list` → `buy_buffer_zone_pct_list` rename
- [ ] `sell_buffer_zone_pct_list: list[float]` 추가
- [ ] 5중 루프로 확장:
  ```python
  for buy_buffer_zone_pct in buy_buffer_zone_pct_list:
      for sell_buffer_zone_pct in sell_buffer_zone_pct_list:
          BufferStrategyParams(
              buy_buffer_zone_pct=buy_buffer_zone_pct,
              sell_buffer_zone_pct=sell_buffer_zone_pct,
              ...
          )
  ```

#### `_run_buffer_strategy_for_grid` 업데이트

- [ ] `GridSearchResult` 반환 딕셔너리:
  - `COL_BUFFER_ZONE_PCT` → `COL_BUY_BUFFER_ZONE_PCT: params.buy_buffer_zone_pct`
  - `COL_SELL_BUFFER_ZONE_PCT: params.sell_buffer_zone_pct` 신규 추가

**Validation (Phase 2):** Phase 0 테스트가 그린 전환 확인 (직접 pytest로만 확인)
```bash
poetry run pytest tests/test_buffer_zone_helpers.py -v
```

---

### Phase 3 — analysis.py 및 전략 모듈 연쇄 업데이트

**작업 내용**:

#### `src/qbt/backtest/analysis.py`

- [ ] import 업데이트:
  - `DISPLAY_BUFFER_ZONE` → `DISPLAY_BUY_BUFFER_ZONE`
  - `DISPLAY_SELL_BUFFER_ZONE` 추가
- [ ] `_GRID_CSV_REQUIRED_COLUMNS` 업데이트:
  ```python
  _GRID_CSV_REQUIRED_COLUMNS = {
      DISPLAY_MA_WINDOW: "ma_window",
      DISPLAY_BUY_BUFFER_ZONE: "buy_buffer_zone_pct",    # rename
      DISPLAY_SELL_BUFFER_ZONE: "sell_buffer_zone_pct",  # 신규
      DISPLAY_HOLD_DAYS: "hold_days",
      DISPLAY_RECENT_MONTHS: "recent_months",
  }
  ```
- [ ] `load_best_grid_params` 반환값 업데이트:
  ```python
  result: BestGridParams = {
      "ma_window": int(row[DISPLAY_MA_WINDOW]),
      "buy_buffer_zone_pct": float(row[DISPLAY_BUY_BUFFER_ZONE]),    # rename
      "sell_buffer_zone_pct": float(row[DISPLAY_SELL_BUFFER_ZONE]),  # 신규
      "hold_days": int(row[DISPLAY_HOLD_DAYS]),
      "recent_months": int(row[DISPLAY_RECENT_MONTHS]),
  }
  ```

#### `src/qbt/backtest/strategies/buffer_zone_tqqq.py`

- [ ] `OVERRIDE_BUFFER_ZONE_PCT` → `OVERRIDE_BUY_BUFFER_ZONE_PCT: float | None = None` rename
- [ ] `OVERRIDE_SELL_BUFFER_ZONE_PCT: float | None = None` 신규 추가
- [ ] `resolve_params()`: `resolve_buffer_params(...)` 호출 시그니처 업데이트
  - `OVERRIDE_BUFFER_ZONE_PCT` → `OVERRIDE_BUY_BUFFER_ZONE_PCT`
  - `OVERRIDE_SELL_BUFFER_ZONE_PCT` 추가
- [ ] `params_json`:
  - `"buffer_zone_pct"` → `"buy_buffer_zone_pct": round(params.buy_buffer_zone_pct, 4)`
  - `"sell_buffer_zone_pct": round(params.sell_buffer_zone_pct, 4)` 추가

#### `src/qbt/backtest/strategies/buffer_zone_qqq.py`

- [ ] `buffer_zone_tqqq.py`와 동일한 변경 적용

#### `scripts/backtest/run_grid_search.py`

- [ ] import 업데이트:
  - `DEFAULT_BUFFER_ZONE_PCT_LIST` → `DEFAULT_BUY_BUFFER_ZONE_PCT_LIST`
  - `DISPLAY_BUFFER_ZONE` → `DISPLAY_BUY_BUFFER_ZONE`
  - `COL_BUFFER_ZONE_PCT` → `COL_BUY_BUFFER_ZONE_PCT`
  - `DEFAULT_SELL_BUFFER_ZONE_PCT_LIST`, `DISPLAY_SELL_BUFFER_ZONE`, `COL_SELL_BUFFER_ZONE_PCT` 신규
- [ ] `run_grid_search()` 호출 업데이트:
  - `buffer_zone_pct_list` → `buy_buffer_zone_pct_list=DEFAULT_BUY_BUFFER_ZONE_PCT_LIST`
  - `sell_buffer_zone_pct_list=DEFAULT_SELL_BUFFER_ZONE_PCT_LIST` 추가
- [ ] `TableLogger` 컬럼 정의 업데이트:
  - `DISPLAY_BUFFER_ZONE` → `DISPLAY_BUY_BUFFER_ZONE`
  - `DISPLAY_SELL_BUFFER_ZONE` 추가
- [ ] `results_df.rename()` 딕셔너리 업데이트:
  - `COL_BUY_BUFFER_ZONE_PCT: DISPLAY_BUY_BUFFER_ZONE`
  - `COL_SELL_BUFFER_ZONE_PCT: DISPLAY_SELL_BUFFER_ZONE` 추가
- [ ] `round_dict` 업데이트:
  - `DISPLAY_BUY_BUFFER_ZONE: 4`
  - `DISPLAY_SELL_BUFFER_ZONE: 4` 추가
- [ ] `save_metadata` payload 업데이트:
  - `"buffer_zone_pct_list"` → `"buy_buffer_zone_pct_list"`
  - `"sell_buffer_zone_pct_list"` 추가
- [ ] log 메시지 업데이트

#### `scripts/backtest/run_single_backtest.py`

- [ ] `_save_equity_csv`: `buffer_zone_pct` 관련 로직 → `buy_buffer_pct`, `sell_buffer_pct` 두 컬럼으로 변경
  ```python
  if "buy_buffer_pct" in equity_export.columns:
      equity_round["buy_buffer_pct"] = 4
  if "sell_buffer_pct" in equity_export.columns:
      equity_round["sell_buffer_pct"] = 4
  ```
- [ ] `_save_trades_csv`: `buffer_zone_pct` → `buy_buffer_pct`로 변경
  ```python
  if "buy_buffer_pct" in trades_export.columns:
      trades_round["buy_buffer_pct"] = 4
  ```

#### `scripts/backtest/app_single_backtest.py`

- [ ] trades 레이블 딕셔너리 업데이트:
  ```python
  "buy_buffer_pct": "매수버퍼존",        # buffer_zone_pct 대체
  "recent_sell_count": "최근청산횟수",   # recent_buy_count 대체
  ```

**Validation (Phase 3):** 직접 pytest로 확인
```bash
poetry run pytest tests/test_buffer_zone_helpers.py tests/test_buffer_zone_tqqq.py tests/test_buffer_zone_qqq.py -v
```

---

### Phase 4 — 테스트 보강

**작업 내용**:

- [ ] `tests/test_buffer_zone_helpers.py` 전체 `BufferStrategyParams` 인스턴스 업데이트:
  - `buffer_zone_pct=0.03` → `buy_buffer_zone_pct=0.03, sell_buffer_zone_pct=0.03`
- [ ] import 업데이트:
  - `_calculate_recent_buy_count` → `_calculate_recent_sell_count`
  - `COL_BUFFER_ZONE_PCT` → `COL_BUY_BUFFER_ZONE_PCT`
- [ ] `TestCalculateRecentSellCount` 클래스: Phase 0 레드 테스트를 그린 전환 확인
- [ ] 신규 테스트 — upper_band/lower_band 분리 계약:
  - 청산 전: `lower_band = MA × (1 - sell_buffer_pct)` 고정 검증
  - 청산 후 60일 내: `upper_band = MA × (1 + (buy_buffer + 0.01))` 검증
  - `lower_band`는 청산 전후 동일
- [ ] 신규 테스트 — 가산 계약: 2회 청산 → count=2 → buy_buffer+0.02
- [ ] `test_validate_params` 업데이트:
  - `buffer_zone_pct` → `buy_buffer_zone_pct` rename
  - `sell_buffer_zone_pct` 경계 조건 추가
- [ ] `TestResolveBufferParams` 업데이트:
  - `sell_buffer_zone_pct` 폴백 체인 테스트 추가
- [ ] 기존 동적 조정 테스트(`TestDynamicParamAdjustment`) 업데이트:
  - `recent_buy_count` → `recent_sell_count` 기반으로 수정
  - lower_band 불변 조건 추가

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - 헬퍼 함수 목록: `_calculate_recent_buy_count` → `_calculate_recent_sell_count`
  - `BufferStrategyParams` 필드: `buffer_zone_pct` → `buy_buffer_zone_pct`, `sell_buffer_zone_pct` 추가
  - 동적 파라미터 조정 수식: `recent_buy_count` → `recent_sell_count` 기반으로 업데이트
  - 상수 목록: rename된 상수명 반영
- [ ] `buffer_zone_tqqq_improvement_log.md`: 구현 완료 상태 업데이트 (section 9/10 개선 계획)
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 매수/매도 버퍼 분리 + buy_buffer_zone_pct rename + 청산 기반 동적 조정
2. 백테스트 / buffer_zone_pct → buy_buffer_zone_pct rename + sell_buffer 신규 도입
3. 백테스트 / upper/lower 밴드 독립 제어 + exit 기반 재진입 억제 메커니즘
4. 백테스트 / 그리드 서치 파라미터 확장 (매수/매도 버퍼존 독립 탐색)
5. 백테스트 / 동적 버퍼 타이밍 오류 수정 (entry→exit 기반) + 네이밍 통일

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|---|---|---|
| `buffer_zone_pct` rename이 누락되면 PyRight 타입 오류 | 높음 | 마지막 Phase에서 `validate_project.py --only-pyright`로 검출 |
| `BufferStrategyParams` 필드 추가/rename으로 기존 tests 전체 실패 | 높음 | Phase 4에서 일괄 업데이트, pytest로 단계 확인 |
| `EquityRecord` 스키마 변경으로 equity.csv 비호환 | 중간 | 재실행으로 재생성. 기존 파일은 수동 삭제 필요 |
| `grid_results.csv` 컬럼명 변경(`버퍼존`→`매수버퍼존`)으로 기존 파일 비호환 | 중간 | 기존 CSV 삭제 후 그리드 서치 재실행 필요. 에러 메시지 명확히 유지 |
| 그리드 서치 탐색 공간 5배 증가 (840 → 4,200) | 중간 | 병렬 처리로 대응. 실행 시간 증가는 허용 |
| `_calculate_recent_sell_count` rename으로 import 오류 | 낮음 | Phase 0 테스트에서 명시적으로 포착 |

## 8) 메모(Notes)

### 핵심 설계 결정 사항

1. **네이밍 통일**: `buffer_zone_pct` → `buy_buffer_zone_pct` (완전 rename, 예외 없음)
   - `EquityRecord`의 내부 필드명은 `buy_buffer_pct` / `sell_buffer_pct` (zone 없음, 간결성)
   - 파라미터/상수/CSV 컬럼은 `buy_buffer_zone_pct` / `sell_buffer_zone_pct` (full name)

2. **`sell_buffer_zone_pct` 기본값**: `DEFAULT_SELL_BUFFER_ZONE_PCT = 0.04`
   - 처음에는 buy buffer 기본값과 동일. 그리드 서치로 최적값 탐색.

3. **`hold_days` 동적 조정 유지**: `current_hold_days = hold_days + (recent_sell_count × 1)`
   - "청산 후 더 보수적으로 재진입"하는 철학과 일관성 유지.
   - hold_days는 upper_band 신호 확정에만 사용, lower_band에는 무관.

4. **그리드 서치 탐색 공간**: 840 → **4,200 조합** (5배 증가)
   - `buy_buffer_zone_pct`: [0.01, 0.02, 0.03, 0.04, 0.05] (5개)
   - `sell_buffer_zone_pct`: [0.01, 0.02, 0.03, 0.04, 0.05] (5개)

### 참고 문서

- `buffer_zone_tqqq_improvement_log.md` — Section 10.5(1)(2)(3): 설계 이슈 분석
- 관련 그리드 데이터: `storage/results/backtest/buffer_zone_tqqq/grid_results.csv`

### 진행 로그 (KST)

- 2026-02-21 00:00: Plan 초안 작성
- 2026-02-21 00:00: `buffer_zone_pct` → `buy_buffer_zone_pct` 전체 rename 반영, sell buffer list [0.01~0.05]로 확장

---
