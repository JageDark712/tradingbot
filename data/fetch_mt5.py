"""
Funciones para traer datos históricos desde MT5 (Exness).
"""
import pandas as pd
from mt5linux import MetaTrader5
from execution.connection_manager import connection_manager

from config.symbols import to_mt5_symbol
from config.settings import CANDLES_LOOKBACK

# Mapeo de timeframe en texto -> Valor entero de MT5
# Valores tomados de mt5linux.MetaTrader5.TIMEFRAME_* constants
MT5_TIMEFRAME_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
}

# El ConnectionManager ahora gestiona la instancia global


def get_mt5_connection():
    """Devuelve la instancia MetaTrader5 gestionada por el ConnectionManager."""
    mt5 = connection_manager.get_connection()
    if mt5 is None:
        raise ConnectionError("No se pudo establecer conexión con el servidor mt5linux.")
    return mt5


def fetch_mt5_candles(symbol: str, timeframe: str, n_candles: int = CANDLES_LOOKBACK) -> pd.DataFrame:
    """
    Trae velas históricas de MT5 para un símbolo y timeframe dados.

    Args:
        symbol: símbolo estándar, ej. "EURUSD", "XAUUSD", "US500"
        timeframe: "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"
        n_candles: cantidad de velas a traer

    Returns:
        DataFrame con columnas: time, open, high, low, close, tick_volume, spread, real_volume
    """
    mt5 = get_mt5_connection()

    mt5_symbol = to_mt5_symbol(symbol)
    tf_val = MT5_TIMEFRAME_MAP.get(timeframe)
    if tf_val is None:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

    mt5.symbol_select(mt5_symbol, True)
    rates = mt5.copy_rates_from_pos(mt5_symbol, tf_val, 0, n_candles)

    if rates is None or len(rates) == 0:
        raise ValueError(
            f"No se obtuvieron datos para {mt5_symbol} en {timeframe}. "
            f"Último error: {mt5.last_error()}"
        )

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["symbol"] = symbol  # nombre estándar, no el de MT5
    return df


if __name__ == "__main__":
    # Prueba rápida
    df = fetch_mt5_candles("EURUSD", "D1", 20)
    print(df.tail())


def fetch_mt5_candles_by_date(symbol: str, timeframe: str, date_from, date_to=None) -> pd.DataFrame:
    """
    Trae velas históricas de MT5 en un rango de fechas (en vez de contar
    velas hacia atrás). Útil para backtests que necesitan años de historia.
    """
    import datetime

    mt5 = get_mt5_connection()

    mt5_symbol = to_mt5_symbol(symbol)
    tf_val = MT5_TIMEFRAME_MAP.get(timeframe)
    if tf_val is None:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

    if date_to is None:
        date_to = datetime.datetime.now()

    # Convertir a timestamps Unix (int) para evitar bug de serialización
    # de mt5linux con objetos datetime en copy_rates_range
    ts_from = int(date_from.timestamp())
    ts_to = int(date_to.timestamp())

    mt5.symbol_select(mt5_symbol, True)
    rates = mt5.copy_rates_range(mt5_symbol, tf_val, ts_from, ts_to)

    if rates is None or len(rates) == 0:
        raise ValueError(
            f"No se obtuvieron datos para {mt5_symbol} en {timeframe} "
            f"entre {date_from} y {date_to}. Último error: {mt5.last_error()}"
        )

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["symbol"] = symbol
    return df
