# Implementation Plan: 분할 매수매도 오케스트레이터

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

**작성일**: 2026-03-14
**마지막 업데이트**: 2026-03-14
**관련 범위**: backtest, scripts, tests, docs
**관련 문서**: `docs/tranche_architecture.md`, `docs/tranche_final_recommendation.md`, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 분할 매수매도 오케스트레이터 모듈(`src/qbt/backtest/split_strategy.py`) 구현
- [x] 3개 트랜치(ma250/ma200/ma150) 독립 실행 후 결과 조합
- [x] buffer_zone_tqqq, buffer_zone_qqq 대상 분할 전략 설정 정의
- [x] 시각화용 데이터(active_tranches, avg_entry_price, 트랜치별 equity/position) 포함
- [x] CLI 스크립트(`scripts/backtest/run_split_backtest.py`) 구현
- [x] 테스트 코드 작성(`tests/test_split_strategy.py`)

## 2) 비목표(Non-Goals)

- 리밸런싱 (추후 별도 계획서)
- 시각화 대시보드 (추후 별도 계획서)
- buffer_zone_tqqq, buffer_zone_qqq 외 다른 자산의 분할 전략
- 기존 `run_buffer_strategy()` 수정
- 기존 단일 백테스트 스크립트(`run_single_backtest.py`) 및 대시보드 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 버퍼존 전략은 단일 MA=200으로만 매매하여 진입/청산 시점이 하나뿐임
- 182회 고원 분석(overfitting_analysis_report.md §17~18)에서 ma_window=150~300이 고원으로 확인됨
- 고원 내 3개 MA(150/200/250)로 자본을 분할하면 시간적 분산(수주 단위) 확보 가능
- `tranche_final_recommendation.md` 확정: ma_window만 변경하는 3분할, 가중치 33:34:33 고정
- 방식 C(오케스트레이터 패턴) 선택: 기존 `run_buffer_strategy()` 무변경 원칙. 새 모듈이 N회 호출 후 결과 조합

### 핵심 설계 원칙 (tranche_final_recommendation.md 기반)

1. **검증된 조합만 사용**: MA=150/200/250 모두 §18.5에서 직접 백테스트 완료
2. **ma_window만 변경**: buy/sell/hold는 전 트랜치 동일 (4P 확정값)
3. **균등 가중치 고정**: 33:34:33, 데이터 기반 비대칭 배분 금지
4. **기존 코드 무변경**: `run_buffer_strategy()`를 블랙박스로 호출

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 전반 규칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 규칙
- `docs/tranche_architecture.md`: 데이터 흐름/출력 구조 설계
- `docs/tranche_final_recommendation.md`: 파라미터 선택 근거

## 4) 완료 조건(Definition of Done)

- [x] `split_strategy.py` 모듈 구현 (타입, 설정, 오케스트레이터 함수, 팩토리)
- [x] 3개 트랜치(ma250/ma200/ma150) 독립 실행 후 결과 조합
- [x] combined_equity_df에 시각화용 컬럼 포함 (active_tranches, avg_entry_price, 트랜치별 equity/position)
- [x] combined_trades_df에 tranche_id, tranche_seq, ma_window 컬럼 포함
- [x] summary.json에 분할 레벨 + 트랜치별 요약 포함
- [x] CLI 스크립트 구현 (`run_split_backtest.py`)
- [x] 회귀/신규 테스트 추가 (`test_split_strategy.py`)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=351, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 관련 문서 업데이트 (`tranche_architecture.md`, `backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 신규 파일

| 파일 | 목적 |
|---|---|
| `src/qbt/backtest/split_strategy.py` | 오케스트레이터 모듈 (타입, 설정, 핵심 함수, 팩토리) |
| `tests/test_split_strategy.py` | 분할 매수매도 모듈 테스트 |
| `scripts/backtest/run_split_backtest.py` | 분할 매수매도 실행 CLI 스크립트 |

### 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `src/qbt/common_constants.py` | 분할 전략 결과 디렉토리 경로 추가 |
| `src/qbt/backtest/constants.py` | 분할 매수매도 트랜치 상수 추가 |
| `docs/tranche_architecture.md` | 네이밍 업데이트 (portfolio→split, T1/T2/T3→ma250/ma200/ma150) |
| `src/qbt/backtest/CLAUDE.md` | split_strategy.py 모듈 설명 추가 |
| `scripts/CLAUDE.md` | run_split_backtest.py 설명 추가 |
| `tests/CLAUDE.md` | test_split_strategy.py 추가 |

### 변경하지 않는 파일 (절대 규칙)

| 파일 | 이유 |
|---|---|
| `buffer_zone_helpers.py` | 182회 백테스트 검증 완료. `run_buffer_strategy()` 무변경 |
| `buffer_zone.py` | 기존 config-driven 팩토리 유지 |
| `buy_and_hold.py` | 무관 |
| `analysis.py` | `calculate_summary()` 재사용만 함 |
| `run_single_backtest.py` | 기존 단일 백테스트 스크립트 유지 |

### 데이터/결과 영향

- 신규 결과 디렉토리 생성:
  - `storage/results/backtest/split_buffer_zone_tqqq/`
  - `storage/results/backtest/split_buffer_zone_qqq/`
- 기존 결과에 영향 없음
- 출력 파일: `equity.csv`, `trades.csv`, `summary.json` (기존 패턴 준수, 컬럼 구조는 분할 전용)

## 6) 단계별 계획(Phases)

### Phase 0 — 타입/상수/인터페이스 정의 + 핵심 인바리언트 테스트 (레드)

> 핵심 계약(자본 분배, 결과 조합)을 테스트로 먼저 고정한다.
> 타입과 상수는 정의하되, `run_split_backtest()` 구현은 Phase 1로 넘긴다.

**작업 내용**:

- [x] `src/qbt/common_constants.py`에 결과 디렉토리 경로 추가

```python
SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "split_buffer_zone_tqqq"
SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "split_buffer_zone_qqq"
```

- [x] `src/qbt/backtest/constants.py`에 분할 매수매도 상수 추가

```python
# --- 분할 매수매도 트랜치 설정 (tranche_final_recommendation.md 기반) ---
SPLIT_TRANCHE_MA_WINDOWS: Final = [250, 200, 150]  # 트랜치별 MA 윈도우 (고원 내 우단/중앙/좌단)
SPLIT_TRANCHE_WEIGHTS: Final = [0.33, 0.34, 0.33]  # 트랜치별 가중치 (균등 분배)
SPLIT_TRANCHE_IDS: Final = ["ma250", "ma200", "ma150"]  # 트랜치 ID
```

- [x] `src/qbt/backtest/split_strategy.py` 신규 생성 — 타입/인터페이스만 정의

**타입 정의**:

```python
@dataclass(frozen=True)
class SplitTrancheConfig:
    """분할 매수매도 트랜치별 설정."""
    tranche_id: str    # "ma250", "ma200", "ma150"
    weight: float      # 0.33, 0.34, 0.33
    ma_window: int     # 250, 200, 150

@dataclass(frozen=True)
class SplitStrategyConfig:
    """분할 매수매도 전략 설정."""
    strategy_name: str               # "split_buffer_zone_qqq"
    display_name: str                # "분할 버퍼존 (QQQ)"
    base_config: BufferZoneConfig    # 기존 자산 설정 (데이터 경로, 4P 파라미터)
    total_capital: float             # 총 자본금
    tranches: tuple[SplitTrancheConfig, ...]  # 트랜치별 설정 (frozen 지원)
    result_dir: Path                 # 결과 저장 디렉토리

@dataclass
class SplitTrancheResult:
    """트랜치별 백테스트 결과."""
    tranche_id: str
    config: SplitTrancheConfig
    trades_df: pd.DataFrame
    equity_df: pd.DataFrame
    summary: BufferStrategyResultDict

@dataclass
class SplitStrategyResult:
    """분할 매수매도 전체 결과."""
    strategy_name: str
    display_name: str
    combined_equity_df: pd.DataFrame    # 합산 에쿼티 (시각화 메인)
    combined_trades_df: pd.DataFrame    # 전체 거래 (tranche_id 포함)
    combined_summary: SummaryDict       # 분할 레벨 성과 지표
    per_tranche: list[SplitTrancheResult]  # 트랜치별 결과
    config: SplitStrategyConfig         # 원본 설정 (재현성)
    params_json: dict[str, Any]         # JSON 저장용
```

**인터페이스 정의 (stub)**:

```python
def run_split_backtest(config: SplitStrategyConfig) -> SplitStrategyResult:
    """분할 매수매도 백테스트를 실행한다."""
    raise NotImplementedError

SPLIT_CONFIGS: list[SplitStrategyConfig] = [...]  # 실제 설정 포함

def create_split_runner(config: SplitStrategyConfig) -> Callable[[], SplitStrategyResult]:
    """SplitStrategyConfig에 대한 실행 함수를 생성한다."""
    raise NotImplementedError
```

- [x] `tests/test_split_strategy.py` 테스트 작성

**그린 테스트** (Phase 0에서 통과):

```
- test_split_tranche_config_creation: SplitTrancheConfig 생성
- test_split_strategy_config_creation: SplitStrategyConfig 생성
- test_split_configs_defined: SPLIT_CONFIGS 리스트 비어있지 않음
- test_split_configs_weight_sum: 각 설정의 가중치 합 ≈ 1.0
- test_split_configs_tranche_ids: 각 설정의 트랜치 ID가 고유
```

**레드 테스트** (Phase 1에서 그린 전환):

```
- test_run_split_backtest_returns_result: 실행 후 SplitStrategyResult 반환
- test_capital_allocation_per_tranche: total_capital × weight = 트랜치 자본
- test_each_tranche_uses_own_ma_window: 트랜치별 올바른 MA 윈도우 사용
- test_base_params_preserved: buy/sell/hold는 base_config의 4P 확정값 그대로
- test_combined_equity_columns: combined_equity_df 필수 컬럼 존재
- test_combined_equity_sum: 합산 equity = 트랜치별 equity 합
- test_combined_trades_tranche_tagging: tranche_id, tranche_seq, ma_window 컬럼
- test_active_tranches_count: 포지션 보유 중인 트랜치 수 정확
- test_avg_entry_price_calculation: 보유 트랜치의 가중 평균 진입가
```

> 테스트에서는 실제 MA=150/200/250 대신 작은 MA 윈도우(5/10/15)와 ~30행 데이터를 사용하여
> 오케스트레이터 로직을 검증한다. run_buffer_strategy()의 정확성은 기존 테스트가 보장한다.

---

### Phase 1 — 오케스트레이터 핵심 구현 (그린)

**작업 내용**:

- [x] `run_split_backtest()` 구현

처리 흐름:

```
1. 입력 검증 (가중치 합, 트랜치 설정)
2. 데이터 로딩 (1회만) — base_config의 경로 사용
3. 모든 트랜치 MA 사전 계산 (signal_df에 add_single_moving_average N회)
4. 트랜치별 독립 실행:
   for tranche in config.tranches:
     capital = total_capital × tranche.weight
     params = BufferStrategyParams(capital, tranche.ma_window, base의 buy/sell/hold/recent)
     trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params)
     → SplitTrancheResult로 수집
5. 결과 조합 → SplitStrategyResult 반환
```

- [x] `_combine_equity()` 헬퍼 구현

```
입력: list[SplitTrancheResult]
출력: pd.DataFrame

컬럼 구성:
- Date: 날짜
- equity: 합산 에쿼티 (전 트랜치 equity 합)
- active_tranches: 포지션 보유 중인 트랜치 수 (0~3)
- avg_entry_price: 보유 트랜치의 가중 평균 진입가 (없으면 None)
- {tranche_id}_equity: 트랜치별 개별 에쿼티
- {tranche_id}_position: 트랜치별 포지션 수량

avg_entry_price 계산:
  보유 중인 트랜치의 (entry_price × shares) 합 / shares 합
  → equity_df의 position > 0인 날짜별로 계산
  → 트랜치의 entry_price는 trades_df의 가장 최근 매수 기록에서 추출
```

- [x] `_combine_trades()` 헬퍼 구현

```
입력: list[SplitTrancheResult]
출력: pd.DataFrame

기존 TradeRecord 컬럼 + 추가 컬럼:
- tranche_id: "ma250", "ma200", "ma150"
- tranche_seq: 해당 트랜치 내 거래 순번 (1-based)
- ma_window: 해당 트랜치의 MA 기간

정렬: entry_date 오름차순 → tranche_id 오름차순
```

- [x] `_calculate_combined_summary()` 헬퍼 구현

```
입력: combined_equity_df, combined_trades_df, total_capital
출력: SummaryDict

합산 에쿼티 DataFrame으로 calculate_summary() 호출
미청산 포지션 수(active_open_positions) 계산 → params_json에 포함
```

- [x] `_build_params_json()` 헬퍼 구현

```json
{
  "total_capital": 10000000,
  "buy_buffer_zone_pct": 0.03,
  "sell_buffer_zone_pct": 0.05,
  "hold_days": 3,
  "ma_type": "ema",
  "tranches": [
    {"tranche_id": "ma250", "ma_window": 250, "weight": 0.33, "initial_capital": 3300000},
    {"tranche_id": "ma200", "ma_window": 200, "weight": 0.34, "initial_capital": 3400000},
    {"tranche_id": "ma150", "ma_window": 150, "weight": 0.33, "initial_capital": 3300000}
  ]
}
```

- [x] `create_split_runner()` 팩토리 구현

```python
def create_split_runner(config: SplitStrategyConfig) -> Callable[[], SplitStrategyResult]:
    def run() -> SplitStrategyResult:
        return run_split_backtest(config)
    return run
```

- [x] Phase 0의 레드 테스트 전부 그린 전환
- [x] 추가 테스트 작성:

```
- test_open_position_in_per_tranche: 미청산 포지션이 트랜치별 summary에 포함
- test_empty_trades_tranche: 거래 없는 트랜치 처리 (equity만 있고 trades 빈 DataFrame)
- test_create_split_runner: 팩토리 함수 호출 후 결과 타입 검증
- test_data_loaded_once: 동일 데이터를 트랜치 수만큼 중복 로딩하지 않음 (구조 검증)
```

---

### Phase 2 — CLI 스크립트 (그린)

**작업 내용**:

- [x] `scripts/backtest/run_split_backtest.py` 구현

구조 (기존 `run_single_backtest.py` 패턴 참고):

```python
"""분할 매수매도 백테스트 실행 스크립트"""

# 명령행 인자
#   --strategy: all(기본) / split_buffer_zone_tqqq / split_buffer_zone_qqq

# 실행 흐름:
# 1. 로거 초기화
# 2. 명령행 인자 파싱
# 3. SPLIT_CONFIGS에서 대상 설정 필터링
# 4. 각 설정에 대해 run_split_backtest() 실행
# 5. 결과 저장 (_save_split_results)
# 6. 메타데이터 저장 (meta_manager)
# 7. 성과 요약 로그 출력
```

결과 저장 (`_save_split_results`):

```
result_dir/
├── equity.csv        # combined_equity_df (반올림 적용)
├── trades.csv        # combined_trades_df (반올림 적용)
└── summary.json      # 분할 레벨 요약 + 트랜치별 요약
```

summary.json 구조:

```json
{
  "display_name": "분할 버퍼존 (QQQ)",
  "split_summary": {
    "initial_capital": 10000000,
    "final_capital": "...",
    "total_return_pct": "...",
    "cagr": "...",
    "mdd": "...",
    "calmar": "...",
    "total_trades": "...",
    "active_open_positions": 2
  },
  "tranches": [
    {
      "tranche_id": "ma250",
      "ma_window": 250,
      "weight": 0.33,
      "initial_capital": 3300000,
      "summary": { "cagr": "...", "mdd": "...", "..." : "..." },
      "open_position": { "..." : "..." }
    }
  ],
  "split_config": {
    "total_capital": 10000000,
    "buy_buffer_zone_pct": 0.03,
    "sell_buffer_zone_pct": 0.05,
    "hold_days": 3,
    "ma_type": "ema"
  }
}
```

메타데이터 타입: `"split_backtest"`

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `docs/tranche_architecture.md` 네이밍 업데이트
  - `portfolio` → `split` (모듈명, 타입명, 함수명)
  - `T1`/`T2`/`T3` → `ma250`/`ma200`/`ma150`
  - `PortfolioConfig` → `SplitStrategyConfig`
  - `PortfolioResult` → `SplitStrategyResult`
  - `portfolio.py` → `split_strategy.py`
  - `run_portfolio_backtest` → `run_split_backtest`
  - (이미 작성 시점에 split/ma250 등 네이밍 적용 완료)
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (split_strategy.py 모듈 설명 추가)
- [x] `scripts/CLAUDE.md` 업데이트 (run_split_backtest.py 설명 추가)
- [x] `tests/CLAUDE.md` 업데이트 (test_split_strategy.py 추가)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=351, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 분할 매수매도 오케스트레이터 신규 구현 (ma250/ma200/ma150 3분할)
2. 백테스트 / 분할 매수매도 전략 추가 — 트랜치별 독립 실행 및 결과 조합
3. 백테스트 / split_strategy.py 신규 — 3트랜치 분할 매수매도 모듈 + CLI + 테스트
4. 백테스트 / 분할 매수매도 모듈, CLI 스크립트, 테스트 일괄 추가
5. 백테스트 / 오케스트레이터 패턴 분할 매수매도 구현 (기존 코드 무변경)

## 7) 리스크(Risks)

- **MA 컬럼 누락**: `run_buffer_strategy()` 내부에서 signal_df를 복사하므로, 사전 계산한 MA 컬럼이 올바르게 전달되어야 함 → 모든 MA를 사전 계산 후 signal_df에 추가하여 해결
- **합산 에쿼티 지표 해석**: 합산 MDD/CAGR이 개별 트랜치와 다를 수 있음 → 정상 동작이며 분산 효과, summary에 트랜치별 지표 별도 포함으로 비교 가능
- **avg_entry_price 계산 복잡도**: 포지션 변경 시점에서 entry_price를 추적해야 함 → equity_df의 position 변화와 trades_df의 entry_price를 조합하여 계산
- **트랜치 간 날짜 불일치**: MA 기간이 다르면 유효 시작일이 다를 수 있음 → `run_buffer_strategy()`가 내부적으로 MA 유효 행 필터링 수행. 트랜치별 equity_df 길이가 다를 수 있으므로 `_combine_equity()`에서 Date 기준 outer merge 후 NaN 처리 필요

## 8) 메모(Notes)

### 참고 문서

- 설계 문서: `docs/tranche_architecture.md` (방식 C 선택 근거, 데이터 흐름, 출력 구조)
- 파라미터 근거: `docs/tranche_final_recommendation.md` (ma_window만 변경, 가중치 33:34:33)
- 고원 분석: `docs/overfitting_analysis_report.md` §17~18

### 핵심 결정 사항

- 트랜치 ID: `ma250`/`ma200`/`ma150` (MA 윈도우 기반 네이밍)
- 모듈 위치: `src/qbt/backtest/split_strategy.py` (strategies/ 패키지가 아닌 backtest/ 레벨 — 전략을 오케스트레이션하는 상위 모듈)
- 전략 이름: `split_buffer_zone_tqqq`, `split_buffer_zone_qqq`
- 기존 코드 무변경: `run_buffer_strategy()`, `buffer_zone.py`, `buffer_zone_helpers.py` 수정 금지

### 테스트 데이터 전략

- 오케스트레이터 테스트에서는 실제 MA=150/200/250 대신 작은 MA 윈도우(5/10/15) 사용
- ~30행 테스트 데이터로 오케스트레이터 로직(자본 분배, 결과 조합) 검증
- `run_buffer_strategy()`의 정확성은 기존 `test_buffer_zone_helpers.py` 182+ 테스트가 보장

### 진행 로그 (KST)

- 2026-03-14: 계획서 작성

---
