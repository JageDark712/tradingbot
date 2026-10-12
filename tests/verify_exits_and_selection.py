import sys, types, io, contextlib, os, tempfile
from collections import namedtuple
sys.path.insert(0, ".")
import numpy as np, pandas as pd

# ---- stubs de librerías externas ----
for name in ["mt5linux", "binance", "binance.client", "binance.enums", "dotenv"]:
    m = types.ModuleType(name); m.MetaTrader5 = object
    m.Client = type("Client", (), {k: 1 for k in ["KLINE_INTERVAL_1MINUTE","KLINE_INTERVAL_5MINUTE","KLINE_INTERVAL_15MINUTE","KLINE_INTERVAL_30MINUTE","KLINE_INTERVAL_1HOUR","KLINE_INTERVAL_4HOUR","KLINE_INTERVAL_1DAY","KLINE_INTERVAL_1WEEK"]})
    m.load_dotenv = lambda *a, **k: None
    sys.modules[name] = m

import execution.position_tracker as tracker
tracker.TRACKER_FILE = os.path.join(tempfile.mkdtemp(), "state.json")
import data.fetch_mt5 as fm
import execution.mt5_executor as ex
import execution.multi_tp_monitor as mon
import scanner.run_live as rl

Pos = namedtuple("Pos", "ticket symbol type volume sl tp price_open")

class Tick: 
    def __init__(s, bid, ask): s.bid, s.ask = bid, ask

class FakeMT5:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP = 1, 6
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC, ORDER_FILLING_FOK, ORDER_FILLING_RETURN = 1, 0, 2
    TRADE_RETCODE_DONE = 10009
    def __init__(s):
        s.positions, s.ticks, s.sent, s.fail_next, s.info = {}, {}, [], [], {}
        s.loss_per_lot = {}; s.market_closed = set(); s.next_ticket = 1000
    def symbol_select(s, *a): return True
    def last_error(s): return (1, "ok")
    def symbol_info_tick(s, sym): return s.ticks.get(sym)
    def symbol_info(s, sym): return s.info.get(sym)
    def positions_get(s, ticket=None):
        if ticket is None: return list(s.positions.values())
        return [s.positions[ticket]] if ticket in s.positions else []
    def order_calc_profit(s, otype, sym, vol, p_open, p_close):
        return -s.loss_per_lot.get(sym, 5.0) * vol
    def order_send(s, req):
        s.sent.append(req)
        R = types.SimpleNamespace
        if s.fail_next:
            code = s.fail_next.pop(0); return R(retcode=code, comment=f"fail {code}", order=0)
        if req["action"] == s.TRADE_ACTION_SLTP:
            p = s.positions[req["position"]]; s.positions[p.ticket] = p._replace(sl=req["sl"])
            return R(retcode=10009, comment="ok", order=0)
        if req["symbol"] in s.market_closed:
            return R(retcode=10018, comment="Market closed", order=0)
        s.next_ticket += 1
        s.positions[s.next_ticket] = Pos(s.next_ticket, req["symbol"], req["type"], req["volume"], req["sl"], req["tp"], req["price"])
        return R(retcode=10009, comment="ok", order=s.next_ticket)

mt5 = FakeMT5()
fm.get_mt5_connection = lambda: mt5; ex.get_mt5_connection = lambda: mt5; mon.get_mt5_connection = lambda: mt5
fetch_calls = []
def fake_fetch(sym, tf, n=200):
    fetch_calls.append(sym)
    # velas con rango constante 1.0 -> ATR ≈ 1.0
    c = np.full(n, 100.0); return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c})
mon.fetch_mt5_candles = fake_fetch

def run(f, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): f(*a)
    return buf.getvalue().strip()

checks = []
def check(name, cond, extra=""):
    checks.append(cond); print(("OK   " if cond else "FALLA"), name, extra)

# ================= MONITOR: compra =================
tracker.register_position(7, "ETHUSDm", "alcista", 100.0, 1.5)   # riesgo original 1.5 (SL 98.5)
mt5.positions[7] = Pos(7, "ETHUSDm", 0, 0.01, 98.5, 104.5, 100.0)
def set_price(p): mt5.ticks["ETHUSDm"] = Tick(p, p + 0.02)
sl = lambda: mt5.positions[7].sl

set_price(100.5); out = run(mon.process_position, 7)
check("compra: bajo TP1 no toca nada", sl() == 98.5 and out == "")
set_price(100.8); out = run(mon.process_position, 7)
check("compra: TP1 (0.75) -> SL a breakeven", sl() == 100.0, f"| {out}")
set_price(101.6); out = run(mon.process_position, 7)
check("compra: TP2 (1.5) -> SL al nivel de TP1", abs(sl() - 100.75) < 1e-9, f"| {out}")
check("trailing pidió velas con símbolo SIN doble 'm'", fetch_calls[-1] == "ETHUSD", f"(pidió '{fetch_calls[-1]}')")
set_price(103.5); out = run(mon.process_position, 7)
check("compra: trailing sube el SL (103.5 - 2*ATR)", sl() > 100.75 and sl() < 103.5, f"| SL={sl():.3f}")
sl_before = sl(); set_price(102.0); out = run(mon.process_position, 7)
check("compra: si el precio retrocede el SL NO se afloja", sl() == sl_before and out == "")
mt5.positions.pop(7); run(mon.process_position, 7)
check("posición cerrada -> se quita del registro", tracker.get_position_state(7) is None)

# ---- escenario del bug del monitor anterior: entrada 100, SL trailing en 104, precio 108
tracker.register_position(8, "ETHUSDm", "alcista", 100.0, 1.5)
tracker.mark_tp_level_hit(8, 0); tracker.mark_tp_level_hit(8, 1)
mt5.positions[8] = Pos(8, "ETHUSDm", 0, 0.01, 104.0, 120.0, 100.0)
mt5.ticks["ETHUSDm"] = Tick(108.0, 108.02); run(mon.process_position, 8)
check("bug anterior: SL en 104 y precio 108 -> NO baja a 100", mt5.positions[8].sl >= 104.0, f"| SL={mt5.positions[8].sl}")

# ================= MONITOR: venta =================
tracker.register_position(9, "EURUSDm", "bajista", 100.0, 1.5)
mt5.positions[9] = Pos(9, "EURUSDm", 1, 0.01, 101.5, 95.5, 100.0)
mt5.ticks["EURUSDm"] = Tick(99.2, 99.25); run(mon.process_position, 9)
check("venta: TP1 -> SL a breakeven", mt5.positions[9].sl == 100.0)
mt5.ticks["EURUSDm"] = Tick(98.4, 98.45); run(mon.process_position, 9)
check("venta: TP2 -> SL al nivel de TP1", abs(mt5.positions[9].sl - 99.25) < 1e-9, f"| SL={mt5.positions[9].sl}")
mt5.ticks["EURUSDm"] = Tick(96.0, 96.05); run(mon.process_position, 9)
check("venta: trailing baja el SL", mt5.positions[9].sl < 99.25, f"| SL={mt5.positions[9].sl:.3f}")

# ---- fallo al modificar: no marca niveles y reintenta
tracker.register_position(10, "ETHUSDm", "alcista", 100.0, 1.5)
mt5.positions[10] = Pos(10, "ETHUSDm", 0, 0.01, 98.5, 104.5, 100.0)
mt5.ticks["ETHUSDm"] = Tick(100.8, 100.82); mt5.fail_next = [10016]
out = run(mon.process_position, 10)
check("fallo 10016: muestra retcode y NO marca el nivel", "retcode=10016" in out and tracker.get_position_state(10)["tp_levels_hit"] == [], f"| {out}")
run(mon.process_position, 10)
check("reintento en el siguiente ciclo funciona", mt5.positions[10].sl == 100.0 and tracker.get_position_state(10)["tp_levels_hit"] == [0])

# ================= SELECCIÓN / LOTE FIJO =================
from risk.engine import RiskEngine
def info(mode=4, point=0.01): return types.SimpleNamespace(trade_mode=mode, volume_min=0.01, volume_step=0.01, volume_max=100.0, point=point)
for s in ["BTCUSDm", "SOLUSDm", "ETHUSDm", "EURUSDm"]: mt5.info[s] = info()
mt5.info["EURUSDm"] = info(point=0.00001)
mt5.info["SOLUSDm"] = info(0)              # trading deshabilitado
mt5.loss_per_lot.update({"BTCUSDm": 650.0, "ETHUSDm": 12.0, "EURUSDm": 200.0, "SOLUSDm": 1.2})
for s_, b_ in [("BTCUSDm", 84800.0), ("SOLUSDm", 120.0), ("ETHUSDm", 2690.0), ("EURUSDm", 1.125)]: mt5.ticks[s_] = Tick(b_, b_ * 1.0001)
mt5.market_closed.add("EURUSDm")
mt5.positions.clear(); mt5.sent.clear()

cands = pd.DataFrame([
    dict(symbol="BTCUSD", category="crypto", direction="alcista", strength=0.80, entry_price=84800.0, sl_price=84150.0, tp_price=86750.0),
    dict(symbol="SOLUSD", category="crypto", direction="alcista", strength=0.75, entry_price=120.0, sl_price=118.8, tp_price=123.6),
    dict(symbol="EURUSD", category="forex",  direction="bajista", strength=0.70, entry_price=1.125, sl_price=1.127, tp_price=1.119),
    dict(symbol="ETHUSD", category="crypto", direction="alcista", strength=0.65, entry_price=2690.0, sl_price=2678.0, tp_price=2726.0),
])
eng = RiskEngine(account_balance=500.0)
out = run(rl.select_and_execute, cands, eng, set(), 500.0)
print("---- salida de select_and_execute (balance $500) ----"); print(out); print("----")
check("SOL con trading deshabilitado: se salta SIN intentar orden", "[NO OPERABLE] SOLUSD" in out and not any(r.get("symbol") == "SOLUSDm" for r in mt5.sent))
check("EUR con mercado cerrado: falla y pasa a la siguiente candidata", "[MERCADO CERRADO] EURUSD" in out and "[EJECUTADO] ETHUSD" in out)
sent_open = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_DEAL and r["symbol"] in ("BTCUSDm", "ETHUSDm")]
check("BTC y ETH ejecutadas con lote 0.01 (float) a $500", len(sent_open) == 2 and all(r["volume"] == 0.01 and isinstance(r["volume"], float) for r in sent_open), f"({len(sent_open)} órdenes)")
check("a $500 BTC arriesga ~$6.50 (1.3%) y pasa el tope", "[EJECUTADO] BTCUSD alcista | lotes=0.01 | riesgo=$6.50" in out)
check("las ejecutadas quedan registradas para el monitor (con riesgo original)", all(tracker.get_position_state(t) and tracker.get_position_state(t)["risk_distance"] > 0 for t in mt5.positions))

mt5.positions.clear(); mt5.sent.clear()
eng2 = RiskEngine(account_balance=50.0)
out2 = run(rl.select_and_execute, cands.iloc[[0, 3]], eng2, set(), 50.0)
print("---- con capital de $50 ----"); print(out2); print("----")
check("con $50, BTC (~13%) se omite por el tope del 3% y ETH (~0.2%) sí entra", "[OMITIDO] BTCUSD" in out2 and "[EJECUTADO] ETHUSD" in out2)

# ================= CICLO COMPLETO (smoke test) =================
mt5.positions.clear(); mt5.sent.clear()
mt5.account_info = lambda: types.SimpleNamespace(balance=500.0)
rl.run_full_scan = lambda: pd.DataFrame([
    dict(symbol="BTCUSD", category="crypto", direction="alcista", strength=0.80, agreement="full", raw_momentum=11.0, entry_price=84800.0, sl_price=84150.0, tp_price=86750.0),
    dict(symbol="EURUSD", category="forex", direction="bajista", strength=0.50, agreement="full", raw_momentum=-2.5, entry_price=1.125, sl_price=1.127, tp_price=1.119),
])
out3 = run(rl.run_one_cycle)
print("---- salida de run_one_cycle ----"); print(out3); print("----")
check("el panel muestra señales de TODAS las categorías antes del umbral", "forex:" in out3 and "crypto:" in out3)
check("las candidatas muestran SL y TP en puntos (BTC: 650 -> 65000 pts)", "sl_pts" in out3 and "tp_pts" in out3 and "65000" in out3)

print(f"\nRESULTADO: {sum(checks)}/{len(checks)} comprobaciones OK")
sys.exit(0 if all(checks) else 1)
