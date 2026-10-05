"""
Mapeo de símbolos: nombre estándar -> nombre real en cada broker/exchange.
"""

MT5_SUFFIX = "m"  # Exness agrega "m" a todos los símbolos


def to_mt5_symbol(standard_symbol: str) -> str:
    """Convierte un símbolo estándar (ej. 'EURUSD') al formato real de Exness (ej. 'EURUSDm')."""
    return f"{standard_symbol}{MT5_SUFFIX}"


def to_binance_symbol(standard_symbol: str) -> str:
    """Binance ya usa el nombre estándar directamente (ej. 'BTCUSDT')."""
    return standard_symbol