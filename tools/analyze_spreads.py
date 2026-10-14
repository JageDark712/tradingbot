"""
Analiza los spreads actuales de los símbolos del universo para proponer
un valor de MAX_SPREAD_FRACTION_OF_TP.
"""
import numpy as np
import pandas as pd
from config.settings import (
    FOREX_SYMBOLS, CRYPTO_SYMBOLS, COMMODITY_SYMBOLS, ETF_SYMBOLS,
    SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER
)
from data.fetch_mt5 import get_mt5_connection

def analyze():
    mt5 = get_mt5_connection()
    universo = FOREX_SYMBOLS + CRYPTO_SYMBOLS + COMMODITY_SYMBOLS + ETF_SYMBOLS
    results = []

    print(f"Analizando spreads para {len(universo)} símbolos...")

    for symbol in universo:
        sym_m = symbol + "m"
        info = mt5.symbol_info(sym_m)
        if info is None:
            print(f"  [ERROR] No se pudo obtener info de {sym_m}")
            continue

        spread = float(info.spread) * info.point
        results.append({
            "symbol": symbol,
            "spread_pts": info.spread,
            "spread_val": spread,
            "point": info.point
        })

    df = pd.DataFrame(results)
    print("\nResumen de Spreads:")
    print(df.to_string(index=False))

    print("\nSugerencia:")
    print("Un spread aceptable suele ser < 10% del TP esperado.")
    print(f"Si TP = {TP_ATR_MULTIPLIER} * ATR, entonces MAX_SPREAD_FRACTION_OF_TP ≈ 0.10")

if __name__ == "__main__":
    analyze()
