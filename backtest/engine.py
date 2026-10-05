"""
Motor de backtest para la estrategia de trend following multi-timeframe.
Simula entradas en señales de confluencia (D1+H4+H1 alineados), con
stop loss basado en ATR y ratio riesgo:beneficio 1:3, con cierre
anticipado si aparece señal contraria.
"""
import pandas as pd
import numpy as np

from indicators.trend import calculate_trend_series, calculate_atr
from config.settings import TIMEFRAMES, ADX_THRESHOLD

RISK_REWARD_RATIO = 3.0
ATR_SL_MULTIPLIER = 1.5  # SL a 1.5x ATR de distancia


def align_multi_timeframe(df_bias: pd.DataFrame, df_confirm: pd.DataFrame, df_entry: pd.DataFrame) -> pd.DataFrame:
    """
    Alinea las señales de D1 (bias), H4 (confirm) y H1 (entry) sobre la
    línea de tiempo de H1 (el timeframe más rápido). Para cada vela H1,
    usa la última señal D1/H4 ya *cerrada* en ese momento (evita look-ahead bias).
    """
    bias = calculate_trend_series(df_bias)[["time", "direction", "strength"]].rename(
        columns={"direction": "bias_direction", "strength": "bias_strength"}
    )
    confirm = calculate_trend_series(df_confirm)[["time", "direction", "strength"]].rename(
        columns={"direction": "confirm_direction", "strength": "confirm_strength"}
    )
    entry = calculate_trend_series(df_entry)
    entry["atr"] = calculate_atr(entry)
    entry = entry.rename(columns={"direction": "entry_direction", "strength": "entry_strength"})

    # merge_asof: para cada timestamp de entry, toma el último bias/confirm
    # con time <= ese timestamp (evita usar datos "del futuro")
    entry = entry.sort_values("time")
    bias = bias.sort_values("time")
    confirm = confirm.sort_values("time")

    merged = pd.merge_asof(entry, bias, on="time", direction="backward")
    merged = pd.merge_asof(merged, confirm, on="time", direction="backward")

    return merged


def generate_signals(merged: pd.DataFrame) -> pd.DataFrame:
    """Marca las filas donde los tres timeframes están alineados."""
    aligned = (
        (merged["bias_direction"] == merged["confirm_direction"])
        & (merged["confirm_direction"] == merged["entry_direction"])
        & (merged["bias_direction"] != "sin_tendencia")
    )
    merged["signal"] = np.where(aligned, merged["bias_direction"], "sin_senal")
    return merged


def simulate_trades(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Simula trades: entra en la primera vela con señal (si no hay posición
    abierta), sale por SL, TP, o señal contraria. Un trade a la vez.

    PnL expresado en R-múltiplos (1R = riesgo asumido en el stop loss).
    """
    trades = []
    in_position = False
    direction = None
    entry_price = None
    sl_price = None
    tp_price = None
    entry_time = None

    for i in range(1, len(merged)):
        row = merged.iloc[i]

        if not in_position:
            if row["signal"] in ("alcista", "bajista") and not pd.isna(row["atr"]):
                direction = row["signal"]
                entry_price = row["close"]
                atr = row["atr"]

                if direction == "alcista":
                    sl_price = entry_price - atr * ATR_SL_MULTIPLIER
                    tp_price = entry_price + atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO
                else:
                    sl_price = entry_price + atr * ATR_SL_MULTIPLIER
                    tp_price = entry_price - atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO

                entry_time = row["time"]
                in_position = True
        else:
            exit_reason = None
            exit_price = None

            if direction == "alcista":
                if row["low"] <= sl_price:
                    exit_reason, exit_price = "SL", sl_price
                elif row["high"] >= tp_price:
                    exit_reason, exit_price = "TP", tp_price
                elif row["signal"] == "bajista":
                    exit_reason, exit_price = "señal_contraria", row["close"]
            else:
                if row["high"] >= sl_price:
                    exit_reason, exit_price = "SL", sl_price
                elif row["low"] <= tp_price:
                    exit_reason, exit_price = "TP", tp_price
                elif row["signal"] == "alcista":
                    exit_reason, exit_price = "señal_contraria", row["close"]

            if exit_reason:
                risk = abs(entry_price - sl_price)
                raw_pnl = (exit_price - entry_price) if direction == "alcista" else (entry_price - exit_price)
                pnl_r = raw_pnl / risk if risk > 0 else 0

                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row["time"],
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl": round(pnl_r, 3),
                })
                in_position = False

    return pd.DataFrame(trades)


def run_backtest(df_bias: pd.DataFrame, df_confirm: pd.DataFrame, df_entry: pd.DataFrame) -> pd.DataFrame:
    """Pipeline completo: alinea timeframes, genera señales, simula trades."""
    merged = align_multi_timeframe(df_bias, df_confirm, df_entry)
    merged = generate_signals(merged)
    trades = simulate_trades(merged)
    return trades


if __name__ == "__main__":
    from data.fetch_mt5 import fetch_mt5_candles
    from backtest.metrics import calculate_metrics

    symbol = "EURUSD"
    df_d1 = fetch_mt5_candles(symbol, "D1", 1000)
    df_h4 = fetch_mt5_candles(symbol, "H4", 1000)
    df_h1 = fetch_mt5_candles(symbol, "H1", 1000)

    trades = run_backtest(df_d1, df_h4, df_h1)

    print(f"Total de trades simulados: {len(trades)}")
    if not trades.empty:
        print(trades.tail(10))

        split_idx = int(len(trades) * 0.7)
        in_sample = trades.iloc[:split_idx]
        out_sample = trades.iloc[split_idx:]

        print("\n=== IN-SAMPLE (70%) ===")
        print(calculate_metrics(in_sample))

        print("\n=== OUT-OF-SAMPLE (30%) ===")
        print(calculate_metrics(out_sample))
