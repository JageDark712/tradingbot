"""
Indicador de momentum: Rate of Change (ROC) multi-período.
"""
import pandas as pd

MOMENTUM_PERIODS = [20, 60, 120]


def calculate_roc(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Rate of Change: % de cambio del precio en los últimos 'period' períodos."""
    return df[column].pct_change(periods=period) * 100


def get_momentum_signal(df: pd.DataFrame) -> dict:
    """
    Calcula momentum combinado (promedio de ROC en varios períodos) para
    el último valor disponible del DataFrame.

    Returns:
        dict con: direction, raw_momentum (promedio de ROC %),
                  roc_by_period (detalle por período)
    """
    df = df.copy()
    roc_values = {}

    for period in MOMENTUM_PERIODS:
        if len(df) > period:
            roc = calculate_roc(df, period)
            roc_values[period] = roc.iloc[-1]
        else:
            roc_values[period] = None

    valid_rocs = [v for v in roc_values.values() if v is not None and not pd.isna(v)]

    if not valid_rocs:
        return {"direction": "sin_senal", "raw_momentum": None, "roc_by_period": roc_values}

    avg_momentum = sum(valid_rocs) / len(valid_rocs)
    direction = "alcista" if avg_momentum > 0 else "bajista" if avg_momentum < 0 else "sin_senal"

    return {
        "direction": direction,
        "raw_momentum": round(avg_momentum, 3),
        "roc_by_period": {k: round(v, 3) if v is not None and not pd.isna(v) else None for k, v in roc_values.items()},
    }


if __name__ == "__main__":
    from data.fetch_mt5 import fetch_mt5_candles

    df = fetch_mt5_candles("EURUSD", "D1", 200)
    signal = get_momentum_signal(df)
    print(f"EURUSD D1 momentum: {signal}")
