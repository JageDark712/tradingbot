"""
Full Backtest Orchestrator: Runs the UnifiedEngine across 4 configurations.
Outputs results to reports/backtest_full.csv.
"""
import sys
import types
import os

# Mock mt5linux before any other imports that might depend on it
mt5_mock = types.ModuleType("mt5linux")
class MockMT5:
    def __init__(self): pass
    def initialize(self): return True
    def shutdown(self): pass
    def symbol_info(self, sym): return types.SimpleNamespace(spread=10, point=0.00001)
    def copy_rates_from_pos(self, *args):
        import pandas as pd
        import numpy as np
        return pd.DataFrame({"close": np.random.randn(100)})
mt5_mock.MetaTrader5 = MockMT5
sys.modules["mt5linux"] = mt5_mock

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime

from backtest.unified_engine import UnifiedBacktestEngine
from scanner.run_scan import run_full_scan_on_data
from config.settings import FOREX_SYMBOLS, CRYPTO_SYMBOLS, COMMODITY_SYMBOLS, ETF_SYMBOLS

def load_historical_data(symbol: str) -> Dict[str, pd.DataFrame]:
    """
    Mocks loading historical data for backtesting.
    """
    dates = pd.date_range("2025-01-01", periods=2000, freq="H")
    np.random.seed(42)
    returns = np.random.normal(0, 0.001, 2000)
    price = 100 * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "time": dates,
        "open": price,
        "high": price + 0.1,
        "low": price - 0.1,
        "close": price + 0.05
    })
    return {"H1": df}

def run_config(name: str, cost_atr: float, symbols: List[str], use_regime: bool):
    print(f"Running Config: {name} (Cost: {cost_atr}, Regime: {use_regime})")
    engine = UnifiedBacktestEngine(cost_atr=cost_atr)
    all_trades = []

    for symbol in symbols:
        data = load_historical_data(symbol)
        df_h1 = data["H1"]

        # Integration with LIVE scan logic
        try:
            signals = run_full_scan_on_data(symbol, data)
            trades = engine.simulate_trade_logic(symbol, df_h1, signals)
            all_trades.extend(trades)
        except Exception as e:
            print(f"  [ERROR] {symbol}: {e}")

    if not all_trades:
        return pd.DataFrame(columns=["symbol", "entry_time", "exit_time", "direction", "entry_price", "exit_price", "exit_reason", "pnl_r", "bars_held", "config"])

    df_results = pd.DataFrame([t.__dict__ for t in all_trades])
    df_results["config"] = name
    return df_results

def main():
    universo = FOREX_SYMBOLS + CRYPTO_SYMBOLS + COMMODITY_SYMBOLS + ETF_SYMBOLS

    configs = [
        {"name": "baseline", "cost": 0.0, "regime": True},
        {"name": "real_costs", "cost": 0.1, "regime": True},
        {"name": "no_regime", "cost": 0.0, "regime": False},
        {"name": "stress_costs", "cost": 0.3, "regime": True},
    ]

    final_results = []
    for cfg in configs:
        res = run_config(cfg["name"], cfg["cost"], universo, cfg["regime"])
        if not res.empty:
            final_results.append(res)

    if not final_results:
        print("No trades generated in any configuration.")
        return

    full_df = pd.concat(final_results)

    # Simple temporal split
    all_dates = sorted(full_df["entry_time"].unique())
    split_idx = int(len(all_dates) * 0.7)
    split_date = all_dates[split_idx] if all_dates else None

    print("\n" + "="*40)
    print("BACKTEST SUMMARY")
    print("="*40)
    for cfg in configs:
        cfg_df = full_df[full_df["config"] == cfg["name"]]
        if cfg_df.empty:
            print(f"{cfg['name']}: No trades")
            continue
        win_rate = len(cfg_df[cfg_df["pnl_r"] > 0]) / len(cfg_df)
        profit_factor = abs(cfg_df[cfg_df["pnl_r"] < 0]["pnl_r"].sum()) / (cfg_df[cfg_df["pnl_r"] > 0]["pnl_r"].sum() + 1e-9)
        print(f"{cfg['name']}: Trades={len(cfg_df)}, WinRate={win_rate:.1%}, PF={profit_factor:.2f}, Total R={cfg_df['pnl_r'].sum():.2f}")

    os.makedirs("reports", exist_ok=True)
    full_df.to_csv("reports/backtest_full.csv", index=False)
    print(f"\nFull results saved to reports/backtest_full.csv")

if __name__ == "__main__":
    main()
