"""
Prueba controlada: ejecuta UNA orden manual pequeña en EURUSD para validar
que execute_mt5_order() funciona correctamente antes de automatizar todo.
"""
from data.fetch_mt5 import fetch_mt5_candles
from indicators.trend import calculate_atr
from execution.mt5_executor import execute_mt5_order, get_open_mt5_positions
from backtest.engine import ATR_SL_MULTIPLIER, RISK_REWARD_RATIO

symbol = "BTCUSD"
direction = "alcista"  # cambia a "bajista" si prefieres probar en corto
volume = 0.01  # lote mínimo típico, bajo riesgo

df = fetch_mt5_candles(symbol, "H1", 200)
df["atr"] = calculate_atr(df)
last = df.iloc[-1]

entry_price = float(last["close"])
atr = float(last["atr"])

if direction == "alcista":
    sl_price = entry_price - atr * ATR_SL_MULTIPLIER
    tp_price = entry_price + atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO
else:
    sl_price = entry_price + atr * ATR_SL_MULTIPLIER
    tp_price = entry_price - atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO

print(f"Símbolo: {symbol}")
print(f"Dirección: {direction}")
print(f"Entrada (referencia): {entry_price}")
print(f"SL calculado: {sl_price}")
print(f"TP calculado: {tp_price}")
print(f"Volumen: {volume}")

confirm = input("\n¿Confirmas enviar esta orden a la cuenta demo? (escribe SI): ")

if confirm.strip().upper() == "SI":
    result = execute_mt5_order(symbol, direction, volume, sl_price, tp_price)
    print("\nResultado de la orden:")
    print(result)

    print("\nPosiciones abiertas actuales:")
    for pos in get_open_mt5_positions():
        print(f"  {pos['symbol']} | vol={pos['volume']} | sl={pos['sl']} | tp={pos['tp']}")
else:
    print("Cancelado, no se envió ninguna orden.")
