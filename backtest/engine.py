"""
Motor de backtest para la estrategia de trend following multi-timeframe.
Simula entradas en señales de confluencia (D1+H4+H1 alineados), con
stop loss y take profit en múltiplos de ATR (ver config/settings.py), con cierre
anticipado si aparece señal contraria.
"""
import pandas as pd
import numpy as np

from indicators.trend import calculate_trend_series, calculate_atr
from config.settings import (
    TIMEFRAMES, ADX_THRESHOLD, SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER, MULTI_TP_LEVELS,
)

# Se derivan de config/settings.py para que scanner y backtest usen siempre las mismas distancias
ATR_SL_MULTIPLIER = SL_ATR_MULTIPLIER                        # SL a N x ATR
RISK_REWARD_RATIO = TP_ATR_MULTIPLIER / SL_ATR_MULTIPLIER    # TP final en múltiplos del riesgo


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


def simulate_trades(merged: pd.DataFrame, sl_mult=None, tp_mult=None,
                    max_hold_bars=None, ladder=False, cost_atr=0.0) -> pd.DataFrame:
    """
    Simula trades: entra en la primera vela con señal (si no hay posición
    abierta), sale por SL, TP, señal contraria o (opcional) límite de tiempo.
    Un trade a la vez. PnL en R-múltiplos (1R = riesgo inicial del stop).

    sl_mult / tp_mult: distancias en múltiplos de ATR (por defecto, las de settings).
    max_hold_bars:     cierra a mercado tras N velas H1 (ej. 5 = "4 o 5 horas").
    ladder:            aplica el SL escalonado (TP1 -> breakeven, TP2 -> SL en TP1).
                       El SL nuevo rige desde la vela siguiente (sin look-ahead).
    cost_atr:          costo por trade (spread + deslizamiento) en múltiplos de ATR.
    """
    sl_mult = ATR_SL_MULTIPLIER if sl_mult is None else sl_mult
    tp_mult = TP_ATR_MULTIPLIER if tp_mult is None else tp_mult
    lvl1, lvl2 = MULTI_TP_LEVELS[0][0], MULTI_TP_LEVELS[1][0]

    times = merged["time"].to_numpy()
    highs = merged["high"].to_numpy(float)
    lows = merged["low"].to_numpy(float)
    closes = merged["close"].to_numpy(float)
    atrs = merged["atr"].to_numpy(float)
    signals = merged["signal"].to_numpy()

    trades = []
    in_position = False
    entry_i = sign = entry = sl0 = sl = tp = risk0 = atr = None

    for i in range(1, len(merged)):
        if not in_position:
            if signals[i] in ("alcista", "bajista") and not np.isnan(atrs[i]):
                sign = 1 if signals[i] == "alcista" else -1
                entry = closes[i]
                atr = atrs[i]
                risk0 = atr * sl_mult
                sl0 = sl = entry - sign * risk0
                tp = entry + sign * atr * tp_mult
                entry_i = i
                in_position = True
            continue

        if sign == 1:
            hit_sl, hit_tp, contra = lows[i] <= sl, highs[i] >= tp, signals[i] == "bajista"
        else:
            hit_sl, hit_tp, contra = highs[i] >= sl, lows[i] <= tp, signals[i] == "alcista"

        reason = exit_price = None
        if hit_sl:
            reason, exit_price = ("SL" if sl == sl0 else "SL_escalonado"), sl
        elif hit_tp:
            reason, exit_price = "TP", tp
        elif contra:
            reason, exit_price = "señal_contraria", closes[i]
        elif max_hold_bars is not None and i - entry_i >= max_hold_bars:
            reason, exit_price = "tiempo", closes[i]

        if reason:
            raw_pnl = (exit_price - entry) * sign
            pnl_r = (raw_pnl - cost_atr * atr) / risk0 if risk0 > 0 else 0
            trades.append({
                "entry_time": times[entry_i],
                "exit_time": times[i],
                "direction": "alcista" if sign == 1 else "bajista",
                "entry_price": entry,
                "exit_price": exit_price,
                "exit_reason": reason,
                "bars_held": i - entry_i,
                "pnl": round(float(pnl_r), 3),
            })
            in_position = False
        elif ladder:
            favorable = (highs[i] - entry) if sign == 1 else (entry - lows[i])
            new_sl = None
            if favorable >= lvl2 * risk0:
                new_sl = entry + sign * lvl1 * risk0
            elif favorable >= lvl1 * risk0:
                new_sl = entry
            if new_sl is not None and ((sign == 1 and new_sl > sl) or (sign == -1 and new_sl < sl)):
                sl = new_sl

    return pd.DataFrame(trades)


def run_backtest(df_bias: pd.DataFrame, df_confirm: pd.DataFrame, df_entry: pd.DataFrame, **exit_params) -> pd.DataFrame:
    """Pipeline completo: alinea timeframes, genera señales, simula trades.
    exit_params se pasa a simulate_trades (sl_mult, tp_mult, max_hold_bars, ladder, cost_atr)."""
    merged = align_multi_timeframe(df_bias, df_confirm, df_entry)
    merged = generate_signals(merged)
    return simulate_trades(merged, **exit_params)


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
