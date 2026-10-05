"""
Ejecutor de órdenes en MT5, con SL/TP incluidos en la misma orden
(bracket order nativo de MT5).
"""
from config.symbols import to_mt5_symbol
from data.fetch_mt5 import get_mt5_connection


def execute_mt5_order(symbol: str, direction: str, volume: float, sl_price: float, tp_price: float) -> dict:
    """
    Envía una orden de mercado en MT5 con SL y TP incluidos.

    Args:
        symbol: símbolo estándar, ej. "EURUSD"
        direction: "alcista" o "bajista"
        volume: tamaño en lotes
        sl_price: precio de stop loss
        tp_price: precio de take profit

    Returns:
        dict con el resultado de la orden
    """
    mt5 = get_mt5_connection()
    mt5_symbol = to_mt5_symbol(symbol)

    mt5.symbol_select(mt5_symbol, True)
    tick = mt5.symbol_info_tick(mt5_symbol)

    if tick is None:
        return {"success": False, "error": f"No se pudo obtener precio actual de {mt5_symbol}"}

    order_type = mt5.ORDER_TYPE_BUY if direction == "alcista" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "alcista" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": mt5_symbol,
        "volume": float(round(volume, 2)),
        "type": order_type,
        "price": float(price),
        "sl": float(round(sl_price, 5)),
        "tp": float(round(tp_price, 5)),
        "deviation": 20,
        "magic": 123456,
        "comment": "scanner_multiestrategia",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result is None:
        return {"success": False, "error": f"order_send devolvió None. Último error: {mt5.last_error()}"}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"retcode={result.retcode}, comment={result.comment}"}

    from execution.position_tracker import register_position
    risk_distance = abs(price - sl_price)
    register_position(result.order, symbol, direction, price, risk_distance)

    return {
        "success": True,
        "order_id": result.order,
        "symbol": symbol,
        "direction": direction,
        "volume": volume,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
    }


def get_open_mt5_positions() -> list:
    """Devuelve las posiciones abiertas actualmente en MT5."""
    mt5 = get_mt5_connection()
    positions = mt5.positions_get()
    if positions is None:
        return []
    return [p._asdict() for p in positions]


def close_mt5_position(ticket: int) -> dict:
    """Cierra una posición abierta por su número de ticket."""
    mt5 = get_mt5_connection()
    positions = mt5.positions_get(ticket=ticket)

    if not positions:
        return {"success": False, "error": f"No se encontró posición con ticket {ticket}"}

    pos = positions[0]
    tick = mt5.symbol_info_tick(pos.symbol)

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "cierre_senal_contraria",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"No se pudo cerrar ticket {ticket}"}

    return {"success": True, "ticket": ticket}


def partial_close_position(ticket: int, volume_to_close: float) -> dict:
    """Cierra una fracción del volumen de una posición abierta."""
    mt5 = get_mt5_connection()
    positions = mt5.positions_get(ticket=ticket)

    if not positions:
        return {"success": False, "error": f"No se encontró posición con ticket {ticket}"}

    pos = positions[0]
    tick = mt5.symbol_info_tick(pos.symbol)

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = float(tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": float(round(volume_to_close, 2)),
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "cierre_parcial_tp",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"No se pudo cerrar parcialmente ticket {ticket}"}

    return {"success": True, "ticket": ticket, "volume_closed": volume_to_close}


def modify_position_sl(ticket: int, new_sl: float) -> dict:
    """Modifica el stop loss de una posición abierta (sin tocar el TP)."""
    mt5 = get_mt5_connection()
    positions = mt5.positions_get(ticket=ticket)

    if not positions:
        return {"success": False, "error": f"No se encontró posición con ticket {ticket}"}

    pos = positions[0]

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": pos.symbol,
        "position": ticket,
        "sl": float(round(new_sl, 5)),
        "tp": float(pos.tp),
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"No se pudo modificar SL de ticket {ticket}"}

    return {"success": True, "ticket": ticket, "new_sl": new_sl}


def get_effective_balance() -> float:
    """Balance real de la cuenta, limitado por OPERATING_CAPITAL si está definido."""
    from config.settings import OPERATING_CAPITAL
    mt5 = get_mt5_connection()
    info = mt5.account_info()
    balance = float(info.balance)
    if OPERATING_CAPITAL is not None:
        balance = min(balance, float(OPERATING_CAPITAL))
    return balance


def calculate_mt5_volume(symbol: str, direction: str, entry_price: float,
                         sl_price: float, risk_amount: float,
                         max_overshoot: float = 1.5) -> dict:
    """
    Convierte un riesgo monetario en lotes reales de MT5, usando la pérdida
    exacta por lote (order_calc_profit) y respetando lote mínimo/paso/máximo.
    Si el lote mínimo arriesga más de max_overshoot veces lo permitido, no opera.
    """
    import math
    mt5 = get_mt5_connection()
    mt5_symbol = to_mt5_symbol(symbol)
    mt5.symbol_select(mt5_symbol, True)
    info = mt5.symbol_info(mt5_symbol)

    if info is None:
        return {"volume": None, "reason": f"sin información del símbolo {mt5_symbol}"}

    order_type = mt5.ORDER_TYPE_BUY if direction == "alcista" else mt5.ORDER_TYPE_SELL
    pnl_1lot = mt5.order_calc_profit(order_type, mt5_symbol, 1.0, float(entry_price), float(sl_price))

    if pnl_1lot is None or pnl_1lot >= 0:
        return {"volume": None, "reason": "no se pudo calcular la pérdida por lote"}

    loss_per_lot = abs(float(pnl_1lot))
    step, vmin, vmax = float(info.volume_step), float(info.volume_min), float(info.volume_max)

    volume = math.floor(risk_amount / loss_per_lot / step + 1e-9) * step

    if volume < vmin:
        min_risk = vmin * loss_per_lot
        if min_risk > risk_amount * max_overshoot:
            return {
                "volume": None,
                "reason": f"lote mínimo ({vmin}) arriesgaría ${min_risk:.2f} vs ${risk_amount:.2f} permitido",
            }
        volume = vmin

    volume = round(min(volume, vmax), 2)
    return {"volume": volume, "actual_risk": volume * loss_per_lot, "reason": "OK"}


def estimate_position_open_risk(pos: dict) -> float:
    """Riesgo actual (en dinero) de una posición abierta, según su SL vigente."""
    mt5 = get_mt5_connection()
    if not pos.get("sl"):
        return 0.0
    order_type = mt5.ORDER_TYPE_BUY if pos["type"] == 0 else mt5.ORDER_TYPE_SELL
    profit = mt5.order_calc_profit(
        order_type, pos["symbol"], float(pos["volume"]),
        float(pos["price_open"]), float(pos["sl"]),
    )
    if profit is None:
        return 0.0
    return max(0.0, -float(profit))
