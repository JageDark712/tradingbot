import pytest
import numpy as np
import pandas as pd
import backtest.engine as engine
import config.settings as settings

# Mock old engine for regression test
import importlib.util
spec = importlib.util.spec_from_file_location("engine_old", "tests/_engine_old_reference.py")
engine_old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_old)

@pytest.fixture
def synthetic_data():
    rng = np.random.default_rng(3)
    n = 6000
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    sp = np.abs(rng.normal(0, 0.002, n)) * c
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": c,
        "high": c + sp,
        "low": c - sp,
        "close": c,
        "atr": np.abs(rng.normal(0.6, 0.1, n)),
        "signal": rng.choice(["alcista", "bajista", "sin_senal"], n, p=[0.04, 0.04, 0.92])
    })
    return df

def test_engine_regression(synthetic_data):
    df = synthetic_data
    t_old = engine_old.simulate_trades(df)
    t_new = engine.simulate_trades(df, sl_mult=1.5, tp_mult=4.5)

    assert len(t_old) == len(t_new)
    assert len(t_old) > 100

    cols = ["entry_time", "exit_time", "direction", "exit_reason", "pnl"]
    for col in cols:
        pd.testing.assert_series_equal(t_old[col], t_new[col])

    pd.testing.assert_series_equal(t_old.entry_price, t_new.entry_price, check_exact=False)
    pd.testing.assert_series_equal(t_old.exit_price, t_new.exit_price, check_exact=False)

def create_path_df(bars, signal_first="alcista"):
    rows = [dict(time=pd.Timestamp("2026-01-01"), open=100, high=100, low=100, close=100, atr=1.0, signal="sin_senal")]
    rows.append(dict(time=pd.Timestamp("2026-01-01 01:00"), open=100, high=100, low=100, close=100, atr=1.0, signal=signal_first))
    for k, (h, l, cl) in enumerate(bars, start=2):
        rows.append(dict(time=pd.Timestamp("2026-01-01") + pd.Timedelta(hours=k), open=cl, high=h, low=l, close=cl, atr=1.0, signal="sin_senal"))
    return pd.DataFrame(rows)

def sim(bars, sig="alcista", sl_mult=1.0, tp_mult=1.5, **kw):
    df = create_path_df(bars, signal_first=sig)
    return engine.simulate_trades(df, sl_mult=sl_mult, tp_mult=tp_mult, **kw)

def test_buy_tp():
    t = sim([(100.4, 99.8, 100.2), (101.6, 100.1, 101.5)])
    assert len(t) == 1
    assert t.pnl[0] == 1.5
    assert t.exit_reason[0] == "TP"

def test_buy_sl():
    t = sim([(100.4, 98.9, 99.2)])
    assert t.pnl[0] == -1.0
    assert t.exit_reason[0] == "SL"

def test_time_limit():
    t = sim([(100.3, 99.8, 100.1), (100.5, 99.9, 100.2), (100.7, 100.0, 100.6), (100.9, 100.2, 100.6)], max_hold_bars=3)
    assert t.exit_reason[0] == "tiempo"
    assert t.bars_held[0] == 3
    assert abs(t.pnl[0] - 0.6) < 1e-9

def test_stepped_sl_breakeven():
    t = sim([(100.6, 100.0, 100.3), (100.4, 99.9, 100.1)], ladder=True)
    assert t.exit_reason[0] == "SL_escalonado"
    assert t.pnl[0] == 0.0

def test_no_stepped_sl():
    t = sim([(100.6, 100.0, 100.3), (100.4, 99.9, 100.1)], ladder=False)
    assert len(t) == 0

def test_stepped_sl_tp1():
    t = sim([(101.1, 100.0, 100.9), (100.9, 100.4, 100.6)], ladder=True)
    assert t.exit_reason[0] == "SL_escalonado"
    assert t.pnl[0] == 0.5

def test_sell_tp():
    t = sim([(100.0, 98.4, 98.9)], sig="bajista", sl_mult=1.0, tp_mult=1.5)
    assert len(t) == 1
    assert t.pnl[0] == 1.5
    assert t.exit_reason[0] == "TP"

def test_sell_sl():
    t = sim([(101.2, 99.9, 101.0)], sig="bajista")
    assert t.pnl[0] == -1.0
    assert t.exit_reason[0] == "SL"

def test_cost_impact():
    t = sim([(101.6, 100.1, 101.5)], cost_atr=0.1)
    assert abs(t.pnl[0] - 1.4) < 1e-9

def test_settings_defaults():
    assert engine.ATR_SL_MULTIPLIER == 1.0
    assert abs(engine.RISK_REWARD_RATIO - 1.5) < 1e-9

def test_multi_tp_derivation():
    # MULTI_TP_LEVELS should be derived from multipliers in settings
    assert abs(settings.MULTI_TP_LEVELS[2][0] - 1.5) < 1e-9
