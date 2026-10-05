"""
Métricas de desempeño para evaluar resultados de backtest.
"""
import pandas as pd


def calculate_metrics(trades: pd.DataFrame) -> dict:
    """
    Args:
        trades: DataFrame con columna 'pnl' (ganancia/pérdida en R-múltiplos
                o en unidades monetarias, una fila por trade)

    Returns:
        dict con profit_factor, win_rate, total_trades, avg_win, avg_loss,
        max_drawdown, net_result
    """
    if trades.empty:
        return {
            "total_trades": 0,
            "win_rate": None,
            "profit_factor": None,
            "avg_win": None,
            "avg_loss": None,
            "net_result": 0.0,
            "max_drawdown": None,
        }

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]

    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(wins) / len(trades) if len(trades) > 0 else 0

    equity_curve = trades["pnl"].cumsum()
    running_max = equity_curve.cummax()
    drawdown = equity_curve - running_max
    max_drawdown = drawdown.min()

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "avg_win": round(wins["pnl"].mean(), 4) if not wins.empty else 0,
        "avg_loss": round(losses["pnl"].mean(), 4) if not losses.empty else 0,
        "net_result": round(trades["pnl"].sum(), 4),
        "max_drawdown": round(max_drawdown, 4),
    }
