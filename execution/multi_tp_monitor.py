"""
Monitor de posiciones: SL escalonado + trailing por ATR.

Para cada posición registrada por el scanner (usa el riesgo ORIGINAL guardado
en position_tracker, nunca el SL actual):
  - TP1 (0.5x el riesgo): SL a breakeven.
  - TP2 (1.0x el riesgo): SL al precio de TP1.
  - Después de TP2: trailing stop por ATR (H1). Solo sube en compras / solo baja
    en ventas; nunca afloja el SL.
El TP final (3x) sigue puesto en la orden original. No hace cierres parciales
(con lote 0.01 no se puede dividir la posición).
"""
import time

from config import settings
from config.settings import MULTI_TP_LEVELS
from data.fetch_mt5 import fetch_mt5_candles, get_mt5_connection
from indicators.trend import calculate_atr
from execution.mt5_executor import modify_position_sl
from execution.position_tracker import (
    get_position_state, mark_tp_level_hit, remove_position, get_all_tracked_tickets,
)

ATR_TRAILING_MULTIPLIER = getattr(settings, "ATR_TRAILING_MULTIPLIER", 2.0)
CHECK_INTERVAL_SECONDS = 30
TRAILING_CANDLES = 100


def standard_symbol(mt5_symbol: str) -> str:
    # fetch_mt5_candles agrega el sufijo "m"; hay que pasarle el símbolo sin él
    return mt5_symbol[:-1] if mt5_symbol.endswith("m") else mt5_symbol


def level_price(direction: str, entry: float, risk: float, multiple: float) -> float:
    d = risk * multiple
    return entry + d if direction == "alcista" else entry - d


def is_improvement(direction: str, current_sl: float, new_sl: float) -> bool:
    if not current_sl:
        return True
    return new_sl > current_sl if direction == "alcista" else new_sl < current_sl


def process_position(ticket):
    tracked = get_position_state(int(ticket))
    if tracked is None:
        return

    mt5 = get_mt5_connection()
    positions = mt5.positions_get(ticket=int(ticket))
    if not positions:
        remove_position(int(ticket))  # cerrada por SL, TP final o manualmente
        return

    pos = positions[0]
    direction = tracked["direction"]
    entry = tracked["entry_price"]
    risk = tracked["risk_distance"]
    levels_hit = list(tracked["tp_levels_hit"])
    current_sl = float(pos.sl)

    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None:
        return
    price = float(tick.bid if direction == "alcista" else tick.ask)

    # 1) Niveles nuevos alcanzados (TP1 y TP2) -> SL escalonado
    newly_hit = []
    ladder_sl = None
    for i in (0, 1):
        if i in levels_hit:
            continue
        target = level_price(direction, entry, risk, MULTI_TP_LEVELS[i][0])
        reached = price >= target if direction == "alcista" else price <= target
        if not reached:
            break
        newly_hit.append(i)
        ladder_sl = entry if i == 0 else level_price(direction, entry, risk, MULTI_TP_LEVELS[0][0])

    # 2) Trailing por ATR, solo después de TP2
    trailing_sl = None
    if 1 in levels_hit or 1 in newly_hit:
        df = fetch_mt5_candles(standard_symbol(pos.symbol), "H1", TRAILING_CANDLES)
        atr = float(calculate_atr(df).iloc[-1])
        if direction == "alcista":
            trailing_sl = price - atr * ATR_TRAILING_MULTIPLIER
        else:
            trailing_sl = price + atr * ATR_TRAILING_MULTIPLIER

    candidates = [c for c in (ladder_sl, trailing_sl) if c is not None]
    if not candidates:
        return
    best_sl = max(candidates) if direction == "alcista" else min(candidates)

    if is_improvement(direction, current_sl, best_sl):
        result = modify_position_sl(int(ticket), best_sl)
        if not result["success"]:
            print(f"  [ERROR] {pos.symbol} ticket {ticket}: {result.get('error')} (se reintenta)")
            return  # no se marcan los niveles; se reintenta en el próximo ciclo
        etiqueta = "SL ESCALONADO" if newly_hit else "TRAILING"
        niveles = ", ".join(f"TP{i + 1}" for i in newly_hit)
        extra = f" tras {niveles}" if niveles else ""
        print(f"  [{etiqueta}] {pos.symbol} ticket {ticket}{extra}: SL {current_sl} -> {round(best_sl, 5)}")

    for i in newly_hit:
        mark_tp_level_hit(int(ticket), i)


def process_all_positions():
    for ticket in get_all_tracked_tickets():
        try:
            process_position(ticket)
        except Exception as e:
            print(f"  [ERROR] procesando ticket {ticket}: {e}")


def run_monitor():
    print(f"Iniciando monitor de posiciones (cada {CHECK_INTERVAL_SECONDS}s | "
          f"trailing {ATR_TRAILING_MULTIPLIER}x ATR después de TP2)")
    while True:
        process_all_positions()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_monitor()
