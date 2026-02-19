# Implementation Plan: run_single_backtest 전략 무관 리팩토링

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
**마지막 업데이트**: 2026-02-19 23:59
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

- [x] `run_single_backtest.py`에서 전략 특화 코드를 모두 제거하고 공통 로직만 남김
- [x] 각 전략 모듈(`buffer_zone.py`, `buy_and_hold.py`)에 `resolve_params()`, `run_single()` 추가
- [x] `--strategy` CLI 인자 추가 (all / buffer_zone / buy_and_hold, 기본값: all)
- [x] `README.md` 업데이트

## 2) 비목표(Non-Goals)

- 새 전략 추가
- 대시보드 앱(`app_single_backtest.py`) 변경
- 비즈니스 로직(매수/매도/에쿼티 계산) 변경
- `run_grid_search.py` 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_single_backtest.py`가 버퍼존 전략에 밀착되어 있음:
  - 모듈 레벨 OVERRIDE 상수 4개 (buffer_zone 전용)
  - 폴백 체인(OVERRIDE → grid_best → DEFAULT) 파라미터 결정 로직
  - `_save_results`(buffer_zone 전용)와 `_save_buy_and_hold_results`(Buy & Hold 전용)이 분리
  - 로그 메시지에 "버퍼존 전략" 하드코딩
  - MA_TYPE = "ema" 상수가 buffer_zone 전용
- 새 전략 추가 시 `run_single_backtest.py`를 직접 수정해야 함

### 설계 결정 사항 (사용자 확인 완료)

1. **Save 함수**: `run_single_backtest.py`에 공통 함수로 통합 (컬럼 감지 기반 반올림)
2. **전략 인자**: `--strategy all/buffer_zone/buy_and_hold` (기본값: all, 확장 가능)
3. **파라미터 결정**: 방안 A — 각 전략 모듈에 `resolve_params()` 함수 + OVERRIDE 상수 이동

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

- [x] `run_single_backtest.py`에 전략 특화 코드 없음 (OVERRIDE 상수, 전략명 하드코딩, 전략별 save 함수 등)
- [x] `--strategy` 인자 동작 (all, buffer_zone, buy_and_hold)
- [x] `buffer_zone.py`에 `resolve_params()`, `run_single()` 추가
- [x] `buy_and_hold.py`에 `resolve_params()`, `run_single()` 추가
- [x] `types.py`에 `SingleBacktestResult` 추가
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 업데이트 (--strategy 인자 설명)
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**변경**:

- `src/qbt/backtest/types.py` — `SingleBacktestResult` 추가
- `src/qbt/backtest/strategies/buffer_zone.py` — `resolve_params()`, `run_single()` 추가, OVERRIDE 상수 이동
- `src/qbt/backtest/strategies/buy_and_hold.py` — `resolve_params()`, `run_single()` 추가
- `src/qbt/backtest/strategies/__init__.py` — 새 함수 export
- `src/qbt/backtest/__init__.py` — `SingleBacktestResult` export
- `scripts/backtest/run_single_backtest.py` — 전략 무관 리팩토링 (주요 변경)
- `README.md` — --strategy 인자 설명 추가
- `src/qbt/backtest/CLAUDE.md` — 모듈 구성 업데이트

**테스트**:

- `tests/test_strategy.py` — resolve_params, run_single 테스트 추가

### 데이터/결과 영향

- 결과 파일 경로/형식 변경 없음 (이전 plan에서 이미 전략별 폴더 구조 완료)
- 동일 파라미터 기준 백테스트 결과 동일

## 6) 단계별 계획(Phases)

### Phase 1 — 타입 정의 + 전략 모듈 확장

**작업 내용**:

- [x] `src/qbt/backtest/types.py`에 `SingleBacktestResult` dataclass 추가:
  ```python
  @dataclass
  class SingleBacktestResult:
      strategy_name: str       # "buffer_zone", "buy_and_hold"
      display_name: str        # "버퍼존 전략", "Buy & Hold"
      signal_df: pd.DataFrame  # 저장용 시그널 데이터 (raw)
      equity_df: pd.DataFrame  # 에쿼티 데이터 (raw)
      trades_df: pd.DataFrame  # 거래 내역 (빈 DataFrame 가능)
      summary: Mapping[str, object]
      params_json: dict[str, Any]  # JSON 저장용 전략 파라미터
      result_dir: Path
  ```

- [x] `src/qbt/backtest/strategies/buffer_zone.py` 확장:
  - OVERRIDE 상수 4개 이동 (`run_single_backtest.py` → `buffer_zone.py` 상단)
  - `MA_TYPE = "ema"` 상수 이동
  - `resolve_params() -> tuple[BufferStrategyParams, dict[str, str]]` 추가
    - 폴백 체인: OVERRIDE → grid_best → DEFAULT
    - `load_best_grid_params(GRID_RESULTS_PATH)` 호출
    - 반환: (params, sources)
  - `run_single(signal_df, trade_df) -> SingleBacktestResult` 추가
    - resolve_params 호출
    - add_single_moving_average 호출 (MA 추가)
    - run_buffer_strategy 호출
    - SingleBacktestResult 패키징

- [x] `src/qbt/backtest/strategies/buy_and_hold.py` 확장:
  - `resolve_params() -> tuple[BuyAndHoldParams, dict[str, str]]` 추가
  - `run_single(signal_df, trade_df) -> SingleBacktestResult` 추가
    - resolve_params 호출
    - run_buy_and_hold 호출
    - signal_df로 trade_df OHLC 사용 (MA 없음)
    - SingleBacktestResult 패키징

- [x] `src/qbt/backtest/strategies/__init__.py` 업데이트 — 새 함수 export
- [x] `src/qbt/backtest/__init__.py` 업데이트 — `SingleBacktestResult` export

---

### Phase 2 — run_single_backtest.py 리팩토링

**작업 내용**:

- [x] `scripts/backtest/run_single_backtest.py` 전면 리팩토링:

  **제거 항목** (전략 특화):
  - OVERRIDE_* 상수 4개
  - MA_TYPE 상수
  - 폴백 체인 파라미터 결정 로직 (main 내 1-1 ~ 1-4)
  - `_save_results()` (buffer_zone 전용)
  - `_save_buy_and_hold_results()` (buy_and_hold 전용)
  - "버퍼존 전략" 하드코딩 로그 메시지

  **추가 항목** (공통):
  - argparse `--strategy` 인자 (choices: all, buffer_zone, buy_and_hold; default: all)
  - 전략 레지스트리:
    ```python
    STRATEGY_RUNNERS: dict[str, Callable] = {
        "buffer_zone": buffer_zone_run_single,
        "buy_and_hold": buy_and_hold_run_single,
    }
    ```
  - 공통 `_save_results(result: SingleBacktestResult)` 함수:
    - 디렉토리 생성
    - signal CSV: change_pct 추가, 컬럼 감지 기반 반올림 (가격 6자리, MA 6자리, % 2자리)
    - equity CSV: drawdown_pct 추가, 컬럼 감지 기반 반올림 (equity 정수, 밴드 6자리, 비율 4자리)
    - trades CSV: holding_days 추가 (entry_date/exit_date 존재 시), 반올림
    - summary JSON: 공통 구조 (summary + params_json + monthly_returns + data_info)
    - 메타데이터 저장
  - 공통 `_load_data()` 함수: QQQ/TQQQ 로딩 + 공통 날짜 정렬
  - 공통 거래 내역 테이블 출력 (trades_df가 비어있지 않을 때만)
  - 전략 비교 요약 테이블 (2개 이상 전략 실행 시)

  **main() 흐름** (전략 무관):
  ```
  1. argparse로 --strategy 파싱
  2. _load_data() → signal_df, trade_df
  3. 전략 목록 결정 (all이면 전체, 아니면 지정된 전략)
  4. for each strategy:
     a. STRATEGY_RUNNERS[name](signal_df, trade_df) → result
     b. print_summary(result.summary, result.display_name, logger)
     c. 거래 내역 테이블 출력 (공통)
     d. _save_results(result)
     e. results 리스트에 추가
  5. 비교 테이블 출력 (2개 이상 시)
  ```

- [x] 기존 테스트 통과 확인: `poetry run pytest tests/test_strategy.py tests/test_integration.py -v`

---

### Phase 3 (마지막) — 테스트 + 문서 + 최종 검증

**작업 내용**:

- [x] `tests/test_strategy.py`에 신규 테스트 추가:
  - `TestResolveParams` 클래스:
    - `test_buffer_zone_resolve_params_default`: OVERRIDE=None, grid=None → DEFAULT 사용
    - `test_buffer_zone_resolve_params_override`: OVERRIDE 값 설정 → OVERRIDE 우선
    - `test_buffer_zone_resolve_params_grid`: grid_results.csv 존재 시 → grid_best 사용
    - `test_buy_and_hold_resolve_params`: 항상 DEFAULT_INITIAL_CAPITAL 사용
  - `TestRunSingle` 클래스:
    - `test_buffer_zone_run_single_returns_result`: SingleBacktestResult 구조 검증
    - `test_buy_and_hold_run_single_returns_result`: SingleBacktestResult 구조 검증
- [x] `README.md` 업데이트:
  - 워크플로우 1 섹션에 `--strategy` 인자 설명 추가
  - 실행 명령어 업데이트
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - strategies/ 모듈 설명에 `resolve_params()`, `run_single()` 추가
  - `SingleBacktestResult` 타입 설명 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=293, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / run_single_backtest 전략 무관 리팩토링 + --strategy 인자 추가
2. 백테스트 / 스크립트에서 전략 특화 코드 분리 + 전략별 run_single/resolve_params 도입
3. 백테스트 / run_single_backtest 공통화 + 전략 레지스트리 패턴 적용
4. 백테스트 / 전략 디스패치 아키텍처 도입 (SingleBacktestResult + resolve_params + run_single)
5. 백테스트 / CLI 스크립트 전략 독립성 확보 + --strategy 인자 지원

## 7) 리스크(Risks)

- **run_single 함수 시그니처**: buffer_zone과 buy_and_hold의 run 함수 반환 구조가 다름 (3-tuple vs 2-tuple). run_single에서 SingleBacktestResult로 통일하여 해결.
- **OVERRIDE 상수 이동**: 기존에 run_single_backtest.py에서 수정하던 사용자가 위치 변경을 인지해야 함. CLAUDE.md에 명시.
- **app_single_backtest.py 호환성**: 결과 파일 경로/형식 변경 없으므로 영향 없음.
- **공통 save 함수 복잡도**: 컬럼 감지 기반 반올림이 매직해 보일 수 있음. 주석으로 규칙 명시.

## 8) 메모(Notes)

### 핵심 파일 경로

- `scripts/backtest/run_single_backtest.py` — 주요 리팩토링 대상
- `src/qbt/backtest/strategies/buffer_zone.py` — resolve_params, run_single 추가
- `src/qbt/backtest/strategies/buy_and_hold.py` — resolve_params, run_single 추가
- `src/qbt/backtest/types.py` — SingleBacktestResult 추가
- `src/qbt/backtest/__init__.py` — export 업데이트
- `src/qbt/backtest/strategies/__init__.py` — export 업데이트

### 재사용할 기존 함수

- `print_summary()` (run_single_backtest.py:75) — 이미 전략 무관, 그대로 유지
- `_calculate_monthly_returns()` (run_single_backtest.py:100) — 이미 전략 무관, 그대로 유지
- `add_single_moving_average()` (analysis.py) — buffer_zone.run_single에서 호출
- `load_best_grid_params()` (analysis.py) — buffer_zone.resolve_params에서 호출

### run_single 반환 구조 차이 해결

| 항목 | buffer_zone | buy_and_hold |
|------|------------|-------------|
| signal_df | signal_df + MA 컬럼 | trade_df OHLC (MA 없음) |
| equity_df | equity + buffer_zone_pct + upper/lower_band | equity + position |
| trades_df | 거래 내역 DataFrame | 빈 DataFrame |
| params_json | ma_window, ma_type, buffer_zone_pct, ... | strategy만 |

→ `SingleBacktestResult`로 통일, 공통 save 함수에서 컬럼 감지 기반 처리

### 진행 로그 (KST)

- 2026-02-19: 계획서 작성
- 2026-02-19: Phase 1~3 완료, 전체 검증 통과 (passed=293, failed=0, skipped=0)

---
