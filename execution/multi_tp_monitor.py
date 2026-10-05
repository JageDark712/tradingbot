"""
Monitor de Posiciones: Gestiona el seguimiento de trades abiertos,
implementando Trailing Stop basado en ATR y movimiento a Breakeven.
"""
import pandas as pd
import numpy as np
from data.fetch_mt5 import fetch_mt5_candles
from indicators.trend import calculate_atr
from execution.mt5_executor import get_open_mt5_positions, modify_position_sl
from execution.position_tracker import get_position_state, get_all_tracked_tickets
from config.settings import ATR_TRAILING_MULTIPLIER # Asumiremos que existe o usaremos un default

# Configuración por defecto si no está en settings
DEFAULT_TRAILING_MULTIPLIER = 2.0
BREAKEVEN_RATIO = 1.0  # Mover a BE cuando el profit es 1x el riesgo original

def update_trailing_stops():
    """
    Recorre todas las posiciones abiertas y ajusta el SL según el ATR y el precio actual.
    """
    print("Ejecutando actualización de Trailing Stops...")

    # 1. Obtener posiciones reales de MT5
    positions = get_open_mt5_positions()
    if not positions:
        print("No hay posiciones abiertas para monitorear.")
        return

    for pos in positions:
        ticket = pos["ticket"]
        symbol = pos["symbol"]
        direction = "alcista" if pos["type"] == 0 else "bajista"
        current_sl = pos["sl"]
        entry_price = pos["price_open"]

        # 2. Obtener datos para calcular ATR actual
        try:
            df = fetch_mt5_candles(symbol, "H1", 50)
            if df is None or df.empty:
                continue

            atr = calculate_atr(df).iloc[-1]
            tick = get_mt5_connection().symbol_info_tick(symbol)
            current_price = tick.bid if direction == "alcista" else tick.ask

            # 3. Lógica de Breakeven (Protección Inicial)
            # Calculamos la distancia de riesgo original
            risk_distance = abs(entry_price - current_sl) if current_sl != 0 else 0
            current_profit = abs(current_price - entry_price)

            if current_sl != entry_price and current_profit >= risk_distance * BREAKEVEN_RATIO:
                # Mover a Breakeven si no se ha hecho ya
                print(f"  [BE] Moviendo ticket {ticket} ({symbol}) a Breakeven.")
                modify_position_sl(ticket, entry_price)
                continue

            # 4. Lógica de Trailing Stop basado en ATR
            if direction == "alcista":
                # En compras, el SL solo puede SUBIR
                new_sl = current_price - (atr * DEFAULT_TRAILING_MULTIPLIER)
                if new_sl > current_sl:
                    print(f"  [TS] Subiendo SL de {symbol} (ticket {ticket}): {current_sl} -> {new_sl:.5f}")
                    modify_position_sl(ticket, new_sl)
            else:
                # En ventas, el SL solo puede BAJAR
                new_sl = current_price + (atr * DEFAULT_TRAILING_MULTIPLIER)
                if current_sl == 0 or new_sl < current_sl:
                    print(f"  [TS] Bajando SL de {symbol} (ticket {ticket}): {current_sl} -> {new_sl:.5f}")
                    modify_position_sl(ticket, new_sl)

        except Exception as e:
            print(f"  [ERROR] Fallo al actualizar stop para {symbol} (ticket {ticket}): {e}")

def get_mt5_connection():
    """Helper para obtener conexión en este módulo."""
    from data.fetch_mt5 import get_mt5_connection
    return get_mt5_connection()

if __name__ == "__main__":
    # Ejecución manual para test
    update_trailing_stops()
