"""백테스트 결과 저장 및 리포트 생성 모듈"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from qbt.utils import get_logger

logger = get_logger(__name__)


def create_result_directory(base_path: Path = Path("results")) -> Path:
    """
    결과 저장용 디렉토리를 생성한다.

    run_id = YYYYMMDD_HHMMSS 형식으로 고유 디렉토리를 생성한다.

    Args:
        base_path: 기본 결과 저장 경로

    Returns:
        생성된 디렉토리 경로
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = base_path / run_id
    result_dir.mkdir(parents=True, exist_ok=True)

    logger.debug(f"결과 디렉토리 생성: {result_dir}")
    return result_dir


def save_trades(trades_df: pd.DataFrame, path: Path, suffix: str = "") -> Path:
    """
    거래 내역을 CSV로 저장한다.

    Args:
        trades_df: 거래 내역 DataFrame
        path: 저장 디렉토리 경로
        suffix: 파일명 접미사 (예: "_sma", "_ema")

    Returns:
        저장된 파일 경로
    """
    filename = f"trades{suffix}.csv"
    file_path = path / filename
    trades_df.to_csv(file_path, index=False)
    logger.debug(f"거래 내역 저장: {file_path}")
    return file_path


def save_equity(equity_df: pd.DataFrame, path: Path, suffix: str = "") -> Path:
    """
    자본 곡선을 CSV로 저장한다.

    Args:
        equity_df: 자본 곡선 DataFrame
        path: 저장 디렉토리 경로
        suffix: 파일명 접미사 (예: "_sma", "_ema", "_bh")

    Returns:
        저장된 파일 경로
    """
    filename = f"equity{suffix}.csv"
    file_path = path / filename
    equity_df.to_csv(file_path, index=False)
    logger.debug(f"자본 곡선 저장: {file_path}")
    return file_path


def save_summary(summary: dict, path: Path, suffix: str = "") -> Path:
    """
    요약 지표를 JSON으로 저장한다.

    Args:
        summary: 요약 지표 딕셔너리
        path: 저장 디렉토리 경로
        suffix: 파일명 접미사 (예: "_sma", "_ema")

    Returns:
        저장된 파일 경로
    """
    filename = f"summary{suffix}.json"
    file_path = path / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    logger.debug(f"요약 지표 저장: {file_path}")
    return file_path


def save_grid_results(results_df: pd.DataFrame, path: Path) -> Path:
    """
    그리드 서치 결과를 CSV로 저장한다.

    Args:
        results_df: 그리드 서치 결과 DataFrame
        path: 저장 디렉토리 경로

    Returns:
        저장된 파일 경로
    """
    file_path = path / "grid_results.csv"
    results_df.to_csv(file_path, index=False)
    logger.debug(f"그리드 서치 결과 저장: {file_path}")
    return file_path


def save_walkforward_results(results_df: pd.DataFrame, path: Path) -> Path:
    """
    워킹 포워드 결과를 CSV로 저장한다.

    Args:
        results_df: 워킹 포워드 결과 DataFrame
        path: 저장 디렉토리 경로

    Returns:
        저장된 파일 경로
    """
    file_path = path / "walkforward_results.csv"
    results_df.to_csv(file_path, index=False)
    logger.debug(f"워킹 포워드 결과 저장: {file_path}")
    return file_path


def plot_equity_curve(
    equity_dfs: dict[str, pd.DataFrame],
    path: Path,
    title: str = "Equity Curve",
) -> Path | None:
    """
    자본 곡선 그래프를 생성하고 저장한다.

    Args:
        equity_dfs: {전략명: equity_df} 딕셔너리
        path: 저장 디렉토리 경로
        title: 그래프 제목

    Returns:
        저장된 파일 경로 (matplotlib 미설치 시 None)
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib이 설치되지 않아 그래프를 생성할 수 없습니다")
        return None

    plt.figure(figsize=(12, 6))

    colors = {"SMA": "blue", "EMA": "green", "Buy&Hold": "gray", "Walkforward": "red"}

    for name, df in equity_dfs.items():
        if df.empty:
            continue
        color = colors.get(name, "black")
        plt.plot(pd.to_datetime(df["Date"]), df["equity"], label=name, color=color)

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity (KRW)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    file_path = path / "equity_curve.png"
    plt.savefig(file_path, dpi=150)
    plt.close()

    logger.debug(f"자본 곡선 그래프 저장: {file_path}")
    return file_path


def plot_drawdown(
    equity_dfs: dict[str, pd.DataFrame],
    path: Path,
    title: str = "Drawdown",
) -> Path | None:
    """
    드로우다운 그래프를 생성하고 저장한다.

    Args:
        equity_dfs: {전략명: equity_df} 딕셔너리
        path: 저장 디렉토리 경로
        title: 그래프 제목

    Returns:
        저장된 파일 경로 (matplotlib 미설치 시 None)
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib이 설치되지 않아 그래프를 생성할 수 없습니다")
        return None

    plt.figure(figsize=(12, 4))

    colors = {"SMA": "blue", "EMA": "green", "Buy&Hold": "gray", "Walkforward": "red"}

    for name, df in equity_dfs.items():
        if df.empty:
            continue

        df = df.copy()
        df["peak"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"] * 100

        color = colors.get(name, "black")
        plt.fill_between(
            pd.to_datetime(df["Date"]),
            df["drawdown"],
            0,
            alpha=0.3,
            label=name,
            color=color,
        )

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    file_path = path / "drawdown.png"
    plt.savefig(file_path, dpi=150)
    plt.close()

    logger.debug(f"드로우다운 그래프 저장: {file_path}")
    return file_path


def plot_grid_heatmap(
    grid_results: pd.DataFrame,
    path: Path,
    metric: str = "total_return_pct",
    ma_type: str = "sma",
) -> Path | None:
    """
    그리드 서치 결과 히트맵을 생성하고 저장한다.

    Args:
        grid_results: 그리드 서치 결과 DataFrame
        path: 저장 디렉토리 경로
        metric: 표시할 지표 (total_return_pct, cagr, mdd 등)
        ma_type: 이동평균 유형 (sma, ema)

    Returns:
        저장된 파일 경로 (matplotlib 미설치 시 None)
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib이 설치되지 않아 그래프를 생성할 수 없습니다")
        return None

    # 해당 ma_type만 필터링
    df = grid_results[grid_results["ma_type"] == ma_type].copy()

    if df.empty:
        logger.warning(f"{ma_type} 데이터가 없어 히트맵을 생성할 수 없습니다")
        return None

    # 피벗 테이블 생성 (short_window x long_window, 평균값)
    pivot = df.pivot_table(
        values=metric,
        index="short_window",
        columns="long_window",
        aggfunc="mean",
    )

    plt.figure(figsize=(10, 6))
    plt.imshow(pivot.values, cmap="RdYlGn", aspect="auto")
    plt.colorbar(label=metric)

    plt.xticks(range(len(pivot.columns)), pivot.columns.tolist())
    plt.yticks(range(len(pivot.index)), pivot.index.tolist())
    plt.xlabel("Long Window")
    plt.ylabel("Short Window")
    plt.title(f"Grid Search Heatmap ({ma_type.upper()}) - {metric}")

    # 값 표시
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = pivot.iloc[i, j]
            plt.text(j, i, f"{value:.1f}", ha="center", va="center", fontsize=8)

    plt.tight_layout()

    file_path = path / f"grid_heatmap_{ma_type}.png"
    plt.savefig(file_path, dpi=150)
    plt.close()

    logger.debug(f"그리드 히트맵 저장: {file_path}")
    return file_path


def generate_html_report(
    summaries: dict[str, dict],
    equity_dfs: dict[str, pd.DataFrame],
    result_dir: Path,
    params: dict | None = None,
    grid_results: pd.DataFrame | None = None,
    walkforward_results: pd.DataFrame | None = None,
) -> Path:
    """
    HTML 리포트를 생성한다.

    Args:
        summaries: {전략명: summary_dict} 딕셔너리
        equity_dfs: {전략명: equity_df} 딕셔너리
        result_dir: 결과 디렉토리 경로
        params: 전략 파라미터 딕셔너리 (선택)
        grid_results: 그리드 서치 결과 DataFrame (선택)
        walkforward_results: 워킹 포워드 결과 DataFrame (선택)

    Returns:
        생성된 HTML 파일 경로
    """
    run_id = result_dir.name

    # 성과 비교 테이블 생성
    performance_rows = ""
    for name, summary in summaries.items():
        performance_rows += f"""
        <tr>
            <td>{name}</td>
            <td>{summary.get('initial_capital', 0):,.0f}</td>
            <td>{summary.get('final_capital', 0):,.0f}</td>
            <td>{summary.get('total_return_pct', 0):.2f}%</td>
            <td>{summary.get('cagr', 0):.2f}%</td>
            <td>{summary.get('mdd', 0):.2f}%</td>
            <td>{summary.get('total_trades', 0)}</td>
            <td>{summary.get('win_rate', 0):.1f}%</td>
        </tr>
        """

    # 파라미터 정보
    params_html = ""
    if params:
        params_html = f"""
        <h2>Strategy Parameters</h2>
        <table>
            <tr><th>Parameter</th><th>Value</th></tr>
            <tr><td>Short Window</td><td>{params.get('short_window', 'N/A')}</td></tr>
            <tr><td>Long Window</td><td>{params.get('long_window', 'N/A')}</td></tr>
            <tr><td>Stop Loss %</td><td>{params.get('stop_loss_pct', 0) * 100:.1f}%</td></tr>
            <tr><td>Lookback for Low</td><td>{params.get('lookback_for_low', 'N/A')}</td></tr>
        </table>
        """  # noqa: E501

    # 그리드 서치 결과
    grid_html = ""
    if grid_results is not None and not grid_results.empty:
        top_10 = grid_results.head(10)
        grid_rows = ""
        for _, row in top_10.iterrows():
            grid_rows += f"""
            <tr>
                <td>{row['ma_type'].upper()}</td>
                <td>{row['short_window']}</td>
                <td>{row['long_window']}</td>
                <td>{row['stop_loss_pct'] * 100:.0f}%</td>
                <td>{row['lookback_for_low']}</td>
                <td>{row['total_return_pct']:.2f}%</td>
                <td>{row['cagr']:.2f}%</td>
                <td>{row['mdd']:.2f}%</td>
            </tr>
            """
        grid_html = f"""
        <h2>Grid Search Top 10</h2>
        <table>
            <tr>
                <th>MA Type</th><th>Short</th><th>Long</th>
                <th>Stop Loss</th><th>Lookback</th>
                <th>Return</th><th>CAGR</th><th>MDD</th>
            </tr>
            {grid_rows}
        </table>
        """

    # 워킹 포워드 결과
    wf_html = ""
    if walkforward_results is not None and not walkforward_results.empty:
        wf_rows = ""
        for _, row in walkforward_results.iterrows():
            wf_rows += f"""
            <tr>
                <td>{row['window_idx']}</td>
                <td>{row['train_start']} ~ {row['train_end']}</td>
                <td>{row['test_start']} ~ {row['test_end']}</td>
                <td>{row['best_ma_type'].upper()}</td>
                <td>{row['best_short_window']}/{row['best_long_window']}</td>
                <td>{row['test_return_pct']:.2f}%</td>
                <td>{row['test_mdd']:.2f}%</td>
            </tr>
            """
        wf_html = f"""
        <h2>Walk-Forward Test Results</h2>
        <table>
            <tr>
                <th>Window</th><th>Train Period</th><th>Test Period</th>
                <th>Best MA</th><th>Short/Long</th>
                <th>Test Return</th><th>Test MDD</th>
            </tr>
            {wf_rows}
        </table>
        """

    # 그래프 이미지 삽입
    images_html = ""
    equity_img = result_dir / "equity_curve.png"
    if equity_img.exists():
        images_html += (
            '<img src="equity_curve.png" alt="Equity Curve" style="max-width:100%;">'
        )

    drawdown_img = result_dir / "drawdown.png"
    if drawdown_img.exists():
        images_html += '<img src="drawdown.png" alt="Drawdown" style="max-width:100%;">'

    for ma_type in ["sma", "ema"]:
        heatmap_img = result_dir / f"grid_heatmap_{ma_type}.png"
        if heatmap_img.exists():
            images_html += f'<img src="grid_heatmap_{ma_type}.png" alt="Grid Heatmap {ma_type.upper()}" style="max-width:100%;">'  # noqa: E501

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Backtest Report - {run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; background-color: white; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: right; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        tr:hover {{ background-color: #ddd; }}
        td:first-child {{ text-align: left; font-weight: bold; }}
        img {{ margin: 20px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        .summary {{ background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>QBT Backtest Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Run ID: {run_id}</p>

    {params_html}

    <div class="summary">
        <h2>Performance Comparison</h2>
        <table>
            <tr>
                <th>Strategy</th>
                <th>Initial Capital</th>
                <th>Final Capital</th>
                <th>Total Return</th>
                <th>CAGR</th>
                <th>MDD</th>
                <th>Trades</th>
                <th>Win Rate</th>
            </tr>
            {performance_rows}
        </table>
    </div>

    {grid_html}
    {wf_html}

    <h2>Charts</h2>
    {images_html}

</body>
</html>
    """  # noqa: E501

    file_path = result_dir / f"report_{run_id}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.debug(f"HTML 리포트 생성: {file_path}")
    return file_path
