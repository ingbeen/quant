# 워킹 포워드 테스트 로직 문서

> **작성일**: 2025-11-29
> **상태**: 삭제됨 (향후 재구현 예정)
> **원본 위치**: `scripts/run_walkforward.py`, `src/qbt/backtest/strategy.py`

## 개요

워킹 포워드 테스트(Walking Forward Test)는 과거 데이터를 학습 구간(Train)과 테스트 구간(Test)으로 롤링하며 나누어, 각 학습 구간에서 최적 파라미터를 찾고 해당 파라미터로 테스트 구간에서 백테스트를 실행하는 방법입니다.

이는 과최적화(overfitting)를 방지하고 전략의 강건성을 검증하는 데 유용합니다.

---

## 핵심 개념

### 1. 윈도우 구조

```
전체 데이터: |------ Train 1 ------|-- Test 1 --|------ Train 2 ------|-- Test 2 --|...
              [그리드 서치로 최적화]  [검증]      [그리드 서치로 최적화]  [검증]
```

- **Train 구간**: 그리드 서치를 통해 최적 파라미터 탐색
- **Test 구간**: Train에서 찾은 파라미터로 실제 백테스트 실행
- **롤링**: Test 구간의 길이만큼씩 윈도우를 이동

### 2. 파라미터 선택 기준

Train 구간의 그리드 서치 결과에서 다음 중 하나를 기준으로 최적 파라미터를 선택:

- `cagr`: 연평균 복리 수익률 (CAGR) 최대화
- `total_return_pct`: 총 수익률 최대화
- `mdd`: 최대 낙폭(MDD) 최소화 (음수이므로 최댓값 선택)

---

## 주요 함수

### 1. `generate_walkforward_windows()`

**목적**: Train/Test 윈도우 생성

**위치**: `src/qbt/backtest/strategy.py` (라인 504-566)

**로직**:
1. 전체 데이터의 시작일과 종료일 확인
2. 현재 Train 시작일로부터 다음을 계산:
   - Train 종료일 = Train 시작일 + (train_years × 365일)
   - Test 시작일 = Train 종료일 + 1일
   - Test 종료일 = Test 시작일 + (test_years × 365일)
3. 데이터 범위 검증:
   - Train 종료일이 전체 데이터 범위를 초과하면 중단
   - Test 종료일이 초과하면 마지막 날까지로 조정
   - Test 기간이 30일 미만이면 스킵
4. 윈도우 정보를 리스트에 추가
5. 다음 윈도우로 이동: Train 시작일 += (test_years × 365일)
6. 반복하여 모든 윈도우 생성

**반환값**:
```python
[
    {
        "train_start": date(2015, 1, 1),
        "train_end": date(2020, 1, 1),
        "test_start": date(2020, 1, 2),
        "test_end": date(2021, 1, 1),
    },
    ...
]
```

**파라미터**:
- `df`: 주식 데이터 DataFrame (Date 컬럼 필수)
- `train_years`: 학습 기간 (년, 기본값: 5)
- `test_years`: 테스트 기간 (년, 기본값: 1)

---

### 2. `run_walkforward()`

**목적**: 워킹 포워드 테스트 메인 실행 함수

**위치**: `src/qbt/backtest/strategy.py` (라인 569-813)

**로직**:

#### 초기화
1. `generate_walkforward_windows()`를 호출하여 윈도우 리스트 생성
2. 윈도우가 없으면 ValueError 발생
3. Date 컬럼을 `datetime.date` 타입으로 변환
4. 결과 리스트와 자본 곡선 세그먼트 초기화
5. 현재 자본 = 초기 자본

#### 각 윈도우에 대한 반복
각 윈도우마다 다음을 수행:

**2-1. Train 데이터 추출**
- 윈도우의 `train_start` ~ `train_end` 기간 데이터 필터링
- Train 데이터가 100행 미만이면 경고 후 스킵

**2-2. Train 구간 그리드 서치**
- `run_grid_search()` 호출하여 파라미터 조합별 백테스트 실행
- 초기 자본은 현재 자본 사용 (복리 효과)
- 실패 시 경고 후 다음 윈도우로 이동

**2-3. 최적 파라미터 선택**
- `selection_metric`에 따라 최적 파라미터 선택:
  - `mdd`: 최댓값 선택 (음수이므로 가장 작은 낙폭)
  - `cagr`, `total_return_pct` 등: 최댓값 선택
- 선택된 파라미터 로깅

**2-4. Test 데이터 추출**
- 윈도우의 `test_start` ~ `test_end` 기간 데이터 필터링
- Test 데이터가 30행 미만이면 경고 후 스킵

**2-5. Test 구간 백테스트 실행**
- `add_moving_averages()`: 최적 파라미터로 이동평균 계산
- `StrategyParams` 객체 생성
- `run_strategy()`: 백테스트 실행하여 자본 곡선과 요약 지표 계산

**2-6. 결과 기록**
- 윈도우별 결과를 딕셔너리로 저장:
  - 윈도우 인덱스, Train/Test 기간
  - 최적 파라미터 (MA 타입, 윈도우, 손절율, 저점 탐색 기간)
  - Train 구간의 선택 기준 지표값
  - Test 구간의 성과 지표 (수익률, CAGR, MDD, 거래 횟수, 승률)
  - 시작 자본, 종료 자본

**2-7. 자본 곡선 연결**
- Test 구간의 자본 곡선에 윈도우 인덱스 추가
- 세그먼트 리스트에 추가
- 현재 자본 = Test 구간의 최종 자본 (복리 효과)

#### 결과 생성
**3. 결과 DataFrame 생성**
- 윈도우별 결과 리스트를 DataFrame으로 변환

**4. 자본 곡선 연결**
- 모든 세그먼트를 하나의 DataFrame으로 연결

**5. 전체 요약 지표 계산**
- 최종 자본, 총 수익, 총 수익률 계산
- 기간 계산: 첫 Test 시작일 ~ 마지막 Test 종료일
- CAGR 계산: `((최종자본 / 초기자본) ^ (1 / 년수) - 1) × 100`
- MDD 계산: 연결된 자본 곡선에서 peak 대비 최대 하락폭 계산
- 평균 Test 수익률 계산

**반환값**:
```python
(
    walkforward_results_df,  # 구간별 결과
    combined_equity_df,      # 연결된 자본 곡선
    summary                  # 전체 요약 지표
)
```

**파라미터**:
- `df`: 주식 데이터 DataFrame
- `short_window_list`: 단기 이동평균 기간 목록
- `long_window_list`: 장기 이동평균 기간 목록
- `stop_loss_pct_list`: 손절 비율 목록
- `lookback_for_low_list`: 최근 저점 탐색 기간 목록
- `train_years`: 학습 기간 (년, 기본값: 5)
- `test_years`: 테스트 기간 (년, 기본값: 1)
- `initial_capital`: 초기 자본금 (기본값: 10,000,000)
- `selection_metric`: 최적 파라미터 선택 기준 (기본값: "cagr")

---

## CLI 스크립트 로직

### `scripts/run_walkforward.py`

**주요 함수**:

#### 1. `parse_args()`
- argparse를 사용하여 CLI 인자 파싱
- 필수 인자:
  - `--train`: 학습 기간 (년)
  - `--test`: 테스트 기간 (년)
  - `--metric`: 최적 파라미터 선택 기준 (cagr, total_return_pct, mdd)

#### 2. `print_window_results(results_df)`
- 구간별 워킹 포워드 결과를 테이블 형식으로 출력
- 컬럼: 윈도우, Train 기간, Test 기간, MA, Short, Long, Test수익률, Test MDD
- `format_cell()` 함수로 정렬된 셀 출력

#### 3. `print_summary(wf_summary, bh_summary)`
- 워킹 포워드 테스트 전체 요약 출력
- Buy & Hold 벤치마크와 비교
- 수익률 차이, CAGR 차이 계산 및 출력

#### 4. `main()`
**실행 흐름**:
1. CLI 인자 파싱
2. 데이터 로딩 및 검증 (`load_and_validate_data()`)
3. 그리드 탐색 파라미터 로깅
4. `run_walkforward()` 호출하여 워킹 포워드 테스트 실행
5. `run_buy_and_hold()` 호출하여 벤치마크 실행
6. 구간별 결과 출력 (`print_window_results()`)
7. 요약 출력 (`print_summary()`)
8. 결과를 CSV 파일로 저장 (`data/raw/walkforward_results.csv`)
9. 성공 시 0, 실패 시 1 반환

**에러 처리**:
- `ValueError`: 값 오류 로깅 및 종료 코드 1 반환
- `Exception`: 예기치 않은 오류 로깅 및 종료 코드 1 반환

---

## 사용 예시

### 기본 사용법
```bash
# 5년 학습, 1년 테스트, CAGR 기준
poetry run python scripts/run_walkforward.py --train 5 --test 1 --metric cagr
```

### MDD 기준 최적화
```bash
# 3년 학습, 1년 테스트, MDD 기준
poetry run python scripts/run_walkforward.py --train 3 --test 1 --metric mdd
```

---

## 출력 형식

### 구간별 결과 예시
```
==================================================================================
[구간별 워킹 포워드 결과]
==================================================================================
  윈도우              Train 기간              Test 기간   MA   Short    Long    Test수익률      Test MDD
----------------------------------------------------------------------------------
       1     2015-01-01 ~ 2020-01-01     2020-01-02 ~ 2021-01-01  SMA       5      20        15.32%        -12.45%
       2     2016-01-01 ~ 2021-01-01     2021-01-02 ~ 2022-01-01  EMA      10      50        -5.20%        -18.32%
==================================================================================
```

### 전체 요약 예시
```
============================================================
[전체 요약]
============================================================

워킹 포워드 테스트:
  - 총 윈도우: 5개
  - 학습 기간: 5년
  - 테스트 기간: 1년
  - 선택 기준: cagr
  - 초기 자본: 10,000,000원
  - 최종 자본: 12,500,000원
  - 총 수익률: 25.00%
  - CAGR: 4.56%
  - MDD: -15.32%
  - 평균 Test 수익률: 5.00%

Buy & Hold 벤치마크:
  - 초기 자본: 10,000,000원
  - 최종 자본: 11,800,000원
  - 총 수익률: 18.00%
  - CAGR: 3.38%
  - MDD: -22.50%

비교:
  - 수익률 차이: +7.00%p
  - CAGR 차이: +1.18%p
============================================================
```

---

## 의존성

### 사용하는 함수 (유지됨)
- `run_grid_search()`: Train 구간에서 그리드 서치 수행
- `run_strategy()`: Test 구간에서 백테스트 실행
- `add_moving_averages()`: 이동평균 계산
- `run_buy_and_hold()`: 벤치마크 계산
- `load_and_validate_data()`: 데이터 로딩 및 검증
- `format_cell()`: CLI 출력 포맷팅

### 사용하는 설정 (config.py)
- `DEFAULT_DATA_FILE`: 기본 데이터 파일 경로
- `DEFAULT_INITIAL_CAPITAL`: 기본 초기 자본
- `DEFAULT_SHORT_WINDOW_LIST`: 단기 윈도우 목록
- `DEFAULT_LONG_WINDOW_LIST`: 장기 윈도우 목록
- `DEFAULT_STOP_LOSS_PCT_LIST`: 손절율 목록
- `DEFAULT_LOOKBACK_FOR_LOW_LIST`: 저점 탐색 기간 목록

---

## 삭제 사유

1. **복잡도**: 워킹 포워드 테스트는 구현이 복잡하고 실행 시간이 오래 걸림
2. **사용 빈도**: 프로젝트 초기 단계에서 자주 사용되지 않음
3. **YAGNI 원칙**: 필요성이 확인되기 전까지 복잡한 기능은 제거하여 코드베이스 단순화

---

## 재구현 시 고려사항

향후 워킹 포워드 테스트를 재구현할 때 다음을 고려:

1. **성능 최적화**:
   - 병렬 처리를 통한 그리드 서치 속도 개선
   - 캐싱을 통한 중복 계산 방지

2. **유연성 향상**:
   - 고정 기간(년) 대신 슬라이딩 윈도우 방식 지원
   - 앵커드 워킹 포워드(Anchored Walking Forward) 옵션 추가

3. **결과 시각화**:
   - 구간별 성과 그래프
   - 파라미터 변화 추이 시각화
   - HTML 리포트 생성

4. **통계적 검증**:
   - 구간 간 성과 일관성 검증
   - 파라미터 안정성 분석
