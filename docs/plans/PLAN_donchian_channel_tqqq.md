# Implementation Plan: Donchian Channel (TQQQ) 전략 추가

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../../../docs/CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../../../docs/CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-03 22:00
**마지막 업데이트**: 2026-03-03 22:00
**관련 범위**: backtest, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../../../docs/CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] E2 전략 (Donchian Channel) 백테스트 엔진 구현 (QQQ 시그널 + TQQQ 합성 데이터 매매)
- [ ] 고정 파라미터 (entry=55일, exit=20일)로 단일 백테스트 실행 지원
- [ ] 대시보드에서 upper_channel / lower_channel 라인 표시 (이평선 불필요, 앱 내 연산 금지)

## 2) 비목표(Non-Goals)

- 그리드 서치 / WFO / CSCV 등 파라미터 탐색 (향후 별도 plan)
- ATR 트레일링 스탑과의 결합
- hold_days 유지 조건 및 동적 파라미터 조정 (recent_months)
- Donchian Channel QQQ 매매 전략 (TQQQ만 구현)
- 기존 버퍼존 전략 코드 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `ATR_WFO_TQQQ_improvement_strategies.md`의 E2 전략 (Donchian Channel, 터틀 트레이딩 방식) 추가 요청
- Donchian Channel은 이평선 기반 밴드가 아닌 N일 최고가/M일 최저가를 사용하는 독립적 프레임워크
- 기존 buffer_zone_helpers의 `run_buffer_strategy()`는 MA 기반 밴드에 밀접 결합 → 별도 실행 엔진 필요

### 핵심 설계 결정

**Donchian Channel 계산**:
- `upper_channel[i]` = signal_df High의 이전 55일간 최고가 (`rolling(55).max().shift(1)`)
- `lower_channel[i]` = signal_df Low의 이전 20일간 최저가 (`rolling(20).min().shift(1)`)
- `shift(1)`: lookahead 방지 (당일 데이터 미포함)

**매매 신호**:
- 매수: `prev_close <= upper_channel AND close > upper_channel` (55일 신고가 돌파)
- 매도: `prev_close >= lower_channel AND close < lower_channel` (20일 신저가 돌파)
- 체결: 신호 발생 익일 시가 (기존 pending order 패턴 동일)

**데이터 소스**:
- 시그널: QQQ (`QQQ_DATA_PATH`)
- 매매: TQQQ 합성 데이터 (`TQQQ_SYNTHETIC_DATA_PATH`)

**별도 실행 엔진 선택 근거**:
- Donchian은 MA 불필요, buffer zone 퍼센트 불필요, hold_days 불필요
- `run_buffer_strategy()`의 MA 컬럼 검증, 밴드 계산, 동적 조정 로직이 모두 불필요
- 간결한 독립 엔진이 유지보수성과 가독성 면에서 우수

**컬럼 명명**:
- equity_df: `upper_channel`, `lower_channel` (기존 `upper_band`/`lower_band`와 구분)
- 대시보드: feature detection으로 자동 탐지

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] Donchian Channel 실행 엔진 구현 (donchian_helpers.py)
- [ ] 전략 모듈 구현 (donchian_channel_tqqq.py)
- [ ] run_single_backtest.py에 전략 등록 + upper_channel/lower_channel CSV 저장 지원
- [ ] app_single_backtest.py에서 upper_channel/lower_channel 라인 렌더링 + tooltip 지원
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 관련 문서 업데이트 (CLAUDE.md 등)
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 신규 파일

| 파일 | 목적 |
|------|------|
| `src/qbt/backtest/strategies/donchian_helpers.py` | Donchian Channel 실행 엔진 (TypedDict, 파라미터, 핵심 함수) |
| `src/qbt/backtest/strategies/donchian_channel_tqqq.py` | 전략 모듈 (설정 + run_single()) |
| `tests/test_donchian_helpers.py` | Donchian 전략 테스트 |

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/common_constants.py` | `DONCHIAN_CHANNEL_TQQQ_RESULTS_DIR` 추가 |
| `src/qbt/backtest/constants.py` | Donchian 기본 상수 추가 (`DEFAULT_ENTRY_CHANNEL_DAYS`, `DEFAULT_EXIT_CHANNEL_DAYS`) |
| `src/qbt/backtest/strategies/__init__.py` | Donchian 전략 export 추가 |
| `scripts/backtest/run_single_backtest.py` | 전략 등록 + `_save_equity_csv`에 upper_channel/lower_channel 반올림 추가 |
| `scripts/backtest/app_single_backtest.py` | upper_channel/lower_channel feature detection + 차트 렌더링 + tooltip |
| `src/qbt/backtest/CLAUDE.md` | Donchian 전략 모듈 문서 추가 |
| `tests/CLAUDE.md` | 테스트 파일 목록에 추가 |

### 데이터/결과 영향

- 신규 결과 폴더: `storage/results/backtest/donchian_channel_tqqq/`
- 기존 전략 결과에 영향 없음

---

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트로 핵심 정책 고정 (레드)

**작업 내용**:

- [ ] `tests/test_donchian_helpers.py` 생성
  - 채널 계산 테스트: `compute_donchian_channels()`가 N일 최고가/M일 최저가를 올바르게 계산하는지 (shift(1) 포함)
  - 매수 신호 테스트: `prev_close <= upper_channel AND close > upper_channel`일 때만 True
  - 매도 신호 테스트: `prev_close >= lower_channel AND close < lower_channel`일 때만 True
  - 전략 실행 테스트: `run_donchian_strategy()` 기본 실행, equity/trades/summary 구조 검증
  - 체결 타이밍 테스트: 신호일 i → 체결일 i+1 시가
  - Pending order 충돌 테스트: 이미 pending 존재 시 새 신호 → PendingOrderConflictError
  - 비용 모델 테스트: SLIPPAGE_RATE 적용 검증
  - 미청산 포지션 테스트: 종료 시 포지션 보유 → summary에 open_position 포함
  - 빈 데이터 / 최소 데이터 엣지 케이스

---

### Phase 1 — 핵심 구현 (그린)

**작업 내용**:

- [ ] `src/qbt/backtest/constants.py`에 Donchian 상수 추가
  ```python
  DEFAULT_ENTRY_CHANNEL_DAYS = 55
  DEFAULT_EXIT_CHANNEL_DAYS = 20
  ```
- [ ] `src/qbt/common_constants.py`에 결과 디렉토리 추가
  ```python
  DONCHIAN_CHANNEL_TQQQ_RESULTS_DIR = BACKTEST_RESULTS_DIR / "donchian_channel_tqqq"
  ```
- [ ] `src/qbt/backtest/strategies/donchian_helpers.py` 생성
  - **TypedDict**: `DonchianEquityRecord` (Date, equity, position, upper_channel, lower_channel)
  - **TypedDict**: `DonchianTradeRecord` (entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct)
  - **TypedDict**: `DonchianStrategyResultDict` (SummaryDict 확장 + strategy, entry_channel_days, exit_channel_days)
  - **dataclass**: `DonchianStrategyParams` (initial_capital, entry_channel_days, exit_channel_days)
  - **함수**: `compute_donchian_channels(signal_df, entry_days, exit_days)` → (upper_series, lower_series)
    - `upper = signal_df["High"].rolling(entry_days).max().shift(1)`
    - `lower = signal_df["Low"].rolling(exit_days).min().shift(1)`
  - **함수**: `run_donchian_strategy(signal_df, trade_df, params, strategy_name)` → (trades_df, equity_df, summary)
    - 입력 검증 (최소 행 수, 채널 일수 유효성)
    - Donchian 채널 계산
    - 일별 루프: pending order 체결 → equity 기록 → 신호 감지
    - 매수 신호: `prev_close <= prev_upper AND close > upper` (position == 0일 때)
    - 매도 신호: `prev_close >= prev_lower AND close < lower` (position > 0일 때)
    - pending order 충돌 시 `PendingOrderConflictError` 발생
    - 비용 모델: `SLIPPAGE_RATE` 적용 (buffer_zone_helpers와 동일)
    - 종료 시 미청산 포지션 → summary에 `open_position` 포함
    - `calculate_summary()` 재사용 (analysis.py)
- [ ] `src/qbt/backtest/strategies/donchian_channel_tqqq.py` 생성
  - `STRATEGY_NAME = "donchian_channel_tqqq"`
  - `DISPLAY_NAME = "Donchian Channel (TQQQ)"`
  - `SIGNAL_DATA_PATH = QQQ_DATA_PATH`
  - `TRADE_DATA_PATH = TQQQ_SYNTHETIC_DATA_PATH`
  - `OVERRIDE_ENTRY_CHANNEL_DAYS: int | None = None` (None → DEFAULT 사용)
  - `OVERRIDE_EXIT_CHANNEL_DAYS: int | None = None`
  - `resolve_params()` → (DonchianStrategyParams, dict[str, str])
  - `run_single()` → SingleBacktestResult
    - load_stock_data + extract_overlap_period
    - resolve_params
    - run_donchian_strategy 호출
    - SingleBacktestResult 반환 (signal_df에 MA 컬럼 없음)
- [ ] Phase 0 테스트 전부 통과 확인

---

### Phase 2 — 통합 (CLI + 대시보드)

**작업 내용**:

- [ ] `src/qbt/backtest/strategies/__init__.py` 업데이트
  - donchian_helpers 및 donchian_channel_tqqq export 추가
- [ ] `scripts/backtest/run_single_backtest.py` 업데이트
  - import에 `donchian_channel_tqqq` 추가
  - `STRATEGY_RUNNERS`에 `donchian_channel_tqqq.STRATEGY_NAME: donchian_channel_tqqq.run_single` 등록
  - `_save_equity_csv()`: `upper_channel`/`lower_channel` 컬럼 감지 + 6자리 반올림 추가
    ```python
    if "upper_channel" in equity_export.columns:
        equity_round["upper_channel"] = 6
    if "lower_channel" in equity_export.columns:
        equity_round["lower_channel"] = 6
    ```
- [ ] `scripts/backtest/app_single_backtest.py` 업데이트
  - `_build_candle_data()`: equity_map 구축 시 `upper_channel`/`lower_channel` 감지 추가
    ```python
    has_upper_ch = "upper_channel" in equity_df.columns
    has_lower_ch = "lower_channel" in equity_df.columns
    # equity_map에 "upper"/"lower" 키로 추가 (기존 band와 동일 키 사용)
    if has_upper_ch and pd.notna(row.upper_channel):
        entry["upper"] = float(row.upper_channel)
    if has_lower_ch and pd.notna(row.lower_channel):
        entry["lower"] = float(row.lower_channel)
    ```
  - `_render_main_chart()`: feature detection 확장
    ```python
    has_upper = "upper_band" in equity_df.columns or "upper_channel" in equity_df.columns
    has_lower = "lower_band" in equity_df.columns or "lower_channel" in equity_df.columns
    upper_col = "upper_band" if "upper_band" in equity_df.columns else "upper_channel"
    lower_col = "lower_band" if "lower_band" in equity_df.columns else "lower_channel"
    ```
    - `_build_series_data(equity_df, upper_col)` / `_build_series_data(equity_df, lower_col)` 사용

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트: donchian_helpers.py, donchian_channel_tqqq.py 모듈 설명 추가
- [ ] `tests/CLAUDE.md` 업데이트: test_donchian_helpers.py 목록 추가
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트
- [ ] 전체 Phase 체크리스트 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Donchian Channel (TQQQ) 전략 추가 (E2, 터틀 트레이딩)
2. 백테스트 / Donchian Channel 실행 엔진 및 대시보드 표시 추가
3. 백테스트 / E2 Donchian Channel 전략 구현 + upper/lower channel 차트 표시
4. 백테스트 / 신규 Donchian Channel 전략 추가 (55/20 고정, QQQ→TQQQ)
5. 백테스트 / Donchian Channel 전략 추가 및 대시보드 채널 라인 렌더링

---

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| 채널 계산 lookahead 오류 | shift(1) 적용 + 테스트로 고정 |
| PendingOrderConflictError 재사용 시 import 문제 | buffer_zone_helpers에서 직접 import |
| 대시보드 feature detection 충돌 (band vs channel) | OR 조건으로 분리 감지, 하나만 존재 보장 |
| 기존 전략 회귀 | 기존 코드 수정 최소화, validate_project.py로 검증 |

## 8) 메모(Notes)

- Donchian Channel은 buffer_zone과 독립적인 프레임워크로, 별도 실행 엔진(`donchian_helpers.py`)을 생성
- `PendingOrderConflictError`는 buffer_zone_helpers에서 import하여 재사용 (중복 정의 방지)
- 향후 그리드 서치/WFO 확장 시 `donchian_helpers.py`에 `run_grid_search()` 추가 예정
- 터틀 트레이딩 55/20은 40년 검증된 표준값이므로 과최적화 위험 낮음

### 진행 로그 (KST)

- 2026-03-03 22:00: Plan 작성 완료

---
