# 테스트 수정 필요 사항

테스트를 실행한 결과, 실제 프로덕션 코드와 테스트 가정이 일부 다릅니다.
아래 수정 사항을 반영하면 테스트가 통과할 것입니다.

## 발견된 차이점

### 1. 컬럼명 형식 (analysis.py)

**테스트 가정**: `MA_3` (대문자)
**실제 코드**: `ma_3` (소문자)

**수정 필요 파일**: `tests/test_analysis.py`

### 2. 상수명 (common_constants.py)

**테스트 가정**: `META_FILE_PATH`
**실제 코드**: `META_JSON_PATH`

**수정 필요 파일**: `tests/conftest.py`

### 3. 상수명 (backtest/constants.py)

**테스트 가정**: `INITIAL_CAPITAL`, `SLIPPAGE_PCT`
**실제 코드**: `DEFAULT_INITIAL_CAPITAL`, `SLIPPAGE_RATE`

**수정 필요 파일**: `tests/test_strategy.py` (이미 수정 완료)

## 빠른 수정 방법

다음 수정 사항을 적용하면 대부분의 테스트가 통과할 것입니다.

### 옵션 1: 자동 수정 스크립트 실행

```bash
# 프로젝트 루트에서 실행
python scripts/fix_tests.py
```

### 옵션 2: 수동 수정

1. **`tests/conftest.py`** 수정:
   - 125번 줄: `META_FILE_PATH` → `META_JSON_PATH`

2. **`tests/test_analysis.py`** 수정:
   - 모든 `MA_3`, `MA_5`, `MA_10` → `ma_3`, `ma_5`, `ma_10`

3. **`tests/test_strategy.py`** 수정 (이미 완료):
   - `INITIAL_CAPITAL` → `DEFAULT_INITIAL_CAPITAL`
   - `SLIPPAGE_PCT` → `SLIPPAGE_RATE`

## 추가 확인 필요 사항

실제 함수 시그니처를 확인해야 하는 모듈:

1. **`qbt.utils.data_loader.py`**
   - `load_stock_data()`: 실제 예외 메시지 확인
   - `load_ffr_data()`: VALUE → FFR rename 여부 확인
   - `load_comparison_data()`: 컬럼명 확인

2. **`qbt.utils.meta_manager.py`**
   - `save_metadata()`: 실제 csv_type 값들 확인
   - 실제 메타데이터 구조 확인

3. **`qbt.backtest.analysis.py`**
   - `calculate_summary()`: 실제 반환 딕셔너리 키 확인

4. **`qbt.backtest.strategy.py`**
   - `run_buy_and_hold()`: 실제 파라미터 형식 확인
   - `run_buffer_strategy()`: 실제 파라미터 형식 확인

5. **`qbt/tqqq/simulation.py`**
   - 모든 함수의 실제 시그니처 및 동작 확인

## 권장 작업 순서

1. **conftest.py 먼저 수정** (다른 모든 테스트가 의존)
2. **test_data_loader.py 수정 후 실행** (기본 데이터 로딩 검증)
3. **test_analysis.py 수정** (컬럼명 대소문자)
4. **나머지 테스트 하나씩 수정 및 실행**

## 테스트 개발 방법론

앞으로 새로운 테스트 작성 시:

1. **프로덕션 코드 먼저 확인**:
   ```python
   # 실제 함수 읽기
   from qbt.backtest.analysis import add_single_moving_average
   help(add_single_moving_average)
   ```

2. **작은 예시로 동작 확인**:
   ```python
   import pandas as pd
   from datetime import date

   df = pd.DataFrame({'Date': [date(2023, 1, 1)], 'Close': [100.0]})
   result = add_single_moving_average(df, window=3)
   print(result.columns)  # 실제 컬럼명 확인
   ```

3. **그 다음 테스트 작성**

이렇게 하면 테스트와 프로덕션 코드의 불일치를 최소화할 수 있습니다.
