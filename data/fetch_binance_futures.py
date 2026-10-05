"""
Cliente y funciones de datos para Binance Futures (testnet).
"""
import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

_futures_client = None


def get_binance_futures_client():
    """Devuelve un cliente de Binance Futures testnet (singleton simple)."""
    global _futures_client
    if _futures_client is None:
        _futures_client = Client(
            os.getenv("BINANCE_FUTURES_API_KEY"),
            os.getenv("BINANCE_FUTURES_API_SECRET"),
            testnet=True,
        )
        # Apunta al endpoint de futures testnet (distinto al de spot testnet)
        _futures_client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
    return _futures_client
