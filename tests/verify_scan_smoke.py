import sys, types, io, contextlib, zlib
sys.path.insert(0, ".")
for name in ["mt5linux", "binance", "binance.client", "binance.enums", "dotenv"]:
    m = types.ModuleType(name); m.MetaTrader5 = object
    m.Client = type("Client", (), {k: 1 for k in ["KLINE_INTERVAL_1MINUTE","KLINE_INTERVAL_5MINUTE","KLINE_INTERVAL_15MINUTE","KLINE_INTERVAL_30MINUTE","KLINE_INTERVAL_1HOUR","KLINE_INTERVAL_4HOUR","KLINE_INTERVAL_1DAY","KLINE_INTERVAL_1WEEK"]})
    m.load_dotenv = lambda *a, **k: None
    sys.modules[name] = m
import numpy as np, pandas as pd
import scanner.run_scan as rs
import config.settings as S

seen = {}
STEP = {"D1": 1440, "H4": 240, "H1": 60}
def synth(symbol, tf, n=200):
    seen.setdefault(symbol, set()).add(tf)
    seed = zlib.crc32(f"{symbol}".encode()) % 10_000
    rng = np.random.default_rng(seed + {"D1": 1, "H4": 2, "H1": 3}[tf])
    kind = seed % 10                       # 0-3 sube, 4-6 baja, 7-9 lateral
    drift = {True: 0.0, False: 0.0}
    vol = 0.004 * (STEP[tf] / 1440) ** 0.5 + 0.0005
    mu = (0.9 * vol) if kind <= 3 else (-0.9 * vol) if kind <= 6 else 0.0
    close = 100 * np.exp(np.cumsum(rng.normal(mu, vol, n)))
    spread = np.abs(rng.normal(0, vol / 2, n)) * close
    t0 = pd.Timestamp("2026-01-01")
    return pd.DataFrame({"time": [t0 + pd.Timedelta(minutes=STEP[tf] * i) for i in range(n)],
                         "open": close, "high": close + spread, "low": close - spread, "close": close,
                         "tick_volume": 1000, "symbol": symbol})
rs.fetch_mt5_candles = synth

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    df = rs.run_full_scan()
errores = [l for l in buf.getvalue().splitlines() if "ERROR" in l]

universo = S.FOREX_SYMBOLS + S.CRYPTO_SYMBOLS + S.COMMODITY_SYMBOLS + S.ETF_SYMBOLS
print(f"Símbolos del universo: {len(universo)} | analizados (con datos pedidos): {len(seen)}")
print(f"Timeframes pedidos por símbolo: { {s: sorted(v) for s, v in list(seen.items())[:1]} } (ejemplo)")
print(f"Errores durante el escaneo: {len(errores)}", errores[:3])
print(f"Señales devueltas: {len(df)} | columnas: {list(df.columns)}")
print(df[["symbol", "category", "direction", "strength", "agreement", "regime"]].to_string(index=False))
print("\nRégimen asignado a las señales:", df["regime"].value_counts().to_dict())
ok = len(seen) == len(universo) and not errores and {"entry_price", "sl_price", "tp_price", "regime", "raw_momentum"} <= set(df.columns)
# SL/TP: relación 1:3 y lado correcto
r = df.assign(riesgo=(df.entry_price - df.sl_price).abs(), recompensa=(df.tp_price - df.entry_price).abs())
esperado = S.TP_ATR_MULTIPLIER / S.SL_ATR_MULTIPLIER
ratio_ok = np.allclose(r.recompensa / r.riesgo, esperado, atol=0.02)
lado_ok = all((row.sl_price < row.entry_price < row.tp_price) if row.direction == "alcista" else (row.tp_price < row.entry_price < row.sl_price) for row in df.itertuples())
print(f"\nRatio recompensa/riesgo = {esperado} (según settings) en todas: {ratio_ok} | SL/TP del lado correcto: {lado_ok}")
print("PIPELINE COMPLETO:", "OK" if ok and ratio_ok and lado_ok else "REVISAR")

# ---- Backtest con datos sintéticos (comprueba que el motor sigue corriendo) ----
from backtest.engine import run_backtest, ATR_SL_MULTIPLIER, RISK_REWARD_RATIO
from backtest.metrics import calculate_metrics
d1, h4, h1 = synth("EURUSD", "D1", 600), synth("EURUSD", "H4", 1500), synth("EURUSD", "H1", 5000)
tr = run_backtest(d1, h4, h1)
print(f"\nBacktest sintético: {len(tr)} trades | {calculate_metrics(tr) if len(tr) else 'sin trades'}")
