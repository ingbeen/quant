"""성과 지표 계산 모듈"""

import pandas as pd


def calculate_summary(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    initial_capital: float,
) -> dict:
    """
    거래 내역과 자본 곡선으로 요약 지표를 계산한다.

    Args:
        trades_df: 거래 내역 DataFrame
        equity_df: 자본 곡선 DataFrame
        initial_capital: 초기 자본금

    Returns:
        요약 지표 딕셔너리
    """
    if equity_df.empty:
        return {
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "cagr": 0.0,
            "mdd": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
        }

    final_capital = equity_df.iloc[-1]["equity"]
    total_return = final_capital - initial_capital
    total_return_pct = (total_return / initial_capital) * 100

    # 기간 계산
    start_date = pd.to_datetime(equity_df.iloc[0]["Date"])
    end_date = pd.to_datetime(equity_df.iloc[-1]["Date"])
    years = (end_date - start_date).days / 365.25

    # CAGR
    if years > 0 and final_capital > 0:
        cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # MDD 계산
    equity_df = equity_df.copy()
    equity_df["peak"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
    mdd = equity_df["drawdown"].min() * 100

    # 거래 통계
    total_trades = len(trades_df)
    if total_trades > 0:
        winning_trades = len(trades_df[trades_df["pnl"] > 0])
        losing_trades = len(trades_df[trades_df["pnl"] <= 0])
        win_rate = (winning_trades / total_trades) * 100
    else:
        winning_trades = 0
        losing_trades = 0
        win_rate = 0.0

    return {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "mdd": mdd,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "start_date": str(equity_df.iloc[0]["Date"]),
        "end_date": str(equity_df.iloc[-1]["Date"]),
    }
