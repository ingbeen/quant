# PLAN: 백테스트 결과 파일 가격 반올림 6자리 통일

- 상태: Done
- 작성일: 2026-02-19 23:00
- 마지막 업데이트: 2026-02-19 23:10

---

## Goal

백테스트 단일 실행 결과 파일(signal, equity, trades CSV + summary JSON)의 가격 관련 컬럼을
소수점 6자리로 통일하고, 관련 로그 출력도 동일하게 맞춘다.

## Non-Goals

- grid_results.csv 반올림 변경 (별도 스크립트, 이번 범위 아님)
- 대시보드 앱(app_single_backtest.py) 표시 포맷 변경 (읽기 전용, CSV 데이터 자체가 변경되면 자동 반영)
- 비즈니스 로직 내부 계산 정밀도 변경

## Context

루트 CLAUDE.md의 "출력 데이터 반올림 규칙"이 가격 6자리로 통일되었으나,
`scripts/backtest/run_single_backtest.py`의 `_save_results()` 함수에서
signal CSV와 equity CSV의 가격 컬럼이 아직 2자리로 반올림되고 있다.
trades CSV의 체결가는 이미 6자리. 로그 출력의 거래 내역 테이블도 `.2f` 포맷 사용 중.

### 영향받는 규칙

- 루트 [`CLAUDE.md`](../../CLAUDE.md): 출력 데이터 반올림 규칙
- [`src/qbt/backtest/CLAUDE.md`](../../src/qbt/backtest/CLAUDE.md): 백테스트 도메인 가이드
- [`scripts/CLAUDE.md`](../../scripts/CLAUDE.md): CLI 스크립트 계층 가이드

해당 문서들에 기재된 규칙을 모두 숙지하고 준수한다.

## Definition of Done

- [x] 변경 대상 파일 식별 완료
- [x] signal CSV: OHLC + MA 컬럼 6자리 반올림
- [x] equity CSV: upper_band, lower_band 6자리 반올림
- [x] 로그: 거래 내역 테이블 진입가/청산가 `.6f` 포맷
- [x] `poetry run python validate_project.py` 통과 (passed=287, failed=0, skipped=0)

## Scope

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `scripts/backtest/run_single_backtest.py` | 반올림 자릿수 변경 + 로그 포맷 변경 |

### 영향받는 결과 파일

| 결과 파일 | 변경되는 컬럼 | 변경 전 → 후 |
|-----------|-------------|-------------|
| `single_backtest_signal.csv` | Open, High, Low, Close, ma_N | 2자리 → 6자리 |
| `single_backtest_equity.csv` | upper_band, lower_band | 2자리 → 6자리 |
| `single_backtest_trades.csv` | (변경 없음, 이미 6자리) | — |
| `single_backtest_summary.json` | (변경 없음, 가격 데이터 없음) | — |

### 변경하지 않는 항목 (이미 규칙 준수)

- equity CSV: `equity` (정수), `buffer_zone_pct` (4자리), `drawdown_pct` (2자리, 백분율)
- trades CSV: `entry_price`/`exit_price` (이미 6자리), `pnl` (정수), `pnl_pct` (4자리)
- signal CSV: `change_pct` (2자리, 백분율)
- summary JSON: 자본금 (정수), 백분율 지표 (2자리), 비율 (4자리)

---

## Phase 1: 코드 변경 + 검증

### 1-1. signal CSV 반올림 변경 (line 175-184)

```python
# 변경 전
signal_export = signal_export.round(
    {
        COL_OPEN: 2,
        COL_HIGH: 2,
        COL_LOW: 2,
        COL_CLOSE: 2,
        ma_col: 2,
        "change_pct": 2,
    }
)

# 변경 후
signal_export = signal_export.round(
    {
        COL_OPEN: 6,
        COL_HIGH: 6,
        COL_LOW: 6,
        COL_CLOSE: 6,
        ma_col: 6,
        "change_pct": 2,
    }
)
```

### 1-2. equity CSV 반올림 변경 (line 194-202)

```python
# 변경 전
equity_export = equity_export.round(
    {
        "equity": 0,
        "buffer_zone_pct": 4,
        "upper_band": 2,
        "lower_band": 2,
        "drawdown_pct": 2,
    }
)

# 변경 후
equity_export = equity_export.round(
    {
        "equity": 0,
        "buffer_zone_pct": 4,
        "upper_band": 6,
        "lower_band": 6,
        "drawdown_pct": 2,
    }
)
```

### 1-3. 로그 포맷 변경 (line 421-422)

```python
# 변경 전
f"{trade['entry_price']:.2f}",
f"{trade['exit_price']:.2f}",

# 변경 후
f"{trade['entry_price']:.6f}",
f"{trade['exit_price']:.6f}",
```

### 1-4. Validation

```bash
poetry run python validate_project.py
```

---

## Risks

| 리스크 | 완화책 |
|--------|--------|
| 대시보드 표시에서 불필요하게 긴 소수점 | 대시보드는 차트 렌더링 용도로 표시 포맷이 별도 — CSV 정밀도와 무관 |

---

## Commit Messages (Final candidates)

1. 백테스트 / 결과 CSV 가격 반올림 6자리 통일 (signal OHLC·MA, equity 밴드)
2. 백테스트 / signal·equity CSV 가격 소수점 6자리 통일 + 로그 포맷 일치
3. 백테스트 / 가격 컬럼 반올림 2→6자리 통일 (CLAUDE.md 규칙 반영)
4. 백테스트 / 결과 파일 가격 정밀도 6자리 통일 (signal, equity CSV + 로그)
5. 백테스트 / 가격 반올림 6자리 통일 (signal CSV, equity CSV, 로그 테이블)
