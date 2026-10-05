"""
Indicadores de tendencia: EMA (dirección) + ADX (fuerza/confirmación).
"""
import pandas as pd
import numpy as np

from config.settings import EMA_FAST, EMA_SLOW, ADX_PERIOD, ADX_THRESHOLD


def calculate_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calcula una EMA simple sobre una columna de precios."""
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.DataFrame:
    """
    Calcula ADX, +DI y -DI manualmente (sin dependencias externas de TA).
    Devuelve un DataFrame con columnas: plus_di, minus_di, adx
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    # Suavizado tipo Wilder
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame({
        "plus_di": plus_di,
        "minus_di": minus_di,
        "adx": adx,
    })


def get_trend_signal(df: pd.DataFrame) -> dict:
    """
    Determina la señal de tendencia para el último valor disponible del DataFrame.

    Args:
        df: DataFrame con columnas open, high, low, close (ordenado cronológicamente)

    Returns:
        dict con: direction ("alcista"/"bajista"/"sin_tendencia"),
                  strength (0.0 a 1.0),
                  ema_fast, ema_slow, adx (valores actuales, para debug)
    """
    df = df.copy()
    df["ema_fast"] = calculate_ema(df, EMA_FAST)
    df["ema_slow"] = calculate_ema(df, EMA_SLOW)

    adx_data = calculate_adx(df)
    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]

    last = df.iloc[-1]

    ema_fast = last["ema_fast"]
    ema_slow = last["ema_slow"]
    adx = last["adx"]
    plus_di = last["plus_di"]
    minus_di = last["minus_di"]

    # Dirección según EMA
    if ema_fast > ema_slow:
        ema_direction = "alcista"
    elif ema_fast < ema_slow:
        ema_direction = "bajista"
    else:
        ema_direction = "sin_tendencia"

    # Sin tendencia confirmada si ADX está por debajo del umbral
    if pd.isna(adx) or adx < ADX_THRESHOLD:
        direction = "sin_tendencia"
        strength = 0.0
    else:
        direction = ema_direction
        # Fuerza normalizada: ADX de 20 a 50+ mapeado a 0.0-1.0
        strength = min((adx - ADX_THRESHOLD) / 30, 1.0)
        strength = max(strength, 0.0)

    return {
        "direction": direction,
        "strength": round(float(strength), 3),
        "ema_fast": round(float(ema_fast), 5) if not pd.isna(ema_fast) else None,
        "ema_slow": round(float(ema_slow), 5) if not pd.isna(ema_slow) else None,
        "adx": round(float(adx), 2) if not pd.isna(adx) else None,
        "plus_di": round(float(plus_di), 2) if not pd.isna(plus_di) else None,
        "minus_di": round(float(minus_di), 2) if not pd.isna(minus_di) else None,
    }


if __name__ == "__main__":
    from data.fetch_mt5 import fetch_mt5_candles

    df = fetch_mt5_candles("EURUSD", "D1", 100)
    signal = get_trend_signal(df)
    print(f"EURUSD D1: {signal}")


def calculate_trend_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Versión vectorizada de get_trend_signal: calcula dirección y fuerza de
    tendencia para CADA fila del DataFrame (no solo la última), para usar
    en backtest.

    Returns:
        DataFrame original + columnas: ema_fast, ema_slow, adx, plus_di,
        minus_di, direction, strength
    """
    df = df.copy()
    df["ema_fast"] = calculate_ema(df, EMA_FAST)
    df["ema_slow"] = calculate_ema(df, EMA_SLOW)

    adx_data = calculate_adx(df)
    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]

    ema_direction = np.where(
        df["ema_fast"] > df["ema_slow"], "alcista",
        np.where(df["ema_fast"] < df["ema_slow"], "bajista", "sin_tendencia")
    )

    has_trend = df["adx"] >= ADX_THRESHOLD
    df["direction"] = np.where(has_trend, ema_direction, "sin_tendencia")

    raw_strength = ((df["adx"] - ADX_THRESHOLD) / 30).clip(lower=0, upper=1)
    df["strength"] = np.where(has_trend, raw_strength, 0.0)

    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR (Average True Range) para dimensionar stop loss / take profit."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False).mean()
