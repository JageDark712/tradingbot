"""
Configuración global del scanner multi-activo.
"""

# --- Timeframes para la señal de tendencia (multi-timeframe) ---
TIMEFRAMES = {
    "bias": "D1",
    "confirm": "H4",
    "entry": "H1",
}

# --- Universo de activos ---

# Top 5 cripto por capitalización/liquidez
CRYPTO_SYMBOLS = [
    "BTCUSD",
    "ETHUSD",
    "BNBUSD",
    "SOLUSD",
    "XRPUSD",
]

# Top 10 pares forex más líquidos
FOREX_SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "GBPJPY",
]

# Materias primas / energía (nombres confirmados en Exness, sin sufijo "m")
COMMODITY_SYMBOLS = [
    "XAUUSD",   # Oro
    "USOIL",    # Petróleo WTI
    "XNGUSD",   # Gas natural
]

# Índices bursátiles principales (nombres confirmados en Exness, sin sufijo "m")
ETF_SYMBOLS = [
    "US500",    # S&P 500
    "USTEC",    # Nasdaq 100
    "US30",     # Dow Jones
    "UK100",    # FTSE 100
]

# --- Parámetros de indicadores de tendencia ---
EMA_FAST = 20
EMA_SLOW = 50
ADX_PERIOD = 14
ADX_THRESHOLD = 20

CANDLES_LOOKBACK = 200
CONFLUENCE_THRESHOLD = 0.6

# --- Gestión de riesgo ---
RISK_BASE_BY_CATEGORY = {
    "forex": 0.005,       # 0.5% del capital (Reducido para micro-cuenta)
    "crypto": 0.003,      # 0.3% del capital (Reducido para micro-cuenta)
    "commodity": 0.005,  # 0.5% del capital (Reducido para micro-cuenta)
    "index": 0.005,       # 0.5% del capital (Reducido para micro-cuenta)
}

MAX_AGGREGATE_RISK = 0.05       # 5% máximo de riesgo abierto simultáneo total
MAX_TRADES_PER_CATEGORY = 5     # máximo de trades simultáneos por categoría

ACCOUNT_LEVERAGE_CAP = 1.0      # apalancamiento máximo (techo, no objetivo)

# --- Take profits escalonados (múltiplo de riesgo, fracción a cerrar) ---
MULTI_TP_LEVELS = [
    (0.5, 0.33),   # TP1: 0.5x el riesgo, cierra 33%
    (1.0, 0.33),   # TP2: 1.0x el riesgo, cierra 33%
    (3.0, 0.34),   # TP3: 3.0x el riesgo, cierra el resto (34%)
]

# Capital operativo para calcular riesgo. None = usa el balance real de la cuenta.
# Ej.: 50.0 para simular una cuenta de $50 sobre la demo de $500.
OPERATING_CAPITAL = None
