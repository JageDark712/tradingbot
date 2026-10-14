import pytest
import numpy as np
import pandas as pd
import zlib
import config.settings as S
import scanner.run_scan as rs
from backtest.engine import run_backtest
from backtest.metrics import calculate_metrics

@pytest.fixture
def mock_scanner(monkeypatch):
    seen = {}
    STEP = {"D1": 1440, "H4": 240, "H1": 60}

    def synth(symbol, tf, n=200):
        seen.setdefault(symbol, set()).add(tf)
        seed = zlib.crc32(f"{symbol}".encode()) % 10_000
        rng = np.random.default_rng(seed + {"D1": 1, "H4": 2, "H1": 3}[tf])
        kind = seed % 10                       # 0-3 sube, 4-6 baja, 7-9 lateral
        vol = 0.004 * (STEP[tf] / 1440) ** 0.5 + 0.0005
        mu = (0.9 * vol) if kind <= 3 else (-0.9 * vol) if kind <= 6 else 0.0
        close = 100 * np.exp(np.cumsum(rng.normal(mu, vol, n)))
        spread = np.abs(rng.normal(0, vol / 2, n)) * close
        t0 = pd.Timestamp("2026-01-01")
        return pd.DataFrame({
            "time": [t0 + pd.Timedelta(minutes=STEP[tf] * i) for i in range(n)],
            "open": close, "high": close + spread, "low": close - spread, "close": close,
            "tick_volume": 1000, "symbol": symbol
        })

    monkeypatch.setattr(rs, "fetch_mt5_candles", synth)
    return seen

def test_pipeline_smoke(mock_scanner):
    seen = mock_scanner
    df = rs.run_full_scan()

    universo = S.FOREX_SYMBOLS + S.CRYPTO_SYMBOLS + S.COMMODITY_SYMBOLS + S.ETF_SYMBOLS

    # 1. All symbols analyzed
    assert len(seen) == len(universo)

    # 2. Required columns present
    required_cols = {"entry_price", "sl_price", "tp_price", "regime", "raw_momentum"}
    assert required_cols <= set(df.columns)

    # 3. Risk/Reward ratio check
    riesgo = (df.entry_price - df.sl_price).abs()
    recompensa = (df.tp_price - df.entry_price).abs()
    esperado = S.TP_ATR_MULTIPLIER / S.SL_ATR_MULTIPLIER

    # Use a small tolerance for float comparisons
    np.testing.assert_allclose(recompensa / riesgo, esperado, atol=0.02)

    # 4. Correct side for SL/TP
    for row in df.itertuples():
        if row.direction == "alcista":
            assert row.sl_price < row.entry_price < row.tp_price
        elif row.direction == "bajista":
            assert row.tp_price < row.entry_price < row.sl_price

def test_backtest_execution(monkeypatch):
    def synth(symbol, tf, n=200):
        rng = np.random.default_rng(42)
        c = 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.001, n)))
        sp = np.abs(rng.normal(0, 0.001, n)) * c
        t0 = pd.Timestamp("2026-01-01")
        return pd.DataFrame({
            "time": [t0 + pd.Timedelta(hours=i) for i in range(n)],
            "open": c, "high": c + sp, "low": c - sp, "close": c
        })


    monkeypatch.setattr("data.fetch_mt5.fetch_mt5_candles", synth)
    # backtest.engine imports fetch_mt5_candles from data.fetch_mt5,
    # so patching the source is sufficient if we patch it before the engine uses it.
    # However, if it was already imported as 'from data.fetch_mt5 import fetch_mt5_candles',
    # we need to patch the reference in backtest.engine as well.
    try:
        monkeypatch.setattr("backtest.engine.fetch_mt5_candles", synth)
    except AttributeError:
        pass # already handled by data.fetch_mt5 patch if imported dynamically


    d1 = synth("EURUSD", "D1", 600)
    h4 = synth("EURUSD", "H4", 1500)
    h1 = synth("EURUSD", "H1", 5000)

    tr = run_backtest(d1, h4, h1)
    assert tr is not None
    if len(tr) > 0:
        metrics = calculate_metrics(tr)
        assert "profit_factor" in metrics
