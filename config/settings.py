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

# --- Parámetros de ejecución ---
MAGIC_NUMBER = 123456           # ID único para rastrear órdenes del bot

# --- Parámetros de salida corta (Scalping / Day Trading) ---
ATR_SL_MULTIPLIER = 1.0
RISK_REWARD_RATIO = 1.2

# --- Parámetros de salida corta (Scalping / Day Trading) ---
# Un multiplicador menor (1.0) hace que el Stop Loss sea más ceñido
# Un RR menor (1.2 a 1.5) hace que el TP sea mucho más alcanzable en pocas horas
ATR_SL_MULTIPLIER = 1.0
RISK_REWARD_RATIO = 1.2

ACCOUNT_LEVERAGE_CAP = 1.0      # apalancamiento máximo (techo, no objetivo)

# --- Distancia de SL y TP final, en múltiplos del ATR de H1 ---
# Perfil corto (objetivo alcanzable en ~4-5 horas): SL 1.0 / TP 1.5.
# Perfil anterior (swing de varios días):          SL 1.5 / TP 4.5.
SL_ATR_MULTIPLIER = 1.0
TP_ATR_MULTIPLIER = 1.5

# --- SL escalonado (múltiplos del riesgo inicial). El tercer valor es el TP final y se deriva de arriba ---
MULTI_TP_LEVELS = [
    (0.5, 0.33),   # TP1: el SL pasa a breakeven
    (1.0, 0.33),   # TP2: el SL pasa al nivel de TP1
    (TP_ATR_MULTIPLIER / SL_ATR_MULTIPLIER, 0.34),   # TP final (va dentro de la orden)
]

# Capital operativo para calcular riesgo. None = usa el balance real de la cuenta.
# Ej.: 50.0 para simular una cuenta de $50 sobre la demo de $500.
OPERATING_CAPITAL = None

# --- Lote y tope de riesgo con lote fijo ---
# Lote fijo por operación (None = calcular el lote según el riesgo y la fuerza de la señal)
FIXED_LOT = 0.01
# Tope de riesgo real por trade con lote fijo, como fracción del capital operativo (None = sin tope)
MAX_RISK_PER_TRADE_PCT = 0.03

# Filtro de spread: omitir si spread > fracción del TP esperado
MAX_SPREAD_FRACTION_OF_TP = 0.10

# --- Seguridad de cuenta: solo demo por defecto ---
ALLOW_LIVE_ACCOUNT = False

# --- Salida de posiciones (monitor): SL escalonado + trailing por ATR tras TP2 ---
ATR_TRAILING_MULTIPLIER = 2.0

