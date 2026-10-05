"""
Funciones para traer datos históricos desde Binance (testnet).
"""
import os
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

from config.symbols import to_binance_symbol
from config.settings import CANDLES_LOOKBACK

load_dotenv()

# Mapeo de timeframe en texto -> constante de Binance
BINANCE_TIMEFRAME_MAP = {
    "M1": Client.KLINE_INTERVAL_1MINUTE,
    "M5": Client.KLINE_INTERVAL_5MINUTE,
    "M15": Client.KLINE_INTERVAL_15MINUTE,
    "M30": Client.KLINE_INTERVAL_30MINUTE,
    "H1": Client.KLINE_INTERVAL_1HOUR,
    "H4": Client.KLINE_INTERVAL_4HOUR,
    "D1": Client.KLINE_INTERVAL_1DAY,
    "W1": Client.KLINE_INTERVAL_1WEEK,
}

_binance_client = None


def get_binance_client():
    """Devuelve un cliente de Binance ya inicializado (singleton simple)."""
    global _binance_client
    if _binance_client is None:
        _binance_client = Client(
            os.getenv("BINANCE_API_KEY"),
            os.getenv("BINANCE_API_SECRET"),
            testnet=True,
        )
    return _binance_client


def fetch_binance_candles(symbol: str, timeframe: str, n_candles: int = CANDLES_LOOKBACK) -> pd.DataFrame:
    """
    Trae velas históricas de Binance para un símbolo y timeframe dados.

    Args:
        symbol: símbolo estándar, ej. "BTCUSDT"
        timeframe: "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"
        n_candles: cantidad de velas a traer

    Returns:
        DataFrame con columnas: time, open, high, low, close, volume, symbol
    """
    client = get_binance_client()

    binance_symbol = to_binance_symbol(symbol)
    interval = BINANCE_TIMEFRAME_MAP.get(timeframe)
    if interval is None:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

    klines = client.get_klines(symbol=binance_symbol, interval=interval, limit=n_candles)

    if not klines:
        raise ValueError(f"No se obtuvieron datos para {binance_symbol} en {timeframe}.")

    df = pd.DataFrame(klines, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["symbol"] = symbol
    return df[["time", "open", "high", "low", "close", "volume", "symbol"]]


if __name__ == "__main__":
    df = fetch_binance_candles("BTCUSDT", "D1", 20)
    print(df.tail())
