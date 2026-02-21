# 미청산 포지션 Buy 마커 표시 + 날짜 표기 한국식 변경

- 상태: Done
- 작성일: 2026-02-21 17:00
- 마지막 업데이트: 2026-02-21 17:30

## Goal

1. 백테스트 대시보드 메인 차트에서 미청산 포지션(마지막 Buy 후 Sell 미발생)의 Buy 마커를 표시한다
2. 메인 차트 하단 날짜 표기를 한국식 "2025-12-01" 형식으로 변경한다

## Non-Goals

- 백테스트 엔진 정책 변경 (강제청산 등)
- 성과 지표(CAGR, MDD 등) 변경
- vendor TSX 코드 변경

## Context

### 문제

- `trades_df`에는 완료된 거래(Buy→Sell 쌍)만 기록됨
- `_build_markers()`가 `trades_df`만 순회하므로 미청산 포지션의 Buy 마커가 누락됨
- Buy & Hold 전략은 매도가 없어 Buy 마커가 전혀 표시되지 않음

### 방안 D 선택

`summary` dict에 `open_position` 필드를 추가하여 `summary.json`에 자동 포함시키고, 앱에서 Feature Detection으로 마커를 생성한다.

### 영향받는 규칙

아래 문서들에 기재된 규칙을 모두 숙지하고 준수한다:

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## Definition of Done

- [x] `OpenPositionDict` TypedDict 정의 (`types.py`)
- [x] `SummaryDict`에 `open_position: NotRequired[OpenPositionDict]` 추가
- [x] `run_buffer_strategy()` 종료 시 미청산 포지션이면 `open_position` 포함
- [x] `run_buy_and_hold()` 종료 시 `open_position` 포함 (항상 보유중)
- [x] `_save_summary_json()`에서 `open_position` 저장
- [x] `app_single_backtest.py`에서 미청산 Buy 마커 생성
- [x] `app_single_backtest.py`에서 날짜 표기 한국식 변경
- [x] 기존 테스트 통과 + 새 테스트 추가
- [x] `poetry run python validate_project.py` passed=전체, failed=0, skipped=0

## Scope

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/types.py` | `OpenPositionDict` 추가, `SummaryDict`에 필드 추가 |
| `src/qbt/backtest/strategies/buffer_zone_helpers.py` | `run_buffer_strategy()` 끝에 open_position 추가 |
| `src/qbt/backtest/strategies/buy_and_hold.py` | `run_buy_and_hold()` 끝에 open_position 추가 |
| `scripts/backtest/run_single_backtest.py` | `_save_summary_json()`에 open_position 저장 |
| `scripts/backtest/app_single_backtest.py` | 마커 빌더 함수 추가 + localization 추가 |
| `tests/test_buffer_zone_helpers.py` | open_position 검증 테스트 추가 |
| `tests/test_buy_and_hold.py` | open_position 검증 테스트 추가 |

### 데이터/결과 영향

- `summary.json`에 `open_position` 필드 추가 (기존 필드 변경 없음)
- 기존 성과 지표에 영향 없음

## Phases

### Phase 1: 타입 정의 + 비즈니스 로직

**1-1. `src/qbt/backtest/types.py`**

```python
class OpenPositionDict(TypedDict):
    """미청산 포지션 정보. summary에 포함되어 summary.json에 저장된다."""
    entry_date: str      # ISO format "YYYY-MM-DD"
    entry_price: float   # 진입가 (슬리피지 반영, 6자리)
    shares: int          # 보유 수량

class SummaryDict(TypedDict):
    # ... 기존 필드 ...
    open_position: NotRequired[OpenPositionDict]  # 미청산 포지션 (없으면 전량 청산 상태)
```

**1-2. `src/qbt/backtest/strategies/buffer_zone_helpers.py`**

`run_buffer_strategy()` 끝, 기존 주석 `# 5. 백테스트 종료 (강제청산 없음)` 뒤에:

```python
# 5-1. 미청산 포지션 정보 기록
if position > 0 and entry_date is not None:
    summary["open_position"] = {
        "entry_date": str(entry_date),
        "entry_price": round(entry_price, 6),
        "shares": position,
    }
```

위치: line 967 이후, `trades_df = pd.DataFrame(trades)` 이전이 아니라 summary 생성(line 973) 이후에 추가.

**1-3. `src/qbt/backtest/strategies/buy_and_hold.py`**

`run_buy_and_hold()` 끝, `calculate_summary` 호출 후:

```python
# 미청산 포지션 정보 기록 (Buy & Hold는 항상 보유중)
summary["open_position"] = {
    "entry_date": str(trade_df.iloc[0][COL_DATE]),
    "entry_price": round(buy_price, 6),
    "shares": shares,
}
```

위치: line 158 (`summary = calculate_summary(...)`) 이후.

**1-4. `scripts/backtest/run_single_backtest.py`**

`_save_summary_json()`에서 기존 `"end_date"` 저장 다음에:

```python
# 미청산 포지션 (있는 경우에만 저장)
open_position = result.summary.get("open_position")
if open_position is not None:
    summary_data["summary"]["open_position"] = {
        "entry_date": str(open_position["entry_date"]),
        "entry_price": round(float(str(open_position["entry_price"])), 6),
        "shares": int(str(open_position["shares"])),
    }
```

위치: line 207 (`"end_date": ...`) 이후.

### Phase 2: 시각화 (앱)

**2-1. `scripts/backtest/app_single_backtest.py` - 미청산 마커 함수 추가**

`_build_markers()` 함수 뒤에 새 함수 추가:

```python
def _build_open_position_marker(
    summary_data: dict[str, Any],
) -> list[dict[str, object]]:
    """미청산 포지션(summary.json의 open_position)의 Buy 마커를 생성한다."""
    summary = summary_data.get("summary", {})
    open_pos = summary.get("open_position")
    if open_pos is None:
        return []

    return [
        {
            "time": open_pos["entry_date"],
            "position": "belowBar",
            "color": COLOR_BUY_MARKER,
            "shape": "arrowUp",
            "text": f"Buy ${open_pos['entry_price']:.1f} (보유중)",
            "size": 2,
        }
    ]
```

**2-2. `_render_main_chart()` 수정**

기존 (lines 421-425):
```python
if has_trades:
    markers = _build_markers(trades_df)
    if markers:
        candle_series["markers"] = markers
```

변경 후:
```python
markers: list[dict[str, object]] = []
if has_trades:
    markers = _build_markers(trades_df)

# 미청산 포지션 마커 추가
open_markers = _build_open_position_marker(strategy["summary_data"])
markers.extend(open_markers)

if markers:
    candle_series["markers"] = markers
```

**2-3. 날짜 표기 한국식 변경**

`chart_theme`에 `localization` 추가 (line 388 부근):

```python
chart_theme = {
    "layout": { ... },
    "grid": { ... },
    "crosshair": { ... },
    "timeScale": {"minBarSpacing": 0.2},
    "localization": {
        "dateFormat": "yyyy-MM-dd",
    },
}
```

### Phase 3: 테스트 + 검증

**3-1. `tests/test_buffer_zone_helpers.py`**

기존 `TestRunBufferStrategy` 클래스에 테스트 추가:

- `test_open_position_included_when_holding`: 백테스트 종료 시 포지션 보유 중이면 summary에 open_position이 포함되는지 검증
- `test_open_position_absent_when_not_holding`: 포지션이 없을 때 open_position이 summary에 없는지 검증

**3-2. `tests/test_buy_and_hold.py`**

기존 테스트 클래스에 테스트 추가:

- `test_open_position_always_present`: Buy & Hold는 항상 open_position이 존재하는지 검증 (entry_date, entry_price, shares 키 존재 및 타입 확인)

**3-3. 전체 검증**

```bash
poetry run black .
poetry run python validate_project.py
```

## Risks

| 리스크 | 완화책 |
|--------|--------|
| lightweight-charts `localization.dateFormat` 미지원 버전 | vendor TSX에서 `...charts[0].chart`로 spread되므로 무시됨 (에러 없음). 실제 적용 여부는 앱 실행으로 확인 |
| 기존 summary.json과 호환성 | `open_position`은 NotRequired이므로 기존 JSON에 없어도 앱 정상 동작 (`.get()` 사용) |
| Buy & Hold shares=0 (자본 부족) | `shares > 0` 조건 추가하여 0주일 때는 open_position 미포함 |

## Notes

### 진행 로그

| 일시 | 내용 |
|------|------|
| 2026-02-21 17:00 | 계획서 작성 |

### Commit Messages (Final candidates)

1. `백테스트 / 미청산 포지션 Buy 마커 표시 및 날짜 표기 한국식 변경`
2. `백테스트 / summary에 open_position 필드 추가, 메인차트 미청산 마커 및 날짜 포맷 개선`
3. `백테스트 / 대시보드 미청산 포지션 마커 표시 + 날짜 형식 yyyy-MM-dd 적용`
4. `백테스트 / open_position 기반 마지막 Buy 마커 표시, 한국식 날짜 포맷 적용`
5. `백테스트 / 미청산 포지션 시각화 지원 (summary open_position + 한국식 날짜)`
