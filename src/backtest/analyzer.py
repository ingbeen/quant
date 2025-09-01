"""
Performance Analyzer - 백테스트 성과 분석

수익률, 리스크 지표, 벤치마크 비교 등의 성과 분석 기능
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import warnings

warnings.filterwarnings("ignore")

from .engine import BacktestResult


class PerformanceAnalyzer:
    """백테스트 성과 분석기"""

    def __init__(self, result: BacktestResult):
        """
        Args:
            result: 백테스트 결과
        """
        self.result = result
        self.portfolio_df = pd.DataFrame(result.portfolio_history)

        if not self.portfolio_df.empty:
            self.portfolio_df["date"] = pd.to_datetime(self.portfolio_df["date"])
            self.portfolio_df.set_index("date", inplace=True)

            # 일별 수익률 계산
            self.portfolio_df["daily_return"] = self.portfolio_df[
                "portfolio_value"
            ].pct_change()
            self.portfolio_df["cumulative_return"] = (
                self.portfolio_df["portfolio_value"] / float(result.config.initial_cash)
                - 1
            )

    def calculate_basic_metrics(self) -> Dict:
        """기본 성과 지표 계산"""
        if self.portfolio_df.empty:
            return {}

        initial_value = float(self.result.config.initial_cash)
        final_value = self.portfolio_df["portfolio_value"].iloc[-1]

        total_return = (final_value - initial_value) / initial_value

        # 거래일 수 계산
        trading_days = len(self.portfolio_df)
        years = trading_days / 252  # 연간 거래일 약 252일

        # 연간 수익률
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 일별 수익률 통계
        daily_returns = self.portfolio_df["daily_return"].dropna()

        return {
            "initial_value": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "annual_return": annual_return,
            "annual_return_pct": annual_return * 100,
            "trading_days": trading_days,
            "years": years,
            "avg_daily_return": daily_returns.mean(),
            "volatility_daily": daily_returns.std(),
            "volatility_annual": daily_returns.std() * np.sqrt(252),
            "max_value": self.portfolio_df["portfolio_value"].max(),
            "min_value": self.portfolio_df["portfolio_value"].min(),
        }

    def calculate_risk_metrics(self) -> Dict:
        """리스크 지표 계산"""
        if self.portfolio_df.empty:
            return {}

        daily_returns = self.portfolio_df["daily_return"].dropna()

        if len(daily_returns) == 0:
            return {}

        # Sharpe Ratio (무위험 수익률 0% 가정)
        sharpe_ratio = (
            daily_returns.mean() / daily_returns.std() * np.sqrt(252)
            if daily_returns.std() > 0
            else 0
        )

        # Sortino Ratio (하방 변동성만 고려)
        downside_returns = daily_returns[daily_returns < 0]
        sortino_ratio = (
            daily_returns.mean() / downside_returns.std() * np.sqrt(252)
            if len(downside_returns) > 0 and downside_returns.std() > 0
            else 0
        )

        # Maximum Drawdown
        cumulative_returns = (1 + daily_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()

        # VaR (Value at Risk) 95%, 99%
        var_95 = daily_returns.quantile(0.05)
        var_99 = daily_returns.quantile(0.01)

        # Calmar Ratio
        annual_return = self.calculate_basic_metrics().get("annual_return", 0)
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        return {
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100,
            "var_95": var_95,
            "var_99": var_99,
            "calmar_ratio": calmar_ratio,
            "positive_days": (daily_returns > 0).sum(),
            "negative_days": (daily_returns < 0).sum(),
            "win_rate": (daily_returns > 0).mean() * 100,
        }

    def calculate_trade_metrics(self) -> Dict:
        """거래 관련 지표 계산"""
        if not self.result.executed_signals:
            return {}

        buy_signals = [s for s in self.result.executed_signals if s.action == "BUY"]
        sell_signals = [s for s in self.result.executed_signals if s.action == "SELL"]

        # 거래 쌍 분석 (매수-매도)
        trades = []
        positions: Dict[str, List[Dict]] = {}

        for signal in self.result.executed_signals:
            if signal.action == "BUY":
                if signal.symbol not in positions:
                    positions[signal.symbol] = []
                positions[signal.symbol].append(
                    {
                        "buy_date": signal.date,
                        "buy_price": float(signal.price),
                        "quantity": signal.quantity or 0,
                    }
                )

            elif signal.action == "SELL" and signal.symbol in positions:
                if positions[signal.symbol]:
                    buy_info = positions[signal.symbol].pop(0)

                    quantity = min(signal.quantity or 0, buy_info["quantity"])
                    if quantity > 0:
                        pnl_per_share = float(signal.price) - buy_info["buy_price"]
                        total_pnl = pnl_per_share * quantity

                        trades.append(
                            {
                                "symbol": signal.symbol,
                                "buy_date": buy_info["buy_date"],
                                "sell_date": signal.date,
                                "buy_price": buy_info["buy_price"],
                                "sell_price": float(signal.price),
                                "quantity": quantity,
                                "pnl": total_pnl,
                                "return_pct": (
                                    float(signal.price) / buy_info["buy_price"] - 1
                                )
                                * 100,
                                "holding_days": (
                                    signal.date - buy_info["buy_date"]
                                ).days,
                            }
                        )

        if not trades:
            return {
                "total_trades": len(buy_signals) + len(sell_signals),
                "buy_signals": len(buy_signals),
                "sell_signals": len(sell_signals),
                "completed_trades": 0,
            }

        trades_df = pd.DataFrame(trades)

        winning_trades = trades_df[trades_df["pnl"] > 0]
        losing_trades = trades_df[trades_df["pnl"] < 0]

        return {
            "total_signals": len(self.result.executed_signals),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "completed_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate_trades": len(winning_trades) / len(trades) * 100 if trades else 0,
            "avg_profit": (
                winning_trades["pnl"].mean() if len(winning_trades) > 0 else 0
            ),
            "avg_loss": losing_trades["pnl"].mean() if len(losing_trades) > 0 else 0,
            "profit_factor": (
                abs(winning_trades["pnl"].sum() / losing_trades["pnl"].sum())
                if len(losing_trades) > 0 and losing_trades["pnl"].sum() != 0
                else float("inf")
            ),
            "avg_holding_days": trades_df["holding_days"].mean() if trades else 0,
            "best_trade": trades_df["pnl"].max() if trades else 0,
            "worst_trade": trades_df["pnl"].min() if trades else 0,
        }

    def generate_summary_report(self) -> Dict:
        """종합 성과 리포트 생성"""
        basic_metrics = self.calculate_basic_metrics()
        risk_metrics = self.calculate_risk_metrics()
        trade_metrics = self.calculate_trade_metrics()

        return {
            "basic_metrics": basic_metrics,
            "risk_metrics": risk_metrics,
            "trade_metrics": trade_metrics,
            "backtest_period": {
                "start_date": self.result.start_date,
                "end_date": self.result.end_date,
                "total_days": self.result.total_days,
            },
        }

    def print_summary(self) -> None:
        """성과 요약 출력"""
        report = self.generate_summary_report()

        print("\n" + "=" * 60)
        print(f"📊 백테스트 성과 분석 리포트")
        print("=" * 60)

        # 기본 지표
        basic = report["basic_metrics"]
        if basic:
            print(f"\n💰 기본 성과:")
            print(f"   초기 자금: ${basic['initial_value']:,.2f}")
            print(f"   최종 자금: ${basic['final_value']:,.2f}")
            print(f"   총 수익률: {basic['total_return_pct']:+.2f}%")
            print(f"   연간 수익률: {basic['annual_return_pct']:+.2f}%")
            print(f"   거래 기간: {basic['years']:.1f}년 ({basic['trading_days']}일)")

        # 리스크 지표
        risk = report["risk_metrics"]
        if risk:
            print(f"\n[WARNING] 리스크 지표:")
            print(f"   샤프 비율: {risk['sharpe_ratio']:.3f}")
            print(f"   소티노 비율: {risk['sortino_ratio']:.3f}")
            print(f"   최대 낙폭: {risk['max_drawdown_pct']:+.2f}%")
            print(f"   연간 변동성: {risk['volatility_annual']*100:.2f}%")
            print(f"   승률: {risk['win_rate']:.1f}%")

        # 거래 지표
        trade = report["trade_metrics"]
        if trade and trade.get("completed_trades", 0) > 0:
            print(f"\n📈 거래 분석:")
            print(f"   총 신호 수: {trade['total_signals']}개")
            print(f"   완료된 거래: {trade['completed_trades']}개")
            print(f"   거래 승률: {trade['win_rate_trades']:.1f}%")
            print(f"   평균 보유 기간: {trade['avg_holding_days']:.1f}일")
            print(f"   최고 수익: ${trade['best_trade']:+,.2f}")
            print(f"   최대 손실: ${trade['worst_trade']:+,.2f}")

        print("\n" + "=" * 60)

    def plot_performance(self, figsize: Tuple[int, int] = (15, 10)) -> None:
        """성과 차트 그리기"""
        if self.portfolio_df.empty:
            print("차트를 그릴 데이터가 없습니다.")
            return

        plt.style.use("seaborn-v0_8")
        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # 1. 포트폴리오 가치 변화
        axes[0, 0].plot(
            self.portfolio_df.index,
            self.portfolio_df["portfolio_value"],
            linewidth=2,
            color="blue",
            label="Portfolio Value",
        )
        axes[0, 0].axhline(
            y=float(self.result.config.initial_cash),
            color="red",
            linestyle="--",
            alpha=0.7,
            label="Initial Value",
        )
        axes[0, 0].set_title("포트폴리오 가치 변화", fontsize=12, fontweight="bold")
        axes[0, 0].set_ylabel("Portfolio Value ($)")
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 누적 수익률
        axes[0, 1].plot(
            self.portfolio_df.index,
            self.portfolio_df["cumulative_return"] * 100,
            linewidth=2,
            color="green",
        )
        axes[0, 1].axhline(y=0, color="red", linestyle="--", alpha=0.7)
        axes[0, 1].set_title("누적 수익률", fontsize=12, fontweight="bold")
        axes[0, 1].set_ylabel("Cumulative Return (%)")
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 일별 수익률 분포
        daily_returns = self.portfolio_df["daily_return"].dropna() * 100
        axes[1, 0].hist(daily_returns, bins=50, alpha=0.7, color="purple")
        axes[1, 0].axvline(
            daily_returns.mean(),
            color="red",
            linestyle="--",
            label=f"Mean: {daily_returns.mean():.3f}%",
        )
        axes[1, 0].set_title("일별 수익률 분포", fontsize=12, fontweight="bold")
        axes[1, 0].set_xlabel("Daily Return (%)")
        axes[1, 0].set_ylabel("Frequency")
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        # 4. 드로우다운
        cumulative_returns = (1 + self.portfolio_df["daily_return"]).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max * 100

        axes[1, 1].fill_between(
            self.portfolio_df.index, drawdown, 0, color="red", alpha=0.3
        )
        axes[1, 1].plot(self.portfolio_df.index, drawdown, color="red", linewidth=1)
        axes[1, 1].set_title("드로우다운", fontsize=12, fontweight="bold")
        axes[1, 1].set_ylabel("Drawdown (%)")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def plot_signals(
        self, symbol: str, data: pd.DataFrame, figsize: Tuple[int, int] = (15, 8)
    ) -> None:
        """매매 신호와 가격 차트"""
        if data.empty:
            print("차트를 그릴 데이터가 없습니다.")
            return

        plt.figure(figsize=figsize)

        # 가격 차트
        data_copy = data.copy()
        data_copy["date"] = pd.to_datetime(data_copy["date"])
        data_copy.set_index("date", inplace=True)

        plt.plot(
            data_copy.index,
            data_copy["close"],
            linewidth=1,
            color="blue",
            label="Price",
        )

        # 매수/매도 신호 표시
        buy_signals = [
            s
            for s in self.result.executed_signals
            if s.action == "BUY" and s.symbol == symbol
        ]
        sell_signals = [
            s
            for s in self.result.executed_signals
            if s.action == "SELL" and s.symbol == symbol
        ]

        if buy_signals:
            buy_dates = pd.to_datetime([s.date for s in buy_signals])
            buy_prices = [float(s.price) for s in buy_signals]
            plt.scatter(
                buy_dates,
                buy_prices,
                color="green",
                marker="^",
                s=100,
                label=f"Buy ({len(buy_signals)})",
                zorder=5,
            )

        if sell_signals:
            sell_dates = pd.to_datetime([s.date for s in sell_signals])
            sell_prices = [float(s.price) for s in sell_signals]
            plt.scatter(
                sell_dates,
                sell_prices,
                color="red",
                marker="v",
                s=100,
                label=f"Sell ({len(sell_signals)})",
                zorder=5,
            )

        plt.title(f"{symbol} - 매매 신호", fontsize=14, fontweight="bold")
        plt.xlabel("Date")
        plt.ylabel("Price ($)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
