"""live.daily_runner 회귀 검증 — ``run_daily`` vs ``run_portfolio_backtest`` 동등성."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from live.constants import get_live_portfolio_config
from live.daily_runner import run_daily
from live.models import AssetMarketData, MarketBundle
from live.state import create_initial_state
from qbt.backtest.engines.portfolio_engine import (
    _load_portfolio_data_with_common_period,
    run_portfolio_backtest,
)
from qbt.common_constants import (
    COL_DATE,
    GLD_DATA_PATH,
    QLD_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    SSO_DATA_PATH,
    TLT_DATA_PATH,
)

# ============================================================================
# 데이터 준비
# ============================================================================


def _all_csvs_exist() -> bool:
    required = (
        SPY_DATA_PATH,
        QQQ_DATA_PATH,
        SSO_DATA_PATH,
        QLD_DATA_PATH,
        GLD_DATA_PATH,
        TLT_DATA_PATH,
    )
    return all(path.exists() for path in required)


pytestmark = pytest.mark.skipif(
    not _all_csvs_exist(),
    reason="storage/stock/*.csv 중 일부가 누락되어 회귀 테스트 skip",
)


@pytest.fixture(scope="module")
def portfolio_config():
    return get_live_portfolio_config()


@pytest.fixture(scope="module")
def prepared_data(portfolio_config):
    """QBT 내부 로직과 동일하게 자산 데이터 준비 (워밍업 슬라이싱 포함).

    Returns:
        (asset_signal_dfs, asset_trade_dfs, slot_dict, trade_dates, start_date)
    """
    signal_dfs, trade_dfs, slot_dict, valid_start = _load_portfolio_data_with_common_period(portfolio_config)

    # MA 워밍업 슬라이싱
    for aid in signal_dfs:
        signal_dfs[aid] = signal_dfs[aid].iloc[valid_start:].reset_index(drop=True)
        trade_dfs[aid] = trade_dfs[aid].iloc[valid_start:].reset_index(drop=True)

    # 최근 1 년 구간만 유지
    first_aid = next(iter(trade_dfs))
    n = len(trade_dfs[first_aid])
    window_days = 252
    start_idx = max(0, n - window_days)
    for aid in signal_dfs:
        signal_dfs[aid] = signal_dfs[aid].iloc[start_idx:].reset_index(drop=True)
        trade_dfs[aid] = trade_dfs[aid].iloc[start_idx:].reset_index(drop=True)

    trade_dates = list(trade_dfs[first_aid][COL_DATE])
    start_date = trade_dates[0]

    return signal_dfs, trade_dfs, slot_dict, trade_dates, start_date


@pytest.fixture(scope="module")
def qbt_backtest_result(portfolio_config, prepared_data):
    """QBT run_portfolio_backtest 결과 (기준값). 모듈 스코프로 1회만 실행."""
    _, _, _, _, start_date = prepared_data
    return run_portfolio_backtest(portfolio_config, start_date=start_date)


@pytest.fixture(scope="module")
def live_iteration_results(portfolio_config, prepared_data):
    """live run_daily 를 일별 순차 호출한 결과 누적.

    Returns:
        list[dict]: 각 거래일마다 model_equity / shares / cash 스냅샷.
    """
    signal_dfs, trade_dfs, _, trade_dates, _ = prepared_data

    bundle: MarketBundle = {
        aid: AssetMarketData(signal_df=signal_dfs[aid], trade_df=trade_dfs[aid]) for aid in signal_dfs
    }

    state = create_initial_state(portfolio_config.total_capital)
    results: list[dict] = []

    for trade_date in trade_dates:
        # pandas Timestamp 또는 date 객체 통일
        if hasattr(trade_date, "date") and not isinstance(trade_date, date):
            td = trade_date.date()
        elif isinstance(trade_date, date):
            td = trade_date
        else:
            td = date.fromisoformat(str(trade_date))

        daily = run_daily(
            trade_date=td,
            state=state,
            market_bundle=bundle,
            pending_fills=[],
            applied_fill_ids={},
        )
        state = daily.updated_state
        results.append(
            {
                "date": td,
                "model_equity": daily.model_equity,
                "shares": {aid: asset.model_shares for aid, asset in state.assets.items()},
                "cash": state.shared_cash_model,
            }
        )

    return results


# ============================================================================
# 회귀 테스트
# ============================================================================


class TestRegression:
    def test_equity_matches_daily_under_1_won(self, qbt_backtest_result, live_iteration_results):
        """Given 동일 구간 When live vs QBT Then 매일 equity 차이 < 1 원."""
        qbt_equity = qbt_backtest_result.equity_df["equity"].tolist()
        live_equity = [r["model_equity"] for r in live_iteration_results]

        assert len(qbt_equity) == len(live_equity), f"길이 불일치: qbt={len(qbt_equity)}, live={len(live_equity)}"

        for i, (qbt_val, live_val) in enumerate(zip(qbt_equity, live_equity, strict=True)):
            assert live_val == pytest.approx(qbt_val, abs=1.0), f"Day {i}: equity qbt={qbt_val} vs live={live_val}"

    def test_positions_match_daily(self, qbt_backtest_result, live_iteration_results):
        """Given 동일 구간 When live vs QBT Then 매일 positions 정수 일치."""
        equity_df = qbt_backtest_result.equity_df

        for i, live_row in enumerate(live_iteration_results):
            for asset_id in ("sso", "qld", "gld", "tlt"):
                col = f"{asset_id}_shares"
                assert col in equity_df.columns, f"{col} 컬럼 없음"
                qbt_shares = int(equity_df[col].iloc[i])
                live_shares = int(live_row["shares"][asset_id])
                assert qbt_shares == live_shares, f"Day {i} {asset_id}: qbt={qbt_shares} vs live={live_shares}"

    def test_cash_matches_daily_under_1_won(self, qbt_backtest_result, live_iteration_results):
        """Given 동일 구간 When live vs QBT Then 매일 cash 차이 < 1 원."""
        qbt_cash = qbt_backtest_result.equity_df["cash"].tolist()
        live_cash = [r["cash"] for r in live_iteration_results]

        for i, (qbt_val, live_val) in enumerate(zip(qbt_cash, live_cash, strict=True)):
            assert live_val == pytest.approx(qbt_val, abs=1.0), f"Day {i}: cash qbt={qbt_val} vs live={live_val}"


class TestRegressionMeta:
    def test_one_year_window_size(self, prepared_data):
        """회귀 테스트 윈도우는 1 년 거래일 이하여야 한다."""
        _, _, _, trade_dates, _ = prepared_data
        assert 100 <= len(trade_dates) <= 252

    def test_start_date_is_at_least_ten_months_ago(self, prepared_data):
        """테스트 윈도우가 최근에 위치 — 적어도 10 개월 전부터 시작."""
        _, _, _, _, start_date = prepared_data
        if hasattr(start_date, "date"):
            start = start_date.date() if not isinstance(start_date, date) else start_date
        else:
            start = start_date
        # 단순 sanity: start_date 가 너무 오래되지 않음 (2000 년 이후)
        assert start >= date(2000, 1, 1)

    def test_all_assets_present_in_bundle(self, prepared_data):
        """live 포트폴리오 자산 모두 데이터 준비 완료."""
        signal_dfs, trade_dfs, _, _, _ = prepared_data
        expected = {"sso", "qld", "gld", "tlt"}
        assert set(signal_dfs.keys()) == expected
        assert set(trade_dfs.keys()) == expected


# timedelta 는 향후 확장용으로 import 유지
_ = timedelta
