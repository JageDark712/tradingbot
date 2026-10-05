"""
Ejecutor de órdenes en Binance: orden de mercado para entrada, seguida de
una orden OCO (SL+TP simultáneos) ya que Binance spot no tiene bracket
order nativo como MT5.
"""
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

from config.symbols import to_binance_symbol
from data.fetch_binance import get_binance_client


def execute_binance_order(symbol: str, direction: str, quantity: float, sl_price: float, tp_price: float) -> dict:
    """
    Ejecuta una orden de mercado en Binance y coloca una orden OCO de
    SL/TP inmediatamente después.

    NOTA: esta implementación cubre posiciones LARGAS (compra). Binance
    spot no permite "vender en corto" directamente como forex/MT5 — para
    señales bajistas en cripto, se necesitaría margin trading o futuros,
    que es un alcance distinto. Por ahora, direction="bajista" se omite.
    """
    if direction == "bajista":
        return {
            "success": False,
            "error": "Binance spot no soporta posiciones cortas; se requiere margin/futuros (fuera de alcance actual)",
        }

    client = get_binance_client()
    binance_symbol = to_binance_symbol(symbol)

    try:
        market_order = client.order_market_buy(symbol=binance_symbol, quantity=round(quantity, 6))
    except Exception as e:
        return {"success": False, "error": f"Error en orden de mercado: {e}"}

    try:
        oco_order = client.create_oco_order(
            symbol=binance_symbol,
            side=SIDE_SELL,
            quantity=round(quantity, 6),
            price=round(tp_price, 5),            # take profit (limit)
            stopPrice=round(sl_price, 5),         # trigger del stop
            stopLimitPrice=round(sl_price * 0.999, 5),  # precio límite del stop (ligeramente por debajo)
            stopLimitTimeInForce="GTC",
        )
    except Exception as e:
        return {
            "success": True,
            "market_order_id": market_order["orderId"],
            "oco_error": f"Entrada ejecutada pero falló el OCO de SL/TP: {e}",
        }

    return {
        "success": True,
        "market_order_id": market_order["orderId"],
        "oco_order_id": oco_order["orderListId"],
        "symbol": symbol,
        "quantity": quantity,
        "sl": sl_price,
        "tp": tp_price,
    }


def get_open_binance_positions() -> list:
    """Devuelve los balances actuales distintos de cero (posiciones abiertas en spot)."""
    client = get_binance_client()
    account = client.get_account()
    return [b for b in account["balances"] if float(b["free"]) > 0 or float(b["locked"]) > 0]
