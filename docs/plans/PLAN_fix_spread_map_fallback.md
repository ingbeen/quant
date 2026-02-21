# PLAN: optimization.py spread_map 조회 fallback 적용

- 작성일: 2026-02-21 16:40
- 상태: Done
- 마지막 업데이트: 2026-02-21 16:45

## Goal

`optimization.py:_precompute_daily_costs_vectorized`에서 `spread_map` 조회 시
2개월 fallback을 적용하여, FFR 데이터 누락 월에도 정상 동작하도록 수정한다.

## Non-Goals

- `_build_monthly_spread_map_from_dict` 함수 구조 변경
- 다른 모듈의 fallback 로직 변경 (이미 적용됨)

## Context

### 배경

FFR 데이터는 `2026-01`까지 존재하지만 TQQQ 주가 데이터에 `2026-02` 거래일이 포함되어 있다.
`_precompute_daily_costs_vectorized`에서 FFR/Expense 조회는 `lookup_ffr`/`lookup_expense`로
fallback이 적용되지만, `spread_map` 조회는 strict dict lookup으로 fallback이 없어
`ValueError: spread_map에 키 누락: 2026-02` 에러가 발생한다.

### 영향받는 규칙

- `CLAUDE.md` (루트): 코딩 표준, 상수 관리
- `src/qbt/tqqq/CLAUDE.md`: 도메인 규칙 (FFR 2개월 fallback 정책)
- `tests/CLAUDE.md`: 테스트 작성 원칙

## Definition of Done

- [x] 에러 원인 파악 및 수정 범위 확정
- [x] `_precompute_daily_costs_vectorized`의 spread 조회에 `lookup_monthly_data` fallback 적용
- [x] 기존 테스트 통과 확인
- [x] `poetry run python validate_project.py` 통과 (passed=317, failed=0, skipped=0)

## Scope

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/tqqq/optimization.py` | spread 조회에 `lookup_monthly_data` fallback 적용, import 추가 |

### 변경 없는 파일

- `simulation.py`: `_resolve_spread`에서 이미 `lookup_monthly_data` 사용
- `walkforward.py`: `simulate()` 경유로 이미 fallback 적용됨
- `data_loader.py`: 변경 불필요

## Phase 1: spread_map 조회 fallback 적용

### 1-1. import 추가 (`optimization.py`)

기존 import에 `lookup_monthly_data`와 `MAX_FFR_MONTHS_DIFF` 추가:

```python
# 기존
from qbt.tqqq.data_loader import (
    create_expense_dict,
    create_ffr_dict,
    lookup_expense,
    lookup_ffr,
)

# 변경
from qbt.tqqq.data_loader import (
    create_expense_dict,
    create_ffr_dict,
    lookup_expense,
    lookup_ffr,
    lookup_monthly_data,
)
```

`MAX_FFR_MONTHS_DIFF`는 `qbt.tqqq.constants`에 정의되어 있으나, 현재 `optimization.py`에서는
import하지 않는다. 추가 import 필요:

```python
from qbt.tqqq.constants import (
    ...기존...,
    MAX_FFR_MONTHS_DIFF,
)
```

### 1-2. `_precompute_daily_costs_vectorized` spread 조회 수정

```python
# 기존 (strict dict lookup, fallback 없음)
if month_key not in spread_map:
    raise ValueError(
        f"spread_map에 키 누락: {month_key}\n"
        f"보유 키: {sorted(spread_map.keys())[:5]}{'...' if len(spread_map) > 5 else ''}"
    )
spread = spread_map[month_key]

# 변경 (lookup_monthly_data로 2개월 fallback 적용)
spread = lookup_monthly_data(d, spread_map, MAX_FFR_MONTHS_DIFF, "spread")
```

`d`는 이미 `date(year, month, 1)`로 생성되어 있으므로 바로 사용 가능하다.
`MAX_FFR_MONTHS_DIFF = 2`이므로 spread도 FFR과 동일하게 최대 2개월 이전 값을 fallback으로 사용한다.

### 1-3. Docstring 수정

`_precompute_daily_costs_vectorized`의 Docstring에서:
- `Raises` 섹션의 "spread_map에 필요한 월 키가 누락된 경우" → "spread 데이터 조회 실패 시 (최대 2개월 fallback 초과)"로 수정
- 함수 설명에 "기존 _calculate_daily_cost와 동일한 비용 공식 및 fallback 로직을 적용한다." 문구가 이미 있으므로 일관성 유지됨

### Validation

```bash
poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py
poetry run python validate_project.py
```

## Risks

- 낮음: `lookup_monthly_data`는 이미 프로젝트 전반에서 사용 중인 검증된 함수

## Notes

### FFR fallback 적용 현황 (분석 결과)

fallback 미적용 지점은 `optimization.py:_precompute_daily_costs_vectorized`의 spread_map 조회 **1곳**뿐.
다른 모든 FFR 사용 지점은 `lookup_ffr`, `lookup_monthly_data`, 또는 `simulate()` → `_resolve_spread` 경유로
이미 2개월 fallback이 적용되어 있다.

### Commit Messages (Final candidates)

1. TQQQ시뮬레이션 / optimization spread_map 조회에 2개월 fallback 적용
2. TQQQ시뮬레이션 / _precompute_daily_costs_vectorized spread 조회 fallback 누락 수정
3. TQQQ시뮬레이션 / spread_map strict lookup을 lookup_monthly_data fallback으로 교체
4. TQQQ시뮬레이션 / optimization.py FFR 최신 월 누락 시 spread 조회 에러 수정
5. TQQQ시뮬레이션 / spread_map 2개월 fallback 미적용 버그 수정
