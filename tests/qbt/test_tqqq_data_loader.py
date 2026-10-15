"""
TQQQ 도메인 전용 데이터 로더 테스트

이 파일은 무엇을 검증하나요?
1. 월별 데이터(FFR · Expense Ratio) 파일이 정확히 로드되는가?
2. 일별 비교 데이터가 정확히 로드되는가?
3. 필수 컬럼이 없으면 즉시 실패하는가?
4. 파일이 없을 때 명확한 에러를 내는가?
5. FFR/Expense 딕셔너리 생성 및 조회가 정확한가?
6. 월별 데이터 중복/갭 · 상한을 넘는 값(% 로 적은 값) 검증이 작동하는가?
7. 운용비율 딕셔너리 확장이 정확한가? (1999-01부터 고정값 채우기)

왜 중요한가요?
TQQQ 시뮬레이션의 모든 결과는 FFR 데이터와 비교 데이터에 의존합니다.
잘못된 데이터는 잘못된 비용 계산과 검증 결과를 초래합니다.
"""

import math
from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_EXPENSE_DATE,
    COL_EXPENSE_VALUE,
    COL_FFR_DATE,
    COL_FFR_VALUE,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    DEFAULT_PRE_LISTING_EXPENSE_RATIO,
)
from qbt.tqqq.data_loader import (
    COMPARISON_COLUMNS,
    MAX_EXPENSE_VALUE,
    MAX_FFR_VALUE,
    _create_monthly_data_dict,
    _lookup_monthly_data,
    build_extended_expense_dict,
    create_expense_dict,
    create_ffr_dict,
    load_comparison_data,
    load_monthly_data,
    lookup_ffr,
)


class TestLoadMonthlyData:
    """월별 데이터(연방기금금리 · 운용비율) 파일 로딩 테스트"""

    def test_normal_load(self, tmp_path, sample_ffr_df):
        """
        월별 데이터 정상 로딩 테스트

        데이터 신뢰성: TQQQ 시뮬레이션의 비용 계산에 필수적인 데이터입니다.

        Given: DATE, VALUE 컬럼이 있는 CSV
        When: load_monthly_data 호출
        Then: DATE · VALUE 컬럼이 그대로 유지되고 행 수가 같다 (DATE 는 yyyy-mm 문자열 그대로)
        """
        # Given
        csv_path = tmp_path / "ffr.csv"
        sample_ffr_df.to_csv(csv_path, index=False)

        # When
        df = load_monthly_data(csv_path)

        # Then: 원본 CSV 스키마 회귀 탐지를 위해 리터럴 유지
        assert "VALUE" in df.columns, "VALUE 컬럼이 유지되어야 합니다"
        assert "DATE" in df.columns, "DATE 컬럼이 유지되어야 합니다"
        assert len(df) == 3
        assert df["DATE"].tolist() == sample_ffr_df["DATE"].tolist()

    def test_file_not_found(self, tmp_path):
        """
        월별 데이터 파일 부재 테스트

        Given: 존재하지 않는 파일
        When: load_monthly_data 호출
        Then: FileNotFoundError
        """
        # Given
        non_existent = tmp_path / "no_monthly.csv"

        # When & Then
        with pytest.raises(FileNotFoundError):
            load_monthly_data(non_existent)


class TestLoadComparisonData:
    """비교 데이터 (TQQQ 검증용) 로딩 테스트"""

    def test_normal_load(self, tmp_path):
        """
        비교 데이터 정상 로딩 테스트

        데이터 신뢰성: 시뮬레이션 결과를 실제 데이터와 비교 검증하는 데 사용됩니다.

        Given: Date, Simulated_Close, Actual_Close 컬럼
        When: load_comparison_data 호출
        Then:
          - COMPARISON_COLUMNS 컬럼 존재
          - Date 파싱 및 정렬
        """
        # Given: 비교 데이터 생성 (실제 컬럼명 사용)
        comparison_df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 2), date(2023, 1, 3)],
                COL_ACTUAL_CLOSE: [100.0, 102.0],
                COL_SIMUL_CLOSE: [100.5, 101.8],
                COL_ACTUAL_DAILY_RETURN: [0.01, 0.02],
                COL_SIMUL_DAILY_RETURN: [0.01, 0.02],
                COL_DAILY_RETURN_ABS_DIFF: [0.0, 0.0],
                COL_ACTUAL_CUMUL_RETURN: [0.01, 0.03],
                COL_SIMUL_CUMUL_RETURN: [0.01, 0.03],
                COL_CUMUL_MULTIPLE_LOG_DIFF_ABS: [0.0, 0.0],
                COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: [0.0, 0.0],
            }
        )
        csv_path = tmp_path / "comparison.csv"
        comparison_df.to_csv(csv_path, index=False)

        # When
        df = load_comparison_data(csv_path)

        # Then
        for col in COMPARISON_COLUMNS:
            assert col in df.columns, f"필수 컬럼 '{col}'이 없습니다"

        assert len(df) == 2
        # 날짜는 pandas Timestamp로 변환됨 (datetime.date가 아님)
        assert df[DISPLAY_DATE].dtype == "datetime64[ns]", "날짜가 datetime으로 변환되어야 합니다"

    def test_missing_columns(self, tmp_path):
        """
        비교 데이터 필수 컬럼 누락 테스트

        Given: Actual_Close 컬럼 누락
        When: load_comparison_data 호출
        Then: ValueError
        """
        # Given: 일부 컬럼 누락
        incomplete_df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 2)],
                COL_SIMUL_CLOSE: [100.0],
                # 다른 필수 컬럼들 누락
            }
        )
        csv_path = tmp_path / "incomplete_comparison.csv"
        incomplete_df.to_csv(csv_path, index=False)

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            load_comparison_data(csv_path)

        assert "필수 컬럼" in str(exc_info.value)


class TestCreateFfrDict:
    """FFR 딕셔너리 생성 함수 테스트"""

    def test_create_ffr_dict_normal(self):
        """
        정상적인 FFR 딕셔너리 생성 테스트

        Given: 정상적인 FFR DataFrame (중복 없음)
        When: create_ffr_dict 호출
        Then: {"YYYY-MM": ffr_value} 딕셔너리 반환
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02", "2023-03"], COL_FFR_VALUE: [0.045, 0.046, 0.047]})

        # When
        result = create_ffr_dict(ffr_df)

        # Then
        assert isinstance(result, dict)
        assert result == {"2023-01": 0.045, "2023-02": 0.046, "2023-03": 0.047}

    def test_create_ffr_dict_empty(self):
        """
        빈 DataFrame 입력 시 예외 발생 테스트

        Given: 빈 FFR DataFrame
        When: create_ffr_dict 호출
        Then: ValueError 발생
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: [], COL_FFR_VALUE: []})

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터가 비어있습니다"):
            create_ffr_dict(ffr_df)

    def test_create_ffr_dict_duplicate_month(self):
        """
        중복 월 발견 시 즉시 예외 발생 테스트 (중대 에러)

        Given: 중복 월이 포함된 FFR DataFrame
        When: create_ffr_dict 호출
        Then: ValueError 발생 (데이터 무결성 보장)
        """
        # Given
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01", "2023-02", "2023-02", "2023-03"],
                COL_FFR_VALUE: [0.045, 0.046, 0.0465, 0.047],
            }
        )

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 무결성 오류.*2023-02.*중복"):
            create_ffr_dict(ffr_df)


class TestLookupFfr:
    """FFR 조회 함수 테스트"""

    def test_lookup_ffr_exact_match(self):
        """
        정확한 월 매칭 테스트

        Given: FFR 딕셔너리와 딕셔너리에 존재하는 월의 날짜
        When: lookup_ffr 호출
        Then: 해당 월의 FFR 값 반환
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6, "2023-03": 4.7}
        date_value = date(2023, 2, 15)

        # When
        result = lookup_ffr(date_value, ffr_dict)

        # Then
        assert result == 4.6

    def test_lookup_ffr_fallback(self):
        """
        이전 월 폴백 테스트

        Given: FFR 딕셔너리와 딕셔너리에 없는 월의 날짜 (단, 이전 월은 존재)
        When: lookup_ffr 호출
        Then: 가장 가까운 이전 월의 FFR 값 반환
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6}
        date_value = date(2023, 3, 15)  # 2023-03은 없음

        # When
        result = lookup_ffr(date_value, ffr_dict)

        # Then
        assert result == 4.6  # 2023-02의 값

    def test_lookup_ffr_no_previous_month(self):
        """
        이전 월도 없는 경우 예외 발생 테스트

        Given: FFR 딕셔너리와 딕셔너리보다 이른 날짜
        When: lookup_ffr 호출
        Then: ValueError 발생
        """
        # Given
        ffr_dict = {"2023-02": 4.6, "2023-03": 4.7}
        date_value = date(2023, 1, 15)  # 2023-01은 없고 이전 월도 없음

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 부족.*2023-01.*이전의 FFR 데이터가 존재하지 않습니다"):
            lookup_ffr(date_value, ffr_dict)

    def test_lookup_ffr_months_diff_exceeded(self):
        """
        월 차이 초과 시 예외 발생 테스트

        Given: FFR 딕셔너리와 MAX_FFR_MONTHS_DIFF(2) 초과한 날짜
        When: lookup_ffr 호출
        Then: ValueError 발생
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6}
        date_value = date(2023, 5, 15)  # 2023-05, 가장 가까운 이전 월은 2023-02 (3개월 차이 > MAX=2)

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 부족.*2023-05.*최대 2개월 이내의 데이터만 사용 가능"):
            lookup_ffr(date_value, ffr_dict)


class TestGenericMonthlyDataDict:
    """제네릭 월별 데이터 딕셔너리 생성/조회 테스트"""

    def test_create_monthly_data_dict_basic(self):
        """
        제네릭 딕셔너리 생성 기본 테스트

        Given: 월별 데이터 DataFrame
        When: _create_monthly_data_dict 호출
        Then: {월: 값} 딕셔너리 반환
        """
        # Given (0~1 비율)
        df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0088]})

        # When: 제네릭 함수 호출
        result_dict = _create_monthly_data_dict(df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense", MAX_EXPENSE_VALUE)

        # Then
        assert result_dict == {"2023-01": 0.0095, "2023-02": 0.0088}

    def test_create_monthly_data_dict_duplicates(self):
        """
        중복 월 검증 테스트

        Given: 중복 월이 있는 DataFrame
        When: _create_monthly_data_dict 호출
        Then: ValueError 발생 (data_type 포함한 명확한 메시지)
        """
        # Given: 2023-01이 중복 (0~1 비율)
        df = pd.DataFrame(
            {COL_EXPENSE_DATE: ["2023-01", "2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0096, 0.0088]}
        )

        # When & Then
        with pytest.raises(ValueError, match="Expense.*2023-01.*중복"):
            _create_monthly_data_dict(df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense", MAX_EXPENSE_VALUE)

    @pytest.mark.parametrize(
        "bad_value",
        [math.nan, math.inf, MAX_FFR_VALUE, 3.63],
        ids=["nan", "inf", "upper_bound", "percent_unit"],
    )
    def test_create_ffr_dict_rejects_invalid_value(self, bad_value):
        """
        목적: 금리가 빈 칸 · inf · 상한 이상이면 멈춤을 검증 — 손으로 고치는 파일이라 % 로 적은 값(3.63)이나 빈 칸이
              들어올 수 있고, 그대로 쓰면 시뮬 종가가 0 이하 · NaN 이 된다

        Given: 2023-02 값만 잘못된 금리 DataFrame
        When: create_ffr_dict 호출
        Then: ValueError (data_type · 월 포함)
        """
        # Given
        df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [0.045, bad_value]})

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 오류: 월 2023-02"):
            create_ffr_dict(df)

    @pytest.mark.parametrize(
        "bad_value",
        [MAX_EXPENSE_VALUE, 0.84],
        ids=["upper_bound", "prospectus_percent"],
    )
    def test_create_expense_dict_rejects_percent_unit(self, bad_value):
        """
        목적: 운용비율이 상한 이상이면 멈춤을 검증 — 설명서는 「Net 0.84」처럼 % 로 적어, 그대로 옮기면 1 미만이라도
              비용이 백 배가 된다

        Given: 2023-02 값만 % 표기인 운용비율 DataFrame
        When: create_expense_dict 호출
        Then: ValueError (data_type · 월 포함)
        """
        # Given
        df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0088, bad_value]})

        # When & Then
        with pytest.raises(ValueError, match="Expense 데이터 오류: 월 2023-02"):
            create_expense_dict(df)

    def test_realistic_values_accepted(self):
        """
        목적: 실제로 나올 수 있는 값은 받음을 검증 — 음수 금리(하한을 두지 않는 계약, 대체 시세의 금리 누적도 그대로 쓴다) ·
              1980년대 초 수준의 금리(0.19) · 레버리지 ETF 로 높은 편인 운용비율(0.02). 상한을 너무 낮추면 여기서 실패한다

        Given: 그 값이 든 금리 · 운용비율 DataFrame
        When: create_ffr_dict · create_expense_dict 호출
        Then: 값 그대로 딕셔너리에 들어간다
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [-0.0005, 0.19]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.02]})

        # When
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = create_expense_dict(expense_df)

        # Then
        assert ffr_dict == {"2023-01": -0.0005, "2023-02": 0.19}
        assert expense_dict == {"2023-01": 0.02}

    def test_lookup_monthly_data_with_gap(self):
        """
        월 차이 검증 테스트

        Given: 월별 데이터 딕셔너리와 갭이 큰 날짜
        When: _lookup_monthly_data 호출
        Then: max_months_diff 초과 시 ValueError 발생
        """
        # Given
        data_dict = {"2023-01": 0.0095}
        date_value = date(2024, 2, 15)  # 2024-02, 2023-01부터 13개월 차이

        # When & Then: max_months_diff=12 초과
        with pytest.raises(ValueError, match="Expense.*데이터 부족.*2024-02.*최대 12개월"):
            _lookup_monthly_data(date_value, data_dict, max_months_diff=12, data_type="Expense")

    def test_lookup_monthly_data_within_gap(self):
        """
        월 차이 허용 범위 내 조회 테스트

        Given: 월별 데이터 딕셔너리와 허용 범위 내 날짜
        When: _lookup_monthly_data 호출
        Then: 가장 가까운 이전 월의 값 반환
        """
        # Given
        data_dict = {"2023-01": 0.0095, "2023-02": 0.0088}
        date_value = date(2023, 12, 15)  # 2023-12, 2023-02부터 10개월 차이 (12개월 이내)

        # When
        result = _lookup_monthly_data(date_value, data_dict, max_months_diff=12, data_type="Expense")

        # Then: 2023-02 값 사용
        assert result == pytest.approx(0.0088)


class TestBuildExtendedExpenseDict:
    """운용비율 딕셔너리 확장 테스트"""

    def test_extends_from_1999(self):
        """
        2010-02 시작 데이터를 1999-01부터 확장하는 테스트

        Given: 2010-02부터 시작하는 expense DataFrame
        When: build_extended_expense_dict 호출
        Then:
          - 1999-01 키가 존재
          - 1999-01 ~ 2010-01 구간에 DEFAULT_PRE_LISTING_EXPENSE_RATIO 적용
          - 2010-02 원본 값 보존
        """
        # Given
        expense_df = pd.DataFrame(
            {
                COL_EXPENSE_DATE: ["2010-02", "2010-03", "2010-04"],
                COL_EXPENSE_VALUE: [0.0095, 0.0093, 0.0091],
            }
        )

        # When
        result = build_extended_expense_dict(expense_df)

        # Then: 1999-01 키가 존재
        assert "1999-01" in result, "1999-01 키가 존재해야 합니다"

        # 확장 구간 값 검증 (DEFAULT_PRE_LISTING_EXPENSE_RATIO = 0.0095)
        assert result["1999-01"] == pytest.approx(DEFAULT_PRE_LISTING_EXPENSE_RATIO)
        assert result["2005-06"] == pytest.approx(DEFAULT_PRE_LISTING_EXPENSE_RATIO)
        assert result["2010-01"] == pytest.approx(DEFAULT_PRE_LISTING_EXPENSE_RATIO)

        # 원본 값 보존 검증
        assert result["2010-02"] == pytest.approx(0.0095)
        assert result["2010-03"] == pytest.approx(0.0093)
        assert result["2010-04"] == pytest.approx(0.0091)

    def test_original_values_preserved(self):
        """
        확장 시 기존 딕셔너리 값이 변경되지 않는 테스트

        Given: 3개월분 expense DataFrame
        When: build_extended_expense_dict 호출
        Then: 원본 3개월 값이 정확히 보존됨
        """
        # Given
        expense_df = pd.DataFrame(
            {
                COL_EXPENSE_DATE: ["2015-01", "2015-02", "2015-03"],
                COL_EXPENSE_VALUE: [0.0088, 0.0085, 0.0082],
            }
        )

        # When
        result = build_extended_expense_dict(expense_df)

        # Then: 원본 값 정확히 보존
        assert result["2015-01"] == pytest.approx(0.0088)
        assert result["2015-02"] == pytest.approx(0.0085)
        assert result["2015-03"] == pytest.approx(0.0082)

    def test_extension_count(self):
        """
        확장된 월 수가 정확한지 테스트

        Given: 2010-02부터 시작하는 expense DataFrame
        When: build_extended_expense_dict 호출
        Then: 1999-01 ~ 2010-01 = 133개월 확장 + 원본 3개월 = 총 136개
        """
        # Given
        expense_df = pd.DataFrame(
            {
                COL_EXPENSE_DATE: ["2010-02", "2010-03", "2010-04"],
                COL_EXPENSE_VALUE: [0.0095, 0.0093, 0.0091],
            }
        )

        # When
        result = build_extended_expense_dict(expense_df)

        # Then: 1999-01 ~ 2010-01 = 11년 * 12 + 1 = 133개월 + 원본 3개월 = 136개
        assert len(result) == 136

    def test_no_extension_if_starts_at_1999(self):
        """
        1999-01부터 시작하면 확장 없이 그대로 반환

        Given: 1999-01부터 시작하는 expense DataFrame
        When: build_extended_expense_dict 호출
        Then: 원본 딕셔너리만 반환 (추가 키 없음)
        """
        # Given
        expense_df = pd.DataFrame(
            {
                COL_EXPENSE_DATE: ["1999-01", "1999-02"],
                COL_EXPENSE_VALUE: [0.0095, 0.0093],
            }
        )

        # When
        result = build_extended_expense_dict(expense_df)

        # Then: 원본 그대로 (확장 없음)
        assert len(result) == 2
        assert result["1999-01"] == pytest.approx(0.0095)
        assert result["1999-02"] == pytest.approx(0.0093)
