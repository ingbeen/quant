# Implementation Plan: 백테스트 도메인 워크포워드 검증(WFO) 구현

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

**작성일**: 2026-02-22 20:00
**마지막 업데이트**: 2026-02-22 20:00
**관련 범위**: backtest, scripts, tests
**관련 문서**: src/qbt/backtest/CLAUDE.md, tests/CLAUDE.md, scripts/CLAUDE.md, src/qbt/utils/CLAUDE.md

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

- [x] `run_buffer_strategy()`에 `params_schedule` 파라미터를 추가하여 구간별 파라미터 전환 지원
- [x] Expanding Anchored WFO 엔진 구현 (Calmar 목적함수, 432개 파라미터 조합)
- [x] Stitched Equity 생성 (params_schedule 기반 연속 자본곡선)
- [x] 3-Mode 비교 지원 (동적 / sell_buffer 고정 / 전체 고정)
- [x] CLI 스크립트(`run_walkforward.py`) 및 결과 저장 (CSV, JSON)

## 2) 비목표(Non-Goals)

- PBO(Probability of Backtest Overfitting) 분석 → 별도 계획서
- ATR 트레일링 스탑 구현
- 기존 그리드 서치 파라미터 리스트 변경 (WFO는 자체 리스트 사용)
- `run_buffer_strategy()` Engine 객체화
- WFO 결과 대시보드 시각화 (후속 작업)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

매수/매도 버퍼 분리 후 탐색 공간이 840 → 4,200으로 확대되었고, 최적 파라미터(buy=0.01, sell=0.05, hold=5, recent=2)가 두 전략(TQQQ/QQQ) 모두 동일하게 수렴하였다. 이는 과최적화(overfitting)의 전형적 징후이다.

현재 최적 파라미터가 "진짜 패턴"인지 "우연히 좋은 조합"인지 검증하려면, **Out-of-Sample(OOS) 평가**가 필수이다. Walk-Forward Optimization(WFO)은 시계열 데이터에서 표준적인 OOS 검증 프레임워크이다.

### 설계 결정 사항 (토론 합의)

| 항목 | 결정 | 근거 |
|---|---|---|
| WFO 방식 | **Stitched (상태 연속)** | 포지션/자본 연속성 보장 (GPT-5.2 + Claude 합의) |
| 구현 패턴 | **params_schedule** | Engine 객체화/Resume 대비 변경범위 최소 |
| 윈도우 타입 | **Expanding (Anchored)** | 핵심 레짐(닷컴/금융위기) 학습 유지 |
| 목적함수 | **Calmar (CAGR/\|MDD\|)** | 프로젝트 목표(CAGR+MDD)와 직접 정렬 |
| OOS 기간 | **24개월 (2년)** | 연 0.6회 거래 → 1년이면 0~1회뿐, 2년이면 1~2회 |
| 초기 IS | **72개월 (6년)** | 최소 3~4회 거래 확보 |
| 파라미터 조합 | **432개** (3×3×3×4×4) | 4,200 대비 -90% 축소 |

### WFO 파라미터 리스트 (확정)

```python
DEFAULT_WFO_MA_WINDOW_LIST = [100, 150, 200]               # 3개
DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST = [0.01, 0.03, 0.05]  # 3개
DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST = [0.01, 0.03, 0.05] # 3개
DEFAULT_WFO_HOLD_DAYS_LIST = [0, 2, 3, 5]                  # 4개
DEFAULT_WFO_RECENT_MONTHS_LIST = [0, 4, 8, 12]             # 4개
# 3 × 3 × 3 × 4 × 4 = 432개
```

### 윈도우 구성 예시 (~26년 데이터, 1999-03 ~ 2025-03)

```
Window 1:  IS=1999-03~2005-02 (72m),  OOS=2005-03~2007-02 (24m)
Window 2:  IS=1999-03~2007-02 (96m),  OOS=2007-03~2009-02 (24m)
Window 3:  IS=1999-03~2009-02 (120m), OOS=2009-03~2011-02 (24m)
...
Window 10: IS=1999-03~2023-02 (288m), OOS=2023-03~2025-02 (24m)
→ 약 10개 윈도우, OOS 합계 약 20년
```

### 3-Mode 비교 패턴

| 모드 | 설명 | 진단 목적 |
|---|---|---|
| **동적 (dynamic)** | 모든 파라미터 IS 최적화 | 기본 WFO |
| **sell_buffer 고정 (sell_fixed)** | sell_buffer=0.05 고정, 나머지 최적화 | sell_buffer 과최적화 여부 |
| **전체 고정 (fully_fixed)** | 첫 IS 윈도우의 Calmar 최적 파라미터 고정 | 전체 과최적화 여부 |

- 3모드 간 OOS 성과 차이가 작으면 → 파라미터 안정 (과최적화 낮음)
- 3모드 간 OOS 성과 차이가 크면 → 동적 최적화가 노이즈 추종 (과최적화 높음)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙 (체결 타이밍, Equity 정의, Pending Order 정책 등)
- `tests/CLAUDE.md`: 테스트 작성 원칙 (Given-When-Then, 부동소수점 비교 등)
- `scripts/CLAUDE.md`: CLI 계층 규칙 (예외 처리 데코레이터, 메타데이터 저장 등)
- `src/qbt/utils/CLAUDE.md`: 유틸리티 사용 규칙 (병렬 처리, 데이터 로더 등)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `params_schedule` 파라미터 추가 및 기존 테스트 통과
- [x] WFO 엔진: 윈도우 생성, IS 최적화(Calmar), OOS 평가, stitched equity 생성
- [x] 3-Mode 비교: 동적/sell_fixed/fully_fixed 실행 및 결과 저장
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=340, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 신규 파일

| 파일 | 설명 |
|---|---|
| `src/qbt/backtest/walkforward.py` | WFO 비즈니스 로직 (윈도우 생성, IS 최적화, OOS 평가, 요약) |
| `scripts/backtest/run_walkforward.py` | CLI 스크립트 (3-Mode 실행, CSV/JSON 저장) |
| `tests/test_backtest_walkforward.py` | WFO + params_schedule 테스트 |

### 변경 대상 파일

| 파일 | 변경 내용 |
|---|---|
| `src/qbt/backtest/strategies/buffer_zone_helpers.py` | `run_buffer_strategy()`에 `params_schedule` 파라미터 추가 |
| `src/qbt/backtest/constants.py` | 기존 그리드 서치 파라미터 5개 주석 처리 + WFO 상수 추가 |
| `scripts/backtest/run_grid_search.py` | import를 `DEFAULT_WFO_*` 리스트로 변경 |
| `src/qbt/backtest/types.py` | WFO TypedDict 추가 (WfoWindowResultDict, WfoModeSummaryDict) |
| `src/qbt/backtest/CLAUDE.md` | WFO 관련 문서 추가 |
| `tests/CLAUDE.md` | 테스트 파일 목록 추가 |
| `scripts/CLAUDE.md` | 스크립트 설명 추가 |

### 데이터/결과 영향

- 기존 결과 파일 변경 없음
- 신규 결과 파일 (전략별 디렉토리에 저장):
  - `walkforward_dynamic.csv`, `walkforward_sell_fixed.csv`, `walkforward_fully_fixed.csv`
  - `walkforward_equity_dynamic.csv`, `walkforward_equity_sell_fixed.csv`, `walkforward_equity_fully_fixed.csv`
  - `walkforward_summary.json`

## 6) 단계별 계획(Phases)

### Phase 0 — 타입/상수 정의 + 테스트 선행 (레드)

**작업 내용**:

- [x] `src/qbt/backtest/types.py`에 WFO TypedDict 추가
  - `WfoWindowResultDict`: 윈도우별 IS/OOS 결과 (window_idx, is/oos 날짜, best params 5개, is/oos CAGR/MDD/Calmar/trades/win_rate, wfe_calmar)
  - `WfoModeSummaryDict`: 모드별 요약 (n_windows, oos 통계, wfe 통계, param_values, stitched 지표)
- [x] `src/qbt/backtest/constants.py` 수정
  - 기존 그리드 서치 파라미터 5개를 WFO 리스트(`DEFAULT_WFO_*`)로 대체
    - `scripts/backtest/run_grid_search.py`의 import도 `DEFAULT_WFO_*`로 변경 완료
  - WFO 상수 추가:
    - 윈도우 설정: `DEFAULT_WFO_INITIAL_IS_MONTHS = 72`, `DEFAULT_WFO_OOS_MONTHS = 24`
    - 파라미터 리스트: `DEFAULT_WFO_MA_WINDOW_LIST`, `DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST` 등 5개
    - 고정값: `DEFAULT_WFO_FIXED_SELL_BUFFER_PCT = 0.05`
    - 파일명: `WALKFORWARD_DYNAMIC_FILENAME` 등 7개
- [x] `tests/test_backtest_walkforward.py` 생성 — Phase 0 테스트 (레드)
  - `TestParamsSchedule`: params_schedule=None이면 기존 동작과 동일함을 검증, params_schedule로 파라미터 전환 검증, MA 윈도우 변경 시 밴드 계산 검증
  - `TestGenerateWfoWindows`: 윈도우 수/날짜 경계 검증, 데이터 부족 시 예외 검증
  - `TestCalmarSelection`: MDD=0 엣지 케이스, Calmar 기준 최적 파라미터 선택 검증

---

### Phase 1 — params_schedule 구현 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` — `run_buffer_strategy()` 수정
  - 시그니처에 `params_schedule: dict[date, BufferStrategyParams] | None = None` 추가
  - 루프 진입 전: `params_schedule`의 모든 고유 MA 윈도우를 signal_df에 사전 계산
  - 루프 진입 전: schedule 날짜를 정렬, `next_switch_idx = 0` 초기화
  - 일일 루프 시작부: `current_date >= sorted_switch_dates[next_switch_idx]`이면 params 교체 + ma_col 갱신
  - `params_schedule=None`이면 기존 동작과 완전히 동일 (기존 테스트 영향 없음)
- [x] Phase 0의 `TestParamsSchedule` 테스트 통과 확인 (3 passed)

---

### Phase 2 — WFO 엔진 구현 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/walkforward.py` 신규 생성

  **공개 함수**:

  - `generate_wfo_windows(data_start, data_end, initial_is_months, oos_months) -> list[tuple[date, date, date, date]]`
  - `run_walkforward(signal_df, trade_df, param_lists, initial_is_months, oos_months, initial_capital) -> list[WfoWindowResultDict]`
  - `select_best_calmar_params(grid_df) -> dict`
  - `build_params_schedule(window_results) -> tuple[BufferStrategyParams, dict[date, BufferStrategyParams]]`
  - `calculate_wfo_mode_summary(window_results, stitched_summary=None) -> WfoModeSummaryDict`

- [x] Phase 0의 `TestGenerateWfoWindows`, `TestCalmarSelection` 테스트 통과 확인 (8 passed)
- [x] 추가 테스트 작성
  - `TestRunWalkforward`: 소규모 데이터로 WFO 루프 동작 검증 (윈도우 수, 결과 구조)
  - `TestBuildParamsSchedule`: schedule 키 날짜 = OOS 시작일 검증
  - `TestCalculateWfoModeSummary`: 통계 계산 검증

---

### Phase 3 — CLI 스크립트 + 결과 저장 (그린)

**작업 내용**:

- [x] `scripts/backtest/run_walkforward.py` 신규 생성
  - `argparse`: `--strategy` (all / buffer_zone_tqqq / buffer_zone_qqq, 기본값: all)
  - `@cli_exception_handler` 적용
  - 3-Mode 비교 실행, CSV/JSON 저장, 메타데이터 저장, 소요 시간 로깅, 요약 테이블 로깅
- [x] `src/qbt/utils/meta_manager.py`: `"backtest_walkforward"` 타입 추가
- [x] `scripts/CLAUDE.md` 업데이트: `run_walkforward.py` 설명 추가 (Phase 4에서 처리)

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트: walkforward.py 모듈, WFO 관련 상수, TypedDict 추가
- [x] `tests/CLAUDE.md` 업데이트: test_backtest_walkforward.py 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=340, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFO 엔진 구현 (Calmar 목적함수 + params_schedule + 3-Mode 비교)
2. 백테스트 / 워크포워드 검증 추가 (Expanding Anchored Window + Stitched Equity)
3. 백테스트 / WFO + params_schedule 구현으로 과최적화 검증 파이프라인 구축
4. 백테스트 / 워크포워드 최적화 구현 (432 파라미터 조합 × 10 윈도우 × 3모드)
5. 백테스트 / WFO 3-Mode 비교 구현 (동적/sell고정/전체고정 + stitched equity)

## 7) 리스크(Risks)

| 리스크 | 완화책 |
|---|---|
| 초기 IS 윈도우(6년)의 거래 수 부족 (~3~4회) | Calmar이 noise에 민감할 수 있음. WFE로 검증하고, 결과 해석 시 첫 1~2 윈도우 주의 |
| params_schedule에서 MA 윈도우 변경 시 밴드 불연속 | 사전에 모든 MA 컬럼을 계산하여 자연스러운 전환 보장. 테스트로 검증 |
| WFO 계산 비용 (432 × 10 윈도우 × 3모드) | IS 그리드 서치에 기존 병렬 처리 재사용. 432개는 현행 4,200 대비 충분히 작음 |
| Calmar 계산 시 MDD=0 (거래 없는 구간) | `abs(mdd) > EPSILON` 검사. cagr > 0이면 최우선 처리, 아니면 calmar=0 |
| signal_df 데이터 불변성 원칙 위반 (MA 컬럼 추가) | 기존 `run_buffer_strategy()`가 이미 동일 패턴 사용. 현행 유지 |

## 8) 메모(Notes)

### 핵심 설계 결정

- **tqqq/walkforward.py 패턴 재사용**: 월 기반 윈도우 생성, 구간별 최적화 → OOS 평가, 요약 통계 집계
- **run_grid_search() 그대로 재사용**: 윈도우별로 슬라이스된 데이터를 넘겨서 IS 그리드 서치 실행. 함수 변경 불필요
- **Mode 3 파라미터 선택**: 첫 IS 윈도우의 Calmar-best를 사용 (look-ahead 방지)
- **Stitched Equity 범위**: 첫 OOS 시작일부터 마지막 OOS 종료일까지 (IS 기간 제외)

### 참고 자료

- buffer_zone_tqqq_improvement_log.md: Session 12~14 (GPT-5.2 + Claude 토론)
- tqqq/walkforward.py: 기존 워크포워드 구현 패턴
- Bailey & Lopez de Prado, "The Probability of Backtest Overfitting" (PBO 후속 작업 참고)
- Pardo, "The Evaluation and Optimization of Trading Strategies" (WFO 방법론)

### 진행 로그 (KST)

- 2026-02-22 20:00: 계획서 초안 작성

---
