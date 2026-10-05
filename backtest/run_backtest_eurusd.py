"""
Backtest de trend following sobre EURUSD con historia extendida.
"""
from data.fetch_mt5 import fetch_mt5_candles
from backtest.engine import run_backtest
from backtest.metrics import calculate_metrics

symbol = "EURUSD"

print(f"Descargando histórico extendido de {symbol}...")

df_d1 = fetch_mt5_candles(symbol, "D1", 1000)
df_h4 = fetch_mt5_candles(symbol, "H4", 5000)
df_h1 = fetch_mt5_candles(symbol, "H1", 20000)

print(f"Velas obtenidas: D1={len(df_d1)}, H4={len(df_h4)}, H1={len(df_h1)}")
print(f"Rango D1: {df_d1['time'].min()} a {df_d1['time'].max()}")

trades = run_backtest(df_d1, df_h4, df_h1)
print(f"\nTotal de trades simulados: {len(trades)}")

if not trades.empty:
    split_idx = int(len(trades) * 0.7)
    in_sample = trades.iloc[:split_idx]
    out_sample = trades.iloc[split_idx:]

    print("\n=== IN-SAMPLE (70%) ===")
    print(calculate_metrics(in_sample))

    print("\n=== OUT-OF-SAMPLE (30%) ===")
    print(calculate_metrics(out_sample))
else:
    print("No se generaron trades en este período.")
