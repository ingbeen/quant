"""WFO Stitched 대시보드 관련 테스트

load_wfo_results_from_csv() 함수의 계약을 검증한다:
- CSV -> WfoWindowResultDict 리스트 변환
- 필수 컬럼 검증
- 정수 타입 보정
- build_params_schedule() 연결 검증
"""

from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.walkforward import build_params_schedule, load_wfo_results_from_csv


class TestLoadWfoResultsFromCsv:
    """load_wfo_results_from_csv() 테스트."""

    def _create_base_wfo_csv(self, tmp_path: Path, filename: str = "walkforward_dynamic.csv") -> Path:
        """테스트용 WFO 결과 CSV를 생성하는 헬퍼.

        Args:
            tmp_path: 임시 디렉토리
            filename: CSV 파일명

        Returns:
            생성된 CSV 파일 경로
        """
        df = pd.DataFrame(
            {
                "window_idx": [0, 1, 2],
                "is_start": ["1999-03-10", "1999-03-10", "1999-03-10"],
                "is_end": ["2005-02-28", "2007-02-28", "2009-02-28"],
                "oos_start": ["2005-03-01", "2007-03-01", "2009-03-01"],
                "oos_end": ["2007-02-28", "2009-02-28", "2011-02-28"],
                "best_ma_window": [150, 200, 200],
                "best_buy_buffer_zone_pct": [0.03, 0.05, 0.03],
                "best_sell_buffer_zone_pct": [0.03, 0.01, 0.03],
                "best_hold_days": [3, 5, 2],
                "best_recent_months": [0, 4, 8],
                "is_cagr": [15.2, 12.8, 10.5],
                "is_mdd": [-25.3, -30.1, -28.7],
                "is_calmar": [0.6008, 0.4252, 0.3659],
                "is_trades": [10, 8, 12],
                "is_win_rate": [60.0, 62.5, 58.3],
                "oos_cagr": [8.1, 5.2, 7.3],
                "oos_mdd": [-18.5, -22.3, -20.1],
                "oos_calmar": [0.4378, 0.2332, 0.3632],
                "oos_trades": [5, 4, 6],
                "oos_win_rate": [60.0, 50.0, 66.7],
                "wfe_calmar": [0.7288, 0.5484, 0.9926],
                "wfe_cagr": [0.5329, 0.4063, 0.6952],
            }
        )
        csv_path = tmp_path / filename
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_load_wfo_results_from_csv_basic(self, tmp_path: Path) -> None:
        """
        목적: 정상 CSV를 로딩하여 올바른 dict 리스트를 반환하는지 검증한다.

        Given: 필수 컬럼이 모두 포함된 WFO 결과 CSV
        When: load_wfo_results_from_csv() 호출
        Then: 3개의 딕셔너리 리스트 반환, 타입 검증 통과
        """
        # Given
        csv_path = self._create_base_wfo_csv(tmp_path)

        # When
        results = load_wfo_results_from_csv(csv_path)

        # Then
        assert len(results) == 3

        # 정수 타입 보정 확인
        for r in results:
            assert isinstance(r["best_ma_window"], int)
            assert isinstance(r["best_hold_days"], int)
            assert isinstance(r["best_recent_months"], int)

        # 첫 번째 윈도우 값 검증
        first = results[0]
        assert first["best_ma_window"] == 150
        assert first["best_buy_buffer_zone_pct"] == pytest.approx(0.03, abs=1e-6)
        assert first["best_sell_buffer_zone_pct"] == pytest.approx(0.03, abs=1e-6)
        assert first["best_hold_days"] == 3
        assert first["best_recent_months"] == 0
        assert first["oos_start"] == "2005-03-01"

    def test_load_wfo_results_from_csv_with_extra_columns(self, tmp_path: Path) -> None:
        """
        목적: 추가 컬럼이 포함된 CSV에서 필수 컬럼만 올바르게 로딩되는지 검증한다.

        Given: 필수 컬럼 + 추가 컬럼이 포함된 WFO 결과 CSV
        When: load_wfo_results_from_csv() 호출
        Then: 각 딕셔너리에 추가 컬럼이 올바른 타입으로 포함됨
        """
        # Given
        df = pd.DataFrame(
            {
                "window_idx": [0, 1],
                "is_start": ["1999-03-10", "1999-03-10"],
                "is_end": ["2005-02-28", "2007-02-28"],
                "oos_start": ["2005-03-01", "2007-03-01"],
                "oos_end": ["2007-02-28", "2009-02-28"],
                "best_ma_window": [200, 200],
                "best_buy_buffer_zone_pct": [0.03, 0.05],
                "best_sell_buffer_zone_pct": [0.03, 0.01],
                "best_hold_days": [3, 5],
                "best_recent_months": [0, 4],
                "extra_metric": [1.5, 2.5],
                "is_cagr": [15.0, 12.0],
                "is_mdd": [-25.0, -30.0],
                "is_calmar": [0.6, 0.4],
                "is_trades": [10, 8],
                "is_win_rate": [60.0, 62.5],
                "oos_cagr": [8.0, 5.0],
                "oos_mdd": [-18.0, -22.0],
                "oos_calmar": [0.44, 0.23],
                "oos_trades": [5, 4],
                "oos_win_rate": [60.0, 50.0],
                "wfe_calmar": [0.73, 0.58],
                "wfe_cagr": [0.53, 0.42],
            }
        )
        csv_path = tmp_path / "walkforward_dynamic.csv"
        df.to_csv(csv_path, index=False)

        # When
        results = load_wfo_results_from_csv(csv_path)

        # Then
        assert len(results) == 2

        # 추가 컬럼이 딕셔너리에 포함됨
        assert results[0].get("extra_metric") == pytest.approx(1.5, abs=1e-6)
        assert results[1].get("extra_metric") == pytest.approx(2.5, abs=1e-6)

        # 필수 필드 정수 타입 보정 확인
        assert isinstance(results[0]["best_ma_window"], int)
        assert isinstance(results[0]["best_hold_days"], int)

    def test_load_wfo_results_from_csv_file_not_found(self, tmp_path: Path) -> None:
        """
        목적: 존재하지 않는 파일 경로에서 FileNotFoundError가 발생하는지 검증한다.

        Given: 존재하지 않는 CSV 경로
        When: load_wfo_results_from_csv() 호출
        Then: FileNotFoundError 발생
        """
        # Given
        fake_path = tmp_path / "nonexistent.csv"

        # When / Then
        with pytest.raises(FileNotFoundError, match="찾을 수 없습니다"):
            load_wfo_results_from_csv(fake_path)

    def test_load_wfo_results_from_csv_missing_columns(self, tmp_path: Path) -> None:
        """
        목적: 필수 컬럼이 누락된 CSV에서 ValueError가 발생하는지 검증한다.

        Given: best_ma_window 컬럼이 누락된 CSV
        When: load_wfo_results_from_csv() 호출
        Then: ValueError 발생 (누락 컬럼명 포함)
        """
        # Given: best_ma_window 누락
        df = pd.DataFrame(
            {
                "oos_start": ["2005-03-01"],
                "best_buy_buffer_zone_pct": [0.03],
                "best_sell_buffer_zone_pct": [0.03],
                "best_hold_days": [3],
                "best_recent_months": [0],
            }
        )
        csv_path = tmp_path / "incomplete.csv"
        df.to_csv(csv_path, index=False)

        # When / Then
        with pytest.raises(ValueError, match="best_ma_window"):
            load_wfo_results_from_csv(csv_path)

    def test_load_wfo_results_builds_valid_params_schedule(self, tmp_path: Path) -> None:
        """
        목적: CSV → load → build_params_schedule 파이프라인이 유효한 결과를 반환하는지 검증한다.

        Given: 3개 윈도우의 WFO 결과 CSV
        When: load_wfo_results_from_csv() → build_params_schedule() 연결 호출
        Then: initial_params와 schedule이 올바르게 생성됨
        """
        # Given
        csv_path = self._create_base_wfo_csv(tmp_path)

        # When
        results = load_wfo_results_from_csv(csv_path)
        initial_params, schedule = build_params_schedule(results)

        # Then
        # initial_params: 첫 윈도우 기반 (ma=150, buy=0.03, sell=0.03, hold=3, recent=0)
        assert initial_params.ma_window == 150
        assert initial_params.buy_buffer_zone_pct == pytest.approx(0.03, abs=1e-6)
        assert initial_params.sell_buffer_zone_pct == pytest.approx(0.03, abs=1e-6)
        assert initial_params.hold_days == 3
        assert initial_params.recent_months == 0

        # schedule: 2번째, 3번째 윈도우의 OOS 시작일 → params
        from datetime import date

        assert len(schedule) == 2
        assert date(2007, 3, 1) in schedule
        assert date(2009, 3, 1) in schedule

        # 두 번째 윈도우 파라미터 확인
        second_params = schedule[date(2007, 3, 1)]
        assert second_params.ma_window == 200
        assert second_params.buy_buffer_zone_pct == pytest.approx(0.05, abs=1e-6)
        assert second_params.hold_days == 5
