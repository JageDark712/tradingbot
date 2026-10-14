import pytest
import numpy as np
import pandas as pd
import os
import tempfile
import types
from collections import namedtuple

import execution.position_tracker as tracker
import data.fetch_mt5 as fm
import execution.mt5_executor as ex
import execution.multi_tp_monitor as mon
import scanner.run_live as rl
from risk.engine import RiskEngine

# --- Mocks ---
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
            p = s.positions[req["position"]]
            s.positions[p.ticket] = p._replace(sl=req["sl"])
            return R(retcode=10009, comment="ok", order=0)
        if req["symbol"] in s.market_closed:
            return R(retcode=10018, comment="Market closed", order=0)
        s.next_ticket += 1
        s.positions[s.next_ticket] = Pos(s.next_ticket, req["symbol"], req["type"], req["volume"], req["sl"], req["tp"], req["price"])
        return R(retcode=10009, comment="ok", order=s.next_ticket)

@pytest.fixture(autouse=True)
def setup_mt5_mocks(monkeypatch):
    mt5 = FakeMT5()
    monkeypatch.setattr(fm, "get_mt5_connection", lambda: mt5)
    monkeypatch.setattr(ex, "get_mt5_connection", lambda: mt5)
    monkeypatch.setattr(mon, "get_mt5_connection", lambda: mt5)

    def fake_fetch(sym, tf, n=200):
        return pd.DataFrame({"open": np.full(n, 100.0), "high": np.full(n, 100.5), "low": np.full(n, 99.5), "close": np.full(n, 100.0)})
    monkeypatch.setattr(mon, "fetch_mt5_candles", fake_fetch)

    return mt5

@pytest.fixture
def temp_tracker(tmp_path):
    tracker.TRACKER_FILE = str(tmp_path / "state.json")
    if os.path.exists(tracker.TRACKER_FILE):
        os.remove(tracker.TRACKER_FILE)
    return tracker

def test_monitor_buy_logic(setup_mt5_mocks, temp_tracker):
    mt5 = setup_mt5_mocks
    tracker.register_position(7, "ETHUSDm", "alcista", 100.0, 1.5)
    mt5.positions[7] = Pos(7, "ETHUSDm", 0, 0.01, 98.5, 104.5, 100.0)

    # Under TP1
    mt5.ticks["ETHUSDm"] = Tick(100.5, 100.52)
    mon.process_position(7)
    assert mt5.positions[7].sl == 98.5

    # Reach TP1 -> Breakeven
    mt5.ticks["ETHUSDm"] = Tick(100.8, 100.82)
    mon.process_position(7)
    assert mt5.positions[7].sl == 100.0

    # Reach TP2 -> SL to TP1 level
    mt5.ticks["ETHUSDm"] = Tick(101.6, 101.62)
    mon.process_position(7)
    assert abs(mt5.positions[7].sl - 100.75) < 1e-9

    # Trailing
    mt5.ticks["ETHUSDm"] = Tick(103.5, 103.52)
    mon.process_position(7)
    assert mt5.positions[7].sl > 100.75

    # No loosen SL
    sl_before = mt5.positions[7].sl
    mt5.ticks["ETHUSDm"] = Tick(102.0, 102.02)
    mon.process_position(7)
    assert mt5.positions[7].sl == sl_before

def test_monitor_sell_logic(setup_mt5_mocks, temp_tracker):
    mt5 = setup_mt5_mocks
    tracker.register_position(9, "EURUSDm", "bajista", 100.0, 1.5)
    mt5.positions[9] = Pos(9, "EURUSDm", 1, 0.01, 101.5, 95.5, 100.0)

    # Reach TP1
    mt5.ticks["EURUSDm"] = Tick(99.2, 99.25)
    mon.process_position(9)
    assert mt5.positions[9].sl == 100.0

    # Reach TP2
    mt5.ticks["EURUSDm"] = Tick(98.4, 98.45)
    mon.process_position(9)
    assert abs(mt5.positions[9].sl - 99.25) < 1e-9

    # Trailing
    mt5.ticks["EURUSDm"] = Tick(96.0, 96.05)
    mon.process_position(9)
    assert mt5.positions[9].sl < 99.25

def test_monitor_fail_retry(setup_mt5_mocks, temp_tracker):
    mt5 = setup_mt5_mocks
    tracker.register_position(10, "ETHUSDm", "alcista", 100.0, 1.5)
    mt5.positions[10] = Pos(10, "ETHUSDm", 0, 0.01, 98.5, 104.5, 100.0)
    mt5.ticks["ETHUSDm"] = Tick(100.8, 100.82)
    mt5.fail_next = [10016]

    mon.process_position(10)
    assert tracker.get_position_state(10)["tp_levels_hit"] == []

    mon.process_position(10)
    assert mt5.positions[10].sl == 100.0
    assert tracker.get_position_state(10)["tp_levels_hit"] == [0]

def test_selection_lot_fixed(setup_mt5_mocks):
    mt5 = setup_mt5_mocks
    info = types.SimpleNamespace(trade_mode=4, volume_min=0.01, volume_step=0.01, volume_max=100.0, point=0.01)
    for s in ["BTCUSDm", "SOLUSDm", "ETHUSDm", "EURUSDm"]: mt5.info[s] = info
    mt5.info["EURUSDm"] = types.SimpleNamespace(trade_mode=4, volume_min=0.01, volume_step=0.01, volume_max=100.0, point=0.00001)
    mt5.info["SOLUSDm"] = types.SimpleNamespace(trade_mode=0, volume_min=0.01, volume_step=0.01, volume_max=100.0, point=0.01)
    mt5.loss_per_lot.update({"BTCUSDm": 650.0, "ETHUSDm": 12.0, "EURUSDm": 200.0, "SOLUSDm": 1.2})
    for s_, b_ in [("BTCUSDm", 84800.0), ("SOLUSDm", 120.0), ("ETHUSDm", 2690.0), ("EURUSDm", 1.125)]: mt5.ticks[s_] = Tick(b_, b_ * 1.0001)
    mt5.market_closed.add("EURUSDm")

    cands = pd.DataFrame([
        dict(symbol="BTCUSD", category="crypto", direction="alcista", strength=0.80, entry_price=84800.0, sl_price=84150.0, tp_price=86750.0),
        dict(symbol="SOLUSD", category="crypto", direction="alcista", strength=0.75, entry_price=120.0, sl_price=118.8, tp_price=123.6),
        dict(symbol="EURUSD", category="forex",  direction="bajista", strength=0.70, entry_price=1.125, sl_price=1.127, tp_price=1.119),
        dict(symbol="ETHUSD", category="crypto", direction="alcista", strength=0.65, entry_price=2690.0, sl_price=2678.0, tp_price=2726.0),
    ])

    eng = RiskEngine(account_balance=500.0)
    rl.select_and_execute(cands, eng, set(), 500.0)

    sent_open = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_DEAL and r["symbol"] in ("BTCUSDm", "ETHUSDm")]
    assert len(sent_open) == 2
    assert all(r["volume"] == 0.01 for r in sent_open)

def test_selection_risk_limit(setup_mt5_mocks):
    mt5 = setup_mt5_mocks
    info = types.SimpleNamespace(trade_mode=4, volume_min=0.01, volume_step=0.01, volume_max=100.0, point=0.01)
    for s in ["BTCUSDm", "SOLUSDm", "ETHUSDm", "EURUSDm"]: mt5.info[s] = info
    mt5.loss_per_lot.update({"BTCUSDm": 650.0, "ETHUSDm": 12.0})
    for s_, b_ in [("BTCUSDm", 84800.0), ("ETHUSDm", 2690.0)]: mt5.ticks[s_] = Tick(b_, b_ * 1.0001)

    cands = pd.DataFrame([
        dict(symbol="BTCUSD", category="crypto", direction="alcista", strength=0.80, entry_price=84800.0, sl_price=84150.0, tp_price=86750.0),
        dict(symbol="ETHUSD", category="crypto", direction="alcista", strength=0.65, entry_price=2690.0, sl_price=2678.0, tp_price=2726.0),
    ])

    # With $50, BTC should be omitted (risk ~13% > 3%)
    eng = RiskEngine(account_balance=50.0)
    rl.select_and_execute(cands, eng, set(), 50.0)

    sent_symbols = [r["symbol"] for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_DEAL]
    assert "ETHUSDm" in sent_symbols
    assert "BTCUSDm" not in sent_symbols
