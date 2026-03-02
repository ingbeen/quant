# Implementation Plan: WFO Stitched 대시보드 시각화

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

**작성일**: 2026-03-02 22:00
**마지막 업데이트**: 2026-03-03 00:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] WFO Stitched(Dynamic) 백테스트 결과를 기존 대시보드(`app_single_backtest.py`)에서 시각화
- [x] 기존 대시보드 코드 수정 없이 Feature Detection으로 자동 호환
- [x] OOS 구간(2005~2026) 매매 패턴(Buy/Sell 마커, 밴드, 에쿼티, 드로우다운) 확인 가능

## 2) 비목표(Non-Goals)

- 대시보드 앱(`app_single_backtest.py`) 코드 수정
- 기존 WFO 파이프라인(`run_walkforward.py`) 수정
- 기존 단일 백테스트 결과 변경
- buffer_zone_tqqq, buffer_zone_qqq 등 다른 전략 지원 (후속 확장 가능)
- WFO Sell Fixed / Fully Fixed 모드 지원 (Dynamic 모드 전용)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

WFO Stitched는 실전 매매와 동일한 방식(OOS 구간에서 params_schedule로 파라미터 순차 교체)이지만, 현재 시각화가 불가능하다.

- `run_walkforward.py`의 `_run_stitched_equity()`가 equity_df, trades_df, summary를 생성하지만, 대시보드 호환 형식(signal.csv + equity.csv(drawdown_pct) + trades.csv + summary.json)으로 저장하지 않음
- 기존 단일 백테스트(`run_single_backtest.py`)의 equity.csv는 `drawdown_pct` 컬럼을 포함하나, WFO stitched equity CSV에는 없음
- `run_buffer_strategy(params_schedule=...)`의 출력 형식은 단일 백테스트와 완전히 동일 → 저장 형식만 맞추면 대시보드가 자동 인식

### 데이터 흐름

```
walkforward_dynamic.csv (이미 존재)
        ↓ 파싱
params_schedule 구축 (build_params_schedule 재사용)
        ↓
run_buffer_strategy(params_schedule=...) 실행 (OOS 구간만)
        ↓
signal.csv + equity.csv + trades.csv + summary.json 저장
        ↓
app_single_backtest.py 자동 탐색 → 새 탭 생성
```

### 기존 인프라 재사용

| 기능 | 기존 위치 | 재사용 |
|------|----------|--------|
| `build_params_schedule()` | `walkforward.py:453-498` | ✅ 그대로 호출 |
| `run_buffer_strategy(params_schedule=...)` | `buffer_zone_helpers.py:893+` | ✅ 그대로 호출 |
| `calculate_summary()` | `analysis.py` | ✅ 그대로 호출 |
| `calculate_monthly_returns()` | `analysis.py` | ✅ 그대로 호출 |
| `load_stock_data()` | `utils/data_loader.py` | ✅ 그대로 호출 |
| `extract_overlap_period()` | `utils/data_loader.py` | ✅ 그대로 호출 |
| 대시보드 Feature Detection | `app_single_backtest.py` | ✅ 코드 변경 없이 자동 호환 |

### 핵심 설계 결정

**결과 디렉토리**: `storage/results/backtest/buffer_zone_atr_tqqq_wfo/`
- 대시보드가 `BACKTEST_RESULTS_DIR` 하위 디렉토리를 스캔하여 자동 탐색
- 기존 `buffer_zone_atr_tqqq/` (단일 백테스트)와 별도 디렉토리로 공존

**display_name**: `"버퍼존 전략 ATR WFO (TQQQ)"` (사용자 결정)

**대상 전략**: buffer_zone_atr_tqqq Dynamic 모드 전용 (사용자 결정)

**MA 라인 처리**: Window 0(2005~2007)은 MA=150이지만, 나머지 10개 윈도우는 MA=200. signal.csv에는 `ma_200` 컬럼만 포함. upper_band/lower_band는 equity_df에서 params_schedule을 반영한 정확한 값. MA 라인은 Window 0에서만 부정확하나 밴드와 매매 마커는 정확.

**summary.json의 params**: 단일 파라미터가 아닌 WFO 메타 정보(모드, 윈도우 수, OOS 기간, 최신 윈도우 파라미터)를 포함.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `run_wfo_stitched_backtest.py` 스크립트 구현 완료
- [x] `load_wfo_results_from_csv()` 비즈니스 로직 함수 구현 완료
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=424, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, 루트 `CLAUDE.md`)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

신규 파일:
- `scripts/backtest/run_wfo_stitched_backtest.py` — WFO Stitched 대시보드 결과 생성 스크립트
- `tests/test_wfo_stitched.py` — `load_wfo_results_from_csv()` 테스트

변경 파일:
- `src/qbt/backtest/walkforward.py` — `load_wfo_results_from_csv()` 함수 추가
- `src/qbt/backtest/CLAUDE.md` — walkforward.py 함수 목록 업데이트
- `scripts/CLAUDE.md` — 신규 스크립트 설명 추가
- 루트 `CLAUDE.md` — 디렉토리 구조에 `buffer_zone_atr_tqqq_wfo/` 추가, 결과 파일 목록 추가

### 데이터/결과 영향

- 신규 디렉토리 생성: `storage/results/backtest/buffer_zone_atr_tqqq_wfo/`
- 신규 파일 4개: `signal.csv`, `equity.csv`, `trades.csv`, `summary.json`
- 기존 결과 파일 변경 없음
- 기존 대시보드 코드 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 비즈니스 로직 + 테스트 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/walkforward.py`에 `load_wfo_results_from_csv()` 함수 추가

```python
def load_wfo_results_from_csv(csv_path: Path) -> list[WfoWindowResultDict]:
    """WFO 결과 CSV를 읽어 WfoWindowResultDict 리스트로 반환한다.

    walkforward_dynamic.csv (또는 다른 WFO 결과 CSV)를 파싱하여
    build_params_schedule()에 전달 가능한 형식으로 변환한다.

    Args:
        csv_path: walkforward_*.csv 파일 경로

    Returns:
        WFO 윈도우 결과 딕셔너리 리스트

    Raises:
        FileNotFoundError: CSV 파일이 존재하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
    """
```

함수 구현 상세:
1. `csv_path` 존재 여부 확인 (없으면 FileNotFoundError)
2. `pd.read_csv(csv_path)` 로 로딩
3. 필수 컬럼 검증: `oos_start`, `best_ma_window`, `best_buy_buffer_zone_pct`, `best_sell_buffer_zone_pct`, `best_hold_days`, `best_recent_months` (없으면 ValueError)
4. 정수 컬럼 타입 보정: `best_ma_window`, `best_hold_days` → int 변환 (pandas CSV 로딩 시 float64 가능성 대비)
5. ATR 컬럼은 선택적: `best_atr_period`, `best_atr_multiplier` (없으면 무시)
6. `df.to_dict("records")` 반환 → `list[WfoWindowResultDict]` 호환

- [x] `tests/test_wfo_stitched.py` 테스트 추가

테스트 케이스:
1. `test_load_wfo_results_from_csv_basic`: 정상 CSV → 올바른 dict 리스트 반환, 타입 검증
2. `test_load_wfo_results_from_csv_with_atr`: ATR 컬럼 포함 CSV → ATR 파라미터 포함 확인
3. `test_load_wfo_results_from_csv_file_not_found`: 존재하지 않는 경로 → FileNotFoundError
4. `test_load_wfo_results_from_csv_missing_columns`: 필수 컬럼 누락 → ValueError
5. `test_load_wfo_results_builds_valid_params_schedule`: CSV → load → build_params_schedule → 유효한 (initial_params, schedule) 반환 확인

---

### Phase 2 — CLI 스크립트 구현 (그린 유지)

**작업 내용**:

- [x] `scripts/backtest/run_wfo_stitched_backtest.py` 신규 생성

스크립트 구조 (CLI 표준 구조 준수):

```python
"""WFO Stitched 백테스트 결과를 대시보드 호환 형식으로 저장한다.

run_walkforward.py 실행 결과(walkforward_dynamic.csv)를 읽어
params_schedule 기반으로 OOS 구간 전체를 1회 실행하고,
app_single_backtest.py 대시보드에서 시각화할 수 있는 형식으로 저장한다.

선행 스크립트:
    poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_atr_tqqq

실행 명령어:
    poetry run python scripts/backtest/run_wfo_stitched_backtest.py
"""
```

실행 흐름:
1. 로거 초기화
2. walkforward_dynamic.csv 로딩 (`load_wfo_results_from_csv()`)
3. `build_params_schedule()` 호출 → `(initial_params, schedule)` 획득
4. 첫 OOS 시작 ~ 마지막 OOS 종료 날짜 범위 추출
5. signal_df(QQQ), trade_df(TQQQ 합성) 로딩 + `extract_overlap_period()`
6. OOS 범위로 signal_df, trade_df 필터링
7. 필요한 MA 윈도우 전부 사전 계산 (`add_single_moving_average()`)
8. `run_buffer_strategy(params_schedule=schedule)` 실행
9. 결과 저장 (아래 형식)
10. 메타데이터 저장 (`save_metadata()`)
11. 요약 출력 + 성공 코드 반환

저장 파일 상세:

**signal.csv** (OOS 구간 signal_df):
- 컬럼: Date, Open, High, Low, Close, Volume, ma_200, change_pct
- change_pct: 전일 종가 대비 변동률 (%)
- 반올림: OHLC/MA → 6자리, change_pct → 2자리
- MA 컬럼: `ma_200` 고정 (11개 윈도우 중 10개가 MA=200 사용)

**equity.csv** (에쿼티 곡선 + 밴드 + 드로우다운):
- 컬럼: Date, equity, position, buy_buffer_pct, sell_buffer_pct, upper_band, lower_band, **drawdown_pct**
- drawdown_pct: `(equity - peak) / peak * 100` (단일 백테스트와 동일 계산)
- 반올림: equity → 0자리, drawdown_pct → 2자리, buffer_pct → 4자리, band → 6자리

**trades.csv** (매매 내역):
- 컬럼: entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, buy_buffer_pct, hold_days_used, recent_sell_count, **holding_days**
- holding_days: `(exit_date - entry_date).days` (저장 직전 계산)
- 반올림: 가격 → 6자리, pnl → 0자리, pnl_pct → 4자리, buy_buffer_pct → 4자리

**summary.json**:
```json
{
  "display_name": "버퍼존 전략 ATR WFO (TQQQ)",
  "summary": { "initial_capital": ..., "final_capital": ..., "cagr": ..., "mdd": ..., ... },
  "params": {
    "wfo_mode": "dynamic",
    "n_windows": 11,
    "oos_start": "2005-03-01",
    "oos_end": "2026-02-17",
    "source_csv": "walkforward_dynamic.csv",
    "latest_window_params": {
      "ma_window": 200,
      "buy_buffer_zone_pct": 0.03,
      "sell_buffer_zone_pct": 0.03,
      "hold_days": 3,
      "recent_months": 0,
      "atr_period": 14,
      "atr_multiplier": 3.0
    }
  },
  "monthly_returns": [...],
  "data_info": {
    "signal_ticker": "QQQ",
    "trade_ticker": "TQQQ_synthetic",
    "start_date": "2005-03-01",
    "end_date": "2026-02-17",
    "total_days": ...
  }
}
```

결과 저장 경로: `storage/results/backtest/buffer_zone_atr_tqqq_wfo/`

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트: walkforward.py 함수 목록에 `load_wfo_results_from_csv()` 추가
- [x] `scripts/CLAUDE.md` 업데이트: 백테스트 섹션에 `run_wfo_stitched_backtest.py` 설명 추가
- [x] 루트 `CLAUDE.md` 업데이트: 디렉토리 구조에 `buffer_zone_atr_tqqq_wfo/` 추가, 결과 파일 목록에 WFO stitched 결과 추가
- [x] `poetry run black .` 실행
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=424, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFO Stitched 대시보드 시각화 스크립트 신규 추가
2. 백테스트 / WFO Dynamic 결과를 기존 대시보드에서 시각화할 수 있도록 저장 스크립트 추가
3. 백테스트 / params_schedule 기반 WFO Stitched 백테스트 결과 대시보드 통합
4. 백테스트 / WFO Stitched 결과 대시보드 호환 저장 모듈 및 스크립트 추가
5. 백테스트 / WFO Stitched OOS 시각화를 위한 대시보드 결과 생성기 추가

## 7) 리스크(Risks)

| 리스크 | 확률 | 완화책 |
|--------|------|--------|
| MA 라인 부정확 (Window 0에서 MA=150이나 ma_200 표시) | 확정 | 밴드(upper/lower)가 정확한 값을 표시하므로 매매 로직 관찰에 지장 없음. 대시보드에서 밴드가 MA보다 우선적으로 참조됨 |
| walkforward_dynamic.csv 미존재 시 실행 실패 | 낮음 | FileNotFoundError + 명확한 안내 메시지 (선행 스크립트 실행 안내) |
| pandas CSV 타입 추론 오류 (int → float) | 낮음 | `load_wfo_results_from_csv()`에서 명시적 타입 보정 |

## 8) 메모(Notes)

### 핵심 결정 사항

- **대상 전략**: buffer_zone_atr_tqqq Dynamic 모드 전용 (사용자 결정 2026-03-02)
- **display_name**: "버퍼존 전략 ATR WFO (TQQQ)" (사용자 결정 2026-03-02)
- **strategy_name (디렉토리명)**: `buffer_zone_atr_tqqq_wfo`
- **MA 라인**: ma_200 고정 (10/11 윈도우가 MA=200, Window 0만 MA=150)
- **Phase 0 불필요**: 기존 인바리언트/정합성 변경 없음. 새로운 출력 형식 추가만 해당

### 후속 확장 가능성

- 다른 전략(buffer_zone_tqqq, buffer_zone_qqq) WFO stitched 시각화
- WFO Sell Fixed / Fully Fixed 모드 시각화
- Composite MA 라인 (params_schedule 전환 시점에 맞춰 active MA 표시)

### 진행 로그 (KST)

- 2026-03-02 22:00: Draft 작성
- 2026-03-03 00:00: Phase 1~3 완료, validate_project.py 통과 (passed=424, failed=0, skipped=0), Done

---
