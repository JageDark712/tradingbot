"""
Ejecutor de órdenes en Binance Futures (testnet): permite posiciones
largas y cortas, con SL/TP simulados vía órdenes condicionales
(STOP_MARKET + TAKE_PROFIT_MARKET), equivalente al bracket order de MT5.
"""
from config.symbols import to_binance_symbol
from data.fetch_binance_futures import get_binance_futures_client


def execute_binance_futures_order(symbol: str, direction: str, quantity: float, sl_price: float, tp_price: float) -> dict:
    """
    Ejecuta una orden de mercado en Binance Futures (largo o corto) y
    coloca las órdenes condicionales de SL y TP a continuación.
    """
    client = get_binance_futures_client()
    futures_symbol = to_binance_symbol(symbol)

    side = "BUY" if direction == "alcista" else "SELL"
    close_side = "SELL" if direction == "alcista" else "BUY"

    try:
        market_order = client.futures_create_order(
            symbol=futures_symbol,
            side=side,
            type="MARKET",
            quantity=round(quantity, 3),
        )
    except Exception as e:
        return {"success": False, "error": f"Error en orden de mercado: {e}"}

    try:
        sl_order = client.futures_create_order(
            symbol=futures_symbol,
            side=close_side,
            type="STOP_MARKET",
            stopPrice=round(sl_price, 2),
            closePosition=True,
        )
        tp_order = client.futures_create_order(
            symbol=futures_symbol,
            side=close_side,
            type="TAKE_PROFIT_MARKET",
            stopPrice=round(tp_price, 2),
            closePosition=True,
        )
    except Exception as e:
        return {
            "success": True,
            "market_order_id": market_order["orderId"],
            "sl_tp_error": f"Entrada ejecutada pero falló colocar SL/TP: {e}",
        }

    return {
        "success": True,
        "market_order_id": market_order["orderId"],
        "sl_order_id": sl_order["orderId"],
        "tp_order_id": tp_order["orderId"],
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "sl": sl_price,
        "tp": tp_price,
    }


def get_open_futures_positions() -> list:
    """Devuelve las posiciones abiertas actualmente en Binance Futures."""
    client = get_binance_futures_client()
    positions = client.futures_position_information()
    return [p for p in positions if float(p["positionAmt"]) != 0]


def close_futures_position(symbol: str, direction: str, quantity: float) -> dict:
    """Cierra una posición abierta con una orden de mercado en sentido contrario."""
    client = get_binance_futures_client()
    futures_symbol = to_binance_symbol(symbol)
    close_side = "SELL" if direction == "alcista" else "BUY"

    try:
        result = client.futures_create_order(
            symbol=futures_symbol,
            side=close_side,
            type="MARKET",
            quantity=round(quantity, 3),
            reduceOnly=True,
        )
        return {"success": True, "order_id": result["orderId"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
